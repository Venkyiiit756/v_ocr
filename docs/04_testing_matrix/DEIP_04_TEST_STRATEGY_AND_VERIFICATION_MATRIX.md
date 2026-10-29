# Test Strategy, Multi-Level Verification & Validation (V&V) Matrix
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.0)

**Document Reference:** DEIP-TEST-V2.0  
**Compliance Standard:** ISO/IEC/IEEE 29119-3:2013 (Software Testing Standard)  
**Testing Philosophy:** Zero Tolerance for Hallucinations & Zero False Positives on Protected Names  
**Scope:** Unit, Optical Regression, Graph Integration, End-to-End, and Chaos Resiliency Testing  

---

## 1. Multi-Level Testing Hierarchy

```
+--------------------------------------------------------------------------------------------------+
|                                    5-LEVEL TESTING HIERARCHY                                     |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  LEVEL 1: UNIT & ALGORITHM TESTS (L1)                                                            |
|  - IoU math, NMS box suppression, CLAHE filtering, deskew math, regex label strippers.          |
|                                                                                                  |
|  LEVEL 2: COMPUTER VISION & OPTICAL GROUND-TRUTH REGRESSION (L2)                                 |
|  - Benchmark runs on physical gold-standard voter card crops (Case 1, 2, 3, 4, Age 97, etc.).    |
|                                                                                                  |
|  LEVEL 3: HOUSEHOLD GRAPH CONSENSUS & SPATIAL INTEGRATION (L3)                                   |
|  - Multi-elector household consensus, single-occupant street adjacency, edge-weight voting.       |
|                                                                                                  |
|  LEVEL 4: END-TO-END CONSTITUENCY SMOKE & PROVENANCE AUDIT (L4)                                 |
|  - Full pipeline runs on synthetic & real assembly parts; asserts 100% lineage capture.          |
|                                                                                                  |
|  LEVEL 5: CHAOS, RESILIENCY & FAULT-TOLERANCE (L5)                                               |
|  - Worker pod kill simulations, corrupted PDF recovery, Playwright crawler CAPTCHA timeouts.     |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Comprehensive Test Case Matrix (Selected Core Tests)

### 2.1 Level 1: Unit & Mathematical Algorithms
| Test ID | Subsystem | Test Objective | Test Input | Expected Result | Pass/Fail Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-L1-01** | `detector.py` | IoU Box Suppression | Two bounding boxes with $IoU = 0.45$ (concentric contours) | Secondary box is suppressed; exactly 1 box retained. | Suppressed count == 1 |
| **TC-L1-02** | `detector.py` | Grid Boundary Invariant | Input produces 31 candidate contours | Detector applies NMS and geometric grid pruning; returns **exactly 30 boxes**. | `len(boxes) == 30` |
| **TC-L1-03** | `detector.py` | Indic Subscript Padding | Card height $h = 650$ px | Vertical padding of $+15\%$ ($97$ px top and bottom) applied; $h_{\text{padded}} = 844$ px. | Bounds expand by $+15\%$ |
| **TC-L1-04** | `parser.py` | EPIC Lookalike Suffix | Candidate `YOU0Q895120` (8 chars, `Q` confusion) | Collapses `0Q` $\rightarrow$ `0`; outputs valid `YOU0895120`. | Strict regex `^[A-Z]{3}[0-9]{7}$` passes |
| **TC-L1-05** | `parser.py` | Age Noise Stripping | Raw string `Age : 41?` or `Age : 21/` | Strips trailing optical noise; outputs integer `41` or `21`. | `age in (41, 21)` |
| **TC-L1-06** | `parser.py` | Gender Inference | Relationship is `Husband`, Gender is `-` (unread) | System automatically infers `Female`. | `gender == 'Female'` |

---

### 2.2 Level 2: Optical Ground-Truth Regression Suite
| Test ID | Reference Record | Input Image Crop | Target Optical Issue | Expected Output | Regression Safeguard |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-L2-01** | AC 37 Part 6 Sno 595 | [`Proof_Case1_Part6_Sno595_Nakikaa.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case1_Part6_Sno595_Nakikaa.png) | Split diagonal stem on `K` (`Nakikaa`) | Resolves to **`Nakka`** (అప్పారావు నక్క). Rejects `Nakkina` and `Nakinaa`. | Must NOT contain letter `i` or `n` |
| **TC-L2-02** | AC 37 Part 241 Sno 265 | [`Proof_Case2_Part241_Sno265_Peditedia.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case2_Part241_Sno265_Peditedia.png) | Crossbar confusion (`Peditedia` vs `Pediredia`) | Resolves to **`Pediredla`** (చెల్లారావు పెదిరెడ్ల). | Must contain `r` (`Pedired-`), not `t` |
| **TC-L2-03** | AC 37 Part 109 Sno 603 | [`Proof_Case3_Part109_Sno603_Macish.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case3_Part109_Sno603_Macish.png) | Faint ascender (`Madish` read as `Macish`) | Resolves to **`Medisetti`** (మేడిశెట్టి) via household anchor Sno 605. | Must resolve to canonical `Medisetti` |
| **TC-L2-04** | AC 37 Part 96 Sno 356 | [`Proof_Case4_Part96_Sno356_Ketiniei.png`](file:///C:/Users/vamsi/.gemini/antigravity/brain/50edf67f-7e1b-4e2f-9f0b-acef3f2ab7ee/proof_images/Proof_Case4_Part96_Sno356_Ketiniei.png) | Faint loop on `d` (`Ketiniei` vs `Ketinidi`) | Resolves to **`Ketinidi`** (కేతినిడి). | Must end in `idi`, not `iei` |
| **TC-L2-05** | Age 97 Corruption Test | Sample card with blurred `27` | Faint first digit misread as `97` | High-res CLAHE zonal crop re-reads true age `27`. | Age is NOT `97` |

---

### 2.3 Level 3: Immutable Safety Barrier & Zero False Positive Tests
| Test ID | Target Token | Input String | Threat Model | Expected Result | Immunity Guarantee |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-L3-01** | `Boppana` | `Boppana Apparao` | Suffix expansion to `Boppanna` | **Preserved exactly as `Boppana`**. Zero modification. | Vocalic Immunity Asserted |
| **TC-L3-02** | `Pasham` | `Pasham Srinivas` | False classification into Muslim Group M | Classified into **Group T (Telugu)**. Zero false minority tag. | Group == 'T' |
| **TC-L3-03** | `Kiran` | `Kiran Kumar` | Halanta masculine suffix forced into `Kirani` | **Preserved exactly as `Kiran`**. | Halanta Blocklist Asserted |
| **TC-L3-04** | `David` | `David Raju` | Anglo-Christian name altered | **Preserved as `David`**, classified as Group C. | Group == 'C', Token Intact |
| **TC-L3-05** | `Shaik` | `Shaik Subhan` | Corrupted into Telugu suffix | **Preserved as `Shaik`**, classified as Group M. | Group == 'M', Token Intact |

---

### 2.4 Level 4: Lineage & Provenance Completeness
| Test ID | Test Scope | Verification Procedure | Pass/Fail Criteria |
| :--- | :--- | :--- | :--- |
| **TC-L4-01** | All 721k Electors | Query `SELECT count(*) FROM master_electors WHERE source_pdf IS NULL OR page_no IS NULL OR box_index IS NULL OR bbox_pts IS NULL;` | **Result must be exactly 0**. |
| **TC-L4-02** | Optical Confidences | Query `SELECT count(*) FROM master_electors WHERE mean_card_conf IS NULL OR mean_card_conf < 0.0 OR mean_card_conf > 1.0;` | **Result must be exactly 0**. |
| **TC-L4-03** | Instant Visual Serving | Benchmark `GET /api/v1/electors/{id}/crop` across 500 concurrent requests | **p99 latency $< 40\text{ms}$**, HTTP 200 on all valid IDs. |

---

### 2.5 Level 5: Chaos, Concurrency & Resiliency Tests
| Test ID | Chaos Stimulus | Expected System Behavior | Recovery Invariant |
| :--- | :--- | :--- | :--- |
| **TC-L5-01** | Kill OCR Worker pod mid-card | RabbitMQ fails to receive ACK; task is re-queued and processed by another pod. | Zero dropped cards; zero duplicate rows in PostgreSQL. |
| **TC-L5-02** | Malformed / 0-byte PDF file | Ingestion service catches bad header, marks Part as `CORRUPTED_DISPATCH_CRAWLER`, and triggers Playwright crawler. | Main pipeline continues uninterrupted. |
| **TC-L5-03** | CAPTCHA Solver 3x Timeout | Crawler applies exponential backoff, switches audio user-agent, and retries. | DLQ alerts telemetry dashboard without crashing worker. |

---

## 3. Automated CI/CD Quality Gate Thresholds

In our automated CI/CD pipeline (GitHub Actions / GitLab CI), every deployment must clear the following **Automated Quality Gates**:

```
+-------------------------------------------------------------+
|               AUTOMATED CI/CD QUALITY GATES                 |
+-------------------------------------------------------------+
| 1. Unit & Regression Tests:        100% Pass (0 failures)   |
| 2. False Positive Safety Barrier:  0.00% False Positives    |
| 3. Lineage Completeness:           100.00% Provenance Captured|
| 4. Mean Constituency Confidence:   >= 0.88 Mean Card Conf    |
| 5. High-Risk Quarantined Tail:     <= 1.00% of Electors     |
+-------------------------------------------------------------+
```
