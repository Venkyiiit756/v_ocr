-- ============================================================================
-- Distributed Electoral Ingestion & Intelligence Platform (DEIP V2.2)
-- Database Migration 01: Master Electors Schema & Partitioning
-- Engine Compatibility: PostgreSQL 16+
-- Target Constituencies: AC 37 (Pithapuram), AC 38 (Kakinada Rural), AC 39 (Peddapuram), Statewide (1-175)
-- ============================================================================

-- Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Master Electors Table (Range Partitioned by assembly_constituency_no)
CREATE TABLE IF NOT EXISTS master_electors (
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
    
    -- Permanent Physical Provenance & Coordinate Lineage (32-field standard)
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
    engine_version VARCHAR(16) NOT NULL DEFAULT 'DEIP-2.2.0',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (assembly_constituency_no, elector_id)
) PARTITION BY RANGE (assembly_constituency_no);

-- Active Assembly Constituency Partitions
CREATE TABLE IF NOT EXISTS master_electors_ac37 
    PARTITION OF master_electors FOR VALUES FROM (37) TO (38);

CREATE TABLE IF NOT EXISTS master_electors_ac38 
    PARTITION OF master_electors FOR VALUES FROM (38) TO (39);

CREATE TABLE IF NOT EXISTS master_electors_ac39 
    PARTITION OF master_electors FOR VALUES FROM (39) TO (40);

-- Statewide Catch-All Default Partition for remaining 1-175 constituencies
CREATE TABLE IF NOT EXISTS master_electors_default 
    PARTITION OF master_electors DEFAULT;

-- Composite B-Tree Indexes for Operational Lookups
CREATE INDEX IF NOT EXISTS idx_electors_ac_part_sno 
    ON master_electors(assembly_constituency_no, assembly_part_no, booth_sno);

CREATE INDEX IF NOT EXISTS idx_electors_epic 
    ON master_electors(epic_no) WHERE epic_no != '-';

CREATE INDEX IF NOT EXISTS idx_electors_household 
    ON master_electors(household_cluster_key);

CREATE INDEX IF NOT EXISTS idx_electors_status 
    ON master_electors(status);

CREATE INDEX IF NOT EXISTS idx_electors_confidence 
    ON master_electors(mean_card_conf);

CREATE INDEX IF NOT EXISTS idx_electors_source_loc 
    ON master_electors(source_pdf_sha256, page_no, box_index);

-- Trigram GIN Indexes for Sub-Second Fuzzy Voter & Relative Search
CREATE INDEX IF NOT EXISTS idx_electors_voter_trgm 
    ON master_electors USING gin (voter_name_en gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_electors_rel_trgm 
    ON master_electors USING gin (rel_name_en gin_trgm_ops);

-- JSONB Path Index for Rapid Audit Trail Inspections
CREATE INDEX IF NOT EXISTS idx_electors_audit_gin 
    ON master_electors USING gin (audit_trail jsonb_path_ops);

-- ============================================================================
-- Immutable Historical Audit Ledger (Append-Only Event Sourcing)
-- ============================================================================
CREATE TABLE IF NOT EXISTS electoral_audit_ledger (
    event_id BIGSERIAL PRIMARY KEY,
    assembly_constituency_no SMALLINT NOT NULL,
    elector_id VARCHAR(36) NOT NULL,
    action_type VARCHAR(32) NOT NULL CHECK (action_type IN ('INGEST', 'BAYESIAN_REPAIR', 'SURGICAL_REOCR', 'MANUAL_OVERRIDE', 'DELETION_STRIKE', 'QUARANTINE')),
    field_name VARCHAR(64) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    confidence_delta REAL DEFAULT 0.0,
    rationale TEXT NOT NULL,
    performed_by VARCHAR(64) NOT NULL DEFAULT 'SYSTEM',
    engine_version VARCHAR(16) NOT NULL DEFAULT 'DEIP-2.2.0',
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_ledger_elector 
    ON electoral_audit_ledger(assembly_constituency_no, elector_id);

CREATE INDEX IF NOT EXISTS idx_audit_ledger_timestamp 
    ON electoral_audit_ledger(recorded_at DESC);

-- ============================================================================
-- Analytical & Monitoring Views
-- ============================================================================

-- Constituency & Part Ingestion Quality Rollup
CREATE OR REPLACE VIEW vw_constituency_quality_summary AS
SELECT 
    assembly_constituency_no,
    assembly_constituency_name,
    assembly_part_no,
    COUNT(*) AS total_electors,
    COUNT(CASE WHEN epic_no != '-' THEN 1 END) AS valid_epic_count,
    ROUND(AVG(mean_card_conf)::numeric, 4) AS avg_confidence,
    COUNT(CASE WHEN gender = 'Male' THEN 1 END) AS male_count,
    COUNT(CASE WHEN gender = 'Female' THEN 1 END) AS female_count,
    COUNT(CASE WHEN gender = 'Third Gender' THEN 1 END) AS third_gender_count,
    COUNT(CASE WHEN status = 'Deleted' THEN 1 END) AS deleted_count,
    COUNT(CASE WHEN status = 'Quarantined' THEN 1 END) AS quarantined_count,
    MIN(created_at) AS first_ingested_at,
    MAX(updated_at) AS last_updated_at
FROM master_electors
GROUP BY assembly_constituency_no, assembly_constituency_name, assembly_part_no;

-- Quarantine Review Queue (HITL - Human In The Loop)
CREATE OR REPLACE VIEW vw_quarantine_queue AS
SELECT 
    elector_id,
    assembly_constituency_no,
    assembly_constituency_name,
    assembly_part_no,
    booth_sno,
    epic_no,
    voter_name_en,
    voter_name_raw,
    rel_name_en,
    rel_name_raw,
    door_no,
    age,
    gender,
    mean_card_conf,
    crop_image_s3_uri,
    source_pdf_filename,
    page_no,
    box_index,
    audit_trail
FROM master_electors
WHERE status = 'Quarantined' OR mean_card_conf < 0.65
ORDER BY mean_card_conf ASC, assembly_constituency_no, assembly_part_no, booth_sno;
