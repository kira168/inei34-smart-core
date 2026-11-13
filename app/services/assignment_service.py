"""
INEI SMART-CORE - Assignment & Submission Service
Handles workshop tasks, student deliveries, feedback, and grading.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from app.database.connection import get_db

class AssignmentService:
    @staticmethod
    def get_course_assignments(course_id: int) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT a.*, c.name as course_name, c.specialty, c.grade,
                       (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.id) as submissions_count,
                       (SELECT COUNT(*) FROM students s WHERE s.grade = c.grade AND s.specialty = c.specialty) as total_students
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                WHERE a.course_id = ?
                ORDER BY a.created_at DESC
                """, (course_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_all_assignments(teacher_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            query = """
                SELECT a.*, c.name as course_name, c.specialty, c.grade, t.full_name as teacher_name,
                       (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.id) as submissions_count,
                       (SELECT COUNT(*) FROM students s WHERE s.grade = c.grade AND s.specialty = c.specialty) as total_students
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                LEFT JOIN teachers t ON a.teacher_id = t.id
                WHERE 1=1
            """
            params = []
            if teacher_id:
                query += " AND (a.teacher_id = ? OR c.teacher_id = ?)"
                params.extend([teacher_id, teacher_id])
            
            query += " ORDER BY a.due_date DESC, a.created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_assignment_by_id(assignment_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT a.*, c.name as course_name, c.specialty, c.grade, t.full_name as teacher_name
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                LEFT JOIN teachers t ON a.teacher_id = t.id
                WHERE a.id = ?
                """, (assignment_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_assignment(
        course_id: int,
        teacher_id: int,
        title: str,
        description: str,
        due_date: str,
        attachment_file: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO assignments (course_id, teacher_id, title, description, due_date, attachment_file)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (course_id, teacher_id, title, description, due_date, attachment_file)
            )
            aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"success": True, "assignment_id": aid, "message": "Tarea técnica publicada y enviada a los estudiantes exitosamente."}

    @staticmethod
    def update_assignment(
        assignment_id: int,
        title: str,
        description: str,
        due_date: str,
        course_id: Optional[int] = None,
        attachment_file: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            if course_id:
                conn.execute(
                    """
                    UPDATE assignments
                    SET title = ?, description = ?, due_date = ?, course_id = ?,
                        attachment_file = COALESCE(?, attachment_file)
                    WHERE id = ?
                    """, (title, description, due_date, course_id, attachment_file, assignment_id)
                )
            else:
                conn.execute(
                    """
                    UPDATE assignments
                    SET title = ?, description = ?, due_date = ?,
                        attachment_file = COALESCE(?, attachment_file)
                    WHERE id = ?
                    """, (title, description, due_date, attachment_file, assignment_id)
                )
            return {"success": True, "message": "Tarea técnica actualizada exitosamente."}

    @staticmethod
    def delete_assignment(assignment_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute("DELETE FROM submissions WHERE assignment_id = ?", (assignment_id,))
            conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
            return {"success": True, "message": "Tarea eliminada exitosamente."}

    @staticmethod
    def get_assignment_submissions(assignment_id: int) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT sub.*, s.full_name as student_name, s.dni as student_dni, s.grade, s.section, s.specialty
                FROM submissions sub
                JOIN students s ON sub.student_id = s.id
                WHERE sub.assignment_id = ?
                ORDER BY sub.submitted_at DESC
                """, (assignment_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_student_assignments(student_id: int) -> List[Dict[str, Any]]:
        with get_db() as conn:
            student = conn.execute("SELECT grade, specialty, section FROM students WHERE id = ?", (student_id,)).fetchone()
            if not student:
                return []

            rows = conn.execute(
                """
                SELECT a.*, c.name as course_name, c.specialty, c.grade, t.full_name as teacher_name,
                       sub.id as submission_id, sub.grade as submission_grade, 
                       sub.submitted_at, sub.feedback, sub.file_path as submission_file, sub.submission_text
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                LEFT JOIN teachers t ON a.teacher_id = t.id
                LEFT JOIN submissions sub ON sub.assignment_id = a.id AND sub.student_id = ?
                WHERE c.grade = ? AND (c.specialty = ? OR c.specialty = 'General' OR c.specialty = 'Educación para el Trabajo')
                ORDER BY a.due_date ASC
                """, (student_id, student["grade"], student["specialty"])
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def submit_assignment(
        assignment_id: int,
        student_id: int,
        file_path: Optional[str] = None,
        submission_text: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            existing = conn.execute(
                "SELECT id FROM submissions WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, student_id)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE submissions 
                    SET file_path = COALESCE(?, file_path), submission_text = COALESCE(?, submission_text), submitted_at = ?
                    WHERE id = ?
                    """, (file_path, submission_text, now_str, existing["id"])
                )
            else:
                conn.execute(
                    """
                    INSERT INTO submissions (assignment_id, student_id, file_path, submission_text, submitted_at, grade)
                    VALUES (?, ?, ?, ?, ?, 'ENTREGADO')
                    """, (assignment_id, student_id, file_path, submission_text, now_str)
                )

            return {"success": True, "message": "Entrega de tarea registrada correctamente en el repositorio de taller."}

    @staticmethod
    def grade_submission(
        submission_id: int,
        grade: str,
        feedback: str
    ) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE submissions 
                SET grade = ?, feedback = ?
                WHERE id = ?
                """, (grade, feedback, submission_id)
            )
            return {"success": True, "message": "Calificación y retroalimentación registradas con éxito."}


assignment_service = AssignmentService()
