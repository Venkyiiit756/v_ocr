# Exhaustive Architectural Audit & Definitive System Design (V2.0)
## Enterprise-Grade Electoral Intelligence & Ground-Truth Ingestion Platform

**Author:** Antigravity (Advanced Agentic Coding Suite)  
**Document Standard:** Definitive Production Specification & Complete Lessons-Learned Synthesis  
**Scope:** 721,735 Electors across Godavari Delta (AC 37 Pithapuram, AC 38 Kakinada Rural, AC 39 Peddapuram) $\rightarrow$ Extensible to 40M+ Electors Statewide  
**Guiding Mandate:** Compute & Time are Unconstrained; Absolute Ground-Truth Quality, Mathematical Auditability & Zero Demographic Bias are Mandatory.

---

## 1. Executive Forensic Synthesis: All Lessons Learned

Before locking any production design, we performed a root-to-leaf forensic audit of the entire codebase, scripts, caches, and test runs. Below is the complete catalog of verified engineering realities:

### 1.1 Ingestion & Spatial Geometry
1. **Administrative Section Breaks Break Arithmetic Page Formulas:**
   - *Failure Mode in V1:* Assuming `page = (sno - 1) // 30 + 2` resulted in a 1 to 3 page drift. ECI rolls terminate polling sections mid-page, leaving lower slots blank, and start the next section on a fresh page.
   - *Design Invariant:* Page indices and slot indices must be read directly from document ingestion and locked into record metadata. Never infer page numbers via division.
2. **Hardcoded Pixel Deduplication Thresholds Leak Concentric Contours:**
   - *Failure Mode in V1:* `detector.py` checked `abs(x1 - x2) < 20`. On 300 DPI scans, the distance between the printed card border and outer table line was exactly 20–22 pixels. The condition failed, yielding 31 boxes on a 30-box page and shifting subsequent card indices by +1.
   - *Design Invariant:* Replace static pixel checks with **Intersection-over-Union (IoU) Non-Maximum Suppression (NMS)** ($IoU > 0.40$ or Center Distance $< 80$ px).
3. **Domain Form Invariant Must Enforce Grid Geometry:**
   - *Failure Mode in V1:* The detector allowed 31 boxes to pass into the OCR engine.
   - *Design Invariant:* An ECI voter page is strictly a $10 \text{ rows} \times 3 \text{ columns} \le 30 \text{ cards}$ grid. If OpenCV detects $> 30$ boxes, an assertion or geometric pruning must force it to the top 30 most regular grid cells.
4. **Card Bounding Boxes Truncate Indic Subscript Conjuncts (Vattulu):**
   - *Failure Mode in V1:* Cutting tightly along the black card border chopped off bottom retroflex Telugu subscripts (`వత్తులు` like `-dla` in `Pediredla`) and top vowel matras (`తలకట్టు`, `దీర్ఘం`), turning `-dla` into `-dia`.
   - *Design Invariant:* Card crops must dynamically extend by $+15\%$ vertically (headroom and footroom) into inter-row margins.

### 1.2 Raster Image Processing
1. **1-Bit Binary Thresholding Destroys Neural OCR Performance:**
   - *Failure Mode in V1:* Otsu thresholding bridged independent letter stems (turning `NAKKAA` into `NWARKAA`), while adaptive Gaussian thresholding introduced salt-and-pepper noise around faint text (turning `ChellaR Madish` into `lames Chellsh iveclieh`).
   - *Design Invariant:* Modern LSTM/transformer OCR engines require **8-bit continuous anti-aliased grayscale**. Enhance faint ribbon ink using **Contrast Limited Adaptive Histogram Equalization (CLAHE)** (`clipLimit=2.0`, `tileGridSize=(8, 8)`).
2. **Scanner Bed Skew Impairs Horizontal Line Segmentation:**
   - *Failure Mode in V1:* Tilted scans ($0.5^\circ - 2.5^\circ$) caused horizontal line projections to slice through neighboring characters.
   - *Design Invariant:* Detect card horizontal partition lines via Hough transforms and deskew each card before OCR.
3. **Zonal Scaling Separation:**
   - *Failure Mode in V1:* OCRing the entire card as one composite image caused Tesseract to miss small-print EPICs or merge SNO headers with voter names.
   - *Design Invariant:* Segment card into **Zone A (Header: SNO & EPIC)** upscaled at $2.0\times$ (PSM 7/8), and **Zone B (Body: Demographic fields)** at native 300 DPI CLAHE (PSM 6).

### 1.3 Entity Extraction & Linguistic Rules
1. **Exhaustive Optical Label Stripping:**
   - *Failure Mode in V1:* In low-res scans, `Father's Name:` was parsed as `Fathar`, `Fether`, `Hushand`, `Otliers`, `Warne`, `Nane`, leaking into the person's name.
   - *Design Invariant:* Maintain an exhaustive, normalized dictionary of OCR label permutations.
2. **Door Number & Age Leakage:**
   - *Failure Mode in V1:* Trailing text like `Photo Available` leaked into door numbers; `Age: 27` or `Age: 37` was misread as `Age: 97` due to optical blur on the first digit.
   - *Design Invariant:* Sanitize door numbers against optical noise tokens; validate ages strictly against $18 \le \text{Age} \le 110$, re-OCRing any age $\ge 90$ with high-resolution zonal focus.
3. **Immutable Safety Barrier (Zero False Positives):**
   - *Failure Mode in V1:* Blind heuristic suffix expansion threatened to mutate valid minority, Sanskrit, and rare Telugu names (e.g., turning `Boppana` into `Boppanna`, classifying `Pasham` into Group M, or mutating `Kiran`, `David`, `Shaik`).
   - *Design Invariant:* Enforce an **Immutable Vocalic & Halanta Blocklist** that blocks any automated rule from modifying protected cultural roots.

### 1.4 Spatial Consensus & Provenance Lineage
1. **Household Proximity is the Ultimate Ground Truth:**
   - *Validation:* In Case 3 (`Macish` / `Mebish`), co-resident Sno 605 was explicitly entered as `Challarao Medisetti`. In Case 2 (`Peditedia`), co-residents were `Pediredla`. In Case 4 (`Ketiniei`), co-residents were `Ketinidi`.
   - *Design Invariant:* Build a **Bipartite Household Graph** (`Constituency + Part + Normalized Door No`). The graph performs consensus voting to resolve optical and clerical contractions automatically.
2. **The Fatal Flaw of V1: The Metadata Strip at the Export Gate:**
   - *Failure Mode in V1:* `run_full_pithapuram_pipeline.py` captured `page_no` and `box_index` internally, but its `export_cols` deliberately excluded them, discarding lineage, raw text, and confidence scores.
   - *Design Invariant:* The primary schema must **never drop lineage**. Every single row must carry `elector_id`, `source_pdf`, `page_no`, `box_index`, `bbox_pts`, `raw_ocr_dump`, and `word_confidences`.

---

## 2. Definitive Microservices Architecture Specification

```
+--------------------------------------------------------------------------------------------------+
|                          DISTRIBUTED ELECTORAL PLATFORM TOPOLOGY                                 |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   [PDF Roll Archive]                                                                             |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 1: Ingestion & Layout Service] (PyMuPDF + OpenCV)                                     |
|     - Renders 300 DPI native anti-aliased grayscale                                              |
|     - Applies CLAHE contrast enhancement & Hough deskewing                                       |
|     - Applies IoU Non-Maximum Suppression (IoU > 0.40) & 10x3 grid enforcement                  |
|     - Extends +15% vertical padding for Indic subscripts (vattulu)                               |
|     - Writes high-res PNG crops to MinIO/S3: `s3://crops/{ac}/{part}/{box}.png`                  |
|     - Publishes task message to Queue: `card.crops.pending`                                      |
|          |                                                                                       |
|          v                                                                                       |
|   [Message Broker: RabbitMQ / Redis Streams]                                                     |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 2: OCR Worker Fleet] (Horizontally Scalable via KEDA)                                 |
|     - Dual-Zone OCR: Zone A (2.0x Upscaled Header for SNO/EPIC), Zone B (Body text)              |
|     - Dual-Engine Parallel Inference: Tesseract 5 LSTM + PaddleOCR/TrOCR                         |
|     - Extracts word-level and character-level confidence vectors via `image_to_data`             |
|     - Publishes extracted raw entity to Queue: `electors.parsed`                                 |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 3: Household Graph Consensus & Linguistic Arbiter]                                    |
|     - Constructs Bipartite Household Graph: `ClusterKey = (AC, Part, NormalizedDoor)`            |
|     - Evaluates Bayesian Transition Probabilities: P(Surname | Household) >= 0.80                |
|     - Enforces Immutable Vocalic & Halanta Safety Barrier                                        |
|     - Writes Gold-Standard Record to PostgreSQL & Master Parquet Data Lake                       |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 4: Verification API Gateway & Real-Time HITL Dashboard]                               |
|     - FastAPI / gRPC High-Throughput REST Gateway                                                |
|     - Serves `/api/v1/electors/{id}/crop` in <20ms (Fetches crop + draws bbox overlay)           |
|     - Interactive 1-click review UI for the <1% low-confidence tail                              |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Storage Tiering & Database Schema

```
+---------------------------------+  +-------------------------------+  +-----------------------------+
| TIER 1: BLOB OBJECT STORE       |  | TIER 2: RELATIONAL DATABASE   |  | TIER 3: COLUMNAR DATA LAKE  |
| (MinIO / AWS S3 / GCS)          |  | (PostgreSQL 16)               |  | (Apache Parquet / DuckDB)   |
+---------------------------------+  +-------------------------------+  +-----------------------------+
| Stores raw 300 DPI card crops:  |  | Stores primary records, JSON  |  | Partitioned by AC and Part. |
| `s3://crops/ac37/p096/c08.png`  |  | provenance, audit trails, and |  | Optimized for sub-second    |
| Serves verification UI instantly|  | foreign-key household graphs. |  | demographic aggregation.    |
+---------------------------------+  +-------------------------------+  +-----------------------------+
```

### PostgreSQL Master Elector Table Schema
```sql
CREATE TABLE master_electors (
    elector_id VARCHAR(32) PRIMARY KEY,       -- e.g. 'AP_AC37_P096_S0356'
    constituency_no SMALLINT NOT NULL,        -- 37
    constituency_name VARCHAR(64) NOT NULL,   -- 'Pithapuram'
    assembly_part INTEGER NOT NULL,           -- 96
    booth_sno INTEGER NOT NULL,               -- 356
    epic_no VARCHAR(16) NOT NULL,             -- 'YOU1903475'
    
    -- Cleaned & Validated Fields
    voter_name_clean VARCHAR(128) NOT NULL,   -- 'Chellarao Ketinidi'
    rel_type VARCHAR(16) NOT NULL,            -- 'Father'
    rel_name_clean VARCHAR(128) NOT NULL,     -- 'Appanna'
    door_no_clean VARCHAR(64) NOT NULL,       -- '2-1'
    age SMALLINT NOT NULL,                    -- 94
    gender VARCHAR(16) NOT NULL,              -- 'Male'
    linguistic_group CHAR(1) NOT NULL,        -- 'T' (T, C, M, S)
    
    -- Raw OCR Captures & Optical Confidences
    voter_name_raw TEXT NOT NULL,             -- 'Name : ChellaR Ketinidi'
    voter_name_conf REAL NOT NULL,            -- 0.94
    rel_name_raw TEXT NOT NULL,               -- 'Fathers Name: Appanna'
    rel_name_conf REAL NOT NULL,              -- 0.96
    door_no_raw TEXT NOT NULL,                -- 'House Number = 2-1'
    mean_card_conf REAL NOT NULL,             -- 0.93
    
    -- Provenance & Document Lineage
    source_pdf VARCHAR(128) NOT NULL,         -- 'roll_part_96.pdf'
    page_no SMALLINT NOT NULL,                -- 15
    box_index SMALLINT NOT NULL,              -- 8
    bbox_pts JSONB NOT NULL,                  -- [121, 2305, 1621, 658]
    crop_uri VARCHAR(256) NOT NULL,           -- 's3://crops/ac37/p096/c08.png'
    
    -- Audit Trail & Household Graph Keys
    household_id VARCHAR(64) NOT NULL,        -- 'AC37_P096_D2-1'
    audit_trail JSONB NOT NULL,               -- [{"rule": "...", "before": "...", "timestamp": "..."}]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_elector_household ON master_electors(household_id);
CREATE INDEX idx_elector_epic ON master_electors(epic_no);
CREATE INDEX idx_elector_conf ON master_electors(mean_card_conf);
CREATE INDEX idx_elector_names ON master_electors USING gin (to_tsvector('simple', voter_name_clean || ' ' || rel_name_clean));
```

---

## 4. Kubernetes (K8s) Cluster Deployment & KEDA Autoscaling

### 4.1 Workload Separation Across Pods
- **`layout-service-pod`**: CPU-bound, handles high-resolution rendering, CLAHE, Hough deskewing, and NMS grid extraction.
- **`ocr-worker-pod`**: Compute-heavy, processes Zone A & Zone B OCR, extracts confidence vectors, and parses fields.
- **`consensus-arbiter-pod`**: Memory-bound, constructs household graphs and applies Bayesian priors.
- **`api-gateway-pod`**: I/O-bound, serves REST queries and verification image crops.

### 4.2 KEDA Dynamic Autoscaling Rule
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ocr-worker-autoscaler
  namespace: electoral-engine
spec:
  scaleTargetRef:
    name: ocr-worker-deployment
  minReplicaCount: 4
  maxReplicaCount: 128
  cooldownPeriod: 30
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: card.crops.pending
      mode: QueueLength
      value: "50" # Automatically spawns 1 pod for every 50 pending card crops
```

---

## 5. Phased Implementation & Rollout Roadmap

| Phase | Objective | Deliverables | Validation Criteria |
| :--- | :--- | :--- | :--- |
| **Phase 1: Core Engine Refactoring** | Upgrade `detector.py`, `engine.py`, and `parser.py` | IoU NMS boundary detector, CLAHE grayscale, +15% Indic padding, complete provenance schema | Test on Parts 6, 96, 109, 241; assert 100% boundary accuracy and zero dropped metadata. |
| **Phase 2: Local Microservices Stack** | Build Docker containers & Docker Compose orchestration | `Dockerfile.worker`, `Dockerfile.api`, `docker-compose.yml` (RabbitMQ, MinIO, Postgres, Workers) | Run locally on multi-core rig; process 10 parts end-to-end with live RabbitMQ queueing. |
| **Phase 3: Benchmark Run (AC 37 Pithapuram)** | Process all 242 parts of Pithapuram on the new stack | Complete 236k elector database with 100% provenance and confidence scores | Audit mean confidence distribution; confirm natural resolution of `Nakikaa`, `Macish`, `Peditedia`. |
| **Phase 4: Full Multi-Constituency Scale** | Process Peddapuram (AC 39) & Kakinada Rural (AC 38) | Consolidated 721k gold-standard Parquet data lake and PostgreSQL master database | Zero true nulls, 100% auditable provenance, instant CLI visual inspection across all records. |
| **Phase 5: K8s Production Deployment (Optional)** | Deploy Helm charts to Kubernetes cluster | Multi-node K8s cluster with KEDA autoscaling | Capable of processing 10M to 40M electors statewide. |
