"""Yield model and adoption scenarios.

A gradient-boosted model learns log(yield) from crop, location, season, plot size, farmer type and input use.
For every crop x district x season in the latest year it then predicts the average yield of the observed plots
under each combination of "all plots adopt input X". Predictions are pre-computed so the API needs no ML
dependencies at runtime. Estimates are associations learned from survey data, not causal effects.
"""

import itertools
import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split

from app.analytics.definitions import INPUT_COLUMNS, MIN_CELL_N

logger = logging.getLogger(__name__)

CATEGORICAL = ["crop", "district", "season", "gender"]
NUMERIC = ["year", "log_area", "large_scale", "anti_erosion", "land_consolidation", *INPUT_COLUMNS]
FEATURES = CATEGORICAL + NUMERIC


def _features(df: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for col in CATEGORICAL:
        X[col] = pd.Categorical(df[col].fillna("Unknown"), categories=categories[col]).codes
    X["year"] = df["year"]
    X["log_area"] = np.log(df["crop_area_ha"])
    X["large_scale"] = df["large_scale"].astype(float)
    for col in ["anti_erosion", "land_consolidation", *INPUT_COLUMNS]:
        X[col] = df[col].fillna(0.0)
    return X[FEATURES]


def train(sas: pd.DataFrame, crops: list[str]) -> tuple[HistGradientBoostingRegressor, dict, dict]:
    data = sas[sas["crop"].isin(crops) & sas["yield_kg_ha"].notna() & (sas["yield_kg_ha"] > 0)].copy()
    categories = {c: sorted(data[c].fillna("Unknown").unique()) for c in CATEGORICAL}
    X = _features(data, categories)
    y = np.log(data["yield_kg_ha"])
    w = data["weight"]

    X_tr, X_te, y_tr, y_te, w_tr, w_te = train_test_split(X, y, w, test_size=0.2, random_state=42)
    model = HistGradientBoostingRegressor(
        categorical_features=[FEATURES.index(c) for c in CATEGORICAL],
        max_iter=400, learning_rate=0.06, max_leaf_nodes=48, min_samples_leaf=40, random_state=42,
    )
    model.fit(X_tr, y_tr, sample_weight=w_tr)
    pred = model.predict(X_te)
    metrics = {
        "r2_log_yield": round(float(r2_score(y_te, pred)), 3),
        "mape_yield": round(float(mean_absolute_percentage_error(np.exp(y_te), np.exp(pred))), 3),
        "train_rows": int(len(X_tr)),
        "test_rows": int(len(X_te)),
        "features": FEATURES,
        "model": "HistGradientBoostingRegressor on log(yield)",
    }
    logger.info("Scenario model metrics: %s", metrics)
    model.fit(X, y, sample_weight=w)  # refit on all data for scenarios
    return model, categories, metrics


def scenarios(model, categories: dict, sas: pd.DataFrame, crops: list[str]) -> pd.DataFrame:
    year = int(sas["year"].max())
    base = sas[(sas["year"] == year) & sas["crop"].isin(crops) & (sas["crop_area_ha"] > 0)]
    inputs = list(INPUT_COLUMNS)
    combos = [c for r in range(len(inputs) + 1) for c in itertools.combinations(inputs, r)]

    rows = []
    for (season, crop, district), g in base.groupby(["season", "crop", "district"]):
        if len(g) < MIN_CELL_N:
            continue
        weights = g["weight"] * g["crop_area_ha"]  # area-weighted, matching the ratio yield estimator
        current = {c: round(float(np.average(g[c].fillna(0), weights=g["weight"]) * 100), 1) for c in inputs}
        baseline = None
        for combo in combos:
            scenario = g.copy()
            for col in combo:
                scenario[col] = 1.0
            predicted = float(np.average(np.exp(model.predict(_features(scenario, categories))), weights=weights))
            if not combo:
                baseline = predicted
            rows.append({
                "year": year, "season": season, "crop": crop, "district": district,
                "inputs": "+".join(combo) if combo else "current",
                "predicted_yield": round(predicted, 1),
                "change_pct": round((predicted / baseline - 1) * 100, 1),
                "n": len(g),
                **{f"current_{c}_pct": current[c] for c in inputs},
            })
    return pd.DataFrame(rows)
