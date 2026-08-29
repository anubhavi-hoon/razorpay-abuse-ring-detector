"""Validate source data and build cutoff-safe account features."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from .data import Account, Transaction, load_dataset, parse_utc_timestamp

FEATURE_DEFINITIONS = {
    "account_age_days": "Days between account creation and the observation cutoff.",
    "transaction_count": "Transactions observed at or before the cutoff.",
    "total_amount": "Total observed transaction amount.",
    "mean_amount": "Mean observed transaction amount.",
    "promotion_claim_count": "Observed transactions with a promotion.",
    "promotion_claim_ratio": "Share of observed transactions with a promotion.",
    "distinct_merchant_count": "Distinct merchants in observed transactions.",
    "distinct_promotion_count": "Distinct promotions in observed transactions.",
    "failure_ratio": "Share of observed transactions that failed.",
    "refund_ratio": "Share of observed transactions that were refunded.",
    "shared_device_accounts": "Other visible accounts using the same device.",
    "shared_ip_accounts": "Other visible accounts using the same IP address.",
    "shared_payment_instrument_accounts": "Other visible accounts using the same payment instrument.",
    "shared_email_accounts": "Other visible accounts using the same email hash.",
    "shared_phone_accounts": "Other visible accounts using the same phone hash.",
    "max_transactions_1h": "Maximum observed transactions in any rolling one-hour window.",
    "max_promotion_claims_1h": "Maximum observed promotion claims in any rolling one-hour window.",
    "time_to_first_promotion_hours": "Hours from signup to first observed promotion, or -1 when absent.",
}
FEATURE_FIELDS = ("account_id", *FEATURE_DEFINITIONS)


def build_account_features(
    accounts: list[Account],
    transactions: list[Transaction],
    cutoff: datetime,
) -> list[dict[str, object]]:
    """Return one deterministic feature row per account visible at cutoff."""
    visible_accounts = sorted(
        (account for account in accounts if parse_utc_timestamp(account.created_at) <= cutoff),
        key=lambda account: account.account_id,
    )
    visible_ids = {account.account_id for account in visible_accounts}
    entity_counts: dict[str, dict[str, set[str]]] = {
        field: defaultdict(set)
        for field in ("device_id", "ip_address", "payment_instrument_id", "email_hash", "phone_hash")
    }
    for account in visible_accounts:
        for field, values in entity_counts.items():
            values[getattr(account, field)].add(account.account_id)

    by_account: dict[str, list[tuple[Transaction, datetime]]] = defaultdict(list)
    for transaction in transactions:
        created = parse_utc_timestamp(transaction.created_at)
        if transaction.account_id in visible_ids and created <= cutoff:
            by_account[transaction.account_id].append((transaction, created))

    rows: list[dict[str, object]] = []
    for account in visible_accounts:
        observed = sorted(by_account[account.account_id], key=lambda item: (item[1], item[0].transaction_id))
        transaction_count = len(observed)
        promotion_times = [created for transaction, created in observed if transaction.promotion_id]
        amounts = [Decimal(transaction.amount) for transaction, _ in observed]
        total_amount = sum(amounts, Decimal())
        account_created = parse_utc_timestamp(account.created_at)
        rows.append(
            {
                "account_id": account.account_id,
                "account_age_days": _rounded((cutoff - account_created).total_seconds() / 86_400),
                "transaction_count": transaction_count,
                "total_amount": float(total_amount),
                "mean_amount": _rounded(float(total_amount / transaction_count)) if transaction_count else 0.0,
                "promotion_claim_count": len(promotion_times),
                "promotion_claim_ratio": _ratio(len(promotion_times), transaction_count),
                "distinct_merchant_count": len({transaction.merchant_id for transaction, _ in observed}),
                "distinct_promotion_count": len(
                    {transaction.promotion_id for transaction, _ in observed if transaction.promotion_id}
                ),
                "failure_ratio": _ratio(
                    sum(transaction.status == "failed" for transaction, _ in observed), transaction_count
                ),
                "refund_ratio": _ratio(
                    sum(transaction.status == "refunded" for transaction, _ in observed), transaction_count
                ),
                "shared_device_accounts": _shared_count(entity_counts, "device_id", account),
                "shared_ip_accounts": _shared_count(entity_counts, "ip_address", account),
                "shared_payment_instrument_accounts": _shared_count(
                    entity_counts, "payment_instrument_id", account
                ),
                "shared_email_accounts": _shared_count(entity_counts, "email_hash", account),
                "shared_phone_accounts": _shared_count(entity_counts, "phone_hash", account),
                "max_transactions_1h": _max_in_window([created for _, created in observed]),
                "max_promotion_claims_1h": _max_in_window(promotion_times),
                "time_to_first_promotion_hours": (
                    _rounded((promotion_times[0] - account_created).total_seconds() / 3_600)
                    if promotion_times
                    else -1.0
                ),
            }
        )
    return rows


def write_feature_outputs(
    accounts_path: Path,
    transactions_path: Path,
    output_dir: Path,
    cutoff: datetime | None = None,
) -> dict[str, object]:
    accounts, transactions = load_dataset(accounts_path, transactions_path)
    if cutoff is None:
        timestamps = [parse_utc_timestamp(account.created_at) for account in accounts]
        timestamps.extend(parse_utc_timestamp(transaction.created_at) for transaction in transactions)
        if not timestamps:
            raise ValueError("source dataset is empty")
        cutoff = max(timestamps)

    features = build_account_features(accounts, transactions, cutoff)
    labels_by_id = {account.account_id: account for account in accounts}
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_dicts(output_dir / "account_features.csv", FEATURE_FIELDS, features)
    _write_dicts(
        output_dir / "account_labels.csv",
        ("account_id", "label", "ring_label"),
        (
            {
                "account_id": row["account_id"],
                "label": labels_by_id[str(row["account_id"])].label,
                "ring_label": labels_by_id[str(row["account_id"])].ring_label,
            }
            for row in features
        ),
    )
    metadata: dict[str, object] = {
        "schema_version": 1,
        "cutoff": cutoff.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "row_count": len(features),
        "features": [
            {"name": name, "description": description}
            for name, description in FEATURE_DEFINITIONS.items()
        ],
        "ground_truth_file": "account_labels.csv",
    }
    (output_dir / "feature_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def _shared_count(
    entity_counts: dict[str, dict[str, set[str]]], field: str, account: Account
) -> int:
    return len(entity_counts[field][getattr(account, field)]) - 1


def _ratio(numerator: int, denominator: int) -> float:
    return _rounded(numerator / denominator) if denominator else 0.0


def _rounded(value: float) -> float:
    return round(value, 6)


def _max_in_window(timestamps: list[datetime]) -> int:
    start = 0
    maximum = 0
    for end, timestamp in enumerate(timestamps):
        while timestamp - timestamps[start] > timedelta(hours=1):
            start += 1
        maximum = max(maximum, end - start + 1)
    return maximum


def _write_dicts(path: Path, fields: tuple[str, ...], rows: object) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", type=Path, default=Path("data/raw/accounts.csv"))
    parser.add_argument("--transactions", type=Path, default=Path("data/raw/transactions.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--cutoff", help="UTC ISO-8601 timestamp; defaults to the latest source event")
    args = parser.parse_args(argv)
    cutoff = parse_utc_timestamp(args.cutoff, "--cutoff") if args.cutoff else None
    metadata = write_feature_outputs(args.accounts, args.transactions, args.output_dir, cutoff)
    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()

