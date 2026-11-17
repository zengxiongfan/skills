---
name: req-op-manual
description: "操作手册自动化（CGIS 团险核心系统）：按需求文档生成单本操作手册（需求点→功能描述→操作方法，截图取自测试案例，缺图留占位），把多本手册整合为一份整合版（保留全部需求点、统一重编号/图号/附录），或对既有手册出 V2 新文件（旧文件不动）。TRIGGER when: 用户要求 生成操作手册 / 按需求写操作手册 / 按测试案例截图生成手册 / 多本操作手册整合 / 手册升版本V2 / 手册补截图清单；即使用户只说'给这个需求出个操作手册''把这几个手册合成一份'也应触发。"
metadata:
  short-description: Requirement → operation manual docx (single/merge/vnext)
---

# req-op-manual 操作手册自动化

**输入**：需求文档（docx/doc/xlsx/pdf，经 `req-doc2md` 转 md）+ 可选测试案例 xlsx（截图来源）+ 可选参考样式手册（封面/修订记录/目录样式）
**输出**：按需求点组织的 docx（每点"功能描述 + 操作方法"），附 QA 报告与待补截图清单

与上游技能的关系：`req-doc2md`（需求文档 → md）→ 本技能（md + 测试案例 → 操作手册）。

## 一、输入参数（缺失先问用户，不得猜测）

| 参数 | 必填 | 说明 |
|---|---|---|
| `requirement_doc` | 是 | 需求文档路径（原文 docx/pdf，由本技能调 req-doc2md 转换） |
| `test_case` | 否 | 测试案例 xlsx；**有则取截图，无则全占位** |
| `reference_manual` | 否 | 参考样式手册（企业封面/修订记录/目录）；默认用内置 corporate 样式 |
| `project` / `version` / `output` | 是 | 项目名称（封面标题）、版本号、输出文件名 |
| `mode` | 否 | single / merge / vnext（按下表自动判定，可被用户覆盖） |
| `sources` + 顺序 | merge 时必填 | 待整合手册路径与顺序 |

## 二、模式与阶段路由

| 模式 | 触发条件 | 关键规则 |
|---|---|---|
| `single` | 1 个需求文档（±测试案例） | **不执行 S6 整合** |
| `merge` | ≥2 本手册，或用户明确要求"整合成一份" | 只复制/重编号/汇总，不重写内容 |
| `vnext` | 既有手册 + 改版要求（改名/删章/调结构） | 按原模式带新版本重跑，**旧文件不动** |

```
S2 截图提取：figures.source = testcase 才执行；否则跳过（可选需求文档示意图）
S6 多本整合：仅 merge（含"整合版 vnext"）执行；single / 单本 vnext 一律跳过
```

## 三、工作目录约定

```
<work>/
├── extract/           # S2 产物：case_rows.txt、imgs/、refmap_*.csv、contact/
├── assets/            # 选中的截图（figP_k_nn.png）
├── manifest.json      # 参数化配置（见 templates/manifest.schema.json）
├── content.py         # single 模式正文脚本（scaffold 生成后补全）
└── <手册>.docx         # 输出
```

脚本目录：`~/.claude/skills/req-op-manual/scripts`（本技能安装位置），所有命令在该目录或任意位置执行均可，使用绝对路径调用。

## 四、执行流程

### S0 · 输入盘点
1. 确认上表参数；判定模式与阶段路由；
2. 需求文档不是 md 时，先转换（依赖 req-doc2md skill）：
   ```bash
   python ~/.claude/skills/req-doc2md/scripts/req-doc2md.py "<需求.docx>"
   ```
3. 与用户确认：项目名、版本、输出名、样式（simple/corporate）、需求点拆分粒度。

### S1 · 需求点解析
```bash
python scripts/manual.py outline "<需求.md>" --json <work>/outline.json --points
```
- 输出 4.x 下的实质节点（含 4.1/4.1.1 两种粒度）；
- 结合需求与测试案例确定最终需求点清单（编号连续），写入 manifest.requirement_points；
- 每个需求点确定其"功能描述/操作方法"素材来源。

### S2 · 测试案例取图（条件执行）
仅在 `figures.source = testcase` 时执行：
```bash
python scripts/manual.py extract "<案例.xlsx>" --out <work>/extract
```
1. 先核验案例是否真有内嵌图：`unzip -l` 查 `xl/media`（req-doc2md 报 0 图不可信）；
2. 打开 `extract/contact/sheet_XX.png` 目视挑图：每需求点 1~3 张（入口/配置/校验）；
3. 按 `references/screenshot-rules.md` 写 `figures.json`，执行裁剪：
   ```bash
   python scripts/manual.py prep --map <work>/figures.json --out <work>/assets
   ```
4. 未覆盖的需求点写 `placeholder` 文案，进入附录汇总。

### S3 · 编写 manifest
按 `templates/manifest.schema.json` 写 `<work>/manifest.json`：
- `project/version/output/style/header_text`
- `cover.lines`（simple 封面标题行）
- `doc_info` / `revision` / `toc`（simple 用静态目录；corporate 用 `toc_field: true`）
- `requirement_points`（no/title/source）
- `figures.per_point`（img+caption 或 placeholder）
- `appendix`（待补截图清单行；merge 自动汇总）

### S4 · content.py 与构建（single）
```bash
python scripts/manual.py scaffold --manifest <work>/manifest.json --out <work>/content.py
# 按 references/writing-guide.md 补全每个需求点的 功能描述/操作方法
python scripts/manual.py build --manifest <work>/manifest.json --out "<输出>.docx"
```

### S5 · 校验
```bash
python scripts/manual.py verify "<输出>.docx" --expect-req <需求点数> --qa <work>/qa.md
```
- 自动：标题/需求点数量、图注格式与重复、占位数量、表/图数量、目录域；
- 有 Word 时：更新目录域 + 导出 PDF + 逐页渲染到 `<输出>_preview/`；
- 按 QA 报告与"待人工确认"逐项核对（封面、目录页码、截图内容、表格断行）。

### S6 · 多本整合（条件执行）
```bash
python scripts/manual.py merge --manifest <work>/merge.json --out "<整合版>.docx" --update-toc
```
merge.json 关键字段见 `templates/example-merge.json`：`sources`（顺序即章节顺序）、`part_title`、`version`、`revision`、`cover.subtitle`、`drop_chapters`。
自动完成：跳过各源封面/文档信息/目录/手册说明 → H1→H2、H2→H3 → 图号重编 → 附录汇总重编号 → 企业样式封面/修订记录/目录。

### S7 · vnext 升版本
1. 复制原 manifest（或 merge.json），修改 `version` / `output` / `drop_chapters`；
   可选：`drop_placeholders: true`（删除全部【截图待补充】占位框）、`appendix: false`（不生成附录）；
2. 重新执行 build 或 merge（**输出新文件名，不覆盖旧文件**）；
3. 修订记录追加一行；`verify` 复检。

## 五、质量门禁

- [ ] 需求章节 4.x ↔ 手册需求点一一对应，无遗漏
- [ ] 每个需求点均有"功能描述 + 操作方法"，操作方法为 1、2、3 编号
- [ ] 图号连续、无旧图号残留；每图有图注
- [ ] 缺图处为红色虚线框【截图待补充】，且与附录清单一致
- [ ] 封面标题完整不裁切、版本行在第 1 页；目录页码已更新
- [ ] 表格不异常断行、列宽可读
- [ ] 文件命名含需求号与版本；旧版本文件未被覆盖

## 六、人工确认点

1. 需求点拆分粒度（4.1 还是 4.1.1）；
2. 每需求点选图（contact 拼版目视后确认）；
3. 未覆盖需求点的占位清单；
4. （merge）整合顺序、部分标题、是否保留/删除章节；
5. （vnext）改了哪些内容、新版本号。

## 七、脚本清单

| 脚本 | 职责 |
|---|---|
| `manual.py` | 统一 CLI（outline/extract/prep/scaffold/build/merge/verify） |
| `parse_requirement.py` | 需求 md → 需求点大纲（4.x、功能路径、附件） |
| `extract_case.py` | 案例 xlsx → 用例行 + 图片 + 锚点映射 + 拼版 |
| `prep_assets.py` | 裁剪/重命名截图 |
| `docx_core.py` / `docx_layout.py` / `docx_engine.py` | 版式引擎（简约/企业两套） |
| `build_single.py` | manifest + content.py → 单本 docx |
| `merge_core.py` | 跨文档复制（图片去重）、大纲解析、章节映射 |
| `build_merge.py` | 多本 → 整合版 docx |
| `verify.py` | 结构检查 + Word 目录更新/PDF/渲染 + QA 报告 |

## 八、依赖

- `req-doc2md` skill（需求文档转 md）
- Python 包：`pip install -r scripts/requirements.txt`（python-docx / openpyxl / Pillow / pypdfium2 / pywin32）
- Word（可选）：用于目录域更新与 PDF 导出；无 Word 时 `verify --no-word`

## 九、参考文档

- `references/writing-guide.md` — 写作规范与句式
- `references/numbering-rules.md` — 章节/图号/附录编号与重编号
- `references/screenshot-rules.md` — 截图来源判定、锚点映射、占位规则
- `references/pitfalls.md` — 踩坑与防护（必读）
