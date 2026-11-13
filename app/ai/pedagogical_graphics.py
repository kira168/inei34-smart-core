"""
Módulo de Soporte y Generación Dinámica Universal de Gráficos Pedagógicos y Mapas Conceptuales.
Garantiza figuras ilustrativas y mapas conceptuales de alta resolución para CUALQUIER tema y área del CNEB,
calibrados para Fichas de Aprendizaje del CET N.° 34 Chancay (exactamente 2 páginas en PDF y 6 tablas en DOCX).
"""
import os, sys, unicodedata, re, math
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "img", "pedagogico"))
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")

def get_font(size: int, bold: bool = False):
    """Carga fuentes truetype estándar de Windows o fallback por defecto."""
    names = ["arialbd.ttf" if bold else "arial.ttf", "calibrib.ttf" if bold else "calibri.ttf", "segoeuib.ttf" if bold else "segoeui.ttf"]
    for n in names:
        p = os.path.join("C:/Windows/Fonts", n)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def slugify(value: str) -> str:
    """Convierte texto en un identificador seguro para nombre de archivo."""
    value = unicodedata.normalize('NFKD', str(value or "")).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '_', value)[:45]

def get_theme_colors(area: str) -> Dict[str, Any]:
    """Retorna una paleta de colores armónica e institucional según el área curricular."""
    a = (area or "").lower()
    if any(k in a for k in ["ciencia", "cyt", "biolog", "quimic", "fisic", "químic", "físic"]):
        return {
            "primary": "#0369A1", "secondary": "#059669", "dark": "#0F172A",
            "accent": "#2563EB", "bg_header": "#E0F2FE", "bg_panel_l": "#F0FDF4",
            "bg_panel_r": "#F8FAFC", "border": "#94A3B8", "border_card": "#CBD5E1",
            "tag_txt": "#0284C7", "badge_col": ["#0284C7", "#059669", "#D97706", "#7C3AED"]
        }
    elif any(k in a for k in ["social", "historia", "geograf", "ccss"]):
        return {
            "primary": "#B45309", "secondary": "#B91C1C", "dark": "#0F172A",
            "accent": "#4338CA", "bg_header": "#FEF3C7", "bg_panel_l": "#FFFBEB",
            "bg_panel_r": "#F8FAFC", "border": "#CBD5E1", "border_card": "#E2E8F0",
            "tag_txt": "#B45309", "badge_col": ["#B45309", "#B91C1C", "#4338CA", "#15803D"]
        }
    elif any(k in a for k in ["matem", "fracci", "geomet", "calcul"]):
        return {
            "primary": "#1D4ED8", "secondary": "#7C3AED", "dark": "#0F172A",
            "accent": "#0D9488", "bg_header": "#EFF6FF", "bg_panel_l": "#F5F3FF",
            "bg_panel_r": "#F8FAFC", "border": "#CBD5E1", "border_card": "#E2E8F0",
            "tag_txt": "#1D4ED8", "badge_col": ["#1D4ED8", "#7C3AED", "#0D9488", "#EA580C"]
        }
    elif any(k in a for k in ["comunic", "lengua", "literat"]):
        return {
            "primary": "#6D28D9", "secondary": "#C026D3", "dark": "#0F172A",
            "accent": "#2563EB", "bg_header": "#FAF5FF", "bg_panel_l": "#FDF4FF",
            "bg_panel_r": "#F8FAFC", "border": "#CBD5E1", "border_card": "#E2E8F0",
            "tag_txt": "#6D28D9", "badge_col": ["#6D28D9", "#C026D3", "#2563EB", "#059669"]
        }
    elif any(k in a for k in ["dpcc", "desarrollo personal", "civic", "ética"]):
        return {
            "primary": "#0D9488", "secondary": "#E11D48", "dark": "#0F172A",
            "accent": "#D97706", "bg_header": "#F0FDFA", "bg_panel_l": "#FFF1F2",
            "bg_panel_r": "#F8FAFC", "border": "#CBD5E1", "border_card": "#E2E8F0",
            "tag_txt": "#0D9488", "badge_col": ["#0D9488", "#E11D48", "#D97706", "#2563EB"]
        }
    else: # EPT, Computación, Educación para el Trabajo, etc.
        return {
            "primary": "#1E40AF", "secondary": "#EA580C", "dark": "#0F172A",
            "accent": "#0284C7", "bg_header": "#F1F5F9", "bg_panel_l": "#FFF7ED",
            "bg_panel_r": "#F8FAFC", "border": "#CBD5E1", "border_card": "#E2E8F0",
            "tag_txt": "#1E40AF", "badge_col": ["#1E40AF", "#EA580C", "#0284C7", "#16A34A"]
        }

def draw_base_frame(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Dibuja el marco perimetral institucional, el encabezado y el banner de actividades."""
    # Marco exterior
    draw.rounded_rectangle([4, 4, w-4, h-4], radius=10, outline=colors["border"], width=2)
    # Banner de encabezado
    draw.rounded_rectangle([6, 6, w-6, 36], radius=8, fill=colors["bg_header"])
    
    t_clean = topic.upper()
    if len(t_clean) > 55:
        t_clean = t_clean[:52] + "..."
    draw.text((16, 12), f"FIGURA PEDAGÓGICA: {t_clean}", fill=colors["dark"], font=get_font(13, bold=True))
    
    tag = f"ÁREA: {area.upper()} | CET N.° 34"
    if len(tag) > 35:
        tag = f"{area[:25].upper()} | CET 34"
    draw.text((w - 230, 13), tag, fill=colors["primary"], font=get_font(10, bold=True))

    # Banner inferior de actividades pedagógicas
    draw.rectangle([6, h-32, w-6, h-6], fill="#F1F5F9", outline="#CBD5E1", width=1)
    draw.text((16, h-24), "Actividad pedagógica: Observa los elementos 1 al 4 y el mapa conceptual para fundamentar las respuestas de tu ficha.", fill="#334155", font=get_font(9, bold=False))

def draw_badge(draw, x: int, y: int, num: int, color: str = "#0284C7"):
    """Dibuja un badge circular numerado para rotulación y llamada en actividades."""
    r = 11
    draw.ellipse([x-r, y-r, x+r, y+r], fill=color, outline="#FFFFFF", width=1)
    draw.text((x-4, y-6), str(num), fill="#FFFFFF", font=get_font(10, bold=True))

def draw_concept_map_panel(draw, rx: int, ry: int, rw: int, rh: int, colors: Dict[str, Any], root_text: str, pillar1: Dict, pillar2: Dict, pillar3: Dict, link_text: str = "comprende"):
    """Dibuja un mapa conceptual jerárquico formal con nodo raíz, conectores y 3 pilares temáticos."""
    draw.rounded_rectangle([rx, ry, rx+rw, ry+rh], radius=8, fill=colors["bg_panel_r"], outline=colors["border_card"], width=1)
    draw.text((rx+12, ry+8), "2. MAPA CONCEPTUAL Y RELACIONES JERÁRQUICAS", fill=colors["dark"], font=get_font(10, bold=True))

    # Nodo Central Raíz
    cx = rx + rw // 2
    root_w, root_h = 240, 26
    draw.rounded_rectangle([cx - root_w//2, ry+26, cx + root_w//2, ry+26+root_h], radius=6, fill=colors["primary"])
    f_root = get_font(9, bold=True)
    r_disp = root_text.upper()
    if len(r_disp) > 34: r_disp = r_disp[:32] + ".."
    draw.text((cx - root_w//2 + 10, ry+32), r_disp, fill="#FFFFFF", font=f_root)

    # Conector vertical con frase de enlace
    draw.line([(cx, ry+52), (cx, ry+64)], fill="#64748B", width=2)
    draw.text((cx - 28, ry+53), f"({link_text})", fill="#475569", font=get_font(7, bold=False))
    
    # Columnas para los 3 pilares conceptuales
    col_w = (rw - 24) // 3
    y_p = ry + 72
    p_h = rh - 80

    pillars = [pillar1, pillar2, pillar3]
    for i, p in enumerate(pillars):
        px = rx + 8 + i * (col_w + 4)
        draw.rounded_rectangle([px, y_p, px + col_w, y_p + p_h], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=1)
        p_color = colors["badge_col"][i % len(colors["badge_col"])]
        draw.rounded_rectangle([px, y_p, px + col_w, y_p + 20], radius=5, fill=p_color)
        p_title = p.get("title", f"Pilar {i+1}")
        if len(p_title) > 16: p_title = p_title[:15] + "."
        draw.text((px + 6, y_p + 4), p_title.upper(), fill="#FFFFFF", font=get_font(8, bold=True))

        y_item = y_p + 24
        for item in p.get("items", []):
            if y_item + 14 > y_p + p_h: break
            txt = str(item)
            if len(txt) > 20:
                txt1 = txt[:18]
                txt2 = txt[18:36]
                draw.text((px + 5, y_item), f"• {txt1}", fill="#1E293B", font=get_font(7, bold=False))
                y_item += 11
                if y_item + 12 <= y_p + p_h:
                    draw.text((px + 12, y_item), txt2, fill="#475569", font=get_font(7, bold=False))
                    y_item += 12
            else:
                draw.text((px + 5, y_item), f"• {txt}", fill="#1E293B", font=get_font(7, bold=False))
                y_item += 13

    # Conectores de ramas desde el nodo central a cada pilar
    p1_cx = rx + 8 + col_w // 2
    p3_cx = rx + 8 + 2 * (col_w + 4) + col_w // 2
    draw.line([(p1_cx, ry+64), (p3_cx, ry+64)], fill="#64748B", width=1)
    draw.line([(p1_cx, ry+64), (p1_cx, y_p)], fill="#64748B", width=1)
    draw.line([(cx, ry+64), (cx, y_p)], fill="#64748B", width=1)
    draw.line([(p3_cx, ry+64), (p3_cx, y_p)], fill="#64748B", width=1)

# -------------------------------------------------------------
# DIBUJADORES TEMÁTICOS ESPECÍFICOS (DOMINIOS CLAVE)
# -------------------------------------------------------------
def draw_adn_arn_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema de ácidos nucleicos: doble hélice de ADN vs cadena simple de ARN con mapa conceptual."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. ESQUEMA ESTRUCTURAL: ADN vs ARN", fill=colors["primary"], font=get_font(10, bold=True))

    # ADN Doble Hélice
    draw.text((lx+35, ly+28), "ADN (Doble Hélice)", fill="#1D4ED8", font=get_font(9, bold=True))
    for i in range(7):
        y_pos = ly + 50 + i * 28
        x_left = lx + 50 + int(math.sin(i * 0.9) * 25)
        x_right = lx + 110 - int(math.sin(i * 0.9) * 25)
        draw.line([(x_left, y_pos), (x_right, y_pos)], fill="#3B82F6", width=2)
        cx = (x_left + x_right) // 2
        draw.line([(x_left, y_pos), (cx, y_pos)], fill="#2563EB", width=3)
        draw.line([(cx, y_pos), (x_right, y_pos)], fill="#DC2626" if i%2==0 else "#16A34A", width=3)
        draw.ellipse([x_left-3, y_pos-3, x_left+3, y_pos+3], fill="#0284C7")
        draw.ellipse([x_right-3, y_pos-3, x_right+3, y_pos+3], fill="#0284C7")

    # ARN Cadena Simple
    draw.text((lx+230, ly+28), "ARN (Cadena Simple)", fill="#059669", font=get_font(9, bold=True))
    for i in range(7):
        y_pos = ly + 50 + i * 28
        x_strand = lx + 270 + int(math.sin(i * 0.8) * 15)
        x_base = x_strand + 24
        draw.ellipse([x_strand-3, y_pos-3, x_strand+3, y_pos+3], fill="#059669")
        col_arn = "#EAB308" if i%3==0 else ("#DC2626" if i%3==1 else "#2563EB")
        draw.line([(x_strand, y_pos), (x_base, y_pos)], fill=col_arn, width=3)
        draw.ellipse([x_base-2, y_pos-2, x_base+2, y_pos+2], fill=col_arn)

    # Cuadro comparativo de bases nitrogenadas
    draw.rounded_rectangle([lx+135, ly+70, lx+215, ly+220], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+140, ly+74), "Bases ADN:", fill="#1E293B", font=get_font(7, bold=True))
    draw.text((lx+140, ly+86), "A = T (2 enlaces)\nC ≡ G (3 enlaces)", fill="#475569", font=get_font(7, bold=False))
    draw.text((lx+140, ly+125), "Bases ARN:", fill="#1E293B", font=get_font(7, bold=True))
    draw.text((lx+140, ly+137), "A = U (Uracilo)\nC ≡ G (Guanina)", fill="#475569", font=get_font(7, bold=False))

    # Badges numerados
    draw_badge(draw, lx+35, ly+75, 1, "#0284C7")
    draw_badge(draw, lx+125, ly+140, 2, "#059669")
    draw_badge(draw, lx+175, ly+235, 3, "#D97706")
    draw_badge(draw, lx+340, ly+110, 4, "#7C3AED")

    draw.rounded_rectangle([lx+12, ly+250, lx+lw-12, ly+lh-10], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+18, ly+254), "Guía anatómica: (1) Azúcar pentosa (desoxirribosa/ribosa)  (2) Grupo fosfato (-PO4)\n                (3) Bases nitrogenadas complementarias  (4) Hebra simple de transcripción", fill="#334155", font=get_font(7, bold=False))
    draw.text((lx+18, ly+284), "• ADN: Almacén del código genético nuclear (doble hélice antiparalela).\n• ARN: Transcripción y síntesis proteica en ribosomas (ARNm, ARNt, ARNr).", fill="#0F172A", font=get_font(7, bold=False))

    # Panel Derecho
    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Estructura Química", "items": ["Desoxirribosa / Ribosa", "Grupo fosfato", "Bases púricas A, G", "Bases pirimídicas T, C, U"]}
    p2 = {"title": "Diferencias Clave", "items": ["ADN: Bicatenario", "ARN: Monocatenario", "ADN: Timina", "ARN: Uracilo (sin T)"]}
    p3 = {"title": "Funciones Vitales", "items": ["Replicación celular", "Transcripción ARNm", "Traducción proteica", "Herencia genética"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "ÁCIDOS NUCLEICOS (ADN Y ARN)", p1, p2, p3, "constituidos por")

def draw_fotosintesis_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema de fotosíntesis, cloroplasto, fase luminosa y ciclo de Calvin."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. ESQUEMA DE FOTOSÍNTESIS Y BIOENERGÍA", fill=colors["primary"], font=get_font(10, bold=True))

    # Cloroplasto (Óvalo verde grande)
    draw.ellipse([lx+30, ly+35, lx+380, ly+245], fill="#ECFDF5", outline="#059669", width=3)
    draw.text((lx+135, ly+42), "CLOROPLASTO VEGETAL", fill="#047857", font=get_font(9, bold=True))

    # Tilacoides (Pila de discos / Grana a la izquierda)
    for i in range(4):
        draw.ellipse([lx+60, ly+90+i*16, lx+150, ly+112+i*16], fill="#A7F3D0", outline="#047857", width=2)
    draw.text((lx+70, ly+165), "Fase Luminosa\n(Tilacoides)", fill="#065F46", font=get_font(8, bold=True))

    # Estroma y Ciclo de Calvin a la derecha
    draw.ellipse([lx+220, ly+85, lx+340, ly+185], fill="#FEF3C7", outline="#D97706", width=2)
    draw.text((lx+238, ly+125), "Ciclo de Calvin\n(Fase Oscura)", fill="#92400E", font=get_font(8, bold=True))

    # Flechas de insumos y productos
    draw.text((lx+40, ly+65), "Luz Solar + H2O ->", fill="#D97706", font=get_font(7, bold=True))
    draw.text((lx+60, ly+195), "-> Libera O2", fill="#0284C7", font=get_font(7, bold=True))
    draw.text((lx+235, ly+65), "Entrada CO2 ->", fill="#475569", font=get_font(7, bold=True))
    draw.text((lx+240, ly+195), "-> Glucosa (C6H12O6)", fill="#059669", font=get_font(7, bold=True))

    # Badges
    draw_badge(draw, lx+45, ly+95, 1, "#047857")
    draw_badge(draw, lx+160, ly+120, 2, "#0284C7")
    draw_badge(draw, lx+215, ly+120, 3, "#D97706")
    draw_badge(draw, lx+350, ly+195, 4, "#059669")

    draw.rounded_rectangle([lx+12, ly+250, lx+lw-12, ly+lh-10], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+18, ly+254), "Ecuación global: 6 CO2 + 6 H2O + Energía lumínica -> C6H12O6 (Glucosa) + 6 O2", fill="#0F172A", font=get_font(8, bold=True))
    draw.text((lx+18, ly+274), "• (1) Clorofila y tilacoide: Fotólisis del agua y generación de energía ATP/NADPH.\n• (2 al 4) Ciclo de Calvin y estroma: Fijación enzimática del carbono para nutrición celular.", fill="#334155", font=get_font(7, bold=False))

    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Fase Luminosa", "items": ["Tilacoide / Clorofila", "Absorción de luz", "Fotólisis del agua", "Liberación de O2"]}
    p2 = {"title": "Fase Oscura", "items": ["Estroma celular", "Fijación de CO2", "Ciclo de Calvin", "Síntesis de glucosa"]}
    p3 = {"title": "Trascendencia", "items": ["Nutrición autótrofa", "Oxígeno atmosférico", "Base de redes tróficas", "Captura de carbono"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "FOTOSÍNTESIS Y PRODUCCIÓN DE ENERGÍA", p1, p2, p3, "se realiza mediante")

def draw_fracciones_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema de números racionales y fracciones con representación gráfica y mapa conceptual."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. MODELOS Y REPRESENTACIÓN DE FRACCIONES", fill=colors["primary"], font=get_font(10, bold=True))

    # Círculo 1/2
    draw.ellipse([lx+30, ly+35, lx+110, ly+115], fill="#EFF6FF", outline="#2563EB", width=2)
    draw.pieslice([lx+30, ly+35, lx+110, ly+115], 90, 270, fill="#93C5FD", outline="#1D4ED8", width=2)
    draw.text((lx+55, ly+120), "1/2", fill="#1D4ED8", font=get_font(9, bold=True))

    # Círculo 3/4
    draw.ellipse([lx+150, ly+35, lx+230, ly+115], fill="#EFF6FF", outline="#2563EB", width=2)
    draw.pieslice([lx+150, ly+35, lx+230, ly+115], 0, 270, fill="#6EE7B7", outline="#059669", width=2)
    draw.text((lx+175, ly+120), "3/4", fill="#047857", font=get_font(9, bold=True))

    # Barra rectangular dividida en 5 partes (3/5 sombreadas)
    draw.rectangle([lx+265, ly+50, lx+385, ly+95], fill="#F8FAFC", outline="#475569", width=2)
    for i in range(5):
        bx = lx + 265 + i * 24
        draw.line([(bx, ly+50), (bx, ly+95)], fill="#64748B", width=1)
        if i < 3:
            draw.rectangle([bx, ly+50, bx+24, ly+95], fill="#FED7AA", outline="#EA580C", width=1)
    draw.text((lx+310, ly+105), "3/5", fill="#C2410C", font=get_font(9, bold=True))

    # Recta numérica abajo
    draw.line([(lx+30, ly+190), (lx+380, ly+190)], fill="#0F172A", width=2)
    # Ticks
    for val, tx in [(0, lx+40), ("1/4", lx+120), ("1/2", lx+200), ("3/4", lx+280), (1, lx+360)]:
        draw.line([(tx, ly+182), (tx, ly+198)], fill="#0F172A", width=2)
        draw.text((tx-6, ly+202), str(val), fill="#1E293B", font=get_font(8, bold=True))

    # Badges
    draw_badge(draw, lx+30, ly+35, 1, "#1D4ED8")
    draw_badge(draw, lx+150, ly+35, 2, "#059669")
    draw_badge(draw, lx+265, ly+40, 3, "#EA580C")
    draw_badge(draw, lx+200, ly+175, 4, "#7C3AED")

    draw.rounded_rectangle([lx+12, ly+250, lx+lw-12, ly+lh-10], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+18, ly+254), "Estructura fundamental: Fracción = Numerador (partes tomadas) / Denominador (total)", fill="#0F172A", font=get_font(8, bold=True))
    draw.text((lx+18, ly+274), "• (1 y 2) Fracciones propias: El numerador es menor que el denominador (valor < 1).\n• (3 y 4) Representación lineal: Permite comparar magnitudes, densidades y orden numérico.", fill="#334155", font=get_font(7, bold=False))

    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Términos Clave", "items": ["Numerador (partes)", "Denominador (total)", "Línea de fracción", "Razón y proporción"]}
    p2 = {"title": "Clasificación", "items": ["Propias (a < b)", "Impropias (a > b)", "Números mixtos", "Equivalentes"]}
    p3 = {"title": "Operaciones", "items": ["Suma y resta (mcm)", "Multiplicación directa", "División (inversa)", "Resolución de problemas"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "NÚMEROS RACIONALES Y FRACCIONES", p1, p2, p3, "se organizan en")

# -------------------------------------------------------------
# DIBUJADOR UNIVERSAL SISTÉMICO (PARA CUALQUIER OTRO TEMA)
# -------------------------------------------------------------
def draw_sistemas_cuerpo_humano_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema anatómico funcional de los sistemas del cuerpo humano e integración vital."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. INTEGRACIÓN ANATÓMICA Y FUNCIONAL", fill=colors["primary"], font=get_font(10, bold=True))

    core_cx = lx + lw // 2
    core_cy = ly + 140
    core_w, core_h = 160, 48
    draw.rounded_rectangle([core_cx - core_w//2, core_cy - core_h//2, core_cx + core_w//2, core_cy + core_h//2], radius=10, fill=colors["primary"])
    draw.rounded_rectangle([core_cx - core_w//2 + 3, core_cy - core_h//2 + 3, core_cx + core_w//2 - 3, core_cy + core_h//2 - 3], radius=8, outline="#FFFFFF", width=1)
    draw.text((core_cx - 68, core_cy - 14), "HOMEOSTASIS VITAL", fill="#FFFFFF", font=get_font(9, bold=True))
    draw.text((core_cx - 68, core_cy + 2), "(Equilibrio del Cuerpo)", fill="#E0F2FE", font=get_font(8, bold=False))

    card_w, card_h = 180, 56
    cards = [
        {"x": lx + 10, "y": ly + 28, "badge": 1, "title": "Digestivo y Respiratorio", "sub": "• Nutrientes (estómago/intestino)\n• Oxígeno y CO2 (pulmones)", "col": "#0284C7"},
        {"x": lx + lw - card_w - 10, "y": ly + 28, "badge": 2, "title": "Sistema Circulatorio", "sub": "• Corazón (bomba muscular)\n• Sangre: transporte de O2 y glucosa", "col": "#DC2626"},
        {"x": lx + 10, "y": ly + 195, "badge": 3, "title": "Sistema Excretor / Renal", "sub": "• Riñones (filtrado de sangre)\n• Eliminación de toxinas en orina", "col": "#D97706"},
        {"x": lx + lw - card_w - 10, "y": ly + 195, "badge": 4, "title": "Nervioso y Locomotor", "sub": "• Cerebro y nervios (control vital)\n• Músculos y huesos (movimiento)", "col": "#7C3AED"}
    ]

    for c in cards:
        cx, cy = c["x"], c["y"]
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=1)
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + 18], radius=5, fill="#F8FAFC")
        draw_badge(draw, cx + 12, cy + 9, c["badge"], c["col"])
        draw.text((cx + 28, cy + 4), c["title"].upper(), fill="#0F172A", font=get_font(7, bold=True))
        draw.text((cx + 8, cy + 22), c["sub"], fill="#334155", font=get_font(7, bold=False))

    draw.line([(lx + 10 + card_w, ly + 28 + card_h//2), (core_cx - core_w//2, core_cy - 10)], fill="#94A3B8", width=1)
    draw.line([(lx + lw - card_w - 10, ly + 28 + card_h//2), (core_cx + core_w//2, core_cy - 10)], fill="#94A3B8", width=1)
    draw.line([(core_cx - core_w//2, core_cy + 10), (lx + 10 + card_w, ly + 195 + card_h//2)], fill="#94A3B8", width=1)
    draw.line([(core_cx + core_w//2, core_cy + 10), (lx + lw - card_w - 10, ly + 195 + card_h//2)], fill="#94A3B8", width=1)

    draw.rounded_rectangle([lx+10, ly+265, lx+lw-10, ly+lh-10], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+16, ly+270), "Interdependencia funcional en el ser humano:", fill=colors["primary"], font=get_font(8, bold=True))
    draw.text((lx+16, ly+286), "• El sistema circulatorio conecta la nutrición del digestivo y respiratorio con la limpieza del excretor.\n• El sistema nervioso coordina el ritmo cardíaco, respiratorio y las respuestas del cuerpo.", fill="#334155", font=get_font(7, bold=False))

    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Nutrición Vital", "items": ["Sist. Digestivo (nutrientes)", "Sist. Respiratorio (O2/CO2)", "Sist. Circulatorio (sangre)", "Sist. Excretor (riñones)"]}
    p2 = {"title": "Relación y Control", "items": ["Sistema Nervioso (cerebro)", "Órganos de los sentidos", "Sistema Muscular (fuerza)", "Sistema Óseo (soporte)"]}
    p3 = {"title": "Salud y Cuidado", "items": ["Dieta balanceada", "Consumo de agua limpia", "Actividad física diaria", "Higiene y descanso"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "SISTEMAS DEL CUERPO HUMANO", p1, p2, p3, "se coordinan en")

def draw_ecuaciones_algebra_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema de la balanza algebraica en equilibrio y mapa conceptual de ecuaciones lineales."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. MODELO DE LA BALANZA Y TRANSPOSICIÓN: 2x + 6 = 16", fill=colors["primary"], font=get_font(10, bold=True))

    # Base y soporte de la balanza
    cx = lx + lw // 2
    # Pilar central
    draw.polygon([(cx-8, ly+180), (cx+8, ly+180), (cx+4, ly+80), (cx-4, ly+80)], fill="#475569")
    draw.polygon([(cx-25, ly+180), (cx+25, ly+180), (cx+15, ly+170), (cx-15, ly+170)], fill="#334155")
    # Brazo horizontal en equilibrio
    draw.rounded_rectangle([cx-150, ly+78, cx+150, ly+86], radius=3, fill="#1E293B")
    # Fulcro / pivote
    draw.ellipse([cx-7, ly+75, cx+7, ly+89], fill="#DC2626")

    # Cuerdas y Platillo Izquierdo (Primer Miembro: 2x + 6)
    px_l = cx - 110
    draw.line([(cx-140, ly+86), (px_l-40, ly+140)], fill="#64748B", width=1)
    draw.line([(cx-80, ly+86), (px_l+40, ly+140)], fill="#64748B", width=1)
    draw.rounded_rectangle([px_l-45, ly+140, px_l+45, ly+146], radius=2, fill="#0F172A")
    # Cajas de incógnita x
    draw.rounded_rectangle([px_l-35, ly+112, px_l-10, ly+138], radius=3, fill="#2563EB", outline="#1D4ED8", width=1)
    draw.text((px_l-26, ly+118), "x", fill="#FFFFFF", font=get_font(12, bold=True))
    draw.rounded_rectangle([px_l-5, ly+112, px_l+20, ly+138], radius=3, fill="#2563EB", outline="#1D4ED8", width=1)
    draw.text((px_l+4, ly+118), "x", fill="#FFFFFF", font=get_font(12, bold=True))
    # Pesas de 1 kg
    for pi in range(6):
        ox = px_l + 25 + (pi % 2) * 9
        oy = ly + 116 + (pi // 2) * 7
        draw.ellipse([ox-3, oy-3, ox+3, oy+3], fill="#DC2626")
    draw.text((px_l-30, ly+150), "Primer Miembro: 2x + 6", fill="#1D4ED8", font=get_font(8, bold=True))

    # Cuerdas y Platillo Derecho (Segundo Miembro: 16)
    px_r = cx + 110
    draw.line([(cx+80, ly+86), (px_r-40, ly+140)], fill="#64748B", width=1)
    draw.line([(cx+140, ly+86), (px_r+40, ly+140)], fill="#64748B", width=1)
    draw.rounded_rectangle([px_r-45, ly+140, px_r+45, ly+146], radius=2, fill="#0F172A")
    # Pesas de 16 unidades
    for pi in range(16):
        ox = px_r - 30 + (pi % 6) * 11
        oy = ly + 112 + (pi // 6) * 9
        draw.ellipse([ox-4, oy-4, ox+4, oy+4], fill="#DC2626")
    draw.text((px_r-25, ly+150), "Segundo Miembro: 16", fill="#B91C1C", font=get_font(8, bold=True))

    # Badges rotulados
    draw_badge(draw, px_l-22, ly+98, 1, "#2563EB")
    draw_badge(draw, px_l, ly+170, 2, "#1D4ED8")
    draw_badge(draw, cx, ly+62, 3, "#059669")
    draw_badge(draw, px_r, ly+170, 4, "#DC2626")

    # Cuadro inferior de reglas de transposición
    draw.rounded_rectangle([lx+10, ly+195, lx+lw-10, ly+lh-10], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+16, ly+200), "Reglas de transposición (operaciones inversas):", fill=colors["primary"], font=get_font(8, bold=True))
    draw.text((lx+16, ly+216), "• Despeje paso a paso: 2x + 6 = 16 -> 2x = 16 - 6 -> 2x = 10 -> x = 10 / 2 -> x = 5\n• Comprobación del equilibrio: Reemplazando x = 5 -> 2(5) + 6 = 10 + 6 = 16 (Verificado ✔)\n• Rotulado: (1) Incógnita x  (2) Primer miembro  (3) Signo igual =  (4) Segundo miembro", fill="#334155", font=get_font(7, bold=False))

    # Panel Derecho: Mapa Conceptual
    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Elementos Clave", "items": ["Incógnita (variable x)", "Coeficiente numérico", "Términos independientes", "Miembros (1.° y 2.°)"]}
    p2 = {"title": "Reglas de Despeje", "items": ["Suma pasa a restar", "Resta pasa a sumar", "Multiplicación a división", "Verificación de igualdad"]}
    p3 = {"title": "Modelado Real", "items": ["Lenguaje algebraico", "Planteo de situaciones", "Problemas cotidianos", "Solución justificada"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "ECUACIONES Y ÁLGEBRA LINEAL", p1, p2, p3, "se resuelven mediante")

def draw_geometria_trigonometria_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema de figuras geométricas, teorema de Pitágoras y mapa conceptual de medidas."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. MODELOS GEOMÉTRICOS, TEOREMA DE PITÁGORAS Y ÁREAS", fill=colors["primary"], font=get_font(10, bold=True))

    # Triángulo Rectángulo con Pitágoras
    draw.polygon([(lx+40, ly+150), (lx+160, ly+150), (lx+40, ly+40)], fill="#EFF6FF", outline="#2563EB", width=2)
    # Ángulo recto
    draw.rectangle([lx+40, ly+135, lx+55, ly+150], outline="#1D4ED8", width=1)
    draw.text((lx+90, ly+155), "Cateto a", fill="#1E293B", font=get_font(8, bold=True))
    draw.text((lx+15, ly+90), "Cateto b", fill="#1E293B", font=get_font(8, bold=True))
    draw.text((lx+105, ly+85), "Hipotenusa c", fill="#DC2626", font=get_font(8, bold=True))
    draw.text((lx+45, ly+168), "Pitágoras: a² + b² = c²", fill="#2563EB", font=get_font(8, bold=True))

    # Rectángulo y Área
    draw.rectangle([lx+220, ly+45, lx+370, ly+125], fill="#ECFDF5", outline="#059669", width=2)
    draw.text((lx+275, ly+28), "Base (b)", fill="#065F46", font=get_font(8, bold=True))
    draw.text((lx+375, ly+78), "Altura (h)", fill="#065F46", font=get_font(8, bold=True))
    draw.text((lx+250, ly+78), "Área = b · h\nPerímetro = 2b + 2h", fill="#047857", font=get_font(8, bold=True))

    # Badges
    draw_badge(draw, lx+30, ly+40, 1, "#2563EB")
    draw_badge(draw, lx+160, ly+135, 2, "#DC2626")
    draw_badge(draw, lx+220, ly+45, 3, "#059669")
    draw_badge(draw, lx+370, ly+125, 4, "#EA580C")

    # Resumen inferior
    draw.rounded_rectangle([lx+10, ly+195, lx+lw-10, ly+lh-10], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+16, ly+200), "Fórmulas fundamentales de forma y espacio:", fill=colors["primary"], font=get_font(8, bold=True))
    draw.text((lx+16, ly+216), "• Triángulo: Área = (b · h) / 2  |  Perímetro = Suma de lados\n• Rectángulo: Área = b · h  |  Cuadrado: Área = L²  |  Círculo: Área = π · r²\n• Unidades: Perímetro en unidades lineales (cm, m) y Área en unidades cuadradas (cm², m²).", fill="#334155", font=get_font(7, bold=False))

    # Panel Derecho: Mapa Conceptual
    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Figuras Planas", "items": ["Triángulos y cuadriláteros", "Polígonos regulares", "Círculo y circunferencia", "Perímetro (contorno)"]}
    p2 = {"title": "Relaciones Métricas", "items": ["Teorema de Pitágoras", "Razones trigonométricas", "Semejanza y congruencia", "Ángulos notables"]}
    p3 = {"title": "Sólidos y Medida", "items": ["Prismas y cilindros", "Volumen y capacidad", "Cuerpos de revolución", "Diseño en el entorno"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "GEOMETRÍA Y MEDICIÓN ESPACIAL", p1, p2, p3, "se organizan en")

def draw_estadistica_probabilidad_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """Esquema de tablas de frecuencias, gráfico de barras y medidas de tendencia central."""
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. DISTRIBUCIÓN DE FRECUENCIAS Y MEDIDAS CENTRALES", fill=colors["primary"], font=get_font(10, bold=True))

    # Gráfico de Barras
    draw.line([(lx+35, ly+150), (lx+185, ly+150)], fill="#0F172A", width=2)
    draw.line([(lx+35, ly+150), (lx+35, ly+40)], fill="#0F172A", width=2)
    # Barras
    bars = [("A", 40, "#3B82F6"), ("B", 85, "#10B981"), ("C", 60, "#F59E0B"), ("D", 30, "#8B5CF6")]
    for bi, (lab, bh, bcol) in enumerate(bars):
        bx = lx + 50 + bi * 32
        by = ly + 150 - bh
        draw.rectangle([bx, by, bx+22, ly+150], fill=bcol, outline="#1E293B", width=1)
        draw.text((bx+6, ly+154), lab, fill="#1E293B", font=get_font(8, bold=True))

    # Tabla resumen al costado
    draw.rounded_rectangle([lx+205, ly+42, lx+395, ly+160], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+215, ly+48), "Medidas de Tendencia Central:", fill="#0F172A", font=get_font(8, bold=True))
    draw.text((lx+215, ly+66), "• Media (x̄): Promedio = Σx / N\n• Mediana (Me): Dato central ordenado\n• Moda (Mo): Dato con mayor frecuencia\n• Probabilidad Laplace:\n  P(A) = Casos favorables / Totales", fill="#334155", font=get_font(7, bold=False))

    # Badges
    draw_badge(draw, lx+30, ly+40, 1, "#3B82F6")
    draw_badge(draw, lx+110, ly+60, 2, "#10B981")
    draw_badge(draw, lx+205, ly+45, 3, "#F59E0B")
    draw_badge(draw, lx+350, ly+135, 4, "#8B5CF6")

    # Resumen inferior
    draw.rounded_rectangle([lx+10, ly+195, lx+lw-10, ly+lh-10], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+16, ly+200), "Gestión e interpretación de datos e incertidumbre:", fill=colors["primary"], font=get_font(8, bold=True))
    draw.text((lx+16, ly+216), "• Tablas: Registran frecuencias absolutas (fi) y relativas porcentuales (hi % = fi / N · 100).\n• Gráficos: Permiten visualizar la dispersión y concentración de datos de manera intuitiva.\n• Probabilidad: Modela el azar desde 0 (suceso imposible) hasta 1 o 100% (suceso seguro).", fill="#334155", font=get_font(7, bold=False))

    # Panel Derecho: Mapa Conceptual
    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Organización", "items": ["Variables cualitativas", "Variables cuantitativas", "Tablas de frecuencias", "Gráficos estadísticos"]}
    p2 = {"title": "Medidas Centrales", "items": ["Media aritmética (x̄)", "Mediana posicional (Me)", "Moda dominante (Mo)", "Rango y dispersión"]}
    p3 = {"title": "Probabilidad", "items": ["Espacio muestral", "Regla de Laplace", "Sucesos seguros/imposibles", "Toma de decisiones"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, "ESTADÍSTICA Y PROBABILIDAD", p1, p2, p3, "se organizan en")

def draw_universal_figure(draw, w: int, h: int, colors: Dict[str, Any], topic: str, area: str):
    """
    Generador sistémico universal para cualquier tema que no disponga de plantilla temática fija.
    Dibuja un diagrama analítico de 4 componentes con llamadas numeradas (1 al 4) y un mapa conceptual formal.
    """
    draw_base_frame(draw, w, h, colors, topic, area)
    lx, ly, lw, lh = 12, 42, 410, 340
    draw.rounded_rectangle([lx, ly, lx+lw, ly+lh], radius=8, fill=colors["bg_panel_l"], outline=colors["border_card"], width=1)
    draw.text((lx+12, ly+8), "1. ESQUEMA CONCEPTUAL Y MODELO SISTÉMICO", fill=colors["primary"], font=get_font(10, bold=True))

    # Núcleo Central
    core_cx = lx + lw // 2
    core_cy = ly + 140
    core_w, core_h = 160, 48
    draw.rounded_rectangle([core_cx - core_w//2, core_cy - core_h//2, core_cx + core_w//2, core_cy + core_h//2], radius=10, fill=colors["primary"])
    draw.rounded_rectangle([core_cx - core_w//2 + 3, core_cy - core_h//2 + 3, core_cx + core_w//2 - 3, core_cy + core_h//2 - 3], radius=8, outline="#FFFFFF", width=1)
    
    t_core = topic.upper()
    if len(t_core) > 22:
        words = t_core.split()
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        draw.text((core_cx - 70, core_cy - 16), line1[:22], fill="#FFFFFF", font=get_font(8, bold=True))
        draw.text((core_cx - 70, core_cy + 2), line2[:22], fill="#FFFFFF", font=get_font(8, bold=True))
    else:
        draw.text((core_cx - 68, core_cy - 7), t_core, fill="#FFFFFF", font=get_font(9, bold=True))

    # 4 Tarjetas de Componentes Esenciales Alrededor del Núcleo
    card_w, card_h = 175, 54
    cards = [
        {"x": lx + 12, "y": ly + 32, "badge": 1, "title": "Definición y Base", "sub": "Conceptos rectores y principio esencial.", "col": colors["badge_col"][0]},
        {"x": lx + lw - card_w - 12, "y": ly + 32, "badge": 2, "title": "Estructura Clave", "sub": "Elementos constitutivos y clasificación.", "col": colors["badge_col"][1]},
        {"x": lx + 12, "y": ly + 195, "badge": 3, "title": "Dinámica y Proceso", "sub": "Interacción funcional y metodologías.", "col": colors["badge_col"][2]},
        {"x": lx + lw - card_w - 12, "y": ly + 195, "badge": 4, "title": "Aplicación Real", "sub": "Impacto, utilidad práctica y retos.", "col": colors["badge_col"][3]}
    ]

    for c in cards:
        cx, cy = c["x"], c["y"]
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=1)
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + 18], radius=5, fill="#F8FAFC")
        draw_badge(draw, cx + 12, cy + 9, c["badge"], c["col"])
        draw.text((cx + 28, cy + 4), c["title"].upper(), fill="#0F172A", font=get_font(8, bold=True))
        draw.text((cx + 8, cy + 24), c["sub"], fill="#475569", font=get_font(7, bold=False))

    # Líneas conectoras direccionales entre el Núcleo y las Tarjetas
    draw.line([(lx + 12 + card_w, ly + 32 + card_h//2), (core_cx - core_w//2, core_cy - 10)], fill="#94A3B8", width=1)
    draw.line([(lx + lw - card_w - 12, ly + 32 + card_h//2), (core_cx + core_w//2, core_cy - 10)], fill="#94A3B8", width=1)
    draw.line([(core_cx - core_w//2, core_cy + 10), (lx + 12 + card_w, ly + 195 + card_h//2)], fill="#94A3B8", width=1)
    draw.line([(core_cx + core_w//2, core_cy + 10), (lx + lw - card_w - 12, ly + 195 + card_h//2)], fill="#94A3B8", width=1)

    # Cuadro inferior de síntesis sistémica
    draw.rounded_rectangle([lx+10, ly+265, lx+lw-10, ly+lh-10], radius=5, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.text((lx+16, ly+270), f"Articulación formativa de {topic[:35]}:", fill=colors["primary"], font=get_font(8, bold=True))
    draw.text((lx+16, ly+286), "• Los componentes 1 y 2 configuran el marco conceptual y los elementos estructurales.\n• Las dimensiones 3 y 4 orientan la aplicación práctica, resolución y pensamiento crítico.", fill="#334155", font=get_font(7, bold=False))

    # Panel Derecho: Mapa Conceptual
    rx, ry, rw, rh = 430, 42, 358, 340
    p1 = {"title": "Fundamentos", "items": ["Concepto rector", "Principios clave", "Premisas teóricas", "Contexto de aplicación"]}
    p2 = {"title": "Componentes", "items": ["Estructura interna", "Clasificación básica", "Variables esenciales", "Interdependencia"]}
    p3 = {"title": "Aplicaciones", "items": ["Resolución de retos", "Procedimientos", "Impacto formativo", "Solución en el entorno"]}
    draw_concept_map_panel(draw, rx, ry, rw, rh, colors, topic, p1, p2, p3, "se estructura en")

# -------------------------------------------------------------
# FUNCIÓN DE ENTRADA Y RESOLUCIÓN PÚBLICA
# -------------------------------------------------------------
def generate_universal_pedagogical_graphic(area: str, topic: str) -> Dict[str, Any]:
    """Genera dinámicamente la figura pedagógica con mapa conceptual si no existe en caché."""
    os.makedirs(GENERATED_DIR, exist_ok=True)
    slug_t = slugify(topic)
    slug_a = slugify(area)
    cache_path = os.path.join(GENERATED_DIR, f"{slug_t}_{slug_a}.png")

    if not os.path.exists(cache_path) or os.path.getsize(cache_path) < 1000:
        w, h = 800, 420
        img = Image.new('RGB', (w, h), color='#FFFFFF')
        draw = ImageDraw.Draw(img)
        colors = get_theme_colors(area)
        
        t_l = (topic or "").lower()
        if any(k in t_l for k in ["cuerpo humano", "sistema del cuerpo", "sistemas del cuerpo", "organos del cuerpo", "digestivo", "respiratorio", "circulatorio", "excretor", "anatomia", "anatomía"]):
            draw_sistemas_cuerpo_humano_figure(draw, w, h, colors, topic, area)
        elif any(k in t_l for k in ["adn", "arn", "genétic", "nucleic", "genoma"]):
            draw_adn_arn_figure(draw, w, h, colors, topic, area)
        elif any(k in t_l for k in ["fotosíntesis", "fotosintesis", "cloroplasto", "calvin"]):
            draw_fotosintesis_figure(draw, w, h, colors, topic, area)
        elif any(k in t_l for k in ["ecuaci", "inecuaci", "algebr", "álgebr", "funci", "polinom", "sucesio", "progresi", "lineal", "cuadrátic", "sistema"]):
            draw_ecuaciones_algebra_figure(draw, w, h, colors, topic, area)
        elif any(k in t_l for k in ["geometr", "triáng", "triang", "polígon", "pitágoras", "pitagoras", "trigono", "ángulo", "angulo", "área", "area", "perímet", "volumen"]):
            draw_geometria_trigonometria_figure(draw, w, h, colors, topic, area)
        elif any(k in t_l for k in ["estadíst", "estadist", "probabil", "gráfico", "grafico", "frecuencia", "media", "mediana", "moda", "azar"]):
            draw_estadistica_probabilidad_figure(draw, w, h, colors, topic, area)
        elif any(k in t_l for k in ["fracci", "racional", "numerador", "denominador", "porcent", "proporc"]):
            draw_fracciones_figure(draw, w, h, colors, topic, area)
        else:
            draw_universal_figure(draw, w, h, colors, topic, area)

        img.save(cache_path, format="PNG", optimize=True)

    return {
        "path": cache_path,
        "title": f"Figura 1: Esquema ilustrativo y mapa conceptual de {topic}",
        "caption": "Observa con atención el esquema estructural y las relaciones jerárquicas del mapa conceptual para desarrollar las actividades.",
        "width_mm": 135,
        "height_mm": 52
    }

def resolve_pedagogical_graphic(area: str, topic: str) -> Dict[str, Any]:
    """
    Retorna la ruta absoluta y metadatos de la figura pedagógica institucional correspondiente al tema.
    Garantiza que NUNCA sea None: si no hay un asset maestro pre-grabado, lo genera dinámicamente al instante.
    """
    area_l = (area or "").lower()
    topic_l = (topic or "").lower()

    # 1. Chequear activos pre-grabados específicos si existen
    if any(k in area_l for k in ["ciencia", "cyt", "biolog", "químic", "físic"]):
        if any(k in topic_l for k in ["célula", "celula", "organelo", "citoplasma", "núcleo", "nucleo", "vegetal", "animal"]):
            p = os.path.join(STATIC_DIR, "ciencia_y_tecnologia", "celula_educativa.png")
            if os.path.exists(p):
                return {
                    "path": p,
                    "title": "Figura 1: Esquema estructural y mapa conceptual de la célula (Animal y Vegetal)",
                    "caption": "Observa la figura con atención y rotula las partes señaladas en los ejercicios de tu ficha.",
                    "width_mm": 135,
                    "height_mm": 52
                }
        if any(k in topic_l for k in ["ecosistema", "trófica", "trofica", "energía", "alimento", "cadena", "red"]):
            p = os.path.join(STATIC_DIR, "ciencia_y_tecnologia", "ecosistema_esquema.png")
            if os.path.exists(p):
                return {
                    "path": p,
                    "title": "Figura 1: Esquema de flujo de energía y niveles tróficos en el ecosistema",
                    "caption": "Analiza las interacciones ecológicas entre productores, consumidores y descomponedores.",
                    "width_mm": 135,
                    "height_mm": 52
                }

    if any(k in area_l for k in ["social", "historia", "geograf", "ccss"]):
        if any(k in topic_l for k in ["tahuantinsuyo", "inca", "suyo", "cusco", "pachacutec", "quechua"]):
            p = os.path.join(STATIC_DIR, "ciencias_sociales", "tahuantinsuyo_mapa.png")
            if os.path.exists(p):
                return {
                    "path": p,
                    "title": "Figura 1: Mapa territorial y mapa conceptual del Tahuantinsuyo (Organización económica y social)",
                    "caption": "Ubica la capital sagrada del Cusco y las cuatro grandes divisiones territoriales.",
                    "width_mm": 135,
                    "height_mm": 52
                }
        if any(k in topic_l for k in ["tiempo", "cronolog", "preinca", "cultura", "chavin", "paracas", "moche", "wari", "chimu", "etapas"]):
            p = os.path.join(STATIC_DIR, "ciencias_sociales", "linea_tiempo_peru.png")
            if os.path.exists(p):
                return {
                    "path": p,
                    "title": "Figura 1: Línea de tiempo cronológica del proceso histórico andino",
                    "caption": "Identifica los horizontes e intermedios culturales del Perú prehispánico y su legado.",
                    "width_mm": 135,
                    "height_mm": 52
                }

    # 2. Generación dinámica universal para CUALQUIER otro tema o área
    return generate_universal_pedagogical_graphic(area, topic)
