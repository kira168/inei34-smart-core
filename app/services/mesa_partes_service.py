"""
INEI SMART-CORE - Mesa de Partes Virtual Service
Manages Citizen & Internal Procedures with secure EXP-2026-XXXX tracking and abuse prevention.
"""

import time
import secrets
import string
from typing import Dict, Any, List, Optional, Tuple
from app.database.connection import get_db
from app.config import MESA_PARTES_RATE_LIMIT, MESA_PARTES_RATE_WINDOW_SECONDS

class MesaPartesService:
    @staticmethod
    def generate_tracking_code(conn) -> str:
        """
        Genera un código de expediente no predecible conservando el prefijo oficial EXP-2026-.
        Utiliza un token aleatorio criptográficamente seguro de 8 caracteres alfanuméricos.
        Verifica unicidad en la base de datos para evitar colisiones.
        """
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            token = "".join(secrets.choice(alphabet) for _ in range(8))
            candidate_code = f"EXP-2026-{token}"
            exists = conn.execute(
                "SELECT 1 FROM mesa_partes_solicitudes WHERE UPPER(expediente_code) = ?",
                (candidate_code,)
            ).fetchone()
            if not exists:
                return candidate_code
        # Fallback de seguridad si hubiera colisión extrema
        hex_token = secrets.token_hex(4).upper()
        return f"EXP-2026-{hex_token}"

    @staticmethod
    def check_and_record_rate_limit(
        ip_address: str,
        limit: int = MESA_PARTES_RATE_LIMIT,
        window_seconds: int = MESA_PARTES_RATE_WINDOW_SECONDS
    ) -> Tuple[bool, int, int]:
        """
        Verifica y registra solicitudes en mesa_partes_rate_limits.
        Garantiza consistencia multiproceso en SQLite.
        Retorna: (permitido: bool, solicitudes_actuales: int, retry_after_seconds: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with get_db() as conn:
            # Asegurar tabla de rate limits
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mesa_partes_rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            # Limpiar entradas más antiguas que la ventana para mantener la tabla compacta
            conn.execute("DELETE FROM mesa_partes_rate_limits WHERE timestamp < ?", (window_start,))

            # Contar peticiones de la IP dentro de la ventana
            count_row = conn.execute(
                "SELECT COUNT(*), MIN(timestamp) FROM mesa_partes_rate_limits WHERE ip_address = ? AND timestamp >= ?",
                (ip_address, window_start)
            ).fetchone()
            current_count = count_row[0] if count_row else 0
            oldest_ts = count_row[1] if count_row and count_row[1] is not None else now

            if current_count >= limit:
                # Excedió el límite
                retry_after = max(1, int(oldest_ts + window_seconds - now))
                return False, current_count, retry_after

            # Registrar la solicitud actual
            conn.execute(
                "INSERT INTO mesa_partes_rate_limits (ip_address, timestamp) VALUES (?, ?)",
                (ip_address, now)
            )
            return True, current_count + 1, 0

    @staticmethod
    def create_request(
        solicitante_nombre: str,
        solicitante_dni: str,
        solicitante_email: str,
        solicitante_telefono: str,
        asunto: str,
        tipo_solicitud: str,
        descripcion: str,
        archivo_adjunto: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            code = MesaPartesService.generate_tracking_code(conn)
            conn.execute(
                """
                INSERT INTO mesa_partes_solicitudes 
                (expediente_code, solicitante_dni, solicitante_name, solicitante_email, solicitante_phone, tipo_tramite, asunto, observaciones, documento_adjunto, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RECIBIDO')
                """, (code, solicitante_dni, solicitante_nombre, solicitante_email, solicitante_telefono, tipo_solicitud, asunto, descripcion, archivo_adjunto)
            )
            req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"success": True, "codigo_expediente": code, "id": req_id, "message": f"Expediente {code} radicado exitosamente."}

    @staticmethod
    def get_requests(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            query = "SELECT * FROM mesa_partes_solicitudes WHERE 1=1"
            params = []
            if status_filter and status_filter != "TODOS":
                query += " AND status = ?"
                params.append(status_filter)
            query += " ORDER BY id DESC"

            rows = conn.execute(query, tuple(params)).fetchall()
            result = []
            for r in rows:
                result.append({
                    "id": r["id"],
                    "codigo_expediente": r["expediente_code"],
                    "solicitante_dni": r["solicitante_dni"],
                    "solicitante_nombre": r["solicitante_name"],
                    "solicitante_email": r["solicitante_email"],
                    "solicitante_telefono": r["solicitante_phone"],
                    "tipo_solicitud": r["tipo_tramite"],
                    "asunto": r["asunto"],
                    "status": r["status"],
                    "created_at": r["fecha_registro"],
                    "observaciones": r["observaciones"]
                })
            return result

    @staticmethod
    def track_request_public(codigo_expediente: str) -> Optional[Dict[str, Any]]:
        """
        Consulta pública de expediente: protege la privacidad ciudadana.
        NO retorna DNI, nombres de personas, correo, teléfono ni domicilio.
        Retorna únicamente metadatos administrativos indispensables:
        código, estado, tipo de trámite, asunto genérico, fecha de registro y resolución oficial.
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT expediente_code, tipo_tramite, asunto, status, fecha_registro, fecha_actualizacion, observaciones FROM mesa_partes_solicitudes WHERE UPPER(expediente_code) = ?",
                (codigo_expediente.strip().upper(),)
            ).fetchone()
            if not row:
                return None
            return {
                "codigo_expediente": row["expediente_code"],
                "tipo_solicitud": row["tipo_tramite"],
                "asunto": row["asunto"],
                "status": row["status"],
                "created_at": row["fecha_registro"],
                "updated_at": row["fecha_actualizacion"],
                "respuesta_oficial": row["observaciones"]
            }

    @staticmethod
    def track_request_internal(codigo_expediente: str) -> Optional[Dict[str, Any]]:
        """Consulta interna con privilegios administrativos colegiados."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM mesa_partes_solicitudes WHERE UPPER(expediente_code) = ?",
                (codigo_expediente.strip().upper(),)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "codigo_expediente": row["expediente_code"],
                "solicitante_nombre": row["solicitante_name"],
                "solicitante_dni": row["solicitante_dni"],
                "solicitante_email": row["solicitante_email"],
                "solicitante_telefono": row["solicitante_phone"],
                "asunto": row["asunto"],
                "tipo_solicitud": row["tipo_tramite"],
                "status": row["status"],
                "created_at": row["fecha_registro"],
                "updated_at": row["fecha_actualizacion"],
                "respuesta_oficial": row["observaciones"]
            }

    # Mantener alias de retrocompatibilidad interna
    track_request = track_request_public

    @staticmethod
    def update_request_status(
        request_id: int,
        new_status: str,
        respuesta_oficial: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE mesa_partes_solicitudes
                SET status = ?, observaciones = ?, fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (new_status, respuesta_oficial, request_id)
            )
            return {"success": True, "message": "Estado y resolución de expediente actualizados."}

    @staticmethod
    def delete_request(request_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute("DELETE FROM mesa_partes_solicitudes WHERE id = ?", (request_id,))
            return {"success": True, "message": "Expediente archivado/eliminado correctamente."}


mesa_partes_service = MesaPartesService()
