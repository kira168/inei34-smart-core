"""
INEI SMART-CORE - Database Migration Script
Phase 8.6: SmartTeacher AI - Document Templates Library Schema & Institutional Pre-seeding
Creates smartteacher_templates table to persist reusable pedagogical document templates
(Word, PDF, TXT) and pre-seeds the official institutional templates from CET N.º 34.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List

logger = logging.getLogger("inei_smart_core.migration_phase8_6")

def migrate_phase8_6_document_templates(db_path: str) -> Dict[str, Any]:
    """
    Applies schema evolution to support the Template Library.
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

        # Check if migration version '8.6_document_templates' was already applied
        mig_row = cursor.execute(
            "SELECT version, applied_at FROM schema_migrations WHERE version = '8.6_document_templates'"
        ).fetchone()
        if mig_row:
            return {
                "success": True,
                "db_path": db_path,
                "already_applied": True,
                "applied_changes": [],
                "message": f"Migration '8.6_document_templates' already applied at {mig_row[1]}."
            }

        # 1. Create smartteacher_templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smartteacher_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                teacher_id INTEGER,
                name TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                description TEXT,
                filename TEXT NOT NULL,
                file_path TEXT,
                file_bytes BLOB,
                blueprint_json TEXT,
                fields_json TEXT,
                styles_json TEXT,
                is_institutional INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
            )
        """)
        applied_changes.append("CREATE TABLE smartteacher_templates")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_user ON smartteacher_templates(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_type ON smartteacher_templates(doc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_inst ON smartteacher_templates(is_institutional)")
        applied_changes.append("CREATE INDEXES on smartteacher_templates")

        # 2. Pre-seed Institutional Templates from CET N.º 34
        templates_dir = os.path.abspath("data/templates/smartteacher")
        inst_templates = [
            {
                "name": "Sesión Técnica de Taller (GTZ - 5h) — CET N° 34",
                "doc_type": "sesion_aprendizaje",
                "description": "Plantilla institucional para sesiones técnicas de taller con metodología de la Acción Completa (6 etapas GTZ). Incluye membrete oficial, tabla de metadatos y 3 firmas institucionales.",
                "filename": "sesion_tecnica_gtz_cet34.docx",
                "is_institutional": 1
            },
            {
                "name": "Sesión de Emprendimiento (Lean Canvas - 3h) — CET N° 34",
                "doc_type": "sesion_aprendizaje",
                "description": "Plantilla institucional para proyectos de emprendimiento escolar con metodología Design Thinking y validación de hipótesis en Lean Canvas (6 etapas).",
                "filename": "sesion_emprendimiento_leancanvas_cet34.docx",
                "is_institutional": 1
            },
            {
                "name": "Unidad Didáctica Oficial — CET N° 34",
                "doc_type": "unidad_didactica",
                "description": "Estructura institucional oficial para programación de unidades didácticas con matrices de habilidades técnicas y emprendimiento, propósitos y secuencia de sesiones.",
                "filename": "unidad_didactica_cet34.docx",
                "is_institutional": 1
            }
        ]

        from app.ai.template_engine import template_engine

        for tpl in inst_templates:
            f_path = os.path.join(templates_dir, tpl["filename"])
            f_bytes = None
            bp_json = None
            fields_json = None
            styles_json = None

            if os.path.exists(f_path):
                with open(f_path, "rb") as fp:
                    f_bytes = fp.read()
                try:
                    analysis = template_engine.analyze_template(f_bytes, tpl["filename"])
                    bp_json = json.dumps(analysis, ensure_ascii=False)
                    fields_json = json.dumps(analysis.get("editable_fields", []), ensure_ascii=False)
                    styles_json = json.dumps({
                        "margins": analysis.get("margins"),
                        "font_family": analysis.get("font_family"),
                        "orientation": analysis.get("orientation")
                    }, ensure_ascii=False)
                except Exception as ex:
                    logger.warning(f"Error analyzing template {tpl['filename']}: {ex}")

            cursor.execute("""
                INSERT INTO smartteacher_templates (
                    user_id, teacher_id, name, doc_type, description,
                    filename, file_path, file_bytes, blueprint_json, fields_json, styles_json,
                    is_institutional, created_at, updated_at
                )
                VALUES (NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                tpl["name"],
                tpl["doc_type"],
                tpl["description"],
                tpl["filename"],
                f_path if os.path.exists(f_path) else None,
                f_bytes,
                bp_json,
                fields_json,
                styles_json,
                tpl["is_institutional"]
            ))
            applied_changes.append(f"PRE-SEED TEMPLATE: {tpl['name']}")

        # 3. Record migration version
        cursor.execute("""
            INSERT INTO schema_migrations (version, description, applied_at)
            VALUES ('8.6_document_templates', 'Phase 8.6: SmartTeacher Document Templates Library Schema & Institutional Pre-seeding', CURRENT_TIMESTAMP)
        """)
        applied_changes.append("RECORD MIGRATION 8.6_document_templates")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "already_applied": False,
            "applied_changes": applied_changes,
            "message": f"Successfully applied {len(applied_changes)} changes for Phase 8.6."
        }

    except Exception as e:
        cursor.execute("ROLLBACK")
        logger.error(f"Migration phase 8.6 failed: {e}", exc_info=True)
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e),
            "applied_changes": []
        }
    finally:
        conn.close()
