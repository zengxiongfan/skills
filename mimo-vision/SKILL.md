---
name: mimo-vision
description: "MANDATORY: The main model (mimo-v2.5-pro) CANNOT read images. NEVER use the Read tool on image files (.png/.jpg/.jpeg/.gif/.webp/.bmp) — it will fail. You MUST use mimo-vision skill instead. TRIGGER when: user provides any image file path or URL; user asks to describe/analyze/understand an image; task requires reading text from images (OCR); user asks about image content, UI screenshots, diagrams, charts; any task involving image files. Supports local files and URLs."
metadata:
  short-description: Image understanding via mimo-v2.5
---

# mimo-vision

**主模型 mimo-v2.5-pro 没有识图能力，绝对不能用 Read 工具读取图片文件。所有图片理解任务必须通过本 skill 处理。**

## 触发规则（强制）

遇到以下情况时，**必须**调用 mimo-vision，**禁止**用 Read 工具读取图片：

- 用户提供了图片文件路径（.png/.jpg/.jpeg/.gif/.webp/.bmp）
- 用户提供了图片 URL
- 用户要求描述/分析/理解图片内容
- 任务需要从图片中读取文字（OCR）
- 用户询问图片内容、UI截图、图表、流程图等
- AI判断需要查看图片才能完成当前任务

## 支持的图片来源

| 来源 | 说明 |
|------|------|
| 本地文件路径 | 自动转为 Base64 编码传入 |
| 公网 URL | 直接传入图片 URL |
| 多张图片 | 支持同时传入多张图片 |

## 支持的图片格式

JPEG, PNG, GIF, WebP, BMP（单张不超过 50MB）

## 用法

### 单张图片（本地文件）

```bash
python ~/.claude/skills/mimo-vision/scripts/mimo_vision.py /path/to/image.png "请描述这张图片的内容"
```

### 单张图片（URL）

```bash
python ~/.claude/skills/mimo-vision/scripts/mimo_vision.py "https://example.com/image.png" "请描述这张图片的内容"
```

### 多张图片

```bash
python ~/.claude/skills/mimo-vision/scripts/mimo_vision.py "/path/to/img1.png" "/path/to/img2.png" "请比较这两张图片的区别"
```

## 参数说明

- 第1~N个参数：图片路径（本地文件或URL），至少一个
- 最后一个参数：对图片的提问/指令（可选，默认为"请详细描述这张图片的内容"）

## 输出

直接输出 mimo-v2.5 模型对图片的理解结果（纯文本），可被主模型直接引用和使用。

## 注意事项

- 本地文件会自动转换为 Base64 编码，大文件可能较慢
- URL 需为公网可访问地址
- 如果图片路径包含空格，请用引号包裹
