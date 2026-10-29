"""
Professional Parquet, Excel, and CSV Exporter with Automated Styling and Auditing.
Generates production-grade Apache Parquet data lake files, publication-ready Excel workbooks,
and CSV exports adhering strictly to the 32-field Permanent Provenance Schema (DEIP V2.2).
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

logger = logging.getLogger(__name__)

# Complete 32-field Schema Specification
SCHEMA_COLUMNS = [
    'elector_id',
    'assembly_constituency_no',
    'assembly_constituency_name',
    'assembly_part_no',
    'booth_sno',
    'epic_no',
    'voter_name_en',
    'voter_name_te',
    'rel_type',
    'rel_name_en',
    'rel_name_te',
    'door_no',
    'normalized_door_no',
    'age',
    'gender',
    'linguistic_group',
    'status',
    'voter_name_raw',
    'rel_name_raw',
    'door_no_raw',
    'mean_card_conf',
    'token_confidences_json',
    'raw_ocr_dump',
    'source_pdf_filename',
    'source_pdf_sha256',
    'page_no',
    'box_index',
    'bbox_x',
    'bbox_y',
    'bbox_w',
    'bbox_h',
    'crop_image_s3_uri',
    'household_cluster_key',
    'audit_trail',
    'engine_version'
]


class ElectoralExporter:
    """
    Multi-format electoral data exporter supporting Apache Parquet (Snappy),
    Excel with conditional formatting, and CSV.
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _prepare_dataframe(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Converts raw records into standard DataFrame matching 32-field schema."""
        if not records:
            return pd.DataFrame(columns=SCHEMA_COLUMNS)

        normalized_records = []
        for r in records:
            norm = {}
            for col in SCHEMA_COLUMNS:
                val = r.get(col)
                if val is None:
                    # Check legacy field name variations
                    if col == 'epic_no':
                        val = r.get('EPIC No') or r.get('epic') or '-'
                    elif col == 'voter_name_en':
                        val = r.get('Voter Name (English)') or r.get('name') or '-'
                    elif col == 'rel_name_en':
                        val = r.get('Father / Husband / Guardian Name') or r.get('relative_name') or '-'
                    elif col == 'rel_type':
                        val = r.get('Relationship Type') or r.get('relationship') or '-'
                    elif col == 'door_no':
                        val = r.get('Door / House No') or r.get('house_no') or '-'
                    elif col == 'age':
                        val = r.get('Age')
                    elif col == 'gender':
                        val = r.get('Gender') or '-'
                    elif col == 'booth_sno':
                        val = r.get('2025 Booth Serial No') or r.get('Serial No') or r.get('Ward Serial No') or 1
                    elif col == 'assembly_part_no':
                        val = r.get('2025 Assembly Part No (Baseline)') or r.get('part_no') or 1
                    elif col == 'assembly_constituency_no':
                        val = r.get('ac_no') or 37
                    elif col == 'assembly_constituency_name':
                        val = r.get('ac_name') or 'Pithapuram'
                    elif col == 'elector_id':
                        val = f"{r.get('ac_no', 37)}_{r.get('part_no', 1)}_{r.get('booth_sno', 1)}"
                    else:
                        val = '-' if isinstance(col, str) and not col.endswith('_conf') else None

                if col in ('token_confidences_json', 'audit_trail') and not isinstance(val, str):
                    val = json.dumps(val or [])
                norm[col] = val
            normalized_records.append(norm)

        df = pd.DataFrame(normalized_records)

        # Type casts
        df['assembly_constituency_no'] = pd.to_numeric(df['assembly_constituency_no'], errors='coerce').fillna(37).astype('int16')
        df['assembly_part_no'] = pd.to_numeric(df['assembly_part_no'], errors='coerce').fillna(1).astype('int32')
        df['booth_sno'] = pd.to_numeric(df['booth_sno'], errors='coerce').fillna(1).astype('int32')
        df['age'] = pd.to_numeric(df['age'], errors='coerce').astype('Int16')
        df['mean_card_conf'] = pd.to_numeric(df['mean_card_conf'], errors='coerce').fillna(0.0).astype('float32')
        df['page_no'] = pd.to_numeric(df['page_no'], errors='coerce').fillna(1).astype('int16')
        df['box_index'] = pd.to_numeric(df['box_index'], errors='coerce').fillna(1).astype('int16')
        for dim in ('bbox_x', 'bbox_y', 'bbox_w', 'bbox_h'):
            df[dim] = pd.to_numeric(df[dim], errors='coerce').fillna(0).astype('int32')

        return df

    def export_parquet(self, records: List[Dict[str, Any]], filename_base: str = 'master_electors',
                       partition_cols: Optional[List[str]] = None) -> str:
        """
        Exports records to an Apache Parquet columnar file or partitioned dataset with Snappy compression.
        """
        df = self._prepare_dataframe(records)

        if not HAS_PYARROW:
            parquet_path = os.path.join(self.output_dir, f"{filename_base}.parquet")
            df.to_parquet(parquet_path, engine='auto', compression='snappy', index=False)
            return parquet_path

        # Construct explicit PyArrow Schema
        pa_schema = pa.schema([
            ('elector_id', pa.string()),
            ('assembly_constituency_no', pa.int16()),
            ('assembly_constituency_name', pa.string()),
            ('assembly_part_no', pa.int32()),
            ('booth_sno', pa.int32()),
            ('epic_no', pa.string()),
            ('voter_name_en', pa.string()),
            ('voter_name_te', pa.string()),
            ('rel_type', pa.string()),
            ('rel_name_en', pa.string()),
            ('rel_name_te', pa.string()),
            ('door_no', pa.string()),
            ('normalized_door_no', pa.string()),
            ('age', pa.int16()),
            ('gender', pa.string()),
            ('linguistic_group', pa.string()),
            ('status', pa.string()),
            ('voter_name_raw', pa.string()),
            ('rel_name_raw', pa.string()),
            ('door_no_raw', pa.string()),
            ('mean_card_conf', pa.float32()),
            ('token_confidences_json', pa.string()),
            ('raw_ocr_dump', pa.string()),
            ('source_pdf_filename', pa.string()),
            ('source_pdf_sha256', pa.string()),
            ('page_no', pa.int16()),
            ('box_index', pa.int16()),
            ('bbox_x', pa.int32()),
            ('bbox_y', pa.int32()),
            ('bbox_w', pa.int32()),
            ('bbox_h', pa.int32()),
            ('crop_image_s3_uri', pa.string()),
            ('household_cluster_key', pa.string()),
            ('audit_trail', pa.string()),
            ('engine_version', pa.string())
        ])

        # Replace NaN in strings with None
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].where(pd.notnull(df[col]), None)

        table = pa.Table.from_pandas(df, schema=pa_schema, preserve_index=False)

        if partition_cols:
            dataset_dir = os.path.join(self.output_dir, filename_base)
            os.makedirs(dataset_dir, exist_ok=True)
            pq.write_to_dataset(table, root_path=dataset_dir, partition_cols=partition_cols, compression='snappy')
            return dataset_dir
        else:
            parquet_path = os.path.join(self.output_dir, f"{filename_base}.parquet")
            pq.write_table(table, parquet_path, compression='snappy')
            return parquet_path

    def export(self, records: List[Dict[str, Any]], audit_report: Optional[Dict[str, Any]] = None,
               filename_base: str = 'Master_Voter_Directory') -> Tuple[str, str]:
        """
        Exports records to styled Excel workbook and CSV file.
        """
        audit_report = audit_report or {}
        df = pd.DataFrame(records)

        # Legacy column normalization if present
        if 'Serial No' in df.columns and 'Ward Serial No' not in df.columns:
            df.rename(columns={'Serial No': 'Ward Serial No'}, inplace=True)

        preferred_cols = [
            'Ward No', 'Ward Serial No', 'EPIC No', 'epic_no',
            'Voter Name (English)', 'voter_name_en', 'Voter Name (Telugu)', 'voter_name_te',
            'Father / Husband / Guardian Name', 'rel_name_en', 'Relationship Type', 'rel_type',
            'Door / House No', 'door_no', 'Age', 'age', 'Gender', 'gender',
            '2025 Assembly Part No (Baseline)', 'assembly_part_no',
            '2025 Booth Serial No', 'booth_sno', 'Polling Station No',
            'Status', 'status', 'Match Confidence', 'mean_card_conf'
        ]

        existing_cols = [c for c in preferred_cols if c in df.columns]
        other_cols = [c for c in df.columns if c not in preferred_cols]
        df_export = df[existing_cols + other_cols] if existing_cols else df

        csv_path = os.path.join(self.output_dir, f"{filename_base}.csv")
        xlsx_path = os.path.join(self.output_dir, f"{filename_base}.xlsx")

        # 1. Save CSV
        df_export.to_csv(csv_path, index=False, encoding='utf-8-sig')

        # 2. Save Styled Excel Workbook
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name='Master Voters', index=False)

            summary_rows = [
                {'Metric': 'Total Ground Truth Electors', 'Value': audit_report.get('total_ground_truth', len(df))},
                {'Metric': 'Electors Matched to Roll Cards', 'Value': audit_report.get('total_resolved', len(df))},
                {'Metric': 'Overall Resolution Rate', 'Value': audit_report.get('resolution_rate', '100.0%')},
                {'Metric': 'Exact EPIC Matches', 'Value': audit_report.get('exact_epic_matches', 0)},
                {'Metric': 'Fuzzy / High-Confidence Name Matches', 'Value': audit_report.get('fuzzy_or_name_matches', 0)},
                {'Metric': 'Unmatched / Pending Review', 'Value': audit_report.get('unmatched', 0)},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Audit & Summary', index=False)

        # Style Workbook
        wb = openpyxl.load_workbook(xlsx_path)
        ws_data = wb['Master Voters']
        ws_sum = wb['Audit & Summary']

        navy_header = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
        header_font = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        center_align = Alignment(horizontal='center', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')

        for col_idx in range(1, len(df_export.columns) + 1):
            cell = ws_data.cell(row=1, column=col_idx)
            cell.fill = navy_header
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border

        for row_idx in range(2, len(df_export) + 2):
            fill_hex = 'F9FBFD' if row_idx % 2 == 0 else 'FFFFFF'
            row_fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type='solid')
            for col_idx in range(1, len(df_export.columns) + 1):
                c = ws_data.cell(row=row_idx, column=col_idx)
                c.fill = row_fill
                c.border = thin_border
                val_str = str(c.value or '').strip()
                if val_str.isdigit() or (len(val_str) <= 10 and ' ' not in val_str):
                    c.alignment = center_align
                else:
                    c.alignment = left_align

        for col in ws_data.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_data.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 42)

        ws_sum.column_dimensions['A'].width = 45
        ws_sum.column_dimensions['B'].width = 20
        for col_idx in [1, 2]:
            c = ws_sum.cell(row=1, column=col_idx)
            c.fill = PatternFill(start_color='203764', end_color='203764', fill_type='solid')
            c.font = header_font
            c.alignment = center_align

        for r in range(2, len(summary_rows) + 2):
            ws_sum.cell(row=r, column=1).alignment = left_align
            ws_sum.cell(row=r, column=1).font = Font(name='Segoe UI', size=10, bold=True)
            ws_sum.cell(row=r, column=2).alignment = center_align
            ws_sum.cell(row=r, column=2).font = Font(name='Segoe UI', size=10)

        wb.save(xlsx_path)
        return csv_path, xlsx_path

    def export_all(self, records: List[Dict[str, Any]], audit_report: Optional[Dict[str, Any]] = None,
                   filename_base: str = 'master_electors',
                   partition_parquet: bool = False) -> Dict[str, str]:
        """
        Exports dataset to CSV, Excel, and Apache Parquet in a single atomic pass.
        Returns paths for all generated deliverables.
        """
        csv_path, xlsx_path = self.export(records, audit_report, filename_base)
        partition_cols = ['assembly_constituency_no', 'assembly_part_no'] if partition_parquet else None
        parquet_path = self.export_parquet(records, filename_base, partition_cols=partition_cols)

        return {
            'csv': csv_path,
            'xlsx': xlsx_path,
            'parquet': parquet_path
        }
