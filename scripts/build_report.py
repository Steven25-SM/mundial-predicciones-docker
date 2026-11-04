"""Genera informe DOCX desde el informe Markdown conservando tablas y diagramas."""
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = ROOT / "docs/INFORME_LAB12.md"
DEST = ROOT / "docs/INFORME_LAB12.docx"

doc = Document()
sec = doc.sections[0]
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2)
sec.left_margin, sec.right_margin = Cm(2.3), Cm(2.2)
styles = doc.styles
normal = styles['Normal']
normal.font.name = 'Aptos'; normal.font.size = Pt(10)
normal.font.color.rgb = RGBColor(45,54,70)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.12
for name, font_size, after in [('Title',29,18),('Heading 1',15.5,9),('Heading 2',12.8,7)]:
    s=styles[name]; s.font.name='Aptos Display'; s.font.size=Pt(font_size)
    s.font.color.rgb=RGBColor(23, 42, 69); s.font.bold=True
    s.paragraph_format.space_before=Pt(13)
    s.paragraph_format.space_after=Pt(after)

for stylename in ['Normal', 'Title', 'Heading 1', 'Heading 2']:
    styles[stylename].paragraph_format.keep_with_next = stylename in ['Title','Heading 1','Heading 2']

header=sec.header.paragraphs[0]
header.text='TECSUP    |    DESARROLLO DE SOLUCIONES EN LA NUBE'
header.style='Caption'
header.runs[0].font.color.rgb=RGBColor(92,106,128)
header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer=sec.footer.paragraphs[0]
footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('MundialLab12     •     Pág. ')
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); footer._p.append(field)

cover=doc.add_paragraph()
cover.paragraph_format.space_before=Pt(60)
run=cover.add_run('LABORATORIO Nº 12')
run.bold=True; run.font.size=Pt(14); run.font.color.rgb=RGBColor(243,117,35)
cover2=doc.add_paragraph()
run=cover2.add_run('Despliegue de\nInstancias Virtualizadas')
run.bold=True; run.font.name='Aptos Display'; run.font.size=Pt(31); run.font.color.rgb=RGBColor(20,41,73)
cover2.paragraph_format.space_after=Pt(30)
cover3=doc.add_paragraph()
r=cover3.add_run('MUNDIAL LAB 12\nSistema de pronósticos, salas y puntuación')
r.font.size=Pt(15);r.font.color.rgb=RGBColor(70,87,112)
cover3.paragraph_format.space_after=Pt(46)
for item in ['Curso: Desarrollo de Soluciones en la Nube','Docente: Jaime Farfán', 'Estudiante: __________________________', 'Ciclo: 2026-2','Modalidad: Local / Docker Desktop']:
    p=doc.add_paragraph()
    r=p.add_run(item); r.font.size=Pt(11)

doc.add_page_break()

def rich(p, line):
    for segment in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', line):
        if not segment:
            continue
        if segment.startswith('**') and segment.endswith('**'):
            r=p.add_run(segment[2:-2]);r.bold=True
        elif segment.startswith('`') and segment.endswith('`'):
            r=p.add_run(segment[1:-1]);r.font.name='Consolas';r.font.size=Pt(8.5)
        else:
            p.add_run(segment)

lines=MARKDOWN.read_text(encoding='utf-8').splitlines()
body_started=False
in_code=False
code_lines=[]
para_lines=[]

def flush_paragraph():
    global para_lines
    if para_lines:
        p=doc.add_paragraph()
        rich(p, ' '.join(x.strip() for x in para_lines))
        para_lines=[]


i=0
while i<len(lines):
    line=lines[i]
    if line.startswith('# Informe técnico'):
        i+=1
        continue
    if line.startswith('```'):
        flush_paragraph()
        if not in_code:
            in_code=True
            code_lines=[]
        else:
            p=doc.add_paragraph(style='Normal')
            p.paragraph_format.left_indent=Cm(.4)
            for k,cl in enumerate(code_lines):
                if k: p.add_run('\n')
                r=p.add_run(cl);r.font.name='Consolas';r.font.size=Pt(8.3);r.font.color.rgb=RGBColor(32,82,98)
            in_code=False
        i+=1;continue
    if in_code:
        code_lines.append(line)
        i+=1; continue
    if not line.strip():
        flush_paragraph();i+=1;continue
    if line.startswith('## '):
        flush_paragraph()
        doc.add_heading(line[3:],level=1)
    elif line.startswith('### '):
        flush_paragraph();doc.add_heading(line[4:],level=2)
    elif line.startswith('![image') or line.startswith('!['):
        flush_paragraph()
        m=re.match(r'!\[[^]]*\]\(([^)]+)\)',line)
        if m:
            img=ROOT/'docs'/m.group(1)
            if img.exists():
                p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.keep_with_next=True
                p.add_run().add_picture(str(img),width=Cm(15.6))
    elif line.startswith('|'):
        flush_paragraph()
        raw=[]
        while i<len(lines) and lines[i].startswith('|'):
            cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?',x) for x in cells):
                raw.append(cells)
            i+=1
        if raw:
            cols=max(map(len,raw))
            t=doc.add_table(rows=0,cols=cols)
            t.style='Light Shading Accent 1'
            t.alignment=WD_TABLE_ALIGNMENT.CENTER
            for ridx,row in enumerate(raw):
                cells=t.add_row().cells
                for j in range(cols):
                    cells[j].text = re.sub(r'\*\*|`','',row[j]) if j<len(row) else ''
                    cells[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    if ridx==0:
                        for r in cells[j].paragraphs[0].runs:r.bold=True
            doc.add_paragraph('')
        continue
    elif re.match(r'^\d+\.\s', line) or line.startswith('- '):
        flush_paragraph()
        p=doc.add_paragraph(style='List Number' if re.match(r'^\d+\.\s',line) else 'List Bullet')
        rich(p,re.sub(r'^\d+\.\s|^-\s','',line))
    elif line.startswith('> '):
        flush_paragraph();p=doc.add_paragraph();p.paragraph_format.left_indent=Cm(.5)
        rich(p,line[2:]); p.runs[0].italic=True
    else:
        para_lines.append(line)
    i+=1
flush_paragraph()
doc.core_properties.title='Informe Laboratorio 12 - MundialLab12'
doc.core_properties.author='Estudiante - Desarrollo de Soluciones en la Nube'
doc.save(DEST)
print(DEST)
