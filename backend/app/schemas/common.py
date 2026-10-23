from typing import Literal

from pydantic import BaseModel

Season = Literal["A", "B", "C"]
Level = Literal["national", "province", "district"]


class IndicatorDefinition(BaseModel):
    id: str
    name: str
    unit: str
    topic: str
    source: str
    description: str
    higher_is_better: bool
    crop_specific: bool


class IndicatorValue(BaseModel):
    indicator_id: str
    year: int
    season: str
    level: str
    area: str
    province: str
    crop: str
    value: float
    n: int
    low_reliability: bool


class Filters(BaseModel):
    years: list[int]
    seasons: list[str]
    crops: list[str]
    provinces: list[str]
    districts: list[str]
    latest: dict[str, int | str]
