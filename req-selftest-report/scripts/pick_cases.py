# -*- coding: utf-8 -*-
"""阶段2：按 picks.json 抽取选中案例详情与截图。

用法：
  python pick_cases.py --data iter_data.json --picks picks.json \
      --outdir report_assets --out selected.json

picks.json 格式（模块必填，rows 与 nos 二选一或混用）：
[
  {"module": "新福利配置页调整", "rows": [2, 6, 18]},
  {"module": "责任匹配规则配置", "nos": ["RCP-15795-133", "RCP-15795-136"]},
  {"module": "跨保单福利累计", "rows": [11, 12, 13]}
]
"""
import argparse
import json
import os
import zipfile


def find_case(cases, module, row=None, no=None):
    pool = [c for c in cases if (c['module'] or '').strip() == module]
    if row is not None:
        hit = [c for c in pool if c['row'] == row]
        if hit:
            return hit[0]
    if no is not None:
        hit = [c for c in pool if (c['no'] or '').strip() == no]
        if hit:
            return hit[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--picks', required=True)
    ap.add_argument('--outdir', default='report_assets')
    ap.add_argument('--out', default='selected.json')
    args = ap.parse_args()

    data = json.load(open(args.data, encoding='utf-8'))
    picks = json.load(open(args.picks, encoding='utf-8'))
    cases = data['cases']
    file_paths = {f['path'].split(os.sep)[-1]: f['path'] for f in data['files']}

    os.makedirs(args.outdir, exist_ok=True)
    selected, seen_at, problems = [], {}, []
    for item in picks:
        module = item['module'].strip()
        rows = item.get('rows') or []
        nos = item.get('nos') or []
        targets = [('row', r) for r in rows] + [('no', n) for n in nos]
        for kind, val in targets:
            case = find_case(cases, module, row=val if kind == 'row' else None,
                             no=val if kind == 'no' else None)
            if case is None:
                problems.append(f'未找到案例: module={module} {kind}={val}')
                continue
            rec = dict(case)
            rec['exported'] = []
            dup = False
            for img in case.get('images') or []:
                key = (img['file'], img['name'])
                if key in seen_at:
                    dup = True
                seen_at.setdefault(key, len(selected))
                src = file_paths.get(img['file'])
                if not src:
                    problems.append(f'找不到源文件: {img["file"]}')
                    continue
                export_name = f'c{len(selected) + 1:02d}_{img["name"]}'
                dest = os.path.join(args.outdir, export_name)
                with zipfile.ZipFile(src) as z:
                    with open(dest, 'wb') as f:
                        f.write(z.read('xl/media/' + img['name']))
                rec['exported'].append(dest)
            rec['dup_of_prev'] = dup
            selected.append(rec)

    dup_count = sum(1 for c in selected if c['dup_of_prev'])
    no_img = [c for c in selected if not c['exported']]
    json.dump(selected, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'selected: {len(selected)}  with_image: {len(selected) - len(no_img)}'
          f'  dup_image: {dup_count}  no_image: {len(no_img)}')
    for c in selected:
        flag = 'DUP' if c['dup_of_prev'] else ('IMG' if c['exported'] else '---')
        print(f'  [{flag}] {c["module"][:16]:<16} | {c["no"] or "—":>14} | '
              f'{c["shot"] or "":>10} -> {",".join(os.path.basename(p) for p in c["exported"]) or "无截图"}'
              f' | {(c["title"] or "")[:36]}')
    if problems:
        print('problems:')
        for p in problems:
            print('  -', p)


if __name__ == '__main__':
    main()
