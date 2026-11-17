# -*- coding: utf-8 -*-
"""深度 dump 参考报告：段落全序列（含空段）、图片段、docDefaults、页眉页脚、sectPr。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

path = sys.argv[1]
doc = Document(path)


def rpr(run):
    r = run._element.rPr
    if r is None:
        return '-'
    fonts = r.find(qn('w:rFonts'))
    ea = fonts.get(qn('w:eastAsia')) if fonts is not None else None
    asc = fonts.get(qn('w:ascii')) if fonts is not None else None
    sz = r.find(qn('w:sz'))
    b = r.find(qn('w:b'))
    color = r.find(qn('w:color'))
    return (f"font={asc}/{ea} sz={(int(sz.get(qn('w:val')))/2 if sz is not None else None)} "
            f"b={b is not None and (b.get(qn('w:val')) != '0')} "
            f"color={color.get(qn('w:val')) if color is not None else None}")


def ppr(p):
    pr = p._p.pPr
    if pr is None:
        return '-'
    parts = []
    for tag in ('w:jc', 'w:ind', 'w:spacing', 'w:keepNext', 'w:keepLines', 'w:pageBreakBefore',
                'w:numPr', 'w:outlineLvl'):
        el = pr.find(qn(tag))
        if el is not None:
            attrs = {k.split('}')[-1]: v for k, v in el.attrib.items()}
            parts.append(f'{tag.split("}")[-1]}{attrs if attrs else ""}')
    return '; '.join(parts) or '-'


print('=' * 100)
print('PARAGRAPH SEQUENCE')
print('=' * 100)
for i, p in enumerate(doc.paragraphs):
    has_img = bool(p._p.findall('.//' + qn('w:drawing')))
    t = p.text.strip()
    if not t and not has_img:
        print(f'[{i:>3}] <EMPTY> style={p.style.name} ppr={ppr(p)}')
        continue
    if has_img:
        exts = [e for e in p._p.iter() if e.tag.endswith('}extent')]
        size = [(e.get('cx'), e.get('cy')) for e in exts]
        print(f'[{i:>3}] <IMAGE> align={p.alignment} ppr={ppr(p)} extent={size}')
        continue
    runs = [rpr(r) for r in p.runs if r.text.strip()][:2]
    print(f'[{i:>3}] style={p.style.name} align={p.alignment} ppr={ppr(p)}')
    print(f'      text={t[:90]!r}')
    for rr in runs:
        print(f'      run {rr}')

print('\n' + '=' * 100)
print('docDefaults / Normal style')
print('=' * 100)


def xml(el):
    if el is None:
        return '-'
    s = etree.tostring(el, encoding='unicode')
    s = re.sub(r'\s+xmlns:\w+="[^"]*"', '', s)
    return re.sub(r'\s+', ' ', s.replace('w:', '')).strip()


styles_el = doc.styles.element
print('docDefaults:', xml(styles_el.find(qn('w:docDefaults'))))
print('Normal:', xml(doc.styles['Normal'].element))

print('\n' + '=' * 100)
print('SECTPR')
print('=' * 100)
print(xml(doc.sections[0]._sectPr))

print('\n' + '=' * 100)
print('HEADER / FOOTER')
print('=' * 100)
for si, s in enumerate(doc.sections):
    print(f'section {si}: header paras={[p.text for p in s.header.paragraphs]!r}')
    print(f'             footer paras={[p.text for p in s.footer.paragraphs]!r}')
    print(f'             header.is_linked_to_previous={s.header.is_linked_to_previous} '
          f'footer.is_linked_to_previous={s.footer.is_linked_to_previous}')
