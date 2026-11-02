"""Pandoc AST helpers: rendering, image rewriting, table placeholders."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Callable

from .util import run_cmd

PLACEHOLDER_RE = re.compile(r'^ZCODETABLE(\d{4})Z$')


def run_pandoc_json(src: str | Path, media_dir: str | Path, timeout: int = 600) -> dict:
    result = run_cmd(
        [
            'pandoc', str(src), '-f', 'docx', '-t', 'json',
            '--wrap=none', '--extract-media', str(media_dir),
        ],
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f'pandoc 读取 docx 失败: {result.stderr.strip()[:1000]}')
    return json.loads(result.stdout)


def run_pandoc_gfm(doc: dict, timeout: int = 600) -> str:
    payload = json.dumps(doc, ensure_ascii=False)
    result = run_cmd(
        ['pandoc', '-f', 'json', '-t', 'gfm', '--wrap=none'],
        input_text=payload,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f'pandoc 渲染 markdown 失败: {result.stderr.strip()[:1000]}')
    return result.stdout


# ---------- plain text ----------

def plain_text(node) -> str:
    if node is None:
        return ''
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(plain_text(x) for x in node)
    if not isinstance(node, dict):
        return ''
    t = node.get('t')
    c = node.get('c')
    if t == 'Str':
        return str(c or '')
    if t == 'Space':
        return ' '
    if t == 'SoftBreak':
        return ' '
    if t == 'LineBreak':
        return '\n'
    if t in ('Code', 'Math'):
        return str(c[1] if isinstance(c, list) and len(c) > 1 else '')
    if t in ('Emph', 'Strong', 'Strikeout', 'Superscript', 'Subscript',
             'Underline', 'SmallCaps'):
        return plain_text(c)
    if t == 'Quoted':
        return plain_text(c[1] if isinstance(c, list) and len(c) > 1 else c)
    if t == 'Cite':
        return plain_text(c[1] if isinstance(c, list) and len(c) > 1 else c)
    if t in ('Link', 'Image'):
        return plain_text(c[1] if isinstance(c, list) and len(c) > 1 else c)
    if t in ('Span',):
        return plain_text(c[1] if isinstance(c, list) and len(c) > 1 else c)
    if t in ('RawInline',):
        return str(c[1] if isinstance(c, list) and len(c) > 1 else '')
    if t == 'Note':
        return ''
    return plain_text(c)


def _join_inlines(inlines, renderer) -> str:
    return ''.join(renderer(x) for x in (inlines or []))


# ---------- inline markdown ----------

def _md_escape_code(text: str) -> str:
    text = str(text)
    if '`' not in text:
        return f'`{text}`'
    return f'`` {text} ``'


def render_inline_md(node) -> str:
    if node is None:
        return ''
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(render_inline_md(x) for x in node)
    if not isinstance(node, dict):
        return ''
    t = node.get('t')
    c = node.get('c')
    if t == 'Str':
        return str(c or '')
    if t == 'Space':
        return ' '
    if t == 'SoftBreak':
        return ' '
    if t == 'LineBreak':
        return '<br>'
    if t == 'Emph':
        return f'*{_join_inlines(c, render_inline_md)}*'
    if t == 'Strong':
        return f'**{_join_inlines(c, render_inline_md)}**'
    if t == 'Strikeout':
        return f'~~{_join_inlines(c, render_inline_md)}~~'
    if t == 'Superscript':
        return f'^{_join_inlines(c, render_inline_md)}^'
    if t == 'Subscript':
        return f'~{_join_inlines(c, render_inline_md)}~'
    if t == 'Underline':
        return f'<u>{_join_inlines(c, render_inline_md)}</u>'
    if t == 'SmallCaps':
        return f'<span style="font-variant:small-caps">{_join_inlines(c, render_inline_md)}</span>'
    if t == 'Code':
        return _md_escape_code(c[1] if isinstance(c, list) and len(c) > 1 else '')
    if t == 'Math':
        kind = c[0].get('t') if isinstance(c, list) and c and isinstance(c[0], dict) else 'InlineMath'
        text = c[1] if isinstance(c, list) and len(c) > 1 else ''
        return f'$${text}$$' if kind == 'DisplayMath' else f'${text}$'
    if t == 'Quoted':
        q = c[0].get('t') if isinstance(c, list) and c and isinstance(c[0], dict) else 'DoubleQuote'
        inner = _join_inlines(c[1] if len(c) > 1 else [], render_inline_md)
        return f'“{inner}”' if q == 'DoubleQuote' else f'‘{inner}’'
    if t == 'Cite':
        return _join_inlines(c[1] if isinstance(c, list) and len(c) > 1 else [], render_inline_md)
    if t == 'Link':
        inner = _join_inlines(c[1], render_inline_md) if len(c) > 1 else ''
        target = c[2][0] if len(c) > 2 and c[2] else ''
        return f'[{inner}]({target})'
    if t == 'Image':
        alt = _join_inlines(c[1], render_inline_md) if len(c) > 1 else ''
        target = c[2][0] if len(c) > 2 and c[2] else ''
        return f'![{alt}]({target})'
    if t == 'Span':
        return _join_inlines(c[1] if isinstance(c, list) and len(c) > 1 else [], render_inline_md)
    if t == 'RawInline':
        fmt = c[0] if isinstance(c, list) and c else ''
        return str(c[1]) if len(c) > 1 and fmt in ('gfm', 'markdown', 'html') else ''
    if t == 'Note':
        return ''
    return _join_inlines(c, render_inline_md)


# ---------- inline HTML ----------

def render_inline_html(node) -> str:
    if node is None:
        return ''
    if isinstance(node, str):
        return html.escape(node, quote=False)
    if isinstance(node, list):
        return ''.join(render_inline_html(x) for x in node)
    if not isinstance(node, dict):
        return ''
    t = node.get('t')
    c = node.get('c')
    if t == 'Str':
        return html.escape(str(c or ''), quote=False)
    if t == 'Space':
        return ' '
    if t == 'SoftBreak':
        return ' '
    if t == 'LineBreak':
        return '<br>'
    if t == 'Emph':
        return f'<em>{_join_inlines(c, render_inline_html)}</em>'
    if t == 'Strong':
        return f'<strong>{_join_inlines(c, render_inline_html)}</strong>'
    if t == 'Strikeout':
        return f'<del>{_join_inlines(c, render_inline_html)}</del>'
    if t == 'Superscript':
        return f'<sup>{_join_inlines(c, render_inline_html)}</sup>'
    if t == 'Subscript':
        return f'<sub>{_join_inlines(c, render_inline_html)}</sub>'
    if t == 'Underline':
        return f'<u>{_join_inlines(c, render_inline_html)}</u>'
    if t == 'SmallCaps':
        return f'<span style="font-variant:small-caps">{_join_inlines(c, render_inline_html)}</span>'
    if t == 'Code':
        text = html.escape(str(c[1] if isinstance(c, list) and len(c) > 1 else ''), quote=False)
        return f'<code>{text}</code>'
    if t == 'Math':
        kind = c[0].get('t') if isinstance(c, list) and c and isinstance(c[0], dict) else 'InlineMath'
        text = html.escape(str(c[1] if isinstance(c, list) and len(c) > 1 else ''), quote=False)
        return f'<span class="math display">{text}</span>' if kind == 'DisplayMath' else f'<span class="math inline">{text}</span>'
    if t == 'Quoted':
        q = c[0].get('t') if isinstance(c, list) and c and isinstance(c[0], dict) else 'DoubleQuote'
        inner = _join_inlines(c[1] if len(c) > 1 else [], render_inline_html)
        return f'“{inner}”' if q == 'DoubleQuote' else f'‘{inner}’'
    if t == 'Cite':
        return _join_inlines(c[1] if isinstance(c, list) and len(c) > 1 else [], render_inline_html)
    if t == 'Link':
        inner = _join_inlines(c[1], render_inline_html) if len(c) > 1 else ''
        target = html.escape(str(c[2][0] if len(c) > 2 and c[2] else ''), quote=True)
        title = c[2][1] if len(c) > 2 and len(c[2]) > 1 else ''
        title_attr = f' title="{html.escape(str(title), quote=True)}"' if title else ''
        return f'<a href="{target}"{title_attr}>{inner}</a>'
    if t == 'Image':
        alt = _join_inlines(c[1], render_inline_html) if len(c) > 1 else ''
        target = html.escape(str(c[2][0] if len(c) > 2 and c[2] else ''), quote=True)
        title = c[2][1] if len(c) > 2 and len(c[2]) > 1 else ''
        title_attr = f' title="{html.escape(str(title), quote=True)}"' if title else ''
        return f'<img src="{target}" alt="{html.escape(alt, quote=True)}"{title_attr}>'
    if t == 'Span':
        inner = _join_inlines(c[1] if isinstance(c, list) and len(c) > 1 else [], render_inline_html)
        return f'<span>{inner}</span>'
    if t == 'RawInline':
        fmt = c[0] if isinstance(c, list) and c else ''
        return str(c[1]) if len(c) > 1 and fmt in ('html', 'gfm') else html.escape(str(c[1] if isinstance(c, list) and len(c) > 1 else ''), quote=False)
    if t == 'Note':
        return ''
    return _join_inlines(c, render_inline_html)


# ---------- blocks ----------

def render_cell_md(blocks) -> str:
    """Render cell blocks as a single markdown-ish line for pipe tables."""
    parts: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        t = block.get('t')
        c = block.get('c')
        if t in ('Para', 'Plain'):
            parts.append(render_inline_md(c))
        elif t == 'Header':
            parts.append(render_inline_md(c[2]))
        elif t == 'BulletList':
            items = []
            for item in c:
                items.append('• ' + render_cell_md(item))
            parts.append('<br>'.join(items))
        elif t == 'OrderedList':
            items = []
            for item in c[1]:
                items.append(render_cell_md(item))
            parts.append('<br>'.join(f'{i}. {x}' for i, x in enumerate(items, 1)))
        elif t == 'CodeBlock':
            parts.append('<br>'.join(str(c[1]).splitlines()))
        elif t == 'RawBlock':
            parts.append(str(c[1]) if isinstance(c, list) and len(c) > 1 else '')
        elif t == 'Table':
            parts.append('[嵌套表格]')
        elif t == 'BlockQuote':
            parts.append(render_cell_md(c))
        elif t == 'Div':
            parts.append(render_cell_md(c[1]))
        else:
            parts.append(plain_text(block))
    text = '<br>'.join(p for p in parts if p != '')
    return text.replace('\r', ' ').replace('\n', '<br>')


def render_blocks_html(blocks) -> str:
    parts: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        t = block.get('t')
        c = block.get('c')
        if t in ('Para', 'Plain'):
            parts.append(f'<p>{render_inline_html(c)}</p>')
        elif t == 'Header':
            level = c[0]
            parts.append(f'<h{level}>{render_inline_html(c[2])}</h{level}>')
        elif t == 'BulletList':
            parts.append('<ul>' + ''.join(f'<li>{render_blocks_html(item)}</li>' for item in c) + '</ul>')
        elif t == 'OrderedList':
            parts.append('<ol>' + ''.join(f'<li>{render_blocks_html(item)}</li>' for item in c[1]) + '</ol>')
        elif t == 'CodeBlock':
            lang = ''
            attr = c[0]
            if isinstance(attr, list) and len(attr) > 1 and attr[1]:
                lang = f' class="language-{html.escape(attr[1][0], quote=True)}"'
            text = html.escape(str(c[1]), quote=False)
            parts.append(f'<pre><code{lang}>{text}</code></pre>')
        elif t == 'BlockQuote':
            parts.append(f'<blockquote>{render_blocks_html(c)}</blockquote>')
        elif t == 'Div':
            parts.append(render_blocks_html(c[1]))
        elif t == 'RawBlock':
            fmt = c[0] if isinstance(c, list) and c else ''
            if fmt in ('html', 'gfm'):
                parts.append(str(c[1]))
        elif t == 'Table':
            try:
                from .tables import table_from_ast, render_table_html
                td = table_from_ast(block, 0, header_rows=1)
                parts.append(render_table_html(td))
            except Exception:
                parts.append('<p>[嵌套表格]</p>')
        elif t == 'Figure':
            parts.append(render_blocks_html(c[2] if isinstance(c, list) and len(c) > 2 else []))
        else:
            text = plain_text(block)
            if text:
                parts.append(f'<p>{html.escape(text, quote=False)}</p>')
    return ''.join(parts)


# ---------- transformations ----------

def transform_images(node, fn: Callable[[dict], dict]):
    if isinstance(node, list):
        return [transform_images(x, fn) for x in node]
    if isinstance(node, dict):
        if node.get('t') == 'Image':
            return fn(node)
        for key, value in list(node.items()):
            node[key] = transform_images(value, fn)
        return node
    return node


def iter_blocks(blocks):
    """Yield every block recursively, without entering Table cells."""
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        yield block
        t = block.get('t')
        c = block.get('c')
        if t == 'BulletList':
            for item in c or []:
                yield from iter_blocks(item)
        elif t == 'OrderedList':
            for item in (c[1] if isinstance(c, list) and len(c) > 1 else []):
                yield from iter_blocks(item)
        elif t == 'BlockQuote':
            yield from iter_blocks(c)
        elif t == 'Div':
            yield from iter_blocks(c[1] if isinstance(c, list) and len(c) > 1 else [])
        elif t == 'Figure':
            yield from iter_blocks(c[2] if isinstance(c, list) and len(c) > 2 else [])


def replace_tables_in_blocks(blocks, collector: Callable[[dict], str]) -> None:
    """Replace Tables with placeholder paragraphs; nested tables stay in cells."""
    for i, block in enumerate(list(blocks or [])):
        if not isinstance(block, dict):
            continue
        t = block.get('t')
        c = block.get('c')
        if t == 'Table':
            placeholder = collector(block)
            blocks[i] = {'t': 'Para', 'c': [{'t': 'Str', 'c': placeholder}]}
        elif t == 'BulletList':
            for item in c or []:
                replace_tables_in_blocks(item, collector)
        elif t == 'OrderedList':
            for item in (c[1] if isinstance(c, list) and len(c) > 1 else []):
                replace_tables_in_blocks(item, collector)
        elif t == 'BlockQuote':
            replace_tables_in_blocks(c, collector)
        elif t == 'Div':
            replace_tables_in_blocks(c[1] if isinstance(c, list) and len(c) > 1 else [], collector)
        elif t == 'Figure':
            replace_tables_in_blocks(c[2] if isinstance(c, list) and len(c) > 2 else [], collector)


def number_headings(doc: dict) -> None:
    counters = [0] * 6

    def already_numbered(text: str) -> bool:
        return bool(
            re.match(r'^\s*\d+(?:\.\d+)*[\s、.．]', text)
            or re.match(r'^\s*[一二三四五六七八九十]+[、.．]', text)
            or re.match(r'^\s*第[一二三四五六七八九十百零\d]+[章节]', text)
        )

    def walk(blocks) -> None:
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            t = block.get('t')
            c = block.get('c')
            if t == 'Header':
                level = max(1, min(6, int(c[0])))
                text = plain_text(c[2]).strip()
                m = re.match(r'^(\d+(?:\.\d+)*)', text)
                if m:
                    parts = [int(x) for x in m.group(1).split('.') if x.isdigit()]
                    for i in range(6):
                        counters[i] = parts[i] if i < len(parts) else 0
                elif already_numbered(text):
                    pass
                else:
                    counters[level - 1] += 1
                    for i in range(level, 6):
                        counters[i] = 0
                    nums = [str(counters[i]) for i in range(level) if counters[i] > 0]
                    if nums:
                        c[2] = [{'t': 'Str', 'c': '.'.join(nums) + ' '}] + list(c[2])
            elif t == 'BulletList':
                for item in c or []:
                    walk(item)
            elif t == 'OrderedList':
                for item in (c[1] if isinstance(c, list) and len(c) > 1 else []):
                    walk(item)
            elif t == 'BlockQuote':
                walk(c)
            elif t == 'Div':
                walk(c[1] if isinstance(c, list) and len(c) > 1 else [])
            elif t == 'Figure':
                walk(c[2] if isinstance(c, list) and len(c) > 2 else [])

    walk(doc.get('blocks') or [])
