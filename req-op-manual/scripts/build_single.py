# -*- coding: utf-8 -*-
"""build_single — 按 manifest + content.py 生成单本操作手册 docx。

用法：
    python build_single.py --manifest manifest.json [--content content.py] --out 手册.docx

content.py 约定：
    def build(doc):
        # 使用 docx_engine 的 h2/para/bullets/steps/table/figure/placeholder ...
        ...
"""
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from docx_engine import (  # noqa: E402
    new_document, setup_page, h1, table, para,
    header_text, footer_page, cover_simple, info_block, revision_simple,
    toc_static, toc_page,
    corporate_margins, corporate_header, corporate_footer,
    corporate_cover, corporate_revision,
)

SKILL_ROOT = os.path.dirname(HERE)
LOGO = os.path.join(SKILL_ROOT, 'assets', 'logo.png')


def load_content(path):
    spec = importlib.util.spec_from_file_location('op_manual_content', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, 'build'):
        raise AttributeError('content.py 必须定义 build(doc) 函数')
    return mod


def main():
    if '--manifest' not in sys.argv:
        print(__doc__)
        sys.exit(2)
    mp = sys.argv[sys.argv.index('--manifest') + 1]
    manifest = json.load(io.open(mp, encoding='utf-8'))
    content_path = None
    if '--content' in sys.argv:
        content_path = sys.argv[sys.argv.index('--content') + 1]
    else:
        content_path = manifest.get('content')
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else manifest['output']
    style = manifest.get('style', 'simple')
    version = str(manifest.get('version', '1.0'))
    project = manifest.get('project', '')

    doc = new_document()
    if style == 'corporate':
        setup_page(doc, 3.175, 3.175, 2.54, 2.54)
        corporate_header(doc, version=version, logo_path=LOGO)
        corporate_footer(doc)
        subtitle = manifest.get('cover', {}).get('subtitle')
        corporate_cover(doc, project, version, subtitle=subtitle)
    else:
        setup_page(doc)
        header_text(doc, manifest.get('header_text') or project)
        footer_page(doc)
        lines = manifest.get('cover', {}).get('lines') or [
            {'text': project, 'size': 24, 'bold': True},
            {'text': '操作手册', 'size': 22, 'bold': False},
        ]
        cover_simple(doc, [(l['text'], l['size'], l.get('bold', False)) for l in lines], version)

    if manifest.get('doc_info'):
        info_block(doc, manifest['doc_info'])
        doc.add_page_break()
    if manifest.get('revision'):
        if style == 'corporate':
            corporate_revision(doc, manifest['revision'])
        else:
            revision_simple(doc, manifest['revision'])
            doc.add_page_break()

    if manifest.get('toc_field') or style == 'corporate':
        toc_page(doc, manifest.get('toc_levels', '1-2'))
    elif manifest.get('toc'):
        toc_static(doc, [(str(a), str(b)) for a, b in manifest['toc']])
        doc.add_page_break()

    if not content_path:
        raise SystemExit('缺少 content.py（manifest.content 或 --content）')
    content_path = os.path.abspath(content_path)
    if os.path.dirname(content_path) not in sys.path:
        sys.path.insert(0, os.path.dirname(content_path))
    mod = load_content(content_path)
    mod.build(doc)

    appendix = manifest.get('appendix') or {}
    if appendix.get('rows'):
        h1(doc, appendix.get('title') or '附录：截图补充清单')
        headers = appendix.get('headers') or ['序号', '对应章节', '需补充的截图内容']
        table(doc, headers, appendix['rows'], font_size=8.5)
        para(doc, '')
        para(doc, '—— 本手册完 ——', align=1)

    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    doc.save(out)
    print('saved:', out)
    print('tables:', len(doc.tables), 'images:', len(doc.inline_shapes))


if __name__ == '__main__':
    main()
