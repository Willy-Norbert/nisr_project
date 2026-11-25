# Analiza

**Open agricultural intelligence for closing Rwanda's crop yield gaps.**
Built for the NISR Big Data Hackathon 2026.

Analiza turns official NISR survey microdata into answers that planners, extension officers, cooperatives and
researchers can use: where farms produce less than they could, which inputs make the difference, and which
districts should be prioritised for support. No account is needed.

- **Live app:** _http://analiza-nisr.vercel.app/_
- **Demo video (max 3 min):** [`/demo video.mp4`](demo video.mp4)

## The problem

Agriculture employs most Rwandans, yet average yields of staple crops remain far below what farmers achieve on
well-managed plots. NST2 and Vision 2050 target higher agricultural productivity, wider use of improved seed,
fertilizer and irrigation, and better-targeted extension. The data to guide this exists in NISR surveys, but it sits
in large microdata files that most decision-makers cannot analyse. Analiza closes that gap.

## Data

| Source | Use in Analiza |
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
- **Ask the data** uses Analiza's own natural-language model, with no external AI service or API key:
  1. **Entity finder** (`backend/app/nlp/entities.py`): spots crops, districts, provinces, measures, inputs, year and
     season in English, Kinyarwanda or French, corrects typos by fuzzy matching ("mesanze" → Musanze, "ibigori" →
     maize) and shows the user what it understood.
  2. **Question classifier** (`backend/app/nlp/intent_model.py`): TF-IDF character + word n-grams and logistic
     regression (scikit-learn), trained on 2,000+ example questions in three languages across 19 question types.
     Names are masked before classification, so it works for every crop and district. Accuracy is reported in
     `backend/app/nlp/intent_metrics.json` (5-fold cross-validation and a separate set of hand-written test questions).
  3. **Answer engine** (`backend/app/services/ask_service.py`): runs the right survey-weighted queries and writes the
     answer from templates, so every number comes from the NISR tables, with maps and charts. Safeguards: same crop
     and period in every comparison, Season A compared with Season A, results on fewer than 30 observations flagged,
     the period and any assumption (e.g. "beans" = bush + climbing bean) always stated. Questions outside the data
     (prices, weather, pests, other countries, years after 2025) are declined politely with suggestions.

Retrain the question model after editing the examples: `cd backend; python -m scripts.train_intent_model`.

### Testing the assistant (questions with known answers)

The assistant is checked with test questions whose correct answer is computed **directly from the processed data
files** (independently of the assistant's code). Run it yourself with `cd backend; python -m scripts.check_ask_answers`
(it also runs as part of `python -m pytest`):

| Question | Understood as | Correct answer (computed directly from the data) | Assistant matches |
|---|---|---|---|
| Which district has the highest maize yield? | District ranking | Nyagatare 3,074 kg/ha | ✅ |
| mesanze beans | Crop in a district | Musanze (typo fixed), climbing bean 1,049 kg/ha | ✅ |
| How is maize grown in Musanze? | How a crop is grown | improved seed on 40.7% of maize plots | ✅ |
| Which districts use the least fertilizer? | District ranking | Ruhango 13.2% | ✅ |
| ni akahe karere keza mu musaruro w ibirayi? | District ranking | Rubavu 14,147 kg/ha (Kinyarwanda question) | ✅ |
| How has bean yield changed across seasons? | Trend over seasons | bush bean Season A 627 kg/ha → 614 kg/ha (-2.1%) | ✅ |
| Does improved seed increase maize yield? | Input effect | 2,216 kg/ha with vs 1,471 kg/ha without (+50.6%) | ✅ |
| What if farmers in Nyagatare used improved seed and fertilizer for maize? | What-if scenario | model change +6.0% | ✅ |
| Compare women and men farmers' maize yields | Women and men farmers | women 1,773 kg/ha vs men 2,078 kg/ha (-14.7%) | ✅ |
| Which districts have the lowest extension access? | District ranking | Karongi 37.6% | ✅ |
| Why is Musanze behind Nyagatare in maize? | Explaining a gap | Musanze 1,755 kg/ha vs Nyagatare 3,074 kg/ha | ✅ |
| What is the price of maize? | Outside our data | politely declined: prices are not in the surveys | ✅ |
| muraho | Greeting | greeting, with example questions | ✅ |

13 of 13 questions answered correctly.

The question classifier itself is evaluated separately: **97.5%** 5-fold
cross-validation accuracy on 2,277 training examples, and **95.8%** on
48 hand-written test questions it never saw (typos, Kinyarwanda and French included).

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
(a JSON list, e.g. `["https://analiza-nisr.vercel.app"]`).

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
2. Niyonshimira Jean Marie


Data: National Institute of Statistics of Rwanda (NISR). Please cite "NISR Seasonal Agricultural Survey 2024-2025
and Agriculture Household Survey 2024, processed by Analiza".
