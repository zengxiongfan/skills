"""Standalone XLSX/XLS conversion."""
from __future__ import annotations

from pathlib import Path

from . import manifest as manifest_mod
from . import report as report_mod
from . import styles
from . import tables
from .convert_docx import ConversionResult
from .options import Options
from .util import ensure_dir, sha256_file, write_json


def convert_xlsx(
    src: str | Path,
    out_dir: str | Path,
    options: Options,
    base_name: str | None = None,
) -> ConversionResult:
    src = Path(src)
    out_dir = Path(out_dir)
    ensure_dir(out_dir)
    base_name = base_name or src.stem
    assets = ensure_dir(out_dir / f'{base_name}_files')
    tables_dir = assets / 'tables'
    suffix = src.suffix.lower()
    warnings: list[dict] = []
    errors: list[dict] = []
    style_data = None
    sheets = 0

    if suffix == '.xls':
        import xlrd
        wb = xlrd.open_workbook(str(src))
        md_text, table_objs, warns = tables.xlrd_workbook_to_markdown(wb, options.table_format)
        sheets = len(wb.sheet_names())
        warnings.extend({'code': 'table', 'message': w, 'location': ''} for w in warns)
    else:
        from openpyxl import load_workbook
        wb = load_workbook(src, data_only=True)
        md_text, table_objs, warns = tables.workbook_to_markdown(wb, options.table_format)
        sheets = len(wb.sheetnames)
        warnings.extend({'code': 'table', 'message': w, 'location': ''} for w in warns)
        style_data = styles.extract_xlsx_styles(wb)
        if style_data and any(style_data.get('sheets', {}).values()):
            write_json(assets / 'xlsx_styles.json', style_data)
        wb.close()

    md_path = out_dir / f'{base_name}.md'
    md_path.write_text(md_text, encoding='utf-8')

    table_records: list[dict] = []
    for td in table_objs:
        csv_path, json_path = tables.write_table_files(td, tables_dir, f'tbl-{td.index:03d}')
        table_records.append({
            'id': f'tbl-{td.index:03d}',
            'caption': td.caption,
            'rows': len(td.grid),
            'cols': td.col_count,
            'header_rows': td.header_rows,
            'merges': td.merges,
            'format': td.format,
            'csv': f'{base_name}_files/tables/{csv_path.name}',
            'json': f'{base_name}_files/tables/{json_path.name}',
        })

    write_json(tables_dir / 'table_index.json', {
        'tables': [
            {k: r[k] for k in ('id', 'caption', 'rows', 'cols', 'header_rows', 'merges', 'format', 'csv', 'json')}
            for r in table_records
        ]
    })

    style_cells = 0
    if style_data:
        style_cells = sum(len(v.get('cells', [])) + len(v.get('comments', [])) for v in style_data.get('sheets', {}).values())
    output_stats = {
        'sheets': sheets,
        'tables': len(table_records),
        'style_cells': style_cells,
        'images': 0,
        'attachments': 0,
        'chars': len(md_text),
        'exists': True,
    }
    empty_fmt = {k: [] for k in ('colored_runs', 'highlights', 'underlines', 'comments',
                                 'insertions', 'deletions', 'shading', 'hidden', 'strikethrough', 'bold', 'italic')}
    report_obj = report_mod.build_report(
        src.name, None, empty_fmt, [], table_records, output_stats, warnings, errors, kind='xlsx'
    )
    report_mod.write_report(report_obj, assets)
    outline = manifest_mod.build_outline(md_text)
    manifest_mod.write_outline(assets / 'outline.md', outline)
    manifest_obj = manifest_mod.build_manifest(
        src, sha256_file(src), src.stat().st_size, report_obj['status'],
        outline, table_records, [], [], report_obj,
    )
    manifest_mod.write_manifest(assets / 'manifest.json', manifest_obj)
    manifest_mod.write_attachment_index(assets / 'attachment_index.json', [], [])

    return ConversionResult(
        md_path=md_path,
        assets_dir=assets,
        report=report_obj,
        manifest=manifest_obj,
        fmt_index=empty_fmt,
        image_records=[],
        attachment_records=[],
        table_records=table_records,
        warnings=warnings,
        errors=errors,
    )
