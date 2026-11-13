"""
INEI SMART-CORE — Módulo Opcional de Precalentamiento de Modelos Locales
I.E. Emblemática INEI N.º 34 de Chancay

Carga de forma no bloqueante y controlada los tensores del modelo en memoria RAM/VRAM
para reducir la latencia de la primera consulta docente de ~74 s a ~19 s.

Características de Seguridad:
1. Control por variable de entorno PREWARM_OLLAMA (por defecto: desactivado '0').
2. Timeout estricto y no bloqueante.
3. Si Ollama no está disponible o falla, no impide el inicio de la plataforma.
4. Cero exposición de información confidencial.
"""

import os
import time
import json
import logging
import threading
import requests
from typing import Dict, Any, Optional

from app.config import OLLAMA_BASE_URL, DEFAULT_AI_MODEL, AI_KEEP_ALIVE

logger = logging.getLogger("smartteacher_prewarm")

def get_prewarm_status() -> Dict[str, Any]:
    """Consulta el estado actual de los modelos en memoria en Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=3.0)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return {"available": True, "loaded_models": models}
    except Exception as e:
        logger.debug(f"Ollama no disponible en {OLLAMA_BASE_URL}: {e}")
    return {"available": False, "loaded_models": []}

def prewarm_ollama_model(
    model_name: str = DEFAULT_AI_MODEL,
    timeout: float = 30.0,
    keep_alive: str = AI_KEEP_ALIVE
) -> Dict[str, Any]:
    """
    Envía una petición de precarga a Ollama sin generar texto para cargar pesos en memoria.
    Retorna un diccionario con métricas de tiempo y estado.
    """
    enabled = os.getenv("PREWARM_OLLAMA", "0").strip().lower() in ("1", "true", "yes")
    if not enabled:
        return {
            "status": "skipped",
            "message": "Precalentamiento desactivado (PREWARM_OLLAMA=0)."
        }

    t0 = time.time()
    try:
        # 1. Verificar si Ollama responde
        check_resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if check_resp.status_code != 200:
            return {"status": "unavailable", "message": "Ollama no responde en el puerto 11434."}

        # 2. Verificar si el modelo ya está cargado
        ps_resp = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=3.0)
        if ps_resp.status_code == 200:
            loaded = [m.get("name") for m in ps_resp.json().get("models", [])]
            if any(model_name in m for m in loaded if m):
                return {
                    "status": "already_warm",
                    "model": model_name,
                    "elapsed_sec": time.time() - t0,
                    "message": f"El modelo {model_name} ya se encuentra cargado en memoria."
                }

        # 3. Precarga de tensores en Ollama
        logger.info(f"Iniciando precarga en segundo plano de {model_name} en Ollama...")
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model_name, "keep_alive": keep_alive},
            timeout=timeout
        )
        elapsed = time.time() - t0
        if resp.status_code == 200:
            logger.info(f"Modelo {model_name} precalentado exitosamente en {elapsed:.2f} s.")
            return {
                "status": "success",
                "model": model_name,
                "elapsed_sec": elapsed,
                "message": f"Modelo precargado en {elapsed:.2f} s con keep_alive={keep_alive}."
            }
        else:
            return {
                "status": "error",
                "status_code": resp.status_code,
                "elapsed_sec": elapsed,
                "message": f"Respuesta no esperada de Ollama: HTTP {resp.status_code}."
            }
    except requests.exceptions.Timeout:
        elapsed = time.time() - t0
        logger.warning(f"Timeout de precalentamiento tras {elapsed:.1f} s. El sistema continuará normalmente.")
        return {"status": "timeout", "elapsed_sec": elapsed, "message": "Tiempo de espera agotado al precargar el modelo."}
    except Exception as e:
        elapsed = time.time() - t0
        logger.warning(f"Aviso no crítico durante precalentamiento: {e}")
        return {"status": "failed", "elapsed_sec": elapsed, "error": str(e)}

def start_prewarm_in_background(model_name: str = DEFAULT_AI_MODEL):
    """Lanza el precalentamiento en un hilo daemon para no retrasar el inicio del servidor."""
    if os.getenv("PREWARM_OLLAMA", "0").strip().lower() in ("1", "true", "yes"):
        th = threading.Thread(target=prewarm_ollama_model, args=(model_name,), daemon=True)
        th.start()
        return th
    return None

if __name__ == "__main__":
    os.environ["PREWARM_OLLAMA"] = "1"
    res = prewarm_ollama_model()
    print("Resultado de precalentamiento:", json.dumps(res, indent=2))
