from fastapi import APIRouter, Query

from app.analytics.definitions import INDICATORS
from app.data import store
from app.schemas.common import IndicatorDefinition, IndicatorValue, Level, Season
from app.services import indicator_service as ind

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("", response_model=list[IndicatorDefinition])
def list_indicators():
    return [i.to_dict() for i in INDICATORS.values()]


@router.get("/{indicator_id}", response_model=IndicatorDefinition)
def get_indicator(indicator_id: str):
    return ind.get_definition(indicator_id).to_dict()


@router.get("/{indicator_id}/values", response_model=list[IndicatorValue])
def get_values(
    indicator_id: str,
    year: int | None = None,
    season: Season | None = None,
    crop: str | None = Query(None, description="Crop name or 'All crops'"),
    level: Level | None = None,
    area: str | None = None,
    province: str | None = None,
):
    return store.records(ind.query(indicator_id, year, season, crop, level, area, province))
