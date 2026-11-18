"""
Academic Documentation Generator for Ndungu Electronics IMS
Generates Milestones 1 to 6 and the Master Consolidated System Documentation
for Zetech University, Diploma in Software Engineering.
Author: Augustin Sanga (DSE-01-0145/2025)
"""

import os
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

BASE_DIR = Path(__file__).resolve().parent.parent
STITCH_DIR = BASE_DIR / "prototypes" / "stitch"
SCREENSHOTS_DIR = BASE_DIR / "screenshots" / "audit"

def set_cell_background(cell, fill_hex):
    """Sets XML background color for a table cell."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_base_doc():
    """Creates a new document with standardized 1-inch margins."""
    doc = docx.Document()
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
    return doc

def add_title_cover(doc, milestone_title, milestone_code="MILESTONE 1"):
    """Adds standard Zetech University academic cover page."""
    p_uni = doc.add_paragraph()
    p_uni.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_uni.paragraph_format.space_before = Pt(36)
    p_uni.paragraph_format.space_after = Pt(12)
    r_uni = p_uni.add_run("ZETECH UNIVERSITY\nDEPARTMENT OF COMPUTER SCIENCE & SOFTWARE ENGINEERING")
    r_uni.font.name = "Times New Roman"
    r_uni.font.size = Pt(14)
    r_uni.font.bold = True
    r_uni.font.color.rgb = RGBColor(15, 23, 42)

    p_proj = doc.add_paragraph()
    p_proj.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_proj.paragraph_format.space_before = Pt(24)
    p_proj.paragraph_format.space_after = Pt(18)
    r_proj = p_proj.add_run(
        f"{milestone_code}: {milestone_title.upper()}\n\n"
        "DESIGN AND IMPLEMENTATION OF A COMPUTERIZED INVENTORY MANAGEMENT SYSTEM FOR NDUNGU ELECTRONICS, THIKA"
    )
    r_proj.font.name = "Times New Roman"
    r_proj.font.size = Pt(13)
    r_proj.font.bold = True
    r_proj.font.color.rgb = RGBColor(15, 118, 110)  # Teal

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_before = Pt(36)
    p_meta.paragraph_format.space_after = Pt(24)
    r_meta = p_meta.add_run(
        "Candidate Name: AUGUSTIN SANGA\n"
        "Registration Number: DSE-01-0145/2025\n"
        "Programme: Diploma in Software Engineering\n"
        "Academic Year: 2025/2026\n"
        "Submission Date: November 2026\n"
        "Supervisor: Department of Computer Science & Software Engineering"
    )
    r_meta.font.name = "Times New Roman"
    r_meta.font.size = Pt(11)
    r_meta.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_page_break()

def add_heading_1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.color.rgb = RGBColor(15, 23, 42)
    return p

def add_heading_2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(15, 118, 110)
    return p

def add_heading_3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(11.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(30, 41, 59)
    return p

def add_paragraph(doc, text, space_after=6, line_spacing=1.15):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(30, 41, 59)
    return p

def add_callout(doc, title, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.right_indent = Inches(0.3)
    r1 = p.add_run(f"{title}: ")
    r1.font.name = "Times New Roman"
    r1.font.size = Pt(10.5)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(15, 118, 110)
    r2 = p.add_run(text)
    r2.font.name = "Times New Roman"
    r2.font.size = Pt(10.5)
    r2.font.italic = True
    r2.font.color.rgb = RGBColor(51, 65, 85)
    return p

def add_table_styled(doc, headers, data, col_widths=None):
    """Creates a beautifully styled academic table with teal headers and alternating shading."""
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "0F766E")
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows
    for r_idx, row_data in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = str(val)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=140, right=140)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.name = "Times New Roman"
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(30, 41, 59)

    # Column widths
    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_after = Pt(4)
    return table

def add_figure(doc, img_path, caption, width_in=5.5):
    """Embeds an image centered with academic figure caption."""
    if not os.path.exists(img_path):
        add_callout(doc, "FIGURE NOTICE", f"Image artifact pending at {img_path}")
        return

    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(str(img_path), width=Inches(width_in))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_after = Pt(10)
    run_cap = p_cap.add_run(caption)
    run_cap.font.name = "Times New Roman"
    run_cap.font.size = Pt(10)
    run_cap.font.bold = True
    run_cap.font.color.rgb = RGBColor(71, 85, 105)

print("Helper definitions loaded successfully.")
