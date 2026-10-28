"""Question answering for the Ask page.

A question is turned into a query plan (intent + indicator/crop/district/season filters), the plan is executed
against the processed survey tables, and the result is written up as an answer. When an LLM is configured it
plans the query (understanding follow-ups from the conversation) and writes the answer from the retrieved numbers
only; otherwise a rule-based parser and templates are used. Either way, every number comes from the data.
"""

import json
import logging
import re

from app.analytics.definitions import INDICATORS
from app.data import store
from app.services import (
    comparison_service,
    geography_service,
    indicator_service as ind,
    llm_service,
    overview_service,
    priority_service,
    scenario_service,
)

logger = logging.getLogger(__name__)

INTENTS = ["overview", "districts", "trend", "inputs", "gender", "scenario", "priorities", "profile", "chat"]

INDICATOR_KEYWORDS = [
    ("production_t", ["production", "produce", "harvest", "tonnes", "output"]),
    ("yield_kg_ha", ["yield", "productivity", "kg/ha", "per hectare"]),
    ("improved_seed_pct", ["seed"]),
    ("organic_fertilizer_pct", ["organic", "manure", "compost"]),
    ("inorganic_fertilizer_pct", ["fertilizer", "fertiliser", "npk", "dap", "urea"]),
    ("irrigation_pct", ["irrigat", "water"]),
    ("anti_erosion_pct", ["erosion", "terrace"]),
    ("land_consolidation_pct", ["consolidat"]),
    ("extension_access_pct", ["extension", "advisory", "training"]),
    ("cooperative_member_pct", ["cooperative", "association"]),
    ("crop_insurance_pct", ["insurance"]),
    ("agri_support_pct", ["grant", "support", "subsid"]),
    ("fertilizer_risk_aware_pct", ["aware", "risk"]),
]

CROP_SYNONYMS = {
    "beans": "Bush bean", "bean": "Bush bean", "potato": "Irish potato", "potatoes": "Irish potato",
    "rice": "Paddy rice", "banana": "Cooking banana", "bananas": "Cooking banana", "soya": "Soybean",
    "peas": "Pea", "groundnuts": "Groundnut", "tomatoes": "Tomato",
}

INPUT_KEYWORDS = {
    "improved_seed": ["seed"],
    "inorganic_fertilizer": ["fertilizer", "fertiliser", "npk", "dap", "urea"],
    "organic_fertilizer": ["organic", "manure", "compost"],
    "irrigated": ["irrigat"],
}

INPUT_INDICATORS = {
    "improved_seed": "improved_seed_pct",
    "inorganic_fertilizer": "inorganic_fertilizer_pct",
    "organic_fertilizer": "organic_fertilizer_pct",
    "irrigated": "irrigation_pct",
}

SUGGESTIONS = [
    "Which districts have the highest maize yield?",
    "How has bean yield changed across seasons?",
    "Does improved seed increase maize yield?",
    "What if farmers in Nyagatare used improved seed and fertilizer for maize?",
    "Where should fertilizer support be prioritised for Irish potato?",
    "Compare women and men farmers' maize yields",
    "Show me Musanze district",
    "Which districts have the lowest extension access?",
]


def _has(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def _find_crop(text: str) -> str | None:
    crops = store.manifest()["crops"]
    for crop in sorted(crops, key=len, reverse=True):
        if crop.lower() in text:
            return crop
    for word, crop in CROP_SYNONYMS.items():
        if re.search(rf"\b{word}\b", text):
            return crop
    return None


def _find_district(text: str) -> str | None:
    for district in store.district_provinces():
        if district.lower() in text:
            return district
    return None


def _find_indicator(text: str) -> str | None:
    for indicator_id, words in INDICATOR_KEYWORDS:
        if _has(text, words):
            return indicator_id
    return None


def _period(text: str) -> tuple[int, str]:
    year, season = ind.latest_period()
    if m := re.search(r"\b(2024|2025)\b", text):
        year = int(m.group(1))
    if m := re.search(r"season\s*([abc])\b", text):
        season = m.group(1).upper()
    return year, season


def parse(question: str) -> dict:
    text = question.lower().strip()
    year, season = _period(text)
    crop = _find_crop(text)
    district = _find_district(text)
    indicator_id = _find_indicator(text)
    inputs = [k for k, words in INPUT_KEYWORDS.items() if _has(text, words)]

    if re.fullmatch(r"(hi|hello|hey|thanks|thank you|muraho|bite|help|who are you|what can you do)[!?. ]*", text):
        intent = "chat"
    elif _has(text, ["what if", "simulat", "scenario", "would happen", "if farmers", "if all"]):
        intent = "scenario"
    elif _has(text, ["priorit", "target", "where should", "most need", "invest"]):
        intent = "priorities"
    elif _has(text, ["women", "woman", "female", "gender", " men "]):
        intent = "gender"
    elif inputs and _has(text, ["effect", "impact", "increase", "improve", "boost", "premium", "difference", "does ", "do "]):
        intent = "inputs"
        indicator_id = INPUT_INDICATORS[inputs[0]]
    elif _has(text, ["trend", "over time", "changed", "change", "across seasons", "between seasons", "evolution", "vs"]):
        intent = "trend"
    elif district and not _has(text, ["compare", "which", "rank", "highest", "lowest", "best", "worst"]):
        intent = "profile"
    elif not indicator_id and not crop and not _has(text, ["which", "rank", "highest", "lowest", "best", "worst", "district"]):
        intent = "overview"
    else:
        intent = "districts"

    return {
        "intent": intent,
        "indicator_id": indicator_id or "yield_kg_ha",
        "crop": crop,
        "district": district,
        "year": year,
        "season": season,
        "inputs": inputs,
        "ascending": _has(text, ["lowest", "worst", "least", "poorest", "bottom"]),
    }


def _run(p: dict) -> tuple[str, dict | None]:
    intent, year, season = p["intent"], p["year"], p["season"]
    crop = p["crop"] or "Maize"

    if intent == "chat":
        data = overview_service.overview(year, season)
        text = ("I'm FarmGap's data assistant. Ask me about crop yields, inputs such as improved seed, fertilizer and "
                "irrigation, district comparisons, trends across seasons, women farmers, priority districts or "
                "what-if scenarios, and I'll answer from NISR survey data.")
    elif intent == "overview":
        data = overview_service.overview(year, season)
        kpis = "; ".join(f"{k['name'].lower()} {k['value']:,.1f}%" for k in data["kpis"] if k["value"] is not None)
        crops = "; ".join(f"{c['crop'].lower()} {c['yield_kg_ha']:,.0f} kg/ha" for c in data["crops"])
        cov = data["coverage"]
        text = (f"Rwanda's agriculture at a glance ({data['year']} Season {data['season']}, NISR surveys covering "
                f"{cov['plot_crop_records']:,} plot-crop records and {cov['households']:,} households in {cov['districts']} districts).\n"
                f"- Farm practices: {kpis}.\n"
                f"- Main crop yields: {crops}.\n"
                f"Ask about a crop, a district or an input (seed, fertilizer, irrigation) to go deeper.")
    elif intent == "scenario":
        district = p["district"] or "Nyagatare"
        inputs = p["inputs"] or ["improved_seed", "inorganic_fertilizer"]
        scen_year = scenario_service.options()["year"]
        data = scenario_service.simulate(crop, district, season if season in ("A", "B") else "A", inputs)
        text = (f"If every surveyed {crop.lower()} plot in {data['district']} adopted "
                f"{', '.join(i.replace('_', ' ') for i in data['inputs'])}, the model estimates average yield would move from "
                f"{data['current_yield']:,.0f} to {data['scenario_yield']:,.0f} kg/ha ({data['change_pct']:+.1f}%), "
                f"based on {scen_year} Season {data['season']} data.")
    elif intent == "priorities":
        data = priority_service.priorities(year, season, crop)
        top = [d["district"] for d in data["districts"][:5]]
        text = f"For {crop.lower()} in {year} Season {season}, the highest-priority districts are {', '.join(top)}."
    elif intent == "gender":
        data = comparison_service.gender(year, season, crop, "national")
        rows = data["rows"]
        if rows and "gap_pct" in rows[0]:
            r = rows[0]
            text = (f"Female-managed {crop.lower()} plots averaged {r['Female']:,.0f} kg/ha vs {r['Male']:,.0f} kg/ha for men "
                    f"({r['gap_pct']:+.1f}%) in {year} Season {season}.")
        else:
            text = f"Not enough plots to compare women and men for {crop.lower()} in {year} Season {season}."
    elif intent == "inputs":
        data = comparison_service.inputs(year, season, crop)
        target = p["inputs"][0]
        effect = next((e for e in data["effects"] if e["input"] == target), None)
        text = (f"{crop} plots using {effect['input_label'].lower()} yielded {effect['yield_with']:,.0f} kg/ha vs "
                f"{effect['yield_without']:,.0f} kg/ha without ({effect['premium_pct']:+.1f}%) in {year} Season {season}."
                if effect else f"Not enough data on that input for {crop.lower()} in {year} Season {season}.")
    elif intent == "trend":
        level, area = ("district", p["district"]) if p["district"] else ("national", "Rwanda")
        data = comparison_service.seasons(p["indicator_id"], crop, level, area)
        series = data["series"]
        name = data["indicator"]["name"].lower()
        label = f"{name} for {data['crop'].lower()}" if data["crop"] != ind.ALL_CROPS else name
        text = (f"{label.capitalize()} in {area}: " + ", ".join(f"{s['period']}: {s['value']:,.1f}" for s in series)
                + f" ({data['indicator']['unit']}).") if series else "No data for that combination."
    elif intent == "profile":
        data = geography_service.profile(p["district"], year, season)
        better = [r["name"] for r in data["indicators"] if r["difference"] and r["difference"] > 0][:3]
        text = (f"{data['district']} ({data['province']}), {year} Season {season}. Above the national average on: "
                f"{', '.join(better) if better else 'none of the headline indicators'}.")
    else:
        data = comparison_service.districts(p["indicator_id"], year, season, p["crop"])
        rows = data["districts"][::-1] if p["ascending"] else data["districts"]
        top = rows[:3]
        word = "lowest" if p["ascending"] else "highest"
        unit = data["indicator"]["unit"]
        subject = data["indicator"]["name"].lower()
        if data["crop"] != ind.ALL_CROPS:
            subject += f" for {data['crop'].lower()}"
        period = "2024 household survey" if data["year"] is None else f"{year} Season {season}"
        text = (f"The {word} {subject} ({period}): "
                + "; ".join(f"{r['area']} {r['value']:,.1f} {unit}" for r in top)
                + (f". National: {data['national_value']:,.1f} {unit}." if data["national_value"] is not None else "."))

    return text, data


def _plan_prompt() -> str:
    year, season = ind.latest_period()
    indicators = "\n".join(f"- {i.id}: {i.name} ({i.unit}){' [per crop]' if i.crop_specific else ''}" for i in INDICATORS.values())
    return f"""You plan data queries for FarmGap Rwanda, an agricultural statistics assistant built on NISR surveys
(Seasonal Agricultural Survey 2024-2025, seasons A/B/C; Agriculture Household Survey 2024).
Read the conversation and the latest user question, then return ONE JSON object:
{{"intent": one of {INTENTS},
 "indicator_id": indicator id or null,
 "crop": crop name from the list or null,
 "district": district name from the list or null,
 "year": 2024 or 2025 or null,
 "season": "A", "B", "C" or null,
 "inputs": list from ["improved_seed","inorganic_fertilizer","organic_fertilizer","irrigated"],
 "ascending": true when the user wants the lowest/worst values}}

Intents:
- overview: general questions about Rwanda's agriculture as a whole ("tell me about Rwanda", "give me a summary")
- districts: rank or compare districts on an indicator ("which districts...", "where is ... highest/lowest")
- trend: change across seasons/years, nationally or for one district
- inputs: whether/how much an input (seed, fertilizer, irrigation) raises yield
- gender: female vs male farmers
- scenario: what-if adoption of inputs in a district (model simulation)
- priorities: where support/investment should go
- profile: anything about one district in general ("tell me about Musanze", "how is Huye doing")
- chat: greetings, questions about FarmGap, methods or definitions that need no specific numbers

Resolve follow-ups from the conversation (e.g. "and in Huye?" keeps the previous intent and crop).
Map crop synonyms: beans -> Bush bean, potato -> Irish potato, rice -> Paddy rice, banana -> Cooking banana.
Default period when not stated: {year} Season {season}.

Crops: {", ".join(store.manifest()["crops"])}
Districts: {", ".join(sorted(store.district_provinces()))}
Indicators:
{indicators}"""


def _validate(raw: dict, fallback: dict) -> dict:
    crops = {c.lower(): c for c in store.manifest()["crops"]}
    districts = {d.lower(): d for d in store.district_provinces()}
    year, season = ind.latest_period()
    p = dict(fallback)
    if raw.get("intent") in INTENTS:
        p["intent"] = raw["intent"]
    if raw.get("indicator_id") in INDICATORS:
        p["indicator_id"] = raw["indicator_id"]
    crop = str(raw.get("crop") or "").lower()
    p["crop"] = crops.get(crop) or CROP_SYNONYMS.get(crop) or (fallback["crop"] if crop else None)
    p["district"] = districts.get(str(raw.get("district") or "").lower())
    p["year"] = raw["year"] if raw.get("year") in (2024, 2025) else year
    p["season"] = raw["season"] if raw.get("season") in ("A", "B", "C") else season
    p["inputs"] = [i for i in raw.get("inputs") or [] if i in INPUT_INDICATORS]
    p["ascending"] = bool(raw.get("ascending"))
    if p["intent"] == "inputs":
        p["inputs"] = p["inputs"] or ["improved_seed"]
        p["indicator_id"] = INPUT_INDICATORS[p["inputs"][0]]
    if p["intent"] == "profile" and not p["district"]:
        p["intent"] = "districts"
    return p


def _facts(p: dict, data: dict | None) -> dict | None:
    """Compact version of the retrieved data for the writer model."""
    if data is None:
        return None
    if p["intent"] in ("chat", "overview"):
        return {"latest_period": f"{data['year']} Season {data['season']}", "kpis": data["kpis"], "crops": data["crops"]}
    if p["intent"] == "districts":
        return {k: data[k] for k in ("indicator", "crop", "year", "season", "national_value")} | {
            "districts": [{"district": r["area"], "value": r["value"], "rank": r["rank"]} for r in data["districts"]]}
    if p["intent"] == "priorities":
        keep = ("district", "rank", "score", "yield_kg_ha", "improved_seed_pct", "inorganic_fertilizer_pct",
                "extension_access_pct", "potential_gain_pct", "additional_production_t")
        return {"crop": data["crop"], "period": f"{data['year']} Season {data['season']}", "method": data["method"],
                "benchmark_yield_kg_ha": data["benchmark_yield_kg_ha"],
                "top_districts": [{k: d[k] for k in keep} for d in data["districts"][:10]]}
    if p["intent"] == "profile":
        return {k: data[k] for k in ("district", "province", "year", "season", "indicators", "crop_yields")}
    return data


WRITER_PROMPT = """You are FarmGap Rwanda's agricultural data analyst. Answer ONLY the LATEST QUESTION, not an
earlier question in the conversation. Use ONLY the numbers and facts in DATA (retrieved from NISR surveys). Never
invent numbers; if DATA does not cover the latest question, return the DRAFT answer unchanged rather than answering
a different question from conversation history.
Style: clear, friendly, plain English (reply in Kinyarwanda or French if the user writes in it); 2-5 short sentences
or a few bullet points with "- "; round sensibly (kg/ha to whole numbers, % to one decimal); always state the
period (year and season). Add one practical takeaway for planners when relevant. Input/yield differences and model
scenarios are associations, not proven causal effects. No headings, no tables, no markdown other than "- " bullets
and **bold**."""


def answer(question: str, history: list[dict] | None = None) -> dict:
    history = [m for m in (history or []) if m.get("role") in ("user", "assistant") and m.get("content")][-8:]
    p = parse(question)
    ai = False

    if llm_service.enabled():
        try:
            raw = llm_service.chat_json([{"role": "system", "content": _plan_prompt()}, *history,
                                         {"role": "user", "content": question}])
            p = _validate(raw, p)
            ai = True
        except llm_service.LLMError:
            pass

    try:
        text, data = _run(p)
    except ind.NotFoundError as exc:
        p, data, text = {**p, "intent": "chat"}, None, f"I couldn't find data for that: {exc}."

    if ai:
        facts = json.dumps({"query": p, "data": _facts(p, data), "draft": text}, default=str)[:24000]
        try:
            text = llm_service.chat(
                [{"role": "system", "content": WRITER_PROMPT}, *history,
                 {"role": "user", "content": f"LATEST QUESTION: {question}\n\nDATA: {facts}"}],
                temperature=0.3,
            )
        except llm_service.LLMError:
            ai = False

    return {"question": question, "parsed": p, "answer": text.strip(), "data": data if p["intent"] != "chat" else None, "ai": ai}
