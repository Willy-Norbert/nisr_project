import pandas as pd

from app.analytics.prioritization import COMPONENT_LABELS, DEFAULT_WEIGHTS, score
from app.data import store
from app.services import indicator_service as ind


def _district_values(indicator_id: str, year: int, season: str, crop: str | None) -> pd.Series:
    rows = ind.query(indicator_id, year, season, crop, level="district")
    return rows.set_index("area")["value"]


def priorities(year: int, season: str, crop: str, weights: dict[str, float] | None = None) -> dict:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    weights = {k: max(float(v), 0.0) for k, v in weights.items() if k in DEFAULT_WEIGHTS}

    yields = _district_values("yield_kg_ha", year, season, crop)
    production = _district_values("production_t", year, season, crop)
    benchmark = float(yields.quantile(0.9)) if not yields.empty else None

    df = pd.DataFrame(index=sorted(store.district_provinces()))
    df["province"] = pd.Series(store.district_provinces())
    df["yield_kg_ha"] = yields
    df["production_t"] = production
    df["improved_seed_pct"] = _district_values("improved_seed_pct", year, season, crop)
    df["inorganic_fertilizer_pct"] = _district_values("inorganic_fertilizer_pct", year, season, crop)
    df["extension_access_pct"] = _district_values("extension_access_pct", year, season, None)

    sc = store.scenarios()
    gain = sc[(sc["year"] == year) & (sc["season"] == season) & (sc["crop"] == crop)
              & (sc["inputs"] == "improved_seed+inorganic_fertilizer")].set_index("district")["change_pct"]
    df["potential_gain_pct"] = gain

    df["yield_gap"] = ((benchmark - df["yield_kg_ha"]) / benchmark * 100).clip(lower=0) if benchmark else None
    df["potential_gain"] = df["potential_gain_pct"]
    df["seed_gap"] = 100 - df["improved_seed_pct"]
    df["fertilizer_gap"] = 100 - df["inorganic_fertilizer_pct"]
    df["extension_gap"] = 100 - df["extension_access_pct"]
    df["additional_production_t"] = (df["production_t"] * df["potential_gain_pct"] / 100).round(0)

    df = df[df["yield_kg_ha"].notna()]
    ranked = score(df, weights).reset_index(names="district")
    ranked["rank"] = range(1, len(ranked) + 1)
    return {
        "year": year,
        "season": season,
        "crop": crop,
        "benchmark_yield_kg_ha": None if benchmark is None else round(benchmark, 1),
        "weights": weights,
        "components": [{"id": k, "label": v, "weight": weights[k]} for k, v in COMPONENT_LABELS.items()],
        "method": "Each component is scaled 0-1 across districts (1 = highest need or opportunity), multiplied by its "
        "weight and summed; the score is out of 100. The benchmark is the 90th-percentile district yield. "
        "Potential gain comes from the yield model scenario 'all plots use improved seed and inorganic fertilizer' "
        "(available for the latest survey year).",
        "districts": store.records(ranked.round(2)),
    }
