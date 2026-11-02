"""Outline / manifest / attachment index generation."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .util import ensure_dir, write_json

VERSION = '0.1.0'


def build_outline(md_text: str) -> list[dict]:
    lines = md_text.splitlines()
    headings: list[dict] = []
    in_fence = False
    fence = ''
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence = marker
            elif marker == fence:
                in_fence = False
            continue
        if in_fence:
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            headings.append({
                'level': len(m.group(1)),
                'title': m.group(2).strip(),
                'line': i,
            })

    used: set[str] = set()
    outline: list[dict] = []
    for idx, head in enumerate(headings):
        title = head['title']
        num_match = re.match(r'^\s*(\d+(?:\.\d+)*)', title)
        if num_match:
            sec_id = 'sec-' + num_match.group(1).replace('.', '-')
            number = num_match.group(1)
        else:
            digest = hashlib.sha1(title.encode('utf-8')).hexdigest()[:8]
            sec_id = f'sec-{digest}'
            number = ''
        base_id = sec_id
        n = 2
        while sec_id in used:
            sec_id = f'{base_id}-{n}'
            n += 1
        used.add(sec_id)
        line_start = head['line']
        line_end = (headings[idx + 1]['line'] - 1) if idx + 1 < len(headings) else len(lines)
        outline.append({
            'id': sec_id,
            'level': head['level'],
            'number': number,
            'title': title,
            'line_start': line_start,
            'line_end': line_end,
        })
    return outline


def write_outline(path: str | Path, outline: list[dict]) -> Path:
    lines = ['# 文档大纲', '']
    if not outline:
        lines.append('（未识别到标题）')
    for item in outline:
        indent = '  ' * max(0, item['level'] - 1)
        lines.append(f"- {indent}[{item['id']}] {item['title']}（L{item['line_start']}-L{item['line_end']}）")
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return p


def _public_table(t: dict) -> dict:
    return {
        'id': t.get('id'),
        'caption': t.get('caption', ''),
        'rows': t.get('rows', 0),
        'cols': t.get('cols', 0),
        'header_rows': t.get('header_rows', 0),
        'merges': t.get('merges', []),
        'format': t.get('format', ''),
        'csv': t.get('csv', ''),
        'json': t.get('json', ''),
    }


def build_manifest(
    source_path: str | Path,
    source_hash: str,
    source_size: int,
    status: str,
    outline: list[dict],
    tables: list[dict],
    attachments: list[dict],
    images: list[dict],
    report: dict,
    extra: dict | None = None,
) -> dict:
    manifest = {
        'schema_version': '1.0',
        'generator': {'name': 'reqdoc2md', 'version': VERSION},
        'source': {
            'path': str(Path(source_path).resolve()),
            'name': Path(source_path).name,
            'sha256': source_hash,
            'size': source_size,
        },
        'status': status,
        'outline': outline,
        'tables': [_public_table(t) for t in tables],
        'attachments': attachments,
        'images': images,
        'checks': report.get('checks', []),
        'warnings': report.get('warnings', []),
        'errors': report.get('errors', []),
    }
    if extra:
        manifest.update(extra)
    return manifest


def write_manifest(path: str | Path, manifest: dict) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    write_json(p, manifest)
    return p


def write_attachment_index(path: str | Path, attachments: list[dict], images: list[dict], links: list[dict] | None = None) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    write_json(p, {
        'schema_version': '1.0',
        'attachments': attachments,
        'images': images,
        'references': links or [],
    })
    return p
