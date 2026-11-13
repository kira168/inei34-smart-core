"""
INEI SMART-CORE - Database Migration Script
Phase 8.0: SmartTeacher AI Didactic Units and Cascading Planning Schema
Creates smartteacher_didactic_units table and adds cascading foreign keys.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, List

logger = logging.getLogger("inei_smart_core.migration_phase8_0")

def get_columns_in_table(cursor: sqlite3.Cursor, table_name: str) -> set:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}

def migrate_phase8_0_didactic_units(db_path: str) -> Dict[str, Any]:
    """
    Applies reversible schema evolution to support Didactic Units and Cascading Planning.
    Creates smartteacher_didactic_units and adds unit_id / session_id linkage columns
    to smartteacher_documents if not already present.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    applied_changes: List[str] = []

    try:
        cursor.execute("BEGIN TRANSACTION")

        # 0. Ensure schema_migrations table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check if migration version '8.0_didactic_units' was already applied
        mig_row = cursor.execute(
            "SELECT version, applied_at FROM schema_migrations WHERE version = '8.0_didactic_units'"
        ).fetchone()
        if mig_row:
            return {
                "success": True,
                "db_path": db_path,
                "already_applied": True,
                "applied_changes": [],
                "message": f"Migration '8.0_didactic_units' already applied at {mig_row[1]}."
            }

        # 1. Create smartteacher_didactic_units table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smartteacher_didactic_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                course_id INTEGER,
                title TEXT NOT NULL,
                academic_year TEXT DEFAULT '2026',
                bimester TEXT DEFAULT 'IV Bimestre',
                unit_number INTEGER DEFAULT 4,
                specialty TEXT NOT NULL,
                formative_module TEXT,
                grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 5),
                section_name TEXT DEFAULT 'A',
                responsible_teacher TEXT NOT NULL,
                director_name TEXT DEFAULT 'Tomas Jurado Zevallos',
                subdirector_name TEXT DEFAULT 'Mg. Javier Eulogio Rosas Maguiña',
                workshop_boss_name TEXT,
                start_date TEXT,
                end_date TEXT,
                duration_weeks INTEGER DEFAULT 9,
                weekly_hours INTEGER DEFAULT 8,
                total_hours INTEGER DEFAULT 72,
                unit_description TEXT,
                technical_matrix_json TEXT,
                entrepreneurship_matrix_json TEXT,
                technical_purposes_json TEXT,
                entrepreneurship_purposes_json TEXT,
                sessions_plan_json TEXT NOT NULL,
                bibliography_json TEXT,
                signatures_json TEXT,
                content_markdown TEXT,
                content_json TEXT NOT NULL,
                status TEXT DEFAULT 'BORRADOR' CHECK(status IN ('BORRADOR', 'REVISADO', 'APROBADO', 'ARCHIVADO')),
                version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
            )
        """)
        applied_changes.append("CREATE TABLE smartteacher_didactic_units")

        # Create indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_teacher ON smartteacher_didactic_units(teacher_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_user ON smartteacher_didactic_units(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_spec_grade ON smartteacher_didactic_units(specialty, grade)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_created ON smartteacher_didactic_units(created_at)")
        applied_changes.append("CREATE INDEXES on smartteacher_didactic_units")

        # 2. Add unit_id and session_id columns to smartteacher_documents if they don't exist
        doc_cols = get_columns_in_table(cursor, "smartteacher_documents")
        if "unit_id" not in doc_cols:
            cursor.execute("""
                ALTER TABLE smartteacher_documents
                ADD COLUMN unit_id INTEGER REFERENCES smartteacher_didactic_units(id) ON DELETE SET NULL
            """)
            applied_changes.append("ALTER TABLE smartteacher_documents ADD COLUMN unit_id")

        if "session_id" not in doc_cols:
            cursor.execute("""
                ALTER TABLE smartteacher_documents
                ADD COLUMN session_id INTEGER REFERENCES smartteacher_documents(id) ON DELETE SET NULL
            """)
            applied_changes.append("ALTER TABLE smartteacher_documents ADD COLUMN session_id")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_unit_id ON smartteacher_documents(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_session_id ON smartteacher_documents(session_id)")
        applied_changes.append("CREATE INDEXES on smartteacher_documents foreign keys")

        # Record migration version
        cursor.execute("""
            INSERT INTO schema_migrations (version, description, applied_at)
            VALUES ('8.0_didactic_units', 'SmartTeacher Didactic Units and Cascading Planning Schema', CURRENT_TIMESTAMP)
        """)
        applied_changes.append("INSERT INTO schema_migrations version 8.0_didactic_units")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "already_applied": False,
            "applied_changes": applied_changes,
            "message": "Migration 8.0_didactic_units applied successfully."
        }
    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        logger.error(f"Error applying migration 8.0_didactic_units: {e}")
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e)
        }
    finally:
        conn.close()

def rollback_phase8_0_didactic_units(db_path: str) -> Dict[str, Any]:
    """
    Rolls back migration 8.0_didactic_units reversibly.
    Drops indexes, drops smartteacher_didactic_units table, removes added columns if supported,
    and removes record from schema_migrations.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    cursor = conn.cursor()

    applied_rollbacks: List[str] = []

    try:
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_st_docs_unit_id")
        cursor.execute("DROP INDEX IF EXISTS idx_st_docs_session_id")
        cursor.execute("DROP INDEX IF EXISTS idx_st_units_created")
        cursor.execute("DROP INDEX IF EXISTS idx_st_units_spec_grade")
        cursor.execute("DROP INDEX IF EXISTS idx_st_units_user")
        cursor.execute("DROP INDEX IF EXISTS idx_st_units_teacher")
        applied_rollbacks.append("DROP INDEXES")

        # Drop smartteacher_didactic_units table
        cursor.execute("DROP TABLE IF EXISTS smartteacher_didactic_units")
        applied_rollbacks.append("DROP TABLE smartteacher_didactic_units")

        # Drop columns from smartteacher_documents if present (SQLite >= 3.35.0)
        doc_cols = get_columns_in_table(cursor, "smartteacher_documents")
        if "unit_id" in doc_cols:
            cursor.execute("ALTER TABLE smartteacher_documents DROP COLUMN unit_id")
            applied_rollbacks.append("DROP COLUMN unit_id")
        if "session_id" in doc_cols:
            cursor.execute("ALTER TABLE smartteacher_documents DROP COLUMN session_id")
            applied_rollbacks.append("DROP COLUMN session_id")

        # Remove from schema_migrations
        cursor.execute("DELETE FROM schema_migrations WHERE version = '8.0_didactic_units'")
        applied_rollbacks.append("DELETE FROM schema_migrations")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "applied_rollbacks": applied_rollbacks,
            "message": "Rollback 8.0_didactic_units completed successfully."
        }
    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        logger.error(f"Error rolling back 8.0_didactic_units: {e}")
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e)
        }
    finally:
        conn.close()
