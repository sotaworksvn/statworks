"""Validation Layer — sanitises LLM-parsed intent before reaching engines (F-02)."""

from __future__ import annotations

import pandas as pd

from backend.models import CleanedIntent


# Intents that do NOT need a specific regression target
_NON_TARGET_INTENTS = {"comparison", "summary", "general_question", "not_supported", "data_edit"}


def validate_parsed_intent(
    parsed: dict,
    df: pd.DataFrame,
) -> CleanedIntent:
    """Clean and validate an intent dict (possibly from an LLM).

    Steps
    -----
    1. Determine intent type.
    2. For driver_analysis: auto-detect target if missing.
    3. For non-regression intents: allow null target.
    4. Strip features not present in the DataFrame columns.
    5. Auto-select features if empty after stripping.

    Parameters
    ----------
    parsed : dict
        Raw parsed intent with keys ``intent``, ``target``, ``features``,
        and optionally ``not_supported_reason``.
    df : pd.DataFrame
        The uploaded dataset.

    Returns
    -------
    CleanedIntent
        Validated intent safe to pass to the Decision Router or direct dispatch.
    """
    columns = df.columns.tolist()
    intent = parsed.get("intent", "driver_analysis")
    not_supported_reason = parsed.get("not_supported_reason")

    # -------------------------------------------------------------------
    # 1. Target detection — only for driver_analysis
    # -------------------------------------------------------------------
    target = parsed.get("target")

    if target and target not in columns:
        target = None  # hallucinated column → drop

    if intent not in _NON_TARGET_INTENTS:
        # Need a target for regression-based intents
        if not target:
            # Heuristic: last column
            target = columns[-1] if columns else None

        if not target:
            # Heuristic: column name containing "index", "score", or "rate"
            for col in columns:
                lower = col.lower()
                if any(kw in lower for kw in ("index", "score", "rate")):
                    target = col
                    break

        if not target:
            # Ultimate fallback: first column
            target = columns[0] if columns else ""
    else:
        # Non-target intents: target stays null/as-is
        if not target:
            target = ""

    # -------------------------------------------------------------------
    # 2. Feature stripping
    # -------------------------------------------------------------------
    raw_features: list[str] = parsed.get("features", []) or []
    features = [f for f in raw_features if f in columns and f != target]

    # -------------------------------------------------------------------
    # 3. Auto-select features if empty (only for driver_analysis)
    # -------------------------------------------------------------------
    if not features and intent not in _NON_TARGET_INTENTS:
        features = [
            col
            for col in columns
            if col != target and pd.api.types.is_numeric_dtype(df[col])
        ]

    # -------------------------------------------------------------------
    # 4. group_by validation (for comparison)
    # -------------------------------------------------------------------
    group_by = parsed.get("group_by")
    if group_by and group_by not in columns:
        group_by = None  # hallucinated column → drop

    # -------------------------------------------------------------------
    # 5. Validate edits (for data_edit intent)
    # -------------------------------------------------------------------
    edits = parsed.get("edits", []) or []
    if intent == "data_edit":
        valid_edits = []
        for e in edits:
            if isinstance(e, dict) and e.get("column") in columns:
                valid_edits.append(e)
        edits = valid_edits

    return CleanedIntent(
        intent=intent,
        target=target,
        features=features,
        group_by=group_by,
        not_supported_reason=not_supported_reason,
        edits=edits,
    )
