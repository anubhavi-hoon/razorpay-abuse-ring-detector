import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from abuse_detector.data import ACCOUNT_FIELDS, TRANSACTION_FIELDS, generate_dataset


class SyntheticDataTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def generate(self, directory: str):
        return generate_dataset(
            self.root / directory,
            seed=7,
            account_count=60,
            transaction_count=180,
            ring_count=4,
        )

    def test_seeded_output_is_identical(self):
        self.generate("first")
        self.generate("second")
        for filename in ("accounts.csv", "transactions.csv", "manifest.json"):
            self.assertEqual(
                (self.root / "first" / filename).read_bytes(),
                (self.root / "second" / filename).read_bytes(),
            )

    def test_schema_ids_relationships_and_rings(self):
        manifest = self.generate("dataset")
        with (self.root / "dataset" / "accounts.csv").open(newline="") as file:
            accounts = list(csv.DictReader(file))
        with (self.root / "dataset" / "transactions.csv").open(newline="") as file:
            transactions = list(csv.DictReader(file))

        self.assertEqual(tuple(accounts[0]), ACCOUNT_FIELDS)
        self.assertEqual(tuple(transactions[0]), TRANSACTION_FIELDS)
        account_ids = {account["account_id"] for account in accounts}
        transaction_ids = {transaction["transaction_id"] for transaction in transactions}
        self.assertEqual(len(account_ids), len(accounts))
        self.assertEqual(len(transaction_ids), len(transactions))
        self.assertTrue(all(transaction["account_id"] in account_ids for transaction in transactions))
        self.assertTrue(all(float(transaction["amount"]) >= 0 for transaction in transactions))
        self.assertTrue(
            all(transaction["status"] in {"succeeded", "failed", "refunded"} for transaction in transactions)
        )
        timestamps = [account["created_at"] for account in accounts]
        timestamps.extend(transaction["created_at"] for transaction in transactions)
        for timestamp in timestamps:
            self.assertIsNotNone(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo)

        planted = {account["ring_label"] for account in accounts if account["label"] == "1"}
        self.assertEqual(planted, {f"ring_{index:03d}" for index in range(1, 5)})
        self.assertTrue(all(account["ring_label"] == "" for account in accounts if account["label"] == "0"))
        evasive = [account for account in accounts if account["ring_label"] == "ring_003"]
        self.assertGreater(len({account["device_id"] for account in evasive}), 1)
        self.assertGreater(len({account["payment_instrument_id"] for account in evasive}), 1)
        benign_shared = accounts[20:25]
        self.assertGreater(len({account["device_id"] for account in benign_shared}), 1)
        self.assertGreater(len({account["payment_instrument_id"] for account in benign_shared}), 1)
        self.assertGreater(len({account["ip_address"] for account in benign_shared}), 1)
        self.assertEqual({account["label"] for account in benign_shared}, {"0"})
        self.assertEqual(manifest["evasive_ring_count"], 1)
        self.assertEqual(manifest["benign_shared_group_count"], 4)
        self.assertEqual(manifest["ground_truth_fields"], ["label", "ring_label"])
        self.assertEqual(json.loads((self.root / "dataset" / "manifest.json").read_text()), manifest)

    def test_invalid_sizes_are_rejected(self):
        invalid = (
            {"account_count": 10, "transaction_count": 10, "ring_count": 3},
            {"account_count": 20, "transaction_count": 19, "ring_count": 2},
            {"account_count": 20, "transaction_count": 20, "ring_count": 0},
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                generate_dataset(self.root / "invalid", **arguments)


if __name__ == "__main__":
    unittest.main()
