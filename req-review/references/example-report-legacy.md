# RCP-10910-2 福利树迭代二 SIT 分支代码评审报告

- **评审时间**：2026-08-12 09:47:22（v2 完整版：所有问题条目均含精确代码位置 / 问题代码原文 / 故障场景）
- **评审人**：开发组长（Claude 代评）
- **评审对象**：cgis-legacy-app / cgis-web-nbx / cgis-web-nb 三个仓库 `origin/sit` 分支上，提交备注含 `RCP-10910-2` 的代码（聚合为最终版本评审）
- **需求文档**：RCP-15793《NHB保单福利配置和理算规则升级（项目实施--第一个迭代）--需求规格说明书**v0.9**》
- **提交人**：lixin（SZW250323）、ludongxu、Xi Cheng（SZW250375）

---

## 〇、本次复评基线说明（重要）

1. **需求基线**：v0.9 与 v0.8 逐字比对**完全一致**（`diff` 无差异），业务规则未变更，因此以 v0.9 为准评审，结论与 v0.8 一致。
2. **代码基线**：复评时已重新拉取三个仓库 `origin/sit`。最新 RCP-10910-2 提交仍为 legacy `27e33cc139` / nbx `e215f94a4` / nb `67a9f1a0`；legacy sit 虽有新提交（`fbe9e9504e` RCP-16143），但**未触碰任何 RCP 涉及文件**（已用 `git diff 27e33cc139 origin/sit` 校验为空）。即本需求代码与上一版评审时**完全一致**。
3. **结论**：所有问题项与上版评审一致（🔴3 个未修复 + 本轮新增 🔴1 个/🟠1 个/🟡1 个，共 🔴4/🟠9/🟡5，另 ✅2 个已修复）。本报告为最新基准的正式完整版。

---

## 一、评审范围与方法

### 1.1 覆盖的提交

| 仓库 | 提交数 | 时间跨度 | 主要提交人 |
|------|-------|---------|-----------|
| cgis-legacy-app | 29 | 06-08 ~ 08-11 | lixin、ludongxu、Xi Cheng |
| cgis-web-nbx | 12 | 06-08 ~ 08-11 | lixin、ludongxu |
| cgis-web-nb | 2 | 06-15 ~ 06-22 | lixin |

### 1.2 评审方法

- 每个仓库将全部 RCP-10910-2 提交**聚合**（最早提交父节点 → 最新提交）得到本需求最终版本的净变更 diff 后评审，避免中间态问题。
- 已校验：legacy RCP 涉及文件在 `origin/sit` HEAD 与最新 RCP 提交 `27e33cc139` 一致；聚合区间内对 RCP 文件的改动全部来自 RCP-10910-2 提交。nbx 已按文件剔除区间内其它需求（RCP-13484-pos、TAPD-1018351）的改动（见第八节）。
- 每条问题均标注：仓库 / 文件:行 / 需求条款 / 问题代码原文 / 具体故障场景 / 责任开发者（附提交）/ 修改建议。

### 1.3 需求要点（v0.9，对照用）

- **4.1** 固定保额自动映射：企补 + 产品代码第 4 位为 R 的 NGB 产品。
- **4.2** 限额时间范围映射：保额单位"元/天"→日，其他→年；GCMS 同步 / 投保录入（GCMS 方案用 GCMS 单位，否则回退产品配置）/ 保全（一律产品配置）。
- **4.3** 安怡万家(GNSR014)保费因子：两个一级责任免赔额**除福利值外全部一致**才生成组合免赔额（取大），家庭范围随免赔方式；险种层年限额组合责任=全部一级责任。
- **4.4** 是否属于标准协议：企补保单险种层统一默认**"否"**；GHB/中端**本次不涉及**。

---

## 二、问题清单（按严重程度排序）

> 🔴=高（需求符合性/正确性） 🟠=中（健壮性/一致性） 🟡=低（质量/规范）。【新】=本轮评审新增；其余标注状态。

---

### 🔴 L-01 需求4.2：legacy 投保录入(NB)场景缺产品配置回退（未修复）

> **说明**：这里的"NB 分支"指 `cgis-legacy-app` 源码内部、`dealTimeUnitOfFixAmntBenifit` 方法中 `bussType == "NB"`（新单投保录入场景）的那段 `if` 分支，**与 `cgis-web-nb` 仓库无关**。同一方法内还有 `"POS"`（保全场景）分支。

- **类/文件**：cgis-legacy-app `java/com/cignacmb/gcis/app/service/LCContPlanDetailService.java`
- **问题代码**：`dealTimeUnitOfFixAmntBenifit(...)`（**第 588 行**）中 **第 590-595 行**（`if("NB".equals(bussType))` 分支）
- **调用链**：
  ```
  第427行  createFixedAmountConBenifit("NB", ...)   ← 新单投保录入场景入口
  第524行  private void createFixedAmountConBenifit(bussType, ...)  { ... if (PRODBUSS=="01") { ... } }
  第569行      timeunit = dealTimeUnitOfFixAmntBenifit(policyno, bussType, planDetail);
  第588行  private String dealTimeUnitOfFixAmntBenifit(...) {   ← 问题所在
  第590-595行   NB 分支：只读 planDetail.getAMNTUNIT()
  ```
- **需求条款**：4.2 投保录入场景——"如果 GCMS 未同步保额单位，**需根据产品配置表中的一级责任对应的保额单位进行映射**"
- **问题代码原文（legacy，590-595 行）**：
  ```java
  if("NB".equals(bussType)) {
      String nbTimeunit = planDetail.getAMNTUNIT();            // 只读 GCMS 同步来的保额单位
      logger.info("NB-保单号:"+policyno+",aTimeunit:"+nbTimeunit);
      if (StringUtils.isNotBlank(nbTimeunit) && "1".equals(nbTimeunit)){
          timeunit = "20";                                     // 只有 AMNTUNIT=="1"(元/天) 才给"日"
      }
      // ❌ AMNTUNIT 为空时什么都不做，timeunit 保持第589行默认值 "30"(年)
  }
  else if("POS".equals(bussType)) {
      String posTimeunit = tLCContPlanDetailInfoMapper.queryAmntUnitOfDutyCode(planDetail.getRISKCODE(), planDetail.getDUTYCODE());  // ✅ 查产品配置 LMDUTY
      if (StringUtils.isNotBlank(posTimeunit) && "1".equals(posTimeunit)){
          timeunit = "20";
      }
  }
  ```
  **缺的就是 AMNTUNIT 为空时的回退查产品配置**。POS 分支（第 597 行）和 nbx 都有，唯独 NB 分支没有。
- **对照：nbx 同功能方法（`ClaimBenefitOfESBService.java:531-553`，已实现回退）**：
  ```java
  if (StringUtils.isNotBlank(planDetail.getAMNTUNIT())){      // GCMS 有保额单位 → 用它
      if ("1".equals(planDetail.getAMNTUNIT())) timeunit = "20";
  }else{                                                      // ✅ GCMS 没有 → 回退查产品配置
      String posTimeunit = lcContPlanDetailMapper.queryAmntUnitOfDutyCode(...);
      if (StringUtils.isNotBlank(posTimeunit) && "1".equals(posTimeunit)) timeunit = "20";
  }
  ```
- **具体故障场景**：
  1. 企补保单投保录入，GCMS **未同步**保额单位 → 保单 `LCCONTPLANDETAIL.AMNTUNIT` 为空；
  2. 但产品配置 `LMDUTY` 中该一级责任保额单位 = `1`（元/天）；
  3. 按需求应生成"**日**"(20) 的年限额，legacy 代码却输出默认 `"30"`（**年**）。
  → 固定保额转年限额时时间范围错误（该生成"日"却生成了"年"），理赔限额管控口径随之错误；且 legacy（缺回退）与 nbx（有回退）同需求行为不一致。
- **责任人**：lixin（`1b20d40941`）
- **建议**：legacy NB 分支补上与 nbx 一致的回退逻辑；以 GCMS 保额单位是否为空作为"GCMS 方案"判断依据。

---

### 🔴 L-02 需求4.3：组合免赔额"一致性校验"只比较 3 个字段（未修复）

> **说明**：该问题同时存在于 legacy 与 nbx，SQL 为同一段，两处都需要改。

- **类/文件**：
  - cgis-legacy-app `java/SqlInfo/app/LCContPlanDetailInfoMapper.xml` `checkDeductibleParamOfGNSR014`
  - cgis-web-nbx `src/main/resources/mapper/com/cignacmb/cgis/nbx/mapper/LcContPlanDetailMapper.xml:486-501`
- **调用链**：
  ```
  生成组合免赔额前判断：
  legacy  LCContPlanDetailService.java:358（NB流程）/ :1158（POS流程）  checkDeductibleParamOfGNSR014(...)=="1" → 生成组合免赔额
  nbx     ClaimBenefitOfESBService.java:216（checkGNSR014OfDutyCondition）  同上
  ```
- **需求条款**：4.3 ——"除福利值外的**所有**福利信息不完全一致，系统不生成组合免赔额"
- **问题代码原文（SQL，两库一致）**：
  ```sql
  SELECT COUNT(1) FROM (
      SELECT DISTINCT l.CLAIMSCOPE, l."TYPE", lpd.DEDUCTIBLEMETHOD      -- ❌ 只比这 3 列
      FROM LcPremFactorInfos l
          LEFT JOIN LCCONTPLANDETAIL lpd ON l.POLICYNO = lpd.POLICYNO
      WHERE l.POLICYNO = #{policyNo}
        AND l.SYSPLANCODE = lpd.SYSPLANCODE AND l.PLANCODE = lpd.PLANCODE
        AND l.RISKCODE = lpd.RISKCODE AND l.DUTYCODE = lpd.DUTYCODE
        AND l.PREMFACTOR = 'Deductibles'
        AND l.PLANCODE = #{planCode}
        AND l.RISKCODE = 'GNSR014'
  )
  ```
  DISTINCT 计数 = 1 → 判定"两责任免赔额信息一致" → 生成组合免赔额。
  **未参与比较的字段**：是否等待期、是否梯度赔付、规则组、免赔额抵扣顺序、优先级、单位等——这些在生成时都是固定默认值（`WAITINGPERIOD=0`、`GRADIENTFLAG=0`、`BENEFITGROUP=10`、`SPECIALRULE=20`、`BENFITUNIT=10`），意味着**即使两责任在这些字段上配置不同，系统也会按统一默认值生成组合免赔额**。
- **具体故障场景**：
  1. 一般医疗保险金、特定疾病医疗保险金两个责任的免赔额因子，`CLAIMSCOPE/TYPE/DEDUCTIBLEMETHOD` 恰好相同，但**免赔额抵扣顺序、等待期、梯度赔付**配置不同；
  2. 按需求"除福利值外所有信息一致才生成"应**不生成**组合免赔额；
  3. 代码 DISTINCT 计数 = 1 → **仍生成**组合免赔额，且生成时把不同字段强行覆盖成统一默认值 → 与需求不符，且丢失两个责任原有的差异配置。
- **责任人**：lixin（`17bbe85cc1`/`9d84813e56`）
- **建议**：与需求方确认"除福利值外"需要比较的字段全集，把可比字段全部纳入 DISTINCT；并核对 `LEFT JOIN LCCONTPLANDETAIL` 是否会把质子重离子等其它责任的免赔额因子也卷入比较导致误判。

---

### 🔴 L-03 需求4.3：nbx 组合免赔额生成仅覆盖"投保录入"流程；保全场景与双系统双写风险待确认（未修复）

- **类/文件**：cgis-web-nbx `src/main/java/com/cignacmb/cgis/nbx/application/service/ApplicationEntryService.java`
- **调用链（nbx）**：
  ```
  第1014行  completeApplicationData(...)                    ← 投保录入完成场景
  第1111行      dealGNSR014RiskBenefit(grpPropNo, claimBenefitAppno, user, claimBenefitList);
  第1177行  private void dealGNSR014RiskBenefit(...) {
  第1186行      createGNSR014RiskBenefitOfYearLimt(...)      // 生成险种层年限额组合
  第1191行      createGNSR014RiskBenefitOfDeductibles(...)   // 生成险种层组合免赔额
  }
  ```
  **全库检索：`dealGNSR014RiskBenefit` 只有第 1111 行一个调用点，位于投保录入流程；未发现保全(POS)流程调用。**
- **对照：legacy 的对应实现（两个场景都有）**：
  ```
  第427行 createFixedAmountConBenifit("NB",...)  +  第346-370行 内联 GNSR014 限额/免赔额生成  ← 投保录入(NB)
  第1139行 createGNSR014RiskBenefitInfo(...)      ← 保全(POS)场景入口（含 :1153 年限额、:1158 免赔额）
  ```
- **需求条款**：4.3 数据范围含三场景：GCMS 复核同步、投保录入完毕、**保全新增方案签发后**
- **问题**：
  1. **nbx 保全场景未覆盖**：若 nbx 需承担需求场景 3，则保全新增方案后组合免赔额/年限额不会生成（legacy 侧有，nbx 侧无）——需与架构确认保全福利生成到底走 legacy 还是 nbx；
  2. **双系统双写风险**：legacy 投保录入流程（`:346-370`）与 nbx 投保录入流程（`:1111`）**都在**生成 GNSR014 组合福利。若同一张保单的投保录入在两个系统各跑一遍，就会重复生成——这很可能正是 legacy 08-10 连续 3 个"数据重复 bug"提交的根因（见 L-06）。
- **具体故障场景**：对同一 GNSR014 保单，legacy 与 nbx 的投保录入链路都执行 → `LCClaimBenefit` 出现 2 条组合免赔额/年限额（数据重复，理赔时重复扣减）。
- **责任人**：ludongxu（nbx 集成 `87fb525bf`）、lixin（legacy 初版）
- **建议**：拉通 legacy/nbx 的 NB、POS 链路，确认生成入口唯一性；必要时按（BENEFITAPPNO+DUTYSERIALNO+BENIFITTYPE+COMBINAFLAG）做唯一键幂等。

---

### 🔴 L-14【新】需求4.4：默认值"一刀切改为 0"，越出"企补险种层"范围，且与条件逻辑矛盾

- **类/文件**：cgis-legacy-app `java/com/cignacmb/gcis/app/service/LCContPlanDetailService.java`、`java/com/cignacmb/gcis/nb/service/ClaimBenefitTransformService.java:159`
- **改动来源**：`1b37845069`（ludongxu）把多处 `setISSTANDARDPROTOCOL("1")` 改为 `"0"`；`27e33cc139`（ludongxu）把 `copyPlanBenefit` 险种层节点 3 改为无条件 `"0"`。
- **问题代码（改后现状）**：
  ```java
  // ① 以下路径全部无条件设 "0"(否)，不再区分产品类型：
  第206行   tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");   // 根节点(NODETYPE=1)
  第633行   tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");   // insertDutyInfo
  第864/905行 tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0"); // 方案层
  第1506行  tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");   // insertDutyInfoNoM
  第3010行  tLCClaimDutyClaimTree3.setISSTANDARDPROTOCOL("0");  // copyPlanBenefit 险种层节点
  第3377行  tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");   // copyPlanBenefit
  ClaimBenefitTransformService.java:159 setISSTANDARDPROTOCOL("0");

  // ② 但 saveRiskBenefitInfo 仍是条件逻辑（第792-794行）：
  LCGrpCont lcGrpCont = ...queryLcGrpContInfo(policyNo);
  if (StringUtils.isNotBlank(lcGrpCont.getPRODBUSS()) && "01".equals(lcGrpCont.getPRODBUSS())) {
      tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");   // 企补 → 否
  } else {
      tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("1");   // 非企补 → 是
  }
  ```
- **需求条款**：4.4 —— 仅企补保单**险种层**默认"否"；**GHB/中端本次不涉及**
- **问题**：
  1. **越界**：非企补(GHB/中端)保单若走 `copyPlanBenefit`/`insertDutyInfo` 等路径，其"是否属于标准协议"默认值从"是"变"否"，违反"GHB/中端不涉及"；
  2. **自相矛盾**：同一非企补保单，险种层节点(`saveRiskBenefitInfo`)仍为"1"(是)，其它层级节点却为"0"(否)——同保单内字段值不一致；
  3. 需求只要求**险种层**字段，本次改动波及所有层级节点，影响面（前端/理算是否使用该字段）未确认。
- **具体故障场景**：一张 GHB（高端医疗）保单保全新增方案走 `copyPlanBenefit` → 险种层"是否属于标准协议"从"是"变"否"，但该保单在 `saveRiskBenefitInfo` 建出的节点仍是"是" → 理赔福利录入页同一保单不同节点显示不一致，且 GHB 业务被错误标记为"非标准协议"。
- **责任人**：ludongxu（`1b37845069`、`27e33cc139`）
- **建议**：默认"否"统一只对**企补保单**生效（以 `PRODBUSS='01'` 判断），其它产品保持原默认；所有设置点收敛为同一判断逻辑，避免两套口径并存。

---

### 🟠 L-04 需求4.4：复制方案流程硬编码"是" —— **已修复**（27e33cc139）

- **修复内容**：`copyPlanBenefit` 节点 2/4/5/6（`:2925/:3089/:3175/:3259`）改为"源节点 ISP 非空则继承，否则默认 0"；险种层节点 3（`:3010`）默认"0"。
- **修复后代码示例（`copyPlanBenefit` 节点 2，第 2925-2928 行）**：
  ```java
  if(StringUtils.isNotBlank(lcClaimDutyClaimTree2.getISSTANDARDPROTOCOL())){   // 源节点（被复制的旧节点）
      tLCClaimDutyClaimTree2.setISSTANDARDPROTOCOL(lcClaimDutyClaimTree2.getISSTANDARDPROTOCOL());
  }else{
      tLCClaimDutyClaimTree2.setISSTANDARDPROTOCOL("0");
  }
  ```
  源→目标复制，符合"保全复制方案时继承原方案标准协议"的业务语义，方向正确。
- **责任人**：ludongxu（`27e33cc139`）
- **遗留**：修复后仍存在 L-14 的"非企补也被改 0"问题；`1b37845069` 在 `:947-951` 存在无操作分支，见 L-15。

---

### 🟠 L-05 需求4.4：`queryLcGrpContInfo` 无判空，保单缺失 NPE；且 N+1 查询（未修复）

- **类/文件**：cgis-legacy-app `java/com/cignacmb/gcis/app/service/LCContPlanDetailService.java:787-793`（`saveRiskBenefitInfo`）
- **问题代码原文**：
  ```java
  LCGrpCont lcGrpCont = tLCContPlanDetailInfoMapper.queryLcGrpContInfo(curBenefitParamVo.getPOLICYNO());
  // ❌ lcGrpCont 可能为 null（SQL 查不到保单行时 MyBatis 返回 null）
  if (StringUtils.isNotBlank(lcGrpCont.getPRODBUSS()) && "01".equals(lcGrpCont.getPRODBUSS())) {
      tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");
  } else {
      tLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("1");
  }
  ```
  底层 SQL（`LCContPlanDetailInfoMapper.xml` `queryLcGrpContInfo`）：
  ```sql
  select * from LCGrpCont where grpcontno = #{grpcontno}   -- 查不到 → 无结果 → 返回 null
  ```
- **具体故障场景**：某保单 `LCGRPCONT` 主档缺失/尚未建立（如 GCMS 同步中断留下的孤儿方案）→ `lcGrpCont` 为 null → `lcGrpCont.getPRODBUSS()` **NPE**，整个险种层福利生成流程中断、保存失败。
- **性能问题**：`saveRiskBenefitInfo` 在**每个险种层节点**都执行一次该查询（N+1），保单下方案/险种多时反复查 `LCGRPCONT`。
- **责任人**：lixin（`d56acd6af2`）
- **建议**：查询后判空（null 时视为非企补并记日志）；`LCGrpCont` 在流程入口只查一次传入。

---

### 🟠 L-06 需求4.3：组合免赔额"先删后插"去重，误删人工调整、旧记录(COMBINAFLAG=0)失效（未修复）

- **类/文件**：cgis-legacy-app `java/com/cignacmb/gcis/app/service/LCContPlanDetailService.java`
  - 年限额：**第 467-472 行**；组合免赔额：**第 516-521 行**
- **问题代码原文（以组合免赔额 516-521 行为例）**：
  ```java
  //先删后插,避免重复保存时同节点叠加多条免赔额福利记录
  tLCContPlanDetailInfoMapper.deleteGNSR014RiskBenefit(
          riskLCClaimDutyClaimTree.getBENEFITAPPNO(),
          riskLCClaimDutyClaimTree.getDUTYSERIALNO(),
          "20");                       // 删除 BENIFITTYPE=20 且 COMBINAFLAG='1' 的记录
  tLCClaimBenefitMapper.insert(claimBenefit);
  ```
  对应删除 SQL（`LCContPlanDetailInfoMapper.xml` `deleteGNSR014RiskBenefit`）：
  ```sql
  delete from LCClaimBenefit
   where CLAIMBENEFITAPPNO = #{claimBenefitAppNo}
     and DUTYSERIALNO      = #{dutySerialNo}
     and BENIFITTYPE       = #{benifitType}
     and COMBINAFLAG       = '1'
  ```
- **问题**：
  1. **覆盖人工微调**：运营在界面上对该组合福利做过的修改（改福利值、费用类型等），流程重跑时 delete+insert 全部重建 → 人工调整丢失；
  2. **旧记录删不掉**：删除条件限 `COMBINAFLAG='1'`，而旧版本生成的组合记录 `COMBINAFLAG='0'` → 删除不命中 → 新旧两条并存，**"数据重复"bug 并未根治**；
  3. 删除与插入是两条独立语句，需确认所在流程有事务包裹（否则删除后插入失败会丢数据）。
- **具体故障场景**：一张保单在旧版本代码下已生成 COMBINAFLAG='0' 的组合免赔额，升级后再次触发生成 → 新代码只删 COMBINAFLAG='1' → 数据库里"0 旧记录 + 1 新记录"**并存两条**，理赔时重复抵扣。
- **责任人**：ludongxu（`a04e0d3d6b`/`2def3add90`/`4dbada0c3a`；`ff3a0ad04a` 仅改注释，未动逻辑）
- **建议**：收敛生成入口 + 按业务唯一键（BENEFITAPPNO+DUTYSERIALNO+BENIFITTYPE+COMBINAFLAG）做"存在则更新、不存在则插入"的 upsert，替代 delete+insert。

---

### 🟠 L-07 需求4.1：`RISKCODE.substring(3,4)` 无判空/长度保护（未修复）

- **类/文件**：
  - cgis-legacy-app `LCContPlanDetailService.java:550`
  - cgis-web-nbx `ClaimBenefitOfESBService.java:477`
- **问题代码原文（两库一致）**：
  ```java
  if ("R".equals(planDetail.getRISKCODE().substring(3,4))) {   // ❌ RISKCODE 为 null 或长度<4 会抛异常
      ...
  }
  ```
- **具体故障场景**：计划明细中某条 `RISKCODE` 缺失或异常（如 `null`、`"AB"`）→ `substring(3,4)` 抛 **NPE / StringIndexOutOfBoundsException** → `createFixedAmountConBenifit` 所在流程中断，投保录入/保全生成失败。
- **责任人**：ludongxu（legacy `138fb1932a`；nbx `87fb525bf`）
- **建议**：改为 `StringUtils.length(riskcode) >= 4 && "R".equals(riskcode.substring(3,4))`。

---

### 🟠 L-08 需求4.3：组合免赔额 `premFactorInfo` 未判空（未修复）

- **类/文件**：
  - cgis-legacy-app `LCContPlanDetailService.java:484-485`（`createGNSR014RiskBenefitOfDeductibles`）
  - cgis-web-nbx `ClaimBenefitOfESBService.java:424`
- **问题代码原文（legacy 484-485 行）**：
  ```java
  BenefitParamVo premFactorInfo = tLCContPlanDetailInfoMapper.queryMaxDeductiblesInfos(policyNo, planCode, riskCode);
  logger.info("查询最大免赔额对应保费因子数据,premvalue:" + premFactorInfo.getPREMVALUE() + ...);   // ❌ premFactorInfo 可能为 null
  claimBenefit.setBENIFITVALUE(premFactorInfo.getPREMVALUE());                                       // ❌ 同样 NPE
  ```
  外层虽然用 `checkDeductibleParamOfGNSR014=="1"` 做了闸口（`LCContPlanDetailService.java:358`），但该闸口与 `queryMaxDeductiblesInfos` **不是同一查询条件**，数据不一致时仍会 NPE。
- **具体故障场景**：有 GNSR014 免赔额因子但 `queryMaxDeductiblesInfos` 的关联条件（`LCCONTPLANDETAIL` 连接）匹配不上 → 返回 null → 日志拼接处先 NPE → 流程中断。
- **责任人**：lixin（legacy `d56acd6af2`；nbx `01e328b64`）
- **建议**：查询后判空，为空记日志并跳过生成。

---

### 🟠 L-09 需求4.3：组合免赔额组合责任**硬编码** `GNSR014001,GNSR014002`（未修复）

- **类/文件**：
  - cgis-legacy-app `LCContPlanDetailService.java:503`
  - cgis-web-nbx `ClaimBenefitOfESBService.java:421`
- **问题代码原文**：
  ```java
  // legacy 第503行 / nbx 第421行
  claimBenefit.setCOMBINADUTYCODES("GNSR014001,GNSR014002");   // ❌ 硬编码两个责任编码
  ```
- **问题**：组合免赔额的下级组合责任编码写死。而同一需求中年限额组合用的是**动态** `getDutyCodeString`（legacy），两处口径不一致；若产品责任编码因方案/配置变化，或未来其它产品复用该逻辑，硬编码即失效。
- **具体故障场景**：某方案下 GNSR014 的"一般医疗/特定疾病医疗"责任编码不是 001/002（如方案定制了责任编码）→ 生成的组合免赔额 COMBINADUTYCODES 指向错误的两个责任，理赔时组合抵扣关系错乱。
- **责任人**：lixin（legacy `d56acd6af2`；nbx `ce0da58e8`）
- **建议**：与年限额一致，按计划动态查询两个一级责任编码；或提为常量统一维护。

---

### 🟠 L-10 需求4.3：年限额组合 `getDutyCodeString` 未过滤一级责任（待确认）

- **类/文件**：cgis-legacy-app `LCContPlanDetailInfoMapper.xml`、cgis-web-nbx `LcContPlanDetailMapper.xml`（同名 SQL）
- **问题代码原文**：
  ```sql
  SELECT LISTAGG(l.DUTYCODE, ',') WITHIN GROUP (ORDER BY l.DUTYCODE) AS DUTYCODES
  FROM LCCONTPLANDETAIL l
  WHERE l.POLICYNO = #{policyNo}
    AND l.PLANCODE = #{planCode}
    AND l.RISKCODE = #{riskCode}
    -- ❌ 没有限制“一级责任”，若 LCCONTPLANDETAIL 含该产品子责任行，会一并拼进组合责任
  ```
- **需求条款**：4.3 第 3 条 下级组合责任 = 产品下所有**一级责任**（4 个）
- **具体故障场景**：若 GNSR014 在 `LCCONTPLANDETAIL` 中存在二级责任（如"一般医疗"下有具体医疗项目子责任），LISTAGG 会把子责任编码也拼入 `COMBINADUTYCODES` → 组合责任的组成与需求"全部一级责任"不符。
- **需确认**：GNSR014 的 `LCCONTPLANDETAIL` 是否含子责任行。
- **责任人**：lixin
- **建议**：SQL 增加一级责任（NODETYPE/层级）过滤，与需求"所有一级责任"对齐。

---

### 🟠 L-15【新】无操作分支：`setISSTANDARDPROTOCOL(getISSTANDARDPROTOCOL())`

- **类/文件**：cgis-legacy-app `LCContPlanDetailService.java:947-951`
- **问题代码原文**：
  ```java
  //RCP-15793：...默认否
  if(StringUtils.isNotBlank(curLCClaimDutyClaimTree.getISSTANDARDPROTOCOL())){
      curLCClaimDutyClaimTree.setISSTANDARDPROTOCOL(curLCClaimDutyClaimTree.getISSTANDARDPROTOCOL());  // ❌ 同一对象自赋值 = 空操作
  }else{
      curLCClaimDutyClaimTree.setISSTANDARDPROTOCOL("0");
  }
  ```
- **问题**：if 分支对**同一个对象** get 再 set，**没有任何效果**。若本意是"DB 已有值则保留、否则默认否"，应写成 `if (isBlank(...)) set("0")`。对照 `:1379-1383`（源 `curLCClaimDutyClaimTree` → 目标 `tLCClaimDutyClaimTree`）才是正确的"源→目标"复制。
- **具体故障场景**：无功能错误（空操作无害），但掩盖了真实意图——若本意是从源对象复制却写错对象，会静默丢值，且代码可读性差。
- **责任人**：ludongxu（`1b37845069`）
- **建议**：删除 if 分支，简化为 `if (StringUtils.isBlank(cur...getISP())) cur...setISP("0")`；若确需复制源值，改正对象引用。

---

### 🟠 N-01 需求4.3：`checkDeductibleParamOfGNSR014` 存在两个副本且取值不一致，其一为死代码（未修复）

- **类/文件**：cgis-web-nbx
  - `src/main/resources/mapper/com/cignacmb/cgis/nbx/application/mapper/ApplicationEntryMapper.xml`（`PREMFACTOR='DeductibleType'`）
  - `src/main/resources/mapper/com/cignacmb/cgis/nbx/mapper/LcContPlanDetailMapper.xml:486-501`（`PREMFACTOR='Deductibles'`，实际被调用）
- **问题代码对比**：
  ```xml
  <!-- ApplicationEntryMapper.xml（无调用点=死代码） -->
  AND l.PREMFACTOR = 'DeductibleType'     <!-- ❌ 与真实码值不符 -->

  <!-- LcContPlanDetailMapper.xml（实际被调用） -->
  AND l.PREMFACTOR = 'Deductibles'        <!-- ✅ 正确码值 -->
  ```
- **调用点核实**：Java 中只有 `LcContPlanDetailMapper.checkDeductibleParamOfGNSR014` 被调用（`ApplicationEntryService.java:1188`、`ClaimBenefitOfESBService.java:216`）；`ApplicationEntryMapper.checkDeductibleParamOfGNSR014` **无任何调用**。
- **问题**：同名 SQL 两个副本过滤值不同。真实码值为 `Deductibles`（`ClaimBenefitOfESBService.java:57` 常量 `PREM_FACTOR_DEDUCTIBLES`、`ApplicationEntryService.java:1323` 判断、legacy 同款 SQL 均为此值）。死代码若日后被误调用（用 `DeductibleType`），组合免赔额在 NB 场景将**静默不生成**。
- **具体故障场景**：某开发误以为两份同名 SQL 等价，在其它逻辑中调用 `ApplicationEntryMapper.checkDeductibleParamOfGNSR014` → 永远查不到（COUNT=0）→ 组合免赔额不生成，且无报错，属静默缺失。
- **责任人**：ludongxu（`bf5fed093` 加入死代码副本）、lixin（`01e328b64` 正常副本）
- **建议**：删除 `ApplicationEntryMapper` 侧死代码副本；两仓库同名 SQL 统一到一处。

---

### 🟠 N-02 需求4.3：nbx `saveOrUpdateClaimBenefit` 删除条件过宽，可能误删同类型责任福利（未修复）

- **类/文件**：cgis-web-nbx `ClaimBenefitOfESBService.java:140-157`
- **问题代码原文**：
  ```java
  private void saveOrUpdateClaimBenefit(LcClaimBenefit claimBenefit, List<LcClaimBenefit> claimBenefitList) {
      if (!ListUtils.emptyIfNull(claimBenefitList).isEmpty()) {
          List<LcClaimBenefit> needDeleteList = claimBenefitList.stream()
                  .filter(old -> StringUtils.equals(claimBenefit.getBENIFITTYPE(), old.getBENIFITTYPE())
                          && StringUtils.equals(claimBenefit.getCLAIMBENEFITAPPNO(), old.getCLAIMBENEFITAPPNO()))  // ❌ 只比 BENIFITTYPE + CLAIMBENEFITAPPNO
                  .collect(Collectors.toList());
          needDeleteList.forEach(lcClaimBenefitMapper::deleteByPrimaryKey);
          claimBenefitList.removeAll(needDeleteList);
      }
      claimBenefit.setBENEFITNO(pubFun.CreateMaxNoSleb(BENEFIT, 20));
      lcClaimBenefitMapper.insert(claimBenefit);
  }
  ```
- **问题**：删除条件**不含 DUTYSERIALNO / COMBINAFLAG**。组合免赔额 BENIFITTYPE="20"、组合年限额 BENIFITTYPE="50"，与责任层的免赔额/限额**同类型**。若 `claimBenefitList` 中同时含责任层免赔额（如 DUTYSERIALNO=GNSR014001 的 BENIFITTYPE=20）与险种层组合免赔额（同 BENIFITTYPE=20），插入组合免赔额时会把**责任层同类型福利一并删除**。
- **具体故障场景**：`completeApplicationData` 传入的 `claimBenefitList`（`ApplicationEntryService.java:1104` 由 `queryClaimbeneFit` 查全量）含责任层免赔额 + 险种层组合免赔额 → `createGNSR014RiskBenefitOfDeductibles` 调用本方法插入组合免赔额 → 责任层两条免赔额被误删 → **理赔时责任层免赔额缺失**。
- **责任人**：lixin（`01e328b64` 引入组合免赔额对该方法的调用；方法本体为迭代一 ludongxu `08bfad123e`）
- **建议**：删除条件收紧到含 `DUTYSERIALNO`（+COMBINAFLAG），或改为按主键 upsert。

---

### 🟠 N-03 需求4.2：nbx 未区分 NB/POS，保全场景若 AMNTUNIT 有值会用 GCMS 单位而非产品配置（未修复）

- **类/文件**：cgis-web-nbx `ClaimBenefitOfESBService.java:531-553`（`dealTimeUnitOfFixAmntBenifit`）
- **问题代码原文**：
  ```java
  private String dealTimeUnitOfFixAmntBenifit(String policyno, LcContPlanDetail planDetail) {
      String timeunit = "30";
      //❌ 方法不区分 NB/POS 场景，一律优先 AMNTUNIT（GCMS 单位）
      if (StringUtils.isNotBlank(planDetail.getAMNTUNIT())){
          if ("1".equals(planDetail.getAMNTUNIT())) timeunit = "20";
      } else {
          String posTimeunit = lcContPlanDetailMapper.queryAmntUnitOfDutyCode(...);  // 产品配置
          if ("1".equals(posTimeunit)) timeunit = "20";
      }
      return timeunit;
  }
  ```
- **需求条款**：4.2 保全新增方案场景——"根据产品配置表中的一级责任对应的保额单位进行映射"（**一律取产品配置，不看 GCMS 单位**）
- **问题**：nbx 不分 NB/POS：只要 AMNTUNIT 有值就用 GCMS 单位。**保全场景**若方案明细仍带 GCMS 保额单位，会优先取 GCMS 单位而非产品配置，与需求不符。legacy 的 POS 分支（`LCContPlanDetailService.java:596-601`）是**直接查产品配置**，两库口径不一致。
- **具体故障场景**：保全新增方案复制了 GCMS 方案（AMNTUNIT=1 元/天 仍存在），但产品配置实际为"元" → 按需求保全应生成"年"，nbx 却因 AMNTUNIT 有值生成"日"。
- **责任人**：lixin（nbx `2bc24c4ae`）
- **建议**：明确 NB/POS 两个场景的取数口径并统一（与 legacy 对齐：保全直取产品配置，不看 AMNTUNIT）。

---

### 🟡 L-11 需求4.3：组合免赔额"独立免赔计划"家庭范围未显式赋"个人"（未修复）

- **类/文件**：cgis-legacy-app `LCContPlanDetailService.java:496-500`；nbx 同方法（`createGNSR014RiskBenefitOfDeductibles`）
- **问题代码原文**：
  ```java
  //根据免赔额方式(1-独立免赔计划,2-共享免赔计划) 映射免赔额的家庭范围,默认为个人
  String deductiblemethod = tLCContPlanDetailInfoMapper.queryDeductiblemethodByPlanInfo(premFactorInfo);
  if (StringUtils.isNotBlank(deductiblemethod) && "2".equals(deductiblemethod)){
      claimBenefit.setFAMILYUNIT("20");     // 共享 → 家庭
  }
  // ❌ 独立("1")场景没有显式 setFAMILYUNIT("10")，依赖数据库默认值
  ```
- **需求条款**：4.3 家庭范围——独立免赔计划→个人，共享免赔计划→家庭
- **问题**：独立场景未显式赋"个人"(10)。若数据库该列默认值不是 10，生成的组合免赔额家庭范围会错。
- **责任人**：lixin
- **建议**：两分支都显式赋值（`if("2") set("20") else set("10")`）。

---

### 🟡 L-12 需求4.3：组合免赔额"时间范围"取值(`TYPE`)与需求表述需拉通（未修复）

- **类/文件**：cgis-legacy-app `LCContPlanDetailService.java:488`；nbx 同（`createGNSR014RiskBenefitOfDeductibles`）
- **问题代码原文**：
  ```java
  claimBenefit.setTIMEUNIT(StringUtils.defaultString(premFactorInfo.getTYPE(), "30"));  // 时间范围取 TYPE
  ```
- **需求条款**：4.3"时间范围：根据 GCMS 或投保录入或保全录入的'**免赔方式**'自动填充"
- **问题**：代码时间范围取 `LcPremFactorInfos.TYPE`（免赔额因子的时间范围码），而需求表述为"根据免赔方式(DEDUCTIBLEMETHOD)自动填充"。`TYPE` 与"免赔方式"是否为同一口径需与需求/数据字典确认，否则生成的时间范围可能不符。
- **责任人**：lixin
- **建议**：与需求方/数据字典确认 `TYPE` 与 `DEDUCTIBLEMETHOD` 的对应关系，确认后固化到代码注释。

---

### 🟡 L-13 规范：diff 噪音与无关行为变更（部分修复）

- **已修复**：`ff3a0ad04a`（ludongxu）恢复了 `LCContPlanDetailInfoMapper.java` 中被删的中文注释。
- **未修复**：
  - `LCClaimDutyClaimTree.java` 466 行变更中绝大多数为 MyBatis Generator **重新生成的注释格式差异**，属噪音 diff；
  - `LPContPlanDetailDB.java` 中 `Required/Mult` 的 jdbcType 被互换（`DECIMAL`↔`VARCHAR`）、`getFieldType` 中 `"DeductibleMethod "` 尾随空格被修正等**与需求无关的行为变更**仍混在"乱码调整"类提交里。
- **问题示例（LPContPlanDetailDB.insert，行为变更）**：
  ```java
  // 旧：#{Required,jdbcType=DECIMAL}, #{Mult,jdbcType=VARCHAR}
  // 新：#{Required,jdbcType=VARCHAR}, #{Mult,jdbcType=DECIMAL}    ← jdbcType 互换，非本需求内容
  ```
- **责任人**：ludongxu（`87efe7512f`/`641c9f8048`）、lixin（`d56acd6af2`/`e098b24ef0`）
- **建议**：确认 `Required/Mult` jdbcType 互换、"DeductibleMethod"空格修正是**有意为之**并在提交说明中注明；后续编码/生成器改动与业务改动拆分提交，降低评审噪音与回归风险。

---

### 🟡 N-04 规范：`setCombinaDutyCodes` 空包装方法（未修复）

- **类/文件**：cgis-web-nbx `ClaimBenefitOfESBService.java:86-88`
- **问题代码原文**：
  ```java
  private void setCombinaDutyCodes(LcClaimBenefit benefit, String codes) {
      benefit.setCOMBINADUTYCODES(codes);     // ❌ 只调一行 setter，无附加逻辑
  }
  ```
- **问题**：无意义的多余抽象，增加阅读成本，与同类 `setTimeUnit`/`setSpecialRule`（有默认值等逻辑）不同，这个纯粹是套壳。
- **责任人**：lixin（`ce0da58e8`）
- **建议**：删除该方法，直接调用 `setCOMBINADUTYCODES`。

---

### 🟡 B-01 nb：`updateByPrimaryKeySelective` 夹带与需求无关的 `DEDUCTIBLEMETHOD` 更新（未修复）

- **类/文件**：cgis-web-nb `src/main/resources/mapper/generate/LcContPlanDetailMapper.xml:474`
- **问题代码原文（本次需求提交新增，与"新增保额单位"无关）**：
  ```xml
  <if test="DEDUCTIBLEMETHOD != null">
      DEDUCTIBLEMETHOD = #{DEDUCTIBLEMETHOD,jdbcType=VARCHAR},      <!-- ❌ 与 AMNTUNIT 一并被新增进 updateSelective -->
  </if>
  <if test="AMNTUNIT != null">
      AMNTUNIT = #{AMNTUNIT,jdbcType=VARCHAR},
  </if>
  ```
- **问题**：本次需求（新增接收 GCMS 保额单位）在 `updateByPrimaryKeySelective` 中一并新增了 `DEDUCTIBLEMETHOD` 的更新，超出需求范围。若为修正既有遗漏需在提交说明注明，否则该行为变化不易被追踪，可能引入回归。
- **其余 nb 改动**（`QuotSaveService.java:4270` 映射 `amntUnit`、模型/resultMap/insert/update 增加 AMNTUNIT 列）实现正确，与需求一致。
- **责任人**：lixin（`67a9f1a0`/`cf8e4de9`）
- **建议**：如为有意修正，补提交说明；否则拆分，仅保留 AMNTUNIT 相关改动。

---

## 三、已修复项（告知团队）

1. **legacy 4.4 保全复制方案流程**（原 L-04）：`copyPlanBenefit` 险种层节点默认"否"、其余节点继承源值，方向正确。—— ludongxu `27e33cc139`。注意遗留 L-14/L-15 需跟进。
2. **nbx 责任层赔付比例配置丢失**：lixin 引入的 `checkGNSR014OfDutyCondition` 守卫原本作用于**所有**保费因子，导致 GNSR014 免赔额参数一致时，责任层赔付比例等其他因子映射被一并抑制（数据丢失）。ludongxu `e215f94a4` 将守卫收窄到仅 `Deductibles` 因子，修复正确，与 legacy 口径一致。
   > 提示：此 bug 属 nbx 侧 lixin 的回归，建议复盘守卫最初为何放在 `switchPremFactor` 之前。

---

## 四、跨仓库一致性问题（重点确认）

1. **4.2 保额单位→时间范围**：nbx 有回退、legacy NB 分支没有（L-01）；nbx 不分 NB/POS，保全口径与 legacy 不同（N-03）。
2. **4.3 去重策略**：legacy 用"appno+duty+type+combinaflag 删后插"（L-06），nbx 用"appno+type 删后插"（N-02），均不严谨且不一致。
3. **4.3 硬编码责任编码**：两库各硬编码 `GNSR014001,GNSR014002`（L-09）。
4. **4.4 默认值口径**：legacy 内 `saveRiskBenefitInfo` 条件逻辑与其它路径一刀切"0"互相矛盾（L-14）；nbx 未做 4.4 相关改动（需确认 nbx 侧【保单理赔福利录入】是否也需同步）。

---

## 五、责任分派建议

| 开发者 | 待处理问题 |
|--------|----------|
| **ludongxu** | L-06、L-07、L-14、L-15、N-01（死代码）、L-13（提交规范）；并复盘 nbx 保全场景覆盖（L-03） |
| **lixin** | L-01、L-02、L-05、L-08、L-09、L-10、L-11、L-12、N-02、N-03、N-04、B-01、L-13 |
| **Xi Cheng** | 见下方专项 |

**Xi Cheng（isnew 字段初始化）专项核查**：
- **类/文件**：cgis-legacy-app `java_schema/SqlInfo/model/LCClaimBenefitAppMapper.xml` `initIsNew`（提交 `424450dc1b`/`ab45ff3fdd`）
- **问题代码原文**：
  ```sql
  SELECT NVL( (SELECT CASE WHEN code.CODE = 'Y' THEN '1' ELSE '0' END
               FROM LDCODE code, lcgrpcont cont
               WHERE code.CODETYPE = 'NewOldBenefitCalcSwitch'
                 AND cont.GRPCONTNO = #{policyNo}
                 AND cont.PRODBUSS = '01' ), '0') FROM DUAL
  ```
- **问题**：子查询对 `LDCODE` 表按 `CODETYPE='NewOldBenefitCalcSwitch'` 过滤后**未限 rownum**。若该 codetype 存在多行（如 'Y'、'N' 并存作为字典枚举），子查询返回多行 → 外层报 **ORA-01427（单行子查询返回多行）** → 福利生成流程整体失败。此外 `LDCODE` 与 `lcgrpcont` 为笛卡尔连接，语义上建议拆分。
- **具体故障场景**：SIT 环境 LDCODE 字典里 `NewOldBenefitCalcSwitch` 配置了 Y/N 两行 → 投保录入插入 `LCClaimBenefitApp` 时 `initIsNew` 报 ORA-01427 → 福利生成中断。
- **责任人**：Xi Cheng（`424450dc1b`/`ab45ff3fdd`）
- **建议**：子查询加 `AND rownum = 1`（或 `MAX(CASE WHEN...)` 聚合），并确认该 codetype 的数据形态（是否允许多行）。

---

## 六、共性规范建议

1. **提交粒度**：业务改动、bug 修复、编码/生成器修正分开提交并注明影响范围（L-13、B-01、N-01 均相关）。
2. **去重/幂等**：删除条件必须含完整业务唯一键（BENEFITAPPNO+DUTYSERIALNO+BENIFITTYPE+COMBINAFLAG），入口唯一。
3. **判空**：查询结果（`queryMaxDeductiblesInfos`、`queryLcGrpContInfo`）用前判空；`substring` 前判长度。
4. **需求口径拉通**：4.3 比较字段全集、组合免赔额"时间范围"取值来源，与需求方/数据字典书面确认。
5. **两库对齐**：legacy 与 nbx 同需求实现保证口径一致（4.2、4.3、4.4）。

---

## 七、建议修改顺序

1. **先改**：L-01（NB 限额时间范围错配，直接影响承保福利生成）、L-02（组合免赔额生成条件不符需求）、L-03（保全场景/双写）、L-14（非企补默认值越界，涉及存量 GHB/中端）。
2. **次改**：L-05~L-10、N-01~N-03 健壮性与一致性。
3. **顺手**：L-15、L-11、L-12、N-04、B-01、L-13。

---

## 八、排除项（非本需求代码，已剔除）

nbx `ApplicationEntryMapper.xml`/`ApplicationEntryService.java` 区间内混有其它需求改动：
- `queryAnnualPersonalPremFlagByZT` —— RCP-13484-pos（`391078457`）
- `queryExpireRisk` businessunit + 渠道校验 —— TAPD-1018351（`b12746a5e`）、禁售开关日志（`2b38b80a6`）

> 提示：`bf5fed093`（本需求）与上述其它需求连续操作 `ApplicationEntryMapper.xml`，多需求同文件改动叠加，建议按需求隔离文件或细化提交粒度。
