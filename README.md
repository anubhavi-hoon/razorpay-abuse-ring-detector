# Razorpay Abuse Ring Detector

Buildathon project for detecting coordinated multi-account promotional abuse using lightweight machine learning and relationship/graph analysis.

## Current status

Relationship-graph ring detection is complete. Detection features are implemented milestone by milestone in [`TASKS.md`](TASKS.md).

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

The command suppresses overly common entities, finds non-singleton connected components, and writes ranked rings, memberships, graph nodes/edges, and ring evaluation. The normalized ring score weights mean/max ML score (35%/15%), shared-entity strength (15%), account-link density (10%), promotion concentration (10%), and signup-time concentration (15%); it is a ranking score, not a probability. Override a noise limit with `--max-entity-accounts TYPE=COUNT`.

See [`SPEC.md`](SPEC.md) for the product contract and [`ARCHITECTURE.md`](ARCHITECTURE.md) for technical decisions.
