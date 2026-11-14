"""
INEI SMART-CORE - Communication Service
Handles Institutional Announcements, In-App Notifications, and Parent Appointments.
"""

from typing import Dict, Any, List, Optional
from app.database.connection import get_db

class CommunicationService:
    @staticmethod
    def get_announcements(target_role: str = "TODOS") -> List[Dict[str, Any]]:
        with get_db() as conn:
            query = "SELECT * FROM announcements WHERE 1=1"
            params = []
            role_norm = (target_role or "TODOS").strip().upper()
            
            if role_norm != "TODOS":
                matched_audiences = ["TODOS", role_norm]
                if "DOCENT" in role_norm:
                    matched_audiences.extend(["DOCENTE", "DOCENTES"])
                elif "ESTUDIANT" in role_norm or "ALUMN" in role_norm:
                    matched_audiences.extend(["ESTUDIANTE", "ESTUDIANTES", "ALUMNO", "ALUMNOS"])
                elif "PADRE" in role_norm or "APODERAD" in role_norm:
                    matched_audiences.extend(["PADRE", "PADRES", "APODERADO", "APODERADOS", "FAMILIA"])
                
                unique_audiences = list(set(matched_audiences))
                placeholders = ",".join("?" for _ in unique_audiences)
                query += f" AND audience IN ({placeholders})"
                params = unique_audiences

            query += " ORDER BY id DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            result = []
            for r in rows:
                name_parts = (r["author_name"] or "").split(" ")
                result.append({
                    "id": r["id"],
                    "title": r["title"],
                    "content": r["content"],
                    "audience": r["audience"],
                    "target_role": r["audience"],
                    "tag": r["tag"],
                    "created_at": r["created_at"],
                    "first_name": name_parts[0] if name_parts else "",
                    "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                    "author_name": r["author_name"],
                    "author_role": r["tag"]
                })
            return result

    @staticmethod
    def create_announcement(
        author_id: int,
        title: str,
        content: str,
        target_role: str = "TODOS",
        tag: str = "General"
    ) -> Dict[str, Any]:
        with get_db() as conn:
            user = conn.execute("SELECT full_name, role FROM users WHERE id = ?", (author_id,)).fetchone()
            author_name = user["full_name"] if user else "Dirección INEI 34"
            if not tag or tag == "General":
                tag = user["role"].capitalize() if user else "General"
            conn.execute(
                """
                INSERT INTO announcements (title, content, author_id, author_name, audience, tag)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, author_id, author_name, target_role, tag)
            )
            aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"success": True, "announcement_id": aid, "message": "Comunicado publicado con éxito a la comunidad escolar."}

    @staticmethod
    def update_announcement(
        announcement_id: int,
        title: str,
        content: str,
        target_role: str = "TODOS",
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            if tag:
                conn.execute(
                    "UPDATE announcements SET title = ?, content = ?, audience = ?, tag = ? WHERE id = ?",
                    (title, content, target_role, tag, announcement_id)
                )
            else:
                conn.execute(
                    "UPDATE announcements SET title = ?, content = ?, audience = ? WHERE id = ?",
                    (title, content, target_role, announcement_id)
                )
            return {"success": True, "message": "Comunicado actualizado correctamente"}

    @staticmethod
    def delete_announcement(announcement_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
            return {"success": True, "message": "Comunicado eliminado"}

    @staticmethod
    def get_user_notifications(user_id: int) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, title, message, type, is_read, link, created_at
                FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC LIMIT 50
                """, (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def mark_notification_read(notification_id: int, user_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                (notification_id, user_id)
            )
            return {"success": True}

    @staticmethod
    def mark_all_read(user_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
            return {"success": True, "message": "Todas las notificaciones marcadas como leídas"}

    @staticmethod
    def mark_all_notifications_read(user_id: int) -> Dict[str, Any]:
        return CommunicationService.mark_all_read(user_id)

    @staticmethod
    def create_notification(user_id: int, title: str, message: str, n_type: str = "INFO", link: Optional[str] = None, **kwargs):
        actual_type = kwargs.get("type", n_type)
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (?, ?, ?, ?, ?)
                """, (user_id, title, message, actual_type, link)
            )

    @staticmethod
    def create_notification_for_role(role: str, title: str, message: str, n_type: str = "INFO", link: Optional[str] = None, **kwargs):
        actual_type = kwargs.get("type", n_type)
        with get_db() as conn:
            rows = conn.execute("SELECT id FROM users WHERE UPPER(role) = UPPER(?)", (role,)).fetchall()
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO notifications (user_id, title, message, type, link)
                    VALUES (?, ?, ?, ?, ?)
                    """, (r["id"], title, message, actual_type, link)
                )

    @staticmethod
    def get_parent_appointments(parent_id: int) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT a.id, a.parent_id, a.teacher_id, a.student_id, a.scheduled_at, a.reason, a.status,
                       u.full_name as teacher_name, s.full_name as student_name
                FROM appointments a
                JOIN users u ON a.teacher_id = u.id
                JOIN users s ON a.student_id = s.id
                WHERE a.parent_id = ?
                ORDER BY a.scheduled_at DESC
                """, (parent_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_appointment(parent_id: int, teacher_id: int, student_id: int, scheduled_at: str, reason: str) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO appointments (parent_id, teacher_id, student_id, scheduled_at, reason, status)
                VALUES (?, ?, ?, ?, ?, 'PENDIENTE')
                """, (parent_id, teacher_id, student_id, scheduled_at, reason)
            )
            aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"success": True, "appointment_id": aid, "message": "Cita de tutoría agendada con éxito."}

communication_service = CommunicationService()
