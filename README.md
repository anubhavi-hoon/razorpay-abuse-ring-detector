# SybilTrace

**Ring-first intelligence for coordinated promotional abuse.**

SybilTrace detects and prioritizes coordinated multi-account promotional abuse using interpretable account-level ML signals and relationship-graph analysis. It is analyst decision support, not an automatic fraud-blocking system.

## Current status

The Buildathon prototype is complete and deployed on Render. Open the [live SybilTrace application](https://anubhavi-razorpay-abuse.onrender.com/) or review the implementation milestones in [`TASKS.md`](TASKS.md).

## Setup

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Test

```bash
python -m unittest discover -s tests
```

## Generate demo data

```bash
generate-demo-data --output-dir data/raw
```

Defaults produce 2,000 synthetic accounts, 10,000 transactions, and 15 planted abuse rings. Use `--help` to change the seed or dataset size. The `label` and `ring_label` columns are synthetic ground truth reserved for training and evaluation; they must not be used as production features.

The default benchmark includes five partially evasive rings that rotate identifiers and weaken behavioural signals, plus 15 legitimate shared-usage groups with similar relationship patterns. This prevents a perfectly separable demo while preserving deterministic evaluation.

The current `email_hash` and `phone_hash` values are synthetic identifiers derived deterministically from `(kind, seed, index)` via SHA-256. They are not anonymized or hashed real personal data because no real personal data enters this system.

A future real-data version would require HMAC-SHA256 instead of plain SHA-256, a secret server-side pepper instead of the public run seed, and key versioning for pepper rotation. Pseudonymization is not the same as anonymization; these are future requirements and are not implemented now.

## Run the complete pipeline

```bash
run-abuse-pipeline --run-id demo
```

The command validates and processes generated data, trains and scores the account model, detects rings, then publishes the completed run under `runs/demo/`. Its `run.json` records configuration, artifact versions, counts, metrics, timings, and output paths. Repeating the same run ID and configuration returns the existing run unchanged; use a new run ID for different inputs. Pass `--model-artifact path/to/model.pkl` to score with a trusted existing model instead of training one.

## Build account features

```bash
build-account-features --accounts data/raw/accounts.csv --transactions data/raw/transactions.csv --output-dir data/processed
```

The command validates both input contracts and writes `account_features.csv`, separate `account_labels.csv` ground truth, and `feature_metadata.json`. Pass `--cutoff` with a UTC ISO-8601 timestamp to reproduce a historical observation point; otherwise the latest source timestamp is used.

## Train and evaluate the account model

```bash
train-account-model --features data/processed/account_features.csv --labels data/processed/account_labels.csv --output-dir artifacts
```

The command keeps each planted ring entirely in train or test data, fits a class-weighted logistic-regression pipeline, and writes `model.pkl`, `account_scores.csv`, and held-out `evaluation.json`. Only load model artifacts produced by this project.

## Detect abuse rings

```bash
detect-abuse-rings --accounts data/raw/accounts.csv --transactions data/raw/transactions.csv --scores artifacts/account_scores.csv --output-dir data/processed/rings
```

The command suppresses overly common entities, finds non-singleton connected components, and writes ranked rings, memberships, graph nodes/edges, and ring evaluation. It also computes a separate detection-resilience result: the minimum accepted shared-evidence loss needed to leave fewer than half the ring connected as one case. This result does not affect detection or ranking; unusually broad components are left unassessed rather than approximated. The normalized ring score weights mean/max ML score (35%/15%), shared-entity strength (15%), account-link density (10%), promotion concentration (10%), and signup-time concentration (15%); it is a ranking score, not a probability. Override a noise limit with `--max-entity-accounts TYPE=COUNT`.

## Load a run into the database

SQLite is the default:

```bash
alembic upgrade head
load-detection-run runs/demo
```

The loader transactionally replaces the same run ID without duplicates and preserves existing ring review statuses. Set `DATABASE_URL` for another database. PostgreSQL uses a `postgresql+psycopg://...` URL and the optional driver installed with `python -m pip install -e '.[postgres]'`.

## Start the API

```bash
uvicorn abuse_detector.api:app --reload
```

The API is served under `http://127.0.0.1:8000/api/v1`; interactive OpenAPI documentation is available at `/docs`. It serves the latest loaded run, caps ring pages at 100 items, and accepts frontend origins only from the comma-separated `ALLOWED_ORIGINS` environment variable. Ring-list filters are `min_score`, `status`, exact `promotion`, and inclusive `date_from`/`date_to` based on the earliest member signup date; summary score buckets are low (`<0.5`), medium (`0.5–<0.8`), and high (`>=0.8`). The dashboard includes an interactive current-run report and exports it as PDF, CSV, or JSON.

## Deployment

[`render.yaml`](render.yaml) defines the deployed static frontend, FastAPI service, and managed PostgreSQL database. The API startup command applies Alembic migrations and loads the versioned synthetic demo only when it is missing. Render's free API instance can take about a minute to wake after inactivity; the landing page starts that wake-up in the background and the dashboard reports the delay honestly.

Antigravity should use the frozen [`OpenAPI contract`](docs/openapi.json) and [`frontend handoff`](docs/FRONTEND_HANDOFF.md). The handoff includes screen-to-endpoint mapping, filters, pagination, status transitions, reason labels, and representative payloads.

See [`SPEC.md`](SPEC.md) for the product contract and [`ARCHITECTURE.md`](ARCHITECTURE.md) for technical decisions.
