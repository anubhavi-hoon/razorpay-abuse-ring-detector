#!/usr/bin/env python3
"""Standalone diagnostic for comparing scoring variants outside the production pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from abuse_detector.data import Account, load_dataset
from abuse_detector.features import FEATURE_DEFINITIONS
from abuse_detector.graph import RING_SCORE_WEIGHTS, _jaccard, detect_rings
from abuse_detector.model import grouped_stratified_split, load_training_data

SHARED_FEATURES = {
    "shared_device_accounts",
    "shared_ip_accounts",
    "shared_payment_instrument_accounts",
    "shared_email_accounts",
    "shared_phone_accounts",
}
K_VALUES = (20, 50, 100)


def train_variant(
    matrix: list[list[float]],
    labels: list[int],
    train_indices: list[int],
    test_indices: list[int],
    feature_indices: list[int],
    seed: int,
    threshold: float,
) -> tuple[list[float], dict[str, float | int]]:
    selected = lambda index: [matrix[index][column] for column in feature_indices]
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", random_state=seed, max_iter=1_000),
    )
    model.fit([selected(index) for index in train_indices], [labels[index] for index in train_indices])
    scores = [float(score) for score in model.predict_proba([selected(i) for i in range(len(matrix))])[:, 1]]
    actual = [labels[index] for index in test_indices]
    predicted = [int(scores[index] >= threshold) for index in test_indices]
    return scores, {
        "precision": precision_score(actual, predicted, zero_division=0),
        "recall": recall_score(actual, predicted, zero_division=0),
        "f1": f1_score(actual, predicted, zero_division=0),
        "account_candidates": sum(predicted),
    }


def score_rows(account_ids: list[str], scores: list[float], threshold: float) -> dict[str, dict[str, object]]:
    return {
        account_id: {
            "ml_score": score,
            "predicted_label": int(score >= threshold),
            "reason_codes": "",
        }
        for account_id, score in zip(account_ids, scores, strict=True)
    }


def member_sets(result: dict[str, object]) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = defaultdict(set)
    for row in result["members"]:
        sets[str(row["ring_id"])].add(str(row["account_id"]))
    return sets


def ring_metrics(
    accounts: list[Account],
    ranked_rings: list[dict[str, object]],
    detected_members: dict[str, set[str]],
) -> dict[int, tuple[float, float, int]]:
    planted: dict[str, set[str]] = defaultdict(set)
    for account in accounts:
        if account.ring_label:
            planted[account.ring_label].add(account.account_id)

    metrics = {}
    for k in K_VALUES:
        top_sets = [detected_members[str(ring["ring_id"])] for ring in ranked_rings[:k]]
        matched = sum(
            max((_jaccard(expected, detected) for expected in planted.values()), default=0.0) >= 0.5
            for detected in top_sets
        )
        surfaced = sum(
            max((_jaccard(expected, detected) for detected in top_sets), default=0.0) >= 0.5
            for expected in planted.values()
        )
        metrics[k] = (
            matched / len(top_sets) if top_sets else 0.0,
            surfaced / len(planted) if planted else 0.0,
            len(top_sets),
        )
    return metrics


def print_table(
    title: str,
    account_metrics: dict[str, float | int] | None,
    rings: dict[int, tuple[float, float, int]],
    candidate_count: int,
) -> None:
    rows: list[tuple[str, str, str]] = []
    if account_metrics is not None:
        rows.extend(
            [
                ("account", "precision", f'{account_metrics["precision"]:.6f}'),
                ("account", "recall", f'{account_metrics["recall"]:.6f}'),
                ("account", "F1", f'{account_metrics["f1"]:.6f}'),
                ("workload", "held-out account candidates", str(account_metrics["account_candidates"])),
            ]
        )
    for k, (precision, recall, workload) in rings.items():
        rows.extend(
            [
                ("ring", f"precision@{k}", f"{precision:.6f}"),
                ("ring", f"recall@{k}", f"{recall:.6f}"),
                ("workload", f"rings reviewed@{k}", str(workload)),
            ]
        )
    rows.append(("workload", "ring candidates", str(candidate_count)))
    headers = ("scope", "metric", "value")
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(3)]
    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    print(f"\n{title}")
    print(separator)
    print("| " + " | ".join(headers[i].ljust(widths[i]) for i in range(3)) + " |")
    print(separator)
    for row in rows:
        print("| " + " | ".join(row[i].ljust(widths[i]) for i in range(3)) + " |")
    print(separator)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=REPO_ROOT / "runs" / "demo")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    configuration = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["configuration"]
    seed = int(configuration["seed"])
    test_size = float(configuration["test_size"])
    threshold = float(configuration["threshold"])

    account_ids, matrix, labels, ring_labels, _ = load_training_data(
        run_dir / "processed" / "account_features.csv",
        run_dir / "processed" / "account_labels.csv",
    )
    train_indices, test_indices = grouped_stratified_split(
        account_ids, labels, ring_labels, seed=seed, test_size=test_size
    )
    feature_names = list(FEATURE_DEFINITIONS)
    full_indices = list(range(len(feature_names)))
    behaviour_indices = [i for i, name in enumerate(feature_names) if name not in SHARED_FEATURES]
    assert len(full_indices) == 18 and len(behaviour_indices) == 13

    full_scores, full_account_metrics = train_variant(
        matrix, labels, train_indices, test_indices, full_indices, seed, threshold
    )
    behaviour_scores, behaviour_account_metrics = train_variant(
        matrix, labels, train_indices, test_indices, behaviour_indices, seed, threshold
    )
    accounts, transactions = load_dataset(
        run_dir / "raw" / "accounts.csv", run_dir / "raw" / "transactions.csv"
    )
    full_result = detect_rings(accounts, transactions, score_rows(account_ids, full_scores, threshold))
    behaviour_result = detect_rings(
        accounts, transactions, score_rows(account_ids, behaviour_scores, threshold)
    )
    full_members = member_sets(full_result)
    behaviour_members = member_sets(behaviour_result)
    assert full_members == behaviour_members

    full_lr_rings = sorted(
        full_result["rings"], key=lambda row: (-float(row["mean_ml_score"]), str(row["ring_id"]))
    )
    behaviour_lr_rings = sorted(
        behaviour_result["rings"],
        key=lambda row: (-float(row["mean_ml_score"]), str(row["ring_id"])),
    )
    graph_weight = sum(
        RING_SCORE_WEIGHTS[name]
        for name in (
            "shared_entity_strength",
            "density",
            "promotion_concentration",
            "temporal_concentration",
        )
    )
    graph_only_rings = sorted(
        full_result["rings"],
        key=lambda row: (
            -(
                RING_SCORE_WEIGHTS["shared_entity_strength"]
                * min(1.0, int(row["shared_entity_count"]) / 3)
                + RING_SCORE_WEIGHTS["density"] * float(row["density"])
                + RING_SCORE_WEIGHTS["promotion_concentration"]
                * float(row["promotion_concentration"])
                + RING_SCORE_WEIGHTS["temporal_concentration"]
                * float(row["temporal_concentration"])
            )
            / graph_weight,
            str(row["ring_id"]),
        ),
    )
    hybrid_rings = list(full_result["rings"])

    variants = (
        ("FULL LR (18 features; mean member LR ranking)", full_account_metrics, full_lr_rings),
        ("BEHAVIOUR-ONLY LR (13 features; mean member LR ranking)", behaviour_account_metrics, behaviour_lr_rings),
        ("GRAPH-ONLY RANKING (no account ML score)", None, graph_only_rings),
        ("CURRENT HYBRID (existing combined ring score)", full_account_metrics, hybrid_rings),
    )
    for title, account_metrics, ranked_rings in variants:
        metrics = ring_metrics(accounts, ranked_rings, full_members)
        assert all(0 <= value <= 1 for precision, recall, _ in metrics.values() for value in (precision, recall))
        print_table(title, account_metrics, metrics, len(ranked_rings))


if __name__ == "__main__":
    main()
