# 坑清单（req-detailed-design reference）

> 实战教训。每条都真实踩过（RCP-15436），代价已付过一次，别再付第二次。按类分组，附「正确做法」。

## 需求文档侧

1. **多版本迭代必须每版 diff**
   - 案例：v0.1→v0.2 去掉 OCR 接口、补 APP 端管控；v0.2→v0.4 补接口字段说明、新增案件审核校验。若整篇重写，会丢失前一轮评审定的口径。
   - 正确：`diff 旧.md 新.md` 出变更清单 → 只改受影响章节 → 文档头追加版本块。

2. **docx 批注是隐藏需求，不读必漏**
   - 案例：批注"本次章节可参考'社保使用情况'的处理 RCP-14939"——直接决定了整个理算章节的参照实现与两阶段设计模式。
   - 正确：阶段 0 必解 `word/comments.xml`（recipe 见 process.md 0.2），逐条纳入需求理解。

3. **内嵌 OLE 附件是 SA 定稿来源，md 表格可能丢内容**
   - 案例：《接口字段说明》附件表格在 md 转换里只剩一行，字段 key/枚举全靠解 `document.xml` 才拿到；且附件内部自相矛盾（表格写 Y/N、示例报文写 1/0）。
   - 正确：附件 md + 原件都看；表格丢失就解 document.xml；附件内矛盾记录两处出处进"待确认"。

4. **文件名含 U+00A0 / 全角空格，Read 与 cp 会报"不存在"**
   - 案例：`RCP-15436\u00a0--希尔顿…v0.4.md`，Read 工具报不存在但 `ls` 能看到。
   - 正确：`ls -b`/`od -c` 看真实字节；`for f in *.md; do cp "$f" /tmp/req.md; done` 复制成简单名再读。

## 代码侧

5. **字段语义禁止想当然（最贵的一课）**
   - 案例：`lcbill.premtype` 被当成"首期/续期"，实际是**账单层级**（0-投保人/1-子团体/2-个人，证据 `BillManageSql.properties` 的 join 方式）。按 premtype='0' 过滤 + paygroupno=子团体编码 = 永不同真，判定**永远不触发且无报错**。
   - 正确：语义取证四步（grep 全部用法 → 找参照 → DDL/DML 证据 → 写进 0.2 表）；拿不准进待确认。

6. **全列 update 的新列在语句末尾**
   - 案例：RCP-14939 的 `ISSOCIALUSEDREJECTFLAG` 在 `updateByPrimaryKey` **:2566（语句末尾）**，设计只列了 6 处会漏第 7 处——理算回写走全列 update，漏改则标志永远落不了库。
   - 正确：新增列时 grep 全部出现处，**区分 resultMap/ColumnList/insert/insertSelective/selective-update/full-update** 六类，full-update 单独确认。

7. **字段/因子清单有第二调用方**
   - 案例：`getLCCLAIMBENEFITDynamicField` 除主匹配（dealLcClaimBenefit）外还被**预授权累计**（:1607）遍历；一阶段跳过逻辑只加一处会漏，且预授权对象无新字段值会造成"限额规则不参与预授权累计"的副作用——须写进文档提示测试。
   - 正确：新因子/字段入清单前，grep 清单方法的全部调用方，逐个说明行为。

8. **"判空清单"类方法要同步**
   - 案例：`isStandardRule` 的 isBlank 清单里有 ISSPECIAL/SOCIALINSUISNOUSED；新字段不加，配置了该字段的规则会被误判为"默认标准规则"。
   - 正确：找参照字段的所有"清单/枚举/判空/过滤"位置，逐处对齐。

9. **主表+日志表成对加列；日志写入是 insert-select 显式列清单**
   - 案例：`LLRECEIPTLOG` 由 `saveLlReceiptTrace` 用 `insert into … select … from LLRECEIPT` 整行快照写入（`ClaimLogTraceMapper` 与 `CLAIMCT01AmqpProcessMapper` 各两处）；只在主表加列，轨迹快照恒 NULL。
   - 正确：加列清单必须含日志表 + 所有快照 SQL 的**列清单与 select 清单两处**。

10. **"后端未实现"极易误判**
    - 案例：NOPAY 三字段曾被判"前后端都没实现"，git 追溯发现 前端+legacy（`PlanTradService.saveServiceRule:282-284`）+表列 已由 RCP-15369 交付，真正缺口只在 policy 消费侧。另该需求第一个提交的 setter 有自身赋值 bug、第二个提交已修复——链路"通"的结论也要带 commit 证据。
    - 正确：先 `git log -S <标志>` 追溯各仓引入提交，再按"配置→消费"分层下结论；"零命中"要写明检索范围。

11. **多副本是缺陷之源**
    - 案例：账单录入页两份（普通 `ReceiptQuery.html` / GHB `ReceiptQueryGHB.html`）；保单查询两条路径（含缓存 `InsuredPolicyWithCache`）；账单轨迹两版（普通/GHB）；医院编码末位=2 的 ISSPECIAL 硬编码三处。
    - 正确：阶段 4.4 多副本清单逐项核对；"两页字段集合比对"要写明结论（仅 1 个字段名不同→必须改两份）。

12. **评估/他人行号不可信**
    - 案例：评估行号偏大 66-100 行（不是 git 漂移，是记录偏差）；路径错误（`AIOUpCommoVo` 实际在 `claim/vo/`；`EpibolyCaseMapper.xml` 在 `claim/mapper/epiboly/`）。
    - 正确：一律当前基线重核；定位用"类名+方法名+原文行"；漂移量写进定位行。

## 工具侧

13. **shell heredoc 里的反引号会被 bash 吃掉**
    - 案例：用 `python -c "...反引号..."` 给设计文档打补丁，反引号内的标识符被当成命令替换（静默写坏文档，内容变空）。
    - 正确：补丁用 `python - <<'PYEOF'`（带引号）或独立 `.py` 文件；补丁后必须复查写入结果。

14. **表格行号重排会碰撞**
    - 案例：删行后想把 2..8 顺延成 3..9，从低到高替换会把刚改的 3 又当旧 3 再改一次。
    - 正确：**区域切片 + 从高到低替换**；或按行内容（文件路径）重排而非按编号替换；改完用正则校验行号连续。

15. **GBK 三件套：iconv -c / grep -a / 分类型对待**
    - 案例：`iconv` 不加 `-c` 静默截断（586 行 mapper 只转出 400 行）；GBK Java 被 grep 当二进制跳过；XML 其实多为 UTF-8（一刀切 GBK 会把 UTF-8 转成乱码）。
    - 正确：`iconv -c`；grep 加 `-a`；每类文件先 `file` 实测，再决定转码与否。

## 协作侧

16. **接口落点反复变更 → 撤销留痕、旧引用清零**
    - 案例：APP 端管控从 policy `insuredPolicy` → policy 内部聚合 → claim 新增接口，三版。若只改新节不清理，文档会同时存在三套矛盾描述。
    - 正确：每个被否方案在相关章节留一行撤销说明；`grep 旧方案关键词` 必须只剩撤销说明；附录 D 文件清单同步增删。

17. **他人先行交付 → 依赖写进上线顺序 + 阻断条件**
    - 案例：NOPAY 三列 DDL 归 RCP-15369 且先上线。若不写清，本需求先上线则规则 SQL/判定全部报列不存在。
    - 正确：上线顺序第 1 条写明"前置依赖 + 核对 SQL（`user_tab_columns`）+ 任一缺失则阻断发布 + 协调对象"。

18. **公共方法 + 失败隔离（设计决策教训）**
    - 案例：APP 标识曾设计为调 `queryServiceState` 复用判定——但后者内部含追缴 feign 且失败抛异常，会把"查保单列表"整条链路拖垮；后改为抽公共判定方法、接口自建轻量链路，并对附加标识做 try-catch 默认值。
    - 正确：同规则多消费方→抽公共方法；附加能力必须"失败不外溢"；聚合口径差异（anyMatch vs allMatch）显式说明是需求设计而非缺陷。
