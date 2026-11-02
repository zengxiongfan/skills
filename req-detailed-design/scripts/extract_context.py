#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按文件 + 锚点提取前后 N 行代码上下文，直接产出可粘贴进设计文档的 Markdown 代码块。

编码策略（与 CGIS 仓库实测一致）：
- 先按 UTF-8 严格解码（含 BOM）；
- 失败回退 GBK(cp936)，不可解码字节按 iconv -c 语义跳过并告警（不静默截断）。

用法：
  # 单点：锚点为原文片段（子串匹配）或 :行号
  python extract_context.py --file <path> --anchor "enterpriseFlag" [--before 5] [--after 5] [--title "方法名"]

  # 批量：从任务表提取（每个任务输出一节）
  python extract_context.py --tasks tasks.json [--out 素材.md]

tasks.json 结构：
  [{"file": "...", "anchor": "...", "before": 5, "after": 5,
    "title": "可选定位标题", "note": "可选备注"}]

退出码：0 成功；2 文件不存在/无法读取；3 锚点未找到。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

LANG_BY_EXT = {
    '.java': 'java', '.xml': 'xml', '.js': 'javascript', '.html': 'html',
    '.htm': 'html', '.sql': 'sql', '.properties': 'properties', '.py': 'python',
    '.sh': 'bash', '.json': 'json', '.css': 'css', '.jsp': 'jsp', '.txt': 'text',
}

DEFAULT_BEFORE = 5
DEFAULT_AFTER = 5


def read_text(path: str) -> tuple[str, str, int]:
    """返回 (text, encoding, skipped_bytes)。UTF-8 严格失败则回退 GBK。"""
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        return raw.decode('utf-8-sig'), 'utf-8', 0
    except UnicodeDecodeError:
        text = raw.decode('gbk', errors='ignore')
        skipped = raw.decode('gbk', errors='replace').count('\ufffd')
        return text, 'gbk', skipped


def split_lines(text: str) -> list[str]:
    return [ln.rstrip('\r') for ln in text.split('\n')]


def find_anchor(lines: list[str], anchor: str) -> tuple[int, list[int]]:
    """返回 (0-based 行索引, 命中的全部行号列表)。锚点 ':123' 表示第 123 行。"""
    if anchor.startswith(':') and anchor[1:].strip().isdigit():
        n = int(anchor[1:].strip())
        if not 1 <= n <= len(lines):
            raise ValueError(f'行号 {n} 超出文件范围 1-{len(lines)}')
        return n - 1, [n]

    hits = [i for i, ln in enumerate(lines) if anchor in ln]
    if not hits:
        # 大小写不敏感兜底
        low = anchor.lower()
        hits = [i for i, ln in enumerate(lines) if low in ln.lower()]
    if not hits:
        return -1, []
    return hits[0], [i + 1 for i in hits]


def language(path: str) -> str:
    return LANG_BY_EXT.get(os.path.splitext(path)[1].lower(), 'text')


def render(file: str, lines: list[str], idx: int, before: int, after: int,
           title: str | None, encoding: str, skipped: int,
           hits: list[int], note: str | None) -> str:
    start = max(0, idx - before)
    end = min(len(lines) - 1, idx + after)
    shown = lines[start:end + 1]

    label = title or (f'行 {idx + 1}' if not title else title)
    loc = f'> 定位：`{file}` · {label} · :{start + 1}-{end + 1}'
    if hits and len(hits) > 1:
        extra = '、'.join(str(h) for h in hits[:5])
        suffix = ' 等' if len(hits) > 5 else ''
        loc += f'\n> 注：锚点命中 {len(hits)} 处，取第 1 处（其余行号：{extra}{suffix}）'
    if encoding != 'utf-8':
        warn = f'按 {encoding.upper()} 解码'
        if skipped:
            warn += f'（跳过 {skipped} 个不可解码字节，等价 iconv -c）'
        loc += f'\n> 注：{warn}'
    if note:
        loc += f'\n> {note}'

    body = '\n'.join(f'{start + 1 + i}\t{ln}' for i, ln in enumerate(shown))
    return f'{loc}\n\n```{language(file)}\n{body}\n```\n'


def run_one(task: dict) -> tuple[str | None, str]:
    """返回 (渲染结果或 None, 错误信息)。"""
    file = task.get('file', '')
    anchor = str(task.get('anchor', ''))
    if not file:
        return None, '任务缺少 file'
    if not os.path.isfile(file):
        return None, f'文件不存在：{file}'
    if not anchor:
        return None, f'缺少 anchor：{file}'
    try:
        text, enc, skipped = read_text(file)
    except OSError as e:
        return None, f'无法读取 {file}：{e}'
    lines = split_lines(text)
    try:
        idx, hits = find_anchor(lines, anchor)
    except ValueError as e:
        return None, f'{file}：{e}'
    if idx < 0:
        return None, f'锚点未找到：{file} · "{anchor}"（请缩短锚点或改用 :行号）'
    out = render(file, lines, idx,
                 int(task.get('before', DEFAULT_BEFORE)),
                 int(task.get('after', DEFAULT_AFTER)),
                 task.get('title'), enc, skipped, hits, task.get('note'))
    return out, ''


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='提取代码上下文（设计文档素材）')
    ap.add_argument('--file')
    ap.add_argument('--anchor')
    ap.add_argument('--before', type=int, default=DEFAULT_BEFORE)
    ap.add_argument('--after', type=int, default=DEFAULT_AFTER)
    ap.add_argument('--title')
    ap.add_argument('--note')
    ap.add_argument('--tasks', help='批量任务 JSON 文件')
    ap.add_argument('--out', help='批量模式输出文件（默认 stdout）')
    args = ap.parse_args(argv)

    if args.tasks:
        try:
            with open(args.tasks, encoding='utf-8') as f:
                tasks = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f'读取任务文件失败：{e}', file=sys.stderr)
            return 2
        if not isinstance(tasks, list):
            print('任务文件必须是 JSON 数组', file=sys.stderr)
            return 2

        blocks, failed = [], []
        for i, task in enumerate(tasks, 1):
            out, err = run_one(task)
            if out:
                blocks.append(out)
            else:
                failed.append(f'[{i}] {err}')
        rendered = '\n---\n\n'.join(b for b in blocks)
        if args.out:
            with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
                f.write(rendered)
            print(f'已写入 {args.out}：成功 {len(blocks)} / 失败 {len(failed)}')
            for e in failed:
                print('  ✗', e, file=sys.stderr)
        else:
            print(rendered)
        return 0 if not failed else 3

    if not args.file or not args.anchor:
        ap.print_help()
        return 2
    out, err = run_one({
        'file': args.file, 'anchor': args.anchor, 'before': args.before,
        'after': args.after, 'title': args.title, 'note': args.note,
    })
    if not out:
        print(err, file=sys.stderr)
        return 3 if '锚点未找到' in err else 2
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
