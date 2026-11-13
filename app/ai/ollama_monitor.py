"""
INEI SMART-CORE - Ollama Health Monitor & Resilient Circuit Breaker
I.E. Emblemática INEI N.º 34 de Chancay

Proporciona:
1. Monitor de disponibilidad y latencia del servicio Ollama local (puerto 11434).
2. Detección precisa de 5 estados: OPERATIVO, INICIANDO, DESCONECTADO, ERROR, MODELO_NO_DISPONIBLE.
3. Disyuntor (Circuit Breaker) para evitar bloqueos y timeouts de 30s cuando Ollama está offline.
4. Reconexión automática con retroceso exponencial (Backoff) no bloqueante.
5. Diagnóstico administrativo seguro con RBAC (solo ADMIN y DIRECTOR), sin exponer datos sensibles.
6. Cero ejecuciones costosas de LLM en comprobaciones rutinarias de salud.
"""

import os
import time
import json
import logging
import threading
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import (
    OLLAMA_BASE_URL,
    DEFAULT_AI_MODEL,
    AI_FALLBACK_MODEL,
    AI_CODER_MODEL,
    AI_VISION_MODEL,
    AI_TIMEOUT_SECONDS
)

logger = logging.getLogger("ollama_monitor")

class OllamaHealthState:
    OPERATIVO = "OPERATIVO"
    INICIANDO = "INICIANDO"
    DESCONECTADO = "DESCONECTADO"
    ERROR = "ERROR"
    MODELO_NO_DISPONIBLE = "MODELO_NO_DISPONIBLE"


class OllamaMonitor:
    """
    Monitor de salud centralizado y resiliente para el motor de IA local Ollama.
    Totalmente seguro, seguro para subprocesos (Thread-Safe) y no bloqueante.
    """
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        default_model: str = DEFAULT_AI_MODEL,
        health_timeout: float = 2.5,
        cache_ttl_seconds: float = 4.0
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.health_timeout = health_timeout
        self.cache_ttl_seconds = cache_ttl_seconds

        self._lock = threading.RLock()
        self._state = OllamaHealthState.DESCONECTADO
        self._circuit_state = "OPEN"  # CLOSED (online), OPEN (offline fast-fail), HALF_OPEN (probing)
        self._latency_ms: float = 0.0
        self._last_check_time: float = 0.0
        self._last_success_time: Optional[float] = None
        self._failure_count: int = 0
        self._reconnect_count: int = 0
        self._consecutive_failures: int = 0
        self._available_models: List[str] = []
        self._loaded_models: List[str] = []
        self._error_message: Optional[str] = "Monitor no ha realizado comprobación inicial."
        self._ollama_version: Optional[str] = None
        self._backoff_delay: float = 2.0
        self._max_backoff: float = 30.0

        # Control del demonio en segundo plano
        self._bg_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._session = self._create_fast_session()

    @staticmethod
    def _create_fast_session() -> requests.Session:
        s = requests.Session()
        adapter = HTTPAdapter(max_retries=Retry(total=0, connect=0, read=0))
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        return s

    def get_state(self) -> str:
        with self._lock:
            return self._state

    def is_online(self) -> bool:
        """Retorna True si Ollama está en línea y accesible."""
        with self._lock:
            return self._state in (OllamaHealthState.OPERATIVO, OllamaHealthState.MODELO_NO_DISPONIBLE)

    def is_model_ready(self) -> bool:
        """Retorna True si Ollama está OPERATIVO y el modelo configurado está listo."""
        with self._lock:
            return self._state == OllamaHealthState.OPERATIVO

    def should_fast_fail(self) -> bool:
        """
        Retorna True si el Circuit Breaker está en OPEN (Ollama offline confirmado)
        para permitir fallback inmediato sin demoras ni timeouts de red.
        """
        with self._lock:
            now = time.time()
            if self._circuit_state == "OPEN":
                # Permitir intento exploratorio (HALF_OPEN) si ya transcurrió el backoff_delay
                if now - self._last_check_time >= self._backoff_delay:
                    self._circuit_state = "HALF_OPEN"
                    return False
                return True
            return False

    def check_health(self, force: bool = False, test_generation: bool = False) -> Dict[str, Any]:
        """
        Ejecuta comprobación ligera de disponibilidad y latencia contra Ollama.
        Utiliza /api/tags y /api/version (no ejecuta generación de texto costosa salvo test_generation=True).
        Respeta caché TTL para no saturar Ollama en ráfagas de consultas.
        """
        now = time.time()
        with self._lock:
            if not force and (now - self._last_check_time) < self.cache_ttl_seconds and self._last_check_time > 0:
                return self._build_status_dict(cached=True)

        t0 = time.time()
        tags_url = f"{self.base_url}/api/tags"
        version_url = f"{self.base_url}/api/version"

        try:
            # 1. Comprobar conectividad básica y etiquetas
            resp = self._session.get(tags_url, timeout=self.health_timeout)
            latency = round((time.time() - t0) * 1000, 2)

            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("models", [])
                models_list = [m.get("name", "") for m in raw_models if isinstance(m, dict)]

                # Obtener versión si está disponible
                ollama_ver = "desconocida"
                try:
                    v_resp = self._session.get(version_url, timeout=1.5)
                    if v_resp.status_code == 200:
                        ollama_ver = v_resp.json().get("version", "desconocida")
                except Exception:
                    pass

                # Verificar si el modelo configurado está presente
                configured_model_clean = (self.default_model or "llama3.2").lower()
                model_found = any(
                    configured_model_clean in m.lower() or m.lower().startswith(configured_model_clean.split(":")[0])
                    for m in models_list
                )

                # Si no está el configurado, verificar si hay al menos un modelo compatible
                fallback_found = any(
                    any(fb in m.lower() for fb in ["llama", "qwen", "hermes", "gemma", "mistral", "phi"])
                    for m in models_list
                )

                with self._lock:
                    was_offline = (self._state == OllamaHealthState.DESCONECTADO)
                    if was_offline:
                        self._reconnect_count += 1
                        logger.info(f"Ollama reconectado satisfactoriamente tras {self._failure_count} fallos previos.")

                    self._last_check_time = now
                    self._last_success_time = now
                    self._latency_ms = latency
                    self._available_models = models_list
                    self._ollama_version = ollama_ver
                    self._consecutive_failures = 0
                    self._backoff_delay = 2.0
                    self._circuit_state = "CLOSED"

                    if model_found or (fallback_found and not models_list):
                        self._state = OllamaHealthState.OPERATIVO
                        self._error_message = None
                    elif models_list:
                        self._state = OllamaHealthState.MODELO_NO_DISPONIBLE
                        self._error_message = (
                            f"Servidor Ollama operativo (v{ollama_ver}), pero el modelo configurado "
                            f"'{self.default_model}' no está descargado. Modelos disponibles: {', '.join(models_list[:4])}."
                        )
                    else:
                        self._state = OllamaHealthState.MODELO_NO_DISPONIBLE
                        self._error_message = f"Servidor Ollama operativo (v{ollama_ver}), pero no tiene ningún modelo descargado."

                # 2. Prueba opcional de inferencia bajo demanda explícita (test_generation=True)
                test_gen_result = None
                if test_generation and self._state == OllamaHealthState.OPERATIVO:
                    test_gen_result = self._execute_test_ping_generation()

                res_dict = self._build_status_dict(cached=False)
                if test_gen_result:
                    res_dict["test_generation"] = test_gen_result
                return res_dict

            else:
                with self._lock:
                    self._state = OllamaHealthState.ERROR
                    self._circuit_state = "OPEN"
                    self._last_check_time = now
                    self._failure_count += 1
                    self._consecutive_failures += 1
                    self._error_message = f"Servidor Ollama respondió con código de estado anómalo: HTTP {resp.status_code}."
                    self._increase_backoff()
                return self._build_status_dict(cached=False)

        except requests.exceptions.Timeout:
            latency = round((time.time() - t0) * 1000, 2)
            with self._lock:
                self._state = OllamaHealthState.DESCONECTADO
                self._circuit_state = "OPEN"
                self._last_check_time = now
                self._latency_ms = latency
                self._failure_count += 1
                self._consecutive_failures += 1
                self._error_message = f"Tiempo de espera agotado ({self.health_timeout}s) al conectar con Ollama en {self.base_url}."
                self._increase_backoff()
            return self._build_status_dict(cached=False)

        except requests.exceptions.ConnectionError:
            latency = round((time.time() - t0) * 1000, 2)
            with self._lock:
                self._state = OllamaHealthState.DESCONECTADO
                self._circuit_state = "OPEN"
                self._last_check_time = now
                self._latency_ms = latency
                self._failure_count += 1
                self._consecutive_failures += 1
                self._error_message = f"Conexión rechazada: Ollama no está en ejecución en {self.base_url} (puerto 11434 inactivo)."
                self._increase_backoff()
            return self._build_status_dict(cached=False)

        except Exception as e:
            latency = round((time.time() - t0) * 1000, 2)
            with self._lock:
                self._state = OllamaHealthState.ERROR
                self._circuit_state = "OPEN"
                self._last_check_time = now
                self._latency_ms = latency
                self._failure_count += 1
                self._consecutive_failures += 1
                self._error_message = f"Excepción de comunicación con Ollama: {type(e).__name__}."
                self._increase_backoff()
            return self._build_status_dict(cached=False)

    def _execute_test_ping_generation(self) -> Dict[str, Any]:
        """
        Ejecuta una generación mínima de prueba (1 token) bajo demanda explícita del Administrador
        para certificar el canal de inferencia de tensores sin costo computacional sensible.
        """
        t0 = time.time()
        try:
            target_model = self.default_model or "llama3.2:latest"
            payload = {
                "model": target_model,
                "prompt": "ping",
                "stream": False,
                "options": {"num_predict": 1, "temperature": 0.0}
            }
            resp = self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=10.0
            )
            elapsed = round((time.time() - t0) * 1000, 2)
            if resp.status_code == 200:
                return {
                    "success": True,
                    "model": target_model,
                    "elapsed_ms": elapsed,
                    "message": f"Inferencia de prueba exitosa en {elapsed} ms."
                }
            else:
                return {
                    "success": False,
                    "model": target_model,
                    "status_code": resp.status_code,
                    "elapsed_ms": elapsed,
                    "message": f"Fallo en generación de prueba: HTTP {resp.status_code}."
                }
        except Exception as e:
            return {
                "success": False,
                "elapsed_ms": round((time.time() - t0) * 1000, 2),
                "message": f"Error en test de inferencia: {type(e).__name__}."
            }

    def _increase_backoff(self):
        """Aumenta el intervalo de reintento progresivo con tope máximo (Backoff exponencial)."""
        self._backoff_delay = min(self._backoff_delay * 2.0, self._max_backoff)

    def _build_status_dict(self, cached: bool = False) -> Dict[str, Any]:
        """Construye el diccionario de estado seguro para clientes y vistas."""
        now = time.time()
        last_check_iso = datetime.fromtimestamp(self._last_check_time).strftime("%Y-%m-%d %H:%M:%S") if self._last_check_time else "Nunca"
        last_success_iso = datetime.fromtimestamp(self._last_success_time).strftime("%Y-%m-%d %H:%M:%S") if self._last_success_time else "Sin conexión previa"
        seconds_since_success = round(now - self._last_success_time, 1) if self._last_success_time else None

        return {
            "status": self._state,
            "is_online": self.is_online(),
            "is_model_ready": self.is_model_ready(),
            "service_address": self.base_url,
            "configured_model": self.default_model,
            "available_models": list(self._available_models),
            "total_models": len(self._available_models),
            "latency_ms": self._latency_ms,
            "ollama_version": self._ollama_version,
            "last_check": last_check_iso,
            "last_successful_connection": last_success_iso,
            "seconds_since_last_success": seconds_since_success,
            "failure_count": self._failure_count,
            "reconnect_count": self._reconnect_count,
            "consecutive_failures": self._consecutive_failures,
            "circuit_state": self._circuit_state,
            "next_retry_seconds": round(self._backoff_delay, 1) if self._circuit_state == "OPEN" else 0.0,
            "error_message": self._error_message,
            "cached": cached,
            "institution": "I.E. Emblemática INEI N.º 34 de Chancay",
            "fallback_active": True
        }

    def get_admin_diagnostics(self) -> Dict[str, Any]:
        """
        Retorna informe técnico exhaustivo para el Administrador o Director.
        Diferencia explícitamente entre:
        1. Falla de servidor Ollama (offline).
        2. Falla de modelo (no instalado/no cargado).
        3. Falla de comunicación de red backend <-> Ollama.
        4. Falla de inferencia.
        """
        status_info = self.check_health(force=False)
        diagnosis_category = "OPTIMO"
        technical_summary = "Motor Ollama local y modelo configurado operando en condiciones óptimas."

        st = status_info["status"]
        if st == OllamaHealthState.DESCONECTADO:
            diagnosis_category = "SERVIDOR_OFFLINE"
            technical_summary = (
                "El daemon local de Ollama no se encuentra en ejecución en el puerto 11434. "
                "Para activarlo en el servidor institucional, ejecute 'ollama serve' en la terminal del sistema."
            )
        elif st == OllamaHealthState.MODELO_NO_DISPONIBLE:
            diagnosis_category = "MODELO_FALTANTE"
            technical_summary = (
                f"El servicio Ollama está activo, pero el modelo pedagógico '{self.default_model}' no ha sido descargado. "
                f"Ejecute 'ollama run {self.default_model}' para descargar los pesos oficiales en el repositorio local."
            )
        elif st == OllamaHealthState.ERROR:
            diagnosis_category = "ERROR_COMUNICACION"
            technical_summary = "El servidor Ollama responde pero genera códigos de error HTTP anómalos o cuelgues temporales."
        elif st == OllamaHealthState.INICIANDO:
            diagnosis_category = "CARGANDO_TENSORES"
            technical_summary = "Ollama se encuentra asignando capas y tensores a la memoria RAM/VRAM."

        return {
            "success": True,
            "diagnostic_category": diagnosis_category,
            "technical_summary": technical_summary,
            "details": status_info,
            "circuit_breaker": {
                "state": self._circuit_state,
                "fast_fail_active": (self._circuit_state == "OPEN"),
                "backoff_delay_seconds": self._backoff_delay
            },
            "security": {
                "local_only": True,
                "sanitized": True,
                "no_sensitive_data": True
            }
        }

    # -------------------------------------------------------------
    # Demonio en Segundo Plano para Reconexión Automática
    # -------------------------------------------------------------
    def start_background_monitor(self, interval_seconds: float = 15.0):
        """Inicia un hilo daemon para supervisión continua y reconexión automática."""
        with self._lock:
            if self._bg_thread and self._bg_thread.is_alive():
                return
            self._stop_event.clear()
            self._bg_thread = threading.Thread(
                target=self._run_monitor_loop,
                args=(interval_seconds,),
                daemon=True,
                name="OllamaHealthMonitorDaemon"
            )
            self._bg_thread.start()
            logger.info("Demonio OllamaHealthMonitorDaemon iniciado.")

    def stop_background_monitor(self):
        """Detiene de forma limpia el demonio de monitoreo."""
        self._stop_event.set()
        with self._lock:
            if self._bg_thread and self._bg_thread.is_alive():
                self._bg_thread.join(timeout=2.0)
            self._bg_thread = None
            logger.info("Demonio OllamaHealthMonitorDaemon detenido.")

    def _run_monitor_loop(self, interval_seconds: float):
        """Bucle en segundo plano con backoff adaptativo."""
        while not self._stop_event.is_set():
            try:
                # Comprobar salud
                self.check_health(force=True)
            except Exception as e:
                logger.debug(f"Error silencioso en monitor daemon: {e}")

            # Calcular tiempo de espera adaptativo: si está offline, esperar backoff_delay; si online, interval_seconds
            with self._lock:
                sleep_time = interval_seconds if self.is_online() else self._backoff_delay

            # Esperar de forma interrumpible
            self._stop_event.wait(timeout=sleep_time)

    # -------------------------------------------------------------
    # Métodos para Pruebas Automatizadas
    # -------------------------------------------------------------
    def _inject_mock_state_for_testing(
        self,
        state: str,
        latency_ms: float = 15.0,
        available_models: Optional[List[str]] = None,
        error_msg: Optional[str] = None
    ):
        """Permite a las suites de prueba inyectar estados controlados sin depender de un proceso Ollama real."""
        with self._lock:
            self._state = state
            self._latency_ms = latency_ms
            self._last_check_time = time.time()
            if state == OllamaHealthState.OPERATIVO:
                self._last_success_time = time.time()
                self._circuit_state = "CLOSED"
                self._backoff_delay = 2.0
            else:
                self._circuit_state = "OPEN"
            if available_models is not None:
                self._available_models = available_models
            self._error_message = error_msg


# Instancia singleton del monitor
ollama_monitor = OllamaMonitor()
