"""Correlation Analysis engine — SPSS-equivalent.

Computes Pearson correlation matrix with p-values for all numeric columns.
Also provides scatter plot data for selected variable pairs.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


def compute_correlations(df: pd.DataFrame) -> dict:
    """Return Pearson correlation matrix with p-values.

    Returns
    -------
    dict with keys:
        columns: list[str] — variable names
        matrix: list[list[float]] — correlation coefficients
        p_matrix: list[list[float]] — p-values
        significant_pairs: list[dict] — pairs with p < 0.05
        n: int — sample size used
    """
    numeric_df = df.select_dtypes(include="number").dropna()
    cols = list(numeric_df.columns)
    n = len(numeric_df)

    if len(cols) < 2 or n < 3:
        return {
            "columns": cols,
            "matrix": [],
            "p_matrix": [],
            "significant_pairs": [],
            "n": n,
        }

    # Compute correlation matrix
    corr_matrix = numeric_df.corr().values
    n_vars = len(cols)

    # Compute p-value matrix
    p_matrix = np.ones((n_vars, n_vars))
    for i, j in itertools.combinations(range(n_vars), 2):
        r, p = sp_stats.pearsonr(numeric_df.iloc[:, i], numeric_df.iloc[:, j])
        p_matrix[i, j] = p
        p_matrix[j, i] = p

    # Find significant pairs
    significant_pairs = []
    for i, j in itertools.combinations(range(n_vars), 2):
        r = float(corr_matrix[i, j])
        p = float(p_matrix[i, j])
        if p < 0.05:
            significant_pairs.append({
                "var1": cols[i],
                "var2": cols[j],
                "r": round(r, 4),
                "p_value": round(p, 4),
                "strength": (
                    "strong" if abs(r) >= 0.7
                    else "moderate" if abs(r) >= 0.4
                    else "weak"
                ),
            })

    # Sort by absolute correlation strength
    significant_pairs.sort(key=lambda x: abs(x["r"]), reverse=True)

    return {
        "columns": cols,
        "matrix": [[round(float(v), 4) for v in row] for row in corr_matrix],
        "p_matrix": [[round(float(v), 4) for v in row] for row in p_matrix],
        "significant_pairs": significant_pairs,
        "n": n,
    }


def compute_scatter_data(
    df: pd.DataFrame,
    x_col: str | None = None,
    y_col: str | None = None,
    max_points: int = 200,
) -> dict:
    """Return scatter plot data points for two variables.

    If x_col/y_col not specified, picks the most correlated pair.
    """
    numeric_df = df.select_dtypes(include="number").dropna()
    cols = list(numeric_df.columns)

    if len(cols) < 2:
        return {"x_col": None, "y_col": None, "points": [], "r": None, "p_value": None}

    # Auto-select most correlated pair if not specified
    if x_col is None or y_col is None or x_col not in cols or y_col not in cols:
        best_r = 0.0
        best_pair = (cols[0], cols[1])
        for i, j in itertools.combinations(range(len(cols)), 2):
            r, _ = sp_stats.pearsonr(numeric_df.iloc[:, i], numeric_df.iloc[:, j])
            if abs(r) > abs(best_r):
                best_r = r
                best_pair = (cols[i], cols[j])
        x_col, y_col = best_pair

    # Sample if too many points
    subset = numeric_df[[x_col, y_col]].dropna()
    if len(subset) > max_points:
        subset = subset.sample(n=max_points, random_state=42)

    r, p = sp_stats.pearsonr(subset[x_col], subset[y_col])

    points = [
        {"x": round(float(row[x_col]), 4), "y": round(float(row[y_col]), 4)}
        for _, row in subset.iterrows()
    ]

    return {
        "x_col": x_col,
        "y_col": y_col,
        "points": points,
        "r": round(float(r), 4),
        "p_value": round(float(p), 4),
        "n": len(subset),
    }
