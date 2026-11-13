from app.api.auth_router import router as auth_router
from app.api.dashboard_router import router as dashboard_router
from app.api.academic_router import router as academic_router
from app.api.attendance_router import router as attendance_router
from app.api.evaluation_router import router as evaluation_router
from app.api.assignment_router import router as assignment_router
from app.api.document_router import router as document_router
from app.api.mesa_partes_router import router as mesa_partes_router
from app.api.communication_router import router as communication_router
from app.api.audit_router import router as audit_router
from app.api.admin_router import router as admin_router
from app.api.ai_router import router as ai_router
from app.api.support_router import router as support_router
from app.api.firewall_router import router as firewall_router
from app.api.whatsapp_router import router as whatsapp_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "academic_router",
    "attendance_router",
    "evaluation_router",
    "assignment_router",
    "document_router",
    "mesa_partes_router",
    "communication_router",
    "audit_router",
    "admin_router",
    "ai_router",
    "support_router",
    "firewall_router",
    "whatsapp_router"
]
