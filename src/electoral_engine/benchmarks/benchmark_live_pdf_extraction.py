"""
Benchmark: Real Scanned English Electoral Roll PDF Optical Extraction (DEIP V2.2)
Target: Kakinada City English Electoral Roll (roll_part_1.pdf)
Tests:
- Native 300 DPI Grayscale Rasterization
- Probabilistic Hough Deskewing
- Card Boundary Detection & IoU NMS
- Dual-Zone OCR (Zone A Header vs Zone B Body in English)
- 32-Field Provenance Extraction & Invariant Adherence
"""

import os
import sys
import time
import json
import zipfile
import logging
import cv2
import pymupdf
import numpy as np

# Reconfigure stdout to utf-8 for Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.electoral_engine.detector import VoterCardDetector
from src.electoral_engine.engine import DualZoneOCREngine
from src.electoral_engine.parser import VoterCardParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("pdf_benchmark")

ZIP_PATH = r"C:\Users\vamsi\Downloads\Voter_Analysis\Kakinada_City_2025_PDFs.zip"


def run_pdf_benchmark():
    if not os.path.exists(ZIP_PATH):
        logger.error(f"ZIP bundle not found at {ZIP_PATH}")
        return None

    print("\n" + "=" * 80)
    print("STARTING LIVE SCANNED ENGLISH ELECTORAL ROLL OPTICAL EXTRACTION BENCHMARK")
    print(f"Archive: {ZIP_PATH} -> roll_part_1.pdf (English Roll)")
    print("=" * 80 + "\n")

    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        pdf_bytes = z.read('roll_part_1.pdf')

    doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    total_pages = len(doc)
    print(f"Total Pages in Roll: {total_pages}")

    # Inspect Page 3 (0-indexed page 2, first voter content page)
    target_page_idx = 2 if total_pages > 2 else 0
    page = doc[target_page_idx]

    # 1. 300 DPI Rasterization
    t0 = time.time()
    pix = page.get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    render_time = time.time() - t0
    h_img, w_img = img.shape[:2]
    print(f"Page {target_page_idx + 1} Rasterized at 300 DPI: {w_img}x{h_img} in {render_time:.2f}s")

    # 2. Card Boundary Detection
    detector = VoterCardDetector(target_dpi=300, enable_grid_fallback=True)
    t1 = time.time()
    boxes = detector.detect_boxes(img)
    detect_time = time.time() - t1
    print(f"Detected {len(boxes)} Card Bounding Boxes in {detect_time:.2f}s (Target: 30 boxes per page)")

    # 3. Dual-Zone OCR & Parsing across detected cards (English mode)
    dual_ocr = DualZoneOCREngine(ocr_lang="eng")
    parser = VoterCardParser()
    gray_page = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    extracted_electors = []
    t_ocr_start = time.time()

    # Process first 5 cards for deep inspection
    inspect_count = min(5, len(boxes))
    print(f"\nExecuting Deep Dual-Zone English OCR on first {inspect_count} cards:")
    print("-" * 80)

    for idx, (x, y, w, h) in enumerate(boxes[:inspect_count], 1):
        t_card = time.time()
        card_crop = gray_page[y:y+h, x:x+w]
        
        # Strikethrough check
        restored_crop, is_strike = detector.detect_and_recover_strikethrough(card_crop)
        
        # Dual-Zone OCR
        ocr_res = dual_ocr.ocr_card(restored_crop)
        
        # Parsing
        metadata = {
            'ac_no': 38,
            'part_no': 1,
            'box_index': idx,
            'page_no': target_page_idx + 1,
            'source_pdf_filename': 'roll_part_1.pdf',
            'source_pdf_sha256': 'live_audit',
            'bbox_pts': [x, y, w, h],
            'mean_card_conf': ocr_res['mean_confidence'],
            'status': 'Deleted' if is_strike else 'Active'
        }
        record = parser.parse_card(ocr_res['raw_dump'], fallback_sno=idx, metadata=metadata)
        if ocr_res['epic_text']:
            norm_epic = parser.normalize_epic_candidate(ocr_res['epic_text'])
            if norm_epic:
                record['epic_no'] = norm_epic

        card_latency = time.time() - t_card
        extracted_electors.append(record)

        print(f"Card #{idx:02d} [{card_latency*1000:.0f}ms] | SNO: {record.get('booth_sno', '-'):3} | EPIC: {record.get('epic_no', '-'):10} | Name: '{record.get('voter_name_clean') or record.get('voter_name_en')}' | Rel: ({record.get('rel_type')}) '{record.get('rel_name_clean') or record.get('rel_name_en')}' | Door: '{record.get('door_no_clean') or record.get('door_no')}' | Age: {record.get('age', '-')} | Gender: {record.get('gender', '-')}")

    total_ocr_time = time.time() - t_ocr_start
    avg_per_card = (total_ocr_time / inspect_count) * 1000

    print("-" * 80)
    print(f"English OCR Benchmark Complete: {inspect_count} cards in {total_ocr_time:.2f}s (Average: {avg_per_card:.1f}ms / card)")
    print("=" * 80 + "\n")

    doc.close()
    return {
        'total_pages': total_pages,
        'boxes_detected': len(boxes),
        'render_time_sec': round(render_time, 2),
        'detect_time_sec': round(detect_time, 2),
        'avg_card_ms': round(avg_per_card, 1),
        'sample_records': extracted_electors
    }


if __name__ == '__main__':
    run_pdf_benchmark()
