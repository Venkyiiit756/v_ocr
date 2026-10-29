"""
Full Production Pipeline Execution on Authentic English Electoral Roll (DEIP V2.2)
Target: Kakinada City 2025 English Electoral Roll (roll_part_1.pdf)
Constituency: AC 38 - Kakinada Rural / City, Part 1
Language: Strictly English (-l eng)

Executes:
1. Extraction from ZIP archive to temporary processing space.
2. 300 DPI native grayscale rasterization & 30-card grid boundary detection.
3. Dual-Zone English OCR (Zone A Header & Zone B Body demographic isolation).
4. 32-Field Provenance extraction with Form-7 strikethrough restoration.
5. Unified 3-Tier Multi-Scale Proximity Surname Restoration (Tier 1 Intra-Card,
   Tier 2 Household Door Consensus, Tier 3 Serial Adjacency).
6. Multi-Format Deliverable Export:
   - Apache Parquet (Snappy columnar data lake with strict PyArrow schema)
   - Styled Publication-Ready Excel (.xlsx) with Audit Trail sheet
   - Master CSV (.csv)
7. Persistence into Master Electors Database Table with SHA-256 physical provenance.
"""

import os
import sys
import time
import json
import zipfile
import shutil
import pymupdf
import pandas as pd
import pyarrow.parquet as pq

# Force UTF-8 on Windows stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.electoral_engine.engine import ElectoralPipelineEngine
from src.electoral_engine.db import ElectoralDatabaseAdapter

ZIP_PATH = r"C:\Users\vamsi\Downloads\Voter_Analysis\Kakinada_City_2025_PDFs.zip"
OUTPUT_DIR = r"C:\Users\vamsi\.gemini\antigravity\scratch\v_ocr\data_lake\english_roll_deliverables"


def run_live_english_roll():
    if not os.path.exists(ZIP_PATH):
        print(f"Error: ZIP archive not found at {ZIP_PATH}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    temp_pdf_dir = os.path.join(OUTPUT_DIR, "temp_pdf")
    os.makedirs(temp_pdf_dir, exist_ok=True)
    target_pdf_path = os.path.join(temp_pdf_dir, "roll_part_1.pdf")

    # 1. Extract roll_part_1.pdf
    print("\n" + "=" * 80)
    print("DEIP V2.2: AUTHENTIC ENGLISH ELECTORAL ROLL INGESTION & DELIVERY RUN")
    print(f"Source: {ZIP_PATH} -> roll_part_1.pdf (English Roll)")
    print(f"Language Mode: Strictly English (-l eng)")
    print(f"Output Deliverables: {OUTPUT_DIR}")
    print("=" * 80 + "\n")

    print("Extracting roll_part_1.pdf from archive...", flush=True)
    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        with open(target_pdf_path, 'wb') as f:
            f.write(z.read('roll_part_1.pdf'))

    doc = pymupdf.open(target_pdf_path)
    total_pages = len(doc)
    doc.close()
    print(f"Loaded authentic English roll: {total_pages} total pages.\n", flush=True)

    # 2. Extract first 3 content pages (pages 3, 4, 5) to produce a representative roll slice
    # Page 1: Cover, Page 2: Summary/Map, Pages 3-5: 90 Voter Cards
    sample_pdf_path = os.path.join(temp_pdf_dir, "roll_part_1_sample.pdf")
    src_doc = pymupdf.open(target_pdf_path)
    sub_doc = pymupdf.open()
    # Insert cover (page 0), map (page 1), and voter pages (pages 2, 3, 4)
    for p in range(min(5, len(src_doc))):
        sub_doc.insert_pdf(src_doc, from_page=p, to_page=p)
    sub_doc.save(sample_pdf_path)
    sub_doc.close()
    src_doc.close()
    print(f"Prepared sample roll slice ({sample_pdf_path}) with 3 content pages (Target: 90 cards).", flush=True)

    # 3. Initialize Pipeline Engine in English Mode
    # Use SQLite in-memory fallback for local execution
    os.environ["USE_SQLITE"] = "true"
    engine = ElectoralPipelineEngine(workers=4, target_dpi=300, ocr_lang="eng")

    pdf_mapping = {1: sample_pdf_path}

    t0 = time.time()
    result = engine.run_pipeline(
        ground_truth_csv=None,
        pdf_mapping=pdf_mapping,
        output_dir=OUTPUT_DIR,
        file_prefix="Kakinada_City_AC38_Part001_Master",
        ac_no=38,
        save_to_db=True
    )
    elapsed = time.time() - t0

    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Total Electors Processed: {result['total_electors']}")
    print(f"Total Processing Time:    {elapsed:.2f} seconds ({result['total_electors'] / max(elapsed, 0.01):.1f} cards/sec)")
    print(f"Database Persistence:     {result['db_stats'].get('inserted_or_updated', 0)} records stored")
    print(f"Exported Files:")
    for fmt, pth in result['export_files'].items():
        size_kb = os.path.getsize(pth) / 1024
        print(f"  - [{fmt.upper()}] {pth} ({size_kb:.1f} KB)")

    # 4. Deep Audit of the Parquet deliverable
    parquet_path = result['export_files']['parquet']
    df_parquet = pd.read_parquet(parquet_path)
    print("\n" + "-" * 80)
    print("PARQUET COLUMNAR DATA LAKE INTEGRITY CHECK:")
    print(f"Total Rows:    {len(df_parquet)}")
    print(f"Total Columns: {len(df_parquet.columns)}")
    print(f"Sample Records Extracted from Authentic English PDF:")
    print("-" * 80)
    for idx, row in df_parquet.head(10).iterrows():
        print(f"Card #{row['booth_sno']:02d} | EPIC: {row['epic_no']:10} | Name: '{row['voter_name_en']}' | Rel: ({row['rel_type']}) '{row['rel_name_en']}' | Door: '{row['door_no']}' | Age: {row['age']} | Gender: {row['gender']}")

    print("=" * 80 + "\n")
    return result


if __name__ == '__main__':
    run_live_english_roll()
