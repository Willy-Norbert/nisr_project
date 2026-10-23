from fastapi import APIRouter

from app.schemas.common import Season
from app.services import indicator_service as ind
from app.services import insight_service, overview_service

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("")
def overview(year: int | None = None, season: Season | None = None):
    latest_year, latest_season = ind.latest_period()
    return overview_service.overview(year or latest_year, season or latest_season)


@router.get("/highlights")
def highlights(limit: int = 4):
    return insight_service.all_insights()[:limit]
