"""Check the Ask assistant against answers computed directly from the processed NISR tables.

For each test question, the expected figure is looked up independently with pandas (not through the assistant's
code), then we check that the assistant understood the question type and that its answer contains that figure.
Prints a Markdown table for the README.

Run from backend/:  python -m scripts.check_ask_answers
"""

import sys

import pandas as pd

from app.core.config import get_settings
from app.services.ask_service import answer

DATA = get_settings().processed_data_dir
ind = pd.read_csv(DATA / "indicators.csv")
effects = pd.read_csv(DATA / "input_effects.csv")
scen = pd.read_csv(DATA / "scenarios.csv")
gender = pd.read_csv(DATA / "gender_yield.csv")


def cell(indicator, crop, level, area, year=2025, season="A"):
    df = ind[(ind.indicator_id == indicator) & (ind.crop == crop) & (ind.level == level) & (ind.area == area)]
    if year is not None:
        df = df[(df.year == year) & (df.season == season)]
    return float(df.value.iloc[0])


def extreme(indicator, crop, lowest=False, year=2025, season="A"):
    df = ind[(ind.indicator_id == indicator) & (ind.crop == crop) & (ind.level == "district")]
    if year is not None:
        df = df[(df.year == year) & (df.season == season)]
    row = df.sort_values("value", ascending=lowest).iloc[0]
    return row.area, float(row.value)


def kg(v):
    return f"{v:,.0f} kg/ha"


def pct(v):
    return f"{v:.1f}%"


def signed(v):
    return f"{v:+.1f}%"


def cases():
    top, v = extreme("yield_kg_ha", "Maize")
    yield (["Which district has the highest maize yield?"], "ranking", f"{top} {kg(v)}", [top, kg(v)])

    v = cell("yield_kg_ha", "Climbing bean", "district", "Musanze")
    yield (["mesanze beans"], "crop_in_district", f"Musanze (typo fixed), climbing bean {kg(v)}", ["Musanze", kg(v)])

    v = cell("improved_seed_pct", "Maize", "district", "Musanze")
    yield (["How is maize grown in Musanze?"], "practices", f"improved seed on {pct(v)} of maize plots", [pct(v)])

    low, v = extreme("inorganic_fertilizer_pct", "All crops", lowest=True)
    yield (["Which districts use the least fertilizer?"], "ranking", f"{low} {pct(v)}", [low, pct(v)])

    top, v = extreme("yield_kg_ha", "Irish potato")
    yield (["ni akahe karere keza mu musaruro w ibirayi?"], "ranking", f"{top} {kg(v)} (Kinyarwanda question)",
           [top, kg(v)])

    a, b = cell("yield_kg_ha", "Bush bean", "national", "Rwanda", 2024), cell("yield_kg_ha", "Bush bean", "national",
                                                                              "Rwanda", 2025)
    yield (["How has bean yield changed across seasons?"], "trend",
           f"bush bean Season A {kg(a)} → {kg(b)} ({signed((b / a - 1) * 100)})", [kg(a), kg(b)])

    e = effects[(effects.crop == "Maize") & (effects.year == 2025) & (effects.season == "A")
                & (effects.input == "improved_seed")].iloc[0]
    yield (["Does improved seed increase maize yield?"], "input_effect",
           f"{kg(e.yield_with)} with vs {kg(e.yield_without)} without ({signed(e.premium_pct)})", [signed(e.premium_pct)])

    s = scen[(scen.crop == "Maize") & (scen.district == "Nyagatare") & (scen.season == "A")
             & (scen.inputs == "improved_seed+inorganic_fertilizer")].iloc[0]
    yield (["What if farmers in Nyagatare used improved seed and fertilizer for maize?"], "scenario",
           f"model change {signed(s.change_pct)}", [signed(s.change_pct)])

    g = gender[(gender.crop == "Maize") & (gender.year == 2025) & (gender.season == "A") & (gender.level == "national")]
    f, m = float(g[g.gender == "Female"].yield_kg_ha.iloc[0]), float(g[g.gender == "Male"].yield_kg_ha.iloc[0])
    yield (["Compare women and men farmers' maize yields"], "gender",
           f"women {kg(f)} vs men {kg(m)} ({signed((f / m - 1) * 100)})", [kg(f), kg(m)])

    low, v = extreme("extension_access_pct", "All crops", lowest=True, year=None)
    yield (["Which districts have the lowest extension access?"], "ranking", f"{low} {pct(v)}", [low, pct(v)])

    a = cell("yield_kg_ha", "Maize", "district", "Musanze")
    b = cell("yield_kg_ha", "Maize", "district", "Nyagatare")
    yield (["Why is Musanze behind Nyagatare in maize?"], "why_gap", f"Musanze {kg(a)} vs Nyagatare {kg(b)}",
           [kg(a), kg(b), "improved seed"])

    yield (["What is the price of maize?"], "out_of_scope", "politely declined: prices are not in the surveys",
           ["do not cover"])
    yield (["muraho"], "greeting", "greeting, with example questions", ["Analiza"])


def main() -> int:
    rows, failures = [], 0
    for (question,), intent, expected, must_contain in cases():
        result = answer(question)
        got = result["understood"]["intent"]
        ok = got == intent and all(m in result["answer"] for m in must_contain)
        failures += not ok
        rows.append(f"| {question} | {result['understood']['intent_label']} | {expected} | {'✅' if ok else '❌'} |")
        if not ok:
            print(f"FAILED: {question!r} intent={got} (expected {intent}); answer: {result['answer'][:300]}",
                  file=sys.stderr)
    print("| Question | Understood as | Correct answer (computed directly from the data) | Assistant matches |")
    print("|---|---|---|---|")
    print("\n".join(rows))
    print(f"\n{len(rows) - failures} of {len(rows)} questions answered correctly.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
