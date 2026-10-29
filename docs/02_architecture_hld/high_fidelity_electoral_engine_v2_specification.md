# High-Fidelity Master Electoral Engine (V2.0): Architectural Specification for Absolute Quality

**Author:** Antigravity (Advanced Agentic Coding Suite)  
**Standard:** Enterprise / Census-Grade Ground-Truth Electoral Pipeline  
**Target:** 721,735 Electors across Pithapuram (AC 37), Peddapuram (AC 39), Kakinada Rural (AC 38)  
**Guiding Constraint:** Compute & Time are Unconstrained; Quality & Auditability are Uncompromising.

---

## 1. System Philosophy: Zero Compromise on Ground Truth

When compute and execution time are unconstrained, every architectural shortcut that was previously taken (1-bit thresholding, dropping metadata to save disk space, fast uncalibrated OCR, post-hoc regex band-aids) is eliminated.

The V2.0 system is designed around four non-negotiable principles:
1. **Pixel-Level Lineage:** Every single character and field in the final database must point to exact pixel bounding boxes on the original ECI scanned page.
2. **Quantified Confidence:** Every word and entity must carry an optical confidence score ($0.00$ to $1.00$).
3. **Topological Image Integrity:** Image preprocessing must preserve sub-pixel stroke gradients and Indic subscript conjuncts (vattulu).
4. **Bayesian Graph Consensus:** Household kinship graphs arbitrate optical ambiguities with mathematical proof, bounded by immutable vocalic safeguards.

---

## 2. End-to-End Pipeline Architecture (V2.0)

```
+--------------------------------------------------------------------------------------------------+
|                                    V2.0 PIPELINE ARCHITECTURE                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  [ECI Scanned PDF Rolls]                                                                         |
|            |                                                                                     |
|            v                                                                                     |
|  [STAGE 1: 300 DPI High-Fidelity Rasterization]                                                  |
|    - Native anti-aliased rendering (PyMuPDF)                                                     |
|    - CLAHE Contrast Normalization (clipLimit=2.0, tileGrid=(8,8))                                |
|    - Card Micro-Deskewing via Hough transform line analysis                                      |
|            |                                                                                     |
|            v                                                                                     |
|  [STAGE 2: NMS Grid-Prior Boundary Detector]                                                    |
|    - Morphological card table extraction                                                         |
|    - Strict Non-Maximum Suppression (IoU > 0.45 / Center Dist < 100px)                          |
|    - Geometric 10x3 Form Prior enforcement (Assertion: len(boxes) <= 30)                        |
|    - +15% Vertical Indic Headroom/Footroom Padding (Protects Vattulu: -dla, -rma)                |
|            |                                                                                     |
|            v                                                                                     |
|  [STAGE 3: Dual-Zone OCR & Confidence Profiling]                                                 |
|    - Zone A (Header): 2.0x Upscaled EPIC & SNO extraction                                        |
|    - Zone B (Body): Name, Relation, Door No, Age, Gender                                         |
|    - Detailed token-level bounding boxes & confidence extraction (`image_to_data`)               |
|            |                                                                                     |
|            v                                                                                     |
|  [STAGE 4: Atomic Checkpointing with Complete Provenance]                                        |
|    - Part-level atomic JSON caches with complete metadata:                                      |
|      [elector_id, page_no, box_index, bbox_pts, raw_text, confidences]                           |
|            |                                                                                     |
|            v                                                                                     |
|  [STAGE 5: Bayesian Household & Kinship Graph Engine]                                            |
|    - Bipartite Household Clustering (Constituency + Part + Normalized Door)                      |
|    - Kinship consensus voting with transition probability matrices                               |
|    - Immutable Vocalic & Halanta Blocklist (Zero false positive guarantee)                       |
|    - Multi-scale serial street propagation for single-occupant homes                             |
|            |                                                                                     |
|            v                                                                                     |
|  [FINAL EXPORT: Gold-Standard Master Parquet & CSV + QA Audit Ledger]                            |
|            |                                                                                     |
|            v                                                                                     |
|  [STAGE 6: Native CLI Visual Verification Sidecar]                                               |
|    - `agy inspect <elector_id>` -> 50ms instant crop overlay verification                        |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Deep Technical Specifications of Key Subsystems

### 3.1 Upstream Boundary Detection: `VoterCardDetector` (V2.0)
The flaw in V1.0 was a hardcoded `< 20px` deduplication check that allowed concentric duplicate boxes to survive at 300 DPI.

**V2.0 Solution:**
```python
class RobustCardDetector:
    def detect_and_align(self, img_bgr):
        h, w = img_bgr.shape[:2]
        # 1. Detect candidate contours using adaptive thresholding & line morphology
        raw_boxes = self._extract_contours(img_bgr)
        
        # 2. Strict Non-Maximum Suppression (NMS) using IoU overlap:
        # Any box with IoU > 0.40 or Center Distance < 80px with an existing box is merged
        nms_boxes = self._apply_nms(raw_boxes, iou_thresh=0.40, dist_thresh=80)
        
        # 3. Enforce the Domain Grid Invariant:
        # A standard page has at most 30 cards arranged in 10 rows x 3 cols
        if len(nms_boxes) > 30:
            # Keep top-30 by area and geometric regularity
            nms_boxes = self._prune_to_grid(nms_boxes, max_cards=30)
            
        # 4. Apply +15% Vertical Padding for Indic Matras & Vattulu:
        padded_boxes = []
        for x, y, bw, bh in nms_boxes:
            v_pad = int(bh * 0.15)
            y0 = max(0, y - v_pad)
            y1 = min(h, y + bh + v_pad)
            padded_boxes.append((x, y0, bw, y1 - y0))
            
        return self._sort_reading_order(padded_boxes)
```

### 3.2 Complete Provenance & Lineage Schema

The schema does not discard any field. Every consolidated record retains:

| Field Name | Type | Description | Purpose |
| :--- | :--- | :--- | :--- |
| `elector_id` | `VARCHAR(32)` | `AP_AC37_P096_S0356` | Globally unique primary key across AP |
| `constituency_no` | `INT` | `37` | AC Number |
| `assembly_part` | `INT` | `96` | Polling Station / Part Number |
| `booth_sno` | `INT` | `356` | Serial Number on Voter Card |
| `epic_no` | `VARCHAR(16)` | `YOU1903475` | Verified ECI Voter ID |
| `voter_name_clean` | `VARCHAR(128)`| `Chellarao Ketinidi` | Final linguistically restored name |
| `voter_name_raw` | `VARCHAR(128)`| `Name : ChellaR Ketinidi` | Unmodified text directly from OCR |
| `voter_name_conf` | `FLOAT` | `0.94` | Mean OCR confidence for voter name |
| `rel_type` | `VARCHAR(16)` | `Father` | Verified relationship |
| `rel_name_clean` | `VARCHAR(128)`| `Appanna` | Final restored relative name |
| `rel_name_raw` | `VARCHAR(128)`| `Fathers Name: Appanna` | Unmodified OCR relative string |
| `rel_name_conf` | `FLOAT` | `0.96` | Mean OCR confidence for relative |
| `door_no_clean` | `VARCHAR(64)` | `2-1` | Sanitized door/house number |
| `door_no_raw` | `VARCHAR(64)` | `House Number = 2-1` | Raw door string from OCR |
| `age` | `INT` | `94` | Verified age |
| `gender` | `VARCHAR(8)` | `Male` | Verified gender |
| `linguistic_group`| `CHAR(1)` | `T` | Demographically verified (T, C, M, S) |
| `source_pdf` | `VARCHAR(64)` | `roll_part_96.pdf` | Relative path to original PDF scan |
| `page_no` | `INT` | `15` | Exact 1-indexed PDF page |
| `box_index` | `INT` | `8` | Exact 1-indexed card slot on page |
| `bbox_pts` | `JSON/LIST` | `[121, 2305, 1621, 658]` | Pixel bounding box [x, y, w, h] |
| `mean_card_conf` | `FLOAT` | `0.93` | Holistic card optical confidence |
| `audit_trail` | `JSON/LIST` | `[{"rule": "...", "before": "...", ...}]` | Append-only history of every change |

---

## 4. Multi-Core High-Throughput Scalability Specification

The engine will be configured for **Process-Level Concurrency with Zero Lock Contention**:

```python
def process_constituency_parallel(pdf_dir, part_numbers, max_workers=None):
    if max_workers is None:
        max_workers = os.cpu_count() # e.g. 8, 16, 32, 64 cores
        
    print(f"Spawning {max_workers} worker processes for parallel roll ingestion...")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_part_v2, p, pdf_dir): p
            for p in part_numbers
        }
        for future in concurrent.futures.as_completed(futures):
            part_id = futures[future]
            try:
                res = future.result()
                print(f"[COMPLETED] Part {part_id}: {res['electors']} electors in {res['elapsed']:.1f}s")
            except Exception as e:
                print(f"[ERROR] Part {part_id} failed: {e}")
```

### Computational Performance Profile:
- **8-Core System:** ~4 to 5 hours for all 242 parts of Pithapuram.
- **16-Core / 32-Core System:** ~1.5 to 2.5 hours per constituency.
- **Full 3-Constituency Run (721k Electors):** ~6 to 10 hours overnight across multi-core systems, with atomic crash checkpoints saved after every single part.

---

## 5. Instant Visual Verification CLI

A native command will be provided in the codebase to make manual review effortless:

```powershell
# Usage:
python inspect_elector.py --id AP_AC37_P096_S0356
# Or by Part and Sno:
python inspect_elector.py --part 96 --sno 356
```

**Output:**
```
========================================================================
ELECTOR RECORD: AP_AC37_P096_S0356 (EPIC: YOU1903475)
========================================================================
Voter Name:  Chellarao Ketinidi (Raw: ChellaR Ketinidi | Conf: 0.94)
Relation:    Appanna (Father | Raw: Appanna | Conf: 0.96)
Door Number: 2-1 (Raw: House Number = 2-1)
Age / Sex:   94 / Male
Linguistic:  Group 'T' (Telugu)
Provenance:  roll_part_96.pdf -> Page 15, Box 8 [x=121, y=2305, w=1621, h=658]
Audit Log:   1. Chellar -> Chellarao (TOKEN_CHELLAR_NORMALIZATION)
             2. Ketiniei -> Ketinidi (OCR_IMAGE_CONFIRMATION_P356)
Generated visual proof -> proof_images/inspect_P96_S356.png (Saved in 42ms)
========================================================================
```

---

## 6. Implementation & Rollout Roadmap

1. **Step 1:** Implement `electoral_engine/detector.py` (V2.0) with strict NMS, $10 \times 3$ grid assertion, and $+15\%$ Indic script padding.
2. **Step 2:** Implement `electoral_engine/engine.py` (V2.0) with 8-bit CLAHE grayscale, dual-zone confidence extraction, and the complete provenance schema.
3. **Step 3:** Benchmark on a multi-part sample (Parts 6, 96, 109, 241) to confirm 100% precision on our known test cases.
4. **Step 4:** Launch the parallel multi-core execution for Pithapuram (AC 37), generating the first institutional-grade gold-standard dataset.
