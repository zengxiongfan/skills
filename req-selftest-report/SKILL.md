---
name: req-selftest-report
description: "需求自测报告生成（CGIS 团险核心系统）：把测试案例 Excel 中带执行截图的重要案例，按模板整理成需求自测报告 docx。TRIGGER when: 用户要求 整理/生成自测报告 / 按模板填自测报告 / 从测试案例挑案例写自测报告；或给出「测试案例 xlsx（1~n 个）」并要求输出某需求的自测报告。即使用户只说'把这个测试案例整理成自测报告'、'按模板出个自测报告'也应触发。"
metadata:
  short-description: Generate self-test report docx from test-case Excel per fixed template
---

# req-selftest-report · 需求自测报告生成

把测试案例 Excel 里**带执行截图**的重要案例，按固定模板整理成需求自测报告 docx。

**输入**：测试案例 xlsx（结构可各不相同，自适应解析）+ 需求编号/名称 + 测试人 + 范围决策
**输出**：自测报告 docx（表头填充、正文按模块分节、每节若干"案例标签+描述+截图"）+ `report.json` 配置留档 + 渲染 PNG（供验收）

## 输入参数（缺失先问用户，不猜）

| 参数 | 含义 | 必填 | 默认 |
|------|------|------|------|
| `req_title` | 需求编号+名称，如 `RCP-15795--NHB保单福利配置和理算规则升级（第三个迭代）` | 是 | — |
| `case_xlsx` | 测试案例文件，1~n 个（列名/列序/工作表名可各不相同） | 是 | — |
| `cases_per_module` | 每模块选几个"重要"案例 | 是（问用户） | 3 |
| `exclude_modules` | 本迭代不写进报告的模块清单（用户当轮指定） | 是（问用户） | 无 |
| `format_ref` | 格式基准报告 docx（沿用哪一版历史风格，**只要给就必须逐项对齐**） | 否（强烈建议） | 内置模板 |
| `tester` | 测试人（多人逗号分隔） | 否 | **留空**（用户默认要求人工填） |
| `modules` | 表头"模块"单元格内容（如 `cgis-web-claim,...`） | 否 | **留空**（人工补） |
| `submit_date` | 提交日期 | 否 | 当天 |
| `verdict` | 测试结论 | 否 | `测试通过`（模板固定值） |
| `env` | 测试环境 | 否 | `DEV测试环境 localhost:8080`（模板固定值） |

**表头口径（用户明确要求，勿擅自改）**：`tester`、`modules` 一律留空；`verdict`、`env` 用模板固定值，**不要**从同目录的 SIT 测试报告里去"抄"真实测试人或 SIT 环境地址。

**"理算计算逻辑 vs 页面显示"的模块归属不固化在本 skill**：每迭代由用户给排除清单（见阶段 1）。

## 流程总览（6 阶段）

```
阶段0 自适应解析 → 阶段1 范围确认（人工）→ 阶段2 选案（人机）
     → 阶段3 取证核验 → 阶段4 组版 → 阶段5 渲染验收 → 交付
```

**铁律**：
1. **范围与选案未经用户确认，不进入组版**（排除清单、每模块案例数由用户拍板）。
2. **无图模块不猜配图片**：要么标"（执行截图待补充）"由用户补图，要么用"实际输出"数据写文字描述。
3. **文案只用案例原始字段**（标题/操作步骤/输出/实际输出），不臆造案号、保单号、金额。
4. **测试案例编号不写入报告正文**（`RCP-xxx-xx` 统一剥离；表头需求编号保留）。
5. 生成过程幂等：始终从内置模板 + `report.json` 重建，不做增量改文档。

## 阶段 0：自适应解析

```bash
python scripts/parse_cases.py --xlsx 案例1.xlsx [案例2.xlsx ...] \
    --out iter_data.json [--export-images all_images]
```

- 自动识别案例表（表头命中"模块/测试项/测试案例标题/截图对应行数"等 ≥4 项，不看工作表名）
- 自动认列（同义词：标题/案例标题；输出/预期/预期结果；实际输出/实际结果；测试状态/执行结果；编号；截图对应行数/截图/截图链接），识别不了的列会打印 `unmapped` 提示用户确认
- 自动扫含 drawing 的工作表，解析图片锚点；截图引用支持 `截图!A65`、`A65`、`65`、多值分隔
- **引用行 → 图片规则：锚点起始行 = n 或 n+1（差一行，两个都试）；兜底取覆盖区间**
- 测试项/模块列空值自动前向填充（合并单元格风格）

**汇报给用户**：模块盘点表（模块 / 案例数 / 带图案例数）+ 未识别列 + 未解析引用。

## 阶段 1：范围确认（人工）

- 问用户：**排除哪些模块**（哪些是纯理算/通知书等不写的，哪些是页面显示要写的）、**每模块几个案例**。
- 只保留有截图引用的案例作为候选；无引用模块单列出来，问用户处置方式（补截图 / 用实际输出 / 暂不写）。

## 阶段 2：选案（人机）

AI 按"重要"标准给每模块推荐 N 个案例（优先级）：
1. 正反例对照（能累计/不能累计、范围内赔付/范围外拒付）
2. 核心规则基线（最小配置场景）
3. 覆盖不同测试项（同一模块内不重复同一测试项）
4. 阻断/非阻断校验成对出现时各取其一

产出 `picks.json` → 用户确认/指定 → 抽图：

```bash
python scripts/pick_cases.py --data iter_data.json --picks picks.json \
    --outdir report_assets --out selected.json
```

`picks.json` 示例：
```json
[
  {"module": "新福利配置页调整", "rows": [2, 6, 18]},
  {"module": "责任匹配规则配置", "nos": ["RCP-15795-133", "RCP-15795-136"]}
]
```

## 阶段 3：取证核验

1. **逐张打开截图核对**案例描述（案号/字段/提示文案能否对上）；对不上就换同组备选案例。
2. 无引用模块用缩略图总览排查隐藏图片（不可猜配）：
   ```bash
   python scripts/contact_sheet.py --data iter_data.json --media-dir all_images \
       --selected selected.json --outdir scan
   ```
3. 找不到图 → 如实向用户报告，按阶段 2 的处置口径处理。

## 阶段 4：组版

写 `report.json`（见 `references/report-spec.md` 与 `assets/report_spec.example.json`），然后：

```bash
python scripts/build_report.py --spec report.json --out "需求自测报告-已填写.docx"
```

- 内置模板：`assets/report_template.docx`（标题 + 4 行表头表格 + `1、测试功能描述` + `1.1` 占位）
- 表头填充：需求编号/名称、提交日期（默认当天）、测试结论/环境模板固定值；**测试人、模块留空**
- 正文：节标题（微软雅黑 10pt）→ 功能说明（10.5pt）→ 每案例"加粗标签 + 描述"（10.5pt）→ 居中截图（6999605 EMU ≈ 19.44cm）
- 案例编号自动剥离
- 分页：节标题 keepNext；**案例文字不加 keepNext**（否则"文字+大图"整体被推到下一页，页尾留大片空白）。截图段 keepLines + 居中

> 可用 `--template 其它报告.docx` 替换内置模板（想沿用某版历史风格时）。
> **用户给了格式基准报告时**，必须先跑 `scripts/inspect_ref.py` 与 `scripts/compare_fmt.py` 逐项对齐，不要凭肉眼"看着像"。

## 阶段 4.5：与格式基准对齐（给了 `format_ref` 就必做）

```bash
# 1) 拆解基准报告：页面几何 / 表头表格每格字体字号加粗颜色 / 正文各级字号 / 截图尺寸
python scripts/inspect_ref.py "基准报告.docx"
python scripts/inspect_table.py "基准报告.docx"

# 2) 重新生成内置模板（把基准的表格几何写死进模板）
python scripts/make_template.py

# 3) 生成后逐项比对，必须全部一致
python scripts/compare_fmt.py "生成的报告.docx" "基准报告.docx"
```

对齐项清单（缺一即返工）：

| 项 | 基准口径（RCP-15795 第三个迭代） |
|---|---|
| 页面 | A4 21×29.7cm，边距 上0.5 / 下0.75 / 左0.75 / 右0.75cm |
| 表头表格 | tblW=11057dxa、tblInd=-5、fixed、网格 1283/5281/1338/3155、行高 445/486/388/388、单元格垂直居中 |
| row0 需求名 | 跨 4 列，微软雅黑 **10.5pt 不加粗** |
| 模块值 | 微软雅黑 **9pt 加粗** |
| 提交日期 / 测试人 值 | 10.5pt 加粗 |
| 测试结论 值 | 10.5pt，**绿色 00B050** |
| 测试环境 值 | 跨 3 列，**10pt 加粗** |
| 节标题 | 微软雅黑 10pt 不加粗，首行缩进清零 |
| 功能说明 / 案例正文 | 10.5pt，标签加粗、描述不加粗 |
| 截图 | 宽 6999605 EMU，居中 |

## 阶段 5：渲染验收

```bash
python scripts/render_docx.py --docx "需求自测报告-已填写.docx" --outdir render
```

- 有 visual-judge 能力时：把 `render/page_*.png` 交给 visual-judge 逐页验收
- 不可用时逐页自查（清单见 `references/process.md` 阶段 5）：图片溢出/截断/变形、孤立标题、编号连续、图文数量对账、乱码

## 脚本清单

| 脚本 | 作用 |
|------|------|
| `scripts/make_template.py` | 生成/重建内置模板 `assets/report_template.docx`（表头几何与字体写死） |
| `scripts/parse_cases.py` | 自适应解析案例 xlsx → `iter_data.json`（可选导出全部图片） |
| `scripts/pick_cases.py` | 按 picks 抽案例+截图 → `selected.json` + `report_assets/` |
| `scripts/contact_sheet.py` | 未引用图片缩略图总览（漏图排查） |
| `scripts/build_report.py` | 内置模板 + `report.json` → 报告 docx |
| `scripts/render_docx.py` | docx → PDF → PNG（Word COM + PyMuPDF） |
| `scripts/inspect_ref.py` | 拆解基准报告的段落/表格字符格式 |
| `scripts/inspect_table.py` | 拆解表头表格 XML（合并、列宽、行高、每 run 格式） |
| `scripts/compare_fmt.py` | 生成报告 vs 基准报告逐项格式比对 |

**环境**：Windows + Office Word（渲染）；Python 3.10 且装有 `python-docx openpyxl PyMuPDF pywin32 Pillow`。本机 `python` 可能指向 3.14（无依赖），需显式用 3.10 解释器路径。

## 参考文件

- `references/process.md` —— 6 阶段完整动作与验收清单
- `references/pitfalls.md` —— 实战坑清单（必读）
- `references/report-spec.md` —— `report.json` 结构契约
- `assets/report_spec.example.json` —— 配置样例
- `tests/test_smoke.py` —— 冒烟测试（两份结构不同的样例 xlsx 验证自适应解析 + 组版）
