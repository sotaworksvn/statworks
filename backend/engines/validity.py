"""Validity Analysis engine — SmartPLS-equivalent.

Computes:
- Average Variance Extracted (AVE) from factor loadings
- Fornell-Larcker discriminant validity criterion
- Factor loadings via PCA
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


def compute_validity(df: pd.DataFrame) -> dict:
    """Compute construct validity metrics.

    Uses PCA-based factor loadings as a proxy for PLS outer loadings.

    Returns
    -------
    dict with keys:
        loadings: list[dict] — factor loading per variable
        ave: float — Average Variance Extracted
        composite_reliability: float — CR
        fornell_larcker: dict — discriminant validity check
        convergent_valid: bool — AVE >= 0.5
        n_valid: int
    """
    numeric_df = df.select_dtypes(include="number").dropna()
    cols = list(numeric_df.columns)
    n = len(numeric_df)
    k = len(cols)

    if k < 2 or n < 3:
        return {
            "loadings": [],
            "ave": None,
            "composite_reliability": None,
            "fornell_larcker": {},
            "convergent_valid": False,
            "n_valid": n,
        }

    # Standardize data
    from sklearn.preprocessing import StandardScaler
    try:
        scaler = StandardScaler()
        X_std = scaler.fit_transform(numeric_df)
    except Exception:
        X_std = ((numeric_df - numeric_df.mean()) / numeric_df.std()).values

    # PCA for first component (latent variable proxy)
    cov_matrix = np.cov(X_std.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

    # Take the principal component (largest eigenvalue)
    idx = np.argsort(eigenvalues)[::-1]
    first_pc = eigenvectors[:, idx[0]]

    # Factor loadings = correlations between items and first PC
    pc_scores = X_std @ first_pc
    loading_values = []
    for i, col in enumerate(cols):
        r, _ = sp_stats.pearsonr(X_std[:, i], pc_scores)
        loading_values.append(float(r))

    # Ensure loadings are positive (flip if needed)
    if sum(1 for l in loading_values if l < 0) > len(loading_values) // 2:
        loading_values = [-l for l in loading_values]

    # AVE = mean of squared loadings
    squared = [l ** 2 for l in loading_values]
    ave = round(float(np.mean(squared)), 4)

    # Composite Reliability: CR = (Σλ)² / ((Σλ)² + Σ(1-λ²))
    sum_loadings = sum(abs(l) for l in loading_values)
    sum_error = sum(1 - l ** 2 for l in loading_values)
    cr = round(float(sum_loadings ** 2 / (sum_loadings ** 2 + sum_error)), 4) if (sum_loadings ** 2 + sum_error) > 0 else 0.0

    # Build loadings list
    loadings = []
    for col, loading, sq in zip(cols, loading_values, squared):
        loadings.append({
            "name": str(col),
            "loading": round(loading, 4),
            "loading_squared": round(sq, 4),
            "communality": round(sq, 4),
        })

    # Fornell-Larcker: √AVE should be greater than all inter-construct correlations
    sqrt_ave = float(np.sqrt(ave))
    corr_matrix = numeric_df.corr()
    max_corr = 0.0
    for i, j in [(a, b) for a in range(k) for b in range(a + 1, k)]:
        r = abs(float(corr_matrix.iloc[i, j]))
        if r > max_corr:
            max_corr = r

    return {
        "loadings": loadings,
        "ave": ave,
        "composite_reliability": cr,
        "sqrt_ave": round(sqrt_ave, 4),
        "max_inter_correlation": round(max_corr, 4),
        "discriminant_valid": sqrt_ave > max_corr,
        "convergent_valid": ave >= 0.5,
        "n_valid": n,
    }
