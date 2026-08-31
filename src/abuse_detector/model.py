"""Train and evaluate the account-level abuse baseline."""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import random
import time
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_DEFINITIONS, FEATURE_FIELDS

LABEL_FIELDS = ("account_id", "label", "ring_label")


def load_training_data(
    features_path: Path, labels_path: Path
) -> tuple[list[str], list[list[float]], list[int | None], list[str], list[dict[str, float]]]:
    feature_rows = _read_csv(features_path, FEATURE_FIELDS)
    label_rows = _read_csv(labels_path, LABEL_FIELDS)
    labels_by_id: dict[str, tuple[int, str]] = {}
    for row_number, row in enumerate(label_rows, start=2):
        account_id = row["account_id"]
        if not account_id or account_id in labels_by_id:
            raise ValueError(f"{labels_path}:{row_number}: missing or duplicate account_id")
        if row["label"] not in {"", "0", "1"}:
            raise ValueError(f"{labels_path}:{row_number}: label must be 0, 1, or empty")
        if row["label"] == "1" and not row["ring_label"]:
            raise ValueError(f"{labels_path}:{row_number}: abusive account requires ring_label")
        labels_by_id[account_id] = (
            int(row["label"]) if row["label"] else None,
            row["ring_label"],
        )

    account_ids: list[str] = []
    matrix: list[list[float]] = []
    labels: list[int] = []
    rings: list[str] = []
    numeric_rows: list[dict[str, float]] = []
    seen: set[str] = set()
    for row_number, row in enumerate(feature_rows, start=2):
        account_id = row["account_id"]
        if not account_id or account_id in seen:
            raise ValueError(f"{features_path}:{row_number}: missing or duplicate account_id")
        if account_id not in labels_by_id:
            raise ValueError(f"{features_path}:{row_number}: missing label for {account_id!r}")
        try:
            numeric = {name: float(row[name]) for name in FEATURE_DEFINITIONS}
        except ValueError as error:
            raise ValueError(f"{features_path}:{row_number}: features must be numeric") from error
        if not all(math.isfinite(value) for value in numeric.values()):
            raise ValueError(f"{features_path}:{row_number}: features must be finite")
        label, ring = labels_by_id[account_id]
        account_ids.append(account_id)
        matrix.append([numeric[name] for name in FEATURE_DEFINITIONS])
        labels.append(label)
        rings.append(ring)
        numeric_rows.append(numeric)
        seen.add(account_id)

    if seen != set(labels_by_id):
        raise ValueError("feature and label account IDs do not match")
    return account_ids, matrix, labels, rings, numeric_rows


def grouped_stratified_split(
    account_ids: list[str],
    labels: list[int | None],
    rings: list[str],
    *,
    seed: int = 42,
    test_size: float = 0.25,
) -> tuple[list[int], list[int]]:
    """Split each class while keeping every planted ring in one partition."""
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")
    fraud_groups: dict[str, list[int]] = {}
    legitimate: list[int] = []
    for index, (label, ring) in enumerate(zip(labels, rings, strict=True)):
        if label:
            fraud_groups.setdefault(ring, []).append(index)
        else:
            legitimate.append(index)
    if len(fraud_groups) < 2 or len(legitimate) < 2:
        raise ValueError("training requires at least two abuse rings and two legitimate accounts")

    rng = random.Random(seed)
    fraud_names = sorted(fraud_groups)
    rng.shuffle(fraud_names)
    rng.shuffle(legitimate)
    fraud_test_count = _bounded_test_count(len(fraud_names), test_size)
    legitimate_test_count = _bounded_test_count(len(legitimate), test_size)
    test = set(legitimate[:legitimate_test_count])
    for ring in fraud_names[:fraud_test_count]:
        test.update(fraud_groups[ring])
    train = [index for index in range(len(account_ids)) if index not in test]
    return train, sorted(test)


def train_and_evaluate(
    features_path: Path,
    labels_path: Path,
    output_dir: Path,
    *,
    seed: int = 42,
    test_size: float = 0.25,
    threshold: float = 0.5,
) -> dict[str, object]:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    started = time.perf_counter()
    account_ids, matrix, labels, rings, numeric_rows = load_training_data(features_path, labels_path)
    if any(label is None for label in labels):
        raise ValueError("training requires a label for every account")
    train_indices, test_indices = grouped_stratified_split(
        account_ids, labels, rings, seed=seed, test_size=test_size
    )
    pipeline = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", random_state=seed, max_iter=1_000),
    )
    pipeline.fit([matrix[index] for index in train_indices], [labels[index] for index in train_indices])
    artifact = {
        "schema_version": 1,
        "pipeline": pipeline,
        "feature_names": tuple(FEATURE_DEFINITIONS),
        "threshold": threshold,
    }

    test_scores = pipeline.predict_proba([matrix[index] for index in test_indices])[:, 1]
    test_labels = [labels[index] for index in test_indices]
    test_predictions = [int(score >= threshold) for score in test_scores]
    all_scores = pipeline.predict_proba(matrix)[:, 1]
    score_rows = score_accounts(artifact, account_ids, numeric_rows, all_scores)
    score_by_id = {row["account_id"]: row for row in score_rows}
    errors = [
        {
            "account_id": account_ids[index],
            "ml_score": score_by_id[account_ids[index]]["ml_score"],
            "reason_codes": score_by_id[account_ids[index]]["reason_codes"],
        }
        for index in test_indices
    ]
    false_positives = sorted(
        (
            error
            for error, actual, predicted in zip(errors, test_labels, test_predictions, strict=True)
            if actual == 0 and predicted == 1
        ),
        key=lambda row: (-float(row["ml_score"]), str(row["account_id"])),
    )[:5]
    false_negatives = sorted(
        (
            error
            for error, actual, predicted in zip(errors, test_labels, test_predictions, strict=True)
            if actual == 1 and predicted == 0
        ),
        key=lambda row: (float(row["ml_score"]), str(row["account_id"])),
    )[:5]
    evaluation: dict[str, object] = {
        "schema_version": 1,
        "metrics_scope": "held_out_test",
        "seed": seed,
        "test_size": test_size,
        "threshold": threshold,
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "train_ring_labels": sorted({rings[index] for index in train_indices if rings[index]}),
        "test_ring_labels": sorted({rings[index] for index in test_indices if rings[index]}),
        "metrics": {
            "precision": round(precision_score(test_labels, test_predictions, zero_division=0), 6),
            "recall": round(recall_score(test_labels, test_predictions, zero_division=0), 6),
            "f1": round(f1_score(test_labels, test_predictions, zero_division=0), 6),
            "pr_auc": round(average_precision_score(test_labels, test_scores), 6),
            "confusion_matrix": confusion_matrix(
                test_labels, test_predictions, labels=[0, 1]
            ).tolist(),
        },
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "runtime_seconds": round(time.perf_counter() - started, 6),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "model.pkl").open("wb") as file:
        pickle.dump(artifact, file)
    write_account_scores(output_dir / "account_scores.csv", score_rows)
    (output_dir / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evaluation


def load_artifact(path: Path) -> dict[str, object]:
    """Load a trusted local model artifact."""
    with path.open("rb") as file:
        return pickle.load(file)


def score_accounts(
    artifact: dict[str, object],
    account_ids: list[str],
    numeric_rows: list[dict[str, float]],
    scores: object | None = None,
) -> list[dict[str, object]]:
    feature_names = artifact["feature_names"]
    if tuple(feature_names) != tuple(FEATURE_DEFINITIONS):
        raise ValueError("model feature names do not match the current feature contract")
    if scores is None:
        matrix = [[row[name] for name in feature_names] for row in numeric_rows]
        scores = artifact["pipeline"].predict_proba(matrix)[:, 1]
    threshold = float(artifact["threshold"])
    return [
        {
            "account_id": account_id,
            "ml_score": round(float(score), 8),
            "predicted_label": int(float(score) >= threshold),
            "reason_codes": ";".join(reason_codes(row)),
        }
        for account_id, row, score in zip(account_ids, numeric_rows, scores, strict=True)
    ]


def reason_codes(row: dict[str, float]) -> list[str]:
    checks = (
        ("SHARED_PAYMENT_INSTRUMENT", row["shared_payment_instrument_accounts"] >= 1),
        ("SHARED_DEVICE", row["shared_device_accounts"] >= 1),
        ("RAPID_PROMO_CLAIMS", row["max_promotion_claims_1h"] >= 2),
        ("HIGH_PROMOTION_RATIO", row["promotion_claim_ratio"] >= 0.6),
        ("HIGH_FAILURE_RATIO", row["failure_ratio"] >= 0.2),
        ("HIGH_REFUND_RATIO", row["refund_ratio"] >= 0.15),
        ("EARLY_PROMOTION_USE", 0 <= row["time_to_first_promotion_hours"] <= 48),
    )
    return [code for code, applies in checks if applies][:3]


def _bounded_test_count(count: int, test_size: float) -> int:
    return max(1, min(count - 1, round(count * test_size)))


def _read_csv(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != expected_fields:
            raise ValueError(f"{path}: unexpected columns")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"{path}: row contains extra columns")
    return rows


def write_account_scores(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=("account_id", "ml_score", "predicted_label", "reason_codes")
        )
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, default=Path("data/processed/account_features.csv"))
    parser.add_argument("--labels", type=Path, default=Path("data/processed/account_labels.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)
    evaluation = train_and_evaluate(
        args.features,
        args.labels,
        args.output_dir,
        seed=args.seed,
        test_size=args.test_size,
        threshold=args.threshold,
    )
    print(json.dumps(evaluation, sort_keys=True))


if __name__ == "__main__":
    main()
