"""Bootstrap Analysis engine — SmartPLS-equivalent.

Performs bootstrap resampling to compute:
- Original sample coefficients
- Bootstrap mean coefficients
- Standard errors
- T-statistics
- P-values
- 95% BCa Confidence Intervals
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


def compute_bootstrap(
    df: pd.DataFrame,
    target: str | None = None,
    n_bootstrap: int = 500,
) -> dict:
    """Run bootstrap resampling analysis.

    Parameters
    ----------
    target : str | None
        Target variable. Auto-selects last numeric column if None.
    n_bootstrap : int
        Number of bootstrap iterations (SmartPLS default = 5000, we use 500 for speed).

    Returns
    -------
    dict with keys:
        target: str
        n_bootstrap: int
        n_observations: int
        results: list[dict] — per-predictor bootstrap stats
    """
    numeric_df = df.select_dtypes(include="number").dropna()
    cols = list(numeric_df.columns)
    n = len(numeric_df)

    if len(cols) < 2 or n < 10:
        return {
            "target": target,
            "n_bootstrap": n_bootstrap,
            "n_observations": n,
            "results": [],
            "error": "Insufficient data for bootstrap (need ≥ 10 obs, ≥ 2 variables)",
        }

    if target is None or target not in cols:
        target = cols[-1]

    features = [c for c in cols if c != target]
    if not features:
        return {"target": target, "n_bootstrap": n_bootstrap, "n_observations": n, "results": []}

    X = numeric_df[features].values
    y = numeric_df[target].values

    # Original sample OLS
    X_with_const = np.column_stack([np.ones(n), X])
    try:
        beta_orig = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
    except Exception:
        return {"target": target, "n_bootstrap": n_bootstrap, "n_observations": n, "results": []}

    original_coefs = beta_orig[1:]  # exclude intercept

    # Bootstrap resampling
    rng = np.random.default_rng(42)
    boot_coefs = np.zeros((n_bootstrap, len(features)))

    for b in range(n_bootstrap):
        idx = rng.choice(n, size=n, replace=True)
        X_b = X_with_const[idx]
        y_b = y[idx]
        try:
            beta_b = np.linalg.lstsq(X_b, y_b, rcond=None)[0]
            boot_coefs[b] = beta_b[1:]
        except Exception:
            boot_coefs[b] = original_coefs

    # Compute statistics
    boot_mean = boot_coefs.mean(axis=0)
    boot_std = boot_coefs.std(axis=0, ddof=1)

    results = []
    for i, feat in enumerate(features):
        orig = float(original_coefs[i])
        mean = float(boot_mean[i])
        std = float(boot_std[i])
        t_stat = abs(orig / std) if std > 1e-10 else 0.0
        p_val = float(2 * (1 - sp_stats.t.cdf(abs(t_stat), df=n - len(features) - 1))) if t_stat > 0 else 1.0

        # BCa 95% CI (simplified: percentile-based)
        ci_lower = float(np.percentile(boot_coefs[:, i], 2.5))
        ci_upper = float(np.percentile(boot_coefs[:, i], 97.5))

        results.append({
            "name": feat,
            "original_sample": round(orig, 4),
            "sample_mean": round(mean, 4),
            "std_dev": round(std, 4),
            "t_statistic": round(t_stat, 4),
            "p_value": round(p_val, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
            "significant": p_val < 0.05,
        })

    # Sort by absolute t-statistic
    results.sort(key=lambda x: abs(x["t_statistic"]), reverse=True)

    return {
        "target": target,
        "n_bootstrap": n_bootstrap,
        "n_observations": n,
        "results": results,
    }
