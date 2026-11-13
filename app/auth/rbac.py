from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, Depends, status
from app.auth.session import get_user_from_session
from app.database.connection import get_db_connection

def normalize_role(role: str) -> str:
    r = (role or "").strip().upper()
    if r in ["ADMIN", "ADMINISTRADOR"]:
        return "ADMINISTRADOR"
    if r in ["DIRECTOR", "DIRECTIVO"]:
        return "DIRECTOR"
    if r in ["SECRETARIA", "SECRETARÍA"]:
        return "SECRETARÍA"
    if r in ["DOCENTE", "PROFESOR"]:
        return "DOCENTE"
    if r in ["ESTUDIANTE", "ALUMNO"]:
        return "ESTUDIANTE"
    if r in ["PADRE", "APODERADO", "PADRE / APODERADO"]:
        return "PADRE"
    return r

async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Obtiene el usuario autenticado desde Cookie 'inei_session_token', 'inei_session' o Authorization Header."""
    token = request.cookies.get("inei_session_token") or request.cookies.get("inei_session")
    if not token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ")[1]
            
    user = get_user_from_session(token)
    return user

async def get_current_user(request: Request) -> Dict[str, Any]:
    """Exige usuario autenticado con sesión activa."""
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no iniciada o expirada. Por favor autentíquese en la Intranet."
        )
    return user

def require_role(allowed_roles: List[str]):
    """Dependencia FastAPI para control de acceso RBAC estricto en backend."""
    normalized_allowed = [normalize_role(r) for r in allowed_roles]
    normalized_allowed.append("ADMINISTRADOR")

    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)):
        user_role_norm = normalize_role(user.get("role") or user.get("role_name", ""))
        if user_role_norm not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: El rol '{user_role_norm}' no tiene permisos suficientes para esta acción."
            )
        return user
    return role_checker

def require_permission(permission_key: str):
    """Dependencia FastAPI para control de acceso basado en permisos granulares."""
    async def permission_checker(user: Dict[str, Any] = Depends(get_current_user)):
        role_norm = normalize_role(user.get("role") or user.get("role_name", ""))
        if role_norm == "ADMINISTRADOR":
            return user
        if not check_permission(user.get("role", "").lower(), permission_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Se requiere el permiso '{permission_key}'."
            )
        return user
    return permission_checker

def check_permission(role: str, perm_key: str) -> bool:
    """Valida si un rol tiene un permiso asignado en la base de datos."""
    r_lower = role.lower()
    if r_lower in ["admin", "administrador"]:
        return True
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM role_permissions WHERE role = ? AND permission = ?", (r_lower, perm_key))
        has_perm = cursor.fetchone() is not None
        conn.close()
        return has_perm
    except Exception:
        return True
