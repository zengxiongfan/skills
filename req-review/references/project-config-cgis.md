# 项目配置示例：CGIS 福利树（项目专属）

> 本文件是 `req-review` 的**项目配置示例**。CGIS 项目评审前必读；其他项目忽略，仅作格式参考。

## 仓库列表（`repos`）

每个服务独立 Git 仓库，逐一评审：

- `cgis-legacy-app`（旧版应用）
- `cgis-web-nbx`（新保单系统）
- `cgis-web-nb`（核保系统）
- `cgis-web-claim`（理赔系统）
- `cgis-web-ruleclm`（规则理赔）
- `cgis-web-benefit`（福利系统）
- `cgis-front-gemini`（前端，statics/pages 下 html+js）

## 提交筛选标识

- 格式 `RCP-XXXX`（如 `RCP-10910-2`），提交说明含完整字符串即为本需求提交
- 需求文档编号（如 `RCP-14939`）与 Git 提交筛选标识（如 `RCP-10910-2`）**用途不同，不得混用**：
  - `RCP-14939` 判断实现是否符合业务需求
  - `RCP-10910-2` 筛选需求提交、文件和责任人

## 问题编号前缀

- `L-` = cgis-legacy-app
- `N-` = cgis-web-nbx
- `B-` = cgis-web-nb

## 编码处理（GBK，重要）

- legacy 等仓库源码为 **GBK 编码**：读取/精确数行号前先转码
  ```bash
  git show <提交>:<文件> > tmp && python -c "
  raw=open(r'<路径>','rb').read()
  txt=raw.decode('gbk', errors='replace')
  open(r'<输出路径>','w',encoding='utf-8').write(txt)"
  ```
- **修改代码时写回 GBK**，保持源文件编码（用 Python 读写，勿用编辑器另存 UTF-8）

## 需求文档读取

- 需求 `.docx/.xlsx` → 用 docx2md skill 转 `.md` 后读取（`python ~/.claude/skills/docx2md/scripts/docx2md.py <文件>`）

## 其他

- 需求要点（如 RCP-14939 的 4.1~4.4）以需求文档为准，评审前逐条建立规则台账
