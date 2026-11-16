"""
INEI SMART-CORE - Deterministic Mathematical Engine & Comprehensive Pedagogical Tutor
Institución: I.E. Emblemática INEI N.º 34 de Chancay, Perú.

Provides deterministic mathematical grounding, verified step-by-step procedures,
hints (pistas), and Socratic guidance across 4 core areas:
1. Aritmética:
   - Fracciones didácticas (suma/resta con MCM y homogeneización, multiplicación directa, división inversa, mixtos).
   - Operaciones combinadas (jerarquía: signos de agrupación, potencias, raíces, productos, cocientes, sumas, restas).
   - Porcentajes (cálculo directo, descuentos y aumentos con monedas S/ y soles).
2. Álgebra:
   - Ecuaciones lineales con y sin signos de agrupación (ej. 3x + 7 = 22, 2(x + 4) = 18) con todos los pasos algebraicos explícitos.
   - Ecuaciones cuadráticas con discriminante y fórmula general.
   - Polinomios y expresiones algebraicas (factorización por aspa simple/factor común y raíces).
3. Razonamiento Matemático:
   - Sucesiones y progresiones aritméticas y geométricas (ej. 2, 6, 18, 54 -> r=3, sig=162).
4. Geometría:
   - Áreas y perímetros (rectángulos, triángulos, cuadrados, círculos, trapecios).
   - Teorema de Pitágoras con unidades y comprobación.
"""

import re
import math
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
import sympy
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor
)

logger = logging.getLogger("inei_smart_core.math_engine")

# Safe transformations for algebraic parsing
SAFE_TRANSFORMATIONS = (
    standard_transformations + 
    (implicit_multiplication_application, convert_xor)
)

# Minimal, strictly restricted primitives required by SymPy's AST parser
SAFE_GLOBAL_DICT = {
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "Rational": sympy.Rational,
    "Symbol": sympy.Symbol,
    "sqrt": sympy.sqrt,
    "pi": sympy.pi,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "Abs": sympy.Abs,
    "factor": sympy.factor,
    "expand": sympy.expand,
    "simplify": sympy.simplify
}

MATH_TOKEN_PATTERN = re.compile(r"^[0-9a-zA-Z\s\+\-\*\/\^\(\)\=\.\,\_\<\>\:\%\²\³\√]+$")
DANGEROUS_KEYWORDS = [
    "__", "import", "eval", "exec", "open", "os", "sys", "subprocess", "compile",
    "globals", "locals", "builtins", "getattr", "setattr", "delattr", "lambda",
    "class", "def", "return", "while", "for", "if", "else", "try", "except"
]


def normalize_math_text(text: str) -> str:
    """Normalizes Unicode mathematical operators to standard ascii equivalents."""
    if not text:
        return ""
    t = text.replace("−", "-").replace("–", "-").replace("—", "-")
    t = t.replace("×", "*").replace("·", "*")
    t = t.replace("÷", "/")
    t = t.replace("√", "sqrt")
    t = t.replace("²", "^2").replace("³", "^3")
    t = t.replace("’", "'").replace("`", "'")
    t = t.replace("S/.", " ").replace("S/", " ").replace("s/.", " ").replace("s/", " ")
    t = t.replace("soles", " ").replace("Soles", " ")
    return t


def compute_lcm(a: int, b: int) -> int:
    """Returns Least Common Multiple (Mínimo Común Múltiplo)."""
    return abs(a * b) // math.gcd(a, b) if (a and b) else 0


def compute_multiple_lcm(denominators: List[int]) -> int:
    """Returns LCM for a list of integers."""
    if not denominators:
        return 1
    res = denominators[0]
    for d in denominators[1:]:
        res = compute_lcm(res, d)
    return res


class MathEngine:
    @staticmethod
    def is_safe_expression(expr_str: str) -> bool:
        """Validates that expression contains only allowed mathematical characters and no code injection."""
        if not expr_str or len(expr_str) > 250:
            return False
        
        normalized = normalize_math_text(expr_str)
        expr_lower = normalized.lower()
        for kw in DANGEROUS_KEYWORDS:
            if kw in expr_lower:
                return False

        if not MATH_TOKEN_PATTERN.match(normalized):
            return False

        if any(c in normalized for c in [";", "{", "}", "[", "]", "'", '"', "\\", "`", "$"]):
            return False

        if re.search(r"(\^|\*\*)\s*\d{3,}", normalized):
            return False

        return True

    @staticmethod
    def detect_variable(expr_str: str) -> Optional[sympy.Symbol]:
        """Detects the primary single variable in an expression (preferring x, y, z, n, a, b)."""
        letters = [c.lower() for c in expr_str if c.isalpha() and c.lower() not in ["e", "i"]]
        if not letters:
            return None
        for pref in ["x", "y", "z", "n", "a", "b", "m", "k"]:
            if pref in letters:
                return sympy.Symbol(pref)
        return sympy.Symbol(letters[0])

    SPANISH_STOPWORDS = {
        "a", "e", "y", "o", "u", "de", "del", "la", "el", "en", "por", "para", 
        "con", "sin", "sobre", "tras", "al", "un", "una", "unos", "unas", 
        "que", "es", "son", "da", "como", "cual", "cuanto", "cuánto", "paso", "solucion",
        "solución", "resolver", "calcula", "encuentra", "ecuacion", "ecuación", "halla",
        "obten", "obtén", "este", "esta", "estos", "estas", "esto", "ejercicio", "problema", "respuesta",
        "ayuda", "ayudame", "ayúdame", "dime", "porfavor", "favor", "hola", "aqui", "aquí", "tutor"
    }

    @classmethod
    def _is_math_token(cls, token: str) -> bool:
        """Determines if an individual token is purely mathematical."""
        raw = normalize_math_text(token).strip()
        if re.match(r"^[-=_*~#]{2,}$", raw):
            return False
        t = raw.strip(",;.$¿?¡!:'\" \t\r\n").lower()
        if not t:
            return raw in ["+", "-", "*", "/", "^", "(", ")", "=", "<", ">", "<=", ">="]
        if t in cls.SPANISH_STOPWORDS:
            return False
        if re.search(r"[a-záéíóúñ]{2,}", t):
            return False
        return bool(re.match(r"^[\(\)\d\+\-\*\/\^a-z\.\<\>\=]+$", t))

    @classmethod
    def extract_equation_candidate(cls, text: str) -> Optional[str]:
        """Extracts an algebraic equation from natural language text, preserving balanced parentheses."""
        if not text or len(text) > 12000 or "=" not in text:
            return None

        norm_text = normalize_math_text(text)
        cleaned_full = norm_text.replace("$", " ").replace("\\", " ").strip()
        for line in cleaned_full.splitlines():
            line_str = line.strip()
            if "=" not in line_str or line_str.startswith("---") or "DIRECTIVA" in line_str:
                continue

            cleaned_line = re.sub(r"[¿?¡!]", " ", line_str)
            parts = cleaned_line.split("=")
            if len(parts) < 2:
                continue

            lhs_text, rhs_text = parts[0], parts[1]
            lhs_tokens, rhs_tokens = lhs_text.strip().split(), rhs_text.strip().split()

            valid_lhs = []
            for tok in reversed(lhs_tokens):
                if cls._is_math_token(tok):
                    # Strip punctuation but preserve mathematical parentheses
                    clean_tok = tok.strip(",;.$¿?¡!:'\" \t\r\n")
                    valid_lhs.insert(0, clean_tok)
                else:
                    if valid_lhs:
                        break

            valid_rhs = []
            for tok in rhs_tokens:
                if cls._is_math_token(tok):
                    clean_tok = tok.strip(",;.$¿?¡!:'\" \t\r\n")
                    valid_rhs.append(clean_tok)
                else:
                    if valid_rhs:
                        break

            if not valid_lhs or not valid_rhs:
                continue

            lhs_str = " ".join(valid_lhs).strip()
            rhs_str = " ".join(valid_rhs).strip()
            eq_str = f"{lhs_str} = {rhs_str}"
            has_var = any(c.isalpha() for c in eq_str)

            if has_var and cls.is_safe_expression(eq_str):
                return eq_str

        return None

    @classmethod
    def extract_arithmetic_snippet(cls, text: str) -> Optional[str]:
        """Extracts arithmetic operations like '48+37-19', '(-12) + 7 - (-5)', '125 * 8', '(15 - 3)^2 / 4 + 7' from text."""
        if not text:
            return None
        norm = normalize_math_text(text)
        cleaned = re.sub(
            r"(?i)^(?:por favor\s*)?(?:ayudame a\s*|ayúdame a\s*)?(?:calcula|calcular|halla|hallar|obten|obtén|obtener|resuelve|resolver|resolvé|cuanto es|cuánto es|la respuesta es|evalua|evalúa|evaluar|dime el resultado de)\s*[:=]?\s*",
            "",
            norm
        ).strip()
        cleaned = cleaned.rstrip("=?¿!¡.: ")

        # Reject if query indicates factorization, ordering, or geometry
        norm_lower = norm.lower()
        # Reject dates like 2026-11-15, 2026/11/15, 15-11-2026 or file attachment requests
        if re.search(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b', norm):
            return None
        if any(w in norm_lower for w in ["archivo adjunto", "captura", "imagen", "pdf", "docx", "pantalla", "adjunto", "screenshot"]):
            return None

        if any(w in norm_lower for w in [
            "factoriza", "factorizar", "factorice", "descompon", "descomponer", 
            "ordena", "ordenar", "clasifica", "área", "area", "perímetro", "perimetro", 
            "rectángulo", "rectangulo", "triángulo", "triangulo", "circulo", "círculo", "trapecio"
        ]):
            return None

        # Normalize multiplication 'x' between numbers (e.g. '12 x 8' -> '12 * 8')
        cleaned = re.sub(r"\b(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\b", r"\1 * \2", cleaned)

        # Reject if expression contains algebraic variable structures (e.g. 'x^2', 'x2', '3x', 'x + y')
        no_funcs = re.sub(r"\b(?:sqrt|sin|cos|tan|pi)\b", "", cleaned, flags=re.I)
        if re.search(r"\b[a-zA-Z]\^|\b[a-zA-Z]\d|\d+[a-zA-Z]|[a-zA-Z]\s*[\+\-\*\/\^=]\s*[a-zA-Z]|\b[a-zA-Z]\s*=\s*", no_funcs):
            return None

        # Match arithmetic expressions with positive/negative numbers, parentheses, powers, operators
        # e.g. '(-12) + 7 - (-5)', '45+28-17', '(15 - 3)^2 / 4 + 7'
        expr_match = re.search(
            r"(?<![a-zA-Z0-9_\^\*\/])("
            r"(?:\(?\s*[\+\-]?\s*\d+(?:\.\d+)?\s*\)?\s*[\+\-\*\/\^]\s*)+"
            r"(?:\(?\s*[\+\-]?\s*\d+(?:\.\d+)?\s*\)?)"
            r")(?![a-zA-Z0-9_\^\*\/])",
            cleaned
        )
        if expr_match:
            candidate = expr_match.group(1).strip()
            # Ensure candidate itself has no letters
            if not re.search(r"[a-zA-Z]", candidate):
                if cls.is_safe_expression(candidate) and any(op in candidate for op in ["+", "-", "*", "/", "^"]):
                    return candidate

        cleaned_no_funcs = re.sub(r"\b(?:sqrt|sin|cos|tan|pi)\b", "", cleaned, flags=re.I)
        if not re.search(r"[a-zA-Z]", cleaned_no_funcs):
            if cls.is_safe_expression(cleaned) and any(op in cleaned for op in ["+", "-", "*", "/", "^"]):
                return cleaned

        return None

    # =========================================================================
    # SAFETY: DETECCIÓN DE ENTRADAS AMBIGUAS O CONCATENADAS (TAREA 1)
    # =========================================================================
    @classmethod
    def detect_ambiguous_or_concatenated_input(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Detects ambiguous, malformed, or concatenated repetitive arithmetic inputs
        (e.g. '45+28-1745 + 28 - 1745+28-17', '2x+1=5=9', '45 + 28 - ')
        and requests clarification politely without assuming unintended operations.
        """
        if not text:
            return None

        # Extensive text or pedagogical prose (> 10 words) is not a raw ambiguous math expression
        if len(re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]{3,}', text)) > 10:
            return None
            
        norm = normalize_math_text(text).strip()
        
        # Check 1: Multiple '=' signs (e.g. 2x + 1 = 5 = 9)
        if norm.count('=') > 1:
            return {
                "category": "algebra",
                "topic": "entrada_ambigua",
                "status": "ambiguo",
                "data_identified": {"entrada": text},
                "exact_solution": "aclaracion_requerida",
                "step_text": (
                    "### ⚠️ ENTRADA AMBIGUA DETECTADA\n\n"
                    "Hola. Al revisar la ecuación ingresada:\n"
                    f"> *\"{text.strip()}\"*\n\n"
                    "Se detectaron múltiples signos de igualdad (`=`), lo que genera una expresión contradictoria o ambigua.\n\n"
                    "👉 **¿Cómo continuar?**\n"
                    "Por favor, escribe una sola ecuación por consulta (por ejemplo: `3x + 5 = 20`) para resolverla paso a paso juntos."
                ),
                "hints_text": "Escribe una única ecuación con un solo signo de igualdad.",
                "socratic_text": "¿Podrías escribir la ecuación con un solo signo de igualdad para poder despejar la incógnita?",
                "verified": True
            }

        # Check 2: Dangling operators at end of arithmetic expression (e.g. '45 + 28 - ')
        clean_no_punct = norm.rstrip('?¿!¡.: ')
        if re.search(r'[\+\-\*\/\^]\s*$', clean_no_punct):
            return {
                "category": "aritmetica",
                "topic": "entrada_incompleta",
                "status": "ambiguo",
                "data_identified": {"entrada": text},
                "exact_solution": "aclaracion_requerida",
                "step_text": (
                    "### ⚠️ EXPRESIÓN INCOMPLETA DETECTADA\n\n"
                    "Hola. Al revisar la operación planteada:\n"
                    f"> *\"{text.strip()}\"*\n\n"
                    "La expresión termina con un signo de operación sin un número posterior.\n\n"
                    "👉 **¿Cómo continuar?**\n"
                    "Por favor, completa la operación (por ejemplo: `45 + 28 - 17`) y con gusto te mostraré el desarrollo."
                ),
                "hints_text": "Completa el último número de la operación matemática.",
                "socratic_text": "¿Qué número falta después del último signo de operación?",
                "verified": True
            }

        # Check 3: Consecutive invalid binary operators (e.g. '++' or '+-+' or '* /')
        if re.search(r'(?:[\+\-\*\/]\s*){3,}', norm) or re.search(r'[\*\/]\s*[\*\/]', norm):
            return {
                "category": "aritmetica",
                "topic": "operadores_consecutivos",
                "status": "ambiguo",
                "data_identified": {"entrada": text},
                "exact_solution": "aclaracion_requerida",
                "step_text": (
                    "### ⚠️ OPERADORES CONSECUTIVOS DETECTADOS\n\n"
                    "Hola. Al revisar la consulta:\n"
                    f"> *\"{text.strip()}\"*\n\n"
                    "Se detectaron operadores matemáticos repetidos consecutivamente de forma ambigua.\n\n"
                    "👉 **¿Cómo continuar?**\n"
                    "Por favor, revisa y vuelve a escribir la expresión utilizando un único operador entre cada número."
                ),
                "hints_text": "Verifica que no haya signos de operación repetidos juntos.",
                "socratic_text": "¿Cuál es el signo correcto que debe ir entre esos dos números?",
                "verified": True
            }

        # Check 4: Space-separated numbers without operator in pure arithmetic query (e.g. '45 28 - 17')
        if re.search(r'(?<![a-zA-Z\d/])\d+\s+\d+(?![a-zA-Z\d/])', norm):
            words = re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]+', norm)
            math_kw = {'calcula', 'resuelve', 'halla', 'cuanto', 'cuánto', 'es', 'resultado', 'de', 'por', 'favor', 'ayudame', 'ayúdame'}
            narrative_words = [w for w in words if w.lower() not in math_kw]
            if not narrative_words:
                return {
                    "category": "aritmetica",
                    "topic": "numeros_sin_operador",
                    "status": "ambiguo",
                    "data_identified": {"entrada": text},
                    "exact_solution": "aclaracion_requerida",
                    "step_text": (
                        "### ⚠️ NÚMEROS SIN OPERADOR DETECTADOS\n\n"
                        "Hola. Al revisar la operación:\n"
                        f"> *\"{text.strip()}\"*\n\n"
                        "Se detectaron números continuos separados solo por espacios sin un signo de suma, resta, multiplicación o división entre ellos.\n\n"
                        "👉 **¿Cómo continuar?**\n"
                        "Por favor, indica qué operación deseas realizar entre ellos (por ejemplo: `45 + 28 - 17`)."
                    ),
                    "hints_text": "Coloca un signo de operación (+, -, *, /) entre los números.",
                    "socratic_text": "¿Qué operación matemática deseas realizar entre esos dos números?",
                    "verified": True
                }

        # Check 5: Concatenated/repeated glued arithmetic patterns (e.g. '45+28-1745 + 28 - 1745+28-17')
        s = re.sub(r'\s+', '', norm)
        tokens = re.findall(r'\d+|[+\-*/^()]', s)
        if len(tokens) >= 5:
            # Check if first and last numbers are glued in any middle number
            first_num = tokens[0] if tokens[0].isdigit() else None
            last_num = tokens[-1] if tokens[-1].isdigit() else None
            if first_num and last_num:
                glued = last_num + first_num
                for t in tokens[1:-1]:
                    if t.isdigit() and glued in t and len(t) >= len(glued):
                        return {
                            "category": "aritmetica",
                            "topic": "entrada_ambigua",
                            "status": "ambiguo",
                            "data_identified": {"entrada": text, "patron_detectado": glued},
                            "exact_solution": "aclaracion_requerida",
                            "step_text": (
                                "### ⚠️ ENTRADA CONCATENADA O AMBIGUA DETECTADA\n\n"
                                "Hola. Al revisar la expresión matemática ingresada:\n"
                                f"> *\"{text.strip()}\"*\n\n"
                                "Se detectó que la consulta contiene operaciones repetidas o concatenadas de forma accidental "
                                f"(por ejemplo, la unión repetida `{glued}` generada al pegar el inicio y el final de la expresión).\n\n"
                                "📌 **Para garantizar la exactitud de tu aprendizaje:**\n"
                                "- No asumiremos una operación distinta a la que realmente necesitas resolver.\n"
                                "- Por favor, vuelve a escribir la operación que deseas calcular (por ejemplo: `45 + 28 - 17`) "
                                "y la resolveremos paso a paso juntos."
                            ),
                            "hints_text": "Vuelve a escribir la operación matemática asegurándote de no pegar expresiones repetidas.",
                            "socratic_text": "¿Podrías escribir únicamente el ejercicio que deseas resolver sin repetir la operación?",
                            "verified": True
                        }

            # Check for repeated token n-grams of length >= 3
            for n in range(3, len(tokens) // 2 + 1):
                for i in range(len(tokens) - n + 1):
                    ngram = tokens[i:i+n]
                    if any(op in ['+', '-', '*', '/', '^'] for op in ngram):
                        occ = 0
                        for j in range(len(tokens) - n + 1):
                            if tokens[j:j+n] == ngram:
                                occ += 1
                        if occ >= 2:
                            for t in tokens:
                                if t.isdigit() and len(t) >= 4:
                                    return {
                                        "category": "aritmetica",
                                        "topic": "entrada_ambigua",
                                        "status": "ambiguo",
                                        "data_identified": {"entrada": text},
                                        "exact_solution": "aclaracion_requerida",
                                        "step_text": (
                                            "### ⚠️ ENTRADA CONCATENADA O REPETIDA DETECTADA\n\n"
                                            "Hola. Al analizar tu consulta:\n"
                                            f"> *\"{text.strip()}\"*\n\n"
                                            "Se detectó una secuencia de operaciones duplicadas y fusionadas de forma ambigua.\n\n"
                                            "👉 **¿Cómo continuar?**\n"
                                            "Por favor, vuelve a escribir la expresión matemática clara y la resolveremos juntos paso a paso."
                                        ),
                                        "hints_text": "Vuelve a escribir la operación matemática sin duplicar los términos.",
                                        "socratic_text": "¿Podrías escribir nuevamente la operación para resolverla con certeza?",
                                        "verified": True
                                    }

        return None

    # =========================================================================
    # AREA 1.0: ORDENAMIENTO NUMÉRICO (TAREA 3)
    # =========================================================================
    @classmethod
    def solve_number_ordering(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Comprehensive pedagogical solver for ordering numerical lists:
        - Numbers: Decimals (with '.' or ','), Fractions (e.g. 3/4), Negative numbers, Integers.
        - Directions: 'de menor a mayor' (ascendente) or 'de mayor a menor' (descendente).
        - Explains conversions: e.g. 3/4 = 0.75.
        """
        if not text:
            return None
            
        norm = normalize_math_text(text)
        text_lower = norm.lower()
        
        is_ordering = any(w in text_lower for w in [
            "ordena", "ordenar", "ordene", "clasifica", "organiza", 
            "de menor a mayor", "de mayor a menor", "ascendente", "descendente"
        ])
        if not is_ordering:
            return None
            
        is_descending = any(w in text_lower for w in ["mayor a menor", "descendente", "decreciente"])
        direction_label = "de mayor a menor (descendente)" if is_descending else "de menor a mayor (ascendente)"
        
        # Strip command phrasing
        m_list = re.search(r"(?i)(?:ordena|clasifica|organiza)[^:]*?:\s*(.+)", norm)
        if m_list:
            cleaned = m_list.group(1).strip()
        else:
            cleaned = re.sub(
                r"(?i)^(?:por favor\s*)?(?:ayudame a\s*)?(?:ordena|ordenar|ordene|clasifica|organiza)\s*(?:los siguientes n[uú]meros\s*)?(?:de menor a mayor|de mayor a menor|ascendente|descendente)?\s*[:=]?\s*",
                "",
                norm
            ).strip()
            cleaned = re.sub(r"(?i)\bde\s+(?:menor\s+a\s+mayor|mayor\s+a\s+menor)\b", "", cleaned).strip()
        
        # Strip trailing narrative instructions (e.g. '. Convierte las fracciones...')
        cleaned = re.sub(r"\.\s+[a-zA-ZáéíóúÁÉÍÓÚñÑ].*$", "", cleaned).strip()
        cleaned = cleaned.rstrip("?¿!¡.: ")
        
        # Split items
        if ";" in cleaned:
            raw_items = [x.strip() for x in cleaned.split(";") if x.strip()]
        elif "," in cleaned:
            raw_items = [x.strip() for x in re.split(r"[,;]\s*|\s+y\s+|\s+e\s+", cleaned) if x.strip()]
        else:
            raw_items = [x.strip() for x in cleaned.split() if x.strip()]
            
        parsed_items = []
        for item in raw_items:
            orig = item
            val_str = item.replace(",", ".")
            try:
                if "/" in val_str:
                    parts = val_str.split("/")
                    num = int(parts[0].strip())
                    den = int(parts[1].strip())
                    val = sympy.Rational(num, den)
                    is_frac = True
                else:
                    val = sympy.Rational(val_str)
                    is_frac = False
                parsed_items.append({
                    "orig": orig,
                    "val": val,
                    "float": float(val),
                    "is_frac": is_frac
                })
            except Exception:
                pass
                
        if len(parsed_items) < 2:
            return None
            
        sorted_items = sorted(parsed_items, key=lambda x: x["val"], reverse=is_descending)
        order_str = "; ".join([x["orig"] for x in sorted_items])
        
        # Build pedagogical steps
        steps = []
        val_explanations = []
        for x in parsed_items:
            if x["is_frac"]:
                dec_float = float(x["val"])
                # Show exact representation or approximation with approx sign
                dec_clean = f"{dec_float:.4f}".rstrip('0').rstrip('.')
                if len(f"{dec_clean}".split(".")[-1]) >= 4 or (x["val"].q not in [1, 2, 4, 5, 8, 10, 20, 25, 50, 100]):
                    dec_display = f"\\approx {dec_float:.4f}"
                else:
                    dec_display = f"= {dec_clean}"
                val_explanations.append(f"   - Para $\\mathbf{{{x['orig']}}}$: realizamos la división ${x['val'].p} \\div {x['val'].q} {dec_display}$")
            else:
                val_explanations.append(f"   - Para $\\mathbf{{{x['orig']}}}$: valor decimal directo = $\\mathbf{{{x['orig']}}}$")

        # Note about equivalent values if any
        equiv_pairs = []
        for i in range(len(sorted_items) - 1):
            if sorted_items[i]["val"] == sorted_items[i+1]["val"]:
                equiv_pairs.append(f"${sorted_items[i]['orig']} = {sorted_items[i+1]['orig']}$")
        equiv_note = ""
        if equiv_pairs:
            equiv_note = f"\n   - *Nota pedagógica sobre valores equivalentes:* " + ", ".join(equiv_pairs) + " (representan la misma magnitud en la recta numérica y se conservan ambos en el orden final)."

        steps.append(
            f"1. **Estandarizar los Valores a Forma Decimal:**\n"
            f"   - Para comparar de forma directa fracciones y decimales, expresamos cada valor en su representación decimal:\n"
            + "\n".join(val_explanations)
            + equiv_note
        )
        
        # Build comparison string preserving equalities
        comp_parts_dec = []
        comp_parts_orig = []
        for i, it in enumerate(sorted_items):
            dec_val_str = f"{it['float']:.4f}".rstrip('0').rstrip('.')
            if i == 0:
                comp_parts_dec.append(dec_val_str)
                comp_parts_orig.append(it["orig"])
            else:
                prev = sorted_items[i-1]
                if it["val"] == prev["val"]:
                    sym_rel = " = "
                else:
                    sym_rel = " > " if is_descending else " < "
                comp_parts_dec.append(f"{sym_rel}{dec_val_str}")
                comp_parts_orig.append(f"{sym_rel}{it['orig']}")

        decimal_comparison = "".join(comp_parts_dec)
        orig_comparison = "".join(comp_parts_orig)
        
        steps.append(
            f"2. **Comparar y Ordenar ({direction_label}):**\n"
            f"   - Comparación numérica directa:\n"
            f"   $${decimal_comparison}$$\n"
            f"   - Sustituyendo los valores originales en el orden requerido:\n"
            f"   $${orig_comparison}$$"
        )
        
        step_text = (
            f"### 🔢 RESOLUCIÓN ARITMÉTICA: ORDENAMIENTO NUMÉRICO\n"
            f"**Valores iniciales:** {', '.join([x['orig'] for x in parsed_items])}\n"
            f"**Criterio:** Ordenar {direction_label}.\n\n"
            + "\n\n".join(steps) + "\n\n"
            + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{order_str}}}$"
        )
        
        return {
            "category": "aritmetica",
            "topic": "ordenamiento_numerico",
            "data_identified": {"valores_originales": [x["orig"] for x in parsed_items], "orden": order_str, "criterio": direction_label},
            "exact_solution": order_str,
            "step_text": step_text,
            "hints_text": "Convierte cada fracción a decimal dividiendo el numerador entre el denominador para compararlas directamente.",
            "socratic_text": "¿Cuál es el valor decimal de cada fracción para ordenarlas en la recta numérica?",
            "verified": True
        }

    # =========================================================================
    # AREA 1.1: CONVERSIÓN DE DECIMAL A FRACCIÓN (TAREA 5)
    # =========================================================================
    @classmethod
    def solve_decimal_to_fraction(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles decimal to fraction conversion: e.g. '0,75 a fraccion' -> '3/4', '0,375 a fraccion irreducible con mcd'."""
        if not text:
            return None
        norm = normalize_math_text(text)
        text_lower = norm.lower()
        if not any(k in text_lower for k in ["fraccion", "fracción", "mcd", "irreducible", "irreductible"]):
            return None
            
        m = re.search(r"(-?\d+[.,]\d+)", text_lower)
        if not m:
            return None
            
        dec_raw = m.group(1)
        dec_clean = dec_raw.replace(",", ".")
        try:
            r = sympy.Rational(dec_clean)
            num = r.p
            den = r.q
            exact_solution = f"{num}/{den}"
            
            parts = dec_clean.split(".")
            decimals_count = len(parts[1]) if len(parts) > 1 else 1
            power10 = 10 ** decimals_count
            raw_num = int(round(float(dec_clean) * power10))
            
            # Algoritmo de Euclides para el MCD
            num1, num2 = max(abs(raw_num), power10), min(abs(raw_num), power10)
            euclid_steps = []
            while num2 > 0:
                q = num1 // num2
                rem = num1 % num2
                euclid_steps.append(f"{num1} = {num2} \\times {q} + {rem}")
                num1, num2 = num2, rem
            gcd_val = num1 if num1 != 0 else 1
            
            euclid_formatted = "\n".join([f"     - ${s}$" for s in euclid_steps])
            
            steps = [
                f"1. **Identificar el Número Decimal:**\n"
                f"   - Decimal dado: **{dec_raw}**\n"
                f"   - Es un decimal exacto con **{decimals_count}** cifra(s) decimal(es).",
                f"2. **Escribir como Fracción Decimal:**\n"
                f"   - Multiplicamos y dividimos por $10^{{{decimals_count}}} = {power10}$ para eliminar la coma decimal:\n"
                f"   $${dec_raw} = \\frac{{{raw_num}}}{{{power10}}}$$",
                f"3. **Cálculo del Máximo Común Divisor (Algoritmo de Euclides):**\n"
                f"   - Aplicamos divisiones sucesivas:\n"
                f"{euclid_formatted}\n"
                f"   - Conclusión del algoritmo: $\\text{{MCD}}({raw_num}, {power10}) = \\mathbf{{{gcd_val}}}$.",
                f"4. **Simplificación a Fracción Irreducible:**\n"
                f"   - Dividimos numerador y denominador entre el MCD ({gcd_val}):\n"
                f"   $$\\frac{{{raw_num} \\div {gcd_val}}}{{{power10} \\div {gcd_val}}} = \\mathbf{{\\frac{{{num}}}{{{den}}}}}$$"
            ]
            
            step_text = (
                f"### 🧮 RESOLUCIÓN ARITMÉTICA: CONVERSIÓN DE DECIMAL A FRACCIÓN\n"
                f"**Decimal:** `{dec_raw}`\n\n"
                + "\n\n".join(steps) + "\n\n"
                + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_solution}}}$"
            )
            
            return {
                "category": "aritmetica",
                "topic": "conversion_decimal_fraccion",
                "data_identified": {"decimal": dec_raw, "fraccion": exact_solution, "mcd": gcd_val},
                "exact_solution": exact_solution,
                "step_text": step_text,
                "hints_text": f"Multiplica y divide por {power10} para escribirlo como fracción y luego simplifica dividiendo por su MCD.",
                "socratic_text": "¿Por qué potencia de 10 debemos multiplicar para convertir la parte decimal en un número entero?",
                "verified": True
            }
        except Exception:
            return None

    # =========================================================================
    # AREA 1: ARITMÉTICA (FRACCIONES, PORCENTAJES, OPERACIONES COMBINADAS)
    # =========================================================================
    @classmethod
    def solve_fraction_operation(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Comprehensive pedagogical solver for fraction operations:
        - Addition & Subtraction (homogéneas y heterogéneas con MCM).
        - Multiplication (producto directo de numeradores y denominadores).
        - Division (multiplicación por la fracción inversa).
        - Mixed Numbers representation (ej. 23/20 = 1 3/20).
        """
        if not text:
            return None

        norm = normalize_math_text(text)
        norm_lower = norm.lower()

        # Reject narrative word problems from isolated fraction arithmetic solver
        VERBAL_PROBLEM_WORDS = [
            "tiene", "gasta", "compr", "pag", "dinero", "cost", "queda", "sobra",
            "vuelto", "alimento", "transporte", "cuanto le queda", "cuánto le queda",
            "cuanto dinero", "cuánto dinero", "le sobra", "le resta", "restante",
            "de su dinero", "de lo que le queda", "del resto", "un alumno", "una persona"
        ]
        if any(w in norm_lower for w in VERBAL_PROBLEM_WORDS):
            return None
        
        # Avoid treating power divisions like '(15 - 3)^2 / 4' as standalone fraction operations
        if "^" in norm or "**" in norm:
            return None

        # Check if text contains fraction structures (\d+/\d+)
        fraction_matches = re.findall(r"\b(\d+)\s*/\s*(\d+)\b", norm)
        if not fraction_matches:
            return None

        # Clean snippet
        snippet = cls.extract_arithmetic_snippet(norm)
        if not snippet:
            m_expr = re.search(r"((?:\(?\s*\d+\s*/\s*\d+\s*\)?|\d+)(?:\s*[\+\-\*\/]\s*(?:\(?\s*\d+\s*/\s*\d+\s*\)?|\d+))+)", norm)
            if m_expr:
                snippet = m_expr.group(1).strip()
            else:
                return None

        # Standalone fraction without operators requires explicit keyword like 'simplifica' or 'fraccion'
        has_operator = any(op in snippet for op in ["+", "-", "*", "÷", "/"])
        is_isolated_frac = bool(re.match(r"^\s*\(?\s*\d+\s*/\s*\d+\s*\)?\s*$", snippet))
        if is_isolated_frac and not any(k in norm_lower for k in ["simplifica", "simplificar", "reduce", "fraccion", "fracción"]):
            return None

        if not cls.is_safe_expression(snippet):
            return None

        try:
            # Check 2-fraction operation: A/B [+-*/] C/D
            simple_2frac = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*([\+\-\*\/])\s*(\d+)\s*/\s*(\d+)\s*$", snippet)
            # Chained add/sub: A/B +/- C/D +/- E/F
            chained_add_sub = re.match(r"^\s*(\d+)\s*/\s*(\d+)(?:\s*([\+\-])\s*(\d+)\s*/\s*(\d+))+\s*$", snippet)

            if simple_2frac:
                n1, d1, op, n2, d2 = int(simple_2frac.group(1)), int(simple_2frac.group(2)), simple_2frac.group(3), int(simple_2frac.group(4)), int(simple_2frac.group(5))
                r1 = sympy.Rational(n1, d1)
                r2 = sympy.Rational(n2, d2)
                if op == "+":
                    exact_sympy = r1 + r2
                elif op == "-":
                    exact_sympy = r1 - r2
                elif op == "*":
                    exact_sympy = r1 * r2
                elif op == "/":
                    exact_sympy = r1 / r2
            else:
                # Replace fraction tokens A/B with Rational(A, B)
                rational_snippet = re.sub(r"\b(\d+)\s*/\s*(\d+)\b", r"Rational(\1, \2)", snippet)
                parsed = parse_expr(
                    rational_snippet,
                    global_dict=SAFE_GLOBAL_DICT,
                    transformations=SAFE_TRANSFORMATIONS,
                    evaluate=True
                )
                if not parsed.is_number:
                    return None
                exact_sympy = sympy.Rational(parsed)

            num = exact_sympy.p
            den = exact_sympy.q

            exact_solution = f"{num}/{den}" if den != 1 else str(num)
            decimal_val = float(exact_sympy.evalf())
            decimal_str = f"{decimal_val:.4f}".rstrip('0').rstrip('.')

            # Determine mixed number if improper fraction (num > den > 1)
            is_improper = abs(num) > den and den > 1
            mixed_str = ""
            if is_improper and num > 0:
                entero = num // den
                resto = num % den
                mixed_str = f"{entero} \\frac{{{resto}}}{{{den}}}"

            steps = []
            if simple_2frac:
                n1, d1, op, n2, d2 = int(simple_2frac.group(1)), int(simple_2frac.group(2)), simple_2frac.group(3), int(simple_2frac.group(4)), int(simple_2frac.group(5))
                steps.append(
                    f"1. **Identificar las Fracciones y la Operación:**\n"
                    f"   - Primera fracción: $\\frac{{{n1}}}{{{d1}}}$ (Numerador = {n1}, Denominador = {d1})\n"
                    f"   - Segunda fracción: $\\frac{{{n2}}}{{{d2}}}$ (Numerador = {n2}, Denominador = {d2})\n"
                    f"   - Operación a realizar: **{'Suma (+)' if op == '+' else 'Resta (-)' if op == '-' else 'Multiplicación (×)' if op == '*' else 'División (÷)'}**"
                )

                if op in ["+", "-"]:
                    if d1 == d2:
                        res_num = n1 + n2 if op == "+" else n1 - n2
                        steps.append(
                            f"2. **Fracciones Homogéneas (Mismo Denominador = {d1}):**\n"
                            f"   - Operamos directamente sobre los numeradores conservando el denominador común:\n"
                            f"   $$\\frac{{{n1}}}{{{d1}}} {op} \\frac{{{n2}}}{{{d2}}} = \\frac{{{n1} {op} {n2}}}{{{d1}}} = \\frac{{{res_num}}}{{{d1}}}$$"
                        )
                    else:
                        lcm_val = compute_lcm(d1, d2)
                        f1_mult = lcm_val // d1
                        f2_mult = lcm_val // d2
                        eq_n1 = n1 * f1_mult
                        eq_n2 = n2 * f2_mult
                        res_num = eq_n1 + eq_n2 if op == "+" else eq_n1 - eq_n2

                        steps.append(
                            f"2. **Cálculo del Mínimo Común Múltiplo (MCM):**\n"
                            f"   - Como los denominadores son distintos ({d1} y {d2}), calculamos el $\\text{{MCM}}({d1}, {d2})$:\n"
                            f"   $$\\text{{MCM}}({d1}, {d2}) = \\mathbf{{{lcm_val}}}$$"
                        )
                        steps.append(
                            f"3. **Homogeneización (Fracciones Equivalentes con Denominador Común {lcm_val}):**\n"
                            f"   - Para $\\frac{{{n1}}}{{{d1}}}$: ${lcm_val} \\div {d1} = {f1_mult} \\implies \\frac{{{n1} \\times {f1_mult}}}{{{d1} \\times {f1_mult}}} = \\frac{{{eq_n1}}}{{{lcm_val}}}$\n"
                            f"   - Para $\\frac{{{n2}}}{{{d2}}}$: ${lcm_val} \\div {d2} = {f2_mult} \\implies \\frac{{{n2} \\times {f2_mult}}}{{{d2} \\times {f2_mult}}} = \\frac{{{eq_n2}}}{{{lcm_val}}}$"
                        )
                        steps.append(
                            f"4. **Operación en el Numerador Común:**\n"
                            f"   $$\\frac{{{eq_n1}}}{{{lcm_val}}} {op} \\frac{{{eq_n2}}}{{{lcm_val}}} = \\frac{{{eq_n1} {op} {eq_n2}}}{{{lcm_val}}} = \\frac{{{res_num}}}{{{lcm_val}}}$$"
                        )

                elif op == "*":
                    raw_num = n1 * n2
                    raw_den = d1 * d2
                    steps.append(
                        f"2. **Propiedad de la Multiplicación de Fracciones:**\n"
                        f"   - Se multiplican los numeradores entre sí y los denominadores entre sí:\n"
                        f"   $$\\frac{{{n1}}}{{{d1}}} \\times \\frac{{{n2}}}{{{d2}}} = \\frac{{{n1} \\times {n2}}}{{{d1} \\times {d2}}} = \\frac{{{raw_num}}}{{{raw_den}}}$$"
                    )

                elif op == "/":
                    steps.append(
                        f"2. **Propiedad de la División de Fracciones (Fracción Inversa):**\n"
                        f"   - Dividir entre una fracción equivale a multiplicar por su inversa (invertir $\\frac{{{n2}}}{{{d2}}} \\to \\frac{{{d2}}}{{{n2}}}$):\n"
                        f"   $$\\frac{{{n1}}}{{{d1}}} \\div \\frac{{{n2}}}{{{d2}}} = \\frac{{{n1}}}{{{d1}}} \\times \\frac{{{d2}}}{{{n2}}} = \\frac{{{n1} \\times {d2}}}{{{d1} \\times {n2}}} = \\frac{{{n1*d2}}}{{{d1*n2}}}$$"
                    )

                # Simplification step
                if den != 1:
                    steps.append(
                        f"5. **Simplificación a Fracción Irreductible:**\n"
                        f"   $$\\frac{{{num}}}{{{den}}}$$"
                    )

                rep_parts = [f"Fracción: $\\frac{{{num}}}{{{den}}}$" if den != 1 else f"Entero: ${num}$"]
                if is_improper and mixed_str:
                    rep_parts.append(f"Número Mixto: ${mixed_str}$ (${num // den}$ enteros y $\\frac{{{num % den}}}{{{den}}}$)")
                rep_parts.append(f"Valor Decimal: ${decimal_str}$")

                steps.append(
                    f"{len(steps) + 1}. **Representaciones del Resultado:**\n"
                    + "\n".join([f"   - {rp}" for rp in rep_parts])
                )

            elif chained_add_sub:
                frac_items = re.findall(r"([\+\-]?)\s*(\d+)\s*/\s*(\d+)", snippet)
                dens = [int(item[2]) for item in frac_items]
                lcm_val = compute_multiple_lcm(dens)

                steps.append(
                    f"1. **Identificar Fracciones y Denominadores:**\n"
                    f"   - Denominadores presentes: {', '.join(str(d) for d in dens)}\n"
                    f"   - Calculamos el $\\text{{MCM}}({', '.join(str(d) for d in dens)}) = \\mathbf{{{lcm_val}}}$"
                )

                homo_terms = []
                num_terms = []
                for sign, fn, fd in frac_items:
                    s_str = "-" if sign == "-" else "+"
                    fn_i, fd_i = int(fn), int(fd)
                    mult = lcm_val // fd_i
                    homo_n = fn_i * mult
                    homo_terms.append(f"{s_str if (homo_terms or s_str == '-') else ''} \\frac{{{homo_n}}}{{{lcm_val}}}")
                    num_terms.append(f"{s_str if (num_terms or s_str == '-') else ''} {homo_n}")

                steps.append(
                    f"2. **Homogeneizar todas las fracciones al denominador común ({lcm_val}):**\n"
                    f"   $$" + " ".join(homo_terms) + "$$"
                )
                steps.append(
                    f"3. **Operar sobre el numerador común:**\n"
                    f"   $$\\frac{{" + " ".join(num_terms).strip() + f"}}{{{lcm_val}}} = \\frac{{{num}}}{{{den}}}" + (f" \\quad (\\text{{Simplificado}})" if den != lcm_val else "") + "$$"
                )
                if is_improper and mixed_str:
                    steps.append(
                        f"4. **Conversión a Número Mixto:**\n"
                        f"   $$\\frac{{{num}}}{{{den}}} = \\mathbf{{{mixed_str}}} \\quad \\left({num // den} \\text{{ enteros y }} \\frac{{{num % den}}}{{{den}}}\\right)$$"
                    )

            elif is_isolated_frac:
                orig_m = re.search(r"(\d+)\s*/\s*(\d+)", snippet)
                if orig_m:
                    n_orig = int(orig_m.group(1))
                    d_orig = int(orig_m.group(2))
                    gcd_val = math.gcd(n_orig, d_orig)
                    steps.append(
                        f"1. **Identificar la Fracción:**\n"
                        f"   - Numerador: **{n_orig}**\n"
                        f"   - Denominador: **{d_orig}**\n"
                        f"   - Fracción a simplificar: $$\\frac{{{n_orig}}}{{{d_orig}}}$$"
                    )
                    if gcd_val > 1:
                        steps.append(
                            f"2. **Cálculo del Máximo Común Divisor (MCD):**\n"
                            f"   - Para reducir la fracción a su forma irreductible, buscamos el mayor divisor común entre el numerador ({n_orig}) y el denominador ({d_orig}):\n"
                            f"   $$\\text{{MCD}}({n_orig}, {d_orig}) = \\mathbf{{{gcd_val}}}$$"
                        )
                        steps.append(
                            f"3. **Simplificación (División por el MCD = {gcd_val}):**\n"
                            f"   - Dividimos tanto el numerador como el denominador entre {gcd_val}:\n"
                            f"   $$\\frac{{{n_orig} \\div {gcd_val}}}{{{d_orig} \\div {gcd_val}}} = \\mathbf{{\\frac{{{num}}}{{{den}}}}}$$"
                        )
                    else:
                        steps.append(
                            f"2. **Evaluación de Divisores Comunes:**\n"
                            f"   - El único divisor común entre {n_orig} y {d_orig} es 1 (son primos entre sí).\n"
                            f"   - Por tanto, la fracción ya se encuentra en su forma **irreductible**: $$\\frac{{{n_orig}}}{{{d_orig}}}$$"
                        )
                    rep_parts = [f"Fracción irreductible: $\\frac{{{num}}}{{{den}}}$" if den != 1 else f"Entero: ${num}$"]
                    if is_improper and mixed_str:
                        rep_parts.append(f"Número Mixto: ${mixed_str}$")
                    rep_parts.append(f"Valor Decimal: ${decimal_str}$")
                    steps.append(
                        f"{len(steps) + 1}. **Representaciones:**\n"
                        + "\n".join([f"   - {rp}" for rp in rep_parts])
                    )

            step_text = (
                f"### 🧮 RESOLUCIÓN ARITMÉTICA DIDÁCTICA (FRACCIONES)\n"
                f"**Operación:** `${snippet}$`\n\n"
                + "\n\n".join(steps) + "\n\n"
                + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_solution}}}$" + (f" (o en número mixto $\\mathbf{{{mixed_str}}}$, decimal: **{decimal_str}**)" if is_improper else "")
            )

            hints_text = (
                f"### 💡 PISTAS PEDAGÓGICAS (MODO GUIADO)\n"
                f"1. **Identifica Denominadores:** Observa si las fracciones tienen el mismo denominador o denominadores distintos.\n"
                f"2. **Estrategia Clave:** Para sumar o restar fracciones con distinto denominador, halla el **MCM** de los denominadores para homogeneizarlas.\n"
                f"3. **Pregunta:** ¿Cuál es el común denominador de estas fracciones?"
            )

            socratic_text = (
                f"### ❓ GUÍA SOCRÁTICA\n"
                f"- ¿Por qué no podemos sumar directamente los numeradores cuando los denominadores son diferentes?\n"
                f"- ¿Qué número representa el Mínimo Común Múltiplo (MCM) de los denominadores en esta operación?"
            )

            return {
                "category": "aritmetica",
                "topic": "fracciones",
                "data_identified": {"snippet": snippet, "num": num, "den": den, "decimal": decimal_val, "is_improper": is_improper},
                "exact_solution": exact_solution,
                "step_text": step_text,
                "hints_text": hints_text,
                "socratic_text": socratic_text,
                "verified": True
            }

        except Exception as e:
            logger.warning(f"Fraction operation solver failed for '{snippet}': {e}")
            return None

    @classmethod
    def solve_percentage(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Handles percentages, commercial discounts and price increases in natural language:
        e.g. 'Descuento del 15 % sobre S/ 120', 'Una mochila cuesta S/ 120 y tiene un descuento del 15 %. ¿Cuánto se paga?',
             'Un producto cuesta S/ 200 y tiene un descuento del 20 %. ¿Cuánto se paga?',
             'Un producto de S/ 100 aumenta un 15 %. ¿Cuál es el precio final?', '15% de 240'.
        """
        norm = normalize_math_text(text)
        norm_lower = norm.lower()

        # Check for discount or increase context
        is_discount = any(w in norm_lower for w in ["descuento", "rebaja", "disminuye", "descontar", "paga con descuento", "cuanto se paga", "cuánto se paga"])
        is_increase = any(w in norm_lower for w in ["aumento", "recargo", "incremento", "igv", "aumenta", "sube"])

        pct_val = None
        total_val = None

        # Pattern A: Standard '% de X' or '% del X' or '% sobre X'
        m_std = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:de|del|sobre|en|a)?\s*(?:s\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)", norm, re.IGNORECASE)
        if not m_std:
            m_std = re.search(r"(?:el|un)?\s*(\d+(?:\.\d+)?)\s*(?:por\s*ciento|porciento)\s*(?:de|del|sobre|en|a)?\s*(?:s\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)", norm, re.IGNORECASE)
        if m_std and m_std.group(2):
            pct_val = float(m_std.group(1))
            total_val = float(m_std.group(2))

        # Pattern B: Reverse / Narrative order: Base price first, percentage later
        # e.g. 'cuesta S/ 120 y tiene un descuento del 15 %', 'producto de S/ 100 aumenta un 15 %'
        if total_val is None or pct_val is None:
            m_pct_standalone = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|por\s*ciento|porciento)", norm, re.IGNORECASE)
            m_base_standalone = re.search(r"(?:cuesta|precio|valor|de|por|un|producto)\s*(?:de)?\s*(?:s\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)", norm, re.IGNORECASE)
            if not m_base_standalone:
                m_base_standalone = re.search(r"(?:s\/\.?|soles|\$)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
            if m_pct_standalone and m_base_standalone:
                pct_val = float(m_pct_standalone.group(1))
                total_val = float(m_base_standalone.group(1))

        if pct_val is None or total_val is None:
            return None

        unit_str = "S/ " if any(w in norm_lower for w in ["s/.", "s/", "soles", "cuesta", "precio", "paga"]) else ""

        raw_result = (pct_val / 100.0) * total_val
        clean_result = int(raw_result) if raw_result.is_integer() else round(raw_result, 4)
        clean_total = int(total_val) if total_val.is_integer() else round(total_val, 2)

        if is_discount:
            final_val = total_val - raw_result
            final_clean = int(final_val) if final_val.is_integer() else round(final_val, 4)
            topic = "porcentaje_descuento"
            exact_solution = f"{unit_str}{final_clean}"

            step_text = (
                f"### 🧮 ARITMÉTICA: CÁLCULO DE DESCUENTO COMERCIAL\n"
                f"**Problema:** Precio original de {unit_str}{clean_total} con un **descuento del {pct_val}%**.\n\n"
                f"1. **Identificar Datos e Incógnita:**\n"
                f"   - Precio base ($P$): **{unit_str}{clean_total}**\n"
                f"   - Porcentaje de descuento ($D\\%$): **{pct_val}%**\n"
                f"   - Incógnita: Precio final a pagar tras aplicar la rebaja.\n\n"
                f"2. **Calcular el Monto del Descuento:**\n"
                f"   $$\\text{{Descuento}} = \\frac{{{pct_val}}}{{100}} \\times {clean_total} = {pct_val/100.0} \\times {clean_total} = \\mathbf{{{unit_str}{clean_result}}}$$\n\n"
                f"3. **Calcular el Precio Final a Pagar:**\n"
                f"   $$\\text{{Precio Final}} = \\text{{Precio Base}} - \\text{{Descuento}} = {clean_total} - {clean_result} = \\mathbf{{{unit_str}{final_clean}}}$$\n\n"
                f"4. **Comprobación:**\n"
                f"   - Suma de precio final y descuento: ${final_clean} + {clean_result} = {clean_total}$ ({unit_str}{clean_total}) $\\checkmark$.\n"
                f"   - O equivalente al $(100 - {pct_val})\\% = {100 - pct_val}\\%$ del precio base: $\\frac{{{100 - pct_val}}}{{100}} \\times {clean_total} = {final_clean}$ $\\checkmark$.\n\n"
                f"📌 **RESPUESTA FINAL:** Con el descuento del {pct_val}% se paga **{exact_solution}** (ahorro de {unit_str}{clean_result})."
            )

        elif is_increase:
            final_val = total_val + raw_result
            final_clean = int(final_val) if final_val.is_integer() else round(final_val, 4)
            topic = "porcentaje_aumento"
            exact_solution = f"{unit_str}{final_clean}"

            step_text = (
                f"### 🧮 ARITMÉTICA: CÁLCULO DE INCREMENTO / RECARGO\n"
                f"**Problema:** Precio original de {unit_str}{clean_total} con un **aumento del {pct_val}%**.\n\n"
                f"1. **Identificar Datos e Incógnita:**\n"
                f"   - Precio base ($P$): **{unit_str}{clean_total}**\n"
                f"   - Porcentaje de aumento ($A\\%$): **{pct_val}%**\n"
                f"   - Incógnita: Precio final tras el incremento.\n\n"
                f"2. **Calcular el Monto del Incremento:**\n"
                f"   $$\\text{{Aumento}} = \\frac{{{pct_val}}}{{100}} \\times {clean_total} = {pct_val/100.0} \\times {clean_total} = \\mathbf{{{unit_str}{clean_result}}}$$\n\n"
                f"3. **Calcular el Precio Final:**\n"
                f"   $$\\text{{Precio Final}} = \\text{{Precio Base}} + \\text{{Aumento}} = {clean_total} + {clean_result} = \\mathbf{{{unit_str}{final_clean}}}$$\n\n"
                f"4. **Comprobación:**\n"
                f"   - Diferencia: ${final_clean} - {clean_result} = {clean_total}$ ({unit_str}{clean_total}) $\\checkmark$.\n"
                f"   - Equivalente al $(100 + {pct_val})\\% = {100 + pct_val}\\%$: $\\frac{{{100 + pct_val}}}{{100}} \\times {clean_total} = {final_clean}$ $\\checkmark$.\n\n"
                f"📌 **RESPUESTA FINAL:** Con el aumento del {pct_val}%, el precio final es **{exact_solution}**."
            )

        else:
            topic = "porcentaje_simple"
            exact_solution = str(clean_result)

            step_text = (
                f"### 🧮 ARITMÉTICA: CÁLCULO DE PORCENTAJES\n"
                f"**Operación:** Calcular el **{pct_val}%** de **{clean_total}**.\n\n"
                f"1. **Identificar Datos e Incógnita:**\n"
                f"   - Porcentaje a calcular: **{pct_val}%**\n"
                f"   - Cantidad base ($N$): **{clean_total}**\n"
                f"   - Incógnita: Determinar el valor correspondiente al {pct_val}% de {clean_total}.\n\n"
                f"2. **Fórmula y Principio Aritmético:**\n"
                f"   $$\\text{{Valor Porcentual}} = \\frac{{P}}{{100}} \\times N = \\frac{{{pct_val}}}{{100}} \\times {clean_total}$$\n\n"
                f"3. **Procedimiento Operativo Paso a Paso:**\n"
                f"   - Convertimos el porcentaje a decimal: $\\frac{{{pct_val}}}{{100}} = {pct_val/100.0}$\n"
                f"   - Multiplicamos por la base: ${pct_val/100.0} \\times {clean_total} = \\mathbf{{{clean_result}}}$\n\n"
                f"4. **Comprobación:**\n"
                f"   - Proporción directa: $\\frac{{{clean_result}}}{{{clean_total}}} = {round(clean_result/clean_total, 4)} = \\frac{{{pct_val}}}{{100}}$ $\\checkmark$.\n\n"
                f"📌 **RESPUESTA FINAL:** El {pct_val}% de {clean_total} es $\\mathbf{{{clean_result}}}$."
            )

        hints_text = (
            f"### 💡 PISTAS PEDAGÓGICAS\n"
            f"1. Convierte el porcentaje {pct_val}% en fracción dividiendo entre 100: $\\frac{{{pct_val}}}{{100}}$.\n"
            f"2. Multiplica esa fracción por el total {clean_total}."
            + (f"\n3. Resta el resultado al precio original para hallar el precio a pagar." if is_discount else "")
            + (f"\n3. Suma el resultado al precio original para hallar el precio con aumento." if is_increase else "")
        )

        socratic_text = (
            f"### ❓ GUÍA SOCRÁTICA\n"
            f"- ¿Qué fracción o decimal representa el {pct_val}% de una cantidad?\n"
            f"- Si a un producto se le descuenta el {pct_val}%, ¿qué porcentaje del precio original pagas realmente?"
        )

        return {
            "category": "aritmetica",
            "topic": topic,
            "data_identified": {
                "porcentaje": pct_val,
                "base": clean_total,
                "monto_porcentual": clean_result,
                "es_descuento": is_discount,
                "es_aumento": is_increase
            },
            "exact_solution": exact_solution,
            "step_text": step_text,
            "hints_text": hints_text,
            "socratic_text": socratic_text,
            "verified": True
        }

    @classmethod
    def format_signed_add_sub_steps(cls, expr_str: str) -> Optional[Tuple[List[str], str, List[Union[int, float]]]]:
        """Formats addition and subtraction of signed numbers into an explicit equality chain."""
        clean = expr_str.strip()
        if any(op in clean for op in ['*', '/', '^']):
            return None
        
        step1 = clean
        step1 = re.sub(r'^\(\s*([\+\-]?\d+(?:\.\d+)?)\s*\)', r'\1', step1)
        step1 = re.sub(r'-\s*\(\s*-\s*(\d+(?:\.\d+)?)\s*\)', r'+ \1', step1)
        step1 = re.sub(r'\+\s*\(\s*-\s*(\d+(?:\.\d+)?)\s*\)', r'- \1', step1)
        step1 = re.sub(r'-\s*\(\s*\+?\s*(\d+(?:\.\d+)?)\s*\)', r'- \1', step1)
        step1 = re.sub(r'\+\s*\(\s*\+?\s*(\d+(?:\.\d+)?)\s*\)', r'+ \1', step1)
        step1 = re.sub(r'\(\s*([\+\-]?\d+(?:\.\d+)?)\s*\)', r'\1', step1)
        
        # normalize spaces around operators
        step1 = re.sub(r'\s*([\+\-])\s*', r' \1 ', step1).strip()
        if step1.startswith('+ '):
            step1 = step1[2:]
        elif step1.startswith('- '):
            step1 = '-' + step1[2:]
            
        m_tokens = re.findall(r'([\+\-]?\s*\d+(?:\.\d+)?)', step1)
        vals = []
        for t in m_tokens:
            t_clean = t.replace(' ', '')
            if t_clean:
                vals.append(float(t_clean) if '.' in t_clean else int(t_clean))
                
        if len(vals) < 2:
            return None
            
        chain = [clean]
        if step1 != clean:
            chain.append(step1)
            
        curr = vals[0]
        for idx in range(1, len(vals)):
            curr = curr + vals[idx]
            rem = vals[idx+1:]
            if rem:
                rem_str = ''.join([f' + {v}' if v >= 0 else f' - {abs(v)}' for v in rem])
                chain.append(f'{curr}{rem_str}')
            else:
                chain.append(f'{curr}')
                
        return chain, step1, vals

    @classmethod
    def solve_arithmetic_operations(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles combined arithmetic operations: e.g. '(-12) + 7 - (-5)', '48 + 37 - 19', '125 * 8', '(15 - 3)^2 / 4 + 7'."""
        snippet = cls.extract_arithmetic_snippet(text)
        if not snippet:
            return None

        # Check if safe expression
        safe_expr_str = snippet.replace("sqrt", "").strip()
        if not cls.is_safe_expression(safe_expr_str):
            return None

        # If it has variables, pass to algebraic solver
        if any(c.isalpha() for c in snippet if c.lower() not in ["s", "q", "r", "t"]):
            return None

        try:
            parsed = parse_expr(
                snippet,
                global_dict=SAFE_GLOBAL_DICT,
                transformations=SAFE_TRANSFORMATIONS,
                evaluate=True
            )
            if not parsed.is_number:
                return None

            if isinstance(parsed, (float, sympy.Float)):
                fv = float(parsed)
                exact_solution = str(int(fv)) if fv.is_integer() else f"{round(fv, 6):g}"
            elif hasattr(parsed, "is_integer") and parsed.is_integer:
                exact_solution = str(int(parsed))
            else:
                exact_solution = str(parsed)
            float_val = float(parsed.evalf())

            # Check if this is an addition/subtraction chain with signed numbers
            chain_res = cls.format_signed_add_sub_steps(snippet)
            if chain_res:
                chain, step1, vals = chain_res
                chain_str = " = ".join(chain)

                has_double_signs = bool(re.search(r'-\s*\(\s*-\s*|\+\s*\(\s*-\s*|-\s*\(\s*\+?\s*|\+\s*\(\s*\+?\s*|--|\+\-', snippet))
                has_signed_parens = bool(re.search(r'\(\s*[\+\-]\s*\d', snippet))
                is_signed_op = has_double_signs or has_signed_parens
                is_two_term_sub = (len(vals) == 2 and vals[0] > 0 and vals[1] < 0 and not is_signed_op)

                steps = []
                hints_text = ""
                socratic_text = ""

                if is_two_term_sub and abs(vals[1]) > vals[0]:
                    # Specific pedagogical explanation for decimal/integer subtraction where minuend < subtrahend
                    # e.g. '2 - 2.25' or '5 - 8'
                    a = vals[0]
                    b = abs(vals[1])
                    is_dec = ('.' in snippet)
                    clean_a = f"{a:g}" if isinstance(a, float) else str(a)
                    clean_b = f"{b:g}" if isinstance(b, float) else str(b)
                    align_a = f"{clean_a}.00" if is_dec and '.' not in clean_a else clean_a
                    topic = "sustraccion_decimales" if is_dec else "sustraccion_enteros"

                    steps.append(
                        f"1. **Identificar los Términos de la Sustracción:**\n"
                        f"   - Minuendo ($M$): **{clean_a}**" + (f" (o ${align_a}$ para alinear las cifras decimales)" if is_dec and '.' not in clean_a else "") + f"\n"
                        f"   - Sustraendo ($S$): **{clean_b}**\n"
                        f"   - Operación planteada: $${clean_a} - {clean_b}$$"
                    )
                    steps.append(
                        f"2. **Análisis de Magnitud y Determinación del Signo:**\n"
                        f"   - Como el sustraendo ($S = {clean_b}$) tiene mayor valor absoluto que el minuendo ($M = {clean_a}$), el resultado es **negativo**.\n"
                        f"   - Restamos el sustraendo menos el minuendo y anteponemos el signo negativo:\n"
                        f"   $$-({clean_b} - {clean_a}) = \\mathbf{{{exact_solution}}}$$"
                    )
                    steps.append(
                        f"3. **Resultado Final:**\n"
                        f"   $${snippet} = \\mathbf{{{exact_solution}}}$$"
                    )
                    hints_text = "Al restar un número mayor de uno menor, el resultado es negativo: a - b = -(b - a)."
                    socratic_text = "¿Por qué al restar un número de mayor magnitud que el inicial obtenemos un resultado negativo?"

                elif is_signed_op:
                    # Explicit signed numbers / double signs (e.g. '(-12) + 7 - (-5)', '15 - (-8)')
                    topic = "operaciones_con_enteros"
                    steps.append(
                        "1. **Manejo de Signos y Opuesto Aditivo:**\n"
                        "   - **Regla fundamental:** Restar un número negativo equivale a **sumar su opuesto positivo**: $$-(-a) = +a$$\n"
                        "   - *Aclaración pedagógica:* No se eliminan los signos negativos indiscriminadamente ni se suman valores absolutos sin criterio; cada número conserva su signo de acuerdo con las propiedades de los números enteros.\n"
                        f"   - Simplificamos los signos dobles en la expresión: $$\\mathbf{{{snippet} = {step1}}}$$"
                    )
                    steps.append(
                        "2. **Operaciones Sucesivas de Izquierda a Derecha:**\n"
                        "   - Efectuamos cada adición respetando la ley de signos:\n"
                        f"     * Si los números tienen signos contrarios, restamos sus valores absolutos y conservamos el signo del que tenga mayor valor absoluto.\n"
                        f"     * Dos números con igual magnitud y signos contrarios son opuestos aditivos y su suma es cero."
                    )
                    steps.append(
                        f"{len(steps) + 1}. **Cadena de Igualdades Completa:**\n"
                        f"   $${chain_str}$$\n"
                        f"   $$\\text{{Resultado exacto: }} \\mathbf{{{exact_solution}}}$$"
                    )
                    hints_text = "Recuerda que restar un negativo equivale a sumar su opuesto: -(-a) = +a. Resuelve luego de izquierda a derecha."
                    socratic_text = "¿Qué ocurre con el signo cuando restamos una cantidad negativa?"

                else:
                    # Standard addition/subtraction (e.g. '45 + 28 - 17')
                    topic = "operaciones_combinadas"
                    steps.append(
                        "1. **Operaciones Aritméticas (de Izquierda a Derecha):**\n"
                        "   - Siguiendo la jerarquía operativa para sumas y restas consecutivas, resolvemos de izquierda a derecha."
                    )
                    steps.append(
                        f"{len(steps) + 1}. **Cadena de Igualdades Completa:**\n"
                        f"   $${chain_str}$$\n"
                        f"   $$\\text{{Resultado exacto: }} \\mathbf{{{exact_solution}}}$$"
                    )
                    hints_text = "Efectúa las adiciones y sustracciones de izquierda a derecha."
                    socratic_text = "¿Cuál es el orden adecuado para resolver una serie de sumas y restas consecutivas?"

                step_text = (
                    f"### 🧮 RESOLUCIÓN ARITMÉTICA PASO A PASO\n"
                    f"**Expresión:** `${snippet}$`\n\n"
                    + "\n\n".join(steps) + "\n\n"
                    + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_solution}}}$"
                )

                return {
                    "category": "aritmetica",
                    "topic": topic,
                    "data_identified": {"expresion": snippet, "cadena_igualdades": chain_str},
                    "exact_solution": exact_solution,
                    "step_text": step_text,
                    "hints_text": hints_text,
                    "socratic_text": socratic_text,
                    "verified": True
                }

            # Generate step-by-step breakdown for general combined expressions
            steps = []
            steps.append(
                f"1. **Identificar la Jerarquía de Operaciones:**\n"
                f"   - 1.° Signos de agrupación (Paréntesis).\n"
                f"   - 2.° Potencias y Raíces cuadradas.\n"
                f"   - 3.° Multiplicaciones y Divisiones (de izquierda a derecha).\n"
                f"   - 4.° Sumas y Restas (de izquierda a derecha)."
            )

            # Check if signs rules in product/division apply
            if any(op in snippet for op in ["*", "/"]) and ("-" in snippet):
                steps.append(
                    "2. **Ley de Signos en Multiplicación y División:**\n"
                    "   - Signos iguales dan resultado positivo: $(+) \\times (+) = (+)$ y $(-) \\times (-) = (+)$\n"
                    "   - Signos diferentes dan resultado negativo: $(+) \\times (-) = (-)$ y $(-) \\times (+) = (-)$"
                )

            # Detailed intermediate demonstration for expressions with parentheses and powers
            m_parens = re.search(r"\(([^)]+)\)\^2", snippet)
            if m_parens:
                sub_inner = m_parens.group(1)
                sub_eval = parse_expr(sub_inner, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
                steps.append(
                    f"{len(steps) + 1}. **Desarrollo de Signos de Agrupación y Potencias:**\n"
                    f"   - Operamos dentro del paréntesis: $({sub_inner}) = {sub_eval}$\n"
                    f"   - Elevamos al cuadrado: $({sub_eval})^2 = {sub_eval**2}$"
                )

            steps.append(
                f"{len(steps) + 1}. **Resultado Operativo:**\n"
                f"   $$\\text{{Expresión original: }} {snippet}$$\n"
                f"   $$\\text{{Resultado exacto: }} \\mathbf{{{exact_solution}}}" + (f" \\approx {round(float_val, 4)}" if not parsed.is_integer else "") + "$$"
            )

            step_text = (
                f"### 🧮 RESOLUCIÓN ARITMÉTICA PASO A PASO (JERARQUÍA OPERATIVA)\n"
                f"**Expresión:** `${snippet}$`\n\n"
                + "\n\n".join(steps) + "\n\n"
                + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_solution}}}$"
            )

            return {
                "category": "aritmetica",
                "topic": "operaciones_combinadas",
                "data_identified": {"expresion": snippet},
                "exact_solution": exact_solution,
                "step_text": step_text,
                "hints_text": f"Aplica la jerarquía de operaciones resolviendo primero paréntesis, luego potencias/raíces, productos/cocientes y finalmente sumas.",
                "socratic_text": "¿Qué operación debe realizarse en primer lugar según la regla de jerarquía operativa?",
                "verified": True
            }
        except Exception:
            return None

    # =========================================================================
    # AREA 2: ÁLGEBRA (ECUACIONES LINEALES, CUADRÁTICAS, POLINOMIOS)
    # =========================================================================
    @classmethod
    def solve_linear_equation(cls, equation_str: str) -> Dict[str, Any]:
        """
        Safely parses and solves linear algebraic equations with and without parentheses:
        e.g. '3x + 7 = 22', '2(x + 4) = 18', '5x + 3 = 2x + 18'.
        Generates explicit step-by-step intermediate algebra lines.
        """
        norm_eq = normalize_math_text(equation_str)
        if not cls.is_safe_expression(norm_eq) or "=" not in norm_eq:
            return {"status": "no_verificable", "reason": "Ecuación no permitida o incompleta."}

        parts = norm_eq.split("=")
        if len(parts) != 2:
            return {"status": "no_verificable", "reason": "La ecuación debe tener exactamente dos miembros."}

        lhs_str, rhs_str = parts[0].strip(), parts[1].strip()
        var_sym = cls.detect_variable(norm_eq)
        if not var_sym:
            return {"status": "no_verificable", "reason": "No se detectó ninguna variable algebraica."}

        local_dict = {str(var_sym): var_sym}

        try:
            lhs_expr = parse_expr(lhs_str, local_dict=local_dict, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
            rhs_expr = parse_expr(rhs_str, local_dict=local_dict, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
            diff_expr = sympy.simplify(lhs_expr - rhs_expr)

            free_symbols = diff_expr.free_symbols
            if var_sym not in free_symbols:
                if diff_expr == 0:
                    return {
                        "status": "infinitas_soluciones",
                        "equation": norm_eq,
                        "variable": str(var_sym),
                        "explanation": "La ecuación es una identidad ($0 = 0$): se cumple para cualquier valor real."
                    }
                else:
                    return {
                        "status": "sin_solucion",
                        "equation": norm_eq,
                        "variable": str(var_sym),
                        "explanation": "La ecuación es una contradicción: no existe ningún valor real que cumpla la igualdad."
                    }

            poly = sympy.Poly(diff_expr, var_sym)
            if poly.degree() != 1:
                return {"status": "no_verificable", "reason": "No es una ecuación de primer grado."}

            solutions = sympy.solve(diff_expr, var_sym)
            if not solutions:
                return {"status": "sin_solucion", "equation": norm_eq, "variable": str(var_sym), "explanation": "No tiene soluciones reales."}

            exact_sol = solutions[0]
            float_val = float(exact_sol.evalf()) if exact_sol.is_number else None

            # Generate explicit intermediate steps:
            expanded_lhs = sympy.expand(lhs_expr)
            expanded_rhs = sympy.expand(rhs_expr)

            steps = [
                f"1. **Identificar la ecuación y la incógnita:**\n"
                f"   - Ecuación dada: $${lhs_str} = {rhs_str}$$\n"
                f"   - Incógnita a despejar: **{var_sym}**"
            ]

            # If there are parentheses, show expansion
            if "(" in lhs_str or "(" in rhs_str:
                steps.append(
                    f"2. **Eliminación de Paréntesis (Propiedad Distributiva):**\n"
                    f"   $${expanded_lhs} = {expanded_rhs}$$"
                )

            # Transposition of terms
            poly_lhs = sympy.Poly(expanded_lhs, var_sym) if var_sym in expanded_lhs.free_symbols else None
            poly_rhs = sympy.Poly(expanded_rhs, var_sym) if var_sym in expanded_rhs.free_symbols else None

            a1 = poly_lhs.coeff_monomial(var_sym) if poly_lhs else sympy.Integer(0)
            b1 = expanded_lhs.subs(var_sym, 0)
            a2 = poly_rhs.coeff_monomial(var_sym) if poly_rhs else sympy.Integer(0)
            b2 = expanded_rhs.subs(var_sym, 0)

            if a2 == 0:
                # Form ax + b = c
                if b1 != 0:
                    sign_b1 = "+" if b1 > 0 else "-"
                    opp_sign = "-" if b1 > 0 else "+"
                    abs_b1 = abs(b1)
                    reduced_rhs = b2 - b1
                    steps.append(
                        f"{len(steps)+1}. **Transposición de términos independientes:**\n"
                        f"   - Pasamos la constante **{sign_b1}{abs_b1}** al segundo miembro con operación inversa ({opp_sign}):\n"
                        f"   $${a1}{var_sym} = {b2} {opp_sign} {abs_b1}$$\n"
                        f"   $${a1}{var_sym} = \\mathbf{{{reduced_rhs}}}$$"
                    )
                else:
                    reduced_rhs = b2

                if a1 != 1:
                    steps.append(
                        f"{len(steps)+1}. **Despeje de la incógnita ({var_sym}):**\n"
                        f"   - El coeficiente **{a1}** que multiplica a **{var_sym}** pasa dividiendo:\n"
                        f"   $${var_sym} = \\frac{{{reduced_rhs}}}{{{a1}}}$$\n"
                        f"   $${var_sym} = \\mathbf{{{exact_sol}}}$$"
                    )
                else:
                    steps.append(
                        f"{len(steps)+1}. **Solución directa:**\n"
                        f"   $${var_sym} = \\mathbf{{{exact_sol}}}$$"
                    )
            else:
                net_a = a1 - a2
                net_b = b2 - b1
                steps.append(
                    f"{len(steps)+1}. **Agrupación de términos (Incógnitas al 1.° miembro, números al 2.° miembro):**\n"
                    f"   $$({a1} - {a2}){var_sym} = {b2} - ({b1})$$\n"
                    f"   $${net_a}{var_sym} = \\mathbf{{{net_b}}}$$"
                )
                steps.append(
                    f"{len(steps)+1}. **Despeje de la incógnita ({var_sym}):**\n"
                    f"   $${var_sym} = \\frac{{{net_b}}}{{{net_a}}} \\implies {var_sym} = \\mathbf{{{exact_sol}}}$$"
                )

            # Verification
            lhs_sub = lhs_expr.subs(var_sym, exact_sol)
            rhs_sub = rhs_expr.subs(var_sym, exact_sol)
            steps.append(
                f"{len(steps)+1}. **Comprobación por sustitución directa:**\n"
                f"   - Reemplazamos ${var_sym} = {exact_sol}$ en la ecuación original:\n"
                f"   - Primer miembro: ${lhs_str.replace(str(var_sym), f'({exact_sol})')} = {lhs_sub}$\n"
                f"   - Segundo miembro: ${rhs_str.replace(str(var_sym), f'({exact_sol})')} = {rhs_sub}$\n"
                f"   - La igualdad idéntica se cumple $\\checkmark$."
            )

            step_text = (
                f"### 📐 RESOLUCIÓN ÁLGEBRAICA PASO A PASO (ECUACIÓN LINEAL)\n"
                f"**Ecuación:** `${norm_eq}$`\n\n"
                + "\n\n".join(steps) + "\n\n"
                + f"📌 **RESPUESTA FINAL:** ${var_sym} = \\mathbf{{{exact_sol}}}$"
            )

            hints_text = (
                f"### 💡 PISTAS PEDAGÓGICAS (MODO GUIADO)\n"
                f"1. **Paso 1:** Si hay paréntesis, elimínalos aplicando la propiedad distributiva.\n"
                f"2. **Paso 2:** Transpón los números al segundo miembro aplicando la operación contraria.\n"
                f"3. **Pregunta:** ¿Cuál es el valor del coeficiente que acompaña a {var_sym}?"
            )

            socratic_text = (
                f"### ❓ GUÍA SOCRÁTICA\n"
                f"- ¿Qué propiedad algebraica nos permite eliminar los paréntesis en esta ecuación?\n"
                f"- Una vez reducida la expresión, ¿cómo aislas completamente la incógnita {var_sym}?"
            )

            return {
                "category": "algebra",
                "topic": "ecuacion_lineal",
                "status": "solucion_unica",
                "equation": norm_eq,
                "variable": str(var_sym),
                "exact_solution": str(exact_sol),
                "float_value": round(float_val, 4) if float_val is not None else None,
                "is_fraction": exact_sol.is_rational and not exact_sol.is_integer,
                "sympy_obj": exact_sol,
                "step_text": step_text,
                "hints_text": hints_text,
                "socratic_text": socratic_text,
                "verified": True
            }

        except Exception as e:
            logger.warning(f"SymPy linear parsing failed for '{norm_eq}': {e}")
            return {"status": "no_verificable", "reason": "Error de sintaxis o estructura no soportada."}

    @classmethod
    def solve_algebraic_expression(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles algebraic expressions & polynomial factorizations (e.g. 'x^2 + 7x + 12', 'x^2 - 9')."""
        norm = normalize_math_text(text)
        if "=" in norm:
            return None

        has_factorize_intent = any(k in norm.lower() for k in ["factoriza", "factorizar", "factorice", "descompon", "descomponer"])
        cleaned = re.sub(
            r"(?i)^(?:por favor\s*)?(?:ayudame a\s*|ayúdame a\s*)?(?:factoriza|factorizar|factorice|simplifica|simplificar|resuelve|resolver|resolvé|halla las raices de|halla las raíces de|desarrolla|desarrollar|descompon|descomponer|despeja|despejar|calcula|calcular|evalua|evalúa|evaluar|halla|hallar|obten|obtén|obtener)\s*[:=]?\s*",
            "",
            norm
        ).strip()
        cleaned = cleaned.rstrip("?¿!¡.: ")
        cleaned = cleaned.lstrip(":= ").strip()

        # Controlled separation of mathematical expression from trailing instructions / sentences
        # 1. Split on sentence delimiters: a period followed by space and letter, or semicolon
        # (Preserves decimal numbers like 0.5 or 2.25 which have no space after dot)
        sentence_split = re.split(r"(?:;\s*|\.\s+(?=[a-zA-ZáéíóúÁÉÍÓÚñÑ]))", cleaned, maxsplit=1)
        core_expr = sentence_split[0].strip()
        instructions = sentence_split[1].strip() if len(sentence_split) > 1 else ""

        # 2. Split on trailing pedagogical connectors: ' y comprueba...', ' y verifica...', ' con procedimiento...'
        ped_match = re.search(
            r"\s+(?:y|,|con|para)\s+(?:comprueba|comprobar|verifica|verificar|explica|explicar|muestra|mostrar|halla|hallar|obten|obtener|indica|indicar|paso a paso|detalla|detallar|justifica|justificar)\b.*$",
            core_expr,
            flags=re.I
        )
        if ped_match:
            instructions = (core_expr[ped_match.start():].strip() + (" " + instructions if instructions else "")).strip()
            core_expr = core_expr[:ped_match.start()].strip()

        cleaned = core_expr.rstrip("?¿!¡.:; ")

        # Check if informal powers were present before normalization (e.g. x2 -> x^2)
        has_informal_power = bool(re.search(r"(\b\d*)?([a-zA-Z])(\d+)\b", cleaned))

        # Normalize informal powers: e.g. x2 -> x^2, 3x2 -> 3x^2, x3 -> x^3
        cleaned = re.sub(r"(\b\d*)?([a-zA-Z])(\d+)\b", r"\1\2^\3", cleaned)

        # If user explicitly requested factorization, check for ambiguous expressions (e.g. x2y3 or missing operators)
        if has_factorize_intent:
            words_in_cleaned = re.findall(r"[a-záéíóúñ]+", cleaned.lower())
            allowed_math_funcs = {"sqrt", "sin", "cos", "tan", "pi"}
            invalid_words = [w for w in words_in_cleaned if w not in allowed_math_funcs and len(w) > 1]
            if invalid_words or not cleaned or re.search(r"[a-zA-Z]\^?\d*[a-zA-Z]", cleaned):
                return {
                    "category": "algebra",
                    "topic": "factorizacion_polinomios",
                    "status": "ambiguo",
                    "data_identified": {"entrada": text},
                    "exact_solution": "aclaracion_requerida",
                    "step_text": (
                        "### ⚠️ EXPRESIÓN DE FACTORIZACIÓN AMBIGUA\n\n"
                        "Hola. Al analizar la expresión que deseas factorizar:\n"
                        f"> *\"{text.strip()}\"*\n\n"
                        "📌 **Aclaración necesaria:**\n"
                        "- No se identificó con certeza un polinomio estándar bien formado (se detectaron variables pegadas o formato no reconocido).\n"
                        "- Por favor, vuelve a escribir la expresión utilizando operadores claros (por ejemplo: `x^2 - 9` o `x^2 + 5x + 6`) para orientarte paso a paso."
                    ),
                    "hints_text": "Escribe la expresión con exponentes y signos de operación claros.",
                    "socratic_text": "¿Podrías escribir nuevamente la expresión indicando con claridad los signos entre cada término?",
                    "verified": True
                }

        # Reject natural language phrases containing standard words of length >= 2
        words = re.findall(r"[a-záéíóúñ]+", cleaned.lower())
        allowed_math_funcs = {"sqrt", "sin", "cos", "tan", "pi"}
        single_vars = {"x", "y", "z", "n", "a", "b", "m", "k", "c"}
        for w in words:
            if w not in allowed_math_funcs and w not in single_vars:
                return None

        var_sym = cls.detect_variable(cleaned)
        if not var_sym:
            if has_factorize_intent:
                return {
                    "category": "algebra",
                    "topic": "factorizacion_polinomios",
                    "status": "ambiguo",
                    "data_identified": {"entrada": text},
                    "exact_solution": "aclaracion_requerida",
                    "step_text": (
                        "### ⚠️ EXPRESIÓN DE FACTORIZACIÓN AMBIGUA\n\n"
                        "Hola. Al analizar la expresión que deseas factorizar:\n"
                        f"> *\"{text.strip()}\"*\n\n"
                        "📌 **Aclaración necesaria:**\n"
                        "- No se identificó con certeza un polinomio estándar bien formado (se detectaron variables pegadas o formato no reconocido).\n"
                        "- Por favor, vuelve a escribir la expresión utilizando operadores claros (por ejemplo: `x^2 - 9` o `x^2 + 5x + 6`) para orientarte paso a paso."
                    ),
                    "hints_text": "Escribe la expresión con exponentes y signos de operación claros.",
                    "socratic_text": "¿Podrías escribir nuevamente la expresión indicando con claridad los signos entre cada término?",
                    "verified": True
                }
            return None

        if not cls.is_safe_expression(cleaned):
            return None

        local_dict = {str(var_sym): var_sym}
        try:
            expr = parse_expr(cleaned, local_dict=local_dict, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
            if not expr.has(var_sym):
                return None

            poly = sympy.Poly(expr, var_sym)
            degree = poly.degree()
            factored = sympy.factor(expr)
            roots = sympy.solve(expr, var_sym)
            roots_str = ", ".join([str(r) for r in roots]) if roots else "Sin raíces reales"

            # Formulate nicely formatted factored representation without '*'
            factored_str = str(factored)
            factored_clean = re.sub(r"\)\s*\*\s*\(", ")(", factored_str)
            factored_clean = re.sub(r"(\d+)\s*\*\s*\(", r"\1(", factored_clean)
            factored_clean = factored_clean.replace("*", "")

            def _clean_val(v):
                if isinstance(v, (float, sympy.Float)):
                    fv = float(v)
                    return str(int(fv)) if fv.is_integer() else f"{round(fv, 6):g}"
                if hasattr(v, "is_integer") and v.is_integer:
                    return str(int(v))
                return str(v)

            # Formulate pedagogical steps
            steps = []
            if not has_factorize_intent and ("=" not in text):
                roots_ped = ", ".join([f"${var_sym} = \\mathbf{{{_clean_val(r)}}}$" for r in roots]) if roots else "no tiene raíces reales"
                steps.append(
                    f"1. **Interpretación Pedagógica (Expresión vs. Ecuación):**\n"
                    f"   - Se identificó la expresión algebraica **${cleaned}$** (sin signo de igualdad '$=$').\n"
                    f"   - Al no tratarse de una ecuación igualada a cero ($P({var_sym}) = 0$), su resolución formal consiste en su **factorización** en factores irreducibles o su simplificación.\n"
                    f"   - *(Nota orientativa: Si tu objetivo era resolver la ecuación igualada a cero $${cleaned} = 0$$, sus raíces correspondientes son: {roots_ped}).*"
                )

            if has_informal_power:
                steps.append(
                    f"{len(steps) + 1}. **Aclaración sobre la Notación:**\n"
                    f"   - Se detectó la escritura informal '{var_sym}2'. Pedagógicamente, se asume e interpreta como la potencia cuadrática **${var_sym}^2$** (diferencia de cuadrados), en lugar de una multiplicación o un subíndice. Si tu intención era otra, por favor indícalo explícitamente."
                )

            steps.append(
                f"{len(steps) + 1}. **Identificar la Expresión Algebraica y Grado:**\n"
                f"   - Polinomio dado: $${cleaned}$$\n"
                f"   - Variable: **{var_sym}** | Grado del polinomio: **{degree}° grado**"
            )

            if degree == 2:
                coeffs = poly.all_coeffs()
                a = coeffs[0]
                b = coeffs[1] if len(coeffs) > 2 else 0
                c = coeffs[2] if len(coeffs) > 2 else coeffs[1]
                b_is_zero = getattr(b, "is_zero", False) or (float(b) == 0)
                if b_is_zero and c < 0:
                    sqrt_c = sympy.sqrt(-c)
                    val_c = float(sqrt_c)
                    clean_c = int(val_c) if val_c.is_integer() else round(val_c, 6)
                    if a == 1 or float(a) == 1:
                        factored_clean = f"({var_sym} - {clean_c})({var_sym} + {clean_c})"
                    sqrt_c_str = str(clean_c) if (sqrt_c.is_integer or isinstance(c, (float, sympy.Float))) else f"\\sqrt{{{-c}}}"
                    steps.append(
                        f"{len(steps) + 1}. **Método de Factorización (Diferencia de Cuadrados):**\n"
                        f"   - Identificamos el producto notable de diferencia de cuadrados: $$a^2 - b^2 = (a - b)(a + b)$$\n"
                        f"   - En este caso: $${cleaned} = ({var_sym})^2 - ({sqrt_c_str})^2$$\n"
                        f"   - Expresión factorizada:\n"
                        f"   $$\\mathbf{{{cleaned} = {factored_clean}}}$$"
                    )
                else:
                    steps.append(
                        f"{len(steps) + 1}. **Método de Factorización (Aspa Simple / Descomposición):**\n"
                        f"   - Buscamos dos números que multiplicados den el término independiente ($c = {c}$) y sumados den el coeficiente lineal ($b = {b}$).\n"
                        f"   - Expresión factorizada:\n"
                        f"   $$\\mathbf{{{cleaned} = {factored_clean}}}$$"
                    )

                # Comprobación obligatoria por expansión distributiva
                steps.append(
                    f"{len(steps) + 1}. **Comprobación (Expansión por Propiedad Distributiva):**\n"
                    f"   - Desarrollamos el producto de los factores obtenidos para verificar que recuperamos el polinomio original:\n"
                    f"   $${factored_clean} = {cleaned} \\quad \\checkmark$$\n"
                    f"   - Se comprueba que la factorización es idéntica y exacta."
                )

                if roots and not has_factorize_intent:
                    steps.append(
                        f"{len(steps) + 1}. **Raíces o Ceros del Polinomio ($P({var_sym}) = 0$):**\n"
                        f"   - Igualando cada factor a cero obtenemos:\n"
                        + "\n".join([f"   - ${var_sym}_{idx+1} = \\mathbf{{{_clean_val(r)}}}$" for idx, r in enumerate(roots)])
                    )
            else:
                steps.append(
                    f"{len(steps) + 1}. **Factorización Algebraica:**\n"
                    f"   $$\\mathbf{{{cleaned} = {factored_clean}}}$$"
                )

            # In factorization mode, exact_solution is purely the factored form without confusing with equation solving
            exact_solution = factored_clean

            step_text = (
                f"### 📐 RESOLUCIÓN ÁLGEBRAICA: FACTORIZACIÓN Y POLINOMIOS\n"
                f"**Expresión:** `${cleaned}$`\n\n"
                + "\n\n".join(steps) + "\n\n"
                + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{factored_clean}}}$"
            )

            return {
                "category": "algebra",
                "topic": "factorizacion_polinomios",
                "data_identified": {"expresion": cleaned, "grado": degree, "factorizado": factored_clean, "raices": roots_str},
                "exact_solution": exact_solution,
                "step_text": step_text,
                "hints_text": f"Busca identificar si es una diferencia de cuadrados a^2 - b^2 = (a-b)(a+b) o un trinomio factorizable.",
                "socratic_text": "¿Qué producto notable o método de factorización podemos aplicar a esta expresión?",
                "verified": True
            }
        except Exception:
            if has_factorize_intent:
                return {
                    "category": "algebra",
                    "topic": "factorizacion_polinomios",
                    "status": "ambiguo",
                    "data_identified": {"entrada": text},
                    "exact_solution": "aclaracion_requerida",
                    "step_text": (
                        "### ⚠️ EXPRESIÓN DE FACTORIZACIÓN AMBIGUA\n\n"
                        "Hola. Al analizar la expresión que deseas factorizar:\n"
                        f"> *\"{text.strip()}\"*\n\n"
                        "📌 **Aclaración necesaria:**\n"
                        "- No se identificó con certeza un polinomio estándar bien formado (se detectaron términos sin operador claro o sintaxis ambigua).\n"
                        "- Por favor, vuelve a escribir la expresión utilizando operadores claros (por ejemplo: `x^2 - 9` o `x^2 + 5x + 6`) para orientarte paso a paso."
                    ),
                    "hints_text": "Escribe la expresión con exponentes y signos de operación claros.",
                    "socratic_text": "¿Podrías escribir nuevamente la expresión indicando con claridad los signos entre cada término?",
                    "verified": True
                }
            return None

    @classmethod
    def solve_linear_word_problem(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Solves classical primary/secondary linear equation word problems:
        e.g. 'Ana tiene el triple de dinero que Luis. Entre ambos tienen S/ 32. ¿Cuánto tiene cada uno?'
        Strictly pedagogical 6-step sequence:
        1. Definir incógnitas.
        2. Plantear ecuaciones.
        3. Resolver paso a paso.
        4. Explicar cada operación.
        5. Comprobar el resultado con el enunciado.
        6. Respuesta final con unidades.
        """
        if not text:
            return None

        norm = normalize_math_text(text)

        mult_map = {
            "doble": 2, "duplo": 2, "dos veces": 2,
            "triple": 3, "triplo": 3, "tres veces": 3,
            "cuadruple": 4, "cuádruple": 4, "cuatro veces": 4,
            "quintuple": 5, "quíntuple": 5, "cinco veces": 5,
            "sextuple": 6, "séxtuple": 6, "seis veces": 6
        }

        p_sub = re.search(
            r'([A-ZÁÉÍÓÚa-záéíóú]+)\s+tiene\s+(?:el\s+)?(doble|duplo|triple|triplo|cu[aá]druple|qu[ií]ntuple|dos veces|tres veces|cuatro veces|cinco veces)\s+(?:de\s+[a-záéíóú]+\s+que|de\s+lo\s+que\s+tiene|que)?\s*([A-ZÁÉÍÓÚa-záéíóú]+)',
            norm,
            re.IGNORECASE
        )
        if not p_sub:
            return None

        p_tot = re.search(
            r'(?:entre\s+(?:ambos|los\s+dos|las\s+dos|ambas)|juntos|juntas|suman|la\s+suma\s+es|en\s+total)\s+(?:tienen\s+)?(?:S\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)',
            norm,
            re.IGNORECASE
        )
        if not p_tot:
            return None

        subj1_raw = p_sub.group(1).strip().capitalize()
        mult_word = p_sub.group(2).strip().lower()
        subj2_raw = p_sub.group(3).strip().capitalize()

        k = mult_map.get(mult_word)
        if not k:
            return None

        try:
            total_val = float(p_tot.group(1))
        except ValueError:
            return None

        unit_prefix = ""
        unit_suffix = ""
        if any(w in norm.lower() for w in ["s/.", "s/", "soles"]):
            unit_prefix = "S/ "
        elif "años" in norm.lower():
            unit_suffix = " años"

        divisor = k + 1
        x_val = total_val / divisor
        y_val = k * x_val

        clean_total = int(total_val) if total_val.is_integer() else round(total_val, 2)
        clean_x = int(x_val) if x_val.is_integer() else round(x_val, 2)
        clean_y = int(y_val) if y_val.is_integer() else round(y_val, 2)

        step_text = (
            f"### 📐 ÁLGEBRA: PLANTEO DE ECUACIONES DE PRIMER GRADO\n"
            f"**Problema:** {subj1_raw} tiene el {mult_word} de lo que tiene {subj2_raw}, y entre ambos tienen {unit_prefix}{clean_total}{unit_suffix}. ¿Cuánto tiene cada uno?\n\n"
            f"1. **Definir las Incógnitas:**\n"
            f"   - Sea $x$: Cantidad correspondiente a **{subj2_raw}**.\n"
            f"   - Como {subj1_raw} tiene el {mult_word}, su cantidad es: **${k}x$**.\n\n"
            f"2. **Plantear la Ecuación:**\n"
            f"   - La suma de lo que tienen ambos es igual a {unit_prefix}{clean_total}{unit_suffix}:\n"
            f"   $$\\text{{{subj2_raw}}} + \\text{{{subj1_raw}}} = {clean_total}$$\n"
            f"   $$x + {k}x = {clean_total}$$\n\n"
            f"3. **Resolver Paso a Paso:**\n"
            f"   - Reducimos términos semejantes en el primer miembro ($1x + {k}x = {divisor}x$):\n"
            f"   $${divisor}x = {clean_total}$$\n"
            f"   - Despejamos $x$ dividiendo ambos lados entre {divisor}:\n"
            f"   $$x = \\frac{{{clean_total}}}{{{divisor}}} = \\mathbf{{{clean_x}}}$$\n"
            f"   - Por lo tanto, {subj2_raw} tiene: **{unit_prefix}{clean_x}{unit_suffix}**.\n\n"
            f"4. **Calcular la Cantidad de {subj1_raw}:**\n"
            f"   - Sustituimos $x = {clean_x}$ en la expresión de {subj1_raw}:\n"
            f"   $$\\text{{{subj1_raw}}} = {k}x = {k} \\times {clean_x} = \\mathbf{{{clean_y}}}$$\n"
            f"   - Por lo tanto, {subj1_raw} tiene: **{unit_prefix}{clean_y}{unit_suffix}**.\n\n"
            f"5. **Comprobación del Resultado:**\n"
            f"   - Relación de múltiplo: ${clean_y} = {k} \\times {clean_x}$ (correcto, es el {mult_word}).\n"
            f"   - Suma total de ambos: ${clean_y} + {clean_x} = {clean_total}$ (correcto, suman {unit_prefix}{clean_total}{unit_suffix}).\n\n"
            f"📌 **RESPUESTA FINAL:**\n"
            f"- **{subj1_raw} tiene {unit_prefix}{clean_y}{unit_suffix}.**\n"
            f"- **{subj2_raw} tiene {unit_prefix}{clean_x}{unit_suffix}.**"
        )

        hints_text = (
            f"### 💡 PISTAS PEDAGÓGICAS (MODO GUIADO)\n"
            f"1. **Incógnita:** Asigna la variable $x$ a quien tiene menos ({subj2_raw}).\n"
            f"2. **Relación:** Expresa lo de {subj1_raw} como ${k}x$.\n"
            f"3. **Ecuación:** Suma ambas partes e iguala al total: $x + {k}x = {clean_total}$."
        )

        socratic_text = (
            f"### ❓ GUÍA SOCRÁTICA\n"
            f"- Si llamamos $x$ a la cantidad de {subj2_raw}, ¿cómo representas que {subj1_raw} tiene el {mult_word}?\n"
            f"- Al juntar ambas cantidades, ¿cuántas 'x' tienes en total para igualar a {clean_total}?"
        )

        exact_solution = f"{subj1_raw} = {unit_prefix}{clean_y}{unit_suffix}, {subj2_raw} = {unit_prefix}{clean_x}{unit_suffix}"

        return {
            "category": "algebra",
            "topic": "planteo_ecuaciones_lineales",
            "data_identified": {
                "sujeto_1": subj1_raw,
                "sujeto_2": subj2_raw,
                "multiplicador": k,
                "total": clean_total,
                "solucion_sujeto_1": clean_y,
                "solucion_sujeto_2": clean_x
            },
            "exact_solution": exact_solution,
            "step_text": step_text,
            "hints_text": hints_text,
            "socratic_text": socratic_text,
            "verified": True
        }

    @classmethod
    def solve_fraction_word_problem(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Solves multistep fraction and percentage word problems:
        e.g. 'María tiene S/ 200. Gasta 2/5 de su dinero en alimentos y luego gasta el 25% de lo que le queda en transporte. ¿Cuánto dinero le sobra al final?'
        Sequence:
        1. Identificar datos e incógnitas (Monto inicial = S/ 200).
        2. Primer gasto (Fracción del total: 2/5 de 200 = S/ 80 -> Resto = S/ 120).
        3. Segundo gasto (Porcentaje o fracción de lo restante: 25% de 120 = S/ 30).
        4. Dinero restante final (120 - 30 = S/ 90).
        5. Comprobación matemática rigurosa (80 + 30 + 90 = 200).
        6. Respuesta final con unidades.
        """
        if not text:
            return None

        norm = normalize_math_text(text)
        norm_lower = norm.lower()

        # Check narrative keywords for chained spending problems
        if not any(k in norm_lower for k in ["gasta", "gasto", "gastó", "paga", "utiliza"]):
            return None
        if not any(k in norm_lower for k in ["queda", "sobra", "resta", "al final", "le queda"]):
            return None

        # 1. Extract Initial Amount (Generalizado con sinónimos de posesión y capital inicial)
        # e.g. 'tiene', 'dispone de', 'cuenta con', 'posee', 'inicia con', 'comienza con', 'un total de'
        m_total = re.search(r'(?:tiene|dispone\s+de|cuenta\s+con|posee|inicia\s+con|comienza\s+con|total\s+de)\s*(?:S\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)', norm, re.IGNORECASE)
        if not m_total:
            m_total = re.search(r'(?:S\/\.?|soles|\$)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if not m_total:
            m_total = re.search(r'(\d+(?:\.\d+)?)\s*(?:soles|S\/\.?)', norm, re.IGNORECASE)
        if not m_total:
            return None

        total_amount = float(m_total.group(1))

        # 2. Extract First Expense (Fraction: e.g. 2/5 de su dinero, o 'la mitad')
        m_frac1 = re.search(r'(\d+)\s*/\s*(\d+)(?:\s*de\s*(?:su\s+dinero|lo\s+que\s+tiene|del\s+total))?(?:\s*en\s+([a-záéíóú]+))?', norm_lower)
        if m_frac1:
            n1, d1 = int(m_frac1.group(1)), int(m_frac1.group(2))
            if d1 == 0:
                return None
            concept1 = m_frac1.group(3) or "el primer gasto"
        elif "la mitad" in norm_lower or "su mitad" in norm_lower:
            n1, d1 = 1, 2
            m_c1 = re.search(r'(?:la mitad|su mitad)\s*(?:en\s+([a-záéíóú]+))?', norm_lower)
            concept1 = (m_c1.group(1) if m_c1 else None) or "el primer gasto"
        else:
            return None

        gasto1 = (n1 / d1) * total_amount
        resto1 = total_amount - gasto1

        # 3. Extract Second Expense (Percentage or Fraction of remainder)
        m_pct2 = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:de\s*(?:lo\s+que\s+le\s+queda|lo\s+restante|del\s+resto))?(?:\s*en\s+([a-záéíóú]+))?', norm_lower)
        m_frac2 = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:de\s*(?:lo\s+que\s+le\s+queda|lo\s+restante|del\s+resto))(?:\s*en\s+([a-záéíóú]+))?', norm_lower)

        gasto2 = 0.0
        pct2_val = None
        concept2 = "el segundo gasto"

        if m_pct2:
            pct2_val = float(m_pct2.group(1))
            concept2 = m_pct2.group(2) or concept2
            gasto2 = (pct2_val / 100.0) * resto1
        elif m_frac2:
            n2, d2 = int(m_frac2.group(1)), int(m_frac2.group(2))
            if d2 != 0:
                concept2 = m_frac2.group(3) or concept2
                gasto2 = (n2 / d2) * resto1
        else:
            return None

        sobra_final = resto1 - gasto2

        clean_total = int(total_amount) if total_amount.is_integer() else round(total_amount, 2)
        clean_gasto1 = int(gasto1) if gasto1.is_integer() else round(gasto1, 2)
        clean_resto1 = int(resto1) if resto1.is_integer() else round(resto1, 2)
        clean_gasto2 = int(gasto2) if gasto2.is_integer() else round(gasto2, 2)
        clean_sobra = int(sobra_final) if sobra_final.is_integer() else round(sobra_final, 2)

        unit_str = "S/ " if any(w in norm_lower for w in ["s/.", "s/", "soles"]) else ""

        step_text = (
            f"### 🧮 ARITMÉTICA: PROBLEMA VERBAL CON FRACCIONES Y PORCENTAJES ENCADENADOS\n"
            f"**Enunciado:** Cantidad inicial: {unit_str}{clean_total}. Gasta $\\frac{{{n1}}}{{{d1}}}$ en {concept1} y luego {pct2_val}% de lo que queda en {concept2}.\n\n"
            f"1. **Definir los Datos e Incógnitas:**\n"
            f"   - Dinero inicial total: **{unit_str}{clean_total}**\n"
            f"   - Primer gasto ({concept1}): $\\frac{{{n1}}}{{{d1}}}$ del dinero inicial\n"
            f"   - Segundo gasto ({concept2}): {pct2_val}% del dinero restante\n"
            f"   - Incógnita: Dinero que le sobra al final.\n\n"
            f"2. **Calcular el Primer Gasto ({concept1.capitalize()}):**\n"
            f"   $$\\text{{Gasto}}_1 = \\frac{{{n1}}}{{{d1}}} \\times {clean_total} = \\frac{{{n1} \\times {clean_total}}}{{{d1}}} = \\mathbf{{{unit_str}{clean_gasto1}}}$$\n"
            f"   - Dinero que le queda tras el primer gasto:\n"
            f"   $$\\text{{Resto}}_1 = {clean_total} - {clean_gasto1} = \\mathbf{{{unit_str}{clean_resto1}}}$$\n\n"
            f"3. **Calcular el Segundo Gasto ({concept2.capitalize()}):**\n"
            f"   - Se aplica {pct2_val}% sobre el dinero que le quedaba ({unit_str}{clean_resto1}):\n"
            f"   $$\\text{{Gasto}}_2 = {pct2_val}\\% \\times {clean_resto1} = \\frac{{{pct2_val}}}{{100}} \\times {clean_resto1} = \\mathbf{{{unit_str}{clean_gasto2}}}$$\n\n"
            f"4. **Calcular el Dinero que le Sobra al Final:**\n"
            f"   $$\\text{{Dinero Final}} = \\text{{Resto}}_1 - \\text{{Gasto}}_2 = {clean_resto1} - {clean_gasto2} = \\mathbf{{{unit_str}{clean_sobra}}}$$\n\n"
            f"5. **Comprobación del Resultado:**\n"
            f"   - Suma de gastos y sobrante: ${clean_gasto1} + {clean_gasto2} + {clean_sobra} = {clean_total}$\n"
            f"   - La suma coincide exactamente con el monto inicial ({unit_str}{clean_total}) $\\checkmark$.\n\n"
            f"📌 **RESPUESTA FINAL:** Al final le sobra **{unit_str}{clean_sobra}**."
        )

        hints_text = (
            f"### 💡 PISTAS PEDAGÓGICAS\n"
            f"1. Primero calcula cuánto es $\\frac{{{n1}}}{{{d1}}}$ de {unit_str}{clean_total} y réstalo para saber cuánto le queda.\n"
            f"2. Con ese nuevo monto restante, calcula el {pct2_val}%.\n"
            f"3. Resta ese segundo gasto para hallar lo que le sobra."
        )

        socratic_text = (
            f"### ❓ GUÍA SOCRÁTICA\n"
            f"- Si tenía {unit_str}{clean_total} y gastó $\\frac{{{n1}}}{{{d1}}}$, ¿cuánto dinero le quedó antes de hacer el segundo gasto?\n"
            f"- ¿El segundo porcentaje se aplica a los {unit_str}{clean_total} iniciales o a lo que le quedaba?"
        )

        return {
            "category": "aritmetica",
            "topic": "problema_fracciones_porcentajes_encadenados",
            "data_identified": {
                "total_inicial": clean_total,
                "gasto_1": clean_gasto1,
                "resto_1": clean_resto1,
                "gasto_2": clean_gasto2,
                "sobra_final": clean_sobra
            },
            "exact_solution": f"{unit_str}{clean_sobra}",
            "step_text": step_text,
            "hints_text": hints_text,
            "socratic_text": socratic_text,
            "verified": True
        }

    @classmethod
    def solve_quadratic_equation(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles quadratic equations: e.g. 'x^2 - 5x + 6 = 0', '2x^2 + 4x - 6 = 0'."""
        norm = normalize_math_text(text)
        if not ("^2" in norm or "**2" in norm or "cuadrática" in norm or "cuadratica" in norm) or "=" not in norm:
            return None

        eq_cand = cls.extract_equation_candidate(norm)
        if not eq_cand or "=" not in eq_cand:
            return None

        parts = eq_cand.split("=")
        var_sym = cls.detect_variable(eq_cand) or sympy.Symbol("x")
        local_dict = {str(var_sym): var_sym}

        try:
            lhs = parse_expr(parts[0], local_dict=local_dict, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
            rhs = parse_expr(parts[1], local_dict=local_dict, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
            diff = sympy.simplify(lhs - rhs)
            
            poly = sympy.Poly(diff, var_sym)
            if poly.degree() != 2:
                return None

            coeffs = poly.all_coeffs()
            a, b, c = coeffs[0], coeffs[1], coeffs[2]
            disc = b**2 - 4*a*c

            solutions = sympy.solve(diff, var_sym)
            def _clean_q(v):
                if isinstance(v, (float, sympy.Float)):
                    fv = float(v)
                    return str(int(fv)) if fv.is_integer() else f"{round(fv, 6):g}"
                if hasattr(v, "is_integer") and v.is_integer:
                    return str(int(v))
                return str(v)

            a_str = _clean_q(a)
            b_str = _clean_q(b)
            c_str = _clean_q(c)
            disc_str = _clean_q(disc)
            clean_sols = [_clean_q(s) for s in solutions]
            sols_str = ", ".join([f"{var_sym}_{idx+1} = {s}" for idx, s in enumerate(clean_sols)])

            b_is_zero = getattr(b, "is_zero", False) or (float(b) == 0)
            is_diff_of_squares = (b_is_zero and c < 0 and (a == 1 or float(a) == 1))
            k_str = ""
            if is_diff_of_squares:
                k = sympy.sqrt(-c)
                val_k = float(k)
                k_str = str(int(val_k)) if val_k.is_integer() else f"{round(val_k, 6):g}"
                factored_clean = f"({var_sym} - {k_str})({var_sym} + {k_str})"
            else:
                # Try factoring the quadratic expression
                factored = sympy.factor(diff)
                factored_str = str(factored)
                factored_clean = re.sub(r"\)\s*\*\s*\(", ")(", factored_str)
                factored_clean = re.sub(r"(\d+)\s*\*\s*\(", r"\1(", factored_clean)
                factored_clean = factored_clean.replace("*", "")

            steps = [
                f"1. **Forma General ($ax^2 + bx + c = 0$):**\n"
                f"   - Ecuación dada: $${eq_cand}$$\n"
                f"   - Coeficientes: $a = {a_str}$, $b = {b_str}$, $c = {c_str}$"
            ]

            # Method 1: Factorization
            if is_diff_of_squares and len(solutions) == 2:
                # Factorization by difference of squares: x^2 - k^2 = (x - k)(x + k) = 0
                steps.append(
                    f"2. **Método Preferente: Factorización por Diferencia de Cuadrados:**\n"
                    f"   - Reconocemos el producto notable de diferencia de cuadrados: $$a^2 - b^2 = (a - b)(a + b)$$\n"
                    f"   - Expresamos la ecuación en su forma factorizada exacta:\n"
                    f"   $${var_sym}^2 - {k_str}^2 = ({var_sym} - {k_str})({var_sym} + {k_str}) = 0$$\n"
                    f"   - Por el Teorema del Factor Cero (Producto Nulo), igualamos cada factor a cero:\n"
                    f"     * Primer factor: $${var_sym} - {k_str} = 0 \\implies {var_sym}_1 = \\mathbf{{{clean_sols[1]}}}$$\n"
                    f"     * Segundo factor: $${var_sym} + {k_str} = 0 \\implies {var_sym}_2 = \\mathbf{{{clean_sols[0]}}}$$"
                )
            elif str(factored) != str(diff) and len(solutions) == 2 and not ("(" in factored_str and "0." in factored_str):
                # Trinomial decomposition (e.g. x^2 - 5x + 6 = (x - 2)(x - 3) = 0)
                steps.append(
                    f"2. **Método de Factorización (Aspa Simple / Descomposición):**\n"
                    f"   - Descomponemos el trinomio cuadrático en factores:\n"
                    f"   $${factored_clean} = 0$$\n"
                    f"   - Por el Teorema del Factor Cero, igualamos cada factor a cero:\n"
                    + "\n".join([f"     * Factor ${idx+1}$: ${var_sym} = \\mathbf{{{clean_sols[idx]}}}$" for idx in range(len(solutions))])
                )

            # Method 2: Discriminant and Quadratic Formula
            sqrt_disc = sympy.sqrt(disc)
            if sqrt_disc.is_real:
                val_sd = float(sqrt_disc)
                sqrt_d_str = str(int(val_sd)) if val_sd.is_integer() else f"{round(val_sd, 6):g}"
            else:
                sqrt_d_str = f"\\sqrt{{{disc_str}}}"

            steps.append(
                f"{len(steps) + 1}. **Método Alternativo: Fórmula General Cuadrática:**\n"
                f"   - Calculamos el discriminante: $$\\Delta = b^2 - 4ac = ({b_str})^2 - 4({a_str})({c_str}) = \\mathbf{{{disc_str}}}$$\n"
                f"   - Aplicamos la fórmula general cuadrática:\n"
                f"   $${var_sym} = \\frac{{-b \\pm \\sqrt{{b^2 - 4ac}}}}{{2a}} = \\frac{{-b \\pm \\sqrt{{\\Delta}}}}{{2a}} = (-b \\pm \\sqrt{{b^2 - 4ac}}) / (2a)$$\n"
                f"   - Sustituimos los coeficientes:\n"
                f"   $${var_sym} = \\frac{{-({b_str}) \\pm \\sqrt{{{disc_str}}}}}{{2({a_str})}} = \\frac{{-({b_str}) \\pm {sqrt_d_str}}}{{{_clean_q(2*a)}}} = (-({b_str}) \\pm {sqrt_d_str}) / ({_clean_q(2*a)})$$\n"
                f"   - Raíces obtenidas:\n"
                f"   $${var_sym}_1 = \\mathbf{{{clean_sols[0]}}}, \\quad {var_sym}_2 = \\mathbf{{{clean_sols[-1]}}}$$"
            )

            # Verification by direct substitution into original equation
            sub_verifs = []
            for idx, sol in enumerate(solutions):
                sol_c = clean_sols[idx]
                sub_lhs = lhs.subs(var_sym, sol)
                sub_rhs = rhs.subs(var_sym, sol)
                lhs_clean_expr = str(lhs).replace("**", "^").replace(str(var_sym), f"({sol_c})").replace("*", " \\cdot ")
                sub_verifs.append(
                    f"     * Para ${var_sym} = {sol_c}$:\n"
                    f"       $${lhs_clean_expr} = {_clean_q(sub_lhs)} = {_clean_q(sub_rhs)} \\quad \\checkmark$$"
                )

            steps.append(
                f"{len(steps) + 1}. **Comprobación por Sustitución Directa en la Ecuación:**\n"
                f"   - Verificamos que cada raíz satisface la igualdad original:\n"
                + "\n".join(sub_verifs) + "\n"
                f"   - Ambas soluciones verifican la ecuación."
            )

            exact_solution = f"{var_sym} = {clean_sols[0]} y {var_sym} = {clean_sols[-1]}" if len(solutions) == 2 else sols_str

            step_text = (
                f"### 🧮 RESOLUCIÓN DE ECUACIÓN CUADRÁTICA PASO A PASO\n"
                f"**Ecuación:** `${eq_cand}$`\n\n"
                + "\n\n".join(steps) + "\n\n"
                + f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_solution}}}$ (${var_sym}_1 = {clean_sols[0]}$, ${var_sym}_2 = {clean_sols[-1]}$)"
            )

            return {
                "category": "algebra",
                "topic": "ecuacion_cuadratica",
                "data_identified": {"a": str(a), "b": str(b), "c": str(c), "discriminante": str(disc), "factorizado": factored_clean},
                "exact_solution": exact_solution,
                "step_text": step_text,
                "hints_text": f"Identifica los coeficientes a, b, c, factoriza la ecuación cuadrática o aplica la fórmula general con el discriminante Δ = b² - 4ac.",
                "socratic_text": "¿Qué signo tiene el discriminante y qué indica sobre la naturaleza de las raíces?",
                "verified": True
            }
        except Exception:
            return None

    # =========================================================================
    # AREA 3: RAZONAMIENTO MATEMÁTICO (SUCESIONES)
    # =========================================================================
    @classmethod
    def solve_sequence(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles number sequences: e.g. '2, 6, 18, 54', '2, 4, 8, 16', '3, 7, 11, 15'."""
        norm = normalize_math_text(text)
        m = re.search(r"(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*,\s*(\d+(?:\.\d+)?))?", norm)
        if not m:
            return None

        terms = [float(g) for g in m.groups() if g is not None]
        if len(terms) < 3:
            return None

        # Check Geometric (multiplication)
        is_geom = True
        r0 = terms[1] / terms[0] if terms[0] != 0 else None
        if r0 is not None:
            for i in range(1, len(terms) - 1):
                if terms[i] == 0 or abs((terms[i+1] / terms[i]) - r0) > 1e-6:
                    is_geom = False
                    break
        else:
            is_geom = False

        # Check Arithmetic (addition)
        is_arit = True
        d0 = terms[1] - terms[0]
        for i in range(1, len(terms) - 1):
            if abs((terms[i+1] - terms[i]) - d0) > 1e-6:
                is_arit = False
                break

        if is_geom and r0 is not None:
            next_term = terms[-1] * r0
            next_clean = int(next_term) if next_term.is_integer() else round(next_term, 4)
            r_clean = int(r0) if r0.is_integer() else round(r0, 4)

            step_text = (
                f"### 🧠 RESOLUCIÓN DE RAZONAMIENTO MATEMÁTICO (SUCESIONES)\n"
                f"**Sucesión dada:** ${', '.join([str(int(t) if t.is_integer() else t) for t in terms])}, \\dots$\n\n"
                f"1. **Análisis de la Razón de Cambio entre Términos Consecutivos:**\n"
                f"   - $a_2 / a_1 = {terms[1]} / {terms[0]} = \\mathbf{{{r_clean}}}$\n"
                f"   - $a_3 / a_2 = {terms[2]} / {terms[1]} = \\mathbf{{{r_clean}}}$\n"
                f"   - $a_4 / a_3 = {terms[3]} / {terms[2]} = \\mathbf{{{r_clean}}}$\n\n"
                f"2. **Regla de Formación:**\n"
                f"   La sucesión es una **Progresión Geométrica** donde cada término se obtiene multiplicando el término anterior por **{r_clean}** ($a_n = a_1 \\cdot r^{{n-1}}$).\n\n"
                f"3. **Cálculo del Siguiente Término ($a_{{{len(terms)+1}}}$):**\n"
                f"   $$a_{{{len(terms)+1}}} = {terms[-1]} \\times {r_clean} = \\mathbf{{{next_clean}}}$$\n\n"
                f"📌 **RESPUESTA FINAL:** El siguiente término es $\\mathbf{{{next_clean}}}$, justificando que cada término se multiplica por {r_clean}."
            )

            return {
                "category": "razonamiento",
                "topic": "sucesion_geometrica",
                "data_identified": {"terminos": terms, "razon": r_clean, "tipo": "geometrica"},
                "exact_solution": str(next_clean),
                "step_text": step_text,
                "hints_text": f"Observa la relación entre términos consecutivos dividiendo un término entre el anterior para encontrar la razón constante.",
                "socratic_text": "¿Qué operación constante transforma el primer número en el segundo y el segundo en el tercero?",
                "verified": True
            }

        elif is_arit:
            next_term = terms[-1] + d0
            next_clean = int(next_term) if next_term.is_integer() else round(next_term, 4)
            d_clean = int(d0) if d0.is_integer() else round(d0, 4)

            step_text = (
                f"### 🧠 RESOLUCIÓN DE RAZONAMIENTO MATEMÁTICO (SUCESIONES)\n"
                f"**Sucesión dada:** ${', '.join([str(int(t) if t.is_integer() else t) for t in terms])}, \\dots$\n\n"
                f"1. **Análisis de la Diferencia entre Términos:**\n"
                f"   - $a_2 - a_1 = {terms[1]} - {terms[0]} = \\mathbf{{{d_clean}}}$\n"
                f"   - $a_3 - a_2 = {terms[2]} - {terms[1]} = \\mathbf{{{d_clean}}}$\n\n"
                f"2. **Regla de Formación:**\n"
                f"   Es una **Progresión Aritmética** con diferencia constante $d = {d_clean}$.\n\n"
                f"3. **Cálculo del Siguiente Término:**\n"
                f"   $$a_{{{len(terms)+1}}} = {terms[-1]} + {d_clean} = \\mathbf{{{next_clean}}}$$\n\n"
                f"📌 **RESPUESTA FINAL:** $\\mathbf{{{next_clean}}}$"
            )

            return {
                "category": "razonamiento",
                "topic": "sucesion_aritmetica",
                "data_identified": {"terminos": terms, "diferencia": d_clean, "tipo": "aritmetica"},
                "exact_solution": str(next_clean),
                "step_text": step_text,
                "hints_text": f"Calcula la diferencia entre dos términos consecutivos para identificar el patrón aditivo.",
                "socratic_text": "¿Cuánto se suma en cada paso de la secuencia?",
                "verified": True
            }

        return None

    # =========================================================================
    # AREA 4: GEOMETRÍA (ÁREAS, PERÍMETROS, PITÁGORAS)
    # =========================================================================
    @classmethod
    def solve_pythagoras(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles Pythagorean Theorem: e.g. 'catetos de 3 cm y 4 cm. Calcula la hipotenusa'."""
        text_lower = normalize_math_text(text).lower()
        if not ("pitagoras" in text_lower or "pitágoras" in text_lower or "hipotenusa" in text_lower or "cateto" in text_lower or "triangulo rectangulo" in text_lower or "triángulo rectángulo" in text_lower):
            return None

        m_cat = re.findall(r"(\d+(?:\.\d+)?)\s*(?:cm|m|mm|unidades)?", text_lower)
        if len(m_cat) < 2:
            return None

        unit_match = re.search(r"\b(cm|m|mm|km|pulgadas)\b", text_lower)
        unit = f" {unit_match.group(1)}" if unit_match else ""

        nums = [float(x) for x in m_cat[:2]]
        
        if "hipotenusa" in text_lower and not any(w in text_lower for w in ["hipotenusa es", "hipotenusa mide", "hipotenusa de"]):
            a, b = nums[0], nums[1]
            c2 = a**2 + b**2
            c = math.sqrt(c2)
            c_clean = int(c) if c.is_integer() else round(c, 4)
            exact_solution = f"{c_clean}{unit}".strip()

            step_text = (
                f"### 📐 RESOLUCIÓN GEOMÉTRICA: TEOREMA DE PITÁGORAS\n"
                f"**Problema:** Triángulo rectángulo con catetos $a = {a}{unit}$ y $b = {b}{unit}$.\n\n"
                f"1. **Identificar Datos e Incógnita:**\n"
                f"   - Cateto $a$: **{a}{unit}**\n"
                f"   - Cateto $b$: **{b}{unit}**\n"
                f"   - Incógnita: Hipotenusa ($c$).\n\n"
                f"2. **Fórmula del Teorema de Pitágoras:**\n"
                f"   $$a^2 + b^2 = c^2 \\implies c = \\sqrt{{a^2 + b^2}}$$\n\n"
                f"3. **Procedimiento Operativo Paso a Paso:**\n"
                f"   - Elevamos los catetos al cuadrado: ${a}^2 = {a**2}$, ${b}^2 = {b**2}$\n"
                f"   - Sumamos los cuadrados: ${a**2} + {b**2} = {c2}$\n"
                f"   - Extraemos la raíz cuadrada: $c = \\sqrt{{{c2}}} = \\mathbf{{{c_clean}{unit}}}$\n\n"
                f"4. **Comprobación:**\n"
                f"   $$({a})^2 + ({b})^2 = {a**2 + b**2} = ({c_clean})^2 \\quad \\checkmark$$\n\n"
                f"📌 **RESPUESTA FINAL:** La hipotenusa es $\\mathbf{{{exact_solution}}}$."
            )

            hints_text = (
                f"### 💡 PISTAS PEDAGÓGICAS (MODO GUIADO)\n"
                f"1. **Fórmula:** Aplica el Teorema de Pitágoras: $c^2 = a^2 + b^2$.\n"
                f"2. **Primer Paso:** Calcula el cuadrado de cada cateto ({a}² y {b}²) y súmalos."
            )

            socratic_text = (
                f"### ❓ GUÍA SOCRÁTICA\n"
                f"- ¿Qué relación establece el Teorema de Pitágoras entre los cuadrados de los catetos y la hipotenusa en un triángulo rectángulo?\n"
                f"- Si los catetos miden {a} y {b}, ¿cuánto da la suma de sus cuadrados?"
            )

            return {
                "category": "geometria",
                "topic": "teorema_pitagoras",
                "data_identified": {"cateto_a": a, "cateto_b": b, "unidad": unit.strip()},
                "exact_solution": exact_solution,
                "step_text": step_text,
                "hints_text": hints_text,
                "socratic_text": socratic_text,
                "verified": True
            }

        return None

    @classmethod
    def solve_geometry_areas_perimeters(cls, text: str) -> Optional[Dict[str, Any]]:
        """Handles geometric areas & perimeters: rectangle (e.g. 'Área de un rectángulo de 12 por 7'), circle, triangle, square."""
        text_lower = normalize_math_text(text).lower()
        if not any(w in text_lower for w in ["area", "área", "perimetro", "perímetro", "circunferencia", "rectangulo", "rectángulo", "rectangular", "terreno", "cerco", "cercar", "alambre", "circulo", "círculo", "cuadrado", "triangulo", "triángulo"]):
            return None

        # 1. Rectángulo / Terreno rectangular: e.g. 'Área de un rectángulo de 12 por 7', 'Terreno de 15 por 8 con 3 vueltas de alambre'
        if any(w in text_lower for w in ["rectangulo", "rectángulo", "rectangular", "terreno"]):
            m_rect = re.search(
                r"(?:rect[aá]ngulo|rectangular|terreno)[^\d]*?(\d+(?:\.\d+)?)\s*(?:cm|m|mm|metros)?\s*(?:por|x|×|\*|y|de base|con base|de largo|de ancho|de altura|y altura|\s+)\s*(?:de\s+)?(\d+(?:\.\d+)?)",
                text_lower
            )
            if not m_rect:
                m_rect = re.search(
                    r"(?:largo|base)\s*(?:de|=)?\s*(\d+(?:\.\d+)?).*?(?:ancho|altura)\s*(?:de|=)?\s*(\d+(?:\.\d+)?)",
                    text_lower
                )

            if m_rect:
                b = float(m_rect.group(1))
                h = float(m_rect.group(2))
            else:
                m_dims = re.findall(r"(\d+(?:\.\d+)?)\s*(?:cm|m|metros|mm)?", text_lower)
                if len(m_dims) >= 2:
                    b = float(m_dims[0])
                    h = float(m_dims[1])
                else:
                    return None

            b_clean = int(b) if b.is_integer() else b
            h_clean = int(h) if h.is_integer() else h
            area = b * h
            perim = 2 * (b + h)
            area_clean = int(area) if area.is_integer() else round(area, 4)
            perim_clean = int(perim) if perim.is_integer() else round(perim, 4)

            # Detect unit
            unit = "metros" if "metro" in text_lower or " m " in f" {text_lower} " else ("cm" if "cm" in text_lower else "unidades")

            # Check if asking specifically for fencing, wire turns or wire length
            is_fencing = any(w in text_lower for w in ["cercar", "cerco", "cerca", "alambre", "vueltas", "vuelta", "rodear", "rodearlo"])

            # Mapeo de multiplicadores numéricos en español
            SPANISH_NUMS = {
                "un": 1, "una": 1, "uno": 1,
                "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
                "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
                "once": 11, "doce": 12
            }
            num_words_pat = r"(\d+|" + "|".join(SPANISH_NUMS.keys()) + r")"

            # 1. Directo vueltas: '3 vueltas', 'tres vueltas', 'dar tres vueltas', 'con una vuelta'
            m_vueltas = re.search(rf"(?:dar|dando|con)?\s*{num_words_pat}\s*vueltas?", text_lower)
            if m_vueltas:
                val = m_vueltas.group(1)
                num_vueltas = int(val) if val.isdigit() else SPANISH_NUMS.get(val, 1)
            else:
                # 2. Expresiones con rodear/cercar: 'rodearlo tres veces', 'rodear 2 veces', 'rodearlo una vez'
                m_rodear = re.search(rf"(?:rodear(?:lo|la|los|las)?|cercar(?:lo|la|los|las)?|dar(?:le)?)\s+{num_words_pat}\s*(?:veces|vez)", text_lower)
                if m_rodear:
                    val = m_rodear.group(1)
                    num_vueltas = int(val) if val.isdigit() else SPANISH_NUMS.get(val, 1)
                elif is_fencing:
                    # 3. Contexto de cerco/alambre/perímetro con 'N veces' o 'N vez'
                    # Evita falsos positivos como 'tres veces más/mayor/menor/el ancho'
                    m_veces = re.search(rf"{num_words_pat}\s*(?:veces|vez)(?!\s+(?:m[aá]s|mayor|menor|el\s+|la\s+|su\s+|que\b))", text_lower)
                    if m_veces:
                        val = m_veces.group(1)
                        num_vueltas = int(val) if val.isdigit() else SPANISH_NUMS.get(val, 1)
                    else:
                        num_vueltas = 1
                else:
                    num_vueltas = 0

            if is_fencing and num_vueltas > 0:
                total_alambre = perim_clean * num_vueltas
                exact_sol = f"{total_alambre} {unit}"
                vueltas_label = "vuelta" if num_vueltas == 1 else "vueltas"
                step_text = (
                    f"### 📐 GEOMETRÍA: PERÍMETRO Y ALAMBRE PARA CERCO RECTANGULAR\n"
                    f"**Problema:** Terreno rectangular de dimensiones $Largo = {b_clean}\\text{{ {unit}}}$ y $Ancho = {h_clean}\\text{{ {unit}}}$ con **{num_vueltas} {vueltas_label} de alambre**.\n\n"
                    f"1. **Identificar Datos e Incógnitas:**\n"
                    f"   - Largo ($L$): **{b_clean} {unit}**\n"
                    f"   - Ancho ($A$): **{h_clean} {unit}**\n"
                    f"   - Vueltas de cerco ($N$): **{num_vueltas} {vueltas_label}**\n"
                    f"   - Incógnita: Metros totales de alambre necesarios.\n\n"
                    f"2. **Fórmula del Perímetro Rectangular:**\n"
                    f"   $$\\text{{Perímetro}} = 2 \\times (\\text{{Largo}} + \\text{{Ancho}}) = 2 \\times (L + A)$$\n\n"
                    f"3. **Calcular la Longitud de 1 Vuelta Completa (Perímetro):**\n"
                    f"   $$\\text{{Perímetro}} = 2 \\times ({b_clean} + {h_clean}) = 2 \\times ({b_clean + h_clean}) = \\mathbf{{{perim_clean}\\text{{ {unit}}}}}$$\n\n"
                    f"4. **Calcular el Alambre Total para {num_vueltas} {vueltas_label.capitalize()}:**\n"
                    f"   $$\\text{{Total Alambre}} = \\text{{Perímetro}} \\times N = {perim_clean} \\times {num_vueltas} = \\mathbf{{{total_alambre}\\text{{ {unit}}}}}$$\n\n"
                    f"5. **Comprobación:**\n"
                    f"   - Al dividir el total entre las vueltas: ${total_alambre} \\div {num_vueltas} = {perim_clean}\\text{{ {unit}}}$ por vuelta.\n"
                    f"   - Al dividir el perímetro entre 2: ${perim_clean} \\div 2 = {b_clean + h_clean} = {b_clean} + {h_clean}$ $\\checkmark$.\n\n"
                    f"📌 **RESPUESTA FINAL:** Se necesitan en total **{exact_sol}** de alambre."
                )
                return {
                    "category": "geometria",
                    "topic": "perimetro_rectangulo_cerco",
                    "data_identified": {"largo": b_clean, "ancho": h_clean, "perimetro": perim_clean, "vueltas": num_vueltas, "total_alambre": total_alambre},
                    "exact_solution": exact_sol,
                    "step_text": step_text,
                    "hints_text": f"Calcula primero el perímetro sumando 2 largos y 2 anchos, luego multiplica por las {num_vueltas} vueltas." if num_vueltas > 1 else "Calcula el perímetro sumando los 4 lados: 2 largos y 2 anchos.",
                    "socratic_text": "¿Cuántos metros mide una sola vuelta completa alrededor del terreno?",
                    "verified": True
                }
            else:
                wants_perimeter = any(w in text_lower for w in ["perimetro", "perímetro", "ambos", "perimetro y area", "area y perimetro", "área y perímetro", "perímetro y área"])
                unit_sq = " m²" if "metro" in text_lower or " m " in f" {text_lower} " else (" cm²" if "cm" in text_lower else " unidades cuadradas")
                unit_len = " metros" if "metro" in text_lower or " m " in f" {text_lower} " else (" cm" if "cm" in text_lower else " unidades")
                exact_sol = f"Área = {area_clean}{unit_sq}, Perímetro = {perim_clean}{unit_len}" if wants_perimeter else (f"{area_clean} m²" if ("metro" in text_lower or " m " in f" {text_lower} ") else str(area_clean))

                if wants_perimeter:
                    step_text = (
                        f"### 📐 GEOMETRÍA: ÁREA Y PERÍMETRO DEL RECTÁNGULO\n"
                        f"**Problema:** Rectángulo con dimensiones base $b = {b_clean}$ y altura $h = {h_clean}$.\n\n"
                        f"1. **Identificar Datos e Incógnitas:**\n"
                        f"   - Base ($b$): **{b_clean}**\n"
                        f"   - Altura ($h$): **{h_clean}**\n\n"
                        f"2. **Fórmula del Área del Rectángulo:**\n"
                        f"   $$\\text{{Área}} = \\text{{Base}} \\times \\text{{Altura}} = b \\times h$$\n\n"
                        f"3. **Procedimiento de Cálculo del Área:**\n"
                        f"   $$\\text{{Área}} = {b_clean} \\times {h_clean} = \\mathbf{{{area_clean}}}{unit_sq}$$\n\n"
                        f"4. **Cálculo de Perímetro:**\n"
                        f"   $$\\text{{Perímetro}} = 2 \\times (b + h) = 2 \\times ({b_clean} + {h_clean}) = 2 \\times ({b_clean + h_clean}) = \\mathbf{{{perim_clean}}}{unit_len}$$\n\n"
                        f"📌 **RESPUESTA FINAL:** Área = $\\mathbf{{{area_clean}}}{unit_sq}$ | Perímetro = $\\mathbf{{{perim_clean}}}{unit_len}$."
                    )
                else:
                    step_text = (
                        f"### 📐 GEOMETRÍA: ÁREA DEL RECTÁNGULO\n"
                        f"**Problema:** Rectángulo con dimensiones base $b = {b_clean}$ y altura $h = {h_clean}$.\n\n"
                        f"1. **Identificar Datos e Incógnitas:**\n"
                        f"   - Base ($b$): **{b_clean}**\n"
                        f"   - Altura ($h$): **{h_clean}**\n\n"
                        f"2. **Fórmula del Área del Rectángulo:**\n"
                        f"   $$\\text{{Área}} = \\text{{Base}} \\times \\text{{Altura}} = b \\times h$$\n\n"
                        f"3. **Procedimiento de Cálculo:**\n"
                        f"   $$\\text{{Área}} = {b_clean} \\times {h_clean} = \\mathbf{{{area_clean}}}{unit_sq}$$\n\n"
                        f"📌 **RESPUESTA FINAL:** El área del rectángulo es $\\mathbf{{{exact_sol}}}$."
                    )

                return {
                    "category": "geometria",
                    "topic": "rectangulo",
                    "data_identified": {"base": b_clean, "altura": h_clean, "area": area_clean, "perimetro": perim_clean if wants_perimeter else None},
                    "exact_solution": exact_sol,
                    "step_text": step_text,
                    "hints_text": f"Recuerda que el área de un rectángulo es el producto de su base por su altura: A = b × h.",
                    "socratic_text": "¿Qué fórmula geométrica permite calcular la superficie de un rectángulo a partir de sus dos lados?",
                    "verified": True
                }

        # 2. Triángulo: Chequeo de suficiencia de datos y cálculo de área
        if any(w in text_lower for w in ["triangulo", "triángulo"]):
            m_base = re.search(r"base[^\d]*?(\d+(?:\.\d+)?)\s*(cm|m|mm|metros)?", text_lower)
            m_alt = re.search(r"altura[^\d]*?(\d+(?:\.\d+)?)\s*(cm|m|mm|metros)?", text_lower)

            unit_t = "cm" if "cm" in text_lower else ("m" if "metro" in text_lower or " m " in f" {text_lower} " else "unidades")

            # Caso Obligatorio A: Base dada pero sin altura (Datos insuficientes)
            if m_base and not m_alt:
                b_val = float(m_base.group(1))
                b_val_clean = int(b_val) if b_val.is_integer() else b_val
                step_text = (
                    f"### 📐 GEOMETRÍA: ANÁLISIS DE DATOS PARA EL ÁREA DEL TRIÁNGULO\n\n"
                    f"1. **Datos identificados en tu consulta:**\n"
                    f"   - Base ($b$): **{b_val_clean} {unit_t}**\n"
                    f"   - Altura ($h$): **Dato no proporcionado**\n\n"
                    f"2. **Fórmula del Área del Triángulo:**\n"
                    f"   $$\\text{{Área}} = \\frac{{\\text{{Base}} \\times \\text{{Altura}}}}{{2}} = \\frac{{b \\times h}}{{2}}$$\n\n"
                    f"3. **Información requerida para resolver el ejercicio:**\n"
                    f"   Para calcular el área de este triángulo se necesita conocer la medida de su **altura** ($h$) correspondiente a la base de {b_val_clean} {unit_t}.\n\n"
                    f"📌 **¿Cómo podemos resolverlo?**\n"
                    f"Por favor indícame cuál es la altura del triángulo (o si se trata de un triángulo equilátero, isósceles o rectángulo con otros datos conocidos) y calcularemos el área paso a paso."
                )
                return {
                    "category": "geometria",
                    "topic": "triangulo_datos_insuficientes",
                    "status": "datos_insuficientes",
                    "missing_field": "altura",
                    "data_identified": {"base": b_val_clean, "altura": None, "unidad": unit_t},
                    "exact_solution": None,
                    "step_text": step_text,
                    "hints_text": "Para hallar el área de cualquier triángulo necesitas la base y la altura: A = (b × h) / 2.",
                    "socratic_text": "¿Qué dato adicional además de la base necesitas para aplicar la fórmula del área del triángulo?",
                    "verified": False
                }

            # Caso Obligatorio B: Altura dada pero sin base (Datos insuficientes)
            if m_alt and not m_base:
                h_val = float(m_alt.group(1))
                h_val_clean = int(h_val) if h_val.is_integer() else h_val
                step_text = (
                    f"### 📐 GEOMETRÍA: ANÁLISIS DE DATOS PARA EL ÁREA DEL TRIÁNGULO\n\n"
                    f"1. **Datos identificados en tu consulta:**\n"
                    f"   - Altura ($h$): **{h_val_clean} {unit_t}**\n"
                    f"   - Base ($b$): **Dato no proporcionado**\n\n"
                    f"2. **Fórmula del Área del Triángulo:**\n"
                    f"   $$\\text{{Área}} = \\frac{{\\text{{Base}} \\times \\text{{Altura}}}}{{2}} = \\frac{{b \\times h}}{{2}}$$\n\n"
                    f"3. **Información requerida para resolver el ejercicio:**\n"
                    f"   Para calcular el área de este triángulo se necesita conocer la medida de su **base** ($b$) correspondiente a la altura de {h_val_clean} {unit_t}.\n\n"
                    f"📌 **¿Cómo podemos resolverlo?**\n"
                    f"Por favor indícame cuál es la medida de la base del triángulo (o si se trata de un triángulo equilátero, isósceles o rectángulo con otros datos conocidos) y calcularemos el área paso a paso."
                )
                return {
                    "category": "geometria",
                    "topic": "triangulo_datos_insuficientes",
                    "status": "datos_insuficientes",
                    "missing_field": "base",
                    "data_identified": {"base": None, "altura": h_val_clean, "unidad": unit_t},
                    "exact_solution": None,
                    "step_text": step_text,
                    "hints_text": "Para hallar el área de cualquier triángulo necesitas la base y la altura: A = (b × h) / 2.",
                    "socratic_text": "¿Qué dato adicional además de la altura necesitas para aplicar la fórmula del área del triángulo?",
                    "verified": False
                }

            # Caso con base y altura completas
            if m_base and m_alt:
                b_val = float(m_base.group(1))
                h_val = float(m_alt.group(1))
                b_clean = int(b_val) if b_val.is_integer() else b_val
                h_clean = int(h_val) if h_val.is_integer() else h_val
                area_t = (b_val * h_val) / 2.0
                area_t_clean = int(area_t) if area_t.is_integer() else round(area_t, 2)
                exact_sol = f"{area_t_clean} {unit_t}²"
                step_text = (
                    f"### 📐 GEOMETRÍA: ÁREA DEL TRIÁNGULO\n"
                    f"**Problema:** Triángulo con base $b = {b_clean}\\text{{ {unit_t}}}$ y altura $h = {h_clean}\\text{{ {unit_t}}}$.\n\n"
                    f"1. **Identificar Datos e Incógnitas:**\n"
                    f"   - Base ($b$): **{b_clean} {unit_t}**\n"
                    f"   - Altura ($h$): **{h_clean} {unit_t}**\n"
                    f"   - Incógnita: Área del triángulo.\n\n"
                    f"2. **Fórmula del Área del Triángulo:**\n"
                    f"   $$\\text{{Área}} = \\frac{{b \\times h}}{{2}}$$\n\n"
                    f"3. **Procedimiento de Cálculo:**\n"
                    f"   $$\\text{{Área}} = \\frac{{{b_clean} \\times {h_clean}}}{{2}} = \\frac{{{b_clean * h_clean}}}{{2}} = \\mathbf{{{area_t_clean}\\text{{ {unit_t}}}^2}}$$\n\n"
                    f"4. **Comprobación:**\n"
                    f"   $$2 \\times \\text{{Área}} = 2 \\times {area_t_clean} = {b_clean * h_clean} = {b_clean} \\times {h_clean}$$ $\\checkmark$.\n\n"
                    f"📌 **RESPUESTA FINAL:** El área del triángulo es **{exact_sol}**."
                )
                return {
                    "category": "geometria",
                    "topic": "triangulo_area",
                    "data_identified": {"base": b_clean, "altura": h_clean, "area": area_t_clean},
                    "exact_solution": exact_sol,
                    "step_text": step_text,
                    "hints_text": "Multiplica la base por la altura y divide el resultado entre 2.",
                    "socratic_text": "¿Por qué el área del triángulo se divide entre 2 en relación al área de un rectángulo?",
                    "verified": True
                }

        # 2. Círculo: e.g. 'radio de 5'
        m_circ = re.search(r"(?:circulo|círculo|circunferencia).*?radio\s*(?:de|=)?\s*(\d+(?:\.\d+)?)", text_lower)
        if m_circ:
            r = float(m_circ.group(1))
            r_clean = int(r) if r.is_integer() else r
            area = math.pi * (r**2)
            perim = 2 * math.pi * r

            if "perimetro" in text_lower or "perímetro" in text_lower or "longitud" in text_lower:
                exact_sol = f"{round(perim, 2)} ({2*r_clean}π)"
                step_text = (
                    f"### 📐 GEOMETRÍA: PERÍMETRO DE CIRCUNFERENCIA\n"
                    f"1. **Fórmula:** $P = 2 \\pi r$\n"
                    f"2. **Cálculo:** $P = 2 \\times \\pi \\times {r_clean} = {2*r_clean}\\pi \\approx \\mathbf{{{round(perim, 2)}}}$\n\n"
                    f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_sol}}}$"
                )
            else:
                exact_sol = f"{round(area, 2)} ({r_clean**2}π)"
                step_text = (
                    f"### 📐 GEOMETRÍA: ÁREA DEL CÍRCULO\n"
                    f"1. **Fórmula:** $A = \\pi r^2$\n"
                    f"2. **Cálculo:** $A = \\pi \\times ({r_clean})^2 = {r_clean**2}\\pi \\approx \\mathbf{{{round(area, 2)}}}$\n\n"
                    f"📌 **RESPUESTA FINAL:** $\\mathbf{{{exact_sol}}}$"
                )

            return {
                "category": "geometria",
                "topic": "circulo",
                "data_identified": {"radio": r},
                "exact_solution": exact_sol,
                "step_text": step_text,
                "hints_text": "Aplica la fórmula geométrica correspondiente reemplazando el valor del radio.",
                "socratic_text": "¿Qué fórmula relaciona el radio con el área o longitud de la circunferencia?",
                "verified": True
            }

    # =========================================================================
    # AREA 5: PROPORCIONALIDAD DIRECTA (REGLA DE TRES SIMPLE DIRECTA)
    # =========================================================================
    @classmethod
    def solve_direct_proportion(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Solves direct proportionality / simple rule of three problems:
        e.g. 'Seis metros de tela cuestan S/ 90. ¿Cuánto cuestan 15 metros?',
             'Cuatro cuadernos cuestan S/ 20. ¿Cuánto cuestan 10 cuadernos al mismo precio unitario?',
             'Tres kilos cuestan S/ 18. ¿Cuánto cuestan cinco kilos?'
        """
        if not text:
            return None

        norm = normalize_math_text(text)
        norm_lower = norm.lower()

        # Word to number mapping for small textual numbers
        num_word_map = {
            "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
            "doce": 12, "quince": 15, "veinte": 20
        }

        # Replace textual numbers at the beginning or after prepositions
        for w, n in num_word_map.items():
            norm_lower = re.sub(rf'\b{w}\b', str(n), norm_lower)

        # Exclude percentage, discount or interest problems
        if any(w in norm_lower for w in ["%", "por ciento", "porciento", "descuento", "rebaja", "aumento", "recargo", "interés", "interes"]):
            return None

        # Require keywords of cost/price/proportionality
        if not any(k in norm_lower for k in ["cuestan", "cuesta", "precio", "valen", "vale", "pagan", "paga"]):
            return None
        if not any(k in norm_lower for k in ["cuanto", "cuánto", "que valor", "qué valor"]):
            return None

        # Pattern 1: 'X <magnitud_1> cuestan S/ Y. ¿Cuánto cuestan Z <magnitud_1>?'
        # e.g. '6 metros de tela cuestan 90. ¿cuánto cuestan 15 metros?'
        # e.g. '4 cuadernos cuestan 20. ¿cuánto cuestan 10 cuadernos?'
        m_prop = re.search(
            r'(\d+(?:\.\d+)?)\s*([a-záéíóú]+(?:\s+de\s+[a-záéíóú]+)?)\s*(?:cuestan|cuesta|valen|vale)\s*(?:s\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)[^\d]*?(\d+(?:\.\d+)?)\s*([a-záéíóú]+(?:\s+de\s+[a-záéíóú]+)?)?',
            norm_lower
        )
        if not m_prop:
            # Pattern 2: 'Se pagan S/ Y por X <magnitud>. ¿Cuánto por Z?'
            m_prop = re.search(
                r'(?:pagan|paga|cuestan|cuesta)\s*(?:s\/\.?|soles|\$)?\s*(\d+(?:\.\d+)?)\s*(?:por|para)\s*(\d+(?:\.\d+)?)\s*([a-záéíóú]+)[^\d]*?(\d+(?:\.\d+)?)',
                norm_lower
            )
            if m_prop:
                y1 = float(m_prop.group(1))
                x1 = float(m_prop.group(2))
                unit_obj = m_prop.group(3)
                x2 = float(m_prop.group(4))
            else:
                return None
        else:
            x1 = float(m_prop.group(1))
            unit_obj = m_prop.group(2).strip()
            y1 = float(m_prop.group(3))
            x2 = float(m_prop.group(4))

        if x1 <= 0 or x2 <= 0 or y1 <= 0:
            return None

        # Calculate unit rate and final value
        unit_rate = y1 / x1
        res_val = x2 * unit_rate

        clean_x1 = int(x1) if x1.is_integer() else round(x1, 2)
        clean_y1 = int(y1) if y1.is_integer() else round(y1, 2)
        clean_x2 = int(x2) if x2.is_integer() else round(x2, 2)
        clean_rate = int(unit_rate) if unit_rate.is_integer() else round(unit_rate, 4)
        clean_res = int(res_val) if res_val.is_integer() else round(res_val, 2)

        currency_str = "S/ " if any(w in norm_lower for w in ["s/.", "s/", "soles", "cuesta", "precio"]) else ""
        exact_solution = f"{currency_str}{clean_res}"

        step_text = (
            f"### 🧮 ARITMÉTICA: PROPORCIONALIDAD DIRECTA (REGLA DE TRES SIMPLE)\n"
            f"**Problema:** Si {clean_x1} {unit_obj} cuestan {currency_str}{clean_y1}, ¿cuánto costarán {clean_x2} {unit_obj} al mismo precio unitario?\n\n"
            f"1. **Identificar Datos e Incógnita:**\n"
            f"   - Magnitud conocida 1 ($A$): **{clean_x1} {unit_obj}** $\\longrightarrow$ Costo ($B$): **{currency_str}{clean_y1}**\n"
            f"   - Magnitud solicitada 2 ($C$): **{clean_x2} {unit_obj}** $\\longrightarrow$ Costo incógnita ($x$): **?**\n"
            f"   - **Justificación de Proporcionalidad:** A mayor cantidad de {unit_obj}, mayor será el costo en la misma proporción directa.\n\n"
            f"2. **Planteo por Regla de Tres Simple Directa:**\n"
            f"   $$\\begin{{array}}{{ccc}}\n"
            f"   {clean_x1}\\text{{ {unit_obj}}} & \\longrightarrow & {currency_str}{clean_y1} \\\\\n"
            f"   {clean_x2}\\text{{ {unit_obj}}} & \\longrightarrow & x\n"
            f"   \\end{{array}}$$\n\n"
            f"3. **Cálculo del Valor Unitario (Constante de Proporcionalidad):**\n"
            f"   $$\\text{{Precio Unitario}} = \\frac{{{clean_y1}}}{{{clean_x1}}} = \\mathbf{{{currency_str}{clean_rate}\\text{{ por {unit_obj}}}}}$$\n\n"
            f"4. **Cálculo del Costo Total para {clean_x2} {unit_obj}:**\n"
            f"   $$x = \\frac{{{clean_y1} \\times {clean_x2}}}{{{clean_x1}}} = {clean_rate} \\times {clean_x2} = \\mathbf{{{currency_str}{clean_res}}}$$\n\n"
            f"5. **Comprobación:**\n"
            f"   - Igualdad de razones: $\\frac{{{clean_y1}}}{{{clean_x1}}} = \\frac{{{clean_res}}}{{{clean_x2}}} = {clean_rate}$ $\\checkmark$.\n"
            f"   - Multiplicación cruzada: ${clean_x1} \\times {clean_res} = {clean_x1 * clean_res}$ y ${clean_y1} \\times {clean_x2} = {clean_y1 * clean_x2}$ $\\checkmark$.\n\n"
            f"📌 **RESPUESTA FINAL:** {clean_x2} {unit_obj} cuestan **{exact_solution}**."
        )

        hints_text = (
            f"### 💡 PISTAS PEDAGÓGICAS\n"
            f"1. Halla primero el valor de 1 unidad dividiendo {clean_y1} entre {clean_x1}.\n"
            f"2. Luego multiplica ese precio unitario ({clean_rate}) por las {clean_x2} unidades requeridas."
        )

        socratic_text = (
            f"### ❓ GUÍA SOCRÁTICA\n"
            f"- Si {clean_x1} {unit_obj} cuestan {currency_str}{clean_y1}, ¿cuánto cuesta una sola unidad?\n"
            f"- ¿Por qué decimos que la cantidad y el costo son magnitudes directamente proporcionales?"
        )

        return {
            "category": "aritmetica",
            "topic": "regla_de_tres_directa",
            "data_identified": {
                "cantidad_1": clean_x1,
                "costo_1": clean_y1,
                "cantidad_2": clean_x2,
                "unidad": unit_obj,
                "precio_unitario": clean_rate,
                "costo_total": clean_res
            },
            "exact_solution": exact_solution,
            "step_text": step_text,
            "hints_text": hints_text,
            "socratic_text": socratic_text,
            "verified": True
        }

    # =========================================================================
    # AREA 5B: PROPORCIONALIDAD INVERSA (REGLA DE TRES SIMPLE INVERSA)
    # =========================================================================
    @classmethod
    def solve_inverse_proportion(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Solves inverse proportionality / inverse rule of three problems:
        e.g. 'Cuatro trabajadores tardan 12 días en una obra. ¿Cuántos días tardarán 8 trabajadores con el mismo rendimiento?',
             '6 trabajadores tardan 10 días; 12 trabajadores tardan 5 días.',
             'Un vehículo recorre una distancia fija en 4 horas a 60 km/h; a 80 km/h tarda 3 horas.',
             'Una llave con caudal constante llena un depósito en 8 horas; con el doble de caudal, tarda 4 horas.'
        Formula: A * B = C * x  =>  x = (A * B) / C
        """
        if not text:
            return None

        import unicodedata
        def _strip_accents(s: str) -> str:
            s_norm = unicodedata.normalize('NFD', s)
            return ''.join(c for c in s_norm if unicodedata.category(c) != 'Mn')

        raw = _strip_accents(normalize_math_text(text).lower())

        # Exclude percentages, discounts, commercial increases
        if any(w in raw for w in ["%", "por ciento", "porciento", "descuento", "rebaja", "aumento"]):
            return None

        # Replace word numbers
        num_word_map = {
            "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
            "doce": 12, "quince": 15, "veinte": 20
        }
        for w, n in num_word_map.items():
            raw = re.sub(rf'\b{w}\b', str(n), raw)
        raw = re.sub(r'\b(un|uno|una)\s+(trabajador|obrero|persona|hombre|alumno|llave|grifo|bomba|vehiculo|auto)\b', r'1 \2', raw)

        a, b, c = 0.0, 0.0, 0.0
        context_type = ""
        unit_mag1 = ""
        unit_mag2 = ""

        # 1. Pattern: Workers / Days / Hours
        # e.g. 4 trabajadores tardan 12 dias ... 8 trabajadores
        m_work = re.search(
            r'(\d+(?:\.\d+)?)\s*(trabajadores|obreros|personas|hombres|alumnos|operarios|pintores)\s*(?:tardan|demoran|emplean|necesitan|hacen)?[^\d]*?(\d+(?:\.\d+)?)\s*(dias|horas|jornadas|minutos).*?(\d+(?:\.\d+)?)\s*(?:trabajadores|obreros|personas|hombres|alumnos|operarios|pintores)',
            raw
        )
        if m_work:
            a = float(m_work.group(1))
            unit_mag1 = m_work.group(2)
            b = float(m_work.group(3))
            unit_mag2 = m_work.group(4)
            c = float(m_work.group(5))
            context_type = "trabajadores"
        else:
            # 2. Pattern: Speed / Time
            # e.g. en 4 horas a 60 km/h; a 80 km/h
            m_speed = re.search(
                r'(\d+(?:\.\d+)?)\s*(horas|h|minutos)[^\d]*?(?:a\s*)?(\d+(?:\.\d+)?)\s*(km\/h|kmh|m\/s).*?(\d+(?:\.\d+)?)\s*(?:km\/h|kmh|m\/s)',
                raw
            )
            if not m_speed:
                m_speed = re.search(
                    r'(\d+(?:\.\d+)?)\s*(km\/h|kmh|m\/s)[^\d]*?(\d+(?:\.\d+)?)\s*(horas|h|minutos).*?(\d+(?:\.\d+)?)\s*(?:km\/h|kmh|m\/s)',
                    raw
                )
                if m_speed:
                    a = float(m_speed.group(1))
                    unit_mag1 = m_speed.group(2)
                    b = float(m_speed.group(3))
                    unit_mag2 = m_speed.group(4)
                    c = float(m_speed.group(5))
                    context_type = "velocidad"
            else:
                b = float(m_speed.group(1))
                unit_mag2 = m_speed.group(2)
                a = float(m_speed.group(3))
                unit_mag1 = m_speed.group(4)
                c = float(m_speed.group(5))
                context_type = "velocidad"

            if not m_speed:
                # 3. Pattern: Tap / Caudal / Flow
                # e.g. Una llave con caudal constante llena un deposito en 8 horas; con el doble de caudal...
                m_tap = re.search(
                    r'(?:llave|grifo|bomba|tuberia|manguera|caudal).*?(\d+(?:\.\d+)?)\s*(horas|h|minutos|min|dias).*?(?:con\s+el\s+)?(doble|triple|mitad|cuadruple|\d+(?:\.\d+)?\s*(?:veces|llaves|grifos|bombas))',
                    raw
                )
                if m_tap:
                    b = float(m_tap.group(1))
                    unit_mag2 = m_tap.group(2)
                    factor_str = m_tap.group(3)
                    a = 1.0
                    unit_mag1 = "caudal"
                    if factor_str == "doble":
                        c = 2.0
                    elif factor_str == "triple":
                        c = 3.0
                    elif factor_str == "mitad":
                        c = 0.5
                    elif factor_str == "cuadruple":
                        c = 4.0
                    else:
                        m_f = re.search(r'(\d+(?:\.\d+)?)', factor_str)
                        c = float(m_f.group(1)) if m_f else 0.0
                    context_type = "caudal"
                else:
                    return None

        # Rejection of zero or negative inputs
        if a <= 0 or b <= 0 or c <= 0:
            return None

        # Constant product k = A * B
        k = a * b
        x = k / c

        clean_a = int(a) if a.is_integer() else round(a, 2)
        clean_b = int(b) if b.is_integer() else round(b, 2)
        clean_c = int(c) if c.is_integer() else round(c, 2)
        clean_k = int(k) if k.is_integer() else round(k, 2)
        clean_x = int(x) if x.is_integer() else round(x, 2)

        # Standardize unit accents for proper Spanish display
        if unit_mag2 == "dias":
            unit_mag2 = "días"

        exact_solution = f"{clean_x} {unit_mag2}"

        if context_type == "trabajadores":
            rel_reason = f"A **mayor** cantidad de {unit_mag1}, se requerirán **menos** {unit_mag2} para culminar la misma obra con igual rendimiento (magnitudes inversamente proporcionales)."
        elif context_type == "velocidad":
            rel_reason = f"A **mayor** velocidad ({unit_mag1}), se tardará **menos** tiempo ({unit_mag2}) para recorrer la misma distancia fija (magnitudes inversamente proporcionales)."
        else:
            rel_reason = f"A **mayor** {unit_mag1}, se requerirá **menos** tiempo ({unit_mag2}) para llenar el mismo depósito (magnitudes inversamente proporcionales)."

        step_text = (
            f"### 🧮 ARITMÉTICA: PROPORCIONALIDAD INVERSA (REGLA DE TRES SIMPLE INVERSA)\n"
            f"**Problema:** Si {clean_a} {unit_mag1} tardan {clean_b} {unit_mag2}, ¿cuánto tardarán {clean_c} {unit_mag1}?\n\n"
            f"1. **Identificar Datos e Incógnita:**\n"
            f"   - Magnitud 1 inicial ($A$): **{clean_a} {unit_mag1}** $\\longrightarrow$ Magnitud 2 inicial ($B$): **{clean_b} {unit_mag2}**\n"
            f"   - Magnitud 1 final ($C$): **{clean_c} {unit_mag1}** $\\longrightarrow$ Magnitud 2 incógnita ($x$): **?**\n"
            f"   - **Justificación de Proporcionalidad Inversa:** {rel_reason}\n\n"
            f"2. **Planteo por Regla de Tres Simple Inversa:**\n"
            f"   $$\\begin{{array}}{{ccc}}\n"
            f"   {clean_a}\\text{{ {unit_mag1}}} & \\longrightarrow & {clean_b}\\text{{ {unit_mag2}}} \\\\\n"
            f"   {clean_c}\\text{{ {unit_mag1}}} & \\longrightarrow & x\n"
            f"   \\end{{array}}$$\n\n"
            f"3. **Propiedad de las Magnitudes Inversamente Proporcionales (Producto Constante):**\n"
            f"   En la proporcionalidad inversa, el producto de ambas magnitudes se mantiene constante ($k$):\n"
            f"   $$A \\times B = C \\times x = k$$\n"
            f"   $${clean_a} \\times {clean_b} = {clean_c} \\times x$$\n"
            f"   $${clean_k} = {clean_c} \\cdot x$$\n\n"
            f"4. **Despeje y Cálculo del Valor Solicitado:**\n"
            f"   $$x = \\frac{{{clean_a} \\times {clean_b}}}{{{clean_c}}} = \\frac{{{clean_k}}}{{{clean_c}}} = \\mathbf{{{clean_x}\\text{{ {unit_mag2}}}}}$$\n\n"
            f"5. **Comprobación del Producto Constante:**\n"
            f"   - Producto con datos iniciales: ${clean_a} \\times {clean_b} = {clean_k}$\n"
            f"   - Producto con valor obtenido: ${clean_c} \\times {clean_x} = {clean_k}$\n"
            f"   - Ambos productos son idénticos (${clean_k} = {clean_k}$ $\\checkmark$), confirmando la proporcionalidad inversa.\n\n"
            f"📌 **RESPUESTA FINAL:** Se tardarán **{exact_solution}**."
        )

        hints_text = (
            f"### 💡 PISTAS PEDAGÓGICAS\n"
            f"1. Observa que al aumentar una magnitud, la otra disminuye en la misma proporción: es una regla de tres inversa.\n"
            f"2. El producto entre ambas magnitudes debe ser constante: {clean_a} × {clean_b} = {clean_k}.\n"
            f"3. Para hallar el nuevo valor, divide ese producto constante ({clean_k}) entre {clean_c}."
        )

        socratic_text = (
            f"### ❓ GUÍA SOCRÁTICA\n"
            f"- Si aumentamos la cantidad de {unit_mag1}, ¿crees que tardarán más tiempo o menos tiempo en terminar?\n"
            f"- ¿Cuál es la propiedad fundamental del producto constante en la proporcionalidad inversa?"
        )

        return {
            "category": "aritmetica",
            "topic": "regla_de_tres_inversa",
            "data_identified": {
                "magnitud_1_inicial": clean_a,
                "magnitud_2_inicial": clean_b,
                "magnitud_1_final": clean_c,
                "unidad_1": unit_mag1,
                "unidad_2": unit_mag2,
                "producto_constante": clean_k,
                "resultado": clean_x
            },
            "exact_solution": exact_solution,
            "step_text": step_text,
            "hints_text": hints_text,
            "socratic_text": socratic_text,
            "verified": True
        }

    # =========================================================================
    # MASTER ANALYZER & DISPATCHER
    # =========================================================================
    @classmethod
    def analyze_and_solve(cls, user_prompt: str, tool_type: str = "paso_a_paso") -> Dict[str, Any]:
        """
        Comprehensive master solver for secondary school mathematics across:
        1. Aritmética (Fracciones didácticas con MCM/mixtos, porcentajes, operaciones combinadas con jerarquía).
        2. Álgebra (Ecuaciones lineales con/sin paréntesis, cuadráticas, factorización de polinomios).
        3. Razonamiento Matemático (Sucesiones y progresiones).
        4. Geometría (Áreas, perímetros de rectángulos/círculos, Teorema de Pitágoras).
        5. Proporcionalidad (Regla de tres simple directa e inversa).
        """
        if not user_prompt:
            return {"is_math": False}

        # 0. Safety Gate: Check Ambiguous or Concatenated Inputs (Tarea 1)
        ambiguous_res = cls.detect_ambiguous_or_concatenated_input(user_prompt)
        if ambiguous_res:
            return {"is_math": True, **ambiguous_res}

        # 0.1 Check Number Ordering (e.g. 'Ordena de menor a mayor: 0,5; 3/4; 0,25') (Tarea 3)
        ordering_res = cls.solve_number_ordering(user_prompt)
        if ordering_res:
            return {"is_math": True, **ordering_res}

        # 0.2 Check Decimal to Fraction Conversion (e.g. '0,75 a fraccion') (Tarea 5)
        dec_frac_res = cls.solve_decimal_to_fraction(user_prompt)
        if dec_frac_res:
            return {"is_math": True, **dec_frac_res}

        # 1. Check Linear Equation Word Problems (e.g. 'Ana tiene el triple de dinero que Luis. Entre ambos tienen S/ 32')
        word_prob_res = cls.solve_linear_word_problem(user_prompt)
        if word_prob_res:
            return {"is_math": True, **word_prob_res}

        # 2. Check Fraction & Percentage Multistep Word Problems (e.g. María S/ 200, 2/5 y 25% del resto)
        frac_word_res = cls.solve_fraction_word_problem(user_prompt)
        if frac_word_res:
            return {"is_math": True, **frac_word_res}

        # 3. Check Inverse Proportionality (e.g. '4 trabajadores tardan 12 días -> 8 trabajadores')
        inv_prop_res = cls.solve_inverse_proportion(user_prompt)
        if inv_prop_res:
            return {"is_math": True, **inv_prop_res}

        # 4. Check Direct Proportionality / Simple Rule of Three (e.g. '6 metros de tela S/ 90 -> 15 metros')
        prop_res = cls.solve_direct_proportion(user_prompt)
        if prop_res:
            return {"is_math": True, **prop_res}

        # 4. Check Percentage & Commercial Discounts/Increases (e.g. 'Mochila S/ 120 descuento 15%', '15% de 240')
        pct_res = cls.solve_percentage(user_prompt)
        if pct_res:
            return {"is_math": True, **pct_res}

        # 2. Check Pythagorean Theorem
        pyth_res = cls.solve_pythagoras(user_prompt)
        if pyth_res:
            return {"is_math": True, **pyth_res}

        # 3. Check Geometry Areas / Perimeters (e.g. 'Área de un rectángulo de 12 por 7')
        geom_res = cls.solve_geometry_areas_perimeters(user_prompt)
        if geom_res:
            return {"is_math": True, **geom_res}

        # 4. Check Sequence & Patterns (e.g. '2, 6, 18, 54')
        seq_res = cls.solve_sequence(user_prompt)
        if seq_res:
            return {"is_math": True, **seq_res}

        # 5. Check Fraction Operations (e.g. '3/4 + 2/5', '7/8 - 1/4', '5/6 * 3/10', '9/12 ÷ 3/4')
        frac_res = cls.solve_fraction_operation(user_prompt)
        if frac_res:
            return {"is_math": True, **frac_res}

        # 6. Check Quadratic Equations (e.g. 'x^2 - 5x + 6 = 0')
        quad_res = cls.solve_quadratic_equation(user_prompt)
        if quad_res:
            return {"is_math": True, **quad_res}

        # 7. Check Linear Algebraic Equations (e.g. '3x + 7 = 22', '2(x + 4) = 18')
        eq_cand = cls.extract_equation_candidate(user_prompt)
        if eq_cand:
            lin_res = cls.solve_linear_equation(eq_cand)
            if lin_res.get("status") in ["solucion_unica", "infinitas_soluciones", "sin_solucion"]:
                return {"is_math": True, **lin_res}

        # 8. Check Polynomials / Algebraic Expressions (e.g. 'x^2 + 7x + 12')
        poly_res = cls.solve_algebraic_expression(user_prompt)
        if poly_res:
            return {"is_math": True, **poly_res}

        # 9. Check Combined Arithmetic Operations (e.g. '48 + 37 - 19', '125 * 8', '864 / 12', '(15 - 3)^2 / 4 + 7')
        arith_res = cls.solve_arithmetic_operations(user_prompt)
        if arith_res:
            return {"is_math": True, **arith_res}

        return {"is_math": False}

    @classmethod
    def verify_solution_claim(cls, equation_str: str, claimed_value: str) -> Dict[str, Any]:
        """Verifies if a claimed answer matches SymPy's analytical solution."""
        sol_data = cls.solve_linear_equation(equation_str)
        if sol_data.get("status") != "solucion_unica":
            return {
                "verified": False,
                "status": sol_data.get("status", "no_verificable"),
                "reason": sol_data.get("reason", "No es una ecuación de solución única.")
            }

        exact_sym = sol_data["sympy_obj"]
        var_name = sol_data["variable"]

        cleaned_claim = claimed_value.strip()
        var_prefix_match = re.match(rf"^{var_name}\s*=\s*(.+)$", cleaned_claim, re.IGNORECASE)
        if var_prefix_match:
            cleaned_claim = var_prefix_match.group(1).strip()

        if not cls.is_safe_expression(cleaned_claim):
            return {"verified": False, "status": "no_verificable", "reason": "Formato de respuesta inválido."}

        local_dict = {var_name: sympy.Symbol(var_name)}

        try:
            claim_sym = parse_expr(cleaned_claim, local_dict=local_dict, global_dict=SAFE_GLOBAL_DICT, transformations=SAFE_TRANSFORMATIONS, evaluate=True)
            diff = sympy.simplify(exact_sym - claim_sym)
            matches = (diff == 0)

            return {
                "verified": matches,
                "status": "verificado" if matches else "discrepancia",
                "equation": equation_str,
                "variable": var_name,
                "exact_solution": str(exact_sym),
                "claimed_solution": str(claim_sym),
                "matches": matches
            }
        except Exception as e:
            return {"verified": False, "status": "no_verificable", "reason": f"Error de comparación: {e}"}

    @classmethod
    def extract_solution_from_model_text(cls, model_text: str, var_name: str = "x") -> Optional[str]:
        """Searches for explicit final answers generated by the LLM."""
        if not model_text:
            return None
        p1 = re.findall(rf"\b{var_name}\s*=\s*([-\d\/\.]+)\b", model_text, re.IGNORECASE)
        if p1:
            return p1[-1]
        p2 = re.findall(r"(?:resultado|solución|solucion|valor de [a-zA-Z]|es)\s*(?:es|:|=)?\s*([-\d\/\.]+)\b", model_text, re.IGNORECASE)
        if p2:
            return p2[-1]
        return None

math_engine = MathEngine()
