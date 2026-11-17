# -*- coding: utf-8 -*-
"""build_merge — 把多本操作手册整合为一份，保留全部需求点并统一重编号。

用法：
    python build_merge.py --manifest merge.json --out 整合版.docx [--update-toc]

merge.json 关键字段：
{
  "project": "团险系统NHB保单福利和理算升级项目",
  "version": "2.0",
  "output": "...docx",
  "cover": {"subtitle": "（可选）"},
  "revision": [["2.0","—","创建文档...","","","2026.11"]],
  "toc_levels": "1-2",
  "part_intro": true,
  "drop_chapters": ["手册说明"],
  "sources": [
    {"label": "RCP-15793 第一个迭代", "path": "...docx", "part_title": "RCP-15793 · 第一个迭代——..."},
    ...
  ]
}
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from docx import Document
from docx.oxml.ns import qn

from docx_engine import (  # noqa: E402
    new_document, h1, h2, h3, h4, para, table,
    corporate_margins, corporate_header, corporate_footer,
    corporate_cover, corporate_revision, toc_page,
)
from merge_core import (  # noqa: E402
    p_style_id, p_text, strip_number, copy_element, parse_outline, map_chapter,
)

SKILL_ROOT = os.path.dirname(HERE)
LOGO = os.path.join(SKILL_ROOT, 'assets', 'logo.png')


def copy_source_body(doc, path, part_no, drop_terms, stats):
    src = Document(path)
    body = src.element.body
    src_part = src.part
    tgt_part = doc.part
    started = False
    in_intro = False
    in_appendix = False
    skipping_req = False
    k = 0
    sub = 0
    figs = {}
    for child in body.iterchildren():
        tag = child.tag.split('}')[-1]
        if tag == 'sectPr':
            continue
        if tag == 'p':
            sid = p_style_id(child)
            text = p_text(child).strip()
            if not started:
                if sid != 'Heading1':
                    continue
                norm = re.sub(r'\s+', '', strip_number(text))
                if norm in ('文档信息', '目录'):
                    continue
                started = True
                if '手册说明' in text:
                    in_intro = True
                    continue
            if in_intro:
                if sid == 'Heading1':
                    in_intro = False
                else:
                    continue
            if in_appendix:
                continue
            if sid == 'Heading1':
                if '附录' in text:
                    in_appendix = True
                    continue
                if any(term and term in text for term in drop_terms):
                    skipping_req = True
                    continue
                skipping_req = False
                k += 1
                sub = 0
                h2(doc, '%d.%d  %s' % (part_no, k, strip_number(text)))
                stats['reqs'] += 1
                continue
            if skipping_req:
                continue
            if sid == 'Heading2':
                sub += 1
                h3(doc, '%d.%d.%d  %s' % (part_no, k, sub, strip_number(text)))
                continue
            if sid in ('Heading3', 'Heading4'):
                h4(doc, strip_number(text))
                continue
            if text and '本手册完' in text:
                continue
            el = copy_element(tgt_part, src_part, child)
            m = re.match(r'^图\s*[\d\.]+-\d+\s*(.*)$', text)
            if m and k:
                figs[k] = figs.get(k, 0) + 1
                new_caption = '图%d.%d-%d %s' % (part_no, k, figs[k], m.group(1))
                ts = list(el.iter(qn('w:t')))
                if ts:
                    ts[0].text = new_caption
                    for extra in ts[1:]:
                        extra.text = ''
                stats['figs'] += 1
            doc.element.body.insert(len(doc.element.body) - 1, el)
        elif tag == 'tbl':
            if (not started) or in_intro or in_appendix or skipping_req:
                continue
            doc.element.body.insert(len(doc.element.body) - 1,
                                    copy_element(tgt_part, src_part, child))
            stats['tables'] += 1


def build_appendix(doc, sources, outlines, title):
    if not re.match(r'^\d+\s', title):
        title = '%d  %s' % (len(sources) + 1, title)
    h1(doc, title)
    para(doc, '本附录汇总各需求手册中标注【截图待补充】的场景，需在正式环境补充截图后更新对应章节：')
    rows = []
    n = 0
    for pi, src in enumerate(sources, 1):
        rows_src = outlines[src['path']][2]
        for r in rows_src:
            if not r or r[0] in ('序号', ''):
                continue
            while len(r) < 3:
                r.append('')
            n += 1
            rows.append([str(n), src['label'], map_chapter(r[1], pi), r[2]])
    table(doc, ['序号', '所属需求（迭代）', '对应章节', '需补充的截图内容'], rows,
          widths=[1.4, 4.6, 2.6, 8.0], font_size=8.5)
    return n


def main():
    if '--manifest' not in sys.argv:
        print(__doc__)
        sys.exit(2)
    mp = sys.argv[sys.argv.index('--manifest') + 1]
    manifest = json.load(io.open(mp, encoding='utf-8'))
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else manifest['output']
    version = str(manifest.get('version', '1.0'))
    project = manifest.get('project', '')
    sources = manifest.get('sources') or []
    if not sources:
        raise SystemExit('merge.json 缺少 sources')

    outlines = {}
    for src in sources:
        if not os.path.exists(src['path']):
            raise SystemExit('源手册不存在: %s' % src['path'])
        outlines[src['path']] = parse_outline(src['path'])

    doc = new_document()
    corporate_margins(doc)
    corporate_header(doc, version=version, logo_path=LOGO)
    corporate_footer(doc)
    corporate_cover(doc, project, version,
                    subtitle=(manifest.get('cover') or {}).get('subtitle'))
    revision = manifest.get('revision') or [
        [version, '—', '创建文档（整合版 V%s）' % version, '', '', '']
    ]
    corporate_revision(doc, revision)
    toc_page(doc, manifest.get('toc_levels', '1-2'))

    stats = {'reqs': 0, 'figs': 0, 'tables': 0}
    drop_terms = manifest.get('drop_chapters') or []
    for pi, src in enumerate(sources, 1):
        h1(doc, '%d  %s' % (pi, src['part_title']))
        intro = src.get('intro') or (outlines[src['path']][1] or [''])[0]
        if intro and manifest.get('part_intro', True):
            para(doc, intro, size=10, color='404040')
        copy_source_body(doc, src['path'], pi, drop_terms, stats)
        doc.add_page_break()

    app_title = manifest.get('appendix_title') or '附录：截图补充清单'
    n_app = build_appendix(doc, sources, outlines, app_title)
    para(doc, '')
    para(doc, '—— 本手册完 ——', align=1)

    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    doc.save(out)
    print('saved:', out)
    print('parts:', len(sources), 'reqs:', stats['reqs'], 'figs:', stats['figs'],
          'tables:', stats['tables'], 'appendix:', n_app)

    if '--update-toc' in sys.argv:
        try:
            import verify
            verify.update_toc(out)
            print('toc updated')
        except Exception as e:  # noqa: BLE001
            print('WARN: 更新目录失败（可在 Word 中右键更新域）:', e)


if __name__ == '__main__':
    main()
