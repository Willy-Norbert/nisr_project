"""Findings generated from the processed tables, so every number shown is traceable to the data."""

from functools import lru_cache

import numpy as np

from app.data import store
from app.services import comparison_service, indicator_service as ind


STAPLE_CROPS = ["Maize", "Bush bean", "Climbing bean", "Irish potato", "Cassava", "Paddy rice", "Sorghum", "Sweet potato", "Soybean"]


def _fmt(v: float, digits: int = 0) -> str:
    return f"{v:,.{digits}f}"


def _yield_trend(year: int, season: str) -> dict | None:
    rows = []
    for crop in ["Maize", "Bush bean", "Irish potato", "Cassava", "Paddy rice", "Sorghum"]:
        cur = ind.value("yield_kg_ha", year, season, crop, "national", "Rwanda")
        prev = ind.value("yield_kg_ha", year - 1, season, crop, "national", "Rwanda")
        if cur and prev:
            rows.append({"crop": crop, "previous": prev, "current": cur, "change_pct": round((cur / prev - 1) * 100, 1)})
    if not rows:
        return None
    best = max(rows, key=lambda r: r["change_pct"])
    worst = min(rows, key=lambda r: r["change_pct"])
    return {
        "id": "yield-trend",
        "topic": "production",
        "title": f"Season {season} yields: {best['crop']} up {best['change_pct']}% from {year - 1} to {year}",
        "summary": f"National {best['crop'].lower()} yield moved from {_fmt(best['previous'])} to {_fmt(best['current'])} kg/ha. "
        f"The weakest change was {worst['crop'].lower()} ({worst['change_pct']:+}%).",
        "chart": "bar",
        "evidence": rows,
        "action": "Investigate what drove the strongest gains (weather, inputs, programmes) and replicate them for lagging crops.",
    }


def _seed_premium(year: int, season: str) -> dict | None:
    df = store.input_effects()
    df = df[(df["year"] == year) & (df["season"] == season) & (df["input"] == "improved_seed") & (df["n_with"] >= 30)
            & df["crop"].isin(STAPLE_CROPS)]
    if df.empty:
        return None
    df = df.sort_values("premium_pct", ascending=False)
    top = df.iloc[0]
    adoption = ind.value("improved_seed_pct", year, season, top["crop"], "national", "Rwanda")
    return {
        "id": "seed-premium",
        "topic": "inputs",
        "title": f"Improved seed plots yield {top['premium_pct']:.0f}% more for {top['crop'].lower()}",
        "summary": f"{top['crop']} plots with improved seed averaged {_fmt(top['yield_with'])} kg/ha vs {_fmt(top['yield_without'])} "
        f"kg/ha without, yet only {adoption:.0f}% of {top['crop'].lower()} plots used improved seed in {year} Season {season}."
        if adoption is not None else "",
        "chart": "bar",
        "evidence": store.records(df[["crop", "yield_with", "yield_without", "premium_pct", "n_with", "n_without"]]),
        "action": "Expand access to certified seed (agro-dealer networks, Smart Nkunganire subsidy) for crops with the largest premium.",
    }


def _fertilizer_premium(year: int, season: str) -> dict | None:
    df = store.input_effects()
    df = df[(df["year"] == year) & (df["season"] == season) & (df["input"] == "inorganic_fertilizer") & (df["n_with"] >= 30)
            & df["crop"].isin(STAPLE_CROPS)]
    if df.empty:
        return None
    df = df.sort_values("premium_pct", ascending=False)
    top = df.iloc[0]
    return {
        "id": "fertilizer-premium",
        "topic": "inputs",
        "title": f"Fertilized {top['crop'].lower()} plots yield {top['premium_pct']:.0f}% more",
        "summary": f"In {year} Season {season}, {top['crop'].lower()} plots using inorganic fertilizer reached {_fmt(top['yield_with'])} kg/ha "
        f"compared with {_fmt(top['yield_without'])} kg/ha without.",
        "chart": "bar",
        "evidence": store.records(df[["crop", "yield_with", "yield_without", "premium_pct", "n_with", "n_without"]]),
        "action": "Prioritise fertilizer subsidies and soil-testing advice for the crops with the strongest response.",
    }


def _district_spread(year: int, season: str) -> dict | None:
    data = comparison_service.districts("yield_kg_ha", year, season, "Maize")
    rows = [r for r in data["districts"] if not r["low_reliability"]]
    if len(rows) < 4:
        return None
    top, bottom = rows[0], rows[-1]
    return {
        "id": "district-spread",
        "topic": "geography",
        "title": f"Maize yields in {top['area']} are {top['value'] / bottom['value']:.1f}x those in {bottom['area']}",
        "summary": f"In {year} Season {season}, district maize yields ranged from {_fmt(bottom['value'])} kg/ha ({bottom['area']}) "
        f"to {_fmt(top['value'])} kg/ha ({top['area']}); the national figure was {_fmt(data['national_value'])} kg/ha.",
        "chart": "map",
        "evidence": rows,
        "action": "Use the Priorities page to target districts with large yield gaps and high potential gains.",
    }


def _gender_gap(year: int, season: str) -> dict | None:
    data = comparison_service.gender(year, season, "Maize", "national")
    if not data["rows"] or "gap_pct" not in data["rows"][0]:
        return None
    r = data["rows"][0]
    direction = "lower" if r["gap_pct"] < 0 else "higher"
    return {
        "id": "gender-gap",
        "topic": "inclusion",
        "title": f"Female-managed maize plots yield {abs(r['gap_pct']):.0f}% {direction} than male-managed plots",
        "summary": f"Small-scale female farmers averaged {_fmt(r['Female'])} kg/ha of maize vs {_fmt(r['Male'])} kg/ha for male farmers "
        f"in {year} Season {season}.",
        "chart": "bar",
        "evidence": data["rows"],
        "action": "Target extension, credit and input packages at women farmers to close the productivity gap.",
    }


def _irrigation(year: int) -> dict | None:
    rows = []
    for season in ["A", "B", "C"]:
        v = ind.value("irrigation_pct", year, season, None, "national", "Rwanda")
        if v is not None:
            rows.append({"season": season, "value": v})
    if len(rows) < 2:
        return None
    a = next((r["value"] for r in rows if r["season"] == "A"), None)
    c = next((r["value"] for r in rows if r["season"] == "C"), None)
    return {
        "id": "irrigation",
        "topic": "practices",
        "title": f"Irrigation reaches only {a:.1f}% of plots in Season A" if a is not None else "Irrigation by season",
        "summary": f"Irrigation is concentrated in the dry Season C ({c:.0f}% of plots, mostly marshlands) while main-season plots "
        f"remain rain-fed ({year})." if c is not None else "",
        "chart": "bar",
        "evidence": rows,
        "action": "Expand small-scale irrigation on hillsides to reduce dependence on rainfall in Seasons A and B (NST2 climate resilience).",
    }


def _extension_link(year: int, season: str) -> dict | None:
    ext = ind.query("extension_access_pct", level="district").set_index("area")["value"]
    fert = ind.query("inorganic_fertilizer_pct", year, season, None, level="district").set_index("area")["value"]
    joined = ext.to_frame("extension").join(fert.to_frame("fertilizer"), how="inner")
    if len(joined) < 10:
        return None
    r = float(np.corrcoef(joined["extension"], joined["fertilizer"])[0, 1])
    if abs(r) >= 0.3:
        title = f"Districts with more extension access use {'more' if r > 0 else 'less'} fertilizer (r = {r:.2f})"
        summary = (f"Across {len(joined)} districts there is a {'strong' if abs(r) >= 0.5 else 'moderate'} correlation between "
                   "household extension access (AHS 2024) and plot-level fertilizer use (SAS).")
        action = "Strengthen extension services (Twigire Muhinzi, farmer field schools) where both access and input use are low."
    else:
        title = f"Extension access alone does not explain fertilizer use (r = {r:.2f})"
        summary = (f"Across {len(joined)} districts, household extension access (AHS 2024) is barely related to plot-level "
                   "fertilizer use (SAS): advice reaches farmers, but other barriers such as price, availability or credit "
                   "appear to limit adoption.")
        action = "Pair extension advice with access measures: input subsidies, agro-dealer coverage and seasonal credit."
    return {
        "id": "extension-link",
        "topic": "support",
        "title": title,
        "summary": summary,
        "chart": "scatter",
        "evidence": store.records(joined.reset_index(names="district").round(1)),
        "action": action,
    }


def _model_potential(year: int, season: str) -> dict | None:
    sc = store.scenarios()
    sc = sc[(sc["year"] == year) & (sc["season"] == season) & (sc["crop"] == "Maize")
            & (sc["inputs"] == "improved_seed+inorganic_fertilizer")].sort_values("change_pct", ascending=False)
    if sc.empty:
        return None
    top = sc.head(5)
    return {
        "id": "model-potential",
        "topic": "opportunity",
        "title": f"Seed + fertilizer could lift maize yields by up to {top['change_pct'].iloc[0]:.0f}% in {top['district'].iloc[0]}",
        "summary": "FarmGap's yield model estimates the gain if every surveyed maize plot used improved seed and inorganic fertilizer. "
        f"The largest estimated gains are in {', '.join(top['district'])}.",
        "chart": "bar",
        "evidence": store.records(sc[["district", "predicted_yield", "change_pct", "current_improved_seed_pct", "current_inorganic_fertilizer_pct"]]),
        "action": "Use the Scenario simulator to explore packages per district and crop.",
    }


@lru_cache
def all_insights() -> list[dict]:
    year, season = ind.latest_period()
    builders = [
        lambda: _yield_trend(year, season),
        lambda: _seed_premium(year, season),
        lambda: _fertilizer_premium(year, season),
        lambda: _district_spread(year, season),
        lambda: _model_potential(year, season),
        lambda: _gender_gap(year, season),
        lambda: _extension_link(year, season),
        lambda: _irrigation(year),
    ]
    out = []
    for build in builders:
        insight = build()
        if insight:
            insight["period"] = f"{year} Season {season}"
            out.append(insight)
    return out


def get(insight_id: str) -> dict:
    for insight in all_insights():
        if insight["id"] == insight_id:
            return insight
    raise ind.NotFoundError(f"Unknown insight '{insight_id}'")
