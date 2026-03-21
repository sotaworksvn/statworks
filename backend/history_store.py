"""In-memory history store with JSON file persistence.

One category: chat.
Upload history is managed purely on the frontend (Zustand store).
Entries are keyed by (user_id, category) and sorted newest-first.
Persists to a JSON file so history survives server restarts.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_PER_CATEGORY = 200
_PERSIST_FILE = Path(__file__).resolve().parent / ".history_data.json"
_DISK_LOCK = threading.Lock()  # Protect concurrent disk I/O (Bug #6 fix)

# Session start time — used to scope PDF exports to "this session"
SESSION_START = datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class HistoryEntry:
    id: str
    user_id: str
    category: str  # "chat" | "data" | "dashboard"
    title: str
    snapshot: dict[str, Any]
    created_at: str  # ISO 8601


# Storage: user_id -> category -> list[HistoryEntry]
_store: dict[str, dict[str, list[HistoryEntry]]] = defaultdict(
    lambda: defaultdict(list)
)


# ---------------------------------------------------------------------------
# Persistence: load / save JSON
# ---------------------------------------------------------------------------

def _load_from_disk() -> None:
    """Load history from JSON file on disk."""
    if not _PERSIST_FILE.exists():
        return
    with _DISK_LOCK:
        try:
            raw = json.loads(_PERSIST_FILE.read_text(encoding="utf-8"))
            for user_id, categories in raw.items():
                for cat, entries in categories.items():
                    for e in entries:
                        _store[user_id][cat].append(HistoryEntry(**e))
        except Exception:
            pass  # Corrupted file — start fresh


def _save_to_disk() -> None:
    """Persist history to JSON file."""
    with _DISK_LOCK:
        try:
            out: dict[str, dict[str, list[dict]]] = {}
            for user_id, categories in _store.items():
                out[user_id] = {}
                for cat, entries in categories.items():
                    out[user_id][cat] = [asdict(e) for e in entries]
            _PERSIST_FILE.write_text(
                json.dumps(out, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass  # Non-critical — next save will retry


# Load history on module import
_load_from_disk()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_entry(
    user_id: str,
    category: str,
    title: str,
    snapshot: dict[str, Any],
) -> HistoryEntry:
    """Create and store a new history entry."""
    entry = HistoryEntry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        category=category,
        title=title,
        snapshot=snapshot,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    entries = _store[user_id][category]
    entries.insert(0, entry)  # newest first
    # LRU eviction
    if len(entries) > MAX_PER_CATEGORY:
        _store[user_id][category] = entries[:MAX_PER_CATEGORY]

    # Persist to disk
    _save_to_disk()
    return entry


def list_entries(
    user_id: str,
    category: str | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
) -> list[dict[str, Any]]:
    """List history entries, optionally filtered by category and date range."""
    results: list[HistoryEntry] = []

    categories = [category] if category else ["chat"]
    for cat in categories:
        results.extend(_store[user_id].get(cat, []))

    # Sort newest first
    results.sort(key=lambda e: e.created_at, reverse=True)

    # Date filtering
    if from_dt:
        try:
            from_ts = datetime.fromisoformat(from_dt.replace("Z", "+00:00"))
            results = [e for e in results if datetime.fromisoformat(e.created_at.replace("Z", "+00:00")) >= from_ts]
        except ValueError:
            pass
    if to_dt:
        try:
            to_ts = datetime.fromisoformat(to_dt.replace("Z", "+00:00"))
            results = [e for e in results if datetime.fromisoformat(e.created_at.replace("Z", "+00:00")) <= to_ts]
        except ValueError:
            pass

    return [
        {
            "id": e.id,
            "category": e.category,
            "title": e.title,
            "created_at": e.created_at,
            "snapshot_preview": _preview(e.snapshot),
        }
        for e in results
    ]


def get_entry(entry_id: str) -> HistoryEntry | None:
    """Get a single entry by ID (scans all users/categories)."""
    for user_cats in _store.values():
        for entries in user_cats.values():
            for e in entries:
                if e.id == entry_id:
                    return e
    return None


def get_all_for_export(
    user_id: str,
    from_dt: str | None = None,
    to_dt: str | None = None,
) -> list[HistoryEntry]:
    """Get all entries (full snapshots) for PDF export."""
    results: list[HistoryEntry] = []
    for cat_entries in _store[user_id].values():
        results.extend(cat_entries)
    results.sort(key=lambda e: e.created_at)

    if from_dt:
        try:
            from_ts = datetime.fromisoformat(from_dt.replace("Z", "+00:00"))
            results = [e for e in results if datetime.fromisoformat(e.created_at.replace("Z", "+00:00")) >= from_ts]
        except ValueError:
            pass
    if to_dt:
        try:
            to_ts = datetime.fromisoformat(to_dt.replace("Z", "+00:00"))
            results = [e for e in results if datetime.fromisoformat(e.created_at.replace("Z", "+00:00")) <= to_ts]
        except ValueError:
            pass

    return results


def _preview(snapshot: dict[str, Any]) -> str:
    """Generate short preview from snapshot."""
    if "messages" in snapshot:
        msgs = snapshot["messages"]
        if msgs:
            last = msgs[-1] if isinstance(msgs, list) else msgs
            content = last.get("content", "") if isinstance(last, dict) else str(last)
            return content[:80] + ("…" if len(content) > 80 else "")
    if "query" in snapshot:
        return str(snapshot["query"])[:80]
    if "edit_description" in snapshot:
        return str(snapshot["edit_description"])[:80]
    return "Snapshot saved"
