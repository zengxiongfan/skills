---
name: docx2md
description: "Convert Office documents (doc/docx/xlsx/xls) to AI-readable Markdown. TRIGGER when: user asks to read doc/docx/xlsx/xls files; user asks to convert/transform these formats; AI determines it needs to read content from these file types; user mentions analyzing Word/Excel documents. This skill makes document content accessible for AI analysis."
metadata:
  short-description: Convert doc/docx/xlsx to markdown
---

# docx2md

将Office文档转换为AI可读的Markdown格式。

## 触发场景

- 用户要求读取doc/docx/xlsx/xls文件内容
- 用户主动要求转换/处理这些格式
- AI判断需要读取这些文件进行分析
- 用户提到分析Word/Excel文档

## 支持格式

| 格式 | 处理方式 |
|------|----------|
| doc | Word COM转docx + pandoc转换 + OLE附件提取 |
| docx | pandoc转换 + OLE附件提取 |
| xlsx/xls | openpyxl读取转为markdown表格 |
| pdf | MarkItDown提取 + 正则后处理识别标题结构 |

## 附件处理

docx中嵌入的OLE附件同样支持转换：

| 附件类型 | 处理方式 |
|----------|----------|
| Excel (.xlsx/.xls) | **保留原始文件（含字体/颜色/合并单元格等全部样式）** + 自动生成.md |
| Word (.docx) | **保留原始文件** + pandoc转.md（附件md末尾附格式索引） |
| Word (.doc) | 保留原始文件 + Word COM转docx + pandoc转.md |
| 图片 | 放入images目录 |
| 其他 | 原样保存到attachments目录 |

## 格式信息保留（重要）

markdown本身不承载字体颜色/高亮/下划线，pandoc的docx reader在读取阶段即丢弃
直接颜色格式（实验验证：AST中color零命中，`+styles`扩展仅映射命名样式）。
因此转换时自动生成旁车产物，**消费方（AI/人）读md时必须结合这些产物**：

| 产物 | 生成条件 | 内容 |
|------|----------|------|
| `{filename}_files/样式标注.md` | 正文存在颜色/高亮/下划线/批注/修订 | 按颜色分组列出带格式文字（段落号+文本）、批注（锚文本+作者+内容）、修订记录 |
| `{filename}_files/styles.json` | 同上 | 同上数据的机器可读版 |
| `{filename}_files/转换报告.md` | 有图片/附件/格式信息时 | 完整性对账：OLE嵌入对象数 vs 处理数、格式信息覆盖、批注/修订检出 |

附件docx（Word嵌入对象）的格式索引追加在附件md末尾（"附件样式标注"一节）。

**消费方规则**：文档正文若引用视觉属性（如"见标红的内容"），md与样式标注.md均无法
表达"哪些单元格标红"这类**附件内部**的格式——此时直接解析attachments/下的**原始
xlsx**（openpyxl读字体颜色），不要凭md下结论。

## 用法

```bash
python <skill_dir>/scripts/docx2md.py <input_file> [-o output_dir]
```

## 输出结构

**doc/docx**:
```
{filename}.md
{filename}_files/
  ├── images/image_1.png, ...
  ├── attachments/{name}.xlsx, {name}.md, ...
  ├── 样式标注.md        # 有颜色/高亮/下划线/批注/修订时生成
  ├── styles.json        # 同上，机器可读
  └── 转换报告.md        # 完整性对账（有产出物时生成）
```

**xlsx**: `{filename}.md` (包含所有工作表)
