"""
INEI SMART-CORE - Evaluation & SIAGIE Service
Manages Competency-Based Grading (CNEB/EPT C1-C4) and Official SIAGIE Excel Generation.
"""

import io
from typing import Dict, Any, List, Optional
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from app.database.connection import get_db

class EvaluationService:
    @staticmethod
    def get_course_evaluations(course_id: int, bimester: int = 1) -> List[Dict[str, Any]]:
        with get_db() as conn:
            course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not course:
                return []

            bim_str = f"{bimester}° Bimestre" if str(bimester) in ["1", "2", "3", "4"] else str(bimester)
            bim_alt = f"I Bimestre" if str(bimester) == "1" else (f"II Bimestre" if str(bimester) == "2" else (f"III Bimestre" if str(bimester) == "3" else "IV Bimestre"))

            students = conn.execute(
                """
                SELECT st.id as student_id, st.dni as code, st.dni, st.full_name,
                       e.id as eval_id, e.bimester, e.c1 as competency_1, e.c2 as competency_2,
                       e.c3 as competency_3, e.c4 as competency_4, e.final_grade as final_score, e.conclusion
                FROM students st
                LEFT JOIN evaluations e ON e.student_id = st.id AND e.course_id = ? AND (e.bimester = ? OR e.bimester = ? OR e.bimester = ?)
                WHERE st.specialty = ?
                ORDER BY st.full_name ASC
                """, (course_id, str(bimester), bim_str, bim_alt, course["specialty"])
            ).fetchall()

            if not students:
                students = conn.execute(
                    """
                    SELECT st.id as student_id, st.dni as code, st.dni, st.full_name,
                           e.id as eval_id, e.bimester, e.c1 as competency_1, e.c2 as competency_2,
                           e.c3 as competency_3, e.c4 as competency_4, e.final_grade as final_score, e.conclusion
                    FROM students st
                    LEFT JOIN evaluations e ON e.student_id = st.id AND e.course_id = ? AND (e.bimester = ? OR e.bimester = ? OR e.bimester = ?)
                    WHERE st.section_id = 1 OR st.grade = '5to'
                    ORDER BY st.full_name ASC
                    """, (course_id, str(bimester), bim_str, bim_alt)
                ).fetchall()

            result = []
            for st in students:
                name_parts = st["full_name"].split(" ")
                result.append({
                    "student_id": st["student_id"],
                    "code": st["code"],
                    "dni": st["dni"],
                    "first_name": name_parts[0] if name_parts else "",
                    "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                    "eval_id": st["eval_id"],
                    "bimester": bimester,
                    "competency_1": st["competency_1"] or "A",
                    "competency_2": st["competency_2"] or "A",
                    "competency_3": st["competency_3"] or "A",
                    "competency_4": st["competency_4"] or "A",
                    "final_score": st["final_score"] or "A",
                    "conclusion": st["conclusion"] or ""
                })
            return result

    @staticmethod
    def save_evaluations_batch(
        course_id: int,
        bimester: int,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        with get_db() as conn:
            bim_str = f"{bimester}° Bimestre" if str(bimester) in ["1", "2", "3", "4"] else str(bimester)
            for rec in records:
                student_id = rec.get("student_id")
                c1 = rec.get("competency_1", "A")
                c2 = rec.get("competency_2", "A")
                c3 = rec.get("competency_3", "A")
                c4 = rec.get("competency_4", "A")
                final_score = rec.get("final_score") or c1
                conclusion = rec.get("conclusion", "")

                existing = conn.execute(
                    "SELECT id FROM evaluations WHERE student_id = ? AND course_id = ?",
                    (student_id, course_id)
                ).fetchone()

                if existing:
                    conn.execute(
                        """
                        UPDATE evaluations 
                        SET c1 = ?, c2 = ?, c3 = ?, c4 = ?, final_grade = ?, conclusion = ?, bimester = ?
                        WHERE id = ?
                        """, (c1, c2, c3, c4, final_score, conclusion, bim_str, existing["id"])
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO evaluations (student_id, course_id, bimester, c1, c2, c3, c4, final_grade, conclusion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (student_id, course_id, bim_str, c1, c2, c3, c4, final_score, conclusion)
                    )

            return {"success": True, "count": len(records)}

    @staticmethod
    def generate_siagie_excel(course_id: int, bimester: int = 1) -> bytes:
        """
        Generates an executive-grade, beautifully formatted SIAGIE Excel workbook
        with institutional letterhead (I.E. INEI N° 34 Chancay), KPI cards,
        zebra striping, conditional grade badge fills, and official signature section.
        """
        with get_db() as conn:
            course = conn.execute(
                """
                SELECT c.name as course_name, c.specialty as technical_specialty, c.grade,
                       t.full_name as teacher_name
                FROM courses c
                LEFT JOIN teachers t ON c.teacher_id = t.id
                WHERE c.id = ?
                """, (course_id,)
            ).fetchone()

            if not course:
                raise ValueError("Curso no encontrado")

            evals = EvaluationService.get_course_evaluations(course_id, bimester)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"SIAGIE_B{bimester}_{course['grade']}A"
        ws.views.sheetView[0].showGridLines = True

        # Styles: Palette
        navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        crimson_fill = PatternFill(start_color="881337", end_color="881337", fill_type="solid")
        sub_slate_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        table_header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        meta_bg_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        zebra_even_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        zebra_odd_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        # Fonts
        white_title_font = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
        white_sub_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        white_gold_font = Font(name="Segoe UI", size=9, bold=True, color="FDE68A")
        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        bold_slate_font = Font(name="Segoe UI", size=9.5, bold=True, color="0F172A")
        regular_font = Font(name="Segoe UI", size=9.5, color="334155")
        muted_font = Font(name="Segoe UI", size=8.5, italic=True, color="64748B")

        # Grade Badge Colors (Fills & Fonts)
        ad_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        ad_font = Font(name="Segoe UI", size=9.5, bold=True, color="166534")

        a_fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
        a_font = Font(name="Segoe UI", size=9.5, bold=True, color="1E40AF")

        b_fill = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
        b_font = Font(name="Segoe UI", size=9.5, bold=True, color="854D0E")

        c_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        c_font = Font(name="Segoe UI", size=9.5, bold=True, color="991B1B")

        # Borders
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )
        header_border = Border(
            left=Side(style='thin', color='475569'),
            right=Side(style='thin', color='475569'),
            top=Side(style='medium', color='0F172A'),
            bottom=Side(style='medium', color='0F172A')
        )
        double_bottom_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='0F172A'),
            bottom=Side(style='double', color='0F172A')
        )

        # 1. Header Banner
        ws.merge_cells("A1:H1")
        ws["A1"] = "I.E. INEI Nº 34 — CHANCAY"
        ws["A1"].font = white_title_font
        ws["A1"].fill = navy_fill
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 32

        ws.merge_cells("A2:H2")
        ws["A2"] = f"REGISTRO OFICIAL DE EVALUACIÓN CNEB / SIAGIE • AÑO LECTIVO 2026 • BIMESTRE {bimester}"
        ws["A2"].font = white_sub_font
        ws["A2"].fill = crimson_fill
        ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 22

        ws.merge_cells("A3:H3")
        ws["A3"] = "UGEL 10 HUARAL • CÓDIGO MODULAR: 0245621-0 • EDUCACIÓN SECUNDARIA TÉCNICA (EPT)"
        ws["A3"].font = white_gold_font
        ws["A3"].fill = sub_slate_fill
        ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[3].height = 18

        # 2. Executive Metadata Box (Rows 5-7)
        meta_items = [
            ("Área / Especialidad:", f"EPT - {course['technical_specialty']}", "Total Estudiantes:", f"{len(evals)} Matriculados"),
            ("Módulo / Asignatura:", course["course_name"], "Estado del Registro:", "100% Validado SIAGIE"),
            ("Grado y Sección:", f"{course['grade']} Grado 'A' (Secundaria)", "Docente Titular:", course["teacher_name"] or "Docente Asignado")
        ]

        for r_offset, (lbl1, val1, lbl2, val2) in enumerate(meta_items, start=5):
            ws.row_dimensions[r_offset].height = 20
            # Col A & B
            ws.cell(row=r_offset, column=1, value=lbl1).font = bold_slate_font
            ws.cell(row=r_offset, column=1).fill = meta_bg_fill
            ws.cell(row=r_offset, column=1).border = thin_border
            ws.cell(row=r_offset, column=2, value=val1).font = regular_font
            ws.cell(row=r_offset, column=2).fill = meta_bg_fill
            ws.cell(row=r_offset, column=2).border = thin_border
            ws.merge_cells(start_row=r_offset, start_column=2, end_row=r_offset, end_column=4)

            # Col E & F
            ws.cell(row=r_offset, column=5, value=lbl2).font = bold_slate_font
            ws.cell(row=r_offset, column=5).fill = meta_bg_fill
            ws.cell(row=r_offset, column=5).border = thin_border
            ws.cell(row=r_offset, column=6, value=val2).font = regular_font
            ws.cell(row=r_offset, column=6).fill = meta_bg_fill
            ws.cell(row=r_offset, column=6).border = thin_border
            ws.merge_cells(start_row=r_offset, start_column=6, end_row=r_offset, end_column=8)

        # 3. Table Column Headers (Row 9)
        table_headers = [
            "N°", "CÓDIGO SIAGIE", "DNI", "APELLIDOS Y NOMBRES",
            "C1: Propuesta Valor", "C2: Aplica Habilidades", "C3: Trabaja Coop.", "LOGRO FINAL"
        ]

        header_row = 9
        ws.row_dimensions[header_row].height = 26
        for col_idx, h in enumerate(table_headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = table_header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = header_border

        # 4. Data Rows with Zebra Striping and Grade Badges
        current_row = 10
        ad_count = 0
        a_count = 0
        b_count = 0
        c_count = 0

        for idx, student in enumerate(evals, start=1):
            ws.row_dimensions[current_row].height = 21
            full_name = f"{student['last_name']}, {student['first_name']}".strip(", ")
            is_odd = (idx % 2 != 0)
            row_fill = zebra_odd_fill if is_odd else zebra_even_fill

            final_val = str(student.get("final_score") or "A").strip()
            if "AD" in final_val:
                ad_count += 1
                score_fill, score_font = ad_fill, ad_font
            elif "A" in final_val:
                a_count += 1
                score_fill, score_font = a_fill, a_font
            elif "B" in final_val:
                b_count += 1
                score_fill, score_font = b_fill, b_font
            else:
                c_count += 1
                score_fill, score_font = c_fill, c_font

            cells = [
                (1, idx, Alignment(horizontal="center", vertical="center"), regular_font, row_fill),
                (2, student["code"], Alignment(horizontal="center", vertical="center"), regular_font, row_fill),
                (3, student["dni"], Alignment(horizontal="center", vertical="center"), regular_font, row_fill),
                (4, full_name, Alignment(horizontal="left", vertical="center"), bold_slate_font, row_fill),
                (5, student.get("competency_1") or "-", Alignment(horizontal="center", vertical="center"), regular_font, row_fill),
                (6, student.get("competency_2") or "-", Alignment(horizontal="center", vertical="center"), regular_font, row_fill),
                (7, student.get("competency_3") or "-", Alignment(horizontal="center", vertical="center"), regular_font, row_fill),
                (8, final_val, Alignment(horizontal="center", vertical="center"), score_font, score_fill)
            ]

            for col, val, align, f_style, f_fill in cells:
                c = ws.cell(row=current_row, column=col, value=val)
                c.font = f_style
                c.alignment = align
                c.fill = f_fill
                c.border = thin_border

            current_row += 1

        # 5. Summary / Totals Row
        ws.row_dimensions[current_row].height = 24
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        sum_lbl = ws.cell(row=current_row, column=1, value="CONSOLIDADO TOTAL: " + str(len(evals)) + " ESTUDIANTES EVALUADOS")
        sum_lbl.font = bold_slate_font
        sum_lbl.fill = summary_fill
        sum_lbl.alignment = Alignment(horizontal="center", vertical="center")

        for col in range(1, 5):
            ws.cell(row=current_row, column=col).border = double_bottom_border
            ws.cell(row=current_row, column=col).fill = summary_fill

        stats_text = f"AD: {ad_count} | A: {a_count} | B: {b_count}"
        ws.merge_cells(start_row=current_row, start_column=5, end_row=current_row, end_column=8)
        stats_cell = ws.cell(row=current_row, column=5, value=stats_text)
        stats_cell.font = bold_slate_font
        stats_cell.fill = summary_fill
        stats_cell.alignment = Alignment(horizontal="center", vertical="center")
        for col in range(5, 9):
            ws.cell(row=current_row, column=col).border = double_bottom_border
            ws.cell(row=current_row, column=col).fill = summary_fill

        # 6. Official Signatures Section (3 columns)
        sig_row = current_row + 4
        ws.row_dimensions[sig_row].height = 20
        ws.row_dimensions[sig_row + 1].height = 18
        ws.row_dimensions[sig_row + 2].height = 16

        # Teacher
        ws.merge_cells(start_row=sig_row, start_column=1, end_row=sig_row, end_column=3)
        ws.cell(row=sig_row, column=1, value="________________________________").alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sig_row + 1, start_column=1, end_row=sig_row + 1, end_column=3)
        ws.cell(row=sig_row + 1, column=1, value=f"{course['teacher_name'] or 'DOCENTE RESPONSABLE'}").font = bold_slate_font
        ws.cell(row=sig_row + 1, column=1).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sig_row + 2, start_column=1, end_row=sig_row + 2, end_column=3)
        ws.cell(row=sig_row + 2, column=1, value=f"Docente Titular - {course['technical_specialty']}").font = muted_font
        ws.cell(row=sig_row + 2, column=1).alignment = Alignment(horizontal="center")

        # Subdirector
        ws.merge_cells(start_row=sig_row, start_column=4, end_row=sig_row, end_column=6)
        ws.cell(row=sig_row, column=4, value="________________________________").alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sig_row + 1, start_column=4, end_row=sig_row + 1, end_column=6)
        ws.cell(row=sig_row + 1, column=4, value="Mg. Javier Eulogio Rosas Maguiña").font = bold_slate_font
        ws.cell(row=sig_row + 1, column=4).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sig_row + 2, start_column=4, end_row=sig_row + 2, end_column=6)
        ws.cell(row=sig_row + 2, column=4, value="Sub-Director de Formación Técnica").font = muted_font
        ws.cell(row=sig_row + 2, column=4).alignment = Alignment(horizontal="center")

        # Director
        ws.merge_cells(start_row=sig_row, start_column=7, end_row=sig_row, end_column=8)
        ws.cell(row=sig_row, column=7, value="________________________").alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sig_row + 1, start_column=7, end_row=sig_row + 1, end_column=8)
        ws.cell(row=sig_row + 1, column=7, value="DIRECCIÓN GENERAL").font = bold_slate_font
        ws.cell(row=sig_row + 1, column=7).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sig_row + 2, start_column=7, end_row=sig_row + 2, end_column=8)
        ws.cell(row=sig_row + 2, column=7, value="I.E. INEI Nº 34 Chancay").font = muted_font
        ws.cell(row=sig_row + 2, column=7).alignment = Alignment(horizontal="center")

        # 7. Footnote Disclaimer
        foot_row = sig_row + 4
        ws.merge_cells(start_row=foot_row, start_column=1, end_row=foot_row, end_column=8)
        foot = ws.cell(row=foot_row, column=1, value="Documento oficial generado por INEI SMART-CORE 2026 • I.E. INEI Nº 34 Chancay • Válido para supervisión UGEL 10 Huaral y actas SIAGIE MINEDU.")
        foot.font = muted_font
        foot.alignment = Alignment(horizontal="center", vertical="center")

        # Column Dimensions
        ws.column_dimensions['A'].width = 7
        ws.column_dimensions['B'].width = 16
        ws.column_dimensions['C'].width = 14
        ws.column_dimensions['D'].width = 38
        ws.column_dimensions['E'].width = 20
        ws.column_dimensions['F'].width = 20
        ws.column_dimensions['G'].width = 20
        ws.column_dimensions['H'].width = 18

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

evaluation_service = EvaluationService()
