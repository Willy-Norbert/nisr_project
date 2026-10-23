from fastapi import APIRouter, HTTPException

from app.analytics.definitions import INDICATORS
from app.data import store
from app.schemas.common import Filters, IndicatorDefinition
from app.schemas.metadata import DatasetDetail, DatasetSummary
from app.services import indicator_service, metadata_service

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets() -> list[DatasetSummary]:
    return metadata_service.list_datasets()


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str) -> DatasetDetail:
    try:
        return metadata_service.get_dataset_detail(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Raw dataset file is not available on this server") from exc


@router.get("/indicators", response_model=list[IndicatorDefinition])
def list_indicators():
    return [i.to_dict() for i in INDICATORS.values()]


@router.get("/filters", response_model=Filters)
def filters():
    return indicator_service.filters()


@router.get("/methodology")
def methodology() -> dict:
    m = store.manifest()
    return {
        "generated_at": m["generated_at"],
        "coverage": {"seasons": m["seasons"], "plot_crop_records": m["sas_plot_crop_rows"], "households": m["ahs_households"]},
        "crops": m["crops"],
        "model": m["model"],
        "notes": [
            "All estimates use NISR survey weights (plot_weight for SAS, household weight for AHS).",
            "Yield = weighted total harvest / weighted planted crop area. 2024 crop areas come from the screening module; "
            "2025 uses NISR's Crop_Area_ha. Plots under 5 m2 and the top 1% of yields per crop are excluded.",
            "Plot-level practice rates count each plot once, even when several crops are grown on it.",
            "Cells with fewer than 10 observations are suppressed; fewer than 30 are flagged as low reliability.",
            "Input effects and model scenarios are associations, not causal estimates.",
            "AHS indicators refer to Season A 2024 and are reported at national, province and district level.",
        ],
    }
