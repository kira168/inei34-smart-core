# INEI SMART-CORE 2.0

> **"Desarrollo de una intranet educativa con inteligencia artificial para apoyar la gestión institucional de la I.E. INEI 34 Chancay, 2026"**

Plataforma educativa integral y modular diseñada específicamente para la **I.E. Emblemática INEI N° 34 Chancay** (UGEL 10 Huaral, Lima Provincias - Perú).

---

## 🌟 CARACTERÍSTICAS PRINCIPALES

1. **Portal Web Institucional:**
   - Presentación de las **10 Áreas Curriculares** y las **7 Especialidades Técnicas** (Mecánica de Producción, Ebanistería, Electricidad, Computación, Contabilidad, Estética Personal y Automotores).
   - **Mesa de Partes Virtual Pública** con generación de código de seguimiento único (`EXP-2026-XXXX`).
   - Módulo de consulta ciudadana de expedientes en tiempo real.

2. **Intranet Educativa con RBAC Estricto (6 Roles):**
   - `ADMINISTRADOR`: Control del sistema, seguridad y trazabilidad forense.
   - `DIRECTOR`: KPIs ejecutivos, gráficos de asistencia y alertas tempranas institucionales.
   - `SECRETARÍA`: Padrón de matrículas y atención de trámites documentarios.
   - `DOCENTE`: Toma de asistencia en 1-clic, registro de notas por competencias CNEB (C1 a C4), y **exportación a Excel oficial para SIAGIE**.
   - `ESTUDIANTE`: Mis cursos técnicos, tareas, horario y calificaciones.
   - `PADRE / APODERADO`: Consulta confidencial exclusiva del estado académico de sus hijos.

3. **Centro de Inteligencia Artificial Contextual por Rol (Ollama Local):**
   - Privacidad total: la IA corre de forma local sin enviar datos de los alumnos a la nube.
   - **Docente:** Generador de Sesiones de Aprendizaje CNEB (Inicio, Desarrollo, Cierre, 5S y Rúbrica) y Exámenes Técnicos de taller.
   - **Director:** Análisis ejecutivo de asistencia y diagnóstico de riesgo de deserción.
   - **Estudiante:** Tutor Socrático Anti-Plagio que guía el razonamiento paso a paso sin dar respuestas directas.
   - **Secretaría:** Redactor protocolar de oficios, memorandos y resoluciones.

4. **Base de Datos Relacional SQLite Normalizada:**
   - 22 tablas con integridad referencial y modo WAL para máxima velocidad y fiabilidad.

---

## 🚀 INICIO RÁPIDO

### 1. Iniciar el Servidor

Ejecuta el servidor web mediante Python:

```powershell
python run.py
```

El servidor estará disponible en:
- **Portal Web Público:** `http://127.0.0.1:8000/`
- **Acceso a Intranet:** `http://127.0.0.1:8000/login`
- **Intranet Principal:** `http://127.0.0.1:8000/intranet`

---

## 🔑 CUENTAS DE PRUEBA Y SELECTOR DEMO

En la pantalla de inicio de sesión (`/login`) y en la barra superior de la Intranet dispones de un **Selector de Modo Demostración (1 Clic)** para alternar al instante entre los 6 roles.

También puedes ingresar manualmente con las siguientes credenciales:

| Rol | Usuario / DNI | Contraseña |
|---|---|---|
| **Administrador** | `admin` | `admin123` |
| **Director** | `director` | `director123` |
| **Secretaría** | `secretaria` | `secre123` |
| **Docente** | `docente` | `docente123` |
| **Estudiante** | `estudiante` | `alumno123` |
| **Apoderado** | `apoderado` | `padre123` |

---

## 🧪 SUITE DE PRUEBAS AUTOMATIZADAS

Para validar todos los módulos, la base de datos y el motor de IA:

```powershell
python app/test_suite.py
```

*Resultado: 8/8 pruebas aprobadas con éxito (100%).*

---

## 📚 DOCUMENTACIÓN TÉCNICA

- [Arquitectura del Sistema](file:///docs/PROJECT_ARCHITECTURE.md)
- [Diccionario de Base de Datos (22 Tablas)](file:///docs/DATABASE.md)
- [Matriz de Roles y Permisos (RBAC)](file:///docs/RBAC.md)
- [Arquitectura de Inteligencia Artificial](file:///docs/AI_ARCHITECTURE.md)
- [Documentación de Endpoints (API REST)](file:///docs/API.md)
- [Reporte de Pruebas y Verificación](file:///docs/TESTING.md)
