from fastapi import APIRouter

from app.api.v1.endpoints import comparisons, geography, health, indicators, insights, metadata, overview, reports

api_router = APIRouter()
for module in (health, metadata, overview, indicators, comparisons, geography, insights, reports):
    api_router.include_router(module.router)
