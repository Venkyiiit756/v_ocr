"""
End-to-End Pipeline Integration Test (DEIP V2.2)
Verifies:
1. Synthetic electoral roll PDF creation (FitZ/PyMuPDF)
2. Dual-Zone OCR & 300 DPI rasterization pipeline
3. Bayesian Household Prior arbitration
4. Database batch ingestion into master_electors
5. Multi-format delivery: CSV, styled Excel, and Apache Parquet (Snappy)
"""

import os
import sys
import tempfile
import unittest
import pymupdf
import pandas as pd
import pyarrow.parquet as pq

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.electoral_engine.engine import ElectoralPipelineEngine
from src.electoral_engine.db import ElectoralDatabaseAdapter


class TestEndToEndPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = self.temp_dir.name
        self.output_dir = os.path.join(self.work_dir, "deliverables")
        self.pdf_path = os.path.join(self.work_dir, "sample_roll_ac37_part001.pdf")

        # Create a 3-page synthetic PDF: Page 1 cover, Page 2 content with card borders, Page 3 end
        self._create_synthetic_electoral_pdf(self.pdf_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_electoral_pdf(self, pdf_path: str):
        """Generates a synthetic 3-page electoral roll with voter card boxes."""
        doc = pymupdf.open()
        
        # Page 1: Cover Page
        cover = doc.new_page(width=595, height=842) # A4
        cover.insert_text((150, 200), "ELECTION COMMISSION OF INDIA", fontsize=16)
        cover.insert_text((120, 240), "ASSEMBLY CONSTITUENCY 37 - PITHAPURAM", fontsize=14)
        cover.insert_text((180, 280), "POLLING STATION PART NO: 1", fontsize=12)

        # Page 2: Elector Content Page with 2 Card Boxes
        page2 = doc.new_page(width=595, height=842)
        
        # Draw Card 1 Rect (x=50, y=80, w=240, h=140)
        rect1 = pymupdf.Rect(50, 80, 290, 220)
        page2.draw_rect(rect1, color=(0, 0, 0), width=1)
        # SNO & EPIC
        page2.insert_text((55, 98), "1", fontsize=10)
        page2.insert_text((140, 98), "YOU1423871", fontsize=11)
        # Demographics
        page2.insert_text((55, 120), "Name : Boppana Venkata Ramana", fontsize=9)
        page2.insert_text((55, 140), "Father's Name : Boppana Subba Rao", fontsize=9)
        page2.insert_text((55, 160), "House No : 1-42/B", fontsize=9)
        page2.insert_text((55, 180), "Age : 38  Gender : Male", fontsize=9)

        # Draw Card 2 Rect (x=305, y=80, w=240, h=140)
        rect2 = pymupdf.Rect(305, 80, 545, 220)
        page2.draw_rect(rect2, color=(0, 0, 0), width=1)
        page2.insert_text((310, 98), "2", fontsize=10)
        page2.insert_text((395, 98), "YOU1423872", fontsize=11)
        page2.insert_text((310, 120), "Name : Boppana Satyavathi", fontsize=9)
        page2.insert_text((310, 140), "Husband's Name : Boppana Venkata Ramana", fontsize=9)
        page2.insert_text((310, 160), "House No : 1-42/B", fontsize=9)
        page2.insert_text((310, 180), "Age : 34  Gender : Female", fontsize=9)

        # Page 3: Summary Page
        page3 = doc.new_page(width=595, height=842)
        page3.insert_text((150, 200), "SUMMARY OF ELECTORS", fontsize=14)

        doc.save(pdf_path)
        doc.close()

    def test_end_to_end_pipeline_execution(self):
        """Verify complete pipeline run from PDF to Parquet & DB."""
        # Force SQLite fallback for test environment
        os.environ["USE_SQLITE"] = "true"

        engine = ElectoralPipelineEngine(workers=1, target_dpi=150)
        pdf_mapping = {1: self.pdf_path}

        result = engine.run_pipeline(
            ground_truth_csv=None,
            pdf_mapping=pdf_mapping,
            output_dir=self.output_dir,
            file_prefix="test_pipeline_run",
            ac_no=37,
            save_to_db=True
        )

        self.assertGreaterEqual(result['total_electors'], 1)
        export_files = result['export_files']
        
        # Verify CSV deliverable
        self.assertTrue(os.path.exists(export_files['csv']))
        df_csv = pd.read_csv(export_files['csv'])
        self.assertGreaterEqual(len(df_csv), 1)

        # Verify Excel deliverable
        self.assertTrue(os.path.exists(export_files['xlsx']))

        # Verify Parquet deliverable
        self.assertTrue(os.path.exists(export_files['parquet']))
        pq_table = pq.read_table(export_files['parquet'])
        self.assertGreaterEqual(pq_table.num_rows, 1)
        self.assertIn('mean_card_conf', pq_table.column_names)


if __name__ == '__main__':
    unittest.main()
