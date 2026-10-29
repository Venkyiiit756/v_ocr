# High-Level Architecture Design (HLD) & Architecture Decision Records (ADR)
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.0)

**Document Reference:** DEIP-HLD-V2.0  
**Compliance Standard:** IEEE 1016-2009 (Systems and Software Engineering — Software Design Descriptions)  
**Architectural Style:** Event-Driven Microservices / Containerized Kubernetes Architecture  
**Target Throughput:** 150–300 cards/second (Distributed) | 721k Voters in $< 30$ mins  

---

## 1. Language & Technology Stack Evaluation Matrix

A critical design-phase question is: **What programming languages and runtimes are best suited for each tier of the platform?**

In enterprise architecture (ISO/IEC 42010), technology selection must be evaluated against four hard engineering criteria:
1. **Raw Vector Compute & Throughput (SIMD / AVX-512 / GPU):** Rendering 300 DPI rasters, CLAHE filtering, and running neural OCR networks.
2. **Library Ecosystem & Ground-Truth Tooling:** Availability of battle-tested Indic OCR engines, PDF rasterizers, and acoustic speech recognizers.
3. **Memory Safety & Process Isolation:** Preventing single malformed PDF segfaults from cascading.
4. **Maintenance Velocity & Schema Uniformity:** Avoiding serialization overhead and schema drift across microservices.

### 1.1 Multi-Language Comparative Analysis

| Subsystem / Tier | Option A: Python 3.12 (C-Extensions) | Option B: Rust | Option C: Go (Golang) | Option D: C++ (Native) | Architectural Selection & Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PDF Ingestion & 300 DPI Rasterization** | **PyMuPDF (MuPDF C-engine)**: Renders 300 DPI page in 40ms via native C SIMD. | `pdfium-render` (C++ wrapper). High safety, but wrapper overhead. | `unidoc` / `pdfcpu`. Lacks high-fidelity raster rendering. | Direct MuPDF / Poppler C++. Maximum speed, high maintenance risk. | **Selected: Python 3.12 (PyMuPDF / C-Core)**. Raw speed is identical to C++ because rendering executes in native C code without GIL contention. |
| **Computer Vision (CLAHE, NMS, Deskew)** | **OpenCV-Python (C++ backend)**: Zero-copy NumPy memory buffers. | `imageproc` / `opencv-rust`. Immature NMS bindings. | `gocv` (cgo wrapper). Heavy cgo context-switch penalty. | Native OpenCV C++. Fast, but segfault risk on corrupt images. | **Selected: Python 3.12 (OpenCV / NumPy SIMD)**. C++ core performance with memory-safe container encapsulation. |
| **Acoustic Voice CAPTCHA Solver** | **Faster-Whisper (CTranslate2 in C++)**: 4x faster than PyTorch; 8-bit quantized. | `whisper-rs` (C++ bindings). Functional, but complex build. | No native production Whisper engine. | Direct `whisper.cpp`. Fast, but complex audio pipeline. | **Selected: Python 3.12 (CTranslate2 C++ engine)**. Transcribes voice audio in $< 150\text{ms}$ with zero PyTorch overhead. |
| **OCR Inference & Confidence Extraction** | **Tesseract 5 LSTM C-API / ONNX Runtime**: Direct in-memory pipe buffer. | `tesseract-rs` (bindings). Hard to customize word confidences. | `gosseract` (cgo overhead on every subimage call). | Direct Libtesseract 5 C++. Maximum speed, high development cost. | **Selected: Python 3.12 with Tesseract 5 C-API + ONNX Runtime**. Provides token bounding boxes and character confidences in-memory. |
| **Household Graph Consensus & Analytics** | **Polars (Rust Core) + NetworkX**: Multi-threaded columnar Arrow memory. | Pure Rust `petgraph` + `polars`. Highest performance. | Go slice operations. Lacks advanced graph algorithms. | Custom C++ graph data structures. Overkill for 721k graph. | **Selected: Python + Polars (Rust core)**. Executes multi-scale consensus across 721k electors in under 8 seconds. |
| **API Gateway & Telemetry** | **FastAPI + Uvicorn (uvloop in C)**: 30,000+ req/sec; shared Pydantic schema. | `Actix-web` / `Axum`. Highest throughput (100k+ req/sec). | `Fiber` / `Gin`. Excellent concurrency, low RAM (15MB). | `Crow` / `Drogon`. High complexity, unnecessary for gateway. | **Selected: Python 3.12 FastAPI (uvloop in C)**. Shares exact Pydantic entity contracts with workers; Go micro-gateway as alternative for cloud scale. |

---

## 2. Architecture Decision Records (ADRs)

### ADR-01: Microservices Architecture with Container Encapsulation
- **Status:** ACCEPTED
- **Context:** Monolithic batch scripts suffered from thread contention, memory bloat on large PDFs, and lacked fault isolation.
- **Decision:** Decouple the system into independent containerized microservices: Ingestion/Layout, OCR Fleet, Graph Consensus, and API Gateway, coordinated by RabbitMQ and MinIO.
- **Consequences:** Eliminates single-point-of-failure risks. Any crashed worker pod is automatically restarted by Kubernetes or Docker without interrupting the remaining pipeline.

### ADR-02: 8-Bit Grayscale CLAHE vs. 1-Bit Binary Thresholding
- **Status:** ACCEPTED
- **Context:** Empirical tests proved that Otsu thresholding bridges letter stems (turning `NAKKAA` into `NWARKAA`), while adaptive Gaussian binarization injects salt-and-pepper noise around faint print.
- **Decision:** Permanently ban hard 1-bit thresholding. Standardize on 300 DPI native 8-bit anti-aliased grayscale with Contrast Limited Adaptive Histogram Equalization (CLAHE).
- **Consequences:** Enhances faint dot-matrix printer ribbon ink while preserving continuous stroke gradients for neural LSTM decoders.

### ADR-03: Dual-Zone OCR with Indic Subscript Padding
- **Status:** ACCEPTED
- **Context:** Whole-card OCR missed small EPIC numbers and chopped off Telugu bottom subscript conjuncts (`వత్తులు` like `-dla` in `Pediredla`).
- **Decision:** Partition each card into Zone A (Header: $2.0\times$ upscaled single-line OCR) and Zone B (Body: multi-line demographic OCR with $+15\%$ vertical headroom and footroom).
- **Consequences:** Eliminates dropped EPICs and prevents `-dla` from degrading into `-dia`.

### ADR-04: Permanent Lineage & Confidence Retention in Master Schema
- **Status:** ACCEPTED
- **Context:** Historical master CSVs dropped `page_no`, `box_index`, and `confidence`, making validation and auditing impossible without ad-hoc scripts.
- **Decision:** The primary database schema shall permanently retain `source_pdf`, `page_no`, `box_index`, `bbox_pts`, `raw_ocr_dump`, and `mean_card_conf`.
- **Consequences:** Enables instantaneous 50ms visual verification and quantified quality filtering (`WHERE mean_card_conf < 0.70`).

### ADR-05: Three-Tier Storage Separation (Blobs, Relations, Columnar)
- **Status:** ACCEPTED
- **Context:** Storing base64 image crops in relational tables bloats databases and slows analytical queries.
- **Decision:** Store card PNG image crops in MinIO/S3 object storage, operational ACID transactions in PostgreSQL, and analytical data lake tables in Apache Parquet.
- **Consequences:** Sub-second analytics via DuckDB/Spark while maintaining fast, lightweight REST image serving.

---

## 3. C4 Architecture Models

### 3.1 C4 Level 1: System Context Diagram
```
+--------------------------------------------------------------------------------------------------+
|                                    C4 LEVEL 1: SYSTEM CONTEXT                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +-------------------+       +-----------------------+       +-----------------------------+    |
|   | ECI Portal Scans  |       | Pre-Downloaded PDFs   |       | Data Analysts & Auditors    |    |
|   | (CEO Andhra Govt) |       | (Local Disk / NFS)    |       | (Inspectors, Demographers)  |    |
|   +-------------------+       +-----------------------+       +-----------------------------+    |
|             |                             |                                  ^                   |
|             v                             v                                  |                   |
|   +--------------------------------------------------------------------------+--------------+    |
|   |                     DISTRIBUTED ELECTORAL INTELLIGENCE PLATFORM (DEIP)                  |    |
|   | - Ingests, normalizes, deskews, and crops 300 DPI voter roll scans                      |    |
|   | - Extracts dual-zone OCR text with character-level confidence vectors                   |    |
|   | - Constructs household graphs and resolves optical corruptions via Bayesian priors       |    |
|   | - Serves verified demographic databases, real-time telemetry, and visual proof panels   |    |
|   +-----------------------------------------------------------------------------------------+    |
|                                           |                                                      |
|                                           v                                                      |
|   +-----------------------------------------------------------------------------------------+    |
|   |                   GOLD-STANDARD CENSUS DATABASE & ANALYTICAL DATA LAKE                  |    |
|   | - 721k+ Elector Records with 100% Provenance, Confidences, and Zero Demographic Bias    |    |
|   +-----------------------------------------------------------------------------------------+    |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### 3.2 C4 Level 2: Container Topology (Microservices)

```
+--------------------------------------------------------------------------------------------------+
|                                    C4 LEVEL 2: CONTAINERS                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   [Roll Dispatcher Service]                                                                      |
|     | (Dispatches AC & Part tasks)                                                               |
|     v                                                                                            |
|   [Queue: roll.tasks (RabbitMQ)]                                                                 |
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

## 4. End-to-End Data Flow & State Machine

Every card progresses through six strictly defined, idempotent lifecycle states:

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
