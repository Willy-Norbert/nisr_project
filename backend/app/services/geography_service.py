import copy

from app.analytics.definitions import INDICATORS
from app.data import store
from app.services import indicator_service as ind


def districts_geojson(indicator_id: str | None, year: int, season: str, crop: str | None) -> dict:
    """District boundaries; when an indicator is given each feature carries its value for the map."""
    geo = copy.deepcopy(store.districts_geojson())
    provinces = store.district_provinces()
    values = {}
    if indicator_id:
        rows = ind.query(indicator_id, year, season, crop, level="district")
        values = {r.area: r for r in rows.itertuples()}
    for feature in geo["features"]:
        name = feature["properties"]["shapeName"]
        row = values.get(name)
        feature["properties"] = {
            "district": name,
            "province": provinces.get(name, ""),
            "value": None if row is None else float(row.value),
            "n": None if row is None else int(row.n),
            "low_reliability": None if row is None else bool(row.low_reliability),
        }
    return geo


def locations() -> list[dict]:
    return [{"district": d, "province": p} for d, p in sorted(store.district_provinces().items())]


def profile(district: str, year: int, season: str) -> dict:
    provinces = store.district_provinces()
    match = next((d for d in provinces if d.lower() == district.lower()), None)
    if match is None:
        raise ind.NotFoundError(f"Unknown district '{district}'")

    rows = []
    for indicator_id, definition in INDICATORS.items():
        crop = "Maize" if definition.crop_specific else ind.ALL_CROPS
        local = ind.value(indicator_id, year, season, crop, "district", match)
        national = ind.value(indicator_id, year, season, crop, "national", "Rwanda")
        if local is None:
            continue
        ranked = ind.query(indicator_id, year, season, crop, level="district")
        ranked = ranked.sort_values("value", ascending=not definition.higher_is_better).reset_index(drop=True)
        position = ranked.index[ranked["area"] == match]
        rows.append({
            "rank": int(position[0]) + 1 if len(position) else None,
            "of": len(ranked),
            "higher_is_better": definition.higher_is_better,
            "indicator_id": indicator_id,
            "name": definition.name,
            "unit": definition.unit,
            "crop": crop if definition.crop_specific else None,
            "value": local,
            "national_value": national,
            "difference": None if national is None else round(local - national, 2),
        })

    df = store.indicators()
    crops = df[
        (df["indicator_id"] == "yield_kg_ha") & (df["level"] == "district") & (df["area"] == match)
        & (df["year"] == year) & (df["season"] == season)
    ]
    nat = df[(df["indicator_id"] == "yield_kg_ha") & (df["level"] == "national") & (df["year"] == year) & (df["season"] == season)]
    crops = crops.merge(nat[["crop", "value"]].rename(columns={"value": "national_value"}), on="crop", how="left")
    crops["vs_national_pct"] = ((crops["value"] / crops["national_value"] - 1) * 100).round(1)
    return {
        "district": match,
        "province": provinces[match],
        "year": year,
        "season": season,
        "indicators": rows,
        "crop_yields": store.records(crops[["crop", "value", "national_value", "vs_national_pct", "n"]].sort_values("crop")),
    }
