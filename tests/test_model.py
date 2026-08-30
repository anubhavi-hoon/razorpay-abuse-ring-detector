import csv
import tempfile
import unittest
from pathlib import Path

from abuse_detector.data import generate_dataset
from abuse_detector.features import write_feature_outputs
from abuse_detector.model import (
    grouped_stratified_split,
    load_artifact,
    load_training_data,
    score_accounts,
    train_and_evaluate,
)


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        raw = self.root / "raw"
        processed = self.root / "processed"
        generate_dataset(raw, seed=13, account_count=100, transaction_count=500, ring_count=6)
        write_feature_outputs(raw / "accounts.csv", raw / "transactions.csv", processed)
        self.features = processed / "account_features.csv"
        self.labels = processed / "account_labels.csv"

    def test_grouped_split_keeps_rings_together(self):
        account_ids, _, labels, rings, _ = load_training_data(self.features, self.labels)
        train, test = grouped_stratified_split(account_ids, labels, rings, seed=7)
        train_rings = {rings[index] for index in train if rings[index]}
        test_rings = {rings[index] for index in test if rings[index]}
        self.assertFalse(train_rings & test_rings)
        self.assertEqual({labels[index] for index in train}, {0, 1})
        self.assertEqual({labels[index] for index in test}, {0, 1})

    def test_artifact_reload_scores_identically(self):
        output = self.root / "artifacts"
        repeated = self.root / "repeated"
        evaluation = train_and_evaluate(self.features, self.labels, output, seed=7)
        train_and_evaluate(self.features, self.labels, repeated, seed=7)
        account_ids, _, _, _, numeric_rows = load_training_data(self.features, self.labels)
        artifact = load_artifact(output / "model.pkl")
        first = score_accounts(artifact, account_ids[:10], numeric_rows[:10])
        second = score_accounts(load_artifact(output / "model.pkl"), account_ids[:10], numeric_rows[:10])
        self.assertEqual(first, second)
        self.assertEqual(
            (output / "account_scores.csv").read_bytes(),
            (repeated / "account_scores.csv").read_bytes(),
        )
        self.assertEqual(artifact["feature_names"], tuple(numeric_rows[0]))
        self.assertEqual(evaluation["metrics_scope"], "held_out_test")
        self.assertFalse(set(evaluation["train_ring_labels"]) & set(evaluation["test_ring_labels"]))

        with (output / "account_scores.csv").open(newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 100)
        self.assertTrue(all(0 <= float(row["ml_score"]) <= 1 for row in rows))


if __name__ == "__main__":
    unittest.main()
