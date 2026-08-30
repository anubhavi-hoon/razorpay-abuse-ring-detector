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

- [x] Initialize Python packaging and the minimal `src/abuse_detector` package.
- [x] Add pinned direct dependencies and test tooling.
- [x] Add `.gitignore`, `.env.example`, and concise setup/run commands in `README.md`.
- [x] Add one import/smoke test.

Acceptance:

- [x] A clean environment can install the project.
- [x] The test command passes.
- [x] No application features or frontend scaffolding are added.

## Milestone 1 — Seeded synthetic data

Deliverables:

- [x] Implement the account/transaction schemas from `SPEC.md`.
- [x] Generate legitimate users, benign shared entities, and planted abuse rings.
- [x] Provide a CLI with seed, account count, ring count, and output directory options.
- [x] Write a compact dataset manifest with counts and seed.
- [x] Test determinism, unique IDs, foreign keys, and planted-ring presence.

Acceptance:

- [x] The default command produces valid `accounts.csv` and `transactions.csv`.
- [x] Repeating a run with the same inputs produces identical files.
- [x] Labels are present for evaluation but isolated from production features.

## Milestone 2 — Validation and account features

Deliverables:

- [x] Validate both CSV contracts with actionable failures.
- [x] Build the minimum account features listed in `SPEC.md` at an observation cutoff.
- [x] Save the processed feature table and feature metadata.
- [x] Test invalid input, representative feature values, determinism, and label leakage.

Acceptance:

- [x] Every feature has a definition and stable name.
- [x] Training labels and future events cannot enter feature columns.
- [x] The default dataset processes on a laptop without special infrastructure.

## Milestone 3 — ML baseline and evaluation

Deliverables:

- [x] Split data without placing one planted ring in both train and test sets.
- [x] Fit a class-weighted logistic-regression pipeline.
- [x] Persist the complete fitted pipeline and feature names.
- [x] Emit account scores and deterministic reason codes.
- [x] Report the account metrics and errors required by `SPEC.md`.
- [x] Test artifact reload and identical scoring on a fixed sample.

Acceptance:

- [x] Account recall is at least 0.75 and precision at least 0.60 on default data.
- [x] Metrics come only from the held-out test set.
- [x] If targets fail, adjust synthetic realism/features before adding model complexity.

## Milestone 4 — Relationship graph and ring detection

Deliverables:

- [x] Build account/entity relationships from configured entity types.
- [x] Suppress or down-weight overly common entities.
- [x] Find non-singleton connected components with NetworkX.
- [x] Compute component metrics, ring scores, and reason codes.
- [x] Export ring, membership, node, and edge records.
- [x] Test shared-entity linking, noisy-entity filtering, component membership, and score bounds.

Acceptance:

- [x] At least 80% of planted rings appear in the top 20 for default data.
- [x] Every surfaced ring has inspectable evidence.
- [x] Common merchants or IPs do not collapse most accounts into one component.

## Milestone 5 — End-to-end batch pipeline

Deliverables:

- [x] Add one command that validates, builds features, trains or loads the model, scores accounts, detects rings, and writes outputs.
- [x] Record run configuration, artifact version, counts, metrics, and timings.
- [x] Make rerunning the same run ID safe and deterministic.
- [x] Add one end-to-end test on a small seeded dataset.

Acceptance:

- [x] The default full run finishes within 60 seconds on a typical laptop.
- [x] A failed stage exits non-zero and does not present partial results as complete.
- [x] The command and output locations are documented.

## Milestone 6 — Database persistence

Deliverables:

- [x] Add SQLAlchemy models for source records, detection runs, account results, rings, memberships, relationships, and review status.
- [x] Add the initial Alembic migration.
- [x] Load one pipeline run transactionally with upsert/replace semantics.
- [x] Support SQLite by default and PostgreSQL through `DATABASE_URL`.
- [x] Test constraints, rollback behavior, relationships, and idempotent reload.

Acceptance:

- [x] Repeating a load creates no duplicate logical records.
- [x] Invalid foreign keys and statuses are rejected.
- [x] SQLite tests pass without an external service.

## Milestone 7 — REST API

Deliverables:

- [x] Implement the endpoints in `SPEC.md` under `/api/v1`.
- [x] Add bounded pagination and documented filters.
- [x] Return graph-ready ring detail and stable reason codes.
- [x] Validate review-status transitions and missing resources.
- [x] Configure CORS from an environment variable.
- [x] Test successful responses, filtering, pagination, validation, and status updates.

Acceptance:

- [x] Generated OpenAPI accurately describes every endpoint.
- [x] The complete demo flow works against seeded database data.
- [x] Antigravity needs no risk logic or data reshaping beyond presentation needs.

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
