from app.ai.curriculum_knowledge import resolve_curriculum_context
"""
Esquemas Pydantic para la Generación Documental Estructurada de SmartTeacher AI.
Define la fuente única de verdad pedagógica para Fichas de Aprendizaje,
Sesiones de Aprendizaje y Unidades Didácticas en la I.E. Emblemática INEI N.º 34.
"""

from typing import List, Dict, Optional, Any, Union
import json
import re
from pydantic import BaseModel, Field, ValidationError


class ActividadPedagogicaItem(BaseModel):
    """Actividad práctica estructurada para la ficha de trabajo del estudiante."""
    numero: int = Field(default=1, description="Número de la actividad (1, 2, 3...)")
    titulo: str = Field(..., description="Título técnico descriptivo de la actividad")
    instrucciones: str = Field(..., description="Instrucciones operativas paso a paso para el estudiante")
    evidencia: str = Field(default="Reporte o avance verificado", description="Producto o evidencia verificable que debe registrar el estudiante")


class CriterioCotejoItem(BaseModel):
    """Criterio de evaluación para la lista de cotejo institucional (4 columnas)."""
    criterio: str = Field(..., description="Criterio de evaluación observable y medible")
    evidencia: str = Field(default="Evidencia verificable", description="Evidencia o recomendación técnica")


class FichaAprendizajeStructured(BaseModel):
    """
    Estructura canónica completa de una Ficha de Aprendizaje (CET N.° 34).
    Alimenta idénticamente a la plantilla DOCX y al generador PDF.
    """
    titulo: str = Field(..., description="Título de la ficha de trabajo")
    area: str = Field(default="Educación para el Trabajo - Computación e Informática", description="Área curricular o especialidad técnica")
    grado: int = Field(default=1, ge=1, le=5, description="Grado de secundaria (1 a 5)")
    seccion: str = Field(default="A", description="Sección del aula o taller")
    fecha: str = Field(default="____ / ____ / 2026", description="Fecha de aplicación")
    docente: str = Field(default="[Docente Responsable - Por completar]", description="Nombre del docente titular")
    
    # Currículo Nacional CNEB (EPT Oficial)
    competencia: str = Field(
        default="Gestiona proyectos de emprendimiento económico o social",
        description="Competencia oficial del Currículo Nacional de Educación Básica (CNEB)"
    )
    capacidades: str = Field(
        default="Aplica habilidades técnicas. Trabaja cooperativamente para lograr objetivos y metas.",
        description="Capacidades del CNEB asociadas a la competencia"
    )
    desempeno: str = Field(
        default="Ejecuta el procedimiento técnico y conceptual cumpliendo especificaciones y normas de seguridad.",
        description="Desempeño contextualizado medible"
    )
    
    # 1. Propósito y Objetivos
    proposito: str = Field(..., description="Propósito de aprendizaje de la sesión o ficha")
    evidencia_general: str = Field(..., description="Producto o evidencia general a entregar")
    objetivos_aprendizaje: List[str] = Field(
        default_factory=list,
        description="Tres objetivos de aprendizaje específicos (bullet points)"
    )
    
    # 2. Situación de reto
    situacion_reto: str = Field(..., description="Contexto del problema y desafío técnico a resolver")
    
    # 3. Reto y marco teórico
    marco_teorico: str = Field(..., description="Fundamentación conceptual técnica del tema")
    ejemplo_modelo_pasos: List[str] = Field(
        default_factory=list,
        description="Pasos del ejemplo modelo (Paso 1 Diagnóstico, Paso 2 Planificación, Paso 3 Ejecución, Paso 4 Control)"
    )
    ejemplo_modelo_resultado: str = Field(
        default="",
        description="Resultado esperado del ejemplo modelo"
    )
    
    # 4. Actividades pedagógicas aplicadas
    actividades: List[ActividadPedagogicaItem] = Field(
        default_factory=list,
        description="Actividades prácticas estructuradas de taller o laboratorio"
    )
    
    # 5. Profundización y extensión
    actividad_extension: str = Field(..., description="Actividad de extensión y profundización creativa en equipo")
    ejercicios_consolidacion: List[str] = Field(
        default_factory=list,
        description="Ejercicios de consolidación y aplicación práctica"
    )
    
    # 6. Evaluación formativa (Lista de cotejo 4 columnas)
    lista_cotejo: List[CriterioCotejoItem] = Field(
        default_factory=list,
        description="Criterios para la lista de cotejo oficial de 4 columnas"
    )
    metacognicion: str = Field(
        default="¿Qué aprendí hoy y cómo puedo aplicar este aprendizaje en una situación real?",
        description="Pregunta de metacognición para el estudiante"
    )


class SesionAprendizajeStructured(BaseModel):
    """
    Estructura canónica completa de una Sesión de Aprendizaje CNEB / GTZ (CET N.° 34).
    Alimenta idénticamente a la plantilla DOCX y al generador PDF.
    """
    titulo: str = Field(..., description="Título de la sesión de aprendizaje")
    area: str = Field(default="Educación para el Trabajo - Computación e Informática", description="Área o especialidad")
    modulo_formativo: str = Field(default="Módulo Formativo de Especialidad", description="Nombre del módulo formativo")
    grado: int = Field(default=1, ge=1, le=5, description="Grado escolar")
    seccion: str = Field(default="A", description="Sección")
    duracion_minutos: int = Field(default=90, description="Duración en minutos (90, 135, 225)")
    docente: str = Field(default="[Docente Responsable - Por completar]", description="Docente titular")
    
    # CNEB
    competencia: str = Field(
        default="Gestiona proyectos de emprendimiento económico o social",
        description="Competencia oficial CNEB"
    )
    capacidades: str = Field(
        default="Aplica habilidades técnicas. Trabaja cooperativamente para lograr objetivos y metas.",
        description="Capacidades CNEB"
    )
    desempeno: str = Field(
        default="Aplica destrezas técnicas cumpliendo normas de calidad y seguridad.",
        description="Desempeño contextualizado"
    )
    
    # Propósitos
    proposito_sesion: str = Field(..., description="Propósito formativo de la sesión")
    criterios_evaluacion: str = Field(..., description="Criterios de evaluación observables")
    evidencias_aprendizaje: str = Field(..., description="Evidencia o producto tangible a verificar")
    
    # Situación significativa
    situacion_significativa: str = Field(..., description="Contexto del problema y retos a resolver")
    
    # Procesos didácticos GTZ (Tabla de 4 columnas: Paso, Tiempo, Actividad Docente, Actividad Estudiante)
    procesos_didacticos_gtz: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Etapas de acción completa GTZ: Informar, Planificar, Decidir, Realizar, Controlar, Valorar"
    )
    
    # Recursos y Bibliografía
    materiales: List[str] = Field(default_factory=list, description="Materiales y recursos de aula/taller")
    bibliografia: List[str] = Field(default_factory=list, description="Bibliografía y fuentes de consulta CNEB/MINEDU")


# =============================================================================
# FUNCIONES DE NORMALIZACIÓN Y GENERACIÓN DETERMINISTA
# =============================================================================

# =============================================================================
# FUNCIONES DE NORMALIZACIÓN Y GENERACIÓN DETERMINISTA MULTI-ÁREA CNEB
# =============================================================================

def normalize_cneb_competence(raw_comp: Optional[str] = None, topic: str = "", specialty: str = "") -> str:
    """Garantiza que la competencia sea una competencia oficial del CNEB correspondiente al área curricular solicitada."""
    s = str(raw_comp or "").strip().lower()
    t = f"{topic} {specialty}".lower()
    
    cneb_official = [
        "Resuelve problemas de cantidad",
        "Resuelve problemas de regularidad, equivalencia y cambio",
        "Resuelve problemas de forma, movimiento y localización",
        "Resuelve problemas de gestión de datos e incertidumbre",
        "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
        "Indaga mediante métodos científicos para construir sus conocimientos",
        "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno",
        "Lee diversos tipos de textos escritos en su lengua materna",
        "Escribe diversos tipos de textos en su lengua materna",
        "Se comunica oralmente en su lengua materna",
        "Construye interpretaciones históricas",
        "Gestiona responsablemente el espacio y el ambiente",
        "Gestiona responsablemente los recursos económicos",
        "Construye su identidad",
        "Convive y participa democráticamente en la búsqueda del bien común",
        "Asume una vida saludable",
        "Se desenvuelve de manera autónoma a través de su motricidad",
        "Interactúa a través de sus habilidades sociomotrices",
        "Crea proyectos desde los lenguajes artísticos",
        "Aprecia de manera crítica manifestaciones artístico-culturales",
        "Se comunica oralmente en inglés como lengua extranjera",
        "Lee diversos tipos de textos en inglés como lengua extranjera",
        "Escribe diversos tipos de textos en inglés como lengua extranjera",
        "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente",
        "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida",
        "Gestiona proyectos de emprendimiento económico o social",
        "Se desenvuelve en los entornos virtuales generados por las TIC",
        "Gestiona su aprendizaje de manera autónoma"
    ]
    for c in cneb_official:
        if c.lower() in s or (s and s in c.lower() and len(s) > 12):
            return c

    # 1. Ciencia y Tecnología
    if any(k in t for k in ["ciencia", "cyt", "biolog", "químic", "quimic", "físic", "fisic", "célula", "celula", "ecosistema", "seres vivos", "materia", "energía", "energia", "tierra"]):
        if any(k in t for k in ["indag", "experiment", "hipótesis", "hipotesis", "método científ", "metodo"]):
            return "Indaga mediante métodos científicos para construir sus conocimientos"
        if any(k in t for k in ["diseñ", "disen", "prototipo", "solución tecnol", "solucion tecnol"]):
            return "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno"
        return "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo"

    # 2. Matemática
    if any(k in t for k in ["matem", "fracci", "númer", "numer", "aritm", "proporc", "porcent", "cantidad"]):
        return "Resuelve problemas de cantidad"
    if any(k in t for k in ["álgebr", "algebr", "ecuaci", "inecuaci", "funci", "patron", "patrón", "regularidad"]):
        return "Resuelve problemas de regularidad, equivalencia y cambio"
    if any(k in t for k in ["geometr", "triáng", "triang", "polígon", "perímet", "área", "volumen", "forma"]):
        return "Resuelve problemas de forma, movimiento y localización"
    if any(k in t for k in ["estadíst", "estadist", "probabil", "gráfico", "grafico", "frecuencia", "media", "moda", "datos"]):
        return "Resuelve problemas de gestión de datos e incertidumbre"

    # 3. Comunicación
    if any(k in t for k in ["comunic", "lengua", "lectur", "comprensi"]):
        if any(k in t for k in ["escrib", "redacci", "producci", "texto"]):
            return "Escribe diversos tipos de textos en su lengua materna"
        if any(k in t for k in ["oral", "exposici", "debate", "diálogo"]):
            return "Se comunica oralmente en su lengua materna"
        return "Lee diversos tipos de textos escritos en su lengua materna"

    # 4. Ciencias Sociales
    if any(k in t for k in ["social", "historia", "virreinat", "inca", "cultura", "tiempo"]):
        return "Construye interpretaciones históricas"
    if any(k in t for k in ["geograf", "territorio", "ambiente", "clima", "cuenca", "espacio"]):
        return "Gestiona responsablemente el espacio y el ambiente"
    if any(k in t for k in ["econom", "financ", "mercado", "recurso"]):
        return "Gestiona responsablemente los recursos económicos"

    # 5. DPCC
    if any(k in t for k in ["dpcc", "desarrollo personal", "identidad", "pubertad", "emocion", "autoestima", "autocuidado"]):
        return "Construye su identidad"
    if any(k in t for k in ["ciudadan", "conviven", "democrac", "derechos", "cívic", "civic"]):
        return "Convive y participa democráticamente en la búsqueda del bien común"

    # 6. Educación Física
    if any(k in t for k in ["física", "fisica", "calentamiento", "hidrataci", "salud", "nutrición"]):
        return "Asume una vida saludable"
    if any(k in t for k in ["motriz", "motor", "coordinac", "atlet", "gimnas", "deporte"]):
        return "Se desenvuelve de manera autónoma a través de su motricidad"

    # 7. Arte y Cultura
    if any(k in t for k in ["arte", "cultura", "pintura", "color", "dibujo", "danza", "música", "teatro"]):
        if any(k in t for k in ["aprec", "crític", "analiz"]):
            return "Aprecia de manera crítica manifestaciones artístico-culturales"
        return "Crea proyectos desde los lenguajes artísticos"

    # 8. Inglés
    if any(k in t for k in ["inglés", "ingles", "english"]):
        if any(k in t for k in ["read", "lee"]):
            return "Lee diversos tipos de textos en inglés como lengua extranjera"
        if any(k in t for k in ["writ", "escrib"]):
            return "Escribe diversos tipos de textos en inglés como lengua extranjera"
        return "Se comunica oralmente en inglés como lengua extranjera"

    # 9. Religión
    if any(k in t for k in ["relig", "fe", "dios", "evangel"]):
        return "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente"

    # 10. EPT / General default
    return "Gestiona proyectos de emprendimiento económico o social"


def build_ficha_from_dict(raw: Dict[str, Any], default_topic: str = "Actividad Pedagógica") -> FichaAprendizajeStructured:
    """
    Construye y valida una FichaAprendizajeStructured con estricta coherencia curricular CNEB,
    diferenciando las 10 áreas del MINEDU y garantizando el formato canónico de 6 secciones oficiales CET N.° 34.
    """
    topic = str(raw.get("topic") or raw.get("titulo") or default_topic).strip()
    specialty = str(raw.get("specialty") or raw.get("area") or "Ciencia y Tecnología").strip()
    
    clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "").strip()
    spec_l = clean_spec.lower()
    t_lower = f"{topic} {clean_spec}".lower()

    grade = int(raw.get("grade") or raw.get("grado") or 1)
    if grade < 1 or grade > 5:
        grade = 1

    clean_teacher = str(raw.get("teacher_name") or raw.get("docente") or "Prof. Roberto Bazán Palacios").strip()
    if clean_teacher in ["Docente", "Profesor", "None", ""]:
        clean_teacher = "Prof. Roberto Bazán Palacios"

    curr_info = resolve_curriculum_context(topic=topic, grade=grade, specialty=clean_spec)
    raw_comp = raw.get("competence") or raw.get("competencia")
    official_comp = normalize_cneb_competence(raw_comp, topic, specialty) if raw_comp else curr_info["competencia"]

    # -------------------------------------------------------------
    # ADAPTACIÓN CURRICULAR SEGÚN EL ÁREA FORMATIVA
    # -------------------------------------------------------------
    # 1. CIENCIA Y TECNOLOGÍA
    if "ciencia" in spec_l or "cyt" in spec_l or "célula" in t_lower or "celula" in t_lower or "biolog" in t_lower:
        area_display = "Ciencia y Tecnología"
        capacidades = "Comprende y usa conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo. Evalúa las implicancias del saber y del quehacer científico y tecnológico."
        desempeno = f"Explica la estructura, función y relaciones de {topic} a partir de evidencias científicas y modelos conceptuales."
        proposito = f"Relacionar las principales características y estructuras de {topic} con sus funciones vitales, explicando su importancia para los seres vivos."
        evidencia = f"Organizador visual que relaciona estructuras y funciones de {topic}, acompañado de una explicación científica breve."
        objs = [
            f"Distinguir las partes y características principales de {topic}.",
            f"Relacionar cada componente con su función biológica y explicar su interdependencia.",
            f"Comunicar una explicación científica usando evidencias y vocabulario adecuado."
        ]
        reto = f"En la naturaleza y en nuestra comunidad de Chancay, los seres vivos interactúan continuamente con su entorno. Frente a situaciones ambientales cambiantes, ¿qué estructuras y procesos relacionados con {topic} permiten a los organismos adaptarse, obtener energía y mantener la vida?"
        if "célula" in t_lower or "celula" in t_lower:
            teor = (
                f"Las células constituyen la unidad anatómica, funcional y genética de todos los seres vivos.\\n"
                f"• Organización estructural básica: Membrana celular (barrera selectiva y transporte), Citoplasma (medio acuoso con organelos) y Material genético / ADN (centro de control celular).\\n"
                f"• Clasificación por complejidad: Procariontes (sin núcleo membranoso, ej. bacterias) y Eucariontes (con núcleo definido y organelos membranosos).\\n"
                f"• Diferenciación eucariota: Célula Animal (heterótrofa, con centríolos) vs. Célula Vegetal (autótrofa, con pared de celulosa, cloroplastos y gran vacuola central)."
            )
            act_items = [
                ActividadPedagogicaItem(numero=1, titulo="Relaciona estructuras", instrucciones="Une cada organelo con su función vital: Núcleo (control genético), Mitocondria (respiración celular y energía ATP), Cloroplasto (fotosíntesis y glucosa vegetal) y Membrana (transporte selectivo).", evidencia="Relación de organelos y funciones completada."),
                ActividadPedagogicaItem(numero=2, titulo="Organizador visual", instrucciones="Completa el siguiente mapa conceptual en tu ficha: [LA CÉLULA] ──► Eucarionte ──► Animal (sin pared) y Vegetal (con pared celular y cloroplastos) / ──► Procarionte (sin núcleo membranoso).", evidencia="Mapa conceptual y cuadro comparativo verificado."),
                ActividadPedagogicaItem(numero=3, titulo="Comunica científicamente", instrucciones="Redacta una explicación de 5 líneas fundamentando por qué la mitocondria y el cloroplasto son los motores bioenergéticos esenciales para los seres vivos.", evidencia="Argumentación científica en la ficha de trabajo.")
            ]
        else:
            teor = f"{topic} constituye un principio fundamental para comprender el funcionamiento de los seres vivos y de la materia. Todas las estructuras coordinan procesos que permiten la nutrición, relación y reproducción celular y ecológica."
            act_items = [
                ActividadPedagogicaItem(numero=1, titulo="Relaciona", instrucciones=f"Une cada estructura o concepto de {topic} con su función principal en los seres vivos.", evidencia=f"Relación conceptual de {topic} completada."),
                ActividadPedagogicaItem(numero=2, titulo="Organizador visual", instrucciones=f"Elabora un mapa conceptual o cuadro sinóptico sintetizando los elementos centrales de {topic}.", evidencia=f"Organizador visual de {topic} completado."),
                ActividadPedagogicaItem(numero=3, titulo="Comunica", instrucciones=f"Redacta una explicación fundamentada de 5 líneas sobre cómo interactúan los componentes de {topic}.", evidencia="Explicación argumentada en la ficha.")
            ]
        pasos = [
            f"Paso 1 – Observación: Identificar las estructuras principales y organelos involucrados en {topic}.",
            f"Paso 2 – Relación funcional: Analizar cómo cada componente desempeña una función específica en el organismo.",
            f"Paso 3 – Integración: Explicar cómo interactúan los componentes para mantener el equilibrio y la energía vital.",
            f"Paso 4 – Conclusión: Formular una explicación científica fundamentada sobre el rol de {topic} en los seres vivos."
        ]
        res_modelo = f"Se comprende con claridad la estructura y función de {topic}, demostrando su rol vital con lenguaje científico."
        ext = f"Elabora un organizador gráfico o modelo de {topic} con materiales reciclables. Incluye etiquetas descriptivas de sus partes y una breve leyenda explicativa de su función biológica."
        cons = [
            f"Construye una cadena de causa y efecto que explique la importancia de {topic} para el equilibrio biológico.",
            f"Completa: Si un organismo no tuviera las estructuras de {topic}, entonces __________ porque __________.",
            f"Elabora un esquema gráfico de {topic} señalando sus partes clave y escribiendo una función para cada una."
        ]
        chk_items = [
            CriterioCotejoItem(criterio=f"Relaciona correctamente las estructuras y funciones fundamentales de {topic}.", evidencia="Organizador visual y respuestas verificadas."),
            CriterioCotejoItem(criterio=f"Explica con lenguaje científico y evidencias la importancia de {topic} para los seres vivos.", evidencia="Argumentación escrita en la ficha de trabajo.")
        ]

    # 2. MATEMÁTICA
    elif "matem" in spec_l or "fracci" in t_lower or "númer" in t_lower:
        area_display = "Matemática"
        capacidades = "Traduce cantidades a expresiones numéricas. Comunica su comprensión sobre los números y las operaciones. Usa estrategias y procedimientos de estimación y cálculo. Argumenta afirmaciones sobre las relaciones numéricas."
        desempeno = f"Modela situaciones cotidianas mediante expresiones numéricas y operativas en {topic}, justificando sus procedimientos."
        proposito = f"Interpretar y resolver situaciones problemáticas vinculadas a {topic} aplicando representaciones gráficas y cálculo exacto."
        evidencia = f"Resolución argumentada de situaciones problemáticas con {topic} y representación gráfica del procedimiento."
        objs = [
            f"Interpretar conceptos, representaciones y propiedades de {topic}.",
            f"Resolver operaciones y problemas de contexto real aplicando algoritmos matemáticos.",
            f"Argumentar procedimientos, estimar resultados y comprobar si una respuesta es razonable."
        ]
        reto = f"En las actividades cotidianas, productivas y comerciales de Chancay, se presentan situaciones donde se deben calcular y comparar cantidades vinculadas a {topic}. ¿Cómo podemos modelar matemáticamente esta situación para encontrar la solución óptima y verificar su exactitud?"
        teor = f"{topic} representa una herramienta matemática indispensable para cuantificar, comparar y resolver situaciones del entorno. Su correcta comprensión facilita la toma de decisiones informadas y la modelación cuantitativa de la realidad."
        pasos = [
            f"Paso 1 – Comprensión: Identificar los datos numéricos y las relaciones esenciales en el problema de {topic}.",
            f"Paso 2 – Planificación: Seleccionar el algoritmo de cálculo, propiedades operativas y representaciones adecuadas.",
            f"Paso 3 – Ejecución: Desarrollar las operaciones paso a paso simplificando y comprobando equivalencias.",
            f"Paso 4 – Verificación: Contrastar la respuesta con las condiciones iniciales para confirmar su validez."
        ]
        res_modelo = f"Se obtiene el resultado exacto mediante procedimientos matemáticos verificados y justificados."
        act_items = [
            ActividadPedagogicaItem(numero=1, titulo="Básico", instrucciones=f"Representa con un gráfico y calcula la operación inicial sobre {topic}. Justifica el procedimiento.", evidencia="Operación básica resuelta y graficada."),
            ActividadPedagogicaItem(numero=2, titulo="Intermedio", instrucciones=f"Resuelve y simplifica la situación operativa de {topic} aplicando propiedades numéricas.", evidencia="Cálculo intermedio desarrollado y simplificado."),
            ActividadPedagogicaItem(numero=3, titulo="Situación problemática", instrucciones=f"Resuelve el problema de contexto cotidiano sobre {topic} respondiendo con claridad a las preguntas planteadas.", evidencia="Problema resuelto con argumentación completa.")
        ]
        ext = f"Inventa una situación cotidiana de tu entorno familiar o comercial que se resuelva mediante {topic}. Incluye gráfico, procedimiento paso a paso y respuesta con su unidad de medida correspondiente."
        cons = [
            f"Crea un problema de dos pasos con {topic} y redacta su solución razonada.",
            f"Resuelve la operación combinada de {topic} y verifica el resultado mediante una estimación previa.",
            f"Explica con tus propias palabras qué propiedad matemática garantiza que tu procedimiento en {topic} sea correcto."
        ]
        chk_items = [
            CriterioCotejoItem(criterio=f"Representa y opera situaciones matemáticas de {topic} con un procedimiento comprensible.", evidencia="Desarrollo de ejercicios y gráficos."),
            CriterioCotejoItem(criterio=f"Comprueba si su respuesta es razonable y comunica con claridad el significado del resultado.", evidencia="Argumentación y comprobación de respuestas.")
        ]

    # 3. DPCC
    elif "dpcc" in spec_l or "desarrollo personal" in spec_l or "pubertad" in t_lower or "identidad" in t_lower:
        area_display = "Desarrollo Personal, Ciudadanía y Cívica (DPCC)"
        capacidades = "Se valora a sí mismo. Autorregula sus emociones. Reflexiona y argumenta éticamente. Vive su sexualidad de manera integral y responsable."
        desempeno = f"Reconoce sus características personales, cambios y emociones en {topic}, proponiendo estrategias de autorregulación y autocuidado."
        proposito = f"Reconocer las dimensiones personales, emocionales y sociales de {topic}, practicando estrategias de autocuidado, autorregulación y búsqueda de apoyo."
        evidencia = f"Respuestas argumentadas a un dilema o caso ético y formulación de un plan personal de autocuidado en {topic}."
        objs = [
            f"Reconocer cambios físicos, emocionales y sociales vinculados a {topic}.",
            f"Valorar la diversidad de experiencias y ritmos personales sin burlas ni estereotipos.",
            f"Aplicar estrategias de comunicación asertiva, autorregulación y búsqueda de apoyo de confianza."
        ]
        reto = f"En la etapa escolar y de convivencia adolescente en Chancay, surgen situaciones donde las opiniones o cambios de ánimo generan tensión y dilemas personales en relación con {topic}. ¿Qué decisiones reflexivas y asertivas pueden ayudar a cuidar el bienestar propio y el de los demás?"
        teor = f"{topic} comprende procesos fundamentales del desarrollo humano y la convivencia social. Reconocer lo que sentimos, expresarlo respetando los límites propios y ajenos y acudir a personas de confianza son pilares clave para una vida saludable y libre de violencia."
        pasos = [
            f"Paso 1 – Reconocimiento: Identificar las emociones, pensamientos y factores involucrados en {topic}.",
            f"Paso 2 – Reflexión ética: Analizar las consecuencias de distintas decisiones para uno mismo y los demás.",
            f"Paso 3 – Comunicación asertiva: Formular una respuesta empática que exprese límites y necesidades claras.",
            f"Paso 4 – Plan de acción: Establecer compromisos concretos y redes de apoyo seguras."
        ]
        res_modelo = f"Se definen pautas claras de autocuidado y convivencia basadas en el respeto mutuo y la asertividad."
        act_items = [
            ActividadPedagogicaItem(numero=1, titulo="Identifica", instrucciones=f"Clasifica los factores y situaciones de {topic} reconociendo su impacto personal y social.", evidencia="Clasificación de factores completada."),
            ActividadPedagogicaItem(numero=2, titulo="Responde asertivamente", instrucciones=f"Formula una respuesta asertiva frente a un caso de {topic} utilizando un mensaje en primera persona.", evidencia="Respuesta asertiva redactada."),
            ActividadPedagogicaItem(numero=3, titulo="Plan de apoyo", instrucciones=f"Escribe tres acciones concretas para promover el autocuidado y la buena convivencia en torno a {topic}.", evidencia="Plan personal de autocuidado.")
        ]
        ext = f"Crea una tarjeta informativa o afiche titulado 'Mi bienestar importa' con tres mensajes de respeto, una estrategia para manejar emociones intensas y una red de apoyo en relación con {topic}."
        cons = [
            f"Elabora un mapa de personas y servicios de confianza en la comunidad a los que acudirías ante dudas sobre {topic}.",
            f"Transforma tres respuestas impulsivas en respuestas asertivas usando la estructura: 'Yo siento... cuando... necesito...'.",
            f"Formula una conclusión reflexiva sobre la importancia de valorar las diferencias individuales en {topic}."
        ]
        chk_items = [
            CriterioCotejoItem(criterio=f"Reconoce la diversidad de experiencias y cambios en {topic} sin estereotipos ni discriminación.", evidencia="Análisis del caso ético desarrollado."),
            CriterioCotejoItem(criterio=f"Propone acciones asertivas de autocuidado, autorregulación y búsqueda de apoyo en {topic}.", evidencia="Plan de autocuidado y compromisos.")
        ]

    # 4. EDUCACIÓN FÍSICA
    elif "física" in spec_l or "fisica" in spec_l or "calentamiento" in t_lower or "deporte" in t_lower:
        area_display = "Educación Física"
        capacidades = "Comprende las relaciones entre la actividad física, alimentación, postura e higiene personal y del ambiente, y la salud. Incorpora prácticas que mejoran su calidad de vida."
        desempeno = f"Aplica pautas de activación fisiológica, hidratación y cuidado corporal en {topic} para optimizar el esfuerzo físico y prevenir lesiones."
        proposito = f"Comprender la importancia fisiológica de {topic} y aplicar hábitos saludables de cuidado corporal antes, durante y después de la práctica motriz."
        evidencia = f"Ejecución de una rutina progresiva de {topic} y elaboración de una pauta personal de hidratación y cuidado físico."
        objs = [
            f"Explicar cómo la práctica de {topic} prepara y protege el organismo para el esfuerzo físico.",
            f"Ejecutar una secuencia progresiva y controlada de ejercicios vinculados a {topic}.",
            f"Tomar decisiones responsables sobre hidratación, descanso y señales de fatiga corporal."
        ]
        reto = f"Durante las actividades recreativas y deportivas en la I.E. CET N.° 34, algunos estudiantes inician juegos intensos sin preparación previa, manifestando cansancio prematuro y riesgo de tirones musculares. ¿Qué secuencia de {topic} y hábitos de cuidado debieron seguir?"
        teor = f"{topic} constituye un proceso fisiológico progresivo que eleva la temperatura, activa la circulación y prepara articulaciones y músculos para el movimiento seguro. Una correcta hidratación y regulación del esfuerzo son indispensables para la salud integral."
        pasos = [
            f"Paso 1 – Activación general: Movilidad articular y desplazamientos suaves de baja intensidad.",
            f"Paso 2 – Activación específica: Ejercicios dinámicos que simulan los gestos de la actividad principal.",
            f"Paso 3 – Regulación e hidratación: Control de pulsaciones y consumo de agua en sorbos espaciados.",
            f"Paso 4 – Recuperación: Estiramientos controlados y retorno a la calma fisiológica."
        ]
        res_modelo = f"El cuerpo se prepara con seguridad, alcanzando un estado óptimo para la actividad física sin riesgo de lesiones."
        act_items = [
            ActividadPedagogicaItem(numero=1, titulo="Ordena", instrucciones=f"Organiza cronológicamente una rutina de 5 momentos para la correcta ejecución de {topic}.", evidencia="Secuencia de ejercicios ordenada."),
            ActividadPedagogicaItem(numero=2, titulo="Practica", instrucciones=f"En parejas, dirijan una secuencia de 6 minutos de {topic} verificando que la intensidad sea progresiva.", evidencia="Práctica motriz coordinada."),
            ActividadPedagogicaItem(numero=3, titulo="Decide", instrucciones=f"Indica qué medidas inmediatas tomarías si aparecen mareos, fatiga extrema o dolor durante {topic}.", evidencia="Pautas de seguridad y primeros auxilios.")
        ]
        ext = f"Diseña un afiche ilustrado con tres beneficios fundamentales de {topic}, momentos adecuados para hidratarse y una recomendación clave de seguridad deportiva."
        cons = [
            f"Registra cómo cambia tu respiración y frecuencia cardíaca antes, durante y después de practicar {topic}.",
            f"Analiza tres escenarios de clima y esfuerzo; describe cómo adaptarías {topic} en cada caso.",
            f"Diseña una rutina de 8 minutos con tiempos, nombres de ejercicios y orden lógico para {topic}."
        ]
        chk_items = [
            CriterioCotejoItem(criterio=f"Realiza la secuencia de {topic} de manera progresiva, técnica y segura.", evidencia="Ejecución de la rutina motriz."),
            CriterioCotejoItem(criterio=f"Explica y aplica hábitos adecuados de hidratación, descanso y cuidado corporal en {topic}.", evidencia="Pautas de cuidado físico y registro.")
        ]

    # 5. GENERAL CNEB ACADÉMICO vs. EPT TALLER
    elif curr_info.get("is_ept", False) or any(k in spec_l for k in ["educación para el trabajo", "educacion para el trabajo", "ept", "taller", "mecanic", "electric", "computac", "vestid", "contab"]):
        area_display = curr_info["area"] if curr_info.get("is_ept") else (clean_spec if clean_spec else "Educación para el Trabajo")
        capacidades = "Crea propuestas de valor. Aplica habilidades técnicas. Trabaja cooperativamente para lograr objetivos y metas. Evalúa los resultados del proyecto de emprendimiento."
        desempeno = f"Planifica y ejecuta procesos de diseño, prototipado o servicio técnico en {topic}, aplicando criterios de calidad y sostenibilidad."
        proposito = f"Desarrollar habilidades prácticas y capacidades de gestión técnica en {topic}, formulando propuestas que respondan a necesidades del entorno."
        evidencia = f"Prototipo técnico, lienzo de modelo o producto aplicado de {topic} verificado con pautas de control."
        objs = [
            f"Identificar las necesidades y requerimientos técnicos en {topic}.",
            f"Aplicar procedimientos sistemáticos de ejecución técnica y control de calidad en {topic}.",
            f"Evaluar la viabilidad, impacto y oportunidades de mejora continua en la propuesta de {topic}."
        ]
        reto = f"En la comunidad productiva y comercial de Chancay, se requiere optimizar procesos y ofrecer soluciones sostenibles mediante {topic}. ¿Cómo podemos diseñar y validar una propuesta técnica que resulte eficiente, accesible y de alta calidad?"
        teor = f"{topic} comprende métodos, herramientas y estándares técnicos indispensables para la producción y los servicios. Su correcta aplicación permite organizar recursos, optimizar tiempos y garantizar soluciones de calidad."
        pasos = [
            f"Paso 1 – Diagnóstico: Identificar el problema central y las especificaciones requeridas en {topic}.",
            f"Paso 2 – Planificación: Seleccionar materiales, herramientas y diseñar el flujo de trabajo.",
            f"Paso 3 – Ejecución técnica: Desarrollar el prototipo o procedimiento aplicando normas de seguridad.",
            f"Paso 4 – Validación: Probar el resultado y recoger sugerencias de mejora."
        ]
        res_modelo = f"Se completa el procedimiento técnico de {topic} cumpliendo con los estándares de calidad y seguridad."
        act_items = [
            ActividadPedagogicaItem(numero=1, titulo="Diagnóstico y análisis", instrucciones=f"Describe los tres requerimientos o componentes esenciales para el desarrollo de {topic}.", evidencia="Diagnóstico técnico completado."),
            ActividadPedagogicaItem(numero=2, titulo="Aplicación práctica", instrucciones=f"Aplica la secuencia operativa de {topic} verificando los criterios de calidad y funcionalidad.", evidencia="Producto o procedimiento verificado."),
            ActividadPedagogicaItem(numero=3, titulo="Mejora continua", instrucciones=f"Evalúa los resultados obtenidos en {topic} y formula dos propuestas de mejora para el proceso.", evidencia="Propuesta de optimización redactada.")
        ]
        ext = f"Elabora una guía técnica o diagrama de procesos de {topic} para compartir con tus compañeros, incluyendo recomendaciones de seguridad y sostenibilidad."
        cons = [
            f"Compara dos alternativas técnicas para resolver {topic} y fundamenta cuál es más eficiente.",
            f"Formula tres preguntas para recoger retroalimentación de usuarios sobre {topic}.",
            f"Completa una matriz de: necesidad, solución técnica, materiales y evidencia de validación para {topic}."
        ]
        chk_items = [
            CriterioCotejoItem(criterio=f"Aplica los procedimientos técnicos y operativos de {topic} con precisión y seguridad.", evidencia="Producto o prototipo verificado."),
            CriterioCotejoItem(criterio=f"Evalúa y justifica mejoras en su propuesta de {topic} a partir de evidencias concretas.", evidencia="Ficha de trabajo y reporte de mejora.")
        ]
    else:
        # Formato Universal Académico CNEB (Arte y Cultura, Comunicación, Religión, DPCC, etc.) sin contaminación de taller 5S
        area_display = curr_info["area"]
        official_comp = curr_info["competencia"]
        capacidades = curr_info["capacidades"]
        desempeno = f"Explica, analiza y aplica conceptos y procedimientos sobre {topic} sustentando conclusiones con pensamiento crítico según los estándares de {area_display}."
        proposito = curr_info["proposito"]
        evidencia = f"Ficha de análisis comprensivo y organizador visual sobre {topic} con conclusiones fundamentadas."
        objs = [
            f"Identificar y explicar los conceptos y principios fundamentales de {topic}.",
            f"Analizar relaciones, causas, efectos o procedimientos vinculados a {topic} con rigor metodológico.",
            f"Formular conclusiones fundamentadas y valorar la trascendencia de {topic} en el entorno escolar y social."
        ]
        reto = f"En nuestra comunidad de Chancay y en el entorno escolar, surgen interrogantes formativas y dilemas cotidianos sobre cómo abordar {topic}. ¿De qué manera podemos investigar, analizar y resolver situaciones vinculadas a {topic} aplicando los conocimientos de {area_display}?"
        teor = (
            f"{topic} constituye un objeto de estudio y desarrollo formativo fundamental en {area_display}.\n"
            f"• Conceptos y fundamentos clave: Permite comprender los principios, hechos y modelos que estructuran {topic}.\n"
            f"• Relaciones y método analítico: Desarrolla el pensamiento crítico, la argumentación sustentada y el discernimiento ético o científico.\n"
            f"• Aplicación contextual: Conecta los saberes de {topic} con la vida cotidiana, la convivencia comunitaria y los desafíos actuales."
        )
        pasos = [
            f"Paso 1 – Comprensión: Reconocer las ideas, elementos y conceptos nucleares de {topic}.",
            f"Paso 2 – Análisis reflexivo: Examinar fuentes, relaciones o casos prácticos vinculados a {topic}.",
            f"Paso 3 – Argumentación: Elaborar explicaciones fundamentadas contrastando diferentes puntos de vista.",
            f"Paso 4 – Aplicación y valoración: Formular propuestas o conclusiones transferibles a la realidad de Chancay."
        ]
        res_modelo = f"Se analiza con rigor formativo el tema {topic}, sustentando ideas en evidencias comprobables y criterios del área de {area_display}."
        act_items = [
            ActividadPedagogicaItem(numero=1, titulo="Comprensión y análisis conceptual", instrucciones=f"A partir de la lectura y conceptos clave sobre {topic}, responde las preguntas formativas fundamentando cada respuesta.", evidencia=f"Preguntas de comprensión de {topic} resueltas."),
            ActividadPedagogicaItem(numero=2, titulo="Organizador visual y mapa conceptual", instrucciones=f"A partir de la Figura 1 (esquema ilustrativo), completa el mapa conceptual jerárquico relacionando los componentes esenciales de {topic}.", evidencia="Organizador conceptual jerárquico verificado."),
            ActividadPedagogicaItem(numero=3, titulo="Juicio crítico y aplicación", instrucciones=f"Redacta una reflexión de 5 a 8 líneas explicando la importancia de aplicar lo aprendido sobre {topic} en tu vida personal o comunitaria.", evidencia="Reflexión crítica argumentada en la ficha de trabajo.")
        ]
        ext = f"Elabora una infografía o resumen argumentativo sobre {topic} para divulgar las principales conclusiones con tus compañeros de aula."
        cons = [
            f"Compara dos posturas o enfoques diferentes sobre {topic} y explica tu posición fundamentada.",
            f"Elabora un cuadro de causa, efecto y propuesta de acción en torno a {topic}.",
            f"Explica qué valores o actitudes ciudadanas se fortalecen al estudiar y reflexionar sobre {topic}."
        ]
        chk_items = [
            CriterioCotejoItem(criterio=f"Comprende y explica los conceptos esenciales y relaciones de {topic}.", evidencia="Actividades 1 y 2 completadas."),
            CriterioCotejoItem(criterio=f"Formula conclusiones argumentadas y reflexivas sobre {topic} con sentido crítico.", evidencia="Actividad 3 y reflexión verificada.")
        ]

    # Sobrescribir con datos específicos pasados por el docente si existen
    if raw.get("proposito"):
        proposito = str(raw["proposito"]).strip()
    if raw.get("evidencia") or raw.get("evidencia_general"):
        evidencia = str(raw.get("evidencia") or raw.get("evidencia_general")).strip()
    if raw.get("objetivos_aprendizaje") and isinstance(raw["objetivos_aprendizaje"], list) and len(raw["objetivos_aprendizaje"]) >= 2:
        objs = [str(x) for x in raw["objetivos_aprendizaje"][:3]]
    if raw.get("situacion_reto") and len(str(raw["situacion_reto"]).strip()) > 20:
        reto = str(raw["situacion_reto"]).strip()
    if raw.get("marco_teorico") and len(str(raw["marco_teorico"]).strip()) > 20:
        teor = str(raw["marco_teorico"]).strip()

    meta = str(raw.get("metacognicion") or "¿Qué aprendí hoy y cómo puedo aplicar este aprendizaje en una situación real?").strip()

    return FichaAprendizajeStructured(
        titulo=f"FICHA DE APRENDIZAJE: {topic.upper()}",
        area=area_display,
        grado=grade,
        seccion=str(raw.get("section_name") or raw.get("seccion") or "A"),
        fecha=str(raw.get("fecha") or "____ / ____ / 2026"),
        docente=clean_teacher,
        competencia=official_comp,
        capacidades=capacidades,
        desempeno=desempeno,
        proposito=proposito,
        evidencia_general=evidencia,
        objetivos_aprendizaje=objs,
        situacion_reto=reto,
        marco_teorico=teor,
        ejemplo_modelo_pasos=pasos,
        ejemplo_modelo_resultado=res_modelo,
        actividades=act_items,
        actividad_extension=ext,
        ejercicios_consolidacion=cons,
        lista_cotejo=chk_items,
        metacognicion=meta
    )

def ficha_to_markdown(f: FichaAprendizajeStructured) -> str:
    """Renderiza una vista Markdown limpia y elegante estrictamente derivada de la estructura validada."""
    md = f"# {f.titulo}\n\n"
    md += f"**Área:** {f.area}  \n"
    md += f"**Grado y Sección:** {f.grado}.° «{f.seccion}» | **Fecha:** {f.fecha}  \n"
    md += f"**Docente Titular:** {f.docente}  \n"
    md += f"**Competencia (CNEB):** {f.competencia}  \n"
    md += f"**Capacidades:** {f.capacidades}  \n"
    md += f"**Desempeño Contextualizado:** {f.desempeno}  \n\n"
    md += "---\n\n"
    md += "### I. PROPÓSITO DE APRENDIZAJE\n"
    md += f"**Propósito:** {f.proposito}  \n"
    md += f"**Producto o Evidencia:** {f.evidencia_general}  \n\n"
    md += "**Objetivos de aprendizaje:**\n"
    for obj in f.objetivos_aprendizaje:
        md += f"- {obj}\n"
    md += "\n---\n\n"
    md += "### II. SITUACIÓN DE RETO («¡ACEPTA EL DESAFÍO!»)\n"
    md += f"{f.situacion_reto}\n\n"
    md += "---\n\n"
    md += "### III. MARCO TEÓRICO Y CONCEPTOS CLAVE\n"
    md += f"{f.marco_teorico}\n\n"
    md += "**Ejemplo Modelo:**\n"
    for p in f.ejemplo_modelo_pasos:
        md += f"- {p}\n"
    if f.ejemplo_modelo_resultado:
        md += f"- **Resultado:** {f.ejemplo_modelo_resultado}\n"
    md += "\n---\n\n"
    md += "### IV. ACTIVIDADES PEDAGÓGICAS APLICADAS\n\n"
    for a in f.actividades:
        md += f"#### Actividad {a.numero}: {a.titulo}\n"
        md += f"**Instrucciones:** {a.instrucciones}  \n"
        md += f"**Evidencia requerida:** {a.evidencia}  \n"
        md += "*Respuesta / desarrollo:* __________________________________________________________________________________________\n\n"
    md += "---\n\n"
    md += "### V. PROFUNDIZACIÓN Y ACTIVIDAD DE EXTENSIÓN\n"
    md += f"{f.actividad_extension}\n\n"
    md += "**Ejercicios de consolidación:**\n"
    for ej in f.ejercicios_consolidacion:
        md += f"- {ej}\n"
    md += "\n---\n\n"
    md += "### VI. INSTRUMENTO DE EVALUACIÓN: LISTA DE COTEJO (4 COLUMNAS)\n\n"
    md += "| Criterio de Evaluación | Sí | En proceso | Evidencia / Recomendación |\n"
    md += "| :--- | :---: | :---: | :--- |\n"
    for item in f.lista_cotejo:
        md += f"| {item.criterio} | [   ] | [   ] | {item.evidencia} |\n"
    md += "\n"
    md += f"**Metacognición:** {f.metacognicion}  \n"
    md += "__________________________________________________________________________________________\n"
    md += "__________________________________________________________________________________________\n"
    return md

class ItemOpcionMultiple(BaseModel):
    numero: int = Field(..., description="Número de ítem (1, 2, 3)")
    pregunta: str = Field(..., description="Enunciado de la pregunta")
    opciones: List[str] = Field(default_factory=list, description="Lista de 3 alternativas")
    opciones_texto: str = Field(default="", description="Texto con formato ☐ a) ... ☐ b) ... ☐ c) ...")
    respuesta_correcta: str = Field(default="", description="Respuesta correcta esperada")
    justificacion: str = Field(default="", description="Fundamentación pedagógica o técnica")

class ItemAbierto(BaseModel):
    numero: int = Field(..., description="Número de ítem (4, 5, 6)")
    pregunta: str = Field(..., description="Enunciado de desarrollo o explicación")
    lineas_respuesta: int = Field(default=2, description="Cantidad de líneas para escribir")
    respuesta_esperada: str = Field(default="", description="Criterio de respuesta o procedimiento esperado")
    justificacion: str = Field(default="", description="Fundamentación pedagógica")

class ItemVerdaderoFalso(BaseModel):
    numero: int = Field(..., description="Número de ítem (7, 8, 9, 10)")
    afirmacion: str = Field(..., description="Enunciado declarativo")
    valor_esperado: str = Field(default="V", description="V o F")
    justificacion: str = Field(default="", description="Por qué es verdadero o falso")

class ItemSolucionario(BaseModel):
    item: str = Field(..., description="Número de ítem (1 al 10)")
    respuesta_esperada: str = Field(..., description="Respuesta esperada o criterio clave")

class FichaExamenPracticaStructured(BaseModel):
    modo: str = Field(default="examen", description="'examen' o 'practica'")
    titulo_documento: str = Field(default="FICHA DE EXAMEN", description="'FICHA DE EXAMEN' o 'FICHA DE PRÁCTICA'")
    institucion: str = Field(default="INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY")
    area: str = Field(..., description="Área curricular oficial")
    grado: int = Field(default=1, description="Grado de secundaria (1 a 5)")
    grado_str: str = Field(default="1.° de Secundaria")
    seccion: str = Field(default="A")
    tema: str = Field(..., description="Tema específico evaluado")
    fecha: str = Field(default="____ / ____ / 2026")
    docente: str = Field(default="Prof. Roberto Bazán Palacios")
    indicaciones: str = Field(default="Indicaciones: Lee con atención. Marca una sola alternativa en la sección A, responde con tus propias palabras en la sección B y escribe V o F en la sección C.")
    seccion_a: List[ItemOpcionMultiple] = Field(default_factory=list)
    seccion_b: List[ItemAbierto] = Field(default_factory=list)
    seccion_c: List[ItemVerdaderoFalso] = Field(default_factory=list)
    puntaje_por_pregunta: int = Field(default=1)
    puntaje_total: int = Field(default=10)
    puntaje_texto: str = Field(default="Cada pregunta vale 1 punto. Total: 10 puntos.")
    orientacion_docente: str = Field(default="Las respuestas abiertas pueden admitir formulaciones equivalentes si mantienen la idea científica, matemática o comunicativa principal.")
    solucionario: List[ItemSolucionario] = Field(default_factory=list)

def build_examen_practica_from_dict(raw: Dict[str, Any], default_topic: str = "Evaluación Formativa") -> FichaExamenPracticaStructured:
    """
    Construye y valida una FichaExamenPracticaStructured con estricta separación institucional:
    - Para el área de Matemática: Estructura especializada de EXACTAMENTE 2 SECCIONES (10 ítems):
      * Sección A: Marca la alternativa correcta (5 ítems de opción múltiple con 3 alternativas a, b, c).
      * Sección B: Resuelve y muestra tu procedimiento (5 problemas abiertos con espacio para desarrollo y respuesta final).
      * Sin Sección C (sin Verdadero o Falso).
      * Solucionario de 10 ítems (ítems 1 al 5: alternativa y justificación; ítems 6 al 10: procedimiento paso a paso y resultado).
    - Para las demás áreas curriculares (EPT, C&T, DPCC, Ed. Física, Arte, Inglés, CCSS, Comunicación):
      * Estructura canónica de 3 secciones (10 ítems):
        - Sección A: Marca la alternativa correcta (3 ítems).
        - Sección B: Responde y explica (3 ítems).
        - Sección C: Verdadero (V) o falso (F) (4 ítems).
      * Solucionario oficial de 10 filas.
    - Soporta modo 'examen' (FICHA DE EXAMEN) y modo 'practica' (FICHA DE PRÁCTICA).
    - Compatible con temarios EBR y COAR.
    """
    topic = str(raw.get("topic") or raw.get("tema") or raw.get("title") or default_topic).strip().strip('"').strip('“').strip('”')
    specialty = str(raw.get("specialty") or raw.get("area") or "Educación para el Trabajo").strip()

    # Detectar modo: examen vs practica
    raw_mode = str(raw.get("modo") or raw.get("mode") or raw.get("doc_type") or "").lower()
    raw_text = f"{topic} {raw.get('raw_prompt') or ''} {raw.get('title') or ''} {raw_mode}".lower()
    if any(k in raw_text for k in ["práctica", "practica", "evaluación continua", "practica calificada", "practica_ejercicios"]):
        modo = "practica"
        titulo_doc = "FICHA DE PRÁCTICA"
    else:
        modo = "examen"
        titulo_doc = "FICHA DE EXAMEN"

    grade = int(raw.get("grade") or raw.get("grado") or 1)
    if grade < 1 or grade > 5:
        grade = 1
    grade_str = f"{grade}.° de Secundaria"

    seccion = str(raw.get("seccion") or raw.get("section_name") or "A").strip()
    fecha = str(raw.get("fecha") or raw.get("date") or "____ / ____ / 2026").strip()
    clean_teacher = str(raw.get("teacher_name") or raw.get("docente") or "Prof. Roberto Bazán Palacios").strip()
    if clean_teacher in ["Docente", "Profesor", "None", ""]:
        clean_teacher = "Prof. Roberto Bazán Palacios"

    # Resolución del Área Curricular oficial
    clean_spec = specialty.replace("Educación para el Trabajo - ", "").replace("Educacion para el Trabajo - ", "").strip()
    spec_l = clean_spec.lower()
    t_lower = f"{topic} {clean_spec}".lower()

    curr_info = resolve_curriculum_context(topic=topic, grade=grade, specialty=clean_spec)
    area_display = curr_info["area"]

    sec_a: List[ItemOpcionMultiple] = []
    sec_b: List[ItemAbierto] = []
    sec_c: List[ItemVerdaderoFalso] = []
    solucionario: List[ItemSolucionario] = []

    is_matematica = (area_display == "Matemática" or curr_info.get("is_math", False))

    # =========================================================================
    # A. RAMA MATEMÁTICA: EXACTAMENTE 2 SECCIONES (5 MARCAR + 5 RESOLVER)
    # =========================================================================
    if is_matematica:
        indicaciones_text = "Indicaciones: Lee atentamente cada situación problemática. Resuelve y marca la alternativa correcta en la sección A (ítems 1 al 5). Desarrolla de forma clara y ordenada tu procedimiento en la sección B (ítems 6 al 10)."
        orientacion_text = "Las respuestas de la sección B deben mostrar el procedimiento y planteamiento matemático adecuado, además de la respuesta final numérica o algebraica."

        # 1. Preset Matemática: Ecuaciones, Inecuaciones y Sistemas (EBR / COAR)
        if any(k in t_lower for k in ["ecuaci", "despeje", "incógnita", "incognita", "sistema", "inecuaci"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="En una ecuación lineal como 2x + 6 = 18, ¿cuál es el valor de la incógnita x?",
                                   opciones=["x = 6", "x = 12", "x = 4"],
                                   opciones_texto="☐ a) x = 6   ☐ b) x = 12   ☐ c) x = 4",
                                   respuesta_correcta="a) x = 6.", justificacion="2x = 18 - 6 -> 2x = 12 -> x = 6."),
                ItemOpcionMultiple(numero=2, pregunta="¿Qué propiedad permite sumar o restar una misma cantidad a ambos miembros de una igualdad sin alterarla?",
                                   opciones=["Propiedad de monotonía / uniforme", "Propiedad conmutativa", "Propiedad asociativa"],
                                   opciones_texto="☐ a) Propiedad de monotonía / uniforme   ☐ b) Propiedad conmutativa   ☐ c) Propiedad asociativa",
                                   respuesta_correcta="a) Propiedad de monotonía / uniforme.", justificacion="Si a = b, entonces a ± c = b ± c conservando la equivalencia."),
                ItemOpcionMultiple(numero=3, pregunta="En la situación: 'El triple de un número aumentado en 8 equivale a 35', ¿cuál es su expresión algebraica?",
                                   opciones=["3(x + 8) = 35", "3x + 8 = 35", "x + 24 = 35"],
                                   opciones_texto="☐ a) 3(x + 8) = 35   ☐ b) 3x + 8 = 35   ☐ c) x + 24 = 35",
                                   respuesta_correcta="b) 3x + 8 = 35.", justificacion="El triple del número es 3x, aumentado en 8 resulta 3x + 8 = 35."),
                ItemOpcionMultiple(numero=4, pregunta="Al resolver la inecuación 3x − 5 < 10, ¿cuál es el conjunto de valores que satisface a x en los reales?",
                                   opciones=["x < 5", "x > 5", "x ≤ 15"],
                                   opciones_texto="☐ a) x < 5   ☐ b) x > 5   ☐ c) x ≤ 15",
                                   respuesta_correcta="a) x < 5.", justificacion="3x < 15 -> x < 5. El intervalo solución es ]-∞; 5[."),
                ItemOpcionMultiple(numero=5, pregunta="En un sistema de dos ecuaciones lineales, si las dos rectas graficadas coinciden en todos sus puntos, el sistema es:",
                                   opciones=["Compatible determinado (solución única)", "Compatible indeterminado (infinitas soluciones)", "Incompatible (sin solución)"],
                                   opciones_texto="☐ a) Compatible determinado   ☐ b) Compatible indeterminado   ☐ c) Incompatible",
                                   respuesta_correcta="b) Compatible indeterminado.", justificacion="Rectas coincidentes tienen infinitos puntos comunes de intersección.")
            ]
            sec_b = [
                ItemAbierto(numero=6, pregunta="Resuelve paso a paso la ecuación 4(x − 3) + 7 = 2x + 15 y comprueba tu solución.",
                            respuesta_esperada="4x - 12 + 7 = 2x + 15 -> 4x - 5 = 2x + 15 -> 2x = 20 -> x = 10. Comprobación: 4(7) + 7 = 35; 2(10) + 15 = 35. Conforme.",
                            justificacion="Resolución de ecuación lineal de primer grado con signos de agrupación."),
                ItemAbierto(numero=7, pregunta="Plantea y resuelve: Juan compró 3 cuadernos y 2 lapiceros pagando S/ 29. Si cada lapicero cuesta S/ 2.50, ¿cuánto costó cada cuaderno?",
                            respuesta_esperada="3x + 2(2.50) = 29 -> 3x + 5 = 29 -> 3x = 24 -> x = S/ 8. Cada cuaderno costó S/ 8.",
                            justificacion="Modelación algebraica de situaciones financieras cotidianas."),
                ItemAbierto(numero=8, pregunta="Resuelve el siguiente sistema de ecuaciones lineales por el método de reducción o sustitución:\n{ 2x + y = 13\n{ x − y = 2",
                            respuesta_esperada="Sumando ambas ecuaciones: 3x = 15 -> x = 5. Sustituyendo en la 2da: 5 - y = 2 -> y = 3. C.S. = {(5; 3)}.",
                            justificacion="Resolución analítica de un sistema lineal 2x2."),
                ItemAbierto(numero=9, pregunta="Determina el conjunto solución de la inecuación lineal 5x − 8 ≤ 2x + 13 y exprésalo en notación de intervalo.",
                            respuesta_esperada="5x - 2x ≤ 13 + 8 -> 3x ≤ 21 -> x ≤ 7. Conjunto Solución: C.S. = ]-∞; 7].",
                            justificacion="Resolución de inecuaciones y representación formal de intervalos."),
                ItemAbierto(numero=10, pregunta="Dos depósitos de agua contienen 120 litros y 80 litros. Si del primero se extraen 5 litros por minuto y del segundo 3 litros por minuto, ¿después de cuántos minutos tendrán exactamente la misma cantidad de agua? Muestra tu procedimiento.",
                            respuesta_esperada="Ecuación: 120 - 5t = 80 - 3t -> 120 - 80 = 5t - 3t -> 40 = 2t -> t = 20 minutos. Tendrán la misma cantidad tras 20 minutos (20 litros en cada uno).",
                            justificacion="Resolución de problemas contextualizados de razones de cambio y modelación lineal.")
            ]

        # 2. Preset Matemática: Fracciones, Racionales, Proporcionalidad y Porcentajes
        elif any(k in t_lower for k in ["fracci", "racional", "fraccion", "proporc", "porcent", "tanto por ciento", "interés", "interes", "magnitud"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="En una fracción como 3/5, ¿qué significado geométrico o analítico tiene el denominador?",
                                   opciones=["Las partes tomadas de la unidad", "Las partes iguales en que se divide la unidad", "El total de unidades enteras"],
                                   opciones_texto="☐ a) Las partes tomadas   ☐ b) Las partes iguales en que se divide la unidad   ☐ c) El total de unidades",
                                   respuesta_correcta="b) Las partes iguales en que se divide la unidad.", justificacion="El denominador define la partición equitativa de la unidad."),
                ItemOpcionMultiple(numero=2, pregunta="Al efectuar la suma de fracciones heterogéneas 2/3 + 1/6, se obtiene:",
                                   opciones=["3/9", "5/6", "3/6"],
                                   opciones_texto="☐ a) 3/9   ☐ b) 5/6   ☐ c) 3/6",
                                   respuesta_correcta="b) 5/6.", justificacion="Homogenizando denominadores: 4/6 + 1/6 = 5/6."),
                ItemOpcionMultiple(numero=3, pregunta="¿Cuál es el 20% del 50% de 800?",
                                   opciones=["S/ 80", "S/ 160", "S/ 40"],
                                   opciones_texto="☐ a) S/ 80   ☐ b) S/ 160   ☐ c) S/ 40",
                                   respuesta_correcta="a) S/ 80.", justificacion="50% de 800 = 400; 20% de 400 = 0.20 * 400 = 80."),
                ItemOpcionMultiple(numero=4, pregunta="Dos magnitudes son inversamente proporcionales cuando:",
                                   opciones=["Al duplicar una, la otra también se duplica", "Su producto se mantiene constante", "Su cociente se mantiene constante"],
                                   opciones_texto="☐ a) Al duplicar una, la otra se duplica   ☐ b) Su producto se mantiene constante   ☐ c) Su cociente es constante",
                                   respuesta_correcta="b) Su producto se mantiene constante.", justificacion="A * B = k (constante de proporcionalidad inversa)."),
                ItemOpcionMultiple(numero=5, pregunta="La fórmula del interés simple anual generado por un capital C a una tasa r% durante t años es:",
                                   opciones=["I = (C * r * t) / 100", "I = C * (1 + r)^t", "I = (C * t) / (100 * r)"],
                                   opciones_texto="☐ a) I = (C * r * t) / 100   ☐ b) I = C * (1 + r)^t   ☐ c) I = (C * t) / (100 * r)",
                                   respuesta_correcta="a) I = (C * r * t) / 100.", justificacion="Expresión canónica del interés simple anual.")
            ]
            sec_b = [
                ItemAbierto(numero=6, pregunta="Resuelve y simplifica a su mínima expresión: (3/4 − 1/6) ÷ 7/12. Muestra tu procedimiento.",
                            respuesta_esperada="3/4 - 1/6 = 9/12 - 2/12 = 7/12. Luego (7/12) ÷ (7/12) = 1.",
                            justificacion="Operaciones combinadas con fracciones y simplificación."),
                ItemAbierto(numero=7, pregunta="Una tienda en Chancay ofrece una casaca a S/ 160 con un descuento del 25%. Si sobre el precio rebajado se aplica el 18% de IGV, ¿cuánto se paga finalmente?",
                            respuesta_esperada="Descuento: 25% de 160 = S/ 40 -> Precio rebajado = S/ 120. IGV: 18% de 120 = S/ 21.60. Total a pagar = S/ 120 + 21.60 = S/ 141.60.",
                            justificacion="Aplicación comercial de porcentajes e impuestos."),
                ItemAbierto(numero=8, pregunta="Si 8 obreros construyen una obra en 15 días, ¿cuántos días tardarán 12 obreros trabajando con el mismo rendimiento? Plantea la regla de tres.",
                            respuesta_esperada="Magnitudes inversamente proporcionales: 8 * 15 = 12 * d -> 120 = 12d -> d = 10 días.",
                            justificacion="Resolución de situaciones de proporcionalidad inversa."),
                ItemAbierto(numero=9, pregunta="Se deposita un capital de S/ 5,000 al 6% de interés simple anual durante 3 años. Calcula el interés producido y el monto final.",
                            respuesta_esperada="I = (5000 * 6 * 3) / 100 = S/ 900. Monto = C + I = S/ 5,000 + S/ 900 = S/ 5,900.",
                            justificacion="Cálculo financiero de interés simple y monto."),
                ItemAbierto(numero=10, pregunta="De un depósito de agua lleno, se extrae 2/5 de su contenido y luego 1/3 de lo que quedaba. Si aún quedan 400 litros, ¿cuál es la capacidad total del depósito? Justifica tu respuesta.",
                            respuesta_esperada="Queda tras 1ra extracción: 3/5. 2da extracción: (1/3)*(3/5) = 1/5. Fracción restante: 3/5 - 1/5 = 2/5 del total. Si (2/5)T = 400 -> T = (400 * 5) / 2 = 1,000 litros.",
                            justificacion="Problemas con fracciones de fracciones y valor desconocido.")
            ]

        # 3. Preset Matemática: Geometría, Trigonometría y Medición (EBR / COAR)
        elif any(k in t_lower for k in ["geometr", "triáng", "triang", "pitágoras", "pitagoras", "trigono", "ángulo", "angulo", "área", "area", "volumen", "perímet", "sólido", "solido", "plano cartesiano", "analítica", "analitica"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="En un triángulo rectángulo cuyos catetos miden 6 cm y 8 cm, ¿cuánto mide la hipotenusa según el Teorema de Pitágoras?",
                                   opciones=["10 cm", "14 cm", "12 cm"],
                                   opciones_texto="☐ a) 10 cm   ☐ b) 14 cm   ☐ c) 12 cm",
                                   respuesta_correcta="a) 10 cm.", justificacion="c² = 6² + 8² = 36 + 64 = 100 -> c = 10 cm."),
                ItemOpcionMultiple(numero=2, pregunta="En el triángulo notable de 30° y 60°, si el cateto opuesto a 30° mide 5 cm, ¿cuánto mide la hipotenusa?",
                                   opciones=["10 cm", "5√3 cm", "15 cm"],
                                   opciones_texto="☐ a) 10 cm   ☐ b) 5√3 cm   ☐ c) 15 cm",
                                   respuesta_correcta="a) 10 cm.", justificacion="En el triángulo 30°-60° la hipotenusa es el doble del cateto opuesto a 30° (2k = 10)."),
                ItemOpcionMultiple(numero=3, pregunta="¿Cuál es la razón trigonométrica seno (sen α) en un triángulo rectángulo?",
                                   opciones=["Cateto opuesto / Hipotenusa", "Cateto adyacente / Hipotenusa", "Cateto opuesto / Cateto adyacente"],
                                   opciones_texto="☐ a) Cateto opuesto / Hipotenusa   ☐ b) Cateto adyacente / Hipotenusa   ☐ c) Cateto opuesto / Cateto adyacente",
                                   respuesta_correcta="a) Cateto opuesto / Hipotenusa.", justificacion="Definición canónica de la función seno."),
                ItemOpcionMultiple(numero=4, pregunta="¿Cuál es el área de un trapecio cuyas bases miden 12 cm y 8 cm, y cuya altura es 6 cm?",
                                   opciones=["60 cm²", "120 cm²", "48 cm²"],
                                   opciones_texto="☐ a) 60 cm²   ☐ b) 120 cm²   ☐ c) 48 cm²",
                                   respuesta_correcta="a) 60 cm².", justificacion="A = [(B + b) * h] / 2 = [(12 + 8) * 6] / 2 = (20 * 6) / 2 = 60 cm²."),
                ItemOpcionMultiple(numero=5, pregunta="La distancia entre los puntos A(1; 2) y B(4; 6) en el plano cartesiano es:",
                                   opciones=["5 unidades", "7 unidades", "25 unidades"],
                                   opciones_texto="☐ a) 5 unidades   ☐ b) 7 unidades   ☐ c) 25 unidades",
                                   respuesta_correcta="a) 5 unidades.", justificacion="d = √[(4-1)² + (6-2)²] = √[3² + 4²] = √25 = 5.")
            ]
            sec_b = [
                ItemAbierto(numero=6, pregunta="Una escalera de 13 metros de longitud se apoya sobre una pared vertical. Si el pie de la escalera dista 5 metros de la pared, ¿qué altura alcanza sobre la pared? Muestra tu procedimiento con Pitágoras.",
                            respuesta_esperada="h² + 5² = 13² -> h² + 25 = 169 -> h² = 144 -> h = 12 metros.",
                            justificacion="Aplicación del teorema de Pitágoras en problemas reales."),
                ItemAbierto(numero=7, pregunta="Desde un punto en el suelo ubicado a 30 metros de la base de un edificio, se divisa su parte más alta con un ángulo de elevación de 37°. Halla la altura del edificio sabiendo que tan(37°) ≈ 3/4.",
                            respuesta_esperada="tan(37°) = h / 30 -> 3/4 = h / 30 -> 4h = 90 -> h = 22.5 metros.",
                            justificacion="Resolución de situaciones de ángulos de elevación y razones trigonométricas."),
                ItemAbierto(numero=8, pregunta="Un cilindro recto de almacenamiento tiene un radio de base de 3 m y una altura de 10 m. Calcula su volumen y su área lateral (utiliza π ≈ 3.14).",
                            respuesta_esperada="Volumen: V = π * r² * h = 3.14 * 3² * 10 = 3.14 * 9 * 10 = 282.6 m³. Área lateral: AL = 2 * π * r * h = 2 * 3.14 * 3 * 10 = 188.4 m².",
                            justificacion="Cálculo de volumen y superficie de cuerpos de revolución."),
                ItemAbierto(numero=9, pregunta="Halla la ecuación de la recta que pasa por los puntos P(2; 3) y Q(6; 11), calculando previamente su pendiente m.",
                            respuesta_esperada="Pendiente: m = (11 - 3) / (6 - 2) = 8 / 4 = 2. Ecuación punto-pendiente: y - 3 = 2(x - 2) -> y = 2x - 4 + 3 -> y = 2x - 1 (o 2x - y - 1 = 0).",
                            justificacion="Geometría analítica de la recta."),
                ItemAbierto(numero=10, pregunta="El perímetro de un terreno rectangular mide 64 metros. Si el largo excede en 8 metros al ancho, determina las dimensiones del terreno y calcula su área en metros cuadrados.",
                            respuesta_esperada="Sea ancho = x, largo = x + 8. Perímetro: 2(x + x + 8) = 64 -> 2(2x + 8) = 64 -> 4x + 16 = 64 -> 4x = 48 -> x = 12 m. Ancho = 12 m, Largo = 20 m. Área = 12 * 20 = 240 m².",
                            justificacion="Problema geométrico-algebraico de optimización y medidas.")
            ]

        # 4. Preset Matemática: Funciones Reales, Álgebra y Sucesiones (EBR / COAR)
        elif any(k in t_lower for k in ["funci", "cuadrátic", "cuadratica", "lineal", "afín", "afin", "exponencial", "logarítm", "logaritm", "polinom", "álgebra", "algebra", "sucesi", "progresi"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="En la función afín f(x) = 3x − 6, ¿cuáles son la pendiente m y el intercepto con el eje Y?",
                                   opciones=["m = 3, intercepto (0; -6)", "m = -6, intercepto (0; 3)", "m = 3, intercepto (0; 6)"],
                                   opciones_texto="☐ a) m = 3, intercepto (0; -6)   ☐ b) m = -6, intercepto (0; 3)   ☐ c) m = 3, intercepto (0; 6)",
                                   respuesta_correcta="a) m = 3, intercepto (0; -6).", justificacion="En f(x) = mx + b, la pendiente es m=3 y el punto de corte con Y es (0; b)=(0; -6)."),
                ItemOpcionMultiple(numero=2, pregunta="Dada la función cuadrática f(x) = x² − 4x + 3, ¿hacia dónde se abre la parábola y cuál es su eje de simetría?",
                                   opciones=["Se abre hacia arriba, eje de simetría x = 2", "Se abre hacia abajo, eje de simetría x = -2", "Se abre hacia la derecha"],
                                   opciones_texto="☐ a) Hacia arriba, eje x = 2   ☐ b) Hacia abajo, eje x = -2   ☐ c) Hacia la derecha",
                                   respuesta_correcta="a) Hacia arriba, eje x = 2.", justificacion="a = 1 > 0 (abre hacia arriba), x_v = -b/(2a) = -(-4)/2 = 2."),
                ItemOpcionMultiple(numero=3, pregunta="¿Cuál es el valor simplificado de la expresión logarítmica log₂(32)?",
                                   opciones=["5", "16", "2"],
                                   opciones_texto="☐ a) 5   ☐ b) 16   ☐ c) 2",
                                   respuesta_correcta="a) 5.", justificacion="2⁵ = 32, por tanto log₂(32) = 5."),
                ItemOpcionMultiple(numero=4, pregunta="En la progresión aritmética 4, 9, 14, 19, ..., ¿cuál es la razón aritmética r y el término general a_n?",
                                   opciones=["r = 5, a_n = 5n - 1", "r = 4, a_n = 4n + 1", "r = 5, a_n = 5n + 4"],
                                   opciones_texto="☐ a) r = 5, a_n = 5n - 1   ☐ b) r = 4, a_n = 4n + 1   ☐ c) r = 5, a_n = 5n + 4",
                                   respuesta_correcta="a) r = 5, a_n = 5n - 1.", justificacion="r = 9 - 4 = 5. a_n = a_1 + (n - 1)r = 4 + 5(n - 1) = 5n - 1."),
                ItemOpcionMultiple(numero=5, pregunta="Al desarrollar el producto notable binomio al cuadrado (3x + 2)², se obtiene:",
                                   opciones=["9x² + 12x + 4", "9x² + 4", "6x² + 12x + 4"],
                                   opciones_texto="☐ a) 9x² + 12x + 4   ☐ b) 9x² + 4   ☐ c) 6x² + 12x + 4",
                                   respuesta_correcta="a) 9x² + 12x + 4.", justificacion="(a+b)² = a² + 2ab + b² -> (3x)² + 2(3x)(2) + 2² = 9x² + 12x + 4.")
            ]
            sec_b = [
                ItemAbierto(numero=6, pregunta="Dada la función lineal f(x) = 2x − 8, calcula los puntos de corte con los ejes X e Y, y comprueba si el punto (5; 2) pertenece a dicha función.",
                            respuesta_esperada="Corte con Y: x=0 -> y = -8 -> (0; -8). Corte con X: y=0 -> 2x - 8 = 0 -> x = 4 -> (4; 0). Pertenencia de (5; 2): f(5) = 2(5) - 8 = 10 - 8 = 2. Sí pertenece.",
                            justificacion="Análisis analítico y funcional de rectas."),
                ItemAbierto(numero=7, pregunta="Una empresa de transporte cobra una tarifa fija de S/ 6 más S/ 1.50 por cada kilómetro recorrido. Modela la función de costo C(x) y determina el costo para un viaje de 24 km.",
                            respuesta_esperada="Función: C(x) = 1.50x + 6. Para x = 24: C(24) = 1.50(24) + 6 = 36 + 6 = S/ 42. El costo total es S/ 42.",
                            justificacion="Modelación funcional en contextos económicos."),
                ItemAbierto(numero=8, pregunta="Para la función cuadrática f(x) = x² − 6x + 8, calcula las coordenadas del vértice V(h; k) y determina los puntos donde interseca al eje X (raíces).",
                            respuesta_esperada="h = -(-6)/2 = 3; k = f(3) = 3² - 6(3) + 8 = 9 - 18 + 8 = -1. Vértice: V(3; -1). Raíces: x² - 6x + 8 = 0 -> (x - 4)(x - 2) = 0 -> x₁ = 4, x₂ = 2.",
                            justificacion="Determinación de vértice y ceros de la función cuadrática."),
                ItemAbierto(numero=9, pregunta="Una colonia de bacterias se triplica cada hora siguiendo la función exponencial N(t) = 100 * 3^t, donde t está en horas. Halla la población inicial y la cantidad de bacterias al cabo de 4 horas.",
                            respuesta_esperada="Población inicial (t=0): N(0) = 100 * 3⁰ = 100 bacterias. Al cabo de 4 horas: N(4) = 100 * 3⁴ = 100 * 81 = 8,100 bacterias.",
                            justificacion="Modelación con funciones exponenciales de crecimiento."),
                ItemAbierto(numero=10, pregunta="Halla la suma de los primeros 20 términos de la progresión aritmética: 3, 7, 11, 15, ... Muestra tu procedimiento aplicando la fórmula de la suma S_n.",
                            respuesta_esperada="a₁ = 3, r = 4. a₂₀ = 3 + 19(4) = 3 + 76 = 79. Suma: S₂₀ = [(a₁ + a₂₀) * n] / 2 = [(3 + 79) * 20] / 2 = 82 * 10 = 820.",
                            justificacion="Cálculo del término enésimo y suma de progresiones aritméticas.")
            ]

        # 5. Preset Matemática: Estadística y Probabilidad (EBR / COAR)
        elif any(k in t_lower for k in ["estadíst", "estadist", "probabil", "frecuencia", "media", "mediana", "moda", "dispersión", "dispersion", "gráfico", "grafico", "azar", "desviación", "desviacion"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="¿Cuál de las siguientes variables corresponde a una variable cuantitativa continua?",
                                   opciones=["Estatura de los estudiantes en metros", "Número de hermanos en una familia", "Color favorito de polo"],
                                   opciones_texto="☐ a) Estatura en metros   ☐ b) Número de hermanos   ☐ c) Color favorito",
                                   respuesta_correcta="a) Estatura de los estudiantes en metros.", justificacion="Admite valores decimales en un intervalo continuo."),
                ItemOpcionMultiple(numero=2, pregunta="En el conjunto de datos {12, 14, 15, 14, 16, 14, 18}, ¿cuál es el valor de la moda?",
                                   opciones=["14", "15", "14.7"],
                                   opciones_texto="☐ a) 14   ☐ b) 15   ☐ c) 14.7",
                                   respuesta_correcta="a) 14.", justificacion="14 es el dato que más se repite (frecuencia = 3)."),
                ItemOpcionMultiple(numero=3, pregunta="Se lanza un dado común balanceado de 6 caras. ¿Cuál es la probabilidad clásica de obtener un número primo (2, 3 o 5)?",
                                   opciones=["3/6 = 1/2 (50%)", "2/6 = 1/3", "4/6 = 2/3"],
                                   opciones_texto="☐ a) 3/6 = 1/2 (50%)   ☐ b) 2/6 = 1/3   ☐ c) 4/6 = 2/3",
                                   respuesta_correcta="a) 3/6 = 1/2 (50%).", justificacion="Casos favorables: {2, 3, 5} -> 3 casos de 6 posibles -> 1/2."),
                ItemOpcionMultiple(numero=4, pregunta="¿Qué información proporciona la desviación estándar respecto a la media en una muestra?",
                                   opciones=["El grado de dispersión o concentración de los datos respecto a la media", "El valor del dato más alto", "La suma total de todas las frecuencias"],
                                   opciones_texto="☐ a) Dispersión respecto a la media   ☐ b) El dato más alto   ☐ c) La suma total",
                                   respuesta_correcta="a) El grado de dispersión o concentración de los datos respecto a la media.", justificacion="Mide la variabilidad promedio alrededor del promedio aritmético."),
                ItemOpcionMultiple(numero=5, pregunta="En un diagrama circular que representa las preferencias de 200 personas, si una categoría abarca un ángulo de 90°, ¿cuántas personas representa?",
                                   opciones=["50 personas (25%)", "100 personas (50%)", "25 personas (12.5%)"],
                                   opciones_texto="☐ a) 50 personas   ☐ b) 100 personas   ☐ c) 25 personas",
                                   respuesta_correcta="a) 50 personas (25%).", justificacion="90° de 360° es 1/4 = 25%. El 25% de 200 es 50.")
            ]
            sec_b = [
                ItemAbierto(numero=6, pregunta="Las calificaciones de 8 estudiantes en una evaluación de matemática son: 11, 14, 15, 12, 14, 16, 18, 16. Calcula la media aritmética y la mediana de las notas.",
                            respuesta_esperada="Media: (11 + 14 + 15 + 12 + 14 + 16 + 18 + 16) / 8 = 116 / 8 = 14.5. Datos ordenados: 11, 12, 14, 14, 15, 16, 16, 18. Mediana: promedio de las posiciones centrales (14 + 15)/2 = 14.5.",
                            justificacion="Cálculo riguroso de medidas de tendencia central."),
                ItemAbierto(numero=7, pregunta="En una encuesta sobre número de horas semanales de estudio a 20 estudiantes se obtuvieron los datos: 4, 6, 8, 10 horas con frecuencias de 5, 8, 5 y 2 estudiantes respectivamente. Elabora la tabla de frecuencias relativas (h_i) y porcentuales (h_i%).",
                            respuesta_esperada="Frecuencias relativas: 4h: 5/20 = 0.25 (25%); 6h: 8/20 = 0.40 (40%); 8h: 5/20 = 0.25 (25%); 10h: 2/20 = 0.10 (10%). Suma = 1.00 (100%).",
                            justificacion="Construcción e interpretación de tablas de frecuencias."),
                ItemAbierto(numero=8, pregunta="En una urna hay 6 fichas rojas, 4 fichas azules y 5 fichas amarillas. Si se extraen dos fichas consecutivas sin reposición, calcula la probabilidad de que la primera sea azul y la segunda sea roja.",
                            respuesta_esperada="Total fichas = 15. P(Azul 1ra) = 4/15. Quedan 14 fichas en la urna. P(Roja 2da) = 6/14. P(A ∩ R) = (4/15) * (6/14) = 24 / 210 = 4 / 35 ≈ 0.114 (11.4%).",
                            justificacion="Cálculo de probabilidad compuesta dependiente sin reposición."),
                ItemAbierto(numero=9, pregunta="Calcula el rango, la varianza y la desviación estándar para el conjunto de datos de temperaturas registradas: 18, 20, 22, 24, 26.",
                            respuesta_esperada="Media = (18+20+22+24+26)/5 = 110/5 = 22. Rango = 26 - 18 = 8. Desviaciones al cuadrado: (18-22)²=16, (20-22)²=4, (22-22)²=0, (24-22)²=4, (26-22)²=16. Varianza = (16+4+0+4+16)/5 = 40/5 = 8. Desviación estándar = √8 ≈ 2.83.",
                            justificacion="Cálculo paso a paso de medidas de dispersión."),
                ItemAbierto(numero=10, pregunta="Dos secciones de 3.° grado obtuvieron los siguientes promedios y desviaciones estándar en una prueba de matemática: Sección A: media = 14, desviación estándar = 1.8; Sección B: media = 14, desviación estándar = 3.5. Justifica con el coeficiente de variación qué sección presenta un rendimiento más homogéneo.",
                            respuesta_esperada="CV_A = (1.8 / 14) * 100 ≈ 12.86%. CV_B = (3.5 / 14) * 100 = 25%. La Sección A es significativamente más homogénea y consistente porque presenta menor coeficiente de variación y dispersión.",
                            justificacion="Toma de decisiones estadísticas y análisis de homogeneidad.")
            ]

        # 6. Fallback General de Matemática para cualquier otro tema (EBR / COAR)
        else:
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta=f"¿Cuál es el concepto o propiedad matemática fundamental al analizar {topic}?",
                                   opciones=[f"Identificar las variables, constantes y relaciones de {topic}",
                                             f"Resolver sin verificar las condiciones del enunciado",
                                             f"Omitir el análisis de unidades y propiedades"],
                                   opciones_texto=f"☐ a) Identificar variables y relaciones   ☐ b) Resolver sin verificar   ☐ c) Omitir análisis",
                                   respuesta_correcta=f"a) Identificar las variables, constantes y relaciones de {topic}.",
                                   justificacion=f"La correcta identificación de parámetros garantiza el rigor matemático en {topic}."),
                ItemOpcionMultiple(numero=2, pregunta=f"¿Qué estrategia es primordial para modelar algebraicamente una situación de {topic}?",
                                   opciones=[f"Traducir el lenguaje común al lenguaje matemático y plantear la igualdad o función",
                                             f"Asignar valores arbitrarios sin respetar las restricciones",
                                             f"Descartar las relaciones cuantitativas"],
                                   opciones_texto=f"☐ a) Traducir lenguaje común a matemático   ☐ b) Asignar valores arbitrarios   ☐ c) Descartar relaciones",
                                   respuesta_correcta="a) Traducir el lenguaje común al lenguaje matemático y plantear la igualdad o función.",
                                   justificacion="Es el paso esencial del enfoque de resolución de problemas del CNEB."),
                ItemOpcionMultiple(numero=3, pregunta=f"En {topic}, cuando se obtiene un resultado numérico, ¿qué paso garantiza su validez matemática?",
                                   opciones=[f"Comprobar el resultado en la situación inicial y verificar su coherencia",
                                             f"Finalizar sin revisar si el resultado tiene sentido físico o contextual",
                                             f"Cambiar la respuesta al azar si no es un número entero"],
                                   opciones_texto=f"☐ a) Comprobar en la situación inicial   ☐ b) Finalizar sin revisar   ☐ c) Cambiar respuesta al azar",
                                   respuesta_correcta="a) Comprobar el resultado en la situación inicial y verificar su coherencia.",
                                   justificacion="La validación y autorregulación cierran el ciclo de modelación matemática."),
                ItemOpcionMultiple(numero=4, pregunta=f"¿Cuál de las siguientes relaciones describe una propiedad consistente en el estudio de {topic}?",
                                   opciones=[f"La conservación de las propiedades numéricas y operaciones inversas",
                                             f"La alteración arbitraria de los signos en una igualdad",
                                             f"La supresión de datos no convenientes"],
                                   opciones_texto=f"☐ a) Conservación de propiedades y operaciones inversas   ☐ b) Alteración de signos   ☐ c) Supresión de datos",
                                   respuesta_correcta="a) La conservación de las propiedades numéricas y operaciones inversas.",
                                   justificacion="Fundamento algebraico y aritmético formal."),
                ItemOpcionMultiple(numero=5, pregunta=f"¿Qué representa la solución analítica en un problema de {topic}?",
                                   opciones=[f"El valor o conjunto de valores que satisfacen rigurosamente las condiciones dadas",
                                             f"Una aproximación gráfica sin justificación de pasos",
                                             f"Cualquier número positivo elegido por conveniencia"],
                                   opciones_texto=f"☐ a) El conjunto de valores que satisface las condiciones   ☐ b) Aproximación sin pasos   ☐ c) Cualquier número",
                                   respuesta_correcta="a) El valor o conjunto de valores que satisfacen rigurosamente las condiciones dadas.",
                                   justificacion="Definición formal de conjunto solución.")
            ]
            sec_b = [
                ItemAbierto(numero=6, pregunta=f"Plantea un modelo matemático o ecuación básica para resolver un problema aplicativo de {topic} y halla su solución paso a paso.",
                            respuesta_esperada=f"Planteamiento ordenado de variables en {topic}, desarrollo algebraico o numérico claro y obtención de la solución verificada.",
                            justificacion=f"Capacidad de matematizar y modelar situaciones de {topic}."),
                ItemAbierto(numero=7, pregunta=f"Resuelve un ejercicio práctico de nivel intermedio sobre {topic}, detallando cada propiedad utilizada en el proceso.",
                            respuesta_esperada=f"Desarrollo secuencial justificando el uso de axiomas, propiedades distributivas o transformaciones equivalentes en {topic}.",
                            justificacion="Uso de estrategias heurísticas y cálculo fundamentado."),
                ItemAbierto(numero=8, pregunta=f"Una situación contextualizada requiere aplicar {topic} en el entorno de Chancay o escolar. Modela la relación entre las dos variables involucradas y calcula el resultado solicitado.",
                            respuesta_esperada=f"Definición explícita de variables contextuales, planteamiento de la relación cuantitativa sobre {topic} y respuesta con unidades pertinentes.",
                            justificacion="Transferencia de saberes matemáticos a contextos reales."),
                ItemAbierto(numero=9, pregunta=f"Comprueba analíticamente la validez de una solución en {topic} sustituyendo el valor hallado en el planteamiento inicial.",
                            respuesta_esperada="Sustitución explícita de la incógnita en ambos miembros de la expresión original, demostrando la identidad matemática.",
                            justificacion="Verificación de soluciones y razonamiento deductivo."),
                ItemAbierto(numero=10, pregunta=f"Explica con argumentos matemáticos cómo generalizar el procedimiento aplicado en {topic} para resolver cualquier caso similar.",
                            respuesta_esperada=f"Formulación de una regla general, algoritmo o fórmula deducida a partir de las regularidades observadas en {topic}.",
                            justificacion="Generalización y comunicación de ideas matemáticas de alta demanda cognitiva.")
            ]

        # En Matemática, NO hay Sección C
        sec_c = []

    # =========================================================================
    # B. OTRAS ÁREAS CURRICULARES: 3 SECCIONES (3 MARCAR + 3 RESPONDER + 4 V/F)
    # =========================================================================
    else:
        indicaciones_text = "Indicaciones: Lee con atención. Marca una sola alternativa en la sección A, responde con tus propias palabras en la sección B y escribe V o F en la sección C."
        orientacion_text = "Las respuestas abiertas pueden admitir formulaciones equivalentes si mantienen la idea científica, técnica o comunicativa principal."

        # 1. Preset Canónico: Lean Canvas (EPT)
        if any(k in t_lower for k in ["lean canvas", "canvas", "modelo de negocio"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="¿Qué herramienta ayuda a organizar una idea de emprendimiento en bloques?",
                                   opciones=["Lean Canvas", "Círculo cromático", "Línea de tiempo"],
                                   opciones_texto="☐ a) Lean Canvas   ☐ b) Círculo cromático   ☐ c) Línea de tiempo",
                                   respuesta_correcta="a) Lean Canvas.", justificacion="El Lean Canvas modela una idea de negocio en 9 bloques estratégicos."),
                ItemOpcionMultiple(numero=2, pregunta="¿Qué debe describir la propuesta única de valor?",
                                   opciones=["Solo el precio", "Por qué la propuesta es útil y diferente", "El nombre del estudiante"],
                                   opciones_texto="☐ a) Solo el precio   ☐ b) Por qué la propuesta es útil y diferente   ☐ c) El nombre del estudiante",
                                   respuesta_correcta="b) Explica el beneficio y la diferencia para el cliente.", justificacion="Define el valor diferenciador que atrae a los usuarios."),
                ItemOpcionMultiple(numero=3, pregunta="¿Qué acción permite validar una hipótesis?",
                                   opciones=["Decorar el canvas", "Entrevistar y observar a usuarios", "Copiar otra idea"],
                                   opciones_texto="☐ a) Decorar el canvas   ☐ b) Entrevistar y observar a usuarios   ☐ c) Copiar otra idea",
                                   respuesta_correcta="b) Entrevistar y observar a usuarios.", justificacion="La validación empírica requiere contacto directo con clientes potenciales.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta=f"Explica con tus palabras qué problema resolvería tu propuesta de {topic} para los usuarios.",
                            respuesta_esperada="Respuesta posible: resolver necesidades de usuarios con soluciones prácticas, nutritivas y económicas.",
                            justificacion="Comprensión del bloque Problema."),
                ItemAbierto(numero=5, pregunta="Escribe dos preguntas abiertas que harías a posibles clientes en una entrevista de validación.",
                            respuesta_esperada="Ejemplos: ¿Qué compras en el recreo? ¿Qué cambiarías de tu lonchera?",
                            justificacion="Técnica de indagación cualitativa."),
                ItemAbierto(numero=6, pregunta="¿Por qué es importante mejorar el Lean Canvas después de escuchar a los usuarios?",
                            respuesta_esperada="Porque la evidencia permite corregir supuestos y tomar mejores decisiones.",
                            justificacion="Aprendizaje validado e iteración continua.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion="El Lean Canvas se completa una sola vez y nunca se modifica.", valor_esperado="F", justificacion="Es un lienzo dinámico e iterativo."),
                ItemVerdaderoFalso(numero=8, afirmacion="Un prototipo puede ser un dibujo, menú o versión sencilla del producto.", valor_esperado="V", justificacion="Representa la solución de forma rápida y de bajo costo."),
                ItemVerdaderoFalso(numero=9, afirmacion="Las métricas ayudan a comprobar si una propuesta funciona.", valor_esperado="V", justificacion="Evalúan el rendimiento y la tracción del proyecto."),
                ItemVerdaderoFalso(numero=10, afirmacion="La validación permite cambiar una idea cuando la evidencia no la apoya.", valor_esperado="V", justificacion="Permite pivotar evitando desperdicio de recursos.")
            ]

        # 2. Preset Canónico: La Célula (Ciencia y Tecnología)
        elif any(k in t_lower for k in ["célula", "celula", "organelo", "membrana celular"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="¿Cuál es la unidad básica de los seres vivos?",
                                   opciones=["El órgano", "La célula", "El tejido"],
                                   opciones_texto="☐ a) El órgano   ☐ b) La célula   ☐ c) El tejido",
                                   respuesta_correcta="b) La célula.", justificacion="La célula es la unidad morfológica y funcional de la vida."),
                ItemOpcionMultiple(numero=2, pregunta="¿Qué estructura contiene el material genético en una célula eucariota?",
                                   opciones=["El núcleo", "La vacuola", "La pared celular"],
                                   opciones_texto="☐ a) El núcleo   ☐ b) La vacuola   ☐ c) La pared celular",
                                   respuesta_correcta="a) El núcleo.", justificacion="El núcleo celular almacena el ADN en células eucariotas."),
                ItemOpcionMultiple(numero=3, pregunta="¿Qué organelo participa en la fotosíntesis?",
                                   opciones=["La mitocondria", "El cloroplasto", "La membrana"],
                                   opciones_texto="☐ a) La mitocondria   ☐ b) El cloroplasto   ☐ c) La membrana",
                                   respuesta_correcta="b) El cloroplasto.", justificacion="El cloroplasto contiene clorofila para captar energía luminosa.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta="Relaciona la membrana celular con una función de control.",
                            respuesta_esperada="Controla el ingreso y salida de sustancias.",
                            justificacion="Función de permeabilidad selectiva."),
                ItemAbierto(numero=5, pregunta="Menciona una diferencia entre una célula animal y una vegetal.",
                            respuesta_esperada="La vegetal puede tener pared celular, cloroplastos y gran vacuola; la animal no los presenta de la misma forma.",
                            justificacion="Diferenciación estructural de reinos biológicos."),
                ItemAbierto(numero=6, pregunta="Explica por qué una planta necesita cloroplastos para producir su alimento.",
                            respuesta_esperada="Los cloroplastos captan luz y permiten la fotosíntesis.",
                            justificacion="Metabolismo autótrofo.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion="Todas las células tienen exactamente la misma forma y función.", valor_esperado="F", justificacion="Las células se especializan según su tejido y función."),
                ItemVerdaderoFalso(numero=8, afirmacion="Las mitocondrias ayudan a obtener energía para las actividades celulares.", valor_esperado="V", justificacion="Sintetizan ATP mediante respiración celular."),
                ItemVerdaderoFalso(numero=9, afirmacion="La pared celular es una estructura característica de las células vegetales.", valor_esperado="V", justificacion="Otorga rigidez y soporte a los vegetales."),
                ItemVerdaderoFalso(numero=10, afirmacion="El núcleo coordina muchas actividades de la célula.", valor_esperado="V", justificacion="Regula la transcripción genética y procesos celulares.")
            ]

        # 3. Preset Canónico: DPCC (La pubertad y los cambios emocionales)
        elif any(k in t_lower for k in ["pubertad", "cambios emocionales", "asertiv", "emocion"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="La pubertad es:",
                                   opciones=["Una etapa de cambios diversos y graduales", "Una enfermedad", "Una experiencia igual para todas las personas"],
                                   opciones_texto="☐ a) Una etapa de cambios diversos y graduales   ☐ b) Una enfermedad   ☐ c) Una experiencia igual para todas las personas",
                                   respuesta_correcta="a) Etapa de cambios diversos y graduales.", justificacion="Es un proceso biológico y psicológico natural."),
                ItemOpcionMultiple(numero=2, pregunta="¿Cuál es una respuesta asertiva?",
                                   opciones=["Insultar", "Expresar lo que siento y pedir respeto", "Guardar silencio siempre"],
                                   opciones_texto="☐ a) Insultar   ☐ b) Expresar lo que siento y pedir respeto   ☐ c) Guardar silencio siempre",
                                   respuesta_correcta="b) Expresar lo que siento y pedir respeto.", justificacion="La asertividad comunica con firmeza y respeto."),
                ItemOpcionMultiple(numero=3, pregunta="Si una situación de acoso continúa, lo más adecuado es:",
                                   opciones=["Enfrentarla a solas siempre", "Buscar a una persona adulta de confianza", "Culpar a la víctima"],
                                   opciones_texto="☐ a) Enfrentarla a solas siempre   ☐ b) Buscar a una persona adulta de confianza   ☐ c) Culpar a la víctima",
                                   respuesta_correcta="b) Buscar apoyo adulto.", justificacion="Buscar apoyo institucional previene situaciones de riesgo.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta="Menciona dos cambios que pueden aparecer durante la pubertad.",
                            respuesta_esperada="Respuesta posible: cambios físicos (estirón, vello corporal), emocionales (cambios de humor) o sociales.",
                            justificacion="Autoconocimiento corporal y emocional."),
                ItemAbierto(numero=5, pregunta="Completa: “No me siento cómodo/a cuando ____________. Te pido que ____________”.",
                            respuesta_esperada="Respuesta asertiva en primera persona y con una petición respetuosa de límites.",
                            justificacion="Habilidades de comunicación asertiva."),
                ItemAbierto(numero=6, pregunta="Escribe dos estrategias para manejar una emoción intensa sin dañar a otras personas.",
                            respuesta_esperada="Respirar profundamente, hacer una pausa reflexiva, hablar con alguien de confianza o escribir lo que se siente.",
                            justificacion="Autorregulación emocional.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion="Todas las personas viven la pubertad al mismo tiempo y de la misma manera.", valor_esperado="F", justificacion="Cada organismo tiene su propio ritmo biológico."),
                ItemVerdaderoFalso(numero=8, afirmacion="Respetar los límites propios y ajenos es una forma de autocuidado.", valor_esperado="V", justificacion="Favorece relaciones interpersonales saludables."),
                ItemVerdaderoFalso(numero=9, afirmacion="Pedir ayuda ante el acoso es una decisión responsable.", valor_esperado="V", justificacion="Protege la integridad y activa redes de apoyo."),
                ItemVerdaderoFalso(numero=10, afirmacion="Las bromas sobre el cuerpo siempre son inofensivas.", valor_esperado="F", justificacion="Pueden constituir hostigamiento o vulnerar la autoestima.")
            ]

        # 4. Preset Canónico: Educación Física (Calentamiento e hidratación)
        elif any(k in t_lower for k in ["calentamiento", "hidratación", "hidratacion", "físico", "fisico", "deporte"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="¿Cuál es el propósito principal del calentamiento?",
                                   opciones=["Agotar el cuerpo", "Prepararlo progresivamente", "Reemplazar el ejercicio"],
                                   opciones_texto="☐ a) Agotar el cuerpo   ☐ b) Prepararlo progresivamente   ☐ c) Reemplazar el ejercicio",
                                   respuesta_correcta="b) Preparar el cuerpo progresivamente.", justificacion="Eleva la temperatura corporal y previene lesiones musculares."),
                ItemOpcionMultiple(numero=2, pregunta="Durante una actividad física es recomendable:",
                                   opciones=["Esperar a tener mucha sed", "Beber agua regularmente", "No hacer pausas"],
                                   opciones_texto="☐ a) Esperar a tener mucha sed   ☐ b) Beber agua regularmente   ☐ c) No hacer pausas",
                                   respuesta_correcta="b) Beber agua regularmente.", justificacion="Mantiene el balance hídrico y evita la deshidratación."),
                ItemOpcionMultiple(numero=3, pregunta="Si aparece mareo o dolor intenso se debe:",
                                   opciones=["Continuar a mayor velocidad", "Detenerse y avisar", "Ignorarlo"],
                                   opciones_texto="☐ a) Continuar a mayor velocidad   ☐ b) Detenerse y avisar   ☐ c) Ignorarlo",
                                   respuesta_correcta="b) Detenerse y avisar.", justificacion="Es una señal de alarma que exige detener el esfuerzo.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta="Ordena tres momentos de una rutina de calentamiento.",
                            respuesta_esperada="Movilidad articular, trote suave (activación cardiovascular) y estiramientos dinámicos específicos, en orden progresivo.",
                            justificacion="Estructura metodológica de la sesión deportiva."),
                ItemAbierto(numero=5, pregunta="Explica por qué la hidratación es importante durante el ejercicio.",
                            respuesta_esperada="Ayuda a regular la temperatura corporal, compensa las pérdidas por sudor y mantiene el rendimiento muscular.",
                            justificacion="Fisiología del esfuerzo físico."),
                ItemAbierto(numero=6, pregunta="Menciona dos señales corporales que indican que debes reducir la intensidad o detenerte.",
                            respuesta_esperada="Mareo, dolor torácico o muscular agudo, dificultad respiratoria severa o debilidad extrema.",
                            justificacion="Autocuidado y prevención de riesgos físicos.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion="El calentamiento debe aumentar la intensidad de manera progresiva.", valor_esperado="V", justificacion="Permite la adaptación paulatina de sistemas circulatorio y locomotor."),
                ItemVerdaderoFalso(numero=8, afirmacion="El dolor intenso debe ignorarse para demostrar esfuerzo.", valor_esperado="F", justificacion="El dolor agudo alerta sobre daño tisular o lesión."),
                ItemVerdaderoFalso(numero=9, afirmacion="El descanso y la hidratación forman parte del cuidado corporal.", valor_esperado="V", justificacion="Facilitan la recuperación homeostática."),
                ItemVerdaderoFalso(numero=10, afirmacion="La hidratación solo es necesaria después del ejercicio.", valor_esperado="F", justificacion="Debe ser antes, durante y después de la actividad física.")
            ]

        # 5. Preset Canónico: Arte y Cultura (El color y las técnicas de la pintura)
        elif any(k in t_lower for k in ["color", "pintura", "círculo cromático", "circulo cromatico", "técnica pictórica", "tecnica pictorica"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="¿Cuáles son colores primarios?",
                                   opciones=["Verde, naranja y violeta", "Amarillo, azul y rojo", "Blanco, negro y gris"],
                                   opciones_texto="☐ a) Verde, naranja y violeta   ☐ b) Amarillo, azul y rojo   ☐ c) Blanco, negro y gris",
                                   respuesta_correcta="b) Amarillo, azul y rojo.", justificacion="Son los colores pigmento base que no pueden obtenerse por mezcla."),
                ItemOpcionMultiple(numero=2, pregunta="Los colores complementarios se caracterizan por:",
                                   opciones=["Ser opuestos en el círculo cromático", "Ser siempre claros", "No producir contraste"],
                                   opciones_texto="☐ a) Ser opuestos en el círculo cromático   ☐ b) Ser siempre claros   ☐ c) No producir contraste",
                                   respuesta_correcta="a) Ser opuestos en el círculo cromático.", justificacion="Se ubican diametralmente opuestos y generan máximo contraste."),
                ItemOpcionMultiple(numero=3, pregunta="La acuarela suele producir:",
                                   opciones=["Transparencias", "Solo colores negros", "Texturas metálicas"],
                                   opciones_texto="☐ a) Transparencias   ☐ b) Solo colores negros   ☐ c) Texturas metálicas",
                                   respuesta_correcta="a) Transparencias.", justificacion="Se aplica diluida en agua aprovechando el blanco del papel.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta="Explica la diferencia entre armonía y contraste de color.",
                            respuesta_esperada="Armonía usa colores relacionados o análogos en el círculo cromático; contraste enfrenta colores opuestos o de intensidades muy distintas.",
                            justificacion="Teoría cromática y composición visual."),
                ItemAbierto(numero=5, pregunta="Elige una emoción y menciona dos colores que podrían comunicarla.",
                            respuesta_esperada="Respuesta justificada; por ejemplo, calma: azul y verde; alegría o energía: amarillo y naranja.",
                            justificacion="Psicología del color y lenguaje plástico."),
                ItemAbierto(numero=6, pregunta="Describe una técnica pictórica y un material que podrías usar.",
                            respuesta_esperada="Témpera sobre cartulina aplicando capas uniformes, o acuarela sobre papel de alto gramaje con degradados al agua.",
                            justificacion="Exploración técnica y material en artes plásticas.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion="Los colores cálidos pueden asociarse con energía o cercanía.", valor_esperado="V", justificacion="Generan sensaciones térmicas de calor y vitalidad."),
                ItemVerdaderoFalso(numero=8, afirmacion="El color no influye en el mensaje de una obra.", valor_esperado="F", justificacion="El color es un elemento comunicativo y expresivo fundamental."),
                ItemVerdaderoFalso(numero=9, afirmacion="Revisar una obra y recibir opiniones forma parte del proceso creativo.", valor_esperado="V", justificacion="El juicio crítico enriquece la producción artística."),
                ItemVerdaderoFalso(numero=10, afirmacion="Una obra puede usar el contraste para destacar un punto focal.", valor_esperado="V", justificacion="El contraste guía la mirada hacia el centro de interés.")
            ]

        # 6. Preset Canónico: Inglés (Simple Present: Daily Routines)
        elif any(k in t_lower for k in ["simple present", "daily routine", "routines"]):
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta="Choose the correct sentence:",
                                   opciones=["She study at seven.", "She studies at seven.", "She studying at seven."],
                                   opciones_texto="☐ a) She study at seven.   ☐ b) She studies at seven.   ☐ c) She studying at seven.",
                                   respuesta_correcta="b) She studies at seven.", justificacion="Third person singular takes -s/-es in Simple Present."),
                ItemOpcionMultiple(numero=2, pregunta="Choose the correct negative sentence:",
                                   opciones=["He don’t play.", "He doesn’t play.", "He not plays."],
                                   opciones_texto="☐ a) He don’t play.   ☐ b) He doesn’t play.   ☐ c) He not plays.",
                                   respuesta_correcta="b) He doesn’t play.", justificacion="Auxiliary 'doesn't' is used with he/she/it followed by base form."),
                ItemOpcionMultiple(numero=3, pregunta="Choose the correct question:",
                                   opciones=["Does she do homework?", "Does she does homework?", "Do she does homework?"],
                                   opciones_texto="☐ a) Does she do homework?   ☐ b) Does she does homework?   ☐ c) Do she does homework?",
                                   respuesta_correcta="a) Does she do homework?", justificacion="Auxiliary 'does' requires the main verb in base form.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta="Write two sentences about your daily routine in the Simple Present.",
                            respuesta_esperada="Answers may vary; correct subject–verb agreement required (e.g., 'I wake up at 6:30 a.m. and I eat breakfast.').",
                            justificacion="Grammar competence and personal expression."),
                ItemAbierto(numero=5, pregunta="Transform “I watch TV at night” into a negative sentence.",
                            respuesta_esperada="I don’t watch TV at night.",
                            justificacion="Use of negative auxiliary 'don't' with first person."),
                ItemAbierto(numero=6, pregunta="Write one question about a partner’s routine.",
                            respuesta_esperada="Example: Do you study in the afternoon? / What time do you wake up?",
                            justificacion="Interrogative structure in Simple Present.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion="With he, she or it, the verb usually takes -s or -es in affirmative sentences.", valor_esperado="V", justificacion="Standard rule for 3rd person singular in Simple Present."),
                ItemVerdaderoFalso(numero=8, afirmacion="After does or doesn’t, the main verb keeps the -s.", valor_esperado="F", justificacion="The main verb always reverts to base form after does/doesn't."),
                ItemVerdaderoFalso(numero=9, afirmacion="First, then and finally help organize a routine.", valor_esperado="V", justificacion="They are sequence connectors used in chronological texts."),
                ItemVerdaderoFalso(numero=10, afirmacion="We use the Simple Present to talk about routines.", valor_esperado="V", justificacion="Primary communicative function of Simple Present.")
            ]

        # 7. Fallback Universal para CUALQUIER otra área
        else:
            sec_a = [
                ItemOpcionMultiple(numero=1, pregunta=f"¿Cuál es el propósito o concepto central al estudiar {topic}?",
                                   opciones=[f"Comprender y aplicar los principios fundamentales de {topic}",
                                             f"Memorizar términos sin vincularlos a la práctica",
                                             f"Omitir el análisis para resolver al azar"],
                                   opciones_texto=f"☐ a) Comprender y aplicar los principios fundamentales de {topic}   ☐ b) Memorizar términos sin vincularlos   ☐ c) Omitir el análisis",
                                   respuesta_correcta=f"a) Comprender y aplicar los principios fundamentales de {topic}.",
                                   justificacion=f"El dominio conceptual de {topic} orienta la resolución fundamentada."),
                ItemOpcionMultiple(numero=2, pregunta=f"¿Qué elemento o parámetro técnico es indispensable al trabajar con {topic}?",
                                   opciones=[f"Criterios de verificación, orden y rigor metodológico",
                                             f"Suposiciones sin contrastar evidencia",
                                             f"Procedimientos improvisados sin registro"],
                                   opciones_texto=f"☐ a) Criterios de verificación y rigor metodológico   ☐ b) Suposiciones sin contrastar   ☐ c) Procedimientos improvisados",
                                   respuesta_correcta="a) Criterios de verificación y rigor metodológico.",
                                   justificacion=f"Garantiza validez y consistencia en {topic}."),
                ItemOpcionMultiple(numero=3, pregunta=f"¿Cuál de las siguientes acciones demuestra una aplicación correcta de {topic}?",
                                   opciones=[f"Analizar la situación, seleccionar una estrategia y validar el resultado",
                                             f"Copiar el procedimiento sin entender el contexto",
                                             f"Cambiar los datos arbitrariamente para simplificar"],
                                   opciones_texto=f"☐ a) Analizar, seleccionar estrategia y validar el resultado   ☐ b) Copiar sin entender   ☐ c) Cambiar datos arbitrariamente",
                                   respuesta_correcta="a) Analizar, seleccionar estrategia y validar el resultado.",
                                   justificacion="Alineado al enfoque por competencias del CNEB.")
            ]
            sec_b = [
                ItemAbierto(numero=4, pregunta=f"Explica con tus propias palabras la importancia de {topic} en el área de {area_display}.",
                            respuesta_esperada=f"Permite desarrollar pensamiento crítico, resolver problemas contextualizados y aplicar conceptos de {topic}.",
                            justificacion=f"Comprensión global del tema {topic}."),
                ItemAbierto(numero=5, pregunta=f"Describe un ejemplo o situación cotidiana en la que se aplique {topic}.",
                            respuesta_esperada=f"Respuesta contextualizada donde el estudiante relacione {topic} con situaciones de su entorno escolar, familiar o comunal.",
                            justificacion="Transferencia de aprendizajes a la vida real."),
                ItemAbierto(numero=6, pregunta=f"¿Cómo verificarías que una conclusión o respuesta sobre {topic} es correcta y confiable?",
                            respuesta_esperada="Contrastando con fuentes confiables, comprobando mediante operaciones inversas o revisando la coherencia lógica de los pasos.",
                            justificacion="Metacognición y autorregulación.")
            ]
            sec_c = [
                ItemVerdaderoFalso(numero=7, afirmacion=f"El estudio y aplicación de {topic} requiere identificar variables y datos con precisión.", valor_esperado="V", justificacion="El rigor analítico es esencial."),
                ItemVerdaderoFalso(numero=8, afirmacion=f"En {topic} todos los problemas tienen exactamente un único camino rígido de solución.", valor_esperado="F", justificacion="Existen diversas estrategias pedagógicas y heurísticas."),
                ItemVerdaderoFalso(numero=9, afirmacion=f"Verificar los resultados obtenidos permite corregir errores y afianzar aprendizajes en {topic}.", valor_esperado="V", justificacion="La evaluación formativa potencia el logro."),
                ItemVerdaderoFalso(numero=10, afirmacion=f"Los conocimientos sobre {topic} no guardan ninguna relación con la realidad cotidiana.", valor_esperado="F", justificacion="Todo aprendizaje significativo conecta con la realidad.")
            ]

    # Construcción unificada del Solucionario (10 filas)
    for q in sec_a:
        solucionario.append(ItemSolucionario(item=str(q.numero), respuesta_esperada=q.respuesta_correcta))
    for q in sec_b:
        solucionario.append(ItemSolucionario(item=str(q.numero), respuesta_esperada=q.respuesta_esperada))
    for q in sec_c:
        solucionario.append(ItemSolucionario(item=str(q.numero), respuesta_esperada=q.valor_esperado))

    return FichaExamenPracticaStructured(
        modo=modo,
        titulo_documento=titulo_doc,
        institucion="INSTITUCIÓN EDUCATIVA PÚBLICA CET N.° 34 – CHANCAY",
        area=area_display,
        grado=grade,
        grado_str=grade_str,
        seccion=seccion,
        tema=topic,
        fecha=fecha,
        docente=clean_teacher,
        indicaciones=indicaciones_text,
        seccion_a=sec_a,
        seccion_b=sec_b,
        seccion_c=sec_c,
        puntaje_por_pregunta=1,
        puntaje_total=10,
        puntaje_texto="Cada pregunta vale 1 punto (o 2 puntos según escala vigesimal). Total: 10 puntos.",
        orientacion_docente=orientacion_text,
        solucionario=solucionario
    )


def examen_practica_to_markdown(exam_obj: FichaExamenPracticaStructured, target: str = "teacher") -> str:
    """
    Serializa una FichaExamenPracticaStructured a Markdown ministerial oficial.
    En versión estudiante ('student'), excluye estrictamente el solucionario docente y claves.
    En el área de Matemática, renderiza exactamente 2 secciones (Marcar y Resolver).
    """
    is_student = (target.strip().lower() == "student")
    is_matematica = (exam_obj.area == "Matemática") or (len(exam_obj.seccion_c) == 0)

    md_lines = [
        f"# {exam_obj.institucion}",
        f"## {exam_obj.titulo_documento} – {exam_obj.grado_str}",
        f"**Área:** {exam_obj.area}  ",
        f"**Tema:** “{exam_obj.tema}”  ",
        f"**Estudiante:** _____________________________________ | **Grado y Sección:** {exam_obj.grado}.° “{exam_obj.seccion}” | **Fecha:** {exam_obj.fecha}  ",
        f"**Docente:** {exam_obj.docente}  ",
        "",
        f"> **{exam_obj.indicaciones}**",
        "",
        "---",
        "### A. Marca la alternativa correcta",
        ""
    ]

    for q in exam_obj.seccion_a:
        md_lines.append(f"**{q.numero}. {q.pregunta}**  ")
        md_lines.append(f"{q.opciones_texto}")
        md_lines.append("")

    md_lines.append("---")
    sec_b_title = "### B. Resuelve y muestra tu procedimiento" if is_matematica else "### B. Responde y explica"
    md_lines.append(sec_b_title)
    md_lines.append("")

    for q in exam_obj.seccion_b:
        md_lines.append(f"**{q.numero}. {q.pregunta}**  ")
        if is_matematica:
            md_lines.append("Espacio de procedimiento:  ")
            md_lines.append("________________________________________________________________________________  ")
            md_lines.append("________________________________________________________________________________  ")
            md_lines.append("**Respuesta final:** ________________________________________")
        else:
            md_lines.append("________________________________________________________________________________  ")
            md_lines.append("________________________________________________________________________________")
        md_lines.append("")

    if not is_matematica and len(exam_obj.seccion_c) > 0:
        md_lines.append("---")
        md_lines.append("### C. Verdadero (V) o falso (F)")
        md_lines.append("")

        for q in exam_obj.seccion_c:
            md_lines.append(f"**{q.numero}. {q.afirmacion}** &nbsp;&nbsp;&nbsp;&nbsp; `(   ) V    (   ) F`")
            md_lines.append("")

    if not is_student:
        md_lines.append("---")
        md_lines.append("### Puntaje sugerido")
        md_lines.append(f"{exam_obj.puntaje_texto}")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("### Clave de respuestas y orientaciones")
        md_lines.append(f"{exam_obj.orientacion_docente}")
        md_lines.append("")
        md_lines.append("| Ítem | Respuesta esperada |")
        md_lines.append("| :---: | :--- |")
        for s in exam_obj.solucionario:
            md_lines.append(f"| {s.item} | {s.respuesta_esperada} |")

    return "\\n".join(md_lines)
