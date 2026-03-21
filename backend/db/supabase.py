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


def get_dataset_by_file_id(file_id: str) -> dict[str, Any] | None:
    """Lookup dataset metadata by file_id (the UUID used in the upload).

    Returns a dict with ``r2_key``, ``file_name``, etc. or None.
    Used by the R2 restore flow when the in-memory store misses.
    """
    if _client is None:
        return None

    try:
        result = (
            _client.table("datasets")
            .select("id, file_name, r2_key, created_at")
            .eq("id", file_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.error("Supabase get_dataset_by_file_id failed: %s", exc)
        return None


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


# ---------------------------------------------------------------------------
# Conversation operations (F-09 — Chat History)
# ---------------------------------------------------------------------------

def create_conversation(
    clerk_user_id: str,
    title: str,
    dataset_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    """Create a new conversation and optionally link datasets.

    Returns the full conversation row dict or None on failure.
    """
    if _client is None:
        return None

    try:
        conv_data: dict[str, Any] = {
            "user_id": clerk_user_id,
            "title": title[:80],  # Truncate to 80 chars
        }
        result = _client.table("conversations").insert(conv_data).execute()
        if not result.data:
            return None

        conv = result.data[0]
        conv_id = conv["id"]

        # Link datasets if provided
        if dataset_ids:
            links = [
                {"conversation_id": conv_id, "dataset_id": did}
                for did in dataset_ids
            ]
            _client.table("conversation_files").insert(links).execute()

        return conv
    except Exception as exc:
        logger.error("Supabase create_conversation failed: %s", exc)
        return None


def get_user_conversations(clerk_user_id: str) -> list[dict[str, Any]]:
    """Fetch all conversations for a user, newest first.

    Each row includes: id, title, created_at, updated_at, plus
    linked file names and message count (computed via separate queries
    to keep the main query fast).
    """
    if _client is None:
        return []

    try:
        result = (
            _client.table("conversations")
            .select("id, title, user_id, created_at, updated_at")
            .eq("user_id", clerk_user_id)
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        conversations = result.data or []

        # Enrich with file names and message count
        for conv in conversations:
            cid = conv["id"]

            # Linked file names
            try:
                files_result = (
                    _client.table("conversation_files")
                    .select("dataset_id")
                    .eq("conversation_id", cid)
                    .execute()
                )
                dataset_ids = [f["dataset_id"] for f in (files_result.data or [])]
                # Fetch file names from datasets table
                file_names: list[str] = []
                for did in dataset_ids:
                    ds_result = (
                        _client.table("datasets")
                        .select("file_name")
                        .eq("id", did)
                        .limit(1)
                        .execute()
                    )
                    if ds_result.data:
                        file_names.append(ds_result.data[0]["file_name"])
                conv["file_names"] = file_names
            except Exception:
                conv["file_names"] = []

            # Message count
            try:
                msg_result = (
                    _client.table("messages")
                    .select("id", count="exact")
                    .eq("conversation_id", cid)
                    .execute()
                )
                conv["message_count"] = msg_result.count or 0
            except Exception:
                conv["message_count"] = 0

        return conversations
    except Exception as exc:
        logger.error("Supabase get_user_conversations failed: %s", exc)
        return []


def create_message(
    conversation_id: str,
    role: str,
    content: dict[str, Any],
) -> str | None:
    """Insert a message into a conversation.  Returns the message ``id``."""
    if _client is None:
        return None

    try:
        data: dict[str, Any] = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
        result = _client.table("messages").insert(data).execute()

        # Also update conversation.updated_at
        try:
            _client.table("conversations").update(
                {"updated_at": "now()"}
            ).eq("id", conversation_id).execute()
        except Exception:
            pass  # Non-critical

        if result.data:
            return result.data[0].get("id")
        return None
    except Exception as exc:
        logger.error("Supabase create_message failed: %s", exc)
        return None


def get_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    """Fetch all messages for a conversation, oldest first."""
    if _client is None:
        return []

    try:
        result = (
            _client.table("messages")
            .select("id, role, content, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .limit(200)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("Supabase get_conversation_messages failed: %s", exc)
        return []


def link_conversation_file(conversation_id: str, dataset_id: str) -> bool:
    """Link a dataset to an existing conversation.  Returns True on success."""
    if _client is None:
        return False

    try:
        _client.table("conversation_files").upsert(
            {"conversation_id": conversation_id, "dataset_id": dataset_id},
            on_conflict="conversation_id,dataset_id",
        ).execute()
        return True
    except Exception as exc:
        logger.error("Supabase link_conversation_file failed: %s", exc)
        return False
