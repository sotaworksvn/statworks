"""Model Fit Assessment engine — SmartPLS-equivalent.

Computes: SRMR, NFI approximation, R² summary, model quality indicators.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_model_fit(df: pd.DataFrame, target: str | None = None) -> dict:
    """Compute model fit indicators.

    Parameters
    ----------
    target : str | None
        If provided, compute R² for this specific variable.
        Otherwise, auto-select the last numeric column.

    Returns
    -------
    dict with keys:
        srmr: float — Standardised Root Mean Residual
        nfi: float — Normed Fit Index approximation
        r_squared: float — R² of the model
        adj_r_squared: float — Adjusted R²
        indicators: list[dict] — fit quality table
    """
    numeric_df = df.select_dtypes(include="number").dropna()
    cols = list(numeric_df.columns)
    n = len(numeric_df)

    if len(cols) < 2 or n < 5:
        return {
            "srmr": None,
            "nfi": None,
            "r_squared": None,
            "adj_r_squared": None,
            "indicators": [],
            "quality": "Insufficient data",
        }

    # Auto-select target
    if target is None or target not in cols:
        target = cols[-1]

    features = [c for c in cols if c != target]
    if not features:
        return {
            "srmr": None, "nfi": None, "r_squared": None,
            "adj_r_squared": None, "indicators": [], "quality": "No features",
        }

    # Compute SRMR from correlation residuals
    observed_corr = numeric_df.corr().values
    k = len(cols)

    # Implied correlation (from single-factor model)
    # Simple approximation: use first PC loadings to reconstruct implied corr
    X = numeric_df.values
    X_std = (X - X.mean(axis=0)) / X.std(axis=0)
    cov = np.cov(X_std.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    idx = np.argsort(eigvals)[::-1]
    first_pc = eigvecs[:, idx[0]]
    loadings = X_std.T @ (X_std @ first_pc) / (X_std @ first_pc).var() / n

    # Normalize loadings
    loading_norms = np.sqrt(np.sum(loadings ** 2))
    if loading_norms > 0:
        loadings = loadings / loading_norms * np.sqrt(eigvals[idx[0]] / k)

    implied_corr = np.outer(loadings, loadings)
    np.fill_diagonal(implied_corr, 1.0)

    # SRMR
    residuals = observed_corr - implied_corr
    np.fill_diagonal(residuals, 0.0)
    n_elements = k * (k - 1) / 2
    srmr = round(float(np.sqrt(np.sum(residuals ** 2) / max(n_elements, 1))), 4)

    # Simple R² via multivariate regression
    from sklearn.linear_model import LinearRegression
    try:
        X_feat = numeric_df[features].values
        y = numeric_df[target].values
        model = LinearRegression()
        model.fit(X_feat, y)
        y_pred = model.predict(X_feat)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = round(float(1 - ss_res / ss_tot), 4) if ss_tot > 0 else 0.0
        p = len(features)
        adj_r2 = round(float(1 - (1 - r2) * (n - 1) / (n - p - 1)), 4) if n > p + 1 else r2
    except Exception:
        r2 = None
        adj_r2 = None

    # NFI approximation: 1 - (chi²_model / chi²_null)
    # Simple approximation using SRMR
    nfi = round(max(0.0, 1 - srmr * 2), 4)

    # Build indicators table
    indicators = [
        {"metric": "SRMR", "value": srmr, "threshold": "< 0.08", "acceptable": srmr < 0.08},
        {"metric": "NFI", "value": nfi, "threshold": "> 0.90", "acceptable": nfi > 0.90},
    ]
    if r2 is not None:
        indicators.append({"metric": "R²", "value": r2, "threshold": "> 0.25", "acceptable": r2 > 0.25})
        indicators.append({"metric": "Adj. R²", "value": adj_r2, "threshold": "> 0.20", "acceptable": adj_r2 > 0.20 if adj_r2 else False})

    # Overall quality
    acceptable_count = sum(1 for i in indicators if i["acceptable"])
    if acceptable_count == len(indicators):
        quality = "Good"
    elif acceptable_count >= len(indicators) // 2:
        quality = "Moderate"
    else:
        quality = "Poor"

    return {
        "srmr": srmr,
        "nfi": nfi,
        "r_squared": r2,
        "adj_r_squared": adj_r2,
        "target": target,
        "indicators": indicators,
        "quality": quality,
    }
