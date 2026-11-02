# 排查手册

| 现象 | 原因 / 处理 |
|------|-------------|
| `pandoc 读取 docx 失败` | 检查 pandoc 是否在 PATH；先手工执行 `pandoc file.docx -t json` |
| `OLE 嵌入对象` 检查不绿 | 看 `report.json` 的 `ole` 检查；未知 ProgID 会在 `attachments/` 保留 `.bin` |
| `正文表格（顶层）` 不绿 | 可能是文本框内表格或嵌套表；看 `table_count` warning，回原始 docx |
| `合并单元格` 不绿 | AST 与 OOXML 的 gridSpan/vMerge 计数不一致；检查是否有嵌套表或异常合并 |
| 图片是 `.emf` | Pillow 转换失败；报告 warning，可用 Word/Visio 另存 PNG |
| 附件名为 `附件N` | 正文没有可用的前驱语义，嵌入内容也没有标题；可在 manifest 里按 `original_name` 对应 |
| `.doc` 转换超时 | 关闭残留 WINWORD 进程；或安装 LibreOffice，脚本会自动 fallback |
| PDF 报缺依赖 | `pip install "markitdown[pdf]"`；扫描件先 OCR |
| 中文路径异常 | 输出名只做非法字符清洗；原始路径/名称保留在 `manifest.json` |
| 输出目录已有同名产物 | 转换会覆盖 md 并合并 `_files/`；对比时请用不同的 `-o` 目录 |
