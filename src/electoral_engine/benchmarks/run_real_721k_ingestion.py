"""
Production Benchmark: Ingestion & Parquet Data Lake Generation Across 721,735 Electors (DEIP V2.2)
Constituencies:
- AC 37 (Pithapuram): 236,192 Electors
- AC 38 (Kakinada Rural): 260,821 Electors
- AC 39 (Peddapuram): 224,722 Electors
Total Ingestion Target: 721,735 Electors (Invariant Delta = 0)
"""

import os
import sys
import time
import json
import logging
import pandas as pd
import pyarrow.parquet as pq

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.electoral_engine.reconciler import ElectoralReconciler
from src.electoral_engine.exporter import ElectoralExporter, SCHEMA_COLUMNS

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("benchmark_721k")

CONSTITUENCIES = [
    {
        'ac_no': 37,
        'name': 'Pithapuram',
        'csv_path': r'C:\Users\vamsi\Downloads\Voter_Analysis\Pithapuram\Pithapuram_AC37_Master_Voters_2025.csv',
        'expected_count': 236192
    },
    {
        'ac_no': 38,
        'name': 'Kakinada_Rural',
        'csv_path': r'C:\Users\vamsi\Downloads\Voter_Analysis\Kakinada_Rural\Kakinada_Rural_AC38_Master_Voters_2025.csv',
        'expected_count': 260821
    },
    {
        'ac_no': 39,
        'name': 'Peddapuram',
        'csv_path': r'C:\Users\vamsi\Downloads\Voter_Analysis\Peddapuram\Peddapuram_AC39_Master_Voters_2025.csv',
        'expected_count': 224722
    }
]


def run_benchmark(output_dir: str = "data_lake"):
    os.makedirs(output_dir, exist_ok=True)
    exporter = ElectoralExporter(output_dir)
    reconciler = ElectoralReconciler()

    grand_total_records = 0
    total_csv_bytes = 0
    total_parquet_bytes = 0
    grand_t0 = time.time()
    benchmark_report = {}

    print("\n" + "=" * 80)
    print("STARTING CENSUS-GRADE BENCHMARK & DATA LAKE EXPORT ACROSS 721,735 ELECTORS")
    print("=" * 80 + "\n")

    for const in CONSTITUENCIES:
        ac_no = const['ac_no']
        ac_name = const['name']
        csv_path = const['csv_path']
        expected_cnt = const['expected_count']

        if not os.path.exists(csv_path):
            logger.error(f"File not found for {ac_name}: {csv_path}")
            continue

        csv_size = os.path.getsize(csv_path)
        total_csv_bytes += csv_size

        t0 = time.time()
        print(f"[{ac_name} (AC {ac_no})] Reading CSV ({csv_size / (1024*1024):.1f} MB)...", flush=True)
        df = pd.read_csv(csv_path, low_memory=False)
        read_time = time.time() - t0

        records_count = len(df)
        grand_total_records += records_count

        # Invariant check
        delta = records_count - expected_cnt
        print(f"[{ac_name} (AC {ac_no})] Loaded {records_count:,} records in {read_time:.2f}s (Delta = {delta})", flush=True)

        # Normalize into records list
        t1 = time.time()
        raw_records = df.to_dict('records')

        # Convert to 32-field format
        formatted_records = []
        for r in raw_records:
            elector_id = f"AP_{ac_no}_P{r.get('assembly_part_2025', 1):03d}_S{r.get('booth_sno_2025', 1):04d}"
            formatted_records.append({
                'elector_id': elector_id,
                'assembly_constituency_no': ac_no,
                'assembly_constituency_name': ac_name,
                'assembly_part_no': int(r.get('assembly_part_2025', 1)),
                'booth_sno': int(r.get('booth_sno_2025', 1)),
                'epic_no': str(r.get('epic_no', '-')),
                'voter_name_en': str(r.get('voter_name_en', '-')),
                'voter_name_te': None,
                'rel_type': str(r.get('rel_type', '-')),
                'rel_name_en': str(r.get('rel_name_en', '-')),
                'rel_name_te': None,
                'door_no': str(r.get('door_no', '-')),
                'normalized_door_no': str(r.get('door_no', '-')),
                'age': int(r['age']) if str(r.get('age', '')).isdigit() else None,
                'gender': str(r.get('gender', '-')),
                'linguistic_group': str(r.get('linguistic_group', 'T')),
                'status': str(r.get('status', 'Active')),
                'voter_name_raw': str(r.get('voter_name_en', '-')),
                'rel_name_raw': str(r.get('rel_name_en', '-')),
                'door_no_raw': str(r.get('door_no', '-')),
                'mean_card_conf': 0.95,
                'token_confidences_json': json.dumps([]),
                'raw_ocr_dump': '',
                'source_pdf_filename': f"AC{ac_no}_Part_{r.get('assembly_part_2025', 1)}.pdf",
                'source_pdf_sha256': '0'*64,
                'page_no': 1,
                'box_index': 1,
                'bbox_x': 0, 'bbox_y': 0, 'bbox_w': 0, 'bbox_h': 0,
                'crop_image_s3_uri': '',
                'household_cluster_key': f"{ac_no}_{r.get('assembly_part_2025', 1)}_{r.get('door_no', '-')}",
                'audit_trail': json.dumps([]),
                'engine_version': 'DEIP-2.2.0'
            })

        # Apply Multi-Scale Proximity Surname Restoration (Tiers 1, 2, 3)
        t_prox_start = time.time()
        print(f"[{ac_name} (AC {ac_no})] Executing 3-Tier Multi-Scale Proximity Surname Arbitration...", flush=True)
        reconciled_records = reconciler.arbitrate_household_consensus(formatted_records)
        prox_time = time.time() - t_prox_start

        # Count total proximity repairs
        repairs_count = sum(1 for rec in reconciled_records if rec.get('audit_trail') and ('PROXIMITY_REPAIR' in str(rec['audit_trail'])))
        print(f"[{ac_name} (AC {ac_no})] Multi-Scale Proximity Repairs Applied: {repairs_count:,} in {prox_time:.2f}s", flush=True)

        # Export to Snappy Apache Parquet
        t_pq_start = time.time()
        parquet_filename = f"ac{ac_no}_{ac_name.lower()}_master"
        parquet_path = exporter.export_parquet(reconciled_records, filename_base=parquet_filename)
        pq_time = time.time() - t_pq_start

        pq_size = os.path.getsize(parquet_path)
        total_parquet_bytes += pq_size
        compression_ratio = csv_size / pq_size

        print(f"[{ac_name} (AC {ac_no})] Exported Parquet: {pq_size / (1024*1024):.1f} MB (Compression: {compression_ratio:.2f}x) in {pq_time:.2f}s", flush=True)
        print(f"[{ac_name} (AC {ac_no})] Total Constituency Throughput: {records_count / (read_time + prox_time + pq_time):,.0f} records/sec\n", flush=True)

        benchmark_report[ac_name] = {
            'ac_no': ac_no,
            'records_count': records_count,
            'delta_from_expected': delta,
            'csv_mb': round(csv_size / (1024*1024), 2),
            'parquet_mb': round(pq_size / (1024*1024), 2),
            'compression_ratio': round(compression_ratio, 2),
            'proximity_repairs': repairs_count,
            'read_sec': round(read_time, 2),
            'proximity_sec': round(prox_time, 2),
            'parquet_export_sec': round(pq_time, 2),
            'total_sec': round(read_time + prox_time + pq_time, 2),
            'throughput_rps': round(records_count / (read_time + prox_time + pq_time), 0)
        }

    grand_total_time = time.time() - grand_t0
    grand_compression = total_csv_bytes / total_parquet_bytes if total_parquet_bytes > 0 else 0

    print("=" * 80)
    print("CENSUS-GRADE BENCHMARK SUMMARY (721,735 ELECTORS)")
    print("=" * 80)
    print(f"Grand Total Records Processed:     {grand_total_records:,} (Target: 721,735 | Delta = {grand_total_records - 721735})")
    print(f"Total Raw CSV Storage:             {total_csv_bytes / (1024*1024):.1f} MB")
    print(f"Total Snappy Parquet Storage:      {total_parquet_bytes / (1024*1024):.1f} MB")
    print(f"Overall Data Lake Compression:     {grand_compression:.2f}x")
    print(f"Grand Total Processing Time:       {grand_total_time:.2f} seconds")
    print(f"Overall Platform Ingestion Rate:   {grand_total_records / grand_total_time:,.0f} records/second")
    print("=" * 80 + "\n")

    # Save summary report
    report_file = os.path.join(output_dir, "benchmark_721k_summary.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            'grand_total_records': grand_total_records,
            'delta': grand_total_records - 721735,
            'total_csv_mb': round(total_csv_bytes / (1024*1024), 2),
            'total_parquet_mb': round(total_parquet_bytes / (1024*1024), 2),
            'compression_ratio': round(grand_compression, 2),
            'grand_total_seconds': round(grand_total_time, 2),
            'records_per_second': round(grand_total_records / grand_total_time, 0),
            'constituencies': benchmark_report
        }, f, indent=2)

    return benchmark_report


if __name__ == '__main__':
    run_benchmark()
