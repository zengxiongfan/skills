# -*- coding: utf-8 -*-
"""精确 dump 表头表格：逐行取真实 tc 列表 + gridSpan/tcW/vAlign + 每 run 的 rPr。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

path = sys.argv[1]
doc = Document(path)
t = doc.tables[0]


def x(el):
    if el is None:
        return '-'
    s = etree.tostring(el, encoding='unicode')
    s = re.sub(r'\s+xmlns:\w+="[^"]*"', '', s)
    s = s.replace('w:', '').replace('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


print('tblPr:', x(t._tbl.tblPr))
print('grid:', [gc.get(qn('w:w')) for gc in t._tbl.find(qn('w:tblGrid'))])

for ri, tr in enumerate(t._tbl.findall(qn('w:tr'))):
    print(f'\n=== ROW {ri} ===')
    print('  trPr:', x(tr.find(qn('w:trPr'))))
    for ci, tc in enumerate(tr.findall(qn('w:tc'))):
        tcPr = tc.find(qn('w:tcPr'))
        w = tcPr.find(qn('w:tcW')) if tcPr is not None else None
        gs = tcPr.find(qn('w:gridSpan')) if tcPr is not None else None
        va = tcPr.find(qn('w:vAlign')) if tcPr is not None else None
        text = ''.join(n.text or '' for n in tc.iter(qn('w:t')))
        print(f'  tc[{ci}] w={w.get(qn("w:w")) if w is not None else "-"} '
              f'gridSpan={gs.get(qn("w:val")) if gs is not None else "-"} '
              f'vAlign={va.get(qn("w:val")) if va is not None else "-"} text={text!r}')
        for p in tc.findall(qn('w:p')):
            print('     pPr:', x(p.find(qn('w:pPr'))))
            for r in p.findall(qn('w:r')):
                rt = ''.join(n.text or '' for n in r.iter(qn('w:t')))
                print(f'     run {rt!r} rPr: {x(r.find(qn("w:rPr")))}')
