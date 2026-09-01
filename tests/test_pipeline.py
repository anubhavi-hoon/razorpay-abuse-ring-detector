import tempfile
import unittest
from pathlib import Path

from abuse_detector.pipeline import run_pipeline


class PipelineTest(unittest.TestCase):
    def test_default_benchmark_is_challenging_and_still_meets_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = run_pipeline(Path(temporary), "realism")
            account = report["metrics"]["account"]
            ring = report["metrics"]["ring"]

            self.assertGreaterEqual(account["precision"], 0.60)
            self.assertLess(account["precision"], 1.0)
            self.assertLess(account["pr_auc"], 1.0)
            self.assertGreaterEqual(account["recall"], 0.75)
            self.assertGreaterEqual(ring["top20_ring_recall"], 0.80)

    def test_small_run_is_complete_atomic_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments = {
                "seed": 17,
                "account_count": 60,
                "transaction_count": 180,
                "ring_count": 4,
            }
            first = run_pipeline(root, "small", **arguments)
            manifest = (root / "small" / "run.json").read_bytes()
            second = run_pipeline(root, "small", **arguments)

            self.assertEqual(first, second)
            self.assertEqual((root / "small" / "run.json").read_bytes(), manifest)
            self.assertEqual(first["status"], "complete")
            self.assertEqual(first["counts"]["accounts"], 60)
            self.assertGreater(first["counts"]["rings"], 0)
            self.assertTrue(all((root / "small" / path).is_file() for path in first["outputs"]))

            with self.assertRaises(ValueError):
                run_pipeline(root, "small", **{**arguments, "seed": 18})
            with self.assertRaises(ValueError):
                run_pipeline(root, "failed", account_count=10, transaction_count=10, ring_count=3)
            self.assertFalse((root / "failed").exists())


if __name__ == "__main__":
    unittest.main()
