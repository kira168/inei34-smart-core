from typing import Optional, Dict, Any, List
"""
INEI SMART-CORE - Educational Visual Diagram Engine
Generates high-resolution, pedagogical visual diagrams using Matplotlib and Pillow
to embed inside PowerPoint presentations, worksheets, and study guides.
"""

import os
import hashlib
import io
import logging
import numpy as np

os.environ['MPLCONFIGDIR'] = os.path.join(os.getcwd(), 'data', 'temp_mpl')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

logger = logging.getLogger("diagram_generator")

DIAGRAMS_DIR = os.path.join(os.getcwd(), "data", "diagrams")
os.makedirs(DIAGRAMS_DIR, exist_ok=True)

class DiagramGenerator:
    """Generates thematic visual educational diagrams for school presentations."""

    @classmethod
    def get_or_create_diagram(cls, topic: str, specialty: str) -> Optional[str]:
        """
        Determines the most relevant educational diagram based on the topic and area,
        generates it as a crisp PNG, and returns the absolute file path.
        """
        text = f"{topic} {specialty}".lower()
        try:
            # 1. Biología / Genética (ADN, ARN, Célula)
            if any(k in text for k in ["adn", "arn", "genet", "genét", "celul", "célul", "molecular", "herenci"]):
                return cls.create_dna_double_helix_diagram()

            # 2. Computación e Informática (Carpetas, Archivos, Sistemas)
            elif any(k in text for k in ["carpeta", "archivo", "computac", "informat", "windows", "directorio", "digital"]):
                return cls.create_folder_hierarchy_diagram()

            # 3. Historia / Ciencias Sociales (Hominización, Evolución, Culturas)
            elif any(k in text for k in ["hominiz", "neolit", "paleolit", "historia", "cronolog", "evoluc", "cultura", "caral", "chavin"]):
                return cls.create_history_timeline_diagram(topic)

            # 4. Educación Física (Frecuencia Cardíaca, Salud, Entrenamiento)
            elif any(k in text for k in ["fisica", "física", "cardiac", "cardíac", "pulso", "respirat", "motriz", "deporte"]):
                return cls.create_heart_rate_diagram()

            # 5. DPCC (Emociones, Convivencia, Autorregulación)
            elif any(k in text for k in ["emocion", "emoción", "autorregul", "convivencia", "autoestima", "asertiv"]):
                return cls.create_emotional_regulation_diagram()

            # 6. Matemática (Plano Cartesiano, Ecuaciones, Funciones, Gráficos)
            elif any(k in text for k in ["matemat", "matemát", "algebra", "álgebra", "geometr", "ecuacion", "función", "funcion", "trigonom", "calcul", "parabola"]):
                return cls.create_math_coordinate_diagram(topic)

            # 7. Mecánica de Producción / Automotriz / Taller EPT
            elif any(k in text for k in ["mecanic", "torno", "soldad", "metal", "mecaniz", "producc", "automotr", "freno", "motor"]):
                return cls.create_industrial_process_diagram(topic)

            # 8. Electricidad y Electrónica
            elif any(k in text for k in ["electr", "circuito", "voltaje", "corriente", "tablero", "pozo a tierra"]):
                return cls.create_electrical_circuit_diagram(topic)

            # 9. Comunicación (Estructura Textual y Comprensión)
            elif any(k in text for k in ["comunicac", "texto", "lectura", "ensayo", "literat", "narrat", "poema", "redacc"]):
                return cls.create_text_structure_diagram(topic)

            # 10. Diagrama Conceptual / Flujo Universal
            else:
                return cls.create_universal_concept_diagram(topic)
        except Exception as e:
            logger.warning(f"Error generando diagrama educativo: {e}")
            return None

    @classmethod
    def create_dna_double_helix_diagram(cls) -> str:
        """Diagrama de alta resolución de la Doble Hélice y Complementariedad de Bases Nitrogenadas."""
        out_path = os.path.join(DIAGRAMS_DIR, "diagram_dna_helix.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#F0FDF4')
        ax.set_facecolor('#F0FDF4')

        t = np.linspace(0, 4 * np.pi, 250)
        x1 = np.sin(t)
        x2 = -np.sin(t)
        y = np.linspace(0, 10, 250)

        # Hebras fosfodiéster
        ax.plot(x1, y, color='#0D9488', lw=4.5, label="Hebra 5' -> 3'", zorder=3)
        ax.plot(x2, y, color='#059669', lw=4.5, label="Hebra 3' -> 5'", zorder=3)

        # Peldaños de bases nitrogenadas
        rungs_y = np.linspace(0.6, 9.4, 15)
        base_colors = [('#EF4444', '#3B82F6'), ('#10B981', '#F59E0B')]

        for i, ry in enumerate(rungs_y):
            sin_v = np.sin(ry * (4 * np.pi / 10))
            c_l, c_r = base_colors[i % 2]
            ax.plot([0, sin_v], [ry, ry], color=c_l, lw=3.2, zorder=2)
            ax.plot([0, -sin_v], [ry, ry], color=c_r, lw=3.2, zorder=2)
            ax.scatter([0], [ry], color='#CBD5E1', s=25, zorder=4)

        ax.set_xlim(-1.8, 1.8)
        ax.set_ylim(-0.8, 10.8)
        ax.axis('off')

        ax.text(0, 10.4, 'ARQUITECTURA DE LA DOBLE HÉLICE', ha='center', fontsize=12, fontweight='bold', color='#065F46')
        # Puntos geométricos nativos sin glifos especiales
        ax.scatter([-1.4], [-0.4], color='#EF4444', s=45, zorder=5)
        ax.text(-1.3, -0.48, 'Adenina (A) = Timina (T)', ha='left', fontsize=8.5, fontweight='bold', color='#B91C1C')
        ax.scatter([0.25], [-0.4], color='#059669', s=45, zorder=5)
        ax.text(0.35, -0.48, 'Citosina (C) = Guanina (G)', ha='left', fontsize=8.5, fontweight='bold', color='#047857')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_folder_hierarchy_diagram(cls) -> str:
        """Diagrama del Árbol de Directorios y Jerarquía de Carpetas en Computación."""
        out_path = os.path.join(DIAGRAMS_DIR, "diagram_folder_tree.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#EFF6FF')
        ax.set_facecolor('#EFF6FF')

        # Draw tree boxes
        boxes = [
            (0, 3.8, "Disco Local (D:)", "#1E3A8A", "#FFFFFF", 2.2, 0.6),
            (0, 2.6, "Portafolio_2026_Alumno", "#2563EB", "#FFFFFF", 2.8, 0.6),
            (-2.2, 1.2, "01_Bimestre", "#3B82F6", "#FFFFFF", 1.8, 0.5),
            (0, 1.2, "02_Bimestre", "#3B82F6", "#FFFFFF", 1.8, 0.5),
            (2.2, 1.2, "03_Bimestre", "#3B82F6", "#FFFFFF", 1.8, 0.5),
            (-2.2, 0.1, "Tarea01.docx", "#60A5FA", "#FFFFFF", 1.8, 0.45),
            (0, 0.1, "Datos.xlsx", "#10B981", "#FFFFFF", 1.8, 0.45),
            (2.2, 0.1, "Portada.png", "#F59E0B", "#FFFFFF", 1.8, 0.45),
        ]

        # Draw lines
        ax.plot([0, 0], [3.8, 2.6], color='#94A3B8', lw=2.5, zorder=1)
        ax.plot([0, -2.2], [2.6, 1.2], color='#94A3B8', lw=2.0, zorder=1)
        ax.plot([0, 0], [2.6, 1.2], color='#94A3B8', lw=2.0, zorder=1)
        ax.plot([0, 2.2], [2.6, 1.2], color='#94A3B8', lw=2.0, zorder=1)
        ax.plot([-2.2, -2.2], [1.2, 0.1], color='#94A3B8', lw=1.5, ls='--', zorder=1)
        ax.plot([0, 0], [1.2, 0.1], color='#94A3B8', lw=1.5, ls='--', zorder=1)
        ax.plot([2.2, 2.2], [1.2, 0.1], color='#94A3B8', lw=1.5, ls='--', zorder=1)

        for bx, by, btext, bbg, bfg, bw, bh in boxes:
            rect = plt.Rectangle((bx - bw/2, by - bh/2), bw, bh, facecolor=bbg, edgecolor='#1E293B', lw=1.5, zorder=2)
            ax.add_patch(rect)
            ax.text(bx, by, btext, ha='center', va='center', fontsize=9.5, fontweight='bold', color=bfg, zorder=3)

        ax.set_xlim(-3.4, 3.4)
        ax.set_ylim(-0.4, 4.4)
        ax.axis('off')
        ax.text(0, 4.25, 'ESTRUCTURA JERÁRQUICA DE ARCHIVOS', ha='center', fontsize=11.5, fontweight='bold', color='#1E3A8A')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_history_timeline_diagram(cls, topic: str) -> str:
        """Diagrama de Línea de Tiempo Histórica con Hitos Evolutivos o Culturales."""
        t_low = (topic or "").lower()
        if any(k in t_low for k in ["caral", "poblam", "litic", "lític", "arcaic", "peru", "perú", "preinca", "andina", "chavin", "paracas", "mochica", "nazca"]):
            out_path = os.path.join(DIAGRAMS_DIR, "diagram_history_andean_timeline.png")
            stages = [
                ("Poblamiento", "14000 a.C.", "Cazadores nómadas"),
                ("Periodo Lítico", "10000 a.C.", "Paiján / Lauricocha"),
                ("Arcaico Temp.", "7000 a.C.", "Horticultura y aldeas"),
                ("Arcaico Tardío", "3000 a.C.", "Civilización Caral"),
                ("P. Formativo", "1500 a.C.", "Chavín y Kotosh")
            ]
            diagram_title = "LÍNEA DE TIEMPO: POBLAMIENTO Y CIVILIZACIÓN ANDINA"
        else:
            out_path = os.path.join(DIAGRAMS_DIR, "diagram_history_timeline.png")
            stages = [
                ("Australopithecus", "4.0 Ma", "Bipedismo inicial"),
                ("Homo Habilis", "2.5 Ma", "Primeras herramientas"),
                ("Homo Erectus", "1.8 Ma", "Uso del fuego"),
                ("Homo Sapiens", "300 Ka", "Lenguaje y arte"),
                ("Rev. Neolítica", "10 Ka", "Agricultura y aldeas")
            ]
            diagram_title = "LÍNEA DE TIEMPO DEL PROCESO HISTÓRICO"

        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#FFFBEB')
        ax.set_facecolor('#FFFBEB')

        ax.plot([0.5, 5.5], [2.2, 2.2], color='#B45309', lw=4, zorder=1)

        for idx, (title, date_str, desc) in enumerate(stages):
            x = 1.0 + idx * 1.0
            # Node circle
            ax.scatter([x], [2.2], color='#D97706', edgecolors='#78350F', s=160, lw=2.5, zorder=3)
            # Date above
            ax.text(x, 2.7, date_str, ha='center', fontsize=8.5, fontweight='bold', color='#92400E')
            # Title below
            ax.text(x, 1.6, title, ha='center', fontsize=8.5, fontweight='bold', color='#451A03', rotation=12)
            # Detail below
            ax.text(x, 0.9, desc, ha='center', fontsize=7.2, color='#78350F')

        ax.set_xlim(0.2, 5.8)
        ax.set_ylim(0.4, 3.4)
        ax.axis('off')
        ax.text(3.0, 3.2, diagram_title, ha='center', fontsize=11.0, fontweight='bold', color='#78350F')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_heart_rate_diagram(cls) -> str:
        """Diagrama de Zonas de Frecuencia Cardíaca y Salud en Educación Física."""
        out_path = os.path.join(DIAGRAMS_DIR, "diagram_heart_rate.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#F0FDFA')
        ax.set_facecolor('#F0FDFA')

        zones = [
            ("Zona Reposo", "60-80 ppm", "Calentamiento y recuperación", "#14B8A6"),
            ("Zona Aeróbica", "120-140 ppm", "Resistencia y quema de grasas", "#0D9488"),
            ("Zona Umbral", "150-170 ppm", "Rendimiento y capacidad física", "#F59E0B"),
            ("Zona Máxima", "180+ ppm", "Esfuerzo breve e intenso", "#EF4444")
        ]

        for idx, (z_title, ppm, desc, z_color) in enumerate(zones):
            y = 3.2 - idx * 0.9
            rect = plt.Rectangle((0.5, y), 5.5, 0.75, facecolor=z_color, edgecolor='#0F766E', lw=1.5, zorder=2)
            ax.add_patch(rect)
            ax.text(0.7, y + 0.38, z_title, va='center', fontsize=10, fontweight='bold', color='#FFFFFF')
            ax.text(3.2, y + 0.38, ppm, va='center', fontsize=10, fontweight='bold', color='#FEF08A')
            ax.text(5.8, y + 0.38, desc, va='center', ha='right', fontsize=8, color='#FFFFFF')

        ax.set_xlim(0.2, 6.2)
        ax.set_ylim(-0.3, 4.2)
        ax.axis('off')
        ax.text(3.2, 3.9, 'ZONAS DE FRECUENCIA CARDÍACA EN ACTIVIDAD', ha='center', fontsize=11.5, fontweight='bold', color='#0F766E')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_emotional_regulation_diagram(cls) -> str:
        """Diagrama del Semáforo Emocional para DPCC."""
        out_path = os.path.join(DIAGRAMS_DIR, "diagram_emotional_regulation.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#FAF5FF')
        ax.set_facecolor('#FAF5FF')

        steps = [
            ("1. ROJO: DETENTE", "Reconoce la emoción intensa (ira, frustración, miedo). Respira hondo antes de reaccionar.", "#EF4444"),
            ("2. AMARILLO: PIENSA", "Analiza las consecuencias de tus palabras y busca alternativas constructivas.", "#F59E0B"),
            ("3. VERDE: ACTÚA", "Comunícate de forma asertiva y resuelve el conflicto mediante el diálogo empático.", "#10B981")
        ]

        for idx, (stitle, sdesc, scolor) in enumerate(steps):
            y = 3.0 - idx * 1.1
            rect = plt.Rectangle((0.5, y), 5.5, 0.9, facecolor='#FFFFFF', edgecolor=scolor, lw=2.5, zorder=2)
            ax.add_patch(rect)
            ax.text(0.8, y + 0.58, stitle, fontsize=10.5, fontweight='bold', color=scolor)
            ax.text(0.8, y + 0.25, sdesc, fontsize=8.5, color='#334155')

        ax.set_xlim(0.2, 6.2)
        ax.set_ylim(-0.3, 4.2)
        ax.axis('off')
        ax.text(3.2, 3.9, 'EL SEMÁFORO DE LA AUTORREGULACIÓN EMOCIONAL', ha='center', fontsize=11.5, fontweight='bold', color='#581C87')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_math_coordinate_diagram(cls, topic: str) -> str:
        """Diagrama del Plano Cartesiano y Función Matemática."""
        import hashlib
        h = hashlib.md5((topic or "matematica").strip().lower().encode("utf-8")).hexdigest()[:8]
        out_path = os.path.join(DIAGRAMS_DIR, f"diagram_math_{h}.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#EFF6FF')
        ax.set_facecolor('#EFF6FF')

        x = np.linspace(-3.5, 3.5, 200)
        # Parábola representativa f(x) = 0.5 * x^2 - 1.5
        y = 0.45 * (x ** 2) - 1.2

        ax.axhline(0, color='#1E3A8A', lw=2.0, zorder=2)
        ax.axvline(0, color='#1E3A8A', lw=2.0, zorder=2)
        ax.plot(x, y, color='#2563EB', lw=3.5, label='f(x) Curva Modelo', zorder=3)

        # Puntos clave: Vértice y Raíces
        ax.scatter([0], [-1.2], color='#DC2626', s=120, edgecolors='#991B1B', lw=2, zorder=4)
        ax.text(0.2, -1.5, 'Vértice (0, -1.2)', fontsize=8.5, fontweight='bold', color='#991B1B')

        r1, r2 = -1.63, 1.63
        ax.scatter([r1, r2], [0, 0], color='#16A34A', s=100, edgecolors='#14532D', lw=2, zorder=4)
        ax.text(r1 - 0.4, 0.35, 'Raíz x₁', fontsize=8.5, fontweight='bold', color='#14532D')
        ax.text(r2 + 0.1, 0.35, 'Raíz x₂', fontsize=8.5, fontweight='bold', color='#14532D')

        ax.grid(True, linestyle='--', alpha=0.5, color='#93C5FD')
        ax.set_xlim(-4.0, 4.0)
        ax.set_ylim(-2.2, 4.2)
        ax.set_xlabel('Eje X (Abscisas)', fontsize=9, fontweight='bold', color='#1E3A8A')
        ax.set_ylabel('Eje Y (Ordenadas)', fontsize=9, fontweight='bold', color='#1E3A8A')

        t_title = f"MODELO MATEMÁTICO: {topic.upper()[:28]}"
        ax.set_title(t_title, fontsize=10.5, fontweight='bold', color='#1E3A8A', pad=8)

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_industrial_process_diagram(cls, topic: str) -> str:
        """Diagrama del Proceso Técnico Operativo y Seguridad Industrial."""
        import hashlib
        h = hashlib.md5((topic or "industrial").strip().lower().encode("utf-8")).hexdigest()[:8]
        out_path = os.path.join(DIAGRAMS_DIR, f"diagram_industrial_{h}.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#FFFBEB')
        ax.set_facecolor('#FFFBEB')

        steps = [
            ("1. Planificación", "Lectura de planos y hoja de operaciones", "#B45309"),
            ("2. Preparación y EPP", "Inspección de máquinas y protección personal", "#D97706"),
            ("3. Mecanizado Técnico", "Ejecución de operaciones según parámetros", "#EA580C"),
            ("4. Control de Calidad", "Verificación dimensional con instrumentos", "#059669")
        ]

        for idx, (stitle, sdesc, scolor) in enumerate(steps):
            y = 3.2 - idx * 0.95
            rect = plt.Rectangle((0.5, y), 5.5, 0.78, facecolor='#FFFFFF', edgecolor=scolor, lw=2.2, zorder=2)
            ax.add_patch(rect)
            ax.text(0.8, y + 0.48, stitle, fontsize=10.0, fontweight='bold', color=scolor)
            ax.text(0.8, y + 0.18, sdesc, fontsize=8.2, color='#451A03')

        ax.set_xlim(0.2, 6.2)
        ax.set_ylim(-0.3, 4.2)
        ax.axis('off')
        ax.text(3.2, 4.0, f'CICLO TÉCNICO PRODUCTIVO: {topic.upper()[:26]}', ha='center', fontsize=11, fontweight='bold', color='#78350F')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_electrical_circuit_diagram(cls, topic: str) -> str:
        """Diagrama del Circuito y Seguridad Eléctrica."""
        import hashlib
        h = hashlib.md5((topic or "electricidad").strip().lower().encode("utf-8")).hexdigest()[:8]
        out_path = os.path.join(DIAGRAMS_DIR, f"diagram_electric_{h}.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#F8FAFC')
        ax.set_facecolor('#F8FAFC')

        blocks = [
            ("Acometida / Red", 1.0, 2.2, "#0284C7"),
            ("Tablero / Termomagnético", 2.6, 2.2, "#EAB308"),
            ("Carga / Receptor", 4.2, 2.2, "#16A34A"),
            ("Pozo a Tierra", 5.6, 2.2, "#15803D")
        ]

        ax.plot([1.0, 5.6], [2.2, 2.2], color='#0F172A', lw=3.0, zorder=1)

        for btitle, bx, by, bcolor in blocks:
            circle = plt.Circle((bx, by), 0.55, color=bcolor, ec='#0F172A', lw=2, zorder=2)
            ax.add_patch(circle)
            ax.text(bx, by - 0.95, btitle, ha='center', fontsize=8.0, fontweight='bold', color='#0F172A')

        ax.set_xlim(0.2, 6.4)
        ax.set_ylim(0.5, 3.8)
        ax.axis('off')
        ax.text(3.3, 3.3, f'ESQUEMA DE PROTECCIÓN ELÉCTRICA: {topic.upper()[:24]}', ha='center', fontsize=10.5, fontweight='bold', color='#0F172A')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_text_structure_diagram(cls, topic: str) -> str:
        """Diagrama de Estructura Textual y Comprensión Lectora."""
        import hashlib
        h = hashlib.md5((topic or "comunicacion").strip().lower().encode("utf-8")).hexdigest()[:8]
        out_path = os.path.join(DIAGRAMS_DIR, f"diagram_text_{h}.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#FFF1F2')
        ax.set_facecolor('#FFF1F2')

        parts = [
            ("1. INTRODUCCIÓN", "Presentación del tema, contexto y tesis central.", "#BE123C"),
            ("2. DESARROLLO", "Argumentos fundamentados, evidencias y análisis crítico.", "#9F1239"),
            ("3. CONCLUSIÓN", "Síntesis de ideas principales y reflexión valorativa.", "#881337")
        ]

        for idx, (ptitle, pdesc, pcolor) in enumerate(parts):
            y = 2.9 - idx * 1.1
            rect = plt.Rectangle((0.5, y), 5.5, 0.85, facecolor='#FFFFFF', edgecolor=pcolor, lw=2.2, zorder=2)
            ax.add_patch(rect)
            ax.text(0.8, y + 0.52, ptitle, fontsize=10.0, fontweight='bold', color=pcolor)
            ax.text(0.8, y + 0.22, pdesc, fontsize=8.5, color='#4C0519')

        ax.set_xlim(0.2, 6.2)
        ax.set_ylim(-0.3, 4.2)
        ax.axis('off')
        ax.text(3.2, 3.9, f'ESTRUCTURA TEXTUAL: {topic.upper()[:28]}', ha='center', fontsize=11, fontweight='bold', color='#881337')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path

    @classmethod
    def create_universal_concept_diagram(cls, topic: str) -> str:
        """Diagrama conceptual de flujo universal para cualquier tema."""
        import hashlib
        h = hashlib.md5((topic or "universal").strip().lower().encode("utf-8")).hexdigest()[:8]
        out_path = os.path.join(DIAGRAMS_DIR, f"diagram_universal_{h}.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return out_path

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        fig.patch.set_facecolor('#F8FAFC')
        ax.set_facecolor('#F8FAFC')

        nodes = [
            ("1. Fundamentos", 1.2, 2.2, "#3B82F6"),
            ("2. Aplicación", 3.2, 2.2, "#10B981"),
            ("3. Impacto", 5.2, 2.2, "#8B5CF6")
        ]

        ax.annotate("", xy=(2.3, 2.2), xytext=(2.1, 2.2), arrowprops=dict(arrowstyle="->", lw=3, color="#94A3B8"))
        ax.annotate("", xy=(4.3, 2.2), xytext=(4.1, 2.2), arrowprops=dict(arrowstyle="->", lw=3, color="#94A3B8"))

        for ntitle, nx, ny, ncolor in nodes:
            circle = plt.Circle((nx, ny), 0.7, color=ncolor, ec='#1E293B', lw=1.5, zorder=2)
            ax.add_patch(circle)
            ax.text(nx, ny, ntitle, ha='center', va='center', fontsize=9.5, fontweight='bold', color='#FFFFFF', zorder=3)

        ax.set_xlim(0.2, 6.2)
        ax.set_ylim(0.8, 3.6)
        ax.axis('off')
        ax.text(3.2, 3.3, f'CICLO DE APRENDIZAJE: {topic.upper()[:30]}', ha='center', fontsize=11, fontweight='bold', color='#1E293B')

        plt.tight_layout()
        plt.savefig(out_path, bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        return out_path
