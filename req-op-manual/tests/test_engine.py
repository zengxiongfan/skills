# -*- coding: utf-8 -*-
"""req-op-manual 冒烟测试：引擎生成、需求解析、merge 工具函数。

运行：
    python tests/test_engine.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, 'scripts')
sys.path.insert(0, SCRIPTS)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, 'w', encoding='utf-8').write(text)


def test_build_single(tmp):
    import docx
    assets = os.path.join(tmp, 'assets')
    os.makedirs(assets, exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'assets', 'logo.png'),
                os.path.join(assets, 'fig2_1_example.png'))
    content = '''# -*- coding: utf-8 -*-
import os
from docx_engine import h1, h2, para, bullets, steps, table, figure, placeholder

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

def build(doc):
    h1(doc, "2  需求点一：示例功能")
    h2(doc, "2.1  功能描述")
    bullets(doc, ["要点一", "要点**加粗**二"])
    h2(doc, "2.2  操作方法")
    steps(doc, ["步骤一", "步骤二"])
    table(doc, ["字段", "说明"], [["A", "说明A"]], widths=[4, 8])
    figure(doc, os.path.join(ASSETS, "fig2_1_example.png"), "示例截图", "2", 2.0)
    placeholder(doc, "建议补充：示例占位")
'''
    _write(os.path.join(tmp, 'content.py'), content)
    manifest = {
        'mode': 'single', 'project': '示例项目', 'version': '1.0',
        'output': os.path.join(tmp, 'out.docx'), 'style': 'simple',
        'header_text': '示例页眉',
        'cover': {'lines': [{'text': '示例项目', 'size': 24, 'bold': True},
                            {'text': '操作手册', 'size': 22, 'bold': False}]},
        'doc_info': [['文档名称', '示例'], ['需求编号', 'X-1']],
        'revision': [['1.0', 'C-创建', '2026-11-17', '创建文档', '—']],
        'toc': [['1', '手册说明'], ['2', '需求点一：示例功能']],
        'content': os.path.join(tmp, 'content.py'),
        'appendix': {'rows': [['1', '2.2', '示例待补截图']]},
    }
    mp = os.path.join(tmp, 'manifest.json')
    _write(mp, json.dumps(manifest, ensure_ascii=False, indent=2))
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'build_single.py'),
                        '--manifest', mp, '--out', manifest['output']], cwd=tmp)
    assert r.returncode == 0, 'build_single failed'
    d = docx.Document(manifest['output'])
    h1s = [p.text for p in d.paragraphs if p.style.name == 'Heading 1']
    caps = [p.text for p in d.paragraphs if p.text.strip().startswith('图')]
    assert any('需求点一' in t for t in h1s), h1s
    assert caps and caps[0].startswith('图2-1'), caps
    assert any('【截图待补充】' in p.text for p in d.paragraphs)
    assert len(d.tables) >= 2, len(d.tables)
    assert len(d.inline_shapes) == 1, len(d.inline_shapes)
    print('PASS build_single ->', manifest['output'])


def test_parse_requirement(tmp):
    from parse_requirement import parse
    md = '''# 4 业务功能需求
## 4.1 功能A
### 4.1.1 功能路径
【福利管理】-【保单理赔福利录入】
### 4.1.2 规则说明
- 规则一
## 4.2 功能B
### 4.2.1 规则说明
- 规则二
'''
    p = os.path.join(tmp, 'req.md')
    _write(p, md)
    data = parse(p)
    nos = [x['no'] for x in data['points']]
    assert '4.1' in nos and '4.2' in nos, nos
    assert '4.1.1' not in nos, nos
    paths = [x['paths'] for x in data['points'] if x['no'] == '4.1'][0]
    assert paths and '【福利管理】-【保单理赔福利录入】' in paths[0], paths
    print('PASS parse_requirement ->', nos)


def test_merge_helpers():
    from merge_core import strip_number, map_chapter
    assert strip_number('2  需求点一：示例') == '需求点一：示例'
    assert map_chapter('2.2', 3) == '3.1.2'
    assert map_chapter('—', 3) == '—'
    print('PASS merge_core helpers')


def main():
    tmp = tempfile.mkdtemp(prefix='op_manual_test_')
    try:
        test_build_single(tmp)
        test_parse_requirement(tmp)
        test_merge_helpers()
        print('ALL TESTS PASSED')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
