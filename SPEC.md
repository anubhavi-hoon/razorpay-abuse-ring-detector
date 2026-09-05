# Razorpay Buildathon: Coordinated Promotional Abuse Detection

## 1. Purpose

Build a demo-ready system that identifies coordinated groups of accounts abusing promotional offers. It combines lightweight tabular machine learning with relationship/graph analysis, then presents ranked cases and supporting evidence for human review.

The system is decision support, not an automatic account-blocking system.

## 2. Abuse scenario

An abuse ring creates or controls multiple accounts to claim the same promotion repeatedly. Accounts may look harmless in isolation but share identifiers, devices, networks, payment instruments, merchants, timing patterns, or transaction behavior.

The MVP must detect:

- suspicious individual accounts;
- relationships among accounts and shared entities;
- connected groups with coordinated behavior;
- concise reasons explaining why each account or ring was flagged.

## 3. Users and product behavior

Primary user: a risk analyst reviewing promotional abuse.

The product must let the analyst:

1. view summary metrics and a ranked list of suspicious rings;
2. open a ring to see members, shared entities, transactions, scores, and reason codes;
3. inspect a simple relationship graph;
4. filter cases by score, promotion, status, and date;
5. mark a case as `new`, `reviewing`, `confirmed`, or `dismissed`.

Antigravity built the initial frontend; Codex also made scoped changes for the dashboard high-risk entry point and risk-level display. Codex owns the data pipeline, detection logic, database, API contract, tests, and deployment setup.

## 4. MVP boundaries

### In scope

- synthetic, reproducible demo data;
- batch ingestion from CSV files;
- deterministic feature generation;
- lightweight supervised account scoring;
- graph construction and connected-component analysis;
- ring scoring using ML and graph signals;
- persisted results and review status;
- read-oriented REST API plus one review-status update endpoint;
- local setup, tests, and modest free-tier deployment.

### Out of scope

- real Razorpay or customer data;
- payment authorization or automatic enforcement;
- streaming detection and real-time guarantees;
- identity verification, device fingerprinting, or external enrichment services;
- RAG, embeddings, vector databases, local LLMs, or generative-AI explanations;
- distributed graph databases, queues, microservices, and Kubernetes;
- production security/compliance certification.

## 5. Data contract

Use stable string IDs and UTC ISO-8601 timestamps.

### `accounts.csv`

| Field | Type | Notes |
|---|---|---|
| `account_id` | string | unique |
| `created_at` | timestamp | UTC |
| `email_hash` | string | synthetic identifier derived deterministically from `(kind, seed, index)` via SHA-256 |
| `phone_hash` | string | synthetic identifier derived deterministically from `(kind, seed, index)` via SHA-256 |
| `device_id` | string | may be shared |
| `ip_address` | string | synthetic address |
| `payment_instrument_id` | string | may be shared |
| `label` | integer | `1` abuse, `0` legitimate; training/evaluation only |
| `ring_label` | string/null | synthetic ground truth; evaluation only |

The current `email_hash` and `phone_hash` values are synthetic identifiers, not anonymized or hashed real personal data. They are generated deterministically from `(kind, seed, index)` using SHA-256, and no real personal data enters this system.

A future real-data version would require HMAC-SHA256 rather than plain SHA-256, a secret server-side pepper rather than the public run seed, and key versioning to support pepper rotation. Pseudonymization is not the same as anonymization. These are stated future requirements and are not implemented now.

### `transactions.csv`

| Field | Type | Notes |
|---|---|---|
| `transaction_id` | string | unique |
| `account_id` | string | references account |
| `merchant_id` | string | synthetic merchant |
| `promotion_id` | string/null | claimed promotion |
| `amount` | number | non-negative |
| `created_at` | timestamp | UTC |
| `status` | string | `succeeded`, `failed`, or `refunded` |

Reject malformed rows, duplicate primary IDs, missing account references, invalid timestamps, and negative amounts with useful errors.

## 6. Synthetic dataset

The generator must accept a seed and produce the same output for the same inputs. Default demo size should remain laptop- and free-tier-friendly: roughly 2,000 accounts, 10,000 transactions, and 10–20 planted rings.

Legitimate data should include benign sharing such as households, offices, and common IPs. Planted rings should combine several—not necessarily all—signals:

- reused device or payment instrument;
- clustered account creation or promotion claims;
- repeated merchant/promotion combinations;
- unusually high claim, failure, or refund rates;
- low-value transactions near promotion thresholds.

Ground-truth labels must never be used as model features.

## 7. Account features

Compute features only from data available at or before the configured observation cutoff. Minimum feature set:

- account age;
- transaction count and total/mean amount;
- promotion claim count and ratio;
- distinct merchants and promotions;
- failure and refund ratios;
- accounts sharing the same device, IP, payment instrument, email, or phone;
- transactions and promotion claims in short time windows;
- time from signup to first promotion claim.

Feature code must be deterministic and reusable by training and scoring.

## 8. Detection approach

### Lightweight ML

Train one interpretable classifier on account features. Start with scikit-learn logistic regression using class weighting. Persist the fitted preprocessing/model pipeline and its feature names. Do not add model-selection infrastructure unless the baseline fails the acceptance targets.

Output per account:

- `ml_score` from 0 to 1;
- predicted label at a configurable threshold;
- top reason codes derived from observed feature values, not generated prose.

### Relationship graph

Create account-to-entity relationships for device, IP, payment instrument, email, phone, merchant, and promotion. Project accounts into an undirected graph only when they share a configured meaningful entity. Suppress or down-weight overly common entities so a public IP or popular merchant does not create a giant false ring.

Use NetworkX connected components for the MVP. For each component, compute:

- member count;
- number and types of shared entities;
- graph density;
- promotion-claim concentration;
- mean and maximum account ML score;
- temporal concentration;
- deterministic ring score and reason codes.

Ignore singleton components in the ring list, while retaining their account scores.

### Ring score

Use a documented weighted formula normalized to 0–1. The initial weights are configuration values, not learned parameters. Rank rings by score descending. Do not claim the ring score is a calibrated probability.

### Detection resilience

For review-sized detected rings, compute a separate structural resilience result from the accepted account–entity bipartite graph. Find the minimum number of shared entity nodes whose loss leaves no residual account component containing at least half of the original members; a two-member ring is considered fragmented when only isolated accounts remain. Classify one required loss as `low`, two or three as `moderate`, and four or more as `high`.

`critical_entity_types` is the intersection of entity-type sets across every minimum cut, not a suggested action. The result describes dependence on available evidence; it is not fraud likelihood, real attacker cost, or an evasion playbook. It must not change ring detection, score, rank, thresholds, or review status. Exact analysis is deliberately omitted for unusually broad components with more than 12 accepted shared entities because balanced node-cut search is exponential.

## 9. Evaluation

Use a stratified train/test split with a fixed seed and avoid leaking `ring_label` across splits: all members of a planted ring must remain in the same split.

Report:

- account precision, recall, F1, PR-AUC, and confusion matrix;
- ring precision/recall using planted ring membership overlap;
- top false positives and false negatives with reason codes;
- runtime for the default dataset.

Demo acceptance targets on the default generated dataset:

- account recall at least 0.75 and precision at least 0.60;
- at least 0.80 of planted rings surfaced in the top 20 ranked rings;
- full generation-to-results run under 60 seconds on a typical laptop;
- identical seeded runs produce identical records and scores within normal floating-point tolerance.

These targets validate the demo dataset and pipeline, not real-world effectiveness.

## 10. API contract

JSON REST API under `/api/v1`:

- `GET /health` — liveness and database availability;
- `GET /summary` — counts, score distribution, and review-status totals;
- `GET /reports/current.csv` and `GET /reports/current.json` — download the current ranked ring report;
- `GET /rings` — paginated ranked rings with score/status/date/promotion filters;
- `GET /rings/{ring_id}` — ring details, reasons, detection resilience, members, shared entities, and graph nodes/edges;
- `PATCH /rings/{ring_id}/status` — validate and update review status;
- `GET /accounts/{account_id}` — account score, features, reasons, and transactions.

Responses must use stable field names, return appropriate 4xx errors for invalid input, and publish an OpenAPI schema. Pagination defaults must be bounded.

## 11. Persistence

Persist source records, derived account features/scores, rings, ring membership, shared entities/edges, and review status. SQLite is the local default; PostgreSQL may be used in hosted environments through the same SQLAlchemy models.

Pipeline reruns for the same dataset/run identifier must be idempotent.

## 12. Quality and security

- Validate all imported data and API inputs.
- Keep synthetic identifiers synthetic; never commit secrets or real personal/payment data.
- Configure allowed frontend origins explicitly.
- Use parameterized ORM/database operations.
- Cover feature leakage, graph construction, scoring, API validation, and status updates with focused tests.
- Log pipeline stages and errors without sensitive record contents.

## 13. Delivery and demo

The repository must support:

1. install dependencies;
2. generate seeded demo data;
3. train and evaluate the model;
4. score accounts and detect rings;
5. load results into the database;
6. start the API;
7. run tests.

Prefer a single Python service and process. Deployment must fit a modest/free-tier container host with a small managed PostgreSQL database, or run entirely locally with SQLite. A public deployment is optional if free-tier availability is unreliable.

Demo flow: show dashboard summary, open a high-ranked ring, explain its shared relationships and behavioral signals, inspect one member account, then record a review outcome.

## 14. Definition of done

The MVP is done when a clean checkout can reproduce the seeded dataset and evaluation, populate the database, pass tests, serve the documented API, and provide Antigravity with stable payloads for the complete demo flow.
