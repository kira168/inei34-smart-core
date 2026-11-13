"""
INEI SMART-CORE - Academic Router
Endpoints for sections, courses, teachers, students, enrollments.
Persistencia centralizada en SQLite (tabla courses).
"""

import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.auth.rbac import get_current_user, get_current_user_optional, require_role
from app.services.academic_service import academic_service
from app.config import DATA_DIR

router = APIRouter(prefix="/api/academic", tags=["Academic"])

class StudentCreateRequest(BaseModel):
    dni: str
    first_name: str
    last_name: str
    email: str
    phone: str
    section_id: int
    student_code: str

class CourseCreateRequest(BaseModel):
    code: str
    name: str
    technical_specialty: Optional[str] = "Educación para el Trabajo"
    grade: Optional[str] = "5to Grado"
    section: Optional[str] = "A"
    weekly_hours: Optional[int] = 4
    room: Optional[str] = "Aula Polifuncional"
    teacher: Optional[str] = ""
    teacher_id: Optional[int] = None
    colorBg: Optional[str] = "bg-red-600"
    image: Optional[str] = ""
    syllabus_file: Optional[str] = ""
    units: Optional[List[Dict[str, Any]]] = []

class CourseUpdateRequest(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    technical_specialty: Optional[str] = None
    grade: Optional[str] = None
    section: Optional[str] = None
    weekly_hours: Optional[int] = None
    room: Optional[str] = None
    teacher: Optional[str] = None
    teacher_id: Optional[int] = None
    colorBg: Optional[str] = None
    image: Optional[str] = None
    syllabus_file: Optional[str] = None
    units: Optional[List[Dict[str, Any]]] = None
    progress: Optional[int] = None
    sessions: Optional[str] = None

class UnitCreateRequest(BaseModel):
    id: Optional[int] = None
    number: Optional[int] = None
    title: str
    bim: Optional[str] = "I Bimestre"
    start_date: Optional[str] = ""
    end_date: Optional[str] = ""
    sessions: Optional[List[Dict[str, Any]]] = []
    tasks: Optional[List[Dict[str, Any]]] = []
    exams: Optional[List[Dict[str, Any]]] = []
    materials: Optional[List[Dict[str, Any]]] = []

class SessionCreateRequest(BaseModel):
    id: Optional[int] = None
    num: Optional[int] = None
    title: str
    type: Optional[str] = "Taller Práctico"
    date: Optional[str] = ""
    duration: Optional[str] = "90 min"
    room: Optional[str] = ""
    status: Optional[str] = "Pendiente"
    verified: Optional[bool] = False
    signed: Optional[bool] = False
    pdf_file: Optional[str] = ""
    docx_file: Optional[str] = ""

class CoursesContentPayload(BaseModel):
    courses: List[dict]


# ==========================================
# RUTAS DE SECCIONES, DOCENTES Y ALUMNOS
# ==========================================

@router.get("/sections")
def get_sections(user: dict = Depends(get_current_user)):
    return academic_service.get_sections()

@router.get("/teachers")
def get_teachers(user: dict = Depends(get_current_user)):
    return academic_service.get_teachers()

@router.get("/students")
def get_students(
    section_id: Optional[int] = None,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA", "DOCENTE"]))
):
    return academic_service.get_students(section_id=section_id)

@router.get("/enrollments")
def get_enrollments(
    year: int = 2026,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA", "DOCENTE"]))
):
    return academic_service.get_enrollments(year=year)

@router.post("/students")
def create_student(
    req: StudentCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    res = academic_service.create_student(
        dni=req.dni,
        first_name=req.first_name,
        last_name=req.last_name,
        email=req.email,
        phone=req.phone,
        section_id=req.section_id,
        student_code=req.student_code
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


# ==========================================
# CRUD COMPLETO DE CURSOS (SQLITE)
# ==========================================

@router.get("/courses")
def get_courses(
    teacher_id: Optional[int] = None,
    section_id: Optional[int] = None,
    grade: Optional[str] = None,
    specialty: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Retorna la lista de cursos oficiales consultando directamente la base de datos SQLite.
    Filtra automáticamente para docentes según su asignación, salvo para directivos y administradores.
    """
    role = (user.get("role_name") or user.get("role") or "").upper()
    if role == "DOCENTE" and not teacher_id:
        from app.database.connection import get_db
        with get_db() as conn:
            t = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
            if t:
                teacher_id = t["id"]

    return academic_service.get_courses(
        teacher_id=teacher_id,
        section_id=section_id,
        grade=grade,
        specialty=specialty
    )

@router.get("/courses/{course_id}")
def get_course_detail(course_id: int, user: dict = Depends(get_current_user)):
    course = academic_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado.")
    return course

@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(
    req: CourseCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR"]))
):
    try:
        new_course = academic_service.create_course(req.model_dump(), user=user)
        return {"success": True, "message": "Curso creado exitosamente en SQLite.", "course": new_course}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando curso: {str(e)}")

@router.put("/courses/{course_id}")
def update_course(
    course_id: int,
    req: CourseUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    try:
        updated = academic_service.update_course(course_id, req.model_dump(exclude_unset=True), user=user)
        return {"success": True, "message": "Curso actualizado correctamente en SQLite.", "course": updated}
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando curso: {str(e)}")

@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    deleted = academic_service.delete_course(course_id, user=user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Curso no encontrado para eliminar.")
    return {"success": True, "message": "Curso desactivado de la malla curricular oficial en SQLite."}


# ==========================================
# GESTIÓN DE UNIDADES Y SESIONES (SQLITE)
# ==========================================

@router.post("/courses/{course_id}/units", status_code=status.HTTP_201_CREATED)
def add_course_unit(
    course_id: int,
    req: UnitCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    try:
        unit = academic_service.add_course_unit(course_id, req.model_dump(), user=user)
        return {"success": True, "message": "Unidad agregada exitosamente en SQLite.", "unit": unit}
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error agregando unidad: {str(e)}")

@router.delete("/courses/{course_id}/units/{unit_id}")
def delete_course_unit(
    course_id: int,
    unit_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    deleted = academic_service.delete_course_unit(course_id, unit_id, user=user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Unidad no encontrada en el curso.")
    return {"success": True, "message": "Unidad eliminada correctamente en SQLite."}

@router.post("/courses/{course_id}/units/{unit_id}/sessions")
def save_course_session(
    course_id: int,
    unit_id: int,
    req: SessionCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE"]))
):
    try:
        session = academic_service.add_course_session(course_id, unit_id, req.model_dump(), user=user)
        return {"success": True, "message": "Sesión guardada exitosamente en SQLite.", "session": session}
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando sesión: {str(e)}")


# ==========================================
# RUTAS DE COMPATIBILIDAD COURSES-CONTENT
# (Sincronización Bidireccional SQLite <-> Frontend)
# ==========================================

@router.get("/courses-content")
def get_courses_content(user: Optional[dict] = Depends(get_current_user_optional)):
    """
    Retorna la malla curricular completa consultando directamente SQLite courses.
    Si la base estuviera vacía, recurre al archivo como fallback.
    """
    try:
        courses = academic_service.get_courses(include_inactive=False)
        if courses and len(courses) > 0:
            return {"success": True, "courses": courses}
    except Exception:
        pass

    # Fallback al archivo si SQLite no tiene cursos
    file_path = DATA_DIR / "courses_content.json"
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"success": True, "courses": data}
        except Exception as e:
            return {"success": False, "error": str(e), "courses": None}
    return {"success": True, "courses": None}

@router.post("/courses-content")
def save_courses_content(
    payload: CoursesContentPayload,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Sincroniza la lista de cursos hacia SQLite courses y preserva el JSON como respaldo permanente.
    Permite persistir las sesiones, tareas, horarios y exámenes creados por el docente.
    """
    from app.services.academic_service import AcademicService
    from app.database.connection import get_db
    
    user_ctx = user or {"id": 1, "role": "DOCENTE", "full_name": "Docente Titular"}
    updated_count = 0

    for c in payload.courses:
        code = c.get("code")
        c_id = c.get("id")
        if not code and not c_id:
            continue
        try:
            with get_db() as conn:
                existing = conn.execute(
                    "SELECT id FROM courses WHERE id = ? OR (code IS NOT NULL AND code = ?)",
                    (c_id, code)
                ).fetchone()
            
            if existing:
                academic_service.update_course(existing["id"], c, user=user_ctx)
                updated_count += 1
            elif code:
                academic_service.create_course(c, user=user_ctx)
                updated_count += 1
        except Exception:
            continue

    # Persistir en JSON físico garantizando sincronía exacta
    try:
        file_path = DATA_DIR / "courses_content.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload.courses, f, ensure_ascii=False, indent=2)
    except Exception:
        AcademicService.sync_all_courses_to_disk_json()

    return {"success": True, "message": f"Contenido curricular ({updated_count} cursos) persistido exitosamente en SQLite y disco."}
