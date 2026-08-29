# Razorpay Abuse Ring Detector

Buildathon project for detecting coordinated multi-account promotional abuse using lightweight machine learning and relationship/graph analysis.

## Current status

Repository baseline complete. Detection features are implemented milestone by milestone in [`TASKS.md`](TASKS.md).

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

See [`SPEC.md`](SPEC.md) for the product contract and [`ARCHITECTURE.md`](ARCHITECTURE.md) for technical decisions.

