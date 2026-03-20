"""PLS engine — simplified mean-based latent variables with path coefficients (F-02).

The PLS implementation here is a simplified version suitable for the hackathon
demo.  Latent variable scores are computed as the row-wise mean of each
indicator group.  The inner model is then an OLS regression on those latent
variable scores, reusing the regression engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.engines.regression import (
    DriverResultData,
    RegressionResultData,
    compute_ols,
)


# ---------------------------------------------------------------------------
# Custom error for fallback handling
# ---------------------------------------------------------------------------

class PLSFallbackError(Exception):
    """Raised when the PLS engine cannot produce a valid result.

    The Decision Router catches this and falls back to OLS regression.
    """


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class PLSResultData:
    """Internal result from PLS path modelling."""
    drivers: list[DriverResultData]
    r2: float
    model_type: str = "pls"


# ---------------------------------------------------------------------------
# PLS core
# ---------------------------------------------------------------------------

def _detect_indicator_groups(
    df: pd.DataFrame,
    features: list[str],
    threshold: float = 0.6,
) -> dict[str, list[str]]:
    """Heuristically group features into latent variable indicators.

    Two features are grouped together if their Pearson correlation exceeds
    *threshold*.  Features that don't correlate highly with any other are
    placed in their own singleton group.

    Returns a dict mapping a group label to its constituent column names.
    Group labels are human-readable: for multi-indicator groups, names are
    joined (e.g. "Trust + Freedom") rather than opaque "LV_0".
    """
    numeric_feats = [f for f in features if pd.api.types.is_numeric_dtype(df[f])]
    if len(numeric_feats) < 2:
        # Nothing to group — return each feature as its own "group"
        return {f: [f] for f in features}

    corr = df[numeric_feats].corr().abs()
    visited: set[str] = set()
    groups: dict[str, list[str]] = {}

    for feat in numeric_feats:
        if feat in visited:
            continue
        # Find all features correlated above threshold with *feat*
        related = [
            f for f in numeric_feats
            if f != feat and f not in visited and corr.loc[feat, f] > threshold
        ]
        group = [feat] + related
        visited.update(group)

        if len(group) > 1:
            # Human-readable label: join indicator names with " + "
            # Show max 2 indicators to keep chart labels compact
            short_names = [_clean_indicator_name(n) for n in group[:2]]
            label = " + ".join(short_names)
            if len(group) > 2:
                label += f" (+{len(group) - 2} more)"
        else:
            label = feat

        groups[label] = group

    # Add any non-numeric features as singletons
    for f in features:
        if f not in visited:
            groups[f] = [f]

    return groups


def _clean_indicator_name(name: str) -> str:
    """Clean up an indicator column name for display.

    Strips trailing year suffixes and common prefixes to make names
    shorter and more readable.
    """
    # Remove common suffixes like "_2019", " 2019"
    import re
    cleaned = re.sub(r"[_ ]\d{4}$", "", name)
    # Replace underscores with spaces and title-case
    cleaned = cleaned.replace("_", " ").strip()
    if cleaned:
        return cleaned.title()
    return name


def compute_pls(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    n_bootstrap: int = 200,
) -> PLSResultData:
    """Compute PLS-style path model with mean-based latent variables.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset with all columns.
    features : list[str]
        Column names to use as indicators.
    target : str
        Column name of the dependent variable.
    n_bootstrap : int
        Number of bootstrap iterations (capped at 200).

    Returns
    -------
    PLSResultData
        Top 5 drivers sorted by absolute path coefficient (descending).

    Raises
    ------
    PLSFallbackError
        When the computation fails for any reason (singular matrix, etc.).
    """
    try:
        indicator_groups = _detect_indicator_groups(df, features)

        # Build latent variable scores
        lv_df = pd.DataFrame(index=df.index)
        for group_label, indicators in indicator_groups.items():
            numeric_indicators = [
                c for c in indicators if pd.api.types.is_numeric_dtype(df[c])
            ]
            if not numeric_indicators:
                continue
            lv_df[group_label] = df[numeric_indicators].mean(axis=1)

        if lv_df.empty or lv_df.shape[1] == 0:
            raise PLSFallbackError("No valid latent variables could be constructed.")

        # Inner model: OLS on the latent variable scores
        lv_features = list(lv_df.columns)

        # We need the target in the same frame
        inner_df = lv_df.copy()
        inner_df[target] = df[target].values

        result: RegressionResultData = compute_ols(
            inner_df, lv_features, target, n_bootstrap=n_bootstrap
        )

        return PLSResultData(
            drivers=result.drivers,
            r2=result.r2,
        )

    except PLSFallbackError:
        raise
    except Exception as exc:
        raise PLSFallbackError(f"PLS computation failed: {exc}") from exc
