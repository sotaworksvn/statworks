"""Cloudflare R2 object storage — presigned URLs + upload/download.

Per ADR-0003 and Rule §Storage:
  • Use ``boto3`` with S3-compatible endpoint — never Cloudflare-specific SDKs.
  • All access via time-limited presigned URLs — no public bucket access.
  • R2 key structure: ``users/{clerk_user_id}/datasets/{dataset_id}.csv``
  • Graceful degradation: if env vars missing → ``_client = None``, log warning.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from backend.config import (
    R2_ACCESS_KEY_ID,
    R2_ACCOUNT_ID,
    R2_BUCKET_NAME,
    R2_SECRET_ACCESS_KEY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client initialisation (graceful degradation)
# ---------------------------------------------------------------------------

_client: Any | None = None

if R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME:
    try:
        import boto3

        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        logger.info("R2 client initialised successfully (bucket=%s).", R2_BUCKET_NAME)
    except Exception as exc:
        logger.warning("R2 client init failed — falling back to in-memory only: %s", exc)
        _client = None
else:
    logger.warning(
        "R2 env vars not fully set — R2 storage disabled (in-memory only)."
    )


def is_available() -> bool:
    """Return True if the R2 client is initialised and usable."""
    return _client is not None


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def make_dataset_key(clerk_user_id: str, dataset_id: str, extension: str = ".csv") -> str:
    """Build the canonical R2 key for a dataset file.

    Format: ``users/{clerk_user_id}/datasets/{dataset_id}{extension}``
    """
    return f"users/{clerk_user_id}/datasets/{dataset_id}{extension}"


def make_output_key(clerk_user_id: str, analysis_id: str) -> str:
    """Build the canonical R2 key for an analysis output.

    Format: ``users/{clerk_user_id}/outputs/{analysis_id}.json``
    """
    return f"users/{clerk_user_id}/outputs/{analysis_id}.json"


# ---------------------------------------------------------------------------
# Presigned URLs
# ---------------------------------------------------------------------------

def generate_presigned_upload_url(key: str, expires_in: int = 3600) -> str | None:
    """Generate a time-limited presigned PUT URL for uploading an object.

    Parameters
    ----------
    key : str
        R2 object key (e.g. ``users/abc/datasets/xyz.csv``).
    expires_in : int
        URL validity in seconds (default 1 hour).

    Returns
    -------
    str | None
        The presigned URL, or ``None`` if R2 is not available.
    """
    if _client is None:
        return None

    try:
        url: str = _client.generate_presigned_url(
            "put_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        logger.error("R2 generate_presigned_upload_url failed: %s", exc)
        return None


def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str | None:
    """Generate a time-limited presigned GET URL for downloading an object.

    Parameters
    ----------
    key : str
        R2 object key.
    expires_in : int
        URL validity in seconds (default 1 hour).

    Returns
    -------
    str | None
        The presigned URL, or ``None`` if R2 is not available.
    """
    if _client is None:
        return None

    try:
        url: str = _client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        logger.error("R2 generate_presigned_download_url failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Direct file operations (server-side)
# ---------------------------------------------------------------------------

def upload_file_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    """Upload raw bytes to R2 directly (server-side upload).

    Used for the legacy upload flow where the backend receives the file
    first and then persists it to R2.  Returns ``True`` on success.
    """
    if _client is None:
        return False

    try:
        _client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return True
    except Exception as exc:
        logger.error("R2 upload_file_bytes failed for key=%s: %s", key, exc)
        return False


def get_file_stream(key: str) -> io.BytesIO | None:
    """Download an object from R2 and return it as an in-memory stream.

    Returns
    -------
    io.BytesIO | None
        The file content as a seekable stream, or ``None`` on failure.
    """
    if _client is None:
        return None

    try:
        response = _client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
        body = response["Body"].read()
        return io.BytesIO(body)
    except Exception as exc:
        logger.error("R2 get_file_stream failed for key=%s: %s", key, exc)
        return None
