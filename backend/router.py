"""Decision Router — selects OLS or PLS engine via scoring function (F-02)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.models import DecisionTrace


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _latent_variable_presence(df: pd.DataFrame, features: list[str]) -> float:
    """L — 1 if at least one feature has multiple highly-correlated sub-columns (r > 0.6)."""
    numeric_feats = [f for f in features if pd.api.types.is_numeric_dtype(df[f])]
    if len(numeric_feats) < 2:
        return 0.0

    corr = df[numeric_feats].corr().abs()
    for i, f1 in enumerate(numeric_feats):
        for f2 in numeric_feats[i + 1 :]:
            if corr.loc[f1, f2] > 0.6:
                return 1.0
    return 0.0


def _multiplicity(features: list[str]) -> float:
    """M — number of features / 10, capped at 1.0."""
    return min(len(features) / 10.0, 1.0)


def _complexity(features: list[str], L: float) -> float:
    """C — 1 if len(features) > 3 and L > 0, else 0."""
    return 1.0 if len(features) > 3 and L > 0 else 0.0


def _observability(df: pd.DataFrame, features: list[str]) -> float:
    """O — fraction of features that are numeric."""
    if not features:
        return 1.0
    numeric_count = sum(1 for f in features if pd.api.types.is_numeric_dtype(df[f]))
    return numeric_count / len(features)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_model(
    df: pd.DataFrame,
    features: list[str],
    target: str,
) -> DecisionTrace:
    """Score PLS vs Regression and return the engine selection decision.

    Returns
    -------
    DecisionTrace
        Contains ``score_pls``, ``score_reg``, ``engine_selected``, and a
        human-readable ``reason``.
    """
    L = _latent_variable_presence(df, features)
    M = _multiplicity(features)
    C = _complexity(features, L)
    O = _observability(df, features)

    score_pls = round(0.4 * L + 0.3 * M + 0.3 * C, 4)
    score_reg = round(0.6 * O + 0.4 * (1 - C), 4)

    if score_pls > score_reg:
        engine = "pls"
        reason = (
            f"Dataset shows latent variable structure (L={L:.1f}) with "
            f"{len(features)} features (M={M:.2f}) and structural complexity "
            f"(C={C:.1f}). PLS score ({score_pls:.2f}) exceeds regression "
            f"score ({score_reg:.2f})."
        )
    else:
        engine = "regression"
        parts: list[str] = []
        if O >= 0.8:
            parts.append("fully observable numeric columns")
        else:
            parts.append(f"observability O={O:.2f}")
        if L == 0:
            parts.append("no latent variable indicators detected")
        reason = (
            f"Dataset has {', '.join(parts)}. "
            f"Regression score ({score_reg:.2f}) meets or exceeds PLS score "
            f"({score_pls:.2f})."
        )

    return DecisionTrace(
        score_pls=score_pls,
        score_reg=score_reg,
        engine_selected=engine,
        reason=reason,
    )
