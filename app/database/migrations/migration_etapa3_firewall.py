"""
INEI SMART-CORE v2.8 - Etapa 3 Migration
Firewall Inteligente con Persistencia SQLite
Tablas: firewall_banned_ips, firewall_events, firewall_settings, firewall_login_attempts
"""

import sqlite3
import os
from typing import Optional, Dict, Any
from pathlib import Path
import app.config as config

MIGRATION_VERSION = "2.8.4_firewall_hardening"

DEFAULT_SETTINGS = [
    ("firewall_enabled", "true", "Activa o desactiva la inspección global del firewall"),
    ("max_login_attempts", "5", "Máximo de intentos fallidos antes de bloqueo o retardo"),
    ("login_window_minutes", "15", "Ventana de tiempo para contar intentos fallidos (minutos)"),
    ("account_lock_duration_minutes", "15", "Duración del bloqueo temporal por cuenta (minutos)"),
    ("ban_duration_minutes", "15", "Duración predeterminada de bloqueo temporal de IP (minutos)"),
    ("rate_limit_default_rpm", "120", "Límite general de peticiones por minuto por IP"),
    ("rate_limit_login_rpm", "10", "Límite de peticiones por minuto por IP en endpoint de login"),
    ("rate_limit_qr_rpm", "30", "Límite de peticiones por minuto por IP en verificación QR"),
    ("rate_limit_ai_rpm", "20", "Límite de peticiones por minuto por IP en endpoints de IA"),
    ("trusted_proxies", "127.0.0.1,::1", "Lista de IPs de proxies inversos confiables separadas por coma"),
    ("progressive_delay_enabled", "false", "Habilita tiempo de espera progresivo ante fallos continuos de login"),
    ("trusted_school_subnets", "", "Subredes IP institucionales confiables en formato CIDR separadas por coma (ej. 192.168.1.0/24)"),
    ("stuffing_account_threshold", "8", "Mínimo de cuentas distintas atacadas en ráfaga para evaluar veto externo"),
    ("stuffing_attempts_threshold", "15", "Mínimo de intentos fallidos acumulados en ráfaga para evaluar veto externo"),
    ("stuffing_window_seconds", "60", "Ventana en segundos para evaluar ataques de ráfaga de credential stuffing")
]

def migrate_firewall_schema(db_path: Optional[str] = None) -> Dict[str, Any]:
    target_db = Path(db_path) if db_path else config.DB_PATH
    
    with sqlite3.connect(str(target_db), timeout=15.0) as conn:
        cursor = conn.cursor()
        
        # 1. Tabla de IPs Bloqueadas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS firewall_banned_ips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            reason TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
            expires_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT DEFAULT 'SYSTEM',
            unblocked_at TEXT,
            unblocked_by TEXT,
            notes TEXT
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_banned_ip ON firewall_banned_ips(ip_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_banned_active ON firewall_banned_ips(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_banned_expires ON firewall_banned_ips(expires_at)")

        # 2. Tabla de Eventos de Seguridad
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS firewall_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            endpoint TEXT,
            user_id INTEGER,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
            metadata_json TEXT
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_events_ip ON firewall_events(ip_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_events_type ON firewall_events(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_events_created ON firewall_events(created_at)")

        # 3. Tabla de Configuraciones Persistentes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS firewall_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
            updated_by TEXT DEFAULT 'SYSTEM'
        )
        """)
        for key, val, desc in DEFAULT_SETTINGS:
            cursor.execute("""
            INSERT OR IGNORE INTO firewall_settings (key, value, description)
            VALUES (?, ?, ?)
            """, (key, val, desc))

        # 4. Tabla de Intentos de Autenticación (mínimo forense, sin contraseñas ni tokens)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS firewall_login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            account_identifier TEXT NOT NULL,
            attempt_time TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
            is_successful INTEGER NOT NULL DEFAULT 0
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_login_ip ON firewall_login_attempts(ip_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_login_account ON firewall_login_attempts(account_identifier)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fw_login_time ON firewall_login_attempts(attempt_time)")

        conn.commit()

    return {
        "success": True,
        "migration_version": MIGRATION_VERSION,
        "db_path": str(target_db),
        "tables_created": [
            "firewall_banned_ips",
            "firewall_events",
            "firewall_settings",
            "firewall_login_attempts"
        ]
    }

def revert_firewall_schema(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Reversión segura de la Etapa 3 (usado solo si se requiere rollback explícito)."""
    target_db = Path(db_path) if db_path else config.DB_PATH
    with sqlite3.connect(str(target_db), timeout=15.0) as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS firewall_login_attempts")
        cursor.execute("DROP TABLE IF EXISTS firewall_settings")
        cursor.execute("DROP TABLE IF EXISTS firewall_events")
        cursor.execute("DROP TABLE IF EXISTS firewall_banned_ips")
        conn.commit()
    return {"success": True, "reverted_tables": ["firewall_login_attempts", "firewall_settings", "firewall_events", "firewall_banned_ips"]}

def verify_firewall_schema(db_path: Optional[str] = None) -> bool:
    target_db = Path(db_path) if db_path else config.DB_PATH
    with sqlite3.connect(str(target_db)) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        required = ["firewall_banned_ips", "firewall_events", "firewall_settings", "firewall_login_attempts"]
        return all(t in tables for t in required)
