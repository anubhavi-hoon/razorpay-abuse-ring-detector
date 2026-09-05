import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from abuse_detector.api import create_app
from abuse_detector.db import create_database_engine, load_pipeline_run
from abuse_detector.pipeline import run_pipeline


class ApiTest(unittest.TestCase):
    def test_complete_review_flow_filters_validation_and_openapi(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_pipeline(
                root / "runs",
                "small",
                seed=29,
                account_count=60,
                transaction_count=180,
                ring_count=4,
            )
            database_url = f"sqlite:///{root / 'test.db'}"
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "head")
            engine = create_database_engine(database_url)
            load_pipeline_run(root / "runs/small", engine)

            with TestClient(
                create_app(engine=engine, allowed_origins=["http://frontend.test"])
            ) as client:
                health = client.get("/api/v1/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["run_id"], "small")

                summary = client.get("/api/v1/summary")
                self.assertEqual(summary.status_code, 200)
                self.assertEqual(summary.json()["account_count"], 60)
                self.assertEqual(sum(summary.json()["score_distribution"].values()), summary.json()["ring_count"])

                json_report = client.get("/api/v1/reports/current.json")
                self.assertEqual(json_report.status_code, 200)
                self.assertIn("attachment;", json_report.headers["content-disposition"])
                self.assertEqual(json_report.json()["summary"], summary.json())
                self.assertEqual(len(json_report.json()["rings"]), summary.json()["ring_count"])

                csv_report = client.get("/api/v1/reports/current.csv")
                self.assertEqual(csv_report.status_code, 200)
                self.assertIn("attachment;", csv_report.headers["content-disposition"])
                csv_rows = list(csv.DictReader(io.StringIO(csv_report.text)))
                self.assertEqual(len(csv_rows), summary.json()["ring_count"])
                self.assertEqual(csv_rows[0]["ring_id"], json_report.json()["rings"][0]["ring_id"])

                pdf_report = client.get("/api/v1/reports/current.pdf")
                self.assertEqual(pdf_report.status_code, 200)
                self.assertEqual(pdf_report.headers["content-type"], "application/pdf")
                self.assertEqual(
                    pdf_report.headers["content-disposition"],
                    'attachment; filename="abuse-ring-report-small.pdf"',
                )
                self.assertTrue(pdf_report.content.startswith(b"%PDF-"))
                self.assertGreater(len(pdf_report.content), 1000)

                rings = client.get("/api/v1/rings", params={"page_size": 2})
                self.assertEqual(rings.status_code, 200)
                self.assertEqual(len(rings.json()["items"]), min(2, rings.json()["total"]))
                ring = rings.json()["items"][0]
                scored = client.get("/api/v1/rings", params={"min_score": 0.5})
                self.assertTrue(all(item["score"] >= 0.5 for item in scored.json()["items"]))
                ring_date = ring["created_at"][:10]
                dated = client.get(
                    "/api/v1/rings", params={"date_from": ring_date, "date_to": ring_date}
                )
                self.assertIn(ring["ring_id"], {item["ring_id"] for item in dated.json()["items"]})

                promotion = ring["promotion_ids"][0]
                filtered = client.get("/api/v1/rings", params={"promotion": promotion})
                self.assertTrue(filtered.json()["items"])
                self.assertTrue(
                    all(promotion in item["promotion_ids"] for item in filtered.json()["items"])
                )
                self.assertEqual(client.get("/api/v1/rings", params={"page_size": 101}).status_code, 422)
                self.assertEqual(
                    client.get(
                        "/api/v1/rings",
                        params={"date_from": "2026-03-01", "date_to": "2026-01-01"},
                    ).status_code,
                    422,
                )

                detail = client.get(f"/api/v1/rings/{ring['ring_id']}")
                self.assertEqual(detail.status_code, 200)
                self.assertTrue(detail.json()["members"])
                self.assertTrue(detail.json()["shared_entities"])
                self.assertTrue(detail.json()["nodes"])
                self.assertTrue(detail.json()["edges"])
                if detail.json()["detection_resilience"] is None:
                    self.assertIsNone(detail.json()["min_entity_removals"])
                else:
                    self.assertIn(
                        detail.json()["detection_resilience"],
                        {"low", "moderate", "high"},
                    )
                    self.assertGreaterEqual(detail.json()["min_entity_removals"], 1)
                self.assertIsInstance(detail.json()["critical_entity_types"], list)

                account_id = detail.json()["members"][0]["account_id"]
                account = client.get(f"/api/v1/accounts/{account_id}")
                self.assertEqual(account.status_code, 200)
                self.assertTrue(account.json()["features"])
                self.assertTrue(account.json()["transactions"])

                status_url = f"/api/v1/rings/{ring['ring_id']}/status"
                self.assertEqual(client.patch(status_url, json={"status": "confirmed"}).status_code, 409)
                self.assertEqual(
                    client.patch(status_url, json={"status": "reviewing"}).json()["status"],
                    "reviewing",
                )
                self.assertEqual(
                    client.patch(status_url, json={"status": "confirmed"}).json()["status"],
                    "confirmed",
                )
                self.assertEqual(
                    client.get("/api/v1/rings", params={"status": "confirmed"}).json()["total"],
                    1,
                )
                self.assertEqual(client.patch(status_url, json={"status": "invalid"}).status_code, 422)
                self.assertEqual(client.get("/api/v1/rings/missing").status_code, 404)
                self.assertEqual(client.get("/api/v1/accounts/missing").status_code, 404)

                cors = client.options(
                    "/api/v1/rings",
                    headers={
                        "Origin": "http://frontend.test",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                self.assertEqual(cors.headers["access-control-allow-origin"], "http://frontend.test")

                schema = client.get("/openapi.json").json()
                frozen_schema = json.loads(
                    (Path(__file__).resolve().parents[1] / "docs/openapi.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(schema, frozen_schema)
                expected_paths = {
                    "/api/v1/health",
                    "/api/v1/summary",
                    "/api/v1/reports/current.csv",
                    "/api/v1/reports/current.json",
                    "/api/v1/reports/current.pdf",
                    "/api/v1/rings",
                    "/api/v1/rings/{ring_id}",
                    "/api/v1/rings/{ring_id}/status",
                    "/api/v1/accounts/{account_id}",
                    "/api/v1/analyze",
                }
                self.assertEqual(set(schema["paths"]), expected_paths)
                page_size = next(
                    item
                    for item in schema["paths"]["/api/v1/rings"]["get"]["parameters"]
                    if item["name"] == "page_size"
                )
                self.assertEqual(page_size["schema"]["maximum"], 100)

    def test_pdf_report_builder_direct(self):
        from abuse_detector.pdf_report import build_pdf_report

        # 1. Test empty rings
        empty_summary = {
            "run_id": "empty_run",
            "account_count": 0,
            "transaction_count": 0,
            "flagged_account_count": 0,
            "ring_count": 0,
            "score_distribution": {"low": 0, "medium": 0, "high": 0},
            "review_status_totals": {"new": 0, "reviewing": 0, "confirmed": 0, "dismissed": 0},
        }
        pdf_empty = build_pdf_report(empty_summary, [], exported_at="2026-09-05T00:00:00+00:00")
        self.assertTrue(pdf_empty.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_empty), 1000)

        # 2. Test large rings list (> 15 rings) to trigger appendix table and pagination
        large_rings = [
            {
                "rank": i,
                "run_id": "large_run",
                "ring_id": f"ring_{i:03d}",
                "risk_level": "high" if i % 3 == 0 else "medium" if i % 2 == 0 else "low",
                "ring_score": round(0.95 - (i * 0.03), 3),
                "review_status": "new" if i % 2 == 0 else "reviewing",
                "created_at": "2026-09-01T12:00:00+00:00",
                "member_count": 3 + (i % 4),
                "shared_entity_count": 2 + (i % 3),
                "entity_types": ["ip_address", "payment_instrument_id"],
                "promotion_ids": [f"promo_{i % 3}"],
                "reason_codes": ["shared_payment_instrument"],
                "detection_resilience": "moderate" if i % 2 == 0 else "high",
                "min_entity_removals": 2,
                "critical_entity_types": ["payment_instrument_id"] if i % 3 == 0 else [],
            }
            for i in range(1, 25)
        ]
        large_summary = {
            "run_id": "large_run",
            "account_count": 1000,
            "transaction_count": 5000,
            "flagged_account_count": 150,
            "ring_count": len(large_rings),
            "score_distribution": {"low": 8, "medium": 8, "high": 8},
            "review_status_totals": {"new": 12, "reviewing": 12, "confirmed": 0, "dismissed": 0},
        }
        pdf_large = build_pdf_report(large_summary, large_rings)
        self.assertTrue(pdf_large.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_large), 5000)

        # 3. Test a 208-ring PDF (specifically verifying > 200 rings balanced pagination)
        rings_208 = [
            {
                "rank": i,
                "run_id": "run_208",
                "ring_id": f"ring_{i:04d}",
                "risk_level": "high" if i <= 50 else "medium" if i <= 150 else "low",
                "ring_score": round(max(0.1, 0.99 - (i * 0.004)), 3),
                "review_status": "confirmed" if i <= 20 else "reviewing" if i <= 60 else "new",
                "created_at": "2026-01-15T00:00:00+00:00",
                "member_count": 3 + (i % 5),
                "shared_entity_count": 2 + (i % 3),
                "entity_types": ["device", "ip", "payment_instrument"],
                "promotion_ids": [f"promo_{i % 4}"],
                "reason_codes": ["SHARED_PAYMENT_INSTRUMENT"],
                "detection_resilience": "moderate" if i % 2 == 0 else "low",
                "min_entity_removals": 2 if i % 2 == 0 else 1,
                "critical_entity_types": ["payment_instrument"] if i % 2 != 0 else [],
            }
            for i in range(1, 209)
        ]
        summary_208 = {
            "run_id": "run_208",
            "account_count": 5000,
            "transaction_count": 20000,
            "flagged_account_count": 850,
            "ring_count": 208,
            "score_distribution": {"high": 50, "medium": 100, "low": 58},
            "review_status_totals": {"new": 148, "reviewing": 40, "confirmed": 20, "dismissed": 0},
        }
        pdf_208 = build_pdf_report(summary_208, rings_208)
        self.assertTrue(pdf_208.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_208), 20000)

        # 4. Test run where resilience is completely unassessed (None)
        unassessed_rings = [
            {
                "rank": i,
                "run_id": "unassessed_run",
                "ring_id": f"ring_u_{i:03d}",
                "risk_level": "high" if i <= 5 else "low",
                "ring_score": round(0.9 - (i * 0.05), 3),
                "review_status": "new",
                "created_at": "2026-02-01T00:00:00+00:00",
                "member_count": 4,
                "shared_entity_count": 2,
                "entity_types": ["ip_address"],
                "promotion_ids": ["promo_test"],
                "reason_codes": ["SHARED_IP"],
                "detection_resilience": None,
                "min_entity_removals": None,
                "critical_entity_types": [],
            }
            for i in range(1, 10)
        ]
        unassessed_summary = {
            "run_id": "unassessed_run",
            "account_count": 100,
            "transaction_count": 400,
            "flagged_account_count": 30,
            "ring_count": 9,
            "score_distribution": {"high": 5, "medium": 0, "low": 4},
            "review_status_totals": {"new": 9, "reviewing": 0, "confirmed": 0, "dismissed": 0},
        }
        pdf_unassessed = build_pdf_report(unassessed_summary, unassessed_rings)
        self.assertTrue(pdf_unassessed.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_unassessed), 5000)


if __name__ == "__main__":
    unittest.main()
