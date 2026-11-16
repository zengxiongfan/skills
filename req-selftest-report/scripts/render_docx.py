# -*- coding: utf-8 -*-
"""阶段5：docx → PDF → PNG（Word COM + PyMuPDF），供逐页视觉验收。

用法：
  python render_docx.py --docx “xxx-已填写.docx” --outdir render [--dpi 110] [--pdf-only]
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--docx', required=True)
    ap.add_argument('--outdir', default='render')
    ap.add_argument('--dpi', type=int, default=110)
    ap.add_argument('--pdf-only', action='store_true')
    args = ap.parse_args()

    src = os.path.abspath(args.docx)
    if not os.path.exists(src):
        sys.exit(f'[render] 文件不存在: {src}')
    os.makedirs(args.outdir, exist_ok=True)
    pdf_path = os.path.join(os.path.abspath(args.outdir), 'report.pdf')

    try:
        import pythoncom
        import win32com.client
    except ImportError:
        sys.exit('[render] 缺少 pywin32；Windows 下请用装有依赖的 Python 运行')

    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(src, ReadOnly=True)
        doc.ExportAsFixedFormat(pdf_path, 17)  # 17 = wdExportFormatPDF
        doc.Close(False)
    finally:
        word.Quit()

    print('pdf:', pdf_path)
    if args.pdf_only:
        return
    try:
        import fitz
    except ImportError:
        sys.exit('[render] 缺少 PyMuPDF；无法转 PNG')

    pdf = fitz.open(pdf_path)
    for i, page in enumerate(pdf, 1):
        out = os.path.join(args.outdir, f'page_{i:02d}.png')
        page.get_pixmap(dpi=args.dpi).save(out)
        print('saved', out)
    print('pages:', pdf.page_count)


if __name__ == '__main__':
    main()
