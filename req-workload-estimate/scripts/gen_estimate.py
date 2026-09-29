#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作量评估表生成器（req-workload-estimate skill）

用法:
    python gen_estimate.py tasks.json [-o 输出.xlsx]
    python gen_estimate.py --example            # 打印 JSON 样例

tasks.json 结构:
{
  "title": "【需求名】工作量评估",
  "tasks": [
    {"no": 1, "category": "任务分类（同类留空则纵向合并）", "subtask": "子任务",
     "item": "任务事项（业务语言，禁代码类名称）", "days": 2,
     "source": "对应需求原文点（章节号+原文摘录，可含〔对照现状〕〔依据〕标注）"}
  ],
  "reverse": [
    {"point": "§4.1.1", "summary": "原文摘要", "tasks": "5；4〔审批区范围依据〕"}
  ],
  "notes": ["1、上表为开发工作量，不含……", "2、……"]
}

生成:
  Sheet1 工作量评估表 —— 模板六列 + 合计行 + 备注行（任务分类纵向合并）
  Sheet2 需求原文-开发点对照 —— 反查表（某条原文涉及哪些开发）

自检:
  全表正则扫描疑似代码类名称（文件名/驼峰标识/全大写标识/SQL词），命中即打印告警。
  对外交付的描述必须用业务语言，命中说明混入了代码类名称，需改 JSON 后重跑。
"""
import sys
import json
import math
import argparse
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side

FONT = "SimSun"
thin = Side(style="thin")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HEADERS = ["序号", "任务分类", "子任务", "任务事项", "开发工作量(人/天)", "对应需求原文点"]

# 自检：疑似代码类名称（对外交付须用业务语言；GHB/NGB/JV/TOB 等三字母业务线缩写不会命中）
_CODE_NAME_PATTERNS = {
    "文件名/路径": r"[A-Za-z_]+\.(?:html|js|java|xml|sql|xlsx|docx|properties)\b",
    "驼峰标识符": r"\b[a-z]+[A-Z][A-Za-z]{2,}\b",
    "全大写标识": r"\b[A-Z]{4,}[A-Z_]*\b",
    "SQL/框架词": r"\b(?:sql|mapper|mybatis|select|from|where)\b",
}

EXAMPLE = {
    "title": "【示例需求】工作量评估",
    "tasks": [
        {"no": 1, "category": "案件审核/审批结论区调整（需求§4.1）",
         "subtask": "通融给付：天数/次数默认值与编辑态",
         "item": "【案件审核】【案件审批】页面，案件结论为“通融给付”且「通融计入福利」为“否”时，"
                 "「天数是否累计」「次数是否累计」由现行“自动隐藏并强制置为是”调整为"
                 "“显示、默认否、置灰不可编辑”；含审核结论区、审批结论区两处联动改造。",
         "days": 2,
         "source": "§4.1.2 调整后描述①：案件结论为'通融给付'的案件：「通融计入福利」为否时，"
                   "「次数是否累计」和「天数是否累计」均默认为'否'，且不支持编辑。"
                   "〔对照现状描述①：为否时支持查询并编辑〕"},
        {"no": 2, "category": "",
         "subtask": "赔付审定：天数/次数默认值与编辑态",
         "item": "【案件审核】【案件审批】页面，案件结论为“赔付审定”且「赔付审定计入福利」为“否”时，"
                 "「天数是否累计」「次数是否累计」默认为“否”且不可编辑。",
         "days": 2,
         "source": "§4.1.2 调整后描述②：……"},
    ],
    "reverse": [
        {"point": "§4.1.1", "summary": "功能位置：【案件审核】【案件审批】【赔案查询】",
         "tasks": "5；4〔审批区范围依据〕"},
        {"point": "§4.1.2 调整后①", "summary": "通融给付：为否时次数/天数默认'否'且不支持编辑", "tasks": "1"},
    ],
    "notes": [
        "1、上表为开发工作量，不含需求澄清、技术方案评审、测试用例编写与系统测试工作量。",
        "2、序号 2 为条件项，如业务确认无需处理，则合计为 2 人天。",
    ],
}


def load_data(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not data.get("tasks"):
        raise SystemExit("tasks.json 缺少 tasks 数组")
    for i, t in enumerate(data["tasks"], 1):
        for field in ("no", "subtask", "item", "days"):
            if t.get(field) in (None, ""):
                raise SystemExit(f"第 {i} 个任务缺少字段 {field}")
        if not isinstance(t["days"], (int, float)):
            raise SystemExit(f"第 {i} 个任务 days 必须是数字")
    return data


def build_workbook(data):
    title = data.get("title", "工作量评估")
    tasks = data["tasks"]
    reverse = data.get("reverse", [])
    notes = data.get("notes", [])

    wb = openpyxl.Workbook()

    # ============ Sheet1：工作量评估表 ============
    ws = wb.active
    ws.title = "工作量评估表"

    ws["A1"] = title
    ws.merge_cells("A1:F1")
    ws["A1"].font = Font(name=FONT, size=10, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    for i, h in enumerate(HEADERS, start=1):
        c = ws.cell(2, i, h)
        c.font = Font(name=FONT, size=10, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER

    r = 3
    for t in tasks:
        for i, v in enumerate((t["no"], t.get("category", ""), t["subtask"],
                                t["item"], t["days"], t.get("source", "")), start=1):
            ws.cell(r, i, v)
        for col in range(1, 7):
            c = ws.cell(r, col)
            c.font = Font(name=FONT, size=10)
            c.border = BORDER
            if col in (1, 2, 5):
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        # 行高按任务事项/原文点文本长度估算
        lines = max(math.ceil(len(str(t["item"])) / 34),
                    math.ceil(len(str(t.get("source", ""))) / 30), 1)
        ws.row_dimensions[r].height = max(24, lines * 15 + 6)
        r += 1

    # 任务分类纵向合并（连续空 category 归并到上一个非空分类）
    def merge_category(start, end):
        if end > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=end, end_column=2)

    cur, start = None, 3
    for idx, t in enumerate(tasks):
        row = idx + 3
        if t.get("category"):
            if cur is not None:
                merge_category(start, row - 1)
            cur, start = t["category"], row
    merge_category(start, r - 1)

    # 合计行（只合计人天；需求覆盖情况见 Sheet2，不在本行重复）
    total = sum(t["days"] for t in tasks)
    ws.cell(r, 1, "合计")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    ws.cell(r, 5, total)
    for col in range(1, 7):
        c = ws.cell(r, col)
        c.font = Font(name=FONT, size=10, bold=True)
        c.border = BORDER
        c.alignment = Alignment(horizontal="center" if col == 5 else "right",
                                vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 24

    # 备注行
    if notes:
        r += 1
        ws.cell(r, 1, "\n".join(notes))
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        ws.cell(r, 1).font = Font(name=FONT, size=9)
        ws.cell(r, 1).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = max(60, 16 * len(notes) + 20)

    for col, w in (("A", 6), ("B", 26), ("C", 26), ("D", 68), ("E", 13), ("F", 56)):
        ws.column_dimensions[col].width = w

    # ============ Sheet2：需求原文-开发点对照 ============
    ws2 = wb.create_sheet("需求原文-开发点对照")
    ws2["A1"] = "需求原文点 → 开发点 对照表（反查：某条原文涉及哪些开发）"
    ws2.merge_cells("A1:C1")
    ws2["A1"].font = Font(name=FONT, size=10, bold=True)
    ws2["A1"].alignment = Alignment(horizontal="center", vertical="center")

    for i, h in enumerate(["需求原文点", "原文摘要", "对应开发任务序号"], start=1):
        c = ws2.cell(2, i, h)
        c.font = Font(name=FONT, size=10, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER

    rr = 3
    for row_data in reverse:
        for i, key in enumerate(("point", "summary", "tasks"), start=1):
            ws2.cell(rr, i, row_data.get(key, ""))
        for col in range(1, 4):
            c = ws2.cell(rr, col)
            c.font = Font(name=FONT, size=10)
            c.border = BORDER
            c.alignment = Alignment(horizontal="center" if col != 2 else "left",
                                    vertical="center", wrap_text=True)
        ws2.row_dimensions[rr].height = max(
            24, math.ceil(len(str(row_data.get("summary", ""))) / 60) * 15 + 6)
        rr += 1

    for col, w in (("A", 22), ("B", 78), ("C", 20)):
        ws2.column_dimensions[col].width = w

    return wb, total


def self_check(wb):
    """全表扫描疑似代码类名称，返回告警列表"""
    import re
    warnings = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not isinstance(v, str) or not v:
                    continue
                for name, pat in _CODE_NAME_PATTERNS.items():
                    hits = sorted(set(re.findall(pat, v)))
                    if hits:
                        warnings.append(f"  [{ws.title}!{cell.coordinate}] {name}: {hits}")
    return warnings


def main():
    ap = argparse.ArgumentParser(description="工作量评估表生成器")
    ap.add_argument("json_file", nargs="?", help="tasks.json 路径")
    ap.add_argument("-o", "--output", default="工作量评估.xlsx", help="输出 xlsx 路径")
    ap.add_argument("--example", action="store_true", help="打印 JSON 样例后退出")
    args = ap.parse_args()

    if args.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return

    if not args.json_file:
        ap.error("需要 tasks.json 路径，或用 --example 查看格式")

    data = load_data(args.json_file)
    wb, total = build_workbook(data)
    wb.save(args.output)

    print(f"已生成: {args.output}")
    print(f"任务数: {len(data['tasks'])}  合计: {total} 人天")
    print(f"反查表行数: {len(data.get('reverse', []))}")

    warnings = self_check(wb)
    if warnings:
        print(f"\n⚠ 自检发现 {len(warnings)} 处疑似代码类名称（对外交付须用业务语言）：")
        for w in warnings:
            print(w)
        print("请修改 tasks.json 后重跑。")
    else:
        print("自检通过：未发现代码类名称")


if __name__ == "__main__":
    main()
