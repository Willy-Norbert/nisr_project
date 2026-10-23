from fastapi import APIRouter

from app.schemas.common import Season
from app.services import geography_service
from app.services import indicator_service as ind

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/districts.geojson")
def districts_geojson(indicator_id: str | None = None, year: int | None = None, season: Season | None = None, crop: str | None = None):
    latest_year, latest_season = ind.latest_period()
    return geography_service.districts_geojson(indicator_id, year or latest_year, season or latest_season, crop)


@router.get("/locations")
def locations():
    return geography_service.locations()


@router.get("/locations/{district}")
def location(district: str, year: int | None = None, season: Season | None = None):
    latest_year, latest_season = ind.latest_period()
    return geography_service.profile(district, year or latest_year, season or latest_season)
