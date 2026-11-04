#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""标准实施费用模板生成器（req-workload-estimate skill）

读取与 gen_estimate.py 相同的 tasks.json，在 standard_template.enabled=true 时
额外生成一份 7 阶段的标准模板：
  项目管理 / 需求阶段 / 设计阶段 / 开发阶段 / 测试阶段 / 验收阶段 / 版本管理及上线发布

规则：
  - 管理/需求/设计/开发/测试五段合计，分别对齐 10 列评估表的对应列小计
  - 项目管理按 pm_split（默认 1:1:3）拆分；需求按 req_split（默认 3:1:1）拆分
  - 设计/测试阶段镜像开发任务分类，排除 self_test_category（默认“开发联调与回归自测”）
  - 测试阶段另加固定行“测试用例编写及评审”2 天
  - 验收默认 5 天；版本管理及上线发布默认 1/1/1
  - 费率默认：1846/1846/1261/1261/1030/1261/1261，可在 standard_template.rates 覆盖
  - 写入 WPS KSOReadingLayout=true，打开即启用阅读模式（行/列聚焦）

用法:
    python gen_std_template.py tasks.json -o 工作量评估_需求名_标准模板.xlsx
"""
import argparse
import json
import math
import os
import re
import sys
import zipfile

import openpyxl
from openpyxl.packaging.custom import BoolProperty, StringProperty
from openpyxl.styles import Alignment, Border, Font, Side

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from estimate_common import ceil_to_half, group_tasks, self_test_category, split_ratio

FONT = "宋体"
THIN = Side(style="thin")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MONEY = '\\¥#,##0.00_);[Red]\\(\\¥#,##0.00\\)'
DEFAULT_RATES = {"pm": 1846, "req": 1846, "design": 1261, "dev": 1261,
                 "test": 1030, "uat": 1261, "rel": 1261}
PHASE_RATE_KEY = {"pm": "pm", "req": "req", "design": "design", "dev": "dev",
                  "test": "test", "uat": "uat", "rel": "rel"}


def _style(cell, bold=False, align="center", money=False):
    cell.font = Font(name=FONT, size=10, bold=bold)
    cell.border = BORDER
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
    if money:
        cell.number_format = MONEY


def _std_title(data):
    cfg = data.get("standard_template") or {}
    if cfg.get("title"):
        return cfg["title"]
    title = data.get("title", "工作量评估")
    m = re.search(r"【(.+?)】", title)
    name = m.group(1) if m else title
    return f"{name}-工作量评估"


def _ensure_estimates(data):
    # 复用 10 列脚本的自动补全（含设计/测试排除自测分类）
    from gen_estimate import apply_auto_estimates
    apply_auto_estimates(data)


def build_standard_template(data, output):
    """构建并保存标准模板，返回汇总信息 dict。"""
    _ensure_estimates(data)
    cfg = data.get("standard_template")
    if not isinstance(cfg, dict):
        cfg = {}
    rates = dict(DEFAULT_RATES)
    rates.update({k: v for k, v in (cfg.get("rates") or {}).items() if k in rates})
    self_test = self_test_category(data)
    tasks = data["tasks"]
    groups = group_tasks(tasks)
    dev_groups = [g for g in groups if g["category"] != self_test]
    first = lambda g, key: float(g["tasks"][0].get(key) or 0)

    mgmt_total = sum(first(g, "mgmt") for g in groups)
    req_total = sum(first(g, "req") for g in groups)
    design_of = {g["category"]: first(g, "design") for g in dev_groups}
    test_of = {g["category"]: first(g, "test") for g in dev_groups}
    design_total = round(sum(design_of.values()), 6)
    test_total = round(sum(test_of.values()), 6)
    dev_total = round(sum(float(t["days"]) for t in tasks), 6)

    pm_split = cfg.get("pm_split") or [1, 1, 3]
    req_split = cfg.get("req_split") or [3, 1, 1]
    pm_days = split_ratio(mgmt_total, pm_split)
    req_days = split_ratio(req_total, req_split)
    acceptance = float(cfg.get("acceptance_days", 5))
    release_days = [float(x) for x in (cfg.get("release_days") or [1, 1, 1])]

    # 预计算各段行号，保证公式范围随任务数动态变化
    n_design = sum(len(g["tasks"]) for g in dev_groups)
    n_dev = len(tasks)
    n_test = 1 + n_design
    design_start = 17
    design_end = design_start + n_design - 1
    dev_start = design_end + 2
    dev_end = dev_start + n_dev - 1
    test_start = dev_end + 2
    test_end = test_start + n_test - 1
    uat_row = test_end + 2
    rel_start = uat_row + 2
    rel_end = rel_start + 2

    wb = openpyxl.Workbook()
    wb.calculation.fullCalcOnLoad = True
    ws = wb.active
    ws.title = "Sheet1"
    for col, w in (("A", 4.5), ("B", 21), ("C", 29.2), ("D", 66.7),
                   ("E", 11.5), ("F", 16.3), ("G", 29.2), ("H", 16.9)):
        ws.column_dimensions[col].width = w

    r = 1
    ws.cell(r, 1, _std_title(data))
    ws.merge_cells("A1:G1")
    for c in range(1, 8):
        _style(ws.cell(r, c), bold=True)
    ws.row_dimensions[r].height = 24

    info = cfg.get("project_info") or {}
    for label, key in (("项目背景", "background"), ("项目范围说明", "scope"),
                       ("项目经理", "manager"), ("影响用户", "users"), ("解决问题", "problems")):
        r += 1
        ws.cell(r, 1, label)
        ws.cell(r, 3, info.get(key, ""))
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=7)
        for c in range(1, 8):
            _style(ws.cell(r, c))
        ws.cell(r, 1).font = Font(name=FONT, size=10, bold=True)
        if key == "scope":
            ws.row_dimensions[r].height = 29

    r += 1
    for i, h in enumerate(["序号", "任务分类", "子任务", "任务事项",
                           "工作量（人/天）", "实施费用", "备注"], 1):
        ws.cell(r, i, h)
        _style(ws.cell(r, i), bold=True)
    ws.row_dimensions[r].height = 24

    def section(title, total_range):
        nonlocal r
        r += 1
        ws.cell(r, 1, "=ROW()-7")
        ws.cell(r, 2, f'="{title}："&SUM({total_range})&"人/天"')
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        for c in range(1, 8):
            _style(ws.cell(r, c), bold=True, align="left" if c == 2 else "center")

    def data_row(task_cat, subtask, item, e, rate):
        nonlocal r
        r += 1
        ws.cell(r, 1, "=ROW()-7")
        if task_cat is not None:
            ws.cell(r, 2, task_cat)
        if subtask is not None:
            ws.cell(r, 3, subtask)
        if item is not None:
            ws.cell(r, 4, item)
        if e is not None:
            ws.cell(r, 5, e)
        ws.cell(r, 6, f"=E{r}*{rate}")  # 每个数据行都带本板块费率公式
        for c in range(1, 8):
            _style(ws.cell(r, c), align="left" if c in (3, 4) else "center", money=(c == 6))

    # 一、项目管理
    section("一、项目管理", "E9:E11")
    for name, desc, days in zip(
            ["项目计划", "工作量评估", "实施管理"],
            ["制定及更新项目实施开发计划",
             "评估项目实施工作量（含需求、开发、测试、UAT、上线）",
             "项目实施过程人员、进度、沟通、风险、质量管理"],
            pm_days):
        data_row(name, desc, None, days, rates["pm"])
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)

    # 二、需求阶段
    section("二、需求阶段", "E13:E15")
    for name, desc, days in zip(
            ["需求分析", "需求文档编写", "需求评审、确认"],
            ["原始需求文档分析、需求沟通", "需求文档编写", "需求文档评审、确认"],
            req_days):
        data_row(name, desc, None, days, rates["req"])
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)

    # 三、设计阶段（镜像开发分组，排除自测；C=子任务，D=子任务+功能设计）
    section("三、设计阶段", f"E{design_start}:E{design_end}")
    for g in dev_groups:
        start = r + 1
        for t in g["tasks"]:
            data_row(g["category"] if t is g["tasks"][0] else None,
                     t["subtask"],
                     t["subtask"] + "，功能设计与设计文档编写",
                     design_of[g["category"]] if t is g["tasks"][0] else None,
                     rates["design"])
        if r > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=r, end_column=2)
            ws.merge_cells(start_row=start, start_column=5, end_row=r, end_column=5)

    # 四、开发阶段
    section("四、开发阶段", f"E{dev_start}:E{dev_end}")
    for g in groups:
        start = r + 1
        for t in g["tasks"]:
            data_row(g["category"] if t is g["tasks"][0] else None,
                     t["subtask"], t["item"], t["days"], rates["dev"])
        if r > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=r, end_column=2)

    # 五、测试阶段（固定用例编写 2 天 + 分组测试，C/D 同文合并）
    section("五、测试阶段", f"E{test_start}:E{test_end}")
    data_row("测试用例编写及评审", None, None, 2, rates["test"])
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    for g in dev_groups:
        start = r + 1
        for t in g["tasks"]:
            text = t["subtask"] + "，测试案例执行"
            data_row(g["category"] if t is g["tasks"][0] else None,
                     text, text,
                     test_of[g["category"]] if t is g["tasks"][0] else None,
                     rates["test"])
            ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        if r > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=r, end_column=2)
            ws.merge_cells(start_row=start, start_column=5, end_row=r, end_column=5)

    # 六、验收阶段
    section("六、验收阶段", f"E{uat_row}:E{uat_row}")
    data_row("UAT测试", "测试支持", None, acceptance, rates["uat"])
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)

    # 七、版本管理及上线发布
    section("七、版本管理及上线发布", f"E{rel_start}:E{rel_end}")
    start = r + 1
    for desc, days in zip(["预生产回归验证", "配合生产环境发布上线", "系统试运行支持"],
                          (release_days + [0, 0, 0])[:3]):
        data_row("预生产回归与投产上线支持" if desc == "预生产回归验证" else None,
                 desc, None, days, rates["rel"])
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
    ws.merge_cells(start_row=start, start_column=2, end_row=r, end_column=2)

    # 总计
    r += 1
    ws.cell(r, 1, "=ROW()-7")
    ws.cell(r, 2, "总计工作量")
    ws.cell(r, 5, f"=SUM(E9:E{r-1})")
    ws.cell(r, 6, f"=SUM(F9:F{r-1})")
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    for c in range(1, 8):
        _style(ws.cell(r, c), bold=True, money=(c == 6))
    ws.freeze_panes = "A8"

    # 数据行高按 C/D 文本长度估算
    for rr in range(8, r + 1):
        ctext = str(ws.cell(rr, 3).value or "")
        dtext = str(ws.cell(rr, 4).value or "")
        lines = max(math.ceil(len(ctext) / 28), math.ceil(len(dtext) / 64), 1)
        ws.row_dimensions[rr].height = max(24, lines * 15 + 6)

    # WPS 阅读模式（行/列聚焦）
    wb.custom_doc_props.append(StringProperty("KSOProductBuildVer", "2052-12.1.0.29161"))
    wb.custom_doc_props.append(BoolProperty("KSOReadingLayout", True))

    wb.save(output)
    # vt:bool 与 WPS 模板保持一致，写 true 而非 1
    tmp = output + ".tmp"
    with zipfile.ZipFile(output) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            blob = zin.read(item.filename)
            if item.filename == "docProps/custom.xml":
                blob = blob.replace(b"<vt:bool>1</vt:bool>", b"<vt:bool>true</vt:bool>")
            zout.writestr(item, blob)
    os.replace(tmp, output)

    total = (mgmt_total + req_total + design_total + dev_total + 2 + test_total
             + acceptance + sum(release_days[:3]))
    amount = (mgmt_total * rates["pm"] + req_total * rates["req"]
              + design_total * rates["design"] + dev_total * rates["dev"]
              + (2 + test_total) * rates["test"] + acceptance * rates["uat"]
              + sum(release_days[:3]) * rates["rel"])
    return {"path": output, "total": round(total, 6), "amount": round(amount, 2),
            "mgmt": mgmt_total, "req": req_total, "design": design_total,
            "dev": dev_total, "test": 2 + test_total, "uat": acceptance,
            "release": sum(release_days[:3]), "test_of": test_of,
            "design_of": design_of, "pm_days": pm_days, "req_days": req_days}


def main():
    ap = argparse.ArgumentParser(description="标准实施费用模板生成器")
    ap.add_argument("json_file", help="tasks.json 路径")
    ap.add_argument("-o", "--output", default="工作量评估_标准模板.xlsx", help="输出 xlsx 路径")
    args = ap.parse_args()
    with open(args.json_file, encoding="utf-8") as f:
        data = json.load(f)
    info = build_standard_template(data, args.output)
    print(f"已生成: {info['path']}")
    print(f"五列: 管理{info['mgmt']:g} 需求{info['req']:g} 设计{info['design']:g} "
          f"开发{info['dev']:g} 测试{info['test']:g}（含用例编写2）")
    print(f"验收{info['uat']:g} 版本{info['release']:g}；总计 {info['total']:g} 人天 / {info['amount']:,.2f} 元")


if __name__ == "__main__":
    main()
