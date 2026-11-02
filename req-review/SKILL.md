---
name: req-review
description: "Review a requirement's code across git repositories by aggregating its commits into the final version. TRIGGER when: user asks to review code for a requirement/JIRA ticket (RCP-xxx, 需求单/需求迭代, feature branch before delivery), or says 需求代码评审 / 按需求评审代码 / 评审这个需求单的代码 / 评审RCP单. Uses commit-message filtering + aggregation (earliest-parent..latest + file whitelist) to review only the requirement's final code state, checks it against the requirement spec, and outputs a distributable issue report with git attribution."
metadata:
  short-description: Review a requirement's code across repos (commit aggregation)
---

# req-review · 需求提交代码评审

按需求标识聚合跨仓库 git 提交，对照需求文档审查**最终版本**，输出可分发到具体开发的问题报告。

## 一、输入参数（必填；缺失先问用户，不得猜测）

| 参数 | 含义 | 示例 |
|------|------|------|
| `requirement_id` | 需求标识，用于筛提交 | `RCP-10910-2` |
| `branch` | 评审分支（远端） | `feature-JIRA-RCP10910-2` / `origin/sit` |
| `repos` | 仓库列表（至少一个） | `cgis-legacy-app`、`cgis-web-nbx` |
| `requirement_doc` | 需求文档路径 | `需求文档.../...v0.12.md` |

参数未给全 → 先向用户问清再开始，不猜。

## 二、执行流程（9 步）

**第 1 步 · 拉取并确认基线**（每个仓库）
```bash
git fetch origin <branch>
git log origin/<branch> --oneline --grep="<requirement_id>"   # 圈定需求提交
```

**第 2 步 · 读取需求文档，建需求规则台账**
- `.docx/.xlsx` 用 req-doc2md skill 转 `.md` 后读取
- 需求多版本时先 diff 相邻版本，确认是否有需求变更
- 逐条提取规则：规则ID / 来源章节 / 适用范围 / 处理规则 / 预期结果 / 边界与例外

**第 3 步 · 计算聚合 diff（核心）**
```bash
# 需求涉及文件白名单
git log origin/<branch> --grep="<requirement_id>" --name-only --pretty=format: | sort -u | grep -v '^$'
# 聚合区间 = 最早需求提交的父节点 → 最新需求提交
git diff <最早需求提交>^ <最新需求提交> -- <文件白名单>
# ⚠️ 逐文件 diff 全覆盖（强制）：白名单内每个文件逐个单独 diff
git diff <最早需求提交>^ <最新需求提交> -- <单个文件>
```
- ⚠️ **逐文件 git diff 全覆盖（强制，不得凭主观跳过）**：对白名单内**每一个**文件逐一执行上面的单文件 diff 并审查。禁止凭文件名、扩展名、"看起来只是生成代码"等主观理由跳过任何文件；MBG 生成的 schema/model/db/vdb 类同样要 diff，确认字段同步完整、`FIELDNUM` 等编号一致。文件清单必须从 diff 结果**自动汇总**，禁止凭记忆手工汇总。

**第 4 步 · 剔除范围污染**
```bash
git log <最早需求提交>^..<最新需求提交> -- <文件> | grep -v "<requirement_id>"
```
- 出现非本需求提交 → 该改动剔除，列入报告"排除项"

**第 5 步 · 双轨审查**
- 需求业务逻辑一致性：逐条对照规则台账，验证**行为结果**（正常/反向/空值/边界/组合/状态流转），不只查字段是否存在
- 基础代码问题：正确性 / 安全 / 可靠 / 数据一致性 / 接口契约 / 性能 / 可维护
- 跨仓库实现口径逐一比对，不一致列为重点确认项

**第 6 步 · 数据库验证（涉及新增/修改 SQL 时）**

仅当白名单 diff 中出现 SQL 变更（Mapper XML、注解 SQL、拼接 SQL、DB 脚本）时执行；纯 Java/前端改动跳过，并在报告中注明「不涉及 SQL」。

1. **确定环境与 schema**：按分支/任务确定 SIT 或 UAT，再按 SQL 所属服务查 `CGIS服务知识库/数据库与Schema映射.md`：claim/ruleclm → `CGIS_CLAIM_SIT1` / `CGIS_CLAIM_UAT1`，其余连库服务 → `GCIS_SIT1` / `GCIS_UAT1`；只在该环境的 schema 验证，不跨环境、不跨 schema 猜。
2. **静态核对**：表/列存在性、类型与长度、NOT NULL/唯一键、索引（`ALL_IND_COLUMNS`/`ALL_INDEXES`）、统计信息（`ALL_TAB_STATISTICS`）。
3. **只读试跑**：SELECT 用真实/绑定值执行；注意 dbx 默认 100 行、最大 1000 行；DML 改写成等价 SELECT，确认过滤条件与影响行数。
4. **执行计划**：对 SQL 执行 `EXPLAIN PLAN FOR <SQL>`（不带 `STATEMENT_ID`，会写 `PLAN_TABLE`），再执行 `SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY())` 读取计划。若 `EXPLAIN PLAN` 无权限或 `PLAN_TABLE` 不可用，退化为索引 + 统计信息 + 实测行数/耗时分析，并标注「执行计划不可得」。
5. **性能分析**：全表扫描、索引失效（函数/隐式转换/前导 `%LIKE`/`OR`/`NOT IN`）、复合索引列序、回表、子查询基数、分页写法、N+1、批量提交。
6. **输出**：归入「基础代码问题-性能」，证据附 SQL、执行计划或索引/统计信息、实测行数与耗时；优化建议给出可执行的索引或改写方案。
7. **环境限制**：dbx 可查 SIT、UAT；STG 分支只做静态分析并标注「未做运行验证」；SIT/UAT 数据量与生产不同，性能结论为参考值；按分支选环境，不混用。

**第 7 步 · 归因与复核**
```bash
git blame <最新需求提交> -L <start,end> -- <文件>
```
- 责任提交必须 ∈ 需求提交集合；最终版本已不存在、或非本需求引入的问题不报

**第 8 步 · 支持复评**
- 发现已有上一份报告 → 先做需求/代码基线比对（报告〇节），标注"已修复 / 新增"

**第 9 步 · 输出报告**
- 按 `references/report-template.md` 结构、`references/example-report.md` 风格
- 输出到**当前项目根 `req-review-report/`** 目录（不存在则创建）
- 文件名：`{requirement_id}-{branch}-代码评审报告-{YYYYMMDD-HHmmss}.md`
- 每条问题可执行：文件:行号 + 问题代码原文 + 故障场景 + 责任人(附提交) + 建议
- 报告必须附两张完整清单：
  - **变动文件清单**：`git log --name-status` 逐文件核对，字段=序号 / 变更类型(A/M/D) / 文件路径 / 变更内容概述，**逐文件全覆盖**，禁止主观跳过
  - **提交记录清单**：`git log --format="%h|%an|%ad|%s"`，字段=序号 / 提交编号 / 提交注释 / 提交人 / 提交时间，按新→旧排列（新提交在上），提交人取 `%an`

## 三、参考文件

| 文件 | 内容 |
|------|------|
| `references/method.md` | 方法规范全文（输入参数 / 范围界定 / 聚合 / 归因 / 双轨审查 / 严重级别 / 问题字段） |
| `references/report-template.md` | 报告模板骨架（〇~十节）+ 单条问题格式 + 编号约定 |
| `references/example-report.md` | 最新完整版范本（RCP-10910-2 cgis-web-nbx，含〇~十全章节 + 新→旧提交清单），输出结构/风格与详细度参照 |
| `references/example-report-legacy.md` | 旧版多仓范本（legacy/nbx/nb 跨仓问题示例），风格参考备用 |
| `references/project-config-cgis.md` | CGIS 项目专属配置（服务列表 / 前缀 / GBK 编码），**CGIS 项目必读** |

## 四、硬性规则（不可违反）

1. 只审 `<requirement_id>` 提交引入的代码；其他需求/他人代码不评
2. 评审对象是**最终版本**；中间提交已修复的问题不报
3. 归因用 `git blame` 逐行定位，不用聚合 diff 定责
4. 提交人取 Git 实际作者 `%an`，禁止用提交说明里的 `--user`
5. 需求矛盾/缺口径 → 标"需求待确认/核验受限"，不自行判错
6. 严重级别 BLOCKER/CRITICAL/MAJOR/MINOR，结合触发条件/影响/可恢复判定，不机械按类型定级
7. **逐文件 git diff 全覆盖**：白名单内每个文件必须逐一 diff 审查，禁止凭主观判断跳过任何文件（含生成代码）；文件清单必须从 diff 结果自动汇总
8. **SQL 改动必须做数据库验证**：只读执行 + `EXPLAIN PLAN` 计划分析；除 `EXPLAIN PLAN` 写 `PLAN_TABLE` 外，禁止任何 DML/DDL；STG 无权限时标注「未做运行验证」
