# -*- coding: utf-8 -*-
"""merge_core — 跨文档复制的底层能力：大纲解析、元素复制（图片去重）、文本工具。"""
import re
from copy import deepcopy
from io import BytesIO

from docx import Document
from docx.oxml.ns import qn


def p_style_id(p_el):
    pPr = p_el.find(qn('w:pPr'))
    if pPr is None:
        return ''
    st = pPr.find(qn('w:pStyle'))
    return st.get(qn('w:val')) if st is not None else ''


def p_text(p_el):
    return ''.join(t.text or '' for t in p_el.iter(qn('w:t')))


def strip_number(text):
    return re.sub(r'^\s*\d+(\.\d+)*\s*', '', text).strip()


def copy_element(target_part, src_part, element):
    """深拷贝元素并重建图片关系（避免多文档图片 partname 冲突）。"""
    el = deepcopy(element)
    for blip in el.iter(qn('a:blip')):
        rid = blip.get(qn('r:embed'))
        if rid and rid in src_part.related_parts:
            img_part = src_part.related_parts[rid]
            new_rid, _ = target_part.get_or_add_image(BytesIO(img_part.blob))
            blip.set(qn('r:embed'), new_rid)
    return el


def parse_outline(path):
    """解析一本操作手册：需求点（H1）、子节（H2）、开篇简介、附录行。

    兼容两种手册：
      A. 含"1 手册说明"开篇章节（六本单本手册）
      B. 直接从"1 RCP-..."需求部分开始（整合版手册）
    """
    src = Document(path)
    body = src.element.body
    outline = []
    intro = []
    appendix_rows = []
    started = False
    in_intro = False
    in_appendix = False
    for child in body.iterchildren():
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            sid = p_style_id(child)
            text = p_text(child).strip()
            if not started:
                if sid != 'Heading1':
                    continue
                norm = re.sub(r'\s+', '', strip_number(text))
                if norm in ('文档信息', '目录'):
                    continue
                started = True
                if '手册说明' in text:
                    in_intro = True
                    continue
            if in_intro:
                if sid == 'Heading1':
                    in_intro = False
                else:
                    if text and len(intro) < 2:
                        intro.append(text)
                    continue
            if in_appendix:
                continue
            if sid == 'Heading1':
                if '附录' in text:
                    in_appendix = True
                    continue
                outline.append({'title': strip_number(text), 'subs': []})
                continue
            if sid == 'Heading2' and outline:
                outline[-1]['subs'].append(strip_number(text))
                continue
        elif tag == 'tbl':
            if in_appendix:
                rows = []
                for tr in child.iter(qn('w:tr')):
                    cells = []
                    for tc in tr.iter(qn('w:tc')):
                        cells.append(''.join(t.text or '' for t in tc.iter(qn('w:t'))).strip())
                    rows.append(cells)
                appendix_rows.extend(rows)
    return outline, intro, appendix_rows


def map_chapter(cell, part_no):
    """附录"对应章节"重编号：旧 2.2 → 新 P.1.2（旧第1章为手册说明）。"""
    cell = (cell or '').strip()
    if not re.match(r'^\d+(\.\d+)*$', cell):
        return cell
    parts = cell.split('.')
    old = int(parts[0])
    if old < 2:
        return cell
    k = old - 1
    return '.'.join([str(part_no), str(k)] + parts[1:])
