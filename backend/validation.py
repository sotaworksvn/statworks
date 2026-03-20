"""Validation Layer — sanitises LLM-parsed intent before reaching engines (F-02)."""

from __future__ import annotations

import pandas as pd

from backend.models import CleanedIntent


def validate_parsed_intent(
    parsed: dict,
    df: pd.DataFrame,
) -> CleanedIntent:
    """Clean and validate an intent dict (possibly from an LLM).

    Steps
    -----
    1. Strip features not present in the DataFrame columns.
    2. Auto-detect target if missing or invalid.
    3. Auto-select features if empty after stripping.

    Parameters
    ----------
    parsed : dict
        Raw parsed intent with keys ``intent``, ``target``, ``features``.
    df : pd.DataFrame
        The uploaded dataset.

    Returns
    -------
    CleanedIntent
        Validated intent safe to pass to the Decision Router.
    """
    columns = df.columns.tolist()
    intent = parsed.get("intent", "driver_analysis")

    # -----------------------------------------------------------------------
    # 1. Target detection
    # -----------------------------------------------------------------------
    target = parsed.get("target")

    if target and target not in columns:
        target = None  # hallucinated column → drop

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
        # Ultimate fallback: first column (should never happen with valid data)
        target = columns[0] if columns else ""

    # -----------------------------------------------------------------------
    # 2. Feature stripping
    # -----------------------------------------------------------------------
    raw_features: list[str] = parsed.get("features", []) or []
    features = [f for f in raw_features if f in columns and f != target]

    # -----------------------------------------------------------------------
    # 3. Auto-select features if empty
    # -----------------------------------------------------------------------
    if not features:
        features = [
            col
            for col in columns
            if col != target and pd.api.types.is_numeric_dtype(df[col])
        ]

    return CleanedIntent(
        intent=intent,
        target=target,
        features=features,
    )
