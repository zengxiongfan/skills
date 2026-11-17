# -*- coding: utf-8 -*-
"""verify — 手册自检：结构检查 + Word 更新目录/导出 PDF + 逐页渲染 + QA 报告。

用法：
    python verify.py <手册.docx> [--qa qa-report.md] [--no-word]
                     [--expect-req N] [--pdf out.pdf] [--render-dir dir]
"""
import io
import os
import re
import sys

import docx

CAP_RE = re.compile(r'^图\s*(\d+(?:\.\d+)*)-(\d+)\s')


def word_update_toc(docx_path):
    """用 Word 更新目录域（没有目录则跳过）。"""
    import win32com.client as win32
    word = win32.DispatchEx('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(os.path.abspath(docx_path))
        try:
            if doc.TablesOfContents.Count > 0:
                doc.TablesOfContents.Item(1).Update()
            doc.Save()
        finally:
            doc.Close(False)
    finally:
        word.Quit()


def word_export_pdf(docx_path, pdf_path):
    import win32com.client as win32
    word = win32.DispatchEx('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(os.path.abspath(docx_path), False, True)
        try:
            doc.ExportAsFixedFormat(os.path.abspath(pdf_path), 17)
        finally:
            doc.Close(False)
    finally:
        word.Quit()


def render_pdf(pdf_path, out_dir, scale=1.25):
    import pypdfium2 as pdfium
    os.makedirs(out_dir, exist_ok=True)
    pdf = pdfium.PdfDocument(pdf_path)
    for i in range(len(pdf)):
        pdf[i].render(scale=scale).to_pil().save(
            os.path.join(out_dir, 'page-%02d.png' % (i + 1)))
    return len(pdf)


def update_toc(docx_path):
    word_update_toc(docx_path)


def structural_checks(path, expect_req=None):
    d = docx.Document(path)
    h1 = [p.text.strip() for p in d.paragraphs if p.style.name == 'Heading 1']
    h2 = [p.text.strip() for p in d.paragraphs if p.style.name == 'Heading 2']
    reqs = [t for t in h2 if '需求点' in t]
    caps = [p.text.strip() for p in d.paragraphs if p.text.strip().startswith('图')]
    bad_caps = [c for c in caps if not CAP_RE.match(c)]
    nums = [CAP_RE.match(c).group(0).strip() for c in caps if CAP_RE.match(c)]
    dup = sorted({n for n in nums if nums.count(n) > 1})
    placeholders = [p.text for p in d.paragraphs if '【截图待补充】' in p.text]
    xml = d.element.body.xml
    has_toc_field = 'TOC \\o' in xml or 'TOC \\\\o' in xml
    issues = []
    if bad_caps:
        issues.append('图注格式异常 %d 条（示例：%s）' % (len(bad_caps), bad_caps[0][:40]))
    if dup:
        issues.append('图号重复：%s' % ', '.join(dup[:5]))
    if expect_req is not None and len(reqs) != expect_req:
        issues.append('需求点数量不符：期望 %d，实际 %d' % (expect_req, len(reqs)))
    empty_heads = [t for t in h1 + h2 if not t]
    if empty_heads:
        issues.append('存在空标题')
    return {
        'h1': h1, 'h2': h2, 'reqs': reqs, 'captions': caps,
        'bad_captions': bad_caps, 'dup_captions': dup,
        'placeholders': placeholders, 'has_toc_field': has_toc_field,
        'tables': len(d.tables), 'images': len(d.inline_shapes),
        'issues': issues,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        raise SystemExit('文件不存在: %s' % path)
    qa = sys.argv[sys.argv.index('--qa') + 1] if '--qa' in sys.argv else \
        os.path.splitext(path)[0] + '-qa.md'
    expect = None
    if '--expect-req' in sys.argv:
        expect = int(sys.argv[sys.argv.index('--expect-req') + 1])
    no_word = '--no-word' in sys.argv
    pdf = sys.argv[sys.argv.index('--pdf') + 1] if '--pdf' in sys.argv else \
        os.path.splitext(path)[0] + '_preview.pdf'
    render_dir = sys.argv[sys.argv.index('--render-dir') + 1] if '--render-dir' in sys.argv else \
        os.path.splitext(path)[0] + '_preview'

    info = structural_checks(path, expect)
    pages = None
    word_err = None
    if not no_word:
        try:
            word_update_toc(path)
            word_export_pdf(path, pdf)
            pages = render_pdf(pdf, render_dir)
        except Exception as e:  # noqa: BLE001
            word_err = str(e)

    lines = ['# 操作手册 QA 报告', '',
             '- 文件：`%s`' % os.path.basename(path),
             '- 生成时间：%s' % __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'),
             '', '## 自动检查', '',
             '| 检查项 | 结果 |', '|---|---|',
             '| 一级标题（部分/章节） | %d |' % len(info['h1']),
             '| 需求点（二级标题） | %d |' % len(info['reqs']),
             '| 图注数量 | %d |' % len(info['captions']),
             '| 图注格式异常 | %d |' % len(info['bad_captions']),
             '| 图号重复 | %d |' % len(info['dup_captions']),
             '| 截图占位框 | %d |' % len(info['placeholders']),
             '| 表格 / 图片 | %d / %d |' % (info['tables'], info['images']),
             '| 目录域 | %s |' % ('有' if info['has_toc_field'] else '无'),
             '| Word 转 PDF | %s |' % (('失败：%s' % word_err) if word_err else
                                       (('%d 页' % pages) if pages else '跳过')),
             '', '## 自动检查发现的问题', '']
    lines += ['- %s' % s for s in info['issues']] or ['- 无']
    lines += ['', '## 需求点清单', '']
    lines += ['- %s' % t for t in info['reqs']] or ['- 无']
    lines += ['', '## 待人工确认', '',
              '- [ ] 封面标题、版本号、页眉/页脚是否正确',
              '- [ ] 目录页码是否已更新（Word 打开后如未更新请右键“更新域”）',
              '- [ ] 每张截图内容是否与所在需求点匹配',
              '- [ ] 占位框清单是否与附录一致',
              '- [ ] 表格是否跨页断裂、列宽是否可读']
    io.open(qa, 'w', encoding='utf-8').write('\n'.join(lines))
    print('QA ->', qa)
    print('reqs:', len(info['reqs']), 'captions:', len(info['captions']),
          'placeholders:', len(info['placeholders']), 'pages:', pages)
    for s in info['issues']:
        print('ISSUE:', s)


if __name__ == '__main__':
    main()
