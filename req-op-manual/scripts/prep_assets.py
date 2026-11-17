# -*- coding: utf-8 -*-
"""prep_assets — 按映射表裁剪/重命名截图，输出到 assets 目录。

用法：
    python prep_assets.py --map figures.json --out assets [--default-crop-top 0]

figures.json 示例：
[
  {"src": "work/extract/imgs/image9.png",  "dst": "fig2_1_hosp_group.png", "crop_top": 0},
  {"src": "work/extract/imgs/image151.png","dst": "fig7_2_supp_hosp.png",  "crop_top": 90},
  {"src": "work/extract/imgs/image4.png",  "dst": "fig2_3_scope.png",
   "crop_box": [1180, 330, 1830, 760]},
  {"src": "work/extract/imgs/image17.png", "dst": "fig6_2_grad.png", "max_width": 1600}
]
"""
import io
import json
import os
import sys

from PIL import Image


def main():
    if '--map' not in sys.argv:
        print(__doc__)
        sys.exit(2)
    map_path = sys.argv[sys.argv.index('--map') + 1]
    out_dir = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'assets'
    default_top = 0
    if '--default-crop-top' in sys.argv:
        default_top = int(sys.argv[sys.argv.index('--default-crop-top') + 1])
    os.makedirs(out_dir, exist_ok=True)

    items = json.load(io.open(map_path, encoding='utf-8'))
    report = []
    for it in items:
        src, dst = it.get('src'), it.get('dst')
        if not src or not dst:
            raise ValueError('map item missing src/dst: %r' % it)
        if not os.path.exists(src):
            raise FileNotFoundError(src)
        im = Image.open(src).convert('RGB')
        box = it.get('crop_box')
        if box:
            im = im.crop(tuple(int(v) for v in box))
        else:
            top = int(it.get('crop_top', default_top))
            if top:
                im = im.crop((0, top, im.size[0], im.size[1]))
        mw = it.get('max_width')
        if mw and im.size[0] > int(mw):
            ratio = int(mw) / float(im.size[0])
            im = im.resize((int(mw), int(im.size[1] * ratio)), Image.LANCZOS)
        out = os.path.join(out_dir, dst)
        im.save(out, optimize=True)
        report.append({'dst': dst, 'size': list(im.size)})
        print('%-40s %s' % (dst, im.size))

    io.open(os.path.join(out_dir, 'prep_report.json'), 'w', encoding='utf-8').write(
        json.dumps(report, ensure_ascii=False, indent=2))
    print('prepared %d images -> %s' % (len(report), out_dir))


if __name__ == '__main__':
    main()
