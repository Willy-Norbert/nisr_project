from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.schemas.common import Season
from app.services import indicator_service as ind
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportRequest(BaseModel):
    year: int | None = None
    season: Season | None = None
    crop: str = "Maize"
    district: str | None = None
    format: Literal["pdf", "csv"] = "pdf"


@router.post("")
def create_report(body: ReportRequest):
    latest_year, latest_season = ind.latest_period()
    result = report_service.create(body.year or latest_year, body.season or latest_season, body.crop, body.district, body.format)
    return {
        **result,
        "download_url": f"/api/v1/reports/{result['report_id']}/download",
        "preview_url": f"/api/v1/reports/{result['report_id']}/preview",
    }


@router.get("/{report_id}/preview")
def preview(report_id: str):
    report = report_service.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or expired. Generate it again.")
    return Response(
        content=report["content"],
        media_type=report["media_type"],
        headers={"Content-Disposition": f'inline; filename="{report["filename"]}"'},
    )


@router.get("/{report_id}/download")
def download(report_id: str):
    report = report_service.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or expired. Generate it again.")
    return Response(
        content=report["content"],
        media_type=report["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{report["filename"]}"'},
    )
