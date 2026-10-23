from app.analytics.definitions import LOW_RELIABILITY_N
from app.data import store
from app.services import indicator_service as ind


def districts(indicator_id: str, year: int, season: str, crop: str | None) -> dict:
    definition = ind.get_definition(indicator_id)
    crop = ind.resolve_crop(indicator_id, crop)
    rows = ind.query(indicator_id, year, season, crop, level="district")
    rows = rows.sort_values("value", ascending=not definition.higher_is_better)
    rows["rank"] = range(1, len(rows) + 1)
    national = ind.query(indicator_id, year, season, crop, level="national")
    return {
        "indicator": definition.to_dict(),
        "year": None if ind.is_household(indicator_id) else year,
        "season": None if ind.is_household(indicator_id) else season,
        "crop": crop,
        "national_value": None if national.empty else float(national["value"].iloc[0]),
        "districts": store.records(rows[["area", "province", "value", "n", "low_reliability", "rank"]]),
    }


def seasons(indicator_id: str, crop: str | None, level: str, area: str) -> dict:
    definition = ind.get_definition(indicator_id)
    crop = ind.resolve_crop(indicator_id, crop)
    rows = ind.query(indicator_id, crop=crop, level=level, area=area).sort_values(["year", "season"])
    rows["period"] = rows["year"].astype(str) + " " + rows["season"]
    return {
        "indicator": definition.to_dict(),
        "crop": crop,
        "level": level,
        "area": area,
        "series": store.records(rows[["period", "year", "season", "value", "n", "low_reliability"]]),
    }


def gender(year: int, season: str, crop: str, level: str = "national", area: str | None = None) -> dict:
    df = store.gender_yield()
    df = df[(df["year"] == year) & (df["season"] == season) & (df["crop"] == crop) & (df["level"] == level)]
    if area:
        df = df[df["area"].str.lower() == area.lower()]
    wide = df.pivot_table(index=["area", "province"], columns="gender", values="yield_kg_ha", dropna=False).reset_index()
    n = df.pivot_table(index="area", columns="gender", values="n").add_prefix("n_").reset_index()
    wide = wide.merge(n, on="area", how="left")
    if {"Female", "Male"} <= set(wide.columns):
        wide["gap_pct"] = ((wide["Female"] / wide["Male"] - 1) * 100).round(1)
        wide["low_reliability"] = wide[["n_Female", "n_Male"]].min(axis=1) < LOW_RELIABILITY_N
        wide = wide.dropna(subset=["Female", "Male"]).sort_values("gap_pct")
    return {"year": year, "season": season, "crop": crop, "level": level, "rows": store.records(wide.fillna(""))}


def inputs(year: int, season: str, crop: str) -> dict:
    df = store.input_effects()
    df = df[(df["year"] == year) & (df["season"] == season) & (df["crop"] == crop)]
    return {
        "year": year,
        "season": season,
        "crop": crop,
        "note": "Yield of plots using vs not using each input. Differences are associations, not proof of causation.",
        "effects": store.records(df),
    }
