"""
INEI SMART-CORE - Database Migration Script
Phase 8.1: SmartTeacher AI - Flexible Pedagogical Document Generator & Preferences Schema
Creates smartteacher_teacher_preferences table to persist teacher format preferences,
custom templates, and default pedagogical settings.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, List

logger = logging.getLogger("inei_smart_core.migration_phase8_1")

def migrate_phase8_1_flexible_documents(db_path: str) -> Dict[str, Any]:
    """
    Applies reversible schema evolution to support Teacher Preferences and Custom Templates.
    Idempotent and safe for SQLite.
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

        # Check if migration version '8.1_flexible_documents' was already applied
        mig_row = cursor.execute(
            "SELECT version, applied_at FROM schema_migrations WHERE version = '8.1_flexible_documents'"
        ).fetchone()
        if mig_row:
            return {
                "success": True,
                "db_path": db_path,
                "already_applied": True,
                "applied_changes": [],
                "message": f"Migration '8.1_flexible_documents' already applied at {mig_row[1]}."
            }

        # 1. Create smartteacher_teacher_preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smartteacher_teacher_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                teacher_id INTEGER,
                preferred_specialty TEXT,
                preferred_grade INTEGER DEFAULT 5,
                include_5s_safety INTEGER DEFAULT 1,
                include_visual_placeholders INTEGER DEFAULT 1,
                include_teacher_key INTEGER DEFAULT 1,
                evaluation_style TEXT DEFAULT 'vigesimal',
                custom_sections_json TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        """)
        applied_changes.append("CREATE TABLE smartteacher_teacher_preferences")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_pref_user ON smartteacher_teacher_preferences(user_id)")
        applied_changes.append("CREATE INDEX idx_st_pref_user")

        # Record migration version
        cursor.execute("""
            INSERT INTO schema_migrations (version, description, applied_at)
            VALUES ('8.1_flexible_documents', 'SmartTeacher Flexible Pedagogical Documents and Teacher Preferences Schema', CURRENT_TIMESTAMP)
        """)
        applied_changes.append("INSERT INTO schema_migrations version 8.1_flexible_documents")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "already_applied": False,
            "applied_changes": applied_changes,
            "message": "Migration 8.1_flexible_documents applied successfully."
        }
    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        logger.error(f"Error applying migration 8.1_flexible_documents: {e}")
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e)
        }
    finally:
        conn.close()


def rollback_phase8_1_flexible_documents(db_path: str) -> Dict[str, Any]:
    """
    Safely rolls back the Phase 8.1 schema additions.
    Drops smartteacher_teacher_preferences table and unregisters the migration record.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("DROP TABLE IF EXISTS smartteacher_teacher_preferences")
        cursor.execute("DELETE FROM schema_migrations WHERE version = '8.1_flexible_documents'")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "message": "Rollback of migration 8.1_flexible_documents executed successfully."
        }
    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        logger.error(f"Error executing rollback 8.1_flexible_documents: {e}")
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e)
        }
    finally:
        conn.close()
