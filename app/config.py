import os
from pathlib import Path

# Directorios base
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
STORAGE_DIR = ROOT_DIR / "storage"
STATIC_DIR = ROOT_DIR / "public"
TEMPLATES_DIR = BASE_DIR / "templates"

# Crear directorios si no existen
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Base de datos (soporta TEST_DB_PATH para aislamiento estricto en pruebas)
TEST_DB_PATH = os.getenv("TEST_DB_PATH", "").strip()
DB_PATH = Path(TEST_DB_PATH) if TEST_DB_PATH else (DATA_DIR / "inei_smart_core.db")


# Configuración del servidor y perfiles de entorno
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SERVER_RELOAD = os.getenv("SERVER_RELOAD", "false").strip().lower() in ("true", "1", "yes")
DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "inei34_chancay_master_key_2026_super_secure")
SESSION_EXPIRY_SECONDS = 86400  # 24 Horas
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

# Orígenes autorizados para validación CSRF y control de peticiones
ALLOWED_ORIGINS = [
    f"http://{SERVER_HOST}:{SERVER_PORT}",
    f"http://127.0.0.1:{SERVER_PORT}",
    f"http://localhost:{SERVER_PORT}",
    "http://192.168.18.215:8000",
    "https://192.168.18.215:8000",
    "http://localhost",
    "http://127.0.0.1"
]
_custom_origins = os.getenv("ALLOWED_ORIGINS", "")
if _custom_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in _custom_origins.split(",") if o.strip()])

# Hosts permitidos para evitar Host Header Injection y suplantación
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "::1",
    "testclient",
    "testserver",
    "0.0.0.0",
    "192.168.18.215",
    "localhost:8000",
    "127.0.0.1:8000",
    "192.168.18.215:8000",
    "0.0.0.0:8000"
]
_custom_hosts = os.getenv("ALLOWED_HOSTS", "")
if _custom_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in _custom_hosts.split(",") if h.strip()])



# Mesa de Partes Virtual - Protección de abuso y Rate Limiting
MESA_PARTES_RATE_LIMIT = int(os.getenv("MESA_PARTES_RATE_LIMIT", "10"))  # solicitudes por ventana
MESA_PARTES_RATE_WINDOW_SECONDS = int(os.getenv("MESA_PARTES_RATE_WINDOW_SECONDS", "3600"))  # 1 hora
TRUSTED_PROXIES = [ip.strip() for ip in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,testclient").split(",") if ip.strip()]

# SmartTutor AI - Control de Frecuencia (Rate Limiting por estudiante)
CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "10"))  # 10 solicitudes por ventana
CHAT_RATE_WINDOW_SECONDS = int(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60"))  # ventana de 60 segundos
UPLOAD_RATE_LIMIT = int(os.getenv("UPLOAD_RATE_LIMIT", "5"))  # 5 subidas de archivo por ventana
UPLOAD_RATE_WINDOW_SECONDS = int(os.getenv("UPLOAD_RATE_WINDOW_SECONDS", "60"))  # ventana de 60 segundos



# Configuración de Inteligencia Artificial (Ollama Local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_AI_MODEL = os.getenv("DEFAULT_AI_MODEL", "llama3.2:latest")
AI_FALLBACK_MODEL = os.getenv("AI_FALLBACK_MODEL", "llama3.2:latest")
AI_CODER_MODEL = os.getenv("AI_CODER_MODEL", "qwen2.5-coder:7b")
AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "llava:latest")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
AI_KEEP_ALIVE = os.getenv("AI_KEEP_ALIVE", "60m")
AI_FALLBACK_ACTIVE = True

# Institución
INSTITUTION_NAME = "I.E. INEI N° 34"
INSTITUTION_LOCATION = "Chancay, Huaral, Lima - Perú"
ACADEMIC_YEAR = "2026"
MODULAR_CODE = "0340349"
