# -*- coding: utf-8 -*-
"""生成/重建内置自测报告模板 assets/report_template.docx。

模板结构与《【自测报告】RCP-15795--...（第三个迭代）.docx》逐项对齐（该文档为格式基准）：

标题：开发测试报告（居中、加粗、微软雅黑 10pt）
表头表格（4 列，tblW=11057dxa、tblInd=-5、fixed 布局、网格 1283/5281/1338/3155）：
  row0 需求编号+名称（跨 4 列，10.5pt 不加粗，行高 445）
  row1 模块 | 值(9pt 加粗) | 提交日期 | 日期(加粗)   [行高 486]
  row2 测试人 | 值 | 测试结论 | 测试通过(绿色 00B050) [行高 388]
  row3 测试环境 | 值(跨 3 列、加粗、10pt)               [行高 388]
正文：1、测试功能描述（10pt）+ 1.1（首节标题占位，10pt、首行缩进清零）

用法：
  python make_template.py [--out assets/report_template.docx]
"""
import argparse
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips

FONT = '微软雅黑'
VERDICT_COLOR = '00B050'

# 页面：A4 + 历史报告窄边距（可用宽度 19.5cm，够放 19.44cm 截图）
PAGE_W, PAGE_H = 11906, 16838
MARGIN_T, MARGIN_R, MARGIN_B, MARGIN_L = 284, 424, 426, 426

# 表头表格几何（与参考报告一致）
TBL_W = 11057
TBL_IND = -5
GRID = [1283, 5281, 1338, 3155]
ROW_HEIGHTS = [445, 486, 388, 388]


def _apply_font(rPr):
    """确保 rPr 下有 rFonts 并写入字体（rPr.rFonts 可能为 None）。"""
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = rPr.makeelement(qn('w:rFonts'), {})
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), FONT)
    rFonts.set(qn('w:hAnsi'), FONT)
    rFonts.set(qn('w:eastAsia'), FONT)
    rFonts.set(qn('w:cs'), FONT)


def set_run(run, text=None, size=10.5, bold=False, color=None):
    if text is not None:
        run.text = text
    _apply_font(run._element.get_or_add_rPr())
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def fill_cell(cell, text, size=10.5, bold=False, color=None):
    """清空单元格（含残留空 run），写入单段单 run，并设置垂直居中。"""
    cell.text = ''
    p = cell.paragraphs[0]
    for r in list(p.runs):          # cell.text='' 后仍可能留一个空 run
        r._element.getparent().remove(r._element)
    set_run(p.add_run(), text=text, size=size, bold=bold, color=color)

    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:vAlign')):
        tcPr.remove(old)
    tcPr.append(tcPr.makeelement(qn('w:vAlign'), {qn('w:val'): 'center'}))


def set_table_geometry(table):
    """python-docx 不直接暴露 tblW/tblInd/tblLayout，这里按参考报告写入 XML。"""
    tblPr = table._tbl.tblPr

    for tag in ('w:tblW', 'w:tblInd', 'w:tblLayout'):
        el = tblPr.find(qn(tag))
        if el is not None:
            tblPr.remove(el)

    tblW = tblPr.makeelement(qn('w:tblW'), {qn('w:w'): str(TBL_W), qn('w:type'): 'dxa'})
    tblInd = tblPr.makeelement(qn('w:tblInd'), {qn('w:w'): str(TBL_IND), qn('w:type'): 'dxa'})
    layout = tblPr.makeelement(qn('w:tblLayout'), {qn('w:type'): 'fixed'})
    tblPr.append(tblW)
    tblPr.append(tblInd)
    tblPr.append(layout)

    # 单元格边距：上下 0、左右 108（与参考一致）
    mar = tblPr.find(qn('w:tblCellMar'))
    if mar is not None:
        tblPr.remove(mar)
    mar = tblPr.makeelement(qn('w:tblCellMar'), {})
    for side, w in (('top', 0), ('left', 108), ('bottom', 0), ('right', 108)):
        mar.append(mar.makeelement(qn('w:' + side), {qn('w:w'): str(w), qn('w:type'): 'dxa'}))
    tblPr.append(mar)

    grid = table._tbl.find(qn('w:tblGrid'))
    for gc, w in zip(grid, GRID):
        gc.set(qn('w:w'), str(w))

    for tr, h in zip(table._tbl.findall(qn('w:tr')), ROW_HEIGHTS):
        trPr = tr.find(qn('w:trPr'))
        if trPr is None:
            trPr = tr.makeelement(qn('w:trPr'), {})
            tr.insert(0, trPr)
        for old in trPr.findall(qn('w:trHeight')):
            trPr.remove(old)
        trPr.append(trPr.makeelement(qn('w:trHeight'), {
            qn('w:val'): str(h), qn('w:hRule'): 'atLeast'}))


def build(out_path):
    doc = Document()

    sec = doc.sections[0]
    sec.page_width = Twips(PAGE_W)
    sec.page_height = Twips(PAGE_H)
    sec.top_margin = Twips(MARGIN_T)
    sec.right_margin = Twips(MARGIN_R)
    sec.bottom_margin = Twips(MARGIN_B)
    sec.left_margin = Twips(MARGIN_L)
    sec.header_distance = Twips(851)
    sec.footer_distance = Twips(992)

    # 正文默认字体（记录在 Normal 上，逐段仍显式设置）
    normal = doc.styles['Normal']
    normal.font.name = FONT
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

    # 标题：居中加粗 10pt
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run(p.add_run(), text='开发测试报告', size=10, bold=True)

    # 表头表格
    table = doc.add_table(rows=4, cols=4)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_geometry(table)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = Twips(GRID[idx])

    # row0：需求编号+名称（跨 4 列，10.5pt 不加粗）
    table.cell(0, 0).merge(table.cell(0, 3))
    fill_cell(table.cell(0, 0), '{{req_title}}', size=10.5, bold=False)

    # row1：模块 / 提交日期
    fill_cell(table.cell(1, 0), '模块', size=10.5, bold=True)
    fill_cell(table.cell(1, 1), '{{modules}}', size=9, bold=True)
    fill_cell(table.cell(1, 2), '提交日期', size=10.5, bold=True)
    fill_cell(table.cell(1, 3), '{{submit_date}}', size=10.5, bold=True)

    # row2：测试人 / 测试结论（结论绿色）
    fill_cell(table.cell(2, 0), '测试人', size=10.5, bold=True)
    fill_cell(table.cell(2, 1), '{{tester}}', size=10.5, bold=True)
    fill_cell(table.cell(2, 2), '测试结论', size=10.5, bold=True)
    fill_cell(table.cell(2, 3), '{{verdict}}', size=10.5, bold=False, color=VERDICT_COLOR)

    # row3：测试环境（跨 3 列、加粗、10pt）
    table.cell(3, 1).merge(table.cell(3, 3))
    fill_cell(table.cell(3, 0), '测试环境', size=10.5, bold=True)
    fill_cell(table.cell(3, 1), '{{env}}', size=10, bold=True)

    # 正文
    p = doc.add_paragraph()
    set_run(p.add_run(), text='1、测试功能描述', size=10, bold=False)

    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Pt(0)
    p.paragraph_format.first_line_indent = Pt(0)
    set_run(p.add_run(), text='1.1', size=10, bold=False)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    doc.save(out_path)
    print('template saved:', out_path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        os.path.dirname(__file__), '..', 'assets', 'report_template.docx'))
    args = ap.parse_args()
    build(args.out)
