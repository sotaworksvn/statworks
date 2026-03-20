"""Regression engine — OLS with bootstrap p-values (F-02)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DriverResultData:
    """Internal result for a single driver (not a Pydantic model)."""
    name: str
    coef: float
    p_value: float
    significant: bool


@dataclass
class RegressionResultData:
    """Internal result from OLS regression."""
    drivers: list[DriverResultData]
    r2: float
    model_type: str = "regression"


# ---------------------------------------------------------------------------
# OLS core
# ---------------------------------------------------------------------------

def _add_intercept(X: np.ndarray) -> np.ndarray:
    """Prepend a column of ones (intercept) to the feature matrix."""
    ones = np.ones((X.shape[0], 1))
    return np.hstack([ones, X])


def compute_ols(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    n_bootstrap: int = 200,
) -> RegressionResultData:
    """Run OLS regression with bootstrap p-values.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset with all columns.
    features : list[str]
        Column names to use as independent variables.
    target : str
        Column name of the dependent variable.
    n_bootstrap : int
        Number of bootstrap iterations (capped at 200).

    Returns
    -------
    RegressionResultData
        Top 5 drivers sorted by absolute coefficient (descending).
    """
    n_bootstrap = min(n_bootstrap, 200)  # hard cap

    X_raw = df[features].values.astype(float)
    y = df[target].values.astype(float)

    # Remove rows with NaN in either X or y
    mask = ~(np.isnan(X_raw).any(axis=1) | np.isnan(y))
    X_raw = X_raw[mask]
    y = y[mask]

    n = len(y)
    if n < 2:
        raise ValueError("Insufficient rows for regression after removing NaNs.")

    X = _add_intercept(X_raw)

    # Point estimate via lstsq (numerically stable)
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    # beta[0] = intercept, beta[1:] = feature coefficients
    coefs = beta[1:]

    # R²
    y_pred = X @ beta
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Bootstrap p-values (fixed seed for reproducibility)
    rng = np.random.default_rng(seed=42)
    boot_coefs = np.zeros((n_bootstrap, len(features)))

    for i in range(n_bootstrap):
        indices = rng.choice(n, size=n, replace=True)
        X_boot = _add_intercept(X_raw[indices])
        y_boot = y[indices]
        try:
            b, _, _, _ = np.linalg.lstsq(X_boot, y_boot, rcond=None)
            boot_coefs[i] = b[1:]
        except np.linalg.LinAlgError:
            boot_coefs[i] = coefs  # degenerate sample → use point estimate

    # p-value: fraction of bootstrap samples with opposite sign
    p_values: list[float] = []
    for j in range(len(features)):
        if coefs[j] >= 0:
            p = float(np.mean(boot_coefs[:, j] < 0))
        else:
            p = float(np.mean(boot_coefs[:, j] > 0))
        # Ensure p is at least 1/n_bootstrap (avoid exact 0.0)
        p = max(p, 1.0 / n_bootstrap)
        p_values.append(p)

    # Build driver list
    drivers: list[DriverResultData] = []
    for j, feat in enumerate(features):
        drivers.append(
            DriverResultData(
                name=feat,
                coef=round(float(coefs[j]), 4),
                p_value=round(p_values[j], 4),
                significant=p_values[j] < 0.05,
            )
        )

    # Sort by abs(coef) descending, keep top 5
    drivers.sort(key=lambda d: abs(d.coef), reverse=True)
    drivers = drivers[:5]

    return RegressionResultData(drivers=drivers, r2=round(r2, 4))
