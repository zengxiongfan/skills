# 表格处理规则

## 网格模型

DOCX 表格从 Pandoc AST 的 `rowspan/colspan` 读取，同时用 OOXML 的 `w:tbl` 元数据补充：

- `gridSpan`：一个元素 = 一个横向合并单元格；
- `vMerge restart`：一个元素 = 一个纵向合并单元格；
- `tblHeader`：表头行数；没有标记时默认第一行为表头；
- `tblCaption` 或表格前一段「表N ...」作为 caption。

`tables/tbl-*.json` 的 `merges` 记录 `{row, col, rowspan, colspan}`；`cells` 只列左上角单元格，避免重复文本。

## 输出形态

| 条件 | 输出 |
|------|------|
| 无合并、单行文本、表头 1 行 | GFM pipe table |
| 合并单元格、多级表头、单元格含列表/图片/嵌套表 | HTML `<table>` + `rowspan/colspan` |
| 空表 | `（空表）`，仍保留 CSV/JSON 记录 |
| 所有表 | `tbl-*.csv` + `tbl-*.json` |

`--table-format pipe` 遇到复杂表会自动回退 HTML 并写 warning；`--table-format html` 强制 HTML。

## CSV

- 矩形网格；合并单元格在覆盖区域填左上角文本（有效值）；
- 适合 AI 直接读字段定义表、参数表、权限矩阵；
- 多行单元格保留换行，CSV 使用标准引号转义。

## Excel 附件

- `openpyxl` 读取，保留多 sheet、合并单元格、隐藏 sheet；
- 每个 sheet 生成 `## sheet名` + 表格；
- 同时写 `{att}.xlsx.styles.json`（字体色/填充色/加粗/批注）；
- 原件永远保留，md 只是阅读副本。

## 已知边界

- 嵌套表超过 3 层：降级为文本并写 warning；
- 文本框内表格：Pandoc 可能不进入正文，报告里会出现 `table_count` warning；
- PDF 表格：只做文本提取，不做结构化拆分。
