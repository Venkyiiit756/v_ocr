# Enterprise Electoral Platform: Dual Ingestion, Telemetry, and Deep Forensic Debugging Architecture

**Author:** Antigravity (Advanced Agentic Coding Suite)  
**Standard:** Enterprise Cloud-Native / Multi-Node Observability Standard  
**Target:** 721k Electors across 3 ACs $\rightarrow$ 40M+ Electors Statewide  
**Core Themes:** Dual-Source Ingestion, Real-Time Structured Telemetry, and Deep Forensic Debugging  

---

## 1. Dual-Source Ingestion Engine: Local Folder vs. Automated Portal Crawler

The system must handle both real-world operational scenarios seamlessly without changing the core OCR engine:
- **Scenario A (Direct PDF Provisioning):** The user provides already-downloaded PDFs on disk, USB, or shared drive (e.g. `C:\Users\vamsi\OneDrive\Desktop\Pithapuram_PDFs\roll_part_<N>.pdf`).
- **Scenario B (Automated Portal Crawler):** The system connects directly to the official CEO Andhra Pradesh / ECI electoral roll download portal, automated via Playwright and acoustic voice CAPTCHA solving using Faster-Whisper.

### 1.1 The Abstract Source Provider Design Pattern
To prevent tight coupling, ingestion is implemented via an **Abstract Ingestion Source Provider**:

```
+--------------------------------------------------------------------------------------------------+
|                                    DUAL INGESTION PATTERN                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +------------------------------------+      +-------------------------------------------+      |
|   | SOURCE A: LocalFolderSource        |      | SOURCE B: AutomatedPortalCrawler          |      |
|   |   - Watches local disk directory   |      |   - Headless Playwright Chrome            |      |
|   |   - Validates PDF integrity (magic |      |   - Faster-Whisper Acoustic Audio CAPTCHA |      |
|   |     bytes `%PDF-`, non-empty)      |      |   - Session rate-limiting & backoff       |      |
|   +------------------------------------+      +-------------------------------------------+      |
|                     |                                              |                             |
|                     +----------------------+-----------------------+                             |
|                                            |                                                     |
|                                            v                                                     |
|                         [Unified Elector Roll Task Producer]                                     |
|                                            |                                                     |
|                                            v                                                     |
|                         `JobPayload: {ac_no, part_no, pdf_stream}`                               |
|                                            |                                                     |
|                                            v                                                     |
|                         [RabbitMQ / Redis Stream: `roll.tasks`]                                  |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

```python
class RollSourceProvider(ABC):
    @abstractmethod
    def acquire_roll(self, ac_no: int, part_no: int) -> BinaryIO:
        """Acquires a valid PDF stream from local disk or portal crawler."""
        pass

class LocalFolderSource(RollSourceProvider):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def acquire_roll(self, ac_no: int, part_no: int) -> BinaryIO:
        path = os.path.join(self.base_dir, f"roll_part_{part_no}.pdf")
        if not os.path.exists(path) or os.path.getsize(path) < 1024:
            raise FileNotFoundError(f"Missing or corrupted local roll: {path}")
        return open(path, "rb")

class AutomatedPortalCrawler(RollSourceProvider):
    def __init__(self, whisper_model="base", headless=True):
        self.whisper = WhisperModel(whisper_model)
        self.headless = headless

    def acquire_roll(self, ac_no: int, part_no: int) -> BinaryIO:
        # 1. Spawn Playwright page
        # 2. Navigate to CEO AP Polling Station Roll URL
        # 3. Intercept `generateVoiceCaptcha` audio stream
        # 4. Transcribe audio via Faster-Whisper to solve alphanumeric CAPTCHA
        # 5. Submit form and download PDF buffer directly to memory/disk
        # 6. Verify `%PDF-` header and return stream
        pass
```

### 1.2 The Hybrid Cache-First Strategy
The crawler operates with a **Cache-First Interceptor**:
1. It queries `LocalFolderSource` first.
2. If `roll_part_{part_no}.pdf` exists on disk and is non-empty, it **skips the portal crawler entirely**.
3. If missing, it dispatches an asynchronous download task to the `AutomatedPortalCrawler` queue, keeping the worker fed ahead of the processing pipeline.

---

## 2. Real-Time Telemetry, Logging & Dashboard Architecture

In the earlier pipeline, telemetry relied on flat text files (`pithapuram_live_log.txt`) scraped via an ad-hoc Python HTTP server (`aggregate_dashboard_server.py`). While functional, it lacked structured metrics, event traces, and real-time push capabilities.

### 2.1 The 3-Tier Observability Stack

```
+--------------------------------------------------------------------------------------------------+
|                                    OBSERVABILITY TOPOLOGY                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  1. STRUCTURED LOGGING:                                                                          |
|     - JSON-formatted logs written to stdout/file.                                                |
|     - Schema: `{"timestamp", "level", "service", "ac_no", "part_no", "sno", "event", "data"}`    |
|                                                                                                  |
|  2. PROMETHEUS METRICS & TELEMETRY:                                                              |
|     - `elector_cards_processed_total{ac="37", status="success"}`                                 |
|     - `elector_ocr_latency_seconds_bucket{service="ocr_worker"}`                                 |
|     - `elector_confidence_gauge{ac="37", part="96"}` (Mean confidence per part)                 |
|     - `queue_backlog_depth{queue="card.crops.pending"}`                                          |
|                                                                                                  |
|  3. REAL-TIME PUSH DASHBOARD (WebSockets / SSE):                                                 |
|     - Live browser dashboard replacing static polling.                                           |
|     - Updates card throughput, active parts, error logs, and quality histograms every 500ms.     |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### 2.2 Metrics Exposed by the API Gateway (`/metrics`)
```
# HELP elector_processed_total Total count of parsed elector cards
# TYPE elector_processed_total counter
elector_processed_total{ac="37", status="clean"} 225265
elector_processed_total{ac="37", status="restored"} 11280

# HELP elector_ocr_confidence_histogram Distribution of card-level optical confidence
# TYPE elector_ocr_confidence_histogram histogram
elector_ocr_confidence_histogram_bucket{le="0.50"} 124
elector_ocr_confidence_histogram_bucket{le="0.75"} 1691
elector_ocr_confidence_histogram_bucket{le="0.90"} 32245
elector_ocr_confidence_histogram_bucket{le="1.00"} 202609

# HELP elector_queue_lag Current pending queue depth
# TYPE elector_queue_lag gauge
elector_queue_lag{queue="card.crops.pending"} 142
```

---

## 3. Deep Forensic Debugging Architecture (Time-Machine Execution)

When a data audit flags an anomaly (e.g. *Why was Sno 603 originally read as `Macish` instead of `Medisetti`?*), the system must provide **Zero-Effort Traceability**.

### 3.1 The 6-Stage Forensic Replay Engine

A dedicated debugging command allows any developer or analyst to execute a **Time-Machine Forensic Replay** for any voter card:

```powershell
python -m electoral_engine.debugger replay --ac 37 --part 109 --sno 603
```

The debugger steps through the entire lifecycle and outputs:

```
========================================================================================
FORENSIC REPLAY AUDIT: ELECTOR AP_AC37_P109_S0603 (EPIC: YOU1560843)
========================================================================================

STAGE 1: DOCUMENT RASTERIZATION
- PDF Source: roll_part_109.pdf | Page: 23 | Hash: 8f4a1c9...
- Resolution: 300 DPI Native Grayscale | CLAHE applied (clip=2.0)
- Skew detected: +0.84 degrees -> Rotated back to 0.00 deg.

STAGE 2: BOUNDARY DETECTION (NMS & GRID)
- Contour Bounding Box: [x=1767, y=3684, w=1621, h=659]
- Grid Cell Invariant: Card 18 on Page 23 (Row 5, Col 2) -> VALID (Slot 18 of 30)
- Indic Subscript Padding: +15% vertical headroom/footroom added.

STAGE 3: DUAL-ZONE OPTICAL OCR
- Zone A (Header): "YOU1560843" (Conf: 0.98)
- Zone B (Body):
    Raw Line 1: "Name : ChellaR Madish" (Tokens: ['ChellaR', 'Madish'] | Conf: [0.88, 0.46])
    Raw Line 2: "Fathers Name? Suryaravu" (Tokens: ['Fathers', 'Name?', 'Suryaravu'] | Conf: [0.91, 0.59, 0.51])
    Raw Line 3: "House Number : 4-40B Photo" (Conf: 0.89)
    Raw Line 4: "Age : 61 Gender : Male" (Conf: 0.94)

STAGE 4: LINGUISTIC NORMALIZATION
- Voter Name: 'ChellaR Madish' -> 'Chellarao Madish' (Rule: TOKEN_CHELLAR_NORMALIZATION)
- Relative Name: 'Suryaravu' -> 'Suryarao' (Rule: ANCHORED_RAVU_SWAP)
- Door Number: '4-40B Photo' -> '4-40B' (Rule: STRIP_TRAILING_PHOTO)

STAGE 5: HOUSEHOLD GRAPH CONSENSUS ARBITRATION
- Household Cluster ID: AC37_P109_D4-40B
- Household Co-Residents:
    1. Sno 601: Gangadhar Medisetti (Rel: Apparao Medisetti)
    2. Sno 603: Chellarao Madish (Target)
    3. Sno 604: Satyavathi Mebish (Husband: Chellarao)
    4. Sno 605: Naga Venkataramana (Father: Challarao Medisetti) <== GROUND TRUTH ANCHOR
- Bayesian Prior: P(Medisetti | Household) = 0.992
- Optical Transition: Madish (conf 0.46) -> Medisetti (Accepted via Household Prior)

STAGE 6: FINAL COMMITTED RECORD
- Final Name: "Chellarao Medisetti" | Relative: "Suryarao" | Group: 'T'
- Saved Visual Artifact: proof_images/debug_replay_AC37_P109_S0603.png
========================================================================================
```

### 3.2 Visual Failure Snapshots (Automated Red-Tier Quarantine)
If any card encounters:
1. Mean character confidence $< 0.60$
2. Incompatible household surname discordance with no majority
3. Unrecognized character transitions

The pipeline automatically writes an **Annotated Forensic Snapshot**:
- It saves a high-res crop with green bounding boxes over high-confidence words and red bounding boxes over low-confidence words.
- It pushes the card ID to the **Human-in-the-Loop (HITL) Review Queue**.

### 3.3 Shadow / Dry-Run Mode
Before rolling out any new linguistic rule or image enhancement filter:
- Run the engine in **Shadow Mode** (`--dry-run --sample 1000`).
- It processes the sample, diffs the new output against the existing baseline, and outputs a visual HTML report highlighting every changed character.

---

## 4. Architectural Summary

| Layer | Implementation Component | Capability Unlocked |
| :--- | :--- | :--- |
| **Ingestion** | `LocalFolderSource` + `AutomatedPortalCrawler` (Playwright & Whisper) | Runs seamlessly on pre-downloaded local folders OR auto-crawls missing rolls with voice CAPTCHA solving. |
| **Telemetry** | OpenTelemetry + Prometheus + WebSocket/SSE Dashboard | Real-time monitoring of cards/sec, live progress bars, queue depths, and confidence histograms across all constituencies. |
| **Debugging** | 6-Stage Forensic Replay + Automated Failure Snapshots + Shadow Mode | 50ms time-machine execution from original PDF pixels to final database entry; zero guesswork on any record. |
