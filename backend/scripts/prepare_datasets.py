"""Turn the raw NISR microdata into the aggregated tables served by the API.

Run from the backend folder:  python -m scripts.prepare_datasets
Needs the raw survey files in datasets/raw/. Outputs (small, aggregated, safe to publish) go to datasets/processed/.
"""

import json
import logging
import time
from datetime import datetime, timezone

from app.analytics import aggregation, scenario_model
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.data.cleaner import load_ahs_households, load_sas

logger = logging.getLogger("prepare")

MIN_CROP_ROWS = 600  # crops with fewer plot observations across all seasons are not published separately


def main() -> None:
    setup_logging()
    started = time.time()
    out = get_settings().processed_data_dir
    out.mkdir(parents=True, exist_ok=True)

    sas = load_sas()
    ahs = load_ahs_households()

    crop_counts = sas["crop"].value_counts()
    crops = sorted(crop_counts[crop_counts >= MIN_CROP_ROWS].index)
    logger.info("Publishing %d crops: %s", len(crops), crops)

    tables = {
        "indicators": aggregation.sas_indicators(sas, crops),
        "gender_yield": aggregation.gender_yield(sas, crops),
        "input_effects": aggregation.input_effects(sas, crops),
    }
    tables["indicators"] = tables["indicators"]._append(aggregation.ahs_indicators(ahs), ignore_index=True)

    model, categories, metrics = scenario_model.train(sas, crops)
    tables["scenarios"] = scenario_model.scenarios(model, categories, sas, crops)

    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        logger.info("Wrote %s.csv (%d rows)", name, len(df))

    seasons = sas.groupby(["year", "season"]).size().reset_index(name="plot_crop_rows")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "crops": crops,
        "seasons": seasons.to_dict(orient="records"),
        "sas_plot_crop_rows": int(len(sas)),
        "ahs_households": int(len(ahs)),
        "model": metrics,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Done in %.0fs", time.time() - started)


if __name__ == "__main__":
    main()
