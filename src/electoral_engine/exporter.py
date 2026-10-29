"""
Professional Excel and CSV Exporter with Automated Styling and Auditing.
Generates publication-ready Excel workbooks and CSV files for any electoral dataset.
"""

import os
import csv
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class ElectoralExporter:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export(self, records, audit_report, filename_base='Master_Voter_Directory'):
        df = pd.DataFrame(records)
        
        # Rename Serial No to Ward Serial No if present
        if 'Serial No' in df.columns and 'Ward Serial No' not in df.columns:
            df.rename(columns={'Serial No': 'Ward Serial No'}, inplace=True)

        preferred_cols = [
            'Ward No',
            'Ward Serial No',
            'EPIC No',
            'Voter Name (English)',
            'Voter Name (Telugu)',
            'Father / Husband / Guardian Name',
            'Relationship Type',
            'Door / House No',
            'Age',
            'Gender',
            '2025 Assembly Part No (Baseline)',
            '2025 Booth Serial No',
            'Polling Station No',
            'Polling Station Name (English)',
            'Polling Station Name (Telugu)',
            'Municipal Corporation (English)',
            'Municipal Corporation (Telugu)',
            'Status',
            'Match Confidence'
        ]
        
        # Reorder columns
        existing_cols = [c for c in preferred_cols if c in df.columns]
        other_cols = [c for c in df.columns if c not in preferred_cols]
        df = df[existing_cols + other_cols]

        csv_path = os.path.join(self.output_dir, f"{filename_base}.csv")
        xlsx_path = os.path.join(self.output_dir, f"{filename_base}.xlsx")

        # 1. Save CSV
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')

        # 2. Save Styled Excel Workbook
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Master Voters', index=False)

            # Build Summary tab
            summary_rows = [
                {'Metric': 'Total Ground Truth Electors', 'Value': audit_report.get('total_ground_truth', len(df))},
                {'Metric': 'Electors Matched to Roll Cards', 'Value': audit_report.get('total_resolved', 0)},
                {'Metric': 'Overall Resolution Rate', 'Value': audit_report.get('resolution_rate', 'N/A')},
                {'Metric': 'Exact EPIC Matches', 'Value': audit_report.get('exact_epic_matches', 0)},
                {'Metric': 'Fuzzy / High-Confidence Name Matches', 'Value': audit_report.get('fuzzy_or_name_matches', 0)},
                {'Metric': 'Unmatched / Pending Review', 'Value': audit_report.get('unmatched', 0)},
                {'Metric': 'Father / Relative Name Filled', 'Value': int((df['Father / Husband / Guardian Name'] != '-').sum()) if 'Father / Husband / Guardian Name' in df else 0},
                {'Metric': 'Door / House Number Filled', 'Value': int((df['Door / House No'] != '-').sum()) if 'Door / House No' in df else 0},
                {'Metric': 'Age Populated', 'Value': int((df['Age'] != '-').sum()) if 'Age' in df else 0},
                {'Metric': 'Gender Populated', 'Value': int((df['Gender'] != '-').sum()) if 'Gender' in df else 0},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Audit & Summary', index=False)

        # Apply formatting
        wb = openpyxl.load_workbook(xlsx_path)
        ws_data = wb['Master Voters']
        ws_sum = wb['Audit & Summary']

        # Theme Colors
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

        # Format Data Sheet Headers
        for col_idx in range(1, len(df.columns) + 1):
            cell = ws_data.cell(row=1, column=col_idx)
            cell.fill = navy_header
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border

        # Format Rows with alternating colors
        for row_idx in range(2, len(df) + 2):
            fill_hex = 'F9FBFD' if row_idx % 2 == 0 else 'FFFFFF'
            row_fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type='solid')
            for col_idx in range(1, len(df.columns) + 1):
                c = ws_data.cell(row=row_idx, column=col_idx)
                c.fill = row_fill
                c.border = thin_border
                val_str = str(c.value or '').strip()
                if val_str.isdigit() or (len(val_str) <= 10 and not ' ' in val_str):
                    c.alignment = center_align
                else:
                    c.alignment = left_align

        # Auto-adjust column widths
        for col in ws_data.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_data.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 42)

        # Format Summary Sheet
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
