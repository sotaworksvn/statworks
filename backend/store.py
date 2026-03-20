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
    ) -> None:
        self.file_id = file_id
        self.dataframe = dataframe
        self.columns = columns
        self.row_count = row_count
        self.context_text = context_text
        self.coefficient_cache = coefficient_cache
        self.r2_key = r2_key
        self.user_id = user_id


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
