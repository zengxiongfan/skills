# -*- coding: utf-8 -*-
"""docx_core — 字体/段落/标题/表格/图片/步骤/占位框等基础排版能力。"""
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BODY_EAST = '宋体'
HEAD_EAST = '黑体'
ASCII_FONT = 'Times New Roman'
HDR_BG = 'D9E2F3'

_fig_no = {}


def reset_fig_counters():
    _fig_no.clear()


def set_run(run, size=10.5, bold=False, color=None, east=BODY_EAST,
            ascii_f=ASCII_FONT, italic=False):
    run.font.name = ascii_f
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), ascii_f)
    rFonts.set(qn('w:hAnsi'), ascii_f)
    rFonts.set(qn('w:eastAsia'), east)


def para(doc, text='', size=10.5, bold=False, color=None, align=None,
         east=BODY_EAST, space_after=4, space_before=0, indent=None, line=18,
         italic=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    # 固定行距只用于正文字号；大字号必须放大行距，否则字顶会被裁切
    if line and size <= 16:
        pf.line_spacing = Pt(line)
    elif size > 16:
        pf.line_spacing = Pt(size * 1.4)
    if indent is not None:
        pf.first_line_indent = Pt(indent)
    if align:
        p.alignment = align
    if text:
        r = p.add_run(text)
        set_run(r, size=size, bold=bold, color=color, east=east, italic=italic)
    return p


def _heading(doc, text, level, size, before, after):
    p = doc.add_heading(level=level)
    r = p.add_run(text)
    set_run(r, size=size, bold=True, east=HEAD_EAST, color='000000')
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    return p


def h1(doc, text):
    return _heading(doc, text, 1, 16, 18, 10)


def h2(doc, text):
    return _heading(doc, text, 2, 14, 12, 8)


def h3(doc, text):
    return _heading(doc, text, 3, 12, 10, 6)


def h4(doc, text):
    return _heading(doc, text, 4, 11, 8, 4)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)


def _repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    tblHeader = OxmlElement('w:tblHeader')
    tblHeader.set(qn('w:val'), 'true')
    trPr.append(tblHeader)


def table(doc, headers, rows, widths=None, font_size=9, header_bg=HDR_BG,
          repeat_header=True):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ''
        r = hdr[i].paragraphs[0].add_run(h)
        set_run(r, size=font_size, bold=True)
        shade(hdr[i], header_bg)
    if repeat_header:
        _repeat_header(t.rows[0])
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ''
            r = cells[i].paragraphs[0].add_run(str(val))
            set_run(r, size=font_size)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(doc, path, caption, chapter, width=6.3):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Inches(width))
    _fig_no[chapter] = _fig_no.get(chapter, 0) + 1
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_after = Pt(8)
    r = cp.add_run('图%s-%d %s' % (chapter, _fig_no[chapter], caption))
    set_run(r, size=9, color='595959')


def steps(doc, items, start=1):
    n = start
    for it in items:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(4)
        pf.line_spacing = Pt(18)
        pf.left_indent = Pt(21)
        pf.first_line_indent = Pt(-21)
        r = p.add_run('%d、' % n)
        set_run(r, size=10.5)
        parts = it.split('**')
        for i, seg in enumerate(parts):
            if seg:
                rr = p.add_run(seg)
                set_run(rr, size=10.5, bold=(i % 2 == 1))
        n += 1


def bullets(doc, items):
    for it in items:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(3)
        pf.line_spacing = Pt(18)
        pf.left_indent = Pt(21)
        pf.first_line_indent = Pt(-14)
        r = p.add_run('• ')
        set_run(r, size=10.5)
        parts = it.split('**')
        for i, seg in enumerate(parts):
            if seg:
                rr = p.add_run(seg)
                set_run(rr, size=10.5, bold=(i % 2 == 1))


def note(doc, text, color='7F6000'):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(4)
    pf.line_spacing = Pt(17)
    pf.left_indent = Pt(21)
    r = p.add_run('注：' + text)
    set_run(r, size=9.5, color=color, east='楷体')


def placeholder(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(4)
    pf.space_after = Pt(8)
    pf.left_indent = Pt(21)
    pPr = p._element.get_or_add_pPr()
    borders = OxmlElement('w:pBdr')
    for tag in ('top', 'left', 'bottom', 'right'):
        b = OxmlElement('w:' + tag)
        b.set(qn('w:val'), 'dashed')
        b.set(qn('w:sz'), '8')
        b.set(qn('w:space'), '4')
        b.set(qn('w:color'), 'C00000')
        borders.append(b)
    pPr.append(borders)
    r = p.add_run('【截图待补充】' + text)
    set_run(r, size=9.5, color='C00000')


def new_document():
    doc = Document()
    st = doc.styles['Normal']
    st.font.name = ASCII_FONT
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), BODY_EAST)
    return doc


def setup_page(doc, left=2.2, right=2.2, top=2.4, bottom=2.2,
               width=21.0, height=29.7):
    sec = doc.sections[0]
    sec.page_width = Cm(width)
    sec.page_height = Cm(height)
    sec.left_margin = Cm(left)
    sec.right_margin = Cm(right)
    sec.top_margin = Cm(top)
    sec.bottom_margin = Cm(bottom)
    return sec
