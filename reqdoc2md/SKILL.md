---
name: reqdoc2md
description: "Convert software requirement documents (doc/docx/xlsx/xls/pdf, including nested OLE Excel/Word attachments and merged-cell tables) into LLM-readable Markdown plus navigable indexes (manifest/outline/tables/attachments). TRIGGER when 用户要求读取或转换需求文档、需求评审、工作量评估前置、docx 内嵌 Excel/Word 附件、合并单元格/多级表头表格、文档结构化索引；also when an AI needs to read a .docx/.doc/.xlsx/.xls/.pdf requirement document before analysis."
metadata:
  short-description: Requirement docs to Markdown + indexes
---

# reqdoc2md

把需求文档转换为 **给 AI 读的 Markdown 包**，而不是只做「文本提取」：

- 正文交给 pandoc，保留标题/列表/脚注/链接；
- 表格用 OOXML/Pandoc AST 的 grid 模型重建，**保留合并单元格、多级表头和嵌套表**；
- 嵌入对象（Excel/Word/Visio/图片）逐个提取，原件和文本副本都保留；
- 额外生成 `manifest.json`、`outline.md`、`tables/`、`样式标注`，让 AI 能按章节/行号/表号精准读取，而不是把整篇文档塞进上下文。

## 何时使用

- 用户要求读取、分析、评审需求文档（doc/docx/xlsx/xls/pdf）。
- 下游技能（需求评审、工作量评估、改造点拆分）需要先解析需求文档。
- 文档里可能有「插入对象」形式的 Excel/Word 附件，或大量字段定义表、接口参数表、权限矩阵。
- 需要把需求原文转成可引用、可追溯的 Markdown。

## 何时不要用

- 扫描版 PDF（没有文本层）：先 OCR，再转。
- 加密文档：先解密。
- 只需要快速看一段文字、且不关心表格/附件：直接读原文即可。

## 使用方式

```bash
python <skill_dir>/scripts/reqdoc2md.py <input> [-o output_dir]
```

常用参数：

| 参数 | 说明 |
|------|------|
| `-o/--output` | 输出目录，默认与输入同目录 |
| `--link-style obsidian\|standard` | 默认 Obsidian `[[双链]]`；`standard` 输出标准 Markdown 链接 |
| `--table-format auto\|pipe\|html` | 默认 auto：简单表 pipe，合并/复杂表 HTML |
| `--no-heading-number` | 不自动给标题加 `1 / 1.1 / 1.1.1` 编号 |
| `--strict` | 有警告时返回退出码 2 |
| `--keep-temp` | 保留 pandoc 临时媒体目录，便于排查 |

退出码：`0` green / warning；`1` failed；加 `--strict` 时 warning 返回 `2`。

## 输出结构

**doc/docx**：

```
{name}.md                       # 正文阅读入口
{name}_files/
  images/                       # 图片（EMF 尽量转 PNG）
  attachments/                  # OLE 附件原件 + 同名 .md
    {att}.xlsx
    {att}.md
    {att}.xlsx.styles.json      # Excel 单元格颜色/批注索引（有样式时）
  tables/
    tbl-001.csv                 # 矩形数据，合并单元格已填有效值
    tbl-001.json                # grid、合并范围、header_rows
    table_index.json            # 表清单
  样式标注.md                    # 颜色/高亮/下划线/底纹/加粗/斜体/批注/修订
  styles.json                   # 同上，机器可读
  转换报告.md                    # 人读对账
  report.json                   # 机器读：status/checks/warnings/errors
  manifest.json                 # 总清单：章节、表格、附件、图片
  outline.md                    # 章节树 + 稳定 ID + 行号范围
  attachment_index.json         # 附件清单与引用索引
```

**xlsx/xls**：`{name}.md` + `{name}_files/`（tables、xlsx_styles、report、manifest）。

**pdf**：`{name}.md` + `{name}_files/`（report、manifest、outline）；表格不做结构化，报告会提示。

## 读取协议（AI 消费方必须按这个顺序）

1. **先读 `转换报告.md` / `report.json`**：`status != green` 时先处理警告，不要带着缺口往下分析。
2. **读 `outline.md` + `manifest.json`**：拿到章节 ID、行号范围、表号、附件号。
3. **按行号读 `{name}.md` 的相关章节**，不要整篇读入。
4. **表格数据以 `tables/tbl-*.csv` 为准**；`tbl-*.json` 用来看合并范围、表头行数、表标题。
5. **附件先看 `attachment_index.json`**，再读对应的 `attachments/{att}.md`；需要精确格式时读原件。
6. **视觉语义**（标红、底色、批注、修订）只看 `样式标注.md` / `styles.json`；附件内部的颜色回 `attachments/` 里的原始 xlsx（用 openpyxl 读字体/填充色），不要凭 md 下结论。

## 表格规则

- DOCX 表格来自 Pandoc AST 的 `rowspan/colspan` + OOXML 的表头/标题元数据；**合并单元格不会被展平**。
- 简单表（无合并、单行文本）输出 GFM pipe table，省 token。
- 复杂表（合并、多级表头、单元格含列表/图片/嵌套表）输出 HTML `<table>`，保留 `rowspan/colspan`。
- 每张表都额外输出：
  - `tbl-*.csv`：矩形数据，合并区域填有效值，适合 AI 直接读；
  - `tbl-*.json`：`rows/cols/header_rows/merges/cells`，适合程序解析。
- 多级表头不强行展平；`header_rows` 告诉消费方前几行是表头。
- 嵌套表递归渲染；超过 3 层的表格降级并写 warning。

## 附件规则

| 类型 | 处理 |
|------|------|
| Excel（`.xlsx/.xls`） | 保留原件 + 生成 `{att}.md` + `{att}.xlsx.styles.json` |
| Word（`.docx/.doc`） | 保留原件 + 递归转换生成 `{att}.md`，嵌套图片/附件合并到父级 |
| 图片（Package/PBrush） | 转 PNG 放 `images/`，正文中替换为图片引用 |
| Visio | 保留 `.vsd` 原件，正文/附件清单给链接 |
| 未知 ProgID | 保存 `attachments/{name}.bin`，写 warning，不丢弃 |

附件命名优先级：正文前驱语义（如「本次需求附件」）→ 嵌入内容首字/sheet 名 → `附件N`；重名自动去重。

同一段出现多个附件时，自动拆成独立行；默认输出 Obsidian `[[双链]]`，`--link-style standard` 可改标准链接。

## 质量门

`report.json` 的 `status`：

- `green`：OLE 数、表格数、合并单元格数、批注、修订、格式计数全部对上。
- `warning`：存在未知 ProgID、图片转换失败、表格数不一致、格式计数偏差等；产物仍可用，但必须先看警告。
- `failed`：转换过程出错。

下游技能可以把 `status == "green"` 作为继续分析的前置条件；不要只看 md 就下结论。

## 依赖

- 必需：Python 3.10+、`pandoc` 3.x（PATH 中可用）、`openpyxl`、`xlrd`、`Pillow`。
- Windows `.doc`：`pywin32` + 已安装 Word；没有 Word 时尝试 LibreOffice `soffice`。
- PDF：`markitdown[pdf]`。
- 不依赖 pandas / python-docx；表格不用 pandas 重写，避免丢合并与样式。

## 排查

| 现象 | 处理 |
|------|------|
| `pandoc 读取 docx 失败` | 检查 pandoc 版本/文件是否损坏；先 `pandoc file.docx -t json` 手工验证 |
| OLE 数对不上 | 看 `report.json` 的 `ole` 检查；未知 ProgID 会在 `attachments/` 保留 `.bin` |
| 表格数对不上 | 可能是嵌套表/文本框内表格；看 `table_count` warning，必要时回原始 docx |
| 图片是 `.emf` | Pillow 转换失败；保留 EMF 并在报告中 warning，可用 Word/Visio 另存 PNG |
| `.doc` 转换超时 | 关闭残留 WINWORD 进程；或安装 LibreOffice 作为 fallback |
| 中文文件名/路径异常 | 输出名已做 Windows 非法字符清洗；原件名保留在 manifest |
