# -*- coding: utf-8 -*-
"""manual — req-op-manual 统一 CLI。

用法：
    python manual.py outline  <需求.md> [--json out.json] [--points]
    python manual.py extract  <测试案例.xlsx> --out <work>/extract [--no-contact]
    python manual.py prep     --map figures.json --out assets [--default-crop-top N]
    python manual.py scaffold --manifest manifest.json --out content.py
    python manual.py build    --manifest manifest.json [--content content.py] --out 手册.docx
    python manual.py merge    --manifest merge.json --out 整合版.docx [--update-toc]
    python manual.py verify   <手册.docx> [--qa qa-report.md] [--no-word] [--expect-req N]
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(script, args):
    cmd = [PY, os.path.join(HERE, script)] + args
    print('$', ' '.join(cmd[1:]))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def scaffold(manifest_path, out_path):
    manifest = json.load(io.open(manifest_path, encoding='utf-8'))
    points = manifest.get('requirement_points') or []
    figs = (manifest.get('figures') or {}).get('per_point') or {}
    lines = [
        '# -*- coding: utf-8 -*-',
        '"""内容脚本（由 manual.py scaffold 生成）。',
        '',
        '按 references/writing-guide.md 补全每个需求点的 功能描述 / 操作方法；',
        '图片放在本文件同级 assets/ 目录，文件名与 manifest.figures.per_point 一致。',
        '"""',
        'import os',
        '',
        'from docx_engine import (h2, h3, para, bullets, steps, table, figure,',
        '                         note, placeholder)',
        '',
        'ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")',
        '',
        '',
        'def build(doc):',
    ]
    if not points:
        lines.append('    # 未在 manifest 中提供 requirement_points')
        lines.append('    h2(doc, "1  需求点一：待补充")')
    for p in points:
        no = str(p.get('no', ''))
        title = p.get('title', '待补充')
        lines.append('')
        lines.append('    # ===== %s %s =====' % (no, title))
        lines.append('    h2(doc, %r)' % ('%s  %s' % (no, title)))
        lines.append('    h3(doc, %r)' % ('%s.1  功能描述' % no))
        lines.append('    para(doc, "（待补充：功能位置、规则要点、字段/校验表、举例）")')
        lines.append('    h3(doc, %r)' % ('%s.2  操作方法' % no))
        lines.append('    steps(doc, ["（待补充：步骤1）"])')
        for item in figs.get(no, []):
            if item.get('img'):
                cap = item.get('caption', '待补充图注')
                lines.append('    figure(doc, os.path.join(ASSETS, %r), %r, %r)' % (
                    item['img'], cap, no))
            elif item.get('placeholder'):
                lines.append('    placeholder(doc, %r)' % item['placeholder'])
    lines.append('')
    io.open(out_path, 'w', encoding='utf-8').write('\n'.join(lines))
    print('scaffold ->', out_path)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'outline':
        run('parse_requirement.py', args)
    elif cmd == 'extract':
        run('extract_case.py', args)
    elif cmd == 'prep':
        run('prep_assets.py', args)
    elif cmd == 'build':
        run('build_single.py', args)
    elif cmd == 'merge':
        run('build_merge.py', args)
    elif cmd == 'verify':
        run('verify.py', args)
    elif cmd == 'scaffold':
        mp = args[args.index('--manifest') + 1]
        out = args[args.index('--out') + 1]
        scaffold(mp, out)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
