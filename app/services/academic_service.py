"""
INEI SMART-CORE - Academic Service
Manages Sections, Specialties, Courses, Students, Teachers, and Enrollments.
Fuente Principal de Verdad Curricular: Base de Datos SQLite (tabla courses).
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.database.connection import get_db
from app.config import DATA_DIR
from app.services.audit_service import audit_service


class AcademicService:
    @staticmethod
    def get_sections() -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.grade, s.section_name as section_letter, s.specialty as technical_specialty, 
                       s.shift, s.academic_year, s.capacity,
                       (SELECT COUNT(*) FROM students WHERE section_id = s.id OR (grade = s.grade AND section = s.section_name)) as enrolled_count
                FROM sections s
                ORDER BY s.grade ASC, s.section_name ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_students(section_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            query = """
                SELECT st.id, st.dni as code, st.dni, st.full_name, st.grade, st.section as section_letter,
                       st.specialty as technical_specialty, st.status, st.section_id,
                       p.full_name as parent_name
                FROM students st
                INNER JOIN users u ON st.user_id = u.id
                LEFT JOIN parents p ON st.parent_id = p.id
                WHERE 1=1
            """
            params = []
            if section_id:
                query += " AND st.section_id = ?"
                params.append(section_id)
            query += " ORDER BY st.full_name ASC"

            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_teachers() -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.dni, t.full_name, t.specialty, t.email, t.phone, t.condition, t.academic_degree,
                       (SELECT COUNT(*) FROM courses WHERE teacher_id = t.id AND (is_active IS NULL OR is_active = 1)) as course_count
                FROM teachers t
                ORDER BY t.full_name ASC
                """
            ).fetchall()
            result = []
            for r in rows:
                name_parts = (r["full_name"] or "").split(" ")
                result.append({
                    "id": r["id"],
                    "dni": r["dni"],
                    "full_name": r["full_name"],
                    "first_name": name_parts[0] if name_parts else "",
                    "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                    "specialty": r["specialty"],
                    "email": r["email"],
                    "phone": r["phone"],
                    "condition": r["condition"],
                    "course_count": r["course_count"]
                })
            return result

    @staticmethod
    def _parse_content_tree(content_json_raw: Optional[str]) -> Dict[str, Any]:
        """Deserializa de forma segura el árbol pedagógico del curso."""
        if not content_json_raw:
            return {"units": []}
        try:
            tree = json.loads(content_json_raw)
            if isinstance(tree, list):
                return {"units": tree}
            if isinstance(tree, dict):
                if "units" not in tree:
                    tree["units"] = []
                return tree
            return {"units": []}
        except Exception:
            return {"units": []}

    @staticmethod
    def get_courses(
        teacher_id: Optional[int] = None,
        section_id: Optional[int] = None,
        grade: Optional[str] = None,
        specialty: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retorna la malla curricular completa consultando directamente SQLite (courses).
        Formatea el resultado compatible con las 32 dependencias de los perfiles Docente, Estudiante y Admin.
        """
        with get_db() as conn:
            # Comprobar si existen las columnas extendidas
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(courses)")
            cols = {r["name"] for r in cur.fetchall()}

            has_section_name = "section_name" in cols
            has_room = "room" in cols
            has_content_json = "content_json" in cols
            has_is_active = "is_active" in cols
            has_color_bg = "color_bg" in cols
            has_image_url = "image_url" in cols

            query = f"""
                SELECT c.id, c.code, c.name, c.specialty as technical_specialty, c.grade,
                       c.hours_per_week as weekly_hours, c.syllabus_file, c.teacher_id,
                       {'c.section_name' if has_section_name else "'A' as section_name"},
                       {'c.room' if has_room else "'Aula Polifuncional' as room"},
                       {'c.color_bg' if has_color_bg else "'bg-red-600' as color_bg"},
                       {'c.image_url' if has_image_url else "'' as image_url"},
                       {'c.content_json' if has_content_json else "NULL as content_json"},
                       {'c.is_active' if has_is_active else "1 as is_active"},
                       t.full_name as teacher_name, t.condition as teacher_condition
                FROM courses c
                LEFT JOIN teachers t ON c.teacher_id = t.id
                WHERE 1=1
            """
            params = []
            if not include_inactive and has_is_active:
                query += " AND (c.is_active IS NULL OR c.is_active = 1)"
            if teacher_id:
                query += " AND c.teacher_id = ?"
                params.append(teacher_id)
            if grade:
                query += " AND c.grade = ?"
                params.append(grade)
            if specialty:
                query += " AND (c.specialty = ? OR c.specialty LIKE ?)"
                params.extend([specialty, f"%{specialty}%"])

            query += " ORDER BY c.grade ASC, c.code ASC"

            rows = conn.execute(query, tuple(params)).fetchall()
            result = []

            for r in rows:
                c_dict = dict(r)
                teacher_full = c_dict.get("teacher_name") or "Docente no asignado"
                t_parts = teacher_full.split(" ")
                teacher_first = t_parts[0] if t_parts else ""
                teacher_last = " ".join(t_parts[1:]) if len(t_parts) > 1 else ""

                tree = AcademicService._parse_content_tree(c_dict.get("content_json"))
                units = tree.get("units", [])

                # Contar sesiones y tareas en el árbol pedagógico
                total_sessions = sum(len(u.get("sessions", [])) for u in units)
                total_tasks = sum(len(u.get("tasks", [])) for u in units)

                code = c_dict.get("code") or ""
                name = c_dict.get("name") or ""
                sec = c_dict.get("section_name") or "A"
                grd = c_dict.get("grade") or "5to Grado"
                spec = c_dict.get("technical_specialty") or "Educación para el Trabajo"

                result.append({
                    "id": c_dict["id"],
                    "code": code,
                    "name": name,
                    "fullCode": f"[{code}] {name}",
                    "technical_specialty": spec,
                    "area": "Educación para el Trabajo" if "EPT" in code or "Técnico" in spec else "Formación General",
                    "grade": grd,
                    "section": sec,
                    "section_letter": sec,
                    "weekly_hours": c_dict.get("weekly_hours", 4),
                    "room": c_dict.get("room") or "Aula Polifuncional",
                    "teacher": teacher_full,
                    "teacher_id": c_dict.get("teacher_id"),
                    "teacher_first": teacher_first,
                    "teacher_last": teacher_last,
                    "puesto": tree.get("puesto") or (c_dict.get("teacher_condition") or "Docente Titular"),
                    "progress": tree.get("progress", 0),
                    "sessions": tree.get("sessions") or f"{total_sessions} de 16 Sesiones",
                    "tasksCount": tree.get("tasksCount", total_tasks),
                    "enrolledCount": tree.get("enrolledCount", 10),
                    "colorBg": c_dict.get("color_bg") or "bg-red-600",
                    "image": c_dict.get("image_url") or "https://images.unsplash.com/photo-1581092335397-9583fe92d232?w=600&auto=format&fit=crop&q=80",
                    "syllabus_file": c_dict.get("syllabus_file") or f"Silabo_{code}_2026.pdf",
                    "units": units,
                    "is_active": c_dict.get("is_active", 1)
                })

            return result

    @staticmethod
    def get_course_by_id(course_id: int) -> Optional[Dict[str, Any]]:
        courses = AcademicService.get_courses(include_inactive=True)
        for c in courses:
            if c["id"] == course_id:
                return c
        return None

    @staticmethod
    def create_course(course_data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo curso oficial en la tabla SQLite courses dentro de una transacción atómica."""
        code = str(course_data.get("code", "")).strip().upper()
        name = str(course_data.get("name", "")).strip()
        if not code or not name:
            raise ValueError("El código y nombre del curso son obligatorios.")

        specialty = str(course_data.get("technical_specialty") or course_data.get("specialty") or "Educación para el Trabajo").strip()
        grade = str(course_data.get("grade") or "5to Grado").strip()
        section = str(course_data.get("section") or course_data.get("section_letter") or "A").strip()
        hours = int(course_data.get("weekly_hours") or 4)
        room = str(course_data.get("room") or "Aula Polifuncional").strip()
        color_bg = str(course_data.get("colorBg") or course_data.get("color_bg") or "bg-red-600").strip()
        image_url = str(course_data.get("image") or course_data.get("image_url") or "")
        syllabus_file = str(course_data.get("syllabus_file") or f"Silabo_{code}_2026.pdf")
        
        teacher_id = course_data.get("teacher_id")
        teacher_name = str(course_data.get("teacher") or "").strip()

        with get_db() as conn:
            # Si no viene teacher_id pero sí teacher_name, buscar docente
            if not teacher_id and teacher_name:
                t_row = conn.execute("SELECT id FROM teachers WHERE full_name LIKE ? LIMIT 1", (f"%{teacher_name}%",)).fetchone()
                if t_row:
                    teacher_id = t_row["id"]
                else:
                    teacher_id = 1

            # Validar unicidad del código
            exists = conn.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()
            if exists:
                raise ValueError(f"Ya existe un curso registrado con el código '{code}'.")

            content_tree = {
                "units": course_data.get("units") or [],
                "tasksCount": 0,
                "enrolledCount": int(course_data.get("enrolledCount") or 10),
                "progress": 0,
                "sessions": "0 de 16 Sesiones",
                "puesto": "Docente Titular"
            }
            content_json_str = json.dumps(content_tree, ensure_ascii=False)

            conn.execute(
                """
                INSERT INTO courses (
                    code, name, specialty, grade, section_name, hours_per_week,
                    room, color_bg, image_url, syllabus_file, content_json, teacher_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (code, name, specialty, grade, section, hours, room, color_bg, image_url, syllabus_file, content_json_str, teacher_id)
            )
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Auditoría tras commit
        audit_service.log(
            user_id=user.get("id", 1),
            action="CREATE_COURSE",
            entity_type="COURSE",
            entity_id=new_id,
            details=f"Curso oficial creado en SQLite: [{code}] {name} ({grade} '{section}')"
        )

        # Sincronizar archivo json secundario
        AcademicService.sync_all_courses_to_disk_json()
        return AcademicService.get_course_by_id(new_id)

    @staticmethod
    def update_course(course_id: int, course_data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un curso oficial en SQLite de forma atómica."""
        with get_db() as conn:
            existing = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not existing:
                raise FileNotFoundError(f"Curso con ID {course_id} no encontrado.")

            code = str(course_data.get("code") or existing["code"]).strip().upper()
            name = str(course_data.get("name") or existing["name"]).strip()
            specialty = str(course_data.get("technical_specialty") or course_data.get("specialty") or existing["specialty"]).strip()
            grade = str(course_data.get("grade") or existing["grade"]).strip()
            section = str(course_data.get("section") or course_data.get("section_name") or "A").strip()
            hours = int(course_data.get("weekly_hours") or existing["hours_per_week"] or 4)
            room = str(course_data.get("room") or "Aula Polifuncional").strip()
            color_bg = str(course_data.get("colorBg") or course_data.get("color_bg") or "bg-red-600").strip()
            image_url = str(course_data.get("image") or course_data.get("image_url") or "")
            syllabus_file = str(course_data.get("syllabus_file") or existing["syllabus_file"] or "")

            teacher_id = course_data.get("teacher_id") or existing["teacher_id"]
            teacher_name = str(course_data.get("teacher") or "").strip()
            if teacher_name and not course_data.get("teacher_id"):
                t_row = conn.execute("SELECT id FROM teachers WHERE full_name LIKE ? LIMIT 1", (f"%{teacher_name}%",)).fetchone()
                if t_row:
                    teacher_id = t_row["id"]

            # Si viene content_json o units en el payload, actualizar el árbol
            if "units" in course_data or "content_json" in course_data:
                tree = AcademicService._parse_content_tree(existing["content_json"])
                if "units" in course_data:
                    tree["units"] = course_data["units"]
                if "progress" in course_data:
                    tree["progress"] = course_data["progress"]
                if "sessions" in course_data:
                    tree["sessions"] = course_data["sessions"]
                content_json_str = json.dumps(tree, ensure_ascii=False)
            else:
                content_json_str = existing["content_json"]

            conn.execute(
                """
                UPDATE courses
                SET code = ?, name = ?, specialty = ?, grade = ?, section_name = ?,
                    hours_per_week = ?, room = ?, color_bg = ?, image_url = ?,
                    syllabus_file = ?, content_json = ?, teacher_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (code, name, specialty, grade, section, hours, room, color_bg, image_url, syllabus_file, content_json_str, teacher_id, course_id)
            )

        audit_service.log(
            user_id=user.get("id", 1),
            action="UPDATE_COURSE",
            entity_type="COURSE",
            entity_id=course_id,
            details=f"Curso oficial actualizado en SQLite: [{code}] {name}"
        )

        AcademicService.sync_all_courses_to_disk_json()
        return AcademicService.get_course_by_id(course_id)

    @staticmethod
    def delete_course(course_id: int, user: Dict[str, Any]) -> bool:
        """Desactiva o elimina un curso de la malla curricular con registro en auditoría."""
        with get_db() as conn:
            existing = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not existing:
                return False

            # Desactivar lógicamente para no romper relaciones foráneas en evaluaciones históricas
            conn.execute("UPDATE courses SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (course_id,))

        audit_service.log(
            user_id=user.get("id", 1),
            action="DELETE_COURSE",
            entity_type="COURSE",
            entity_id=course_id,
            details=f"Curso desactivado de la malla oficial: [{existing['code']}] {existing['name']}"
        )

        AcademicService.sync_all_courses_to_disk_json()
        return True

    @staticmethod
    def add_course_unit(course_id: int, unit_data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega una unidad didáctica a un curso en SQLite dentro de content_json."""
        with get_db() as conn:
            course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not course:
                raise FileNotFoundError(f"Curso {course_id} no encontrado.")

            tree = AcademicService._parse_content_tree(course["content_json"])
            units = tree.get("units", [])

            new_unit_id = unit_data.get("id") or (max([u.get("id", 0) for u in units], default=100) + 1)
            new_unit = {
                "id": new_unit_id,
                "number": unit_data.get("number") or (len(units) + 1),
                "title": unit_data.get("title", f"Unidad {len(units) + 1}"),
                "bim": unit_data.get("bim", "I Bimestre"),
                "start_date": unit_data.get("start_date", ""),
                "end_date": unit_data.get("end_date", ""),
                "sessions": unit_data.get("sessions", []),
                "tasks": unit_data.get("tasks", []),
                "exams": unit_data.get("exams", []),
                "materials": unit_data.get("materials", [])
            }
            units.append(new_unit)
            tree["units"] = units

            content_json_str = json.dumps(tree, ensure_ascii=False)
            conn.execute("UPDATE courses SET content_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (content_json_str, course_id))

        audit_service.log(
            user_id=user.get("id", 1),
            action="ADD_COURSE_UNIT",
            entity_type="COURSE_UNIT",
            entity_id=new_unit_id,
            details=f"Unidad agregada al curso ID {course_id}: {new_unit['title']}"
        )

        AcademicService.sync_all_courses_to_disk_json()
        return new_unit

    @staticmethod
    def delete_course_unit(course_id: int, unit_id: int, user: Dict[str, Any]) -> bool:
        """Elimina una unidad didáctica de un curso en SQLite."""
        with get_db() as conn:
            course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not course:
                return False

            tree = AcademicService._parse_content_tree(course["content_json"])
            units = tree.get("units", [])
            filtered_units = [u for u in units if u.get("id") != unit_id]

            if len(filtered_units) == len(units):
                return False

            tree["units"] = filtered_units
            content_json_str = json.dumps(tree, ensure_ascii=False)
            conn.execute("UPDATE courses SET content_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (content_json_str, course_id))

        audit_service.log(
            user_id=user.get("id", 1),
            action="DELETE_COURSE_UNIT",
            entity_type="COURSE_UNIT",
            entity_id=unit_id,
            details=f"Unidad {unit_id} eliminada del curso ID {course_id}"
        )

        AcademicService.sync_all_courses_to_disk_json()
        return True

    @staticmethod
    def add_course_session(course_id: int, unit_id: int, session_data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega o actualiza una sesión de aprendizaje dentro de una unidad didáctica en SQLite."""
        with get_db() as conn:
            course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not course:
                raise FileNotFoundError(f"Curso {course_id} no encontrado.")

            tree = AcademicService._parse_content_tree(course["content_json"])
            units = tree.get("units", [])
            target_unit = None
            for u in units:
                if u.get("id") == unit_id:
                    target_unit = u
                    break

            if not target_unit:
                raise FileNotFoundError(f"Unidad {unit_id} no encontrada en curso {course_id}.")

            sessions = target_unit.get("sessions", [])
            new_session_id = session_data.get("id") or (max([s.get("id", 0) for s in sessions], default=0) + 1)
            
            # Comprobar si ya existe para editar
            existing_s_idx = next((i for i, s in enumerate(sessions) if s.get("id") == new_session_id), -1)
            
            session_entry = {
                "id": new_session_id,
                "num": session_data.get("num") or (len(sessions) + 1),
                "title": session_data.get("title", f"Sesión {len(sessions) + 1}"),
                "type": session_data.get("type", "Taller Práctico"),
                "date": session_data.get("date", ""),
                "duration": session_data.get("duration", "90 min"),
                "room": session_data.get("room", course["room"] if "room" in course.keys() else "Taller"),
                "status": session_data.get("status", "Pendiente"),
                "verified": session_data.get("verified", False),
                "signed": session_data.get("signed", False),
                "pdf_file": session_data.get("pdf_file", ""),
                "docx_file": session_data.get("docx_file", "")
            }

            if existing_s_idx >= 0:
                sessions[existing_s_idx] = session_entry
            else:
                sessions.append(session_entry)

            target_unit["sessions"] = sessions
            tree["sessions"] = f"{sum(len(u.get('sessions', [])) for u in units)} de 16 Sesiones"
            content_json_str = json.dumps(tree, ensure_ascii=False)
            conn.execute("UPDATE courses SET content_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (content_json_str, course_id))

        audit_service.log(
            user_id=user.get("id", 1),
            action="SAVE_COURSE_SESSION",
            entity_type="COURSE_SESSION",
            entity_id=new_session_id,
            details=f"Sesión guardada en curso {course_id}, unidad {unit_id}: {session_entry['title']}"
        )

        AcademicService.sync_all_courses_to_disk_json()
        return session_entry

    @staticmethod
    def sync_all_courses_to_disk_json() -> bool:
        """
        Sincroniza el catálogo completo de SQLite courses hacia data/courses_content.json
        para mantener compatibilidad y soporte de respaldo.
        """
        try:
            courses = AcademicService.get_courses(include_inactive=False)
            file_path = DATA_DIR / "courses_content.json"
            temp_path = DATA_DIR / "courses_content.json.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(courses, f, ensure_ascii=False, indent=2)
            temp_path.replace(file_path)
            return True
        except Exception:
            return False

    @staticmethod
    def get_enrollments(year: int = 2026) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT e.*, st.full_name, st.dni, st.grade, st.section as section_letter, st.specialty as technical_specialty
                FROM enrollments e
                JOIN students st ON e.student_id = st.id
                INNER JOIN users u ON st.user_id = u.id
                WHERE e.academic_year = ? OR e.academic_year = '2026'
                ORDER BY e.id DESC
                """, (str(year),)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_student(
        dni: str,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        section_id: int,
        student_code: str
    ) -> Dict[str, Any]:
        with get_db() as conn:
            full_name = f"{first_name} {last_name}".strip()
            existing = conn.execute("SELECT id FROM students WHERE dni = ?", (dni,)).fetchone()
            if existing:
                return {"success": False, "error": "Ya existe un estudiante con este DNI"}

            sec = conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
            grade = sec["grade"] if sec else "5to"
            section = sec["section_name"] if sec else "A"
            specialty = sec["specialty"] if sec else "Mecánica de Producción"

            conn.execute(
                """
                INSERT INTO students (dni, full_name, specialty, grade, section, section_id, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Activo')
                """, (dni, full_name, specialty, grade, section, section_id)
            )
            student_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """
                INSERT INTO enrollments (student_id, section_id, academic_year, status)
                VALUES (?, ?, '2026', 'Matriculado')
                """, (student_id, section_id)
            )

            return {"success": True, "student_id": student_id}


academic_service = AcademicService()
