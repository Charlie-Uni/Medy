# 2026-10-08 标注修订草案 v1

状态：**draft，尚未冻结、尚未重新复核**。本包落实已有 13 题裁决，并联动 5 道英文孪生题，共 18 条。完整修改在 [proposals.json](proposals.json)；每条包含原样本 canonical 哈希、新标注、改动理由、必需证据组与 pending 复核状态。

## 1. 这次改了什么

- 明确问题指定的文档、品牌、版本和条件，避免“问题问得宽，gold 却只认一份文档”。选择了原裁决允许的明确来源路径，保留了原问题要考查的内容。新版题的来源更明确，难度可能改变，旧新版本得分不能直接当系统收益对照。
- ms-0124/ms-0125：分级原则及 critical、major、minor 为 4 组。
- ms-0205/ms-0206：SmPC 各节与额外 RMM 说明为 4 组。
- ms-0243/ms-0244：必须报告的原则与事件示例为 2 组。
- 原页核对额外发现 ms-0241/ms-0242 的示例与汇总分析说明跨块，拆为 3 组；这项超出旧表“仅修来源”的细化建议，保留待复核。
- ms-0298 的旧 key_text 跨块，是当前 7 条 unmappable 之一。拆为 2 组，各自对应一种例外，保留包含两个条件的完整上下文。组间 AND 表示完整回答须覆盖两种例外，不表示两种情形必须同时发生。
- ms-0177/ms-0178 将“若选择请求”的条件写明，保留 30 天事实；不可把请求的可选性改成强制义务。
- pc-0017、pc-0028、pc-0029 明确品牌仿单，追加 `drug_name_zh` 标签。原冻结探针样本继续保持不变；探针新版本完成后才能按 PR-16 导入新版主集。
- [corpus_edits.json](corpus_edits.json) 提出一项标题修正：FDA 研究者安全报告文件封面为 December 2025，旧 corpus.title 误写 September 2021。版本字段本来即为 2025；无需改变原件、许可或来源哈希。

## 2. 检查结果与限制

- 9 份关联文档在当前 medops_v2 均为 active。只读核对了来源、版本、部门、抽取器及参数；1,445 个文档 chunk 的内容与原页一致、坐标与旧快照一致。[核查记录](document_verification.json)
- 本包只保留 12 个 gold 页的 94 个 chunk 坐标，供预览映射使用；另登记 FDA 封面页哈希。[快照](chunks.snapshot.json) · [原页绑定](page_inputs.json)
- 37 个 gold 单元均可映射；共同必需的组不能打平成“任一命中”。[映射预览](chunk_mapping.preview.json)
- 按现行 PR-19，拆分后单个 span 均不超过 1,500 字符，且这些题均在同一页；ms-0124/0125、ms-0205/0206 移除 long_context。因此投影到主集后该切片为 **19/20**，不能直接冻结新版。仍需补至少一道真正符合原规则的题，再检查文档配额与复核。
- 当前正式主集仍为 v3，仍按 553 有答案题、7 条未映射计算；本包的 37/37 只说明修订证据可映射，不是系统召回或答题成绩。
- 新标注没有 `review` 块，旧人/模型复核没有复制过去。元数据明确 human_annotation、independent_llm、second_human 均 pending；历史原文仍可从被冻结的基线读出。

## 3. 重现检查

```sh
venv/bin/python -m medops.evals.annotation_revision \
  evals/main_set/drafts/revision-2026-10-08 --with-pages
make eval-check EVAL_ARGS=--with-pages
```

本草案已登记到 `evals/dataset_catalog.json`，常规 `make check` 会验证其哈希、样本来源、孪生同步和映射结构；`--with-pages` 进一步读取本地页文本。机械通过不表示可冻结。CLI 运行器会拒绝本目录的 draft manifest。

## 4. 如何成为新版数据

1. 按下面逐题原文完成修订复核；新增判断不能沿用旧输入的签字或模型 verdict。
2. 补 long_context 配额，并重新检查全量分布、同文档上限、来源约束和全部 gold。
3. 三道 pc- 题先完成 probe 新版本，再由主集导入该版完整探针并记录新哈希。不得保持 `imported_samples=probe-v2` 却单独改三个 pc- 样本。
4. 独立第二人工暂缺时继续如实披露 provisional/pending，沿用原批准范围，不伪造身份。新模型复核与正式运行需另外记录实际调用、输入绑定及费用。
5. 组装与冻结后，针对新数据 hash 重新生成正式 chunk mapping，运行问答/安全并构建新 replay；旧主集和旧成绩保留。

候选版本名 probe-v3/main-v4 仅用于说明先后依赖，本包未分配或冻结这些正式目录。下表是具体修订，不是已经通过的人工确认表。

## 5. 修改索引

| 样本 | 类型 | 原 gold → 新 gold | query 改动 | 切片变化 |
| --- | --- | ---: | --- | --- |
| ms-0124 | 原清单 | 1 → 4 | 否 | 移除 long_context |
| ms-0125 | 英文联动 | 1 → 4 | 否 | 移除 long_context |
| ms-0177 | 原清单 | 1 → 1 | 是 | 无 |
| ms-0178 | 英文联动 | 1 → 1 | 是 | 无 |
| ms-0205 | 原清单 | 1 → 4 | 否 | 移除 long_context |
| ms-0206 | 英文联动 | 1 → 4 | 否 | 移除 long_context |
| ms-0241 | 原清单 | 1 → 3 | 是 | 无 |
| ms-0242 | 原清单 | 1 → 3 | 是 | 无 |
| ms-0243 | 原清单 | 1 → 2 | 是 | 无 |
| ms-0244 | 英文联动 | 1 → 2 | 是 | 无 |
| ms-0280 | 原清单 | 1 → 1 | 是 | 无 |
| ms-0298 | 原清单 | 1 → 2 | 是 | 无 |
| ms-0299 | 原清单 | 1 → 1 | 是 | 无 |
| ms-0336 | 原清单 | 1 → 1 | 是 | 无 |
| ms-0337 | 英文联动 | 1 → 1 | 是 | 无 |
| pc-0017 | 原清单 | 1 → 1 | 是 | 新增 drug_name_zh |
| pc-0028 | 原清单 | 1 → 1 | 是 | 新增 drug_name_zh |
| pc-0029 | 原清单 | 1 → 1 | 是 | 新增 drug_name_zh |

## 6. 逐题修订与核对证据

### ms-0124

**原 query**：根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、major、minor 三个等级?每个等级的具体定义是什么?

**新 query**：根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、major、minor 三个等级?每个等级的具体定义是什么?

**来源身份**：`ema-gvp-module-iv-rev1`；EMA/228028/2012 Rev 1 (2015-08-03)。

**理由**：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。

#### ms-0124-g1（PDF 物理页 8，norm-v1 偏移 [952, 1176)）

关键锚点：`should be graded in order to indicate their relative criticality`

> Audit findings should be reported in line with their relative risk level and should be graded in order to indicate their relative criticality to risks impacting the pharmacovigilance system, processes and parts of processes.

映射：`c0cb043c-cd67-4888-9e19-d1c822acd461`。

#### ms-0124-g2（PDF 物理页 8，norm-v1 偏移 [1177, 1754)）

关键锚点：`critical is a fundamental weakness in one or more pharmacovigilance processes or practices`

> The grading system should be defined in the description of the quality system for pharmacovigilance, and should take into consideration the thresholds noted below which would be used in further reporting under the legislation as set out in IV.C.2.: • critical is a fundamental weakness in one or more pharmacovigilance processes or practices that adversely affects the whole pharmacovigilance system and/or the rights, safety or well-being of patients, or that poses a potential risk to public health and/or represents a serious violation of applicable regulatory requirements.

映射：`fc140511-65be-4a82-87ad-9dc9dd4e8543`。

#### ms-0124-g3（PDF 物理页 8，norm-v1 偏移 [1755, 2226)）

关键锚点：`major is a significant weakness in one or more pharmacovigilance processes or practices`

> • major is a significant weakness in one or more pharmacovigilance processes or practices, or a fundamental weakness in part of one or more pharmacovigilance processes or practices that is detrimental to the whole process and/or could potentially adversely affect the rights, safety or well-being of patients and/or could potentially pose a risk to public health and/or represents a violation of applicable regulatory requirements which is however not considered serious.

映射：`05a7926d-889c-4182-a023-4b6f5cb97ee4`。

#### ms-0124-g4（PDF 物理页 8，norm-v1 偏移 [2227, 2456)）

关键锚点：`minor is a weakness in the part of one or more pharmacovigilance processes or practices`

> • minor is a weakness in the part of one or more pharmacovigilance processes or practices that is not expected to adversely affect the whole pharmacovigilance system or process and/or the rights, safety or well-being of patients.

映射：`7313c35d-8d97-46d2-a2cf-f4724e14ecb4`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0125

**原 query**：According to GVP Module IV, how should pharmacovigilance audit findings be graded as critical, major, or minor, and what is the specific definition of each grade?

**新 query**：According to GVP Module IV, how should pharmacovigilance audit findings be graded as critical, major, or minor, and what is the specific definition of each grade?

**来源身份**：`ema-gvp-module-iv-rev1`；EMA/228028/2012 Rev 1 (2015-08-03)。

**理由**：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 与父题 ms-0124 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

英文孪生父题：`ms-0124`。

#### ms-0125-g1（PDF 物理页 8，norm-v1 偏移 [952, 1176)）

关键锚点：`should be graded in order to indicate their relative criticality`

> Audit findings should be reported in line with their relative risk level and should be graded in order to indicate their relative criticality to risks impacting the pharmacovigilance system, processes and parts of processes.

映射：`c0cb043c-cd67-4888-9e19-d1c822acd461`。

#### ms-0125-g2（PDF 物理页 8，norm-v1 偏移 [1177, 1754)）

关键锚点：`critical is a fundamental weakness in one or more pharmacovigilance processes or practices`

> The grading system should be defined in the description of the quality system for pharmacovigilance, and should take into consideration the thresholds noted below which would be used in further reporting under the legislation as set out in IV.C.2.: • critical is a fundamental weakness in one or more pharmacovigilance processes or practices that adversely affects the whole pharmacovigilance system and/or the rights, safety or well-being of patients, or that poses a potential risk to public health and/or represents a serious violation of applicable regulatory requirements.

映射：`fc140511-65be-4a82-87ad-9dc9dd4e8543`。

#### ms-0125-g3（PDF 物理页 8，norm-v1 偏移 [1755, 2226)）

关键锚点：`major is a significant weakness in one or more pharmacovigilance processes or practices`

> • major is a significant weakness in one or more pharmacovigilance processes or practices, or a fundamental weakness in part of one or more pharmacovigilance processes or practices that is detrimental to the whole process and/or could potentially adversely affect the rights, safety or well-being of patients and/or could potentially pose a risk to public health and/or represents a violation of applicable regulatory requirements which is however not considered serious.

映射：`05a7926d-889c-4182-a023-4b6f5cb97ee4`。

#### ms-0125-g4（PDF 物理页 8，norm-v1 偏移 [2227, 2456)）

关键锚点：`minor is a weakness in the part of one or more pharmacovigilance processes or practices`

> • minor is a weakness in the part of one or more pharmacovigilance processes or practices that is not expected to adversely affect the whole pharmacovigilance system or process and/or the rights, safety or well-being of patients.

映射：`7313c35d-8d97-46d2-a2cf-f4724e14ecb4`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0177

**原 query**：按 REG Art 10a(2) 和 DIR Art 22a(2)，MAH 希望针对被施加的义务陈述书面意见时，应在收到书面通知后多久内提出这一请求？

**新 query**：根据 GVP Module VIII Rev 3 中对 REG Art 10a(2) 和 DIR Art 22a(2) 的说明，MAH 若选择请求陈述书面意见，应在收到施加义务的书面通知后多久内提出请求？

**来源身份**：`ema-gvp-module-viii-rev3`；EMA/813938/2011 Rev 3 (2017-10-09)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0177-g1（PDF 物理页 19，norm-v1 偏移 [187, 427)）

关键锚点：`Within 30 days of receipt of the written notification of an obligation imposed`

> Within 30 days of receipt of the written notification of an obligation imposed, the marketing authorisation holder may request to present written observations in response to the imposition of the obligation [REG Art 10a(2), DIR Art 22a(2)].

映射：`7cdac483-63f7-460f-a19b-d42a18eecf6a`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0178

**原 query**：Under REG Art 10a(2) and DIR Art 22a(2), within how many days of receiving written notification of an imposed obligation may the marketing authorisation holder request to present written observations?

**新 query**：Under GVP Module VIII Rev 3, which cites REG Art 10a(2) and DIR Art 22a(2), if the marketing authorisation holder chooses to request to present written observations, within how many days of receiving written notification of the imposed obligation should it make that request?

**来源身份**：`ema-gvp-module-viii-rev3`；EMA/813938/2011 Rev 3 (2017-10-09)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 与父题 ms-0177 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

英文孪生父题：`ms-0177`。

#### ms-0178-g1（PDF 物理页 19，norm-v1 偏移 [187, 427)）

关键锚点：`Within 30 days of receipt of the written notification of an obligation imposed`

> Within 30 days of receipt of the written notification of an obligation imposed, the marketing authorisation holder may request to present written observations in response to the imposition of the obligation [REG Art 10a(2), DIR Art 22a(2)].

映射：`7cdac483-63f7-460f-a19b-d42a18eecf6a`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0205

**原 query**：根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果该药品配有额外RMM材料，SmPC 4.4节又应额外说明什么？

**新 query**：根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果该药品配有额外RMM材料，SmPC 4.4节又应额外说明什么？

**来源身份**：`ema-gvp-module-xvi-rev3`；EMA/204715/2012 Rev 3 (2024-07-26)。

**理由**：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。

#### ms-0205-g1（PDF 物理页 36，norm-v1 偏移 [362, 658)）

关键锚点：`Information on adverse reactions, including information characterising the reaction`

> the summary of product characteristics (SmPC) (see GVP Annex I) presents information relevant to RMM in: • SmPC section 4.8 ‘Undesirable Effects’: Information on adverse reactions, including information characterising the reaction which may be useful to prevent, monitor or manage its occurrence;

映射：`05f240dd-a36c-414d-a2bc-61130c47f651`。

#### ms-0205-g2（PDF 物理页 36，norm-v1 偏移 [659, 1253)）

关键锚点：`Warnings and actions to be taken to avoid specific possible adverse reactions`

> • SmPC section 4.4 ‘Special Warnings and Precautions for Use’: Warnings and actions to be taken to avoid specific possible adverse reactions or to be taken if a specific reaction occurs or, if deemed necessary, actions to be taken as a precaution for potential risks; • SmPC section 4.6 ‘Fertility, Pregnancy and Lactation’: Information on risks of the medicinal product impacting on fertility, pregnancy and lactation, including risks for the embryo/foetus/child due to adverse effects at conception, in utero or through breastfeeding, and actions to be taken to avoid or minimise these risks;

映射：`b7f9d06b-d380-4bcf-966f-f05b371b7cf9`。

#### ms-0205-g3（PDF 物理页 36，norm-v1 偏移 [1254, 1669)）

关键锚点：`Safe use advice regarding indications, dosing and administration, contraindications, interactions`

> • SmPC sections 4.1 ‘Therapeutic Indications’, 4.2 ‘Posology and Method of Administration’, 4.3 ‘Contraindications’, 4.5 ‘Interaction with Other Medicinal Products and Other Forms of Interaction’, 4.7 ‘Effects on Ability to Drive and Use Machines’ and 4.9’ Overdose’: Safe use advice regarding indications, dosing and administration, contraindications, interactions, ability to drive and use machines, and overdose.

映射：`62b7f077-0073-44cf-aab0-0740a2d7898f`。

#### ms-0205-g4（PDF 物理页 36，norm-v1 偏移 [1670, 2194)）

关键锚点：`should describe the intended actions for risk minimisation and should include a statement`

> For medicinal products with additional RMM materials, according to the Guideline on Summary of Product Characteristics26 and supplementary Guidance on Frequently Asked Questions on SmPC Section 4.427, the SmPC section 4.4. should describe the intended actions for risk minimisation and should include a statement on the educational/safety advice materials addressed to healthcare professionals or patients which clearly and succinctly explains the purpose (e.g. “to be handed out to the patient”) and scope of the materials.

映射：`737c819a-dd24-4ac1-9862-88fdd83e7113`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0206

**原 query**：According to GVP Module XVI, what information relevant to risk minimisation measures (RMM) should the relevant SmPC sections contain, and what additional information should Section 4.4 include when additional RMM materials are provided?

**新 query**：According to GVP Module XVI, what information relevant to risk minimisation measures (RMM) should the relevant SmPC sections contain, and what additional information should Section 4.4 include when additional RMM materials are provided?

**来源身份**：`ema-gvp-module-xvi-rev3`；EMA/204715/2012 Rev 3 (2024-07-26)。

**理由**：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 与父题 ms-0205 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

英文孪生父题：`ms-0205`。

#### ms-0206-g1（PDF 物理页 36，norm-v1 偏移 [362, 658)）

关键锚点：`Information on adverse reactions, including information characterising the reaction`

> the summary of product characteristics (SmPC) (see GVP Annex I) presents information relevant to RMM in: • SmPC section 4.8 ‘Undesirable Effects’: Information on adverse reactions, including information characterising the reaction which may be useful to prevent, monitor or manage its occurrence;

映射：`05f240dd-a36c-414d-a2bc-61130c47f651`。

#### ms-0206-g2（PDF 物理页 36，norm-v1 偏移 [659, 1253)）

关键锚点：`Warnings and actions to be taken to avoid specific possible adverse reactions`

> • SmPC section 4.4 ‘Special Warnings and Precautions for Use’: Warnings and actions to be taken to avoid specific possible adverse reactions or to be taken if a specific reaction occurs or, if deemed necessary, actions to be taken as a precaution for potential risks; • SmPC section 4.6 ‘Fertility, Pregnancy and Lactation’: Information on risks of the medicinal product impacting on fertility, pregnancy and lactation, including risks for the embryo/foetus/child due to adverse effects at conception, in utero or through breastfeeding, and actions to be taken to avoid or minimise these risks;

映射：`b7f9d06b-d380-4bcf-966f-f05b371b7cf9`。

#### ms-0206-g3（PDF 物理页 36，norm-v1 偏移 [1254, 1669)）

关键锚点：`Safe use advice regarding indications, dosing and administration, contraindications, interactions`

> • SmPC sections 4.1 ‘Therapeutic Indications’, 4.2 ‘Posology and Method of Administration’, 4.3 ‘Contraindications’, 4.5 ‘Interaction with Other Medicinal Products and Other Forms of Interaction’, 4.7 ‘Effects on Ability to Drive and Use Machines’ and 4.9’ Overdose’: Safe use advice regarding indications, dosing and administration, contraindications, interactions, ability to drive and use machines, and overdose.

映射：`62b7f077-0073-44cf-aab0-0740a2d7898f`。

#### ms-0206-g4（PDF 物理页 36，norm-v1 偏移 [1670, 2194)）

关键锚点：`should describe the intended actions for risk minimisation and should include a statement`

> For medicinal products with additional RMM materials, according to the Guideline on Summary of Product Characteristics26 and supplementary Guidance on Frequently Asked Questions on SmPC Section 4.427, the SmPC section 4.4. should describe the intended actions for risk minimisation and should include a statement on the educational/safety advice materials addressed to healthcare professionals or patients which clearly and succinctly explains the purpose (e.g. “to be handed out to the patient”) and scope of the materials.

映射：`737c819a-dd24-4ac1-9862-88fdd83e7113`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0241

**原 query**：依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reasonable possibility)因果关系时可参考哪些示例情形?

**新 query**：根据 FDA 2025 年 12 月《Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices》指南，§ 312.32(c)(1)(i) 的哪些示例说明药物与不良事件间存在因果关系的“合理可能性”（reasonable possibility）？

**来源身份**：`fda-investigator-safety-reporting-2025`；Final guidance, December 2025 (FDA media 152530)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 原页另发现示例及汇总分析说明跨三个块，不能只命中导语；此扩展为实现方新增修订建议，尚待复核。

#### ms-0241-g1（PDF 物理页 7，norm-v1 偏移 [753, 1185)）

关键锚点：`A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure`

> The following examples are also provided in the IND safety reporting regulation (§ 312.32(c)(1)(i)) and illustrate the meaning of reasonable possibility with respect to a determination that there may be a causal relationship between the drug and the adverse event: • A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure (e.g., angioedema, hepatic injury, Stevens-Johnson Syndrome).

映射：`03b274ab-a8e2-4032-bbc7-10379ae547b9`。

#### ms-0241-g2（PDF 物理页 7，norm-v1 偏移 [1186, 1731)）

关键锚点：`An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently`

> • One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug (e.g., tendon rupture). • An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group. Examples of such events are known consequences of the underlying disease or condition or events that commonly occur in the study population independent of drug therapy.

映射：`dc317e2b-b2e7-49ab-b9e7-298ff69fb957`。

#### ms-0241-g3（PDF 物理页 7，norm-v1 偏移 [1732, 1900)）

关键锚点：`such events could also be associated with treatment or therapy that is standard of care`

> For aggregate analysis under § 312.32(c)(1)(i)(C), such events could also be associated with treatment or therapy that is standard of care for the disease or condition.

映射：`cd331ebb-3faf-4c10-b8a6-47ddc7194b39`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0242

**原 query**：According to the examples provided under § 312.32(c)(1)(i) for IND safety reporting, what examples illustrate a 'reasonable possibility' of a causal relationship between a drug and an adverse event?

**新 query**：According to FDA’s December 2025 guidance “Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices”, what examples under § 312.32(c)(1)(i) illustrate a reasonable possibility of a causal relationship between a drug and an adverse event?

**来源身份**：`fda-investigator-safety-reporting-2025`；Final guidance, December 2025 (FDA media 152530)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 原页另发现示例及汇总分析说明跨三个块，不能只命中导语；此扩展为实现方新增修订建议，尚待复核。 与父题 ms-0241 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

英文孪生父题：`ms-0241`。

#### ms-0242-g1（PDF 物理页 7，norm-v1 偏移 [753, 1185)）

关键锚点：`A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure`

> The following examples are also provided in the IND safety reporting regulation (§ 312.32(c)(1)(i)) and illustrate the meaning of reasonable possibility with respect to a determination that there may be a causal relationship between the drug and the adverse event: • A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure (e.g., angioedema, hepatic injury, Stevens-Johnson Syndrome).

映射：`03b274ab-a8e2-4032-bbc7-10379ae547b9`。

#### ms-0242-g2（PDF 物理页 7，norm-v1 偏移 [1186, 1731)）

关键锚点：`An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently`

> • One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug (e.g., tendon rupture). • An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group. Examples of such events are known consequences of the underlying disease or condition or events that commonly occur in the study population independent of drug therapy.

映射：`dc317e2b-b2e7-49ab-b9e7-298ff69fb957`。

#### ms-0242-g3（PDF 物理页 7，norm-v1 偏移 [1732, 1900)）

关键锚点：`such events could also be associated with treatment or therapy that is standard of care`

> For aggregate analysis under § 312.32(c)(1)(i)(C), such events could also be associated with treatment or therapy that is standard of care for the disease or condition.

映射：`cd331ebb-3faf-4c10-b8a6-47ddc7194b39`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0243

**原 query**：在IND研究中,除IND安全报告和BA/BE研究中的SAE外,哪些其他类型的事件即使不符合IND安全报告标准,仍必须作为涉及受试者风险的意外问题(unanticipated problem)报告给IRB,请举例说明?

**新 query**：根据 FDA 2025 年 12 月《Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices》指南，哪些事件即使不符合 IND 安全报告或 BA/BE 研究上市前 SAE 报告标准，仍须作为涉及受试者或他人风险的意外问题报告给 IRB？请举例说明。

**来源身份**：`fda-investigator-safety-reporting-2025`；Final guidance, December 2025 (FDA media 152530)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。

#### ms-0243-g1（PDF 物理页 12，norm-v1 偏移 [816, 1061)）

关键锚点：`still must be reported to the IRB because they represent unanticipated problems`

> Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB because they represent unanticipated problems involving risk to human participants or others.

映射：`56c2d993-45d3-4934-a083-ecfdfb2861e3`。

#### ms-0243-g2（PDF 物理页 12，norm-v1 偏移 [1062, 1588)）

关键锚点：`Other examples may include reports of medication errors`

> − Such events may occur at the participant, site, and/or study level and may include serious and unexpected adverse events that occur prior to test article administration, during a washout period, or that are attributable to a screening procedure. − Other examples may include reports of medication errors (such as receipt of wrong dose or contaminated study medication), breach of privacy/confidentiality (such as disclosure of personally identifiable information), untimely destruction of study records, and other scenarios.

映射：`f22428d5-feb0-473b-9c17-41c005048f26`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0244

**原 query**：In IND studies, apart from IND safety reports and premarket SAEs from BA/BE studies, what other events must be reported to the IRB as unanticipated problems involving risk to participants even when they do not meet IND safety-reporting criteria? Give examples.

**新 query**：Under FDA’s December 2025 investigator safety-reporting guidance, which events still require IRB reporting as unanticipated problems even if they do not qualify for an IND safety report or a BA/BE premarket SAE? Give examples.

**来源身份**：`fda-investigator-safety-reporting-2025`；Final guidance, December 2025 (FDA media 152530)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 与父题 ms-0243 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

英文孪生父题：`ms-0243`。

#### ms-0244-g1（PDF 物理页 12，norm-v1 偏移 [816, 1061)）

关键锚点：`still must be reported to the IRB because they represent unanticipated problems`

> Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB because they represent unanticipated problems involving risk to human participants or others.

映射：`56c2d993-45d3-4934-a083-ecfdfb2861e3`。

#### ms-0244-g2（PDF 物理页 12，norm-v1 偏移 [1062, 1588)）

关键锚点：`Other examples may include reports of medication errors`

> − Such events may occur at the participant, site, and/or study level and may include serious and unexpected adverse events that occur prior to test article administration, during a washout period, or that are attributable to a screening procedure. − Other examples may include reports of medication errors (such as receipt of wrong dose or contaminated study medication), breach of privacy/confidentiality (such as disclosure of personally identifiable information), untimely destruction of study records, and other scenarios.

映射：`f22428d5-feb0-473b-9c17-41c005048f26`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0280

**原 query**：使用 MedDRA 时,能否对术语的层级结构进行临时改动,比如变更某个 PT 的主 SOC 分配?

**新 query**：根据《MedDRA 数据检索和展示：考虑要点》发布版本 3.26（2026 年 3 月），用户能否临时改动 MedDRA 的术语层级结构，例如变更某个 PT 的主 SOC 分配？

**来源身份**：`meddra-data-retrieval-ptc-3-26-zh-hans`；发布版本 3.26（2026-03）。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0280-g1（PDF 物理页 8，norm-v1 偏移 [535, 657)）

关键锚点：`用户不得对 MedDRA 进行临时的结构改动,包括变更主 SOC 分配`

> MedDRA 是一个标准术语集,有预先界定的术语层级结构,不应更改。用户不得对 MedDRA 进行临时的结构改动,包括变更主 SOC 分配;这样做将有损该标准的完整性。如果发现术语的 MedDRA 层级结构不正确,应向 MSSO 提交变更申请。

映射：`b0373069-8929-4b2e-aab7-48212775ac10`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0298

**原 query**：根据ICH E6(R3),在什么情况下可以不经IRB/IEC事先书面批准就对已批准的试验方案进行偏离或变更?

**新 query**：根据 FDA 2025 年 9 月《E6(R3) Good Clinical Practice》指南，在哪些情况下，可以不经 IRB/IEC 事先记录在案的批准或赞同意见就对已批准的试验方案进行偏离或变更？

**来源身份**：`fda-e6r3-gcp-2025`；Final guidance, September 2025。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 原 key_text 跨 chunk，属于旧 7 条 unmappable 之一；拆成“紧急危险”和“法规允许的行政/后勤变更”两组，保留完整共同上下文，两个条件都须覆盖。

#### ms-0298-g1（PDF 物理页 18，norm-v1 偏移 [1177, 1554)）

关键锚点：`when necessary to eliminate immediate hazards to the participants`

> no deviations from or changes to the protocol should be initiated without prior documented IRB/IEC approval/favorable opinion of an appropriate protocol amendment except when necessary to eliminate immediate hazards to the participants or, in accordance with applicable regulatory requirements, when the change(s) involves only logistical or administrative aspects of the trial

映射：`9a07ba2f-4043-4450-8b53-49b3fa9507db`。

#### ms-0298-g2（PDF 物理页 18，norm-v1 偏移 [1177, 1554)）

关键锚点：`in accordance with applicable regulatory requirements, when the change(s) involves only logistical or administrative aspects of the trial`

> no deviations from or changes to the protocol should be initiated without prior documented IRB/IEC approval/favorable opinion of an appropriate protocol amendment except when necessary to eliminate immediate hazards to the participants or, in accordance with applicable regulatory requirements, when the change(s) involves only logistical or administrative aspects of the trial

映射：`00062a43-08f0-4114-b843-b9ef14106733`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0299

**原 query**：根据ICH E6(R3),研究者或研究机构工作人员是否可以对受试者施压以促使其继续参与临床试验?

**新 query**：根据 FDA 2025 年 9 月《E6(R3) Good Clinical Practice》指南，研究者或研究机构工作人员是否可以胁迫或不当影响受试者，使其继续参与临床试验？

**来源身份**：`fda-e6r3-gcp-2025`；Final guidance, September 2025。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0299-g1（PDF 物理页 24，norm-v1 偏移 [209, 377)）

关键锚点：`Neither the investigator nor the investigator site staff should coerce or unduly influence a participant to participate or to continue their participation in the trial`

> Neither the investigator nor the investigator site staff should coerce or unduly influence a participant to participate or to continue their participation in the trial.

映射：`c38214e4-2dd1-49f1-b311-b50697a427c7`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0336

**原 query**：根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？

**新 query**：根据 FDA 2013 年 8 月《Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring》指南引述的 21 CFR 312.50，申办者在临床试验监查方面须确保哪两件事？

**来源身份**：`fda-risk-based-monitoring-2013`；Final guidance, August 2013 (PRA update 2022-11-21)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0336-g1（PDF 物理页 5，norm-v1 偏移 [3227, 3467)）

关键锚点：`ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”`

> 21 CFR 312.50 requires a sponsor to, among other things, ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”

映射：`233db844-7a4a-426f-a28d-dcc0b8b6ee41`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### ms-0337

**原 query**：According to the passage quoting 21 CFR 312.50 in FDA's August 2013 risk-based monitoring guidance, what specific monitoring responsibilities does a sponsor have for a clinical investigation?

**新 query**：According to the passage quoting 21 CFR 312.50 in FDA’s August 2013 guidance “Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring”, which two things must a sponsor ensure regarding trial monitoring and conduct?

**来源身份**：`fda-risk-based-monitoring-2013`；Final guidance, August 2013 (PRA update 2022-11-21)。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 与父题 ms-0336 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

英文孪生父题：`ms-0336`。

#### ms-0337-g1（PDF 物理页 5，norm-v1 偏移 [3227, 3467)）

关键锚点：`ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”`

> 21 CFR 312.50 requires a sponsor to, among other things, ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”

映射：`233db844-7a4a-426f-a28d-dcc0b8b6ee41`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### pc-0017

**原 query**：糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎

**新 query**：根據穩壓膜衣錠50毫克仿單，糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎？

**来源身份**：`tfda-label-zosaa-50mg`；B版 104.10.27（2015-10-27）。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 探针导入题须先完成 probe 新版本复核/冻结，再供主集导入；不绕过 PR-16。

#### pc-0017-g1（PDF 物理页 1，norm-v1 偏移 [2612, 2859)）

关键锚点：`ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者`

> 雙重阻斷腎素-血管昇壓素-醛固酮系統(renin-angiotensin-aldosterone system, RAAS):有證據顯示,合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品會增加低血壓、高鉀血症及腎功能下降(包括急性腎衰竭)之風險,故不建議合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品來雙重阻斷 RAAS,若確有必要使用雙重阻斷治療,應密切監測患者之腎+A12 功能、電解質及血壓。ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者。

映射：`189c6570-b688-4b28-83ec-a94026d9f772`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### pc-0028

**原 query**：esomeprazole 可以和 nelfinavir 一起服用嗎

**新 query**：根據胃所樂腸溶膜衣錠40毫克（esomeprazole）仿單，可以與 nelfinavir 一起服用嗎？

**来源身份**：`tfda-label-esomen-40mg`；pdf-meta 2013-11-08（未见版本行）。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 探针导入题须先完成 probe 新版本复核/冻结，再供主集导入；不绕过 PR-16。

#### pc-0028-g1（PDF 物理页 2，norm-v1 偏移 [811, 924)）

关键锚点：`禁止同時併用 esomeprazole 和 nelfinavir`

> 由於omeprazole 與 esomeprazole 的藥效學效應與藥動學性質類似,故不建議同時投予 esomeprazole 和 atazanavir ,禁止同時併用 esomeprazole 和 nelfinavir 。

映射：`61c0abb1-c83b-4b30-9ebf-e93935edf2f3`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。

### pc-0029

**原 query**：嚴重肝功能不良的病人 esomeprazole 最高劑量是多少

**新 query**：根據胃所樂腸溶膜衣錠40毫克仿單，嚴重肝功能不良病人的 esomeprazole 最高劑量是多少？

**来源身份**：`tfda-label-esomen-40mg`；pdf-meta 2013-11-08（未见版本行）。

**理由**：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 探针导入题须先完成 probe 新版本复核/冻结，再供主集导入；不绕过 PR-16。

#### pc-0029-g1（PDF 物理页 3，norm-v1 偏移 [4174, 4258)）

关键锚点：`此類病人的esomeprazole 最高劑量不可超過 20 mg`

> 嚴重肝功能不良的病人的 esomeprazole 代謝率降低,導致血漿濃度時間曲線下的面積加倍,因此此類病人的esomeprazole 最高劑量不可超過 20 mg 。

映射：`2576704b-ffbb-46b0-a301-ad2f6a5301d4`。

复核应确认：问题范围与该来源一致；证据包含完整条件、否定与例外；必需组完整且没有误当替代；英文与父题语义一致（如适用）。当前状态：待复核。
