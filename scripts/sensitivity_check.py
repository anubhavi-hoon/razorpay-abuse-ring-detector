#!/usr/bin/env python3
"""Standalone diagnostic for sensitivity checks outside the production pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from abuse_detector.data import load_dataset
from abuse_detector.graph import RING_SCORE_WEIGHTS, _jaccard, load_account_scores
from abuse_detector.model import grouped_stratified_split

THRESHOLDS = tuple(value / 100 for value in range(30, 71, 5))
EXPECTED_WEIGHTS = (
    "mean_ml_score",
    "max_ml_score",
    "shared_entity_strength",
    "density",
    "promotion_concentration",
    "temporal_concentration",
)
K_VALUES = (20, 50, 100)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    print(separator)
    print("| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    print(separator)
    for row in rows:
        print("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    print(separator)


def account_sweep(run_dir: Path, seed: int, test_size: float) -> None:
    accounts, _ = load_dataset(run_dir / "raw" / "accounts.csv", run_dir / "raw" / "transactions.csv")
    by_id = {account.account_id: account for account in accounts}
    scores = load_account_scores(run_dir / "artifacts" / "account_scores.csv", set(by_id))
    account_ids = list(scores)
    labels = [by_id[account_id].label for account_id in account_ids]
    rings = [by_id[account_id].ring_label for account_id in account_ids]
    _, test_indices = grouped_stratified_split(account_ids, labels, rings, seed=seed, test_size=test_size)

    rows = []
    for threshold in THRESHOLDS:
        actual = [labels[index] for index in test_indices]
        predicted = [int(float(scores[account_ids[index]]["ml_score"]) >= threshold) for index in test_indices]
        true_positives = sum(expected == predicted_label == 1 for expected, predicted_label in zip(actual, predicted))
        false_positives = sum(expected == 0 and predicted_label == 1 for expected, predicted_label in zip(actual, predicted))
        false_negatives = sum(expected == 1 and predicted_label == 0 for expected, predicted_label in zip(actual, predicted))
        precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 0.0
        recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append(
            (
                f"{threshold:.2f}",
                f"{precision:.6f}",
                f"{recall:.6f}",
                f"{f1:.6f}",
                str(sum(predicted)),
                str(false_positives),
            )
        )

    print("PART 1 — ACCOUNT THRESHOLD SWEEP (held-out test partition)")
    print_table(("threshold", "precision", "recall", "F1", "flagged", "false positives"), rows)


def ring_signals(row: dict[str, str]) -> dict[str, float]:
    return {
        "mean_ml_score": float(row["mean_ml_score"]),
        "max_ml_score": float(row["max_ml_score"]),
        "shared_entity_strength": min(1.0, int(row["shared_entity_count"]) / 3),
        "density": float(row["density"]),
        "promotion_concentration": float(row["promotion_concentration"]),
        "temporal_concentration": float(row["temporal_concentration"]),
    }


def surfaced_planted(
    ranked: list[dict[str, str]],
    detected_members: dict[str, set[str]],
    planted_members: dict[str, set[str]],
    k: int,
) -> set[str]:
    top_sets = [detected_members[row["ring_id"]] for row in ranked[:k]]
    return {
        label
        for label, expected in planted_members.items()
        if max((_jaccard(expected, detected) for detected in top_sets), default=0.0) >= 0.5
    }


def ring_sensitivity(run_dir: Path) -> None:
    assert tuple(RING_SCORE_WEIGHTS) == EXPECTED_WEIGHTS
    assert abs(sum(RING_SCORE_WEIGHTS.values()) - 1.0) < 1e-12
    rings = read_csv(run_dir / "rings" / "rings.csv")
    baseline = sorted(rings, key=lambda row: (-float(row["score"]), row["ring_id"]))
    baseline_top20 = {row["ring_id"] for row in baseline[:20]}

    detected_members: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(run_dir / "rings" / "ring_members.csv"):
        detected_members[row["ring_id"]].add(row["account_id"])
    planted_members: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(run_dir / "processed" / "account_labels.csv"):
        if row["ring_label"]:
            planted_members[row["ring_label"]].add(row["account_id"])
    baseline_surfaced = {
        k: surfaced_planted(baseline, detected_members, planted_members, k) for k in K_VALUES
    }

    rows = []
    for weight_name, baseline_weight in RING_SCORE_WEIGHTS.items():
        for change, factor in (("-20%", 0.8), ("+20%", 1.2)):
            changed = dict(RING_SCORE_WEIGHTS)
            changed[weight_name] *= factor
            total = sum(changed.values())
            normalized = {name: weight / total for name, weight in changed.items()}
            ranked = sorted(
                rings,
                key=lambda row: (
                    -sum(ring_signals(row)[name] * weight for name, weight in normalized.items()),
                    row["ring_id"],
                ),
            )
            dropouts = {
                k: baseline_surfaced[k]
                - surfaced_planted(ranked, detected_members, planted_members, k)
                for k in K_VALUES
            }
            rows.append(
                (
                    weight_name,
                    f"{baseline_weight:.2f}",
                    change,
                    f'{normalized[weight_name]:.6f}',
                    f"{len(baseline_top20 & {row['ring_id'] for row in ranked[:20]})}/20",
                    *("no" if not dropouts[k] else "yes: " + ",".join(sorted(dropouts[k])) for k in K_VALUES),
                )
            )

    print("\nPART 2 — RING-WEIGHT SENSITIVITY")
    print_table(
        ("weight", "baseline", "change", "normalized", "top-20 overlap", "drop@20", "drop@50", "drop@100"),
        rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=REPO_ROOT / "runs" / "demo")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    configuration = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["configuration"]
    account_sweep(run_dir, int(configuration["seed"]), float(configuration["test_size"]))
    ring_sensitivity(run_dir)


if __name__ == "__main__":
    main()
