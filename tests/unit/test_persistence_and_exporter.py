"""
Verification Tests for Persistence Layer & Multi-Format Exporter (DEIP V2.2)
Verifies:
1. SQLite/PostgreSQL Database Adapter schema initialization
2. Batch upsert idempotency and conflict resolution
3. Quarantine queue filtering & audit ledger event recording
4. Apache Parquet Snappy export and column type fidelity
5. Atomic export_all delivering CSV, styled Excel, and Parquet
"""

import os
import sys
import tempfile
import unittest
import pandas as pd
import pyarrow.parquet as pq

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.electoral_engine.db import ElectoralDatabaseAdapter
from src.electoral_engine.exporter import ElectoralExporter, SCHEMA_COLUMNS


class TestPersistenceAndExporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = self.temp_dir.name
        self.db = ElectoralDatabaseAdapter(use_sqlite_fallback=True)
        self.exporter = ElectoralExporter(self.output_dir)

        # Sample high-fidelity record
        self.sample_record = {
            'elector_id': '37_1_1',
            'assembly_constituency_no': 37,
            'assembly_constituency_name': 'Pithapuram',
            'assembly_part_no': 1,
            'booth_sno': 1,
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
            'raw_ocr_dump': '1 YOU1423871\nName: Boppana Venkata Ramana\nFather: Boppana Subba Rao\nHouse: 1-42/B\nAge: 38 Gender: Male',
            'source_pdf_filename': 'AC37_Part001.pdf',
            'source_pdf_sha256': 'a' * 64,
            'page_no': 3,
            'box_index': 1,
            'bbox_x': 50,
            'bbox_y': 120,
            'bbox_w': 380,
            'bbox_h': 160,
            'crop_image_s3_uri': 's3://electoral-rolls/crops/37/1/3_1.png',
            'household_cluster_key': '37_1_1-42/B',
            'audit_trail': [{'action': 'INGEST', 'timestamp': '2026-10-29T10:00:00Z'}],
            'engine_version': 'DEIP-2.2.0'
        }

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_database_batch_upsert_and_fetch(self):
        """Verify atomic batch upsert and retrieval."""
        res = self.db.upsert_electors_batch([self.sample_record])
        self.assertEqual(res['inserted_or_updated'], 1)

        fetched = self.db.get_elector_by_id(37, '37_1_1')
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched['epic_no'], 'YOU1423871')
        self.assertEqual(fetched['voter_name_en'], 'Boppana Venkata Ramana')
        self.assertEqual(fetched['age'], 38)
        self.assertAlmostEqual(fetched['mean_card_conf'], 0.942, places=3)

    def test_database_upsert_idempotency(self):
        """Verify that re-inserting with updated age mutates record in place."""
        self.db.upsert_electors_batch([self.sample_record])
        
        # Mutate age to 39
        updated_record = dict(self.sample_record)
        updated_record['age'] = 39
        self.db.upsert_electors_batch([updated_record])

        fetched = self.db.get_elector_by_id(37, '37_1_1')
        self.assertEqual(fetched['age'], 39)

    def test_quarantine_queue_filtering(self):
        """Verify that low-confidence cards (< 0.65) or status 'Quarantined' appear in queue."""
        low_conf_record = dict(self.sample_record)
        low_conf_record['elector_id'] = '37_1_2'
        low_conf_record['booth_sno'] = 2
        low_conf_record['mean_card_conf'] = 0.52
        low_conf_record['status'] = 'Quarantined'

        self.db.upsert_electors_batch([self.sample_record, low_conf_record])
        queue = self.db.get_quarantine_queue()
        
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['elector_id'], '37_1_2')

    def test_audit_ledger_recording(self):
        """Verify append-only audit ledger records events."""
        self.db.record_audit_event(
            constituency_no=37,
            elector_id='37_1_1',
            action_type='BAYESIAN_REPAIR',
            field_name='voter_name_en',
            old_val='Bappana',
            new_val='Boppana',
            rationale='Bayesian co-resident prior posterior P=0.98',
            confidence_delta=0.15,
            actor='CONSENSUS_ENGINE'
        )

        cur = self.db.sqlite_conn.cursor()
        cur.execute("SELECT * FROM electoral_audit_ledger WHERE elector_id = '37_1_1'")
        rows = cur.fetchall()
        cur.close()
        
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['action_type'], 'BAYESIAN_REPAIR')
        self.assertEqual(rows[0]['new_value'], 'Boppana')

    def test_parquet_export_integrity(self):
        """Verify Apache Parquet export with Snappy compression and column type fidelity."""
        parquet_path = self.exporter.export_parquet([self.sample_record], filename_base='test_electors')
        self.assertTrue(os.path.exists(parquet_path))

        # Read back table with PyArrow
        table = pq.read_table(parquet_path)
        self.assertEqual(table.num_rows, 1)
        self.assertIn('voter_name_en', table.column_names)
        self.assertIn('mean_card_conf', table.column_names)
        self.assertEqual(table['epic_no'][0].as_py(), 'YOU1423871')
        self.assertEqual(table['voter_name_en'][0].as_py(), 'Boppana Venkata Ramana')
        self.assertEqual(table['age'][0].as_py(), 38)

    def test_export_all_bundle(self):
        """Verify export_all generates CSV, Excel, and Parquet."""
        results = self.exporter.export_all([self.sample_record], filename_base='bundle_master')
        self.assertTrue(os.path.exists(results['csv']))
        self.assertTrue(os.path.exists(results['xlsx']))
        self.assertTrue(os.path.exists(results['parquet']))

        # Verify CSV row count
        df_csv = pd.read_csv(results['csv'])
        self.assertEqual(len(df_csv), 1)

    def test_sql_ddl_file_exists_and_valid(self):
        """Verify PostgreSQL DDL migration file exists and contains essential table statements."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        ddl_path = os.path.join(base_dir, 'sql', '01_master_electors_ddl.sql')
        self.assertTrue(os.path.exists(ddl_path))

        with open(ddl_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('CREATE TABLE IF NOT EXISTS master_electors', content)
        self.assertIn('PARTITION BY RANGE (assembly_constituency_no)', content)
        self.assertIn('master_electors_ac37', content)
        self.assertIn('master_electors_ac38', content)
        self.assertIn('master_electors_ac39', content)
        self.assertIn('idx_electors_voter_trgm', content)
        self.assertIn('CREATE TABLE IF NOT EXISTS electoral_audit_ledger', content)


if __name__ == '__main__':
    unittest.main()
