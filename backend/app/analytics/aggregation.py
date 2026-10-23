"""Survey-weighted aggregation of the harmonised microdata into small, publishable tables."""

import numpy as np
import pandas as pd

from app.analytics.definitions import AHS_RATE_COLUMNS, INPUT_COLUMNS, MIN_CELL_N, SAS_RATE_COLUMNS
from app.data.cleaner import PLOT_KEY

ALL = "All crops"
LEVELS = {"national": None, "province": "province", "district": "district"}


def _ratio_yield(g: pd.DataFrame) -> tuple[float, int]:
    v = g[g["yield_kg_ha"].notna()]
    area = (v["weight"] * v["crop_area_ha"]).sum()
    return ((v["weight"] * v["harvest_kg"]).sum() / area if area > 0 else np.nan), len(v)


def _weighted_rate(values: pd.Series, weights: pd.Series) -> tuple[float, int]:
    mask = values.notna()
    if not mask.any():
        return np.nan, 0
    return float(np.average(values[mask], weights=weights[mask]) * 100), int(mask.sum())


def _plot_level(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse plot x crop rows to one row per plot, so multi-crop plots are counted once."""
    flags = list(SAS_RATE_COLUMNS.values())
    agg = {c: "max" for c in flags} | {"weight": "first", "province": "first", "district": "first"}
    return df.groupby(PLOT_KEY, as_index=False).agg(agg)


def _groups(df: pd.DataFrame, level: str):
    col = LEVELS[level]
    if col is None:
        yield "Rwanda", None, df
        return
    for area, g in df.groupby(col):
        province = g["province"].iloc[0] if level == "district" else area
        yield area, province, g


def sas_indicators(sas: pd.DataFrame, crops: list[str]) -> pd.DataFrame:
    rows = []
    for (year, season), season_df in sas.groupby(["year", "season"]):
        plots = _plot_level(season_df)
        crop_frames = {ALL: (plots, season_df)} | {c: (season_df[season_df["crop"] == c],) * 2 for c in crops}
        for crop, (rate_df, prod_df) in crop_frames.items():
            for level in LEVELS:
                for area, province, g in _groups(rate_df, level):
                    for ind, col in SAS_RATE_COLUMNS.items():
                        value, n = _weighted_rate(g[col], g["weight"])
                        rows.append((ind, year, season, level, area, province, crop, value, n))
                if crop == ALL:
                    continue
                for area, province, g in _groups(prod_df, level):
                    value, n = _ratio_yield(g)
                    rows.append(("yield_kg_ha", year, season, level, area, province, crop, value, n))
                    total = (g["weight"] * g["harvest_kg"]).sum() / 1000
                    rows.append(("production_t", year, season, level, area, province, crop, total, int(g["harvest_kg"].notna().sum())))
    return _finalise(rows)


def ahs_indicators(ahs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for level in LEVELS:
        for area, province, g in _groups(ahs, level):
            for ind, col in AHS_RATE_COLUMNS.items():
                value, n = _weighted_rate(g[col], g["weight"])
                rows.append((ind, 2024, "A", level, area, province, ALL, value, n))
    return _finalise(rows)


def _finalise(rows: list[tuple]) -> pd.DataFrame:
    out = pd.DataFrame(rows, columns=["indicator_id", "year", "season", "level", "area", "province", "crop", "value", "n"])
    out = out[(out["n"] >= MIN_CELL_N) & out["value"].notna()].copy()
    out["value"] = out["value"].round(2)
    return out.reset_index(drop=True)


def gender_yield(sas: pd.DataFrame, crops: list[str]) -> pd.DataFrame:
    """Yield of plots managed by female vs male farmers (small-scale farmers only)."""
    rows = []
    small = sas[~sas["large_scale"] & sas["gender"].notna()]
    for (year, season, crop), g in small[small["crop"].isin(crops)].groupby(["year", "season", "crop"]):
        for level in ("national", "district"):
            for area, province, ga in _groups(g, level):
                for gender, gg in ga.groupby("gender"):
                    value, n = _ratio_yield(gg)
                    rows.append((year, season, level, area, province, crop, gender, value, n))
    out = pd.DataFrame(rows, columns=["year", "season", "level", "area", "province", "crop", "gender", "yield_kg_ha", "n"])
    out = out[(out["n"] >= MIN_CELL_N) & out["yield_kg_ha"].notna()]
    out["yield_kg_ha"] = out["yield_kg_ha"].round(1)
    return out.reset_index(drop=True)


def input_effects(sas: pd.DataFrame, crops: list[str]) -> pd.DataFrame:
    """National yield of plots with vs without each input. Descriptive, not causal."""
    rows = []
    for (year, season, crop), g in sas[sas["crop"].isin(crops)].groupby(["year", "season", "crop"]):
        for col, label in INPUT_COLUMNS.items():
            with_y, n_with = _ratio_yield(g[g[col] == 1])
            without_y, n_without = _ratio_yield(g[g[col] == 0])
            if min(n_with, n_without) < MIN_CELL_N:
                continue
            rows.append((year, season, crop, col, label, round(with_y, 1), round(without_y, 1), n_with, n_without))
    out = pd.DataFrame(
        rows, columns=["year", "season", "crop", "input", "input_label", "yield_with", "yield_without", "n_with", "n_without"]
    )
    out["premium_pct"] = ((out["yield_with"] / out["yield_without"] - 1) * 100).round(1)
    return out
