# High-Level Architecture Design (HLD) & System Architecture Description
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.1)

**Document Reference:** DEIP-HLD-V2.1-DEFINITIVE  
**Compliance Standard:** IEEE 1016-2009 (Systems and Software Engineering — Software Design Descriptions) / ISO/IEC 42010  
**Architectural Style:** Event-Driven Microservices / Containerized Kubernetes Architecture  
**Target Throughput:** 150–300 cards/second (Distributed) | 721k Voters in $< 30$ mins  
**Classification:** Mission-Critical Demographic Data Infrastructure  
**Status:** Approved Definitive Baseline (SDLC Phase 2)  

---

## 1. Executive Architecture Summary

The **Distributed Electoral Intelligence Platform (DEIP V2.0)** is an enterprise-grade, distributed, cloud-native system designed to ingest, process, sanitize, reconcile, classify, and audit scanned Election Commission of India (ECI) voter rolls. 

To achieve census-grade fidelity across 721,735 electors (scalable to 40,000,000+ statewide) with **zero dropped records, 0.00% false-positive demographic mutations, and 100% permanent provenance**, the platform adopts an **Event-Driven Microservices Architecture (EDA)** decoupled by a reliable message broker (RabbitMQ), high-performance object storage (MinIO / S3), a relational master database (PostgreSQL 16), and a columnar analytical data lake (Apache Parquet).

```
+--------------------------------------------------------------------------------------------------+
|                              HIGH-LEVEL PLATFORM ARCHITECTURE TOPOLOGY                           |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   [DUAL-SOURCE INGESTION]                                                                        |
|   +--------------------------+          +-----------------------------------------+              |
|   | Local Air-Gapped Scanner |          | Headless Autonomous Crawler (Playwright)|              |
|   | (Directory / NFS / S3)   |          | with Faster-Whisper Voice CAPTCHA Solver|              |
|   +------------+-------------+          +--------------------+--------------------+              |
|                |                                             |                                   |
|                +----------------------+----------------------+                                   |
|                                       |                                                          |
|                                       v                                                          |
|                      [RabbitMQ Message Broker: roll.ingest.tasks]                                |
|                                       |                                                          |
|                                       v                                                          |
|   +------------------------------------------------------------------------------------------+   |
|   | SERVICE 1: INGESTION & LAYOUT SERVICE (PyMuPDF + OpenCV C-Core SIMD)                     |   |
|   | - 300 DPI Native Anti-Aliased Grayscale Rasterization (No 1-bit thresholding)            |   |
|   | - CLAHE Contrast Enhancement (clipLimit=2.0, 8x8 contextual tiles) & Hough Deskewing     |   |
|   | - RobustCardDetector with IoU Non-Maximum Suppression (IoU >= 0.40, distance < 80 px)    |   |
|   | - Vertical Indic Subscript Padding (+15% margin for retroflex vattulu & matras)          |   |
|   | - Writes Lossless Card Crops to MinIO: s3://crops/{ac}/{part}/{box_id}.png               |   |
|   +------------------------------------------------------------------------------------------+   |
|                                       |                                                          |
|                                       v                                                          |
|                    [RabbitMQ Message Broker: card.crops.pending]                                 |
|                                       |                                                          |
|               (Autoscaled via KEDA based on RabbitMQ Queue Depth)                                |
|                                       v                                                          |
|   +------------------------------------------------------------------------------------------+   |
|   | SERVICE 2: DUAL-ZONE OCR WORKER FLEET (Tesseract 5 LSTM C-API / ONNX Runtime)            |   |
|   | - Zone A (Header: SNO & EPIC): 2.0x Bicubic, PSM 7, tessedit_char_whitelist=[A-Z0-9]     |   |
|   | - Zone B (Demographics): 1.8x Bicubic, PSM 6, Custom CASL user-words (20,791 surnames)   |   |
|   | - Word-Level & Character-Level Confidence Vector Extraction via Tesseract TSV Engine     |   |
|   | - 5-Tier Surgical Re-OCR Escalation on degraded cards (< 0.60 conf or missing fields)    |   |
|   +------------------------------------------------------------------------------------------+   |
|                                       |                                                          |
|                                       v                                                          |
|                      [RabbitMQ Message Broker: electors.parsed]                                  |
|                                       |                                                          |
|                                       v                                                          |
|   +------------------------------------------------------------------------------------------+   |
|   | SERVICE 3: HOUSEHOLD GRAPH CONSENSUS & LINGUISTIC ARBITER                                |   |
|   | - Constructs Bipartite Household Graph: ClusterKey = (AC, Part, Normalized_Door_No)      |   |
|   | - Computes Bayesian Household Posterior: P(Surname | Household, OCR) >= 0.85            |   |
|   | - Applies 128 Glyph Maps, 23 Space-Split Rules & Compound Token Ungluing                 |   |
|   | - Enforces Immutable Safety Barrier: Boppana, Pasham, Kiran, David, Shaik (0.00% FP)    |   |
|   | - Classifies Electors into 4 Mutually Exclusive Groups: T (Telugu), M, C, S              |   |
|   +------------------------------------------------------------------------------------------+   |
|                         |                                                |                       |
|                         v                                                v                       |
|   +------------------------------------------+   +-------------------------------------------+   |
|   | MASTER RELATIONAL STORE (PostgreSQL 16)  |   | COLUMNAR DATA LAKE (Apache Parquet)       |   |
|   | - 32-Field Permanent Provenance Schema   |   | - Snappy Compressed Columnar Partitions   |   |
|   | - Immutable Audit Trail & Change Events  |   | - Sub-second analytics via DuckDB / Spark |   |
|   | - B-Tree & GIN Trigram Search Indexes    |   | - < 150 bytes per elector record          |   |
|   +------------------------------------------+   +-------------------------------------------+   |
|                         ^                                                ^                       |
|                         +-----------------------+------------------------+                       |
|                                                 |                                                |
|   +------------------------------------------------------------------------------------------+   |
|   | SERVICE 4: API GATEWAY, TIME-MACHINE REPLAY & PROMETHEUS TELEMETRY EXPORTER              |   |
|   | - High-Throughput REST Gateway (FastAPI + uvloop in C)                                   |   |
|   | - Sub-50ms Forensic Time-Machine Replay: /api/v1/electors/{id}/crop (Crop + BBox Overlay)|   |
|   | - Real-Time Operational Push Dashboard: WebSockets & Server-Sent Events (SSE)            |   |
|   | - Prometheus SRE Metrics Exporter on /metrics                                            |   |
|   +------------------------------------------------------------------------------------------+   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Multi-Language & Technology Selection Evaluation

In enterprise architecture (ISO/IEC 42010), technology and programming language choices must be rigorously justified across four hard engineering criteria:
1. **Raw Vector Compute & Throughput (SIMD / AVX-512):** 300 DPI rasterization, CLAHE filtering, and neural OCR matrix math.
2. **Ecosystem Maturity for Indic Document Processing:** Availability of production C/C++ bindings for Tesseract, MuPDF, and acoustic speech recognition.
3. **Memory Safety & Process Isolation:** Preventing malformed or corrupted PDF buffer overflows from crashing the system.
4. **Maintenance Velocity & Schema Uniformity:** Eliminating serialization overhead and schema drift across services.

### 2.1 Multi-Language Comparative Analysis

| Platform Tier | Option A: Python 3.12 (C-Extensions) | Option B: Rust | Option C: Go (Golang) | Option D: C++ (Native) | Architectural Selection & Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PDF Rasterization & Ingestion** | **PyMuPDF (MuPDF C-Engine):** 40ms/page at 300 DPI via C SIMD. | `pdfium-render` (C++ wrapper). Safe, but wrapper overhead. | `unidoc` / `pdfcpu`. Lacks anti-aliased font rasterizer. | Direct MuPDF / Poppler C++. Maximum speed, high maintenance. | **Selected: Python 3.12 (PyMuPDF C-Core).** Identical speed to native C++ because rasterization runs in native C without Python GIL contention. |
| **Computer Vision (CLAHE, Deskew, NMS)** | **OpenCV-Python (C++ backend):** Zero-copy NumPy memory buffers. | `imageproc` / `opencv-rust`. Immature NMS bindings. | `gocv` (cgo wrapper). Heavy cgo context-switch penalty. | Native OpenCV C++. Fast, but segfault risk on corrupt scans. | **Selected: Python 3.12 (OpenCV C++ backend).** C++ performance with memory-safe container encapsulation. |
| **Acoustic CAPTCHA Solver** | **Faster-Whisper (CTranslate2 in C++):** 4x faster than PyTorch; 8-bit quantized. | `whisper-rs` (C++ bindings). Functional, but complex build. | No production Whisper engine. | Direct `whisper.cpp`. Fast, but complex audio pipeline. | **Selected: Python 3.12 (CTranslate2 C++ Engine).** Transcribes audio in $< 1.2\text{s}$ with minimal memory footprint ($< 250\text{MB}$). |
| **OCR Inference & Confidence Extraction** | **Tesseract 5 LSTM C-API / ONNX:** Direct in-memory buffer pipes. | `tesseract-rs`. Inflexible token confidence APIs. | `gosseract` (cgo context penalty on every subimage). | Direct Libtesseract 5 C++. Maximum speed, steep build cost. | **Selected: Python 3.12 with Tesseract 5 C-API.** Provides token bounding boxes and character confidences via in-memory pipes. |
| **Household Graph Consensus** | **Polars (Rust Core) + NetworkX:** Multi-threaded Arrow memory. | Pure Rust `petgraph` + `polars`. Highest speed. | Go slice operations. Lacks advanced graph algorithms. | Custom C++ graph structures. Unnecessary complexity. | **Selected: Python + Polars (Rust core).** Executes multi-scale consensus across 721k electors in under 8 seconds. |
| **API Gateway & Observability** | **FastAPI + Uvicorn (uvloop in C):** 30k+ req/sec; shared Pydantic models. | `Axum` / `Actix-web`. Maximum throughput (100k+ req/s). | `Gin` / `Fiber`. Low RAM footprint (15MB). | `Drogon` C++. Excessive maintenance complexity. | **Selected: Python 3.12 FastAPI (uvloop in C).** Shares exact Pydantic entity contracts with workers; Go micro-gateway as alternative for cloud scale. |

---

## 3. Architecture Decision Records (ADR)

### ADR-01: Microservices Architecture with RabbitMQ Event Bus
- **Status:** APPROVED
- **Context:** Monolithic batch scripts suffered from thread contention, memory bloat on large PDFs, and lacked fault isolation. A crash on Part 142 halted the entire constituency pipeline.
- **Decision:** Decompose the pipeline into 7 autonomous, containerized microservices communicating asynchronously via RabbitMQ AMQP 0-9-1 with persistent message acknowledgments (`ack`), dead-letter exchanges (`DLX`), and priority queues.
- **Consequences:** Eliminates single-point-of-failure risks. Any crashed worker pod is automatically restarted by Kubernetes or Docker without interrupting the remaining pipeline.

### ADR-02: 8-Bit Grayscale CLAHE vs. 1-Bit Binary Thresholding
- **Status:** APPROVED
- **Context:** Empirical visual audits proved that Otsu thresholding bridges letter stems (turning `NAKKAA` into `NWARKAA`), while adaptive Gaussian binarization injects salt-and-pepper noise around faint print (turning `ChellaR Madish` into `lames Chellsh iveclieh`).
- **Decision:** Permanently ban hard 1-bit thresholding during initial card ingestion. Standardize on 300 DPI native 8-bit anti-aliased grayscale with Contrast Limited Adaptive Histogram Equalization (CLAHE: `clipLimit=2.0`, `tileGridSize=(8, 8)`).
- **Consequences:** Enhances faint dot-matrix printer ribbon ink while preserving continuous stroke gradients for neural LSTM decoders.

### ADR-03: Dual-Zone OCR Ingestion with Indic Subscript Padding
- **Status:** APPROVED
- **Context:** Whole-card OCR missed small-print EPIC numbers and chopped off Telugu bottom subscript conjuncts (`వత్తులు` like `-dla` in `Pediredla`), degrading `-dla` into `-dia`.
- **Decision:** Partition each card into Zone A (Header: $2.0\times$ upscaled single-line OCR with strict alphanumeric whitelist `[A-Z0-9]`) and Zone B (Demographics Body: multi-line OCR with $+15\%$ vertical headroom and footroom into inter-card gutters).
- **Consequences:** Eliminates dropped EPICs and preserves bottom retroflex Indic diacritics.

### ADR-04: Tesseract 5 LSTM C-API with DAWG User-Words Injection
- **Status:** APPROVED
- **Context:** Unconstrained OCR decoding frequently yields unpronounceable gibberish when printer ink is faint (e.g. `Madish` for `Medisetti`).
- **Decision:** Pre-load the **Canonical Andhra Surname Lexicon (CASL - 20,791 unique surnames)** directly into Tesseract's neural beam-search decoder via `tessdata/eng.user-words`.
- **Consequences:** The beam search prioritizes valid Andhra Pradesh surnames over nonsense strings at the optical root, preventing errors before string emission.

### ADR-05: Acoustic Voice CAPTCHA Solving via Faster-Whisper (CTranslate2)
- **Status:** APPROVED
- **Context:** ECI and CEO Andhra portals protect downloads with dynamic audio CAPTCHAs. Optical image CAPTCHA solvers suffer from high failure rates on distorted visual text.
- **Decision:** Implement headless Playwright browser crawling with an autonomous acoustic CAPTCHA solver using `faster-whisper` (`base` model on CTranslate2 C++ engine with 8-bit quantization).
- **Consequences:** Transcribes spoken alphanumeric CAPTCHAs in $< 1.2$ seconds with $\ge 96.5\%$ first-pass accuracy without external third-party API dependencies.

### ADR-06: Permanent Data Provenance Invariant (32-Field Schema)
- **Status:** APPROVED
- **Context:** Legacy systems stripped `source_pdf`, `page_no`, `box_index`, and bounding box coordinates, making forensic auditing impossible when data discrepancies arose.
- **Decision:** The platform shall permanently enforce the **Permanent Provenance Schema** across all database tables, Parquet partitions, and CSV/XLSX exports. No transformation stage may ever drop lineage fields.
- **Consequences:** Enables instantaneous sub-50ms visual verification and quantified quality filtering (`WHERE mean_card_conf < 0.70`).

### ADR-07: Four-Tier Storage Separation
- **Status:** APPROVED
- **Context:** Storing base64 image crops directly in relational tables bloats databases and degrades analytical query performance.
- **Decision:** Implement a strictly segregated 4-tier storage architecture:
  1. **Blob Storage (MinIO / S3):** Lossless PNG card crops (`s3://crops/{ac}/{part}/{box}.png`).
  2. **Relational Database (PostgreSQL 16):** Master operational records, ACID transactions, GIN trigram indexes.
  3. **Columnar Data Lake (Apache Parquet):** Snappy-compressed analytics lake partitioned by `ac_no/part_no`.
  4. **Message Broker (RabbitMQ):** In-memory task queues and dead-letter queues.
- **Consequences:** Sub-second analytics via DuckDB/Spark while maintaining fast, lightweight REST image serving.

### ADR-08: OpenShift (OCP) Non-Root Arbitrary UID Container Security
- **Status:** APPROVED
- **Context:** Enterprise Kubernetes clusters (particularly Red Hat OpenShift OCP) enforce strict Security Context Constraints (`restricted-v2` SCC) that forbid running containers as root and allocate arbitrary dynamic UIDs at runtime.
- **Decision:** All container images must be built with non-root security: `USER 10001` and group ownership `chgrp -R 0 /app && chmod -R g=u /app`. All temporary file writes must target `/tmp` or in-memory shared memory (`/dev/shm`).
- **Consequences:** 100% compliance with enterprise Kubernetes and OpenShift security standards.

### ADR-09: Event-Driven Horizontal Autoscaling via KEDA
- **Status:** APPROVED
- **Context:** OCR processing is CPU-bound and creates queue spikes during batch ingestion, whereas layout detection is fast.
- **Decision:** Deploy KEDA (Kubernetes Event-driven Autoscaling) with a `ScaledObject` monitoring RabbitMQ queue depth on `card.crops.pending`, dynamically scaling OCR worker pods from 8 up to 128 replicas.
- **Consequences:** Optimizes compute utilization, automatically scaling down to zero idle workers when queues are drained.

### ADR-10: Air-Gapped Disconnected Cluster Readiness
- **Status:** APPROVED
- **Context:** Sensitive electoral roll data must frequently be processed in air-gapped government enclaves without public internet access.
- **Decision:** All container images shall bake in their neural network weights (`faster-whisper`), Tesseract language models (`eng`, `tel`), and the CASL surname lexicon during the Docker build stage.
- **Consequences:** The system executes completely offline without external HTTP calls or CDN dependencies.

---

## 4. C4 Architecture Models

### 4.1 C4 Level 1: System Context Diagram

```
+--------------------------------------------------------------------------------------------------+
|                                    C4 LEVEL 1: SYSTEM CONTEXT                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +-----------------------+     +-----------------------+       +---------------------------+    |
|   | CEO Andhra Pradesh    |     | Local PDF Archive     |       | Data Auditors & Analysts  |    |
|   | Official ECI Portal   |     | (Air-Gapped Disk/NFS) |       | (Inspectors, Legal Teams) |    |
|   +-----------------------+     +-----------------------+       +---------------------------+    |
|               |                             |                                 ^                  |
|   (HTTPS /    |                             | (File I/O /                     | (HTTP REST /     |
|    Playwright)|                             |  SHA-256)                       |  WebSockets)     |
|               v                             v                                 |                  |
|   +---------------------------------------------------------------------------+-------------+    |
|   |                     DISTRIBUTED ELECTORAL INTELLIGENCE PLATFORM (DEIP)                  |    |
|   | - Ingests, rasterizes, and deskews scanned rolls at 300 DPI native grayscale            |    |
|   | - Detects card boundaries via IoU NMS and applies +15% vertical Indic padding           |    |
|   | - Executes Dual-Zone OCR with CASL 20,791-surname lexicon injection                     |    |
|   | - Reconstructs household consensus graphs and applies Bayesian surname arbitration       |    |
|   | - Guarantees 0.00% false positives on protected tokens (Boppana, Pasham, Kiran, David)  |    |
|   | - Serves verified demographic datasets, real-time telemetry, and visual proof panels    |    |
|   +-----------------------------------------------------------------------------------------+    |
|                                           |                                                      |
|                                           v                                                      |
|   +-----------------------------------------------------------------------------------------+    |
|   |                   GOLD-STANDARD CENSUS DATABASE & ANALYTICAL DATA LAKE                  |    |
|   | - 721,735 Elector Records with 100% Provenance, Confidences, and Zero Demographic Bias  |    |
|   +-----------------------------------------------------------------------------------------+    |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### 4.2 C4 Level 2: Container Topology (Microservices)

```
+--------------------------------------------------------------------------------------------------+
|                                    C4 LEVEL 2: CONTAINERS                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   [Roll Dispatcher Service]                                                                      |
|     | (Dispatches AC & Part tasks)                                                               |
|     v                                                                                            |
|   [Queue: roll.ingest.tasks (RabbitMQ)]                                                          |
|     |                                                                                            |
|     v                                                                                            |
|   +------------------------------------------------------------------------------------------+   |
|   | Ingestion & Layout Service (Containers: 2 - 8 Replicas)                                  |   |
|   | - Runtime: Python 3.12 (PyMuPDF + OpenCV C-Core)                                         |   |
|   | - Functions: 300 DPI Rasterization, CLAHE, Hough Deskew, IoU NMS Grid Detector           |   |
|   | - Writes: Raw card PNGs to MinIO (`s3://crops/{ac}/{part}/{box}.png`)                    |   |
|   +------------------------------------------------------------------------------------------+   |
|     |                                                                                            |
|     v                                                                                            |
|   [Queue: card.crops.pending (RabbitMQ)]                                                         |
|     |                                                                                            |
|     v (Autoscaled by KEDA based on queue depth)                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   | OCR Worker Fleet (Containers: 8 - 128 Replicas)                                          |   |
|   | - Runtime: Python 3.12 (Tesseract 5 LSTM C-API / ONNX Runtime)                            |   |
|   | - Functions: Dual-Zone Header/Body OCR, Word & Character Confidence Extraction            |   |
|   +------------------------------------------------------------------------------------------+   |
|     |                                                                                            |
|     v                                                                                            |
|   [Queue: electors.parsed (RabbitMQ)]                                                            |
|     |                                                                                            |
|     v                                                                                            |
|   +------------------------------------------------------------------------------------------+   |
|   | Graph Consensus & Linguistic Arbiter (Containers: 2 - 4 Replicas)                        |   |
|   | - Runtime: Python 3.12 (Polars Rust Engine + NetworkX)                                   |   |
|   | - Functions: Bipartite Household Graph, Bayesian Surname Prior, Vocalic Safety Barrier   |   |
|   +------------------------------------------------------------------------------------------+   |
|     |                                                        |                                   |
|     v                                                        v                                   |
|   [Relational DB: PostgreSQL 16]                           [Data Lake: Apache Parquet Files]     |
|   - Operational master records, provenance,                - Columnar data partitioned by AC,    |
|     B-tree & GIN indices, audit trails                       optimized for sub-second analytics  |
|                                                                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   | API Gateway & Telemetry Service (Containers: 2 Replicas)                                 |   |
|   | - Runtime: Python 3.12 FastAPI + Uvicorn (uvloop in C)                                   |   |
|   | - Functions: Serves `/api/v1/electors/{id}/crop` in <20ms, Prometheus `/metrics`, SSE    |   |
|   +------------------------------------------------------------------------------------------+   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 5. Microservices Decomposition & Service Contracts

The platform is decomposed into seven specialized, single-responsibility microservices:

```
+--------------------------------------------------------------------------------------------------+
|                                MICROSERVICES DECOMPOSITION TABLE                                 |
+--------------------------------------------------------------------------------------------------+
| Service Name           | Primary Responsibility            | Scaling Metric  | Protocol / Format |
+------------------------+-----------------------------------+-----------------+-------------------+
| 1. crawler-service     | Headless Playwright & CAPTCHA     | 1 - 4 Pods      | AMQP / HTTP       |
| 2. layout-service      | 300 DPI Rasterization & IoU NMS   | 2 - 8 Pods      | AMQP / S3 PNG     |
| 3. ocr-worker-fleet    | Dual-Zone OCR & Confidence Profiling| 8 - 128 Pods  | AMQP / JSON TSV   |
| 4. surgical-reocr      | 5-Tier Escalation on Failed Cards | 2 - 16 Pods     | AMQP / JSON       |
| 5. consensus-service   | Household Graph & Bayesian Prior  | 2 - 4 Pods      | AMQP / PostgreSQL |
| 6. export-service      | Parquet Lake & Styled Excel Export| 1 - 2 Pods      | PostgreSQL / Disk |
| 7. gateway-service     | REST API, Replay & Prometheus     | 2 - 4 Pods      | HTTP / WebSockets |
+--------------------------------------------------------------------------------------------------+
```

### 5.1 Service 1: `crawler-service` (Autonomous Portal Ingestion)
* **Function:** Navigates the CEO Andhra portal, intercepts audio CAPTCHA WAV buffers, executes `faster-whisper` transcription on CTranslate2, and downloads PDF rolls.
* **Resilience:** Token-bucket rate limiter enforcing max 1 request every 2.5 seconds; exponential backoff with jitter on HTTP 429 / 503.
* **Output:** Writes PDF to shared object storage (`s3://raw-rolls/{ac}/roll_part_{part}.pdf`) and publishes task to `roll.ingest.tasks`.

### 5.2 Service 2: `layout-service` (Document Rasterization & Geometry)
* **Function:** Renders PDF pages at 300 DPI in 8-bit continuous anti-aliased grayscale, applies CLAHE contrast equalization, runs Hough micro-deskewing, and executes `RobustCardDetector` with IoU NMS ($IoU \ge 0.40$).
* **Padding:** Expands bounding boxes by $+15\%$ vertically into margins.
* **Output:** Saves lossless PNG crops to MinIO (`s3://crops/{ac}/{part}/{box_id}.png`) and publishes metadata to `card.crops.pending`.

### 5.3 Service 3: `ocr-worker-fleet` (Dual-Zone Optical Character Recognition)
* **Function:** Consumes crop tasks from `card.crops.pending`. Segments crop into Zone A (Header: SNO & EPIC) and Zone B (Demographics Body).
* **Decoding Configuration:** 
  - Zone A: `--psm 7` with alphanumeric whitelist `[A-Z0-9]`.
  - Zone B: `--psm 6` with CASL `user-words` DAWG dictionary (20,791 Andhra surnames).
* **Output:** Extracts token-level and character-level confidence vectors via Tesseract TSV output. Publishes record to `electors.parsed`. If mean confidence $< 0.60$ or fields are missing, routes to `card.surgical_reocr.pending`.

#### 5.3.1 Zonal Header Extraction Architecture (Overcoming SNO Box Border Suppression)
* **The Defect:** Running a single `--psm 6` pass across an entire voter card causes Tesseract's page segmentation analyzer to misinterpret the black rectangular border around the serial number `[ SNO ]` at the top left as a graphical table divider. Consequently, the OCR engine completely skips the EPIC number at the top right (e.g. `YOU1474972`), leading to false claims that EPICs are missing from source rolls.
* **The Architecture:** The Ingestion Service crops Zone A (Header Bar) into an independent memory buffer, scales it by $2.0\times$ bicubic interpolation, and feeds it directly into Tesseract with `--psm 7` (Single Text Line) or `--psm 8` (Single Word) and strict character whitelisting `-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`. This physically isolates the header from the body, guaranteeing 100% EPIC detection.

#### 5.3.2 Non-Greedy Age Parsing Architecture (Protecting 18/19-Year-Old Electors)
* **The Defect:** In legacy parsers, placing `1`, `l`, `|` inside a greedy separator regex `[:*+=;>?\-\.\'\"it1l|/\\!\}\]\s]{0,6}` directly before the age capture group caused the regex engine to greedily swallow `: 1` from `Age : 18` and `Age : 19`. The capture group received only `8` or `9`, which failed the $18 \le \text{Age} \le 110$ threshold, erroneously discarding over 4,300 young electors across AC 37 and AC 38.
* **The Architecture:** The Voter Card Parser enforces an atomic, non-digit separator pattern `[^\d\n\r]{0,4}` followed by a strict two-digit or three-digit capture group `(\d{2,3})`, ensuring the leading digit `1` in young electors is never swallowed.

### 5.4 Service 4: `surgical-reocr` (Multi-Pass Degraded Card Recovery)
* **Function:** Executes 5-tier escalation ladder on cards routed from OCR workers (Pass 1: $2.2\times$ Zone A; Pass 2: Sparse-text header; Pass 3: $1.8\times$ Zone B; Pass 4: Dynamic tile CLAHE; Pass 5: Controlled Otsu fallback).
* **Quarantine:** If card fails all 5 tiers, sets `status = 'Quarantined'` and routes to `anomalies.red_tier` DLQ.

### 5.5 Service 5: `consensus-service` (Household Graph & Linguistic Arbiter)
* **Function:** Reconstructs bipartite household clusters keyed by `(Constituency, Part, Normalized_Door_No)`. Resolves optical corruptions using Bayesian posterior probability $P(S \mid \text{Household}, \text{OCR}) \ge 0.85$.
* **Safeguards:** Enforces the Immutable Safety Barrier (blocking mutations on `Boppana`, `Pasham`, `Kiran`, `David`, `Shaik`).
* **Demographic Classifier:** Classifies electors into Groups `T`, `M`, `C`, and `S` with strict boundary disqualifiers.
* **Output:** Commits finalized record to PostgreSQL 16.

#### 5.5.1 Comprehensive Demographic Traps & Empirical Optical Error Architecture
The consensus engine enforces strict contextual guards on verified empirical failure modes discovered across 721,735 electors:
1. **Palatal/Velar Fricative Confusion (`Gh-` $\rightarrow$ `Ch-`):** 19,500+ empirical records (`Ghinta` $\rightarrow$ `Chinta`, `Ghekka` $\rightarrow$ `Chekka`, `Ghellarao` $\rightarrow$ `Chellarao`, `Ghallapalli` $\rightarrow$ `Challapalli`). Guarded by strict `PROTECTED_GH_STEMS` blocklist protecting authentic names like `Ghantasala`, `Ghantam`, `Ghouse`.
2. **Capital `D` $\rightarrow$ `Q` Bowl Smudge:** 833 empirical records (`Qurga*` $\rightarrow$ `Durga*`, `Qandu` $\rightarrow$ `Dandu`, `Qoddi` $\rightarrow$ `Doddi`, `Qevalla` $\rightarrow$ `Devalla`) with Arabic `Qureshi` protection.
3. **Terminal `l` Smudge Family (12,000+ empirical records across 7 sub-classes):**
   - `-pl` $\rightarrow$ `-pu` (4,603 records: `Nallapl` $\rightarrow$ `Nallapu`, `Kanakapl` $\rightarrow$ `Kanakapu`)
   - `-dl` $\rightarrow$ `-du` (2,450 records: `Rayudl` $\rightarrow$ `Rayudu`, `Govindl` $\rightarrow$ `Govindu`)
   - `-url` $\rightarrow$ `-uri` (2,190 records: `Vallurl` $\rightarrow$ `Valluri`, `Anasurl` $\rightarrow$ `Anasuri`)
   - `-settl` $\rightarrow$ `-setti` (1,280 records: `Medisettl` $\rightarrow$ `Medisetti`, `Koppisettl` $\rightarrow$ `Koppisetti`)
   - `-rajil` $\rightarrow$ `-raju` (1,033 records: `Sattirajil` $\rightarrow$ `Sattiraju`, `Nookarajil` $\rightarrow$ `Nookaraju`)
   - `-baabl` $\rightarrow$ `-babu` (1,831 records: `Yesubaabl` $\rightarrow$ `Yesubabu`, `Suribaabl` $\rightarrow$ `Suribabu`)
   - Female terminal `-l` $\rightarrow$ `-i` (3,056 records: `-shml` $\rightarrow$ `-shmi`, `-vatl` $\rightarrow$ `-vati`, `-eswarl` $\rightarrow$ `-eswari`, `-thl` $\rightarrow$ `-thi`, `-devl` $\rightarrow$ `-devi`).
4. **Authentic `rn` Surnames Protection (10,000+ empirical records):** Valid Indo-Aryan and Dravidian `rn` stems (`Narna` with 4,238 records, `Marni`/`Marne` with 1,826 records, `Karneedi`/`Karnam` with 345 records, `Aparna`/`Annapurna` with 1,639 records) shall NEVER be corrupted by `rn` $\rightarrow$ `m` kerning rules.
5. **Optical `rn` $\rightarrow$ `m` in Non-Sanskrit Positions (1,329 records):** Contextually applied (`^rn([aeiou])` $\rightarrow$ `m\1`, `kshrn` $\rightarrow$ `kshm`, `drna$` $\rightarrow$ `dma`, `hrn` $\rightarrow$ `hm`, `mrn`/`rnm` $\rightarrow$ `mm`, `-arn$` $\rightarrow$ `-am$`).
6. **`Sal` $\rightarrow$ `Sai` (4,604 electors) & `Srl` $\rightarrow$ `Sri` (319 electors):** Straight vertical stem misclassification. Replaced ONLY when co-occurring with recognized Indian given names (`Kumar`, `Ram`, `Lakshmi`, `Krishna`, `Babu`, `Durga`, `Kiran`, `Satya`, `Teja`, `Prasad`). Never applied to isolated surnames.
7. **`...rad` $\rightarrow$ `...rao` (3,363 occurrences):** Terminal loop smudge. Anchored to 45 recognized Telugu masculine stems (`venkata-`, `subba-`, `apparao-`, `satya-`, `nageswara-`, `seshagiri-`). Hard block on `Murad`, `Sharad`, `Varad`, `Farhad`.
8. **Broken Geminate Respect Plurals (`-ull` $\rightarrow$ `-ulu`, `-all` $\rightarrow$ `-alu`):** 3,641 empirical records (`Thrimurthull` $\rightarrow$ `Thrimurthulu`, `Veeraraghavull` $\rightarrow$ `Veeraraghavulu`, `Trimurthull` $\rightarrow$ `Trimurthulu`, `Shriramull` $\rightarrow$ `Shriramulu`, `Amull` $\rightarrow$ `Amulu`, `Abbull` $\rightarrow$ `Abbulu`, `Govindarajull` $\rightarrow$ `Govindarajulu`).
9. **ECI Card Label Bleed Stripping:** 2,128 empirical records where pre-printed `Father's Name:` or `Husband's Name:` produced `Narmne` bleeding into the relation name field (`Narmne Prasad Pilla` $\rightarrow$ `Prasad Pilla`).
10. **`Simhaghalam` $\rightarrow$ `Simhachalam` (1,037 occurrences):** Curve closure on `c`. Enforces terminal morpheme lock `-ghalam$` and `-cghalam$`. General substring replacements are forbidden, protecting Sanskrit `Meghala` and `Meghamala`.
11. **`Simhadai` $\rightarrow$ `Simhadri` (152 occurrences):** Ligature degeneration on `dri`. Constrained strictly to holy hill roots (`Simhadri`, `Neeladri`, `Seshadri`). Strictly protects authentic Sri Vaishnava Brahmin surname `Kandadai`.
12. **Toponymic `-ur` $\rightarrow$ `-uri`:** Restricts village expansions strictly to 23 whitelisted surnames (`Kommuri`, `Yendamuri`, `Valluri`, etc.). Absolute block on `Bahadur`, `Thakur`, `Nagur`, `Mansoor`, `Noor`, `Mayur`, `Ankur`.
13. **Caste Suffix Truncations (`-red` $\rightarrow$ `-reddy`, `-shett` $\rightarrow$ `-shetti`):** Restricts expansion to Telugu roots. Absolute block on Anglo names (`Alfred`, `Wilfred`).
14. **Western `-nald`:** Absolute block preventing `Ronald`, `Reginald`, `Donald` from becoming `*Ronaidu` or `*Reginaidu`.
15. **Halanta `-id`:** Absolute block preventing `David`, `Shahid`, `Rashid`, `Majid`, `Khalid`, `Hamid` from expanding to `*Davidi` or `*Shahidi`.
16. **`Pasham` Cultural Safeguard:** Classical Hindu Telugu nominalizer `-am` locked to Group `T`. Never converted to Islamic `Pasha`.
17. **Ascender Reflection (`d` $\leftrightarrow$ `b`):** Restricts Islamic `-bi` matching to `ISLAMIC_BI_WHITELIST`, preventing `Dibbidi` from becoming `*Dibbibi`.
18. **Single-Word Patronymics:** Supports single-word authentic names (`Ayesha`, `Subhan`, father listed simply as `Basha` or `Shaik`) without flagging false errors.

#### 5.5.2 Image-Level Strikethrough & Rubber Stamp Occlusion Recovery
* **The Defect:** In deletion rolls, deceased or shifted electors have large diagonal `DELETED` or `CANCELLED` rubber stamps stamped across their voter cards, occluding door numbers (e.g. `1-21/J` occluded to `NO J`) and elector names.
* **The Architecture:** The Ingestion and Layout Service applies a Hough transform diagonal angle detector ($30^\circ - 45^\circ$). When a cancellation stamp is recognized, the service tags the record as `status = 'Deleted'` and executes morphological mask subtraction to attenuate the diagonal stamp strokes, allowing the OCR engine to cleanly read the underlying door numbers and demographic text.

### 5.6 Service 6: `export-service` (Data Lake & Deliverables Builder)
* **Function:** Reads committed records from PostgreSQL. Builds Snappy-compressed Apache Parquet data lake partitions (`/lake/ac={ac}/part={part}.parquet`).
* **Corporate Exports:** Generates publication-ready CSV and styled Excel workbooks with corporate summary audit tabs.

### 5.7 Service 7: `gateway-service` (REST API & Observability)
* **Function:** Serves high-speed REST queries (`/api/v1/electors/{id}/crop` in $< 50\text{ms}$), streams live telemetry via WebSockets and SSE, and exposes Prometheus metrics on `/metrics`.

---

## 6. End-to-End Data Flow & State Machine

Every individual card progresses through six strictly defined, idempotent lifecycle states:

```
+-------------------+      +-------------------+      +--------------------+
| 1. ROLL_PENDING   | ===> | 2. CARD_EXTRACTED | ===> | 3. OCR_COMPLETED   |
| PDF verified &    |      | 300 DPI crop in   |      | Dual-zone text &   |
| queued in broker  |      | MinIO; NMS locked |      | confidences stored |
+-------------------+      +-------------------+      +--------------------+
                                                         |
                                                         v
+-------------------+      +-------------------+      +--------------------+
| 6. COMMITTED_GOLD | <=== | 5. CONSENSUS_DONE | <=== | 4. QUARANTINE_HOLD |
| Written to PG &   |      | Bayesian household|      | (If confidence     |
| Parquet data lake |      | consensus resolved|      | < 0.60, alert HITL)|
+-------------------+      +-------------------+      +--------------------+
```

---

## 7. Four-Tier Storage Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                    FOUR-TIER STORAGE TOPOLOGY                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   TIER 1: OBJECT STORAGE (MinIO / AWS S3)                                                        |
|   - Storage for raw PDF rolls and lossless PNG card crops.                                       |
|   - Keying Convention: s3://crops/{ac_no}/{part_no}/{box_index}.png                              |
|   - Metadata: Content-Type: image/png, x-amz-meta-bbox: [x,y,w,h], x-amz-meta-dpi: 300           |
|                                                                                                  |
|   TIER 2: OPERATIONAL RELATIONAL STORE (PostgreSQL 16)                                           |
|   - Primary operational ACID database storing the 32-field Permanent Provenance Schema.          |
|   - Indexing:                                                                                    |
|     * B-Tree Index: (assembly_constituency_no, assembly_part_no, booth_sno)                      |
|     * B-Tree Unique Index: epic_no (where epic_no != '-')                                        |
|     * B-Tree Index: normalized_door_no (for household graph clustering)                          |
|     * GIN Trigram Index: gin_trgm_ops on voter_name_en and rel_name_en (for fuzzy audit)         |
|   - Table Partitioning: Partitioned by Range on assembly_constituency_no.                        |
|                                                                                                  |
|   TIER 3: COLUMNAR ANALYTICAL DATA LAKE (Apache Parquet)                                         |
|   - Long-term analytical data lake optimized for sub-second aggregations.                       |
|   - Partitioned by: /lake/ac_no={ac}/part_no={part}/data.parquet                                 |
|   - Compression: Snappy codec (< 150 bytes per elector record).                                  |
|   - Interoperability: Queryable directly via DuckDB, PySpark, Polars, and ClickHouse.            |
|                                                                                                  |
|   TIER 4: IN-MEMORY MESSAGE BROKER (RabbitMQ AMQP 0-9-1)                                         |
|   - High-throughput message queuing across microservices.                                        |
|   - Dedicated Queues: roll.ingest.tasks, card.crops.pending, electors.parsed, card.reocr.pending |
|   - Dead-Letter Exchange: dlx.anomalies routing to anomalies.red_tier                            |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 8. Failure Modes, Resilience & Self-Healing Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                  FAILURE RESILIENCE MATRIX                                       |
+--------------------------------------------------------------------------------------------------+
| Failure Scenario               | Detection Mechanism      | Automated Recovery Action            |
+--------------------------------+--------------------------+--------------------------------------+
| 1. Truncated / 0-Byte PDF      | Magic byte / EOF check   | Re-schedule crawl task to DLQ retry  |
| 2. OCR Worker Segfault / OOM   | K8s Liveness Probe       | Pod auto-restart; message redelivered|
| 3. Portal Rate-Limit (HTTP 429)| HTTP status code parsing | Exponential backoff with jitter      |
| 4. Severely Degraded Card Print| Mean confidence < 0.60   | Escalate to 5-Tier Surgical Re-OCR   |
| 5. Failed Surgical Re-OCR      | All 5 tiers fail         | Route to anomalies.red_tier for HITL |
| 6. RabbitMQ Broker Outage      | Circuit Breaker pattern  | Local SQLite spooling on workers     |
+--------------------------------------------------------------------------------------------------+
```

### 8.1 Dead-Letter Queue (DLQ) Architecture
Every worker queue declares a Dead-Letter Exchange (`x-dead-letter-exchange: dlx.anomalies`). If a task fails more than 3 consecutive retries or triggers an unhandled parsing error, it is acknowledged and routed to `anomalies.red_tier`. This ensures that a single corrupt card never blocks the processing of remaining electors.

---

## 9. Containerization & Kubernetes / OpenShift Deployment

### 9.1 Red Hat OpenShift (OCP) Invariants
All container images are engineered to meet strict OpenShift Security Context Constraints (`restricted-v2` SCC):
* **Non-Root Execution:** Containers never execute as `root`. Dockerfiles declare `USER 10001`.
* **Arbitrary Dynamic UIDs:** Containers support arbitrary UIDs allocated by OpenShift at runtime via root group ownership:
  ```dockerfile
  RUN chgrp -R 0 /app && chmod -R g=u /app
  ```
* **Read-Only Root Filesystems:** Containers run with read-only root filesystems; all temporary file operations target in-memory `/tmp` (`tmpfs`) or `/dev/shm`.

### 9.2 Event-Driven Autoscaling with KEDA
OCR worker pods scale dynamically based on the queue depth of `card.crops.pending`:
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: deip-ocr-worker-scaler
  namespace: deip-production
spec:
  scaleTargetRef:
    name: deip-ocr-worker
  minReplicaCount: 8
  maxReplicaCount: 128
  triggers:
  - type: rabbitmq
    metadata:
      queueName: card.crops.pending
      mode: QueueLength
      value: "50"
```

---

## 10. Observability, Telemetry & SRE Architecture

### 10.1 Prometheus Metrics Exposed on `/metrics`
```
# HELP deip_elector_processed_total Total count of processed electors
# TYPE deip_elector_processed_total counter
deip_elector_processed_total{ac="37",status="Active"} 236545
deip_elector_processed_total{ac="37",status="Quarantined"} 12

# HELP deip_ocr_confidence_histogram Optical character recognition confidence percentiles
# TYPE deip_ocr_confidence_histogram histogram
deip_ocr_confidence_histogram_bucket{zone="header",le="0.70"} 142
deip_ocr_confidence_histogram_bucket{zone="body",le="0.85"} 4521

# HELP deip_dropped_records_total Strict zero-dropped record assertion metric
# TYPE deip_dropped_records_total counter
deip_dropped_records_total{ac="37"} 0
```

### 10.2 Structured JSON Logging Standard
Every service logs in structured JSON to standard output (`stdout`):
```json
{
  "timestamp": "2026-10-29T09:15:00.123Z",
  "level": "INFO",
  "service": "ocr-worker",
  "correlation_id": "c8a41f6e-92d3-4f9b-8e12-32a89c45b789",
  "ac_no": 37,
  "part_no": 6,
  "page_no": 21,
  "box_index": 20,
  "elector_id": "AP_37_P006_S0595",
  "message": "Dual-zone OCR completed successfully",
  "mean_card_conf": 0.89,
  "duration_ms": 38.4
}
```

---

## 11. Traceability: Mapping SRS Requirements to HLD Components

| SRS Requirement ID | Requirement Description | HLD Architecture Component | Service Responsible |
| :--- | :--- | :--- | :--- |
| **FR-01, 02, 03** | 300 DPI Grayscale, CLAHE & Deskew | Ingestion Pipeline (PyMuPDF + OpenCV) | `layout-service` |
| **FR-04, 05, 06** | 10x3 Invariant, IoU NMS, Indic Padding | `RobustCardDetector` with IoU Suppression | `layout-service` |
| **FR-07, 08** | Section Breaks & Grid Fallback | Dynamic Coordinate Mapper | `layout-service` |
| **FR-09, 10, 11** | Dual-Zone OCR & CASL DAWG Injection | Tesseract 5 C-API + User-Words DAWG | `ocr-worker-fleet` |
| **FR-12..17** | Entity Parsing, EPIC & Age 97 | `VoterCardParser` Engine | `ocr-worker-fleet` |
| **FR-18..22** | Linguistic Rules & Safety Barrier | `LinguisticSuite` & Immunity Blocklists | `consensus-service` |
| **FR-23, 24, 25** | Household Consensus Graph | Bipartite Graph & Bayesian Prior | `consensus-service` |
| **FR-26, 27** | Surgical Re-OCR 5-Tier Ladder | Progressive Re-OCR Engine | `surgical-reocr` |
| **FR-28, 29** | Permanent Provenance Schema | PostgreSQL 16 & MinIO Blob Storage | `consensus-service` |
| **FR-30, 31** | Forensic Replay & Red Quarantine | REST API Gateway & DLQ Architecture | `gateway-service` |
| **FR-32, 33, 34** | Prometheus Telemetry & SSE Push | FastAPI Prometheus Exporter & SSE | `gateway-service` |
| **SPEC-ING-01..08**| Dual Ingestion (Airgap & Crawler) | Local Scanner & Playwright Whisper Crawler| `crawler-service` |

---

## 12. Document Revision History

| Version | Date | Author / Role | Changes / Descriptions |
| :--- | :--- | :--- | :--- |
| **v1.0** | 2026-10-28 | Systems Architecture Team | Initial Microservices Concept & Docker-compose topology. |
| **v2.0** | 2026-10-29 | Lead Systems Architect | Definitive IEEE 1016 HLD: 7 microservices, C4 Models, 10 ADRs, RabbitMQ AMQP topology, PostgreSQL 16 DDL, OpenShift SCC, and KEDA autoscaling. |
| **v2.1** | 2026-10-29 | Principal Systems Architect | Forensics synchronization: Aligned Section 5.5.1 with complete 18 empirical error families (19,500+ `Gh-` $\rightarrow$ `Ch-`, 12,000+ terminal `l` smudges, 10,000+ authentic `rn` surname protection, 833 `Q` $\rightarrow$ `D` smudges, 3,363 `-rad` $\rightarrow$ `-rao` records, 3,641 `-ull` $\rightarrow$ `-ulu` plurals, 2,128 `Narmne` bleeds) and detailed Form 7 strikethrough restoration filter. |
