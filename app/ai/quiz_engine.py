"""
INEI SMART-CORE - Formative Quiz & Practice Engine (SmartTutor AI)
Provides structured, CNEB-aligned and technical workshop formative quizzes.
Evaluates submissions exclusively on the server, calculates achievement levels,
and persists student practice history in SQLite.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from app.database.connection import get_db

logger = logging.getLogger("inei_smart_core.quiz_engine")

# Bank of Formative Quizzes by Specialty and General Subjects
QUIZ_QUESTION_BANK: Dict[str, List[Dict[str, Any]]] = {
    "electricidad": [
        {
            "id": "elec_01",
            "subject_id": "electricidad",
            "topic": "Ley de Ohm y Parámetros Eléctricos",
            "question": "¿Qué fórmula expresa la Ley de Ohm fundamental para un circuito de corriente continua?",
            "options": ["V = I × R", "I = V × R", "R = V × I", "P = V / R"],
            "correct_index": 0,
            "explanation": "La Ley de Ohm fundamental establece que el Voltaje (V) es directamente proporcional al producto de la Intensidad de corriente (I) y la Resistencia (R): V = I × R.",
            "cneb_competence": "Aplica procesos de diseño y cálculo en circuitos eléctricos.",
            "safety_tip": "Verifica siempre la ausencia de tensión antes de manipular conductores usando un multímetro calibrado."
        },
        {
            "id": "elec_02",
            "subject_id": "electricidad",
            "topic": "Sistemas Trifásicos y Conexión en Estrella",
            "question": "¿Qué relación existe entre la tensión de línea (VL) y la tensión de fase (VF) en una conexión estrella (Y)?",
            "options": ["VL = VF", "VL = √3 × VF (aprox. 1.732 × VF)", "VL = VF / √3", "VL = 3 × VF"],
            "correct_index": 1,
            "explanation": "En una conexión en estrella (Y), la tensión de línea es raíz de 3 (√3 ≈ 1.732) veces mayor que la tensión de fase (VL = √3 × VF). Por ejemplo, 220V fase / 380V línea.",
            "cneb_competence": "Opera máquinas y sistemas de distribución eléctrica trifásica.",
            "safety_tip": "Utiliza botas dieléctricas certificadas y guantes clase 0 para trabajos en tableros trifásicos."
        },
        {
            "id": "elec_03",
            "subject_id": "electricidad",
            "topic": "Código Nacional de Electricidad (CNE) y Puesta a Tierra",
            "question": "Según la norma técnica del CNE en Perú, ¿qué color de aislamiento corresponde al conductor de protección de puesta a tierra (PE)?",
            "options": ["Rojo o Negro", "Azul o Blanco", "Verde o Verde con franja Amarilla", "Marrón"],
            "correct_index": 2,
            "explanation": "El Código Nacional de Electricidad establece que el conductor de puesta a tierra de protección debe identificarse siempre con color verde o amarillo con rayas verdes.",
            "cneb_competence": "Cumple normas técnicas y de seguridad eléctrica institucional.",
            "safety_tip": "Nunca anules ni desconectes la línea a tierra de maquinaria de taller."
        },
        {
            "id": "elec_04",
            "subject_id": "electricidad",
            "topic": "Potencia Eléctrica y Factor de Potencia",
            "question": "¿Qué instrumento se utiliza en taller para medir simultáneamente la potencia activa (W) y el factor de potencia (cos φ)?",
            "options": ["Megóhmetro", "Vatímetro / Analizador de redes", "Telurómetro", "Amperímetro de gancho simple"],
            "correct_index": 1,
            "explanation": "El vatímetro o analizador de redes mide la potencia activa consumida (Watts) y permite calcular el factor de potencia del sistema.",
            "cneb_competence": "Aplica instrumentos de medición de precisión en tableros.",
            "safety_tip": "Conecta primero la bobina voltimétrica en paralelo y la amperimétrica en serie respetando la polaridad."
        }
    ],
    "automotores": [
        {
            "id": "auto_01",
            "subject_id": "automotores",
            "topic": "Ciclo Termodinámico Otto de 4 Tiempos",
            "question": "¿Cuál es la secuencia correcta de los 4 tiempos en un motor de combustión interna de ciclo Otto?",
            "options": [
                "Admisión - Escape - Compresión - Explosión",
                "Admisión - Compresión - Expansión/Combustión - Escape",
                "Compresión - Admisión - Escape - Expansión",
                "Escape - Admisión - Combustión - Compresión"
            ],
            "correct_index": 1,
            "explanation": "El ciclo Otto opera en 4 fases secuenciales: 1. Admisión (baja el pistón), 2. Compresión (sube el pistón), 3. Expansión/Combustión (fuerza motriz), 4. Escape (expulsión de gases quemados).",
            "cneb_competence": "Diagnostica y mantiene el motor de combustión interna.",
            "safety_tip": "Usa gafas de protección y guantes de nitrilo para evitar contacto con aceites y piezas calientes."
        },
        {
            "id": "auto_02",
            "subject_id": "automotores",
            "topic": "Inyección Electrónica y Sensores",
            "question": "¿Qué función primordial cumple el sensor MAF (Mass Air Flow) en el sistema de inyección electrónica?",
            "options": [
                "Mide la temperatura del refrigerante",
                "Mide la masa o flujo de aire que ingresa al múltiple de admisión",
                "Calcula la presión del aceite de lubricación",
                "Detecta la posición del árbol de levas"
            ],
            "correct_index": 1,
            "explanation": "El sensor MAF mide en tiempo real la masa de aire admitida por el motor para que la computadora (ECU) calcule la cantidad exacta de combustible a inyectar (mezcla estequiométrica 14.7:1).",
            "cneb_competence": "Verifica sensores y actuadores con escáner automotriz.",
            "safety_tip": "Desconecta la batería antes de intervenir arneses de la ECU para evitar cortocircuitos."
        },
        {
            "id": "auto_03",
            "subject_id": "automotores",
            "topic": "Sistema de Frenos Antibloqueo (ABS)",
            "question": "¿Cuál es el beneficio principal que aporta el sistema de frenos antibloqueo (ABS) en una frenada de emergencia?",
            "options": [
                "Bloquear las 4 ruedas inmediatamente para derrapar",
                "Evitar que las ruedas se bloqueen para mantener el control direccional del vehículo",
                "Apagar automáticamente el motor",
                "Aumentar la dureza del pedal de freno"
            ],
            "correct_index": 1,
            "explanation": "El ABS modula la presión hidráulica en cada rueda evitando su bloqueo, lo que permite al conductor mantener la maniobrabilidad direccional del volante durante frenadas bruscas.",
            "cneb_competence": "Realiza mantenimiento al sistema de frenos y seguridad activa.",
            "safety_tip": "Asegura el vehículo con caballetes mecánicos antes de ingresar debajo del chasis."
        },
        {
            "id": "auto_04",
            "subject_id": "automotores",
            "topic": "Sistema de Lubricación del Motor",
            "question": "¿Qué indica la nomenclatura '10W-40' en la viscosidad de un aceite de motor multigrado?",
            "options": [
                "10 litros de capacidad y 40 grados de temperatura",
                "Viscosidad 10 en frío (Winter) y viscosidad 40 a temperatura de trabajo (100°C)",
                "Presión de 10 PSI a 40 RPM",
                "Duración de 10 meses o 40 mil kilómetros"
            ],
            "correct_index": 1,
            "explanation": "La clasificación SAE '10W-40' indica un aceite multigrado con comportamiento fluido grado 10 en frío (W = Winter) y viscosidad grado 40 a temperatura de régimen de motor.",
            "cneb_competence": "Aplica fluidos y lubricantes según especificaciones del fabricante.",
            "safety_tip": "Dispón los aceites usados en contenedores rotulados de residuos peligrosos (5S)."
        }
    ],
    "mecanica_produccion": [
        {
            "id": "mec_01",
            "subject_id": "mecanica_produccion",
            "topic": "Mecanizado por Torneado y Velocidad de Corte",
            "question": "¿Qué fórmula se utiliza para calcular las RPM del husillo en un torno en función de la velocidad de corte (Vc en m/min) y el diámetro de la pieza (D en mm)?",
            "options": [
                "N = (Vc × 1000) / (π × D)",
                "N = (Vc × π) / (1000 × D)",
                "N = Vc × D × 1000",
                "N = (π × D) / Vc"
            ],
            "correct_index": 0,
            "explanation": "La fórmula de cálculo de RPM en torneado es N = (Vc × 1000) / (π × D), donde Vc es la velocidad de corte en metros por minuto y D es el diámetro en milímetros.",
            "cneb_competence": "Calcula parámetros de corte para mecanizado en máquinas herramientas.",
            "safety_tip": "NUNCA uses ropa suelta, corbatas, pulseras o cabello suelto al operar tornos o fresadoras."
        },
        {
            "id": "mec_02",
            "subject_id": "mecanica_produccion",
            "topic": "Soldadura por Arco Eléctrico (SMAW)",
            "question": "En la designación de electrodos AWS A5.1 'E6011', ¿qué indica el número '60'?",
            "options": [
                "Resistencia mínima a la tracción de 60,000 PSI",
                "Posición de soldadura sobrecabeza",
                "Tipo de corriente continua polaridad inversa",
                "60% de contenido de celulosa"
            ],
            "correct_index": 0,
            "explanation": "Los dos primeros dígitos (60) en la clasificación AWS indican la resistencia mínima a la tracción del metal depositado en miles de libras por pulgada cuadrada (60,000 PSI).",
            "cneb_competence": "Ejecuta uniones soldadas mediante proceso SMAW.",
            "safety_tip": "Usa careta de soldar con filtro de sombra adecuada (grado 10-12) y mandil de cuero cromo."
        },
        {
            "id": "mec_03",
            "subject_id": "mecanica_produccion",
            "topic": "Metrología Dimensional y Calibrador Vernier",
            "question": "Si un calibrador pie de rey tiene un nonio de 20 divisiones en 19 mm, ¿cuál es su apreciación o precisión mínima?",
            "options": ["0.1 mm", "0.05 mm (1/20 mm)", "0.02 mm", "0.01 mm"],
            "correct_index": 1,
            "explanation": "La apreciación de un nonio con 20 divisiones en 19 mm es 1 mm / 20 = 0.05 mm.",
            "cneb_competence": "Utiliza instrumentos de metrología dimensional de alta precisión.",
            "safety_tip": "Limpia las mordazas del calibrador con paño suave y guárdalo en su estuche al terminar (5S)."
        }
    ],
    "computacion": [
        {
            "id": "comp_01",
            "subject_id": "computacion",
            "topic": "Bases de Datos Relacionales y SQL",
            "question": "¿Qué comando SQL se utiliza para agregar un nuevo registro a una tabla relacional?",
            "options": ["ADD ROW TO table", "INSERT INTO table VALUES (...)", "UPDATE table SET (...)", "CREATE RECORD table"],
            "correct_index": 1,
            "explanation": "La instrucción estándar del lenguaje SQL para incorporar nuevas filas a una tabla es INSERT INTO nombre_tabla (columnas) VALUES (valores).",
            "cneb_competence": "Diseña y gestiona bases de datos relacionales normalizadas.",
            "safety_tip": "Mantén las áreas de cableado de red y servidores libres de polvo y humedad."
        },
        {
            "id": "comp_02",
            "subject_id": "computacion",
            "topic": "Redes de Datos y Direccionamiento IPv4",
            "question": "¿Cuál de las siguientes direcciones IPv4 corresponde a un rango de red privada según el estándar RFC 1918?",
            "options": ["192.168.1.50", "8.8.8.8", "200.48.225.130", "1.1.1.1"],
            "correct_index": 0,
            "explanation": "El rango 192.168.0.0/16 (junto con 10.0.0.0/8 y 172.16.0.0/12) está reservado para redes privadas de área local (LAN).",
            "cneb_competence": "Configura y administra redes de computadoras locales.",
            "safety_tip": "Usa pulsera antiestática al ensamblar placas madre y módulos de memoria RAM."
        }
    ],
    "contabilidad": [
        {
            "id": "cont_01",
            "subject_id": "contabilidad",
            "topic": "Principio de Partida Doble y Ecuación Contable",
            "question": "¿Cuál es la ecuación contable fundamental que rige el Balance General?",
            "options": [
                "Activo = Pasivo + Patrimonio",
                "Pasivo = Activo + Patrimonio",
                "Patrimonio = Pasivo + Activo",
                "Ingresos = Gastos - Costos"
            ],
            "correct_index": 0,
            "explanation": "La ecuación contable fundamental establece que el Activo (bienes y derechos) es igual al Pasivo (obligaciones con terceros) más el Patrimonio neto (capital propio).",
            "cneb_competence": "Elabora estados financieros y balances contables.",
            "safety_tip": "Asegura la confidencialidad y respaldo digital de los libros contables institucionales."
        }
    ],
    "matematica": [
        {
            "id": "mat_01",
            "subject_id": "matematica",
            "topic": "Ecuaciones Lineales y Despeje de Incógnitas",
            "question": "En la ecuación 3x + 12 = 36, ¿cuál es el valor exacto de la incógnita x?",
            "options": ["x = 6", "x = 8", "x = 10", "x = 4"],
            "correct_index": 1,
            "explanation": "Restando 12 a ambos lados: 3x = 36 - 12 = 24. Dividiendo entre 3: x = 24 / 3 = 8.",
            "cneb_competence": "Resuelve problemas de regularidad, equivalencia y cambio.",
            "safety_tip": "Verifica siempre tu respuesta sustituyendo el valor hallado en la ecuación inicial."
        },
        {
            "id": "mat_02",
            "subject_id": "matematica",
            "topic": "Geometría y Teorema de Pitágoras",
            "question": "En un triángulo rectángulo cuyos catetos miden a = 6 cm y b = 8 cm, ¿cuánto mide la hipotenusa (c)?",
            "options": ["10 cm", "14 cm", "12 cm", "9 cm"],
            "correct_index": 0,
            "explanation": "Por el Teorema de Pitágoras: c² = a² + b² = 6² + 8² = 36 + 64 = 100. Por tanto, c = √100 = 10 cm.",
            "cneb_competence": "Resuelve problemas de forma, movimiento y localización.",
            "safety_tip": "Utiliza escuadras y regla milimetrada para el trazado exacto de polígonos."
        }
    ],
    "comunicacion": [
        {
            "id": "com_01",
            "subject_id": "comunicacion",
            "topic": "Estructura del Ensayo Argumentativo",
            "question": "¿Cuáles son las tres partes estructurales fundamentales de un ensayo argumentativo según el CNEB?",
            "options": [
                "Introducción (Tesis) - Desarrollo (Argumentos) - Conclusión (Síntesis)",
                "Nudo - Desenlace - Moraleja",
                "Encabezado - Índice - Glosario",
                "Membrete - Cuerpo - Firma"
            ],
            "correct_index": 0,
            "explanation": "El ensayo argumentativo se compone de: 1. Introducción (planteamiento del tema y tesis), 2. Desarrollo (argumentación razonada y evidencias), 3. Conclusión (reiteración de la postura y síntesis final).",
            "cneb_competence": "Escribe diversos tipos de textos en su lengua materna.",
            "safety_tip": "Organiza tus ideas en esquemas previos antes de redactar la versión final."
        }
    ],
    "ciencia_tecnologia": [
        {
            "id": "cyt_01",
            "subject_id": "ciencia_tecnologia",
            "topic": "Leyes de Newton y Dinámica Clásica",
            "question": "La Segunda Ley de Newton establece que la fuerza neta aplicada sobre un cuerpo es igual a:",
            "options": [
                "F = m × a (Masa por aceleración)",
                "F = m / a",
                "F = v × t (Velocidad por tiempo)",
                "F = m × g × h"
            ],
            "correct_index": 0,
            "explanation": "La Segunda Ley de Newton cuantifica la dinámica fundamental: la Fuerza neta (en Newtons) es el producto de la masa inercial (kg) por la aceleración producida (m/s²): F = m × a.",
            "cneb_competence": "Explica el mundo físico basándose en conocimientos científicos.",
            "safety_tip": "En el laboratorio de ciencias, usa bata blanca y gafas de seguridad al manipular reactivos o masas en suspensión."
        }
    ]
}

# Generic fallback questions for any subject not specifically populated
GENERIC_SUBJECT_QUESTIONS = [
    {
        "id": "gen_01",
        "subject_id": "general",
        "topic": "Método de Estudio y Metacognición CNEB",
        "question": "¿Cuál es el primer paso recomendado para resolver un problema técnico o académico complejo?",
        "options": [
            "Comprender el problema e identificar los datos e incógnitas",
            "Escribir fórmulas al azar sin leer el enunciado",
            "Copiar el resultado del compañero",
            "Adivinar la respuesta más corta"
        ],
        "correct_index": 0,
        "explanation": "El primer paso del método de resolución de problemas (Polya / CNEB) es comprender a fondo el enunciado, distinguiendo claramente los datos conocidos de la meta o incógnita a resolver.",
        "cneb_competence": "Gestiona su aprendizaje de manera autónoma.",
        "safety_tip": "Mantén tu espacio de estudio ordenado y con buena iluminación."
    }
]

class QuizEngine:
    @classmethod
    def get_available_subjects(cls) -> List[Dict[str, Any]]:
        """Returns the list of subjects with available formative quizzes."""
        subjects = [
            {"id": "electricidad", "name": "Electricidad (Taller)", "category": "ESPECIALIDAD"},
            {"id": "automotores", "name": "Automotores (Taller)", "category": "ESPECIALIDAD"},
            {"id": "mecanica_produccion", "name": "Mecánica de Producción (Taller)", "category": "ESPECIALIDAD"},
            {"id": "computacion", "name": "Computación (Taller)", "category": "ESPECIALIDAD"},
            {"id": "contabilidad", "name": "Contabilidad (Taller)", "category": "ESPECIALIDAD"},
            {"id": "matematica", "name": "Matemática", "category": "CURSO GENERAL"},
            {"id": "comunicacion", "name": "Comunicación", "category": "CURSO GENERAL"},
            {"id": "ciencia_tecnologia", "name": "Ciencia y Tecnología", "category": "CURSO GENERAL"}
        ]
        return subjects

    @classmethod
    def get_quiz_for_subject(
        cls,
        subject_id: str,
        limit: int = 4,
        exclude_solutions: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieves formative quiz questions for a subject.
        CRITICAL SECURITY: When exclude_solutions=True, correct_index and explanation
        are STRICTLY REMOVED so students cannot inspect solutions in dev tools.
        """
        normalized_id = (subject_id or "electricidad").strip().lower()
        bank = QUIZ_QUESTION_BANK.get(normalized_id) or QUIZ_QUESTION_BANK.get("electricidad") or GENERIC_SUBJECT_QUESTIONS
        selected = bank[:limit]

        formatted = []
        for q in selected:
            item = {
                "id": q["id"],
                "subject_id": q["subject_id"],
                "topic": q.get("topic", "General"),
                "question": q["question"],
                "options": q["options"],
                "cneb_competence": q.get("cneb_competence", "Competencia del área."),
                "safety_tip": q.get("safety_tip")
            }
            if not exclude_solutions:
                item["correct_index"] = q["correct_index"]
                item["explanation"] = q["explanation"]

            formatted.append(item)

        return formatted

    @classmethod
    def evaluate_submission(
        cls,
        subject_id: str,
        answers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Server-side evaluation of student answers.
        Calculates exact score, CNEB achievement level (AD, A, B, C), and provides
        justified pedagogical explanations for every question.
        """
        normalized_id = (subject_id or "electricidad").strip().lower()
        bank = QUIZ_QUESTION_BANK.get(normalized_id) or QUIZ_QUESTION_BANK.get("electricidad") or GENERIC_SUBJECT_QUESTIONS
        q_map = {q["id"]: q for q in bank}

        total_questions = len(answers)
        if total_questions == 0:
            return {
                "success": False,
                "message": "No se enviaron respuestas para evaluar.",
                "total_questions": 0,
                "correct_answers": 0,
                "score_percentage": 0.0,
                "achievement_level": "C",
                "results": []
            }

        correct_count = 0
        results = []

        for ans in answers:
            q_id = ans.get("question_id")
            selected_opt = ans.get("selected_option")
            q_obj = q_map.get(q_id)

            if not q_obj:
                # Question not found in bank
                results.append({
                    "question_id": q_id,
                    "question": "Pregunta no encontrada",
                    "selected_option": selected_opt,
                    "correct_option": -1,
                    "is_correct": False,
                    "explanation": "No se encontró la pregunta en el banco oficial.",
                    "topic": "Desconocido"
                })
                continue

            correct_opt = q_obj["correct_index"]
            is_correct = (selected_opt == correct_opt)
            if is_correct:
                correct_count += 1

            results.append({
                "question_id": q_id,
                "question": q_obj["question"],
                "options": q_obj["options"],
                "selected_option": selected_opt,
                "correct_option": correct_opt,
                "is_correct": is_correct,
                "explanation": q_obj["explanation"],
                "topic": q_obj.get("topic", "General"),
                "cneb_competence": q_obj.get("cneb_competence", ""),
                "safety_tip": q_obj.get("safety_tip")
            })

        score_percentage = round((correct_count / total_questions) * 100, 1)

        # CNEB Achievement Levels
        if score_percentage >= 90.0:
            achievement_level = "AD"  # Logro Destacado
            feedback_msg = "¡Excelente trabajo! Has demostrado dominio destacado de las competencias evaluadas."
        elif score_percentage >= 70.0:
            achievement_level = "A"   # Logro Esperado
            feedback_msg = "¡Muy bien! Has alcanzado el nivel de logro esperado para esta unidad."
        elif score_percentage >= 50.0:
            achievement_level = "B"   # En Proceso
            feedback_msg = "Buen intento. Estás en proceso; te recomendamos repasar los temas señalados con SmartTutor AI."
        else:
            achievement_level = "C"   # En Inicio
            feedback_msg = "Nivel en inicio. Consulta el modo 'Paso a Paso' con SmartTutor AI para reforzar los conceptos clave."

        return {
            "success": True,
            "subject_id": normalized_id,
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "incorrect_answers": total_questions - correct_count,
            "score_percentage": score_percentage,
            "achievement_level": achievement_level,
            "feedback_message": feedback_msg,
            "results": results
        }

    @classmethod
    def record_attempt(
        cls,
        user_id: int,
        subject_id: str,
        total_q: int,
        correct_q: int,
        score_pct: float,
        achievement_lvl: str,
        details: List[Dict[str, Any]]
    ) -> int:
        """Persists the quiz attempt in SQLite smarttutor_quiz_attempts table."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO smarttutor_quiz_attempts (
                    user_id, subject_id, total_questions, correct_answers, 
                    score_percentage, achievement_level, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    subject_id,
                    total_q,
                    correct_q,
                    score_pct,
                    achievement_lvl,
                    json.dumps(details, ensure_ascii=False)
                )
            )
            return cursor.lastrowid

    @classmethod
    def get_student_progress(cls, user_id: int) -> Dict[str, Any]:
        """
        Retrieves personalized quiz history and stats for the authenticated student.
        Strictly isolates data by user_id.
        """
        with get_db() as conn:
            # Summary totals
            summary = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_attempts,
                    AVG(score_percentage) as average_score,
                    MAX(score_percentage) as max_score
                FROM smarttutor_quiz_attempts
                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

            total_attempts = summary["total_attempts"] if summary else 0
            avg_score = round(summary["average_score"], 1) if (summary and summary["average_score"] is not None) else 0.0
            max_score = round(summary["max_score"], 1) if (summary and summary["max_score"] is not None) else 0.0

            # Subject breakdown
            rows_by_sub = conn.execute(
                """
                SELECT 
                    subject_id,
                    COUNT(*) as attempts_count,
                    AVG(score_percentage) as avg_score,
                    MAX(score_percentage) as best_score
                FROM smarttutor_quiz_attempts
                WHERE user_id = ?
                GROUP BY subject_id
                ORDER BY attempts_count DESC
                """,
                (user_id,)
            ).fetchall()

            subject_stats = []
            for r in rows_by_sub:
                subject_stats.append({
                    "subject_id": r["subject_id"],
                    "attempts_count": r["attempts_count"],
                    "avg_score": round(r["avg_score"], 1) if r["avg_score"] is not None else 0.0,
                    "best_score": round(r["best_score"], 1) if r["best_score"] is not None else 0.0
                })

            # Recent attempts
            recent_rows = conn.execute(
                """
                SELECT id, subject_id, total_questions, correct_answers, score_percentage, achievement_level, created_at
                FROM smarttutor_quiz_attempts
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 15
                """,
                (user_id,)
            ).fetchall()

            recent_attempts = [dict(r) for r in recent_rows]

            return {
                "user_id": user_id,
                "total_attempts": total_attempts,
                "average_score": avg_score,
                "max_score": max_score,
                "subject_stats": subject_stats,
                "recent_attempts": recent_attempts
            }


quiz_engine = QuizEngine()
