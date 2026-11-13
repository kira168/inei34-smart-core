"""
INEI SMART-CORE - Independent Mathematical & Pedagogical Verifier
Institución: I.E. Emblemática INEI N.º 34 de Chancay, Perú.

Separates responsibilities into 5 distinct pedagogical pillars:
1. Interpretation of the problem (incógnitas, datos, restricciones, unidades).
2. Deterministic Mathematical Resolution (SymPy / Exact Arithmetic).
3. Independent Verification (Sustitución en ecuaciones originales, residuo < 1e-9, positividad física, coherencia de dominio).
4. Pedagogical Quality Audit (Secuencia obligatoria de 6 pasos, ausencia de corrupción, coherencia entre pasos y resultado, español puro).
5. Safe Failure Handling (Fallback responsable ante contradicciones o ambigüedades sin inventar datos).
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

logger = logging.getLogger("inei_smart_core.math_verifier")

SAFE_TRANSFORMATIONS = (
    standard_transformations +
    (implicit_multiplication_application, convert_xor)
)

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


class MathVerifier:
    """Independent Mathematical and Pedagogical Verifier for SmartTutor AI."""

    @classmethod
    def sanitize_math_text(cls, text: str) -> str:
        """Cleans and standardizes mathematical text for verification."""
        if not text:
            return ""
        t = text.replace("−", "-").replace("–", "-").replace("—", "-")
        t = t.replace("×", "*").replace("·", "*").replace("÷", "/")
        t = t.replace("S/.", " ").replace("S/", " ").replace("soles", " ").replace("Soles", " ")
        t = t.replace("√", "sqrt").replace("²", "^2").replace("³", "^3")
        return t

    @classmethod
    def parse_safely(cls, expr_str: str, local_dict: Optional[Dict[str, Any]] = None) -> Optional[sympy.Expr]:
        """Safely parses mathematical expression using AST transformations without arbitrary code execution."""
        clean = cls.sanitize_math_text(expr_str).strip()
        if not clean or len(clean) > 250:
            return None
        # Disallow dangerous patterns
        for bad in ["__", "import", "eval", "exec", "open", "os", "sys", "subprocess", "lambda", "class", "def"]:
            if bad in clean.lower():
                return None
        try:
            return parse_expr(
                clean,
                local_dict=local_dict or {},
                global_dict=SAFE_GLOBAL_DICT,
                transformations=SAFE_TRANSFORMATIONS,
                evaluate=True
            )
        except Exception:
            return None

    @classmethod
    def verify_by_substitution(
        cls,
        equation_lhs: str,
        equation_rhs: str,
        variable_values: Dict[str, Union[float, int, str]],
        tolerance: float = 1e-9
    ) -> Dict[str, Any]:
        """
        Substitutes candidate values into the LHS and RHS of an equation
        and verifies if |LHS - RHS| < tolerance or simplify(LHS - RHS) == 0.
        """
        try:
            var_symbols = {k: sympy.Symbol(k) for k in variable_values.keys()}
            lhs_expr = cls.parse_safely(equation_lhs, local_dict=var_symbols)
            rhs_expr = cls.parse_safely(equation_rhs, local_dict=var_symbols)

            if lhs_expr is None or rhs_expr is None:
                return {
                    "verified": False,
                    "reason": "No se pudieron analizar sintácticamente los miembros de la ecuación.",
                    "status": "error_sintaxis"
                }

            # Substitute each variable
            subs_dict = {}
            for k, v in variable_values.items():
                if isinstance(v, (int, float)):
                    subs_dict[sympy.Symbol(k)] = sympy.Rational(str(v)) if isinstance(v, float) else sympy.Integer(v)
                else:
                    v_parsed = cls.parse_safely(str(v))
                    subs_dict[sympy.Symbol(k)] = v_parsed if v_parsed is not None else sympy.Rational(str(v))

            lhs_eval = lhs_expr.subs(subs_dict)
            rhs_eval = rhs_expr.subs(subs_dict)

            diff = sympy.simplify(lhs_eval - rhs_eval)
            try:
                numeric_diff = float(diff.evalf())
                is_exact = abs(numeric_diff) <= tolerance
            except Exception:
                is_exact = (diff == 0)

            return {
                "verified": is_exact,
                "status": "verificado_exacto" if is_exact else "discrepancia_detectada",
                "lhs_eval": str(lhs_eval),
                "rhs_eval": str(rhs_eval),
                "diff": str(diff),
                "reason": "La igualdad se cumple exactamente por sustitución." if is_exact else f"Sustitución fallida: LHS = {lhs_eval} ≠ RHS = {rhs_eval}."
            }
        except Exception as e:
            return {
                "verified": False,
                "status": "error_sustitucion",
                "reason": f"Fallo al evaluar sustitución: {e}"
            }

    @classmethod
    def audit_pedagogical_structure(cls, explanation_text: str, problem_type: str = "algebra") -> Dict[str, Any]:
        """
        Audits pedagogical sequence and formats in an explanation:
        1. Incógnitas / Datos definidos.
        2. Ecuación / Planteamiento explícito.
        3. Desarrollo paso a paso.
        4. Explicación de operaciones.
        5. Comprobación final.
        6. Ausencia de lenguaje corrupto (mezclas de inglés, fórmulas pegadas).
        """
        if not explanation_text:
            return {
                "is_pedagogically_valid": False,
                "score": 0.0,
                "issues": ["Explicación vacía o ausente."]
            }

        issues = []
        checks = {
            "has_variables_defined": False,
            "has_equation_stated": False,
            "has_step_by_step": False,
            "has_operations_explained": False,
            "has_verification": False,
            "has_final_answer": False,
            "is_spanish_only": True,
            "has_no_corrupt_formulas": True
        }

        text_lower = explanation_text.lower()

        # 1. Variables defined
        if any(k in text_lower for k in ["incógnita", "incognita", "sea x", "sea $x$", "datos:", "identificar", "llamamos"]):
            checks["has_variables_defined"] = True
        else:
            issues.append("No define claramente las incógnitas o variables.")

        # 2. Equation stated
        if any(k in text_lower for k in ["plantear", "ecuación", "ecuacion", "planteamiento", "="]):
            checks["has_equation_stated"] = True
        else:
            issues.append("No plantea la ecuación de partida formalmente.")

        # 3. Step by step development
        if any(k in text_lower for k in ["paso 1", "paso 2", "1.", "2.", "despej", "reduc", "primer miembro", "segundo miembro"]):
            checks["has_step_by_step"] = True
        else:
            issues.append("Falta desglose paso a paso de la resolución.")

        # 4. Operations explained
        if any(k in text_lower for k in ["divid", "multiplic", "sum", "rest", "propiedad", "operaci"]):
            checks["has_operations_explained"] = True
        else:
            issues.append("No justifica las operaciones intermedias realizadas.")

        # 5. Verification step
        if any(k in text_lower for k in ["comprobaci", "verificaci", "sustituy", "comprobar"]):
            checks["has_verification"] = True
        else:
            issues.append("Omite el paso de comprobación de la respuesta obtenida.")

        # 6. Final answer with units
        if any(k in text_lower for k in ["respuesta final", "por lo tanto", "en conclusión", "resultado:", "📌"]):
            checks["has_final_answer"] = True
        else:
            issues.append("No resalta una respuesta final concluyente.")

        # 7. Language check: detect unwanted English preambles or explanations
        english_artifacts = [
            "here is the", "let's solve", "step-by-step solution", "therefore we have",
            "first, we define", "substituting we get", "let x be", "where x represents"
        ]
        if any(ea in text_lower for ea in english_artifacts):
            checks["is_spanish_only"] = False
            issues.append("Se detectaron frases o preámbulos en inglés en una respuesta en español.")

        # 8. Corrupt formula artifacts (like 'A = 3(324)', '5. 5. Respuesta', unescaped tags)
        corrupt_patterns = [
            r'[A-Za-z]\s*=\s*\d+\(\d{3,}\)',  # e.g. A = 3(324)
            r'(?:^|\n)\s*(\d+)\.\s+\1\.\s+',   # e.g. 5. 5.
            r'\\\(.*?$',                       # unclosed LaTeX inline
            r'\\\[.*?$'                        # unclosed LaTeX display
        ]
        for cp in corrupt_patterns:
            if re.search(cp, explanation_text):
                checks["has_no_corrupt_formulas"] = False
                issues.append(f"Se detectó una fórmula o numeración corrupta coincidente con el patrón: {cp}")
                break

        passed_count = sum(1 for v in checks.values() if v)
        total_checks = len(checks)
        score = round((passed_count / total_checks) * 100, 1)

        return {
            "is_pedagogically_valid": (len(issues) == 0),
            "score": score,
            "checks": checks,
            "issues": issues
        }

    @classmethod
    def clean_and_repair_response(cls, raw_text: str) -> str:
        """
        Repairs common LaTeX rendering defects, duplicated list markers,
        and English preambles from model text.
        """
        if not raw_text:
            return ""

        text = raw_text

        # 1. Scrub leaked internal instruction headers and prompt directives
        leak_pattern = r'\n*\s*(?:(?:\*\*|\#\#)?\s*(?:RIGOR,\s*TRATO\s*Y\s*CERO\s*ALUCINACI[OÓ]N|DIRECTIVAS\s*PEDAG[OÓ]GICAS|ESTRUCTURA\s*DID[AÁ]CTICA\s*DE\s*RESPUESTAS|DATOS\s*DE\s*CONTEXTO\s*DEL\s*ESTUDIANTE|INSTRUCCIONES\s*DEL\s*SISTEMA|DIRECTIVA\s*DE\s*SEGURIDAD\s*PARA\s*SMARTTUTOR|CONFIDENCIALIDAD,\s*PROTECCI[OÓ]N\s*DE\s*DIRECTIVAS|--- INICIO DE DOCUMENTO ADJUNTO NO CONFIABLE|--- FIN DE DOCUMENTO ADJUNTO)[\s\S]*$)'
        text = re.sub(leak_pattern, '', text, flags=re.IGNORECASE).strip()
        # Clean any trailing connective fragments left immediately before the scrubbed header
        text = re.sub(r'[\s,\-;:]+(?:En su lugar|Por ejemplo|Asimismo|Es decir|En cambio|Sin embargo)\s*$', '', text, flags=re.IGNORECASE).strip()
        if text and not text.endswith(('.', '!', '?', '”', '"', ')', '`', '$', '*', ':', ']')):
            text += '.'

        # 2. Remove English preambles if present
        text = re.sub(
            r'^(?:Here is the step-by-step solution:?|Sure! Here is the solution:?|Let\'s solve this problem step by step:?)\s*',
            '',
            text,
            flags=re.IGNORECASE
        )

        # 3. Fix duplicated list numbering: '5. 5. ' -> '5. '
        text = re.sub(r'(^|\n)\s*(\d+)\.\s+\2\.\s+', r'\1\2. ', text)

        # 4. Fix corrupted formula joins like 'A = 3(324)' if originated from broken stitch
        # If pattern A = k(kx_val) occurs, fix to A = k * x_val = ...
        corrupt_match = re.search(r'([A-Za-z]+)\s*=\s*(\d+)\((\d{3,})\)', text)
        if corrupt_match:
            var_name = corrupt_match.group(1)
            k_val = corrupt_match.group(2)
            num_str = corrupt_match.group(3)
            # usually num_str is joined, e.g. '324' was 32 and 24, or 3 * 8 = 24
            # We standardize presentation
            text = text.replace(corrupt_match.group(0), f"{var_name} = {k_val} \\times x")

        # 5. Normalize single brackets LaTeX to standard markdown delimiters for webview
        # \[ ... \] -> $$ ... $$
        text = re.sub(r'\\\[\s*([\s\S]*?)\s*\\\]', r'$$\1$$', text)
        # \( ... \) -> $ ... $
        text = re.sub(r'\\\(\s*([\s\S]*?)\s*\\\)', r'$\1$', text)

        return text.strip()

    @classmethod
    def build_safe_uncertainty_response(
        cls,
        user_prompt: str,
        reason: str,
        identified_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates a transparent, pedagogically supportive response when
        data is contradictory, impossible, or cannot be verified with certainty.
        Adheres to Rule: Do NOT guess or hallucinate solutions.
        """
        data_text = ""
        if identified_data:
            items = [f"- **{k}:** {v}" for k, v in identified_data.items()]
            data_text = f"\n\n**Datos identificados en tu consulta:**\n" + "\n".join(items)

        return (
            f"### ⚠️ ORIENTACIÓN PEDAGÓGICA Y ANÁLISIS DEL PROBLEMA\n\n"
            f"Hola. Al analizar detalladamente el problema planteado:\n"
            f"> *\"{user_prompt.strip()}\"*\n\n"
            f"Se ha detectado una limitación matemática o inconsistencia en los datos:\n"
            f"**Motivo:** {reason}{data_text}\n\n"
            f"📌 **¿Cómo podemos resolverlo juntos?**\n"
            f"1. **Verifica los datos:** Revisa si los números, signos o las cantidades del enunciado coinciden exactamente con tu libro o ficha de trabajo.\n"
            f"2. **Plantea tu avance:** Escribe qué incógnitas identificaste o cómo comenzaste a resolverlo para orientarte paso a paso.\n"
            f"3. **Formula de nuevo la pregunta:** Si deseas, reformula el ejercicio indicando claramente qué datos te dan y qué incógnita te piden hallar."
        )


math_verifier = MathVerifier()
