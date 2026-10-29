# Test Strategy, Multi-Level Verification & Validation (V&V) Matrix
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.2)

**Document Reference:** DEIP-TEST-V2.2-DEFINITIVE  
**Compliance Standard:** ISO/IEC/IEEE 29119-3:2013 (Software Testing — Test Documentation)  
**Testing Philosophy:** Zero Tolerance for Hallucinations, Zero Dropped Records ($\Delta = 0$), and 0.00% False Positives on Protected Demographic Surnames  
**Scope:** 721,735 Verified Electors across Godavari Delta (AC 37, AC 38, AC 39) $\rightarrow$ Scalable to 40,000,000+ Statewide  
**Status:** Approved Definitive Baseline (SDLC Phase 4)  

---

## 1. Test Policy, Governance & Quality Philosophy

### 1.1 The Golden Invariants
In a census-grade electoral intelligence platform, traditional heuristic approximations (e.g. "95% accuracy is good enough") are categorically unacceptable. An error of 0.1% corrupts 40,000 legal citizen identities across a state. DEIP V2.2 enforces five non-negotiable **Golden Invariants**:

```
+--------------------------------------------------------------------------------------------------+
|                                  THE FIVE GOLDEN TEST INVARIANTS                                 |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  INVARIANT 1: ABSOLUTE DATA LINEAGE & ZERO RECORD LOSS (DELTA = 0)                                |
|  - Every card detected on a physical roll must yield exactly one master database record.          |
|  - Delta = Count(Input Physical Cards) - Count(Output Database Records) == 0.                     |
|  - 100.00% of records must permanently retain source_pdf, page_no, box_index, bbox_pts,           |
|    raw_ocr_dump, and token_confidences.                                                          |
|                                                                                                  |
|  INVARIANT 2: 0.00% FALSE POSITIVES ON PROTECTED DEMOGRAPHIC SURNAMES                             |
|  - False Positive Rate (FPR) on protected tokens (Boppana, Pasham, Kiran, David, Shaik,           |
|    Narna, Marni) must be exactly 0.0000%.                                                        |
|  - Dual-CASL Immunity: If an observed token exists in CASL, it is never mutated.                 |
|                                                                                                  |
|  INVARIANT 3: YOUNG ELECTOR REGEX INTEGRITY (AGES 18 & 19)                                       |
|  - The parser must NEVER swallow the leading digit '1' in young electors (Age 18 and 19).        |
|  - Non-greedy atomic boundary regex must assert zero drops across young voter cohorts.           |
|                                                                                                  |
|  INVARIANT 4: ZONAL INDEPENDENCE & BORDER ISOLATION                                              |
|  - Serial Number (SNO) border boxes must NEVER suppress EPIC extraction in Zone A.               |
|  - Photo Box (Zone C) must be geometrically excluded from OCR to prevent visual hallucinations.   |
|                                                                                                  |
|  INVARIANT 5: DETERMINISTIC AUDITABILITY & TIME-MACHINE REPLAY                                   |
|  - Every token mutation must be backed by an append-only JSON audit trail entry containing       |
|    rule_id, before_val, after_val, mathematical prior / household evidence, and UTC timestamp.   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. 5-Level Testing Hierarchy (ISO/IEC/IEEE 29119 Architecture)

```
+--------------------------------------------------------------------------------------------------+
|                                    5-LEVEL TESTING HIERARCHY                                     |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  LEVEL 1: UNIT & MATHEMATICAL ALGORITHM TESTS (L1)                                               |
|  - IoU NMS deduplication, CLAHE contrast math, Probabilistic Hough deskewing, Form 7 strikethrough|
|    morphological recovery, non-greedy age regex, EPIC lookalike normalizer, door number cleaner. |
|                                                                                                  |
|  LEVEL 2: COMPUTER VISION & OPTICAL GROUND-TRUTH REGRESSION (L2)                                 |
|  - Regression on physical gold-standard crops: Case 1 (Nakka), Case 2 (Pediredla),                |
|    Case 3 (Medisetti), Case 4 (Ketinidi), Age 97 repair, Form 7 DELETED rubber stamp recovery.   |
|                                                                                                  |
|  LEVEL 3: LINGUISTIC REPAIR SUITE & DEMOGRAPHIC IMMUNITY (L3)                                    |
|  - Full suite testing of all 18 empirical error families (19,500+ Gh->Ch, 12,000+ terminal l,    |
|    10,000+ authentic rn protection, 833 Q->D, 3,363 -rad->-rao, 3,641 -ull->-ulu respect plurals).|
|                                                                                                  |
|  LEVEL 4: SPATIAL HOUSEHOLD GRAPH & FULL-ROLL PROVENANCE (L4)                                    |
|  - Bipartite household consensus graph, Laplace-smoothed Dirichlet multinomial prior,            |
|    PostgreSQL 16 partitioned storage, Apache Parquet lake integrity, REST Time-Machine latency.  |
|                                                                                                  |
|  LEVEL 5: CHAOS RESILIENCY, CONCURRENCY & RECOVERY (L5)                                          |
|  - Abrupt worker SIGKILL, RabbitMQ unacked requeue, 0-byte corrupt PDF handling, Playwright     |
|    audio CAPTCHA retry with Whisper acoustic model, AMQP dead-letter queue routing.              |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Automated CI/CD Quality Gate Thresholds

Every candidate release in CI/CD must pass five quantitative Quality Gates before deployment:

| Quality Gate | Description | Metric Target | Blocking Condition |
| :--- | :--- | :---: | :---: |
| **GATE 1** | Optical Ambiguities & Ingestion | 100% pass on Proof Cases 1–4; Age 18/19 retention $\ge 99.9\%$ | Any failure blocks build |
| **GATE 2** | Mathematical Algorithms & NMS | Exact 30-box grid invariant; IoU NMS suppression $IoU \ge 0.40$ | Any off-by-one blocks build |
| **GATE 3** | Lineage & Provenance Retention | $\Delta = 0$ dropped cards; 100.00% provenance field non-null | Any missing metadata blocks build |
| **GATE 4** | Demographic Safety & Zero FP | False Positive Rate on protected tokens == **0.0000%** | Single mutation blocks build |
| **GATE 5** | Large-Scale Throughput & Resiliency | $\ge 150\text{ cards/sec}$; P99 API latency $< 40\text{ms}$; 100% crash recovery | Latency / drop blocks build |

---

## 4. Comprehensive Test Case Specifications

### 4.1 Level 1: Unit & Mathematical Algorithm Test Cases (L1)

| Test Case ID | Target Component | Input Stimulus | Execution Logic | Expected Outcome | Pass/Fail Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-L1-01** | `detector.apply_card_nms` | 2 candidate boxes: $B_1=(100, 100, 500, 200)$, $B_2=(105, 104, 495, 196)$ | Computes $IoU(B_1, B_2) \approx 0.94 \ge 0.40$ | Concentric duplicate $B_2$ is suppressed; exactly $B_1$ retained. | `len(retained) == 1` |
| **TC-L1-02** | `detector.apply_card_nms` | 31 candidate contours on a 30-card page due to ink bleed | Applies area sorting, centroid Euclidean distance ($< 80\text{px}$), and IoU | Eliminates spurious border box; returns exactly 30 valid boxes. | `len(retained) == 30` |
| **TC-L1-03** | `detector.apply_padding` | Card bounding box with $h = 600\text{px}$ | Applies vertical Indic subscript padding: $y_{\text{pad}} = y - 0.05h$, $h_{\text{pad}} = 1.15h$ | Bounds expand vertically by $+15\%$ ($690\text{px}$ total height), capturing Telugu vattulu. | $h_{\text{pad}} == \text{round}(1.15 \cdot h)$ |
| **TC-L1-04** | `detector.deskew` | Scanned page rotated by $+2.5^\circ$ | Probabilistic Hough transform detects line vectors; calculates median tilt $\theta = +2.5^\circ$ | Rotates page by $-2.5^\circ$ with constant white padding. | Residual angle $|\theta_{\text{res}}| < 0.2^\circ$ |
| **TC-L1-05** | `detector.strikethrough` | Card with diagonal strike line at $35^\circ$ across text | Hough angle filter flags $\phi \in [25^\circ, 65^\circ]$; creates rotated morphological kernel | Flags `is_deletion_strike = True`, subtracts mask, restores underlying text. | `status == 'Deleted'`, text restored |
| **TC-L1-06** | `parser.extract_valid_age` | Raw OCR text: `"Age : 18 Gender : Male"` | Non-greedy bottom-up regex `RE_AGE_BOTTOM_UP` | Captures exact integer `18`. Does not swallow ': 1'. | `age == 18` |
| **TC-L1-07** | `parser.extract_valid_age` | Raw OCR text: `"Age : 19 Gender : Female"` | Non-greedy bottom-up regex `RE_AGE_BOTTOM_UP` | Captures exact integer `19`. Does not swallow ': 1'. | `age == 19` |
| **TC-L1-08** | `parser.extract_valid_age` | Raw OCR text: `"Name: Nageswararao ... Age : 45"` | Bottom-up search on card text dump | Matches `"Age : 45"`, ignoring `"Age"` substring in `"Nageswararao"`. | `age == 45` |
| **TC-L1-09** | `parser.extract_valid_age` | Raw OCR text: `"Age : 197 Gender : Male"` | Evaluates 3-digit divider artifact where column pipe fused into `197` | Parses leading `1` as pipe; extracts authentic age `97` or `19`. | `18 <= age <= 110` |
| **TC-L1-10** | `parser.normalize_epic` | Candidate: `"YOUM12345"` (Pithapuram kerning fusion) | Regex `^(YOUM)(?=[0-9A-Z]{5}$)` replaces with `YOU14` | Normalizes to valid 10-char ECI EPIC: `"YOU1412345"`. | `re.match(r'^[A-Z]{3}[0-9]{7}$', epic)` |
| **TC-L1-11** | `parser.normalize_epic` | Candidate: `"IMZN123456"` (Kakinada Rural kerning fusion) | Regex `^(IMZN)(?=[0-9A-Z]{6}$)` replaces with `IMZ1` | Normalizes to valid 10-char ECI EPIC: `"IMZ1123456"`. | `re.match(r'^[A-Z]{3}[0-9]{7}$', epic)` |
| **TC-L1-12** | `parser.normalize_epic` | Candidate: `"WUZM12345"` (Peddapuram kerning fusion) | Regex `^(WUZM)(?=[0-9A-Z]{5}$)` replaces with `WUZ14` | Normalizes to valid 10-char ECI EPIC: `"WUZ1412345"`. | `re.match(r'^[A-Z]{3}[0-9]{7}$', epic)` |
| **TC-L1-13** | `parser.normalize_epic` | Candidate: `"YOU123O567"` (Letter 'O' for digit '0') | Lookalike dictionary replaces `O` with `0` in numeric suffix | Normalizes to valid `"YOU1230567"`. | `epic == "YOU1230567"` |
| **TC-L1-14** | `parser.normalize_door` | Raw door string: `"D.No: 3-109 Photo Available"` | Regex `RE_DOOR_RAW` strips label and photo trailing artifact | Outputs clean canonical `"3-109"`. | `door == "3-109"` |
| **TC-L1-15** | `parser.normalize_door` | Raw door string: `"NO J 1-21/A"` (DELETED stamp noise) | Strips rubber stamp noise `NO J`; extracts underlying number | Outputs clean canonical `"1-21/A"`. | `door == "1-21/A"` |
| **TC-L1-16** | `parser.normalize_door` | Raw door string: `"ఇంటి నెం. 4/40B"` (Telugu script label) | Strips Indic prefix; standardizes delimiters | Outputs clean canonical `"4/40B"`. | `door == "4/40B"` |
| **TC-L1-17** | `parser.household_key` | Inputs: `ac=37`, `part=96`, `door="2-1"` | Constructs compound string `AC{ac}_P{part:03d}_{door}` | Outputs `"AC37_P096_2-1"`. | `key == "AC37_P096_2-1"` |
| **TC-L1-18** | `parser.gender_infer` | Relationship: `"Husband"`, OCR Gender: `"-"` (unread) | Contextual inference rule executes | Infers elector gender as `"Female"`. | `gender == "Female"` |
| **TC-L1-19** | `parser.eval_conf` | Record with `mean_card_conf = 0.92`, all fields valid | Evaluates confidence against thresholds | Classifies as `"GREEN"` tier for direct master commit. | `tier == "GREEN"` |
| **TC-L1-20** | `parser.eval_conf` | Record with `mean_card_conf = 0.54` or missing EPIC | Evaluates confidence against thresholds | Classifies as `"RED"` tier for AMQP DLQ dead-letter routing. | `tier == "RED"` |

---

### 4.2 Level 2: Optical Ground-Truth Regression Suite (L2)

This suite runs against real physical image crops representing proven empirical ambiguities uncovered across the 721,735 electorate:

| Test Case ID | Reference Record | Input Image Crop Asset | Underlying Optical Defect | Target Expected Output | Mandatory Regression Assertion |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-L2-01** | AC 37 Part 6 Sno 595 | [`Proof_Case1_Part6_Sno595_Nakikaa.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case1_Part6_Sno595_Nakikaa.png) | Faint diagonal joint on `K` causing split stem `Nakikaa` | **`Nakka`** (అప్పారావు నక్క) | Must NOT contain letter `i` or `n`. Rejects `Nakkina`. |
| **TC-L2-02** | AC 37 Part 241 Sno 265 | [`Proof_Case2_Part241_Sno265_Peditedia.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case2_Part241_Sno265_Peditedia.png) | Missing 1-px crossbar on `t` (`Peditedia` vs `Pediredia`) | **`Pediredla`** (చెల్లారావు పెదిరెడ్ల) | Must contain `r` (`Pedired-`), never `t`. |
| **TC-L2-03** | AC 37 Part 109 Sno 603 | [`Proof_Case3_Part109_Sno603_Macish.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case3_Part109_Sno603_Macish.png) | Faint top riser on `d` loop (`Madish` read as `Macish`) | **`Medisetti`** (మేడిశెట్టి) | Resolves to canonical `Medisetti` via Sno 605 co-resident anchor. |
| **TC-L2-04** | AC 37 Part 96 Sno 356 | [`Proof_Case4_Part96_Sno356_Ketiniei.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case4_Part96_Sno356_Ketiniei.png) | Faint loop on `d` (`Ketiniei` vs `Ketinidi`) | **`Ketinidi`** (కేతినిడి) | Ends in `idi`, never `iei`. Confirmed by household consensus. |
| **TC-L2-05** | Blurred Age Card | Physical crop with dot-matrix smudged `"27"` | Faint top curve on `2` causing standard OCR to read `"97"` | **`27`** | Re-OCR with CLAHE contrast enhancement extracts true age `27`. |
| **TC-L2-06** | Zone A SNO Border | Physical card with heavy black rectangular box around `[ SNO ]` | Full-card `--psm 6` treats header row as table border | **SNO & EPIC extracted** | Isolated Zone A crop extracts both Serial Number and EPIC cleanly. |
| **TC-L2-07** | Deletion Stamp Card | Physical card with diagonal rubber stamp across Door No | Stamped text occludes underlying door `1-21/J` to `NO J` | **`1-21/J`** | Morphological line subtraction restores underlying number. |

---

### 4.3 Level 3: Linguistic Repair Suite & Demographic Immunity (L3)

This suite asserts that all 18 empirical error families are corrected while verifying **0.00% False Positives** on protected minority and rare surnames:

| Test Case ID | Target Linguistic Group | Input String / Context | Transformation Rule Under Test | Expected Output | Mandatory Immunity Constraint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-L3-01** | Velar/Palatal (`Gh-`) | `"Ghinta Apparao"` | `Gh-` $\rightarrow$ `Ch-` prefix repair | **`Chinta Apparao`** | Repaired (19,500+ record family) |
| **TC-L3-02** | Velar/Palatal (`Gh-`) | `"Ghellarao Chekka"` | `Gh-` $\rightarrow$ `Ch-` prefix repair | **`Chellarao Chekka`** | Repaired |
| **TC-L3-03** | Protected `Gh-` Stem | `"Ghantasala Venkateswarlu"` | `PROTECTED_GH_STEMS` Barrier | **`Ghantasala Venkateswarlu`** | **BLOCKED.** Never becomes `*Chantasala` |
| **TC-L3-04** | Protected `Gh-` Stem | `"Ghouse Mohiddin"` | `PROTECTED_GH_STEMS` Barrier | **`Ghouse Mohiddin`** | **BLOCKED.** Never becomes `*Chouse` |
| **TC-L3-05** | Capital `D` $\rightarrow$ `Q` Smudge | `"Qurga Prasad"` | `Q` $\rightarrow$ `D` bowl smudge repair | **`Durga Prasad`** | Repaired (833 record family) |
| **TC-L3-06** | Capital `D` $\rightarrow$ `Q` Smudge | `"Qandu Subbarao"` | `Q` $\rightarrow$ `D` bowl smudge repair | **`Dandu Subbarao`** | Repaired |
| **TC-L3-07** | Protected `Q-` Stem | `"Qureshi Shaik"` | `PROTECTED_Q_STEMS` Barrier | **`Qureshi Shaik`** | **BLOCKED.** Never becomes `*Dureshi` |
| **TC-L3-08** | Terminal `l` Family | `"Nallapl Venkanna"` | Terminal `-pl` $\rightarrow$ `-pu` repair | **`Nallapu Venkanna`** | Repaired (4,603 record family) |
| **TC-L3-09** | Terminal `l` Family | `"Rayudl Satyanarayana"` | Terminal `-dl` $\rightarrow$ `-du` repair | **`Rayudu Satyanarayana`** | Repaired (2,450 record family) |
| **TC-L3-10** | Terminal `l` Family | `"Vallurl Ramakrishna"` | Terminal `-url` $\rightarrow$ `-uri` repair | **`Valluri Ramakrishna`** | Repaired (2,190 record family) |
| **TC-L3-11** | Terminal `l` Family | `"Medisettl Apparao"` | Terminal `-settl` $\rightarrow$ `-setti` repair | **`Medisetti Apparao`** | Repaired (1,280 record family) |
| **TC-L3-12** | Terminal `l` Family | `"Sattirajil Varma"` | Terminal `-rajil` $\rightarrow$ `-raju` repair | **`Sattiraju Varma`** | Repaired (1,033 record family) |
| **TC-L3-13** | Terminal `l` Family | `"Yesubaabl Joseph"` | Terminal `-baabl` $\rightarrow$ `-babu` repair | **`Yesubabu Joseph`** | Repaired (1,831 record family) |
| **TC-L3-14** | Terminal `l` Female | `"Lakshml Satyavatl"` | Female terminal `-l` $\rightarrow$ `-i` repair | **`Lakshmi Satyavati`** | Repaired (3,056 record family) |
| **TC-L3-15** | Authentic `rn` Surnames | `"Narna Subbarao"` | `PROTECTED_RN` Barrier | **`Narna Subbarao`** | **BLOCKED.** Never mutated to `*Nama` (4,238 records) |
| **TC-L3-16** | Authentic `rn` Surnames | `"Marni Apparao"` | `PROTECTED_RN` Barrier | **`Marni Apparao`** | **BLOCKED.** Never mutated to `*Mami` (1,826 records) |
| **TC-L3-17** | Authentic `rn` Surnames | `"Karneedi Venkatrao"` | `PROTECTED_RN` Barrier | **`Karneedi Venkatrao`** | **BLOCKED.** Never mutated to `*Kameedi` (345 records) |
| **TC-L3-18** | Authentic `rn` Given | `"Aparna Annapurna"` | `PROTECTED_RN` Barrier | **`Aparna Annapurna`** | **BLOCKED.** Never mutated to `*Apama` (1,639 records) |
| **TC-L3-19** | Optical `rn` in Non-Sanskrit| `"Rnurthy Palla"` | Non-Sanskrit `^rn([aeiou])` $\rightarrow$ `m\1` | **`Murthy Palla`** | Repaired (1,329 record family) |
| **TC-L3-20** | Optical `rn` in Non-Sanskrit| `"Lakshrni Pilli"` | Conjunct `kshrn` $\rightarrow$ `kshm` | **`Lakshmi Pilli`** | Repaired |
| **TC-L3-21** | Masculine Honorific `-rad`| `"Venkateshwaraad Tida"` | Telugu stem `-rad` $\rightarrow$ `-rao` | **`Venkateshwararao Tida`** | Repaired (3,363 record family) |
| **TC-L3-22** | Masculine Honorific `-rad`| `"Murad Shaik"` | Halanta Blocklist Protection | **`Murad Shaik`** | **BLOCKED.** Never becomes `*Murao` |
| **TC-L3-23** | Respect Plural `-ull` | `"Thrimurthull Koppisetti"` | Terminal `-ull` $\rightarrow$ `-ulu` repair | **`Thrimurthulu Koppisetti`** | Repaired (3,641 record family) |
| **TC-L3-24** | ECI Card Label Bleed | `"Narmne Prasad Pilla"` | Strips pre-printed `'s Name:` token | **`Prasad Pilla`** | Repaired (2,128 record family) |
| **TC-L3-25** | Space-Split Surname | `["ga", "ttem", "Apparao"]` | `SPLIT_SURNAME_MAP` Rejoining | `["Gattem", "Apparao"]` | Rejoined (23 pattern family) |
| **TC-L3-26** | Leading Consonant Stutter | `"Kkommineedi Srinivas"` | Leading double consonant collapse | **`Kommineedi Srinivas`** | Collapsed (1,157 record family) |
| **TC-L3-27** | Triple Stutter Collapse | `"Appparao Penke"` | Triple consonant collapse | **`Apparao Penke`** | Collapsed (1,560 record family) |
| **TC-L3-28** | Trailing Echo Vowels | `"Adapaa Venkanna"` | Trailing duplicate vowel halt | **`Adapa Venkanna`** | Halted (310 record family) |
| **TC-L3-29** | Absolute Vowel Immunity | `"Boppana Apparao"` | Absolute Vocalic Immunity Rule | **`Boppana Apparao`** | **BLOCKED.** Never becomes `*Boppanna` |
| **TC-L3-30** | Pasham Cultural Safeguard | `"Pasham Srinivas"` | Pasham Nominalizer Lock | **`Pasham Srinivas` (Group T)** | **BLOCKED.** Never converted to `*Pasha` or `M` |
| **TC-L3-31** | Sanskrit Halanta Lock | `"Kiran Kumar"` | Sanskrit Halanta Protection | **`Kiran Kumar` (Group S)** | **BLOCKED.** Never becomes `*Kirani` |
| **TC-L3-32** | Biblical / Anglo Lock | `"David Raju Gadi"` | Christian / Biblical Protection | **`David Raju Gadi` (Group C)** | **BLOCKED.** Never becomes `*Davidi` |
| **TC-L3-33** | Anglo Caste Suffix Lock | `"Alfred Joseph Ratnakar"` | Western `-red` Blocklist | **`Alfred Joseph Ratnakar`** | **BLOCKED.** Never becomes `*Alfreddy` |
| **TC-L3-34** | Western Naidu Lock | `"Prem Ronald Jetty"` | Western `-nald` Blocklist | **`Prem Ronald Jetty`** | **BLOCKED.** Never becomes `*Ronaidu` |
| **TC-L3-35** | Toponymic Village Lock | `"Bahadur Shaik"` | Urdu / North Indian `-ur` Blocklist | **`Bahadur Shaik` (Group M)** | **BLOCKED.** Never becomes `*Bahaduri` |

---

### 4.4 Level 4: Lineage, Full-Roll Provenance & Data Lake Integration (L4)

| Test Case ID | Test Objective | Execution Logic & Verification SQL | Success Criteria |
| :--- | :--- | :--- | :--- |
| **TC-L4-01** | Provenance Completeness | `SELECT count(*) FROM master_electors WHERE source_pdf_filename IS NULL OR source_pdf_sha256 IS NULL OR page_no IS NULL OR box_index IS NULL OR bbox_pts IS NULL;` | **Result == 0** (100% Provenance Captured) |
| **TC-L4-02** | Raw OCR Dump Auditability | `SELECT count(*) FROM master_electors WHERE raw_ocr_dump IS NULL OR length(raw_ocr_dump) < 10;` | **Result == 0** (Zero dropped text dumps) |
| **TC-L4-03** | Mean Card Confidence Bound | `SELECT count(*) FROM master_electors WHERE mean_card_conf < 0.0 OR mean_card_conf > 1.0;` | **Result == 0** (All scores normalized to $[0, 1]$) |
| **TC-L4-04** | Partition Pruning Efficiency | Query `EXPLAIN ANALYZE SELECT * FROM master_electors WHERE assembly_constituency_no = 37 AND booth_sno = 500;` | Query planner scans *only* `master_electors_ac37`; execution $< 5\text{ms}$. |
| **TC-L4-05** | Parquet Data Lake Integrity | Reads `/lake/ac_no=37/part_no=096/data.parquet` via DuckDB; verifies row count against PostgreSQL master | Exact row count match; Snappy compression $< 150\text{ bytes/row}$. |
| **TC-L4-06** | REST Time-Machine API | Executes 1,000 concurrent requests to `GET /api/v1/electors/AP_37_P096_S0356/crop` | **p99 latency $< 40\text{ms}$**; returns lossless PNG with overlay. |

---

### 4.5 Level 5: Chaos, Concurrency & Resiliency (L5)

| Test Case ID | Fault Injection Stimulus | Subsystem Response & Automated Recovery | Pass/Fail Criteria |
| :--- | :--- | :--- | :--- |
| **TC-L5-01** | Worker process killed via `kill -9` while decoding card | RabbitMQ broker detects unacknowledged AMQP delivery; message automatically requeued to `card.crops.pending` and claimed by surviving worker. | Zero lost cards; zero duplicate records written to PostgreSQL. |
| **TC-L5-02** | Ingestion encountering zero-byte or corrupt PDF roll | Ingestion catches invalid PDF header, logs error with SHA-256 hash, marks part as `CORRUPTED`, and triggers crawler dispatch. | Main ingestion worker continues processing adjacent rolls without crashing. |
| **TC-L5-03** | Playwright crawler encountering audio CAPTCHA timeout | Audio solver retries with exponential backoff ($2\text{s}, 4\text{s}, 8\text{s}$), switching acoustic noise filter. | Maximum 3 retries; routes to DLQ if unrecoverable without stalling crawler pod. |
| **TC-L5-04** | PostgreSQL connection pool exhaustion (500 concurrent workers) | HikariCP/asyncpg pool queues requests; services apply circuit-breaker backoff. | No dropped connection exceptions; zero transaction deadlocks. |

---

## 5. Comprehensive Requirements Traceability Matrix (RTM)

This matrix maps every Functional Requirement (FR-01 to FR-42) and Non-Functional Requirement (NFR-01 to NFR-14) from SRS v2.2 to its verifying Test Cases:

| Requirement ID | Requirement Scope | Target Component | Verifying Test Case(s) | Quality Gate |
| :--- | :--- | :--- | :--- | :---: |
| **FR-01, FR-02** | 300 DPI Rasterization & CLAHE | `layout-service` | `TC-L1-03`, `TC-L2-05` | Gate 1 & 2 |
| **FR-03** | Probabilistic Hough Deskewing | `layout-service` | `TC-L1-04` | Gate 2 |
| **FR-04, 05** | 10x3 Invariant & IoU NMS Suppression | `layout-service` | `TC-L1-01`, `TC-L1-02` | Gate 2 |
| **FR-06** | Vertical Indic Subscript Padding | `layout-service` | `TC-L1-03` | Gate 2 |
| **FR-07, 08** | Section Breaks & Fixed Grid Calibration | `layout-service` | `TC-L1-02` | Gate 2 |
| **FR-09, 10** | Dual-Zone Header/Body Ingestion | `ocr-worker-fleet` | `TC-L2-06` | Gate 1 |
| **FR-11** | Word & Card Confidence Profiling | `ocr-worker-fleet` | `TC-L1-19`, `TC-L4-03` | Gate 3 |
| **FR-12, 15** | Non-Greedy Age Parsing (Ages 18 & 19) | `ocr-worker-fleet` | `TC-L1-06`, `TC-L1-07`, `TC-L1-08` | Gate 1 |
| **FR-13, 14** | EPIC Kerning Repair & Normalization | `ocr-worker-fleet` | `TC-L1-10`, `TC-L1-11`, `TC-L1-12`, `TC-L1-13` | Gate 1 |
| **FR-16** | Gender Inference from Relation | `ocr-worker-fleet` | `TC-L1-18` | Gate 1 |
| **FR-17** | Door Number Sanitization & Key | `ocr-worker-fleet` | `TC-L1-14`, `TC-L1-15`, `TC-L1-16`, `TC-L1-17` | Gate 2 |
| **FR-18** | 18 Empirical Optical Error Families | `consensus-service` | `TC-L3-01`, `TC-L3-05`, `TC-L3-08..14`, `TC-L3-19..24` | Gate 4 |
| **FR-19** | 23 Space-Split Surnames Rejoining | `consensus-service` | `TC-L3-25` | Gate 4 |
| **FR-20** | Leading Double Consonant Stripping | `consensus-service` | `TC-L3-26` | Gate 4 |
| **FR-21** | Whitelisted Ajanta Suffix Restorations| `consensus-service` | `TC-L3-10`, `TC-L3-11` | Gate 4 |
| **FR-22** | Immutable Safety Barrier (0.00% FP) | `consensus-service` | `TC-L3-03`, `TC-L3-04`, `TC-L3-07`, `TC-L3-15..18`, `TC-L3-29..35` | Gate 4 |
| **FR-23..25** | Household Consensus & Bayesian Prior | `consensus-service` | `TC-L2-02`, `TC-L2-03`, `TC-L2-04` | Gate 2 & 4 |
| **FR-26, 27** | Surgical Re-OCR 5-Tier Ladder | `surgical-reocr` | `TC-L2-05` | Gate 1 |
| **FR-28, 29** | Permanent Provenance Retention | `export-service` | `TC-L4-01`, `TC-L4-02`, `TC-L4-03` | Gate 3 |
| **FR-30** | Time-Machine Visual Replay API | `gateway-service` | `TC-L4-06` | Gate 5 |
| **FR-31** | Red-Tier Quarantine & DLQ Routing | `ocr-worker-fleet` | `TC-L1-20`, `TC-L5-03` | Gate 3 & 5 |
| **FR-32..34** | Prometheus Telemetry & Live SSE | `gateway-service` | `TC-L4-06` | Gate 5 |
| **FR-35** | Shadow Mode Parallel Evaluation | `consensus-service` | `TC-L4-05` | Gate 5 |
| **FR-36..38** | N-Gram, Plural Cutoff & Ungluing | `consensus-service` | `TC-L3-21`, `TC-L3-23`, `TC-L3-27` | Gate 4 |
| **FR-39, 40** | Demographic Classification (T, M, C, S)| `consensus-service` | `TC-L3-30`, `TC-L3-31`, `TC-L3-32` | Gate 4 |
| **FR-41** | Bilingual Cross-Script Verification | `ocr-worker-fleet` | `TC-L2-01`, `TC-L2-02` | Gate 1 & 4 |
| **FR-42** | Form 7 Strikethrough & Stamp Occlusion| `layout-service` | `TC-L1-05`, `TC-L1-15`, `TC-L2-07` | Gate 2 |
| **NFR-01** | Zero False Positives on Protected Tokens| Platform-wide | `TC-L3-29..35` | Gate 4 |
| **NFR-02** | Zero Dropped Records ($\Delta = 0$) | Platform-wide | `TC-L4-01`, `TC-L5-01` | Gate 3 |
| **NFR-03** | 100% Provenance Retention | `export-service` | `TC-L4-01`, `TC-L4-02` | Gate 3 |
| **NFR-04** | Distributed Throughput $\ge 150\text{ cards/s}$| Worker Fleet | `TC-L5-04` | Gate 5 |
| **NFR-07** | High Availability & Worker Failover | AMQP Broker | `TC-L5-01` | Gate 5 |
| **NFR-11** | Sub-50ms Visual Serving Latency | `gateway-service` | `TC-L4-06` | Gate 5 |
| **SPEC-ING-01..08**| Airgap Local & Crawler Ingestion | `crawler-service` | `TC-L5-02`, `TC-L5-03` | Gate 5 |

---

## 6. Document Revision History

| Version | Date | Author / Role | Changes / Descriptions |
| :--- | :--- | :--- | :--- |
| **v1.0** | 2026-10-28 | QA & Verification Team | Initial Draft: 15 basic unit and regression test cases. |
| **v2.0** | 2026-10-29 | Lead Test Architect | Enterprise Test Strategy: 5-level testing hierarchy, 4 proven visual regression cases, automated CI/CD quality gate thresholds. |
| **v2.1** | 2026-10-29 | Principal Test Architect | Full Empirical Expansion: Aligned with SRS v2.2 and HLD v2.1. Added full test coverage for all 18 empirical error families (19,500+ `Gh-` $\rightarrow$ `Ch-`, 12,000+ terminal `l` smudges, 10,000+ authentic `rn` surname protection, 833 `Q` $\rightarrow$ `D` smudges, 3,363 `-rad` $\rightarrow$ `-rao` records, 3,641 `-ull` $\rightarrow$ `-ulu` plurals, 2,128 `Narmne` bleeds), non-greedy age regex tests for young electors (18 & 19), Form 7 strikethrough recovery, and full 42-requirement RTM. |
