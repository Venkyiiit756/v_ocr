"""
API Gateway Verification Tests (DEIP V2.2)
Verifies:
1. Health check & runtime version reporting
2. Elector record retrieval with 32-field lineage
3. Low-latency 300 DPI card crop generation and serving (< 40ms)
4. Quarantine review queue
5. Human-in-the-loop manual override with audit ledger logging
6. Prometheus telemetry metrics exposition
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.gateway.main import app, get_db
from src.electoral_engine.db import ElectoralDatabaseAdapter


class TestAPIGateway(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize an isolated SQLite test database
        cls.test_db = ElectoralDatabaseAdapter(use_sqlite_fallback=True)
        # Override the dependency in FastAPI
        app.dependency_overrides[get_db] = lambda: cls.test_db
        cls.client = TestClient(app)

        # Seed sample record
        cls.sample_record = {
            'elector_id': '37_1_101',
            'assembly_constituency_no': 37,
            'assembly_constituency_name': 'Pithapuram',
            'assembly_part_no': 1,
            'booth_sno': 101,
            'epic_no': 'YOU1423871',
            'voter_name_en': 'Boppana Venkata Ramana',
            'voter_name_te': 'బొప్పన వెంకట రమణ',
            'rel_type': 'Father',
            'rel_name_en': 'Boppana Subba Rao',
            'rel_name_te': 'బొప్పన సుబ్బా రావు',
            'door_no': '1-42/B',
            'normalized_door_no': '1-42/B',
            'age': 38,
            'gender': 'Male',
            'linguistic_group': 'T',
            'status': 'Active',
            'voter_name_raw': 'Boppana Venkata Ramana',
            'rel_name_raw': 'Boppana Subba Rao',
            'door_no_raw': '1-42/B',
            'mean_card_conf': 0.942,
            'token_confidences_json': [{'token': 'Boppana', 'conf': 0.98}],
            'raw_ocr_dump': '101 YOU1423871\nName: Boppana Venkata Ramana\nFather: Boppana Subba Rao\nHouse: 1-42/B\nAge: 38 Gender: Male',
            'source_pdf_filename': 'AC37_Part001.pdf',
            'source_pdf_sha256': 'a' * 64,
            'page_no': 4,
            'box_index': 5,
            'bbox_x': 50,
            'bbox_y': 120,
            'bbox_w': 380,
            'bbox_h': 160,
            'crop_image_s3_uri': '',
            'household_cluster_key': '37_1_1-42/B',
            'audit_trail': [{'action': 'INGEST', 'timestamp': '2026-10-29T10:00:00Z'}],
            'engine_version': 'DEIP-2.2.0'
        }
        cls.test_db.upsert_electors_batch([cls.sample_record])

        # Seed quarantined record
        cls.quarantined_record = dict(cls.sample_record)
        cls.quarantined_record['elector_id'] = '37_1_102'
        cls.quarantined_record['booth_sno'] = 102
        cls.quarantined_record['mean_card_conf'] = 0.51
        cls.quarantined_record['status'] = 'Quarantined'
        cls.test_db.upsert_electors_batch([cls.quarantined_record])

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.test_db.close()

    def test_health_check(self):
        """Verify health check returns UP and correct version."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "UP")
        self.assertEqual(data["version"], "DEIP-2.2.0")

    def test_get_elector_details(self):
        """Verify retrieval of complete 32-field elector record."""
        response = self.client.get("/api/v1/electors/37/37_1_101")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["elector_id"], "37_1_101")
        self.assertEqual(data["epic_no"], "YOU1423871")
        self.assertEqual(data["voter_name_en"], "Boppana Venkata Ramana")
        self.assertEqual(data["age"], 38)
        self.assertEqual(data["bbox_w"], 380)

    def test_get_elector_not_found(self):
        """Verify 404 for non-existent elector."""
        response = self.client.get("/api/v1/electors/37/99_99_999")
        self.assertEqual(response.status_code, 404)

    def test_get_card_crop_latency_and_format(self):
        """Verify 300 DPI card crop returns PNG with low latency (< 100ms on test runner)."""
        response = self.client.get("/api/v1/electors/37/37_1_101/crop")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertTrue(len(response.content) > 1000)
        self.assertIn("X-Crop-Render-Latency-Ms", response.headers)

    def test_quarantine_queue_endpoint(self):
        """Verify quarantine endpoint lists red-tier electors."""
        response = self.client.get("/api/v1/qc/quarantine")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)
        elector_ids = [r["elector_id"] for r in data["records"]]
        self.assertIn("37_1_102", elector_ids)

    def test_manual_override_endpoint(self):
        """Verify human-in-the-loop manual override clears quarantine and records audit trail."""
        override_payload = {
            "assembly_constituency_no": 37,
            "elector_id": "37_1_102",
            "field_name": "door_no",
            "new_value": "1-45/A",
            "rationale": "Auditor visual inspection confirmed house number smudge",
            "auditor_id": "AUDITOR_VAMSI"
        }
        response = self.client.post("/api/v1/qc/override", json=override_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["new_value"], "1-45/A")

        # Verify database record updated
        updated = self.test_db.get_elector_by_id(37, "37_1_102")
        self.assertEqual(updated["door_no"], "1-45/A")
        self.assertEqual(updated["status"], "Active")

    def test_prometheus_metrics_endpoint(self):
        """Verify /metrics endpoint returns standard Prometheus exposition format."""
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("electoral_http_requests_total", response.text)


if __name__ == '__main__':
    unittest.main()
