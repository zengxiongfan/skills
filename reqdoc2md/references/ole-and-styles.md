# OLE 附件与格式索引

## OLE 识别

从 `word/_rels/document.xml.rels` 找 `oleObject` / `package` 关系，从 `<o:OLEObject ProgID="...">` 取类型：

| ProgID | 处理 |
|--------|------|
| `Package` | 解析 `\x01Ole10Native` 流：原始文件名 + 数据；按扩展名分流 |
| `Excel.Sheet.12` / `.8` | 从 CFB 的 `package`/`Workbook` 流或内嵌 ZIP 取 xlsx/xls |
| `Word.Document.12` / `.8` | 从 CFB 的 `package` 流或裸 ZIP 取 docx；递归转换 |
| `Visio.Drawing.*` | 保留 `.vsd` 原件 |
| `PBrush` | 从 OLE 数据中找合法 BMP 头，转 PNG |
| 未知 | 保存 `.bin` + warning，不丢弃 |

预览图通过 `<w:object>` / `<w:pict>` 内的 `<v:imagedata r:id>` 或 `<a:blip r:embed>` 精确映射到 OLE，不依赖 `rId+1`。

## 命名

优先级：

- Excel：真实文件名 → 首个非 `SheetN` 的 sheet 名 → 正文上下文 → `附件N`；
- Word：正文上下文 → 嵌入文档首段标题 → `附件N`；
- 所有类型共享去重表，避免 `.md` 与原件互相覆盖。

嵌套 docx 的图片/附件会合并到父级 `_files/`；相同内容按 SHA-256 去重，引用路径同步重写。

## 格式索引

`styles.json` 包含：

- `colored_runs`：字体颜色（含 theme 色标记）；
- `highlights`：高亮；
- `underlines`：下划线；
- `shading`：段落/表格单元格底色（需求文档里常用于“本次新增/待确认”）；
- `comments`：批注正文、作者、日期、锚文本、已解决标记；
- `insertions` / `deletions`：修订；
- `hidden` / `strikethrough`：隐藏文字、删除线；
- `bold` / `italic`：加粗、斜体（md 中通常已有 `**`/`*`，此处保留 run 级证据）。

每条尽量带 `table` / `row` / `cell` 或 `para`，便于回源。

## 原则

Markdown 不承载直接格式。正文引用“标红/标黄/见批注”时：

1. 先看 `样式标注.md` / `styles.json`；
2. 如果语义在附件内部，直接 openpyxl 读原始 xlsx 的字体/填充色；
3. 不要凭 md 文本推断格式含义。
