"""Ask the data: Analiza's own question-answering engine. No external AI service is used.

Pipeline for every question:
1. entities.extract    finds crops, districts, provinces, measure, inputs, year and season (typo-tolerant, EN/RW/FR)
                       and masks them (CROPX, DISTX...) so the classifier sees only the phrasing
2. intent_model        TF-IDF + logistic regression (scikit-learn) picks one of 19 question types
3. _resolve            sanity rules on top of the model (e.g. two districts named -> comparison), follow-ups,
                       defaults that are always stated in the answer
4. handlers            read the survey-weighted NISR tables and write the answer from templates, so every number
                       in an answer comes from the data; each answer carries maps/charts as "visuals"

Fairness safeguards: same crop and same period in every comparison, season-to-season changes compared like with like
(Season A with Season A), results on fewer than 30 observations flagged, cells under 10 already suppressed upstream,
and the period used is always named. When the requested period has no data for a place, the nearest period that does
is used and the answer says so.
"""

import logging

from app.analytics.definitions import INDICATORS, INPUT_COLUMNS, LOW_RELIABILITY_N
from app.data import store
from app.nlp import entities as ent
from app.nlp import intent_model
from app.nlp.training_data import INTENTS
from app.services import (
    comparison_service,
    geography_service,
    indicator_service as ind,
    overview_service,
    priority_service,
    scenario_service,
)

logger = logging.getLogger(__name__)

ALL = ind.ALL_CROPS
PRACTICES = ["improved_seed_pct", "inorganic_fertilizer_pct", "organic_fertilizer_pct", "irrigation_pct",
             "anti_erosion_pct", "land_consolidation_pct"]
HOUSEHOLD = ["extension_access_pct", "cooperative_member_pct"]
PERIODS = [(2025, "A"), (2025, "B"), (2024, "A"), (2024, "B"), (2025, "C"), (2024, "C")]
CONFIDENT = 0.35
CROP_INDICATORS = {"yield_kg_ha", "production_t"}
CHART_LABEL = {"improved_seed_pct": "Improved seed", "inorganic_fertilizer_pct": "Inorganic fert.",
               "organic_fertilizer_pct": "Organic fert.", "irrigation_pct": "Irrigation",
               "anti_erosion_pct": "Anti-erosion", "land_consolidation_pct": "Land consol.",
               "extension_access_pct": "Extension", "cooperative_member_pct": "Cooperative"}
INPUT_TO_INDICATOR = {"improved_seed": "improved_seed_pct", "inorganic_fertilizer": "inorganic_fertilizer_pct",
                      "organic_fertilizer": "organic_fertilizer_pct", "irrigated": "irrigation_pct"}

SUGGESTIONS = [
    "Which districts have the highest maize yield?",
    "How is maize grown in Musanze?",
    "Compare beans in Musanze and Nyabihu",
    "Why is Musanze behind Nyagatare in maize?",
    "How has Irish potato yield changed across seasons?",
    "Does improved seed increase maize yield?",
    "What if farmers in Nyagatare used improved seed and fertilizer for maize?",
    "Where should support be prioritised for beans?",
    "Which crops grow best in Huye?",
    "Compare women and men farmers' maize yields",
]


class Clarify(Exception):
    """The question is missing something we cannot sensibly assume; ask the user, with clickable options."""

    def __init__(self, text: str, options: list[str]):
        super().__init__(text)
        self.text, self.options = text, options


# --- data helpers -------------------------------------------------------------------------------------------------


def _household(indicator_id: str) -> bool:
    return ind.is_household(indicator_id)


def _crop_key(indicator_id: str, crop: str | None) -> str:
    if _household(indicator_id):
        return ALL
    return crop or ALL


def cell(indicator_id: str, crop: str | None, year: int | None, season: str | None, level: str,
         area: str) -> dict | None:
    """One published value with its sample size, or None (no plots / suppressed)."""
    df = store.indicators()
    df = df[(df["indicator_id"] == indicator_id) & (df["crop"] == _crop_key(indicator_id, crop))
            & (df["level"] == level) & (df["area"].str.lower() == area.lower())]
    if not _household(indicator_id):
        df = df[(df["year"] == year) & (df["season"] == season)]
    df = df[df["value"].notna()]
    if df.empty:
        return None
    row = df.iloc[0]
    return {"value": float(row["value"]), "n": int(row["n"]), "low": int(row["n"]) < LOW_RELIABILITY_N}


def nat(indicator_id: str, crop: str | None, year: int | None, season: str | None) -> dict | None:
    return cell(indicator_id, crop, year, season, "national", "Rwanda")


def rank_of(indicator_id: str, crop: str | None, year: int, season: str, district: str) -> tuple[int | None, int]:
    df = ind.query(indicator_id, None if _household(indicator_id) else year,
                   None if _household(indicator_id) else season, _crop_key(indicator_id, crop), level="district")
    df = df[df["value"].notna()].sort_values("value", ascending=not INDICATORS[indicator_id].higher_is_better)
    areas = list(df["area"])
    return (areas.index(district) + 1 if district in areas else None), len(areas)


def pick_period(indicator_id: str, crop: str | None, places: list[tuple[str, str]], year: int | None,
                season: str | None) -> tuple[int, str, str | None]:
    """The asked period if every place has data there, otherwise the most recent period that does (with a note)."""
    if _household(indicator_id):
        return 2024, "A", None
    wanted = (year or PERIODS[0][0], season or PERIODS[0][1])
    order = [wanted] + [p for p in PERIODS if p != wanted]
    if year and not season:
        order = [p for p in order if p[0] == year] + [p for p in order if p[0] != year]
    places = places or [("national", "Rwanda")]
    for y, s in order:
        if all(cell(indicator_id, crop, y, s, level, area) for level, area in places):
            if (y, s) == wanted:
                return y, s, None
            asked = f"{wanted[0]} Season {wanted[1]}" if (year or season) else "the latest season (2025 Season A)"
            return y, s, (f"There were too few surveyed plots for {asked}, so this uses **{y} Season {s}**, the most "
                          f"recent period with data for every place named.")
    return wanted[0], wanted[1], None


# --- formatting ---------------------------------------------------------------------------------------------------


def kg(v) -> str:
    return "n/a" if v is None else f"{v:,.0f} kg/ha"


def pct(v) -> str:
    return "n/a" if v is None else f"{v:.1f}%"


def signed(v) -> str:
    return "n/a" if v is None else f"{v:+.1f}%"


def change(a, b) -> float | None:
    return None if a is None or not b else round((a / b - 1) * 100, 1)


def fmt(indicator_id: str, v) -> str:
    if v is None:
        return "n/a"
    unit = INDICATORS[indicator_id].unit
    if unit == "kg/ha":
        return kg(v)
    if unit == "tonnes":
        return f"{v:,.0f} tonnes"
    return f"{v:.1f}%"


def period_label(year: int | None, season: str | None, indicator_id: str | None = None) -> str:
    if indicator_id and _household(indicator_id):
        return "Agriculture Household Survey 2024"
    return f"{year} Season {season}"


def short_name(indicator_id: str) -> str:
    return {"yield_kg_ha": "yield", "production_t": "production"}.get(indicator_id,
                                                                     INDICATORS[indicator_id].name.lower())


def low_note(n: int | None) -> str:
    return f" ⚠ based on only {n} plots, treat with caution" if n is not None and n < LOW_RELIABILITY_N else ""


# --- the answer object --------------------------------------------------------------------------------------------


class Reply:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.visuals: list[dict] = []
        self.warnings: list[str] = []
        self.suggestions: list[str] = []
        self.assumptions: list[str] = []
        self.period: tuple[int, str] | None = None

    def say(self, text: str) -> None:
        if text:
            self.parts.append(text)

    def visual(self, kind: str, title: str | None = None, **data) -> None:
        self.visuals.append({"kind": kind, "title": title, **data})

    def warn(self, text: str | None) -> None:
        if text and text not in self.warnings:
            self.warnings.append(text)

    def suggest(self, *questions: str) -> None:
        for q in questions:
            if q and q not in self.suggestions:
                self.suggestions.append(q)


def map_visual(r: Reply, indicator_id: str, crop: str | None, year, season, highlight: list[str] | None = None):
    r.visual("choropleth", f"{INDICATORS[indicator_id].name}"
             + (f" · {crop}" if crop and not _household(indicator_id) else "")
             + f" · {period_label(year, season, indicator_id)}",
             indicator_id=indicator_id, crop=None if _household(indicator_id) else crop,
             year=None if _household(indicator_id) else year, season=None if _household(indicator_id) else season,
             unit=INDICATORS[indicator_id].unit, highlight=highlight or [])


def district_maps(r: Reply, districts: list[str]) -> None:
    if districts:
        r.visual("district_maps", None, districts=districts[:3])


# --- understanding ------------------------------------------------------------------------------------------------

FOLLOW_UP_STARTS = ("and ", "what about", "how about", "and in", "na ", "naho", "et ", "et a", "same for", "now ")


def _resolve(question: str, e: ent.Entities, context: dict | None) -> tuple[str, float, list]:
    intent, confidence, alternatives = intent_model.predict(e.masked)
    text = ent.normalise(question)
    n_places = len(e.districts) + len(e.provinces)

    # Follow-up such as "and in Huye?" or "what about beans?": keep the previous question type.
    previous = (context or {}).get("intent")
    if previous and previous not in ("greeting", "thanks", "goodbye", "help", "about_data", "out_of_scope") and \
            (text.startswith(FOLLOW_UP_STARTS) or len(text.split()) <= 3) and (e.districts or e.crops or e.provinces) \
            and intent not in ("greeting", "thanks", "goodbye", "help"):
        if not e.crops and context.get("crops") and previous not in ("profile",):
            e.crops = list(context["crops"])
        if not e.indicator_id and context.get("indicator_id"):
            e.indicator_id = context["indicator_id"]
        if previous in ("compare", "why_gap") and len(e.districts) == 1 and context.get("districts"):
            e.districts = [context["districts"][0], *e.districts] if context["districts"][0] not in e.districts \
                else e.districts
        intent, confidence = previous, max(confidence, 0.6)

    if e.foreign or (e.other_year and e.other_year not in (2024, 2025)):
        return "out_of_scope", 1.0, alternatives

    # Low confidence: fall back on what the question names.
    if confidence < CONFIDENT and intent not in ("greeting", "thanks", "goodbye"):
        if n_places >= 2:
            intent = "compare"
        elif e.districts and e.crops:
            intent = "crop_in_district"
        elif e.districts or e.provinces:
            intent = "profile"
        elif e.crops:
            intent = "ranking"

    # Structural sanity rules on top of the model.
    if intent in ("ranking", "crop_in_district", "profile", "practices") and n_places >= 2:
        intent = "compare"
    if intent == "ranking" and len(e.districts) == 1 and not any(
            w in text for w in ("which", "rank", "top", "best", "highest", "lowest", "most", "least", "where", "akahe",
                                "utuhe", "quel")):
        intent = "crop_in_district" if e.crops else "practices" if e.indicator_id in PRACTICES else "profile"
    if intent == "crop_in_district" and not e.districts and not e.provinces:
        intent = "ranking"
    if intent == "crop_in_district" and not e.crops:
        intent = "practices" if e.indicator_id in PRACTICES + HOUSEHOLD else "profile"
    if intent == "profile" and e.crops and (e.districts or e.provinces):
        intent = "crop_in_district"
    if intent == "profile" and not e.districts and not e.provinces:
        intent = "overview"
    if intent == "compare" and n_places < 2 and len(e.crops) < 2 and len(e.seasons) < 2 and not e.year:
        intent = "crop_in_district" if (e.districts or e.provinces) and e.crops else \
            "profile" if (e.districts or e.provinces) else "ranking"
    return intent, confidence, alternatives


def _main_crop(r: Reply, e: ent.Entities, purpose: str = "") -> str:
    if e.crops:
        return e.crops[0]
    r.assumptions.append("No crop was named, so this uses **maize**, Rwanda's most widely grown cereal"
                         + (f" ({purpose})" if purpose else "") + ". Name a crop to change it.")
    return "Maize"


def _crop_list(r: Reply, e: ent.Entities, purpose: str = "") -> list[str]:
    if e.beans_generic:
        r.assumptions.append("\"Beans\" covers two crops in the survey, **bush bean** and **climbing bean**, so "
                             "both are shown.")
    return e.crops[:3] if e.crops else [_main_crop(r, e, purpose)]


# --- conversation handlers ----------------------------------------------------------------------------------------


def h_greeting(r: Reply, e: ent.Entities, q: str) -> None:
    r.say("Hello! I'm **Analiza**, your guide to Rwanda's official agricultural statistics (NISR surveys "
          "2024-2025). Ask me about crop yields, how crops are grown in a district, comparisons between districts, "
          "trends, the effect of improved seed or fertilizer, what-if scenarios or priority districts.")
    r.suggest(*SUGGESTIONS[:4])


def h_thanks(r: Reply, e: ent.Entities, q: str) -> None:
    r.say("You're welcome! Ask me anything else about crops, districts or farming practices in Rwanda.")
    r.suggest(SUGGESTIONS[4], SUGGESTIONS[6], SUGGESTIONS[8])


def h_goodbye(r: Reply, e: ent.Entities, q: str) -> None:
    r.say("Goodbye, and thank you for using Analiza. Murabeho!")


def h_help(r: Reply, e: ent.Entities, q: str) -> None:
    r.say("I answer questions from **official NISR survey data**: the Seasonal Agricultural Survey 2024-2025 "
          "(Seasons A, B and C) and the Agriculture Household Survey 2024, for 19 crops and all 30 districts. "
          "You can write in English, Kinyarwanda or French, and small typos are fine. For example:")
    r.say("\n".join([
        "- **Rankings**: which districts have the highest maize yield?",
        "- **A crop in a district**: beans in Musanze",
        "- **How a crop is grown**: how is maize planted in Nyagatare?",
        "- **Comparisons and reasons**: why is Musanze behind Nyagatare in maize?",
        "- **Trends**: how has potato yield changed across seasons?",
        "- **Inputs and what-if**: what if Nyagatare farmers used improved seed?",
        "- **Priorities, women farmers, best crops, district profiles, national overview**",
    ]))
    r.say("Every answer shows where its numbers come from, with a map or chart.")
    r.suggest(*SUGGESTIONS[:3])


def h_about_data(r: Reply, e: ent.Entities, q: str) -> None:
    m = intent_model.metrics()
    man = store.manifest()
    r.say(f"All numbers come from **NISR microdata**: the Seasonal Agricultural Survey 2024 and 2025 "
          f"({man['sas_plot_crop_rows']:,} plot-crop records, Seasons A, B and C) and the Agriculture Household "
          f"Survey 2024 ({man['ahs_households']:,} households), for 30 districts and {len(man['crops'])} crops.")
    r.say("\n".join([
        "- **Weighted**: every estimate uses NISR survey weights, so it represents all farm plots, not only the "
        "surveyed ones.",
        "- **Yield** = weighted harvest ÷ weighted planted area (kg/ha). The top 1% of yields per crop are excluded "
        "as outliers.",
        "- **Reliability**: results on fewer than 10 observations are not published; fewer than 30 are flagged.",
        "- **What-if scenarios** use a gradient-boosted model trained on plot data "
        f"(holdout R² = {man['model'].get('r2_log_yield', 0):.2f}); they show associations, not proven causes.",
    ]))
    if m:
        r.say(f"Questions are understood by Analiza's own classifier ({m['algorithm']}, trained on "
              f"{m['training_examples']:,} example questions in English, Kinyarwanda and French; "
              f"{m['test_accuracy'] * 100:.0f}% accuracy on unseen test questions). No external AI service is used.")
    r.suggest("Which districts have the highest maize yield?", "Tell me about Rwanda")


OUT_OF_SCOPE_REASONS = [
    (("price", "prices", "cost", "costs", "sell", "market", "igiciro", "prix", "earn", "income", "gdp", "export",
      "kilo"), "prices, markets or incomes"),
    (("weather", "rain", "rainfall", "forecast", "climate", "imvura", "meteo", "temperature", "drought"),
     "weather or climate"),
    (("pest", "pests", "armyworm", "disease", "pesticide", "insect", "treat", "spray"), "pests and diseases"),
    (("plant", "planting", "spacing", "when should", "how do i", "compost", "how to"), "farming advice"),
    (("loan", "loans", "credit", "bank", "tractor", "machinery", "brand"), "loans, machinery or brands"),
    (("cow", "cows", "livestock", "cattle", "goat", "fish", "chicken", "milk"), "livestock"),
]


def h_out_of_scope(r: Reply, e: ent.Entities, q: str) -> None:
    text = ent.normalise(q)
    if e.foreign:
        reason = f"other countries ({e.foreign.title()})"
    elif e.other_year and e.other_year not in (2024, 2025):
        reason = f"{e.other_year} (the surveys cover 2024 and 2025 only, and Analiza does not forecast)"
    else:
        reason = next((label for words, label in OUT_OF_SCOPE_REASONS if any(f" {w}" in f" {text}" for w in words)),
                      None)
    head = f"The NISR agricultural surveys do not cover **{reason}**" if reason else \
        "That question is outside what the NISR agricultural surveys measure"
    r.say(head + ", so I can't answer it without inventing numbers.")
    if reason == "farming advice":
        r.say("For agronomic advice, your local agronomist or RAB (Rwanda Agriculture Board) extension services are "
              "the right source.")
    r.say("I can tell you about yields, production, improved seed, fertilizer, irrigation and erosion control, "
          "extension and cooperatives, women and men farmers, priority districts and what-if scenarios.")
    crop = (e.crops or ["maize"])[0].lower()
    place = e.districts[0] if e.districts else None
    r.suggest(f"How is {crop} grown in {place}?" if place else f"Which districts have the highest {crop} yield?",
              f"Does fertilizer increase {crop} yield?", "What can you do?")


# --- data handlers ------------------------------------------------------------------------------------------------


def h_ranking(r: Reply, e: ent.Entities, q: str) -> None:
    indicator_id = e.indicator_id or "yield_kg_ha"
    if indicator_id in CROP_INDICATORS:
        crops = _crop_list(r, e, "the ranking needs one crop")
    else:
        crops = e.crops[:2] or [None]
    definition = INDICATORS[indicator_id]
    for crop in crops:
        year, season, note = pick_period(indicator_id, crop, [], e.year, e.season)
        data = comparison_service.districts(indicator_id, year, season, crop)
        rows = [d for d in data["districts"] if d["value"] == d["value"]]
        if e.provinces:
            rows = [d for d in rows if d["province"] in e.provinces]
        if not rows:
            r.say(f"No district has enough surveyed plots to rank {short_name(indicator_id)}"
                  f"{' for ' + crop.lower() if crop else ''} in {period_label(year, season, indicator_id)}.")
            continue
        want_low = e.ascending == definition.higher_is_better
        ordered = rows[::-1] if want_low else rows
        top = ordered[:3]
        word = "lowest" if e.ascending else "highest"
        if not definition.higher_is_better:
            word = "highest" if e.ascending else "lowest"
        subject = short_name(indicator_id) + (f" for **{crop.lower()}**" if crop and indicator_id not in
                                              HOUSEHOLD and crop != ALL else "")
        where = f" in {', '.join(e.provinces)} Province" if e.provinces else ""
        r.say(f"The {word} {subject}{where} ({period_label(year, season, indicator_id)}): "
              + "; ".join(f"**{d['area']}** {fmt(indicator_id, d['value'])}" for d in top)
              + (f". National: **{fmt(indicator_id, data['national_value'])}**." if data["national_value"] else "."))
        best, worst = rows[0], rows[-1]
        national = data["national_value"]
        bits = []
        if national:
            above = sum(1 for d in rows if d["value"] > national)
            bits.append(f"{above} of {len(rows)} districts are above the national figure")
        if worst["value"]:
            bits.append(f"the gap between {best['area']} ({fmt(indicator_id, best['value'])}) and {worst['area']} "
                        f"({fmt(indicator_id, worst['value'])}) is {best['value'] / worst['value']:.1f} times"
                        if definition.unit == "kg/ha" else
                        f"they range from {fmt(indicator_id, worst['value'])} in {worst['area']} to "
                        f"{fmt(indicator_id, best['value'])} in {best['area']}")
        if bits:
            r.say(bits[0][0].upper() + "; ".join(bits)[1:] + ".")
        low = [f"{d['area']} ({d['n']})" for d in top if d.get("low_reliability")]
        if low:
            r.warn("Few surveyed plots behind: " + ", ".join(low) + ". These averages are less certain.")
        r.warn(note)
        r.period = (year, season)
        map_visual(r, indicator_id, crop, year, season, [d["area"] for d in top])
        r.visual("ranking", f"{definition.name}{' · ' + crop if crop and crop != ALL and indicator_id not in HOUSEHOLD else ''}"
                 f" · {period_label(year, season, indicator_id)}", data=data, highlight=[d["area"] for d in top])
    crop = crops[0]
    ranked = [v for v in r.visuals if v["kind"] == "ranking"]
    if ranked and (not crop or crop == ALL):
        first = ranked[0]["highlight"][0]
        r.suggest(f"{INDICATORS[indicator_id].name} in {first}", "Does fertilizer increase maize yield?",
                  "Where should support be prioritised for maize?")
    if crop and crop != ALL:
        lead = ranked[0]["highlight"][0] if ranked else "Nyagatare"
        r.suggest(f"How is {crop.lower()} grown in {lead}?", f"Where should support be prioritised for {crop.lower()}?",
                  f"How has {crop.lower()} yield changed across seasons?")


def _crop_block(r: Reply, crop: str, level: str, area: str, e: ent.Entities, with_practices: bool = True) -> dict:
    """Yield, production, rank and practices of one crop in one place against the national figures."""
    year, season, note = pick_period("yield_kg_ha", crop, [(level, area)], e.year, e.season)
    r.warn(note)
    r.period = (year, season)
    y = cell("yield_kg_ha", crop, year, season, level, area)
    if y is None:
        r.say(f"There are no published **{crop.lower()}** results for {area} in any season (too few surveyed "
              f"plots), so {area} grows little {crop.lower()} according to the survey.")
        return {}
    n = nat("yield_kg_ha", crop, year, season)
    prod = cell("production_t", crop, year, season, level, area)
    rank, of = rank_of("yield_kg_ha", crop, year, season, area) if level == "district" else (None, 0)
    gap = change(y["value"], n["value"] if n else None)
    text = (f"**{crop}** in **{area}** ({year} Season {season}): **{kg(y['value'])}**"
            + (f", against {kg(n['value'])} nationally (**{signed(gap)}**)" if n else "")
            + (f", ranking {rank} of {of} districts" if rank else "")
            + (f". Estimated production: {prod['value']:,.0f} tonnes" if prod else "") + "."
            + low_note(y["n"]))
    r.say(text)
    rows = []
    if with_practices:
        lines = []
        for indicator_id in PRACTICES:
            local = cell(indicator_id, crop, year, season, level, area)
            national = nat(indicator_id, crop, year, season)
            if local and national:
                rows.append({"name": CHART_LABEL[indicator_id], "local": round(local["value"], 1),
                             "national": round(national["value"], 1)})
                lines.append(f"- {INDICATORS[indicator_id].name}: **{pct(local['value'])}** of plots "
                             f"(national {pct(national['value'])})")
        if lines:
            r.say(f"How {crop.lower()} is grown there:\n" + "\n".join(lines))
            r.visual("bars", f"How {crop.lower()} is grown · {area} vs Rwanda · {year} Season {season} (% of plots)",
                     unit="%", series=[{"key": "local", "label": area}, {"key": "national", "label": "Rwanda"}],
                     rows=rows)
    return {"year": year, "season": season, "yield": y, "national": n, "gap": gap, "rows": rows}


def h_crop_in_district(r: Reply, e: ent.Entities, q: str) -> None:
    level, area = ("district", e.districts[0]) if e.districts else ("province", e.provinces[0])
    crops = _crop_list(r, e)
    if level == "district":
        district_maps(r, [area])
    for crop in crops:
        _crop_block(r, crop, level, area, e, with_practices=len(crops) == 1)
    crop = crops[0].lower()
    r.suggest(f"Why is {crop} yield in {area} different from the national average?" if level == "district" else "",
              f"What if farmers in {area} used improved seed and fertilizer for {crop}?" if level == "district" else "",
              f"How has {crop} yield changed in {area}?")


def h_practices(r: Reply, e: ent.Entities, q: str) -> None:
    if e.districts or e.provinces:
        level, area = ("district", e.districts[0]) if e.districts else ("province", e.provinces[0])
    else:
        level, area = "national", "Rwanda"
    if e.crops:
        if level == "district":
            district_maps(r, [area])
        if level == "national":
            crop = e.crops[0]
            year, season, note = pick_period("yield_kg_ha", crop, [], e.year, e.season)
            lines = [f"- {INDICATORS[i].name}: **{pct(c['value'])}** of plots"
                     for i in PRACTICES if (c := nat(i, crop, year, season))]
            r.say(f"How **{crop.lower()}** is grown in Rwanda ({year} Season {season}):\n" + "\n".join(lines))
            r.visual("simple_bars", f"{crop} plots using each practice · Rwanda · {year} Season {season}", unit="%",
                     rows=[{"name": CHART_LABEL[i], "value": round(c["value"], 1)}
                           for i in PRACTICES if (c := nat(i, crop, year, season))])
            r.suggest(f"Which districts use the most fertilizer for {crop.lower()}?",
                      f"Does improved seed increase {crop.lower()} yield?")
            return
        for crop in e.crops[:2]:
            _crop_block(r, crop, level, area, e)
        crop = e.crops[0].lower()
    else:
        # All crops: practice rates across every crop's plots, plus household support.
        if level == "district":
            district_maps(r, [area])
        year, season, note = pick_period("improved_seed_pct", None, [(level, area)], e.year, e.season)
        r.warn(note)
        r.period = (year, season)
        rows, lines = [], []
        for indicator_id in PRACTICES + HOUSEHOLD:
            local = cell(indicator_id, None, year, season, level, area)
            national = nat(indicator_id, None, year, season)
            if local and national:
                rows.append({"name": CHART_LABEL[indicator_id], "local": round(local["value"], 1),
                             "national": round(national["value"], 1)})
                lines.append(f"- {INDICATORS[indicator_id].name}: **{pct(local['value'])}** "
                             f"(national {pct(national['value'])})")
        r.say(f"Farming practices in **{area}**, all crops ({year} Season {season}; extension and cooperatives from "
              f"the 2024 household survey):\n" + "\n".join(lines))
        r.visual("bars", f"Farming practices · {area} vs Rwanda (%)", unit="%",
                 series=[{"key": "local", "label": area}, {"key": "national", "label": "Rwanda"}], rows=rows)
        crop = "maize"
    if level == "district":
        r.suggest(f"Why is {crop} yield in {area} different from the national average?",
                  f"What if farmers in {area} used improved seed and fertilizer for {crop}?",
                  f"Which crops grow best in {area}?")


def _places(e: ent.Entities) -> tuple[str, list[str]]:
    if len(e.districts) >= 2:
        return "district", e.districts[:3]
    if len(e.provinces) >= 2:
        return "province", e.provinces[:3]
    if e.districts and (e.national or len(e.crops) < 2):
        return "district", [e.districts[0], "Rwanda"]
    if e.districts:
        return "district", e.districts[:1]
    return "national", ["Rwanda"]


def _practice_rows(crop: str, year: int, season: str, places: list[tuple[str, str]]) -> list[dict]:
    rows = []
    for indicator_id in PRACTICES:
        values = [cell(indicator_id, crop, year, season, lvl, a) for lvl, a in places]
        if all(values):
            rows.append({"id": indicator_id, "name": INDICATORS[indicator_id].name, "label": CHART_LABEL[indicator_id],
                         **{f"p{i}": round(v["value"], 1) for i, v in enumerate(values)}})
    return rows


def _compare_places(r: Reply, e: ent.Entities, crop: str, level: str, names: list[str], explain: bool) -> None:
    places = [("national" if a == "Rwanda" else level, a) for a in names]
    year, season, note = pick_period("yield_kg_ha", crop, places, e.year, e.season)
    r.warn(note)
    r.period = (year, season)
    values = [cell("yield_kg_ha", crop, year, season, lvl, a) for lvl, a in places]
    missing = [a for (lvl, a), v in zip(places, values) if v is None]
    if missing:
        r.say(f"There are too few surveyed **{crop.lower()}** plots in {', '.join(missing)} in any season to "
              f"publish a yield, so a fair comparison is not possible.")
        return
    lines = []
    for (lvl, a), v in zip(places, values):
        rank = rank_of("yield_kg_ha", crop, year, season, a)[0] if lvl == "district" else None
        lines.append(f"**{a}** {kg(v['value'])}" + (f" (rank {rank})" if rank else "") + low_note(v["n"]))
    ordered = sorted(zip(names, values), key=lambda x: x[1]["value"], reverse=True)
    lead, trail = ordered[0], ordered[-1]
    diff = lead[1]["value"] - trail[1]["value"]
    r.say(f"**{crop}** yield, {year} Season {season}: " + " vs ".join(lines) + ". "
          + (f"{lead[0]} is ahead by **{diff:,.0f} kg/ha ({signed(change(lead[1]['value'], trail[1]['value']))})**."
             if abs(change(lead[1]["value"], trail[1]["value"]) or 0) >= 5 else
             f"They are almost level ({signed(change(lead[1]['value'], trail[1]['value']))} for {lead[0]}), within "
             f"what survey sampling can separate."))
    rows = _practice_rows(crop, year, season, places)
    r.visual("bars", f"{crop} yield · {year} Season {season} (kg/ha)", unit="kg/ha",
             series=[{"key": f"p{i}", "label": a} for i, a in enumerate(names)],
             rows=[{"name": crop, **{f"p{i}": round(v["value"]) for i, v in enumerate(values)}}])
    if rows:
        r.visual("bars", f"How {crop.lower()} is grown · % of {crop.lower()} plots", unit="%",
                 series=[{"key": f"p{i}", "label": a} for i, a in enumerate(names)],
                 rows=[{**x, "name": x["label"]} for x in rows])
        lead_i, trail_i = names.index(lead[0]), names.index(trail[0])
        diffs = sorted(rows, key=lambda x: abs(x[f"p{lead_i}"] - x[f"p{trail_i}"]), reverse=True)
        lines = [f"- {x['name']}: {lead[0]} **{pct(x[f'p{lead_i}'])}** vs {trail[0]} **{pct(x[f'p{trail_i}'])}**"
                 for x in diffs]
        r.say(f"How {crop.lower()} is grown (share of {crop.lower()} plots):\n" + "\n".join(lines))
        if explain:
            _explain(r, crop, year, season, lead, trail, diffs, lead_i, trail_i)


def _explain(r: Reply, crop, year, season, lead, trail, diffs, lead_i, trail_i) -> None:
    """Which measured practices line up with the gap, backed by the national input effects and the yield model."""
    effects = {x["input"]: x for x in comparison_service.inputs(year, season, crop)["effects"]}
    ind_to_input = {v: k for k, v in INPUT_TO_INDICATOR.items()}
    helps, against = [], []
    for x in diffs:
        a, b = x[f"p{lead_i}"], x[f"p{trail_i}"]
        if abs(a - b) < 5:
            continue
        effect = effects.get(ind_to_input.get(x["id"], ""), {})
        premium = effect.get("premium_pct")
        first, second = (a, b) if a > b else (b, a)
        reason = (f"{x['name'].lower()} ({pct(first)} vs {pct(second)}"
                  + (f"; nationally, {crop.lower()} plots using it yield {signed(premium)} more" if premium is not None
                     and premium > 0 else "") + ")")
        (helps if a > b else against).append(reason)
    if helps:
        r.say(f"**What the data points to:** {lead[0]} is ahead on " + "; ".join(helps[:2]) + ".")
    if against:
        r.say(f"But {trail[0]} actually leads on " + "; ".join(against[:2]) + ", so that is not what holds it back.")
    if not helps and not against:
        r.say("The two places use seed, fertilizer and irrigation at similar rates, so the measured practices do not "
              "explain the gap.")
    if trail[0] != "Rwanda" and trail[0] in store.district_provinces():
        inputs = [ind_to_input[x["id"]] for x in diffs
                  if x["id"] in ind_to_input and x[f"p{lead_i}"] - x[f"p{trail_i}"] >= 5][:2] \
            or ["improved_seed", "inorganic_fertilizer"]
        try:
            sim = scenario_service.simulate(crop, trail[0], season if season in ("A", "B") else "A", inputs)
            r.say(f"**Model estimate:** if every {crop.lower()} plot in {trail[0]} used "
                  f"{' and '.join(INPUT_COLUMNS[i].lower() for i in sim['inputs'])}, the yield model expects about "
                  f"**{signed(sim['change_pct'])}** higher average yield ({kg(sim['current_yield'])} → "
                  f"{kg(sim['scenario_yield'])} on the model's own scale).")
            r.visual("scenario", f"What-if · {crop} · {trail[0]}", data=sim)
        except ind.NotFoundError:
            pass
    r.say("Soil, altitude and rainfall also matter but are not measured in these surveys, and these are "
          "associations in survey data, not proven causes.")


def h_compare(r: Reply, e: ent.Entities, q: str, explain: bool = False) -> None:
    # Two or more crops in one place: compare each crop against its own national average (fair across crops).
    distinct_crops = len(e.crops) - (1 if e.beans_generic else 0)
    if distinct_crops >= 2 and len(e.districts) + len(e.provinces) <= 1:
        level, area = ("district", e.districts[0]) if e.districts else \
            ("province", e.provinces[0]) if e.provinces else ("national", "Rwanda")
        if level == "district":
            district_maps(r, [area])
        rows, lines = [], []
        for crop in e.crops[:4]:
            year, season, note = pick_period("yield_kg_ha", crop, [(level, area)], e.year, e.season)
            v = cell("yield_kg_ha", crop, year, season, level, area)
            n = nat("yield_kg_ha", crop, year, season)
            trend = comparison_service.seasons("yield_kg_ha", crop, level, area)["series"]
            same = [s for s in trend if s["season"] == season]
            yoy = change(same[-1]["value"], same[0]["value"]) if len(same) >= 2 else None
            if v:
                rows.append({"name": crop, "value": change(v["value"], n["value"]) if level != "national" else yoy})
                lines.append(f"- **{crop}** ({year} Season {season}): {kg(v['value'])}"
                             + (f", {signed(change(v['value'], n['value']))} vs national" if level != "national" else "")
                             + (f"; Season {season} 2024→2025 {signed(yoy)}" if yoy is not None else "")
                             + low_note(v["n"]))
        r.say(f"Comparing crops in **{area}**. Different crops have very different normal yields (cassava naturally "
              f"weighs far more per hectare than beans), so each is compared with "
              f"{'its own national average' if level != 'national' else 'itself a year earlier'}:\n" + "\n".join(lines))
        r.suggest(*(f"How is {c.lower()} grown in {area}?" if level != "national" else
                    f"Which districts have the highest {c.lower()} yield?" for c in e.crops[:2]))
        r.visual("simple_bars", ("Yield vs national average (%) · " if level != "national" else
                                 "Change in yield, same season 2024→2025 (%) · ") + area, unit="%", rows=rows,
                 signed=True)
        return
    # Two seasons or years for one crop: that is a trend question.
    if len(e.seasons) >= 2 or (e.year and not (e.districts or e.provinces)):
        h_trend(r, e, q)
        return
    level, names = _places(e)
    if len(names) < 2:
        (h_crop_in_district if (e.districts or e.provinces) else h_ranking)(r, e, q)
        return
    crops = _crop_list(r, e)
    if level == "district":
        district_maps(r, [n for n in names if n != "Rwanda"])
    for crop in crops[:2]:
        _compare_places(r, e, crop, level, names, explain)
    real = [n for n in names if n != "Rwanda"]
    crop = crops[0].lower()
    if len(real) >= 2:
        r.suggest(f"Why is {real[1]} behind {real[0]} in {crop}?" if not explain else
                  f"Compare women and men farmers' {crop} yields",
                  f"What if farmers in {real[1]} used improved seed and fertilizer for {crop}?",
                  f"How has {crop} yield changed in {real[0]}?")


def h_why_gap(r: Reply, e: ent.Entities, q: str) -> None:
    if not e.districts and not e.provinces:
        crop = _main_crop(r, e)
        year, season, note = pick_period("yield_kg_ha", crop, [], e.year, e.season)
        effects = sorted(comparison_service.inputs(year, season, crop)["effects"],
                         key=lambda x: x["premium_pct"] if x["premium_pct"] == x["premium_pct"] else -999, reverse=True)
        n = nat("yield_kg_ha", crop, year, season)
        r.say(f"Nationally, **{crop.lower()}** averaged **{kg(n['value'] if n else None)}** in {year} Season {season}. "
              "The survey shows which practices go with higher yields:")
        lines = []
        for x in effects[:4]:
            adoption = nat(INPUT_TO_INDICATOR.get(x["input"], ""), crop, year, season) \
                if x["input"] in INPUT_TO_INDICATOR else None
            lines.append(f"- {x['input_label']}: plots using it yield **{kg(x['yield_with'])}** vs "
                         f"{kg(x['yield_without'])} without ({signed(x['premium_pct'])})"
                         + (f"; used on only {pct(adoption['value'])} of plots" if adoption else ""))
        r.say("\n".join(lines))
        r.say("Low use of the inputs with the biggest differences is where the data points. These are associations; "
              "soil, altitude and rainfall also matter but are not measured here.")
        r.visual("inputs", f"{crop} yield with vs without each input · {year} Season {season}",
                 data=comparison_service.inputs(year, season, crop))
        r.suggest(f"Where should support be prioritised for {crop.lower()}?",
                  f"Which districts have the lowest {crop.lower()} yield?")
        return
    if len(e.districts) == 1 and not e.provinces:
        e.national = True
    h_compare(r, e, q, explain=True)


def h_trend(r: Reply, e: ent.Entities, q: str) -> None:
    indicator_id = e.indicator_id or "yield_kg_ha"
    crops = _crop_list(r, e) if indicator_id in CROP_INDICATORS or e.crops else [None]
    level, area = ("district", e.districts[0]) if e.districts else \
        ("province", e.provinces[0]) if e.provinces else ("national", "Rwanda")
    if _household(indicator_id):
        r.say(f"{INDICATORS[indicator_id].name} comes from the 2024 household survey only, so there is no trend "
              f"over time for it yet.")
        return
    if level == "district":
        district_maps(r, [area])
    for crop in crops[:2]:
        data = comparison_service.seasons(indicator_id, crop, level, area)
        series = [s for s in data["series"] if s["value"] == s["value"]]
        label = short_name(indicator_id) + (f" for **{crop.lower()}**" if crop else "")
        if len(series) < 2:
            r.say(f"Only one period has enough data on {label} in {area}, so there is no trend to show.")
            continue
        lines = []
        for season in ("A", "B", "C"):
            same = [s for s in series if s["season"] == season]
            if len(same) >= 2:
                a, b = same[0], same[-1]
                lines.append(f"- Season {season}: {fmt(indicator_id, a['value'])} in {a['year']} → "
                             f"**{fmt(indicator_id, b['value'])}** in {b['year']} "
                             f"(**{signed(change(b['value'], a['value']))}**)" + low_note(b["n"]))
        peak = max(series, key=lambda s: s["value"])
        r.say(f"How {label} changed in **{area}**, comparing each season with the same season a year earlier "
              f"(seasons differ in rainfall and crops, so A is compared with A):\n" + "\n".join(lines))
        r.say(f"The highest value was in {peak['period']} ({fmt(indicator_id, peak['value'])}). Two years is a short "
              f"series, so treat this as a direction, not a long-term trend.")
        r.visual("trend", f"{INDICATORS[indicator_id].name}{' · ' + crop if crop else ''} · {area}", data=data)
    crop = (crops[0] or "maize").lower()
    r.suggest(f"Which districts have the highest {crop} yield?", f"Does improved seed increase {crop} yield?")


def h_input_effect(r: Reply, e: ent.Entities, q: str) -> None:
    crops = _crop_list(r, e)
    for crop in crops[:2]:
        year, season, note = pick_period("yield_kg_ha", crop, [], e.year, e.season)
        data = comparison_service.inputs(year, season, crop)
        effects = [x for x in data["effects"] if x["yield_with"] == x["yield_with"]]
        if not effects:
            r.say(f"Not enough {crop.lower()} plots to compare inputs in {year} Season {season}.")
            continue
        wanted = [x for x in effects if x["input"] in e.inputs] or effects
        lines = []
        for x in wanted:
            thin = x["n_with"] < LOW_RELIABILITY_N
            lines.append(f"- **{x['input_label']}**: {kg(x['yield_with'])} with vs {kg(x['yield_without'])} without "
                         f"(**{signed(x['premium_pct'])}**; {x['n_with']:,} plots use it)"
                         + (" ⚠ few plots" if thin else ""))
        first = wanted[0]
        verdict = "yes" if first["premium_pct"] > 5 else "only slightly" if first["premium_pct"] > 0 else "no"
        r.say((f"**{'Yes' if verdict == 'yes' else 'Only slightly' if verdict == 'only slightly' else 'Not in this data'}**"
               f" for {first['input_label'].lower()} on {crop.lower()}. " if e.inputs else "")
              + f"Nationally, {crop.lower()} plots in {year} Season {season}:\n" + "\n".join(lines))
        if e.inputs and len(effects) > len(wanted):
            best = max(effects, key=lambda x: x["premium_pct"])
            r.say(f"Of all inputs, **{best['input_label'].lower()}** shows the largest difference "
                  f"({signed(best['premium_pct'])}).")
        r.visual("inputs", f"{crop} yield with vs without each input · {year} Season {season}", data=data)
    r.say("These compare plots that do and don't use an input. Farmers who use inputs may also differ in other ways "
          "(land, location), so this is an association, not proof.")
    crop = crops[0].lower()
    r.suggest(f"What if farmers in Nyagatare used improved seed and fertilizer for {crop}?",
              f"Which districts use the least fertilizer for {crop}?")


def h_scenario(r: Reply, e: ent.Entities, q: str) -> None:
    crop = _main_crop(r, e)
    if not e.districts:
        top = priority_service.priorities(2025, "A", crop)["districts"][:3]
        raise Clarify(f"The what-if model works district by district. Which district should I simulate for "
                      f"{crop.lower()}? These have the biggest potential:",
                      [f"What if farmers in {d['district']} used improved seed and fertilizer for {crop.lower()}?"
                       for d in top])
    district = e.districts[0]
    inputs = e.inputs or ["improved_seed", "inorganic_fertilizer"]
    if not e.inputs:
        r.assumptions.append("No input was named, so this simulates **improved seed + inorganic fertilizer**.")
    season = e.season if e.season in ("A", "B") else "A"
    district_maps(r, [district])
    try:
        sim = scenario_service.simulate(crop, district, season, inputs)
    except ind.NotFoundError:
        r.say(f"The model has too few {crop.lower()} plots in {district} in 2025 Season {season} to simulate. "
              f"Try another season or crop.")
        return
    adoption = "; ".join(f"{INPUT_COLUMNS[i].lower()} on {pct(sim['current_adoption_pct'][i])}" for i in sim["inputs"])
    r.say(f"If every surveyed {crop.lower()} plot in **{district}** used "
          f"{' and '.join(INPUT_COLUMNS[i].lower() for i in sim['inputs'])}, the model estimates average yield would "
          f"rise **{signed(sim['change_pct'])}**, from {kg(sim['current_yield'])} to **{kg(sim['scenario_yield'])}** "
          f"(2025 Season {season}, {sim['n_plots']:,} plots). The starting figure is the model's own estimate for "
          f"today's plots, so it can differ a little from the survey average.")
    r.say(f"Today these inputs are used on: {adoption} of plots.")
    singles = sorted(sim["single_input_effects"], key=lambda s: s["change_pct"], reverse=True)
    if singles:
        r.say("Each input on its own: " + "; ".join(f"{INPUT_COLUMNS.get(s['input'], s['input']).lower()} "
                                                    f"{signed(s['change_pct'])}" for s in singles) + ".")
    r.say("This is a machine-learning estimate from survey patterns (holdout R² ≈ 0.80), not a guaranteed result.")
    r.visual("scenario", f"What-if · {crop} · {district}", data=sim)
    r.suggest(f"How is {crop.lower()} grown in {district}?", f"Where should support be prioritised for {crop.lower()}?")


def h_priorities(r: Reply, e: ent.Entities, q: str) -> None:
    crops = _crop_list(r, e)
    for crop in crops[:2]:
        data = priority_service.priorities(2025, "A", crop)
        rows = data["districts"]
        if e.provinces:
            rows = [d for d in rows if d.get("province") in e.provinces]
        if not rows:
            r.say(f"Not enough {crop.lower()} data to rank priority districts.")
            continue
        top = rows[:5]
        r.say(f"Priority districts for **{crop.lower()}** support (2025 Season A, score out of 100): "
              + "; ".join(f"**{d['district']}** {d['score']:.0f}" for d in top) + ".")
        first = top[0]
        r.say(f"{first['district']} ranks first: yield {kg(first['yield_kg_ha'])} against a benchmark of "
              f"{kg(data['benchmark_yield_kg_ha'])} (the 90th-percentile district), improved seed on "
              f"{pct(first.get('improved_seed_pct'))} and fertilizer on {pct(first.get('inorganic_fertilizer_pct'))} "
              f"of plots" + (f", and the model sees about {signed(first['potential_gain_pct'])} potential gain"
                             if first.get("potential_gain_pct") == first.get("potential_gain_pct") and
                             first.get("potential_gain_pct") is not None else "") + ".")
        r.say("The score combines yield gap, modelled potential gain, low seed and fertilizer use and low extension "
              "access, with equal transparency on the Priorities page where the weights can be changed.")
        map_visual(r, "yield_kg_ha", crop, 2025, "A", [d["district"] for d in top])
        r.visual("priorities", f"Priority score · {crop} · 2025 Season A", data=data)
    crop = crops[0].lower()
    r.suggest(f"Why is {crop} yield low in {rows[0]['district'] if rows else 'Nyamagabe'}?",
              f"What if farmers in {rows[0]['district'] if rows else 'Nyamagabe'} used improved seed and fertilizer "
              f"for {crop}?")


def h_gender(r: Reply, e: ent.Entities, q: str) -> None:
    crops = _crop_list(r, e)
    for crop in crops[:2]:
        year, season, note = pick_period("yield_kg_ha", crop, [], e.year, e.season)
        national = comparison_service.gender(year, season, crop, "national")
        rows = national["rows"]
        if not rows or rows[0].get("Female") in ("", None):
            r.say(f"Not enough plots to compare women and men for {crop.lower()}.")
            continue
        row = rows[0]
        r.say(f"Nationally in {year} Season {season}, **{crop.lower()}** plots managed by women yielded "
              f"**{kg(row['Female'])}** against **{kg(row['Male'])}** for men (**{signed(row['gap_pct'])}**; "
              f"{int(row['n_Female']):,} and {int(row['n_Male']):,} plots).")
        districts = comparison_service.gender(year, season, crop, "district")
        drows = [d for d in districts["rows"] if not d.get("low_reliability")]
        if e.districts:
            local = [d for d in districts["rows"] if d["area"] == e.districts[0]]
            if local:
                d = local[0]
                r.say(f"In **{d['area']}**: women {kg(d['Female'])}, men {kg(d['Male'])} ({signed(d['gap_pct'])})"
                      + (" ⚠ few plots" if d.get("low_reliability") else "") + ".")
        if drows:
            behind = sum(1 for d in drows if d["gap_pct"] < 0)
            r.say(f"Women's plots trail men's in {behind} of {len(drows)} districts with reliable samples; the widest "
                  f"gap is in {drows[0]['area']} ({signed(drows[0]['gap_pct'])}).")
            r.visual("gender", f"{crop} yield by plot manager · {year} Season {season} (districts with ≥30 plots)",
                     data={**districts, "rows": drows[:12]})
        r.say("Differences can reflect land size, access to inputs and extension rather than farming skill.")
    crop = crops[0].lower()
    r.suggest("Which districts have the lowest extension access?", f"Does improved seed increase {crop} yield?")


def h_best_crops(r: Reply, e: ent.Entities, q: str) -> None:
    level, area = ("district", e.districts[0]) if e.districts else \
        ("province", e.provinces[0]) if e.provinces else ("national", "Rwanda")
    year, season = e.year or 2025, e.season or "A"
    df = store.indicators()
    sub = df[(df["indicator_id"] == "yield_kg_ha") & (df["level"] == level) & (df["area"] == area)
             & (df["year"] == year) & (df["season"] == season) & (df["crop"] != ALL) & df["value"].notna()]
    if sub.empty:
        r.say(f"No crop has enough surveyed plots in {area} for {year} Season {season}.")
        return
    if level == "district":
        district_maps(r, [area])
    rows = []
    for row in sub.itertuples():
        n = nat("yield_kg_ha", row.crop, year, season)
        prod = cell("production_t", row.crop, year, season, level, area)
        rows.append({"crop": row.crop, "value": row.value, "n": int(row.n),
                     "vs": change(row.value, n["value"]) if n else None, "prod": prod["value"] if prod else None})
    if level == "national":
        by_prod = sorted([x for x in rows if x["prod"]], key=lambda x: x["prod"], reverse=True)
        r.say(f"Rwanda's biggest crops by production in {year} Season {season}: "
              + "; ".join(f"**{x['crop']}** {x['prod']:,.0f} t ({kg(x['value'])})" for x in by_prod[:5]) + ".")
        r.say("Yields in kg/ha can't be compared fairly across crops (a cassava field weighs far more than a bean "
              "field), so this ranks crops by total production.")
        r.visual("simple_bars", f"Production by crop · Rwanda · {year} Season {season} (tonnes)", unit="t",
                 rows=[{"name": x["crop"], "value": round(x["prod"])} for x in by_prod[:10]])
    else:
        strong = sorted([x for x in rows if x["vs"] is not None and x["n"] >= LOW_RELIABILITY_N],
                        key=lambda x: x["vs"], reverse=True)
        by_prod = sorted([x for x in rows if x["prod"]], key=lambda x: x["prod"], reverse=True)
        r.say(f"Crops where **{area}** does best compared with the rest of Rwanda ({year} Season {season}): "
              + "; ".join(f"**{x['crop']}** {kg(x['value'])} ({signed(x['vs'])} vs national)" for x in strong[:4])
              + ".")
        if by_prod:
            r.say("By total production, the main crops are " + ", ".join(f"{x['crop'].lower()} "
                                                                          f"({x['prod']:,.0f} t)" for x in by_prod[:3])
                  + ".")
        r.say("Crops are compared with their own national average, because raw kg/ha differ hugely between crops. "
              "Crops with fewer than 30 surveyed plots are left out of the ranking.")
        r.visual("simple_bars", f"Yield vs national average by crop · {area} · {year} Season {season} (%)", unit="%",
                 rows=[{"name": x["crop"], "value": x["vs"]} for x in strong[:10]], signed=True)
        if strong:
            r.suggest(f"How is {strong[0]['crop'].lower()} grown in {area}?")
    r.suggest(f"Tell me about {area}" if level != "national" else "Which crops grow best in Musanze?")


def h_profile(r: Reply, e: ent.Entities, q: str) -> None:
    if not e.districts:
        e.districts = []
        province = e.provinces[0]
        year, season = e.year or 2025, e.season or "A"
        r.say(f"**{province} Province** ({year} Season {season}):")
        lines = []
        for crop in ("Maize", "Bush bean", "Climbing bean", "Irish potato", "Cassava", "Cooking banana"):
            v = cell("yield_kg_ha", crop, year, season, "province", province)
            n = nat("yield_kg_ha", crop, year, season)
            if v and n:
                lines.append(f"- {crop}: {kg(v['value'])} ({signed(change(v['value'], n['value']))} vs national)")
        r.say("\n".join(lines))
        districts = sorted(d for d, p in store.district_provinces().items() if p == province)
        r.say("Districts: " + ", ".join(districts) + ".")
        r.suggest(f"Which districts in {province} have the highest maize yield?", f"Tell me about {districts[0]}")
        return
    district = e.districts[0]
    year, season, note = pick_period("yield_kg_ha", "Maize", [("district", district)], e.year, e.season)
    data = geography_service.profile(district, year, season)
    r.period = (year, season)
    district_maps(r, [district])
    above = [x for x in data["indicators"] if x["difference"] is not None and
             (x["difference"] > 0) == x["higher_is_better"] and x["difference"] != 0]
    below = [x for x in data["indicators"] if x["difference"] is not None and
             (x["difference"] > 0) != x["higher_is_better"] and x["difference"] != 0]
    r.say(f"**{district}** ({data['province']} Province), {year} Season {season}.")
    if above:
        r.say("Better than the national average on: " + ", ".join(
            f"{x['name'].lower()}{' (maize)' if x.get('crop') else ''}" for x in above[:4]) + ".")
    if below:
        r.say("Behind the national average on: " + ", ".join(
            f"{x['name'].lower()}{' (maize)' if x.get('crop') else ''}" for x in below[:4]) + ".")
    crops = [c for c in data["crop_yields"] if c["vs_national_pct"] == c["vs_national_pct"] and
             c["n"] >= LOW_RELIABILITY_N]
    if crops:
        best = max(crops, key=lambda c: c["vs_national_pct"])
        worst = min(crops, key=lambda c: c["vs_national_pct"])
        r.say(f"Strongest crop compared with Rwanda: **{best['crop'].lower()}** {kg(best['value'])} "
              f"({signed(best['vs_national_pct'])}); weakest: {worst['crop'].lower()} ({signed(worst['vs_national_pct'])}).")
    r.visual("profile", f"Crop yields · {district} vs Rwanda · {year} Season {season}", data=data)
    r.suggest(f"Which crops grow best in {district}?", f"How is maize grown in {district}?",
              "Where should support be prioritised for maize?")


def h_overview(r: Reply, e: ent.Entities, q: str) -> None:
    year, season = e.year or 2025, e.season or "A"
    data = overview_service.overview(year, season)
    kpis = [k for k in data["kpis"] if k["value"] is not None]
    r.say(f"**Rwanda's agriculture, {year} Season {season}** (NISR surveys: {data['coverage']['plot_crop_records']:,} "
          f"plot-crop records and {data['coverage']['households']:,} households in 30 districts).")
    r.say("\n".join(f"- {k['name']}: **{pct(k['value'])}**" + (f" ({k['change']:+.1f} points on a year earlier)"
                                                                 if k.get("change") is not None else "")
                    for k in kpis))
    crops = sorted(data["crops"], key=lambda c: c["production_t"] or 0, reverse=True)
    r.say("Main crops: " + "; ".join(f"{c['crop'].lower()} {kg(c['yield_kg_ha'])}"
                                     + (f" ({signed(c['yield_change_pct'])} on a year earlier)"
                                        if c.get("yield_change_pct") is not None else "") for c in crops[:5]) + ".")
    r.visual("overview", None, data=data)
    r.suggest("Which districts have the highest maize yield?", "Which crops grow best in Huye?",
              "Where should support be prioritised for beans?")


HANDLERS = {
    "greeting": h_greeting, "thanks": h_thanks, "goodbye": h_goodbye, "help": h_help, "about_data": h_about_data,
    "out_of_scope": h_out_of_scope, "ranking": h_ranking, "crop_in_district": h_crop_in_district,
    "practices": h_practices, "compare": h_compare, "why_gap": h_why_gap, "trend": h_trend,
    "input_effect": h_input_effect, "scenario": h_scenario, "priorities": h_priorities, "gender": h_gender,
    "best_crops": h_best_crops, "profile": h_profile, "overview": h_overview,
}


# --- entry point --------------------------------------------------------------------------------------------------


def answer(question: str, history: list[dict] | None = None, context: dict | None = None) -> dict:
    question = (question or "").strip()[:500]
    e = ent.extract(question)
    intent, confidence, alternatives = _resolve(question, e, context)
    r = Reply()

    try:
        HANDLERS[intent](r, e, question)
    except Clarify as c:
        r = Reply()
        r.say(c.text)
        r.suggest(*c.options)
    except ind.NotFoundError as exc:
        r = Reply()
        r.say(f"I couldn't find data for that ({exc}). Try another crop, district or season.")
        r.suggest(*SUGGESTIONS[:3])
    except Exception:
        logger.exception("Ask failed for %r (intent %s)", question, intent)
        r = Reply()
        r.say("Sorry, I couldn't work that one out. Could you rephrase it, naming a crop and a district? For example: "
              "*beans in Musanze*.")
        r.suggest(*SUGGESTIONS[:3])

    if not r.parts:
        r.say("I couldn't find data for that combination. Try another crop, district or season.")
    year, season = r.period or (e.year or 2025, e.season or "A")
    understood = {
        "intent": intent,
        "intent_label": INTENTS.get(intent, intent),
        "confidence": round(confidence, 2),
        "alternatives": alternatives,
        "crops": e.crops,
        "districts": e.districts,
        "provinces": e.provinces,
        "indicator_id": e.indicator_id,
        "indicator": INDICATORS[e.indicator_id].name if e.indicator_id else None,
        "inputs": e.inputs,
        "year": year,
        "season": season,
        "corrections": e.corrections,
        "assumptions": r.assumptions,
    }
    return {
        "question": question,
        "answer": "\n\n".join(r.parts),
        "understood": understood,
        "visuals": r.visuals,
        "warnings": r.warnings,
        "suggestions": r.suggestions[:3],
        "engine": "Analiza NLP (scikit-learn)",
        # Backwards-compatible summary used by older clients and tests.
        "parsed": {"intent": intent, "crop": e.crops[0] if e.crops else None,
                   "district": e.districts[0] if e.districts else None, "districts": e.districts,
                   "indicator_id": e.indicator_id, "year": year, "season": season},
    }
