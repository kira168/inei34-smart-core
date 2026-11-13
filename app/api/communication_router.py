"""
INEI SMART-CORE - Communication Router
Institutional Announcements and User Notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from app.auth.rbac import get_current_user, require_role
from app.services.communication_service import communication_service

router = APIRouter(prefix="/api/communication", tags=["Communication"])

class AnnouncementCreateRequest(BaseModel):
    title: str
    content: str
    target_role: str = "TODOS"
    tag: Optional[str] = "General"

class AnnouncementUpdateRequest(BaseModel):
    title: str
    content: str
    target_role: str = "TODOS"
    tag: Optional[str] = None

@router.get("/announcements")
def get_announcements(target_role: Optional[str] = None, user: dict = Depends(get_current_user)):
    user_role = (user.get("role") or "").upper()
    is_staff = any(r in user_role for r in ["ADMIN", "DIRECT", "SECRE"])
    
    # Si se pide explícitamente una categoría que no sea TODOS
    if target_role and target_role.upper() != "TODOS":
        return communication_service.get_announcements(target_role.upper())
    
    # Personal administrativo y secretaría ven todos los comunicados por defecto
    if is_staff:
        return communication_service.get_announcements("TODOS")
    
    # Estudiantes, docentes y padres ven comunicados para TODOS + su rol específico
    return communication_service.get_announcements(user_role)

@router.post("/announcements")
def create_announcement(
    req: AnnouncementCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return communication_service.create_announcement(
        author_id=user["id"],
        title=req.title,
        content=req.content,
        target_role=req.target_role,
        tag=req.tag or "General"
    )

@router.put("/announcements/{announcement_id}")
def update_announcement(
    announcement_id: int,
    req: AnnouncementUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return communication_service.update_announcement(
        announcement_id=announcement_id,
        title=req.title,
        content=req.content,
        target_role=req.target_role,
        tag=req.tag
    )

@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return communication_service.delete_announcement(announcement_id)

@router.get("/notifications")
def get_notifications(user: dict = Depends(get_current_user)):
    return communication_service.get_user_notifications(user["id"])

@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: dict = Depends(get_current_user)):
    return communication_service.mark_notification_read(notification_id, user["id"])

@router.post("/notifications/read-all")
def mark_all_read(user: dict = Depends(get_current_user)):
    return communication_service.mark_all_notifications_read(user["id"])
