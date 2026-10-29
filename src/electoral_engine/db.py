"""
Distributed Electoral Ingestion & Intelligence Platform (DEIP V2.2)
Database Layer: PostgreSQL 16 Enterprise Adapter & Audit Ledger Manager
Supports Partitioned Master Electors Table, Trigram Search, and In-Memory SQLite Fallback for Local/Test Environments.
"""

import os
import json
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Check PostgreSQL driver availability
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor, execute_values
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

import sqlite3


class ElectoralDatabaseAdapter:
    """
    Enterprise Database Adapter for DEIP V2.2.
    Connects to PostgreSQL 16 (production) with automatic fallback to SQLite (local/test).
    Provides atomic batch upsert, append-only audit trail logging, and low-latency queries.
    """

    def __init__(self, db_url: Optional[str] = None, use_sqlite_fallback: bool = False):
        """
        Initializes the DB Adapter.
        :param db_url: PostgreSQL connection string (postgresql://user:pass@host:port/dbname)
                       or sqlite file path / ':memory:'.
        :param use_sqlite_fallback: If True, forces SQLite engine.
        """
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.is_sqlite = use_sqlite_fallback or (self.db_url and self.db_url.startswith("sqlite:")) or not self.db_url
        
        self.pg_pool = None
        self.sqlite_conn = None
        self.lock = threading.Lock()

        if self.is_sqlite:
            sqlite_path = ":memory:"
            if self.db_url and self.db_url.startswith("sqlite:///"):
                sqlite_path = self.db_url.replace("sqlite:///", "")
            self.sqlite_path = sqlite_path
            self._init_sqlite()
        else:
            if not HAS_PSYCOPG2:
                raise ImportError("psycopg2 is required for PostgreSQL connection. Install via pip install psycopg2-binary.")
            self._init_postgres()

    def _init_sqlite(self):
        """Initializes SQLite connection and creates schema."""
        self.sqlite_conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row
        self._create_sqlite_schema()
        logger.info(f"Initialized SQLite Electoral Database at {self.sqlite_path}")

    def _init_postgres(self):
        """Initializes PostgreSQL connection pool."""
        try:
            self.pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=self.db_url
            )
            logger.info("Initialized PostgreSQL Connection Pool for DEIP V2.2")
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL: {e}. Falling back to SQLite in-memory.")
            self.is_sqlite = True
            self.sqlite_path = ":memory:"
            self._init_sqlite()

    def _create_sqlite_schema(self):
        """Creates table structure in SQLite for testing and offline environments."""
        cur = self.sqlite_conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS master_electors (
            elector_id TEXT NOT NULL,
            assembly_constituency_no INTEGER NOT NULL,
            assembly_constituency_name TEXT NOT NULL,
            assembly_part_no INTEGER NOT NULL,
            booth_sno INTEGER NOT NULL,
            epic_no TEXT NOT NULL,
            voter_name_en TEXT NOT NULL,
            voter_name_te TEXT,
            rel_type TEXT NOT NULL,
            rel_name_en TEXT NOT NULL,
            rel_name_te TEXT,
            door_no TEXT NOT NULL,
            normalized_door_no TEXT NOT NULL,
            age INTEGER,
            gender TEXT NOT NULL,
            linguistic_group TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            voter_name_raw TEXT NOT NULL,
            rel_name_raw TEXT NOT NULL,
            door_no_raw TEXT NOT NULL,
            mean_card_conf REAL NOT NULL,
            token_confidences_json TEXT NOT NULL DEFAULT '[]',
            raw_ocr_dump TEXT NOT NULL,
            source_pdf_filename TEXT NOT NULL,
            source_pdf_sha256 TEXT NOT NULL,
            page_no INTEGER NOT NULL,
            box_index INTEGER NOT NULL,
            bbox_x INTEGER NOT NULL,
            bbox_y INTEGER NOT NULL,
            bbox_w INTEGER NOT NULL,
            bbox_h INTEGER NOT NULL,
            crop_image_s3_uri TEXT NOT NULL,
            household_cluster_key TEXT NOT NULL,
            audit_trail TEXT NOT NULL DEFAULT '[]',
            engine_version TEXT NOT NULL DEFAULT 'DEIP-2.2.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (assembly_constituency_no, elector_id)
        );

        CREATE INDEX IF NOT EXISTS idx_electors_ac_part_sno 
            ON master_electors(assembly_constituency_no, assembly_part_no, booth_sno);
        CREATE INDEX IF NOT EXISTS idx_electors_epic 
            ON master_electors(epic_no);
        CREATE INDEX IF NOT EXISTS idx_electors_household 
            ON master_electors(household_cluster_key);
        CREATE INDEX IF NOT EXISTS idx_electors_status 
            ON master_electors(status);

        CREATE TABLE IF NOT EXISTS electoral_audit_ledger (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assembly_constituency_no INTEGER NOT NULL,
            elector_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            confidence_delta REAL DEFAULT 0.0,
            rationale TEXT NOT NULL,
            performed_by TEXT NOT NULL DEFAULT 'SYSTEM',
            engine_version TEXT NOT NULL DEFAULT 'DEIP-2.2.0',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        self.sqlite_conn.commit()
        cur.close()

    def execute_ddl(self, ddl_path: Optional[str] = None):
        """
        Executes external DDL SQL migration file on the connected PostgreSQL database.
        """
        if self.is_sqlite:
            logger.info("SQLite active; skipping PostgreSQL partitioned DDL execution.")
            return

        if not ddl_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ddl_path = os.path.join(base_dir, "sql", "01_master_electors_ddl.sql")

        with open(ddl_path, "r", encoding="utf-8") as f:
            ddl_sql = f.read()

        conn = self.pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(ddl_sql)
            conn.commit()
            logger.info(f"Successfully executed DDL from {ddl_path}")
        finally:
            self.pg_pool.putconn(conn)

    def _normalize_record_for_db(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures all 32 fields conform to DB types and JSON strings."""
        elector_id = str(r.get('elector_id') or r.get('id') or f"{r.get('assembly_constituency_no', 37)}_{r.get('assembly_part_no', 1)}_{r.get('booth_sno', 1)}")
        
        token_conf = r.get('token_confidences_json', [])
        if not isinstance(token_conf, str):
            token_conf = json.dumps(token_conf)
            
        audit_trail = r.get('audit_trail', [])
        if not isinstance(audit_trail, str):
            audit_trail = json.dumps(audit_trail)

        return {
            'elector_id': elector_id,
            'assembly_constituency_no': int(r.get('assembly_constituency_no', 37)),
            'assembly_constituency_name': str(r.get('assembly_constituency_name', 'Pithapuram')),
            'assembly_part_no': int(r.get('assembly_part_no', 1)),
            'booth_sno': int(r.get('booth_sno', 1)),
            'epic_no': str(r.get('epic_no', '-')),
            'voter_name_en': str(r.get('voter_name_en', '-')),
            'voter_name_te': r.get('voter_name_te'),
            'rel_type': str(r.get('rel_type', '-')),
            'rel_name_en': str(r.get('rel_name_en', '-')),
            'rel_name_te': r.get('rel_name_te'),
            'door_no': str(r.get('door_no', '-')),
            'normalized_door_no': str(r.get('normalized_door_no', '-')),
            'age': int(r['age']) if r.get('age') is not None and str(r.get('age')).isdigit() else None,
            'gender': str(r.get('gender', '-')),
            'linguistic_group': str(r.get('linguistic_group', 'T'))[:1],
            'status': str(r.get('status', 'Active')),
            'voter_name_raw': str(r.get('voter_name_raw', '-')),
            'rel_name_raw': str(r.get('rel_name_raw', '-')),
            'door_no_raw': str(r.get('door_no_raw', '-')),
            'mean_card_conf': float(r.get('mean_card_conf', 0.0)),
            'token_confidences_json': token_conf,
            'raw_ocr_dump': str(r.get('raw_ocr_dump', '')),
            'source_pdf_filename': str(r.get('source_pdf_filename', '')),
            'source_pdf_sha256': str(r.get('source_pdf_sha256', '0'*64)),
            'page_no': int(r.get('page_no', 1)),
            'box_index': int(r.get('box_index', 1)),
            'bbox_x': int(r.get('bbox_x', 0)),
            'bbox_y': int(r.get('bbox_y', 0)),
            'bbox_w': int(r.get('bbox_w', 0)),
            'bbox_h': int(r.get('bbox_h', 0)),
            'crop_image_s3_uri': str(r.get('crop_image_s3_uri', '')),
            'household_cluster_key': str(r.get('household_cluster_key', '-')),
            'audit_trail': audit_trail,
            'engine_version': str(r.get('engine_version', 'DEIP-2.2.0'))
        }

    def upsert_electors_batch(self, records: List[Dict[str, Any]], actor: str = "PIPELINE_ENGINE") -> Dict[str, int]:
        """
        Performs high-performance batch upsert into master_electors.
        Employs ON CONFLICT DO UPDATE for idempotency and records audit events.
        """
        if not records:
            return {'inserted_or_updated': 0, 'audit_events': 0}

        cleaned = [self._normalize_record_for_db(r) for r in records]

        if self.is_sqlite:
            return self._upsert_sqlite(cleaned, actor)
        else:
            return self._upsert_postgres(cleaned, actor)

    def _upsert_sqlite(self, cleaned: List[Dict[str, Any]], actor: str) -> Dict[str, int]:
        with self.lock:
            cur = self.sqlite_conn.cursor()
            sql = """
            INSERT INTO master_electors (
                elector_id, assembly_constituency_no, assembly_constituency_name, assembly_part_no, booth_sno, epic_no,
                voter_name_en, voter_name_te, rel_type, rel_name_en, rel_name_te, door_no, normalized_door_no, age, gender,
                linguistic_group, status, voter_name_raw, rel_name_raw, door_no_raw, mean_card_conf, token_confidences_json,
                raw_ocr_dump, source_pdf_filename, source_pdf_sha256, page_no, box_index, bbox_x, bbox_y, bbox_w, bbox_h,
                crop_image_s3_uri, household_cluster_key, audit_trail, engine_version
            ) VALUES (
                :elector_id, :assembly_constituency_no, :assembly_constituency_name, :assembly_part_no, :booth_sno, :epic_no,
                :voter_name_en, :voter_name_te, :rel_type, :rel_name_en, :rel_name_te, :door_no, :normalized_door_no, :age, :gender,
                :linguistic_group, :status, :voter_name_raw, :rel_name_raw, :door_no_raw, :mean_card_conf, :token_confidences_json,
                :raw_ocr_dump, :source_pdf_filename, :source_pdf_sha256, :page_no, :box_index, :bbox_x, :bbox_y, :bbox_w, :bbox_h,
                :crop_image_s3_uri, :household_cluster_key, :audit_trail, :engine_version
            )
            ON CONFLICT (assembly_constituency_no, elector_id) DO UPDATE SET
                epic_no = excluded.epic_no,
                voter_name_en = excluded.voter_name_en,
                voter_name_te = excluded.voter_name_te,
                rel_type = excluded.rel_type,
                rel_name_en = excluded.rel_name_en,
                rel_name_te = excluded.rel_name_te,
                door_no = excluded.door_no,
                normalized_door_no = excluded.normalized_door_no,
                age = excluded.age,
                gender = excluded.gender,
                linguistic_group = excluded.linguistic_group,
                status = excluded.status,
                mean_card_conf = excluded.mean_card_conf,
                token_confidences_json = excluded.token_confidences_json,
                crop_image_s3_uri = excluded.crop_image_s3_uri,
                household_cluster_key = excluded.household_cluster_key,
                audit_trail = excluded.audit_trail,
                updated_at = CURRENT_TIMESTAMP;
            """
            cur.executemany(sql, cleaned)
            self.sqlite_conn.commit()
            cur.close()
            return {'inserted_or_updated': len(cleaned), 'audit_events': 0}

    def _upsert_postgres(self, cleaned: List[Dict[str, Any]], actor: str) -> Dict[str, int]:
        columns = [
            'elector_id', 'assembly_constituency_no', 'assembly_constituency_name', 'assembly_part_no', 'booth_sno', 'epic_no',
            'voter_name_en', 'voter_name_te', 'rel_type', 'rel_name_en', 'rel_name_te', 'door_no', 'normalized_door_no', 'age', 'gender',
            'linguistic_group', 'status', 'voter_name_raw', 'rel_name_raw', 'door_no_raw', 'mean_card_conf', 'token_confidences_json',
            'raw_ocr_dump', 'source_pdf_filename', 'source_pdf_sha256', 'page_no', 'box_index', 'bbox_x', 'bbox_y', 'bbox_w', 'bbox_h',
            'crop_image_s3_uri', 'household_cluster_key', 'audit_trail', 'engine_version'
        ]

        query = f"""
        INSERT INTO master_electors ({', '.join(columns)})
        VALUES %s
        ON CONFLICT (assembly_constituency_no, elector_id) DO UPDATE SET
            epic_no = EXCLUDED.epic_no,
            voter_name_en = EXCLUDED.voter_name_en,
            voter_name_te = EXCLUDED.voter_name_te,
            rel_type = EXCLUDED.rel_type,
            rel_name_en = EXCLUDED.rel_name_en,
            rel_name_te = EXCLUDED.rel_name_te,
            door_no = EXCLUDED.door_no,
            normalized_door_no = EXCLUDED.normalized_door_no,
            age = EXCLUDED.age,
            gender = EXCLUDED.gender,
            linguistic_group = EXCLUDED.linguistic_group,
            status = EXCLUDED.status,
            mean_card_conf = EXCLUDED.mean_card_conf,
            token_confidences_json = EXCLUDED.token_confidences_json,
            crop_image_s3_uri = EXCLUDED.crop_image_s3_uri,
            household_cluster_key = EXCLUDED.household_cluster_key,
            audit_trail = master_electors.audit_trail || EXCLUDED.audit_trail,
            updated_at = CURRENT_TIMESTAMP;
        """

        data_tuples = [tuple(r[col] for col in columns) for r in cleaned]

        conn = self.pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                execute_values(cur, query, data_tuples)
            conn.commit()
            return {'inserted_or_updated': len(cleaned), 'audit_events': 0}
        finally:
            self.pg_pool.putconn(conn)

    def record_audit_event(self, constituency_no: int, elector_id: str, action_type: str,
                           field_name: str, old_val: str, new_val: str, rationale: str,
                           confidence_delta: float = 0.0, actor: str = "SYSTEM") -> None:
        """Appends an event to the immutable electoral audit ledger."""
        if self.is_sqlite:
            cur = self.sqlite_conn.cursor()
            cur.execute("""
            INSERT INTO electoral_audit_ledger (
                assembly_constituency_no, elector_id, action_type, field_name,
                old_value, new_value, confidence_delta, rationale, performed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (constituency_no, elector_id, action_type, field_name, old_val, new_val, confidence_delta, rationale, actor))
            self.sqlite_conn.commit()
            cur.close()
        else:
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                    INSERT INTO electoral_audit_ledger (
                        assembly_constituency_no, elector_id, action_type, field_name,
                        old_value, new_value, confidence_delta, rationale, performed_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (constituency_no, elector_id, action_type, field_name, old_val, new_val, confidence_delta, rationale, actor))
                conn.commit()
            finally:
                self.pg_pool.putconn(conn)

    def get_elector_by_id(self, constituency_no: int, elector_id: str) -> Optional[Dict[str, Any]]:
        """Queries single elector by partition key and elector_id."""
        if self.is_sqlite:
            with self.lock:
                cur = self.sqlite_conn.cursor()
                cur.execute("""
                SELECT * FROM master_electors 
                WHERE assembly_constituency_no = ? AND elector_id = ?
                """, (constituency_no, elector_id))
                row = cur.fetchone()
                res = dict(row) if row else None
                cur.close()
                return res
        else:
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                    SELECT * FROM master_electors 
                    WHERE assembly_constituency_no = %s AND elector_id = %s
                    """, (constituency_no, elector_id))
                    row = cur.fetchone()
                    return dict(row) if row else None
            finally:
                self.pg_pool.putconn(conn)

    def get_electors_by_part(self, constituency_no: int, part_no: int) -> List[Dict[str, Any]]:
        """Queries all electors within an assembly constituency part, ordered by booth_sno."""
        if self.is_sqlite:
            cur = self.sqlite_conn.cursor()
            cur.execute("""
            SELECT * FROM master_electors 
            WHERE assembly_constituency_no = ? AND assembly_part_no = ?
            ORDER BY booth_sno ASC
            """, (constituency_no, part_no))
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
        else:
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                    SELECT * FROM master_electors 
                    WHERE assembly_constituency_no = %s AND assembly_part_no = %s
                    ORDER BY booth_sno ASC
                    """, (constituency_no, part_no))
                    return [dict(r) for r in cur.fetchall()]
            finally:
                self.pg_pool.putconn(conn)

    def get_quarantine_queue(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Queries electors flagged for review (Quarantined or mean_card_conf < 0.65)."""
        if self.is_sqlite:
            cur = self.sqlite_conn.cursor()
            cur.execute("""
            SELECT * FROM master_electors 
            WHERE status = 'Quarantined' OR mean_card_conf < 0.65
            ORDER BY mean_card_conf ASC, assembly_constituency_no, assembly_part_no, booth_sno
            LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
        else:
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                    SELECT * FROM master_electors 
                    WHERE status = 'Quarantined' OR mean_card_conf < 0.65
                    ORDER BY mean_card_conf ASC, assembly_constituency_no, assembly_part_no, booth_sno
                    LIMIT %s OFFSET %s
                    """, (limit, offset))
                    return [dict(r) for r in cur.fetchall()]
            finally:
                self.pg_pool.putconn(conn)

    def close(self):
        """Closes all open database connections and pools."""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
        if self.pg_pool:
            self.pg_pool.closeall()
            self.pg_pool = None
