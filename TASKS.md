# Implementation Tasks

## Working rules

- Complete one milestone at a time; do not implement later milestones early.
- Read `SPEC.md` and `ARCHITECTURE.md` before each milestone.
- Keep each change runnable and add the smallest relevant test.
- Reuse existing code and installed dependencies before adding anything.
- Update this file only to check completed acceptance items or record an explicit scope decision.
- Antigravity owns frontend work; Codex stops at the documented API and sample payloads.

## Milestone 0 — Repository baseline

Deliverables:

- [ ] Initialize Python packaging and the minimal `src/abuse_detector` package.
- [ ] Add pinned direct dependencies and test tooling.
- [ ] Add `.gitignore`, `.env.example`, and concise setup/run commands in `README.md`.
- [ ] Add one import/smoke test.

Acceptance:

- [ ] A clean environment can install the project.
- [ ] The test command passes.
- [ ] No application features or frontend scaffolding are added.

## Milestone 1 — Seeded synthetic data

Deliverables:

- [ ] Implement the account/transaction schemas from `SPEC.md`.
- [ ] Generate legitimate users, benign shared entities, and planted abuse rings.
- [ ] Provide a CLI with seed, account count, ring count, and output directory options.
- [ ] Write a compact dataset manifest with counts and seed.
- [ ] Test determinism, unique IDs, foreign keys, and planted-ring presence.

Acceptance:

- [ ] The default command produces valid `accounts.csv` and `transactions.csv`.
- [ ] Repeating a run with the same inputs produces identical files.
- [ ] Labels are present for evaluation but isolated from production features.

## Milestone 2 — Validation and account features

Deliverables:

- [ ] Validate both CSV contracts with actionable failures.
- [ ] Build the minimum account features listed in `SPEC.md` at an observation cutoff.
- [ ] Save the processed feature table and feature metadata.
- [ ] Test invalid input, representative feature values, determinism, and label leakage.

Acceptance:

- [ ] Every feature has a definition and stable name.
- [ ] Training labels and future events cannot enter feature columns.
- [ ] The default dataset processes on a laptop without special infrastructure.

## Milestone 3 — ML baseline and evaluation

Deliverables:

- [ ] Split data without placing one planted ring in both train and test sets.
- [ ] Fit a class-weighted logistic-regression pipeline.
- [ ] Persist the complete fitted pipeline and feature names.
- [ ] Emit account scores and deterministic reason codes.
- [ ] Report the account metrics and errors required by `SPEC.md`.
- [ ] Test artifact reload and identical scoring on a fixed sample.

Acceptance:

- [ ] Account recall is at least 0.75 and precision at least 0.60 on default data.
- [ ] Metrics come only from the held-out test set.
- [ ] If targets fail, adjust synthetic realism/features before adding model complexity.

## Milestone 4 — Relationship graph and ring detection

Deliverables:

- [ ] Build account/entity relationships from configured entity types.
- [ ] Suppress or down-weight overly common entities.
- [ ] Find non-singleton connected components with NetworkX.
- [ ] Compute component metrics, ring scores, and reason codes.
- [ ] Export ring, membership, node, and edge records.
- [ ] Test shared-entity linking, noisy-entity filtering, component membership, and score bounds.

Acceptance:

- [ ] At least 80% of planted rings appear in the top 20 for default data.
- [ ] Every surfaced ring has inspectable evidence.
- [ ] Common merchants or IPs do not collapse most accounts into one component.

## Milestone 5 — End-to-end batch pipeline

Deliverables:

- [ ] Add one command that validates, builds features, trains or loads the model, scores accounts, detects rings, and writes outputs.
- [ ] Record run configuration, artifact version, counts, metrics, and timings.
- [ ] Make rerunning the same run ID safe and deterministic.
- [ ] Add one end-to-end test on a small seeded dataset.

Acceptance:

- [ ] The default full run finishes within 60 seconds on a typical laptop.
- [ ] A failed stage exits non-zero and does not present partial results as complete.
- [ ] The command and output locations are documented.

## Milestone 6 — Database persistence

Deliverables:

- [ ] Add SQLAlchemy models for source records, detection runs, account results, rings, memberships, relationships, and review status.
- [ ] Add the initial Alembic migration.
- [ ] Load one pipeline run transactionally with upsert/replace semantics.
- [ ] Support SQLite by default and PostgreSQL through `DATABASE_URL`.
- [ ] Test constraints, rollback behavior, relationships, and idempotent reload.

Acceptance:

- [ ] Repeating a load creates no duplicate logical records.
- [ ] Invalid foreign keys and statuses are rejected.
- [ ] SQLite tests pass without an external service.

## Milestone 7 — REST API

Deliverables:

- [ ] Implement the endpoints in `SPEC.md` under `/api/v1`.
- [ ] Add bounded pagination and documented filters.
- [ ] Return graph-ready ring detail and stable reason codes.
- [ ] Validate review-status transitions and missing resources.
- [ ] Configure CORS from an environment variable.
- [ ] Test successful responses, filtering, pagination, validation, and status updates.

Acceptance:

- [ ] Generated OpenAPI accurately describes every endpoint.
- [ ] The complete demo flow works against seeded database data.
- [ ] Antigravity needs no risk logic or data reshaping beyond presentation needs.

## Milestone 8 — Frontend handoff contract

Codex deliverables:

- [ ] Freeze and export the OpenAPI document.
- [ ] Provide representative success and error payloads.
- [ ] Document local API URL, CORS setup, pagination, filters, statuses, and reason-code labels.
- [ ] Run a frontend-contract smoke check against seeded data.

Antigravity scope:

- dashboard summary and ranked rings;
- ring detail with relationship graph;
- account detail and transaction view;
- filters, loading/empty/error states, and review-status control;
- responsive, accessible presentation.

Acceptance:

- [ ] The handoff contains no frontend implementation from Codex.
- [ ] Antigravity can build the agreed screens from the API contract alone.

## Milestone 9 — Deployment and demo verification

Deliverables:

- [ ] Add a minimal production container and startup command.
- [ ] Document local SQLite deployment and one modest hosted PostgreSQL option.
- [ ] Ensure migrations and one-off data loading are explicit deployment steps.
- [ ] Run tests, the full seeded pipeline, API smoke checks, and the demo flow.
- [ ] Record exact demo commands and known limitations.

Acceptance:

- [ ] A clean checkout can reproduce the backend and detection results.
- [ ] No secrets, real personal data, or machine-specific paths are committed.
- [ ] Deployment uses one API service and one small database at most.

## Deferred until evidence requires them

- streaming ingestion or online scoring;
- graph databases or distributed graph processing;
- model registry, feature store, experiment platform, or workflow orchestrator;
- hyperparameter-search framework or multiple-model ensemble;
- RAG, vector search, LLM-generated explanations, or local LLM runtime;
- microservices, queues, Redis, Kubernetes, or multi-region deployment;
- automated enforcement actions.
