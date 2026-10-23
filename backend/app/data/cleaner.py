"""Harmonise the Seasonal Agricultural Survey (SAS) and Agriculture Household Survey (AHS) microdata.

SAS output: one row per plot x crop for every year/season, with consistent column names.
AHS output: one row per household with district, survey weight and binary indicators.
"""

import logging

import numpy as np
import pandas as pd

from app.data.loader import load_dataset
from app.data.registry import SAS_FOLDERS

logger = logging.getLogger(__name__)

SEASONS = ("A", "B", "C")
PLOT_KEY = ["year", "season", "segment_id", "farmer_id", "plot_id"]
MIN_CROP_AREA_HA = 0.0005  # 5 m2; smaller areas produce meaningless yields

DISTRICT_FIXES = {"Nyarugenege": "Nyarugenge"}

PRODUCTION_COLUMNS = {
    "Segment_ID": "segment_id",
    "s1q1": "province",
    "s1q2": "district",
    "s1q3": "stratum",
    "s1q6": "farmer_id",
    "s1q8": "gender",
    "s1q9": "age",
    "s2q1": "plot_id",
    "s2q2": "plot_area_m2",
    "s2q3": "crops_on_plot",
    "s2q4": "crop",
    "CropCategory": "crop_category",
    "s2q11": "seed_type",
    "s2q21": "harvest_kg",
    "s3q1": "organic_any",
    "s3q3": "organic_plot",
    "s3q7": "inorganic_any",
    "s3q9": "inorganic_plot",
    "s4q2": "erosion_any",
    "s4q3": "erosion_plot",
    "s4q6": "land_consolidation",
    "s4q8": "mechanization_any",
    "s4q9": "mechanization_plot",
    "s4q14": "irrigated",
}


def _answer_is(series: pd.Series, value: str) -> pd.Series:
    return series.astype("string").str.strip().str.lower().eq(value).fillna(False).astype(bool)


def _binary(series: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=series.index, dtype="float")
    out[_answer_is(series, "yes")] = 1.0
    out[_answer_is(series, "no")] = 0.0
    return out


def _gated(plot_answer: pd.Series, gate: pd.Series) -> pd.Series:
    """Plot-level Yes/No where the plot question is skipped (NaN) if the farmer answered No to the gate."""
    out = _binary(plot_answer)
    out[out.isna() & _answer_is(gate, "no")] = 0.0
    return out


def _screening_crop_area(year: int, season: str) -> pd.DataFrame:
    sc = load_dataset(
        f"sas{year}_{season.lower()}_screening", ["Segment_ID", "s2q1", "s3q1", "crop_area", "Plot_size_ha", "s3q2_1"]
    )
    if "crop_area" not in sc.columns:
        sc["crop_area"] = sc["Plot_size_ha"] * pd.to_numeric(sc["s3q2_1"], errors="coerce") / 100
    sc = sc.rename(columns={"Segment_ID": "segment_id", "s2q1": "plot_id", "s3q1": "crop", "crop_area": "screen_area_ha"})
    return sc.groupby(["segment_id", "plot_id", "crop"], as_index=False)["screen_area_ha"].sum()


def load_sas_season(year: int, season: str) -> pd.DataFrame:
    dataset_id = f"sas{year}_{season.lower()}_production"
    raw = load_dataset(dataset_id, [*PRODUCTION_COLUMNS, "plot_weight", "Plot_weight", "Crop_Area_ha"])
    weight_col = "plot_weight" if "plot_weight" in raw.columns else "Plot_weight"
    df = raw[list(PRODUCTION_COLUMNS) + [weight_col]].rename(columns={**PRODUCTION_COLUMNS, weight_col: "weight"})
    # Planted crop area is used for every season so 2024 (screening-derived) and 2025 yields are comparable.
    if "Crop_Area_ha" in raw.columns:
        df["crop_area_ha"] = raw["Crop_Area_ha"]
    else:
        df = df.merge(_screening_crop_area(year, season), on=["segment_id", "plot_id", "crop"], how="left")
        df["crop_area_ha"] = df.pop("screen_area_ha")

    df["year"] = year
    df["season"] = season
    df["district"] = df["district"].replace(DISTRICT_FIXES)
    df["province"] = df["province"].astype("string").str.strip()
    df["farmer_id"] = df["farmer_id"].astype("string")
    df["plot_area_ha"] = df.pop("plot_area_m2") / 10_000
    df["large_scale"] = df["stratum"].astype("string").str.contains("LSF", na=False)
    if "Crop_Area_ha" not in raw.columns:
        # Screening areas of large-scale farms are recorded per bloc and do not reliably match production plots,
        # so their crop area is the plot area shared equally between the crops on the plot.
        crops_on_plot = pd.to_numeric(df["crops_on_plot"], errors="coerce").clip(lower=1).fillna(1)
        df.loc[df["large_scale"], "crop_area_ha"] = df["plot_area_ha"] / crops_on_plot
        df["crop_area_ha"] = np.minimum(df["crop_area_ha"], df["plot_area_ha"])
    df = df.drop(columns=["crops_on_plot"])
    df["gender"] = df["gender"].where(df["gender"].isin(["Male", "Female"]))

    df["improved_seed"] = df["seed_type"].astype("string").str.contains("improved", case=False, na=False).astype(float)
    df["organic_fertilizer"] = _gated(df.pop("organic_plot"), df.pop("organic_any"))
    df["inorganic_fertilizer"] = _gated(df.pop("inorganic_plot"), df.pop("inorganic_any"))
    df["anti_erosion"] = _gated(df.pop("erosion_plot"), df.pop("erosion_any"))
    df["mechanization"] = _gated(df.pop("mechanization_plot"), df.pop("mechanization_any"))
    df["land_consolidation"] = _binary(df["land_consolidation"])
    df["irrigated"] = _binary(df["irrigated"]).fillna(0.0)

    valid_yield = (df["crop_area_ha"] >= MIN_CROP_AREA_HA) & (df["harvest_kg"] >= 0)
    df["yield_kg_ha"] = np.where(valid_yield, df["harvest_kg"] / df["crop_area_ha"], np.nan)
    df = _flag_yield_outliers(df)
    df = df.drop(columns=["seed_type"])
    logger.info("SAS %s%s: %d plot-crop rows, %d with valid yield", year, season, len(df), df["yield_kg_ha"].notna().sum())
    return df


def _flag_yield_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Drop yields above the 99th percentile for the crop (data-entry and area errors)."""
    cap = df.groupby("crop")["yield_kg_ha"].transform(lambda s: s.quantile(0.99))
    outlier = df["yield_kg_ha"] > cap
    df.loc[outlier, ["yield_kg_ha"]] = np.nan
    return df


def load_sas() -> pd.DataFrame:
    frames = [load_sas_season(year, season) for year in SAS_FOLDERS for season in SEASONS]
    return pd.concat(frames, ignore_index=True)


def load_ahs_households() -> pd.DataFrame:
    hh = load_dataset("ahs2024_section0", ["hhid", "province", "district", "weight"])
    hh["district"] = hh["district"].replace(DISTRICT_FIXES)

    ext = load_dataset("ahs2024_extension")
    received = ~_answer_is(ext["s6q1"], "none") & ext["s6q3"].astype("string").str.strip().ne("").fillna(False)
    ext_flags = pd.DataFrame(
        {
            "hhid": ext["hhid"],
            "extension_access": received.astype(float),
            "cooperative_member": _binary(ext["s6q10"]),
            "crop_insurance": _binary(ext["s6q8"]),
            "farmer_group_member": _binary(ext["s6q5"]),
            "agri_support_received": _binary(ext["s6q14"]),
        }
    ).groupby("hhid").max()

    sus = load_dataset("ahs2024_sustainable", ["hhid", "s8q1", "s8q4"])
    sus_flags = pd.DataFrame(
        {
            "hhid": sus["hhid"],
            "fertilizer_risk_aware": _binary(sus["s8q1"]),
            "pesticide_risk_aware": _binary(sus["s8q4"]),
        }
    ).set_index("hhid")

    out = hh.set_index("hhid").join(ext_flags).join(sus_flags).reset_index()
    logger.info("AHS: %d households", len(out))
    return out
