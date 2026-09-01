import csv
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from abuse_detector.db import (
    Account,
    DetectionRun,
    Relationship,
    Ring,
    TransactionRecord,
    create_database_engine,
    load_pipeline_run,
)
from abuse_detector.pipeline import run_pipeline


class DatabaseTest(unittest.TestCase):
    def test_migration_constraints_transactional_reload_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_pipeline(
                root / "runs",
                "small",
                seed=23,
                account_count=60,
                transaction_count=180,
                ring_count=4,
            )
            run_dir = root / "runs/small"
            database_url = f"sqlite:///{root / 'test.db'}"
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "head")
            engine = create_database_engine(database_url)

            first = load_pipeline_run(run_dir, engine)
            with Session(engine) as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Account)), 60)
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(TransactionRecord)), 180
                )
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(Ring)), first["counts"]["rings"]
                )
                self.assertGreater(session.scalar(select(func.count()).select_from(Relationship)), 0)
                ring = session.scalars(select(Ring).order_by(Ring.ring_id)).first()
                ring_id = ring.ring_id
                ring.status = "confirmed"
                session.commit()

            skipped = load_pipeline_run(root / "missing", engine, if_empty=True)
            self.assertEqual(skipped, {"run_id": "small", "skipped": True})

            second = load_pipeline_run(run_dir, engine)
            self.assertTrue(second["replaced"])
            with Session(engine) as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(DetectionRun)), 1)
                self.assertEqual(session.get(Ring, ("small", ring_id)).status, "confirmed")

                invalid = session.get(Ring, ("small", ring_id))
                invalid.status = "invalid"
                with self.assertRaises(IntegrityError):
                    session.commit()
                session.rollback()

                session.add(
                    TransactionRecord(
                        run_id="small",
                        transaction_id="missing_account_txn",
                        account_id="missing",
                        merchant_id="merchant_1",
                        promotion_id=None,
                        amount=Decimal("1.00"),
                        created_at=datetime.now(timezone.utc),
                        status="succeeded",
                    )
                )
                with self.assertRaises(IntegrityError):
                    session.commit()
                session.rollback()

            edge_path = run_dir / "rings/graph_edges.csv"
            with edge_path.open(newline="") as file:
                edges = list(csv.DictReader(file))
            edges[0]["source"] = "missing"
            with edge_path.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=edges[0])
                writer.writeheader()
                writer.writerows(edges)
            with self.assertRaises(IntegrityError):
                load_pipeline_run(run_dir, engine)
            with Session(engine) as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(DetectionRun)), 1)
                self.assertEqual(session.get(Ring, ("small", ring_id)).status, "confirmed")


if __name__ == "__main__":
    unittest.main()
