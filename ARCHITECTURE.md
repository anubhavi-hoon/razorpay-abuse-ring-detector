# Architecture

## 1. Design goals

- explainable results suitable for a buildathon demo;
- one reproducible batch pipeline and one small API service;
- laptop-scale operation and free-tier-friendly deployment;
- stable backend/frontend boundary;
- minimal infrastructure and dependencies.

## 2. System shape

```text
Seeded CSV data
      |
      v
Validate -> Feature builder -> ML train/score
                         \        /
                          Graph analysis
                                |
                                v
                    Account + ring results
                                |
                                v
                     SQLite / PostgreSQL
                                |
                                v
                          FastAPI REST API
                                |
                                v
                    Antigravity frontend
```

This is a modular monolith: offline jobs and the API share one Python codebase and database schema. No service boundary is introduced until scale or ownership requires one.

## 3. Technology choices

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | single backend/ML runtime |
| Tabular work | pandas | simple feature and CSV workflows |
| ML | scikit-learn logistic regression | lightweight, reproducible, interpretable |
| Graphs | NetworkX | sufficient for the demo dataset |
| API | FastAPI + Pydantic | validation and generated OpenAPI |
| Persistence | SQLAlchemy | SQLite locally, PostgreSQL when hosted |
| Migrations | Alembic | explicit schema evolution |
| Tests | pytest | focused unit and API checks |
| Packaging | `pyproject.toml` | one dependency/config source |
| Deployment | one container | smallest deployable unit |

No RAG, vector database, graph database, local LLM, queue, cache, or orchestrator is part of the MVP.

## 4. Proposed repository layout

```text
Razorpay/
├── SPEC.md
├── ARCHITECTURE.md
├── TASKS.md
├── pyproject.toml
├── README.md
├── .env.example
├── data/
│   ├── raw/
│   └── processed/
├── artifacts/
├── src/abuse_detector/
│   ├── config.py
│   ├── data.py
│   ├── features.py
│   ├── model.py
│   ├── graph.py
│   ├── pipeline.py
│   ├── db.py
│   ├── schemas.py
│   └── api.py
├── scripts/
│   ├── generate_demo_data.py
│   └── run_pipeline.py
├── migrations/
├── tests/
└── Dockerfile
```

This is a target layout, not permission to scaffold every path upfront. Each milestone creates only what it needs.

## 5. Data flow

1. The generator writes seeded account and transaction CSV files.
2. Validation rejects invalid rows before feature computation.
3. The feature builder produces one row per account at an observation cutoff.
4. The training job splits by planted ring group, fits the pipeline, reports metrics, and saves the artifact.
5. The scorer emits account scores and deterministic reason codes.
6. Graph analysis builds relationships, filters noisy entities, finds components, and scores rings.
7. The loader transactionally replaces or upserts one run's derived results.
8. FastAPI reads results and updates review status.
9. Antigravity renders the API payloads; it does not reproduce risk logic.

## 6. Core records

- `Account`: source identity and creation metadata.
- `Transaction`: account activity and promotion use.
- `DetectionRun`: seed/config/model version, timestamps, and evaluation summary.
- `AccountResult`: feature snapshot, ML score, predicted label, and reasons.
- `Ring`: aggregate score, metrics, reasons, and review status.
- `RingMember`: account membership and member contribution.
- `Relationship`: the shared entity/type connecting two accounts or an account and entity.

Store flexible feature/reason details as JSON where querying individual values is unnecessary. Keep IDs, scores, statuses, timestamps, and foreign keys as typed columns.

## 7. Scoring boundaries

`features.py` is the single source of feature definitions for training and inference. `model.py` owns only model fitting and account scoring. `graph.py` owns relationship filtering, components, and ring scoring. `pipeline.py` coordinates these steps without duplicating their logic.

Reason codes are deterministic mappings such as `SHARED_PAYMENT_INSTRUMENT`, `RAPID_PROMO_CLAIMS`, and `HIGH_REFUND_RATIO`. API text labels may map from these codes, but risk decisions must not depend on frontend wording.

Configuration should include only values expected to vary: random seed, observation cutoff, model threshold, noisy-entity limits, ring-score weights, database URL, and allowed frontend origins.

## 8. API/frontend boundary

The OpenAPI schema is the contract. Ring detail returns graph-ready data directly:

```json
{
  "ring_id": "ring_001",
  "score": 0.91,
  "status": "new",
  "reason_codes": ["SHARED_DEVICE", "RAPID_PROMO_CLAIMS"],
  "members": [{"account_id": "acct_1", "ml_score": 0.88}],
  "nodes": [{"id": "acct_1", "type": "account", "label": "acct_1"}],
  "edges": [{"source": "acct_1", "target": "device_7", "type": "device"}]
}
```

Antigravity owns layout, visualization, client-side state, and presentation. Codex owns payload correctness, pagination/filter semantics, validation, and CORS configuration.

## 9. Deployment

Build one container that runs the API. Run data generation and pipeline loading as explicit one-off commands before the demo or during deployment setup, not on every API startup.

Local default:

- files and model artifact on disk;
- SQLite database;
- API on one process.

Hosted option:

- small container/web-service free tier;
- managed PostgreSQL free tier where available;
- generated/model artifacts baked into the image or produced by a one-off job.

Do not depend on ephemeral SQLite storage for a hosted review workflow. If no durable free database is available, use local deployment for the demo.

## 10. Operational expectations

- structured logs for run ID, stage, duration, counts, and failures;
- `/api/v1/health` checks application and database connectivity;
- database writes for a pipeline run occur transactionally;
- deterministic seeds and versioned run metadata support reproduction;
- secrets come from environment variables and are never committed.

## 11. Scaling seams

The MVP deliberately uses batch processing, NetworkX, and one service. Replace them only after measured need:

- pandas/NetworkX when data no longer fits comfortably in memory;
- batch execution when detection latency must become near-real-time;
- JSON feature fields when specific features require indexed analytics;
- modular monolith when independent ownership or scaling justifies services.
