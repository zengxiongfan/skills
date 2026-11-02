# 产物契约（reqdoc2md 1.0）

## 目录

```
{name}.md
{name}_files/
  images/
  attachments/
  tables/
    tbl-001.csv
    tbl-001.json
    table_index.json
  styles.json
  样式标注.md
  report.json
  转换报告.md
  manifest.json
  outline.md
  attachment_index.json
  xlsx_styles.json          # 仅 xlsx/xls 独立转换
```

## report.json

```json
{
  "schema_version": "1.0",
  "source": "需求.docx",
  "kind": "docx",
  "status": "green",              // green | warning | failed
  "checks": [
    {"id": "ole", "label": "OLE 嵌入对象", "expected": 7, "actual": 7, "ok": true, "note": ""}
  ],
  "warnings": [{"code": "table", "message": "...", "location": "tbl-003"}],
  "errors": [],
  "counts": {"ole": 7, "tables": 8, "table_merges": 12, "images": 9, "attachments": 7}
}
```

`status` 是下游唯一质量门：`warning` / `failed` 时不要直接拿正文下结论。

## manifest.json

关键字段：

- `outline[]`：`id`、`level`、`number`、`title`、`line_start`、`line_end`
- `tables[]`：`id`、`caption`、`rows`、`cols`、`header_rows`、`merges`、`format`、`csv`、`json`
- `attachments[]`：`id`、`rId`、`prog_id`、`type`、`original_name`、`display_name`、`saved_name`、`saved_rel`、`md_name`、`md_rel`、`sha256`、`preview`、`is_image`、`depth`
- `images[]`：`id`、`media`、`path`、`alt`、`nested`（嵌套文档合并进来的图片）
- `checks` / `warnings` / `errors`：与 `report.json` 同源

## 消费顺序

1. `report.json` / `转换报告.md`：先看状态。
2. `outline.md` + `manifest.json`：定位章节行号、表号、附件号。
3. `{name}.md`：按 `line_start` / `line_end` 读相关段落。
4. `tables/tbl-*.csv`：表格数据优先读 CSV；`tbl-*.json` 看 `header_rows` 和合并范围。
5. `attachments/*.md`：附件正文；需要精确格式时读同目录原件。
6. `styles.json` / `样式标注.md`：标红、底色、批注、修订。
7. 附件内部的颜色/批注：用 openpyxl 读原始 xlsx，不要凭附件 md 推断。

## 退出码

- `0`：green / warning（默认）
- `2`：warning（加 `--strict` 时）
- `1`：failed
