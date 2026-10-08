# CLAUDE.md — Real-Time Fraud Detection & Risk Scoring

Guidance for Claude when working in this repository. Read this file at the start of every session.

## Project goal

Train fraud-detection models on the Kaggle credit card dataset, serve them through a FastAPI API, stream held-out transactions through the API in real time, store results in Supabase, and show everything on a React analyst dashboard. This is a resume-grade portfolio project, so code quality, honest metrics, and clear docs matter.

## Current status

- **Phase:** 0 — Setup ✅ complete (2026-10-08)
- **Last completed:** Phase 0 — git + GitHub repo (github.com/vid6848/fraud-detection), Python 3.13 venv, pinned requirements, libomp (for XGBoost), folder structure, .env.example, dataset sanity test (4/4 passing)
- **Next step:** Phase 1 — EDA notebook in `ml/`
- **Open questions / blockers:** none
- **Notes:**
  - Using Python 3.13 (3.11 not installed; user chose 3.13).
  - `tests/test_setup.py::test_dataset_exists` will fail in CI where the dataset is absent — handle in Phase 7 (e.g. mark as a data test).
  - `.mcp.json` (Supabase MCP config, user-added) is intentionally left untracked.

> Update this section at the end of every phase.

## Rules

1. **One phase at a time.** Finish, test, and summarize a phase before starting the next. After each phase, tick the checklist below and update "Current status".
2. **Always use the venv** (`.venv/`). Never install packages globally.
3. **Secrets live only in `.env`**, which is never committed. Keep `.env.example` updated with every variable name (no real values).
4. **Never commit `data/creditcard.csv`** (or anything else in `data/`).
5. **Write tests for each module** and run them before saying a phase is done. Report failures honestly.
6. **Explain in simple terms** at the end of each phase what was built and why — the user is new to this.
7. **Ask before installing anything big** (e.g. heavy libraries, Docker images, global tools) **or changing the plan**.

## Data

- File: `data/creditcard.csv` (Kaggle ULB credit card dataset; gitignored)
- 284,807 transactions, 492 frauds (**0.17%** — extremely imbalanced)
- Columns: `Time` (seconds since first transaction), `V1`–`V28` (anonymized PCA features), `Amount`, `Class` (1 = fraud)
- Because features are anonymized, "real-time" means a **simulator replaying the held-out test set** through the API.

## Key ML principles

- **Time-based split** (train → validation → test, ordered by `Time`). Never random split — it leaks future information.
- **Accuracy is never a headline metric.** Predicting "all legit" already scores 99.83%.
- Headline metrics: **PR-AUC, precision, recall, F1, recall at 90% precision, cost saved**.
- Fit scalers / resamplers / calibrators on training data only. Apply SMOTE/undersampling to the training fold only — never to validation or test.
- Threshold is chosen on the **validation** set by business cost (missed fraud amount vs. analyst review cost), then reported once on the **test** set.

## Stack

| Area | Tools |
|---|---|
| ML | Python 3.13, pandas, scikit-learn, XGBoost, imbalanced-learn, SHAP |
| API | FastAPI, pytest |
| Frontend | React, Vite, TypeScript, Tailwind, Recharts |
| Data / Auth | Supabase (Postgres, Realtime, Auth, Row Level Security) |
| Ops | Docker Compose, GitHub Actions, Render (API), Vercel (web) |

## Folder structure

```
data/        # raw dataset (gitignored)
ml/          # EDA notebook, training pipeline
ml/artifacts/  # saved model, threshold, metrics JSON, PR curve plots
api/         # FastAPI service
simulator/   # replays test-set rows to the API
web/         # React dashboard
supabase/    # SQL migrations
tests/       # pytest tests
docs/        # extra documentation, screenshots
```

## Feature spec

### ML
- Time-based train/validation/test split
- Models: Logistic Regression, Decision Tree, Random Forest, XGBoost
- Imbalance handling compared: class weights vs. SMOTE vs. undersampling
- Metrics: PR-AUC, precision, recall, F1, recall @ 90% precision, cost saved
- Cost-based threshold tuning
- Probability calibration
- SHAP explanations per transaction
- Save best model + threshold + metrics JSON + PR curve plots to `ml/artifacts/`

### API
- Endpoints: `POST /predict`, `POST /predict/batch`, `GET /explain/{id}`, `GET /health`, `GET /metrics` (p50/p95 latency)
- Risk levels **LOW / MEDIUM / HIGH** + a small rules layer (hybrid rules + ML)
- Writes every scored transaction to Supabase; HIGH risk also creates an alert

### Supabase
- Tables: `transactions`, `alerts`, `feedback`, `model_runs` — all with Row Level Security
- Realtime enabled on `transactions` and `alerts`
- Auth for analyst login

### Simulator
- Replays test-set rows to `/predict` at a configurable rate (e.g. 20/sec)

### Dashboard
- Live transaction feed
- Alert review queue (confirm fraud / false alarm → `feedback` table)
- Model comparison page with PR curves
- Transaction detail with SHAP bar chart
- Analyst login

### Production
- pytest tests, Docker Compose, GitHub Actions CI
- Drift check (live score distribution vs. training distribution)
- Deploy API to Render, web to Vercel

## Phase checklist

### Phase 0 — Setup
- [x] `git init` + `.gitignore` (data/, .env, .venv/, node_modules/, artifacts as appropriate)
- [x] Python 3.13 venv in `.venv/`
- [x] `requirements.txt` with pinned versions (+ `brew install libomp` for XGBoost on macOS)
- [x] Folder structure created
- [x] `.env.example` with all expected variables
- [x] `tests/test_setup.py` — dataset sanity check

### Phase 1 — EDA
- [ ] EDA notebook in `ml/` (class balance, Amount/Time distributions, feature correlations, fraud over time)
- [ ] Key findings written up in the notebook

### Phase 2 — Training pipeline
- [ ] Time-based train/validation/test split
- [ ] Train LR, Decision Tree, Random Forest, XGBoost
- [ ] Compare class weights vs. SMOTE vs. undersampling
- [ ] Metrics: PR-AUC, precision, recall, F1, recall @ 90% precision, cost saved
- [ ] Cost-based threshold tuning on validation set
- [ ] Probability calibration
- [ ] SHAP explainer
- [ ] Save model, threshold, metrics JSON, PR curves to `ml/artifacts/`
- [ ] Tests for the pipeline
- [ ] Fill in README "Results" table

### Phase 3 — FastAPI service
- [ ] `/predict`, `/predict/batch`, `/explain/{id}`, `/health`, `/metrics`
- [ ] Risk levels LOW / MEDIUM / HIGH + rules layer
- [ ] p50/p95 latency tracking
- [ ] pytest tests for all endpoints

### Phase 4 — Supabase
- [ ] SQL migrations for `transactions`, `alerts`, `feedback`, `model_runs`
- [ ] Row Level Security policies
- [ ] Realtime on `transactions` and `alerts`
- [ ] Auth configured for analysts
- [ ] API writes scored transactions; HIGH risk creates alerts
- [ ] Integration tests

### Phase 5 — Stream simulator
- [ ] Replay test-set rows to `/predict` at configurable rate
- [ ] CLI options (rate, limit, API URL)
- [ ] Tests

### Phase 6 — React dashboard
- [ ] Vite + React + TS + Tailwind scaffold
- [ ] Analyst login (Supabase Auth)
- [ ] Live transaction feed (Realtime)
- [ ] Alert review queue → `feedback` table
- [ ] Model comparison page with PR curves
- [ ] Transaction detail with SHAP bars

### Phase 7 — Production
- [ ] Dockerfiles + Docker Compose
- [ ] GitHub Actions CI (lint + tests)
- [ ] Drift check (live vs. training score distribution)
- [ ] Deploy API (Render) + web (Vercel)
- [ ] Final README with real metrics, screenshots, live links

## End-of-phase routine

1. Run all tests and show the result.
2. Tick completed boxes above.
3. Update "Current status".
4. Give the user a plain-language summary: what was built, why it matters, how to try it.
