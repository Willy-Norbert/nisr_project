from app.data import store
from app.services import indicator_service as ind

KEY_CROPS = ["Maize", "Bush bean", "Irish potato", "Cassava", "Paddy rice"]


def overview(year: int, season: str) -> dict:
    manifest = store.manifest()
    kpis = []
    for indicator_id in ["improved_seed_pct", "inorganic_fertilizer_pct", "irrigation_pct", "extension_access_pct"]:
        definition = ind.get_definition(indicator_id)
        current = ind.value(indicator_id, year, season, None, "national", "Rwanda")
        previous = None if ind.is_household(indicator_id) else ind.value(indicator_id, year - 1, season, None, "national", "Rwanda")
        kpis.append({
            "indicator_id": indicator_id,
            "name": definition.name,
            "unit": definition.unit,
            "value": current,
            "previous_value": previous,
            "change": None if current is None or previous is None else round(current - previous, 2),
            "period": "2024 (household survey)" if ind.is_household(indicator_id) else f"{year} Season {season}",
        })

    crops = []
    for crop in KEY_CROPS:
        current = ind.value("yield_kg_ha", year, season, crop, "national", "Rwanda")
        previous = ind.value("yield_kg_ha", year - 1, season, crop, "national", "Rwanda")
        production = ind.value("production_t", year, season, crop, "national", "Rwanda")
        if current is None:
            continue
        crops.append({
            "crop": crop,
            "yield_kg_ha": current,
            "previous_yield_kg_ha": previous,
            "yield_change_pct": None if not previous else round((current / previous - 1) * 100, 1),
            "production_t": production,
        })

    season_rows = [s for s in manifest["seasons"] if s["year"] == year and s["season"] == season]
    return {
        "year": year,
        "season": season,
        "coverage": {
            "plot_crop_records": manifest["sas_plot_crop_rows"],
            "households": manifest["ahs_households"],
            "districts": 30,
            "crops": len(manifest["crops"]),
            "season_records": season_rows[0]["plot_crop_rows"] if season_rows else None,
        },
        "kpis": kpis,
        "crops": crops,
    }
