# -*- coding: utf-8 -*-
"""阶段0：自适应解析测试案例 xlsx（不依赖固定工作表名/列序）。

用法：
  python parse_cases.py --xlsx a.xlsx [b.xlsx ...] --out iter_data.json [--export-images DIR]

产出 iter_data.json：
{
  "files": [{"path", "case_sheet", "header_row", "shot_sheets": [...], "unmapped_headers": [...]}],
  "cases": [{"file", "row", "no", "module", "item", "title", "level", "steps", "expect",
             "actual", "status", "shot", "images": [{"file","name"}], "warnings": [...]}],
  "shot_spans": {"截图": [{"from","to","target"}]},
  "warnings": [...]
}
"""
import argparse
import json
import os
import re
import zipfile

import openpyxl

# 表头同义词（左侧为内部字段键）
HEADER_ALIASES = {
    'path':    ['路径'],
    'no':      ['测试案例编号', '案例编号', '编号'],
    'module':  ['模块', '模块名称'],
    'item':    ['测试项', '测试项名称', '测试项描述'],
    'title':   ['测试案例标题', '案例标题', '标题'],
    'level':   ['重要级别', '优先级', '级别'],
    'steps':   ['操作步骤', '步骤', '执行步骤'],
    'expect':  ['输出', '预期', '预期结果', '预期输出'],
    'actual':  ['实际输出', '实际结果'],
    'status':  ['测试状态', '执行状态', '执行结果', '测试结果'],
    'shot':    ['截图对应行数', '截图链接', '截图行数', '截图'],
}

REF_RE = re.compile(r'(?:([^\s!！,，、；;：:]+)[!！])?\s*A?(\d+)')


def norm(v):
    return v.strip().lstrip('*').strip() if isinstance(v, str) else v


def match_header(text):
    """返回 (字段键, 精确度) 或 (None, 0)。精确优先于包含。"""
    if not isinstance(text, str):
        return None, 0
    s = norm(text)
    if not s:
        return None, 0
    for key, aliases in HEADER_ALIASES.items():
        if s in aliases:
            return key, 2
    for key, aliases in HEADER_ALIASES.items():
        for a in aliases:
            if a in s:
                return key, 1
    return None, 0


def detect_header(rows):
    """在前若干行中找表头行，返回 (row_index0, {字段键: 列号})。"""
    best = None
    for idx, row in enumerate(rows):
        exact, loose, used_cols, used_keys = {}, {}, set(), set()
        for j, v in enumerate(row):
            key, score = match_header(v)
            if key and key not in used_keys and j not in used_cols:
                exact[key] = j
                used_keys.add(key)
                used_cols.add(j)
        hits = dict(loose)
        hits.update(exact)
        score = len(hits)
        if score >= 4 and (best is None or score > best[0]):
            best = (score, idx, hits)
    return (best[1], best[2]) if best else (None, None)


def parse_rels(z, rels_path, base_dir):
    """解析 .rels，返回 {rId: 规范化的 zip 内路径}。

    兼容：属性顺序（Id/Target 先后）与目标路径写法（相对 ../、绝对 /xl/）。
    """
    try:
        xml = z.read(rels_path).decode('utf-8')
    except KeyError:
        return {}
    out = {}
    for tag in re.findall(r'<Relationship\b[^>]*?/?>', xml):
        rid = re.search(r'\bId="([^"]+)"', tag)
        tgt = re.search(r'\bTarget="([^"]+)"', tag)
        if not (rid and tgt):
            continue
        target = tgt.group(1)
        if target.startswith('/'):
            path = target.lstrip('/')
        else:
            path = os.path.normpath(os.path.join(base_dir, target)).replace('\\', '/')
        out[rid.group(1)] = path
    return out


def parse_drawings(z, drawing_path):
    """解析 drawing.xml 的图片锚点，返回 [{'from','to','target'}]（行号为1-based）。

    兼容两种写法：Excel/WPS 的 <xdr:twoCellAnchor> 与 openpyxl 的 <oneCellAnchor>
    （无命名空间前缀），统一用前缀无关正则。
    """
    d = z.read(drawing_path).decode('utf-8')
    blocks = re.findall(
        r'<(?:\w+:)?(?:twoCellAnchor|oneCellAnchor)\b[^>]*>.*?</(?:\w+:)?(?:twoCellAnchor|oneCellAnchor)>',
        d, re.S)
    rels_path = drawing_path.replace('drawings/', 'drawings/_rels/') + '.rels'
    relmap = parse_rels(z, rels_path, 'xl/drawings')
    spans = []
    for a in blocks:
        frm = re.search(r'<(?:\w+:)?from>(.*?)</(?:\w+:)?from>', a, re.S)
        to = re.search(r'<(?:\w+:)?to>(.*?)</(?:\w+:)?to>', a, re.S)
        embed = re.search(r'r:embed="(rId\d+)"', a)
        if not frm or not embed:
            continue
        row_m = re.search(r'<(?:\w+:)?row>(\d+)</(?:\w+:)?row>', frm.group(1))
        if not row_m:
            continue
        r0 = int(row_m.group(1)) + 1
        r1 = r0
        if to:
            to_m = re.search(r'<(?:\w+:)?row>(\d+)</(?:\w+:)?row>', to.group(1))
            if to_m:
                r1 = int(to_m.group(1)) + 1
        spans.append({'from': r0, 'to': r1, 'target': relmap.get(embed.group(1), '')})
    return spans


def sheet_drawings(z):
    """返回 {工作表名: [span]}（只含有 drawing 的工作表）。"""
    wb_xml = z.read('xl/workbook.xml').decode('utf-8')
    wb_rels = parse_rels(z, 'xl/_rels/workbook.xml.rels', 'xl')
    out = {}
    for tag in re.findall(r'<sheet\b[^>]*>', wb_xml):
        nm = re.search(r'\bname="([^"]+)"', tag)
        rid = re.search(r'\br:id="(rId\d+)"', tag)
        if not (nm and rid):
            continue
        name = nm.group(1)
        sheet_file = wb_rels.get(rid.group(1), '')
        if not sheet_file or sheet_file not in z.namelist():
            continue
        x = z.read(sheet_file).decode('utf-8')
        dr = re.search(r'<drawing\b[^>]*>', x)
        if not dr:
            continue
        drid = re.search(r'\br:id="(rId\d+)"', dr.group(0))
        if not drid:
            continue
        srels_path = sheet_file.replace('worksheets/', 'worksheets/_rels/') + '.rels'
        srels = parse_rels(z, srels_path, 'xl/worksheets')
        dpath = srels.get(drid.group(1), '')
        if dpath in z.namelist():
            out[name] = parse_drawings(z, dpath)
    return out


def parse_refs(text):
    """解析截图引用，支持 '截图!A65'、'A65'、'65'、多值用 、,; 分隔。"""
    out = []
    if not isinstance(text, str) or not text.strip():
        return out
    for m in REF_RE.finditer(text):
        sheet = m.group(1)
        if sheet and sheet.lower() in ('a',):
            sheet = None
        out.append((sheet, int(m.group(2))))
    return out


def resolve_image(spans_by_sheet, sheet, n):
    """引用行 n → 图片文件名。规则：起始行 n 或 n+1；兜底覆盖区间。"""
    sheets = [sheet] if sheet and sheet in spans_by_sheet else list(spans_by_sheet)
    for sname in sheets:
        spans = spans_by_sheet[sname]
        starts = {s['from']: s for s in spans}
        hit = starts.get(n) or starts.get(n + 1)
        if hit:
            return hit['target'].split('/')[-1], sname
    for sname in sheets:
        for s in spans_by_sheet[sname]:
            if s['from'] <= n <= s['to']:
                return s['target'].split('/')[-1], sname
    return None, None


def parse_file(path):
    """解析单个 xlsx，返回 (file_info, cases)。"""
    z = zipfile.ZipFile(path)
    spans_by_sheet = sheet_drawings(z)
    wb = openpyxl.load_workbook(path, read_only=True)
    best = None  # (score, sheet_name, header_row, mapping, all_rows)
    for ws in wb.worksheets:
        rows = []
        for i, r in enumerate(ws.iter_rows(values_only=True), 1):
            rows.append(r)
            if i >= 15:
                break
        hrow, mapping = detect_header(rows)
        if hrow is None:
            continue
        score = len(mapping)
        if best is None or score > best[0]:
            best = (score, ws.title, hrow, mapping)

    if best is None:
        wb.close()
        raise SystemExit(f'[parse_cases] 未能在 {path} 中识别案例表（需至少命中4个表头关键字）')

    score, sheet_name, hrow, mapping = best
    ws = wb[sheet_name]
    cases = []
    last_module, last_item = '', ''
    header = [c.value for c in next(ws.iter_rows(min_row=hrow + 1, max_row=hrow + 1))]

    for rn, row in enumerate(ws.iter_rows(min_row=hrow + 2, values_only=True), hrow + 2):
        def get(key):
            col = mapping.get(key)
            if col is None or col >= len(row):
                return None
            v = row[col]
            return v.strip() if isinstance(v, str) else v

        title = get('title')
        module = get('module')
        item = get('item')
        if module:
            last_module = module
        if item:
            last_item = item
        if not title and not item and not get('steps'):
            continue
        w = []
        refs = parse_refs(get('shot'))
        images = []
        for sheet, n in refs:
            name, used_sheet = resolve_image(spans_by_sheet, sheet, n)
            if name:
                images.append({'file': os.path.basename(path), 'name': name})
            else:
                w.append(f'截图引用 {sheet or ""}!A{n} 未找到对应图片')
        cases.append({
            'file': os.path.basename(path),
            'row': rn,
            'no': get('no'),
            'module': (module or last_module or '').strip(),
            'item': (item or last_item or '').strip(),
            'title': title,
            'level': get('level'),
            'steps': get('steps'),
            'expect': get('expect'),
            'actual': get('actual'),
            'status': get('status'),
            'shot': get('shot'),
            'images': images,
            'warnings': w,
        })

    unmapped = [norm(v) for j, v in enumerate(header)
                if v and match_header(v)[0] is None]
    wb.close()
    info = {
        'path': os.path.abspath(path),
        'case_sheet': sheet_name,
        'header_row': hrow + 1,
        'shot_sheets': list(spans_by_sheet.keys()),
        'unmapped_headers': [u for u in unmapped if u],
    }
    return info, cases, spans_by_sheet


def export_images(paths, outdir):
    """导出所有 xlsx 内嵌图片到 outdir，命名 f{file_idx}_{name}。"""
    os.makedirs(outdir, exist_ok=True)
    count = 0
    for idx, path in enumerate(paths):
        z = zipfile.ZipFile(path)
        for n in z.namelist():
            if n.startswith('xl/media/'):
                name = n.split('/')[-1]
                with open(os.path.join(outdir, f'f{idx}_{name}'), 'wb') as f:
                    f.write(z.read(n))
                count += 1
    return count


def main():
    ap = argparse.ArgumentParser(description='自适应解析测试案例 xlsx')
    ap.add_argument('--xlsx', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--export-images', default=None)
    args = ap.parse_args()

    all_cases, files, shot_spans, warnings = [], [], {}, []
    for path in args.xlsx:
        info, cases, spans = parse_file(path)
        files.append(info)
        all_cases.extend(cases)
        shot_spans.update(spans)
        warnings.extend(f'{info["case_sheet"]}: {u}' for u in info['unmapped_headers'])

    data = {'files': files, 'cases': all_cases, 'shot_spans': shot_spans, 'warnings': warnings}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    if args.export_images:
        n = export_images(args.xlsx, args.export_images)
        print(f'exported {n} images -> {args.export_images}')

    print(f'files: {len(files)}, cases: {len(all_cases)}')
    for info in files:
        print(f'  [{info["case_sheet"]}] {info["path"]}  shot_sheets={info["shot_sheets"]}'
              f'  unmapped={info["unmapped_headers"]}')
    with_images = sum(1 for c in all_cases if c['images'])
    print(f'cases with images: {with_images}; unresolved refs: '
          f'{sum(1 for c in all_cases if c["warnings"])}')


if __name__ == '__main__':
    main()
