"""Deterministic synthetic data for the abuse-ring demo."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ACCOUNT_FIELDS = (
    "account_id",
    "created_at",
    "email_hash",
    "phone_hash",
    "device_id",
    "ip_address",
    "payment_instrument_id",
    "label",
    "ring_label",
)
TRANSACTION_FIELDS = (
    "transaction_id",
    "account_id",
    "merchant_id",
    "promotion_id",
    "amount",
    "created_at",
    "status",
)
GROUND_TRUTH_FIELDS = ("label", "ring_label")
# Uploaded test data often has no ground truth, so the two trailing label columns
# are optional. Absent or blank label means "unavailable", never "not abusive".
REQUIRED_ACCOUNT_FIELDS = ACCOUNT_FIELDS[: -len(GROUND_TRUTH_FIELDS)]
ANCHOR = datetime(2026, 1, 1, tzinfo=timezone.utc)
RING_SIZE = 5


@dataclass(frozen=True)
class Account:
    account_id: str
    created_at: str
    email_hash: str
    phone_hash: str
    device_id: str
    ip_address: str
    payment_instrument_id: str
    label: int | None
    ring_label: str


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    account_id: str
    merchant_id: str
    promotion_id: str
    amount: str
    created_at: str
    status: str


class DataValidationError(ValueError):
    """Raised when an input CSV violates the source data contract."""


def parse_utc_timestamp(value: str, location: str = "timestamp") -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DataValidationError(f"{location}: invalid ISO-8601 timestamp {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise DataValidationError(f"{location}: timestamp must be UTC")
    return parsed


def load_dataset(accounts_path: Path, transactions_path: Path) -> tuple[list[Account], list[Transaction]]:
    """Load and validate the complete source CSV contract."""
    account_rows = _read_rows(
        accounts_path, ACCOUNT_FIELDS, optional_trailing=len(GROUND_TRUTH_FIELDS)
    )
    transaction_rows = _read_rows(transactions_path, TRANSACTION_FIELDS)

    accounts: list[Account] = []
    account_ids: set[str] = set()
    account_created: dict[str, datetime] = {}
    for row_number, row in enumerate(account_rows, start=2):
        location = f"{accounts_path}:{row_number}"
        _require_values(row, REQUIRED_ACCOUNT_FIELDS, location)
        if row["account_id"] in account_ids:
            raise DataValidationError(f"{location}: duplicate account_id {row['account_id']!r}")
        raw_label = (row.get("label") or "").strip()
        if raw_label not in {"", "0", "1"}:
            raise DataValidationError(f"{location}: label must be 0, 1, or empty")
        created = parse_utc_timestamp(row["created_at"], f"{location} created_at")
        account = Account(
            account_id=row["account_id"],
            created_at=row["created_at"],
            email_hash=row["email_hash"],
            phone_hash=row["phone_hash"],
            device_id=row["device_id"],
            ip_address=row["ip_address"],
            payment_instrument_id=row["payment_instrument_id"],
            label=int(raw_label) if raw_label else None,
            ring_label=row.get("ring_label") or "",
        )
        accounts.append(account)
        account_ids.add(account.account_id)
        account_created[account.account_id] = created

    transactions: list[Transaction] = []
    transaction_ids: set[str] = set()
    for row_number, row in enumerate(transaction_rows, start=2):
        location = f"{transactions_path}:{row_number}"
        required = tuple(field for field in TRANSACTION_FIELDS if field != "promotion_id")
        _require_values(row, required, location)
        if row["transaction_id"] in transaction_ids:
            raise DataValidationError(f"{location}: duplicate transaction_id {row['transaction_id']!r}")
        if row["account_id"] not in account_ids:
            raise DataValidationError(f"{location}: unknown account_id {row['account_id']!r}")
        try:
            amount = Decimal(row["amount"])
        except InvalidOperation as error:
            raise DataValidationError(f"{location}: amount must be numeric") from error
        if not amount.is_finite() or amount < 0:
            raise DataValidationError(f"{location}: amount must be a finite non-negative number")
        if row["status"] not in {"succeeded", "failed", "refunded"}:
            raise DataValidationError(f"{location}: invalid status {row['status']!r}")
        created = parse_utc_timestamp(row["created_at"], f"{location} created_at")
        if created < account_created[row["account_id"]]:
            raise DataValidationError(f"{location}: transaction predates its account")
        transaction = Transaction(**row)
        transactions.append(transaction)
        transaction_ids.add(transaction.transaction_id)

    return accounts, transactions


def _read_rows(
    path: Path, expected_fields: tuple[str, ...], optional_trailing: int = 0
) -> list[dict[str, str]]:
    accepted = {
        expected_fields[: len(expected_fields) - dropped]
        for dropped in range(optional_trailing + 1)
    }
    try:
        with path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if tuple(reader.fieldnames or ()) not in accepted:
                raise DataValidationError(
                    f"{path}: expected columns {expected_fields}, got {tuple(reader.fieldnames or ())}"
                )
            rows = list(reader)
            if any(None in row for row in rows):
                raise DataValidationError(f"{path}: row contains extra columns")
            return rows
    except csv.Error as error:
        raise DataValidationError(f"{path}: malformed CSV: {error}") from error


def _require_values(row: dict[str, str], fields: tuple[str, ...], location: str) -> None:
    missing = [field for field in fields if not row[field]]
    if missing:
        raise DataValidationError(f"{location}: missing value for {', '.join(missing)}")


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _synthetic_hash(kind: str, index: int, seed: int) -> str:
    value = hashlib.sha256(f"{kind}:{seed}:{index}".encode()).hexdigest()[:20]
    return f"{kind}_{value}"


def _weighted_choice(rng: random.Random, choices: tuple[tuple[str, int], ...]) -> str:
    return rng.choices(
        [choice for choice, _ in choices],
        weights=[weight for _, weight in choices],
        k=1,
    )[0]


def generate_dataset(
    output_dir: Path,
    *,
    seed: int = 42,
    account_count: int = 2_000,
    transaction_count: int = 10_000,
    ring_count: int = 15,
) -> dict[str, object]:
    """Write deterministic account, transaction, and manifest files."""
    if ring_count < 1:
        raise ValueError("ring_count must be at least 1")
    if account_count < ring_count * RING_SIZE:
        raise ValueError(f"account_count must be at least ring_count * {RING_SIZE}")
    if transaction_count < account_count:
        raise ValueError("transaction_count must be at least account_count")

    rng = random.Random(seed)
    fraud_count = ring_count * RING_SIZE
    accounts: list[Account] = []

    for index in range(account_count):
        is_fraud = index < fraud_count
        if is_fraud:
            ring_index = index // RING_SIZE
            created = ANCHOR + timedelta(days=ring_index * 2, minutes=rng.randrange(180))
            ring_label = f"ring_{ring_index + 1:03d}"
            device_id = f"device_ring_{ring_index + 1:03d}"
            payment_id = f"payment_ring_{ring_index + 1:03d}"
            ip_address = f"198.51.100.{ring_index % 250 + 1}"
        else:
            legitimate_index = index - fraud_count
            created = ANCHOR + timedelta(days=rng.randrange(90), seconds=rng.randrange(86_400))
            ring_label = ""
            # Some legitimate accounts share household devices/payments and office IPs.
            household = legitimate_index // 2
            device_id = (
                f"device_household_{household:05d}"
                if legitimate_index % 10 < 2
                else f"device_{index:06d}"
            )
            payment_id = (
                f"payment_household_{household:05d}"
                if legitimate_index % 20 < 2
                else f"payment_{index:06d}"
            )
            ip_address = f"203.0.113.{legitimate_index % 80 + 1}"

        accounts.append(
            Account(
                account_id=f"acct_{index + 1:06d}",
                created_at=_timestamp(created),
                email_hash=_synthetic_hash("email", index, seed),
                phone_hash=_synthetic_hash("phone", index, seed),
                device_id=device_id,
                ip_address=ip_address,
                payment_instrument_id=payment_id,
                label=int(is_fraud),
                ring_label=ring_label,
            )
        )

    transactions: list[Transaction] = []
    for index in range(transaction_count):
        account = accounts[index] if index < account_count else rng.choice(accounts)
        account_created = datetime.fromisoformat(account.created_at.replace("Z", "+00:00"))
        if account.label:
            ring_number = int(account.ring_label.removeprefix("ring_"))
            created = account_created + timedelta(minutes=rng.randrange(30, 2_880))
            promotion_id = f"promo_{ring_number % 4 + 1:02d}" if rng.random() < 0.88 else ""
            merchant_id = f"merchant_{ring_number % 8 + 1:03d}"
            status = _weighted_choice(rng, (("succeeded", 55), ("failed", 25), ("refunded", 20)))
            threshold = rng.choice((99, 199, 499))
            amount = threshold + rng.randrange(0, 10)
        else:
            created = account_created + timedelta(minutes=rng.randrange(30, 86_400))
            promotion_id = f"promo_{rng.randrange(1, 13):02d}" if rng.random() < 0.18 else ""
            merchant_id = f"merchant_{rng.randrange(1, 101):03d}"
            status = _weighted_choice(rng, (("succeeded", 92), ("failed", 5), ("refunded", 3)))
            amount = rng.randrange(100, 50_001) / 100

        transactions.append(
            Transaction(
                transaction_id=f"txn_{index + 1:08d}",
                account_id=account.account_id,
                merchant_id=merchant_id,
                promotion_id=promotion_id,
                amount=f"{amount:.2f}",
                created_at=_timestamp(created),
                status=status,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "accounts.csv", ACCOUNT_FIELDS, accounts)
    _write_csv(output_dir / "transactions.csv", TRANSACTION_FIELDS, transactions)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "seed": seed,
        "account_count": account_count,
        "transaction_count": transaction_count,
        "ring_count": ring_count,
        "ring_size": RING_SIZE,
        "ground_truth_fields": list(GROUND_TRUTH_FIELDS),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_csv(path: Path, fields: tuple[str, ...], records: list[object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--accounts", type=int, default=2_000)
    parser.add_argument("--transactions", type=int, default=10_000)
    parser.add_argument("--rings", type=int, default=15)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)
    manifest = generate_dataset(
        args.output_dir,
        seed=args.seed,
        account_count=args.accounts,
        transaction_count=args.transactions,
        ring_count=args.rings,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
