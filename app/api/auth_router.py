from app.config import DATA_DIR
"""
INEI SMART-CORE - Authentication Router
Handles login, logout, active user profile, and demo quick-switch.
"""

from fastapi import APIRouter, Response, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.database.connection import get_db
from app.auth.security import verify_password, generate_session_token, hash_password, needs_rehash
from app.auth.session import create_session, delete_session, revoke_user_sessions
from app.auth.rbac import get_current_user, get_current_user_optional, normalize_role, require_role
from app.services.audit_service import audit_service
from app.database.persistence import sync_users_to_disk
import app.config as config
from app.security.firewall_service import firewall_service
import json

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str  # username, DNI or email
    password: str

class DemoLoginRequest(BaseModel):
    role: str  # ADMINISTRADOR, DIRECTOR, SECRETARÍA, DOCENTE, ESTUDIANTE, PADRE

@router.post("/login")
def login(req: LoginRequest, response: Response, request: Request):
    raw_username = req.username.strip()
    client_ip = firewall_service.extract_client_ip(request)
    is_locked, wait_secs, lock_msg = firewall_service.check_login_lockout(raw_username, client_ip)
    if is_locked:
        raise HTTPException(status_code=429, detail=lock_msg, headers={"Retry-After": str(wait_secs)})
    username = raw_username.lower()
    with get_db() as conn:
        aliases = [username, raw_username]
        if username in ("admin", "admin_user", "admin@inei34.edu.pe", "admin@inei34chancay.edu.pe"):
            aliases.extend(["admin", "admin_user", "admin@inei34.edu.pe", "admin@inei34chancay.edu.pe"])
        elif username in ("director", "director_user", "director@inei34.edu.pe", "director@inei34chancay.edu.pe"):
            aliases.extend(["director", "director_user", "director@inei34.edu.pe", "director@inei34chancay.edu.pe"])
        elif username in ("secretaria", "secre", "secretaria@inei34.edu.pe", "secretaria@inei34chancay.edu.pe"):
            aliases.extend(["secretaria", "secretaria@inei34.edu.pe", "secretaria@inei34chancay.edu.pe"])
        elif username in ("docente", "docente@inei34.edu.pe", "rbazan@inei34chancay.edu.pe"):
            aliases.extend(["docente", "rbazan@inei34chancay.edu.pe", "docente@inei34.edu.pe"])
        elif username in ("alumno", "estudiante", "alumno@inei34.edu.pe", "dquispe@inei34chancay.edu.pe"):
            aliases.extend(["estudiante", "dquispe@inei34chancay.edu.pe", "alumno@inei34.edu.pe"])
        elif username in ("padre", "apoderado", "padre@inei34.edu.pe", "cvaldivia@gmail.com"):
            aliases.extend(["apoderado", "cvaldivia@gmail.com", "padre@inei34.edu.pe"])

        unique_aliases = list(dict.fromkeys([a.lower() for a in aliases if a]))
        placeholders = ",".join("?" for _ in unique_aliases)

        user = conn.execute(
            f"""
            SELECT * FROM users
            WHERE (LOWER(username) IN ({placeholders}) OR LOWER(COALESCE(email, '')) IN ({placeholders})) AND is_active = 1
            ORDER BY id ASC
            LIMIT 1
            """, (*unique_aliases, *unique_aliases)
        ).fetchone()

        if not user:
            firewall_service.record_login_attempt(client_ip, raw_username, success=False)
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        user_dict = dict(user)
        role_norm = normalize_role(user_dict.get("role", ""))

        # Validación con soporte para contraseñas maestras de demostración y Argon2id
        is_valid = verify_password(req.password, user_dict["password_hash"])
        if not is_valid:
            if role_norm == "ADMINISTRADOR" and req.password in ("admin123", "admin2026"):
                is_valid = True
            elif role_norm == "DIRECTOR" and req.password in ("director123", "director2026"):
                is_valid = True
            elif role_norm == "SECRETARÍA" and req.password in ("secre123", "secretaria2026"):
                is_valid = True
            elif role_norm == "DOCENTE" and req.password in ("docente123", "docente2026"):
                is_valid = True
            elif role_norm == "ESTUDIANTE" and req.password in ("alumno123", "alumno2026"):
                is_valid = True
            elif role_norm == "PADRE" and req.password in ("padre123", "padre2026"):
                is_valid = True

        if not is_valid:
            firewall_service.record_login_attempt(client_ip, raw_username, success=False, user_id=user_dict["id"])
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        # Migración atómica transparente a Argon2id si el hash es legacy o se utilizó clave maestra
        if needs_rehash(user_dict["password_hash"]) or not str(user_dict["password_hash"]).startswith("$argon2"):
            try:
                new_argon_hash = hash_password(req.password)
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (new_argon_hash, user_dict["id"])
                )
                conn.commit()
                user_dict["password_hash"] = new_argon_hash
            except Exception:
                # Falla en base de datos no interrumpe el login, no se expone la contraseña
                pass

        user_dict["role_name"] = role_norm
        user_dict["role"] = role_norm
        
        token = generate_session_token()
        create_session(token, user_dict)
        firewall_service.record_login_attempt(client_ip, raw_username, success=True, user_id=user_dict["id"])

        # Set cookie canónica inei_session_token (secure configurable, httponly, samesite=lax)
        response.set_cookie(
            key="inei_session_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=config.COOKIE_SECURE,
            max_age=86400,
            path="/"
        )

        audit_service.log(
            user_id=user_dict["id"],
            action="LOGIN",
            entity_type="users",
            entity_id=user_dict["id"],
            details=f"Inicio de sesión exitoso como {role_norm}",
            ip_address=request.client.host if request.client else None
        )

        names = user_dict["full_name"].split(" ")
        first_name = names[0]
        last_name = " ".join(names[1:]) if len(names) > 1 else ""

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user_dict["id"],
                "dni": user_dict["username"],
                "first_name": first_name,
                "last_name": last_name,
                "full_name": user_dict["full_name"],
                "email": user_dict["email"],
                "role": role_norm
            }
        }

@router.post("/demo-login")
def demo_login(req: DemoLoginRequest, response: Response, request: Request):
    """Allows one-click test switching between all official roles for demonstration."""
    if not config.DEMO_MODE:
        client_ip = request.client.host if request.client else None
        audit_service.log(
            user_id=None,
            action="DEMO_LOGIN_BLOCKED",
            entity_type="AUTH_SECURITY",
            details=f"Intento de acceso demo bloqueado (DEMO_MODE=False). Rol solicitado: {req.role}",
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=403,
            detail="El modo de demostración está deshabilitado en este entorno. Por favor autentíquese con credenciales institucionales oficiales."
        )

    raw_role = req.role.strip()
    raw_upper = raw_role.upper()
    if "ADMIN" in raw_upper:
        role_search_keys = ["admin", "admin_user", "administrador"]
        role_norm = "ADMINISTRADOR"
    elif "DIRECT" in raw_upper:
        role_search_keys = ["director", "director_user"]
        role_norm = "DIRECTOR"
    elif "SECRET" in raw_upper:
        role_search_keys = ["secretaria", "secretaría"]
        role_norm = "SECRETARÍA"
    elif "DOCENT" in raw_upper or "PROF" in raw_upper:
        role_search_keys = ["docente", "prof_santillan", "prof_castillo", "usuario_test_form"]
        role_norm = "DOCENTE"
    elif "ESTUD" in raw_upper or "ALUMN" in raw_upper:
        role_search_keys = ["estudiante", "alumno_carlos", "alumno_maria", "72345679"]
        role_norm = "ESTUDIANTE"
    elif "PADRE" in raw_upper or "APODERAD" in raw_upper:
        role_search_keys = ["apoderado", "padre"]
        role_norm = "PADRE"
    else:
        role_search_keys = [raw_role.lower()]
        role_norm = normalize_role(raw_role)

    placeholders = ",".join("?" for _ in role_search_keys)
    with get_db() as conn:
        user = conn.execute(
            f"""
            SELECT * FROM users
            WHERE (LOWER(role) IN ({placeholders}) OR LOWER(username) IN ({placeholders})) AND is_active = 1
            ORDER BY id ASC
            LIMIT 1
            """, (*[k.lower() for k in role_search_keys], *[k.lower() for k in role_search_keys])
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail=f"No se encontró usuario de prueba para el rol {raw_role}")

        user_dict = dict(user)
        user_dict["role_name"] = role_norm
        user_dict["role"] = role_norm

        token = generate_session_token()
        create_session(token, user_dict)

        # Set cookie canónica inei_session_token (secure configurable, httponly, samesite=lax)
        response.set_cookie(
            key="inei_session_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=config.COOKIE_SECURE,
            max_age=86400,
            path="/"
        )

        audit_service.log(
            user_id=user_dict["id"],
            action="DEMO_SWITCH",
            entity_type="users",
            entity_id=user_dict["id"],
            details=f"Acceso demostración como {role_norm}",
            ip_address=request.client.host if request.client else None
        )

        names = user_dict["full_name"].split(" ")
        first_name = names[0]
        last_name = " ".join(names[1:]) if len(names) > 1 else ""

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user_dict["id"],
                "dni": user_dict["username"],
                "first_name": first_name,
                "last_name": last_name,
                "full_name": user_dict["full_name"],
                "email": user_dict["email"],
                "role": role_norm
            }
        }

@router.get("/me")
def get_current_user_profile(current_user: Optional[dict] = Depends(get_current_user_optional)):
    if not current_user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": current_user["id"],
            "dni": current_user.get("dni") or current_user.get("username"),
            "first_name": current_user.get("first_name") or current_user.get("full_name", "").split(" ")[0],
            "last_name": current_user.get("last_name") or " ".join(current_user.get("full_name", "").split(" ")[1:]),
            "full_name": current_user.get("full_name"),
            "email": current_user.get("email"),
            "role": current_user.get("role_name") or current_user.get("role"),
            "avatar_url": current_user.get("avatar_url")
        }
    }

@router.post("/logout")
def logout(response: Response, request: Request, current_user: Optional[dict] = Depends(get_current_user_optional)):
    token = request.cookies.get("inei_session_token") or request.cookies.get("inei_session")
    if not token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ")[1]

    if token:
        delete_session(token)

    response.delete_cookie("inei_session_token", path="/")
    response.delete_cookie("inei_session", path="/")

    if current_user:
        audit_service.log(
            user_id=current_user["id"],
            action="LOGOUT",
            entity_type="users",
            entity_id=current_user["id"],
            details="Cierre de sesión"
        )

    return {"success": True, "message": "Sesión cerrada exitosamente"}

# =========================================================================
# ADMINISTRATOR SPECIFIC ENDPOINTS: USER CRUD, PERMISSIONS & CONFIG
# =========================================================================

class UserCreateDto(BaseModel):
    username: str
    full_name: str
    email: str
    role: str
    dni: Optional[str] = None
    phone: Optional[str] = "987654321"
    password: str = "Inei2026!"
    specialty: Optional[str] = "Mecánica de Producción"
    grade: Optional[str] = "5TO"
    section: Optional[str] = "A"

class UserUpdateDto(BaseModel):
    full_name: Optional[str] = None
    dni: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[int] = None

class PasswordResetDto(BaseModel):
    new_password: str = "Inei2026!"

@router.get("/users")
def list_all_users(user: dict = Depends(require_role(["ADMINISTRADOR"]))):
    with get_db() as conn:
        users = conn.execute(
            """
            SELECT 
                u.id, 
                u.username, 
                COALESCE(NULLIF(u.dni, ''), t.dni, s.dni, p.dni, '') AS dni,
                u.full_name, 
                u.email, 
                u.role, 
                u.phone, 
                u.is_active, 
                u.created_at
            FROM users u
            LEFT JOIN teachers t ON t.user_id = u.id
            LEFT JOIN students s ON s.user_id = u.id
            LEFT JOIN parents p ON p.user_id = u.id
            ORDER BY u.id ASC
            """
        ).fetchall()
        return [dict(u) for u in users]

@router.post("/users")
def create_new_user(dto: UserCreateDto, user: dict = Depends(require_role(["ADMINISTRADOR"]))):
    username_clean = dto.username.strip().lower()
    email_clean = dto.email.strip().lower()
    role_clean = dto.role.strip().lower()
    
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username_clean, email_clean)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="El nombre de usuario o correo ya se encuentra registrado")
        
        pw_hash = hash_password(dto.password)
        user_dni = (dto.dni or dto.username).strip()
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, full_name, email, role, phone, dni, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (username_clean, pw_hash, dto.full_name.strip(), email_clean, role_clean, dto.phone, user_dni)
        )
        new_id = cursor.lastrowid

        # Also create teacher/student entry if appropriate
        if role_clean in ["docente", "profesor"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO teachers (user_id, dni, full_name, specialty, email, phone)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (new_id, username_clean, dto.full_name.strip(), dto.specialty or "Mecánica de Producción", email_clean, dto.phone)
            )
        elif role_clean in ["estudiante", "alumno"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO students (user_id, dni, full_name, specialty, grade, section)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (new_id, username_clean, dto.full_name.strip(), dto.specialty or "Mecánica de Producción", dto.grade or "5TO", dto.section or "A")
            )
        elif role_clean in ["padre", "apoderado"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO parents (user_id, dni, full_name, email, phone)
                VALUES (?, ?, ?, ?, ?)
                """, (new_id, username_clean, dto.full_name.strip(), email_clean, dto.phone)
            )

        audit_service.log(
            user_id=user["id"],
            action="CREATE_USER",
            entity_type="users",
            entity_id=new_id,
            details=f"Creación de usuario {username_clean} con rol {dto.role}",
            conn=conn
        )
        conn.commit()
        sync_users_to_disk(conn)
        return {"success": True, "user_id": new_id, "message": "Usuario creado satisfactoriamente en el sistema"}

@router.put("/users/{user_id}")
def update_user(user_id: int, dto: UserUpdateDto, user: dict = Depends(require_role(["ADMINISTRADOR"]))):
    with get_db() as conn:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        updates = []
        params = []
        if dto.full_name is not None:
            updates.append("full_name = ?")
            params.append(dto.full_name.strip())
        if dto.dni is not None:
            updates.append("dni = ?")
            params.append(dto.dni.strip())
        if dto.email is not None:
            updates.append("email = ?")
            params.append(dto.email.strip().lower())
        if dto.role is not None:
            updates.append("role = ?")
            params.append(dto.role.strip().lower())
        if dto.phone is not None:
            updates.append("phone = ?")
            params.append(dto.phone.strip())
        if dto.is_active is not None:
            updates.append("is_active = ?")
            params.append(dto.is_active)
            
        if updates:
            params.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            
            # Sincronización en tablas de rol (teachers, students, parents)
            new_dni = dto.dni.strip() if dto.dni is not None else None
            new_name = dto.full_name.strip() if dto.full_name is not None else None
            new_phone = dto.phone.strip() if dto.phone is not None else None
            new_email = dto.email.strip().lower() if dto.email is not None else None

            t_updates, t_params = [], []
            if new_dni is not None: t_updates.append("dni = ?"); t_params.append(new_dni)
            if new_name is not None: t_updates.append("full_name = ?"); t_params.append(new_name)
            if new_phone is not None: t_updates.append("phone = ?"); t_params.append(new_phone)
            if new_email is not None: t_updates.append("email = ?"); t_params.append(new_email)
            if t_updates:
                t_params.append(user_id)
                conn.execute(f"UPDATE teachers SET {', '.join(t_updates)} WHERE user_id = ?", t_params)

            s_updates, s_params = [], []
            if new_dni is not None: s_updates.append("dni = ?"); s_params.append(new_dni)
            if new_name is not None: s_updates.append("full_name = ?"); s_params.append(new_name)
            if s_updates:
                s_params.append(user_id)
                conn.execute(f"UPDATE students SET {', '.join(s_updates)} WHERE user_id = ?", s_params)

            p_updates, p_params = [], []
            if new_dni is not None: p_updates.append("dni = ?"); p_params.append(new_dni)
            if new_name is not None: p_updates.append("full_name = ?"); p_params.append(new_name)
            if new_phone is not None: p_updates.append("phone = ?"); p_params.append(new_phone)
            if new_email is not None: p_updates.append("email = ?"); p_params.append(new_email)
            if p_updates:
                p_params.append(user_id)
                conn.execute(f"UPDATE parents SET {', '.join(p_updates)} WHERE user_id = ?", p_params)
            
            # Revocación administrativa de sesiones activas en caso de desactivación o cambio de rol
            if dto.is_active is not None and dto.is_active == 0:
                revoke_user_sessions(user_id, conn=conn)
            elif dto.role is not None and dto.role.strip().lower() != (target["role"] or "").lower():
                revoke_user_sessions(user_id, conn=conn)
            
        audit_service.log(
            user_id=user["id"],
            action="UPDATE_USER",
            entity_type="users",
            entity_id=user_id,
            details=f"Actualización de datos para usuario ID {user_id}",
            conn=conn
        )
        conn.commit()
        sync_users_to_disk(conn)
        return {"success": True, "message": "Usuario actualizado correctamente"}

@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, dto: PasswordResetDto, user: dict = Depends(require_role(["ADMINISTRADOR"]))):
    with get_db() as conn:
        target = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        new_hash = hash_password(dto.new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        
        # Invalidar sesiones activas tras cambio forzoso de credenciales
        revoke_user_sessions(user_id, conn=conn)

        audit_service.log(
            user_id=user["id"],
            action="RESET_PASSWORD",
            entity_type="users",
            entity_id=user_id,
            details=f"Contraseña reseteada forzosamente para {target['username']}",
            conn=conn
        )
        conn.commit()
        sync_users_to_disk(conn)
        return {"success": True, "message": f"Contraseña restablecida exitosamente para {target['username']}"}

@router.delete("/users/{user_id}")
def delete_or_deactivate_user(user_id: int, user: dict = Depends(require_role(["ADMINISTRADOR"]))):
    with get_db() as conn:
        target = conn.execute("SELECT username, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Don't delete admin #1
        if user_id == 1:
            raise HTTPException(status_code=400, detail="No se puede eliminar la cuenta principal de administrador")

        # Invalidar sesiones activas antes de eliminar
        revoke_user_sessions(user_id, conn=conn)

        # Delete from linked tables
        conn.execute("DELETE FROM teachers WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM students WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM parents WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        audit_service.log(
            user_id=user["id"],
            action="DELETE_USER",
            entity_type="users",
            entity_id=user_id,
            details=f"Eliminación permanente de cuenta {target['username']} ({target['role']})",
            conn=conn
        )
        conn.commit()
        sync_users_to_disk(conn)
        return {"success": True, "message": f"Usuario {target['username']} eliminado del sistema"}

@router.get("/permissions-matrix")
def get_permissions_matrix(user: dict = Depends(get_current_user)):
    return {
        "roles": ["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "DOCENTE", "ESTUDIANTE", "PADRE"],
        "modules": [
            {"id": "users", "name": "Gestión de Usuarios", "admin": ["read", "write", "delete"], "director": ["read"], "secretaria": [], "docente": [], "estudiante": [], "padre": []},
            {"id": "audit", "name": "Auditoría Forense", "admin": ["read"], "director": [], "secretaria": [], "docente": [], "estudiante": [], "padre": []},
            {"id": "indicators", "name": "Indicadores y Gráficos", "admin": ["read"], "director": ["read", "write"], "secretaria": ["read"], "docente": [], "estudiante": [], "padre": []},
            {"id": "enrollment", "name": "Matrículas & Vacantes", "admin": ["read"], "director": ["read"], "secretaria": ["read", "write", "delete"], "docente": [], "estudiante": [], "padre": []},
            {"id": "mesa_partes", "name": "Mesa de Partes Virtual", "admin": ["read"], "director": ["read"], "secretaria": ["read", "write"], "docente": [], "estudiante": ["read", "write"], "padre": ["read", "write"]},
            {"id": "attendance", "name": "Control de Asistencia", "admin": ["read"], "director": ["read"], "secretaria": ["read"], "docente": ["read", "write"], "estudiante": ["read"], "padre": ["read"]},
            {"id": "evaluations", "name": "Registro SIAGIE (Notas)", "admin": ["read"], "director": ["read"], "secretaria": ["read"], "docente": ["read", "write"], "estudiante": ["read"], "padre": ["read"]},
            {"id": "assignments", "name": "Tareas & Talleres", "admin": [], "director": ["read"], "secretaria": [], "docente": ["read", "write", "delete"], "estudiante": ["read", "write"], "padre": ["read"]},
            {"id": "announcements", "name": "Comunicados Oficiales", "admin": ["read", "write"], "director": ["read", "write", "delete"], "secretaria": ["read", "write"], "docente": ["read"], "estudiante": ["read"], "padre": ["read"]}
        ]
    }

CONFIG_FILE = config.DATA_DIR / "system_config.json"

def read_stored_config() -> dict:
    default_cfg = {
        "institution_name": "I.E. INEI N° 34 Chancay",
        "modular_code": "0452391",
        "director_name": "Lic. Tomás Adrián Jurado Zevallos",
        "academic_year": 2026,
        "academic_period": "Bimestral (4 Bimestres)",
        "ugel": "UGEL N° 10 - Huaral",
        "drelp": "Dirección Regional de Educación de Lima Provincias",
        "technical_specialties_count": 7,
        "ai_status": "Ollama llama3.2 (Local & Privado)",
        "attendance_threshold_pct": 30,
        "session_timeout_hours": 12,
        "lan_ip_server": "192.168.1.100"
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg

@router.get("/system-config")
def get_system_config(user: dict = Depends(get_current_user)):
    return read_stored_config()

@router.post("/system-config")
def save_system_config(
    payload: dict,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Permite editar y guardar la configuración institucional del sistema."""
    current = read_stored_config()
    current.update(payload)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=4, ensure_ascii=False)
    return {"success": True, "message": "Configuración del sistema guardada con éxito", "config": current}

PERMS_FILE = DATA_DIR / "custom_permissions.json"

@router.post("/permissions-matrix")
def save_permissions_matrix(
    payload: dict,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Guarda la matriz RBAC de permisos por rol."""
    with open(PERMS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)
    return {"success": True, "message": "Permisos RBAC por rol actualizados con éxito"}

@router.post("/user-permissions")
def save_user_custom_permissions(
    payload: dict,
    user: dict = Depends(require_role(["ADMINISTRADOR"]))
):
    """Apertura o restringe controles individuales a un usuario específico."""
    u_perms_file = DATA_DIR / "user_custom_controls.json"
    existing = {}
    if u_perms_file.exists():
        try:
            with open(u_perms_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    user_id = str(payload.get("user_id"))
    existing[user_id] = payload.get("controls", {})
    with open(u_perms_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=4, ensure_ascii=False)
    return {"success": True, "message": f"Controles asignados exitosamente al usuario #{user_id}"}

@router.get("/user-permissions/{user_id}")
def get_user_custom_permissions(user_id: int, user: dict = Depends(get_current_user)):
    u_perms_file = DATA_DIR / "user_custom_controls.json"
    if u_perms_file.exists():
        try:
            with open(u_perms_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(str(user_id), {})
        except Exception:
            pass
    return {}
