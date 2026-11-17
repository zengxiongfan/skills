# -*- coding: utf-8 -*-
"""parse_requirement — 把 req-doc2md 产出的需求 md 解析成"需求点大纲"。

用法：
    python parse_requirement.py <需求.md> [--json out.json] [--points]

输出：
    - 标题树（编号/层级/标题/行号）
    - 候选需求点（4.x 下的功能节点，供模型确认拆分）
    - 每个节点的【功能路径】行（【菜单】-【菜单】）
    - 附件清单
"""
import io
import json
import re
import sys

HEAD_RE = re.compile(r'^(#{1,6})\s+(\d+(?:\.\d+)*)?\s*(.*)$')
PATH_RE = re.compile(r'【[^】]+】(?:\s*-\s*【[^】]+】)+')
ATTACH_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
NON_POINT = ('规则说明', '功能位置', '功能路径', '功能描述', '字段说明', '概述')


def parse(md_path):
    lines = io.open(md_path, encoding='utf-8').read().splitlines()
    headings = []
    for i, line in enumerate(lines, 1):
        m = HEAD_RE.match(line.strip())
        if not m:
            continue
        level = len(m.group(1))
        no = m.group(2) or ''
        title = m.group(3).strip()
        if not title:
            continue
        headings.append({'level': level, 'no': no, 'title': title, 'line': i})
    # 每个标题的"子树"结束行：下一个层级 <= 当前层级的标题之前
    for idx, h in enumerate(headings):
        end = len(lines)
        for c in headings[idx + 1:]:
            if c['level'] <= h['level']:
                end = c['line'] - 1
                break
        h['end'] = end
    # 功能路径 / 附件（按子树归集，父节点也包含子节内容）
    for h in headings:
        block = lines[h['line']:h['end']]
        paths = []
        for ln in block:
            for p in PATH_RE.findall(ln):
                p = re.sub(r'\s+', '', p)
                if p not in paths:
                    paths.append(p)
        h['paths'] = paths
        h['attachments'] = []
        for ln in block:
            for a in ATTACH_RE.findall(ln):
                name = a.split('/')[-1]
                if name not in h['attachments']:
                    h['attachments'].append(name)
        h.pop('end', None)
    # 候选需求点：section 4 下所有"实质节点"（标题不是规则说明/功能路径等）
    # 同时给出最浅层（4.x）与最深层的粒度，供模型在 manifest 中决定拆分口径。
    points = []
    for h in headings:
        no = h['no']
        if not no.startswith('4.'):
            continue
        if h['title'] in NON_POINT:
            continue
        depth = no.count('.') + 1
        points.append({
            'no': no,
            'title': h['title'],
            'depth': depth,
            'paths': h['paths'],
            'attachments': h['attachments'],
        })
    return {'headings': headings, 'points': points}


def main():
    if len(sys.argv) < 2:
        print('usage: python parse_requirement.py <req.md> [--json out.json] [--points]')
        sys.exit(2)
    md = sys.argv[1]
    out_json = None
    only_points = '--points' in sys.argv
    if '--json' in sys.argv:
        out_json = sys.argv[sys.argv.index('--json') + 1]
    data = parse(md)
    if out_json:
        io.open(out_json, 'w', encoding='utf-8').write(
            json.dumps(data, ensure_ascii=False, indent=2))
        print('json ->', out_json)
    if only_points:
        for i, p in enumerate(data['points'], 1):
            print('%2d  %-8s %s  (path:%d, att:%d)' %
                  (i, p['no'], p['title'], len(p['paths']), len(p['attachments'])))
    else:
        print('headings:', len(data['headings']), 'points:', len(data['points']))
        for p in data['points']:
            print('  ', p['no'], p['title'])


if __name__ == '__main__':
    main()
