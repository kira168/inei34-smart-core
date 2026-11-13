"""
INEI SMART-CORE - Database Migration Script
Phase 8.7: SmartTeacher AI - Real Institutional Templates Library (CET N.º 34)
Integrates and pre-seeds the 6 authentic institutional templates:
1. Sesión Técnica de Taller (GTZ - Acción Completa - 5h)
2. Sesión de Emprendimiento (Lean Canvas / Design Thinking - 3h)
3. Unidad Didáctica Oficial (CET N.º 34)
4. Ficha de Trabajo del Estudiante (CET N.º 34)
5. Examen o Práctica Calificada (CET N.º 34)
6. Presentación PowerPoint Oficial (7 Diapositivas - CET N.º 34)
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List

logger = logging.getLogger("inei_smart_core.migration_phase8_7")

INSTITUTIONAL_TEMPLATES_SPECS = [
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
    },
    {
        "name": "Ficha de Trabajo del Estudiante — CET N° 34",
        "doc_type": "ficha_trabajo",
        "description": "Ficha institucional de aprendizaje para el estudiante con membrete oficial del C.E.T. N° 34, propósito, reto motivador, marco teórico breve, actividades prácticas guiadas con líneas y lista de cotejo.",
        "filename": "ficha_trabajo_estudiante_cet34.docx",
        "is_institutional": 1
    },
    {
        "name": "Examen o Práctica Calificada — CET N° 34",
        "doc_type": "examen_tecnico",
        "description": "Examen institucional con membrete oficial del C.E.T. N° 34, Sección A (alternativas múltiples con casillas ☐), Sección B (desarrollo y análisis con líneas) y Sección C (Verdadero/Falso). Incluye versión estudiante y solucionario docente justificado.",
        "filename": "examen_practica_cet34.docx",
        "is_institutional": 1
    },
    {
        "name": "Presentación PowerPoint Oficial (7 Diapositivas) — CET N° 34",
        "doc_type": "presentacion_pptx",
        "description": "Presentación institucional de 7 diapositivas con membrete CET N° 34, portada temática, propósito y reto, diagrama conceptual de 9 bloques, caso práctico, herramientas de validación, reto dinámico y metacognición.",
        "filename": "presentacion_leancanvas_cet34.pptx",
        "is_institutional": 1
    }
]

def migrate_phase8_7_institutional_templates(db_path: str) -> Dict[str, Any]:
    """
    Applies schema evolution to support all 6 institutional templates of CET N.º 34.
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

        # Check if migration version '8.7_institutional_templates' was already applied
        mig_row = cursor.execute(
            "SELECT version, applied_at FROM schema_migrations WHERE version = '8.7_institutional_templates'"
        ).fetchone()
        if mig_row:
            return {
                "success": True,
                "db_path": db_path,
                "already_applied": True,
                "applied_changes": [],
                "message": f"Migration '8.7_institutional_templates' already applied at {mig_row[1]}."
            }

        # 1. Create smartteacher_templates table if not exists
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
        applied_changes.append("VERIFY TABLE smartteacher_templates")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_user ON smartteacher_templates(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_type ON smartteacher_templates(doc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_inst ON smartteacher_templates(is_institutional)")
        applied_changes.append("CREATE INDEXES on smartteacher_templates")

        # 2. Pre-seed or Update all 6 Institutional Templates
        templates_dir = os.path.abspath("data/templates/smartteacher")

        from app.ai.template_engine import template_engine

        for tpl in INSTITUTIONAL_TEMPLATES_SPECS:
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

            # Check if template already exists by filename and is_institutional
            existing = cursor.execute(
                "SELECT id FROM smartteacher_templates WHERE filename = ? AND is_institutional = 1",
                (tpl["filename"],)
            ).fetchone()

            if existing:
                cursor.execute("""
                    UPDATE smartteacher_templates
                    SET name = ?, doc_type = ?, description = ?, file_path = ?,
                        file_bytes = ?, blueprint_json = ?, fields_json = ?, styles_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    tpl["name"],
                    tpl["doc_type"],
                    tpl["description"],
                    f_path if os.path.exists(f_path) else None,
                    f_bytes,
                    bp_json,
                    fields_json,
                    styles_json,
                    existing[0]
                ))
                applied_changes.append(f"UPDATE TEMPLATE: {tpl['name']}")
            else:
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
                applied_changes.append(f"INSERT TEMPLATE: {tpl['name']}")

        # 3. Record migration version
        cursor.execute("""
            INSERT INTO schema_migrations (version, description, applied_at)
            VALUES ('8.7_institutional_templates', 'Phase 8.7: SmartTeacher Real Institutional Templates Integration CET N.º 34', CURRENT_TIMESTAMP)
        """)
        applied_changes.append("RECORD MIGRATION 8.7_institutional_templates")

        cursor.execute("COMMIT")
        return {
            "success": True,
            "db_path": db_path,
            "already_applied": False,
            "applied_changes": applied_changes,
            "message": f"Successfully applied {len(applied_changes)} changes for Phase 8.7."
        }

    except Exception as e:
        cursor.execute("ROLLBACK")
        logger.error(f"Migration phase 8.7 failed: {e}", exc_info=True)
        return {
            "success": False,
            "db_path": db_path,
            "error": str(e),
            "applied_changes": []
        }
    finally:
        conn.close()
