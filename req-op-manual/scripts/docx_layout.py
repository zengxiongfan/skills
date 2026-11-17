# -*- coding: utf-8 -*-
"""docx_layout — 封面、文档信息、修订记录、目录、页眉页脚（简约/企业两套）。"""
import os

from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from docx_core import para, table, set_run, BODY_EAST, HEAD_EAST


# ---------------------------------------------------------------- 域
def _fld(kind):
    e = OxmlElement('w:fldChar')
    e.set(qn('w:fldCharType'), kind)
    return e


def _instr(text):
    e = OxmlElement('w:instrText')
    e.set(qn('xml:space'), 'preserve')
    e.text = text
    return e


def _wt(text):
    e = OxmlElement('w:t')
    e.text = text
    return e


def page_field(paragraph, size=10.5):
    r = paragraph.add_run()
    for e in (_fld('begin'), _instr('PAGE'), _fld('separate'), _wt('1'), _fld('end')):
        r._r.append(e)
    set_run(r, size=size)


def toc_field(doc, levels='1-2'):
    p = doc.add_paragraph()
    r = p.add_run()
    for e in (_fld('begin'), _instr('TOC \\o "%s" \\h \\z \\u' % levels),
              _fld('separate'), _wt('（目录将在 Word 中自动更新，如未更新请右键“更新域”）'),
              _fld('end')):
        r._r.append(e)
    return p


# ---------------------------------------------------------------- 简约样式
def header_text(doc, text):
    p = doc.sections[0].header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(text)
    set_run(r, size=8, color='808080')


def footer_page(doc):
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p.add_run('第 ')
    set_run(r1, size=9)
    page_field(p, size=9)
    r2 = p.add_run(' 页')
    set_run(r2, size=9)


def cover_simple(doc, lines, version, blanks_before=5, blanks_before_version=9):
    """lines: [(text, size, bold), ...]，按顺序居中输出。"""
    for _ in range(blanks_before):
        para(doc, '')
    for text, size, bold in lines:
        para(doc, text, size=size, bold=bold, align=WD_ALIGN_PARAGRAPH.CENTER,
             east=HEAD_EAST if bold else BODY_EAST, space_after=8)
    for _ in range(blanks_before_version):
        para(doc, '')
    para(doc, '版本：%s' % version, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def info_block(doc, rows, title='文档信息'):
    para(doc, title, size=16, bold=True, east=HEAD_EAST, space_after=10)
    table(doc, ['项目', '内容'], rows, widths=[3.2, 13.0], font_size=9.5)


def revision_simple(doc, rows, title='修订记录'):
    para(doc, title, size=14, bold=True, east=HEAD_EAST, space_after=8)
    table(doc, ['版本号', '修订类型', '修订日期', '修订内容', '作者'], rows,
          widths=[2.2, 2.2, 3.0, 6.6, 2.2], font_size=9.5)


def toc_static(doc, entries, title='目  录'):
    para(doc, title, size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         east=HEAD_EAST, space_after=12)
    for no, text in entries:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = Pt(17)
        if '.' in str(no):
            p.paragraph_format.left_indent = Pt(24)
        r = p.add_run('%s  %s' % (no, text))
        set_run(r, size=10.5, bold=('.' not in str(no)))


def toc_page(doc, levels='1-2', title='目    录'):
    para(doc, '', space_after=16)
    para(doc, title, size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         east=HEAD_EAST, space_after=14)
    toc_field(doc, levels)
    doc.add_page_break()


# ---------------------------------------------------------------- 企业样式
def corporate_margins(doc):
    sec = doc.sections[0]
    sec.left_margin = Cm(3.175)
    sec.right_margin = Cm(3.175)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)


def corporate_header(doc, version='1.0', owner='信息科技部',
                     logo_path=None, doc_title='操作手册（项目）'):
    hdr = doc.sections[0].header
    p = hdr.paragraphs[0]
    p.text = ''
    t = hdr.add_table(rows=1, cols=3, width=Cm(14.6))
    t.style = 'Table Grid'
    t.alignment = 1
    c0, c1, c2 = t.rows[0].cells
    c0.width, c1.width, c2.width = Cm(4.4), Cm(5.2), Cm(5.0)
    if logo_path and os.path.exists(logo_path):
        cp = c0.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.add_run().add_picture(logo_path, width=Cm(3.9))
    c1.text = ''
    r = c1.paragraphs[0].add_run('招商信诺人寿保险有限公司')
    set_run(r, size=10.5, bold=True, east=HEAD_EAST)
    r = c1.add_paragraph().add_run(doc_title)
    set_run(r, size=10.5, bold=True, east=HEAD_EAST)
    c2.text = ''
    for line in ('编号：', '版本：%s' % version, '制度拥有者：%s' % owner):
        r = c2.add_paragraph().add_run(line)
        set_run(r, size=10.5, bold=True, east=HEAD_EAST)
    # 发布对象
    pp = hdr.add_paragraph()
    pp.paragraph_format.space_before = Pt(2)
    r = pp.add_run('发布对象：信息科技部全体员工')
    set_run(r, size=9, bold=True)
    pPr = pp._element.get_or_add_pPr()
    bdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '8')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '000000')
    bdr.append(bottom)
    pPr.append(bdr)


def corporate_footer(doc):
    p = doc.sections[0].footer.paragraphs[0]
    p.text = ''
    p.paragraph_format.tab_stops.add_tab_stop(Cm(7.3), WD_TAB_ALIGNMENT.CENTER)
    r = p.add_run('内部使用')
    set_run(r, size=10.5)
    r = p.add_run('\t')
    set_run(r, size=10.5)
    page_field(p, size=10.5)
    r = p.add_run(' /')
    set_run(r, size=10.5)


def corporate_cover(doc, project_title, version,
                    company='招商信诺人寿保险有限公司',
                    subtitle=None, blanks_before=5, blanks_before_version=9):
    for _ in range(blanks_before):
        para(doc, '')
    para(doc, company, size=26, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)
    para(doc, '')
    para(doc, project_title, size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         east=HEAD_EAST, space_after=6)
    if subtitle:
        para(doc, subtitle, size=16, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
    para(doc, '')
    para(doc, '操作手册', size=22, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
    for _ in range(blanks_before_version):
        para(doc, '')
    para(doc, '版本：%s' % version, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def corporate_revision(doc, rows, title='文档修订记录：'):
    para(doc, title, size=14, bold=True, east=HEAD_EAST,
         space_before=6, space_after=10)
    table(doc, ['版本', '作者', '修订详情', '审核', '批准', '修订日期'], rows,
          widths=[1.8, 1.8, 7.6, 1.6, 1.6, 2.2], font_size=9)
    doc.add_page_break()
