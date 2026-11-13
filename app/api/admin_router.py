"""
INEI SMART-CORE - Admin Router
Endpoints de Administración Institucional: Respaldos de Base de Datos y Verificación de Integridad.
Acceso estrictamente restringido al rol ADMINISTRADOR.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from typing import Dict, Any, List

from app.auth.rbac import require_role
from app.services.backup_service import backup_service

router = APIRouter(prefix="/api/admin", tags=["Administración"])

def get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente considerando proxies institucionales."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


@router.get("/backups", response_model=List[Dict[str, Any]])
def list_backups(
    user: Dict[str, Any] = Depends(require_role(["ADMINISTRADOR"]))
):
    """Lista todos los respaldos generados disponibles en el servidor."""
    try:
        return backup_service.list_backups()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error consultando respaldos: {str(e)}"
        )


@router.post("/backups/generate")
def generate_backup(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Genera un nuevo respaldo atómico de la base de datos mediante sqlite3.Connection.backup().
    Verifica integridad de inmediato y calcula el hash SHA-256.
    """
    client_ip = get_client_ip(request)
    try:
        meta = backup_service.generate_backup(admin_user=user, client_ip=client_ip)
        return {
            "success": True,
            "message": "Copia de seguridad generada y verificada exitosamente.",
            "backup": meta
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la generación del respaldo: {str(e)}"
        )


@router.get("/backups/{backup_id}/download")
def download_backup(
    backup_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Descarga el archivo físico .db del respaldo previa verificación estricta de seguridad.
    Previene Path Traversal y registra el evento en auditoría forense.
    """
    client_ip = get_client_ip(request)
    try:
        file_path, filename, sha256_hash = backup_service.get_backup_file_for_download(
            backup_id=backup_id,
            admin_user=user,
            client_ip=client_ip
        )
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/x-sqlite3",
            headers={
                "X-Checksum-SHA256": sha256_hash,
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except (FileNotFoundError, PermissionError) as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error preparando descarga: {str(e)}"
        )


@router.post("/backups/{backup_id}/verify-restore")
def verify_restore(
    backup_id: str,
    user: Dict[str, Any] = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Ejecuta una prueba de restauración simulada en una base SQLite en memoria aislada (:memory:).
    No toca la base de datos de producción y reporta integridad y métricas exactas.
    """
    try:
        result = backup_service.verify_restore_in_sandbox(backup_id=backup_id)
        return {
            "success": True,
            "message": "Prueba de restauración en sandbox completada satisfactoriamente.",
            "result": result
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante prueba de restauración: {str(e)}"
        )
