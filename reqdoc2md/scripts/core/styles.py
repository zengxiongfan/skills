"""Format / revision / comment indexes that Markdown cannot carry."""
from __future__ import annotations

import io
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .ooxml import W
from .util import ensure_dir, write_json

_COLOR_NAMES = {
    'FF0000': '红色', 'C00000': '深红色', 'FFC000': '橙色', 'ED7D31': '橙色',
    '0000FF': '蓝色', '0070C0': '蓝色', '002060': '深蓝色', '00B0F0': '浅蓝色',
    '00B050': '绿色', '006100': '深绿色', 'FFFF00': '黄色', 'BF9000': '深黄色',
    '7030A0': '紫色', '808080': '灰色', 'A6A6A6': '浅灰色',
    'FFFFFF': '白色', '000000': '黑色',
}


def _docx_zip(source):
    if isinstance(source, (bytes, bytearray)):
        return zipfile.ZipFile(io.BytesIO(source))
    return zipfile.ZipFile(str(source))


def _para_locations(root) -> dict[int, dict]:
    locations: dict[int, dict] = {}
    for ti, tbl in enumerate(root.iter(W + 'tbl'), 1):
        for ri, tr in enumerate(tbl.findall(W + 'tr'), 1):
            for ci, tc in enumerate(tr.findall(W + 'tc'), 1):
                for p in tc.iter(W + 'p'):
                    locations[id(p)] = {'table': ti, 'row': ri, 'cell': ci}
    return locations


def extract_format_index(source) -> dict:
    result = {
        'colored_runs': [],
        'highlights': [],
        'underlines': [],
        'comments': [],
        'insertions': [],
        'deletions': [],
        'shading': [],
        'hidden': [],
        'strikethrough': [],
        'bold': [],
        'italic': [],
    }
    try:
        z = _docx_zip(source)
        names = z.namelist()
        if 'word/document.xml' not in names:
            return result
        root = ET.fromstring(z.read('word/document.xml'))
    except Exception:
        return result

    locations = _para_locations(root)

    # comment anchors
    comment_anchor: dict[str, str] = {}
    open_ids: list[str] = []
    for elem in root.iter():
        if elem.tag == W + 'commentRangeStart':
            cid = elem.get(W + 'id')
            if cid:
                open_ids.append(cid)
                comment_anchor.setdefault(cid, '')
        elif elem.tag == W + 'commentRangeEnd':
            cid = elem.get(W + 'id')
            try:
                open_ids.remove(cid)
            except ValueError:
                pass
        elif elem.tag == W + 't' and open_ids and elem.text:
            for cid in open_ids:
                comment_anchor[cid] = (comment_anchor.get(cid, '') + elem.text)[-100:]

    # revisions
    for elem in root.iter(W + 'ins'):
        text = ''.join(t.text or '' for t in elem.iter(W + 't')).strip()
        if text:
            result['insertions'].append({
                'author': elem.get(W + 'author', ''),
                'date': elem.get(W + 'date', ''),
                'text': text[:100],
            })
    for elem in root.iter(W + 'del'):
        text = ''.join(t.text or '' for t in elem.iter(W + 'delText')).strip()
        if text:
            result['deletions'].append({
                'author': elem.get(W + 'author', ''),
                'date': elem.get(W + 'date', ''),
                'text': text[:100],
            })

    # table-cell shading (very common for "changed/attention" markers)
    for ti, tbl in enumerate(root.iter(W + 'tbl'), 1):
        for ri, tr in enumerate(tbl.findall(W + 'tr'), 1):
            for ci, tc in enumerate(tr.findall(W + 'tc'), 1):
                tc_pr = tc.find(W + 'tcPr')
                if tc_pr is None:
                    continue
                shd = tc_pr.find(W + 'shd')
                if shd is None:
                    continue
                fill = (shd.get(W + 'fill') or '').strip()
                if not fill or fill.lower() in ('auto', 'ffffff'):
                    continue
                text = ''.join(t.text or '' for t in tc.iter(W + 't')).strip()
                if not text:
                    continue
                result['shading'].append({
                    'table': ti, 'row': ri, 'cell': ci,
                    'text': text[:60],
                    'fill': fill,
                })

    # paragraph / run scan
    para_idx = 0
    for p in root.iter(W + 'p'):
        para_idx += 1
        para_text = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        loc = locations.get(id(p), {})
        ppr = p.find(W + 'pPr')
        if ppr is not None:
            shd = ppr.find(W + 'shd')
            if shd is not None:
                fill = (shd.get(W + 'fill') or '').strip()
                if fill and fill.lower() not in ('auto', 'ffffff'):
                    result['shading'].append({
                        'para': para_idx,
                        'text': para_text[:60],
                        'context': para_text[:40],
                        'fill': fill,
                        **loc,
                    })
        for r in p.iter(W + 'r'):
            rpr = r.find(W + 'rPr')
            if rpr is None:
                continue
            text = ''.join(t.text or '' for t in r.iter(W + 't')).strip()
            if not text:
                continue
            entry = {
                'para': para_idx,
                'text': text[:60],
                'context': para_text[:40],
                **loc,
            }
            color_el = rpr.find(W + 'color')
            if color_el is not None:
                val = (color_el.get(W + 'val') or '').strip()
                if not val or val.lower() == 'auto':
                    theme = (color_el.get(W + 'themeColor') or '').strip()
                    val = f'theme:{theme}' if theme else ''
                if val and val.lower() != 'auto':
                    result['colored_runs'].append(dict(entry, color=val.upper() if not val.startswith('theme:') else val))
            hl = rpr.find(W + 'highlight')
            if hl is not None:
                val = (hl.get(W + 'val') or '').strip()
                if val and val.lower() != 'none':
                    result['highlights'].append(dict(entry, color=val))
            u = rpr.find(W + 'u')
            if u is not None:
                val = (u.get(W + 'val') or '').strip()
                if val and val.lower() != 'none':
                    result['underlines'].append(dict(entry))
            if rpr.find(W + 'vanish') is not None:
                result['hidden'].append(dict(entry))
            if rpr.find(W + 'strike') is not None or rpr.find(W + 'dstrike') is not None:
                result['strikethrough'].append(dict(entry))

            def enabled(tag: str) -> bool:
                el = rpr.find(W + tag)
                if el is None:
                    return False
                return (el.get(W + 'val') or '').strip().lower() not in ('0', 'false', 'off')

            if enabled('b') or enabled('bCs'):
                result['bold'].append(dict(entry))
            if enabled('i') or enabled('iCs'):
                result['italic'].append(dict(entry))
            shd = rpr.find(W + 'shd')
            if shd is not None:
                fill = (shd.get(W + 'fill') or '').strip()
                if fill and fill.lower() not in ('auto', 'ffffff'):
                    result['shading'].append(dict(entry, fill=fill))

    # comments
    if 'word/comments.xml' in names:
        try:
            croot = ET.fromstring(z.read('word/comments.xml'))
            for c in croot.iter(W + 'comment'):
                cid = c.get(W + 'id')
                text = ''.join(t.text or '' for t in c.iter(W + 't')).strip()
                if not text:
                    continue
                result['comments'].append({
                    'id': cid,
                    'author': c.get(W + 'author', ''),
                    'date': c.get(W + 'date', ''),
                    'done': c.get(W + 'done', ''),
                    'text': text[:300],
                    'anchor': (comment_anchor.get(cid, '') or '')[:100],
                })
        except Exception:
            pass

    return result


def _location_text(entry: dict) -> str:
    if entry.get('table'):
        return f"表{entry['table']} 行{entry['row']} 单元格{entry['cell']}"
    return f"段落{entry.get('para', '?')}"


def format_index_as_md(index: dict, title: str) -> str | None:
    if not any(index.values()):
        return None
    lines = [
        f'# {title}',
        '',
        '> 由 reqdoc2md 自动生成：以下文字带有 markdown 无法承载的直接格式'
        '（颜色/高亮/下划线/底纹），或文档包含批注/修订。',
        '> 阅读转换产物时请结合本索引；需要精确核对时回原始 docx。',
        '',
    ]
    if index['colored_runs']:
        lines.append('## 文字颜色')
        by_color: dict[str, list] = {}
        for r in index['colored_runs']:
            by_color.setdefault(r['color'], []).append(r)
        for color in sorted(by_color):
            runs = by_color[color]
            name = _COLOR_NAMES.get(color)
            head = f'### {color}（{name}）' if name else f'### {color}'
            lines += ['', f'{head} — {len(runs)} 处']
            for r in runs:
                lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index['highlights']:
        lines.append('## 高亮（底色）')
        by_color: dict[str, list] = {}
        for r in index['highlights']:
            by_color.setdefault(r['color'], []).append(r)
        for color in sorted(by_color):
            runs = by_color[color]
            lines += ['', f'### {color} — {len(runs)} 处']
            for r in runs:
                lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index['underlines']:
        lines.append('## 下划线')
        for r in index['underlines']:
            lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index['shading']:
        lines.append('## 底纹（单元格/段落底色）')
        for r in index['shading']:
            lines.append(f"- {_location_text(r)}：「{r['text']}」 底色 {r['fill']}")
        lines.append('')
    if index['hidden']:
        lines.append('## 隐藏文字')
        for r in index['hidden']:
            lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index['strikethrough']:
        lines.append('## 删除线')
        for r in index['strikethrough']:
            lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index.get('bold'):
        lines.append('## 加粗')
        for r in index['bold']:
            lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index.get('italic'):
        lines.append('## 斜体')
        for r in index['italic']:
            lines.append(f"- {_location_text(r)}：「{r['text']}」")
        lines.append('')
    if index['comments']:
        lines.append('## 批注')
        for c in index['comments']:
            anchor = f"「{c['anchor']}」" if c.get('anchor') else ''
            done = '（已解决）' if str(c.get('done', '')).lower() in ('1', 'true') else ''
            lines.append(f"- {anchor}{c['text']}（{c['author']} {c['date']}）{done}")
        lines.append('')
    if index['insertions'] or index['deletions']:
        lines.append('## 修订（track changes，pandoc 转换时按“接受”处理，此处仅记录）')
        for r in index['insertions']:
            lines.append(f"- 插入：「{r['text']}」（{r['author']} {r['date']}）")
        for r in index['deletions']:
            lines.append(f"- 删除：「{r['text']}」（{r['author']} {r['date']}）")
        lines.append('')
    return '\n'.join(lines)


def write_style_files(index: dict, out_dir: str | Path, source_label: str) -> tuple[Path | None, Path | None]:
    text = format_index_as_md(index, f'样式标注（{source_label}）')
    if text is None:
        return None, None
    d = ensure_dir(out_dir)
    md_path = d / '样式标注.md'
    json_path = d / 'styles.json'
    md_path.write_text(text, encoding='utf-8')
    write_json(json_path, index)
    return md_path, json_path


# ---------- Excel cell styles ----------

def _value_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    return str(value).replace('\n', ' ')[:80]


def extract_xlsx_styles(wb, max_cells: int = 5000) -> dict:
    result = {
        'sheets': {},
        'counts': {'font_color': 0, 'fill_color': 0, 'bold': 0, 'italic': 0, 'underline': 0, 'strike': 0, 'comments': 0},
        'truncated': False,
    }
    try:
        from openpyxl.utils import get_column_letter
    except Exception:
        return result
    total = 0
    for ws in wb.worksheets:
        cells = []
        comments = []
        max_row = min(int(ws.max_row or 0), 2000)
        max_col = min(int(ws.max_column or 0), 200)
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                if total >= max_cells:
                    result['truncated'] = True
                    break
                font = cell.font
                fill = cell.fill
                font_color = None
                if font and font.color:
                    if getattr(font.color, 'type', None) == 'rgb' and font.color.rgb:
                        rgb = str(font.color.rgb).upper()
                        if rgb not in ('FF000000', '00000000', 'FFFFFFFF'):
                            font_color = rgb
                    elif getattr(font.color, 'type', None) == 'theme' and font.color.theme is not None:
                        font_color = f'theme:{font.color.theme}'
                fill_color = None
                if fill and fill.patternType and fill.fgColor:
                    if getattr(fill.fgColor, 'type', None) == 'rgb' and fill.fgColor.rgb:
                        rgb = str(fill.fgColor.rgb).upper()
                        if rgb not in ('FF000000', '00000000', 'FFFFFFFF'):
                            fill_color = rgb
                    elif getattr(fill.fgColor, 'type', None) == 'theme' and fill.fgColor.theme is not None:
                        fill_color = f'theme:{fill.fgColor.theme}'
                bold = bool(font and font.bold)
                italic = bool(font and font.italic)
                underline = bool(font and font.underline)
                strike = bool(font and font.strike)
                comment = cell.comment
                if not any((font_color, fill_color, bold, italic, underline, strike, comment)):
                    continue
                ref = f'{get_column_letter(cell.column)}{cell.row}'
                entry = {
                    'cell': ref,
                    'value': _value_text(cell.value),
                    'font_color': font_color,
                    'fill_color': fill_color,
                    'bold': bold,
                    'italic': italic,
                    'underline': underline,
                    'strike': strike,
                }
                cells.append({k: v for k, v in entry.items() if v not in (None, False, '')})
                if font_color:
                    result['counts']['font_color'] += 1
                if fill_color:
                    result['counts']['fill_color'] += 1
                if bold:
                    result['counts']['bold'] += 1
                if italic:
                    result['counts']['italic'] += 1
                if underline:
                    result['counts']['underline'] += 1
                if strike:
                    result['counts']['strike'] += 1
                if comment:
                    comments.append({
                        'cell': ref,
                        'author': getattr(comment, 'author', '') or '',
                        'text': (getattr(comment, 'text', '') or '')[:500],
                    })
                    result['counts']['comments'] += 1
                total += 1
            if total >= max_cells:
                break
        if cells or comments:
            result['sheets'][ws.title] = {'cells': cells, 'comments': comments}
        if total >= max_cells:
            break
    return result
