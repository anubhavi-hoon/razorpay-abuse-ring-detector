import csv
import json
import tempfile
import unittest
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from abuse_detector.data import (
    ACCOUNT_FIELDS,
    TRANSACTION_FIELDS,
    Account,
    DataValidationError,
    Transaction,
    generate_dataset,
    load_dataset,
)
from abuse_detector.features import FEATURE_DEFINITIONS, build_account_features, write_feature_outputs


def account(account_id, created_at="2026-01-01T00:00:00Z", **changes):
    values = {
        "account_id": account_id,
        "created_at": created_at,
        "email_hash": f"email_{account_id}",
        "phone_hash": f"phone_{account_id}",
        "device_id": "shared_device",
        "ip_address": "203.0.113.1",
        "payment_instrument_id": f"payment_{account_id}",
        "label": 0,
        "ring_label": "",
    }
    values.update(changes)
    return Account(**values)


def transaction(transaction_id, account_id="acct_1", **changes):
    values = {
        "transaction_id": transaction_id,
        "account_id": account_id,
        "merchant_id": "merchant_1",
        "promotion_id": "",
        "amount": "100.00",
        "created_at": "2026-01-01T00:30:00Z",
        "status": "succeeded",
    }
    values.update(changes)
    return Transaction(**values)


class FeatureTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def test_representative_features_respect_cutoff(self):
        accounts = [
            account("acct_1"),
            account("acct_2", created_at="2026-01-01T00:10:00Z"),
            account("acct_future", created_at="2026-01-01T05:00:00Z"),
        ]
        transactions = [
            transaction("txn_1", promotion_id="promo_1"),
            transaction(
                "txn_2",
                merchant_id="merchant_2",
                promotion_id="promo_1",
                amount="200.00",
                created_at="2026-01-01T01:00:00Z",
                status="failed",
            ),
            transaction(
                "txn_future",
                amount="999.00",
                created_at="2026-01-01T04:00:00Z",
                status="refunded",
            ),
            transaction(
                "txn_3",
                account_id="acct_2",
                amount="50.00",
                created_at="2026-01-01T00:40:00Z",
                status="refunded",
            ),
        ]
        cutoff = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
        rows = {row["account_id"]: row for row in build_account_features(accounts, transactions, cutoff)}

        self.assertNotIn("acct_future", rows)
        self.assertEqual(rows["acct_1"]["transaction_count"], 2)
        self.assertEqual(rows["acct_1"]["total_amount"], 300.0)
        self.assertEqual(rows["acct_1"]["mean_amount"], 150.0)
        self.assertEqual(rows["acct_1"]["promotion_claim_ratio"], 1.0)
        self.assertEqual(rows["acct_1"]["distinct_merchant_count"], 2)
        self.assertEqual(rows["acct_1"]["failure_ratio"], 0.5)
        self.assertEqual(rows["acct_1"]["refund_ratio"], 0.0)
        self.assertEqual(rows["acct_1"]["shared_device_accounts"], 1)
        self.assertEqual(rows["acct_1"]["max_transactions_1h"], 2)
        self.assertEqual(rows["acct_1"]["max_promotion_claims_1h"], 2)
        self.assertEqual(rows["acct_1"]["time_to_first_promotion_hours"], 0.5)

    def test_outputs_are_deterministic_and_keep_labels_separate(self):
        raw = self.root / "raw"
        generate_dataset(raw, seed=9, account_count=40, transaction_count=120, ring_count=3)
        for output in (self.root / "first", self.root / "second"):
            write_feature_outputs(raw / "accounts.csv", raw / "transactions.csv", output)
        for filename in ("account_features.csv", "account_labels.csv", "feature_metadata.json"):
            self.assertEqual(
                (self.root / "first" / filename).read_bytes(),
                (self.root / "second" / filename).read_bytes(),
            )

        with (self.root / "first" / "account_features.csv").open(newline="") as file:
            feature_fields = tuple(csv.DictReader(file).fieldnames or ())
        self.assertNotIn("label", feature_fields)
        self.assertNotIn("ring_label", feature_fields)
        self.assertEqual(feature_fields[1:], tuple(FEATURE_DEFINITIONS))
        metadata = json.loads((self.root / "first" / "feature_metadata.json").read_text())
        self.assertEqual([feature["name"] for feature in metadata["features"]], list(FEATURE_DEFINITIONS))

    def test_invalid_source_rows_have_actionable_errors(self):
        base_accounts = [account("acct_1"), account("acct_2")]
        base_transactions = [transaction("txn_1")]
        cases = (
            ("duplicate", [*base_accounts, base_accounts[0]], base_transactions, "duplicate account_id"),
            (
                "unknown",
                base_accounts,
                [transaction("txn_1", account_id="missing")],
                "unknown account_id",
            ),
            (
                "timestamp",
                [account("acct_1", created_at="not-a-date"), base_accounts[1]],
                base_transactions,
                "invalid ISO-8601 timestamp",
            ),
            (
                "negative",
                base_accounts,
                [transaction("txn_1", amount="-1")],
                "finite non-negative",
            ),
        )
        for name, accounts, transactions, message in cases:
            with self.subTest(name=name):
                directory = self.root / name
                directory.mkdir()
                self._write(directory / "accounts.csv", ACCOUNT_FIELDS, accounts)
                self._write(directory / "transactions.csv", TRANSACTION_FIELDS, transactions)
                with self.assertRaisesRegex(DataValidationError, message):
                    load_dataset(directory / "accounts.csv", directory / "transactions.csv")

        malformed = self.root / "malformed"
        malformed.mkdir()
        self._write(malformed / "accounts.csv", ACCOUNT_FIELDS, base_accounts)
        (malformed / "transactions.csv").write_text(
            ",".join(TRANSACTION_FIELDS) + "\n" + ",".join(asdict(base_transactions[0]).values()) + ",extra\n"
        )
        with self.assertRaisesRegex(DataValidationError, "extra columns"):
            load_dataset(malformed / "accounts.csv", malformed / "transactions.csv")

    @staticmethod
    def _write(path, fields, rows):
        with path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(asdict(row) for row in rows)


if __name__ == "__main__":
    unittest.main()
