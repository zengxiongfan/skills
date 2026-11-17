# -*- coding: utf-8 -*-
"""extract_case — 从测试案例 xlsx 提取：用例行、内嵌截图、截图锚点映射、缩略图拼版。

用法：
    python extract_case.py <测试案例.xlsx> --out <work>/extract [--no-contact]

产出（<out> 目录）：
    case_rows.txt        各 sheet 的非空行（[R行号] a | b | ...）
    imgs/imageN.png      xl/media 下的全部图片
    anchors_<sheet>_<drawing>.csv   锚点：ref,excel_row,img（ref 即"截图!A{ref}"中的行号）
    ref_image_map.csv    截图类 sheet 的 A{n} -> imageN.png 映射
    contact/sheet_XX.png 缩略图拼版（带图名，供目视选图）
    summary.json         统计信息
"""
import csv
import io
import json
import os
import re
import sys
import zipfile

import openpyxl
from PIL import Image, ImageDraw, ImageFont


def export_rows(wb, out_dir):
    path = os.path.join(out_dir, 'case_rows.txt')
    fo = io.open(path, 'w', encoding='utf-8')
    meta = []
    for idx, ws in enumerate(wb.worksheets):
        rows = 0
        fo.write('\n===== SHEET %d: %s =====\n' % (idx, ws.title))
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            cells = [str(c).strip().replace('\n', ' / ') if c is not None else '' for c in row]
            if any(cells):
                fo.write('[R%d] ' % i + ' | '.join(cells) + '\n')
                rows += 1
        meta.append({'index': idx, 'title': ws.title, 'rows': rows})
    fo.close()
    return meta


def extract_media(z, out_dir):
    imgs = os.path.join(out_dir, 'imgs')
    os.makedirs(imgs, exist_ok=True)
    saved = []
    for name in z.namelist():
        if name.startswith('xl/media/') and not name.endswith('/'):
            dst = os.path.join(imgs, os.path.basename(name))
            with open(dst, 'wb') as f:
                f.write(z.read(name))
            saved.append(os.path.basename(name))
    return sorted(saved, key=lambda x: int(''.join(c for c in x if c.isdigit()) or 0))


def sheet_drawings(z):
    """返回 {sheet_title: drawing_file}"""
    wbxml = z.read('xl/workbook.xml').decode('utf-8')
    names = re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wbxml)
    rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8')
    relmap = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    result = {}
    for title, rid in names:
        target = relmap.get(rid)
        if not target:
            continue
        sheet_file = 'xl/' + target.lstrip('/').replace('xl/', '')
        relfile = 'xl/worksheets/_rels/' + os.path.basename(target) + '.rels'
        if relfile not in z.namelist():
            continue
        r = z.read(relfile).decode('utf-8')
        m = re.search(r'Target="\.\./drawings/(drawing\d+\.xml)"', r)
        if m:
            result[title] = 'xl/drawings/' + m.group(1)
    return result


def parse_anchors(z, drawing_path):
    xml = z.read(drawing_path).decode('utf-8')
    relfile = 'xl/drawings/_rels/' + os.path.basename(drawing_path) + '.rels'
    relmap = {}
    if relfile in z.namelist():
        r = z.read(relfile).decode('utf-8')
        relmap = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', r))
        relmap.update({b: a for a, b in re.findall(r'Target="([^"]+)"[^>]*Id="([^"]+)"', r)})
    anchors = []
    for body in re.findall(r'<xdr:(?:oneCellAnchor|twoCellAnchor)[^>]*>(.*?)</xdr:(?:oneCellAnchor|twoCellAnchor)>',
                           xml, re.S):
        frm = re.search(r'<xdr:from><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>', body, re.S)
        emb = re.search(r'r:embed="([^"]+)"', body)
        if not frm:
            continue
        row0 = int(frm.group(2))
        img = relmap.get(emb.group(1), '') if emb else ''
        img = os.path.basename(img)
        anchors.append({'ref': 'A%d' % row0, 'excel_row': row0 + 1,
                        'col': int(frm.group(1)), 'img': img})
    anchors.sort(key=lambda a: (a['col'], int(a['ref'][1:])))
    return anchors


def contact_sheets(imgs_dir, out_dir, cols=4, rows=5, tw=480, th=230):
    files = sorted([f for f in os.listdir(imgs_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
                   key=lambda x: int(''.join(c for c in x if c.isdigit()) or 0))
    cdir = os.path.join(out_dir, 'contact')
    os.makedirs(cdir, exist_ok=True)
    per = cols * rows
    made = []
    for si in range(0, len(files), per):
        batch = files[si:si + per]
        sheet = Image.new('RGB', (cols * tw, rows * th), 'white')
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(batch):
            im = Image.open(os.path.join(imgs_dir, f)).convert('RGB')
            im.thumbnail((tw, th - 24))
            x, y = (i % cols) * tw, (i // cols) * th
            sheet.paste(im, (x, y + 24))
            d.text((x + 6, y + 6), f, fill='red')
        out = os.path.join(cdir, 'sheet_%02d.png' % (si // per + 1))
        sheet.save(out)
        made.append(out)
    return made


def main():
    if len(sys.argv) < 2:
        print('usage: python extract_case.py <case.xlsx> --out <dir> [--no-contact]')
        sys.exit(2)
    xlsx = sys.argv[1]
    out_dir = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'extract'
    os.makedirs(out_dir, exist_ok=True)

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    sheets = export_rows(wb, out_dir)
    z = zipfile.ZipFile(xlsx)
    images = extract_media(z, out_dir)

    drawings = sheet_drawings(z)
    anchors_info = {}
    ref_map = {}
    for title, dpath in drawings.items():
        anchors = parse_anchors(z, dpath)
        anchors_info[title] = anchors
        csv_name = 'anchors_%s_%s.csv' % (re.sub(r'[^\w]+', '_', title), os.path.basename(dpath).replace('.xml', ''))
        with io.open(os.path.join(out_dir, csv_name), 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['ref', 'excel_row', 'col', 'img'])
            for a in anchors:
                w.writerow([a['ref'], a['excel_row'], a['col'], a['img']])
        for a in anchors:
            ref_map[(title, a['ref'])] = a['img']
    # 按 sheet 输出映射（测试案例引用形如 截图!A1，需按 sheet 区分）
    by_sheet = {}
    for (title, ref), img in ref_map.items():
        by_sheet.setdefault(title, []).append((ref, img))
    with io.open(os.path.join(out_dir, 'ref_image_map.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['sheet', 'ref', 'img'])
        for title in by_sheet:
            for ref, img in sorted(by_sheet[title], key=lambda x: int(x[0][1:])):
                w.writerow([title, ref, img])
    for title, items in by_sheet.items():
        safe = re.sub(r'[^\w]+', '_', title)
        with io.open(os.path.join(out_dir, 'refmap_%s.csv' % safe), 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['ref', 'img'])
            for ref, img in sorted(items, key=lambda x: int(x[0][1:])):
                w.writerow([ref, img])

    contacts = [] if '--no-contact' in sys.argv else contact_sheets(os.path.join(out_dir, 'imgs'), out_dir)

    summary = {
        'case': os.path.basename(xlsx),
        'sheets': sheets,
        'images': len(images),
        'drawings': {k: len(v) for k, v in anchors_info.items()},
        'refs': len(ref_map),
        'ref_sheets': {k: len(v) for k, v in by_sheet.items()},
        'contact_sheets': [os.path.basename(c) for c in contacts],
    }
    io.open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8').write(
        json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
