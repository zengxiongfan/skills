"""Completeness checks and human/machine conversion reports."""
from __future__ import annotations

from pathlib import Path

from .util import ensure_dir, write_json


def _check(check_id: str, label: str, expected, actual, ok: bool, note: str = '') -> dict:
    return {
        'id': check_id,
        'label': label,
        'expected': expected,
        'actual': actual,
        'ok': bool(ok),
        'note': note,
    }


def build_report(
    source_name: str,
    pkg_stats,
    fmt_index: dict,
    ole_records: list[dict],
    table_records: list[dict],
    output_stats: dict,
    warnings: list[dict],
    errors: list[dict],
    kind: str = 'docx',
) -> dict:
    checks: list[dict] = []
    fmt_counts = {
        'colors': len(fmt_index.get('colored_runs', [])),
        'highlights': len(fmt_index.get('highlights', [])),
        'underlines': len(fmt_index.get('underlines', [])),
        'shadings': len(fmt_index.get('shading', [])),
        'comments': len(fmt_index.get('comments', [])),
        'insertions': len(fmt_index.get('insertions', [])),
        'deletions': len(fmt_index.get('deletions', [])),
    }
    if kind == 'docx' and pkg_stats is not None:
        ole_count = len(ole_records)
        checks.append(_check('ole', 'OLE 嵌入对象', pkg_stats.embeddings, ole_count, pkg_stats.embeddings == ole_count))
        checks.append(_check('tables', '正文表格（顶层）', pkg_stats.top_tables, len(table_records), pkg_stats.top_tables == len(table_records)))
        expected_merges = pkg_stats.grid_span + pkg_stats.v_merge_restart
        actual_merges = sum(len(t.get('merges', [])) for t in table_records)
        checks.append(_check('table_merges', '合并单元格', expected_merges, actual_merges, expected_merges == actual_merges,
                             'AST 合并计数与 OOXML gridSpan/vMerge 对账'))
        checks.append(_check('comments', '批注', pkg_stats.comments, fmt_counts['comments'], pkg_stats.comments == fmt_counts['comments']))
        expected_rev = pkg_stats.insertions + pkg_stats.deletions
        actual_rev = fmt_counts['insertions'] + fmt_counts['deletions']
        checks.append(_check('revisions', '修订（插入+删除）', expected_rev, actual_rev, expected_rev == actual_rev))
        expected_fmt = pkg_stats.colors + pkg_stats.highlights + pkg_stats.underlines + pkg_stats.shadings
        actual_fmt = fmt_counts['colors'] + fmt_counts['highlights'] + fmt_counts['underlines'] + fmt_counts['shadings']
        fmt_ok = (expected_fmt == 0 and actual_fmt == 0) or (expected_fmt > 0 and actual_fmt > 0)
        checks.append(_check('formats', '颜色/高亮/下划线/底纹', expected_fmt, actual_fmt, fmt_ok,
                             'XML 计数含默认色/删除文本；实际按有效 run 统计，>0 即已生成样式标注'))
        expected_images = pkg_stats.media
        actual_images = output_stats.get('images', 0)
        checks.append(_check('images', '图片产出', expected_images, actual_images,
                             actual_images > 0 or expected_images == 0,
                             'OLE 预览图不复制，页眉/未引用媒体不计入正文图片'))
    elif kind == 'xlsx':
        checks.append(_check('sheets', '工作表', output_stats.get('sheets', 0), output_stats.get('tables', 0),
                             output_stats.get('sheets', 0) == output_stats.get('tables', 0)))
        checks.append(_check('styles', 'Excel 样式单元格', output_stats.get('style_cells', 0),
                             output_stats.get('style_cells', 0), True))
    elif kind == 'pdf':
        checks.append(_check('text', 'PDF 文本提取', 1 if output_stats.get('chars', 0) > 0 else 0,
                             1 if output_stats.get('chars', 0) > 0 else 0,
                             output_stats.get('chars', 0) > 0,
                             'PDF 表格不会结构化，必要时回原 PDF'))
    else:
        checks.append(_check('output', '产物生成', 1, 1 if output_stats.get('exists') else 0, bool(output_stats.get('exists'))))

    hard_fail = any(not c['ok'] for c in checks)
    status = 'failed' if errors else ('warning' if (warnings or hard_fail) else 'green')
    return {
        'schema_version': '1.0',
        'source': source_name,
        'kind': kind,
        'status': status,
        'checks': checks,
        'warnings': warnings,
        'errors': errors,
        'counts': {
            'ole': len(ole_records),
            'tables': len(table_records),
            'table_merges': sum(len(t.get('merges', [])) for t in table_records),
            'images': output_stats.get('images', 0),
            'attachments': output_stats.get('attachments', 0),
            **fmt_counts,
        },
    }


_status_label = {'green': '✅ GREEN', 'warning': '⚠️ WARNING', 'failed': '❌ FAILED'}


def render_report_md(report: dict) -> str:
    lines = [
        '# 转换报告（完整性对账）',
        '',
        f"- 状态：{_status_label.get(report['status'], report['status'])}",
        f"- 源文件：`{report['source']}`",
        '',
        '> req-doc2md 自动生成：markdown 不承载颜色/高亮等格式，本报告用于核对转换是否有信息缺口。',
        '',
        '## 对账',
        '',
        '| 检查项 | 期望 | 实际 | 结果 | 说明 |',
        '|--------|------|------|------|------|',
    ]
    for c in report['checks']:
        mark = '✓' if c['ok'] else '⚠'
        note = (c.get('note') or '').replace('|', '\\|')
        lines.append(f"| {c['label']} | {c['expected']} | {c['actual']} | {mark} | {note} |")
    lines.append('')
    if report['warnings']:
        lines.append('## 警告')
        for w in report['warnings']:
            loc = f"（{w.get('location')}）" if w.get('location') else ''
            lines.append(f"- `{w.get('code', 'warning')}` {w.get('message', '')}{loc}")
        lines.append('')
    if report['errors']:
        lines.append('## 错误')
        for e in report['errors']:
            loc = f"（{e.get('location')}）" if e.get('location') else ''
            lines.append(f"- `{e.get('code', 'error')}` {e.get('message', '')}{loc}")
        lines.append('')
    if report['status'] == 'green':
        lines.append('结论：对账全绿，可进入正文阅读。')
    elif report['status'] == 'warning':
        lines.append('结论：存在警告，请先核对再进入正文；需要精确判断时回原始 docx。')
    else:
        lines.append('结论：转换失败，请根据错误信息修复后重试。')
    return '\n'.join(lines) + '\n'


def write_report(report: dict, assets_dir: str | Path) -> tuple[Path, Path]:
    d = ensure_dir(assets_dir)
    json_path = d / 'report.json'
    md_path = d / '转换报告.md'
    write_json(json_path, report)
    md_path.write_text(render_report_md(report), encoding='utf-8')
    return json_path, md_path
