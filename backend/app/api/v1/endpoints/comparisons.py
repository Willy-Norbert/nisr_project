from fastapi import APIRouter

from app.schemas.common import Level, Season
from app.services import comparison_service
from app.services import indicator_service as ind

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _period(year: int | None, season: str | None) -> tuple[int, str]:
    latest_year, latest_season = ind.latest_period()
    return year or latest_year, season or latest_season


@router.get("/districts")
def districts(indicator_id: str = "yield_kg_ha", year: int | None = None, season: Season | None = None, crop: str | None = None):
    year, season = _period(year, season)
    return comparison_service.districts(indicator_id, year, season, crop)


@router.get("/seasons")
def seasons(indicator_id: str = "yield_kg_ha", crop: str | None = None, level: Level = "national", area: str = "Rwanda"):
    return comparison_service.seasons(indicator_id, crop, level, area)


@router.get("/gender")
def gender(year: int | None = None, season: Season | None = None, crop: str = "Maize", level: Level = "national", area: str | None = None):
    year, season = _period(year, season)
    return comparison_service.gender(year, season, crop, level, area)


@router.get("/inputs")
def inputs(year: int | None = None, season: Season | None = None, crop: str = "Maize"):
    year, season = _period(year, season)
    return comparison_service.inputs(year, season, crop)
