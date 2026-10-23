import pandas as pd

from app.analytics.definitions import INDICATORS, LOW_RELIABILITY_N
from app.data import store
from app.data.cleaner import SEASONS

ALL_CROPS = "All crops"
AHS_YEAR, AHS_SEASON = 2024, "A"


class NotFoundError(LookupError):
    pass


def get_definition(indicator_id: str):
    if indicator_id not in INDICATORS:
        raise NotFoundError(f"Unknown indicator '{indicator_id}'")
    return INDICATORS[indicator_id]


def is_household(indicator_id: str) -> bool:
    return get_definition(indicator_id).source.endswith("Household Survey 2024")


def latest_period() -> tuple[int, str]:
    df = store.indicators()
    sas = df[df["indicator_id"] == "yield_kg_ha"]
    year = int(sas["year"].max())
    return year, "A"


def resolve_crop(indicator_id: str, crop: str | None) -> str:
    definition = get_definition(indicator_id)
    if is_household(indicator_id):
        return ALL_CROPS
    if definition.crop_specific and (crop is None or crop == ALL_CROPS):
        return "Maize"
    return crop or ALL_CROPS


def query(
    indicator_id: str,
    year: int | None = None,
    season: str | None = None,
    crop: str | None = None,
    level: str | None = None,
    area: str | None = None,
    province: str | None = None,
) -> pd.DataFrame:
    get_definition(indicator_id)
    df = store.indicators()
    df = df[df["indicator_id"] == indicator_id]
    if is_household(indicator_id):
        year, season = None, None
    if year is not None:
        df = df[df["year"] == year]
    if season is not None:
        df = df[df["season"] == season]
    df = df[df["crop"] == resolve_crop(indicator_id, crop)]
    if level is not None:
        df = df[df["level"] == level]
    if area is not None:
        df = df[df["area"].str.lower() == area.lower()]
    if province is not None:
        df = df[df["province"].str.lower() == province.lower()]
    df = df.copy()
    df["low_reliability"] = df["n"] < LOW_RELIABILITY_N
    return df


def value(indicator_id: str, year: int, season: str, crop: str | None, level: str, area: str) -> float | None:
    df = query(indicator_id, year, season, crop, level, area)
    return None if df.empty else float(df["value"].iloc[0])


def filters() -> dict:
    df = store.indicators()
    sas = df[df["indicator_id"] == "yield_kg_ha"]
    year, season = latest_period()
    return {
        "years": sorted(int(y) for y in sas["year"].unique()),
        "seasons": [s for s in SEASONS if s in set(sas["season"])],
        "crops": [ALL_CROPS, *store.manifest()["crops"]],
        "provinces": sorted(df.loc[df["level"] == "province", "area"].unique()),
        "districts": sorted(df.loc[df["level"] == "district", "area"].unique()),
        "latest": {"year": year, "season": season},
    }
