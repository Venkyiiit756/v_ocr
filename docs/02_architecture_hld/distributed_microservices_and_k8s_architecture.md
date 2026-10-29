# Distributed Electoral Intelligence Platform (DEIP): Microservices, Containerization & Kubernetes (K8s) Architecture

**Author:** Antigravity (Advanced Agentic Coding Suite)  
**Standard:** Enterprise Cloud-Native / Multi-Node Scalable System  
**Target:** From 3 Constituencies (721k Electors) to Full State Census (40M+ Electors)  
**Infrastructure Targets:** Local Docker / K3s (Single High-Core Rig) to Cloud Kubernetes (GKE / EKS / AKS)

---

## 1. Why a Distributed Microservices Architecture?

Processing scanned government voter rolls is an **embarrassingly parallel, multi-stage, heterogeneous workload**. 

In a monolithic script:
- If OpenCV hits a memory spike or segfault on a malformed 100MB PDF page, the entire pipeline crashes.
- Heavy PDF rasterization contends for CPU memory with OCR neural nets.
- There is no central queue to inspect live throughput, retry failed cards, or re-run specific stages.

### The Microservices Advantage:
1. **Heterogeneous Scaling:** Layout detection is lightweight CPU-bound; OCR is heavy vector-math (AVX-512 / GPU); Graph reconciliation is graph-memory bound. Decoupling allows each stage to scale independently.
2. **Crash-Proof Fault Isolation:** If a single card fails OCR, only that card message is sent to a Dead-Letter Queue (DLQ). The remaining 721,000 continue without interruption.
3. **Infinite Horizontal Scale (K8s + KEDA):** Scale from 8 worker pods on a single developer workstation to 500+ pods across a 10-node cloud cluster, processing 40 million voters in hours.
4. **Instant API & Headless Verification:** A lightweight FastAPI gateway serves card image crops and bounding box overlays to a web dashboard in under 20 milliseconds.

---

## 2. Event-Driven Microservices Architecture

```
+--------------------------------------------------------------------------------------------------+
|                               DISTRIBUTED SYSTEM TOPOLOGY                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   [Roll Dispatcher]                                                                              |
|          | (Publishes PDF paths)                                                                 |
|          v                                                                                       |
|   [Queue: pdf.tasks]                                                                             |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 1: Ingestion & Layout Service] (Pod Replica: 4 - 16)                                  |
|     - PyMuPDF 300 DPI Native Rendering                                                           |
|     - CLAHE 8-Bit Grayscale Enhancement                                                          |
|     - Hough Card Micro-Deskewing                                                                 |
|     - NMS 10x3 Grid Boundary Detector (+15% Indic Subscript Padding)                             |
|     - Writes high-res card crops to MinIO / S3 Object Storage                                     |
|     - Publishes detected card metadata to Queue                                                  |
|          |                                                                                       |
|          v                                                                                       |
|   [Queue: card.crops.pending]                                                                    |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 2: OCR Worker Fleet] (Pod Replica: 16 - 256, Scaled by KEDA)                         |
|     - Dual-Zone Header (EPIC/SNO) & Body Extraction                                              |
|     - Tesseract 5 LSTM / PaddleOCR Parallel Inference                                            |
|     - Word-level & Character-level Confidence Vector Extraction                                  |
|     - Publishes parsed elector record to Queue                                                   |
|          |                                                                                       |
|          v                                                                                       |
|   [Queue: electors.parsed]                                                                       |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 3: Graph Consensus & Linguistic Arbiter] (Pod Replica: 2 - 4)                         |
|     - Part-level & Household Bipartite Graph Construction (`Part + Door_No`)                     |
|     - Bayesian Consensus on Optical Ambiguities (P(Surname | Household) >= 0.80)                |
|     - Immutable Vocalic & Halanta Safety Guards (Guarantees Zero False Positives)                |
|     - Writes Gold-Standard Elector to PostgreSQL & Master Parquet Data Lake                      |
|          |                                                                                       |
|          v                                                                                       |
|   [Service 4: API Gateway & Human-in-the-Loop Verification Dashboard]                            |
|     - FastAPI / gRPC High-Throughput REST API                                                    |
|     - Serves `/api/v1/electors/{id}/crop` (Fetches cropped image from MinIO + bbox overlay)       |
|     - Serves `/api/v1/qc/anomalies` (Interactive 1-click review UI for <1% tail)                 |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Storage Architecture: Separation of Blobs, Relations & Analytics

To guarantee instant retrieval and infinite scalability, data is partitioned into three tiers:

```
+---------------------+      +----------------------+      +----------------------+
| 1. OBJECT STORAGE   |      | 2. RELATIONAL DB     |      | 3. ANALYTICAL LAKE   |
| (MinIO / S3)        |      | (PostgreSQL / Times) |      | (Apache Parquet)     |
+---------------------+      +----------------------+      +----------------------+
| Stores raw PNG card |      | Stores active master |      | Partitioned data lake|
| crops:              |      | records, provenance, |      | by constituency and  |
| /ac37/p096/c08.png  |      | and audit logs with  |      | part for lightning-  |
| (Indexed by URI)    |      | B-Tree / GIN indices |      | fast DuckDB/Spark    |
+---------------------+      +----------------------+      +----------------------+
```

---

## 4. Kubernetes (K8s) Cluster Deployment Model

### 4.1 Pod Role Definitions

| Pod Name | Resource Request (CPU / Mem) | Resource Limit (CPU / Mem) | Scaling Policy |
| :--- | :--- | :--- | :--- |
| `layout-detector-pod` | 1.0 CPU / 1.5 GB | 2.0 CPU / 3.0 GB | Scaled by PDF backlog |
| `ocr-worker-pod` | 1.5 CPU / 2.0 GB | 3.0 CPU / 4.0 GB | **KEDA Autoscaling** (Queue depth) |
| `graph-arbiter-pod` | 1.0 CPU / 2.0 GB | 2.0 CPU / 4.0 GB | Static (2 - 4 replicas) |
| `api-gateway-pod` | 0.5 CPU / 512 MB | 1.0 CPU / 1.0 GB | HTTP traffic HPA |
| `rabbitmq-cluster` | 1.0 CPU / 2.0 GB | 2.0 CPU / 4.0 GB | StatefulSet (3 nodes) |
| `minio-cluster` | 1.0 CPU / 2.0 GB | 2.0 CPU / 4.0 GB | Distributed Persistent Volumes |

### 4.2 KEDA ScaledObject for OCR Fleet
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
  maxReplicaCount: 64 # Expands to 128+ on multi-node clusters
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: card.crops.pending
      mode: QueueLength
      value: "50" # Spawns 1 pod for every 50 pending card crops
```

---

## 5. Containerization: Docker Compose Blueprint (Local Execution)

For your current multi-core workstation, the entire distributed architecture can be launched with a single command via **Docker Compose**:

```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports:
      - "5672:5672"   # AMQP
      - "15672:15672" # RabbitMQ Management Dashboard
    environment:
      RABBITMQ_DEFAULT_USER: elector_admin
      RABBITMQ_DEFAULT_PASS: supersecret123

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000" # S3 API
      - "9001:9001" # MinIO Web Console
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: minio_admin
      MINIO_ROOT_PASSWORD: minio_password123

  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: electoral_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgrespassword
    volumes:
      - pg_data:/var/lib/postgresql/data

  layout-service:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: python -m workers.layout_worker
    deploy:
      replicas: 2
    depends_on:
      - rabbitmq
      - minio

  ocr-worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: python -m workers.ocr_worker
    deploy:
      replicas: 6 # Spawns 6 parallel OCR workers matching available CPU cores
    depends_on:
      - rabbitmq
      - minio

  graph-consensus:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: python -m workers.consensus_worker
    deploy:
      replicas: 1
    depends_on:
      - rabbitmq
      - postgres

  api-gateway:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - minio

volumes:
  minio_data:
  pg_data:
```

### Universal Worker Dockerfile (`Dockerfile.worker`)
```dockerfile
FROM python:3.12-slim

# Install core image processing & Indic Tesseract OCR libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-tel \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY electoral_engine/ ./electoral_engine/
COPY workers/ ./workers/

ENV PYTHONUNBUFFERED=1
```

---

## 6. Real-Time Human-in-the-Loop (HITL) Web Inspection Interface

The API gateway exposes dedicated endpoints for interactive auditing:

```
GET /api/v1/electors/{elector_id}
Returns complete record JSON + lineage metadata + confidence score.

GET /api/v1/electors/{elector_id}/proof-image
Returns cropped PNG from MinIO with green/red bounding boxes over low-confidence words.

GET /api/v1/triage/anomalies?limit=50&min_confidence=0.75
Returns a paginated list of anomalous electors for rapid 1-click verification.

POST /api/v1/electors/{elector_id}/override
Allows an authorized analyst to verify or correct a surname, logging the human review
into the immutable audit trail.
```

---

## 7. Migration & Rollout Strategy

1. **Step 1 (Standalone Modular Core):** Refactor `detector.py`, `engine.py`, and `parser.py` into clean, stateless message-driven functions with strict Pydantic schemas.
2. **Step 2 (Local Docker Compose):** Launch the RabbitMQ + MinIO + Worker stack on your multi-core machine. Benchmark 10 assembly parts.
3. **Step 3 (Cluster Scale):** When deploying across full districts (e.g. 10+ constituencies or state-level), point the deployment to a Kubernetes cluster (GKE / K3s) and scale OCR replicas to 64+ pods.
