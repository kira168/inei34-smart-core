"""
INEI SMART-CORE - Assignment Router
Homework assignments, student deliveries, feedback, and grading.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pathlib import Path
import shutil
import os
import re
from pydantic import BaseModel
from typing import Optional, List
from app.auth.rbac import get_current_user, get_current_user_optional, require_role, normalize_role
from app.services.assignment_service import assignment_service
from app.database.connection import get_db

router = APIRouter(prefix="/api/assignments", tags=["Assignments"])

class AssignmentCreateRequest(BaseModel):
    course_id: int
    title: str
    description: str
    due_date: str
    attachment_file: Optional[str] = None

class AssignmentUpdateRequest(BaseModel):
    title: str
    description: str
    due_date: str
    course_id: Optional[int] = None
    attachment_file: Optional[str] = None

class SubmissionSubmitRequest(BaseModel):
    assignment_id: int
    submission_text: Optional[str] = None
    file_path: Optional[str] = None

class GradeSubmissionRequest(BaseModel):
    submission_id: int
    grade: str
    feedback: str

def verify_assignment_teacher_access(user: dict, assignment_id: int):
    """Verifica que el usuario tenga permiso sobre la tarea (Director/Admin o docente titular de la tarea/curso)."""
    role = normalize_role(user.get("role") or user.get("role_name", ""))
    if role in ["ADMINISTRADOR", "DIRECTOR"]:
        return True
    if role == "DOCENTE":
        with get_db() as conn:
            asgn = conn.execute("SELECT id, course_id, teacher_id FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
            if not asgn:
                raise HTTPException(status_code=404, detail="Tarea no encontrada")
            t = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
            if not t:
                raise HTTPException(status_code=403, detail="Acceso denegado: Docente no registrado en la planta profesoral")
            
            course = conn.execute("SELECT teacher_id FROM courses WHERE id = ?", (asgn["course_id"],)).fetchone()
            course_teacher_id = course["teacher_id"] if course else None
            
            if asgn["teacher_id"] != t["id"] and course_teacher_id != t["id"]:
                raise HTTPException(
                    status_code=403,
                    detail="Acceso denegado: El docente no tiene asignada esta tarea ni el curso asociado"
                )
            return True
    raise HTTPException(
        status_code=403,
        detail=f"Acceso denegado: El rol '{role}' no tiene permisos para gestionar esta tarea"
    )

def verify_submission_teacher_access(user: dict, submission_id: int):
    """Verifica que el docente tenga permiso para calificar la entrega."""
    role = normalize_role(user.get("role") or user.get("role_name", ""))
    if role in ["ADMINISTRADOR", "DIRECTOR"]:
        return True
    if role == "DOCENTE":
        with get_db() as conn:
            sub = conn.execute("SELECT assignment_id FROM submissions WHERE id = ?", (submission_id,)).fetchone()
            if not sub:
                raise HTTPException(status_code=404, detail="Entrega no encontrada")
            return verify_assignment_teacher_access(user, sub["assignment_id"])
    raise HTTPException(
        status_code=403,
        detail=f"Acceso denegado: El rol '{role}' no tiene permisos para calificar entregas"
    )

@router.get("")
def get_assignments(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        role = user.get("role", "").upper()
        if role == "DOCENTE":
            t = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
            teacher_id = t["id"] if t else None
            return assignment_service.get_all_assignments(teacher_id=teacher_id)
        elif role in ["ESTUDIANTE", "ALUMNO"]:
            st = conn.execute("SELECT id FROM students WHERE user_id = ?", (user["id"],)).fetchone()
            if not st:
                return []
            return assignment_service.get_student_assignments(st["id"])
        else:
            return assignment_service.get_all_assignments()

@router.get("/course/{course_id}")
def get_course_assignments(course_id: int, user: dict = Depends(get_current_user)):
    return assignment_service.get_course_assignments(course_id)

@router.get("/{assignment_id}/submissions")
def get_assignment_submissions(
    assignment_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    verify_assignment_teacher_access(user, assignment_id)
    return assignment_service.get_assignment_submissions(assignment_id)

@router.post("")
def create_assignment(
    req: AssignmentCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    role = normalize_role(user.get("role") or user.get("role_name", ""))
    with get_db() as conn:
        t = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
        if role == "DOCENTE":
            if not t:
                raise HTTPException(status_code=403, detail="Acceso denegado: Docente no registrado en la planta profesoral")
            c = conn.execute("SELECT teacher_id FROM courses WHERE id = ?", (req.course_id,)).fetchone()
            if not c:
                raise HTTPException(status_code=404, detail="Curso no encontrado")
            if c["teacher_id"] != t["id"]:
                raise HTTPException(status_code=403, detail="Acceso denegado: El docente no tiene asignado el curso seleccionado")
            teacher_id = t["id"]
        else:
            teacher_id = t["id"] if t else 1

        return assignment_service.create_assignment(
            course_id=req.course_id,
            teacher_id=teacher_id,
            title=req.title,
            description=req.description,
            due_date=req.due_date,
            attachment_file=req.attachment_file
        )

@router.put("/{assignment_id}")
def update_assignment(
    assignment_id: int,
    req: AssignmentUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    verify_assignment_teacher_access(user, assignment_id)
    role = normalize_role(user.get("role") or user.get("role_name", ""))
    if req.course_id and role == "DOCENTE":
        with get_db() as conn:
            t = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
            c = conn.execute("SELECT teacher_id FROM courses WHERE id = ?", (req.course_id,)).fetchone()
            if not c or not t or c["teacher_id"] != t["id"]:
                raise HTTPException(status_code=403, detail="Acceso denegado: No puedes reasignar la tarea a un curso no asignado")

    return assignment_service.update_assignment(
        assignment_id=assignment_id,
        title=req.title,
        description=req.description,
        due_date=req.due_date,
        course_id=req.course_id,
        attachment_file=req.attachment_file
    )

@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    verify_assignment_teacher_access(user, assignment_id)
    return assignment_service.delete_assignment(assignment_id)

@router.get("/my-assignments")
def get_my_assignments(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        st = conn.execute("SELECT id FROM students WHERE user_id = ?", (user["id"],)).fetchone()
        if not st:
            return []
        return assignment_service.get_student_assignments(st["id"])

@router.post("/submit")
def submit_assignment(req: SubmissionSubmitRequest, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        st = conn.execute("SELECT id FROM students WHERE user_id = ?", (user["id"],)).fetchone()
        if not st:
            raise HTTPException(status_code=403, detail="Solo los estudiantes matriculados pueden entregar tareas")
        return assignment_service.submit_assignment(
            assignment_id=req.assignment_id,
            student_id=st["id"],
            file_path=req.file_path,
            submission_text=req.submission_text
        )

@router.post("/grade")
def grade_submission(
    req: GradeSubmissionRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    verify_submission_teacher_access(user, req.submission_id)
    return assignment_service.grade_submission(
        submission_id=req.submission_id,
        grade=req.grade,
        feedback=req.feedback
    )


# ==========================================
# RUTAS DE TAREAS DE SESIÓN BLACKBOARD
# ==========================================

class SessionTaskSubmitRequest(BaseModel):
    course_id: Optional[int] = None
    unit_id: Optional[str] = None
    ses_id: Optional[str] = None
    task_id: str
    task_title: str
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    student_dni: Optional[str] = None
    submission_text: Optional[str] = ""
    file_path: Optional[str] = ""
    file_name: Optional[str] = ""

class GradeSessionTaskRequest(BaseModel):
    course_id: int
    ses_id: str
    task_id: str
    student_id: int
    student_name: Optional[str] = ""
    grade: float
    cneb_level: str
    feedback: Optional[str] = ""
    task_title: Optional[str] = None

@router.post("/upload-evidence")
async def upload_task_evidence_file(file: UploadFile = File(...)):
    """Guarda físicamente la evidencia enviada por el estudiante en public/uploads."""
    from app.main import STATIC_DIR
    uploads_dir = STATIC_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    original_filename = Path(file.filename).name
    # Limpiar nombre pero mantener extensión y legibilidad
    clean_name = re.sub(r'[^\w\.-]', '_', original_filename)
    dest_path = uploads_dir / clean_name

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "success": True,
        "filename": clean_name,
        "url": f"/uploads/{clean_name}",
        "size": os.path.getsize(dest_path)
    }

@router.post("/session-task-submit")
def submit_session_task(
    req: SessionTaskSubmitRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    student_id = req.student_id
    student_name = req.student_name
    student_dni = req.student_dni

    with get_db() as conn:
        if user and isinstance(user, dict):
            st = conn.execute(
                "SELECT id, dni, full_name FROM students WHERE user_id = ? OR id = ? OR dni = ?",
                (user.get("id"), user.get("id"), user.get("dni"))
            ).fetchone()
            if st:
                student_id = st["id"]
                student_name = st["full_name"]
                student_dni = st["dni"]

        if not student_id:
            st = conn.execute("SELECT id, dni, full_name FROM students ORDER BY id ASC LIMIT 1").fetchone()
            if st:
                student_id = st["id"]
                student_name = req.student_name or st["full_name"]
                student_dni = req.student_dni or st["dni"]
            else:
                student_id = 1
                student_name = req.student_name or "Diego Quispe Alarcón"
                student_dni = req.student_dni or "73849502"

        cursor = conn.cursor()
        clean_task_id = str(req.task_id).replace("t_", "")
        clean_title = (req.task_title or "").strip()
        existing = cursor.execute(
            """
            SELECT id, grade, cneb_level FROM session_task_submissions
            WHERE student_id = ?
              AND (
                task_id = ?
                OR task_id = ?
                OR task_id LIKE ?
                OR (task_title IS NOT NULL AND TRIM(task_title) = ?)
                OR (task_title IS NOT NULL AND TRIM(task_title) LIKE ?)
              )
            ORDER BY id DESC LIMIT 1
            """,
            (student_id, str(req.task_id), clean_task_id, f"%{clean_task_id}%", clean_title, f"%{clean_title}%")
        ).fetchone()

        if existing and existing["grade"] is not None:
            raise HTTPException(
                status_code=400,
                detail=f"La tarea '{clean_title or req.task_title}' ya fue revisada y calificada por el docente con nota {existing['grade']} ({existing['cneb_level'] or 'AD'}). La entrega se encuentra cerrada y no se admiten nuevos envíos."
            )

        if existing:
            sub_id = existing["id"]
            cursor.execute(
                """
                UPDATE session_task_submissions
                SET course_id = ?, unit_id = ?, ses_id = ?, task_id = ?, task_title = ?,
                    student_name = ?, student_dni = ?,
                    submission_text = ?, file_path = ?, file_name = ?, submitted_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    req.course_id, req.unit_id, req.ses_id, str(req.task_id), req.task_title,
                    student_name, student_dni,
                    req.submission_text, req.file_path, req.file_name, sub_id
                )
            )
        else:
            cursor.execute(
                """
                INSERT INTO session_task_submissions (
                    course_id, unit_id, ses_id, task_id, task_title, student_id, student_name, student_dni,
                    submission_text, file_path, file_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req.course_id, req.unit_id, req.ses_id, str(req.task_id), req.task_title,
                    student_id, student_name, student_dni, req.submission_text, req.file_path, req.file_name
                )
            )
            sub_id = cursor.lastrowid

    return {
        "success": True,
        "message": "Evidencia de tarea enviada con éxito.",
        "id": sub_id,
        "student_id": student_id,
        "student_name": student_name,
        "file_name": req.file_name
    }

@router.get("/session-task-submissions")
def get_session_task_submissions(
    course_id: Optional[int] = None,
    ses_id: Optional[str] = None,
    task_id: Optional[str] = None,
    task_title: Optional[str] = None,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    with get_db() as conn:
        query = "SELECT * FROM session_task_submissions WHERE 1=1"
        params = []
        if course_id:
            query += " AND (course_id = ? OR course_id IS NULL)"
            params.append(course_id)
        if ses_id:
            query += " AND (ses_id = ? OR ses_id IS NULL)"
            params.append(ses_id)
        if task_id and task_title:
            clean_tid = str(task_id).replace("t_", "")
            query += " AND (task_id = ? OR task_id = ? OR task_id LIKE ? OR task_title = ?)"
            params.extend([str(task_id), clean_tid, f"%{clean_tid}%", task_title])
        elif task_id:
            clean_tid = str(task_id).replace("t_", "")
            query += " AND (task_id = ? OR task_id = ? OR task_id LIKE ?)"
            params.extend([str(task_id), clean_tid, f"%{clean_tid}%"])
        elif task_title:
            query += " AND task_title = ?"
            params.append(task_title)

        query += " ORDER BY submitted_at DESC, id DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        return {"success": True, "submissions": [dict(r) for r in rows]}

@router.post("/grade-session-task")
def grade_session_task(
    req: GradeSessionTaskRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    with get_db() as conn:
        cursor = conn.cursor()
        clean_tid = str(req.task_id).replace("t_", "")
        existing = cursor.execute(
            """
            SELECT id FROM session_task_submissions
            WHERE student_id = ?
              AND (
                task_id = ?
                OR task_id = ?
                OR task_id LIKE ?
                OR (task_title IS NOT NULL AND task_title = ?)
              )
            ORDER BY id DESC LIMIT 1
            """,
            (req.student_id, str(req.task_id), clean_tid, f"%{clean_tid}%", req.task_title or "")
        ).fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE session_task_submissions
                SET grade = ?, cneb_level = ?, feedback = ?, graded_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (req.grade, req.cneb_level, req.feedback, existing["id"])
            )
        else:
            cursor.execute(
                """
                INSERT INTO session_task_submissions (
                    course_id, ses_id, task_id, task_title, student_id, student_name, grade, cneb_level, feedback, graded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (req.course_id, req.ses_id, str(req.task_id), req.task_title or "Tarea de Sesión", req.student_id, req.student_name, req.grade, req.cneb_level, req.feedback)
            )

    return {"success": True, "message": "Calificación de tarea guardada correctamente"}
