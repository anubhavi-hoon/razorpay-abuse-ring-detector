# Razorpay Abuse Ring Detector

Buildathon project for detecting coordinated multi-account promotional abuse using lightweight machine learning and relationship/graph analysis.

## Current status

Seeded synthetic data generation is complete. Detection features are implemented milestone by milestone in [`TASKS.md`](TASKS.md).

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

See [`SPEC.md`](SPEC.md) for the product contract and [`ARCHITECTURE.md`](ARCHITECTURE.md) for technical decisions.
