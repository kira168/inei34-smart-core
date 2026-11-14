"""
INEI SMART-CORE 2.0 - FastAPI Application
Main application entry point mounting all routers, templates, and static assets.
"""

import os
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.config import STATIC_DIR, TEMPLATES_DIR, DATA_DIR, STORAGE_DIR, ROOT_DIR, ALLOWED_ORIGINS, ALLOWED_HOSTS
from app.database.schema import create_all_tables
from app.database.seed import seed_database
from app.api import (
    auth_router,
    dashboard_router,
    academic_router,
    attendance_router,
    evaluation_router,
    assignment_router,
    document_router,
    mesa_partes_router,
    communication_router,
    audit_router,
    admin_router,
    ai_router,
    support_router,
    firewall_router,
    whatsapp_router
)

# Ensure folders exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(STATIC_DIR / "imagen", exist_ok=True)
os.makedirs(STATIC_DIR / "uploads", exist_ok=True)
os.makedirs(STATIC_DIR / "img", exist_ok=True)
os.makedirs(ROOT_DIR / "app" / "static", exist_ok=True)

# Initialize Database
create_all_tables()
seed_database()

app = FastAPI(
    title="INEI SMART-CORE",
    description="Intranet Educativa Inteligente para la I.E. INEI N° 34 Chancay",
    version="2.0.0"
)

# 1. Configuración CORS con orígenes explícitos (sin comodines y con credenciales permitidas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# 2. Middleware de Protección CSRF, Validación Estricta de Origen, Host y Sec-Fetch-Site
class CSRFOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Validar únicamente métodos mutables que alteran estado
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            # 1. Validar cabecera Host para mitigar Host Header Injection y Spoofing
            host_hdr = request.headers.get("host")
            if host_hdr:
                host_clean = host_hdr.strip().lower()
                allowed_hosts_lower = [h.lower() for h in ALLOWED_HOSTS]
                is_tunnel_host = host_clean.endswith(".trycloudflare.com")
                if "*" not in allowed_hosts_lower and host_clean not in allowed_hosts_lower and not is_tunnel_host:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Host no autorizado"}
                    )

            # 2. Comprobar Origin si está presente (validación estricta de esquema y lista blanca)
            origin = request.headers.get("origin")
            if origin:
                origin_clean = origin.strip().rstrip("/")
                allowed_clean = [o.strip().rstrip("/") for o in ALLOWED_ORIGINS]
                parsed = urlparse(origin_clean)
                if parsed.scheme not in ("http", "https"):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF: Esquema de origen no permitido"}
                    )
                is_tunnel_origin = bool(parsed.netloc and parsed.netloc.endswith(".trycloudflare.com"))
                if "*" not in allowed_clean and origin_clean not in allowed_clean and not is_tunnel_origin:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF: Origen no autorizado"}
                    )

            # 3. Comprobar Sec-Fetch-Site como defensa en navegadores modernos
            sec_fetch_site = request.headers.get("sec-fetch-site")
            if sec_fetch_site == "cross-site":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF: Petición de origen cruzado no permitida"}
                )

            # 4. Si no hay Origin pero hay Referer, verificar estrictamente contra ALLOWED_ORIGINS
            referer = request.headers.get("referer")
            if not origin and referer:
                parsed_ref = urlparse(referer)
                if parsed_ref.scheme not in ("http", "https"):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF: Esquema de referer no permitido"}
                    )
                ref_origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}".rstrip("/")
                allowed_clean = [o.strip().rstrip("/") for o in ALLOWED_ORIGINS]
                is_tunnel_ref = bool(parsed_ref.netloc and parsed_ref.netloc.endswith(".trycloudflare.com"))
                if ref_origin not in allowed_clean and not is_tunnel_ref:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF: Referer no autorizado"}
                    )

            # 5. Si no están presentes Origin, Sec-Fetch-Site ni Referer (p. ej. TestClient, scripts locales, cURL):
            # Se permite la solicitud para preservar compatibilidad con clientes legítimos locales.

        return await call_next(request)

app.add_middleware(CSRFOriginMiddleware)

# 3. Middleware del Firewall Inteligente con Persistencia SQLite
from app.security.firewall_service import firewall_service

class FirewallInspectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Omitir archivos estáticos y recursos multimedia para latencia cero
        if (
            path.startswith("/static")
            or path.startswith("/imagen")
            or path.startswith("/uploads")
            or path in ("/favicon.ico", "/logo.png")
        ):
            return await call_next(request)

        # 1. Identificar y normalizar la IP de origen con validación de proxies confiables
        client_ip = firewall_service.extract_client_ip(request)

        # Si el firewall está desactivado globalmente por configuración, continuar
        if not firewall_service.is_enabled():
            return await call_next(request)

        # 2. Comprobar si la IP se encuentra activamente bloqueada en SQLite
        is_banned, ban_info = firewall_service.is_ip_banned(client_ip)
        if is_banned:
            reason = ban_info.get("reason", "Bloqueo preventivo por políticas de seguridad") if ban_info else "Bloqueo preventivo"
            expires = ban_info.get("expires_at", "Indefinida") if ban_info else "Indefinida"
            firewall_service.log_event(
                ip_address=client_ip,
                event_type="BLOCKED_REQUEST",
                severity="HIGH",
                endpoint=path,
                user_id=None,
                description=f"Solicitud bloqueada para IP con veto activo ({reason})",
                metadata={"expires_at": expires, "method": request.method}
            )
            if path.startswith("/api/"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Acceso denegado: Su dirección IP está bloqueada por el Firewall institucional. Motivo: {reason}."}
                )
            blocked_html = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Acceso Bloqueado - Firewall Institucional</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-900 min-h-screen flex items-center justify-center p-4 text-white">
<div class="bg-slate-800 border border-red-500/40 rounded-3xl p-8 max-w-md w-full text-center space-y-4 shadow-2xl">
    <div class="w-16 h-16 mx-auto rounded-2xl bg-red-950 text-red-400 flex items-center justify-center text-3xl font-black">!</div>
    <div class="text-xs font-mono tracking-widest text-red-400 uppercase font-bold">FIREWALL INSTITUCIONAL</div>
    <h1 class="text-xl font-black">ACCESO RESTRINGIDO POR SEGURIDAD</h1>
    <p class="text-xs text-slate-300 leading-relaxed">Su dirección IP (<code>{client_ip}</code>) se encuentra bloqueada temporalmente.<br><strong>Motivo:</strong> {reason}</p>
    <div class="text-[11px] font-mono text-slate-400 bg-slate-950 p-2.5 rounded-xl border border-slate-700">Expira: {expires or 'Consulte con Administración'}</div>
</div></body></html>'''
            return HTMLResponse(status_code=403, content=blocked_html)

        # 3. Inspeccionar patrones anómalos (traversal, sondeo hostil)
        anomaly = firewall_service.inspect_request_anomalies(request, client_ip)
        if anomaly:
            if "traversal" in anomaly.lower() or "passwd" in anomaly.lower():
                return JSONResponse(status_code=400, content={"detail": "Petición no válida detectada por el firewall"})

        # 4. Control de tasa (Rate Limiting) por endpoint
        if path == "/api/auth/login" and request.method == "POST":
            allowed, retry_after = firewall_service.check_rate_limit(client_ip, category="login")
            if not allowed:
                firewall_service.log_event(
                    ip_address=client_ip,
                    event_type="RATE_LIMIT_EXCEEDED",
                    severity="MEDIUM",
                    endpoint=path,
                    user_id=None,
                    description=f"Límite de intentos de login superado para IP {client_ip}",
                    metadata={"retry_after": retry_after}
                )
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={"detail": f"Demasiadas solicitudes de autenticación. Espere {retry_after} segundos."}
                )
        elif path.startswith("/api/"):
            # Excluir endpoints administrativos del rate limit general si vienen de loopback
            if not (path.startswith("/api/admin/") and client_ip in ("127.0.0.1", "::1")):
                allowed, retry_after = firewall_service.check_rate_limit(client_ip, category="default")
                if not allowed:
                    firewall_service.log_event(
                        ip_address=client_ip,
                        event_type="RATE_LIMIT_EXCEEDED",
                        severity="LOW",
                        endpoint=path,
                        user_id=None,
                        description=f"Límite general de API excedido para IP {client_ip}",
                        metadata={"retry_after": retry_after}
                    )
                    return JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={"detail": f"Límite de solicitudes alcanzado. Espere {retry_after} segundos."}
                    )

        return await call_next(request)

app.add_middleware(FirewallInspectionMiddleware)

# Mount Static Assets & Images directly
app.mount("/imagen", StaticFiles(directory=str(STATIC_DIR / "imagen")), name="imagen")
app.mount("/uploads", StaticFiles(directory=str(STATIC_DIR / "uploads")), name="uploads")
app.mount("/docs", StaticFiles(directory=str(STATIC_DIR / "docs")), name="docs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/docs/FUT_OFICIAL_INEI34_CHANCAY_2026.pdf")
@app.get("/api/documents/fut-pdf")
@app.get("/descargar-fut")
def get_official_fut_pdf():
    candidates = [
        STATIC_DIR / "docs" / "FUT_OFICIAL_INEI34_CHANCAY_2026.pdf",
        ROOT_DIR / "app" / "static" / "docs" / "FUT_OFICIAL_INEI34_CHANCAY_2026.pdf",
        ROOT_DIR / "public" / "docs" / "FUT_OFICIAL_INEI34_CHANCAY_2026.pdf",
    ]
    for c in candidates:
        if c.exists():
            return FileResponse(
                str(c),
                media_type="application/pdf",
                filename="FUT_OFICIAL_INEI34_CHANCAY_2026.pdf"
            )
    return JSONResponse(status_code=404, content={"detail": "Documento FUT no encontrado"})

@app.get("/favicon.ico")
@app.get("/logo.png")
@app.get("/imagen/insignia.png")
@app.get("/static/imagen/insignia.png")
def get_institutional_logo():
    logo_candidates = [
        STATIC_DIR / "imagen" / "insignia.png",
        STATIC_DIR / "insignia.png",
        STATIC_DIR / "logo.png",
        ROOT_DIR / "app" / "static" / "imagen" / "insignia.png",
        ROOT_DIR / "app" / "static" / "logo.png"
    ]
    for candidate in logo_candidates:
        if candidate.exists():
            return FileResponse(str(candidate), media_type="image/png")
    return HTMLResponse(status_code=404, content="Logo not found")


# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(academic_router)
app.include_router(attendance_router)
app.include_router(evaluation_router)
app.include_router(assignment_router)
app.include_router(document_router)
app.include_router(mesa_partes_router)
app.include_router(communication_router)
app.include_router(audit_router)
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(support_router)
app.include_router(firewall_router)
app.include_router(whatsapp_router)

# Eventos de Ciclo de Vida: Monitor de Inteligencia Artificial y WhatsApp Gateway
@app.on_event("startup")
def startup_event():
    try:
        from app.database.connection import is_test_process
        if is_test_process():
            return
        from app.ai.ollama_monitor import ollama_monitor
        ollama_monitor.start_background_monitor(interval_seconds=15.0)

        # Iniciar WhatsApp Gateway (Baileys) en segundo plano
        from app.api.whatsapp_router import ensure_whatsapp_bot_running
        ensure_whatsapp_bot_running()
    except Exception as e:
        pass

@app.on_event("shutdown")
def shutdown_event():
    try:
        from app.ai.ollama_monitor import ollama_monitor
        ollama_monitor.stop_background_monitor()

        from app.api.whatsapp_router import _bot_subprocess
        if _bot_subprocess and _bot_subprocess.poll() is None:
            _bot_subprocess.terminate()
    except Exception as e:
        pass

# HTML Web Routes
@app.get("/", response_class=HTMLResponse)
def public_portal(request: Request):
    template_path = TEMPLATES_DIR / "public_portal.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    template_path = TEMPLATES_DIR / "login.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/intranet", response_class=HTMLResponse)
def intranet_portal(request: Request):
    template_path = TEMPLATES_DIR / "intranet.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/descargar-documento/{doc_id}")
@app.get("/descargar-plan-colegio")
def download_practice_doc(doc_id: int = 2):
    doc_map = {
        1: ("1_Plan_Practicas_Preprofesionales_UCV_Scrum.doc", "Plan_Practicas_Preprofesionales_UCV_Scrum.doc"),
        2: ("PLAN_DESARROLLO_PRACTICAS_INEI34_CHANCAY.doc", "Plan_Desarrollo_Practicas_INEI34_Chancay.doc"),
        3: ("3_Carta_Compromiso_Supervision_Virtual_UCV.doc", "Carta_Compromiso_Supervision_Virtual_UCV.doc")
    }
    if doc_id in doc_map:
        disk_name, dl_name = doc_map[doc_id]
        file_path = ROOT_DIR / "docs" / disk_name
        if file_path.exists():
            return FileResponse(
                str(file_path),
                filename=dl_name,
                media_type="application/msword"
            )
    return HTMLResponse(status_code=404, content="Documento no encontrado")

@app.get("/verificar-documento/{verification_code}", response_class=HTMLResponse)
def verify_document_view(verification_code: str, request: Request = None):
    """
    Página oficial pública de verificación de autenticidad institucional.
    I.E. INEI N.º 34 de Chancay • DRE Lima Provincias / UGEL 10 Huaral.
    Garantiza verificación de solo lectura, protección contra abusos y diferenciación v1/v2.
    """
    from app.api.ai_router import verify_document_code_api, check_verification_rate_limit

    # Control de tasa (Rate Limiting) para prevenir ataques de enumeración o denegación de servicio
    client_ip = (request.client.host if (request and request.client) else "127.0.0.1")
    if not check_verification_rate_limit(client_ip, max_requests=30, window_seconds=60):
        rate_limit_html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Límite de Consultas Excedido | INEI N.º 34 Chancay</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">
    <style>body { font-family: 'Plus Jakarta Sans', sans-serif; }</style>
</head>
<body class="bg-slate-100 min-h-screen flex items-center justify-center p-4 text-slate-800">
    <div class="bg-white rounded-3xl border border-amber-300 p-8 max-w-md w-full text-center shadow-xl space-y-4">
        <div class="w-16 h-16 mx-auto rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center text-3xl">
            <i class="fa-solid fa-hand-palm"></i>
        </div>
        <div class="text-xs font-mono font-bold tracking-widest text-amber-800 uppercase">Seguridad Institucional</div>
        <h1 class="text-xl font-black text-slate-900">LÍMITE DE CONSULTAS EXCEDIDO</h1>
        <p class="text-xs text-slate-600 leading-relaxed">
            Por motivos de protección contra consultas automatizadas o ataques de fuerza bruta, se ha alcanzado el límite de <strong>30 solicitudes por minuto</strong> para su dirección de red.
        </p>
        <p class="text-[11px] text-slate-500 font-mono bg-slate-50 p-2.5 rounded-xl border border-slate-200">
            Espere 60 segundos antes de intentar una nueva verificación.
        </p>
        <div class="pt-2">
            <a href="/" class="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs px-5 py-2.5 rounded-xl transition shadow">
                <i class="fa-solid fa-house"></i> Volver al Portal Institucional
            </a>
        </div>
    </div>
</body>
</html>"""
        return HTMLResponse(status_code=429, content=rate_limit_html)

    res = verify_document_code_api(verification_code, request=request)

    status_code = res.get("status", "NO_VALIDO")
    title = res.get("document_title", "Documento Pedagógico")
    approver = res.get("approver_name", "Lic. César Tinedo Jiménez")
    approved_at = res.get("approved_at", "—")
    revoked_at = res.get("revoked_at", "—")
    reason = res.get("revocation_reason", "")
    code = res.get("verification_code", verification_code)
    doc_hash = res.get("document_hash", "")
    canonical_schema = res.get("canonical_schema", "v2_canonical (Estándar Actual Completo)")
    verification_subject = res.get("verification_subject", "Contenido Pedagógico Oficial Visado por Dirección")
    integrity_ok = res.get("integrity_valid", False)
    is_valid = res.get("is_official_seal_valid", False)
    is_v1_legacy = res.get("is_v1_legacy", False)
    integrity_scope = res.get("integrity_scope", "Integridad del contenido pedagógico")
    warning_notice = res.get("warning_notice")

    # Banner de Estado
    if is_valid and not is_v1_legacy:
        badge_html = f"""
        <div class="bg-emerald-50 border-2 border-emerald-400 rounded-2xl p-5 text-center shadow-sm">
            <div class="w-14 h-14 mx-auto rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-2xl mb-2">
                <i class="fa-solid fa-shield-check"></i>
            </div>
            <div class="text-xs font-mono font-bold tracking-widest text-emerald-800 uppercase">Estado de Autenticidad</div>
            <div class="text-xl font-black text-emerald-700 mt-0.5">VISADO DIGITAL INSTITUCIONAL VÁLIDO • INTEGRIDAD COMPLETA (v2)</div>
            <p class="text-xs text-emerald-700 mt-1 max-w-md mx-auto">
                La autenticidad e integridad del 100% del contenido pedagógico y la estructura curricular han sido verificadas en tiempo real contra el repositorio institucional oficial.
            </p>
        </div>
        """
    elif is_valid and is_v1_legacy:
        badge_html = f"""
        <div class="bg-amber-50 border-2 border-amber-400 rounded-2xl p-5 text-center shadow-sm">
            <div class="w-14 h-14 mx-auto rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-2xl mb-2">
                <i class="fa-solid fa-clock-rotate-left"></i>
            </div>
            <div class="text-xs font-mono font-bold tracking-widest text-amber-800 uppercase">Visado Histórico Registrado</div>
            <div class="text-xl font-black text-amber-900 mt-0.5">VISADO DIGITAL HISTÓRICO (MÉTODO ANTERIOR v1)</div>
            <p class="text-xs text-amber-800 mt-1 max-w-md mx-auto font-medium">
                Documento visado bajo la versión anterior del protocolo. Verificación limitada a cabecera y primeros 500 caracteres.
            </p>
        </div>
        """
    elif status_code == "APROBADO" and not integrity_ok:
        badge_html = f"""
        <div class="bg-amber-50 border-2 border-red-400 rounded-2xl p-5 text-center shadow-sm">
            <div class="w-14 h-14 mx-auto rounded-full bg-red-100 text-red-600 flex items-center justify-center text-2xl mb-2">
                <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
            <div class="text-xs font-mono font-bold tracking-widest text-red-800 uppercase">Alerta de Integridad</div>
            <div class="text-xl font-black text-red-700 mt-0.5">INTEGRIDAD COMPROMETIDA (CONTENIDO MODIFICADO)</div>
            <p class="text-xs text-red-700 mt-1 max-w-md mx-auto">
                El código de visado existe pero el contenido pedagógico actual en la base de datos no coincide con la huella digital criptográfica generada durante la aprobación directiva.
            </p>
        </div>
        """
    elif status_code == "REVOCADO":
        badge_html = f"""
        <div class="bg-red-50 border border-red-300 rounded-2xl p-5 text-center shadow-sm">
            <div class="w-14 h-14 mx-auto rounded-full bg-red-100 text-red-600 flex items-center justify-center text-2xl mb-2">
                <i class="fa-solid fa-ban"></i>
            </div>
            <div class="text-xs font-mono font-bold tracking-widest text-red-800 uppercase">Estado de Autenticidad</div>
            <div class="text-xl font-black text-red-700 mt-0.5">VISADO REVOCADO FORMALMENTE</div>
            <p class="text-xs text-red-600 mt-1 max-w-md mx-auto">
                Este visado directivo fue revocado formalmente el {revoked_at}. Motivo: {reason}
            </p>
        </div>
        """
    else:
        badge_html = """
        <div class="bg-slate-50 border border-slate-300 rounded-2xl p-5 text-center shadow-sm">
            <div class="w-14 h-14 mx-auto rounded-full bg-slate-200 text-slate-500 flex items-center justify-center text-2xl mb-2">
                <i class="fa-solid fa-circle-xmark"></i>
            </div>
            <div class="text-xs font-mono font-bold tracking-widest text-slate-600 uppercase">Estado de Autenticidad</div>
            <div class="text-xl font-black text-slate-800 mt-0.5">CÓDIGO DE VERIFICACIÓN NO REGISTRADO</div>
            <p class="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                El código consultado no corresponde a ningún documento visado en el repositorio institucional oficial.
            </p>
        </div>
        """

    # Advertencia específica si es v1_legacy
    legacy_warning_html = ""
    if is_v1_legacy and warning_notice:
        legacy_warning_html = f"""
        <div class="p-3.5 bg-amber-50 border border-amber-300 rounded-xl text-xs text-amber-900 space-y-1">
            <div class="font-bold flex items-center gap-1.5 text-amber-950">
                <i class="fa-solid fa-triangle-exclamation text-amber-600"></i> Alcance de Integridad: Validación Parcial (v1)
            </div>
            <p class="text-[11.5px] leading-relaxed">
                {warning_notice}
            </p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verificación de Autenticidad Documental | INEI N.º 34 Chancay</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800 flex flex-col justify-between">
    <!-- Header Institucional -->
    <header class="bg-slate-900 border-b border-red-900/40 text-white py-4 px-6 shadow-md">
        <div class="max-w-4xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-red-900/60 border border-red-500/40 flex items-center justify-center text-white font-black text-lg">
                    34
                </div>
                <div>
                    <h1 class="text-sm font-black tracking-wide uppercase text-white">I.E. INEI N.º 34</h1>
                    <p class="text-[10px] text-slate-400 font-medium">Chancay • DRE Lima Provincias • UGEL 10 Huaral</p>
                </div>
            </div>
            <div class="text-right">
                <span class="text-[10px] font-mono font-bold px-2.5 py-1 rounded bg-red-950 border border-red-500/40 text-red-200">
                    SISTEMA DE VERIFICACIÓN QR
                </span>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-3xl w-full mx-auto p-4 sm:p-6 my-auto space-y-5">
        <!-- Badge Status -->
        {badge_html}

        <!-- Legacy Warning Banner if applicable -->
        {legacy_warning_html}

        <!-- Document Details Card -->
        <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4 text-xs">
            <div class="flex justify-between items-center pb-3 border-b border-slate-100">
                <div class="font-bold text-slate-700 text-sm flex items-center gap-2">
                    <i class="fa-solid fa-file-shield text-ineiRed"></i>
                    Visado Digital Institucional con Verificación de Integridad Criptográfica SHA-256
                </div>
                <span class="text-[10px] font-mono font-bold bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded border border-slate-200">
                    CÓDIGO: {code}
                </span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <div class="text-[10px] font-mono text-slate-400 font-bold uppercase">Título del Documento</div>
                    <div class="font-extrabold text-slate-900 text-sm mt-0.5">{title}</div>
                </div>
                <div>
                    <div class="text-[10px] font-mono text-slate-400 font-bold uppercase">Tipo y Especialidad Técnica</div>
                    <div class="font-bold text-slate-800 mt-0.5">{res.get('document_type', 'Planificación')} &bull; {res.get('specialty', 'EPT')} ({res.get('grade', '1')}° {res.get('section_name', 'Sec.')})</div>
                </div>
                <div>
                    <div class="text-[10px] font-mono text-slate-400 font-bold uppercase">Autoridad Aprobante</div>
                    <div class="font-bold text-slate-800 mt-0.5">{approver} <span class="text-[10px] text-slate-500 font-medium">({res.get('approver_role', 'DIRECTOR GENERAL')})</span></div>
                </div>
                <div>
                    <div class="text-[10px] font-mono text-slate-400 font-bold uppercase">Fecha y Hora de Visado</div>
                    <div class="font-mono font-bold text-slate-800 mt-0.5">{approved_at}</div>
                </div>
            </div>

            <!-- Criptografía e Integridad -->
            <div class="pt-3 border-t border-slate-100 space-y-2">
                <div class="flex items-center justify-between">
                    <div>
                        <span class="text-[10px] font-mono text-slate-400 font-bold uppercase">Objeto Certificado</span>
                        <div class="font-bold text-slate-800 text-[11px]">{verification_subject}</div>
                    </div>
                    <span class="text-[10px] font-mono font-bold { 'text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded' if integrity_ok else 'text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded' }">
                        { 'CONFORME (SIN ALTERACIONES)' if integrity_ok else 'INTEGRIDAD COMPROMETIDA' }
                    </span>
                </div>
                <div class="space-y-1">
                    <div class="text-[9px] font-mono text-slate-400 uppercase font-bold">
                        Esquema Canónico: <span class="text-slate-700 font-semibold">{canonical_schema}</span>
                    </div>
                    <div class="text-[9px] text-slate-500 font-medium">
                        Alcance: {integrity_scope}
                    </div>
                    <div class="font-mono text-[10px] text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-200 break-all select-all">
                        {doc_hash if doc_hash else 'No registrado'}
                    </div>
                </div>
            </div>

            <!-- Distinción Técnica y Disclaimer Institucional -->
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-200 text-[11px] text-slate-600 leading-relaxed space-y-2">
                <div class="font-bold text-slate-800 flex items-center gap-1.5">
                    <i class="fa-solid fa-circle-check text-emerald-600"></i> Distinción Técnica de Integridad Documental
                </div>
                <p>
                    1. <strong>Integridad del Contenido:</strong> El hash SHA-256 superior certifica la inmutabilidad exacta del contenido pedagógico y rúbricas CNEB aprobados por la Dirección General.<br/>
                    2. <strong>Archivos Oficiales Descargados:</strong> Los documentos exportados en Word (.docx) y PDF (.pdf) incluyen en sus cabeceras HTTP la huella de contenido <code>X-Content-SHA256</code> y la huella del binario generado <code>X-Export-File-SHA256</code>.<br/>
                    3. <strong>Naturaleza Legal y Control Interno:</strong> Mecanismo de supervisión técnico-pedagógica y control interno institucional de la I.E. INEI N.º 34 de Chancay (DRE Lima Provincias / UGEL 10 Huaral). No constituye firma digital acreditada bajo la Ley N.º 27269 (IOFE/INDECOPI).
                </p>
            </div>
        </div>

        <div class="flex justify-center gap-3">
            <button onclick="window.print()" class="bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs px-4 py-2 rounded-xl border border-slate-300 shadow-sm transition flex items-center gap-1.5">
                <i class="fa-solid fa-print"></i> Imprimir Constancia
            </button>
            <a href="/" class="bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs px-4 py-2 rounded-xl shadow transition flex items-center gap-1.5">
                <i class="fa-solid fa-house"></i> Portal Institucional
            </a>
        </div>
    </main>

    <!-- Footer -->
    <footer class="text-center py-4 text-xs text-slate-400 border-t border-slate-200">
        I.E. INEI N.º 34 • Chancay, Perú &bull; Plataforma INEI SMART-CORE
    </footer>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/health")
def health_check():
    return {"status": "healthy", "system": "INEI SMART-CORE 2.0", "institution": "I.E. INEI N° 34 Chancay"}
