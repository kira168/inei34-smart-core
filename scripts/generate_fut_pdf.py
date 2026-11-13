"""
Generator script for the official FUT (Formulario Único de Trámite) PDF of I.E. INEI Nº 34 Chancay
"""
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
)
from reportlab.pdfgen import canvas

def generate_fut_pdf(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 595.27 x 841.89 points (A4)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=28
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#C8102E")
    dark_text = colors.HexColor("#1A1A1A")
    muted_text = colors.HexColor("#475569")
    border_color = colors.HexColor("#94A3B8")
    bg_light = colors.HexColor("#F8FAFC")
    bg_header = colors.HexColor("#FFF1F2")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        alignment=1, # Center
        textColor=primary_color
    )
    
    header_title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=dark_text
    )
    
    header_sub_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9.5,
        alignment=1,
        textColor=muted_text
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    
    field_label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=dark_text
    )
    
    field_value_style = ParagraphStyle(
        'FieldValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=muted_text
    )
    
    story = []
    
    # 1. HEADER TABLE (Logo + Institutional Text + Expediente Box)
    logo_path = "public/imagen/insignia.png"
    if not os.path.exists(logo_path):
        logo_path = "app/static/imagen/insignia.png"
    
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=48, height=52)
    else:
        logo_img = Paragraph("<b>INEI 34</b>", field_label_style)
        
    inst_info = [
        Paragraph("<b>REPÚBLICA DEL PERÚ — MINISTERIO DE EDUCACIÓN</b>", header_sub_style),
        Paragraph("DIRECCIÓN REGIONAL DE EDUCACIÓN DE LIMA PROVINCIAS<br/><b>UGEL Nº 10 — HUARAL</b>", header_sub_style),
        Spacer(1, 2),
        Paragraph("<b>I.E. PÚBLICA INEI Nº 34 — CHANCAY</b>", header_title_style),
        Paragraph("<i>Formación Técnica Científica y Humanista • C.M. 0341750</i>", header_sub_style),
    ]
    
    expediente_box = [
        Paragraph("<b>MESA DE PARTES VIRTUAL</b>", ParagraphStyle('ExpHead', fontName='Helvetica-Bold', fontSize=6.5, leading=8, alignment=1, textColor=primary_color)),
        Paragraph("<b>F.U.T. N° 2026 - ________</b>", ParagraphStyle('ExpNum', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=1, textColor=dark_text)),
        Spacer(1, 2),
        Paragraph("Reg. Entrada: ____________<br/>Fecha: ___/___/2026<br/>Folios: [ ______ ]", ParagraphStyle('ExpMeta', fontName='Helvetica', fontSize=6.5, leading=8, alignment=0, textColor=muted_text))
    ]
    
    header_data = [
        [logo_img, inst_info, expediente_box]
    ]
    
    header_table = Table(header_data, colWidths=[55, 330, 138])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('BOX', (2,0), (2,0), 1, primary_color),
        ('BACKGROUND', (2,0), (2,0), bg_header),
        ('TOPPADDING', (2,0), (2,0), 4),
        ('BOTTOMPADDING', (2,0), (2,0), 4),
        ('LEFTPADDING', (2,0), (2,0), 6),
        ('RIGHTPADDING', (2,0), (2,0), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    
    # 2. DOCUMENT TITLE
    doc_banner = Table([
        [Paragraph("FORMULARIO ÚNICO DE TRÁMITE (F.U.T.) — AÑO LECTIVO 2026", title_style)]
    ], colWidths=[523])
    doc_banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_header),
        ('BOX', (0,0), (-1,-1), 1, primary_color),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(doc_banner)
    story.append(Spacer(1, 5))
    
    # HELPER FOR SECTION BANNERS
    def make_section_banner(title: str):
        t = Table([[Paragraph(title, section_title_style)]], colWidths=[523])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), primary_color),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
        ]))
        return t

    # 3. SECCIÓN I: SUMILLA / OBJETO DE LA SOLICITUD
    story.append(make_section_banner("I. TRÁMITE QUE SOLICITA (Marque con una 'X')"))
    
    tramites_data = [
        [
            Paragraph("[ &nbsp; ] Certificado de Estudios", field_label_style),
            Paragraph("[ &nbsp; ] Constancia de Matrícula", field_label_style),
            Paragraph("[ &nbsp; ] Traslado de Matrícula (Ingreso/Salida)", field_label_style)
        ],
        [
            Paragraph("[ &nbsp; ] Certificado Modular Técnico CNOF", field_label_style),
            Paragraph("[ &nbsp; ] Rectificación de Nombres/DNI", field_label_style),
            Paragraph("[ &nbsp; ] Exoneración de Área (Religión/Ed. Física)", field_label_style)
        ],
        [
            Paragraph("[ &nbsp; ] Constancia de No Adeudo / Buena Conducta", field_label_style),
            Paragraph("[ &nbsp; ] Solicitud General / Otro: __________________________________________________", field_label_style),
            Paragraph("", field_label_style)
        ]
    ]
    tramites_table = Table(tramites_data, colWidths=[174, 174, 175])
    tramites_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
    ]))
    story.append(tramites_table)
    story.append(Spacer(1, 4))
    
    # 4. SECCIÓN II: DATOS DEL SOLICITANTE / APODERADO
    story.append(make_section_banner("II. DATOS DEL SOLICITANTE (Padre, Madre, Apoderado o Titular)"))
    
    solic_data = [
        [
            Paragraph("<b>Apellidos y Nombres:</b>", field_label_style),
            Paragraph("____________________________________________________________________________", field_value_style),
            Paragraph("<b>DNI / C.E.:</b>", field_label_style),
            Paragraph("___________________", field_value_style)
        ],
        [
            Paragraph("<b>Dirección / Domicilio:</b>", field_label_style),
            Paragraph("________________________________________________________", field_value_style),
            Paragraph("<b>Distrito / Centro Pob.:</b>", field_label_style),
            Paragraph("Chancay / _________", field_value_style)
        ],
        [
            Paragraph("<b>Teléfono / WhatsApp:</b>", field_label_style),
            Paragraph("________________________", field_value_style),
            Paragraph("<b>Correo Electrónico:</b>", field_label_style),
            Paragraph("___________________________________", field_value_style)
        ],
        [
            Paragraph("<b>Condición:</b>", field_label_style),
            Paragraph("[ &nbsp; ] Padre/Madre &nbsp;&nbsp;&nbsp; [ &nbsp; ] Apoderado Legal &nbsp;&nbsp;&nbsp; [ &nbsp; ] Exalumno &nbsp;&nbsp;&nbsp; [ &nbsp; ] Estudiante", field_label_style),
            Paragraph("", field_label_style),
            Paragraph("", field_label_style)
        ]
    ]
    solic_table = Table(solic_data, colWidths=[90, 220, 85, 128])
    solic_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('SPAN', (1,3), (3,3)),
    ]))
    story.append(solic_table)
    story.append(Spacer(1, 4))
    
    # 5. SECCIÓN III: DATOS DEL ESTUDIANTE
    story.append(make_section_banner("III. DATOS DEL ESTUDIANTE (Llenar si el trámite concierne a un alumno matriculado)"))
    
    estud_data = [
        [
            Paragraph("<b>Apellidos y Nombres:</b>", field_label_style),
            Paragraph("____________________________________________________________________________", field_value_style),
            Paragraph("<b>DNI Estudiante:</b>", field_label_style),
            Paragraph("___________________", field_value_style)
        ],
        [
            Paragraph("<b>Grado y Sección 2026:</b>", field_label_style),
            Paragraph("[ 1° ] [ 2° ] [ 3° ] [ 4° ] [ 5° ] &nbsp;&nbsp;&nbsp; Sec: [ &nbsp; &nbsp; &nbsp; ]", field_label_style),
            Paragraph("<b>Turno:</b>", field_label_style),
            Paragraph("[ &nbsp; ] Mañana &nbsp;&nbsp; [ &nbsp; ] Tarde", field_label_style)
        ],
        [
            Paragraph("<b>Especialidad Técnica (EPT):</b>", field_label_style),
            Paragraph("[ &nbsp; ] Automotores &nbsp; [ &nbsp; ] Computación &nbsp; [ &nbsp; ] Contabilidad &nbsp; [ &nbsp; ] Electricidad<br/>[ &nbsp; ] Ebanistería &nbsp;&nbsp;&nbsp;&nbsp; [ &nbsp; ] Mec. Producción &nbsp; [ &nbsp; ] Estética Personal &nbsp; [ &nbsp; ] Ind. Vestido", field_label_style),
            Paragraph("", field_label_style),
            Paragraph("", field_label_style)
        ]
    ]
    estud_table = Table(estud_data, colWidths=[105, 205, 85, 128])
    estud_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('SPAN', (1,2), (3,2)),
    ]))
    story.append(estud_table)
    story.append(Spacer(1, 4))
    
    # 6. SECCIÓN IV: FUNDAMENTACIÓN DE LA SOLICITUD
    story.append(make_section_banner("IV. FUNDAMENTACIÓN DE LA SOLICITUD (Exponer de forma clara el motivo del trámite)"))
    
    fund_lines = Paragraph(
        "Que, recurro a su despacho directivo a fin de exponer lo siguiente:<br/>"
        "____________________________________________________________________________________________________________<br/>"
        "____________________________________________________________________________________________________________<br/>"
        "____________________________________________________________________________________________________________<br/>"
        "____________________________________________________________________________________________________________<br/>"
        "Por lo expuesto: Pido a Ud. acceder a mi solicitud por ser de justicia.",
        ParagraphStyle('FundStyle', fontName='Helvetica', fontSize=7, leading=11, textColor=dark_text)
    )
    fund_table = Table([[fund_lines]], colWidths=[523])
    fund_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
    ]))
    story.append(fund_table)
    story.append(Spacer(1, 4))
    
    # 7. SECCIÓN V: DOCUMENTOS ADJUNTOS
    story.append(make_section_banner("V. DOCUMENTOS ADJUNTOS (Marque los requisitos que adjunta al expediente)"))
    adjuntos_data = [
        [
            Paragraph("[ &nbsp; ] Copia Simple de DNI del Solicitante", field_label_style),
            Paragraph("[ &nbsp; ] Copia Simple de DNI del Estudiante", field_label_style),
            Paragraph("[ &nbsp; ] Ficha Única de Matrícula (SIAGIE)", field_label_style)
        ],
        [
            Paragraph("[ &nbsp; ] Libreta / Boleta Informativa de Notas", field_label_style),
            Paragraph("[ &nbsp; ] Constancia de No Adeudo Institucional", field_label_style),
            Paragraph("[ &nbsp; ] Otro: ___________________________", field_label_style)
        ]
    ]
    adj_table = Table(adjuntos_data, colWidths=[174, 174, 175])
    adj_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(adj_table)
    story.append(Spacer(1, 5))
    
    # 8. DECLARACIÓN JURADA, FIRMAS Y RECEPCIÓN
    declaracion = Paragraph(
        "<b>DECLARACIÓN JURADA:</b> Declaro bajo juramento que toda la información consignada en el presente F.U.T. es verídica y concuerda con la documentación oficial que obra en mi poder, sujetándome a las responsabilidades de ley correspondientes (Art. 51° TUO de la Ley N° 27444).",
        ParagraphStyle('DecStyle', fontName='Helvetica', fontSize=6.2, leading=8.5, textColor=muted_text, alignment=0)
    )
    story.append(declaracion)
    story.append(Spacer(1, 5))
    
    lugar_fecha = Paragraph(
        "Chancay, ________ de ________________________ del 2026.",
        ParagraphStyle('LugarStyle', fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=dark_text, alignment=0)
    )
    story.append(lugar_fecha)
    story.append(Spacer(1, 6))
    
    # Signature Box + Huella Digital + Sello Mesa de Partes
    firma_cell = [
        Spacer(1, 34),
        Paragraph("________________________________________", ParagraphStyle('Line', alignment=1, fontSize=8, leading=9)),
        Paragraph("<b>FIRMA DEL SOLICITANTE</b>", ParagraphStyle('SignLbl', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, alignment=1, textColor=dark_text)),
        Paragraph("DNI N°: ____________________________", ParagraphStyle('DniLbl', fontName='Helvetica', fontSize=7, leading=9, alignment=1, textColor=muted_text)),
    ]
    
    huella_cell = [
        Spacer(1, 2),
        Paragraph("<b>HUELLA DIGITAL</b><br/>(Índice Derecho)", ParagraphStyle('HuellaLbl', fontName='Helvetica', fontSize=6.5, leading=8, alignment=1, textColor=muted_text)),
        Spacer(1, 22),
    ]
    
    sello_cell = [
        Paragraph("<b>RECEPCIÓN MESA DE PARTES</b><br/>I.E. Pública INEI Nº 34 Chancay", ParagraphStyle('SelloHead', fontName='Helvetica-Bold', fontSize=6.5, leading=8, alignment=1, textColor=primary_color)),
        Spacer(1, 10),
        Paragraph("FIRMA Y SELLO DE RECEPCIÓN<br/>Fecha: ___/___/2026 &nbsp; Hora: ___:___", ParagraphStyle('SelloFoot', fontName='Helvetica', fontSize=6, leading=7.5, alignment=1, textColor=muted_text))
    ]
    
    firmas_data = [
        [firma_cell, huella_cell, sello_cell]
    ]
    firmas_table = Table(firmas_data, colWidths=[240, 110, 173])
    firmas_table.setStyle(TableStyle([
        ('BOX', (0,0), (0,0), 0.5, border_color),
        ('BOX', (1,0), (1,0), 0.5, border_color),
        ('BOX', (2,0), (2,0), 1, primary_color),
        ('BACKGROUND', (2,0), (2,0), bg_header),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(firmas_table)
    
    # Footnote
    story.append(Spacer(1, 4))
    nota_foot = Paragraph(
        "<b>Nota:</b> La entrega de este documento es gratuita. La recepción virtual se efectúa a través de <b>informes@inei34chancay.edu.pe</b> o en ventanilla en Av. Mariscal Cáceres 162, Chancay.",
        ParagraphStyle('FootNote', fontName='Helvetica', fontSize=5.8, leading=7.5, textColor=muted_text, alignment=1)
    )
    story.append(nota_foot)
    
    doc.build(story)
    print(f"PDF generated successfully at {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == '__main__':
    generate_fut_pdf("public/docs/FUT_OFICIAL_INEI34_CHANCAY_2026.pdf")
    generate_fut_pdf("app/static/docs/FUT_OFICIAL_INEI34_CHANCAY_2026.pdf")
