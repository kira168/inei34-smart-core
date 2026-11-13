"""
INEI SMART-CORE - Audit Service
Immutable Forensic Logging for Security & Traceability.
"""

from typing import Dict, Any, List, Optional
from app.database.connection import get_db

class AuditService:
    @staticmethod
    def log(
        user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        conn=None
    ) -> None:
        try:
            if conn is not None:
                user = conn.execute("SELECT username, role FROM users WHERE id = ?", (user_id,)).fetchone()
                username = user["username"] if user else "system"
                role = user["role"] if user else "system"
                conn.execute(
                    """
                    INSERT INTO audit_logs (user_id, username, role, action, module, record_id, details, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, username, role, action, entity_type, str(entity_id or ""), details, ip_address or "127.0.0.1")
                )
            else:
                with get_db() as c:
                    user = c.execute("SELECT username, role FROM users WHERE id = ?", (user_id,)).fetchone()
                    username = user["username"] if user else "system"
                    role = user["role"] if user else "system"
                    c.execute(
                        """
                        INSERT INTO audit_logs (user_id, username, role, action, module, record_id, details, ip_address)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (user_id, username, role, action, entity_type, str(entity_id or ""), details, ip_address or "127.0.0.1")
                    )
        except Exception:
            pass

    @staticmethod
    def get_logs(limit: int = 100) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT a.*, u.full_name
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                ORDER BY a.id DESC
                LIMIT ?
                """, (limit,)
            ).fetchall()
            result = []
            for r in rows:
                full_name = r["full_name"] or r["username"]
                name_parts = full_name.split(" ")
                result.append({
                    "id": r["id"],
                    "created_at": r["timestamp"],
                    "first_name": name_parts[0],
                    "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                    "role_name": r["role"].upper(),
                    "action": r["action"],
                    "details": r["details"]
                })
            return result


audit_service = AuditService()
