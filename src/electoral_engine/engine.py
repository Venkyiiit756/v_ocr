"""
Core Pipeline Engine: Orchestrates Dynamic CV Detection,
Multithreaded Dual-Zone OCR Parsing, Entity Reconciliation, and Export.
High-throughput document image processing optimized for zero I/O lock contention.
"""

import os
import glob
import time
import tempfile
import threading
import pymupdf
import cv2
import numpy as np
import subprocess
import pandas as pd
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from .detector import VoterCardDetector
from .parser import VoterCardParser
from .reconciler import ElectoralReconciler
from .exporter import ElectoralExporter

class ElectoralPipelineEngine:
    def __init__(self, tesseract_cmd=None, workers=2):
        if tesseract_cmd is None:
            self.tess_exe = shutil.which('tesseract') or r'C:\Users\vamsi\Tesseract-OCR\tesseract.exe'
        else:
            self.tess_exe = tesseract_cmd
        self.workers = workers
        self.detector = VoterCardDetector()
        self.parser = VoterCardParser()
        self._temp_dir = tempfile.gettempdir()

    def _ocr_subimage(self, crop_bgr, psm=6):
        """
        Runs Tesseract OCR on a subimage with pre-binarization/grayscale conversion
        via in-memory pipe (stdin) to eliminate disk I/O, file locks, and temp directory bloat.
        """
        if len(crop_bgr.shape) == 3:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop_bgr

        padded = cv2.copyMakeBorder(gray, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
        success, buf = cv2.imencode('.png', padded)
        if not success:
            return ""

        try:
            res = subprocess.run(
                [self.tess_exe, 'stdin', 'stdout', '--psm', str(psm)],
                input=buf.tobytes(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False
            )
            return res.stdout.decode('utf-8', errors='ignore').strip()
        except Exception:
            return ""

    def _ocr_composite_card(self, card_bgr):
        """
        Combines the upscaled EPIC header zone and body text zone into a single
        border-free composite buffer, cutting Tesseract invocations to 1 call per card.
        """
        ch, cw = card_bgr.shape[:2]
        header_h = int(ch * 0.22)
        if len(card_bgr.shape) == 3:
            gray = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = card_bgr

        epic_crop = gray[5:max(6, header_h - 2), int(cw * 0.42):max(int(cw * 0.42) + 1, cw - 8)]
        if epic_crop.size > 0:
            epic_crop = cv2.resize(epic_crop, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
        body_crop = gray[int(ch * 0.19):max(int(ch * 0.19) + 1, ch - 6), 6:max(7, int(cw * 0.72))]

        eh, ew = epic_crop.shape[:2]
        bh, bw = body_crop.shape[:2]
        max_w = max(ew, bw) + 30
        canvas = np.full((eh + bh + 50, max_w), 255, dtype=np.uint8)
        if eh > 0 and ew > 0:
            canvas[15:15 + eh, 15:15 + ew] = epic_crop
        if bh > 0 and bw > 0:
            canvas[15 + eh + 20:15 + eh + 20 + bh, 15:15 + bw] = body_crop

        success, buf = cv2.imencode('.png', canvas)
        if not success:
            return ""

        try:
            res = subprocess.run(
                [self.tess_exe, 'stdin', 'stdout', '--psm', '6'],
                input=buf.tobytes(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False
            )
            return res.stdout.decode('utf-8', errors='ignore').strip()
        except Exception:
            return ""

    def process_pdf_page(self, pdf_path, page_num, part_no, dpi=200):
        """
        Renders a page, dynamically detects content card regions via CV contours,
        and extracts structured fields via single-pass composite OCR parsing.
        """
        doc = pymupdf.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        else:
            img = img.copy()
        del pix
        doc.close()

        boxes = self.detector.detect_boxes(img)
        page_records = []

        for b_idx, (x, y, w, h) in enumerate(boxes, 1):
            card = img[y:y+h, x:x+w]
            ch, cw = card.shape[:2]

            full_card_txt = self._ocr_composite_card(card)
            card_data = self.parser.parse_card(full_card_txt, fallback_sno=b_idx)

            if not card_data.get('epic_no'):
                header_h = int(ch * 0.22)
                epic_zone = card[4:max(5, header_h), int(cw * 0.38):max(int(cw * 0.38) + 1, cw - 6)]
                if epic_zone.size > 0:
                    up_epic = cv2.resize(epic_zone, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
                    up_txt = self._ocr_subimage(up_epic, psm=7)
                    norm = self.parser.normalize_epic_candidate(up_txt)
                    if norm:
                        card_data['epic_no'] = norm
                    del up_epic
                if not card_data.get('epic_no') and epic_zone.size > 0:
                    gray_ep = cv2.cvtColor(epic_zone, cv2.COLOR_BGR2GRAY) if len(epic_zone.shape) == 3 else epic_zone
                    up3_ep = cv2.resize(gray_ep, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                    _, bw_ep = cv2.threshold(up3_ep, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    for psm_mode in (8, 7):
                        bw_ep_txt = self._ocr_subimage(bw_ep, psm=psm_mode)
                        norm = self.parser.normalize_epic_candidate(bw_ep_txt)
                        if norm:
                            card_data['epic_no'] = norm
                            break
                    del gray_ep, up3_ep, bw_ep
                if not card_data.get('epic_no'):
                    header_crop = card[6:header_h, 6:cw-6]
                    header_txt = self._ocr_subimage(header_crop, psm=11)
                    norm = self.parser.normalize_epic_candidate(header_txt)
                    if not norm:
                        fallback_parsed = self.parser.parse_card(header_txt, fallback_sno=b_idx)
                        norm = fallback_parsed.get('epic_no')
                    if norm:
                        card_data['epic_no'] = norm

            # Inline Surgical Fallback: Only triggered on the ~3-5% of cards missing a body field or with voter_name == rel_name
            name_collision = bool(card_data.get('voter_name') and card_data.get('voter_name') == card_data.get('rel_name'))
            if name_collision or not (card_data.get('voter_name') and card_data.get('rel_name') and card_data.get('door_no') and card_data.get('age') and card_data.get('gender')):
                body_crop = card[int(ch * 0.16):ch - 4, 6:int(cw * 0.78)]
                if body_crop.size > 0:
                    up_body = cv2.resize(body_crop, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
                    body_txt = self._ocr_subimage(up_body, psm=6)
                    b_parsed = self.parser.parse_card(body_txt, fallback_sno=b_idx)
                    if name_collision and b_parsed.get('voter_name') and b_parsed.get('voter_name') != card_data.get('rel_name'):
                        card_data['voter_name'] = b_parsed['voter_name']
                    for k in ('voter_name', 'rel_type', 'rel_name', 'door_no', 'age', 'gender'):
                        if not card_data.get(k) and b_parsed.get(k):
                            card_data[k] = b_parsed[k]
                    if not (card_data.get('age') and card_data.get('door_no')):
                        gray_b = cv2.cvtColor(up_body, cv2.COLOR_BGR2GRAY) if len(up_body.shape) == 3 else up_body
                        _, bw_b = cv2.threshold(gray_b, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        bw_txt = self._ocr_subimage(bw_b, psm=6)
                        bw_parsed = self.parser.parse_card(bw_txt, fallback_sno=b_idx)
                        for k in ('voter_name', 'rel_type', 'rel_name', 'door_no', 'age', 'gender'):
                            if not card_data.get(k) and bw_parsed.get(k):
                                card_data[k] = bw_parsed[k]
                        del gray_b, bw_b
                    del up_body
                if card_data.get('rel_type') == 'Husband' and not card_data.get('gender'):
                    card_data['gender'] = 'Female'

            card_data['part_no'] = part_no
            card_data['page_no'] = page_num + 1
            card_data['box_index'] = b_idx
            page_records.append(card_data)

        del img
        return page_records

    def process_roll_pdf(self, pdf_path, part_no, cache_prefix="peddapuram", log_file="peddapuram_live_log.txt"):
        """
        Processes an entire document roll across multithreaded worker pools.
        Includes page-level incremental checkpointing for crash-proof resume.
        """
        import json
        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
        doc.close()

        cache_file = f"cache_{cache_prefix}_part_{part_no}.json"
        partial_file = f"partial_cache_{cache_prefix}_part_{part_no}.json"

        if os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
            print(f"Loading cached records for Part {part_no} from {cache_file}...", flush=True)
            with open(cache_file, 'r', encoding='utf-8') as f:
                all_records = json.load(f)
            for r in all_records:
                if r.get('raw_text'):
                    updated = self.parser.parse_card(r['raw_text'], fallback_sno=r.get('booth_sno'))
                    r['epic_no'] = updated.get('epic_no') or r.get('epic_no', '')
                    r['voter_name'] = updated.get('voter_name') or r.get('voter_name', '')
                    r['rel_type'] = updated.get('rel_type') or r.get('rel_type', '')
                    r['rel_name'] = updated.get('rel_name') or r.get('rel_name', '')
                    r['door_no'] = updated.get('door_no') or r.get('door_no', '')
                    r['age'] = updated.get('age') or r.get('age')
                    r['gender'] = updated.get('gender') or r.get('gender', '')
            print(f"Loaded {len(all_records)} cached cards for Part {part_no}.", flush=True)
            return all_records

        pages_to_process = list(range(2, total_pages - 1))
        content_page_count = len(pages_to_process)

        # Load incremental page checkpoint if interrupted mid-part
        page_cache = {}
        if os.path.exists(partial_file):
            try:
                with open(partial_file, 'r', encoding='utf-8') as f:
                    page_cache = json.load(f)
            except Exception:
                page_cache = {}

        all_records = []
        remaining_pages = []
        for pno in pages_to_process:
            if str(pno) in page_cache:
                all_records.extend(page_cache[str(pno)])
            else:
                remaining_pages.append(pno)

        completed_pages = len(pages_to_process) - len(remaining_pages)
        if completed_pages > 0:
            print(f"Resuming Part {part_no} from page checkpoint ({completed_pages}/{content_page_count} pages already done)...", flush=True)
        else:
            print(f"Processing Part {part_no} ({content_page_count} pages) with {self.workers} workers...", flush=True)

        if remaining_pages:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(self.process_pdf_page, pdf_path, pno, part_no): pno
                    for pno in remaining_pages
                }
                for fut in as_completed(futures):
                    pno = futures[fut]
                    completed_pages += 1
                    try:
                        recs = fut.result()
                        all_records.extend(recs)
                        page_cache[str(pno)] = recs
                        try:
                            tmp_part = f"{partial_file}.tmp"
                            with open(tmp_part, 'w', encoding='utf-8') as pf:
                                json.dump(page_cache, pf, ensure_ascii=False)
                            os.replace(tmp_part, partial_file)
                        except Exception:
                            pass
                        prog_line = f"  [OCR_PROGRESS] Part {part_no} | Page {completed_pages}/{content_page_count} done ({len(recs)} cards, {len(all_records)} total)"
                        print(prog_line, flush=True)
                        try:
                            with open(log_file, "a", encoding="utf-8") as lf:
                                lf.write(f"{time.strftime('[%Y-%m-%d %H:%M:%S]')} {prog_line.strip()}\n")
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"  Part {part_no} -> Error on page {pno + 1}: {e}", flush=True)

        all_records.sort(key=lambda r: (r.get('page_no', 0), r.get('box_index', 0)))

        for idx, rec in enumerate(all_records, 1):
            ocr_sno = rec.get('booth_sno')
            if ocr_sno and isinstance(ocr_sno, int) and abs(ocr_sno - idx) <= 2:
                rec['booth_sno'] = ocr_sno
            else:
                rec['booth_sno'] = idx

        try:
            tmp_cache = f"{cache_file}.tmp"
            with open(tmp_cache, 'w', encoding='utf-8') as f:
                json.dump(all_records, f, indent=2, ensure_ascii=False)
            os.replace(tmp_cache, cache_file)
            if os.path.exists(partial_file):
                os.remove(partial_file)
        except Exception:
            pass

        print(f"[OCR_DONE] Part {part_no} finished! Extracted {len(all_records)} total voter cards.", flush=True)
        return all_records

    def run_pipeline(self, ground_truth_csv, pdf_mapping, output_dir, file_prefix='Master_Records'):
        print(f"\n=======================================================", flush=True)
        print(f"STARTING DOCUMENT RECONCILIATION PIPELINE: {file_prefix}", flush=True)
        print(f"=======================================================", flush=True)

        df_gt = pd.read_csv(ground_truth_csv)
        gt_records = df_gt.to_dict(orient='records')
        print(f"Loaded {len(gt_records)} ground-truth records from {ground_truth_csv}", flush=True)

        all_extracted = []
        for part_no, pdf_path in pdf_mapping.items():
            if os.path.exists(pdf_path):
                recs = self.process_roll_pdf(pdf_path, part_no)
                all_extracted.extend(recs)
            else:
                print(f"Warning: PDF for Part {part_no} not found at {pdf_path}", flush=True)

        print(f"\nTotal records extracted across all rolls: {len(all_extracted)}", flush=True)

        reconciler = ElectoralReconciler(gt_records, key_field='EPIC No')
        enriched, audit = reconciler.reconcile(all_extracted)

        print("\n--- RECONCILIATION AUDIT ---", flush=True)
        for k, v in audit.items():
            print(f"  {k}: {v}", flush=True)

        exporter = ElectoralExporter(output_dir)
        csv_out, xlsx_out = exporter.export(enriched, audit, filename_base=file_prefix)

        print(f"\nDeliverables generated successfully:", flush=True)
        print(f"  CSV:  {csv_out}", flush=True)
        print(f"  XLSX: {xlsx_out}", flush=True)
        print(f"=======================================================\n", flush=True)
        return enriched, audit, csv_out, xlsx_out
