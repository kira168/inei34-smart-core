"""
INEI SMART-CORE - Audit Router
Forensic activity and traceability logs for Dirección / Administración.
"""

from fastapi import APIRouter, Depends
from app.auth.rbac import require_role
from app.services.audit_service import audit_service

router = APIRouter(prefix="/api/audit", tags=["Audit"])

@router.get("/logs")
def get_logs(limit: int = 100, user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))):
    return audit_service.get_logs(limit=limit)
