"""
INEI SMART-CORE v2.8 - Servicio Centralizado de Firewall Inteligente (Endurecido v2.8.4)
Institución: I.E. Emblemática INEI N.º 34 de Chancay
Módulo: app/security/firewall_service.py

Responsabilidades Endurecidas (Etapa 3.1):
1. Identificación y normalización estricta de IPv4 e IPv6.
2. Procesamiento seguro de cadenas de proxies de derecha a izquierda (Right-to-Left Trust).
3. Protección de redes escolares compartidas (trusted_school_subnets) evitando vetos a aulas completas.
4. Protección contra Account DoS mediante bloqueo combinado (account_identifier + ip_address).
5. Eliminación de retardos bloqueantes (time.sleep) en autenticación, reemplazados por HTTP 429 con Retry-After.
6. Política de retención y depuración transaccional (7d login attempts, 60d events, 90d inactive bans).
7. Degradación elegante (Fail-Open) con diagnóstico de salud para el panel administrativo.
8. Documentación explícita de arquitectura de un solo worker (In-Process Sliding Window).
"""

import ipaddress
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from fastapi import Request

from app.database.connection import get_db
import app.config as config

logger = logging.getLogger("firewall_service")

class FirewallService:
    def __init__(self):
        self._lock = threading.Lock()
        # Estructura en memoria para Rate Limiting con ventana deslizante por proceso:
        # { (ip, category): [timestamp1, timestamp2, ...] }
        self._rate_limits: Dict[Tuple[str, str], List[float]] = {}
        
        # Caché de configuraciones para evitar lecturas continuas a SQLite en cada paquete
        self._settings_cache: Dict[str, str] = {}
        self._settings_last_fetch = 0.0
        self._settings_cache_ttl = 30.0  # Refrescar cada 30 segundos
        
        # Estado de salud del servicio (Degradación elegante / Fail-Open)
        self._health_status = "OPERATIONAL"
        self._health_error_detail: Optional[str] = None
        self._last_health_check = 0.0

    # =========================================================================
    # 1. IDENTIFICACIÓN Y NORMALIZACIÓN DE IP
    # =========================================================================
    def normalize_ip(self, ip_str: Optional[str]) -> Optional[str]:
        """
        Valida y normaliza una dirección IPv4 o IPv6 utilizando ipaddress estándar.
        Retorna la representación canónica (.compressed) o None si es inválida.
        """
        if not ip_str or not isinstance(ip_str, str):
            return None
        clean_ip = ip_str.strip()
        # Manejar formato IPv6 con puerto o corchetes ej: [::1]:8000
        if clean_ip.startswith("[") and "]" in clean_ip:
            clean_ip = clean_ip[1:clean_ip.index("]")]
        elif ":" in clean_ip and clean_ip.count(":") == 1:
            # Caso IPv4 con puerto ej: 192.168.1.50:8080
            clean_ip = clean_ip.split(":")[0]
            
        try:
            parsed = ipaddress.ip_address(clean_ip)
            return parsed.compressed
        except ValueError:
            return None

    def is_trusted_school_network(self, ip_str: str) -> bool:
        """
        Determina si una dirección IP pertenece a las subredes escolares institucionales confiables.
        Las IPs en subredes escolares NUNCA reciben vetos automáticos globales por comportamiento compartido.
        """
        norm_ip = self.normalize_ip(ip_str)
        if not norm_ip:
            return False

        # Loopback e interfaces locales siempre son tratadas como red institucional local
        if norm_ip in ("127.0.0.1", "::1"):
            return True

        settings = self.get_settings()
        raw_subnets = settings.get("trusted_school_subnets", "").strip()
        if not raw_subnets:
            return False

        try:
            target_ip_obj = ipaddress.ip_address(norm_ip)
            subnets = [s.strip() for s in raw_subnets.split(",") if s.strip()]
            for s in subnets:
                try:
                    net = ipaddress.ip_network(s, strict=False)
                    if target_ip_obj in net:
                        return True
                except ValueError:
                    logger.warning(f"Subred inválida en trusted_school_subnets: {s}")
        except Exception as e:
            logger.error(f"Error evaluando pertenencia a subred escolar: {e}")

        return False

    def extract_client_ip(self, request: Optional[Request]) -> str:
        """
        Extrae la IP real del cliente con validación estricta de proxies confiables.
        Procesamiento de cadenas de proxies de Derecha a Izquierda (Right-to-Left Trust Chain).
        - Si la conexión directa no procede de un proxy confiable, se descartan cabeceras reenviadas.
        - Si procede de proxy confiable, se evalúa X-Forwarded-For de derecha a izquierda.
        """
        if not request or not getattr(request, "client", None):
            return "127.0.0.1"

        raw_direct = request.client.host if request.client else "127.0.0.1"
        direct_ip = self.normalize_ip(raw_direct) or "127.0.0.1"

        trusted = self.get_trusted_proxies()
        if direct_ip not in trusted:
            # Cliente no es proxy autorizado: NO confiar en cabeceras de reenvío
            return direct_ip

        # Si el cliente directo ES un proxy confiable, inspeccionar cabeceras
        headers = request.headers
        cf_ip = headers.get("cf-connecting-ip")
        if cf_ip:
            norm_cf = self.normalize_ip(cf_ip)
            if norm_cf:
                return norm_cf

        x_forwarded = headers.get("x-forwarded-for")
        if x_forwarded:
            # Procesar de derecha a izquierda: el último hop es el más cercano al proxy confiable
            hops = [p.strip() for p in x_forwarded.split(",") if p.strip()]
            for hop in reversed(hops):
                norm_hop = self.normalize_ip(hop)
                if norm_hop and norm_hop not in trusted:
                    # Encontramos el primer hop no confiable desde el perímetro hacia afuera: es el cliente real
                    return norm_hop

        return direct_ip

    def get_trusted_proxies(self) -> set:
        """Retorna el conjunto de IPs de proxies confiables configurados."""
        settings = self.get_settings()
        raw = settings.get("trusted_proxies", "127.0.0.1,::1")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        result = set()
        for p in parts:
            norm = self.normalize_ip(p)
            if norm:
                result.add(norm)
        return result or {"127.0.0.1", "::1"}

    # =========================================================================
    # 2. GESTIÓN DE CONFIGURACIÓN PERSISTENTE (firewall_settings)
    # =========================================================================
    def get_settings(self, force_refresh: bool = False) -> Dict[str, str]:
        now = time.time()
        if not force_refresh and self._settings_cache and (now - self._settings_last_fetch < self._settings_cache_ttl):
            return dict(self._settings_cache)

        settings = {}
        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT key, value FROM firewall_settings").fetchall()
                for r in rows:
                    settings[r["key"]] = r["value"]
            self._health_status = "OPERATIONAL"
            self._health_error_detail = None
        except Exception as e:
            logger.warning(f"Error reading firewall_settings (Fail-Open Activo): {e}")
            self._health_status = "DEGRADED"
            self._health_error_detail = f"Fallo al leer firewall_settings: {str(e)}"
            settings = {
                "firewall_enabled": "true",
                "max_login_attempts": "5",
                "login_window_minutes": "15",
                "account_lock_duration_minutes": "15",
                "ban_duration_minutes": "15",
                "rate_limit_default_rpm": "120",
                "rate_limit_login_rpm": "10",
                "rate_limit_qr_rpm": "30",
                "rate_limit_ai_rpm": "20",
                "trusted_proxies": "127.0.0.1,::1",
                "progressive_delay_enabled": "false",
                "trusted_school_subnets": "",
                "stuffing_account_threshold": "8",
                "stuffing_attempts_threshold": "15",
                "stuffing_window_seconds": "60"
            }

        with self._lock:
            self._settings_cache = settings
            self._settings_last_fetch = now
        return settings

    def update_settings(self, new_settings: Dict[str, str], admin_user: str = "admin_user") -> Dict[str, Any]:
        """Actualiza configuraciones del firewall en SQLite de manera transaccional."""
        try:
            with get_db() as conn:
                for k, v in new_settings.items():
                    conn.execute("""
                    INSERT INTO firewall_settings (key, value, updated_at, updated_by)
                    VALUES (?, ?, DATETIME('now', 'localtime'), ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """, (k, str(v), admin_user))
                conn.commit()

            # Invalidar caché
            self.get_settings(force_refresh=True)
            self.log_event(
                ip_address="127.0.0.1",
                event_type="SETTINGS_UPDATED",
                severity="MEDIUM",
                endpoint="/api/admin/firewall/settings",
                user_id=None,
                description=f"Políticas del firewall actualizadas por {admin_user}",
                metadata={"updated_keys": list(new_settings.keys())}
            )
            return {"success": True, "updated": len(new_settings)}
        except Exception as e:
            self._health_status = "DEGRADED"
            self._health_error_detail = f"Fallo al actualizar configuraciones: {str(e)}"
            logger.error(f"Error updating firewall settings: {e}")
            raise

    def is_enabled(self) -> bool:
        settings = self.get_settings()
        return settings.get("firewall_enabled", "true").lower() in ("true", "1", "yes")

    # =========================================================================
    # 3. VERIFICACIÓN Y GESTIÓN DE BLOQUEOS (firewall_banned_ips)
    # =========================================================================
    def is_ip_banned(self, ip_str: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Comprueba si una IP tiene un bloqueo activo en SQLite.
        Aplica auto-expiración atómica si el tiempo expiró.
        Tolerancia a fallos Fail-Open: si SQLite falla, no detiene el sistema.
        """
        norm_ip = self.normalize_ip(ip_str)
        if not norm_ip:
            return False, None

        # Excepción administrativa: loopback nunca se bloquea
        if norm_ip in ("127.0.0.1", "::1"):
            return False, None

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                ban = conn.execute("""
                    SELECT * FROM firewall_banned_ips
                    WHERE ip_address = ? AND is_active = 1
                    ORDER BY id DESC LIMIT 1
                """, (norm_ip,)).fetchone()

                if not ban:
                    return False, None

                # Comprobar expiración
                expires_at = ban["expires_at"]
                if expires_at and expires_at < now_str:
                    # Desbloqueo automático por expiración
                    conn.execute("""
                        UPDATE firewall_banned_ips
                        SET is_active = 0, unblocked_at = DATETIME('now', 'localtime'), unblocked_by = 'SYSTEM_EXPIRED'
                        WHERE id = ?
                    """, (ban["id"],))
                    conn.commit()
                    return False, None

                return True, dict(ban)
        except Exception as e:
            self._health_status = "DEGRADED"
            self._health_error_detail = f"Error al verificar IP vetada: {str(e)}"
            logger.warning(f"Error checking banned IP (Fail-Open activo): {e}")
            return False, None

    def ban_ip(
        self,
        ip_str: str,
        reason: str,
        duration_minutes: Optional[int] = 15,
        source: str = "MANUAL_ADMIN",
        created_by: str = "SYSTEM",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Registra un bloqueo de IP temporal o indefinido en SQLite."""
        norm_ip = self.normalize_ip(ip_str)
        if not norm_ip:
            return {"success": False, "message": "Dirección IP inválida"}

        if norm_ip in ("127.0.0.1", "::1"):
            return {"success": False, "message": "No se permite bloquear la interfaz de loopback"}

        expires_at = None
        if duration_minutes and duration_minutes > 0:
            exp_dt = datetime.now() + timedelta(minutes=duration_minutes)
            expires_at = exp_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with get_db() as conn:
                # Desactivar bloqueos previos activos para esta IP para no duplicar
                conn.execute("""
                    UPDATE firewall_banned_ips
                    SET is_active = 0, unblocked_at = DATETIME('now', 'localtime'), unblocked_by = 'SYSTEM_SUPERSEDED'
                    WHERE ip_address = ? AND is_active = 1
                """, (norm_ip,))

                cursor = conn.execute("""
                    INSERT INTO firewall_banned_ips 
                    (ip_address, reason, source, expires_at, is_active, created_by, notes)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (norm_ip, reason, source, expires_at, created_by, notes))
                ban_id = cursor.lastrowid
                conn.commit()

            self.log_event(
                ip_address=norm_ip,
                event_type="MANUAL_BAN" if source == "MANUAL_ADMIN" else "AUTO_BAN",
                severity="HIGH" if not expires_at else "MEDIUM",
                endpoint=None,
                user_id=None,
                description=f"IP bloqueada ({reason}). Expiración: {expires_at or 'Indefinida'}",
                metadata={"duration_minutes": duration_minutes, "source": source, "ban_id": ban_id}
            )

            return {
                "success": True,
                "ban_id": ban_id,
                "ip_address": norm_ip,
                "reason": reason,
                "expires_at": expires_at,
                "source": source
            }
        except Exception as e:
            self._health_status = "DEGRADED"
            self._health_error_detail = f"Error al registrar veto: {str(e)}"
            logger.error(f"Error banning IP: {e}")
            return {"success": False, "message": f"Error interno en base de datos: {e}"}

    def unblock_ip(self, ip_str: str, unblocked_by: str = "admin_user", notes: Optional[str] = None) -> Dict[str, Any]:
        """Desbloquea manualmente una IP."""
        norm_ip = self.normalize_ip(ip_str)
        if not norm_ip:
            return {"success": False, "message": "Dirección IP inválida"}

        try:
            with get_db() as conn:
                cursor = conn.execute("""
                    UPDATE firewall_banned_ips
                    SET is_active = 0, unblocked_at = DATETIME('now', 'localtime'), unblocked_by = ?, notes = COALESCE(notes, '') || ' | ' || COALESCE(?, '')
                    WHERE ip_address = ? AND is_active = 1
                """, (unblocked_by, notes or f"Desbloqueado manualmente por {unblocked_by}", norm_ip))
                affected = cursor.rowcount
                conn.commit()

            if affected > 0:
                self.log_event(
                    ip_address=norm_ip,
                    event_type="MANUAL_UNBAN",
                    severity="LOW",
                    endpoint=None,
                    user_id=None,
                    description=f"IP desbloqueada manualmente por {unblocked_by}",
                    metadata={"notes": notes}
                )
                return {"success": True, "message": f"IP {norm_ip} desbloqueada exitosamente", "unblocked_count": affected}
            return {"success": False, "message": f"La IP {norm_ip} no tenía bloqueos activos"}
        except Exception as e:
            logger.error(f"Error unblocking IP: {e}")
            return {"success": False, "message": f"Error en base de datos: {e}"}

    # =========================================================================
    # 4. CONTROL DE TASA (RATE LIMITING) MULTINIVEL
    # =========================================================================
    def check_rate_limit(self, ip_str: str, category: str = "default") -> Tuple[bool, int]:
        """
        Verifica el límite de peticiones por minuto para la IP en la categoría indicada.
        Categorías: 'default', 'login', 'qr', 'ai'.
        Arquitectura: Local a la instancia del proceso Uvicorn (In-Process Sliding Window).
        Retorna (allowed: bool, retry_after_seconds: int).
        """
        norm_ip = self.normalize_ip(ip_str) or "127.0.0.1"
        settings = self.get_settings()
        
        if category == "login":
            limit = int(settings.get("rate_limit_login_rpm", 10))
        elif category == "qr":
            limit = int(settings.get("rate_limit_qr_rpm", 30))
        elif category == "ai":
            limit = int(settings.get("rate_limit_ai_rpm", 20))
        else:
            limit = int(settings.get("rate_limit_default_rpm", 120))

        window_seconds = 60.0
        now = time.time()
        window_start = now - window_seconds
        key = (norm_ip, category)

        with self._lock:
            history = self._rate_limits.get(key, [])
            valid_history = [t for t in history if t > window_start]

            if len(valid_history) >= limit:
                oldest = valid_history[0]
                retry_after = max(1, int(oldest + window_seconds - now) + 1)
                self._rate_limits[key] = valid_history
                return False, retry_after

            valid_history.append(now)
            self._rate_limits[key] = valid_history
            return True, 0

    def reset_rate_limits(self):
        """Limpia contadores en memoria de proceso (útil para pruebas y reinicio)."""
        with self._lock:
            self._rate_limits.clear()

    # =========================================================================
    # 5. PROTECCIÓN DE AUTENTICACIÓN (Account DoS Protection & No time.sleep)
    # =========================================================================
    def check_login_lockout(self, account: str, ip_str: str) -> Tuple[bool, int, str]:
        """
        Comprueba si la combinación (cuenta + IP) o la IP tienen bloqueo activo de autenticación.
        Protege contra Account DoS: un atacante no puede bloquear la cuenta de otro usuario globalmente.
        Elimina time.sleep() por completo.
        Retorna (is_locked, retry_after_seconds, message).
        """
        norm_account = account.strip().lower()
        norm_ip = self.normalize_ip(ip_str) or "127.0.0.1"
        settings = self.get_settings()
        
        max_attempts = int(settings.get("max_login_attempts", 5))
        window_min = int(settings.get("login_window_minutes", 15))
        lock_min = int(settings.get("account_lock_duration_minutes", 15))

        since_dt = (datetime.now() - timedelta(minutes=window_min)).strftime("%Y-%m-%d %H:%M:%S")

        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                # 1. Contar fallos recientes para la combinación específica (cuenta + IP)
                pair_fails = conn.execute("""
                    SELECT COUNT(*) as count, MAX(attempt_time) as last_time
                    FROM firewall_login_attempts
                    WHERE account_identifier = ? AND ip_address = ? AND is_successful = 0 AND attempt_time >= ?
                """, (norm_account, norm_ip, since_dt)).fetchone()

                count = pair_fails["count"] if pair_fails else 0
                if count >= max_attempts:
                    last_time = pair_fails["last_time"]
                    if last_time:
                        last_dt = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
                        unlock_dt = last_dt + timedelta(minutes=lock_min)
                        now_dt = datetime.now()
                        if now_dt < unlock_dt:
                            remaining = max(1, int((unlock_dt - now_dt).total_seconds()))
                            # Mensaje genérico sin confirmar existencia de la cuenta
                            return True, remaining, f"Límite de intentos de autenticación excedido desde su ubicación. Espere {max(1, remaining // 60)} min."

                return False, 0, ""
        except Exception as e:
            logger.warning(f"Error checking login lockout (Fail-Open activo): {e}")
            return False, 0, ""

    def record_login_attempt(self, ip_str: str, account: str, success: bool, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Registra intento de inicio de sesión de forma segura (sin passwords ni hashes).
        Distingue redes escolares confiables y mitiga ataques de ráfaga externa de credential stuffing.
        """
        norm_account = account.strip().lower()
        norm_ip = self.normalize_ip(ip_str) or "127.0.0.1"
        settings = self.get_settings()

        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO firewall_login_attempts (ip_address, account_identifier, is_successful)
                    VALUES (?, ?, ?)
                """, (norm_ip, norm_account, 1 if success else 0))
                conn.commit()

                if success:
                    # En login exitoso, resolver intentos fallidos previos de esa cuenta desde esta IP
                    conn.execute("""
                        DELETE FROM firewall_login_attempts
                        WHERE account_identifier = ? AND ip_address = ? AND is_successful = 0
                    """, (norm_account, norm_ip))
                    conn.commit()
                    return {"success": True, "ip_banned": False}

                # --- Evaluación en caso de FALLO ---
                # A. Si la IP pertenece a la red escolar confiable: NUNCA vetar la IP por comportamiento compartido
                if self.is_trusted_school_network(norm_ip):
                    self.log_event(
                        ip_address=norm_ip,
                        event_type="AUTH_FAILED",
                        severity="LOW",
                        endpoint="/api/auth/login",
                        user_id=user_id,
                        description=f"Intento fallido en red escolar confiable para cuenta '{norm_account}'",
                        metadata={"account": norm_account, "school_network": True}
                    )
                    return {"success": False, "ip_banned": False, "school_network": True}

                # B. Si es una IP externa: evaluar ráfaga violenta de credential stuffing
                # Se evalúa en una ventana corta de ráfaga (default 60s) con umbral alto de cuentas e intentos
                burst_window_sec = int(settings.get("stuffing_window_seconds", 60))
                burst_dt = (datetime.now() - timedelta(seconds=burst_window_sec)).strftime("%Y-%m-%d %H:%M:%S")
                account_thresh = int(settings.get("stuffing_account_threshold", 8))
                attempts_thresh = int(settings.get("stuffing_attempts_threshold", 15))

                conn.row_factory = sqlite3.Row
                stats = conn.execute("""
                    SELECT COUNT(DISTINCT account_identifier) as distinct_count, COUNT(*) as total_fails
                    FROM firewall_login_attempts
                    WHERE ip_address = ? AND is_successful = 0 AND attempt_time >= ?
                """, (norm_ip, burst_dt)).fetchone()

                distinct_accounts = stats["distinct_count"] if stats else 0
                total_fails = stats["total_fails"] if stats else 0

                # Solo aplicar veto si supera AMBOS umbrales (múltiples cuentas Y ráfaga de intentos)
                if distinct_accounts >= account_thresh and total_fails >= attempts_thresh:
                    ban_min = int(settings.get("ban_duration_minutes", 15))
                    self.ban_ip(
                        ip_str=norm_ip,
                        reason=f"Ataque de credential stuffing en ráfaga ({distinct_accounts} cuentas, {total_fails} intentos en {burst_window_sec}s)",
                        duration_minutes=ban_min,
                        source="AUTO_AUTH_FAIL",
                        created_by="SYSTEM_FIREWALL",
                        notes="Veto automático preventivo por ráfaga externa"
                    )
                    return {"success": False, "ip_banned": True, "reason": "credential_stuffing_burst"}

            # Registrar evento ordinario de fallo
            self.log_event(
                ip_address=norm_ip,
                event_type="AUTH_FAILED",
                severity="MEDIUM",
                endpoint="/api/auth/login",
                user_id=user_id,
                description=f"Intento fallido de autenticación para cuenta '{norm_account}'",
                metadata={"account": norm_account}
            )
            return {"success": False, "ip_banned": False}
        except Exception as e:
            logger.warning(f"Error recording login attempt: {e}")
            return {"success": False, "ip_banned": False, "error": str(e)}

    def reset_login_attempts(
        self,
        account: Optional[str] = None,
        ip_address: Optional[str] = None,
        admin_user: str = "admin_user"
    ) -> Dict[str, Any]:
        """
        Acción administrativa controlada para restablecer intentos fallidos y desbloquear pares cuenta/IP.
        No elimina eventos históricos de firewall_events.
        """
        cleared_attempts = 0
        unblocked_bans = 0
        norm_account = account.strip().lower() if account else None
        norm_ip = self.normalize_ip(ip_address) if ip_address else None

        if not norm_account and not norm_ip:
            return {"success": False, "message": "Debe especificar una cuenta o una dirección IP"}

        try:
            with get_db() as conn:
                # 1. Borrar intentos fallidos
                if norm_account and norm_ip:
                    cur = conn.execute("DELETE FROM firewall_login_attempts WHERE account_identifier = ? AND ip_address = ? AND is_successful = 0", (norm_account, norm_ip))
                elif norm_account:
                    cur = conn.execute("DELETE FROM firewall_login_attempts WHERE account_identifier = ? AND is_successful = 0", (norm_account,))
                else:
                    cur = conn.execute("DELETE FROM firewall_login_attempts WHERE ip_address = ? AND is_successful = 0", (norm_ip,))
                cleared_attempts = cur.rowcount

                # 2. Si se especificó IP, desactivar también cualquier veto activo
                if norm_ip:
                    b_cur = conn.execute("""
                        UPDATE firewall_banned_ips
                        SET is_active = 0, unblocked_at = DATETIME('now', 'localtime'), unblocked_by = ?, notes = COALESCE(notes, '') || ' | Desbloqueo administrativo de intentos'
                        WHERE ip_address = ? AND is_active = 1
                    """, (admin_user, norm_ip))
                    unblocked_bans = b_cur.rowcount

                conn.commit()

            self.log_event(
                ip_address=norm_ip or "127.0.0.1",
                event_type="LOGIN_ATTEMPTS_RESET",
                severity="LOW",
                endpoint="/api/admin/firewall/reset-login-attempts",
                user_id=None,
                description=f"Restablecimiento de intentos fallidos por {admin_user}",
                metadata={"account": norm_account, "ip_address": norm_ip, "cleared": cleared_attempts, "unblocked_bans": unblocked_bans}
            )

            return {
                "success": True,
                "account": norm_account,
                "ip_address": norm_ip,
                "cleared_attempts": cleared_attempts,
                "unblocked_bans": unblocked_bans,
                "message": f"Se restablecieron {cleared_attempts} intentos fallidos exitosamente"
            }
        except Exception as e:
            logger.error(f"Error resetting login attempts: {e}")
            return {"success": False, "message": f"Error en base de datos: {e}"}

    # =========================================================================
    # 6. RETENCIÓN Y DEPURACIÓN PROGRAMADA (cleanup_old_records)
    # =========================================================================
    def cleanup_old_records(self) -> Dict[str, Any]:
        """
        Ejecuta depuración transaccional de registros antiguos según política institucional:
        - firewall_login_attempts: > 7 días
        - firewall_events: > 60 días
        - firewall_banned_ips: inactivos > 90 días (los activos NUNCA se eliminan)
        Registra una única fila resumen en firewall_events.
        """
        now = datetime.now()
        cutoff_attempts = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_events = (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_bans = (now - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

        try:
            with get_db() as conn:
                c1 = conn.execute("DELETE FROM firewall_login_attempts WHERE attempt_time < ?", (cutoff_attempts,)).rowcount
                c2 = conn.execute("DELETE FROM firewall_events WHERE created_at < ?", (cutoff_events,)).rowcount
                # Solo vetos inactivos con más de 90 días de antigüedad
                c3 = conn.execute("""
                    DELETE FROM firewall_banned_ips 
                    WHERE is_active = 0 AND expires_at IS NOT NULL AND expires_at < ?
                """, (cutoff_bans,)).rowcount
                conn.commit()

            self.log_event(
                ip_address="127.0.0.1",
                event_type="RETENTION_CLEANUP",
                severity="LOW",
                endpoint=None,
                user_id=None,
                description=f"Depuración de retención ejecutada: {c1} logins (>7d), {c2} eventos (>60d), {c3} vetos inactivos (>90d)",
                metadata={"deleted_login_attempts": c1, "deleted_events": c2, "deleted_banned_ips": c3}
            )

            return {
                "success": True,
                "deleted_login_attempts": c1,
                "deleted_events": c2,
                "deleted_banned_ips": c3,
                "message": "Depuración de retención completada exitosamente"
            }
        except Exception as e:
            logger.error(f"Error during retention cleanup: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # 7. DETECCIÓN DE PATRONES ANÓMALOS
    # =========================================================================
    def inspect_request_anomalies(self, request: Request, ip_str: str) -> Optional[str]:
        """
        Inspecciona rutas y cadenas de consulta en busca de patrones hostiles:
        - Path traversal (../, ..\\)
        - Sondeo de archivos sensibles (.env, wp-login, etc.)
        No bloquea automáticamente por un simple 404 o 403.
        """
        path = request.url.path.lower()
        query = str(request.url.query).lower()
        full_uri = f"{path}?{query}"

        hostile_patterns = [
            ("../", "Path traversal detectado"),
            ("..\\", "Windows path traversal detectado"),
            (".env", "Sondeo de archivo de entorno .env"),
            ("wp-login.php", "Sondeo automatizado de CMS WordPress"),
            ("phpmyadmin", "Sondeo de consola PHPMyAdmin"),
            ("web.config", "Sondeo de configuración IIS"),
            ("etc/passwd", "Intento de extracción de passwd"),
            ("<script>", "Intento de inyección XSS en URL")
        ]

        for pattern, desc in hostile_patterns:
            if pattern in full_uri:
                self.log_event(
                    ip_address=ip_str,
                    event_type="ANOMALY_DETECTED",
                    severity="HIGH",
                    endpoint=path,
                    user_id=None,
                    description=desc,
                    metadata={"pattern": pattern, "query": query[:100]}
                )
                return desc
        return None

    # =========================================================================
    # 8. REGISTRO FORENSE DE EVENTOS (firewall_events)
    # =========================================================================
    def log_event(
        self,
        ip_address: str,
        event_type: str,
        severity: str,
        endpoint: Optional[str],
        user_id: Optional[int],
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra un evento forense en la tabla firewall_events sin secretos ni tokens."""
        norm_ip = self.normalize_ip(ip_address) or "127.0.0.1"
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO firewall_events
                    (ip_address, event_type, severity, endpoint, user_id, description, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (norm_ip, event_type, severity, endpoint, user_id, description, meta_json))
                conn.commit()
        except Exception as e:
            logger.warning(f"Error logging firewall event (Fail-Open): {e}")

    # =========================================================================
    # 9. CONSULTAS PARA PANEL DE ADMINISTRACIÓN
    # =========================================================================
    def get_status(self) -> Dict[str, Any]:
        """Devuelve resumen de salud, métricas y estado del firewall para el panel administrativo."""
        settings = self.get_settings()
        enabled = self.is_enabled()
        today_str = datetime.now().strftime("%Y-%m-%d 00:00:00")

        active_bans = 0
        events_today = 0
        blocked_today = 0
        last_events = []

        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                active_bans = conn.execute("""
                    SELECT COUNT(*) as count FROM firewall_banned_ips WHERE is_active = 1
                """).fetchone()["count"]

                events_today = conn.execute("""
                    SELECT COUNT(*) as count FROM firewall_events WHERE created_at >= ?
                """, (today_str,)).fetchone()["count"]

                blocked_today = conn.execute("""
                    SELECT COUNT(*) as count FROM firewall_events 
                    WHERE created_at >= ? AND event_type IN ('BLOCKED_REQUEST', 'RATE_LIMIT_EXCEEDED')
                """, (today_str,)).fetchone()["count"]

                last_events = [dict(r) for r in conn.execute("""
                    SELECT * FROM firewall_events ORDER BY id DESC LIMIT 5
                """).fetchall()]
        except Exception as e:
            self._health_status = "DEGRADED"
            self._health_error_detail = f"Error al consultar métricas: {str(e)}"
            logger.warning(f"Error fetching firewall status metrics: {e}")

        # Subredes escolares
        raw_school_subnets = settings.get("trusted_school_subnets", "")
        school_subnets_list = [s.strip() for s in raw_school_subnets.split(",") if s.strip()]

        return {
            "firewall_enabled": enabled,
            "health": self._health_status,
            "health_detail": self._health_error_detail or "Todos los servicios de seguridad operan con normalidad en SQLite WAL.",
            "active_bans_count": active_bans,
            "events_today_count": events_today,
            "blocked_requests_today": blocked_today,
            "trusted_proxies": list(self.get_trusted_proxies()),
            "trusted_school_subnets": school_subnets_list,
            "architecture_note": "Monoproceso Uvicorn (Workers=1). Contadores en memoria de proceso (In-Process Sliding Window). Persistencia de vetos y eventos en SQLite WAL.",
            "recent_events": last_events
        }

    def get_blocked_ips(self, include_inactive: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        """Listado de IPs bloqueadas (con opción de incluir historial inactivo)."""
        self.cleanup_expired_bans()
        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                if include_inactive:
                    rows = conn.execute("SELECT * FROM firewall_banned_ips ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM firewall_banned_ips WHERE is_active = 1 ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching blocked IPs: {e}")
            return []

    def get_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Listado de eventos de seguridad forense."""
        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                if event_type:
                    rows = conn.execute("SELECT * FROM firewall_events WHERE event_type = ? ORDER BY id DESC LIMIT ?", (event_type, limit)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM firewall_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching firewall events: {e}")
            return []

    def cleanup_expired_bans(self) -> int:
        """Marca como inactivas las IPs cuya fecha de expiración haya vencido."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with get_db() as conn:
                cursor = conn.execute("""
                    UPDATE firewall_banned_ips
                    SET is_active = 0, unblocked_at = DATETIME('now', 'localtime'), unblocked_by = 'SYSTEM_EXPIRED'
                    WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at < ?
                """, (now_str,))
                affected = cursor.rowcount
                conn.commit()
                return affected
        except Exception as e:
            logger.error(f"Error cleaning expired bans: {e}")
            return 0


# Instancia Singleton institucional
firewall_service = FirewallService()
