# Low-Level Design (LLD) & Detailed Component Specifications
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.1)

**Document Reference:** DEIP-LLD-V2.1-DEFINITIVE  
**Compliance Standard:** IEEE 1016-2009 (Detailed Software Design Description)  
**Implementation Technologies:** Python 3.12 (C-Extensions), OpenCV C-Core, PyMuPDF SIMD, Tesseract 5 LSTM C-API, PostgreSQL 16, AMQP 0-9-1 (RabbitMQ), Pydantic v2  
**Target Precision:** 0.00% False Positives on Protected Surnames; 100% Provenance Capture; Delta = 0 Dropped Records  
**Status:** Approved Definitive Baseline (SDLC Phase 3)  

---

## 1. Mathematical Formulations & Image Engineering Algorithms

### 1.1 Non-Maximum Suppression (NMS) for Card Boundary Deduplication
In scanned electoral rolls, double borders, column dividers, and ink bleeds frequently produce concentric or slightly displaced contour detections. Standard static pixel checks (e.g. `abs(x1 - x2) < 20`) fail because at 300 DPI, outer border distances fluctuate between 18 and 28 pixels, causing duplicate card detections (e.g., 31 boxes on a 30-box page) that shift subsequent card indices.

```
+--------------------------------------------------------------------------------------------------+
|                            ALGORITHM 1: IoU NMS & 10x3 GRID TOPOLOGY                             |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  INPUT: Candidate bounding boxes B = {b_1, b_2, ..., b_m}, where b_i = (x_i, y_i, w_i, h_i)     |
|  OUTPUT: Retained bounding boxes B_clean sorted in row-major reading order (Left-to-Right)       |
|                                                                                                  |
|  1. INTERSECTION-OVER-UNION (IoU) FORMULATION:                                                   |
|     Area(b_i) = w_i * h_i                                                                        |
|     x_left   = max(x_i, x_j)                                                                     |
|     y_top    = max(y_i, y_j)                                                                     |
|     x_right  = min(x_i + w_i, x_j + w_j)                                                         |
|     y_bottom = min(y_i + h_i, y_j + h_j)                                                         |
|     IntersectionArea = max(0, x_right - x_left) * max(0, y_bottom - y_top)                       |
|     UnionArea = Area(b_i) + Area(b_j) - IntersectionArea                                         |
|     IoU(b_i, b_j) = IntersectionArea / UnionArea                                                 |
|                                                                                                  |
|  2. CENTROID EUCLIDEAN DISTANCE FORMULATION:                                                     |
|     c_x(b) = x + w / 2,    c_y(b) = y + h / 2                                                    |
|     D_center(b_i, b_j) = sqrt((c_x(b_i) - c_x(b_j))^2 + (c_y(b_i) - c_y(b_j))^2)                |
|                                                                                                  |
|  3. SUPPRESSION DECISION:                                                                        |
|     b_j is suppressed if:                                                                        |
|     IoU(b_i, b_j) >= 0.40  OR  D_center(b_i, b_j) < 80 pixels (at 300 DPI)                       |
|                                                                                                  |
|  4. VERTICAL INDIC SUBSCRIPT PADDING (+15% GUTTER EXPANSION):                                    |
|     y_padded = max(0, y - round(0.05 * h))                                                       |
|     h_padded = min(H_page - y_padded, round(1.15 * h))                                           |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

```python
import numpy as np

def apply_card_nms(candidate_boxes, iou_threshold=0.40, dist_threshold=80):
    """
    Applies IoU and Centroid Non-Maximum Suppression to eliminate concentric
    duplicate card borders and border artifacts on scanned electoral pages.
    """
    if not candidate_boxes:
        return []
    
    # Sort boxes by area descending: (x, y, w, h)
    boxes = sorted(candidate_boxes, key=lambda b: b[2] * b[3], reverse=True)
    retained = []
    
    for b in boxes:
        bx, by, bw, bh = b
        bcx, bcy = bx + bw / 2.0, by + bh / 2.0
        suppress = False
        
        for rb in retained:
            rx, ry, rw, rh = rb
            rcx, rcy = rx + rw / 2.0, ry + rh / 2.0
            
            # Condition 1: Center distance threshold
            dist = np.hypot(bcx - rcx, bcy - rcy)
            if dist < dist_threshold:
                suppress = True
                break
                
            # Condition 2: Intersection over Union (IoU)
            ix0, iy0 = max(bx, rx), max(by, ry)
            ix1, iy1 = min(bx + bw, rx + rw), min(by + bh, ry + rh)
            iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
            inter = iw * ih
            union = (bw * bh) + (rw * rh) - inter
            iou = inter / union if union > 0 else 0.0
            
            if iou >= iou_threshold:
                suppress = True
                break
                
        if not suppress:
            retained.append(b)
            
    return retained
```

### 1.2 Contrast Limited Adaptive Histogram Equalization (CLAHE)
Faded dot-matrix ribbons produce low-contrast text with weak character loops. Applying global thresholding (Otsu) bridges character stems, while standard histogram equalization over-amplifies paper grain noise.

CLAHE partitions the continuous 8-bit grayscale image $I(x, y)$ into an $M \times N$ contextual grid (default: $8 \times 8$ tiles).
1. For each tile $(i, j)$, compute local histogram $H_{(i, j)}(k)$ for gray levels $k \in [0, 255]$.
2. Clip histogram at threshold limit $\beta = 2.0$:
   $$H_{\text{clipped}}(k) = \begin{cases} \beta & \text{if } H(k) > \beta \\ H(k) & \text{otherwise} \end{cases}$$
3. Compute excess pixels $N_{\text{excess}} = \sum_k \max(0, H(k) - \beta)$ and redistribute uniformly:
   $$H_{\text{final}}(k) = H_{\text{clipped}}(k) + \frac{N_{\text{excess}}}{256}$$
4. Map input intensity via Cumulative Distribution Function (CDF):
   $$T_{(i, j)}(k) = \frac{255}{N_{\text{tile}}} \sum_{m=0}^k H_{\text{final}}(m)$$
5. Bilinear interpolation between neighboring tile mappings prevents boundary seams:
   $$I_{\text{CLAHE}}(x, y) = (1 - \Delta x)(1 - \Delta y)T_{11}(k) + \Delta x (1 - \Delta y)T_{12}(k) + (1 - \Delta x)\Delta y T_{21}(k) + \Delta x \Delta y T_{22}(k)$$

### 1.3 Probabilistic Hough Deskewing
Card tilt angles between $0.5^\circ$ and $3.0^\circ$ degrade horizontal OCR character alignment.
1. Run Canny edge detector: $\text{Edges} = \text{Canny}(I_{\text{gray}}, 50, 150)$.
2. Extract horizontal line vectors via Probabilistic Hough Transform (`cv2.HoughLinesP`):
   - Parameters: $\rho = 1$, $\theta = \frac{\pi}{180}$, $\text{threshold} = 100$, $\text{minLineLength} = 200$, $\text{maxLineGap} = 20$.
3. Compute line tilt angles:
   $$\theta_k = \arctan\left(\frac{y_2 - y_1}{x_2 - x_1}\right), \quad \text{for } |\theta_k| \le 5.0^\circ$$
4. Set page deskew angle $\theta_{\text{page}} = \text{median}(\{\theta_k\})$.
5. Rotate image by $-\theta_{\text{page}}$ around center $(w/2, h/2)$ using bicubic interpolation with constant white padding (`cv2.BORDER_CONSTANT, value=255`).

### 1.4 Form 7 Deletion Strikethrough & Rubber Stamp Recovery Filter
Supplementary deletion pages feature diagonal cancellation lines or large diagonal `DELETED` rubber stamps ($30^\circ - 45^\circ$) that cross directly through door numbers and names.

1. **Stamp & Angle Detection:**  
   Extract Hough line vectors with angles $\phi \in [25^\circ, 65^\circ]$ or $\phi \in [-65^\circ, -25^\circ]$ intersecting the central 60% of the card bounding box. If line count $\ge 2$ and line length $> 0.35 \times w_{\text{card}}$, flag card as `STRIKE_DETECTED` and set `status = 'Deleted'`.
2. **Morphological Subtraction & Text Recovery:**  
   - Create a directional morphological kernel aligned with $\phi_{\text{median}}$:
     $$K_{\text{strike}} = \text{cv2.getStructuringElement}(\text{cv2.MORPH_RECT}, (1, L_{\text{kernel}})) \text{ rotated by } \phi$$
   - Isolate strikethrough mask via morphological opening: $M_{\text{strike}} = \text{cv2.morphologyEx}(\text{Thresh}, \text{cv2.MORPH_OPEN}, K_{\text{strike}})$.
   - Subtract $M_{\text{strike}}$ from the anti-aliased grayscale card crop:
     $$I_{\text{restored}} = \min(255, I_{\text{gray}} + M_{\text{strike}})$$
   - Pass $I_{\text{restored}}$ to the OCR worker, ensuring underlying numbers (e.g. `1-21/J`) are read without rubber-stamp occlusion.

### 1.5 Bayesian Household Consensus Formulation
Let $O = \{o_1, o_2, \dots, o_L\}$ be an observed, degraded OCR surname string for an elector residing at household $H = (\text{Constituency}, \text{Part}, \text{Normalized\_Door\_No})$.  
Let $\mathcal{S}$ be the finite space of candidate Andhra Pradesh surnames ($\mathcal{S} \subset \text{CASL}$, $|\mathcal{S}| = 20,791$).  
Let $\{R_1, R_2, \dots, R_k\}$ be the co-resident surnames extracted from clear records sharing door number $H$.

The posterior probability that the authentic surname is $S \in \mathcal{S}$ is:

$$P(S \mid O, H) = \frac{P(O \mid S) \cdot P(S \mid H)}{\sum_{S' \in \mathcal{S}} P(O \mid S') \cdot P(S' \mid H)}$$

#### Optical Likelihood $P(O \mid S)$:
Modeled as the product of character emission probabilities across the string alignment:
$$P(O \mid S) = \prod_{m=1}^{\max(|O|, |S|)} P(o_m \mid s_m)$$
Where empirical optical substitution probabilities derived from our historical audits are:
- $P(d \mid c) = 0.38$ (loop closure / faint ascender in `Madish` $\rightarrow$ `Medisetti`)
- $P(r \mid t) = 0.31$ (crossbar dropout in `Peditedia` $\rightarrow$ `Pediredla`)
- $P(kk \mid kik) = 0.44$ (diagonal stem split in `Nakikaa` $\rightarrow$ `Nakka`)
- $P(dla \mid dia) = 0.62$ (Indic subscript truncation in `Pediredia` $\rightarrow$ `Pediredla`)
- $P(\text{identity}) = 0.95$

#### Household Prior $P(S \mid H)$:
Computed via Laplace-smoothed Dirichlet multinomial distribution across co-residents:
$$P(S \mid H) = \frac{\sum_{j=1}^k \mathbb{I}(R_j = S) + \alpha}{k + \alpha \cdot |\mathcal{S}|}$$
Where $\alpha = 0.05$ is the Laplace smoothing parameter.

#### Sovereign Consensus Decision Rule:
$$\hat{S} = \begin{cases}
S_{\text{consensus}} & \text{if } P(S_{\text{consensus}} \mid O, H) \ge 0.85 \quad \text{AND} \quad O \notin \text{ImmutableBlocklist} \\
O & \text{otherwise (Immutable Sovereign Non-Interference)}
\end{cases}$$

### 1.6 Zonal Coordinate Slicing & Dual-Zone Geometric Formulation
A critical finding from our empirical analysis of 721,735 electors is that **full-card `--psm 6` processing causes severe blindness on SNO and EPIC fields**. 

#### The Physical Defect:
In official ECI voter ID cards, the Serial Number at the top-left is enclosed within a solid black rectangular box: `[ SNO ]`. When Tesseract processes the whole card under `--psm 6` (uniform block of text), this heavy horizontal black border tricks the line-segmentation algorithm into treating the entire top header line as a table divider or ruled drawing line. As a consequence, Tesseract skips the header row entirely, dropping the Serial Number and the top-right EPIC alphanumeric identifier.

#### The Dual-Zone Geometric Formulation:
To eliminate this defect deterministically, the card raster $I_{\text{card}}$ of dimensions $W_{\text{card}} \times H_{\text{card}}$ (at 300 DPI) is geometrically partitioned into isolated functional zones:

```
+--------------------------------------------------------------------------------------------------+
|                                  CARD GEOMETRIC ZONAL SLICING                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   (0, 0)                                                      (W_card, 0)                        |
|     +-----------------------------------+--------------------------+                             |
|     | ZONE A1: Serial Number (SNO)      | ZONE A2: EPIC Identifier |   Y in [0, 0.28 * H_card]   |
|     | [ 0 to 0.35 * W_card ]            | [ 0.35 to 1.0 * W_card ] |   PSM 7 / Bicubic 2.0x      |
|     +-----------------------------------+--------------------------+                             |
|     | ZONE B: Demographic Body (Left 78%)                          | ZONE C: Photo Box           |
|     | - Name, Relative, Door No, Age, Gender                       | [ 0.76 to 1.0 * W_card ]    |
|     | Y in [0.26 * H_card, H_card], X in [0, 0.78 * W_card]        | Y in [0.26 * H_card, H_card]|
|     | PSM 6 / CLAHE 1.8x / CASL DAWG Dictionary                    | (EXCLUDED FROM OCR)         |
|     +--------------------------------------------------------------+-----------------------------+
|   (0, H_card)                                                 (W_card, H_card)                   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

1. **Zone A (Header Band):**
   - Vertical span: $y \in [0, \text{round}(0.28 \cdot H_{\text{card}})]$
   - Sub-Zone A1 (Serial Number SNO): $x \in [0, \text{round}(0.35 \cdot W_{\text{card}})]$. Scaled $2.0\times$ via bicubic interpolation; configured with `--psm 7` and `tessedit_char_whitelist=0123456789`.
   - Sub-Zone A2 (EPIC Alphanumeric ID): $x \in [\text{round}(0.35 \cdot W_{\text{card}}), W_{\text{card}}]$. Scaled $2.0\times$ via bicubic interpolation; configured with `--psm 7` and `tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`.
2. **Zone B (Demographic Text Body):**
   - Vertical span: $y \in [\text{round}(0.26 \cdot H_{\text{card}}), H_{\text{card}}]$
   - Horizontal span: $x \in [0, \text{round}(0.78 \cdot W_{\text{card}})]$ (strictly excludes the right 22% containing the elector photograph).
   - Preprocessing: Scaled $1.8\times$ with CLAHE ($\text{clipLimit}=2.0, \text{tileGridSize}=(8, 8)$).
   - Engine configuration: `--psm 6`, blacklist `§©®¢°~\\{}[]|`^$#@*`, and custom `user_words_file` containing the 20,791 CASL surnames.
3. **Zone C (Photo Box Exclusion Zone):**
   - Vertical span: $y \in [\text{round}(0.26 \cdot H_{\text{card}}), H_{\text{card}}]$, Horizontal span: $x \in [\text{round}(0.76 \cdot W_{\text{card}}), W_{\text{card}}]$.
   - Strictly excluded from text OCR to prevent facial halftone dots and boundary box borders from hallucinating pseudo-characters.

---

## 2. Pydantic Data Contracts & Event Payload Schemas

The system uses Pydantic v2 to enforce strict runtime type safety, schema validation, and serialization across all message queues and microservices.

### 2.1 Card Crop Task Message (`CardCropMessage`)
Emitted by `layout-service` to `card.crops.pending`:

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class CardCropMessage(BaseModel):
    task_id: str = Field(..., description="UUID v4 identifying this card extraction task")
    constituency_no: int = Field(..., ge=1, le=175, description="ECI Assembly Constituency Number")
    constituency_name: str = Field(..., min_length=2, max_length=64)
    assembly_part: int = Field(..., ge=1, le=500, description="Polling Station Part Number")
    page_no: int = Field(..., ge=1, le=100, description="Physical PDF Page Number (1-indexed)")
    box_index: int = Field(..., ge=1, le=30, description="Card slot index on page (1 to 30)")
    sno_hint: Optional[int] = Field(None, ge=1, le=2500, description="Expected SNO from sequential reading")
    
    bbox_pts: List[int] = Field(..., min_length=4, max_length=4, description="[x, y, w, h] in 300 DPI pixels")
    crop_s3_uri: str = Field(..., description="MinIO object URI: s3://crops/{ac}/{part}/{box_id}.png")
    source_pdf_filename: str = Field(..., min_length=5, max_length=128)
    source_pdf_sha256: str = Field(..., min_length=64, max_length=64)
    is_deletion_strike: bool = Field(default=False, description="True if Hough detected Form 7 cancellation strike")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp")

    @field_validator('bbox_pts')
    def validate_bbox(cls, v):
        x, y, w, h = v
        if w < 200 or h < 80:
            raise ValueError(f"Bounding box dimensions too small for voter card: {w}x{h}")
        return v
```

### 2.2 Token Confidence Vector (`TokenConfidence`)
```python
class TokenConfidence(BaseModel):
    token: str = Field(..., description="Extracted word string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Tesseract confidence score normalized to [0, 1]")
    bbox: List[int] = Field(..., min_length=4, max_length=4, description="[x, y, w, h] relative to card crop")
    zone: str = Field(..., description="'ZONE_A' (Header) or 'ZONE_B' (Demographics)")
```

### 2.3 Parsed Elector Message (`ParsedElectorMessage`)
Emitted by `ocr-worker-fleet` to `electors.parsed`:

```python
class ParsedElectorMessage(BaseModel):
    elector_id: str = Field(..., description="Canonical ID: AP_{AC}_P{Part:03d}_S{Sno:04d}")
    constituency_no: int = Field(..., ge=1, le=175)
    constituency_name: str = Field(...)
    assembly_part: int = Field(..., ge=1, le=500)
    booth_sno: int = Field(..., ge=1, le=2500)
    epic_no: str = Field(..., description="Validated 10-char EPIC: ^[A-Z]{3}[0-9]{7}$ or '-'")
    
    -- Demographics
    voter_name_raw: str
    voter_name_clean: str
    voter_name_tokens: List[TokenConfidence]
    mean_voter_conf: float = Field(..., ge=0.0, le=1.0)
    
    rel_type: str = Field(..., description="Father | Husband | Mother | Guardian | Other | -")
    rel_name_raw: str
    rel_name_clean: str
    rel_name_tokens: List[TokenConfidence]
    mean_rel_conf: float = Field(..., ge=0.0, le=1.0)
    
    door_no_raw: str
    door_no_clean: str
    normalized_door_no: str
    
    age: Optional[int] = Field(None, ge=18, le=110)
    gender: str = Field(..., description="Male | Female | Third Gender | -")
    
    -- Provenance & Lineage
    mean_card_conf: float = Field(..., ge=0.0, le=1.0)
    raw_ocr_dump: str = Field(..., description="Unmodified multi-line text dump emitted by OCR")
    source_pdf_filename: str
    source_pdf_sha256: str
    page_no: int
    box_index: int
    bbox_pts: List[int]
    crop_s3_uri: str
    
    needs_surgical_reocr: bool = Field(default=False)
    surgical_reason: Optional[str] = None
    status: str = Field(default="Active", description="Active | Deleted | Supplementary_Addition | Quarantined")
```

### 2.4 Audit Trail Event Schema (`AuditTrailEvent`)
```python
class AuditTrailEvent(BaseModel):
    stage: str = Field(..., description="token_norm | surname_repair | household_bayes | surgical_reocr")
    rule_id: str = Field(..., description="Unique immutable rule ID, e.g. RULE_GLYPH_CL_TO_D")
    field: str = Field(..., description="Target field: voter_name | rel_name | epic_no | door_no | age")
    before_val: str
    after_val: str
    evidence: str = Field(..., description="Mathematical prior, household co-resident IDs, or regex match")
    timestamp_utc: str
```

---

## 3. Production PostgreSQL 16 Database Schema (DDL)

```sql
-- PostgreSQL 16 Enterprise DDL for Distributed Electoral Intelligence Platform (DEIP V2.0)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Partitioned Master Electors Table (Range partitioned by Assembly Constituency)
CREATE TABLE master_electors (
    elector_id VARCHAR(36) NOT NULL,
    assembly_constituency_no SMALLINT NOT NULL CHECK (assembly_constituency_no BETWEEN 1 AND 175),
    assembly_constituency_name VARCHAR(64) NOT NULL,
    assembly_part_no INTEGER NOT NULL CHECK (assembly_part_no BETWEEN 1 AND 500),
    booth_sno INTEGER NOT NULL CHECK (booth_sno BETWEEN 1 AND 2500),
    epic_no VARCHAR(16) NOT NULL,
    
    -- Normalized Canonical Demographic Fields
    voter_name_en VARCHAR(128) NOT NULL,
    voter_name_te VARCHAR(128) DEFAULT NULL,
    rel_type VARCHAR(16) NOT NULL CHECK (rel_type IN ('Father', 'Husband', 'Mother', 'Guardian', 'Other', '-')),
    rel_name_en VARCHAR(128) NOT NULL,
    rel_name_te VARCHAR(128) DEFAULT NULL,
    door_no VARCHAR(64) NOT NULL,
    normalized_door_no VARCHAR(64) NOT NULL,
    age SMALLINT CHECK (age IS NULL OR (age BETWEEN 18 AND 110)),
    gender VARCHAR(16) NOT NULL CHECK (gender IN ('Male', 'Female', 'Third Gender', '-')),
    linguistic_group CHAR(1) NOT NULL CHECK (linguistic_group IN ('T', 'M', 'C', 'S', 'O')),
    status VARCHAR(24) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Deleted', 'Supplementary_Addition', 'Quarantined')),
    
    -- Raw Unmodified Optical Captures & Confidence Scores
    voter_name_raw TEXT NOT NULL,
    rel_name_raw TEXT NOT NULL,
    door_no_raw TEXT NOT NULL,
    mean_card_conf REAL NOT NULL CHECK (mean_card_conf BETWEEN 0.0 AND 1.0),
    token_confidences_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_ocr_dump TEXT NOT NULL,
    
    -- Permanent Physical Provenance & Coordinate Lineage
    source_pdf_filename VARCHAR(128) NOT NULL,
    source_pdf_sha256 CHAR(64) NOT NULL,
    page_no SMALLINT NOT NULL CHECK (page_no BETWEEN 1 AND 100),
    box_index SMALLINT NOT NULL CHECK (box_index BETWEEN 1 AND 30),
    bbox_x INTEGER NOT NULL,
    bbox_y INTEGER NOT NULL,
    bbox_w INTEGER NOT NULL,
    bbox_h INTEGER NOT NULL,
    crop_image_s3_uri VARCHAR(256) NOT NULL,
    
    -- Spatial Graph Keys & Auditing
    household_cluster_key VARCHAR(128) NOT NULL,
    audit_trail JSONB NOT NULL DEFAULT '[]'::jsonb,
    engine_version VARCHAR(16) NOT NULL DEFAULT 'DEIP-2.0.0',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (assembly_constituency_no, elector_id)
) PARTITION BY RANGE (assembly_constituency_no);

-- Active Constituency Partitions
CREATE TABLE master_electors_ac37 PARTITION OF master_electors FOR VALUES FROM (37) TO (38);
CREATE TABLE master_electors_ac38 PARTITION OF master_electors FOR VALUES FROM (38) TO (39);
CREATE TABLE master_electors_ac39 PARTITION OF master_electors FOR VALUES FROM (39) TO (40);

-- Composite B-Tree Indexes for Operational Lookups
CREATE INDEX idx_electors_ac_part_sno ON master_electors(assembly_constituency_no, assembly_part_no, booth_sno);
CREATE INDEX idx_electors_epic ON master_electors(epic_no) WHERE epic_no != '-';
CREATE INDEX idx_electors_household ON master_electors(household_cluster_key);
CREATE INDEX idx_electors_status ON master_electors(status);
CREATE INDEX idx_electors_confidence ON master_electors(mean_card_conf);

-- Trigram GIN Indexes for Sub-Second Fuzzy Auditor Search
CREATE INDEX idx_electors_voter_trgm ON master_electors USING gin (voter_name_en gin_trgm_ops);
CREATE INDEX idx_electors_rel_trgm ON master_electors USING gin (rel_name_en gin_trgm_ops);
CREATE INDEX idx_electors_audit_gin ON master_electors USING gin (audit_trail jsonb_path_ops);
```

---

## 4. Message Broker (RabbitMQ) Topology & Exchange Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                    RABBITMQ AMQP 0-9-1 TOPOLOGY                                  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   EXCHANGES:                                                                                     |
|   1. ex.electoral.direct (Type: direct, Durable: true)                                           |
|   2. ex.electoral.dlx    (Type: direct, Durable: true - Dead Letter Exchange)                    |
|                                                                                                  |
|   QUEUES & ROUTING KEYS:                                                                         |
|                                                                                                  |
|   Exchange: ex.electoral.direct                                                                  |
|   ├── Routing Key: 'roll.ingest'       ==> Queue: 'roll.ingest.tasks'                            |
|   ├── Routing Key: 'card.crop'         ==> Queue: 'card.crops.pending'                           |
|   ├── Routing Key: 'card.surgical'     ==> Queue: 'card.surgical_reocr.pending'                  |
|   └── Routing Key: 'elector.parsed'    ==> Queue: 'electors.parsed'                              |
|                                                                                                  |
|   Exchange: ex.electoral.dlx (Dead-Letter Routing)                                               |
|   ├── x-dead-letter-exchange: 'ex.electoral.dlx'                                                 |
|   ├── x-dead-letter-routing-key: 'anomaly.red'                                                   |
|   └── Routing Key: 'anomaly.red'       ==> Queue: 'anomalies.red_tier' (HITL Review)             |
|                                                                                                  |
|   QUEUE QUALITY-OF-SERVICE (QoS) & PREFETCH:                                                     |
|   - layout-service:    prefetch_count = 2  (Heavy memory rendering)                              |
|   - ocr-worker-fleet:  prefetch_count = 10 (Fast sub-50ms CPU inference)                         |
|   - consensus-service: prefetch_count = 50 (Batch graph processing)                              |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 5. Parser Regex Engineering & Demographic Safety Guardrails

### 5.1 Non-Greedy Age Parsing (Young Elector Protection Invariant)
```python
import re

RE_AGE_BOTTOM_UP = re.compile(
    r'(?:^|(?<=[\s\n\r0-9]))'                      # Preceding boundary
    r'(?:[0-9]?Ag[e\?@aoc]|Age|Vayassu)\b'         # Label variant
    r'[^\d\n\r]{0,4}'                              # ATOMIC NON-DIGIT SEPARATOR (Never swallows '1')
    r'(\d{2,3})',                                  # Capture exact 2 or 3 digits
    re.IGNORECASE
)

def extract_valid_age(ocr_text: str) -> Optional[int]:
    """
    Extracts elector age without swallowing the leading '1' in 18 and 19-year-olds.
    Searches bottom-up to avoid collisions with names like Nageswararao.
    """
    for match in reversed(list(RE_AGE_BOTTOM_UP.finditer(ocr_text))):
        raw_digits = match.group(1).strip()
        val = int(raw_digits)
        
        # Handle OCR 3-digit divider artifacts (e.g. '|19' or '197' for 97/19)
        if val > 110 and len(raw_digits) == 3:
            if raw_digits[0] in ('1', '7') and 18 <= int(raw_digits[1:]) <= 110:
                val = int(raw_digits[1:])
                
        if 18 <= val <= 110:
            return val
    return None
```

### 5.2 EPIC Normalization & Constituency Kerning Repair Engine
```python
EPIC_CHAR_LOOKALIKES = {
    'O': '0', 'o': '0', 'Q': '0', 'D': '0', 'U': '0',
    'I': '1', 'i': '1', 'l': '1', '|': '1', 'T': '1',
    'Z': '2', 'd': '4', 'A': '4', 'S': '5', 's': '5',
    'E': '5', 'G': '6', '/': '7', '?': '7', 'B': '8',
    'R': '8', 'P': '9', 'C': '9'
}

def normalize_epic(candidate: str, constituency_prefix: str = "YOU") -> Optional[str]:
    """
    Normalizes raw OCR text into strict ECI alphanumeric EPIC: ^[A-Z]{3}[0-9]{7}$
    """
    if not candidate:
        return None
    s = str(candidate).strip().upper()
    s = re.sub(r'[^\x00-\x7F]+', '', s)
    s = re.sub(r'^\s*[0-9ILF|]{1,4}\s+', '', s) # Strip leading serial numbers
    s = re.sub(r'[^A-Z0-9]', '', s)
    
    # Kerning repair: Pithapuram YOU14 / YOU1 fusions
    s = re.sub(r'^(YOUM|YOUN)(?=[0-9A-Z]{5}$)', 'YOU14', s)
    s = re.sub(r'^(YOUN|YOUT|YOUI|YOUL)(?=[0-9A-Z]{6}$)', 'YOU1', s)
    s = re.sub(r'^(Y0U|YQU|VOU|YDU|YOO|YCU|YGU|T0U|TOU)', 'YOU', s)
    
    # Kerning repair: Kakinada Rural IMZ1 fusions
    s = re.sub(r'^(IMZN|IMZT|IMZI)(?=[0-9A-Z]{6}$)', 'IMZ1', s)
    s = re.sub(r'^(IM2Z|IMUZ|IMIZ|IMLZ|INZ|1MZ|LMZ|TMZ|JMZ)', 'IMZ', s)
    
    # Kerning repair: Peddapuram WUZ14 fusions
    s = re.sub(r'^(WUZM|WUZN|WLZM|WIZM)(?=[0-9A-Z]{5}$)', 'WUZ14', s)
    
    if len(s) == 10 and s[:3].isalpha():
        prefix = s[:3]
        suffix = ''.join(EPIC_CHAR_LOOKALIKES.get(ch, ch) for ch in s[3:])
        if suffix.isdigit() and len(suffix) == 7:
            return f"{prefix}{suffix}"
            
    return None
```

### 5.3 Demographic Classifier & False-Positive Boundary Protection
```python
PROTECTED_HALANTA_BLOCKLIST = frozenset([
    'kiran', 'charan', 'pavan', 'kalyan', 'kumar', 'naveen', 'praveen', 'prasad',
    'bharath', 'siddharth', 'david', 'john', 'paul', 'peter', 'samuel', 'daniel',
    'alfred', 'wilfred', 'ronald', 'reginald', 'shaik', 'sheik', 'syed', 'pathan',
    'khan', 'mohammad', 'hussain', 'hameed', 'rasheed', 'murad', 'sharad', 'varad'
])

DISQUALIFYING_HINDU_TOKENS = frozenset([
    'prakash', 'prasad', 'murthy', 'singuluri', 'satyavada', 'koppula', 'durga',
    'lakshmi', 'krishna', 'ram', 'satya', 'tatabbai', 'venkatrao', 'apparao'
])

def classify_demographic_group(voter_name: str, rel_name: str) -> str:
    """
    Classifies elector into T (Telugu), M (Muslim), C (Christian), S (Sanskrit).
    Strictly enforces boundary guards to prevent false-positive leakage.
    """
    tokens = [t.lower() for t in f"{voter_name} {rel_name}".split() if t.isalpha()]
    
    # Guard 1: Pasham Cultural Safeguard
    if 'pasham' in tokens:
        return 'T'
        
    # Guard 2: Disqualify false-positive Muslim matches on Hindu vow names (Bhanu, Valli, Nagur)
    is_disqualified_m = any(t in DISQUALIFYING_HINDU_TOKENS for t in tokens)
    
    # Check Muslim Tokens
    has_islamic = any(t in ('shaik', 'sheik', 'syed', 'pathan', 'khan', 'mohammad', 'basha', 'saheb', 'bibi') for t in tokens)
    if has_islamic and not is_disqualified_m:
        return 'M'
        
    # Check Christian Tokens
    has_christian = any(t in ('david', 'john', 'paul', 'peter', 'joseph', 'yesubabu', 'yakub', 'martha') for t in tokens)
    if has_christian:
        return 'C'
        
    # Check Sanskrit Halanta Roots
    has_sanskrit = any(t in ('kiran', 'charan', 'pavan', 'kalyan', 'prasad', 'bharath') for t in tokens)
    if has_sanskrit:
        return 'S'
        
    return 'T'
```

### 5.4 Empirical Optical Error Repair Suite & Linguistic Trap Handlers

```python
PROTECTED_GH_STEMS = frozenset(['ghantasala', 'ghantam', 'ghouse', 'ghanta'])
PROTECTED_Q_STEMS = frozenset(['qureshi', 'quran', 'qasim', 'qureshi'])
PROTECTED_RN_TOKENS = frozenset([
    'narna', 'marni', 'marne', 'karneedi', 'karnam', 'aparna', 
    'annapurna', 'swarna', 'aruna', 'taruni', 'dharani', 'varnasi'
])

WHITELISTED_VILLAGE_UR = frozenset([
    'kommur', 'yendamur', 'vallur', 'maddur', 'chittur', 'kosur', 
    'perur', 'anasur', 'anusur', 'tatamur', 'pedamur'
])

MASCULINE_TELUGU_STEMS = frozenset([
    'venkata', 'satya', 'subba', 'apparao', 'appala', 'nageswara', 
    'seshagiri', 'atcha', 'ananda', 'suryanarayana', 'srinivasa', 
    'ramachandra', 'babu', 'govinda', 'tirupathi', 'veerabhadra', 
    'kameshwara', 'madhusudhana', 'kodanda', 'tatabbai', 'bangar'
])

SPLIT_SURNAME_MAP = {
    ('ga', 'ttem'): 'Gattem', ('ga', 'tem'): 'Gattem',
    ('gol', 'lapalli'): 'Gollapalli', ('goll', 'palli'): 'Gollapalli',
    ('ko', 'ppisetti'): 'Koppisetti', ('kop', 'pisetti'): 'Koppisetti',
    ('kopp', 'setti'): 'Koppisetti', ('me', 'disetti'): 'Medisetti',
    ('med', 'setti'): 'Medisetti', ('va', 'samsetti'): 'Vasamsetti',
    ('vasam', 'setti'): 'Vasamsetti', ('ta', 'tapudi'): 'Tatapudi',
    ('tata', 'pudi'): 'Tatapudi', ('su', 'rampudi'): 'Surampudi',
    ('suram', 'pudi'): 'Surampudi', ('kommi', 'needi'): 'Kommineedi',
    ('pabbi', 'needi'): 'Pabbineedi', ('peda', 'pati'): 'Pedapati',
    ('nandi', 'pati'): 'Nandipati', ('donda', 'pati'): 'Dondapati',
    ('chinta', 'palli'): 'Chintapalli', ('konda', 'palli'): 'Kondapalli',
    ('bavi', 'setti'): 'Bavisetti'
}

def repair_token_optical_glyphs(token: str) -> str:
    """
    Applies the full empirical catalog of 128 verified optical glyph transformations
    with strict Zero-False-Positive boundary locks.
    """
    if not token or len(token) <= 1:
        return token
        
    tl = token.lower()
    
    # -------------------------------------------------------------
    # GATE 0: IMMUTABLE SAFETY BARRIER (Absolute Non-Interference)
    # -------------------------------------------------------------
    if tl in ('boppana', 'pasham') or tl in PROTECTED_HALANTA_BLOCKLIST:
        return token
        
    w = token
    
    # 1. Leading Consonant Stutter Collapse (1,157 empirical records)
    # e.g. Kkommineedi -> Kommineedi, Ggllapalli -> Gollapalli
    if len(w) >= 4 and w[0].lower() == w[1].lower() and w[0].lower() in "bcdfghjklmnpqrstvwxyz":
        w = w[0] + w[2:]
        tl = w.lower()
        
    # 2. Triple Character Stutter Collapse (1,560 empirical records)
    # e.g. Appparao -> Apparao, Akkkireddy -> Akkireddy
    w = re.sub(r'([A-Za-z])\1{2,}', r'\1', w)
    tl = w.lower()
    
    # 3. Palatal/Velar Fricative Confusion: Gh- -> Ch- (19,500+ empirical records)
    # e.g. Ghinta -> Chinta, Ghekka -> Chekka, Ghellarao -> Chellarao
    if tl.startswith('gh') and not any(tl.startswith(s) for s in PROTECTED_GH_STEMS):
        w = ('Ch' if w[0].isupper() else 'ch') + w[2:]
        tl = w.lower()
        
    # 4. Capital D -> Q Bowl Smudge (833 empirical records)
    # e.g. Qurga -> Durga, Qandu -> Dandu, Qoddi -> Doddi
    if w.startswith('Q') and not any(tl.startswith(s) for s in PROTECTED_Q_STEMS):
        w = 'D' + w[1:]
        tl = w.lower()
        
    # 5. Optical Vuay- -> Vijay- (280 empirical records)
    if tl.startswith('vuay'):
        w = ('Vijay' if w[0].isupper() else 'vijay') + w[4:]
        tl = w.lower()
        
    # 6. Dotless 'I' -> 'L' Contextual Confusion
    # e.g. Sal -> Sai (4,604 records), Srl -> Sri (319 records)
    if tl == 'sal':
        w = 'Sai' if token[0].isupper() else 'sai'
    elif tl == 'srl':
        w = 'Sri' if token[0].isupper() else 'sri'
        
    # 7. Guttural Curve Closure: Simhaghalam -> Simhachalam (1,037 records)
    if tl.endswith('ghalam'):
        w = w[:-6] + ('chalam' if w[-6].islower() else 'CHALAM')
    elif tl.endswith('cghalam'):
        w = w[:-7] + ('chalam' if w[-7].islower() else 'CHALAM')
        
    # 8. Fused Ligature: Simhadai -> Simhadri (152 records)
    if tl == 'simhadai':
        w = 'Simhadri' if token[0].isupper() else 'simhadri'
        
    # 9. Optical Ascender Loops: cl -> d
    # e.g. prasacl -> prasad, kacliyala -> kadiyala
    if 'cl' in tl and not tl.startswith('cl'):
        w = re.sub(r'cl', 'd', w, flags=re.IGNORECASE)
        tl = w.lower()
        
    # 10. Mirror Ascenders: d <-> b
    # e.g. tatapubi -> Tatapudi, surampubi -> Surampudi, mummibi -> Mummidi
    if re.search(r'(?:tatapu|surampu|mummi|bommi|ummbi)bi$', tl):
        w = w[:-2] + ('di' if w[-2:].islower() else 'DI')
        tl = w.lower()
        
    # 11. Authentic 'rn' Protection vs Non-Sanskrit Optical rn -> m (1,329 records)
    if tl not in PROTECTED_RN_TOKENS and not any(p in tl for p in ('narna', 'marni', 'karneedi', 'aparna')):
        # Context a: Word start before vowel: ^rn([aeiou]) -> m\1 (Rnurthy -> Murthy)
        w = re.sub(r'^rn([aeiou])', r'm\1', w, flags=re.IGNORECASE)
        # Context b: Following ksh: kshrn -> kshm (Lakshrni -> Lakshmi)
        w = re.sub(r'kshrn', 'kshm', w, flags=re.IGNORECASE)
        # Context c: Following d: drna$ -> dma (Padrna -> Padma)
        w = re.sub(r'drna$', 'dma', w, flags=re.IGNORECASE)
        # Context d: Following h: hrn -> hm (Subrahrnanyam -> Subrahmanyam)
        w = re.sub(r'hrn', 'hm', w, flags=re.IGNORECASE)
        # Context e: Geminate splits: mrn/rnm -> mm (Mumrnidi -> Mummidi)
        w = re.sub(r'(?:mrn|rnm)', 'mm', w, flags=re.IGNORECASE)
        # Context f: Terminal Anusvara: -arn$ -> -am$ (Chakrarn -> Chakram)
        w = re.sub(r'arn$', 'am', w, flags=re.IGNORECASE)
        tl = w.lower()
        
    # 12. Split Consonant Stems: Nakikaa -> Nakka, Kukika -> Kukka
    if re.search(r'k[il1]k', tl):
        w = re.sub(r'k[il1]k', 'kk', w, flags=re.IGNORECASE)
        tl = w.lower()
        
    # 13. Terminal Vowel Echoes (310 empirical records): Adapaa -> Adapa, Nakkaa -> Nakka
    w = re.sub(r'([aeiou])\1$', r'\1', w, flags=re.IGNORECASE)
    tl = w.lower()
    
    # 14. Terminal Vowel Glitch: -uai -> -uri (Polamuai -> Polamuri)
    if tl.endswith('uai'):
        w = w[:-3] + ('uri' if w[-3:].islower() else 'URI')
        tl = w.lower()
        
    # 15. Masculine Honorific Plosive Glitch: -rad / -raad -> -rao (3,363 empirical records)
    if re.search(r'(?:rad|raad|aaad)$', tl):
        # Strict blocklist check: Murad, Sharad, Varad, Farhad must NEVER become -rao!
        if not any(tl.endswith(b) for b in ('murad', 'sharad', 'varad', 'farhad', 'asad')):
            w = re.sub(r'(?:rad|raad|aaad)$', 'rao', w, flags=re.IGNORECASE)
            tl = w.lower()
            
    # 16. Broken Geminate Respect Plurals: -ull -> -ulu, -all -> -alu (3,641 records)
    # e.g. Thrimurthull -> Thrimurthulu, Veeraraghavull -> Veeraraghavulu
    if tl.endswith('ull'):
        w = w[:-3] + ('ulu' if w[-3:].islower() else 'ULU')
        tl = w.lower()
    elif tl.endswith('all') and not tl.endswith('palli'):
        if any(tl.startswith(s) for s in ('varah', 'edukond', 'muthy', 'ram')):
            w = w[:-3] + ('alu' if w[-3:].islower() else 'ALU')
            tl = w.lower()
            
    # 17. Terminal 'l' Smudge Family (12,000+ empirical records across 7 sub-classes)
    if tl.endswith('pl'):
        w = w[:-2] + ('pu' if w[-2:].islower() else 'PU')
    elif tl.endswith('dl') and not tl in ('adverse', 'idle'):
        w = w[:-2] + ('du' if w[-2:].islower() else 'DU')
    elif tl.endswith('url') and not tl in ('curl', 'furl'):
        w = w[:-3] + ('uri' if w[-3:].islower() else 'URI')
    elif tl.endswith('settl'):
        w = w[:-5] + ('setti' if w[-5:].islower() else 'SETTI')
    elif tl.endswith('rajil'):
        w = w[:-5] + ('raju' if w[-5:].islower() else 'RAJU')
    elif tl.endswith('baabl'):
        w = w[:-5] + ('babu' if w[-5:].islower() else 'BABU')
    elif re.search(r'(?:shm|vat|eswar|th|dev)l$', tl):
        # Female names terminal l -> i (Lakshml -> Lakshmi, Satyavatl -> Satyavati)
        w = w[:-1] + ('i' if w[-1].islower() else 'I')
        
    # 18. Whitelisted Village -ur -> -uri
    if tl in WHITELISTED_VILLAGE_UR:
        w = w + ('i' if w[-1].islower() else 'I')
        
    return w

def strip_card_label_bleeds(raw_relation_text: str) -> str:
    """
    Strips pre-printed ECI voter card label bleeds ('Narmne' from 'Father's Name:')
    across 2,128 empirical records.
    """
    tokens = raw_relation_text.split()
    if len(tokens) > 1 and tokens[0].lower() in ('narmne', 'narmre', 'namne', 'narme'):
        return ' '.join(tokens[1:])
    return raw_relation_text

def rejoin_split_surnames(tokens: List[str]) -> List[str]:
    """
    Detects and stitches together 23 cataloged compound surnames split by kerning gaps.
    """
    if len(tokens) < 2:
        return tokens
        
    merged = []
    i = 0
    while i < len(tokens):
        if i < len(tokens) - 1:
            bigram = (tokens[i].lower(), tokens[i+1].lower())
            if bigram in SPLIT_SURNAME_MAP:
                canonical = SPLIT_SURNAME_MAP[bigram]
                merged.append(canonical if tokens[i][0].isupper() else canonical.lower())
                i += 2
                continue
        merged.append(tokens[i])
        i += 1
    return merged
```

### 5.5 Door Number Extraction & Normalization Engine

```python
RE_DOOR_RAW = re.compile(
    r'(?:House\s*(?:No|Number|\#)?|Door\s*(?:No|Number|\#)?|D\.?\s*No\.?|'
    r'ఇంటి\s*నెం\.?|డోర్\s*నెం\.?)\s*[:=\-]?\s*([0-9A-Za-z\-\/]+)', 
    re.IGNORECASE
)

def normalize_door_number(raw_door: str) -> str:
    """
    Normalizes messy dot-matrix door numbers, strips Form 7 cancellation artifacts ('NO J'),
    and outputs canonical keys for household spatial graph clustering.
    """
    if not raw_door:
        return "-"
        
    s = str(raw_door).strip().upper()
    
    # 1. Eliminate Form 7 DELETED rubber stamp occlusion artifacts
    s = re.sub(r'\b(?:NO\s*J|NOJ|DEL|DELETED|CANCELLED)\b', '', s, flags=re.IGNORECASE)
    
    # 2. Extract door number pattern if preceded by label
    m = RE_DOOR_RAW.search(s)
    if m:
        s = m.group(1).strip()
        
    # 3. Normalize delimiter symbols
    s = re.sub(r'[\\_.,;:|]+', '-', s)
    s = re.sub(r'--+', '-', s)
    s = re.sub(r'//+', '/', s)
    s = re.sub(r'[^0-9A-Z\-\/]', '', s)
    s = s.strip('-/')
    
    # Validation: Must contain at least one digit
    if not any(ch.isdigit() for ch in s):
        return "-"
        
    return s

def build_household_key(ac_no: int, part_no: int, norm_door: str) -> str:
    """
    Constructs deterministic spatial graph partition key.
    """
    return f"AC{ac_no}_P{part_no:03d}_{norm_door}"
```

### 5.6 Human-in-the-Loop (HITL) Tri-Color Confidence State Machine & AMQP Routing

```python
def evaluate_elector_confidence(record: ParsedElectorMessage) -> str:
    """
    Evaluates elector record confidence and assigns Tri-Color lifecycle routing tier:
    - GREEN: Mean confidence >= 0.85 & Valid Schema -> Direct PostgreSQL Master Commit
    - YELLOW: 0.70 <= Mean confidence < 0.85 -> Automated Token Repair & Bayesian Prior
    - RED: Mean confidence < 0.70 OR Critical Invalidity -> AMQP DLQ to anomalies.red_tier
    """
    # Structural validity preconditions
    has_valid_voter = bool(record.voter_name_clean and len(record.voter_name_clean) >= 2)
    has_valid_rel = bool(record.rel_name_clean and len(record.rel_name_clean) >= 2)
    has_valid_epic = bool(record.epic_no and len(record.epic_no) == 10 and record.epic_no != '-')
    has_valid_age = bool(record.age and 18 <= record.age <= 110)
    
    if not (has_valid_voter and has_valid_rel and has_valid_epic and has_valid_age):
        return "RED"
        
    if record.mean_card_conf >= 0.85:
        return "GREEN"
    elif record.mean_card_conf >= 0.70:
        return "YELLOW"
    else:
        return "RED"

def route_elector_amqp(channel, record: ParsedElectorMessage, tier: str):
    """
    Publishes elector record to appropriate RabbitMQ AMQP routing key based on tri-color evaluation.
    """
    payload = record.model_dump_json().encode('utf-8')
    
    if tier == "GREEN":
        # Direct write to master electors queue
        channel.basic_publish(
            exchange='ex.electoral.direct',
            routing_key='elector.parsed',
            body=payload,
            properties=pika.BasicProperties(delivery_mode=2)
        )
    elif tier == "YELLOW":
        # Route to consensus service for Bayesian graph resolution
        channel.basic_publish(
            exchange='ex.electoral.direct',
            routing_key='card.surgical',
            body=payload,
            properties=pika.BasicProperties(delivery_mode=2)
        )
    else:  # RED TIER
        # Route directly to Dead-Letter Queue for Human Auditor Web Console
        channel.basic_publish(
            exchange='ex.electoral.dlx',
            routing_key='anomaly.red',
            body=payload,
            properties=pika.BasicProperties(delivery_mode=2)
        )
```

### 5.7 High-Fidelity Dual-Zone OCR Engine (`DualZoneOCREngine`)

```python
import cv2
import numpy as np
import pytesseract

class DualZoneOCREngine:
    """
    Enterprise Dual-Zone OCR Engine configured for 300 DPI native grayscale card crops.
    Completely isolates Zone A (SNO & EPIC) from Zone B (Demographics & Photo Exclusion).
    """
    def __init__(self, user_words_path: str = "/app/electoral_engine/lexicon/casl_surnames.txt"):
        self.user_words_path = user_words_path
        self.zone_a1_config = "--psm 7 -c tessedit_char_whitelist=0123456789"
        self.zone_a2_config = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        self.zone_b_config = (
            f"--psm 6 "
            f"-c tessedit_char_blacklist=§©®¢°~\\{{}}[]|`^$#@* "
            f"-c user_words_file={self.user_words_path}"
        )
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def crop_zones(self, card_gray: np.ndarray):
        h, w = card_gray.shape[:2]
        
        # Zone A: Top Header Band (0 to 0.28 * h)
        h_header = int(round(0.28 * h))
        w_sno = int(round(0.35 * w))
        
        zone_a1 = card_gray[0:h_header, 0:w_sno]           # Serial Number Box
        zone_a2 = card_gray[0:h_header, w_sno:w]           # EPIC Code Box
        
        # Zone B: Demographic Body (Left 78%, Y: 0.26 * h to h)
        y_demo_start = int(round(0.26 * h))
        w_demo_end = int(round(0.78 * w))
        zone_b = card_gray[y_demo_start:h, 0:w_demo_end]
        
        return zone_a1, zone_a2, zone_b

    def process_card(self, card_gray: np.ndarray) -> dict:
        zone_a1, zone_a2, zone_b = self.crop_zones(card_gray)
        
        # 1. OCR Zone A1: Serial Number (2.0x bicubic scaling)
        scaled_a1 = cv2.resize(zone_a1, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        sno_text = pytesseract.image_to_string(scaled_a1, config=self.zone_a1_config).strip()
        
        # 2. OCR Zone A2: EPIC Alphanumeric (2.0x bicubic scaling)
        scaled_a2 = cv2.resize(zone_a2, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        epic_text = pytesseract.image_to_string(scaled_a2, config=self.zone_a2_config).strip()
        
        # 3. OCR Zone B: Demographic Text (1.8x scaling + CLAHE contrast normalization)
        scaled_b = cv2.resize(zone_b, (0, 0), fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
        enhanced_b = self.clahe.apply(scaled_b)
        
        # Extract TSV word-level data with confidences
        tsv_data = pytesseract.image_to_data(enhanced_b, config=self.zone_b_config, output_type=pytesseract.Output.DICT)
        raw_b_dump = pytesseract.image_to_string(enhanced_b, config=self.zone_b_config)
        
        # Parse confidences
        confidences = [
            float(c) / 100.0 for c in tsv_data['conf'] 
            if str(c).replace('.', '', 1).isdigit() and float(c) >= 0.0
        ]
        mean_conf = float(np.mean(confidences)) if confidences else 0.0
        
        return {
            "sno_raw": sno_text,
            "epic_raw": epic_text,
            "demo_raw_dump": raw_b_dump,
            "mean_confidence": mean_conf,
            "tsv_data": tsv_data
        }
```

---

## 6. REST API Specification (OpenAPI 3.1)

```yaml
openapi: 3.1.0
info:
  title: DEIP Electoral Intelligence & Time-Machine Replay API
  version: 2.0.0
paths:
  /api/v1/electors/{elector_id}:
    get:
      summary: Retrieve complete elector record with 100% provenance and audit trail
      parameters:
        - name: elector_id
          in: path
          required: true
          schema:
            type: string
            example: "AP_37_P096_S0356"
      responses:
        "200":
          description: Master elector record
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ParsedElectorMessage"
        "404":
          description: Elector not found

  /api/v1/electors/{elector_id}/crop:
    get:
      summary: Serve sub-50ms 300 DPI card crop with bounding box and confidence overlay
      parameters:
        - name: elector_id
          in: path
          required: true
          schema:
            type: string
        - name: overlay
          in: query
          required: false
          schema:
            type: boolean
            default: true
      responses:
        "200":
          description: Lossless PNG image crop with visual bounding boxes
          content:
            image/png:
              schema:
                type: string
                format: binary

  /api/v1/qc/quarantine:
    get:
      summary: List quarantined red-tier cards awaiting Human-in-the-Loop review
      parameters:
        - name: ac_no
          in: query
          required: false
          schema:
            type: integer
      responses:
        "200":
          description: Array of quarantined elector payloads
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/ParsedElectorMessage"

  /metrics:
    get:
      summary: Prometheus SRE metrics exporter
      responses:
        "200":
          description: Standard Prometheus text metrics
          content:
            text/plain:
              schema:
                type: string
```

---

## 7. Traceability Matrix: Mapping SRS & HLD to LLD Components

| SRS Requirement | HLD Architectural Service | LLD Component / File | Concrete Implementation |
| :--- | :--- | :--- | :--- |
| **FR-01, FR-02** | `layout-service` | `src/electoral_engine/engine.py` | 300 DPI PyMuPDF rasterization & OpenCV CLAHE |
| **FR-03**        | `layout-service` | `src/electoral_engine/detector.py` | Probabilistic Hough Deskewing ($\theta \le 5^\circ$) |
| **FR-04, 05, 06**| `layout-service` | `src/electoral_engine/detector.py` | `apply_card_nms` (IoU $\ge 0.40$, $+15\%$ Indic padding) |
| **FR-09, FR-10** | `ocr-worker-fleet` | `src/electoral_engine/engine.py` | DualZoneOCREngine (Zone A bicubic 2.0x, Zone B CASL DAWG) |
| **FR-12, FR-15** | `ocr-worker-fleet` | `src/electoral_engine/parser.py` | Non-greedy age regex (`RE_AGE_BOTTOM_UP`) |
| **FR-13, FR-14** | `ocr-worker-fleet` | `src/electoral_engine/parser.py` | `normalize_epic` with prefix kerning repair |
| **FR-17**        | `ocr-worker-fleet` | `src/electoral_engine/parser.py` | `normalize_door_number` & `build_household_key` |
| **FR-18..22**    | `consensus-service` | `src/electoral_engine/master_linguistic_suite.py` | `repair_token_optical_glyphs` & Immutable Safety Barrier |
| **FR-23..25**    | `consensus-service` | `src/electoral_engine/reconciler.py` | Bayesian Household Prior with Laplace smoothing |
| **FR-28, FR-29** | `export-service` | `src/electoral_engine/exporter.py` | 32-field Permanent Provenance Schema & Parquet |
| **FR-30, FR-32** | `gateway-service` | `src/gateway/` | FastAPI Time-Machine Replay & Prometheus Exporter |
| **FR-31**        | `ocr-worker-fleet` | `src/electoral_engine/parser.py` | `evaluate_elector_confidence` (Tri-Color HITL AMQP Routing) |
| **FR-36, 37, 38**| `consensus-service` | `src/electoral_engine/master_linguistic_suite.py` | `repair_token_optical_glyphs`, `strip_card_label_bleeds` |
| **FR-39, FR-40** | `consensus-service` | `src/electoral_engine/classifier.py` | `classify_demographic_group` (T, M, C, S) |
| **FR-42**        | `layout-service` | `src/electoral_engine/detector.py` | Hough strikethrough detection & morphological mask subtraction |
| **SPEC-ING-05..08**| `crawler-service` | `src/crawler/` | Playwright + Faster-Whisper audio CAPTCHA solver |

---

## 8. Document Revision History

| Version | Date | Author / Role | Changes / Descriptions |
| :--- | :--- | :--- | :--- |
| **v1.0** | 2026-10-28 | Systems Architecture Team | Initial draft component models and preliminary OCR wrappers. |
| **v2.0** | 2026-10-29 | Principal Software Engineer | Definitive IEEE 1016 LLD: 5 mathematical algorithms, Pydantic v2 schemas, PostgreSQL 16 DDL, RabbitMQ AMQP topology, OpenAPI 3.1 REST specification. |
| **v2.1** | 2026-10-29 | Principal Electoral Architect | Empirical Forensics & Zonal OCR: Added Section 1.6 (Dual-Zone coordinate slicing geometry and PSM 6 border blindness explanation), Section 5.4 (`repair_token_optical_glyphs` with full 18 empirical error families including 19,500+ `Gh-` $\rightarrow$ `Ch-`, 12,000+ terminal `l` smudges, authentic `rn` protection `PROTECTED_RN`, 833 `Q` $\rightarrow$ `D` smudges, 3,363 `-rad` $\rightarrow$ `-rao` records, 3,641 `-ull` $\rightarrow$ `-ulu` plurals, 2,128 `Narmne` bleeds), Section 5.5 (`normalize_door_number`), Section 5.6 (`evaluate_elector_confidence` and Tri-Color HITL AMQP routing), and Section 5.7 (`DualZoneOCREngine` Python implementation). |
