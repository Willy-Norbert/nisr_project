# Analiza - Backend (FastAPI)

Python API that turns NISR agricultural survey microdata into survey-weighted indicators, district comparisons,
insights, priority rankings, yield scenarios and downloadable reports.

## Run the API

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- The API only reads `datasets/processed/` (aggregated tables, committed to the repo), so it runs without the raw microdata.

## Rebuild the processed data (optional)

1. Download from the [NISR Microdata Portal](https://microdata.statistics.gov.rw/index.php/catalog):
   Seasonal Agricultural Survey 2024 and 2025, Agriculture Household Survey 2024.
2. Extract them into `datasets/raw/` as `sas_2024/`, `sas_2025/` (each with `Season A|B|C` folders) and `ahs_2024/`.
3. Run `python -m scripts.prepare_datasets` (about 5-10 minutes). `python -m scripts.build_data_dictionary` lists every variable.

Raw files are git-ignored: NISR microdata must not be redistributed.

## Structure

```
app/
  main.py                 FastAPI app, error handlers, serves frontend/dist in production
  core/                   settings (env prefix FARMGAP_) and logging
  data/
    registry.py           catalogue of the 38 raw NISR files
    loader.py             reads Stata files with value labels
    cleaner.py            harmonises SAS (plot x crop) and AHS (household) microdata
    store.py              cached access to datasets/processed
  analytics/
    definitions.py        indicator catalogue (single source of truth)
    aggregation.py        survey-weighted indicators, gender yields, input effects
    scenario_model.py     gradient-boosted yield model + adoption scenarios
    prioritization.py     transparent district priority score
  services/               business logic per feature
  api/v1/endpoints/       HTTP routes
scripts/                  prepare_datasets.py, build_data_dictionary.py
datasets/processed/       indicators.csv, gender_yield.csv, input_effects.csv, scenarios.csv, manifest.json
datasets/geography/       rwanda_districts.geojson (geoBoundaries, CC BY 4.0)
tests/                    pytest suite (python -m pytest)
```

## Endpoints (`/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API status |
| GET | `/metadata/datasets`, `/metadata/datasets/{id}` | Raw NISR files and their variables |
| GET | `/metadata/indicators`, `/metadata/filters`, `/metadata/methodology` | Definitions, filter options, methods and model metrics |
| GET | `/overview`, `/overview/highlights` | Dashboard KPIs, main crops, top findings |
| GET | `/indicators`, `/indicators/{id}`, `/indicators/{id}/values` | Indicator catalogue and values (filter by year, season, crop, level, area) |
| GET | `/comparisons/districts` | Ranked district values vs national |
| GET | `/comparisons/seasons` | Time series across 2024-2025 seasons |
| GET | `/comparisons/gender` | Female vs male farmer yields |
| GET | `/comparisons/inputs` | Yield with vs without improved seed, fertilizer, irrigation |
| GET | `/geography/districts.geojson` | District boundaries with indicator values for maps |
| GET | `/geography/locations`, `/geography/locations/{district}` | District list and district profile |
| GET | `/insights`, `/insights/{id}` | Data-generated findings with evidence and suggested actions |
| GET | `/priorities` | District priority ranking with adjustable weights (`w_yield_gap`, ...) |
| GET | `/scenarios/options`, `/scenarios` | Yield simulator: crop, district, season, `inputs=` |
| POST | `/ask`, GET `/ask/suggestions` | Plain-language questions answered from the data |
| POST | `/reports`, GET `/reports/{id}/download` | PDF or CSV report (national or district) |

## Methodology

- **Weights:** every estimate uses NISR survey weights (`plot_weight` for SAS, household `weight` for AHS).
- **Yield:** weighted total harvest / weighted planted crop area (kg/ha). 2025 uses NISR's `Crop_Area_ha`; 2024 crop
  area comes from the screening module (for large-scale farms: plot area shared between crops on the plot). Plots
  under 5 m2 and the top 1% of yields per crop are excluded.
- **Practice rates:** share of plots (each plot counted once) using improved seed, fertilizer, irrigation, etc.
- **Suppression:** cells with fewer than 10 observations are dropped; fewer than 30 are flagged `low_reliability`.
- **Yield model:** `HistGradientBoostingRegressor` on log(yield) with crop, district, season, year, plot size, farmer
  type, gender and practices. Holdout R2 = 0.80 (log yield). Scenarios predict the average yield of observed plots if
  all adopted the selected inputs. These are associations, not causal effects.
