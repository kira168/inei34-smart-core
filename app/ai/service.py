"""
INEI SMART-CORE - AI Specialized Services
High-level pedagogical and institutional functions for role-specific AI tools.
"""

import os
import logging
import re
import json
import time
from typing import Dict, Any, Optional, List, Union
from app.ai.orchestrator import ai_orchestrator
from app.database.connection import get_db

logger = logging.getLogger(__name__)

class AIService:
    @staticmethod
    def generate_cneb_session(
        user: Dict[str, Any],
        topic: str,
        grade: int,
        specialty: str,
        duration_minutes: int = 90,
        competence: Optional[str] = None,
        purpose: Optional[str] = None,
        difficulty: Optional[str] = "intermedio",
        observations: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a structured CNEB Learning Session draft for General or Technical Secondary Education.
        Returns editable markdown with CNEB competence, performance criteria, 3-phase sequence, and rubric.
        """
        cleaned_topic = (topic or "").strip()
        cleaned_specialty = (specialty or "Educación para el Trabajo").strip()
        cleaned_competence = (competence or "Gestiona proyectos de emprendimiento económico o social").strip()
        cleaned_purpose = (purpose or f"Desarrollar habilidades teórico-prácticas sobre {cleaned_topic}").strip()
        cleaned_diff = (difficulty or "intermedio").strip().lower()
        cleaned_obs = (observations or "").strip()

        diff_desc = {
            "inicial": "Básico / Inicial (Con énfasis en andamiaje, instrucciones detalladas y modelado continuo)",
            "basico": "Básico / Inicial (Con énfasis en andamiaje, instrucciones detalladas y modelado continuo)",
            "básico": "Básico / Inicial (Con énfasis en andamiaje, instrucciones detalladas y modelado continuo)",
            "intermedio": "Intermedio (Aplicación práctica estándar y trabajo en cuadrillas colaborativas)",
            "avanzado": "Avanzado (Resolución autónoma de problemas técnicos, tolerancias estrictas y optimización)"
        }.get(cleaned_diff, "Intermedio (Aplicación práctica estándar)")

        obs_clause = f"\n- Observaciones / Especificaciones del Docente: {cleaned_obs}" if cleaned_obs else ""

        min_inicio = max(10, int(duration_minutes * 0.15))
        min_cierre = max(10, int(duration_minutes * 0.15))
        min_desarrollo = max(20, duration_minutes - min_inicio - min_cierre)

        prompt = (
            f"Elabora un BORRADOR COMPLETO de Sesión de Aprendizaje Pedagógica contextualizada bajo los lineamientos del CNEB (MINEDU) y Educación Técnica (EPT).\n"
            f"- Institución: I.E. INEI N.º 34 de Chancay\n"
            f"- Tema / Actividad Productiva: {cleaned_topic}\n"
            f"- Grado: {grade}° de Secundaria\n"
            f"- Área / Especialidad Técnica: {cleaned_specialty}\n"
            f"- Duración: {duration_minutes} minutos (Inicio: {min_inicio} min, Desarrollo: {min_desarrollo} min, Cierre: {min_cierre} min)\n"
            f"- Nivel de Dificultad: {diff_desc}\n"
            f"- Competencia Priorizada: {cleaned_competence}\n"
            f"- Propósito de Aprendizaje: {cleaned_purpose}{obs_clause}\n\n"
            f"ESTRUCTURA OBLIGATORIA DEL BORRADOR REQUERIDA:\n"
            f"1. DATOS INFORMATIVOS (I.E. INEI 34 Chancay, Área/Especialidad, Grado, Duración, Nivel de Dificultad, Docente, Fecha 2026).\n"
            f"2. PROPÓSITOS DE APRENDIZAJE:\n"
            f"   - Propósito formativo claro y medible.\n"
            f"   - Competencia y Capacidades CNEB pertinentes.\n"
            f"   - Desempeños precisados y contextualizados para {cleaned_specialty}.\n"
            f"3. CRITERIOS DE EVALUACIÓN Y EVIDENCIAS:\n"
            f"   - Criterios de evaluación observables.\n"
            f"   - Evidencia tangible de aprendizaje.\n"
            f"   - Instrumento de evaluación formal (Rúbrica analítica).\n"
            f"4. MATERIALES Y RECURSOS EDUCATIVOS:\n"
            f"   - Herramientas, máquinas o insumos propios de {cleaned_specialty}.\n"
            f"   - Guías técnicas, fichas de trabajo y EPP reglamentario.\n"
            f"5. SECUENCIA DIDÁCTICA CON DISTRIBUCIÓN DE TIEMPOS:\n"
            f"   - MOMENTO DE INICIO ({min_inicio} min): Motivación, recuperación de saberes previos, conflicto cognitivo o reto inicial.\n"
            f"   - MOMENTO DE DESARROLLO ({min_desarrollo} min): Procesamiento técnico, modelado docente, aplicación práctica por cuadrillas, monitoreo y retroalimentación formativa.\n"
            f"   - MOMENTO DE CIERRE ({min_cierre} min): Metacognición reflexiva, evaluación de productos y protocolo 5S de orden y limpieza.\n"
            f"6. ACTIVIDAD O PRODUCTO FINAL: Tarea o pieza técnica a entregar por el estudiante.\n"
            f"7. SEGURIDAD INDUSTRIAL Y PROTOCOLO 5S (TALLER EPT): Medidas de prevención de riesgos y uso de EPP.\n"
            f"8. INSTRUMENTO DE EVALUACIÓN: Rúbrica formativa analítica con escala ministerial (AD, A, B, C).\n"
            f"9. ADAPTACIONES Y APOYOS PEDAGÓGICOS (DUA): Atención a la diversidad y nivelación.\n"
            f"10. PROPUESTA EDITABLE DEL DOCENTE: Presentar el contenido como propuesta pedagógica editable para revisión y adecuación del docente titular. No inventar códigos curriculares no verificables."
        )
        result = ai_orchestrator.execute_prompt(user, prompt, tool_type="cneb_session_generator", subject_id=cleaned_specialty)
        result["draft_metadata"] = {
            "doc_type": "sesion_aprendizaje",
            "topic": cleaned_topic,
            "grade": grade,
            "specialty": cleaned_specialty,
            "duration_minutes": duration_minutes,
            "competence": cleaned_competence,
            "difficulty": cleaned_diff,
            "observations": cleaned_obs,
            "is_draft": True,
            "disclaimer": "Propuesta pedagógica editable generada por SmartTeacher AI para contextualización y adecuación del docente."
        }
        return result

    @classmethod
    def parse_session_markdown_to_structure(
        cls,
        raw_text: str,
        topic: str,
        grade: int,
        specialty: str,
        duration_minutes: int = 90,
        competence: str = "Gestiona proyectos de emprendimiento económico o social",
        purpose: str = "",
        teacher_name: str = "Docente",
        section_name: str = "A",
        difficulty: str = "intermedio",
        observations: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses session markdown into a modular semantic structure with phases, safety, and rubric.
        """
        text = raw_text or ""
        
        # Calculate proportional minutes for phases
        min_inicio = max(10, int(duration_minutes * 0.15))
        min_cierre = max(10, int(duration_minutes * 0.15))
        min_desarrollo = max(20, duration_minutes - min_inicio - min_cierre)

        # Extraction regexes for 3 didactic phases
        inicio_match = re.search(r'(?:(?:###?|\d+\.?\s*\*+)\s*(?:FASE\s*1:?\s*|MOMENTO\s*DE\s*)?INICIO[\s\S]*?)(?=(?:###?|\d+\.?\s*\*+)\s*(?:FASE\s*2:?\s*|MOMENTO\s*DE\s*)?DESARROLLO|\Z)', text, re.IGNORECASE)
        desarrollo_match = re.search(r'(?:(?:###?|\d+\.?\s*\*+)\s*(?:FASE\s*2:?\s*|MOMENTO\s*DE\s*)?DESARROLLO[\s\S]*?)(?=(?:###?|\d+\.?\s*\*+)\s*(?:FASE\s*3:?\s*|MOMENTO\s*DE\s*)?CIERRE|\Z)', text, re.IGNORECASE)
        cierre_match = re.search(r'(?:(?:###?|\d+\.?\s*\*+)\s*(?:FASE\s*3:?\s*|MOMENTO\s*DE\s*)?CIERRE[\s\S]*?)(?=(?:###?|\d+\.?\s*\*+)\s*(?:(?:IV|V|VI|4|5|6)\.|\n##\s*|ACTIVIDAD|INSTRUMENTO|RÚBRICA|RUBRICA|NOTA|---)|\Z)', text, re.IGNORECASE)
        
        inicio_text = inicio_match.group(0).strip() if inicio_match else (
            f"1. Motivación y Saberes Previos ({min_inicio} min): El docente presenta un desafío real de taller o problema del entorno vinculado a {topic}.\n"
            f"2. Conflicto Cognitivo / Reto: ¿Cómo podemos realizar {topic} con precisión técnica garantizando la seguridad en el taller?\n"
            f"3. Propósito y Criterios: {purpose or f'Desarrollar habilidades operativas y conceptuales sobre {topic}'}."
        )

        desarrollo_text = desarrollo_match.group(0).strip() if desarrollo_match else (
            f"1. Demostración y Modelado Docente ({int(min_desarrollo*0.3)} min): El docente ejecuta la técnica paso a paso frente a los estudiantes enfatizando puntos críticos de control.\n"
            f"2. Práctica Guiada por Cuadrillas ({int(min_desarrollo*0.7)} min): Los estudiantes operan en sus puestos aplicando la técnica modelada con supervisión formativa continua y retroalimentación in situ."
        )

        cierre_text = cierre_match.group(0).strip() if cierre_match else (
            f"1. Metacognición y Evaluación Formativa ({min_cierre} min): ¿Qué aprendimos hoy sobre {topic}? ¿Qué dificultades operativas se presentaron y cómo las solucionamos?\n"
            f"2. Protocolo 5S de Taller: Desconexión segura de equipos, limpieza de puestos, conteo y guardado de herramientas en pañol."
        )

        # Extraction or fallback for workshop safety
        epp_text = "Lentes de seguridad con protección lateral, calzado de seguridad con punta de acero, mameluco o guardapolvo institucional de taller, guantes adecuados según la operación."
        normas_5s = "Seiri (Clasificar), Seiton (Ordenar), Seiso (Limpiar), Seiketsu (Estandarizar), Shitsuke (Disciplina). Prohibido uso de accesorios colgantes o cabello suelto cerca de partes móviles."

        # Structured rubric items
        rubric_items = [
            {
                "criterio": f"Aplicación de Habilidades Técnicas en {topic}",
                "ad": f"Ejecuta la técnica de {topic} con precisión sobresaliente, autonomía y optimización de materiales.",
                "a": f"Ejecuta la técnica de {topic} siguiendo el procedimiento técnico establecido y las tolerancias requeridas.",
                "b": f"Aplica la técnica de {topic} con dudas menores, requiriendo supervisión ocasional del docente.",
                "c": f"Dificultades notorias para aplicar la técnica; no cumple el procedimiento básico sin asistencia constante."
            },
            {
                "criterio": "Seguridad Industrial y Metodología 5S",
                "ad": "Usa EPP completo reglamentario, previene riesgos proactivamente y mantiene su puesto impecable (5S).",
                "a": "Usa EPP adecuadamente durante toda la sesión y deja su área de trabajo ordenada y limpia.",
                "b": "Requiere recordatorios para mantener colocado el EPP o completar la limpieza de su puesto.",
                "c": "Incumple normas elementales de seguridad de taller o abandona su puesto de trabajo desordenado."
            },
            {
                "criterio": "Trabajo Cooperativo y Responsabilidad en Taller",
                "ad": "Lidera su cuadrilla con empatía, fomenta la disciplina y promueve el cuidado de los equipos.",
                "a": "Colabora activamente con sus compañeros de equipo y cuida las herramientas asignadas.",
                "b": "Participa pasivamente en el equipo o delega tareas de mayor esfuerzo a sus compañeros.",
                "c": "Genera distracciones en el taller, no colabora con su cuadrilla o hace mal uso de las herramientas."
            }
        ]

        seguridad_str = f"EPP Obligatorio:\n{epp_text}\n\nProtocolo 5S de Taller:\n{normas_5s}"
        rubrica_str = "RÚBRICA ANALÍTICA DE EVALUACIÓN CNEB:\n" + "\n".join(
            [f"- {r['criterio']}:\n  * AD: {r['ad']}\n  * A: {r['a']}\n  * B: {r['b']}\n  * C: {r['c']}" for r in rubric_items]
        )

        # Materials extraction or fallback
        mat_match = re.search(r'(?:###?\s*(?:(?:III|3)\.?)?\s*MATERIALES[\s\S]*?)(?=###?\s*(?:(?:IV|4)\.|SECUENCIA|MOMENTO|INICIO|ACTIVIDAD)|\Z)', text, re.IGNORECASE)
        materiales_str = mat_match.group(0).strip() if mat_match else (
            f"- Herramientas, máquinas o instrumentos propios de {specialty}.\n"
            f"- Ficha técnica de proceso y guía de aprendizaje sobre {topic}.\n"
            f"- Equipo de Protección Personal (EPP reglamentario de taller).\n"
            f"- Pizarra acrílica, plumones y materiales fungibles de práctica."
        )

        # Product / activity extraction or fallback
        act_match = re.search(r'(?:###?\s*(?:(?:V|5)\.?)?\s*ACTIVIDAD[\s\S]*?)(?=###?\s*(?:(?:VI|6)\.|SEGURIDAD|5S|INSTRUMENTO|RÚBRICA|RUBRICA|ADAPTACIONES)|\Z)', text, re.IGNORECASE)
        actividad_str = act_match.group(0).strip() if act_match else (
            f"Elaboración de la pieza o ejecución del proceso técnico de {topic}, "
            f"completando la hoja de operaciones y verificación dimensional con normas de calidad y seguridad."
        )

        # Adaptations extraction or fallback
        adap_match = re.search(r'(?:###?\s*(?:(?:VIII|8)\.?)?\s*ADAPTACIONES[\s\S]*?)(?=###?\s*(?:---|NOTA|PROPUESTA)|\Z)', text, re.IGNORECASE)
        adaptaciones_str = adap_match.group(0).strip() if adap_match else (
            f"1. Enfoque DUA (Múltiples formas de representación): Guías gráficas ilustradas y demostración técnica modelada paso a paso.\n"
            f"2. Nivelación y Andamiaje: Cuadrillas colaborativas mixtas y retroalimentación personalizada durante el desarrollo de la práctica.\n"
            f"3. Enriquecimiento / Extensión: Actividades de optimización o mayor precisión técnica para estudiantes con ritmo avanzado."
        )

        return {
            "datos_informativos": {
                "institucion": "I.E. INEI N.º 34 de Chancay",
                "area_especialidad": specialty,
                "grado": grade,
                "seccion": section_name,
                "duracion_minutos": duration_minutes,
                "dificultad": difficulty,
                "observaciones": observations or "",
                "docente": teacher_name,
                "fecha": "2026",
                "tema": topic
            },
            "propositos_aprendizaje": competence,
            "propositos": {
                "competencia": competence,
                "capacidades": "Crea propuestas de valor / Aplica habilidades técnicas / Trabaja cooperativamente / Evalúa resultados",
                "desempeno": f"Planifica y ejecuta procesos de producción técnica aplicando normas de calidad y seguridad en {topic}.",
                "evidencia": f"Ficha de proceso técnico desarrollada y producto/muestra práctica de {topic}.",
                "proposito_sesion": purpose or f"Desarrollar habilidades operativas y conceptuales en {topic}."
            },
            "materiales_recursos": materiales_str,
            "secuencia_didactica": {
                "inicio": inicio_text,
                "desarrollo": desarrollo_text,
                "cierre": cierre_text
            },
            "actividad_producto": actividad_str,
            "seguridad_industrial_5s": seguridad_str,
            "seguridad_industrial": {
                "epp": epp_text,
                "normas_5s": normas_5s,
                "contenido": seguridad_str
            },
            "criterios_evaluacion": f"Aplica habilidades técnicas en {topic}, respeta normas de seguridad en taller y verifica la calidad del producto final.",
            "evaluacion_rubrica": rubrica_str,
            "evaluacion": {
                "instrumento": "Rúbrica Analítica CNEB (Escala Ministerial AD - A - B - C)",
                "rubrica": rubric_items,
                "contenido": rubrica_str
            },
            "adaptaciones_apoyos": adaptaciones_str,
            "nota_pedagogica": "Propuesta pedagógica editable elaborada por SmartTeacher AI bajo los lineamientos del CNEB y Educación Técnica. Queda sujeta a la revisión, adecuación contextual y firma del docente titular de la I.E. INEI N.º 34."
        }

    @classmethod
    def generate_cneb_session_structured(
        cls,
        user: Dict[str, Any],
        topic: str,
        grade: int,
        specialty: str,
        duration_minutes: int = 90,
        competence: Optional[str] = None,
        purpose: Optional[str] = None,
        learning_purpose: Optional[str] = None,
        section_name: str = "A",
        difficulty: str = "intermedio",
        observations: Optional[str] = None,
        evaluation_criteria: Optional[str] = None,
        learning_evidence: Optional[str] = None,
        methodology: Optional[str] = None,
        structure_mode: Optional[str] = "institucional",
        unit_id: Optional[int] = None,
        unit_title: Optional[str] = None,
        week_number: Optional[int] = None,
        session_number: Optional[int] = None,
        session_type: Optional[str] = None,
        confirm_time_action: Optional[str] = None,
        custom_stages: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera un borrador completo de sesión de aprendizaje CNEB/EPT estructurado semánticamente en JSON y Markdown.
        Diferencia pertinentemente:
        - Sesiones Técnicas de Taller (Metodología GTZ - Acción Completa, 5h / 225 min).
        - Sesiones de Emprendimiento (Enfoque Design Thinking / Lean Canvas, 3h / 135 min).
        - Sesiones Generales CNEB (Inicio, Desarrollo, Cierre para áreas no-EPT o solicitud libre).
        Soporta modo institucional CET N.º 34 o formato libre modular, sin copiar datos personales ajenos.
        Detecta discrepancias de tiempo y ofrece opciones de resolución interactiva.
        """
        if not purpose and learning_purpose:
            purpose = learning_purpose
        cleaned_topic = (topic or "").strip()
        cleaned_specialty = (specialty or "Educación para el Trabajo").strip()
        cleaned_diff = (difficulty or "intermedio").strip().lower()
        cleaned_obs = (observations or "").strip() or None
        spec_lower = cleaned_specialty.lower()

        # Resolución inteligente del contexto curricular CNEB
        from app.ai.curriculum_knowledge import resolve_curriculum_context
        curr_info = resolve_curriculum_context(topic=cleaned_topic, grade=grade, specialty=cleaned_specialty)

        # Si la especialidad era genérica o por defecto y el tema pertenece a otra área curricular oficial
        if (not specialty or specialty.strip() in ["Educación para el Trabajo", "General", ""]) and not curr_info["is_ept"]:
            cleaned_specialty = curr_info["area"]
            spec_lower = cleaned_specialty.lower()

        # Determinar si la especialidad pertenece al área técnica EPT
        is_ept = curr_info["is_ept"] or "educación para el trabajo" in spec_lower or "ept" in spec_lower or any(
            k in spec_lower for k in ["computaci", "mecan", "electr", "metal", "vestid", "conta"]
        )

        # Resolver el tipo de sesión y metodología
        req_type = (session_type or "").strip().lower()
        req_meth = (methodology or "").strip().lower()
        topic_lower = cleaned_topic.lower()
        obs_lower = (cleaned_obs or "").lower()

        if req_type in ["tecnica", "tecnica_especifica", "taller"]:
            resolved_type = "tecnica"
        elif req_type in ["emprendimiento", "gestion_proyectos", "lean_canvas"]:
            resolved_type = "emprendimiento"
        elif req_type in ["general", "cneb_general", "libre"]:
            resolved_type = "general"
        else:
            # Detección contextual por contenido y área
            if not is_ept:
                resolved_type = "general"
            elif any(k in req_meth or k in topic_lower or k in obs_lower for k in [
                "lean canvas", "design thinking", "emprendimiento", "startup", "validación", "validacion", "modelo de negocio", "canvas"
            ]):
                resolved_type = "emprendimiento"
            elif any(k in req_meth or k in topic_lower or k in obs_lower for k in [
                "gtz", "acción completa", "accion completa", "taller", "laboratorio", "mecanizado", "torno", "soldadura", "operaciones"
            ]):
                resolved_type = "tecnica"
            else:
                resolved_type = "tecnica" if is_ept else "general"

        # Competencias oficiales CNEB verificadas (MINEDU)
        OFFICIAL_CNEB_LIST = [
            "Gestiona proyectos de emprendimiento económico o social",
            "Se desenvuelve en los entornos virtuales generados por las TIC",
            "Gestiona su aprendizaje de manera autónoma",
            "Resuelve problemas de cantidad",
            "Resuelve problemas de regularidad, equivalencia y cambio",
            "Resuelve problemas de forma, movimiento y localización",
            "Resuelve problemas de gestión de datos e incertidumbre",
            "Se comunica oralmente en su lengua materna",
            "Lee diversos tipos de textos escritos en su lengua materna",
            "Escribe diversos tipos de textos en su lengua materna",
            "Indaga mediante métodos científicos para construir conocimientos",
            "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
            "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno",
            "Construye su identidad",
            "Convive y participa democráticamente en la búsqueda del bien común",
            "Construye interpretaciones históricas",
            "Gestiona responsablemente el espacio y el ambiente",
            "Gestiona responsablemente los recursos económicos",
            "Aprecia de manera crítica manifestaciones artístico-culturales",
            "Crea proyectos desde los lenguajes artísticos",
            "Asume una vida saludable",
            "Interactúa a través de sus habilidades sociomotrices",
            "Se desenvuelve de manera autónoma a través de su motricidad"
        ]
        default_comp = curr_info["competencia"]
        cleaned_competence = (competence or default_comp).strip()

        # Detección contextual de especialidad digital / informática vs taller industrial
        is_digital_topic = any(k in topic_lower for k in [
            "carpeta digital", "carpetas digitales", "archivos", "archivo", "ofimática", "ofimatica",
            "nube", "google drive", "computación", "computacion", "informática", "informatica",
            "software", "hoja de cálculo", "hojas de cálculo", "excel", "sistema operativo",
            "almacenamiento en la nube", "seguridad digital", "gestión de archivos", "gestion de archivos"
        ])
        is_digital_spec = any(k in spec_lower for k in ["comput", "inform", "digital"])
        is_digital = is_digital_spec or is_digital_topic

        cleaned_purpose = (purpose or "").strip()
        if not cleaned_purpose or cleaned_purpose.lower().startswith("desarrollar capacidades y habilidades formativas sobre"):
            if not is_ept:
                cleaned_purpose = curr_info["proposito"]
            elif is_digital:
                cleaned_purpose = f"Comprender y aplicar criterios técnicos para organizar, clasificar, respaldar y gestionar carpetas y archivos digitales de manera estructurada y segura, optimizando el acceso y la conservación de la información en entornos locales y en la nube."
            elif resolved_type == "emprendimiento":
                cleaned_purpose = f"Analizar, validar y ajustar la propuesta de valor y el modelo de negocio mediante el lienzo Lean Canvas para {cleaned_topic}, tomando decisiones estratégicas basadas en evidencias empíricas recogidas de usuarios reales."
            else:
                cleaned_purpose = f"Comprender los principios técnicos, normas de seguridad y secuencia operativa estandarizada para {cleaned_topic}, ejecutando las tareas prácticas con precisión, orden y control de calidad (5S)."
        else:
            cleaned_purpose = cleaned_purpose.strip()

        if not evaluation_criteria:
            evaluation_criteria = curr_info.get("criterio")

        is_official_comp = any(c.lower() in cleaned_competence.lower() for c in OFFICIAL_CNEB_LIST)
        comp_display = f"{cleaned_competence} (Competencia Oficial CNEB)" if is_official_comp else f"{cleaned_competence} [Sugerencia pedagógica editable / Por confirmar]"

        # Metodología didáctica
        if methodology:
            metodo_didactico = methodology.strip()
        elif resolved_type == "tecnica":
            metodo_didactico = "Aprendizaje por la acción completa (GTZ)"
        elif resolved_type == "emprendimiento":
            metodo_didactico = "Enfoque de Design Thinking (Pensamiento de diseño) / Lean Canvas"
        else:
            metodo_didactico = "Enfoque por competencias CNEB"

        # Duración pedagógica sugerida si vino en default 90 y es de taller o emprendimiento
        if duration_minutes == 90 and kwargs.get("auto_set_duration", False):
            if resolved_type == "tecnica":
                duration_minutes = 225
            elif resolved_type == "emprendimiento":
                duration_minutes = 135

        raw_res = cls.generate_cneb_session(
            user=user,
            topic=cleaned_topic,
            grade=grade,
            specialty=cleaned_specialty,
            duration_minutes=duration_minutes,
            competence=cleaned_competence,
            purpose=cleaned_purpose,
            difficulty=cleaned_diff,
            observations=cleaned_obs
        )

        teacher_param = kwargs.get("teacher_name") or user.get("full_name") or user.get("username") or "Docente Responsable"
        from app.ai.template_engine import template_engine
        is_verified_teacher, clean_teacher = template_engine.resolve_verified_teacher(teacher_param)
        final_teacher = clean_teacher if is_verified_teacher else teacher_param
        teacher_name = final_teacher
        structured_json = cls.parse_session_markdown_to_structure(
            raw_text=raw_res.get("content", ""),
            topic=cleaned_topic,
            grade=grade,
            specialty=cleaned_specialty,
            duration_minutes=duration_minutes,
            competence=cleaned_competence,
            purpose=cleaned_purpose,
            teacher_name=teacher_name,
            section_name=section_name,
            difficulty=cleaned_diff,
            observations=cleaned_obs
        )

        title = f"Sesión de Aprendizaje N° {session_number or '01'}: {cleaned_topic} ({grade}° Sec. - {cleaned_specialty})"
        grade_words = {1: "Primer", 2: "Segundo", 3: "Tercer", 4: "Cuarto", 5: "Quinto"}
        grade_str = grade_words.get(grade, f"{grade}°")

        # Detección contextual de especialidad digital / informática vs taller industrial
        is_digital_topic = any(k in topic_lower for k in [
            "carpeta digital", "carpetas digitales", "archivos", "archivo", "ofimática", "ofimatica",
            "nube", "google drive", "computación", "computacion", "informática", "informatica",
            "software", "hoja de cálculo", "hojas de cálculo", "excel", "sistema operativo",
            "almacenamiento en la nube", "seguridad digital", "gestión de archivos", "gestion de archivos"
        ])
        is_digital_spec = any(k in spec_lower for k in ["comput", "inform", "digital"])
        is_digital = is_digital_spec or is_digital_topic

        # Si el tema es claramente digital y la especialidad vino genérica o por defecto de taller, ajustar
        if is_digital:
            spec_prog = "Computación e Informática"
            mod_form = "Aplica herramientas de productividad, almacenamiento y colaboración en la nube"
            jefe_taller = "Mg. Luis Arturo La Rosa Gallardo"
            jefe_cargo = "Jefe de Taller Computación e Informática"
            if is_digital_topic and ("mecan" in spec_lower or "general" in spec_lower or "educación para el trabajo" in spec_lower):
                cleaned_specialty = "Computación e Informática"
                spec_lower = cleaned_specialty.lower()
        elif "mecan" in spec_lower or "torno" in spec_lower:
            spec_prog = "Mecánica de Producción"
            mod_form = "Mecanizado de piezas por arranque de viruta en máquinas herramientas y soldadura"
            jefe_taller = "Prof. Responsable de Taller de Mecánica"
            jefe_cargo = "Jefe de Taller Mecánica de Producción"
        elif "electr" in spec_lower:
            spec_prog = "Electricidad y Electrónica"
            mod_form = "Instalaciones eléctricas residenciales, industriales y control electrónico de potencia"
            jefe_taller = "Prof. Responsable de Taller de Electricidad"
            jefe_cargo = "Jefe de Taller Electricidad y Electrónica"
        elif "metal" in spec_lower or "construc" in spec_lower:
            spec_prog = "Construcciones Metálicas"
            mod_form = "Trazado, corte, conformado y soldadura de estructuras metálicas normalizadas"
            jefe_taller = "Prof. Responsable de Taller de Construcciones Metálicas"
            jefe_cargo = "Jefe de Taller Construcciones Metálicas"
        elif "vestid" in spec_lower or "textil" in spec_lower:
            spec_prog = "Industria del Vestido"
            mod_form = "Patronaje, corte, confección y acabado industrial de prendas de vestir"
            jefe_taller = "Prof. Responsable de Taller de Industria del Vestido"
            jefe_cargo = "Jefe de Taller Industria del Vestido"
        elif "conta" in spec_lower:
            spec_prog = "Contabilidad"
            mod_form = "Gestión de procesos contables, tributarios y comerciales de la micro y pequeña empresa"
            jefe_taller = "Prof. Responsable de Especialidad de Contabilidad"
            jefe_cargo = "Coordinador de Especialidad Contabilidad"
        else:
            if is_ept:
                spec_prog = cleaned_specialty
                mod_form = f"Desarrollo de módulos formativos y competencias técnicas de {cleaned_topic}"
                jefe_taller = "Jefe de Taller de Especialidad"
                jefe_cargo = f"Jefe de Taller {cleaned_specialty}"
            else:
                spec_prog = cleaned_specialty
                mod_form = f"Desarrollo de competencias curriculares vinculadas a {cleaned_topic}"
                jefe_taller = "Prof. Coordinador(a) Pedagógico(a)"
                jefe_cargo = f"Coordinador(a) Pedagógico(a) de {cleaned_specialty}"

        # Procesamiento y validación de tiempos por fases
        warning_time_discrepancy = None

        if custom_stages and isinstance(custom_stages, list) and len(custom_stages) > 0:
            # Se proporcionaron etapas específicas personalizadas por el docente
            val_custom = cls.validate_session_stage_times(
                stages=custom_stages,
                expected_minutes=duration_minutes,
                confirm_action=confirm_time_action
            )
            if confirm_time_action == "sync_header":
                duration_minutes = val_custom["expected_minutes"]
            elif confirm_time_action == "sync_stages":
                custom_stages = val_custom["adjusted_stages"]

            if val_custom.get("has_discrepancy") and not confirm_time_action:
                warning_time_discrepancy = val_custom

            procesos_steps = custom_stages
            t_inf = val_custom["adjusted_stages"][0].get("tiempo_minutos", 15) if len(val_custom["adjusted_stages"]) > 0 else 15
            t_plan = val_custom["adjusted_stages"][1].get("tiempo_minutos", 20) if len(val_custom["adjusted_stages"]) > 1 else 20
            t_dec = val_custom["adjusted_stages"][2].get("tiempo_minutos", 20) if len(val_custom["adjusted_stages"]) > 2 else 20
            t_ejec = val_custom["adjusted_stages"][3].get("tiempo_minutos", 50) if len(val_custom["adjusted_stages"]) > 3 else 50
            t_cont = val_custom["adjusted_stages"][4].get("tiempo_minutos", 15) if len(val_custom["adjusted_stages"]) > 4 else 15
            t_eval = val_custom["adjusted_stages"][5].get("tiempo_minutos", 15) if len(val_custom["adjusted_stages"]) > 5 else 15
        else:
            # Determinación determinista y exacta de tiempos de etapa según el tipo de sesión
            if resolved_type == "tecnica":
                # Referencia real: Sesion_01_Gestionamos_nuestra_carpeta_digital.docx (5h / 225 min exactos)
                if duration_minutes == 225:
                    t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 10, 20, 30, 135, 20, 10
                else:
                    t_inf = max(5, int(duration_minutes * 0.08))
                    t_plan = max(10, int(duration_minutes * 0.12))
                    t_dec = max(10, int(duration_minutes * 0.15))
                    t_cont = max(5, int(duration_minutes * 0.10))
                    t_eval = max(5, int(duration_minutes * 0.08))
                    t_ejec = duration_minutes - (t_inf + t_plan + t_dec + t_cont + t_eval)
            elif resolved_type == "emprendimiento":
                # Referencia real: Sesion_01_Mejoramos_nuestro_Lean_Canvas.docx (3h / 135 min exactos)
                if duration_minutes == 135:
                    t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 15, 20, 20, 50, 15, 15
                elif duration_minutes == 225:
                    # Caso del documento de muestra donde se sumaron 225m:
                    t_inf, t_plan, t_dec, t_ejec, t_cont, t_eval = 30, 30, 25, 80, 25, 35
                else:
                    t_inf = max(10, int(duration_minutes * 0.15))
                    t_plan = max(10, int(duration_minutes * 0.15))
                    t_dec = max(10, int(duration_minutes * 0.15))
                    t_cont = max(10, int(duration_minutes * 0.12))
                    t_eval = max(10, int(duration_minutes * 0.12))
                    t_ejec = duration_minutes - (t_inf + t_plan + t_dec + t_cont + t_eval)
            else:
                # Sesión general CNEB
                t_ini = max(10, int(duration_minutes * 0.15))
                t_cie = max(10, int(duration_minutes * 0.15))
                t_des = duration_minutes - (t_ini + t_cie)
                t_inf = t_ini
                t_plan = 0
                t_dec = 0
                t_ejec = t_des
                t_cont = 0
                t_eval = t_cie

        ped_hours = max(1, round(duration_minutes / 45))

# Criterios y evidencias
        if resolved_type == "tecnica":
            if is_digital:
                default_crit = "Organiza una carpeta digital aplicando criterios de estructura jerárquica, nombres adecuados, eliminación segura de duplicados y uso responsable del almacenamiento en la nube."
                default_evid = "Carpeta digital organizada y depurada que cumple los criterios de gestión de archivos y seguridad digital."
            else:
                default_crit = f"Aplica habilidades técnicas en {cleaned_topic}, respeta normas de seguridad 5S y verifica la calidad del producto final mediante lista de verificación técnica."
                default_evid = f"Ficha de operaciones y producto técnico de {cleaned_topic} terminado según especificaciones."
        elif resolved_type == "emprendimiento":
            default_crit = f"Realiza modificaciones pertinentes en los bloques del Lean Canvas considerando evidencias obtenidas durante la validación con usuarios."
            default_evid = f"Lienzo Lean Canvas actualizado y mejorado con hipótesis validadas y sustentación del equipo."
        else:
            default_crit = f"Demuestra el desarrollo de capacidades en {cleaned_topic} aplicando criterios de calidad y reflexión metacognitiva."
            default_evid = f"Producto o evidencia de aprendizaje de {cleaned_topic} completada."

        crit_text = (evaluation_criteria or "").strip() or default_crit
        evid_text = (learning_evidence or "").strip() or default_evid
        structured_json.setdefault("propositos", {})["evidencia"] = evid_text
        structured_json["criterios_evaluacion"] = crit_text

        # Redacción de actividades según el modelo pedagógico específico
        if resolved_type == "emprendimiento":
            # Modelo de referencia: Sesion_01_Mejoramos_nuestro_Lean_Canvas.docx
            act_doc_inf = f"Inicia recordando las actividades previas: formulación de hipótesis iniciales y entrevistas con clientes respecto a {cleaned_topic}. Plantea la situación: 'Al dialogar con los usuarios descubrimos aciertos pero también aspectos a reformular. ¿Debemos mantener nuestro Lean Canvas idéntico o adaptarlo a las necesidades reales?'. Explica que la validación empírica genera aprendizajes para iterar la propuesta de valor."
            act_est_inf = f"Recuerda las hipótesis planteadas en su equipo y los datos recopilados en las entrevistas o encuestas sobre {cleaned_topic}. Identifica qué información confirmó o refutó las suposiciones iniciales y analiza las necesidades no satisfechas de los usuarios."

            act_doc_plan = f"Orienta a los equipos para revisar los 9 bloques del Lean Canvas actual. Entrega una ficha de análisis de validación con preguntas estratégicas: ¿Qué problema fue confirmado?, ¿qué descubrimos sobre los usuarios?, ¿nuestra solución responde a su necesidad?, ¿qué bloques debemos ajustar?"
            act_est_plan = f"En equipos de trabajo, revisa su Lean Canvas y clasifica la información obtenida durante la validación. Identifica los bloques que requieren cambios y planifica la secuencia de modificaciones que realizarán."

            act_doc_dec = f"Solicita que cada equipo determine los cambios específicos a realizar en los bloques del lienzo y justifique sus decisiones frente a alternativas viables, basándose exclusivamente en evidencias de clientes y no en suposiciones."
            act_est_dec = f"Analiza las opciones de mejora, debate en equipo y decide qué bloques del Lean Canvas se modificarán (propuesta de valor, canales, flujos de ingresos o segmentos), justificando sus elecciones técnicas y comerciales."

            act_doc_ejec = f"Acompaña permanentemente a los equipos durante la actualización del Lean Canvas (físico con post-its o digital). Revisa la redacción de las nuevas hipótesis, resuelve dudas sobre la articulación entre propuesta de valor y canales, y orienta la estimación de costos e ingresos."
            act_est_ejec = f"Actualiza su lienzo Lean Canvas, redacta las nuevas hipótesis validadas, ajusta la propuesta de valor y los canales de distribución, y registra en su ficha de trabajo los aprendizajes validados del emprendimiento."

            act_doc_cont = f"Revisa la coherencia del Lean Canvas mejorado mediante una lista de verificación. Comprueba que las modificaciones respondan a evidencias reales y orienta la coevaluación entre equipos con preguntas reflexivas."
            act_est_cont = f"Verifica que los cambios en su lienzo guarden coherencia interna, intercambia impresiones con otro equipo para recibir retroalimentación y realiza ajustes de precisión antes de la presentación final."

            act_doc_eval = f"Conduce la plenaria de sustentación de los lienzos mejorados. Promueve la reflexión metacognitiva: ¿Cómo influyó la opinión de los usuarios en el emprendimiento? ¿Qué fue lo más retador de iterar? Evalúa el desempeño y los compromisos del equipo."
            act_est_eval = f"Presenta y sustenta el Lean Canvas actualizado explicando los aprendizajes de la validación, y reflexiona sobre sus logros, dificultades y próximos pasos para la viabilidad de su propuesta emprendedora."

            sit_sig = (
                f"En la I.E. INEI N.º 34 de Chancay, los estudiantes del {grade_str.lower()} grado de secundaria en {spec_prog} "
                f"vienen desarrollando proyectos de emprendimiento vinculados a las oportunidades del polo de desarrollo y comercial del distrito. "
                f"Tras una primera etapa de ideación, los equipos interactuaron con potenciales usuarios para validar sus hipótesis sobre {cleaned_topic}, "
                f"descubriendo que algunas ideas iniciales no respondían completamente a las demandas reales del mercado.\n\n"
                f"Ante esta situación, nos planteamos los siguientes retos:\n"
                f"- ¿Cómo podemos incorporar las evidencias de los usuarios para mejorar nuestra propuesta de valor en el Lean Canvas?\n"
                f"- ¿De qué manera la toma de decisiones basada en datos previene pérdidas de tiempo y recursos en nuestro proyecto?\n"
                f"- ¿Cómo demostramos la viabilidad, sostenibilidad y responsabilidad social de nuestro emprendimiento en la comunidad de Chancay?"
            )
        elif resolved_type == "tecnica":
            if is_digital:
                # Modelo de referencia oficial: sesion_tecnica_gtz_cet34.docx (Acción Completa GTZ - CET 34 Chancay)
                act_doc_inf = "Presenta una situación problemática: los estudiantes tienen muchos archivos desordenados, con nombres poco claros y documentos duplicados. Formula preguntas: ¿Cómo podemos encontrar rápidamente un archivo? ¿Qué problemas genera tener documentos duplicados? Explica los criterios para organizar, nombrar y depurar archivos y carpetas."
                act_est_inf = "Observa la situación problemática presentada, responde las preguntas, comparte sus saberes previos y experiencias, y reconoce la importancia de mantener sus archivos digitales ordenados y seguros."

                act_doc_plan = "Orienta a los estudiantes para elaborar un plan de organización de sus archivos. Indica que deben establecer carpetas principales y subcarpetas, definir nombres claros y determinar cómo identificar los archivos duplicados."
                act_est_plan = "Elabora un plan de trabajo en el que establece los pasos para organizar sus archivos, propone nombres para las carpetas y selecciona criterios para identificar documentos duplicados."

                act_doc_dec = "Solicita que cada estudiante determine la estructura de carpetas que utilizará y los criterios para nombrar, clasificar y depurar sus archivos. Supervisa las decisiones y brinda orientación cuando sea necesario."
                act_est_dec = "Decide cómo organizará su espacio digital, qué nombres utilizará, dónde guardará cada archivo y cuáles documentos duplicados puede eliminar después de verificar su contenido."

                act_doc_ejec = "Demuestra cómo crear carpetas y subcarpetas, cambiar nombres, mover archivos, identificar duplicados y eliminarlos de forma segura. Acompaña a los estudiantes durante la práctica y resuelve sus dudas."
                act_est_ejec = "Organiza su carpeta digital en la nube, crea subcarpetas, cambia los nombres poco claros, mueve los archivos a sus ubicaciones correspondientes e identifica y depura duplicados, conservando las versiones necesarias."

                act_doc_cont = "Revisa el trabajo de los estudiantes mediante una lista de cotejo. Verifica que las carpetas estén organizadas, los nombres sean adecuados y los duplicados se hayan gestionado correctamente. Proporciona retroalimentación."
                act_est_cont = "Comprueba que sus archivos estén en las carpetas correctas, verifica los nombres asignados, revisa que no haya duplicados innecesarios y corrige los errores encontrados."

                act_doc_eval = "Promueve la reflexión mediante preguntas: ¿Qué aprendiste? ¿Qué dificultad encontraste? ¿Cómo te ayudará esta organización en tus actividades escolares? Evalúa el producto final y el cumplimiento del propósito de aprendizaje."
                act_est_eval = "Presenta su carpeta digital organizada, explica los procedimientos realizados y reflexiona sobre sus aprendizajes, dificultades y compromisos para mantener ordenada su información digital."

                sit_sig = (
                    f"En la institución educativa CET N.º 34 (I.E. INEI N.º 34) de Chancay, se ha observado que muchos estudiantes del {grade_str.lower()} grado de secundaria "
                    f"en el programa formativo de {spec_prog} tienen dificultades para organizar y gestionar sus archivos digitales. Acumulan documentos con nombres poco claros "
                    f"(ej. 'documento1', 'tarea_final'), carpetas desorganizadas, archivos duplicados que saturan el almacenamiento y falta de respaldo seguro.\n\n"
                    f"Ante esta situación, nos planteamos los siguientes retos:\n"
                    f"- ¿Cómo podemos organizar nuestros archivos digitales para encontrarlos de manera rápida y sencilla?\n"
                    f"- ¿Qué buenas prácticas debemos aplicar al crear carpetas, nombrar archivos y evitar documentos duplicados?\n"
                    f"- ¿De qué manera el uso responsable y seguro de las plataformas de almacenamiento en la nube puede mejorar nuestro trabajo escolar y proteger nuestra información?"
                )
            else:
                # Taller técnico industrial (Mecánica de Producción, Electricidad, Construcciones Metálicas)
                act_doc_inf = f"Presenta una situación problemática del entorno de taller o laboratorio relacionada con {cleaned_topic}. Formula preguntas desafiantes sobre la calidad técnica y la prevención de errores comunes. Explica las especificaciones técnicas, tolerancias y normas de seguridad industrial y protocolos 5S."
                act_est_inf = f"Observa la situación problemática presentada, responde a las preguntas orientadoras, comparte sus saberes previos y experiencias operativas, y reconoce la importancia de aplicar correctamente {cleaned_topic} con seguridad y eficiencia."

                act_doc_plan = f"Orienta a los estudiantes en la elaboración de su plan de trabajo u hoja de operaciones. Explica cómo definir la secuencia de pasos, seleccionar herramientas, máquinas e instrumentos de medición, y calcular tiempos de ejecución."
                act_est_plan = f"En equipos o de forma individual, elabora su plan de operaciones detallando la secuencia técnica ordenada para realizar {cleaned_topic}, seleccionando las herramientas necesarias y definiendo criterios de calidad."

                act_doc_dec = f"Solicita a los estudiantes que determinen el procedimiento técnico específico y justifiquen sus elecciones frente a alternativas viables. Supervisa la decisión y orienta hacia la eficiencia, el ahorro de material y la seguridad."
                act_est_dec = f"Decide la estrategia técnica operativa, selecciona parámetros óptimos de ejecución (medidas, configuraciones o tolerancias) y distribuye responsabilidades en su puesto de trabajo justificando sus elecciones técnicas."

                act_doc_ejec = f"Demuestra el modelado técnico paso a paso en el puesto de trabajo. Acompaña permanentemente la práctica de los estudiantes en taller/laboratorio, supervisa el uso estricto del EPP y el cumplimiento de las normas 5S, y resuelve dudas operativas in situ."
                act_est_ejec = f"Ejecuta el procedimiento técnico de {cleaned_topic} en el taller o laboratorio aplicando las normas de seguridad e higiene, opera las herramientas o máquinas con precisión y registra sus avances en su hoja de operaciones."

                act_doc_cont = f"Supervisa el avance y producto técnico mediante una lista de cotejo técnica. Verifica que los archivos, esquemas o piezas cumplan con las especificaciones y tolerancias requeridas. Brinda retroalimentación formativa inmediata."
                act_est_cont = f"Comprueba que su trabajo cumpla con las especificaciones técnicas de la guía, verifica dimensiones con instrumentos de medición o comprobación, identifica desviaciones y ejecuta correcciones autónomas."

                act_doc_eval = f"Promueve la reflexión metacognitiva: ¿Qué aprendiste hoy en el taller? ¿Qué dificultades operativas se presentaron y cómo las resolviste? Evalúa el producto final y el logro del propósito formativo con el instrumento de evaluación."
                act_est_eval = f"Presenta su producto técnico final o evidencia de taller, explica los procedimientos y técnicas aplicadas, y reflexiona sobre sus logros, dificultades y compromisos de mejora operativa."

                sit_sig = (
                    f"En la I.E. INEI N.º 34 de Chancay, los estudiantes del {grade_str.lower()} grado de secundaria en el programa formativo de {spec_prog} "
                    f"requieren consolidar sus capacidades operativas y técnicas en {cleaned_topic}. En el entorno de taller y frente al crecimiento industrial y tecnológico del distrito, "
                    f"es imprescindible dominar la secuencia correcta de operaciones, el uso adecuado de herramientas e instrumentos de control y la aplicación estricta de las normas de seguridad y ergonomía.\n\n"
                    f"Ante esta situación, nos planteamos los siguientes retos:\n"
                    f"- ¿Cómo podemos ejecutar las operaciones de {cleaned_topic} garantizando acabados de calidad y tolerancias técnicas óptimas?\n"
                    f"- ¿Qué buenas prácticas de orden, limpieza (Metodología 5S) y uso de EPP debemos aplicar durante la práctica?\n"
                    f"- ¿De qué manera el dominio de este módulo técnico fortalece nuestras competencias formativas y empleabilidad?"
                )
        else:
            # Sesión general CNEB por competencias
            act_doc_inf = f"Plantea una situación significativa y motivadora sobre {cleaned_topic}. Formula preguntas para activar saberes previos y generar conflicto cognitivo. Comunica el propósito de aprendizaje y los criterios de evaluación."
            act_est_inf = f"Participa activamente respondiendo las preguntas, comparte saberes previos, comprende el reto propuesto y toma nota del propósito y los criterios con los que será evaluado."

            act_doc_plan = f"Orienta la búsqueda y procesamiento de información sobre {cleaned_topic}. Modela estrategias de resolución y organiza a los estudiantes para el trabajo guiado e individual."
            act_est_plan = f"Organiza su espacio de trabajo, selecciona estrategias para resolver el reto planteado y formula preguntas ante dudas conceptuales o procedimentales."

            act_doc_dec = f"Acompaña la toma de decisiones metodológicas de los estudiantes frente a las tareas propuestas, promoviendo el pensamiento crítico y la autonomía."
            act_est_dec = f"Decide la estrategia más pertinente para resolver la actividad sobre {cleaned_topic} y fundamenta su postura con argumentos claros."

            act_doc_ejec = f"Monitorea el desarrollo de las actividades en el aula, atiende dudas de los estudiantes y brinda retroalimentación formativa oportuna a nivel individual y grupal."
            act_est_ejec = f"Desarrolla las actividades de aprendizaje aplicando los conceptos y procedimientos de {cleaned_topic}, registrando sus avances en su cuaderno o ficha de trabajo."

            act_doc_cont = f"Verifica el avance de los estudiantes utilizando una lista de cotejo o rúbrica de evaluación. Formula preguntas de comprobación y reorienta aprendizajes."
            act_est_cont = f"Revisa su propia producción contra los criterios de evaluación compartidos, identifica errores y realiza las correcciones necesarias."

            act_doc_eval = f"Promueve la reflexión metacognitiva: ¿Qué aprendimos hoy? ¿Cómo lo aprendimos? ¿Para qué nos sirve lo aprendido en la vida cotidiana? Evalúa el logro del propósito."
            act_est_eval = f"Presenta la evidencia de aprendizaje final, responde a las preguntas metacognitivas y asume compromisos para seguir mejorando sus desempeños."

            sit_sig = (
                f"En la I.E. INEI N.º 34 de Chancay, los estudiantes del {grade_str.lower()} grado de secundaria en el área de {cleaned_specialty} "
                f"necesitan afianzar sus aprendizajes en torno a {cleaned_topic}. En el contexto sociocultural actual, es fundamental desarrollar competencias analíticas y prácticas "
                f"que les permitan desenvolverse de manera crítica, colaborativa y ética.\n\n"
                f"Ante esta situación, nos planteamos los siguientes retos:\n"
                f"- ¿De qué manera podemos comprender y aplicar {cleaned_topic} para resolver problemas de nuestro entorno?\n"
                f"- ¿Qué evidencias demuestran que hemos alcanzado los aprendizajes esperados?\n"
                f"- ¿Cómo podemos transferir lo aprendido a nuevas situaciones cotidianas y académicas?"
            )

        # Verificación matemática estricta de tiempos
        if resolved_type == "tecnica" and duration_minutes == 225:
            assert (t_inf + t_plan + t_dec + t_ejec + t_cont + t_eval) == 225, f"La suma de las 6 etapas GTZ ({t_inf+t_plan+t_dec+t_ejec+t_cont+t_eval} min) no coincide con 225 minutos."
        elif resolved_type == "emprendimiento" and duration_minutes == 135:
            assert (t_inf + t_plan + t_dec + t_ejec + t_cont + t_eval) == 135, f"La suma de las 6 etapas Lean Canvas ({t_inf+t_plan+t_dec+t_ejec+t_cont+t_eval} min) no coincide con 135 minutos."

        # Rúbrica de evaluación pertinente según la metodología y tipo de sesión
        if resolved_type == "tecnica":
            if is_digital:
                rubric_items = [
                    {
                        "criterio": "Estructura y Organización de Carpetas Digitales",
                        "ad": "Crea una jerarquía lógica y sistemática de carpetas y subcarpetas con nomenclatura normalizada, facilitando la ubicación inmediata de la información escolar.",
                        "a": "Crea carpetas y subcarpetas organizadas según el área o tema asignado, clasificando adecuadamente sus archivos.",
                        "b": "Organiza carpetas de manera parcial; algunos archivos permanecen fuera de su ubicación correspondiente o con estructura incompleta.",
                        "c": "No crea estructura de carpetas o mantiene sus archivos desordenados en una sola ubicación."
                    },
                    {
                        "criterio": "Nomenclatura y Depuración Segura de Archivos Duplicados",
                        "ad": "Asigna nombres descriptivos y estandarizados a todos los archivos, identificando y depurando duplicados sin pérdida de información relevante.",
                        "a": "Asigna nombres claros a la mayoría de archivos y elimina duplicados evidentes tras verificar su contenido.",
                        "b": "Nombra archivos con ambigüedad o conserva copias duplicadas innecesarias en el almacenamiento.",
                        "c": "Mantiene nombres genéricos ('sin título', 'documento 1') y no depura archivos duplicados."
                    },
                    {
                        "criterio": "Seguridad Digital y Respaldo en la Nube",
                        "ad": "Aplica buenas prácticas de respaldo en la nube, gestiona permisos de acceso y protege la privacidad de sus datos digitales.",
                        "a": "Utiliza el almacenamiento digital de manera responsable, manteniendo copias de respaldo de sus trabajos escolares.",
                        "b": "Requiere orientación frecuente para guardar sus archivos en la nube o respaldar su información.",
                        "c": "Desconoce las normas de seguridad digital y no respalda sus documentos de trabajo."
                    }
                ]
            else:
                rubric_items = [
                    {
                        "criterio": f"Aplicación y Destreza Técnica en {cleaned_topic}",
                        "ad": f"Ejecuta las operaciones de {cleaned_topic} con autonomía sobresaliente, precisión dimensional y optimización de materiales.",
                        "a": f"Ejecuta las operaciones de {cleaned_topic} siguiendo el procedimiento técnico establecido y las normas de calidad.",
                        "b": f"Aplica la técnica de {cleaned_topic} con dudas menores, requiriendo supervisión ocasional del docente.",
                        "c": f"Dificultades notorias para aplicar la técnica básica; no cumple el procedimiento sin asistencia continua."
                    },
                    {
                        "criterio": "Seguridad Industrial, Uso de EPP y Protocolo 5S",
                        "ad": "Aplica proactivamente el protocolo 5S, porta el EPP reglamentario en todo momento y previene riesgos de taller.",
                        "a": "Porta el EPP reglamentario durante toda la sesión y deja su puesto de trabajo limpio y ordenado.",
                        "b": "Requiere recordatorios para mantener colocado el EPP o completar la limpieza de su puesto.",
                        "c": "Incumple normas elementales de seguridad de taller o abandona su área de trabajo desordenada."
                    },
                    {
                        "criterio": "Control de Calidad y Trabajo Cooperativo en Taller",
                        "ad": "Verifica rigurosamente tolerancias con instrumentos de control y colabora activamente con su cuadrilla.",
                        "a": "Comprueba especificaciones técnicas y colabora de manera adecuada con sus compañeros de equipo.",
                        "b": "Revisa parcialmente su trabajo o participa pasivamente en las tareas del equipo.",
                        "c": "No realiza control de calidad o genera distracciones y desorden en el taller."
                    }
                ]
        elif resolved_type == "emprendimiento":
            rubric_items = [
                {
                    "criterio": "Formulación y Validación de Hipótesis en Lean Canvas",
                    "ad": "Formula hipótesis precisas y contrasta con evidencias empíricas sólidas los 9 bloques del Lean Canvas de su proyecto.",
                    "a": "Modifica y valida las hipótesis principales del Lean Canvas (problema, solución, propuesta de valor y canales).",
                    "b": "Presenta hipótesis generales con escasa contrastación o validación superficial con clientes.",
                    "c": "No formula hipótesis medibles ni valida los supuestos de su modelo de negocio."
                },
                {
                    "criterio": "Iteración y Adaptación del Modelo de Negocio según el Cliente",
                    "ad": "Itera con agilidad y criterio comercial la propuesta de valor incorporando retroalimentación real de usuarios.",
                    "a": "Realiza ajustes pertinentes en el lienzo respondiendo a las necesidades observadas en los clientes.",
                    "b": "Muestra resistencia a modificar su idea original a pesar de las evidencias recopiladas.",
                    "c": "No realiza adaptaciones en el Lean Canvas o no considera la opinión de los usuarios."
                },
                {
                    "criterio": "Sustentación de Aprendizajes, Viabilidad y Trabajo en Equipo",
                    "ad": "Sustenta con claridad técnica y convicción la viabilidad de su propuesta, demostrando liderazgo cooperativo.",
                    "a": "Expone con argumentos válidos las decisiones del equipo y la viabilidad de la propuesta emprendedora.",
                    "b": "Participa en la sustentación con argumentos limitados sobre la viabilidad comercial.",
                    "c": "No sustenta los cambios realizados en el lienzo ni demuestra articulación con su equipo."
                }
            ]
        else:
            rubric_items = [
                {
                    "criterio": f"Comprensión y Aplicación de Capacidades en {cleaned_topic}",
                    "ad": f"Demuestra dominio conceptual y procedimental sobresaliente al resolver situaciones problemáticas de {cleaned_topic}.",
                    "a": f"Aplica adecuadamente los conceptos y procedimientos de {cleaned_topic} según los propósitos establecidos.",
                    "b": f"Aplica conceptos de {cleaned_topic} con dificultades menores, requiriendo apoyo pedagógico guiado.",
                    "c": f"Dificultades evidentes para comprender y aplicar las nociones básicas de {cleaned_topic}."
                },
                {
                    "criterio": "Estrategias de Resolución y Calidad de la Evidencia",
                    "ad": "Desarrolla estrategias autónomas, creativas y fundamentadas para alcanzar la evidencia con alta calidad.",
                    "a": "Sigue la secuencia de actividades planificada completando la evidencia de aprendizaje requerida.",
                    "b": "Completa parcialmente las actividades o presenta evidencias con omisiones secundarias.",
                    "c": "No completa las actividades formativas o no presenta la evidencia solicitada."
                },
                {
                    "criterio": "Reflexión Metacognitiva y Trabajo Autónomo",
                    "ad": "Evalúa críticamente sus aciertos y errores, proponiendo acciones de mejora y autorregulación de su aprendizaje.",
                    "a": "Reconoce sus avances y dificultades, respondiendo con pertinencia a las preguntas metacognitivas.",
                    "b": "Identifica sus dificultades solo con la mediación directa del docente.",
                    "c": "Muestra escaso interés en evaluar su propio proceso formativo."
                }
            ]

        # Configuración de pasos didácticos
        if not custom_stages:
            if resolved_type == "tecnica":
                # Configuración Institucional Oficial CET N.º 34 (GTZ - Acción Completa)
                nombre_p1 = "Informarse"
                nombre_p2 = "Planificar"
                nombre_p3 = "Decidir"
                nombre_p4 = "Ejecutar"
                nombre_p5 = "Controlar"
                nombre_p6 = "Evaluar"
                procesos_steps = [
                    {"paso": nombre_p1, "tiempo": f"{t_inf} Minutos", "tiempo_minutos": t_inf, "actividad_docente": act_doc_inf, "actividad_estudiante": act_est_inf},
                    {"paso": nombre_p2, "tiempo": f"{t_plan} Minutos", "tiempo_minutos": t_plan, "actividad_docente": act_doc_plan, "actividad_estudiante": act_est_plan},
                    {"paso": nombre_p3, "tiempo": f"{t_dec} Minutos", "tiempo_minutos": t_dec, "actividad_docente": act_doc_dec, "actividad_estudiante": act_est_dec},
                    {"paso": nombre_p4, "tiempo": f"{t_ejec} Minutos", "tiempo_minutos": t_ejec, "actividad_docente": act_doc_ejec, "actividad_estudiante": act_est_ejec},
                    {"paso": nombre_p5, "tiempo": f"{t_cont} Minutos", "tiempo_minutos": t_cont, "actividad_docente": act_doc_cont, "actividad_estudiante": act_est_cont},
                    {"paso": nombre_p6, "tiempo": f"{t_eval} Minutos", "tiempo_minutos": t_eval, "actividad_docente": act_doc_eval, "actividad_estudiante": act_est_eval}
                ]
            elif resolved_type == "emprendimiento":
                # Configuración Institucional Oficial CET N.º 34 (Design Thinking / Lean Canvas)
                nombre_p1 = "Empatizar / Informar"
                nombre_p2 = "Definir / Planificar"
                nombre_p3 = "Idear / Decidir"
                nombre_p4 = "Prototipar / Ejecutar"
                nombre_p5 = "Evaluar / Controlar"
                nombre_p6 = "Valorar / Metacognición"
                procesos_steps = [
                    {"paso": nombre_p1, "tiempo": f"{t_inf} Minutos", "tiempo_minutos": t_inf, "actividad_docente": act_doc_inf, "actividad_estudiante": act_est_inf},
                    {"paso": nombre_p2, "tiempo": f"{t_plan} Minutos", "tiempo_minutos": t_plan, "actividad_docente": act_doc_plan, "actividad_estudiante": act_est_plan},
                    {"paso": nombre_p3, "tiempo": f"{t_dec} Minutos", "tiempo_minutos": t_dec, "actividad_docente": act_doc_dec, "actividad_estudiante": act_est_dec},
                    {"paso": nombre_p4, "tiempo": f"{t_ejec} Minutos", "tiempo_minutos": t_ejec, "actividad_docente": act_doc_ejec, "actividad_estudiante": act_est_ejec},
                    {"paso": nombre_p5, "tiempo": f"{t_cont} Minutos", "tiempo_minutos": t_cont, "actividad_docente": act_doc_cont, "actividad_estudiante": act_est_cont},
                    {"paso": nombre_p6, "tiempo": f"{t_eval} Minutos", "tiempo_minutos": t_eval, "actividad_docente": act_doc_eval, "actividad_estudiante": act_est_eval}
                ]
            else:
                procesos_steps = [
                    {"paso": "1. INICIO (Problematización, saberes previos y propósito)", "tiempo": f"{t_inf} Minutos", "tiempo_minutos": t_inf, "actividad_docente": act_doc_inf, "actividad_estudiante": act_est_inf},
                    {"paso": "2. DESARROLLO (Gestión y acompañamiento de competencias)", "tiempo": f"{t_ejec} Minutos", "tiempo_minutos": t_ejec, "actividad_docente": act_doc_ejec, "actividad_estudiante": act_est_ejec},
                    {"paso": "3. CIERRE (Evaluación formativa y metacognición)", "tiempo": f"{t_eval} Minutos", "tiempo_minutos": t_eval, "actividad_docente": act_doc_eval, "actividad_estudiante": act_est_eval}
                ]

        # Secuencia didáctica sintetizada para editor modular
        if resolved_type in ["tecnica", "emprendimiento"]:
            secuencia_didactica = {
                "inicio": {
                    "tiempo_minutos": t_inf + t_plan,
                    "descripcion": f"Fase de Preparación ({t_inf + t_plan} min):\n- {act_doc_inf}\n- {act_doc_plan}",
                    "actividades": f"1. INFORMARSE ({t_inf} min)\n2. PLANIFICAR ({t_plan} min)"
                },
                "desarrollo": {
                    "tiempo_minutos": t_dec + t_ejec,
                    "descripcion": f"Fase de Ejecución y Modelado ({t_dec + t_ejec} min):\n- {act_doc_dec}\n- {act_doc_ejec}",
                    "actividades": f"3. DECIDIR ({t_dec} min)\n4. EJECUTAR ({t_ejec} min)"
                },
                "cierre": {
                    "tiempo_minutos": t_cont + t_eval,
                    "descripcion": f"Fase de Control y Valoración ({t_cont + t_eval} min):\n- {act_doc_cont}\n- {act_doc_eval}",
                    "actividades": f"5. CONTROLAR ({t_cont} min)\n6. EVALUAR ({t_eval} min)"
                }
            }
        else:
            secuencia_didactica = {
                "inicio": {
                    "tiempo_minutos": t_inf,
                    "descripcion": act_doc_inf,
                    "actividades": f"Inicio y problematización ({t_inf} min)"
                },
                "desarrollo": {
                    "tiempo_minutos": t_ejec,
                    "descripcion": act_doc_ejec,
                    "actividades": f"Desarrollo y práctica guiada ({t_ejec} min)"
                },
                "cierre": {
                    "tiempo_minutos": t_eval,
                    "descripcion": act_doc_eval,
                    "actividades": f"Cierre y metacognición ({t_eval} min)"
                }
            }

        is_institucional = (structure_mode or "institucional").strip().lower() == "institucional"

        # Actualizar estructura semántica oficial
        structured_json["rubrica_items"] = rubric_items
        structured_json["competencia_oficial_verificada"] = is_official_comp
        structured_json["datos_generales_oficiales"] = {
            "institucion": "CET N° 34 (I.E. INEI N.º 34)" if is_institucional else "I.E. INEI N.º 34",
            "area_curricular": cleaned_specialty,
            "programa_formativo": spec_prog,
            "modulo_formativo": mod_form,
            "grado_seccion": f"{grade_str} grado: \"{section_name}\"",
            "fecha": "Octubre a Diciembre de 2026",
            "duracion": f"{ped_hours} horas pedagógicas ({duration_minutes} minutos)",
            "metodo_didactico": metodo_didactico,
            "sub_director": ("Mg. Javier Eulogio Rosas Maguiña" if is_ept else "Subdirección Pedagógica") if is_institucional else "[Por completar]",
            "docente_responsable": final_teacher
        }
        structured_json["situacion_significativa"] = sit_sig
        structured_json["procesos_didacticos_gtz"] = procesos_steps
        structured_json["secuencia_didactica"] = secuencia_didactica
        structured_json["structure_mode"] = "institucional" if is_institucional else "libre"
        structured_json["session_type"] = resolved_type
        structured_json["warning_time_discrepancy"] = warning_time_discrepancy

        if is_institucional:
            if is_ept:
                subdirector_cargo = "Sub-Director de Área Técnica"
                subdirector_nom = "Mg. Javier Eulogio Rosas Maguiña"
                docente_cargo = "Docente Responsable"
            else:
                subdirector_cargo = "Subdirectora de Formación General"
                subdirector_nom = "Subdirección Pedagógica"
                docente_cargo = f"Docente Responsable - Área de {cleaned_specialty}"

            structured_json["firmas_institucionales"] = {
                "docente": {"cargo": docente_cargo, "nombre": final_teacher},
                "jefe_taller": {"cargo": jefe_cargo, "nombre": jefe_taller},
                "subdirector": {"cargo": subdirector_cargo, "nombre": subdirector_nom}
            }

        # Vínculo con Unidad Didáctica en Cascada
        if unit_id or week_number or session_number:
            structured_json["unidad_didactica_origen"] = {
                "unit_id": unit_id,
                "unit_title": unit_title,
                "week": week_number,
                "session_number": session_number,
                "session_type": resolved_type,
                "metodologia": metodo_didactico
            }

        # Construcción de Markdown según el modo de estructura elegido
        num_ses_str = f"Nº {session_number:02d}" if session_number else "Nº 01"
        col_pasos_label = "Pasos o etapas" if resolved_type == "tecnica" else ("Proceso didáctico" if resolved_type == "emprendimiento" else "Momento pedagógico")
        col_doc_label = "Acciones o actividades del docente" if resolved_type == "tecnica" else "Actividad del docente"
        col_est_label = "Acciones o actividades del estudiante" if resolved_type == "tecnica" else "Actividad del estudiante"

        rows_table_md = "\n".join(
            f"| {p.get('paso', '')} | {p.get('tiempo', '')} | {p.get('actividad_docente', '')} | {p.get('actividad_estudiante', '')} |"
            for p in procesos_steps
        )

        if is_institucional:
            if is_digital:
                materiales_list = (
                    f"- Computadoras / Laptops con conexión a Internet y navegador web\n"
                    f"- Proyector multimedia y ecran / pizarra interactiva\n"
                    f"- Plataforma institucional en la nube (Google Drive / Workspace escolar)\n"
                    f"- Hojas de trabajo o cuaderno de apuntes\n"
                    f"- Plumones y pizarra para esquemas de organización de carpetas"
                )
            else:
                materiales_list = (
                    f"- Equipos de cómputo y plataformas digitales institucionales\n"
                    f"- Proyector multimedia y conectividad a internet\n"
                    f"- Herramientas, máquinas y materiales específicos de {spec_prog}\n"
                    f"- Fichas técnicas de trabajo y listas de verificación formativa"
                )

            markdown_text = (
                f"# SESIÓN DE APRENDIZAJE {num_ses_str} - IVB\n\n"
                f"**Título:** \"{cleaned_topic}\"  \n"
                f"**PLANIFICACIÓN PEDAGÓGICA INSTITUCIONAL CET N.º 34**\n\n"
                f"### I. DATOS GENERALES:\n\n"
                f"| | | |\n"
                f"|:---|:---|:---|\n"
                f"| Institución educativa | : CET N° 34 (I.E. INEI N.º 34) | |\n"
                f"| Área curricular | : {cleaned_specialty} | |\n"
                f"| Programa formativo | : {spec_prog} | |\n"
                f"| Módulo formativo | : {mod_form} | |\n"
                f"| Grado y sección | : {grade_str} grado: \"{section_name}\" | |\n"
                f"| Fecha | : Octubre a Diciembre de 2026 | |\n"
                f"| Duración | : {ped_hours} horas pedagógicas ({duration_minutes} minutos) | |\n"
                f"| Método didáctico | : {metodo_didactico} | |\n"
                f"| Sub director | : Mg. Javier Eulogio Rosas Maguiña (Subdirector de Área Técnica) | |\n"
                f"| Docente responsable | : {teacher_name} | |\n\n"
                f"### II. PROPÓSITO DE LA SESIÓN\n"
                f"{cleaned_purpose}\n\n"
                f"### III. CRITERIOS DE EVALUACIÓN\n"
                f"{crit_text}\n\n"
                f"### IV. EVIDENCIAS DE APRENDIZAJE\n"
                f"{evid_text}\n\n"
                f"### V. SITUACIÓN SIGNIFICATIVA\n"
                f"{sit_sig}\n\n"
                f"### VI. DESARROLLO DE LOS PROCESOS DIDÁCTICOS DE LA SESIÓN\n\n"
                f"| {col_pasos_label} | Tiempo | {col_doc_label} | {col_est_label} |\n"
                f"|---|---|---|---|\n"
                f"{rows_table_md}\n\n"
                f"### VII. MATERIALES\n"
                f"{materiales_list}\n\n"
                f"### VIII. BIBLIOGRAFÍA\n"
                f"- Currículo Nacional de la Educación Básica (CNEB) — MINEDU.\n"
                f"- Manuales técnicos y recursos pedagógicos de especialidad — CET N.º 34 Chancay.\n\n"
                f"---\n\n"
                f"### FIRMAS INSTITUCIONALES\n\n"
                f"| DOCENTE RESPONSABLE | JEFE DE TALLER | SUB-DIRECTOR DE ÁREA TÉCNICA |\n"
                f"|:---:|:---:|:---:|\n"
                f"| ________________________________ | ________________________________ | ________________________________ |\n"
                f"| **{teacher_name}** | **{jefe_taller}** | **Mg. Javier Eulogio Rosas Maguiña** |\n"
                f"| Docente de Especialidad | {jefe_cargo} | Sub-Director de Área Técnica |\n"
                f"| I.E. CET N° 34 - Chancay | I.E. CET N° 34 - Chancay | I.E. CET N° 34 - Chancay |\n\n"
            )
        else:
            # Estructura modular libre
            markdown_text = (
                f"# Sesión de Aprendizaje: {cleaned_topic}\n\n"
                f"**Área / Especialidad:** {cleaned_specialty} | **Grado:** {grade_str} Sec. (Sección {section_name})  \n"
                f"**Duración:** {duration_minutes} min ({ped_hours} horas pedagógicas) | **Docente:** {teacher_name}\n\n"
                f"## 1. Propósitos y Criterios de Evaluación\n"
                f"- **Competencia:** {comp_display if not is_official_comp else cleaned_competence}\n"
                f"- **Propósito:** {cleaned_purpose}\n"
                f"- **Criterios de Evaluación:** {crit_text}\n"
                f"- **Evidencia:** {evid_text}\n\n"
                f"## 2. Situación Significativa\n"
                f"{sit_sig}\n\n"
                f"## 3. Secuencia Didáctica ({metodo_didactico})\n\n"
                f"| {col_pasos_label} | Tiempo | {col_doc_label} | {col_est_label} |\n"
                f"|---|---|---|---|\n"
                f"{rows_table_md}\n\n"
                f"## 4. Recursos y Materiales\n"
                f"- Materiales y equipos específicos para {cleaned_topic}\n"
                f"- Fichas de trabajo, guías de práctica y fuentes de consulta\n\n"
                f"> **Nota:** Estructura modular abierta, adaptable a cualquier enfoque o especialidad."
            )

        raw_res["title"] = title
        raw_res["doc_type"] = "sesion_aprendizaje"
        raw_res["teacher_name"] = teacher_name
        raw_res["content_markdown"] = markdown_text
        raw_res["content"] = markdown_text
        raw_res["content_json"] = structured_json
        raw_res["secuencia_didactica"] = structured_json["secuencia_didactica"]
        raw_res["topic"] = cleaned_topic
        raw_res["grade"] = grade
        raw_res["specialty"] = cleaned_specialty
        raw_res["section_name"] = section_name
        raw_res["duration_minutes"] = duration_minutes
        raw_res["competence"] = comp_display if not is_official_comp else cleaned_competence
        raw_res["purpose"] = cleaned_purpose
        raw_res["difficulty"] = cleaned_diff
        raw_res["observations"] = cleaned_obs
        raw_res["status"] = "BORRADOR"
        raw_res["version"] = 1
        raw_res["unit_id"] = unit_id
        raw_res["unit_title"] = unit_title
        raw_res["week_number"] = week_number
        raw_res["session_number"] = session_number
        raw_res["session_type"] = resolved_type
        raw_res["structure_mode"] = "institucional" if is_institucional else "libre"
        raw_res["methodology"] = metodo_didactico
        raw_res["criterios_evaluacion"] = crit_text
        raw_res["evidencia_aprendizaje"] = evid_text
        raw_res["warning_time_discrepancy"] = warning_time_discrepancy
        return raw_res

    @classmethod
    def validate_session_stage_times(
        cls,
        stages: Union[List[Dict[str, Any]], Dict[str, Any]],
        expected_minutes: Optional[int] = None,
        target_total_minutes: Optional[int] = None,
        confirm_action: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Valida determinísticamente si la suma de los minutos de las etapas de la sesión coincide
        con la duración declarada en el encabezado (expected_minutes).
        
        Si no coinciden:
        - Detecta la discrepancia sin alterar silenciosamente los datos.
        - Si se provee confirm_action:
            * 'sync_header': ajusta el encabezado a la suma de las actividades.
            * 'sync_stages': ajusta proporcionalmente las etapas para sumar expected_minutes.
            * 'keep': mantiene los datos para ajuste manual.
        - Mantiene compatibilidad total con llamadas anteriores (target_total_minutes).
        """
        exp_min = expected_minutes if expected_minutes is not None else (target_total_minutes or 90)

        is_dict_format = isinstance(stages, dict)
        stage_list = []
        if is_dict_format:
            for k in ["inicio", "desarrollo", "cierre"]:
                if k in stages:
                    stage_list.append({"nombre_fase": k, **stages[k]})
            if not stage_list:
                for k, v in stages.items():
                    if isinstance(v, dict):
                        stage_list.append({"nombre_fase": k, **v})
        else:
            stage_list = list(stages or [])

        total_minutes = 0
        extracted_times = []
        for st in stage_list:
            mins = 0
            if "tiempo_minutos" in st and isinstance(st["tiempo_minutos"], (int, float)):
                mins = int(st["tiempo_minutos"])
            elif "tiempo" in st:
                t_val = st.get("tiempo", "")
                if isinstance(t_val, (int, float)):
                    mins = int(t_val)
                else:
                    m = re.search(r"(\d+)", str(t_val))
                    mins = int(m.group(1)) if m else 0
            extracted_times.append(mins)
            total_minutes += mins

        is_valid = (total_minutes == exp_min)
        has_discrepancy = not is_valid
        diff = total_minutes - exp_min  # Positivo indica exceso de tiempo en etapas
        diff_to_balance = exp_min - total_minutes

        # Preparar sugerencia de etapas ajustadas a la duración declarada (escalado proporcional determinista)
        suggested_stages_to_header = []
        if not is_valid and stage_list and total_minutes > 0:
            scale_factor = exp_min / total_minutes
            scaled_mins = [max(5, round(m * scale_factor)) for m in extracted_times]
            remainder = exp_min - sum(scaled_mins)
            if remainder != 0 and scaled_mins:
                max_idx = scaled_mins.index(max(scaled_mins))
                scaled_mins[max_idx] = max(5, scaled_mins[max_idx] + remainder)

            for i, st in enumerate(stage_list):
                st_copy = dict(st)
                new_m = scaled_mins[i]
                st_copy["tiempo_minutos"] = new_m
                if "tiempo" in st_copy:
                    st_copy["tiempo"] = f"{new_m} Minutos"
                suggested_stages_to_header.append(st_copy)
        else:
            suggested_stages_to_header = [dict(s) for s in stage_list]

        # Determinar si se aplica ajuste según la decisión del docente
        was_adjusted = False
        final_expected = exp_min
        final_stages = [dict(s) for s in stage_list]

        if confirm_action == "sync_header":
            final_expected = total_minutes
            was_adjusted = True
        elif confirm_action == "sync_stages":
            final_stages = suggested_stages_to_header
            was_adjusted = True
        elif confirm_action == "keep":
            final_stages = [dict(s) for s in stage_list]
            was_adjusted = False
        else:
            # Compatibilidad previa cuando se pasa target_total_minutes explícito en pruebas unitarias legacy
            if target_total_minutes is not None or "target_total_minutes" in kwargs or kwargs.get("auto_balance", False):
                final_stages = suggested_stages_to_header
                was_adjusted = not is_valid

        # Reconstruir dict si el formato de entrada era diccionario
        adjusted_dict = {}
        suggested_dict = {}
        if is_dict_format:
            for s in (final_stages if was_adjusted else stage_list):
                f_name = s.get("nombre_fase") or "fase"
                adjusted_dict[f_name] = s
            for s in suggested_stages_to_header:
                f_name = s.get("nombre_fase") or "fase"
                suggested_dict[f_name] = s

        ped_declared = max(1, round(exp_min / 45))
        ped_total = max(1, round(total_minutes / 45))

        discrepancy_message = None
        if has_discrepancy:
            discrepancy_message = (
                f"Inconsistencia de tiempos detectada: La duración declarada en el encabezado es de {exp_min} min "
                f"({ped_declared} horas pedagógicas), pero la suma de las actividades es de {total_minutes} min "
                f"({ped_total} horas pedagógicas). Diferencia: {diff:+d} minutos."
            )

        resolution_options = [
            {
                "action": "sync_header",
                "label": f"Ajustar duración declarada a las actividades ({total_minutes} min / {ped_total} horas pedagógicas)",
                "description": "Modifica el encabezado general para reflejar la duración real requerida por las fases de aprendizaje."
            },
            {
                "action": "sync_stages",
                "label": f"Ajustar actividades a la duración declarada ({exp_min} min / {ped_declared} horas pedagógicas)",
                "description": "Ajusta la etapa principal de ejecución para que la suma coincida exactamente con las horas asignadas."
            },
            {
                "action": "keep",
                "label": "Mantener y ajustar manualmente en el editor interactivo",
                "description": "Conserva los tiempos tal como están y permite al docente editarlos paso a paso."
            }
        ]

        return {
            "is_valid": is_valid or was_adjusted,
            "originally_valid": is_valid,
            "has_discrepancy": has_discrepancy,
            "total_minutes": total_minutes,
            "stages_sum_minutes": total_minutes,
            "sum_minutes": total_minutes if confirm_action == "sync_header" else exp_min,
            "expected_minutes": final_expected,
            "target_total_minutes": final_expected,
            "declared_minutes": exp_min,
            "computed_minutes": total_minutes,
            "difference": diff,
            "difference_minutes": abs(diff),
            "available_actions": ["sync_header", "sync_stages", "keep"],
            "stages": final_stages,
            "was_adjusted": was_adjusted,
            "discrepancy_message": discrepancy_message,
            "resolution_options": resolution_options,
            "adjusted_stages": (adjusted_dict if is_dict_format else final_stages) if was_adjusted else (stage_list if confirm_action == "keep" else None),
            "suggested_adjusted_stages": suggested_dict if is_dict_format else suggested_stages_to_header,
            "suggested_header_minutes": total_minutes
        }

    @classmethod
    def validate_didactic_unit_hours(
        cls,
        sessions_plan: List[Dict[str, Any]],
        duration_weeks: int = 9,
        weekly_hours: int = 8,
        pedagogical_hour_minutes: int = 45,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validates deterministically the weekly hours, total hours, and session timing distribution.
        Does not automatically hide errors; reports all inconsistencies clearly.
        """
        if "expected_weeks" in kwargs:
            duration_weeks = kwargs["expected_weeks"]
        if "expected_weekly_hours" in kwargs:
            weekly_hours = kwargs["expected_weekly_hours"]
        expected_total_hours = kwargs.get("expected_total_hours") or (duration_weeks * weekly_hours)

        inconsistencies: List[str] = []
        warnings: List[str] = []

        weekly_breakdown: Dict[int, Dict[str, Any]] = {}
        for w in range(1, duration_weeks + 1):
            weekly_breakdown[w] = {
                "semana": w,
                "tecnica_hours": 0,
                "emprendimiento_hours": 0,
                "total_hours": 0,
                "sessions_count": 0,
                "is_valid": False,
                "sessions": []
            }

        seen_session_numbers = set()
        total_unit_hours = 0

        for idx, s in enumerate(sessions_plan, start=1):
            s_num = s.get("numero_sesion") or s.get("session_number") or idx
            if s_num in seen_session_numbers:
                inconsistencies.append(f"Número de sesión duplicado detectado: Sesión Nº {s_num}.")
            seen_session_numbers.add(s_num)

            week = s.get("semana") or s.get("week")
            if week is None or not isinstance(week, int) or week < 1 or week > duration_weeks:
                inconsistencies.append(f"Sesión Nº {s_num} ('{s.get('titulo') or s.get('activity_title', 'Sin título')}'): asignada a una semana inválida ({week}). Debe estar entre 1 y {duration_weeks}.")
                continue

            h = s.get("horas_pedagogicas") if s.get("horas_pedagogicas") is not None else s.get("duration_hours", 0)
            if not isinstance(h, (int, float)) or h <= 0:
                inconsistencies.append(f"Sesión Nº {s_num}: horas pedagógicas inválidas ({h}).")
                continue

            s_type = (s.get("tipo_sesion") or s.get("session_type") or "").strip().lower()
            dur_min = s.get("duracion_minutos") if s.get("duracion_minutos") is not None else s.get("duration_minutes")
            expected_min = int(h * pedagogical_hour_minutes)
            if dur_min is not None and int(dur_min) != expected_min:
                warnings.append(f"Sesión Nº {s_num}: duración declarada ({dur_min} min) no coincide exactamente con {h} horas pedagógicas ({expected_min} min).")

            wb = weekly_breakdown[week]
            if "tec" in s_type:
                wb["tecnica_hours"] += h
            else:
                wb["emprendimiento_hours"] += h
            wb["total_hours"] += h
            wb["sessions_count"] += 1
            wb["sessions"].append(s)
            total_unit_hours += h

        # Validate each week against weekly_hours
        for w in range(1, duration_weeks + 1):
            wb = weekly_breakdown[w]
            if wb["total_hours"] == weekly_hours:
                wb["is_valid"] = True
            else:
                wb["is_valid"] = False
                inconsistencies.append(f"Semana {w}: suma {wb['total_hours']} horas pedagógicas en lugar de las {weekly_hours} horas requeridas (Semana {w} tiene {wb['total_hours']} horas pedagógicas).")

        # Validate total unit hours
        if total_unit_hours != expected_total_hours:
            inconsistencies.append(f"Total de horas de la unidad ({total_unit_hours} h) no coincide con el total previsto ({expected_total_hours} h para {duration_weeks} semanas a {weekly_hours} h/sem): {total_unit_hours} horas, diferente de las {expected_total_hours} horas esperadas.")

        return {
            "is_valid": len(inconsistencies) == 0,
            "total_hours": total_unit_hours,
            "calculated_total_hours": total_unit_hours,
            "expected_total_hours": expected_total_hours,
            "duration_weeks": duration_weeks,
            "weekly_hours": weekly_hours,
            "total_sessions": len(sessions_plan),
            "expected_total_sessions": duration_weeks * 2,
            "weekly_breakdown": weekly_breakdown,
            "inconsistencies": inconsistencies,
            "discrepancies": inconsistencies,
            "warnings": warnings
        }

    @classmethod
    def validate_didactic_unit_coherence(cls, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida rigurosamente la coherencia integral de una Unidad Didáctica:
        1. Coherencia numérica: semanas x horas semanales = total de horas, y suma de sesiones = total.
        2. Coherencia curricular y aislamiento de áreas: verifica que no exista contaminación
           entre áreas (por ejemplo, contenidos de taller, computación o Lean Canvas en Matemática).
        3. Integridad de metadatos institucionales y firmas reglamentarias.
        """
        c_json = unit_data.get("content_json") or unit_data
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}

        gen = c_json.get("datos_generales") or unit_data.get("datos_generales") or {}
        specialty = gen.get("especialidad") or unit_data.get("specialty") or ""
        clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "").strip().lower()

        is_ept = c_json.get("is_ept")
        if is_ept is None:
            is_ept = any(k in clean_spec for k in [
                "educación para el trabajo", "educacion para el trabajo", "ept",
                "computac", "informát", "informat", "mecánic", "mecanic",
                "electric", "electrón", "electron", "ebanist", "mader",
                "construc", "metálic", "metalic", "vestido", "textil",
                "contabil", "estétic", "estetic", "cosmetol"
            ])

        duration_weeks = int(gen.get("duracion_semanas") or unit_data.get("duration_weeks") or 9)
        weekly_hours = int(gen.get("horas_semanales") or unit_data.get("weekly_hours") or (8 if is_ept else 4))
        total_hours = int(gen.get("total_horas") or unit_data.get("total_hours") or (duration_weeks * weekly_hours))
        sessions = c_json.get("organizacion_sesiones") or unit_data.get("sessions_plan") or []

        errors: List[str] = []
        warnings: List[str] = []

        # 1. Validación Numérica
        expected_calc_total = duration_weeks * weekly_hours
        if total_hours != expected_calc_total:
            errors.append(
                f"Discrepancia en horas: el total declarado ({total_hours} h) no coincide "
                f"con el cálculo de {duration_weeks} semanas x {weekly_hours} horas semanales ({expected_calc_total} h)."
            )

        sum_session_hours = 0
        for s_idx, s in enumerate(sessions, 1):
            sh = s.get("horas_pedagogicas") if s.get("horas_pedagogicas") is not None else s.get("duration_hours", 0)
            sum_session_hours += sh

        if sessions and sum_session_hours != total_hours:
            errors.append(
                f"Discrepancia en sesiones: la suma de horas de las {len(sessions)} sesiones ({sum_session_hours} h) "
                f"no coincide con el total de horas de la unidad ({total_hours} h)."
            )

        # 2. Validación de Contaminación Curricular entre Áreas
        if not is_ept:
            forbidden_ept_terms = [
                ("almacenamiento en la nube", "concepto de computación"),
                ("carpetas digitales", "concepto de ofimática"),
                ("permisos de acceso", "concepto de administración informática"),
                ("reuniones virtuales", "actividad técnica de TIC"),
                ("lean canvas", "metodología exclusiva de emprendimiento / EPT"),
                ("máquinas herramientas", "taller de mecánica"),
                ("soldadura eléctrica", "taller de mecánica"),
                ("torno paralelo", "taller de mecánica"),
                ("jefe de taller", "cargo exclusivo de educación técnica")
            ]

            fields_to_check = [
                str(c_json.get("descripcion_unidad") or ""),
                str(c_json.get("propositos_tecnicos") or ""),
                str(c_json.get("propositos_emprendimiento") or "")
            ]
            for m in c_json.get("matriz_habilidades_tecnicas") or []:
                fields_to_check.append(str(m))
            for m in c_json.get("matriz_habilidades_emprendimiento") or []:
                fields_to_check.append(str(m))
            for s in sessions:
                fields_to_check.append(str(s))

            full_text_lower = " ".join(fields_to_check).lower()
            for term, reason in forbidden_ept_terms:
                if term in full_text_lower:
                    errors.append(
                        f"Contaminación curricular detectada en área {clean_spec.title()}: "
                        f"aparece el término '{term}' ({reason}), el cual no corresponde a esta área."
                    )

        # 3. Validación de Firmas Institucionales
        firmas = c_json.get("firmas_institucionales") or {}
        if firmas:
            jefe_taller_info = firmas.get("jefe_taller") or {}
            jefe_cargo = (jefe_taller_info.get("cargo") or "").upper()
            if not is_ept and "JEFE DE TALLER" in jefe_cargo:
                errors.append(
                    f"Inconsistencia institucional: en el área de {clean_spec.title()} se asignó "
                    f"el cargo de 'JEFE DE TALLER' en lugar de 'COORDINADOR PEDAGÓGICO'."
                )

        is_valid = len(errors) == 0
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "details": {
                "specialty": specialty,
                "is_ept": is_ept,
                "duration_weeks": duration_weeks,
                "weekly_hours": weekly_hours,
                "total_hours": total_hours,
                "sum_session_hours": sum_session_hours,
                "session_count": len(sessions)
            }
        }

    @classmethod
    def generate_didactic_unit_structured(
        cls,
        user: Dict[str, Any],
        topic: str,
        grade: int,
        specialty: str,
        duration_weeks: int = 9,
        weekly_hours: Optional[int] = None,
        formative_module: Optional[str] = None,
        section_name: str = "A",
        bimester: str = "IV Bimestre",
        unit_number: int = 4,
        technical_competence: Optional[str] = None,
        entrepreneurship_competence: Optional[str] = None,
        observations: Optional[str] = None,
        weekly_topics: Optional[str] = None,
        teacher_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera Unidad Didáctica completa estructurada con las 9 secciones oficiales de CET N° 34,
        diferenciando estrictamente entre Educación para el Trabajo (EPT - Técnica) y las
        Áreas Curriculares Básicas (MINEDU: Matemática, Comunicación, Ciencias Sociales, CyT, etc.),
        con nombres 100% oficiales de competencias CNEB, coherencia matemática de fechas y horas,
        y criterios de evaluación y evidencias observables libres de formulaciones genéricas.
        """
        cleaned_topic = (topic or "").strip()
        cleaned_specialty = (specialty or "Educación para el Trabajo").strip()
        final_teacher = teacher_name or user.get("full_name") or user.get("username") or "Docente de Especialidad"
        grade_words = {1: "Primer", 2: "Segundo", 3: "Tercer", 4: "Cuarto", 5: "Quinto"}
        grade_str = grade_words.get(grade, f"{grade}.°")
        is_ciclo_6 = (grade in [1, 2])
        ciclo_label = "Ciclo VI" if is_ciclo_6 else "Ciclo VII"

        # Resolución inteligente del contexto curricular CNEB
        from app.ai.curriculum_knowledge import resolve_curriculum_context
        curr_info = resolve_curriculum_context(topic=cleaned_topic, grade=grade, specialty=cleaned_specialty)
        if (not specialty or specialty.strip() in ["Educación para el Trabajo", "General", ""]) and not curr_info["is_ept"]:
            cleaned_specialty = curr_info["area"]

        spec_lower = cleaned_specialty.lower()

        # Detección estricta: ¿Es especialidad técnica de taller (EPT) o Área Académica Básica?
        is_ept = curr_info["is_ept"] or any(k in spec_lower for k in [
            "educación para el trabajo", "educacion para el trabajo", "ept",
            "computac", "informát", "informat", "mecánic", "mecanic",
            "electric", "electrón", "electron", "ebanist", "mader",
            "construc", "metálic", "metalic", "vestido", "textil",
            "contabil", "estétic", "estetic", "cosmetol"
        ])

        # Fechas oficiales del calendario escolar MINEDU 2026 según Bimestre y Duración
        bimester_clean = (bimester or "IV Bimestre").strip()
        dur_w = duration_weeks
        if "I Bimestre" in bimester_clean or bimester_clean.startswith("I "):
            f_ini_c = "16-03-2026"
            f_ini_l = "16 de marzo de 2026"
            if dur_w <= 9:
                f_fin_c = "15-05-2026"
                f_fin_l = "15 de mayo de 2026"
            else:
                f_fin_c = "22-05-2026"
                f_fin_l = "22 de mayo de 2026"
        elif "II Bimestre" in bimester_clean or bimester_clean.startswith("II "):
            f_ini_c = "25-05-2026"
            f_ini_l = "25 de mayo de 2026"
            if dur_w <= 9:
                f_fin_c = "24-07-2026"
                f_fin_l = "24 de julio de 2026"
            else:
                f_fin_c = "31-07-2026"
                f_fin_l = "31 de julio de 2026"
        elif "III Bimestre" in bimester_clean or bimester_clean.startswith("III "):
            f_ini_c = "10-08-2026"
            f_ini_l = "10 de agosto de 2026"
            if dur_w <= 9:
                f_fin_c = "09-10-2026"
                f_fin_l = "09 de octubre de 2026"
            else:
                f_fin_c = "16-10-2026"
                f_fin_l = "16 de octubre de 2026"
        else: # IV Bimestre
            f_ini_c = "12-10-2026"
            f_ini_l = "12 de octubre de 2026"
            if dur_w <= 9:
                f_fin_c = "11-12-2026"
                f_fin_l = "11 de diciembre de 2026"
            else:
                f_fin_c = "18-12-2026"
                f_fin_l = "18 de diciembre de 2026"

        p_texto = f"Del {f_ini_l} al {f_fin_l} ({bimester_clean})"
        dur_display = f"Inicio: {f_ini_c}     Fin: {f_fin_c}"

        # -------------------------------------------------------------
        # CONFIGURACIÓN DE HORAS PEDAGÓGICAS NORMATIVAS MINEDU
        # -------------------------------------------------------------
        default_hours_map = {
            "matem": 5, "comunic": 5, "social": 4, "historia": 4, "geograf": 4,
            "ciencia": 4, "biolog": 4, "quimic": 4, "ciudadan": 3, "cívic": 3, "civic": 3, "dpcc": 3, "personal": 3,
            "ingl": 3, "english": 3, "arte": 3, "cultur": 3, "física": 3, "fisica": 3, "relig": 2
        }

        if is_ept:
            final_weekly_hours = weekly_hours or 8
        elif weekly_hours is None or weekly_hours == 8:
            matched_h = 4
            for k_h, val_h in default_hours_map.items():
                if k_h in spec_lower:
                    matched_h = val_h
                    break
            final_weekly_hours = matched_h
        else:
            final_weekly_hours = weekly_hours

        total_horas_calculadas = duration_weeks * final_weekly_hours
        horas_display = f"{total_horas_calculadas} horas pedagógicas ({duration_weeks} semanas x {final_weekly_hours} horas)"

        # -------------------------------------------------------------
        # MAPEO CURRICULAR AUTÉNTICO CNEB PARA LAS 10 ÁREAS
        # -------------------------------------------------------------
        # 1. MATEMÁTICA
        if "matem" in spec_lower:
            spec_prog = "Matemática"
            area_display = "Matemática"
            prog_display = "Educación Secundaria - Matemática"
            coordinador_nom = "Coordinador Pedagógico del Área de Matemática"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE CIENCIAS"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Resolución de Problemas (Método Pólya)"

            eje_1_nombre = "Resuelve problemas de cantidad"
            eje_2_nombre = "Resuelve problemas de regularidad, equivalencia y cambio"

            if is_ciclo_6:
                mod_default = f"Resolución de problemas de cantidad y regularidad en contextos cotidianos: {cleaned_topic}"
                eje_1_estandar = "Resuelve problemas referidos a las relaciones entre cantidades o magnitudes, traduciéndolas a expresiones numéricas y operativas con números enteros y racionales, aumentos y descuentos porcentuales sucesivos. Expresa su comprensión sobre las propiedades de las operaciones, selecciona y emplea estrategias de cálculo exacto o aproximado, justificando sus procedimientos."
                eje_2_estandar = "Resuelve problemas referidos a interpretar cambios y regularidades entre magnitudes, traduciéndolas a patrones geométricos y numéricos, progresiones aritméticas, ecuaciones e inecuaciones lineales y funciones lineales. Justifica afirmaciones sobre relaciones de cambio y equivalencia."
                skills_eje_1 = [
                    (f"Números enteros y operaciones combinadas en {cleaned_topic}", "Resuelve problemas cotidianos aplicando adición y sustracción con números enteros.", "Modela relaciones numéricas en situaciones cotidianas mediante adición y sustracción con números enteros, comprobando la validez del resultado.", "Ficha de resolución de problemas con operaciones combinadas de números enteros desarrolladas paso a paso.", "Modela situaciones con cantidades enteras.", "Resolución de Problemas"),
                    ("Fracciones y números decimales en transacciones comerciales", "Calcula operaciones combinadas con fracciones y decimales en compras y ventas.", "Aplica algoritmos de cálculo y simplificación de fracciones en problemas comerciales, verificando la equivalencia decimal.", "Guía práctica de cálculo con operaciones de fracciones y decimales resueltas y justificadas.", "Aplica algoritmos de cálculo exacto.", "Pensamiento Crítico"),
                    ("Razones y proporcionalidad directa en contextos productivos", "Establece relaciones de proporcionalidad directa en presupuestos y recetas.", "Determina constantes de proporcionalidad directa en tablas numéricas y formula modelos multiplicativos de equivalencia.", "Tabla de proporcionalidad directa con cálculo explícito de constantes y valores desconocidos.", "Modela relaciones de proporcionalidad.", "Resolución de Problemas"),
                    ("Porcentajes y aplicaciones en finanzas familiares", "Resuelve situaciones de aumentos y descuentos porcentuales en el mercado local.", "Calcula porcentajes, aumentos e IGV aplicando modelos aritméticos e interpreta variaciones cuantitativas.", "Ficha de situaciones financieras con cálculo de aumentos y descuentos porcentuales fundamentados.", "Evalúa presupuestos y aumentos porcentuales.", "Pensamiento Crítico"),
                    ("Ecuaciones lineales de primer grado en situaciones reales", "Traduce enunciados verbales a ecuaciones lineales de la forma ax + b = c.", "Plantea ecuaciones lineales de primer grado a partir de problemas cotidianos y despeja incógnitas aplicando propiedades de la igualdad.", "Ficha de ecuaciones lineales con desarrollo algebraico paso a paso y comprobación de la solución.", "Modela relaciones de equivalencia.", "Resolución de Problemas"),
                    ("Inecuaciones lineales y restricciones cuantitativas", "Determina el conjunto solución de inecuaciones lineales en límites de presupuesto.", "Resuelve inecuaciones lineales representando el conjunto solución en la recta numérica e interpretando las restricciones.", "Conjunto solución de inecuaciones graficado en la recta numérica con justificación de valores límite.", "Interpreta desigualdades numéricas.", "Pensamiento Crítico"),
                    ("Perímetros y áreas de polígonos en terrenos de Chancay", "Calcula perímetros y áreas de figuras geométricas bidimensionales regulares.", "Calcula perímetros y áreas de polígonos regulares y compuestos aplicando propiedades geométricas y fórmulas pertinentes.", "Plano geométrico acotado con cálculo detallado de perímetros y áreas de figuras planas.", "Modela formas geométricas bidimensionales.", "Resolución de Problemas"),
                    ("Tablas de frecuencias y gráficos estadísticos comunitarios", "Organiza datos cuantitativos discretos en tablas y gráficos de barras e histogramas.", "Organiza datos estadísticos en tablas de frecuencias absolutas y porcentuales, elaborando gráficos pertinentes para su lectura.", "Tabla de distribución de frecuencias y gráfico estadístico interpretado con análisis cuantitativo.", "Representa datos con gráficos estadísticos.", "Pensamiento Crítico"),
                    ("Medidas de tendencia central y toma de decisiones", "Calcula e interpreta la media, mediana y moda en muestras de datos de la comunidad.", "Calcula medidas de tendencia central (media, mediana y moda) e interpreta su significado para sustentar conclusiones.", "Reporte estadístico con cálculo justificado de media, mediana y moda y recomendaciones basadas en datos.", "Sustenta conclusiones basadas en datos.", "Resolución de Problemas")
                ]
                skills_eje_2 = [
                    ("Patrones numéricos y regularidades aritméticas", "Identifica la regla de formación en sucesiones crecientes y decrecientes.", "Determina la regla de formación y el término enésimo en progresiones aritméticas a partir de regularidades observadas.", "Ficha de análisis de sucesiones con regla de formación deducida y cálculo de términos posteriores.", "Generaliza reglas de formación.", "Pensamiento Crítico"),
                    ("Plano cartesiano y relaciones funcionales directas", "Ubica pares ordenados y modela dependencias lineales simples en gráficos.", "Representa relaciones funcionales directas en tablas de valores y en el plano cartesiano identificando la razón de cambio.", "Gráfica en el plano cartesiano con tabla de valores y deducción de la relación funcional lineal.", "Modela relaciones en el plano.", "Resolución de Problemas"),
                    ("Proporcionalidad inversa en distribución de recursos", "Resuelve problemas de reparto y magnitudes inversamente proporcionales.", "Establece relaciones de proporcionalidad inversa mediante productos constantes y modela situaciones de rendimiento y tiempo.", "Tabla de proporcionalidad inversa con cálculo de la constante y verificación gráfica.", "Modela proporcionalidad inversa.", "Pensamiento Crítico"),
                    ("Modelamiento algebraico de costos y beneficios", "Plantea expresiones algebraicas que relacionan costo fijo, costo variable e ingreso.", "Formula expresiones algebraicas de costo total e ingreso identificando el punto de equilibrio en situaciones productivas.", "Expresión algebraica modelada con cálculo del punto de equilibrio y sustentación financiera.", "Modela relaciones de costo e ingreso.", "Resolución de Problemas"),
                    ("Sistemas de dos ecuaciones lineales por método gráfico", "Grafica dos rectas en el plano cartesiano para encontrar el punto de intersección.", "Determina la solución de sistemas de ecuaciones lineales de 2x2 mediante el método gráfico verificando la intersección.", "Plano cartesiano con trazado de rectas y determinación explícita de las coordenadas de intersección.", "Resuelve sistemas lineales gráficamente.", "Pensamiento Crítico"),
                    ("Funciones lineales afines y razones de cambio", "Interpreta la pendiente y el intercepto con el eje Y en funciones f(x) = mx + b.", "Analiza la pendiente y el punto de corte con el eje vertical en funciones lineales afines describiendo el tipo de variación.", "Ficha de funciones lineales afines con cálculo de pendientes e interpretación de tasas de variación.", "Analiza funciones lineales afines.", "Resolución de Problemas"),
                    ("Ángulos y propiedades de triángulos en construcciones", "Aplica teoremas de la suma de ángulos internos y clasificación de triángulos.", "Aplica propiedades angulares y teoremas fundamentales de triángulos en el cálculo de medidas desconocidas.", "Ficha de geometría con teoremas de triángulos demostrados y cálculo de medidas angulares.", "Aplica propiedades geométricas.", "Pensamiento Crítico"),
                    ("Probabilidad de sucesos simples mediante regla de Laplace", "Calcula la probabilidad de eventos cotidianos como cociente de casos favorables y posibles.", "Determina la probabilidad de sucesos aleatorios equiprobables aplicando la regla de Laplace y expresándola en porcentaje.", "Ficha de cálculo probabilístico con espacio muestral detallado y probabilidades porcentuales.", "Calcula probabilidades de sucesos.", "Resolución de Problemas"),
                    ("Evaluación formativa de las competencias matemáticas", "Demuestra dominio en resolución de problemas de cantidad y regularidad.", "Resuelve situaciones problemáticas integradas demostrando selección autónoma de estrategias heurísticas y de cálculo.", "Portafolio de resolución de problemas tipo CNEB resuelto con justificación de procedimientos.", "Consolida competencias matemáticas.", "Pensamiento Crítico")
                ]
            else: # Ciclo VII (3.°, 4.°, 5.° secundaria)
                mod_default = f"Modelamiento algebraico, geométrico y financiero de situaciones complejas: {cleaned_topic}"
                eje_1_estandar = "Resuelve problemas referidos a las relaciones entre cantidades muy grandes o muy pequeñas, magnitudes derivadas y tasas de interés simple y compuesto, traduciéndolas a expresiones con notación científica y financiera. Evalúa si los procedimientos matemáticos empleados satisfacen las condiciones del problema."
                eje_2_estandar = "Resuelve problemas referidos a analizar cambios y relaciones de equivalencia, modelándolas con sistemas de ecuaciones lineales, ecuaciones cuadráticas, funciones cuadráticas y exponenciales. Justifica la validez de sus procedimientos y soluciones con propiedades algebraicas."
                skills_eje_1 = [
                    (f"Notación científica y números reales en {cleaned_topic}", "Aplica operaciones con números racionales e irracionales y notación científica.", "Modela situaciones con cantidades muy grandes o muy pequeñas utilizando notación científica y justificando el redondeo.", "Ficha de ejercicios con operaciones en notación científica y conversión de unidades dimensionales.", "Modela cantidades con notación científica.", "Resolución de Problemas"),
                    ("Interés simple y tasas porcentuales en inversiones", "Calcula el interés simple y monto total en préstamos e inversiones a plazo fijo.", "Aplica fórmulas de interés simple deduciendo tasas equivalentes mensuales y anuales en contratos financieros.", "Hoja de liquidación financiera con cálculo de interés simple y comparativa de opciones crediticias.", "Evalúa modelos financieros simples.", "Pensamiento Crítico"),
                    ("Interés compuesto y capitalización en el sistema bancario", "Modela el crecimiento de capital con tasas de interés compuesto periódico.", "Modela el valor futuro de un capital con interés compuesto evaluando el impacto de diferentes periodos de capitalización.", "Cuadro de amortización y capitalización con aplicación justificada del modelo exponencial de interés compuesto.", "Modela interés compuesto.", "Resolución de Problemas"),
                    ("Sistemas de ecuaciones lineales 2x2 por método algebraico", "Resuelve sistemas lineales mediante reducción, sustitución e igualación.", "Resuelve sistemas de dos ecuaciones lineales aplicando el método de reducción y verificando la consistencia algebraica.", "Ficha de sistemas de ecuaciones con planteamiento algebraico, resolución paso a paso y comprobación de soluciones.", "Resuelve sistemas de ecuaciones lineales.", "Pensamiento Crítico"),
                    ("Ecuaciones cuadráticas y factorización en problemas de áreas", "Resuelve ecuaciones cuadráticas aplicando la fórmula general y aspa simple.", "Plantea y resuelve ecuaciones de segundo grado mediante factorización y fórmula general interpretando sus raíces reales.", "Ficha de ecuaciones cuadráticas con desarrollo de raíces reales y verificación en problemas geométricos.", "Modela situaciones cuadráticas.", "Resolución de Problemas"),
                    ("Funciones cuadráticas: vértice, eje de simetría y optimización", "Determina el valor máximo o mínimo modelando trayectorias parabólicas.", "Analiza la función cuadrática determinando el vértice y los interceptos para hallar valores óptimos en problemas de maximización.", "Gráfico de la parábola con coordenadas del vértice, cálculo de máximos/mínimos e interpretación contextual.", "Optimiza con funciones cuadráticas.", "Pensamiento Crítico"),
                    ("Geometría del espacio y volúmenes de prismas y cilindros", "Calcula el área total y volumen de cuerpos geométricos tridimensionales.", "Calcula áreas laterales, totales y volúmenes de prismas y cilindros rectos aplicando unidades del sistema internacional.", "Cálculo de volúmenes de cuerpos tridimensionales acotados con justificación de fórmulas empleadas.", "Modela cuerpos geométricos tridimensionales.", "Resolución de Problemas"),
                    ("Trigonometría y razones trigonométricas en triángulos rectángulos", "Aplica razones seno, coseno y tangente en el cálculo de alturas y distancias.", "Calcula distancias y ángulos de elevación o depresión aplicando razones trigonométricas en triángulos rectángulos notables.", "Esquema topográfico con cálculo trigonométrico de distancias inaccesibles y ángulos de elevación.", "Resuelve triángulos rectángulos.", "Pensamiento Crítico"),
                    ("Estadística inferencial: desviación estándar y coeficiente de variación", "Calcula medidas de dispersión para evaluar la homogeneidad de dos conjuntos de datos.", "Calcula e interpreta la varianza, desviación estándar y coeficiente de variación para comparar la dispersión de datos.", "Informe comparativo de muestras de datos con cálculo de desviación estándar e interpretación estadística.", "Sustenta conclusiones con medidas de dispersión.", "Resolución de Problemas")
                ]
                skills_eje_2 = [
                    ("Modelos exponenciales y crecimiento demográfico", "Interpreta el comportamiento de funciones exponenciales f(x) = a^x.", "Modela fenómenos de crecimiento exponencial analizando la tasa de variación y las asíntotas horizontales.", "Gráfico de función exponencial con tabla de variación y análisis del factor de crecimiento.", "Modela relaciones exponenciales.", "Pensamiento Crítico"),
                    ("Inecuaciones cuadráticas y regiones de viabilidad", "Determina intervalos solución de inecuaciones de segundo grado.", "Resuelve inecuaciones cuadráticas mediante puntos críticos determinando el intervalo solución en la recta real.", "Conjunto solución de inecuaciones cuadráticas graficado en la recta con verificación de signos.", "Resuelve inecuaciones cuadráticas.", "Resolución de Problemas"),
                    ("Programación lineal básica: regiones factibles en el plano", "Modela restricciones mediante semiplanos y encuentra polígonos de soluciones.", "Determina la región factible generada por un sistema de inecuaciones lineales en dos variables.", "Gráfico de la región factible acotada con identificación de vértices y restricciones lineales.", "Modela regiones factibles.", "Pensamiento Crítico"),
                    ("Sistemas de tres ecuaciones lineales con tres incógnitas", "Resuelve sistemas 3x3 aplicando el método de Gauss o determinantes (Cramer).", "Resuelve sistemas lineales de tres ecuaciones con tres incógnitas mediante matrices o determinantes justificando cada paso.", "Resolución detallada de sistema 3x3 por determinantes con verificación algebraica del vector solución.", "Resuelve sistemas de tres variables.", "Resolución de Problemas"),
                    ("Transformaciones geométricas: traslación, rotación y homotecia", "Aplica vectores de traslación y factores de escala en figuras geométricas.", "Realiza transformaciones geométricas en el plano cartesiano justificando la conservación de medidas y ángulos.", "Composición de transformaciones geométricas en el plano cartesiano con coordenadas de los vértices resultantes.", "Aplica transformaciones geométricas.", "Pensamiento Crítico"),
                    ("Geometría analítica de la recta: ecuación general y punto-pendiente", "Determina la pendiente y la ecuación de rectas paralelas y perpendiculares.", "Halla la ecuación general de la recta y determina condiciones de paralelismo y perpendicularidad entre rectas.", "Ecuaciones de rectas trazadas en el plano cartesiano con comprobación de pendientes perpendiculares.", "Modela la recta analíticamente.", "Resolución de Problemas"),
                    ("Ángulos de elevación y depresión en problemas de navegación", "Modela situaciones trigonométricas en contextos náuticos y topográficos.", "Resuelve situaciones de navegación y topografía aplicando ángulos de elevación y leyes de senos y cosenos.", "Plano de navegación con cálculo de rumbos y distancias aplicando modelos trigonométricos.", "Resuelve triángulos oblicuángulos.", "Pensamiento Crítico"),
                    ("Probabilidad condicional y teorema de Bayes en pruebas diagnósticas", "Calcula probabilidades condicionales P(A|B) e interpreta tablas de contingencia.", "Calcula probabilidades condicionales en tablas de contingencia evaluando la dependencia entre sucesos aleatorios.", "Tabla de contingencia con cálculo explícito de probabilidades condicionales e interpretación médica/social.", "Calcula probabilidad condicional.", "Resolución de Problemas"),
                    ("Consolidación y evaluación de competencias de Matemática", "Integra competencias de cantidad, álgebra, geometría y gestión de datos.", "Resuelve situaciones complejas de evaluación censal o de admisión demostrando dominio autónomo de las competencias CNEB.", "Portafolio de problemas de alta demanda cognitiva resueltos con argumentación rigurosa de procedimientos.", "Consolida competencias matemáticas.", "Pensamiento Crítico")
                ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Matemática. Lima: MINEDU.",
                "MINEDU (2020). Cuaderno de trabajo de Matemática: Resolvamos Problemas (Fascículos oficiales para secundaria). Lima: MINEDU.",
                "Stewart, J., Redlin, L. y Watson, S. (2017). Precálculo: Matemáticas para el cálculo. México: Cengage Learning.",
                "Baldor, A. (2019). Álgebra y Aritmética con aplicaciones prácticas. México: Grupo Editorial Patria.",
                "Plataforma Digital PerúEduca y Portal Educativo Aprendo en Casa (Recursos pedagógicos CNEB)."
            ]

        # 2. COMUNICACIÓN
        elif "comunic" in spec_lower:
            spec_prog = "Comunicación"
            area_display = "Comunicación"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico del Área de Comunicación"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE HUMANIDADES"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Enfoque Comunicativo y Prácticas Sociales del Lenguaje"

            eje_1_nombre = "Lee diversos tipos de textos escritos en su lengua materna"
            eje_2_nombre = "Escribe diversos tipos de textos en su lengua materna"

            mod_default = f"Comprensión crítica y producción de textos continuos y discontinuos: {cleaned_topic}"
            eje_1_estandar = "Lee diversos tipos de textos con estructuras complejas y vocabulario especializado. Integra información contrapuesta, deduce relaciones de causalidad e interpreta el sentido global del texto, evaluando la eficacia de los recursos discursivos y la validez de los argumentos."
            eje_2_estandar = "Escribe diversos tipos de textos de forma reflexiva. Adecúa su texto al destinatario, organiza y desarrolla lógicamente las ideas en torno a un tema, utiliza recursos cohesivos y vocabulario variado, y reflexiona permanentemente sobre el contenido y la intención comunicativa."

            skills_eje_1 = [
                (f"Estrategias de lectura y tema central en {cleaned_topic}", "Identifica la idea principal y la intención del autor en textos expositivos.", "Identifica información explícita, el tema central y la intención del autor mediante subrayado y notas al margen.", "Ficha de comprensión lectora con tema central, ideas principales y propósito comunicativo identificados.", "Identifica información en textos.", "Comprensión Lectora"),
                ("Deducción de relaciones de causalidad e inferencias textuales", "Deduce relaciones lógicas de causa-efecto en textos informativos.", "Deduce relaciones de causa-efecto y conclusiones lógicas a partir de premisas explícitas e implícitas en el texto.", "Cuadro de inferencias textuales con causas, efectos y deducciones fundamentadas en párrafos clave.", "Deduce relaciones lógicas.", "Pensamiento Crítico"),
                ("Análisis de textos argumentativos: tesis y argumentos", "Diferencia la tesis de los argumentos en ensayos de opinión ciudadana.", "Identifica la tesis central y clasifica los tipos de argumentos (de autoridad, de hecho y de causa) en textos de opinión.", "Esquema argumentativo con tesis identificada y argumentos clasificados según su tipología.", "Analiza estructura argumentativa.", "Comprensión Lectora"),
                ("Interpretación de infografías y textos discontinuos", "Interpreta datos estadísticos e iconográficos en infografías y reportajes.", "Sintetiza la información de textos discontinuos relacionando elementos visuales, gráficos y textuales.", "Ficha de análisis de infografía con síntesis visual e interpretación crítica de datos cuantitativos.", "Interpreta textos discontinuos.", "Pensamiento Crítico"),
                ("Lectura crítica y contraste de posturas divergentes", "Contrasta opiniones opuestas sobre problemáticas ambientales de Chancay.", "Evalúa la validez de posturas discrepantes en artículos periodísticos identificando sesgos y falacias argumentativas.", "Cuadro comparativo de posturas divergentes con análisis crítico de sesgos y evidencias presentadas.", "Evalúa argumentos divergentes.", "Juicio Crítico"),
                ("Análisis de recursos discursivos y figuras retóricas", "Explica el uso de metáforas, ironías y recursos enfáticos en textos.", "Interpreta el sentido de figuras retóricas y recursos paratextuales en función del propósito del autor.", "Guía de análisis estilístico con identificación de figuras retóricas y justificación de su efecto comunicativo.", "Interpreta recursos estilísticos.", "Comprensión Lectora"),
                ("Lectura de textos literarios peruanos y universales", "Analiza personajes, contexto social y conflicto central en relatos literarios.", "Interpreta el conflicto dramático y las motivaciones de los personajes relacionándolos con su contexto sociocultural.", "Ensayo breve de apreciación literaria sobre el conflicto de los personajes y su vigencia social.", "Aprecia obras literarias.", "Juicio Crítico"),
                ("Evaluación de la confiabilidad de fuentes digitales", "Verifica la autoría, rigor y actualización de artículos de divulgación en línea.", "Evalúa la confiabilidad y veracidad de fuentes digitales aplicando criterios de rigor académico y verificación cruzada.", "Ficha de cotejo de fuentes digitales con verificación de autores, fecha, rigor y referencias.", "Evalúa fuentes de información.", "Pensamiento Crítico"),
                ("Consolidación del plan lector y reflexión metacognitiva", "Sustenta una postura crítica fundamentada sobre los textos leídos en la unidad.", "Sustenta oralmente y por escrito conclusiones personales sobre las lecturas integrando evidencias textuales.", "Reseña crítica literaria o de opinión con valoración fundamentada del texto y su impacto social.", "Sustenta posturas personales.", "Juicio Crítico")
            ]
            skills_eje_2 = [
                ("Planificación de un texto argumentativo con rigor temático", "Define el tema, propósito, destinatario y esquema de redacción del texto.", "Adecúa el texto a la situación comunicativa definiendo la tesis, el registro lingüístico y el plan de escritura.", "Matriz de planificación textual con delimitación de tema, destinatario, tesis y esquema de párrafos.", "Planifica textos argumentativos.", "Producción Textual"),
                ("Redacción de párrafos de introducción y planteamiento de tesis", "Redacta el párrafo de inicio capturando el interés y enunciando la tesis.", "Escribe la introducción utilizando estrategias de contextualización y enunciando con claridad la tesis argumentativa.", "Párrafo introductorio redactado con gancho de lectura, contextualización y tesis explícita.", "Redacta introducciones claras.", "Pensamiento Crítico"),
                ("Construcción de párrafos de desarrollo con argumentos sólidos", "Desarrolla argumentos de autoridad y de hechos con conectores de causa.", "Construye párrafos de desarrollo articulando argumentos mediante conectores lógicos y citas de respaldo pertinentes.", "Párrafos de desarrollo redactados con argumento principal, fundamentación y conectores de causa-efecto.", "Escribe argumentos fundamentados.", "Producción Textual"),
                ("Uso de conectores lógicos y marcadores discursivos", "Emplea conectores de contraste, adición, consecuencia y ejemplificación.", "Utiliza marcadores textuales y conectores lógicos para cohesionar ideas evitando reiteraciones innecesarias.", "Texto en proceso de redacción con conectores lógicos variados destacados y revisados.", "Cohesiona ideas con conectores.", "Pensamiento Crítico"),
                ("Ortografía acentual, puntual y concordancia gramatical", "Aplica tildación diacrítica, uso de comas y concordancia entre sujeto y verbo.", "Aplica normas ortográficas de acentuación, puntuación jerárquica y concordancia para dar claridad al texto.", "Borrador de texto con corrección ortográfica de tildes diacríticas, signos de puntuación y concordancia.", "Aplica normas ortográficas.", "Producción Textual"),
                ("Redacción del párrafo de conclusión y síntesis argumentativa", "Resume los argumentos principales y formula un llamado a la acción reflexivo.", "Elabora la conclusión recapitulando la tesis sin repetir palabras literales y proponiendo una reflexión final.", "Párrafo de conclusión estructurado con síntesis de argumentos y llamado a la acción.", "Redacta conclusiones efectivas.", "Pensamiento Crítico"),
                ("Revisión textual entre pares y retroalimentación formativa", "Aplica una rúbrica de redacción para coevaluar el borrador de un compañero.", "Revisa textos ajenos y propios utilizando rúbricas analíticas para identificar oportunidades de mejora en cohesión.", "Rúbrica de evaluación entre pares aplicada con sugerencias específicas de mejora ortográfica y textual.", "Coevalúa textos reflexivamente.", "Juicio Crítico"),
                ("Edición final y publicación del artículo de opinión", "Corrige el borrador final e incorpora elementos de diagramación y titulación.", "Edita la versión final del texto argumentativo asegurando precisión léxica, coherencia y pulcritud formal.", "Versión final del artículo de opinión editada, diagramada y lista para difusión en el mural escolar.", "Edita textos para publicación.", "Producción Textual"),
                ("Exposición oral y defensa de posturas del texto producido", "Expone oralmente la tesis de su texto utilizando recursos paraverbales.", "Expone con fluidez y claridad la tesis de su escrito empleando volumen, entonación y contacto visual adecuados.", "Presentación oral grabada o en aula defendiendo la postura del texto y respondiendo preguntas.", "Comunica oralmente sus ideas.", "Juicio Crítico")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Comunicación. Lima: MINEDU.",
                "Real Academia Española y ASALE (2010). Ortografía de la lengua española. Madrid: Espasa.",
                "Cassany, D. (2018). Describir el escribir: Cómo se aprende a escribir. Barcelona: Paidós.",
                "MINEDU (2020). Cuaderno de trabajo de Comunicación: Comprensión y Producción. Lima: MINEDU.",
                "Portal PerúEduca y Biblioteca Digital Escolar MINEDU."
            ]

        # 3. CIENCIAS SOCIALES
        elif "social" in spec_lower or "historia" in spec_lower or "geograf" in spec_lower:
            spec_prog = "Ciencias Sociales"
            area_display = "Ciencias Sociales"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico del Área de Ciencias Sociales"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE HUMANIDADES"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Enfoque de Ciudadanía Activa y Crítico-Social"

            eje_1_nombre = "Construye interpretaciones históricas"
            eje_2_nombre = "Gestiona responsablemente el espacio y el ambiente"

            mod_default = f"Interpretación histórica y gestión sostenible del territorio: {cleaned_topic}"
            eje_1_estandar = "Construye interpretaciones históricas sobre procesos peruanos y mundiales. Explica hechos históricos complejos a partir de la contrastación de fuentes diversas, analiza causas y consecuencias socioeconómicas y políticas, y contextualiza los cambios y permanencias en el tiempo."
            eje_2_estandar = "Gestiona responsablemente el espacio y el ambiente al proponer acciones orientadas a la sostenibilidad, conservación de ecosistemas y mitigación de desastres. Utiliza cartografía e información geográfica para analizar la dinámica del territorio y el uso del espacio."

            skills_eje_1 = [
                (f"Análisis de fuentes históricas primarias y secundarias sobre {cleaned_topic}", "Contrasta testimonios de época con investigaciones históricas recientes.", "Contrasta fuentes primarias y secundarias sobre el proceso histórico evaluando la intención de los autores y el contexto de producción.", "Cuadro comparativo de fuentes históricas con análisis de fiabilidad y puntos de vista sobre el tema.", "Contrasta fuentes históricas.", "Pensamiento Crítico"),
                ("Simultaneidad y cronología en los procesos históricos", "Elabora líneas de tiempo comparativas entre sucesos mundiales y peruanos.", "Organiza cronológicamente los acontecimientos históricos estableciendo relaciones de simultaneidad entre el Perú y el mundo.", "Línea de tiempo comparada con hechos simultáneos de la historia nacional e internacional analizados.", "Organiza secuencias temporales.", "Comprensión Histórica"),
                ("Causas múltiples de las transformaciones sociopolíticas", "Explica las causas estructurales, coyunturales y desencadenantes.", "Distingue causas estructurales, coyunturales y detonantes en los procesos de cambio político y económico estudiados.", "Esquema multicausal con clasificación jerárquica de causas políticas, económicas y sociales.", "Explica multicausalidad.", "Pensamiento Crítico"),
                ("Cambios y permanencias en la estructura social y económica", "Identifica elementos que se transformaron y otros que perduran.", "Explica cambios significativos y permanencias en las condiciones de vida y relaciones de poder entre el pasado y el presente.", "Matriz de cambios y permanencias históricas con ejemplos concretos contrastados con la actualidad.", "Analiza cambios y permanencias.", "Comprensión Histórica"),
                ("El rol de los actores sociales en los hitos históricos", "Analiza el papel de sectores populares, mujeres e intelectuales.", "Reconoce la participación de diversos actores sociales (sectores populares, mujeres y líderes) en los procesos de transformación.", "Texto explicativo sobre el rol de actores subalternos y colectivos en el hito histórico investigado.", "Reconoce actores históricos.", "Pensamiento Crítico"),
                ("Impacto económico de las reformas y políticas de Estado", "Evalúa las consecuencias fiscales, comerciales y laborales.", "Analiza el impacto socioeconómico de las reformas fiscales e institucionales en los diferentes grupos de la población.", "Informe histórico con evaluación de las consecuencias económicas y tributarias para la sociedad.", "Evalúa impactos económicos.", "Comprensión Histórica"),
                ("Conflictos sociales y mecanismos de resolución histórica", "Examina rebeliones, demandas populares y respuestas del Estado.", "Explica las causas de las demandas sociales y rebeliones históricas evaluando las respuestas estatales de la época.", "Ficha de análisis de conflictos históricos con causas, demandas de las partes y lecciones para el presente.", "Analiza conflictos sociales.", "Pensamiento Crítico"),
                ("Debates historiográficos y posturas interpretativas", "Evalúa interpretaciones contradictorias de historiadores.", "Contrasta interpretaciones historiográficas divergentes sobre un mismo hecho histórico sustentando una postura fundamentada.", "Ensayo breve de contraste historiográfico argumentando una posición propia con evidencias documentales.", "Evalúa debates historiográficos.", "Juicio Crítico"),
                ("Memoria histórica y ciudadanía democrática", "Reflexiona sobre el aprendizaje del pasado para construir el futuro cívico.", "Sustenta la importancia de la memoria histórica para el fortalecimiento de la convivencia democrática y los derechos humanos.", "Manifiesto ciudadano sobre lecciones del proceso histórico para la convivencia democrática en el Perú.", "Reflexiona sobre memoria histórica.", "Ciudadanía Activa")
            ]
            skills_eje_2 = [
                ("Lectura de mapas temáticos y cartografía del territorio", "Interpreta coordenadas, escalas y curvas de nivel en mapas de Chancay.", "Utiliza herramientas cartográficas y mapas temáticos para localizar elementos geográficos y explicar dinámicas espaciales.", "Mapa temático de la provincia interpretado con simbología convencional, escala y coordenadas geográficas.", "Interpreta mapas temáticos.", "Gestión del Territorio"),
                ("Ecosistemas costeros y vulnerabilidad ambiental local", "Analiza los humedales de Santa Rosa y el litoral de Chancay.", "Explica las características ecológicas y los factores de degradación antrópica en ecosistemas costeros vulnerables.", "Infografía ambiental sobre la biodiversidad y amenazas a los ecosistemas locales de Chancay.", "Analiza ecosistemas locales.", "Conciencia Ambiental"),
                ("Gestión de cuencas hidrográficas y uso sostenible del agua", "Examina la cuenca del río Chancay-Huaral y la distribución hídrica.", "Propone medidas de uso eficiente y conservación del recurso hídrico en las actividades agrícolas y urbanas de la cuenca.", "Propuesta técnica de conservación y uso eficiente del agua en la cuenca hidrográfica local.", "Gestiona recursos hídricos.", "Sostenibilidad"),
                ("Plan de gestión del riesgo de desastres ante sismos y tsunamis", "Identifica zonas de peligro y rutas de evacuación en la comunidad.", "Diseña un plan familiar y escolar de evacuación ante riesgos geológicos e hidrometeorológicos en la zona costera.", "Mapa de riesgos y rutas de evacuación escolar y comunitario con protocolos de prevención validados.", "Planifica gestión de riesgos.", "Seguridad Ciudadana"),
                ("Impacto del crecimiento urbano desordenado en Chancay", "Evalúa el uso del suelo y la expansión urbana sobre áreas agrícolas.", "Analiza las consecuencias de la ocupación no planificada del territorio sobre la pérdida de áreas de cultivo y servicios.", "Informe de diagnóstico territorial sobre problemáticas del crecimiento urbano y periurbano en Chancay.", "Evalúa dinámicas urbanas.", "Gestión del Territorio"),
                ("Circuitos económicos locales y cadenas de comercialización", "Analiza las actividades productivas de pesca, agricultura y comercio.", "Explica cómo interactúan los agentes económicos en el mercado local identificando oferta, demanda y formación de precios.", "Diagrama de flujo del circuito comercial y productivo local de Chancay con análisis de agentes económicos.", "Explica circuitos económicos.", "Conciencia Económica"),
                ("Presupuesto familiar, ahorro e inversión responsable", "Elabora presupuestos familiares distinguiendo necesidades y deseos.", "Formula un presupuesto equilibrado identificando ingresos, costos fijos y alternativas de ahorro frente al endeudamiento.", "Presupuesto mensual planificado con metas de ahorro y análisis comparativo de créditos financieros.", "Planifica presupuesto financiero.", "Cultura Financiera"),
                ("Derechos del consumidor y regulación del mercado (INDECOPI)", "Reconoce derechos ciudadanos frente a publicidad engañosa y monopolios.", "Ejerce sus derechos como consumidor informado evaluando contratos, garantías y mecanismos de reclamo ciudadano.", "Ficha de reclamo simulada ante vulneración de derechos del consumidor con fundamentación normativa.", "Ejerce derechos del consumidor.", "Ciudadanía Económica"),
                ("Proyecto de desarrollo territorial sostenible para la comunidad", "Formula una propuesta comunitaria articulando ambiente y economía.", "Diseña participativamente un proyecto de mejora socioambiental y económica para la localidad de Chancay.", "Proyecto de desarrollo local sostenible con objetivos, actividades comunitarias y presupuesto preliminar.", "Diseña proyectos sostenibles.", "Sostenibilidad")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Ciencias Sociales. Lima: MINEDU.",
                "Contreras, C. y Cueto, M. (2018). Historia del Perú contemporáneo. Lima: Instituto de Estudios Peruanos (IEP).",
                "Pulgar Vidal, J. (2014). Las ocho regiones naturales del Perú. Lima: Terra Brasilis.",
                "MINEDU (2020). Texto Escolar de Ciencias Sociales (Historia, Geografía y Economía). Lima: Santillana / MINEDU.",
                "Centro Nacional de Estimación, Prevención y Reducción del Riesgo de Desastres (CENEPRED)."
            ]

        # 4. CIENCIA Y TECNOLOGÍA
        elif ("ciencia" in spec_lower and "social" not in spec_lower) or "biolog" in spec_lower or "quimic" in spec_lower:
            spec_prog = "Ciencia y Tecnología"
            area_display = "Ciencia y Tecnología"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico de Ciencia y Tecnología"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE CIENCIAS"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Indagación Científica y Alfabetización Científica y Tecnológica"

            eje_1_nombre = "Indaga mediante métodos científicos para construir conocimientos"
            eje_2_nombre = "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo"

            mod_default = f"Indagación científica y explicación del mundo físico: {cleaned_topic}"
            eje_1_estandar = "Indaga a partir de preguntas y plantea hipótesis con base científica sobre variables intervinientes. Diseña y ejecuta planes de recolección de datos cualitativos y cuantitativos, analiza tendencias en gráficos, contrasta hipótesis y sustenta conclusiones con rigor experimental."
            eje_2_estandar = "Explica con base en evidencia científica la relación entre la estructura atómica y molecular con las propiedades físicas y químicas de la materia, la transferencia de energía en ecosistemas y el impacto del cambio climático en la biosfera."

            skills_eje_1 = [
                (f"Planteamiento de preguntas de indagación e hipótesis sobre {cleaned_topic}", "Formula preguntas investigables y delimita variable independiente y dependiente.", "Formula preguntas de indagación científica delimitando variables (independiente, dependiente e intervinientes) y plantea hipótesis explicativas.", "Matriz de formulación de indagación con pregunta de investigación, variables delimitadas e hipótesis causal.", "Formula preguntas e hipótesis.", "Método Científico"),
                ("Diseño de estrategias experimentales y control de variables", "Planifica el protocolo de laboratorio, instrumentos de medición y seguridad.", "Diseña procedimientos experimentales para manipular la variable independiente, medir la dependiente y controlar variables intervinientes.", "Protocolo experimental detallado con lista de materiales, medidas de seguridad y tabla de registro de datos.", "Diseña protocolos experimentales.", "Rigor Experimental"),
                ("Registro y organización de datos cuantitativos experimentales", "Recopila mediciones repetidas en tablas con unidades del SI.", "Registra datos cuantitativos y cualitativos mediante mediciones sistemáticas y repetidas, organizándolos en tablas estructuradas.", "Tabla de datos experimentales con mediciones repetidas, cálculo de promedios y márgenes de incertidumbre.", "Registra datos sistemáticos.", "Método Científico"),
                ("Representación gráfica e interpretación de patrones de datos", "Grafica relaciones entre variables en ejes cartesianos (curvas y pendientes).", "Elabora gráficos pertinentes a partir de los datos experimentales e interpreta tendencias, proporcionalidades y anomalías.", "Gráfico de dispersión con curva de ajuste, análisis de pendientes y deducción de relaciones matemáticas entre variables.", "Grafica e interpreta datos.", "Análisis de Datos"),
                ("Contrastación de hipótesis y discusión con sustento científico", "Compara los resultados experimentales con teorías científicas validadas.", "Contrasta los resultados obtenidos con la hipótesis planteada y con información de fuentes científicas para validarla o refutarla.", "Texto de discusión científica que contrasta resultados con la hipótesis y explica discrepancias observadas.", "Contrasta hipótesis con teoría.", "Rigor Experimental"),
                ("Elaboración de conclusiones y sustento de limitaciones del método", "Formula conclusiones objetivas identificando sesgos e incertidumbres del ensayo.", "Elabora conclusiones basadas estrictamente en la evidencia experimental y evalúa las limitaciones de los instrumentos empleados.", "Informe de conclusiones científicas con análisis de limitaciones técnicas y sugerencias de mejora metodológica.", "Formula conclusiones rigurosas.", "Método Científico"),
                ("Diseño de prototipos de solución tecnológica en el entorno", "Diseña alternativas de solución a problemas ecológicos de la comunidad.", "Diseña alternativas de solución tecnológica a problemáticas ambientales locales justificando su viabilidad y materiales.", "Plano técnico acotado del prototipo tecnológico con lista de materiales reciclables y presupuesto estimado.", "Diseña soluciones tecnológicas.", "Innovación Tecnológica"),
                ("Construcción, prueba y validación del prototipo funcional", "Ensambla y prueba el prototipo realizando ajustes para optimizar su rendimiento.", "Construye el prototipo según las especificaciones técnicas y realiza pruebas operativas para verificar su eficiencia.", "Registro de pruebas de funcionamiento del prototipo con datos de rendimiento y mejoras mecánicas incorporadas.", "Valida prototipos tecnológicos.", "Innovación Tecnológica"),
                ("Comunicación del informe de indagación científica y tecnológica", "Sustenta el informe de indagación frente a la comunidad educativa.", "Comunica los resultados de la indagación científica y el impacto social del prototipo mediante un informe estructurado.", "Informe final de indagación científica en formato estándar de feria escolar con sustentación pública de resultados.", "Comunica hallazgos científicos.", "Divulgación Científica")
            ]
            skills_eje_2 = [
                ("Estructura atómica y propiedades de los enlaces químicos", "Explica la reactividad de los elementos según su configuración electrónica.", "Explica cómo la distribución de electrones determina la formación de enlaces iónicos y covalentes y las propiedades de la materia.", "Organizador visual con modelos atómicos y justificación científica de las propiedades de enlaces químicos.", "Explica enlaces químicos.", "Conocimiento Científico"),
                ("Reacciones químicas y conservación de la masa (Lavoisier)", "Balancea ecuaciones químicas y modela la transformación de reactivos en productos.", "Aplica la ley de conservación de la masa para balancear ecuaciones químicas y predecir la cantidad de productos obtenidos.", "Ficha de balanceo de ecuaciones químicas con cálculo estequiométrico y comprobación de conservación de masa.", "Modela reacciones químicas.", "Pensamiento Crítico"),
                ("Termodinámica y transferencia de calor en fenómenos naturales", "Diferencia conducción, convección y radiación en el sistema Tierra.", "Explica los mecanismos de transferencia de calor y su influencia en las corrientes marinas y la regulación térmica costera.", "Infografía científica sobre los mecanismos de transferencia térmica en la atmósfera y el mar de Chancay.", "Explica transferencia térmica.", "Conocimiento Científico"),
                ("La célula como unidad fundamental y respiración celular", "Explica la producción de ATP en la mitocondria y el metabolismo energético.", "Explica la transformación de biomoléculas en energía química (ATP) durante la respiración celular y la fotosíntesis.", "Esquema metabólico comparado entre fotosíntesis y respiración celular con balance energético celular.", "Explica metabolismo celular.", "Biología Celular"),
                ("Genética mendeliana y transmisión de caracteres hereditarios", "Resuelve cruces genéticos monohíbridos aplicando cuadros de Punnett.", "Explica las leyes de Mendel sobre la herencia de caracteres analizando probabilidades genotípicas y fenotípicas.", "Cuadros de Punnett resueltos con cálculo de probabilidades de genotipos y fenotipos de caracteres hereditarios.", "Aplica leyes de la herencia.", "Pensamiento Crítico"),
                ("Dinámica de ecosistemas y flujo de materia y energía", "Modela cadenas tróficas y ciclos biogeoquímicos (carbono y nitrógeno).", "Explica el flujo de energía unidireccional y el reciclaje de materia en los ciclos biogeoquímicos de los ecosistemas.", "Diagrama de red trófica con cálculo de niveles energéticos y representación de ciclos biogeoquímicos.", "Modela flujo de energía.", "Ecología"),
                ("El cambio climático global y el efecto invernadero antrópico", "Analiza la concentración de CO2 y el calentamiento global.", "Explica las causas antrópicas del aumento de gases de efecto invernadero y sus consecuencias en el régimen de lluvias.", "Reporte científico sobre el incremento del forzamiento radiativo y el retroceso de glaciares andinos.", "Explica cambio climático.", "Conciencia Ambiental"),
                ("Biotecnología y bioética en la producción de alimentos", "Evalúa el uso de organismos modificados genéticamente y vacunas.", "Sustenta posturas informadas sobre las aplicaciones de la biotecnología moderna considerando implicancias bioéticas.", "Texto argumentativo de bioética evaluando beneficios y riesgos del uso de transgénicos y edición genética.", "Evalúa implicancias bioéticas.", "Juicio Crítico"),
                ("Impacto de la actividad humana en la biodiversidad costera", "Evalúa el impacto de la contaminación marina y sobrepesca en Chancay.", "Propone medidas de mitigación del impacto ambiental de actividades portuarias e industriales sobre la fauna marina.", "Plan de mitigación ambiental con propuestas científicamente fundamentadas para la conservación marina local.", "Propone mitigación ambiental.", "Sostenibilidad")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Ciencia y Tecnología. Lima: MINEDU.",
                "Chang, R. y Goldsby, K. (2017). Química general. México: McGraw-Hill Interamericana.",
                "Campbell, N. y Reece, J. (2018). Biología general. Madrid: Editorial Médica Panamericana.",
                "Hewitt, P. (2016). Física conceptual. México: Pearson Educación.",
                "Consejo Nacional de Ciencia, Tecnología e Innovación Tecnológica (CONCYTEC)."
            ]

        # 5. DESARROLLO PERSONAL, CIUDADANÍA Y CÍVICA (DPCC)
        elif any(k in spec_lower for k in ["dpcc", "ciudadan", "cívic", "civic", "personal"]):
            spec_prog = "Desarrollo Personal, Ciudadanía y Cívica"
            area_display = "Desarrollo Personal, Ciudadanía y Cívica"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico de DPCC"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE HUMANIDADES"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Desarrollo Personal y Ciudadanía Activa"

            eje_1_nombre = "Construye su identidad"
            eje_2_nombre = "Convive y participa democráticamente en la búsqueda del bien común"

            mod_default = f"Fortalecimiento de la identidad, ética y convivencia democrática: {cleaned_topic}"
            eje_1_estandar = "Construye su identidad al tomar conciencia de los aspectos que lo hacen único. Se reconoce como persona valiosa, autorregula sus emociones en diversas situaciones, reflexiona sobre dilemas morales argumentando su postura con principios éticos y proyecta su vida con autonomía."
            eje_2_estandar = "Convive y participa democráticamente cuando se relaciona con los demás respetando las diferencias y los derechos de cada persona. Construye y cumple acuerdos y normas, delibera sobre asuntos públicos con argumentos razonados y promueve acciones concertadas para el bien común."

            skills_eje_1 = [
                (f"Autoconocimiento, autoestima y proyecto de vida en {cleaned_topic}", "Identifica fortalezas personales y metas a mediano y largo plazo.", "Reconoce sus potencialidades, intereses y valores personales formulando metas realistas para su proyecto de vida.", "Matriz de autodiagnóstico personal (FODA) y formulación de metas para su proyecto de vida.", "Construye autoconocimiento.", "Desarrollo Personal"),
                ("Autorregulación emocional y estrategias de afrontamiento", "Aplica técnicas de respiración y reestructuración cognitiva ante el estrés.", "Aplica estrategias de autorregulación emocional en situaciones de conflicto interpersonal y presión social.", "Registro de autorregulación emocional con identificación de detonantes y técnicas de afrontamiento aplicadas.", "Autorregula emociones.", "Habilidades Socioemocionales"),
                ("Dilemas morales y fundamentación de decisiones éticas", "Analiza casos de conflicto ético aplicando principios de justicia y verdad.", "Argumenta su postura frente a dilemas morales utilizando principios éticos universales y derechos fundamentales.", "Ensayo reflexivo sobre un dilema moral con argumentación fundamentada en valores éticos y consecuencias.", "Argumenta con ética.", "Juicio Moral"),
                ("Identidad cultural y valoración de la diversidad en Chancay", "Reconoce la herencia cultural chancayana y el diálogo intercultural.", "Valora las tradiciones y costumbres de su comunidad promoviendo el respeto hacia la diversidad cultural sin discriminación.", "Álbum de testimonios culturales sobre tradiciones de Chancay con reflexión sobre diálogo intercultural.", "Valora diversidad cultural.", "Interculturalidad"),
                ("Sexualidad integral, afectividad y vínculos saludables", "Distingue mitos de realidades en la vivencia de la sexualidad adolescente.", "Explica la importancia de relaciones afectivas basadas en el consentimiento, el respeto mutuo y la equidad de género.", "Ficha de análisis sobre mitos de la sexualidad y pautas para la construcción de relaciones afectivas sanas.", "Promueve relaciones saludables.", "Desarrollo Personal"),
                ("Toma de decisiones responsables frente a situaciones de riesgo", "Evalúa las consecuencias del consumo de drogas, alcohol y conductas adictivas.", "Sustenta decisiones autónomas orientadas al cuidado de su integridad física y psicológica frente a factores de riesgo.", "Plan personal de prevención de conductas de riesgo con estrategias de asertividad y redes de apoyo.", "Decide con autonomía.", "Prevención y Cuidado"),
                ("Comunicación asertiva y resolución pacífica de discrepancias", "Aplica la escucha activa y la asertividad en discusiones grupales.", "Emplea habilidades de comunicación asertiva para expresar ideas y desacuerdos sin recurrir a la violencia.", "Guion de dramatización de situaciones conflictivas resueltas pacíficamente mediante comunicación asertiva.", "Comunica con asertividad.", "Habilidades Socioemocionales"),
                ("Presión de grupo, autonomía moral y pensamiento crítico", "Sustenta su negativa ante propuestas contrarias a sus valores éticos.", "Ejerce su autonomía moral resistiendo la presión de pares en decisiones que comprometen su seguridad o dignidad.", "Texto de reflexión personal sobre experiencias de resistencia asertiva frente a la presión de grupo.", "Ejerce autonomía moral.", "Pensamiento Crítico"),
                ("Consolidación del plan de vida con visión comunitaria", "Integra aprendizajes socioemocionales en un plan vocacional y de servicio.", "Sintetiza sus aprendizajes personales en un plan de desarrollo vocacional articulado al bienestar de su entorno.", "Portafolio de desarrollo personal con plan vocacional sustentado y compromisos de servicio ciudadano.", "Consolida plan vocacional.", "Desarrollo Personal")
            ]
            skills_eje_2 = [
                ("Normas de convivencia escolar y construcción democrática", "Evalúa el cumplimiento de acuerdos del aula y propone mejoras consensuadas.", "Participa en la elaboración consensuada de acuerdos de convivencia respetando los derechos de todos los estudiantes.", "Reglamento de convivencia del aula construido participativamente con derechos, responsabilidades y medidas reparadoras.", "Construye normas democráticas.", "Convivencia Democrática"),
                ("Deliberación sobre asuntos públicos: la seguridad ciudadana local", "Investiga problemáticas comunitarias contrastando diversas fuentes.", "Delibera sobre problemáticas de seguridad y convivencia en Chancay fundamentando su postura en los derechos humanos.", "Matriz de deliberación pública sobre seguridad ciudadana con causas, posturas y propuestas de acción concertada.", "Delibera asuntos públicos.", "Participación Ciudadana"),
                ("Mecanismos de resolución pacífica de conflictos: la mediación", "Aplica los pasos de la mediación escolar para resolver desacuerdos.", "Aplica técnicas de mediación y negociación orientadas a la búsqueda de soluciones justas y acuerdos mutuos.", "Acta de mediación escolar simulada con registro de acuerdos de reparación y compromisos de las partes.", "Media en conflictos escolares.", "Cultura de Paz"),
                ("La Constitución Política del Perú y los Derechos Fundamentales", "Analiza los artículos sobre derechos civiles, políticos y laborales.", "Explica la estructura del Estado peruano y la importancia de las garantías constitucionales para proteger la dignidad.", "Cuadro comparativo de garantías constitucionales (Habeas Corpus, Amparo) con casos prácticos analizados.", "Interpreta la Constitución.", "Estado de Derecho"),
                ("Democracia, Estado de Derecho y lucha contra la corrupción", "Evalúa el impacto de la corrupción en el desarrollo y la confianza ciudadana.", "Argumenta la importancia de la transparencia, la rendición de cuentas y la ética pública para fortalecer la democracia.", "Texto argumentativo sobre el costo social de la corrupción y el rol de la fiscalización ciudadana.", "Defiende el Estado de Derecho.", "Ética Pública"),
                ("Grupos vulnerables y derechos de la mujer y personas con discapacidad", "Examina situaciones de discriminación y violencia de género.", "Propone acciones institucionales y comunitarias para prevenir la discriminación y promover la igualdad de oportunidades.", "Plan de campaña de sensibilización escolar por la igualdad de género y la inclusión de personas con discapacidad.", "Promueve inclusión social.", "Derechos Humanos"),
                ("Organizaciones estudiantiles: Municipio Escolar y liderazgo", "Organiza propuestas y planes de trabajo para el Municipio Escolar.", "Participa activamente en procesos electorales y representativos escolares ejerciendo un liderazgo democrático.", "Plan de trabajo para el Municipio Escolar con propuestas de mejora ambiental, cultural y académica.", "Ejerce liderazgo escolar.", "Participación Democrática"),
                ("Mecanismos de participación ciudadana en el gobierno local", "Explica el presupuesto participativo, cabildos abiertos y revocatoria.", "Analiza los canales constitucionales de participación vecinal y control ciudadano en la Municipalidad de Chancay.", "Ficha técnica de mecanismos de participación ciudadana (presupuesto participativo) con ejemplos locales.", "Conoce participación vecinal.", "Ciudadanía Activa"),
                ("Proyecto participativo de acción comunitaria para el bien común", "Diseña y ejecuta una iniciativa concreta de mejora en el colegio o barrio.", "Ejecuta un proyecto participativo ciudadano evaluando su impacto en la convivencia pacífica y el bien común.", "Informe final del proyecto participativo escolar con evidencias fotográficas, resultados y lecciones aprendidas.", "Ejecuta proyectos comunitarios.", "Bien Común")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de DPCC. Lima: MINEDU.",
                "Constitución Política del Perú de 1993 (Texto actualizado). Lima: Congreso de la República.",
                "Defensoría del Pueblo (2020). Informes Defensoriales sobre Derechos Fundamentales y Convivencia. Lima.",
                "MINEDU (2020). Texto Escolar de Desarrollo Personal, Ciudadanía y Cívica. Lima: Santillana / MINEDU.",
                "Jurado Nacional de Elecciones (JNE) - Dirección Nacional de Educación y Formación Cívica Ciudadana."
            ]

        # 6. INGLÉS COMO LENGUA EXTRANJERA
        elif "ingl" in spec_lower or "english" in spec_lower:
            spec_prog = "Inglés como Lengua Extranjera"
            area_display = "Inglés"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico del Área de Inglés"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE HUMANIDADES"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Enfoque Comunicativo y Acción en Lengua Extranjera"

            eje_1_nombre = "Lee diversos tipos de textos en inglés como lengua extranjera"
            eje_2_nombre = "Escribe diversos tipos de textos en inglés como lengua extranjera"

            mod_default = f"Reading comprehension and written communication in English: {cleaned_topic}"
            eje_1_estandar = "Lee diversos tipos de textos en inglés identificando información explícita, deduciendo el significado de vocabulario contextual y reconociendo el propósito de textos instructivos, descriptivos y narrativos breves."
            eje_2_estandar = "Escribe diversos tipos de textos breves en inglés adecuando su mensaje a situaciones cotidianas, empleando vocabulario básico, conectores de adición y contraste y respetando normas ortográficas y gramaticales elementales."

            skills_eje_1 = [
                (f"Reading for gist and main ideas in texts about {cleaned_topic}", "Identifica el tema general y datos explícitos en textos breves.", "Identifies explicit facts and the main topic in short written texts in English using skimming and scanning techniques.", "Reading comprehension sheet with main idea, key vocabulary and specific details identified.", "Identifies main ideas in English.", "Reading Comprehension"),
                ("Scanning for specific details in informational leaflets", "Localiza horarios, fechas y datos cuantitativos en folletos turísticos.", "Scans authentic short texts (leaflets, emails) to extract specific technical or tourist information accurately.", "Information extraction grid with dates, numbers and places located in authentic English materials.", "Scans for specific details.", "Reading Comprehension"),
                ("Deducing meaning of unknown vocabulary from context", "Deduce el significado de palabras compuestas y adjetivos por contexto.", "Infers the meaning of unfamiliar vocabulary and collocations using context clues and morphological roots.", "Vocabulary log with contextual definitions, synonyms and example sentences in English.", "Infers vocabulary from context.", "Language Awareness"),
                ("Reading narrative texts and identifying sequence of events", "Reconoce la secuencia temporal (First, Next, Then, Finally) en relatos.", "Identifies the chronological sequence of events in simple narrative texts using sequencing linkers.", "Timeline diagram ordering the sequence of events of a short story with key connectors highlighted.", "Identifies sequence of events.", "Reading Comprehension"),
                ("Reading instructions and procedures for daily tasks", "Comprende instrucciones paso a paso en manuales de usuario y recetas.", "Understands step-by-step instructions and imperative structures in technical guides or recipes.", "Step-by-step checklist matching instructional steps with corresponding actions and illustrations.", "Follows written instructions.", "Reading Comprehension"),
                ("Identifying author's purpose and tone in opinion texts", "Diferencia textos cuyo fin es informar, persuadir o entretener.", "Recognizes the communicative purpose and basic attitude of the author in short opinion articles.", "Critical reading card determining author's purpose, audience and supporting evidence in the text.", "Identifies author's purpose.", "Critical Thinking"),
                ("Reading comparative articles about lifestyles and traditions", "Compara costumbres de países angloparlantes con tradiciones peruanas.", "Compares cultural practices and daily routines between English-speaking countries and Peru in short texts.", "Comparative Venn diagram contrasting cultural habits based on reading selections in English.", "Compares cultural contexts.", "Intercultural Awareness"),
                ("Reading digital posts and social media messages critically", "Evalúa mensajes publicitarios y comentarios en redes sociales en inglés.", "Interprets communicative intentions and basic facts in digital formats such as forums and social posts.", "Digital media analysis sheet evaluating post reliability, emojis, and informal abbreviations.", "Reads digital formats in English.", "Digital Literacy"),
                ("Consolidation of reading strategies and synthesis", "Sintetiza la información de dos lecturas relacionadas con la unidad.", "Synthesizes key information from multiple short texts to produce an integrated personal summary in English.", "Reading portfolio containing written summaries and reflections on texts analyzed during the unit.", "Synthesizes reading texts.", "Reading Comprehension")
            ]
            skills_eje_2 = [
                ("Writing simple descriptive sentences with Subject-Verb-Object", "Construye oraciones con sustantivos, verbos en presente y adjetivos.", "Writes simple grammatically correct sentences in English using present simple and descriptive adjectives.", "Grammar drill and sentence building worksheet applying correct word order and punctuation rules.", "Writes descriptive sentences.", "Written Production"),
                ("Describing personal routines and habits using frequency adverbs", "Redacta párrafos cortos sobre su horario diario y actividades escolares.", "Produces a short descriptive paragraph about daily routines incorporating adverbs of frequency appropriately.", "Short paragraph describing daily routines with time expressions and frequency adverbs highlighted.", "Describes daily routines.", "Written Production"),
                ("Writing informal emails to introduce oneself to a penpal", "Redacta un correo electrónico de presentación personal en inglés.", "Drafts a friendly email following standard conventions (greeting, body, closing) to share personal details.", "Draft and final copy of an introductory email written according to standard email conventions.", "Writes informal emails.", "Communication"),
                ("Using connectors of addition, contrast and sequence", "Emplea conectores: and, but, because, so, first, then en sus textos.", "Links clauses and sentences using basic coordinating conjunctions and sequence adverbs coherently.", "Short narrative composition using target conjunctions to link related ideas without excessive repetition.", "Links ideas with connectors.", "Language Accuracy"),
                ("Describing past experiences using past simple tense", "Narra una anécdota personal o viaje empleando verbos regulares e irregulares.", "Writes a short anecdote in the past simple tense using common regular and irregular past verb forms correctly.", "Personal anecdote composition in the past tense with correct verb forms and temporal expressions.", "Narrates past events.", "Written Production"),
                ("Writing short comparative reviews of products or places", "Compara dos lugares turísticos de Chancay utilizando adjetivos comparativos.", "Writes comparative and superlative sentences evaluating features of two local places or technological devices.", "Product review card with comparative and superlative sentences justifying a preferred choice.", "Writes comparative reviews.", "Critical Thinking"),
                ("Writing simple invitations and posters for school events", "Elabora afiches con fecha, lugar, hora y mensaje persuasivo en inglés.", "Designs a flyer or digital poster for a school activity using imperative verbs and catchy slogans.", "Event flyer designed with attractive visual layout, event details, and compelling slogans in English.", "Designs promotional flyers.", "Creativity"),
                ("Editing and peer-reviewing written drafts in English", "Revisa la ortografía (spelling) y puntuación de textos propios y ajenos.", "Applies a self-editing checklist to identify and correct spelling errors, capitalization, and punctuation.", "Annotated draft showing proofreading marks, corrected spelling, and improved vocabulary choices.", "Proofreads written work.", "Language Accuracy"),
                ("Final publishing of a personal profile or brochure in English", "Edita y presenta la versión final de un folleto informativo bilingüe.", "Produces a polished, illustrated brochure or digital profile synthesizing all communicative skills acquired.", "Illustrated English brochure or personal profile ready for exhibition in the English classroom showcase.", "Publishes final written product.", "Written Production")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Inglés. Lima: MINEDU.",
                "Council of Europe (2020). Common European Framework of Reference for Languages (CEFR). Strasbourg.",
                "Murphy, R. (2019). Essential Grammar in Use with answers (4th ed.). Cambridge University Press.",
                "MINEDU (2020). English for Secondary Education (Workbooks & Audio resources). Lima: MINEDU.",
                "British Council LearnEnglish Teens Platform & PerúEduca English Program."
            ]

        # 7. ARTE Y CULTURA
        elif "arte" in spec_lower or "cultur" in spec_lower:
            spec_prog = "Arte y Cultura"
            area_display = "Arte y Cultura"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico de Arte y Cultura"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE HUMANIDADES"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Enfoque Multicultural e Interdisciplinario de los Lenguajes Artísticos"

            eje_1_nombre = "Aprecia de manera crítica manifestaciones artístico-culturales"
            eje_2_nombre = "Crea proyectos desde los lenguajes artísticos"

            mod_default = f"Apreciación crítica y creación artística con identidad local: {cleaned_topic}"
            eje_1_estandar = "Aprecia de manera crítica manifestaciones artístico-culturales al percibir elementos visuales, auditivos o corporales. Investiga el contexto sociocultural de su creación, interpreta las intenciones del creador y emite juicios de valor fundamentados sobre su mensaje estético."
            eje_2_estandar = "Crea proyectos artísticos integrando diversos lenguajes (artes visuales, danza, música o teatro). Experimenta con técnicas, planifica propuestas con intención expresiva, documenta su proceso creativo y socializa su obra evaluando el impacto comunicativo en su público."

            skills_eje_1 = [
                (f"Observación sensible y elementos visuales en {cleaned_topic}", "Identifica líneas, formas, colores y texturas en obras tradicionales.", "Describe las cualidades estéticas y elementos plásticos (línea, forma, color) presentes en manifestaciones artísticas.", "Ficha de apreciación estética con análisis formal de los elementos visuales de la obra analizada.", "Describe elementos visuales.", "Apreciación Artística"),
                ("Contexto histórico y cultural de la iconografía de la Cultura Chancay", "Investiga el significado de los cuchimilcos y textiles preincas.", "Investiga el contexto histórico, social y simbólico de la cerámica y textilería de la Cultura Chancay.", "Cuadro de investigación iconográfica con significado simbólico y sociocultural del arte Chancay.", "Investiga contexto cultural.", "Conciencia Histórica"),
                ("Análisis de la composición y ritmo en el arte plástico", "Examina el equilibrio, simetría y contrastes en pinturas emblemáticas.", "Analiza cómo la composición, el ritmo y el contraste transmiten sensaciones y comunican la intención del artista.", "Guía de análisis compositivo identificando puntos de interés y equilibrio visual en pinturas peruanas.", "Analiza composición artística.", "Pensamiento Crítico"),
                ("Apreciación musical: ritmo, melodía y sonoridades afroperuanas", "Reconoce instrumentos y patrones rítmicos del cajón y festejo en la costa.", "Identifica auditivamente patrones rítmicos, timbre de instrumentos y estructuras melódicas de la música tradicional costeña.", "Ficha de audición musical con discriminación tímbrica e identificación de ritmos afroperuanos.", "Aprecia música tradicional.", "Sensibilidad Auditiva"),
                ("La danza folclórica como expresión de memoria colectiva", "Analiza la vestimenta, coreografía y simbolismo de danzas peruanas.", "Interpreta el significado de los movimientos corporales, indumentaria y relatos representados en danzas costeras y andinas.", "Reseña coreográfica sobre el origen, significado y vestimenta de una danza tradicional representativa.", "Interpreta danzas folclóricas.", "Apreciación Cultural"),
                ("Apreciación teatral: caracterización y conflicto dramático", "Identifica el conflicto, atmósfera y mensaje en representaciones teatrales.", "Analiza cómo los recursos vocales, corporales y la puesta en escena transmiten emociones y conflictos éticos.", "Ficha de crítica teatral analizando la interpretación actoral, escenografía y mensaje de la puesta en escena.", "Evalúa puestas teatrales.", "Juicio Estético"),
                ("El arte contemporáneo y el grabado como denuncia comunitaria", "Examina murales urbanos y carteles con mensaje de protección ambiental.", "Analiza cómo el arte visual contemporáneo utiliza espacios públicos para interpelar a la ciudadanía sobre temas ecológicos.", "Ensayo visual crítico analizando el mensaje social y la técnica empleada en murales comunitarios.", "Analiza arte urbano.", "Juicio Crítico"),
                ("Crítica de arte fundamentada en evidencias estéticas", "Emite juicios de valor argumentando el impacto de una obra de arte.", "Formula una opinión fundamentada sobre el valor estético y social de una manifestación artística superando el 'me gusta'.", "Texto de crítica artística estructurado con descripción formal, contextualización y valoración personal.", "Emite crítica fundamentada.", "Apreciación Crítica"),
                ("Valoración del patrimonio inmaterial de Chancay y la región", "Sustenta la necesidad de preservar las tradiciones orales y artísticas.", "Propone estrategias comunitarias para la salvaguardia y puesta en valor del patrimonio cultural inmaterial local.", "Manifiesto de preservación patrimonial con propuestas para difundir el arte tradicional de Chancay.", "Valora patrimonio inmaterial.", "Identidad Cultural")
            ]
            skills_eje_2 = [
                ("Exploración con técnicas plásticas: acuarela, témpera y collage", "Experimenta con mezclas cromáticas, transparencias y texturas táctiles.", "Experimenta con diversos materiales y técnicas plásticas seleccionando aquellos que responden a su idea expresiva.", "Muestrario de experimentación cromática con gradaciones tonales, contrastes y texturas aplicadas.", "Experimenta con técnicas plásticas.", "Creatividad"),
                ("Bocetado y diseño de proyectos visuales con identidad chancayana", "Elabora bocetos previos definiendo encuadre, proporción y tema.", "Planifica un proyecto artístico visual elaborando bocetos preliminares inspirados en la iconografía local.", "Serie de bocetos exploratorios con notas sobre materiales, paleta de colores y mensaje pretendido.", "Planifica proyectos visuales.", "Diseño Artístico"),
                ("Modelado en arcilla o plastilina: escultura y volumen", "Aplica técnicas de modelado escultórico recreando figuras antropomorfas.", "Aplica técnicas tridimensionales de adición y sustracción en arcilla para crear volúmenes con intención estética.", "Pieza escultórica modelada en arcilla inspirada en motivos precolombinos con pulido y acabados cuidados.", "Modela esculturas tridimensionales.", "Expresión Plástica"),
                ("Creación de patrones rítmicos y ensamble sonoro en el aula", "Ejecuta secuencias percutivas con cajón, palmas e instrumentos reciclados.", "Crea y ejecuta ensambles rítmicos colectivos coordinando entradas, silencios y dinámicas de intensidad sonora.", "Registro audiovisual de ensamble rítmico coordinado con compases regulares y variaciones dinámicas.", "Ejecuta ensambles rítmicos.", "Expresión Musical"),
                ("Expresión corporal y coreografía de danza tradicional", "Coordina desplazamientos espaciales y pasos rítmicos en grupo.", "Diseña secuencias de movimiento corporal y desplazamientos espaciales que comunican emociones colectivas.", "Secuencia coreográfica ejecutada con coordinación rítmica, expresividad gestual y trabajo sincronizado.", "Crea secuencias coreográficas.", "Expresión Corporal"),
                ("Improvisación teatral y construcción de personajes", "Representa escenas breves basadas en problemáticas de convivencia.", "Construye personajes dramáticos utilizando matices de voz, gestos corporales y desplazamiento escénico con intención.", "Representación teatral breve de situaciones cotidianas con personajes caracterizados y conflicto resuelto.", "Representa obras teatrales.", "Expresión Dramática"),
                ("Elaboración de un mural o grabado colectivo con mensaje ecológico", "Aplica técnicas de estarcido o grabado en xilografía/linóleo escolar.", "Ejecuta un proyecto plástico colectivo aplicando técnicas de grabado o muralismo con mensaje conservacionista.", "Mural o serie de estampas grabadas con mensaje ecológico sobre la protección de los humedales de Chancay.", "Ejecuta murales colectivos.", "Creatividad Social"),
                ("Registro en bitácora y documentación del proceso creador", "Registra reflexiones, cambios y dificultades afrontadas durante el taller.", "Documenta en su bitácora artística las decisiones tomadas, bocetos descartados y aprendizajes logrados.", "Bitácora artística ilustrada con notas reflexivas, bocetos sucesivos y autoevaluación del proceso creador.", "Documenta procesos creativos.", "Reflexión Artística"),
                ("Montaje, curaduría y exhibición escolar de las obras creadas", "Organiza la galería de arte escolar con fichas técnicas y cédulas.", "Participa en el montaje y socialización de la exposición artística explicando su obra a la comunidad educativa.", "Exposición artística escolar inaugurada con cédulas museográficas redactadas y visita guiada participativa.", "Exhibe proyectos artísticos.", "Socialización Artística")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Arte y Cultura. Lima: MINEDU.",
                "Eisner, E. (2014). El arte y la creación de la mente: El papel de las artes visuales en la transformación de la conciencia. Barcelona: Paidós.",
                "Museo de Sitio de Chancay (2019). Catálogo Arqueológico e Iconográfico de la Cultura Chancay. Chancay: Municipalidad.",
                "MINEDU (2020). Orientaciones para la enseñanza de Arte y Cultura en Secundaria. Lima: MINEDU.",
                "Ministerio de Cultura del Perú - Plataforma de Recursos y Patrimonio Cultural Inmaterial."
            ]

        # 8. EDUCACIÓN FÍSICA
        elif "física" in spec_lower or "fisica" in spec_lower:
            spec_prog = "Educación Física"
            area_display = "Educación Física"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico de Educación Física"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE CIENCIAS"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Enfoque de Corporeidad y Motricidad Humana"

            eje_1_nombre = "Se desenvuelve de manera autónoma a través de su motricidad"
            eje_2_nombre = "Asume una vida saludable"

            mod_default = f"Desarrollo motriz, hábitos de vida saludable y habilidades sociomotrices: {cleaned_topic}"
            eje_1_estandar = "Se desenvuelve de manera autónoma a través de su motricidad al evaluar sus capacidades físicas y coordinativas. Regula su cuerpo en situaciones de movimiento complejo, afianza su lateralidad y expresa emociones a través de prácticas corporales y lúdicas."
            eje_2_estandar = "Asume una vida saludable al comprender la relación entre actividad física, nutrición e hidratación. Regula su esfuerzo mediante el control de la frecuencia cardíaca, previene lesiones deportivas y promueve estilos de vida activos en su entorno."

            skills_eje_1 = [
                (f"Diagnóstico de capacidades físicas básicas y antropometría en {cleaned_topic}", "Mide su peso, talla e índice de masa corporal y evalúa fuerza y flexibilidad.", "Evalúa su condición física inicial mediante pruebas estandarizadas (test de Ruffier, flexibilidad y salto vertical).", "Ficha antropométrica y de condición física inicial con cálculo de IMC y registro de pruebas motrices.", "Evalúa capacidades físicas.", "Condición Física"),
                ("Coordinación dinámica general y circuitos de agilidad", "Supera circuitos de saltos, giros y cambios de dirección coordinados.", "Ejecuta patrones motores complejos regulando el equilibrio estático y dinámico en circuitos de habilidad motriz.", "Circuito motriz ejecutado con fluidez temporal, equilibrio dinámico y superación de obstáculos.", "Regula el equilibrio motor.", "Coordinación Motriz"),
                ("Velocidad de reacción y desplazamiento en carreras de relevos", "Aplica técnicas de salida baja y entrega de testimonio en velocidad.", "Optimiza su velocidad de reacción y desplazamiento aplicando técnicas biomecánicas de carrera y coordinación grupal.", "Prueba de velocidad de relevos con técnica correcta de pase de testimonio y registro de tiempos cronometrados.", "Optimiza velocidad de carrera.", "Habilidades Atléticas"),
                ("Fundamentos técnicos del voleibol: voleo y antebrazo", "Ejecuta pases de dedos y recepción de antebrazo con precisión direccional.", "Aplica los gestos técnicos del voleo alto y la recepción de antebrazo con adecuada postura de flexión y amortiguación.", "Secuencia técnica de pases continuos en parejas con precisión hacia zonas delimitadas de la cancha.", "Aplica técnicas deportivas.", "Iniciación Deportiva"),
                ("Fundamentos del baloncesto: drible, pase de pecho y lanzamiento", "Dribla con ambas manos protegiendo el balón y ejecuta pases precisos.", "Coordina el bote dinámico del balón con cambios de ritmo y ejecuta lanzamientos a canasta con arco técnico adecuado.", "Circuito de habilidades de baloncesto con drible entre conos, pase de pecho y lanzamiento en suspensión.", "Coordina drible y tiro.", "Iniciación Deportiva"),
                ("Fundamentos del futsal: control del balón, pase al ras y definición", "Domina el balón con la planta del pie y entrega pases precisos al ras.", "Ejecuta controles orientados y pases con el borde interno del pie demostrando visión periférica del campo de juego.", "Práctica de fútbol reducido con control orientado de balón, pases de primera intención y remates a portería.", "Domina control de balón.", "Habilidades de Futsal"),
                ("Gimnasia básica: rodamientos, aspas de molino y pirámides humanas", "Ejecuta rodamientos adelante y atrás con control postural y seguridad.", "Realiza combinaciones gimnásticas en suelo cuidando la alineación corporal y apoyando figuras cooperativas seguras.", "Rutina gimnástica en suelo con rodamientos continuos, paradas de manos asistidas y postura corporal correcta.", "Ejecuta rutinas gimnásticas.", "Expresión Motriz"),
                ("Juegos tradicionales y actividades recreativas en equipo", "Participa en juegos de persecución y estrategia respetando las reglas.", "Adapta estrategias colectivas en juegos cooperativos tradicionales valorando la inclusión y el esfuerzo compartido.", "Participación activa en festival de juegos tradicionales con propuesta de adaptaciones para la integración de todos.", "Participa en juegos cooperativos.", "Sociomotricidad"),
                ("Evaluación final de habilidades motrices y rendimiento físico", "Comprueba la mejora de sus marcas físicas respecto al inicio de la unidad.", "Analiza su progresión motriz y resistencia aeróbica comparando los resultados con su línea base diagnóstica.", "Ficha de evaluación física comparada con evidencia de mejora en resistencia, fuerza y flexibilidad.", "Evalúa progresión física.", "Autonomía Motriz")
            ]
            skills_eje_2 = [
                ("Control de la frecuencia cardíaca antes, durante y después del ejercicio", "Toma el pulso radial y carotídeo en 15 segundos y calcula pulsaciones por minuto.", "Monitorea su frecuencia cardíaca para autorregular la intensidad del esfuerzo y mantenerse en zona aeróbica segura.", "Registro de frecuencia cardíaca en reposo, en esfuerzo máximo y en recuperación de 3 minutos.", "Monitorea frecuencia cardíaca.", "Salud y Ejercicio"),
                ("Hidratación adecuada y balance de líquidos en el esfuerzo físico", "Explica la importancia de beber agua antes, durante y después del deporte.", "Reconoce los signos tempranos de deshidratación y planifica pautas de consumo hídrico según el clima y desgaste.", "Plan personal de hidratación deportiva con horarios y volúmenes de ingesta recomendados para días de entrenamiento.", "Planifica hidratación deportiva.", "Hábitos Saludables"),
                ("Calentamiento preventivo y elongación muscular específica", "Dirige una secuencia de activación fisiológica general y estiramientos.", "Diseña y ejecuta rutinas de calentamiento dinámico y movilidad articular para prevenir desgarros y esguinces.", "Rutina guiada de activación fisiológica de 10 minutos con estiramientos musculares progresivos.", "Aplica calentamiento preventivo.", "Prevención de Lesiones"),
                ("Alimentación balanceada y requerimientos calóricos del adolescente", "Calcula el aporte de carbohidratos, proteínas y lípidos en su dieta diaria.", "Evalúa su ingesta nutricional diaria contrastándola con el gasto calórico de sus actividades escolares y físicas.", "Menú semanal saludable con distribución calórica balanceada adaptada a la actividad física regular.", "Planifica dieta equilibrada.", "Nutrición Saludable"),
                ("Higiene personal post entrenamiento y aseo corporal", "Aplica el lavado de manos, cambio de indumentaria y duchado tras la clase.", "Practica hábitos rigurosos de aseo e higiene personal después de la actividad motriz para prevenir infecciones.", "Lista de verificación de hábitos de higiene deportiva con cumplimiento sistemático de normas de aseo.", "Practica higiene personal.", "Cuidado Corporal"),
                ("Ergonomía postural en la vida escolar y prevención de dorsalgias", "Corrige la postura al sentarse, levantar cargas pesadas y usar mochila.", "Aplica principios ergonómicos para mantener una postura corporal equilibrada en actividades cotidianas de carga.", "Guía gráfica de corrección postural con autoevaluación de posturas ergonómicas en aula y hogar.", "Aplica ergonomía postural.", "Salud Ocupacional"),
                ("Primeros auxilios básicos ante contusiones y torceduras (método RICE)", "Aplica reposo, hielo, compresión y elevación frente a lesiones comunes.", "Aplica el protocolo RICE de primeros auxilios ante golpes y esguinces en la práctica deportiva escolar.", "Simulación práctica de atención básica de primeros auxilios ante un esguince de tobillo simulado.", "Aplica primeros auxilios.", "Seguridad Deportiva"),
                ("Diseño de un plan semanal de actividad física familiar", "Organiza rutinas de caminatas, baile o bicicleta para su entorno familiar.", "Propone un programa de actividad física recreativa familiar para contrarrestar el sedentarismo en su hogar.", "Cronograma familiar de actividad física semanal con registro de participantes y actividades recreativas.", "Promueve actividad familiar.", "Vida Activa"),
                ("Consolidación del estilo de vida saludable y autonomía corporal", "Sustenta compromisos personales de bienestar físico y salud mental.", "Sustenta un compromiso personal de hábitos activos y alimentación sana como pilar de su bienestar integral.", "Portafolio de vida saludable con compromisos firmados, evolución de su IMC y metas de ejercicio continuo.", "Asume estilo de vida saludable.", "Bienestar Integral")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Educación Física. Lima: MINEDU.",
                "Organización Mundial de la Salud (OMS) (2020). Directrices de la OMS sobre actividad física y hábitos sedentarios. Ginebra.",
                "Blázquez, D. (2017). Métodos de enseñanza en educación física: Enfoques innovadores para la enseñanza deportiva. Barcelona: INDE.",
                "MINEDU (2020). Orientaciones para la promoción de la actividad física y salud escolar. Lima: MINEDU.",
                "Instituto Peruano del Deporte (IPD) - Guías Técnicas de Deporte Escolar."
            ]

        # 9. EDUCACIÓN RELIGIOSA
        elif "relig" in spec_lower:
            spec_prog = "Educación Religiosa"
            area_display = "Educación Religiosa"
            prog_display = f"Educación Secundaria - {spec_prog}"
            coordinador_nom = "Coordinador Pedagógico de Educación Religiosa"
            coordinador_cargo = "COORDINADOR PEDAGÓGICO DE HUMANIDADES"
            subdirector_cargo = "SUB-DIRECTOR"
            enfoque_area = "Enfoque Humanista Cristiano y Cristocéntrico"

            eje_1_nombre = "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente"
            eje_2_nombre = "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida"

            mod_default = f"Valores evangélicos, dignidad de la persona humana y solidaridad comunitaria: {cleaned_topic}"
            eje_1_estandar = "Construye su identidad como persona humana amada por Dios al comprender la doctrina de su religión. Reconoce su dignidad, libertad y dimensión trascendente a la luz del mensaje de Jesucristo y promueve el diálogo fraterno con otras confesiones religiosas."
            eje_2_estandar = "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida. Actúa coherentemente en razón de su fe, participa en la misión de la Iglesia promoviendo la justicia, la paz y el cuidado de la creación con testimonio de servicio solidario."

            skills_eje_1 = [
                (f"La dignidad inalienable de la persona humana en {cleaned_topic}", "Reconoce que toda vida humana es sagrada y creada a imagen y semejanza de Dios.", "Fundamenta la dignidad inalienable de toda persona a partir del relato bíblico de la Creación y el magisterio social.", "Ensayo reflexivo sobre la dignidad humana como fundamento de los derechos universales frente a la discriminación.", "Fundamenta la dignidad humana.", "Identidad Trascendente"),
                ("La revelación de Dios en la historia de la salvación", "Identifica las alianzas de Dios con su pueblo en el Antiguo Testamento.", "Explica los hitos fundamentales de la Historia de la Salvación reconociendo las promesas divinas de liberación y justicia.", "Línea de tiempo de la salvación con las grandes alianzas bíblicas comentadas desde una perspectiva ética.", "Interpreta la salvación.", "Comprensión Doctrinal"),
                ("Jesucristo y el mandamiento del amor fraterno", "Analiza el sermón de la montaña y las bienaventuranzas evangélicas.", "Interpreta las Bienaventuranzas como camino de felicidad plena y propuesta ética frente al individualismo moderno.", "Ficha de análisis de las Bienaventuranzas aplicadas a situaciones de injusticia y vulnerabilidad social actual.", "Aplica las Bienaventuranzas.", "Valores Evangélicos"),
                ("El magisterio eclesial y la encíclica Laudato Si'", "Examina el llamado del Papa Francisco al cuidado de la casa común.", "Sustenta acciones ecológicas comunitarias inspiradas en la encíclica Laudato Si' para la protección del medio ambiente.", "Propuesta de acción ecológica escolar orientada a la conservación ambiental como deber moral cristiano.", "Promueve ecología integral.", "Compromiso Social"),
                ("Libertad, conciencia moral y discernimiento de valores", "Distingue la libertad responsable del libertinaje en sus elecciones cotidianas.", "Aplica el discernimiento moral cristiano para tomar decisiones orientadas al bien de sí mismo y de su prójimo.", "Cuadro de discernimiento ético frente a decisiones de presión de grupo analizadas a la luz del Evangelio.", "Discierne con conciencia moral.", "Autonomía Ética"),
                ("Las parábolas de misericordia: el Buen Samaritano", "Examina el significado del prójimo y la compasión activa en la sociedad.", "Analiza la parábola del Buen Samaritano deduciendo compromisos concretos de auxilio hacia los marginados.", "Comentario exegético sobre el Buen Samaritano con compromisos concretos de solidaridad comunitaria en Chancay.", "Practica la misericordia.", "Solidaridad Cristiana"),
                ("El perdón y la reconciliación comunitaria", "Reflexiona sobre el poder sanador del perdón frente al rencor y la venganza.", "Argumenta la necesidad del perdón y la reconciliación para sanar heridas emocionales y reconstruir el tejido familiar.", "Texto de reflexión personal sobre experiencias de perdón sincero y restauración de vínculos familiares rotos.", "Promueve reconciliación.", "Cultura de Paz"),
                ("Diálogo interreligioso y respeto a la libertad de cultos", "Reconoce valores comunes de compasión y paz en diversas religiones.", "Promueve el respeto y el diálogo ecuménico e interreligioso valorando la búsqueda de la trascendencia en la humanidad.", "Panel de investigación comparativa sobre principios éticos de las grandes religiones del mundo.", "Respeta diversidad religiosa.", "Diálogo Interreligioso"),
                ("Consolidación de la fe y proyecto de vida trascendente", "Formula un compromiso ético de vida basado en las enseñanzas de Jesús.", "Sintetiza sus aprendizajes en un proyecto de vida inspirado en el servicio al prójimo y la búsqueda de la justicia.", "Credo personal y declaración de principios éticos con compromisos de servicio solidario para su juventud.", "Asume proyecto de fe.", "Trascendencia")
            ]
            skills_eje_2 = [
                ("La oración como diálogo personal y comunitario con Dios", "Conoce diversas formas de oración: petición, alabanza y acción de gracias.", "Practica la oración reflexiva como fuente de fortaleza interior y discernimiento personal ante desafíos cotidianos.", "Guía de oración comunitaria redactada por el estudiante con peticiones por la paz y el bienestar local.", "Practica la oración reflexiva.", "Vida de Fe"),
                ("Los sacramentos como signos eficaces de gracia y vida eclesial", "Explica el significado del Bautismo, la Eucaristía y la Confirmación.", "Explica el valor vivencial de los sacramentos de iniciación cristiana en la maduración de la fe comunitaria.", "Organizador visual sobre los sacramentos de iniciación y su compromiso en la vida cotidiana del creyente.", "Comprende los sacramentos.", "Vida Eclesial"),
                ("La vivencia litúrgica de los tiempos litúrgicos (Cuaresma, Adviento)", "Identifica el sentido de conversión y esperanza en las fiestas cristianas.", "Participa reflexivamente en los tiempos litúrgicos del calendario eclesial asumiendo gestos de sobriedad y caridad.", "Calendario litúrgico comentado con propuestas de acciones caritativas para vivir el tiempo de gracia.", "Vive los tiempos litúrgicos.", "Celebración de la Fe"),
                ("Testimonio de vida de santos peruanos: Santa Rosa y San Martín", "Examina la caridad y humildad de Santa Rosa de Lima y San Martín de Porres.", "Valora el ejemplo de servicio desinteresado y cercanía a los enfermos de los santos peruanos como modelos cívicos.", "Biografía crítica comentada de San Martín de Porres destacando su labor social y fraternidad universal.", "Sigue modelos de santidad.", "Testimonio Cristiano"),
                ("Acción solidaria y voluntariado en la parroquia o escuela", "Organiza campañas de recolección de víveres o ropa para familias necesitadas.", "Diseña y ejecuta una campaña solidaria de ayuda humanitaria coordinada con organizaciones eclesiales o locales.", "Plan de campaña solidaria con cronograma de acopio, distribución transparente y evaluación del impacto social.", "Organiza voluntariado social.", "Caridad Activa"),
                ("Cuidado de los enfermos y visita a ancianos vulnerables", "Reflexiona sobre la ternura y acompañamiento a personas solas de la comunidad.", "Propone acciones de acompañamiento fraterno y escucha activa hacia personas de la tercera edad o enfermas.", "Registro de acciones solidarias de visita y acompañamiento a adultos mayores con compromisos sostenidos.", "Acompaña a personas vulnerables.", "Compasión Cristiana"),
                ("La defensa de la paz y la no violencia activa en la juventud", "Rechaza el acoso escolar, el pandillaje y la violencia doméstica desde la fe.", "Formula propuestas de prevención de la violencia en el colegio inspiradas en la bienaventuranza de los constructores de paz.", "Campaña escolar por la paz y el desarme verbal con lemas y actividades de mediación inspiradas en el Evangelio.", "Construye la paz.", "Cultura de Paz"),
                ("El compromiso misionero de los jóvenes en su entorno", "Transmite alegría, esperanza y valores éticos en sus redes sociales y amigos.", "Ejerce un liderazgo juvenil misionero comunicando mensajes de esperanza y defensa de la vida en entornos digitales.", "Campaña digital de valores con mensajes positivos y citas bíblicas ilustradas creadas para redes juveniles.", "Comunica esperanza cristiana.", "Misión y Testimonio"),
                ("Celebración comunitaria de acción de gracias y servicio", "Participa en una liturgia de acción de gracias por los logros del periodo.", "Diseña comunitariamente una celebración litúrgica o acto de acción de gracias renovando compromisos de vida fraterna.", "Guion litúrgico de acción de gracias con lecturas seleccionadas, ofrendas representativas y oración compartida.", "Celebra en comunidad.", "Acción de Gracias")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Educación Religiosa. Lima: MINEDU.",
                "Biblia de América o Biblia de Jerusalén (Edición pastoral oficial).",
                "Papa Francisco (2015). Carta Encíclica Laudato Si' sobre el cuidado de la casa común. Roma: Tipografía Vaticana.",
                "Catecismo de la Iglesia Católica (Compendio pastoral). Lima: Conferencia Episcopal Peruana.",
                "Oficina Nacional de Educación Católica (ONDEC) - Guías pedagógicas de Educación Religiosa."
            ]

        # 10. EDUCACIÓN PARA EL TRABAJO (EPT)
        else:
            spec_prog = cleaned_specialty
            area_display = "Educación para el Trabajo"
            prog_display = f"Educación Técnica - {spec_prog}"

            spec_l = cleaned_specialty.lower()
            if "comput" in spec_l or "inform" in spec_l:
                jefe_taller_nom = "Mg. Luis Arturo La Rosa Gallardo"
                jefe_taller_cargo = "JEFE DE TALLER COMPUTACIÓN E INFORMÁTICA"
                mod_default = "Aplica herramientas de productividad, almacenamiento y colaboración en la nube"
            elif "mecan" in spec_l or "torno" in spec_l:
                jefe_taller_nom = "Prof. Responsable de Taller de Mecánica"
                jefe_taller_cargo = "JEFE DE TALLER MECÁNICA DE PRODUCCIÓN"
                mod_default = "Mecanizado de piezas por arranque de viruta en máquinas herramientas y soldadura"
            elif "electr" in spec_l:
                jefe_taller_nom = "Prof. Responsable de Taller de Electricidad"
                jefe_taller_cargo = "JEFE DE TALLER ELECTRICIDAD Y ELECTRÓNICA"
                mod_default = "Instalaciones eléctricas residenciales, industriales y control electrónico de potencia"
            else:
                jefe_taller_nom = f"Jefe de Taller de {cleaned_specialty}"
                jefe_taller_cargo = f"JEFE DE TALLER {cleaned_specialty.upper()[:25]}"
                mod_default = f"Módulo Formativo de {cleaned_specialty}: {cleaned_topic}"

            coordinador_nom = jefe_taller_nom
            coordinador_cargo = jefe_taller_cargo
            subdirector_cargo = "SUB-DIRECTOR DE ÁREA TÉCNICA"
            enfoque_area = "Pedagogía de Emprendimiento y Método de Acción Completa (GTZ)"

            eje_1_nombre = "Habilidades Técnicas Específicas de Taller"
            eje_2_nombre = "Gestiona proyectos de emprendimiento económico o social"

            eje_1_estandar = f"Aplica habilidades técnicas especializadas en el módulo formativo de {cleaned_specialty}, ejecutando operaciones con máquinas herramientas, cumpliendo normas de seguridad industrial 5S, tolerancias técnicas y criterios de calidad industrial."
            eje_2_estandar = "Gestiona proyectos de emprendimiento económico o social cuando formula modelos de negocio innovadores, valida hipótesis del lienzo Lean Canvas mediante entrevistas de problemas y soluciones, y evalúa la viabilidad comercial y social del prototipo."

            skills_eje_1 = [
                (f"Normas de seguridad industrial 5S e inducción de taller en {cleaned_specialty}", "Aplica protocolos de bioseguridad, orden y uso de EPP en el taller.", "Aplica estrictamente las normas de seguridad industrial 5S y verifica el estado de operatividad de los instrumentos de trabajo.", "Ficha de inspección de seguridad en taller diligenciada y puesto de trabajo acondicionado según protocolo 5S.", "Cumple normas de seguridad en taller.", "Seguridad Industrial"),
                (f"Lectura e interpretación de planos técnicos y hojas de operaciones", "Interpreta especificaciones técnicas, cotas y simbología normalizada.", "Interpreta planos y diagramas técnicos normalizados identificando tolerancias, materiales y secuencias de mecanizado/instalación.", "Hoja de procesos y operaciones técnicas elaborada con croquis acotado y secuencia de tareas definida.", "Interpreta planos técnicos.", "Rigor Operativo"),
                (f"Preparación y calibración de máquinas herramientas e instrumental", "Acondiciona parámetros de velocidad, avance y lubricación de equipos.", "Realiza la calibración y ajuste previo de instrumentos de medición y máquinas respetando las especificaciones de fábrica.", "Checklist de calibración de instrumental técnico y parámetros de mecanizado/configuración verificados.", "Calibra instrumental técnico.", "Mantenimiento Técnico"),
                (f"Ejecución de operaciones básicas del módulo formativo de {cleaned_specialty}", "Ejecuta procesos de corte, desbaste o configuración según diseño.", "Ejecuta operaciones técnicas fundamentales empleando herramientas adecuadas y controlando tolerancias dimensionales.", "Pieza técnica/proyecto en proceso ejecutado cumpliendo los estándares y especificaciones de calidad iniciales.", "Ejecuta operaciones técnicas.", "Destreza Operativa"),
                (f"Operaciones intermedias y ensamble de subcomponentes técnicos", "Aplica uniones mecánicas, eléctricas o de software con precisión.", "Realiza ensambles y conexiones técnicas intermedias verificando continuidad, ajuste mecánico y fijación segura.", "Subcomponente técnico ensamblado con verificación de ajuste y pruebas funcionales intermedias.", "Ensambla subcomponentes técnicos.", "Control de Calidad"),
                (f"Mecanizado o montaje especializado según proyecto de especialidad", "Realiza operaciones avanzadas de acabado, conexionado o programación.", "Aplica técnicas especializadas del módulo formativo optimizando el rendimiento de insumos y tiempos de ejecución.", "Producto técnico terminado según tolerancias requeridas y especificaciones del cliente.", "Aplica técnicas especializadas.", "Destreza Operativa"),
                (f"Control de calidad dimensional, pruebas de carga y verificación", "Comprueba el producto final con calibrador vernier, multímetro o test suite.", "Inspecciona la calidad del producto aplicando instrumentos de medición de precisión y contrastando con la ficha técnica.", "Ficha de control de calidad final con medidas registradas, tolerancias verificadas y visto bueno técnico.", "Verifica calidad del producto.", "Control de Calidad"),
                (f"Mantenimiento preventivo de máquinas y orden del taller técnico", "Limpia, lubrica y preserva máquinas, herramientas y banco de trabajo.", "Ejecuta el protocolo de mantenimiento preventivo de primer nivel de la maquinaria utilizada y clasifica residuos.", "Puesto de taller y máquinas limpias, lubricadas y residuos sólidos clasificados según norma ambiental.", "Ejecuta mantenimiento preventivo.", "Cuidado del Taller"),
                (f"Evaluación técnica y entrega de producto final terminado", "Sustenta la viabilidad técnica y operativa de la pieza o sistema elaborado.", "Sustenta el proceso de fabricación o servicio técnico ejecutado demostrando dominio de competencias técnicas de taller.", "Portafolio técnico de especialidad con hojas de operaciones, plano final y producto culminado expuesto.", "Sustenta producto técnico.", "Competencia Profesional")
            ]
            skills_eje_2 = [
                ("Design Thinking: Fase Empatizar y observación de necesidades", "Aplica entrevistas de problemas a potenciales usuarios de Chancay.", "Recopila información cualitativa sobre necesidades insatisfechas de la comunidad mediante técnicas de inmersión y entrevista.", "Mapa de empatía diligenciado con hallazgos de usuarios y necesidades reales identificadas.", "Empatiza con usuarios reales.", "Design Thinking"),
                ("Design Thinking: Fase Definir y formulación del reto (POV)", "Sintetiza la información y formula el Punto de Vista (POV) creativo.", "Define el problema central formulando la pregunta retadora '¿Cómo podríamos nosotros...?' orientada a una solución innovadora.", "Declaración del POV y pregunta retadora formulada con foco en el usuario y su necesidad crítica.", "Define el reto de diseño.", "Innovación"),
                ("Design Thinking: Fase Idear y selección de la propuesta de valor", "Genera múltiples alternativas de solución mediante lluvia de ideas (Brainstorming).", "Aplica técnicas de pensamiento divergente y selecciona la propuesta de valor más viable, factible y deseable.", "Matriz de selección de ideas innovadoras con criterios de ponderación y propuesta ganadora delimitada.", "Genera ideas innovadoras.", "Creatividad Emprendedora"),
                ("Lienzo Lean Canvas: Bloque Problema, Segmento y Propuesta Única", "Estructura los tres primeros bloques del modelo de negocio en equipo.", "Formula las hipótesis de problemas, segmentos de clientes (early adopters) y propuesta única de valor en el lienzo Lean Canvas.", "Lienzo Lean Canvas con los bloques 1, 2 y 3 formulados con claridad y enfoque en el cliente objetivo.", "Modela en Lean Canvas.", "Gestión de Negocios"),
                ("Design Thinking: Fase Prototipar (baja fidelidad)", "Elabora bocetos, mockups o maquetas de la solución propuesta.", "Construye un prototipo de baja fidelidad que permite visualizar y comunicar los atributos clave de la propuesta de valor.", "Prototipo de baja fidelidad (mockup físico o digital) listo para ser testeado con potenciales usuarios.", "Construye prototipos iniciales.", "Prototipado"),
                ("Design Thinking: Fase Evaluar y testeo de la solución con usuarios", "Aplica la malla receptora de información con usuarios reales de Chancay.", "Testea el prototipo con usuarios objetivos registrando críticas constructivas, dudas y nuevas ideas en la malla receptora.", "Malla receptora de información completada con retroalimentación sistematizada de al menos 3 usuarios.", "Testea con usuarios reales.", "Validación de Hipótesis"),
                ("Lienzo Lean Canvas: Canales, Flujos de Ingreso y Estructura de Costos", "Modela los bloques de comercialización y finanzas del emprendimiento.", "Estructura los canales de distribución física y digital, calcula el punto de equilibrio y define las fuentes de ingreso.", "Lienzo Lean Canvas completado en sus 9 bloques con estimación de costos unitarios y precio de venta.", "Estructura finanzas del negocio.", "Cultura Financiera"),
                ("Pivoteo del modelo de negocio y mejoras en el prototipo", "Modifica bloques del Lean Canvas a partir de las evidencias obtenidas.", "Incorpora mejoras sustantivas en el producto y ajusta las hipótesis comerciales a partir de los datos de validación.", "Lienzo Lean Canvas versión 2.0 con hipótesis validadas y prototipo mejorado de media/alta fidelidad.", "Pivotea el modelo comercial.", "Resiliencia Emprendedora"),
                ("Elevator Pitch y defensa del proyecto de emprendimiento", "Prepara y expone un discurso de ventas persuasivo de 3 minutos.", "Comunica con convicción y argumentos comerciales la propuesta de valor de su emprendimiento ante un jurado simulado.", "Exposición oral del Elevator Pitch grabada o presencial con presentación visual y defensa de métricas clave.", "Comunica propuesta de valor.", "Liderazgo Emprendedor")
            ]

            bibliografia = [
                "MINEDU (2016). Currículo Nacional de la Educación Básica (CNEB). Lima: Ministerio de Educación.",
                "MINEDU (2016). Programa Curricular de Educación Secundaria - Área de Educación para el Trabajo. Lima: MINEDU.",
                "Maurya, A. (2014). Running Lean: Cómo iterar de un plan A a un plan que funcione. Barcelona: Deusto.",
                "Osterwalder, A. y Pigneur, Y. (2011). Generación de modelos de negocio. Barcelona: Deusto.",
                "Agencia de Cooperación Técnica Alemana (GTZ) (2010). Método de Proyectos de Acción Completa en la Formación Técnica.",
                "Catálogos Nacionales de la Oferta Formativa (CNOF) del Ministerio de Educación del Perú."
            ]

        # -------------------------------------------------------------
        # ADAPTACIÓN DINÁMICA DE EXTENSIÓN PARA 9, 10, 11 O 12 SEMANAS
        # -------------------------------------------------------------
        while len(skills_eje_1) < duration_weeks:
            ext_num = len(skills_eje_1) + 1
            if is_ept:
                skills_eje_1.append((
                    f"Consolidación de proyectos técnicos especializados (Semana {ext_num})",
                    f"Ejecuta tareas avanzadas de producción o servicio en el taller de {cleaned_specialty}.",
                    f"Aplica especificaciones de calidad industrial y seguridad en la fabricación técnica avanzada.",
                    f"Producto técnico terminado verificado según tolerancia y normas de taller.",
                    "Consolida capacidades técnicas.",
                    "Rigor Técnico"
                ))
            else:
                if ext_num == 10:
                    skills_eje_1.append((
                        f"Evaluación de logros y resolución de problemas complejos en {cleaned_topic}",
                        f"Resuelve situaciones complejas de evaluación aplicando autónomamente las competencias de {eje_1_nombre}.",
                        f"Modela y sustenta procedimientos de resolución de problemas complejos verificando la consistencia de sus respuestas.",
                        f"Ficha de evaluación integral resuelta con justificación analítica de procedimientos.",
                        f"Consolida competencias de {eje_1_nombre}.",
                        "Pensamiento Crítico"
                    ))
                elif ext_num == 11:
                    skills_eje_1.append((
                        f"Aplicación interdisciplinaria de competencias de {spec_prog} (Semana 11)",
                        f"Modela situaciones del entorno local de Chancay integrando competencias curriculares.",
                        f"Aplica modelos conceptuales de {spec_prog} en el análisis de problemas comunitarios sustentando conclusiones.",
                        f"Informe de aplicación contextualizada con recomendaciones para la comunidad.",
                        "Aplica competencias en su entorno.",
                        "Compromiso Social"
                    ))
                else:
                    skills_eje_1.append((
                        f"Refuerzo pedagógico y sistematización curricular (Semana {ext_num})",
                        f"Sistematiza los aprendizajes clave de la unidad mediante retroalimentación reflexiva.",
                        f"Explica con argumentos sólidos los conceptos y procedimientos desarrollados en la unidad didáctica.",
                        f"Portafolio final de evidencias de aprendizaje consolidado y autoevaluado.",
                        "Sistematiza aprendizajes clave.",
                        "Autonomía en el Aprendizaje"
                    ))

        while len(skills_eje_2) < duration_weeks:
            ext_num = len(skills_eje_2) + 1
            if is_ept:
                skills_eje_2.append((
                    f"Sistematización y escalabilidad del emprendimiento (Semana {ext_num})",
                    "Sistematiza lecciones aprendidas y elabora el plan de escalabilidad para futuros proyectos.",
                    "Evalúa el modelo de negocio validado formulando estrategias de crecimiento comercial y sostenibilidad.",
                    "Plan de escalabilidad y lecciones aprendidas del proyecto de emprendimiento.",
                    "Consolida el portafolio de emprendimiento.",
                    "Visión de Negocio"
                ))
            else:
                if ext_num == 10:
                    skills_eje_2.append((
                        f"Evaluación formativa y síntesis articuladora en {eje_2_nombre}",
                        f"Consolida las competencias articuladoras de la unidad mediante análisis de casos y reflexión crítica.",
                        f"Analiza situaciones complejas aplicando las capacidades de {eje_2_nombre} con rigor y coherencia.",
                        f"Ficha de síntesis y autoevaluación formativa con conclusiones fundamentadas.",
                        f"Demuestra dominio de las capacidades de {eje_2_nombre}.",
                        "Juicio Crítico"
                    ))
                elif ext_num == 11:
                    skills_eje_2.append((
                        f"Presentación de proyectos interdisciplinarios (Semana 11)",
                        f"Expone soluciones integradas a problemáticas del entorno social y ambiental de Chancay.",
                        f"Sustenta propuestas de solución comunitaria articulando saberes interdisciplinarios con ética ciudadana.",
                        f"Panel de exposición y defensa de propuestas interdisciplinarias frente al aula.",
                        "Aplica conocimientos con enfoque ético.",
                        "Orientación al Bien Común"
                    ))
                else:
                    skills_eje_2.append((
                        f"Nivelación y consolidación de competencias (Semana {ext_num})",
                        f"Aplica retroalimentación reflexiva para asegurar el logro de los aprendizajes previstos.",
                        f"Demuestra superación de dificultades de aprendizaje en las competencias evaluadas de la unidad.",
                        f"Ficha de mejora de aprendizajes con evidencias corregidas y explicadas.",
                        "Desarrolla autonomía en el aprendizaje.",
                        "Búsqueda de la Excelencia"
                    ))

        # -------------------------------------------------------------
        # CONSTRUCCIÓN DE LAS MATRICES CURRICULARES (TABLAS 1 Y 2)
        # -------------------------------------------------------------
        matrix_1 = []
        for w in range(1, duration_weeks + 1):
            s_tit, s_des, s_crit, s_evid, s_est, s_eje = skills_eje_1[w - 1]
            matrix_1.append({
                "semana": w,
                "habilidad_tecnica": s_tit,
                "habilidad_o_desempeno": s_tit,
                "desempenos": s_des,
                "criterio_evaluacion": s_crit,
                "evidencia_aprendizaje": s_evid,
                "estandar_modulo": s_est or eje_1_estandar,
                "ejes_transversales": s_eje
            })

        matrix_2 = []
        for w in range(1, duration_weeks + 1):
            s_tit, s_des, s_crit, s_evid, s_est, s_eje = skills_eje_2[w - 1]
            matrix_2.append({
                "semana": w,
                "habilidad_emprendimiento": s_tit,
                "habilidad_o_desempeno": s_tit,
                "desempenos": s_des,
                "criterio_evaluacion": s_crit,
                "evidencia_aprendizaje": s_evid,
                "estandar_ciclo": s_est or eje_2_estandar,
                "ejes_transversales": s_eje
            })

        # -------------------------------------------------------------
        # DISTRIBUCIÓN DE HORAS POR SESIÓN Y GENERACIÓN DE SESIONES
        # -------------------------------------------------------------
        if is_ept:
            h_s1 = 5
            h_s2 = 3
        else:
            if final_weekly_hours == 5:
                h_s1 = 3
                h_s2 = 2
            elif final_weekly_hours == 4:
                h_s1 = 2
                h_s2 = 2
            elif final_weekly_hours == 3:
                h_s1 = 2
                h_s2 = 1
            elif final_weekly_hours == 2:
                h_s1 = 2
                h_s2 = 0
            else:
                h_s1 = final_weekly_hours // 2
                h_s2 = final_weekly_hours - h_s1

        sessions_plan: List[Dict[str, Any]] = []
        s_counter = 1

        for w in range(1, duration_weeks + 1):
            s1_tit, s1_des, s1_crit, s1_evid, _, _ = skills_eje_1[w - 1]
            s2_tit, s2_des, s2_crit, s2_evid, _, _ = skills_eje_2[w - 1]

            if is_ept:
                sessions_plan.append({
                    "semana": w, "week": w,
                    "numero_sesion": s_counter, "session_number": s_counter,
                    "tipo_sesion": "tecnica",
                    "titulo": f"Sesión {s_counter:02d}: {s1_tit}",
                    "activity_title": s1_tit,
                    "proposito": s1_des,
                    "criterio_evaluacion": s1_crit,
                    "evidencia_aprendizaje": s1_evid,
                    "horas_pedagogicas": h_s1, "duration_hours": h_s1,
                    "duracion_minutos": h_s1 * 45, "duration_minutes": h_s1 * 45,
                    "metodologia": "Acción Completa (GTZ)"
                })
                s_counter += 1

                sessions_plan.append({
                    "semana": w, "week": w,
                    "numero_sesion": s_counter, "session_number": s_counter,
                    "tipo_sesion": "emprendimiento",
                    "titulo": f"Sesión {s_counter:02d}: {s2_tit}",
                    "activity_title": s2_tit,
                    "proposito": s2_des,
                    "criterio_evaluacion": s2_crit,
                    "evidencia_aprendizaje": s2_evid,
                    "horas_pedagogicas": h_s2, "duration_hours": h_s2,
                    "duracion_minutos": h_s2 * 45, "duration_minutes": h_s2 * 45,
                    "metodologia": "Design Thinking / Lean Canvas"
                })
                s_counter += 1
            else:
                sessions_plan.append({
                    "semana": w, "week": w,
                    "numero_sesion": s_counter, "session_number": s_counter,
                    "tipo_sesion": eje_1_nombre,
                    "titulo": f"Sesión {s_counter:02d}: {s1_tit}",
                    "activity_title": s1_tit,
                    "proposito": s1_des,
                    "criterio_evaluacion": s1_crit,
                    "evidencia_aprendizaje": s1_evid,
                    "horas_pedagogicas": h_s1, "duration_hours": h_s1,
                    "duracion_minutos": h_s1 * 45, "duration_minutes": h_s1 * 45,
                    "metodologia": enfoque_area
                })
                s_counter += 1

                if h_s2 > 0:
                    sessions_plan.append({
                        "semana": w, "week": w,
                        "numero_sesion": s_counter, "session_number": s_counter,
                        "tipo_sesion": eje_2_nombre,
                        "titulo": f"Sesión {s_counter:02d}: {s2_tit}",
                        "activity_title": s2_tit,
                        "proposito": s2_des,
                        "criterio_evaluacion": s2_crit,
                        "evidencia_aprendizaje": s2_evid,
                        "horas_pedagogicas": h_s2, "duration_hours": h_s2,
                        "duracion_minutos": h_s2 * 45, "duration_minutes": h_s2 * 45,
                        "metodologia": enfoque_area
                    })
                    s_counter += 1

        mod_form = formative_module or mod_default
        title = f"UNIDAD DIDÁCTICA N° {unit_number:02d}: {cleaned_topic.upper()} ({grade_str} Sec. - {spec_prog})"

        # Descripción pedagógica institucional situada en Chancay
        if is_ept:
            desc_unidad = (
                f"El módulo formativo «{mod_form}» de la especialidad de {cleaned_specialty} en CET N.º 34 (Chancay) "
                f"tiene como propósito desarrollar en los estudiantes de {grade_str} de educación secundaria habilidades técnicas "
                f"operativas de taller y capacidades de gestión de emprendimiento económico o social. A lo largo de {duration_weeks} "
                f"semanas ({total_horas_calculadas} horas pedagógicas), los estudiantes experimentan el método de proyectos de Acción Completa (GTZ) "
                f"integrado con metodologías ágiles de Design Thinking y Lean Canvas, permitiéndoles transformar necesidades reales "
                f"del entorno portuario, agrícola y comercial de la provincia de Huaral en propuestas productivas sostenibles, "
                f"respetando rigurosamente las normas de seguridad industrial 5S, control de calidad y preservación del medio ambiente."
            )
        else:
            desc_unidad = (
                f"La presente unidad didáctica del área curricular de {spec_prog} correspondiente al {grade_str} de educación secundaria "
                f"({ciclo_label}) en la I.E. INEI N.º 34 de Chancay, se orienta al desarrollo articulado de las competencias fundamentales "
                f"«{eje_1_nombre}» y «{eje_2_nombre}». Durante las {duration_weeks} semanas programadas en el {bimester_clean} "
                f"({total_horas_calculadas} horas pedagógicas en total, a razón de {final_weekly_hours} horas semanales), los estudiantes abordan "
                f"situaciones significativas auténticas vinculadas al desarrollo social, económico y ambiental de la comunidad de Chancay, "
                f"aplicando el {enfoque_area.lower()} para formular soluciones fundamentadas, reflexivas y con rigor científico-humanístico "
                f"alineado a los estándares de aprendizaje establecidos en el Currículo Nacional de la Educación Básica (CNEB)."
            )

        propositos_tecnicos = {
            "competencia": eje_1_nombre,
            "estandar_esperado": eje_1_estandar,
            "habilidades_priorizadas": [item["habilidad_o_desempeno"] for item in matrix_1]
        }
        propositos_emprendimiento = {
            "competencia": eje_2_nombre,
            "estandar_esperado": eje_2_estandar,
            "habilidades_priorizadas": [item["habilidad_o_desempeno"] for item in matrix_2]
        }

        # Estructuración final para Pydantic y serialización limpia
        unit_structured = {
            "is_ept": is_ept,
            "eje_curricular_1_nombre": eje_1_nombre,
            "eje_curricular_2_nombre": eje_2_nombre,
            "datos_generales": {
                "institucion": "CET 34 (I.E. INEI N.º 34)",
                "dre_ugel": "DRE Lima Provincias • UGEL Nº 10 - Huaral",
                "area_curricular": area_display,
                "especialidad": prog_display,
                "modulo_formativo": mod_form,
                "grado": grade,
                "grado_secciones": f'{grade_str}: "{section_name}"',
                "seccion": section_name,
                "docente_responsable": final_teacher,
                "director": "Tomas Jurado Zevallos",
                "subdirector": "Mg. Javier Eulogio Rosas Maguiña",
                "jefe_taller": coordinador_nom,
                "coordinador_cargo": coordinador_cargo,
                "fecha_inicio": f_ini_l,
                "fecha_fin": f_fin_l,
                "fecha_inicio_corta": f_ini_c,
                "fecha_fin_corta": f_fin_c,
                "periodo": p_texto,
                "duracion_semanas": duration_weeks,
                "duracion_texto": dur_display,
                "horas_semanales": final_weekly_hours,
                "total_horas": total_horas_calculadas,
                "horas_texto": horas_display,
                "bimestre": bimester_clean,
                "ano_academico": "2026",
                "titulo_unidad": title
            },
            "descripcion_unidad": desc_unidad,
            "matriz_habilidades_tecnicas": matrix_1,
            "matriz_habilidades_emprendimiento": matrix_2,
            "matriz_desempenos_1": matrix_1,
            "matriz_desempenos_2": matrix_2,
            "propositos_tecnicos": propositos_tecnicos,
            "propositos_emprendimiento": propositos_emprendimiento,
            "organizacion_sesiones": sessions_plan,
            "bibliografia": bibliografia,
            "firmas_institucionales": {
                "docente": {
                    "nombre": final_teacher,
                    "cargo": f"DOCENTE RESPONSABLE - ÁREA DE {spec_prog.upper()}" if not is_ept else "DOCENTE RESPONSABLE - ÁREA EDUCACIÓN PARA EL TRABAJO"
                },
                "jefe_taller": {
                    "nombre": coordinador_nom,
                    "cargo": coordinador_cargo
                },
                "subdirector": {
                    "nombre": "Mg. Javier Eulogio Rosas Maguiña",
                    "cargo": subdirector_cargo
                }
            }
        }

        # Validar rigurosamente coherencia numérica y aislamiento curricular de la unidad
        validation = cls.validate_didactic_unit_coherence(unit_structured)
        unit_structured["validacion"] = validation
        if not validation["is_valid"]:
            logger.warning(f"Unidad didáctica generada con inconsistencias: {validation['errors']}")

        # Generar vista Markdown legible para visualizador
        markdown_view = cls._build_unit_markdown_preview(unit_structured)

        resolved_comp = technical_competence or curr_info.get("competencia") or "Gestiona proyectos de emprendimiento económico o social"
        resolved_purp = curr_info.get("proposito") or f"Desarrollar capacidades fundamentales en torno a {cleaned_topic}"

        return {
            "title": title,
            "validation": validation,
            "is_valid": validation["is_valid"],
            "topic": cleaned_topic,
            "doc_type": "unidad_didactica",
            "content": markdown_view,
            "content_json": unit_structured,
            "specialty": cleaned_specialty,
            "competence": resolved_comp,
            "purpose": resolved_purp,
            "grade": grade,
            "section_name": section_name,
            "duration_weeks": duration_weeks,
            "weekly_hours": final_weekly_hours,
            "total_hours": total_horas_calculadas,
            "is_ept": is_ept,
            "bimester": bimester_clean,
            "unit_number": unit_number,
            "teacher_name": final_teacher,
            "status": "completed",
            "sessions_plan": sessions_plan
        }


    @classmethod
    def _build_unit_markdown_preview(cls, unit: Dict[str, Any]) -> str:
        """
        Construye la vista Markdown para el visualizador del intranet con las 9 secciones oficiales.
        """
        gen = unit.get("datos_generales") or {}
        is_ept = unit.get("is_ept", False)
        title = gen.get("titulo_unidad") or "UNIDAD DIDÁCTICA"
        dur_sem = gen.get("duracion_semanas", 9)
        tot_h = gen.get("total_horas", 72)
        h_sem = gen.get("horas_semanales", 8)

        eje_1 = unit.get("eje_curricular_1_nombre") or ("Habilidades Técnicas" if is_ept else "Competencia 1")
        eje_2 = unit.get("eje_curricular_2_nombre") or ("Gestión de Emprendimiento" if is_ept else "Competencia 2")

        m1 = unit.get("matriz_habilidades_tecnicas") or []
        m2 = unit.get("matriz_habilidades_emprendimiento") or []
        sessions = unit.get("organizacion_sesiones") or []
        biblio = unit.get("bibliografia") or []
        firmas = unit.get("firmas_institucionales") or {}

        lines = [
            f"# {title}",
            "",
            "## I. DATOS GENERALES",
            f"- **Institución Educativa:** {gen.get('institucion', 'CET 34 (I.E. INEI N.º 34)')}",
            f"- **Área Curricular:** {gen.get('area_curricular', 'Área')}",
            f"- **Programa / Especialidad:** {gen.get('especialidad', '')}",
            f"- **Módulo / Proyecto:** {gen.get('modulo_formativo', '')}",
            f"- **Grado y Sección:** {gen.get('grado_secciones', '')}",
            f"- **Duración:** {gen.get('duracion_texto', '')}",
            f"- **Horas:** {gen.get('horas_texto', f'{tot_h} horas ({dur_sem} semanas x {h_sem} horas)')}",
            f"- **Director:** {gen.get('director', 'Tomas Jurado Zevallos')}",
            f"- **Subdirector:** {gen.get('subdirector', 'Mg. Javier Eulogio Rosas Maguiña')}",
            f"- **Docente Responsable:** {gen.get('docente_responsable', '')}",
            "",
            "## II. DESCRIPCIÓN DE LOS APRENDIZAJES",
            unit.get("descripcion_unidad", ""),
            "",
            f"## III. RELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: {eje_1.upper()}",
            f"| Desempeños del grado - Matriz curricular: {eje_1} | Estándar de aprendizaje | Estructura interna del área |",
            "| :--- | :--- | :--- |",
        ]

        m1_lines = "<br>".join([f"**{i}.** {item.get('desempenos') or item.get('habilidad_o_desempeno', '')}" for i, item in enumerate(m1, 1)])
        est1 = (unit.get("propositos_tecnicos") or {}).get("estandar_esperado") or (m1[0].get("estandar_modulo") if m1 else "")
        mod1 = gen.get("modulo_formativo", "")
        lines.append(f"| {m1_lines} | *{est1}* | {mod1} |")
        lines.append("")

        lines.append(f"## IV. RELACIÓN DE LOS DESEMPEÑOS, EL ESTÁNDAR DE APRENDIZAJE Y SU ESTRUCTURA INTERNA: {eje_2.upper()}")
        lines.append(f"| Desempeños del grado - Matriz curricular articuladora: {eje_2} | Estándar de aprendizaje | Estructura interna del área |")
        lines.append("| :--- | :--- | :--- |")
        m2_lines = "<br>".join([f"**{i}.** {item.get('desempenos') or item.get('habilidad_o_desempeno', '')}" for i, item in enumerate(m2, 1)])
        est2 = (unit.get("propositos_emprendimiento") or {}).get("estandar_esperado") or (m2[0].get("estandar_ciclo") if m2 else "")
        mod2 = "Implementamos, comunicamos y mejoramos nuestro emprendimiento (Design Thinking / Lean Canvas)" if is_ept else "Articulación curricular y competencias transversales"
        lines.append(f"| {m2_lines} | *{est2}* | {mod2} |")
        lines.append("")

        lines.append(f"## V. ORGANIZACIÓN DE LOS PROPÓSITOS DE APRENDIZAJE: {eje_1.upper()}")
        lines.append("| SEMANAS | PROPÓSITO DE LA SESIÓN DE APRENDIZAJE |")
        lines.append("| :---: | :--- |")
        for i, item in enumerate(m1, 1):
            h_tit = item.get("habilidad_o_desempeno") or item.get("habilidad_tecnica", "")
            h_purp = item.get("desempenos", "")
            lines.append(f"| **Semana {i}**<br>{h_tit} | {h_purp} |")
        lines.append("")

        lines.append(f"## VI. ORGANIZACIÓN DE LOS PROPÓSITOS DE APRENDIZAJE: {eje_2.upper()}")
        lines.append("| SEMANAS | PROPÓSITO DE LA SESIÓN DE APRENDIZAJE |")
        lines.append("| :---: | :--- |")
        for i, item in enumerate(m2, 1):
            h_tit = item.get("habilidad_o_desempeno") or item.get("habilidad_emprendimiento", "")
            h_purp = item.get("desempenos", "")
            lines.append(f"| **Semana {i}**<br>{h_tit} | {h_purp} |")
        lines.append("")

        lines.append(f"## VII. ORGANIZACIÓN DE LAS {len(sessions)} SESIONES DE APRENDIZAJE ({dur_sem} SEMANAS — {tot_h} HORAS)")
        lines.append("| N° | Sem. | Tipo / Metodología | Título de la Sesión | Propósito de Aprendizaje | Criterio de Evaluación | Evidencia de Aprendizaje | Horas |")
        lines.append("| :-: | :-: | :--- | :--- | :--- | :--- | :--- | :-: |")
        for s in sessions:
            tipo_disp = s.get("tipo_sesion") or "Curricular"
            if is_ept:
                tipo_disp = "Técnica (GTZ)" if tipo_disp == "tecnica" else "Emprendimiento (Lean Canvas)"
            lines.append(
                f"| **{s.get('numero_sesion', '')}** | Sem. {s.get('semana', '')} | {tipo_disp} | "
                f"**{s.get('titulo', '')}** | {s.get('proposito', '')} | "
                f"{s.get('criterio_evaluacion', '')} | {s.get('evidencia_aprendizaje', '')} | {s.get('horas_pedagogicas', 0)} h |"
            )
        lines.append("")

        lines.append("## VIII. BIBLIOGRAFÍA Y REFERENCIAS")
        for b in biblio:
            lines.append(f"- {b}")
        lines.append("")

        lines.append("## IX. FIRMAS INSTITUCIONALES")
        doc_sig = firmas.get("docente", {})
        jefe_sig = firmas.get("jefe_taller", {})
        sub_sig = firmas.get("subdirector", {})
        lines.append(f"- **Docente Responsable:** {doc_sig.get('nombre', '')} — {doc_sig.get('cargo', '')}")
        lines.append(f"- **Coordinación / Jefatura:** {jefe_sig.get('nombre', '')} — {jefe_sig.get('cargo', '')}")
        lines.append(f"- **Subdirección:** {sub_sig.get('nombre', '')} — {sub_sig.get('cargo', '')}")

        return "\n".join(lines)


    @classmethod
    def derive_session_from_unit_row(
        cls,
        unit_data: Optional[Dict[str, Any]] = None,
        week: Optional[int] = None,
        session_type: Optional[str] = None,
        session_number: Optional[int] = None,
        user: Optional[Dict[str, Any]] = None,
        unit_row: Optional[Dict[str, Any]] = None,
        unit_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Derives a specific learning session from a row in the Didactic Unit matrix.
        Preloads title, purpose, criteria, evidence, duration (225m/135m), methodology, and unit linkage.
        If user is provided, generates the full session draft via generate_cneb_session_structured.
        """
        if unit_context is not None and (unit_data is None or not unit_data):
            unit_data = unit_context
        if unit_data is None:
            unit_data = {}

        if unit_row is not None:
            if week is None:
                week = unit_row.get("week") or unit_row.get("semana") or 1
            if session_type is None:
                session_type = unit_row.get("session_type") or unit_row.get("tipo_sesion") or "tecnica_especifica"
            if session_number is None:
                session_number = unit_row.get("session_number") or unit_row.get("numero_sesion")

        if week is None:
            week = 1
        if session_type is None:
            session_type = "tecnica_especifica"

        c_json = unit_data.get("content_json")
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}
        elif not isinstance(c_json, dict):
            c_json = {}

        sessions_plan = c_json.get("organizacion_sesiones") or unit_data.get("sessions_plan_json") or []
        if isinstance(sessions_plan, str):
            try:
                sessions_plan = json.loads(sessions_plan)
            except Exception:
                sessions_plan = []

        # Find row by week and session_type, or by session_number
        target_row = unit_row
        if not target_row:
            for s in sessions_plan:
                if session_number and (s.get("numero_sesion") == session_number or s.get("session_number") == session_number):
                    target_row = s
                    break
                s_wk = s.get("semana") or s.get("week")
                s_tp = (s.get("tipo_sesion") or s.get("session_type") or "").strip().lower()
                req_tp = (session_type or "").strip().lower()
                if s_wk == week and (s_tp == req_tp or ("tec" in s_tp and "tec" in req_tp) or ("emp" in s_tp and "emp" in req_tp)):
                    target_row = s
                    break

        is_tech = ("tec" in str(session_type).lower())
        if not target_row:
            # Fallback row if not found in list
            horas = 5 if is_tech else 3
            dur = 225 if is_tech else 135
            target_row = {
                "semana": week,
                "week": week,
                "numero_sesion": session_number or ((week - 1) * 2 + (1 if is_tech else 2)),
                "session_number": session_number or ((week - 1) * 2 + (1 if is_tech else 2)),
                "tipo_sesion": "tecnica" if is_tech else "emprendimiento",
                "session_type": "tecnica_especifica" if is_tech else "emprendimiento",
                "titulo": f"Sesión de {'Técnica Específica' if is_tech else 'Emprendimiento'} - Semana {week}",
                "proposito": f"Desarrollar capacidades en el marco de la unidad didáctica.",
                "criterio_evaluacion": f"Demuestra habilidades técnicas y de gestión pertinentes a la semana {week}.",
                "evidencia_aprendizaje": "Ficha o producto técnico del taller.",
                "horas_pedagogicas": horas,
                "duration_hours": horas,
                "duracion_minutos": dur,
                "duration_minutes": dur,
                "metodologia": "Acción Completa (GTZ)" if is_tech else "Design Thinking / Lean Canvas"
            }

        unit_id = unit_data.get("id") or unit_data.get("unit_id")
        unit_title = unit_data.get("title") or c_json.get("datos_generales", {}).get("titulo", "Unidad Didáctica")
        grade = unit_data.get("grade") or c_json.get("datos_generales", {}).get("grado", 5)
        specialty = unit_data.get("specialty") or c_json.get("datos_generales", {}).get("especialidad", "Educación para el Trabajo")
        section_name = unit_data.get("section_name") or c_json.get("datos_generales", {}).get("seccion", "A")

        title = target_row.get("titulo") or target_row.get("activity_title") or f"Sesión de Aprendizaje - Semana {week}"
        purpose = target_row.get("proposito") or target_row.get("learning_purpose")
        eval_crit = target_row.get("criterio_evaluacion") or target_row.get("evaluation_criteria")
        learning_evid = target_row.get("evidencia_aprendizaje") or target_row.get("learning_evidence")
        duration_m = target_row.get("duracion_minutos") or target_row.get("duration_minutes") or (225 if is_tech else 135)
        s_num = target_row.get("numero_sesion") or target_row.get("session_number") or ((week - 1) * 2 + (1 if is_tech else 2))

        payload = {
            "title": title,
            "topic": title,
            "grade": grade,
            "specialty": specialty,
            "section_name": section_name,
            "duration_minutes": duration_m,
            "purpose": purpose,
            "learning_purpose": purpose,
            "evaluation_criteria": eval_crit,
            "learning_evidence": learning_evid,
            "methodology": target_row.get("metodologia") or ("Acción Completa (GTZ)" if is_tech else "Design Thinking / Lean Canvas"),
            "unit_id": unit_id,
            "unit_title": unit_title,
            "week": week,
            "week_number": week,
            "session_number": s_num,
            "session_type": "tecnica_especifica" if is_tech else "emprendimiento"
        }

        if user:
            return cls.generate_cneb_session_structured(
                user=user,
                topic=payload["topic"],
                grade=payload["grade"],
                specialty=payload["specialty"],
                duration_minutes=payload["duration_minutes"],
                purpose=payload["purpose"],
                section_name=payload["section_name"],
                evaluation_criteria=payload["evaluation_criteria"],
                learning_evidence=payload["learning_evidence"],
                methodology=payload["methodology"],
                unit_id=payload["unit_id"],
                unit_title=payload["unit_title"],
                week_number=payload["week_number"],
                session_number=payload["session_number"],
                session_type=payload["session_type"]
            )

        return payload

    @classmethod
    def derive_material_from_session(
        cls,
        session_data: Dict[str, Any],
        material_type: str = "ficha_guia",
        instruction: Optional[str] = None,
        user: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Derives an educational material linked to a saved session and its parent unit.
        Inherits topic, grade, specialty, and purpose.
        """
        c_json = session_data.get("content_json")
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}
        elif not isinstance(c_json, dict):
            c_json = {}

        topic = session_data.get("topic") or c_json.get("topic") or session_data.get("title", "Actividad Técnica")
        grade = session_data.get("grade") or c_json.get("grade", 5)
        specialty = session_data.get("specialty") or c_json.get("specialty", "Educación para el Trabajo")
        purpose = session_data.get("purpose") or c_json.get("propositos", {}).get("proposito_formativo", "")
        session_id = session_data.get("id")
        session_title = session_data.get("title", "Sesión de Aprendizaje")
        unit_id = session_data.get("unit_id") or c_json.get("unidad_didactica_origen", {}).get("unit_id")

        type_names = {
            "ficha_trabajo": "Ficha de trabajo y práctica operativa de taller",
            "ficha_guia": "Ficha guía de estudio y procedimiento técnico",
            "ficha_actividad": "Ficha de actividad técnica",
            "examen_tecnico": "Evaluación técnica escrita y práctica de taller",
            "rubrica_evaluacion": "Rúbrica analítica de evaluación formativa",
            "practica_ejercicios": "Práctica de ejercicios y problemas técnicos"
        }
        type_desc = type_names.get(material_type, "Material educativo y ficha de aprendizaje")

        if instruction and instruction.strip():
            prompt = (
                f"Elabora {type_desc} sobre '{topic}' para {grade}° de secundaria en {specialty}. "
                f"Considera el propósito de la sesión: '{purpose}'. "
                f"Instrucción específica: {instruction.strip()}"
            )
        else:
            prompt = (
                f"Elabora {type_desc} contextualizada sobre '{topic}' para {grade}° de secundaria en {specialty}. "
                f"Debe reforzar el propósito de aprendizaje: '{purpose}'. "
                f"Incluye conceptos clave, procedimiento técnico paso a paso, medidas de seguridad 5S, actividades de aplicación y preguntas de autoevaluación."
            )

        if user:
            material_res = cls.generate_material_from_instructions(
                user=user,
                prompt=prompt,
                preferred_type=material_type,
                grade=grade,
                specialty=specialty
            )
            # Link metadata
            material_res["session_id"] = session_id
            material_res["session_title"] = session_title
            material_res["unit_id"] = unit_id
            m_cjson = material_res.get("content_json")
            if isinstance(m_cjson, dict):
                m_cjson["origen_cascada"] = {
                    "session_id": session_id,
                    "session_title": session_title,
                    "unit_id": unit_id
                }
            return material_res

        return {
            "prompt": prompt,
            "preferred_type": material_type,
            "grade": grade,
            "specialty": specialty,
            "session_id": session_id,
            "session_title": session_title,
            "unit_id": unit_id
        }

    @staticmethod
    def regenerate_session_section(
        user: Dict[str, Any],
        section: str,
        topic: str,
        grade: int,
        specialty: str,
        duration_minutes: int = 90,
        competence: Optional[str] = None,
        teacher_instruction: Optional[str] = None,
        current_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Regenerates exclusively a single phase or section without altering the rest of the session.
        """
        sec_key = (section or "desarrollo").strip().lower()
        cleaned_topic = (topic or "").strip()
        cleaned_specialty = (specialty or "Educación para el Trabajo").strip()
        cleaned_instruction = (teacher_instruction or "").strip()

        section_prompts = {
            "inicio": (
                f"Rediseña EXCLUSIVAMENTE la FASE DE INICIO (Motivación, Saberes Previos, Conflicto Cognitivo y Propósito) "
                f"para una sesión de {grade}° de secundaria en {cleaned_specialty} sobre: {cleaned_topic}.\n"
                f"Duración estimada para esta fase: {max(10, int(duration_minutes*0.15))} minutos.\n"
                f"{f'Indicación pedagógica del docente: {cleaned_instruction}' if cleaned_instruction else ''}\n"
                f"Devuelve únicamente la secuencia detallada de la fase de Inicio sin incluir otras fases."
            ),
            "desarrollo": (
                f"Rediseña EXCLUSIVAMENTE la FASE DE DESARROLLO (Demostración del docente, práctica en taller por cuadrillas, "
                f"aplicación técnica y seguridad de taller) para {grade}° de secundaria en {cleaned_specialty} sobre: {cleaned_topic}.\n"
                f"Duración estimada para esta fase: {max(20, int(duration_minutes*0.70))} minutos.\n"
                f"{f'Indicación pedagógica del docente: {cleaned_instruction}' if cleaned_instruction else ''}\n"
                f"Devuelve únicamente la secuencia detallada de la fase de Desarrollo con actividades prácticas de taller."
            ),
            "cierre": (
                f"Rediseña EXCLUSIVAMENTE la FASE DE CIERRE (Metacognición: ¿Qué aprendimos?, Evaluación formativa de la evidencia "
                f"y protocolo 5S de orden y limpieza) para {grade}° de secundaria en {cleaned_specialty} sobre: {cleaned_topic}.\n"
                f"Duración estimada para esta fase: {max(10, int(duration_minutes*0.15))} minutos.\n"
                f"{f'Indicación pedagógica del docente: {cleaned_instruction}' if cleaned_instruction else ''}\n"
                f"Devuelve únicamente la secuencia detallada de la fase de Cierre."
            ),
            "rubrica": (
                f"Elabora una NUEVA RÚBRICA ANALÍTICA DE EVALUACIÓN formativa CNEB para la sesión sobre: {cleaned_topic} "
                f"en {cleaned_specialty} ({grade}° de Secundaria).\n"
                f"Incluye 3 criterios de evaluación claros y descriptores en 4 niveles de logro: AD (Destacado), A (Esperado), B (En Proceso), C (En Inicio).\n"
                f"{f'Indicación del docente: {cleaned_instruction}' if cleaned_instruction else ''}"
            ),
            "seguridad_industrial": (
                f"Detalla las NORMAS DE SEGURIDAD INDUSTRIAL, EQUIPO DE PROTECCIÓN PERSONAL (EPP) REGLAMENTARIO "
                f"y PROTOCOLOS 5S específicos de taller para la sesión de {cleaned_specialty} sobre: {cleaned_topic}.\n"
                f"{f'Indicación del docente: {cleaned_instruction}' if cleaned_instruction else ''}"
            )
        }

        prompt = section_prompts.get(sec_key, section_prompts["desarrollo"])
        result = ai_orchestrator.execute_prompt(user, prompt, tool_type="cneb_section_regenerator", subject_id=cleaned_specialty)
        result["section"] = sec_key
        result["topic"] = cleaned_topic
        result["regenerated_content"] = result.get("content") or result.get("response") or ""
        return result


    @classmethod
    def generate_learning_activity(
        cls,
        user: Dict[str, Any],
        topic: str,
        grade: int,
        specialty: str,
        competence: Optional[str] = None,
        activity_type: str = "ficha_taller",
        duration_minutes: int = 45,
        section_name: str = "A",
        difficulty: str = "intermedio",
        materials: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera una Ficha de Actividad / Guía Práctica de Taller estructurada según CNEB/EPT.
        Soporta: Fichas de taller, guías de laboratorio, estudios de caso, proyectos integradores y ejercicios por dificultad.
        """
        cleaned_topic = (topic or "").strip()
        cleaned_specialty = (specialty or "Educación para el Trabajo").strip()
        cleaned_competence = (competence or "Aplica habilidades técnicas en proyectos productivos y emprendimiento").strip()
        cleaned_purpose = (purpose or f"Desarrollar habilidades procedimentales y cognitivas en {cleaned_topic}.").strip()
        cleaned_difficulty = (difficulty or "intermedio").strip().lower()

        activity_labels = {
            "ficha_taller": "Ficha de Práctica de Taller / Hoja de Operación",
            "guia_laboratorio": "Guía de Laboratorio y Experimentación",
            "estudio_caso": "Estudio de Caso Técnico y Resolución de Fallas",
            "proyecto_integrador": "Ficha de Proyecto Productivo Integrador",
            "ejercicios_dificultad": "Banco de Ejercicios Graduados por Nivel de Dificultad"
        }
        activity_type_label = activity_labels.get(activity_type, "Ficha de Actividad de Aprendizaje")

        # Asignación de normas de seguridad y EPP contextualizadas a la especialidad técnica
        spec_norm = cleaned_specialty.lower()
        topic_norm = cleaned_topic.lower()
        is_digital_activity = any(k in f"{topic_norm} {spec_norm}" for k in [
            "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
            "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
        ])

        if is_digital_activity:
            epp_standard = "Postura ergonómica reglamentaria (regla 90-90-90 para espalda y extremidades), descansos visuales periódicos (regla 20-20-20), verificación de conexiones eléctricas y orden del cableado en el laboratorio de cómputo."
            safety_warning = "Seguridad de la información: Cerrar sesión en plataformas de almacenamiento al finalizar, no compartir credenciales institucionales y verificar los niveles de acceso (Lector / Editor) antes de compartir enlaces."
            default_materials = materials or "Computadora con conexión a red / internet, plataforma de almacenamiento en la nube institucional (Google Workspace / OneDrive), explorador de archivos y fichas guía de gestión documental."
        elif "electr" in spec_norm:
            epp_standard = "Lentes de seguridad transparentes con protección lateral UV, calzado dieléctrico con suela aislante, guantes de maniobra dieléctricos hasta 1000V (clase 0), ropa de trabajo de algodón 100% sin accesorios metálicos."
            safety_warning = "Desenergizar completamente el circuito y verificar ausencia de tensión con multímetro CAT III antes de manipular conexiones. Aplicar bloqueo y etiquetado (LOTO)."
            default_materials = materials or "Multímetro digital calibrado, pinza amperimétrica, alicates de corte y punta con aislamiento 1000V, destornilladores aislados VDE, conductores eléctricos normalizados y llaves termomagnéticas."
        elif "mecan" in spec_norm or "torno" in spec_norm or "metal" in spec_norm:
            epp_standard = "Lentes de policarbonato de alta resistencia con protección lateral, calzado de seguridad con puntera de acero, mameluco ceñido institucional sin dobleces ni tiras sueltas, protectores auditivos de copa o inserción."
            safety_warning = "PROHIBIDO terminantemente el uso de guantes, bufandas o cabello suelto cerca del husillo o partes rotativas del torno. Verificar ajuste de platos y llave de mandril retirada antes de encender."
            default_materials = materials or "Calibrador Vernier (precisión 0.02 mm / 0.05 mm), goniómetro, micrómetro de exteriores, cuchillas HSS debidamente afiladas, probeta de material (aluminio o acero SAE 1020) y taladrina para refrigeración."
        elif "ebanist" in spec_norm or "mader" in spec_norm:
            epp_standard = "Lentes de seguridad herméticos anti-impacto, mascarilla con filtro para polvo fino de madera y aserrín (N95), calzado de seguridad, mandil o mameluco de taller, protectores auditivos para máquinas de corte."
            safety_warning = "Verificar guías y empujadores de madera antes de accionar la sierra circular o tupi. Mantener manos fuera de la línea de corte."
            default_materials = materials or "Gramil, escuadra de precisión, cepillo de carpintero, formones afilados, prensas sargento, lija para madera y madera seleccionada habilitada."
        elif "comput" in spec_norm or "inform" in spec_norm:
            epp_standard = "Pulsera antiestática con conexión a tierra (ESD), calzado con suela de goma aislante, verificación de pozo a tierra en tomas de corriente y postura ergonómica frente al monitor."
            safety_warning = "Desconectar cables de alimentación de la fuente antes de desmontar placas madre o módulos de memoria RAM. Manejar componentes por sus bordes aislantes."
            default_materials = materials or "Kit de destornilladores de precisión imantados, pulsera ESD, pasta térmica de alta conductividad, alcohol isopropílico 99%, hisopos y sopladora/aire comprimido."
        else:
            epp_standard = "Lentes de seguridad reglamentarios, calzado cerrado de seguridad, guardapolvo/mameluco institucional, cabello recogido y retiro de accesorios colgantes."
            safety_warning = "Respetar las señales de advertencia y pasillos de seguridad en el taller. Conocer la ubicación del extintor y botiquín de primeros auxilios."
            default_materials = materials or f"Herramientas manuales de taller, instrumentos de verificación e insumos necesarios para la práctica de {cleaned_topic}."

        prompt = (
            f"Diseña una {activity_type_label.upper()} oficial para estudiantes de secundaria de la I.E. INEI N° 34 de Chancay.\n"
            f"- Especialidad / Área: {cleaned_specialty}\n"
            f"- Grado y Sección: {grade}° de Secundaria - Sección {section_name}\n"
            f"- Tema Técnico: {cleaned_topic}\n"
            f"- Tipo de Actividad: {activity_type_label}\n"
            f"- Nivel de Dificultad: {cleaned_difficulty.upper()}\n"
            f"- Tiempo estimado de ejecución: {duration_minutes} minutos\n"
            f"- Competencia CNEB: {cleaned_competence}\n"
            f"- Propósito / Reto Formativo: {cleaned_purpose}\n"
            f"- Herramientas y Materiales disponibles: {default_materials}\n"
            f"- EPP reglamentario aplicable: {epp_standard}\n\n"
            f"ESTRUCTURA OBLIGATORIA DE LA FICHA:\n"
            f"1. ENCABEZADO ESCOLAR: I.E. INEI N° 34 Chancay con campos para Alumno(a), Grado/Sección, Especialidad, Fecha y Firma Docente.\n"
            f"2. MARCO CONCEPTUAL Y FUNDAMENTO TÉCNICO: Resumen claro con parámetros, fórmulas o principios operativos aplicados a {cleaned_topic}.\n"
            f"3. NORMAS DE SEGURIDAD INDUSTRIAL Y PROTOCOLO 5S: Equipos de protección personal obligatorios y advertencias críticas de taller.\n"
            f"4. PROCEDIMIENTO TÉCNICO GUIADO (Paso a Paso): Secuencia ordenada de ejecución con instrucciones claras, tolerancias y control de calidad.\n"
            f"5. RETOS Y EJERCICIOS DE APLICACIÓN ({cleaned_difficulty.upper()}): 3 a 4 actividades progresivas orientadas a la práctica real.\n"
            f"6. LISTA DE COTEJO DE AUTOEVALUACIÓN / HETEROEVALUACIÓN: Criterios verificables de logro (Sí / No / En proceso).\n"
            f"7. PREGUNTA METACOGNITIVA: Reflexión sobre la aplicación laboral y la mejora continua."
        )

        t_start = time.time()
        raw_res = ai_orchestrator.execute_prompt(user, prompt, tool_type="learning_activity_generator", subject_id=cleaned_specialty)
        raw_content = (raw_res.get("content") or "").strip()

        # Construcción semántica estructurada (content_json)
        structured_json = {
            "datos_informativos": {
                "institucion": "I.E. INEI N.º 34 de Chancay",
                "area_especialidad": cleaned_specialty,
                "grado": grade,
                "seccion": section_name,
                "duracion_minutos": duration_minutes,
                "tema": cleaned_topic,
                "tipo_actividad": activity_type,
                "tipo_actividad_label": activity_type_label,
                "dificultad": cleaned_difficulty
            },
            "propositos": {
                "competencia": cleaned_competence,
                "proposito": cleaned_purpose,
                "desempeno": f"Aplica técnicas de ejecución y verificación en {cleaned_topic} cumpliendo normas de calidad y seguridad industrial."
            },
            "materiales_herramientas": default_materials,
            "seguridad_epp_5s": f"EPP Obligatorio: {epp_standard}\n\nAdvertencia de Seguridad: {safety_warning}\n\nProtocolo 5S: Clasificar (Seiri), Ordenar (Seiton), Limpiar (Seiso), Estandarizar (Seiketsu) y Disciplina (Shitsuke).",
            "seguridad_industrial_5s": f"EPP Obligatorio: {epp_standard}\n\nAdvertencia de Seguridad: {safety_warning}\n\nProtocolo 5S: Clasificar (Seiri), Ordenar (Seiton), Limpiar (Seiso), Estandarizar (Seiketsu) y Disciplina (Shitsuke).",
            "equipos_proteccion_personal": epp_standard,
            "normas_5s": "Clasificar (Seiri), Ordenar (Seiton), Limpiar (Seiso), Estandarizar (Seiketsu) y Disciplina (Shitsuke)",
            "marco_conceptual": (
                f"Arquitectura jerárquica de archivos y carpetas, estandarización de nombres (nomenclatura AAAA-MM-DD_Asignatura_Detalle), depuración de duplicados, sincronización en la nube institucional y políticas de respaldo seguro para {cleaned_topic}."
                if is_digital_activity else
                f"Fundamentos técnicos de {cleaned_topic} orientados a la producción eficiente y segura en taller."
            ),
            "actividad_paso_a_paso": (
                f"1. Diagnóstico de la información: Exploración del espacio de almacenamiento y detección de archivos desordenados o duplicados.\n2. Diseño de la jerarquía: Creación del árbol de carpetas por año, bimestre y áreas curriculares.\n3. Normalización y depuración: Renombrado de archivos con estándar institucional y eliminación segura de duplicados.\n4. Gestión en la nube: Carga de evidencias, sincronización y configuración de permisos de acceso compartido.\n5. Verificación y respaldo: Comprobación de integridad de los enlaces y ejecución de copia de seguridad local/externa."
                if is_digital_activity else
                f"1. Habilitación de materiales y verificación dimensional previa.\n2. Calibración y puesta a punto de los equipos.\n3. Ejecución de la operación técnica siguiendo el plano.\n4. Control de calidad y medición de tolerancias.\n5. Limpieza del puesto y reporte al docente."
            ),
            "retos_aplicacion": (
                f"Reto 1 (Inicial): Diseñar en el explorador un árbol jerárquico de 3 niveles para el portafolio del estudiante en {cleaned_topic}.\nReto 2 (Intermedio): Normalizar los nombres de 10 archivos desorganizados aplicando la regla estándar y depurar copias idénticas.\nReto 3 (Avanzado): Configurar una carpeta compartida en la nube asignando permisos diferenciados (Lector para pares, Editor para docente) y verificar el respaldo seguro."
                if is_digital_activity else
                f"Reto 1 (Inicial): Reconocimiento y verificación de herramientas para {cleaned_topic}.\nReto 2 (Intermedio): Ejecución del procedimiento respetando tolerancias técnicas.\nReto 3 (Avanzado): Diagnóstico de fallas dimensionales o averías y propuesta de optimización técnica."
            ),
            "lista_cotejo_autoevaluacion": (
                [
                    {"criterio": "Creé la estructura lógica de carpetas respetando niveles y categorías temáticas.", "logrado": True},
                    {"criterio": "Apliqué la convención de nomenclatura estándar a todos los archivos y carpetas.", "logrado": True},
                    {"criterio": "Identifiqué y depuré archivos duplicados de forma segura sin pérdida de datos.", "logrado": True},
                    {"criterio": "Configuré correctamente los permisos de acceso compartido en la nube institucional.", "logrado": True},
                    {"criterio": "Apliqué hábitos de seguridad digital, postura ergonómica y cierre de sesión.", "logrado": True}
                ]
                if is_digital_activity else
                [
                    {"criterio": "Utilicé el EPP completo reglamentario durante toda la práctica.", "logrado": True},
                    {"criterio": f"Ejecuté la operación de {cleaned_topic} respetando las tolerancias técnicas.", "logrado": True},
                    {"criterio": "Mantuve mi puesto de trabajo ordenado y limpio según el protocolo 5S.", "logrado": True},
                    {"criterio": "Registré las mediciones y evidencias de forma precisa en la hoja de trabajo.", "logrado": True}
                ]
            ),
            "metacognicion": (
                f"¿De qué manera una estructura ordenada de carpetas y respaldos en la nube te ayuda a ahorrar tiempo y asegurar tus evidencias de aprendizaje en {cleaned_topic}?"
                if is_digital_activity else
                f"¿Qué dificultades operativas encontraste al trabajar con {cleaned_topic} y qué medidas tomaste para resolverlas?"
            )
        }

        title = f"{activity_type_label}: {cleaned_topic} ({grade}° Sec. - {cleaned_specialty})"

        # Si el texto de la IA es válido y completo, usarlo como Markdown; de lo contrario, generar Markdown determinista estructurado
        if raw_content and ("# " in raw_content or "## " in raw_content) and len(raw_content) > 200:
            markdown_text = raw_content
        else:
            checklist_md = "\n".join([f"- [ ] {item['criterio']}" for item in structured_json["lista_cotejo_autoevaluacion"]])
            markdown_text = (
                f"# I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY\n"
                f"## {activity_type_label.upper()}\n\n"
                f"**Tema:** {cleaned_topic}  \n"
                f"**Especialidad:** {cleaned_specialty} | **Grado y Sección:** {grade}° Secundaria - {section_name} | **Duración:** {duration_minutes} min  \n"
                f"**Dificultad:** {cleaned_difficulty.upper()} | **Competencia:** {cleaned_competence}  \n"
                f"**Estudiante:** ________________________________________ **Fecha:** ______________\n\n"
                f"---\n\n"
                f"### I. OBJETIVO / PROPÓSITO FORMATIVO\n"
                f"{cleaned_purpose}\n\n"
                f"### II. HERRAMIENTAS, MÁQUINAS Y MATERIALES\n"
                f"{default_materials}\n\n"
                f"### III. NORMAS DE SEGURIDAD INDUSTRIAL Y METODOLOGÍA 5S\n"
                f"**EPP Obligatorio:** {epp_standard}\n\n"
                f"**¡Advertencia de Seguridad!** {safety_warning}\n\n"
                f"### IV. PROCEDIMIENTO TÉCNICO GUIADO (PASO A PASO)\n"
                f"{structured_json['actividad_paso_a_paso']}\n\n"
                f"### V. RETOS Y EJERCICIOS DE APLICACIÓN ({cleaned_difficulty.upper()})\n"
                f"{structured_json['retos_aplicacion']}\n\n"
                f"### VI. LISTA DE COTEJO DE EVALUACIÓN TÉCNICA\n"
                f"{checklist_md}\n\n"
                f"### VII. PREGUNTAS METACOGNITIVAS DE CIERRE\n"
                f"{structured_json['metacognicion']}\n"
            )

        teacher_name = (
            user.get("full_name") or
            user.get("username") or
            "Prof. César Morales"
        )
        return {
            "success": True,
            "title": title,
            "doc_type": "ficha_actividad",
            "teacher_name": teacher_name,
            "activity_type": activity_type,
            "topic": cleaned_topic,
            "grade": grade,
            "specialty": cleaned_specialty,
            "section_name": section_name,
            "duration_minutes": duration_minutes,
            "difficulty": cleaned_difficulty,
            "content": markdown_text,
            "content_markdown": markdown_text,
            "content_json": structured_json,
            "status": "BORRADOR",
            "version": 1,
            "model": raw_res.get("model", "nexus_contingency_engine")
        }

    @classmethod
    def generate_technical_exam(
        cls,
        user: Dict[str, Any],
        topic: str,
        specialty: str,
        grade: int,
        num_questions: int = 5,
        include_rubric: bool = True,
        competence: Optional[str] = None,
        difficulty: str = "intermedio",
        section_name: str = "A",
        question_types: str = "mixto",
        total_points: int = 20
    ) -> Dict[str, Any]:
        """
        Genera un Examen Técnico / Instrumento de Evaluación con separación estricta:
        1. Versión Estudiante (limpia, sin respuestas, lista para imprimir/resolver).
        2. Solucionario Docente Separado (con justificaciones técnicas y criterios de corrección).
        3. Rúbrica CNEB analítica ministerial con cálculo exacto de puntajes (suman exactamente total_points).
        """
        cleaned_topic = (topic or "").strip()
        cleaned_specialty = (specialty or "Educación para el Trabajo").strip()
        cleaned_competence = (competence or "Evalúa los resultados del proyecto de emprendimiento e innovación técnica").strip()
        cleaned_difficulty = (difficulty or "intermedio").strip().lower()

        # Validación y cálculo de puntajes exactos (entre 1 y 10 preguntas)
        num_q = max(1, min(int(num_questions or 5), 10))
        total_pts = max(10, min(int(total_points or 20), 100))

        # Desglose matemático exacto de puntos por pregunta sumando rigurosamente total_pts
        base_pts = total_pts // num_q
        remainder = total_pts % num_q
        pts_list = [base_pts + (1 if i < remainder else 0) for i in range(num_q)]
        assert sum(pts_list) == total_pts

        prompt = (
            f"Diseña una Evaluación Técnica Escrita y Práctica para estudiantes de secundaria de la I.E. INEI N° 34 Chancay.\n"
            f"- Especialidad / Área: {cleaned_specialty}\n"
            f"- Grado y Sección: {grade}° de Secundaria - Sección {section_name}\n"
            f"- Tema evaluado: {cleaned_topic}\n"
            f"- Modalidad de preguntas: {question_types.upper()}\n"
            f"- Nivel de Dificultad: {cleaned_difficulty.upper()}\n"
            f"- Cantidad de preguntas: {num_q}\n"
            f"- Puntaje Total: {total_pts} puntos (Distribución por pregunta: {pts_list})\n"
            f"- Competencia CNEB: {cleaned_competence}\n\n"
            f"REGLA CRÍTICA DE SEPARACIÓN:\n"
            f"Debes estructurar dos secciones claramente delimitadas:\n"
            f"=== SECCION 1: EXAMEN ESTUDIANTE (SIN RESPUESTAS NI PISTAS) ===\n"
            f"Encabezado institucional, instrucciones y {num_q} preguntas numeradas con su puntaje asignado [{pts_list[0]} pts].\n"
            f"Bajo ninguna circunstancia incluyas la respuesta correcta en esta sección.\n\n"
            f"=== SECCION 2: SOLUCIONARIO Y CLAVE DOCENTE (EXCLUSIVO DOCENTE) ===\n"
            f"Para cada una de las {num_q} preguntas, detalla la respuesta correcta, la justificación técnica paso a paso y los criterios de asignación de puntaje parcial.\n\n"
            f"{'=== SECCION 3: RUBRICA ANALITICA CNEB ===' if include_rubric else ''}\n"
            f"Matriz con descriptores de logro en escala ministerial (AD, A, B, C) coherente con los {total_pts} puntos."
        )

        # Delegación canónica en generate_exam_or_practice_structured (CET N.° 34)
        return cls.generate_exam_or_practice_structured(
            user=user,
            topic=cleaned_topic,
            grade=grade,
            specialty=cleaned_specialty,
            difficulty=cleaned_difficulty,
            mode="examen",
            observations=f"Competence: {cleaned_competence}. Section: {section_name}. Questions: {num_q}. Points: {total_pts}",
            wants_solutions=True
        )

        t_start = time.time()

        # Construcción determinista de preguntas y solucionario garantizando 10 preguntas únicas sin repeticiones
        is_lathe_mfg = any(k in f"{cleaned_topic} {cleaned_specialty}".lower() for k in [
            "torno", "mecanizado", "cilíndrico", "cilindrico", "mecanica de produccion", "mecánica de producción"
        ])
        is_digital_exam = any(k in f"{cleaned_topic} {cleaned_specialty}".lower() for k in [
            "carpeta", "carpetas", "digital", "archivo", "archivos", "ofimática", "ofimatica",
            "computación", "computacion", "informática", "informatica", "nube", "drive", "onedrive", "almacenamiento"
        ])

        if is_lathe_mfg:
            raw_pool = [
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Cuál es la diferencia técnica fundamental entre el cilindrado de desbaste y el cilindrado de acabado en el torno paralelo?",
                    "opciones": [
                        "A) El desbaste busca remover rápidamente el mayor volumen de material con mayor profundidad y avance; el acabado busca precisión dimensional y rugosidad superficial reducida con pasadas finas.",
                        "B) El desbaste se realiza a máxima velocidad de rotación (RPM) sin refrigeración y el acabado a bajas revoluciones con avance manual rápido.",
                        "C) El desbaste solo se aplica a materiales no ferrosos y el acabado se reserva exclusivamente para aceros templados.",
                        "D) El desbaste requiere herramientas de carburo de tungsteno y el acabado obliga a utilizar limas rotativas en lugar de buril."
                    ],
                    "respuesta_correcta": "Opción A: El desbaste busca remover rápidamente el mayor volumen de material con mayor profundidad y avance; el acabado busca precisión dimensional y rugosidad superficial reducida con pasadas finas.",
                    "justificacion": "En torneado cilíndrico, la etapa de desbaste prioriza el rendimiento volumétrico de corte (alta profundidad ap y avance f), mientras que el acabado prioriza la tolerancia dimensional (IT7/IT8) y la rugosidad superficial (Ra).",
                    "criterio_evaluacion": "Diferencia con criterio técnico las operaciones de desbaste y acabado en torno cilíndrico."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Qué consecuencia técnica inmediata ocurre si la punta del buril se monta por debajo o por encima de la línea de centros del torno paralelo?",
                    "opciones": [
                        "A) Si está por encima disminuye el ángulo de incidencia provocando rozamiento excesivo; si está por debajo aumenta el ángulo de incidencia debilitando el filo y alterando el diámetro efectivo.",
                        "B) La pieza se suelda automáticamente a la torreta portaherramientas impidiendo el avance transversal.",
                        "C) El motor trifásico invierte su sentido de giro y el paso del tornillo patrón se descalibra permanentemente.",
                        "D) No produce ningún efecto mecánico perceptible siempre que la pieza esté lubricada con taladrina."
                    ],
                    "respuesta_correcta": "Opción A: Si está por encima disminuye el ángulo de incidencia provocando rozamiento excesivo; si está por debajo aumenta el ángulo de incidencia debilitando el filo y alterando el diámetro efectivo.",
                    "justificacion": "El centrado a la altura de centros garantiza los ángulos de incidencia (alpha) y desprendimiento (gamma) nominales de la cuchilla, evitando vibraciones, rozamiento del flanco o fractura del filo.",
                    "criterio_evaluacion": "Identifica la correcta alineación geométrica del filo de corte respecto al eje del husillo."
                },
                {
                    "tipo": "calculo_procedimiento",
                    "enunciado": "Cálculo técnico de mecanizado: Se requiere cilindrar un eje de acero SAE 1020 de diámetro exterior D = 50 mm con una velocidad de corte recomendada Vc = 25 m/min. Aplica la fórmula N = (1000 * Vc) / (pi * D) y determina la velocidad de rotación teórica (RPM) y la selección en el cabezal del torno.",
                    "opciones": [],
                    "respuesta_correcta": "Resolución técnica: N = (1000 * 25) / (3.1416 * 50) = 25000 / 157.08 = 159.15 RPM. Se selecciona en la caja de cambios del cabezal la velocidad normalizada más cercana disponible (aproximadamente 160 RPM).",
                    "justificacion": "La determinación matemática rigurosa de las RPM preserva la vida útil de la herramienta HSS/metal duro y evita el desgaste térmico acelerado del filo según las tablas del fabricante.",
                    "criterio_evaluacion": "Calcula con exactitud matemática la velocidad de rotación N (RPM) según parámetros de corte."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Por qué es obligatorio utilizar el apoyo del contrapunto y/o luneta cuando la longitud de la pieza que sobresale del plato excede 3 veces su diámetro (L > 3D)?",
                    "opciones": [
                        "A) Para evitar la flexión radial de la pieza por las fuerzas de corte, prevenir vibraciones mecánicas y conicidad involuntaria.",
                        "B) Para reducir el consumo de energía eléctrica del motor principal del torno en un 50%.",
                        "C) Para permitir que el husillo gire en sentido antihorario sin necesidad de embrague.",
                        "D) Para fijar la escala micrométrica del carro portaherramientas superior."
                    ],
                    "respuesta_correcta": "Opción A: Para evitar la flexión radial de la pieza por las fuerzas de corte, prevenir vibraciones mecánicas y conicidad involuntaria.",
                    "justificacion": "Las fuerzas de corte radiales (Fr) provocan deflexión elástica en piezas esbeltas voladas, generando deformación geométrica, mal acabado superficial y riesgo de expulsión de la pieza.",
                    "criterio_evaluacion": "Aplica criterios de sujeción segura y rigidez mecánica en piezas torneadas esbeltas."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": "Secuencia de refrentado: Explica el procedimiento técnico correcto para refrentar la cara frontal de un eje cilíndrico en el torno, indicando la orientación del filo y la dirección del avance transversal.",
                    "opciones": [],
                    "respuesta_correcta": "Procedimiento técnico: 1. Fijar la pieza con vuelo mínimo en el plato. 2. Centrar el buril de refrentar a la altura exacta de centros. 3. Ajustar la torreta a un ángulo de 5° a 10°. 4. Regular RPM según diámetro exterior. 5. Iniciar el avance transversal de la periferia hacia el centro exacto de la pieza para obtener una cara plana perpendicular al eje sin tetón central.",
                    "justificacion": "El refrentado genera una superficie plana de referencia axial y prepara la cara para el taladrado del punto de centrado con broca de centros.",
                    "criterio_evaluacion": "Estructura la secuencia ordenada de operaciones de refrentado frontal perpendicular al eje."
                },
                {
                    "tipo": "calculo_procedimiento",
                    "enunciado": "Metrología dimensional: Se realiza la medición del diámetro cilindrado con un Calibrador Vernier de resolución 0.02 mm (nonio de 50 divisiones). La cota nominal requerida en plano es 38.00 mm con tolerancia ISO (+0.05 mm / -0.02 mm). Si el vernier marca 38.04 mm, determina si la pieza es conforme y calcula el error respecto a la cota media.",
                    "opciones": [],
                    "respuesta_correcta": "Resolución metrológica: Límites admisibles: D_max = 38.05 mm, D_min = 37.98 mm. Medida obtenida = 38.04 mm. Conclusión: La pieza es CONFORME porque 37.98 <= 38.04 <= 38.05 mm. Cota media = 38.015 mm. Desviación = +0.025 mm respecto a la media.",
                    "justificacion": "El control metrológico directo en taller garantiza la intercambiabilidad de partes mecanizadas y el cumplimiento de las tolerancias de ajuste y ensamble.",
                    "criterio_evaluacion": "Interpreta lecturas con Calibrador Vernier y evalúa conformidad dimensional según tolerancias."
                },
                {
                    "tipo": "caso_tecnico_averia",
                    "enunciado": "Diagnóstico de fallas en torneado: Durante el cilindrado longitudinal de un eje de 200 mm entre plato y punto, se detecta que el diámetro cercano al contrapunto mide 32.40 mm mientras que el extremo cercano al plato mide 32.00 mm (conicidad involuntaria de 0.40 mm). Diagnostica la causa principal y describe el método de corrección técnica.",
                    "opciones": [],
                    "respuesta_correcta": "Diagnóstico técnico: Desalineación lateral del cabezal móvil (contrapunto desfasado del eje del husillo hacia el operador). Corrección técnica: Aflojar los tornillos de fijación del cuerpo del contrapunto y accionar los tornillos de reglaje lateral transversal contrastando con un comparador de carátula hasta alinear la línea de centros.",
                    "justificacion": "Cualquier desalineación horizontal del cabezal móvil genera un eje cónico en lugar de cilíndrico perfecto en operaciones de torneado entre puntos.",
                    "criterio_evaluacion": "Diagnostica causas de defectos geométricos (conicidad) y ejecuta el reglaje del contrapunto."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Cuál es la función técnica primordial de la taladrina (fluido de corte soluble en agua) durante el torneado de aceros al carbono?",
                    "opciones": [
                        "A) Refrigerar la zona de corte disipando calor, lubricar la interfaz viruta-herramienta para reducir fricción y arrastrar las virutas finas.",
                        "B) Pintar la superficie del acero para evitar la corrosión durante los primeros 5 minutos de trabajo.",
                        "C) Aumentar la dureza Rockwell del material mecanizado mediante choque térmico permanente.",
                        "D) Limpiar el aceite residual de las guías prismáticas de la bancada del torno."
                    ],
                    "respuesta_correcta": "Opción A: Refrigerar la zona de corte disipando calor, lubricar la interfaz viruta-herramienta para reducir fricción y arrastrar las virutas finas.",
                    "justificacion": "El fluido de corte controla la temperatura en la zona de cizallamiento primario y secundario, prolonga la vida del filo de corte y mejora la calidad superficial evitando recrecimiento de filo.",
                    "criterio_evaluacion": "Reconoce la función tribológica y térmica de los fluidos de corte en el mecanizado."
                },
                {
                    "tipo": "seguridad_industrial",
                    "enunciado": "Norma de seguridad industrial crítica: En el taller de Mecánica de Producción de la I.E. CET N.° 34, ¿por qué está TERMINANTEMENTE PROHIBIDO el uso de guantes, bufandas o mangas sueltas al operar el torno paralelo?",
                    "opciones": [
                        "A) Por el riesgo inminente de atrapamiento mecánico severo, amputación o arrastre del operador hacia las piezas o husillo rotativo de alta inercia.",
                        "B) Porque los guantes de cuero aíslan la corriente estática necesaria para la lectura del nonio micrométrico.",
                        "C) Porque la taladrina degrada las fibras textiles alterando el equilibrio dinámico del torno.",
                        "D) Porque dificulta la pulsación del pedal del freno electromecánico de emergencia."
                    ],
                    "respuesta_correcta": "Opción A: Por el riesgo inminente de atrapamiento mecánico severo, amputación o arrastre del operador hacia las piezas o husillo rotativo de alta inercia.",
                    "justificacion": "Bajo la Ley 29783 de SST y normas técnicas de máquinas-herramienta, los elementos rotativos atrapan materiales flexibles no desprendibles, provocando accidentes graves e irreversibles.",
                    "criterio_evaluacion": "Aplica con rigurosidad las normas de seguridad industrial y prevención de atrapamiento en máquinas rotativas."
                },
                {
                    "tipo": "seguridad_industrial",
                    "enunciado": "Protocolo operacional obligatorio: Inmediatamente después de ajustar o soltar una pieza en el plato autocentrante del torno con la llave de mandril, ¿cuál es la acción de seguridad obligatoria antes de pulsar el botón de encendido?",
                    "opciones": [
                        "A) Retirar de inmediato la llave del plato y colocarla en su soporte designado, nunca dejarla puesta en el mandril.",
                        "B) Girar la llave dos vueltas adicionales mientras el motor arranca a baja velocidad para verificar apriete.",
                        "C) Dejar la llave colocada en el plato como contrapeso dinámico durante la primera pasada de prueba.",
                        "D) Ajustar el avance automático transversal con la llave puesta en la cremallera del carro."
                    ],
                    "respuesta_correcta": "Opción A: Retirar de inmediato la llave del plato y colocarla en su soporte designado, nunca dejarla puesta en el mandril.",
                    "justificacion": "Dejar la llave en el plato es una de las causas más frecuentes de accidentes graves en taller: al arrancar el torno, la llave sale proyectada como proyectil balístico por la fuerza centrífuga.",
                    "criterio_evaluacion": "Cumple estrictamente el protocolo de retiro de llave de mandril garantizando la seguridad en el taller."
                }
            ]
        elif is_digital_exam:
            raw_pool = [
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Cuál es la función principal de implementar una estructura jerárquica de carpetas y subcarpetas en el almacenamiento digital?",
                    "opciones": [
                        "A) Organizar sistemáticamente la información por niveles lógicos (año, bimestre, área) facilitando la localización inmediata y evitando el desorden.",
                        "B) Aumentar automáticamente la memoria RAM del equipo de cómputo.",
                        "C) Impedir que los archivos se puedan abrir desde aplicaciones ofimáticas.",
                        "D) Convertir todos los archivos a formato de texto plano sin formato."
                    ],
                    "respuesta_correcta": "Opción A: Organizar sistemáticamente la información por niveles lógicos (año, bimestre, área) facilitando la localización inmediata y evitando el desorden.",
                    "justificacion": "La arquitectura jerárquica de directorios clasifica los datos de lo general a lo específico, optimizando tiempos de búsqueda y gestión de archivos.",
                    "criterio_evaluacion": "Comprende la estructura y niveles lógicos de las carpetas digitales."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Qué criterio describe una convención de nomenclatura estándar recomendada para nombrar archivos escolares institucionales?",
                    "opciones": [
                        "A) Incluir fecha normalizada, asignatura, contenido clave y versión (ej. 2026-10-23_EPT_CarpetasDigitales_v01) sin caracteres especiales.",
                        "B) Utilizar nombres genéricos como 'tarea1', 'documento_final' o 'nuevo_archivo'.",
                        "C) Usar nombres con más de 100 caracteres y signos especiales (?, %, $, #) en el título.",
                        "D) Nombrar todos los archivos con la misma palabra para que queden agrupados."
                    ],
                    "respuesta_correcta": "Opción A: Incluir fecha normalizada, asignatura, contenido clave y versión (ej. 2026-10-23_EPT_CarpetasDigitales_v01) sin caracteres especiales.",
                    "justificacion": "La nomenclatura estándar previene la confusión de versiones, evita errores de lectura en sistemas de archivos y agiliza la auditoría documental.",
                    "criterio_evaluacion": "Aplica convenciones de nomenclatura normalizada en archivos digitales."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": "Procedimiento de depuración: Explica los pasos técnicos para identificar y eliminar archivos duplicados en un sistema de archivos sin perder información relevante.",
                    "opciones": [],
                    "respuesta_correcta": "Procedimiento técnico: 1. Ordenar por nombre, tamaño y fecha de modificación. 2. Abrir y comparar el contenido entre archivos sospechosos. 3. Identificar la versión más completa y reciente. 4. Renombrar la versión final. 5. Mover los duplicados redundantes a la papelera y vaciar tras verificar.",
                    "justificacion": "La depuración controlada libera cuota de almacenamiento en la nube y previene el trabajo accidental sobre versiones desactualizadas.",
                    "criterio_evaluacion": "Ejecuta procedimientos seguros de depuración y control de versiones."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿Qué extensión de archivo es más apropiada para distribuir un documento final que deba conservar exactamente su formato visual e impedir modificaciones accidentales?",
                    "opciones": [
                        "A) Archivo PDF (.pdf)",
                        "B) Archivo de texto sin formato (.txt)",
                        "C) Archivo ejecutable (.exe)",
                        "D) Archivo temporal (.tmp)"
                    ],
                    "respuesta_correcta": "Opción A: Archivo PDF (.pdf)",
                    "justificacion": "El formato PDF (Portable Document Format) preserva la fidelidad gráfica, fuentes e imágenes independientemente del sistema operativo y dispositivo.",
                    "criterio_evaluacion": "Selecciona el formato y extensión de archivo apropiado según el propósito formativo."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": "Gestión de permisos en la nube: Explica la diferencia técnica entre otorgar acceso como 'Lector', 'Comentarista' y 'Editor' al compartir una carpeta en la nube institucional.",
                    "opciones": [],
                    "respuesta_correcta": "Explicación técnica: Lector: Solo puede ver y descargar archivos sin alterar el contenido. Comentarista: Puede ver y agregar notas/sugerencias sin modificar el texto original. Editor: Puede modificar, agregar, mover o eliminar archivos dentro de la carpeta.",
                    "justificacion": "El principio de menor privilegio en seguridad informática exige otorgar solo los permisos indispensables para la tarea asignada.",
                    "criterio_evaluacion": "Configura permisos de acceso diferenciados en plataformas de almacenamiento en la nube."
                },
                {
                    "tipo": "calculo_procedimiento",
                    "enunciado": "Cálculo de almacenamiento digital: Un estudiante tiene una cuota de 15 GB en la nube institucional. Si su portafolio digital contiene 120 archivos PDF de 2.5 MB cada uno y 15 videos tutoriales de 300 MB cada uno, calcula el espacio total ocupado en MB y el espacio libre restante en GB.",
                    "opciones": [],
                    "respuesta_correcta": "Cálculo técnico: PDFs = 120 * 2.5 MB = 300 MB. Videos = 15 * 300 MB = 4500 MB. Total ocupado = 300 + 4500 = 4800 MB (aprox. 4.69 GB). Espacio total = 15 GB = 15360 MB. Espacio libre = 15360 - 4800 = 10560 MB = 10.31 GB.",
                    "justificacion": "Permite cuantificar el consumo de almacenamiento y planificar políticas de depuración y compresión de archivos multimedia.",
                    "criterio_evaluacion": "Calcula y administra eficientemente capacidades y cuotas de almacenamiento digital."
                },
                {
                    "tipo": "caso_tecnico_averia",
                    "enunciado": "Diagnóstico de fallas en sincronización: Un estudiante modificó un archivo en su computadora local, pero al abrir la carpeta en la nube desde el laboratorio del colegio nota que los cambios no aparecen. Diagnostica 2 causas posibles y plantea la solución técnica.",
                    "opciones": [],
                    "respuesta_correcta": "Diagnóstico técnico: 1. Falta de conexión a internet o sincronización pausada en el equipo de origen antes de apagarlo. 2. Conflicto de cuentas de usuario o archivo guardado fuera de la carpeta sincronizada. Solución: Verificar estado del cliente de sincronización (icono en barra de tareas), comprobar cuenta activa y forzar la sincronización manual.",
                    "justificacion": "Desarrolla capacidades de resolución autónoma de incidentes tecnológicos en entornos de nube colaborativa.",
                    "criterio_evaluacion": "Diagnostica y resuelve problemas de sincronización en plataformas de almacenamiento en la nube."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": "¿En qué consiste la regla 3-2-1 de copias de seguridad recomendada para la protección de evidencias digitales?",
                    "opciones": [
                        "A) Mantener al menos 3 copias de los datos, en 2 soportes o medios diferentes, con 1 copia guardada fuera de las instalaciones (o en la nube).",
                        "B) Guardar 3 archivos en la papelera, 2 en descargas y 1 en el escritorio.",
                        "C) Compartir el archivo con 3 compañeros, revisarlo 2 veces y enviarlo en 1 minuto.",
                        "D) Guardar el archivo en 3 carpetas del mismo disco duro sin conexión a internet."
                    ],
                    "respuesta_correcta": "Opción A: Mantener al menos 3 copias de los datos, en 2 soportes o medios diferentes, con 1 copia guardada fuera de las instalaciones (o en la nube).",
                    "justificacion": "La regla 3-2-1 es el estándar internacional para prevenir pérdidas irreparables ante fallos de hardware, virus o borrados accidentales.",
                    "criterio_evaluacion": "Aplica estrategias de respaldo y seguridad digital bajo la regla 3-2-1."
                },
                {
                    "tipo": "seguridad_industrial",
                    "enunciado": "Buenas prácticas de seguridad digital: ¿Qué acción obligatoria debe realizar un estudiante al terminar su trabajo en una computadora compartida del laboratorio de cómputo?",
                    "opciones": [
                        "A) Cerrar todas las sesiones de correo y nube, borrar datos de navegación si guardó contraseñas y apagar el equipo correctamente.",
                        "B) Dejar la sesión abierta para que el siguiente estudiante pueda ver las tareas del día.",
                        "C) Desconectar bruscamente el cable de poder del tomacorriente sin cerrar el sistema.",
                        "D) Guardar la contraseña en el navegador web para no olvidarla."
                    ],
                    "respuesta_correcta": "Opción A: Cerrar todas las sesiones de correo y nube, borrar datos de navegación si guardó contraseñas y apagar el equipo correctamente.",
                    "justificacion": "Protege la privacidad personal, previene accesos no autorizados a las cuentas institucionales y preserva el equipamiento informático.",
                    "criterio_evaluacion": "Aplica protocolos de seguridad digital y protección de identidad en entornos compartidos."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": "Portafolio digital de evidencias: Describe cómo estructurarías las carpetas del portafolio digital para la especialidad técnica a lo largo del año lectivo.",
                    "opciones": [],
                    "respuesta_correcta": "Estructura técnica: Carpeta Raíz: '2026_Portafolio_Especialidad_NombreApellido' -> Subcarpetas: 'Bimestre_1', 'Bimestre_2', 'Bimestre_3', 'Bimestre_4' -> Dentro de cada bimestre: '01_Sesiones_Guias', '02_Evidencias_Practicas', '03_Evaluaciones_Rubricas', '04_Recursos_Manuales'.",
                    "justificacion": "Garantiza orden cronológico y temático facilitando la evaluación formativa continua y la presentación de evidencias.",
                    "criterio_evaluacion": "Diseña estructuras organizadas para portafolios digitales de evidencias escolares."
                }
            ]
        else:
            raw_pool = [
                {
                    "tipo": "opcion_multiple",
                    "enunciado": f"¿Cuál es el concepto técnico fundamental y objetivo principal al aplicar {cleaned_topic}?",
                    "opciones": [
                        f"A) Optimizar el procedimiento técnico, asegurar la calidad y cumplir especificaciones bajo normas de {cleaned_specialty}.",
                        "B) Realizar la operación sin planificación previa ni control de parámetros.",
                        "C) Omitir las medidas de prevención para acelerar la entrega del producto.",
                        "D) Modificar los estándares establecidos sin contrastar con el docente."
                    ],
                    "respuesta_correcta": f"Opción A: Optimizar el procedimiento técnico, asegurar la calidad y cumplir especificaciones bajo normas de {cleaned_specialty}.",
                    "justificacion": f"La aplicación técnica rigurosa de {cleaned_topic} exige planificación, control de calidad y cumplimiento de normas.",
                    "criterio_evaluacion": f"Comprende los fundamentos conceptuales y objetivos técnicos de {cleaned_topic}."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": f"¿Qué herramientas, instrumentos o recursos son indispensables para la correcta ejecución de {cleaned_topic}?",
                    "opciones": [
                        f"A) Instrumentos de medición y verificación debidamente calibrados y herramientas específicas de {cleaned_specialty}.",
                        "B) Herramientas improvisadas o en mal estado sin calibrar.",
                        "C) Estimación subjetiva del operador sin verificar parámetros.",
                        "D) Ninguno, la operación no requiere instrumental técnico."
                    ],
                    "respuesta_correcta": f"Opción A: Instrumentos de medición y verificación debidamente calibrados y herramientas específicas de {cleaned_specialty}.",
                    "justificacion": "El instrumental calibrado garantiza reproducibilidad, precisión y minimiza el margen de error técnico.",
                    "criterio_evaluacion": "Selecciona el instrumental y herramientas adecuadas para la actividad."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": f"Describe la secuencia técnica ordenada de pasos para ejecutar {cleaned_topic} garantizando eficiencia y orden:",
                    "opciones": [],
                    "respuesta_correcta": f"Secuencia técnica: 1. Inspección previa y preparación de recursos. 2. Calibración y ajuste de parámetros. 3. Ejecución controlada paso a paso. 4. Verificación y control de calidad. 5. Limpieza, orden y reporte.",
                    "justificacion": "La metodología secuencial evita retrabajos y garantiza el logro del propósito técnico.",
                    "criterio_evaluacion": "Estructura la secuencia técnica de operaciones con criterio técnico."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": f"¿Por qué es fundamental respetar las tolerancias y parámetros operativos en {cleaned_topic}?",
                    "opciones": [
                        "A) Porque garantizan la funcionalidad, seguridad y compatibilidad del producto o servicio según normas técnicas.",
                        "B) Porque aumentan innecesariamente el tiempo de trabajo.",
                        "C) Solo se aplican cuando el docente supervisa presencialmente.",
                        "D) No influyen en la calidad del resultado final."
                    ],
                    "respuesta_correcta": "Opción A: Porque garantizan la funcionalidad, seguridad y compatibilidad del producto o servicio según normas técnicas.",
                    "justificacion": "Las tolerancias aseguran la conformidad técnica y la intercambiabilidad bajo estándares de calidad.",
                    "criterio_evaluacion": "Reconoce la importancia del cumplimiento de especificaciones y tolerancias."
                },
                {
                    "tipo": "seguridad_industrial",
                    "enunciado": f"¿Cuáles son las medidas críticas de seguridad, uso de EPP y prevención de riesgos aplicables a {cleaned_topic}?",
                    "opciones": [],
                    "respuesta_correcta": f"Medidas de seguridad: Utilizar permanentemente el EPP reglamentario, verificar estado de equipos antes de operar, mantener despejada el área y aplicar el protocolo 5S.",
                    "justificacion": "La seguridad laboral y el protocolo 5S previenen accidentes y aseguran un ambiente formativo protegido.",
                    "criterio_evaluacion": "Aplica normas de seguridad industrial y prevención de riesgos en la especialidad."
                },
                {
                    "tipo": "calculo_procedimiento",
                    "enunciado": f"Desarrolla el procedimiento de control dimensional o verificación funcional para validar {cleaned_topic}:",
                    "opciones": [],
                    "respuesta_correcta": f"Procedimiento de control: Registrar la medida u observación con el instrumento correspondiente, contrastar con la especificación de referencia, determinar desviación y registrar conformidad.",
                    "justificacion": "La verificación cuantitativa y cualitativa respalda la trazabilidad y calidad técnica de la práctica.",
                    "criterio_evaluacion": "Ejecuta procedimientos de control y verificación de calidad."
                },
                {
                    "tipo": "caso_tecnico_averia",
                    "enunciado": f"Caso de aplicación: Durante la práctica de {cleaned_topic} surge una desviación o falla técnica. Plantea el diagnóstico y la solución correctiva:",
                    "opciones": [],
                    "respuesta_correcta": "Diagnóstico y solución: Detener la operación, aislar la causa raíz (parámetro descalibrado, herramienta desgastada o error en procedimiento), ajustar la variable y revalidar con prueba controlada.",
                    "justificacion": "Evalúa el pensamiento crítico y la capacidad de resolución de contingencias en el entorno técnico.",
                    "criterio_evaluacion": "Diagnostica fallas operativas y formula soluciones técnicas oportunas."
                },
                {
                    "tipo": "opcion_multiple",
                    "enunciado": f"¿Cuál de las siguientes acciones promueve la sostenibilidad y el ahorro de recursos en {cleaned_topic}?",
                    "opciones": [
                        "A) Planificar adecuadamente para evitar desperdicio de materiales, reutilizar mermas y cuidar el equipamiento.",
                        "B) Desechar sobrantes sin evaluar su reutilización.",
                        "C) Operar máquinas a sobrecarga sin respetar ciclos de trabajo.",
                        "D) Utilizar materiales sin registrar su consumo."
                    ],
                    "respuesta_correcta": "Opción A: Planificar adecuadamente para evitar desperdicio de materiales, reutilizar mermas y cuidar el equipamiento.",
                    "justificacion": "La gestión responsable de recursos es un principio fundamental en la formación técnica moderna.",
                    "criterio_evaluacion": "Aplica criterios de sostenibilidad y uso eficiente de recursos."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": f"¿Cómo contribuye el protocolo 5S (Seiri, Seiton, Seiso, Seiketsu, Shitsuke) al éxito de {cleaned_topic}?",
                    "opciones": [],
                    "respuesta_correcta": "Aporte 5S: Clasificar elimina lo innecesario; ordenar ubica cada herramienta en su sitio; limpiar previene fallas; estandarizar mantiene métodos y disciplina genera hábitos profesionales permanentes.",
                    "justificacion": "El protocolo 5S optimiza tiempos de operación, previene accidentes y mejora la productividad en el puesto de trabajo.",
                    "criterio_evaluacion": "Aplica los principios de la metodología 5S en su práctica técnica."
                },
                {
                    "tipo": "procedimiento_tecnico",
                    "enunciado": f"Propón una mejora o innovación técnica aplicable a {cleaned_topic} para elevar la calidad o productividad:",
                    "opciones": [],
                    "respuesta_correcta": f"Propuesta de mejora: Optimizar la hoja de procesos incorporando listas de verificación rápida, estandarizar tiempos de preparación y documentar lecciones aprendidas para futuros proyectos.",
                    "justificacion": "Fomenta la cultura de mejora continua (Kaizen) y la innovación en estudiantes de secundaria técnica.",
                    "criterio_evaluacion": "Formula propuestas de mejora continua e innovación en procesos técnicos."
                }
            ]

        # Seleccionar exactamente num_q preguntas distintas sin repetición
        questions_data = []
        for i in range(num_q):
            q_num = i + 1
            pts = pts_list[i]
            pool_item = raw_pool[i % len(raw_pool)]
            questions_data.append({
                "numero": q_num,
                "number": q_num,
                "puntaje": pts,
                "points": pts,
                "tipo": pool_item.get("tipo", "desarrollo"),
                "type": pool_item.get("tipo", "desarrollo"),
                "enunciado": pool_item["enunciado"],
                "statement": pool_item["enunciado"],
                "opciones": pool_item.get("opciones", []),
                "options": pool_item.get("opciones", []),
                "respuesta_correcta": pool_item["respuesta_correcta"],
                "correct_answer": pool_item["respuesta_correcta"],
                "justificacion": pool_item["justificacion"],
                "justification": pool_item["justificacion"],
                "criterio_evaluacion": f"{pool_item['criterio_evaluacion']} ({pts} pts)."
            })

        # Generación de la Versión del Estudiante (ESTRICTAMENTE LIMPIA DE RESPUESTAS)
        student_lines = [
            f"# I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY",
            f"## EVALUACIÓN TÉCNICA Y FORMATIVA — CNEB / EPT 2026",
            f"**Especialidad:** {cleaned_specialty} | **Grado y Sección:** {grade}° Secundaria - {section_name}",
            f"**Tema Evaluado:** {cleaned_topic} | **Nivel:** {cleaned_difficulty.upper()} | **Puntaje Total:** {total_pts} Puntos",
            f"**Apellidos y Nombres:** ____________________________________________________ **Fecha:** ______________",
            f"**Calificación Obtenida:** [ _____ / {total_pts} pts ]",
            f"",
            f"### INSTRUCCIONES GENERALES:",
            f"1. Lea detenidamente cada enunciado antes de responder.",
            f"2. Utilice letra clara y justifique sus respuestas en las preguntas de desarrollo.",
            f"3. Cuide el orden y limpieza de su prueba técnica. Duración máxima: 45-60 minutos.",
            f"",
            f"---",
            f"### BANCO DE PREGUNTAS ({total_pts} PUNTOS TOTALES):"
        ]

        for q in questions_data:
            student_lines.append(f"\n#### Pregunta {q['numero']} [{q['puntaje']} Puntos]")
            student_lines.append(f"{q['enunciado']}")
            if q["opciones"]:
                for opt in q["opciones"]:
                    student_lines.append(f"  {opt}")
            else:
                student_lines.append(f"\n*Espacio para desarrollo y cálculos técnicos:*")
                student_lines.append(f"__________________________________________________________________________________________")
                student_lines.append(f"__________________________________________________________________________________________")

        student_version_md = "\n".join(student_lines)

        # Generación del Solucionario Docente Separado
        teacher_lines = [
            f"# I.E. EMBLEMÁTICA INEI N.º 34 DE CHANCAY",
            f"## SOLUCIONARIO Y CLAVE DE CORRECCIÓN JUSTIFICADA (EXCLUSIVO DOCENTE)",
            f"**Evaluación:** {cleaned_topic} | **Especialidad:** {cleaned_specialty} | **Grado:** {grade}° Sec.",
            f"**Puntaje Máximo:** {total_pts} Puntos | **Distribución:** {pts_list}",
            f"",
            f"> ⚠️ **DOCUMENTO CONFIDENCIAL DOCENTE:** Esta guía de corrección contiene las respuestas justificadas y criterios de calificación parcial. No distribuir a los estudiantes.",
            f"",
            f"---"
        ]

        for q in questions_data:
            teacher_lines.append(f"\n### Ítem {q['numero']} [{q['puntaje']} Puntos] — Criterio: {q['criterio_evaluacion']}")
            teacher_lines.append(f"**Enunciado:** {q['enunciado']}")
            teacher_lines.append(f"**Respuesta Correcta:** {q['respuesta_correcta']}")
            teacher_lines.append(f"**Justificación Técnica:** {q['justificacion']}")
            teacher_lines.append(f"**Criterios de Puntaje Parcial:**")
            teacher_lines.append(f"- Procedimiento técnico correcto y resultado exacto: {q['puntaje']} pts (100%).")
            teacher_lines.append(f"- Procedimiento adecuado pero error numérico/conceptual menor: {max(1, q['puntaje'] // 2)} pts (50%).")
            teacher_lines.append(f"- Respuesta errónea o sin sustento técnico: 0 pts.")

        teacher_answer_key_md = "\n".join(teacher_lines)

        # Rúbrica CNEB Analítica
        rubric_lines = [
            f"# RÚBRICA ANALÍTICA DE EVALUACIÓN CNEB ({total_pts} PUNTOS)",
            f"**Competencia:** {cleaned_competence}",
            f"",
            f"| Criterio de Evaluación | AD: Destacado ({int(total_pts*0.9)}-{total_pts} pts) | A: Esperado ({int(total_pts*0.7)}-{int(total_pts*0.9)-1} pts) | B: En Proceso ({int(total_pts*0.55)}-{int(total_pts*0.7)-1} pts) | C: En Inicio (0-{int(total_pts*0.55)-1} pts) |",
            f"|---|---|---|---|---|",
            f"| **1. Dominio Conceptual y Teórico de {cleaned_topic}** | Explica principios con lenguaje técnico impecable y sustenta todas sus respuestas. | Responde con claridad la mayoría de conceptos técnicos requeridos. | Presenta dudas en conceptos clave o definiciones técnicas elementales. | No identifica los conceptos técnicos fundamentales de la especialidad. |",
            f"| **2. Aplicación y Procedimiento Técnico** | Resuelve problemas y cálculos con exactitud y optimización de recursos. | Desarrolla procedimientos técnicos correctos con desviaciones menores. | Requiere guía para completar la secuencia de cálculo u operación. | Incumple el procedimiento técnico y no llega al resultado. |",
            f"| **3. Seguridad Industrial y Normas 5S** | Demuestra conocimiento proactivo de riesgos, EPP y medidas preventivas. | Identifica el EPP necesario y normas básicas de seguridad de taller. | Omite recomendaciones secundarias de seguridad o protocolo 5S. | Desconoce normas elementales de seguridad y uso de EPP en taller. |"
        ]
        rubric_md = "\n".join(rubric_lines)

        combined_markdown = (
            f"{student_version_md}\n\n"
            f"================================================================================\n"
            f"<!-- CORTE DE PÁGINA / SEPARADOR DE USO EXCLUSIVO DOCENTE -->\n"
            f"================================================================================\n\n"
            f"{teacher_answer_key_md}\n\n"
            f"---\n\n"
            f"{rubric_md}"
        )

        title = f"Examen Técnico: {cleaned_topic} ({grade}° Sec. - {cleaned_specialty})"

        structured_json = {
            "student_version": student_version_md,
            "teacher_answer_key": teacher_answer_key_md,
            "rubric": rubric_md,
            "num_questions": num_q,
            "total_points": total_pts,
            "points_breakdown": pts_list,
            "difficulty": cleaned_difficulty,
            "question_types": question_types,
            "topic": cleaned_topic,
            "specialty": cleaned_specialty,
            "grade": grade,
            "section_name": section_name,
            "questions": questions_data
        }

        teacher_name = (
            user.get("full_name") or
            user.get("username") or
            "Prof. César Morales"
        )
        return {
            "success": True,
            "title": title,
            "doc_type": "examen_tecnico",
            "teacher_name": teacher_name,
            "topic": cleaned_topic,
            "specialty": cleaned_specialty,
            "grade": grade,
            "section_name": section_name,
            "num_questions": num_q,
            "total_points": total_pts,
            "points_breakdown": pts_list,
            "difficulty": cleaned_difficulty,
            "has_rubric": include_rubric,
            "content": combined_markdown,
            "content_markdown": combined_markdown,
            "student_version": student_version_md,
            "teacher_answer_key": teacher_answer_key_md,
            "rubric": rubric_md,
            "content_json": structured_json,
            "status": "BORRADOR",
            "version": 1,
            "model": raw_res.get("model", "nexus_contingency_engine")
        }

    @staticmethod
    def teacher_pedagogical_chat(
        user: Dict[str, Any],
        message: str,
        specialty: Optional[str] = "Educación para el Trabajo",
        grade: Optional[int] = None,
        subject_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Direct pedagogical dialogue assistant for teachers.
        Consultations on CNEB planning, evaluation strategies, workshop safety, curricular adaptations and technical projects.
        """
        cleaned_msg = (message or "").strip()
        cleaned_specialty = (specialty or subject_id or "Educación para el Trabajo").strip()
        context_prompt = (
            f"CONSULTA PEDAGÓGICA DEL DOCENTE ({user.get('full_name', 'Docente')} - Especialidad/Área: {cleaned_specialty}"
            f"{f', Grado: {grade}°' if grade else ''}):\n{cleaned_msg}"
        )
        return ai_orchestrator.execute_prompt(
            user=user,
            user_prompt=context_prompt,
            tool_type="teacher_pedagogical_chat",
            subject_id=cleaned_specialty,
            chat_history=chat_history
        )

    @staticmethod
    def answer_student_tutor(
        user: Dict[str, Any],
        student_question: str
    ) -> Dict[str, Any]:
        """Socratic tutor that guides the student through critical thinking without giving direct answers."""
        return ai_orchestrator.execute_prompt(user, student_question, tool_type="socratic_tutor")

    @staticmethod
    def draft_administrative_document(
        user: Dict[str, Any],
        doc_type: str,
        recipient: str,
        subject: str,
        key_points: str
    ) -> Dict[str, Any]:
        """Drafts formal institutional documents (Oficio, Memorando, Constancia, Acta)."""
        prompt = (
            f"Redacta un documento administrativo formal e institucional para la I.E. INEI N° 34 Chancay.\n"
            f"- Tipo de Documento: {doc_type}\n"
            f"- Destinatario / Cargo: {recipient}\n"
            f"- Asunto: {subject}\n"
            f"- Puntos clave / Contenido a fundamentar:\n{key_points}\n\n"
            f"Asegúrate de incluir la estructura protocolar peruana completa (Lugar y fecha, Destinatario, Asunto, Referencia si aplica, Cuerpo fundamentado en normas educativas, Despedida y pie de firma institucional)."
        )
        return ai_orchestrator.execute_prompt(user, prompt, tool_type="admin_document_drafter")

    @staticmethod
    def generate_institutional_analysis(
        user: Dict[str, Any],
        analysis_topic: str
    ) -> Dict[str, Any]:
        """Generates executive reports and KPI diagnostics for the Director."""
        prompt = (
            f"Elabora un Informe Ejecutivo y Diagnóstico Estratégico para la Dirección de la I.E. INEI 34 Chancay sobre: {analysis_topic}.\n"
            f"Incluye:\n"
            f"1. Resumen Ejecutivo y Estado Situacional.\n"
            f"2. Análisis de Factores de Impacto en Talleres Técnicos y Rendimiento Académico.\n"
            f"3. Detección de Riesgos / Alertas Tempranas.\n"
            f"4. Recomendaciones de Acción Inmediata para el Equipo Directivo y Docente."
        )
        return ai_orchestrator.execute_prompt(user, prompt, tool_type="executive_analytics")

    @staticmethod
    def generate_parent_consultation(
        user: Dict[str, Any],
        parent_query: str
    ) -> Dict[str, Any]:
        """Provides empathetic guidance to parents regarding their child's academic or attendance status."""
        return ai_orchestrator.execute_prompt(user, parent_query, tool_type="parent_advisor")

    @classmethod
    def parse_material_instructions(cls, prompt: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Interpreta automáticamente el tema, tipo de material, grado, especialidad,
        dificultad y requerimientos indicados en una solicitud en lenguaje natural.
        Detecta parámetros faltantes para ofrecer clarificación inteligente al docente.
        """
        text = (prompt or "").strip()
        text_lower = text.lower()

        # 1. Detectar si se solicitan soluciones / solucionario para el docente
        include_solutions = any(k in text_lower for k in [
            "solucion", "solución", "soluciones", "solucionario", "clave de respuesta",
            "clave de resp", "con respuestas", "para el docente", "respuestas para el profesor"
        ])

        # 2. Detectar tipo de documento
        doc_type = "ficha_guia"
        if any(k in text_lower for k in ["unidad didáctica", "unidad didactica", "unidad de aprendizaje", "programación de unidad", "programacion de unidad", "unidad cet 34", "unidad cet34"]):
            doc_type = "unidad_didactica"
        elif any(k in text_lower for k in ["solucionario", "clave de respuestas", "respuestas del examen"]):
            doc_type = "solucionario_docente"
        elif any(k in text_lower for k in ["taller", "ficha de trabajo", "actividad práctica", "actividad practica", "hoja de operaci"]):
            doc_type = "ficha_trabajo"
        elif any(k in text_lower for k in ["rúbrica", "rubrica", "matriz de evaluaci"]):
            doc_type = "rubrica_evaluacion"
        elif any(k in text_lower for k in ["examen", "evaluacion", "evaluación", "prueba", "cuestionario"]):
            doc_type = "examen_tecnico"
        elif any(k in text_lower for k in ["ejercicios", "problemas", "banco de preguntas", "práctica", "practica"]):
            doc_type = "practica_ejercicios"
        elif any(k in text_lower for k in ["presentacion", "presentación", "diapositiva", "exposicion", "exposición"]):
            doc_type = "presentacion_tema"
        elif any(k in text_lower for k in ["criterios de evaluaci"]):
            doc_type = "rubrica_evaluacion"
        elif any(k in text_lower for k in ["guía", "guia", "guía de clase", "guia de clase", "ficha guía", "ficha guia", "material de estudio", "lectura"]):
            doc_type = "ficha_guia"
        elif any(k in text_lower for k in ["sesión de aprendizaje", "sesion de aprendizaje", "plan de clase", "clase completa"]) or (
            any(k in text_lower for k in ["sesion", "sesión"]) and not any(k in text_lower for k in ["ficha", "guia", "guía", "material", "examen", "práctica", "practica"])
        ):
            doc_type = "sesion_aprendizaje"

        # 3. Detectar cantidad de preguntas / ítems
        num_questions = 10 if doc_type == "examen_tecnico" else 5
        num_match = re.search(r'\b(\d{1,2})\s+(?:preguntas?|reactivos?|ejercicios?|problemas?|items?|ítems?)\b', text_lower)
        if num_match:
            try:
                num_questions = int(num_match.group(1))
            except Exception:
                pass
        elif "diez preguntas" in text_lower:
            num_questions = 10
        elif "cinco preguntas" in text_lower:
            num_questions = 5

        # 4. Detectar grado escolar (1 a 5)
        grade_detected = False
        grade = 5
        if re.search(r'\b(?:1(?:ro|er|°)?|primer(?:o)?)\s*(?:de\s+secundaria|grado|año)?\b', text_lower):
            grade = 1
            grade_detected = True
        elif re.search(r'\b(?:2(?:do|°)?|segundo)\s*(?:de\s+secundaria|grado|año)?\b', text_lower):
            grade = 2
            grade_detected = True
        elif re.search(r'\b(?:3(?:ro|er|°)?|tercer(?:o)?)\s*(?:de\s+secundaria|grado|año)?\b', text_lower):
            grade = 3
            grade_detected = True
        elif re.search(r'\b(?:4(?:to|°)?|cuarto)\s*(?:de\s+secundaria|grado|año)?\b', text_lower):
            grade = 4
            grade_detected = True
        elif re.search(r'\b(?:5(?:to|°)?|quinto)\s*(?:de\s+secundaria|grado|año)?\b', text_lower):
            grade = 5
            grade_detected = True

        # 5. Detectar especialidad o área curricular
        specialty_detected = False
        specialty = "Educación para el Trabajo"
        if any(k in text_lower for k in [
            "excel", "computacion", "computación", "informatica", "informática",
            "programacion", "programación", "ofimatica", "ofimática", "software", "redes",
            "hoja de cálculo", "hoja de calculo", "base de datos", "digital", "ciberseguridad",
            "seguridad digital", "internet", "nube", "carpeta", "carpetas", "archivo", "archivos", "tic"
        ]):
            specialty = "Educación para el Trabajo - Computación e Informática"
            specialty_detected = True
        elif any(k in text_lower for k in ["motor", "motores", "combustion", "combustión", "mecanica", "mecánica", "torno", "fresadora", "mecanizado", "metalmec", "mantenimiento preventivo"]):
            specialty = "Educación para el Trabajo - Mecánica de Producción"
            specialty_detected = True
        elif any(k in text_lower for k in ["electricidad", "electrónica", "electronica", "circuito", "circuitos", "luminaria", "voltaje", "corriente", "instalacion", "instalación", "multímetro", "multimetro", "ley de ohm", "diferencial", "termomagnético", "termomagnetico"]):
            specialty = "Educación para el Trabajo - Electricidad y Electrónica"
            specialty_detected = True
        elif any(k in text_lower for k in ["vestido", "textil", "costura", "confeccion", "confección", "patronaje"]):
            specialty = "Educación para el Trabajo - Industria del Vestido"
            specialty_detected = True
        elif any(k in text_lower for k in ["metálica", "metalica", "carpinteria metalica", "carpintería metálica", "estructuras metálicas"]):
            specialty = "Educación para el Trabajo - Construcciones Metálicas"
            specialty_detected = True
        elif any(k in text_lower for k in ["contabilidad", "tributacion", "tributación", "balance", "financiera", "empresa", "costos"]):
            specialty = "Educación para el Trabajo - Contabilidad"
            specialty_detected = True
        elif any(k in text_lower for k in ["matemática", "matematica", "álgebra", "algebra", "geometría", "geometria", "trigonometría"]):
            specialty = "Matemática"
            specialty_detected = True
        elif any(k in text_lower for k in ["comunicación", "comunicacion", "lenguaje", "literatura", "redacción", "redaccion"]):
            specialty = "Comunicación"
            specialty_detected = True
        elif any(k in text_lower for k in ["ciencia y tecnología", "cyt", "química", "quimica", "física", "fisica", "biología", "biologia"]):
            specialty = "Ciencia y Tecnología"
            specialty_detected = True
        elif any(k in text_lower for k in ["ciencias sociales", "ccss", "historia", "geografía", "geografia", "economía", "economia"]):
            specialty = "Ciencias Sociales"
            specialty_detected = True

        # Herencia inteligente de la especialidad del docente si no se especificó en el prompt
        if not specialty_detected and user_context:
            user_spec = (user_context.get("specialty") or "").strip()
            if user_spec:
                if not user_spec.startswith("Educación para el Trabajo") and any(k in user_spec.lower() for k in ["computac", "informát", "mecanic", "electr", "vestid", "metálic", "contabil"]):
                    specialty = f"Educación para el Trabajo - {user_spec}"
                else:
                    specialty = user_spec
                specialty_detected = True

        # 6. Detectar nivel de dificultad
        difficulty = "intermedio"
        if any(k in text_lower for k in ["sencillo", "básico", "basico", "inicial", "facil", "fácil", "adaptado"]):
            difficulty = "inicial"
        elif any(k in text_lower for k in ["avanzado", "complejo", "dificil", "difícil", "reto", "profundizacion", "profundización"]):
            difficulty = "avanzado"

        # 7. Extraer tema central
        m_title = re.search(r'(?:Título|Titulo):\s*([^\n\r]+)', text, re.IGNORECASE)
        m_sobre = re.search(r'(?:sobre|acerca\s+de)\s+(?:la\s+|el\s+|los\s+|las\s+)?([^\.,\n]+?)(?:\.|\s+Incluye|\s+para\s+|\s+en\s+|$)', text, re.IGNORECASE)
        if m_title:
            clean_topic = m_title.group(1).strip(' .,:;"\'')
        elif m_sobre and len(m_sobre.group(1).strip()) >= 3:
            clean_topic = m_sobre.group(1).strip(' .,:;"\'')
        else:
            clean_topic = text
            clean_topic = re.sub(
                r'^(?:por\s+favor\s+)?(?:crea|elabora|diseña|disena|prepara|genera|haz|redacta|necesito|quiero)\s+(?:una?\s+)?(?:ficha(?:\s+guía|\s+de\s+trabajo|\s+de\s+ejercicios)?|guía(?:\s+de\s+clase)?|guia(?:\s+de\s+clase)?|examen(?:\s+técnico)?|evaluación|evaluacion|sesión(?:\s+de\s+aprendizaje)?|rúbrica|rubrica|solucionario|práctica(?:\s+de\s+ejercicios|\s+de\s+laboratorio)?|practica(?:\s+de\s+ejercicios)?|material(?:\s+de\s+estudio)?|presentación)?\s*(?:sobre|de|acerca\s+de)?\s*',
                '',
                clean_topic,
                flags=re.IGNORECASE
            )
            clean_topic = re.sub(r'\s+con\s+(?:\d{1,2}|diez|cinco)\s+preguntas.*$', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'\s+con\s+soluciones.*$', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'\s+para\s+(?:el\s+)?docente.*$', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'\s+para\s+(?:primer|segundo|tercer|cuarto|quinto|\d+[°º]?)\s*(?:de\s+secundaria|grado|año)?.*$', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'\s+en\s+(?:la\s+especialidad\s+de\s+)?(?:mecánica|mecanica|electricidad|computación|computacion|industria|construcciones|contabilidad|matemática|matematica|comunicación|comunicacion).*$', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = clean_topic.strip(' .,:;"\'')

        topic_detected = bool(clean_topic and len(clean_topic) >= 3 and clean_topic.lower() not in [
            "material", "clase", "documento", "tema", "ejercicios", "soluciones", "evaluacion", "examen"
        ])
        topic = clean_topic if topic_detected else "Tema Pedagógico Institucional"

        # 8. Detectar solicitud de recursos gráficos / imágenes
        request_images = any(k in text_lower for k in ["imagen", "imágenes", "grafico", "gráfico", "diagrama", "ilustraci", "dibujo", "figura"])

        # 9. Detectar modo de estructura (Institucional CET 34 vs Libre/Modular)
        is_inst_req = any(k in text_lower for k in ["institucional", "cet 34", "cet34", "inei 34", "oficial", "con membrete", "con firmas", "formato institucional"])
        is_free_req = any(k in text_lower for k in ["libre", "modular", "abierto", "flexible", "sin membrete", "formato libre"])
        if is_free_req:
            structure_mode = "libre"
        elif is_inst_req or doc_type in ["sesion_aprendizaje", "unidad_didactica"]:
            structure_mode = "institucional"
        else:
            structure_mode = "libre"

        # 10. Detectar tipo de sesión y duración sugerida
        if any(k in text_lower for k in ["emprendimiento", "lean canvas", "design thinking", "startup", "validación", "validacion", "modelo de negocio", "canvas"]):
            session_type = "emprendimiento"
        elif any(k in text_lower for k in ["técnica", "tecnica", "taller", "laboratorio", "gtz", "acción completa", "accion completa", "mecanizado", "maquinaria", "torno", "soldadura", "operaciones"]):
            session_type = "tecnica"
        elif "educación para el trabajo" in specialty.lower():
            session_type = "tecnica"
        else:
            session_type = "general"

        if re.search(r'\b(?:225\s*min(?:utos)?|5\s*horas?)\b', text_lower):
            detected_duration = 225
        elif re.search(r'\b(?:135\s*min(?:utos)?|3\s*horas?)\b', text_lower):
            detected_duration = 135
        elif re.search(r'\b(?:180\s*min(?:utos)?|4\s*horas?)\b', text_lower):
            detected_duration = 180
        elif re.search(r'\b(?:45\s*min(?:utos)?|1\s*hora)\b', text_lower):
            detected_duration = 45
        elif re.search(r'\b(?:90\s*min(?:utos)?|2\s*horas?)\b', text_lower):
            detected_duration = 90
        else:
            detected_duration = 225 if session_type == "tecnica" else (135 if session_type == "emprendimiento" else 90)

        # 11. Identificar campos faltantes y preguntas de clarificación
        missing_fields = []
        if not topic_detected:
            missing_fields.append("topic")
        if not grade_detected:
            missing_fields.append("grade")
        if not specialty_detected:
            missing_fields.append("specialty")

        clarification_needed = len(missing_fields) > 0
        clarification_question = None
        if clarification_needed:
            if "topic" in missing_fields and "grade" in missing_fields and "specialty" in missing_fields:
                clarification_question = "¿Sobre qué tema técnico, para qué grado (1.° a 5.° de secundaria) y en qué especialidad deseas generar el documento?"
            elif "grade" in missing_fields and "specialty" in missing_fields:
                clarification_question = f"¿Para qué grado (1.° a 5.° de secundaria) y especialidad técnica deseas enfocar el material sobre '{topic}'?"
            elif "grade" in missing_fields:
                clarification_question = f"¿Para qué grado de secundaria (1.° a 5.°) deseas preparar este material sobre '{topic}'?"
            elif "specialty" in missing_fields:
                clarification_question = f"¿A qué especialidad técnica o área curricular corresponde el material sobre '{topic}'?"
            elif "topic" in missing_fields:
                clarification_question = "¿Cuál es el tema específico o unidad de trabajo que deseas desarrollar en este material?"

        quick_fixes = {
            "grades": [1, 2, 3, 4, 5],
            "specialties": [
                "Educación para el Trabajo - Computación e Informática",
                "Educación para el Trabajo - Mecánica de Producción",
                "Educación para el Trabajo - Electricidad y Electrónica",
                "Educación para el Trabajo - Construcciones Metálicas",
                "Educación para el Trabajo - Industria del Vestido",
                "Educación para el Trabajo - Contabilidad",
                "Matemática",
                "Comunicación"
            ]
        }

        suggested_sections = cls.get_recommended_sections(
            doc_type=doc_type,
            specialty=specialty,
            include_solutions=include_solutions,
            topic=topic
        )

        # 12. Extraer secciones solicitadas explícitamente en el prompt (ej. "1. Título... 2. Propósito... 3. Explicación...")
        extracted_sections = []
        sec_matches = re.findall(r'(?:^|[\n,.;]|\b)\s*(\d+)[\.\)]\s*([A-Za-zÁÉÍÓÚáéíóúñÑ][^\n.,;]{3,65})', text)
        if sec_matches and len(sec_matches) >= 3:
            for s_num, s_title in sec_matches:
                clean_sec_title = s_title.strip()
                extracted_sections.append({"id": f"sec_{s_num}", "title": f"{s_num}. {clean_sec_title}", "editable": True})

        # 13. Detección específica de tema de Computación: Archivos y carpetas
        is_files_and_folders = any(k in text_lower for k in [
            "archivo", "carpeta", "carpetas digitales", "organización de archivos", "organizacion de archivos", "explorador"
        ])

        return {
            "doc_type": doc_type,
            "topic": topic,
            "topic_detected": topic_detected,
            "grade": grade,
            "grade_detected": grade_detected,
            "specialty": specialty,
            "specialty_detected": specialty_detected,
            "difficulty": difficulty,
            "num_questions": num_questions,
            "include_solutions": include_solutions,
            "request_images": request_images,
            "structure_mode": structure_mode,
            "session_type": session_type,
            "duration_minutes": detected_duration,
            "requested_sections": extracted_sections,
            "is_files_and_folders": is_files_and_folders,
            "missing_fields": missing_fields,
            "clarification_needed": clarification_needed,
            "clarification_question": clarification_question,
            "quick_fixes": quick_fixes,
            "suggested_sections": suggested_sections,
            "raw_prompt": text
        }

    @classmethod
    def get_recommended_sections(
        cls,
        doc_type: str,
        specialty: str = "Educación para el Trabajo",
        include_solutions: bool = False,
        topic: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Retorna el esquema de secciones recomendado según el tipo de documento pedagógico y la especialidad.
        Permite previsualizar y editar el bosquejo antes de la generación definitiva.
        """
        spec_lower = (specialty or "").lower()
        is_comp = any(k in spec_lower for k in ["computaci", "inform", "ofim"])

        sections: List[Dict[str, Any]] = []

        if doc_type in ("ficha_guia", "guia_clase"):
            sections = [
                {"id": "sec_1", "title": "I. Datos Informativos y Propósito Formativo", "description": "I.E. INEI N.º 34, Grado, Especialidad, Docente y Propósito Formativo", "editable": True},
                {"id": "sec_2", "title": "II. Marco Conceptual y Componentes Principales", "description": "Explicación clara y accesible con terminología técnica y analogías cotidianas", "editable": True},
                {"id": "sec_3", "title": "III. Sugerencias Visuales y Diagramas", "description": "Croquis, esquemas y marcadores visuales recomendados para el taller o laboratorio", "editable": True},
            ]
            if is_comp:
                sections.append({"id": "sec_4", "title": "IV. Ergonomía Digital y Protocolos del Laboratorio", "description": "Postura ergonómica, descanso visual y cuidado de equipos informáticos", "editable": True})
            else:
                sections.append({"id": "sec_4", "title": "IV. Normas de Seguridad Industrial y Protocolo 5S en Taller", "description": "Uso de EPP obligatorio y metodología 5S (Seiri, Seiton, Seiso)", "editable": True})
            sections.extend([
                {"id": "sec_5", "title": "V. Actividades Prácticas y Hoja de Operaciones", "description": "Procedimiento paso a paso para el desarrollo individual o en equipo", "editable": True},
                {"id": "sec_6", "title": "VI. Preguntas de Autoevaluación y Metacognición", "description": "Preguntas de repaso con espacio para desarrollo del estudiante", "editable": True}
            ])

        elif doc_type == "practica_ejercicios":
            sections = [
                {"id": "sec_1", "title": "I. Datos Informativos y Fórmulas Clave", "description": "Identificación institucional, parámetros de cálculo y criterios técnicos", "editable": True},
                {"id": "sec_2", "title": "II. Ejercicio Modelo Resuelto Paso a Paso", "description": "Problema resuelto demostrativo con fundamentación técnica completa", "editable": True},
                {"id": "sec_3", "title": "III. Banco de Ejercicios Graduados (Nivel 1 Básico, Nivel 2 Intermedio, Nivel 3 Reto)", "description": "Ejercicios técnicos escalonados con datos de taller o laboratorio", "editable": True},
                {"id": "sec_4", "title": "IV. Espacio de Desarrollo y Cálculos Técnicos", "description": "Tablas de registro, cuadrícula y espacio para fórmulas del estudiante", "editable": True},
            ]
            if is_comp:
                sections.append({"id": "sec_5", "title": "V. Buenas Prácticas Informáticas y Atajos de Teclado", "description": "Optimización del flujo de trabajo y productividad en hoja de cálculo o software", "editable": True})
            else:
                sections.append({"id": "sec_5", "title": "V. Cuidado de Instrumentos de Medición y Seguridad 5S", "description": "Conservación preventiva de instrumentos de precisión o tableros", "editable": True})

            if include_solutions:
                sections.append({"id": "sec_6", "title": "VI. Solucionario Docente, Justificaciones y Errores Comunes", "description": "Respuestas correctas, desarrollos matemáticos y pautas de corrección (Confidencial)", "editable": True})
            else:
                sections.append({"id": "sec_6", "title": "VI. Lista de Cotejo de Logro para el Estudiante", "description": "Criterios observables de calidad y autoevaluación", "editable": True})

        elif doc_type == "examen_tecnico":
            sections = [
                {"id": "sec_1", "title": "I. Datos Informativos e Instrucciones Generales", "description": "Membrete oficial, tiempo asignado, puntaje vigesimal (20 pts) y reglas de evaluación", "editable": True},
                {"id": "sec_2", "title": "II. Bloque Conceptual y Selección Múltiple", "description": "Preguntas conceptuales con alternativas estructuradas y clave única", "editable": True},
                {"id": "sec_3", "title": "III. Bloque de Cálculo Técnico y Procedimientos", "description": "Problemas de aplicación práctica con espacio de desarrollo", "editable": True},
                {"id": "sec_4", "title": "IV. Bloque de Seguridad Industrial, 5S y Criterio Técnico", "description": "Situaciones problemáticas de taller y medidas preventivas", "editable": True},
            ]
            if include_solutions:
                sections.append({"id": "sec_5", "title": "V. Solucionario y Rúbrica de Calificación Docente", "description": "Clave oficial ítem por ítem, justificación técnica y rúbrica vigesimal", "editable": True})

        elif doc_type == "solucionario_docente":
            sections = [
                {"id": "sec_1", "title": "I. Identificación Institucional y Aviso de Confidencialidad", "description": "Datos del instrumento evaluativo y advertencia de uso exclusivo del docente", "editable": True},
                {"id": "sec_2", "title": "II. Pautas de Ponderación y Rúbrica Vigesimal (20 pts)", "description": "Distribución de puntajes por ítem y criterios de calificación parcial", "editable": True},
                {"id": "sec_3", "title": "III. Solucionario Detallado Ítem por Ítem", "description": "Respuesta correcta y procedimiento técnico paso a paso", "editable": True},
                {"id": "sec_4", "title": "IV. Justificación Técnica y Fundamentación", "description": "Sustento normativo, fórmulas y principios de especialidad", "editable": True},
                {"id": "sec_5", "title": "V. Análisis de Errores Comunes y Retroalimentación", "description": "Dificultades típicas de los estudiantes y estrategias pedagógicas de remediación", "editable": True}
            ]

        elif doc_type == "rubrica_evaluacion":
            sections = [
                {"id": "sec_1", "title": "I. Datos Informativos y Competencias CNEB", "description": "Alineación curricular con el CNEB y especialidad EPT", "editable": True},
                {"id": "sec_2", "title": "II. Matriz Analítica con Niveles de Logro (AD, A, B, C)", "description": "Descriptores observables para cada criterio de desempeño", "editable": True},
                {"id": "sec_3", "title": "III. Ponderación Vigesimal y Pautas de Calificación", "description": "Equivalencia de niveles de logro a escala vigesimal", "editable": True},
                {"id": "sec_4", "title": "IV. Orientaciones de Retroalimentación Formativa", "description": "Pautas para el acompañamiento y retroalimentación oportuna", "editable": True}
            ]

        else: # ficha_trabajo, presentacion_tema, etc.
            sections = [
                {"id": "sec_1", "title": "I. Datos Informativos y Propósito Operativo", "description": "Identificación institucional y objetivo de la sesión práctica", "editable": True},
                {"id": "sec_2", "title": "II. Equipos, Herramientas, Materiales y EPP", "description": "Inventario de recursos necesarios para el trabajo", "editable": True},
                {"id": "sec_3", "title": "III. Normas de Seguridad Industrial y Protocolo 5S", "description": "Prevención de riesgos en el taller y orden de herramientas", "editable": True},
                {"id": "sec_4", "title": "IV. Procedimiento Técnico Guiado Paso a Paso", "description": "Secuencia operativa detallada e ilustrada", "editable": True},
                {"id": "sec_5", "title": "V. Hoja de Registro y Mediciones Técnicas", "description": "Tablas de control dimensional y tolerancias", "editable": True},
                {"id": "sec_6", "title": "VI. Lista de Cotejo de Calidad del Producto", "description": "Indicadores para verificar el producto final del estudiante", "editable": True}
            ]

        return sections

    @classmethod
    def get_teacher_preferences(cls, user_id: int) -> Dict[str, Any]:
        """
        Obtiene las preferencias de formato y diseño pedagógico del docente desde SQLite.
        Si no existen, retorna la configuración predeterminada institucional.
        """
        try:
            with get_db() as conn:
                row = conn.execute(
                    """
                    SELECT user_id, teacher_id, preferred_specialty, preferred_grade,
                           include_5s_safety, include_visual_placeholders, include_teacher_key,
                           evaluation_style, custom_sections_json, updated_at
                    FROM smartteacher_teacher_preferences
                    WHERE user_id = ?
                    """,
                    (user_id,)
                ).fetchone()

                if row:
                    custom_secs = []
                    if row["custom_sections_json"]:
                        try:
                            custom_secs = json.loads(row["custom_sections_json"])
                        except Exception:
                            custom_secs = []
                    return {
                        "user_id": row["user_id"],
                        "teacher_id": row["teacher_id"],
                        "preferred_specialty": row["preferred_specialty"] or "Educación para el Trabajo",
                        "preferred_grade": row["preferred_grade"] or 5,
                        "include_5s_safety": bool(row["include_5s_safety"]),
                        "include_visual_placeholders": bool(row["include_visual_placeholders"]),
                        "include_teacher_key": bool(row["include_teacher_key"]),
                        "evaluation_style": row["evaluation_style"] or "vigesimal",
                        "custom_sections": custom_secs,
                        "updated_at": row["updated_at"]
                    }
        except Exception:
            pass

        return {
            "user_id": user_id,
            "teacher_id": None,
            "preferred_specialty": "Educación para el Trabajo",
            "preferred_grade": 5,
            "include_5s_safety": True,
            "include_visual_placeholders": True,
            "include_teacher_key": True,
            "evaluation_style": "vigesimal",
            "custom_sections": [],
            "updated_at": None
        }

    @classmethod
    def save_teacher_preferences(cls, user_id: int, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persiste las preferencias pedagógicas del docente en smartteacher_teacher_preferences.
        """
        pref_spec = prefs.get("preferred_specialty") or "Educación para el Trabajo"
        pref_grade = int(prefs.get("preferred_grade") or 5)
        inc_5s = 1 if prefs.get("include_5s_safety", True) else 0
        inc_vis = 1 if prefs.get("include_visual_placeholders", True) else 0
        inc_key = 1 if prefs.get("include_teacher_key", True) else 0
        eval_style = str(prefs.get("evaluation_style") or "vigesimal")
        custom_secs = prefs.get("custom_sections") or []
        custom_json = json.dumps(custom_secs, ensure_ascii=False) if custom_secs else None
        teacher_id = prefs.get("teacher_id")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO smartteacher_teacher_preferences (
                    user_id, teacher_id, preferred_specialty, preferred_grade,
                    include_5s_safety, include_visual_placeholders, include_teacher_key,
                    evaluation_style, custom_sections_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    preferred_specialty = excluded.preferred_specialty,
                    preferred_grade = excluded.preferred_grade,
                    include_5s_safety = excluded.include_5s_safety,
                    include_visual_placeholders = excluded.include_visual_placeholders,
                    include_teacher_key = excluded.include_teacher_key,
                    evaluation_style = excluded.evaluation_style,
                    custom_sections_json = excluded.custom_sections_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, teacher_id, pref_spec, pref_grade, inc_5s, inc_vis, inc_key, eval_style, custom_json)
            )
            conn.commit()

        return cls.get_teacher_preferences(user_id)

    @classmethod
    def generate_exam_or_practice_structured(
        cls,
        user: Dict[str, Any],
        topic: str,
        grade: int = 1,
        specialty: str = "Matemática",
        difficulty: str = "intermedio",
        mode: str = "examen",
        observations: Optional[str] = None,
        session_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        wants_solutions: bool = True
    ) -> Dict[str, Any]:
        """
        Genera una Ficha de Examen o Ficha de Práctica estructurada bajo el esquema canónico oficial CET N.° 34.
        Garantiza fuente única de verdad para los 10 ítems (Sección A, B, C y Solucionario) tanto para DOCX como PDF.
        """
        from app.ai.document_schemas import build_examen_practica_from_dict, examen_practica_to_markdown

        user_name = user.get("full_name") or user.get("username") or "Prof. Roberto Bazán Palacios"

        cascade_context: Dict[str, Any] = {}
        if session_id:
            try:
                with get_db() as conn:
                    s_row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (session_id,)).fetchone()
                    if s_row:
                        s_dict = dict(s_row)
                        cascade_context["session_id"] = s_dict["id"]
                        cascade_context["session_title"] = s_dict.get("title", "")
            except Exception:
                pass

        raw_input = {
            "topic": topic,
            "grade": grade,
            "specialty": specialty,
            "docente": user_name,
            "modo": mode,
            "raw_prompt": observations
        }

        exam_obj = build_examen_practica_from_dict(raw_input)
        content_markdown = examen_practica_to_markdown(exam_obj, target="teacher")
        student_markdown = examen_practica_to_markdown(exam_obj, target="student")
        content_json_data = exam_obj.model_dump()
        content_json_data["cascade_context"] = cascade_context
        content_json_data["include_teacher_key"] = wants_solutions

        teacher_key_text = ""
        if wants_solutions:
            teacher_key_text = (
                f"# SOLUCIONARIO Y PAUTAS DOCENTES DE CORRECCIÓN: {topic.upper()}\n\n"
                f"**I.E. EMBLEMÁTICA INEI N.° 34 DE CHANCAY**  \n"
                f"**Documento Confidencial Exclusivo para el Docente Calificador**  \n\n"
                f"### I. SOLUCIONARIO OFICIAL (10 ÍTEMS)\n"
            )
            for s in exam_obj.solucionario:
                teacher_key_text += f"- **Ítem {s.item}:** {s.respuesta_esperada}\n"
            teacher_key_text += (
                f"\n### II. ORIENTACIONES PEDAGÓGICAS Y RETROALIMENTACIÓN\n"
                f"- {exam_obj.orientacion_docente}\n"
                f"- Se sugiere brindar retroalimentación formativa inmediata a los ítems de desarrollo de la Sección B."
            )

        doc_type_val = "examen_tecnico" if exam_obj.modo == "examen" else "practica_calificada"

        return {
            "success": True,
            "title": f"{exam_obj.titulo_documento}: {exam_obj.tema}",
            "doc_type": doc_type_val,
            "topic": exam_obj.tema,
            "grade": exam_obj.grado,
            "specialty": exam_obj.area,
            "section_name": exam_obj.seccion,
            "duration_minutes": 45 if exam_obj.modo == "practica" else 90,
            "difficulty": difficulty,
            "modo": exam_obj.modo,
            "titulo_documento": exam_obj.titulo_documento,
            "content": content_markdown,
            "content_markdown": content_markdown,
            "student_version": student_markdown,
            "teacher_answer_key": teacher_key_text,
            "content_json": content_json_data,
            "status": "BORRADOR",
            "version": 1,
            "teacher_name": exam_obj.docente
        }

    @classmethod
    def generate_student_worksheet_structured(
        cls,
        user: Dict[str, Any],
        topic: str,
        grade: int = 1,
        specialty: str = "Educación para el Trabajo - Computación e Informática",
        difficulty: str = "intermedio",
        observations: Optional[str] = None,
        custom_sections: Optional[List[Any]] = None,
        session_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        wants_solutions: bool = False
    ) -> Dict[str, Any]:
        """
        Genera una Ficha de Aprendizaje estructurada bajo el esquema canónico oficial CET N.° 34.
        Garantiza fuente única de verdad para el documento DOCX y PDF, sin scraping de Markdown.
        """
        from app.ai.document_schemas import build_ficha_from_dict, ficha_to_markdown
        
        user_name = user.get("full_name") or user.get("username") or "Docente"
        
        cascade_context: Dict[str, Any] = {}
        if session_id:
            try:
                with get_db() as conn:
                    s_row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (session_id,)).fetchone()
                    if s_row:
                        s_dict = dict(s_row)
                        cascade_context["session_id"] = s_dict["id"]
                        cascade_context["session_title"] = s_dict.get("title", "")
            except Exception:
                pass

        raw_input = {
            "topic": topic,
            "grade": grade,
            "specialty": specialty,
            "docente": user_name,
            "raw_prompt": observations
        }

        # Construir y validar esquema canónico FichaAprendizajeStructured
        ficha_obj = build_ficha_from_dict(raw_input)
        content_markdown = ficha_to_markdown(ficha_obj)
        content_json_data = ficha_obj.model_dump()
        content_json_data["cascade_context"] = cascade_context
        content_json_data["include_teacher_key"] = wants_solutions
        content_json_data["custom_sections"] = custom_sections or []

        teacher_key_text = ""
        if wants_solutions:
            teacher_key_text = (
                f"# SOLUCIONARIO Y PAUTAS DOCENTES DE CORRECCIÓN: {topic.upper()}\n\n"
                f"**I.E. EMBLEMÁTICA INEI N.° 34 DE CHANCAY**  \n"
                f"**Documento Confidencial Exclusivo para el Docente Calificador**  \n\n"
                f"### I. SOLUCIONARIO Y JUSTIFICACIONES TÉCNICAS\n"
                f"- Cada ejercicio planteado en la ficha debe verificarse conforme a la estructura jerárquica y nomenclatura requerida.\n\n"
                f"### II. ANÁLISIS DE ERRORES COMUNES Y RETROALIMENTACIÓN\n"
                f"- **Error recurrente 1:** Nombres de archivo con espacios o caracteres especiales no estándar.\n"
                f"- **Estrategia docente:** Modelar en proyector la convención institucional normalizada."
            )

        return {
            "success": True,
            "title": ficha_obj.titulo,
            "doc_type": "ficha_trabajo",
            "topic": topic,
            "grade": ficha_obj.grado,
            "specialty": ficha_obj.area,
            "section_name": ficha_obj.seccion,
            "duration_minutes": 90,
            "difficulty": difficulty,
            "content": content_markdown,
            "content_markdown": content_markdown,
            "student_version": content_markdown,
            "teacher_answer_key": teacher_key_text,
            "content_json": content_json_data,
            "status": "BORRADOR",
            "version": 1,
            "teacher_name": ficha_obj.docente
        }

    @classmethod
    def generate_material_from_instructions(
        cls,
        user: Dict[str, Any],
        prompt: str,
        preferred_type: Optional[str] = None,
        grade: Optional[int] = None,
        specialty: Optional[str] = None,
        difficulty: Optional[str] = None,
        custom_sections: Optional[List[Any]] = None,
        include_teacher_key: Optional[bool] = None,
        session_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        teacher_preferences: Optional[Dict[str, Any]] = None,
        reference_blueprint: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera un material educativo completo a partir de una instrucción en lenguaje natural.
        Detecta y personaliza automáticamente la estructura según el tipo de documento.
        Soporta esquemas de secciones personalizados, coherencia en cascada (unidad/sesión),
        y separación estricta de versión estudiante vs. solucionario docente.
        """
        parsed = cls.parse_material_instructions(prompt, user)

        doc_type = (preferred_type or parsed["doc_type"]).strip().lower()
        active_grade = grade if (grade and 1 <= grade <= 5) else parsed["grade"]
        active_specialty = (specialty or parsed["specialty"]).strip()
        active_diff = (difficulty or parsed["difficulty"]).strip().lower()
        topic = parsed["topic"]
        wants_solutions = (include_teacher_key is True) or parsed.get("include_solutions", False) or (doc_type in ["examen_tecnico", "solucionario_docente"])

        # Si el tipo solicitado es unidad didáctica, delegar en el generador de unidades
        if doc_type == "unidad_didactica":
            unit_res = cls.generate_didactic_unit_structured(
                user=user,
                topic=topic,
                grade=active_grade,
                specialty=active_specialty,
                duration_weeks=9,
                weekly_hours=8,
                total_hours=72
            )
            unit_res["metadata"] = parsed
            return unit_res

        # Si el tipo solicitado es sesión de aprendizaje CNEB, delegar en el generador de sesiones
        if doc_type == "sesion_aprendizaje":
            session_dur = parsed.get("duration_minutes") or (225 if parsed.get("session_type") == "tecnica" else (135 if parsed.get("session_type") == "emprendimiento" else 90))
            session_res = cls.generate_cneb_session_structured(
                user=user,
                topic=topic,
                grade=active_grade,
                specialty=active_specialty,
                duration_minutes=session_dur,
                difficulty=active_diff,
                session_type=parsed.get("session_type"),
                structure_mode=parsed.get("structure_mode", "institucional"),
                observations=parsed.get("raw_prompt")
            )
            session_res["metadata"] = parsed
            return session_res

        # Si es examen o práctica evaluativa, delegar en el generador estructurado oficial CET N.° 34
        if doc_type in ["examen_tecnico", "examen", "practica_calificada", "practica_ejercicios"] or any(k in (parsed.get("raw_prompt") or prompt or "").lower() for k in ["examen", "práctica", "practica"]):
            detected_mode = "practica" if doc_type in ["practica_calificada", "practica_ejercicios"] or any(k in (parsed.get("raw_prompt") or prompt or "").lower() for k in ["práctica", "practica"]) else "examen"
            exam_res = cls.generate_exam_or_practice_structured(
                user=user,
                topic=topic,
                grade=active_grade,
                specialty=active_specialty,
                difficulty=active_diff,
                mode=detected_mode,
                observations=parsed.get("raw_prompt") or prompt,
                session_id=session_id,
                unit_id=unit_id,
                wants_solutions=wants_solutions
            )
            exam_res["metadata"] = parsed
            return exam_res

        # Si el tipo solicitado es ficha de trabajo / aprendizaje, delegar en el generador estructurado oficial
        if doc_type in ["ficha_trabajo", "ficha_actividad", "ficha_guia"]:
            worksheet_res = cls.generate_student_worksheet_structured(
                user=user,
                topic=topic,
                grade=active_grade,
                specialty=active_specialty,
                difficulty=active_diff,
                observations=parsed.get("raw_prompt") or prompt,
                custom_sections=custom_sections,
                session_id=session_id,
                unit_id=unit_id,
                wants_solutions=wants_solutions
            )
            worksheet_res["metadata"] = parsed
            return worksheet_res

        # Recuperar contexto en cascada si se proporcionó session_id o unit_id
        cascade_context: Dict[str, Any] = {}
        if session_id:
            try:
                with get_db() as conn:
                    s_row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (session_id,)).fetchone()
                    if s_row:
                        s_dict = dict(s_row)
                        cascade_context["session_id"] = s_dict["id"]
                        cascade_context["session_title"] = s_dict.get("title", "")
                        try:
                            s_cj = json.loads(s_dict["content_json"]) if isinstance(s_dict["content_json"], str) else (s_dict.get("content_json") or {})
                        except Exception:
                            s_cj = {}
                        cascade_context["session_purpose"] = s_cj.get("propositos", {}).get("proposito_formativo") or s_dict.get("purpose")
                        cascade_context["session_criteria"] = s_cj.get("propositos", {}).get("criterios_evaluacion")
                        cascade_context["session_evidence"] = s_cj.get("actividad_producto")
            except Exception:
                pass

        if unit_id:
            try:
                with get_db() as conn:
                    u_row = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE id = ?", (unit_id,)).fetchone()
                    if u_row:
                        u_dict = dict(u_row)
                        cascade_context["unit_id"] = u_dict["id"]
                        cascade_context["unit_title"] = u_dict.get("title", "")
            except Exception:
                pass

        user_name = user.get("full_name") or user.get("username") or "Docente"
        img_instruction = (
            "Incluye sugerencias visuales explícitas bajo el formato `[📷 Sugerencia visual / diagrama: descripción clara del gráfico técnico que el docente puede insertar]`."
            if parsed.get("request_images") else ""
        )

        cascade_prompt_part = ""
        if cascade_context:
            cascade_prompt_part = (
                f"\nCONTEXTO DE PLANIFICACIÓN EN CASCADA:\n"
                f"- Unidad Didáctica: {cascade_context.get('unit_title', 'Unidad de Aprendizaje')}\n"
                f"- Sesión de Aprendizaje: {cascade_context.get('session_title', 'Sesión')}\n"
                f"- Propósito Formativo Vinculado: {cascade_context.get('session_purpose', '')}\n"
                f"- Criterio de Evaluación: {cascade_context.get('session_criteria', '')}\n"
                f"- Evidencia / Producto: {cascade_context.get('session_evidence', '')}\n"
                f"Asegura coherencia pedagógica directa con estos elementos formativos.\n"
            )

        if not custom_sections and reference_blueprint and reference_blueprint.get("sections"):
            custom_sections = reference_blueprint.get("sections")
        elif not custom_sections and parsed.get("requested_sections"):
            custom_sections = parsed.get("requested_sections")

        ref_prompt_part = ""
        if reference_blueprint and reference_blueprint.get("sections"):
            ref_prompt_part = (
                f"\nMODELO PEDAGÓGICO DE REFERENCIA INSTITUCIONAL ({reference_blueprint.get('filename', 'Modelo')}):\n"
                f"- Reproduce y respeta estrictamente la secuencia de apartados, títulos y tablas del documento modelo.\n"
                f"- REGLA DE NO-COPIA: Desarrolla contenido completamente NUEVO para el tema '{topic}'. NO copies datos específicos, nombres de archivos, tareas ni información de clases pasadas del documento de referencia.\n"
                f"- Docente Responsable Titular: {user_name}\n"
            )

        custom_sections_prompt_part = ""
        if custom_sections and len(custom_sections) > 0:
            formatted_sec_list = []
            for s in custom_sections:
                if isinstance(s, dict):
                    t = s.get("title") or s.get("name") or str(s)
                    d = s.get("description", "")
                    formatted_sec_list.append(f"- {t}: {d}" if d else f"- {t}")
                else:
                    formatted_sec_list.append(f"- {str(s)}")
            custom_sections_prompt_part = (
                ref_prompt_part
                + f"\nESTRUCTURA DE SECCIONES DEL DOCUMENTO:\n"
                + "\n".join(formatted_sec_list)
                + "\nDesarrolla exhaustivamente cada una de las secciones indicadas sin omitir ninguna.\n"
            )

        type_prompts = {
            "ficha_guia": (
                f"Genera una FICHA GUÍA Y MATERIAL DE ESTUDIO estructurado para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema: {topic}\n"
                f"- Nivel de Dificultad: {active_diff.capitalize()}\n"
                f"- Docente Titular: {user_name}\n"
                f"- Indicación del docente: {prompt}\n"
                f"{cascade_prompt_part}"
                f"{custom_sections_prompt_part if custom_sections_prompt_part else '''ESTRUCTURA OBLIGATORIA:
1. DATOS INFORMATIVOS (I.E. INEI N.º 34, Grado, Especialidad, Tema, Año 2026).
2. INTRODUCCIÓN Y PROPÓSITO: Explicación motivadora de la utilidad del tema.
3. MARCO CONCEPTUAL: Desglose claro de los conceptos o partes con lenguaje sencillo y analogías cotidianas.
4. SUGERENCIAS VISUALES: ''' + img_instruction + '''
5. NORMAS DE SEGURIDAD INDUSTRIAL Y PROTOCOLO 5S (o ergonomía si es informática).
6. ACTIVIDADES PRÁCTICAS DE COMPRENSIÓN (individual o grupal).
7. PREGUNTAS DE REPASO Y AUTOEVALUACIÓN (con espacio de desarrollo).
8. NOTA PEDAGÓGICA: Propuesta pedagógica editable generada con asistencia de SmartTeacher AI.'''}"
            ),
            "presentacion_pptx": (
                f"Diseña una PRESENTACIÓN OFICIAL DE 7 DIAPOSITIVAS de alto rigor pedagógico para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema Oficial: {topic}\n"
                f"- Docente Titular: {user_name}\n"
                f"- Indicación docente: {prompt}\n"
                f"{cascade_prompt_part}\n"
                f"REGLAS METODOLÓGICAS Y DE CALIDAD (OBLIGATORIAS):\n"
                f"1. PERTINENCIA TOTAL AL ÁREA: El contenido debe ser 100% fiel al área de '{active_specialty}' y al tema '{topic}'.\n"
                f"2. DESARROLLO COMPLETO Y DETALLADO: Prohibido entregar esquemas vacíos, palabras sueltas o frases telegráficas. Cada concepto, paso y herramienta debe tener su explicación clara, concreta y aplicable.\n"
                f"3. ESTRUCTURA EXACTA DE LAS 7 DIAPOSITIVAS:\n"
                f"• DIAPOSITIVA 1: Portada Institucional\n"
                f"  - Título oficial: {topic}\n"
                f"  - Subtítulo motivador y técnico\n"
                f"  - Grado: {active_grade}° de Secundaria | Área: {active_specialty} | Docente: {user_name}\n"
                f"• DIAPOSITIVA 2: Propósito de la Sesión y Situación de Reto\n"
                f"  - Propósito: (Propósito de aprendizaje articulado a la competencia del CNEB de esta materia)\n"
                f"  - Situación de Reto: (Desafío contextualizado de la vida escolar o cotidiana de los estudiantes)\n"
                f"  - Pregunta detonante: (Interrogante retadora para el debate en clase)\n"
                f"• DIAPOSITIVA 3: Fundamentos y 7 Conceptos/Pasos Clave de '{topic}'\n"
                f"  - Título del marco conceptual\n"
                f"  - 7 conceptos, etapas o pautas esenciales (cada uno con su nombre y una explicación clara de 1 o 2 líneas):\n"
                f"    1. [Nombre 1]: [Explicación detallada]\n"
                f"    2. [Nombre 2]: [Explicación detallada]\n"
                f"    3. [Nombre 3]: [Explicación detallada]\n"
                f"    4. [Nombre 4]: [Explicación detallada]\n"
                f"    5. [Nombre 5]: [Explicación detallada]\n"
                f"    6. [Nombre 6]: [Explicación detallada]\n"
                f"    7. [Nombre 7]: [Explicación detallada]\n"
                f"• DIAPOSITIVA 4: Caso Práctico Modelado Paso a Paso\n"
                f"  - Título del caso práctico modelado\n"
                f"  - Paso 1: [Nombre conciso del paso 1]: [Explicación detallada y técnica del procedimiento]\n"
                f"  - Paso 2: [Nombre conciso del paso 2]: [Explicación detallada y técnica del procedimiento]\n"
                f"  - Paso 3: [Nombre conciso del paso 3]: [Explicación detallada y técnica del procedimiento]\n"
                f"  - Resultado: [Logro medible, impacto formativo o evidencia concreta de éxito obtenida]\n"
                f"  - Pregunta para el equipo: [Pregunta de análisis crítico para consolidar el caso]\n"
                f"• DIAPOSITIVA 5: Herramientas, Métodos y Buenas Prácticas\n"
                f"  - 4 pautas, herramientas o técnicas clave del área de '{active_specialty}' con sus respectivos Tips prácticos de aplicación:\n"
                f"    1. [Nombre de Herramienta o Técnica 1]: [Descripción clara de su función y utilidad]\n"
                f"    Tip: [Consejo técnico o recomendación experta de aplicación real]\n"
                f"    2. [Nombre de Herramienta o Técnica 2]: [Descripción clara de su función y utilidad]\n"
                f"    Tip: [Consejo técnico o recomendación experta de aplicación real]\n"
                f"    3. [Nombre de Herramienta o Técnica 3]: [Descripción clara de su función y utilidad]\n"
                f"    Tip: [Consejo técnico o recomendación experta de aplicación real]\n"
                f"    4. [Nombre de Herramienta o Técnica 4]: [Descripción clara de su función y utilidad]\n"
                f"    Tip: [Consejo técnico o recomendación experta de aplicación real]\n"
                f"• DIAPOSITIVA 6: ¡Hora de la Acción! Reto Práctico\n"
                f"  - Título del reto en el aula/taller/laboratorio\n"
                f"  - Instrucciones paso a paso para los estudiantes (4 acciones concretas y ejecutables)\n"
                f"  - Tiempo límite estimado: [Ej: 25 a 30 minutos]\n"
                f"  - Lema motivador (frase inspiradora vinculada al aprendizaje del tema)\n"
                f"• DIAPOSITIVA 7: Reflexionamos y Metacognición\n"
                f"  - Criterios de autoevaluación formativa (3 criterios claros)\n"
                f"  - 3 preguntas metacognitivas clave directamente contextualizadas a '{topic}' (que fomenten el pensamiento crítico, la transferencia práctica y la autorregulación)\n"
            ),
            "presentacion_tema": (
                f"Diseña una GUÍA DE PRESENTACIÓN Y DESARROLLO TEMÁTICO para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema: {topic}\n"
                f"- Indicación docente: {prompt}\n"
                f"{cascade_prompt_part}"
                f"{custom_sections_prompt_part if custom_sections_prompt_part else '''ESTRUCTURA:
1. Portada y Propósitos de la Presentación.
2. Guion Secuencial por Diapositivas / Bloques Temáticos.
3. Ideas Clave y Síntesis Visual (bullet points concretos).
4. Preguntas Detonantes para la Participación en Clase.
5. Sugerencias de Demostración Práctica y Recursos Visuales.
6. Cierre Formativo y Comprobación de Aprendizajes.'''}"
            ),
            "ficha_trabajo": (
                f"Elabora una FICHA DE TRABAJO Y GUÍA OPERATIVA para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema: {topic}\n"
                f"- Dificultad: {active_diff}\n"
                f"- Indicación docente: {prompt}\n"
                f"{cascade_prompt_part}"
                f"REGLAS PEDAGÓGICAS ESTRICTAS PARA LA FICHA:\n"
                f"- Identificación del Estudiante: Solicitar ÚNICAMENTE Apellidos y Nombres, Grado/Sección y Fecha. Queda estrictamente prohibido pedir fecha de nacimiento, DNI, teléfono o correo electrónico.\n"
                f"- Procedimiento Técnico: Explicar de forma clara cómo crear y guardar archivos en el sistema operativo cuando sea requerido.\n"
                f"- Ejercicios en Laboratorio: Plantear ejercicios directamente realizables en la computadora del laboratorio escolar. Cada ejercicio debe ser diferente, progresivo y no repetido.\n"
                f"- Alcance Realista: NO exigir crear videos, audios ni manipular software de diseño gráfico si no forman parte del objetivo central.\n"
                f"- Estructura del Documento: Respetar rigurosamente las secciones solicitadas por el docente.\n"
                f"{custom_sections_prompt_part if custom_sections_prompt_part else '''ESTRUCTURA OBLIGATORIA:
1. Título y Datos del Estudiante (Apellidos y Nombres, Grado y Sección, Fecha).
2. Propósito de Aprendizaje.
3. Explicación Sencilla del Tema (conceptos claros con analogías cotidianas).
4. Procedimiento Técnico Paso a Paso (cómo crear carpetas, crear y guardar archivos).
5. Cinco Ejercicios Prácticos de Laboratorio (graduados, realizables y sin repeticiones).
6. Actividad Final y Criterios de Evaluación (Rúbrica / Lista de Cotejo de Logro).'''}"
            ),
            "practica_ejercicios": (
                f"Elabora una PRÁCTICA DE EJERCICIOS Y PROBLEMAS TÉCNICOS para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema: {topic}\n"
                f"- Dificultad: {active_diff}\n"
                f"- Indicación docente: {prompt}\n"
                f"{cascade_prompt_part}"
                f"{custom_sections_prompt_part if custom_sections_prompt_part else '''ESTRUCTURA:
1. Fórmulas, Parámetros y Criterios Técnicos Fundamentales.
2. Ejercicio Modelo Resuelto Paso a Paso con Justificación.
3. Banco de Ejercicios Graduados (Nivel 1 Básico, Nivel 2 Intermedio, Nivel 3 Reto Técnico).
4. Espacio de Desarrollo y Cálculos Técnicos.
5. Normas de Seguridad y Buenas Prácticas Técnicas.
''' + ('6. Solucionario Docente Confidencial con respuestas justificadas paso a paso.' if wants_solutions else '6. Lista de Cotejo de Autoevaluación.')}"
            ),
            "rubrica_evaluacion": (
                f"Genera una RÚBRICA ANALÍTICA DE EVALUACIÓN CNEB para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema: {topic}\n"
                f"- Indicación docente: {prompt}\n"
                f"{cascade_prompt_part}"
                f"{custom_sections_prompt_part if custom_sections_prompt_part else '''ESTRUCTURA:
1. Datos Informativos, Competencia y Capacidades CNEB.
2. Matriz con Criterios de Evaluación y 4 Niveles de Logro (AD, A, B, C).
3. Descriptores de Desempeño Observables en Taller / Aula.
4. Ponderación Vigesimal y Pautas de Calificación.'''}"
            ),
            "solucionario_docente": (
                f"Elabora un SOLUCIONARIO Y PAUTAS PEDAGÓGICAS DOCENTES para {active_grade}° de secundaria en {active_specialty}.\n"
                f"- Tema: {topic}\n"
                f"- Indicación docente: {prompt}\n"
                f"{cascade_prompt_part}"
                f"{custom_sections_prompt_part if custom_sections_prompt_part else '''ESTRUCTURA:
1. Identificación y Aviso de Confidencialidad Docente.
2. Respuestas Correctas Ítem por Ítem con Justificación Técnica Rigurosa.
3. Análisis de Errores Comunes de los Estudiantes y Estrategias de Retroalimentación.
4. Criterios de Calificación Parcial y Ponderación Vigesimal.'''}"
            )
        }

        exec_prompt = type_prompts.get(doc_type, type_prompts["ficha_guia"])
        raw_res = ai_orchestrator.execute_prompt(user, exec_prompt, tool_type="cneb_material_generator", subject_id=active_specialty)
        content_markdown = raw_res.get("content") or raw_res.get("response") or ""

        # Sanitización determinista de privacidad y pertinencia en fichas de trabajo
        if doc_type in ["ficha_trabajo", "ficha_guia", "ficha_actividad", "practica_ejercicios"]:
            # Eliminar cualquier solicitud indebida de fecha de nacimiento o correo
            content_markdown = re.sub(r'(?i)[-*•]?\s*(?:fecha\s+de\s+nacimiento|f\.\s*nacimiento|correo\s+electr[oó]nico|email|e-mail)\s*:[^\r\n]*', '', content_markdown)
            content_markdown = re.sub(r'\n{3,}', '\n\n', content_markdown)

        # Manejo de Versión Estudiante vs. Solucionario Docente
        student_version_text = ""
        teacher_key_text = ""
        if wants_solutions or "solucionario" in content_markdown.lower() or "parte b:" in content_markdown.lower():
            if "## PARTE B:" in content_markdown or "PARTE B: CLAVE" in content_markdown or "PARTE B: SOLUCIONARIO" in content_markdown:
                split_token = "## PARTE B:" if "## PARTE B:" in content_markdown else ("PARTE B: CLAVE" if "PARTE B: CLAVE" in content_markdown else "PARTE B: SOLUCIONARIO")
                parts = content_markdown.split(split_token, 1)
                student_version_text = parts[0].strip()
                teacher_key_text = f"## {split_token.lstrip('#').strip()}\n\n" + parts[1].strip()
            else:
                student_version_text = content_markdown
                teacher_key_text = (
                    f"# SOLUCIONARIO Y PAUTAS DOCENTES DE CORRECCIÓN: {topic.upper()}\n\n"
                    f"**I.E. EMBLEMÁTICA INEI N.° 34 DE CHANCAY**  \n"
                    f"**Documento Confidencial Exclusivo para el Docente Calificador**  \n\n"
                    f"### I. SOLUCIONARIO Y JUSTIFICACIONES TÉCNICAS\n"
                    f"- Cada ejercicio o pregunta planteada en la ficha debe evaluarse según la exactitud del cálculo y el procedimiento técnico seguido.\n"
                    f"- Para respuestas de desarrollo, ponderar el uso correcto de simbología y aplicación de normas de seguridad de taller.\n\n"
                    f"### II. ANÁLISIS DE ERRORES COMUNES Y RETROALIMENTACIÓN\n"
                    f"- **Error recurrente 1:** Omisión de unidades de medida en el resultado final.\n"
                    f"- **Error recurrente 2:** Confusión en la aplicación de tolerancias o cotas nominales.\n"
                    f"- **Estrategia docente:** Realizar una demostración práctica con un instrumento real al inicio de la sesión."
                )

        type_titles = {
            "ficha_guia": f"Ficha Guía: {topic.title()}",
            "presentacion_tema": f"Presentación: {topic.title()}",
            "ficha_trabajo": f"Ficha de Trabajo: {topic.title()}",
            "practica_ejercicios": f"Práctica de Ejercicios: {topic.title()}",
            "rubrica_evaluacion": f"Rúbrica CNEB: {topic.title()}",
            "solucionario_docente": f"Solucionario Docente: {topic.title()}"
        }
        title = type_titles.get(doc_type, f"Material Pedagógico: {topic.title()}")

        content_json_data = {
            "topic": topic,
            "grade": active_grade,
            "specialty": active_specialty,
            "doc_type": doc_type,
            "difficulty": active_diff,
            "prompt": prompt,
            "raw_markdown": content_markdown,
            "student_version": student_version_text,
            "teacher_answer_key": teacher_key_text,
            "custom_sections": custom_sections or [],
            "cascade_context": cascade_context,
            "include_teacher_key": wants_solutions
        }

        return {
            "success": True,
            "title": title,
            "doc_type": doc_type,
            "topic": topic,
            "grade": active_grade,
            "specialty": active_specialty,
            "section_name": "A",
            "duration_minutes": 90,
            "difficulty": active_diff,
            "content": content_markdown,
            "content_markdown": content_markdown,
            "student_version": student_version_text,
            "teacher_answer_key": teacher_key_text,
            "content_json": content_json_data,
            "status": "BORRADOR",
            "version": 1,
            "metadata": parsed,
            "teacher_name": user.get("full_name") or user.get("username") or "Docente"
        }

    @classmethod
    def refine_material(
        cls,
        user: Dict[str, Any],
        instruction: str,
        current_content_markdown: str,
        doc_type: Optional[str] = "ficha_guia",
        topic: Optional[str] = None,
        grade: Optional[int] = 5,
        specialty: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aplica solicitudes de cambio del docente (ej. 'hazlo más sencillo', 'añade tres ejercicios',
        'amplía los ejemplos') sobre el documento pedagógico existente preservando su formato.
        """
        cleaned_inst = (instruction or "").strip()
        cleaned_spec = (specialty or "Educación para el Trabajo").strip()
        cleaned_topic = (topic or "Tema Pedagógico").strip()

        refine_prompt = (
            f"Actúa como SmartTeacher AI, copiloto pedagógico de la I.E. INEI N.º 34 de Chancay.\n"
            f"El docente solicita realizar el siguiente cambio o ajuste sobre su material educativo:\n"
            f"INSTRUCCIÓN DEL DOCENTE: \"{cleaned_inst}\"\n\n"
            f"INFORMACIÓN DEL DOCUMENTO:\n"
            f"- Tipo: {doc_type} | Grado: {grade}° Secundaria | Área: {cleaned_spec} | Tema: {cleaned_topic}\n\n"
            f"DOCUMENTO ACTUAL:\n"
            f"```markdown\n{current_content_markdown}\n```\n\n"
            f"Aplica los cambios requeridos por el docente. Conserva el formato Markdown, mantén las secciones que no requieran cambios y devuelve el documento completo revisado."
        )

        raw_res = ai_orchestrator.execute_prompt(user, refine_prompt, tool_type="cneb_material_refiner", subject_id=cleaned_spec)
        updated_content = raw_res.get("content") or raw_res.get("response") or ""

        if not updated_content or len(updated_content) < 50:
            updated_content = (
                f"{current_content_markdown}\n\n"
                f"### ✏️ AJUSTE PEDAGÓGICO SOLICITADO ({cleaned_inst.upper()})\n"
                f"- Contenido actualizado según la indicación del docente titular para contextualización de taller."
            )

        return {
            "success": True,
            "instruction": cleaned_inst,
            "content": updated_content,
            "content_markdown": updated_content,
            "status": "BORRADOR_REFINADO"
        }

    @classmethod
    def regenerate_material_section(
        cls,
        user: Dict[str, Any],
        section_title: str,
        current_section_content: str,
        instruction: str,
        doc_type: str,
        topic: str,
        grade: int,
        specialty: str
    ) -> Dict[str, Any]:
        """
        Regenera exclusivamente una sección seleccionada del material educativo.
        """
        cleaned_title = (section_title or "Sección").strip()
        cleaned_inst = (instruction or "").strip()
        cleaned_spec = (specialty or "Educación para el Trabajo").strip()

        regen_prompt = (
            f"Regenera EXCLUSIVAMENTE la sección '{cleaned_title}' para un material de tipo {doc_type} "
            f"en {cleaned_spec} ({grade}° de Secundaria) sobre el tema '{topic}'.\n"
            f"{f'Indicación específica del docente: {cleaned_inst}' if cleaned_inst else ''}\n"
            f"Contenido actual de la sección:\n{current_section_content}\n\n"
            f"Devuelve únicamente la versión mejorada de esta sección en formato Markdown sin incluir el resto del documento."
        )

        raw_res = ai_orchestrator.execute_prompt(user, regen_prompt, tool_type="cneb_section_regenerator", subject_id=cleaned_spec)
        regen_text = raw_res.get("content") or raw_res.get("response") or ""

        return {
            "success": True,
            "section_title": cleaned_title,
            "regenerated_content": regen_text,
            "content": regen_text
        }


    # -------------------------------------------------------------
    # FASE 8.6: BIBLIOTECA Y MOTOR DE PLANTILLAS REALES (SMARTTEACHER)
    # -------------------------------------------------------------
    OFFICIAL_CET34_TEMPLATES = [
        {
            "id": 1001,
            "name": "Sesión Técnica de Taller (GTZ - 5h) — CET N° 34",
            "doc_type": "sesion_aprendizaje",
            "description": "Plantilla institucional para sesiones técnicas de taller con metodología de la Acción Completa (6 etapas GTZ). Incluye membrete oficial, tabla de metadatos y 3 firmas institucionales.",
            "filename": "sesion_tecnica_gtz_cet34.docx",
            "is_institutional": 1
        },
        {
            "id": 1002,
            "name": "Sesión de Emprendimiento (Lean Canvas - 3h) — CET N° 34",
            "doc_type": "sesion_aprendizaje",
            "description": "Plantilla institucional para proyectos de emprendimiento escolar con metodología Design Thinking y validación de hipótesis en Lean Canvas (6 etapas).",
            "filename": "sesion_emprendimiento_leancanvas_cet34.docx",
            "is_institutional": 1
        },
        {
            "id": 1003,
            "name": "Unidad Didáctica Oficial — CET N° 34",
            "doc_type": "unidad_didactica",
            "description": "Estructura institucional oficial para programación de unidades didácticas con matrices de habilidades técnicas y emprendimiento, propósitos y secuencia de sesiones.",
            "filename": "unidad_didactica_cet34.docx",
            "is_institutional": 1
        },
        {
            "id": 1004,
            "name": "Ficha de Trabajo del Estudiante — CET N° 34",
            "doc_type": "ficha_trabajo",
            "description": "Ficha institucional de aprendizaje para el estudiante con membrete oficial del C.E.T. N° 34, propósito, reto motivador, marco teórico breve, actividades prácticas guiadas con líneas y lista de cotejo.",
            "filename": "ficha_trabajo_estudiante_cet34.docx",
            "is_institutional": 1
        },
        {
            "id": 1005,
            "name": "Examen o Práctica Calificada — CET N° 34",
            "doc_type": "examen_tecnico",
            "description": "Examen institucional con membrete oficial del C.E.T. N° 34, Sección A (alternativas múltiples con casillas ☐), Sección B (desarrollo y análisis con líneas) y Sección C (Verdadero/Falso). Incluye versión estudiante y solucionario docente justificado.",
            "filename": "examen_practica_cet34.docx",
            "is_institutional": 1
        },
        {
            "id": 1006,
            "name": "Presentación PowerPoint Oficial (7 Diapositivas) — CET N° 34",
            "doc_type": "presentacion_pptx",
            "description": "Presentación institucional de 7 diapositivas con membrete CET N° 34, portada temática, propósito y reto, diagrama conceptual de 9 bloques, caso práctico, herramientas de validación, reto dinámico y metacognición.",
            "filename": "presentacion_leancanvas_cet34.pptx",
            "is_institutional": 1
        }
    ]

    @classmethod
    def get_available_templates(cls, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Lista todas las plantillas disponibles: institucionales oficiales (CET N° 34)
        y plantillas personalizadas subidas por el docente autenticado.
        Garantiza que las 6 plantillas oficiales estén siempre presentes.
        """
        from app.ai.template_engine import template_engine, TEMPLATES_STORAGE_DIR

        user_id = user.get("id") or user.get("user_id")
        results = []
        try:
            with get_db() as conn:
                rows = conn.execute("""
                    SELECT id, user_id, name, doc_type, description, filename,
                           file_path, blueprint_json, fields_json, styles_json,
                           is_institutional, created_at, updated_at
                    FROM smartteacher_templates
                    WHERE is_institutional = 1 OR user_id = ?
                    ORDER BY is_institutional DESC, id ASC
                """, (user_id,)).fetchall()

                for r in rows:
                    r_dict = dict(r)
                    for j_field in ["blueprint_json", "fields_json", "styles_json"]:
                        if r_dict.get(j_field) and isinstance(r_dict[j_field], str):
                            try:
                                r_dict[j_field] = json.loads(r_dict[j_field])
                            except Exception:
                                pass
                    results.append(r_dict)
        except Exception as e:
            logger.warning(f"Error fetching smartteacher_templates from DB: {e}")

        # Asegurar que las 6 plantillas institucionales oficiales estén en la lista
        existing_filenames = {r.get("filename") for r in results}
        for off_tpl in cls.OFFICIAL_CET34_TEMPLATES:
            if off_tpl["filename"] not in existing_filenames:
                f_path = os.path.join(TEMPLATES_STORAGE_DIR, off_tpl["filename"])
                tpl_entry = dict(off_tpl)
                tpl_entry["file_path"] = f_path if os.path.exists(f_path) else None
                tpl_entry["user_id"] = None
                tpl_entry["created_at"] = "2026-10-21 00:00:00"
                tpl_entry["updated_at"] = "2026-10-21 00:00:00"
                if os.path.exists(f_path):
                    try:
                        with open(f_path, "rb") as fp:
                            f_bytes = fp.read()
                        analysis = template_engine.analyze_template(f_bytes, off_tpl["filename"])
                        tpl_entry["blueprint_json"] = analysis
                        tpl_entry["fields_json"] = analysis.get("editable_fields", [])
                        tpl_entry["styles_json"] = {
                            "margins": analysis.get("margins"),
                            "font_family": analysis.get("font_family"),
                            "orientation": analysis.get("orientation")
                        }
                    except Exception as ex:
                        logger.warning(f"Error analyzing template {off_tpl['filename']}: {ex}")
                results.append(tpl_entry)

        return results

    @classmethod
    def get_template_by_id(cls, template_id: int, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Recupera los datos y bytes binarios de una plantilla por su ID.
        Si no se encuentra en base de datos, busca en las plantillas oficiales predefinidas.
        """
        from app.ai.template_engine import template_engine, TEMPLATES_STORAGE_DIR

        user_id = user.get("id") or user.get("user_id")
        user_role = str(user.get("role_name") or user.get("role") or "").upper()
        tpl_alt_id = (template_id - 1000) if (template_id and template_id >= 1000) else (template_id + 1000 if template_id else None)
        try:
            with get_db() as conn:
                row = conn.execute("""
                    SELECT * FROM smartteacher_templates WHERE id = ? OR id = ?
                """, (template_id, tpl_alt_id)).fetchone()
                if row:
                    r_dict = dict(row)
                    if r_dict["is_institutional"] != 1 and r_dict.get("user_id") != user_id and user_role not in ["ADMINISTRADOR", "DIRECTOR"]:
                        return None

                    # Resuelve archivo en disco multiplataforma (Windows <-> Linux)
                    if r_dict.get("file_path"):
                        fp = r_dict["file_path"]
                        if not os.path.exists(fp):
                            fname = os.path.basename(fp.replace("\\", "/"))
                            alt_fp = os.path.join(TEMPLATES_STORAGE_DIR, fname)
                            if os.path.exists(alt_fp):
                                fp = alt_fp
                            else:
                                alt_fp2 = os.path.abspath(os.path.join("data", "templates", "smartteacher", fname))
                                if os.path.exists(alt_fp2):
                                    fp = alt_fp2
                        if os.path.exists(fp):
                            r_dict["file_path"] = fp
                            with open(fp, "rb") as fpb:
                                r_dict["file_bytes"] = fpb.read()

                    for j_field in ["blueprint_json", "fields_json", "styles_json"]:
                        if r_dict.get(j_field) and isinstance(r_dict[j_field], str):
                            try:
                                r_dict[j_field] = json.loads(r_dict[j_field])
                            except Exception:
                                pass
                    return r_dict
        except Exception as e:
            logger.warning(f"Error fetching template {template_id} from DB: {e}")

        # Fallback para IDs institucionales
        for off_tpl in cls.OFFICIAL_CET34_TEMPLATES:
            if off_tpl["id"] in [template_id, tpl_alt_id]:
                f_path = os.path.join(TEMPLATES_STORAGE_DIR, off_tpl["filename"])
                if not os.path.exists(f_path):
                    f_path_alt = os.path.abspath(os.path.join("data", "templates", "smartteacher", off_tpl["filename"]))
                    if os.path.exists(f_path_alt):
                        f_path = f_path_alt
                f_bytes = None
                if os.path.exists(f_path):
                    with open(f_path, "rb") as fp:
                        f_bytes = fp.read()
                analysis = template_engine.analyze_template(f_bytes, off_tpl["filename"]) if f_bytes else {}
                return {
                    "id": off_tpl["id"],
                    "user_id": None,
                    "name": off_tpl["name"],
                    "doc_type": off_tpl["doc_type"],
                    "description": off_tpl["description"],
                    "filename": off_tpl["filename"],
                    "file_path": f_path,
                    "file_bytes": f_bytes,
                    "blueprint_json": analysis,
                    "fields_json": analysis.get("editable_fields", []),
                    "styles_json": {
                        "margins": analysis.get("margins"),
                        "font_family": analysis.get("font_family"),
                        "orientation": analysis.get("orientation")
                    },
                    "is_institutional": 1
                }

        return None
    @classmethod
    def save_uploaded_template(
        cls,
        user: Dict[str, Any],
        file_bytes: bytes,
        filename: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analiza y guarda un archivo modelo como plantilla reutilizable en la biblioteca.
        """
        from app.ai.template_engine import template_engine, TEMPLATES_STORAGE_DIR
        from app.ai.document_processor import document_processor

        user_id = user.get("id") or user.get("user_id")
        teacher_id = user.get("teacher_id")

        analysis = template_engine.analyze_template(file_bytes, filename)
        if not analysis.get("success"):
            return analysis

        clean_name = (name or analysis.get("filename") or filename).strip()
        doc_type = analysis.get("doc_type", "ficha_guia")
        clean_desc = (description or f"Plantilla personalizada para {doc_type.replace('_', ' ')} subida por el docente.").strip()

        safe_filename = f"tpl_user{user_id}_{document_processor.sanitize_filename(filename)}"
        file_path = os.path.join(TEMPLATES_STORAGE_DIR, safe_filename)
        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        except Exception as fe:
            logger.warning(f"Could not write template to disk: {fe}")
            file_path = None

        bp_json = json.dumps(analysis, ensure_ascii=False)
        fields_json = json.dumps(analysis.get("editable_fields", []), ensure_ascii=False)
        styles_json = json.dumps({
            "margins": analysis.get("margins"),
            "font_family": analysis.get("font_family"),
            "orientation": analysis.get("orientation")
        }, ensure_ascii=False)

        new_id = None
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO smartteacher_templates (
                    user_id, teacher_id, name, doc_type, description,
                    filename, file_path, file_bytes, blueprint_json, fields_json, styles_json,
                    is_institutional, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                user_id, teacher_id, clean_name, doc_type, clean_desc,
                safe_filename, file_path, file_bytes, bp_json, fields_json, styles_json
            ))
            new_id = cur.lastrowid
            conn.commit()

        analysis["id"] = new_id
        analysis["template_id"] = new_id
        analysis["name"] = clean_name
        analysis["message"] = f"Plantilla '{clean_name}' guardada exitosamente en la biblioteca."
        return analysis

    @classmethod
    def delete_template(cls, template_id: int, user: Dict[str, Any]) -> bool:
        """
        Elimina una plantilla personalizada. Queda estrictamente prohibido eliminar
        plantillas institucionales oficiales (is_institutional = 1).
        """
        user_id = user.get("id") or user.get("user_id")
        user_role = str(user.get("role_name") or user.get("role") or "").upper()

        with get_db() as conn:
            tpl = conn.execute("SELECT * FROM smartteacher_templates WHERE id = ?", (template_id,)).fetchone()
            if not tpl:
                return False
            if tpl["is_institutional"] == 1:
                return False
            if tpl["user_id"] != user_id and user_role not in ["ADMINISTRADOR", "DIRECTOR"]:
                return False

            conn.execute("DELETE FROM smartteacher_templates WHERE id = ?", (template_id,))
            conn.commit()
            return True

    @classmethod
    def generate_material_from_template(
        cls,
        user: Dict[str, Any],
        template_id: Optional[int] = None,
        template_bytes: Optional[bytes] = None,
        template_filename: Optional[str] = None,
        prompt: Optional[str] = None,
        topic: Optional[str] = None,
        grade: Optional[int] = None,
        specialty: Optional[str] = None,
        purpose: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        session_type: Optional[str] = None,
        custom_sections: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera un material nuevo para cualquier tema utilizando como molde una plantilla real.
        Inserta el contenido generado en el archivo de plantilla original preservando márgenes,
        tablas, membrete y estilos.
        """
        from app.ai.template_engine import template_engine

        tpl_record = None
        tpl_bytes = template_bytes
        tpl_name = template_filename or "Plantilla_Modelo.docx"

        if template_id:
            tpl_record = cls.get_template_by_id(template_id, user)
            if tpl_record:
                tpl_bytes = tpl_record.get("file_bytes")
                if not tpl_bytes and tpl_record.get("file_path"):
                    cand_fp = tpl_record["file_path"]
                    if not os.path.exists(cand_fp):
                        cand_name = os.path.basename(cand_fp.replace("\\", "/"))
                        alt1 = os.path.join(TEMPLATES_STORAGE_DIR, cand_name)
                        alt2 = os.path.abspath(os.path.join("data", "templates", "smartteacher", cand_name))
                        if os.path.exists(alt1):
                            cand_fp = alt1
                        elif os.path.exists(alt2):
                            cand_fp = alt2
                    if os.path.exists(cand_fp):
                        with open(cand_fp, "rb") as fp:
                            tpl_bytes = fp.read()
                tpl_name = tpl_record.get("filename") or tpl_record.get("name") or "Plantilla_Modelo.docx"
                if not any(tpl_name.endswith(ext) for ext in [".docx", ".pdf", ".txt", ".pptx"]):
                    tpl_name += ".docx"

        if not tpl_bytes:
            # Fallback inteligente: si la plantilla física no está en disco, generamos el material dinámico
            doc_type = (tpl_record.get("doc_type") if tpl_record else None) or "ficha_trabajo"
            logger.warning(f"Plantilla física {template_id} no encontrada en disco. Ejecutando generación nativa para {doc_type}.")
            active_topic = (topic or "").strip() or "Tema Técnico de Especialidad"
            active_grade = grade or 5
            active_spec = specialty or "Educación para el Trabajo"
            active_dur = duration_minutes or 90
            teacher_name = user.get("full_name") or user.get("username") or "Docente"
            full_prompt = prompt or f"Genera un documento oficial de tipo {doc_type} sobre '{active_topic}' para {active_grade}° de secundaria en {active_spec}. I.E. INEI N.° 34 de Chancay."
            if doc_type == "sesion_aprendizaje":
                gen_res = cls.generate_cneb_session_structured(
                    user=user,
                    topic=active_topic,
                    grade=active_grade,
                    specialty=active_spec,
                    duration_minutes=active_dur,
                    session_type=session_type or "general",
                    structure_mode="institucional"
                )
            else:
                gen_res = cls.generate_material_from_instructions(
                    user=user,
                    prompt=full_prompt,
                    preferred_type=doc_type,
                    grade=active_grade,
                    specialty=active_spec
                )
            return {
                "success": True,
                "template_id": template_id,
                "template_name": tpl_name,
                "doc_type": doc_type,
                "title": gen_res.get("title") or active_topic,
                "topic": active_topic,
                "grade": active_grade,
                "specialty": active_spec,
                "duration_minutes": active_dur,
                "teacher_name": teacher_name,
                "content_markdown": gen_res.get("content_markdown") or gen_res.get("content") or f"# {active_topic}\n\nDocumento institucional generado exitosamente.",
                "content_json": gen_res.get("content_json") or gen_res.get("structured_json") or {},
                "docx_bytes": gen_res.get("docx_bytes"),
                "pptx_bytes": gen_res.get("pptx_bytes"),
                "metadata": gen_res.get("metadata", {}),
                "status": "BORRADOR_PLANTILLA_GENERADO"
            }

        analysis = template_engine.analyze_template(tpl_bytes, tpl_name)
        doc_type = analysis.get("doc_type", "sesion_aprendizaje")
        sections = custom_sections or analysis.get("sections")

        active_topic = (topic or "").strip()
        if not active_topic and prompt:
            m_t = re.search(r'(?:sobre|acerca\s+de|tema:?)\s+([^\n\r\.\,]+)', prompt, re.IGNORECASE)
            active_topic = m_t.group(1).strip() if m_t else prompt[:60]
        active_topic = active_topic or "Tema Técnico de Especialidad"

        active_grade = grade or 5
        active_spec = specialty or "Educación para el Trabajo"
        active_dur = duration_minutes or (225 if doc_type == "sesion_aprendizaje" and session_type == "tecnica" else (135 if session_type == "emprendimiento" else 90))

        full_prompt = prompt or f"Genera un documento de tipo {doc_type} sobre '{active_topic}' para {active_grade}° de secundaria en {active_spec}."

        if doc_type == "sesion_aprendizaje":
            gen_res = cls.generate_cneb_session_structured(
                user=user,
                topic=active_topic,
                grade=active_grade,
                specialty=active_spec,
                duration_minutes=active_dur,
                session_type=session_type or ("tecnica" if "gtz" in tpl_name.lower() or "5h" in tpl_name.lower() else "general"),
                structure_mode="institucional"
            )
        else:
            eff_sections = None if doc_type == "presentacion_pptx" else sections
            eff_bp = None if doc_type == "presentacion_pptx" else analysis
            gen_res = cls.generate_material_from_instructions(
                user=user,
                prompt=full_prompt,
                preferred_type=doc_type,
                grade=active_grade,
                specialty=active_spec,
                custom_sections=eff_sections,
                reference_blueprint=eff_bp
            )

        teacher_name = user.get("full_name") or user.get("username") or "Docente"
        doc_data = {
            "title": gen_res.get("title") or active_topic,
            "topic": active_topic,
            "doc_type": doc_type,
            "specialty": active_spec,
            "grade": active_grade,
            "section_name": "A",
            "duration_minutes": active_dur,
            "purpose": purpose or gen_res.get("purpose") or "",
            "content_markdown": gen_res.get("content_markdown") or gen_res.get("content") or "",
            "content_json": gen_res.get("content_json") or gen_res.get("structured_json") or {},
            "teacher_name": teacher_name,
            "template_id": template_id,
            "template_name": tpl_name
        }

        if doc_type == "presentacion_pptx":
            rendered_pptx_bytes = template_engine.render_pptx_from_template(tpl_bytes, doc_data)
            return {
                "success": True,
                "template_id": template_id,
                "template_name": tpl_name,
                "doc_type": "presentacion_pptx",
                "title": doc_data["title"],
                "topic": active_topic,
                "grade": active_grade,
                "specialty": active_spec,
                "duration_minutes": active_dur,
                "teacher_name": teacher_name,
                "content_markdown": gen_res.get("content_markdown") or f"# Presentación: {active_topic}\n\nPresentación interactiva de 7 diapositivas con membrete oficial CET N.º 34.",
                "content_json": doc_data["content_json"],
                "pptx_bytes": rendered_pptx_bytes,
                "pptx_size_bytes": len(rendered_pptx_bytes),
                "docx_bytes": None,
                "docx_size_bytes": 0,
                "preserved_elements": analysis.get("preserved_elements", []),
                "metadata": gen_res.get("metadata", {}),
                "status": "BORRADOR_PLANTILLA_GENERADO"
            }

        rendered_docx_bytes = template_engine.render_docx_from_template(tpl_bytes, doc_data)

        return {
            "success": True,
            "template_id": template_id,
            "template_name": tpl_name,
            "doc_type": doc_type,
            "title": doc_data["title"],
            "topic": active_topic,
            "grade": active_grade,
            "specialty": active_spec,
            "duration_minutes": active_dur,
            "teacher_name": teacher_name,
            "content_markdown": doc_data["content_markdown"],
            "content_json": doc_data["content_json"],
            "docx_bytes": rendered_docx_bytes,
            "docx_size_bytes": len(rendered_docx_bytes),
            "preserved_elements": analysis.get("preserved_elements", []),
            "metadata": gen_res.get("metadata", {}),
            "status": "BORRADOR_PLANTILLA_GENERADO"
        }


ai_service = AIService()
