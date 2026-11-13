"""
INEI SMART-CORE - Backup Service
Mecanismo de Respaldo Oficial de Base de Datos SQLite mediante Connection.backup().
Garantiza copias consistentes no bloqueantes, verificación de integridad SHA-256 y trazabilidad forense.
"""

import os
import sqlite3
import hashlib
import time
import json
import re
import secrets
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.config import DATA_DIR
from app.database.connection import get_current_db_path
from app.services.audit_service import audit_service

BACKUPS_DIR = DATA_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

# Validación estricta de formato de identificador para prevenir Directory / Path Traversal
SAFE_BACKUP_ID_PATTERN = re.compile(r"^backup_\d{8}_\d{6}_[a-fA-F0-9]{8}$")

class BackupService:
    @staticmethod
    def get_backup_directory() -> Path:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        return BACKUPS_DIR

    @staticmethod
    def calculate_file_sha256(filepath: Path) -> str:
        """Calcula el hash SHA-256 en bloques de 64 KB."""
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest().upper()

    @staticmethod
    def generate_backup(admin_user: Dict[str, Any], client_ip: str = "127.0.0.1") -> Dict[str, Any]:
        """
        Genera una copia de seguridad consistente de SQLite usando Connection.backup().
        No interrumpe escrituras activas ni bloquea Uvicorn.
        """
        src_path = get_current_db_path()
        if not src_path.exists():
            raise FileNotFoundError(f"Base de datos origen no encontrada en: {src_path}")

        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        entropy_token = secrets.token_hex(4).upper()
        backup_id = f"backup_{timestamp_str}_{entropy_token}"
        backup_filename = f"inei34_{backup_id}.db"
        dest_path = BACKUPS_DIR / backup_filename
        meta_filename = f"inei34_{backup_id}.meta.json"
        meta_path = BACKUPS_DIR / meta_filename

        t_start = time.perf_counter()

        # 1. Ejecutar Backup Atómico mediante API nativa de SQLite
        source_conn = sqlite3.connect(str(src_path), timeout=30.0)
        dest_conn = sqlite3.connect(str(dest_path))

        try:
            with dest_conn:
                # Copia 100 páginas por paso para no saturar I/O
                source_conn.backup(dest_conn, pages=100)
            
            backup_duration_ms = (time.perf_counter() - t_start) * 1000

            # 2. Verificación de Integridad Inmediata sobre la conexión del respaldo
            cur = dest_conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity_result = cur.fetchone()[0]
            if integrity_result != "ok":
                raise RuntimeError(f"Falla crítica de integridad en el respaldo: {integrity_result}")

            # Extraer métricas de la base respaldada
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            tables_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM users")
            users_count = cur.fetchone()[0]

        finally:
            dest_conn.close()
            source_conn.close()

        # 3. Calcular Checksum SHA-256
        file_size = os.path.getsize(dest_path)
        sha256_hash = BackupService.calculate_file_sha256(dest_path)

        # 4. Guardar Metadatos del Respaldo
        meta_data = {
            "backup_id": backup_id,
            "filename": backup_filename,
            "created_at": now.isoformat(),
            "created_at_formatted": now.strftime("%d/%m/%Y %H:%M:%S"),
            "size_bytes": file_size,
            "size_formatted": f"{file_size / (1024 * 1024):.2f} MB",
            "sha256": sha256_hash,
            "integrity": integrity_result,
            "tables_count": tables_count,
            "users_count": users_count,
            "duration_ms": round(backup_duration_ms, 2),
            "created_by_user_id": admin_user.get("id"),
            "created_by_username": admin_user.get("username", "administrador")
        }

        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta_data, mf, indent=2, ensure_ascii=False)

        # 5. Registro Mandatorio en Auditoría Forense
        audit_service.log(
            user_id=admin_user.get("id", 1),
            action="BACKUP_GENERATED",
            entity_type="DATABASE",
            entity_id=None,
            details=f"Respaldo generado exitosamente ({meta_data['size_formatted']}, SHA-256:{sha256_hash[:16]}..., Tiempo:{meta_data['duration_ms']}ms)",
            ip_address=client_ip
        )

        return meta_data

    @staticmethod
    def list_backups() -> List[Dict[str, Any]]:
        """Lista todos los respaldos institucionales generados."""
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        results = []
        meta_files = sorted(BACKUPS_DIR.glob("inei34_backup_*.meta.json"), reverse=True)

        for mf in meta_files:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Verificar que el archivo .db todavía exista
                    db_file = BACKUPS_DIR / data.get("filename", "")
                    if db_file.exists():
                        results.append(data)
            except Exception:
                continue

        return results

    @staticmethod
    def get_backup_file_for_download(backup_id: str, admin_user: Dict[str, Any], client_ip: str = "127.0.0.1") -> Tuple[Path, str, str]:
        """
        Valida y entrega la ruta física segura del archivo de respaldo para su descarga.
        Previene vulnerabilidades de Path Traversal de forma estricta.
        """
        # 1. Validar sintaxis del backup_id
        if not SAFE_BACKUP_ID_PATTERN.match(backup_id):
            raise ValueError("Identificador de respaldo inválido o malformado.")

        expected_filename = f"inei34_{backup_id}.db"
        target_path = (BACKUPS_DIR / expected_filename).resolve()

        # 2. Verificación de seguridad de ruta (dentro de BACKUPS_DIR)
        if not str(target_path).startswith(str(BACKUPS_DIR.resolve())):
            raise PermissionError("Acceso a ruta de archivo no autorizado (Path Traversal detectado).")

        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"El respaldo solicitado '{backup_id}' no existe en el almacenamiento.")

        # 3. Leer o recalcular SHA-256
        sha256_hash = BackupService.calculate_file_sha256(target_path)

        # 4. Registrar la descarga en Auditoría Forense
        audit_service.log(
            user_id=admin_user.get("id", 1),
            action="BACKUP_DOWNLOADED",
            entity_type="DATABASE",
            entity_id=None,
            details=f"Descarga de base de datos autorizada: {expected_filename} (SHA-256:{sha256_hash[:16]}...)",
            ip_address=client_ip
        )

        return target_path, expected_filename, sha256_hash

    @staticmethod
    def verify_restore_in_sandbox(backup_id: str) -> Dict[str, Any]:
        """
        Ejecuta una prueba completa de restauración en un entorno aislado en memoria (:memory:).
        Comprueba integridad, conteo de tablas y mide el tiempo exacto de restauración sin tocar producción.
        """
        if not SAFE_BACKUP_ID_PATTERN.match(backup_id):
            raise ValueError("Identificador de respaldo inválido.")

        target_path = (BACKUPS_DIR / f"inei34_{backup_id}.db").resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"Archivo de respaldo no encontrado: {target_path}")

        t_start = time.perf_counter()

        backup_conn = sqlite3.connect(str(target_path))
        sandbox_conn = sqlite3.connect(":memory:")

        try:
            with sandbox_conn:
                backup_conn.backup(sandbox_conn)

            restore_duration_ms = (time.perf_counter() - t_start) * 1000

            cur = sandbox_conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            tables = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM users")
            users = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM audit_logs")
            audit_records = cur.fetchone()[0]

            return {
                "success": (integrity == "ok"),
                "integrity": integrity,
                "tables_count": tables,
                "users_count": users,
                "audit_logs_count": audit_records,
                "restore_duration_ms": round(restore_duration_ms, 2),
                "verified_at": datetime.now().isoformat()
            }
        finally:
            sandbox_conn.close()
            backup_conn.close()

backup_service = BackupService()
