# -*- coding: utf-8 -*-
"""比对生成报告与参考报告的格式（表头字符格式、页面几何、正文字号）。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Emu

gen, ref = sys.argv[1], sys.argv[2]


def fmt_run(run):
    rPr = run._element.rPr
    if rPr is None:
        return '-'
    rf = rPr.find(qn('w:rFonts'))
    sz = rPr.find(qn('w:sz'))
    b = rPr.find(qn('w:b'))
    c = rPr.find(qn('w:color'))
    return dict(
        ea=rf.get(qn('w:eastAsia')) if rf is not None else None,
        sz=int(sz.get(qn('w:val'))) / 2 if sz is not None else None,
        bold=(b is not None and b.get(qn('w:val')) != '0'),
        color=c.get(qn('w:val')) if c is not None else None,
    )


def table_sig(doc):
    t = doc.tables[0]
    out = []
    for tr in t._tbl.findall(qn('w:tr')):
        for tc in tr.findall(qn('w:tc')):
            text = ''.join(n.text or '' for n in tc.iter(qn('w:t')))
            runs = [fmt_run_obj(r) for p in tc.findall(qn('w:p'))
                    for r in p.findall(qn('w:r'))]
            out.append((text, runs))
    return out


def fmt_run_obj(r):
    from docx.text.run import Run
    return fmt_run(Run(r, None))


def page_geo(doc):
    s = doc.sections[0]
    return (Emu(s.page_width).cm, Emu(s.page_height).cm,
            Emu(s.left_margin).cm, Emu(s.right_margin).cm,
            Emu(s.top_margin).cm, Emu(s.bottom_margin).cm)


ds = {'gen': Document(gen), 'ref': Document(ref)}
for name, doc in ds.items():
    print(f'--- {name} page geometry (cm): {tuple(round(x,2) for x in page_geo(doc))}')

print('\n--- header table cells (text | eastAsia | sz | bold | color) ---')
for name, doc in ds.items():
    print(f'\n[{name}]')
    for text, runs in table_sig(doc):
        if not text.strip():
            continue
        r = runs[0] if runs else {}
        print(f'  {text[:46]!r:<50} ea={r.get("ea")} sz={r.get("sz")} bold={r.get("bold")} color={r.get("color")}')

print('\n--- body paragraph sizes ---')
for name, doc in ds.items():
    sizes = {}
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        for r in p.runs:
            if not r.text.strip():
                continue
            f = fmt_run(r)
            key = (f['sz'], f['bold'])
            sizes[key] = sizes.get(key, 0) + 1
    print(f'  {name}: {sorted(sizes.items(), key=lambda kv: -kv[1])}')

print('\n--- image widths (EMU) ---')
for name, doc in ds.items():
    ws = []
    for p in doc.paragraphs:
        for ext in p._p.iter():
            if ext.tag.endswith('}extent'):
                ws.append(ext.get('cx'))
    print(f'  {name}: count={len(ws)} unique={sorted(set(ws))}')
