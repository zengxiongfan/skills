#!/usr/bin/env python
"""reqdoc2md: convert requirement documents to AI-readable Markdown + indexes."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core.convert_docx import convert_doc, convert_docx  # noqa: E402
from core.convert_pdf import convert_pdf  # noqa: E402
from core.convert_xlsx import convert_xlsx  # noqa: E402
from core.options import Options  # noqa: E402

VERSION = '0.1.0'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='reqdoc2md',
        description='把需求文档（doc/docx/xlsx/xls/pdf）转换为 AI 可读的 Markdown，并生成表格/附件/样式索引。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python reqdoc2md.py 需求说明书.docx
  python reqdoc2md.py 需求说明书.docx -o ./out
  python reqdoc2md.py 需求说明书.doc --link-style standard
  python reqdoc2md.py 附件.xlsx --table-format html
        ''',
    )
    parser.add_argument('input_file', help='输入文件（doc/docx/xlsx/xls/pdf）')
    parser.add_argument('-o', '--output', help='输出目录（默认与输入文件同目录）')
    parser.add_argument('--link-style', choices=('obsidian', 'standard'), default='obsidian',
                        help='链接风格：obsidian=[[双链]]（默认），standard=标准 Markdown')
    parser.add_argument('--table-format', choices=('auto', 'pipe', 'html'), default='auto',
                        help='表格输出：auto=简单表 pipe、复杂表 HTML')
    parser.add_argument('--no-heading-number', action='store_true', help='不自动给标题加 1/1.1 编号')
    parser.add_argument('--strict', action='store_true', help='有警告时也返回非零退出码')
    parser.add_argument('--keep-temp', action='store_true', help='保留 pandoc 临时媒体目录')
    parser.add_argument('--version', action='version', version=f'reqdoc2md {VERSION}')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f'文件不存在: {input_path}', file=sys.stderr)
        return 1
    suffix = input_path.suffix.lower()
    out_dir = Path(args.output) if args.output else input_path.parent
    options = Options(
        link_style=args.link_style,
        table_format=args.table_format,
        heading_number=not args.no_heading_number,
        strict=args.strict,
        keep_temp=args.keep_temp,
    )

    try:
        if suffix == '.docx':
            result = convert_docx(input_path, out_dir, options)
        elif suffix == '.doc':
            result = convert_doc(input_path, out_dir, options)
        elif suffix in ('.xlsx', '.xls'):
            result = convert_xlsx(input_path, out_dir, options)
        elif suffix == '.pdf':
            result = convert_pdf(input_path, out_dir, options)
        else:
            print(f'不支持的文件格式: {suffix}', file=sys.stderr)
            print('支持: .doc, .docx, .xlsx, .xls, .pdf', file=sys.stderr)
            return 1
    except Exception as exc:
        print(f'转换失败: {exc}', file=sys.stderr)
        return 1

    status = result.report.get('status', 'failed')
    label = {'green': 'GREEN', 'warning': 'WARNING', 'failed': 'FAILED'}.get(status, status)
    print('')
    print('转换完成')
    print(f'  状态: {label}')
    print(f'  MD: {result.md_path}')
    print(f'  产物: {result.assets_dir}')
    print(f"  表格: {len(result.table_records)} | 附件: {len(result.attachment_records)} | 图片: {len(result.image_records)} | 警告: {len(result.warnings)}")
    if (result.assets_dir / '转换报告.md').exists():
        print(f"  报告: {result.assets_dir / '转换报告.md'}")
    if status == 'failed':
        return 1
    if status == 'warning' and args.strict:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
