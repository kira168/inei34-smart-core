"""
INEI SMART-CORE - Dashboard Service
Aggregates key educational indicators per role.
"""

from typing import Dict, Any, List
from app.database.connection import get_db
from app.auth.rbac import normalize_role

class DashboardService:
    @staticmethod
    def get_dashboard_data(user: Dict[str, Any]) -> Dict[str, Any]:
        raw_role = user.get("role") or user.get("role_name") or "ESTUDIANTE"
        role = normalize_role(raw_role)
        user_id = user.get("id") or user.get("user_id")

        with get_db() as conn:
            if role in ["ADMINISTRADOR", "DIRECTOR"]:
                return DashboardService._get_director_dashboard(conn)
            elif role == "DOCENTE":
                return DashboardService._get_teacher_dashboard(conn, user_id)
            elif role == "ESTUDIANTE":
                return DashboardService._get_student_dashboard(conn, user_id)
            elif role in ["PADRE", "APODERADO"]:
                return DashboardService._get_parent_dashboard(conn, user_id)
            elif role == "SECRETARÍA":
                return DashboardService._get_secretary_dashboard(conn)
            else:
                return {"message": f"Panel para {role}", "stats": {}}

    @staticmethod
    def _get_director_dashboard(conn) -> Dict[str, Any]:
        students_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        teachers_count = conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
        sections_count = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        expedientes_pendientes = conn.execute("SELECT COUNT(*) FROM mesa_partes_solicitudes WHERE status IN ('RECIBIDO', 'EN PROCESO', 'PENDIENTE')").fetchone()[0]

        # Attendance summary
        att_stats = conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM attendance
            GROUP BY status
            """
        ).fetchall()
        att_map = {r["status"]: r["count"] for r in att_stats}

        # Early warnings
        warnings = conn.execute(
            """
            SELECT ew.id, ew.student_id, ew.warning_type, ew.severity, ew.description, ew.status,
                   st.full_name as student_name, st.grade, st.section as section_letter, st.specialty as technical_specialty
            FROM early_warnings ew
            JOIN students st ON ew.student_id = st.id
            WHERE ew.status IN ('ABIERTA', 'ACTIVA')
            LIMIT 5
            """
        ).fetchall()

        # Specialties breakdown
        specialties = conn.execute(
            """
            SELECT specialty as technical_specialty, COUNT(*) as total_students
            FROM students
            GROUP BY specialty
            """
        ).fetchall()

        # Recent audit actions with user info
        audits = conn.execute(
            """
            SELECT id, user_id, username, role, action, module, details, ip_address, timestamp
            FROM audit_logs
            ORDER BY id DESC
            LIMIT 6
            """
        ).fetchall()

        return {
            "role": "DIRECTOR",
            "kpis": {
                "total_students": students_count,
                "total_teachers": teachers_count,
                "total_sections": sections_count,
                "pending_expedientes": expedientes_pendientes
            },
            "attendance_breakdown": {
                "present": att_map.get("P", 0) + att_map.get("PRESENTE", 0),
                "late": att_map.get("T", 0) + att_map.get("TARDANZA", 0),
                "absent": att_map.get("F", 0) + att_map.get("FALTA", 0),
                "justified": att_map.get("J", 0) + att_map.get("JUSTIFICADO", 0)
            },
            "specialties": [dict(s) for s in specialties],
            "early_warnings": [
                {
                    "first_name": w["student_name"].split(" ")[0] if w["student_name"] else "Estudiante",
                    "last_name": " ".join(w["student_name"].split(" ")[1:]) if w["student_name"] else "",
                    "grade": w["grade"],
                    "section_letter": w["section_letter"],
                    "warning_type": w["warning_type"],
                    "risk_level": w["severity"] if "severity" in w.keys() and w["severity"] else "ALTO",
                    "description": w["description"]
                } for w in warnings
            ],
            "recent_activity": [dict(a) for a in audits]
        }

    @staticmethod
    def _get_teacher_dashboard(conn, user_id: int) -> Dict[str, Any]:
        teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ? OR id = ?", (user_id, user_id)).fetchone()
        if not teacher:
            teacher = conn.execute("SELECT * FROM teachers LIMIT 1").fetchone()

        t_id = teacher["id"] if teacher else 1
        courses = conn.execute(
            """
            SELECT c.*, c.specialty as technical_specialty, c.grade, 'A' as section_letter,
                   (SELECT COUNT(*) FROM students WHERE specialty = c.specialty) as student_count
            FROM courses c
            WHERE c.teacher_id = ?
            """, (t_id,)
        ).fetchall()

        return {
            "role": "DOCENTE",
            "teacher_info": dict(teacher) if teacher else {},
            "courses": [dict(c) for c in courses],
            "total_courses": len(courses)
        }

    @staticmethod
    def _get_student_dashboard(conn, user_id: int) -> Dict[str, Any]:
        student = conn.execute("SELECT * FROM students WHERE user_id = ? OR id = ?", (user_id, user_id)).fetchone()
        if not student:
            student = conn.execute("SELECT * FROM students LIMIT 1").fetchone()

        spec = student["specialty"] if student else "Mecánica de Producción"
        courses = conn.execute(
            """
            SELECT c.*, t.full_name as teacher_name
            FROM courses c
            LEFT JOIN teachers t ON c.teacher_id = t.id
            WHERE c.specialty = ?
            """, (spec,)
        ).fetchall()

        s_id = student["id"] if student else 1
        assignments = conn.execute(
            """
            SELECT a.*, c.name as course_name, sub.grade as score,
                   CASE WHEN sub.id IS NOT NULL THEN 'ENTREGADO' ELSE 'PENDIENTE' END as submission_status
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            LEFT JOIN submissions sub ON sub.assignment_id = a.id AND sub.student_id = ?
            ORDER BY a.due_date ASC
            LIMIT 6
            """, (s_id,)
        ).fetchall()

        evals = conn.execute(
            """
            SELECT e.*, c.name as course_name
            FROM evaluations e
            JOIN courses c ON e.course_id = c.id
            WHERE e.student_id = ?
            """, (s_id,)
        ).fetchall()

        return {
            "role": "ESTUDIANTE",
            "student_info": {
                "id": s_id,
                "grade": student["grade"] if student else "5to",
                "section_letter": student["section"] if student else "A",
                "technical_specialty": spec,
                "full_name": student["full_name"] if student else "Estudiante"
            },
            "courses": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "weekly_hours": c["hours_per_week"] if "hours_per_week" in c.keys() else 4,
                    "teacher_first": c["teacher_name"].split(" ")[0] if c["teacher_name"] else "Prof.",
                    "teacher_last": " ".join(c["teacher_name"].split(" ")[1:]) if c["teacher_name"] else "Docente"
                } for c in courses
            ],
            "assignments": [dict(a) for a in assignments],
            "evaluations": [dict(e) for e in evals]
        }

    @staticmethod
    def _get_parent_dashboard(conn, user_id: int) -> Dict[str, Any]:
        parent = conn.execute("SELECT * FROM parents WHERE user_id = ? OR id = ?", (user_id, user_id)).fetchone()
        if not parent:
            parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()

        p_id = parent["id"] if parent else 1
        children = conn.execute("SELECT * FROM students WHERE parent_id = ?", (p_id,)).fetchall()
        if not children:
            children = conn.execute("SELECT * FROM students LIMIT 1").fetchall()

        children_data = []
        for ch in children:
            ch_dict = {
                "student_id": ch["id"],
                "code": ch["dni"],
                "first_name": ch["full_name"].split(" ")[0],
                "last_name": " ".join(ch["full_name"].split(" ")[1:]),
                "grade": ch["grade"],
                "section_letter": ch["section"],
                "technical_specialty": ch["specialty"]
            }
            # Grades
            grades = conn.execute(
                """
                SELECT c.name as course_name, e.bimester, e.final_grade as final_score
                FROM evaluations e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = ?
                """, (ch["id"],)
            ).fetchall()
            ch_dict["grades"] = [dict(g) for g in grades]

            # Attendance
            att = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM attendance
                WHERE student_id = ?
                GROUP BY status
                """, (ch["id"],)
            ).fetchall()
            att_map = {a["status"]: a["count"] for a in att}
            ch_dict["attendance"] = {
                "PRESENTE": att_map.get("P", 0) + att_map.get("PRESENTE", 0),
                "TARDANZA": att_map.get("T", 0) + att_map.get("TARDANZA", 0),
                "FALTA": att_map.get("F", 0) + att_map.get("FALTA", 0),
                "JUSTIFICADO": att_map.get("J", 0) + att_map.get("JUSTIFICADO", 0)
            }
            children_data.append(ch_dict)

        return {
            "role": "PADRE",
            "parent_info": dict(parent) if parent else {},
            "children": children_data
        }

    @staticmethod
    def _get_secretary_dashboard(conn) -> Dict[str, Any]:
        expedientes = conn.execute("SELECT * FROM mesa_partes_solicitudes ORDER BY id DESC LIMIT 10").fetchall()
        pending_enrollments = conn.execute("SELECT COUNT(*) FROM enrollments WHERE status = 'En Trámite'").fetchone()[0]

        return {
            "role": "SECRETARÍA",
            "expedientes": [
                {
                    "codigo_expediente": e["expediente_code"],
                    "solicitante_nombre": e["solicitante_name"],
                    "solicitante_dni": e["solicitante_dni"],
                    "tipo_solicitud": e["tipo_tramite"],
                    "asunto": e["asunto"],
                    "status": e["status"]
                } for e in expedientes
            ],
            "pending_enrollments": pending_enrollments,
            "total_documents": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        }


dashboard_service = DashboardService()

