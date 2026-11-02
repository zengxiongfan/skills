"""DOCX conversion pipeline: pandoc AST + OOXML sidecars + custom tables."""
from __future__ import annotations

import io
import re
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image

from . import astutil
from . import manifest as manifest_mod
from . import ole
from . import report as report_mod
from . import styles
from . import tables
from .ooxml import DocxPackage
from .options import Options
from .util import ensure_dir, sha256_bytes, sha256_file, unique_stem, write_json


@dataclass
class ConversionResult:
    md_path: Path
    assets_dir: Path
    report: dict
    manifest: dict | None
    fmt_index: dict
    image_records: list
    attachment_records: list
    table_records: list
    warnings: list
    errors: list


def convert_docx(
    src: str | Path,
    out_dir: str | Path,
    options: Options,
    base_name: str | None = None,
    depth: int = 0,
) -> ConversionResult:
    src = Path(src)
    out_dir = Path(out_dir)
    ensure_dir(out_dir)
    base_name = base_name or src.stem
    assets = ensure_dir(out_dir / f'{base_name}_files')
    images_dir = assets / 'images'
    tables_dir = assets / 'tables'

    pkg = DocxPackage(src)
    try:
        stats = pkg.stats()
        used_names: set[str] = set()
        ole_result = ole.extract_attachments(
            pkg, assets, base_name, options,
            image_start=1, used_names=used_names, depth=depth,
        )

        media_tmp = Path(tempfile.mkdtemp(prefix='reqdoc2md_media_'))
        warnings: list[dict] = list(ole_result.warnings)
        errors: list[dict] = []
        try:
            ast = astutil.run_pandoc_json(src, media_tmp)
            image_map, next_idx, image_records, image_warnings = _copy_media(
                media_tmp, images_dir, ole_result, base_name
            )
            warnings.extend(image_warnings)
            ast = astutil.transform_images(
                ast,
                lambda node: _rewrite_image_node(node, image_map, ole_result.by_media, base_name, options),
            )
            if options.heading_number:
                astutil.number_headings(ast)
            table_records, table_warnings = _extract_tables(ast, tables_dir, base_name, pkg, options)
            warnings.extend(table_warnings)
            md_text = astutil.run_pandoc_gfm(ast)
            md_text = _fix_list_hierarchy(md_text)
            md_text = _apply_source_list_levels(md_text, pkg)
            md_text = _replace_placeholders(md_text, table_records)
            md_text = _clean_empty_list_items(md_text)
            md_text = _split_attachment_links(md_text)
            md_text = _append_attachment_section(md_text, ole_result.records, base_name, options)
            md_text = _clean_toc(md_text, options.link_style)
            md_text = _collapse_blank_lines(md_text)
            md_path = out_dir / f'{base_name}.md'
            md_path.write_text(md_text, encoding='utf-8')
        finally:
            if not options.keep_temp:
                shutil.rmtree(media_tmp, ignore_errors=True)

        fmt_index = styles.extract_format_index(src)
        image_records = _reconcile_images(images_dir, base_name, image_records)
        output_stats = {
            'images': len(image_records),
            'attachments': len(ole_result.records),
            'tables': len(table_records),
            'exists': True,
            'chars': len(md_text),
        }
        report_obj = report_mod.build_report(
            src.name, stats, fmt_index, ole_result.records, table_records,
            output_stats, warnings, errors, kind='docx',
        )

        manifest_obj = None
        if not options.nested:
            styles.write_style_files(fmt_index, assets, f'正文：{base_name}')
            report_mod.write_report(report_obj, assets)
            outline = manifest_mod.build_outline(md_text)
            manifest_mod.write_outline(assets / 'outline.md', outline)
            manifest_obj = manifest_mod.build_manifest(
                src, sha256_file(src), src.stat().st_size, report_obj['status'],
                outline, table_records, ole_result.records, image_records, report_obj,
            )
            manifest_mod.write_manifest(assets / 'manifest.json', manifest_obj)
            manifest_mod.write_attachment_index(
                assets / 'attachment_index.json', ole_result.records, image_records
            )

        return ConversionResult(
            md_path=md_path,
            assets_dir=assets,
            report=report_obj,
            manifest=manifest_obj,
            fmt_index=fmt_index,
            image_records=image_records,
            attachment_records=ole_result.records,
            table_records=table_records,
            warnings=warnings,
            errors=errors,
        )
    finally:
        pkg.close()


def _reconcile_images(images_dir: Path, base_name: str, records: list[dict]) -> list[dict]:
    """Include images merged from nested docx in the manifest image list."""
    if not images_dir.exists():
        return records
    known = {Path(r.get('path', '')).name for r in records if r.get('path')}
    out = list(records)
    for f in sorted(images_dir.iterdir()):
        if not f.is_file() or f.name in known:
            continue
        out.append({
            'id': f'img-{len(out) + 1:03d}',
            'media': '',
            'path': f'{base_name}_files/images/{f.name}',
            'alt': '',
            'nested': True,
        })
    return out


def _copy_media(media_tmp: Path, images_dir: Path, ole_result, base_name: str):
    media_dir = Path(media_tmp) / 'media'
    image_map: dict[str, str] = {}
    records = list(ole_result.image_records)
    warnings: list[dict] = []
    idx = ole_result.next_image_idx
    if not media_dir.exists():
        return image_map, idx, records, warnings
    ensure_dir(images_dir)
    for f in sorted(media_dir.iterdir()):
        if not f.is_file():
            continue
        name = f.name
        if name in ole_result.by_media or name in image_map:
            continue
        suffix = f.suffix.lower()
        new_name = f'image_{idx}{suffix}'
        try:
            if suffix == '.emf':
                img = Image.open(f)
                new_name = f'image_{idx}.png'
                img.save(images_dir / new_name, format='PNG')
            else:
                shutil.copy2(f, images_dir / new_name)
        except Exception as exc:
            new_name = f'image_{idx}{suffix}'
            shutil.copy2(f, images_dir / new_name)
            warnings.append({'code': 'image_convert', 'message': f'图片转换失败 {name}: {exc}', 'location': new_name})
        rel = f'{base_name}_files/images/{new_name}'
        image_map[name] = rel
        records.append({
            'id': f'img-{len(records) + 1:03d}',
            'media': name,
            'path': rel,
            'alt': '',
        })
        idx += 1
    return image_map, idx, records, warnings


def _rewrite_image_node(node: dict, image_map: dict, by_media: dict, base_name: str, options: Options) -> dict:
    c = node.get('c') or []
    if len(c) < 3:
        return node
    alt_inlines = c[1] if len(c) > 1 else []
    alt = astutil.plain_text(alt_inlines).strip()
    src = str(c[2][0]) if c[2] else ''
    title = c[2][1] if len(c[2]) > 1 else ''
    name = Path(src.replace('\\', '/')).name
    rec = by_media.get(name)
    if rec:
        if rec.get('is_image'):
            new_alt = alt_inlines or [{'t': 'Str', 'c': rec.get('original_name') or '图片'}]
            return {'t': 'Image', 'c': [c[0], new_alt, [rec['saved_rel'], title]]}
        label = rec.get('display_name') or rec.get('original_name') or alt or '附件'
        target = rec.get('md_rel') or rec.get('saved_rel') or ''
        if not target:
            return node
        if options.link_style == 'obsidian':
            target_noext = re.sub(r'\.md$', '', target)
            return {'t': 'RawInline', 'c': ['gfm', f'[[{target_noext}]]']}
        return {
            't': 'Link',
            'c': [['', [], []], [{'t': 'Str', 'c': f'📎 {label}'}], [target, '']],
        }
    if name in image_map:
        return {'t': 'Image', 'c': [c[0], alt_inlines, [image_map[name], title]]}
    return node


def _extract_tables(ast: dict, tables_dir: Path, base_name: str, pkg: DocxPackage, options: Options):
    records: list[dict] = []
    warnings: list[dict] = []
    metas = pkg.iter_tables()
    counter = [0]

    def collector(node: dict) -> str:
        counter[0] += 1
        i = counter[0]
        meta = metas[i - 1] if i - 1 < len(metas) else None
        if meta is not None:
            header_rows = meta.header_rows if meta.header_rows > 0 else (1 if meta.rows > 1 else 0)
        else:
            header_rows = 1
        td = tables.from_ast_table(node, i, header_rows=header_rows)
        if meta is not None and not td.caption:
            td.caption = meta.caption
        md, fmt, warns = tables.render_table(td, options.table_format)
        warnings.extend({'code': 'table', 'message': w, 'location': f'tbl-{i:03d}'} for w in warns)
        csv_path, json_path = tables.write_table_files(td, tables_dir, f'tbl-{i:03d}')
        placeholder = f'ZCODETABLE{i:04d}Z'
        td.placeholder = placeholder
        records.append({
            'id': f'tbl-{i:03d}',
            'caption': td.caption,
            'rows': len(td.grid),
            'cols': td.col_count,
            'header_rows': td.header_rows,
            'merges': td.merges,
            'format': fmt,
            'csv': f'{base_name}_files/tables/{csv_path.name}',
            'json': f'{base_name}_files/tables/{json_path.name}',
            'placeholder': placeholder,
            'markdown': md,
            'warnings': warns,
        })
        return placeholder

    astutil.replace_tables_in_blocks(ast.get('blocks') or [], collector)
    write_json(tables_dir / 'table_index.json', {
        'tables': [
            {k: r[k] for k in ('id', 'caption', 'rows', 'cols', 'header_rows', 'merges', 'format', 'csv', 'json')}
            for r in records
        ]
    })
    if len(records) != len(metas):
        warnings.append({
            'code': 'table_count',
            'message': f'OOXML 表格数 {len(metas)} 与 AST 顶层表格数 {len(records)} 不一致，嵌套表/文本框可能未进入正文',
        })
    return records, warnings


def _replace_placeholders(md_text: str, records: list[dict]) -> str:
    if not records:
        return md_text
    by_ph = {r['placeholder']: r for r in records}
    out: list[str] = []
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped in by_ph:
            rec = by_ph[stripped]
            if rec.get('format') == 'empty':
                # empty layout tables are source artefacts; do not emit "(空表)"
                continue
            out.extend(['', rec.get('markdown') or '', ''])
            continue
        for ph, rec in by_ph.items():
            if ph in line:
                if rec.get('format') == 'empty':
                    line = line.replace(ph, '')
                else:
                    line = line.replace(ph, f"\n\n{rec.get('markdown') or ''}\n\n")
        out.append(line)
    return '\n'.join(out)


def _fix_list_hierarchy(md_text: str) -> str:
    """Pandoc emits nested Word lists as flat items separated by ``<!-- -->``.

    The HTML comment marks "the following items are children of the previous
    item"; indent them before the comments are removed.
    """
    lines = md_text.splitlines()
    out: list[str] = []
    indent_next = False
    for line in lines:
        stripped = line.strip()
        if stripped == '<!-- -->':
            for prev in reversed(out[-5:]):
                prev_stripped = prev.strip()
                if not prev_stripped:
                    continue
                if prev_stripped.startswith('-') or re.match(r'^\d+\.', prev_stripped):
                    indent_next = True
                break
            continue
        if stripped.startswith('-') or re.match(r'^\d+\.', stripped):
            if indent_next:
                existing = len(line) - len(line.lstrip())
                line = ' ' * (existing + 4) + line.lstrip()
        elif stripped:
            indent_next = False
        out.append(line)
    return '\n'.join(out)


def _apply_source_list_levels(md_text: str, pkg: DocxPackage) -> str:
    """Use Word's numbering left-indents to restore list levels in Markdown.

    Pandoc often emits separate Word lists as flat sibling lists; the visual
    hierarchy is encoded in ``word/numbering.xml`` left indents (e.g. 425 /
    840 / 1260 twips), not in ``w:ilvl``.
    """
    items = pkg.iter_list_items()
    if not items:
        return md_text

    def key(text: str) -> str:
        text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)
        text = re.sub(r'\[[^\]]*\]\([^)]*\)', ' ', text)
        return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', text)[:30]

    lines = md_text.splitlines()
    cursor = 0
    region: list[tuple[int, int]] = []  # (line index, Word left indent)

    def flush(region_items: list[tuple[int, int]]) -> None:
        if not region_items:
            return
        values = sorted({left for _, left in region_items})
        mapping: dict[int, int] = {}
        level = -1
        prev = None
        for value in values:
            if prev is None or value - prev >= 200:
                level += 1
            mapping[value] = level
            prev = value
        for line_idx, left in region_items:
            lines[line_idx] = ' ' * (max(0, mapping.get(left, 0)) * 4) + lines[line_idx].lstrip()

    for i, line in enumerate(lines):
        if re.match(r'^#{1,6}\s', line):
            flush(region)
            region = []
            continue
        m = re.match(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$', line)
        if not m:
            continue
        current_key = key(m.group(3))
        if not current_key:
            continue
        found = None
        for j in range(cursor, min(len(items), cursor + 12)):
            item_key = key(items[j]['text'])
            if item_key and (
                item_key.startswith(current_key[:12])
                or current_key.startswith(item_key[:12])
            ):
                found = items[j]
                cursor = j + 1
                break
        if found is not None:
            region.append((i, found['left']))
    flush(region)
    return '\n'.join(lines)


def _clean_empty_list_items(md_text: str) -> str:
    """Drop empty list markers and renumber the following ordered items.

    Word documents sometimes contain an empty numbered paragraph followed by an
    empty layout table; rendering it leaves a bare ``1.`` + ``(空表)`` and pushes
    the real item to ``2.``.
    """
    out: list[str] = []
    pending_old: int | None = None
    shift = 0
    for line in md_text.splitlines():
        empty = re.match(r'^(\s*)([-*+]|(\d+)[.)])\s*$', line)
        if empty:
            if empty.group(3):
                pending_old = int(empty.group(3)) + 1
                shift += 1
            continue
        m = re.match(r'^(\s*)(\d+)([.)])(\s+.*)$', line)
        if m and pending_old is not None:
            number = int(m.group(2))
            if number == pending_old:
                new_number = number - shift
                if new_number >= 1:
                    line = f'{m.group(1)}{new_number}{m.group(3)}{m.group(4)}'
                pending_old = number + 1
            else:
                pending_old = None
                shift = 0
        out.append(line)
    return '\n'.join(out)


def _collapse_blank_lines(md_text: str) -> str:
    """Limit runs of blank lines outside fenced code blocks."""
    out: list[str] = []
    blank = 0
    fence = ''
    for line in md_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            marker = stripped[:3]
            if not fence:
                fence = marker
            elif marker == fence:
                fence = ''
        if not fence and not line.strip():
            blank += 1
            if blank <= 2:
                out.append('')
        else:
            blank = 0
            out.append(line)
    return '\n'.join(out)


_ATTACHMENT_LINK_RE = re.compile(
    r'\[📎[^\]]*\]\([^)\n]+\)'
    r'|\[\[[^\]]*_files/attachments/[^\]]*\]\]'
)


def _split_attachment_links(md_text: str) -> str:
    """Put multiple attachment links on one source line onto separate lines."""
    out: list[str] = []
    for line in md_text.splitlines():
        if '<td' in line or '<table' in line:
            out.append(line)
            continue
        links = list(_ATTACHMENT_LINK_RE.finditer(line))
        if len(links) < 2:
            out.append(line)
            continue
        prefix = line[:links[0].start()].rstrip()
        suffix = line[links[-1].end():].strip()
        indent = re.match(r'^\s*', line).group(0)
        parts: list[str] = []
        marker = re.match(r'^\s*([-*+]|\d+[.)])\s*$', prefix)
        if marker:
            parts.append(f"{prefix} {links[0].group(0)}")
            continuation = indent + '  '
            parts.extend(continuation + link.group(0) for link in links[1:])
        else:
            if prefix:
                parts.append(prefix)
            parts.extend(indent + link.group(0) for link in links)
        if suffix:
            parts.append(indent + suffix)
        out.extend(parts)
    return '\n'.join(out)


def _clean_toc(md_text: str, link_style: str) -> str:
    """Turn Word's nested TOC links into plain anchors and drop pandoc list comments."""
    pattern = re.compile(r'^\[([\d\.\s]+)([^\[]+?)\s+\[[^\]]+\]\(#([^)]+)\)\]\(#([^)]+)\)\s*$', re.M)

    def repl(m):
        number = m.group(1).strip()
        title = m.group(2).strip()
        anchor = (m.group(3) or m.group(4)).strip()
        if link_style == 'obsidian':
            return f'[[#{number} {title}]]'
        return f'[{number} {title}](#{anchor})'

    text = pattern.sub(repl, md_text)
    text = re.sub(r'^\s*<!--\s*-->\s*$', '', text, flags=re.M)
    return text


def _append_attachment_section(md_text: str, records: list[dict], base_name: str, options: Options) -> str:
    if not records or '## 附件清单' in md_text:
        return md_text
    lines = ['', '## 附件清单', '']
    for rec in records:
        label = (rec.get('display_name') or rec.get('original_name') or rec.get('saved_name') or '附件').replace('[', '(').replace(']', ')')
        target = rec.get('md_rel') or rec.get('saved_rel')
        if not target:
            continue
        if options.link_style == 'obsidian':
            target_noext = re.sub(r'\.md$', '', target)
            line = f'- [[{target_noext}]]'
        else:
            line = f'- [📎 {label}]({target})'
        if rec.get('md_rel') and rec.get('saved_rel') and rec.get('saved_rel') != rec.get('md_rel'):
            if options.link_style == 'obsidian':
                original_noext = re.sub(r'\.[^.\\/]+$', '', rec['saved_rel'])
                line += f'（原件：[[{original_noext}]]）'
            else:
                line += f'（原件：[{rec.get("saved_name")}]({rec["saved_rel"]})）'
        lines.append(line)
    return md_text.rstrip() + '\n' + '\n'.join(lines) + '\n'


def convert_docx_bytes_to_md(
    data: bytes,
    parent_assets_dir: str | Path,
    parent_base_name: str,
    options: Options,
    image_idx: int,
    depth: int,
    used_names: set[str],
) -> tuple[str, int]:
    """Convert an embedded docx and merge its images/attachments into the parent."""
    parent_assets = Path(parent_assets_dir)
    tmp_dir = Path(tempfile.mkdtemp(prefix='reqdoc2md_nested_'))
    try:
        tmp_docx = tmp_dir / 'att.docx'
        tmp_docx.write_bytes(data)
        tmp_out = tmp_dir / 'out'
        nested_opts = replace(options, nested=True)
        result = convert_docx(tmp_docx, tmp_out, nested_opts, base_name='att', depth=depth)
        md_text = result.md_path.read_text(encoding='utf-8')
        md_text = md_text.replace('## 附件清单', '### 附件清单（嵌套文档）')
        child_assets = result.assets_dir
        parent_images = ensure_dir(parent_assets / 'images')
        parent_attachments = ensure_dir(parent_assets / 'attachments')

        child_images = child_assets / 'images'
        if child_images.exists():
            for img in sorted(child_images.iterdir()):
                if not img.is_file():
                    continue
                new_name = f'image_{image_idx}{img.suffix}'
                shutil.copy2(img, parent_images / new_name)
                new_rel = f'{parent_base_name}_files/images/{new_name}'
                md_text = md_text.replace(f'att_files/images/{img.name}', new_rel)
                image_idx += 1

        child_attachments = child_assets / 'attachments'
        if child_attachments.exists():
            groups: dict[str, list[Path]] = {}
            for att in sorted(child_attachments.iterdir()):
                if not att.is_file():
                    continue
                if att.name.endswith('.styles.json'):
                    base = att.name[:-len('.styles.json')]
                else:
                    base = att.stem
                groups.setdefault(base, []).append(att)
            hash_to_base: dict[str, str] = {}
            for base, files in sorted(groups.items()):
                main = next(
                    (f for f in files if not f.name.endswith('.md') and not f.name.endswith('.styles.json')),
                    files[0],
                )
                digest = sha256_bytes(main.read_bytes())
                new_base = hash_to_base.get(digest)
                if new_base is None:
                    new_base = unique_stem(base, used_names)
                    hash_to_base[digest] = new_base
                    for f in files:
                        new_name = f'{new_base}.styles.json' if f.name.endswith('.styles.json') else f'{new_base}{f.suffix}'
                        shutil.copy2(f, parent_attachments / new_name)
                for f in files:
                    new_name = f'{new_base}.styles.json' if f.name.endswith('.styles.json') else f'{new_base}{f.suffix}'
                    new_rel = f'{parent_base_name}_files/attachments/{new_name}'
                    md_text = md_text.replace(f'att_files/attachments/{f.name}', new_rel)
                    if f.suffix == '.md':
                        md_text = md_text.replace(
                            f'att_files/attachments/{f.stem}',
                            re.sub(r'\.md$', '', new_rel),
                        )

        fmt_md = styles.format_index_as_md(result.fmt_index, f'附件样式标注（{tmp_docx.stem}）')
        if fmt_md:
            md_text = md_text.rstrip() + '\n\n---\n\n' + fmt_md + '\n'
        return md_text, image_idx
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def convert_doc_bytes_to_docx(data: bytes, original_name: str) -> bytes:
    """Convert legacy .doc bytes to .docx via Word COM, with LibreOffice fallback."""
    tmp_dir = Path(tempfile.mkdtemp(prefix='reqdoc2md_doc_'))
    try:
        doc_path = tmp_dir / (Path(original_name).stem + '.doc')
        docx_path = tmp_dir / (Path(original_name).stem + '.docx')
        doc_path.write_bytes(data)
        errors: list[str] = []
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            word = win32com.client.DispatchEx('Word.Application')
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
            except Exception:
                pass
            try:
                doc = word.Documents.Open(str(doc_path), ReadOnly=True, AddToRecentFiles=False, Visible=False)
                doc.SaveAs2(str(docx_path), FileFormat=16)
                doc.Close(False)
            finally:
                word.Quit()
            if docx_path.exists():
                return docx_path.read_bytes()
        except Exception as exc:
            errors.append(f'Word COM: {exc}')
        soffice = shutil.which('soffice') or shutil.which('libreoffice')
        if soffice:
            try:
                import subprocess
                subprocess.run([soffice, '--headless', '--convert-to', 'docx', '--outdir', str(tmp_dir), str(doc_path)],
                               capture_output=True, timeout=180)
                if docx_path.exists():
                    return docx_path.read_bytes()
            except Exception as exc:
                errors.append(f'LibreOffice: {exc}')
        raise RuntimeError('; '.join(errors) or '无法转换 .doc')
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def convert_doc(src: str | Path, out_dir: str | Path, options: Options) -> ConversionResult:
    src = Path(src)
    data = convert_doc_bytes_to_docx(src.read_bytes(), src.name)
    tmp_dir = Path(tempfile.mkdtemp(prefix='reqdoc2md_doc_out_'))
    try:
        tmp_docx = tmp_dir / f'{src.stem}.docx'
        tmp_docx.write_bytes(data)
        return convert_docx(tmp_docx, out_dir, options, base_name=src.stem)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
