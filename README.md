# FarmGap Rwanda

**Open agricultural intelligence for closing Rwanda's crop yield gaps.**
Built for the NISR Big Data Hackathon 2026.

FarmGap turns official NISR survey microdata into answers that planners, extension officers, cooperatives and
researchers can use: where farms produce less than they could, which inputs make the difference, and which
districts should be prioritised for support. No account is needed.

- **Live app:** _add deployment link here_
- **Demo video (max 3 min):** [`docs/demo.webm`](docs/demo.webm)
- **API docs:** `<app-url>/docs`

## The problem

Agriculture employs most Rwandans, yet average yields of staple crops remain far below what farmers achieve on
well-managed plots. NST2 and Vision 2050 target higher agricultural productivity, wider use of improved seed,
fertilizer and irrigation, and better-targeted extension. The data to guide this exists in NISR surveys, but it sits
in large microdata files that most decision-makers cannot analyse. FarmGap closes that gap.

## Data

| Source | Use in FarmGap |
|---|---|
| [Seasonal Agricultural Survey 2024](https://microdata.statistics.gov.rw/index.php/catalog) (Seasons A, B, C) | Plot-level production, crop area, inputs, practices |
| [Seasonal Agricultural Survey 2025](https://microdata.statistics.gov.rw/index.php/catalog) (Seasons A, B, C) | Same, latest seasons |
| [Agriculture Household Survey 2024](https://microdata.statistics.gov.rw/index.php/catalog) | Extension, cooperatives, insurance, support programmes |
| [geoBoundaries Rwanda ADM2](https://www.geoboundaries.org/) (CC BY 4.0) | District boundaries for maps |

About 146,000 plot-crop records and 3,724 households, covering 30 districts, 19 crops and 6 seasons.
The raw microdata is not redistributed in this repository (NISR terms of use). The aggregated, survey-weighted
tables the app needs are committed in [`backend/datasets/processed/`](backend/datasets/processed/), with a full
variable list in [`data_dictionary.md`](backend/datasets/processed/data_dictionary.md).

## What the app does

| Page | What you can do |
|---|---|
| **Home** | National key indicators, latest findings and main crop yields at a glance |
| **Ask the data** | Type a question such as "Which districts have the highest maize yield?" and get an answer with charts |
| **Dashboard** | Map any of 13 indicators across the 30 districts, by crop, year and season |
| **District page** | Click any district (map or name) for its own map, ranks, crop yields vs Rwanda, trend and priority score |
| **Insights** | Eight findings generated from the data, each with evidence, a chart and a suggested action |
| **Priorities** | A transparent district priority score for a crop, with weights you can adjust |
| **Simulator** | See how yields could change if farmers adopted improved seed, inorganic or organic fertilizer, or irrigation |
| **Reports** | Download a national or district PDF brief, or the priority table as CSV |
| **Data & methods** | Sources, processing pipeline, model accuracy and the indicator catalogue |

## Methodology (short)

- Every estimate uses NISR survey weights. Yield is weighted harvest divided by weighted planted area (kg/ha).
- Cells with fewer than 10 observations are suppressed; fewer than 30 are flagged as low reliability.
- Yield outliers (top 1% per crop) are excluded.
- The simulator uses a gradient-boosted model trained on log yield (holdout R² = 0.80). It shows associations, not
  causal effects.
- **Ask the data** is an AI assistant: a language model plans the query (intent, crop, district, season, and
  follow-ups from the conversation), FarmGap runs it on the processed survey tables, and the model writes the answer
  from those retrieved numbers only. Without an API key it falls back to a rule-based parser.

### Enable the AI assistant

Copy `backend/.env.example` to `backend/.env` and set `FARMGAP_LLM_API_KEY` (free Gemini key from
[Google AI Studio](https://aistudio.google.com/apikey), or Groq/OpenAI via `FARMGAP_LLM_BASE_URL` and
`FARMGAP_LLM_MODEL`). On Render, add the same variables in the service's Environment settings.

Full details: [`backend/README.md`](backend/README.md) and the in-app **Data & methods** page.

## Run locally

Requirements: Python 3.11+, Node.js 20.19+ (or 22.12+).

```powershell
# 1. Backend API  (http://localhost:8000, docs at /docs)
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend  (new terminal, http://localhost:5173)
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to the backend on port 8000.

Run the tests with `cd backend; python -m pytest -q`.

### Single server (production mode)

```powershell
cd frontend; npm run build      # creates frontend/dist
cd ../backend; python -m uvicorn app.main:app --port 8000
```

FastAPI serves the built React app and the API together at http://localhost:8000.

### Rebuild the processed data (optional)

Download the three surveys from the NISR Microdata Portal, extract them into `backend/datasets/raw/`
(`sas_2024/`, `sas_2025/` with `Season A|B|C` folders, and `ahs_2024/`), then run
`python -m scripts.prepare_datasets` from `backend/` (about 10 minutes).

## Deploy (no Docker)

One web service serves both the frontend and the API. Example on [Render](https://render.com):

- **New Web Service** from this GitHub repo, runtime **Python 3**.
- **Build command:**
  ```
  pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build
  ```
- **Start command:**
  ```
  cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- Environment variable `PYTHON_VERSION=3.11.9`.

The same two commands work on Railway, Fly.io (with a buildpack) or any VM.
To host the frontend separately (for example on Vercel or Netlify), build it with
`VITE_API_URL=https://your-api-host` and add that frontend origin to `FARMGAP_CORS_ORIGINS` on the API
(a JSON list, e.g. `["https://farmgap.vercel.app"]`).

## Repository structure

```
backend/      FastAPI API, data pipeline, analytics, tests       (see backend/README.md)
  app/        api/v1/endpoints, services, analytics, data, core
  scripts/    prepare_datasets.py, build_data_dictionary.py
  datasets/   processed/ (committed), geography/, raw/ (git-ignored)
frontend/     React + TypeScript (Vite), Leaflet maps, Recharts
  src/pages/  Home, Explore, Dashboard, Insights, Priorities, Simulator, Reports, Methods
```

## Team

**Team BitBender**

1. Willy Norbert Irabaruta
2. Niyonshimira Jeanmarie
3. Byiringiro Urbain Bobola


Data: National Institute of Statistics of Rwanda (NISR). Please cite "NISR Seasonal Agricultural Survey 2024-2025
and Agriculture Household Survey 2024, processed by FarmGap Rwanda".
