# -*- coding: utf-8 -*-
"""阶段4：按 report.json 用内置模板生成自测报告 docx（幂等重建）。

用法：
  python build_report.py --spec report.json --out “xxx-已填写.docx” \
      [--template assets/report_template.docx]

report.json：
{
  "header": {"req_title": "...", "tester": "...", "submit_date": "auto",
             "modules": "", "verdict": "测试通过", "env": "DEV测试环境 localhost:8080"},
  "sections": [
    {"title": "1.1新福利配置页调整",
     "intro": "功能说明……",
     "cases": [
       {"label": "在方案层配置公共保额要素：", "desc": "……", "image": "report_assets/c01_image1.png"},
       {"label": "……：", "desc": "……（执行截图同上）"},
       {"label": "……：", "desc": "……", "note": "（执行截图待补充）"}
     ]}
  ]
}
"""
import argparse
import datetime
import json
import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu, Pt

FONT = '微软雅黑'
CASE_NO_RE = re.compile(r'^RCP-\d+-\d+\s*')          # 案例编号不写入报告
DEFAULT_VERDICT = '测试通过'
DEFAULT_ENV = 'DEV测试环境 localhost:8080'


def set_run(run, text=None, size=10.5, bold=False):
    if text is not None:
        run.text = text
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    run.font.size = Pt(size)
    run.font.bold = bold


def iter_cells(doc):
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                yield cell


def fill_placeholders(doc, mapping):
    for cell in iter_cells(doc):
        for p in cell.paragraphs:
            if '{{' not in p.text:
                continue
            new = p.text
            for k, v in mapping.items():
                new = new.replace('{{' + k + '}}', v)
            if p.runs:
                p.runs[0].text = new
                for r in p.runs[1:]:
                    r.text = ''
            else:
                p.add_run(new)


def find_body_para(doc, text):
    for p in doc.paragraphs:
        if p.text.strip() == text:
            return p
    return None


def image_width_emu(doc):
    sec = doc.sections[0]
    usable = sec.page_width - sec.left_margin - sec.right_margin
    return int(min(7000000, usable - 20000))


def build(spec_path, out_path, template_path):
    spec = json.load(open(spec_path, encoding='utf-8'))
    header = spec.get('header', {})
    sections = spec.get('sections', [])
    if not sections:
        raise SystemExit('[build_report] report.json 缺少 sections')

    doc = Document(template_path)
    mapping = {
        'req_title': header.get('req_title', ''),
        'tester': header.get('tester', ''),
        'modules': header.get('modules', ''),
        'verdict': header.get('verdict') or DEFAULT_VERDICT,
        'env': header.get('env') or DEFAULT_ENV,
        'submit_date': (datetime.date.today().strftime('%Y/%m/%d')
                        if not header.get('submit_date') or header.get('submit_date') == 'auto'
                        else header['submit_date']),
    }
    fill_placeholders(doc, mapping)

    # 占位段落 1.1 → 首节标题
    first = find_body_para(doc, '1.1')
    if first is None:
        raise SystemExit('[build_report] 模板中未找到 "1.1" 占位段落')
    first.paragraph_format.left_indent = Pt(0)
    first.paragraph_format.first_line_indent = Pt(0)
    for r in list(first.runs):
        r._element.getparent().remove(r._element)
    set_run(first.add_run(), text=sections[0]['title'], size=10)

    def add_para(text=None, size=10.5, bold=False):
        p = doc.add_paragraph()
        if text:
            set_run(p.add_run(), text=text, size=size, bold=bold)
        return p

    img_w = image_width_emu(doc)
    skipped_images = []
    for idx, sec in enumerate(sections):
        if idx > 0:
            add_para(sec['title'], size=10)
        if sec.get('intro'):
            add_para(sec['intro'], size=10.5)
        for case in sec.get('cases', []):
            label = CASE_NO_RE.sub('', case.get('label', ''))
            desc = case.get('desc', '')
            if case.get('note') and case['note'] not in desc:
                desc += case['note']
            p = doc.add_paragraph()
            set_run(p.add_run(), text=label, size=10.5, bold=True)
            set_run(p.add_run(), text=desc, size=10.5, bold=False)
            img = case.get('image')
            if img:
                if not os.path.exists(img):
                    skipped_images.append(img)
                    continue
                pic = doc.add_paragraph()
                pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pic.add_run().add_picture(img, width=Emu(img_w))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    doc.save(out_path)
    print(f'saved: {out_path}')
    print(f'  sections={len(sections)} cases={sum(len(s["cases"]) for s in sections)}'
          f' images={sum(1 for s in sections for c in s["cases"] if c.get("image")) - len(skipped_images)}')
    if skipped_images:
        print('  WARNING missing images:', skipped_images)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--template',
                    default=os.path.join(os.path.dirname(__file__), '..', 'assets', 'report_template.docx'))
    args = ap.parse_args()
    build(args.spec, args.out, args.template)
