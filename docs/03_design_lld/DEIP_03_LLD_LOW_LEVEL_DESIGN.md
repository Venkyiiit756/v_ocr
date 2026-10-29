# Low-Level Design (LLD) & Algorithm Specifications
## Enterprise Distributed Electoral Intelligence Platform (DEIP V2.0)

**Document Reference:** DEIP-LLD-V2.0  
**Compliance Standard:** IEEE 1016 Detailed Design Specification  
**Implementation Languages:** Python 3.12 (C-Extensions), PostgreSQL 16, AMQP 0-9-1  
**Target Precision:** Zero False Positives on Protected Surnames; 100% Provenance Capture  

---

## 1. Mathematical Formulations & Core Algorithms

### 1.1 IoU-Based Non-Maximum Suppression (NMS) for Card Boundaries
The core failure mode in V1.0 was concentric duplicate contours surviving a hardcoded 20px threshold.

**Algorithm 1: IoU Non-Maximum Suppression & Grid Enforcement**
Given a set of candidate bounding boxes $B = \{b_1, b_2, \dots, b_m\}$ where each box $b_i = (x_i, y_i, w_i, h_i)$:

1. **Intersection-over-Union (IoU) Definition:**
   $$\text{IoU}(b_i, b_j) = \frac{\text{Area}(b_i \cap b_j)}{\text{Area}(b_i \cup b_j)} = \frac{\max(0, x_2^{\text{int}} - x_1^{\text{int}}) \cdot \max(0, y_2^{\text{int}} - y_1^{\text{int}})}{\text{Area}(b_i) + \text{Area}(b_j) - \text{Area}(b_i \cap b_j)}$$
2. **Center-Distance Normalization:**
   $$D_{\text{center}}(b_i, b_j) = \sqrt{(c_{x, i} - c_{x, j})^2 + (c_{y, i} - c_{y, j})^2}$$
3. **Suppression Condition:**
   Box $b_j$ is suppressed if:
   $$\text{IoU}(b_i, b_j) \ge 0.40 \quad \lor \quad D_{\text{center}}(b_i, b_j) < 80 \text{ pixels (at 300 DPI)}$$
4. **Topological Grid Assertion:**
   - Sort retained boxes into 10 row bands ($\Delta y \le 40$ px) and 3 column bands ($\Delta x \le 50$ px).
   - If $|B_{\text{clean}}| > 30$, retain only the 30 boxes that maximize geometric alignment with the modal row/column pitch.

```python
def apply_card_nms(candidate_boxes, iou_threshold=0.40, dist_threshold=80):
    # Sort boxes by area descending
    boxes = sorted(candidate_boxes, key=lambda b: b[2] * b[3], reverse=True)
    retained = []
    
    for b in boxes:
        bx, by, bw, bh = b
        bcx, bcy = bx + bw / 2, by + bh / 2
        suppress = False
        
        for rb in retained:
            rx, ry, rw, rh = rb
            rcx, rcy = rx + rw / 2, ry + rh / 2
            
            # 1. Center distance
            dist = np.hypot(bcx - rcx, bcy - rcy)
            if dist < dist_threshold:
                suppress = True
                break
                
            # 2. IoU calculation
            ix0, iy0 = max(bx, rx), max(by, ry)
            ix1, iy1 = min(bx + bw, rx + rw), min(by + bh, ry + rh)
            iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
            inter = iw * ih
            union = (bw * bh) + (rw * rh) - inter
            iou = inter / union if union > 0 else 0
            
            if iou >= iou_threshold:
                suppress = True
                break
                
        if not suppress:
            retained.append(b)
            
    return retained
```

### 1.2 Contrast Limited Adaptive Histogram Equalization (CLAHE)
To enhance faint dot-matrix printer ink without thickening strokes:
1. Divide the 8-bit grayscale image $I(x, y)$ into an $8 \times 8$ grid of contextual tiles.
2. For each tile, compute the local histogram $H(k)$.
3. Clip the histogram at clip limit $\beta = 2.0$:
   $$H_{\text{clipped}}(k) = \begin{cases} \beta & \text{if } H(k) > \beta \\ H(k) & \text{otherwise} \end{cases}$$
4. Redistribute the clipped pixels uniformly across all gray levels.
5. Apply bilinear interpolation between adjacent tile mappings to eliminate artificial boundary seams.

### 1.3 Bayesian Household Graph Prior Formulation
For a voter card with observed OCR string $O$, candidate surname $S \in \mathcal{S}$, and household co-residents $\{R_1, R_2, \dots, R_k\}$:

$$P(S \mid O, \text{Household}) = \frac{P(O \mid S) \cdot P(S \mid \text{Household})}{\sum_{S' \in \mathcal{S}} P(O \mid S') \cdot P(S' \mid \text{Household})}$$

Where:
- **Optical Likelihood $P(O \mid S)$:** Derived from character transition probabilities:
  $$P(O \mid S) = \prod_{i=1}^{L} P(o_i \mid s_i)$$
  With empirical weights: $P(d \mid c) = 0.38$, $P(r \mid t) = 0.31$, $P(kk \mid kik) = 0.44$, $P(dla \mid dia) = 0.62$.
- **Household Prior $P(S \mid \text{Household})$:**
  $$P(S \mid \text{Household}) = \frac{\sum_{j=1}^k \mathbb{I}(R_j = S) + \alpha}{k + \alpha \cdot |\mathcal{S}|}$$
  Where $\alpha = 0.05$ (Laplace smoothing).
- **Decision Rule:**
  $$\hat{S} = \begin{cases} 
  S_{\text{consensus}} & \text{if } P(S_{\text{consensus}} \mid O, \text{Household}) \ge 0.85 \text{ and } O \notin \text{ProtectedBlocklist} \\
  O & \text{otherwise (Immutable Safety)}
  \end{cases}$$

---

## 2. Pydantic Data Contracts & Schemas

### 2.1 Card Crop Task Message (`CardCropMessage`)
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class CardCropMessage(BaseModel):
    task_id: str = Field(..., description="UUID for card processing task")
    constituency_no: int = Field(..., ge=1, le=175)
    assembly_part: int = Field(..., ge=1, le=500)
    page_no: int = Field(..., ge=1, le=100)
    box_index: int = Field(..., ge=1, le=30)
    sno_hint: int = Field(..., ge=1, le=2000)
    bbox_pts: List[int] = Field(..., min_length=4, max_length=4, description="[x, y, w, h]")
    crop_s3_uri: str = Field(..., description="s3://crops/ac37/p096/c08.png")
    timestamp_utc: str
```

### 2.2 Parsed Elector Message (`ParsedElectorMessage`)
```python
class TokenConfidence(BaseModel):
    token: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: List[int]

class ParsedElectorMessage(BaseModel):
    elector_id: str # e.g. AP_AC37_P096_S0356
    constituency_no: int
    assembly_part: int
    booth_sno: int
    epic_no: Optional[str] = None
    
    voter_name_raw: str
    voter_name_tokens: List[TokenConfidence]
    mean_voter_conf: float
    
    rel_type: str
    rel_name_raw: str
    rel_name_tokens: List[TokenConfidence]
    mean_rel_conf: float
    
    door_no_raw: str
    age_raw: Optional[int] = None
    gender_raw: Optional[str] = None
    
    raw_ocr_dump: str
    mean_card_conf: float
    source_pdf: str
    page_no: int
    box_index: int
    bbox_pts: List[int]
    crop_s3_uri: str
```

---

## 3. PostgreSQL Database Definition (DDL)

```sql
-- PostgreSQL 16 Enterprise Schema for DEIP
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

CREATE TABLE master_electors (
    elector_id VARCHAR(32) PRIMARY KEY,
    constituency_no SMALLINT NOT NULL,
    constituency_name VARCHAR(64) NOT NULL,
    assembly_part INTEGER NOT NULL,
    booth_sno INTEGER NOT NULL,
    epic_no VARCHAR(16) NOT NULL,
    
    -- Canonical Normalized Demographic Fields
    voter_name_clean VARCHAR(128) NOT NULL,
    rel_type VARCHAR(16) NOT NULL,
    rel_name_clean VARCHAR(128) NOT NULL,
    door_no_clean VARCHAR(64) NOT NULL,
    age SMALLINT NOT NULL,
    gender VARCHAR(16) NOT NULL,
    linguistic_group CHAR(1) NOT NULL CHECK (linguistic_group IN ('T', 'C', 'M', 'S')),
    status VARCHAR(16) DEFAULT 'Active',
    
    -- Unmodified Optical Captures & Confidence Scores
    voter_name_raw TEXT NOT NULL,
    voter_name_conf REAL NOT NULL,
    rel_name_raw TEXT NOT NULL,
    rel_name_conf REAL NOT NULL,
    door_no_raw TEXT NOT NULL,
    mean_card_conf REAL NOT NULL,
    raw_ocr_dump TEXT NOT NULL,
    
    -- Physical Lineage & Provenance
    source_pdf VARCHAR(128) NOT NULL,
    page_no SMALLINT NOT NULL,
    box_index SMALLINT NOT NULL,
    bbox_pts JSONB NOT NULL, -- [x, y, w, h]
    crop_s3_uri VARCHAR(256) NOT NULL,
    
    -- Spatial Keys & Audit Trails
    household_id VARCHAR(64) NOT NULL,
    audit_trail JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indices
CREATE INDEX idx_elector_household ON master_electors(household_id);
CREATE INDEX idx_elector_ac_part ON master_electors(constituency_no, assembly_part, booth_sno);
CREATE INDEX idx_elector_epic ON master_electors(epic_no);
CREATE INDEX idx_elector_conf ON master_electors(mean_card_conf);
CREATE INDEX idx_elector_names_trgm ON master_electors USING gin (voter_name_clean gin_trgm_ops);
```

---

## 4. REST API Specification (OpenAPI 3.1)

### 4.1 Endpoint: Visual Crop Inspection with Overlay
- **Route:** `GET /api/v1/electors/{elector_id}/crop`
- **Response:** `image/png`
- **Behavior:** Fetches 300 DPI crop from MinIO object storage, draws green bounding boxes over high-confidence words ($\ge 0.80$) and red bounding boxes over low-confidence words ($< 0.80$), returning annotated image in $< 20\text{ms}$.

### 4.2 Endpoint: Forensic Lineage Query
- **Route:** `GET /api/v1/electors/{elector_id}`
- **Response:**
```json
{
  "elector_id": "AP_AC37_P096_S0356",
  "voter_name_clean": "Chellarao Ketinidi",
  "rel_name_clean": "Appanna",
  "door_no_clean": "2-1",
  "age": 94,
  "gender": "Male",
  "linguistic_group": "T",
  "provenance": {
    "source_pdf": "roll_part_96.pdf",
    "page_no": 15,
    "box_index": 8,
    "bbox_pts": [121, 2305, 1621, 658],
    "mean_card_conf": 0.94,
    "crop_s3_uri": "s3://crops/ac37/p096/c08.png"
  },
  "audit_trail": [
    {
      "stage": "token_norm",
      "rule": "TOKEN_CHELLAR_NORMALIZATION",
      "before": "Chellar",
      "after": "Chellarao"
    },
    {
      "stage": "household_consensus",
      "rule": "HOUSEHOLD_CONSENSUS_REPAIR",
      "before": "Ketiniei",
      "after": "Ketinidi",
      "evidence": "Co-residents Sno 357, 358, 359 all Ketinidi"
    }
  ]
}
```
