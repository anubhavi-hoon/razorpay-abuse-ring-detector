"""Detect coordinated abuse rings from shared entities and account scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx

from .data import Account, Transaction, load_dataset, parse_utc_timestamp

SCORE_FIELDS = ("account_id", "ml_score", "predicted_label", "reason_codes")
DEFAULT_MAX_ENTITY_ACCOUNTS = {
    "device": 10,
    "ip": 10,
    "payment_instrument": 10,
    "email": 5,
    "phone": 5,
    "merchant": 6,
    "promotion": 10,
}
RING_SCORE_WEIGHTS = {
    "mean_ml_score": 0.35,
    "max_ml_score": 0.15,
    "shared_entity_strength": 0.15,
    "density": 0.10,
    "promotion_concentration": 0.10,
    "temporal_concentration": 0.15,
}
RING_FIELDS = (
    "ring_id",
    "score",
    "member_count",
    "shared_entity_count",
    "entity_types",
    "density",
    "promotion_concentration",
    "mean_ml_score",
    "max_ml_score",
    "temporal_concentration",
    "reason_codes",
    "detection_resilience",
    "min_entity_removals",
    "critical_entity_types",
)


def load_account_scores(path: Path, account_ids: set[str]) -> dict[str, dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != SCORE_FIELDS:
            raise ValueError(f"{path}: unexpected columns")
        rows = list(reader)
    scores: dict[str, dict[str, object]] = {}
    for row_number, row in enumerate(rows, start=2):
        account_id = row["account_id"]
        if account_id in scores:
            raise ValueError(f"{path}:{row_number}: duplicate account_id {account_id!r}")
        try:
            score = float(row["ml_score"])
        except ValueError as error:
            raise ValueError(f"{path}:{row_number}: ml_score must be numeric") from error
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"{path}:{row_number}: ml_score must be between 0 and 1")
        if row["predicted_label"] not in {"0", "1"}:
            raise ValueError(f"{path}:{row_number}: predicted_label must be 0 or 1")
        scores[account_id] = {
            "ml_score": score,
            "predicted_label": int(row["predicted_label"]),
            "reason_codes": row["reason_codes"],
        }
    if set(scores) != account_ids:
        raise ValueError("account score IDs do not match source account IDs")
    return scores


def detect_rings(
    accounts: list[Account],
    transactions: list[Transaction],
    scores: dict[str, dict[str, object]],
    max_entity_accounts: dict[str, int] | None = None,
) -> dict[str, object]:
    limits = dict(DEFAULT_MAX_ENTITY_ACCOUNTS)
    if max_entity_accounts:
        limits.update(max_entity_accounts)
    if set(limits) != set(DEFAULT_MAX_ENTITY_ACCOUNTS) or any(limit < 2 for limit in limits.values()):
        raise ValueError("entity limits must define every known type with values of at least 2")

    account_by_id = {account.account_id: account for account in accounts}
    entity_accounts: dict[tuple[str, str], set[str]] = defaultdict(set)
    account_entities = (
        ("device", "device_id"),
        ("ip", "ip_address"),
        ("payment_instrument", "payment_instrument_id"),
        ("email", "email_hash"),
        ("phone", "phone_hash"),
    )
    for account in accounts:
        for entity_type, field in account_entities:
            entity_accounts[(entity_type, getattr(account, field))].add(account.account_id)
    for transaction in transactions:
        entity_accounts[("merchant", transaction.merchant_id)].add(transaction.account_id)
        if transaction.promotion_id:
            entity_accounts[("promotion", transaction.promotion_id)].add(transaction.account_id)

    accepted = {
        key: members
        for key, members in entity_accounts.items()
        if 2 <= len(members) <= limits[key[0]]
    }
    graph = nx.Graph()
    graph.add_nodes_from(account_by_id)
    for key in sorted(accepted):
        for left, right in combinations(sorted(accepted[key]), 2):
            graph.add_edge(left, right)

    transactions_by_account: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        transactions_by_account[transaction.account_id].append(transaction)

    components = sorted(
        (tuple(sorted(component)) for component in nx.connected_components(graph) if len(component) > 1),
        key=lambda members: members,
    )
    rings: list[dict[str, object]] = []
    members_out: list[dict[str, object]] = []
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    member_sets: dict[str, set[str]] = {}
    for members in components:
        member_set = set(members)
        shared_entities = [
            (key, sorted(entity_members & member_set))
            for key, entity_members in sorted(accepted.items())
            if len(entity_members & member_set) >= 2
        ]
        ring_id = "ring_" + hashlib.sha256("\n".join(members).encode()).hexdigest()[:12]
        member_sets[ring_id] = member_set
        member_scores = [float(scores[account_id]["ml_score"]) for account_id in members]
        density = nx.density(graph.subgraph(members))
        promotions = Counter(
            transaction.promotion_id
            for account_id in members
            for transaction in transactions_by_account[account_id]
            if transaction.promotion_id
        )
        promotion_concentration = max(promotions.values()) / sum(promotions.values()) if promotions else 0.0
        created = [parse_utc_timestamp(account_by_id[account_id].created_at) for account_id in members]
        temporal_concentration = 1 - min(1.0, (max(created) - min(created)).total_seconds() / (7 * 86_400))
        signals = {
            "mean_ml_score": sum(member_scores) / len(member_scores),
            "max_ml_score": max(member_scores),
            "shared_entity_strength": min(1.0, len(shared_entities) / 3),
            "density": density,
            "promotion_concentration": promotion_concentration,
            "temporal_concentration": temporal_concentration,
        }
        ring_score = sum(signals[name] * weight for name, weight in RING_SCORE_WEIGHTS.items())
        entity_types = sorted({key[0] for key, _ in shared_entities})
        reasons = ring_reason_codes(signals, entity_types)
        resilience, min_removals, critical_types = detection_resilience(
            members, shared_entities
        )
        rings.append(
            {
                "ring_id": ring_id,
                "score": round(ring_score, 8),
                "member_count": len(members),
                "shared_entity_count": len(shared_entities),
                "entity_types": ";".join(entity_types),
                "density": round(density, 6),
                "promotion_concentration": round(promotion_concentration, 6),
                "mean_ml_score": round(signals["mean_ml_score"], 8),
                "max_ml_score": round(signals["max_ml_score"], 8),
                "temporal_concentration": round(temporal_concentration, 6),
                "reason_codes": ";".join(reasons),
                "detection_resilience": resilience,
                "min_entity_removals": min_removals,
                "critical_entity_types": ";".join(critical_types),
            }
        )
        for account_id in members:
            members_out.append(
                {
                    "ring_id": ring_id,
                    "account_id": account_id,
                    "ml_score": scores[account_id]["ml_score"],
                    "reason_codes": scores[account_id]["reason_codes"],
                }
            )
            nodes.append(
                {"ring_id": ring_id, "node_id": account_id, "node_type": "account", "label": account_id}
            )
        for (entity_type, value), entity_members in shared_entities:
            entity_id = f"{entity_type}:{value}"
            nodes.append(
                {"ring_id": ring_id, "node_id": entity_id, "node_type": entity_type, "label": value}
            )
            edges.extend(
                {
                    "ring_id": ring_id,
                    "source": account_id,
                    "target": entity_id,
                    "relationship_type": entity_type,
                }
                for account_id in entity_members
            )

    rings.sort(key=lambda row: (-float(row["score"]), str(row["ring_id"])))
    rank = {str(row["ring_id"]): index for index, row in enumerate(rings)}
    members_out.sort(key=lambda row: (rank[str(row["ring_id"])], str(row["account_id"])))
    nodes.sort(key=lambda row: (rank[row["ring_id"]], row["node_type"], row["node_id"]))
    edges.sort(key=lambda row: (rank[row["ring_id"]], row["relationship_type"], row["source"], row["target"]))
    evaluation = evaluate_rings(accounts, rings, member_sets)
    evaluation["score_weights"] = RING_SCORE_WEIGHTS
    evaluation["largest_component"] = max((len(members) for members in components), default=0)
    return {"rings": rings, "members": members_out, "nodes": nodes, "edges": edges, "evaluation": evaluation}


def detection_resilience(
    members: tuple[str, ...],
    shared_entities: list[tuple[tuple[str, str], list[str]]],
) -> tuple[str | None, int | None, list[str]]:
    """Find the smallest shared-evidence loss that fragments a detected ring."""
    # ponytail: balanced node cuts are exponential; keep the exact result for
    # normal review-sized rings and leave unusually broad components unassessed.
    if len(shared_entities) > 12:
        return None, None, []
    largest_allowed = max(1, (len(members) - 1) // 2)
    minimum_cuts: list[tuple[int, ...]] = []
    for removal_count in range(1, len(shared_entities) + 1):
        for removed in combinations(range(len(shared_entities)), removal_count):
            residual = nx.Graph()
            residual.add_nodes_from(members)
            for index, (_, entity_members) in enumerate(shared_entities):
                if index not in removed:
                    residual.add_edges_from(combinations(entity_members, 2))
            if max(map(len, nx.connected_components(residual)), default=0) <= largest_allowed:
                minimum_cuts.append(removed)
        if minimum_cuts:
            break

    critical_types = set.intersection(
        *(
            {shared_entities[index][0][0] for index in cut}
            for cut in minimum_cuts
        )
    )
    level = "low" if removal_count == 1 else "moderate" if removal_count <= 3 else "high"
    return level, removal_count, sorted(critical_types)


def ring_reason_codes(signals: dict[str, float], entity_types: list[str]) -> list[str]:
    checks = (
        ("HIGH_MEAN_ML_SCORE", signals["mean_ml_score"] >= 0.7),
        ("MULTIPLE_SHARED_ENTITIES", signals["shared_entity_strength"] >= 2 / 3),
        ("DENSE_ACCOUNT_LINKS", signals["density"] >= 0.6),
        ("CONCENTRATED_PROMOTIONS", signals["promotion_concentration"] >= 0.7),
        ("CLUSTERED_ACCOUNT_CREATION", signals["temporal_concentration"] >= 0.7),
        ("SHARED_PAYMENT_INSTRUMENT", "payment_instrument" in entity_types),
        ("SHARED_DEVICE", "device" in entity_types),
    )
    return [code for code, applies in checks if applies]


def evaluate_rings(
    accounts: list[Account],
    rings: list[dict[str, object]],
    member_sets: dict[str, set[str]],
) -> dict[str, object]:
    planted: dict[str, set[str]] = defaultdict(set)
    for account in accounts:
        if account.ring_label:
            planted[account.ring_label].add(account.account_id)
    top = rings[:20]
    top_sets = [member_sets[str(ring["ring_id"])] for ring in top]
    surfaced = [
        label
        for label, expected in sorted(planted.items())
        if max((_jaccard(expected, detected) for detected in top_sets), default=0.0) >= 0.5
    ]
    matched_detections = sum(
        max((_jaccard(expected, detected) for expected in planted.values()), default=0.0) >= 0.5
        for detected in top_sets
    )
    # No ring labels means no ground truth, so recall/precision are unavailable.
    # Reporting 0.0 would read as "the detector missed everything" instead.
    return {
        "planted_ring_count": len(planted),
        "detected_ring_count": len(rings),
        "top20_ring_recall": round(len(surfaced) / len(planted), 6) if planted else None,
        "top20_ring_precision": (
            round(matched_detections / len(top_sets), 6) if planted and top_sets else None
        ),
        "surfaced_planted_rings": surfaced,
    }


def write_ring_outputs(
    accounts_path: Path,
    transactions_path: Path,
    scores_path: Path,
    output_dir: Path,
    max_entity_accounts: dict[str, int] | None = None,
) -> dict[str, object]:
    accounts, transactions = load_dataset(accounts_path, transactions_path)
    scores = load_account_scores(scores_path, {account.account_id for account in accounts})
    result = detect_rings(accounts, transactions, scores, max_entity_accounts)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "rings.csv", RING_FIELDS, result["rings"])
    _write_csv(
        output_dir / "ring_members.csv",
        ("ring_id", "account_id", "ml_score", "reason_codes"),
        result["members"],
    )
    _write_csv(
        output_dir / "graph_nodes.csv",
        ("ring_id", "node_id", "node_type", "label"),
        result["nodes"],
    )
    _write_csv(
        output_dir / "graph_edges.csv",
        ("ring_id", "source", "target", "relationship_type"),
        result["edges"],
    )
    (output_dir / "ring_evaluation.json").write_text(
        json.dumps(result["evaluation"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result["evaluation"]


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right)


def _write_csv(path: Path, fields: tuple[str, ...], rows: object) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _parse_limits(values: list[str]) -> dict[str, int]:
    limits = dict(DEFAULT_MAX_ENTITY_ACCOUNTS)
    for value in values:
        try:
            entity_type, raw_limit = value.split("=", 1)
            limit = int(raw_limit)
        except ValueError as error:
            raise ValueError("--max-entity-accounts must use TYPE=COUNT") from error
        if entity_type not in limits or limit < 2:
            raise ValueError(f"invalid entity limit {value!r}")
        limits[entity_type] = limit
    return limits


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", type=Path, default=Path("data/raw/accounts.csv"))
    parser.add_argument("--transactions", type=Path, default=Path("data/raw/transactions.csv"))
    parser.add_argument("--scores", type=Path, default=Path("artifacts/account_scores.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/rings"))
    parser.add_argument("--max-entity-accounts", action="append", default=[], metavar="TYPE=COUNT")
    args = parser.parse_args(argv)
    evaluation = write_ring_outputs(
        args.accounts,
        args.transactions,
        args.scores,
        args.output_dir,
        _parse_limits(args.max_entity_accounts),
    )
    print(json.dumps(evaluation, sort_keys=True))


if __name__ == "__main__":
    main()
