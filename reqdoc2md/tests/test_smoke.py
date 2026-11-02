"""Dependency-free smoke tests for the core table/outline logic.

Run with: python tests/test_smoke.py
"""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))

from core import manifest, tables  # noqa: E402
from core.convert_docx import (  # noqa: E402
    _clean_empty_list_items,
    _fix_list_hierarchy,
    _split_attachment_links,
)


def cell(text: str, rowspan: int = 1, colspan: int = 1) -> list:
    return [
        ['', [], []],
        {'t': 'AlignDefault'},
        rowspan,
        colspan,
        [{'t': 'Plain', 'c': [{'t': 'Str', 'c': text}]}],
    ]


def table_node() -> dict:
    # 3x3: header merges two columns, one vertical merge in body
    rows = [
        [cell('字段'), cell('说明', colspan=2)],
        [cell('A', rowspan=2), cell('B'), cell('C')],
        [cell('D'), cell('E')],
        [cell('合并行', colspan=3)],
    ]
    row_nodes = [[['', [], []], cells] for cells in rows]
    return {
        't': 'Table',
        'c': [
            ['', [], []],
            [None, []],
            [[{'t': 'AlignDefault'}, {'t': 'ColWidthDefault'}] * 3],
            [['', [], []], []],
            [[['', [], []], 0, [], row_nodes]],
            [['', [], []], []],
        ],
    }


def test_table_grid():
    td = tables.from_ast_table(table_node(), 1, header_rows=1)
    html = tables.render_table_html(td)
    assert 'colspan="2"' in html, html
    assert 'rowspan="2"' in html, html
    assert 'colspan="3"' in html, html
    assert len(td.merges) == 3, td.merges
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / 't.csv'
        tables.render_table_csv(td, csv_path)
        rows = list(csv.reader(csv_path.open(encoding='utf-8')))
    assert len(rows) == 4 and all(len(r) == 3 for r in rows), rows
    # merged horizontal value is filled in every covered column
    assert rows[3] == ['合并行', '合并行', '合并行'], rows[3]


def test_empty_table():
    node = {
        't': 'Table',
        'c': [
            ['', [], []], [None, []],
            [[{'t': 'AlignDefault'}, {'t': 'ColWidthDefault'}]],
            [['', [], []], []],
            [[['', [], []], 0, [], [[['', [], []], [cell('')]]]]],
            [['', [], []], []],
        ],
    }
    td = tables.from_ast_table(node, 1, header_rows=1)
    text, fmt, _ = tables.render_table(td)
    assert text == '（空表）' and fmt == 'empty', (text, fmt)


def test_outline():
    md = '# 1 引言\n\n## 1.1 目的\n\n正文\n\n```\n# 不是标题\n```\n\n## 1.2 范围\n'
    outline = manifest.build_outline(md)
    assert [o['number'] for o in outline] == ['1', '1.1', '1.2']
    assert outline[0]['line_start'] == 1
    assert outline[1]['line_end'] == 10, outline[1]


def test_list_hierarchy():
    md = '- parent\n\n<!-- -->\n\n- child A\n\n- child B\n\nplain paragraph\n\n- sibling\n'
    out = _fix_list_hierarchy(md)
    assert '    - child A' in out, out
    assert '    - child B' in out, out
    assert '\n- sibling' in out, out


def test_empty_list_item_cleanup():
    md = 'intro\n\n1.  \n\n2.  理算补充规则区域：A/B值\n\n3.  理算补充规则区域：统计维度\n'
    out = _clean_empty_list_items(md)
    assert '1.  理算补充规则区域：A/B值' in out, out
    assert '2.  理算补充规则区域：统计维度' in out, out
    assert '\n1.  \n' not in out, out


def test_attachment_link_split():
    standard = '[📎 a.xlsx](x_files/attachments/a.md) [📎 b.xlsx](x_files/attachments/b.md)'
    out = _split_attachment_links(standard)
    assert out.count('📎') == 2 and '](x_files/attachments/a.md)\n' in out, out
    obsidian = '[[a_files/attachments/a]] [[b_files/attachments/b]]'
    out2 = _split_attachment_links(obsidian)
    assert out2.count('attachments/') == 2 and '\n' in out2, out2
    item = '- [📎 a.xlsx](x_files/attachments/a.md) [📎 b.xlsx](x_files/attachments/b.md)'
    out3 = _split_attachment_links(item)
    assert out3.startswith('- [📎 a.xlsx]'), out3
    assert '  [📎 b.xlsx]' in out3, out3


def main():
    tests = [
        test_table_grid, test_empty_table, test_outline, test_list_hierarchy,
        test_empty_list_item_cleanup, test_attachment_link_split,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f'PASS {test.__name__}')
        except Exception as exc:
            failed += 1
            print(f'FAIL {test.__name__}: {exc}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
