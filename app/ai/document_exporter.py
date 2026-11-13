"""
INEI SMART-CORE — Módulo SmartTeacher AI
Exportador Documental Profesional (DOCX y PDF)
I.E. INEI N.º 34 de Chancay

Generación en memoria (BytesIO) de documentos Office Open XML (.docx) válidos
y documentos portables (.pdf) de alta calidad gráfica institucional.
"""

import io
import os
import shutil
import tempfile
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from xml.sax.saxutils import escape as xml_escape

# python-docx
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

# reportlab
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, BaseDocTemplate, PageTemplate, Frame, NextPageTemplate,
    Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
import reportlab.rl_config
reportlab.rl_config.pageCompression = 0

logger = logging.getLogger("smartteacher_exporter")

# -----------------------------------------------------------------------------
# CONSTANTES INSTITUCIONALES — I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY
# -----------------------------------------------------------------------------
INSTITUTION_NAME = "I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY"
INSTITUTION_LEMA = "\"Ciencia, Trabajo y Disciplina\""
INSTITUTION_DRE = "DRE LIMA PROVINCIAS — UGEL 10 HUARAL"
INSTITUTION_COUNTRY = "REPÚBLICA DEL PERÚ — MINISTERIO DE EDUCACIÓN"

COLOR_PRIMARY_HEX = "8B0000"       # Guinda institucional INEI N.º 34
COLOR_SECONDARY_HEX = "1E293B"     # Slate 800
COLOR_MUTED_HEX = "64748B"         # Slate 500
COLOR_BG_LIGHT_HEX = "F8FAFC"      # Slate 50
COLOR_BORDER_HEX = "CBD5E1"        # Slate 300
COLOR_ACCENT_BLUE_HEX = "1D4ED8"   # Blue 700
COLOR_WARNING_BG_HEX = "FEF3C7"    # Amber 100
COLOR_WARNING_BORDER_HEX = "F59E0B"# Amber 500


# -----------------------------------------------------------------------------
# NUMBERED CANVAS PARA REPORTE PDF (Página X de Y + Membrete Pie)
# -----------------------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor(f"#{COLOR_MUTED_HEX}"))

        page_width = self._pagesize[0] if hasattr(self, '_pagesize') else A4[0]

        # Línea separadora inferior
        self.setStrokeColor(colors.HexColor(f"#{COLOR_BORDER_HEX}"))
        self.setLineWidth(0.5)
        self.line(20 * mm, 16 * mm, page_width - 20 * mm, 16 * mm)

        # Texto del pie
        left_text = f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026"
        right_text = f"Página {self._pageNumber} de {page_count}"
        self.drawString(20 * mm, 11 * mm, left_text)
        self.drawRightString(page_width - 20 * mm, 11 * mm, right_text)
        self.restoreState()


# -----------------------------------------------------------------------------
# UTILIDADES DE PARSEO Y SANITIZACIÓN DE CONTENIDO
# -----------------------------------------------------------------------------
def sanitize_text_for_xml(text: str) -> str:
    """Escapa caracteres para ReportLab evitando errores de XML."""
    if not text:
        return ""
    # Reemplazar primero entidades XML
    safe = xml_escape(str(text))
    # Reemplazar saltos de línea con <br/>
    safe = safe.replace("\n", "<br/>")
    return safe


# Patrones estrictos de detección de claves y solucionarios docentes confidenciales
# Diseñados para evitar falsos positivos con términos pedagógicos legítimos (ej. explicacion_teorica, criterios_evaluacion)
FORBIDDEN_KEY_PATTERN = re.compile(
    r'(?i)(?:^|_)(?:solucion(?:ario|es)?|clave(?:s)?|answer(?:s)?|respuesta(?:s)?_correcta(?:s)?|respuestas_oficiales|respuestas|justificaci[oó]n|justification|pauta(?:s)?|teacher_notes|notas_docente|notas_privadas|docente_solucion|evaluacion_docente)(?:_|$)'
)

OPT_MARK_PATTERN = re.compile(
    r'\s*[\(\[\*]\s*(?:CORRECTA|RESPUESTA\s+CORRECTA|RESPUESTA|CLAVE|OPCI[OÓ]N\s+CORRECTA|CORRECT)\s*[\)\]\*]\s*$',
    re.IGNORECASE
)


def _clean_student_data_recursively(item: Any) -> Any:
    """
    Sanitiza recursivamente cualquier estructura de datos para modo estudiante,
    eliminando claves confidenciales docentes y marcas de respuesta en texto,
    preservando el 100% del contenido pedagógico y explicaciones legítimas.
    """
    if isinstance(item, dict):
        sanitized = {}
        for k, v in item.items():
            k_lower = str(k).lower().strip()
            # Eliminar claves que coincidan con el patrón estricto de soluciones / claves docentes
            if FORBIDDEN_KEY_PATTERN.search(k_lower):
                continue
            sanitized[k] = _clean_student_data_recursively(v)
        return sanitized
    elif isinstance(item, list):
        return [_clean_student_data_recursively(x) for x in item]
    elif isinstance(item, str):
        return OPT_MARK_PATTERN.sub('', item).strip()
    return item



def extract_real_topic(title: Optional[str], topic: Optional[str], text: Optional[str]) -> str:
    """Extrae el tema pedagogico real evitando nombres genericos de interfaz o archivo."""
    generic_names = {
        "documento_docente_inei34", "documento_pedagogico_inei34", "guia_estudio_inei34",
        "documento_inei34_2026", "documento_inei34", "ficha_trabajo", "sesion_aprendizaje",
        "documento pedagogico inei 34", "ficha de trabajo", "sesion de aprendizaje",
        "documento_pedagogico", "documento_docente", "documento", "documento_pedagogico_inei34",
        "ficha de aprendizaje", "material pedagogico inei 34"
    }
    clean_top = (topic or "").strip()
    if clean_top and clean_top.lower() not in generic_names and len(clean_top) > 3:
        return clean_top
    clean_tit = (title or "").strip()
    if clean_tit and clean_tit.lower() not in generic_names and len(clean_tit) > 3:
        cand_m = re.search(r'(?i)(?:ficha|sesion|material|tema|guia)?(?:\\s+de\\s+aprendizaje|\\s+de\\s+trabajo)?\\s*[:\\-]\\s*(.+)', clean_tit)
        if cand_m:
            cand_tit = cand_m.group(1).strip()
            if cand_tit.lower() not in generic_names:
                return cand_tit
        return clean_tit
    if text:
        cand_m1 = re.search(r'(?i)#+\\s*(?:FICHA DE APRENDIZAJE|FICHA DE TRABAJO|SESION DE APRENDIZAJE)?\\s*[:\\-]?\\s*(.+)', text)
        if cand_m1:
            cand1 = cand_m1.group(1).strip().replace("*", "").strip()
            cand1 = re.sub(r'(?i)\\s+para\\s+[1-5].*$', '', cand1).strip()
            if cand1.lower() not in generic_names and len(cand1) > 3:
                return cand1
        cand_m2 = re.search(r'(?i)(?:sobre|acerca\\s+de|tema:?)\\s+(?:el\\s+tema\\s+de\\s+)?([^\\n\\r\\.\\,\\;\\:]{3,60})', text)
        if cand_m2:
            cand2 = cand_m2.group(1).strip().replace("*", "").strip()
            cand2 = re.sub(r'(?i)\\s+para\\s+[1-5].*$', '', cand2).strip()
            if cand2.lower() not in generic_names and len(cand2) > 3:
                return cand2
    return clean_tit or clean_top or "Desarrollo de Competencias del Área"


def parse_document_data(doc_data: Dict[str, Any], target: str = "teacher") -> Dict[str, Any]:
    """
    Normaliza y extrae la información del documento (JSON y Markdown).
    Aplica sanitización Anti-Fuga estricta y recursiva si target == 'student'.
    """
    d = dict(doc_data)
    doc_type = d.get("doc_type") or "sesion_aprendizaje"

    raw_json = d.get("content_json")
    parsed_json: Dict[str, Any] = {}
    if isinstance(raw_json, dict):
        parsed_json = dict(raw_json)
    elif isinstance(raw_json, str) and raw_json.strip():
        try:
            parsed_json = json.loads(raw_json)
        except Exception:
            parsed_json = {}

    content_md = str(d.get("content_markdown") or d.get("content") or "")

    # Sanitización estricta para estudiantes
    is_student = (target == "student")
    if is_student:
        # 1. Sanitización recursiva profunda de content_json
        parsed_json = _clean_student_data_recursively(parsed_json)

        # 2. Sanitización estricta de preguntas y opciones
        if "questions" in parsed_json and isinstance(parsed_json["questions"], list):
            sanitized_q = []
            for q in parsed_json["questions"]:
                if isinstance(q, dict):
                    qc = dict(q)
                    # Asegurar eliminación de claves de respuesta en la pregunta
                    for k in list(qc.keys()):
                        k_low = k.lower().strip()
                        if FORBIDDEN_KEY_PATTERN.search(k_low) or k_low in [
                            "explicacion", "explicación", "explicacion_docente",
                            "explicacion_respuesta", "criterio_evaluacion"
                        ]:
                            qc.pop(k, None)
                    # Limpiar opciones de marcas de respuesta y normalizar dicts a strings
                    if "opciones" in qc and isinstance(qc["opciones"], list):
                        cleaned_opts = []
                        for opt in qc["opciones"]:
                            if isinstance(opt, dict):
                                opt_str = opt.get("texto") or opt.get("text") or opt.get("option") or str(opt)
                            else:
                                opt_str = str(opt)
                            opt_clean = OPT_MARK_PATTERN.sub('', opt_str).strip()
                            cleaned_opts.append(opt_clean)
                        qc["opciones"] = cleaned_opts
                    sanitized_q.append(qc)
            parsed_json["questions"] = sanitized_q

        # 3. Sanitización de content_markdown
        # Si hay versión de estudiante explícita en JSON, priorizarla
        if parsed_json.get("student_version"):
            content_md = str(parsed_json["student_version"])
        else:
            # Eliminar comentarios HTML
            content_md = re.sub(r'<!--.*?-->', '', content_md, flags=re.DOTALL)
            # Cortar antes de cualquier sección de solucionario o clave docente
            split_regex = re.compile(
                r'(?i)#+\s*(?:SOLUCIONARIO|CLAVE(?:S)?(?:\s+DE\s+RESPUESTA(?:S)?)?|PAUTAS?(?:\s+DE\s+CORRECCI[OÓ]N)?|RESPUESTAS?(?:\s+CORRECTAS?)?|GU[IÍ]A(?:\s+DOCENTE|\s+DE\s+EVALUACI[OÓ]N)?|HOJA\s+DE\s+RESPUESTAS?(?:\s+DOCENTE)?|CORTE\s+DE\s+P[AÁ]GINA)',
                re.MULTILINE
            )
            parts = split_regex.split(content_md)
            content_md = parts[0].strip()
            # Limpiar marcas inline residuales
            content_md = re.sub(
                r'(?i)\s*[\(\[\*]\s*(?:CORRECTA|RESPUESTA|CLAVE|VERDADERA|CORRECT)\s*[\)\]\*]',
                '',
                content_md
            )

    # Limpieza rigurosa de marcadores de membrete residuales generados por la IA
    content_md = re.sub(r'(?i)\[\s*(?:insertar\s+)?(?:membrete|logo)(?:\s+oficial|\s+institucional|\s+del\s+colegio)*\s*\]', '', content_md)
    content_md = re.sub(r'(?i)\[\s*(?:membrete\s+institucional|membrete\s+oficial)\s*\]', '', content_md)

    # Limpieza estricta de solucionarios genéricos sin respuestas reales en fichas
    doc_type_raw = (d.get("doc_type") or parsed_json.get("doc_type") or "").strip().lower()
    if doc_type_raw in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
        # Si es ficha de estudiante o si el texto es solo boilerplate genérico, eliminar sección de solucionario
        generic_boilerplate_regex = re.compile(
            r'(?is)#+\s*(?:SOLUCIONARIO|CLAVE(?:S)?\s+DE\s+RESPUESTA(?:S)?|PAUTAS?\s+DOCENTES?\s+DE\s+CORRECCI[OÓ]N).*?'
            r'(?:Cada ejercicio o pregunta planteada en la ficha debe evaluarse|Para respuestas de desarrollo, ponderar el uso correcto|Error recurrente).*?$',
            re.MULTILINE
        )
        content_md = generic_boilerplate_regex.sub('', content_md).strip()
        if is_student:
            split_sol = re.compile(r'(?i)#+\s*(?:SOLUCIONARIO|CLAVE|PAUTAS?|GU[IÍ]A\s+DOCENTE)', re.MULTILINE)
            content_md = split_sol.split(content_md)[0].strip()
            if parsed_json.get("teacher_answer_key"):
                parsed_json["teacher_answer_key"] = ""

    title = d.get("title") or parsed_json.get("title") or "Documento Pedagógico"
    specialty = d.get("specialty") or parsed_json.get("specialty") or "Educación para el Trabajo"
    grade = d.get("grade") or parsed_json.get("grade") or 5
    section = d.get("section_name") or parsed_json.get("section_name") or "A"
    duration = d.get("duration_minutes") or parsed_json.get("duration_minutes") or 90
    raw_cand_topic = d.get("topic") or parsed_json.get("topic") or d.get("title") or parsed_json.get("title")
    topic = extract_real_topic(d.get("title") or parsed_json.get("title"), raw_cand_topic, content_md)

    # Si es una ficha de aprendizaje y content_json no tiene las actividades estructuradas, auto-estructurar:
    if doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
        if not parsed_json or not parsed_json.get("actividades") or not parsed_json.get("proposito"):
            from app.ai.document_schemas import build_ficha_from_dict
            t_grade = int(grade or 1)
            t_spec = str(specialty)
            t_doc = str(d.get("teacher_name") or parsed_json.get("teacher_name") or "Docente")
            ficha = build_ficha_from_dict({
                "topic": topic,
                "grade": t_grade,
                "specialty": t_spec,
                "docente": t_doc,
                "raw_prompt": content_md
            })
            parsed_json = ficha.model_dump()
            d["content_json"] = parsed_json

    # Ajuste contextual de especialidad si el tema es digital
    t_low = (topic or "").lower()
    spec_low = (specialty or "").lower()
    if any(k in t_low for k in ["carpeta digital", "carpetas digitales", "archivos", "ofimática", "ofimatica", "nube", "google drive", "computación", "computacion", "informática", "informatica"]):
        if "mecan" in spec_low or "general" in spec_low or "educación para el trabajo" in spec_low:
            specialty = "Computación e Informática"

    clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "")
    is_digital_topic = any(k in f"{topic} {clean_spec}".lower() for k in [
        "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
        "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
    ])

    # Normalización estricta de Competencia CNEB oficial por área curricular:
    from app.ai.document_schemas import normalize_cneb_competence
    raw_comp = str(d.get("competence") or parsed_json.get("competence") or "").strip()
    competence = normalize_cneb_competence(raw_comp, specialty, topic)

    spec_l = specialty.lower()
    if any(k in spec_l for k in ["ciencia", "cyt", "biolog", "químic", "físic"]):
        capacidades = "Comprende y usa conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo. Evalúa las implicancias del saber y del quehacer científico y tecnológico."
        desempeno = f"Explica la estructura, función y relaciones de {topic} a partir de evidencias científicas y modelos conceptuales."
    elif any(k in spec_l for k in ["matem", "álgebr", "geometr", "aritm"]):
        capacidades = "Traduce cantidades a expresiones numéricas. Comunica su comprensión sobre los números y las operaciones. Usa estrategias y procedimientos de estimación y cálculo. Argumenta afirmaciones sobre las relaciones numéricas."
        desempeno = f"Establece relaciones entre datos y acciones referidas a {topic}, transformándolas a expresiones numéricas y justificando los procedimientos empleados."
    elif any(k in spec_l for k in ["desarrollo personal", "dpcc", "ciudadan"]):
        capacidades = "Se valora a sí mismo. Autorregula sus emociones. Reflexiona y argumenta éticamente. Vive su sexualidad de manera integral y responsable."
        desempeno = f"Explica las características y dinámicas de {topic} valorando la propia identidad y proponiendo pautas de convivencia armónica."
    else:
        capacidades = f"Aplica habilidades técnicas en {topic}. Trabaja cooperativamente para lograr objetivos y metas."
        desempeno = (
            f"Ejecuta el procedimiento técnico y conceptual de {topic} cumpliendo con especificaciones técnicas y normas de seguridad en el laboratorio de cómputo y entorno digital."
            if is_digital_topic else
            f"Ejecuta el procedimiento técnico y conceptual de {topic} cumpliendo con especificaciones técnicas y normas de seguridad en taller."
        )

    _raw_purpose = d.get("purpose") or parsed_json.get("purpose") or ""
    _PURPOSE_UI_LABELS = {
        "copiar propósito", "copiar proposito", "propósito de aprendizaje",
        "escribe el propósito", "escribe aquí el propósito", "ingresa el propósito",
        "propósito...", "proposito", "opcional", ""
    }
    if not _raw_purpose or _raw_purpose.strip().lower() in _PURPOSE_UI_LABELS:
        purpose = f"Comprender y aplicar los principios y operaciones clave de {topic}, formulando soluciones prácticas y verificables."
    else:
        purpose = _raw_purpose.strip()

    evidence = (
        parsed_json.get("evidencia") or
        (parsed_json.get("propositos") or {}).get("evidencia") or
        f"Ficha de trabajo desarrollada con ejercicios y reporte técnico de {topic} finalizado."
    )

    # Reto contextualizado coherente
    custom_reto = parsed_json.get("situacion_reto") or parsed_json.get("situacion_significativa") or parsed_json.get("reto") or parsed_json.get("desafio")
    if custom_reto and isinstance(custom_reto, str) and len(custom_reto.strip()) > 15:
        reto_text = custom_reto.strip()
    else:
        reto_text = (
            f"En el laboratorio de cómputo y entorno digital de la I.E. CET N.° 34 de Chancay, los estudiantes deben implementar una solución eficiente relacionada con {topic}. "
            f"El reto consiste en estructurar los espacios de almacenamiento, normalizar archivos y verificar que el resultado "
            f"cumpla con los estándares de organización documental y seguridad digital esperados en la comunidad escolar."
            if is_digital_topic else
            f"En el taller de la I.E. CET N.° 34 de Chancay, los estudiantes deben implementar una solución eficiente relacionada con {topic}. "
            f"El reto consiste en identificar las necesidades técnicas, planificar las operaciones requeridas y verificar que el resultado "
            f"cumpla con los estándares de calidad y seguridad industrial esperados en la comunidad."
        )

    # Marco teórico
    custom_teor = parsed_json.get("marco_teorico") or parsed_json.get("conceptos_clave")
    if custom_teor and isinstance(custom_teor, str) and len(custom_teor.strip()) > 15:
        teor_text = custom_teor.strip()
    else:
        teor_text = (
            f"{topic} es fundamental en el área de {clean_spec}. Permite organizar recursos, optimizar tiempos de trabajo "
            f"y prevenir errores operacionales. La correcta ejecución de sus principios técnicos garantiza resultados precisos, "
            f"seguros y alineados con las demandas productivas y de servicio de nuestro entorno local."
        )

    # Actividades pedagógicas unificadas (Actividades 1, 2, 3)
    acts = parsed_json.get("actividades") or parsed_json.get("actividades_principales") or []
    # Si no vienen en JSON, extraer de Markdown si existen
    if not acts and content_md:
        extracted_acts = []
        act_pattern = re.compile(
            r'(?i)(?:####|###|\*\*)\s*(?:Actividad|Ejercicio)\s*([0-9]+)\s*[:\-–—]\s*([^\r\n]+)(.*?)(?=(?:####|###|\*\*)\s*(?:Actividad|Ejercicio|\bIII\b|\bIV\b|\bV\b|\bVI\b|INSTRUMENTO|EVALUACI)|$)',
            re.DOTALL
        )
        for m in act_pattern.finditer(content_md):
            num = m.group(1).strip()
            tit = m.group(2).strip().replace('*', '').strip()
            body_text = m.group(3).strip()
            clean_body = re.sub(r'\s+', ' ', body_text).strip()
            desc = f"{tit}: {clean_body}" if clean_body else tit
            extracted_acts.append({
                "numero": int(num) if num.isdigit() else len(extracted_acts) + 1,
                "titulo": tit,
                "descripcion": desc[:250]
            })
        if extracted_acts:
            acts = extracted_acts
            parsed_json["actividades"] = acts

    def _extract_act_text(item, fallback_tit, fallback_desc):
        if not item:
            return fallback_desc
        if isinstance(item, dict):
            t = (item.get("titulo") or "").strip()
            inst = (item.get("instrucciones") or item.get("descripcion") or item.get("detalle") or "").strip()
            if t and inst:
                return f"{t}: {inst}"
            return inst or t or fallback_desc
        return str(item).strip() or fallback_desc

    act1_desc = _extract_act_text(acts[0] if len(acts) > 0 else None, "Identificación técnica", f"Identificación técnica: Describe los tres componentes o pasos esenciales involucrados en {topic}.")
    act2_desc = _extract_act_text(acts[1] if len(acts) > 1 else None, "Análisis operativo", (
        f"Análisis operativo: Explica qué medidas de seguridad digital y protección de datos debes tomar antes de compartir y respaldar {topic}."
        if is_digital_topic else
        f"Análisis operativo: Explica qué medidas de seguridad y prevención debes tomar antes de ejecutar {topic}."
    ))
    act3_desc = _extract_act_text(acts[2] if len(acts) > 2 else None, "Propuesta de mejora", f"Propuesta de mejora: Propón una optimización técnica o de procedimientos para hacer más eficiente el trabajo en {topic}.")

    # Actividad de extensión
    custom_ext = parsed_json.get("actividad_extension") or parsed_json.get("extension")
    if custom_ext and isinstance(custom_ext, str) and len(custom_ext.strip()) > 15:
        ext_text = custom_ext.strip()
    else:
        ext_text = (
            f"Elabora en equipo un diagrama o ficha técnica de {topic} que sirva como guía rápida de gestión documental y respaldos en la nube. "
            f"Incluye recomendaciones prácticas para tus compañeros y formula una conclusión sobre la utilidad de este aprendizaje para tu portafolio digital."
            if is_digital_topic else
            f"Elabora en equipo un diagrama o ficha técnica de {topic} que sirva como guía rápida de taller. "
            f"Incluye recomendaciones prácticas para tus compañeros y formula una conclusión sobre la utilidad de este aprendizaje para tu proyecto formativo."
        )

    # Extracción inteligente de lista de cotejo de Markdown si parsed_json no la contiene
    if not parsed_json.get("lista_cotejo") and not parsed_json.get("lista_cotejo_autoevaluacion") and content_md:
        extracted_chk = []
        in_chk_tbl = False
        for l_chk in content_md.splitlines():
            line_s = l_chk.strip()
            if line_s.startswith("|") and line_s.endswith("|"):
                parts = [p.strip() for p in line_s[1:-1].split("|")]
                if len(parts) >= 3:
                    p0_low = parts[0].lower()
                    if any(h in p0_low for h in ["criterio", "indicador", "desempeño", "desempeno"]) or "---" in parts[0]:
                        in_chk_tbl = True
                        continue
                    if in_chk_tbl:
                        crit_clean = re.sub(r'[*_`]', '', parts[0]).strip()
                        if crit_clean and not crit_clean.startswith("---") and not "CRITERIO" in crit_clean.upper():
                            evid_clean = parts[3].strip() if len(parts) >= 4 else f"Evidencia de {topic}"
                            extracted_chk.append({
                                "criterio": crit_clean,
                                "evidencia": evid_clean
                            })
            else:
                if in_chk_tbl and extracted_chk:
                    break
        if extracted_chk:
            parsed_json["lista_cotejo"] = extracted_chk

    # Extracción inteligente de etapas GTZ de Markdown si parsed_json no las contiene
    if doc_type == "sesion_aprendizaje":
        if not parsed_json.get("procesos_didacticos_gtz") and content_md:
            extracted_steps = []
            in_tbl = False
            for line in content_md.splitlines():
                line_s = line.strip()
                if line_s.startswith("|") and line_s.endswith("|"):
                    parts = [p.strip() for p in line_s[1:-1].split("|")]
                    if len(parts) >= 4:
                        if any(h in parts[0].lower() for h in ["paso", "etapa", "proceso", "momento"]) or "---" in parts[0]:
                            in_tbl = True
                            continue
                        if in_tbl:
                            paso_clean = re.sub(r'[*_`]', '', parts[0]).strip()
                            t_clean = parts[1].strip()
                            doc_clean = parts[2].strip()
                            est_clean = parts[3].strip()
                            if paso_clean and not paso_clean.startswith("---") and not "DOCENTE" in paso_clean:
                                extracted_steps.append({
                                    "paso": paso_clean,
                                    "tiempo": t_clean,
                                    "actividad_docente": doc_clean,
                                    "actividad_estudiante": est_clean
                                })
                else:
                    if in_tbl and extracted_steps:
                        break
            if extracted_steps:
                parsed_json["procesos_didacticos_gtz"] = extracted_steps

        if not parsed_json.get("situacion_significativa") and content_md:
            m_sit = re.search(r'(?:###\s*V\.\s*SITUACIÓN SIGNIFICATIVA|###\s*V\.\s*SITUACIN SIGNIFICATIVA|##\s*2\.\s*Situación Significativa|##\s*2\.\s*Situacin Significativa)(.*?)(?:###|##|$)', content_md, re.DOTALL | re.IGNORECASE)
            if m_sit:
                parsed_json["situacion_significativa"] = m_sit.group(1).strip()

    teacher_name = (
        d.get("teacher_name") or
        parsed_json.get("teacher_name") or
        (parsed_json.get("datos_generales_oficiales") or {}).get("docente_responsable") or
        (parsed_json.get("datos_informativos") or {}).get("docente") or
        "Profesor de Taller / Aula"
    )

    session_type = d.get("session_type") or parsed_json.get("session_type")
    structure_mode = d.get("structure_mode") or parsed_json.get("structure_mode") or "institucional"

    return {
        "doc_type": doc_type,
        "title": title,
        "specialty": specialty,
        "clean_spec": clean_spec,
        "grade": grade,
        "section": section,
        "duration": duration,
        "topic": topic,
        "competence": competence,
        "capacidades": capacidades,
        "desempeno": desempeno,
        "purpose": purpose,
        "evidence": evidence,
        "reto_text": reto_text,
        "teor_text": teor_text,
        "act1_desc": act1_desc,
        "act2_desc": act2_desc,
        "act3_desc": act3_desc,
        "ext_text": ext_text,
        "checklist": parsed_json.get("lista_cotejo") or parsed_json.get("lista_cotejo_autoevaluacion") or [],
        "teacher_name": teacher_name,
        "session_type": session_type,
        "structure_mode": structure_mode,
        "content_json": parsed_json,
        "content_markdown": content_md,
        "target": target,
        "is_student": is_student,
        "is_digital_topic": is_digital_topic,
        "status": d.get("status") or "BORRADOR",
        "visado_digital": parsed_json.get("visado_digital") or d.get("visado_digital")
    }


# =============================================================================
# EXPORTACIÓN WORD (.DOCX) — OFFICE OPEN XML VÁLIDO
# =============================================================================

def set_cell_background_color(cell, hex_color: str):
    """Establece color de fondo de una celda en tabla python-docx."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Configura márgenes internos (padding) de celda."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m_name, m_val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m_name}')
        node.set(qn('w:w'), str(m_val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_docx_header_banner(doc: Document, title: str, subtitle: str, is_confidential: bool = False):
    """Agrega membrete institucional formal de la I.E. INEI N.º 34 como párrafos estilizados (sin tablas de una sola celda)."""
    p_top = doc.add_paragraph()
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top.paragraph_format.space_before = Pt(0)
    p_top.paragraph_format.space_after = Pt(1)
    p_top.paragraph_format.keep_with_next = True
    r_top = p_top.add_run(f"{INSTITUTION_COUNTRY} | {INSTITUTION_DRE}")
    r_top.font.name = "Arial"
    r_top.font.size = Pt(8.5)
    r_top.bold = True
    r_top.font.color.rgb = RGBColor(139, 0, 0) if not is_confidential else RGBColor(124, 45, 18)

    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(1)
    p_inst.paragraph_format.space_after = Pt(1)
    p_inst.paragraph_format.keep_with_next = True
    r_inst = p_inst.add_run(INSTITUTION_NAME)
    r_inst.font.name = "Arial"
    r_inst.font.size = Pt(13)
    r_inst.bold = True
    r_inst.font.color.rgb = RGBColor(139, 0, 0) if not is_confidential else RGBColor(124, 45, 18)

    p_lema = doc.add_paragraph()
    p_lema.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lema.paragraph_format.space_before = Pt(0)
    p_lema.paragraph_format.space_after = Pt(2.5)
    p_lema.paragraph_format.keep_with_next = True
    r_lema = p_lema.add_run(INSTITUTION_LEMA)
    r_lema.font.name = "Arial"
    r_lema.font.size = Pt(8.5)
    r_lema.italic = True
    r_lema.font.color.rgb = RGBColor(100, 116, 139)

    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tit.paragraph_format.space_before = Pt(3)
    p_tit.paragraph_format.space_after = Pt(1.5)
    p_tit.paragraph_format.keep_with_next = True
    r_tit = p_tit.add_run(title.upper())
    r_tit.font.name = "Arial"
    r_tit.font.size = Pt(12)
    r_tit.bold = True
    r_tit.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(4)
    p_sub.paragraph_format.keep_with_next = True
    r_sub = p_sub.add_run(subtitle)
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(9.5)
    r_sub.bold = True
    r_sub.font.color.rgb = RGBColor(139, 0, 0) if not is_confidential else RGBColor(180, 83, 9)

    # Línea horizontal divisoria sutil
    pBrd = OxmlElement('w:pBrd')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '8')
    bottom.set(qn('w:color'), COLOR_BORDER_HEX)
    pBrd.append(bottom)
    p_sub._p.get_or_add_pPr().append(pBrd)


def add_docx_metadata_table(doc: Document, data: Dict[str, Any]):
    """Crea tabla de datos informativos organizada con bordes y fondo grisáceo (auténtica tabla de 4 columnas)."""
    table = doc.add_table(rows=3, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Configuración de anchos ajustada al ancho útil A4 (6.77 in = 17.20 cm con márgenes 0.75 in)
    col_widths = [Inches(1.45), Inches(1.93), Inches(1.45), Inches(1.94)]

    teacher_str = data.get("teacher_name") or "Prof. Responsable de Taller"
    is_session = data.get("doc_type") == "sesion_aprendizaje"
    if is_session:
        row_3 = [("Docente Responsable:", True), (teacher_str, False), ("Año Lectivo / Metodología:", True), ("2026 — Acción Completa GTZ", False)]
    else:
        row_3 = [("Docente Titular:", True), (teacher_str, False), ("Estudiante:", True), ("___________________________________", False)]

    row_data = [
        [("Área / Especialidad:", True), (data["specialty"], False), ("Grado y Sección:", True), (f"{data['grade']}° Sec. - Sección {data['section']}", False)],
        [("Tema Técnico:", True), (data["topic"], False), ("Duración Estimada:", True), (f"{data['duration']} minutos", False)],
        row_3
    ]

    for r_idx, row in enumerate(row_data):
        row_obj = table.rows[r_idx]
        trPr = row_obj._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))
        for c_idx, (text, is_bold) in enumerate(row):
            cell = row_obj.cells[c_idx]
            cell.width = col_widths[c_idx]
            set_cell_margins(cell, top=55, bottom=55, left=75, right=75)
            if is_bold:
                set_cell_background_color(cell, "F1F5F9")
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            run = p.add_run(text)
            run.font.name = "Calibri"
            run.font.size = Pt(9.5)
            run.bold = is_bold
            if is_bold:
                run.font.color.rgb = RGBColor(30, 41, 59)
            else:
                run.font.color.rgb = RGBColor(51, 65, 85)


def add_docx_student_identification_box(doc: Document, total_pts: int = 20):
    """Crea recuadro formal para que el estudiante complete sus datos en el examen/ficha."""
    table = doc.add_table(rows=2, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    c0 = table.cell(0, 0)
    c0.width = Inches(4.86)
    set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
    p0 = c0.paragraphs[0]
    p0.add_run("APELLIDOS Y NOMBRES: __________________________________________________").bold = True
    p0.runs[0].font.size = Pt(9.5)

    c1 = table.cell(0, 1)
    c1.width = Inches(1.70)
    set_cell_margins(c1, top=80, bottom=80, left=120, right=120)
    set_cell_background_color(c1, "F8FAFC")
    p1 = c1.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_nota = p1.add_run(f"CALIFICACIÓN\n[ _____ / {total_pts} pts ]")
    r_nota.bold = True
    r_nota.font.size = Pt(10)
    r_nota.font.color.rgb = RGBColor(139, 0, 0)

    c2 = table.cell(1, 0)
    c2.width = Inches(4.86)
    set_cell_margins(c2, top=80, bottom=80, left=120, right=120)
    p2 = c2.paragraphs[0]
    p2.add_run("GRADO Y SECCIÓN: _______________   FECHA: _______________   FIRMA: ____________").bold = True
    p2.runs[0].font.size = Pt(9.5)

    c3 = table.cell(1, 1)
    c3.width = Inches(1.70)
    set_cell_margins(c3, top=80, bottom=80, left=120, right=120)
    p3 = c3.paragraphs[0]
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.add_run("ESCALA CNEB\n( AD - A - B - C )").font.size = Pt(8.5)

    doc.add_paragraph()


def add_docx_heading(doc: Document, text: str, level: int = 1):
    """Agrega títulos estilizados con paleta institucional."""
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Arial"
    run.bold = True

    if level == 1:
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(139, 0, 0)  # Guinda institucional
        # Añadir pequeña línea divisoria horizontal sutil
        pBrd = OxmlElement('w:pBrd')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), COLOR_BORDER_HEX)
        pBrd.append(bottom)
        p._p.get_or_add_pPr().append(pBrd)
    elif level == 2:
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(30, 41, 59)
    else:
        p.paragraph_format.space_before = Pt(5)
        p.paragraph_format.space_after = Pt(1.5)
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(71, 85, 105)


def add_docx_callout_box(doc: Document, text: str, title: str = "NOTA PEDAGÓGICA", is_warning: bool = False):
    """Crea recuadro destacado (callout) sin tablas de una sola celda, usando bordes de párrafo."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.right_indent = Inches(0.25)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_with_next = False

    pBrd = OxmlElement('w:pBrd')
    leftBrd = OxmlElement('w:left')
    leftBrd.set(qn('w:val'), 'single')
    leftBrd.set(qn('w:sz'), '24')
    leftBrd.set(qn('w:color'), 'DC2626' if is_warning else '8B0000')
    pBrd.append(leftBrd)
    p._p.get_or_add_pPr().append(pBrd)

    r_tit = p.add_run(f"► {title}: ")
    r_tit.bold = True
    r_tit.font.name = "Calibri"
    r_tit.font.size = Pt(9.5)
    r_tit.font.color.rgb = RGBColor(180, 83, 9) if is_warning else RGBColor(139, 0, 0)

    r_body = p.add_run(text)
    r_body.font.name = "Calibri"
    r_body.font.size = Pt(9.5)
    r_body.font.color.rgb = RGBColor(30, 41, 59)


def add_docx_signatures_block(doc: Document):
    """Agrega bloque de firmas al pie del documento ajustado al ancho útil A4."""
    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(16)
    p_space.paragraph_format.keep_with_next = True

    tbl = doc.add_table(rows=1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    c0 = tbl.cell(0, 0)
    c0.width = Inches(3.28)
    p0 = c0.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p0.add_run("_________________________________________\n").bold = True
    p0.add_run("PROFESOR DE ESPECIALIDAD / AULA\n").bold = True
    p0.add_run(f"Docente Titular de {INSTITUTION_NAME}").font.size = Pt(8.5)

    c1 = tbl.cell(0, 1)
    c1.width = Inches(3.28)
    p1 = c1.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.add_run("_________________________________________\n").bold = True
    p1.add_run("V.° B.° COORDINACIÓN / DIRECCIÓN\n").bold = True
    p1.add_run(f"Dirección General — INEI N.º 34 Chancay").font.size = Pt(8.5)


def add_docx_institutional_3_signatures(doc: Document, specialty: str = "Taller", teacher_name: str = "Docente", custom_firmas: Optional[Dict[str, Any]] = None):
    """Agrega bloque oficial reglamentario de 3 firmas de la I.E. CET N° 34 / INEI N° 34 ajustado a A4."""
    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(16)
    p_space.paragraph_format.keep_with_next = True

    spec_l = specialty.lower()
    is_ept = "educación para el trabajo" in spec_l or "ept" in spec_l or any(
        k in spec_l for k in ["computaci", "mecan", "electr", "metal", "vestid", "conta"]
    )

    from app.ai.template_engine import template_engine
    is_verified, clean_teacher = template_engine.resolve_verified_teacher(teacher_name)
    doc_display = clean_teacher if is_verified else (teacher_name or "Docente Responsable")

    if custom_firmas and isinstance(custom_firmas, dict):
        f_doc = custom_firmas.get("docente") or {}
        f_jefe = custom_firmas.get("jefe_taller") or {}
        f_sub = custom_firmas.get("subdirector") or {}

        doc_name = f_doc.get("nombre") or doc_display
        doc_cargo = f_doc.get("cargo") or ("DOCENTE RESPONSABLE" if is_ept else f"DOCENTE RESPONSABLE - {specialty.upper()}")
        jefe_name = f_jefe.get("nombre") or ("Mg. Luis Arturo La Rosa Gallardo" if is_ept else "Coordinación Pedagógica de Área")
        jefe_cargo = f_jefe.get("cargo") or ("JEFE DE TALLER" if is_ept else f"COORDINACIÓN PEDAGÓGICA - {specialty.upper()}")
        sub_name = f_sub.get("nombre") or ("Mg. Javier Eulogio Rosas Maguiña" if is_ept else "Subdirección Pedagógica")
        sub_cargo = f_sub.get("cargo") or ("SUB-DIRECTOR DE ÁREA TÉCNICA" if is_ept else "SUBDIRECTORA DE FORMACIÓN GENERAL")
    else:
        doc_name = doc_display
        doc_cargo = "DOCENTE RESPONSABLE" if is_ept else f"DOCENTE RESPONSABLE - {specialty.upper()}"
        if is_ept:
            if "comput" in spec_l or "inform" in spec_l:
                jefe_name = "Mg. Luis Arturo La Rosa Gallardo"
                jefe_cargo = "JEFE DE TALLER COMPUTACIÓN E INFORMÁTICA"
            elif "mecan" in spec_l:
                jefe_name = "Prof. Responsable de Taller"
                jefe_cargo = "JEFE DE TALLER MECÁNICA DE PRODUCCIÓN"
            elif "electr" in spec_l:
                jefe_name = "Prof. Responsable de Taller"
                jefe_cargo = "JEFE DE TALLER ELECTRICIDAD Y ELECTRÓNICA"
            else:
                jefe_name = "Jefe de Taller de Especialidad"
                jefe_cargo = f"JEFE DE TALLER {specialty.upper()[:25]}"
            sub_name = "Mg. Javier Eulogio Rosas Maguiña"
            sub_cargo = "SUB-DIRECTOR ÁREA TÉCNICA"
        else:
            jefe_name = "Prof. Coordinador(a) Pedagógico(a)"
            jefe_cargo = f"COORDINACIÓN PEDAGÓGICA - {specialty.upper()}"
            sub_name = "Subdirección de Formación General"
            sub_cargo = "SUBDIRECCIÓN PEDAGÓGICA"

    tbl = doc.add_table(rows=1, cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    cols_data = [
        (doc_name, "DOCENTE RESPONSABLE", doc_cargo),
        (jefe_name, "JEFE DE TALLER" if is_ept else "COORDINADOR PEDAGÓGICO", jefe_cargo),
        (sub_name, sub_cargo, "I.E. CET N° 34 - Chancay")
    ]

    for idx, (nom, cargo, inst) in enumerate(cols_data):
        c = tbl.cell(0, idx)
        c.width = Inches(2.18)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run("_______________________________\n").bold = True
        r_c = p.add_run(f"{cargo}\n")
        r_c.bold = True
        r_c.font.size = Pt(8)
        r_n = p.add_run(f"{nom}\n")
        r_n.bold = True
        r_n.font.size = Pt(8.5)
        r_i = p.add_run(inst)
        r_i.font.size = Pt(7.5)
        r_i.font.color.rgb = RGBColor(100, 116, 139)


def add_docx_simple_teacher_signature(doc: Document, teacher_name: str = "Docente Responsable"):
    """Agrega pie de firma simple y formal del docente responsable sin tablas de una sola celda."""
    clean_name = (teacher_name or "Docente Responsable").strip()
    if clean_name.lower() in ["docente", "docente responsable", "[pendiente de completar]"]:
        clean_name = "Docente Responsable"
    elif not any(clean_name.startswith(pfx) for pfx in ["Prof.", "Lic.", "Mg.", "Dr.", "Ing."]):
        clean_name = f"Prof. {clean_name}"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    r_line = p.add_run("_________________________________________\n")
    r_line.font.color.rgb = RGBColor(100, 116, 139)

    r_nom = p.add_run(f"{clean_name}\n")
    r_nom.bold = True
    r_nom.font.name = "Calibri"
    r_nom.font.size = Pt(10)
    r_nom.font.color.rgb = RGBColor(30, 41, 59)

    r_cargo = p.add_run("Docente Responsable del Área — CET N.° 34")
    r_cargo.font.name = "Calibri"
    r_cargo.font.size = Pt(9)
    r_cargo.font.color.rgb = RGBColor(100, 116, 139)

def add_docx_session_gtz_table(doc: Document, gtz_steps: list):
    """
    Inserta la tabla oficial de procesos didácticos GTZ con EXACTAMENTE CUATRO COLUMNAS:
    Columna 1: Pasos o etapas
    Columna 2: Tiempo
    Columna 3: Acciones o actividades del docente
    Columna 4: Acciones o actividades del estudiante
    Ajustada al ancho útil A4 (6.77 in) con cantSplit y tblHeader reglamentarios.
    """
    headers = [
        "Pasos o etapas",
        "Tiempo",
        "Acciones o actividades del docente",
        "Acciones o actividades del estudiante"
    ]
    col_widths = [Inches(1.25), Inches(0.72), Inches(2.40), Inches(2.40)]

    tbl = doc.add_table(rows=len(gtz_steps) + 1, cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    # Header Row con tblHeader y cantSplit
    hdr_row = tbl.rows[0]
    trPr_hdr = hdr_row._tr.get_or_add_trPr()
    trPr_hdr.append(OxmlElement('w:tblHeader'))
    trPr_hdr.append(OxmlElement('w:cantSplit'))

    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.width = col_widths[c_idx]
        set_cell_background_color(cell, "1E293B")
        set_cell_margins(cell, top=60, bottom=60, left=70, right=70)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.font.name = "Arial"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows con cantSplit y tipografía calibrada
    for r_idx, step in enumerate(gtz_steps, start=1):
        row = tbl.rows[r_idx]
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))

        paso_nom = step.get("paso") or step.get("fase") or step.get("nombre") or f"Paso {r_idx}"
        t_val = step.get("tiempo") or step.get("tiempo_minutos") or "15"
        tiempo_str = f"{t_val} Minutos" if (str(t_val).isdigit() or str(t_val).endswith("min")) else str(t_val)
        if str(t_val).isdigit():
            tiempo_str = f"{t_val} Minutos"
        act_doc = step.get("actividad_docente") or step.get("docente") or step.get("acciones_docente") or ""
        act_est = step.get("actividad_estudiante") or step.get("estudiante") or step.get("acciones_estudiante") or ""

        row_cells = [
            (paso_nom, True, WD_ALIGN_PARAGRAPH.LEFT, Pt(9.0)),
            (tiempo_str, True, WD_ALIGN_PARAGRAPH.CENTER, Pt(8.5)),
            (act_doc, False, WD_ALIGN_PARAGRAPH.JUSTIFY, Pt(9.0)),
            (act_est, False, WD_ALIGN_PARAGRAPH.JUSTIFY, Pt(9.0))
        ]

        bg_col = "F8FAFC" if (r_idx % 2 == 1) else "FFFFFF"

        for c_idx, (val, is_bld, align, fsz) in enumerate(row_cells):
            cell = row.cells[c_idx]
            cell.width = col_widths[c_idx]
            if bg_col != "FFFFFF":
                set_cell_background_color(cell, bg_col)
            set_cell_margins(cell, top=50, bottom=50, left=70, right=70)
            p = cell.paragraphs[0]
            p.alignment = align
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = fsz
            r.bold = is_bld
            if is_bld:
                r.font.color.rgb = RGBColor(15, 23, 42)
            else:
                r.font.color.rgb = RGBColor(51, 65, 85)


def add_docx_rubric_table(doc: Document, total_pts: int = 20, topic: str = "Taller", custom_criteria: Optional[List[Dict[str, Any]]] = None, session_type: Optional[str] = None):
    """Inserta tabla formal de rúbrica analítica CNEB pertinente según la especialidad y propósito evaluado."""
    add_docx_heading(doc, f"Matriz de Rúbrica Analítica de Evaluación CNEB (Escala Vigesimal - {total_pts} Puntos)", level=2)

    headers = [
        "Criterio de Evaluación",
        f"AD: Destacado\n({int(total_pts*0.9)}-{total_pts} pts)",
        f"A: Esperado\n({int(total_pts*0.7)}-{int(total_pts*0.9)-1} pts)",
        f"B: En Proceso\n({int(total_pts*0.55)}-{int(total_pts*0.7)-1} pts)",
        f"C: En Inicio\n(0-{int(total_pts*0.55)-1} pts)"
    ]

    rows_data = []
    if custom_criteria and isinstance(custom_criteria, list) and len(custom_criteria) > 0:
        for r_idx, c_item in enumerate(custom_criteria, start=1):
            crit_name = c_item.get("criterio") or f"Criterio {r_idx}"
            ad_desc = c_item.get("ad") or "Demuestra dominio sobresaliente y autonomía en el criterio evaluado."
            a_desc = c_item.get("a") or "Cumple satisfactoriamente con los desempeños esperados del criterio."
            b_desc = c_item.get("b") or "Muestra avances parciales requiriendo retroalimentación pedagógica."
            c_desc = c_item.get("c") or "Dificultades notorias para alcanzar el nivel básico del criterio."
            rows_data.append([f"{r_idx}. {crit_name}", ad_desc, a_desc, b_desc, c_desc])
    elif session_type == "emprendimiento" or any(k in (topic or "").lower() for k in ["lean canvas", "emprendimiento", "negocio", "canvas", "startup"]):
        rows_data = [
            [
                "1. Formulación y Validación de Hipótesis en Lean Canvas",
                "Formula hipótesis precisas y contrasta con evidencias empíricas sólidas los 9 bloques del Lean Canvas de su proyecto.",
                "Modifica y valida las hipótesis principales del Lean Canvas (problema, solución, propuesta de valor y canales).",
                "Presenta hipótesis generales con escasa contrastación o validación superficial con clientes.",
                "No formula hipótesis medibles ni valida los supuestos de su modelo de negocio."
            ],
            [
                "2. Iteración y Adaptación del Modelo según el Cliente",
                "Itera con agilidad y criterio comercial la propuesta de valor incorporando retroalimentación real de usuarios.",
                "Realiza ajustes pertinentes en el lienzo respondiendo a las necesidades observadas en los clientes.",
                "Muestra resistencia a modificar su idea original a pesar de las evidencias recopiladas.",
                "No realiza adaptaciones en el Lean Canvas o no considera la opinión de los usuarios."
            ],
            [
                "3. Sustentación de Aprendizajes y Trabajo en Equipo",
                "Sustenta con claridad técnica y convicción la viabilidad de su propuesta, demostrando liderazgo cooperativo.",
                "Expone con argumentos válidos las decisiones del equipo y la viabilidad de la propuesta emprendedora.",
                "Participa en la sustentación con argumentos limitados sobre la viabilidad comercial.",
                "No sustenta los cambios realizados en el lienzo ni demuestra articulación con su equipo."
            ]
        ]
    elif session_type == "tecnica" or any(k in (topic or "").lower() for k in ["taller", "gtz", "mecaniz", "torno", "soldad", "circuit", "motor"]):
        rows_data = [
            [
                f"1. Dominio Conceptual y Fundamento Técnico de {topic}",
                "Explica principios con lenguaje técnico riguroso y sustenta todas sus respuestas con exactitud.",
                "Responde con claridad la mayoría de conceptos técnicos requeridos por la especialidad.",
                "Presenta dudas en conceptos clave o definiciones técnicas elementales de taller.",
                "No identifica los conceptos técnicos fundamentales de la especialidad."
            ],
            [
                "2. Procedimiento Técnico y Operaciones Prácticas",
                "Resuelve operaciones y maniobras con óptima precisión, tolerancias y uso racional de recursos.",
                "Desarrolla procedimientos técnicos correctos con desviaciones menores admisibles.",
                "Requiere asistencia continua para completar la secuencia técnica u operativa.",
                "Incumple el procedimiento técnico y comete errores críticos de operación."
            ],
            [
                "3. Seguridad Industrial, Uso de EPP y Metodología 5S",
                "Aplica proactivamente el protocolo 5S, porta el EPP reglamentario y previene riesgos de taller.",
                "Porta el EPP requerido e identifica las normas de seguridad aplicables a la tarea.",
                "Omite recomendaciones secundarias de seguridad o desatiende el orden en su puesto.",
                "Incurre en conductas inseguras de taller o no porta el EPP obligatorio."
            ]
        ]
    else:
        rows_data = [
            [
                f"1. Comprensión y Aplicación de Capacidades en {topic}",
                "Demuestra dominio conceptual y procedimental sobresaliente al resolver situaciones problemáticas.",
                "Aplica adecuadamente los conceptos y procedimientos formativos según los propósitos establecidos.",
                "Aplica conceptos con dudas menores, requiriendo apoyo pedagógico guiado.",
                "Dificultades evidentes para comprender y aplicar las nociones básicas del área."
            ],
            [
                "2. Estrategias de Resolución y Calidad de la Evidencia",
                "Desarrolla estrategias autónomas, creativas y fundamentadas para alcanzar la evidencia con alta calidad.",
                "Sigue la secuencia de actividades planificada completando la evidencia de aprendizaje requerida.",
                "Completa parcialmente las actividades o presenta evidencias con omisiones secundarias.",
                "No completa las actividades formativas o no presenta la evidencia solicitada."
            ],
            [
                "3. Reflexión Metacognitiva y Trabajo Autónomo",
                "Evalúa críticamente sus aciertos y errores, proponiendo acciones de mejora y autorregulación.",
                "Reconoce sus avances y dificultades, respondiendo con pertinencia a las preguntas metacognitivas.",
                "Identifica sus dificultades solo con la mediación directa del docente.",
                "Muestra escaso interés en evaluar su propio proceso formativo."
            ]
        ]

    tbl = doc.add_table(rows=len(rows_data) + 1, cols=5)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    widths = [Inches(1.76), Inches(1.2), Inches(1.2), Inches(1.2), Inches(1.2)]

    # Encabezados
    for c_idx, h_text in enumerate(headers):
        cell = tbl.cell(0, c_idx)
        cell.width = widths[c_idx]
        set_cell_background_color(cell, "1E293B")
        set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h_text)
        r.bold = True
        r.font.name = "Arial"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    # Filas
    for r_idx, r_vals in enumerate(rows_data):
        for c_idx, val in enumerate(r_vals):
            cell = tbl.cell(r_idx + 1, c_idx)
            cell.width = widths[c_idx]
            if c_idx == 0:
                set_cell_background_color(cell, "F8FAFC")
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 0 else WD_ALIGN_PARAGRAPH.JUSTIFY
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.5)
            if c_idx == 0:
                r.bold = True
                r.font.color.rgb = RGBColor(30, 41, 59)

    doc.add_paragraph()


def _repeat_table_header_docx(row):
    """Marca la primera fila de una tabla para repetirse automáticamente como encabezado en cada página."""
    try:
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(r'<w:tblHeader %s/>' % nsdecls('w')))
        trPr.append(parse_xml(r'<w:cantSplit %s/>' % nsdecls('w')))
    except Exception:
        pass



# -----------------------------------------------------------------------------
# ESTAMPILLA INSTITUCIONAL DE VISADO DIGITAL Y CÓDIGO QR (BLOQUE 3)
# -----------------------------------------------------------------------------
def _generate_qr_png_bytes(data_str: str, box_size: int = 5, border: int = 2) -> bytes:
    """
    Genera en memoria los bytes binarios de una imagen PNG con el código QR.
    Utiliza el motor nativo ReportLab QrCodeWidget y Pillow (PIL).
    """
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from PIL import Image
    import io

    widget = QrCodeWidget(data_str)
    widget.getBounds()  # Inicializa la matriz de módulos
    qr = widget.qr
    mod_count = qr.getModuleCount()

    img_size = (mod_count + border * 2) * box_size
    img = Image.new('RGB', (img_size, img_size), 'white')
    pixels = img.load()

    for r in range(mod_count):
        for c in range(mod_count):
            if qr.isDark(r, c):
                for bx in range(box_size):
                    for by in range(box_size):
                        pixels[(c + border) * box_size + bx, (r + border) * box_size + by] = (0, 0, 0)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def add_docx_digital_visa_stamp(doc: Document, visa_data: Dict[str, Any]):
    """
    Inserta la estampilla institucional de visado digital directivo en el documento Word (.docx).
    Incluye código QR verificable, identificación del Director, código único y hash SHA-256.
    """
    if not visa_data or not isinstance(visa_data, dict):
        return

    code = visa_data.get("verification_code") or "INEI-VISA-OFICIAL"
    approver = visa_data.get("approver_name") or "Lic. César Tinedo Jiménez"
    role = visa_data.get("approver_role") or "DIRECTOR GENERAL"
    approved_at = visa_data.get("approved_at") or "2026-11-02 16:00:00"
    doc_hash = visa_data.get("document_hash") or ""
    hash_short = doc_hash[:24] + "..." if len(doc_hash) > 24 else doc_hash
    url = visa_data.get("verification_url") or f"/verificar-documento/{code}"
    if not url.startswith("http"):
        url = f"https://inei34chancay.edu.pe{url}"

    qr_bytes = _generate_qr_png_bytes(url, box_size=5, border=2)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(12)
    p_spacer.paragraph_format.space_after = Pt(4)
    p_spacer.paragraph_format.keep_with_next = True

    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    table.columns[0].width = Inches(1.3)
    table.columns[1].width = Inches(5.2)

    # Columna 0: Código QR
    cell_qr = table.cell(0, 0)
    cell_qr.width = Inches(1.3)
    cell_qr.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p_qr = cell_qr.paragraphs[0]
    p_qr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_qr.paragraph_format.space_before = Pt(2)
    p_qr.paragraph_format.space_after = Pt(2)
    run_qr = p_qr.add_run()
    run_qr.add_picture(io.BytesIO(qr_bytes), width=Inches(1.1), height=Inches(1.1))

    # Columna 1: Datos Oficiales del Visado
    cell_txt = table.cell(0, 1)
    cell_txt.width = Inches(5.2)
    cell_txt.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    p1 = cell_txt.paragraphs[0]
    p1.paragraph_format.space_before = Pt(0)
    p1.paragraph_format.space_after = Pt(1)
    r1 = p1.add_run("I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY • DIRECCIÓN GENERAL\n")
    r1.font.name = "Arial"
    r1.font.size = Pt(8.5)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(139, 0, 0)

    r2 = p1.add_run("VISADO DIGITAL INSTITUCIONAL • DIRECCIÓN GENERAL\n")
    r2.font.name = "Arial"
    r2.font.size = Pt(10)
    r2.font.bold = True
    r2.font.color.rgb = RGBColor(30, 41, 59)

    p2 = cell_txt.add_paragraph()
    p2.paragraph_format.space_before = Pt(1)
    p2.paragraph_format.space_after = Pt(1)
    r3 = p2.add_run(f"Visado por: {approver} ({role})\n")
    r3.font.name = "Arial"
    r3.font.size = Pt(8)
    r3.font.bold = True

    r4 = p2.add_run(f"Fecha de Aprobación: {approved_at}  •  Código: {code}\n")
    r4.font.name = "Consolas"
    r4.font.size = Pt(7.5)
    r4.font.bold = True
    r4.font.color.rgb = RGBColor(139, 0, 0)

    r5 = p2.add_run(f"Integridad SHA-256: {hash_short} (Control Interno SHA-256) • Escanear código QR para verificar")
    r5.font.name = "Arial"
    r5.font.size = Pt(7)
    r5.font.italic = True
    r5.font.color.rgb = RGBColor(100, 116, 139)

    # Fondo suave y bordes institucionales
    for cell in [cell_qr, cell_txt]:
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="FFF8F8"/>')
        tcPr.append(shd)

    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="12" w:space="0" w:color="8B0000"/>'
        f'<w:left w:val="single" w:sz="12" w:space="0" w:color="8B0000"/>'
        f'<w:bottom w:val="single" w:sz="12" w:space="0" w:color="8B0000"/>'
        f'<w:right w:val="single" w:sz="12" w:space="0" w:color="8B0000"/>'
        f'<w:insideH w:val="none"/>'
        f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="F3D8D8"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)


def create_pdf_digital_visa_stamp_table(visa_data: Dict[str, Any]) -> Table:
    """
    Construye la tabla Flowable de ReportLab con la estampilla institucional y el QR vectorial.
    """
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing

    code = visa_data.get("verification_code") or "INEI-VISA-OFICIAL"
    approver = visa_data.get("approver_name") or "Lic. César Tinedo Jiménez"
    role = visa_data.get("approver_role") or "DIRECTOR GENERAL"
    approved_at = visa_data.get("approved_at") or "2026-11-02 16:00:00"
    doc_hash = visa_data.get("document_hash") or ""
    hash_short = doc_hash[:24] + "..." if len(doc_hash) > 24 else doc_hash
    url = visa_data.get("verification_url") or f"/verificar-documento/{code}"
    if not url.startswith("http"):
        url = f"https://inei34chancay.edu.pe{url}"

    qr_widget = QrCodeWidget(url)
    qr_bounds = qr_widget.getBounds()
    qw = qr_bounds[2] - qr_bounds[0]
    qh = qr_bounds[3] - qr_bounds[1]
    qr_drawing = Drawing(48, 48, transform=[48. / qw, 0, 0, 48. / qh, 0, 0])
    qr_drawing.add(qr_widget)

    styles = getSampleStyleSheet()
    style_stamp_header = ParagraphStyle(
        'StampHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor('#8B0000')
    )
    style_stamp_title = ParagraphStyle(
        'StampTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )
    style_stamp_body = ParagraphStyle(
        'StampBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#334155')
    )
    style_stamp_code = ParagraphStyle(
        'StampCode',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#8B0000')
    )
    style_stamp_hash = ParagraphStyle(
        'StampHash',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#64748B')
    )

    txt_flowables = [
        Paragraph("I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY • DIRECCIÓN GENERAL", style_stamp_header),
        Paragraph("VISADO DIGITAL INSTITUCIONAL • DIRECCIÓN GENERAL", style_stamp_title),
        Paragraph(f"<b>Visado por:</b> {approver} ({role}) — <b>Fecha:</b> {approved_at}", style_stamp_body),
        Paragraph(f"<b>Código de Verificación:</b> {code}", style_stamp_code),
        Paragraph(f"<b>Integridad SHA-256:</b> {hash_short} (Control Interno SHA-256) • Escanear código QR para verificar", style_stamp_hash)
    ]

    stamp_table = Table([[qr_drawing, txt_flowables]], colWidths=[20 * mm, 140 * mm])
    stamp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8F8')),
        ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#8B0000')),
        ('LINEBEFORE', (1, 0), (1, 0), 0.5, colors.HexColor('#F3D8D8')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return stamp_table


def generate_unit_docx_bytes(doc_data: Dict[str, Any]) -> bytes:
    """
    Genera un archivo Microsoft Word (.docx) oficial para la Unidad Didáctica Institucional
    rellenando la plantilla oficial CET N.º 34 (unidad_didactica_cet34.docx) mediante el motor
    de plantillas DocumentTemplateEngine para garantizar 100% de fidelidad al formato oficial.
    """
    data = parse_document_data(doc_data, target="teacher")
    tpl_candidates = [
        os.path.abspath(os.path.join("data", "templates", "smartteacher", "unidad_didactica_cet34.docx")),
        os.path.abspath(os.path.join("app", "templates", "smartteacher", "unidad_didactica_cet34.docx")),
    ]
    tpl_path = None
    for cand in tpl_candidates:
        if os.path.exists(cand):
            tpl_path = cand
            break

    if tpl_path:
        try:
            from app.ai.template_engine import template_engine
            with open(tpl_path, "rb") as fp:
                tpl_b = fp.read()
            merged_payload = {**data, **doc_data, "doc_type": "unidad_didactica"}
            return template_engine.render_docx_from_template(tpl_b, merged_payload)
        except Exception as e:
            logger.warning(f"Error renderizando desde plantilla oficial unidad_didactica_cet34.docx: {e}")

    c_json = data.get("content_json") or {}
    if isinstance(c_json, str):
        try:
            c_json = json.loads(c_json)
        except Exception:
            c_json = {}

    gen = c_json.get("datos_generales") or {}
    title = data.get("title") or c_json.get("title") or "UNIDAD DIDÁCTICA INSTITUCIONAL"
    specialty = gen.get("especialidad") or data.get("specialty") or "Educación para el Trabajo"
    teacher_name = gen.get("docente_responsable") or data.get("teacher_name") or "Docente"
    desc_unidad = c_json.get("descripcion_unidad") or ""
    tech_matrix = c_json.get("matriz_habilidades_tecnicas") or []
    ent_matrix = c_json.get("matriz_habilidades_emprendimiento") or []
    tech_purp = c_json.get("propositos_tecnicos") or {}
    ent_purp = c_json.get("propositos_emprendimiento") or {}
    sessions = c_json.get("organizacion_sesiones") or []
    biblio = c_json.get("bibliografia") or []
    firmas = c_json.get("firmas_institucionales") or {}

    doc = Document()

    # Configuración de página en orientación horizontal (Landscape A4)
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11.69)
    section.page_height = Inches(8.27)
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    # Membrete institucional
    add_docx_header_banner(
        doc,
        title=title,
        subtitle="PROGRAMACIÓN Y PLANIFICACIÓN CURRICULAR EN CASCADA CNEB / EPT 2026"
    )

    # I. DATOS GENERALES
    add_docx_heading(doc, "I. DATOS GENERALES", level=1)
    t_gen = doc.add_table(rows=6, cols=2)
    t_gen.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_gen.autofit = False

    meta_rows = [
        (f"• Institución Educativa: {gen.get('institucion', INSTITUTION_NAME)}", f"• DRE / UGEL: {gen.get('dre_ugel', INSTITUTION_DRE)}"),
        (f"• Área Curricular: {gen.get('area_curricular', 'Educación para el Trabajo')}", f"• Especialidad Técnica: {specialty}"),
        (f"• Módulo Formativo: {gen.get('modulo_formativo', 'Módulo Formativo de Especialidad')}", f"• Grado y Secciones: {gen.get('grado_secciones', 'Secundaria')}"),
        (f"• Docente Responsable: {teacher_name}", f"• Director: {gen.get('director', 'Tomas Jurado Zevallos')}"),
        (f"• Subdirector Área Técnica: {gen.get('subdirector', 'Mg. Javier Eulogio Rosas Maguiña')}", f"• Jefe de Taller: {gen.get('jefe_taller', 'Jefe de Taller de Especialidad')}"),
        (f"• Periodo: {gen.get('fecha_inicio', 'Octubre 2026')} al {gen.get('fecha_fin', 'Diciembre 2026')}", f"• Carga Horaria: {gen.get('duracion_semanas', 9)} semanas ({gen.get('horas_semanales', 8)} h/sem — Total: {gen.get('total_horas', 72)} horas)")
    ]

    for r_idx, (col1_txt, col2_txt) in enumerate(meta_rows):
        c1, c2 = t_gen.cell(r_idx, 0), t_gen.cell(r_idx, 1)
        c1.width = Inches(5.05)
        c2.width = Inches(5.05)
        set_cell_background_color(c1, "F8FAFC" if r_idx % 2 == 0 else "FFFFFF")
        set_cell_background_color(c2, "F8FAFC" if r_idx % 2 == 0 else "FFFFFF")
        set_cell_margins(c1, top=60, bottom=60, left=90, right=90)
        set_cell_margins(c2, top=60, bottom=60, left=90, right=90)
        p1 = c1.paragraphs[0]
        p1.add_run(col1_txt).font.size = Pt(8.5)
        p2 = c2.paragraphs[0]
        p2.add_run(col2_txt).font.size = Pt(8.5)

    doc.add_paragraph()

    # II. DESCRIPCIÓN DE LOS APRENDIZAJES
    add_docx_heading(doc, "II. DESCRIPCIÓN DE LOS APRENDIZAJES", level=1)
    p_desc = doc.add_paragraph()
    p_desc.paragraph_format.line_spacing = 1.15
    p_desc.paragraph_format.space_after = Pt(8)
    r_desc = p_desc.add_run(desc_unidad)
    r_desc.font.size = Pt(9.5)

    # III. MATRIZ DE HABILIDADES TÉCNICAS
    if tech_matrix:
        add_docx_heading(doc, "III. MATRIZ DE HABILIDADES TÉCNICAS (ÁREA DE TALLER)", level=1)
        t_tm = doc.add_table(rows=len(tech_matrix) + 1, cols=4)
        t_tm.alignment = WD_TABLE_ALIGNMENT.CENTER
        t_tm.autofit = False
        _repeat_table_header_docx(t_tm.rows[0])

        headers_tm = ["Sem.", "Habilidad Técnica Priorizada", "Desempeños Específicos de Taller", "Estándar del Módulo y Ejes"]
        widths_tm = [Inches(0.65), Inches(2.2), Inches(3.9), Inches(3.35)]

        for c_idx, h_text in enumerate(headers_tm):
            cell = t_tm.cell(0, c_idx)
            cell.width = widths_tm[c_idx]
            set_cell_background_color(cell, "1E293B")
            set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
            p = cell.paragraphs[0]
            r = p.add_run(h_text)
            r.bold = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, row_data in enumerate(tech_matrix):
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            vals = [
                f"Sem. {row_data.get('semana', r_idx + 1)}",
                row_data.get("habilidad_tecnica", ""),
                row_data.get("desempenos", ""),
                f"{row_data.get('estandar_modulo', '')}\nEje: {row_data.get('ejes_transversales', '')}"
            ]
            for c_idx, val in enumerate(vals):
                cell = t_tm.cell(r_idx + 1, c_idx)
                cell.width = widths_tm[c_idx]
                set_cell_background_color(cell, bg)
                set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
                p = cell.paragraphs[0]
                r = p.add_run(val)
                r.font.size = Pt(8.5)
                if c_idx == 0:
                    r.bold = True

        doc.add_paragraph()

    # IV. MATRIZ DE HABILIDADES DE EMPRENDIMIENTO
    if ent_matrix:
        add_docx_heading(doc, "IV. MATRIZ DE HABILIDADES DE EMPRENDIMIENTO (DESIGN THINKING Y LEAN CANVAS)", level=1)
        t_em = doc.add_table(rows=len(ent_matrix) + 1, cols=4)
        t_em.alignment = WD_TABLE_ALIGNMENT.CENTER
        t_em.autofit = False
        _repeat_table_header_docx(t_em.rows[0])

        headers_em = ["Sem.", "Habilidad de Emprendimiento", "Desempeños de Gestión y Validación", "Estándar de Ciclo y Ejes"]
        widths_em = [Inches(0.65), Inches(2.2), Inches(3.9), Inches(3.35)]

        for c_idx, h_text in enumerate(headers_em):
            cell = t_em.cell(0, c_idx)
            cell.width = widths_em[c_idx]
            set_cell_background_color(cell, "1E293B")
            set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
            p = cell.paragraphs[0]
            r = p.add_run(h_text)
            r.bold = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, row_data in enumerate(ent_matrix):
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            vals = [
                f"Sem. {row_data.get('semana', r_idx + 1)}",
                row_data.get("habilidad_emprendimiento", ""),
                row_data.get("desempenos", ""),
                f"{row_data.get('estandar_ciclo', '')}\nEje: {row_data.get('ejes_transversales', '')}"
            ]
            for c_idx, val in enumerate(vals):
                cell = t_em.cell(r_idx + 1, c_idx)
                cell.width = widths_em[c_idx]
                set_cell_background_color(cell, bg)
                set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
                p = cell.paragraphs[0]
                r = p.add_run(val)
                r.font.size = Pt(8.5)
                if c_idx == 0:
                    r.bold = True

        doc.add_paragraph()

    # V & VI. PROPÓSITOS DE APRENDIZAJE TÉCNICOS Y DE EMPRENDIMIENTO
    add_docx_heading(doc, "V. PROPÓSITOS DE APRENDIZAJE TÉCNICOS Y DE EMPRENDIMIENTO", level=1)
    p_tp = doc.add_paragraph()
    p_tp.paragraph_format.line_spacing = 1.15
    p_tp.add_run("1. Propósitos de Aprendizaje Técnicos (Área de Taller):\n").bold = True
    p_tp.add_run(f"• Competencia: {tech_purp.get('competencia', 'Gestiona proyectos de emprendimiento económico o social')}\n")
    p_tp.add_run(f"• Estándar Esperado: {tech_purp.get('estandar_esperado', 'Aplica destrezas técnicas en máquinas y herramientas')}\n")
    for cap in tech_purp.get("capacidades", []):
        p_tp.add_run(f"   - {cap}\n")

    p_ep = doc.add_paragraph()
    p_ep.paragraph_format.line_spacing = 1.15
    p_ep.add_run("2. Propósitos de Aprendizaje de Emprendimiento (Metodologías Ágiles):\n").bold = True
    p_ep.add_run(f"• Competencia: {ent_purp.get('competencia', 'Gestiona proyectos de emprendimiento económico o social')}\n")
    p_ep.add_run(f"• Estándar Esperado: {ent_purp.get('estandar_esperado', 'Diseña y valida modelos de negocio sostenibles')}\n")
    for cap in ent_purp.get("capacidades", []):
        p_ep.add_run(f"   - {cap}\n")

    # VII. ORGANIZACIÓN DE LAS SESIONES
    if sessions:
        dur_sem = gen.get('duracion_semanas', 9)
        tot_h = gen.get('total_horas', 72)
        add_docx_heading(doc, f"VII. ORGANIZACIÓN DE LAS {len(sessions)} SESIONES DE APRENDIZAJE ({dur_sem} SEMANAS — {tot_h} HORAS PEDAGÓGICAS)", level=1)
        
        t_ses = doc.add_table(rows=len(sessions) + 1, cols=6)
        t_ses.alignment = WD_TABLE_ALIGNMENT.CENTER
        t_ses.autofit = False
        _repeat_table_header_docx(t_ses.rows[0])

        headers_ses = ["Sem.", "Tipo / Metodología", "Título de la Sesión / Habilidad", "Propósito de Aprendizaje", "Criterios y Evidencias", "Horas"]
        widths_ses = [Inches(0.65), Inches(1.4), Inches(2.3), Inches(2.4), Inches(2.55), Inches(0.8)]

        for c_idx, h_text in enumerate(headers_ses):
            cell = t_ses.cell(0, c_idx)
            cell.width = widths_ses[c_idx]
            set_cell_background_color(cell, "1E293B")
            set_cell_margins(cell, top=80, bottom=80, left=80, right=80)
            p = cell.paragraphs[0]
            r = p.add_run(h_text)
            r.bold = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, s in enumerate(sessions):
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            tipo_label = "Técnica\n(Acción Completa GTZ)" if s.get("tipo_sesion") == "tecnica" else "Emprendimiento\n(Design Thinking / LC)"
            crit_evid = f"Criterio: {s.get('criterio_evaluacion', '')}\nEvidencia: {s.get('evidencia_aprendizaje', '')}"
            horas_txt = f"{s.get('horas_pedagogicas', 0)} h\n({s.get('duracion_minutos', 0)}m)"

            vals = [
                str(s.get("semana", "")),
                tipo_label,
                s.get("titulo", ""),
                s.get("proposito", ""),
                crit_evid,
                horas_txt
            ]

            for c_idx, val in enumerate(vals):
                cell = t_ses.cell(r_idx + 1, c_idx)
                cell.width = widths_ses[c_idx]
                set_cell_background_color(cell, bg)
                set_cell_margins(cell, top=60, bottom=60, left=70, right=70)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx in [0, 5] else WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
                r.font.size = Pt(8.0)
                if c_idx == 0:
                    r.bold = True

        doc.add_paragraph()

    # VIII. BIBLIOGRAFÍA Y REFERENCIAS
    add_docx_heading(doc, "VIII. BIBLIOGRAFÍA Y REFERENCIAS", level=1)
    for b in biblio:
        p_b = doc.add_paragraph()
        p_b.paragraph_format.space_after = Pt(2)
        r = p_b.add_run(f"• {b}")
        r.font.size = Pt(8.5)

    # IX. BLOQUE DE 3 FIRMAS INSTITUCIONALES
    add_docx_institutional_3_signatures(
        doc,
        specialty=specialty,
        teacher_name=teacher_name
    )

    # LLAMADA PEDAGÓGICA
    add_docx_callout_box(
        doc,
        text="Propuesta de Planificación Curricular en Cascada elaborada por SmartTeacher AI bajo los lineamientos del CNEB y Educación Técnica. Documento sujeto a la revisión y aprobación formal del personal jerárquico y directivo de la I.E. INEI N.º 34 de Chancay.",
        title="NOTA PEDAGÓGICA INSTITUCIONAL",
        is_warning=False
    )

    # Protección de filas de tablas (cantSplit y tblHeader)
    for tbl in doc.tables:
        for r_idx, r in enumerate(tbl.rows):
            trPr = r._tr.get_or_add_trPr()
            trPr.append(OxmlElement('w:cantSplit'))
            if r_idx == 0 and len(tbl.rows) > 1:
                trPr.append(OxmlElement('w:tblHeader'))

    out_stream = io.BytesIO()
    doc.save(out_stream)
    return out_stream.getvalue()


def generate_unit_pdf_bytes(doc_data: Dict[str, Any]) -> bytes:
    """
    Genera un archivo PDF oficial para la Unidad Didáctica Institucional utilizando ReportLab
    con orientación horizontal (Landscape A4), encabezado de doble escudo oficial CET N.º 34,
    tabla de metadatos de 10 filas oficiales, estructura matricial idéntica a la plantilla Word
    en las secciones III y IV, y total coherencia curricular sin contradicciones en horas y semanas.
    """
    data = parse_document_data(doc_data, target="teacher")
    c_json = data.get("content_json") or {}
    if isinstance(c_json, str):
        try:
            c_json = json.loads(c_json)
        except Exception:
            c_json = {}

    gen = c_json.get("datos_generales") or {}
    topic = data.get("topic") or data.get("title") or "Unidad Didáctica"
    specialty = gen.get("especialidad") or data.get("specialty") or "Educación para el Trabajo"
    clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "").strip()
    grade = int(gen.get("grado") or data.get("grade") or 5)
    grade_words = {1: "Primer", 2: "Segundo", 3: "Tercer", 4: "Cuarto", 5: "Quinto"}
    grade_str = f"{grade_words.get(grade, str(grade) + '.°')} grado"
    is_ciclo_6 = (grade in [1, 2])
    ciclo_label = "Ciclo VI" if is_ciclo_6 else "Ciclo VII"
    section_name = gen.get("seccion") or data.get("section_name") or "A"

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
    teacher_name = gen.get("docente_responsable") or data.get("teacher_name") or "Docente"
    desc_unidad = c_json.get("descripcion_unidad") or ""
    purpose = data.get("purpose") or f"Desarrollar competencias fundamentales en {topic}."

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
            jefe_name = "Mg. Luis Arturo La Rosa Gallardo"
            jefe_cargo = "JEFE DE TALLER COMPUTACIÓN E INFORMÁTICA"
            mod_default = "Aplica herramientas de productividad, almacenamiento y colaboración en la nube"
        elif "mecan" in spec_l or "torno" in spec_l:
            jefe_name = "Prof. Responsable de Taller"
            jefe_cargo = "JEFE DE TALLER MECÁNICA DE PRODUCCIÓN"
            mod_default = "Mecanizado de piezas por arranque de viruta en máquinas herramientas y soldadura"
        elif "electr" in spec_l:
            jefe_name = "Prof. Responsable de Taller"
            jefe_cargo = "JEFE DE TALLER ELECTRICIDAD Y ELECTRÓNICA"
            mod_default = "Instalaciones eléctricas residenciales, industriales y control electrónico de potencia"
        else:
            jefe_name = f"Jefe de Taller de {clean_spec}"
            jefe_cargo = f"JEFE DE TALLER {clean_spec.upper()[:25]}"
            mod_default = f"Módulo Formativo de {clean_spec}: {topic}"
        subdirector_cargo = "SUB-DIRECTOR ÁREA TÉCNICA"
        subtitle_header = "PLANIFICACIÓN CURRICULAR EN CASCADA CNEB / EPT 2026"
    else:
        jefe_name = firmas.get("jefe_taller", {}).get("nombre") or f"Coordinador(a) Pedagógico(a) del Área de {clean_spec}"
        jefe_cargo = firmas.get("jefe_taller", {}).get("cargo") or f"COORDINACIÓN PEDAGÓGICA DE {clean_spec.upper()}"
        subdirector_cargo = "SUB-DIRECTOR"
        mod_default = gen.get("modulo_formativo") or f"Desarrollo de competencias curriculares en {clean_spec}: {topic}"
        subtitle_header = "PLANIFICACIÓN CURRICULAR CNEB 2026 — EDUCACIÓN SECUNDARIA"

    mod_val = gen.get("modulo_formativo") or mod_default
    f_inicio_str = gen.get("fecha_inicio_corta") or "16-03-2026"
    f_fin_str = gen.get("fecha_fin_corta") or "22-05-2026"
    dur_display = gen.get("duracion_texto") or f"Inicio: {f_inicio_str}     Fin: {f_fin_str}"
    horas_display = gen.get("horas_texto") or f"{total_hours} horas pedagógicas ({duration_weeks} semanas x {weekly_hours} horas)"

    buf = io.BytesIO()
    pdf_doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=12 * mm,
        bottomMargin=15 * mm
    )

    styles = build_pdf_styles()
    style_h_caption = ParagraphStyle('UnitHCaption', parent=styles['Normal'], alignment=TA_CENTER, fontSize=6.5, leading=8, fontName='Helvetica-Bold', textColor=colors.HexColor("#8B0000"))
    style_h_center = ParagraphStyle('UnitHCenter', parent=styles['Normal'], alignment=TA_CENTER, leading=11, textColor=colors.HexColor("#0F172A"))
    unit_meta_label = ParagraphStyle('UnitMetaLabel', parent=styles['Normal'], fontSize=7.5, leading=9.5, fontName='Helvetica-Bold', textColor=colors.HexColor("#1E293B"))
    unit_meta_val = ParagraphStyle('UnitMetaVal', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor("#0F172A"))
    unit_th_style = ParagraphStyle('UnitTHStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)
    unit_tb_style = ParagraphStyle('UnitTBStyle', parent=styles['Normal'], fontSize=7.5, leading=9.5)
    unit_tb_center = ParagraphStyle('UnitTBCStyle', parent=unit_tb_style, alignment=TA_CENTER)
    story = []

    # 1. Header institucional con 2 logos (Fiel al Word oficial)
    logo_gear_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "logo_inei34.png"))
    logo_bee_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "insignia.png"))
    if not os.path.exists(logo_gear_path):
        logo_gear_path = os.path.abspath(os.path.join("app", "static", "imagen", "logo_inei34.png"))
    if not os.path.exists(logo_bee_path):
        logo_bee_path = os.path.abspath(os.path.join("app", "static", "imagen", "insignia.png"))

    from reportlab.platypus import Image as ReportLabImage
    has_logos = os.path.exists(logo_gear_path) and os.path.exists(logo_bee_path)

    if has_logos:
        img_gear = ReportLabImage(logo_gear_path, width=22 * mm, height=22 * mm)
        img_bee = ReportLabImage(logo_bee_path, width=22 * mm, height=22 * mm)
        cell_l = [img_gear, Spacer(1, 1*mm), Paragraph("R.M. Nº 2296-57", style_h_caption)]
        cell_r = [img_bee, Spacer(1, 1*mm), Paragraph("CHANCAY", style_h_caption)]
    else:
        cell_l = Paragraph("<b>CET N.º 34</b>", style_h_caption)
        cell_r = Paragraph("<b>CHANCAY</b>", style_h_caption)

    cell_c = Paragraph(f"""
    <font size="7.5" color="#475569">"Decenio de la Igualdad de oportunidades para mujeres y hombres"<br/>
    "Año de la Esperanza y el Fortalecimiento de la Democracia"</font><br/>
    <font size="9.5" color="#8B0000"><b>INSTITUCIÓN EDUCATIVA PÚBLICA TÉCNICA Nº 34 (CET 34)</b></font><br/>
    <font size="6.5" color="#475569">"Honradez - Disciplina - Trabajo" • R.M. Nº 2296-57 • Cód. Modular: 0245621-0<br/>
    GOBIERNO REGIONAL DE LIMA • UGEL Nº 10 - HUARAL • CHANCAY</font><br/>
    <font size="10" color="#0F172A"><b>UNIDAD DIDÁCTICA N° {str(unit_number).zfill(2)}: {xml_escape(topic.upper())}</b></font><br/>
    <font size="7.5" color="#8B0000"><b>{subtitle_header}</b></font>
    """, style_h_center)

    head_tbl = Table([[cell_l, cell_c, cell_r]], colWidths=[24 * mm, 213 * mm, 24 * mm])
    head_tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor("#8B0000")),
    ]))
    story.append(head_tbl)
    story.append(Spacer(1, 2.5 * mm))

    # 2. I. DATOS GENERALES (10 filas exactas del formato institucional)
    area_display = gen.get("area_curricular") or ("Educación para el Trabajo" if is_ept else clean_spec)
    prog_display = gen.get("especialidad") or (clean_spec if is_ept else f"Educación Secundaria - {clean_spec}")

    story.append(Paragraph("<b>I. DATOS GENERALES:</b>", styles['SectionHeading1']))
    meta_rows = [
        [Paragraph("Institución educativa", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph("CET 34 (I.E. INEI N.º 34)", unit_meta_val)],
        [Paragraph("Área curricular", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(area_display), unit_meta_val)],
        [Paragraph("Programa formativo", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(prog_display), unit_meta_val)],
        [Paragraph("Módulo formativo", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(mod_val), unit_meta_val)],
        [Paragraph("Grado y sección", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(f'{grade_str}: "{xml_escape(str(section_name))}"', unit_meta_val)],
        [Paragraph("Duración", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(dur_display), unit_meta_val)],
        [Paragraph("Horas", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(horas_display), unit_meta_val)],
        [Paragraph("Director", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(gen.get('director', 'Tomas Jurado Zevallos')), unit_meta_val)],
        [Paragraph("Sub director", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(gen.get('subdirector', 'Mg. Javier Eulogio Rosas Maguiña')), unit_meta_val)],
        [Paragraph("Docente responsable", unit_meta_label), Paragraph(":", unit_meta_label), Paragraph(xml_escape(teacher_name), unit_meta_val)],
    ]
    t_gen_pdf = Table(meta_rows, colWidths=[48 * mm, 5 * mm, 208 * mm])
    t_gen_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(f"#{COLOR_BG_LIGHT_HEX}")),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_gen_pdf)
    story.append(Spacer(1, 2.5 * mm))

    # II. DESCRIPCIÓN DE LOS APRENDIZAJES
    story.append(Paragraph("<b>II. DESCRIPCIÓN DE LOS APRENDIZAJES A DESARROLLAR EN LA UNIDAD DIDÁCTICA</b>", styles['SectionHeading1']))
    story.append(Paragraph(sanitize_text_for_xml(desc_unidad), styles['BodyJustified']))
    story.append(Spacer(1, 2.5 * mm))

    # III. MATRIZ DE DESEMPEÑOS EJE 1 (Fiel estructura matricial: 2 filas x 3 columnas idéntica a Word)
    if tech_matrix:
        sec3_title = (
            "<b>III. RELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: HABILIDADES TÉCNICAS</b>"
            if is_ept else
            f"<b>III. RELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: {xml_escape(eje_1_name.upper())}</b>"
        )
        col0_label = f"<b>Desempeños del grado - Matriz curricular: {xml_escape(eje_1_name)}</b>"
        col1_label = f"<b>Estándar de aprendizaje ({ciclo_label})</b>"
        col2_label = "<b>Estructura interna del área</b>" if not is_ept else "<b>Estructura interna del módulo formativo</b>"

        desemp_lines_1 = [
            f"<b>{i}.</b> {xml_escape(tm.get('desempenos') or tm.get('habilidad_o_desempeno') or tm.get('habilidad_tecnica', ''))}"
            for i, tm in enumerate(tech_matrix, 1)
        ]
        desemp_text_1 = "<br/><br/>".join(desemp_lines_1)
        est_text_1 = f"<i>{xml_escape(tech_purp.get('estandar_esperado') or tech_matrix[0].get('estandar_modulo') or '')}</i>"
        mod_text_1 = xml_escape(mod_val)

        story.append(Paragraph(sec3_title, styles['SectionHeading1']))
        t_data_3 = [
            [Paragraph(col0_label, unit_th_style), Paragraph(col1_label, unit_th_style), Paragraph(col2_label, unit_th_style)],
            [Paragraph(desemp_text_1, unit_tb_style), Paragraph(est_text_1, unit_tb_style), Paragraph(mod_text_1, unit_tb_style)]
        ]
        t_tm_pdf = Table(t_data_3, colWidths=[105 * mm, 95 * mm, 61 * mm])
        t_tm_pdf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_tm_pdf)
        story.append(Spacer(1, 2.5 * mm))

    # IV. MATRIZ DE DESEMPEÑOS EJE 2 (Fiel estructura matricial: 2 filas x 3 columnas idéntica a Word)
    if ent_matrix:
        sec4_title = (
            "<b>IV. RELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: HABILIDADES DE GESTIÓN DE PROYECTOS DE EMPRENDIMIENTO</b>"
            if is_ept else
            f"<b>IV. RELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: {xml_escape(eje_2_name.upper())}</b>"
        )
        col0_label_4 = f"<b>Desempeños del grado - Matriz curricular articuladora: {xml_escape(eje_2_name)}</b>"
        col1_label_4 = f"<b>Estándar de aprendizaje ({ciclo_label})</b>"
        col2_label_4 = "<b>Estructura interna del área</b>" if not is_ept else "<b>Estructura interna del módulo formativo</b>"

        desemp_lines_2 = [
            f"<b>{i}.</b> {xml_escape(em.get('desempenos') or em.get('habilidad_o_desempeno') or em.get('habilidad_emprendimiento', ''))}"
            for i, em in enumerate(ent_matrix, 1)
        ]
        desemp_text_2 = "<br/><br/>".join(desemp_lines_2)
        est_text_2 = f"<i>{xml_escape(ent_purp.get('estandar_esperado') or ent_matrix[0].get('estandar_ciclo') or '')}</i>"
        est_int_label = "Implementamos, comunicamos y mejoramos nuestro emprendimiento (Design Thinking / Lean Canvas)" if is_ept else f"Articulación curricular y competencias de {clean_spec}"

        story.append(Paragraph(sec4_title, styles['SectionHeading1']))
        t_data_4 = [
            [Paragraph(col0_label_4, unit_th_style), Paragraph(col1_label_4, unit_th_style), Paragraph(col2_label_4, unit_th_style)],
            [Paragraph(desemp_text_2, unit_tb_style), Paragraph(est_text_2, unit_tb_style), Paragraph(est_int_label, unit_tb_style)]
        ]
        t_em_pdf = Table(t_data_4, colWidths=[105 * mm, 95 * mm, 61 * mm])
        t_em_pdf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_em_pdf)
        story.append(Spacer(1, 2.5 * mm))

    # V. ORGANIZACIÓN DE PROPÓSITOS POR SEMANA EJE 1
    if tech_matrix:
        sec5_title = (
            "<b>V. PROPÓSITO DE LA UNIDAD DIDÁCTICA: HABILIDADES TÉCNICAS POR SEMANA</b>"
            if is_ept else
            f"<b>V. ORGANIZACIÓN DE LOS PROPÓSITOS DE APRENDIZAJE: {xml_escape(eje_1_name.upper())}</b>"
        )
        story.append(Paragraph(sec5_title, styles['SectionHeading1']))
        pt_data = [
            [Paragraph(f"<b>PROPÓSITO DE UNIDAD DIDÁCTICA {unit_number}: {xml_escape(purpose)}</b>", unit_th_style), Paragraph("", unit_th_style)],
            [Paragraph("<b>SEMANAS</b>", unit_th_style), Paragraph("<b>PROPÓSITO DE LA SESIÓN DE APRENDIZAJE</b>", unit_th_style)]
        ]
        for w_idx, tm in enumerate(tech_matrix, 1):
            h_tit = tm.get("habilidad_o_desempeno") or tm.get("habilidad_tecnica", "")
            s_purp = tm.get("desempenos") or f"Desarrollar habilidades y competencias en {h_tit}."
            pt_data.append([
                Paragraph(f"<b>Semana {w_idx}</b><br/>{xml_escape(h_tit)}", unit_tb_center),
                Paragraph(xml_escape(s_purp), unit_tb_style)
            ])
        t_pt_pdf = Table(pt_data, colWidths=[65 * mm, 196 * mm], repeatRows=2)
        t_pt_pdf.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),
            ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_pt_pdf)
        story.append(Spacer(1, 2.5 * mm))

    # VI. ORGANIZACIÓN DE PROPÓSITOS POR SEMANA EJE 2
    if ent_matrix:
        sec6_title = (
            "<b>VI. PROPÓSITO DE LA UNIDAD DE EMPRENDIMIENTO / GESTIÓN POR SEMANA</b>"
            if is_ept else
            f"<b>VI. ORGANIZACIÓN DE LOS PROPÓSITOS DE APRENDIZAJE: {xml_escape(eje_2_name.upper())}</b>"
        )
        story.append(Paragraph(sec6_title, styles['SectionHeading1']))
        pe_data = [
            [Paragraph(f"<b>PROPÓSITO DE UNIDAD DE APRENDIZAJE {unit_number}: {xml_escape(purpose)}</b>", unit_th_style), Paragraph("", unit_th_style)],
            [Paragraph("<b>SEMANAS</b>", unit_th_style), Paragraph("<b>PROPÓSITO DE LA SESIÓN DE APRENDIZAJE</b>", unit_th_style)]
        ]
        for w_idx, em in enumerate(ent_matrix, 1):
            h_tit = em.get("habilidad_o_desempeno") or em.get("habilidad_emprendimiento", "")
            s_purp = em.get("desempenos") or f"Aplicar competencias en {h_tit}."
            pe_data.append([
                Paragraph(f"<b>Semana {w_idx}</b><br/>{xml_escape(h_tit)}", unit_tb_center),
                Paragraph(xml_escape(s_purp), unit_tb_style)
            ])
        t_pe_pdf = Table(pe_data, colWidths=[65 * mm, 196 * mm], repeatRows=2)
        t_pe_pdf.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),
            ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_pe_pdf)
        story.append(Spacer(1, 2.5 * mm))

    # VII. ORGANIZACIÓN DE LAS SESIONES (Fiel a la tabla oficial: 6 columnas)
    if sessions:
        story.append(Paragraph(f"<b>VII. ORGANIZACIÓN DE LAS {len(sessions)} SESIONES DE APRENDIZAJE ({duration_weeks} SEMANAS — {total_hours} HORAS)</b>", styles['SectionHeading1']))
        s_data = [[
            Paragraph("<b>HABILIDAD / TÍTULO DE SESIÓN</b>", unit_th_style),
            Paragraph("<b>PROPÓSITO DE LA SESIÓN DE APRENDIZAJE</b>", unit_th_style),
            Paragraph("<b>CRITERIO EVALUACIÓN</b>", unit_th_style),
            Paragraph("<b>EVIDENCIA DE APRENDIZAJE</b>", unit_th_style),
            Paragraph("<b>N° DE SEMANA</b>", unit_th_style),
            Paragraph("<b>N° DE HORAS</b>", unit_th_style)
        ]]
        for s in sessions:
            if is_ept:
                tipo_prefix = "Técnica" if s.get("tipo_sesion") == "tecnica" else "Gestión de proyectos de emprendimiento"
            else:
                tipo_prefix = s.get("tipo_sesion") or clean_spec

            tit_cell = f"<b>{xml_escape(tipo_prefix)}</b><br/>{xml_escape(s.get('titulo', ''))}"
            prop_cell = xml_escape(s.get('proposito', ''))
            crit_cell = xml_escape(s.get('criterio_evaluacion', ''))
            evid_cell = xml_escape(s.get('evidencia_aprendizaje', ''))
            sem_cell = str(s.get('semana', ''))
            horas_cell = str(s.get('horas_pedagogicas', 0))

            s_data.append([
                Paragraph(tit_cell, unit_tb_style),
                Paragraph(prop_cell, unit_tb_style),
                Paragraph(crit_cell, unit_tb_style),
                Paragraph(evid_cell, unit_tb_style),
                Paragraph(sem_cell, unit_tb_center),
                Paragraph(horas_cell, unit_tb_center)
            ])
        t_ses_pdf = Table(s_data, colWidths=[55 * mm, 65 * mm, 60 * mm, 55 * mm, 13 * mm, 13 * mm], repeatRows=1)
        t_ses_pdf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_ses_pdf)
        story.append(Spacer(1, 2.5 * mm))

    # VIII. BIBLIOGRAFÍA
    story.append(Paragraph("<b>VIII. BIBLIOGRAFÍA Y REFERENCIAS</b>", styles['SectionHeading1']))
    for b in biblio:
        story.append(Paragraph(f"• {xml_escape(b)}", styles['BodyJustified']))
    story.append(Spacer(1, 3 * mm))

    # IX. FIRMAS INSTITUCIONALES (3 FIRMAS)
    if is_ept:
        doc_cargo = "Docente de Especialidad EPT"
        jefe_rol = "JEFE DE TALLER"
        sub_rol = "SUB-DIRECTOR ÁREA TÉCNICA"
    else:
        doc_cargo = f"Área Curricular de {clean_spec}"
        jefe_rol = "COORDINACIÓN PEDAGÓGICA"
        sub_rol = "SUB-DIRECTOR"

    p1 = Paragraph(
        f"____________________________<br/><b>DOCENTE RESPONSABLE</b><br/><font size='7.5'>{xml_escape(teacher_name)}<br/>{xml_escape(doc_cargo)}</font>",
        ParagraphStyle('SigU1', parent=styles['Normal'], alignment=TA_CENTER)
    )
    p2 = Paragraph(
        f"____________________________<br/><b>{jefe_rol}</b><br/><font size='7.5'>{xml_escape(jefe_name)}<br/>{xml_escape(jefe_cargo)}</font>",
        ParagraphStyle('SigU2', parent=styles['Normal'], alignment=TA_CENTER)
    )
    p3 = Paragraph(
        f"____________________________<br/><b>{sub_rol}</b><br/><font size='7.5'>Mg. Javier Eulogio Rosas Maguiña<br/>I.E. CET N° 34 - Chancay</font>",
        ParagraphStyle('SigU3', parent=styles['Normal'], alignment=TA_CENTER)
    )
    t_sig = Table([[p1, p2, p3]], colWidths=[87 * mm, 87 * mm, 87 * mm])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_sig)

    pdf_doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()



def add_formatted_runs_to_paragraph(p, text: str, default_font_size: float = 10.0, default_color: Optional[RGBColor] = None):
    """
    Parsea markdown en línea (**negrita**, *cursiva*, ***negrita cursiva***, `código`, placeholders)
    y añade runs estilizados en Word sin dejar símbolos markdown crudos.
    """
    if not text:
        return
    tokens = re.split(r'(\*\*\*[^*]+?\*\*\*|\*\*[^*]+?\*\*|\*[^*]+?\*|`[^`]+?`|\[📷[^\]]+?\]|\[Sugerencia[^\]]+?\])', text)
    for tok in tokens:
        if not tok:
            continue
        run = p.add_run()
        run.font.name = "Calibri"
        run.font.size = Pt(default_font_size)
        if default_color:
            run.font.color.rgb = default_color
        else:
            run.font.color.rgb = RGBColor(30, 41, 59)

        if tok.startswith('***') and tok.endswith('***') and len(tok) >= 6:
            run.text = tok[3:-3]
            run.bold = True
            run.italic = True
        elif tok.startswith('**') and tok.endswith('**') and len(tok) >= 4:
            run.text = tok[2:-2]
            run.bold = True
        elif tok.startswith('*') and tok.endswith('*') and len(tok) >= 2:
            run.text = tok[1:-1]
            run.italic = True
        elif tok.startswith('`') and tok.endswith('`') and len(tok) >= 2:
            run.text = tok[1:-1]
            run.font.name = "Consolas"
            run.font.size = Pt(default_font_size - 0.5)
            run.font.color.rgb = RGBColor(180, 83, 9)
        elif (tok.startswith('[📷') or tok.startswith('[Sugerencia')) and tok.endswith(']'):
            run.text = tok
            run.bold = True
            run.font.color.rgb = RGBColor(14, 116, 144)
        else:
            run.text = tok


def render_markdown_table_to_docx(doc: Document, table_lines: List[str], max_width_in: float = 6.56):
    """Convierte líneas de tabla markdown en una tabla real de Word ajustada al ancho útil de la página A4."""
    rows_data = []
    for line in table_lines:
        line_clean = line.strip().strip('|')
        if re.match(r'^\s*[-:\s|]+\s*$', line):
            continue
        cells = [c.strip() for c in line_clean.split('|')]
        rows_data.append(cells)

    if not rows_data:
        return

    num_cols = max(len(r) for r in rows_data)
    for r in rows_data:
        while len(r) < num_cols:
            r.append('')

    # Cálculo proporcional de anchos de columna según el contenido
    col_max_lens = [0] * num_cols
    for r in rows_data:
        for c_idx, val in enumerate(r):
            col_max_lens[c_idx] = max(col_max_lens[c_idx], len(val))

    total_len = sum(col_max_lens) or 1
    col_props = []
    for cl in col_max_lens:
        prop = max(0.12, min(0.60, cl / total_len))
        col_props.append(prop)
    
    sum_props = sum(col_props)
    col_widths = [Inches((p / sum_props) * max_width_in) for p in col_props]

    tbl = doc.add_table(rows=len(rows_data), cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    tblPr = tbl._tbl.tblPr
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'), str(int(max_width_in * 1440)))
    tblW.set(qn('w:type'), 'dxa')
    tblPr.append(tblW)

    tblGrid = OxmlElement('w:tblGrid')
    for w in col_widths:
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), str(int(w.inches * 1440)))
        tblGrid.append(gridCol)
    tbl._tbl.append(tblGrid)

    for r_idx, r in enumerate(rows_data):
        is_header = (r_idx == 0)
        row_obj = tbl.rows[r_idx]

        trPr = row_obj._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))
        if is_header:
            trPr.append(OxmlElement('w:tblHeader'))

        for c_idx, val in enumerate(r):
            cell = tbl.cell(r_idx, c_idx)
            cell.width = col_widths[c_idx]
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)

            if is_header:
                set_cell_background_color(cell, COLOR_PRIMARY_HEX)
            elif r_idx % 2 == 1:
                set_cell_background_color(cell, "F8FAFC")

            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.1

            if is_header:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                add_formatted_runs_to_paragraph(p, val, default_font_size=9.5, default_color=RGBColor(255, 255, 255))
                for run in p.runs:
                    run.bold = True
            else:
                add_formatted_runs_to_paragraph(p, val, default_font_size=9)

    sp_p = doc.add_paragraph()
    sp_p.paragraph_format.space_before = Pt(0)
    sp_p.paragraph_format.space_after = Pt(3)
    sp_p.paragraph_format.line_spacing = Pt(2)
    sp_p.add_run("").font.size = Pt(2)


def render_markdown_to_docx(doc: Document, markdown_text: str):
    """
    Interpreta y renderiza un documento Markdown completo en elementos nativos de Microsoft Word:
    - Encabezados estructurados (Heading 1, 2, 3) con tipografía institucional INEI 34 y keep_with_next.
    - Listas con viñetas y numeradas con sangrías colgantes uniformes y soporte multilínea.
    - Tablas de datos autoajustadas al ancho útil A4 (6.56 pulgadas) con anchos proporcionales.
    - Cuadros destacados (Callouts) para seguridad, avisos pedagógicos o solucionarios.
    - Líneas de respuesta pautadas para estudiantes.
    - Párrafos justificados con interlineado profesional (1.15) y espaciado consistente.
    """
    if not markdown_text or not markdown_text.strip():
        return

    clean_md = markdown_text.replace('\r\n', '\n').strip()
    lines = clean_md.split('\n')

    # Omitir títulos repetitivos y membretes al inicio si ya están impresos en el encabezado
    start_idx = 0
    for idx_l, l in enumerate(lines[:6]):
        strp = l.strip().strip('*# ').lower()
        if not strp:
            start_idx = idx_l + 1
            continue
        if any(strp.startswith(k) for k in [
            "institución educativa", "i.e. emblemática", "república del perú",
            "ficha de trabajo", "ficha guía", "guía de clase",
            "evaluación escrita", "cuestionario técnico", "solucionario"
        ]):
            start_idx = idx_l + 1
        elif any(strp.startswith(k) for k in ["área:", "grado y sección:", "duración:", "docente:"]):
            start_idx = idx_l + 1
        else:
            break

    lines = lines[start_idx:]
    i = 0
    table_lines: List[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detección de filas de tabla Markdown
        if stripped.startswith('|') and stripped.endswith('|'):
            table_lines.append(stripped)
            i += 1
            continue
        elif table_lines:
            render_markdown_table_to_docx(doc, table_lines)
            table_lines = []

        if not stripped:
            i += 1
            continue

        # Regla horizontal (--- o ***)
        if re.match(r'^(?:---|\*\*\*|___)\s*$', stripped):
            p_hr = doc.add_paragraph()
            p_hr.paragraph_format.space_before = Pt(4)
            p_hr.paragraph_format.space_after = Pt(4)
            pBrd = OxmlElement('w:pBrd')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '4')
            bottom.set(qn('w:color'), COLOR_BORDER_HEX)
            pBrd.append(bottom)
            p_hr._p.get_or_add_pPr().append(pBrd)
            i += 1
            continue

        # Títulos Markdown oficiales (#, ##, ###)
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if heading_match:
            hashes, h_text = heading_match.groups()
            lvl = len(hashes)
            p_h = doc.add_paragraph()
            p_h.paragraph_format.keep_with_next = True

            if lvl == 1:
                p_h.paragraph_format.space_before = Pt(11)
                p_h.paragraph_format.space_after = Pt(3)
                add_formatted_runs_to_paragraph(p_h, h_text, default_font_size=11.5, default_color=RGBColor(139, 0, 0))
                for run in p_h.runs:
                    run.bold = True
                pBrd = OxmlElement('w:pBrd')
                bottom = OxmlElement('w:bottom')
                bottom.set(qn('w:val'), 'single')
                bottom.set(qn('w:sz'), '6')
                bottom.set(qn('w:color'), COLOR_BORDER_HEX)
                pBrd.append(bottom)
                p_h._p.get_or_add_pPr().append(pBrd)
            elif lvl == 2:
                p_h.paragraph_format.space_before = Pt(9)
                p_h.paragraph_format.space_after = Pt(2.5)
                add_formatted_runs_to_paragraph(p_h, h_text, default_font_size=10.5, default_color=RGBColor(30, 41, 59))
                for run in p_h.runs:
                    run.bold = True
            else:
                p_h.paragraph_format.space_before = Pt(7)
                p_h.paragraph_format.space_after = Pt(2)
                add_formatted_runs_to_paragraph(p_h, h_text, default_font_size=10, default_color=RGBColor(51, 65, 85))
                for run in p_h.runs:
                    run.bold = True

            i += 1
            continue

        # Subtítulo en negrita independiente (ej: **1. Título y datos**, **Propósito de Aprendizaje:**, etc.)
        bold_heading_match = re.match(r'^\*\*(.+?)\*\*:?\s*$', stripped)
        if bold_heading_match:
            raw_h_text = bold_heading_match.group(1).strip()
            if len(raw_h_text) < 90 and not raw_h_text.lower().startswith("nota"):
                p_h = doc.add_paragraph()
                p_h.paragraph_format.keep_with_next = True
                
                is_main_sec = bool(re.match(r'^(?:[0-9]{1,2}\.|\b[IVXLCDM]+\.)\s+', raw_h_text))
                if is_main_sec:
                    p_h.paragraph_format.space_before = Pt(11)
                    p_h.paragraph_format.space_after = Pt(3)
                    add_formatted_runs_to_paragraph(p_h, raw_h_text, default_font_size=11.5, default_color=RGBColor(139, 0, 0))
                    for run in p_h.runs:
                        run.bold = True
                    pBrd = OxmlElement('w:pBrd')
                    bottom = OxmlElement('w:bottom')
                    bottom.set(qn('w:val'), 'single')
                    bottom.set(qn('w:sz'), '6')
                    bottom.set(qn('w:color'), COLOR_BORDER_HEX)
                    pBrd.append(bottom)
                    p_h._p.get_or_add_pPr().append(pBrd)
                else:
                    p_h.paragraph_format.space_before = Pt(9)
                    p_h.paragraph_format.space_after = Pt(2.5)
                    add_formatted_runs_to_paragraph(p_h, raw_h_text, default_font_size=10.5, default_color=RGBColor(30, 41, 59))
                    for run in p_h.runs:
                        run.bold = True

                i += 1
                continue

        # Apartado numerado principal sin asteriscos: ej "1. Título y datos del estudiante"
        main_sec_plain_match = re.match(r'^([0-9]{1,2}\.|\b[IVXLCDM]+\.)\s+([A-ZÁÉÍÓÚÑ].+?):?\s*$', stripped)
        if main_sec_plain_match and len(stripped) < 75 and not any(k in stripped.lower() for k in ["crear", "hacer", "seleccionar", "abrir", "guardar"]):
            num_lbl, title_lbl = main_sec_plain_match.groups()
            p_h = doc.add_paragraph()
            p_h.paragraph_format.keep_with_next = True
            p_h.paragraph_format.space_before = Pt(11)
            p_h.paragraph_format.space_after = Pt(3)
            add_formatted_runs_to_paragraph(p_h, f"{num_lbl} {title_lbl}", default_font_size=11.5, default_color=RGBColor(139, 0, 0))
            for run in p_h.runs:
                run.bold = True
            pBrd = OxmlElement('w:pBrd')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '6')
            bottom.set(qn('w:color'), COLOR_BORDER_HEX)
            pBrd.append(bottom)
            p_h._p.get_or_add_pPr().append(pBrd)
            i += 1
            continue

        # Citas y Callouts (> ...)
        if stripped.startswith('>'):
            callout_text = stripped.lstrip('> ').strip()
            while i + 1 < len(lines) and lines[i+1].strip().startswith('>'):
                i += 1
                callout_text += " " + lines[i].strip().lstrip('> ').strip()

            p_call = doc.add_paragraph()
            p_call.paragraph_format.left_indent = Inches(0.25)
            p_call.paragraph_format.right_indent = Inches(0.25)
            p_call.paragraph_format.space_before = Pt(4)
            p_call.paragraph_format.space_after = Pt(4)
            p_call.paragraph_format.line_spacing = 1.15
            p_call.paragraph_format.keep_with_next = True

            is_warn = any(k in callout_text.lower() for k in ["seguridad", "advertencia", "peligro", "importante", "atención", "confidencial"])
            pBrd = OxmlElement('w:pBrd')
            leftBrd = OxmlElement('w:left')
            leftBrd.set(qn('w:val'), 'single')
            leftBrd.set(qn('w:sz'), '24')
            leftBrd.set(qn('w:color'), 'DC2626' if is_warn else '8B0000')
            pBrd.append(leftBrd)
            p_call._p.get_or_add_pPr().append(pBrd)

            add_formatted_runs_to_paragraph(p_call, callout_text, default_font_size=9.5)
            i += 1
            continue

        # Placeholder gráfico o sugerencia visual: [📷 Sugerencia visual: ...]
        if (stripped.startswith('[📷') or stripped.startswith('[Sugerencia')) and stripped.endswith(']'):
            p_v = doc.add_paragraph()
            p_v.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_v.paragraph_format.space_before = Pt(4)
            p_v.paragraph_format.space_after = Pt(4)
            p_v.paragraph_format.keep_with_next = True
            r_v = p_v.add_run(stripped)
            r_v.font.name = "Calibri"
            r_v.font.size = Pt(9)
            r_v.bold = True
            r_v.font.color.rgb = RGBColor(14, 116, 144)
            i += 1
            continue

        # Expandir tabulaciones para listas multinivel
        expanded_line = line.expandtabs(4)

        # Viñetas (*, -, +, •)
        bullet_match = re.match(r'^(\s*)(?:[\*\-\+\•])\s+(.+)$', expanded_line)
        if bullet_match:
            indent_str, b_text = bullet_match.groups()
            indent_lvl = min(len(indent_str) // 2, 4)
            p_b = doc.add_paragraph()
            p_b.paragraph_format.left_indent = Inches(0.28 + indent_lvl * 0.20)
            p_b.paragraph_format.first_line_indent = Inches(-0.16)
            p_b.paragraph_format.space_before = Pt(1)
            p_b.paragraph_format.space_after = Pt(2.5)
            p_b.paragraph_format.line_spacing = 1.15

            r_bullet = p_b.add_run("• ")
            r_bullet.bold = True
            r_bullet.font.color.rgb = RGBColor(139, 0, 0)
            add_formatted_runs_to_paragraph(p_b, b_text, default_font_size=10)
            i += 1
            continue

        # Listas numeradas (1., 2., 1), a), b))
        num_match = re.match(r'^(\s*)(\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+(.+)$', expanded_line)
        if num_match:
            indent_str, num_prefix, num_text = num_match.groups()
            indent_lvl = min(len(indent_str) // 2, 4)
            p_n = doc.add_paragraph()
            p_n.paragraph_format.left_indent = Inches(0.32 + indent_lvl * 0.20)
            p_n.paragraph_format.first_line_indent = Inches(-0.20)
            p_n.paragraph_format.space_before = Pt(1.5)
            p_n.paragraph_format.space_after = Pt(2.5)
            p_n.paragraph_format.line_spacing = 1.15

            r_num = p_n.add_run(f"{num_prefix} ")
            r_num.bold = True
            r_num.font.name = "Calibri"
            r_num.font.color.rgb = RGBColor(139, 0, 0)
            add_formatted_runs_to_paragraph(p_n, num_text, default_font_size=10)
            i += 1
            continue

        # Líneas pautadas para respuestas de desarrollo
        if re.search(r'_{5,}', stripped):
            p_rule = doc.add_paragraph()
            p_rule.paragraph_format.space_before = Pt(2)
            p_rule.paragraph_format.space_after = Pt(4)
            p_rule.paragraph_format.left_indent = Inches(0.2)
            r_rule = p_rule.add_run(stripped)
            r_rule.font.name = "Calibri"
            r_rule.font.size = Pt(9.5)
            r_rule.font.color.rgb = RGBColor(148, 163, 184)
            i += 1
            continue

        # Párrafo estándar
        p_norm = doc.add_paragraph()
        p_norm.paragraph_format.space_before = Pt(0)
        p_norm.paragraph_format.space_after = Pt(4)
        p_norm.paragraph_format.line_spacing = 1.15
        p_norm.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_formatted_runs_to_paragraph(p_norm, stripped, default_font_size=10)
        i += 1

    if table_lines:
        render_markdown_table_to_docx(doc, table_lines)


def add_docx_worksheet_activities_table(doc: Document, activities: Optional[List[Dict[str, str]]] = None, topic: str = "la actividad"):
    """
    Inserta la tabla auténtica «Ficha de Aprendizaje» con EXACTAMENTE DOS COLUMNAS:
    Columna 1: Actividad
    Columna 2: Descripción
    """
    if not activities or not isinstance(activities, list) or len(activities) == 0:
        activities = [
            {
                "actividad": "Actividad 1:\nExploración y Diagnóstico",
                "descripcion": f"Identifica los conceptos clave y condiciones iniciales para {topic}, reconociendo las herramientas y parámetros de operación requeridos."
            },
            {
                "actividad": "Actividad 2:\nProcedimiento Guiado",
                "descripcion": f"Aplica la secuencia técnica modelada paso a paso para {topic}, respetando tolerancias, normas técnicas y medidas de seguridad."
            },
            {
                "actividad": "Actividad 3:\nEjercicio Práctico Aplicado",
                "descripcion": f"Desarrolla el ejercicio práctico propuesto en el taller o aula digital, registrando mediciones, capturas o avances técnicos en la guía de trabajo."
            },
            {
                "actividad": "Actividad 4:\nReto Autónomo y Resolución",
                "descripcion": f"Resuelve el reto técnico planteado aplicando estrategias de optimización, control de calidad y prevención de fallas operacionales."
            },
            {
                "actividad": "Actividad 5:\nMetacognición y Transferencia",
                "descripcion": f"Evalúa los resultados obtenidos en {topic}, describe los aprendizajes adquiridos y formula propuestas de mejora para su desempeño."
            }
        ]

    tbl = doc.add_table(rows=len(activities) + 1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    w_col0 = Inches(1.90)
    w_col1 = Inches(4.87)
    widths = [w_col0, w_col1]

    # Header Row
    headers = ["Actividad", "Descripción"]
    hdr_row = tbl.rows[0]
    trPr_hdr = hdr_row._tr.get_or_add_trPr()
    trPr_hdr.append(OxmlElement('w:tblHeader'))
    trPr_hdr.append(OxmlElement('w:cantSplit'))

    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.width = widths[c_idx]
        set_cell_background_color(cell, "1E293B")
        set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.bold = True
        r.font.name = "Arial"
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows
    for r_idx, act in enumerate(activities, start=1):
        row = tbl.rows[r_idx]
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))

        act_title = act.get("actividad") or act.get("titulo") or f"Actividad {r_idx}"
        act_desc = act.get("descripcion") or act.get("detalle") or act.get("texto") or ""

        # Col 0: Actividad
        c0 = row.cells[0]
        c0.width = w_col0
        set_cell_background_color(c0, "F8FAFC")
        set_cell_margins(c0, top=55, bottom=55, left=80, right=80)
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p0.paragraph_format.space_before = Pt(0)
        p0.paragraph_format.space_after = Pt(0)
        p0.paragraph_format.line_spacing = 1.15
        r0 = p0.add_run(act_title)
        r0.bold = True
        r0.font.name = "Calibri"
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(30, 41, 59)

        # Col 1: Descripción
        c1 = row.cells[1]
        c1.width = w_col1
        if r_idx % 2 == 0:
            set_cell_background_color(c1, "F8FAFC")
        set_cell_margins(c1, top=55, bottom=55, left=80, right=80)
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p1.paragraph_format.space_before = Pt(0)
        p1.paragraph_format.space_after = Pt(0)
        p1.paragraph_format.line_spacing = 1.15
        r1 = p1.add_run(act_desc)
        r1.font.name = "Calibri"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(51, 65, 85)


def add_docx_worksheet_rubric_table(doc: Document, criteria: Optional[List[Dict[str, Any]]] = None, topic: str = "la actividad", total_pts: int = 20):
    """
    Inserta la tabla auténtica «Rúbrica de Evaluación» con EXACTAMENTE TRES COLUMNAS:
    Columna 1: Criterio
    Columna 2: Descripción
    Columna 3: Nivel de logro
    """
    if not criteria or not isinstance(criteria, list) or len(criteria) == 0:
        criteria = [
            {
                "criterio": f"1. Dominio Conceptual y Fundamento de {topic}",
                "descripcion": f"Explica con precisión los principios técnicos, componentes y requerimientos operativos para {topic}.",
                "nivel_logro": "Destacado (AD)\nEsperado (A)"
            },
            {
                "criterio": "2. Ejecución Operativa y Calidad de Evidencia",
                "descripcion": f"Ejecuta el procedimiento práctico de {topic} con destreza, completando las actividades según las especificaciones técnicas.",
                "nivel_logro": "Esperado (A)"
            },
            {
                "criterio": "3. Seguridad Industrial y Protocolo 5S",
                "descripcion": "Aplica de forma constante las normas de seguridad, cuidado de herramientas o datos y mantiene el orden y limpieza.",
                "nivel_logro": "Esperado (A)"
            },
            {
                "criterio": "4. Autonomía y Metacognición Formativa",
                "descripcion": "Identifica sus avances y dificultades, proponiendo soluciones constructivas y autorregulando su proceso de aprendizaje.",
                "nivel_logro": "Esperado (A)\nEn proceso (B)"
            }
        ]

    tbl = doc.add_table(rows=len(criteria) + 1, cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    w_col0 = Inches(1.90)
    w_col1 = Inches(3.52)
    w_col2 = Inches(1.35)
    widths = [w_col0, w_col1, w_col2]

    # Header Row
    headers = ["Criterio", "Descripción", "Nivel de logro"]
    hdr_row = tbl.rows[0]
    trPr_hdr = hdr_row._tr.get_or_add_trPr()
    trPr_hdr.append(OxmlElement('w:tblHeader'))
    trPr_hdr.append(OxmlElement('w:cantSplit'))

    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.width = widths[c_idx]
        set_cell_background_color(cell, "1E293B")
        set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.bold = True
        r.font.name = "Arial"
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows
    for r_idx, crit in enumerate(criteria, start=1):
        row = tbl.rows[r_idx]
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))

        c_name = crit.get("criterio") or crit.get("name") or f"Criterio {r_idx}"
        c_desc = crit.get("descripcion") or crit.get("desc") or crit.get("ad") or crit.get("a") or ""
        c_level = crit.get("nivel_logro") or crit.get("nivel") or "Esperado (A)"

        # Col 0: Criterio
        c0 = row.cells[0]
        c0.width = w_col0
        set_cell_background_color(c0, "F8FAFC")
        set_cell_margins(c0, top=55, bottom=55, left=80, right=80)
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p0.paragraph_format.space_before = Pt(0)
        p0.paragraph_format.space_after = Pt(0)
        p0.paragraph_format.line_spacing = 1.15
        r0 = p0.add_run(c_name)
        r0.bold = True
        r0.font.name = "Calibri"
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(30, 41, 59)

        # Col 1: Descripción
        c1 = row.cells[1]
        c1.width = w_col1
        if r_idx % 2 == 0:
            set_cell_background_color(c1, "F8FAFC")
        set_cell_margins(c1, top=55, bottom=55, left=80, right=80)
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p1.paragraph_format.space_before = Pt(0)
        p1.paragraph_format.space_after = Pt(0)
        p1.paragraph_format.line_spacing = 1.15
        r1 = p1.add_run(c_desc)
        r1.font.name = "Calibri"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(51, 65, 85)

        # Col 2: Nivel de logro
        c2 = row.cells[2]
        c2.width = w_col2
        set_cell_background_color(c2, "F8FAFC")
        set_cell_margins(c2, top=55, bottom=55, left=80, right=80)
        p2 = c2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after = Pt(0)
        p2.paragraph_format.line_spacing = 1.15
        r2 = p2.add_run(c_level)
        r2.bold = True
        r2.font.name = "Calibri"
        r2.font.size = Pt(9.0)
        r2.font.color.rgb = RGBColor(30, 41, 59)



def add_docx_worksheet_checklist_table(doc: Document, criteria: Optional[List[Any]] = None, topic: str = "la actividad"):
    """
    Inserta la tabla auténtica institucional 'Lista de Cotejo' con CUATRO COLUMNAS (CET N.º 34):
    Columna 1: Criterio de Evaluación / Indicador (3.47 in / 8.81 cm)
    Columna 2: Sí (0.65 in / 1.65 cm, centrado [   ])
    Columna 3: En proceso (0.85 in / 2.16 cm, centrado [   ])
    Columna 4: Evidencia / Comentario (1.80 in / 4.57 cm)
    Ancho total: 6.77 in (A4 Portrait exacto con márgenes 0.75 in).
    """
    rows_data = []
    if criteria and isinstance(criteria, list) and len(criteria) > 0:
        for c in criteria:
            if isinstance(c, dict):
                crit_txt = c.get("criterio") or c.get("name") or c.get("descripcion") or str(c)
            else:
                crit_txt = str(c)
            if crit_txt.strip():
                rows_data.append(crit_txt.strip())

    if not rows_data:
        rows_data = [
            f"1. Dominio conceptual: Explica los principios técnicos y requerimientos operativos de {topic}.",
            f"2. Ejecución práctica: Desarrolla las actividades y ejercicios respetando pautas y procedimientos de {topic}.",
            f"3. Calidad y seguridad: Aplica normas técnicas, cuidado de recursos y protocolos de seguridad/5S.",
            f"4. Autonomía y mejora: Verifica sus resultados y propone soluciones para optimizar su desempeño."
        ]

    tbl = doc.add_table(rows=len(rows_data) + 1, cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    widths = [Inches(3.17), Inches(0.70), Inches(1.00), Inches(1.90)]
    headers = ["Criterio de Evaluación / Indicador", "Sí", "En proceso", "Evidencia / Comentario"]

    hdr_row = tbl.rows[0]
    trPr_hdr = hdr_row._tr.get_or_add_trPr()
    trPr_hdr.append(OxmlElement('w:tblHeader'))
    trPr_hdr.append(OxmlElement('w:cantSplit'))

    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.width = widths[c_idx]
        set_cell_background_color(cell, "1E293B")
        set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx in [1, 2] else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(h_text)
        run.bold = True
        run.font.name = "Calibri"
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, c_text in enumerate(rows_data):
        row_obj = tbl.rows[r_idx + 1]
        trPr = row_obj._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))

        # Col 0: Criterio
        c0 = row_obj.cells[0]
        c0.width = widths[0]
        set_cell_margins(c0, top=50, bottom=50, left=70, right=70)
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_before = Pt(0)
        p0.paragraph_format.space_after = Pt(0)
        p0.paragraph_format.line_spacing = 1.15
        r0 = p0.add_run(c_text)
        r0.font.name = "Calibri"
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(30, 41, 59)

        # Col 1: Sí
        c1 = row_obj.cells[1]
        c1.width = widths[1]
        set_cell_margins(c1, top=50, bottom=50, left=40, right=40)
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p1.paragraph_format.space_before = Pt(0)
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run("[   ]")
        r1.font.name = "Calibri"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(100, 116, 139)

        # Col 2: En proceso
        c2 = row_obj.cells[2]
        c2.width = widths[2]
        set_cell_margins(c2, top=50, bottom=50, left=40, right=40)
        p2 = c2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after = Pt(0)
        r2 = p2.add_run("[   ]")
        r2.font.name = "Calibri"
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = RGBColor(100, 116, 139)

        # Col 3: Evidencia / Comentario
        c3 = row_obj.cells[3]
        c3.width = widths[3]
        set_cell_margins(c3, top=50, bottom=50, left=70, right=70)
        p3 = c3.paragraphs[0]
        p3.paragraph_format.space_before = Pt(0)
        p3.paragraph_format.space_after = Pt(0)
        r3 = p3.add_run("")
        r3.font.name = "Calibri"
        r3.font.size = Pt(9.0)

def generate_session_docx_bytes(doc_data: Dict[str, Any]) -> bytes:
    """
    Genera una Sesión de Aprendizaje en Microsoft Word (.docx) con formato institucional oficial CET N.º 34:
    - Encabezado institucional formal único (sin duplicaciones).
    - Metadatos informativos en tabla de 4 columnas (sin campo 'Estudiante').
    - Propósito formativo que describe el aprendizaje esperado real.
    - Situación significativa contextualizada con retos técnicos.
    - Tabla de Procesos Didácticos (Acción Completa GTZ) con EXACTAMENTE 4 COLUMNAS:
      1. Pasos o etapas
      2. Tiempo (suma exactamente la duración establecida)
      3. Acciones o actividades del docente
      4. Acciones o actividades del estudiante
    - cantSplit en todas las filas y tblHeader en encabezados de tabla.
    - Materiales y recursos de especialidad (digital/computación o taller industrial).
    - Matriz de Rúbrica Analítica CNEB (Escala vigesimal o niveles de logro).
    - Bloque de 3 firmas reglamentarias (Docente Responsable, Jefe de Taller, Subdirector).
    - Márgenes A4 calibrados (0.75 in) y tipografía equilibrada (10.5 pt cuerpo, 9.5 pt tablas).
    """
    data = parse_document_data(doc_data, target="teacher")
    c_json = data.get("content_json") or {}
    if isinstance(c_json, str):
        try:
            c_json = json.loads(c_json)
        except Exception:
            c_json = {}

    topic = data.get("topic") or "la actividad"
    specialty = data.get("specialty") or "Educación para el Trabajo"
    clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "")
    duration_min = int(data.get("duration") or 90)
    ped_hours = max(1, round(duration_min / 45))
    grade = int(data.get("grade") or 1)
    grade_words = {1: "1.°", 2: "2.°", 3: "3.°", 4: "4.°", 5: "5.°"}
    grade_str = grade_words.get(grade, f"{grade}.°")
    section_name = data.get("section") or "A"
    teacher_name = data.get("teacher_name") or "Prof. Responsable de Taller"

    is_digital = any(k in f"{topic} {clean_spec}".lower() for k in [
        "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
        "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
    ])

    doc = Document()

    # Configuración de márgenes A4 estrictos (0.75 in simétricos)
    for s in doc.sections:
        s.top_margin = Inches(0.75)
        s.bottom_margin = Inches(0.75)
        s.left_margin = Inches(0.75)
        s.right_margin = Inches(0.75)
        s.page_width = Inches(8.27)
        s.page_height = Inches(11.69)
        s.different_first_page_header_footer = True

        # Header subsiguiente
        header_p = s.header.paragraphs[0]
        header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_head = header_p.add_run(f"I.E. CET N.º 34 | Sesión de Aprendizaje: {topic[:45]}")
        r_head.font.name = "Calibri"
        r_head.font.size = Pt(8.5)
        r_head.font.color.rgb = RGBColor(148, 163, 184)

        # Footer en todas las páginas
        footer_p = s.footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_foot = footer_p.add_run(f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026")
        r_foot.font.name = "Calibri"
        r_foot.font.size = Pt(8.5)
        r_foot.font.color.rgb = RGBColor(148, 163, 184)

        first_footer_p = s.first_page_footer.paragraphs[0]
        first_footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_ff = first_footer_p.add_run(f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026")
        r_ff.font.name = "Calibri"
        r_ff.font.size = Pt(8.5)
        r_ff.font.color.rgb = RGBColor(148, 163, 184)

    # 1. Membrete Institucional CET N.° 34 como párrafos estilizados (cero duplicaciones)
    add_docx_header_banner(
        doc,
        title=f"SESIÓN DE APRENDIZAJE: {topic.upper()}",
        subtitle=f"PLANIFICACIÓN CURRICULAR Y SECUENCIA DIDÁCTICA CNEB / EPT 2026 — CET N.° 34",
        is_confidential=False
    )

    # 2. Datos Informativos (Tabla auténtica de 4 columnas, sin campo 'Estudiante')
    add_docx_metadata_table(doc, data)

    # 3. Propósito de Aprendizaje y Criterios de Evaluación
    add_docx_heading(doc, "I. Propósitos de Aprendizaje y Criterios de Evaluación", level=1)

    comp_val = data.get("competence") or (c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}).get("competencia") or "Gestiona proyectos de emprendimiento económico o social."
    purp_val = data.get("purpose") or (c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}).get("proposito") or ""
    if not purp_val or purp_val.lower().startswith("desarrollar capacidades y habilidades formativas sobre"):
        if is_digital:
            purp_val = f"Comprender y aplicar criterios técnicos para organizar, clasificar, respaldar y gestionar carpetas y archivos digitales de manera estructurada y segura, optimizando el acceso y la conservación de la información en entornos locales y en la nube."
        else:
            purp_val = f"Comprender los principios técnicos, normas de seguridad y secuencia operativa estandarizada para {topic}, ejecutando las tareas prácticas con precisión, orden y control de calidad (5S)."

    crit_val = c_json.get("criterios_evaluacion") or (
        "Organiza una carpeta digital aplicando criterios de estructura jerárquica, nombres adecuados, depuración de duplicados y uso responsable del almacenamiento en la nube."
        if is_digital else
        f"Aplica destrezas técnicas en {topic} cumpliendo normas de seguridad 5S y especificaciones técnicas requeridas."
    )
    evid_val = c_json.get("evidencia_aprendizaje") or (c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}).get("evidencia") or (
        "Carpeta digital organizada y depurada que cumple los criterios de gestión de archivos y seguridad digital."
        if is_digital else
        f"Ficha de operaciones y producto técnico de {topic} terminado según especificaciones."
    )

    items_prop = [
        ("• Competencia CNEB: ", comp_val),
        ("• Capacidades CNEB: ", "Aplica habilidades técnicas en entornos tecnológicos y de taller. Trabaja cooperativamente para lograr objetivos y metas. Evalúa los resultados del proyecto."),
        ("• Propósito Formativo (Aprendizaje Esperado): ", purp_val),
        ("• Criterio de Evaluación: ", crit_val),
        ("• Evidencia de Aprendizaje: ", evid_val)
    ]

    for lbl, val in items_prop:
        p_item = doc.add_paragraph()
        p_item.paragraph_format.space_before = Pt(0)
        p_item.paragraph_format.space_after = Pt(2.5)
        p_item.paragraph_format.line_spacing = 1.15
        r_lbl = p_item.add_run(lbl)
        r_lbl.bold = True
        r_lbl.font.name = "Calibri"
        r_lbl.font.size = Pt(10.5)
        r_lbl.font.color.rgb = RGBColor(30, 41, 59)
        r_val = p_item.add_run(val)
        r_val.font.name = "Calibri"
        r_val.font.size = Pt(10.5)
        r_val.font.color.rgb = RGBColor(51, 65, 85)

    # 4. Situación Significativa Contextualizada
    add_docx_heading(doc, "II. Situación Significativa Contextualizada", level=1)
    sit_sig = c_json.get("situacion_significativa") or (
        f"En el aula digital y laboratorio de cómputo de la I.E. CET N.º 34 de Chancay, los estudiantes del {grade_str} grado de secundaria "
        f"deben estructurar eficientemente sus evidencias académicas vinculadas a {topic}. Se evidencia desorganización en sus archivos y falta "
        f"de nomenclatura uniforme, lo que ocasiona pérdidas de información y demoras en el aprendizaje. Frente a este desafío, nos preguntamos: "
        f"¿Cómo estructurar nuestras carpetas y archivos con estándares técnicos y de seguridad? ¿Qué protocolos de respaldo en la nube debemos aplicar?"
        if is_digital else
        f"En los talleres productivos de la I.E. CET N.º 34 de Chancay, los estudiantes del {grade_str} grado de secundaria desarrollan competencias prácticas "
        f"en {clean_spec}. Para la sesión de {topic}, se requiere aplicar secuencias de operación estandarizadas respetando tolerancias, orden y medidas 5S. "
        f"Frente a este reto, los estudiantes planifican, ejecutan y controlan el proceso técnico para garantizar un producto de calidad y libre de riesgos."
    )
    add_docx_callout_box(doc, text=sit_sig, title="CONTEXTO INSTITUCIONAL Y RETO FORMATIVO", is_warning=False)

    # 5. Desarrollo de los Procesos Didácticos (Acción Completa GTZ)
    add_docx_heading(doc, f"III. Desarrollo de los Procesos Didácticos de la Sesión ({duration_min} Minutos)", level=1)

    gtz_steps = c_json.get("procesos_didacticos_gtz")
    if not gtz_steps or not isinstance(gtz_steps, list) or len(gtz_steps) == 0:
        if duration_min == 225:
            t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 10, 20, 30, 135, 20, 10
        elif duration_min == 135:
            t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 15, 20, 20, 50, 15, 15
        elif duration_min == 90:
            t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 10, 15, 15, 35, 10, 5
        else:
            t_inf = max(5, int(duration_min * 0.08))
            t_plan = max(10, int(duration_min * 0.12))
            t_dec = max(10, int(duration_min * 0.15))
            t_cont = max(5, int(duration_min * 0.10))
            t_eval = max(5, int(duration_min * 0.08))
            t_ejec = duration_min - (t_inf + t_plan + t_dec + t_cont + t_eval)

        if is_digital:
            gtz_steps = [
                {
                    "paso": "1. INFORMARSE",
                    "tiempo": f"{t_inf} Minutos",
                    "actividad_docente": f"Presenta una situación problemática real sobre pérdida y desorden de archivos en entornos informáticos. Plantea preguntas retadoras sobre cómo estructurar {topic} y explica los objetivos esperados.",
                    "actividad_estudiante": f"Analiza la situación planteada, recupera saberes previos sobre almacenamiento local y en la nube, y reflexiona sobre la necesidad de organizar metódicamente sus archivos digitales."
                },
                {
                    "paso": "2. PLANIFICAR",
                    "tiempo": f"{t_plan} Minutos",
                    "actividad_docente": f"Modela la secuencia técnica y orienta a los equipos en la formulación de una hoja de ruta jerárquica para {topic}, detallando reglas de nomenclatura y clasificación.",
                    "actividad_estudiante": f"Elabora en equipo un plan de trabajo y diagrama el árbol de carpetas con niveles por año, bimestre y asignatura, definiendo convenciones de nombres estándar."
                },
                {
                    "paso": "3. DECIDIR",
                    "tiempo": f"{t_dec} Minutos",
                    "actividad_docente": f"Revisa las propuestas de los equipos, absuelve dudas sobre plataformas en la nube (Google Drive / OneDrive) y valida la estructura jerárquica antes de la práctica en computadoras.",
                    "actividad_estudiante": f"Decide la arquitectura final de carpetas, asigna responsabilidades dentro del equipo y selecciona las herramientas digitales idóneas para respaldar la información."
                },
                {
                    "paso": "4. EJECUTAR",
                    "tiempo": f"{t_ejec} Minutos",
                    "actividad_docente": f"Demuestra el procedimiento operativo: creación de directorios, renombramiento sistemático, depuración de duplicados, sincronización en la nube y configuración de permisos de acceso. Monitorea y brinda soporte técnico continuo.",
                    "actividad_estudiante": f"Aplica la secuencia técnica en su estación de cómputo: crea la estructura de directorios, renombra los archivos según la convención establecida, depura elementos redundantes y realiza copias de seguridad en la nube."
                },
                {
                    "paso": "5. CONTROLAR",
                    "tiempo": f"{t_cont} Minutos",
                    "actividad_docente": f"Guía la autoevaluación y coevaluación mediante una lista de cotejo técnica. Verifica el cumplimiento de los estándares de orden, nomenclatura y seguridad digital en cada estación.",
                    "actividad_estudiante": f"Verifica su carpeta digital mediante la lista de cotejo: comprueba la correcta jerarquía, la legibilidad de nombres, la ausencia de archivos duplicados y el correcto acceso compartido."
                },
                {
                    "paso": "6. EVALUAR",
                    "tiempo": f"{t_eval} Minutos",
                    "actividad_docente": f"Modera la plenaria de cierre, retroalimenta los logros observados, consolida los conceptos clave de {topic} y promueve la reflexión metacognitiva.",
                    "actividad_estudiante": f"Sustenta brevemente la organización de su portafolio digital, evalúa su desempeño técnico y propone acciones de mejora para la gestión responsable de su información."
                }
            ]
        else:
            gtz_steps = [
                {
                    "paso": "1. INFORMARSE",
                    "tiempo": f"{t_inf} Minutos",
                    "actividad_docente": f"Presenta la pieza o servicio a realizar en {topic}, explica las especificaciones técnicas del plano de taller y las normas de seguridad aplicables.",
                    "actividad_estudiante": f"Interpreta las especificaciones del plano, identifica materiales y herramientas requeridas y formula consultas técnicas al docente."
                },
                {
                    "paso": "2. PLANIFICAR",
                    "tiempo": f"{t_plan} Minutos",
                    "actividad_docente": f"Orienta la elaboración de la hoja de proceso, guiando la selección de herramientas, parámetros de operación y tiempos estándar para {topic}.",
                    "actividad_estudiante": f"Elabora la hoja de proceso de operaciones, definiendo la secuencia de pasos técnicos y seleccionando los equipos de protección personal."
                },
                {
                    "paso": "3. DECIDIR",
                    "tiempo": f"{t_dec} Minutos",
                    "actividad_docente": f"Valida la hoja de proceso de cada cuadrilla y autoriza el inicio de la fase operativa tras constatar las condiciones de seguridad en el taller.",
                    "actividad_estudiante": f"Revisa y optimiza la secuencia de operaciones elegida, verificando que los instrumentos de medición estén calibrados."
                },
                {
                    "paso": "4. EJECUTAR",
                    "tiempo": f"{t_ejec} Minutos",
                    "actividad_docente": f"Modela las operaciones críticas de {topic}, supervisa permanentemente el cumplimiento de normas de seguridad industrial y atiende contingencias técnicas.",
                    "actividad_estudiante": f"Ejecuta las operaciones en las máquinas o bancos de trabajo siguiendo estrictamente la hoja de proceso y respetando las tolerancias permitidas."
                },
                {
                    "paso": "5. CONTROLAR",
                    "tiempo": f"{t_cont} Minutos",
                    "actividad_docente": f"Acompaña la verificación dimensional y de acabado técnico con instrumentos de precisión y ficha técnica de control de calidad.",
                    "actividad_estudiante": f"Mide y verifica las dimensiones de la pieza o trabajo realizado, contrastando los resultados con las especificaciones técnicas."
                },
                {
                    "paso": "6. EVALUAR",
                    "tiempo": f"{t_eval} Minutos",
                    "actividad_docente": f"Evalúa el producto terminado y el proceso formativo integral, aplicando la rúbrica de evaluación y reforzando las buenas prácticas de orden y limpieza 5S.",
                    "actividad_estudiante": f"Presenta el producto terminado para su calificación, reflexiona sobre las dificultades superadas y limpia y ordena su puesto de trabajo."
                }
            ]
    else:
        for s_idx, st in enumerate(gtz_steps[:6], start=1):
            if "tiempo" not in st and "tiempo_minutos" in st:
                st["tiempo"] = f"{st['tiempo_minutos']} Minutos"
            elif "tiempo" in st and str(st["tiempo"]).isdigit():
                st["tiempo"] = f"{st['tiempo']} Minutos"

    add_docx_session_gtz_table(doc, gtz_steps)

    # 6. Recursos y Materiales Educativos
    add_docx_heading(doc, "IV. Materiales y Recursos Educativos", level=1)
    if is_digital:
        mat_items = [
            ("• Recursos Informáticos: ", "Computadoras / Laptops con conexión a Internet y navegador web actualizado."),
            ("• Plataformas Digitales: ", "Plataforma de almacenamiento en la nube institucional (Google Workspace / Drive)."),
            ("• Equipos Multimedia: ", "Proyector multimedia, ecran y pizarra interactiva del aula de cómputo."),
            ("• Materiales de Estudio: ", f"Guía técnica de operaciones y ficha de actividades prácticas sobre {topic}."),
            ("• Bibliografía Oficial: ", "Currículo Nacional de la Educación Básica (CNEB) — MINEDU; Manuales y guías técnicas de especialidad — CET N.º 34 Chancay.")
        ]
    else:
        mat_items = [
            ("• Maquinaria y Equipos: ", f"Máquinas herramientas, equipos e instrumentos propios del taller de {clean_spec}."),
            ("• Herramientas de Trabajo: ", f"Herramientas manuales de corte, sujeción y conformado requeridas para {topic}."),
            ("• Instrumentos de Control: ", "Calibre pie de rey, vernier, micrómetro y patrones de verificación dimensional."),
            ("• Equipo de Protección: ", "EPP reglamentario de taller (mameluco, lentes de seguridad, calzado con punta de acero)."),
            ("• Bibliografía Oficial: ", "Currículo Nacional de la Educación Básica (CNEB) — MINEDU; Manuales técnicos de taller — CET N.º 34 Chancay.")
        ]

    for lbl, val in mat_items:
        p_mat = doc.add_paragraph()
        p_mat.paragraph_format.space_before = Pt(0)
        p_mat.paragraph_format.space_after = Pt(2.5)
        p_mat.paragraph_format.line_spacing = 1.15
        r_lbl = p_mat.add_run(lbl)
        r_lbl.bold = True
        r_lbl.font.name = "Calibri"
        r_lbl.font.size = Pt(10.0)
        r_lbl.font.color.rgb = RGBColor(30, 41, 59)
        r_val = p_mat.add_run(val)
        r_val.font.name = "Calibri"
        r_val.font.size = Pt(10.0)
        r_val.font.color.rgb = RGBColor(51, 65, 85)

    # 7. Matriz de Rúbrica Analítica de Evaluación Formativa
    add_docx_heading(doc, "V. Instrumento de Evaluación Formativa (Rúbrica Analítica CNEB)", level=1)
    add_docx_rubric_table(doc, total_pts=20, topic=topic, custom_criteria=c_json.get("rubrica_items"), session_type=data.get("session_type"))

    # 8. Conformidad y Firmas Institucionales Reglamentarias (3 Firmas Oficiales)
    add_docx_heading(doc, "VI. Conformidad y Firmas Institucionales", level=1)
    add_docx_institutional_3_signatures(doc, specialty=clean_spec, teacher_name=teacher_name, custom_firmas=c_json.get("firmas_institucionales"))

    # Estampilla institucional de visado digital directivo con código QR (Bloque 3)
    visa_info = c_json.get("visado_digital") or data.get("visado_digital")
    if visa_info and (data.get("status") == "APROBADO" or visa_info.get("status") == "APROBADO"):
        add_docx_digital_visa_stamp(doc, visa_info)

    # Protección de filas de tablas (cantSplit y tblHeader)
    for tbl in doc.tables:
        for r_idx, r in enumerate(tbl.rows):
            trPr = r._tr.get_or_add_trPr()
            trPr.append(OxmlElement('w:cantSplit'))
            if r_idx == 0 and len(tbl.rows) > 1:
                trPr.append(OxmlElement('w:tblHeader'))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def generate_worksheet_docx_bytes(doc_data: Dict[str, Any], target: str = "teacher") -> bytes:
    """
    Genera una Ficha de Aprendizaje en Microsoft Word (.docx) con formato institucional auténtico:
    - Sin tablas de una sola celda.
    - Encabezado institucional CET N.º 34 y metadatos auténticos.
    - Tabla «Ficha de Aprendizaje» con 2 columnas (Actividad y Descripción).
    - Tabla «Rúbrica de Evaluación» con 3 columnas (Criterio, Descripción y Nivel de logro).
    - Distribución equilibrada, espaciado profesional (1.15), márgenes A4 (0.8 in / 0.85 in).
    - Sin saltos de página artificiales ni soluciones genéricas sin respuestas reales.
    """
    data = parse_document_data(doc_data, target=target)
    c_json = data.get("content_json") or {}

    doc = Document()

    # Configuración de márgenes A4 estrictos
    for s in doc.sections:
        s.top_margin = Inches(0.75)
        s.bottom_margin = Inches(0.75)
        s.left_margin = Inches(0.75)
        s.right_margin = Inches(0.75)
        s.page_width = Inches(8.27)
        s.page_height = Inches(11.69)
        s.different_first_page_header_footer = True

        # Header subsiguiente
        header_p = s.header.paragraphs[0]
        header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_head = header_p.add_run(f"I.E. CET N.º 34 | Ficha de Aprendizaje: {data['topic'][:50]}")
        r_head.font.name = "Calibri"
        r_head.font.size = Pt(8.5)
        r_head.font.color.rgb = RGBColor(148, 163, 184)

        # Footer en todas las páginas
        footer_p = s.footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_foot = footer_p.add_run(f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026")
        r_foot.font.name = "Calibri"
        r_foot.font.size = Pt(8.5)
        r_foot.font.color.rgb = RGBColor(148, 163, 184)

        first_footer_p = s.first_page_footer.paragraphs[0]
        first_footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_ff = first_footer_p.add_run(f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026")
        r_ff.font.name = "Calibri"
        r_ff.font.size = Pt(8.5)
        r_ff.font.color.rgb = RGBColor(148, 163, 184)

    # 1. Membrete Institucional CET N.° 34 como párrafos estilizados (cero tablas de 1 celda)
    add_docx_header_banner(
        doc,
        title=f"FICHA DE APRENDIZAJE: {data['topic'].upper()}",
        subtitle="EDUCACIÓN PARA EL TRABAJO — CNEB 2026",
        is_confidential=False
    )

    # 2. Datos Informativos (Tabla auténtica de 4 columnas)
    add_docx_metadata_table(doc, data)

    # 3. Propósito de Aprendizaje y Competencia CNEB
    add_docx_heading(doc, "I. Propósito de Aprendizaje y Competencia CNEB", level=1)
    is_digital_topic = any(k in f"{data['topic']} {data['specialty']}".lower() for k in [
        "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
        "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
    ])
    comp_val = data.get("competence") or (c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}).get("competencia") or "Gestiona proyectos de emprendimiento económico o social."
    _raw_p = data.get("purpose") or (c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}).get("proposito") or ""
    if not _raw_p or _raw_p.strip().lower().startswith("desarrollar capacidades en"):
        if is_digital_topic:
            purp_val = "Comprender y aplicar criterios técnicos para organizar, clasificar, respaldar y gestionar carpetas y archivos digitales de manera estructurada y segura, optimizando el acceso y la conservación de la información en entornos locales y en la nube."
        else:
            purp_val = f"Comprender y aplicar los principios y operaciones clave de {data['topic']}, formulando soluciones prácticas y verificables con criterios de calidad y seguridad."
    else:
        purp_val = _raw_p.strip()
    evid_val = (c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}).get("evidencia") or f"Ficha de actividades desarrollada con ejercicios prácticos y reporte técnico de {data['topic']}."

    for lbl, val in [
        ("• Competencia CNEB: ", comp_val),
        ("• Propósito Formativo: ", purp_val),
        ("• Evidencia de Aprendizaje: ", evid_val)
    ]:
        p_item = doc.add_paragraph()
        p_item.paragraph_format.space_before = Pt(0)
        p_item.paragraph_format.space_after = Pt(2.5)
        p_item.paragraph_format.line_spacing = 1.15
        r_lbl = p_item.add_run(lbl)
        r_lbl.bold = True
        r_lbl.font.name = "Calibri"
        r_lbl.font.size = Pt(10.5)
        r_lbl.font.color.rgb = RGBColor(30, 41, 59)
        r_val = p_item.add_run(val)
        r_val.font.name = "Calibri"
        r_val.font.size = Pt(10.5)
        r_val.font.color.rgb = RGBColor(51, 65, 85)

    # 4. Marco Conceptual y Fundamento Técnico
    add_docx_heading(doc, "II. Fundamento Técnico y Conceptos Clave", level=1)
    mc_text = c_json.get("marco_conceptual") or ""
    if not mc_text:
        raw_md = data.get("content_markdown") or ""
        sec_m = re.search(r'(?i)(?:##|###)\s*(?:3\.\s*EXPLICACI[OÓ]N|MARCO\s+CONCEPTUAL|CONCEPTOS\s+CLAVE)[^\r\n]*\n(.*?)(?=\n(?:##|###)|$)', raw_md, re.DOTALL)
        if sec_m:
            mc_text = sec_m.group(1).strip()
        else:
            mc_text = f"El estudio y aplicación de {data['topic']} constituye un fundamento esencial en la formación técnica de {data['specialty']}. Permite a los estudiantes organizar recursos, aplicar secuencias operativas estandarizadas y desarrollar soluciones prácticas con criterios de calidad y seguridad."

    for line in mc_text.split("\n"):
        line_s = line.strip()
        if line_s and line_s not in ["---", "===", "***", "___", "**", "*"]:
            p_line = doc.add_paragraph()
            p_line.paragraph_format.space_before = Pt(0)
            p_line.paragraph_format.space_after = Pt(2.5)
            p_line.paragraph_format.line_spacing = 1.15
            p_line.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_formatted_runs_to_paragraph(p_line, line_s, default_font_size=10.5)

    # 5. Tabla «Ficha de Aprendizaje» (2 Columnas: Actividad y Descripción)
    add_docx_heading(doc, "III. Ficha de Aprendizaje — Actividades Prácticas", level=1)
    act_items = []
    if c_json.get("actividades") and isinstance(c_json["actividades"], list):
        for act in c_json["actividades"]:
            if isinstance(act, dict):
                act_items.append({
                    "actividad": act.get("actividad") or act.get("titulo") or "Actividad",
                    "descripcion": act.get("descripcion") or act.get("detalle") or ""
                })
    elif c_json.get("retos_aplicacion"):
        retos_raw = c_json["retos_aplicacion"]
        if isinstance(retos_raw, str):
            for line in retos_raw.split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    act_items.append({"actividad": parts[0].strip(), "descripcion": parts[1].strip()})
        elif isinstance(retos_raw, list):
            for idx, r_item in enumerate(retos_raw, start=1):
                act_items.append({"actividad": f"Reto {idx}", "descripcion": str(r_item)})

    if len(act_items) < 3:
        act_items = [
            {
                "actividad": "Actividad 1:\nExploración y Diagnóstico",
                "descripcion": f"Identifica los conceptos clave y condiciones iniciales para {data['topic']}, reconociendo las herramientas y parámetros de operación requeridos."
            },
            {
                "actividad": "Actividad 2:\nProcedimiento Guiado",
                "descripcion": f"Aplica la secuencia técnica modelada paso a paso para {data['topic']}, respetando tolerancias, normas técnicas y medidas de seguridad."
            },
            {
                "actividad": "Actividad 3:\nEjercicio Práctico Aplicado",
                "descripcion": f"Desarrolla el ejercicio práctico propuesto en el taller o aula digital, registrando mediciones, capturas o avances técnicos en la guía de trabajo."
            },
            {
                "actividad": "Actividad 4:\nReto Autónomo y Resolución",
                "descripcion": f"Resuelve el reto técnico planteado aplicando estrategias de optimización, control de calidad y prevención de fallas operacionales."
            },
            {
                "actividad": "Actividad 5:\nMetacognición y Transferencia",
                "descripcion": f"Evalúa los resultados obtenidos en {data['topic']}, describe los aprendizajes adquiridos y formula propuestas de mejora para su desempeño."
            }
        ]

    add_docx_worksheet_activities_table(doc, activities=act_items, topic=data["topic"])

    # 6. Tabla Institucional “Lista de Cotejo” (4 Columnas: Criterio, Sí, En proceso, Evidencia/Comentario)
    add_docx_heading(doc, "IV. Evaluación Rápida — Lista de Cotejo", level=1)
    crit_items = []
    if c_json.get("lista_cotejo_autoevaluacion") and isinstance(c_json["lista_cotejo_autoevaluacion"], list):
        for idx, lc in enumerate(c_json["lista_cotejo_autoevaluacion"][:4], start=1):
            if isinstance(lc, dict):
                crit_items.append(f"{idx}. {lc.get('criterio', f'Criterio {idx}')}")
            else:
                crit_items.append(f"{idx}. {str(lc)}")
    elif c_json.get("rubrica_items") and isinstance(c_json["rubrica_items"], list):
        for idx, c_it in enumerate(c_json["rubrica_items"][:4], start=1):
            if isinstance(c_it, dict):
                c_nom = c_it.get("criterio") or f"Criterio {idx}"
                crit_items.append(f"{idx}. {c_nom}")

    if len(crit_items) < 3:
        crit_items = [
            f"1. Dominio conceptual: Explica los principios técnicos y requerimientos operativos de {data['topic']}.",
            f"2. Ejecución práctica: Desarrolla las actividades y ejercicios respetando pautas y procedimientos de {data['topic']}.",
            f"3. Calidad y seguridad: Aplica normas técnicas, cuidado de recursos y protocolos de seguridad/5S.",
            f"4. Autonomía y mejora: Verifica sus resultados y propone soluciones para optimizar su desempeño."
        ]

    add_docx_worksheet_checklist_table(doc, criteria=crit_items, topic=data["topic"])

    # Metacognición Formativa
    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_before = Pt(4)
    p_meta.paragraph_format.space_after = Pt(2)
    p_meta.paragraph_format.keep_with_next = True
    r_mq = p_meta.add_run("Metacognición Formativa: ")
    r_mq.bold = True
    r_mq.font.name = "Calibri"
    r_mq.font.size = Pt(9.5)
    r_mq.font.color.rgb = RGBColor(30, 41, 59)
    r_mt = p_meta.add_run("¿Qué aprendí hoy en esta actividad y cómo puedo aplicar este aprendizaje en una situación técnica real?")
    r_mt.italic = True
    r_mt.font.name = "Calibri"
    r_mt.font.size = Pt(9.5)
    r_mt.font.color.rgb = RGBColor(71, 85, 105)

    p_lines = doc.add_paragraph()
    p_lines.paragraph_format.space_before = Pt(1)
    p_lines.paragraph_format.space_after = Pt(4)
    r_l = p_lines.add_run("_________________________________________________________________________________")
    r_l.font.color.rgb = RGBColor(148, 163, 184)

    # 7. Firma Docente Institucional
    add_docx_simple_teacher_signature(doc, teacher_name=data.get("teacher_name", "Docente Responsable"))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_docx_bytes(doc_data: Dict[str, Any], target: str = "teacher") -> bytes:
    """
    Genera un archivo Microsoft Word (.docx) real y validado Office Open XML.
    Retorna bytes puros listos para descarga o streaming.
    """
    data = parse_document_data(doc_data, target=target)
    doc_type = data["doc_type"]

    # Soporte y auto-resolución obligatoria de plantillas maestras oficiales CET N.º 34
    tpl_b = doc_data.get("template_bytes")
    tpl_path = doc_data.get("template_path")
    tpl_id = doc_data.get("template_id")

    if not tpl_b and not tpl_path and not tpl_id:
        tpl_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "templates", "smartteacher")
        if not os.path.isdir(tpl_dir):
            tpl_dir = os.path.abspath(os.path.join(os.getcwd(), "data", "templates", "smartteacher"))

        session_type = (data.get("session_type") or doc_data.get("session_type") or "").strip().lower()
        topic_lower = (data.get("topic") or "").lower()

        if doc_type == "sesion_aprendizaje":
            if session_type == "emprendimiento" or "lean" in topic_lower or "canvas" in topic_lower:
                cand = os.path.join(tpl_dir, "sesion_emprendimiento_leancanvas_cet34.docx")
            else:
                cand = os.path.join(tpl_dir, "sesion_tecnica_gtz_cet34.docx")
            if os.path.exists(cand):
                tpl_path = cand

        elif doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
            cand = os.path.join(tpl_dir, "ficha_trabajo_estudiante_cet34.docx")
            if os.path.exists(cand):
                tpl_path = cand

        elif doc_type in ["examen_tecnico", "examen", "practica_calificada", "practica_ejercicios", "practica"] or doc_data.get("modo") in ["examen", "practica"]:
            cand = os.path.join(tpl_dir, "examen_practica_cet34.docx")
            if os.path.exists(cand):
                tpl_path = cand

        elif doc_type in ["unidad_didactica", "unidad_aprendizaje"]:
            cand = os.path.join(tpl_dir, "unidad_didactica_cet34.docx")
            if os.path.exists(cand):
                tpl_path = cand

    if tpl_b or tpl_path or tpl_id:
        try:
            from app.ai.template_engine import template_engine
            if not tpl_b and tpl_path and os.path.exists(tpl_path):
                with open(tpl_path, "rb") as fp:
                    tpl_b = fp.read()
            if not tpl_b and tpl_id:
                from app.ai.service import ai_service
                t_rec = ai_service.get_template_by_id(int(tpl_id), {"id": doc_data.get("user_id", 1), "role_name": "DOCENTE"})
                if t_rec:
                    tpl_b = t_rec.get("file_bytes")
                    if not tpl_b and t_rec.get("file_path") and os.path.exists(t_rec["file_path"]):
                        with open(t_rec["file_path"], "rb") as fp:
                            tpl_b = fp.read()
            if tpl_b:
                return template_engine.render_docx_from_template(tpl_b, {**data, **doc_data, "doc_type": doc_type})
        except Exception as e:
            logger.warning(f"Error renderizando desde plantilla DOCX, aplicando fallback estandarizado: {e}")

    # Fallback de contingencia si no existe plantilla física o falló la renderización:
    if doc_type == "unidad_didactica":
        return generate_unit_docx_bytes(doc_data)

    if doc_type == "sesion_aprendizaje":
        return generate_session_docx_bytes(doc_data)

    if doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
        return generate_worksheet_docx_bytes(doc_data, target=target)

    is_student = data["is_student"]

    doc = Document()

    # Configuración de márgenes de página (2.0 cm superior/inferior, 2.16 cm laterales - A4 estricto)
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.85)
        s.right_margin = Inches(0.85)
        s.page_width = Inches(8.27)   # A4 ancho
        s.page_height = Inches(11.69) # A4 alto
        s.different_first_page_header_footer = True

        # Encabezado en páginas subsiguientes
        header_p = s.header.paragraphs[0]
        header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_head = header_p.add_run(f"I.E. INEI N.º 34 | {data['title'][:55]}")
        r_head.font.name = "Calibri"
        r_head.font.size = Pt(8.5)
        r_head.font.color.rgb = RGBColor(148, 163, 184)

        # Pie de página institucional en todas las páginas
        footer_p = s.footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r_foot = footer_p.add_run(f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026")
        r_foot.font.name = "Calibri"
        r_foot.font.size = Pt(8.5)
        r_foot.font.color.rgb = RGBColor(148, 163, 184)

        first_footer_p = s.first_page_footer.paragraphs[0]
        first_footer_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r_ff = first_footer_p.add_run(f"{INSTITUTION_NAME} — Chancay | Educación Técnica CNEB 2026")
        r_ff.font.name = "Calibri"
        r_ff.font.size = Pt(8.5)
        r_ff.font.color.rgb = RGBColor(148, 163, 184)

    # Subtítulo institucional según tipo y versión
    sub_map = {
        "sesion_aprendizaje": "PLANIFICACIÓN CURRICULAR Y SECUENCIA DIDÁCTICA CNEB / EPT 2026",
        "ficha_actividad": "FICHA DE APRENDIZAJE Y GUÍA TÉCNICA DE TALLER OPERATIVO",
        "ficha_guia": "FICHA GUÍA Y MATERIAL DE ESTUDIO CNEB / EPT 2026",
        "presentacion_tema": "GUÍA DE PRESENTACIÓN Y DESARROLLO TEMÁTICO",
        "ficha_trabajo": "FICHA DE TRABAJO Y GUÍA OPERATIVA DE TALLER",
        "practica_ejercicios": "PRÁCTICA DE EJERCICIOS Y PROBLEMAS TÉCNICOS",
        "solucionario_docente": "SOLUCIONARIO Y PAUTAS PEDAGÓGICAS DOCENTES",
        "examen_tecnico": "EVALUACIÓN ESCRITA Y PRÁCTICA DE TALLER" if is_student else "SOLUCIONARIO Y CLAVE DE CORRECCIÓN CONFIDENCIAL DOCENTE",
        "rubrica_evaluacion": "INSTRUMENTO DE EVALUACIÓN FORMATIVA CNEB"
    }
    subtitle = sub_map.get(doc_type, "DOCUMENTO PEDAGÓGICO OFICIAL")

    # 1. Membrete Institucional
    add_docx_header_banner(
        doc,
        title=data["title"],
        subtitle=subtitle,
        is_confidential=(doc_type == "examen_tecnico" and not is_student)
    )

    # 2. Datos Informativos
    add_docx_metadata_table(doc, data)

    # 3. Recuadro de Estudiante para Fichas y Exámenes dirigidos a estudiantes
    if is_student and doc_type in ["examen_tecnico", "ficha_actividad"]:
        tot_pts = data["content_json"].get("total_points", 20)
        add_docx_student_identification_box(doc, total_pts=tot_pts)

    # 4. Aviso de Confidencialidad para Solucionarios Docentes
    if not is_student and doc_type == "examen_tecnico":
        add_docx_callout_box(
            doc,
            text="Este solucionario contiene las respuestas correctas, justificaciones pedagógicas y matriz de ponderación. Documento reservado exclusivamente para el docente calificador.",
            title="CONFIDENCIAL DOCENTE — PROHIBIDA SU DISTRIBUCIÓN",
            is_warning=True
        )

    # 5. Renderizado del Cuerpo según Tipo de Documento
    c_json = data["content_json"]

    if doc_type == "sesion_aprendizaje":
        gtz_steps = c_json.get("procesos_didacticos_gtz")
        if gtz_steps and isinstance(gtz_steps, list):
            # Formato Institucional Oficial CET N° 34 / INEI N° 34 de Chancay
            add_docx_heading(doc, "I. Propósito de la Sesión y Criterios de Evaluación", level=1)
            p_prop = doc.add_paragraph()
            r_purp = p_prop.add_run("• Propósito de la Sesión: ")
            r_purp.bold = True
            crit_text = c_json.get('criterios_evaluacion') or f"Aplica habilidades técnicas en {data['topic']}"
            evid_text = c_json.get('propositos', {}).get('evidencia') or f"Producto técnico terminado o ficha de operaciones de {data['topic']}"
            p_prop.add_run(f"{data['purpose']}\n")
            r_crit = p_prop.add_run("• Criterio de Evaluación: ")
            r_crit.bold = True
            p_prop.add_run(f"{crit_text}\n")
            r_evid = p_prop.add_run("• Evidencia de Aprendizaje: ")
            r_evid.bold = True
            p_prop.add_run(f"{evid_text}")

            # Situación Significativa
            sit_sig = c_json.get("situacion_significativa")
            if sit_sig:
                add_docx_heading(doc, "II. Situación Significativa", level=1)
                add_docx_callout_box(doc, text=str(sit_sig), title="CONTEXTO INSTITUCIONAL Y RETOS", is_warning=False)

            # Procesos Didácticos (Acción Completa GTZ)
            add_docx_heading(doc, f"III. Desarrollo de los Procesos Didácticos de la Sesión ({data['duration']} Minutos)", level=1)
            add_docx_session_gtz_table(doc, gtz_steps)

            # Materiales y Recursos
            add_docx_heading(doc, "IV. Materiales y Recursos Educativos", level=1)
            p_mat = doc.add_paragraph()
            is_dig = any(k in f"{data['topic']} {data['specialty']}".lower() for k in ["carpeta", "digital", "archivo", "ofimática", "computación", "informática", "nube", "web"])
            default_mat = "Computadora con acceso a internet, almacenamiento en la nube, proyector multimedia" if is_dig else "Herramientas de taller, instrumentos de medición y verificación técnica"
            p_mat.add_run(f"• Materiales: {c_json.get('materiales_recursos', default_mat)}\n")
            p_mat.add_run("• Bibliografía: Currículo Nacional de Educación Básica (CNEB) — MINEDU.")

            # Rúbrica formativa y Firmas según modalidad institucional vs libre
            add_docx_rubric_table(doc, total_pts=20, topic=data["topic"], custom_criteria=c_json.get("rubrica_items"), session_type=data.get("session_type"))
            if data.get("structure_mode") == "institucional":
                add_docx_institutional_3_signatures(doc, specialty=data["specialty"], teacher_name=data.get("teacher_name", "Docente"))
            else:
                add_docx_simple_teacher_signature(doc, teacher_name=data.get("teacher_name", "Docente"))

        else:
            # Propósitos CNEB
            add_docx_heading(doc, "I. Propósitos de Aprendizaje y Criterios de Evaluación", level=1)
            p_prop = doc.add_paragraph()
            r_comp = p_prop.add_run("• Competencia CNEB: ")
            r_comp.bold = True
            p_prop.add_run(f"{data['competence']}\n")
            r_purp = p_prop.add_run("• Propósito de Aprendizaje: ")
            r_purp.bold = True
            p_prop.add_run(f"{data['purpose']}\n")
            r_evid = p_prop.add_run("• Evidencia de Aprendizaje: ")
            r_evid.bold = True
            p_prop.add_run(f"Elaboración de ficha de proceso y ejecución práctica de {data['topic']} con aplicación de normas técnicas.")

            # Secuencia Didáctica
            add_docx_heading(doc, "II. Secuencia Didáctica (Momentos Pedagógicos)", level=1)

            sec_did = c_json.get("secuencia_didactica")
            if not isinstance(sec_did, dict):
                sec_did = {}
            fases = [
                ("1. Fase de Inicio (Motivación, Saberes Previos y Conflicto Cognitivo)", sec_did.get("inicio", {}), "15 min"),
                ("2. Fase de Desarrollo (Gestión, Acompañamiento y Práctica Técnica)", sec_did.get("desarrollo", {}), f"{int(data['duration']) - 30} min"),
                ("3. Fase de Cierre (Metacognición, Evaluación y Retroalimentación)", sec_did.get("cierre", {}), "15 min")
            ]

            for f_title, f_val, default_t in fases:
                if isinstance(f_val, dict):
                    tiempo = f_val.get("tiempo", default_t)
                    f_text = f_val.get("actividades") or f_val.get("descripcion") or ""
                    if not f_text:
                        parts = [f"• {k.replace('_', ' ').capitalize()}: {v}" for k, v in f_val.items() if isinstance(v, str) and v.strip()]
                        f_text = "\n".join(parts)
                elif isinstance(f_val, str) and f_val.strip():
                    tiempo = default_t
                    f_text = f_val.strip()
                else:
                    tiempo = default_t
                    f_text = f"Actividades planificadas para el momento pedagógico de {f_title.lower()} contextualizadas en {data['topic']}."

                add_docx_heading(doc, f"{f_title} — [{tiempo}]", level=2)
                p_fase = doc.add_paragraph()
                p_fase.paragraph_format.line_spacing = 1.15
                p_fase.paragraph_format.space_after = Pt(6)
                p_fase.add_run(f_text)

            # Normas de Seguridad Industrial y 5S
            add_docx_heading(doc, "III. Normas de Seguridad Industrial, EPP y Protocolo 5S", level=1)
            seg_text = c_json.get("seguridad_industrial_5s") or c_json.get("seguridad_industrial") or ""
            if isinstance(seg_text, dict):
                seg_text = f"EPP Obligatorio: {seg_text.get('epp_requerido', 'Casco, lentes y zapatos dieléctricos')}\nNormas 5S: {seg_text.get('normas_5s', 'Seiri, Seiton, Seiso, Seiketsu, Shitsuke')}"
            if not seg_text:
                seg_text = f"El trabajo técnico en el taller de {data['specialty']} exige el uso estricto del Equipo de Protección Personal (EPP) y la aplicación rigurosa de las 5S antes, durante y después de la sesión."
            add_docx_callout_box(doc, text=seg_text, title="SEGURIDAD Y SALUD EN EL TRABAJO", is_warning=True)

            # Rúbrica y Firmas según modalidad institucional vs libre
            add_docx_rubric_table(doc, total_pts=20, topic=data["topic"], custom_criteria=c_json.get("rubrica_items"), session_type=data.get("session_type"))
            if data.get("structure_mode") == "institucional":
                add_docx_institutional_3_signatures(doc, specialty=data["specialty"], teacher_name=data.get("teacher_name", "Docente"))
            else:
                add_docx_simple_teacher_signature(doc, teacher_name=data.get("teacher_name", "Docente"))

    elif doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
        # Si el documento tiene contenido markdown generado, renderizar fielmente dicho contenido
        if data.get("content_markdown") and len(data["content_markdown"].strip()) > 30:
            render_markdown_to_docx(doc, data["content_markdown"])
            add_docx_simple_teacher_signature(doc, teacher_name=data.get("teacher_name", "Docente"))
        else:
            add_docx_heading(doc, "I. Marco Conceptual y Fundamento Técnico", level=1)
            p_mc = doc.add_paragraph()
            p_mc.paragraph_format.line_spacing = 1.15
            mc_text = c_json.get("marco_conceptual") or f"La presente guía técnica de {data['specialty']} orienta al estudiante en los principios fundamentales de {data['topic']}."
            p_mc.add_run(mc_text)

            add_docx_heading(doc, "II. Actividad de Aplicación y Procedimiento Paso a Paso", level=1)
            proc_text = c_json.get("actividad_paso_a_paso") or "1. Revisar los conceptos teóricos.\n2. Realizar las actividades formativas propuestas.\n3. Presentar los resultados obtenidos."
            for line in proc_text.split("\n"):
                line = line.strip()
                if line:
                    p_item = doc.add_paragraph()
                    p_item.paragraph_format.space_after = Pt(3)
                    p_item.add_run(line)

            add_docx_simple_teacher_signature(doc, teacher_name=data.get("teacher_name", "Docente"))

    elif doc_type == "examen_tecnico":
        questions = c_json.get("questions", [])
        total_pts = c_json.get("total_points", 20)

        if is_student:
            # Versión limpia de examen
            add_docx_heading(doc, f"Instrucciones Generales para la Evaluación ({total_pts} Puntos Totales)", level=1)
            p_inst = doc.add_paragraph()
            p_inst.paragraph_format.line_spacing = 1.15
            p_inst.add_run(
                "• Lea con detenimiento cada una de las preguntas antes de contestar.\n"
                "• Utilice letra legible y justifique sus respuestas en las preguntas de desarrollo técnico.\n"
                "• Mantenga el orden, la limpieza y evite el uso de corrector en la hoja de respuestas.\n"
                f"• Tiempo límite para la resolución: {data['duration']} minutos."
            )

            add_docx_heading(doc, "Cuestionario Técnico Escrito y Práctico", level=1)

            if questions and isinstance(questions, list):
                for q in questions:
                    q_num = q.get("numero") or q.get("number") or 1
                    q_pts = q.get("puntaje") or q.get("points") or 4
                    q_stmt = q.get("enunciado") or q.get("statement") or "Pregunta técnica de taller."
                    q_opts = q.get("opciones") or q.get("options") or []

                    p_q = doc.add_paragraph()
                    p_q.paragraph_format.space_before = Pt(8)
                    p_q.paragraph_format.space_after = Pt(3)
                    p_q.paragraph_format.keep_with_next = True
                    r_num = p_q.add_run(f"Pregunta {q_num}. ")
                    r_num.bold = True
                    r_num.font.color.rgb = RGBColor(139, 0, 0)
                    r_pts = p_q.add_run(f"[{q_pts} Puntos]\n")
                    r_pts.bold = True
                    r_pts.font.size = Pt(9)
                    r_pts.font.color.rgb = RGBColor(100, 116, 139)
                    p_q.add_run(q_stmt)

                    if q_opts:
                        for opt in q_opts:
                            p_opt = doc.add_paragraph()
                            p_opt.paragraph_format.left_indent = Inches(0.3)
                            p_opt.paragraph_format.space_before = Pt(1)
                            p_opt.paragraph_format.space_after = Pt(1)
                            p_opt.add_run(f"(   )  {opt}")
                    else:
                        p_lines = doc.add_paragraph()
                        p_lines.paragraph_format.left_indent = Inches(0.2)
                        p_lines.paragraph_format.space_before = Pt(3)
                        p_lines.paragraph_format.space_after = Pt(6)
                        p_lines.add_run("Respuesta / Desarrollo Técnico:\n")
                        p_lines.add_run("_________________________________________________________________________________\n")
                        p_lines.add_run("_________________________________________________________________________________")
            else:
                # Renderizar estructuradamente desde markdown si no hay questions array en JSON
                render_markdown_to_docx(doc, data["content_markdown"])

            add_docx_rubric_table(doc, total_pts=total_pts, topic=data["topic"])

        else:
            # Solucionario docente confidencial
            add_docx_heading(doc, f"Guía de Corrección y Clave Docente Justificada ({total_pts} Puntos)", level=1)

            if questions and isinstance(questions, list):
                for q in questions:
                    q_num = q.get("numero") or q.get("number") or 1
                    q_pts = q.get("puntaje") or q.get("points") or 4
                    q_stmt = q.get("enunciado") or q.get("statement") or "Pregunta técnica."
                    q_ans = q.get("respuesta_correcta") or q.get("correct_answer") or "Respuesta oficial según norma técnica."
                    q_just = q.get("justificacion") or q.get("justification") or "Justificación basada en el marco curricular de EPT."
                    q_crit = q.get("criterio_evaluacion") or f"Dominio técnico y seguridad en {data['topic']}."

                    add_docx_heading(doc, f"Ítem {q_num} [{q_pts} Pts] — Criterio: {q_crit}", level=2)
                    p_enun = doc.add_paragraph()
                    p_enun.add_run(f"Enunciado: {q_stmt}").italic = True

                    # Cuadro destacado con respuesta y justificación
                    tbl_ans = doc.add_table(rows=1, cols=1)
                    tbl_ans.alignment = WD_TABLE_ALIGNMENT.CENTER
                    c_ans = tbl_ans.cell(0, 0)
                    c_ans.width = Inches(6.56)
                    set_cell_background_color(c_ans, "FEF9C3")  # Amarillo claro
                    set_cell_margins(c_ans, top=80, bottom=80, left=120, right=120)
                    p_c = c_ans.paragraphs[0]
                    r_ans_t = p_c.add_run("✔ Respuesta Correcta:\n")
                    r_ans_t.bold = True
                    r_ans_t.font.color.rgb = RGBColor(180, 83, 9)
                    p_c.add_run(f"{q_ans}\n\n")

                    r_just_t = p_c.add_run("💡 Justificación Pedagógica y Técnica:\n")
                    r_just_t.bold = True
                    r_just_t.font.color.rgb = RGBColor(30, 41, 59)
                    p_c.add_run(f"{q_just}\n\n")

                    r_crit_t = p_c.add_run("⚖ Ponderación Parcial Sugerida:\n")
                    r_crit_t.bold = True
                    p_c.add_run(f"• Procedimiento y resultado exacto: {q_pts} pts (100%)\n")
                    p_c.add_run(f"• Planteamiento adecuado con error aritmético menor: {max(1, q_pts//2)} pts (50%)\n")
                    p_c.add_run("• Procedimiento incorrecto o sin sustento técnico: 0 pts")

                    doc.add_paragraph()
            else:
                render_markdown_to_docx(doc, data["content_markdown"])

            add_docx_rubric_table(doc, total_pts=total_pts, topic=data["topic"])
            add_docx_signatures_block(doc)

    else:
        # Renderizado profesional de documentos pedagógicos estructurados desde Markdown
        # (Fichas de trabajo, guías de estudio, prácticas de ejercicios, presentaciones, rúbricas)
        render_markdown_to_docx(doc, data["content_markdown"])

        # Solo si es específicamente rúbrica y no tiene tabla incorporada
        if doc_type == "rubrica_evaluacion" and "|" not in data["content_markdown"]:
            add_docx_rubric_table(doc, total_pts=20, topic=data["topic"])

        # Bloque oficial de firmas institucionales al cierre del documento
        add_docx_institutional_3_signatures(
            doc,
            specialty=data["specialty"],
            teacher_name=data.get("teacher_name", "Docente Responsable")
        )

    # Compilación en memoria
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# =============================================================================
# EXPORTACIÓN PDF — ALTA RESOLUCIÓN Y VALIDADO (REPORTLAB)
# =============================================================================

def build_pdf_styles():
    """Construye hoja de estilos tipográficos ReportLab."""
    styles = getSampleStyleSheet()

    # Normal modificado
    styles['Normal'].textColor = colors.HexColor(f"#{COLOR_SECONDARY_HEX}")
    styles['Normal'].fontSize = 9.5
    styles['Normal'].leading = 13.5
    styles['Normal'].fontName = "Helvetica"

    # Estilos institucionales personalizados
    styles.add(ParagraphStyle(
        name='InstHeaderCountry',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#FEE2E2")
    ))

    styles.add(ParagraphStyle(
        name='InstHeaderName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.white
    ))

    styles.add(ParagraphStyle(
        name='InstHeaderLema',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#FEF08A")
    ))

    styles.add(ParagraphStyle(
        name='InstHeaderDocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.white
    ))

    styles.add(ParagraphStyle(
        name='SectionHeading1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor(f"#{COLOR_PRIMARY_HEX}"),
        spaceBefore=12,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name='SectionHeading2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor(f"#{COLOR_SECONDARY_HEX}"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name='MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor(f"#{COLOR_SECONDARY_HEX}")
    ))

    styles.add(ParagraphStyle(
        name='MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor(f"#{COLOR_SECONDARY_HEX}")
    ))

    styles.add(ParagraphStyle(
        name='BodyJustified',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        alignment=TA_JUSTIFY,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name='CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#78350F")
    ))

    styles.add(ParagraphStyle(
        name='CalloutTextDocente',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E3A8A")
    ))

    styles.add(ParagraphStyle(
        name='TableHeadCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.white
    ))

    styles.add(ParagraphStyle(
        name='TableBodyCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor(f"#{COLOR_SECONDARY_HEX}")
    ))

    return styles


def create_pdf_header_table(title: str, subtitle: str, styles, is_confidential: bool = False) -> Table:
    """Construye tabla de membrete institucional auténtica con los dos logotipos oficiales CET N.º 34."""
    logo_gear_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "logo_inei34.png"))
    logo_bee_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "insignia.png"))
    if not os.path.exists(logo_gear_path):
        logo_gear_path = os.path.abspath(os.path.join("app", "static", "imagen", "logo_inei34.png"))
    if not os.path.exists(logo_bee_path):
        logo_bee_path = os.path.abspath(os.path.join("app", "static", "imagen", "insignia.png"))

    from reportlab.platypus import Image as ReportLabImage
    has_logos = os.path.exists(logo_gear_path) and os.path.exists(logo_bee_path)

    if has_logos:
        try:
            img_gear = ReportLabImage(logo_gear_path, width=22*mm, height=22*mm)
            img_bee = ReportLabImage(logo_bee_path, width=22*mm, height=22*mm)
            cap_style = ParagraphStyle('CapHead', parent=styles['Normal'], alignment=TA_CENTER, fontSize=6.5, leading=8, fontName='Helvetica-Bold', textColor=colors.HexColor("#8B0000"))
            cell_l = [img_gear, Spacer(1, 1*mm), Paragraph("R.M. Nº 2296-57", cap_style)]
            cell_r = [img_bee, Spacer(1, 1*mm), Paragraph("CHANCAY", cap_style)]

            tit_col = "#7C2D12" if is_confidential else "#8B0000"
            cnt_text = f"""
            <font size="9" color="{tit_col}"><b>INSTITUCIÓN EDUCATIVA PÚBLICA TÉCNICA Nº 34 (CET 34)</b></font><br/>
            <font size="6.5" color="#475569">"Honradez - Disciplina - Trabajo" • R.M. Nº 2296-57 • Cód. Modular: 0245621-0<br/>
            GOBIERNO REGIONAL DE LIMA • UGEL Nº 10 - HUARAL • CHANCAY</font><br/>
            <font size="9.5" color="#0F172A"><b>{xml_escape(title.upper())}</b></font><br/>
            <font size="7.5" color="{tit_col}"><b>{xml_escape(subtitle)}</b></font>
            """
            cell_c = Paragraph(cnt_text, ParagraphStyle('CntHead', parent=styles['Normal'], alignment=TA_CENTER, fontName='Helvetica', leading=10.5))

            header_table = Table([[cell_l, cell_c, cell_r]], colWidths=[24 * mm, 122 * mm, 24 * mm])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor(tit_col)),
            ]))
            return header_table
        except Exception as e:
            logger.warning(f"Fallback en create_pdf_header_table: {e}")

    p_country = Paragraph(f"{INSTITUTION_COUNTRY}<br/>{INSTITUTION_DRE}", styles['InstHeaderCountry'])
    p_name = Paragraph(INSTITUTION_NAME, styles['InstHeaderName'])
    p_lema = Paragraph(INSTITUTION_LEMA, styles['InstHeaderLema'])
    p_title = Paragraph(f"<b>{xml_escape(title.upper())}</b><br/><font size='8.5' color='#FEF08A'>{xml_escape(subtitle)}</font>", styles['InstHeaderDocTitle'])

    cell_content = [p_country, Spacer(1, 2*mm), p_name, Spacer(1, 1*mm), p_lema, Spacer(1, 2*mm), p_title]
    header_table = Table([[cell_content]], colWidths=[170 * mm])
    bg_color = colors.HexColor(f"#{COLOR_PRIMARY_HEX}") if not is_confidential else colors.HexColor("#7C2D12")
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return header_table


def create_pdf_worksheet_header_table(data: Dict[str, Any], styles) -> Table:
    """
    Construye la tabla de membrete institucional auténtica para Fichas de Aprendizaje CET N.º 34.
    Fiel réplica de la Tabla 0 de ficha_trabajo_estudiante_cet34.docx (4 filas):
    Fila 0: [Logo / Escudo] | INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY / Área | FICHA DE APRENDIZAJE / Grado
    Fila 1: “Título / Tema”
    Fila 2: Estudiante: _____________________________________ | Grado y sección | Fecha: ____ / ____ / 2026
    Fila 3: Docente: [Docente Responsable]
    """
    t_name = data.get("teacher_name") or "[Docente Responsable - Por completar]"
    grade = data.get("grade") or 1
    section = data.get("section") or data.get("section_name") or "A"
    specialty = data.get("specialty") or "Educación para el Trabajo"
    topic = data.get("topic") or data.get("title") or "Ficha de Aprendizaje"
    date_str = data.get("date") or "____ / ____ / 2026"

    logo_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "logo_inei34.png"))
    logo_cell = ""
    if os.path.exists(logo_path):
        try:
            from reportlab.platypus import Image as ReportLabImage
            logo_cell = ReportLabImage(logo_path, width=20*mm, height=20*mm)
        except Exception:
            logo_cell = Paragraph("<b>CET N.° 34</b>", styles['Normal'])
    else:
        logo_cell = Paragraph("<b>CET N.° 34<br/>CHANCAY</b>", ParagraphStyle('LogoTxt', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, fontName='Helvetica-Bold'))

    head_title = Paragraph(f"<b>INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY</b><br/><font size='8' color='#475569'>Área: {xml_escape(specialty)}</font>", ParagraphStyle('WH1', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8.5, fontName='Helvetica-Bold', leading=10))
    head_type = Paragraph(f"<b>FICHA DE APRENDIZAJE</b><br/><font size='8' color='#475569'>{grade}.° de Secundaria</font>", ParagraphStyle('WH2', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8.5, fontName='Helvetica-Bold', leading=10))

    row0 = [logo_cell, head_title, head_type]
    
    topic_cell = Paragraph(f"<b>“{xml_escape(topic)}”</b>", ParagraphStyle('WHTopic', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9.5, fontName='Helvetica-Bold', textColor=colors.HexColor("#0F172A")))
    row1 = [topic_cell, "", ""]

    est_cell = Paragraph("<b>Estudiante:</b> _____________________________________", ParagraphStyle('WHEst', parent=styles['Normal'], fontSize=8))
    sec_cell = Paragraph(f"<b>Grado y sección:</b> {grade}.° “{xml_escape(str(section))}”", ParagraphStyle('WHSec', parent=styles['Normal'], fontSize=8))
    fec_cell = Paragraph(f"<b>Fecha:</b> {xml_escape(date_str)}", ParagraphStyle('WHFec', parent=styles['Normal'], fontSize=8))
    row2 = [est_cell, sec_cell, fec_cell]

    doc_cell = Paragraph(f"<b>Docente:</b> {xml_escape(t_name)}", ParagraphStyle('WHDoc', parent=styles['Normal'], fontSize=8))
    row3 = [doc_cell, "", ""]

    tbl = Table([row0, row1, row2, row3], colWidths=[26*mm, 94*mm, 50*mm])
    tbl.setStyle(TableStyle([
        ('SPAN', (0, 1), (2, 1)),
        ('SPAN', (0, 3), (2, 3)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F1F5F9")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tbl


def create_pdf_metadata_table(data: Dict[str, Any], styles) -> Table:
    """Crea tabla de datos informativos en ReportLab."""
    rows = [
        [
            Paragraph("<b>Área / Especialidad:</b>", styles['MetaLabel']),
            Paragraph(xml_escape(str(data["specialty"])), styles['MetaValue']),
            Paragraph("<b>Grado y Sección:</b>", styles['MetaLabel']),
            Paragraph(f"{data['grade']}° Sec. - Secc. {xml_escape(str(data['section']))}", styles['MetaValue'])
        ],
        [
            Paragraph("<b>Duración Estimada:</b>", styles['MetaLabel']),
            Paragraph(f"{data['duration']} minutos", styles['MetaValue']),
            Paragraph("<b>Año Escolar:</b>", styles['MetaLabel']),
            Paragraph("2026 — Modalidad EPT/CNEB", styles['MetaValue'])
        ],
        [
            Paragraph("<b>Tema Técnico:</b>", styles['MetaLabel']),
            Paragraph(xml_escape(str(data["topic"])), styles['MetaValue']),
            Paragraph("<b>Docente Titular:</b>", styles['MetaLabel']),
            Paragraph(xml_escape(str(data.get("teacher_name") or "Prof. Responsable de Taller")), styles['MetaValue'])
        ]
    ]

    tbl = Table(rows, colWidths=[36 * mm, 49 * mm, 36 * mm, 49 * mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return tbl


def create_pdf_student_identification_box(styles, total_pts: int = 20) -> Table:
    """Crea recuadro formal de identificación de estudiante en PDF."""
    p_name = Paragraph("<b>APELLIDOS Y NOMBRES:</b> ____________________________________________________", styles['Normal'])
    p_score = Paragraph(f"<b>CALIFICACIÓN</b><br/><font size='10' color='#8B0000'><b>[ _____ / {total_pts} pts ]</b></font>", ParagraphStyle('CScore', parent=styles['Normal'], alignment=TA_CENTER))
    p_meta = Paragraph("<b>GRADO Y SECCIÓN:</b> _______________   <b>FECHA:</b> _______________   <b>FIRMA:</b> ____________", styles['Normal'])
    p_scale = Paragraph("<font size='7.5'>ESCALA MINISTERIAL<br/>( AD - A - B - C )</font>", ParagraphStyle('CScale', parent=styles['Normal'], alignment=TA_CENTER))

    data = [
        [p_name, p_score],
        [p_meta, p_scale]
    ]

    tbl = Table(data, colWidths=[130 * mm, 40 * mm])
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.7, colors.HexColor(f"#{COLOR_PRIMARY_HEX}")),
        ('BACKGROUND', (1, 0), (1, 1), colors.HexColor("#F8FAFC")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return tbl


def create_pdf_callout(text: str, title: str, styles, is_warning: bool = False) -> Table:
    """Crea caja de advertencia o llamada en PDF evitando doble escape y caracteres incompatibles."""
    tit_color = "#B45309" if is_warning else "#1D4ED8"
    bg_color = colors.HexColor(f"#{COLOR_WARNING_BG_HEX.lstrip('#')}" if is_warning else "#EFF6FF")
    border_color = colors.HexColor(f"#{COLOR_WARNING_BORDER_HEX.lstrip('#')}" if is_warning else "#60A5FA")

    clean_text = (
        str(text or "")
        .replace("📌", "■ ")
        .replace("✔", "[OK] ")
        .replace("💡", "[Nota] ")
        .replace("⚖", "[Criterio] ")
        .replace("⚠️", "[Aviso] ")
    )

    # Si el texto ya contiene etiquetas XML/HTML de ReportLab, no escapar las etiquetas
    if any(tag in clean_text for tag in ["<b", "<font", "<br", "<i>", "<color"]):
        formatted_body = clean_text
    else:
        formatted_body = xml_escape(clean_text)

    clean_title = xml_escape(str(title or "").replace("📌", "").replace("⚠️", "").strip())
    content = Paragraph(
        f"<b><font color='{tit_color}'>■ {clean_title}:</font></b> {formatted_body}",
        styles['CalloutText'] if is_warning else styles['CalloutTextDocente']
    )

    tbl = Table([[content]], colWidths=[170 * mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('BOX', (0, 0), (-1, -1), 1, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return tbl


def format_markdown_inline_for_xml(text: str) -> str:
    """Escapa texto plano a XML válido para ReportLab conservando negritas, cursivas y etiquetas semánticas."""
    if not text:
        return ""
    safe = xml_escape(str(text).strip())
    # Negrita **text** o __text__
    safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
    safe = re.sub(r'__(.+?)__', r'<b>\1</b>', safe)
    # Cursiva *text*
    safe = re.sub(r'(?<!\*)\*([^\*]+?)\*(?!\*)', r'<i>\1</i>', safe)
    # Código en línea `code`
    safe = re.sub(r'`([^`]+?)`', r'<font face="Courier" color="#1E293B"><b>\1</b></font>', safe)
    safe = safe.replace("\n", "<br/>")
    return safe


def _parse_and_append_pdf_table(story, styles, table_lines: List[str]):
    """Parsea líneas de tabla markdown (| col1 | col2 |) y las agrega como Table formal a ReportLab story."""
    if not table_lines:
        return
    parsed_rows = []
    for line in table_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        parts = [p.strip() for p in line_clean.split('|')]
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        if not parts:
            continue
        if all(re.match(r'^:?-+:?$', p) for p in parts if p):
            continue
        parsed_rows.append(parts)

    if not parsed_rows:
        return

    num_cols = max(len(r) for r in parsed_rows)
    for r in parsed_rows:
        while len(r) < num_cols:
            r.append('')

    total_w = 170.0
    col_w = (total_w / num_cols) * mm
    col_widths = [col_w] * num_cols

    table_data = []
    for r_idx, r in enumerate(parsed_rows):
        row_cells = []
        is_hdr = (r_idx == 0)
        st = styles['TableHeadCell'] if is_hdr else styles['TableBodyCell']
        for c in r:
            xml_c = format_markdown_inline_for_xml(c)
            row_cells.append(Paragraph(xml_c, st))
        table_data.append(row_cells)

    tbl = Table(table_data, colWidths=col_widths)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    for r_idx in range(1, len(parsed_rows)):
        if r_idx % 2 == 1:
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#F8FAFC")))
    tbl.setStyle(TableStyle(t_style))
    story.append(tbl)
    story.append(Spacer(1, 3 * mm))


def render_markdown_to_pdf_story(story: list, styles: dict, markdown_text: str):
    """Interpreta y renderiza un documento Markdown completo en elementos ReportLab (párrafos, títulos, listas, tablas)."""
    if not markdown_text:
        return

    lines = markdown_text.splitlines()
    in_table = False
    table_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if line.startswith('|') and '|' in line[1:]:
            in_table = True
            table_lines.append(line)
            continue
        elif in_table:
            _parse_and_append_pdf_table(story, styles, table_lines)
            table_lines = []
            in_table = False

        if not line:
            story.append(Spacer(1, 1.5 * mm))
            continue

        if re.match(r'^[-*_]{3,}$', line):
            story.append(Spacer(1, 2 * mm))
            continue

        if line.startswith('# '):
            story.append(Paragraph(format_markdown_inline_for_xml(line[2:]), styles['SectionHeading1']))
            story.append(Spacer(1, 1.5 * mm))
        elif line.startswith('## '):
            story.append(Paragraph(format_markdown_inline_for_xml(line[3:]), styles['SectionHeading2']))
            story.append(Spacer(1, 1.5 * mm))
        elif line.startswith('### ') or line.startswith('#### '):
            clean_title = re.sub(r'^#+\s*', '', line)
            story.append(Paragraph(f"<b>{format_markdown_inline_for_xml(clean_title)}</b>", styles['SectionHeading2']))
            story.append(Spacer(1, 1 * mm))
        elif line.startswith('> '):
            story.append(create_pdf_callout(format_markdown_inline_for_xml(line[2:]), "ORIENTACIÓN PEDAGÓGICA", styles=styles, is_warning=False))
            story.append(Spacer(1, 2 * mm))
        elif re.match(r'^[-*•]\s+', line):
            clean_item = re.sub(r'^[-*•]\s+', '', line)
            story.append(Paragraph(f"• {format_markdown_inline_for_xml(clean_item)}", styles['BodyJustified']))
        elif re.match(r'^\d+[\.\)]\s+', line):
            num_match = re.match(r'^(\d+[\.\)])\s+(.*)$', line)
            if num_match:
                prefix, rest = num_match.group(1), num_match.group(2)
                story.append(Paragraph(f"<b>{prefix}</b> {format_markdown_inline_for_xml(rest)}", styles['BodyJustified']))
            else:
                story.append(Paragraph(format_markdown_inline_for_xml(line), styles['BodyJustified']))
        else:
            story.append(Paragraph(format_markdown_inline_for_xml(line), styles['BodyJustified']))

    if in_table and table_lines:
        _parse_and_append_pdf_table(story, styles, table_lines)


def create_pdf_simple_teacher_signature(styles, teacher_name: str = "Docente Responsable") -> Table:
    """Pie de firma simple y formal del docente responsable para fichas de trabajo y sesiones libres."""
    clean_name = (teacher_name or "Docente Responsable").strip()
    if not any(clean_name.startswith(pfx) for pfx in ["Prof.", "Lic.", "Mg.", "Dr.", "Ing."]):
        clean_name = f"Prof. {clean_name}"

    p = Paragraph(
        f"_________________________________________<br/>"
        f"<b>{xml_escape(clean_name)}</b><br/>"
        f"<font size='7.5'>Docente Responsable | I.E. INEI N.º 34</font>",
        ParagraphStyle('SimpleSig', parent=styles['Normal'], alignment=TA_CENTER)
    )
    tbl = Table([[p]], colWidths=[170 * mm])
    tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
    ]))
    return tbl


def create_pdf_rubric_table(styles, total_pts: int = 20, topic: str = "Taller", custom_criteria: Optional[List[Dict[str, Any]]] = None, session_type: Optional[str] = None, is_landscape: bool = False) -> Table:
    """Crea tabla de rúbrica analítica CNEB en ReportLab pertinente según la especialidad y propósito evaluado."""
    headers = [
        Paragraph("<b>Criterio de Evaluación</b>", styles['TableHeadCell']),
        Paragraph(f"<b>AD: Destacado</b><br/>({int(total_pts*0.9)}-{total_pts} pts)", styles['TableHeadCell']),
        Paragraph(f"<b>A: Esperado</b><br/>({int(total_pts*0.7)}-{int(total_pts*0.9)-1} pts)", styles['TableHeadCell']),
        Paragraph(f"<b>B: En Proceso</b><br/>({int(total_pts*0.55)}-{int(total_pts*0.7)-1} pts)", styles['TableHeadCell']),
        Paragraph(f"<b>C: En Inicio</b><br/>(0-{int(total_pts*0.55)-1} pts)", styles['TableHeadCell'])
    ]

    rows_data = []
    if custom_criteria and isinstance(custom_criteria, list) and len(custom_criteria) > 0:
        for r_idx, c_item in enumerate(custom_criteria, start=1):
            crit_name = c_item.get("criterio") or f"Criterio {r_idx}"
            ad_desc = c_item.get("ad") or "Demuestra dominio sobresaliente y autonomía en el criterio evaluado."
            a_desc = c_item.get("a") or "Cumple satisfactoriamente con los desempeños esperados del criterio."
            b_desc = c_item.get("b") or "Muestra avances parciales requiriendo retroalimentación pedagógica."
            c_desc = c_item.get("c") or "Dificultades notorias para alcanzar el nivel básico del criterio."
            rows_data.append([f"{r_idx}. {crit_name}", ad_desc, a_desc, b_desc, c_desc])
    elif session_type == "emprendimiento" or any(k in (topic or "").lower() for k in ["lean canvas", "emprendimiento", "negocio", "canvas", "startup"]):
        rows_data = [
            [
                "1. Formulación y Validación de Hipótesis en Lean Canvas",
                "Formula hipótesis precisas y contrasta con evidencias empíricas sólidas los 9 bloques del Lean Canvas de su proyecto.",
                "Modifica y valida las hipótesis principales del Lean Canvas (problema, solución, propuesta de valor y canales).",
                "Presenta hipótesis generales con escasa contrastación o validación superficial con clientes.",
                "No formula hipótesis medibles ni valida los supuestos de su modelo de negocio."
            ],
            [
                "2. Iteración y Adaptación del Modelo según el Cliente",
                "Itera con agilidad y criterio comercial la propuesta de valor incorporando retroalimentación real de usuarios.",
                "Realiza ajustes pertinentes en el lienzo respondiendo a las necesidades observadas en los clientes.",
                "Muestra resistencia a modificar su idea original a pesar de las evidencias recopiladas.",
                "No realiza adaptaciones en el Lean Canvas o no considera la opinión de los usuarios."
            ],
            [
                "3. Sustentación de Aprendizajes y Trabajo en Equipo",
                "Sustenta con claridad técnica y convicción la viabilidad de su propuesta, demostrando liderazgo cooperativo.",
                "Expone con argumentos válidos las decisiones del equipo y la viabilidad de la propuesta emprendedora.",
                "Participa en la sustentación con argumentos limitados sobre la viabilidad comercial.",
                "No sustenta los cambios realizados en el lienzo ni demuestra articulación con su equipo."
            ]
        ]
    elif session_type == "tecnica" or any(k in (topic or "").lower() for k in ["taller", "gtz", "mecaniz", "torno", "soldad", "circuit", "motor"]):
        rows_data = [
            [
                f"1. Dominio Conceptual y Fundamento Técnico de {topic}",
                "Explica principios con lenguaje técnico riguroso y sustenta todas sus respuestas con exactitud.",
                "Responde con claridad la mayoría de conceptos técnicos requeridos por la especialidad.",
                "Presenta dudas en conceptos clave o definiciones técnicas elementales de taller.",
                "No identifica los conceptos técnicos fundamentales de la especialidad."
            ],
            [
                "2. Procedimiento Técnico y Operaciones Prácticas",
                "Resuelve operaciones y maniobras con óptima precisión, tolerancias y uso racional de recursos.",
                "Desarrolla procedimientos técnicos correctos con desviaciones menores admisibles.",
                "Requiere asistencia continua para completar la secuencia técnica u operativa.",
                "Incumple el procedimiento técnico y comete errores críticos de operación."
            ],
            [
                "3. Seguridad Industrial, Uso de EPP y Metodología 5S",
                "Aplica proactivamente el protocolo 5S, porta el EPP reglamentario y previene riesgos de taller.",
                "Porta el EPP requerido e identifica las normas de seguridad aplicables a la tarea.",
                "Omite recomendaciones secundarias de seguridad o desatiende el orden en su puesto.",
                "Incurre en conductas inseguras de taller o no porta el EPP obligatorio."
            ]
        ]
    else:
        rows_data = [
            [
                f"1. Comprensión y Aplicación de Capacidades en {topic}",
                "Demuestra dominio conceptual y procedimental sobresaliente al resolver situaciones problemáticas.",
                "Aplica adecuadamente los conceptos y procedimientos formativos según los propósitos establecidos.",
                "Aplica conceptos con dudas menores, requiriendo apoyo pedagógico guiado.",
                "Dificultades evidentes para comprender y aplicar las nociones básicas del área."
            ],
            [
                "2. Estrategias de Resolución y Calidad de la Evidencia",
                "Desarrolla estrategias autónomas, creativas y fundamentadas para alcanzar la evidencia con alta calidad.",
                "Sigue la secuencia de actividades planificada completando la evidencia de aprendizaje requerida.",
                "Completa parcialmente las actividades o presenta evidencias con omisiones secundarias.",
                "No completa las actividades formativas o no presenta la evidencia solicitada."
            ],
            [
                "3. Reflexión Metacognitiva y Trabajo Autónomo",
                "Evalúa críticamente sus aciertos y errores, proponiendo acciones de mejora y autorregulación.",
                "Reconoce sus avances y dificultades, respondiendo con pertinencia a las preguntas metacognitivas.",
                "Identifica sus dificultades solo con la mediación directa del docente.",
                "Muestra escaso interés en evaluar su propio proceso formativo."
            ]
        ]

    table_rows = [headers]
    for r_vals in rows_data:
        crit_p = Paragraph(f"<b>{xml_escape(r_vals[0])}</b>", styles['TableBodyCell'])
        ad_p = Paragraph(xml_escape(r_vals[1]), styles['TableBodyCell'])
        a_p = Paragraph(xml_escape(r_vals[2]), styles['TableBodyCell'])
        b_p = Paragraph(xml_escape(r_vals[3]), styles['TableBodyCell'])
        c_p = Paragraph(xml_escape(r_vals[4]), styles['TableBodyCell'])
        table_rows.append([crit_p, ad_p, a_p, b_p, c_p])

    col_widths = [57 * mm, 50 * mm, 50 * mm, 50 * mm, 50 * mm] if is_landscape else [42 * mm, 32 * mm, 32 * mm, 32 * mm, 32 * mm]
    tbl = Table(table_rows, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor("#F8FAFC")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return tbl


def create_pdf_checklist_table(styles, criteria: Optional[List[Any]] = None, topic: str = "la actividad") -> Table:
    """Crea la tabla oficial de Lista de Cotejo institucional (4 columnas) para Fichas de Aprendizaje CET N.º 34."""
    head_center = ParagraphStyle('CheckHeadCenter', parent=styles['TableHeadCell'], alignment=TA_CENTER)
    headers = [
        Paragraph("<b>Criterio de Evaluación / Indicador</b>", styles['TableHeadCell']),
        Paragraph("<b>Sí</b>", head_center),
        Paragraph("<b>En proceso</b>", head_center),
        Paragraph("<b>Evidencia / Comentario</b>", styles['TableHeadCell'])
    ]

    rows_data = []
    if criteria and isinstance(criteria, list) and len(criteria) > 0:
        for c in criteria:
            if isinstance(c, dict):
                crit_txt = (c.get("criterio") or c.get("name") or str(c)).strip()
                evid_txt = (c.get("evidencia") or c.get("recomendacion") or c.get("comentario") or "").strip()
            else:
                crit_txt = str(c).strip()
                evid_txt = ""
            if crit_txt:
                rows_data.append((crit_txt, evid_txt))

    if not rows_data:
        rows_data = [
            (f"Comprendo y explico con precisión los conceptos y operaciones fundamentales de {topic}.", f"Evidencia de {topic}"),
            (f"Aplico procedimientos técnicos seguros y sigo las pautas metodológicas de {topic}.", f"Evidencia de {topic}"),
            (f"Propongo mejoras técnicas u optimizaciones documentadas en el desarrollo de {topic}.", f"Evidencia de {topic}")
        ]

    cell_center = ParagraphStyle('CheckCellCenter', parent=styles['TableBodyCell'], alignment=TA_CENTER)
    table_rows = [headers]
    for c_text, evid_text in rows_data:
        p_crit = Paragraph(xml_escape(c_text), styles['TableBodyCell'])
        p_si = Paragraph("[ &nbsp;&nbsp; ]", cell_center)
        p_proc = Paragraph("[ &nbsp;&nbsp; ]", cell_center)
        p_evid = Paragraph(xml_escape(evid_text), styles['TableBodyCell'])
        table_rows.append([p_crit, p_si, p_proc, p_evid])

    tbl = Table(table_rows, colWidths=[95 * mm, 18 * mm, 22 * mm, 35 * mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor("#FFFFFF")),
        ('BACKGROUND', (1, 1), (2, -1), colors.HexColor("#F8FAFC")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return tbl


def create_pdf_signatures_block(styles) -> Table:
    """Bloque de firmas institucional para ReportLab."""
    p1 = Paragraph("_________________________________________<br/><b>PROFESOR DE ESPECIALIDAD / AULA</b><br/><font size='7.5'>Docente Titular de Taller</font>", ParagraphStyle('Sig1', parent=styles['Normal'], alignment=TA_CENTER))
    p2 = Paragraph(f"_________________________________________<br/><b>V.° B.° COORDINACIÓN / DIRECCIÓN</b><br/><font size='7.5'>{INSTITUTION_NAME}</font>", ParagraphStyle('Sig2', parent=styles['Normal'], alignment=TA_CENTER))

    tbl = Table([[p1, p2]], colWidths=[85 * mm, 85 * mm])
    tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
    ]))
    return tbl


def create_pdf_institutional_3_signatures(styles, teacher_name: str = "Docente", specialty: str = "Taller", is_landscape: bool = False) -> Table:
    """Bloque oficial de 3 firmas reglamentarias para ReportLab en la I.E. CET N° 34 / INEI N° 34."""
    from app.ai.template_engine import template_engine
    is_verified, clean_teacher = template_engine.resolve_verified_teacher(teacher_name)
    doc_display = clean_teacher if is_verified else "[Pendiente de completar]"

    spec_l = specialty.lower()
    if "comput" in spec_l or "inform" in spec_l:
        jefe_name = "Mg. Luis Arturo La Rosa Gallardo"
        jefe_cargo = "JEFE DE TALLER COMPUTACIÓN E INFORMÁTICA"
    else:
        jefe_name = "Jefe de Taller de Especialidad"
        jefe_cargo = f"JEFE DE TALLER {specialty.upper()[:25]}"

    rule_str = "_________________________________________" if is_landscape else "____________________________"
    p1 = Paragraph(
        f"{rule_str}<br/><b>DOCENTE RESPONSABLE</b><br/><font size='7.5'>{xml_escape(doc_display)}<br/>Docente de Especialidad / Aula</font>",
        ParagraphStyle('Sig1', parent=styles['Normal'], alignment=TA_CENTER)
    )
    p2 = Paragraph(
        f"{rule_str}<br/><b>JEFE DE TALLER</b><br/><font size='7.5'>{xml_escape(jefe_name)}<br/>{xml_escape(jefe_cargo)}</font>",
        ParagraphStyle('Sig2', parent=styles['Normal'], alignment=TA_CENTER)
    )
    p3 = Paragraph(
        f"{rule_str}<br/><b>SUB-DIRECTOR ÁREA TÉCNICA</b><br/><font size='7.5'>Mg. Javier Eulogio Rosas Maguiña<br/>I.E. CET N° 34 - Chancay</font>",
        ParagraphStyle('Sig3', parent=styles['Normal'], alignment=TA_CENTER)
    )

    col_widths = [85 * mm, 85 * mm, 85 * mm] if is_landscape else [56 * mm, 56 * mm, 56 * mm]
    tbl = Table([[p1, p2, p3]], colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
    ]))
    return tbl


def create_pdf_session_gtz_table(styles, gtz_steps: list, is_landscape: bool = False) -> Table:
    """Crea tabla PDF de 4 columnas para Acción Completa GTZ (168 mm total)."""
    headers = [
        Paragraph("<b>Pasos o etapas</b>", styles['TableHeadCell']),
        Paragraph("<b>Tiempo</b>", styles['TableHeadCell']),
        Paragraph("<b>Acciones o actividades del docente</b>", styles['TableHeadCell']),
        Paragraph("<b>Acciones o actividades del estudiante</b>", styles['TableHeadCell'])
    ]
    rows = [headers]

    for step in gtz_steps:
        paso_nom = step.get("paso", "")
        tiempo_str = step.get("tiempo", "")
        act_doc = step.get("actividad_docente", "")
        act_est = step.get("actividad_estudiante", "")

        rows.append([
            Paragraph(f"<b>{xml_escape(paso_nom)}</b>", styles['TableBodyCell']),
            Paragraph(xml_escape(tiempo_str), ParagraphStyle('TCell', parent=styles['TableBodyCell'], alignment=TA_CENTER)),
            Paragraph(sanitize_text_for_xml(act_doc), styles['TableBodyCell']),
            Paragraph(sanitize_text_for_xml(act_est), styles['TableBodyCell'])
        ])

    col_widths = [36 * mm, 22 * mm, 99.5 * mm, 99.5 * mm] if is_landscape else [24 * mm, 18 * mm, 64 * mm, 64 * mm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_SECONDARY_HEX}")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{COLOR_BORDER_HEX}")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tbl



def check_docx_to_pdf_converter() -> Optional[str]:
    """Comprueba si existe un conversor DOCX a PDF compatible disponible en el entorno."""
    import shutil
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return None


def convert_docx_bytes_to_pdf(docx_bytes: bytes) -> Optional[bytes]:
    """Convierte bytes de un archivo DOCX maestro a PDF usando el conversor disponible."""
    converter = check_docx_to_pdf_converter()
    if not converter:
        return None
    import subprocess
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            in_docx = os.path.join(tmp_dir, "documento_maestro.docx")
            with open(in_docx, "wb") as f:
                f.write(docx_bytes)
            cmd = [converter, "--headless", "--convert-to", "pdf", "--outdir", tmp_dir, in_docx]
            res = subprocess.run(cmd, capture_output=True, timeout=60)
            out_pdf = os.path.join(tmp_dir, "documento_maestro.pdf")
            if res.returncode == 0 and os.path.exists(out_pdf):
                with open(out_pdf, "rb") as f:
                    return f.read()
    except Exception as e:
        logger.warning(f"Error en conversión DOCX a PDF con {converter}: {e}")
    return None


def generate_pending_conversion_pdf(doc_data: Dict[str, Any]) -> bytes:
    """Genera documento PDF que identifica claramente el estado de conversión pendiente."""
    data = parse_document_data(doc_data)
    topic = data.get("topic") or data.get("title") or "Ficha de Aprendizaje"
    styles = build_pdf_styles()
    buf = io.BytesIO()
    pdf_doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm
    )
    story = [
        create_pdf_header_table(
            title="DOCUMENTO PEDAGÓGICO OFICIAL — CET N.º 34",
            subtitle="I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY",
            styles=styles,
            is_confidential=False
        ),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>{xml_escape(topic.upper())}</b>", styles['Title']),
        Spacer(1, 4 * mm),
        create_pdf_metadata_table(data, styles=styles),
        Spacer(1, 6 * mm),
        create_pdf_callout(
            text=(
                "El documento maestro ha sido generado y completado exitosamente en formato Microsoft Word (.docx) "
                "utilizando la plantilla institucional oficial <b>'ficha_trabajo_estudiante_cet34.docx'</b> con datos estructurados "
                "CNEB (Competencia oficial: Gestiona proyectos de emprendimiento económico o social, marco teórico, 3 actividades "
                "pedagógicas independientes y lista de cotejo de 4 columnas).<br/><br/>"
                "<b>CONVERSIÓN DIRECTA A PDF PENDIENTE:</b> En el servidor actual no se encuentra disponible un motor "
                "de conversión nativo (LibreOffice / soffice) para transformar archivos Word a PDF sin reconstruir el diseño.<br/><br/>"
                "<b>INSTRUCCIÓN DOCENTE:</b> Utilice y descargue el archivo oficial <b>Microsoft Word (.docx)</b> para su visualización, "
                "edición e impresión directa con el formato y membrete institucional 100% fieles."
            ),
            title="DOCUMENTO MAESTRO WORD (.DOCX) GENERADO — CONVERSIÓN PDF PENDIENTE",
            styles=styles,
            is_warning=True
        ),
        Spacer(1, 8 * mm),
        Paragraph("<b>Resumen de Contenido Validado en Documento Maestro (.docx):</b>", styles['SectionHeading1']),
        Spacer(1, 2 * mm),
        Paragraph(f"• <b>Competencia Curricular:</b> {xml_escape(data.get('competence', ''))}", styles['BodyJustified']),
        Paragraph(f"• <b>Propósito Formativo:</b> {xml_escape(data.get('purpose', ''))}", styles['BodyJustified']),
        Paragraph(f"• <b>Evidencia / Producto:</b> {xml_escape(data.get('evidence', ''))}", styles['BodyJustified']),
        Paragraph("• <b>Estructura Documental:</b> Membrete institucional oficial, situación de reto, marco teórico técnico, actividades prácticas 1, 2 y 3, actividad de extensión, ejercicios de consolidación, lista de cotejo (4 columnas) y metacognición.", styles['BodyJustified']),
        Spacer(1, 10 * mm),
        create_pdf_simple_teacher_signature(styles, teacher_name=data.get("teacher_name", "Docente"))
    ]
    pdf_doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


def generate_session_pdf_bytes(doc_data: Dict[str, Any]) -> bytes:
    """
    Genera un archivo PDF 100% idéntico al diseño oficial de Word (.docx) para la Sesión de Aprendizaje CET N.º 34:
    - Membrete oficial con los dos logotipos (Engranaje naranja y Abeja obrera).
    - I. DATOS GENERALES en tabla de 10 filas con dos puntos alineados.
    - II. PROPÓSITO DE LA SESIÓN.
    - III. CRITERIOS DE EVALUACIÓN.
    - IV. EVIDENCIAS DE APRENDIZAJE.
    - V. SITUACIÓN SIGNIFICATIVA (narrativa y retos en viñetas limpias).
    - VI. DESARROLLO DE LOS PROCESOS DIDÁCTICOS DE LA SESIÓN (Tabla GTZ de 4 columnas en orientación vertical).
    - VII. MATERIALES.
    - VIII. BIBLIOGRAFIA.
    - Firmas institucionales (Docente Responsable, Jefe de Taller, Sub-Director de Área Técnica).
    - Pie de página institucional sin menciones a IA.
    """
    data = parse_document_data(doc_data, target="teacher")
    c_json = data.get("content_json") or {}
    if isinstance(c_json, str):
        try:
            c_json = json.loads(c_json)
        except Exception:
            c_json = {}

    topic = data.get("topic") or data.get("title") or "Gestionamos carpeta digital"
    specialty = data.get("specialty") or "Educación para el Trabajo"
    clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "")
    grade = int(data.get("grade") or 1)
    grade_str = f"{grade}.° grado"
    section = data.get("section") or data.get("section_name") or "A"
    duration_min = int(data.get("duration") or data.get("duration_minutes") or 225)
    ped_hours = max(1, round(duration_min / 45))
    teacher_name = data.get("teacher_name") or "Prof. Roberto Bazán Palacios"
    subdirector_name = "Mg. Javier Eulogio Rosas Maguiña (Subdirector de Área Técnica)"
    jefe_taller_name = f"Mg. Luis Arturo La Rosa Gallardo (Jefe de Taller de {clean_spec})"

    is_digital = any(k in f"{topic} {clean_spec}".lower() for k in [
        "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
        "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
    ])

    props = c_json.get("propositos") if isinstance(c_json.get("propositos"), dict) else {}
    purpose_val = data.get("purpose") or props.get("proposito_formativo") or props.get("proposito") or (
        f"Comprender y aplicar criterios técnicos para organizar, clasificar, respaldar y gestionar carpetas y archivos digitales de manera estructurada y segura, optimizando el acceso y la conservación de la información en entornos locales y en la nube."
        if is_digital else
        f"Comprender y aplicar los principios y operaciones clave de {topic}, formulando soluciones prácticas y verificables."
    )
    criteria_val = c_json.get("criterios_evaluacion") or props.get("criterios_evaluacion") or (
        f"Organiza una carpeta digital aplicando criterios de estructura jerárquica, nombres adecuados, eliminación segura de duplicados y uso responsable del almacenamiento en la nube."
        if is_digital else
        f"Aplica destrezas técnicas en {topic} cumpliendo normas de seguridad y control de calidad."
    )
    evidence_val = c_json.get("evidencia_aprendizaje") or props.get("evidencia") or (
        f"Carpeta digital organizada y depurada que cumple los criterios de gestión de archivos y seguridad digital."
        if is_digital else
        f"Ficha de operaciones y producto técnico de {topic} verificado."
    )

    modulo_val = (
        c_json.get("datos_generales_oficiales", {}).get("modulo_formativo")
        or c_json.get("datos_generales", {}).get("modulo_formativo")
        or c_json.get("modulo_formativo")
        or (f"Aplica herramientas de productividad, almacenamiento y colaboración en la nube" if is_digital else f"Módulo formativo de {clean_spec}: {topic}")
    )
    metodo_val = (
        c_json.get("datos_generales_oficiales", {}).get("metodo_didactico")
        or c_json.get("datos_generales", {}).get("metodo_didactico")
        or "Aprendizaje por la acción completa (GTZ)"
    )
    fecha_val = data.get("date") or data.get("fecha") or "12 de octubre al 14 de octubre 2026"

    buf = io.BytesIO()
    pdf_doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    style_center_header = ParagraphStyle(
        'CenterHeaderSess', parent=styles['Normal'],
        alignment=TA_CENTER, fontName='Helvetica', leading=11
    )
    style_caption = ParagraphStyle(
        'CapSess', parent=styles['Normal'],
        alignment=TA_CENTER, fontSize=6.5, leading=8,
        fontName='Helvetica-Bold', textColor=colors.HexColor("#8B0000")
    )
    style_sec_title = ParagraphStyle(
        'SecTitleSess', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9.5, leading=13,
        textColor=colors.HexColor("#8B0000"),
        spaceBefore=7, spaceAfter=2.5, keepWithNext=True
    )
    style_body = ParagraphStyle(
        'BodyJustSess', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=11.5,
        alignment=TA_JUSTIFY, textColor=colors.HexColor("#1E293B"),
        spaceAfter=2.5
    )
    style_meta_label = ParagraphStyle(
        'MetaLblSess', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=10,
        textColor=colors.HexColor("#0F172A")
    )
    style_meta_val = ParagraphStyle(
        'MetaValSess', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=10,
        textColor=colors.HexColor("#334155")
    )
    style_tbl_head = ParagraphStyle(
        'TblHeadSess', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=9.5,
        alignment=TA_CENTER, textColor=colors.HexColor("#0F172A")
    )
    style_tbl_cell = ParagraphStyle(
        'TblCellSess', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7.5, leading=9.5,
        alignment=TA_LEFT, textColor=colors.HexColor("#1E293B")
    )
    style_tbl_step = ParagraphStyle(
        'TblStepSess', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=10,
        alignment=TA_CENTER, textColor=colors.HexColor("#8B0000")
    )

    story = []

    # 1. Header institucional con 2 logos (Fiel al Word oficial)
    logo_gear_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "logo_inei34.png"))
    logo_bee_path = os.path.abspath(os.path.join("data", "templates", "smartteacher", "insignia.png"))
    if not os.path.exists(logo_gear_path):
        logo_gear_path = os.path.abspath(os.path.join("app", "static", "imagen", "logo_inei34.png"))
    if not os.path.exists(logo_bee_path):
        logo_bee_path = os.path.abspath(os.path.join("app", "static", "imagen", "insignia.png"))

    from reportlab.platypus import Image as ReportLabImage
    has_logos = os.path.exists(logo_gear_path) and os.path.exists(logo_bee_path)

    if has_logos:
        img_gear = ReportLabImage(logo_gear_path, width=22 * mm, height=22 * mm)
        img_bee = ReportLabImage(logo_bee_path, width=22 * mm, height=22 * mm)
        cell_l = [img_gear, Spacer(1, 1*mm), Paragraph("R.M. Nº 2296-57", style_caption)]
        cell_r = [img_bee, Spacer(1, 1*mm), Paragraph("CHANCAY", style_caption)]
    else:
        cell_l = Paragraph("<b>CET N.º 34</b>", style_caption)
        cell_r = Paragraph("<b>CHANCAY</b>", style_caption)

    cell_c = Paragraph(f"""
    <font size="9" color="#8B0000"><b>INSTITUCIÓN EDUCATIVA PÚBLICA TÉCNICA Nº 34 (CET 34)</b></font><br/>
    <font size="6.5" color="#475569">"Honradez - Disciplina - Trabajo" • R.M. Nº 2296-57 • Cód. Modular: 0245621-0<br/>
    GOBIERNO REGIONAL DE LIMA • UGEL Nº 10 - HUARAL • CHANCAY</font><br/>
    <font size="9.5" color="#0F172A"><b>SESIÓN DE APRENDIZAJE N° 01 – IVB</b></font><br/>
    <font size="9" color="#0F172A"><b>Título: "{xml_escape(topic)}"</b></font><br/>
    <font size="7.5" color="#8B0000"><b>PLANIFICACIÓN PEDAGÓGICA INSTITUCIONAL CET N.º 34</b></font>
    """, style_center_header)

    head_tbl = Table([[cell_l, cell_c, cell_r]], colWidths=[24 * mm, 126 * mm, 24 * mm])
    head_tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor("#8B0000")),
    ]))
    story.append(head_tbl)
    story.append(Spacer(1, 2.5 * mm))

    # 2. I. DATOS GENERALES: (Tabla exacta del Word oficial)
    story.append(Paragraph("I. DATOS GENERALES:", style_sec_title))
    is_ept_meta = "educación para el trabajo" in specialty.lower() or "ept" in specialty.lower() or any(
        k in specialty.lower() for k in ["computaci", "mecan", "electr", "metal", "vestid", "conta"]
    )
    if is_ept_meta:
        meta_rows = [
            [Paragraph("Institución educativa", style_meta_label), Paragraph(":", style_meta_label), Paragraph("CET N.° 34 (I.E. Emblemática INEI N.° 34)", style_meta_val)],
            [Paragraph("Área curricular", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(specialty), style_meta_val)],
            [Paragraph("Programa formativo", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(clean_spec), style_meta_val)],
            [Paragraph("Módulo formativo", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(modulo_val), style_meta_val)],
            [Paragraph("Grado y sección", style_meta_label), Paragraph(":", style_meta_label), Paragraph(f'{grade_str}: "{xml_escape(str(section))}"', style_meta_val)],
            [Paragraph("Fecha", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(fecha_val), style_meta_val)],
            [Paragraph("Duración", style_meta_label), Paragraph(":", style_meta_label), Paragraph(f"{ped_hours} horas pedagógicas ({duration_min} minutos)", style_meta_val)],
            [Paragraph("Método didáctico", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(metodo_val), style_meta_val)],
            [Paragraph("Sub director", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(subdirector_name), style_meta_val)],
            [Paragraph("Docente responsable", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(teacher_name), style_meta_val)],
        ]
    else:
        comp_priorizada = props.get("competencia") or data.get("competence") or f"Competencias CNEB del área de {specialty}"
        meta_rows = [
            [Paragraph("Institución educativa", style_meta_label), Paragraph(":", style_meta_label), Paragraph("CET N.° 34 (I.E. Emblemática INEI N.° 34)", style_meta_val)],
            [Paragraph("Área curricular", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(specialty), style_meta_val)],
            [Paragraph("Competencia priorizada", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(comp_priorizada), style_meta_val)],
            [Paragraph("Propósito formativo", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(purpose_val[:120] + ('...' if len(purpose_val) > 120 else '')), style_meta_val)],
            [Paragraph("Grado y sección", style_meta_label), Paragraph(":", style_meta_label), Paragraph(f'{grade_str}: "{xml_escape(str(section))}"', style_meta_val)],
            [Paragraph("Fecha", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(fecha_val), style_meta_val)],
            [Paragraph("Duración", style_meta_label), Paragraph(":", style_meta_label), Paragraph(f"{ped_hours} horas pedagógicas ({duration_min} minutos)", style_meta_val)],
            [Paragraph("Método didáctico", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(metodo_val), style_meta_val)],
            [Paragraph("Subdirección", style_meta_label), Paragraph(":", style_meta_label), Paragraph("Subdirección de Formación General", style_meta_val)],
            [Paragraph("Docente responsable", style_meta_label), Paragraph(":", style_meta_label), Paragraph(xml_escape(teacher_name), style_meta_val)],
        ]
    meta_tbl = Table(meta_rows, colWidths=[42 * mm, 4 * mm, 128 * mm])
    meta_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 2 * mm))

    # 3. II. PROPÓSITO DE LA SESIÓN
    story.append(Paragraph("II. PROPÓSITO DE LA SESIÓN", style_sec_title))
    story.append(Paragraph(xml_escape(purpose_val), style_body))

    # 4. III. CRITERIOS DE EVALUACIÓN
    story.append(Paragraph("III. CRITERIOS DE EVALUACIÓN", style_sec_title))
    story.append(Paragraph(xml_escape(criteria_val), style_body))

    # 5. IV. EVIDENCIAS DE APRENDIZAJE
    story.append(Paragraph("IV. EVIDENCIAS DE APRENDIZAJE", style_sec_title))
    story.append(Paragraph(xml_escape(evidence_val), style_body))

    # 6. V. SITUACIÓN SIGNIFICATIVA (Sin cajas azules ni llamadas artificiales)
    story.append(Paragraph("V. SITUACIÓN SIGNIFICATIVA", style_sec_title))
    sit_sig_raw = c_json.get("situacion_significativa")
    if not sit_sig_raw:
        if is_digital:
            sit_sig_p1 = f"En la institución educativa CET N.º 34 (I.E. INEI N.º 34) de Chancay, se ha observado que muchos estudiantes del {grade_str} de secundaria en el programa formativo de {clean_spec} tienen dificultades para organizar y gestionar adecuadamente sus archivos digitales. Acumulan documentos con nombres poco claros, carpetas desorganizadas, archivos duplicados que saturan el almacenamiento y falta de respaldo seguro."
            sit_sig_retos = [
                "¿Cómo podemos organizar nuestros archivos digitales para encontrarlos de manera rápida y sencilla?",
                "¿Qué buenas prácticas debemos aplicar al crear carpetas, nombrar archivos y evitar documentos duplicados?",
                "¿De qué manera el uso responsable y seguro de las plataformas de almacenamiento en la nube puede mejorar nuestro trabajo escolar y proteger nuestra información?"
            ]
        else:
            sit_sig_p1 = f"En la institución educativa CET N.º 34 (I.E. INEI N.º 34) de Chancay, los estudiantes del {grade_str} de secundaria del programa de {clean_spec} requieren desarrollar destrezas operativas para {topic}, aplicando normas de seguridad, tolerancias técnicas y orden de taller."
            sit_sig_retos = [
                f"¿Cuáles son los pasos operativos necesarios para ejecutar {topic} con precisión y calidad?",
                "¿Qué medidas de seguridad y protocolo 5S debemos cumplir para evitar accidentes en el taller?",
                "¿Cómo verificamos que el producto obtenido cumpla con las especificaciones técnicas requeridas?"
            ]
        story.append(Paragraph(xml_escape(sit_sig_p1), style_body))
        story.append(Paragraph("Ante esta situación, nos planteamos los siguientes retos:", style_body))
        for r_txt in sit_sig_retos:
            story.append(Paragraph(f"• {xml_escape(r_txt)}", style_body))
    else:
        for p_line in str(sit_sig_raw).split("\n"):
            p_line = p_line.strip()
            if p_line:
                if p_line.startswith("-") or p_line.startswith("*") or p_line.startswith("•") or p_line.startswith("?") or p_line.startswith("¿"):
                    clean_r = p_line.lstrip("-*• ")
                    story.append(Paragraph(f"• {xml_escape(clean_r)}", style_body))
                else:
                    story.append(Paragraph(xml_escape(p_line), style_body))
    story.append(Spacer(1, 2 * mm))

    # 7. VI. DESARROLLO DE LOS PROCESOS DIDÁCTICOS DE LA SESIÓN (Tabla de 4 columnas en vertical)
    story.append(Paragraph("VI. DESARROLLO DE LOS PROCESOS DIDÁCTICOS DE LA SESIÓN", style_sec_title))

    gtz_steps = c_json.get("procesos_didacticos_gtz")
    if not gtz_steps or not isinstance(gtz_steps, list) or len(gtz_steps) == 0:
        if duration_min == 225:
            t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 10, 20, 30, 135, 20, 10
        elif duration_min == 135:
            t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 15, 20, 20, 50, 15, 15
        elif duration_min == 90:
            t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 10, 15, 15, 35, 10, 5
        else:
            t_inf = max(5, int(duration_min * 0.08))
            t_plan = max(10, int(duration_min * 0.12))
            t_dec = max(10, int(duration_min * 0.15))
            t_cont = max(5, int(duration_min * 0.10))
            t_eval = max(5, int(duration_min * 0.08))
            t_ejec = duration_min - (t_inf + t_plan + t_dec + t_cont + t_eval)

        if is_digital:
            gtz_steps = [
                {
                    "paso": "INFORMARSE",
                    "tiempo": f"{t_inf} Minutos",
                    "actividad_docente": "Presenta una situación problemática: los estudiantes tienen muchos archivos desordenados, con nombres poco claros y documentos duplicados. Formula preguntas: ¿Cómo podemos encontrar rápidamente un archivo? ¿Qué problemas genera tener documentos duplicados? Explica los criterios para organizar, nombrar y depurar archivos y carpetas.",
                    "actividad_estudiante": "Observa la situación problemática presentada, responde las preguntas, comparte sus saberes previos y experiencias, y reconoce la importancia de mantener sus archivos digitales ordenados y seguros."
                },
                {
                    "paso": "PLANIFICAR",
                    "tiempo": f"{t_plan} Minutos",
                    "actividad_docente": "Orienta a los estudiantes para elaborar un plan de organización de sus archivos. Indica que deben establecer carpetas principales y subcarpetas, definir nombres claros y determinar cómo identificar los archivos duplicados.",
                    "actividad_estudiante": "Elabora un plan de trabajo en el que establece los pasos para organizar sus archivos, propone nombres para las carpetas y selecciona criterios para identificar documentos duplicados."
                },
                {
                    "paso": "DECIDIR",
                    "tiempo": f"{t_dec} Minutos",
                    "actividad_docente": "Solicita que cada estudiante determine la estructura de carpetas que utilizará y los criterios para nombrar, clasificar y depurar sus archivos. Supervisa las decisiones y brinda orientación cuando sea necesario.",
                    "actividad_estudiante": "Decide cómo organizará su espacio digital, qué nombres utilizará, dónde guardará cada archivo y cuáles documentos duplicados puede eliminar después de verificar su contenido."
                },
                {
                    "paso": "EJECUTAR",
                    "tiempo": f"{t_ejec} Minutos",
                    "actividad_docente": "Demuestra cómo crear carpetas y subcarpetas, cambiar nombres, mover archivos, identificar duplicados y eliminarlos de forma segura. Acompaña a los estudiantes durante la práctica y resuelve sus dudas.",
                    "actividad_estudiante": "Organiza su carpeta digital en la nube, crea subcarpetas, cambia los nombres poco claros, mueve los archivos a sus ubicaciones correspondientes e identifica y depura duplicados, conservando las versiones necesarias."
                },
                {
                    "paso": "CONTROLAR",
                    "tiempo": f"{t_cont} Minutos",
                    "actividad_docente": "Revisa el trabajo de los estudiantes mediante una lista de cotejo. Verifica que las carpetas estén organizadas, los nombres sean adecuados y los duplicados se hayan gestionado correctamente. Proporciona retroalimentación.",
                    "actividad_estudiante": "Comprueba que sus archivos estén en las carpetas correctas, verifica los nombres asignados, revisa que no haya duplicados innecesarios y corrige los errores encontrados."
                },
                {
                    "paso": "EVALUAR",
                    "tiempo": f"{t_eval} Minutos",
                    "actividad_docente": "Promueve la reflexión mediante preguntas: ¿Qué aprendiste? ¿Qué dificultad encontraste? ¿Cómo te ayudará esta organización en tus actividades escolares? Evalúa el producto final y el cumplimiento del propósito de aprendizaje.",
                    "actividad_estudiante": "Presenta su carpeta digital organizada, explica los procedimientos realizados y reflexiona sobre sus aprendizajes, dificultades y compromisos para mantener ordenada su información digital."
                }
            ]
        else:
            gtz_steps = [
                {
                    "paso": "INFORMARSE",
                    "tiempo": f"{t_inf} Minutos",
                    "actividad_docente": f"Presenta la situación técnica desafiante vinculada a {topic}. Plantea preguntas técnicas y explica los parámetros de calidad, tolerancia y normas de seguridad en el taller.",
                    "actividad_estudiante": f"Analiza la situación planteada, recupera saberes previos e investiga las especificaciones técnicas requeridas para {topic} en el manual de especialidad."
                },
                {
                    "paso": "PLANIFICAR",
                    "tiempo": f"{t_plan} Minutos",
                    "actividad_docente": f"Orienta la formulación de la hoja de operaciones para {topic}, indicando la secuencia técnica de pasos, selección de herramientas y cálculo de tiempos de ejecución.",
                    "actividad_estudiante": f"En equipo de taller, formula el plan de operaciones detallando la secuencia técnica, herramientas requeridas y medidas preventivas de seguridad."
                },
                {
                    "paso": "DECIDIR",
                    "tiempo": f"{t_dec} Minutos",
                    "actividad_docente": f"Supervisa las alternativas operativas planteadas por los equipos. Promueve la justificación técnica y autoriza la ejecución del proceso más seguro y eficiente.",
                    "actividad_estudiante": f"Debate en su equipo, evalúa opciones y decide la alternativa óptima para ejecutar {topic} cumpliendo los estándares del puesto de trabajo."
                },
                {
                    "paso": "EJECUTAR",
                    "tiempo": f"{t_ejec} Minutos",
                    "actividad_docente": f"Demuestra la secuencia de operación técnica en el puesto de trabajo. Monitorea permanentemente la ejecución, corrige posturas y verifica el uso estricto del EPP.",
                    "actividad_estudiante": f"Ejecuta la tarea técnica de {topic} siguiendo la secuencia planificada, respetando tolerancias, medidas de seguridad y protocolo de orden y limpieza 5S."
                },
                {
                    "paso": "CONTROLAR",
                    "tiempo": f"{t_cont} Minutos",
                    "actividad_docente": f"Aplica lista de cotejo y guía a los estudiantes en el control de calidad dimensional, funcional y de acabado del producto obtenido.",
                    "actividad_estudiante": f"Verifica su trabajo mediante instrumentos de medición técnica o lista de control, identificando aciertos, discrepancias y ejecutando ajustes necesarios."
                },
                {
                    "paso": "EVALUAR",
                    "tiempo": f"{t_eval} Minutos",
                    "actividad_docente": f"Facilita la sesión de metacognición técnica y evalúa el nivel de logro de las competencias alcanzadas en la sesión de {topic}.",
                    "actividad_estudiante": f"Sustenta el producto final obtenido, valora el trabajo colaborativo en taller y reflexiona sobre la aplicación productiva de lo aprendido."
                }
            ]

    gtz_table_rows = [
        [
            Paragraph("<b>Pasos o etapas</b>", style_tbl_head),
            Paragraph("<b>Tiempo</b>", style_tbl_head),
            Paragraph("<b>Acciones o actividades del docente</b>", style_tbl_head),
            Paragraph("<b>Acciones o actividades del estudiante</b>", style_tbl_head)
        ]
    ]

    for step in gtz_steps:
        p_nom = str(step.get("paso") or "").strip().upper().lstrip("0123456789. ")
        t_str = str(step.get("tiempo") or "").strip()
        if not "minuto" in t_str.lower():
            t_str = f"{t_str} Minutos"
        a_doc = str(step.get("actividad_docente") or step.get("acciones_docente") or "").strip()
        a_est = str(step.get("actividad_estudiante") or step.get("acciones_estudiante") or "").strip()

        gtz_table_rows.append([
            Paragraph(xml_escape(p_nom), style_tbl_step),
            Paragraph(xml_escape(t_str), style_tbl_head),
            Paragraph(xml_escape(a_doc), style_tbl_cell),
            Paragraph(xml_escape(a_est), style_tbl_cell)
        ])

    gtz_tbl = Table(gtz_table_rows, colWidths=[25 * mm, 18 * mm, 65.5 * mm, 65.5 * mm], repeatRows=1)
    gtz_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(gtz_tbl)
    story.append(Spacer(1, 2.5 * mm))

    # 8. VII. MATERIALES (Fiel a Word)
    story.append(Paragraph("VII. MATERIALES", style_sec_title))
    mat_raw = c_json.get("materiales_recursos") or c_json.get("materiales")
    if not mat_raw:
        if is_digital:
            mat_list = [
                "Computadora",
                "Proyector",
                f"Herramientas, máquinas o instrumentos propios de {clean_spec}.",
                f"Ficha técnica de proceso y guía de aprendizaje sobre {topic}.",
                "Equipo de Protección Personal (EPP reglamentario de taller).",
                "Pizarra acrílica, plumones y materiales fungibles de práctica."
            ]
        else:
            mat_list = [
                f"Herramientas, máquinas o instrumentos propios de {clean_spec}.",
                f"Ficha técnica de proceso y guía de aprendizaje sobre {topic}.",
                "Equipo de Protección Personal (EPP reglamentario de taller).",
                "Pizarra acrílica, plumones y materiales fungibles de práctica."
            ]
    elif isinstance(mat_raw, list):
        mat_list = [str(m).strip().lstrip("•-* ") for m in mat_raw if str(m).strip()]
    else:
        mat_list = [l.strip().lstrip("•-* ") for l in str(mat_raw).split("\n") if l.strip()]

    for m_item in mat_list:
        story.append(Paragraph(f"• {xml_escape(m_item)}", style_body))
    story.append(Spacer(1, 2 * mm))

    # 9. VIII. BIBLIOGRAFIA (Fiel a Word)
    story.append(Paragraph("VIII. BIBLIOGRAFIA", style_sec_title))
    bib_raw = c_json.get("bibliografia")
    if not bib_raw:
        bib_list = [
            "Currículo Nacional de Educación Básica",
            "Recursos digitales educativos",
            f"Manual técnico de especialidad en {clean_spec} – CET N.° 34 Chancay"
        ]
    elif isinstance(bib_raw, list):
        bib_list = [str(b).strip().lstrip("•-* ") for b in bib_raw if str(b).strip()]
    else:
        bib_list = [l.strip().lstrip("•-* ") for l in str(bib_raw).split("\n") if l.strip()]

    for b_item in bib_list:
        story.append(Paragraph(f"• {xml_escape(b_item)}", style_body))
    story.append(Spacer(1, 5 * mm))

    # 10. Firmas (Tabla de 3 columnas auténtica)
    from reportlab.platypus import KeepTogether
    firmas = c_json.get("firmas_institucionales") or {}
    f_doc = firmas.get("docente") or {}
    f_jefe = firmas.get("jefe_taller") or {}
    f_sub = firmas.get("subdirector") or {}

    is_ept_pdf = "educación para el trabajo" in specialty.lower() or "ept" in specialty.lower() or any(
        k in specialty.lower() for k in ["computaci", "mecan", "electr", "metal", "vestid", "conta"]
    )

    sig_doc_name = f_doc.get("nombre") or teacher_name
    sig_doc_cargo = f_doc.get("cargo") or ("DOCENTE RESPONSABLE" if is_ept_pdf else f"DOCENTE RESPONSABLE - {clean_spec.upper()}")

    if is_ept_pdf:
        if "comput" in clean_spec.lower() or "inform" in clean_spec.lower():
            def_jefe_nom = "Mg. Luis Arturo La Rosa Gallardo"
            def_jefe_car = "JEFE DE TALLER COMPUTACIÓN E INFORMÁTICA"
        elif "mecan" in clean_spec.lower():
            def_jefe_nom = "Prof. Responsable de Taller de Mecánica"
            def_jefe_car = "JEFE DE TALLER MECÁNICA DE PRODUCCIÓN"
        else:
            def_jefe_nom = f"Jefe de Taller de {clean_spec}"
            def_jefe_car = f"JEFE DE TALLER {clean_spec.upper()}"
        def_sub_nom = "Mg. Javier Eulogio Rosas Maguiña"
        def_sub_car = "SUB-DIRECTOR DE ÁREA TÉCNICA"
    else:
        def_jefe_nom = "Prof. Coordinador(a) Pedagógico(a)"
        def_jefe_car = f"COORDINACIÓN PEDAGÓGICA - {clean_spec.upper()}"
        def_sub_nom = "Subdirección de Formación General"
        def_sub_car = "SUBDIRECCIÓN PEDAGÓGICA"

    sig_jefe_name = f_jefe.get("nombre") or def_jefe_nom
    sig_jefe_cargo = f_jefe.get("cargo") or def_jefe_car
    sig_sub_name = f_sub.get("nombre") or def_sub_nom
    sig_sub_cargo = f_sub.get("cargo") or def_sub_car

    sig_rows = [
        [
            Paragraph("___________________________________", style_center_header),
            Paragraph("___________________________________", style_center_header),
            Paragraph("___________________________________", style_center_header)
        ],
        [
            Paragraph(f"<b>{xml_escape(sig_doc_name)}</b><br/><font size='7' color='#475569'>{xml_escape(sig_doc_cargo)}<br/>Especialidad / Aula</font>", style_center_header),
            Paragraph(f"<b>{xml_escape(sig_jefe_name)}</b><br/><font size='7' color='#475569'>{xml_escape(sig_jefe_cargo)}</font>", style_center_header),
            Paragraph(f"<b>{xml_escape(sig_sub_name)}</b><br/><font size='7' color='#475569'>{xml_escape(sig_sub_cargo)}<br/>I.E. CET N° 34 - CHANCAY</font>", style_center_header)
        ]
    ]
    sig_tbl = Table(sig_rows, colWidths=[58 * mm, 58 * mm, 58 * mm])
    sig_tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(KeepTogether(sig_tbl))

    # Estampilla institucional de visado digital directivo con código QR (Bloque 3)
    visa_info_pdf = c_json.get("visado_digital") or data.get("visado_digital")
    if visa_info_pdf and (data.get("status") == "APROBADO" or visa_info_pdf.get("status") == "APROBADO"):
        pdf_visa_table = create_pdf_digital_visa_stamp_table(visa_info_pdf)
        story.append(Spacer(1, 4 * mm))
        story.append(KeepTogether(pdf_visa_table))

    pdf_doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


def generate_worksheet_pdf_bytes(doc_data: Dict[str, Any], target: str = "teacher") -> bytes:
    from reportlab.platypus import Image as ReportLabImage
    """
    Genera la Ficha de Aprendizaje / Trabajo oficial CET N.º 34 en formato PDF nativo ReportLab
    exactamente en 2 páginas A4 verticales, alineada al CNEB y sin dependencias de conversión externa.
    """
    from app.ai.document_schemas import build_ficha_from_dict
    f_obj = build_ficha_from_dict(doc_data)
    f = f_obj.model_dump()

    parsed = parse_document_data(doc_data, target=target)
    topic = doc_data.get('topic') or doc_data.get('title') or parsed.get('topic') or f['titulo']
    if topic.lower().startswith('ficha de aprendizaje: '):
        topic = topic[22:].strip()
    topic_clean = str(topic or "").strip().strip('"').strip('“').strip('”')
    topic_display = topic_clean.upper()
    area = f['area'] or parsed.get('specialty') or "Ciencia y Tecnología"
    grade = f['grado'] or parsed.get('grade') or 1
    sec = f['seccion'] or parsed.get('section_name') or "A"
    teacher = f['docente'] or parsed.get('teacher_name') or "Docente Responsable"
    date_val = f.get('fecha') or parsed.get('date') or "____ / ____ / 2026"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('WTitle', parent=styles['Normal'], fontSize=11, leading=14, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#8B0000'))
    h_sec = ParagraphStyle('WSec', parent=styles['Normal'], fontSize=9.5, leading=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F172A'))
    body = ParagraphStyle('WBody', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'), alignment=TA_JUSTIFY)
    body_bold = ParagraphStyle('WBodyB', parent=body, fontName='Helvetica-Bold')
    meta_style = ParagraphStyle('WMeta', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#334155'))
    meta_center = ParagraphStyle('WMetaC', parent=meta_style, alignment=TA_CENTER)
    meta_right = ParagraphStyle('WMetaR', parent=meta_style, alignment=TA_RIGHT)
    box_style = ParagraphStyle('WBox', parent=body, fontSize=8, leading=10.5)

    story = []
    # 1. Header con Insignia
    logo_path = os.path.abspath('data/templates/smartteacher/insignia.png')
    img = ReportLabImage(logo_path, width=18*mm, height=18*mm) if os.path.exists(logo_path) else Paragraph('<b>CET 34</b>', title_style)
    txt_center = Paragraph(f'<b>INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY</b><br/>Área: {xml_escape(str(area))}', meta_center)
    txt_right = Paragraph(f'<b>FICHA DE APRENDIZAJE</b><br/>{grade}.° de Secundaria', meta_right)
    t_head = Table([[img, txt_center, txt_right]], colWidths=[22*mm, 118*mm, 40*mm])
    t_head.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#8B0000'))
    ]))
    story.append(t_head)
    story.append(Spacer(1, 1.5*mm))

    story.append(Paragraph(f'<b>“{xml_escape(topic_display)}”</b>', title_style))
    story.append(Spacer(1, 1*mm))

    p_meta1 = Paragraph('<b>Estudiante:</b> _____________________________________', meta_style)
    p_meta2 = Paragraph(f'<b>Grado y sección:</b> {grade}.° “{sec}”', meta_center)
    p_meta3 = Paragraph(f'<b>Fecha:</b> {date_val}', meta_right)
    p_meta4 = Paragraph(f'<b>Docente:</b> {xml_escape(str(teacher))}', meta_style)

    t_meta = Table([[p_meta1, p_meta2, p_meta3], [p_meta4, '', '']], colWidths=[85*mm, 45*mm, 50*mm])
    t_meta.setStyle(TableStyle([
        ('SPAN', (0, 1), (2, 1)),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 2*mm))

    # Sec 1: Propósito de la sesión
    story.append(Paragraph('<b>1. Propósito de la sesión</b>', h_sec))
    story.append(Spacer(1, 1*mm))
    comp_p = Paragraph(f'<b>Competencia del Currículo Nacional:</b> {xml_escape(str(f["competencia"]))}<br/><b>Capacidades:</b> {xml_escape(str(f["capacidades"]))}<br/><b>Desempeño contextualizado:</b> {xml_escape(str(f["desempeno"]))}', box_style)
    t_comp = Table([[comp_p]], colWidths=[180*mm])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 1.5*mm))

    story.append(Paragraph(f'<b>Propósito:</b> {xml_escape(str(f["proposito"]))}', body))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(f'<b>Producto o evidencia:</b> {xml_escape(str(f["evidencia_general"]))}', body))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph('<b>Objetivos de aprendizaje:</b>', body_bold))
    for obj_i in f.get('objetivos_aprendizaje', []):
        story.append(Paragraph(f'• {xml_escape(str(obj_i))}', body))
    story.append(Spacer(1, 2*mm))

    # Sec 2: Situación de reto
    story.append(Paragraph('<b>2. Situación de reto</b>', h_sec))
    story.append(Spacer(1, 1*mm))
    reto_p = Paragraph(f'<b>¡Acepta el desafío!</b><br/>{xml_escape(str(f["situacion_reto"]))}', box_style)
    t_reto = Table([[reto_p]], colWidths=[180*mm])
    t_reto.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEF3C7')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#F59E0B')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_reto)
    story.append(Spacer(1, 2*mm))

    # Sec 3: Reto y marco teórico
    story.append(Paragraph('<b>3. Reto y marco teórico</b>', h_sec))
    story.append(Spacer(1, 1*mm))
    teor_p = Paragraph(f'<b>Lectura / fuente breve:</b><br/>{xml_escape(str(f["marco_teorico"]))}', box_style)
    t_teor = Table([[teor_p]], colWidths=[180*mm])
    t_teor.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EFF6FF')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#3B82F6')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_teor)
    story.append(Spacer(1, 1.5*mm))

    # Sec 4: Actividades / aplicación
    story.append(Paragraph('<b>4. Actividades / aplicación</b>', h_sec))
    story.append(Spacer(1, 1*mm))
    for act in f.get('actividades', []):
        tit = act.get('titulo') or 'Actividad'
        inst = act.get('instrucciones') or 'Desarrolla el ejercicio propuesto.'
        num = act.get('numero') or 1
        story.append(Paragraph(f'<b>Actividad {num} – {xml_escape(str(tit))}:</b> {xml_escape(str(inst))}<br/><b>Respuesta / desarrollo:</b> __________________________________________________________________________________', body))
        story.append(Spacer(1, 1.5*mm))

    ext_p = Paragraph(f'<b>Actividad de extensión:</b><br/>{xml_escape(str(f["actividad_extension"]))}', box_style)
    t_ext = Table([[ext_p]], colWidths=[180*mm])
    t_ext.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#64748B')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_ext)

    # Page Break for exactly 2 pages
    story.append(PageBreak())

    # Page 2: Sec 5: Profundización creativa y análisis gráfico
    story.append(Paragraph(f'<b>5. Profundización creativa y soporte gráfico – {xml_escape(topic_display)}</b>', h_sec))
    story.append(Spacer(1, 0.8*mm))

    from app.ai.pedagogical_graphics import resolve_pedagogical_graphic
    g_info = resolve_pedagogical_graphic(area, topic)
    if g_info and os.path.exists(g_info["path"]):
        ped_img = ReportLabImage(g_info["path"], width=g_info["width_mm"]*mm, height=g_info["height_mm"]*mm)
        cap_p = Paragraph(f'<b>{xml_escape(g_info["title"])}</b> — {xml_escape(g_info["caption"])}', meta_center)
        t_img_box = Table([[ped_img], [cap_p]], colWidths=[180*mm])
        t_img_box.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        story.append(t_img_box)
        story.append(Spacer(1, 1.2*mm))
    else:
        story.append(Paragraph(f'Aplica los conocimientos de {xml_escape(str(topic))} en situaciones complejas, conectando conceptos, formulando hipótesis y resolviendo los siguientes retos:', body))
        story.append(Spacer(1, 1.2*mm))
        if f.get('ejemplo_modelo_pasos'):
            for p_step in f['ejemplo_modelo_pasos']:
                story.append(Paragraph(f'• {xml_escape(str(p_step))}', body))
        story.append(Spacer(1, 2*mm))

    story.append(Paragraph('<b>Ejercicios de consolidación y aplicación práctica:</b>', body_bold))
    for ej in f.get('ejercicios_consolidacion', []):
        story.append(Paragraph(f'• {xml_escape(str(ej))}', body))
    story.append(Spacer(1, 2.5*mm))

    # Sec 6: Evaluación rápida – lista de cotejo (4 columnas auténticas)
    story.append(Paragraph('<b>6. Evaluación rápida – lista de cotejo</b>', h_sec))
    story.append(Spacer(1, 1.5*mm))
    eval_rows = [
        [Paragraph('<b>Criterio de Evaluación</b>', ParagraphStyle('THC', parent=body_bold, textColor=colors.HexColor('#0F172A'))),
         Paragraph('<b>Sí</b>', ParagraphStyle('TH', parent=body_bold, alignment=TA_CENTER)),
         Paragraph('<b>En proceso</b>', ParagraphStyle('THP', parent=body_bold, alignment=TA_CENTER)),
         Paragraph('<b>Evidencia / comentario</b>', ParagraphStyle('THE', parent=body_bold))]
    ]
    for c_item in f.get('lista_cotejo', []):
        crit_txt = c_item.get('criterio') or 'Criterio de evaluación'
        evid_txt = c_item.get('evidencia') or f'Evidencia de {topic}'
        eval_rows.append([
            Paragraph(xml_escape(str(crit_txt)), body),
            Paragraph('[   ]', ParagraphStyle('TB', parent=body, alignment=TA_CENTER)),
            Paragraph('[   ]', ParagraphStyle('TB', parent=body, alignment=TA_CENTER)),
            Paragraph(xml_escape(str(evid_txt)), meta_style)
        ])
    t_eval = Table(eval_rows, colWidths=[100*mm, 15*mm, 20*mm, 45*mm])
    t_eval.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_eval)
    story.append(Spacer(1, 3.5*mm))

    story.append(Paragraph(f'<b>Metacognición:</b> {xml_escape(str(f.get("metacognicion", "¿Qué aprendí hoy y cómo puedo aplicar este aprendizaje en una situación real?")))}', body_bold))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph('______________________________________________________________________________________________', meta_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


def generate_exam_pdf_bytes(doc_data: Dict[str, Any], target: str = "teacher") -> bytes:
    """
    Genera la Ficha de Examen o Ficha de Práctica oficial CET N.° 34 en formato PDF nativo ReportLab.
    - Versión Estudiante: Exactamente 1 página A4 vertical (Header institucional, indicaciones, Sec A, B y C).
    - Versión Docente: 2 páginas A4 verticales (Página 1: Examen/Práctica; Página 2: Solucionario Docente con 10 filas).
    """
    from reportlab.platypus import Image as ReportLabImage
    from app.ai.document_schemas import build_examen_practica_from_dict
    exam_obj = build_examen_practica_from_dict(doc_data)
    is_student = (target.strip().lower() == "student")
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ETitle', parent=styles['Normal'], fontSize=10.5, leading=13, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#8B0000'))
    banner_style = ParagraphStyle('EBanner', parent=styles['Normal'], fontSize=9.5, leading=12, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#1E3A8A'))
    h_sec = ParagraphStyle('ESec', parent=styles['Normal'], fontSize=9.5, leading=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F172A'))
    body = ParagraphStyle('EBody', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    body_bold = ParagraphStyle('EBodyB', parent=body, fontName='Helvetica-Bold')
    meta_style = ParagraphStyle('EMeta', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#334155'))
    meta_center = ParagraphStyle('EMetaC', parent=meta_style, alignment=TA_CENTER)
    meta_right = ParagraphStyle('EMetaR', parent=meta_style, alignment=TA_RIGHT)
    box_style = ParagraphStyle('EBox', parent=body, fontSize=8, leading=10.5)

    story = []
    
    # 1. Header institucional
    logo_path = os.path.abspath('data/templates/smartteacher/insignia.png')
    img = ReportLabImage(logo_path, width=18*mm, height=18*mm) if os.path.exists(logo_path) else Paragraph('<b>CET 34</b>', title_style)
    
    inst_text = (
        f"<b>INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY</b><br/>"
        f"<b>Área:</b> {xml_escape(exam_obj.area)}"
    )
    banner_text = (
        f"<b>{xml_escape(exam_obj.titulo_documento)}</b><br/>"
        f"<font size=8.5>{xml_escape(exam_obj.grado_str)}</font>"
    )
    
    r0 = [img, Paragraph(inst_text, meta_style), Paragraph(banner_text, banner_style)]
    r1 = [Paragraph(f'<b>“{xml_escape(exam_obj.tema.upper())}”</b>', title_style), '', '']
    r2_sub = Table([
        [
            Paragraph("<b>Estudiante:</b> _________________________________________", meta_style),
            Paragraph(f"<b>Grado y sección:</b> {exam_obj.grado}.° “{xml_escape(exam_obj.seccion)}”", meta_center),
            Paragraph(f"<b>Fecha:</b> {xml_escape(exam_obj.fecha)}", meta_right)
        ]
    ], colWidths=[95*mm, 45*mm, 40*mm])
    r2_sub.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    r2 = [r2_sub, '', '']
    r3 = [Paragraph(f"<b>Docente:</b> {xml_escape(exam_obj.docente)}", meta_style), '', '']

    header_table = Table([r0, r1, r2, r3], colWidths=[24*mm, 106*mm, 50*mm])
    header_table.setStyle(TableStyle([
        ('SPAN', (0, 1), (2, 1)),
        ('SPAN', (0, 2), (2, 2)),
        ('SPAN', (0, 3), (2, 3)),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#1E3A8A')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
        ('BACKGROUND', (0, 1), (2, 1), colors.HexColor('#F8FAFC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 2.5*mm))

    # 2. Indicaciones
    ind_table = Table([[Paragraph(f"<b>Indicaciones:</b> {xml_escape(exam_obj.indicaciones.replace('Indicaciones: ', ''))}", box_style)]], colWidths=[180*mm])
    ind_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(ind_table)
    story.append(Spacer(1, 2.5*mm))

    is_matematica = (exam_obj.area == "Matemática") or (len(exam_obj.seccion_c) == 0)

    # 3. Sección A
    story.append(Paragraph("<b>A. Marca la alternativa correcta</b>", h_sec))
    story.append(Spacer(1, 1.2*mm))
    for q in exam_obj.seccion_a:
        story.append(Paragraph(f"<b>{q.numero}.</b> {xml_escape(q.pregunta)}", body))
        story.append(Spacer(1, 0.4*mm))
        opt0 = xml_escape(q.opciones[0]) if len(q.opciones) > 0 else ''
        opt1 = xml_escape(q.opciones[1]) if len(q.opciones) > 1 else ''
        opt2 = xml_escape(q.opciones[2]) if len(q.opciones) > 2 else ''

        box_a = "[&#160;&#160;] a)"
        box_b = "[&#160;&#160;] b)"
        box_c = "[&#160;&#160;] c)"
        total_len = len(opt0) + len(opt1) + len(opt2)
        if total_len > 75:
            opts_pdf = f"&nbsp;&nbsp;&nbsp;&nbsp;<b>{box_a}</b> {opt0}<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>{box_b}</b> {opt1}<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>{box_c}</b> {opt2}"
        else:
            opts_pdf = f"<b>{box_a}</b> {opt0} &nbsp;&nbsp;&nbsp;&nbsp; <b>{box_b}</b> {opt1} &nbsp;&nbsp;&nbsp;&nbsp; <b>{box_c}</b> {opt2}"

        story.append(Paragraph(opts_pdf, body))
        story.append(Spacer(1, 1.2*mm))

    # 4. Sección B
    story.append(Spacer(1, 1*mm))
    sec_b_title = "<b>B. Resuelve y muestra tu procedimiento</b>" if is_matematica else "<b>B. Responde y explica</b>"
    story.append(Paragraph(sec_b_title, h_sec))
    story.append(Spacer(1, 1.2*mm))
    for q in exam_obj.seccion_b:
        story.append(Paragraph(f"<b>{q.numero}.</b> {xml_escape(q.pregunta)}", body))
        story.append(Spacer(1, 0.4*mm))
        if is_matematica:
            story.append(Paragraph("Espacio de resolución: __________________________________________________________________", meta_style))
            story.append(Paragraph("<b>Respuesta final:</b> ___________________________________________________________________", meta_style))
        else:
            story.append(Paragraph("____________________________________________________________________________________", meta_style))
            story.append(Paragraph("____________________________________________________________________________________", meta_style))
        story.append(Spacer(1, 1.2*mm))

    # 5. Sección C (solo en áreas no matemáticas que tengan preguntas en seccion_c)
    if not is_matematica and len(exam_obj.seccion_c) > 0:
        story.append(Spacer(1, 1*mm))
        story.append(Paragraph("<b>C. Verdadero (V) o falso (F)</b>", h_sec))
        story.append(Spacer(1, 1.2*mm))
        for q in exam_obj.seccion_c:
            row_vf = Table([
                [Paragraph(f"<b>{q.numero}.</b> {xml_escape(q.afirmacion)}", body), Paragraph("<b>(&nbsp;&nbsp;&nbsp;) V &nbsp;&nbsp;&nbsp; (&nbsp;&nbsp;&nbsp;) F</b>", meta_right)]
            ], colWidths=[145*mm, 35*mm])
            row_vf.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(row_vf)
            story.append(Spacer(1, 1*mm))

    # Si es versión docente, agregar página 2 con Solucionario y Criterios
    if not is_student:
        story.append(PageBreak())
        
        # Encabezado Solucionario
        sol_banner = [
            img,
            Paragraph(
                f"<b>INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY</b><br/>"
                f"<b>SOLUCIONARIO DOCENTE Y ORIENTACIONES DE CORRECCIÓN</b><br/>"
                f"<font size=8 color='#64748B'>Área: {xml_escape(exam_obj.area)} | {xml_escape(exam_obj.grado_str)} | Tema: “{xml_escape(exam_obj.tema)}”</font>",
                meta_style
            ),
            Paragraph(f"<b>CLAVE DOCENTE</b><br/><font size=8 color='#B91C1C'>CONFIDENCIAL</font>", banner_style)
        ]
        t_sol_head = Table([sol_banner], colWidths=[24*mm, 116*mm, 40*mm])
        t_sol_head.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#1E3A8A')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_sol_head)
        story.append(Spacer(1, 3*mm))

        # Cuadro de puntaje y orientaciones
        p_info = (
            f"<b>Puntaje sugerido:</b> {xml_escape(exam_obj.puntaje_texto)}<br/>"
            f"<b>Orientaciones pedagógicas:</b> {xml_escape(exam_obj.orientacion_docente)}"
        )
        t_info = Table([[Paragraph(p_info, box_style)]], colWidths=[180*mm])
        t_info.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#0284C7')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0F9FF')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_info)
        story.append(Spacer(1, 3*mm))

        # Tabla del solucionario (11 filas x 2 cols)
        sol_rows = [[Paragraph("<b>Ítem</b>", meta_center), Paragraph("<b>Respuesta esperada / Criterio pedagógico</b>", body_bold)]]
        for s in exam_obj.solucionario:
            sol_rows.append([
                Paragraph(f"<b>{xml_escape(s.item)}</b>", meta_center),
                Paragraph(xml_escape(s.respuesta_esperada), body)
            ])
        t_sol = Table(sol_rows, colWidths=[20*mm, 160*mm])
        t_sol.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#1E3A8A')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8FAFC')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_sol)

    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()



def generate_pdf_bytes(doc_data: Dict[str, Any], target: str = "teacher") -> bytes:
    """
    Genera un documento PDF oficial utilizando ReportLab con NumberedCanvas.
    Retorna bytes binarios listos para streaming.
    """
    data = parse_document_data(doc_data, target=target)
    doc_type = data["doc_type"]
    is_student = data.get("is_student", False)
    c_json = data.get("content_json") or {}

    if doc_type in ["unidad_didactica", "unidad_aprendizaje"]:
        return generate_unit_pdf_bytes(doc_data)
    if doc_type == "sesion_aprendizaje":
        return generate_session_pdf_bytes(doc_data)

    # Para fichas de examen o práctica oficial CET N.º 34:
    if doc_type in ["examen_tecnico", "examen", "practica_calificada", "practica_ejercicios", "practica"] or doc_data.get("modo") in ["examen", "practica"] or (isinstance(c_json, dict) and c_json.get("modo") in ["examen", "practica"]):
        return generate_exam_pdf_bytes(doc_data, target=target)

    # Para fichas de aprendizaje CET N.º 34 (generación nativa ReportLab 2 páginas oficial):
    if doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia"]:
        return generate_worksheet_pdf_bytes(doc_data, target=target)

    buf = io.BytesIO()
    is_session_gtz = (doc_type == "sesion_aprendizaje" and bool(c_json.get("procesos_didacticos_gtz")))
    if is_session_gtz:
        # Orientación mixta réplica fiel del Word institucional: Sección 1 Vertical, Sección 2 Horizontal
        frame_port = Frame(20 * mm, 20 * mm, (210 - 40) * mm, (297 - 40) * mm, id='F_Port', topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0)
        frame_land = Frame(20 * mm, 20 * mm, (297 - 40) * mm, (210 - 40) * mm, id='F_Land', topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0)
        pt_port = PageTemplate(id='portrait', frames=frame_port, pagesize=A4)
        pt_land = PageTemplate(id='landscape', frames=frame_land, pagesize=landscape(A4))
        pdf_doc = BaseDocTemplate(buf, pageTemplates=[pt_port, pt_land])
    else:
        pdf_doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=22 * mm
        )

    styles = build_pdf_styles()
    story = []

    # Subtítulo institucional
    sub_map = {
        "sesion_aprendizaje": "PLANIFICACIÓN CURRICULAR Y SECUENCIA DIDÁCTICA CNEB / EPT 2026",
        "ficha_actividad": "FICHA DE APRENDIZAJE Y GUÍA TÉCNICA DE TALLER OPERATIVO",
        "ficha_guia": "FICHA GUÍA Y MATERIAL DE ESTUDIO CNEB / EPT 2026",
        "presentacion_tema": "GUÍA DE PRESENTACIÓN Y DESARROLLO TEMÁTICO",
        "ficha_trabajo": "FICHA DE TRABAJO Y GUÍA OPERATIVA DE TALLER",
        "practica_ejercicios": "PRÁCTICA DE EJERCICIOS Y PROBLEMAS TÉCNICOS",
        "solucionario_docente": "SOLUCIONARIO Y PAUTAS PEDAGÓGICAS DOCENTES",
        "examen_tecnico": "EVALUACIÓN ESCRITA Y PRÁCTICA DE TALLER" if is_student else "SOLUCIONARIO Y CLAVE DE CORRECCIÓN CONFIDENCIAL DOCENTE",
        "rubrica_evaluacion": "INSTRUMENTO DE EVALUACIÓN FORMATIVA CNEB"
    }
    subtitle = sub_map.get(doc_type, "DOCUMENTO PEDAGÓGICO OFICIAL")

    if doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
        # Encabezado institucional fiel a la Tabla 0 de la Ficha CET N.º 34 (sin duración artificial ni campos vacíos)
        story.append(create_pdf_worksheet_header_table(data, styles=styles))
        story.append(Spacer(1, 3 * mm))
    else:
        # 1. Membrete Institucional
        story.append(create_pdf_header_table(
            title=data["title"],
            subtitle=subtitle,
            styles=styles,
            is_confidential=(doc_type == "examen_tecnico" and not is_student)
        ))
        story.append(Spacer(1, 3 * mm))

        # 2. Datos Informativos
        story.append(create_pdf_metadata_table(data, styles=styles))
        story.append(Spacer(1, 4 * mm))

    # 3. Recuadro Estudiante si aplica (Exclusivo para exámenes)
    if is_student and doc_type in ["examen_tecnico"]:
        tot_pts = c_json.get("total_points", 20)
        story.append(create_pdf_student_identification_box(styles, total_pts=tot_pts))
        story.append(Spacer(1, 3 * mm))

    # 4. Aviso Docente Confidencial si aplica
    if not is_student and doc_type == "examen_tecnico":
        story.append(create_pdf_callout(
            text="Este solucionario contiene las respuestas correctas, justificaciones pedagógicas y ponderación técnica. Documento reservado exclusivamente para el docente calificador.",
            title="CONFIDENCIAL DOCENTE — PROHIBIDA SU DISTRIBUCIÓN",
            styles=styles,
            is_warning=True
        ))
        story.append(Spacer(1, 3 * mm))

    # 5. Cuerpo según Documento
    if doc_type == "sesion_aprendizaje":
        gtz_steps = c_json.get("procesos_didacticos_gtz")
        if gtz_steps and isinstance(gtz_steps, list):
            is_dig_session = any(k in f"{data['topic']} {data['specialty']}".lower() for k in [
                "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
                "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
            ])
            # Formato Institucional Oficial CET N° 34 / INEI N° 34 de Chancay
            story.append(Paragraph("I. Propósito y Criterios de Evaluación", styles['SectionHeading1']))
            story.append(Paragraph(f"• <b>Propósito de la Sesión:</b> {xml_escape(data['purpose'])}", styles['BodyJustified']))
            crit_val = c_json.get('criterios_evaluacion') or (c_json.get('propositos') or {}).get('criterios_evaluacion') or f"Aplica destrezas técnicas en {data['topic']} cumpliendo normas de calidad."
            evid_val = (c_json.get('propositos') or {}).get('evidencia') or c_json.get('evidencia') or f"Ficha técnica y producto verificado de {data['topic']}."
            story.append(Paragraph(f"• <b>Criterio de Evaluación:</b> {xml_escape(str(crit_val))}", styles['BodyJustified']))
            story.append(Paragraph(f"• <b>Evidencia de Aprendizaje:</b> {xml_escape(str(evid_val))}", styles['BodyJustified']))
            story.append(Spacer(1, 2 * mm))

            sit_sig = c_json.get("situacion_significativa")
            if sit_sig:
                story.append(Paragraph("II. Situación Significativa", styles['SectionHeading1']))
                callout_tit = "CONTEXTO DIGITAL Y RETOS" if is_dig_session else "CONTEXTO DEL TALLER Y RETOS"
                story.append(create_pdf_callout(str(sit_sig), callout_tit, styles=styles, is_warning=False))
                story.append(Spacer(1, 2 * mm))

            # Transición a Orientación Horizontal (Landscape) idéntica a la plantilla institucional Word
            story.append(NextPageTemplate('landscape'))
            story.append(PageBreak())

            story.append(Paragraph(f"III. Desarrollo de los Procesos Didácticos — Metodología de Acción Completa GTZ ({data['duration']} Minutos)", styles['SectionHeading1']))
            story.append(create_pdf_session_gtz_table(styles, gtz_steps, is_landscape=True))
            story.append(Spacer(1, 3 * mm))

            # Recursos y Materiales Educativos
            story.append(Paragraph("IV. Recursos y Materiales Educativos", styles['SectionHeading1']))
            mat_items = c_json.get("materiales_recursos") or c_json.get("materiales")
            if not mat_items:
                if is_dig_session:
                    mat_items = [
                        "Computadoras conectadas a red e internet institucional",
                        "Plataforma de almacenamiento en la nube institucional (Google Workspace / OneDrive)",
                        "Proyector multimedia o pantalla interactiva del laboratorio",
                        "Guías de práctica digital y fichas de aplicación de gestión documental"
                    ]
                else:
                    mat_items = [
                        "Torno paralelo, mandril autocentrante y accesorios de fijación",
                        "Herramientas de corte (buriles HSS afilados a altura de centros)",
                        "Instrumentos de control metrológico (Calibrador Vernier de 0.02 mm)",
                        "Equipo de Protección Personal (mameluco ceñido, lentes con protección lateral, calzado de seguridad)"
                    ]
            if isinstance(mat_items, list):
                for m in mat_items:
                    story.append(Paragraph(f"• {xml_escape(str(m))}", styles['Bullet']))
            elif isinstance(mat_items, str):
                for m in mat_items.split("\n"):
                    if m.strip():
                        story.append(Paragraph(f"• {xml_escape(m.strip().lstrip('•-* '))}", styles['Bullet']))
            story.append(Spacer(1, 2 * mm))

            # V. Bibliografía y Recursos de Consulta (Sección VIII fiel a plantilla Word)
            story.append(Paragraph("V. Bibliografía y Recursos de Consulta", styles['SectionHeading1']))
            bib_items = c_json.get("bibliografia") or [
                "Currículo Nacional de la Educación Básica (CNEB) – MINEDU",
                "Catálogo Nacional de la Oferta Formativa (CNOF) – EPT",
                "Guía metodológica de formación profesional GTZ – Aprendizaje por la acción completa",
                "Manual institucional de normas técnicas y seguridad – CET N.° 34 Chancay"
            ]
            if isinstance(bib_items, list):
                for b in bib_items:
                    story.append(Paragraph(f"• {xml_escape(str(b))}", styles['Bullet']))
            story.append(Spacer(1, 3 * mm))

            if data.get("structure_mode") == "institucional":
                story.append(create_pdf_institutional_3_signatures(styles, teacher_name=data.get("teacher_name", "Docente"), specialty=data["specialty"], is_landscape=True))
            else:
                story.append(create_pdf_simple_teacher_signature(styles, teacher_name=data.get("teacher_name", "Docente")))

        else:
            story.append(Paragraph("I. Propósitos de Aprendizaje y Criterios de Evaluación", styles['SectionHeading1']))
            story.append(Paragraph(f"• <b>Competencia CNEB:</b> {xml_escape(data['competence'])}", styles['BodyJustified']))
            story.append(Paragraph(f"• <b>Propósito de la Sesión:</b> {xml_escape(data['purpose'])}", styles['BodyJustified']))
            story.append(Paragraph(f"• <b>Evidencia de Aprendizaje:</b> Ficha técnica elaborada y aplicación práctica en el taller de {xml_escape(data['specialty'])}.", styles['BodyJustified']))
            story.append(Spacer(1, 3 * mm))

            story.append(Paragraph("II. Secuencia Didáctica (Momentos Pedagógicos)", styles['SectionHeading1']))
            sec_did = c_json.get("secuencia_didactica")
            if not isinstance(sec_did, dict):
                sec_did = {}
            fases = [
                ("1. Fase de Inicio (Motivación, Saberes Previos y Conflicto Cognitivo)", sec_did.get("inicio", {}), "15 min"),
                ("2. Fase de Desarrollo (Gestión, Acompañamiento y Práctica Técnica)", sec_did.get("desarrollo", {}), f"{int(data['duration']) - 30} min"),
                ("3. Fase de Cierre (Metacognición, Evaluación y Retroalimentación)", sec_did.get("cierre", {}), "15 min")
            ]

            for f_title, f_val, default_t in fases:
                if isinstance(f_val, dict):
                    tiempo = f_val.get("tiempo", default_t)
                    f_text = f_val.get("actividades") or f_val.get("descripcion") or ""
                    if not f_text:
                        parts = [f"• <b>{k.replace('_', ' ').capitalize()}:</b> {v}" for k, v in f_val.items() if isinstance(v, str) and v.strip()]
                        f_text = "<br/>".join(parts)
                elif isinstance(f_val, str) and f_val.strip():
                    tiempo = default_t
                    f_text = f_val.strip()
                else:
                    tiempo = default_t
                    f_text = f"Actividades formativas orientadas a la adquisición y consolidación de competencias en {data['topic']}."

                story.append(Paragraph(f"<b>{xml_escape(f_title)} — [{xml_escape(str(tiempo))}]</b>", styles['SectionHeading2']))
                story.append(Paragraph(sanitize_text_for_xml(f_text), styles['BodyJustified']))
                story.append(Spacer(1, 2 * mm))

            story.append(Paragraph("III. Normas de Seguridad Industrial, EPP y Protocolo 5S", styles['SectionHeading1']))
            seg_text = c_json.get("seguridad_industrial_5s") or c_json.get("seguridad_industrial") or "Porte obligatorio de EPP y cumplimiento estricto del protocolo 5S en taller."
            if isinstance(seg_text, dict):
                seg_text = f"EPP Obligatorio: {seg_text.get('epp_requerido', 'EPP Completo')}. Normas 5S: {seg_text.get('normas_5s', 'Seiri, Seiton, Seiso, Seiketsu, Shitsuke')}"
            story.append(create_pdf_callout(str(seg_text), "SEGURIDAD INDUSTRIAL EN TALLER", styles=styles, is_warning=True))
            story.append(Spacer(1, 3 * mm))

            story.append(Paragraph("IV. Instrumento de Evaluación Formativa", styles['SectionHeading1']))
            story.append(create_pdf_rubric_table(styles, total_pts=20, topic=data["topic"], custom_criteria=c_json.get("rubrica_items"), session_type=data.get("session_type")))
            story.append(Spacer(1, 4 * mm))
            if data.get("structure_mode") == "institucional":
                story.append(create_pdf_institutional_3_signatures(styles, teacher_name=data.get("teacher_name", "Docente"), specialty=data["specialty"]))
            else:
                story.append(create_pdf_simple_teacher_signature(styles, teacher_name=data.get("teacher_name", "Docente")))

    elif doc_type in ["ficha_actividad", "ficha_trabajo", "guia_clase", "ficha_guia", "practica"]:
        # Formato Institucional Oficial CET N.º 34 / INEI N.º 34 de Chancay (DEF-F01, DEF-F02)
        topic = data.get("topic") or data.get("title") or "Ficha de Aprendizaje"
        specialty = data.get("specialty") or "Educación para el Trabajo"
        clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "")
        is_digital_topic = any(k in f"{topic} {clean_spec}".lower() for k in [
            "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
            "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
        ])

        # 1. Cuadro de Competencia CNEB (Tabla 1 institucional idéntica a Word)
        comp_box = (
            f"<b>Competencia del Currículo Nacional:</b> {xml_escape(data['competence'])}<br/>"
            f"<b>Capacidades:</b> {xml_escape(data['capacidades'])}<br/>"
            f"<b>Desempeño contextualizado:</b> {xml_escape(data['desempeno'])}"
        )
        story.append(create_pdf_callout(comp_box, "COMPETENCIA Y CAPACIDADES CNEB / EPT", styles=styles, is_warning=False))
        story.append(Spacer(1, 2.5 * mm))

        # 2. Propósito de la sesión (Sección 1 idéntica a Word)
        story.append(Paragraph("1. Propósito de la sesión", styles['SectionHeading1']))
        story.append(Paragraph(f"• <b>Propósito:</b> {xml_escape(data['purpose'])}", styles['BodyJustified']))
        story.append(Paragraph(f"• <b>Producto o evidencia:</b> {xml_escape(data['evidence'])}", styles['BodyJustified']))
        story.append(Paragraph("<b>Objetivos de aprendizaje:</b>", styles['BodyJustified']))
        story.append(Paragraph(f"• Comprender el fundamento técnico y los pasos operativos de {xml_escape(topic)}.", styles['Bullet']))
        if is_digital_topic:
            story.append(Paragraph(f"• Identificar herramientas, estructura de carpetas, nomenclatura y control de acceso para {xml_escape(topic)}.", styles['Bullet']))
            story.append(Paragraph(f"• Aplicar criterios de organización documental, seguridad digital y mejora continua en {xml_escape(topic)}.", styles['Bullet']))
        else:
            story.append(Paragraph(f"• Identificar herramientas, variables de control y tolerancias para {xml_escape(topic)}.", styles['Bullet']))
            story.append(Paragraph(f"• Aplicar criterios de control de calidad, seguridad y mejora continua en {xml_escape(topic)}.", styles['Bullet']))
        story.append(Spacer(1, 2.5 * mm))

        # 3. Situación de reto (Tabla 2 institucional idéntica a Word)
        story.append(Paragraph("2. Situación de reto", styles['SectionHeading1']))
        story.append(create_pdf_callout(data['reto_text'], "¡ACEPTA EL DESAFÍO!", styles=styles, is_warning=False))
        story.append(Spacer(1, 2.5 * mm))

        # 4. Reto y marco teórico (Tabla 3 institucional idéntica a Word)
        story.append(Paragraph("3. Reto y marco teórico", styles['SectionHeading1']))
        story.append(create_pdf_callout(data['teor_text'], "MARCO TEÓRICO Y CONCEPTOS CLAVE", styles=styles, is_warning=False))
        story.append(Spacer(1, 2 * mm))

        story.append(Paragraph("<b>Ejemplo modelo</b>", styles['SectionHeading2']))
        story.append(Paragraph(f"• <b>Paso 1 – Diagnóstico y necesidad:</b> Se identifican las condiciones iniciales y requerimientos técnicos de {xml_escape(topic)}.", styles['Bullet']))
        if is_digital_topic:
            story.append(Paragraph(f"• <b>Paso 2 – Planificación y recursos:</b> Se seleccionan las plataformas de almacenamiento en la nube, esquemas de nomenclatura y herramientas digitales necesarias para {xml_escape(topic)}.", styles['Bullet']))
            story.append(Paragraph(f"• <b>Paso 3 – Ejecución controlada:</b> Se aplica el procedimiento técnico modelado paso a paso estructurando carpetas y normalizando nombres de archivo.", styles['Bullet']))
            story.append(Paragraph(f"• <b>Paso 4 – Verificación y control:</b> Se contrastan los resultados obtenidos con las especificaciones técnicas esperadas.", styles['Bullet']))
            story.append(Paragraph(f"• <b>Resultado:</b> El proceso de {xml_escape(topic)} se completa con éxito, asegurando orden jerárquico, respaldos y cumplimiento de normas 5S digitales.", styles['Bullet']))
        else:
            story.append(Paragraph(f"• <b>Paso 2 – Planificación y recursos:</b> Se seleccionan las herramientas, materiales y equipos de protección necesarios para {xml_escape(topic)}.", styles['Bullet']))
            story.append(Paragraph(f"• <b>Paso 3 – Ejecución controlada:</b> Se aplica el procedimiento técnico modelado paso a paso verificando medidas y tolerancias.", styles['Bullet']))
            story.append(Paragraph(f"• <b>Paso 4 – Verificación y control:</b> Se contrastan los resultados obtenidos con las especificaciones técnicas esperadas.", styles['Bullet']))
            story.append(Paragraph(f"• <b>Resultado:</b> El proceso de {xml_escape(topic)} se completa con éxito, asegurando precisión, orden y cumplimiento de normas 5S.", styles['Bullet']))
        story.append(Spacer(1, 2.5 * mm))

        # 5. Actividades / aplicación (Sección 4 idéntica a Word)
        story.append(Paragraph("4. Actividades / aplicación", styles['SectionHeading1']))
        story.append(Paragraph(f"<b>Actividad 1:</b> {xml_escape(data['act1_desc'])}", styles['BodyJustified']))
        story.append(Paragraph("<i>Respuesta / desarrollo:</i> __________________________________________________________________________________________", styles['Normal']))
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph(f"<b>Actividad 2:</b> {xml_escape(data['act2_desc'])}", styles['BodyJustified']))
        story.append(Paragraph("<i>Respuesta / desarrollo:</i> __________________________________________________________________________________________", styles['Normal']))
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph(f"<b>Actividad 3:</b> {xml_escape(data['act3_desc'])}", styles['BodyJustified']))
        story.append(Paragraph("<i>Respuesta / desarrollo:</i> __________________________________________________________________________________________", styles['Normal']))
        story.append(Spacer(1, 2.5 * mm))

        # 6. Profundización técnica / creativa (Tabla 4 institucional idéntica a Word)
        sec5_tit = "5. Profundización técnica y buenas prácticas digitales" if is_digital_topic else f"5. Profundización técnica y control de calidad en {topic}"
        story.append(Paragraph(sec5_tit, styles['SectionHeading1']))
        story.append(create_pdf_callout(data['ext_text'], "ACTIVIDAD DE EXTENSIÓN Y PROFUNDIZACIÓN CREATIVA", styles=styles, is_warning=False))
        story.append(Spacer(1, 2 * mm))

        if is_digital_topic:
            story.append(Paragraph(f"En el entorno informático de la I.E. CET N.° 34, organiza y respalda la documentación digital de {xml_escape(topic)} aplicando protocolos profesionales:", styles['BodyJustified']))
            story.append(Paragraph("• Estructura un esquema jerárquico de carpetas ordenado por año, bimestre y tipo de evidencia.", styles['Bullet']))
            story.append(Paragraph("• Aplica la convención de nomenclatura estándar: AAAA-MM-DD_Asignatura_Detalle_v##.", styles['Bullet']))
            story.append(Paragraph("• Identifica y depura archivos duplicados, liberando espacio y optimizando la búsqueda.", styles['Bullet']))
            story.append(Paragraph("• Sincroniza la información en la nube institucional y configura permisos estrictos (Lector / Editor).", styles['Bullet']))
            story.append(Spacer(1, 1.5 * mm))
            story.append(Paragraph("<b>Ejercicios de consolidación y aplicación práctica</b>", styles['SectionHeading2']))
            story.append(Paragraph("• Simula la reorganización de una carpeta de descargas con 15 archivos desordenados aplicando la jerarquía técnica.", styles['Bullet']))
            story.append(Paragraph("• Configura un enlace seguro en la nube compartida verificando que los permisos restrinjan la edición no autorizada.", styles['Bullet']))
            story.append(Paragraph("• Elabora una lista de verificación de copias de seguridad (regla 3-2-1: copia local, en la nube y medio externo).", styles['Bullet']))
        else:
            story.append(Paragraph(f"En los talleres de la I.E. CET N.° 34 de Chancay, optimiza los procedimientos técnicos de {xml_escape(topic)} aplicando normas de precisión:", styles['BodyJustified']))
            story.append(Paragraph("• Verifica el estado de las herramientas e instrumentos de medición antes de iniciar la operación.", styles['Bullet']))
            story.append(Paragraph("• Respeta rigurosamente las tolerancias dimensionales especificadas en la hoja de proceso.", styles['Bullet']))
            story.append(Paragraph("• Aplica el protocolo 5S (orden y limpieza) durante toda la jornada de trabajo.", styles['Bullet']))
            story.append(Paragraph("• Utiliza de forma permanente el Equipo de Protección Personal (EPP) reglamentario.", styles['Bullet']))
            story.append(Spacer(1, 1.5 * mm))
            story.append(Paragraph("<b>Ejercicios de consolidación y aplicación práctica</b>", styles['SectionHeading2']))
            story.append(Paragraph(f"• Describe la secuencia de operaciones y parámetros de trabajo para {xml_escape(topic)}.", styles['Bullet']))
            story.append(Paragraph(f"• Identifica dos defectos u averías posibles en {xml_escape(topic)} y explica la acción correctiva técnica.", styles['Bullet']))
            story.append(Paragraph("• Registra las mediciones obtenidas y contrástalas con las tolerancias admisibles del plano.", styles['Bullet']))
        story.append(Spacer(1, 2.5 * mm))

        # 7. Evaluación rápida – lista de cotejo (Tabla 5 institucional idéntica a Word - 4 columnas)
        story.append(Paragraph("6. Evaluación rápida – lista de cotejo", styles['SectionHeading1']))
        chk_items = data.get("checklist") or c_json.get("lista_cotejo_autoevaluacion") or c_json.get("lista_cotejo")
        if not chk_items:
            chk_items = [
                {"criterio": f"Comprendo y explico con precisión los conceptos y operaciones de {topic}."},
                {"criterio": f"Aplico procedimientos técnicos seguros y propongo mejoras en {topic}."}
            ]
        story.append(create_pdf_checklist_table(styles, criteria=chk_items, topic=topic))
        story.append(Spacer(1, 2 * mm))

        meta_q = c_json.get("metacognicion") or "¿Qué aprendí hoy y cómo puedo aplicar este aprendizaje en una situación real?"
        if isinstance(meta_q, dict):
            meta_q = meta_q.get("pregunta") or str(meta_q)
        story.append(Paragraph(f"<b>Metacognición:</b> {xml_escape(str(meta_q))}", styles['BodyJustified']))
        story.append(Paragraph("__________________________________________________________________________________________", styles['Normal']))
        story.append(Paragraph("__________________________________________________________________________________________", styles['Normal']))

    elif doc_type == "examen_tecnico":
        questions = c_json.get("questions", [])
        total_pts = c_json.get("total_points", 20)

        if is_student:
            story.append(Paragraph(f"Instrucciones para la Evaluación ({total_pts} Puntos Totales)", styles['SectionHeading1']))
            story.append(Paragraph(
                "• Lea con detenimiento cada enunciado antes de contestar.<br/>"
                "• Utilice letra legible y justifique sus respuestas en las preguntas de desarrollo.<br/>"
                f"• Tiempo límite estimado para la prueba: {data['duration']} minutos.",
                styles['BodyJustified']
            ))
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("Cuestionario Técnico Escrito y Práctico", styles['SectionHeading1']))

            if questions and isinstance(questions, list):
                for q in questions:
                    q_num = q.get("numero") or q.get("number") or 1
                    q_pts = q.get("puntaje") or q.get("points") or 4
                    q_stmt = q.get("enunciado") or q.get("statement") or "Pregunta técnica."
                    q_opts = q.get("opciones") or q.get("options") or []

                    q_header = f"<b>Pregunta {q_num}.</b> <font color='#64748B'>[{q_pts} Puntos]</font><br/>{xml_escape(q_stmt)}"
                    story.append(Paragraph(q_header, styles['BodyJustified']))

                    if q_opts:
                        for opt in q_opts:
                            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;( &nbsp; ) &nbsp; {xml_escape(opt)}", styles['BodyJustified']))
                    else:
                        story.append(Spacer(1, 1 * mm))
                        story.append(Paragraph("<i>Espacio de desarrollo y cálculos técnicos:</i>", styles['Normal']))
                        story.append(Paragraph("__________________________________________________________________________________________", styles['Normal']))
                        story.append(Paragraph("__________________________________________________________________________________________", styles['Normal']))
                    story.append(Spacer(1, 2 * mm))
            else:
                story.append(Paragraph(sanitize_text_for_xml(data["content_markdown"]), styles['BodyJustified']))

            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("Criterios de Evaluación y Rúbrica", styles['SectionHeading1']))
            story.append(create_pdf_rubric_table(styles, total_pts=total_pts, topic=data["topic"]))

        else:
            # Solucionario exclusivo docente
            story.append(Paragraph(f"Solucionario y Pautas de Corrección Docente ({total_pts} Puntos)", styles['SectionHeading1']))

            if questions and isinstance(questions, list):
                for q in questions:
                    q_num = q.get("numero") or q.get("number") or 1
                    q_pts = q.get("puntaje") or q.get("points") or 4
                    q_stmt = q.get("enunciado") or q.get("statement") or "Pregunta técnica."
                    q_ans = q.get("respuesta_correcta") or q.get("correct_answer") or "Respuesta oficial."
                    q_just = q.get("justificacion") or q.get("justification") or "Justificación pedagógica."
                    q_crit = q.get("criterio_evaluacion") or f"Criterio de evaluación en {data['topic']}."

                    story.append(Paragraph(f"<b>Ítem {q_num} [{q_pts} Pts] — {xml_escape(q_crit)}</b>", styles['SectionHeading2']))
                    story.append(Paragraph(f"<i>Enunciado: {xml_escape(q_stmt)}</i>", styles['BodyJustified']))

                    box_text = (
                        f"<b><font color='#B45309'>[Clave] Respuesta Correcta:</font></b><br/>{xml_escape(q_ans)}<br/><br/>"
                        f"<b>[Justificación Técnica]:</b><br/>{xml_escape(q_just)}<br/><br/>"
                        f"<b>[Criterios de Calificación Parcial]:</b><br/>"
                        f"• Procedimiento y resultado exacto: {q_pts} pts (100%)<br/>"
                        f"• Procedimiento adecuado pero error numérico/conceptual menor: {max(1, q_pts//2)} pts (50%)<br/>"
                        f"• Respuesta errónea o sin sustento técnico: 0 pts"
                    )
                    story.append(create_pdf_callout(box_text, "SOLUCIONARIO DOCENTE", styles=styles, is_warning=False))
                    story.append(Spacer(1, 2 * mm))
            else:
                story.append(Paragraph(sanitize_text_for_xml(data["content_markdown"]), styles['BodyJustified']))

            story.append(Spacer(1, 2 * mm))
            story.append(create_pdf_rubric_table(styles, total_pts=total_pts, topic=data["topic"]))
            story.append(Spacer(1, 3 * mm))
            story.append(create_pdf_signatures_block(styles))

    else:
        render_markdown_to_pdf_story(story, styles, data["content_markdown"])
        story.append(Spacer(1, 4 * mm))
        story.append(create_pdf_simple_teacher_signature(styles, teacher_name=data.get("teacher_name", "Docente")))

    # Construcción del PDF con NumberedCanvas
    pdf_doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
