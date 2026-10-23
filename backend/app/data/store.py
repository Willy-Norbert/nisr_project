"""Read-only access to the processed tables produced by scripts/prepare_datasets.py."""

import json
from functools import lru_cache

import pandas as pd

from app.core.config import get_settings


class DataNotPreparedError(RuntimeError):
    pass


def _read_csv(name: str) -> pd.DataFrame:
    path = get_settings().processed_data_dir / f"{name}.csv"
    if not path.exists():
        raise DataNotPreparedError(f"{path.name} not found. Run: python -m scripts.prepare_datasets")
    return pd.read_csv(path)


@lru_cache
def indicators() -> pd.DataFrame:
    df = _read_csv("indicators")
    df["province"] = df["province"].fillna("")
    return df


@lru_cache
def gender_yield() -> pd.DataFrame:
    return _read_csv("gender_yield")


@lru_cache
def input_effects() -> pd.DataFrame:
    return _read_csv("input_effects")


@lru_cache
def scenarios() -> pd.DataFrame:
    return _read_csv("scenarios")


@lru_cache
def manifest() -> dict:
    path = get_settings().processed_data_dir / "manifest.json"
    if not path.exists():
        raise DataNotPreparedError("manifest.json not found. Run: python -m scripts.prepare_datasets")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def districts_geojson() -> dict:
    path = get_settings().geography_dir / "rwanda_districts.geojson"
    return json.loads(path.read_text(encoding="utf-8"))


def district_provinces() -> dict[str, str]:
    df = indicators()
    d = df[df["level"] == "district"].drop_duplicates("area")
    return dict(zip(d["area"], d["province"]))


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records"))
