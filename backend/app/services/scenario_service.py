from app.analytics.definitions import INPUT_COLUMNS
from app.data import store
from app.services.indicator_service import NotFoundError

INPUT_ORDER = list(INPUT_COLUMNS)


def options() -> dict:
    df = store.scenarios()
    model = store.manifest()["model"]
    return {
        "year": int(df["year"].max()),
        "seasons": sorted(df["season"].unique()),
        "crops": sorted(df["crop"].unique()),
        "districts": sorted(df["district"].unique()),
        "inputs": [{"id": k, "label": v} for k, v in INPUT_COLUMNS.items()],
        "model": model,
    }


def simulate(crop: str, district: str, season: str, inputs: list[str]) -> dict:
    unknown = set(inputs) - set(INPUT_ORDER)
    if unknown:
        raise NotFoundError(f"Unknown inputs: {sorted(unknown)}")
    key = "+".join(i for i in INPUT_ORDER if i in inputs) or "current"
    df = store.scenarios()
    cell = df[(df["crop"] == crop) & (df["district"].str.lower() == district.lower()) & (df["season"] == season)]
    if cell.empty:
        raise NotFoundError(f"No scenario for {crop} in {district}, season {season} (too few survey plots)")
    current = cell[cell["inputs"] == "current"].iloc[0]
    chosen = cell[cell["inputs"] == key].iloc[0]
    singles = cell[cell["inputs"].isin(INPUT_ORDER)][["inputs", "predicted_yield", "change_pct"]]
    return {
        "crop": crop,
        "district": current["district"],
        "season": season,
        "year": int(current["year"]),
        "inputs": [i for i in INPUT_ORDER if i in inputs],
        "current_yield": float(current["predicted_yield"]),
        "scenario_yield": float(chosen["predicted_yield"]),
        "change_pct": float(chosen["change_pct"]),
        "current_adoption_pct": {i: float(current[f"current_{i}_pct"]) for i in INPUT_ORDER},
        "single_input_effects": store.records(singles.rename(columns={"inputs": "input"})),
        "n_plots": int(current["n"]),
        "note": "Model estimate of average yield if every surveyed plot adopted the selected inputs. "
        "Learned associations from survey data, not guaranteed outcomes.",
    }
