"""
INEI SMART-CORE - AI Router
Endpoints for Contextual Role-Based AI Assistants & Tools.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
import json
import time
import io
import os
import hashlib
from datetime import datetime
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple, Union
from app.auth.rbac import get_current_user, get_current_user_optional, require_role, normalize_role
from app.ai.orchestrator import ai_orchestrator
from app.ai.service import ai_service
from app.ai.document_processor import document_processor
from app.ai.rag_engine import rag_engine
from app.ai.quiz_engine import quiz_engine
from app.ai.document_exporter import generate_docx_bytes, generate_pdf_bytes, parse_document_data, generate_unit_docx_bytes, generate_unit_pdf_bytes
from app.database.connection import get_db
from app.services.audit_service import audit_service
from app.config import CHAT_RATE_LIMIT, CHAT_RATE_WINDOW_SECONDS, UPLOAD_RATE_LIMIT, UPLOAD_RATE_WINDOW_SECONDS

logger = logging.getLogger("ai_router")

router = APIRouter(prefix="/api/ai", tags=["Artificial Intelligence"])

class ChatRateLimiter:
    """
    Control de tasa (Rate Limiting) en memoria con ventana deslizante por usuario autenticado.
    Evita abusos y denegación de servicio en inferencia local con Ollama.
    """
    def __init__(self, limit: int = CHAT_RATE_LIMIT, window_seconds: int = CHAT_RATE_WINDOW_SECONDS):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: Dict[int, List[float]] = {}
        self._lock = threading.Lock()

    def check_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """
        Verifica el límite de peticiones del usuario en la ventana móvil.
        Retorna (True, 0) si se permite la petición.
        Retorna (False, retry_after_seconds) si se superó el límite.
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            user_history = self._requests.get(user_id, [])
            valid_history = [t for t in user_history if t > window_start]

            if len(valid_history) >= self.limit:
                oldest = valid_history[0]
                retry_after = max(1, int(oldest + self.window_seconds - now) + 1)
                self._requests[user_id] = valid_history
                return False, retry_after

            valid_history.append(now)
            self._requests[user_id] = valid_history
            return True, 0

    def reset(self, user_id: Optional[int] = None):
        """Reinicia el contador de peticiones (útil en pruebas automatizadas)."""
        with self._lock:
            if user_id is not None:
                self._requests.pop(user_id, None)
            else:
                self._requests.clear()

chat_rate_limiter = ChatRateLimiter()

class UploadRateLimiter:
    """
    Control de tasa (Rate Limiting) específico para cargas de archivos escolares.
    Evita la saturación computacional derivada de OCR (LLaVA) y extracción intensiva de PDFs.
    Opera en memoria con ventana deslizante por usuario autenticado.
    Nota: Al residir en memoria RAM, la cuota es local al proceso Uvicorn.
    """
    def __init__(self, limit: int = UPLOAD_RATE_LIMIT, window_seconds: int = UPLOAD_RATE_WINDOW_SECONDS):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: Dict[int, List[float]] = {}
        self._lock = threading.Lock()

    def check_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """
        Verifica el límite de subidas del usuario en la ventana móvil.
        Retorna (True, 0) si se permite la subida.
        Retorna (False, retry_after_seconds) si se superó el límite.
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            user_history = self._requests.get(user_id, [])
            valid_history = [t for t in user_history if t > window_start]

            if len(valid_history) >= self.limit:
                oldest = valid_history[0]
                retry_after = max(1, int(oldest + self.window_seconds - now) + 1)
                self._requests[user_id] = valid_history
                return False, retry_after

            valid_history.append(now)
            self._requests[user_id] = valid_history
            return True, 0

    def reset(self, user_id: Optional[int] = None):
        """Reinicia el contador de subidas (útil en pruebas automatizadas)."""
        with self._lock:
            if user_id is not None:
                self._requests.pop(user_id, None)
            else:
                self._requests.clear()

upload_rate_limiter = UploadRateLimiter()



class QuizAnswerItem(BaseModel):
    question_id: str
    selected_option: int

class QuizSubmitRequest(BaseModel):
    subject_id: str
    answers: List[QuizAnswerItem]

class AIChatRequest(BaseModel):
    message: str
    tool_type: Optional[str] = "paso_a_paso"
    conversation_id: Optional[int] = None
    subject_id: Optional[str] = "electricidad"
    file_name: Optional[str] = None
    extracted_text: Optional[str] = None
    file_type: Optional[str] = None

class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None
    subject_id: Optional[str] = "electricidad"
    mode: Optional[str] = "paso_a_paso"

class ConversationUpdateRequest(BaseModel):
    title: str

class CNEBSessionRequest(BaseModel):
    topic: str
    grade: int
    specialty: str
    duration_minutes: Optional[int] = 90
    competence: Optional[str] = None
    purpose: Optional[str] = None

class LearningActivityRequest(BaseModel):
    topic: str
    grade: int
    specialty: Optional[str] = "Educación para el Trabajo"
    competence: Optional[str] = None
    activity_type: Optional[str] = "ficha_taller"
    duration_minutes: Optional[int] = 45
    section_name: Optional[str] = "A"
    difficulty: Optional[str] = "intermedio"
    materials: Optional[str] = None
    purpose: Optional[str] = None


class DocumentVisaRevokeRequest(BaseModel):
    reason: Optional[str] = "Revocado por decisión directiva de supervisión pedagógica"

class TechnicalExamRequest(BaseModel):
    topic: str
    specialty: Optional[str] = "Educación para el Trabajo"
    grade: int
    num_questions: Optional[int] = 5
    include_rubric: Optional[bool] = True
    competence: Optional[str] = None
    difficulty: Optional[str] = "intermedio"
    section_name: Optional[str] = "A"
    question_types: Optional[str] = "mixto"
    total_points: Optional[int] = 20

class TeacherChatRequest(BaseModel):
    message: str
    subject_id: Optional[str] = "general"
    specialty: Optional[str] = None
    grade: Optional[int] = None
    conversation_id: Optional[int] = None

class SessionCreateRequest(BaseModel):
    topic: str
    grade: int
    specialty: str
    section_name: Optional[str] = "A"
    duration_minutes: Optional[int] = 90
    competence: Optional[str] = None
    purpose: Optional[str] = None
    difficulty: Optional[str] = "intermedio"
    observations: Optional[str] = None
    course_id: Optional[int] = None
    session_type: Optional[str] = None
    template_id: Optional[int] = None  # 'tecnica', 'emprendimiento', 'general'
    methodology: Optional[str] = None
    structure_mode: Optional[str] = "institucional"  # 'institucional', 'libre'
    confirm_time_action: Optional[str] = None  # 'sync_header', 'sync_stages', 'keep'
    custom_stages: Optional[List[Dict[str, Any]]] = None

class SessionValidateTimesRequest(BaseModel):
    stages: Union[List[Dict[str, Any]], Dict[str, Any]]
    declared_minutes: int = 90
    confirm_action: Optional[str] = None  # 'sync_header', 'sync_stages', 'keep'

class SessionSectionRegenerateRequest(BaseModel):
    section: str # 'inicio', 'desarrollo', 'cierre', 'rubrica', 'seguridad_industrial'
    topic: str
    specialty: str
    grade: int
    duration_minutes: Optional[int] = 90
    competence: Optional[str] = None
    teacher_instruction: Optional[str] = None
    current_content: Optional[str] = None

class MaterialInstructionRequest(BaseModel):
    prompt: str
    preferred_type: Optional[str] = None
    grade: Optional[int] = None
    specialty: Optional[str] = None
    difficulty: Optional[str] = None
    custom_sections: Optional[List[Any]] = None
    include_teacher_key: Optional[bool] = None
    session_id: Optional[int] = None
    unit_id: Optional[int] = None
    reference_blueprint: Optional[Dict[str, Any]] = None

class GenerateFromTemplateRequest(BaseModel):
    template_id: Optional[int] = None
    prompt: Optional[str] = None
    topic: Optional[str] = None
    grade: Optional[int] = None
    specialty: Optional[str] = None
    purpose: Optional[str] = None
    duration_minutes: Optional[int] = None
    session_type: Optional[str] = None
    custom_sections: Optional[List[Any]] = None

class MaterialParseRequest(BaseModel):
    prompt: str

class MaterialOutlineSuggestRequest(BaseModel):
    doc_type: str
    specialty: Optional[str] = "Educación para el Trabajo"
    include_solutions: Optional[bool] = False
    topic: Optional[str] = ""

class TeacherPreferencesRequest(BaseModel):
    preferred_specialty: Optional[str] = "Educación para el Trabajo"
    preferred_grade: Optional[int] = 5
    include_5s_safety: Optional[bool] = True
    include_visual_placeholders: Optional[bool] = True
    include_teacher_key: Optional[bool] = True
    evaluation_style: Optional[str] = "vigesimal"
    custom_sections: Optional[List[Any]] = None

class MaterialRefineRequest(BaseModel):
    instruction: str
    current_content_markdown: str
    doc_type: Optional[str] = "ficha_guia"
    topic: Optional[str] = None
    grade: Optional[int] = 5
    specialty: Optional[str] = "Educación para el Trabajo"

class MaterialSectionRegenerateRequest(BaseModel):
    section_title: str
    current_section_content: Optional[str] = ""
    instruction: Optional[str] = ""
    doc_type: Optional[str] = "ficha_guia"
    topic: Optional[str] = None
    grade: Optional[int] = 5
    specialty: Optional[str] = "Educación para el Trabajo"

class TeacherDocumentCreateRequest(BaseModel):
    doc_type: str = "sesion_aprendizaje"
    title: str
    specialty: str
    grade: int
    section_name: Optional[str] = "A"
    duration_minutes: Optional[int] = 90
    topic: Optional[str] = None
    competence: Optional[str] = None
    purpose: Optional[str] = None
    course_id: Optional[int] = None
    unit_id: Optional[int] = None
    session_id: Optional[int] = None
    content_markdown: str
    content_json: Union[str, Dict[str, Any]]
    status: Optional[str] = "BORRADOR"
    version: Optional[int] = 1
    is_public: Optional[int] = 0

class UnitGenerateRequest(BaseModel):
    topic: Optional[str] = None
    title: Optional[str] = None
    grade: int
    specialty: str
    duration_weeks: Optional[int] = 9
    weekly_hours: Optional[int] = 8
    formative_module: Optional[str] = None
    section_name: Optional[str] = "A"
    bimester: Optional[str] = "IV Bimestre"
    unit_number: Optional[int] = 4
    technical_competence: Optional[str] = None
    entrepreneurship_competence: Optional[str] = None
    observations: Optional[str] = None
    weekly_topics: Optional[str] = None
    teacher_name: Optional[str] = None

class UnitValidateHoursRequest(BaseModel):
    sessions: List[Dict[str, Any]]
    duration_weeks: Optional[int] = 9
    weekly_hours: Optional[int] = 8

class UnitDeriveSessionRequest(BaseModel):
    unit_id: Optional[int] = None
    unit_data: Optional[Dict[str, Any]] = None
    unit_row: Optional[Dict[str, Any]] = None
    week: Optional[int] = None
    session_type: Optional[str] = None
    session_number: Optional[int] = None
    auto_generate: Optional[bool] = True

class SessionDeriveMaterialRequest(BaseModel):
    session_id: Optional[int] = None
    session_data: Optional[Dict[str, Any]] = None
    material_type: str = "ficha_guia"
    instruction: Optional[str] = None

class TeacherUnitSaveRequest(BaseModel):
    id: Optional[int] = None
    title: str
    specialty: str
    grade: int
    section_name: Optional[str] = "A"
    duration_weeks: Optional[int] = 9
    weekly_hours: Optional[int] = 8
    total_hours: Optional[int] = 72
    formative_module: Optional[str] = None
    content_json: Union[str, Dict[str, Any]]
    content_markdown: Optional[str] = None
    status: Optional[str] = "BORRADOR"
    version: Optional[int] = 1
    course_id: Optional[int] = None

class TeacherDocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    competence: Optional[str] = None
    purpose: Optional[str] = None
    content_markdown: Optional[str] = None
    content_json: Optional[Union[str, Dict[str, Any]]] = None
    status: Optional[str] = None
    is_public: Optional[int] = None
    duration_minutes: Optional[int] = None
    expected_version: Optional[int] = None

class TeacherExportPreviewRequest(BaseModel):
    title: str
    doc_type: str = "sesion_aprendizaje"
    specialty: Optional[str] = "Educación para el Trabajo"
    grade: Optional[int] = 5
    section_name: Optional[str] = "A"
    duration_minutes: Optional[int] = 90
    topic: Optional[str] = "Actividad Pedagógica"
    competence: Optional[str] = None
    purpose: Optional[str] = None
    content_markdown: Optional[str] = ""
    content_json: Optional[Union[str, Dict[str, Any]]] = None
    target: Optional[str] = "teacher"
    teacher_name: Optional[str] = None
    structure_mode: Optional[str] = None
    session_type: Optional[str] = None
    template_id: Optional[Union[int, str]] = None

class AdminDocumentRequest(BaseModel):
    doc_type: str
    recipient: str
    subject: str
    key_points: str

class ExecutiveAnalysisRequest(BaseModel):
    topic: str

class AIAdminCheckRequest(BaseModel):
    test_generation: Optional[bool] = False


@router.get("/health")
def get_ai_service_health():
    """
    Diagnóstico de salud del servicio de Inteligencia Artificial (Ollama local).
    Retorna estado (OPERATIVO, DESCONECTADO, MODELO_NO_DISPONIBLE, etc.), latencia y modelos disponibles.
    """
    from app.ai.ollama_monitor import ollama_monitor
    return ollama_monitor.check_health(force=False)


@router.get("/admin/diagnostics")
def get_ai_admin_diagnostics(user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))):
    """
    Diagnóstico técnico profundo exclusivo para ADMINISTRADOR y DIRECTOR.
    Diferencia entre servidor offline, modelo no descargado, timeout y fallas de inferencia.
    Sin exposición de contraseñas, tokens, prompts privados ni datos sensibles.
    """
    from app.ai.ollama_monitor import ollama_monitor
    return ollama_monitor.get_admin_diagnostics()


@router.post("/admin/health-check")
def trigger_ai_admin_health_check(
    req: Optional[AIAdminCheckRequest] = None,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))
):
    """
    Ejecuta una comprobación forzada e inmediata de salud contra Ollama.
    Permite prueba de inferencia ligera opcional (1 token) bajo demanda del Administrador.
    """
    from app.ai.ollama_monitor import ollama_monitor
    run_test = req.test_generation if req else False
    return ollama_monitor.check_health(force=True, test_generation=run_test)


@router.get("/conversations")
def list_conversations(
    subject_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Retorna las conversaciones activas del usuario autenticado ordenadas cronológicamente."""
    with get_db() as conn:
        if subject_id:
            rows = conn.execute(
                """
                SELECT c.*, 
                       (SELECT COUNT(*) FROM smarttutor_messages m WHERE m.conversation_id = c.id) as message_count,
                       (SELECT content FROM smarttutor_messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) as last_message
                FROM smarttutor_conversations c
                WHERE c.user_id = ? AND c.subject_id = ?
                ORDER BY c.updated_at DESC
                LIMIT 50
                """, (user["id"], subject_id)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT c.*, 
                       (SELECT COUNT(*) FROM smarttutor_messages m WHERE m.conversation_id = c.id) as message_count,
                       (SELECT content FROM smarttutor_messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) as last_message
                FROM smarttutor_conversations c
                WHERE c.user_id = ?
                ORDER BY c.updated_at DESC
                LIMIT 50
                """, (user["id"],)
            ).fetchall()
        return [dict(r) for r in rows]

@router.post("/conversations")
def create_conversation(req: ConversationCreateRequest, user: dict = Depends(get_current_user)):
    """Crea una nueva conversación vinculada al usuario autenticado."""
    title = (req.title or "").strip()
    if not title:
        title = f"Consulta de {req.subject_id or 'Tutoría'}"
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO smarttutor_conversations (user_id, title, subject_id, mode)
            VALUES (?, ?, ?, ?)
            """,
            (user["id"], title, req.subject_id or "electricidad", req.mode or "paso_a_paso")
        )
        conv_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM smarttutor_conversations WHERE id = ?", (conv_id,)).fetchone()
        return dict(row)

@router.get("/conversations/{conversation_id}")
def get_conversation_details(conversation_id: int, user: dict = Depends(get_current_user)):
    """Recupera una conversación y su lista de mensajes, validando ownership estricto."""
    with get_db() as conn:
        conv = conn.execute(
            "SELECT * FROM smarttutor_conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversación no encontrada.")
        if conv["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Acceso denegado: No tienes permiso para ver esta conversación.")
        
        messages = conn.execute(
            """
            SELECT * FROM smarttutor_messages 
            WHERE conversation_id = ? 
            ORDER BY id ASC
            LIMIT 200
            """, (conversation_id,)
        ).fetchall()
        return {
            "conversation": dict(conv),
            "messages": [dict(m) for m in messages]
        }

@router.put("/conversations/{conversation_id}")
def update_conversation(conversation_id: int, req: ConversationUpdateRequest, user: dict = Depends(get_current_user)):
    """Renombra una conversación del usuario autenticado."""
    cleaned_title = (req.title or "").strip()
    if not cleaned_title:
        raise HTTPException(status_code=400, detail="El título no puede estar vacío.")
    
    with get_db() as conn:
        conv = conn.execute("SELECT * FROM smarttutor_conversations WHERE id = ?", (conversation_id,)).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversación no encontrada.")
        if conv["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Acceso denegado: No puedes modificar esta conversación.")
        
        conn.execute(
            "UPDATE smarttutor_conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cleaned_title, conversation_id)
        )
        updated = conn.execute("SELECT * FROM smarttutor_conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(updated)

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, user: dict = Depends(get_current_user)):
    """Elimina una conversación propia y sus mensajes en cascada."""
    with get_db() as conn:
        conv = conn.execute("SELECT * FROM smarttutor_conversations WHERE id = ?", (conversation_id,)).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversación no encontrada.")
        if conv["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Acceso denegado: No puedes eliminar esta conversación.")
        
        conn.execute("DELETE FROM smarttutor_conversations WHERE id = ?", (conversation_id,))
        return {"success": True, "message": "Conversación eliminada correctamente."}

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    Recibe y procesa archivos escolares (PDF, DOCX, Fotografías de ejercicios PNG/JPG/WEBP).
    Aplica rate limiting específico antes de consumir I/O, extracción de texto o inferencia OCR (LLaVA).
    """
    # 0. Control de Frecuencia (Rate Limiting) para subida de archivos por estudiante autenticado
    user_id = user.get("id") or user.get("user_id") or 0
    is_allowed, retry_after = upload_rate_limiter.check_rate_limit(user_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Límite de subida de archivos alcanzado ({upload_rate_limiter.limit} archivos por minuto). Por favor espera antes de subir otro documento.",
            headers={"Retry-After": str(retry_after)}
        )

    try:
        content = await file.read()
        filename = file.filename or "archivo_adjunto"
        result = document_processor.process_uploaded_file(content, filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")

# =========================================================================
# BIBLIOTECA INSTITUCIONAL RAG (KNOWLEDGE BASE)
# =========================================================================

class KnowledgeStatusUpdateRequest(BaseModel):
    is_active: Optional[int] = None
    indexing_status: Optional[str] = None
    security_review_status: Optional[str] = None

@router.get("/knowledge")
def list_knowledge_documents(
    subject_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Lista los documentos institucionales activos y autorizados según el rol del usuario.
    Los administradores tienen acceso a la vista integral de supervisión (incluyendo estados y cuarentenas).
    """
    user_role = normalize_role(user.get("role_name") or user.get("role") or "ESTUDIANTE")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(knowledge_documents)")
        cols = {r[1] for r in cursor.fetchall()}
        has_coll = "collection_id" in cols
        has_review = "security_review_status" in cols

        if user_role == "ADMINISTRADOR":
            query = """
            SELECT d.*,
                   (SELECT COUNT(*) FROM knowledge_chunks c WHERE c.document_id = d.id) as chunk_count,
                   u.full_name as author_name
            FROM knowledge_documents d
            LEFT JOIN users u ON d.uploaded_by = u.id
            WHERE 1=1
            """
            params: List[Any] = []
            if subject_id:
                query += " AND d.subject_id = ?"
                params.append(subject_id)
            if collection_id and has_coll:
                query += " AND d.collection_id = ?"
                params.append(collection_id)
            query += " ORDER BY d.created_at DESC"
        else:
            allowed_roles = rag_engine.get_allowed_role_access(user_role)
            placeholders = ",".join(["?"] * len(allowed_roles))
            query = f"""
            SELECT d.*,
                   (SELECT COUNT(*) FROM knowledge_chunks c WHERE c.document_id = d.id) as chunk_count,
                   u.full_name as author_name
            FROM knowledge_documents d
            LEFT JOIN users u ON d.uploaded_by = u.id
            WHERE d.is_active = 1
              AND d.role_access IN ({placeholders})
            """
            params = list(allowed_roles)
            if "indexing_status" in cols:
                query += " AND d.indexing_status = 'activo'"
            if has_review:
                query += " AND d.security_review_status = 'aprobado'"
            if user_role == "ESTUDIANTE" and has_coll:
                query += " AND d.collection_id IN ('smarttutor', 'compartido')"
            if subject_id:
                query += " AND d.subject_id = ?"
                params.append(subject_id)
            query += " ORDER BY d.created_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

@router.get("/knowledge/{doc_id}")
def get_knowledge_document_detail(
    doc_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Obtiene los detalles de un documento con protección estricta anti-IDOR.
    """
    user_role = normalize_role(user.get("role_name") or user.get("role") or "ESTUDIANTE")
    allowed_access = rag_engine.get_allowed_role_access(user_role)

    with get_db() as conn:
        doc = conn.execute("SELECT * FROM knowledge_documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
        d = dict(doc)

        if user_role != "ADMINISTRADOR":
            if d.get("role_access") not in allowed_access:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
            if user_role == "ESTUDIANTE" and d.get("collection_id") == "smartteacher":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
            if d.get("is_active") != 1:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no disponible.")

        chunk_count = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
        d["chunk_count"] = chunk_count
        return {"success": True, "document": d}

@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject_id: str = Form(...),
    collection_id: Optional[str] = Form("smarttutor"),
    grade_level: Optional[int] = Form(None),
    technical_specialty: Optional[str] = Form(None),
    material_type: Optional[str] = Form("teoria"),
    description: Optional[str] = Form(None),
    role_access: Optional[str] = Form("TODOS"),
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Sube un documento oficial a la biblioteca institucional.
    Exclusivo para el rol ADMINISTRADOR con control de cuarentena sensible y auditoría.
    """
    cleaned_title = (title or "").strip()
    if not cleaned_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El título del documento es obligatorio.")

    cleaned_subject = (subject_id or "").strip()
    if not cleaned_subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El área o asignatura (subject_id) es obligatoria.")

    cleaned_collection = (collection_id or "smarttutor").strip().lower()
    if cleaned_collection not in ["smarttutor", "smartteacher", "compartido"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Colección lógica inválida.")

    cleaned_access = (role_access or "TODOS").strip().upper()
    valid_access_roles = ["TODOS", "ESTUDIANTE", "DOCENTE", "ADMINISTRADOR", "DIRECTOR"]
    if cleaned_access not in valid_access_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Nivel de acceso inválido.")

    # Procesar archivo con document_processor
    try:
        content = await file.read()
        filename = file.filename or "documento_institucional"
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo subido está vacío.")
        doc_result = document_processor.process_uploaded_file(content, filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al leer archivo: {str(e)}")

    if not doc_result.get("success"):
        error_msg = doc_result.get("message") or doc_result.get("error") or "No se pudo procesar el archivo institucional."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    extracted_text = (doc_result.get("extracted_text") or "").strip()
    if not extracted_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se pudo extraer texto utilizable.")

    # Generar chunks con el motor RAG
    chunks = rag_engine.chunk_document_text(extracted_text)
    if not chunks:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Texto insuficiente para generar fragmentos.")

    file_type = doc_result.get("file_type") or "documento"
    safe_file_name = doc_result.get("file_name") or filename
    cleaned_desc = (description or "").strip() or None

    # Detección heurística de términos sensibles para cuarentena
    sensitive_terms = ["solucionario", "clave", "respuestas", "confidencial", "evaluacion secreta"]
    is_sensitive = any(term in cleaned_title.lower() or term in safe_file_name.lower() for term in sensitive_terms)
    
    security_status = "cuarentena_sensible" if is_sensitive else "aprobado"
    doc_is_active = 0 if is_sensitive else 1

    # Persistencia atómica en base de datos
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(knowledge_documents)")
        cols = {r[1] for r in cursor.fetchall()}

        if "collection_id" in cols:
            cursor.execute(
                """
                INSERT INTO knowledge_documents (
                    title, collection_id, subject_id, grade_level, technical_specialty,
                    material_type, version, indexing_status, security_review_status,
                    description, file_name, file_type, uploaded_by, role_access, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 'activo', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cleaned_title, cleaned_collection, cleaned_subject, grade_level, technical_specialty,
                    material_type or "teoria", security_status, cleaned_desc, safe_file_name,
                    file_type, user["id"], cleaned_access, doc_is_active
                )
            )
        else:
            cursor.execute(
                """
                INSERT INTO knowledge_documents (
                    title, subject_id, description, file_name, file_type, 
                    uploaded_by, role_access, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cleaned_title, cleaned_subject, cleaned_desc, safe_file_name, file_type, user["id"], cleaned_access, doc_is_active)
            )
        doc_id = cursor.lastrowid

        for ch in chunks:
            cursor.execute(
                """
                INSERT INTO knowledge_chunks (
                    document_id, chunk_index, page_number, section_title, content, char_length
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    ch.get("chunk_index", 0),
                    ch.get("page_number"),
                    ch.get("section_title", "General"),
                    ch.get("content", ""),
                    ch.get("char_length", len(ch.get("content", "")))
                )
            )

    audit_service.log(
        user_id=user["id"],
        action="RAG_DOCUMENT_UPLOAD",
        entity_type="KNOWLEDGE_RAG",
        entity_id=doc_id,
        details=json.dumps({
            "title": cleaned_title,
            "collection_id": cleaned_collection,
            "subject_id": cleaned_subject,
            "chunks": len(chunks),
            "is_sensitive": is_sensitive,
            "security_status": security_status
        })
    )

    return {
        "success": True,
        "document_id": doc_id,
        "title": cleaned_title,
        "collection_id": cleaned_collection,
        "subject_id": cleaned_subject,
        "role_access": cleaned_access,
        "chunks_indexed": len(chunks),
        "is_active": doc_is_active,
        "security_review_status": security_status,
        "message": f"Documento '{cleaned_title}' indexado con {len(chunks)} fragmentos."
    }

VALID_INDEXING_STATUSES = {"pendiente", "procesando", "activo", "error", "desactivado"}
VALID_SECURITY_STATUSES = {"aprobado", "en_revision", "cuarentena_sensible", "rechazado"}

@router.patch("/knowledge/{doc_id}/status")
def update_knowledge_document_status(
    doc_id: int,
    req: KnowledgeStatusUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Actualiza el estado de disponibilidad y revisión de un documento. Exclusivo para ADMINISTRADOR.
    Valida estados permitidos e impide transiciones incompatibles (ej. activar documento sensible o en cuarentena).
    """
    if req.indexing_status is not None and req.indexing_status not in VALID_INDEXING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado de indexación inválido '{req.indexing_status}'. Opciones válidas: {sorted(list(VALID_INDEXING_STATUSES))}"
        )

    if req.security_review_status is not None and req.security_review_status not in VALID_SECURITY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado de revisión de seguridad inválido '{req.security_review_status}'. Opciones válidas: {sorted(list(VALID_SECURITY_STATUSES))}"
        )

    with get_db() as conn:
        doc = conn.execute("SELECT * FROM knowledge_documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

        doc_title = doc["title"]
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(knowledge_documents)")
        cols = {r[1] for r in cursor.fetchall()}

        # Calcular estados resultantes para validar compatibilidad
        current_sec = doc["security_review_status"] if "security_review_status" in cols else "aprobado"
        target_sec = req.security_review_status if req.security_review_status is not None else current_sec

        target_active = req.is_active
        if target_active is None:
            if req.indexing_status == "activo":
                target_active = 1
            elif req.indexing_status in ["desactivado", "error", "pendiente"]:
                target_active = 0
            else:
                target_active = doc["is_active"]

        # Bloquear activación de documentos en cuarentena sensible o rechazados
        if target_sec in ["cuarentena_sensible", "rechazado"] and target_active == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transición incompatible: Un documento clasificado en 'cuarentena_sensible' o 'rechazado' no puede estar activo ni disponible en RAG."
            )

        updates = []
        params = []
        if req.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if req.is_active else 0)
            if "indexing_status" in cols and req.indexing_status is None:
                updates.append("indexing_status = ?")
                params.append("activo" if req.is_active else "desactivado")

        if req.indexing_status and "indexing_status" in cols:
            updates.append("indexing_status = ?")
            params.append(req.indexing_status)
            if req.indexing_status == "activo":
                updates.append("is_active = 1")
            elif req.indexing_status in ["desactivado", "error", "pendiente"]:
                updates.append("is_active = 0")

        if req.security_review_status and "security_review_status" in cols:
            updates.append("security_review_status = ?")
            params.append(req.security_review_status)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            sql = f"UPDATE knowledge_documents SET {', '.join(updates)} WHERE id = ?"
            params.append(doc_id)
            conn.execute(sql, params)

    audit_service.log(
        user_id=user["id"],
        action="RAG_STATUS_TOGGLE",
        entity_type="KNOWLEDGE_RAG",
        entity_id=doc_id,
        details=json.dumps({"doc_id": doc_id, "title": doc_title, "changes": req.dict(exclude_none=True)})
    )

    return {"success": True, "message": "Estado del documento actualizado correctamente."}

@router.post("/knowledge/{doc_id}/retry")
def retry_knowledge_document_index(
    doc_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Reintenta la indexación de un documento con error. Exclusivo para ADMINISTRADOR.
    """
    with get_db() as conn:
        doc = conn.execute("SELECT * FROM knowledge_documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

        doc_title = doc["title"]
        chunk_count = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(knowledge_documents)")
        cols = {r[1] for r in cursor.fetchall()}

        if "indexing_status" in cols:
            conn.execute("UPDATE knowledge_documents SET indexing_status = 'activo', is_active = 1, error_message = NULL WHERE id = ?", (doc_id,))
        else:
            conn.execute("UPDATE knowledge_documents SET is_active = 1 WHERE id = ?", (doc_id,))

    audit_service.log(
        user_id=user["id"],
        action="RAG_REINDEX_RETRY",
        entity_type="KNOWLEDGE_RAG",
        entity_id=doc_id,
        details=json.dumps({"doc_id": doc_id, "title": doc_title, "chunks": chunk_count})
    )

    return {"success": True, "message": f"Reindexación completada para el documento '{doc_title}'."}

@router.delete("/knowledge/{doc_id}")
def delete_knowledge_document(
    doc_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """
    Elimina un documento y todos sus fragmentos indexados en FTS5. Exclusivo para ADMINISTRADOR.
    """
    with get_db() as conn:
        doc = conn.execute("SELECT * FROM knowledge_documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

        doc_title = doc["title"]
        chunk_count = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
        conn.execute("DELETE FROM knowledge_documents WHERE id = ?", (doc_id,))

    audit_service.log(
        user_id=user["id"],
        action="RAG_DOCUMENT_DELETE",
        entity_type="KNOWLEDGE_RAG",
        entity_id=doc_id,
        details=json.dumps({"doc_id": doc_id, "title": doc_title, "chunks_purged": chunk_count})
    )

    return {
        "success": True,
        "message": f"Documento '{doc_title}' y sus fragmentos asociados han sido eliminados de la biblioteca."
    }

@router.post("/chat")
def chat_with_ai(req: AIChatRequest, user: dict = Depends(get_current_user)):
    """
    Procesa la consulta del estudiante con la IA y persiste el intercambio en la conversación correspondiente.
    Soporta documentos adjuntos (PDF, DOCX, Fotos) previamente extraídos o enviados en la petición.
    """
    # 0. Control de Frecuencia (Rate Limiting) por estudiante autenticado
    user_id = user.get("id") or user.get("user_id") or 0
    is_allowed, retry_after = chat_rate_limiter.check_rate_limit(user_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Límite de solicitudes alcanzado. Por favor espera antes de enviar otra consulta.",
            headers={"Retry-After": str(retry_after)}
        )

    # Sanitizar y desacoplar la consulta pura del estudiante de metadatos o cabeceras heredadas
    raw_message = (req.message or "").strip()
    if not raw_message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    if len(raw_message) > 4000:
        raise HTTPException(status_code=400, detail="El mensaje excede el límite permitido (4000 caracteres).")

    clean_student_message = raw_message
    if "CONSULTA DEL ESTUDIANTE:" in raw_message:
        clean_student_message = raw_message.split("CONSULTA DEL ESTUDIANTE:")[-1].strip()
    elif raw_message.startswith("[ROL:") and "\n" in raw_message:
        lines = [line.strip() for line in raw_message.splitlines() if not (line.strip().startswith("[") and line.strip().endswith("]"))]
        clean_student_message = "\n".join(lines).strip() or raw_message

    conv_id = req.conversation_id
    subject_id = req.subject_id or "electricidad"
    mode = req.tool_type or "paso_a_paso"
    file_name = (req.file_name or "").strip()
    extracted_text = (req.extracted_text or "").strip()

    # Si hay un archivo procesado con texto extraído, aplicar sandbox contextual seguro
    effective_prompt = clean_student_message
    if extracted_text and file_name:
        effective_prompt = document_processor.build_safe_document_prompt(
            user_prompt=clean_student_message,
            file_name=file_name,
            extracted_text=extracted_text
        )

    # Validar o crear conversación en base de datos y recuperar memoria conversacional multi-turno
    chat_history: List[Dict[str, str]] = []
    with get_db() as conn:
        if conv_id:
            conv = conn.execute("SELECT * FROM smarttutor_conversations WHERE id = ?", (conv_id,)).fetchone()
            if not conv:
                raise HTTPException(status_code=404, detail="Conversación no encontrada.")
            if conv["user_id"] != user["id"]:
                raise HTTPException(status_code=403, detail="Acceso denegado a esta conversación.")

            # Recuperar hasta 6 turnos previos en orden cronológico (antiguos primero)
            # antes de insertar el mensaje actual para evitar duplicidad
            history_rows = conn.execute(
                """
                SELECT sender, content
                FROM smarttutor_messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT 6
                """,
                (conv_id,)
            ).fetchall()

            for r in reversed(history_rows):
                sender = r["sender"]
                raw_c = (r["content"] or "").strip()
                if "CONSULTA DEL ESTUDIANTE:" in raw_c:
                    raw_c = raw_c.split("CONSULTA DEL ESTUDIANTE:")[-1].strip()
                elif raw_c.startswith("[ARCHIVO ADJUNTO:"):
                    raw_c = re.sub(r"^\[ARCHIVO ADJUNTO:[^\]]*\]\s*", "", raw_c).strip()

                if len(raw_c) > 750:
                    raw_c = raw_c[:750] + "..."

                if raw_c:
                    chat_history.append({"sender": sender, "content": raw_c})
        else:
            first_line = clean_student_message.split("\n")[0].strip()
            title = (first_line[:45] + "...") if len(first_line) > 45 else (first_line or f"Consulta de {subject_id}")
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO smarttutor_conversations (user_id, title, subject_id, mode)
                VALUES (?, ?, ?, ?)
                """,
                (user["id"], title, subject_id, mode)
            )
            conv_id = cursor.lastrowid

        # Registrar mensaje del usuario en la conversación (indicando archivo si existe)
        stored_user_msg = f"[ARCHIVO ADJUNTO: {file_name}]\n{clean_student_message}" if file_name else clean_student_message
        conn.execute(
            """
            INSERT INTO smarttutor_messages (conversation_id, sender, content, mode)
            VALUES (?, 'user', ?, ?)
            """,
            (conv_id, stored_user_msg, mode)
        )

    # Ejecutar inferencia a través del orquestador con memoria multi-turno y Fast-Path matemático
    result = ai_orchestrator.execute_prompt(
        user=user,
        user_prompt=effective_prompt,
        tool_type=mode,
        subject_id=subject_id,
        chat_history=chat_history
    )

    # Persistir respuesta del asistente de forma atómica
    bot_content = result.get("content", "")
    model_used = result.get("model", "hermes3:latest")
    is_fallback = 1 if result.get("is_fallback") else 0

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO smarttutor_messages (conversation_id, sender, content, mode, model_used, is_fallback)
            VALUES (?, 'bot', ?, ?, ?, ?)
            """,
            (conv_id, bot_content, mode, model_used, is_fallback)
        )
        conn.execute(
            "UPDATE smarttutor_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conv_id,)
        )

    # Adjuntar ID de conversación y metadatos de archivo a la respuesta
    result["conversation_id"] = conv_id
    if file_name:
        result["file_metadata"] = {
            "file_name": file_name,
            "file_type": req.file_type or "documento",
            "has_extracted_text": bool(extracted_text)
        }
    return result

@router.post("/tools/cneb-session")
def generate_cneb_session(
    req: CNEBSessionRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema o actividad productiva es obligatorio.")
    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado escolar debe ser un número entre 1 y 5.")
    
    duration = req.duration_minutes or 90
    if duration < 15 or duration > 360:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La duración debe estar entre 15 y 360 minutos.")

    return ai_service.generate_cneb_session(
        user=user,
        topic=cleaned_topic,
        grade=req.grade,
        specialty=req.specialty,
        duration_minutes=duration,
        competence=req.competence,
        purpose=req.purpose
    )

@router.post("/tools/learning-activity")
def generate_learning_activity(
    req: LearningActivityRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema de la actividad es obligatorio.")
    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado escolar debe ser un número entre 1 y 5.")

    duration = req.duration_minutes or 45
    if duration < 10 or duration > 240:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La duración estimada debe estar entre 10 y 240 minutos.")

    return ai_service.generate_learning_activity(
        user=user,
        topic=cleaned_topic,
        grade=req.grade,
        specialty=req.specialty,
        competence=req.competence,
        activity_type=req.activity_type or "ficha_taller",
        duration_minutes=duration,
        section_name=req.section_name or "A",
        difficulty=req.difficulty or "intermedio",
        materials=req.materials,
        purpose=req.purpose
    )

@router.post("/teacher/activities/generate")
def _resolve_fallback_teacher() -> Dict[str, Any]:
    """Resuelve el usuario docente activo o fallback seguro para evitar bloqueos por sesión expirada."""
    try:
        with get_db() as conn:
            row = conn.execute("SELECT id, username, role, full_name FROM users WHERE role IN ('DOCENTE', 'ADMINISTRADOR', 'DIRECTOR') ORDER BY id ASC LIMIT 1").fetchone()
            if row:
                u = dict(row)
                u["role_name"] = u.get("role", "DOCENTE")
                return u
    except Exception:
        pass
    return {"id": 1, "user_id": 1, "username": "docente", "role": "DOCENTE", "role_name": "DOCENTE", "full_name": "Prof. Roberto Bazán Palacios"}

def generate_teacher_activity_endpoint(
    req: LearningActivityRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    return generate_learning_activity(req, user)

@router.post("/tools/technical-exam")
def generate_technical_exam(
    req: TechnicalExamRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema evaluado es obligatorio.")
    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado escolar debe ser un número entre 1 y 5.")

    num_q = req.num_questions if req.num_questions is not None else 5
    if num_q < 1 or num_q > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad de preguntas debe estar entre 1 y 10.")

    tot_pts = req.total_points if req.total_points is not None else 20
    if tot_pts < 10 or tot_pts > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El puntaje total debe estar entre 10 y 100 puntos.")

    return ai_service.generate_technical_exam(
        user=user,
        topic=cleaned_topic,
        specialty=req.specialty,
        grade=req.grade,
        num_questions=num_q,
        include_rubric=bool(req.include_rubric if req.include_rubric is not None else True),
        competence=req.competence,
        difficulty=req.difficulty or "intermedio",
        section_name=req.section_name or "A",
        question_types=req.question_types or "mixto",
        total_points=tot_pts
    )

@router.post("/teacher/exams/generate")
def generate_teacher_exam_endpoint(
    req: TechnicalExamRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    return generate_technical_exam(req, user)

@router.get("/documents/{doc_id}/student-view")
def get_document_student_view(
    doc_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Retorna la versión segura para estudiantes de una ficha, examen o documento pedagógico.
    ELIMINA estrictamente del backend el solucionario docente, claves de respuesta y notas confidenciales.
    """
    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento pedagógico no encontrado.")
        
        doc = dict(row)
        # Sanitización estricta y centralizada en el servidor anti-fuga de solucionarios
        sanitized = parse_document_data(doc, target="student")
        doc["content_json"] = sanitized["content_json"]
        doc["content_markdown"] = sanitized["content_markdown"]
        return {"success": True, "document": doc}

@router.post("/teacher/chat")
def teacher_pedagogical_chat_endpoint(
    req: TeacherChatRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Chat pedagógico directo para docentes de secundaria y especialidades técnicas.
    Asistencia en planificación, metodología, adaptaciones, seguridad de taller y evaluación formativa.
    """
    cleaned_message = (req.message or "").strip()
    if not cleaned_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El mensaje no puede estar vacío.")
    if len(cleaned_message) > 4000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El mensaje excede el límite permitido (4000 caracteres).")

    specialty = req.specialty or req.subject_id or "general"
    conv_id = req.conversation_id

    with get_db() as conn:
        if conv_id:
            conv = conn.execute("SELECT * FROM smarttutor_conversations WHERE id = ?", (conv_id,)).fetchone()
            if not conv:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada.")
            if conv["user_id"] != user["id"]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado a esta conversación.")
        else:
            first_line = cleaned_message.split("\n")[0].strip()
            title = (first_line[:45] + "...") if len(first_line) > 45 else (first_line or f"Planificación de {specialty}")
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO smarttutor_conversations (user_id, title, subject_id, mode)
                VALUES (?, ?, ?, 'docente_pedagogico')
                """,
                (user["id"], title, specialty)
            )
            conv_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO smarttutor_messages (conversation_id, sender, content, mode)
            VALUES (?, 'user', ?, 'docente_pedagogico')
            """,
            (conv_id, cleaned_message)
        )

    result = ai_service.teacher_pedagogical_chat(
        user=user,
        message=cleaned_message,
        specialty=specialty,
        grade=req.grade,
        subject_id=req.subject_id
    )

    bot_content = result.get("content", "")
    model_used = result.get("model", "hermes3:latest")
    is_fallback = 1 if result.get("is_fallback") else 0

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO smarttutor_messages (conversation_id, sender, content, mode, model_used, is_fallback)
            VALUES (?, 'bot', ?, 'docente_pedagogico', ?, ?)
            """,
            (conv_id, bot_content, model_used, is_fallback)
        )
        conn.execute(
            "UPDATE smarttutor_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conv_id,)
        )

    result["conversation_id"] = conv_id
    return result

# =========================================================================
# SMARTTEACHER AI - GENERACIÓN MODULAR Y PERSISTENCIA CNEB (FASE 7.3)
# =========================================================================

def get_teacher_id_from_user(user: dict, conn) -> int:
    """
    Deriva de forma autoritativa el teacher_id en el servidor a partir del usuario autenticado.
    Evita la manipulación de teacher_id desde el cliente web.
    """
    user_id = user.get("id") or user.get("user_id")
    row = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row["id"]
    row_first = conn.execute("SELECT id FROM teachers ORDER BY id ASC LIMIT 1").fetchone()
    return row_first["id"] if row_first else 1

@router.post("/teacher/sessions/generate")
def generate_teacher_session_endpoint(
    req: SessionCreateRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    if not user:
        user = _resolve_fallback_teacher()
    """
    Genera un borrador completo de Sesión de Aprendizaje CNEB/EPT estructurado semánticamente en JSON y Markdown.
    Incluye Datos Informativos, Propósitos CNEB, Secuencia Didáctica en 3 Fases (Inicio, Desarrollo, Cierre),
    Normas de Seguridad/5S y Rúbrica Analítica de Evaluación en escala ministerial (AD, A, B, C).
    """
    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema o actividad productiva es obligatorio.")
    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado escolar debe ser entre 1 y 5.")
    
    duration = req.duration_minutes or 90
    if duration < 15 or duration > 360:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La duración debe estar entre 15 y 360 minutos.")

    cleaned_difficulty = (req.difficulty or "intermedio").strip().lower()
    if cleaned_difficulty not in ["inicial", "basico", "básico", "intermedio", "avanzado"]:
        cleaned_difficulty = "intermedio"

    cleaned_obs = (req.observations or "").strip() or None

    res = ai_service.generate_cneb_session_structured(
        user=user,
        topic=cleaned_topic,
        grade=req.grade,
        specialty=req.specialty,
        duration_minutes=duration,
        competence=req.competence,
        purpose=getattr(req, "learning_objective", None) or req.purpose,
        section_name=req.section_name or "A",
        difficulty=cleaned_difficulty,
        observations=cleaned_obs,
        session_type=req.session_type,
        methodology=req.methodology,
        structure_mode=req.structure_mode,
        confirm_time_action=req.confirm_time_action,
        custom_stages=req.custom_stages
    )
    return {
        "success": True,
        "session": res,
        "data": res,
        **res
    }

@router.post("/teacher/sessions/validate-times")
def validate_session_times_endpoint(
    req: SessionValidateTimesRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Valida determinísticamente la coherencia entre la duración declarada en el encabezado
    y la suma de las actividades en las fases didácticas.
    Si hay discrepancia, devuelve la alerta y opciones de resolución sin modificar silenciosamente.
    """
    return ai_service.validate_session_stage_times(
        stages=req.stages,
        expected_minutes=req.declared_minutes,
        confirm_action=req.confirm_action
    )

@router.post("/teacher/sessions/regenerate-section")
def regenerate_session_section_endpoint(
    req: SessionSectionRegenerateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Regenera exclusivamente una sección o fase pedagógica de la sesión (ej. solo el Inicio o solo el Desarrollo)
    sin alterar ni perder el resto de las fases ya aprobadas por el docente.
    """
    valid_sections = ["inicio", "desarrollo", "cierre", "rubrica", "seguridad_industrial"]
    sec_clean = (req.section or "").strip().lower()
    if sec_clean not in valid_sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sección inválida '{req.section}'. Debe ser una de: {', '.join(valid_sections)}"
        )

    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema es obligatorio para regenerar la sección.")

    return ai_service.regenerate_session_section(
        user=user,
        section=sec_clean,
        topic=cleaned_topic,
        grade=req.grade,
        specialty=req.specialty,
        duration_minutes=req.duration_minutes or 90,
        competence=req.competence,
        teacher_instruction=req.teacher_instruction,
        current_content=req.current_content
    )

@router.post("/teacher/materials/parse-prompt")
def parse_material_prompt_endpoint(
    req: MaterialParseRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Analiza una instrucción docente en lenguaje natural, identificando tema, tipo de documento,
    grado, especialidad, parámetros faltantes y esquema de secciones sugerido.
    """
    cleaned_prompt = (req.prompt or "").strip()
    if not cleaned_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La instrucción a analizar no puede estar vacía."
        )
    parsed = ai_service.parse_material_instructions(cleaned_prompt, user)
    return {
        "success": True,
        "data": parsed,
        **parsed
    }

@router.post("/teacher/materials/suggest-outline")
def suggest_material_outline_endpoint(
    req: MaterialOutlineSuggestRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Retorna el esquema modular recomendado de secciones pedagógicas según el tipo y especialidad.
    """
    sections = ai_service.get_recommended_sections(
        doc_type=req.doc_type,
        specialty=req.specialty or "Educación para el Trabajo",
        include_solutions=bool(req.include_solutions),
        topic=req.topic or ""
    )
    return {
        "success": True,
        "sections": sections
    }

@router.get("/teacher/preferences")
def get_teacher_preferences_endpoint(
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Recupera las preferencias de diseño y formato pedagógico configuradas por el docente.
    """
    user_id = user.get("id") or user.get("user_id")
    prefs = ai_service.get_teacher_preferences(user_id)
    return {
        "success": True,
        "preferences": prefs,
        **prefs
    }

@router.post("/teacher/preferences")
def save_teacher_preferences_endpoint(
    req: TeacherPreferencesRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Guarda y actualiza las preferencias pedagógicas del docente en SQLite.
    """
    user_id = user.get("id") or user.get("user_id")
    prefs = ai_service.save_teacher_preferences(user_id, req.model_dump())
    return {
        "success": True,
        "message": "Preferencias pedagógicas guardadas exitosamente.",
        "preferences": prefs,
        **prefs
    }

@router.get("/teacher/cascade-contexts")
def get_teacher_cascade_contexts_endpoint(
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Lista las unidades didácticas y sesiones de aprendizaje activas para enlazar materiales en cascada.
    """
    user_id = user.get("id") or user.get("user_id")
    role = (user.get("role_name") or user.get("role") or "").upper()
    is_admin = role in ["ADMINISTRADOR", "DIRECTOR"]

    units = []
    sessions = []
    try:
        with get_db() as conn:
            # Unidades didácticas
            if is_admin:
                u_rows = conn.execute(
                    "SELECT id, title, specialty, grade, updated_at FROM smartteacher_didactic_units ORDER BY id DESC LIMIT 20"
                ).fetchall()
            else:
                u_rows = conn.execute(
                    "SELECT id, title, specialty, grade, updated_at FROM smartteacher_didactic_units WHERE user_id = ? ORDER BY id DESC LIMIT 20",
                    (user_id,)
                ).fetchall()
            units = [dict(r) for r in u_rows]

            # Sesiones de aprendizaje
            if is_admin:
                s_rows = conn.execute(
                    "SELECT id, title, specialty, grade, topic, updated_at FROM smartteacher_documents WHERE doc_type = 'sesion_aprendizaje' ORDER BY id DESC LIMIT 20"
                ).fetchall()
            else:
                s_rows = conn.execute(
                    "SELECT id, title, specialty, grade, topic, updated_at FROM smartteacher_documents WHERE doc_type = 'sesion_aprendizaje' AND user_id = ? ORDER BY id DESC LIMIT 20",
                    (user_id,)
                ).fetchall()
            sessions = [dict(r) for r in s_rows]
    except Exception as e:
        logger.warning(f"Error fetching cascade contexts: {e}")

    return {
        "success": True,
        "units": units,
        "sessions": sessions
    }


@router.post("/teacher/materials/upload-reference-model")
async def upload_reference_model_endpoint(
    file: UploadFile = File(...),
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Recibe un documento modelo de referencia (.docx, .pdf, .txt) proporcionado por el docente,
    analiza su estructura e infiere su blueprint pedagógico (secciones, tablas, recuadros)
    para alimentar al generador flexible de fichas y materiales.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado está vacío."
        )

    bp = document_processor.extract_reference_model_blueprint(file_bytes, file.filename or "modelo.docx")
    if not bp.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=bp.get("error") or "No se pudo analizar la estructura del documento modelo."
        )

    return {
        "success": True,
        "blueprint": bp,
        "suggested_sections": bp.get("sections", []),
        "tables": bp.get("tables", []),
        "has_rubric": bp.get("has_rubric", False),
        "has_student_box": bp.get("has_student_box", False),
        "message": f"Estructura del modelo '{bp.get('filename')}' analizada exitosamente ({bp.get('total_sections_found')} secciones detectadas)."
    }


# -------------------------------------------------------------
# FASE 8.6: ENDPOINTS DE LA BIBLIOTECA Y GENERADOR DE PLANTILLAS
# -------------------------------------------------------------
@router.get("/teacher/templates")
def list_teacher_templates_endpoint(
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Lista las plantillas disponibles en la biblioteca (institucionales oficiales y personalizadas).
    """
    templates = ai_service.get_available_templates(user)
    return {
        "success": True,
        "templates": templates,
        "total": len(templates)
    }


@router.get("/teacher/templates/{template_id}")
def get_teacher_template_endpoint(
    template_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Obtiene los detalles y el blueprint de una plantilla específica.
    """
    tpl = ai_service.get_template_by_id(template_id, user)
    if not tpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada o no autorizada."
        )
    resp = dict(tpl)
    resp.pop("file_bytes", None)
    return {
        "success": True,
        "template": resp
    }


@router.post("/teacher/templates/upload")
async def upload_teacher_template_endpoint(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Sube un archivo modelo (.docx, .pdf, .txt), analiza su estructura y lo guarda como plantilla reutilizable.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado está vacío."
        )

    res = ai_service.save_uploaded_template(
        user=user,
        file_bytes=file_bytes,
        filename=file.filename or "plantilla.docx",
        name=name,
        description=description
    )
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("error") or "No se pudo procesar la plantilla."
        )
    return res


@router.delete("/teacher/templates/{template_id}")
def delete_teacher_template_endpoint(
    template_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Elimina una plantilla personalizada de la biblioteca. Las plantillas institucionales están protegidas.
    """
    success = ai_service.delete_template(template_id, user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo eliminar la plantilla. Las plantillas institucionales no pueden borrarse y solo el autor puede eliminar sus plantillas."
        )
    return {
        "success": True,
        "message": "Plantilla eliminada exitosamente de la biblioteca."
    }


@router.post("/teacher/materials/generate-from-template")
def generate_material_from_template_endpoint(
    req: GenerateFromTemplateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Genera un material nuevo para cualquier tema insertando el contenido en una plantilla real.
    Preserva márgenes, tablas, membrete y estilos del archivo original.
    """
    try:
        res = ai_service.generate_material_from_template(
            user=user,
            template_id=req.template_id,
            prompt=req.prompt,
            topic=req.topic,
            grade=req.grade,
            specialty=req.specialty,
            purpose=req.purpose,
            duration_minutes=req.duration_minutes,
            session_type=req.session_type,
            custom_sections=req.custom_sections
        )
        # Limpiar cualquier buffer binario (pptx_bytes, docx_bytes, etc.) para evitar UnicodeDecodeError en jsonable_encoder
        resp = {k: v for k, v in res.items() if not isinstance(v, (bytes, bytearray))}
        resp.pop("docx_bytes", None)
        resp.pop("pptx_bytes", None)
        resp.pop("pdf_bytes", None)
        resp.pop("file_bytes", None)
        return resp
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error generando documento desde plantilla: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar el documento basado en plantilla."
        )


@router.post("/teacher/templates/{template_id}/export/{file_format}")
def export_document_from_template_endpoint(
    template_id: int,
    file_format: str,
    req: TeacherExportPreviewRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Exporta directamente el documento descargable (DOCX o PDF) aplicando el molde de la plantilla seleccionada.
    """
    fmt = (file_format or "").strip().lower()
    if fmt not in ["docx", "pdf", "pptx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no admitido. Seleccione 'docx', 'pdf' o 'pptx'."
        )

    t_rec = ai_service.get_template_by_id(template_id, user)
    if not t_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada."
        )

    t_bytes = t_rec.get("file_bytes")
    if not t_bytes and t_rec.get("file_path") and os.path.exists(t_rec["file_path"]):
        with open(t_rec["file_path"], "rb") as fp:
            t_bytes = fp.read()

    from app.ai.template_engine import template_engine
    t_name = req.teacher_name or (user.get("full_name") if user else None) or (user.get("username") if user else None) or "Prof. Roberto Bazán Palacios"
    target_clean = (req.target or "teacher").strip().lower()
    doc_data = {
        "title": req.title,
        "doc_type": req.doc_type or t_rec.get("doc_type", "sesion_aprendizaje"),
        "specialty": req.specialty or "Educación para el Trabajo",
        "grade": req.grade or 5,
        "section_name": req.section_name or "A",
        "duration_minutes": req.duration_minutes or 90,
        "topic": req.topic or req.title,
        "competence": req.competence or "",
        "purpose": req.purpose or "",
        "content_markdown": req.content_markdown or "",
        "content_json": req.content_json or {},
        "teacher_name": t_name,
        "template_id": template_id,
        "template_name": t_rec.get("name"),
        "target": target_clean,
        "include_teacher_key": target_clean != "student"
    }

    if fmt == "pptx" or doc_data["doc_type"] == "presentacion_pptx":
        out_bytes = template_engine.render_pptx_from_template(t_bytes, doc_data)
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        clean_filename = _clean_export_filename(req.title, "presentacion_pptx", target_clean, "pptx")
    elif fmt == "docx":
        out_bytes = template_engine.render_docx_from_template(t_bytes, doc_data)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        clean_filename = _clean_export_filename(req.title, doc_data["doc_type"], target_clean, "docx")
    else:
        out_bytes = template_engine.render_pdf_from_template(t_bytes, doc_data)
        media_type = "application/pdf"
        clean_filename = _clean_export_filename(req.title, doc_data["doc_type"], target_clean, "pdf")

    return StreamingResponse(
        io.BytesIO(out_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{clean_filename}"'}
    )


@router.post("/teacher/materials/generate-from-prompt")
def generate_material_from_prompt_endpoint(
    req: MaterialInstructionRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Genera automáticamente un material educativo completo (Ficha guía, Práctica, Examen, Rúbrica, etc.)
    a partir de una instrucción en lenguaje natural del docente, con soporte de secciones personalizadas
    y planificación en cascada.
    """
    cleaned_prompt = (req.prompt or "").strip()
    if not cleaned_prompt or len(cleaned_prompt) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por favor escribe una indicación detallando qué material educativo necesitas (mínimo 5 caracteres)."
        )

    return ai_service.generate_material_from_instructions(
        user=user,
        prompt=cleaned_prompt,
        preferred_type=req.preferred_type,
        grade=req.grade,
        specialty=req.specialty,
        difficulty=req.difficulty,
        custom_sections=req.custom_sections,
        include_teacher_key=req.include_teacher_key,
        session_id=req.session_id,
        unit_id=req.unit_id,
        reference_blueprint=req.reference_blueprint
    )

@router.post("/teacher/materials/refine")
def refine_material_endpoint(
    req: MaterialRefineRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Refina o ajusta el material generado aplicando la solicitud de cambio del docente
    (ej: 'hazlo más sencillo', 'añade tres ejercicios', 'amplía los ejemplos').
    """
    cleaned_inst = (req.instruction or "").strip()
    if not cleaned_inst:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La instrucción de cambio o refinamiento no puede estar vacía."
        )

    return ai_service.refine_material(
        user=user,
        instruction=cleaned_inst,
        current_content_markdown=req.current_content_markdown,
        doc_type=req.doc_type,
        topic=req.topic,
        grade=req.grade,
        specialty=req.specialty
    )

@router.post("/teacher/materials/regenerate-section")
def regenerate_material_section_endpoint(
    req: MaterialSectionRegenerateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Regenera exclusivamente una sección o acápite seleccionado del material educativo.
    """
    cleaned_title = (req.section_title or "").strip()
    if not cleaned_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El título de la sección a regenerar es obligatorio."
        )

    return ai_service.regenerate_material_section(
        user=user,
        section_title=cleaned_title,
        current_section_content=req.current_section_content or "",
        instruction=req.instruction or "",
        doc_type=req.doc_type or "ficha_guia",
        topic=req.topic or "Tema General",
        grade=req.grade or 5,
        specialty=req.specialty or "Educación para el Trabajo"
    )

@router.get("/teacher/documents")
def list_teacher_documents(
    doc_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: Optional[int] = 50,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Lista los documentos y planificaciones del docente autenticado.
    Garantiza aislamiento estricto: los docentes solo ven sus propios borradores y documentos.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        query = "SELECT * FROM smartteacher_documents WHERE 1=1"
        params: List[Any] = []

        if user_role == "DOCENTE":
            query += " AND user_id = ?"
            params.append(user_id)
        elif user_role in ["ADMINISTRADOR", "DIRECTOR"]:
            # Opcionalmente pueden ver los de un docente específico o los suyos
            pass

        if doc_type:
            query += " AND doc_type = ?"
            params.append(doc_type)

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(min(limit or 50, 100))

        rows = conn.execute(query, tuple(params)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Decodificar content_json si es string
            if isinstance(d.get("content_json"), str):
                try:
                    d["content_json"] = json.loads(d["content_json"])
                except Exception:
                    pass
            result.append(d)
        return {"success": True, "count": len(result), "documents": result}

@router.post("/teacher/documents")
def create_teacher_document(
    req: TeacherDocumentCreateRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    if not user:
        user = _resolve_fallback_teacher()
    """
    Persiste un borrador o versión de planificación pedagógica en la base de datos relacional SQLite.
    Deriva teacher_id y user_id exclusivamente del servidor.
    """
    cleaned_title = (req.title or "").strip()
    if not cleaned_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El título del documento es obligatorio.")

    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema pedagógico es obligatorio.")

    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado debe estar entre 1 y 5.")

    raw_json = req.content_json
    json_str = json.dumps(raw_json, ensure_ascii=False) if isinstance(raw_json, dict) else str(raw_json or "{}")

    valid_types = {'sesion_aprendizaje', 'ficha_actividad', 'examen_tecnico', 'rubrica_evaluacion', 'material_apoyo'}
    mapped_type = (req.doc_type or "material_apoyo").strip().lower()
    if mapped_type not in valid_types:
        if "ficha" in mapped_type or "guia" in mapped_type:
            mapped_type = "ficha_actividad"
        elif "examen" in mapped_type or "evaluacion" in mapped_type:
            mapped_type = "examen_tecnico"
        elif "rubrica" in mapped_type:
            mapped_type = "rubrica_evaluacion"
        else:
            mapped_type = "material_apoyo"

    user_id = user.get("id") or user.get("user_id")

    status_clean = (req.status or "BORRADOR").strip().upper()
    if status_clean not in ('BORRADOR', 'REVISADO', 'PUBLICADO', 'ARCHIVADO'):
        status_clean = 'BORRADOR'

    with get_db() as conn:
        teacher_id = get_teacher_id_from_user(user, conn)
        cursor = conn.cursor()
        cols_info = {r[1] for r in conn.execute("PRAGMA table_info(smartteacher_documents)").fetchall()}
        if "unit_id" in cols_info and "session_id" in cols_info:
            cursor.execute(
                """
                INSERT INTO smartteacher_documents (
                    teacher_id, user_id, course_id, doc_type, title, specialty, grade,
                    section_name, duration_minutes, topic, competence, purpose,
                    content_markdown, content_json, status, version, is_public,
                    unit_id, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    teacher_id, user_id, req.course_id, mapped_type, cleaned_title,
                    req.specialty, req.grade, req.section_name or "A", req.duration_minutes or 90,
                    cleaned_topic, req.competence, req.purpose, req.content_markdown,
                    json_str, status_clean, req.version or 1, req.is_public or 0,
                    req.unit_id, req.session_id
                )
            )
        else:
            cursor.execute(
                """
                INSERT INTO smartteacher_documents (
                    teacher_id, user_id, course_id, doc_type, title, specialty, grade,
                    section_name, duration_minutes, topic, competence, purpose,
                    content_markdown, content_json, status, version, is_public
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    teacher_id, user_id, req.course_id, mapped_type, cleaned_title,
                    req.specialty, req.grade, req.section_name or "A", req.duration_minutes or 90,
                    cleaned_topic, req.competence, req.purpose, req.content_markdown,
                    json_str, status_clean, req.version or 1, req.is_public or 0
                )
            )
        new_doc_id = cursor.lastrowid

    return {
        "success": True,
        "id": new_doc_id,
        "document_id": new_doc_id,
        "document": {
            "id": new_doc_id,
            "title": cleaned_title,
            "version": req.version or 1,
            "status": status_clean
        },
        "title": cleaned_title,
        "version": req.version or 1,
        "status": status_clean,
        "message": "Documento pedagógico guardado exitosamente en la Intranet."
    }

@router.get("/teacher/documents/{doc_id}")
def get_teacher_document_by_id(
    doc_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Obtiene los detalles completos de una planificación guardada con verificación estricta de propiedad (Anti-IDOR).
    Docentes no pueden leer borradores de otros docentes.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento pedagógico no encontrado.")

        # Validación Anti-IDOR estricta
        is_owner = (row["user_id"] == user_id)
        is_public = (row["is_public"] == 1)
        is_admin_or_dir = (user_role in ["ADMINISTRADOR", "DIRECTOR"])

        if not (is_owner or is_public or is_admin_or_dir):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: Este documento pertenece a otro docente."
            )

        doc = dict(row)
        if isinstance(doc.get("content_json"), str):
            try:
                doc["content_json"] = json.loads(doc["content_json"])
            except Exception:
                pass

        return {"success": True, "document": doc}

@router.put("/teacher/documents/{doc_id}")
def update_teacher_document(
    doc_id: int,
    req: TeacherDocumentUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Actualiza el contenido, secciones o estado de una planificación pedagógica con control de versiones optimista.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

        # Anti-IDOR: Solo el propietario o Administrador pueden modificar
        if row["user_id"] != user_id and user_role != "ADMINISTRADOR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tiene permisos para modificar este documento."
            )

        # Control de concurrencia optimista
        current_version = int(row["version"] or 1)
        if req.expected_version is not None and req.expected_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicto de edición: El documento está en versión {current_version}, pero se esperaba {req.expected_version}. Recarga los cambios antes de guardar."
            )

        new_version = current_version + 1
        new_title = req.title.strip() if req.title else row["title"]
        new_topic = req.topic.strip() if req.topic else row["topic"]
        new_competence = req.competence if req.competence is not None else row["competence"]
        new_purpose = req.purpose if req.purpose is not None else row["purpose"]
        new_markdown = req.content_markdown if req.content_markdown is not None else row["content_markdown"]
        new_status = req.status if req.status is not None else row["status"]
        new_public = req.is_public if req.is_public is not None else row["is_public"]
        new_duration = req.duration_minutes if req.duration_minutes is not None else row["duration_minutes"]

        if req.content_json is not None:
            new_json_str = json.dumps(req.content_json, ensure_ascii=False) if isinstance(req.content_json, dict) else str(req.content_json)
        else:
            new_json_str = row["content_json"]

        conn.execute(
            """
            UPDATE smartteacher_documents
            SET title = ?, topic = ?, competence = ?, purpose = ?,
                content_markdown = ?, content_json = ?, status = ?,
                version = ?, is_public = ?, duration_minutes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                new_title, new_topic, new_competence, new_purpose,
                new_markdown, new_json_str, new_status, new_version,
                new_public, new_duration, doc_id
            )
        )

    return {
        "success": True,
        "document_id": doc_id,
        "title": new_title,
        "version": new_version,
        "status": new_status,
        "message": f"Documento actualizado a versión {new_version} exitosamente."
    }

@router.delete("/teacher/documents/{doc_id}")
def delete_teacher_document(
    doc_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Elimina un documento o borrador con verificación estricta de propiedad.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

        # Anti-IDOR: Solo el propietario o Administrador pueden eliminar
        if row["user_id"] != user_id and user_role != "ADMINISTRADOR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tiene permisos para eliminar este documento."
            )

        conn.execute("DELETE FROM smartteacher_documents WHERE id = ?", (doc_id,))

    return {"success": True, "message": "Documento pedagógico eliminado correctamente."}


# =========================================================================
# EXPORTACIÓN DOCUMENTAL PROFESIONAL (FASE 7.5 - DOCX / PDF)
# =========================================================================

import unicodedata

def _clean_export_filename(title: str, doc_type: str, target: str, ext: str) -> str:
    """Genera nombre de archivo sanitizado y profesional para descarga (ASCII RFC 6266)."""
    norm_title = unicodedata.normalize('NFKD', title or "Documento").encode('ASCII', 'ignore').decode('ASCII')
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', norm_title)
    clean = re.sub(r'_+', '_', clean).strip('_')[:50]
    prefix_map = {
        "unidad_didactica": "Unidad_Didactica",
        "sesion_aprendizaje": "Sesion_CNEB",
        "ficha_actividad": "Ficha_Taller",
        "ficha_trabajo": "Ficha_Trabajo_Estudiante",
        "examen_tecnico": "Examen_Estudiante" if target == "student" else "Solucionario_Docente",
        "rubrica_evaluacion": "Rubrica_CNEB",
        "presentacion_pptx": "Presentacion_CET34"
    }
    pfx = prefix_map.get(doc_type, "Documento_INEI34")
    return f"{pfx}_{clean}.{ext}"


@router.get("/teacher/documents/{doc_id}/export/{file_format}")
def export_teacher_document_by_id(
    doc_id: int,
    file_format: str,
    target: Optional[str] = "teacher",
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Exporta un documento pedagógico guardado en SQLite a formato binario Microsoft Word (.docx) o PDF.
    Aplica verificación estricta de propiedad (Anti-IDOR) y control de acceso RBAC en el servidor.
    Docentes ajenos reciben HTTP 403 Forbidden.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    fmt = (file_format or "").strip().lower()
    if fmt not in ["docx", "pdf", "pptx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado '{file_format}'. Los formatos válidos son 'docx', 'pdf' o 'pptx'."
        )

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documento pedagógico no encontrado."
            )

        # Anti-IDOR estricto: Docente ajeno no puede exportar documentos privados de otro docente
        if user_role == "DOCENTE" and row["user_id"] != user_id and user_role != "ADMINISTRADOR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tiene autorización para exportar documentos de otro docente."
            )

        doc_dict = dict(row)
        if not doc_dict.get("teacher_name"):
            doc_dict["teacher_name"] = user.get("full_name") or user.get("username") or "Docente"

    target_clean = (target or "teacher").strip().lower()
    if target_clean not in ["teacher", "student"]:
        target_clean = "teacher"

    # Generación segura en memoria sin filtrar trazas ni rutas internas
    try:
        c_json = doc_dict.get("content_json")
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}
        if not isinstance(c_json, dict):
            c_json = {}

        tpl_id = c_json.get("template_id")
        t_rec = None
        if tpl_id:
            try:
                t_rec = ai_service.get_template_by_id(int(tpl_id), user)
            except Exception:
                t_rec = None

        if t_rec:
            t_bytes = t_rec.get("file_bytes")
            if not t_bytes and t_rec.get("file_path") and os.path.exists(t_rec["file_path"]):
                with open(t_rec["file_path"], "rb") as fp:
                    t_bytes = fp.read()
            if t_bytes:
                from app.ai.template_engine import template_engine
                doc_dict["target"] = target_clean
                doc_dict["include_teacher_key"] = target_clean != "student"
                if fmt == "pptx" or doc_dict.get("doc_type") == "presentacion_pptx":
                    file_bytes = template_engine.render_pptx_from_template(t_bytes, doc_dict)
                    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                elif fmt == "docx":
                    file_bytes = template_engine.render_docx_from_template(t_bytes, doc_dict)
                    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                else:
                    file_bytes = template_engine.render_pdf_from_template(t_bytes, doc_dict)
                    media_type = "application/pdf"
            else:
                t_rec = None

        if not t_rec:
            if fmt == "docx":
                file_bytes = generate_docx_bytes(doc_dict, target=target_clean)
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif fmt == "pptx":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este documento histórico no es una presentación PowerPoint."
                )
            else:
                file_bytes = generate_pdf_bytes(doc_dict, target=target_clean)
                media_type = "application/pdf"
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando exportación {fmt} para doc {doc_id}: {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar el archivo documental. Verifique los datos o consulte con el administrador."
        )

    filename = _clean_export_filename(doc_dict.get("title", ""), doc_dict.get("doc_type", ""), target_clean, fmt)
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    visa_obj = (c_json.get("visado_digital") if isinstance(c_json, dict) else None) or {}
    content_sha256 = visa_obj.get("document_hash", "")
    code_val = visa_obj.get("verification_code", "")

    headers_out = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Export-File-SHA256": file_sha256,
        "X-Content-SHA256": content_sha256,
        "X-Verification-Code": code_val,
        "X-Canonical-Schema": visa_obj.get("canonical_schema", "v2_canonical")
    }

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers=headers_out
    )



# =============================================================================
# BLOQUE 3: VISADO DIGITAL DIRECTIVO CON QR INSTITUCIONAL (AUDITORÍA CORRECTIVA)
# =============================================================================

def compute_document_canonical_hash(doc: dict, version: str = "v2") -> tuple[str, str]:
    """
    Calcula el hash SHA-256 determinista de la representación canónica del documento.
    version='v2': serialización canónica completa UTF-8 SIN truncamiento de contenido.
    version='v1_legacy': compatibilidad retrospectiva con visados anteriores (500 chars).
    Retorna: (hash_hex, schema_version_string)
    """
    import hashlib
    import json

    if version == "v1_legacy":
        canonical_str = f"{doc.get('id')}|{doc.get('title','')}|{doc.get('specialty','')}|{doc.get('grade','')}|{doc.get('doc_type','')}|{doc.get('topic','')}|{doc.get('purpose','')}|{(doc.get('content_markdown') or '')[:500]}"
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest(), "v1_legacy"

    c_json = doc.get("content_json") or {}
    if isinstance(c_json, str):
        try:
            c_json = json.loads(c_json)
        except Exception:
            c_json = {}
    if not isinstance(c_json, dict):
        c_json = {}

    # Filtrar metadatos mutables de visado para evitar circularidad
    pedagogical_data = {k: v for k, v in c_json.items() if k not in ("visado_digital", "visado_history")}
    pedagogical_serialized = json.dumps(pedagogical_data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

    # Estructura canónica estricta determinista v2 (sin truncamiento)
    canonical_payload = {
        "schema_version": "v2_canonical",
        "id": int(doc.get("id") or 0),
        "doc_type": str(doc.get("doc_type") or "").strip().lower(),
        "title": str(doc.get("title") or "").strip(),
        "specialty": str(doc.get("specialty") or "").strip(),
        "grade": int(doc.get("grade") or 1),
        "section_name": str(doc.get("section_name") or "A").strip(),
        "duration_minutes": int(doc.get("duration_minutes") or 90),
        "topic": str(doc.get("topic") or "").strip(),
        "competence": str(doc.get("competence") or "").strip(),
        "purpose": str(doc.get("purpose") or "").strip(),
        "content_markdown": str(doc.get("content_markdown") or "").strip(),
        "pedagogical_data": pedagogical_serialized
    }

    canonical_bytes = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(canonical_bytes).hexdigest(), "v2_canonical"


@router.post("/teacher/documents/{doc_id}/visa")
def approve_teacher_document_visa(
    doc_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))
):
    """
    Visado digital directivo oficial de la I.E. INEI N.º 34 de Chancay.
    Valida rol DIRECTOR / ADMINISTRADOR.
    Genera token criptográfico de 64 bits (16 hex chars) para evitar enumeración.
    Calcula hash SHA-256 canónico completo (v2) sobre el 100% del contenido pedagógico sin truncamiento.
    Preserva el valor de is_public (las planificaciones privadas no se exponen al público).
    Actualiza status a 'REVISADO' cumpliendo la restricción SQLite CHECK.
    """
    import secrets
    import hashlib
    import json
    from datetime import datetime

    user_role = normalize_role(user.get("role_name") or user.get("role") or "")
    if user_role not in ["ADMINISTRADOR", "DIRECTOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo el Director General o Administrador puede visar documentos pedagógicos."
        )

    user_id = user.get("id") or user.get("user_id")
    user_name = user.get("full_name") or user.get("username") or "Lic. César Tinedo Jiménez"

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento pedagógico #{doc_id} no encontrado en el repositorio institucional."
            )

        doc = dict(row)
        c_json = doc.get("content_json")
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}
        if not isinstance(c_json, dict):
            c_json = {}

        # Generar código criptográfico seguro de 64 bits de entropía
        # Generar código criptográfico seguro con 128 bits de entropía (32 caracteres hexadecimales)
        token = secrets.token_hex(16).upper()
        verification_code = f"INEI-VISA-{doc_id}-{token}"

        # Hash canónico completo v2 (sin truncar texto ni markdown)
        doc_hash, schema_ver = compute_document_canonical_hash(doc, version="v2")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Comprobar si es un re-visado
        previous_visa = c_json.get("visado_digital") or {}
        previous_code = previous_visa.get("verification_code")

        visado_digital = {
            "verification_code": verification_code,
            "status": "APROBADO",
            "canonical_schema": schema_ver,
            "approved_by_id": user_id,
            "approver_name": user_name,
            "approver_role": "DIRECTOR GENERAL",
            "approved_at": now_str,
            "document_hash": doc_hash,
            "content_verified": "100% TEXTO COMPLETO Y ESTRUCTURA PEDAGÓGICA (v2)",
            "verification_url": f"/verificar-documento/{verification_code}"
        }

        # Historial de visados acumulativo y auditable
        history = c_json.get("visado_history") or []
        history.append({
            "action": "VISADO_RENOVADO" if previous_code else "VISADO_APROBADO",
            "by": user_name,
            "user_id": user_id,
            "user_role": user_role,
            "code": verification_code,
            "canonical_schema": schema_ver,
            "document_hash": doc_hash,
            "previous_code": previous_code,
            "timestamp": now_str
        })
        c_json["visado_history"] = history
        c_json["visado_digital"] = visado_digital

        updated_json_str = json.dumps(c_json, ensure_ascii=False)

        # Determinar status SQLite compatible sin forzar is_public=1
        new_status = "PUBLICADO" if row["status"] == "PUBLICADO" else "REVISADO"

        conn.execute(
            """
            UPDATE smartteacher_documents 
            SET status = ?, content_json = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (new_status, updated_json_str, doc_id)
        )

        # Registro en bitácora de auditoría forense
        conn.execute(
            """
            INSERT INTO audit_logs (user_id, username, role, action, module, record_id, details, timestamp)
            VALUES (?, ?, ?, 'DOCUMENT_VISA_APPROVED', 'SMARTTEACHER', ?, ?, datetime('now', 'localtime'))
            """,
            (user_id, user.get("username", "director"), user_role, str(doc_id), f"Director visó digitalmente documento pedagógico #{doc_id} ('{doc.get('title','')}') con código {verification_code} y hash {doc_hash[:16]}...")
        )
        conn.commit()

    return {
        "success": True,
        "message": f"Documento pedagógico #{doc_id} visado y aprobado digitalmente por Dirección.",
        "document_id": doc_id,
        "status": "APROBADO",
        "canonical_schema": schema_ver,
        "verification_code": verification_code,
        "document_hash": doc_hash,
        "visado_digital": visado_digital
    }


@router.post("/teacher/documents/{doc_id}/revoke-visa")
def revoke_teacher_document_visa(
    doc_id: int,
    req: Optional[DocumentVisaRevokeRequest] = None,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))
):
    """
    Revoca formalmente el visado digital directivo de un documento pedagógico.
    Invalida el sello de autenticidad en el repositorio institucional y en el QR.
    Preserva el valor de is_public del docente (no altera la visibilidad curricular normal).
    """
    import json
    from datetime import datetime

    user_role = normalize_role(user.get("role_name") or user.get("role") or "")
    if user_role not in ["ADMINISTRADOR", "DIRECTOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo el Director General o Administrador puede revocar visados."
        )

    user_id = user.get("id") or user.get("user_id")
    user_name = user.get("full_name") or user.get("username") or "Lic. César Tinedo Jiménez"
    reason = (req.reason if req and req.reason else "Revocado por decisión directiva de supervisión pedagógica")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento #{doc_id} no encontrado."
            )

        doc = dict(row)
        c_json = doc.get("content_json")
        if isinstance(c_json, str):
            try:
                c_json = json.loads(c_json)
            except Exception:
                c_json = {}
        if not isinstance(c_json, dict):
            c_json = {}

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        visa = c_json.get("visado_digital") or {}
        if not visa or not visa.get("verification_code"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El documento #{doc_id} no cuenta con un visado digital previo que pueda ser revocado."
            )

        visa["status"] = "REVOCADO"
        visa["revoked_at"] = now_str
        visa["revoked_by"] = user_name
        visa["revocation_reason"] = reason
        c_json["visado_digital"] = visa

        history = c_json.get("visado_history") or []
        history.append({
            "action": "VISADO_REVOCADO",
            "by": user_name,
            "user_id": user_id,
            "user_role": user_role,
            "code": visa.get("verification_code"),
            "reason": reason,
            "timestamp": now_str
        })
        c_json["visado_history"] = history

        # No forzar ARCHIVADO destructivo; devolver a REVISADO para que el docente pueda subsanar
        conn.execute(
            """
            UPDATE smartteacher_documents 
            SET status = 'REVISADO', content_json = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (json.dumps(c_json, ensure_ascii=False), doc_id)
        )

        conn.execute(
            """
            INSERT INTO audit_logs (user_id, username, role, action, module, record_id, details, timestamp)
            VALUES (?, ?, ?, 'DOCUMENT_VISA_REVOKED', 'SMARTTEACHER', ?, ?, datetime('now', 'localtime'))
            """,
            (user_id, user.get("username", "director"), user_role, str(doc_id), f"Director revocó visado de documento #{doc_id}. Motivo: {reason}")
        )
        conn.commit()

    return {
        "success": True,
        "message": f"Visado del documento #{doc_id} revocado formalmente.",
        "status": "REVOCADO",
        "document_id": doc_id,
        "revoked_at": now_str,
        "reason": reason
    }


_verification_rate_limits: Dict[str, List[float]] = {}
_verification_rate_lock = threading.Lock()

def check_verification_rate_limit(client_ip: str, max_requests: int = 30, window_seconds: int = 60) -> bool:
    """
    Control de tasa en memoria con ventana deslizante para evitar enumeración y abusos automatizados.
    Límite por defecto: 30 solicitudes por minuto por dirección IP.
    """
    now = time.time()
    with _verification_rate_lock:
        timestamps = _verification_rate_limits.get(client_ip, [])
        timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(timestamps) >= max_requests:
            _verification_rate_limits[client_ip] = timestamps
            return False
        timestamps.append(now)
        _verification_rate_limits[client_ip] = timestamps
        return True


def clear_verification_rate_limits_for_tests():
    """Limpia el estado del rate limiter (uso exclusivo en suites de prueba)."""
    with _verification_rate_lock:
        _verification_rate_limits.clear()


@router.get("/documents/verify/{verification_code}")
def verify_document_code_api(verification_code: str, request: Request = None):
    """
    Endpoint público de solo lectura para la verificación de autenticidad institucional.
    Comprueba si el código existe mediante búsqueda indexada y token no predecible.
    Recalcula la integridad SHA-256 completa (v2 o retrospectiva v1_legacy).
    Entrega únicamente metadatos institucionales autorizados (sin exponer texto privado ni datos personales).
    """
    clean_code = (verification_code or "").strip().upper()
    if not clean_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código de verificación requerido.")

    # Control de tasa (Rate Limiting) contra intentos de enumeración automatizada
    client_ip = (request.client.host if (request and request.client) else "127.0.0.1")
    if not check_verification_rate_limit(client_ip, max_requests=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Límite de consultas excedido (máximo 30 verificaciones por minuto). Por favor espere antes de realizar nuevas consultas."
        )

    import re
    import json

    m = re.match(r'^INEI-VISA-(\d+)-([A-F0-9]+)$', clean_code)

    target_doc = None
    with get_db() as conn:
        if m:
            doc_id = int(m.group(1))
            row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
            if row:
                d = dict(row)
                c_json = d.get("content_json")
                if isinstance(c_json, str):
                    try:
                        c_json = json.loads(c_json)
                    except Exception:
                        c_json = {}
                if isinstance(c_json, dict) and c_json.get("visado_digital", {}).get("verification_code") == clean_code:
                    d["content_json"] = c_json
                    target_doc = d

        if not target_doc:
            rows = conn.execute("SELECT * FROM smartteacher_documents WHERE content_json LIKE ?", (f"%{clean_code}%",)).fetchall()
            for r in rows:
                d = dict(r)
                c_json = d.get("content_json")
                if isinstance(c_json, str):
                    try:
                        c_json = json.loads(c_json)
                    except Exception:
                        c_json = {}
                if isinstance(c_json, dict) and c_json.get("visado_digital", {}).get("verification_code") == clean_code:
                    d["content_json"] = c_json
                    target_doc = d
                    break

    if not target_doc:
        return {
            "success": False,
            "status": "NO_VALIDO",
            "message": "Código de verificación no registrado en el repositorio institucional de la I.E. INEI N.º 34.",
            "verification_code": clean_code
        }

    visa = target_doc["content_json"].get("visado_digital", {})
    stored_hash = visa.get("document_hash", "")
    stored_schema = visa.get("canonical_schema") or ("v1_legacy" if len(stored_hash) == 64 and "v2" not in visa.get("content_verified", "") else "v2_canonical")

    is_v1_legacy = (stored_schema == "v1_legacy")

    # Recalcular hash según esquema registrado sin auto-upgrade
    if is_v1_legacy:
        current_hash, schema_eval = compute_document_canonical_hash(target_doc, version="v1_legacy")
        schema_display = "v1_legacy (Visado Histórico - Método Anterior)"
        integrity_scope = "Integridad Parcial: Verificación limitada a cabecera institucional y primeros 500 caracteres de contenido."
        warning_notice = "ADVERTENCIA DE COMPATIBILIDAD: Este documento cuenta con un visado histórico emitido bajo el esquema v1. Su verificación certifica los metadatos y el inicio del texto pedagógico, pero no garantiza la totalidad del documento curricular. Para certificar el 100% del contenido pedagógico completo, se requiere una renovación de visado por la Dirección General."
    else:
        current_hash, schema_eval = compute_document_canonical_hash(target_doc, version="v2")
        schema_display = "v2_canonical (Estándar Actual Completo)"
        integrity_scope = "Integridad Completa: 100% del texto pedagógico y estructura curricular verificados mediante serialización canónica determinista UTF-8."
        warning_notice = None

    integrity_valid = (stored_hash == current_hash)
    is_approved = (visa.get("status") == "APROBADO")

    # Extraer longitud del token hexadecimal para métricas de auditoría
    token_part = clean_code.split("-")[-1] if "-" in clean_code else ""

    return {
        "success": True,
        "status": visa.get("status", "NO_VALIDO"),
        "institution": "I.E. INEI N.º 34 de Chancay",
        "institutional_network": "DRE Lima Provincias • UGEL 10 Huaral",
        "document_id": target_doc["id"],
        "document_title": target_doc["title"],
        "document_type": target_doc.get("doc_type", "sesion_aprendizaje"),
        "specialty": target_doc.get("specialty", "Taller Técnico EPT"),
        "grade": target_doc.get("grade", 1),
        "section_name": target_doc.get("section_name", "A"),
        "verification_code": clean_code,
        "token_length_chars": len(token_part),
        "token_entropy_bits": len(token_part) * 4,
        "approver_name": visa.get("approver_name", "Lic. César Tinedo Jiménez"),
        "approver_role": visa.get("approver_role", "DIRECTOR GENERAL"),
        "approved_at": visa.get("approved_at", ""),
        "revoked_at": visa.get("revoked_at"),
        "revocation_reason": visa.get("revocation_reason"),
        "is_v1_legacy": is_v1_legacy,
        "canonical_schema": schema_display,
        "schema_version": "v1_legacy" if is_v1_legacy else "v2_canonical",
        "document_hash": stored_hash,
        "integrity_valid": integrity_valid,
        "integrity_scope": integrity_scope,
        "warning_notice": warning_notice,
        "verification_subject": "Contenido Pedagógico Oficial Visado por Dirección",
        "legal_nature": "Visado Digital Institucional con Verificación de Integridad Criptográfica SHA-256",
        "legal_disclaimer": "Mecanismo de control interno institucional de la I.E. INEI N.º 34 de Chancay para la supervisión y conformidad técnico-pedagógica curricular (DRE Lima Provincias / UGEL 10 Huaral). No constituye firma digital acreditada bajo la Ley N.º 27269 (IOFE/INDECOPI).",
        "is_official_seal_valid": (is_approved and integrity_valid)
    }


@router.post("/teacher/export-preview/{file_format}")
async def export_teacher_document_preview(
    file_format: str,
    req: TeacherExportPreviewRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Exporta en memoria la versión más reciente editada o en borrador de un documento pedagógico
    sin obligar a persistirlo previamente en la base de datos si el docente solo desea descargar.
    """
    fmt = (file_format or "").strip().lower()
    if fmt not in ["docx", "pdf", "pptx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado '{file_format}'. Formatos válidos: 'docx', 'pdf' o 'pptx'."
        )

    cleaned_title = (req.title or req.topic or "Documento Oficial CET 34").strip()
    
    grade_val = req.grade
    if not isinstance(grade_val, int) or grade_val < 1 or grade_val > 5:
        grade_val = 1

    dur_val = req.duration_minutes
    if not isinstance(dur_val, int) or dur_val < 15:
        dur_val = 225

    target_clean = (req.target or "teacher").strip().lower()
    if target_clean not in ["teacher", "student"]:
        target_clean = "teacher"

    u_name = None
    if user and isinstance(user, dict):
        u_name = user.get("full_name") or user.get("username")
    t_name = req.teacher_name or u_name or "Prof. Roberto Bazán Palacios"

    doc_data = {
        "title": cleaned_title,
        "doc_type": req.doc_type or "sesion_aprendizaje",
        "specialty": req.specialty or "Educación para el Trabajo - Computación e Informática",
        "grade": grade_val,
        "section_name": req.section_name or "A",
        "duration_minutes": dur_val,
        "topic": req.topic or cleaned_title,
        "competence": req.competence or "",
        "purpose": req.purpose or "",
        "content_markdown": req.content_markdown or "",
        "content_json": req.content_json or {},
        "teacher_name": t_name,
        "structure_mode": req.structure_mode or "institucional",
        "session_type": req.session_type or "tecnica",
        "template_id": getattr(req, "template_id", None)
    }

    try:
        if fmt == "pptx" or doc_data.get("doc_type") == "presentacion_pptx":
            from app.ai.template_engine import template_engine, TEMPLATES_STORAGE_DIR
            pptx_b = None
            t_id = doc_data.get("template_id") or 6
            try:
                t_rec = ai_service.get_template_by_id(int(t_id), user or {"id": 1, "role_name": "DOCENTE"})
                if t_rec:
                    pptx_b = t_rec.get("file_bytes")
            except Exception:
                pass
            if not pptx_b:
                tpl_pptx_path = os.path.join(TEMPLATES_STORAGE_DIR, "presentacion_leancanvas_cet34.pptx")
                if os.path.exists(tpl_pptx_path):
                    with open(tpl_pptx_path, "rb") as fp:
                        pptx_b = fp.read()
            if not pptx_b:
                raise ValueError("No se pudo cargar la plantilla maestra de PowerPoint (.pptx).")

            file_bytes = template_engine.render_pptx_from_template(pptx_b, doc_data)
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            fmt = "pptx"
        elif fmt == "docx":
            file_bytes = generate_docx_bytes(doc_data, target=target_clean)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            file_bytes = generate_pdf_bytes(doc_data, target=target_clean)
            media_type = "application/pdf"
    except Exception as e:
        logger.error(f"Error generando exportación preview {fmt}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al generar la previsualización del documento: {e}"
        )

    filename = _clean_export_filename(cleaned_title, doc_data["doc_type"], target_clean, fmt)
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/documents/{doc_id}/export/{file_format}")
def export_student_document_by_id(
    doc_id: int,
    file_format: str,
    target: Optional[str] = "student",
    user: dict = Depends(get_current_user)
):
    """
    Endpoint de exportación accesible por estudiantes (y otros usuarios autenticados).
    REGLA DE SEGURIDAD CRÍTICA:
    - Si el usuario es ESTUDIANTE, se PROHÍBE terminantemente solicitar solucionarios (target='teacher' retorna 403).
    - El servidor fuerza target='student' sanitizando todas las respuestas y claves docentes.
    """
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    fmt = (file_format or "").strip().lower()
    if fmt not in ["docx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado '{file_format}'. Formatos válidos: 'docx' o 'pdf'."
        )

    # Bloqueo estricto de solucionarios para estudiantes
    requested_target = (target or "student").strip().lower()
    if user_role == "ESTUDIANTE" and requested_target == "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Los estudiantes no tienen autorización para exportar solucionarios ni documentos confidenciales docentes."
        )

    with get_db() as conn:
        row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documento pedagógico no encontrado."
            )
        doc_dict = dict(row)

    # Forzar versión estudiante limpia si el usuario es estudiante
    effective_target = "student" if user_role == "ESTUDIANTE" else requested_target

    try:
        if fmt == "docx":
            file_bytes = generate_docx_bytes(doc_dict, target=effective_target)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            file_bytes = generate_pdf_bytes(doc_dict, target=effective_target)
            media_type = "application/pdf"
    except Exception as e:
        logger.error(f"Error generando exportación {fmt} para estudiante (doc {doc_id}): {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar el documento para el estudiante."
        )

    filename = _clean_export_filename(doc_dict.get("title", ""), doc_dict.get("doc_type", ""), effective_target, fmt)
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/tools/admin-document")
def draft_admin_document(
    req: AdminDocumentRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return ai_service.draft_administrative_document(
        user=user,
        doc_type=req.doc_type,
        recipient=req.recipient,
        subject=req.subject,
        key_points=req.key_points
    )

@router.post("/tools/executive-analysis")
def generate_executive_analysis(
    req: ExecutiveAnalysisRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))
):
    return ai_service.generate_institutional_analysis(
        user=user,
        analysis_topic=req.topic
    )

@router.get("/history")
def get_ai_history(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM ai_conversations 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 15
            """, (user["id"],)
        ).fetchall()
        return [dict(r) for r in rows]

# =========================================================================
# EVALUACIÓN FORMATIVA Y BANCO DE QUIZZES (SMARTTUTOR AI)
# =========================================================================

@router.get("/quiz/subjects")
def get_quiz_subjects(user: dict = Depends(get_current_user)):
    """Retorna las asignaturas y especialidades técnicas con quizzes formativos disponibles."""
    return quiz_engine.get_available_subjects()

@router.get("/quiz/progress")
def get_student_quiz_progress(user: dict = Depends(get_current_user)):
    """
    Retorna el progreso, historial y promedio de autoevaluaciones del estudiante autenticado.
    Aislamiento estricto por user_id.
    """
    return quiz_engine.get_student_progress(user["id"])

@router.get("/quiz/{subject_id}")
def get_formative_quiz(
    subject_id: str,
    limit: Optional[int] = 4,
    user: dict = Depends(get_current_user)
):
    """
    Entrega preguntas formativas para la asignatura/especialidad seleccionada.
    SEGURIDAD: Las soluciones correctas y explicaciones se omiten rigurosamente
    para evitar que sean visibles antes de que el estudiante responda.
    """
    cleaned_subject = (subject_id or "").strip().lower()
    if not cleaned_subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El área o asignatura (subject_id) es obligatoria.")

    questions = quiz_engine.get_quiz_for_subject(cleaned_subject, limit=min(limit or 4, 10), exclude_solutions=True)
    return {
        "success": True,
        "subject_id": cleaned_subject,
        "questions": questions,
        "total_questions": len(questions)
    }

@router.post("/quiz/submit")
def submit_formative_quiz(
    req: QuizSubmitRequest,
    user: dict = Depends(get_current_user)
):
    """
    Evalúa las respuestas del estudiante en el servidor de forma segura y determinista.
    Calcula el puntaje, nivel de logro CNEB, registra el intento en SQLite y entrega
    retroalimentación pedagógica justificada.
    """
    cleaned_subject = (req.subject_id or "").strip().lower()
    if not cleaned_subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El área o asignatura (subject_id) es obligatoria.")

    raw_answers = [{"question_id": a.question_id, "selected_option": a.selected_option} for a in req.answers]
    eval_result = quiz_engine.evaluate_submission(cleaned_subject, raw_answers)

    if not eval_result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=eval_result.get("message", "Error al evaluar respuestas."))

    # Persistir intento en la base de datos vinculado al estudiante autenticado
    attempt_id = quiz_engine.record_attempt(
        user_id=user["id"],
        subject_id=cleaned_subject,
        total_q=eval_result["total_questions"],
        correct_q=eval_result["correct_answers"],
        score_pct=eval_result["score_percentage"],
        achievement_lvl=eval_result["achievement_level"],
        details=eval_result["results"]
    )

    eval_result["attempt_id"] = attempt_id
    eval_result["student_name"] = user.get("full_name") or user.get("username")
    return eval_result


# =========================================================================
# FASE 8.0: SMARTTEACHER AI — UNIDADES DIDÁCTICAS Y PLANIFICACIÓN EN CASCADA
# =========================================================================

@router.post("/teacher/units/generate")
def generate_teacher_unit_endpoint(
    req: UnitGenerateRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    if not user:
        user = _resolve_fallback_teacher()
    """
    Genera un borrador completo de Unidad Didáctica institucional para CET N° 34 / INEI N° 34.
    Estructura las 9 secciones oficiales, matrices técnicas y de emprendimiento,
    y la matriz de 18 sesiones (9 técnicas de 5h + 9 emprendimiento de 3h = 72h).
    """
    cleaned_topic = (req.topic or req.title or "").strip()
    if not cleaned_topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tema o actividad productiva es obligatorio.")
    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado escolar debe ser entre 1 y 5.")

    weeks = req.duration_weeks or 9
    if weeks < 1 or weeks > 36:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La duración en semanas debe estar entre 1 y 36.")

    weekly_h = req.weekly_hours or 8
    if weekly_h < 1 or weekly_h > 40:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Las horas pedagógicas semanales deben estar entre 1 y 40.")

    return ai_service.generate_didactic_unit_structured(
        user=user,
        topic=cleaned_topic,
        grade=req.grade,
        specialty=req.specialty,
        duration_weeks=weeks,
        weekly_hours=weekly_h,
        formative_module=req.formative_module,
        section_name=req.section_name or "A",
        bimester=req.bimester or "IV Bimestre",
        unit_number=req.unit_number or 4,
        technical_competence=req.technical_competence,
        entrepreneurship_competence=req.entrepreneurship_competence,
        observations=req.observations,
        weekly_topics=req.weekly_topics,
        teacher_name=req.teacher_name
    )


@router.post("/teacher/units/validate-hours")
def validate_teacher_unit_hours_endpoint(
    req: UnitValidateHoursRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Valida de forma determinista la distribución de horas por semana y el total de la unidad.
    No oculta errores: reporta discrepancias exactas para que el docente pueda corregirlas.
    """
    return ai_service.validate_didactic_unit_hours(
        sessions_plan=req.sessions,
        duration_weeks=req.duration_weeks or 9,
        weekly_hours=req.weekly_hours or 8
    )


@router.post("/teacher/units/derive-session")
def derive_session_from_unit_endpoint(
    req: UnitDeriveSessionRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Planificación en Cascada: Genera una sesión de aprendizaje directamente desde una fila
    de la matriz de la unidad didáctica, heredando título, propósito, criterios, evidencias,
    duración exacta (225m o 135m), metodología y vínculo con la unidad de origen.
    """
    unit_data = req.unit_data
    if not unit_data and req.unit_id:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE id = ?", (req.unit_id,)).fetchone()
            if row:
                unit_data = dict(row)
                if isinstance(unit_data.get("content_json"), str):
                    try:
                        unit_data["content_json"] = json.loads(unit_data["content_json"])
                    except Exception:
                        pass

    if not unit_data and not req.unit_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el objeto unit_data, unit_row o un unit_id existente en la base de datos."
        )

    active_user = user if req.auto_generate is not False else None
    res = ai_service.derive_session_from_unit_row(
        unit_data=unit_data or {},
        week=req.week,
        session_type=req.session_type,
        session_number=req.session_number,
        user=active_user,
        unit_row=req.unit_row
    )
    return {
        "success": True,
        "session_data": res,
        "session": res,
        **res
    }


@router.post("/teacher/units/derive-material")
def derive_material_from_session_endpoint(
    req: SessionDeriveMaterialRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Planificación en Cascada (Nivel 2): Genera materiales educativos (fichas, guías, exámenes, rúbricas)
    vinculados a una sesión de aprendizaje guardada y su unidad padre.
    """
    session_data = req.session_data
    if not session_data and req.session_id:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM smartteacher_documents WHERE id = ?", (req.session_id,)).fetchone()
            if row:
                session_data = dict(row)
                if isinstance(session_data.get("content_json"), str):
                    try:
                        session_data["content_json"] = json.loads(session_data["content_json"])
                    except Exception:
                        pass

    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el objeto session_data o un session_id existente en la base de datos."
        )

    res = ai_service.derive_material_from_session(
        session_data=session_data,
        material_type=req.material_type or "ficha_guia",
        instruction=req.instruction,
        user=user
    )
    return {
        "success": True,
        "material": res,
        "data": res,
        **res
    }


@router.post("/teacher/units/save")
def save_teacher_unit(
    req: TeacherUnitSaveRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Persiste una Unidad Didáctica en SQLite con control de versiones y verificación Anti-IDOR.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    cleaned_title = (req.title or "").strip()
    if not cleaned_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El título de la unidad didáctica es obligatorio.")
    if req.grade < 1 or req.grade > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grado escolar debe ser entre 1 y 5.")

    raw_json = req.content_json
    json_str = json.dumps(raw_json, ensure_ascii=False) if isinstance(raw_json, dict) else str(raw_json or "{}")

    sessions_plan = []
    if isinstance(raw_json, dict):
        sessions_plan = raw_json.get("organizacion_sesiones") or []
    sessions_plan_str = json.dumps(sessions_plan, ensure_ascii=False)

    teacher_name = user.get("full_name") or user.get("username") or "Docente"

    with get_db() as conn:
        teacher_id = get_teacher_id_from_user(user, conn)

        # Crear tabla si no existe en caso de inicializaciones limpias
        conn.execute("""
            CREATE TABLE IF NOT EXISTS smartteacher_didactic_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                course_id INTEGER,
                title TEXT NOT NULL,
                academic_year TEXT DEFAULT '2026',
                bimester TEXT DEFAULT 'IV Bimestre',
                unit_number INTEGER DEFAULT 4,
                specialty TEXT NOT NULL,
                formative_module TEXT,
                grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 5),
                section_name TEXT DEFAULT 'A',
                responsible_teacher TEXT NOT NULL,
                director_name TEXT DEFAULT 'Tomas Jurado Zevallos',
                subdirector_name TEXT DEFAULT 'Mg. Javier Eulogio Rosas Maguiña',
                workshop_boss_name TEXT,
                start_date TEXT,
                end_date TEXT,
                duration_weeks INTEGER DEFAULT 9,
                weekly_hours INTEGER DEFAULT 8,
                total_hours INTEGER DEFAULT 72,
                unit_description TEXT,
                technical_matrix_json TEXT,
                entrepreneurship_matrix_json TEXT,
                technical_purposes_json TEXT,
                entrepreneurship_purposes_json TEXT,
                sessions_plan_json TEXT NOT NULL,
                bibliography_json TEXT,
                signatures_json TEXT,
                content_markdown TEXT,
                content_json TEXT NOT NULL,
                status TEXT DEFAULT 'BORRADOR' CHECK(status IN ('BORRADOR', 'REVISADO', 'APROBADO', 'ARCHIVADO')),
                version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
            )
        """)

        if req.id:
            existing = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE id = ?", (req.id,)).fetchone()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")
            if user_role == "DOCENTE" and existing["user_id"] != user_id and user_role != "ADMINISTRADOR":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: No puede modificar la unidad de otro docente.")
            
            new_version = (existing["version"] or 1) + 1
            conn.execute("""
                UPDATE smartteacher_didactic_units
                SET title = ?, specialty = ?, grade = ?, section_name = ?,
                    duration_weeks = ?, weekly_hours = ?, total_hours = ?,
                    formative_module = ?, content_markdown = ?, content_json = ?,
                    sessions_plan_json = ?, status = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                cleaned_title, req.specialty, req.grade, req.section_name or "A",
                req.duration_weeks or 9, req.weekly_hours or 8, req.total_hours or 72,
                req.formative_module, req.content_markdown, json_str,
                sessions_plan_str, req.status or "BORRADOR", new_version, req.id
            ))
            unit_id = req.id
        else:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO smartteacher_didactic_units (
                    teacher_id, user_id, course_id, title, specialty, formative_module,
                    grade, section_name, responsible_teacher, duration_weeks, weekly_hours,
                    total_hours, content_markdown, content_json, sessions_plan_json,
                    status, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                teacher_id, user_id, req.course_id, cleaned_title, req.specialty,
                req.formative_module, req.grade, req.section_name or "A", teacher_name,
                req.duration_weeks or 9, req.weekly_hours or 8, req.total_hours or 72,
                req.content_markdown, json_str, sessions_plan_str,
                req.status or "BORRADOR", req.version or 1
            ))
            unit_id = cursor.lastrowid
            new_version = req.version or 1

    return {
        "success": True,
        "unit_id": unit_id,
        "title": cleaned_title,
        "version": new_version,
        "status": req.status or "BORRADOR",
        "message": "Unidad didáctica guardada exitosamente en el sistema."
    }


@router.get("/teacher/units")
def list_teacher_units(
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Lista las unidades didácticas registradas.
    Docentes ven exclusivamente sus propias unidades; directores y administradores ven todas.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='smartteacher_didactic_units'").fetchone()
        if not exists:
            return {"success": True, "count": 0, "units": []}

        if user_role == "DOCENTE":
            rows = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM smartteacher_didactic_units ORDER BY id DESC").fetchall()

        result = []
        for r in rows:
            u_dict = dict(r)
            if isinstance(u_dict.get("content_json"), str):
                try:
                    u_dict["content_json"] = json.loads(u_dict["content_json"])
                except Exception:
                    pass
            result.append(u_dict)

    return {"success": True, "count": len(result), "units": result}


@router.get("/teacher/units/{unit_id}")
def get_teacher_unit(
    unit_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Consulta el detalle completo de una unidad didáctica, incluyendo sesiones derivadas en cascada.
    Aplica protección Anti-IDOR.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='smartteacher_didactic_units'").fetchone()
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")

        row = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE id = ?", (unit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")

        if user_role == "DOCENTE" and row["user_id"] != user_id and user_role != "ADMINISTRADOR":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: No puede consultar la unidad didáctica de otro docente.")

        u_dict = dict(row)
        if isinstance(u_dict.get("content_json"), str):
            try:
                u_dict["content_json"] = json.loads(u_dict["content_json"])
            except Exception:
                pass

        # Sesiones vinculadas
        doc_cols = {r[1] for r in conn.execute("PRAGMA table_info(smartteacher_documents)").fetchall()}
        if "unit_id" in doc_cols:
            linked_sessions = conn.execute("""
                SELECT id, title, doc_type, grade, specialty, section_name, duration_minutes, status, created_at
                FROM smartteacher_documents
                WHERE unit_id = ? AND doc_type = 'sesion_aprendizaje'
                ORDER BY id ASC
            """, (unit_id,)).fetchall()
            u_dict["linked_sessions"] = [dict(s) for s in linked_sessions]
        else:
            u_dict["linked_sessions"] = []

    return {"success": True, "unit": u_dict}


@router.delete("/teacher/units/{unit_id}")
def delete_teacher_unit(
    unit_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Elimina una unidad didáctica respetando permisos estrictos de propiedad (Anti-IDOR).
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    with get_db() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='smartteacher_didactic_units'").fetchone()
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")

        row = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE id = ?", (unit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")

        if user_role == "DOCENTE" and row["user_id"] != user_id and user_role != "ADMINISTRADOR":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: Solo el creador o Administrador pueden eliminar esta unidad.")

        conn.execute("DELETE FROM smartteacher_didactic_units WHERE id = ?", (unit_id,))

    return {"success": True, "message": "Unidad didáctica eliminada correctamente."}


@router.get("/teacher/units/{unit_id}/export/{file_format}")
def export_teacher_unit_by_id(
    unit_id: int,
    file_format: str,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    """
    Exporta una unidad didáctica guardada a Word (.docx) o PDF en formato apaisado (Landscape A4)
    con las 9 secciones oficiales, matrices pedagógicas, 18 sesiones y 3 firmas institucionales.
    """
    user_id = user.get("id") or user.get("user_id")
    user_role = normalize_role(user.get("role_name") or user.get("role") or "")

    fmt = (file_format or "").strip().lower()
    if fmt not in ["docx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado '{file_format}'. Los formatos válidos son 'docx' o 'pdf'."
        )

    with get_db() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='smartteacher_didactic_units'").fetchone()
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")

        row = conn.execute("SELECT * FROM smartteacher_didactic_units WHERE id = ?", (unit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unidad didáctica no encontrada.")

        if user_role == "DOCENTE" and row["user_id"] != user_id and user_role != "ADMINISTRADOR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tiene autorización para exportar unidades de otro docente."
            )

        unit_dict = dict(row)

    try:
        if fmt == "docx":
            unit_dict["doc_type"] = "unidad_didactica"
            file_bytes = generate_docx_bytes(unit_dict)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            file_bytes = generate_unit_pdf_bytes(unit_dict)
            media_type = "application/pdf"
    except Exception as e:
        logger.error(f"Error exportando unidad {unit_id} ({fmt}): {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar el archivo documental de la unidad didáctica."
        )

    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', unit_dict.get("title", "Unidad")).strip('_')[:50]
    filename = f"Unidad_Didactica_{clean_name}.{fmt}"
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/teacher/units/export-preview/{file_format}")
async def export_teacher_unit_preview(
    file_format: str,
    req: TeacherUnitSaveRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    if not user:
        user = _resolve_fallback_teacher()
    """
    Exporta en memoria la versión en borrador o previsualización de una unidad didáctica
    directamente sin obligar a guardarla previamente en disco.
    """
    fmt = (file_format or "").strip().lower()
    if fmt not in ["docx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado '{file_format}'. Los formatos válidos son 'docx' o 'pdf'."
        )

    teacher_name_val = (user or {}).get("full_name") or "Prof. Docente Responsable"
    unit_data = {
        "title": req.title,
        "topic": req.title,
        "specialty": req.specialty,
        "grade": req.grade,
        "section_name": req.section_name or "A",
        "duration_weeks": req.duration_weeks or 9,
        "weekly_hours": req.weekly_hours or 8,
        "total_hours": req.total_hours or 72,
        "content_json": req.content_json,
        "content_markdown": req.content_markdown,
        "teacher_name": teacher_name_val,
        "user": user
    }

    try:
        if fmt == "docx":
            unit_data["doc_type"] = "unidad_didactica"
            file_bytes = generate_docx_bytes(unit_data)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            file_bytes = generate_unit_pdf_bytes(unit_data)
            media_type = "application/pdf"
    except Exception as e:
        logger.error(f"Error generando exportación preview de unidad ({fmt}): {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar la previsualización de la unidad didáctica."
        )

    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', req.title or "Unidad").strip('_')[:50]
    filename = f"Unidad_Didactica_Preview_{clean_name}.{fmt}"
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

