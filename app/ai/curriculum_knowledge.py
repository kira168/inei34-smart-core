"""
Módulo de Base de Conocimiento Curricular CNEB y Bachillerato / Preuniversitario.
Contiene la malla temática completa de 1.° a 5.° de secundaria para todas las áreas:
- DPCC (Desarrollo Personal, Ciudadanía y Cívica)
- Ciencias Sociales (Historia, Geografía, Economía)
- Educación para el Trabajo (EPT) (Design Thinking, Lean Canvas, Prototipado, Ofimática, Gestión)
- Educación Física
- Comunicación (Expresión oral, Comprensión lectora, Gramática/Ortografía, Producción escrita, Literatura)
- Arte y Cultura (Artes visuales, Música, Teatro, Danza)
- Inglés como Lengua Extranjera (A1, A2, B1, Cambridge)
- Matemática (Cantidad, Regularidad/Álgebra, Forma/Geometría/Trigonometría, Gestión de datos/Estadística)
- Ciencia y Tecnología (Biología, Química, Física, Tierra y Universo, Indagación científica)
- Educación Religiosa
Así como la estructura extendida para Colegios Privados y Preuniversitarios (Biología, Química, Física independientes; Aritmética, Álgebra, Geometría, Trigonometría; Filosofía, Psicología, Cívica; Bilingüismo B2/C1).

Soporta:
1. Coincidencia exacta y difusa de temas de la malla.
2. Inferencia inteligente para CUALQUIER tema nuevo o libre que ingrese el docente.
3. Asignación automática y pertinente de Área, Competencia Oficial CNEB, Capacidades, Criterios de Evaluación y Propósito Formativo.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

# Mapeo oficial de Competencias CNEB por Área
AREA_COMPETENCIAS_CNEB = {
    "Desarrollo Personal, Ciudadanía y Cívica": [
        "Construye su identidad",
        "Convive y participa democráticamente en la búsqueda del bien común"
    ],
    "Ciencias Sociales": [
        "Construye interpretaciones históricas",
        "Gestiona responsablemente el espacio y el ambiente",
        "Gestiona responsablemente los recursos económicos"
    ],
    "Educación para el Trabajo": [
        "Gestiona proyectos de emprendimiento económico o social"
    ],
    "Educación Física": [
        "Se desenvuelve de manera autónoma a través de su motricidad",
        "Asume una vida saludable",
        "Interactúa a través de sus habilidades sociomotrices"
    ],
    "Comunicación": [
        "Se comunica oralmente en su lengua materna",
        "Lee diversos tipos de textos escritos en su lengua materna",
        "Escribe diversos tipos de textos en su lengua materna"
    ],
    "Arte y Cultura": [
        "Aprecia de manera crítica manifestaciones artístico-culturales",
        "Crea proyectos desde los lenguajes artísticos"
    ],
    "Inglés": [
        "Se comunica oralmente en inglés como lengua extranjera",
        "Lee diversos tipos de textos en inglés como lengua extranjera",
        "Escribe diversos tipos de textos en inglés como lengua extranjera"
    ],
    "Matemática": [
        "Resuelve problemas de cantidad",
        "Resuelve problemas de regularidad, equivalencia y cambio",
        "Resuelve problemas de forma, movimiento y localización",
        "Resuelve problemas de gestión de datos e incertidumbre"
    ],
    "Ciencia y Tecnología": [
        "Indaga mediante métodos científicos para construir conocimientos",
        "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
        "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno"
    ],
    "Educación Religiosa": [
        "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente",
        "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida"
    ]
}

# Base de datos curricular exhaustiva de 1.° a 5.° de secundaria
CURRICULAR_SYLLABUS = {
    1: {
        "Desarrollo Personal, Ciudadanía y Cívica": [
            {
                "eje": "Identidad y cambios",
                "temas": ["Los cambios físicos, psicológicos y sociales en la pubertad y adolescencia", "La pubertad y la adolescencia", "Autoconocimiento y aceptación corporal"],
                "competencia": "Construye su identidad",
                "proposito": "Comprender y valorar los cambios físicos, psicológicos y sociales propios de la pubertad y adolescencia, reconociéndolos como parte natural de su desarrollo personal.",
                "criterio": "Explica los cambios que experimenta en su cuerpo y comportamiento, proponiendo pautas de autocuidado y respeto mutuo."
            },
            {
                "eje": "Emociones",
                "temas": ["Reconocimiento y estrategias básicas de autorregulación emocional", "Emociones básicas y estados de ánimo", "Manejo de la frustración y la ira"],
                "competencia": "Construye su identidad",
                "proposito": "Identificar las emociones propias y ajenas, aplicando técnicas sencillas de respiración y autorregulación para responder asertivamente.",
                "criterio": "Reconoce sus emociones y utiliza estrategias de autorregulación emocional en situaciones de conflicto cotidiano."
            },
            {
                "eje": "Cuidado personal",
                "temas": ["Estilos de vida saludables, prevención de riesgos comunes en la adolescencia y autocuidado", "Alimentación balanceada y hábitos de higiene", "Prevención de conductas de riesgo"],
                "competencia": "Construye su identidad",
                "proposito": "Reconocer la importancia de los estilos de vida saludables y las prácticas de autocuidado para prevenir situaciones de riesgo en la adolescencia.",
                "criterio": "Propone acciones concretas de autocuidado e higiene que favorecen su bienestar físico y emocional."
            },
            {
                "eje": "Convivencia en el aula",
                "temas": ["Normas de convivencia, resolución pacífica de conflictos cotidianos y empatía", "El diálogo como vía de resolución pacífica", "Construcción participativa de acuerdos"],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Promover una convivencia armoniosa en el aula mediante el cumplimiento de acuerdos y la resolución dialogada de desacuerdos.",
                "criterio": "Aplica normas de convivencia y propone alternativas pacíficas ante discrepancias entre compañeros de clase."
            },
            {
                "eje": "Derechos y deberes",
                "temas": ["Introducción a los Derechos Humanos y los Derechos del Niño y del Adolescente", "Convención sobre los Derechos del Niño", "Deberes en la familia y la comunidad"],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Analizar los derechos fundamentales del niño y del adolescente, reconociendo su vinculación con los deberes ciudadanos en la escuela y el hogar.",
                "criterio": "Distingue situaciones en las que se respetan o vulneran los derechos del adolescente y argumenta sobre su cumplimiento."
            },
            {
                "eje": "Cultura y Diversidad",
                "temas": ["La diversidad cultural en la familia y la escuela, y rechazo a la discriminación", "Tradiciones familiares y comunitarias", "Igualdad y no discriminación"],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Valorar la riqueza de la diversidad cultural de su entorno escolar y manifestar un rechazo fundamentado a todo tipo de discriminación.",
                "criterio": "Muestra respeto por las costumbres y procedencias de sus compañeros, rechazando estereotipos excluyentes."
            }
        ],
        "Ciencias Sociales": [
            {
                "eje": "Historia - Fuentes y tiempo",
                "temas": ["La ciencia histórica (fuentes y tiempo cronológico)", "Fuentes primarias y secundarias", "Líneas de tiempo y periodificación"],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Comprender la importancia de las fuentes históricas y el tiempo cronológico para reconstruir el pasado de la humanidad.",
                "criterio": "Clasifica fuentes históricas (materiales, escritas, orales) y ubica hechos en líneas de tiempo secuenciales."
            },
            {
                "eje": "Historia - Hominización",
                "temas": ["El proceso de hominización y la Revolución Neolítica", "Evolución humana del Paleolítico", "Surgimiento de la agricultura y la domesticación"],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Explicar las etapas del proceso de hominización y el impacto transformador de la Revolución Neolítica en la vida social y económica.",
                "criterio": "Identifica cambios y permanencias en los modos de vida del Paleolítico al Neolítico a partir del análisis de evidencias."
            },
            {
                "eje": "Historia - Civilizaciones antiguas",
                "temas": ["Grandes civilizaciones del Occidente y Oriente antiguo (Mesopotamia, Egipto)", "Aportes culturales de Mesopotamia", "El Antiguo Egipto y su organización"],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Analizar la organización social, política y los aportes culturales de las civilizaciones fluviales de Mesopotamia y Egipto.",
                "criterio": "Compara las características políticas, religiosas y arquitectónicas de Egipto y Mesopotamia reconociendo su legado."
            },
            {
                "eje": "Historia del Perú - Poblamiento y Preínca",
                "temas": ["El poblamiento de América y el Perú: el Periodo Lítico y Arcaico (Caral)", "Altas culturas preíncas clásicas: Chavín, Paracas, Nasca, Mochica", "Caral civilización más antigua de América"],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Explicar el poblamiento del territorio andino y el desarrollo de Caral y las culturas Chavín, Paracas, Nasca y Mochica.",
                "criterio": "Describe los logros arquitectónicos, textiles y cerámicos de las culturas preíncas tempranas y su adaptación geográfica."
            },
            {
                "eje": "Geografía",
                "temas": ["Elementos del espacio geográfico y lectura de mapas", "Las ecorregiones del Perú y las ocho regiones naturales (enfoque inicial)", "Nociones de vulnerabilidad y gestión de riesgos ante desastres en la localidad"],
                "competencia": "Gestiona responsablemente el espacio y el ambiente",
                "proposito": "Interpretar elementos cartográficos básicos y describir las características físicas y ecológicas de las regiones del Perú.",
                "criterio": "Utiliza escalas, coordenadas y leyendas en mapas geográficos y reconoce zonas de riesgo en su comunidad."
            },
            {
                "eje": "Economía",
                "temas": ["Las necesidades humanas, los bienes y los servicios", "Los agentes económicos: la familia como unidad consumidora y las empresas", "El ahorro familiar y el consumo responsable"],
                "competencia": "Gestiona responsablemente los recursos económicos",
                "proposito": "Reconocer cómo las familias y empresas toman decisiones económicas frente a la escasez de recursos y promover el consumo responsable.",
                "criterio": "Diferencia necesidades de deseos y elabora una propuesta sencilla de ahorro y presupuesto familiar."
            }
        ],
        "Educación para el Trabajo": [
            {
                "eje": "Emprendimiento inicial",
                "temas": ["Qué es ser emprendedor y ejemplos de proyectos sociales y económicos", "Cualidades del emprendedor", "Identificación de oportunidades locales"],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Comprender el concepto de emprendimiento y reconocer las cualidades creativas y perseverantes necesarias para diseñar proyectos con impacto.",
                "criterio": "Identifica problemas en su entorno y formula una idea de proyecto emprendedor que atiende una necesidad real."
            },
            {
                "eje": "Design Thinking - Empatizar, Definir, Idear",
                "temas": ["Metodología Design Thinking (Fases iniciales): Empatizar, Definir, Idear", "Técnicas de entrevista y observación en el entorno escolar", "Generación de lluvia de ideas creativas"],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Aplicar las fases de Empatizar, Definir e Idear del Design Thinking para identificar necesidades de los usuarios y plantear soluciones innovadoras.",
                "criterio": "Recoge información de usuarios mediante guías de entrevista y sintetiza el 'Punto de Vista' (POV) formulando la pregunta retadora."
            },
            {
                "eje": "Prototipado inicial",
                "temas": ["Prototipado básico: Creación de bocetos, dibujos y modelos sencillos en papel o cartón", "Bocetos y maquetas rápidas", "Representación gráfica de la solución"],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Materializar ideas de solución mediante bocetos, esquemas y maquetas tridimensionales en papel o cartón reciclado.",
                "criterio": "Elabora un prototipo inicial que comunica visualmente las características principales del producto o servicio."
            },
            {
                "eje": "Tecnologías digitales",
                "temas": ["Introducción al procesador de textos (Word) y hojas de cálculo básicas (Excel) aplicadas al proyecto", "Redacción de fichas técnicas en Word", "Tablas sencillas de costos en Excel"],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Utilizar procesadores de textos y hojas de cálculo básicas para documentar la propuesta y registrar presupuestos elementales.",
                "criterio": "Aplica formato de texto, tablas e imágenes en procesadores digitales para presentar el informe del proyecto."
            }
        ],
        "Educación Física": [
            {
                "eje": "Esquema corporal y salud",
                "temas": ["Reconocimiento de la frecuencia cardíaca y respiratoria en actividad", "Frecuencia cardíaca en reposo y ejercicio", "Toma de pulsaciones"],
                "competencia": "Asume una vida saludable",
                "proposito": "Aprender a medir y controlar la frecuencia cardíaca y respiratoria antes, durante y después del esfuerzo físico.",
                "criterio": "Registra sus pulsaciones y describe los cambios fisiológicos que experimenta su cuerpo durante la actividad motriz."
            },
            {
                "eje": "Higiene y nutrición",
                "temas": ["Prácticas de hidratación, alimentación saludable para la edad y hábitos de aseo post-ejercicio", "Hidratación antes, durante y después del ejercicio", "Higiene personal deportiva"],
                "competencia": "Asume una vida saludable",
                "proposito": "Adoptar hábitos de hidratación adecuada y aseo personal tras la práctica física para preservar la salud.",
                "criterio": "Explica la importancia de la hidratación y practica rutinas de higiene corporal después del ejercicio."
            },
            {
                "eje": "Habilidades motrices y deportes",
                "temas": ["Coordinación motriz fina y gruesa, equilibrio, agilidad y flexibilidad general", "Juegos tradicionales y cooperativos", "Fundamentos técnicos básicos del atletismo, minifútbol, minivóley y minibásquet"],
                "competencia": "Se desenvuelve de manera autónoma a través de su motricidad",
                "proposito": "Desarrollar habilidades motrices básicas y fundamentos de iniciación deportiva a través de juegos cooperativos y disciplinas colectivas.",
                "criterio": "Ejecuta patrones motores con fluidez, respetando las reglas de juego y mostrando espíritu de colaboración."
            },
            {
                "eje": "Expresión corporal",
                "temas": ["Actividades rítmicas individuales y en grupo empleando música regional", "Secuencias rítmicas y danzas escolares", "Expresión gestual y espacial"],
                "competencia": "Interactúa a través de sus habilidades sociomotrices",
                "proposito": "Expresar emociones y coordinar movimientos colectivos siguiendo ritmos musicales tradicionales de la región.",
                "criterio": "Crea y sincroniza secuencias de movimiento corporal al compás de la música junto a sus compañeros."
            }
        ],
        "Comunicación": [
            {
                "eje": "Expresión oral",
                "temas": ["La narración oral de anécdotas, el diálogo guiado y el uso de recursos no verbales (gestos, postura)", "Narración de anécdotas personales", "Recursos paralingüísticos y no verbales"],
                "competencia": "Se comunica oralmente en su lengua materna",
                "proposito": "Expresar anécdotas y experiencias cotidianas con entonación, volumen adecuado y uso pertinente de gestos y postura corporal.",
                "criterio": "Narra vivencias con secuencia lógica, claridad vocal y coherencia temporal evitando divagaciones."
            },
            {
                "eje": "Comprensión lectora",
                "temas": ["El texto narrativo (mitos, leyendas, cuentos) y el texto expositivo instructivo", "Identificación del tema, subtemas, idea principal y personajes", "Mitos y leyendas del Perú"],
                "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
                "proposito": "Identificar el tema central, subtemas e ideas principales en textos narrativos e instructivos de la tradición peruana y universal.",
                "criterio": "Distingue la información explícita de las inferencias y resume el sentido global de la lectura."
            },
            {
                "eje": "Gramática y Ortografía",
                "temas": ["El sustantivo, el adjetivo y el artículo", "Reglas generales de acentuación (agudas, graves, esdrújulas)", "Uso del punto y la coma"],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Aplicar con precisión las categorías gramaticales básicas, reglas de acentuación y signos de puntuación fundamentales en escritos breves.",
                "criterio": "Clasifica palabras según el acento prosódico y ortográfico y utiliza el punto y la coma para organizar oraciones."
            },
            {
                "eje": "Producción escrita y Literatura",
                "temas": ["Redacción de cuentos cortos, descripciones, y elaboración de organizadores visuales simples (mapas mentales)", "Introducción a los géneros literarios (narrativo, lírico, dramático) con relatos populares peruanos"],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Redactar relatos breves de estructura inicio-nudo-desenlace y reconocer las características de los tres géneros literarios clásicos.",
                "criterio": "Produce un cuento breve o mapa mental estructurado, revisando ortografía, coherencia y riqueza léxica."
            }
        ],
        "Arte y Cultura": [
            {
                "eje": "Artes visuales",
                "temas": ["El dibujo y la pintura usando elementos básicos: el punto, la línea, la forma y la teoría del color (colores primarios y secundarios)", "Círculo cromático y mezcla de colores", "Texturas visuales y táctiles"],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Explorar las posibilidades expresivas del punto, la línea, la forma y las combinaciones cromáticas primarias y secundarias.",
                "criterio": "Elabora una composición plástica aplicando armonía de color, equilibrio de formas y técnica de dibujo cuidada."
            },
            {
                "eje": "Música",
                "temas": ["Elementos de la música (ritmo, melodía), exploración sonora con objetos cotidianos e introducción al canto coral o instrumentos peruanos de percusión", "Instrumentos peruanos de percusión: cajón y maracas"],
                "competencia": "Aprecia de manera crítica manifestaciones artístico-culturales",
                "proposito": "Diferenciar el ritmo y la melodía e interpretar patrones rítmicos usando instrumentos de percusión o la voz en ensamble coral.",
                "criterio": "Reproduce secuencias rítmicas con precisión y describe las cualidades sonoras de instrumentos tradicionales peruanos."
            },
            {
                "eje": "Teatro y Danza",
                "temas": ["Teatro: Juegos de improvisación, expresión corporal y creación de títeres o máscaras sencillas", "Danza: Práctica de danzas folclóricas locales y regionales reconociendo su contexto e historia"],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Representar personajes a través del juego dramático o títeres y ejecutar pasos coreográficos de danzas tradicionales peruanas.",
                "criterio": "Participa en representaciones escénicas y danzas folclóricas expresando el trasfondo cultural y emotivo de la obra."
            }
        ],
        "Inglés": [
            {
                "eje": "Expresiones cotidianas y Vocabulario",
                "temas": ["Saludos, despedidas, presentaciones personales e información personal básica (edad, procedencia)", "Los miembros de la familia, el aula y útiles escolares, los números del 1 al 100, colores y adjetivos"],
                "competencia": "Se comunica oralmente en inglés como lengua extranjera",
                "proposito": "Intercambiar información personal básica, saludos y presentaciones en inglés con pronunciación clara y vocabulario cotidiano.",
                "criterio": "Formula y responde preguntas sobre nombre, edad, procedencia y miembros de la familia en diálogos guiados."
            },
            {
                "eje": "Gramática base",
                "temas": ["El verbo To Be (afirmativo, negativo e interrogativo)", "Adjetivos posesivos (my, your, his, her)", "El presente simple para rutinas diarias sencillas (I get up, I go to school)"],
                "competencia": "Escribe diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Construir oraciones afirmativas, negativas e interrogativas con el verbo To Be y describir rutinas diarias en presente simple.",
                "criterio": "Redacta un texto breve sobre su rutina escolar usando correctamente el verbo To Be y adjetivos posesivos."
            },
            {
                "eje": "Comprensión y redacción",
                "temas": ["Lectura de perfiles cortos y escritura de textos breves de presentación"],
                "competencia": "Lee diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Comprender textos breves de presentación personal y redactar su propio perfil personal en inglés.",
                "criterio": "Extrae datos específicos de un perfil en inglés y redacta un párrafo coherente sobre sí mismo."
            }
        ],
        "Matemática": [
            {
                "eje": "Resuelve problemas de cantidad",
                "temas": [
                    "El conjunto de los números enteros (Z): adición, sustracción, multiplicación y división",
                    "Fracciones y decimales: conceptos básicos y operaciones elementales",
                    "Razones y proporciones elementales",
                    "Operaciones con números enteros en situaciones cotidianas"
                ],
                "competencia": "Resuelve problemas de cantidad",
                "proposito": "Comprender el significado de los números enteros y sus operaciones, aplicándolos para resolver problemas de ganancias, pérdidas y variaciones térmicas.",
                "criterio": "Aplica la regla de signos y algoritmos de operaciones combinadas con números enteros y fracciones justificando sus pasos."
            },
            {
                "eje": "Resuelve problemas de regularidad, equivalencia y cambio",
                "temas": [
                    "Patrones aditivos y multiplicativos",
                    "Introducción a las expresiones algebraicas básicas",
                    "Ecuaciones lineales de primer grado con una incógnita de la forma x + a = b y ax = b",
                    "Lenguaje algebraico y despeje de incógnitas"
                ],
                "competencia": "Resuelve problemas de regularidad, equivalencia y cambio",
                "proposito": "Traducir enunciados verbales a expresiones algebraicas y resolver ecuaciones lineales de primer grado con una incógnita.",
                "criterio": "Plantea ecuaciones lineales a partir de situaciones problemáticas y comprueba el valor numérico de la solución obtenida."
            },
            {
                "eje": "Resuelve problemas de forma, movimiento y localización",
                "temas": [
                    "Ángulos, rectas paralelas y perpendiculares",
                    "Polígonos: clasificación de triángulos y cuadriláteros",
                    "Perímetro y área de figuras geométricas planas básicas (cuadrado, rectángulo, triángulo)"
                ],
                "competencia": "Resuelve problemas de forma, movimiento y localización",
                "proposito": "Clasificar ángulos y polígonos regulares y calcular el perímetro y área de triángulos y cuadriláteros en situaciones prácticas.",
                "criterio": "Emplea fórmulas y propiedades geométricas para hallar perímetros y áreas de superficies planas expresando unidades adecuadas."
            },
            {
                "eje": "Resuelve problemas de gestión de datos e incertidumbre",
                "temas": [
                    "Población, muestra y variables cualitativas y cuantitativas discretas",
                    "Tablas de frecuencias absolutas para datos no agrupados",
                    "Gráficos de barras y circulares"
                ],
                "competencia": "Resuelve problemas de gestión de datos e incertidumbre",
                "proposito": "Organizar datos cualitativos y cuantitativos discretos en tablas de frecuencias y representarlos mediante gráficos de barras y circulares.",
                "criterio": "Interpreta información presentada en gráficos estadísticos y sustenta conclusiones a partir de las frecuencias observadas."
            }
        ],
        "Ciencia y Tecnología": [
            {
                "eje": "Materia y Energía",
                "temas": [
                    "Propiedades generales y específicas de la materia",
                    "Estados de agregación y cambios de estado",
                    "Modelos atómicos básicos y estructura del átomo (protones, neutrones, electrones)"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Diferenciar las propiedades generales y específicas de la materia y explicar la estructura atómica y los cambios de estado según la energía cinética.",
                "criterio": "Relaciona los cambios de estado de la materia con la temperatura y representa la estructura de un átomo neutro."
            },
            {
                "eje": "Biología (Seres vivos)",
                "temas": [
                    "La célula como unidad de vida (estructura de la célula animal y vegetal)",
                    "Los niveles de organización biológica",
                    "Los cinco reinos de la naturaleza (clasificación general)"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Explicar las semejanzas y diferencias entre la célula animal y vegetal y describir los niveles de organización biológica desde la célula hasta el individuo.",
                "criterio": "Identifica las organelas celulares clave y justifica por qué la célula es la unidad fundamental de los seres vivos."
            },
            {
                "eje": "Tierra y Universo",
                "temas": [
                    "Estructura interna y externa de la Tierra (litosfera, hidrosfera, atmósfera)",
                    "El sistema solar y los movimientos de la Tierra (rotación y traslación)"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Analizar la estructura de las capas de la Tierra y las consecuencias de los movimientos de rotación y traslación en los ciclos de vida.",
                "criterio": "Explica cómo interactúan la litosfera, hidrosfera y atmósfera y argumenta el origen de las estaciones y el día/noche."
            },
            {
                "eje": "Método científico",
                "temas": [
                    "Pasos de la indagación científica aplicados a experimentos escolares sencillos (observación, hipótesis, experimentación y conclusiones)"
                ],
                "competencia": "Indaga mediante métodos científicos para construir conocimientos",
                "proposito": "Formular una pregunta de indagación, plantear una hipótesis y contrastarla mediante un experimento escolar controlando variables.",
                "criterio": "Registra datos cuantitativos y cualitativos de su experimento y formula conclusiones fundamentadas en evidencias empíricas."
            }
        ],
        "Educación Religiosa": [
            {
                "eje": "La Creación y la Biblia",
                "temas": [
                    "La Creación: El amor de Dios manifestado en la creación y la responsabilidad humana de cuidarla",
                    "La Biblia: Introducción a las Sagradas Escrituras (cómo se divide, búsqueda de citas bíblicas, el Antiguo Testamento)",
                    "Búsqueda de citas bíblicas y estructura del Antiguo Testamento"
                ],
                "competencia": "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente",
                "proposito": "Reconocer a Dios como creador de la vida y aprender a manejar la Biblia localizando libros, capítulos y versículos con facilidad.",
                "criterio": "Ubica citas bíblicas y propone acciones de cuidado ambiental y respeto a la creación desde su fe."
            },
            {
                "eje": "Historia de la salvación y Jesús",
                "temas": [
                    "Historia de la salvación: Los patriarcas (Abrahán, Moisés) y la promesa de un Salvador",
                    "La figura de Jesús: Nacimiento, infancia y los primeros años del ministerio de Jesús",
                    "Valores cristianos: La convivencia fraterna, el respeto mutuo, el amor a la familia y la solidaridad"
                ],
                "competencia": "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida",
                "proposito": "Conocer los hitos principales de la historia de la salvación y las enseñanzas de Jesús de Nazaret, asumiendo actitudes de fraternidad y servicio.",
                "criterio": "Explica el mensaje de amor y perdón de Jesús y demuestra actitudes solidarias en la convivencia escolar."
            }
        ]
    },
    2: {
        "Desarrollo Personal, Ciudadanía y Cívica": [
            {
                "eje": "Identidad y Autoestima",
                "temas": ["Fortalecimiento de la autoimagen, aceptación de los cambios corporales tardíos y manejo de la presión de grupo", "Autoestima y toma de decisiones frente a pares"],
                "competencia": "Construye su identidad",
                "proposito": "Consolidar una autoimagen positiva y desarrollar habilidades de resistencia asertiva frente a la presión de grupo.",
                "criterio": "Reconoce sus fortalezas y límites personales y toma decisiones autónomas frente a propuestas perjudiciales de pares."
            },
            {
                "eje": "Sexualidad y Género",
                "temas": ["Diferencia entre sexo y género, afectividad en la adolescencia y mitos comunes sobre la sexualidad", "Afectividad y respeto en las relaciones interpersonales"],
                "competencia": "Construye su identidad",
                "proposito": "Comprender la dimensión afectiva y biológica de la sexualidad, diferenciando sexo de género y desmitificando creencias erróneas.",
                "criterio": "Distingue conceptos de sexo y género y fundamenta la importancia del respeto en las relaciones de amistad y afecto."
            },
            {
                "eje": "Habilidades Sociales",
                "temas": ["Comunicación asertiva, empatía y técnicas básicas de negociación ante conflictos familiares o escolares", "Resolución de conflictos y mediación escolar"],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Ejercitar estilos de comunicación asertiva y técnicas de negociación pacífica para resolver desacuerdos en la familia y la escuela.",
                "criterio": "Aplica pasos de negociación y escucha activa para llegar a consensos ante un conflicto cotidiano."
            },
            {
                "eje": "Democracia y Estado",
                "temas": ["La estructura del Estado peruano (Poder Ejecutivo, Legislativo y Judicial) y el concepto de ciudadanía activa", "División de poderes del Estado", "Participación ciudadana en el Perú"],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Analizar la función de los tres poderes del Estado peruano y la importancia del ejercicio de una ciudadanía responsable e informada.",
                "criterio": "Explica las competencias del Ejecutivo, Legislativo y Judicial e identifica canales de participación ciudadana."
            },
            {
                "eje": "Cultura y Convivencia",
                "temas": ["Manifestaciones de la diversidad cultural, prejuicios y estereotipos sociales comunes en la comunidad"],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Identificar y cuestionar críticamente prejuicios y estereotipos culturales presentes en la vida comunitaria.",
                "criterio": "Argumenta contra estereotipos de género y discriminación cultural, promoviendo la integración escolar."
            }
        ],
        "Ciencias Sociales": [
            {
                "eje": "Historia - Edad Media",
                "temas": ["Fin de la Edad Antigua e inicios de la Edad Media en Europa (Imperio Carolingio, Feudalismo)", "El sistema feudal: señoríos y vasallaje", "La Iglesia en la Edad Media"],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Explicar la transición a la Edad Media, el surgimiento del Imperio Carolingio y el funcionamiento social y económico del régimen feudal.",
                "criterio": "Analiza las relaciones de vasallaje y el rol rector de la Iglesia medieval basándose en fuentes documentales."
            },
            {
                "eje": "Historia del Perú - Intermedio Tardío y Tahuantinsuyo",
                "temas": [
                    "Las grandes culturas del Intermedio Tardío en el Perú (Chimú, Chachapoyas, Lambayeque, Chincha)",
                    "El Tahuantinsuyo: Origen, expansión, organización política, social, económica y cosmovisión incaica",
                    "La llegada de los europeos a América y la caída del Tahuantinsuyo (conquista y resistencia)"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Analizar la organización recíproca y redistributiva del Tahuantinsuyo y comprender los factores que desencadenaron la caída del Imperio incaico.",
                "criterio": "Explica la reciprocidad y redistribución incaica y contrasta múltiples visiones sobre la captura de Atahualpa y la resistencia andina."
            },
            {
                "eje": "Geografía",
                "temas": [
                    "Las ocho regiones naturales del Perú y las 11 ecorregiones de Antonio Brack Egg (profundización)",
                    "Cuencas hidrográficas del Perú (Pacífico, Amazonas y Titicaca)",
                    "Población y migraciones: Causas y efectos en el espacio geográfico local y nacional"
                ],
                "competencia": "Gestiona responsablemente el espacio y el ambiente",
                "proposito": "Analizar las vertientes hidrográficas y las ecorregiones del Perú, evaluando el impacto de las migraciones en la configuración del territorio.",
                "criterio": "Describe las características hídricas de las cuencas del Perú y explica factores de atracción y expulsión migratoria."
            },
            {
                "eje": "Economía",
                "temas": [
                    "El mercado: Funcionamiento básico de la oferta y la demanda",
                    "El sistema financiero formal vs. informal",
                    "El rol del Estado en la economía y la importancia de los tributos (SUNAT)"
                ],
                "competencia": "Gestiona responsablemente los recursos económicos",
                "proposito": "Comprender la interacción de la oferta y la demanda en el mercado y reconocer la relevancia del pago de tributos para los servicios públicos.",
                "criterio": "Diferencia el crédito formal del informal y argumenta por qué la tributación permite financiar la educación y salud pública."
            }
        ],
        "Educación para el Trabajo": [
            {
                "eje": "Design Thinking - Mapa de Empatía y SCAMPER",
                "temas": [
                    "Metodología Design Thinking (Profundización): Definición y mapas de empatía para sintetizar información",
                    "Técnicas avanzadas de ideación: Aplicación de la técnica SCAMPER o Da Vinci para ideas de negocio"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Sintetizar hallazgos de usuarios en mapas de empatía y generar alternativas creativas de solución empleando la técnica SCAMPER.",
                "criterio": "Construye un mapa de empatía consistente y genera al menos 10 propuestas de mejora mediante preguntas SCAMPER."
            },
            {
                "eje": "Lean Canvas Inicial",
                "temas": [
                    "El Modelo de Negocio (Lean Canvas): Primeros bloques: Problema, Solución, Propuesta de valor única y Segmento de clientes",
                    "Lienzo Lean Canvas: Problema, Solución y Propuesta de Valor"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Estructurar los cuatro bloques iniciales del lienzo Lean Canvas formulando hipótesis medibles y centradas en el usuario.",
                "criterio": "Redacta hipótesis claras para el problema, solución, propuesta de valor y segmento de clientes en su lienzo de negocio."
            },
            {
                "eje": "Técnicas y Producción",
                "temas": [
                    "Elaboración del presupuesto del prototipo (costos directos e indirectos)",
                    "Nociones de marketing básico y canales de venta (físico y digital)"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Calcular costos directos e indirectos para estimar el precio unitario del prototipo y definir canales viables de comercialización.",
                "criterio": "Elabora una hoja de costos detallada separando materia prima de mano de obra y selecciona canales de venta adecuados."
            }
        ],
        "Educación Física": [
            {
                "eje": "Salud y Condición Física",
                "temas": [
                    "Medición de las capacidades físicas individuales (resistencia, fuerza, velocidad, flexibilidad)",
                    "Diseño de rutinas sencillas de activación corporal (calentamiento)"
                ],
                "competencia": "Asume una vida saludable",
                "proposito": "Evaluar la condición física personal mediante pruebas de aptitud y diseñar rutinas de calentamiento general y específico.",
                "criterio": "Aplica tests físicos para medir su flexibilidad y resistencia, estructurando una rutina de activación previa segura."
            },
            {
                "eje": "Nutrición y Deportes",
                "temas": [
                    "Relación entre el gasto calórico de la actividad física y la ingesta de alimentos nutritivos de la región",
                    "Reglamentos oficiales y fundamentos técnicos intermedios en fútbol, vóley, básquet o atletismo",
                    "Estrategias de juego cooperativo y liderazgo de equipos"
                ],
                "competencia": "Interactúa a través de sus habilidades sociomotrices",
                "proposito": "Aplicar fundamentos técnicos y tácticos en deportes colectivos respetando el reglamento y adoptando dietas equilibradas.",
                "criterio": "Demuestra dominio técnico en situaciones de juego real y colabora activamente en la estrategia de equipo."
            },
            {
                "eje": "Expresión Corporal",
                "temas": ["Creación de secuencias coreográficas combinando danzas tradicionales peruanas y ritmos modernos"],
                "competencia": "Se desenvuelve de manera autónoma a través de su motricidad",
                "proposito": "Diseñar y coordinar coreografías que integren pasos de danzas tradicionales y expresiones dancísticas juveniles.",
                "criterio": "Ejecuta figuras coreográficas con ritmo, expresividad y coordinación colectiva en presentaciones escolares."
            }
        ],
        "Comunicación": [
            {
                "eje": "Expresión Oral y Debate",
                "temas": [
                    "La técnica del debate guiado, la argumentación oral de puntos de vista y el uso de la voz (entonación, ritmo y volumen)"
                ],
                "competencia": "Se comunica oralmente en su lengua materna",
                "proposito": "Sustentar posturas con argumentos fundamentados en debates reglados, modulando adecuadamente la entonación y el volumen.",
                "criterio": "Defiende una tesis con argumentos lógicos, rebate objeciones con serenidad y respeta turnos de intervención."
            },
            {
                "eje": "Comprensión Lectora",
                "temas": [
                    "El texto argumentativo (artículos de opinión sencillos, editoriales) y textos continuos y discontinuos (infografías, afiches)",
                    "Identificación de falacias, intenciones del autor y opiniones sesgadas"
                ],
                "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
                "proposito": "Identificar tesis, argumentos y falacias en textos argumentativos e infografías, reconociendo el propósito comunicativo del autor.",
                "criterio": "Distingue hechos de opiniones y evalúa la validez de los argumentos presentados en artículos de opinión e infografías."
            },
            {
                "eje": "Gramática y Ortografía",
                "temas": [
                    "El pronombre, el verbo (conjugación y tiempos) y los adverbios",
                    "Uso de las reglas de tildación diacrítica, uso de las mayúsculas y grafías dudosas (B-V, C-S-Z, G-J)"
                ],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Aplicar la tildación diacrítica y normas ortográficas de grafías dudosas para asegurar la corrección de textos formales.",
                "criterio": "Utiliza adecuadamente tildes diacríticas (él/el, tú/tu, más/mas) y conjuga verbos en tiempos simples y compuestos sin errores."
            },
            {
                "eje": "Producción escrita y Literatura",
                "temas": [
                    "Redacción de cartas notariales o solicitudes, noticias y textos de opinión breves estructurados en párrafos",
                    "Poesía y lírica (métrica, rima, figuras literarias básicas como la metáfora y el símil) con enfoque en autores peruanos"
                ],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Redactar solicitudes formales y textos de opinión, y analizar figuras retóricas en poemas de autores peruanos representativos.",
                "criterio": "Redacta una solicitud con estructura formal completa e identifica metáforas, símiles y anáforas en textos poéticos."
            }
        ],
        "Arte y Cultura": [
            {
                "eje": "Artes visuales",
                "temas": [
                    "Técnicas de pintura avanzadas (témperas, acuarelas, pasteles), nociones de volumen, luces, sombras y perspectiva lineal"
                ],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Aplicar nociones de perspectiva con punto de fuga y claroscuro en pinturas con témperas o acuarelas para lograr sensación de profundidad.",
                "criterio": "Demuestra dominio en la degradación tonal, uso de luces y sombras y trazado de perspectiva en bodegones o paisajes."
            },
            {
                "eje": "Música",
                "temas": [
                    "Lectura musical con figuras básicas (redonda, blanca, negra, corchea), ensambles musicales con flauta, guitarra o cajón",
                    "Géneros de la música criolla y andina"
                ],
                "competencia": "Aprecia de manera crítica manifestaciones artístico-culturales",
                "proposito": "Leer figuras rítmicas en pentagrama o compases básicos e interpretar piezas instrumentales de música criolla y andina.",
                "criterio": "Interpreta melodías sencillas en flauta dulce o guitarra coordinando el compás con el ensamble del aula."
            },
            {
                "eje": "Teatro y Danza",
                "temas": [
                    "Creación de libretos breves, diseño de escenografía reciclada y representación de sketches teatrales",
                    "Danzas de carácter mestizo o colonial en el Perú (Marinera, Tondero, Huaylas) analizando su vestimenta e historia"
                ],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Escribir libretos breves de contenido social y ejecutar coreografías mestizas reconociendo su evolución histórica.",
                "criterio": "Actúa con expresividad gestual y vocal en escenas teatrales e interpreta pasos de Marinera o Huaylas con precisión."
            }
        ],
        "Inglés": [
            {
                "eje": "Expresiones y Vocabulario",
                "temas": [
                    "Describir la casa y las habitaciones, dar direcciones urbanas básicas, hablar de habilidades y talentos",
                    "Lugares de la ciudad, profesiones u oficios, comidas y bebidas, prendas de vestir y el clima"
                ],
                "competencia": "Se comunica oralmente en inglés como lengua extranjera",
                "proposito": "Describir ubicaciones urbanas, dar indicaciones de dirección y expresar habilidades personales en intercambios orales guiados.",
                "criterio": "Utiliza vocabulario de lugares de la ciudad y preposiciones de lugar para guiar a un turista a un destino determinado."
            },
            {
                "eje": "Gramática",
                "temas": [
                    "El uso de There is / There are y cuantificadores (some, any, much, many)",
                    "El verbo modal Can / Can't para habilidades",
                    "Introducción al Past Simple del verbo To Be (was / were) y verbos regulares comunes"
                ],
                "competencia": "Escribe diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Emplear There is/are, cuantificadores, el modal Can y el pasado simple de verbos regulares en descripciones y anécdotas.",
                "criterio": "Redacta oraciones en pasado simple con terminación -ed y utiliza correctamente was/were en contextos temporales."
            },
            {
                "eje": "Comprensión y redacción",
                "temas": [
                    "Lectura de recetas o descripciones de lugares turísticos, y redacción de correos electrónicos informales"
                ],
                "competencia": "Lee diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Comprender instrucciones de recetas y folletos turísticos en inglés, y redactar correos electrónicos informales a amigos.",
                "criterio": "Redacta un correo electrónico informal en inglés con apertura, cuerpo y despedida estándar siguiendo pautas ortográficas."
            }
        ],
        "Matemática": [
            {
                "eje": "Resuelve problemas de cantidad",
                "temas": [
                    "El conjunto de los números racionales (Q): Operaciones combinadas con fracciones y decimales",
                    "Potenciación y radicación con números enteros y racionales (propiedades básicas)",
                    "Proporcionalidad directa e inversa y regla de tres simple",
                    "Porcentajes aplicados al comercio (descuentos e incrementos sucesivos)"
                ],
                "competencia": "Resuelve problemas de cantidad",
                "proposito": "Resolver operaciones combinadas con números racionales y aplicar la proporcionalidad directa e inversa y porcentajes comerciales a la economía diaria.",
                "criterio": "Calcula aumentos y descuentos sucesivos justificando la diferencia con el descuento simple y resuelve reglas de tres correctamente."
            },
            {
                "eje": "Resuelve problemas de regularidad, equivalencia y cambio",
                "temas": [
                    "Polinomios: Grados, adición, sustracción y multiplicación de expresiones algebraicas",
                    "Sistemas de ecuaciones lineales con dos incógnitas (Métodos de reducción y sustitución)",
                    "Inecuaciones lineales de primer grado"
                ],
                "competencia": "Resuelve problemas de regularidad, equivalencia y cambio",
                "proposito": "Efectuar operaciones con polinomios algebraicos y resolver sistemas de ecuaciones lineales con dos incógnitas mediante métodos algebraicos.",
                "criterio": "Resuelve sistemas lineales 2x2 por sustitución o reducción comprobando algebraicamente el par ordenado solución."
            },
            {
                "eje": "Resuelve problemas de forma, movimiento y localización",
                "temas": [
                    "Propiedades de los triángulos (líneas notables: bisectriz, mediana, altura)",
                    "Teorema de Pitágoras y sus aplicaciones",
                    "Área y volumen de prismas rectos y cilindros"
                ],
                "competencia": "Resuelve problemas de forma, movimiento y localización",
                "proposito": "Aplicar el Teorema de Pitágoras y calcular el área lateral, total y volumen de prismas rectos y cilindros en problemas de empaque y construcción.",
                "criterio": "Calcula volúmenes y áreas de cilindros y prismas rectangulares aplicando unidades cúbicas y cuadradas con exactitud."
            },
            {
                "eje": "Resuelve problemas de gestión de datos e incertidumbre",
                "temas": [
                    "Variables cuantitativas continuas: Tablas de frecuencias con datos agrupados en intervalos",
                    "Medidas de tendencia central para datos no agrupados (Media, Mediana, Moda)",
                    "Gráficos estadísticos complejos: Histogramas y polígonos de frecuencia",
                    "Probabilidad teórica mediante la Ley de Laplace"
                ],
                "competencia": "Resuelve problemas de gestión de datos e incertidumbre",
                "proposito": "Elaborar tablas de frecuencias con datos agrupados, calcular la media, mediana y moda, y determinar probabilidades simples mediante la regla de Laplace.",
                "criterio": "Calcula medidas de tendencia central e interpreta la probabilidad teórica de un suceso expresándola en fracción y porcentaje."
            }
        ],
        "Ciencia y Tecnología": [
            {
                "eje": "Materia, Energía y Mecánica",
                "temas": [
                    "La Tabla Periódica moderna: Organización, grupos, periodos y propiedades de los elementos",
                    "Enlaces químicos (iónico y covalente) y compuestos químicos inorgánicos sencillos",
                    "Introducción a la cinemática: Movimiento Rectilíneo Uniforme (MRU)",
                    "Formas de energía, fuentes renovables y no renovables, y conservación de la energía"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Explicar la organización de la tabla periódica, predecir el tipo de enlace químico (iónico o covalente) y resolver problemas de MRU fundamentando la conservación de energía.",
                "criterio": "Diferencia enlaces iónicos de covalentes por transferencia o compartición de electrones y aplica la fórmula d = v*t en problemas físicos."
            },
            {
                "eje": "Biología (Funciones Vitales y Ecología)",
                "temas": [
                    "La nutrición celular (autótrofa y heterótrofa) y los procesos de fotosíntesis y respiración celular",
                    "Ecosistemas: Factores bióticos y abióticos, cadenas y redes tróficas",
                    "El impacto de la actividad humana en los ecosistemas y la pérdida de biodiversidad"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Analizar la transformación de energía en la fotosíntesis y respiración celular, describiendo el flujo de materia y energía en las redes tróficas.",
                "criterio": "Elabora esquemas comparativos entre fotosíntesis y respiración celular y evalúa consecuencias de la deforestación en redes tróficas."
            },
            {
                "eje": "Ciencias de la Tierra",
                "temas": [
                    "La dinámica interna de la Tierra: Tectónica de placas, sismos y vulcanismo en el Cinturón de Fuego del Pacífico",
                    "El ciclo del agua y el fenómeno de El Niño"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Explicar los procesos endógenos de la tectónica de placas que originan sismos y analizar las causas climáticas del fenómeno de El Niño.",
                "criterio": "Describe la colisión de placas tectónicas en el margen andino y relaciona anomalías de temperatura marina con El Niño costero."
            }
        ],
        "Educación Religiosa": [
            {
                "eje": "Nuevo Testamento y Sacramentos",
                "temas": [
                    "El Nuevo Testamento: Las primeras comunidades cristianas y las cartas de San Pablo",
                    "Los Sacramentos: Los sacramentos de iniciación cristiana (Bautismo, Confirmación y Eucaristía)",
                    "Las Parábolas y Milagros: Análisis del mensaje ético y espiritual de Jesús"
                ],
                "competencia": "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente",
                "proposito": "Analizar la vida de las primeras comunidades cristianas, el testimonio de San Pablo y el significado de los sacramentos de iniciación cristiana.",
                "criterio": "Explica el significado del Bautismo, Eucaristía y Confirmación e interpreta las enseñanzas morales de las parábolas evangélicas."
            },
            {
                "eje": "La Iglesia y Compromiso",
                "temas": [
                    "La Iglesia: Historia básica de la Iglesia, el rol del Papa, los obispos y los laicos",
                    "Compromiso Cristiano: Proyectos de proyección social o campañas solidarias organizadas desde el aula"
                ],
                "competencia": "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida",
                "proposito": "Comprender la misión de la Iglesia en el mundo contemporáneo y participar activamente en iniciativas solidarias con los más necesitados.",
                "criterio": "Diseña una campaña solidaria para apoyar a personas en situación de vulnerabilidad en su localidad."
            }
        ]
    },
    3: {
        "Desarrollo Personal, Ciudadanía y Cívica": [
            {
                "eje": "Identidad y Autonomía",
                "temas": ["Construcción de la historia personal, proyecto de vida inicial, autoconcepto y resiliencia frente a riesgos (adicciones, redes)", "Proyecto de vida y prevención de adicciones"],
                "competencia": "Construye su identidad",
                "proposito": "Formular metas iniciales para su proyecto de vida y evaluar críticamente los riesgos asociados al uso indebido de redes sociales y adicciones.",
                "criterio": "Diseña un plan de vida con metas académicas y personales a mediano plazo, identificando factores protectores."
            },
            {
                "eje": "Sexualidad y Relaciones",
                "temas": ["Enamoramiento, mitos del amor romántico, prevención de violencia de género, cyberbullying y toma de decisiones", "Prevención de relaciones tóxicas y ciberacoso"],
                "competencia": "Construye su identidad",
                "proposito": "Cuestionar mitos del amor romántico y reconocer señales de alerta ante situaciones de violencia de género o ciberacoso.",
                "criterio": "Identifica conductas de control o violencia en relaciones de pareja juvenil y propone pautas de ciberseguridad."
            },
            {
                "eje": "Cultura y Estado",
                "temas": [
                    "Mecanismos de inclusión y exclusión social, valoración de la identidad amazónica, andina y afroperuana",
                    "La Constitución Política del Perú, derechos fundamentales, órganos autónomos (RENIEC, ONPE, JNE) y participación"
                ],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Analizar los derechos constitucionales fundamentales y el rol de los organismos electorales y de fiscalización en la democracia peruana.",
                "criterio": "Explica la función de la ONPE, JNE y RENIEC en elecciones democráticas y valora el aporte cultural afroperuano e indígena."
            }
        ],
        "Ciencias Sociales": [
            {
                "eje": "Historia Universal",
                "temas": [
                    "Europa en los siglos XVII y XVIII: El Absolutismo, la Ilustración y la Revolución Francesa",
                    "Pensadores ilustrados y la Declaración de los Derechos del Hombre"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Analizar la crisis del Antiguo Régimen, los ideales de libertad e igualdad de la Ilustración y las consecuencias de la Revolución Francesa.",
                "criterio": "Contrasta el poder absolutista monárquico con las ideas ilustradas de Montesquieu, Rousseau y Voltaire."
            },
            {
                "eje": "Historia del Perú",
                "temas": [
                    "América colonial en el siglo XVIII: Reformas Borbónicas y rebeliones indígenas (Túpac Amaru II)",
                    "El proceso de Independencia del Perú y de Hispanoamérica: Corrientes libertadoras del Sur y del Norte",
                    "Inicios de la República en el Perú: El caudillismo militar y la delimitación de fronteras"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Explicar el impacto de las Reformas Borbónicas, la gesta emancipadora de San Martín y Bolívar y el caudillismo en los albores de la República.",
                "criterio": "Analiza las causas de la rebelión de Túpac Amaru II y evalúa las consecuencias políticas del primer militarismo en el Perú."
            },
            {
                "eje": "Geografía y Economía",
                "temas": [
                    "Las grandes regiones bioclimáticas del mundo y los ecosistemas globales",
                    "Desarrollo urbano y rural en el Perú: Centralismo, crecimiento demográfico y tugurización",
                    "Áreas Naturales Protegidas (ANP) del Perú: Parques, santuarios y reservas nacionales",
                    "El mercado global: Globalización económica, comercio internacional, TLC e inflación",
                    "El mercado laboral: Empleo formal, informalidad, derechos laborales y MYPES",
                    "Derechos del consumidor e instituciones reguladoras (INDECOPI)"
                ],
                "competencia": "Gestiona responsablemente el espacio y el ambiente",
                "proposito": "Evaluar los efectos del centralismo demográfico y la importancia de las ANP, comprendiendo las dinámicas del comercio exterior y los derechos laborales.",
                "criterio": "Explica el rol de las ANP en la conservación de la biodiversidad y describe las causas y consecuencias de la informalidad laboral."
            }
        ],
        "Educación para el Trabajo": [
            {
                "eje": "Design Thinking - Validación",
                "temas": [
                    "Prototipado interactivo: Creación de maquetas funcionales, esquemas digitales (wireframes) o dramatizaciones",
                    "Evaluar / Testear: Técnicas de malla receptora de información y entrevistas de validación de usuarios"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Diseñar prototipos interactivos o wireframes y testearlos con usuarios reales aplicando la malla receptora de información.",
                "criterio": "Aplica la malla receptora organizando cosas interesantes, críticas constructivas, preguntas y nuevas ideas recogidas de usuarios."
            },
            {
                "eje": "Lean Canvas Avanzado",
                "temas": [
                    "Modelo de Negocio Lean Canvas: Estructura de costos (costos fijos, variables) y flujos de ingresos (monetización)",
                    "Canales de distribución (canal físico, canal web) y métricas clave del proyecto",
                    "Principios de diseño ecoamigable y herramientas de marketing digital"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Estructurar los bloques financieros del Lean Canvas (costos fijos, variables, ingresos) y definir métricas clave de rendimiento.",
                "criterio": "Diferencia costos fijos de variables, calcula el punto de equilibrio elemental y establece estrategias para canal web o físico."
            }
        ],
        "Educación Física": [
            {
                "eje": "Acondicionamiento y Ergonomía",
                "temas": [
                    "Acondicionamiento Físico Autónomo: Planificación personal de rutinas de resistencia y fuerza con autocarga",
                    "Salud y Ergonomía: Consciencia postural durante el estudio, primeros auxilios básicos ante lesiones (esguinces, calambres)"
                ],
                "competencia": "Asume una vida saludable",
                "proposito": "Diseñar rutinas de entrenamiento físico autónomo con el propio peso corporal y aplicar protocolos elementales de primeros auxilios deportivos.",
                "criterio": "Ejecuta ejercicios de calistenia con técnica postural adecuada y describe el protocolo RICE ante un esguince."
            },
            {
                "eje": "Deportes y Danza",
                "temas": [
                    "Sistemas de juego y tácticas complejas en disciplinas colectivas (futsal, básquet, vóley, balonmano)",
                    "Roles de liderazgo, arbitraje básico y organización de torneos deportivos escolares",
                    "Danzas folclóricas de mayor exigencia motriz (danzas de luces, danzas guerreras o agrícolas)"
                ],
                "competencia": "Interactúa a través de sus habilidades sociomotrices",
                "proposito": "Implementar sistemas tácticos ofensivos y defensivos en deportes de conjunto y asumir roles de arbitraje y organización comunitaria.",
                "criterio": "Aplica reglas oficiales como juez de juego y ejecuta desplazamientos tácticos sincronizados en partidos escolares."
            }
        ],
        "Comunicación": [
            {
                "eje": "Expresión Oral y Oratoria",
                "temas": [
                    "La técnica del panel de discusión, el discurso argumentativo, técnicas de oratoria moderna y manejo del miedo escénico"
                ],
                "competencia": "Se comunica oralmente en su lengua materna",
                "proposito": "Participar en paneles de discusión sustentando tesis con evidencias estadísticas y testimoniales, controlando el miedo escénico.",
                "criterio": "Expone con fluidez, responde a interpelaciones con solvencia argumentativa y utiliza conectores de causa y contraste."
            },
            {
                "eje": "Comprensión Lectora y Gramática",
                "temas": [
                    "El ensayo literario y el artículo científico descriptivo: Macroestructura, microestructura, premisas y argumentos",
                    "La estructura de la oración compuesta (coordinadas y subordinadas iniciales)",
                    "Uso avanzado de la tildación (diacrítica, enfática, compuestas) y signos complejos (dos puntos, punto y coma)"
                ],
                "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
                "proposito": "Analizar la estructura lógica de ensayos y artículos científicos e identificar oraciones compuestas y tildación especial.",
                "criterio": "Diferencia proposiciones coordinadas de subordinadas y emplea correctamente el punto y coma en enumeraciones complejas."
            },
            {
                "eje": "Producción escrita y Literatura",
                "temas": [
                    "Planificación, redacción y edición de ensayos argumentativos, reseñas de libros y monografías escolares breves",
                    "El Clasicismo, Renacimiento, Romanticismo y Realismo europeo vinculados a la literatura colonial y emancipadora en el Perú"
                ],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Redactar un ensayo argumentativo con tesis clara, argumentos respaldados y conclusiones sólidas, contextualizando movimientos literarios clásicos.",
                "criterio": "Redacta un ensayo de 4 a 5 párrafos respetando la cohesión textual y analiza el influjo del Romanticismo en la literatura peruana."
            }
        ],
        "Arte y Cultura": [
            {
                "eje": "Artes visuales y Música",
                "temas": [
                    "Técnicas de grabado (xilografía o linografía escolar con materiales alternativos), el cómic e historieta (guión, viñetas, planos)",
                    "Lectura de partituras sencillas en clave de Sol, acordes básicos en guitarra, ukelele o teclado, y ensamble instrumental"
                ],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Diseñar historietas con planos cinematográficos y ejecutar acordes básicos en instrumentos melódicos o armónicos.",
                "criterio": "Construye una tira cómica con estructura narrativa coherente e interpreta círculos armónicos en guitarra o ukelele."
            },
            {
                "eje": "Teatro y Danza",
                "temas": [
                    "El drama y la tragedia, creación colectiva de obras basadas en problemáticas juveniles, diseño de vestuario y maquillaje",
                    "Exploración y ejecución de danzas afroperuanas e hispanoamericanas contemporáneas (carácter social y rítmico)"
                ],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Montar microobras teatrales sobre problemáticas juveniles e interpretar danzas afroperuanas valorando su origen festivo y de resistencia.",
                "criterio": "Construye diálogos dramáticos con carga emotiva y ejecuta el zapateo y movimientos rítmicos del festejo o landó."
            }
        ],
        "Inglés": [
            {
                "eje": "Comunicación y Vocabulario",
                "temas": [
                    "Hablar sobre experiencias pasadas, planes futuros confirmados, dar consejos de salud, describir apariencia física y reglas",
                    "Enfermedades y síntomas comunes, adjetivos de personalidad, tecnologías, medios de transporte y expresiones temporales"
                ],
                "competencia": "Se comunica oralmente en inglés como lengua extranjera",
                "proposito": "Describir eventos pasados, formular planes futuros y dar consejos de salud empleando vocabulario especializado y modal verbs.",
                "criterio": "Utiliza Should/Shouldn't para recomendar tratamientos médicos sencillos y describe metas a futuro con fluidez."
            },
            {
                "eje": "Gramática y Producción",
                "temas": [
                    "Past Simple con verbos irregulares comunes",
                    "Future Continuous / Present Continuous con valor de futuro (going to vs will)",
                    "Verbos modales básicos: Should / Shouldn't (consejos), Must / Mustn't (obligación)",
                    "Lectura de biografías cortas, noticias sencillas y redacción de historias breves en tiempo pasado"
                ],
                "competencia": "Escribe diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Redactar historias cortas en pasado utilizando verbos irregulares y contrastar el uso de 'will' frente a 'going to' para predicciones y planes.",
                "criterio": "Aplica correctamente formas verbales irregulares en pasado simple (went, saw, bought) y redacta una crónica breve en inglés."
            }
        ],
        "Matemática": [
            {
                "eje": "Resuelve problemas de cantidad",
                "temas": [
                    "El conjunto de los números reales (R): Operaciones, aproximaciones, errores y truncamiento",
                    "Notación exponencial y notación científica: Operaciones con cantidades extremadamente grandes o pequeñas",
                    "Modelos financieros: Interés simple e interés compuesto aplicado a préstamos y ahorros"
                ],
                "competencia": "Resuelve problemas de cantidad",
                "proposito": "Realizar cálculos con números reales en notación científica y modelar situaciones crediticias y de ahorro mediante fórmulas de interés simple y compuesto.",
                "criterio": "Calcula el monto final de un préstamo con interés compuesto justificando la fórmula M = C(1+r)^t y efectúa operaciones en notación científica."
            },
            {
                "eje": "Resuelve problemas de regularidad, equivalencia y cambio (Álgebra)",
                "temas": [
                    "Productos notables y factorización de polinomios (factor común, aspa simple)",
                    "Ecuaciones cuadráticas (de segundo grado): Resolución por aspa simple y fórmula general",
                    "Funciones reales: Función lineal, función afín y función cuadrática (dominio, rango y gráfica)"
                ],
                "competencia": "Resuelve problemas de regularidad, equivalencia y cambio",
                "proposito": "Factorizar expresiones algebraicas, resolver ecuaciones cuadráticas y graficar funciones lineales y cuadráticas determinando vértice y dominio/rango.",
                "criterio": "Halla las raíces de una ecuación cuadrática ax^2 + bx + c = 0 mediante la fórmula general e interpreta el discriminante."
            },
            {
                "eje": "Resuelve problemas de forma, movimiento y localización (Geometría y Trigonometría)",
                "temas": [
                    "Semejanza y congruencia de triángulos (Teorema de Tales)",
                    "Áreas y volúmenes de pirámides, conos y esferas",
                    "Introducción a la trigonometría: Razones trigonométricas en el triángulo rectángulo (seno, coseno, tangente)"
                ],
                "competencia": "Resuelve problemas de forma, movimiento y localización",
                "proposito": "Aplicar el Teorema de Tales en triángulos semejantes, calcular volúmenes de cuerpos cónicos/esféricos y resolver triángulos rectángulos usando razones trigonométricas.",
                "criterio": "Determina alturas inaccesibles aplicando seno, coseno o tangente en triángulos notables (30°-60°, 45°, 37°-53°)."
            },
            {
                "eje": "Resuelve problemas de gestión de datos e incertidumbre",
                "temas": [
                    "Medidas de tendencia central para datos agrupados (Media, Mediana, Moda)",
                    "Medidas de posición: Cuartiles, quintiles y percentiles",
                    "Espacio muestral y cálculo de probabilidad condicionada (nociones iniciales)"
                ],
                "competencia": "Resuelve problemas de gestión de datos e incertidumbre",
                "proposito": "Calcular la media, mediana y percentiles en distribuciones agrupadas en intervalos y determinar probabilidades en experimentos compuestos.",
                "criterio": "Interpreta el significado del percentil 50 y cuartil 3 en una distribución de ingresos o notas escolares."
            }
        ],
        "Ciencia y Tecnología": [
            {
                "eje": "Química Inorgánica y Mecánica",
                "temas": [
                    "Nomenclatura química inorgánica: Óxidos, hidróxidos y ácidos básicos",
                    "Reacciones químicas y su clasificación (síntesis, descomposición, combustión) y balance por tanteo",
                    "Cinemática y Dinámica: Movimiento Rectilíneo Uniforme Variado (MRUV) y las Tres Leyes de Newton"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Formular y nombrar óxidos e hidróxidos, balancear ecuaciones químicas sencillas y explicar el movimiento acelerado y las fuerzas según las Leyes de Newton.",
                "criterio": "Balancea ecuaciones químicas por el método de tanteo y calcula aceleración y distancia en problemas de MRUV aplicando F = m*a."
            },
            {
                "eje": "Biología (Genética y Coordinación)",
                "temas": [
                    "La base química de la herencia: Estructura del ADN y ARN, y las Leyes de Mendel",
                    "El sistema nervioso humano (central y periférico) y el sistema endocrino (glándulas y hormonas)",
                    "Mecanismos de defensa del organismo: El sistema inmunológico, vacunas y agentes patógenos (virus y bacterias)"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Explicar la transmisión de rasgos hereditarios según los postulados mendelianos y el funcionamiento integrado del sistema nervioso, endocrino e inmune.",
                "criterio": "Resuelve cruces monohíbridos aplicando cuadros de Punnett y fundamenta la acción de las vacunas en la generación de anticuerpos."
            },
            {
                "eje": "Ecología y Sostenibilidad",
                "temas": [
                    "Ciclos biogeoquímicos (Carbono, Nitrógeno, Fósforo) y su relación con el efecto invernadero"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Describir el recorrido de los elementos en los ciclos del carbono y nitrógeno y evaluar el impacto del incremento de gases de efecto invernadero.",
                "criterio": "Modela el ciclo del carbono y propone medidas sustentables para reducir la huella de carbono escolar."
            }
        ],
        "Educación Religiosa": [
            {
                "eje": "Jesucristo y Doctrina Social",
                "temas": [
                    "Jesucristo y su Mensaje: Las Bienaventuranzas como proyecto de vida y camino a la felicidad cristiana",
                    "Historia de la Iglesia y Concilios: El Concilio Vaticano II y los desafíos en el mundo moderno",
                    "Doctrina Social de la Iglesia (DSI): Principios éticos cristianos aplicados a la economía, el trabajo y la justicia",
                    "Cuidado del Medio Ambiente: Reflexión basada en la encíclica Laudato si’ (El cuidado de la casa común)"
                ],
                "competencia": "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida",
                "proposito": "Analizar las Bienaventuranzas como brújula moral y reflexionar sobre la Doctrina Social de la Iglesia y la encíclica Laudato si' en defensa de la justicia ecológica.",
                "criterio": "Propone acciones basadas en la encíclica Laudato si' para el cuidado de la casa común y la dignidad laboral."
            }
        ]
    },
    4: {
        "Desarrollo Personal, Ciudadanía y Cívica": [
            {
                "eje": "Identidad y Salud Mental",
                "temas": [
                    "Construcción de la personalidad, dilemas morales complejos, autoeficacia y consolidación del proyecto de vida",
                    "Prevención de trastornos alimenticios, manejo de la ansiedad, depresión y resiliencia"
                ],
                "competencia": "Construye su identidad",
                "proposito": "Analizar dilemas éticos complejos fundamentando decisiones en principios morales universales y diseñar estrategias para preservar la salud mental.",
                "criterio": "Resuelve dilemas éticos apelando a la autonomía moral y reconoce factores de riesgo ante la ansiedad y depresión adolescente."
            },
            {
                "eje": "Estado, Derecho y Democracia",
                "temas": [
                    "Análisis crítico de la exclusión, racismo, discriminación de género y valoración del patrimonio cultural inmaterial",
                    "El sistema interamericano de derechos humanos, gobernabilidad, institucionalidad, transparencia y lucha contra la corrupción"
                ],
                "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
                "proposito": "Evaluar la solidez institucional de la democracia peruana, los tratados interamericanos de derechos humanos y los mecanismos contra la corrupción pública.",
                "criterio": "Explica el rol de la CIDH y los órganos de control del Estado en la prevención y sanción de delitos de corrupción."
            }
        ],
        "Ciencias Sociales": [
            {
                "eje": "Historia Universal",
                "temas": [
                    "La segunda revolución industrial y el Imperialismo del siglo XIX",
                    "La Primera Guerra Mundial y la Revolución Rusa",
                    "La crisis de 1929, el Periodo de Entreguerras y el surgimiento de los totalitarismos (Fascismo, Nazismo)"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Explicar las tensiones imperialistas que provocaron la Primera Guerra Mundial, el colapso del zarismo en Rusia y el auge del fascismo y nazismo.",
                "criterio": "Compara las ideologías totalitarias de entreguerras y analiza el impacto de la Gran Depresión de 1929 en la economía global."
            },
            {
                "eje": "Historia del Perú",
                "temas": [
                    "El Perú en el siglo XIX: La Era del Guano, la Guerra con Chile y la Reconstrucción Nacional",
                    "El Perú a inicios del siglo XX: La República Aristocrática y el Oncenio de Leguía"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Analizar la bonanza falaz del guano, las causas y secuelas de la Guerra del Pacífico y las transformaciones modernizadoras durante el Oncenio de Leguía.",
                "criterio": "Evalúa críticamente la gestión económica del guano y contrasta los proyectos políticos de la República Aristocrática con el Oncenio."
            },
            {
                "eje": "Geografía y Economía",
                "temas": [
                    "Organización del espacio rural y urbano en América Latina y el mundo",
                    "El cambio climático global, la pérdida de glaciares andinos y los acuerdos ambientales internacionales (Acuerdo de París, COP)",
                    "Modelos económicos en el mundo (libre mercado, economía mixta, planificación centralizada)",
                    "El sistema tributario peruano, el presupuesto público nacional y la evasión fiscal",
                    "Políticas monetarias y fiscales (Banco Central de Reserva del Perú - BCRP)"
                ],
                "competencia": "Gestiona responsablemente los recursos económicos",
                "proposito": "Comprender el funcionamiento de las políticas monetarias del BCRP frente a la inflación y analizar los compromisos internacionales frente al cambio climático.",
                "criterio": "Explica cómo la tasa de interés de referencia del BCRP influye en el costo del crédito y la estabilidad monetaria nacional."
            }
        ],
        "Educación para el Trabajo": [
            {
                "eje": "Design Thinking y Lean Canvas Completo",
                "temas": [
                    "Fase de Testeo avanzada: Técnicas de co-diseño con usuarios y refinamiento de la propuesta de valor",
                    "Modelo de Negocio Lean Canvas Completo: Ventajas competitivas injustas, flujo de caja proyectado y punto de equilibrio",
                    "Introducción al desarrollo web básico o herramientas de gestión de proyectos (Trello, Notion)",
                    "Estrategias de Growth Hacking y uso avanzado de redes sociales comerciales"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Calcular con precisión el punto de equilibrio y flujo de caja de un emprendimiento y utilizar herramientas digitales de gestión ágil (Trello/Notion).",
                "criterio": "Determina el punto de equilibrio en unidades y soles y diseña un embudo de ventas en redes sociales para su prototipo validado."
            }
        ],
        "Educación Física": [
            {
                "eje": "Gestión y Nutrición",
                "temas": [
                    "Autoevaluación del rendimiento físico, diseño y ejecución autónoma de un plan de entrenamiento semanal personalizado",
                    "Cálculo del Índice de Masa Corporal (IMC) y tasa metabólica basal; elaboración de dietas equilibradas",
                    "Reglamentos oficiales avanzados y sistemas tácticos complejos en fútbol, básquet, vóley y atletismo",
                    "Organización, arbitraje y gestión de eventos deportivos comunitarios",
                    "Coreografías complejas basadas en fusiones dancísticas peruanas y contemporáneas"
                ],
                "competencia": "Asume una vida saludable",
                "proposito": "Calcular el IMC y la tasa metabólica personal para formular un plan nutricional acorde a su gasto calórico, gestionando torneos escolares.",
                "criterio": "Calcula su IMC y elabora una propuesta de entrenamiento semanal equilibrando volumen e intensidad de carga."
            }
        ],
        "Comunicación": [
            {
                "eje": "Expresión Oral y Lectura Crítica",
                "temas": [
                    "El discurso político, la argumentación académica, técnicas de debate competitivo (formato parlamentario) y manejo de la voz",
                    "El ensayo filosófico, artículos de opinión de coyuntura y textos científicos complejos: Evaluación de argumentos y sesgos"
                ],
                "competencia": "Se comunica oralmente en su lengua materna",
                "proposito": "Pronunciar discursos argumentativos persuasivos y evaluar la consistencia epistémica y sesgos ideológicos en ensayos filosóficos y científicos.",
                "criterio": "Detecta falacias ad hominem, de generalización indebida o apelación a la autoridad en discursos de debate competitivo."
            },
            {
                "eje": "Gramática y Producción",
                "temas": [
                    "La oración compuesta subordinada (sustantivas, adjetivas, adverbiales)",
                    "Vicios del lenguaje (anfibología, redundancia, queísmo) y puntuación en textos académicos",
                    "Redacción formal de artículos de opinión, monografías de investigación y cartas de motivación",
                    "Las vanguardias europeas y latinoamericanas, el Modernismo, el Indigenismo peruano (Vallejo, Arguedas) y el Boom Latinoamericano"
                ],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Redactar monografías académicas y artículos de opinión libres de vicios de dicción, analizando las obras cumbres de Vallejo, Arguedas y el Boom.",
                "criterio": "Construye oraciones subordinadas complejas con puntuación pulcra y redacta un ensayo sobre el indigenismo de José María Arguedas."
            }
        ],
        "Arte y Cultura": [
            {
                "eje": "Artes Visuales, Música y Teatro",
                "temas": [
                    "Técnicas de pintura al óleo o acrílica, iniciación a las artes digitales (ilustración digital, edición de fotos), pop art",
                    "Armonía musical elemental (escalas mayores y menores, círculos armónicos de acordes), apreciación de música clásica y jazz",
                    "El teatro del absurdo, teatro contemporáneo, dramaturgia (escritura de microobras) y dirección de escenas cortas",
                    "Creación coreográfica libre basada en problemáticas sociales actuales a través de danza contemporánea"
                ],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Experimentar con técnicas pictóricas contemporáneas o digitales y componer obras teatrales breves inspiradas en el teatro del absurdo.",
                "criterio": "Produce una pintura o ilustración digital aplicando cánones estéticos modernos y escribe el guion de una escena dramática original."
            }
        ],
        "Inglés": [
            {
                "eje": "Gramática y Comunicación (A2/B1)",
                "temas": [
                    "Hablar sobre hipótesis o situaciones imaginarias, describir planes futuros, expresar acuerdos y desacuerdos fundamentados",
                    "Carreras profesionales, medio ambiente, problemas globales, idioms comunes y vocabulario de tecnología avanzada",
                    "Present Perfect Simple con since, for, already, yet",
                    "First and Second Conditionals (If I study... / If I won the lottery...)",
                    "Voz pasiva en tiempo presente y pasado (Present and Past Passive)",
                    "Lectura de artículos periodísticos en inglés y redacción de ensayos de opinión cortos"
                ],
                "competencia": "Escribe diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Expresar situaciones hipotéticas con el segundo condicional, transformar oraciones a voz pasiva y redactar ensayos de opinión estructurados.",
                "criterio": "Aplica 'If + past simple, would + verb' para dilemas hipotéticos y redacta un ensayo de 150 palabras con introducción, argumentos y conclusión."
            }
        ],
        "Matemática": [
            {
                "eje": "Resuelve problemas de cantidad",
                "temas": [
                    "Números reales: Intervalos y operaciones complejas. Nociones elementales de números imaginarios",
                    "Magnitudes derivadas y sistemas de unidades aplicados a la ciencia",
                    "Matemática financiera avanzada: Tasas de interés nominal y efectiva (TNA y TEA), y amortización de deudas"
                ],
                "competencia": "Resuelve problemas de cantidad",
                "proposito": "Operar con intervalos reales y calcular cronogramas de pago financiero diferenciando tasa nominal (TNA) de tasa efectiva anual (TEA).",
                "criterio": "Calcula el costo financiero total de una deuda aplicando la TEA y efectúa operaciones de unión e intersección de intervalos reales."
            },
            {
                "eje": "Resuelve problemas de regularidad, equivalencia y cambio (Álgebra)",
                "temas": [
                    "Ecuaciones e inecuaciones con valor absoluto y racionales",
                    "Funciones reales: Función raíz cuadrada, función valor absoluto, dominio, rango, monotonía y gráficas",
                    "Progresiones aritméticas y geométricas avanzadas"
                ],
                "competencia": "Resuelve problemas de regularidad, equivalencia y cambio",
                "proposito": "Resolver inecuaciones con valor absoluto y racionales y graficar funciones con valor absoluto y raíz cuadrada hallando dominio y rango.",
                "criterio": "Resuelve inecuaciones fraccionarias por el método de puntos críticos y determina el dominio y rango de f(x) = sqrt(ax + b)."
            },
            {
                "eje": "Resuelve problemas de forma, movimiento y localización (Geometría y Trigonometría)",
                "temas": [
                    "Geometría del espacio: Propiedades de poliedros regulares y cuerpos de revolución",
                    "Trigonometría analítica: Razones en el círculo trigonométrico, identidades fundamentales y Ley de Senos y Cosenos",
                    "Introducción a la geometría analítica: La recta en el plano cartesiano (ecuación e inclinación)"
                ],
                "competencia": "Resuelve problemas de forma, movimiento y localización",
                "proposito": "Demostrar identidades trigonométricas fundamentales, resolver triángulos oblicuángulos con Ley de Cosenos y hallar la ecuación de la recta.",
                "criterio": "Aplica la Ley de Cosenos a^2 = b^2 + c^2 - 2bc*cos(A) en problemas topográficos y halla la pendiente y ecuación de una recta."
            },
            {
                "eje": "Resuelve problemas de gestión de datos e incertidumbre",
                "temas": [
                    "Medidas de dispersión: Varianza, desviación estándar y coeficiente de variación para datos agrupados",
                    "Análisis combinatorio: Permutaciones, combinaciones y variaciones",
                    "Probabilidad condicional y el Teorema de Bayes (introducción conceptual)"
                ],
                "competencia": "Resuelve problemas de gestión de datos e incertidumbre",
                "proposito": "Calcular la desviación estándar y el coeficiente de variación de muestras agrupadas y resolver problemas combinatorios de conteo.",
                "criterio": "Calcula varianza y desviación estándar para evaluar la homogeneidad de dos grupos y diferencia permutaciones de combinaciones."
            }
        ],
        "Ciencia y Tecnología": [
            {
                "eje": "Química Orgánica y Termodinámica",
                "temas": [
                    "Introducción a la química del carbono (hidrocarburos: alcanos, alquenos, alquinos y grupos funcionales)",
                    "Estequiometría: Leyes ponderales, cálculo de moles, masa molecular y reactivo limitante",
                    "Trabajo, potencia y energía mecánica. Principios de termodinámica básica (calor y temperatura)",
                    "Estática y fluidos: Presión hidrostática y el Principio de Arquímedes"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Nombrar cadenas de hidrocarburos según la IUPAC, resolver problemas estequiométricos determinando el reactivo limitante y aplicar el Principio de Arquímedes.",
                "criterio": "Calcula la masa de producto obtenida a partir del reactivo limitante y aplica el empuje hidrostático E = rho * g * V en problemas de flotabilidad."
            },
            {
                "eje": "Biología Celular y Evolución",
                "temas": [
                    "Biotecnología y bioética: Clonación, alimentos transgénicos y edición genética (CRISPR)",
                    "Teorías de la evolución del siglo XX (neodarwinismo) y la biodiversidad del Perú como recurso estratégico",
                    "Diseño e implementación de proyectos de indagación cuantitativa y cualitativa con control de variables"
                ],
                "competencia": "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno",
                "proposito": "Evaluar los alcances bioéticos de la edición genética CRISPR y el cultivo de transgénicos, argumentando la importancia de la conservación evolutiva.",
                "criterio": "Formula argumentos científicos y éticos sobre la biotecnología moderna y diseña una solución tecnológica experimental."
            }
        ],
        "Educación Religiosa": [
            {
                "eje": "Teología Moral y Magisterio",
                "temas": [
                    "Teología Moral: La conciencia moral, las virtudes teologales y cardinales frente a la sociedad de consumo",
                    "El Magisterio de la Iglesia: Estudio de encíclicas sociales clave (Fratelli tutti, Rerum novarum) sobre justicia",
                    "Libertad y Verdad: El concepto cristiano de libertad frente al relativismo moral contemporáneo",
                    "Ecumenismo: El diálogo interreligioso con las grandes religiones (Judaísmo, Islam, Budismo, Hinduismo)"
                ],
                "competencia": "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente",
                "proposito": "Analizar la encíclica Fratelli tutti sobre fraternidad universal y reflexionar sobre la libertad cristiana frente al consumismo y relativismo ético.",
                "criterio": "Argumenta la importancia del diálogo interreligioso y asume compromisos de caridad y justicia social en su comunidad."
            }
        ]
    },
    5: {
        "Desarrollo Personal, Ciudadanía y Cívica": [
            {
                "eje": "Proyecto de Vida y Ética",
                "temas": [
                    "Proyecto de Vida y Vocación: Consolidación de metas personales, profesionales y laborales; orientación vocacional y resiliencia",
                    "Ética y Bioética: Dilemas morales contemporáneos (eutanasia, manipulación genética, derechos reproductivos)",
                    "Sistema Democrático y Corrupción: Fortalecimiento institucional, fiscalización, transparencia y análisis de la corrupción",
                    "Convivencia de la Diversidad: Ciudadanía global, discriminación étnico-racial y equidad de género"
                ],
                "competencia": "Construye su identidad",
                "proposito": "Consolidar el proyecto de vida y orientación vocacional para la vida adulta, y debatir dilemas bioéticos contemporáneos con rigor filosófico.",
                "criterio": "Sustenta su plan vocacional profesional y formula argumentos fundamentados en bioética y derechos humanos."
            }
        ],
        "Ciencias Sociales": [
            {
                "eje": "Historia Universal",
                "temas": [
                    "La Segunda Guerra Mundial, el Holocausto y las consecuencias geopolíticas globales",
                    "La Guerra Fría, descolonización de Asia y África, y revoluciones en América Latina (Revolución Cubana)"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Analizar las causas y desenlace de la Segunda Guerra Mundial, el exterminio del Holocausto y la polarización este-oeste en la Guerra Fría.",
                "criterio": "Evalúa el impacto de la bipolaridad nuclear durante la Guerra Fría y analiza la descolonización afroasiática a partir de fuentes primarias."
            },
            {
                "eje": "Historia del Perú Contemporáneo",
                "temas": [
                    "El Perú a mediados del siglo XX: El Odríismo, el Reformismo, el Gobierno Revolucionario de las FF.AA. (Reforma Agraria)",
                    "La crisis económica de los 80, el conflicto armado interno (Terrorismo y Violencia Política) y el informe de la CVR",
                    "El Perú en los 90 (Fujimorismo) y el proceso de transición democrática en el siglo XXI"
                ],
                "competencia": "Construye interpretaciones históricas",
                "proposito": "Analizar las causas estructurales del conflicto armado interno de 1980-2000, las conclusiones de la CVR y las reformas económicas de los años 90.",
                "criterio": "Examina críticamente las conclusiones de la Comisión de la Verdad y Reconciliación (CVR) y evalúa los costos y logros del retorno democrático."
            },
            {
                "eje": "Geografía y Finanzas Globales",
                "temas": [
                    "Organización política y administrativa del territorio peruano; fronteras y tratados internacionales",
                    "La Antártida como continente de paz y la importancia geopolítica de la cuenca del Pacífico",
                    "Políticas económicas internacionales, crisis financieras globales y mercados de valores",
                    "Educación financiera avanzada: Inversiones personales, pensiones (AFP/ONP), seguros y endeudamiento"
                ],
                "competencia": "Gestiona responsablemente los recursos económicos",
                "proposito": "Evaluar la posición geopolítica del Perú en el Pacífico y en la Antártida y comprender el funcionamiento de los sistemas previsionales (AFP/ONP) e inversión.",
                "criterio": "Compara las ventajas y riesgos de los fondos de pensiones y explica la importancia estratégica de la base científica Machu Picchu en la Antártida."
            }
        ],
        "Educación para el Trabajo": [
            {
                "eje": "Lean Canvas Escalable y Finanzas",
                "temas": [
                    "Validación final de todos los bloques en el mercado real mediante la venta de productos mínimos viables (PMV)",
                    "Métricas clave de retención y adquisición de clientes (CAC, LTV)",
                    "Gestión Financiera del Emprendimiento: Flujo de caja comercial, rentabilidad, Retorno de la Inversión (ROI) y régimen MYPE tributario",
                    "Inserción Laboral y Profesional: Diseño de Currículum Vitae moderno, LinkedIn, simulación de entrevistas laborales y elevator pitch"
                ],
                "competencia": "Gestiona proyectos de emprendimiento económico o social",
                "proposito": "Calcular el ROI y métricas comerciales de un PMV validado, redactar un CV profesional de impacto y presentar un elevator pitch convincente.",
                "criterio": "Calcula el Retorno de la Inversión (ROI = (Beneficio - Inversión) / Inversión) y sustenta su discurso de ventas en menos de 2 minutos."
            }
        ],
        "Educación Física": [
            {
                "eje": "Salud Ocupacional y Deportes",
                "temas": [
                    "Autogestión de planes de actividad física orientados a la salud ocupacional, control del estrés y condición física a largo plazo",
                    "Prevención de enfermedades crónicas no transmisibles (diabetes, hipertensión) y evaluación crítica de dietas de moda",
                    "Expresión táctica libre y adaptativa en deportes colectivos; planeamiento, ejecución y evaluación de festivales deportivos",
                    "Montajes coreográficos colectivos de gran envergadura combinando disciplinas corporales artísticas"
                ],
                "competencia": "Asume una vida saludable",
                "proposito": "Diseñar programas de pausas activas y salud ocupacional para prevenir el sedentarismo y liderar la organización de festivales deportivos escolares.",
                "criterio": "Elabora una guía de ergonomía y pausas activas para puestos de trabajo y asume la dirección técnica de una competencia escolar."
            }
        ],
        "Comunicación": [
            {
                "eje": "Oratoria Académica y Comprensión Crítica",
                "temas": [
                    "La sustentación oral de proyectos de investigación, conferencias, seminarios y debates formales argumentativos de alta competencia",
                    "Ensayos críticos de corte filosófico, político y sociológico, y artículos científicos indexados",
                    "Contraste de diversas posturas editoriales sobre un mismo hecho histórico o de coyuntura actual"
                ],
                "competencia": "Se comunica oralmente en su lengua materna",
                "proposito": "Sustentar rigurosamente una tesis académica ante un jurado simulado y contrastar líneas editoriales contrapuestas sobre temas de coyuntura nacional.",
                "criterio": "Demuestra solvencia en la defensa de su postura respondiendo a contraargumentos con fuentes académicas contrastadas."
            },
            {
                "eje": "Gramática y Producción de Ensayo",
                "temas": [
                    "Revisión de la sintaxis oracional, normas de citación y referencias bibliográficas académicas (Normas APA)",
                    "Redacción formal de un ensayo académico original y completo (tesis, argumentación, conclusiones) y de cartas académicas",
                    "Literatura contemporánea del siglo XX y XXI: Narrativa urbana en el Perú (Generación del 50 al presente), literatura universal actual"
                ],
                "competencia": "Escribe diversos tipos de textos en su lengua materna",
                "proposito": "Redactar un ensayo académico riguroso con citas textuales y parafraseadas según normas APA 7.ª edición, analizando la narrativa urbana peruana.",
                "criterio": "Aplica adecuadamente normas APA en citas parentéticas y bibliografía y redacta un ensayo de 5 páginas con cohesión y profundidad analítica."
            }
        ],
        "Arte y Cultura": [
            {
                "eje": "Medios Digitales y Producción",
                "temas": [
                    "El cine, el videoarte, el diseño multimedia, portafolios artísticos digitales y análisis crítico de imágenes en medios",
                    "Introducción al software de edición de audio, creación de composiciones musicales propias, ensambles de música fusionada",
                    "El teatro contemporáneo, puestas en escena completas dirigidas por los estudiantes y performance",
                    "Planificación de un proyecto cultural escolar o comunitario orientado a revalorar el patrimonio cultural regional"
                ],
                "competencia": "Crea proyectos desde los lenguajes artísticos",
                "proposito": "Editar un cortometraje o pieza multimedia que visibilice el patrimonio cultural de Chancay y producir una puesta en escena teatral comunitaria.",
                "criterio": "Utiliza recursos de montaje audiovisual digital y dirige una escena teatral colectiva con propuesta escenográfica fundamentada."
            }
        ],
        "Inglés": [
            {
                "eje": "Competencia B1 Avanzada",
                "temas": [
                    "Expresar arrepentimientos sobre el pasado, predicciones a largo plazo sobre tecnología, debatir dilemas y quejas formales",
                    "Educación superior, mercado laboral, globalización, expresiones idiomáticas complejas (idioms y phrasal verbs)",
                    "Past Perfect Simple y Continuous",
                    "Third Conditional e hipótesis en el pasado (Wish / If only)",
                    "Discurso indirecto (Reported Speech) para reportar lo dicho por otros",
                    "Comprensión de textos extensos de opinión y redacción de cartas de presentación laboral y ensayos formales"
                ],
                "competencia": "Escribe diversos tipos de textos en inglés como lengua extranjera",
                "proposito": "Utilizar el tercer condicional para hipótesis sobre el pasado, transformar diálogos a Reported Speech y redactar una carta de presentación laboral formal (Cover Letter).",
                "criterio": "Aplica correctamente 'If + had + past participle, would have + past participle' y redacta una Cover Letter en inglés con registro formal estricto."
            }
        ],
        "Matemática": [
            {
                "eje": "Resuelve problemas de cantidad",
                "temas": [
                    "El sistema de los números complejos (C): Concepto, forma binómica y operaciones elementales",
                    "Modelos financieros sofisticados: Cronogramas de pagos, amortizaciones con cuotas variables/fijas y evaluación de créditos"
                ],
                "competencia": "Resuelve problemas de cantidad",
                "proposito": "Operar con números complejos en forma binómica (adición, multiplicación y conjugado) y estructurar cronogramas de amortización de préstamos (método francés y alemán).",
                "criterio": "Efectúa operaciones en el plano complejo y calcula la cuota fija mensual de un crédito bancario aplicando la fórmula de anualidades."
            },
            {
                "eje": "Resuelve problemas de regularidad, equivalencia y cambio (Álgebra)",
                "temas": [
                    "Funciones elementales de variable real: Funciones exponenciales y logarítmicas (propiedades, dominio, rango y aplicaciones)",
                    "Programación lineal bidimensional: Planteamiento de inecuaciones lineales, región factible y optimización de funciones objetivo"
                ],
                "competencia": "Resuelve problemas de regularidad, equivalencia y cambio",
                "proposito": "Resolver ecuaciones exponenciales y logarítmicas y optimizar costos o ganancias evaluando los vértices de una región factible en programación lineal.",
                "criterio": "Halla el valor máximo o mínimo de una función objetivo Z = ax + by dentro del polígono de soluciones factibles acotado."
            },
            {
                "eje": "Resuelve problemas de forma, movimiento y localización (Trigonometría y Geometría Analítica)",
                "temas": [
                    "Secciones cónicas en el plano cartesiano: La circunferencia y la parábola (ecuaciones ordinarias y generales)",
                    "Trigonometría avanzada: Funciones trigonométricas (seno, coseno, tangente) e identidades de ángulos compuestos y dobles"
                ],
                "competencia": "Resuelve problemas de forma, movimiento y localización",
                "proposito": "Determinar centro y radio de circunferencias, vértice y foco de parábolas a partir de su ecuación general, y resolver identidades de ángulo doble.",
                "criterio": "Completa cuadrados para transformar la ecuación general de la parábola a su forma canónica y halla sus elementos principales."
            },
            {
                "eje": "Resuelve problemas de gestión de datos e incertidumbre",
                "temas": [
                    "Regresión lineal simple: Diagramas de dispersión, covarianza y recta de regresión (ajuste lineal óptimo)",
                    "Probabilidad: Teorema de la probabilidad total y cálculo avanzado con permutaciones y combinaciones con repetición"
                ],
                "competencia": "Resuelve problemas de gestión de datos e incertidumbre",
                "proposito": "Estimar tendencias mediante la ecuación de la recta de regresión lineal y resolver problemas probabilísticos aplicando el Teorema de la Probabilidad Total.",
                "criterio": "Calcula el coeficiente de correlación lineal r de Pearson e interpreta si existe correlación positiva, negativa o nula entre dos variables."
            }
        ],
        "Ciencia y Tecnología": [
            {
                "eje": "Física General y Mecánica Cuántica",
                "temas": [
                    "Leyes de la electricidad y magnetismo: Electrostática (Ley de Coulomb), corriente eléctrica, circuitos eléctricos simples y electromagnetismo",
                    "Introducción a la física moderna: Teoría de la relatividad especial (conceptos iniciales) y el modelo cuántico del átomo"
                ],
                "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
                "proposito": "Calcular la fuerza de atracción/repulsión entre cargas eléctricas (Ley de Coulomb), resolver circuitos eléctricos en serie y paralelo y explicar la dilatación temporal de la relatividad.",
                "criterio": "Aplica F = k*(q1*q2)/d^2 y la Ley de Ohm V = I*R en circuitos mixtos fundamentando la naturaleza cuántica de la luz."
            },
            {
                "eje": "Química Orgánica Avanzada y Bioquímica",
                "temas": [
                    "Funciones químicas orgánicas oxigenadas y nitrogenadas (alcoholes, aldehídos, cetonas, ácidos carboxílicos, aminas y amidas)",
                    "Introducción a las biomoléculas: Glúcidos, lípidos, proteínas y ácidos nucleicos",
                    "Ejecución final, informe y defensa de un proyecto de indagación científica escolar de carácter experimental o prototipo tecnológico"
                ],
                "competencia": "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno",
                "proposito": "Identificar y nombrar grupos funcionales oxigenados y nitrogenados, describir la síntesis y función biológica de las proteínas y ácidos nucleicos, y defender un proyecto de indagación científica.",
                "criterio": "Diferencia la estructura molecular de un aldehído frente a una cetona y sustenta su informe experimental de ciencias con rigurosidad metodológica."
            }
        ],
        "Educación Religiosa": [
            {
                "eje": "Misión, Fe y Vocación",
                "temas": [
                    "Misión en el Mundo: El compromiso de los cristianos en la construcción de una sociedad justa, pacífica y fraterna",
                    "Respuestas de Fe a la Modernidad: El sentido de la vida, el valor del sufrimiento y la esperanza cristiana frente al nihilismo",
                    "La Doctrina Social de la Iglesia: Derechos de los migrantes, trabajo digno, economía solidaria y paz mundial",
                    "Proyecto Vocacional Cristiano: El matrimonio, el orden sagrado y la vida consagrada o laical como realización personal"
                ],
                "competencia": "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida",
                "proposito": "Discernir su vocación personal a la luz del Evangelio y proponer respuestas cristianas frente al sufrimiento y el sinsentido contemporáneo.",
                "criterio": "Formula su proyecto de vida cristiana integrando compromisos éticos, laborales y de servicio desinteresado a la sociedad."
            }
        ]
    }
}

# Base de datos curricular para Colegios Particulares y Formatos Preuniversitarios
PRIVATE_PREU_SPECIALTIES = {
    "Aritmética": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de cantidad",
        "temas": ["Conjuntos numéricos (Z, Q, R, C)", "Teoría de números y divisibilidad", "Números primos y MCD/MCM", "Razones y proporciones", "Regla de tres simple y compuesta", "Porcentajes comerciales", "Matemática financiera avanzada (interés simple y compuesto, TEA/TNA, amortización)"],
        "proposito": "Resolver problemas de alta demanda aritmética y financiera aplicando propiedades de divisibilidad, proporcionalidad y modelos de interés compuesto.",
        "criterio": "Demuestra rigor en demostraciones aritméticas y calcula cuotas y rendimientos en operaciones financieras avanzadas."
    },
    "Álgebra": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de regularidad, equivalencia y cambio",
        "temas": ["Polinomios y grados", "Productos notables y factorización avanzada", "Ecuaciones e inecuaciones lineales, cuadráticas, con valor absoluto y racionales", "Matrices y determinantes", "Sistemas de ecuaciones 2x2 y 3x3", "Funciones reales (lineal, cuadrática, raíz cuadrada, exponencial y logarítmica)", "Programación lineal bidimensional"],
        "proposito": "Manipular con destreza expresiones algebraicas avanzadas, resolver sistemas de ecuaciones matricialmente y optimizar funciones reales.",
        "criterio": "Resuelve sistemas por la regla de Cramer o Gauss y determina máximos y mínimos de funciones en regiones factibles."
    },
    "Geometría": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de forma, movimiento y localización",
        "temas": ["Triángulos, líneas notables y teoremas de semejanza y congruencia", "Polígonos y cuadriláteros", "Circunferencia y propiedades de tangencia", "Áreas y volúmenes de prismas, pirámides, conos, esferas y poliedros regulares", "Geometría analítica: la recta y secciones cónicas (circunferencia y parábola)"],
        "proposito": "Demostrar teoremas geométricos clásicos y resolver problemas espaciales y analíticos de lugares geométricos y sólidos de revolución.",
        "criterio": "Aplica relaciones métricas en el triángulo rectángulo y transforma ecuaciones canónicas a generales de cónicas con exactitud."
    },
    "Trigonometría": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de forma, movimiento y localización",
        "temas": ["Razones trigonométricas en el triángulo rectángulo y círculo trigonométrico", "Identidades trigonométricas fundamentales, de ángulos compuestos, dobles y triples", "Ecuaciones trigonométricas", "Resolución de triángulos oblicuángulos (Leyes de Senos y Cosenos)"],
        "proposito": "Demostrar identidades trigonométricas complejas y resolver ecuaciones trigonométricas en intervalos reales y situaciones de navegación.",
        "criterio": "Simplifica expresiones mediante identidades de ángulo doble y resuelve triángulos generales aplicando leyes de senos y cosenos."
    },
    "Estadística y Probabilidad": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de gestión de datos e incertidumbre",
        "temas": ["Medidas de tendencia central y dispersión (varianza, desviación estándar) para datos agrupados", "Análisis combinatorio (permutaciones y combinaciones con/sin repetición)", "Probabilidad condicional y Teorema de Bayes", "Regresión lineal y correlación de Pearson"],
        "proposito": "Modelar inferencias estadísticas a partir de muestras y calcular probabilidades compuestas mediante el Teorema de Bayes.",
        "criterio": "Aplica el Teorema de Bayes P(A|B) = [P(B|A)*P(A)]/P(B) en árboles de probabilidad e interpreta la desviación estándar."
    },
    "Biología": {
        "area": "Ciencia y Tecnología",
        "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
        "temas": ["Biología celular (organelas, transporte de membrana activo y pasivo)", "Bioquímica básica (glúcidos, lípidos, proteínas, ácidos nucleicos)", "Genética mendeliana y molecular (replicación, transcripción, traducción del ADN)", "Anatomía y fisiología humana (sistemas circulatorio, digestivo, nervioso, endocrino)", "Ecología, ciclos biogeoquímicos y evolución molecular"],
        "proposito": "Explicar los mecanismos moleculares de la replicación del ADN, la síntesis proteica y el funcionamiento coordinado de la fisiología humana.",
        "criterio": "Describe las etapas de la transcripción y traducción genética y resuelve cruces mendelianos complejos con rigor científico."
    },
    "Química": {
        "area": "Ciencia y Tecnología",
        "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
        "temas": ["Estructura atómica, configuración electrónica y números cuánticos", "Tabla periódica y propiedades periódicas (electronegatividad, radio atómico)", "Enlaces químicos (iónico, covalente, metálico) y fuerzas intermoleculares", "Nomenclatura inorgánica completa y reacciones químicas (REDOX y tanteo)", "Estequiometría (mol, reactivo limitante, rendimiento porcentual)", "Soluciones (molaridad, normalidad, porcentaje en masa)", "Química orgánica (hidrocarburos y funciones oxigenadas/nitrogenadas)"],
        "proposito": "Determinar números cuánticos, balancear reacciones por el método del ion-electrón y resolver problemas estequiométricos de disoluciones.",
        "criterio": "Calcula la molaridad y normalidad de una solución y balancea ecuaciones REDOX en medio ácido y básico sin errores."
    },
    "Física": {
        "area": "Ciencia y Tecnología",
        "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
        "temas": ["Cinemática (MRU, MRUV, movimiento parabólico, MCU y MCUV)", "Dinámica lineal y circular (Leyes de Newton y fuerza centrípeta)", "Estática (primera y segunda condición de equilibrio, torque)", "Trabajo, Potencia y Energía mecánica (conservación de la energía)", "Hidrostática (Principio de Arquímedes y Pascal)", "Electrostática (Ley de Coulomb y campo eléctrico)", "Electrodinámica (Ley de Ohm, circuitos mixtos y Leyes de Kirchhoff)", "Física moderna y relatividad especial"],
        "proposito": "Resolver problemas de mecánica clásica aplicando leyes de Newton, conservación de energía y analizar circuitos eléctricos complejos con leyes de Kirchhoff.",
        "criterio": "Aplica diagramas de cuerpo libre (DCL) en estática y dinámica y resuelve mallas eléctricas calculando corrientes y caídas de voltaje."
    },
    "Psicología y Filosofía": {
        "area": "Desarrollo Personal, Ciudadanía y Cívica",
        "competencia": "Construye su identidad",
        "temas": ["Procesos cognitivos (memoria, aprendizaje, percepción)", "Inteligencia emocional y teorías de la personalidad", "Dilemas morales clásicos y corrientes éticas (utilitarismo, deontología, ética de la virtud)", "Bioética (eutanasia, aborto, manipulación genética)", "Gnoseología y epistemología clásica"],
        "proposito": "Analizar los procesos cognitivos humanos y reflexionar críticamente sobre dilemas bioéticos y corrientes éticas filosóficas.",
        "criterio": "Compara la postura utilitarista de Bentham/Mill con la deontología kantiana frente a un dilema moral contemporáneo."
    },
    "Aptitud Verbal y Literatura Preuniversitaria": {
        "area": "Comunicación",
        "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
        "temas": ["Comprensión lectora preuniversitaria (inferencias complejas, términos en contexto, extrapolaciones)", "Analogías, conectores lógicos e inclusión de enunciados", "Literatura Universal cronológica (Clásica, Medieval, Siglo de Oro, Vanguardias)", "Literatura Peruana e Hispanoamericana en profundidad"],
        "proposito": "Resolver ejercicios de aptitud verbal de alta exigencia inferencial y analizar la evolución estética de la literatura universal y peruana.",
        "criterio": "Determina la idea principal y la intención del autor en lecturas filosóficas complejas y resuelve analogías rigurosamente."
    }
}


def normalize_text(text: str) -> str:
    """Normaliza texto para comparaciones léxicas sin acentos ni signos raros."""
    if not text:
        return ""
    t = text.lower().strip()
    replacements = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("ü", "u"), ("ñ", "n"), (",", " "), (".", " "), (":", " "),
        (";", " "), ("-", " "), ("_", " "), ("/", " "), ("(", " "),
        (")", " "), ('"', " "), ("'", " "), ("?", " "), ("¿", " ")
    )
    for orig, rep in replacements:
        t = t.replace(orig, rep)
    return " ".join(t.split())


def normalize_area_acronym(spec: str) -> str:
    """Normaliza abreviaturas y nombres populares de áreas escolares peruanas."""
    if not spec:
        return ""
    s = normalize_text(spec)
    acronym_map = {
        "dpcc": "desarrollo personal ciudadania y civica",
        "c y c": "desarrollo personal ciudadania y civica",
        "civica": "desarrollo personal ciudadania y civica",
        "ciudadania": "desarrollo personal ciudadania y civica",
        "persona familia": "desarrollo personal ciudadania y civica",
        "ccss": "ciencias sociales",
        "cc ss": "ciencias sociales",
        "sociales": "ciencias sociales",
        "historia": "ciencias sociales",
        "geografia": "ciencias sociales",
        "economia": "ciencias sociales",
        "cyt": "ciencia y tecnologia",
        "c y t": "ciencia y tecnologia",
        "ciencias": "ciencia y tecnologia",
        "cta": "ciencia y tecnologia",
        "c t a": "ciencia y tecnologia",
        "biologia": "ciencia y tecnologia",
        "quimica": "ciencia y tecnologia",
        "fisica": "ciencia y tecnologia",
        "ept": "educacion para el trabajo",
        "e p t": "educacion para el trabajo",
        "tecnica": "educacion para el trabajo",
        "taller": "educacion para el trabajo",
        "emprendimiento": "educacion para el trabajo",
        "computacion": "educacion para el trabajo",
        "informatica": "educacion para el trabajo",
        "ef": "educacion fisica",
        "e f": "educacion fisica",
        "ed fisica": "educacion fisica",
        "comunicacion": "comunicacion",
        "lenguaje": "comunicacion",
        "literatura": "comunicacion",
        "arte": "arte y cultura",
        "arte y cultura": "arte y cultura",
        "ingles": "ingles",
        "english": "ingles",
        "matematica": "matematica",
        "mate": "matematica",
        "aritmetica": "matematica",
        "algebra": "matematica",
        "geometria": "matematica",
        "trigonometria": "matematica",
        "estadistica": "matematica",
        "religion": "educacion religiosa",
        "educacion religiosa": "educacion religiosa",
        "religiosa": "educacion religiosa"
    }
    for acr, full_area in acronym_map.items():
        if s == acr or s.startswith(acr + " ") or s.endswith(" " + acr) or (" " + acr + " ") in s:
            return full_area
    return s


def has_word(word: str, text: str) -> bool:
    """Verifica si una palabra existe como palabra completa y delimitada."""
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text))



CNEB_CAPACIDADES: dict[str, str] = {
    "Construye su identidad": (
        "Se valora a sí mismo. Autorregula sus emociones. Reflexiona y argumenta éticamente. "
        "Vive su sexualidad de manera integral y responsable de acuerdo a su etapa de desarrollo y madurez."
    ),
    "Convive y participa democráticamente en la búsqueda del bien común": (
        "Interactúa con todas las personas. Construye normas y asume acuerdos y leyes. "
        "Maneja conflictos de manera constructiva. Delibera sobre asuntos públicos. Participa en acciones que promueven el bienestar común."
    ),
    "Construye interpretaciones históricas": (
        "Interpreta críticamente fuentes diversas. Comprende el tiempo histórico. Elabora explicaciones sobre procesos históricos."
    ),
    "Gestiona responsablemente el espacio y el ambiente": (
        "Comprende las relaciones entre los elementos naturales y sociales. "
        "Maneja fuentes de información para comprender el espacio geográfico y el ambiente. "
        "Genera acciones para conservar el ambiente local y global."
    ),
    "Gestiona responsablemente los recursos económicos": (
        "Comprende las relaciones entre los elementos del sistema económico y financiero. Toma decisiones económicas y financieras."
    ),
    "Gestiona proyectos de emprendimiento económico o social": (
        "Crea propuestas de valor. Aplica habilidades técnicas. Trabaja cooperativamente para lograr objetivos y metas. "
        "Evalúa los resultados del proyecto de emprendimiento."
    ),
    "Se desenvuelve de manera autónoma a través de su motricidad": (
        "Comprende su cuerpo. Se expresa corporalmente."
    ),
    "Asume una vida saludable": (
        "Comprende las relaciones entre la actividad física, alimentación, postura e higiene personal y del ambiente, y la salud. "
        "Incorpora prácticas que mejoran su calidad de vida."
    ),
    "Interactúa a través de sus habilidades sociomotrices": (
        "Se relaciona utilizando sus habilidades sociomotrices. Crea y aplica estrategias y tácticas de juego."
    ),
    "Aprecia de manera crítica manifestaciones artístico-culturales": (
        "Percibe manifestaciones artístico-culturales. Contextualiza manifestaciones artístico-culturales. "
        "Reflexiona creativa y críticamente sobre manifestaciones artístico-culturales."
    ),
    "Crea proyectos desde los lenguajes artísticos": (
        "Explora y experimenta los lenguajes de las artes. Aplica procesos creativos. Evalúa y comunica sus procesos y proyectos."
    ),
    "Se comunica oralmente en su lengua materna": (
        "Obtiene información del texto oral. Infiere e interpreta información del texto oral. "
        "Adecúa, organiza y desarrolla las ideas de forma coherente y cohesionada. "
        "Utiliza recursos no verbales y paraverbales de forma estratégica. "
        "Interactúa estratégicamente con distintos interlocutores. Reflexiona y evalúa la forma, el contenido y contexto del texto oral."
    ),
    "Lee diversos tipos de textos escritos en su lengua materna": (
        "Obtiene información del texto escrito. Infiere e interpreta información del texto. "
        "Reflexiona y evalúa la forma, el contenido y contexto del texto escrito."
    ),
    "Escribe diversos tipos de textos en su lengua materna": (
        "Adecúa el texto a la situación comunicativa. Organiza y desarrolla las ideas de forma coherente y cohesionada. "
        "Utiliza convenciones del lenguaje escrito de forma pertinente. Reflexiona y evalúa la forma, el contenido y contexto del texto escrito."
    ),
    "Se comunica oralmente en inglés como lengua extranjera": (
        "Obtiene información del texto oral en inglés. Infiere e interpreta información del texto oral. "
        "Adecúa, organiza y desarrolla las ideas de forma coherente y cohesionada en inglés. "
        "Utiliza recursos no verbales y paraverbales de forma estratégica. "
        "Interactúa estratégicamente con distintos interlocutores en inglés. Reflexiona y evalúa el texto oral."
    ),
    "Lee diversos tipos de textos en inglés como lengua extranjera": (
        "Obtiene información del texto escrito en inglés. Infiere e interpreta información del texto en inglés. "
        "Reflexiona y evalúa la forma, el contenido y contexto del texto en inglés."
    ),
    "Escribe diversos tipos de textos en inglés como lengua extranjera": (
        "Adecúa el texto a la situación comunicativa en inglés. Organiza y desarrolla las ideas de forma coherente y cohesionada. "
        "Utiliza convenciones del lenguaje escrito en inglés. Reflexiona y evalúa el texto escrito en inglés."
    ),
    "Resuelve problemas de cantidad": (
        "Traduce cantidades a expresiones numéricas. Comunica su comprensión sobre los números y las operaciones. "
        "Usa estrategias y procedimientos de estimación y cálculo. Argumenta afirmaciones sobre las relaciones numéricas y las operaciones."
    ),
    "Resuelve problemas de regularidad, equivalencia y cambio": (
        "Traduce datos y condiciones a expresiones algebraicas y gráficas. Comunica su comprensión sobre las relaciones algebraicas. "
        "Usa estrategias y procedimientos para encontrar equivalencias y reglas generales. "
        "Argumenta afirmaciones sobre relaciones de cambio y equivalencia."
    ),
    "Resuelve problemas de forma, movimiento y localización": (
        "Modela objetos con formas geométricas y sus transformaciones. Comunica su comprensión sobre las formas y relaciones geométricas. "
        "Usa estrategias y procedimientos para orientarse en el espacio. Argumenta afirmaciones sobre relaciones geométricas."
    ),
    "Resuelve problemas de gestión de datos e incertidumbre": (
        "Representa datos con gráficos y medidas estadísticas o probabilísticas. "
        "Comunica su comprensión de los conceptos estadísticos y probabilísticos. "
        "Usa estrategias y procedimientos para recopilar y procesar datos. "
        "Sustenta conclusiones o decisiones con base en la información obtenida."
    ),
    "Indaga mediante métodos científicos para construir conocimientos": (
        "Problematiza situaciones para hacer indagación. Diseña estrategias para hacer indagación. "
        "Genera y registra datos e información. Analiza datos e información. "
        "Evalúa y comunica el proceso y resultados de su indagación."
    ),
    "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo": (
        "Comprende y usa conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo. "
        "Evalúa las implicancias del saber y del quehacer científico y tecnológico."
    ),
    "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno": (
        "Determina una alternativa de solución tecnológica. Diseña la alternativa de solución tecnológica. "
        "Implementa y valida la alternativa de solución tecnológica. "
        "Evalúa y comunica el funcionamiento y los impactos de su alternativa de solución tecnológica."
    ),
    "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente": (
        "Conoce a Dios y asume su identidad religiosa y espiritual como persona digna, libre y trascendente. "
        "Cultiva y valora las manifestaciones religiosas de su entorno argumentando su fe de manera comprensible y respetuosa."
    ),
    "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida": (
        "Transforma su entorno desde el encuentro personal y comunitario con Dios y desde la fe que profesa. "
        "Actúa coherentemente en razón de su fe según los principios de su conciencia moral en situaciones concretas de la vida."
    ),
    "Se desenvuelve en los entornos virtuales generados por las TIC": (
        "Personaliza entornos virtuales. Gestiona información del entorno virtual. "
        "Interactúa en entornos virtuales. Crea objetos virtuales en diversos formatos."
    ),
    "Gestiona su aprendizaje de manera autónoma": (
        "Define metas de aprendizaje. Organiza acciones estratégicas para alcanzar sus metas de aprendizaje. "
        "Monitorea y ajusta su desempeño durante el proceso de aprendizaje."
    )
}

def get_cneb_capacidades(competencia: str) -> str:
    """Devuelve las capacidades oficiales CNEB para la competencia dada."""
    if not competencia:
        return "Comprende y aplica los conocimientos y habilidades del área curricular con rigor metodológico y pensamiento crítico."
    comp_clean = competencia.strip()
    for k, v in CNEB_CAPACIDADES.items():
        if k.lower() in comp_clean.lower() or comp_clean.lower() in k.lower():
            return v
    return "Comprende y aplica los conocimientos, métodos y habilidades fundamentales del área curricular, comunicando y evaluando sus resultados."


def _resolve_curriculum_context_raw(
    topic: str,
    grade: Optional[int] = None,
    specialty: Optional[str] = None
) -> Dict[str, Any]:
    """
    Motor inteligente de resolución curricular:
    1. Si el tema o palabra clave pertenece a la malla oficial provista (1.° a 5.° o preuniversitaria),
       retorna con exactitud el Área, Eje temático, Competencia CNEB, Capacidades,
       Criterio de Evaluación y Propósito Formativo pertinente.
    2. Si el docente ingresa un TEMA LIBRE O NUEVO (fuera de la malla), deduce inteligentemente
       el área disciplinar, grado adecuado y redacta un propósito y criterio pedagógico formal,
       sin contaminar con términos de taller industrial salvo que sea explícitamente EPT.
    """
    clean_topic = (topic or "").strip()
    norm_topic = normalize_text(clean_topic)
    
    clean_grade = 1
    if isinstance(grade, int) and 1 <= grade <= 5:
        clean_grade = grade

    spec_raw = normalize_text(specialty or "")
    spec_norm = normalize_area_acronym(spec_raw)


    # -------------------------------------------------------------
    # PASO 1: Búsqueda exacta y por palabras clave en PRIVATE_PREU_SPECIALTIES
    # -------------------------------------------------------------
    for subj_name, data in PRIVATE_PREU_SPECIALTIES.items():
        norm_subj = normalize_text(subj_name)
        norm_data_area = normalize_text(data["area"])
        
        subj_compatible = True
        if spec_norm:
            subj_compatible = (
                norm_subj in spec_norm or 
                spec_norm in norm_subj or 
                norm_data_area in spec_norm or 
                spec_norm in norm_data_area or
                spec_raw in norm_subj or
                spec_raw in norm_data_area
            )

        topic_match = any(has_word(normalize_text(t), norm_topic) or normalize_text(t) in norm_topic for t in data["temas"] if len(t) >= 6)
        
        kw_match = False
        if subj_name == "Aritmética" and any(has_word(k, norm_topic) for k in ["mcd", "mcm", "divisibilidad", "numeros primos", "regla de tres", "interes compuesto", "interes simple", "tna", "tea"]):
            kw_match = True
        elif subj_name == "Álgebra" and any(has_word(k, norm_topic) for k in ["polinomio", "polinomios", "factorizacion", "ecuacion cuadratica", "inecuacion", "cramer", "programacion lineal"]):
            kw_match = True
        elif subj_name == "Geometría" and any(has_word(k, norm_topic) for k in ["teorema de pitagoras", "pitagoras", "teorema de tales", "conicas", "parabola", "poliedros"]):
            kw_match = True
        elif subj_name == "Trigonometría" and any(has_word(k, norm_topic) for k in ["trigonometria", "seno", "coseno", "tangente", "angulo doble", "ley de senos", "ley de cosenos"]):
            kw_match = True
        elif subj_name == "Estadística y Probabilidad" and any(has_word(k, norm_topic) for k in ["teorema de bayes", "bayes", "probabilidad condicional", "desviacion estandar", "varianza", "combinatoria"]):
            kw_match = True
        elif subj_name == "Biología" and any(has_word(k, norm_topic) for k in ["celula", "adn", "arn", "mendel", "transcripcion", "fisiologia", "organelas", "mitocondria"]):
            kw_match = True
        elif subj_name == "Química" and any(has_word(k, norm_topic) for k in ["estequiometria", "reactivo limitante", "redox", "molaridad", "enlace quimico", "tabla periodica"]):
            kw_match = True
        elif subj_name == "Física" and any(has_word(k, norm_topic) for k in ["mru", "mruv", "newton", "coulomb", "kirchhoff", "arquimedes", "estatica", "dinamica"]):
            kw_match = True
        elif subj_name == "Psicología y Filosofía" and any(has_word(k, norm_topic) for k in ["procesos cognitivos", "dilemas morales", "bioetica", "kant", "utilitarismo"]):
            kw_match = True
        elif subj_name == "Aptitud Verbal y Literatura Preuniversitaria" and any(has_word(k, norm_topic) for k in ["aptitud verbal", "analogias verbales", "boom latinoamericano"]):
            kw_match = True

        if subj_compatible and (topic_match or kw_match):
            return {
                "is_matched": True,
                "matched_type": "preuniversitario_privado",
                "area": data["area"],
                "subdisciplina": subj_name,
                "grade": clean_grade,
                "competencia": data["competencia"],
                "eje": subj_name,
                "proposito": data["proposito"],
                "criterio": data["criterio"],
                "is_ept": data["area"] == "Educación para el Trabajo"
            }

    # -------------------------------------------------------------
    # PASO 2: Búsqueda exhaustiva en la malla CNEB por Grado y Área
    # -------------------------------------------------------------
    grades_to_check = [clean_grade] + [g for g in [1, 2, 3, 4, 5] if g != clean_grade]

    for g_eval in grades_to_check:
        grade_syllabus = CURRICULAR_SYLLABUS.get(g_eval, {})
        for area_name, units in grade_syllabus.items():
            norm_area = normalize_text(area_name)
            is_area_candidate = (
                (not spec_norm) or 
                (norm_area in spec_norm) or 
                (spec_norm in norm_area) or
                (spec_raw in norm_area) or
                any(k in spec_norm for k in norm_area.split() if len(k) > 3)
            )

            if spec_norm and not is_area_candidate:
                continue

            for u in units:
                for t in u["temas"]:
                    norm_t = normalize_text(t)
                    if (len(norm_t) >= 6 and norm_t in norm_topic) or (len(norm_topic) >= 8 and norm_topic in norm_t):
                        return {
                            "is_matched": True,
                            "matched_type": "cneb_oficial",
                            "area": area_name,
                            "grade": g_eval,
                            "competencia": u["competencia"],
                            "eje": u["eje"],
                            "proposito": u["proposito"],
                            "criterio": u["criterio"],
                            "is_ept": "educacion para el trabajo" in norm_area or "ept" in norm_area
                        }

                    words_t = [w for w in norm_t.split() if len(w) >= 5]
                    words_topic = [w for w in norm_topic.split() if len(w) >= 5]
                    common = set(words_t).intersection(set(words_topic))
                    
                    special_words = ["mru", "mruv", "adn", "arn", "tales", "newton", "tupac", "scamper", "canvas", "laudato", "crispr", "bayes", "coulomb", "arquimedes", "hominizacion", "neolitica", "feudalismo", "tahuantinsuyo", "revolucion"]
                    special_match = any(w in norm_t and w in norm_topic for w in special_words)

                    if len(common) >= 2 or (len(common) >= 1 and special_match):
                        return {
                            "is_matched": True,
                            "matched_type": "cneb_oficial_parcial",
                            "area": area_name,
                            "grade": g_eval,
                            "competencia": u["competencia"],
                            "eje": u["eje"],
                            "proposito": u["proposito"],
                            "criterio": u["criterio"],
                            "is_ept": "educacion para el trabajo" in norm_area or "ept" in norm_area
                        }

    # -------------------------------------------------------------
    # PASO 3: INFERENCIA DINÁMICA INTELIGENTE PARA TEMAS LIBRES O NUEVOS
    # -------------------------------------------------------------
    # 1. Ciencia y Tecnología (Biología, Química, Física, Ecología, Agricultura/Botánica)
    if any(k in norm_topic for k in ["cultivo", "hidropon", "planta", "hortaliza", "biohuerto", "agricultur", "celul", "atomo", "quimic", "fisic", "organismo", "energia", "ecosistema", "planeta", "fuerza", "velocidad", "reaccion", "molecula", "bacteria", "virus", "adn", "arn", "ciencia", "biodiversidad", "clima", "tierra", "glaciar"]):
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Ciencia y Tecnología",
            "grade": clean_grade,
            "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo",
            "eje": "Explicación del mundo físico e Indagación científica",
            "proposito": f"Explicar los fundamentos científicos, principios y relaciones ecológicas y tecnológicas en torno a {clean_topic}, sustentando sus conclusiones en evidencias experimentales.",
            "criterio": f"Argumenta con base científica la estructura y funcionamiento de {clean_topic} relacionándolo con fenómenos del entorno.",
            "is_ept": False
        }

    # 2. Educación para el Trabajo (Tecnología, IA, Proyectos, Negocios, Talleres Técnicos)
    is_ept_spec = any(k in spec_norm for k in ["educacion para el trabajo", "ept", "mecanic", "computac", "electric", "electron", "metal", "mader", "ebanist", "vestid", "textil", "conta", "artesani", "agropecuar"])
    is_ept_top = any(k in norm_topic for k in ["inteligencia artificial", "aprendizaje automatico", "programacion", "algoritmo", "software", "negocio", "emprendim", "design thinking", "lean canvas", "canvas", "prototipo", "taller", "mecanic", "computac", "ofimatica", "presupuesto", "marketing", "costos", "torno", "torneado", "soldadura", "fresadora", "mecanizado", "circuito", "cableado", "instalacion electrica"]) or has_word("ia", norm_topic)
    
    if is_ept_spec or is_ept_top:
        resolved_ept_area = specialty if (specialty and is_ept_spec) else "Educación para el Trabajo"
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": resolved_ept_area,
            "grade": clean_grade,
            "competencia": "Gestiona proyectos de emprendimiento económico o social",
            "eje": "Metodología de proyectos, habilidades técnicas e innovación",
            "proposito": f"Comprender, diseñar y aplicar la secuencia operativa y normas técnicas en {clean_topic}, ejecutando las tareas prácticas con destreza y control de calidad.",
            "criterio": f"Formula propuestas viables, ejecuta las operaciones técnicas de {clean_topic} con precisión, orden y cumplimiento de normas de seguridad.",
            "is_ept": True
        }

    # 3. Matemática
    if any(k in norm_topic for k in ["aritmetica", "algebra", "geometria", "trigonometr", "ecuacion", "funcion", "fraccion", "numero", "matemat", "poligono", "triangulo", "estadist", "probabilidad", "calculo", "logaritmo", "limite", "derivada"]):
        comp = "Resuelve problemas de regularidad, equivalencia y cambio" if any(k in norm_topic for k in ["ecuacion", "algebra", "funcion", "polinomio", "limite", "derivada"]) else (
            "Resuelve problemas de forma, movimiento y localización" if any(k in norm_topic for k in ["geometr", "trigonometr", "angulo", "triangulo", "area", "volumen"]) else (
                "Resuelve problemas de gestión de datos e incertidumbre" if any(k in norm_topic for k in ["estadist", "probabilidad", "muestra", "frecuencia", "grafico"]) else "Resuelve problemas de cantidad"
            )
        )
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Matemática",
            "grade": clean_grade,
            "competencia": comp,
            "eje": "Resolución de problemas de Matemática",
            "proposito": f"Comprender, modelar y resolver situaciones problemáticas vinculadas a {clean_topic}, seleccionando y justificando estrategias heurísticas y de cálculo formal.",
            "criterio": f"Aplica conceptos y propiedades de {clean_topic} para modelar la situación y verifica la validez del resultado obtenido.",
            "is_ept": False
        }

    # 4. Comunicación
    if any(k in norm_topic for k in ["lectura", "texto", "cuento", "novela", "poesia", "ensayo", "ortografia", "gramatica", "oracion", "verbo", "debate", "redaccion", "literatura", "comunicacion", "autor", "narrativo", "obra", "cien anos de soledad"]):
        comp = "Se comunica oralmente en su lengua materna" if any(k in norm_topic for k in ["oral", "debate", "discurso", "exposicion"]) else (
            "Lee diversos tipos de textos escritos en su lengua materna" if any(k in norm_topic for k in ["lectura", "comprension", "analisis", "literatura", "novela", "obra"]) else "Escribe diversos tipos de textos en su lengua materna"
        )
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Comunicación",
            "grade": clean_grade,
            "competencia": comp,
            "eje": "Competencias comunicativas y literarias",
            "proposito": f"Desarrollar habilidades de comprensión crítica, expresión y producción textual en relación con {clean_topic}, utilizando recursos cohesivos y léxico pertinente.",
            "criterio": f"Identifica ideas centrales, redacta con coherencia y evalúa la eficacia comunicativa de textos sobre {clean_topic}.",
            "is_ept": False
        }

    # 5. Ciencias Sociales
    if any(k in norm_topic for k in ["historia", "revolucion", "guerra", "imperio", "cultura", "geografia", "mapa", "cuenca", "economia", "mercado", "sociedad", "poblacion", "republica", "virreinato", "inca", "siglo"]):
        comp = "Construye interpretaciones históricas" if any(k in norm_topic for k in ["historia", "guerra", "revolucion", "imperio", "inca", "siglo", "republica"]) else (
            "Gestiona responsablemente el espacio y el ambiente" if any(k in norm_topic for k in ["geografia", "cuenca", "mapa", "ambiente", "desastre", "espacio"]) else "Gestiona responsablemente los recursos económicos"
        )
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Ciencias Sociales",
            "grade": clean_grade,
            "competencia": comp,
            "eje": "Construcción de interpretaciones y gestión espacial/económica",
            "proposito": f"Analizar críticamente las fuentes y factores históricos, espaciales y socioeconómicos que configuran {clean_topic}, reconociendo sus implicancias en el presente.",
            "criterio": f"Utiliza fuentes contrastadas y sitúa procesos temporales y espaciales sobre {clean_topic} argumentando con rigor histórico.",
            "is_ept": False
        }

    # 6. DPCC
    if any(k in norm_topic for k in ["autoestima", "emocion", "identidad", "sexualidad", "ciudadania", "derechos", "constitucion", "estado", "etica", "convivencia", "conflicto", "psicologia", "adolescencia", "valores"]):
        comp = "Construye su identidad" if any(k in norm_topic for k in ["identidad", "autoestima", "emocion", "sexualidad", "psicologia", "adolescencia"]) else "Convive y participa democráticamente en la búsqueda del bien común"
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Desarrollo Personal, Ciudadanía y Cívica",
            "grade": clean_grade,
            "competencia": comp,
            "eje": "Identidad, ética y ciudadanía activa",
            "proposito": f"Reflexionar de manera crítica sobre {clean_topic}, promoviendo el autoconocimiento, la convivencia democrática y el respeto irrestricto de los derechos fundamentales.",
            "criterio": f"Sustenta posturas éticas y propone acciones para la convivencia armónica y el desarrollo personal sobre {clean_topic}.",
            "is_ept": False
        }

    # 7. Inglés
    if any(k in norm_topic for k in ["ingles", "english", "verb", "past", "present", "future", "vocabulary", "grammar", "reading", "listening", "speaking", "cambridge"]):
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Inglés",
            "grade": clean_grade,
            "competencia": "Se comunica oralmente en inglés como lengua extranjera",
            "eje": "English Language Skills",
            "proposito": f"To understand and produce meaningful language structures regarding {clean_topic}, developing communicative competence in English.",
            "criterio": f"Uses appropriate grammar structures and vocabulary to communicate ideas about {clean_topic} clearly.",
            "is_ept": False
        }

    # 8. Educación Física
    if any(k in norm_topic for k in ["deporte", "futbol", "voley", "basquet", "atletismo", "gimnasia", "calentamiento", "frecuencia cardiaca", "nutricion", "calistenia", "motriz", "entrenamiento"]):
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Educación Física",
            "grade": clean_grade,
            "competencia": "Asume una vida saludable",
            "eje": "Cultura física y salud motriz",
            "proposito": f"Ejecutar actividades motrices y patrones deportivos vinculados a {clean_topic}, adoptando hábitos de hidratación y cuidado corporal autónomo.",
            "criterio": f"Regula su esfuerzo físico y demuestra destreza técnica motriz en la práctica de {clean_topic}.",
            "is_ept": False
        }

    # 9. Arte y Cultura
    if any(k in norm_topic for k in ["dibujo", "pintura", "color", "musica", "danza", "teatro", "grabado", "escultura", "guion", "cancion", "instrumento", "canto", "folclor"]):
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Arte y Cultura",
            "grade": clean_grade,
            "competencia": "Crea proyectos desde los lenguajes artísticos",
            "eje": "Lenguajes artísticos y apreciación cultural",
            "proposito": f"Explorar y experimentar lenguajes artísticos aplicados a {clean_topic}, comunicando vivencias, emociones y valoración del patrimonio cultural.",
            "criterio": f"Emplea técnicas artísticas con destreza expresiva y sustenta el mensaje estético de su creación sobre {clean_topic}.",
            "is_ept": False
        }

    # 10. Educación Religiosa
    if any(k in norm_topic for k in ["dios", "jesus", "biblia", "cristo", "iglesia", "fe", "creacion", "sacramento", "evangelio", "parabola", "oracion", "cristian", "religion", "laudato"]):
        return {
            "is_matched": False,
            "matched_type": "inferido_libre",
            "area": "Educación Religiosa",
            "grade": clean_grade,
            "competencia": "Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente",
            "eje": "Vida cristiana y trascendencia ética",
            "proposito": f"Reflexionar sobre el mensaje de fe, caridad y esperanza cristiana en torno a {clean_topic}, asumiendo actitudes fraternas y de servicio al prójimo.",
            "criterio": f"Interpreta las enseñanzas cristianas sobre {clean_topic} y propone acciones de solidaridad y respeto a la dignidad humana.",
            "is_ept": False
        }

    # Fallback Universal Educativo Formal
    resolved_area = specialty or "Área Curricular General"
    is_ept_flag = "educacion para el trabajo" in norm_topic or "ept" in norm_topic
    return {
        "is_matched": False,
        "matched_type": "universal_educativo",
        "area": resolved_area,
        "grade": clean_grade,
        "competencia": "Gestiona proyectos de emprendimiento económico o social" if is_ept_flag else "Desarrolla competencias del área curricular",
        "eje": f"Desarrollo formativo de {clean_topic}",
        "proposito": f"Comprender, analizar y aplicar los principios y capacidades fundamentales sobre {clean_topic}, demostrando pensamiento crítico, rigurosidad metodológica y trabajo colaborativo.",
        "criterio": f"Demuestra comprensión de los conceptos clave de {clean_topic} y elabora una evidencia de aprendizaje que cumple con los criterios formativos establecidos.",
        "is_ept": is_ept_flag
    }


def resolve_curriculum_context(
    topic: str,
    grade: Optional[int] = None,
    specialty: Optional[str] = None
) -> Dict[str, Any]:
    """
    Función principal de resolución curricular que enriquece el resultado con:
    - is_math: True si el área o disciplina es Matemática
    - capacidades: Capacidades oficiales CNEB para la competencia asignada
    - is_ept: True si pertenece a Educación para el Trabajo
    """
    res = _resolve_curriculum_context_raw(topic, grade, specialty)
    if "is_math" not in res:
        res["is_math"] = (res.get("area") == "Matemática")
    if "capacidades" not in res:
        res["capacidades"] = get_cneb_capacidades(res.get("competencia", ""))
    return res
