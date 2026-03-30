"""In-memory file store with LRU eviction (10-entry cap).

Thread-safety is provided by an ``asyncio.Lock`` that MUST be held during
all reads and writes.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Store types
# ---------------------------------------------------------------------------

class FileEntry:
    """A single stored upload."""

    __slots__ = (
        "file_id",
        "dataframe",
        "columns",
        "row_count",
        "context_text",
        "coefficient_cache",
        "r2_key",
        "user_id",
        "content_hash",
        "file_name",
        "file_type",
        "secondary_dataframes",  # dict[filename, DataFrame] for multi-file uploads
    )

    def __init__(
        self,
        file_id: str,
        dataframe: pd.DataFrame,
        columns: list[dict[str, Any]],
        row_count: int,
        context_text: str | None = None,
        coefficient_cache: dict[str, Any] | None = None,
        r2_key: str | None = None,
        user_id: str | None = None,
        content_hash: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        secondary_dataframes: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        self.file_id = file_id
        self.dataframe = dataframe
        self.columns = columns
        self.row_count = row_count
        self.context_text = context_text
        self.coefficient_cache = coefficient_cache
        self.r2_key = r2_key
        self.user_id = user_id
        self.content_hash = content_hash
        self.file_name = file_name
        self.file_type = file_type
        self.secondary_dataframes = secondary_dataframes or {}


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

MAX_ENTRIES: int = 10

file_store: OrderedDict[str, FileEntry] = OrderedDict()
store_lock: asyncio.Lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Helper functions (caller MUST hold ``store_lock``)
# ---------------------------------------------------------------------------

async def get_entry(file_id: str) -> FileEntry | None:
    """Retrieve an entry by *file_id*.  Returns ``None`` if not found."""
    async with store_lock:
        entry = file_store.get(file_id)
        if entry is not None:
            # Move to end to mark as recently used
            file_store.move_to_end(file_id)
        return entry


async def set_entry(entry: FileEntry) -> None:
    """Insert or update an entry, evicting the oldest if at capacity."""
    async with store_lock:
        if entry.file_id in file_store:
            file_store.move_to_end(entry.file_id)
        file_store[entry.file_id] = entry
        # Evict oldest entries while over capacity
        while len(file_store) > MAX_ENTRIES:
            file_store.popitem(last=False)


async def get_or_restore_entry(file_id: str) -> FileEntry | None:
    """Get entry from RAM, or restore from R2 if available (cold-start).

    Flow:
      1. Check RAM (fast path, ~0ms)
      2. RAM miss → query Supabase for r2_key + file_name
      3. Download file bytes from R2
      4. Re-parse with pandas
      5. Store back in RAM cache (subsequent calls instant)
      6. Return restored entry, or None if restore impossible
    """
    # 1. Fast path — RAM hit
    entry = await get_entry(file_id)
    if entry is not None:
        return entry

    # 2. Slow path — try R2 restore
    import logging

    logger = logging.getLogger(__name__)
    logger.info("RAM miss for file_id=%s — attempting R2 restore", file_id)

    try:
        from backend.db import supabase as supa
        from backend.storage import r2

        if not supa.is_available() or not r2.is_available():
            logger.info("R2 or Supabase not available — cannot restore")
            return None

        # 2a. Lookup metadata in Supabase
        import asyncio

        loop = asyncio.get_running_loop()
        meta = await loop.run_in_executor(
            None, supa.get_dataset_by_file_id, file_id,
        )
        if meta is None or not meta.get("r2_key"):
            logger.info("No Supabase metadata for file_id=%s", file_id)
            return None

        r2_key: str = meta["r2_key"]
        file_name: str = meta.get("file_name", "restored.xlsx")

        # 2b. Download from R2
        stream = await loop.run_in_executor(None, r2.get_file_stream, r2_key)
        if stream is None:
            logger.warning("R2 download failed for key=%s", r2_key)
            return None

        # 2c. Determine file type from r2_key extension
        from pathlib import PurePath

        ext = PurePath(r2_key).suffix.lower()

        # 2d. Re-parse
        import io

        content_bytes = stream.read()
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(content_bytes))
        elif ext == ".xls":
            df = pd.read_excel(io.BytesIO(content_bytes), engine="xlrd")
        else:
            df = pd.read_excel(io.BytesIO(content_bytes), engine="openpyxl")

        df.columns = df.columns.str.strip()

        # 2e. Build column metadata
        columns = [
            {
                "name": str(col),
                "dtype": str(df[col].dtype),
                "is_numeric": bool(pd.api.types.is_numeric_dtype(df[col])),
            }
            for col in df.columns
        ]

        # 2f. Store back in RAM
        restored = FileEntry(
            file_id=file_id,
            dataframe=df,
            columns=columns,
            row_count=len(df),
            r2_key=r2_key,
            file_name=file_name,
            file_type=ext,
        )
        await set_entry(restored)
        logger.info("R2 restore complete for file_id=%s (%d rows)", file_id, len(df))
        return restored

    except Exception as exc:
        import logging

        logging.getLogger(__name__).error("R2 restore failed for file_id=%s: %s", file_id, exc)
        return None

