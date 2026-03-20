"""OpenAI SDK client management — key rotation and retry logic.

Rule references:
- AI/LLM: openai SDK only (04-rule.md §Python–AI/LLM Layer)
- Security: keys in env vars (04-rule.md §Common–Security)
- AI/LLM: key rotation order fixed (04-rule.md §Python–AI/LLM Layer)
- AI/LLM: retry ×2 only (04-rule.md §Common–Error Handling)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI, RateLimitError

from backend.config import DEV_MODE, OPENAI_API_KEYS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class LLMFailureError(Exception):
    """Raised after all retry attempts on an LLM call have failed."""


# ---------------------------------------------------------------------------
# Client pool — up to 4 AsyncOpenAI instances
# ---------------------------------------------------------------------------

_clients: list[AsyncOpenAI] = []
_active_index: int = 0

for _key in OPENAI_API_KEYS:
    _clients.append(AsyncOpenAI(api_key=_key))

if _clients:
    logger.info("Initialised %d OpenAI client(s) for key rotation.", len(_clients))
else:
    logger.warning(
        "No OpenAI API keys configured. LLM calls will use fallback chain."
    )


def get_active_client() -> AsyncOpenAI | None:
    """Return the current primary client, or ``None`` if no keys are set."""
    if not _clients:
        return None
    return _clients[_active_index]


def _rotate_client() -> None:
    """Rotate to the next client in the pool (round-robin)."""
    global _active_index
    if not _clients:
        return
    _active_index = (_active_index + 1) % len(_clients)
    logger.info("Rotated to OpenAI client index %d.", _active_index)


# ---------------------------------------------------------------------------
# Core LLM call with retry
# ---------------------------------------------------------------------------

async def call_llm_with_retry(
    *,
    model: str,
    messages: list[dict[str, str]],
    response_format: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call the OpenAI Chat Completions API with retry + key rotation.

    Attempts the call up to 3 times (initial + 2 retries) with 500ms backoff.
    On ``RateLimitError``, rotates to the next API key before retrying.
    Raises ``LLMFailureError`` after all attempts fail.

    Parameters
    ----------
    model : str
        The model name, e.g. ``"gpt-5.4-mini"`` or ``"gpt-5.4"``.
    messages : list[dict]
        Chat messages (system + user).
    response_format : dict | None
        Optional response format, e.g. ``{"type": "json_object"}``.

    Returns
    -------
    dict
        Parsed JSON from the model's response content.
    """
    client = get_active_client()
    if client is None:
        raise LLMFailureError("No OpenAI API keys configured.")

    last_error: Exception | None = None

    for attempt in range(3):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            logger.debug("LLM raw content (model=%s): %r", model, content[:500])

            # Strip markdown code fences — some models wrap JSON in ```json...```
            stripped = content.strip()
            if stripped.startswith("```"):
                lines = stripped.split("\n")
                # Remove first line (```json or ```) and last line (```)
                stripped = "\n".join(lines[1:-1]) if len(lines) > 2 else stripped
            return json.loads(stripped)

        except RateLimitError as exc:
            logger.warning(
                "RateLimitError on attempt %d: %s — rotating key.", attempt + 1, exc
            )
            _rotate_client()
            client = get_active_client()
            if client is None:
                raise LLMFailureError("All API keys exhausted.") from exc
            last_error = exc

        except json.JSONDecodeError as exc:
            logger.warning(
                "JSON parse error on attempt %d (model=%s): %s", attempt + 1, model, exc
            )
            last_error = exc

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LLM call error on attempt %d (model=%s): %s", attempt + 1, model, exc
            )
            last_error = exc

        # Backoff before next retry (skip sleep on the last attempt)
        if attempt < 2:
            await asyncio.sleep(0.5)

    raise LLMFailureError(
        f"LLM call failed after 3 attempts. Last error: {last_error}"
    ) from last_error
