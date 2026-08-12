# RCP-10910-2 cgis-web-nbx origin/sit 代码评审报告

- **评审时间**：2026-08-12 17:28
- **评审人**：Claude Code
- **评审对象**：`cgis-web-nbx`（新保单系统），分支 `origin/sit`（HEAD `354caaacc`）
- **需求标识**：RCP-10910-2（福利树项目迭代二）
- **需求文档**：RCP-15793《NHB保单福利配置和理算规则升级（项目实施--第一个迭代）--需求规格说明书》v0.9
- **提交人**：lixin、ludongxu（Git 实际作者 `%an`；提交注释内 `--user` 标注的 SZW250323 等与实际作者不一致，归因一律以 `%an` 为准）
- **评审方法**：12 条 RCP-10910-2 提交聚合净变更（区间 `304e17874^..e215f94a4`），7 个文件逐文件 git diff 全覆盖，范围污染剔除，`git blame` 逐行归因，双轨审查（需求一致性 + 基础代码）。

---

## 〇、本次评审基线说明

1. **需求基线**：需求文档 v0.9 覆盖 4.1~4.4 四章（4.1 固定保额自动映射 / 4.2 限额时间范围映射 / 4.3 安怡万家保费因子 / 4.4 是否标准协议）。修订记录列至 v0.8，文件名 v0.9，以文档实际正文为准。
2. **代码基线**：本仓 RCP-10910-2 共 12 条提交，聚合区间为最早需求提交父节点 `304e17874` → 最新需求提交 `e215f94a4`。区间内交错 RCP-2595 / RCP-13484 / GCIS-19821 / TAPD-1018351 等其他需求提交，已按文件逐 hunk 甄别剔除（见「八、排除项」）。
3. **关联报告**：同需求另有 `cgis-legacy-app` 评审报告（`RCP-10910-2-origin-sit-代码评审报告-20260812-165012.md`）。本报告为 **cgis-web-nbx 首评**；两仓实现同一需求，互为跨仓对照（见「四、跨仓库一致性」）。本报告问题为【新】，跨仓同名问题标注【同 legacy L-xx】供参考。
4. **结论**：nbx 侧共识别问题 10 项（🔴1 / 🟠3 / 🟡6）+ 需求待确认 6 项。核心缺陷为组合免赔额"取大"用 VARCHAR 排序可能取错值，以及若干需求口径/覆盖待确认项。

---

## 一、评审范围与方法

### 1.1 覆盖的提交

| 仓库 | 提交数 | 时间跨度 | 主要提交人 |
|------|-------|---------|-----------|
| cgis-web-nbx | 12 | 2026-06-08 ~ 2026-08-11 | lixin（6）、ludongxu（6） |

### 1.2 评审方法

- 聚合净变更：`git diff 304e17874 e215f94a4 -- <文件白名单>`，白名单 = `git log --grep=RCP-10910-2 --name-only | sort -u`（7 个文件）。
- **逐文件 git diff 全覆盖**：7 个文件逐一 diff 审查（含 MBG 生成的 model 类 `LcContPlanDetail.java`，确认 AMNTUNIT 字段与 resultMap 同步），无主观跳过。
- 范围污染剔除：`ApplicationEntryService.java` / `ApplicationEntryMapper.java(.xml)` 中 RCP-13484、TAPD-1018351、`2b38b80a6` 提交的改动经 `git log -S` 定位后全部剔除，不纳入评审（见「八、排除项」）。
- 归因：`git blame -L` 定位最终版本问题行，验证责任提交 ∈ RCP-10910-2 提交集合；预存在（RCP-10910-1 迭代一，如 `08bfad123e`）代码不报。
- 备注：本仓文件 GBK 编码，读取前已按 UTF-8 转码核对行号。

### 1.3 需求要点（对照用）

- **R1（4.1）**：产品业务所属为"企补产品"且产品代码第 4 位为 R 的所有 NGB 产品，一级责任固定保额自动转"年限额"。
- **R2（4.2）**：限额"时间范围"按保额单位映射——元/天→日(20)，其他（元、月薪倍数）→年(30)；投保录入优先 GCMS 保额单位（核心方案责任"保额单位"非空即 GCMS 原始方案），为空回退产品配置表；保全新增方案取产品配置表；无需区分是否医疗产品；中端&GHB 不涉及。
- **R3（4.3.1）**：GNSR014 产品「一般医疗」「特定疾病医疗」2 个一级责任免赔额除福利值外信息一致 → 险种层生成 1 条组合型免赔额（类型=免赔额、组合=是、下级=两责任、福利值取大、单位元、计算方式本身、家庭范围按免赔方式、等待期否、梯度否、规则组=责任自付比例、抵扣顺序自费→部分自付→社保内），不一致则不生成、责任层照常映射。
- **R4（4.3.2）**：GNSR014 险种总赔付年限额（迭代一已有）迭代调整为：是否组合=组合，下级组合责任=当前产品下全部 4 个一级责任。
- **R5（4.4）**：【保单理赔福利录入】页险种层"是否属于标准协议"统一默认"否"；历史数据统一改"否"；GHB/中端不涉及。

---

## 二、问题清单（按严重程度排序）

> 图例：🔴=高（需求符合性/正确性）🟠=中（健壮性/一致性）🟡=低（质量/规范）。【新】=本轮新增。

### 🔴 N-01 需求4.3.1：组合免赔额"取大"用 VARCHAR 词典序排序，跨位数时取错值（【新】）

- **类/文件**：cgis-web-nbx `src/main/resources/mapper/com/cignacmb/cgis/nbx/mapper/LcContPlanDetailMapper.xml:557`（`queryMaxDeductiblesInfos`）
- **调用链**：
  ```
  第1190行  checkDeductibleParamOfGNSR014(...)=="1"    ← 前置闸口（两责任免赔额配置一致才生成组合）
  第1193行  createGNSR014RiskBenefitOfDeductibles(...)  ← 组合免赔额生成入口
  第423行   premFactorInfo = queryMaxDeductiblesInfos(...)  ← 问题所在：取最大免赔额
  第425行   setBaseBenefitInfo(claimBenefit,"20",premFactorInfo.getPremValue(),"10")  ← 组合福利值=查出的"最大"值
  ```
- **需求条款**：4.3.1 —— "福利值：如果上述2个责任的免赔额'福利值'不一致，需比较上述2个责任的福利值，**然后取大**"
- **问题代码原文（XML 557 行）**：
  ```sql
  SELECT policyNo, ..., premValue, type, claimScope
  FROM (
      SELECT l.policyno, ..., l.premvalue, l.type, l.claimscope
      FROM LcPremFactorInfos l
           LEFT JOIN LCCONTPLANDETAIL lpd ON l.POLICYNO = lpd.POLICYNO
      WHERE l.POLICYNO = #{policyNo}
        AND ... (join 条件)
        AND l.PREMFACTOR = 'Deductibles'
        AND l.PLANCODE = #{planCode}
        AND l.RISKCODE = #{riskCode}
      ORDER BY l.premvalue DESC            -- ❌ premvalue 为 VARCHAR，按词典序而非数值序
  )
  WHERE ROWNUM = 1
  ```
- **问题**：`l.premvalue` 是 VARCHAR 列，`ORDER BY ... DESC` 按字符串词典序取"最大"，跨位数时数值大小与词典序相反。对照 `getMaxFixAmnt`（同文件 496 行）用了 `MAX(TO_NUMBER(FIXEDAMNT))`（数值序，正确），两处口径不一致。
- **具体故障场景**：
  1. 数据前提：一般医疗免赔额 10000 元、特定疾病医疗免赔额 2000 元（应取大=10000）；
  2. 触发：组合免赔额生成执行本 SQL；
  3. 错误结果：词典序 `'2000' > '10000'`（首字符 '2' > '1'），`ROWNUM=1` 取到 **2000** → 组合免赔额福利值错误，理赔时免赔额抵扣口径错误，违反"取大"规则。
- **责任人**：lixin（`330056deb`；提交注释标注 --user SZW250323）
- **建议**：改为 `ORDER BY TO_NUMBER(l.premvalue) DESC`（与 `getMaxFixAmnt` 口径一致），并加 `premvalue` 非数值保护。

> **跨仓**：legacy `java/SqlInfo/app/LCContPlanDetailInfoMapper.xml` 同名 SQL 同样 `ORDER BY l.premvalue DESC`，双仓同缺陷（见「四、跨仓库一致性」）。

---

### 🟠 N-02 规范：`applicationEntryMapper` 注入与 `ApplicationEntryMapper.checkDeductibleParamOfGNSR014`（DeductibleType 变体）为死代码，且与在用 SQL 因子名不一致（【新】）

- **类/文件**：
  - `ClaimBenefitOfESBService.java:49`（`@Autowired ApplicationEntryMapper applicationEntryMapper`，全文件未使用）
  - `ApplicationEntryMapper.java:835`（`checkDeductibleParamOfGNSR014` 方法声明，全仓无调用方）
  - `ApplicationEntryMapper.xml:3959-3973`（对应 SQL）
- **调用链**：无调用方（`git grep` 全仓最终版仅命中声明处）。
- **需求条款**：4.3.1（组合免赔额一致性判断）。
- **问题代码原文（ApplicationEntryMapper.xml 3973 行）**：
  ```xml
  <select id="checkDeductibleParamOfGNSR014" ...>
    SELECT COUNT(1) FROM (
      SELECT DISTINCT l.CLAIMSCOPE, l."TYPE", lpd.DEDUCTIBLEMETHOD
      FROM LcPremFactorInfos l
        LEFT JOIN LCCONTPLANDETAIL lpd ON l.POLICYNO = lpd.POLICYNO
      WHERE ... AND l.PREMFACTOR = 'DeductibleType'   <!-- ❌ 在用路径因子名为 'Deductibles'，此处为 'DeductibleType' -->
        AND l.RISKCODE = 'GNSR014'
    )
  </select>
  ```
- **问题**：注入的 `applicationEntryMapper` 及同名方法（因子名 `DeductibleType`）**从未被任何代码调用**（在用的一致性判断走 `LcContPlanDetailMapper.checkDeductibleParamOfGNSR014`，因子名 `Deductibles`）。`DeductibleType` 是另一批产品（GNSR002/GNSR015，见本 XML 3606 行）使用的因子名，照搬到 GNSR014 属误用。死代码易被后续开发者误调用而踩错因子名。
- **具体故障场景**：开发后续在此处补逻辑时误调 `applicationEntryMapper.checkDeductibleParamOfGNSR014` → 因子名 `DeductibleType` 匹配不到任何记录 → COUNT=0 → 返回 `"0"` → 与在用 `"1"` 语义相反，条件判断反向。
- **责任人**：lixin（`bf5fed093`；提交注释标注 --user ludongxu）
- **建议**：删除 `ClaimBenefitOfESBService` 中未使用的 `applicationEntryMapper` 注入及 `ApplicationEntryMapper` 接口/XML 中的 `checkDeductibleParamOfGNSR014`；如确需保留，统一因子名为 `Deductibles` 并补充调用方。

---

### 🟠 N-03 需求4.1/4.2：固定保额→年限额产品范围收窄为"仅企补(01)+第4位R"，中端(02) NGB 医疗产品失去原有自动映射，与"中端&GHB本次不涉及调整"冲突（【新】/待确认）

- **类/文件**：`ClaimBenefitOfESBService.java:471-476`（`createFixedAmountConBenifit`）
- **调用链**：
  ```
  第1117行  createFixedAmountConBenifit(grpPropNo, claimBenefitAppno, user, claimBenefitList)  ← 投保录入完成触发
  第471-472行  if (planDetails非空 && ldCode非空 && tLCGrpCont非空 && PRODTYPE=='00' && PRODBUSS=='01')   ← 外层范围
  第476行  if ("R".equals(planDetail.getRISKCODE().substring(3,4)))   ← 第4位为R
  ```
- **需求条款**：4.1 —— 生效对象"产品业务所属为'企补产品'，且产品代码第四位为 R 的所有 NGB 产品"；4.2 —— "注：中端&GHB本次不涉及调整"。
- **问题代码原文（472/476 行）**：
  ```java
  && null != tLCGrpCont && "00".equals(tLCGrpCont.getPRODTYPE()) && "01".equals(tLCGrpCont.getPRODBUSS())) {  // ❌ 新增 PRODBUSS=='01'
      planDetails.forEach(planDetail -> {
          if ("R".equals(planDetail.getRISKCODE().substring(3,4))) {   // ❌ 新增第4位R过滤
  ```
- **问题**：基线（迭代一，`08bfad123e`）外层仅 `PRODTYPE=='00'`（NGB），即**全部 NGB 医疗产品**固定保额均自动转年限额；迭代二（`77d583765`）新增 `PRODBUSS=='01'`（企补）+ 第4位 R 双重收窄。`PRODBUSS=='02'`（中端业务）NGB 医疗产品被一并剔除，**原自动映射消失**。这与需求 4.1"扩展与调整"的表述、以及 4.2"中端&GHB本次不涉及调整"（中端应保持原行为）存在口径冲突。
- **具体故障场景**：
  1. 数据前提：一张中端医疗（PRODBUSS='02'）NGB 保单，一级责任保额类型为固定保额，迭代一可自动生成年限额；
  2. 触发：本次升级后投保录入完成；
  3. 错误结果：外层 `PRODBUSS=='01'` 不满足 → 不再生成年限额 → 中端保单限额缺失（或依赖人工补录），与"中端不涉及调整"相悖。
- **责任人**：ludongxu（`77d583765`）
- **建议**：与需求方确认中端/GHB 原固定保额自动映射是否应保留。若应保留，外层改为 `PRODBUSS IN ('01','02')`（或按需求口径补充）；若仅企补+R 生效，需在需求中明确中端行为变更。
- **状态**：**待确认**（需求口径冲突，不自行判错）。

---

### 🟠 N-04 需求4.2/4.3/4.4：GCMS 同步节点、保全新增方案节点、"是否标准协议"默认否在本仓提交中无对应改动（【新】/核验受限）

- **类/文件**：本仓 RCP-10910-2 全部 7 个变更文件（均不涉及上述三节点）
- **调用链**：
  ```
  第1113行  dealGNSR014RiskBenefit(...)     ← 仅在投保录入完成（completeApplicationData）流程调用
  第1117行  createFixedAmountConBenifit(...) ← 仅投保录入完成流程调用
  （保全新增方案签发、GCMS 询报价单同步核心两节点在 nbx 无调用方）
  ```
- **需求条款**：4.2 数据范围含"GCMS运营复核通过同步核心时"、"保全新增方案签发后"；4.3 数据范围同上；4.4 页面默认"否"+历史数据处理。
- **问题**：本仓 nbx 的新逻辑（组合免赔额、组合限额、固定保额→年限额时间范围）仅接线在**投保录入完成**流程。需求文档列出的 GCMS 同步节点、保全新增方案节点，以及 4.4"是否标准协议"默认否/历史数据，在本仓提交中均无实现。参照同需求 legacy 报告，legacy 侧实现了保全(POS)流程与 4.4 ISSTANDARDPROTOCOL；GCMS 推送在 legacy 侧（`initIsNew`）。NGB 保单的保全/GCMS 同步是否同样落在 legacy 或其它服务，需确认，否则存在节点漏实现。
- **具体故障场景**：企补 NGB 保单走保全新增方案签发，若该流程不在 nbx（也未复用 nbx 该方法族），则新方案不会生成 GNSR014 组合福利/固定保额年限额 → 福利缺失。核验受限。
- **责任人**：—（需需求/架构确认归属系统，非单一代码缺陷）
- **建议**：确认 4.2/4.3 三节点的实现分布（nbx / legacy / 前端 / 数据脚本），列出覆盖矩阵；对未覆盖节点补实现或补脚本。
- **状态**：**核验受限**。

---

### 🟠 N-05 健壮性：`createGNSR014RiskBenefitOfDeductibles` 中 `premFactorInfo` 未判空即访问（【新】，低概率）

- **类/文件**：`ClaimBenefitOfESBService.java:423-424`（`createGNSR014RiskBenefitOfDeductibles`）
- **调用链**：
  ```
  第1190行  checkResult = checkDeductibleParamOfGNSR014(grpPropNo, planCode)   ← 前置闸口
  第1193行  createGNSR014RiskBenefitOfDeductibles(...)                          ← 生成入口
  第423行   premFactorInfo = queryMaxDeductiblesInfos(policyNo, planCode, riskCode)
  第424行   log.info("...premvalue:"+premFactorInfo.getPremValue()...)          ← 问题所在：可能 null
  第425行   setBaseBenefitInfo(claimBenefit,"20",premFactorInfo.getPremValue(),"10")
  ```
- **需求条款**：4.3.1 —— "系统需自动在险种（产品）层新生成1条组合型「免赔额」福利配置"
- **问题代码原文（423-426 行）**：
  ```java
  LcPremFactorInfosVo premFactorInfo = lcContPlanDetailMapper.queryMaxDeductiblesInfos(policyNo, planLcClaimDutyClaimTree.getNODECODE(), riskLCClaimDutyClaimTree.getNODECODE());
  log.info("查询最大免赔额对应保费因子数据,premvalue:"+premFactorInfo.getPremValue()+",type:"+premFactorInfo.getType()+",claimscope:"+premFactorInfo.getClaimScope());   // ❌ 未判空
  setBaseBenefitInfo(claimBenefit, "20", premFactorInfo.getPremValue(), "10");   // ❌ 未判空
  ```
- **问题**：前置闸口 `checkDeductibleParamOfGNSR014=="1"` 与 `queryMaxDeductiblesInfos` 同为 `PREMFACTOR='Deductibles'` 查询，正常时若闸口命中则查询必有行，NPE 概率低；但两者过滤条件存在细微差异（闸口硬编码 `RISKCODE='GNSR014'`，查询用入参 `#{riskCode}`），一旦风险节点编码/方案数据不一致导致查询返回空，`premFactorInfo` 为 null → 日志拼接与取值直接 NPE，中断福利生成且无任何兜底。与 legacy L-01 同模式。
- **具体故障场景**：GNSR014 风险层福利树 `NODECODE` 非标准 'GNSR014'（如复制方案编码变形）→ 闸口命中但查询按入参匹配不到 → `queryMaxDeductiblesInfos` 返回 null → 第 424 行 NPE → 组合免赔额缺失。
- **责任人**：lixin（`01e328b64`；提交注释标注 --user SZW250323）
- **建议**：查询后判空，为空 `log.warn` 并 `return`（跳过组合生成），避免中断整体福利流程。

---

### 🟡 N-06 需求4.3.1：组合免赔额"下级责任"硬编码且取值/校验未限定两个一级责任（【新】/核验受限）

- **类/文件**：`ClaimBenefitOfESBService.java:420`（硬编码）；`LcContPlanDetailMapper.xml:504-522`（`checkDeductibleParamOfGNSR014`）、`525-560`（`queryMaxDeductiblesInfos`）
- **需求条款**：4.3.1 —— "下级责任：一般医疗、特定疾病医疗"；取值与一致性判断应限于这 2 个一级责任。
- **问题代码原文**：
  ```java
  String dutyCodeString = "GNSR014001,GNSR014002";   // 硬编码（420行）
  ```
  ```sql
  -- checkDeductibleParamOfGNSR014 / queryMaxDeductiblesInfos 均未限定 DUTYCODE ∈ ('GNSR014001','GNSR014002')
  WHERE ... AND l.PREMFACTOR = 'Deductibles'
        AND l.PLANCODE = #{planCode}
        AND l.RISKCODE = 'GNSR014'      -- 只限险种，不限两个一级责任
  ```
- **问题**：组合"下级责任"写死两个编码（与同方法族年限额组合 `getDutyCodeString` 动态查询口径不一致）；而**一致性校验与取大查询没有按责任过滤**，若 GNSR014 下除「一般医疗、特定疾病医疗」外还存在其他带 Deductibles 因子的责任（子责任/另两个一级责任），会把这些责任一并卷入判断与取值：取值可能取到非目标责任的更大值，校验也可能因非目标责任不一致而误判"不生成组合"。是否实际触发取决于 GNSR014 数据结构，核验受限。
- **具体故障场景**：某 GNSR014 方案下子责任带更大免赔额因子 → `queryMaxDeductiblesInfos` 取到子责任的值填充组合 → 组合免赔额福利值虚高，理赔抵扣口径错误。
- **责任人**：lixin（`ce0da58e8` 硬编码组合责任 / `01e328b64`、`330056deb` 取值与校验）
- **建议**：与需求/数据确认 GNSR014 是否仅 2 个一级责任含 Deductibles 因子；如否，`checkDeductibleParamOfGNSR014` 与 `queryMaxDeductiblesInfos` 均加 `l.DUTYCODE IN ('GNSR014001','GNSR014002')` 限定；`COMBINADUTYCODES` 改动态查询或提升为常量并核验与取值范围一致。
- **状态**：**核验受限**。

---

### 🟡 N-07 需求4.3.2：年限额组合"下级责任"由 `getDutyCodeString` 查询该险种全部责任，未限定一级责任（【新】/核验受限）

- **类/文件**：`ClaimBenefitOfESBService.java:405` + `LcContPlanDetailMapper.xml:561-567`（`getDutyCodeString`）
- **需求条款**：4.3.2 —— "下级组合责任：默认选中当前产品下的**所有一级责任**（一般医疗保险金、特定疾病医疗保险金、质子重离子医疗保险金、特定疾病异地转诊保险金）"
- **问题代码原文（getDutyCodeString）**：
  ```sql
  SELECT LISTAGG(l.DUTYCODE, ',') WITHIN GROUP (ORDER BY l.DUTYCODE) AS DUTYCODES
  FROM LCCONTPLANDETAIL l
  WHERE l.POLICYNO = #{policyNo} AND l.PLANCODE = #{planCode} AND l.RISKCODE = #{riskCode}   -- 取全部责任
  ```
- **问题**：查询返回该险种 `LCCONTPLANDETAIL` 中的**所有**责任编码，未区分一级/非一级。若 GNSR014 在计划明细中存在子责任记录，`COMBINADUTYCODES` 将混入非一级责任，与需求"所有一级责任（4 个）"不符。对照 4.3.1 硬编码的两个责任（N-06），同一方法族两种口径并存。实际是否触发取决于 GNSR014 计划明细是否含子责任，核验受限。
- **具体故障场景**：GNSR014 计划明细含子责任（如 GNSR014101 等）→ 年限额组合"下级责任"含子责任 → 理赔组合抵扣关系错乱。
- **责任人**：lixin（`ce0da58e8`）
- **建议**：确认 GNSR014 `LCCONTPLANDETAIL` 是否仅含 4 个一级责任；如否，查询按一级责任（如 `DUTYCODE` 第 7 位为 '1' 或其他层级标识）过滤。
- **状态**：**核验受限**。

---

### 🟡 N-08 规范：`createFixedAmountConBenifit` 内层 PRODBUSS 判断冗余（【新】）

- **类/文件**：`ClaimBenefitOfESBService.java:490`
- **问题代码原文**：
  ```java
  if ("01".equals(tLCGrpCont.getPRODBUSS())) {      // ❌ 外层472行已判 PRODBUSS=='01'，冗余
      timeunit = dealTimeUnitOfFixAmntBenifit(policyNo, planDetail);
  }
  ```
- **问题**：外层条件（472 行）已限定 `PRODBUSS=='01'`，内层再次判断恒真，属冗余死分支，且语义易误导（暗示存在 PRODBUSS 非 01 的场景）。
- **责任人**：ludongxu（`77d583765`）
- **建议**：删除内层判断，直接调用 `dealTimeUnitOfFixAmntBenifit`。

---

### 🟡 N-09 规范：`LcContPlanDetailMapper.xml` resultMap 增加 AMNTUNIT 列但 `Base_Column_List` 未同步（【新】）

- **类/文件**：`LcContPlanDetailMapper.xml:43`（resultMap 增列）与 `:45-55`（Base_Column_List 未增）
- **问题代码原文**：
  ```xml
  <!-- 43行 resultMap：已增加 -->
  <result column="AMNTUNIT" jdbcType="VARCHAR" property="AMNTUNIT" />
  <!-- 45-55行 Base_Column_List：仍不含 AMNTUNIT -->
  <sql id="Base_Column_List">POLICYNO, SYSPLANCODE, ..., TEMPLATENO</sql>
  ```
- **问题**：MBG 生成代码字段同步不完整——`selectByPrimaryKey` 走 `Base_Column_List`，不返回 AMNTUNIT（当前 `queryPlanDetailByAmnttype` 显式 SELECT 含该列，功能无碍）。但模型已加字段、查询列未加，后续复用 `selectByPrimaryKey` 取保额单位会静默得 null，属生成代码同步隐患。
- **责任人**：lixin（`330056deb`）
- **建议**：`Base_Column_List` 补入 `AMNTUNIT`，与 resultMap 同步。

---

### 🟡 N-10 规范：生产 INFO 日志打印保单号/方案号/免赔额明细（【新】，同 legacy L-10）

- **类/文件**：`ClaimBenefitOfESBService.java:422-424、535、541-542、211`
- **问题代码原文**：
  ```java
  log.info("查询最大免赔额对应保费因子数据,policyNo:"+policyNo);            // ❌ INFO 日志泄漏保单号
  log.info("保单号:"+policyno+",方案编码:"+planDetail.getPLANCODE()+",责任编码:"+planDetail.getDUTYCODE());  // ❌
  ```
- **问题**：INFO 级日志直接拼接保单号/方案号/免赔额数据，存在敏感信息落盘与日志膨胀风险（生产 INFO 级别下持续写入）。
- **责任人**：lixin（`01e328b64` / `330056deb`）
- **建议**：降为 `log.debug`，或对保单号脱敏。

---

## 三、已修复项

本仓为 cgis-web-nbx 首评，无上版对比。注：`e215f94a4`（最新提交）将 `checkGNSR014OfDutyCondition` 拦截从"所有因子"收窄为仅 `Deductibles` 因子，修复"复制 GCMS 安怡万家方案后责任层赔付比例(GetRate)配置丢失"问题——该修复经核验正确（拦截仅作用于免赔额，赔付比例正常映射责任层）。

## 四、跨仓库一致性（重点确认）

| # | 项 | cgis-web-nbx | cgis-legacy-app | 结论 |
|---|----|-------------|-----------------|------|
| C1 | `queryMaxDeductiblesInfos` 取大排序 | `ORDER BY l.premvalue DESC`（VARCHAR）❌ | 同 `ORDER BY l.premvalue DESC` ❌ | **双仓同缺陷**，见 N-01 |
| C2 | 4.2 时间范围回退（AMNTUNIT 为空查产品配置） | `dealTimeUnitOfFixAmntBenifit` 有 else 回退 ✅ | NB 分支**无**回退（legacy 报告 L-04）❌ | **口径不一致**，nbx 实现正确，legacy 缺回退 |
| C3 | 组合免赔额"下级责任" | 硬编码 `GNSR014001,GNSR014002`（N-06） | 硬编码同串（legacy 报告 L-03）❌ | 双仓同模式，均待需求确认 |
| C4 | 一致性校验字段 | 仅 3 字段（CLAIMSCOPE/TYPE/DEDUCTIBLEMETHOD，N-06） | 同 3 字段（legacy 报告 L-05） | 双仓同模式，需确认字段全集 |
| C5 | 组合免赔额 `premFactorInfo` 判空 | 未判空（N-05，概率低） | 未判空（legacy 报告 L-01，概率高） | 同模式，nbx 因闸口同查询概率低 |

> 重点：C2 为双仓行为差异（nbx 已实现需求回退、legacy 未实现），需开发确认以 legacy 口径补齐。C1 为双仓共同正确性缺陷，应一并修复。

## 五、需求待确认事项

| # | 待确认内容 | 关联章节 | 关联问题 |
|---|-----------|---------|---------|
| D1 | 中端(02)/GHB(03) NGB 产品原"固定保额自动转年限额"是否应保留？本仓迭代二已将其移除。 | 4.1/4.2 | N-03 |
| D2 | 4.2/4.3 三节点（GCMS同步、投保录入、保全新增方案）实现分布：本仓仅投保录入节点；保全/GCMS 在 legacy 还是其它系统？ | 4.2/4.3 | N-04 |
| D3 | 4.4"是否标准协议"默认"否"：页面在 cgis-front-gemini、历史数据脚本在 gis-sql 的实现/脚本是否已安排？本仓无改动。 | 4.4 | N-04 |
| D4 | GNSR014 除「一般医疗、特定疾病医疗」两个一级责任外，是否还有其他责任带 Deductibles 因子？若是，取值/校验范围需限定。 | 4.3.1 | N-06 |
| D5 | GNSR014 `LCCONTPLANDETAIL` 是否仅含 4 个一级责任（无子责任记录）？`getDutyCodeString` 需据此确认是否过滤。 | 4.3.2 | N-07 |
| D6 | 4.3.1"时间范围：根据…免赔方式自动填充"与"家庭范围按免赔方式映射个人/家庭"在文档中表述混杂；代码时间范围取 `premFactorInfo.getType()`、家庭范围按 DEDUCTIBLEMETHOD，请确认需求口径。 | 4.3.1 | — |

## 六、责任分派建议

| 开发者（%an） | 待处理问题 |
|--------------|-----------|
| lixin | N-01（组合免赔额取大排序）、N-02（死代码）、N-05（判空）、N-06/N-07（组合责任范围）、N-09（MBG 同步）、N-10（日志） |
| ludongxu | N-03（范围收窄口径）、N-08（冗余判断） |

专项：N-03、N-04、D1~D6 为需求/架构口径问题，建议与需求方（高亚楠）及架构确认后统一排期。

## 七、建议修改顺序

- **先改**：N-01（正确性，双仓同修）、N-02（死代码清理，防误用）；
- **次改**：N-05（判空兜底）、N-03（与需求确认后调整范围）；
- **顺手**：N-06/N-07（随 GNSR014 数据核验后限定责任范围）、N-08/N-09/N-10（规范类）。

## 八、排除项（区间内混入其它需求，已剔除）

| 文件 | 被剔除的改动 | 实际变更来源 |
|------|------------|------------|
| `ApplicationEntryService.java` | 渠道停售校验（`channelInfoTing`/`containsChannel` 抛异常）、`checkChannelExpireRiskFlag` 日志 | TAPD-1018351（`b12746a5e`）、禁售险种开关日志（`2b38b80a6`） |
| `ApplicationEntryMapper.java` | `queryAnnualPersonalPremFlagByZT` 方法声明 | RCP-13484（`391078457`） |
| `ApplicationEntryMapper.xml` | `queryExpireRisk` 增 `b.businessunit`；`queryAnnualPersonalPremFlagByZT` SQL | TAPD-1018351（`b12746a5e`）、RCP-13484（`391078457`） |

## 九、变动文件清单（本需求最终版本净变更）

> 取自 `git log --name-status` 逐文件核对；7 个文件全部为 M（修改），无新增/删除。

| 序号 | 变更 | 文件路径 | 变更内容概述 |
|-----|-----|---------|------------|
| 1 | M | `src/main/java/com/cignacmb/cgis/nbx/application/mapper/ApplicationEntryMapper.java` | 新增 `checkDeductibleParamOfGNSR014` 方法声明（因子名 `DeductibleType`，死代码，全仓未调用） |
| 2 | M | `src/main/java/com/cignacmb/cgis/nbx/application/service/ApplicationEntryService.java` | 投保录入完成流程：`dealGNSR014RiskBenefit` 增加 GNSR014 组合免赔额生成块（`checkDeductibleParamOfGNSR014` 闸口 + `createGNSR014RiskBenefitOfDeductibles`） |
| 3 | M | `src/main/java/com/cignacmb/cgis/nbx/application/service/ClaimBenefitOfESBService.java` | 核心业务：GNSR014 组合免赔额/年限额组合（COMBINAFLAG=1 + COMBINADUTYCODES）、`checkGNSR014OfDutyCondition` 责任层免赔额拦截、固定保额→年限额范围收窄（企补+R）与时间单位映射、`Deductibles` 拦截收窄修复（e215f94a4） |
| 4 | M | `src/main/java/com/cignacmb/cgis/nbx/mapper/LcContPlanDetailMapper.java` | 新增 `checkDeductibleParamOfGNSR014` / `queryMaxDeductiblesInfos` / `queryAmntUnitOfDutyCode` 方法声明 |
| 5 | M | `src/main/java/com/cignacmb/cgis/nbx/model/LcContPlanDetail.java` | 新增 `AMNTUNIT` 字段 + getter/setter |
| 6 | M | `src/main/resources/mapper/com/cignacmb/cgis/nbx/application/mapper/ApplicationEntryMapper.xml` | 新增 `checkDeductibleParamOfGNSR014`（`DeductibleType` 变体，死代码） |
| 7 | M | `src/main/resources/mapper/com/cignacmb/cgis/nbx/mapper/LcContPlanDetailMapper.xml` | resultMap 增 `AMNTUNIT` 列；新增 `checkDeductibleParamOfGNSR014` / `queryMaxDeductiblesInfos` / `queryAmntUnitOfDutyCode`；`queryPlanDetailByAmnttype` 增 `AMNTUNIT` 列 |

## 十、提交记录清单（本需求全部 Git 提交，按新→旧排列）

> 取自 `git log --format="%h|%an|%ad|%s"`，顺序与 git log / IDEA 提交记录一致（新提交在上）；提交人为 Git 实际作者 `%an`，与提交注释内 `--user` 无关。

| 序号 | 提交编号 | 提交注释 | 提交人 | 提交时间 |
|-----|---------|---------|-------|---------|
| 1 | e215f94a4 | 福利树项目迭代二：新单投保录入复制GCMS安逸万家的方案，点击投保录入完成，理赔福利配置中GCMS方被复制的方案中，责任层级的赔付比例配置会丢失 bug 修复（--user ludongxu） | ludongxu | 2026-08-11 17:22:01 |
| 2 | 06c16ae3a | 福利树项目迭代二：安怡万家生成组合免赔额错误问题调整（--user ludongxu） | ludongxu | 2026-08-06 12:14:17 |
| 3 | ad3fc4d5d | 福利树项目迭代二：安怡万家生成组合免赔额问题调整（--user ludongxu） | ludongxu | 2026-08-06 09:53:29 |
| 4 | 8a4ecf7a4 | 福利树项目迭代二：安怡万家不生成组合免赔额问题调整（--user ludongxu） | ludongxu | 2026-08-05 15:28:55 |
| 5 | 2bc24c4ae | 福利树项目迭代二：限额时间范围映射规则调整投保录入新增方案保额单位取险种配置（--user ludongxu） | lixin | 2026-06-08 17:16:21 |
| 6 | 87fb525bf | 福利树项目迭代二：GNSR014产品层限额福利调整，新增组合责任（--user ludongxu） | ludongxu | 2026-07-30 19:51:49 |
| 7 | 77d583765 | 福利树项目迭代二：固定保额自动映射规则调整（--user ludongxu） | ludongxu | 2026-07-13 17:06:26 |
| 8 | ce0da58e8 | 福利树项目迭代二：GNSR014产品层限额福利调整，新增组合责任（--user SZW250323） | lixin | 2026-06-26 11:22:38 |
| 9 | f614ff747 | 福利树项目迭代二：部分无用代码调整（--user SZW250323） | lixin | 2026-06-16 16:13:42 |
| 10 | 330056deb | 福利树项目迭代二：安怡万家产品层限额映射规则新增（--user SZW250323） | lixin | 2026-06-16 10:49:03 |
| 11 | 01e328b64 | 福利树项目迭代二：安怡万家产品层免赔额映射规则新增（--user SZW250323） | lixin | 2026-06-15 11:02:30 |
| 12 | bf5fed093 | 福利树项目迭代二：GNSR014产品层限额福利调整，新增组合责任（--user ludongxu） | lixin | 2026-06-08 17:16:21 |

> 备注：排序按提交图拓扑/git log 默认序（新→旧），时间列显示作者时间 `%ad`。本仓历史经 cherry-pick 重建，作者时间与图序存在倒挂（如 2bc24c4ae 作者时间 6-08 但拓扑上位于 87fb525bf 之后），IDEA 展示亦为同一顺序，时间仅供查看参考。
