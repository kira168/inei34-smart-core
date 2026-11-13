"""
INEI SMART-CORE 2.0 - Persistencia Atómica y Salvaguarda de Cuentas de Usuario
Garantiza que cualquier usuario creado o editado nunca se pierda ante cortes de energía,
reinicios de Windows o sincronizaciones de OneDrive.
"""

import json
import logging
from pathlib import Path
from typing import Optional
import os
from app.config import DATA_DIR

logger = logging.getLogger("inei_persistence")

_test_users_path = os.getenv("PERSISTENT_USERS_PATH", "").strip()

if _test_users_path:
    PERSISTENT_USERS_FILE = Path(_test_users_path)
else:
    PERSISTENT_USERS_FILE = DATA_DIR / "users_persistent.json"

def get_persistent_users_file() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return PERSISTENT_USERS_FILE

def sync_users_to_disk(conn=None) -> bool:
    """
    Exporta la tabla completa de usuarios y sus perfiles asociados a un archivo JSON atómico.
    Se ejecuta tras cualquier creación, edición, reseteo o eliminación de usuarios.
    """
    from app.database.connection import get_db_connection
    
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        users = conn.execute("""
            SELECT id, username, password_hash, full_name, email, role, phone, avatar_url, dni, is_active, created_at
            FROM users
            ORDER BY id ASC
        """).fetchall()

        backup_data = []
        for u in users:
            u_dict = dict(u)
            u_id = u_dict["id"]
            
            # Perfil docente si existe
            teacher = conn.execute("SELECT dni, full_name, specialty, email, phone, condition, academic_degree FROM teachers WHERE user_id = ?", (u_id,)).fetchone()
            if teacher:
                u_dict["teacher_profile"] = dict(teacher)
            
            # Perfil estudiante si existe
            student = conn.execute("SELECT dni, full_name, specialty, grade, section, parent_id, section_id, status, birth_date, address FROM students WHERE user_id = ?", (u_id,)).fetchone()
            if student:
                u_dict["student_profile"] = dict(student)
                
            # Perfil apoderado si existe
            parent = conn.execute("SELECT dni, full_name, phone, address, email, occupation FROM parents WHERE user_id = ?", (u_id,)).fetchone()
            if parent:
                u_dict["parent_profile"] = dict(parent)
                
            backup_data.append(u_dict)

        target_file = get_persistent_users_file()
        tmp_file = target_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
            f.flush()
        
        # Reemplazo atómico seguro en Windows
        tmp_file.replace(target_file)
        logger.info(f"Persistencia atómica actualizada: {len(backup_data)} usuarios guardados en disco.")
        return True
    except Exception as e:
        logger.error(f"Error sincronizando usuarios a disco: {e}")
        return False
    finally:
        if close_conn and conn:
            conn.close()

def restore_persistent_users(conn) -> int:
    """
    Restaura y sincroniza usuarios desde el archivo persistente JSON hacia SQLite al arrancar el servidor.
    Si SQLite se reinició o un archivo fue reemplazado por OneDrive, este método recupera todas las cuentas.
    """
    target_file = get_persistent_users_file()
    if not target_file.exists():
        # Si aún no existe el archivo JSON, exportar el estado actual como punto de partida
        sync_users_to_disk(conn)
        return 0

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
            
        if not isinstance(backup_data, list):
            return 0

        restored_count = 0
        for u in backup_data:
            username = str(u.get("username", "")).strip().lower()
            if not username:
                continue

            existing = conn.execute("SELECT id, username, password_hash, full_name, email, role, phone, dni, is_active FROM users WHERE username = ?", (username,)).fetchone()
            
            if existing:
                u_id = existing["id"]
                # Si algún dato clave difiere del respaldo permanente, actualizarlo
                needs_update = False
                new_full_name = u.get("full_name") or existing["full_name"]
                new_email = u.get("email") or existing["email"]
                new_role = u.get("role") or existing["role"]
                new_phone = u.get("phone") or existing["phone"]
                new_dni = u.get("dni") or existing["dni"]
                new_active = u.get("is_active", 1)
                new_hash = u.get("password_hash") or existing["password_hash"]

                if (existing["full_name"] != new_full_name or 
                    existing["email"] != new_email or 
                    existing["role"] != new_role or 
                    existing["phone"] != new_phone or 
                    existing["dni"] != new_dni or
                    existing["is_active"] != new_active or
                    existing["password_hash"] != new_hash):
                    conn.execute("""
                        UPDATE users
                        SET full_name = ?, email = ?, role = ?, phone = ?, dni = ?, is_active = ?, password_hash = ?
                        WHERE id = ?
                    """, (new_full_name, new_email, new_role, new_phone, new_dni, new_active, new_hash, u_id))
                    restored_count += 1
            else:
                # Insertar usuario faltante preservando su hash y rol
                cursor = conn.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, role, phone, avatar_url, dni, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    username,
                    u.get("password_hash"),
                    u.get("full_name", username),
                    u.get("email"),
                    u.get("role", "estudiante"),
                    u.get("phone"),
                    u.get("avatar_url"),
                    u.get("dni"),
                    u.get("is_active", 1)
                ))
                u_id = cursor.lastrowid
                restored_count += 1

            # Restaurar perfil docente si aplica
            if u.get("teacher_profile"):
                tp = u["teacher_profile"]
                t_exist = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (u_id,)).fetchone()
                if not t_exist:
                    conn.execute("""
                        INSERT INTO teachers (user_id, dni, full_name, specialty, email, phone, condition, academic_degree)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (u_id, tp.get("dni", username), tp.get("full_name", u.get("full_name")), tp.get("specialty", "General"), tp.get("email", u.get("email")), tp.get("phone", u.get("phone")), tp.get("condition", "Nombrado"), tp.get("academic_degree", "Licenciado")))
            
            # Restaurar perfil estudiante si aplica
            if u.get("student_profile"):
                sp = u["student_profile"]
                s_exist = conn.execute("SELECT id FROM students WHERE user_id = ?", (u_id,)).fetchone()
                if not s_exist:
                    conn.execute("""
                        INSERT INTO students (user_id, dni, full_name, specialty, grade, section, parent_id, section_id, status, birth_date, address)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (u_id, sp.get("dni", username), sp.get("full_name", u.get("full_name")), sp.get("specialty", "General"), sp.get("grade", "5to"), sp.get("section", "A"), sp.get("parent_id"), sp.get("section_id"), sp.get("status", "Matriculado"), sp.get("birth_date"), sp.get("address")))

            # Restaurar perfil apoderado si aplica
            if u.get("parent_profile"):
                pp = u["parent_profile"]
                p_exist = conn.execute("SELECT id FROM parents WHERE user_id = ?", (u_id,)).fetchone()
                if not p_exist:
                    conn.execute("""
                        INSERT INTO parents (user_id, dni, full_name, phone, address, email, occupation)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (u_id, pp.get("dni", username), pp.get("full_name", u.get("full_name")), pp.get("phone", u.get("phone")), pp.get("address"), pp.get("email", u.get("email")), pp.get("occupation")))

        if restored_count > 0:
            conn.commit()
            logger.info(f"Restauración persistente completada: {restored_count} usuarios sincronizados desde respaldo.")
        return restored_count
    except Exception as e:
        logger.error(f"Error restaurando usuarios desde disco: {e}")
        return 0
