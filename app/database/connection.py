import sqlite3
import os
import sys
from pathlib import Path
from contextlib import contextmanager
from app.config import DB_PATH

def is_test_process() -> bool:
    """
    Detecta si el proceso actual es una ejecución de pruebas automatizadas o auditoría.
    Comprueba el nombre del ejecutable/script, argumentos de CLI y módulos de testing.
    """
    # Si ya se definió TEST_DB_PATH, el proceso sabe que está en testing aislado
    if os.getenv("TEST_DB_PATH", "").strip():
        return True
    # Detección por nombre de script
    prog = os.path.basename(sys.argv[0] or "").lower()
    if any(prog.startswith(prefix) for prefix in ["test", "audit", "pytest", "check"]):
        return True
    # Detección por argumentos CLI
    if any("pytest" in a.lower() or "unittest" in a.lower() or "test_" in a.lower() for a in sys.argv):
        return True
    # Detección por módulos de prueba cargados en memoria
    # Nota: No incluir 'unittest' plano aquí porque librerías como matplotlib importan unittest internamente
    test_modules = ["pytest", "starlette.testclient", "fastapi.testclient"]
    if any(m in sys.modules for m in test_modules):
        return True
    return False

def get_current_db_path() -> Path:
    """Retorna la ruta activa de base de datos, respetando TEST_DB_PATH si está configurada."""
    test_path = os.getenv("TEST_DB_PATH", "").strip()
    if test_path:
        return Path(test_path)
    return DB_PATH

def assert_isolated_db() -> None:
    """Verifica que la prueba no esté conectada accidentalmente a la base de producción."""
    current = str(get_current_db_path()).lower().replace("/", "\\")
    test_env = os.getenv("TEST_DB_PATH", "").strip().lower()
    if not test_env:
        raise RuntimeError("AISLAMIENTO NO GARANTIZADO: La variable TEST_DB_PATH no está configurada.")
    if "data\\inei_smart_core.db" in current:
        raise RuntimeError(f"AISLAMIENTO VIOLADO: Se intentó conectar a la base de producción: {current}")

def get_db_connection():
    """
    Crea y retorna una conexión a la base de datos SQLite con soporte para claves foráneas y Row Factory.
    Incorpora salvaguarda estricta: bloquea cualquier intento de conexión a producción durante pruebas si falta TEST_DB_PATH.
    """
    target_path = get_current_db_path()
    resolved_str = str(target_path).lower().replace("/", "\\")
    is_prod_target = "data\\inei_smart_core.db" in resolved_str

    if is_prod_target and is_test_process():
        # Si no se autorizó explícitamente el acceso a producción en CLI
        if os.getenv("ALLOW_PRODUCTION_TESTING", "0").strip().lower() not in ("1", "true", "yes"):
            raise RuntimeError(
                "PROTECCIÓN DE PRODUCCIÓN ACTIVA: Se detectó una ejecución de pruebas/auditoría "
                "intentando conectar a 'data/inei_smart_core.db' sin la variable TEST_DB_PATH. "
                "Para proteger los datos oficiales de la I.E. Emblemática INEI N.º 34, "
                "defina TEST_DB_PATH apuntando a una base SQLite aislada (ej. os.environ['TEST_DB_PATH'] = 'data/test_temp.db')."
            )

    conn = sqlite3.connect(str(target_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Forzar escritura directa e inmediata al archivo .db (sin archivos WAL flotantes que desincronice OneDrive)
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA synchronous = FULL")
    return conn

@contextmanager
def db_session():
    """Context manager para operaciones atómicas en la base de datos."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Alias for standard access
get_db = db_session

def init_db():
    from app.database.schema import create_all_tables
    create_all_tables()
