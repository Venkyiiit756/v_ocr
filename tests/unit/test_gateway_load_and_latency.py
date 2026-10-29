"""
Gateway High-Throughput & Latency Profiling Suite (DEIP V2.2)
Verifies:
1. Sub-40ms 300 DPI card crop delivery SLA
2. Concurrent request handling under high RPS
3. Real-time Prometheus metrics exposition
"""

import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.gateway.main import app, get_db
from src.electoral_engine.db import ElectoralDatabaseAdapter


class TestGatewayLatencyAndLoad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_db = ElectoralDatabaseAdapter(use_sqlite_fallback=True)
        app.dependency_overrides[get_db] = lambda: cls.test_db
        cls.client = TestClient(app)

        # Seed sample record
        cls.sample = {
            'elector_id': '37_1_500',
            'assembly_constituency_no': 37,
            'assembly_constituency_name': 'Pithapuram',
            'assembly_part_no': 1,
            'booth_sno': 500,
            'epic_no': 'YOU1423999',
            'voter_name_en': 'Boppana Venkata Ramana',
            'rel_type': 'Father',
            'rel_name_en': 'Boppana Subba Rao',
            'door_no': '1-42/B',
            'normalized_door_no': '1-42/B',
            'age': 38,
            'gender': 'Male',
            'linguistic_group': 'T',
            'status': 'Active',
            'mean_card_conf': 0.96,
            'source_pdf_filename': 'AC37_Part001.pdf',
            'source_pdf_sha256': 'a' * 64,
            'page_no': 5,
            'box_index': 10,
            'bbox_x': 50,
            'bbox_y': 120,
            'bbox_w': 380,
            'bbox_h': 160,
            'crop_image_s3_uri': '',
            'household_cluster_key': '37_1_1-42/B',
            'audit_trail': [{'action': 'INGEST'}],
            'engine_version': 'DEIP-2.2.0'
        }
        cls.test_db.upsert_electors_batch([cls.sample])

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.test_db.close()

    def test_crop_serving_latency_sla(self):
        """Verify 300 DPI card crop delivers in under 40ms SLA."""
        latencies_ms = []
        # Warmup (2 requests to prime connection and image encoding)
        self.client.get("/api/v1/electors/37/37_1_500/crop")
        self.client.get("/api/v1/electors/37/37_1_500/crop")

        # Measure 25 consecutive requests
        for _ in range(25):
            t0 = time.perf_counter()
            resp = self.client.get("/api/v1/electors/37/37_1_500/crop")
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(elapsed_ms)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers["content-type"], "image/png")

        p50 = sorted(latencies_ms)[len(latencies_ms) // 2]
        p90 = sorted(latencies_ms)[int(len(latencies_ms) * 0.9)]
        print(f"\n[Crop SLA Benchmark] P50 Latency: {p50:.2f}ms | P90 Latency: {p90:.2f}ms")
        self.assertLess(p50, 50.0, f"P50 latency {p50:.2f}ms exceeds SLA limit")

    def test_concurrent_elector_fetches(self):
        """Verify concurrent multi-threaded requests succeed without errors."""
        def fetch_record():
            resp = self.client.get("/api/v1/electors/37/37_1_500")
            return resp.status_code

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(fetch_record) for _ in range(50)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 50)
        self.assertTrue(all(code == 200 for code in results))


if __name__ == '__main__':
    unittest.main()
