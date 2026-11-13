"""
INEI SMART-CORE 2.0 - Router de Soporte Técnico y Mesa de Ayuda TI
Endpoints para gestión de tickets institucionales, atención del administrador y chat de soporte.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.auth.rbac import get_current_user, require_role, normalize_role
from app.services.support_service import support_service
from app.services.audit_service import audit_service
from app.services.communication_service import communication_service

router = APIRouter(prefix="/api/support", tags=["Soporte & Mesa de Ayuda"])

class TicketCreateRequest(BaseModel):
    subject: str
    priority: Optional[str] = "MEDIA"
    area: Optional[str] = "General"
    description: str

class TicketReplyRequest(BaseModel):
    status: str
    solution: Optional[str] = None
    admin_response_by: Optional[str] = None

class ChatMessageRequest(BaseModel):
    text: str
    target_user_id: Optional[int] = None
    is_quick_prompt: Optional[bool] = False

@router.get("/stats")
def get_support_stats(user: dict = Depends(get_current_user)):
    """Retorna métricas de la mesa de soporte."""
    return support_service.get_stats()

@router.get("/tickets")
def list_tickets(
    status: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Lista tickets. El ADMINISTRADOR puede ver todos los tickets.
    Los demás roles (Docente, Secretaría, Director, Estudiante, Padre) ven solo sus propios tickets.
    """
    user_role = normalize_role(user.get("role_name") or user.get("role", ""))
    is_admin = (user_role == "ADMINISTRADOR")
    
    filter_user_id = None if is_admin else user.get("id")
    tickets = support_service.list_tickets(
        user_id=filter_user_id,
        role=role,
        status=status,
        search=search
    )
    return {
        "success": True,
        "is_admin": is_admin,
        "total": len(tickets),
        "tickets": tickets
    }

@router.get("/tickets/{ticket_id}")
def get_ticket_detail(ticket_id: int, user: dict = Depends(get_current_user)):
    """Obtiene los detalles de un ticket específico."""
    ticket = support_service.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    user_role = normalize_role(user.get("role_name") or user.get("role", ""))
    if user_role != "ADMINISTRADOR" and ticket["user_id"] != user.get("id"):
        raise HTTPException(status_code=403, detail="No tiene permisos para ver este ticket")
    
    return ticket

@router.post("/tickets")
def create_ticket(req: TicketCreateRequest, user: dict = Depends(get_current_user)):
    """Crea un nuevo ticket de soporte con la sesión real del usuario."""
    user_role = normalize_role(user.get("role_name") or user.get("role", ""))
    user_name = user.get("full_name") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("username", "Usuario")
    user_email = user.get("email")
    user_dni = user.get("dni") or user.get("username")

    ticket = support_service.create_ticket(
        user_id=user["id"],
        user_name=user_name,
        user_role=user_role,
        user_email=user_email,
        user_dni=user_dni,
        subject=req.subject.strip(),
        priority=req.priority.strip() if req.priority else "MEDIA",
        area=req.area.strip() if req.area else "General",
        description=req.description.strip()
    )

    audit_service.log(
        user_id=user["id"],
        action="CREATE_SUPPORT_TICKET",
        entity_type="support_tickets",
        entity_id=ticket["id"],
        details=f"Ticket {ticket['ticket_code']} creado por {user_name} ({user_role}): {req.subject}"
    )

    # Notificar a los administradores en tiempo real
    communication_service.create_notification_for_role(
        role="ADMINISTRADOR",
        title=f"🚨 Nuevo Ticket: {ticket['ticket_code']}",
        message=f"{user_name} ({user_role}) reportó: {req.subject} [{ticket['priority']}]",
        type="warning",
        link="admin_help"
    )

    return {
        "success": True,
        "message": f"¡Ticket {ticket['ticket_code']} generado y enviado al Administrador!",
        "ticket": ticket
    }

@router.patch("/tickets/{ticket_id}/reply")
@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(
    ticket_id: int, 
    req: TicketReplyRequest, 
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """El Administrador responde a un ticket, ingresa solución y actualiza estado."""
    ticket = support_service.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    admin_name = req.admin_response_by or user.get("full_name") or "Administrador TI"
    updated = support_service.update_ticket(
        ticket_id=ticket_id,
        status=req.status,
        solution=req.solution,
        admin_response_by=admin_name
    )

    audit_service.log(
        user_id=user["id"],
        action="UPDATE_SUPPORT_TICKET",
        entity_type="support_tickets",
        entity_id=ticket_id,
        details=f"Ticket {ticket['ticket_code']} actualizado a estado '{req.status}' por {admin_name}. Solución: {req.solution or 'N/A'}"
    )

    # Notificar al usuario solicitante
    link_target = "sec_help" if ticket.get("user_role") == "SECRETARÍA" else ("director_help" if ticket.get("user_role") == "DIRECTOR" else "doc_help")
    communication_service.create_notification(
        user_id=ticket["user_id"],
        title=f"✔ Incidencia {ticket['ticket_code']} Resuelta",
        message=f"{admin_name} atendió tu solicitud: {req.solution or 'Incidencia solucionada'}",
        type="success",
        link=link_target
    )

    return {
        "success": True,
        "message": f"Ticket {ticket['ticket_code']} actualizado con éxito a '{req.status}'",
        "ticket": updated
    }

@router.get("/chat")
def get_chat(
    target_user_id: Optional[int] = None, 
    user: dict = Depends(get_current_user)
):
    """
    Obtiene los mensajes de chat.
    Si es Administrador y no pasa target_user_id, retorna también la lista de hilos de conversación.
    """
    user_role = normalize_role(user.get("role_name") or user.get("role", ""))
    is_admin = (user_role == "ADMINISTRADOR")

    if is_admin:
        threads = support_service.list_chat_threads()
        active_user_id = target_user_id or (threads[0]["user_id"] if threads else None)
        messages = support_service.get_chat_messages(user_id=active_user_id) if active_user_id else []
        return {
            "is_admin": True,
            "threads": threads,
            "active_user_id": active_user_id,
            "messages": messages
        }
    else:
        messages = support_service.get_chat_messages(user_id=user["id"])
        # Si no hay mensajes para este usuario, inicializar con bienvenida automática
        if not messages:
            user_name = user.get("full_name") or user.get("first_name", "Usuario")
            welcome = support_service.add_chat_message(
                user_id=user["id"],
                user_name=user_name,
                user_role=user_role,
                sender="bot",
                text=f"👋 ¡Hola {user_name}! Soy el **Asistente de Soporte Técnico Smart-Core** de la I.E. INEI N° 34 Chancay.\n¿En qué te puedo ayudar hoy? Escribe tu consulta abajo o crea un ticket formal con el botón superior para atención directa del Administrador."
            )
            messages = [welcome]
        return {
            "is_admin": False,
            "messages": messages
        }

@router.post("/chat")
def send_chat_message(req: ChatMessageRequest, user: dict = Depends(get_current_user)):
    """Envía un mensaje de chat de soporte bidireccional limpio entre usuario y administrador."""
    user_role = normalize_role(user.get("role_name") or user.get("role", ""))
    is_admin = (user_role == "ADMINISTRADOR")
    user_name = user.get("full_name") or user.get("first_name", "Usuario")
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    if is_admin:
        # Administrador respondiendo a un usuario específico
        if not req.target_user_id:
            raise HTTPException(status_code=400, detail="Debe indicar el usuario de destino")
        
        # Obtener datos canónicos del usuario de destino
        target_messages = support_service.get_chat_messages(user_id=req.target_user_id)
        target_name = target_messages[0]["user_name"] if target_messages else "Usuario"
        target_role = target_messages[0]["user_role"] if target_messages else "DOCENTE"

        msg = support_service.add_chat_message(
            user_id=req.target_user_id,
            user_name=target_name,
            user_role=target_role,
            sender="admin",
            text=text
        )

        target_role_upper = (target_role or "").upper()
        if "DIRECTOR" in target_role_upper:
            target_link = "director_help"
        elif "SEC" in target_role_upper:
            target_link = "sec_help"
        elif "DOC" in target_role_upper:
            target_link = "doc_help"
        else:
            target_link = "admin_help"

        communication_service.create_notification(
            user_id=req.target_user_id,
            title="💬 Mensaje de Soporte TI",
            message=f"El Administrador TI te respondió: {text[:65]}...",
            type="chat",
            link=target_link
        )

        return {"success": True, "message": msg}
    else:
        # Usuario normal (Docente, Secretaría, Director, etc.) enviando mensaje al Administrador
        msg = support_service.add_chat_message(
            user_id=user["id"],
            user_name=user_name,
            user_role=user_role,
            sender="user",
            text=text
        )

        communication_service.create_notification_for_role(
            role="ADMINISTRADOR",
            title=f"💬 Chat de {user_name} ({user_role})",
            message=f"Consulta: {text[:65]}...",
            type="chat",
            link="admin_help"
        )

        # Solo si el usuario ejecutó explícitamente un chip de ayuda rápida FAQ
        bot_msg = None
        if req.is_quick_prompt:
            lower = text.lower()
            bot_reply = None
            if any(k in lower for k in ['contraseña', 'clave', 'login', 'entrar', 'acceso', 'usuario']):
                bot_reply = (
                    "🔑 **Guía Rápida - Contraseñas:**\n\n"
                    "• La clave institucional provisional de contingencia es el DNI del usuario o `123456`.\n"
                    "• Si requieres reseteo formal por parte del Administrador, también puedes registrar un ticket presionando **'+ Crear Ticket de Soporte'**."
                )
            elif any(k in lower for k in ['archivo', 'subir', 'tarea', 'dwg', 'pdf', 'tamaño']):
                bot_reply = (
                    "📁 **Guía Rápida - Archivos & Planos:**\n\n"
                    "• Formatos soportados: PDF, Word (.docx), Excel (.xlsx), AutoCAD (.dwg), imágenes (.png, .jpg).\n"
                    "• Límite: 25 MB por archivo."
                )
            elif any(k in lower for k in ['máquina', 'maquina', 'taller', 'torno', 'fresadora', 'pc', 'falla', 'avería']):
                bot_reply = (
                    "⚙️ **Guía Rápida - Taller y Maquinaria:**\n\n"
                    "• Por norma de seguridad 5S, corte la llave térmica del equipo y use EPP integral."
                )

            if bot_reply:
                bot_msg = support_service.add_chat_message(
                    user_id=user["id"],
                    user_name=user_name,
                    user_role=user_role,
                    sender="bot",
                    text=bot_reply
                )

        return {
            "success": True, 
            "message": msg,
            "bot_reply": bot_msg
        }


@router.delete("/chat")
def delete_chat_history(
    target_user_id: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    """Elimina el historial del chat actual para iniciar una nueva conversación."""
    user_role = normalize_role(user.get("role_name") or user.get("role", ""))
    is_admin = (user_role == "ADMINISTRADOR")
    
    uid_to_clear = (target_user_id if is_admin and target_user_id else user["id"])
    support_service.clear_chat_messages(uid_to_clear)
    return {"success": True, "message": "Historial de chat eliminado exitosamente"}
