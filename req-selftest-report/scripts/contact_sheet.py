# -*- coding: utf-8 -*-
"""阶段3 辅助：把未被选中案例引用的图片拼成带编号的总览图，排查漏图。

用法：
  python contact_sheet.py --data iter_data.json --media-dir all_images \
      --selected selected.json --outdir scan [--cols 4 --rows 5]

说明：
  media-dir 由 parse_cases.py --export-images 生成（命名 f{file_idx}_{name}）；
  selected.json 由 pick_cases.py 生成。
"""
import argparse
import json
import os
import re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--media-dir', required=True)
    ap.add_argument('--selected', required=True)
    ap.add_argument('--outdir', default='scan')
    ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--rows', type=int, default=5)
    ap.add_argument('--thumb-width', type=int, default=470)
    args = ap.parse_args()

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise SystemExit('[contact_sheet] 缺少 Pillow')

    data = json.load(open(args.data, encoding='utf-8'))
    selected = json.load(open(args.selected, encoding='utf-8'))
    file_ids = {f['path'].split(os.sep)[-1]: i for i, f in enumerate(data['files'])}

    used = set()
    for c in selected:
        for img in c.get('images') or []:
            idx = file_ids.get(img['file'])
            if idx is not None:
                used.add(f'f{idx}_{img["name"]}')

    all_imgs = [n for n in os.listdir(args.media_dir)
                if n.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
    all_imgs.sort(key=lambda x: (int(re.search(r'^f(\d+)_', x).group(1)) if re.search(r'^f(\d+)_', x) else 0,
                                 int(re.search(r'(\d+)', x.split('_')[-1]).group(1)) if re.search(r'(\d+)', x.split('_')[-1]) else 0))
    unused = [n for n in all_imgs if n not in used]
    print(f'images: {len(all_imgs)}, used: {len(all_imgs) - len(unused)}, unused: {len(unused)}')
    if not unused:
        return

    os.makedirs(args.outdir, exist_ok=True)
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    except OSError:
        font = ImageFont.load_default()

    per_sheet = args.cols * args.rows
    tw = args.thumb_width
    for start in range(0, len(unused), per_sheet):
        chunk = unused[start:start + per_sheet]
        thumbs = []
        for name in chunk:
            im = Image.open(os.path.join(args.media_dir, name))
            h = int(im.height * tw / im.width)
            thumbs.append((name, im.resize((tw, h))))
        row_h = [max(t[1].height for t in thumbs[i:i + args.cols]) + 30
                 for i in range(0, len(thumbs), args.cols)]
        width = args.cols * (tw + 10) + 10
        sheet = Image.new('RGB', (width, sum(row_h) + 10), 'white')
        d = ImageDraw.Draw(sheet)
        y = 5
        ri = 0
        for i in range(0, len(thumbs), args.cols):
            x = 5
            for name, t in thumbs[i:i + args.cols]:
                sheet.paste(t, (x, y + 28))
                d.rectangle([x - 2, y + 26, x + tw + 2, y + 30 + t.height], outline='red')
                d.text((x, y + 2), name, fill='red', font=font)
                x += tw + 10
            y += row_h[ri] + 5
            ri += 1
        out = os.path.join(args.outdir, f'sheet_{start // per_sheet + 1}.png')
        sheet.save(out)
        print('saved', out)


if __name__ == '__main__':
    main()
