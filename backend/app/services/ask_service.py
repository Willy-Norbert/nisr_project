"""Question answering for the Ask page.

A question becomes a plan of one to three data queries. Each query is run against the processed survey tables and
the result is reduced to an ANALYSIS block of computed comparisons (ranks, gaps, changes, ratios, rankings). An LLM
plans the queries and writes the answer strictly from the retrieved numbers plus that analysis; without an LLM a
rule-based parser and templates answer instead. Either way every number in an answer comes from the data.
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

_NUMBER = re.compile(r"\d[\d,]*\.?\d*")

INTENTS = ["overview", "districts", "compare", "trend", "inputs", "gender", "scenario", "priorities", "profile",
           "chat", "out_of_scope"]
MAX_STEPS = 3

COMPARE_PRACTICES = ["improved_seed_pct", "inorganic_fertilizer_pct", "organic_fertilizer_pct", "irrigation_pct",
                     "anti_erosion_pct", "land_consolidation_pct", "extension_access_pct", "cooperative_member_pct"]

SCOPE_TOPICS = ("crop yields, production, improved seed, fertilizer, irrigation, erosion measures, extension, "
                "cooperative membership, women versus men, priority districts and what-if scenarios")

OUT_OF_SCOPE_TOPICS = [
    ("market prices or production costs", ["price", "prices", "cost", "costs", "profit", "profits", "revenue",
                                           "market", "markets", "sell", "selling", "export", "gdp", "income"]),
    ("weather or climate", ["weather", "rain", "rainfall", "climate", "temperature", "drought", "flood", "forecast"]),
    ("loans, credit or money", ["loan", "loans", "credit", "interest", "bank", "banks", "cash", "subsidy amount"]),
    ("farm machinery or input brands", ["tractor", "tractors", "machinery", "machine", "machines", "brand", "brands",
                                        "pesticide", "equipment"]),
    ("other countries", ["kenya", "uganda", "tanzania", "burundi", "congo", "kampala", "nairobi", "ethiopia"]),
    ("years after 2025", ["2026", "2027", "2028", "2029", "2030", "next year", "coming years"]),
]

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


def _find_districts(text: str) -> list[str]:
    """Every district named in the text, in the order the user wrote them."""
    found = []
    for district in store.district_provinces():
        index = text.find(district.lower())
        if index >= 0:
            found.append((index, district))
    return [district for _, district in sorted(found)]


def _find_district(text: str) -> str | None:
    districts = _find_districts(text)
    return districts[0] if districts else None


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


def _scope_message(subject: str | None = None) -> str:
    head = "I can only answer from the NISR agricultural surveys this app is built on. "
    if subject:
        head += f"Our data does not measure {subject}, so answering would mean inventing numbers. "
    else:
        head += "That question falls outside what our data measures. "
    return head + f"What the surveys do cover: {SCOPE_TOPICS}, for 2024 and 2025 Season A."


def _scope_refusal(question: str) -> str | None:
    """Refuse before any model call when the question asks for something the surveys do not measure."""
    text = question.lower()
    for topic, words in OUT_OF_SCOPE_TOPICS:
        if any(re.search(rf"\b{re.escape(word)}\b", text) for word in words):
            return _scope_message(topic)
    return None


def _best_period(areas: list[str], crop: str, year: int, season: str) -> tuple[int, str, bool]:
    """The latest period in which every named district actually has plots of this crop."""
    df = store.indicators()
    subset = df[(df["indicator_id"] == "yield_kg_ha") & (df["level"] == "district") & (df["crop"] == crop)]
    if subset.empty:
        return year, season, False

    def complete(period_year: int, period_season: str) -> bool:
        present = subset[(subset["year"] == period_year) & (subset["season"] == period_season)]
        have = {item.area for item in present.itertuples() if item.value == item.value}
        return all(area in have for area in areas)

    if complete(year, season):
        return year, season, False
    periods = (subset[["year", "season"]].drop_duplicates()
               .sort_values(["year", "season"], ascending=False).itertuples(index=False))
    for row in periods:
        if (int(row.year), str(row.season)) == (year, season):
            continue
        if complete(int(row.year), str(row.season)):
            return int(row.year), str(row.season), True
    return year, season, False


def _compare_data(areas: list[str], crop: str, year: int, season: str) -> dict:
    """Side-by-side picture of two or more districts: the crop's yield plus the practices we publish."""
    crop_name = ind.resolve_crop("yield_kg_ha", crop)
    year, season, moved = _best_period(areas, crop_name, year, season)
    ranked = comparison_service.districts("yield_kg_ha", year, season, crop_name)
    by_area = {row["area"]: row for row in ranked["districts"]}
    national = ranked.get("national_value")
    series = {key: {"id": key, "name": INDICATORS[key].name, "unit": INDICATORS[key].unit, "values": []}
              for key in COMPARE_PRACTICES if key in INDICATORS}
    rows = []
    for area in areas:
        profile = geography_service.profile(area, year, season)
        value = by_area.get(profile["district"], {})
        yield_value = value.get("value")
        practices = {item["indicator_id"]: item for item in profile["indicators"]}
        rows.append({
            "district": profile["district"],
            "province": profile["province"],
            "yield_kg_ha": yield_value,
            "national_yield": national,
            "vs_national_pct": (None if yield_value is None or not national
                                else round((yield_value / national - 1) * 100, 1)),
            "rank": value.get("rank"),
            "of": len(ranked["districts"]),
            "n": value.get("n"),
            "low_reliability": bool(value.get("low_reliability")),
            "practices": {key: (None if practices.get(key) is None else practices[key]["value"]) for key in series},
        })
        for key, item in series.items():
            item["values"].append(rows[-1]["practices"][key])
    return {"crop": ranked.get("crop") or crop, "year": year, "season": season, "period_note": moved,
            "districts": rows, "practice_series": list(series.values())}


def parse(question: str) -> dict:
    text = question.lower().strip()
    year, season = _period(text)
    crop = _find_crop(text)
    districts = _find_districts(text)
    district = districts[0] if districts else None
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
    elif len(districts) >= 2:
        intent = "compare"
    elif district and _has(text, ["compare", "versus", " vs ", "difference between"]):
        intent = "profile"
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
        "districts": districts,
        "year": year,
        "season": season,
        "inputs": inputs,
        "ascending": _has(text, ["lowest", "worst", "least", "poorest", "bottom"]),
    }


def _run(p: dict) -> tuple[str, dict | None]:
    """Run one query step; return a rough draft (the answer when no LLM is available) and the retrieved data."""
    intent, year, season = p["intent"], p["year"], p["season"]
    crop = p["crop"] or "Maize"

    if intent == "out_of_scope":
        data = None
        text = _scope_message(p.get("unknown"))
    elif intent == "compare":
        areas = p.get("districts") or ([p["district"]] if p.get("district") else [])
        data = _compare_data(areas, crop, year, season)
        kept = [r for r in data["districts"] if r["yield_kg_ha"] is not None]
        missing = [r["district"] for r in data["districts"] if r["yield_kg_ha"] is None]
        note = (" That is the latest season in which every district named has surveyed plots of this crop."
                if data.get("period_note") else "")
        if len(kept) >= 2:
            first, second = kept[0], kept[1]
            gap = first["yield_kg_ha"] - second["yield_kg_ha"]
            pct = round((first["yield_kg_ha"] / second["yield_kg_ha"] - 1) * 100, 1) if second["yield_kg_ha"] else None
            text = (f"{data['crop']} in {data['year']} Season {data['season']}: {first['district']} "
                    f"{first['yield_kg_ha']:,.0f} kg/ha against {second['district']} "
                    f"{second['yield_kg_ha']:,.0f} kg/ha ({gap:+,.0f} kg/ha"
                    + (f", {pct:+.1f}%)." if pct is not None else ").") + note)
        elif kept and missing:
            text = (f"{data['crop']} in {data['year']} Season {data['season']}: {kept[0]['district']} "
                    f"{kept[0]['yield_kg_ha']:,.0f} kg/ha. There are no surveyed {data['crop'].lower()} plots in "
                    f"{', '.join(missing)} for that season, so there is nothing to compare against there.")
        else:
            text = (f"No surveyed {data['crop'].lower()} plots for {', '.join(r['district'] for r in data['districts'])} "
                    f"in {data['year']} Season {data['season']}, so I cannot compare them.")
    elif intent == "chat":
        data = overview_service.overview(year, season)
        text = ("I'm Analiza's data assistant. Ask me about crop yields, inputs such as improved seed, fertilizer and "
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


# --- derived analysis ---------------------------------------------------------------------------------------------
# Everything a writer needs to explain what the numbers mean, computed here so the model never has to guess.


def _num(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _n(value, digits: int = 0) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def _sign(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:+.{digits}f}%"


def _change_pct(current, base) -> float | None:
    if current is None or not base:
        return None
    return round((current / base - 1) * 100, 1)


def _analyse_overview(data: dict) -> dict:
    crops = sorted([c for c in data.get("crops") or [] if _num(c.get("yield_kg_ha")) is not None],
                   key=lambda c: _num(c["yield_kg_ha"]), reverse=True)
    kpis = {k["indicator_id"]: k for k in data.get("kpis") or [] if k.get("indicator_id")}
    findings = []
    if crops:
        best, worst = crops[0], crops[-1]
        findings.append(f"{best['crop']} has the highest national yield at {_n(_num(best['yield_kg_ha']))} kg/ha; "
                        f"{worst['crop']} the lowest at {_n(_num(worst['yield_kg_ha']))} kg/ha.")
    for key in ("inorganic_fertilizer_pct", "improved_seed_pct", "irrigation_pct"):
        kpi = kpis.get(key)
        if kpi and _num(kpi.get("value")) is not None:
            change = _num(kpi.get("change"))
            suffix = f" ({_sign(change)} on the same season a year earlier)" if change is not None else ""
            findings.append(f"{kpi['name']}: {_n(_num(kpi['value']), 1)}% of plots{suffix}.")
    return {
        "figures": {"crop_yields": [{"crop": c["crop"], "yield_kg_ha": _num(c["yield_kg_ha"])} for c in crops],
                    "practices": {k: _num(v.get("value")) for k, v in kpis.items()}},
        "findings": findings,
    }


def _analyse_districts(p: dict, data: dict) -> dict:
    rows = [r for r in data.get("districts") or [] if _num(r.get("value")) is not None]
    if not rows:
        return {}
    definition = data.get("indicator") or {}
    unit = definition.get("unit", "")
    subject = definition.get("name", "value").lower()
    if data.get("crop") and data["crop"] != ind.ALL_CROPS:
        subject += f" for {data['crop'].lower()}"
    want_high = definition.get("higher_is_better", True)

    best, worst = rows[0], rows[-1]
    best_v, worst_v = _num(best["value"]), _num(worst["value"])
    national = _num(data.get("national_value"))
    spread = round(best_v - worst_v, 2) if best_v is not None and worst_v is not None else None
    figures = {
        "districts": len(rows),
        "higher_is_better": want_high,
        "wants": "lowest" if p.get("ascending") else "highest",
        "best": {"district": best.get("area"), "value": best_v, "rank": best.get("rank")},
        "worst": {"district": worst.get("area"), "value": worst_v, "rank": worst.get("rank")},
        "national": national,
        "spread": spread,
        "spread_pct_of_worst": round(spread / worst_v * 100, 1) if spread is not None and worst_v else None,
        "best_vs_national_pct": _change_pct(best_v, national),
        "worst_vs_national_pct": _change_pct(worst_v, national),
        "above_national": sum(1 for r in rows if national is not None and _num(r["value"]) > national),
        "below_national": sum(1 for r in rows if national is not None and _num(r["value"]) < national),
        "top5": [{"district": r["area"], "value": _num(r["value"])} for r in rows[:5]],
        "bottom5": [{"district": r["area"], "value": _num(r["value"])} for r in rows[-5:][::-1]],
        "low_reliability": [r["area"] for r in rows if r.get("low_reliability")],
    }

    findings = []
    high, low = ("highest", "lowest") if want_high else ("lowest", "highest")
    if p.get("ascending"):
        findings.append(f"The {low} {subject} is in {worst.get('area')} at {_n(worst_v, 1)} {unit}; "
                        f"the {high} is {best.get('area')} at {_n(best_v, 1)} {unit}.")
    else:
        findings.append(f"{best.get('area')} has the {high} {subject} at {_n(best_v, 1)} {unit}; "
                        f"{worst.get('area')} has the {low} at {_n(worst_v, 1)} {unit}.")
    if spread is not None and worst_v:
        findings.append(f"That is a gap of {_n(spread, 1)} {unit}: the leading district is about "
                        f"{best_v / worst_v:.1f} times the trailing one.")
    if national is not None:
        findings.append(f"{figures['above_national']} of {len(rows)} districts are above the national average of "
                        f"{_n(national, 1)} {unit}.")
    if figures["low_reliability"]:
        findings.append("These districts rest on fewer than 30 survey plots, so their averages are noisy: "
                        + ", ".join(figures["low_reliability"][:5]) + ".")
    return {"figures": figures, "findings": findings}


def _analyse_trend(data: dict) -> dict:
    series = [s for s in data.get("series") or [] if _num(s.get("value")) is not None]
    if not series:
        return {}
    definition = data.get("indicator") or {}
    unit = definition.get("unit", "")
    subject = definition.get("name", "value").lower()
    if data.get("crop") and data["crop"] != ind.ALL_CROPS:
        subject += f" for {data['crop'].lower()}"
    if data.get("area") and data.get("level") == "district":
        subject += f" in {data['area']}"

    first, last = series[0], series[-1]
    first_v, last_v = _num(first["value"]), _num(last["value"])
    change = round(last_v - first_v, 2)
    change_pct = _change_pct(last_v, first_v)
    peak = max(series, key=lambda s: _num(s["value"]))
    trough = min(series, key=lambda s: _num(s["value"]))
    latest = series[-2] if len(series) > 1 else None
    figures = {
        "periods": [s["period"] for s in series],
        "first": {"period": first["period"], "value": first_v},
        "last": {"period": last["period"], "value": last_v},
        "change": change,
        "change_pct": change_pct,
        "latest_change_pct": _change_pct(last_v, _num(latest["value"])) if latest else None,
        "peak": {"period": peak["period"], "value": _num(peak["value"])},
        "trough": {"period": trough["period"], "value": _num(trough["value"])},
        "series": [{"period": s["period"], "value": _num(s["value"])} for s in series],
    }

    verb = "rose" if change > 0 else "fell" if change < 0 else "was flat"
    findings = [f"{subject.capitalize()} {verb} from {_n(first_v, 1)} {unit} in {first['period']} to "
                f"{_n(last_v, 1)} {unit} in {last['period']} ({_sign(change_pct)}), a change of {_n(change, 1)} {unit}."]
    if latest:
        findings.append(f"The latest move, {latest['period']} to {last['period']}, was {_sign(figures['latest_change_pct'])}.")
    findings.append(f"The highest point was {peak['period']} ({_n(_num(peak['value']), 1)} {unit}) and the lowest "
                    f"{trough['period']} ({_n(_num(trough['value']), 1)} {unit}), across {len(series)} periods.")
    noisy = [s["period"] for s in series if s.get("low_reliability")]
    if noisy:
        findings.append("Thin samples (fewer than 30 plots) in: " + ", ".join(noisy) + ".")
    return {"figures": figures, "findings": findings}


def _analyse_inputs(p: dict, data: dict) -> dict:
    effects = [e for e in data.get("effects") or [] if _num(e.get("yield_with")) is not None]
    if not effects:
        return {}
    rows = [{
        "input": e.get("input"),
        "label": e.get("input_label") or str(e.get("input", "")).replace("_", " "),
        "yield_with": _num(e.get("yield_with")),
        "yield_without": _num(e.get("yield_without")),
        "premium_pct": _num(e.get("premium_pct")),
        "n_with": _num(e.get("n_with")),
        "n_without": _num(e.get("n_without")),
    } for e in effects]
    ranked = sorted(rows, key=lambda r: r["premium_pct"] if r["premium_pct"] is not None else -999, reverse=True)
    target = (p.get("inputs") or [None])[0]
    focus = next((r for r in rows if r["input"] == target), ranked[0])
    crop = data.get("crop", "crop")
    figures = {
        "crop": crop,
        "requested_input": target,
        "focus": focus,
        "effects": ranked,
        "best": ranked[0],
        "worst": ranked[-1],
        "positive_effects": sum(1 for r in rows if (r["premium_pct"] or 0) > 0),
    }

    findings = [f"{focus['label']}: plots using it averaged {_n(focus['yield_with'])} kg/ha of {crop.lower()} against "
                f"{_n(focus['yield_without'])} kg/ha without it ({_sign(focus['premium_pct'])})."]
    findings.append("All inputs for this crop, best to worst: "
                    + ", ".join(f"{r['label'].lower()} {_sign(r['premium_pct'])}" for r in ranked) + ".")
    if len(ranked) > 1:
        findings.append(f"{ranked[0]['label']} shows the biggest difference ({_sign(ranked[0]['premium_pct'])}), "
                        f"{ranked[-1]['label']} the smallest ({_sign(ranked[-1]['premium_pct'])}).")
    findings.append(f"{figures['positive_effects']} of {len(rows)} inputs are associated with higher yield; "
                    "these are comparisons of plots, not proof that the input caused the difference.")
    thin = [r["label"].lower() for r in rows if (r["n_with"] or 0) < 30]
    if thin:
        findings.append("Few plots use " + ", ".join(thin) + ", so those numbers are shaky.")
    return {"figures": figures, "findings": findings}


def _analyse_gender(p: dict, data: dict) -> dict:
    rows = [r for r in data.get("rows") or [] if _num(r.get("Female")) is not None and _num(r.get("Male")) is not None]
    if not rows:
        return {}
    crop = data.get("crop", "crop")
    national = next((r for r in rows if str(r.get("area", "")).lower() in ("rwanda", "national")), None)
    widest, narrowest = rows[0], rows[-1]  # already sorted from largest female disadvantage upwards
    figures = {
        "crop": crop,
        "national": None if national is None else {
            "female": _num(national.get("Female")), "male": _num(national.get("Male")),
            "gap_pct": _num(national.get("gap_pct"))},
        "widest_gap": {"area": widest.get("area"), "gap_pct": _num(widest.get("gap_pct"))},
        "smallest_gap": {"area": narrowest.get("area"), "gap_pct": _num(narrowest.get("gap_pct"))},
        "areas_with_female_below_male": sum(1 for r in rows if (_num(r.get("gap_pct")) or 0) < 0),
        "areas": len(rows),
        "mean_gap_pct": round(sum(_num(r.get("gap_pct")) or 0 for r in rows) / len(rows), 1),
    }

    findings = []
    if national:
        findings.append(f"Nationally, female-managed {crop.lower()} plots averaged "
                        f"{_n(_num(national.get('Female')))} kg/ha against {_n(_num(national.get('Male')))} kg/ha for "
                        f"male-managed plots ({_sign(_num(national.get('gap_pct')))}).")
    if len(rows) > 1:
        findings.append(f"Female-managed plots trail male-managed ones in {figures['areas_with_female_below_male']} of "
                        f"{figures['areas']} areas; the average gap is {_sign(figures['mean_gap_pct'])}.")
        findings.append(f"The widest gap is in {widest.get('area')} ({_sign(_num(widest.get('gap_pct')))}) and the "
                        f"narrowest in {narrowest.get('area')} ({_sign(_num(narrowest.get('gap_pct')))}).")
    elif national:
        n_female, n_male = _num(national.get("n_Female")), _num(national.get("n_Male"))
        if n_female and n_male:
            findings.append(f"The comparison rests on {_n(n_female)} female-managed and {_n(n_male)} male-managed "
                            "plot observations.")
    return {"figures": figures, "findings": findings}


def _analyse_scenario(data: dict) -> dict:
    current, scenario = _num(data.get("current_yield")), _num(data.get("scenario_yield"))
    if current is None or scenario is None:
        return {}
    change_pct = _num(data.get("change_pct"))
    singles = [s for s in data.get("single_input_effects") or [] if _num(s.get("change_pct")) is not None]
    singles = sorted(singles, key=lambda s: _num(s["change_pct"]), reverse=True)
    labels = {i["id"]: i["label"] for i in scenario_service.options()["inputs"]}
    adoption = {str(k): _num(v) for k, v in (data.get("current_adoption_pct") or {}).items()}
    figures = {
        "crop": data.get("crop"),
        "district": data.get("district"),
        "inputs": data.get("inputs"),
        "current": current,
        "scenario": scenario,
        "lift_kg_ha": round(scenario - current, 1),
        "change_pct": change_pct,
        "adoption_pct": adoption,
        "n_plots": data.get("n_plots"),
        "single_input_effects": [{"input": s.get("input"), "change_pct": _num(s.get("change_pct"))} for s in singles],
    }

    findings = [f"Modelled average {str(data.get('crop')).lower()} yield in {data.get('district')} moves from "
                f"{_n(current)} to {_n(scenario)} kg/ha ({_sign(change_pct)}), a lift of about "
                f"{_n(figures['lift_kg_ha'])} kg/ha."]
    if adoption:
        findings.append("Today " + ", ".join(f"{labels.get(k, k).lower()} is used on {_n(v)}% of the surveyed plots"
                                             for k, v in adoption.items()) + ".")
    if singles:
        findings.append("On its own, " + ", ".join(f"{labels.get(s.get('input'), s.get('input')).lower()} would give "
                                                   f"{_sign(_num(s.get('change_pct')))}" for s in singles) + ".")
    findings.append("This is a model estimate from survey associations, not a guaranteed outcome.")
    return {"figures": figures, "findings": findings}


def _analyse_priorities(data: dict) -> dict:
    rows = [r for r in data.get("districts") or [] if _num(r.get("yield_kg_ha")) is not None]
    if not rows:
        return {}
    crop = data.get("crop", "crop")
    benchmark = _num(data.get("benchmark_yield_kg_ha"))
    top = rows[:5]
    total_gain = sum(_num(r.get("additional_production_t")) or 0 for r in rows)
    figures = {
        "crop": crop,
        "benchmark_yield_kg_ha": benchmark,
        "top": [{"district": r.get("district"), "score": _num(r.get("score")), "yield_kg_ha": _num(r.get("yield_kg_ha")),
                 "potential_gain_pct": _num(r.get("potential_gain_pct")),
                 "improved_seed_pct": _num(r.get("improved_seed_pct")),
                 "inorganic_fertilizer_pct": _num(r.get("inorganic_fertilizer_pct")),
                 "extension_access_pct": _num(r.get("extension_access_pct")),
                 "additional_production_t": _num(r.get("additional_production_t"))} for r in top],
        "districts_scored": len(rows),
        "total_additional_production_t": round(total_gain),
    }

    first = top[0]
    findings = [f"{first.get('district')} ranks first for {str(crop).lower()} with a priority score of "
                f"{_n(_num(first.get('score')), 1)} out of 100."]
    if benchmark:
        gap = _change_pct(_num(first.get("yield_kg_ha")), benchmark)
        findings.append(f"Its yield of {_n(_num(first.get('yield_kg_ha')))} kg/ha is {_sign(gap)} against the "
                        f"{_n(benchmark)} kg/ha benchmark (the 90th-percentile district).")
    findings.append("Top five: " + ", ".join(f"{r.get('district')} ({_n(_num(r.get('score')), 1)})" for r in top) + ".")
    seed = sum(_num(r.get("improved_seed_pct")) or 0 for r in top) / len(top)
    fert = sum(_num(r.get("inorganic_fertilizer_pct")) or 0 for r in top) / len(top)
    findings.append(f"On average these five districts use improved seed on {_n(seed, 1)}% of plots and inorganic "
                    f"fertilizer on {_n(fert, 1)}%, which is where the model sees room to grow.")
    if total_gain:
        findings.append(f"Closing that gap across all districts would add roughly {_n(total_gain)} tonnes of "
                        f"{str(crop).lower()} per season at current planted area.")
    return {"figures": figures, "findings": findings}


def _analyse_profile(data: dict) -> dict:
    rows = data.get("indicators") or []
    district = data.get("district")
    if not rows:
        return {}
    scored = [r for r in rows if _num(r.get("value")) is not None]
    above = [r for r in scored if (_num(r.get("difference")) or 0) > 0]
    below = [r for r in scored if (_num(r.get("difference")) or 0) < 0]
    ranked = [r for r in scored if r.get("rank")]
    strongest = min(ranked, key=lambda r: r["rank"]) if ranked else None
    weakest = max(ranked, key=lambda r: r["rank"]) if ranked else None
    crops = sorted([c for c in data.get("crop_yields") or [] if _num(c.get("vs_national_pct")) is not None],
                   key=lambda c: _num(c["vs_national_pct"]), reverse=True)
    figures = {
        "district": district,
        "province": data.get("province"),
        "above_national": [{"name": r["name"], "value": _num(r["value"]), "difference": _num(r.get("difference"))}
                           for r in above],
        "below_national": [{"name": r["name"], "value": _num(r["value"]), "difference": _num(r.get("difference"))}
                           for r in below],
        "strongest": None if not strongest else {"name": strongest["name"], "rank": strongest.get("rank"),
                                                 "of": strongest.get("of")},
        "weakest": None if not weakest else {"name": weakest["name"], "rank": weakest.get("rank"), "of": weakest.get("of")},
        "crops": [{"crop": c["crop"], "yield_kg_ha": _num(c["value"]),
                   "vs_national_pct": _num(c["vs_national_pct"])} for c in crops],
    }

    findings = []
    better = [r["name"].lower() for r in above[:4]]
    worse = [r["name"].lower() for r in below[:4]]
    findings.append(f"{district} is above the national average on {', '.join(better) if better else 'nothing'}"
                    + (f" and below on {', '.join(worse)}." if worse else "."))
    if strongest and weakest:
        findings.append(f"Its strongest indicator is {strongest['name'].lower()} (rank {strongest['rank']} of "
                        f"{strongest.get('of')}); the weakest is {weakest['name'].lower()} (rank {weakest['rank']}).")
    if crops:
        best, worst = crops[0], crops[-1]
        findings.append(f"Its best crop relative to the national average is {best['crop'].lower()} at "
                        f"{_n(_num(best['value']))} kg/ha ({_sign(_num(best.get('vs_national_pct')))}); the weakest is "
                        f"{worst['crop'].lower()} ({_sign(_num(worst.get('vs_national_pct')))}).")
    return {"figures": figures, "findings": findings}


def _analyse_compare(p: dict, data: dict) -> dict:
    rows = [r for r in data.get("districts") or [] if _num(r.get("yield_kg_ha")) is not None]
    if len(rows) < 2:
        return {}
    crop = str(data.get("crop") or "crop")
    first, second = rows[0], rows[1]
    va, vb = _num(first["yield_kg_ha"]), _num(second["yield_kg_ha"])
    gap = round(va - vb, 1)
    gap_pct = _change_pct(va, vb)
    lead, trail = (first, second) if va >= vb else (second, first)

    practices = []
    for item in data.get("practice_series") or []:
        left, right = _num(item["values"][0]), _num(item["values"][1])
        if left is None or right is None:
            continue
        practices.append({"name": item["name"], "unit": item["unit"], "first": left, "second": right,
                          "diff": round(left - right, 1),
                          "leader": first["district"] if left >= right else second["district"]})

    figures = {
        "crop": crop,
        "year": data.get("year"),
        "season": data.get("season"),
        "districts": [{"district": r["district"], "yield_kg_ha": _num(r["yield_kg_ha"]), "rank": r.get("rank"),
                       "of": r.get("of"), "vs_national_pct": _num(r.get("vs_national_pct"))} for r in rows],
        "yield_gap": abs(gap),
        "yield_gap_pct": gap_pct,
        "leader": lead["district"],
        "trailing": trail["district"],
        "practices": practices,
        "leads": {first["district"]: sum(1 for x in practices if x["leader"] == first["district"]),
                  second["district"]: sum(1 for x in practices if x["leader"] == second["district"])},
    }

    findings = [f"{lead['district']} yields {_n(_num(lead['yield_kg_ha']))} kg/ha of {crop.lower()} against "
                f"{_n(_num(trail['yield_kg_ha']))} kg/ha in {trail['district']} ({_sign(gap_pct)}, a difference of "
                f"{_n(abs(gap))} kg/ha) in {data.get('year')} Season {data.get('season')}."]
    if first.get("rank") and second.get("rank"):
        findings.append(f"They rank {first['rank']} and {second['rank']} of {first.get('of')} districts for this crop.")
    if practices:
        widest = max(practices, key=lambda x: abs(x["diff"]))
        findings.append(f"{first['district']} leads on {figures['leads'][first['district']]} of {len(practices)} "
                        f"practices, {second['district']} on {figures['leads'][second['district']]}.")
        findings.append(f"The widest practice gap is {widest['name'].lower()}: {_n(widest['first'], 1)}% in "
                        f"{first['district']} against {_n(widest['second'], 1)}% in {second['district']}.")
    national = _num(first.get("national_yield"))
    if national and first.get("vs_national_pct") is not None and second.get("vs_national_pct") is not None:
        findings.append(f"Against the national average of {_n(national)} kg/ha, {first['district']} is "
                        f"{_sign(_num(first.get('vs_national_pct')))} and {second['district']} "
                        f"{_sign(_num(second.get('vs_national_pct')))}.")
    return {"figures": figures, "findings": findings}


def _analyse(p: dict, data: dict | None) -> dict:
    if not data:
        return {}
    try:
        if p["intent"] in ("chat", "overview"):
            return _analyse_overview(data)
        if p["intent"] == "districts":
            return _analyse_districts(p, data)
        if p["intent"] == "compare":
            return _analyse_compare(p, data)
        if p["intent"] == "trend":
            return _analyse_trend(data)
        if p["intent"] == "inputs":
            return _analyse_inputs(p, data)
        if p["intent"] == "gender":
            return _analyse_gender(p, data)
        if p["intent"] == "scenario":
            return _analyse_scenario(data)
        if p["intent"] == "priorities":
            return _analyse_priorities(data)
        if p["intent"] == "profile":
            return _analyse_profile(data)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        logger.warning("Could not derive analysis for %s", p.get("intent"), exc_info=True)
    return {}


# --- planning -----------------------------------------------------------------------------------------------------


def _label(p: dict) -> str:
    definition = INDICATORS.get(p.get("indicator_id") or "")
    parts = [p["intent"], definition.name if definition else None, p.get("crop"), p.get("district")]
    return " · ".join(str(x) for x in parts if x)


def _public(p: dict) -> dict:
    return {k: p.get(k) for k in ("intent", "indicator_id", "crop", "district", "districts", "year", "season", "inputs",
                                  "ascending")}


def _plan_prompt() -> str:
    year, season = ind.latest_period()
    indicators = "\n".join(
        f"- {i.id}: {i.name} ({i.unit}){' [per crop]' if i.crop_specific else ''}" for i in INDICATORS.values())
    return f"""You plan the data work for Analiza, an agricultural statistics assistant built on NISR surveys
(Seasonal Agricultural Survey 2024-2025, seasons A/B/C; Agriculture Household Survey 2024).
Read the conversation and the LATEST question, then return ONE JSON object:
{{"focus": "one sentence restating exactly what the user wants answered, in their words",
 "steps": [{{"label": "what this step finds out",
            "intent": one of {INTENTS},
            "indicator_id": indicator id or null,
            "crop": crop name from the list or null,
            "district": district name from the list or null,
            "districts": [district names] when the user compares several places,
            "year": 2024 or 2025 or null,
            "season": "A", "B", "C" or null,
            "inputs": list from ["improved_seed","inorganic_fertilizer","organic_fertilizer","irrigated"],
            "ascending": true when the user wants the lowest/worst values}}],
 "answer_plan": ["the point the answer must make, in order"]}}

How many steps:
- ONE step when the question asks for one thing ("which districts...", "does seed raise yield").
- TWO or THREE steps only when the question really has several parts or one measure cannot answer it
  ("compare maize and beans", "why is Huye behind", "yield trend and does seed explain it"). Each extra step must
  add a different measure, crop, district or period. Never repeat the same query twice.
- Never invent a place or a crop. If the user names one outside the lists below, use out_of_scope.

Intents:
- overview: Rwanda's agriculture as a whole ("tell me about Rwanda", "give me a summary")
- districts: rank or compare districts on an indicator ("which districts...", "where is ... highest/lowest")
- trend: change across seasons/years, nationally or for one district
- inputs: whether/how much an input (seed, fertilizer, irrigation) raises yield
- gender: female vs male farmers
- scenario: what-if adoption of inputs in a district (model simulation)
- priorities: where support or investment should go
- compare: the user names two or more districts and wants them side by side ("compare Musanze and Nyagatare")
- profile: anything about one district in general
- chat: greetings or questions about Analiza/methods that need no numbers
- out_of_scope: the question needs something these surveys do not measure (prices, costs, weather, forecasts,
  machinery, other countries, years after 2025). Put what is missing in "label".

Rules:
- focus must state the actual question, not the topic.
- Resolve follow-ups from the conversation ("and in Huye?" keeps the previous crop and intent).
- Map crop synonyms: beans -> Bush bean, potato -> Irish potato, rice -> Paddy rice, banana -> Cooking banana.
- Default period when not stated: {year} Season {season}.
- answer_plan lists 1-4 points; the first must be the direct answer.

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
    crop_raw = str(raw.get("crop") or "").strip()
    p["crop"] = (crops.get(crop_raw.lower()) or CROP_SYNONYMS.get(crop_raw.lower())
                 or (fallback["crop"] if crop_raw else None))
    if crop_raw and p["crop"] is None:
        p["intent"], p["unknown"] = "out_of_scope", crop_raw

    named = [str(x).strip() for x in raw.get("districts") or [] if str(x).strip()]
    if raw.get("district"):
        named.insert(0, str(raw["district"]).strip())
    resolved: list[str] = []
    for name in named:
        match = districts.get(name.lower())
        if match is None:
            p["intent"], p["unknown"] = "out_of_scope", name
            continue
        if match not in resolved:
            resolved.append(match)
    p["districts"] = resolved
    p["district"] = resolved[0] if resolved else None
    p["year"] = raw["year"] if raw.get("year") in (2024, 2025) else year
    p["season"] = raw["season"] if raw.get("season") in ("A", "B", "C") else season
    p["inputs"] = [i for i in raw.get("inputs") or [] if i in INPUT_INDICATORS]
    p["ascending"] = bool(raw.get("ascending"))
    if p["intent"] == "inputs":
        p["inputs"] = p["inputs"] or ["improved_seed"]
        p["indicator_id"] = INPUT_INDICATORS[p["inputs"][0]]
    if p["intent"] == "compare" and len(p["districts"]) < 2:
        p["intent"] = "profile" if p["districts"] else "districts"
    if p["intent"] == "profile" and not p["district"]:
        p["intent"] = "districts"
    return p


def _plan_from(raw: dict, fallback: dict) -> dict:
    steps: list[dict] = []
    seen: set[tuple] = set()
    for item in raw.get("steps") or []:
        if not isinstance(item, dict) or len(steps) >= MAX_STEPS:
            continue
        step = _validate(item, fallback)
        key = (step["intent"], step["indicator_id"], step["crop"], step["district"], step["year"], step["season"],
               tuple(step["inputs"]))
        if key in seen:
            continue
        seen.add(key)
        step["label"] = str(item.get("label") or _label(step))[:160]
        steps.append(step)
    side_by_side = [s for s in steps if s["intent"] in ("profile", "districts") and len(s.get("districts") or []) == 1]
    if len(side_by_side) >= 2:
        merged = {**side_by_side[0], "intent": "compare",
                  "districts": [s["districts"][0] for s in side_by_side],
                  "district": side_by_side[0]["districts"][0],
                  "label": "Side-by-side comparison of " + ", ".join(s["districts"][0] for s in side_by_side)}
        steps = [merged] + [s for s in steps if s not in side_by_side]
    if not steps:
        steps = [{**fallback, "label": _label(fallback)}]
    focus = str(raw.get("focus") or "").strip()[:400]
    answer_plan = [str(x).strip()[:200] for x in raw.get("answer_plan") or [] if str(x).strip()][:4]
    return {"focus": focus, "steps": steps, "answer_plan": answer_plan}


# --- writer input -------------------------------------------------------------------------------------------------


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


def _trim(value, keep: int):
    if isinstance(value, dict):
        return {k: _trim(v, keep) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim(v, keep) for v in (value[:keep] if keep else [])]
    return value


def _payload(obj: dict, limit: int = 24000) -> str:
    """Serialise the writer input, shrinking rows instead of cutting the JSON mid-string."""
    text = json.dumps(obj, default=str)
    for keep in (8, 4, 0):
        if len(text) <= limit:
            return text
        for item in obj["results"]:
            item["data"] = _trim(item.get("data"), keep)
        text = json.dumps(obj, default=str)
    for item in obj["results"]:
        item.pop("data", None)
        item.pop("draft", None)
    text = json.dumps(obj, default=str)
    if len(text) > limit:
        obj["results"] = obj["results"][:1]
        obj["results"][0].pop("analysis", None)
        text = json.dumps(obj, default=str)
    return text


def _writer_input(question: str, plan: dict, results: list[dict]) -> dict:
    year, season = ind.latest_period()
    return {
        "latest_period": f"{year} Season {season}",
        "focus": plan.get("focus") or question,
        "answer_plan": plan.get("answer_plan") or [],
        "results": [{
            "step": i + 1,
            "purpose": r["step"].get("label"),
            "query": _public(r["step"]),
            "analysis": r["analysis"],
            "data": _facts(r["step"], r["data"]),
            "draft": r["draft"],
        } for i, r in enumerate(results)],
    }


WRITER_PROMPT = """You are Analiza's agricultural data analyst. You receive LATEST QUESTION, FOCUS (what the user
wants answered), PLAN and up to three RESULTS. Each result holds the QUERY that was run, DATA retrieved from NISR
surveys, an ANALYSIS block of comparisons already computed for you (ranks, gaps, changes, ratios, adoption rates)
and a rough DRAFT.

How to answer:
1. First sentence: answer FOCUS directly with the number, ranking or yes/no the user asked for.
2. Answer every part of the question, in the order it was asked. If it names two crops, two districts or a yield
   and an input, cover both.
3. Use ANALYSIS to explain what the numbers mean (how big the gap is, who is behind, what changed and by how much).
   Do not just restate a list of figures.
4. Every number must come from DATA or ANALYSIS. Never invent, extrapolate or estimate a number that is not there;
   if something is missing, say what is missing.
5. Answer the LATEST QUESTION, not an earlier one from the conversation. Never answer a topic that was not asked.
6. State the period (year and season) and name the crop or district the numbers refer to.
7. COMPARISONS: when RESULTS cover two or more districts, answer for BOTH named places side by side - each one's
   number, then the difference both in absolute terms and in %. Never answer only the first place, and never list
   other districts instead.
8. If the question needs something DATA and ANALYSIS do not contain (prices, costs, weather, forecasts, machinery,
   other countries, years after 2025, a measure we do not publish), refuse in one or two sentences: say plainly
   that the surveys do not cover it and name what you can answer instead. A refusal carries NO statistics, no other
   crops and no other findings.

Style: clear, friendly, plain English (reply in Kinyarwanda or French if the user writes in it); 3-6 short
sentences or "- " bullets; kg/ha to whole numbers, percentages to one decimal; end with one practical sentence for
a planner when it follows from the data. Input differences and model scenarios are associations, not proven causal
effects. No headings, no tables, no markdown other than "- " bullets and **bold**."""


def _fallback(results: list[dict]) -> str:
    """Answer without an LLM: the rule-based draft plus the one computed comparison that adds new numbers."""
    parts = []
    for r in results:
        draft = (r.get("draft") or "").strip()
        if r["step"].get("intent") in ("chat", "out_of_scope"):
            parts.append(draft)
            continue
        known = set(_NUMBER.findall(draft))
        findings = (r.get("analysis") or {}).get("findings") or []
        scored = [(len(set(_NUMBER.findall(f)) - known), f) for f in findings if f]
        fresh = max(scored, key=lambda s: s[0])[1] if scored and max(s[0] for s in scored) > 0 else ""
        parts.append(f"{draft} {fresh}".strip() if fresh else draft)
    return "\n\n".join(p for p in parts if p)


def answer(question: str, history: list[dict] | None = None) -> dict:
    history = [m for m in (history or []) if m.get("role") in ("user", "assistant") and m.get("content")][-8:]

    refusal = _scope_refusal(question)
    if refusal:
        year, season = ind.latest_period()
        return {"question": question,
                "parsed": {"intent": "out_of_scope", "indicator_id": None, "crop": None, "district": None,
                           "districts": [], "year": year, "season": season, "inputs": [], "ascending": False},
                "steps": [], "focus": question, "answer": refusal, "data": None, "analysis": {}, "ai": False}

    rule = parse(question)
    plan = {"focus": question.strip(), "steps": [{**rule, "label": _label(rule)}], "answer_plan": []}
    ai = False

    if llm_service.enabled():
        try:
            raw = llm_service.chat_json([{"role": "system", "content": _plan_prompt()}, *history,
                                         {"role": "user", "content": question}])
            plan = _plan_from(raw, rule)
            ai = True
        except llm_service.LLMError:
            pass

    results: list[dict] = []
    for i, step in enumerate(plan["steps"]):
        try:
            draft, data = _run(step)
            analysis = _analyse(step, data)
        except ind.NotFoundError as exc:
            draft, data, analysis = f"I couldn't find data for that: {exc}.", None, {}
            if i == 0:
                step = {**step, "intent": "chat"}
        except Exception:  # a failed side step must not break the answer
            if i == 0:
                raise
            logger.warning("Ask step failed: %s", step, exc_info=True)
            continue
        results.append({"step": step, "draft": draft, "data": data, "analysis": analysis})

    plan["steps"] = [r["step"] for r in results] or plan["steps"]
    text = _fallback(results)

    if ai:
        payload = _payload(_writer_input(question, plan, results))
        try:
            written = llm_service.chat(
                [{"role": "system", "content": WRITER_PROMPT}, *history,
                 {"role": "user", "content": f"LATEST QUESTION: {question}\n\nANALYSIS_DATA:\n{payload}"}],
                temperature=0.3,
            )
            text = written.strip() or text
        except llm_service.LLMError:
            ai = False

    first = results[0] if results else {"data": None, "analysis": {}}
    return {
        "question": question,
        "parsed": plan["steps"][0],
        "steps": [{**_public(r["step"]), "label": r["step"].get("label")} for r in results],
        "focus": plan.get("focus") or question,
        "answer": text.strip(),
        "data": None if plan["steps"][0]["intent"] == "chat" else first["data"],
        "analysis": first["analysis"],
        "ai": ai,
    }
