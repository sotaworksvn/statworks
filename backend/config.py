"""Application configuration — reads environment variables at import time."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Auto-load .env from the backend directory (works from any working directory)
_backend_dir = Path(__file__).resolve().parent
_env_file = _backend_dir / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


def _get_env(key: str, required: bool = False) -> str | None:
    """Read an environment variable. Fail loudly if *required* and missing."""
    value = os.environ.get(key)
    if required and not value:
        raise ValueError(
            f"Environment variable '{key}' is required but not set. "
            "Set it in Render's dashboard or in a local .env file."
        )
    return value


# ---------------------------------------------------------------------------
# Development mode flag — when True, missing API keys are tolerated
# ---------------------------------------------------------------------------
DEV_MODE: bool = os.environ.get("DEV_MODE", "true").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# OpenAI API keys (4 accounts for rotation)
# ---------------------------------------------------------------------------
OPENAI_API_KEYS: list[str] = []
for i in range(1, 5):
    key = _get_env(f"OPENAI_API_KEY_{i}", required=False)
    if key:
        OPENAI_API_KEYS.append(key)

if not DEV_MODE and len(OPENAI_API_KEYS) == 0:
    raise ValueError(
        "At least one OPENAI_API_KEY_* must be set in production mode. "
        "Set DEV_MODE=true for local development without API keys."
    )

# ---------------------------------------------------------------------------
# CORS origin — "*" in dev, comma-separated URLs in production
# Example: CORS_ORIGIN=https://stat.sotaworks.xyz,https://app.vercel.app
# ---------------------------------------------------------------------------
_cors_raw: str = os.environ.get("CORS_ORIGIN", "*")
CORS_ORIGINS: list[str] = [
    origin.strip().rstrip("/") for origin in _cors_raw.split(",") if origin.strip()
]

# ---------------------------------------------------------------------------
# Supabase (optional — graceful degradation if missing)
# ---------------------------------------------------------------------------
SUPABASE_URL: str | None = _get_env("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str | None = _get_env("SUPABASE_SERVICE_KEY")

# ---------------------------------------------------------------------------
# Cloudflare R2 (optional — graceful degradation if missing)
# ---------------------------------------------------------------------------
R2_ACCOUNT_ID: str | None = _get_env("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID: str | None = _get_env("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY: str | None = _get_env("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME: str | None = _get_env("R2_BUCKET_NAME")

# ---------------------------------------------------------------------------
# Clerk (optional — used only if JWT verification is needed server-side)
# ---------------------------------------------------------------------------
CLERK_SECRET_KEY: str | None = _get_env("CLERK_SECRET_KEY")
