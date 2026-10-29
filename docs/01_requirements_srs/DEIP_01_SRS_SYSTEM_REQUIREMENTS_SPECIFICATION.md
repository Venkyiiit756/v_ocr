# Software Requirements Specification (SRS) & System Specification
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.0)

**Document Reference:** DEIP-SRS-V2.0-DEFINITIVE  
**Compliance Standard:** ISO/IEC/IEEE 29148:2018 / IEEE 830-1998  
**Classification:** Census-Grade Demographic Ingestion & Electoral Intelligence Platform  
**Target Scope:** 721,735 Electors across Pithapuram (AC 37), Kakinada Rural (AC 38), and Peddapuram (AC 39) $\rightarrow$ Extensible to 40,000,000+ Electors Statewide  
**Status:** Approved Baseline (SDLC Phase 1)  

---

## 1. Introduction, Business Context & System Objectives

### 1.1 Purpose & Vision
This document establishes the exhaustive, formal Software Requirements Specification (SRS) for the **Distributed Electoral Intelligence Platform (DEIP V2.0)**. 

DEIP V2.0 is an enterprise-tier, distributed, census-grade document processing and data intelligence platform engineered to ingest, extract, sanitize, reconcile, classify, audit, and analyze official Election Commission of India (ECI) scanned electoral rolls. The system transforms unstructured, degraded, dot-matrix, and multi-format PDF voter rolls into an authoritative, 100% provenance-backed ground-truth relational dataset with **zero tolerance for hallucination, zero dropped records, and 0.00% false positives** on protected demographic surnames.

### 1.2 Core Problem Statement & Forensic Learnings
Decades of programmatic electoral roll parsing in India have suffered from systemic engineering flaws:
1. **Upstream Optical Character Recognition (OCR) Fragility:**  
   Standard OCR engines (e.g. naive Tesseract, EasyOCR, cloud vision APIs) fail on low-resolution dot-matrix rolls, producing character stem splitting (`K` $\rightarrow$ `kik`/`kkl` in `Nakikaa`), faint ascender dropouts (`d` $\rightarrow$ `c` in `Macish`), dropped crossbars (`t` $\leftrightarrow$ `r` in `Peditedia`), rounded bottom fusions (`-rad`/`-rag` for `-rao`, `-babl` for `-babu`), and severed Telugu vowel diacritics.
2. **Permanent Loss of Data Lineage (The "Black Box" Defect):**  
   Legacy extraction pipelines stripped away PDF file origins, page numbers, card box indices, bounding box coordinates, optical confidence vectors, and raw unedited OCR dumps. As a result, when data anomalies arose, forensic auditing was impossible without manual PDF searching.
3. **Boundary Ingestion Drift & Misalignment:**  
   Naive boundary detection algorithms using simple contour heuristics or rigid page-division math `(sno - 1) // 30 + 2` failed catastrophically when encountering administrative section breaks, resulting in blank card crops, off-by-one card shifts, and duplicate concentric detections.
4. **Demographic Bias & Overfitting Hallucinations:**  
   Naive regex cleanup scripts frequently mutilated genuine minority, classical Sanskrit, Anglo-Christian, Islamic, and rare Telugu surnames (e.g., mutating classical Kamma/Kapu `Boppana` into `Boppanna`, mistaking classical Hindu `Pasham` for Urdu `Pasha`, or converting Biblical `David` or Sanskrit `Kiran` into vowel-ended Telugu words).
5. **Operational Rigidity:**  
   Pipelines were built either strictly for offline batch files or strictly for manual browser downloads, lacking an autonomous, rate-limited crawler capable of solving voice CAPTCHAs, or a real-time observability and time-machine replay system.

DEIP V2.0 is designed from first principles to resolve every one of these failure modes.

---

## 2. ECI Document Structure, Taxonomy & Physical Realities

The platform shall natively handle the complete physical and administrative morphology of official ECI Electoral Rolls across Andhra Pradesh:

```
+--------------------------------------------------------------------------------------------------+
|                            ECI ELECTORAL ROLL COMPONENT TAXONOMY                                 |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  1. TITLE & SUMMARY SECTION (Page 1):                                                            |
|     - Assembly Constituency (AC) Name & Number, Parliamentary Constituency Name.                 |
|     - Polling Station Part Number, Polling Station Name & Building Address (English & Telugu).   |
|     - Revenue Mandal, Village / Ward Name, Police Station, Pin Code.                             |
|     - Administrative Census Aggregate Table: Total Male, Female, Third Gender, and Net Electors. |
|                                                                                                  |
|  2. GEOGRAPHIC & MAP SECTION (Page 2):                                                           |
|     - Cadastral / Polling Station Layout Map and Polling Station Building Frontage Photograph.   |
|                                                                                                  |
|  3. DEMOGRAPHIC ELECTOR CARD PAGES (Pages 3 to N-2):                                             |
|     - Form Invariant: Up to 30 individual voter cards arranged in a 10 Rows x 3 Columns matrix.  |
|     - Section Breaks: End-of-street / section division boundaries where trailing card slots      |
|       on the page are deliberately blank (e.g., card slots 21 to 30 unprinted).                  |
|                                                                                                  |
|  4. SUPPLEMENTARY REVISION & DELETION LISTS (Pages N-1 to N):                                    |
|     - Form 6 Supplementary Additions (Newly enrolled electors).                                  |
|     - Form 7 Deletions (Electors deceased or migrated - marked with diagonal strikethroughs).    |
|     - Form 8 Modifications (Corrected demographic entries).                                      |
|     - Final Summary Revision Aggregate Table.                                                    |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### 2.1 Individual Voter Card Anatomy
Each demographic card within the $10 \times 3$ matrix is physically divided into three distinct zones:
* **Zone A (Header Bar - Top 22%):** Contains the Booth Serial Number (`booth_sno`, left-aligned or centered) and the ECI Elector Photo Identity Card Number (`epic_no`, right-aligned, 10-character alphanumeric: 3 letters + 7 digits).
* **Zone B (Demographic Body - Bottom 78%, Left 72%):** Multi-line dot-matrix demographic text containing:
  - Line 1: Elector's Name (`voter_name`)
  - Line 2: Relative's Name (`rel_name`) and Relationship Marker (`Father`, `Husband`, `Mother`, `Guardian`, `Other`)
  - Line 3: House / Door Number (`door_no`)
  - Line 4: Age (`age`) and Gender (`gender`)
* **Zone C (Photograph Box - Bottom 78%, Right 28%):** Bounded photographic portrait box containing elector photo or `"Photo Available"` placeholder badge.

---

## 3. Operational Modes & Dual-Source Ingestion Specifications

The platform shall support two primary ingestion modes and an automatic hybrid fallback mode:

```
                                  +-----------------------+
                                  |   INGESTION ROUTER    |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
                     ▼                                                 ▼
        +-------------------------+                       +-------------------------+
        |   MODE 1: LOCAL AIRGAP   |                       |  MODE 2: HEADLESS CRAWL |
        +-------------------------+                       +-------------------------+
        | - Local Directory Walk  |                       | - Playwright Chromium   |
        | - Header Byte Validation|                       | - Acoustic CAPTCHA Solv |
        | - SHA-256 Checksums     |                       | - Session / Rate Limit  |
        | - Zero Network Outbound |                       | - Exponential Backoff   |
        +------------+------------+                       +------------+------------+
                     |                                                 |
                     +------------------------+------------------------+
                                              |
                                              ▼
                                 +-------------------------+
                                 |  MODE 3: AUTO-FALLBACK  |
                                 +-------------------------+
                                 | - Read local cache first|
                                 | - Detect corrupt / miss |
                                 | - Autonomous targeted   |
                                 |   crawl of missing Part |
                                 +-------------------------+
```

### 3.1 Mode 1: Local Provisioned Ingestion (Air-Gapped Batch Mode)
* **SPEC-ING-01:** The system shall ingest pre-downloaded electoral roll PDFs directly from local file systems, network mounts (NFS/SMB), or object storage (MinIO/S3).
* **SPEC-ING-02:** The system shall execute fully air-gapped without requiring any external internet connectivity.
* **SPEC-ING-03:** The file scanner shall verify every input PDF via:
  1. Magic byte validation (`%PDF-` in the first 1024 bytes).
  2. SHA-256 cryptographic checksum calculation.
  3. PDF trailer EOF parsing to detect truncated or zero-byte downloads.
* **SPEC-ING-04:** Missing Part Assertion: Given constituency $AC$ and expected part count $N$ (e.g. Pithapuram $N=242$, Kakinada Rural $N=264$, Peddapuram $N=201$), the scanner shall identify any missing parts in the range $[1, N]$ before starting processing.

### 3.2 Mode 2: Headless Autonomous Portal Crawler
* **SPEC-ING-05:** The system shall provide an autonomous crawler built on headless Chromium (via Playwright) capable of navigating the Chief Electoral Officer (CEO) Andhra Pradesh portal (`https://ceoandhra.nic.in`) and the national ECI portal.
* **SPEC-ING-06:** Acoustic Voice CAPTCHA Solver:
  - The crawler shall automatically trigger the portal's `"Play Voice CAPTCHA"` audio stream.
  - The audio stream (WAV buffer) shall be intercepted and fed into a local `faster-whisper` acoustic speech recognition model (`base` / `small` model running on `CTranslate2` C++ engine).
  - The model shall transcribe the spoken numbers and characters in $< 1.5$ seconds with $\ge 96.5\%$ first-pass transcription accuracy.
* **SPEC-ING-07:** Anti-Throttling & Resilience:
  - The crawler shall implement a token-bucket rate limiter enforcing a configurable maximum request rate (default: 1 request every 2.5 seconds per worker).
  - On HTTP 429 (Too Many Requests), HTTP 503, or connection reset, the crawler shall back off exponentially with random jitter:
    $$T_{\text{backoff}} = \min(60, 2^{\text{retry}} + \text{Uniform}(0, 2))$$
  - Automatic session cookie, viewport, and CSRF token persistence across requests.

### 3.3 Mode 3: Hybrid Cache-First Auto-Fallback
* **SPEC-ING-08:** When configured in hybrid mode, the dispatcher shall check the local directory first. If Part $P$ is missing, empty, or has an invalid PDF header, the dispatcher shall dynamically schedule a targeted crawl task for Part $P$ while the rest of the pipeline proceeds concurrently.

---

## 4. Functional Requirements (FR)

### 4.1 Document Rasterization & Image Engineering
* **FR-01 (300 DPI Native Grayscale Rasterization):**  
  The system shall render all PDF elector pages at **300 DPI native resolution** using PyMuPDF (MuPDF C-engine) in **8-bit continuous anti-aliased grayscale** ($2479 \times 3508$ pixels for standard A4). 1-bit binarized thresholding (Otsu / Adaptive Gaussian) shall be strictly prohibited during initial rasterization to prevent character stem erosion.
* **FR-02 (Contrast Limited Adaptive Histogram Equalization - CLAHE):**  
  To equalize faded dot-matrix ribbon ink across uneven page scans, the system shall apply CLAHE:
  - Contextual tile grid: $8 \times 8$ pixels.
  - Histogram clip limit: $\beta = 2.0$.
  - Continuous grayscale contrast stretching before character boundary detection.
* **FR-03 (Hough Transform Micro-Deskewing):**  
  The system shall detect dominant horizontal card divider lines using the Probabilistic Hough Transform (`cv2.HoughLinesP`). If the median page tilt angle $|\theta| \in [0.1^\circ, 5.0^\circ]$, the image shall be rotated by $-\theta$ using bicubic interpolation with white boundary border filling.

### 4.2 Boundary Detection & Spatial Geometry
* **FR-04 (ECI Form Invariant Enforcement):**  
  The system shall enforce the physical layout rule: a standard demographic page contains at most 30 voter cards arranged in 10 rows and 3 columns.
* **FR-05 (IoU Non-Maximum Suppression - NMS):**  
  Candidate bounding boxes detected via morphological contour analysis shall be deduplicated using two-tier suppression:
  1. Euclidean center distance threshold: If Euclidean distance between card centroids $< 80$ pixels, suppress the smaller box.
  2. Intersection over Union (IoU) threshold:
     $$\text{IoU}(B_1, B_2) = \frac{\text{Area}(B_1 \cap B_2)}{\text{Area}(B_1 \cup B_2)} \ge 0.40 \implies \text{suppress}$$
* **FR-06 (Vertical Indic Subscript Padding):**  
  Because Telugu retroflex consonants and subscript conjuncts (`వత్తులు` such as `-dla`, `-rma`, `-kka`, `-tta`) frequently extend below the baseline and touch the printed border, every detected card bounding box $(x, y, w, h)$ shall be padded vertically by **$+15\%$** (top headroom and bottom footroom) into the inter-card gutter:
  $$y_{\text{padded}} = \max(0, y - 0.05h), \quad h_{\text{padded}} = \min(H_{\text{page}} - y_{\text{padded}}, 1.15h)$$
* **FR-07 (Section-Break Awareness & Slot Indexing):**  
  The detector shall identify administrative section breaks where trailing card slots on a page are blank. Unprinted slots shall be indexed and tagged as `EMPTY_SLOT` without shifting or misaligning the serial numbering or page coordinates of subsequent cards.
* **FR-08 (Geometric Grid Fallback):**  
  If morphological contour detection discovers fewer than 25 or more than 30 boxes on a demographic page (and the page is not an end-of-section break or supplement), the system shall automatically fall back to geometric $10 \times 3$ grid interpolation anchored to the page margins.

### 4.3 Multi-Zone Optical Character Recognition (OCR) Engine
* **FR-09 (Dual-Zone Ingestion Strategy):**  
  Each isolated card crop shall be segmented and processed through dedicated OCR zones:
  - **Zone A (Header: SNO & EPIC ID):**  
    - Crop region: Top 22% of card height, right 58% of card width for EPIC; top 22% height, left 42% for SNO.
    - Preprocessing: Bicubic upscaling $2.0\times$, contrast enhancement.
    - OCR Configuration: `--psm 7` (Single text line) or `--psm 8` (Single word).
    - Whitelist Constraint: `-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`.  
      *(Strictly eliminates optical symbol leaks such as `|`, `~`, `§`, `©`, `\ufffd`).*
  - **Zone B (Demographic Body: Voter Name, Relative Name, Door No, Age, Gender):**  
    - Crop region: Lower 78% of card height, left 72% of card width.
    - Preprocessing: Native 300 DPI CLAHE, bicubic upscaling $1.8\times$.
    - OCR Configuration: `--psm 6` (Uniform block of text).
    - Blacklist Constraint: `-c tessedit_char_blacklist=§©®¢°~\\{}[]|\`^$#@*`.
* **FR-10 (Compiled Domain Lexicon Injection - `user-words`):**  
  The OCR engine's neural LSTM beam-search decoder shall be pre-loaded with the **Canonical Andhra Surname Lexicon (CASL)** containing **20,791 unique Andhra surnames** via `tessdata/eng.user-words`. This shall bias the beam-search decoder towards valid Telugu surnames and suppress unpronounceable optical errors at the point of ingestion.
* **FR-11 (Token & Character Confidence Vector Extraction):**  
  The OCR engine shall extract and persist word-level and character-level optical confidence scores ($0.00$ to $1.00$) via Tesseract TSV output (`image_to_data`). Every elector record shall retain its mean card confidence and token-level confidence arrays.

### 4.4 Entity Extraction, Sanitization & Normalization
* **FR-12 (Label Bleed Sanitization):**  
  The parsing engine shall purge all OCR-corrupted permutations of field labels from elector demographic fields, including:
  `Father`, `Fathar`, `Fether`, `Husband`, `Hushend`, `Hushand`, `Mother`, `Mothar`, `Guardian`, `Name`, `Mame`, `Namie`, `Narne`, `Narre`, `Nama`, `Narme`, `Namet`, `Warne`, `Nate`, `Nane`, `House`, `Howse`, `Number`, `Nurnber`, `Photo`, `Available`, `Age`, `Gender`, `Gencler`, `Ganclar`, `Gander`.
* **FR-13 (EPIC Normalization & Lookalike Substitution):**  
  The parser shall validate all EPIC IDs against the standard ECI regular expression `^[A-Z]{3}[0-9]{7}$`. In the numeric suffix, controlled character lookalike substitutions shall be applied:
  - `O`, `o`, `Q`, `D`, `U` $\rightarrow$ `0`
  - `I`, `i`, `l`, `|`, `T` $\rightarrow$ `1`
  - `Z` $\rightarrow$ `2`
  - `d`, `A` $\rightarrow$ `4`
  - `S`, `s`, `E` $\rightarrow$ `5`
  - `G` $\rightarrow$ `6`
  - `/`, `?` $\rightarrow$ `7`
  - `B`, `R` $\rightarrow$ `8`
  - `P`, `C` $\rightarrow$ `9`
* **FR-14 (EPIC Prefix Kerning Restoration):**  
  The parser shall repair known dot-matrix kerning fusions for constituency prefixes:
  - Pithapuram (AC 37): `YOUM` $\rightarrow$ `YOU14`, `YOUN` $\rightarrow$ `YOU1`, `Y0U`/`YQU`/`VOU`/`YDU` $\rightarrow$ `YOU`, `BOCK`/`8CK`/`BCR` $\rightarrow$ `BCK`.
  - Kakinada Rural (AC 38): `IMZN` $\rightarrow$ `IMZ1`, `IM2Z`/`IMUZ`/`INZ`/`1MZ`/`LMZ` $\rightarrow$ `IMZ`, `U0N`/`VON` $\rightarrow$ `UON`, `GH2`/`GZ`/`CHZ` $\rightarrow$ `GHZ`.
  - Peddapuram (AC 39): `WUZM` $\rightarrow$ `WUZ14`, `WLZM`/`WIZM` $\rightarrow$ `WUZ`, `AP` series.
* **FR-15 (Age Bounding & High-Age Zonal Re-OCR):**  
  - Age values shall be validated against the physiological bound $18 \le \text{Age} \le 110$.
  - Age parsing shall search tokens from the bottom-up using strict word boundaries to prevent substring collisions with elector names (e.g. `Nageswararao`).
  - **Age 97 Re-OCR Trigger:** If an extracted age is $\ge 90$ or exactly `97`, the system shall trigger a surgical re-OCR with high-contrast CLAHE to distinguish between genuine centenarians and faint `27`, `37`, or `47`.
* **FR-16 (Gender Normalization & Inferencing):**  
  - Gender shall be standardized to `Male`, `Female`, or `Third Gender`.
  - Inferencing rule: If relationship type is `Husband`, elector gender must be set to `Female`.
* **FR-17 (Door / House Number Sanitization):**  
  Door numbers shall have extraneous label artifacts stripped, noise symbols (`¢`, `°`, `§`) normalized to hyphens or slashes, and must contain at least one digit to be considered valid.

### 4.5 Linguistic Engine & Demographic Safeguards
* **FR-18 (128 Deterministic Optical Glyph Confusions):**  
  The token engine shall apply the complete catalog of 128 verified optical glyph replacements:
  - Ascender loops: `cl` $\rightarrow$ `d` (`prasacl` $\rightarrow$ `prasad`, `kacliyala` $\rightarrow$ `kadiyala`).
  - Mirror ascenders: `d` $\leftrightarrow$ `b` (`tatapubi` $\rightarrow$ `Tatapudi`, `surampubi` $\rightarrow$ `Surampudi`, `mummibi` $\rightarrow$ `Mummadi`).
  - Kerning fusions: `rn` $\rightarrow$ `m` in standard Telugu roots (`rarnana` $\rightarrow$ `ramana`, `arnma` $\rightarrow$ `amma`), protected from mutating `PROTECTED_RN`.
  - Split diagonal stems: `kik`/`kkl`/`kiaa` $\rightarrow$ `kk` (`Nakikaa` $\rightarrow$ `Nakka`, `klukika` $\rightarrow$ `Kukka`).
  - Masculine suffixes: `-rad`/`-raq`/`-rag` $\rightarrow$ `-rao` (anchored to 45 known Telugu masculine stems like `Venkata-`, `Appala-`, `Subba-`, `Satya-`); `-rajl`/`-raiu` $\rightarrow$ `-raju`; `-babl`/`-bablu` $\rightarrow$ `-babu`.
* **FR-19 (23 Space-Split Surnames):**  
  The token engine shall detect and rejoin compound surnames split across whitespace by dot-matrix print gaps:
  `('ga', 'ttem')` $\rightarrow$ `Gattem`, `('gol', 'lapalli')` $\rightarrow$ `Gollapalli`, `('ko', 'ppisetti')` $\rightarrow$ `Koppisetti`, `('me', 'disetti')` $\rightarrow$ `Medisetti`, `('va', 'samsetti')` $\rightarrow$ `Vasamsetti`, `('ta', 'tapudi')` $\rightarrow$ `Tatapudi`, `('su', 'rampudi')` $\rightarrow$ `Surampudi`, `('kommi', 'needi')` $\rightarrow$ `Kommineedi`, `('pabbi', 'needi')` $\rightarrow$ `Pabbineedi`, `('chinta', 'palli')` $\rightarrow$ `Chintapalli`, `('konda', 'palli')` $\rightarrow$ `Kondapalli`, `('bavi', 'setti')` $\rightarrow$ `Bavisetti`, etc.
* **FR-20 (Leading Double Consonant Stripping):**  
  Border touches that produce leading duplicated consonants (`kkommineedi` $\rightarrow$ `Kommineedi`, `ggllapalli` $\rightarrow$ `Gollapalli`) shall be stripped when length $\ge 4$.
* **FR-21 (Whitelisted Ajanta Suffix Restorations):**  
  Truncated vowel endings shall only be expanded if the base token matches:
  - 23 Whitelisted Village `-ur` $\rightarrow$ `-uri` Surnames (`Kommur` $\rightarrow$ `Kommuri`, `Yendamur` $\rightarrow$ `Yendamuri`, `Vallur` $\rightarrow$ `Valluri`, `Maddur` $\rightarrow$ `Madduri`, etc.).
  - 9 Whitelisted `-shett` $\rightarrow$ `-shetti` Surnames (`Medishett` $\rightarrow$ `Medishetti`, `Vasamshett` $\rightarrow$ `Vasamshetti`, `Koppishett` $\rightarrow$ `Koppishetti`, etc.).
  - 5 Whitelisted `-red` $\rightarrow$ `-reddy` Surnames (`Abbired` $\rightarrow$ `Abbireddy`, `Pedired` $\rightarrow$ `Pedireddy`, `Ramired` $\rightarrow$ `Ramireddy`, etc.).
* **FR-22 (The Immutable Safety Barrier - 0.00% False Positive Rule):**  
  Automated token mutation shall be **strictly prohibited** if the target token belongs to any of the following protected classes:
  1. **Absolute Vocalic Immunity:** Classical Telugu micro-surnames (`Boppana`, `Chavala`, `Peeta`, etc.) ending in valid vowels shall never have consonants or vowels added.
  2. **`Pasham` Cultural Safeguard:** Classical Hindu Telugu nominalizer `-am` shall be protected; `Pasham` must never be modified or classified as Islamic `Pasha`.
  3. **Sanskrit Halanta Blocklist (`PROTECTED_HALANTA_BLOCKLIST`):** Masculine halanta names ending in consonants (`Kiran`, `Charan`, `Pavan`, `Kalyan`, `Kumar`, `Naveen`, `Praveen`, `Prasad`, `Bharath`, `Siddharth`) shall never be suffixed with Ajanta vowels.
  4. **Anglo-Christian Blocklist (`CHRISTIAN_TOKENS`):** Biblical given names (`David`, `John`, `Paul`, `Peter`, `Samuel`, `Daniel`, `Joseph`, `Stephen`, `Philip`, `Thomas`, `James`, `Jacob`, `Mary`, `Martha`) shall never be modified.
  5. **Islamic Nomenclature Safeguards (`ISLAMIC_TOKENS`):** Arabic/Urdu names (`Shaik`, `Syed`, `Pathan`, `Khan`, `Mohammad`, `Hussain`, `Hameed`, `Rasheed`, `Bibi`, `Khatoon`) shall never have Telugu suffixes appended.

### 4.6 Spatial Household Graph & Bayesian Consensus Engine
* **FR-23 (Bipartite Household Graph Construction):**  
  Electors shall be dynamically partitioned into a bipartite graph keyed by `(Constituency, Part, Normalized_Door_No)`.
* **FR-24 (Intra-Card Surname Reconciliation):**  
  Where an elector's surname is truncated but the co-listed relative's surname on the same card is complete (e.g. Elector `Koppisett Durga`, Father `Koppisetti Apparao`), the elector surname shall be reconciled to the canonical relative surname.
* **FR-25 (Bayesian Spatial Household Consensus):**  
  Where an elector's surname suffers from optical print degradation (e.g. `Peditedia` vs `Pediredla` at Door 1-8; `Madish` vs `Medisetti` at Door 4-40B), the consensus engine shall compute the posterior probability:
  $$P(S \mid O, \text{Household}) = \frac{P(O \mid S) \cdot P(S \mid \text{Household})}{\sum_{S' \in \mathcal{S}} P(O \mid S') \cdot P(S' \mid \text{Household})}$$
  If the posterior $P(S_{\text{consensus}} \mid O, \text{Household}) \ge 0.85$, the outlier shall be resolved to the household consensus surname, provided $O \notin \text{ProtectedBlocklist}$.

### 4.7 Surgical Multi-Pass Re-OCR Ladder
* **FR-26 (Surgical Re-OCR Triggers):**  
  A card shall automatically enter the Surgical Re-OCR Ladder if any of the following conditions occur:
  1. `voter_name == rel_name` (card parser line-collision error).
  2. `voter_name == '-'` (missing elector name).
  3. `rel_name == '-'` (missing relative name).
  4. `epic_no == '-'` (missing EPIC ID).
  5. `door_no == '-'` (missing door number).
  6. `age == '-'` or `age == 97` (potential centenarian artifact).
  7. `gender == '-'` (missing gender).
  8. `mean_card_conf < 0.60` (low-confidence anomaly).
* **FR-27 (Five-Tier Escalation Ladder):**  
  - Tier 1: High-resolution $2.2\times$ bicubic crop of Zone A with `--psm 7` alphanumeric whitelist.
  - Tier 2: Sparse-text `--psm 11` crop of Header line.
  - Tier 3: Isolated $1.8\times$ bicubic crop of Zone B with `--psm 6` and CASL `user-words` injection.
  - Tier 4: Contrast-stretched CLAHE with dynamic tile sizing ($4 \times 4$ contextual grid).
  - Tier 5: Controlled Otsu binarization fallback for unread numeric door/age tokens.

### 4.8 Permanent Data Provenance & Forensic Time-Machine Replay
* **FR-28 (Permanent Provenance Schema):**  
  Under no circumstances shall any pipeline stage or exporter drop provenance fields. Every elector record must permanently retain all 32 fields in the **Permanent Provenance Schema**:
  1. `elector_id` (UUID / Canonical string: `AP_{AC}_P{Part}_S{Sno:04d}`)
  2. `assembly_constituency_no` (int)
  3. `assembly_constituency_name` (str)
  4. `assembly_part_no` (int)
  5. `booth_sno` (int)
  6. `epic_no` (str)
  7. `voter_name_en` (str)
  8. `voter_name_te` (str, if bilingual roll)
  9. `rel_type` (str)
  10. `rel_name_en` (str)
  11. `rel_name_te` (str)
  12. `door_no` (str)
  13. `normalized_door_no` (str)
  14. `age` (int)
  15. `gender` (str)
  16. `linguistic_group` (str: `T`, `M`, `C`, `O`)
  17. `source_pdf_filename` (str)
  18. `source_pdf_sha256` (str)
  19. `page_no` (int)
  20. `box_index` (int, 1-30)
  21. `bbox_x` (int)
  22. `bbox_y` (int)
  23. `bbox_w` (int)
  24. `bbox_h` (int)
  25. `crop_image_s3_uri` (str)
  26. `mean_card_conf` (float, 0.00-1.00)
  27. `token_confidences_json` (JSON)
  28. `raw_ocr_dump` (str)
  29. `status` (str: `Active`, `Quarantined`, `Re-OCR-Repaired`)
  30. `audit_trail` (JSON array of transformations)
  31. `created_at` (ISO timestamp)
  32. `engine_version` (str: `DEIP-2.0.0`)
* **FR-29 (Card Crop Blob Storage):**  
  Every detected voter card crop shall be persisted as a lossless PNG in object storage (`MinIO / S3`), keyed by `s3://crops/{ac}/{part}/{box_id}.png`.
* **FR-30 (Forensic Time-Machine Replay API & CLI):**  
  The system shall provide sub-50ms visual verification via CLI (`deip inspect --part {P} --sno {S}`) and REST API (`/api/v1/electors/{id}/crop`), displaying the original 300 DPI crop with bounding box overlays, token confidence heatmaps, raw OCR text, and household consensus evidence side-by-side.
* **FR-31 (Automated Red-Tier Quarantine Queue):**  
  Any card that fails all 5 tiers of surgical re-OCR or retains `mean_card_conf < 0.60` shall be routed to the `anomalies.red_tier` dead-letter queue for human-in-the-loop audit without halting or polluting the clean master dataset.

### 4.9 Observability, Telemetry & Status Monitoring
* **FR-32 (Prometheus Telemetry Exporter):**  
  The platform shall expose Prometheus-compliant metrics on `/metrics`:
  - `deip_elector_processed_total{ac, part, status}`
  - `deip_ocr_confidence_histogram{ac, zone}`
  - `deip_surgical_reocr_events_total{ac, reason}`
  - `deip_stage_duration_seconds{stage="rasterize|detect|ocr|consensus"}`
  - `deip_dropped_records_total` *(Must strictly be 0)*
* **FR-33 (Structured JSON Logging):**  
  All logging across services shall emit structured JSON lines to standard output containing: `timestamp`, `level`, `service`, `correlation_id`, `ac_no`, `part_no`, `page_no`, `box_index`, and `message`.
* **FR-34 (Live Status Push via WebSockets / SSE):**  
  The platform shall provide real-time status streaming to the operational dashboard via WebSockets and Server-Sent Events (SSE), transmitting parts completed, cards processed per second, queue lag, and anomaly rates.
* **FR-35 (Shadow / Dry-Run Verification Mode):**  
  The engine shall support a `--shadow-mode` flag where new algorithms run against historical baseline outputs, generating diff reports showing exact token changes before modifying the master database.

---

## 5. Non-Functional Requirements (NFR)

* **NFR-01 (Throughput & Multiprocessing Scalability):**  
  The system shall process at least **150 cards/second** on a 32-core compute node, completing a 236,000-elector constituency (e.g. Pithapuram AC 37) in under 30 minutes.
* **NFR-02 (Zero Demographic False Positives - Census Precision):**  
  The false positive mutation rate on protected cultural, Sanskrit, Anglo-Christian, and Islamic surnames shall be **$0.00\%$** ($100\%$ precision).
* **NFR-03 (Zero Data Loss & Strict Provenance Invariant):**  
  Under no condition shall an elector record be dropped. Total output electors must strictly equal total input detected cards across all parts: $\Delta = 0$.
* **NFR-04 (Fault Isolation & Poison Pill Resilience):**  
  A corrupt PDF, unreadable page, or out-of-memory error on a single card shall not crash worker processes. Failed tasks shall be isolated to the Dead-Letter Queue (DLQ).
* **NFR-05 (Idempotency & Safe Checkpointing):**  
  All pipeline operations shall be strictly idempotent. Re-running a part, page, or entire constituency shall produce bit-identical results without duplicate records.
* **NFR-06 (Sub-50ms Audit Query Latency):**  
  Single-elector provenance queries, image crop URLs, and audit history lookups via the API shall respond in $< 50\text{ms}$ at 99th percentile ($p99$).
* **NFR-07 (OpenShift / Kubernetes Non-Root Security Compliance):**  
  All container images shall execute under arbitrary dynamic user IDs (OpenShift `restricted-v2` SCC) with non-root permissions: `USER 10001` and group ownership `chgrp -R 0 /app && chmod -R g=u /app`.
* **NFR-08 (Air-Gapped Disconnected Deployment):**  
  Container images must bundle all neural network weights (`faster-whisper`), Tesseract language models (`eng`, `tel`), and the CASL surname lexicon internally to enable deployment on air-gapped clusters without internet access.
* **NFR-09 (Memory Bound per Worker):**  
  Each layout and OCR worker process shall operate with an RSS memory footprint of $\le 750\text{ MB}$, preventing memory leaks through aggressive explicit garbage collection (`gc.collect()`) after each page rasterization.
* **NFR-10 (Deterministic Master Output Parquet & CSV):**  
  Master deliverables shall be emitted in Parquet format (Snappy compressed, $< 150$ bytes/record) and UTF-8-SIG CSV/XLSX with styled corporate summary audit sheets.
* **NFR-11 (Horizontal Auto-Scaling):**  
  Worker fleets on Kubernetes / OpenShift shall scale dynamically between 4 and 64 replicas via KEDA based on RabbitMQ queue depth.
* **NFR-12 (Data Retention & Encryption at Rest):**  
  All elector database records and MinIO crop blobs shall support encryption at rest (AES-256) and immutable audit log retention.

---

## 6. Detailed Use Case Catalog

### Use Case UC-01: Air-Gapped Local Ingestion with Complete Provenance
- **Primary Actor:** Pipeline Administrator / Operations Engineer
- **Trigger:** Command `deip ingest --source local --path /data/rolls/AC37/ --ac 37`.
- **Preconditions:** Local directory contains 242 scanned PDF files for Pithapuram.
- **Main Flow:**
  1. Ingestion service performs directory walk, verifies `%PDF-` magic bytes, computes SHA-256 hashes, and confirms all 242 parts are present.
  2. Dispatcher pushes 242 part messages to RabbitMQ queue `roll.ingest.tasks`.
  3. Layout workers rasterize pages at 300 DPI continuous grayscale, apply CLAHE contrast enhancement, and run IoU NMS boundary detection with $+15\%$ vertical Indic padding.
  4. Card crops are uploaded to MinIO object storage (`s3://crops/37/{part}/{box}.png`) and metadata published to `card.ocr.tasks`.
  5. OCR worker fleet executes dual-zone parsing using compiled CASL `user-words` DAWG dictionary and extracts token confidence vectors.
  6. Consensus arbiter executes intra-card and Bayesian household surname reconciliation.
  7. Electors committed to PostgreSQL 16 and master Parquet files with 100% provenance retention.
- **Postconditions:** Master voter dataset contains 236,000+ electors; Prometheus reports `deip_dropped_records_total = 0`.

---

### Use Case UC-02: Autonomous Portal Crawling with Acoustic Voice CAPTCHA Solver
- **Primary Actor:** Ingestion Scheduler / Autonomous Crawler
- **Trigger:** System detects Part 182 of Peddapuram (AC 39) is missing or corrupted.
- **Preconditions:** Network access to CEO Andhra Pradesh portal enabled.
- **Main Flow:**
  1. Crawler initializes headless Playwright Chromium instance with anti-bot fingerprint masking.
  2. Navigates to Polling Station directory for AC 39 and selects Part 182.
  3. Crawler clicks `"Play Audio CAPTCHA"` button and intercepts audio WAV buffer.
  4. Faster-Whisper transcribes acoustic numbers/letters via CTranslate2 in 1.2 seconds.
  5. Crawler inputs CAPTCHA response and submits form.
  6. Portal returns binary PDF stream.
  7. Crawler validates `%PDF-` header bytes, writes `roll_part_182.pdf` to disk, and pushes task to `roll.ingest.tasks`.
- **Alternative Flow (CAPTCHA Rejection):** If portal responds with `"Invalid CAPTCHA"`, crawler applies exponential backoff with jitter and retries with a fresh session (up to 5 attempts) before escalating to DLQ.

---

### Use Case UC-03: Forensic Time-Machine Visual Elector Audit
- **Primary Actor:** Electoral Analyst / Legal Auditor
- **Trigger:** Auditor questions why elector Sno 265 in Part 241 is named `Pediredla` when raw text reads `Peditedia`.
- **Main Flow:**
  1. Auditor opens dashboard UI `/inspect` or executes `deip inspect --ac 37 --part 241 --sno 265`.
  2. API gateway queries PostgreSQL for elector UUID `AP_37_P241_S0265`.
  3. API retrieves 300 DPI card crop from MinIO, bounding box coordinates `[x=450, y=1200, w=720, h=280]`, and raw OCR dump.
  4. Displays side-by-side visual evidence:
     - Panel 1: Original high-resolution card crop highlighting the letter `r` vs `t` with token confidence $0.52$.
     - Panel 2: Raw OCR dump showing unedited text `Peditedia`.
     - Panel 3: Household Consensus graph showing co-residents at Door 1-8 (Sno 263, Sno 266) with canonical surname `Pediredla` ($P = 0.98$).
     - Panel 4: Complete immutable audit log showing timestamp, rule ID `RULE_BAYES_HOUSEHOLD`, and before/after values.
- **Postconditions:** Auditor verifies visual and mathematical proof in $< 50\text{ms}$ with zero ambiguity.

---

### Use Case UC-04: Automated Quarantining of Degraded Cards (Red Tier)
- **Primary Actor:** Automated Quality Gate
- **Trigger:** OCR Worker processes a card with severe water damage or torn paper.
- **Main Flow:**
  1. OCR Worker executes 5-tier surgical re-OCR ladder; all attempts yield `mean_card_conf = 0.48` ($< 0.60$).
  2. Quality Gate marks record status as `STATUS_QUARANTINED` and publishes payload to `anomalies.red_tier`.
  3. Diagnostic crop generated with bounding box overlay and low-confidence tokens highlighted in red.
  4. Record routed to Human-in-the-Loop review dashboard (`/api/v1/qc/anomalies`).
  5. Clean master dataset remains unpolluted by low-confidence hallucinations.

---

## 7. Multi-Level Verification & Acceptance Quality Gates

The system shall be formally verified against 5 rigorous quality gates prior to production sign-off:

```
+--------------------------------------------------------------------------------------------------+
|                              5-LEVEL ACCEPTANCE QUALITY GATES                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  GATE 1: UNIT LOGIC & TOKEN NORMALIZATION                                                        |
|  - 100% pass rate on 128 glyph replacements, 23 split surnames, and EPIC prefix regexes.          |
|                                                                                                  |
|  GATE 2: OPTICAL AMBIGUITY REGRESSION (FORENSIC PROOFS)                                          |
|  - Part 6 Sno 595: Proved Card "APPARAD NAKKAA"       -> Apparao Nakka (Pass)                   |
|  - Part 241 Sno 265: Proved Card "Pediredia" (Letter r) -> Chellarao Pediredla (Pass)            |
|  - Part 109 Sno 603: Proved Card "Madish" (Letter d)   -> Chellarao Medisetti (Pass)             |
|  - Part 96 Sno 356: Proved Card "Ketinidi" (Literal)   -> Chellarao Ketinidi (Pass)              |
|                                                                                                  |
|  GATE 3: PROVENANCE RETENTION & ZERO LOSS                                                        |
|  - Input Cards Detected == Output Records Ingested (Delta = 0).                                  |
|  - 100.00% of records retain source_pdf, page_no, box_index, bbox_pts, and raw_ocr_dump.         |
|                                                                                                  |
|  GATE 4: DEMOGRAPHIC SAFETY & ZERO FALSE POSITIVES                                               |
|  - False Positive Rate on Protected Tokens (Boppana, Pasham, Kiran, David, Shaik) == 0.00%.      |
|                                                                                                  |
|  GATE 5: LARGE-SCALE CONSTITUENCY BENCHMARK                                                      |
|  - Pithapuram (236,000 electors) processed in < 30 minutes on 32-core node.                      |
|  - EPIC Extraction Rate >= 99.85%, Age Validity Rate >= 99.90%.                                  |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 8. Requirements Traceability Matrix (RTM)

| Requirement ID | Requirement Category | Target Component | Verification Gate |
| :--- | :--- | :--- | :--- |
| **FR-01** | Rasterization | `LayoutWorker` (PyMuPDF) | Gate 1 & 5 |
| **FR-02** | Contrast Enhancement | `ImagePreproc` (OpenCV CLAHE) | Gate 2 |
| **FR-03** | Deskewing | `HoughDeskew` | Gate 1 |
| **FR-04, 05** | Boundary Detection | `RobustCardDetector` (IoU NMS) | Gate 3 |
| **FR-06** | Indic Padding | `RobustCardDetector` (+15% margin) | Gate 2 |
| **FR-07, 08** | Section Breaks & Grid | `RobustCardDetector` (Grid Fallback) | Gate 3 |
| **FR-09** | Dual-Zone Ingestion | `OCRWorker` (Zone A / Zone B) | Gate 1 & 2 |
| **FR-10** | DAWG Lexicon Injection | Tesseract C-API (`eng.user-words`) | Gate 2 |
| **FR-11** | Confidence Profiling | `OCRWorker` (TSV parser) | Gate 3 |
| **FR-12, 13, 14**| EPIC Normalization | `VoterCardParser` | Gate 1 & 5 |
| **FR-15, 16, 17**| Demographics & Age 97 | `VoterCardParser` (Re-OCR Ladder) | Gate 1 & 2 |
| **FR-18, 19, 20**| Linguistic Engine | `LinguisticSuite` | Gate 1 & 4 |
| **FR-21** | Ajanta Suffix Restorations | `LinguisticSuite` (Whitelists) | Gate 1 & 4 |
| **FR-22** | Immutable Safety Barrier | `LinguisticSuite` (Blocklists) | Gate 4 |
| **FR-23, 24, 25**| Household Consensus | `ConsensusArbiter` (Bayesian Prior)| Gate 2 & 4 |
| **FR-26, 27** | Surgical Re-OCR Ladder | `SurgicalReocrService` | Gate 2 |
| **FR-28, 29** | Provenance Retention | `MasterExporter` & MinIO Storage | Gate 3 |
| **FR-30, 31** | Time-Machine & Quarantine | API Gateway & DLQ | Gate 3 |
| **FR-32, 33, 34**| Observability | Prometheus & WebSocket Gateway | Gate 5 |
| **FR-35** | Shadow Mode | `ReconciliationEngine` | Gate 5 |
| **SPEC-ING-01..08**| Dual-Source Ingestion | Local Scanner & Playwright Crawler | Gate 5 |
