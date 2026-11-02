"""PDF conversion: MarkItDown text + conservative heading detection."""
from __future__ import annotations

import re
from pathlib import Path

from . import manifest as manifest_mod
from . import report as report_mod
from .convert_docx import ConversionResult
from .options import Options
from .util import ensure_dir, sha256_file


def convert_pdf(
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
    warnings: list[dict] = []
    errors: list[dict] = []
    try:
        from markitdown import MarkItDown
        result = MarkItDown().convert(str(src))
        text = result.text_content or ''
    except Exception as exc:
        raise RuntimeError(f'PDF 读取失败（需要 markitdown）: {exc}') from exc

    lines: list[str] = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            lines.append('')
            continue
        if re.match(r'^第[一二三四五六七八九十百零\d]+章', stripped):
            lines.append(f'# {stripped}')
        elif re.match(r'^第[一二三四五六七八九十百零\d]+条', stripped):
            lines.append(f'## {stripped}')
        elif re.match(r'^[一二三四五六七八九十]+、', stripped) and len(stripped) < 60:
            lines.append(f'### {stripped}')
        elif re.match(r'^（[一二三四五六七八九十]+）', stripped) and len(stripped) < 60:
            lines.append(f'#### {stripped}')
        else:
            lines.append(stripped)
    text = '\n'.join(lines)
    text = re.sub(r'\n\d+\n', '\n', text)
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')

    if not text.strip():
        warnings.append({'code': 'pdf_empty', 'message': 'PDF 未提取到文本，可能是扫描件'})
    else:
        warnings.append({'code': 'pdf_tables', 'message': 'PDF 表格不会做结构化拆分；需要精确表格时回原 PDF 或源文件'})
    md_path = out_dir / f'{base_name}.md'
    md_path.write_text(text, encoding='utf-8')

    empty_fmt = {k: [] for k in ('colored_runs', 'highlights', 'underlines', 'comments',
                                 'insertions', 'deletions', 'shading', 'hidden', 'strikethrough', 'bold', 'italic')}
    output_stats = {'chars': len(text), 'images': 0, 'attachments': 0, 'tables': 0, 'exists': True}
    report_obj = report_mod.build_report(
        src.name, None, empty_fmt, [], [], output_stats, warnings, errors, kind='pdf'
    )
    report_mod.write_report(report_obj, assets)
    outline = manifest_mod.build_outline(text)
    manifest_mod.write_outline(assets / 'outline.md', outline)
    manifest_obj = manifest_mod.build_manifest(
        src, sha256_file(src), src.stat().st_size, report_obj['status'],
        outline, [], [], [], report_obj,
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
        table_records=[],
        warnings=warnings,
        errors=errors,
    )
