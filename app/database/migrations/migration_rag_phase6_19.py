"""
INEI SMART-CORE - Database Migration Script
Phase 6.19: Institutional Knowledge Base RAG Partition & Security Hardening
Applies non-destructive schema extensions to knowledge_documents table.
"""

import os
import sqlite3
import logging
from typing import Dict, Any

logger = logging.getLogger("inei_smart_core.migration_rag")

def get_columns_in_table(cursor: sqlite3.Cursor, table_name: str) -> set:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}

def migrate_rag_schema(db_path: str) -> Dict[str, Any]:
    """
    Applies non-destructive schema evolution to knowledge_documents table in the specified database.
    Does NOT touch production unless db_path points to it.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    applied_changes = []

    try:
        cursor.execute("BEGIN TRANSACTION")

        # 0. Ensure schema_migrations table exists for version control
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check if migration version '6.19_rag_partition' was already applied
        mig_row = cursor.execute(
            "SELECT version, applied_at FROM schema_migrations WHERE version = '6.19_rag_partition'"
        ).fetchone()
        if mig_row:
            return {
                "success": True,
                "db_path": db_path,
                "already_applied": True,
                "applied_changes": [],
                "message": f"Migration '6.19_rag_partition' is already applied (applied_at: {mig_row[1]}). No changes performed."
            }

        existing_cols = get_columns_in_table(cursor, "knowledge_documents")

        # 1. Add collection_id column
        if "collection_id" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN collection_id TEXT NOT NULL DEFAULT 'smarttutor' 
                CHECK(collection_id IN ('smarttutor', 'smartteacher', 'compartido'))
            """)
            applied_changes.append("ADD COLUMN collection_id")

        # 2. Add grade_level column
        if "grade_level" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN grade_level INTEGER 
                CHECK(grade_level BETWEEN 1 AND 5 OR grade_level IS NULL)
            """)
            applied_changes.append("ADD COLUMN grade_level")

        # 3. Add technical_specialty column
        if "technical_specialty" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN technical_specialty TEXT
            """)
            applied_changes.append("ADD COLUMN technical_specialty")

        # 4. Add material_type column
        if "material_type" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN material_type TEXT NOT NULL DEFAULT 'teoria' 
                CHECK(material_type IN ('teoria', 'ejercicio_resuelto', 'banco_admision', 'sesion_formato', 'ficha_taller', 'examen_balotario', 'rubrica', 'normativa_institucional', 'guia_docente'))
            """)
            applied_changes.append("ADD COLUMN material_type")

        # 5. Add version column
        if "version" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN version INTEGER NOT NULL DEFAULT 1 
                CHECK(version >= 1)
            """)
            applied_changes.append("ADD COLUMN version")

        # 6. Add indexing_status column
        if "indexing_status" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN indexing_status TEXT NOT NULL DEFAULT 'activo' 
                CHECK(indexing_status IN ('pendiente', 'procesando', 'activo', 'error', 'desactivado'))
            """)
            applied_changes.append("ADD COLUMN indexing_status")

        # 7. Add security_review_status column
        if "security_review_status" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN security_review_status TEXT NOT NULL DEFAULT 'en_revision' 
                CHECK(security_review_status IN ('aprobado', 'en_revision', 'cuarentena_sensible', 'rechazado'))
            """)
            applied_changes.append("ADD COLUMN security_review_status")

        # 8. Add error_message column
        if "error_message" not in existing_cols:
            cursor.execute("""
                ALTER TABLE knowledge_documents 
                ADD COLUMN error_message TEXT
            """)
            applied_changes.append("ADD COLUMN error_message")

        # 9. Synchronize status coherence ONLY for existing unmigrated rows
        # Strictly preserves pre-existing valid states ('error', 'pendiente', 'procesando')
        cursor.execute("""
            UPDATE knowledge_documents 
            SET indexing_status = 'desactivado' 
            WHERE is_active = 0 AND (indexing_status NOT IN ('error', 'pendiente', 'procesando', 'desactivado') OR indexing_status IS NULL)
        """)
        cursor.execute("""
            UPDATE knowledge_documents 
            SET indexing_status = 'activo' 
            WHERE is_active = 1 AND (indexing_status NOT IN ('error', 'pendiente', 'procesando', 'activo') OR indexing_status IS NULL)
        """)

        # 10. Handle sensitive Document ID 802: Quarantine strictly without activating
        cursor.execute("""
            UPDATE knowledge_documents 
            SET collection_id = 'smartteacher',
                material_type = 'examen_balotario',
                role_access = 'DOCENTE',
                indexing_status = 'activo',
                security_review_status = 'cuarentena_sensible',
                is_active = 0
            WHERE id = 802
        """)

        # 11. Create performance & security gating indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_rag_gate ON knowledge_documents(is_active, indexing_status, security_review_status, collection_id, role_access)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_coll_subject ON knowledge_documents(collection_id, subject_id)")

        # 12. Record versioned migration into schema_migrations
        cursor.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES ('6.19_rag_partition', 'Phase 6.19: Institutional Knowledge Base RAG Partition & Security Hardening')
        """)

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "already_applied": False,
            "applied_changes": applied_changes,
            "message": "Migration completed successfully."
        }
    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e)
        }
    finally:
        conn.close()

def rollback_rag_schema(db_path: str) -> Dict[str, Any]:
    """
    Rolls back the migration on the specified database by dropping indexes and newly added columns.
    Ensures foreign keys and FTS5 triggers remain valid.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN TRANSACTION")

        # Disable foreign keys during DDL manipulation
        cursor.execute("PRAGMA foreign_keys = OFF")

        # 1. Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_kdocs_rag_gate")
        cursor.execute("DROP INDEX IF EXISTS idx_kdocs_coll_subject")

        # 2. Drop added columns (Supported in SQLite >= 3.35.0)
        existing_cols = get_columns_in_table(cursor, "knowledge_documents")
        cols_to_drop = [
            "error_message",
            "security_review_status",
            "indexing_status",
            "version",
            "material_type",
            "technical_specialty",
            "grade_level",
            "collection_id"
        ]

        dropped = []
        for col in cols_to_drop:
            if col in existing_cols:
                cursor.execute(f"ALTER TABLE knowledge_documents DROP COLUMN {col}")
                dropped.append(col)

        # 3. Restore foreign keys & verify integrity
        cursor.execute("PRAGMA foreign_keys = ON")
        fk_violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
        if fk_violations:
            raise RuntimeError(f"Foreign key violations detected after rollback: {fk_violations}")

        # 4. Remove version from schema_migrations
        cursor.execute("DELETE FROM schema_migrations WHERE version = '6.19_rag_partition'")

        # 5. Check FTS5 virtual table integrity
        cursor.execute("INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts) VALUES('integrity-check')")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "dropped_columns": dropped,
            "message": "Rollback completed cleanly. FK and FTS5 integrity verified."
        }
    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e)
        }
    finally:
        conn.close()
