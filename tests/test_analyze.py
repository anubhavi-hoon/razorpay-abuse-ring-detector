import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from abuse_detector.api import MAX_ACCOUNT_ROWS, MAX_UPLOAD_BYTES, create_app
from abuse_detector.data import ACCOUNT_FIELDS, TRANSACTION_FIELDS
from abuse_detector.db import create_database_engine, load_pipeline_run
from abuse_detector.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
UNLABELLED_ACCOUNT_FIELDS = ACCOUNT_FIELDS[:-2]


def _csv(fields, rows):
    return "\n".join([",".join(fields), *(",".join(row) for row in rows)]) + "\n"


def _account(index, *, device, created="2026-01-01T00:00:00Z"):
    return (
        f"acct_{index:04d}",
        created,
        f"email_{index:04d}",
        f"phone_{index:04d}",
        device,
        "198.51.100.7",
        f"payment_{index:04d}",
    )


def _transaction(index, account_index):
    return (
        f"txn_{index:04d}",
        f"acct_{account_index:04d}",
        "merchant_001",
        "promo_01",
        "199.00",
        "2026-01-02T00:00:00Z",
        "succeeded",
    )


def _labelled_upload(labels):
    """One upload per given label string; "" means the label column is left blank."""
    accounts = [
        (*_account(index, device="device_shared"), label, "")
        for index, label in enumerate(labels, start=1)
    ]
    transactions = [_transaction(index, index) for index in range(1, len(labels) + 1)]
    return {
        "accounts": ("accounts.csv", _csv(ACCOUNT_FIELDS, accounts), "text/csv"),
        "transactions": ("transactions.csv", _csv(TRANSACTION_FIELDS, transactions), "text/csv"),
    }


def _ring_upload(member_count=4):
    accounts = [_account(i, device="device_shared") for i in range(1, member_count + 1)]
    transactions = [_transaction(i, i) for i in range(1, member_count + 1)]
    return {
        "accounts": ("accounts.csv", _csv(UNLABELLED_ACCOUNT_FIELDS, accounts), "text/csv"),
        "transactions": ("transactions.csv", _csv(TRANSACTION_FIELDS, transactions), "text/csv"),
    }


class AnalyzeUploadTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        run_pipeline(
            root / "runs", "demo", seed=29, account_count=60, transaction_count=180, ring_count=4
        )
        database_url = f"sqlite:///{root / 'test.db'}"
        self.config = Config(str(ROOT / "alembic.ini"))
        self.config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(self.config, "head")
        self.engine = create_database_engine(database_url)
        load_pipeline_run(root / "runs/demo", self.engine)
        self.model_artifact = root / "runs/demo/artifacts/model.pkl"
        self.client = TestClient(
            create_app(engine=self.engine, model_artifact=self.model_artifact)
        )

    def test_unlabelled_upload_becomes_the_active_run(self):
        before = self.client.get("/api/v1/health").json()["run_id"]
        self.assertEqual(before, "demo")

        response = self.client.post("/api/v1/analyze", files=_ring_upload())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["account_count"], 4)
        self.assertEqual(body["transaction_count"], 4)
        self.assertGreaterEqual(body["ring_count"], 1)
        self.assertFalse(body["labels_available"])

        self.assertEqual(self.client.get("/api/v1/health").json()["run_id"], body["run_id"])
        summary = self.client.get("/api/v1/summary").json()
        self.assertEqual(summary["run_id"], body["run_id"])
        self.assertEqual(summary["account_count"], 4)

        rings = self.client.get("/api/v1/rings").json()["items"]
        self.assertTrue(rings)
        detail = self.client.get(f"/api/v1/rings/{rings[0]['ring_id']}")
        self.assertEqual(detail.status_code, 200)
        account = self.client.get(f"/api/v1/accounts/{detail.json()['members'][0]['account_id']}")
        self.assertEqual(account.status_code, 200)
        self.assertEqual(len(account.json()["features"]), 18)

    def test_unlabelled_run_reports_no_evaluation_metrics(self):
        run_id = self.client.post("/api/v1/analyze", files=_ring_upload()).json()["run_id"]
        with self.engine.connect() as connection:
            from sqlalchemy import text

            metrics, labels = connection.execute(
                text(
                    "SELECT r.metrics, (SELECT COUNT(*) FROM accounts a "
                    "WHERE a.run_id = r.run_id AND a.label IS NOT NULL) "
                    "FROM detection_runs r WHERE r.run_id = :run_id"
                ),
                {"run_id": run_id},
            ).one()
        self.assertEqual(labels, 0)
        import json

        parsed = json.loads(metrics) if isinstance(metrics, str) else metrics
        self.assertIsNone(parsed["account"])
        self.assertIsNone(parsed["ring"]["top20_ring_recall"])
        self.assertIsNone(parsed["ring"]["top20_ring_precision"])

    def test_labels_available_requires_every_account_to_be_labelled(self):
        cases = {
            "fully labelled": (["0", "0", "0", "0"], True),
            "partially labelled": (["0", "0", "", ""], False),
            "single missing label": (["0", "0", "0", ""], False),
            "wholly unlabelled": (["", "", "", ""], False),
        }
        for name, (labels, expected) in cases.items():
            with self.subTest(name):
                response = self.client.post("/api/v1/analyze", files=_labelled_upload(labels))
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIs(response.json()["labels_available"], expected)

    def test_downgrade_drops_whole_unlabelled_runs_and_keeps_labelled_ones(self):
        from sqlalchemy import text

        upload = self.client.post("/api/v1/analyze", files=_ring_upload()).json()["run_id"]

        def snapshot():
            tables = (
                "detection_runs",
                "accounts",
                "transactions",
                "account_results",
                "rings",
                "ring_members",
                "relationships",
            )
            with self.engine.connect() as connection:
                counts = {
                    table: connection.execute(
                        text(f"SELECT COUNT(*) FROM {table} WHERE run_id = :run_id"),
                        {"run_id": "demo"},
                    ).scalar()
                    for table in tables
                }
                counts["upload_rows"] = connection.execute(
                    text("SELECT COUNT(*) FROM accounts WHERE run_id = :run_id"),
                    {"run_id": upload},
                ).scalar()
                counts["null_labels"] = connection.execute(
                    text("SELECT COUNT(*) FROM accounts WHERE label IS NULL")
                ).scalar()
                counts["orphans"] = connection.execute(
                    text(
                        "SELECT COUNT(*) FROM accounts a WHERE NOT EXISTS "
                        "(SELECT 1 FROM detection_runs r WHERE r.run_id = a.run_id)"
                    )
                ).scalar()
            return counts

        before = snapshot()
        self.assertEqual(before["upload_rows"], 4)
        self.assertEqual(before["null_labels"], 4)

        self.engine.dispose()
        command.downgrade(self.config, "0001_initial")
        after = snapshot()

        # The unlabelled run is gone in full, children included.
        self.assertEqual(after["upload_rows"], 0)
        self.assertEqual(after["null_labels"], 0)
        self.assertEqual(after["orphans"], 0)
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(text("SELECT run_id FROM detection_runs")).scalars().all(),
                ["demo"],
            )
        # The labelled run keeps every row it had, so its recorded counts still hold.
        for table, count in before.items():
            if table not in {"upload_rows", "null_labels", "orphans"}:
                self.assertEqual(after[table], count, f"{table} changed for the demo run")
        self.assertGreater(after["ring_members"], 0)
        self.assertGreater(after["relationships"], 0)

    def test_malformed_schema_is_rejected(self):
        files = _ring_upload()
        files["accounts"] = ("accounts.csv", "account_id,created_at\nacct_1,nope\n", "text/csv")
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 422)
        self.assertIn("expected columns", response.json()["detail"])

        bad_amount = _ring_upload()
        rows = [_transaction(1, 1), ("txn_0002", "acct_0002", "m", "", "abc", "2026-01-02T00:00:00Z", "succeeded")]
        bad_amount["transactions"] = (
            "transactions.csv",
            _csv(TRANSACTION_FIELDS, rows),
            "text/csv",
        )
        malformed = self.client.post("/api/v1/analyze", files=bad_amount)
        self.assertEqual(malformed.status_code, 422)
        self.assertIn("amount", malformed.json()["detail"])

    def test_missing_file_and_oversized_uploads_are_rejected(self):
        only_one = self.client.post(
            "/api/v1/analyze", files={"accounts": ("accounts.csv", "a\n", "text/csv")}
        )
        self.assertEqual(only_one.status_code, 422)

        oversized = _ring_upload()
        oversized["accounts"] = (
            "accounts.csv",
            "x" * (MAX_UPLOAD_BYTES + 1),
            "text/csv",
        )
        too_big = self.client.post("/api/v1/analyze", files=oversized)
        self.assertEqual(too_big.status_code, 413)
        self.assertIn("MB limit", too_big.json()["detail"])

        too_many = _ring_upload()
        rows = [_account(i, device=f"device_{i:05d}") for i in range(1, MAX_ACCOUNT_ROWS + 2)]
        too_many["accounts"] = (
            "accounts.csv",
            _csv(UNLABELLED_ACCOUNT_FIELDS, rows),
            "text/csv",
        )
        too_many["transactions"] = (
            "transactions.csv",
            _csv(TRANSACTION_FIELDS, [_transaction(1, 1)]),
            "text/csv",
        )
        rows_rejected = self.client.post("/api/v1/analyze", files=too_many)
        self.assertEqual(rows_rejected.status_code, 413)
        self.assertIn("row limit", rows_rejected.json()["detail"])

    def test_transaction_referencing_missing_account_is_rejected(self):
        files = _ring_upload()
        files["transactions"] = (
            "transactions.csv",
            _csv(TRANSACTION_FIELDS, [_transaction(1, 999)]),
            "text/csv",
        )
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 422)
        self.assertIn("unknown account_id", response.json()["detail"])

    def test_duplicate_account_id_is_rejected(self):
        duplicate = [_account(1, device="device_shared"), _account(1, device="device_shared")]
        files = _ring_upload()
        files["accounts"] = ("accounts.csv", _csv(UNLABELLED_ACCOUNT_FIELDS, duplicate), "text/csv")
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 422)
        self.assertIn("duplicate account_id", response.json()["detail"])

    def test_non_utf8_upload_is_rejected(self):
        files = _ring_upload()
        files["accounts"] = ("accounts.csv", b"\xff\xfe\x00bad", "text/csv")
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 400)
        self.assertIn("UTF-8", response.json()["detail"])

    def test_failed_upload_leaves_the_previous_run_active_and_no_temp_files(self):
        before = tempfile.gettempdir()
        existing = set(Path(before).glob("analyze-*"))
        bad = _ring_upload()
        bad["transactions"] = (
            "transactions.csv",
            _csv(TRANSACTION_FIELDS, [_transaction(1, 999)]),
            "text/csv",
        )
        self.assertEqual(self.client.post("/api/v1/analyze", files=bad).status_code, 422)
        self.assertEqual(self.client.get("/api/v1/health").json()["run_id"], "demo")

        self.client.post("/api/v1/analyze", files=_ring_upload())
        self.assertEqual(set(Path(before).glob("analyze-*")), existing)


if __name__ == "__main__":
    unittest.main()
