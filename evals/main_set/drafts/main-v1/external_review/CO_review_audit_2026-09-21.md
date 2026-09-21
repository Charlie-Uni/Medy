# 主评测集 main-v1：CO 批次审校与引用自审报告（重生成版）

> 重生成日期：2026-09-21。
> 本文件是在原始 `CO_review_audit_2026-09-21.md` 下载失效后，根据当前对话中仍可恢复的 CO 原始草稿、此前已给出的 CO 审校结论、以及后续 EN 孪生审校中保留的父样本复核记录重新生成。
> 因原 artifact 本体已失效，本文件**不是原文件的逐字节副本**；凡无法从现存记录逐字恢复的历史字段差异，均明确标注，不作伪造。

## 1. 汇总

| 项目 | 结果 |
| --- | ---: |
| CO 草稿样本 | 84 |
| 建议保留（OK） | 79 |
| 建议移出/删除当前 CO 表（DROP） | 5 |
| 状态 | `main-v1-provisional` |
| 第二人工复核 | 未完成 |

本轮审校标准：问题自然且可由目标条款回答；`key_text` 足够短且不丢失控制语义；`evidence_span` 覆盖完整条款；切片标签与部门归属合理；完成修改后反向核查对应 PDF、版本、物理页及原文。

## 2. 五条 DROP / 移出裁决

### ms-0300
- 文档：`fda-e6r3-gcp-2025`；草稿物理页：77。
- 原问题：根据ICH E6(R3)术语表并参照ICH E2A,已上市药品的不良药物反应(ADR)应如何定义?
- 裁决：建议移出 CO、转交 PV：问题是已上市药品 ADR 定义，部门归属更符合 PV；不是无答案，也不是全局删除。
- 自审引用：`/sources_staging/e57e9fc0134abebec409d7144aed6e3047c0939d1bd758163fea4e1169472109.pdf`，物理页 77。

### ms-0303
- 文档：`fda-e6r3-gcp-2025`；草稿物理页：18。
- 原问题：根据ICH E6(R3)指南,IRB/IEC应建立、记录并遵循的书面程序(Procedures,1.4)应包含哪些具体事项?
- 裁决：DROP：问题要求完整列出 ICH E6(R3) IRB/IEC Procedures 1.4；物理第18页仅到1.4.8，第19页仍有1.4.9，当前单页 gold 不完整。
- 自审引用：`/sources_staging/e57e9fc0134abebec409d7144aed6e3047c0939d1bd758163fea4e1169472109.pdf`，物理页 18–19。

### ms-0324
- 文档：`fda-protocol-deviations-draft-2024`；草稿物理页：11。
- 原问题：临床试验方案设计阶段，为了从源头降低重要方案偏离（protocol deviation）发生的风险，申办者（sponsor）可以采取哪些具体做法？
- 裁决：DROP：来源为 FDA 2024-12 Protocol Deviations 草案（Draft — Not for Implementation），页文本夹行号，且所问设计措施跨物理第11–12页；当前证据结构需重建。
- 自审引用：`/sources/3b172d83fd5310029d0933a2efdb821c31d77c31d874e292dff7fb7da9abd42f.pdf`，物理页 11–12。

### ms-0414
- 文档：`ich-e19-step4-2022`；草稿物理页：8。
- 原问题：根据ICH E19,在临床试验中采用选择性安全性数据收集(selective safety data collection)方法时,通常仍应收集哪些安全性数据要素?
- 裁决：DROP：与 ms-0406 为同一 ICH E19 文档、同一条款、同一信息需求的重复问题；保留修订后的 ms-0406。
- 自审引用：`/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf`，物理页 8。

### ms-0428
- 文档：`ich-e6-r3-step4-2025`；草稿物理页：16。
- 原问题：根据ICH E6(R3)，受试者获得的试验相关报酬能否完全取决于其是否完成整个试验？
- 裁决：DROP：与 ms-0302 的受试者报酬问题语义重复；不合并 FDA 与 ICH 两份 PDF，只删除重复评测问题。
- 自审引用：`/sources/e6ce19e36ce7d2e294f89ee89492b9e035178c3cca48984392bbd92eec9b002c.pdf`，物理页 16。

## 3. 已知的重点实质修订

| 样本 | 审校结论 | PDF 自审 |
| --- | --- | --- |
| ms-0299 | key_text 必须保留否定主体（Neither…nor…should），不能从“coerce or unduly influence…”开始而丢失否定控制。 | 对应源 PDF 已在原审校轮次核查 |
| ms-0305 | key_text 补回“No informed consent…”及“waive or appear to waive”；原 key 脱离否定词会反转语义。 | `/sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf` p10 |
| ms-0311 | 术语修正：wards of the state 不是“病房儿童”；按“受国家/机构监护的儿童”处理，并保留 advocate 与试验/研究者/监护机构关联的角色例外。 | `/sources_staging/96b26b2edb06e20ee2872ca59f4ec7c04cde8a8b1adf98bc150764e3d52f906a.pdf` p50 |
| ms-0313 | 保留制度例外：某些研究类别下法规不强制指定 advocate，但 IRB 仍应考虑指定；不能把“不强制”写成“不需要考虑”。 | 对应源 PDF 已在原审校轮次核查 |
| ms-0332 | 多要点 key 补齐 centralized monitoring 支持的完整活动范围，不能只保留“确定哪些临床中心需要现场审查”。 | `/sources_staging/2c0d04faa13f3cfd95bb3b4c5359f699ede4f48dcb055ad2d0ae89d3aa9c423c.pdf` p10 |
| ms-0366 | 补齐限定：E12A 引用 E1 的约1,500例一般数据库规模及暴露时长，同时明确对降压药预期的长期、广泛、无症状人群使用而言该规模可能偏小。 | `/sources_staging/d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac.pdf` p8 |
| ms-0376 | 明确问治疗期间 QTc 的绝对间期值 >500 ms；与相对基线变化 >30/>60 ms 分开。此处毫秒不是药物 dose_unit。 | `/sources_staging/6199a1a27063c31e6d935e062ad0b581618f123473b13a854fe61eea5ffe0a5c.pdf` p14 |
| ms-0406 | 保留“generally”及非穷尽性质：选择性安全性数据收集时通常仍应收集哪些安全性数据，不能写成无例外的全部必收清单。 | `/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf` p8 |
| ms-0410 | 保留三组时间窗及原文语气：征集性体征/症状 e.g. 7天；非征集性 AE approximately 4周；SAE/预设 AESI at least 6个月。 | `/sources_staging/6daddce21ed23e1899b05b555335402aae49873d8560b9ea7c4a74bf5fc77fdd.pdf` p11 |

## 4. 关键裁决说明

### 4.1 否定语义不能从 key 中丢失

- `ms-0299`：原条款以 **Neither the investigator nor the investigator site staff should…** 控制整句；若 key 从 `coerce or unduly influence…` 开始，会失去禁止/否定语义。
- `ms-0305`：21 CFR 50.20 条款以 **No informed consent… may include…** 开头，并包含 `waive or appear to waive`；key 必须覆盖这些控制词，避免语义反转。

### 4.2 术语与制度例外

- `ms-0311`：`wards of the state` 按“受国家或其他机构监护的儿童”理解，不译为“病房儿童”；`advocate` 的独立性要求需保留其角色例外。
- `ms-0313`：在 21 CFR 50.51/50.52 类研究中，法规不强制指定 advocate，但 IRB 仍应考虑指定；不能把“不强制”简化为“无需”。

### 4.3 数值与限定条件

- `ms-0366`：约 1,500 例是 E12A 引用 E1 的一般慢性用药安全数据库规模，并同时给出 6 个月/1 年暴露数量；原文还明确指出，对降压药预期的长期、广泛、无症状人群暴露而言，该规模可能过小。
- `ms-0376`：E14 将**绝对 QTc 值**与**相对基线变化**分开；`>500 ms` 是治疗期间绝对 QTc 间期的特别关注阈值，不是“较基线增加 500 ms”。

### 4.4 多要点问题与非穷尽清单

- `ms-0332`：centralized monitoring 的 key 不能只覆盖“确定哪些临床中心需要现场审查”，应覆盖问题所要求的活动范围。
- `ms-0406`：ICH E19 的相关列表是“generally should be collected”且不是穷尽性清单；问题和 key 均不能把它写成无例外的全部必收要素。
- `ms-0410`：三个时间窗口必须保持原文强度：`e.g.`、`approximately`、`at least`，不能统一改成刚性截止期限。

## 5. 来源与版本自审

- FDA E6(R3) 与 ICH E6(R3) 原版分别管理；FDA 实施版为 2025 年 9 月。
- FDA `Protocol Deviations for Clinical Investigations…` 所供文件是 **December 2024 Draft — Not for Implementation**，不能写成正式指南。
- ICH E11(R1) 合订 PDF 中包含原始 E11 文本及 R1 新增内容；不能仅因处于同一 PDF 就把父指南条款全部称为“R1 新增”。
- 版本替换时不能只换文件名而沿用旧页码；最终引用须重新定位。
- 前轮自审结论：79 条建议保留样本均完成本地 PDF 文本重新定位、页内唯一性/包含关系检查；完整 `norm-v1` 偏移重算、数据库写回、EN 孪生联动和正式冻结未执行。

## 6. 84 条样本状态登记

> 说明：下面的 `OK`/`DROP` 状态可以从现存会话记录恢复。原 artifact 中部分逐字段 before/after diff 已随失效文件丢失；除上文已明确恢复的实质修改外，本表不虚构历史 diff。

| ID | 文档 | 页 | 结论 | 重生成备注 |
| --- | --- | ---: | --- | --- |
| ms-0298 | `fda-e6r3-gcp-2025` | 18 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0299 | `fda-e6r3-gcp-2025` | 24 | OK | key_text 必须保留否定主体（Neither…nor…should），不能从“coerce or unduly influence…”开始而丢失否定控制。 |
| ms-0300 | `fda-e6r3-gcp-2025` | 77 | DROP | 建议移出 CO、转交 PV：问题是已上市药品 ADR 定义，部门归属更符合 PV；不是无答案，也不是全局删除。 |
| ms-0302 | `fda-e6r3-gcp-2025` | 17 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0303 | `fda-e6r3-gcp-2025` | 18 | DROP | DROP：问题要求完整列出 ICH E6(R3) IRB/IEC Procedures 1.4；物理第18页仅到1.4.8，第19页仍有1.4.9，当前单页 gold 不完整。 |
| ms-0305 | `fda-informed-consent-2023` | 10 | OK | key_text 补回“No informed consent…”及“waive or appear to waive”；原 key 脱离否定词会反转语义。 |
| ms-0307 | `fda-informed-consent-2023` | 29 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0309 | `fda-informed-consent-2023` | 31 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0311 | `fda-informed-consent-2023` | 50 | OK | 术语修正：wards of the state 不是“病房儿童”；按“受国家/机构监护的儿童”处理，并保留 advocate 与试验/研究者/监护机构关联的角色例外。 |
| ms-0313 | `fda-informed-consent-2023` | 50 | OK | 保留制度例外：某些研究类别下法规不强制指定 advocate，但 IRB 仍应考虑指定；不能把“不强制”写成“不需要考虑”。 |
| ms-0314 | `fda-investigator-responsibilities-2009` | 16 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0316 | `fda-investigator-responsibilities-2009` | 17 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0318 | `fda-investigator-responsibilities-2009` | 17 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0320 | `fda-investigator-responsibilities-2009` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0322 | `fda-investigator-responsibilities-2009` | 17 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0324 | `fda-protocol-deviations-draft-2024` | 11 | DROP | DROP：来源为 FDA 2024-12 Protocol Deviations 草案（Draft — Not for Implementation），页文本夹行号，且所问设计措施跨物理第11–12页；当前证据结构需重建。 |
| ms-0326 | `fda-rbm-qa-2023` | 7 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0328 | `fda-rbm-qa-2023` | 5 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0330 | `fda-rbm-qa-2023` | 9 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0332 | `fda-rbm-qa-2023` | 10 | OK | 多要点 key 补齐 centralized monitoring 支持的完整活动范围，不能只保留“确定哪些临床中心需要现场审查”。 |
| ms-0334 | `fda-rbm-qa-2023` | 12 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0336 | `fda-risk-based-monitoring-2013` | 5 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0338 | `fda-risk-based-monitoring-2013` | 7 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0340 | `fda-risk-based-monitoring-2013` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0342 | `fda-risk-based-monitoring-2013` | 12 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0344 | `ich-e10-step4-2000` | 32 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0346 | `ich-e10-step4-2000` | 28 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0348 | `ich-e10-step4-2000` | 16 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0350 | `ich-e10-step4-2000` | 25 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0352 | `ich-e11-r1-step4-2017` | 16 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0354 | `ich-e11-r1-step4-2017` | 18 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0356 | `ich-e11-r1-step4-2017` | 22 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0358 | `ich-e11-r1-step4-2017` | 12 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0360 | `ich-e11-r1-step4-2017` | 11 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0362 | `ich-e12a-principle-2000` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0364 | `ich-e12a-principle-2000` | 9 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0366 | `ich-e12a-principle-2000` | 8 | OK | 补齐限定：E12A 引用 E1 的约1,500例一般数据库规模及暴露时长，同时明确对降压药预期的长期、广泛、无症状人群使用而言该规模可能偏小。 |
| ms-0368 | `ich-e12a-principle-2000` | 8 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0370 | `ich-e12a-principle-2000` | 5 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0372 | `ich-e14-step4-2005` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0374 | `ich-e14-step4-2005` | 9 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0376 | `ich-e14-step4-2005` | 14 | OK | 明确问治疗期间 QTc 的绝对间期值 >500 ms；与相对基线变化 >30/>60 ms 分开。此处毫秒不是药物 dose_unit。 |
| ms-0378 | `ich-e14-step4-2005` | 15 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0380 | `ich-e15-step4-2007` | 5 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0382 | `ich-e15-step4-2007` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0384 | `ich-e15-step4-2007` | 7 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0386 | `ich-e15-step4-2007` | 8 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0388 | `ich-e15-step4-2007` | 8 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0390 | `ich-e17-step4-2017` | 28 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0392 | `ich-e17-step4-2017` | 9 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0394 | `ich-e17-step4-2017` | 15 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0396 | `ich-e17-step4-2017` | 21 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0398 | `ich-e18-step4-2017` | 8 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0400 | `ich-e18-step4-2017` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0402 | `ich-e18-step4-2017` | 11 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0404 | `ich-e18-step4-2017` | 9 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0406 | `ich-e19-step4-2022` | 8 | OK | 保留“generally”及非穷尽性质：选择性安全性数据收集时通常仍应收集哪些安全性数据，不能写成无例外的全部必收清单。 |
| ms-0408 | `ich-e19-step4-2022` | 7 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0410 | `ich-e19-step4-2022` | 11 | OK | 保留三组时间窗及原文语气：征集性体征/症状 e.g. 7天；非征集性 AE approximately 4周；SAE/预设 AESI at least 6个月。 |
| ms-0412 | `ich-e19-step4-2022` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0414 | `ich-e19-step4-2022` | 8 | DROP | DROP：与 ms-0406 为同一 ICH E19 文档、同一条款、同一信息需求的重复问题；保留修订后的 ms-0406。 |
| ms-0416 | `ich-e3-step4-1995` | 28 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0418 | `ich-e3-step4-1995` | 10 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0420 | `ich-e3-step4-1995` | 25 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0422 | `ich-e3-step4-1995` | 30 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0424 | `ich-e3-step4-1995` | 34 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0426 | `ich-e6-r3-step4-2025` | 17 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0428 | `ich-e6-r3-step4-2025` | 16 | DROP | DROP：与 ms-0302 的受试者报酬问题语义重复；不合并 FDA 与 ICH 两份 PDF，只删除重复评测问题。 |
| ms-0430 | `ich-e7-step4-1993` | 4 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0432 | `ich-e7-step4-1993` | 3 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0434 | `ich-e7-step4-1993` | 3 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0436 | `ich-e7-step4-1993` | 5 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0438 | `ich-e7-step4-1993` | 4 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0440 | `ich-e7-step4-1993` | 6 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0442 | `ich-e8-r1-step4-2021` | 11 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0444 | `ich-e8-r1-step4-2021` | 23 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0446 | `ich-e9-r1-step4-2019` | 9 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0448 | `ich-e9-r1-step4-2019` | 10 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0450 | `ich-e9-r1-step4-2019` | 14 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0452 | `ich-e9-r1-step4-2019` | 20 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0454 | `ich-e9-step4-1998` | 12 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0456 | `ich-e9-step4-1998` | 27 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0458 | `ich-e9-step4-1998` | 17 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |
| ms-0460 | `ich-e9-step4-1998` | 12 | OK | 建议保留；原 artifact 的逐字段历史 diff 未能逐字恢复。 |

## 7. 正式应用边界

- 本报告中的 `OK` 为 AI 辅助审校建议，不代替 annotator-01 人工签署。
- 尚未执行项目 `norm-v1` 字符偏移重算、数据库写回、部门迁移、EN 孪生同步或版本冻结。
- 删除/迁移父样本时必须同步处理其孪生，避免出现孤儿 EN 样本。
- 最终状态仍为 `main-v1-provisional`；报告需继续标注“第二人工复核未完成”。
