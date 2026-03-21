"""Frequency Analysis engine — SPSS-equivalent.

Computes frequency distributions for all columns:
- Categorical: value_counts with count, percent, cumulative percent
- Numeric: binned into 10 intervals with same stats
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_frequencies(df: pd.DataFrame, max_categories: int = 20) -> dict:
    """Return frequency distributions for all columns.

    Parameters
    ----------
    max_categories : int
        Columns with more unique values than this are binned (numeric)
        or truncated (categorical).

    Returns
    -------
    dict with keys:
        variables: list[dict] — one entry per column
        n_variables: int
    """
    variables: list[dict] = []

    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue

        is_numeric = pd.api.types.is_numeric_dtype(series)
        n_unique = series.nunique()

        if is_numeric and n_unique > max_categories:
            # Bin numeric columns into 10 equal-width intervals
            bins = pd.cut(series, bins=10)
            counts = bins.value_counts(sort=False)
            total = counts.sum()
            cum = 0.0
            freq_rows = []
            for interval, count in counts.items():
                pct = round(float(count / total * 100), 2) if total > 0 else 0.0
                cum += pct
                freq_rows.append({
                    "value": str(interval),
                    "count": int(count),
                    "percent": pct,
                    "cumulative_percent": round(cum, 2),
                })
            var_type = "numeric_binned"
        else:
            # Categorical or low-cardinality numeric
            counts = series.value_counts()
            if len(counts) > max_categories:
                counts = counts.head(max_categories)
            total = counts.sum()
            cum = 0.0
            freq_rows = []
            for value, count in counts.items():
                pct = round(float(count / total * 100), 2) if total > 0 else 0.0
                cum += pct
                freq_rows.append({
                    "value": str(value),
                    "count": int(count),
                    "percent": pct,
                    "cumulative_percent": round(cum, 2),
                })
            var_type = "categorical" if not is_numeric else "numeric"

        variables.append({
            "name": str(col),
            "type": var_type,
            "n_valid": int(len(series)),
            "n_missing": int(df[col].isna().sum()),
            "n_unique": int(n_unique),
            "frequencies": freq_rows,
        })

    return {
        "variables": variables,
        "n_variables": len(variables),
    }
