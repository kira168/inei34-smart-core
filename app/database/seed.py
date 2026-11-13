from datetime import datetime
from app.database.connection import db_session
from app.auth.security import hash_password

def ensure_critical_accounts(conn):
    """Garantiza que existan cuentas operativas de Administrador y Director con hashes válidos y correos institucionales."""
    cursor = conn.cursor()
    # 1. Administrador
    admin_hash = hash_password("admin2026")
    cursor.execute("SELECT id, email, password_hash FROM users WHERE LOWER(role) IN ('admin', 'administrador') OR LOWER(username) IN ('admin', 'admin_user') LIMIT 1")
    admin_row = cursor.fetchone()
    if admin_row:
        cursor.execute("""
            UPDATE users
            SET email = COALESCE(email, 'admin@inei34.edu.pe'),
                role = 'ADMINISTRADOR',
                is_active = 1
            WHERE id = ?
        """, (admin_row[0],))
    else:
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email, role, phone, is_active)
            VALUES ('admin_user', ?, 'Ing. Carlos Mendoza Poma', 'admin@inei34.edu.pe', 'ADMINISTRADOR', '987654321', 1)
        """, (admin_hash,))

    # 2. Director
    director_hash = hash_password("director2026")
    cursor.execute("SELECT id, email, password_hash FROM users WHERE LOWER(role) IN ('director') OR LOWER(username) IN ('director', 'director_user') LIMIT 1")
    director_row = cursor.fetchone()
    if director_row:
        curr_hash = director_row[2] or ""
        update_hash = director_hash if (curr_hash == "hash" or not str(curr_hash).startswith("$argon2")) else curr_hash
        cursor.execute("""
            UPDATE users
            SET email = COALESCE(email, 'director@inei34.edu.pe'),
                password_hash = ?,
                role = 'DIRECTOR',
                is_active = 1
            WHERE id = ?
        """, (update_hash, director_row[0]))
    else:
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email, role, phone, is_active)
            VALUES ('director_user', ?, 'Lic. Manuel Romero Salazar', 'director@inei34.edu.pe', 'DIRECTOR', '984123890', 1)
        """, (director_hash,))

    # Garantizar tickets de soporte iniciales si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM support_tickets")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO support_tickets (ticket_code, user_id, user_name, user_role, user_email, user_dni, subject, priority, area, description, status, solution, admin_response_by, resolved_at)
        VALUES 
        ('TCK-2026-001', 4, 'Prof. Roberto Bazán', 'DOCENTE', 'rbazan@inei34chancay.edu.pe', '10234567', 'Restablecimiento de contraseña para alumno Diego Quispe', 'MEDIA', 'Mecánica de Producción', 'El alumno Diego Quispe de 5to A olvidó su contraseña de acceso y no puede subir sus planos de torno.', 'RESUELTO', 'Contraseña temporal asignada por Administrador: 123456. Se recomendó al estudiante cambiarla en su primer inicio de sesión.', 'Lic. Carlos S. (Admin TI)', '01/10/2026 10:15 AM'),
        ('TCK-2026-002', 4, 'Prof. Roberto Bazán', 'DOCENTE', 'rbazan@inei34chancay.edu.pe', '10234567', 'Calibración de lectura en vernier digital de Taller N° 2', 'ALTA', 'Mecánica de Producción', 'Dos vernieres digitales Mitutoyo del banco 4 presentan desfase de 0.05 mm en la lectura cero.', 'EN ATENCIÓN', 'Equipo derivado a calibración de precisión. Se asignaron 2 vernieres de reserva del almacén central para no interrumpir la práctica.', 'Lic. Carlos S. (Admin TI)', NULL),
        ('TCK-2026-003', 3, 'Lic. Rosa Flores Meléndez', 'SECRETARÍA', 'secretaria@inei34.edu.pe', '08765432', 'Habilitación de módulo para matrículas extemporáneas', 'ALTA', 'Secretaría General', 'Se requiere autorización para registrar matrícula excepcional de dos estudiantes trasladados de la UGEL 10 Huaral fuera de fecha ordinaria.', 'PENDIENTE', NULL, NULL, NULL),
        ('TCK-2026-004', 2, 'Lic. Manuel Romero Salazar', 'DIRECTOR', 'director@inei34.edu.pe', '09876543', 'Revisión técnica de proyector multimedia en Sala de Innovación', 'MEDIA', 'Dirección General', 'El proyector Epson de la Sala 1 no detecta la señal HDMI desde la laptop institucional del docente.', 'PENDIENTE', NULL, NULL, NULL)
        """)

    # Mensajes Iniciales de Chat Mesa de Ayuda si está vacía
    cursor.execute("SELECT COUNT(*) FROM support_chat_messages")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO support_chat_messages (user_id, user_name, user_role, sender, text)
        VALUES 
        (4, 'Prof. Roberto Bazán', 'DOCENTE', 'bot', '👋 ¡Hola Prof. Roberto! Soy el Asistente de Soporte Técnico Smart-Core de la I.E. INEI N° 34 Chancay. ¿En qué te puedo ayudar hoy? Puedes consultar tus dudas o crear un ticket oficial para el Administrador.'),
        (4, 'Prof. Roberto Bazán', 'DOCENTE', 'user', 'Buenas tardes estimado administrador, tengo una duda sobre el aforo en el taller de torneado.'),
        (4, 'Prof. Roberto Bazán', 'DOCENTE', 'admin', 'Buenas tardes Prof. Roberto. El aforo máximo normativo según directiva 5S es de 20 estudiantes por turno en taller de mecanizado.')
        """)

def seed_database():
    """Inserta datos de demostración realistas y estructurados para el INEI 34 Chancay."""
    from app.database.persistence import restore_persistent_users, sync_users_to_disk

    with db_session() as conn:
        cursor = conn.cursor()

        # Restaurar usuarios persistentes desde JSON si existen (salvaguarda ante reinicios o sincronizaciones de OneDrive)
        restore_persistent_users(conn)

        # Verificar si ya existen datos generales
        cursor.execute("SELECT COUNT(*) FROM roles")
        if cursor.fetchone()[0] > 0:
            ensure_critical_accounts(conn)
            sync_users_to_disk(conn)
            return

        # Garantizar cuentas críticas operativas siempre
        ensure_critical_accounts(conn)

        # 1. Catálogo de Roles
        roles = [
            ("admin", "Administrador", "Control total del sistema, seguridad y auditoría"),
            ("director", "Director General", "Monitoreo institucional, reportes y supervisión"),
            ("secretaria", "Secretaría General", "Gestión de matrícula, mesa de partes y documentos"),
            ("docente", "Docente de Especialidad", "Cursos, calificaciones SIAGIE, asistencia y tareas"),
            ("estudiante", "Estudiante", "Mis cursos, horario, tareas, calificaciones y tutor IA"),
            ("apoderado", "Padre / Apoderado", "Información exclusiva de sus hijos, asistencia y notas")
        ]
        cursor.executemany("INSERT INTO roles (role_key, role_name, description) VALUES (?, ?, ?)", roles)

        # 2. Catálogo de Permisos Granulares
        perms = [
            ("users:manage", "Gestión de usuarios y contraseñas", "Usuarios"),
            ("roles:manage", "Gestión de roles y permisos", "Roles"),
            ("audit:view", "Visualizar registros de auditoría", "Auditoría"),
            ("config:manage", "Configuración institucional", "Configuración"),
            ("dashboard:institutional", "Acceso al dashboard directivo", "Dashboard"),
            ("reports:view", "Ver y generar reportes ejecutivos", "Reportes"),
            ("students:manage", "Administración de estudiantes", "Académico"),
            ("enrollment:manage", "Gestión de matrículas y vacantes", "Matrícula"),
            ("documents:manage", "Gestión de repositorio institucional", "Documentos"),
            ("mesa_partes:manage", "Gestión de trámites y expedientes", "Mesa de Partes"),
            ("attendance:record", "Registrar asistencia de aula/taller", "Asistencia"),
            ("grades:record", "Registrar calificaciones SIAGIE EPT", "Evaluaciones"),
            ("assignments:manage", "Crear y calificar tareas escolares", "Tareas"),
            ("announcements:create", "Publicar comunicados oficiales", "Comunicaciones"),
            ("student:view_own", "Ver cursos, notas y horario personal", "Estudiante"),
            ("parent:view_own", "Ver información exclusiva de sus hijos", "Familia"),
            ("ai:access", "Acceso al Asistente Institucional IA", "IA")
        ]
        cursor.executemany("INSERT INTO permissions (perm_key, description, module) VALUES (?, ?, ?)", perms)

        # 3. Asignación Roles - Permisos
        role_perms = [
            ("admin", "users:manage"), ("admin", "roles:manage"), ("admin", "audit:view"), ("admin", "config:manage"), ("admin", "ai:access"),
            ("director", "dashboard:institutional"), ("director", "reports:view"), ("director", "audit:view"), ("director", "announcements:create"), ("director", "ai:access"),
            ("secretaria", "students:manage"), ("secretaria", "enrollment:manage"), ("secretaria", "documents:manage"), ("secretaria", "mesa_partes:manage"), ("secretaria", "announcements:create"), ("secretaria", "ai:access"),
            ("docente", "attendance:record"), ("docente", "grades:record"), ("docente", "assignments:manage"), ("docente", "ai:access"),
            ("estudiante", "student:view_own"), ("estudiante", "ai:access"),
            ("apoderado", "parent:view_own"), ("apoderado", "ai:access")
        ]
        cursor.executemany("INSERT INTO role_permissions (role, permission) VALUES (?, ?)", role_perms)

        # 4. Usuarios Iniciales (Contraseñas seguras con hash)
        users = [
            ("admin", hash_password("admin123"), "Ing. Carlos Mendoza Poma", "admin@inei34chancay.edu.pe", "admin", "987654321", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"),
            ("director", hash_password("director123"), "Lic. Manuel Romero Salazar", "director@inei34chancay.edu.pe", "director", "984123890", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80"),
            ("secretaria", hash_password("secre123"), "Sra. Patricia Vega Arredondo", "secretaria@inei34chancay.edu.pe", "secretaria", "981234567", "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=100&auto=format&fit=crop&q=80"),
            ("docente", hash_password("docente123"), "Prof. Roberto Bazán Palacios", "rbazan@inei34chancay.edu.pe", "docente", "992345678", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&auto=format&fit=crop&q=80"),
            ("docente2", hash_password("docente123"), "Lic. Isabel Mercado Vargas", "imercado@inei34chancay.edu.pe", "docente", "993456789", "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=100&auto=format&fit=crop&q=80"),
            ("estudiante", hash_password("alumno123"), "Diego Quispe Alarcón", "dquispe@inei34chancay.edu.pe", "estudiante", "971234567", "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=100&auto=format&fit=crop&q=80"),
            ("estudiante2", hash_password("alumno123"), "Camila Nicole Barrera Rosales", "cbarrera@inei34chancay.edu.pe", "estudiante", "972345678", "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=100&auto=format&fit=crop&q=80"),
            ("apoderado", hash_password("padre123"), "Sra. Carmen Valdivia Morales", "cvaldivia@gmail.com", "apoderado", "999888777", "https://images.unsplash.com/photo-1548142813-c348350df52b?w=100&auto=format&fit=crop&q=80")
        ]
        cursor.executemany("""
        INSERT INTO users (username, password_hash, full_name, email, role, phone, avatar_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, users)

        # 5. Docentes
        cursor.execute("SELECT id FROM users WHERE username = 'docente'")
        doc1_uid = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE username = 'docente2'")
        doc2_uid = cursor.fetchone()[0]

        teachers = [
            (doc1_uid, "09823451", "Prof. Roberto Bazán Palacios", "Mecánica de Producción", "rbazan@inei34chancay.edu.pe", "992345678", "Nombrado", "Licenciado en EPT"),
            (doc2_uid, "08761234", "Lic. Isabel Mercado Vargas", "Computación e Informática", "imercado@inei34chancay.edu.pe", "993456789", "Nombrado", "Magíster en Educación")
        ]
        cursor.executemany("""
        INSERT INTO teachers (user_id, dni, full_name, specialty, email, phone, condition, academic_degree)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, teachers)

        cursor.execute("SELECT id FROM teachers WHERE dni = '09823451'")
        t1_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM teachers WHERE dni = '08761234'")
        t2_id = cursor.fetchone()[0]

        # 6. Secciones y Talleres
        sections = [
            ("5to", "A", "Mecánica de Producción", t1_id, "2026", 35, "Mañana"),
            ("5to", "B", "Computación e Informática", t2_id, "2026", 35, "Mañana"),
            ("4to", "A", "Electricidad", t1_id, "2026", 35, "Tarde"),
            ("3ro", "A", "Automotores", t1_id, "2026", 35, "Mañana")
        ]
        cursor.executemany("""
        INSERT INTO sections (grade, section_name, specialty, tutor_id, academic_year, capacity, shift)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sections)

        cursor.execute("SELECT id FROM sections WHERE grade = '5to' AND section_name = 'A'")
        sec_5a_id = cursor.fetchone()[0]

        # 7. Apoderados
        cursor.execute("SELECT id FROM users WHERE username = 'apoderado'")
        parent_uid = cursor.fetchone()[0]
        cursor.execute("""
        INSERT INTO parents (user_id, dni, full_name, phone, address, email, occupation)
        VALUES (?, '07654321', 'Sra. Carmen Valdivia Morales', '999888777', 'Calle Las Flores 230, Chancay', 'cvaldivia@gmail.com', 'Comerciante')
        """, (parent_uid,))
        p1_id = cursor.lastrowid

        # 8. Estudiantes Oficiales
        cursor.execute("SELECT id FROM users WHERE username = 'estudiante'")
        est1_uid = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE username = 'estudiante2'")
        est2_uid = cursor.fetchone()[0]

        students = [
            (est1_uid, "73849502", "Diego Quispe Alarcón", "Mecánica de Producción", "5to", "A", p1_id, sec_5a_id, "Activo", "2009-04-15", "Calle Las Flores 230, Chancay"),
            (est2_uid, "73910284", "Camila Nicole Barrera Rosales", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-07-22", "Av. Belén 140, Chancay"),
            (None, "72841029", "Renzo Miguel Alcántara Bazán", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-02-10", "Jr. San Martín 450, Chancay"),
            (None, "74829103", "Kevin Jean Collantes Castillo", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-08-30", "Calle Tacna 310, Chancay"),
            (None, "71928374", "Fabrizio David Díaz Mendoza", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-11-18", "Av. Roosevelt 112, Chancay"),
            (None, "75839201", "Kimberly Dayana Espinoza Paredes", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-05-03", "Prolongación López 54, Chancay"),
            (None, "76948271", "Juan Carlos Flores Chávez", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-09-14", "Calle Pringles 89, Chancay"),
            (None, "70819283", "Bryan Alexis Guerrero Morales", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-03-27", "Jr. Sucre 205, Chancay"),
            (None, "72938475", "Ariana Belén Herrera Salazar", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-12-01", "Av. 1ro de Mayo 430, Chancay"),
            (None, "74950281", "Luciana Sofía Jiménez Valverde", "Mecánica de Producción", "5to", "A", None, sec_5a_id, "Activo", "2009-06-19", "Calle Bolognesi 600, Chancay")
        ]
        cursor.executemany("""
        INSERT INTO students (user_id, dni, full_name, specialty, grade, section, parent_id, section_id, status, birth_date, address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, students)

        # 9. Cursos
        courses = [
            ("EPT-MP-501", "Torno y Mecanizado CNC", "Mecánica de Producción", "5to", 6, t1_id, "Silabo_Torno_CNC_2026.pdf"),
            ("EPT-MP-502", "Ajuste y Matricería Industrial", "Mecánica de Producción", "5to", 4, t1_id, "Silabo_Matriceria_2026.pdf"),
            ("EPT-COM-501", "Redes y Conectividad AIP", "Computación e Informática", "5to", 6, t2_id, "Silabo_Redes_2026.pdf"),
            ("MAT-501", "Matemática Aplicada al Taller", "Mecánica de Producción", "5to", 4, t1_id, "Silabo_Matematica_2026.pdf")
        ]
        cursor.executemany("""
        INSERT INTO courses (code, name, specialty, grade, hours_per_week, teacher_id, syllabus_file)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, courses)

        # 10. Matrículas 2026
        cursor.execute("SELECT id FROM students")
        st_ids = [r[0] for r in cursor.fetchall()]
        for sid in st_ids:
            cursor.execute("INSERT INTO enrollments (student_id, section_id, academic_year, status) VALUES (?, ?, '2026', 'Matriculado')", (sid, sec_5a_id))

        # 11. Asistencia
        today = datetime.now().strftime("%Y-%m-%d")
        att_records = [
            (st_ids[0], sec_5a_id, today, "P", 4, "Asistencia puntual en taller de torno"),
            (st_ids[1], sec_5a_id, today, "P", 4, "Puntual"),
            (st_ids[2], sec_5a_id, today, "P", 4, "Puntual"),
            (st_ids[3], sec_5a_id, today, "T", 4, "Tardanza de 10 minutos"),
            (st_ids[4], sec_5a_id, today, "P", 4, "Puntual"),
            (st_ids[5], sec_5a_id, today, "J", 4, "Justificación médica presentada"),
            (st_ids[6], sec_5a_id, today, "P", 4, "Puntual"),
            (st_ids[7], sec_5a_id, today, "F", 4, "Inasistencia sin avisar"),
            (st_ids[8], sec_5a_id, today, "P", 4, "Puntual"),
            (st_ids[9], sec_5a_id, today, "P", 4, "Puntual")
        ]
        cursor.executemany("""
        INSERT INTO attendance (student_id, section_id, date, status, recorded_by, remarks)
        VALUES (?, ?, ?, ?, ?, ?)
        """, att_records)

        # 12. Evaluaciones SIAGIE
        cursor.execute("SELECT id FROM courses WHERE code = 'EPT-MP-501'")
        c1_id = cursor.fetchone()[0]
        evals = [
            (st_ids[0], c1_id, "I Bimestre", "AD", "AD", "A", "AD", "AD", "Sobresaliente en torneado y liderazgo de taller.", 4),
            (st_ids[1], c1_id, "I Bimestre", "A", "AD", "A", "A", "A", "Logro esperado cumplido con alta precisión.", 4),
            (st_ids[2], c1_id, "I Bimestre", "A", "A", "B", "A", "A", "Buen desempeño técnico; afianzar trabajo en equipo.", 4),
            (st_ids[3], c1_id, "I Bimestre", "AD", "AD", "AD", "AD", "AD", "Dominio técnico impecable y riguroso uso de EPP.", 4),
            (st_ids[4], c1_id, "I Bimestre", "A", "B", "A", "B", "B", "En proceso en calibración vernier; requiere refuerzo.", 4),
            (st_ids[5], c1_id, "I Bimestre", "AD", "A", "AD", "A", "A", "Destaca en orden y bioseguridad 5S en taller.", 4),
            (st_ids[6], c1_id, "I Bimestre", "B", "B", "B", "C", "B", "Programado para reforzamiento práctico de taller.", 4),
            (st_ids[7], c1_id, "I Bimestre", "A", "A", "A", "A", "A", "Cumple satisfactoriamente con la pieza programada.", 4),
            (st_ids[8], c1_id, "I Bimestre", "AD", "AD", "A", "AD", "AD", "Habilidad destacada en acabado superficial N7.", 4),
            (st_ids[9], c1_id, "I Bimestre", "A", "A", "AD", "A", "A", "Muy colaborativa y ordenada en el puesto de trabajo.", 4)
        ]
        cursor.executemany("""
        INSERT INTO evaluations (student_id, course_id, bimester, c1, c2, c3, c4, final_grade, conclusion, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, evals)

        # 13. Tareas
        cursor.execute("""
        INSERT INTO assignments (course_id, teacher_id, title, description, due_date)
        VALUES (?, ?, 'Hoja de Procesos: Fabricación de Eje Escalonado en Torno', 'Elaborar la secuencia operacional, cálculo de RPM y normas de seguridad para tornear un eje de acero SAE 1020.', '2026-10-12')
        """, (c1_id, t1_id))

        # 14. Mesa de Partes Virtual
        expedientes = [
            ("EXP-2026-00104", "07654321", "Sra. Carmen Valdivia Morales", "cvaldivia@gmail.com", "999888777", "Constancia de Matrícula", "Solicitud de constancia oficial para trámite de seguro de salud", "RECIBIDO", 3, "solicitud_constancia.pdf", "Pendiente de firma de secretaría"),
            ("EXP-2026-00098", "45892134", "Sr. Juan Carlos Pérez", "jperez@gmail.com", "981122334", "Certificado de Estudios", "Duplicado de certificado de egresado promoción 2025", "EN PROCESO", 3, "duplicado_cert.pdf", "Búsqueda en libro de actas histórico")
        ]
        cursor.executemany("""
        INSERT INTO mesa_partes_solicitudes (expediente_code, solicitante_dni, solicitante_name, solicitante_email, solicitante_phone, tipo_tramite, asunto, status, responsable_id, documento_adjunto, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, expedientes)

        # 15. Comunicados Oficiales
        announcements = [
            ("Publicación Oficial de Boletas de Notas del I Bimestre", "Se comunica a los padres de familia y estudiantes que las calificaciones de las 8 especialidades técnicas ya se encuentran disponibles en la Intranet.", 2, "Dirección General - Lic. Manuel Romero Salazar", "TODOS", "Académico"),
            ("Protocolo Obligatorio de Seguridad y EPP en Talleres", "Queda terminantemente prohibido el encendido de tornos CNC, compresores y tableros de 380V sin el uso integral de botas con punta de acero y lentes de protección.", 4, "Prof. Roberto Bazán - Jefatura de Taller", "TODOS", "Seguridad"),
            ("Celebración de los 69 Años de la I.E. INEI N° 34", "Invitamos a toda la comunidad inista a participar en la gran feria de proyectos técnicos y desfile en la Plaza de Armas de Chancay.", 1, "Comisión de Aniversario", "TODOS", "Institucional")
        ]
        cursor.executemany("""
        INSERT INTO announcements (title, content, author_id, author_name, audience, tag)
        VALUES (?, ?, ?, ?, ?, ?)
        """, announcements)

        # 16. Alerta Temprana (Indicador de apoyo)
        cursor.execute("""
        INSERT INTO early_warnings (student_id, warning_type, description, severity, status)
        VALUES (?, 'Inasistencia Reiterada', 'Se identifican 2 inasistencias en el taller de mecanizado que podrían requerir seguimiento tutorial.', 'Media', 'ABIERTA')
        """, (st_ids[7],))

        # 17. Registro de Auditoría Inicial
        cursor.execute("""
        INSERT INTO audit_logs (user_id, username, role, action, module, record_id, details, ip_address)
        VALUES (1, 'admin', 'admin', 'SYSTEM_INITIALIZATION', 'SISTEMA', 'DB_INIT', 'Base de datos relacional SQLite inicializada con 22 tablas y datos semilla del INEI 34', '127.0.0.1')
        """)

        # 18. Centro de Ayuda & Tickets de Soporte TI Semilla
        cursor.execute("SELECT COUNT(*) FROM support_tickets")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO support_tickets (ticket_code, user_id, user_name, user_role, user_email, user_dni, subject, priority, area, description, status, solution, admin_response_by, resolved_at)
            VALUES 
            ('TCK-2026-001', 4, 'Prof. Roberto Bazán', 'DOCENTE', 'rbazan@inei34chancay.edu.pe', '10234567', 'Restablecimiento de contraseña para alumno Diego Quispe', 'MEDIA', 'Mecánica de Producción', 'El alumno Diego Quispe de 5to A olvidó su contraseña de acceso y no puede subir sus planos de torno.', 'RESUELTO', 'Contraseña temporal asignada por Administrador: 123456. Se recomendó al estudiante cambiarla en su primer inicio de sesión.', 'Lic. Carlos S. (Admin TI)', '01/10/2026 10:15 AM'),
            ('TCK-2026-002', 4, 'Prof. Roberto Bazán', 'DOCENTE', 'rbazan@inei34chancay.edu.pe', '10234567', 'Calibración de lectura en vernier digital de Taller N° 2', 'ALTA', 'Mecánica de Producción', 'Dos vernieres digitales Mitutoyo del banco 4 presentan desfase de 0.05 mm en la lectura cero.', 'EN ATENCIÓN', 'Equipo derivado a calibración de precisión. Se asignaron 2 vernieres de reserva del almacén central para no interrumpir la práctica.', 'Lic. Carlos S. (Admin TI)', NULL),
            ('TCK-2026-003', 3, 'Lic. Rosa Flores Meléndez', 'SECRETARÍA', 'secretaria@inei34.edu.pe', '08765432', 'Habilitación de módulo para matrículas extemporáneas', 'ALTA', 'Secretaría General', 'Se requiere autorización para registrar matrícula excepcional de dos estudiantes trasladados de la UGEL 10 Huaral fuera de fecha ordinaria.', 'PENDIENTE', NULL, NULL, NULL),
            ('TCK-2026-004', 2, 'Lic. Manuel Romero Salazar', 'DIRECTOR', 'director@inei34.edu.pe', '09876543', 'Revisión técnica de proyector multimedia en Sala de Innovación', 'MEDIA', 'Dirección General', 'El proyector Epson de la Sala 1 no detecta la señal HDMI desde la laptop institucional del docente.', 'PENDIENTE', NULL, NULL, NULL)
            """)

        # 19. Mensajes Iniciales de Chat Mesa de Ayuda
        cursor.execute("SELECT COUNT(*) FROM support_chat_messages")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO support_chat_messages (user_id, user_name, user_role, sender, text)
            VALUES 
            (4, 'Prof. Roberto Bazán', 'DOCENTE', 'bot', '👋 ¡Hola Prof. Roberto! Soy el Asistente de Soporte Técnico Smart-Core de la I.E. INEI N° 34 Chancay. ¿En qué te puedo ayudar hoy? Puedes consultar tus dudas o crear un ticket oficial para el Administrador.'),
            (4, 'Prof. Roberto Bazán', 'DOCENTE', 'user', 'Buenas tardes estimado administrador, tengo una duda sobre el aforo en el taller de torneado.'),
            (4, 'Prof. Roberto Bazán', 'DOCENTE', 'admin', 'Buenas tardes Prof. Roberto. El aforo máximo normativo según directiva 5S es de 20 estudiantes por turno en taller de mecanizado.')
            """)

        # 20. Notificaciones Iniciales del Sistema y Soporte
        cursor.execute("SELECT COUNT(*) FROM notifications")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type, link, is_read)
            VALUES 
            (1, 'Nuevo Ticket Pendiente (TCK-2026-003)', 'La Lic. Rosa Flores Meléndez (SECRETARÍA) ha enviado un ticket sobre matrícula extemporánea.', 'ticket', 'admin_help', 0),
            (1, 'Nuevo Ticket Pendiente (TCK-2026-004)', 'El Director Lic. Manuel Romero Salazar reportó una falla en el proyector de Sala de Innovación.', 'ticket', 'admin_help', 0),
            (1, 'Nuevo Mensaje en Chat Mesa de Ayuda', 'El docente Prof. Roberto Bazán envió una consulta técnica en el chat.', 'chat', 'admin_help', 0),
            (4, 'Ticket TCK-2026-001 Resuelto', 'El Administrador TI ha resuelto tu ticket sobre restablecimiento de contraseña.', 'ticket', 'doc_help', 0)
            ''')

