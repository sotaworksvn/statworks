"""Application configuration — reads environment variables at import time."""

from __future__ import annotations

import os


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
# CORS origin — "*" in dev, exact Vercel URL in production
# ---------------------------------------------------------------------------
CORS_ORIGIN: str = os.environ.get("CORS_ORIGIN", "*")
