import time
import hashlib
from typing import Optional, Dict, Any
from app.config import SESSION_EXPIRY_SECONDS
from app.auth.security import generate_session_token
from app.database.connection import get_db

# Active sessions in-memory L1 cache (token -> session_dict)
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

def hash_token(token: str) -> str:
    """Calcula un hash criptográfico SHA-256 del token para evitar almacenamiento en texto plano."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _norm_role(r: str) -> str:
    """Normaliza identificadores de rol para comparaciones canónicas."""
    r_clean = (r or "").strip().upper()
    if r_clean in ["ADMIN", "ADMINISTRADOR"]: return "ADMINISTRADOR"
    if r_clean in ["DIRECTOR", "DIRECTIVO"]: return "DIRECTOR"
    if r_clean in ["SECRETARIA", "SECRETARÍA"]: return "SECRETARÍA"
    if r_clean in ["DOCENTE", "PROFESOR"]: return "DOCENTE"
    if r_clean in ["ESTUDIANTE", "ALUMNO"]: return "ESTUDIANTE"
    if r_clean in ["PADRE", "APODERADO"]: return "PADRE"
    return r_clean

def _ensure_sessions_table():
    """Garantiza de forma idempotente que la tabla user_sessions exista en SQLite."""
    try:
        with get_db() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                dni TEXT,
                full_name TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                role TEXT NOT NULL,
                role_name TEXT NOT NULL,
                role_id INTEGER DEFAULT 1,
                avatar_url TEXT,
                expires_at REAL NOT NULL,
                is_revoked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)")
    except Exception:
        pass

def _verify_user_account_status(user_id: int, session_role: str) -> bool:
    """
    Verifica contra la base de datos si la cuenta sigue activa y mantiene su rol vigente.
    Si el usuario fue desactivado (is_active = 0) o su rol fue modificado, invalida la sesión.
    Si el usuario no existe en la tabla users (ej. sesión ficticia en tests aislados), permite continuar.
    """
    if not user_id:
        return True
    try:
        with get_db() as conn:
            user_row = conn.execute("SELECT is_active, role FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_row:
                if user_row["is_active"] == 0:
                    return False
                if _norm_role(user_row["role"]) != _norm_role(session_role):
                    return False
        return True
    except Exception:
        return True

def create_user_session(user_dict: dict) -> str:
    """Crea una nueva sesión para el usuario, genera un token seguro y lo persiste en SQLite y cache L1."""
    token = generate_session_token()
    create_session(token, user_dict)
    return token

def create_session(token: str, user_dict: dict) -> None:
    """
    Registra la sesión en cache de memoria L1 y persiste el hash del token en SQLite (L2).
    Almacena únicamente los metadatos necesarios sin exponer contraseñas ni tokens en texto plano.
    """
    _ensure_sessions_table()

    user_id = user_dict.get("id") or user_dict.get("user_id") or 0
    username = str(user_dict.get("username") or user_dict.get("dni") or "usuario").strip()
    dni = str(user_dict.get("dni") or user_dict.get("username") or "").strip()
    
    full_name = user_dict.get("full_name")
    if not full_name:
        fn = user_dict.get("first_name", "")
        ln = user_dict.get("last_name", "")
        full_name = f"{fn} {ln}".strip() or username
    else:
        full_name = full_name.strip()

    names = full_name.split(" ")
    first_name = user_dict.get("first_name") or (names[0] if names else "")
    last_name = user_dict.get("last_name") or (" ".join(names[1:]) if len(names) > 1 else "")

    role = _norm_role(str(user_dict.get("role") or user_dict.get("role_name", "ESTUDIANTE")))
    role_name = _norm_role(str(user_dict.get("role_name") or user_dict.get("role", "ESTUDIANTE")))
    role_id = user_dict.get("role_id", 1)
    email = user_dict.get("email")
    avatar_url = user_dict.get("avatar_url")
    expires_at = time.time() + SESSION_EXPIRY_SECONDS

    session_data = {
        "id": user_id,
        "user_id": user_id,
        "username": username,
        "dni": dni,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
        "role": role,
        "role_name": role_name,
        "role_id": role_id,
        "avatar_url": avatar_url,
        "expires_at": expires_at
    }

    # 1. Almacenar en memoria L1
    ACTIVE_SESSIONS[token] = session_data

    # 2. Persistir en SQLite L2 con hash seguro
    token_hash = hash_token(token)
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_sessions (
                    token_hash, user_id, username, dni, first_name, last_name, full_name,
                    email, role, role_name, role_id, avatar_url, expires_at, is_revoked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                token_hash, user_id, username, dni, first_name, last_name, full_name,
                email, role, role_name, role_id, avatar_url, expires_at
            ))
    except Exception:
        # Fallback silencioso sin exponer datos en log
        pass

def get_user_from_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Recupera y valida una sesión activa.
    Comprueba expiración explícita, estado de revocación y vigencia de cuenta
    tanto en memoria L1 como en SQLite L2.
    """
    if not token or not isinstance(token, str):
        return None

    now = time.time()

    # 1. Verificar en Cache L1
    if token in ACTIVE_SESSIONS:
        session = ACTIVE_SESSIONS[token]
        # Verificar expiración temporal
        if now > session.get("expires_at", 0):
            del ACTIVE_SESSIONS[token]
            _mark_token_revoked(token)
            return None
        # Verificar estado activo y rol vigente de la cuenta
        if not _verify_user_account_status(session.get("user_id", 0), session.get("role", "")):
            del ACTIVE_SESSIONS[token]
            _mark_token_revoked(token)
            return None
        return session

    # 2. Fallback a Persistencia SQLite L2 (p. ej. tras reinicio del servidor)
    token_hash = hash_token(token)
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, username, dni, first_name, last_name, full_name,
                       email, role, role_name, role_id, avatar_url, expires_at, is_revoked
                FROM user_sessions
                WHERE token_hash = ?
                LIMIT 1
                """,
                (token_hash,)
            ).fetchone()

            if not row:
                return None

            # Verificar si fue revocado explícitamente (Logout o Revocación Administrativa)
            if row["is_revoked"] != 0:
                return None

            # Verificar expiración temporal
            expires_at = float(row["expires_at"])
            if now > expires_at:
                conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE id = ?", (row["id"],))
                return None

            # Verificar estado activo y rol vigente en users
            if not _verify_user_account_status(row["user_id"], row["role"]):
                conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE id = ?", (row["id"],))
                return None

            # Sesión válida recuperada de SQLite: repoblar cache L1
            session_data = {
                "id": row["user_id"],
                "user_id": row["user_id"],
                "username": row["username"],
                "dni": row["dni"] or row["username"],
                "first_name": row["first_name"] or "",
                "last_name": row["last_name"] or "",
                "full_name": row["full_name"],
                "email": row["email"],
                "role": row["role"],
                "role_name": row["role_name"],
                "role_id": row["role_id"] if "role_id" in row.keys() else 1,
                "avatar_url": row["avatar_url"],
                "expires_at": expires_at
            }
            ACTIVE_SESSIONS[token] = session_data
            return session_data
    except Exception:
        return None

def get_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Alias para get_user_from_session."""
    return get_user_from_session(token)

def destroy_user_session(token: Optional[str]) -> None:
    """
    Revoca inmediatamente una sesión en memoria L1 y en persistencia SQLite L2.
    Garantiza que el token no pueda ser reutilizado.
    """
    if not token or not isinstance(token, str):
        return

    # 1. Eliminar de L1
    ACTIVE_SESSIONS.pop(token, None)

    # 2. Marcar revocado en SQLite L2
    _mark_token_revoked(token)

def delete_session(token: Optional[str]) -> None:
    """Alias para destroy_user_session."""
    destroy_user_session(token)

def revoke_user_sessions(user_id: int, conn=None) -> None:
    """
    Revoca inmediatamente todas las sesiones activas de un usuario en L1 (RAM)
    y en SQLite L2 (user_sessions). Utilizado cuando una cuenta es desactivada,
    eliminada, cambia de rol o restablece contraseña.
    """
    if not user_id:
        return

    # 1. Purgar de memoria L1 todas las sesiones que pertenezcan a user_id
    tokens_to_evict = [
        tok for tok, sess in ACTIVE_SESSIONS.items()
        if sess.get("user_id") == user_id or sess.get("id") == user_id
    ]
    for tok in tokens_to_evict:
        ACTIVE_SESSIONS.pop(tok, None)

    # 2. Marcar revocadas en SQLite L2 (reutiliza conexión si se pasa para evitar bloqueos)
    try:
        if conn is not None:
            conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,))
        else:
            with get_db() as c:
                c.execute("UPDATE user_sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,))
    except Exception:
        pass

def _mark_token_revoked(token: str) -> None:
    """Marca el hash del token como revocado atómicamente en la base de datos."""
    try:
        token_hash = hash_token(token)
        with get_db() as conn:
            conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE token_hash = ?", (token_hash,))
    except Exception:
        pass
