# ApexStrategy AI

An AI-assisted Formula 1 strategy analytics platform. It combines five seasons
of real historical F1 data with a calibrated probability model and a
data-grounded AI analyst, so fans, creators and amateur analysts can understand
*why* a driver, a team or a strategy performs the way it does.

The product's governing rule: **it never states a number it cannot show you the
source for, and it never presents a probability as a prediction.**

---

## What it does

| Feature | What you get |
|---|---|
| **Race dashboard** | Championship state, constructor progression, the race in focus and its circuit's strategy character |
| **Driver comparison** | Head-to-head records, normalised per-race rates and race-by-race finishing positions |
| **Circuit analysis** | Who goes well where, grid-position conversion, and observed pit-stop patterns |
| **Podium probabilities** | Calibrated podium and points-finish estimates for every driver, each with its contributing factors |
| **Scenario explorer** | Move a driver to a different grid slot and re-score the race, clearly labelled as a simulation |
| **AI Race Analyst** | Natural-language questions answered only from data held in the app, with citations |
| **Model transparency** | How the model was trained and how it scores against baselines on unseen seasons |
| **Feedback loop** | Per-answer ratings with a follow-up reason, aggregated to find weak explanations |
| **Accounts** *(optional)* | Sign in to save comparisons and reopen them later. Nothing else is gated. |

---

## Quick start

Requires Python 3.9+ and Node 20+. No AWS account is needed — the AI layer falls
back to a built-in writer that produces the same grounded answers, just less
fluently.

```bash
git clone <your-repo-url> && cd ApexStrategy-AI

cp .env.example backend/.env   # optional: defaults work without it
make setup                     # venv + Python and Node dependencies
make bootstrap                 # download 5 seasons of data, then train
```

Then start the two dev servers, one per terminal:

```bash
# Terminal 1 — API on http://localhost:8000
make dev-backend

# Terminal 2 — UI on http://localhost:5173  ← open this one
make dev-frontend
```

Open **<http://localhost:5173>**. The Vite dev server proxies `/api` to the
backend, so both run on the same origin and no CORS setup is needed.

`make bootstrap` takes a few minutes: it pulls roughly 2,300 race results,
2,300 qualifying results and 4,000 pit stops from the Ergast/Jolpica F1 API,
fetches CC-licensed driver portraits from Wikimedia Commons, then trains and
evaluates the model. Responses are cached on disk, so re-runs
are fast and offline.

### Single-service mode

To run exactly as it deploys — one FastAPI process serving both the API and the
compiled React bundle:

```bash
make build        # compile the frontend into frontend/dist
make dev-backend  # everything on http://localhost:8000
```

### Verifying it worked

```bash
curl -s localhost:8000/api/health | python3 -m json.tool
```

`status` should be `ok`, `database.races` should be `114`, and `model.available`
should be `true`.

### With Docker

```bash
docker compose up --build   # PostgreSQL + the app on http://localhost:8000
```

---

## Architecture

```
                        ┌─────────────────────────────┐
  Browser ──────────────► React 18 + TypeScript + Vite │
                        │ Tailwind · Recharts          │
                        └───────────────┬─────────────┘
                                        │  /api
                        ┌───────────────▼─────────────┐
                        │ FastAPI                     │
                        │  routers · services · deps  │
                        └───┬────────┬────────┬───────┘
                            │        │        │
          ┌─────────────────▼──┐  ┌──▼─────┐  ▼──────────────────┐
          │ analytics          │  │ ML     │  │ grounding        │
          │ (all stats live    │  │ podium │  │ retrieve → cite  │
          │  in one module)    │  │ model  │  └────────┬─────────┘
          └─────────┬──────────┘  └───┬────┘           │
                    │                 │        ┌───────▼────────┐
          ┌─────────▼─────────────────▼──┐     │ Amazon Bedrock │
          │ PostgreSQL (RDS) / SQLite    │     │  or  narrator  │
          └──────────────────────────────┘     └────────────────┘
                    ▲
          ┌─────────┴──────────┐
          │ Ergast / Jolpica   │   historical F1 data
          └────────────────────┘
```

Both the charts and the AI read from the **same analytics module**. That is what
makes "data-grounded answers" structurally true rather than a prompt
instruction: the assistant can only discuss numbers a chart could also render.

### Layers

| Layer | Technology | Role |
|---|---|---|
| Frontend | React, TypeScript, Vite, Tailwind, Recharts | Dashboards, comparisons, charts, chat |
| Backend | Python, FastAPI, SQLAlchemy 2 | REST API, auth, orchestration |
| Database | PostgreSQL (Amazon RDS); SQLite locally | Races, results, qualifying, pit stops, predictions, users, feedback |
| Data processing | pandas, NumPy | Ingestion, cleaning, feature engineering |
| Model | scikit-learn | Calibrated podium / points-finish probabilities |
| AI | Amazon Bedrock (`bedrock-runtime` Converse) | Grounded natural-language explanations |
| Storage | Amazon S3 | Raw datasets, model artifacts, exports |
| Deployment | Docker, AWS App Runner | Single container serving API + SPA |

---

## Project layout

```
ApexStrategy-AI/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app; also serves the built SPA
│   │   ├── config.py          Settings (env / AWS Secrets Manager)
│   │   ├── models.py          SQLAlchemy schema (15 tables)
│   │   ├── schemas.py         Pydantic request/response models
│   │   ├── security.py        Password hashing, JWT
│   │   ├── routers/           One module per resource
│   │   ├── services/
│   │   │   ├── analytics.py   Every statistic in the product
│   │   │   ├── prediction.py  Scoring, scenarios, model cache
│   │   │   ├── grounding.py   Retrieval + citations for the AI
│   │   │   ├── bedrock.py     Amazon Bedrock client
│   │   │   ├── narrator.py    Deterministic fallback writer
│   │   │   └── analyst.py     Chat orchestration
│   │   ├── ml/
│   │   │   ├── features.py    Feature engineering (leak-free by construction)
│   │   │   ├── model.py       Training, blending, explanation
│   │   │   ├── evaluate.py    Baselines and metrics
│   │   │   └── train.py       End-to-end pipeline
│   │   └── ingest/            Ergast/Jolpica client + transform pipeline
│   ├── migrations/            Alembic
│   ├── scripts/               ingest.py, train_model.py
│   └── tests/                 91 tests
├── frontend/src/
│   ├── pages/                 Dashboard, Compare, Circuits, Predictions,
│   │                          Analyst, Model, Account
│   ├── components/            UI primitives, chart frame, form field, feedback
│   └── lib/                   API client, auth context, validation, palette
│       └── __tests__/         Validation unit tests (vitest)
├── docs/                      MODEL.md, DEPLOYMENT.md, API.md, DESIGN.md
├── infra/iam-policy.json      Least-privilege instance role
├── Dockerfile                 Multi-stage: Node build → Python runtime
└── docker-compose.yml
```

---

## The model

Two binary classifiers estimate **P(podium)** and **P(points finish)**. Each is
a blend of a calibrated L2 logistic regression over 24 pre-race features and the
historical conversion rate for the driver's grid slot.

Measured on **2025, a season held out entirely from training**:

| Target | Metric | Model | Best baseline | |
|---|---|---|---|---|
| Podium | log loss | **0.1922** | 0.2002 | ✅ |
| Podium | ROC AUC | **0.9503** | 0.9386 | ✅ |
| Points | log loss | **0.4859** | 0.5023 | ✅ |
| Points | ROC AUC | **0.8453** | 0.8332 | ✅ |

Three baselines are evaluated every run, and the strongest is the one reported.
`grid_base_rate` — the historical conversion rate per grid slot — is genuinely
hard to beat in a sport where starting position dominates, which is exactly why
it is the benchmark. **The first model built for this project lost to it**; the
architecture changed in response rather than the benchmark.

Read [`docs/MODEL.md`](docs/MODEL.md) for the feature list, the leakage
guarantees, the blending scheme and the known limitations.

---

## Responsible use

This is built into the product, not bolted on:

- **Probabilities are labelled as estimates** everywhere they appear, with the
  assumptions they rest on.
- **Scenarios are labelled simulations** and are never written to the
  predictions table.
- **Every AI answer carries its sources**, expandable in the UI.
- **The assistant refuses to guess.** If retrieval finds nothing, it says which
  part it cannot answer and what data would be needed.
- **The model's scorecard is a user-facing page**, including the case where it
  stops beating its baseline.
- **Sample sizes are shown** next to circuit statistics, because a driver with
  two starts somewhere has a record, not a trend.

---

## Development

```bash
make test-all      # 103 backend tests + 27 frontend tests
make test          # backend only
make test-cov      # backend with coverage
make test-frontend # TypeScript type check + vitest
make lint          # ruff
make migrate       # alembic upgrade head
```

Interactive API docs: <http://localhost:8000/api/docs>

---

## Deployment

Containerised and deployed to **AWS App Runner** as a single service: the React
bundle is built during the Docker build and served by FastAPI, so there is one
image, one service and one URL.

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the ECR + App Runner setup,
RDS, Secrets Manager, the IAM roles and the CI/CD workflows.

---

## Data source & attribution

Historical data comes from the [Jolpica F1 API](https://github.com/jolpica/jolpica-f1),
the community successor to the Ergast Developer API.

Driver portraits come from **Wikimedia Commons** and are all freely licensed
(CC BY, CC BY-SA or CC0). The author and licence of each image are stored
alongside it and rendered next to the photo, because almost all of these
licences require attribution. Drivers without a Commons portrait fall back to a
generated monogram. Track-character metadata
(tyre degradation, overtaking difficulty, pit-lane loss) is hand-maintained
editorial judgement and is labelled as such in the UI.

ApexStrategy AI is an independent project and is not affiliated with, endorsed
by, or connected to Formula 1, the FIA, or any team.
