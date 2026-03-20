"""LLM Call 1 — Intent parsing via gpt-5.4-mini (Phase 2 · task 2.2).

Rule references:
- AI/LLM: gpt-5.4-mini for Call 1 only (04-rule.md §Python–AI/LLM Layer)
- AI/LLM: system prompt must enforce schema (04-rule.md §Python–AI/LLM Layer)
- AI/LLM: token budget ≤1000 (04-rule.md §Common–Performance)
- Error Handling: Layer 1 fallback (04-rule.md §Common–Error Handling)
"""

from __future__ import annotations

import logging
from typing import Any

from backend.llm.client import LLMFailureError, call_llm_with_retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — strict JSON schema enforcement
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_PARSE: str = (
    "You are a data analysis assistant.\n"
    'Return ONLY valid JSON matching this schema:\n'
    '{"intent": "driver_analysis|summary|comparison", '
    '"target": "string", "features": ["string"]}\n'
    "Rules:\n"
    "- intent must be one of: driver_analysis, summary, comparison.\n"
    "- target is the outcome variable the user wants to explain.\n"
    "- features are the columns that might drive the target.\n"
    "- Use ONLY column names from the dataset. Do not hallucinate column names.\n"
    "- If unsure about features, return an empty list.\n"
    "- If unsure about target, return null.\n"
    "- Do not include markdown, code fences, or explanation."
)

# Default fallback when LLM fails (Layer 1 fallback)
_DEFAULT_PARSED: dict[str, Any] = {
    "intent": "driver_analysis",
    "target": None,
    "features": [],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_user_intent(
    query: str,
    column_names: list[str],
    context_text: str | None = None,
) -> dict[str, Any]:
    """Parse user query into structured intent using gpt-5.4-mini.

    Parameters
    ----------
    query : str
        The user's natural-language question.
    column_names : list[str]
        Column names from the uploaded dataset.
    context_text : str | None
        Optional context text extracted from .docx/.pptx uploads.

    Returns
    -------
    dict
        Parsed intent with keys ``intent``, ``target``, ``features``.
        On LLM failure, returns a safe default dict (Layer 1 fallback).
    """
    # Build user prompt (keep under ~500 tokens for the user message)
    user_parts: list[str] = [
        f"Dataset columns: {', '.join(column_names)}",
    ]

    if context_text:
        # Truncate context to first 500 chars to respect token budget
        snippet = context_text[:500]
        user_parts.append(f"Additional context: {snippet}")

    user_parts.append(f"User question: {query}")

    user_prompt = "\n".join(user_parts)

    try:
        result = await call_llm_with_retry(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_PARSE},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        # Ensure required keys exist in response
        if not isinstance(result, dict):
            logger.warning("LLM Call 1 returned non-dict: %s", type(result))
            return dict(_DEFAULT_PARSED)

        # Normalise: ensure keys exist with safe defaults
        return {
            "intent": result.get("intent", "driver_analysis"),
            "target": result.get("target"),
            "features": result.get("features", []) or [],
        }

    except LLMFailureError as exc:
        logger.warning("LLM Call 1 failed, using fallback: %s", exc)
        return dict(_DEFAULT_PARSED)
