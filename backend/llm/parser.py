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
    '{"intent": "<intent>", "target": "<string|null>", '
    '"features": ["<string>"], "group_by": "<string|null>", '
    '"not_supported_reason": "<string|null>", '
    '"edits": [{"filter_column": "<string>", "filter_value": "<string>", '
    '"column": "<string>", "new_value": "<string>"}]}\n\n'
    "INTENT must be one of:\n"
    "- driver_analysis: user wants to know what drives/affects/influences a target variable\n"
    "- comparison: user wants to compare groups, categories, or subsets of data\n"
    "- summary: user wants a general overview or descriptive statistics\n"
    "- general_question: user asks a general question about the data that doesn't fit above\n"
    "- data_edit: user wants to CHANGE/MODIFY/UPDATE/DELETE/ADD data values in the dataset\n"
    "- not_supported: the question CANNOT be answered with the available columns\n\n"
    "Rules:\n"
    "- target is the outcome variable the user wants to explain. Set null for comparison/summary/general/data_edit.\n"
    "- features are the columns relevant to the question.\n"
    "- group_by: for comparison intent, specify which column to group by. Pick the column that best\n"
    "  matches the user's grouping request (e.g., if user says 'compare continents/regions', use a\n"
    "  region/continent column, NOT the country column). Set null for non-comparison intents.\n"
    "- edits: for data_edit intent ONLY, list each edit. filter_column+filter_value identify the row(s),\n"
    "  column is what to change, new_value is the new value. Set [] for non-data_edit intents.\n"
    "- Use ONLY column names from the dataset. Do not hallucinate column names.\n"
    "- If the user asks to compare groups but no suitable grouping column exists, set intent to\n"
    "  'not_supported' and explain in 'not_supported_reason'.\n"
    "- Do not include markdown, code fences, or explanation.\n\n"
    "Examples:\n"
    '- "What affects Generosity?" → {"intent":"driver_analysis","target":"Generosity 2019","features":["Trust 2019","Freedom 2019"],"group_by":null,"not_supported_reason":null,"edits":[]}\n'
    '- "Compare Asia vs Europe GDP" (has Region col) → {"intent":"comparison","target":null,"features":["GDP 2019"],"group_by":"Region","not_supported_reason":null,"edits":[]}\n'
    '- "Compare Asia vs Europe" (no region column) → {"intent":"not_supported","target":null,"features":[],"group_by":null,"not_supported_reason":"No region/continent column in dataset","edits":[]}\n'
    '- "Summarize the data" → {"intent":"summary","target":null,"features":[],"group_by":null,"not_supported_reason":null,"edits":[]}\n'
    '- "Change the region of Iran from Middle East to Western Asia" → {"intent":"data_edit","target":null,"features":[],"group_by":null,"not_supported_reason":null,"edits":[{"filter_column":"Country","filter_value":"Iran","column":"Region","new_value":"Western Asia"}]}\n'
)

# Default fallback when LLM fails (Layer 1 fallback)
_DEFAULT_PARSED: dict[str, Any] = {
    "intent": "driver_analysis",
    "target": None,
    "features": [],
    "group_by": None,
    "not_supported_reason": None,
    "edits": [],
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
        Parsed intent with keys ``intent``, ``target``, ``features``,
        ``not_supported_reason``.
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
            "group_by": result.get("group_by"),
            "not_supported_reason": result.get("not_supported_reason"),
            "edits": result.get("edits", []) or [],
        }

    except LLMFailureError as exc:
        logger.warning("LLM Call 1 failed, using fallback: %s", exc)
        return dict(_DEFAULT_PARSED)
