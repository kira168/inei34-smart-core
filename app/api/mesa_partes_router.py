"""
INEI SMART-CORE - Mesa de Partes Virtual Router
Public submission & tracking, plus internal management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from typing import Optional, List
from app.auth.rbac import get_current_user, require_role
from app.services.mesa_partes_service import mesa_partes_service
from app.config import TRUSTED_PROXIES, MESA_PARTES_RATE_LIMIT, MESA_PARTES_RATE_WINDOW_SECONDS

router = APIRouter(prefix="/api/mesa-partes", tags=["Mesa de Partes"])

def get_client_ip(request: Request) -> str:
    """
    Obtiene la dirección IP real del cliente de forma segura.
    Solo confía en X-Forwarded-For si la conexión directa proviene de un proxy confiable.
    """
    direct_ip = request.client.host if request.client else "127.0.0.1"
    
    if direct_ip in TRUSTED_PROXIES:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # La IP original del cliente es la primera en la cadena X-Forwarded-For
            proxies = [p.strip() for p in forwarded_for.split(",") if p.strip()]
            if proxies:
                return proxies[0]
    return direct_ip

class PublicRequestCreate(BaseModel):
    solicitante_nombre: str
    solicitante_dni: str
    solicitante_email: str
    solicitante_telefono: str
    asunto: str
    tipo_solicitud: str
    descripcion: str
    archivo_adjunto: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    request_id: int
    status: str
    respuesta_oficial: Optional[str] = None

# Public endpoint: Citizen registers request with rate limiting
@router.post("/public-submit")
def public_submit_request(req: PublicRequestCreate, request: Request, response: Response):
    client_ip = get_client_ip(request)
    allowed, current_count, retry_after = mesa_partes_service.check_and_record_rate_limit(
        ip_address=client_ip,
        limit=MESA_PARTES_RATE_LIMIT,
        window_seconds=MESA_PARTES_RATE_WINDOW_SECONDS
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Límite de solicitudes excedido ({MESA_PARTES_RATE_LIMIT} trámites por hora). Por favor, espere {retry_after} segundos antes de intentar nuevamente.",
            headers={"Retry-After": str(retry_after)}
        )

    return mesa_partes_service.create_request(
        solicitante_nombre=req.solicitante_nombre,
        solicitante_dni=req.solicitante_dni,
        solicitante_email=req.solicitante_email,
        solicitante_telefono=req.solicitante_telefono,
        asunto=req.asunto,
        tipo_solicitud=req.tipo_solicitud,
        descripcion=req.descripcion,
        archivo_adjunto=req.archivo_adjunto
    )

# Public endpoint: Citizen tracks expedientes (sanitized response)
@router.get("/track/{codigo_expediente}")
def track_expediente(codigo_expediente: str):
    record = mesa_partes_service.track_request_public(codigo_expediente)
    if not record:
        raise HTTPException(status_code=404, detail="Expediente no encontrado. Verifique el código ingresado.")
    return record

# Internal endpoint: List all requests
@router.get("/requests")
def get_internal_requests(
    status: Optional[str] = None,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return mesa_partes_service.get_requests(status_filter=status)

# Internal endpoint: Update status & official reply
@router.post("/update-status")
def update_status(
    req: StatusUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return mesa_partes_service.update_request_status(
        request_id=req.request_id,
        new_status=req.status,
        respuesta_oficial=req.respuesta_oficial
    )

# Internal endpoint: Delete/archive request
@router.delete("/requests/{request_id}")
def delete_request(
    request_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return mesa_partes_service.delete_request(request_id)
