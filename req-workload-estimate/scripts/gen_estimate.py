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
     "mgmt": 1, "req": 1.5, "design": 1.5, "test": 3,
     "source": "对应需求原文点（章节号+原文摘录，可含〔对照现状〕〔依据〕标注）"}
  ],
  "reverse": [
    {"point": "§4.1.1", "summary": "原文摘要", "tasks": "5；4〔审批区范围依据〕"}
  ],
  "notes": ["1、上表为开发工作量，不含……", "2、……"]
}

管理/需求/设计/测试工作量是分类级数据：每个任务分类块只在块首行填写，
脚本按任务分类的合并范围对 管理/需求/设计/测试 四列做同样的纵向合并；
开发工作量仍逐行填写，不参与合并。

生成:
  Sheet1 工作量评估表 —— 十列 + 合计行 + 工作量总计行（均为 Excel 公式）+ 备注行
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
from openpyxl.utils import get_column_letter

FONT = "SimSun"
thin = Side(style="thin")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HEADERS = ["序号", "任务分类", "子任务", "任务事项", "管理", "需求", "设计",
           "开发工作量(人/天)", "测试工作量", "对应需求原文点"]

# 分类级工作量字段：(tasks.json 字段, Sheet1 列号, 中文名)
NEW_FIELDS = (("mgmt", 5, "管理"), ("req", 6, "需求"),
              ("design", 7, "设计"), ("test", 9, "测试工作量"))
# 合计行的五列工作量：(tasks.json 字段, Sheet1 列号)
WORKLOAD_COLS = (("mgmt", 5), ("req", 6), ("design", 7), ("days", 8), ("test", 9))

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
         "days": 2, "mgmt": 1, "req": 1.5, "design": 1.5, "test": 3,
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


def task_blocks(tasks):
    """按任务分类切块，返回 [(start_idx, end_idx), ...]，索引均含首尾。"""
    blocks, start = [], 0
    for idx, t in enumerate(tasks):
        if idx > start and t.get("category"):
            blocks.append((start, idx - 1))
            start = idx
    blocks.append((start, len(tasks) - 1))
    return blocks


def validate_blocks(tasks):
    """管理/需求/设计/测试为分类级字段：每块只在首行填写且必须是数字。"""
    for bi, (start, end) in enumerate(task_blocks(tasks), 1):
        first = tasks[start]
        for key, _, label in NEW_FIELDS:
            v = first.get(key)
            if v not in (None, "") and not isinstance(v, (int, float)):
                raise SystemExit(f"第 {bi} 个任务分类块的「{label}」必须是数字")
            for t in tasks[start + 1:end + 1]:
                if t.get(key) not in (None, ""):
                    raise SystemExit(
                        f"第 {bi} 个任务分类块的「{label}」只能在块首行（序号 {first['no']}）填写")


def build_workbook(data):
    title = data.get("title", "工作量评估")
    tasks = data["tasks"]
    reverse = data.get("reverse", [])
    notes = data.get("notes", [])

    wb = openpyxl.Workbook()
    wb.calculation.fullCalcOnLoad = True  # 打开时强制重算公式

    # ============ Sheet1：工作量评估表 ============
    ws = wb.active
    ws.title = "工作量评估表"

    ws["A1"] = title
    ws.merge_cells("A1:J1")
    ws["A1"].font = Font(name=FONT, size=10, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    for i, h in enumerate(HEADERS, start=1):
        c = ws.cell(2, i, h)
        c.font = Font(name=FONT, size=10, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER

    validate_blocks(tasks)

    r = 3
    for t in tasks:
        for i, v in enumerate((t["no"], t.get("category", ""), t["subtask"], t["item"],
                                t.get("mgmt", ""), t.get("req", ""), t.get("design", ""),
                                t["days"], t.get("test", ""), t.get("source", "")), start=1):
            ws.cell(r, i, v)
        for col in range(1, 11):
            c = ws.cell(r, col)
            c.font = Font(name=FONT, size=10)
            c.border = BORDER
            if col in (1, 2, 5, 6, 7, 8, 9):
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        # 行高按任务事项/原文点文本长度估算
        lines = max(math.ceil(len(str(t["item"])) / 34),
                    math.ceil(len(str(t.get("source", ""))) / 30), 1)
        ws.row_dimensions[r].height = max(24, lines * 15 + 6)
        r += 1

    # 任务分类纵向合并：B 列按分类块合并，管理/需求/设计/测试按同一块合并
    def merge_block(start, end):
        if end <= start:
            return
        ws.merge_cells(start_row=start, start_column=2, end_row=end, end_column=2)
        for key, col, _ in NEW_FIELDS:
            if tasks[start - 3].get(key) not in (None, ""):
                ws.merge_cells(start_row=start, start_column=col, end_row=end, end_column=col)

    for s, e in task_blocks(tasks):
        merge_block(s + 3, e + 3)

    # 合计行：五列工作量各自合计（Excel 公式）；需求覆盖情况见 Sheet2，不在本行重复
    totals = {key: sum(t.get(key, 0) or 0 for t in tasks) for key, _ in WORKLOAD_COLS}
    data_end = r - 1
    ws.cell(r, 1, "合计")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    for key, col in WORKLOAD_COLS:
        cl = get_column_letter(col)
        ws.cell(r, col, f"=SUM({cl}3:{cl}{data_end})")
    for col in range(1, 11):
        c = ws.cell(r, col)
        c.font = Font(name=FONT, size=10, bold=True)
        c.border = BORDER
        c.alignment = Alignment(horizontal="center" if 5 <= col <= 9 else "right",
                                vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 24

    # 工作量总计行：五列工作量之和（Excel 公式）
    total_row = r
    r += 1
    ws.cell(r, 1, "工作量总计")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    ws.cell(r, 5, f"=SUM(E{total_row}:I{total_row})")
    ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=9)
    for col in range(1, 11):
        c = ws.cell(r, col)
        c.font = Font(name=FONT, size=10, bold=True)
        c.border = BORDER
        c.alignment = Alignment(horizontal="center" if 5 <= col <= 9 else "right",
                                vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 24

    # 备注行
    if notes:
        r += 1
        ws.cell(r, 1, "\n".join(notes))
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
        ws.cell(r, 1).font = Font(name=FONT, size=9)
        ws.cell(r, 1).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = max(60, 16 * len(notes) + 20)

    for col, w in (("A", 6), ("B", 26), ("C", 26), ("D", 68), ("E", 6), ("F", 6),
                   ("G", 13), ("H", 13), ("I", 13), ("J", 56)):
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

    return wb, sum(totals.values())


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
    print(f"任务数: {len(data['tasks'])}  工作量总计: {total} 人天")
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
