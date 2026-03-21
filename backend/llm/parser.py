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
from backend.llm.prompts import SYSTEM_PROMPT_PARSE

logger = logging.getLogger(__name__)

# Default fallback when LLM fails (Layer 1 fallback)
_DEFAULT_PARSED: dict[str, Any] = {
    "intent": "driver_analysis",
    "target": None,
    "features": [],
    "group_by": None,
    "not_supported_reason": None,
    "edits": [],
}

_SUPPORTED_INTENTS: set[str] = {
    "driver_analysis",
    "comparison",
    "summary",
    "general_question",
    "data_edit",
    "not_supported",
    "scholarship_prediction",
    "scholarship",
    "predict_scholarship",
    "school_matching",
    "descriptive",
    "descriptive_statistics",
    "frequency",
    "frequencies",
    "correlation",
    "correlations",
    "scatter",
    "scatter_plot",
    "reliability",
    "validity",
    "model_fit",
    "effects",
    "effects_table",
    "path_coefficients",
    "bootstrap",
    "pls_sem",
    "bar_chart",
}


def _looks_off_topic(query: str) -> bool:
    q = query.lower()
    off_topic_cues = (
        "capital of",
        "weather",
        "recipe",
        "poem",
        "joke",
        "translate",
        "code review",
        "python bug",
        "movie",
        "football",
        "stock price",
    )
    return any(cue in q for cue in off_topic_cues)


def _looks_data_related(query: str) -> bool:
    q = query.lower()
    data_cues = (
        "data",
        "dataset",
        "column",
        "row",
        "table",
        "analy",
        "insight",
        "summary",
        "trend",
        "compare",
        "impact",
        "affect",
        "driver",
        "score",
        "rate",
        "group",
        "mean",
        "average",
        "correlation",
        "regression",
        "thong ke",
        "du lieu",
        "dữ liệu",
        "phan tich",
        "phân tích",
        "tong quan",
        "tổng quan",
        "so sanh",
        "so sánh",
        "anh huong",
        "ảnh hưởng",
        "yeu to",
        "yếu tố",
    )
    return any(cue in q for cue in data_cues)


def _intent_hint_from_query(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ("compare", "comparison", "so sanh", "so sánh", "khac nhau", "khác nhau")):
        return "comparison"
    if any(k in q for k in ("summary", "summarize", "tong quan", "tổng quan", "overview")):
        return "summary"
    if any(k in q for k in ("change", "edit", "update", "sua", "chinh sua", "sửa", "chỉnh sửa")):
        return "data_edit"
    if any(k in q for k in ("impact", "affect", "influence", "driver", "anh huong", "ảnh hưởng", "tac dong", "tác động", "yeu to", "yếu tố")):
        return "driver_analysis"
    return "general_question"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_user_intent(
    query: str,
    column_names: list[str],
    context_text: str | None = None,
    sample_rows: list[dict] | None = None,
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
    sample_rows : list[dict] | None
        Optional first few rows of data to give LLM context about current values/formats.

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

    if sample_rows:
        # Include first few rows so LLM can see current data formats
        import json
        sample_str = json.dumps(sample_rows[:3], ensure_ascii=False, default=str)
        # Cap at 800 chars to stay within token budget
        if len(sample_str) > 800:
            sample_str = sample_str[:800] + "..."
        user_parts.append(f"Sample data (first rows): {sample_str}")

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
        parsed = {
            "intent": result.get("intent", "driver_analysis"),
            "target": result.get("target"),
            "features": result.get("features", []) or [],
            "group_by": result.get("group_by"),
            "not_supported_reason": result.get("not_supported_reason"),
            "edits": result.get("edits", []) or [],
        }

        intent = str(parsed.get("intent") or "").lower().replace(" ", "_")
        if intent not in _SUPPORTED_INTENTS:
            parsed["intent"] = "general_question"
            parsed["not_supported_reason"] = None
            return parsed

        # Make parser less rigid: keep not_supported only for clearly off-topic requests.
        if intent == "not_supported" and not _looks_off_topic(query):
            parsed["intent"] = _intent_hint_from_query(query) if _looks_data_related(query) else "general_question"
            parsed["not_supported_reason"] = None

        return parsed

    except LLMFailureError as exc:
        logger.warning("LLM Call 1 failed, using fallback: %s", exc)
        return dict(_DEFAULT_PARSED)
