"""
INEI SMART-CORE - Document Template Engine
SmartTeacher AI - Fase 8.7: Motor Inteligente de Plantillas Institucionales Reales
I.E. INEI N.º 34 de Chancay - CET N.º 34

Permite a SmartTeacher AI:
1. Ingerir y analizar documentos modelo institucionales (.docx, .pptx, .pdf, .txt).
2. Extraer estructura pedagógica, apartados, tablas, estilos, márgenes y campos editables.
3. Clonar y rellenar documentos Word (.docx) y presentaciones PowerPoint (.pptx)
   preservando encabezados, logotipos, márgenes, tipografías, anchos de tabla, celdas
   y firmas institucionales sin deformar el formato.
4. Generar:
   - Sesiones Técnicas GTZ (5h) y de Emprendimiento Lean Canvas (3h)
   - Unidades Didácticas Oficiales CET N.º 34
   - Fichas de Trabajo del Estudiante (2 caras)
   - Exámenes Técnicos / Prácticas Calificadas (Versión Estudiante vs. Solucionario Docente)
   - Presentaciones PowerPoint Institucionales (7 diapositivas con membrete CET N.º 34)
"""

import io
import os
import re
import copy
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

try:
    import pptx
    from pptx import Presentation
    from pptx.util import Inches as PptxInches, Pt as PptxPt
    from pptx.dml.color import RGBColor as PptxRGBColor
    from pptx.enum.text import PP_ALIGN as PptxPPAlign, MSO_ANCHOR as PptxMSOAnchor, MSO_AUTO_SIZE
    from pptx.enum.shapes import MSO_SHAPE as PptxMSOShape
except ImportError:
    pptx = None
    Presentation = None
    PptxPt = None
    MSO_AUTO_SIZE = None

from app.ai.document_processor import document_processor
from app.ai.diagram_generator import DiagramGenerator

logger = logging.getLogger("inei_smart_core.template_engine")

# Directorio de plantillas oficiales del sistema
TEMPLATES_STORAGE_DIR = os.path.abspath("data/templates/smartteacher")
os.makedirs(TEMPLATES_STORAGE_DIR, exist_ok=True)


class DocumentTemplateEngine:
    """
    Motor centralizado de análisis y generación de documentos basados en plantillas reales.
    """

    @classmethod
    def analyze_template(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Analiza un archivo de referencia y extrae su blueprint estructural, tipología documental,
        tablas, márgenes, estilos y lista de campos editables.
        """
        # Asegurar extensión válida si no viene en el filename
        if "." not in filename:
            if file_bytes.startswith(b"PK\x03\x04") and any(k in filename.lower() for k in ["ppt", "presentacion", "slides", "canvas"]):
                filename = filename + ".pptx"
            elif file_bytes.startswith(b"PK\x03\x04"):
                filename = filename + ".docx"
            elif file_bytes.startswith(b"%PDF"):
                filename = filename + ".pdf"
            else:
                filename = filename + ".txt"

        name_lower = filename.lower()

        # Soporte para presentaciones PowerPoint (.pptx)
        if name_lower.endswith(".pptx") or "presentacion" in name_lower or "diapositiva" in name_lower:
            total_slides = 7
            slide_titles = []
            if pptx is not None:
                try:
                    prs = pptx.Presentation(io.BytesIO(file_bytes))
                    total_slides = len(prs.slides)
                    for s in prs.slides:
                        for shape in s.shapes:
                            if shape.has_text_frame and shape.text.strip():
                                slide_titles.append(shape.text.strip().split("\n")[0][:40])
                                break
                except Exception as ex:
                    logger.warning(f"Error inspecting PPTX: {ex}")

            return {
                "success": True,
                "filename": filename,
                "file_type": "pptx",
                "doc_type": "presentacion_pptx",
                "total_slides": total_slides,
                "sections": slide_titles or [f"Diapositiva {i+1}" for i in range(total_slides)],
                "tables": [],
                "has_rubric": True,
                "has_student_box": False,
                "margins": {"orientation": "landscape"},
                "orientation": "landscape",
                "font_family": "Calibri",
                "header_text": "INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY",
                "footer_text": "Educación para el Trabajo",
                "editable_fields": [
                    {"key": "topic", "label": "Tema Central de la Presentación", "type": "text", "required": True},
                    {"key": "grade", "label": "Grado de Secundaria (1.° a 5.°)", "type": "number", "default": 5, "required": True},
                    {"key": "specialty", "label": "Especialidad / Área Curricular", "type": "text", "default": "Computación e Informática", "required": True},
                    {"key": "purpose", "label": "Propósito de la Sesión (Opcional)", "type": "textarea", "required": False}
                ],
                "preserved_elements": [
                    f"Presentación interactiva oficial CET N.º 34 ({total_slides} diapositivas)",
                    "Plantilla y membrete institucional de la I.E. INEI N.º 34",
                    "Paleta cromática oficial (Azul noche, ámbar, blanco y gris técnico)",
                    "Tarjetas conceptuales, cuadrantes de herramientas e iconos integrados",
                    "Estructura pedagógica: Portada, Propósito/Reto, Marco Conceptual, Caso, Herramientas, Dinámica y Cierre"
                ],
                "total_sections_found": total_slides,
                "total_tables_found": 0
            }

        bp = document_processor.extract_reference_model_blueprint(file_bytes, filename)
        if not bp.get("success"):
            return bp

        fmt_type = bp.get("file_type", "docx")
        sections = bp.get("sections", [])
        tables_info = bp.get("tables", [])
        has_rubric = bp.get("has_rubric", False)
        has_student_box = bp.get("has_student_box", False)

        # 1. Inferir tipo de documento
        sec_text = " ".join(sections).lower()
        doc_type = "ficha_guia"

        if any(k in name_lower or k in sec_text for k in ["unidad didáctica", "unidad didactica", "matriz curricular"]):
            doc_type = "unidad_didactica"
        elif any(k in name_lower or k in sec_text for k in ["sesión de aprendizaje", "sesion de aprendizaje", "procesos didácticos", "procesos didacticos", "pasos o etapas", "proceso didáctico", "etapa gtz"]):
            doc_type = "sesion_aprendizaje"
        elif any(k in name_lower or k in sec_text for k in ["examen técnico", "examen tecnico", "examen_practica", "prueba escrita", "cuestionario de examen", "solucionario"]):
            doc_type = "examen_tecnico"
        elif any(k in name_lower or k in sec_text for k in ["rúbrica analítica", "rubrica analitica"]):
            doc_type = "rubrica_evaluacion"
        elif has_student_box or any(k in name_lower or k in sec_text for k in ["ficha de trabajo", "ficha_trabajo", "ficha de actividad", "hoja de operaciones", "guía práctica", "guia practica", "ficha"]):
            doc_type = "ficha_trabajo"

        # 2. Extraer propiedades físicas si es DOCX
        margins_info = {"top": 0.8, "bottom": 0.8, "left": 0.85, "right": 0.85}
        orientation = "portrait"
        font_family = "Calibri"
        header_text = ""
        footer_text = ""

        if fmt_type == "docx":
            try:
                doc = Document(io.BytesIO(file_bytes))
                if doc.sections:
                    s0 = doc.sections[0]
                    margins_info = {
                        "top": round(s0.top_margin.inches, 2) if s0.top_margin else 0.8,
                        "bottom": round(s0.bottom_margin.inches, 2) if s0.bottom_margin else 0.8,
                        "left": round(s0.left_margin.inches, 2) if s0.left_margin else 0.85,
                        "right": round(s0.right_margin.inches, 2) if s0.right_margin else 0.85,
                        "page_width": round(s0.page_width.inches, 2) if s0.page_width else 8.27,
                        "page_height": round(s0.page_height.inches, 2) if s0.page_height else 11.69
                    }
                    if s0.page_width and s0.page_height and s0.page_width > s0.page_height:
                        orientation = "landscape"

                    # Header/Footer inspect
                    if s0.header and s0.header.paragraphs:
                        h_texts = [p.text.strip() for p in s0.header.paragraphs if p.text.strip()]
                        if h_texts:
                            header_text = " | ".join(h_texts)
                    if s0.footer and s0.footer.paragraphs:
                        f_texts = [p.text.strip() for p in s0.footer.paragraphs if p.text.strip()]
                        if f_texts:
                            footer_text = " | ".join(f_texts)

                # Detect default font
                for p in doc.paragraphs[:10]:
                    if p.runs and p.runs[0].font.name:
                        font_family = p.runs[0].font.name
                        break
            except Exception as e:
                logger.warning(f"Error inspecting DOCX physical attributes: {e}")

        # 3. Detectar campos editables sugeridos
        editable_fields = [
            {"key": "topic", "label": "Tema Central", "type": "text", "required": True},
            {"key": "grade", "label": "Grado de Secundaria (1.° a 5.°)", "type": "number", "required": True},
            {"key": "specialty", "label": "Especialidad / Área Curricular", "type": "text", "required": True},
            {"key": "purpose", "label": "Propósito de Aprendizaje", "type": "textarea", "required": False},
        ]

        if doc_type == "sesion_aprendizaje":
            editable_fields.extend([
                {"key": "duration_minutes", "label": "Duración en Minutos (ej. 225 o 135)", "type": "number", "default": 225},
                {"key": "session_type", "label": "Enfoque Metodológico (tecnica GTZ / emprendimiento Lean Canvas)", "type": "select", "options": ["tecnica", "emprendimiento"]},
                {"key": "formative_module", "label": "Módulo Formativo", "type": "text", "required": False},
                {"key": "section_name", "label": "Sección (A, B, C...)", "type": "text", "default": "A"}
            ])
        elif doc_type == "examen_tecnico":
            editable_fields.extend([
                {"key": "include_teacher_key", "label": "Incluir Solucionario Docente", "type": "boolean", "default": True},
                {"key": "section_name", "label": "Sección (A, B, C...)", "type": "text", "default": "A"}
            ])
        elif doc_type in ["ficha_trabajo", "ficha_guia", "practica_ejercicios"]:
            editable_fields.extend([
                {"key": "difficulty", "label": "Nivel de Dificultad", "type": "select", "options": ["inicial", "intermedio", "avanzado"], "default": "intermedio"},
                {"key": "include_rubric", "label": "Incluir Rúbrica / Lista de Cotejo", "type": "boolean", "default": True}
            ])

        # 4. Detectar elementos institucionales conservados
        preserved_elements = [
            "Márgenes, orientación y tamaño de página (A4 estricto)",
            "Jerarquía y familias tipográficas del documento original",
            "Estructura, bordes y anchos relativos de tablas",
            "Identidad institucional del CET N.º 34 (I.E. INEI N.º 34)",
            "Nombres y cargos de directivos institucionales oficiales"
        ]
        if has_student_box:
            preserved_elements.append("Recuadro normativo de identificación del estudiante")
        if has_rubric:
            preserved_elements.append("Cuadrícula y escala de niveles de logro (AD, A, B, C)")

        return {
            "success": True,
            "filename": bp.get("filename"),
            "file_type": fmt_type,
            "doc_type": doc_type,
            "sections": sections,
            "tables": tables_info,
            "has_rubric": has_rubric,
            "has_student_box": has_student_box,
            "margins": margins_info,
            "orientation": orientation,
            "font_family": font_family,
            "header_text": header_text,
            "footer_text": footer_text,
            "editable_fields": editable_fields,
            "preserved_elements": preserved_elements,
            "total_sections_found": len(sections),
            "total_tables_found": len(tables_info)
        }

    @classmethod
    def render_docx_from_template(
        cls,
        template_bytes: bytes,
        doc_data: Dict[str, Any]
    ) -> bytes:
        """
        Clona el archivo DOCX de plantilla y sustituye únicamente los campos y tablas necesarios,
        preservando el 100% de los encabezados, logotipos, márgenes, tipografías, bordes y tablas.
        """
        try:
            doc = Document(io.BytesIO(template_bytes))
        except Exception as e:
            logger.error(f"Error cargando DOCX de plantilla: {e}")
            from app.ai.document_exporter import generate_docx_bytes
            return generate_docx_bytes(doc_data)

        c_json_temp = doc_data.get("content_json") or {}
        if isinstance(c_json_temp, str):
            try:
                c_json_temp = json.loads(c_json_temp)
            except Exception:
                c_json_temp = {}
        doc_type = doc_data.get("doc_type") or c_json_temp.get("doc_type")
        if not doc_type:
            topic_hint = str(doc_data.get("topic") or doc_data.get("title") or "").lower()
            if "unidad" in topic_hint or "matriz_habilidades_tecnicas" in c_json_temp or "organizacion_sesiones" in c_json_temp:
                doc_type = "unidad_didactica"
            else:
                doc_type = "sesion_aprendizaje"

        if doc_type == "sesion_aprendizaje":
            cls._fill_session_docx_template(doc, doc_data)
        elif doc_type in ["unidad_didactica", "unidad_aprendizaje"]:
            cls._fill_unit_docx_template(doc, doc_data)
        elif doc_type in ["examen_tecnico", "examen", "practica_calificada", "practica_ejercicios", "practica"]:
            cls._fill_exam_docx_template(doc, doc_data)
        elif doc_type in ["ficha_trabajo", "ficha_actividad", "ficha_guia"]:
            cls._fill_student_worksheet_docx_template(doc, doc_data)
        else:
            cls._fill_generic_docx_template(doc, doc_data)

        # Incorporar estampilla de visado digital institucional si el documento fue aprobado
        c_json_doc = doc_data.get("content_json") or {}
        if isinstance(c_json_doc, str):
            try:
                c_json_doc = json.loads(c_json_doc)
            except Exception:
                c_json_doc = {}
        visa_info = doc_data.get("visado_digital") or c_json_doc.get("visado_digital")
        doc_status = doc_data.get("status") or (visa_info.get("status") if isinstance(visa_info, dict) else None)
        if visa_info and isinstance(visa_info, dict) and (doc_status == "APROBADO" or visa_info.get("status") == "APROBADO"):
            try:
                from app.ai.document_exporter import add_docx_digital_visa_stamp
                add_docx_digital_visa_stamp(doc, visa_info)
            except Exception as e:
                logger.warning(f"Error adjuntando estampilla de visado a plantilla DOCX: {e}")

        output_io = io.BytesIO()
        doc.save(output_io)
        return output_io.getvalue()

    # -------------------------------------------------------------
    # Rellenado de Sesiones de Aprendizaje (GTZ / Lean Canvas)
    # -------------------------------------------------------------
    @classmethod
    def _fill_session_docx_template(cls, doc: Document, data: Dict[str, Any]):
        """
        Rellena una plantilla de Sesión de Aprendizaje CET N.º 34 (ej. GTZ o Lean Canvas).
        """
        topic = data.get("topic") or data.get("title") or "Sesión de Aprendizaje"
        specialty = data.get("specialty") or "Educación para el Trabajo"
        grade = int(data.get("grade") or 5)
        grade_str = f"{grade}.° grado"
        section_name = data.get("section_name") or "A"
        duration_minutes = int(data.get("duration_minutes") or 225)
        teacher_name = data.get("teacher_name")
        is_verified_teacher, clean_teacher = cls.resolve_verified_teacher(teacher_name)

        c_json = data.get("content_json") or {}
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}

        propositos = c_json.get("propositos") or {}
        purpose_text = propositos.get("proposito_formativo") or data.get("purpose") or f"Desarrollar habilidades técnicas y operativas sobre {topic}."
        criteria_text = propositos.get("criterios_evaluacion") or f"Aplica destrezas técnicas en {topic} cumpliendo normas de seguridad y control de calidad."
        evidence_text = propositos.get("evidencia") or f"Ficha de operaciones y producto técnico de {topic} verificado."
        situacion_sig = c_json.get("situacion_significativa") or ""

        # 1. Actualizar Párrafo de Título Principal
        for p in doc.paragraphs[:5]:
            t_clean = p.text.strip()
            if any(k in t_clean.lower() for k in ["título:", "titulo:", "“", "gestionamos", "mejoramos"]):
                cls._set_p_text_preserving_runs(p, f'Título: "{topic}"')
                break

        # 2. Actualizar Tabla 1: Metadatos Informativos
        if len(doc.tables) >= 1:
            tbl_meta = doc.tables[0]
            clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "")
            for row in tbl_meta.rows:
                if len(row.cells) >= 2:
                    k_cell_text = row.cells[0].text.strip().lower()
                    val_idx = 2 if len(row.cells) >= 3 else 1

                    if "programa" in k_cell_text or "especialidad" in k_cell_text:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], clean_spec)
                    elif "módulo" in k_cell_text or "modulo" in k_cell_text:
                        mod_val = (
                            c_json.get("datos_generales_oficiales", {}).get("modulo_formativo")
                            or c_json.get("datos_generales", {}).get("modulo_formativo")
                            or f"Módulo formativo de {clean_spec}: {topic}"
                        )
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], mod_val)
                    elif "método" in k_cell_text or "metodo" in k_cell_text:
                        met_val = (
                            c_json.get("datos_generales_oficiales", {}).get("metodo_didactico")
                            or "Aprendizaje por la acción completa (GTZ)"
                        )
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], met_val)
                    elif "grado" in k_cell_text:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], f'{grade_str}: "{section_name}"')
                    elif "duración" in k_cell_text or "duracion" in k_cell_text:
                        dur_h = duration_minutes // 45
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], f"{dur_h} horas pedagógicas ({duration_minutes} minutos)")
                    elif "docente" in k_cell_text:
                        val_doc = clean_teacher if is_verified_teacher else "[Docente Responsable - Por completar]"
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], val_doc)

        # 3. Actualizar Párrafos del Cuerpo (Propósito, Criterios, Evidencia, Situación Significativa, Materiales)
        is_digital_topic = any(k in f"{topic} {clean_spec}".lower() for k in [
            "carpeta", "digital", "archivo", "ofimática", "computación", "informática", "nube", "web"
        ])
        for i, p in enumerate(doc.paragraphs):
            p_text = p.text.strip().upper()

            if "II." in p_text and ("PROPÓSITO" in p_text or "PROPOSITO" in p_text):
                if i + 1 < len(doc.paragraphs):
                    cls._set_p_text_preserving_runs(doc.paragraphs[i + 1], purpose_text)

            elif "III." in p_text and "CRITERIOS" in p_text:
                if i + 1 < len(doc.paragraphs):
                    cls._set_p_text_preserving_runs(doc.paragraphs[i + 1], criteria_text)

            elif "IV." in p_text and ("EVIDENCIAS" in p_text or "EVIDENCIA" in p_text):
                if i + 1 < len(doc.paragraphs):
                    cls._set_p_text_preserving_runs(doc.paragraphs[i + 1], evidence_text)

            elif "V." in p_text and "SITUACIÓN" in p_text and situacion_sig:
                if i + 1 < len(doc.paragraphs):
                    cls._set_p_text_preserving_runs(doc.paragraphs[i + 1], situacion_sig.strip())
                    for k_idx in range(i + 2, min(i + 7, len(doc.paragraphs))):
                        if k_idx < len(doc.paragraphs):
                            pk = doc.paragraphs[k_idx]
                            if "VI." in pk.text.upper() or "DESARROLLO" in pk.text.upper():
                                break
                            p_elem = pk._element
                            if p_elem.getparent() is not None and not p_elem.xpath('.//w:sectPr'):
                                p_elem.getparent().remove(p_elem)

            elif "VII." in p_text and "MATERIALES" in p_text:
                if is_digital_topic:
                    mat_list = [
                        "Computadora con conexión a red / internet",
                        "Plataforma de almacenamiento en la nube institucional",
                        "Proyector multimedia",
                        "Pizarra interactiva",
                        "Guías de práctica digital y fichas de aplicación",
                        "Recursos digitales de la especialidad"
                    ]
                else:
                    mat_list = [
                        "Torno paralelo y accesorios de torneado",
                        "Herramientas de corte (buriles HSS / plaquitas intercambiables)",
                        "Instrumentos de medición y verificación (calibre pie de rey, vernier)",
                        "Equipo de Protección Personal (mameluco, lentes de seguridad, calzado de seguridad)",
                        "Probeta de acero o material de trabajo para mecanizado",
                        "Guía técnica de operaciones de taller"
                    ]
                custom_mat = c_json.get("materiales_recursos") or c_json.get("materiales")
                if isinstance(custom_mat, list) and custom_mat:
                    mat_list = [str(m) for m in custom_mat]
                elif isinstance(custom_mat, str) and custom_mat.strip():
                    mat_list = [m.strip().lstrip("•-* ") for m in custom_mat.split("\n") if m.strip()]

                for m_idx, mat_item in enumerate(mat_list):
                    target_p_idx = i + 1 + m_idx
                    if target_p_idx < len(doc.paragraphs):
                        target_p = doc.paragraphs[target_p_idx]
                        if "VIII." in target_p.text.upper() or "BIBLIOGRAF" in target_p.text.upper():
                            break
                        cls._set_p_text_preserving_runs(target_p, mat_item)

        # 4. Actualizar Tabla 2: Actividades Pedagógicas (6 Etapas GTZ o Lean Canvas)
        if len(doc.tables) >= 2:
            tbl_act = doc.tables[1]
            actividades_list = (
                c_json.get("procesos_didacticos_gtz")
                or c_json.get("actividades_gtz")
                or c_json.get("desarrollo_didactico", {}).get("momentos", [])
            )
            if not actividades_list or len(actividades_list) < 6:
                actividades_list = cls._build_default_gtz_activities(topic, duration_minutes)

            gtz_names_upper = ["INFORMARSE", "PLANIFICAR", "DECIDIR", "EJECUTAR", "CONTROLAR", "EVALUAR"]
            gtz_names_title = ["Informarse", "Planificar", "Decidir", "Ejecutar", "Controlar", "Evaluar"]
            is_lc_session = any(k in f"{topic} {data.get('session_type', '')}".lower() for k in ["lean", "canvas", "emprendimiento", "design"])
            official_names = gtz_names_title if is_lc_session else gtz_names_upper

            for idx, act in enumerate(actividades_list[:6]):
                row_idx = idx + 1
                if row_idx < len(tbl_act.rows):
                    row = tbl_act.rows[row_idx]
                    if len(row.cells) >= 4:
                        # Fase limpia sin numeros ni asteriscos (*)
                        stage_label = official_names[idx] if idx < len(official_names) else re.sub(r'[*_#\d\.\s]', '', str(act.get("paso") or act.get("fase") or "")).strip()
                        cls._set_cell_text_preserving_runs(row.cells[0], stage_label)

                        t_min = act.get("tiempo_minutos") or act.get("duration") or (30 if idx in [0, 1] and is_lc_session else 15)
                        t_str = f"{t_min} min" if is_lc_session else f"{t_min} Minutos"
                        cls._set_cell_text_preserving_runs(row.cells[1], t_str)

                        # Limpieza estricta de asteriscos y markdown para actividades de docente y estudiante
                        raw_doc = str(act.get("actividad_docente") or act.get("docente") or "")
                        clean_doc = re.sub(r'[*_#]', '', raw_doc).strip()
                        raw_est = str(act.get("actividad_estudiante") or act.get("estudiante") or "")
                        clean_est = re.sub(r'[*_#]', '', raw_est).strip()

                        cls._set_cell_text_preserving_runs(row.cells[2], clean_doc)
                        cls._set_cell_text_preserving_runs(row.cells[3], clean_est)

        # Preservar el encabezado institucional REPROGRAMACION intacto tal como en la plantilla original

        # Aplicar cantSplit y tblHeader a las tablas de la sesión
        for t_obj in doc.tables:
            for r_obj in t_obj.rows:
                trPr = r_obj._tr.get_or_add_trPr()
                trPr.append(OxmlElement('w:cantSplit'))
        if len(doc.tables) >= 2:
            hdr_tr = doc.tables[1].rows[0]._tr.get_or_add_trPr()
            hdr_tr.append(OxmlElement('w:tblHeader'))

        # 5. Sección de Firmas Institucionales Oficiales (Tabla 2)
        if len(doc.tables) >= 3:
            tbl_sig = doc.tables[2]
            if len(tbl_sig.rows) >= 1:
                row_0 = tbl_sig.rows[0]
                for c in row_0.cells:
                    cls._set_cell_text_preserving_runs(c, "")

            if len(tbl_sig.rows) >= 2:
                sig_row = tbl_sig.rows[1]
                if len(sig_row.cells) >= 1:
                    c0_cell = sig_row.cells[0]
                    c0_text = c0_cell.text.strip().lower()
                    if any(k in c0_text for k in ["profesor", "profesora", "docente", "lic.", "ing."]):
                        if is_verified_teacher:
                            cls._set_cell_text_preserving_runs(c0_cell, f"{clean_teacher}\nDOCENTE RESPONSABLE")
                        else:
                            cls._set_cell_text_preserving_runs(c0_cell, "DOCENTE RESPONSABLE\n[Pendiente de completar]")

                if len(sig_row.cells) >= 2:
                    jefe_info = c_json.get("firmas_institucionales", {}).get("jefe_taller", {})
                    jefe_nom = jefe_info.get("nombre")
                    jefe_car = jefe_info.get("cargo")
                    clean_spec_low = clean_spec.lower()
                    is_ept_sig = "educación para el trabajo" in clean_spec_low or "ept" in clean_spec_low or any(
                        k in clean_spec_low for k in ["computac", "inform", "mecan", "electr", "metal", "vestid", "conta"]
                    )
                    if not jefe_nom:
                        if not is_ept_sig:
                            jefe_nom = f"Prof. Coordinador(a) Pedagógico(a)"
                            jefe_car = f"Coordinación Pedagógica de {clean_spec}"
                        elif "computac" in clean_spec_low or "inform" in clean_spec_low:
                            jefe_nom = "Mg. Luis Arturo La Rosa Gallardo"
                            jefe_car = "Jefe de Taller Computación e Informática"
                        elif "mecan" in clean_spec_low:
                            jefe_nom = "Prof. Responsable de Taller de Mecánica"
                            jefe_car = "Jefe de Taller Mecánica de Producción"
                        else:
                            jefe_nom = f"Jefe de Taller de {clean_spec}"
                            jefe_car = f"Jefe de Taller {clean_spec}"
                    cls._set_cell_text_preserving_runs(sig_row.cells[1], f"{jefe_nom}\n{jefe_car.upper()}")

                if len(sig_row.cells) >= 3:
                    sub_info = c_json.get("firmas_institucionales", {}).get("subdirector", {})
                    default_sub_nom = "Mg. Javier Eulogio Rosas Maguiña" if is_ept_sig else "Subdirección Pedagógica"
                    default_sub_car = "Subdirector Área Técnica" if is_ept_sig else "Subdirectora de Formación General"
                    sub_nom = sub_info.get("nombre", default_sub_nom)
                    sub_car = sub_info.get("cargo", default_sub_car)
                    cls._set_cell_text_preserving_runs(sig_row.cells[2], f"{sub_nom}\n{sub_car.upper()}\nINSTITUCIÓN EDUC. CET INEI 34 - CHANCAY")

    # Rellenado de Unidades Didácticas Oficiales CET N.º 34
    # -------------------------------------------------------------
    @classmethod
    def _fill_unit_docx_template(cls, doc: Document, data: Dict[str, Any]):
        """
        Rellena la plantilla de Unidad Didáctica Oficial CET N.º 34 con 100% concordancia temática
        en las 9 secciones oficiales, diferenciando limpiamente entre Áreas Académicas y EPT,
        preservando con absoluta fidelidad las tablas, bordes, encabezados y firmas institucionales.
        """
        topic = data.get("topic") or data.get("title") or "Unidad Didáctica"
        specialty = data.get("specialty") or "Educación para el Trabajo"
        clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "").strip()
        grade = int(data.get("grade") or 5)
        grade_words = {1: "Primer", 2: "Segundo", 3: "Tercer", 4: "Cuarto", 5: "Quinto"}
        grade_str = f"{grade_words.get(grade, str(grade) + '.°')} grado"
        is_ciclo_6 = (grade in [1, 2])
        ciclo_label = "Ciclo VI" if is_ciclo_6 else "Ciclo VII"
        section_name = data.get("section_name") or "A"

        c_json = data.get("content_json") or {}
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}

        gen = c_json.get("datos_generales") or {}
        is_ept = c_json.get("is_ept")
        if is_ept is None:
            is_ept = any(k in clean_spec.lower() for k in [
                "educación para el trabajo", "educacion para el trabajo", "ept",
                "computac", "informát", "informat", "mecánic", "mecanic",
                "electric", "electrón", "electron", "ebanist", "mader",
                "construc", "metálic", "metalic", "vestido", "textil",
                "contabil", "estétic", "estetic", "cosmetol"
            ])

        duration_weeks = int(gen.get("duracion_semanas") or data.get("duration_weeks") or 9)
        weekly_hours = int(gen.get("horas_semanales") or data.get("weekly_hours") or (8 if is_ept else 4))
        total_hours = int(gen.get("total_horas") or data.get("total_hours") or (duration_weeks * weekly_hours))
        unit_number = int(gen.get("numero_unidad") or data.get("unit_number") or 4)
        bimester = gen.get("bimestre") or data.get("bimester") or "IV Bimestre"
        purpose = data.get("purpose") or f"Desarrollar competencias fundamentales en {topic}."

        teacher_name = gen.get("docente_responsable") or data.get("teacher_name")
        is_verified_teacher, clean_teacher = cls.resolve_verified_teacher(teacher_name)

        desc_unidad = c_json.get("descripcion_unidad") or ""
        tech_matrix = c_json.get("matriz_habilidades_tecnicas") or c_json.get("matriz_desempenos_1") or []
        ent_matrix = c_json.get("matriz_habilidades_emprendimiento") or c_json.get("matriz_desempenos_2") or []
        tech_purp = c_json.get("propositos_tecnicos") or {}
        ent_purp = c_json.get("propositos_emprendimiento") or {}
        sessions = c_json.get("organizacion_sesiones") or []
        biblio = c_json.get("bibliografia") or []
        firmas = c_json.get("firmas_institucionales") or {}

        eje_1_name = c_json.get("eje_curricular_1_nombre") or ("Habilidades Técnicas Específicas de Taller" if is_ept else "Competencia 1")
        eje_2_name = c_json.get("eje_curricular_2_nombre") or ("Habilidades de Gestión de Proyectos de Emprendimiento" if is_ept else "Competencia 2")

        spec_l = clean_spec.lower()
        if is_ept:
            if "comput" in spec_l or "inform" in spec_l:
                jefe_taller = "Mg. Luis Arturo La Rosa Gallardo"
                jefe_cargo = "JEFE DE TALLER COMPUTACIÓN E INFORMÁTICA"
                mod_default = "Aplica herramientas de productividad, almacenamiento y colaboración en la nube"
            elif "mecan" in spec_l or "torno" in spec_l:
                jefe_taller = "Prof. Responsable de Taller de Mecánica"
                jefe_cargo = "JEFE DE TALLER MECÁNICA DE PRODUCCIÓN"
                mod_default = "Mecanizado de piezas por arranque de viruta en máquinas herramientas y soldadura"
            elif "electr" in spec_l:
                jefe_taller = "Prof. Responsable de Taller de Electricidad"
                jefe_cargo = "JEFE DE TALLER ELECTRICIDAD Y ELECTRÓNICA"
                mod_default = "Instalaciones eléctricas residenciales, industriales y control electrónico de potencia"
            else:
                jefe_taller = f"Jefe de Taller de {clean_spec}"
                jefe_cargo = f"JEFE DE TALLER {clean_spec.upper()[:30]}"
                mod_default = f"Módulo Formativo de {clean_spec}: {topic}"
            subdirector_cargo = "SUB-DIRECTOR DE ÁREA TÉCNICA"
        else:
            jefe_taller = firmas.get("jefe_taller", {}).get("nombre") or f"Coordinador(a) Pedagógico(a) del Área de {clean_spec}"
            jefe_cargo = firmas.get("jefe_taller", {}).get("cargo") or f"COORDINADOR PEDAGÓGICO DE {clean_spec.upper()}"
            subdirector_cargo = "SUB-DIRECTOR"
            mod_default = gen.get("modulo_formativo") or f"Desarrollo de competencias curriculares en {clean_spec}: {topic}"

        mod_val = gen.get("modulo_formativo") or mod_default
        f_inicio_str = gen.get("fecha_inicio_corta") or "16-03-2026"
        f_fin_str = gen.get("fecha_fin_corta") or "22-05-2026"
        dur_display = gen.get("duracion_texto") or f"Inicio: {f_inicio_str}     Fin: {f_fin_str}"
        horas_display = gen.get("horas_texto") or f"{total_hours} horas pedagógicas ({duration_weeks} semanas x {weekly_hours} horas)"

        # 1. Párrafo de Título (P2)
        for p in doc.paragraphs[:5]:
            p_text = p.text.strip().upper()
            if "UNIDAD DIDÁCTICA" in p_text or "UNIDAD DIDACTICA" in p_text:
                cls._set_p_text_preserving_runs(p, f"UNIDAD DIDÁCTICA N° {unit_number:02d}: {topic.upper()}")
                break

        # 2. Párrafos de Secciones III, IV, V, VI, VII (Actualizar títulos con nombres oficiales CNEB)
        for p in doc.paragraphs:
            p_u = p.text.strip().upper()
            if not is_ept:
                if p_u.startswith("III.") and ("HABILIDADES" in p_u or "DESEMPEÑOS" in p_u or "RELACIÓN" in p_u):
                    cls._set_p_text_preserving_runs(p, f"III.\tRELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: {eje_1_name.upper()}")
                elif p_u.startswith("IV.") and ("HABILIDADES" in p_u or "DESEMPEÑOS" in p_u or "RELACIÓN" in p_u or "EMPRENDIMIENTO" in p_u):
                    cls._set_p_text_preserving_runs(p, f"IV.\tRELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: {eje_2_name.upper()}")
                elif p_u.startswith("V.") and "PROPÓSITOS" in p_u:
                    cls._set_p_text_preserving_runs(p, f"V.\tORGANIZACIÓN DE LOS PROPÓSITOS DE APRENDIZAJE: {eje_1_name.upper()}")
                elif p_u.startswith("VI.") and "PROPÓSITOS" in p_u:
                    cls._set_p_text_preserving_runs(p, f"VI.\tORGANIZACIÓN DE LOS PROPÓSITOS DE APRENDIZAJE: {eje_2_name.upper()}")
            if p_u.startswith("VII.") and "SESIONES" in p_u:
                cls._set_p_text_preserving_runs(p, f"VII.\tORGANIZACIÓN DE LAS {len(sessions)} SESIONES DE APRENDIZAJE ({duration_weeks} SEMANAS — {total_hours} HORAS)")

        # 3. Párrafo de Descripción (P5)
        if desc_unidad:
            for i, p in enumerate(doc.paragraphs[:12]):
                p_u = p.text.upper()
                if "DESCRIPCIÓN DE LOS APRENDIZAJES" in p_u or "DESCRIPCION DE LOS APRENDIZAJES" in p_u:
                    if i + 1 < len(doc.paragraphs):
                        cls._set_p_text_preserving_runs(doc.paragraphs[i + 1], desc_unidad)
                    break

        # 4. Tabla 0: Datos Generales (10 filas exactas del formato institucional)
        if len(doc.tables) >= 1:
            tbl_meta = doc.tables[0]
            for r_idx, row in enumerate(tbl_meta.rows):
                if len(row.cells) >= 2:
                    k_text = row.cells[0].text.strip().lower()
                    val_idx = 2 if len(row.cells) >= 3 else 1
                    if "institución" in k_text or "institucion" in k_text or r_idx == 0:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], "CET 34 (I.E. INEI N.º 34)")
                    elif "área" in k_text or "area" in k_text or r_idx == 1:
                        area_out = gen.get("area_curricular") or (clean_spec if not is_ept else "Educación para el Trabajo")
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], area_out)
                    elif "programa" in k_text or "especialidad" in k_text or r_idx == 2:
                        prog_out = gen.get("especialidad") or (clean_spec if is_ept else f"Educación Secundaria - {clean_spec}")
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], prog_out)
                    elif "módulo" in k_text or "modulo" in k_text or r_idx == 3:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], mod_val)
                    elif "grado" in k_text or r_idx == 4:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], f'{grade_str}: "{section_name}"')
                    elif ("duración" in k_text or "duracion" in k_text) and r_idx == 5:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], dur_display)
                    elif ("hora" in k_text or r_idx == 6) and r_idx != 5:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], horas_display)
                    elif ("director" in k_text and "sub" not in k_text) or r_idx == 7:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], gen.get("director") or "Tomas Jurado Zevallos")
                    elif "sub" in k_text or r_idx == 8:
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], gen.get("subdirector") or "Mg. Javier Eulogio Rosas Maguiña")
                    elif "docente" in k_text or r_idx == 9:
                        doc_val = clean_teacher if is_verified_teacher else (clean_teacher or "Docente del Área")
                        cls._set_cell_text_preserving_runs(row.cells[val_idx], doc_val)

        # 5. Tabla 1: Matriz Curricular Eje 1 (Sección III - 2 filas x 3 columnas)
        if len(doc.tables) >= 2 and tech_matrix:
            tbl_t = doc.tables[1]
            if len(tbl_t.rows) >= 1 and not is_ept:
                cls._set_cell_text_preserving_runs(tbl_t.rows[0].cells[0], f"Desempeños del grado - Matriz curricular: {eje_1_name}")
                cls._set_cell_text_preserving_runs(tbl_t.rows[0].cells[1], f"Estándar de aprendizaje ({ciclo_label})")
                cls._set_cell_text_preserving_runs(tbl_t.rows[0].cells[2], "Estructura interna del área")
            if len(tbl_t.rows) >= 2:
                r1 = tbl_t.rows[1]
                desemp_lines = [f"{i}. {tm.get('desempenos') or tm.get('habilidad_o_desempeno') or tm.get('habilidad_tecnica', '')}" for i, tm in enumerate(tech_matrix, 1)]
                cls._set_cell_text_preserving_runs(r1.cells[0], "\n".join(desemp_lines))
                est_text = tech_purp.get("estandar_esperado") or tech_matrix[0].get("estandar_modulo") or f"Competencias del área en {topic}."
                cls._set_cell_text_preserving_runs(r1.cells[1], est_text)
                cls._set_cell_text_preserving_runs(r1.cells[2], f"Módulo / Proyecto Pedagógico: {mod_val}")

        # 6. Tabla 2: Matriz Curricular Eje 2 (Sección IV - 2 filas x 3 columnas)
        if len(doc.tables) >= 3 and ent_matrix:
            tbl_e = doc.tables[2]
            if len(tbl_e.rows) >= 1 and not is_ept:
                cls._set_cell_text_preserving_runs(tbl_e.rows[0].cells[0], f"Desempeños del grado - Matriz curricular articuladora: {eje_2_name}")
                cls._set_cell_text_preserving_runs(tbl_e.rows[0].cells[1], f"Estándar de aprendizaje ({ciclo_label})")
                cls._set_cell_text_preserving_runs(tbl_e.rows[0].cells[2], "Estructura interna del área")
            if len(tbl_e.rows) >= 2:
                r1 = tbl_e.rows[1]
                desemp_lines_e = [f"{i}. {em.get('desempenos') or em.get('habilidad_o_desempeno') or em.get('habilidad_emprendimiento', '')}" for i, em in enumerate(ent_matrix, 1)]
                cls._set_cell_text_preserving_runs(r1.cells[0], "\n".join(desemp_lines_e))
                est_e_text = ent_purp.get("estandar_esperado") or ent_matrix[0].get("estandar_ciclo") or "Competencias transversales articuladas a la unidad."
                cls._set_cell_text_preserving_runs(r1.cells[1], est_e_text)
                est_int_label = "Implementamos, comunicamos y mejoramos nuestro emprendimiento (Design Thinking / Lean Canvas)" if is_ept else f"Articulación curricular y competencias de {clean_spec}"
                cls._set_cell_text_preserving_runs(r1.cells[2], est_int_label)

        # 7. Tabla 3: Propósitos Semanales Eje 1 (Sección V)
        if len(doc.tables) >= 4 and tech_matrix:
            tbl_pt = doc.tables[3]
            if len(tbl_pt.rows) >= 1:
                p_text_full = f"PROPÓSITO DE UNIDAD DIDÁCTICA {unit_number}: {purpose}"
                for cell in tbl_pt.rows[0].cells:
                    cls._set_cell_text_preserving_runs(cell, p_text_full)

            # Dinámicamente expandir o recortar filas conservando fielmente bordes, estilos y márgenes XML
            if len(tbl_pt.rows) >= 3:
                ref_tr = tbl_pt.rows[2]._tr
                while len(tbl_pt.rows) < len(tech_matrix) + 2:
                    tbl_pt._tbl.append(copy.deepcopy(ref_tr))
                while len(tbl_pt.rows) > len(tech_matrix) + 2:
                    extra_tr = tbl_pt.rows[-1]._tr
                    extra_tr.getparent().remove(extra_tr)

            for w_idx in range(len(tech_matrix)):
                row_idx = w_idx + 2
                if row_idx < len(tbl_pt.rows):
                    tm = tech_matrix[w_idx]
                    h_title = tm.get("habilidad_o_desempeno") or tm.get("habilidad_tecnica") or f"Semana {w_idx+1}"
                    s_purp = tm.get("desempenos") or f"Desarrollar capacidades en {h_title}."
                    cls._set_cell_text_preserving_runs(tbl_pt.rows[row_idx].cells[0], f"Semana {w_idx+1}\n{h_title}")
                    cls._set_cell_text_preserving_runs(tbl_pt.rows[row_idx].cells[1], s_purp)

        # 8. Tabla 4: Propósitos Semanales Eje 2 (Sección VI)
        if len(doc.tables) >= 5 and ent_matrix:
            tbl_pe = doc.tables[4]
            if len(tbl_pe.rows) >= 1:
                p_text_full = f"PROPÓSITO DE UNIDAD DE APRENDIZAJE {unit_number}: {purpose}"
                for cell in tbl_pe.rows[0].cells:
                    cls._set_cell_text_preserving_runs(cell, p_text_full)

            if len(tbl_pe.rows) >= 3:
                ref_tr = tbl_pe.rows[2]._tr
                while len(tbl_pe.rows) < len(ent_matrix) + 2:
                    tbl_pe._tbl.append(copy.deepcopy(ref_tr))
                while len(tbl_pe.rows) > len(ent_matrix) + 2:
                    extra_tr = tbl_pe.rows[-1]._tr
                    extra_tr.getparent().remove(extra_tr)

            for w_idx in range(len(ent_matrix)):
                row_idx = w_idx + 2
                if row_idx < len(tbl_pe.rows):
                    em = ent_matrix[w_idx]
                    h_title = em.get("habilidad_o_desempeno") or em.get("habilidad_emprendimiento") or f"Semana {w_idx+1}"
                    s_purp = em.get("desempenos") or f"Aplicar competencias en {h_title}."
                    cls._set_cell_text_preserving_runs(tbl_pe.rows[row_idx].cells[0], f"Semana {w_idx+1}\n{h_title}")
                    cls._set_cell_text_preserving_runs(tbl_pe.rows[row_idx].cells[1], s_purp)

        # 9. Tabla 5: Propósito de la Unidad (Sección VII A)
        if len(doc.tables) >= 6:
            tbl_p = doc.tables[5]
            if len(tbl_p.rows) >= 2 and len(tbl_p.rows[1].cells) >= 1:
                cls._set_cell_text_preserving_runs(tbl_p.rows[1].cells[0], purpose)

        # 10. Tabla 6: Organización de las Sesiones (Sección VII B)
        if len(doc.tables) >= 7 and sessions:
            tbl_s = doc.tables[6]
            # Asegurar filas suficientes para todas las sesiones clonando el XML de celda con bordes exactos
            if len(tbl_s.rows) >= 2:
                ref_tr = tbl_s.rows[1]._tr
                while len(tbl_s.rows) < len(sessions) + 1:
                    tbl_s._tbl.append(copy.deepcopy(ref_tr))
                while len(tbl_s.rows) > len(sessions) + 1:
                    extra_tr = tbl_s.rows[-1]._tr
                    extra_tr.getparent().remove(extra_tr)

            for s_idx, s in enumerate(sessions):
                r_idx = s_idx + 1
                if r_idx < len(tbl_s.rows):
                    row = tbl_s.rows[r_idx]
                    if is_ept:
                        tipo_txt = "Técnica" if s.get("tipo_sesion") == "tecnica" else "Gestión de proyectos de emprendimiento"
                    else:
                        tipo_txt = s.get("tipo_sesion") or clean_spec
                    tit_full = f"{tipo_txt}\n{s.get('titulo', '')}"
                    cls._set_cell_text_preserving_runs(row.cells[0], tit_full)
                    cls._set_cell_text_preserving_runs(row.cells[1], s.get("proposito", ""))
                    cls._set_cell_text_preserving_runs(row.cells[2], s.get("criterio_evaluacion", ""))
                    cls._set_cell_text_preserving_runs(row.cells[3], s.get("evidencia_aprendizaje", ""))
                    if len(row.cells) >= 5:
                        cls._set_cell_text_preserving_runs(row.cells[4], str(s.get("semana", "")))
                    if len(row.cells) >= 6:
                        cls._set_cell_text_preserving_runs(row.cells[5], str(s.get("horas_pedagogicas", 0)))

        # 11. Sección VIII: Bibliografía y Referencias (Reemplazar párrafos de la plantilla original)
        if biblio:
            bib_hdr_p = None
            for p in doc.paragraphs:
                p_u = p.text.upper()
                if "VIII." in p_u and ("BIBLIO" in p_u or "REFEREN" in p_u):
                    bib_hdr_p = p
                    break
            if bib_hdr_p is not None:
                current_el = bib_hdr_p._element.getnext()
                existing_bib_ps = []
                while current_el is not None and current_el.tag.split('}')[-1] == 'p':
                    p_obj = docx.text.paragraph.Paragraph(current_el, doc)
                    if p_obj.text.strip():
                        existing_bib_ps.append(p_obj)
                    current_el = current_el.getnext()

                for b_idx, b_text in enumerate(biblio):
                    if b_idx < len(existing_bib_ps):
                        cls._set_p_text_preserving_runs(existing_bib_ps[b_idx], b_text)
                    else:
                        last_p = existing_bib_ps[-1] if existing_bib_ps else bib_hdr_p
                        new_p = doc.add_paragraph(b_text, style="List Paragraph")
                        last_p._element.addnext(new_p._element)
                        existing_bib_ps.append(new_p)

                for extra_p in existing_bib_ps[len(biblio):]:
                    extra_el = extra_p._element
                    extra_el.getparent().remove(extra_el)

        # 12. Tabla 7: Firmas Institucionales Reglamentarias (3 firmas)
        sig_tbl_idx = len(doc.tables) - 1
        tbl_sig = doc.tables[sig_tbl_idx]
        if len(tbl_sig.rows) >= 2 and len(tbl_sig.columns) >= 3:
            row_0 = tbl_sig.rows[0]
            for c in row_0.cells:
                cls._set_cell_text_preserving_runs(c, "")

            sig_row = tbl_sig.rows[1]
            if is_ept:
                doc_sign = f"{clean_teacher}\nDOCENTE RESPONSABLE\nÁREA EDUCACIÓN PARA EL TRABAJO"
                jefe_sign = f"{jefe_taller}\n{jefe_cargo}\nJEFE DE TALLER"
                sub_sign = "Mg. Javier Eulogio Rosas Maguiña\nSUB-DIRECTOR DE ÁREA TÉCNICA\nINSTITUCIÓN EDUC. CET INEI 34 - CHANCAY"
            else:
                doc_sign = f"{clean_teacher}\nDOCENTE RESPONSABLE\nÁREA CURRICULAR DE {clean_spec.upper()}"
                jefe_sign = f"{jefe_taller}\n{jefe_cargo}\nCOORDINACIÓN PEDAGÓGICA"
                sub_sign = f"Mg. Javier Eulogio Rosas Maguiña\n{subdirector_cargo}\nINSTITUCIÓN EDUC. CET INEI 34 - CHANCAY"

            cls._set_cell_text_preserving_runs(sig_row.cells[0], doc_sign)
            cls._set_cell_text_preserving_runs(sig_row.cells[1], jefe_sign)
            cls._set_cell_text_preserving_runs(sig_row.cells[2], sub_sign)


    # -------------------------------------------------------------
    # Rellenado de Exámenes Técnicos y Prácticas Calificadas (CET N.º 34)
    # -------------------------------------------------------------
    @classmethod
    def _fill_exam_docx_template(cls, doc: Document, data: Dict[str, Any]):
        """
        Rellena la plantilla institucional de Examen Técnico o Práctica Calificada (CET N.° 34).
        Aplica slicing curricular selectivo según el área, adapta el membrete a FICHA DE EXAMEN
        o FICHA DE PRÁCTICA, e inserta las 10 preguntas canónicas con sus respectivas secciones.
        Diferencia estrictamente la Versión Estudiante (sin solucionario) y la
        Versión Docente (con solucionario y respuestas justificadas).
        """
        from app.ai.document_schemas import build_examen_practica_from_dict
        exam_obj = build_examen_practica_from_dict(data)

        topic = exam_obj.tema
        specialty = exam_obj.area
        grade = exam_obj.grado
        grade_str = f"{grade}.°"
        section_name = exam_obj.seccion
        clean_teacher = exam_obj.docente
        is_verified_teacher, clean_teacher = cls.resolve_verified_teacher(clean_teacher)
        target = (data.get("target") or "teacher").strip().lower()
        include_teacher_key = data.get("include_teacher_key", target != "student")

        # 1. Slicing selectivo según el área curricular (si el doc contiene las 7 fichas = 21 tablas)
        sheet_idx = cls._select_ficha_sheet_index(specialty, topic)
        if len(doc.tables) >= 21:
            body = doc._body._element
            all_elements = list(body)
            sectPr = body.xpath('.//w:sectPr')
            sectPr_el = sectPr[-1] if sectPr else None

            start_table_el = doc.tables[sheet_idx * 3]._element
            end_table_el = doc.tables[sheet_idx * 3 + 2]._element

            start_idx_elem = all_elements.index(start_table_el)
            end_idx_elem = all_elements.index(end_table_el)

            for idx, el in enumerate(all_elements):
                if el == sectPr_el:
                    continue
                if idx < start_idx_elem or idx > end_idx_elem:
                    body.remove(el)
        elif len(doc.tables) >= 6:
            tbl2_elem = doc.tables[2]._element
            body = doc._body._element
            found = False
            for elem in list(body):
                if elem == tbl2_elem:
                    found = True
                    continue
                if found and not elem.tag.endswith("sectPr"):
                    body.remove(elem)

        # 2. Actualizar Tabla 0: Membrete y metadatos del estudiante
        if len(doc.tables) >= 1:
            tbl_meta = doc.tables[0]
            if len(tbl_meta.rows) >= 1 and len(tbl_meta.rows[0].cells) >= 4:
                r0 = tbl_meta.rows[0]
                cls._set_cell_text_preserving_runs(r0.cells[1], f"INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY\nÁrea: {exam_obj.area}")
                cls._set_cell_text_preserving_runs(r0.cells[3], f"{exam_obj.titulo_documento}\n{grade_str} de Secundaria")

            clean_title = topic.strip().strip('"').strip('“').strip('”').upper()
            if len(tbl_meta.rows) >= 2 and len(tbl_meta.rows[1].cells) >= 1:
                r1 = tbl_meta.rows[1]
                cls._set_cell_text_preserving_runs(r1.cells[0], f'“{clean_title}”')

            if len(tbl_meta.rows) >= 3 and len(tbl_meta.rows[2].cells) >= 6:
                r2 = tbl_meta.rows[2]
                cls._set_cell_text_preserving_runs(r2.cells[0], "Estudiante: _____________________________________")
                cls._set_cell_text_preserving_runs(r2.cells[3], f'Grado y sección: {grade_str} “{section_name}”')
                cls._set_cell_text_preserving_runs(r2.cells[5], f"Fecha: {exam_obj.fecha}")

            if len(tbl_meta.rows) >= 4 and len(tbl_meta.rows[3].cells) >= 1:
                r3 = tbl_meta.rows[3]
                doc_val = clean_teacher if is_verified_teacher else (exam_obj.docente or "[Docente Responsable - Por completar]")
                cls._set_cell_text_preserving_runs(r3.cells[0], f"Docente: {doc_val}")

        # 3. Actualizar Tabla 1: Indicaciones
        if len(doc.tables) >= 2:
            tbl_ind = doc.tables[1]
            if len(tbl_ind.rows) >= 1 and len(tbl_ind.rows[0].cells) >= 1:
                cls._set_cell_text_preserving_runs(
                    tbl_ind.rows[0].cells[0],
                    exam_obj.indicaciones
                )

        # 4. Actualizar párrafos de las preguntas
        is_matematica = (exam_obj.area == "Matemática") or (len(exam_obj.seccion_c) == 0)

        if is_matematica and len(doc.tables) >= 2:
            from docx.shared import Pt
            body = doc._body._element
            all_els = list(body)
            tbl1_el = doc.tables[1]._element
            tbl2_el = doc.tables[2]._element if len(doc.tables) >= 3 else None

            idx1 = all_els.index(tbl1_el)
            idx2 = all_els.index(tbl2_el) if tbl2_el is not None else len(all_els)

            # Eliminar párrafos predeterminados de 3 secciones entre tbl1 y tbl2
            for el in all_els[idx1+1:idx2]:
                if not el.tag.endswith("sectPr"):
                    body.remove(el)

            # Insertar los párrafos especializados de 2 secciones para Matemática
            def _add_math_p(text, bold=False, italic=False, font_size=9.5, space_after=2):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = pptx.util.Pt(space_after)
                p.paragraph_format.space_before = pptx.util.Pt(0)
                p.paragraph_format.line_spacing = 1.05
                run = p.add_run(text)
                run.font.name = 'Calibri'
                run.font.size = pptx.util.Pt(font_size)
                run.bold = bold
                run.italic = italic
                if tbl2_el is not None:
                    tbl2_el.addprevious(p._element)
                return p

            _add_math_p("A. Marca la alternativa correcta", bold=True, font_size=10.5, space_after=3)
            for q in exam_obj.seccion_a:
                _add_math_p(f"{q.numero}. {q.pregunta}", bold=True, font_size=9, space_after=1)
                _add_math_p(q.opciones_texto, bold=False, font_size=8.5, space_after=3)

            _add_math_p("B. Resuelve y muestra tu procedimiento", bold=True, font_size=10.5, space_after=3)
            for q in exam_obj.seccion_b:
                _add_math_p(f"{q.numero}. {q.pregunta}", bold=True, font_size=9, space_after=1)
                _add_math_p("Espacio de resolución: __________________________________________________________________", font_size=8, space_after=1)
                _add_math_p("Respuesta final: _________________________________________________________________________", bold=True, font_size=8, space_after=3)

            if include_teacher_key:
                _add_math_p("Puntaje sugerido", bold=True, font_size=9, space_after=1)
                _add_math_p(exam_obj.puntaje_texto, font_size=8.5, space_after=2)
                _add_math_p("Clave de respuestas y orientaciones", bold=True, font_size=9, space_after=1)
                _add_math_p(exam_obj.orientacion_docente, font_size=8.5, space_after=3)
        else:
            paras = doc.paragraphs
            p_len = len(paras)

            sec_a = exam_obj.seccion_a
            sec_b = exam_obj.seccion_b
            sec_c = exam_obj.seccion_c

            for i in range(p_len):
                p_text = paras[i].text.strip()
                # Sección A
                if p_text.startswith("1.") and len(sec_a) >= 1:
                    cls._set_p_text_preserving_runs(paras[i], f"1. {sec_a[0].pregunta}")
                    if i + 1 < p_len:
                        cls._set_p_text_preserving_runs(paras[i+1], sec_a[0].opciones_texto)
                elif p_text.startswith("2.") and len(sec_a) >= 2:
                    cls._set_p_text_preserving_runs(paras[i], f"2. {sec_a[1].pregunta}")
                    if i + 1 < p_len:
                        cls._set_p_text_preserving_runs(paras[i+1], sec_a[1].opciones_texto)
                elif p_text.startswith("3.") and len(sec_a) >= 3:
                    cls._set_p_text_preserving_runs(paras[i], f"3. {sec_a[2].pregunta}")
                    if i + 1 < p_len:
                        cls._set_p_text_preserving_runs(paras[i+1], sec_a[2].opciones_texto)

                # Sección B
                elif p_text.startswith("4.") and len(sec_b) >= 1:
                    cls._set_p_text_preserving_runs(paras[i], f"4. {sec_b[0].pregunta}")
                elif p_text.startswith("5.") and len(sec_b) >= 2:
                    cls._set_p_text_preserving_runs(paras[i], f"5. {sec_b[1].pregunta}")
                elif p_text.startswith("6.") and len(sec_b) >= 3:
                    cls._set_p_text_preserving_runs(paras[i], f"6. {sec_b[2].pregunta}")

                # Sección C
                elif p_text.startswith("7.") and len(sec_c) >= 1:
                    cls._set_p_text_preserving_runs(paras[i], f"7. {sec_c[0].afirmacion}    (   ) V    (   ) F")
                elif p_text.startswith("8.") and len(sec_c) >= 2:
                    cls._set_p_text_preserving_runs(paras[i], f"8. {sec_c[1].afirmacion}    (   ) V    (   ) F")
                elif p_text.startswith("9.") and len(sec_c) >= 3:
                    cls._set_p_text_preserving_runs(paras[i], f"9. {sec_c[2].afirmacion}    (   ) V    (   ) F")
                elif p_text.startswith("10.") and len(sec_c) >= 4:
                    cls._set_p_text_preserving_runs(paras[i], f"10. {sec_c[3].afirmacion}    (   ) V    (   ) F")

                elif "cada pregunta vale" in p_text.lower():
                    cls._set_p_text_preserving_runs(paras[i], exam_obj.puntaje_texto)
                elif "las respuestas abiertas pueden admitir" in p_text.lower():
                    cls._set_p_text_preserving_runs(paras[i], exam_obj.orientacion_docente)

        # 5. Tabla 2: Solucionario Docente vs. Versión Estudiante
        if len(doc.tables) >= 3:
            tbl_sol = doc.tables[2]
            if not include_teacher_key:
                # VERSIÓN ESTUDIANTE: Eliminar completamente la tabla de solucionario
                tbl_elem = tbl_sol._element
                if tbl_elem.getparent() is not None:
                    tbl_elem.getparent().remove(tbl_elem)
                for p in list(doc.paragraphs):
                    p_lower = p.text.lower()
                    if any(k in p_lower for k in [
                        "solucionario",
                        "puntaje sugerido",
                        "clave de respuesta",
                        "claves de respuesta",
                        "clave de respuestas",
                        "cada pregunta vale 1 punto",
                        "cada pregunta vale",
                        "las respuestas abiertas pueden admitir"
                    ]):
                        p_el = p._element
                        parent = p_el.getparent()
                        if parent is not None:
                            parent.remove(p_el)
            else:
                # VERSIÓN DOCENTE: Rellenar las 10 filas de respuestas
                for idx, item in enumerate(exam_obj.solucionario[:10]):
                    row_idx = idx + 1
                    if row_idx < len(tbl_sol.rows):
                        row = tbl_sol.rows[row_idx]
                        if len(row.cells) >= 2:
                            cls._set_cell_text_preserving_runs(row.cells[0], str(item.item))
                            cls._set_cell_text_preserving_runs(row.cells[1], item.respuesta_esperada)

        # Aplicar cantSplit y tblHeader a todas las tablas del examen
        from docx.oxml import OxmlElement
        for tbl in doc.tables:
            for r_idx, r in enumerate(tbl.rows):
                trPr = r._tr.get_or_add_trPr()
                trPr.append(OxmlElement('w:cantSplit'))
                if r_idx == 0 and len(tbl.rows) > 1:
                    trPr.append(OxmlElement('w:tblHeader'))

    # -------------------------------------------------------------
    # Rellenado de Fichas de Trabajo del Estudiante (CET N.º 34)
    # -------------------------------------------------------------
    @classmethod
    def _select_ficha_sheet_index(cls, area_str: str, topic_str: str = "") -> int:
        """
        Selecciona el índice de la ficha temático-curricular oficial (0 a 6)
        en la plantilla multi-área CET N.º 34 (ficha_trabajo_estudiante_cet34.docx).
        0: EPT / Computación (Lean Canvas / Procesos técnicos)
        1: Ciencia y Tecnología (La célula / Explicación científica)
        2: DPCC (Identidad / Convivencia / Dilema moral)
        3: Educación Física (Calentamiento / Salud corporal)
        4: Arte y Cultura (Expresión artística / Lenguajes plásticos)
        5: Inglés (Simple Present / Vocabulario)
        6: Matemática (Fracciones / Operaciones / Resolución de problemas)
        """
        text = f"{area_str} {topic_str}".lower()
        if any(k in text for k in ["ciencia y tecnolog", "ciencias y tecnolog", "c y t", "cyt", "biolog", "químic", "quimic", "físic", "fisic", "célula", "celula", "átomo", "atomo", "ecosistema"]):
            return 1
        if any(k in text for k in ["social", "ciencias sociales", "historia", "geograf", "ccss", "tahuantinsuyo", "desarrollo personal", "dpcc", "ciudadan", "cívic", "civica", "ética", "etica", "identidad", "autoestima", "convivencia", "pubertad"]):
            return 2
        if any(k in text for k in ["educación física", "educacion fisica", "deporte", "motric", "físico", "calentamiento", "hidratación", "hidratacion"]):
            return 3
        if any(k in text for k in ["arte y cultura", "artes visuales", "música", "musica", "teatro", "danza", "dibujo", "pintura", "color"]):
            return 4
        if any(k in text for k in ["inglés", "ingles", "english", "foreign language", "present simple", "routines"]):
            return 5
        if any(k in text for k in ["matemática", "matematica", "matemáticas", "matematicas", "álgebra", "algebra", "geometría", "geometria", "trigonometría", "trigonometria", "aritmética", "aritmetica", "cálculo", "calculo", "números", "fracciones"]):
            return 6
        return 0  # EPT por defecto

    @classmethod
    def _fill_student_worksheet_docx_template(cls, doc: Document, data: Dict[str, Any]):
        """
        Rellena la Ficha de Trabajo del Estudiante (CET N.º 34) con membrete, propósito,
        desafío contextualizado, marco teórico, actividades prácticas y lista de cotejo.
        Garantiza aislamiento estricto por área curricular (sin contaminación cruzada).
        """
        from app.ai.document_schemas import build_ficha_from_dict
        f_obj = build_ficha_from_dict(data)
        f_data = f_obj.model_dump()

        topic = data.get("topic") or data.get("title") or f_data.get("titulo") or "Ficha de Aprendizaje"
        if topic.lower().startswith("ficha de aprendizaje: "):
            topic = topic[22:].strip()
        area = f_data.get("area") or data.get("specialty") or "Ciencia y Tecnología"
        grade = int(f_data.get("grado") or data.get("grade") or 1)
        grade_str = f"{grade}.°"
        section_name = f_data.get("seccion") or data.get("section_name") or "A"
        teacher_name = data.get("teacher_name")
        is_verified_teacher, clean_teacher = cls.resolve_verified_teacher(teacher_name)
        if not is_verified_teacher:
            clean_teacher = f_data.get("docente") or "[Docente Responsable - Por completar]"

        # 1. Slicing selectivo según el área curricular (si el doc tiene las 7 fichas = 42 tablas)
        sheet_idx = cls._select_ficha_sheet_index(area, topic)
        if len(doc.tables) >= 42:
            body = doc._body._element
            all_elements = list(body)
            sectPr = body.xpath('.//w:sectPr')
            sectPr_el = sectPr[-1] if sectPr else None

            start_table_el = doc.tables[sheet_idx * 6]._element
            end_table_el = doc.tables[(sheet_idx + 1) * 6]._element if (sheet_idx + 1) * 6 < len(doc.tables) else None

            start_idx = all_elements.index(start_table_el)
            end_idx = all_elements.index(end_table_el) if end_table_el is not None else len(all_elements)

            for idx, el in enumerate(all_elements):
                if el == sectPr_el:
                    continue
                if idx < start_idx or idx >= end_idx:
                    body.remove(el)
        elif len(doc.tables) > 6:
            # Fallback seguro si la plantilla contiene otra cantidad
            tbl6_elem = doc.tables[6]._element
            body = doc._body._element
            found = False
            for elem in list(body):
                if elem == tbl6_elem:
                    found = True
                if found and not elem.tag.endswith("sectPr"):
                    body.remove(elem)

        # 2. Tabla 0: Membrete y metadatos del estudiante
        if len(doc.tables) >= 1:
            tbl_meta = doc.tables[0]
            if len(tbl_meta.rows) >= 1 and len(tbl_meta.rows[0].cells) >= 4:
                r0 = tbl_meta.rows[0]
                cls._set_cell_text_preserving_runs(r0.cells[1], f"INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY\nÁrea: {area}")
                cls._set_cell_text_preserving_runs(r0.cells[3], f"FICHA DE APRENDIZAJE\n{grade_str} de Secundaria")

            clean_title = topic.strip().strip('"').strip('“').strip('”').upper()
            if len(tbl_meta.rows) >= 2 and len(tbl_meta.rows[1].cells) >= 1:
                r1 = tbl_meta.rows[1]
                cls._set_cell_text_preserving_runs(r1.cells[0], f'“{clean_title}”')

            if len(tbl_meta.rows) >= 3 and len(tbl_meta.rows[2].cells) >= 6:
                r2 = tbl_meta.rows[2]
                cls._set_cell_text_preserving_runs(r2.cells[0], "Estudiante: _____________________________________")
                cls._set_cell_text_preserving_runs(r2.cells[3], f'Grado y sección: {grade_str} “{section_name}”')
                cls._set_cell_text_preserving_runs(r2.cells[5], f"Fecha: {f_data.get('fecha') or data.get('date', '____ / ____ / 2026')}")

            if len(tbl_meta.rows) >= 4 and len(tbl_meta.rows[3].cells) >= 1:
                r3 = tbl_meta.rows[3]
                cls._set_cell_text_preserving_runs(r3.cells[0], f"Docente: {clean_teacher}")

        # 3. Tabla 1: Competencia CNEB
        if len(doc.tables) >= 2:
            tbl_cneb = doc.tables[1]
            if len(tbl_cneb.rows) >= 1 and len(tbl_cneb.rows[0].cells) >= 1:
                comp_text = (
                    f"Competencia del Currículo Nacional: {f_data['competencia']}\n"
                    f"Capacidades: {f_data['capacidades']}\n"
                    f"Desempeño contextualizado: {f_data['desempeno']}"
                )
                cls._set_cell_text_preserving_runs(tbl_cneb.rows[0].cells[0], comp_text)

        # Eliminar cualquier párrafo residual generado por la IA con texto "[Insertar membrete...]"
        for p_elem in list(doc.paragraphs):
            p_txt_low = p_elem.text.strip().lower()
            if any(k in p_txt_low for k in ["insertar membrete", "[membrete", "insertar logo", "[logo"]):
                el = p_elem._element
                if el.getparent() is not None and not el.xpath('.//w:sectPr'):
                    el.getparent().remove(el)

        # 4. Párrafos: Propósito, Evidencia y Objetivos
        objs = f_data.get("objetivos_aprendizaje") or []
        for i, p in enumerate(list(doc.paragraphs[:25])):
            p_text = p.text.strip().lower()
            if p_text.startswith("propósito:") or p_text.startswith("proposito:"):
                cls._set_p_text_preserving_runs(p, f"Propósito: {f_data['proposito']}")
            elif p_text.startswith("producto o evidencia:"):
                cls._set_p_text_preserving_runs(p, f"Producto o evidencia: {f_data['evidencia_general']}")
            elif "objetivos de aprendizaje" in p_text:
                b_idx = 0
                for j in range(i + 1, min(i + 6, len(doc.paragraphs))):
                    if j >= len(doc.paragraphs):
                        break
                    p_sub = doc.paragraphs[j]
                    p_sub_txt = p_sub.text.strip()
                    if p_sub_txt.startswith("•") or p_sub_txt.startswith("-"):
                        if b_idx < len(objs):
                            cls._set_p_text_preserving_runs(p_sub, f"• {objs[b_idx]}")
                            b_idx += 1
                        else:
                            p_sub._element.getparent().remove(p_sub._element)

        # Limpiar cualquier pregunta de análisis residual de la plantilla
        for p in list(doc.paragraphs):
            p_low = p.text.strip().lower()
            if any(k in p_low for k in ["pregunta de análisis", "pregunta de analisis", "dos estructuras celulares", "por qué la planta", "por que la planta"]):
                p._element.getparent().remove(p._element)

        # 5. Tabla 2: Situación de reto ("¡Acepta el desafío!")
        if len(doc.tables) >= 3:
            tbl_reto = doc.tables[2]
            if len(tbl_reto.rows) >= 1 and len(tbl_reto.rows[0].cells) >= 1:
                cls._set_cell_text_preserving_runs(tbl_reto.rows[0].cells[0], f"¡Acepta el desafío!\n{f_data['situacion_reto']}")

        # 6. Tabla 3: Marco teórico breve
        if len(doc.tables) >= 4:
            tbl_teor = doc.tables[3]
            if len(tbl_teor.rows) >= 1 and len(tbl_teor.rows[0].cells) >= 1:
                cls._set_cell_text_preserving_runs(tbl_teor.rows[0].cells[0], f"Marco teórico y conceptos clave\n{f_data['marco_teorico']}")

        # 7. Actualizar Ejemplo Modelo y Actividades / Ejercicios 1, 2, 3
        # A) Actualizar Ejemplo modelo (Pasos 1 al 4) si existe en la plantilla
        steps = f_data.get("ejemplo_modelo_pasos") or []
        res_mod = f_data.get("ejemplo_modelo_resultado") or ""
        for i, p in enumerate(list(doc.paragraphs)):
            p_text = p.text.strip().lower()
            if p_text.startswith("ejemplo modelo"):
                cls._set_p_text_preserving_runs(p, f"Ejemplo modelo – {clean_title}")
                s_idx = 0
                for j in range(i + 1, min(i + 8, len(doc.paragraphs))):
                    if j >= len(doc.paragraphs): break
                    p_step = doc.paragraphs[j]
                    p_st = p_step.text.strip().lower()
                    if p_st.startswith("paso"):
                        if s_idx < len(steps):
                            cls._set_p_text_preserving_runs(p_step, steps[s_idx])
                            s_idx += 1
                        else:
                            p_step._element.getparent().remove(p_step._element)
                    elif p_st.startswith("resultado:"):
                        if res_mod:
                            cls._set_p_text_preserving_runs(p_step, f"Resultado: {res_mod}")
                        else:
                            p_step._element.getparent().remove(p_step._element)

        # B) Actualizar Actividades / Ejercicios 1, 2, 3 (soporta tanto "Actividad" como "Ejercicio")
        act_list = f_data.get("actividades") or []
        for p in doc.paragraphs:
            p_text = p.text.strip().lower()
            if (p_text.startswith("actividad 1") or p_text.startswith("ejercicio 1")) and len(act_list) >= 1:
                act1 = act_list[0]
                tit1 = act1.get("titulo") or "Actividad 1"
                inst1 = act1.get("instrucciones") or f"Desarrolla el reto planteado de {topic}."
                cls._set_p_text_preserving_runs(p, f"Actividad 1 – {tit1}: {inst1}")
            elif (p_text.startswith("actividad 2") or p_text.startswith("ejercicio 2")) and len(act_list) >= 2:
                act2 = act_list[1]
                tit2 = act2.get("titulo") or "Actividad 2"
                inst2 = act2.get("instrucciones") or f"Desarrolla el reto planteado de {topic}."
                cls._set_p_text_preserving_runs(p, f"Actividad 2 – {tit2}: {inst2}")
            elif (p_text.startswith("actividad 3") or p_text.startswith("ejercicio 3")) and len(act_list) >= 3:
                act3 = act_list[2]
                tit3 = act3.get("titulo") or "Actividad 3"
                inst3 = act3.get("instrucciones") or f"Desarrolla el reto planteado de {topic}."
                cls._set_p_text_preserving_runs(p, f"Actividad 3 – {tit3}: {inst3}")

        # 8. Tabla 4: Actividad de extensión
        if len(doc.tables) >= 5:
            tbl_ext = doc.tables[4]
            if len(tbl_ext.rows) >= 1 and len(tbl_ext.rows[0].cells) >= 1:
                cls._set_cell_text_preserving_runs(tbl_ext.rows[0].cells[0], f"Actividad de extensión y profundización creativa\n{f_data['actividad_extension']}")

        # 9. Actualizar Tabla 5: Lista de Cotejo institucional oficial (4 columnas auténticas)
        if len(doc.tables) >= 6:
            tbl_eval = doc.tables[5]
            crit_list = f_data.get("lista_cotejo") or []
            if not crit_list:
                crit_list = [
                    {"criterio": f"Comprende y explica los conceptos y procedimientos fundamentales de {topic}.", "evidencia": f"Evidencia de {topic}"},
                    {"criterio": f"Aplica destrezas y métodos contextualizados respondiendo al propósito de aprendizaje.", "evidencia": f"Respuestas verificadas de {topic}"}
                ]

            for r_idx, r in enumerate(tbl_eval.rows):
                trPr = r._tr.get_or_add_trPr()
                trPr.append(OxmlElement('w:cantSplit'))
                if r_idx == 0:
                    trPr.append(OxmlElement('w:tblHeader'))

            for idx, c_item in enumerate(crit_list[:4]):
                row_idx = idx + 1
                if row_idx < len(tbl_eval.rows):
                    row = tbl_eval.rows[row_idx]
                else:
                    row = tbl_eval.add_row()
                    trPr = row._tr.get_or_add_trPr()
                    trPr.append(OxmlElement('w:cantSplit'))
                    for c_i, c in enumerate(row.cells):
                        if c_i < len(tbl_eval.rows[1].cells):
                            c.width = tbl_eval.rows[1].cells[c_i].width

                if len(row.cells) >= 4:
                    crit_txt = c_item.get("criterio") or str(c_item)
                    evid_txt = c_item.get("evidencia") or f"Evidencia de {topic}"
                    cls._set_cell_text_preserving_runs(row.cells[0], crit_txt)
                    cls._set_cell_text_preserving_runs(row.cells[1], "[   ]")
                    cls._set_cell_text_preserving_runs(row.cells[2], "[   ]")
                    cls._set_cell_text_preserving_runs(row.cells[3], evid_txt)

        # cantSplit en todas las tablas
        for tbl in doc.tables:
            for r in tbl.rows:
                trPr = r._tr.get_or_add_trPr()
                trPr.append(OxmlElement('w:cantSplit'))

        # 10. Actualizar Metacognición
        meta_q = f_data.get("metacognicion") or "¿Qué aprendí hoy y cómo puedo aplicar este aprendizaje en una situación real?"
        if isinstance(meta_q, dict):
            meta_q = meta_q.get("pregunta") or str(meta_q)

        for p in doc.paragraphs:
            p_low = p.text.strip().lower()
            if "metacognici" in p_low:
                cls._set_p_text_preserving_runs(p, f"Metacognición: {meta_q}")

        # Limpiar cualquier párrafo residual con solucionario genérico
        for p in list(doc.paragraphs):
            p_low = p.text.strip().lower()
            if any(k in p_low for k in [
                "cada ejercicio o pregunta planteada en la ficha debe evaluarse",
                "para respuestas de desarrollo, ponderar el uso correcto",
                "solucionario y clave de respuestas justificadas"
            ]):
                p._element.getparent().remove(p._element)

        # 11. Limpieza Total de Sección 5 e Inserción de Gráfico Pedagógico y Consolidación
        clean_title = topic.strip().strip('"').strip('“').strip('”').upper()
        sec5_p = None
        for p in doc.paragraphs:
            p_low = p.text.strip().lower()
            if p_low.startswith("5."):
                sec5_p = p
                break

        if sec5_p is not None and len(doc.tables) >= 6:
            cls._set_p_text_preserving_runs(sec5_p, f"5. Profundización creativa y soporte gráfico – {clean_title}")
            tbl5_elem = doc.tables[5]._element
            body = doc._body._element
            all_els = list(body)
            s5_idx = all_els.index(sec5_p._element)
            t5_idx = all_els.index(tbl5_elem)
            # Eliminar TODOS los párrafos viejos entre Sección 5 y Tabla 5 (sin importar la hoja)
            for el in all_els[s5_idx + 1:t5_idx]:
                if el.tag.endswith("p"):
                    body.remove(el)

            # Inserción de gráfico pedagógico institucional
            try:
                from app.ai.pedagogical_graphics import resolve_pedagogical_graphic
                from docx.shared import Inches, Pt, RGBColor
                from docx.enum.text import WD_ALIGN_PARAGRAPH
                g_info = resolve_pedagogical_graphic(area, topic)
                if g_info and os.path.exists(g_info["path"]):
                    new_p = doc.add_paragraph()
                    new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = new_p.add_run()
                    run.add_picture(g_info["path"], width=pptx.util.Inches(5.2))

                    cap_p = doc.add_paragraph()
                    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap_run = cap_p.add_run(f"{g_info['title']} — {g_info['caption']}")
                    cap_run.font.size = pptx.util.Pt(8)
                    cap_run.font.italic = True
                    cap_run.font.color.rgb = pptx.dml.color.RGBColor(71, 85, 105)

                    tbl5_elem.addprevious(new_p._element)
                    tbl5_elem.addprevious(cap_p._element)
            except Exception:
                pass

            # Inserción de Ejercicios de Consolidación limpios y específicos del tema
            cons = f_data.get("ejercicios_consolidacion") or []
            if cons:
                h_cons = doc.add_paragraph()
                r_h = h_cons.add_run("Ejercicios de consolidación y aplicación práctica:")
                r_h.bold = True
                tbl5_elem.addprevious(h_cons._element)

                for item in cons[:3]:
                    p_c = doc.add_paragraph()
                    r_c = p_c.add_run(f"• {item}")
                    tbl5_elem.addprevious(p_c._element)

    # -------------------------------------------------------------
    # Rellenado de Fichas de Trabajo Genéricas / Compatibilidad
    # -------------------------------------------------------------
    @classmethod
    def _fill_worksheet_docx_template(cls, doc: Document, data: Dict[str, Any]):
        """Método de retrocompatibilidad que delega a la implementación especializada."""
        cls._fill_student_worksheet_docx_template(doc, data)

    # -------------------------------------------------------------
    # Adaptación Semántica Oficial PPTX por Especialidad (CET N.° 34)
    # -------------------------------------------------------------
    PPTX_SPECIALTY_PRESETS = {
        "emprendimiento": {
            "specialty_name": "Gestión de Proyectos de Emprendimiento",
            "icons": ("💼", "💡", "🚀"),
            "tagline": "Ficha de Aprendizaje 01 • Sesión de Emprendimiento",
            "slide2": {
                "purpose_headline": "Revisar y mejorar nuestra idea de emprendimiento usando el Lean Canvas.",
                "purpose_detail": "Aprenderemos a tomar decisiones basadas en las necesidades reales de los clientes, no solo en suposiciones.",
                "challenge_title": "El reto del modelo de negocio:",
                "challenge_desc": "Muchos proyectos escolares fracasan al no validar la demanda real. ¿Cómo diseñar y probar una propuesta viable y económica?",
                "meta": "Meta: Convertir una idea general en una propuesta de valor viable.",
                "question": "Pregunta: ¿Qué comprarían realmente tus clientes y qué problema les resuelves?"
            },
            "slide3": {
                "header": "Los 9 Bloques Clave del Lean Canvas",
                "cards": [
                    {"tag": "BLOQUE 1", "title": "Problema 🧐", "text": "¿Qué dolor o necesidad tienen las personas? (Listar los 3 principales)."},
                    {"tag": "BLOQUE 4", "title": "Solución 💡", "text": "¿Cómo resolverás el problema con tu producto o servicio?"},
                    {"tag": "BLOQUE 3", "title": "Propuesta Valor 💎", "text": "¿Qué te hace único y especial? ¿Por qué elegirte a ti?"},
                    {"tag": "BLOQUE 9", "title": "Ventaja Clave 👑", "text": "Factor diferencial difícil de copiar o comprar por otros."},
                    {"tag": "BLOQUE 2", "title": "Segmento Clientes 👥", "text": "¿Quiénes son los primeros adoptantes y dónde encontrarlos?"},
                    {"tag": "BLOQUE 8", "title": "Métricas Clave 📊", "text": "¿Cómo medirás el avance y la tracción del negocio?"},
                    {"tag": "BLOQUE 5", "title": "Canales 🚚", "text": "¿Cómo llega tu producto o servicio al cliente final?"}
                ],
                "footer": "El Lean Canvas trabaja con HIPÓTESIS: afirmaciones que debemos validar con la realidad antes de invertir recursos."
            },
            "slide4": {
                "header": "Caso Práctico: Validación de Propuesta de Valor 💼",
                "step1_title": "Problema Detectado",
                "step1_text": "“Clientes potenciales enfrentan necesidades insatisfechas por falta de alternativas viables”.",
                "step2_title": "Propuesta de Valor",
                "step2_text": "“Una propuesta accesible, económica y con entrega oportuna validada en campo”.",
                "step3_title": "Validación de Campo",
                "step3_text": "Entrevistar a 10 usuarios potenciales y realizar una prueba piloto de 3 días.",
                "result": "✅ RESULTADO: El Canvas mejora con evidencia real y testimonios directos",
                "question": "Pregunta para el equipo: ¿Qué respuesta de tus usuarios te obligaría a cambiar la propuesta?"
            },
            "slide5": {
                "header": "Herramientas para Validar en Terreno",
                "q1": {"icon": "🗣️", "title": "Entrevistas", "desc": "Conversa con clientes potenciales. No vendas tu idea, escucha sus problemas reales.", "tip": "Tip: Haz preguntas abiertas como '¿Qué es lo más difícil de...?'"},
                "q2": {"icon": "👀", "title": "Observación", "desc": "Mira cómo actúan tus usuarios. ¿Qué compran realmente? ¿Qué dificultades tienen?", "tip": "Tip: Los hechos reales valen más que las palabras o promesas."},
                "q3": {"icon": "🛠️", "title": "Prototipo Rápido", "desc": "Crea una versión sencilla y rápida (boceto, maqueta, menú) para que la prueben.", "tip": "Tip: Falla rápido y barato para aprender antes de gastar presupuesto."},
                "q4": {"icon": "📈", "title": "Métricas", "desc": "Registra cuántas personas se detuvieron a mirar y cuántas preguntaron por el precio.", "tip": "Tip: Los datos objetivos te ayudan a decidir si sigues o pivotas."}
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción!",
                "challenge_title": "Reto: El Pitch de Validación de 60 Segundos",
                "instructions": "Presenta en equipo tu propuesta:\nProblema + Segmento + Valor diferencial + Estrategia de validación.",
                "timer": "01:00",
                "quote": "\"La mejor forma de predecir el futuro es creándolo en el CET N.° 34.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Identifiqué el problema real y mi segmento de clientes.",
                "item2": "Propuse un método claro para validar mis hipótesis.",
                "item3": "Acepté y apliqué los consejos de mis compañeros.",
                "question": "¿Qué aprendí hoy sobre mi proyecto que no sabía antes de empezar?"
            }
        },
        "mecanica_produccion": {
            "specialty_name": "Mecánica de Producción",
            "icons": ("⚙️", "📐", "🔧"),
            "tagline": "Taller de Máquinas Herramientas • CET N.° 34",
            "slide2": {
                "purpose_headline": "Aprender el procedimiento de torneado y refrentado seguro bajo plano técnico.",
                "purpose_detail": "Aprenderemos a calcular velocidades de corte, calibrar instrumentos y aplicar normas de seguridad 5S en el torno.",
                "challenge_title": "El reto del mecanizado de precisión:",
                "challenge_desc": "Una pieza con tolerancias desfasadas queda inservible y genera mermas costosas. ¿Cómo mecanizar respetando cotas centesimales?",
                "meta": "Meta: Tornear y refrentar la pieza cumpliendo la tolerancia IT8 requerida.",
                "question": "Pregunta: ¿Qué variables de corte evitan vibraciones y rugosidad en la pieza?"
            },
            "slide3": {
                "header": "Fases Técnicas del Mecanizado por Torno",
                "cards": [
                    {"tag": "FASE 1", "title": "Planificación 📋", "text": "Lectura del plano técnico y selección de acero calibrado."},
                    {"tag": "FASE 2", "title": "Metrología 📐", "text": "Verificación de medidas iniciales con pie de rey y micrómetro."},
                    {"tag": "FASE 3", "title": "Parámetros ⚙️", "text": "Cálculo de RPM del husillo según diámetro y material del buril."},
                    {"tag": "FASE 4", "title": "Herramental 🔧", "text": "Centrado de la cuchilla a la altura exacta del contrapunto."},
                    {"tag": "FASE 5", "title": "Mecanizado 🏭", "text": "Cilindrado y refrentado seguro con refrigeración continua."},
                    {"tag": "FASE 6", "title": "Control 5S 🧽", "text": "Retiro de virutas con gancho y limpieza del torno."},
                    {"tag": "FASE 7", "title": "Calidad 🎯", "text": "Inspección de rugosidad superficial y cota dimensional final."}
                ],
                "footer": "El mecanizado exige precisión milimétrica: medir dos veces antes de cortar garantiza cero mermas y seguridad."
            },
            "slide4": {
                "header": "Caso Práctico: Mecanizado de Eje Escalonado ⚙️",
                "step1_title": "Condición Inicial",
                "step1_text": "“Barra de acero SAE 1020 con superficie oxidada y desalineación de 0.8 mm”.",
                "step2_title": "Proceso en Torno",
                "step2_text": "“Refrentado de caras a 550 RPM, centrado y pasada de desbaste a 0.5 mm”.",
                "step3_title": "Control Dimensional",
                "step3_text": "Medición con micrómetro centesimal verificando diámetro objetivo ±0.03 mm.",
                "result": "✅ RESULTADO: Eje terminado conforme a especificación técnica institucional",
                "question": "Pregunta para el equipo: ¿Cómo influye el radio de punta del buril en el acabado final?"
            },
            "slide5": {
                "header": "Herramientas y Métodos de Taller: Mecánica",
                "q1": {"icon": "📐", "title": "Metrología", "desc": "Calibrador vernier, micrómetro y reloj comparador para verificar medidas.", "tip": "Tip: Limpia los topes de medición antes de contrastar el cero."},
                "q2": {"icon": "⚙️", "title": "Torno Paralelo", "desc": "Alineación de carro longitudinal, transversal y charriot para conos.", "tip": "Tip: Retira siempre la llave del mandril antes de poner en marcha el torno."},
                "q3": {"icon": "📋", "title": "Hoja de Proceso", "desc": "Diagrama secuencial de operaciones, tiempos calculados y herramientas.", "tip": "Tip: Planificar las pasadas previene rotura de herramientas y accidentes."},
                "q4": {"icon": "🎯", "title": "Control Calidad", "desc": "Peines de roscas y rugosímetro para verificar tolerancias normalizadas.", "tip": "Tip: Realiza mediciones únicamente con el husillo completamente detenido."}
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción en Taller!",
                "challenge_title": "Reto Técnico: Mecanizado en Puesto de Trabajo",
                "instructions": "Ejecuta en cuadrilla de taller:\n1. Calibración + 2. Montaje y centrado + 3. Cilindrado seguro + 4. Control 5S.",
                "timer": "60:00",
                "quote": "\"La precisión y la seguridad distinguen al técnico calificado del CET N.° 34.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Utilicé lentes de seguridad, mameluco y zapatos con punta de acero.",
                "item2": "Mecanicé la pieza respetando las tolerancias del plano de taller.",
                "item3": "Mantuve el puesto de trabajo limpio y ordenado bajo protocolo 5S.",
                "question": "¿Qué aprendí hoy sobre el mecanizado y qué ajuste dimensional fue el más exigente?"
            }
        },
        "automotriz": {
            "specialty_name": "Mecánica Automotriz",
            "icons": ("🚗", "🔧", "⚡"),
            "tagline": "Taller de Mecánica Automotriz • CET N.° 34",
            "slide2": {
                "purpose_headline": "Diagnosticar y ejecutar el mantenimiento del sistema de frenos bajo manual técnico.",
                "purpose_detail": "Aprenderemos a purgar el sistema hidráulico de frenos y verificar presiones operativas y estanqueidad del circuito.",
                "challenge_title": "El reto del diagnóstico vehicular:",
                "challenge_desc": "Un pedal de freno esponjoso incrementa la distancia de frenado y pone en riesgo vidas. ¿Cómo purgar el circuito y eliminar burbujas?",
                "meta": "Meta: Restablecer la presión hidráulica óptima y purgar el 100% de aire residual.",
                "question": "Pregunta: ¿Qué protocolo de purga asegura que el pedal quede completamente firme?"
            },
            "slide3": {
                "header": "Fases del Servicio y Mantenimiento Automotriz",
                "cards": [
                    {"tag": "FASE 1", "title": "Recepción 🚗", "text": "Inspección perimetral del vehículo y reporte de fallas del conductor."},
                    {"tag": "FASE 2", "title": "Diagnóstico 🔍", "text": "Comprobación del recorrido del pedal e inspección visual de fugas."},
                    {"tag": "FASE 3", "title": "Seguridad ⚠️", "text": "Bloqueo de neumáticos, colocación de caballetes y uso de EPP."},
                    {"tag": "FASE 4", "title": "Desmontaje 🛠️", "text": "Retiro seguro de ruedas y limpieza con limpiador de frenos."},
                    {"tag": "FASE 5", "title": "Purga Sistema ⚙️", "text": "Sustitución de líquido DOT-4 y purga secuencial desde la rueda lejana."},
                    {"tag": "FASE 6", "title": "Torque Ruedas 🔧", "text": "Ajuste de pernos de rueda con torquímetro según manual de taller."},
                    {"tag": "FASE 7", "title": "Prueba Final 📋", "text": "Verificación de frenado progresivo y ausencia total de fugas."}
                ],
                "footer": "En automotriz, la seguridad vial depende de un apriete con torquímetro y purga sin burbujas."
            },
            "slide4": {
                "header": "Caso Práctico: Diagnóstico y Purga de Frenos Hidráulicos 🚗",
                "step1_title": "Falla Reportada",
                "step1_text": "“Vehículo presenta pedal esponjoso que se va al fondo al frenar en pendiente”.",
                "step2_title": "Procedimiento Técnico",
                "step2_text": "“Inspección de cálipers, cambio de líquido degradado y purga en cruz a 2 técnicos”.",
                "step3_title": "Prueba Funcional",
                "step3_text": "Presurización del circuito a 40 bar y comprobación de retorno firme del pedal.",
                "result": "✅ RESULTADO: Sistema hidráulico 100% purgado y frenado balanceado",
                "question": "Pregunta para el equipo: ¿Por qué nunca se debe reutilizar el líquido de frenos purgado?"
            },
            "slide5": {
                "header": "Herramientas y Equipos: Mecánica Automotriz",
                "q1": {"icon": "🔍", "title": "Escáner OBD-II", "desc": "Lectura de códigos de falla DTC en módulos ABS y control del motor.", "tip": "Tip: Anota los códigos antes de borrarlos para llevar la trazabilidad."},
                "q2": {"icon": "🛠️", "title": "Torquímetro", "desc": "Llave dinamométrica para aplicar el par de apriete exacto del fabricante.", "tip": "Tip: Descarga el resorte del torquímetro a cero antes de guardarlo."},
                "q3": {"icon": "📖", "title": "Manual de Taller", "desc": "Diagramas hidráulicos, tolerancias de discos y espesores mínimos de pastillas.", "tip": "Tip: Consulta el orden de purga específico para vehículos con ABS."},
                "q4": {"icon": "🧪", "title": "Pruebas Presión", "desc": "Comprobador de humedad de líquido de frenos y manómetros de presión.", "tip": "Tip: El líquido DOT-4 absorbe agua del ambiente; cámbialo cada 2 años."}
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción en Taller!",
                "challenge_title": "Reto Técnico: Diagnóstico y Servicio en Cuadrilla",
                "instructions": "Ejecuta en cuadrilla automotriz:\n1. Elevación y calces + 2. Desmontaje + 3. Purga hidráulica + 4. Torqueo final.",
                "timer": "60:00",
                "quote": "\"Un servicio automotriz riguroso garantiza vidas seguras en la pista.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Apliqué el protocolo de elevación segura y bloqueé las ruedas.",
                "item2": "Purgué el circuito hidráulico sin derramar líquido sobre la carrocería.",
                "item3": "Torqueé las tuercas de rueda en cruz según especificación técnica.",
                "question": "¿Qué aprendí hoy sobre el sistema de frenos y qué cuidado fue el más crítico?"
            }
        },
        "electricidad": {
            "specialty_name": "Electricidad y Electrónica",
            "icons": ("⚡", "🔌", "💡"),
            "tagline": "Taller de Electrotecnia • CET N.° 34",
            "slide2": {
                "purpose_headline": "Diseñar y cablear tableros de distribución eléctrica bajo el Código Nacional.",
                "purpose_detail": "Aprenderemos a dimensionar interruptores termomagnéticos, calcular calibres de cable y conectar protección diferencial.",
                "challenge_title": "El reto de la instalación eléctrica segura:",
                "challenge_desc": "Las sobrecargas y malas conexiones provocan cortocircuitos e incendios. ¿Cómo cablear un tablero con protección de vidas y equipos?",
                "meta": "Meta: Entregar el circuito balanceado, energizado y libre de caídas de tensión.",
                "question": "Pregunta: ¿Cómo verificamos que la protección diferencial dispara en 30 milisegundos?"
            },
            "slide3": {
                "header": "Fases de la Instalación Eléctrica Residencial",
                "cards": [
                    {"tag": "FASE 1", "title": "Planos ⚡", "text": "Interpretación de diagramas unifilares y cuadro de cargas CNE."},
                    {"tag": "FASE 2", "title": "5 Reglas de Oro 🛡️", "text": "Corte visible, bloqueo, comprobación de ausencia de tensión y tierra."},
                    {"tag": "FASE 3", "title": "Canalizado 🔌", "text": "Fijación de tuberías conduit y cajas de paso octogonales."},
                    {"tag": "FASE 4", "title": "Cableado 🧶", "text": "Tendido de conductores NH-80 respetando código de colores."},
                    {"tag": "FASE 5", "title": "Tablero 🎛️", "text": "Montaje en riel DIN de interruptor termomagnético e ID de 30mA."},
                    {"tag": "FASE 6", "title": "Medición 📊", "text": "Pruebas de continuidad con multímetro y aislamiento de línea."},
                    {"tag": "FASE 7", "title": "Puesta Tierra 🌱", "text": "Conexión de barra de tierra y comprobación con telurómetro (<25Ω)."}
                ],
                "footer": "La electricidad no da segundas oportunidades: verificar siempre ausencia de tensión antes de intervenir."
            },
            "slide4": {
                "header": "Caso Práctico: Tablero de Distribución Domiciliaria ⚡",
                "step1_title": "Falla Detectada",
                "step1_text": "“Circuito de tomacorrientes se sobrecalienta por conductores de calibre insuficiente”.",
                "step2_title": "Instalación Segura",
                "step2_text": "“Reemplazo por cable libre de halógenos 4 mm², balanceo de fases y puesta a tierra”.",
                "step3_title": "Protocolo de Prueba",
                "step3_text": "Medición de voltaje 220V ±3%, prueba de disparo del diferencial y rotulado.",
                "result": "✅ RESULTADO: Tablero certificado bajo norma CNE con protección integral a personas",
                "question": "Pregunta para el equipo: ¿Por qué es obligatorio el interruptor diferencial además del termomagnético?"
            },
            "slide5": {
                "header": "Instrumentos y Métodos: Electrotecnia",
                "q1": {"icon": "🔌", "title": "Multímetro", "desc": "Medición de tensión (V), corriente (A) y continuidad con pitido audible.", "tip": "Tip: Comprueba siempre la escala y bornes correctos antes de medir."},
                "q2": {"icon": "⚡", "title": "Pinza Amperimétrica", "desc": "Medición de corriente de carga sin interrumpir el servicio eléctrico.", "tip": "Tip: Abraza un solo conductor por vez; nunca abraces el cable mellizo junto."},
                "q3": {"icon": "📑", "title": "Diagrama Unifilar", "desc": "Esquema normado de circuitos derivados, calibres y capacidad de corte.", "tip": "Tip: Rotula cada llave con su circuito correspondiente para emergencias."},
                "q4": {"icon": "🌱", "title": "Megóhmetro", "desc": "Verificación de resistencia de aislamiento y resistencia de puesta a tierra.", "tip": "Tip: Una tierra de menos de 25 ohmios desvía corrientes de fuga peligrosas."}
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción en Taller!",
                "challenge_title": "Reto Técnico: Cableado y Pruebas del Circuito",
                "instructions": "Ejecuta en cuadrilla eléctrica:\n1. 5 Reglas de oro + 2. Tendido ordenado + 3. Conexión a borneras + 4. Prueba energizada.",
                "timer": "60:00",
                "quote": "\"La energía bien controlada impulsa con seguridad el taller del CET N.° 34.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Verifiqué la ausencia de tensión con multímetro antes de manipular cables.",
                "item2": "Respeté el código de colores normado (Fase: rojo/negro, Neutro: blanco/azul).",
                "item3": "Ajusté los terminales con torque adecuado evitando falsos contactos.",
                "question": "¿Qué aprendí hoy sobre instalaciones eléctricas y qué medida preventiva fue indispensable?"
            }
        },
        "construcciones_metalicas": {
            "specialty_name": "Construcciones Metálicas",
            "icons": ("🔥", "🛡️", "⚙️"),
            "tagline": "Taller de Soldadura y Construcciones Metálicas • CET N.° 34",
            "slide2": {
                "purpose_headline": "Ejecutar uniones soldadas SMAW en posiciones 1F y 2F bajo norma AWS D1.1.",
                "purpose_detail": "Aprenderemos a calibrar amperajes, mantener arco corto y realizar cordones continuos sin inclusiones de escoria.",
                "challenge_title": "El reto de la estructura soldada:",
                "challenge_desc": "Una unión mal fusionada o con poros compromete la resistencia de una estructura. ¿Cómo lograr un cordón homogéneo y resistente?",
                "meta": "Meta: Soldar la junta a tope cumpliendo penetración total y cero socavados.",
                "question": "Pregunta: ¿Qué ángulo de inclinación y avance garantizan una penetración uniforme?"
            },
            "slide3": {
                "header": "Fases del Proceso de Soldeo y Fabricación Metálica",
                "cards": [
                    {"tag": "FASE 1", "title": "Trazado 📏", "text": "Marcado con rayador, compás de puntas y escuadra de precisión."},
                    {"tag": "FASE 2", "title": "Corte y Bisel ✂️", "text": "Corte por amoladora o cizalla y biselado en V a 60° con talón."},
                    {"tag": "FASE 3", "title": "Punteado 🧲", "text": "Fijación de placas con prensas C manteniendo separación de raíz."},
                    {"tag": "FASE 4", "title": "WPS 📑", "text": "Selección de electrodo E6011 para raíz y regulación de amperaje."},
                    {"tag": "FASE 5", "title": "Soldeo Continuo 🔥", "text": "Pase de raíz y relleno manteniendo arco corto y oscilación."},
                    {"tag": "FASE 6", "title": "Desescoriado 🔨", "text": "Limpieza con piqueta y cepillado profundo de alambre de acero."},
                    {"tag": "FASE 7", "title": "Inspección 🔍", "text": "Control visual de socavados, poros y prueba de doblado guiado."}
                ],
                "footer": "Una soldadura de calidad requiere regulación precisa del amperaje, arco corto y protección visual permanente."
            },
            "slide4": {
                "header": "Caso Práctico: Unión a Tope en Plancha de 6 mm con E6011 🔥",
                "step1_title": "Preparación de Junta",
                "step1_text": "“Bisel en V simple a 60°, talón de raíz de 1.5 mm y separación libre de 2 mm”.",
                "step2_title": "Pase Raíz y Relleno",
                "step2_text": "“Soldadura con E6011 a 75A con arco corto, seguido de pase de presentación con E7018”.",
                "step3_title": "Inspección de Junta",
                "step3_text": "Control visual con galgas de soldadura verificando refuerzo de 1.5 mm sin poros.",
                "result": "✅ RESULTADO: Junta soldada calificada con penetración completa y excelente acabado",
                "question": "Pregunta para el equipo: ¿Cómo evitamos la deformación angular de las planchas por calor?"
            },
            "slide5": {
                "header": "Equipos e Instrumentos: Construcciones Metálicas",
                "q1": {"icon": "📏", "title": "Galgas de Soldar", "desc": "Calibradores para medir altura de refuerzo, garganta y cateto de filete.", "tip": "Tip: Mide la garganta del filete en tres secciones distintas del cordón."},
                "q2": {"icon": "🔥", "title": "Máquina Soldar", "desc": "Inversor electrónico con polaridad directa/inversa y regulación continua.", "tip": "Tip: Asegura la pinza de masa en metal limpio para evitar arco errático."},
                "q3": {"icon": "🛡️", "title": "WPS y Electrodos", "desc": "Especificación técnica de soldadura y conservación de electrodos en termo.", "tip": "Tip: Mantén los electrodos E7018 en termo portátil a 100°C contra la humedad."},
                "q4": {"icon": "🔍", "title": "Inspección Visual", "desc": "Lupa técnica, piqueta y líquidos penetrantes para detectar fisuras.", "tip": "Tip: Desescoria totalmente el pase de raíz antes de aplicar el pase de acabado."}
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción en Taller!",
                "challenge_title": "Reto Técnico: Ejecución de Cordón Calificado",
                "instructions": "Ejecuta en cuadrilla de taller:\n1. EPP completo + 2. Biselado y punteo + 3. Pase continuo + 4. Desescoriado y control.",
                "timer": "60:00",
                "quote": "\"Estructuras sólidas y uniones precisas forjan el prestigio del CET N.° 34.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Utilicé careta con filtro DIN 11, mandil de cuero, escarpines y guantes caña larga.",
                "item2": "Ejecuté el cordón de soldadura manteniendo velocidad constante y arco corto.",
                "item3": "Limpié la escoria y dejé la cabina de soldadura ordenada bajo norma 5S.",
                "question": "¿Qué aprendí hoy sobre soldadura y qué variable fue la más determinante en la penetración?"
            }
        },
        "computacion": {
            "specialty_name": "Computación e Informática",
            "icons": ("💻", "🌐", "🔒"),
            "tagline": "Taller de Redes e Informática • CET N.° 34",
            "slide2": {
                "purpose_headline": "Configurar switches y segmentar redes VLAN con direccionamiento IPv4.",
                "purpose_detail": "Aprenderemos a configurar enlaces troncales 802.1Q, crear subredes y verificar conectividad con ping y traceroute.",
                "challenge_title": "El reto de la conectividad y seguridad de red:",
                "challenge_desc": "Las redes no segmentadas sufren tormentas de broadcast y vulnerabilidades. ¿Cómo aislar el tráfico institucional de forma eficiente?",
                "meta": "Meta: Desplegar la topología de red con 0% de pérdidas de paquetes en pruebas ping.",
                "question": "Pregunta: ¿Por qué los puertos de acceso no deben pertenecer a la VLAN nativa 1?"
            },
            "slide3": {
                "header": "Fases de la Implementación de Redes y Sistemas",
                "cards": [
                    {"tag": "FASE 1", "title": "Topología 💻", "text": "Diseño del diagrama lógico y físico en simulador de red."},
                    {"tag": "FASE 2", "title": "Direccionamiento 📊", "text": "Cálculo de máscaras VLSM y rangos de IP para cada área."},
                    {"tag": "FASE 3", "title": "Cableado Físico 🔌", "text": "Conectorización RJ-45 bajo norma T568B y testeo de par trenzado."},
                    {"tag": "FASE 4", "title": "CLI Switch ⚙️", "text": "Creación de VLANs, nombres y asignación de puertos en consola."},
                    {"tag": "FASE 5", "title": "Troncal 802.1Q 🌐", "text": "Configuración de enlaces troncales entre switches con encapsulación."},
                    {"tag": "FASE 6", "title": "Seguridad 🔒", "text": "Protección de puertos con port-security y contraseñas cifradas."},
                    {"tag": "FASE 7", "title": "Testing 🚀", "text": "Pruebas de conectividad inter-VLAN y documentación final."}
                ],
                "footer": "En informática, documentar la red y respaldar las configuraciones en memoria previene pérdidas críticas."
            },
            "slide4": {
                "header": "Caso Práctico: Configuración de Router y Segmentación VLAN 💻",
                "step1_title": "Problema en Red",
                "step1_text": "“Tráfico broadcast elevado y lentitud generalizada en el aula de innovación pedagógica”.",
                "step2_title": "Configuración CLI",
                "step2_text": "“Creación de VLAN 10 (Dirección) y VLAN 20 (Alumnos) con subinterfaces router-on-a-stick”.",
                "step3_title": "Validación Ping",
                "step3_text": "Pruebas de conectividad con ping continuo y verificación de tabla de enrutamiento.",
                "result": "✅ RESULTADO: Red escolar segmentada, latencia <3ms y seguridad perimetral activa",
                "question": "Pregunta para el equipo: ¿Por qué es fundamental ejecutar 'copy running-config startup-config'?"
            },
            "slide5": {
                "header": "Herramientas y Métodos: Informática y Redes",
                "q1": {"icon": "⌨️", "title": "Consola CLI", "desc": "Línea de comandos IOS para configuración precisa de routers y switches.", "tip": "Tip: Usa el comando 'show running-config' para auditar antes de guardar cambios."},
                "q2": {"icon": "🌐", "title": "Packet Tracer", "desc": "Simulador visual de topologías, pruebas de ping y análisis de paquetes ICMP.", "tip": "Tip: El modo simulación paso a paso permite visualizar el recorrido exacto de la trama."},
                "q3": {"icon": "🔧", "title": "Crimpadora RJ-45", "desc": "Herramienta de ponchado y probador de cables para certificar enlaces.", "tip": "Tip: Destrenza los pares lo mínimo necesario para mantener la inmunidad al ruido."},
                "q4": {"icon": "📊", "title": "Wireshark / Ping", "desc": "Analizador de protocolos en tiempo real para diagnosticar microcortes y DNS.", "tip": "Tip: Filtra por protocolo 'bootp' o 'arp' para aislar problemas de asignación DHCP."}
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción en Taller!",
                "challenge_title": "Reto Técnico: Configuración y Verificación de Red",
                "instructions": "Ejecuta en cuadrilla de informática:\n1. Topología + 2. Scripts CLI + 3. Port-Security + 4. Ping de verificación 100% OK.",
                "timer": "60:00",
                "quote": "\"La conectividad confiable y segura transforma el aprendizaje en el CET N.° 34.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Apliqué normas de seguridad eléctrica al manipular equipos de red y racks.",
                "item2": "Configuré las VLANs y enlaces troncales verificando la conectividad de hosts.",
                "item3": "Respaldé la configuración activa en memoria y documenté las direcciones IP.",
                "question": "¿Qué aprendí hoy sobre redes y qué comando fue clave para verificar la conectividad?"
            }
        },
        "computacion_ofimatica": {
            "specialty_name": "Computación e Informática",
            "icons": ("💻", "📁", "🔒"),
            "tagline": "Taller de Computación e Informática • CET N.° 34",
            "slide2": {
                "purpose_headline": "Crear, estructurar y gestionar carpetas y archivos digitales de forma ordenada y segura.",
                "purpose_detail": "Aprenderemos a estructurar árboles de carpetas, aplicar nombres normalizados y realizar copias de respaldo.",
                "challenge_title": "El reto del orden y seguridad digital:",
                "challenge_desc": "Archivos dispersos en el escritorio provocan pérdida de tareas escolares. ¿Cómo estructurar un árbol de carpetas eficiente?",
                "meta": "Meta: Organizar el portafolio escolar digital en carpetas temáticas sin archivos duplicados.",
                "question": "Pregunta: ¿Por qué es fundamental tener una estructura lógica de carpetas en la computadora y en la nube?"
            },
            "slide3": {
                "header": "7 Pasos Clave para Gestionar Carpetas Digitales",
                "cards": [
                    {"tag": "PASO 1", "title": "Explorador 💻", "text": "Navegación por unidades y accesos rápidos de Windows."},
                    {"tag": "PASO 2", "title": "Nueva Carpeta 📁", "text": "Creación de carpetas raíz y subcarpetas por áreas."},
                    {"tag": "PASO 3", "title": "Nomenclatura 🏷️", "text": "Formato estándar: Fecha_Materia_Tarea_Apellidos."},
                    {"tag": "PASO 4", "title": "Extensiones 📄", "text": "Reconocimiento de formatos (.docx, .pdf, .xlsx, .pptx)."},
                    {"tag": "PASO 5", "title": "Mover y Copiar 🔄", "text": "Organización limpia arrastrando o usando Ctrl+X y Ctrl+V."},
                    {"tag": "PASO 6", "title": "Nube Digital ☁️", "text": "Sincronización en Google Drive o OneDrive institucional."},
                    {"tag": "PASO 7", "title": "Copias Backup 🛡️", "text": "Regla 3-2-1 para proteger evidencias contra pérdidas."}
                ],
                "footer": "En informática, un portafolio de carpetas bien organizado ahorra tiempo y garantiza la seguridad de tu información."
            },
            "slide4": {
                "header": "Caso Práctico: Organización del Portafolio Digital Escolar 💻",
                "step1_title": "Diagnóstico Inicial",
                "step1_text": "“Escritorio con 25 archivos sueltos y nombres confusos como 'trabajo1.docx'”.",
                "step2_title": "Estructura en Árbol",
                "step2_text": "“Creación de la carpeta 'Portafolio_2026' con 5 subcarpetas por asignaturas”.",
                "step3_title": "Clasificación y Backup",
                "step3_text": "Se renombran los archivos con fecha y materia, sincronizando una copia en la nube.",
                "result": "✅ RESULTADO: Portafolio 100% ordenado, archivos ubicables en <5 segundos y respaldo activo",
                "question": "Pregunta para el equipo: ¿Qué ventajas tiene ordenar por carpetas frente a guardar todo en el escritorio?"
            },
            "slide5": {
                "header": "Herramientas y Métodos: Gestión de Carpetas Digitales",
                "q1": {
                    "icon": "📁",
                    "title": "Explorador Windows",
                    "desc": "Gestor nativo para navegar, estructurar y buscar archivos con filtros avanzados.",
                    "tip": "Tip: Usa el atajo 'Win + E' para abrir directamente el Explorador de Archivos."
                },
                "q2": {
                    "icon": "☁️",
                    "title": "Nube Escolar",
                    "desc": "Google Drive y OneDrive para sincronizar evidencias escolares automáticamente.",
                    "tip": "Tip: Mantén la misma estructura de carpetas en tu PC y en la nube."
                },
                "q3": {
                    "icon": "🏷️",
                    "title": "Nomenclatura Limpia",
                    "desc": "Reglas de nombres sin caracteres especiales (?, /, *) y con fechas ordenables.",
                    "tip": "Tip: Usa guiones bajos (Archivo_01) en lugar de espacios dobles."
                },
                "q4": {
                    "icon": "🛡️",
                    "title": "Seguridad y Copias",
                    "desc": "Antivirus activo y almacenamiento secundario en memoria USB o disco externo.",
                    "tip": "Tip: Realiza una copia de seguridad semanal de tus proyectos importantes."
                }
            },
            "slide6": {
                "header": "🚀 ¡Hora de la Acción en el Laboratorio!",
                "challenge_title": "Reto Técnico: Estructura tu Portafolio Digital",
                "instructions": "Ejecuta en tu computadora:\n1. Crea la carpeta raíz con tu nombre.\n2. Genera 4 subcarpetas por áreas.\n3. Guarda un archivo de prueba en cada una.\n4. Verifica en pantalla.",
                "timer": "40:00",
                "quote": "\"El orden digital potencia tu productividad y protege tu esfuerzo escolar en el CET N.° 34.\""
            },
            "slide7": {
                "header": "Reflexionamos y Cerramos 🏁",
                "label": "CRITERIOS DE LOGRO Y AUTOEVALUACIÓN:",
                "item1": "Creé y estructuré carpetas y subcarpetas con jerarquía lógica.",
                "item2": "Apliqué nombres normalizados reconociendo las extensiones de archivo.",
                "item3": "Comprendí la importancia del almacenamiento seguro y las copias de respaldo.",
                "question": "¿De qué manera la organización de carpetas digitales mejorará mi rendimiento escolar?"
            }
        }
    }

    @classmethod
    def detect_pptx_specialty_key(cls, specialty_str: str, topic_str: str = "") -> str:
        """
        Determina de manera unívoca la especialidad técnica oficial (6 especialidades CET N.° 34)
        a partir de la especialidad declarada y/o el tema curricular.
        """
        def _norm(txt: str) -> str:
            val = (txt or "").lower()
            for src, dst in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
                val = val.replace(src, dst)
            return val

        s = _norm(specialty_str)
        t = _norm(topic_str)

        # Detección directa por especialidad
        if any(k in s for k in ["automotr", "vehicul", "freno", "inyecc"]):
            return "automotriz"
        elif any(k in s for k in ["producc", "mecaniz", "torno", "fresa", "viruta", "ajuste mec"]):
            return "mecanica_produccion"
        elif any(k in s for k in ["metal", "soldad", "calderer"]):
            return "construcciones_metalicas"
        elif any(k in s for k in ["electr", "circuito", "tablero", "tension"]):
            return "electricidad"
        elif any(k in s for k in ["comput", "inform", "red", "software", "programac", "sistema"]):
            return "computacion"
        elif any(k in s for k in ["emprend", "lean canvas", "negocio", "gestion"]):
            return "emprendimiento"

        # Detección contextual por tema si la especialidad es genérica
        if any(k in t for k in ["freno", "automotr", "embrague", "caja de cambio", "culata", "suspension", "neumatic"]):
            return "automotriz"
        elif any(k in t for k in ["torno", "fresador", "mecaniz", "buril", "viruta", "refrentad", "cilindrad", "arranque", "5s", "seguridad", "taller", "epp", "prevencion"]):
            return "mecanica_produccion"
        elif any(k in t for k in ["soldad", "electrodo", "smaw", "gmaw", "gtaw", "metalic", "trazado", "oxicorte"]):
            return "construcciones_metalicas"
        elif any(k in t for k in ["electr", "pozo a tierra", "termomagnet", "diferencial", "luminari", "voltaje", "tablero"]):
            return "electricidad"
        elif any(k in t for k in ["comput", "servidor", "red", "cableado estructurad", "switch", "router", "vlan", "dhcp"]):
            return "computacion"

        return "emprendimiento"

    @classmethod
    def _set_pptx_shape_text_safe(
        cls,
        shape,
        new_text: str,
        base_font_size_pt: Optional[float] = None,
        min_font_size_pt: float = 7.0,
        max_chars: Optional[int] = None,
        bold: Optional[bool] = None,
        font_name: Optional[str] = None,
        color_rgb: Any = None
    ):
        """
        Actualiza el texto de una forma PowerPoint (.pptx) validando estrictamente que no se desborde.
        Garantías:
        1. Activa word_wrap = True en el marco de texto.
        2. Configura auto_size a TEXT_TO_FIT_SHAPE para permitir reducción automática en PowerPoint.
        3. Limita los caracteres (max_chars) con corte respetuoso en límites de palabra.
        4. Calcula la escala tipográfica dinámica en puntos (Pt) según la longitud del texto.
        5. Preserva la familia tipográfica (ej. Rubik Bold, Calibri), negrita y color institucional.
        6. Soporta párrafos multilínea sin destruir propiedades XML de los runs.
        """
        if not shape or not shape.has_text_frame:
            return

        tf = shape.text_frame
        tf.word_wrap = True
        if MSO_AUTO_SIZE is not None and hasattr(MSO_AUTO_SIZE, "TEXT_TO_FIT_SHAPE"):
            try:
                tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
            except Exception:
                pass

        p0 = tf.paragraphs[0] if tf.paragraphs else None
        r0 = p0.runs[0] if (p0 and p0.runs) else None

        eff_font_name = font_name or (r0.font.name if r0 and r0.font.name else "Calibri")
        eff_bold = bold if bold is not None else (r0.font.bold if r0 else False)
        eff_color = color_rgb or (r0.font.color.rgb if (r0 and r0.font.color and r0.font.color.type == 1) else None)
        orig_size_pt = r0.font.size.pt if (r0 and r0.font.size) else None
        eff_base_pt = base_font_size_pt or orig_size_pt or 11.0

        clean_text = str(new_text or "").strip()
        if max_chars and len(clean_text) > max_chars:
            cutoff = max_chars - 3
            space_idx = clean_text[:cutoff].rfind(" ")
            if space_idx > int(max_chars * 0.6):
                clean_text = clean_text[:space_idx].rstrip() + "..."
            else:
                clean_text = clean_text[:cutoff].rstrip() + "..."

        # Ajuste dinámico de escala de fuente anti-desbordamiento
        str_len = len(clean_text)
        if eff_base_pt >= 30:
            if str_len > 50:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.60)
            elif str_len > 35:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.75)
            elif str_len > 25:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.88)
            else:
                target_pt = eff_base_pt
        elif eff_base_pt >= 20:
            if str_len > 55:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.75)
            elif str_len > 40:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.85)
            else:
                target_pt = eff_base_pt
        elif eff_base_pt >= 13:
            if str_len > 55:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.78)
            elif str_len > 40:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.88)
            else:
                target_pt = eff_base_pt
        else:
            if str_len > 90:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.82)
            elif str_len > 60:
                target_pt = max(min_font_size_pt, eff_base_pt * 0.90)
            else:
                target_pt = eff_base_pt

        lines = clean_text.split("\n")
        while len(tf.paragraphs) > 1:
            p_elem = tf.paragraphs[-1]._p
            p_elem.getparent().remove(p_elem)

        p0 = tf.paragraphs[0]
        while len(p0.runs) > 1:
            r_elem = p0.runs[-1]._r
            r_elem.getparent().remove(r_elem)

        if p0.runs:
            r0 = p0.runs[0]
            r0.text = lines[0]
        else:
            r0 = p0.add_run()
            r0.text = lines[0]

        if eff_font_name:
            r0.font.name = eff_font_name
        if target_pt and PptxPt is not None:
            r0.font.size = Pptxpptx.util.Pt(target_pt)
        if eff_bold is not None:
            r0.font.bold = eff_bold
        if eff_color:
            try:
                r0.font.color.rgb = eff_color
            except Exception:
                pass

        for line in lines[1:]:
            p_next = tf.add_paragraph()
            r_next = p_next.add_run()
            r_next.text = line
            if eff_font_name:
                r_next.font.name = eff_font_name
            if target_pt and PptxPt is not None:
                r_next.font.size = Pptxpptx.util.Pt(target_pt)
            if eff_bold is not None:
                r_next.font.bold = eff_bold
            if eff_color:
                try:
                    r_next.font.color.rgb = eff_color
                except Exception:
                    pass

    @classmethod
    def validate_pptx_text_fit(cls, prs) -> Dict[str, Any]:
        """
        Audita los marcos de texto de la presentación verificando que tengan activo word_wrap
        y auto_size sin violaciones de desbordamiento de límites.
        """
        total_shapes = 0
        fitted_shapes = 0
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame and shape.text.strip():
                    total_shapes += 1
                    tf = shape.text_frame
                    if tf.word_wrap:
                        fitted_shapes += 1

        return {
            "total_text_shapes": total_shapes,
            "fitted_shapes": fitted_shapes,
            "overflow_free": (total_shapes == fitted_shapes),
            "ratio": round(fitted_shapes / max(1, total_shapes), 2)
        }

    # -------------------------------------------------------------
    # Rellenado de Presentaciones PowerPoint Institucionales (.pptx)
    # -------------------------------------------------------------
    @classmethod
    def extract_slide_config_from_markdown(cls, md_text: str):
        """
        Analiza el texto markdown generado por la IA y extrae la configuración estructurada
        de las 7 diapositivas con limpieza semántica profunda (eliminando etiquetas meta como
        'Propósito:', 'Situación de Reto:', 'Pregunta Detonante:', 'Resultado:', asteriscos markdown, etc.).
        """
        if not md_text or "DIAPOSITIVA" not in md_text.upper():
            return None

        import re
        parts = re.split(r'DIAPOSITIVA\s*(\d+)\s*[:\-]', md_text, flags=re.IGNORECASE)
        slides = {}
        for i in range(1, len(parts), 2):
            try:
                s_num = int(parts[i])
                slides[s_num] = parts[i+1].strip()
            except Exception:
                pass

        if len(slides) < 3:
            return None

        def clean_field(s: str) -> str:
            if not s:
                return ""
            s = re.sub(r'^(?:prop[oó]sito|situaci[oó]n(?:\s+de)?\s+reto|reto|pregunta(?:\s+detonante|\s+reflexiva)?|resultado|t[ií]tulo(?:\s+oficial|\s+del\s+caso\s+pr[aá]ctico|\s+del\s+marco\s+conceptual|\s+del\s+reto[^\:]*)?|paso\s*\d+|lema(?:\s+motivador)?)\s*[:\-]\s*', '', s, flags=re.IGNORECASE)
            s = re.sub(r'[*_#`]', '', s)
            s = s.strip(' \t\n\r"\'•-–—+[]')
            return s.strip()

        cfg = {}

        # SLIDE 2: Propósito y Reto
        s2 = slides.get(2, "")
        p_head, chal_d, chal_q = "", "", ""
        for l in s2.split('\n'):
            l_str = l.strip()
            if not l_str:
                continue
            l_low = l_str.lower()
            if "diapositiva" in l_low or "portada" in l_low:
                continue
            if ("propósito:" in l_low or "proposito:" in l_low) and not p_head:
                p_head = clean_field(l_str)
            elif ("reto:" in l_low or "situación" in l_low) and ":" in l_str and not chal_d:
                chal_d = clean_field(l_str)
            elif ("pregunta" in l_low or "?" in l_str or "¿" in l_str) and not chal_q:
                chal_q = clean_field(l_str)

        cfg["slide2"] = {
            "purpose_headline": p_head[:160] if p_head else "",
            "purpose_detail": "Desarrollaremos competencias formativas y evidencias de aprendizaje orientadas a la indagación, argumentación y resolución de problemas.",
            "challenge_title": "El Reto de la Sesión",
            "challenge_desc": chal_d[:180] if chal_d else "",
            "question": chal_q[:140] if chal_q else ""
        }

        # SLIDE 3: Conceptos Clave
        s3 = slides.get(3, "")
        s3_lines = [l.strip() for l in s3.split('\n') if l.strip()]
        h3 = "Conceptos y Fundamentos Clave"
        concepts = []
        for line in s3_lines:
            c_low = line.lower()
            if any(k in c_low for k in ["fundamentos y", "7 conceptos", "pasos clave", "diapositiva", "título"]):
                continue
            if ":" in line:
                t_raw, d_raw = line.split(":", 1)
                t_val = clean_field(t_raw)
                d_val = clean_field(d_raw).replace("a la ribosoma", "al ribosoma")
                if len(t_val) >= 3 and len(d_val) >= 8:
                    concepts.append((t_val[:45], d_val[:220]))
            elif len(line) > 10 and not concepts:
                concepts.append(("Concepto Principal", clean_field(line)[:220]))

        cards = []
        for i, (ct, cd) in enumerate(concepts[:4]):
            cards.append({"tag": f"CONCEPTO {i+1}", "title": ct, "text": cd})

        cfg["slide3"] = {
            "header": h3[:60],
            "cards": cards
        }

        # SLIDE 4: Caso Práctico Modelado (Multi-línea robusto)
        s4 = slides.get(4, "")
        h4 = "Caso Práctico Modelado Paso a Paso"
        res4 = ""
        raw_steps = []
        current_step = None

        for l in s4.split('\n'):
            l_str = l.strip()
            if not l_str:
                continue
            l_low = l_str.lower()
            if "título:" in l_low or "titulo:" in l_low:
                h4 = clean_field(l_str)
            elif re.search(r'^(?:\*\*)?paso\s*([123])', l_low):
                m_p = re.search(r'^(?:\*\*)?paso\s*([123])\s*[:\-]\s*(.*)', l_str, flags=re.IGNORECASE)
                rest = m_p.group(2) if m_p and m_p.group(2) else ""
                if ":" in rest:
                    p_title, p_desc = rest.split(":", 1)
                    st_title = clean_field(p_title)
                    st_desc = clean_field(p_desc)
                    current_step = {"title": st_title or f"Paso {len(raw_steps)+1}", "desc": [st_desc] if st_desc else []}
                elif " - " in rest:
                    p_title, p_desc = rest.split(" - ", 1)
                    st_title = clean_field(p_title)
                    st_desc = clean_field(p_desc)
                    current_step = {"title": st_title or f"Paso {len(raw_steps)+1}", "desc": [st_desc] if st_desc else []}
                else:
                    st_title = clean_field(rest) if rest else f"Paso {len(raw_steps)+1}"
                    if len(st_title) > 28:
                        words = st_title.split()
                        st_title = " ".join(words[:3])
                    current_step = {"title": st_title, "desc": []}
                raw_steps.append(current_step)
            elif "resultado:" in l_low:
                res4 = clean_field(l_str)
                current_step = None
            elif "pregunta" in l_low:
                current_step = None
            elif current_step is not None:
                cf = clean_field(l_str)
                if cf:
                    current_step["desc"].append(cf)

        steps = []
        default_step_titles = ["Diagnóstico Inicial", "Procedimiento Aplicado", "Validación y Resultado"]
        for i, st_obj in enumerate(raw_steps[:3]):
            s_desc = " ".join(st_obj["desc"]).strip() if st_obj["desc"] else "Ejecución técnica del procedimiento planificado."
            s_title = st_obj["title"] if len(st_obj["title"]) >= 3 and not st_obj["title"].lower().startswith("paso") else default_step_titles[i]
            steps.append((s_title[:40], s_desc[:240]))

        cfg["slide4"] = {
            "header": h4[:60],
            "steps": steps,
            "result": res4[:240] if res4 else ""
        }

        # SLIDE 5: Herramientas y Técnicas (con vinculación precisa de Tips)
        s5 = slides.get(5, "")
        tools = []
        current_tool = None
        for l in s5.split('\n'):
            l_str = l.strip()
            if not l_str:
                continue
            l_low = l_str.lower()
            if any(k in l_low for k in ["herramientas, métodos", "herramientas y métodos", "buenas prácticas", "diapositiva 5", "4 pautas"]):
                if ":" not in l_str or "4 pautas" in l_low:
                    continue
            if "|" in l_str and "tip:" in l_low:
                parts = l_str.split("|", 1)
                main_part = parts[0].strip()
                tip_part = clean_field(re.sub(r'^tip(?:\s+pr[aá]ctico)?\s*[:\-]\s*', '', parts[1].strip(), flags=re.IGNORECASE))
                if ":" in main_part:
                    t_p, d_p = main_part.split(":", 1)
                    t_c = clean_field(t_p)
                    d_c = clean_field(d_p)
                    if len(t_c) >= 3:
                        current_tool = [t_c[:45], d_c[:200], tip_part[:180]]
                        tools.append(current_tool)
                        continue
            elif l_low.startswith("tip:") or l_low.startswith("tip práctico:") or "tip:" in l_low[:10]:
                t_tip = clean_field(re.sub(r'^tip(?:\s+pr[aá]ctico)?\s*[:\-]\s*', '', l_str, flags=re.IGNORECASE))
                if current_tool:
                    current_tool[2] = t_tip[:180]
            elif ":" in l_str:
                t_p, d_p = l_str.split(":", 1)
                t_clean = clean_field(t_p)
                d_clean = clean_field(d_p)
                if any(k in t_clean.lower() for k in ["herramientas, métodos", "diapositiva", "pautas"]):
                    continue
                if len(t_clean) >= 3 and len(d_clean) >= 5:
                    current_tool = [t_clean[:45], d_clean[:200], ""]
                    tools.append(current_tool)

        cfg["slide5"] = {
            "header": "Métodos, Tecnologías y Buenas Prácticas",
            "tools": tools[:4]
        }

        # SLIDE 6: Reto Práctico
        s6 = slides.get(6, "")
        s6_title = ""
        s6_instruct = []
        s6_quote = ""
        s6_time = "20:00 min"
        in_inst = False
        for l in s6.split('\n'):
            l_str = l.strip()
            if not l_str:
                continue
            l_low = l_str.lower()
            if ("título:" in l_low or "reto:" in l_low) and not s6_title and "instruccion" not in l_low:
                s6_title = clean_field(l_str)
            elif "instruccion" in l_low:
                in_inst = True
                continue
            elif ("lema" in l_low or "motivador" in l_low or "frase" in l_low) and not s6_quote:
                s6_quote = clean_field(l_str)
                in_inst = False
            elif "tiempo" in l_low and ("minuto" in l_low or "min" in l_low):
                m_t = re.search(r'(\d+)\s*(?:minutos|min)', l_low)
                if m_t:
                    s6_time = f"{m_t.group(1)}:00 min"
                in_inst = False
            elif in_inst and len(l_str) > 5:
                s6_instruct.append(clean_field(l_str))
            elif re.match(r'^\d+[\.\)]', l_str) or l_str.startswith("-") or l_str.startswith("•"):
                s6_instruct.append(clean_field(l_str))

        cfg["slide6"] = {
            "header": "¡Hora de la Acción! Reto de Aprendizaje",
            "title": s6_title[:70],
            "instructions": "\n".join(s6_instruct[:4]) if s6_instruct else "",
            "time": s6_time,
            "quote": s6_quote[:150]
        }

        # SLIDE 7: Metacognición
        s7 = slides.get(7, "")
        s7_crit = []
        s7_q = []
        in_questions = False
        for l in s7.split('\n'):
            l_str = l.strip()
            if not l_str:
                continue
            l_low = l_str.lower()
            if "diapositiva" in l_low:
                continue
            if "pregunta" in l_low and ("metacognitiva" in l_low or "clave" in l_low):
                in_questions = True
                continue
            if in_questions and ("?" in l_str or "¿" in l_str or re.match(r'^\d+[\.\)]', l_str)):
                s7_q.append(clean_field(l_str))
            elif not in_questions and ("criterio" in l_low or "☑" in l_str or re.match(r'^\d+[\.\)]', l_str) or l_str.startswith("-") or l_str.startswith("•")):
                cf = clean_field(l_str)
                if len(cf) > 10 and not any(k in cf.lower() for k in ["criterios de autoevaluación", "preguntas clave", "metacognitivas"]):
                    s7_crit.append(cf)
            elif not in_questions and ("?" in l_str or "¿" in l_str):
                cf_q = clean_field(l_str)
                if not any(k in cf_q.lower() for k in ["qué aprendí hoy", "cómo lo aprendí", "para qué me servirá"]):
                    s7_q.append(cf_q)

        cfg["slide7"] = {
            "header": "Reflexionamos y Evaluación Formativa",
            "criteria": s7_crit[:3],
            "questions": s7_q[:3]
        }

        return cfg

    @classmethod
    def generate_native_ai_pptx(cls, doc_data: Dict[str, Any]) -> bytes:
        """
        Generador Nativo 100% IA de Presentaciones PowerPoint (.pptx).
        Diseña desde cero una presentación panorámica moderna (16:9 Widescreen HD)
        con paletas cromáticas adaptadas al área curricular, membrete oficial de la
        I.E. INEI N.° 34 de Chancay, diagramas educativos en alta resolución y
        tarjetas de contenido perfectamente estructuradas sin textos cortados ni desbordamientos.
        """
        if pptx is None:
            raise RuntimeError("La librería python-pptx no está disponible.")

        topic = doc_data.get("topic") or doc_data.get("title") or "Sesión de Aprendizaje"
        specialty_raw = doc_data.get("specialty") or "Educación Secundaria"
        grade = doc_data.get("grade") or 1
        teacher_name = doc_data.get("teacher_name") or "Prof. Roberto Bazán Palacios"
        content_md = doc_data.get("content_markdown") or ""

        text_theme = (specialty_raw + " " + topic).lower()
        if any(k in text_theme for k in ["computac", "comput", "informat", "carpeta", "archivo", "ofimat", "word", "excel", "windows", "digital", "software", "redes"]):
            primary = pptx.dml.color.RGBColor(26, 54, 93)      # Azul cobalto / Marino tecnológico
            accent = pptx.dml.color.RGBColor(49, 130, 206)     # Celeste vivo
            light_bg = pptx.dml.color.RGBColor(240, 248, 255)  # Fondo azul tenue
            area_name = "Computación e Informática" if "inform" in text_theme else "Computación"
        elif any(k in text_theme for k in ["matematic", "matemátic", "algebra", "álgebra", "geometr", "trigonom", "calculo", "aritm"]):
            primary = pptx.dml.color.RGBColor(30, 58, 138)     # Azul Rey matemático
            accent = pptx.dml.color.RGBColor(59, 130, 246)     # Azul eléctrico
            light_bg = pptx.dml.color.RGBColor(239, 246, 255)  # Hielo matemático
            area_name = "Matemática"
        elif any(k in text_theme for k in ["comunicac", "lengua", "literat", "redacc", "gramat", "comprensión lectora"]):
            primary = pptx.dml.color.RGBColor(159, 18, 57)     # Rojo Carmín / Burdeos literario
            accent = pptx.dml.color.RGBColor(225, 29, 72)      # Frambuesa vivo
            light_bg = pptx.dml.color.RGBColor(255, 241, 242)  # Rosa pálido elegante
            area_name = "Comunicación"
        elif any(k in text_theme for k in ["social", "historia", "geograf", "economia", "economía", "neolit", "hominiz", "inca", "cultura", "ecorregion", "caral"]):
            primary = pptx.dml.color.RGBColor(123, 52, 30)     # Terracota / Bronce histórico
            accent = pptx.dml.color.RGBColor(192, 86, 33)      # Ámbar tostado
            light_bg = pptx.dml.color.RGBColor(255, 245, 240)  # Pergamino suave
            area_name = "Ciencias Sociales"
        elif any(k in text_theme for k in ["dpcc", "desarrollo personal", "ciudadan", "civica", "cívica", "emocion", "autoestima", "derecho", "convivencia"]):
            primary = pptx.dml.color.RGBColor(85, 60, 154)     # Púrpura cívico institucional
            accent = pptx.dml.color.RGBColor(128, 90, 213)     # Violeta vivo
            light_bg = pptx.dml.color.RGBColor(250, 245, 255)  # Lila suave
            area_name = "Desarrollo Personal, Ciudadanía y Cívica"
        elif any(k in text_theme for k in ["arte", "danza", "musica", "música", "teatro", "pintura", "dibujo"]):
            primary = pptx.dml.color.RGBColor(147, 51, 234)    # Violeta artístico
            accent = pptx.dml.color.RGBColor(236, 72, 153)     # Fucsia creativo
            light_bg = pptx.dml.color.RGBColor(253, 244, 255)  # Orquídea suave
            area_name = "Arte y Cultura"
        elif any(k in text_theme for k in ["ingles", "inglés", "english"]):
            primary = pptx.dml.color.RGBColor(15, 76, 129)     # Classic Navy Blue
            accent = pptx.dml.color.RGBColor(217, 119, 6)      # Gold Accent
            light_bg = pptx.dml.color.RGBColor(241, 245, 249)  # Slate tenue
            area_name = "Inglés como Lengua Extranjera"
        elif any(k in text_theme for k in ["religio", "fe", "valores", "biblia", "cristian"]):
            primary = pptx.dml.color.RGBColor(120, 53, 15)     # Ámbar cálido sagrado
            accent = pptx.dml.color.RGBColor(217, 119, 6)      # Dorado
            light_bg = pptx.dml.color.RGBColor(254, 252, 232)  # Marfil cálido
            area_name = "Educación Religiosa"
        elif any(k in text_theme for k in ["fisica", "física", "deporte", "cardiac", "motriz", "atletismo", "salud", "nutricion"]):
            primary = pptx.dml.color.RGBColor(40, 116, 101)    # Verde azulado deportivo
            accent = pptx.dml.color.RGBColor(56, 178, 172)     # Turquesa enérgico
            light_bg = pptx.dml.color.RGBColor(230, 255, 250)  # Menta suave
            area_name = "Educación Física"
        elif any(k in text_theme for k in ["ciencia", "tecnolog", "cyt", "celul", "adn", "arn", "quimic", "ecosistema", "materia", "energia", "biolog"]):
            primary = pptx.dml.color.RGBColor(20, 82, 55)      # Verde bosque de laboratorio
            accent = pptx.dml.color.RGBColor(16, 185, 129)     # Esmeralda brillante
            light_bg = pptx.dml.color.RGBColor(240, 253, 244)  # Verde tenue
            area_name = "Ciencia y Tecnología"
        elif any(k in text_theme for k in ["estetica", "estética", "cosmetol", "peinado", "corte de cabello"]):
            primary = pptx.dml.color.RGBColor(190, 24, 93)     # Rosa estilismo
            accent = pptx.dml.color.RGBColor(244, 114, 182)    # Rosa suave
            light_bg = pptx.dml.color.RGBColor(253, 242, 248)  # Fondo rosa tenue
            area_name = "Estética Personal"
        elif any(k in text_theme for k in ["contabil", "finanz", "tribut", "balance"]):
            primary = pptx.dml.color.RGBColor(15, 118, 110)    # Verde esmeralda contable
            accent = pptx.dml.color.RGBColor(20, 184, 166)     # Teal vivo
            light_bg = pptx.dml.color.RGBColor(240, 253, 250)  # Menta contable tenue
            area_name = "Contabilidad"
        elif any(k in text_theme for k in ["ebanist", "mader"]):
            primary = pptx.dml.color.RGBColor(120, 53, 15)     # Nogal cálido
            accent = pptx.dml.color.RGBColor(180, 83, 9)       # Madera miel
            light_bg = pptx.dml.color.RGBColor(254, 252, 232)  # Fondo madera claro
            area_name = "Ebanistería"
        elif any(k in text_theme for k in ["mecanic", "electric", "automotriz", "torno", "soldadur"]):
            primary = pptx.dml.color.RGBColor(156, 66, 33)     # Ocre técnico industrial
            accent = pptx.dml.color.RGBColor(221, 107, 32)     # Naranja industrial
            light_bg = pptx.dml.color.RGBColor(255, 250, 240)  # Marfil industrial
            area_name = specialty_raw.replace("Educación para el Trabajo - ", "").strip()
        else:
            primary = pptx.dml.color.RGBColor(160, 24, 24)     # Rojo Granate oficial INEI N.° 34
            accent = pptx.dml.color.RGBColor(46, 125, 50)      # Verde oficial INEI N.° 34
            light_bg = pptx.dml.color.RGBColor(253, 251, 247)  # Crema institucional
            area_name = specialty_raw or "Educación Secundaria"

        white = pptx.dml.color.RGBColor(255, 255, 255)
        dark_text = pptx.dml.color.RGBColor(30, 41, 59)
        muted_text = pptx.dml.color.RGBColor(100, 116, 139)

        prs = pptx.Presentation()
        prs.slide_width = pptx.util.Inches(13.333)
        prs.slide_height = pptx.util.Inches(7.5)
        blank_layout = prs.slide_layouts[6]
        insignia_path = 'app/static/insignia.png' if os.path.exists('app/static/insignia.png') else None

        def add_bg(s, color):
            sh = s.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.RECTANGLE, 0, 0, pptx.util.Inches(13.333), pptx.util.Inches(7.5))
            sh.fill.solid()
            sh.fill.fore_color.rgb = color
            sh.line.fill.background()
            return sh

        def add_clean_header(s, title_text, slide_num):
            hb = s.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.RECTANGLE, 0, 0, pptx.util.Inches(13.333), pptx.util.Inches(1.1))
            hb.fill.solid()
            hb.fill.fore_color.rgb = primary
            hb.line.fill.background()

            tx = s.shapes.add_textbox(pptx.util.Inches(0.8), pptx.util.Inches(0.18), pptx.util.Inches(9.2), pptx.util.Inches(0.8))
            tf = tx.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = title_text
            p.font.size = pptx.util.Pt(20)
            p.font.bold = True
            p.font.color.rgb = white

            ib = s.shapes.add_textbox(pptx.util.Inches(9.2), pptx.util.Inches(0.28), pptx.util.Inches(3.3), pptx.util.Inches(0.5))
            p_inst = ib.text_frame.paragraphs[0]
            p_inst.alignment = pptx.enum.text.PP_ALIGN.RIGHT
            p_inst.text = "INEI N.° 34 — CHANCAY"
            p_inst.font.size = pptx.util.Pt(10)
            p_inst.font.bold = True
            p_inst.font.color.rgb = pptx.dml.color.RGBColor(226, 232, 240)

            fb = s.shapes.add_textbox(pptx.util.Inches(11.5), pptx.util.Inches(6.9), pptx.util.Inches(1.5), pptx.util.Inches(0.4))
            p_num = fb.text_frame.paragraphs[0]
            p_num.alignment = pptx.enum.text.PP_ALIGN.RIGHT
            p_num.text = f"{slide_num:02d} / 07"
            p_num.font.size = pptx.util.Pt(11)
            p_num.font.bold = True
            p_num.font.color.rgb = muted_text

        md_cfg = cls.extract_slide_config_from_markdown(content_md)

        # SLIDE 1: Portada
        s1 = prs.slides.add_slide(blank_layout)
        add_bg(s1, primary)

        dec = s1.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(1.1), pptx.util.Inches(1.5), pptx.util.Inches(0.08))
        dec.fill.solid()
        dec.fill.fore_color.rgb = accent
        dec.line.fill.background()

        sp = s1.shapes.add_textbox(pptx.util.Inches(0.8), pptx.util.Inches(1.3), pptx.util.Inches(9.0), pptx.util.Inches(0.5))
        p = sp.text_frame.paragraphs[0]
        p.text = "I.E. INEI N.° 34 DE CHANCAY"
        p.font.size = pptx.util.Pt(13)
        p.font.bold = True
        p.font.color.rgb = accent

        t_box = s1.shapes.add_textbox(pptx.util.Inches(0.8), pptx.util.Inches(1.9), pptx.util.Inches(9.2), pptx.util.Inches(2.2))
        tf = t_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = topic
        p.font.size = pptx.util.Pt(36)
        p.font.bold = True
        p.font.color.rgb = white

        sub_box = s1.shapes.add_textbox(pptx.util.Inches(0.8), pptx.util.Inches(4.3), pptx.util.Inches(9.2), pptx.util.Inches(0.8))
        p = sub_box.text_frame.paragraphs[0]
        p.text = f"{area_name}  •  {grade}.° de Secundaria  •  Material Oficial"
        p.font.size = pptx.util.Pt(16)
        p.font.color.rgb = pptx.dml.color.RGBColor(226, 232, 240)

        t_card = s1.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(5.4), pptx.util.Inches(8.5), pptx.util.Inches(1.0))
        t_card.fill.solid()
        t_card.fill.fore_color.rgb = pptx.dml.color.RGBColor(15, 23, 42)
        t_card.line.color.rgb = accent
        t_card.line.width = pptx.util.Pt(1.5)
        tf_tc = t_card.text_frame
        tf_tc.vertical_anchor = pptx.enum.text.MSO_ANCHOR.MIDDLE
        p = tf_tc.paragraphs[0]
        p.text = f"👨‍🏫 Docente: {teacher_name}   |   📅 Año Escolar 2026"
        p.font.size = pptx.util.Pt(13)
        p.font.bold = True
        p.font.color.rgb = white

        if insignia_path:
            s1.shapes.add_picture(insignia_path, pptx.util.Inches(10.5), pptx.util.Inches(1.5), pptx.util.Inches(2.1), pptx.util.Inches(2.1))

        # SLIDE 2: Propósito y Reto
        s2 = prs.slides.add_slide(blank_layout)
        add_bg(s2, light_bg)
        add_clean_header(s2, "🎯 Propósito de Aprendizaje y Situación de Reto", 2)

        s2_data = md_cfg.get("slide2", {}) if md_cfg else {}
        purpose_head = s2_data.get("purpose_headline") or f"Analizar y comprender los fundamentos de {topic}, reconociendo su estructura, función e importancia en el mundo real."
        purpose_det = s2_data.get("purpose_detail") or "Desarrollaremos competencias formativas y evidencias de aprendizaje orientadas a la indagación, argumentación y resolución de problemas."
        chal_t = s2_data.get("challenge_title") or "Situación de Reto y Desafío"
        chal_d = s2_data.get("challenge_desc") or f"¿Cómo influyen los conceptos de {topic} en nuestra vida diaria y qué retos plantea su estudio para la ciencia y la sociedad actual?"
        chal_q = s2_data.get("question") or "¿Por qué es fundamental que un estudiante de secundaria comprenda este tema para tomar decisiones informadas?"

        c1 = s2.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(1.6), pptx.util.Inches(5.6), pptx.util.Inches(5.0))
        c1.fill.solid()
        c1.fill.fore_color.rgb = white
        c1.line.color.rgb = primary
        c1.line.width = pptx.util.Pt(1.5)
        tf1 = c1.text_frame
        tf1.word_wrap = True
        p1 = tf1.paragraphs[0]
        p1.text = "🎯 PROPÓSITO DE LA SESIÓN\n\n"
        p1.font.size = pptx.util.Pt(15)
        p1.font.bold = True
        p1.font.color.rgb = primary
        p2 = tf1.add_paragraph()
        p2.text = f"{purpose_head}\n\n"
        p2.font.size = pptx.util.Pt(13)
        p2.font.bold = True
        p2.font.color.rgb = dark_text
        p3 = tf1.add_paragraph()
        p3.text = purpose_det
        p3.font.size = pptx.util.Pt(11.5)
        p3.font.color.rgb = muted_text

        c2 = s2.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(6.8), pptx.util.Inches(1.6), pptx.util.Inches(5.7), pptx.util.Inches(5.0))
        c2.fill.solid()
        c2.fill.fore_color.rgb = white
        c2.line.color.rgb = accent
        c2.line.width = pptx.util.Pt(1.5)
        tf2 = c2.text_frame
        tf2.word_wrap = True
        p1 = tf2.paragraphs[0]
        p1.text = f"⚡ {chal_t.upper()}\n\n"
        p1.font.size = pptx.util.Pt(15)
        p1.font.bold = True
        p1.font.color.rgb = accent
        p2 = tf2.add_paragraph()
        p2.text = f"{chal_d}\n\n"
        p2.font.size = pptx.util.Pt(12.5)
        p2.font.color.rgb = dark_text
        p3 = tf2.add_paragraph()
        p3.text = f"💡 Pregunta Reflexiva:\n{chal_q}"
        p3.font.size = pptx.util.Pt(12)
        p3.font.bold = True
        p3.font.color.rgb = primary

        # SLIDE 3: Marco Conceptual con DIAGRAMA EDUCATIVO
        s3 = prs.slides.add_slide(blank_layout)
        add_bg(s3, light_bg)
        s3_data = md_cfg.get("slide3", {}) if md_cfg else {}
        h3 = s3_data.get("header") or f"Fundamentos Clave: {topic}"
        add_clean_header(s3, f"📚 {h3}", 3)

        diag_path = DiagramGenerator.get_or_create_diagram(topic, area_name)
        has_diag = bool(diag_path and os.path.exists(diag_path))

        card_w = pptx.util.Inches(5.8) if has_diag else pptx.util.Inches(11.7)
        card_h = pptx.util.Inches(1.15)
        gap_y = pptx.util.Inches(0.15)

        parsed_cards = s3_data.get("cards", [])
        if parsed_cards and len(parsed_cards) >= 3:
            core_concepts = [(c.get("title", f"Concepto {i+1}"), c.get("text", "")) for i, c in enumerate(parsed_cards[:4])]
        elif any(k in text_theme for k in ["adn", "arn", "genet", "biolog", "celul"]):
            core_concepts = [
                ("Estructura del ADN", "Dos cadenas de nucleótidos unidas por puentes de hidrógeno formando una doble hélice."),
                ("Función del ADN", "Almacena las instrucciones genéticas para la síntesis de proteínas y la herencia biológica."),
                ("Estructura del ARN", "Cadena simple de nucleótidos donde el Uracilo reemplaza a la Timina del ADN."),
                ("Función del ARN", "Transporta el mensaje genético hacia los ribosomas para ensamblar los aminoácidos.")
            ]
        elif any(k in text_theme for k in ["carpeta", "archivo", "computac", "informat"]):
            core_concepts = [
                ("Explorador de Windows", "Gestor de archivos nativo accesible rápidamente mediante el atajo Win + E."),
                ("Estructura en Árbol", "Jerarquía lógica: Unidad de disco ➔ Carpeta Raíz ➔ Subcarpetas temáticas."),
                ("Nomenclatura Estándar", "Nombres legibles: Año_Área_Tarea_Apellidos sin caracteres especiales prohibidos."),
                ("Copia de Seguridad 3-2-1", "3 copias de evidencias escolares en 2 medios diferentes y 1 en la nube institucional.")
            ]
        else:
            core_concepts = [
                ("Fundamento Esencial", f"Principio central que define la comprensión de {topic}."),
                ("Estructura y Funcionamiento", "Componentes organizados que permiten el desarrollo del proceso."),
                ("Aplicación Práctica", "Uso directo de los conceptos para resolver problemas del entorno."),
                ("Impacto en la Sociedad", "Relevancia del conocimiento para el desarrollo sostenible y la vida diaria.")
            ]

        for i, (ctitle, cdesc) in enumerate(core_concepts):
            cy = pptx.util.Inches(1.5) + i * (card_h + gap_y)
            c_sh = s3.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), cy, card_w, card_h)
            c_sh.fill.solid()
            c_sh.fill.fore_color.rgb = white
            c_sh.line.color.rgb = primary
            c_sh.line.width = pptx.util.Pt(1.2)
            tf = c_sh.text_frame
            tf.word_wrap = True
            p1 = tf.paragraphs[0]
            p1.text = f"{ctitle}\n"
            p1.font.size = pptx.util.Pt(12)
            p1.font.bold = True
            p1.font.color.rgb = primary
            p2 = tf.add_paragraph()
            p2.text = cdesc
            p2.font.size = pptx.util.Pt(10.5)
            p2.font.color.rgb = dark_text

        if has_diag:
            s3.shapes.add_picture(diag_path, pptx.util.Inches(6.9), pptx.util.Inches(1.5), pptx.util.Inches(5.6), pptx.util.Inches(5.1))

        # SLIDE 4: Caso Práctico Modelado
        s4 = prs.slides.add_slide(blank_layout)
        add_bg(s4, light_bg)
        s4_data = md_cfg.get("slide4", {}) if md_cfg else {}
        h4 = s4_data.get("header") or f"Caso Práctico Modelado: {topic}"
        add_clean_header(s4, f"🔍 {h4}", 4)

        parsed_steps = s4_data.get("steps", [])
        valid_parsed_steps = [(st, sd) for st, sd in parsed_steps if sd and len(sd) > 5 and "procedimiento técnico" not in sd.lower()]

        if len(valid_parsed_steps) >= 3:
            p_steps = []
            default_step_titles = ["Diagnóstico Inicial", "Procedimiento Aplicado", "Validación y Resultado"]
            for idx, (st, sd) in enumerate(valid_parsed_steps[:3]):
                clean_t = st if len(st) > 3 and not st.lower().startswith("paso") else default_step_titles[idx]
                p_steps.append((clean_t, sd))
            res_text = s4_data.get("result") or "Procedimiento ejecutado con éxito cumpliendo todos los estándares formativos."
        elif any(k in text_theme for k in ["adn", "arn", "genet"]):
            p_steps = [
                ("Toma de Muestra", "Recolección de muestra biológica (células epiteliales) y observación en el microscopio."),
                ("Lisis y Extracción", "Ruptura de membranas con detergente y aislamiento de las hebras con alcohol frío."),
                ("Electroforesis y Análisis", "Separación de fragmentos moleculares en gel para contrastar con el patrón de referencia.")
            ]
            res_text = s4_data.get("result") or "Identificación precisa del perfil genético con 99.9% de certeza y validación experimental."
        elif any(k in text_theme for k in ["carpeta", "archivo", "computac"]):
            p_steps = [
                ("Diagnóstico Inicial", "Escritorio con 25 archivos sueltos y nombres confusos que dificultan encontrar las tareas."),
                ("Procedimiento Técnico", "Creación de la carpeta 'Portafolio_2026' con 4 subcarpetas por áreas usando Ctrl+Shift+N."),
                ("Validación y Backup", "Renombrado con F2 según el estándar oficial y sincronización en la nube institucional.")
            ]
            res_text = s4_data.get("result") or "Portafolio digital 100% organizado, archivos ubicables en <5 segundos y cero pérdidas de tareas."
        else:
            p_steps = [
                ("Diagnóstico Inicial", "Identificación del problema o necesidad en el entorno de aprendizaje."),
                ("Procedimiento Aplicado", "Ejecución técnica y metodológica de la secuencia de pasos planificados."),
                ("Validación de Resultados", "Comprobación de calidad y verificación formativa del producto obtenido.")
            ]
            res_text = s4_data.get("result") or "Procedimiento ejecutado con éxito cumpliendo todos los estándares de calidad y seguridad."

        step_w = pptx.util.Inches(3.6)
        gap_s = pptx.util.Inches(0.4)
        for i, (stitle, stext) in enumerate(p_steps):
            sx = pptx.util.Inches(0.8) + i * (step_w + gap_s)
            sc = s4.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, sx, pptx.util.Inches(1.6), step_w, pptx.util.Inches(3.6))
            sc.fill.solid()
            sc.fill.fore_color.rgb = white
            sc.line.color.rgb = primary if i == 0 else (accent if i == 1 else pptx.dml.color.RGBColor(16, 185, 129))
            sc.line.width = pptx.util.Pt(1.5)
            tf = sc.text_frame
            tf.word_wrap = True
            p1 = tf.paragraphs[0]
            p1.text = f"PASO {i+1}\n\n"
            p1.font.size = pptx.util.Pt(13)
            p1.font.bold = True
            p1.font.color.rgb = accent
            p2 = tf.add_paragraph()
            p2.text = f"{stitle}\n\n"
            p2.font.size = pptx.util.Pt(13)
            p2.font.bold = True
            p2.font.color.rgb = primary
            p3 = tf.add_paragraph()
            p3.text = stext
            p3.font.size = pptx.util.Pt(11.5)
            p3.font.color.rgb = dark_text

        res_box = s4.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(5.5), pptx.util.Inches(11.7), pptx.util.Inches(1.1))
        res_box.fill.solid()
        res_box.fill.fore_color.rgb = pptx.dml.color.RGBColor(236, 253, 245)
        res_box.line.color.rgb = pptx.dml.color.RGBColor(52, 211, 153)
        res_box.line.width = pptx.util.Pt(1.5)
        tf_res = res_box.text_frame
        tf_res.vertical_anchor = pptx.enum.text.MSO_ANCHOR.MIDDLE
        p = tf_res.paragraphs[0]
        p.text = f"✅ RESULTADO MEDIBLE: {res_text}"
        p.font.size = pptx.util.Pt(12)
        p.font.bold = True
        p.font.color.rgb = pptx.dml.color.RGBColor(6, 78, 59)

        # SLIDE 5: Herramientas y Métodos
        s5 = prs.slides.add_slide(blank_layout)
        add_bg(s5, light_bg)
        s5_data = md_cfg.get("slide5", {}) if md_cfg else {}
        h5 = s5_data.get("header") or f"Herramientas, Métodos y Tecnologías: {topic}"
        add_clean_header(s5, f"🛠️ {h5}", 5)

        # Configuración contextual de iconos y tips de respaldo según área
        if any(k in text_theme for k in ["social", "historia", "geograf", "caral", "cultura", "inca", "poblam"]):
            icons = ["📜", "🏛️", "🌾", "🏺"]
            default_tips = [
                "Evalúa la autenticidad y el contexto temporal de las fuentes históricas.",
                "Contrasta vestigios arqueológicos para fundamentar hipótesis explicativas.",
                "Analiza el rol de la geografía y recursos en la organización social.",
                "Interpreta la cosmovisión y el simbolismo cultural de la época."
            ]
        elif any(k in text_theme for k in ["adn", "arn", "genet", "biolog", "celul"]):
            icons = ["🔬", "⚡", "🧬", "✂️"]
            default_tips = [
                "Usa reactivos fríos para preservar la integridad molecular.",
                "El ADN migra al polo positivo debido a su carga negativa.",
                "Sigue las normas de esterilidad y bioseguridad en el laboratorio.",
                "Compara las bandas de control para validar el resultado."
            ]
        elif any(k in text_theme for k in ["matematic", "álgebra", "algebra", "geometr", "calcul"]):
            icons = ["📐", "🔢", "📊", "💡"]
            default_tips = [
                "Verifica los signos y simplifica antes de operar.",
                "Representa gráficamente para visualizar las relaciones numéricas.",
                "Comprueba la solución sustituyendo en la ecuación original.",
                "Justifica cada paso deductivo con axiomas o teoremas conocidos."
            ]
        elif any(k in text_theme for k in ["carpeta", "archivo", "computac", "ofimat"]):
            icons = ["📁", "☁️", "🏷️", "🛡️"]
            default_tips = [
                "Usa el atajo 'Win + E' para abrir directamente el Explorador de Windows.",
                "Sincroniza periódicamente tu respaldo en la nube escolar institucional.",
                "Usa guiones bajos o fechas (AAAA-MM-DD) para ordenar tus tareas.",
                "Mantén carpetas ordenadas por bimestres o asignaturas escolares."
            ]
        else:
            icons = ["📌", "⚡", "🏷️", "🛡️"]
            default_tips = [
                "Aplica con rigor analítico y verifica la fiabilidad de las fuentes.",
                "Registra observaciones de manera ordenada en tu cuaderno de trabajo.",
                "Sustenta tus conclusiones con evidencias contrastadas.",
                "Verifica siempre los detalles antes de entregar la evidencia final."
            ]

        parsed_tools = s5_data.get("tools", [])
        if parsed_tools:
            tools_list = []
            for i, t in enumerate(parsed_tools[:4]):
                t_name = t[0] if len(t) > 0 else f"Herramienta {i+1}"
                t_desc = t[1] if len(t) > 1 else "Aplicación práctica orientada al aprendizaje."
                t_tip = t[2] if len(t) > 2 and t[2] else default_tips[i % len(default_tips)]
                icon = icons[i % len(icons)]
                tools_list.append((f"{icon} {t_name}", t_desc, t_tip))
        else:
            tools_list = [
                (f"{icons[0]} Instrumento de Análisis", "Herramienta metodológica para la recolección sistemática de evidencias.", default_tips[0]),
                (f"{icons[1]} Metodología Activa", "Estrategia participativa para poner a prueba los conceptos estudiados.", default_tips[1]),
                (f"{icons[2]} Estándar de Calidad", "Criterios normativos para asegurar la precisión y validez del producto.", default_tips[2]),
                (f"{icons[3]} Protocolo de Seguridad", "Normas de cuidado, respeto y preservación del entorno formativo.", default_tips[3])
            ]

        coords = [(pptx.util.Inches(0.8), pptx.util.Inches(1.6)), (pptx.util.Inches(6.8), pptx.util.Inches(1.6)), (pptx.util.Inches(0.8), pptx.util.Inches(4.3)), (pptx.util.Inches(6.8), pptx.util.Inches(4.3))]
        for idx, (t_title, t_desc, t_tip) in enumerate(tools_list[:4]):
            qx, qy = coords[idx]
            qc = s5.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, qx, qy, pptx.util.Inches(5.7), pptx.util.Inches(2.5))
            qc.fill.solid()
            qc.fill.fore_color.rgb = white
            qc.line.color.rgb = primary
            qc.line.width = pptx.util.Pt(1.0)
            tf = qc.text_frame
            tf.word_wrap = True
            p1 = tf.paragraphs[0]
            p1.text = f"{t_title}\n"
            p1.font.size = pptx.util.Pt(12.5)
            p1.font.bold = True
            p1.font.color.rgb = primary
            p2 = tf.add_paragraph()
            p2.text = f"{t_desc}\n"
            p2.font.size = pptx.util.Pt(11)
            p2.font.color.rgb = dark_text
            p3 = tf.add_paragraph()
            p3.text = f"💡 TIP: {t_tip}"
            p3.font.size = pptx.util.Pt(10)
            p3.font.bold = True
            p3.font.color.rgb = accent

        # SLIDE 6: Reto Práctico
        s6 = prs.slides.add_slide(blank_layout)
        add_bg(s6, light_bg)
        s6_data = md_cfg.get("slide6", {}) if md_cfg else {}
        h6 = s6_data.get("header") or f"¡Hora de la Acción! Reto de Aprendizaje: {topic}"
        add_clean_header(s6, f"🚀 {h6}", 6)

        act_card = s6.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(1.6), pptx.util.Inches(11.7), pptx.util.Inches(5.0))
        act_card.fill.solid()
        act_card.fill.fore_color.rgb = white
        act_card.line.color.rgb = accent
        act_card.line.width = pptx.util.Pt(2.0)
        tf_act = act_card.text_frame
        tf_act.word_wrap = True
        p1 = tf_act.paragraphs[0]
        p1.text = f"DESAFÍO PRÁCTICO EN CLASE: {topic.upper()}\n\n"
        p1.font.size = pptx.util.Pt(16)
        p1.font.bold = True
        p1.font.color.rgb = primary

        parsed_inst = s6_data.get("instructions")
        if parsed_inst and len(parsed_inst) > 20:
            instruct = f"📋 Instrucciones para el Estudiante:\n{parsed_inst}\n\n"
            motto = s6_data.get("quote") or "La práctica constante consolida el aprendizaje y potencia tus habilidades."
        elif any(k in text_theme for k in ["adn", "arn", "genet"]):
            instruct = (
                "📋 Instrucciones para el Estudiante (En equipos de 3):\n"
                "1. Recibe la secuencia molde de ADN: TAC — CGA — TTT — ACT.\n"
                "2. Realiza la TRANSCRIPCIÓN a ARN mensajero usando complementariedad de bases (A➔U, T➔A, C➔G, G➔C).\n"
                "3. Utiliza la tabla del código genético para TRADUCIR cada codón al aminoácido correspondiente.\n"
                "4. Predice qué ocurriría con la proteína final si una mutación cambia la tercera base de la secuencia.\n\n"
            )
            motto = '"En cada hebra de ADN está escrita la historia viva de cuatro mil millones de años en la Tierra."'
        elif any(k in text_theme for k in ["carpeta", "archivo", "computac"]):
            instruct = (
                "📋 Instrucciones para el Estudiante (En tu estación de cómputo):\n"
                "1. Abre el Explorador de Windows con el atajo Win + E y accede a tu unidad de trabajo D:\\.\n"
                "2. Crea la carpeta principal: 2026_PrimerGrado_TuNombre con el atajo Ctrl + Shift + N.\n"
                "3. Dentro de ella, crea 4 subcarpetas por bimestres (Bimestre_01 a Bimestre_04).\n"
                "4. Guarda un archivo de texto en cada una con la nomenclatura oficial y valida en pantalla.\n\n"
            )
            motto = '"El orden digital potencia tu productividad y protege tu esfuerzo escolar."'
        else:
            instruct = (
                "📋 Instrucciones para el Estudiante (Trabajo en equipo colaborativo):\n"
                "1. Analiza el caso propuesto identificando las variables y conceptos clave estudiados.\n"
                "2. Aplica la metodología modelada para resolver el desafío de forma fundamentada.\n"
                "3. Elabora la evidencia del equipo registrando los pasos y conclusiones obtenidas.\n"
                "4. Sustenta los resultados y responde a las preguntas de análisis planteadas.\n\n"
            )
            motto = '"La práctica constante consolida el aprendizaje y potencia tus habilidades."'

        p2 = tf_act.add_paragraph()
        p2.text = instruct
        p2.font.size = pptx.util.Pt(12.5)
        p2.font.color.rgb = dark_text

        p3 = tf_act.add_paragraph()
        p3.text = f"⏱ Tiempo Asignado: {s6_data.get('time', '20:00 min')}   |   🎯 Criterio de Éxito: Completar la evidencia de forma autónoma y sustentarla.\n\n"
        p3.font.size = pptx.util.Pt(13)
        p3.font.bold = True
        p3.font.color.rgb = accent

        p4 = tf_act.add_paragraph()
        p4.text = f"💬 Lema Motivador:\n{motto}"
        p4.font.size = pptx.util.Pt(12)
        p4.font.italic = True
        p4.font.color.rgb = primary

        # SLIDE 7: Metacognición
        s7 = prs.slides.add_slide(blank_layout)
        add_bg(s7, light_bg)
        s7_data = md_cfg.get("slide7", {}) if md_cfg else {}
        add_clean_header(s7, "🏁 Reflexionamos y Evaluación Formativa", 7)

        c_auto = s7.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(1.6), pptx.util.Inches(5.6), pptx.util.Inches(4.5))
        c_auto.fill.solid()
        c_auto.fill.fore_color.rgb = white
        c_auto.line.color.rgb = primary
        c_auto.line.width = pptx.util.Pt(1.5)
        tf_auto = c_auto.text_frame
        tf_auto.word_wrap = True
        p1 = tf_auto.paragraphs[0]
        p1.text = "📋 CRITERIOS DE AUTOEVALUACIÓN\n\n"
        p1.font.size = pptx.util.Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = primary

        parsed_crit = s7_data.get("criteria", [])
        if parsed_crit and len(parsed_crit) >= 2:
            crit = parsed_crit[:3]
        elif any(k in text_theme for k in ["adn", "arn", "genet"]):
            crit = [
                "Diferencié con claridad la estructura y función del ADN frente al ARN.",
                "Comprendí cómo la complementariedad de bases transmite el código de la vida.",
                "Reconocí la importancia de la genética en la salud y el bienestar humano."
            ]
        elif any(k in text_theme for k in ["carpeta", "archivo", "computac"]):
            crit = [
                "Creé y estructuré carpetas y subcarpetas con jerarquía lógica.",
                "Apliqué nombres normalizados reconociendo las extensiones de archivo.",
                "Comprendí la importancia del almacenamiento seguro y las copias de respaldo."
            ]
        else:
            crit = [
                "Comprendí los conceptos esenciales y su aplicación práctica.",
                "Apliqué el procedimiento paso a paso de forma autónoma.",
                "Valoré la importancia del orden, la seguridad y el trabajo en equipo."
            ]

        for item in crit:
            p = tf_auto.add_paragraph()
            p.text = f"☑ {item}\n"
            p.font.size = pptx.util.Pt(12)
            p.font.color.rgb = dark_text

        c_meta = s7.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(6.8), pptx.util.Inches(1.6), pptx.util.Inches(5.7), pptx.util.Inches(4.5))
        c_meta.fill.solid()
        c_meta.fill.fore_color.rgb = white
        c_meta.line.color.rgb = accent
        c_meta.line.width = pptx.util.Pt(1.5)
        tf_meta = c_meta.text_frame
        tf_meta.word_wrap = True
        p1 = tf_meta.paragraphs[0]
        p1.text = "🧠 PREGUNTAS METACOGNITIVAS\n\n"
        p1.font.size = pptx.util.Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = accent

        parsed_q = s7_data.get("questions", [])
        if parsed_q and len(parsed_q) >= 2:
            q_meta = [f"{idx+1}. {q}" for idx, q in enumerate(parsed_q[:3])]
        elif any(k in text_theme for k in ["adn", "arn", "genet"]):
            q_meta = [
                "1. ¿Qué aprendí hoy sobre la función del ADN y ARN que antes no sabía?",
                "2. ¿Cómo le explicaría a un compañero por qué el código genético es universal?",
                "3. ¿Para qué me servirá comprender este conocimiento en mi vida diaria y salud?"
            ]
        elif any(k in text_theme for k in ["carpeta", "archivo", "computac"]):
            q_meta = [
                "1. ¿Qué atajos de teclado nuevos aprendí hoy y cómo me ayudarán a ahorrar tiempo?",
                "2. ¿Cómo mantendré ordenado mi escritorio para no volver a perder tareas?",
                "3. ¿De qué manera la organización digital mejorará mi rendimiento escolar?"
            ]
        else:
            q_meta = [
                "1. ¿Qué aprendí hoy que antes de la sesión no comprendía del todo?",
                "2. ¿Qué dificultades encontré durante la actividad y cómo logré superarlas?",
                "3. ¿De qué manera aplicaré lo aprendido en mi vida escolar y personal?"
            ]

        for qm in q_meta:
            p = tf_meta.add_paragraph()
            p.text = f"{qm}\n\n"
            p.font.size = pptx.util.Pt(12)
            p.font.color.rgb = dark_text

        # Bottom Seal Badge
        seal_box = s7.shapes.add_shape(pptx.enum.shapes.MSO_SHAPE.ROUNDED_RECTANGLE, pptx.util.Inches(0.8), pptx.util.Inches(6.25), pptx.util.Inches(11.7), pptx.util.Inches(0.75))
        seal_box.fill.solid()
        seal_box.fill.fore_color.rgb = primary
        seal_box.line.fill.background()
        tf_seal = seal_box.text_frame
        tf_seal.vertical_anchor = pptx.enum.text.MSO_ANCHOR.MIDDLE
        p = tf_seal.paragraphs[0]
        p.alignment = pptx.enum.text.PP_ALIGN.CENTER
        p.text = "🏛️ I.E. INEI N.° 34 DE CHANCAY — FORMANDO LÍDERES PARA EL FUTURO"
        p.font.size = pptx.util.Pt(11)
        p.font.bold = True
        p.font.color.rgb = white

        out = io.BytesIO()
        prs.save(out)
        return out.getvalue()
    @classmethod
    def render_pptx_from_template(
        cls,
        template_bytes: bytes,
        doc_data: Dict[str, Any]
    ) -> bytes:
        # Generación Nativa 100% IA de alta fidelidad:
        # Crea la presentación panorámica (16:9) desde cero para cualquier área y tema,
        # sin arrastrar imágenes residuales ni depender de plantillas fijas.
        try:
            return cls.generate_native_ai_pptx(doc_data)
        except Exception as _native_err:
            logger.warning(f"Fallback a renderizado por plantilla debido a: {_native_err}")
        """
        Clona la presentación PPTX oficial de CET N.º 34 (7 diapositivas) y realiza la
        adaptación semántica profunda por especialidad (Emprendimiento, Mecánica de Producción,
        Automotriz, Electricidad, Construcciones Metálicas y Computación).
        Garantiza que ningún texto se desborde de sus cuadros mediante cálculo dinámico de fuente,
        envoltura automática de palabras y preservación de tipografías y membretes institucionales.
        """
        if pptx is None:
            raise RuntimeError("La librería python-pptx no está instalada en el entorno.")

        topic = doc_data.get("topic") or doc_data.get("title") or "Presentación Pedagógica"
        specialty_raw = doc_data.get("specialty") or "Educación para el Trabajo"
        grade = int(doc_data.get("grade") or 5)
        teacher_name = doc_data.get("teacher_name")
        is_verified_teacher, clean_teacher = cls.resolve_verified_teacher(teacher_name)
        doc_display = clean_teacher if is_verified_teacher else "[Docente Responsable]"

        spec_key = cls.detect_pptx_specialty_key(specialty_raw, topic)
        if spec_key == "computacion" and any(k in (topic + " " + specialty_raw).lower() for k in ["carpeta", "archivo", "ofimatica", "ofimática", "word", "excel", "windows", "digital", "almacenamiento", "backup", "seguridad"]):
            spec_key = "computacion_ofimatica"
        preset = copy.deepcopy(cls.PPTX_SPECIALTY_PRESETS.get(spec_key, cls.PPTX_SPECIALTY_PRESETS["emprendimiento"]))

        # Sincronización dinámica profunda: extrae las diapositivas redactadas por la IA para transferirlas al PPT
        content_md = doc_data.get("content_markdown") or ""
        md_cfg = cls.extract_slide_config_from_markdown(content_md)
        if md_cfg:
            for s_k, s_val in md_cfg.items():
                if s_k in preset and isinstance(preset[s_k], dict) and isinstance(s_val, dict):
                    preset[s_k].update(s_val)
                else:
                    preset[s_k] = s_val

        # Nombre de especialidad visible (preserva si el docente especificó una oficial)
        clean_spec = specialty_raw.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "").strip()
        if clean_spec.lower() in ["educación para el trabajo", "educacion para el trabajo", "ept", ""]:
            specialty_display = preset["specialty_name"]
        else:
            specialty_display = clean_spec

        prs = pptx.Presentation(io.BytesIO(template_bytes))

        # =========================================================
        # SLIDE 1: Portada Institucional
        # =========================================================
        if len(prs.slides) >= 1:
            s1 = prs.slides[0]
            cls._set_pptx_shape_text_safe(s1.shapes[0], topic, base_font_size_pt=41.5, max_chars=75, bold=True)
            cls._set_pptx_shape_text_safe(
                s1.shapes[1],
                f"{specialty_display} • {grade}.° Secundaria • CET N.° 34",
                base_font_size_pt=17.0,
                max_chars=80
            )
            icons = preset.get("icons", ("💼", "💡", "🚀"))
            cls._set_pptx_shape_text_safe(s1.shapes[2], icons[0], base_font_size_pt=55.0)
            cls._set_pptx_shape_text_safe(s1.shapes[3], icons[1], base_font_size_pt=55.0)
            cls._set_pptx_shape_text_safe(s1.shapes[4], icons[2], base_font_size_pt=55.0)
            cls._set_pptx_shape_text_safe(
                s1.shapes[5],
                f"Sesión de Especialidad Técnica • {doc_display}",
                base_font_size_pt=10.5,
                max_chars=55
            )

        # =========================================================
        # SLIDE 2: Propósito y Situación de Reto
        # =========================================================
        if len(prs.slides) >= 2:
            s2 = prs.slides[1]
            s2_cfg = preset["slide2"]
            cls._set_pptx_shape_text_safe(s2.shapes[0], "🎯 Propósito y Situación de Reto", base_font_size_pt=16.0)
            cls._set_pptx_shape_text_safe(s2.shapes[3], "Propósito de la Sesión", base_font_size_pt=10.5)

            # Integración de propósito personalizado si se suministró
            user_purpose = doc_data.get("purpose")
            if user_purpose and len(user_purpose.strip()) > 5:
                p_headline = user_purpose.strip()
            else:
                p_headline = s2_cfg["purpose_headline"]
            cls._set_pptx_shape_text_safe(s2.shapes[4], p_headline, base_font_size_pt=8.5, max_chars=120, bold=True)
            cls._set_pptx_shape_text_safe(s2.shapes[5], s2_cfg["purpose_detail"], base_font_size_pt=8.5, max_chars=130)

            cls._set_pptx_shape_text_safe(s2.shapes[8], "⚡ ¡Acepta el Desafío!", base_font_size_pt=10.5)
            cls._set_pptx_shape_text_safe(s2.shapes[10], s2_cfg["challenge_title"], base_font_size_pt=8.0, max_chars=50, bold=True)
            cls._set_pptx_shape_text_safe(s2.shapes[11], s2_cfg["challenge_desc"], base_font_size_pt=8.5, max_chars=145)
            cls._set_pptx_shape_text_safe(s2.shapes[12], s2_cfg["meta"], base_font_size_pt=8.0, max_chars=80)
            cls._set_pptx_shape_text_safe(s2.shapes[14], s2_cfg["question"], base_font_size_pt=7.0, max_chars=90)
            if len(s2.shapes) > 15:
                cls._set_pptx_shape_text_safe(s2.shapes[15], "02 / 07", base_font_size_pt=7.5)

        # =========================================================
        # SLIDE 3: Marco Conceptual y Bloques/Fases Técnicas
        # =========================================================
        if len(prs.slides) >= 3:
            s3 = prs.slides[2]
            s3_cfg = preset["slide3"]
            cls._set_pptx_shape_text_safe(s3.shapes[0], s3_cfg["header"], base_font_size_pt=18.0, max_chars=50, bold=True)

            cards = s3_cfg["cards"]
            card_shapes_map = [
                (3, 4, 5),      # Card 1 (Bloque 1)
                (8, 9, 10),    # Card 2 (Bloque 4)
                (13, 14, 15),  # Card 3 (Bloque 3)
                (18, 19, 20),  # Card 4 (Bloque 9)
                (23, 24, 25),  # Card 5 (Bloque 2)
                (28, 29, 30),  # Card 6 (Bloque 8)
                (33, 34, 35),  # Card 7 (Bloque 5)
            ]
            for c_idx, (s_tag, s_title, s_desc) in enumerate(card_shapes_map):
                if c_idx < len(cards):
                    c_data = cards[c_idx]
                    cls._set_pptx_shape_text_safe(s3.shapes[s_tag], c_data["tag"], base_font_size_pt=7.0, bold=True, max_chars=12)
                    cls._set_pptx_shape_text_safe(s3.shapes[s_title], c_data["title"], base_font_size_pt=9.5, bold=True, max_chars=22)
                    cls._set_pptx_shape_text_safe(s3.shapes[s_desc], c_data["text"], base_font_size_pt=8.5, max_chars=75)

            if len(s3.shapes) > 38:
                cls._set_pptx_shape_text_safe(s3.shapes[38], s3_cfg["footer"], base_font_size_pt=10.5, max_chars=160)
            if len(s3.shapes) > 39:
                cls._set_pptx_shape_text_safe(s3.shapes[39], "03 / 07", base_font_size_pt=7.5)

        # =========================================================
        # SLIDE 4: Caso Práctico Modelado
        # =========================================================
        if len(prs.slides) >= 4:
            s4 = prs.slides[3]
            s4_cfg = preset["slide4"]
            cls._set_pptx_shape_text_safe(s4.shapes[0], s4_cfg["header"], base_font_size_pt=14.0, max_chars=55, bold=True)

            cls._set_pptx_shape_text_safe(s4.shapes[4], "1", base_font_size_pt=10.0, bold=True)
            cls._set_pptx_shape_text_safe(s4.shapes[5], s4_cfg["step1_title"], base_font_size_pt=9.0, bold=True, max_chars=30)
            cls._set_pptx_shape_text_safe(s4.shapes[6], s4_cfg["step1_text"], base_font_size_pt=8.5, max_chars=85)

            cls._set_pptx_shape_text_safe(s4.shapes[10], "2", base_font_size_pt=10.0, bold=True)
            cls._set_pptx_shape_text_safe(s4.shapes[11], s4_cfg["step2_title"], base_font_size_pt=9.0, bold=True, max_chars=30)
            cls._set_pptx_shape_text_safe(s4.shapes[12], s4_cfg["step2_text"], base_font_size_pt=8.5, max_chars=85)

            cls._set_pptx_shape_text_safe(s4.shapes[16], "3", base_font_size_pt=10.0, bold=True)
            cls._set_pptx_shape_text_safe(s4.shapes[17], s4_cfg["step3_title"], base_font_size_pt=9.0, bold=True, max_chars=30)
            cls._set_pptx_shape_text_safe(s4.shapes[18], s4_cfg["step3_text"], base_font_size_pt=8.5, max_chars=85)

            if len(s4.shapes) > 20:
                cls._set_pptx_shape_text_safe(s4.shapes[20], s4_cfg["result"], base_font_size_pt=9.0, max_chars=75, bold=True)
            if len(s4.shapes) > 23:
                cls._set_pptx_shape_text_safe(s4.shapes[23], s4_cfg["question"], base_font_size_pt=7.5, max_chars=95)
            if len(s4.shapes) > 24:
                cls._set_pptx_shape_text_safe(s4.shapes[24], "04 / 07", base_font_size_pt=7.5)

        # =========================================================
        # SLIDE 5: Herramientas y Métodos de Trabajo
        # =========================================================
        if len(prs.slides) >= 5:
            s5 = prs.slides[4]
            s5_cfg = preset["slide5"]
            cls._set_pptx_shape_text_safe(s5.shapes[0], s5_cfg["header"], base_font_size_pt=18.0, max_chars=55, bold=True)

            # Cuadrante 1
            q1 = s5_cfg["q1"]
            cls._set_pptx_shape_text_safe(s5.shapes[3], q1["icon"], base_font_size_pt=17.0)
            cls._set_pptx_shape_text_safe(s5.shapes[4], q1["title"], base_font_size_pt=12.0, max_chars=20, bold=True)
            cls._set_pptx_shape_text_safe(s5.shapes[5], q1["desc"], base_font_size_pt=10.0, max_chars=110)
            cls._set_pptx_shape_text_safe(s5.shapes[7], q1["tip"], base_font_size_pt=9.0, max_chars=85)

            # Cuadrante 2
            q2 = s5_cfg["q2"]
            cls._set_pptx_shape_text_safe(s5.shapes[10], q2["icon"], base_font_size_pt=17.0)
            cls._set_pptx_shape_text_safe(s5.shapes[11], q2["title"], base_font_size_pt=12.0, max_chars=20, bold=True)
            cls._set_pptx_shape_text_safe(s5.shapes[12], q2["desc"], base_font_size_pt=10.0, max_chars=110)
            cls._set_pptx_shape_text_safe(s5.shapes[14], q2["tip"], base_font_size_pt=9.0, max_chars=85)

            # Cuadrante 3
            q3 = s5_cfg["q3"]
            cls._set_pptx_shape_text_safe(s5.shapes[17], q3["icon"], base_font_size_pt=17.0)
            cls._set_pptx_shape_text_safe(s5.shapes[18], q3["title"], base_font_size_pt=12.0, max_chars=20, bold=True)
            cls._set_pptx_shape_text_safe(s5.shapes[19], q3["desc"], base_font_size_pt=10.0, max_chars=110)
            cls._set_pptx_shape_text_safe(s5.shapes[21], q3["tip"], base_font_size_pt=9.0, max_chars=85)

            # Cuadrante 4
            q4 = s5_cfg["q4"]
            cls._set_pptx_shape_text_safe(s5.shapes[24], q4["icon"], base_font_size_pt=17.0)
            cls._set_pptx_shape_text_safe(s5.shapes[25], q4["title"], base_font_size_pt=12.0, max_chars=20, bold=True)
            cls._set_pptx_shape_text_safe(s5.shapes[26], q4["desc"], base_font_size_pt=10.0, max_chars=110)
            cls._set_pptx_shape_text_safe(s5.shapes[28], q4["tip"], base_font_size_pt=9.0, max_chars=85)

            if len(s5.shapes) > 29:
                cls._set_pptx_shape_text_safe(s5.shapes[29], "05 / 07", base_font_size_pt=8.5)

        # =========================================================
        # SLIDE 6: ¡Hora de la Acción! Reto de Taller
        # =========================================================
        if len(prs.slides) >= 6:
            s6 = prs.slides[5]
            s6_cfg = preset["slide6"]
            cls._set_pptx_shape_text_safe(s6.shapes[1], s6_cfg["header"], base_font_size_pt=24.5, bold=True)
            cls._set_pptx_shape_text_safe(s6.shapes[3], s6_cfg["challenge_title"], base_font_size_pt=16.0, max_chars=45, bold=True)
            cls._set_pptx_shape_text_safe(s6.shapes[4], s6_cfg["instructions"], base_font_size_pt=12.0, max_chars=110)
            cls._set_pptx_shape_text_safe(s6.shapes[5], s6_cfg["timer"], base_font_size_pt=32.5, bold=True)
            cls._set_pptx_shape_text_safe(s6.shapes[6], s6_cfg["quote"], base_font_size_pt=10.5, max_chars=80)
            if len(s6.shapes) > 7:
                cls._set_pptx_shape_text_safe(s6.shapes[7], "06 / 07", base_font_size_pt=8.5)

        # =========================================================
        # SLIDE 7: Reflexionamos y Cerramos / Autoevaluación
        # =========================================================
        if len(prs.slides) >= 7:
            s7 = prs.slides[6]
            s7_cfg = preset["slide7"]
            cls._set_pptx_shape_text_safe(s7.shapes[2], s7_cfg["header"], base_font_size_pt=20.0, bold=True)
            cls._set_pptx_shape_text_safe(s7.shapes[4], s7_cfg["label"], base_font_size_pt=9.0, bold=True)
            cls._set_pptx_shape_text_safe(s7.shapes[5], s7_cfg["item1"], base_font_size_pt=10.5, max_chars=65)
            cls._set_pptx_shape_text_safe(s7.shapes[6], s7_cfg["item2"], base_font_size_pt=10.5, max_chars=65)
            cls._set_pptx_shape_text_safe(s7.shapes[7], s7_cfg["item3"], base_font_size_pt=10.5, max_chars=65)
            cls._set_pptx_shape_text_safe(s7.shapes[9], s7_cfg["question"], base_font_size_pt=11.0, max_chars=95, bold=True)
            if len(s7.shapes) > 10:
                cls._set_pptx_shape_text_safe(s7.shapes[10], "07 / 07", base_font_size_pt=8.5)

        # Validación interna de desbordamiento de texto
        fit_report = cls.validate_pptx_text_fit(prs)
        logger.info(
            f"PPTX Renderizado CET N.° 34: Especialidad '{specialty_display}' ({spec_key}) - "
            f"{fit_report['fitted_shapes']}/{fit_report['total_text_shapes']} formas adaptadas sin desbordamiento."
        )

        # Limpieza estricta de imágenes residuales de la plantilla (evita foto de comida o afiche Lean Canvas en otras materias)
        if spec_key != 'emprendimiento' and not any(k in (topic + ' ' + specialty_raw).lower() for k in ['lean canvas', 'lonchera', 'emprendimiento']):
            try:
                if len(prs.slides) >= 2:
                    for sh in list(prs.slides[1].shapes):
                        if sh.name == 'Image 1':
                            sh._element.getparent().remove(sh._element)
                if len(prs.slides) >= 3:
                    for sh in list(prs.slides[2].shapes):
                        if sh.name == 'Image 1':
                            sh._element.getparent().remove(sh._element)
            except Exception:
                pass

        out = io.BytesIO()
        prs.save(out)
        return out.getvalue()
    # -------------------------------------------------------------
    # Rellenado Genérico con Placeholders ({{TAG}})
    # -------------------------------------------------------------
    @classmethod
    def _fill_generic_docx_template(cls, doc: Document, data: Dict[str, Any]):
        """
        Soporta reemplazo de etiquetas de sustitución {{TAG}} y mapeo de secciones generales.
        """
        topic = data.get("topic") or data.get("title") or "Documento Pedagógico"
        teacher_name = cls._clean_teacher_title(data.get("teacher_name") or "Docente")
        grade_str = f"{data.get('grade', 5)}.° de Secundaria"
        specialty = data.get("specialty") or "Educación para el Trabajo"

        replacements = {
            "{{TITULO}}": topic.upper(),
            "{{TEMA}}": topic,
            "{{DOCENTE}}": teacher_name,
            "{{GRADO}}": grade_str,
            "{{ESPECIALIDAD}}": specialty,
            "{{PROPOSITO}}": data.get("purpose") or f"Desarrollar capacidades en {topic}.",
            "{{ANO}}": "2026",
            "{{COLEGIO}}": "CET N° 34 (I.E. INEI N.º 34)"
        }

        # Reemplazo en párrafos
        for p in doc.paragraphs:
            for tag, val in replacements.items():
                if tag in p.text:
                    cls._set_p_text_preserving_runs(p, p.text.replace(tag, val))

        # Reemplazo en celdas de tablas
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for tag, val in replacements.items():
                        if tag in cell.text:
                            cls._set_cell_text_preserving_runs(cell, cell.text.replace(tag, val))

    # -------------------------------------------------------------
    # Renderizado PDF desde Plantilla
    # -------------------------------------------------------------
    @classmethod
    def render_pdf_from_template(
        cls,
        template_bytes: bytes,
        doc_data: Dict[str, Any]
    ) -> bytes:
        """
        Genera el PDF correspondiente al documento basado en plantilla.
        Aplica los estilos, márgenes y membretes institucionales sincronizados.
        """
        from app.ai.document_exporter import generate_pdf_bytes, generate_unit_pdf_bytes
        doc_type = doc_data.get("doc_type") or "sesion_aprendizaje"
        if doc_type in ["unidad_didactica", "unidad_aprendizaje"]:
            return generate_unit_pdf_bytes(doc_data)
        return generate_pdf_bytes(doc_data, target=doc_data.get("target", "teacher"))

    # -------------------------------------------------------------
    # Métodos Auxiliares de Estilizado y Manipulación XML
    # -------------------------------------------------------------
    @classmethod
    def _set_p_text_preserving_runs(cls, p, new_text: str):
        """
        Reemplaza el texto de un párrafo preservando las propiedades XML del primer run
        (fuente, tamaño, color, negrita, cursiva) sin destruir el nodo w:rPr.
        """
        if not p.runs:
            p.add_run(new_text)
            return

        p.runs[0].text = new_text
        for extra_run in p.runs[1:]:
            extra_run.text = ""

    @classmethod
    def _set_cell_text_preserving_runs(cls, cell, new_text: str):
        """
        Actualiza el texto de una celda de tabla preservando las propiedades de fuente
        y alineación del párrafo original, y eliminando SIEMPRE los párrafos residuales de la plantilla.
        """
        if not cell.paragraphs:
            p = cell.add_paragraph()
            p.add_run(new_text or "")
            return

        p0 = cell.paragraphs[0]
        font_name = None
        font_size = None
        bold = False
        italic = False
        if p0.runs:
            r0 = p0.runs[0]
            font_name = r0.font.name
            font_size = r0.font.size
            bold = r0.bold
            italic = r0.italic

        # ELIMINAR SIEMPRE todos los párrafos posteriores (p1, p2, p3...)
        # de modo que nunca quede texto residual de la plantilla original
        for extra_p in list(cell.paragraphs[1:]):
            p_elem = extra_p._element
            p_elem.getparent().remove(p_elem)

        if not new_text:
            cls._set_p_text_preserving_runs(p0, "")
            return

        lines = str(new_text).split("\n")
        cls._set_p_text_preserving_runs(p0, lines[0])

        for l in lines[1:]:
            new_p = cell.add_paragraph()
            r = new_p.add_run(l)
            if font_name:
                r.font.name = font_name
            if font_size:
                r.font.size = font_size
            if bold:
                r.bold = bold
            if italic:
                r.italic = italic

    @classmethod
    def resolve_verified_teacher(cls, name: Optional[str]) -> Tuple[bool, str]:
        """
        Determina si el nombre corresponde a un docente real autenticado o verificado.
        Retorna (is_verified, formatted_name).
        Si no está verificado o es genérico, retorna (False, "[Pendiente de completar]").
        """
        if not name:
            return False, "[Pendiente de completar]"

        name_clean = name.strip()
        generic_patterns = [
            r'^(?:prof(?:esor|a)?\.?\s*)?(?:docente|profesor|profesora)(?:\s+responsable|\s+de\s+especialidad|\s+titular)?$',
            r'^(?:usuario|admin|administrador|admin_user|test|docente_test|docente_api|docente_exp)$',
            r'^\[.*\]$'
        ]
        for pat in generic_patterns:
            if re.match(pat, name_clean, re.IGNORECASE):
                return False, "[Pendiente de completar]"

        if not re.match(r'^(?:prof(?:esor|a)?\.?|lic\.?|ing\.?|mg\.?|dr\.?)\s+', name_clean, re.IGNORECASE):
            name_clean = f"Prof. {name_clean}"
        return True, name_clean

    @classmethod
    def _clean_teacher_title(cls, name: str) -> str:
        """Limpia y estandariza el título honorífico del docente evitando duplicaciones."""
        if not name:
            return "DOCENTE RESPONSABLE"
        name_clean = name.strip()
        if re.match(r'^(?:docente|profesor|profesora)(?:\s+responsable)?$', name_clean, re.IGNORECASE):
            return "DOCENTE RESPONSABLE"
        if not re.match(r'^(?:prof(?:esor|a)?\.?|lic\.?|ing\.?|mg\.?|dr\.?)\s*', name_clean, re.IGNORECASE):
            return f"Prof. {name_clean}"
        return name_clean

    @classmethod
    def _build_default_gtz_activities(cls, topic: str, total_minutes: int = 225) -> List[Dict[str, Any]]:
        """
        Construye las 6 etapas GTZ con cálculo matemático exacto de minutos según duración total.
        """
        if total_minutes == 225:
            times = [10, 20, 30, 135, 20, 10]
        elif total_minutes == 135:
            times = [15, 20, 15, 60, 15, 10]
        elif total_minutes == 180:
            times = [15, 25, 20, 85, 20, 15]
        else:
            t_exec = max(30, int(total_minutes * 0.50))
            rem = total_minutes - t_exec
            t_each = rem // 5
            times = [t_each, t_each, t_each, t_exec, t_each, total_minutes - t_exec - (t_each * 4)]

        return [
            {
                "paso": "1. INFORMARSE",
                "tiempo_minutos": times[0],
                "actividad_docente": f"Presenta la situación significativa y desafiante de taller vinculada a {topic}. Plantea interrogantes orientadoras y explica los parámetros técnicos, tolerancias y normas de seguridad aplicables.",
                "actividad_estudiante": f"Analiza la situación problemática presentada sobre {topic}, participa activamente compartiendo sus saberes previos e investiga las especificaciones técnicas en el manual de especialidad."
            },
            {
                "paso": "2. PLANIFICAR",
                "tiempo_minutos": times[1],
                "actividad_docente": f"Orienta la elaboración de la hoja de operaciones y plan de trabajo para {topic}. Explica la secuencia lógica de pasos, selección de herramientas y cálculo de tiempos.",
                "actividad_estudiante": f"En equipo de taller, formula el plan de operaciones detallando la secuencia técnica de pasos, selección de herramientas, instrumentos de medición y medidas preventivas de seguridad."
            },
            {
                "paso": "3. DECIDIR",
                "tiempo_minutos": times[2],
                "actividad_docente": f"Supervisa las estrategias operativas propuestas por los equipos para {topic}. Promueve el debate técnico y valida la alternativa más eficiente y segura.",
                "actividad_estudiante": f"Debate en su cuadrilla de taller, justifica técnicamente la secuencia seleccionada frente a alternativas y asume responsabilidades operativas en el puesto de trabajo."
            },
            {
                "paso": "4. EJECUTAR",
                "tiempo_minutos": times[3],
                "actividad_docente": f"Demuestra el procedimiento técnico modelado frente a los estudiantes. Supervisa permanentemente el trabajo práctico en taller, el uso estricto del EPP y el cumplimiento del protocolo 5S.",
                "actividad_estudiante": f"Ejecuta con autonomía y destreza las operaciones técnicas de {topic} aplicando normas de seguridad e higiene, registrando mediciones y avances en su guía de trabajo."
            },
            {
                "paso": "5. CONTROLAR",
                "tiempo_minutos": times[4],
                "actividad_docente": f"Supervisa el control de calidad dimensional y funcional de los productos terminados mediante lista de verificación técnica. Brinda retroalimentación formativa inmediata.",
                "actividad_estudiante": f"Aplica instrumentos de verificación y medición para contrastar su producto frente a las tolerancias requeridas, detecta posibles desviaciones y realiza ajustes autónomos."
            },
            {
                "paso": "6. VALORAR",
                "tiempo_minutos": times[5],
                "actividad_docente": f"Conduce la plenaria de evaluación y metacognición: ¿Qué aprendimos hoy sobre {topic}? ¿Qué dificultades operativas se presentaron y cómo las superamos? Evalúa el logro con la rúbrica formativa.",
                "actividad_estudiante": f"Sustenta técnicamente su producto o evidencia final, reflexiona sobre sus logros, errores corregidos y propone compromisos de mejora continua en el taller."
            }
        ]

    @classmethod
    def _build_exam_questions(cls, topic: str, specialty: str, grade: int, c_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construye o extrae las 10 preguntas institucionales del examen divididas en Secciones A, B y C
        con solucionario detallado para la versión docente, consumiendo fielmente c_json['questions'].
        """
        qs = c_json.get("questions") or []
        if isinstance(qs, list) and len(qs) >= 10:
            # Clasificar y ordenar inteligentemente las preguntas por sección
            # Sección A: Opción múltiple (las que contienen opciones reales)
            # Sección B: Desarrollo técnico y resolución abierta
            # Sección C: Afirmaciones para Verdadero/Falso y aplicación
            mc_pool = [q for q in qs if q.get("opciones") and len(q.get("opciones")) >= 2]
            non_mc_pool = [q for q in qs if not (q.get("opciones") and len(q.get("opciones")) >= 2)]

            ordered_qs = []
            # 3 preguntas para Sección A
            for i in range(3):
                if i < len(mc_pool):
                    ordered_qs.append(mc_pool[i])
                elif non_mc_pool:
                    ordered_qs.append(non_mc_pool.pop(0))
                else:
                    ordered_qs.append(qs[i])

            # 3 preguntas para Sección B (Desarrollo)
            for i in range(3):
                if non_mc_pool:
                    ordered_qs.append(non_mc_pool.pop(0))
                elif len(mc_pool) > 3:
                    ordered_qs.append(mc_pool.pop())
                else:
                    ordered_qs.append(qs[3 + i])

            # 4 preguntas para Sección C (V/F o afirmaciones técnicas)
            for i in range(4):
                if non_mc_pool:
                    ordered_qs.append(non_mc_pool.pop(0))
                elif mc_pool:
                    ordered_qs.append(mc_pool.pop(0))
                else:
                    ordered_qs.append(qs[6 + i])

            sec_a = []
            for q in ordered_qs[:3]:
                opts = q.get("opciones") or q.get("options") or []
                if opts:
                    opt_str = "   ".join([f"(   ) {opt}" for opt in opts])
                else:
                    opt_str = f"(   ) A) Principio operativo de {topic}   (   ) B) Parámetro técnico secundario   (   ) C) Variable de control auxiliar   (   ) D) Ninguna de las anteriores"
                sec_a.append({
                    "pregunta": q.get("enunciado") or q.get("statement") or "",
                    "opciones": opt_str
                })

            sec_b = []
            for q in ordered_qs[3:6]:
                sec_b.append({
                    "pregunta": q.get("enunciado") or q.get("statement") or ""
                })

            sec_c = []
            for q in ordered_qs[6:10]:
                stmt = q.get("enunciado") or q.get("statement") or ""
                sec_c.append({
                    "enunciado": stmt
                })

            solucionario = []
            for q in ordered_qs[:10]:
                ans = q.get("respuesta_correcta") or q.get("correct_answer") or ""
                just = q.get("justificacion") or q.get("justification") or ""
                solucionario.append({
                    "respuesta": f"{ans}. Justificación técnica: {just}" if just else ans
                })

            return {
                "sec_a": sec_a,
                "sec_b": sec_b,
                "sec_c": sec_c,
                "solucionario": solucionario
            }

        # Fallback temático cuando no vienen preguntas en c_json
        is_lathe = any(k in f"{topic} {specialty}".lower() for k in ["torno", "mecanizado", "cilíndrico", "cilindrico", "mecanica de produccion"])
        is_digital = any(k in f"{topic} {specialty}".lower() for k in ["carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica", "computación", "computacion", "informática", "nube"])

        if is_lathe:
            sec_a = [
                {
                    "pregunta": "¿Cuál es la diferencia técnica fundamental entre el cilindrado de desbaste y el cilindrado de acabado en el torno?",
                    "opciones": "☐ a) El desbaste busca arranque volumétrico de viruta; el acabado busca precisión y rugosidad reducida   ☐ b) El desbaste es sin lubricación y el acabado con taladrina   ☐ c) No existe diferencia técnica"
                },
                {
                    "pregunta": "¿Qué ocurre si la punta del buril se coloca por debajo o por encima de la línea de centros del torno?",
                    "opciones": "☐ a) Altera los ángulos de corte de incidencia y desprendimiento generando rozamiento o rotura del filo   ☐ b) El motor invierte su giro   ☐ c) No afecta la operación"
                },
                {
                    "pregunta": "¿Cuál es la función técnica de la taladrina (refrigerante soluble) durante el mecanizado?",
                    "opciones": "☐ a) Disipar calor en la interfaz de corte, lubricar el filo y evacuar virutas finas   ☐ b) Dar brillo estético   ☐ c) Aumentar la dureza Rockwell del material"
                }
            ]
            sec_b = [
                {
                    "pregunta": "Calcula las RPM para tornear un eje de acero SAE 1020 de D=50 mm con Vc=25 m/min usando N = (1000*Vc)/(pi*D):"
                },
                {
                    "pregunta": "¿Por qué es obligatorio utilizar el apoyo del contrapunto en piezas cuya longitud volada supera 3 veces su diámetro (L > 3D)?"
                },
                {
                    "pregunta": "Explica la secuencia ordenada para refrentar la cara frontal de un eje cilíndrico desde la periferia hacia el centro:"
                }
            ]
            sec_c = [
                {
                    "enunciado": "La lectura e interpretación con Calibrador Vernier de 0.02 mm es indispensable para verificar tolerancias dimensionales en torno."
                },
                {
                    "enunciado": "La conicidad involuntaria en un cilindrado longitudinal suele originarse por desalineación lateral del cabezal móvil / contrapunto."
                },
                {
                    "enunciado": "El uso de guantes, bufandas o prendas holgadas está TERMINANTEMENTE PROHIBIDO al operar el torno por riesgo grave de atrapamiento."
                },
                {
                    "enunciado": "Es obligatorio retirar inmediatamente la llave del plato autocentrante tras ajustar la pieza antes de encender el torno."
                }
            ]
            solucionario = [
                {"respuesta": "a) El desbaste busca arranque volumétrico de viruta; el acabado busca precisión y rugosidad reducida. Justificación: Parámetros ap y f diferenciados."},
                {"respuesta": "a) Altera los ángulos de corte de incidencia y desprendimiento generando rozamiento o rotura del filo. Justificación: Geometría de la cuchilla."},
                {"respuesta": "a) Disipar calor en la interfaz de corte, lubricar el filo y evacuar virutas finas. Justificación: Evita el desgaste térmico acelerado."},
                {"respuesta": "N = (1000 * 25) / (3.1416 * 50) = 159.15 RPM. Justificación: Se selecciona en cabezal la velocidad normalizada más cercana (aprox 160 RPM)."},
                {"respuesta": "Para evitar la flexión radial provocada por las fuerzas de corte y prevenir vibraciones mecánicas y conicidad."},
                {"respuesta": "Fijar pieza con vuelo mínimo, centrar buril a altura de centros, regular RPM y avanzar de la periferia al centro sin dejar tetón."},
                {"respuesta": "Verdadero (V). La metrología directa con nonio de 50 divisiones asegura la conformidad de cotas según plano técnico."},
                {"respuesta": "Verdadero (V). El eje del contrapunto desfasado del husillo produce un cono en lugar de un cilindro."},
                {"respuesta": "Verdadero (V). Norma de seguridad crítica bajo Ley 29783 para evitar accidentes irreversibles por piezas rotativas."},
                {"respuesta": "Verdadero (V). Evita que la llave salga disparada como proyectil por la fuerza centrífuga al arrancar el motor."}
            ]
        elif is_digital:
            sec_a = [
                {
                    "pregunta": "¿Cuál es la función primordial de estructurar jerárquicamente carpetas y subcarpetas en el almacenamiento digital?",
                    "opciones": "☐ a) Organizar sistemáticamente la información por niveles lógicos facilitando su localización inmediata   ☐ b) Aumentar la memoria RAM del equipo   ☐ c) Ocultar archivos al usuario"
                },
                {
                    "pregunta": "¿Qué criterio caracteriza una convención de nomenclatura estándar recomendada para archivos escolares?",
                    "opciones": "☐ a) Incluir fecha normalizada, área curricular, tema y versión (ej. 2026-10-23_EPT_Carpetas_v01)   ☐ b) Usar nombres como 'tarea1' o 'final'   ☐ c) Usar caracteres especiales (?, #, $)"
                },
                {
                    "pregunta": "¿Qué nivel de permiso en la nube permite a los compañeros revisar evidencias sin riesgo de que alteren o borren el contenido?",
                    "opciones": "☐ a) Permiso de Lector (solo lectura)   ☐ b) Permiso de Editor total   ☐ c) Administrador del dominio"
                }
            ]
            sec_b = [
                {
                    "pregunta": "Explica el procedimiento técnico para identificar y depurar archivos duplicados sin perder datos esenciales:"
                },
                {
                    "pregunta": "Describe la regla 3-2-1 de copias de seguridad recomendada para la protección de portafolios digitales:"
                },
                {
                    "pregunta": "Diseña la estructura de carpetas de 3 niveles para organizar el portafolio escolar de la especialidad durante el año lectivo:"
                }
            ]
            sec_c = [
                {
                    "enunciado": "La sincronización en la nube institucional permite acceder a las evidencias actualizadas desde cualquier dispositivo autorizado."
                },
                {
                    "enunciado": "Es una buena práctica de seguridad mantener abierta la sesión de correo y nube en computadoras compartidas del colegio."
                },
                {
                    "enunciado": "El formato PDF es recomendado para entregar documentos finales porque preserva la diagramación e impide ediciones accidentales."
                },
                {
                    "enunciado": "La depuración de archivos temporales y duplicados optimiza el espacio de almacenamiento y agiliza las búsquedas."
                }
            ]
            solucionario = [
                {"respuesta": "a) Organizar sistemáticamente la información por niveles lógicos facilitando su localización inmediata. Justificación: Reduce tiempos de búsqueda."},
                {"respuesta": "a) Incluir fecha normalizada, área curricular, tema y versión. Justificación: Evita ambigüedad y confusión de versiones."},
                {"respuesta": "a) Permiso de Lector (solo lectura). Justificación: Aplica el principio de menor privilegio en seguridad digital."},
                {"respuesta": "Ordenar por nombre/tamaño/fecha, contrastar contenidos, conservar la versión más reciente, renombrar y eliminar duplicados redundantes."},
                {"respuesta": "Mantener al menos 3 copias de los datos, en 2 soportes o medios diferentes, con 1 copia fuera de las instalaciones o en la nube."},
                {"respuesta": "Carpeta raíz por año y especialidad -> subcarpetas por bimestres -> carpetas específicas de guías, evidencias y evaluaciones."},
                {"respuesta": "Verdadero (V). La sincronización bidireccional garantiza disponibilidad y respaldo continuo de los trabajos."},
                {"respuesta": "Falso (F). En equipos públicos o compartidos siempre debe cerrarse sesión para proteger la identidad y privacidad."},
                {"respuesta": "Verdadero (V). El PDF asegura fidelidad tipográfica y gráfica en cualquier pantalla o impresora."},
                {"respuesta": "Verdadero (V). Libera espacio en la cuota de almacenamiento institucional y evita saturación."}
            ]
        else:
            sec_a = [
                {
                    "pregunta": f"¿Cuál es el objetivo principal o concepto fundamental al aplicar {topic} en {specialty}?",
                    "opciones": "☐ a) Optimizar el procedimiento técnico y asegurar la calidad   ☐ b) Omitir normas de seguridad para acelerar   ☐ c) Trabajar sin calibrar herramientas"
                },
                {
                    "pregunta": f"¿Qué herramienta, instrumento o parámetro técnico es indispensable para verificar {topic}?",
                    "opciones": "☐ a) Estimación visual aproximada   ☐ b) Instrumento de medición y verificación calibrado   ☐ c) Suposiciones del operador"
                },
                {
                    "pregunta": f"¿Cuál de las siguientes alternativas describe una práctica correcta de seguridad y calidad en {topic}?",
                    "opciones": "☐ a) Utilizar el EPP reglamentario y respetar tolerancias   ☐ b) Desconectar protecciones de las máquinas   ☐ c) Dejar el puesto de trabajo desordenado"
                }
            ]
            sec_b = [
                {
                    "pregunta": f"Explica detalladamente la secuencia técnica recomendada para ejecutar {topic} en el taller de {specialty}:"
                },
                {
                    "pregunta": f"¿Qué fallas o defectos comunes pueden ocurrir durante {topic} y qué acciones correctivas inmediatas propones?"
                },
                {
                    "pregunta": f"¿Por qué es fundamental el cumplimiento estricto del protocolo 5S (orden y limpieza) al desarrollar {topic}?"
                }
            ]
            sec_c = [
                {
                    "enunciado": f"La calibración y verificación previa de herramientas es obligatoria antes de iniciar {topic}."
                },
                {
                    "enunciado": f"Las tolerancias técnicas dimensionales pueden modificarse libremente sin consultar las especificaciones."
                },
                {
                    "enunciado": f"El control de calidad durante el proceso de {topic} previene el desperdicio de material y riesgos operativos."
                },
                {
                    "enunciado": f"El uso correcto del Equipo de Protección Personal (EPP) es obligatorio para todos los integrantes del equipo."
                }
            ]
            solucionario = [
                {"respuesta": f"a) Optimizar el procedimiento técnico y asegurar la calidad. Justificación: {topic} busca eficiencia y precisión bajo normas de especialidad."},
                {"respuesta": "b) Instrumento de medición y verificación calibrado. Justificación: Garantiza exactitud en los valores y tolerancias requeridas."},
                {"respuesta": "a) Utilizar el EPP reglamentario y respetar tolerancias. Justificación: Protege la integridad del estudiante y asegura la calidad del producto."},
                {"respuesta": f"Respuesta esperada: El estudiante debe detallar preparación, ejecución paso a paso respetando tolerancias y verificación final en {topic}."},
                {"respuesta": "Respuesta esperada: Identifica al menos 2 fallas operativas típicas y propone ajuste dimensional, cambio de parámetro o corrección técnica adecuada."},
                {"respuesta": "Respuesta esperada: Argumenta que las 5S previenen accidentes, optimizan tiempos de operación y cuidan el equipamiento institucional."},
                {"respuesta": "Verdadero (V). La verificación instrumental previa es indispensable para asegurar precisión y evitar piezas defectuosas."},
                {"respuesta": "Falso (F). Las tolerancias técnicas están normalizadas y su incumplimiento genera rechazo del componente o riesgo mecánico."},
                {"respuesta": "Verdadero (V). El control formativo continuo detecta desviaciones a tiempo y ahorra recursos del taller."},
                {"respuesta": "Verdadero (V). La seguridad industrial es prioritaria y no negociable en todos los talleres de la I.E. CET N.° 34."}
            ]

        return {
            "sec_a": sec_a,
            "sec_b": sec_b,
            "sec_c": sec_c,
            "solucionario": solucionario
        }


template_engine = DocumentTemplateEngine()
