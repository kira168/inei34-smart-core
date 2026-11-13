import hashlib
import secrets
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.config import SECRET_KEY

# Hasher Argon2id optimizado para alta reactividad web (estándar recomendado OWASP)
ph = PasswordHasher(time_cost=1, memory_cost=19456, parallelism=1)
LEGACY_SALT = "inei34_chancay_master_salt_2026_"

def hash_password(password: str) -> str:
    """Genera hash Argon2id seguro para contraseñas."""
    return ph.hash(password)

def hash_password_legacy(password: str) -> str:
    """Genera hash SHA-256 legacy (solo para verificación y compatibilidad)."""
    return hashlib.sha256((LEGACY_SALT + password).encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña contra su hash (Argon2id o SHA-256 legacy).
    Utiliza comparación en tiempo constante para hashes heredados.
    """
    if not hashed_password or not plain_password:
        return False

    if hashed_password.startswith("$argon2"):
        try:
            return ph.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    else:
        # Legacy SHA-256 con comparación en tiempo constante
        legacy_hash = hash_password_legacy(plain_password)
        return secrets.compare_digest(legacy_hash, hashed_password)

def needs_rehash(hashed_password: str) -> bool:
    """
    Determina si un hash debe ser actualizado a Argon2id.
    Retorna True si es un hash legacy SHA-256 o si Argon2id requiere re-hash.
    """
    if not hashed_password:
        return True
    if not hashed_password.startswith("$argon2"):
        return True
    try:
        return ph.check_needs_rehash(hashed_password)
    except Exception:
        return True

def generate_session_token() -> str:
    return secrets.token_urlsafe(32)

