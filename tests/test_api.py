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

                rings = client.get("/api/v1/rings", params={"page_size": 2})
                self.assertEqual(rings.status_code, 200)
                self.assertEqual(len(rings.json()["items"]), 2)
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
                    "/api/v1/rings",
                    "/api/v1/rings/{ring_id}",
                    "/api/v1/rings/{ring_id}/status",
                    "/api/v1/accounts/{account_id}",
                }
                self.assertEqual(set(schema["paths"]), expected_paths)
                page_size = next(
                    item
                    for item in schema["paths"]["/api/v1/rings"]["get"]["parameters"]
                    if item["name"] == "page_size"
                )
                self.assertEqual(page_size["schema"]["maximum"], 100)


if __name__ == "__main__":
    unittest.main()
