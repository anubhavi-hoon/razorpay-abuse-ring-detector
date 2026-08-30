"""Run the complete synthetic-data abuse detection pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import time
from pathlib import Path

from . import __version__
from .data import generate_dataset
from .features import write_feature_outputs
from .graph import write_ring_outputs
from .model import (
    load_artifact,
    load_training_data,
    score_accounts,
    train_and_evaluate,
    write_account_scores,
)

RUN_SCHEMA_VERSION = 1
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def run_pipeline(
    output_root: Path,
    run_id: str,
    *,
    seed: int = 42,
    account_count: int = 2_000,
    transaction_count: int = 10_000,
    ring_count: int = 15,
    test_size: float = 0.25,
    threshold: float = 0.5,
    model_artifact: Path | None = None,
) -> dict[str, object]:
    """Create one atomic, reproducible pipeline run or return its completed result."""
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id must contain 1-64 letters, numbers, underscores, or hyphens")
    external_artifact = load_artifact(model_artifact) if model_artifact else None
    model_hash = hashlib.sha256(model_artifact.read_bytes()).hexdigest() if model_artifact else None
    config = {
        "seed": seed,
        "account_count": account_count,
        "transaction_count": transaction_count,
        "ring_count": ring_count,
        "test_size": test_size if external_artifact is None else None,
        "threshold": threshold if external_artifact is None else external_artifact["threshold"],
        "model_source": "trained" if model_artifact is None else f"sha256:{model_hash}",
    }
    destination = output_root / run_id
    if destination.exists():
        return _load_completed_run(destination, config)

    output_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    timings: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix=f".{run_id}-", dir=output_root) as temporary:
        workspace = Path(temporary)
        raw = workspace / "raw"
        processed = workspace / "processed"
        artifacts = workspace / "artifacts"
        rings = workspace / "rings"

        stage_started = time.perf_counter()
        source_manifest = generate_dataset(
            raw,
            seed=seed,
            account_count=account_count,
            transaction_count=transaction_count,
            ring_count=ring_count,
        )
        timings["generate"] = _elapsed(stage_started)

        stage_started = time.perf_counter()
        feature_metadata = write_feature_outputs(
            raw / "accounts.csv", raw / "transactions.csv", processed
        )
        timings["features"] = _elapsed(stage_started)

        stage_started = time.perf_counter()
        if model_artifact is None:
            account_evaluation = train_and_evaluate(
                processed / "account_features.csv",
                processed / "account_labels.csv",
                artifacts,
                seed=seed,
                test_size=test_size,
                threshold=threshold,
            )
            artifact = load_artifact(artifacts / "model.pkl")
        else:
            artifacts.mkdir(parents=True)
            shutil.copyfile(model_artifact, artifacts / "model.pkl")
            artifact = external_artifact
            account_ids, _, _, _, numeric_rows = load_training_data(
                processed / "account_features.csv", processed / "account_labels.csv"
            )
            write_account_scores(
                artifacts / "account_scores.csv",
                score_accounts(artifact, account_ids, numeric_rows),
            )
            account_evaluation = None
        timings["model"] = _elapsed(stage_started)

        stage_started = time.perf_counter()
        ring_evaluation = write_ring_outputs(
            raw / "accounts.csv",
            raw / "transactions.csv",
            artifacts / "account_scores.csv",
            rings,
        )
        timings["graph"] = _elapsed(stage_started)
        timings["total"] = _elapsed(started)

        outputs = [
            "raw/accounts.csv",
            "raw/transactions.csv",
            "raw/manifest.json",
            "processed/account_features.csv",
            "processed/account_labels.csv",
            "processed/feature_metadata.json",
            "artifacts/model.pkl",
            "artifacts/account_scores.csv",
            "rings/rings.csv",
            "rings/ring_members.csv",
            "rings/graph_nodes.csv",
            "rings/graph_edges.csv",
            "rings/ring_evaluation.json",
        ]
        if account_evaluation is not None:
            outputs.append("artifacts/evaluation.json")
        report: dict[str, object] = {
            "schema_version": RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "status": "complete",
            "artifact_versions": {
                "package": __version__,
                "model": artifact["schema_version"],
                "run_manifest": RUN_SCHEMA_VERSION,
            },
            "configuration": config,
            "counts": {
                "accounts": source_manifest["account_count"],
                "transactions": source_manifest["transaction_count"],
                "features": feature_metadata["row_count"],
                "account_scores": feature_metadata["row_count"],
                "rings": ring_evaluation["detected_ring_count"],
            },
            "metrics": {
                "account": account_evaluation["metrics"] if account_evaluation else None,
                "ring": ring_evaluation,
            },
            "timings_seconds": timings,
            "outputs": sorted(outputs),
        }
        (workspace / "run.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        workspace.replace(destination)
    return report


def _load_completed_run(destination: Path, config: dict[str, object]) -> dict[str, object]:
    manifest_path = destination / "run.json"
    try:
        report = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"run {destination.name!r} exists but is incomplete") from error
    if report.get("status") != "complete" or report.get("configuration") != config:
        raise ValueError(f"run {destination.name!r} already exists with different or incomplete configuration")
    outputs = report.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError(f"run {destination.name!r} has an invalid output manifest")
    missing = [path for path in outputs if not isinstance(path, str) or not (destination / path).is_file()]
    if missing:
        raise ValueError(f"run {destination.name!r} is missing outputs: {', '.join(missing)}")
    return report


def _elapsed(started: float) -> float:
    return round(time.perf_counter() - started, 6)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="demo")
    parser.add_argument("--output-root", type=Path, default=Path("runs"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--accounts", type=int, default=2_000)
    parser.add_argument("--transactions", type=int, default=10_000)
    parser.add_argument("--rings", type=int, default=15)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--model-artifact", type=Path)
    args = parser.parse_args(argv)
    report = run_pipeline(
        args.output_root,
        args.run_id,
        seed=args.seed,
        account_count=args.accounts,
        transaction_count=args.transactions,
        ring_count=args.rings,
        test_size=args.test_size,
        threshold=args.threshold,
        model_artifact=args.model_artifact,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
