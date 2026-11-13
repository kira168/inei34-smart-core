from app.database.connection import db_session

def create_schema():
    """Crea el esquema completo con 22 tablas relacionales normalizadas."""
    with db_session() as conn:
        cursor = conn.cursor()

        # 1. Usuarios
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE,
            role TEXT NOT NULL,
            phone TEXT,
            dni TEXT,
            avatar_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. Roles
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_key TEXT UNIQUE NOT NULL,
            role_name TEXT NOT NULL,
            description TEXT
        )
        """)

        # 3. Permisos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            perm_key TEXT UNIQUE NOT NULL,
            description TEXT,
            module TEXT
        )
        """)

        # 4. Mapeo Roles - Permisos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            UNIQUE(role, permission)
        )
        """)

        # 5. Padres / Apoderados
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS parents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            dni TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            email TEXT,
            occupation TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # 6. Docentes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            dni TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            condition TEXT DEFAULT 'Nombrado',
            academic_degree TEXT DEFAULT 'Licenciado en Educación Técnica',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # 7. Grados, Secciones y Talleres
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade TEXT NOT NULL,
            section_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            tutor_id INTEGER,
            academic_year TEXT DEFAULT '2026',
            capacity INTEGER DEFAULT 35,
            shift TEXT DEFAULT 'Mañana',
            FOREIGN KEY (tutor_id) REFERENCES teachers(id) ON DELETE SET NULL
        )
        """)

        # 8. Estudiantes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            dni TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            grade TEXT NOT NULL,
            section TEXT NOT NULL,
            parent_id INTEGER,
            section_id INTEGER,
            status TEXT DEFAULT 'Activo',
            birth_date TEXT,
            address TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (parent_id) REFERENCES parents(id) ON DELETE SET NULL,
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL
        )
        """)

        # 9. Cursos y Módulos Técnicos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            grade TEXT NOT NULL,
            hours_per_week INTEGER DEFAULT 4,
            teacher_id INTEGER,
            syllabus_file TEXT,
            section_name TEXT DEFAULT 'A',
            room TEXT DEFAULT 'Aula Polifuncional',
            color_bg TEXT DEFAULT 'bg-red-600',
            image_url TEXT,
            content_json TEXT DEFAULT '{"units": []}',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        )
        """)

        # Migración idempotente para bases existentes
        try:
            cursor.execute("PRAGMA table_info(courses)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in [
                ("section_name", "TEXT DEFAULT 'A'"),
                ("room", "TEXT DEFAULT 'Aula Polifuncional'"),
                ("color_bg", "TEXT DEFAULT 'bg-red-600'"),
                ("image_url", "TEXT"),
                ("content_json", 'TEXT DEFAULT \'{"units": []}\''),
                ("is_active", "INTEGER DEFAULT 1"),
                ("created_at", "TEXT"),
                ("updated_at", "TEXT")
            ]:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE courses ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

        # 10. Matrículas (Enrollments)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            academic_year TEXT DEFAULT '2026',
            status TEXT DEFAULT 'Matriculado',
            enrollment_date TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE RESTRICT,
            UNIQUE(student_id, academic_year)
        )
        """)

        # 11. Asistencia Diaria
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            section_id INTEGER,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('P', 'T', 'F', 'J')),
            recorded_by INTEGER,
            remarks TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL,
            FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(student_id, date)
        )
        """)

        # 12. Evaluaciones y Notas SIAGIE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            bimester TEXT NOT NULL,
            c1 TEXT DEFAULT 'A',
            c2 TEXT DEFAULT 'A',
            c3 TEXT DEFAULT 'A',
            c4 TEXT DEFAULT 'A',
            final_grade TEXT DEFAULT 'A',
            conclusion TEXT,
            updated_by INTEGER,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(student_id, course_id, bimester)
        )
        """)

        # 13. Tareas y Asignaciones
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
        )
        """)

        # 14. Entregas de Tareas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            submission_text TEXT,
            file_path TEXT,
            grade TEXT,
            feedback TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(assignment_id, student_id)
        )
        """)

        # 15. Repositorio de Documentos Institucionales
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size_kb REAL DEFAULT 0,
            uploaded_by INTEGER,
            is_public INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # 16. Mesa de Partes Virtual
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesa_partes_solicitudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expediente_code TEXT UNIQUE NOT NULL,
            solicitante_dni TEXT NOT NULL,
            solicitante_name TEXT NOT NULL,
            solicitante_email TEXT,
            solicitante_phone TEXT,
            tipo_tramite TEXT NOT NULL,
            asunto TEXT NOT NULL,
            status TEXT DEFAULT 'RECIBIDO' CHECK(status IN ('RECIBIDO', 'EN REVISIÓN', 'EN PROCESO', 'ATENDIDO', 'OBSERVADO')),
            responsable_id INTEGER,
            documento_adjunto TEXT,
            observaciones TEXT,
            fecha_registro TEXT DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (responsable_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # 17. Comunicados y Avisos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER,
            author_name TEXT NOT NULL,
            audience TEXT DEFAULT 'TODOS',
            tag TEXT DEFAULT 'General',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # 18. Notificaciones de Usuario
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            link TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # 19. Citas y Tutoría con Padres
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            date_time TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'PENDIENTE' CHECK(status IN ('PENDIENTE', 'CONFIRMADA', 'REALIZADA', 'CANCELADA')),
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES parents(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """)

        # 20. Auditoría Forense (Audit Log Inmutable)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            module TEXT NOT NULL,
            record_id TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # 21. Alertas Tempranas (Indicador de Apoyo)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS early_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            warning_type TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'Media',
            status TEXT DEFAULT 'ABIERTA',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """)

        # 22. Conversaciones e Historial IA (Auditoría General)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            model_used TEXT,
            context_module TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # 23. Sesiones de Conversación SmartTutor AI (NEXUS INEI)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smarttutor_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject_id TEXT DEFAULT 'electricidad',
            mode TEXT DEFAULT 'paso_a_paso',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # 24. Mensajes Persistentes de SmartTutor AI
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smarttutor_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender TEXT NOT NULL CHECK(sender IN ('user', 'bot', 'assistant', 'system')),
            content TEXT NOT NULL,
            mode TEXT,
            model_used TEXT,
            is_fallback INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES smarttutor_conversations(id) ON DELETE CASCADE
        )
        """)

        # 25. Biblioteca de Documentos Institucionales Autorizados (RAG)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            collection_id TEXT NOT NULL DEFAULT 'smarttutor' CHECK(collection_id IN ('smarttutor', 'smartteacher', 'compartido')),
            subject_id TEXT NOT NULL,
            grade_level INTEGER CHECK(grade_level BETWEEN 1 AND 5 OR grade_level IS NULL),
            technical_specialty TEXT,
            material_type TEXT NOT NULL DEFAULT 'teoria' CHECK(material_type IN ('teoria', 'ejercicio_resuelto', 'banco_admision', 'sesion_formato', 'ficha_taller', 'examen_balotario', 'rubrica', 'normativa_institucional', 'guia_docente')),
            version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
            indexing_status TEXT NOT NULL DEFAULT 'activo' CHECK(indexing_status IN ('pendiente', 'procesando', 'activo', 'error', 'desactivado')),
            security_review_status TEXT NOT NULL DEFAULT 'en_revision' CHECK(security_review_status IN ('aprobado', 'en_revision', 'cuarentena_sensible', 'rechazado')),
            error_message TEXT,
            description TEXT,
            file_name TEXT,
            file_type TEXT,
            uploaded_by INTEGER,
            role_access TEXT DEFAULT 'TODOS' CHECK(role_access IN ('TODOS', 'ESTUDIANTE', 'DOCENTE', 'ADMINISTRADOR', 'DIRECTOR')),
            is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_subject ON knowledge_documents(subject_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_active ON knowledge_documents(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_access ON knowledge_documents(role_access)")
        cursor.execute("PRAGMA table_info(knowledge_documents)")
        k_cols = {r[1] for r in cursor.fetchall()}
        if "indexing_status" in k_cols:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_rag_gate ON knowledge_documents(is_active, indexing_status, security_review_status, collection_id, role_access)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_coll_subject ON knowledge_documents(collection_id, subject_id)")

        # 26. Fragmentos Semánticos de Documentos (Chunks)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER,
            section_title TEXT,
            content TEXT NOT NULL,
            char_length INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kchunks_doc ON knowledge_chunks(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kchunks_order ON knowledge_chunks(document_id, chunk_index)")

        # 27. Tabla Virtual de Búsqueda de Texto Completo FTS5 (Full-Text Search)
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
            content,
            section_title,
            content='knowledge_chunks',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 1'
        )
        """)

        # Triggers de Sincronización Automática para FTS5
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
            INSERT INTO knowledge_chunks_fts(rowid, content, section_title)
            VALUES (new.id, new.content, new.section_title);
        END;
        """)

        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
            INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts, rowid, content, section_title)
            VALUES('delete', old.id, old.content, old.section_title);
        END;
        """)

        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
            INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts, rowid, content, section_title)
            VALUES('delete', old.id, old.content, old.section_title);
            INSERT INTO knowledge_chunks_fts(rowid, content, section_title)
            VALUES (new.id, new.content, new.section_title);
        END;
        """)

        # 28. Intentos y Evaluaciones Formativas SmartTutor AI (Quizzes)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smarttutor_quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id TEXT NOT NULL,
            total_questions INTEGER NOT NULL,
            correct_answers INTEGER NOT NULL,
            score_percentage REAL NOT NULL,
            achievement_level TEXT DEFAULT 'B',
            details_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_quiz_user ON smarttutor_quiz_attempts(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_quiz_subject ON smarttutor_quiz_attempts(subject_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_quiz_date ON smarttutor_quiz_attempts(created_at)")

        # 29. Control y Limitación de Frecuencia (Rate Limiting) Mesa de Partes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesa_partes_rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_ip_time ON mesa_partes_rate_limits(ip_address, timestamp)")

        # 30. Sesiones Persistentes de Usuario (Fase 6.7)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            dni TEXT,
            full_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            role TEXT NOT NULL,
            role_name TEXT NOT NULL,
            role_id INTEGER DEFAULT 1,
            avatar_url TEXT,
            expires_at REAL NOT NULL,
            is_revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)")

        # 31. Documentos y Planificaciones Pedagógicas SmartTeacher AI (Fase 7.3 & Fase 8.0)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smartteacher_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            course_id INTEGER,
            unit_id INTEGER,
            session_id INTEGER,
            doc_type TEXT NOT NULL CHECK(doc_type IN (
                'sesion_aprendizaje',
                'ficha_actividad',
                'examen_tecnico',
                'rubrica_evaluacion',
                'material_apoyo',
                'unidad_didactica'
            )),
            title TEXT NOT NULL,
            specialty TEXT NOT NULL,
            grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 5),
            section_name TEXT DEFAULT 'A',
            duration_minutes INTEGER DEFAULT 90,
            topic TEXT NOT NULL,
            competence TEXT,
            purpose TEXT,
            content_markdown TEXT NOT NULL,
            content_json TEXT NOT NULL,
            status TEXT DEFAULT 'BORRADOR' CHECK(status IN ('BORRADOR', 'REVISADO', 'PUBLICADO', 'ARCHIVADO')),
            version INTEGER DEFAULT 1,
            is_public INTEGER DEFAULT 0 CHECK(is_public IN (0, 1)),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
            FOREIGN KEY (unit_id) REFERENCES smartteacher_didactic_units(id) ON DELETE SET NULL,
            FOREIGN KEY (session_id) REFERENCES smartteacher_documents(id) ON DELETE SET NULL
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_teacher ON smartteacher_documents(teacher_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_user ON smartteacher_documents(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_type ON smartteacher_documents(doc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_status ON smartteacher_documents(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_created ON smartteacher_documents(created_at)")

        # Columnas de vinculación en cascada Fase 8.0
        cursor.execute("PRAGMA table_info(smartteacher_documents)")
        doc_cols = {row[1] for row in cursor.fetchall()}
        if doc_cols and "unit_id" not in doc_cols:
            try:
                cursor.execute("ALTER TABLE smartteacher_documents ADD COLUMN unit_id INTEGER REFERENCES smartteacher_didactic_units(id) ON DELETE SET NULL")
            except Exception:
                pass
        if doc_cols and "session_id" not in doc_cols:
            try:
                cursor.execute("ALTER TABLE smartteacher_documents ADD COLUMN session_id INTEGER REFERENCES smartteacher_documents(id) ON DELETE SET NULL")
            except Exception:
                pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_unit_id ON smartteacher_documents(unit_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_docs_session_id ON smartteacher_documents(session_id)")
        except Exception:
            pass

        # 32. Unidades Didácticas Oficiales y Planificación en Cascada SmartTeacher AI (Fase 8.0)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smartteacher_didactic_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            course_id INTEGER,
            title TEXT NOT NULL,
            academic_year TEXT DEFAULT '2026',
            bimester TEXT DEFAULT 'IV Bimestre',
            unit_number INTEGER DEFAULT 4,
            specialty TEXT NOT NULL,
            formative_module TEXT,
            grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 5),
            section_name TEXT DEFAULT 'A',
            responsible_teacher TEXT NOT NULL,
            director_name TEXT DEFAULT 'Tomas Jurado Zevallos',
            subdirector_name TEXT DEFAULT 'Mg. Javier Eulogio Rosas Maguiña',
            workshop_boss_name TEXT,
            start_date TEXT,
            end_date TEXT,
            duration_weeks INTEGER DEFAULT 9,
            weekly_hours INTEGER DEFAULT 8,
            total_hours INTEGER DEFAULT 72,
            unit_description TEXT,
            technical_matrix_json TEXT,
            entrepreneurship_matrix_json TEXT,
            technical_purposes_json TEXT,
            entrepreneurship_purposes_json TEXT,
            sessions_plan_json TEXT NOT NULL,
            bibliography_json TEXT,
            signatures_json TEXT,
            content_markdown TEXT,
            content_json TEXT NOT NULL,
            status TEXT DEFAULT 'BORRADOR' CHECK(status IN ('BORRADOR', 'REVISADO', 'APROBADO', 'ARCHIVADO')),
            version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_teacher ON smartteacher_didactic_units(teacher_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_user ON smartteacher_didactic_units(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_spec_grade ON smartteacher_didactic_units(specialty, grade)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_units_created ON smartteacher_didactic_units(created_at)")

        # 33. Tabla de Control de Versiones de Migraciones de Base de Datos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 34. Preferencias de Formato y Plantillas Docentes SmartTeacher AI (Fase 8.1)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smartteacher_teacher_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            teacher_id INTEGER,
            preferred_specialty TEXT,
            preferred_grade INTEGER DEFAULT 5,
            include_5s_safety INTEGER DEFAULT 1,
            include_visual_placeholders INTEGER DEFAULT 1,
            include_teacher_key INTEGER DEFAULT 1,
            evaluation_style TEXT DEFAULT 'vigesimal',
            custom_sections_json TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_pref_user ON smartteacher_teacher_preferences(user_id)")

        # 35. Biblioteca de Plantillas y Modelos Reales SmartTeacher AI (Fase 8.6)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS smartteacher_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            teacher_id INTEGER,
            name TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            file_path TEXT,
            file_bytes BLOB,
            blueprint_json TEXT,
            fields_json TEXT,
            styles_json TEXT,
            is_institutional INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_user ON smartteacher_templates(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_type ON smartteacher_templates(doc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_tpl_inst ON smartteacher_templates(is_institutional)")

        # 36. Centro de Ayuda & Tickets de Soporte TI
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_code TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            user_role TEXT NOT NULL,
            user_email TEXT,
            user_dni TEXT,
            subject TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'MEDIA',
            area TEXT NOT NULL DEFAULT 'General',
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDIENTE',
            solution TEXT,
            admin_response_by TEXT,
            resolved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_code ON support_tickets(ticket_code)")

        # 37. Chat en Vivo de Mesa de Ayuda y Soporte
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            user_role TEXT NOT NULL,
            sender TEXT NOT NULL, -- 'user', 'admin', 'bot'
            text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_chat_user ON support_chat_messages(user_id)")

        # 38. Entregas de Exámenes con Temporizador
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS exam_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            unit_id TEXT,
            ses_id TEXT,
            exam_title TEXT,
            student_id INTEGER,
            student_name TEXT,
            student_dni TEXT,
            score REAL,
            total_points REAL,
            correct_count INTEGER,
            total_questions INTEGER,
            cneb_level TEXT,
            answers_json TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            feedback TEXT,
            teacher_reviewed INTEGER DEFAULT 0
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exam_sub_course_ses ON exam_submissions(course_id, ses_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exam_sub_student ON exam_submissions(student_id)")

        # 39. Entregas de Tareas de Sesión Blackboard
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_task_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            unit_id TEXT,
            ses_id TEXT,
            task_id TEXT,
            task_title TEXT,
            student_id INTEGER,
            student_name TEXT,
            student_dni TEXT,
            submission_text TEXT,
            file_path TEXT,
            file_name TEXT,
            grade REAL,
            cneb_level TEXT,
            feedback TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            graded_at TEXT,
            UNIQUE(course_id, ses_id, task_id, student_id)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_sub_course_task ON session_task_submissions(course_id, ses_id, task_id)")

        # Garantizar columna 'dni' en users para bases existentes
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [c[1] for c in cursor.fetchall()]
        if 'dni' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN dni TEXT")

    try:
        from app.database.migrations.migration_etapa3_firewall import migrate_firewall_schema
        migrate_firewall_schema()
    except Exception:
        pass

create_all_tables = create_schema

