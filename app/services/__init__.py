from app.services.dashboard_service import dashboard_service
from app.services.academic_service import academic_service
from app.services.attendance_service import attendance_service
from app.services.evaluation_service import evaluation_service
from app.services.assignment_service import assignment_service
from app.services.document_service import document_service
from app.services.mesa_partes_service import mesa_partes_service
from app.services.communication_service import communication_service
from app.services.audit_service import audit_service
from app.services.support_service import support_service

__all__ = [
    "dashboard_service",
    "academic_service",
    "attendance_service",
    "evaluation_service",
    "assignment_service",
    "document_service",
    "mesa_partes_service",
    "communication_service",
    "audit_service",
    "support_service"
]
