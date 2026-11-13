"""
INEI SMART-CORE - Dashboard Router
Returns specialized analytics based on the active role.
"""

from fastapi import APIRouter, Depends
from app.auth.rbac import get_current_user
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary(user: dict = Depends(get_current_user)):
    return dashboard_service.get_dashboard_data(user)
