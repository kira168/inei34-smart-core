"""
INEI SMART-CORE 2.0 - Servicio de Soporte Técnico y Mesa de Ayuda TI
Gestión de incidencias, tickets institucionales y chat bidireccional entre usuarios y el Administrador.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database.connection import db_session

class SupportService:
    def get_stats(self) -> Dict[str, Any]:
        """Calcula métricas globales de atención de la Mesa de Ayuda."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets")
            total = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'PENDIENTE'")
            pendientes = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'EN ATENCIÓN'")
            en_atencion = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'RESUELTO'")
            resueltos = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE priority = 'ALTA' AND status != 'RESUELTO'")
            urgentes = cursor.fetchone()[0] or 0

            return {
                "total": total,
                "pendientes": pendientes,
                "en_atencion": en_atencion,
                "resueltos": resueltos,
                "urgentes": urgentes,
                "tasa_resolucion": f"{round((resueltos / total * 100), 1)}%" if total > 0 else "100%"
            }

    def list_tickets(
        self, 
        user_id: Optional[int] = None, 
        role: Optional[str] = None, 
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista tickets con datos del usuario y teléfono para contacto directo.
        """
        query = """
            SELECT t.*, COALESCE(u.phone, '992345678') as user_phone
            FROM support_tickets t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE 1=1
        """
        params = []

        if user_id is not None:
            query += " AND t.user_id = ?"
            params.append(user_id)

        if status and status.upper() != 'TODOS':
            query += " AND UPPER(t.status) = UPPER(?)"
            params.append(status)

        if role and role.upper() != 'TODOS':
            query += " AND UPPER(t.user_role) = UPPER(?)"
            params.append(role)

        if search:
            query += " AND (t.ticket_code LIKE ? OR t.subject LIKE ? OR t.user_name LIKE ? OR t.description LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s])

        query += """ ORDER BY 
            CASE t.status 
                WHEN 'PENDIENTE' THEN 1 
                WHEN 'EN ATENCIÓN' THEN 2 
                WHEN 'RESUELTO' THEN 3 
                ELSE 4 
            END, t.id DESC"""

        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, COALESCE(u.phone, '992345678') as user_phone
                FROM support_tickets t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.id = ?
            """, (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_ticket(
        self,
        user_id: int,
        user_name: str,
        user_role: str,
        user_email: Optional[str],
        user_dni: Optional[str],
        subject: str,
        priority: str = "MEDIA",
        area: str = "General",
        description: str = ""
    ) -> Dict[str, Any]:
        """Crea un nuevo ticket y le asigna un código incremental oficial TCK-2026-XXX."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM support_tickets")
            max_id = cursor.fetchone()[0] or 0
            next_code = f"TCK-2026-{(max_id + 1):03d}"

            cursor.execute("""
            INSERT INTO support_tickets 
            (ticket_code, user_id, user_name, user_role, user_email, user_dni, subject, priority, area, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE')
            """, (next_code, user_id, user_name, user_role, user_email or '', user_dni or '', subject, priority, area, description))
            
            new_id = cursor.lastrowid
            cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (new_id,))
            return dict(cursor.fetchone())

    def update_ticket(
        self,
        ticket_id: int,
        status: str,
        solution: Optional[str] = None,
        admin_response_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """El administrador actualiza el estado, registra la solución y fecha de resolución."""
        resolved_at = datetime.now().strftime("%d/%m/%Y %I:%M %p") if status.upper() == "RESUELTO" else None
        
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE support_tickets
            SET status = ?,
                solution = COALESCE(?, solution),
                admin_response_by = COALESCE(?, admin_response_by),
                resolved_at = COALESCE(?, resolved_at),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (status, solution, admin_response_by, resolved_at, ticket_id))

            cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_chat_messages(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Obtiene el historial de chat. Si se especifica user_id, devuelve el hilo de ese usuario."""
        with db_session() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                SELECT * FROM support_chat_messages 
                WHERE user_id = ? 
                ORDER BY id ASC
                """, (user_id,))
            else:
                cursor.execute("SELECT * FROM support_chat_messages ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def list_chat_threads(self) -> List[Dict[str, Any]]:
        """Lista para el administrador las conversaciones activas agrupadas estrictamente por usuario (sin duplicados)."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT m.user_id,
                   COALESCE(u.full_name, MAX(m.user_name)) as user_name,
                   COALESCE(u.role, MAX(m.user_role)) as user_role,
                   COALESCE(u.phone, '992345678') as user_phone,
                   MAX(m.created_at) as last_activity,
                   COALESCE(
                       (SELECT text FROM support_chat_messages sub 
                        WHERE sub.user_id = m.user_id AND sub.sender != 'bot'
                        ORDER BY sub.id DESC LIMIT 1),
                       (SELECT text FROM support_chat_messages sub 
                        WHERE sub.user_id = m.user_id 
                        ORDER BY sub.id DESC LIMIT 1)
                   ) as last_message,
                   (SELECT sender FROM support_chat_messages sub 
                    WHERE sub.user_id = m.user_id 
                    ORDER BY sub.id DESC LIMIT 1) as last_sender,
                   COUNT(m.id) as total_messages
            FROM support_chat_messages m
            LEFT JOIN users u ON m.user_id = u.id
            GROUP BY m.user_id
            ORDER BY last_activity DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def add_chat_message(
        self,
        user_id: int,
        user_name: str,
        user_role: str,
        sender: str, # 'user', 'admin', 'bot'
        text: str
    ) -> Dict[str, Any]:
        """Registra un mensaje en el chat institucional con datos normalizados."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT full_name, role FROM users WHERE id = ?", (user_id,))
            u = cursor.fetchone()
            if u:
                if u["full_name"]:
                    user_name = u["full_name"]
                if u["role"]:
                    user_role = u["role"]

            cursor.execute("""
            INSERT INTO support_chat_messages (user_id, user_name, user_role, sender, text)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id, user_name, user_role, sender, text))
            new_id = cursor.lastrowid
            cursor.execute("SELECT * FROM support_chat_messages WHERE id = ?", (new_id,))
            return dict(cursor.fetchone())


    def clear_chat_messages(self, user_id: int) -> bool:
        """Elimina el historial de mensajes de soporte para iniciar un nuevo chat."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM support_chat_messages WHERE user_id = ?", (user_id,))
            return True

support_service = SupportService()
