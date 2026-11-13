"""
INEI SMART-CORE v2.8 - Router Administrativo del Firewall Inteligente
Institución: I.E. Emblemática INEI N.º 34 de Chancay
Endpoints bajo /api/admin/firewall (Protegidos estrictamente para rol ADMINISTRADOR)
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.auth.rbac import require_role
from app.security.firewall_service import firewall_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/api/admin/firewall", tags=["Admin Firewall"])

# =============================================================================
# MODELOS DE ENTRADA
# =============================================================================
class ManualBlockRequest(BaseModel):
    ip_address: str = Field(..., min_length=3, max_length=50)
    reason: str = Field(..., min_length=3, max_length=255)
    duration_minutes: Optional[int] = Field(default=15, ge=1, le=525600)  # De 1 min hasta 1 año
    notes: Optional[str] = Field(default=None, max_length=500)

class UnblockRequest(BaseModel):
    ip_address: str = Field(..., min_length=3, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)

class ResetLoginAttemptsRequest(BaseModel):
    account_identifier: Optional[str] = Field(default=None, max_length=100)
    ip_address: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)

class UpdateSettingsRequest(BaseModel):
    settings: Dict[str, str]

# =============================================================================
# ENDPOINTS ADMINISTRATIVOS (SOLO ADMINISTRADOR)
# =============================================================================

@router.get("/status")
def get_firewall_status(
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Retorna el estado general, métricas y salud del Firewall."""
    status = firewall_service.get_status()
    return {
        "success": True,
        "data": status
    }

@router.get("/blocked-ips")
def get_blocked_ips(
    include_inactive: bool = Query(False, description="Incluir bloqueos históricos inactivos"),
    limit: int = Query(100, ge=1, le=1000),
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Lista las IPs con bloqueos activos o históricos."""
    ips = firewall_service.get_blocked_ips(include_inactive=include_inactive, limit=limit)
    return {
        "success": True,
        "total": len(ips),
        "data": ips
    }

@router.post("/block")
def block_ip_manually(
    payload: ManualBlockRequest,
    request: Request,
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Aplica un bloqueo manual a una dirección IP con motivo y duración."""
    norm_ip = firewall_service.normalize_ip(payload.ip_address)
    if not norm_ip:
        raise HTTPException(status_code=400, detail="Formato de dirección IP inválido (debe ser IPv4 o IPv6 válida)")

    admin_username = admin_user.get("username", "admin_user")
    result = firewall_service.ban_ip(
        ip_str=norm_ip,
        reason=payload.reason,
        duration_minutes=payload.duration_minutes,
        source="MANUAL_ADMIN",
        created_by=admin_username,
        notes=payload.notes
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "No se pudo bloquear la IP"))

    # Auditoría institucional
    audit_service.log(
        user_id=admin_user.get("id"),
        action="FIREWALL_IP_BLOCKED",
        entity_type="FIREWALL",
        entity_id=result.get("ban_id"),
        details=f"Bloqueo manual de IP {norm_ip}. Motivo: {payload.reason}. Duración: {payload.duration_minutes} min.",
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": f"IP {norm_ip} bloqueada exitosamente por {payload.duration_minutes} minutos",
        "data": result
    }

@router.post("/unblock")
def unblock_ip_manually(
    payload: UnblockRequest,
    request: Request,
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Desbloquea manualmente una dirección IP."""
    norm_ip = firewall_service.normalize_ip(payload.ip_address)
    if not norm_ip:
        raise HTTPException(status_code=400, detail="Formato de dirección IP inválido")

    admin_username = admin_user.get("username", "admin_user")
    result = firewall_service.unblock_ip(
        ip_str=norm_ip,
        unblocked_by=admin_username,
        notes=payload.notes
    )

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "No se encontró un bloqueo activo para esta IP"))

    audit_service.log(
        user_id=admin_user.get("id"),
        action="FIREWALL_IP_UNBLOCKED",
        entity_type="FIREWALL",
        entity_id=None,
        details=f"Desbloqueo manual de IP {norm_ip} por {admin_username}",
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": f"IP {norm_ip} desbloqueada exitosamente",
        "data": result
    }

@router.get("/events")
def get_firewall_events(
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = Query(None, description="Filtrar por tipo de evento"),
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Consulta el registro forense de eventos de seguridad."""
    events = firewall_service.get_events(limit=limit, event_type=event_type)
    return {
        "success": True,
        "total": len(events),
        "data": events
    }

@router.get("/settings")
def get_firewall_settings(
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Consulta las configuraciones y umbrales persistentes del Firewall."""
    settings = firewall_service.get_settings(force_refresh=True)
    return {
        "success": True,
        "data": settings
    }

@router.put("/settings")
def update_firewall_settings(
    payload: UpdateSettingsRequest,
    request: Request,
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Actualiza las políticas y límites de seguridad del Firewall."""
    admin_username = admin_user.get("username", "admin_user")
    result = firewall_service.update_settings(payload.settings, admin_user=admin_username)

    audit_service.log(
        user_id=admin_user.get("id"),
        action="FIREWALL_SETTINGS_UPDATED",
        entity_type="FIREWALL",
        entity_id=None,
        details=f"Parámetros del firewall actualizados: {', '.join(payload.settings.keys())}",
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": "Parámetros del firewall actualizados exitosamente",
        "data": result
    }

@router.post("/reset-login-attempts")
def reset_failed_login_attempts(
    payload: ResetLoginAttemptsRequest,
    request: Request,
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Restablece intentos fallidos acumulados y desbloquea el acceso para una cuenta o IP específica."""
    admin_username = admin_user.get("username", "admin_user")
    result = firewall_service.reset_login_attempts(
        account=payload.account_identifier,
        ip_address=payload.ip_address,
        admin_user=admin_username
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Error al restablecer intentos"))

    audit_service.log(
        user_id=admin_user.get("id"),
        action="FIREWALL_LOGIN_RESET",
        entity_type="FIREWALL",
        entity_id=None,
        details=f"Restablecimiento de intentos fallidos por {admin_username}: Cuenta={payload.account_identifier or 'Todas'}, IP={payload.ip_address or 'Todas'}",
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": result.get("message"),
        "data": result
    }

@router.post("/cleanup")
def trigger_retention_cleanup(
    request: Request,
    admin_user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Ejecuta de forma manual y controlada la depuración de registros vencidos según política de retención."""
    admin_username = admin_user.get("username", "admin_user")
    result = firewall_service.cleanup_old_records()

    audit_service.log(
        user_id=admin_user.get("id"),
        action="FIREWALL_RETENTION_CLEANUP",
        entity_type="FIREWALL",
        entity_id=None,
        details=f"Depuración de retención ejecutada por {admin_username}. Resultado: {json.dumps(result, ensure_ascii=False)}",
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": "Depuración de registros completada",
        "data": result
    }
