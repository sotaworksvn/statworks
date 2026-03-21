"""Reliability Analysis engine — SmartPLS-equivalent.

Computes Cronbach's Alpha and item-total correlations.
Alpha formula: α = (k / (k-1)) * (1 - Σσ²ᵢ / σ²_total)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_reliability(df: pd.DataFrame) -> dict:
    """Compute Cronbach's Alpha and item-total correlations.

    Returns
    -------
    dict with keys:
        cronbachs_alpha: float
        items: list[dict] — per-item stats (mean, std, item-total corr, alpha if deleted)
        n_items: int
        n_valid: int — observations used (listwise deletion)
        interpretation: str — reliability level label
    """
    numeric_df = df.select_dtypes(include="number").dropna()
    cols = list(numeric_df.columns)
    k = len(cols)
    n = len(numeric_df)

    if k < 2 or n < 3:
        return {
            "cronbachs_alpha": None,
            "items": [],
            "n_items": k,
            "n_valid": n,
            "interpretation": "Insufficient items for reliability analysis",
        }

    # Compute Cronbach's Alpha
    item_vars = numeric_df.var(ddof=1)
    total_var = numeric_df.sum(axis=1).var(ddof=1)
    sum_item_vars = item_vars.sum()

    alpha = (k / (k - 1)) * (1 - sum_item_vars / total_var) if total_var > 0 else 0.0
    alpha = round(float(alpha), 4)

    # Per-item analysis
    items: list[dict] = []
    total_scores = numeric_df.sum(axis=1)

    for col in cols:
        series = numeric_df[col]

        # Item-total correlation (corrected — exclude this item from total)
        rest_total = total_scores - series
        item_total_corr = float(series.corr(rest_total))

        # Alpha if this item is deleted
        remaining = [c for c in cols if c != col]
        if len(remaining) >= 2:
            rem_df = numeric_df[remaining]
            rem_k = len(remaining)
            rem_item_vars = rem_df.var(ddof=1).sum()
            rem_total_var = rem_df.sum(axis=1).var(ddof=1)
            alpha_if_deleted = (
                (rem_k / (rem_k - 1)) * (1 - rem_item_vars / rem_total_var)
                if rem_total_var > 0 else 0.0
            )
        else:
            alpha_if_deleted = None

        items.append({
            "name": str(col),
            "mean": round(float(series.mean()), 4),
            "std": round(float(series.std()), 4),
            "item_total_corr": round(item_total_corr, 4),
            "alpha_if_deleted": round(float(alpha_if_deleted), 4) if alpha_if_deleted is not None else None,
        })

    # Interpretation
    if alpha >= 0.9:
        interpretation = "Excellent"
    elif alpha >= 0.8:
        interpretation = "Good"
    elif alpha >= 0.7:
        interpretation = "Acceptable"
    elif alpha >= 0.6:
        interpretation = "Questionable"
    elif alpha >= 0.5:
        interpretation = "Poor"
    else:
        interpretation = "Unacceptable"

    return {
        "cronbachs_alpha": alpha,
        "items": items,
        "n_items": k,
        "n_valid": n,
        "interpretation": interpretation,
    }
