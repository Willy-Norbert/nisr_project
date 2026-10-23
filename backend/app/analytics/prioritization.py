"""Transparent district priority scores for targeting yield-improvement support.

Each component is min-max scaled across districts to 0-1 (1 = greater need or opportunity) and combined with
user-adjustable weights. Districts missing a component are scored on the remaining components only.
"""

import numpy as np
import pandas as pd

DEFAULT_WEIGHTS = {
    "yield_gap": 0.30,
    "potential_gain": 0.30,
    "seed_gap": 0.15,
    "fertilizer_gap": 0.15,
    "extension_gap": 0.10,
}

COMPONENT_LABELS = {
    "yield_gap": "Yield gap to top-performing districts",
    "potential_gain": "Model-estimated gain from improved seed + fertilizer",
    "seed_gap": "Plots not using improved seed",
    "fertilizer_gap": "Plots not using inorganic fertilizer",
    "extension_gap": "Households without extension services",
}


def _scale(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or hi == lo:
        return pd.Series(0.5, index=s.index).where(s.notna())
    return (s - lo) / (hi - lo)


def score(components: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """components: one row per district with raw columns matching DEFAULT_WEIGHTS keys."""
    scaled = pd.DataFrame({k: _scale(components[k]) for k in weights}, index=components.index)
    w = pd.Series(weights)
    available = scaled.notna()
    weighted = scaled.fillna(0).mul(w, axis=1).sum(axis=1)
    total_weight = available.mul(w, axis=1).sum(axis=1)
    out = components.copy()
    out["score"] = np.where(total_weight > 0, weighted / total_weight * 100, np.nan).round(1)
    for k in weights:
        out[f"{k}_scaled"] = scaled[k].round(3)
    return out.sort_values("score", ascending=False)
