# -*- coding: utf-8 -*-
"""工作量评估 skill 公共工具：取整、比例拆分、任务分组、输出命名。"""
import math
import os
import re

DEFAULT_SELF_TEST = "开发联调与回归自测"


def ceil_to_half(value):
    """向上取整到 0.5：0.1→0.5，0.5→0.5，0.9→1.0，1.6→2.0。"""
    return math.ceil(round(value * 2, 6)) / 2


def split_ratio(total, ratio):
    """按比例拆成 0.5 步长，保证合计等于 total；余数给比例最大项。"""
    s = sum(ratio)
    raw = [total * r / s for r in ratio]
    vals = [max(0.0, math.floor(v * 2) / 2) for v in raw]
    diff = round(total - sum(vals), 6)
    i = raw.index(max(raw))
    vals[i] = round(vals[i] + diff, 6)
    return vals


def group_tasks(tasks):
    """按任务分类切块；category 留空表示沿用上一类。返回 [{'category','tasks'}]。"""
    groups, cur = [], ""
    for t in tasks:
        if t.get("category"):
            cur = t["category"]
        if not groups or groups[-1]["category"] != cur:
            groups.append({"category": cur, "tasks": []})
        groups[-1]["tasks"].append(t)
    return groups


def self_test_category(data):
    cfg = data.get("standard_template")
    if isinstance(cfg, dict):
        return cfg.get("self_test_category", DEFAULT_SELF_TEST)
    return DEFAULT_SELF_TEST


def derive_std_output(output):
    """工作量评估_需求_v5.xlsx → 工作量评估_需求_标准模板_v5.xlsx"""
    stem, ext = os.path.splitext(output)
    m = re.search(r"(_v\d+)$", stem)
    if m:
        return f"{stem[:m.start()]}_标准模板{m.group(1)}{ext}"
    return f"{stem}_标准模板{ext}"


_DOC_TYPE_RE = re.compile(
    r"[-_\s]*(?:需求规格说明书|需求说明书|需求文档)(?:[-_\s]*[vV]?\d+(?:\.\d+)*)?\s*$",
    re.IGNORECASE,
)
_DOC_VER_RE = re.compile(r"[-_\s]*[vV]\d+(?:\.\d+)*\s*$", re.IGNORECASE)


def simplify_doc_name(source):
    """需求文档名精简：去扩展名、去尾部“需求规格说明书v0.1”和版本号。"""
    name = os.path.splitext(os.path.basename(str(source).strip()))[0]
    name = _DOC_TYPE_RE.sub("", name)
    name = _DOC_VER_RE.sub("", name)
    name = re.sub(r"[-_\s]+$", "", name).strip()
    return name or os.path.splitext(os.path.basename(str(source).strip()))[0]


def build_output_base(source, suffix="工作量评估"):
    """RCP-20009-公共保额要素转化--需求规格说明书v0.1.docx → RCP-20009-公共保额要素转化-工作量评估"""
    stem = simplify_doc_name(source)
    m = re.match(r"^【(.+?)】\s*(.*)$", stem)
    if m:
        stem = (m.group(1) + m.group(2)).strip()
    if stem.endswith(suffix):
        stem = stem[: -len(suffix)].rstrip("-_ ")
    if not stem:
        return suffix
    return f"{stem}-{suffix}"


def next_version(outdir, base):
    """扫描输出目录下 10 列与标准模板文件，返回下一个 _vN 的 N（从 1 开始）。"""
    pattern = re.compile(re.escape(base) + r"_v(\d+)\.xlsx$", re.IGNORECASE)
    pattern_std = re.compile(re.escape(base) + r"_标准模板_v(\d+)\.xlsx$", re.IGNORECASE)
    max_v = 0
    if os.path.isdir(outdir):
        for fn in os.listdir(outdir):
            m = pattern.match(fn) or pattern_std.match(fn)
            if m:
                max_v = max(max_v, int(m.group(1)))
    return max_v + 1
