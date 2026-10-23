from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.analytics.prioritization import DEFAULT_WEIGHTS
from app.schemas.common import Season
from app.core.config import get_settings
from app.services import ask_service, insight_service, llm_service, priority_service, scenario_service
from app.services import indicator_service as ind

router = APIRouter(tags=["insights"])


@router.get("/insights")
def list_insights():
    return insight_service.all_insights()


@router.get("/insights/{insight_id}")
def get_insight(insight_id: str):
    return insight_service.get(insight_id)


@router.get("/priorities")
def priorities(
    year: int | None = None,
    season: Season | None = None,
    crop: str = "Maize",
    w_yield_gap: float = DEFAULT_WEIGHTS["yield_gap"],
    w_potential_gain: float = DEFAULT_WEIGHTS["potential_gain"],
    w_seed_gap: float = DEFAULT_WEIGHTS["seed_gap"],
    w_fertilizer_gap: float = DEFAULT_WEIGHTS["fertilizer_gap"],
    w_extension_gap: float = DEFAULT_WEIGHTS["extension_gap"],
):
    latest_year, latest_season = ind.latest_period()
    weights = {
        "yield_gap": w_yield_gap,
        "potential_gain": w_potential_gain,
        "seed_gap": w_seed_gap,
        "fertilizer_gap": w_fertilizer_gap,
        "extension_gap": w_extension_gap,
    }
    return priority_service.priorities(year or latest_year, season or latest_season, crop, weights)


@router.get("/scenarios/options")
def scenario_options():
    return scenario_service.options()


@router.get("/scenarios")
def scenario(crop: str = "Maize", district: str = "Nyagatare", season: Season = "A", inputs: list[str] = Query(default=[])):
    return scenario_service.simulate(crop, district, season, inputs)


class ChatTurn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[ChatTurn] = []


@router.post("/ask")
def ask(body: AskRequest):
    return ask_service.answer(body.question, [t.model_dump() for t in body.history])


@router.get("/ask/status")
def ask_status():
    settings = get_settings()
    return {"ai_enabled": llm_service.enabled(), "model": settings.llm_model if llm_service.enabled() else None}


@router.get("/ask/suggestions")
def suggestions():
    return ask_service.SUGGESTIONS
