# -*- coding: utf-8 -*-
"""生成/重建内置自测报告模板 assets/report_template.docx。

模板结构（与 CGIS 历史自测报告一致）：
  标题：开发测试报告（加粗居中，微软雅黑 10pt）
  表头表格（4列）：{{req_title}} 行 / 模块-{{modules}}-提交日期-{{submit_date}} /
                  测试人-{{tester}}-测试结论-{{verdict}} / 测试环境-{{env}}（跨3列）
  正文：1、测试功能描述 + 1.1（占位段落，生成时替换为首节标题）

用法：
  python make_template.py [--out assets/report_template.docx]
"""
import argparse
import os

from docx import Document
from docx.shared import Pt, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

FONT = '微软雅黑'


def set_run(run, text=None, size=9, bold=False):
    if text is not None:
        run.text = text
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    run.font.size = Pt(size)
    run.font.bold = bold


def fill_cell(cell, text, bold=False, size=9):
    cell.text = ''
    p = cell.paragraphs[0]
    set_run(p.add_run(), text=text, size=size, bold=bold)


def build(out_path):
    doc = Document()

    # 页面：A4 + 窄边距（与历史报告一致，保证 19cm 宽截图可用）
    sec = doc.sections[0]
    sec.page_width = Twips(11906)
    sec.page_height = Twips(16838)
    sec.top_margin = Twips(284)
    sec.right_margin = Twips(424)
    sec.bottom_margin = Twips(426)
    sec.left_margin = Twips(426)
    sec.header_distance = Twips(851)
    sec.footer_distance = Twips(992)

    # 正文默认字体
    normal = doc.styles['Normal']
    normal.font.name = FONT
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

    # 标题
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run(p.add_run(), text='开发测试报告', size=10, bold=True)

    # 表头表格
    table = doc.add_table(rows=4, cols=4)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = [Twips(1300), Twips(5590), Twips(1430), Twips(3330)]
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = widths[idx]

    table.cell(0, 0).merge(table.cell(0, 3))
    fill_cell(table.cell(0, 0), '{{req_title}}', size=9)
    fill_cell(table.cell(1, 0), '模块', bold=True)
    fill_cell(table.cell(1, 1), '{{modules}}')
    fill_cell(table.cell(1, 2), '提交日期', bold=True)
    fill_cell(table.cell(1, 3), '{{submit_date}}')
    fill_cell(table.cell(2, 0), '测试人', bold=True)
    fill_cell(table.cell(2, 1), '{{tester}}')
    fill_cell(table.cell(2, 2), '测试结论', bold=True)
    fill_cell(table.cell(2, 3), '{{verdict}}')
    table.cell(3, 1).merge(table.cell(3, 3))
    fill_cell(table.cell(3, 0), '测试环境', bold=True)
    fill_cell(table.cell(3, 1), '{{env}}')

    # 正文
    p = doc.add_paragraph()
    set_run(p.add_run(), text='1、测试功能描述', size=10)
    p = doc.add_paragraph()
    set_run(p.add_run(), text='1.1', size=10)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    doc.save(out_path)
    print('template saved:', out_path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'assets', 'report_template.docx'))
    args = ap.parse_args()
    build(args.out)
