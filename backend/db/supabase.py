"""Supabase metadata persistence — users, datasets, analyses.

Per ADR-0002 and Rule §Metadata:
  • Use ``supabase-py`` client — never raw HTTP.
  • ``SUPABASE_SERVICE_KEY`` is backend-only.
  • Graceful degradation: if env vars missing → ``_client = None``, log warning.
  • All writes should be called via ``asyncio.create_task()`` (non-blocking).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from backend.config import SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client initialisation (graceful degradation)
# ---------------------------------------------------------------------------

_client: Any | None = None

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        from supabase import create_client

        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client initialised successfully.")
    except Exception as exc:
        logger.warning("Supabase client init failed — falling back to in-memory only: %s", exc)
        _client = None
else:
    logger.warning(
        "SUPABASE_URL and/or SUPABASE_SERVICE_KEY not set — "
        "Supabase persistence disabled (in-memory only)."
    )


def is_available() -> bool:
    """Return True if the Supabase client is initialised and usable."""
    return _client is not None


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def upsert_user(clerk_user_id: str, email: str | None = None, name: str | None = None) -> str | None:
    """Insert or update a user row.  Returns the DB ``id`` or None on failure.

    Uses ``ON CONFLICT (clerk_user_id) DO UPDATE`` semantics via Supabase upsert.
    """
    if _client is None:
        return None

    try:
        data: dict[str, Any] = {"clerk_user_id": clerk_user_id}
        if email:
            data["email"] = email
        if name:
            data["name"] = name

        result = (
            _client.table("users")
            .upsert(data, on_conflict="clerk_user_id")
            .execute()
        )
        if result.data:
            return result.data[0].get("id")
        return None
    except Exception as exc:
        logger.error("Supabase upsert_user failed: %s", exc)
        return None


def get_user_by_clerk_id(clerk_user_id: str) -> dict[str, Any] | None:
    """Fetch a user row by ``clerk_user_id``.  Returns the row dict or None."""
    if _client is None:
        return None

    try:
        result = (
            _client.table("users")
            .select("*")
            .eq("clerk_user_id", clerk_user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.error("Supabase get_user_by_clerk_id failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Dataset operations
# ---------------------------------------------------------------------------

def create_dataset(
    user_id: str,
    file_name: str,
    r2_key: str,
    dataset_id: str | None = None,
) -> str | None:
    """Insert a dataset metadata row.  Returns the DB ``id`` or None."""
    if _client is None:
        return None

    try:
        data: dict[str, Any] = {
            "user_id": user_id,
            "file_name": file_name,
            "r2_key": r2_key,
        }
        if dataset_id:
            data["id"] = dataset_id

        result = _client.table("datasets").insert(data).execute()
        if result.data:
            return result.data[0].get("id")
        return None
    except Exception as exc:
        logger.error("Supabase create_dataset failed: %s", exc)
        return None


def get_user_datasets(clerk_user_id: str) -> list[dict[str, Any]]:
    """Fetch all datasets belonging to a user (via clerk_user_id join).

    Returns a list of dataset rows (empty list on failure).
    """
    if _client is None:
        return []

    try:
        # First get the user's DB id
        user = get_user_by_clerk_id(clerk_user_id)
        if not user:
            return []

        result = (
            _client.table("datasets")
            .select("id, file_name, r2_key, created_at")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("Supabase get_user_datasets failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Analysis operations
# ---------------------------------------------------------------------------

def create_analysis(dataset_id: str, result: dict[str, Any]) -> str | None:
    """Insert an analysis result row.  Returns the DB ``id`` or None."""
    if _client is None:
        return None

    try:
        data: dict[str, Any] = {
            "dataset_id": dataset_id,
            "result": result,
        }
        resp = _client.table("analyses").insert(data).execute()
        if resp.data:
            return resp.data[0].get("id")
        return None
    except Exception as exc:
        logger.error("Supabase create_analysis failed: %s", exc)
        return None
