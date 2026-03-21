"""Descriptive Statistics engine — SPSS-equivalent.

Computes: count, mean, std, min, 25%, 50%, 75%, max, skewness, kurtosis
for all numeric columns in the DataFrame.
"""

from __future__ import annotations

import pandas as pd
from scipy import stats as sp_stats


def compute_descriptive(df: pd.DataFrame) -> dict:
    """Return descriptive statistics for all numeric columns.

    Returns
    -------
    dict with keys:
        variables: list[dict] — one entry per numeric column with all stats
        n_numeric: int — number of numeric columns analysed
        n_rows: int — total observations
    """
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.empty:
        return {"variables": [], "n_numeric": 0, "n_rows": len(df)}

    desc = numeric_df.describe().T  # index = column names
    variables: list[dict] = []

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        row = desc.loc[col] if col in desc.index else {}

        variables.append({
            "name": str(col),
            "count": int(row.get("count", len(series))),
            "mean": round(float(row.get("mean", series.mean())), 4),
            "std": round(float(row.get("std", series.std())), 4),
            "min": round(float(row.get("min", series.min())), 4),
            "q25": round(float(row.get("25%", series.quantile(0.25))), 4),
            "median": round(float(row.get("50%", series.median())), 4),
            "q75": round(float(row.get("75%", series.quantile(0.75))), 4),
            "max": round(float(row.get("max", series.max())), 4),
            "skewness": round(float(sp_stats.skew(series, nan_policy="omit")), 4),
            "kurtosis": round(float(sp_stats.kurtosis(series, nan_policy="omit")), 4),
            "missing": int(numeric_df[col].isna().sum()),
        })

    return {
        "variables": variables,
        "n_numeric": len(variables),
        "n_rows": len(df),
    }
