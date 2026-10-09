# 标注修订草案 v2：19 条第一人工确认，模型复核完成、4 条争议待裁决

日期：2026-10-08。状态 **draft / freeze_ready=false**。本版承接 [v1 草案](../revision-2026-10-08/README.md)，落实 13 道原裁决题、5 道英文联动题，并新增跨页回归题 ms-0525。v1 保留，正式冻结主集仍为 v3。

**人工确认更新（2026-10-08）**：用户在逐项差异说明后回复“同意”。19 条标注及 1 项 corpus 标题修正已登记[确认记录](human_confirmation_2026-10-08.json)，绑定原提案、manifest、标题修订与每条证据组的哈希。`proposals.json.review_state` 保留确认前的起草快照，后续人工决定以本确认记录为准。独立模型复核完成 19/19（15 同意、4 争议）后，项目所有者已按建议裁决三项并落实为 [v3](../revision-2026-10-08-v3/README.md)；本目录保留裁决前输入和原始意见。第二人工仍 pending；没有冻结新版或更新生产语料。

## 本轮变化与检查

- 新题的两条证据分别在 EMA GVP Module IV Rev 1 的第 8、9 页，都是完整原句，覆盖同一审计处理流程的紧急沟通与整改留证。该文档非派生题由 5 增为 6，低于 8。
- 按原 PR-19 投影：主集 615 题（有答案 554、无答案 61），long_context=20，全部既有数量要求满足。不是通过保留旧标签或扩大证据 span 补数。
- 共 39 个 gold 单元，39 mapped；页文本及偏移已核对。101 条 gold 页 chunk 坐标纳入本包；新增第 9 页的 7 个 chunk 已只读复查实际数据库。
- 自审发现 ms-0124/0125 与 ms-0243/0244 的首组 key 只含泛化谓语，已补足 Audit findings / Certain events 等对象，符合 P1 的对象与约束要求，映射组不变。第一人工已确认；独立模型已完成，具体原始意见见逐题结论；第二人工仍待完成。
- 新版检查补充了全量 query 唯一性、query 不等于 gold key、PII、同文档配额、新 ID 不复用、全部配额投影，以及必需输入文件哈希声明。

完整数据：[proposals.json](proposals.json) · [映射预览](chunk_mapping.preview.json) · [manifest](manifest.json) · [标题修订](corpus_edits.json)。每条新标注没有沿用旧 review；提案文件中的 pending 是起草时快照，后续第一人工确认见上方确认记录。本包不能作为正式数据集运行。

## 人工应重点检查

来源明确后的问题范围是否合适；多块证据是否共同必需；请求的可选性与期限是否区分；中文和英文孪生是否等义；新跨页题是否自然、可由两句完整回答。请逐项阅读下面的新 query 和原文；已有旧裁决不需重复作出。

三道 pc- 题须先完成新探针的复核/冻结，再导入新主集。新增题已被实现方看到，只是回归题。[第二人工分派](../../../review/stage-01-2026-10-08/README.md)与[独立盲测准备](../../../holdout/README.md)另行记录。

## 复现命令

```sh
venv/bin/python -m medops.evals.annotation_revision \
  evals/main_set/drafts/revision-2026-10-08-v2 --with-pages
make eval-check EVAL_ARGS=--with-pages
```

## 怎样看每条改动

以下逐项对照的是**冻结 main-v3 与当前草案 v2**；不是只对比草案 v1/v2。18 道旧题中，14 道 query 有改动、4 道 query 完全没变；另有 1 道新增题。9 道旧题修改了 gold/key，其余 9 道旧题的 gold/key 完全保持。未改 query 的四道题不再重复展示相同文字。

- `query`：交给系统的问题文字。
- `gold / evidence_span`：人工指定、用于评测的标准证据及其原文范围。
- `key_text`：在原文和 chunk 中定位这条证据的锚点，不是完整答案。
- “共同必需”：完整覆盖需要每组都命中；组内多个等价块可任选。
- 所有旧题的原文来源 hash 和版本未更换。题目中新增文档身份，是把既有 gold 来源写清楚。
- 18 道旧题均将 drafted_by 记录为本次草案作者，并移除旧 review；旧批准不自动覆盖新标注；本次第一人工已确认；模型复核完成、争议待裁决，第二人工仍 pending。以上不修改历史冻结样本。
- 另有一项 corpus 标题元数据修正：FDA 研究者安全报告指南的 September 2021 改为封面所示 December 2025；见本页“标题修订”链接，不是新增第 20 道题。

## 逐题材料

### ms-0124 · PV

**实际改动**：

- 问题文字未修改。
- gold 从 1 段改为 4 个共同必需单元：分级原则、critical、major、minor；原文总体范围仍为第 8 页 [952,2456)。
- 原 key 仅定位 critical 定义开头；现在四项分别定位，首项明确包含 Audit findings。
- 移除 long_context：原单段 1504 字符，拆分后各段不足 1500 字符且仍在同一页。

**query：未修改**。根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、major、minor 三个等级?每个等级的具体定义是什么?

来源：`ema-gvp-module-iv-rev1`。切片：negation, mixed_zh_en。

理由：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 本轮自审按 P1 将首组 key_text 补足对象，避免只锚定 should/still 等通用谓语；chunk 映射不变。

#### ms-0124-g1 · 物理页 8 · [952, 1176)

key_text：`Audit findings should be reported in line with their relative risk level and should be graded`

> Audit findings should be reported in line with their relative risk level and should be graded in order to indicate their relative criticality to risks impacting the pharmacovigilance system, processes and parts of processes.

映射组：`c0cb043c-cd67-4888-9e19-d1c822acd461`。

#### ms-0124-g2 · 物理页 8 · [1177, 1754)

key_text：`critical is a fundamental weakness in one or more pharmacovigilance processes or practices`

> The grading system should be defined in the description of the quality system for pharmacovigilance, and should take into consideration the thresholds noted below which would be used in further reporting under the legislation as set out in IV.C.2.: • critical is a fundamental weakness in one or more pharmacovigilance processes or practices that adversely affects the whole pharmacovigilance system and/or the rights, safety or well-being of patients, or that poses a potential risk to public health and/or represents a serious violation of applicable regulatory requirements.

映射组：`fc140511-65be-4a82-87ad-9dc9dd4e8543`。

#### ms-0124-g3 · 物理页 8 · [1755, 2226)

key_text：`major is a significant weakness in one or more pharmacovigilance processes or practices`

> • major is a significant weakness in one or more pharmacovigilance processes or practices, or a fundamental weakness in part of one or more pharmacovigilance processes or practices that is detrimental to the whole process and/or could potentially adversely affect the rights, safety or well-being of patients and/or could potentially pose a risk to public health and/or represents a violation of applicable regulatory requirements which is however not considered serious.

映射组：`05a7926d-889c-4182-a023-4b6f5cb97ee4`。

#### ms-0124-g4 · 物理页 8 · [2227, 2456)

key_text：`minor is a weakness in the part of one or more pharmacovigilance processes or practices`

> • minor is a weakness in the part of one or more pharmacovigilance processes or practices that is not expected to adversely affect the whole pharmacovigilance system or process and/or the rights, safety or well-being of patients.

映射组：`7313c35d-8d97-46d2-a2cf-f4724e14ecb4`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0125 · PV

**实际改动**：

- 英文问题文字未修改。
- 与 ms-0124 联动：gold 1→4，分别锚定分级原则与三个等级，四组共同必需。
- 移除 long_context，依据与中文题相同。

**query：未修改**。According to GVP Module IV, how should pharmacovigilance audit findings be graded as critical, major, or minor, and what is the specific definition of each grade?

来源：`ema-gvp-module-iv-rev1`。切片：negation, mixed_zh_en。

理由：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 与父题 ms-0124 同步 gold、切片和问题范围；旧复核不覆盖修订输入。 本轮自审按 P1 将首组 key_text 补足对象，避免只锚定 should/still 等通用谓语；chunk 映射不变。

#### ms-0125-g1 · 物理页 8 · [952, 1176)

key_text：`Audit findings should be reported in line with their relative risk level and should be graded`

> Audit findings should be reported in line with their relative risk level and should be graded in order to indicate their relative criticality to risks impacting the pharmacovigilance system, processes and parts of processes.

映射组：`c0cb043c-cd67-4888-9e19-d1c822acd461`。

#### ms-0125-g2 · 物理页 8 · [1177, 1754)

key_text：`critical is a fundamental weakness in one or more pharmacovigilance processes or practices`

> The grading system should be defined in the description of the quality system for pharmacovigilance, and should take into consideration the thresholds noted below which would be used in further reporting under the legislation as set out in IV.C.2.: • critical is a fundamental weakness in one or more pharmacovigilance processes or practices that adversely affects the whole pharmacovigilance system and/or the rights, safety or well-being of patients, or that poses a potential risk to public health and/or represents a serious violation of applicable regulatory requirements.

映射组：`fc140511-65be-4a82-87ad-9dc9dd4e8543`。

#### ms-0125-g3 · 物理页 8 · [1755, 2226)

key_text：`major is a significant weakness in one or more pharmacovigilance processes or practices`

> • major is a significant weakness in one or more pharmacovigilance processes or practices, or a fundamental weakness in part of one or more pharmacovigilance processes or practices that is detrimental to the whole process and/or could potentially adversely affect the rights, safety or well-being of patients and/or could potentially pose a risk to public health and/or represents a violation of applicable regulatory requirements which is however not considered serious.

映射组：`05a7926d-889c-4182-a023-4b6f5cb97ee4`。

#### ms-0125-g4 · 物理页 8 · [2227, 2456)

key_text：`minor is a weakness in the part of one or more pharmacovigilance processes or practices`

> • minor is a weakness in the part of one or more pharmacovigilance processes or practices that is not expected to adversely affect the whole pharmacovigilance system or process and/or the rights, safety or well-being of patients.

映射组：`7313c35d-8d97-46d2-a2cf-f4724e14ecb4`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0177 · PV

**实际改动**：

- 原“按 REG Art 10a(2) 和 DIR Art 22a(2)”改为“根据 GVP Module VIII Rev 3 中对……的说明”，明确引用的是指南对法规的说明。
- 原“MAH 希望……时”改为“MAH 若选择请求……”，并明确书面通知针对施加的义务，保留请求的可选性。
- gold、key、页码和切片均未修改；原文中的 30 天也未修改。

**原 query**：按 REG Art 10a(2) 和 DIR Art 22a(2)，MAH 希望针对被施加的义务陈述书面意见时，应在收到书面通知后多久内提出这一请求？

**新 query**：根据 GVP Module VIII Rev 3 中对 REG Art 10a(2) 和 DIR Art 22a(2) 的说明，MAH 若选择请求陈述书面意见，应在收到施加义务的书面通知后多久内提出请求？

来源：`ema-gvp-module-viii-rev3`。切片：time_window, protocol_id, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0177-g1 · 物理页 19 · [187, 427)

key_text：`Within 30 days of receipt of the written notification of an obligation imposed`

> Within 30 days of receipt of the written notification of an obligation imposed, the marketing authorisation holder may request to present written observations in response to the imposition of the obligation [REG Art 10a(2), DIR Art 22a(2)].

映射组：`7cdac483-63f7-460f-a19b-d42a18eecf6a`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0178 · PV

**实际改动**：

- 英文同步 ms-0177：新增 GVP Module VIII Rev 3 及 which cites，明确法规与指南的引用关系。
- 原 may ... request 改为 if ... chooses to request ... should it make the request，明确自愿选择与期限的关系。
- gold、key、页码和切片均未修改。

**原 query**：Under REG Art 10a(2) and DIR Art 22a(2), within how many days of receiving written notification of an imposed obligation may the marketing authorisation holder request to present written observations?

**新 query**：Under GVP Module VIII Rev 3, which cites REG Art 10a(2) and DIR Art 22a(2), if the marketing authorisation holder chooses to request to present written observations, within how many days of receiving written notification of the imposed obligation should it make that request?

来源：`ema-gvp-module-viii-rev3`。切片：time_window, protocol_id, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 与父题 ms-0177 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

#### ms-0178-g1 · 物理页 19 · [187, 427)

key_text：`Within 30 days of receipt of the written notification of an obligation imposed`

> Within 30 days of receipt of the written notification of an obligation imposed, the marketing authorisation holder may request to present written observations in response to the imposition of the obligation [REG Art 10a(2), DIR Art 22a(2)].

映射组：`7cdac483-63f7-460f-a19b-d42a18eecf6a`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0205 · PV

**实际改动**：

- 问题文字未修改。
- gold 1→4：SmPC 4.8；4.4/4.6；其余相关章节；有额外 RMM 材料时 4.4 的补充说明，四组共同必需。
- 原 key 仅定位总导语 presents information relevant to RMM in；改为四处分别定位，原文总体范围仍为第 36 页 [362,2194)。
- 移除 long_context：原单段 1832 字符，拆分后各段不足 1500 字符且同页。

**query：未修改**。根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果该药品配有额外RMM材料，SmPC 4.4节又应额外说明什么？

来源：`ema-gvp-module-xvi-rev3`。切片：protocol_id, mixed_zh_en。

理由：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。

#### ms-0205-g1 · 物理页 36 · [362, 658)

key_text：`Information on adverse reactions, including information characterising the reaction`

> the summary of product characteristics (SmPC) (see GVP Annex I) presents information relevant to RMM in: • SmPC section 4.8 ‘Undesirable Effects’: Information on adverse reactions, including information characterising the reaction which may be useful to prevent, monitor or manage its occurrence;

映射组：`05f240dd-a36c-414d-a2bc-61130c47f651`。

#### ms-0205-g2 · 物理页 36 · [659, 1253)

key_text：`Warnings and actions to be taken to avoid specific possible adverse reactions`

> • SmPC section 4.4 ‘Special Warnings and Precautions for Use’: Warnings and actions to be taken to avoid specific possible adverse reactions or to be taken if a specific reaction occurs or, if deemed necessary, actions to be taken as a precaution for potential risks; • SmPC section 4.6 ‘Fertility, Pregnancy and Lactation’: Information on risks of the medicinal product impacting on fertility, pregnancy and lactation, including risks for the embryo/foetus/child due to adverse effects at conception, in utero or through breastfeeding, and actions to be taken to avoid or minimise these risks;

映射组：`b7f9d06b-d380-4bcf-966f-f05b371b7cf9`。

#### ms-0205-g3 · 物理页 36 · [1254, 1669)

key_text：`Safe use advice regarding indications, dosing and administration, contraindications, interactions`

> • SmPC sections 4.1 ‘Therapeutic Indications’, 4.2 ‘Posology and Method of Administration’, 4.3 ‘Contraindications’, 4.5 ‘Interaction with Other Medicinal Products and Other Forms of Interaction’, 4.7 ‘Effects on Ability to Drive and Use Machines’ and 4.9’ Overdose’: Safe use advice regarding indications, dosing and administration, contraindications, interactions, ability to drive and use machines, and overdose.

映射组：`62b7f077-0073-44cf-aab0-0740a2d7898f`。

#### ms-0205-g4 · 物理页 36 · [1670, 2194)

key_text：`should describe the intended actions for risk minimisation and should include a statement`

> For medicinal products with additional RMM materials, according to the Guideline on Summary of Product Characteristics26 and supplementary Guidance on Frequently Asked Questions on SmPC Section 4.427, the SmPC section 4.4. should describe the intended actions for risk minimisation and should include a statement on the educational/safety advice materials addressed to healthcare professionals or patients which clearly and succinctly explains the purpose (e.g. “to be handed out to the patient”) and scope of the materials.

映射组：`737c819a-dd24-4ac1-9862-88fdd83e7113`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0206 · PV

**实际改动**：

- 英文问题文字未修改。
- 与 ms-0205 联动：gold 1→4，每项有独立 key，四组共同必需。
- 移除 long_context，依据与中文题相同。

**query：未修改**。According to GVP Module XVI, what information relevant to risk minimisation measures (RMM) should the relevant SmPC sections contain, and what additional information should Section 4.4 include when additional RMM materials are provided?

来源：`ema-gvp-module-xvi-rev3`。切片：protocol_id, mixed_zh_en。

理由：分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 与父题 ms-0205 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

#### ms-0206-g1 · 物理页 36 · [362, 658)

key_text：`Information on adverse reactions, including information characterising the reaction`

> the summary of product characteristics (SmPC) (see GVP Annex I) presents information relevant to RMM in: • SmPC section 4.8 ‘Undesirable Effects’: Information on adverse reactions, including information characterising the reaction which may be useful to prevent, monitor or manage its occurrence;

映射组：`05f240dd-a36c-414d-a2bc-61130c47f651`。

#### ms-0206-g2 · 物理页 36 · [659, 1253)

key_text：`Warnings and actions to be taken to avoid specific possible adverse reactions`

> • SmPC section 4.4 ‘Special Warnings and Precautions for Use’: Warnings and actions to be taken to avoid specific possible adverse reactions or to be taken if a specific reaction occurs or, if deemed necessary, actions to be taken as a precaution for potential risks; • SmPC section 4.6 ‘Fertility, Pregnancy and Lactation’: Information on risks of the medicinal product impacting on fertility, pregnancy and lactation, including risks for the embryo/foetus/child due to adverse effects at conception, in utero or through breastfeeding, and actions to be taken to avoid or minimise these risks;

映射组：`b7f9d06b-d380-4bcf-966f-f05b371b7cf9`。

#### ms-0206-g3 · 物理页 36 · [1254, 1669)

key_text：`Safe use advice regarding indications, dosing and administration, contraindications, interactions`

> • SmPC sections 4.1 ‘Therapeutic Indications’, 4.2 ‘Posology and Method of Administration’, 4.3 ‘Contraindications’, 4.5 ‘Interaction with Other Medicinal Products and Other Forms of Interaction’, 4.7 ‘Effects on Ability to Drive and Use Machines’ and 4.9’ Overdose’: Safe use advice regarding indications, dosing and administration, contraindications, interactions, ability to drive and use machines, and overdose.

映射组：`62b7f077-0073-44cf-aab0-0740a2d7898f`。

#### ms-0206-g4 · 物理页 36 · [1670, 2194)

key_text：`should describe the intended actions for risk minimisation and should include a statement`

> For medicinal products with additional RMM materials, according to the Guideline on Summary of Product Characteristics26 and supplementary Guidance on Frequently Asked Questions on SmPC Section 4.427, the SmPC section 4.4. should describe the intended actions for risk minimisation and should include a statement on the educational/safety advice materials addressed to healthcare professionals or patients which clearly and succinctly explains the purpose (e.g. “to be handed out to the patient”) and scope of the materials.

映射组：`737c819a-dd24-4ac1-9862-88fdd83e7113`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0241 · PV

**实际改动**：

- 原仅点名 IND 法规条款，改为明确 FDA 2025 年 12 月《Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices》指南及其中条款。
- gold 1→3：罕见且与药物暴露高度相关的单次事件；其他罕见事件及汇总比较的示例；标准治疗也可能相关的补充说明。原文总体范围不变。
- 原 key 是 reasonable possibility 的导语；新 key 分别定位三个单元，要求三组共同覆盖。第三组是否应强制必需，是本次新增的语义复核重点。
- 切片未修改。

**原 query**：依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reasonable possibility)因果关系时可参考哪些示例情形?

**新 query**：根据 FDA 2025 年 12 月《Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices》指南，§ 312.32(c)(1)(i) 的哪些示例说明药物与不良事件间存在因果关系的“合理可能性”（reasonable possibility）？

来源：`fda-investigator-safety-reporting-2025`。切片：protocol_id, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 原页另发现示例及汇总分析说明跨三个块，不能只命中导语；此扩展为实现方新增修订建议，尚待复核。

#### ms-0241-g1 · 物理页 7 · [753, 1185)

key_text：`A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure`

> The following examples are also provided in the IND safety reporting regulation (§ 312.32(c)(1)(i)) and illustrate the meaning of reasonable possibility with respect to a determination that there may be a causal relationship between the drug and the adverse event: • A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure (e.g., angioedema, hepatic injury, Stevens-Johnson Syndrome).

映射组：`03b274ab-a8e2-4032-bbc7-10379ae547b9`。

#### ms-0241-g2 · 物理页 7 · [1186, 1731)

key_text：`An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently`

> • One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug (e.g., tendon rupture). • An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group. Examples of such events are known consequences of the underlying disease or condition or events that commonly occur in the study population independent of drug therapy.

映射组：`dc317e2b-b2e7-49ab-b9e7-298ff69fb957`。

#### ms-0241-g3 · 物理页 7 · [1732, 1900)

key_text：`such events could also be associated with treatment or therapy that is standard of care`

> For aggregate analysis under § 312.32(c)(1)(i)(C), such events could also be associated with treatment or therapy that is standard of care for the disease or condition.

映射组：`cd331ebb-3faf-4c10-b8a6-47ddc7194b39`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0242 · PV

**实际改动**：

- 英文同步明确 FDA December 2025 指南全名，保留原条款号和 reasonable possibility 问法。
- gold 与 key 同 ms-0241：1→3，三组共同必需；第三组必要性待复核。
- 切片未修改。

**原 query**：According to the examples provided under § 312.32(c)(1)(i) for IND safety reporting, what examples illustrate a 'reasonable possibility' of a causal relationship between a drug and an adverse event?

**新 query**：According to FDA’s December 2025 guidance “Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices”, what examples under § 312.32(c)(1)(i) illustrate a reasonable possibility of a causal relationship between a drug and an adverse event?

来源：`fda-investigator-safety-reporting-2025`。切片：protocol_id, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 原页另发现示例及汇总分析说明跨三个块，不能只命中导语；此扩展为实现方新增修订建议，尚待复核。 与父题 ms-0241 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

#### ms-0242-g1 · 物理页 7 · [753, 1185)

key_text：`A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure`

> The following examples are also provided in the IND safety reporting regulation (§ 312.32(c)(1)(i)) and illustrate the meaning of reasonable possibility with respect to a determination that there may be a causal relationship between the drug and the adverse event: • A single occurrence of an event that is uncommon and known to be strongly associated with drug exposure (e.g., angioedema, hepatic injury, Stevens-Johnson Syndrome).

映射组：`03b274ab-a8e2-4032-bbc7-10379ae547b9`。

#### ms-0242-g2 · 物理页 7 · [1186, 1731)

key_text：`An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently`

> • One or more occurrences of an event that is not commonly associated with drug exposure but is otherwise uncommon in the population exposed to the drug (e.g., tendon rupture). • An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group. Examples of such events are known consequences of the underlying disease or condition or events that commonly occur in the study population independent of drug therapy.

映射组：`dc317e2b-b2e7-49ab-b9e7-298ff69fb957`。

#### ms-0242-g3 · 物理页 7 · [1732, 1900)

key_text：`such events could also be associated with treatment or therapy that is standard of care`

> For aggregate analysis under § 312.32(c)(1)(i)(C), such events could also be associated with treatment or therapy that is standard of care for the disease or condition.

映射组：`cd331ebb-3faf-4c10-b8a6-47ddc7194b39`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0243 · PV

**实际改动**：

- 新增 FDA 2025 年 12 月指南身份。
- 原“除 IND 安全报告和 BA/BE 研究中的 SAE 外”改为“即使不符合 IND 安全报告或 BA/BE 研究上市前 SAE 报告标准”，明确区分不同报告标准。
- 原“涉及受试者风险”改为“涉及受试者或他人风险”。
- gold 1→2：报告原则与具体例子共同必需；第一组 key 与冻结 v3 相同，第二组新增 Other examples may include reports of medication errors。切片未修改。

**原 query**：在IND研究中,除IND安全报告和BA/BE研究中的SAE外,哪些其他类型的事件即使不符合IND安全报告标准,仍必须作为涉及受试者风险的意外问题(unanticipated problem)报告给IRB,请举例说明?

**新 query**：根据 FDA 2025 年 12 月《Investigator Responsibilities — Safety Reporting for Investigational Drugs and Devices》指南，哪些事件即使不符合 IND 安全报告或 BA/BE 研究上市前 SAE 报告标准，仍须作为涉及受试者或他人风险的意外问题报告给 IRB？请举例说明。

来源：`fda-investigator-safety-reporting-2025`。切片：negation, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 本轮自审按 P1 将首组 key_text 补足对象，避免只锚定 should/still 等通用谓语；chunk 映射不变。

#### ms-0243-g1 · 物理页 12 · [816, 1061)

key_text：`Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB`

> Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB because they represent unanticipated problems involving risk to human participants or others.

映射组：`56c2d993-45d3-4934-a083-ecfdfb2861e3`。

#### ms-0243-g2 · 物理页 12 · [1062, 1588)

key_text：`Other examples may include reports of medication errors`

> − Such events may occur at the participant, site, and/or study level and may include serious and unexpected adverse events that occur prior to test article administration, during a washout period, or that are attributable to a screening procedure. − Other examples may include reports of medication errors (such as receipt of wrong dose or contaminated study medication), breach of privacy/confidentiality (such as disclosure of personally identifiable information), untimely destruction of study records, and other scenarios.

映射组：`f22428d5-feb0-473b-9c17-41c005048f26`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0244 · PV

**实际改动**：

- 英文同步补上 FDA December 2025 指南身份，将 apart from 改成 even if they do not qualify，明确未达到相关报告标准仍可能需报 IRB 的问法。
- gold 1→2，原则与例子共同必需；第一组 key 与冻结 v3 相同，第二组新增例子锚点。
- 切片未修改。

**原 query**：In IND studies, apart from IND safety reports and premarket SAEs from BA/BE studies, what other events must be reported to the IRB as unanticipated problems involving risk to participants even when they do not meet IND safety-reporting criteria? Give examples.

**新 query**：Under FDA’s December 2025 investigator safety-reporting guidance, which events still require IRB reporting as unanticipated problems even if they do not qualify for an IND safety report or a BA/BE premarket SAE? Give examples.

来源：`fda-investigator-safety-reporting-2025`。切片：negation, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 分开完整证据单元并保留上下文，组间共同必需；按现行 PR-19 重算 long_context。 与父题 ms-0243 同步 gold、切片和问题范围；旧复核不覆盖修订输入。 本轮自审按 P1 将首组 key_text 补足对象，避免只锚定 should/still 等通用谓语；chunk 映射不变。

#### ms-0244-g1 · 物理页 12 · [816, 1061)

key_text：`Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB`

> Certain events may not meet the criteria for reporting in an IND safety report or as a BA/BE study premarket SAE, but still must be reported to the IRB because they represent unanticipated problems involving risk to human participants or others.

映射组：`56c2d993-45d3-4934-a083-ecfdfb2861e3`。

#### ms-0244-g2 · 物理页 12 · [1062, 1588)

key_text：`Other examples may include reports of medication errors`

> − Such events may occur at the participant, site, and/or study level and may include serious and unexpected adverse events that occur prior to test article administration, during a washout period, or that are attributable to a screening procedure. − Other examples may include reports of medication errors (such as receipt of wrong dose or contaminated study medication), breach of privacy/confidentiality (such as disclosure of personally identifiable information), untimely destruction of study records, and other scenarios.

映射组：`f22428d5-feb0-473b-9c17-41c005048f26`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0280 · PV

**实际改动**：

- 原泛指“使用 MedDRA 时”，改为点名《MedDRA 数据检索和展示：考虑要点》3.26（2026 年 3 月）。
- “术语的层级结构”调整为“MedDRA 的术语层级结构”，提问对象明确为用户；仍询问能否临时改动及 PT 主 SOC 分配。
- gold、key、页码和切片均未修改。

**原 query**：使用 MedDRA 时,能否对术语的层级结构进行临时改动,比如变更某个 PT 的主 SOC 分配?

**新 query**：根据《MedDRA 数据检索和展示：考虑要点》发布版本 3.26（2026 年 3 月），用户能否临时改动 MedDRA 的术语层级结构，例如变更某个 PT 的主 SOC 分配？

来源：`meddra-data-retrieval-ptc-3-26-zh-hans`。切片：negation, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0280-g1 · 物理页 8 · [535, 657)

key_text：`用户不得对 MedDRA 进行临时的结构改动,包括变更主 SOC 分配`

> MedDRA 是一个标准术语集,有预先界定的术语层级结构,不应更改。用户不得对 MedDRA 进行临时的结构改动,包括变更主 SOC 分配;这样做将有损该标准的完整性。如果发现术语的 MedDRA 层级结构不正确,应向 MSSO 提交变更申请。

映射组：`b0373069-8929-4b2e-aab7-48212775ac10`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0298 · CO

**实际改动**：

- 原“根据 ICH E6(R3)”改为“根据 FDA 2025 年 9 月《E6(R3) Good Clinical Practice》指南”，与实际标注来源一致。
- 原“事先书面批准”改为“事先记录在案的批准或赞同意见”，对应 documented approval/favorable opinion。
- gold 1→2：两项保留同一个完整上下文 span，分别用“消除受试者即时危险”和“符合适用法规的纯行政/后勤变更”作为短 key；旧跨 chunk 长 key 改为可分别映射。
- 评测要求完整列出两种例外，不代表业务上两种例外须同时发生。切片未修改。

**原 query**：根据ICH E6(R3),在什么情况下可以不经IRB/IEC事先书面批准就对已批准的试验方案进行偏离或变更?

**新 query**：根据 FDA 2025 年 9 月《E6(R3) Good Clinical Practice》指南，在哪些情况下，可以不经 IRB/IEC 事先记录在案的批准或赞同意见就对已批准的试验方案进行偏离或变更？

来源：`fda-e6r3-gcp-2025`。切片：negation, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 原 key_text 跨 chunk，属于旧 7 条 unmappable 之一；拆成“紧急危险”和“法规允许的行政/后勤变更”两组，保留完整共同上下文，两个条件都须覆盖。

#### ms-0298-g1 · 物理页 18 · [1177, 1554)

key_text：`when necessary to eliminate immediate hazards to the participants`

> no deviations from or changes to the protocol should be initiated without prior documented IRB/IEC approval/favorable opinion of an appropriate protocol amendment except when necessary to eliminate immediate hazards to the participants or, in accordance with applicable regulatory requirements, when the change(s) involves only logistical or administrative aspects of the trial

映射组：`9a07ba2f-4043-4450-8b53-49b3fa9507db`。

#### ms-0298-g2 · 物理页 18 · [1177, 1554)

key_text：`in accordance with applicable regulatory requirements, when the change(s) involves only logistical or administrative aspects of the trial`

> no deviations from or changes to the protocol should be initiated without prior documented IRB/IEC approval/favorable opinion of an appropriate protocol amendment except when necessary to eliminate immediate hazards to the participants or, in accordance with applicable regulatory requirements, when the change(s) involves only logistical or administrative aspects of the trial

映射组：`00062a43-08f0-4114-b843-b9ef14106733`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0299 · CO

**实际改动**：

- 原“根据 ICH E6(R3)”改为明确 FDA 2025 年 9 月版本。
- 原“施压”改为“胁迫或不当影响”，对应 coerce or unduly influence；继续参与试验的提问范围保留。
- gold、key、页码和切片均未修改。

**原 query**：根据ICH E6(R3),研究者或研究机构工作人员是否可以对受试者施压以促使其继续参与临床试验?

**新 query**：根据 FDA 2025 年 9 月《E6(R3) Good Clinical Practice》指南，研究者或研究机构工作人员是否可以胁迫或不当影响受试者，使其继续参与临床试验？

来源：`fda-e6r3-gcp-2025`。切片：negation, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0299-g1 · 物理页 24 · [209, 377)

key_text：`Neither the investigator nor the investigator site staff should coerce or unduly influence a participant to participate or to continue their participation in the trial`

> Neither the investigator nor the investigator site staff should coerce or unduly influence a participant to participate or to continue their participation in the trial.

映射组：`c38214e4-2dd1-49f1-b311-b50697a427c7`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0336 · CO

**实际改动**：

- 原仅问“根据 21 CFR 312.50”，改为点名 FDA 2013 年 8 月《Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring》指南对该条款的引述。
- 原“有哪些具体职责”缩小为“须确保哪两件事”，让问题范围与现有 gold 支持的两项内容一致。
- gold、key、页码和切片均未修改。

**原 query**：根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？

**新 query**：根据 FDA 2013 年 8 月《Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring》指南引述的 21 CFR 312.50，申办者在临床试验监查方面须确保哪两件事？

来源：`fda-risk-based-monitoring-2013`。切片：protocol_id, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。

#### ms-0336-g1 · 物理页 5 · [3227, 3467)

key_text：`ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”`

> 21 CFR 312.50 requires a sponsor to, among other things, ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”

映射组：`233db844-7a4a-426f-a28d-dcc0b8b6ee41`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0337 · CO

**实际改动**：

- 原英文已点名 FDA August 2013 risk-based monitoring guidance；此次补全正式标题，不是从没有来源改成有来源。
- 原 what specific monitoring responsibilities 改为 which two things ... regarding trial monitoring and conduct，与中文题同步限定两项。
- gold、key、页码和切片均未修改。

**原 query**：According to the passage quoting 21 CFR 312.50 in FDA's August 2013 risk-based monitoring guidance, what specific monitoring responsibilities does a sponsor have for a clinical investigation?

**新 query**：According to the passage quoting 21 CFR 312.50 in FDA’s August 2013 guidance “Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring”, which two things must a sponsor ensure regarding trial monitoring and conduct?

来源：`fda-risk-based-monitoring-2013`。切片：protocol_id, mixed_zh_en。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 与父题 ms-0336 同步 gold、切片和问题范围；旧复核不覆盖修订输入。

#### ms-0337-g1 · 物理页 5 · [3227, 3467)

key_text：`ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”`

> 21 CFR 312.50 requires a sponsor to, among other things, ensure “proper monitoring of the investigation(s)” and “that the investigation(s) is conducted in accordance with the general investigational plan and protocols contained in the IND.”

映射组：`233db844-7a4a-426f-a28d-dcc0b8b6ee41`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### pc-0017 · MA

**实际改动**：

- 原通用问法前增加“根據穩壓膜衣錠50毫克仿單”，句末补问号；ACEI/ARB 的原问题保持。
- 增加 drug_name_zh 标签。gold、key、页码均未修改。
- 属于探针导入题，须先在探针新版本完成复核/冻结，再导入主集。

**原 query**：糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎

**新 query**：根據穩壓膜衣錠50毫克仿單，糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎？

来源：`tfda-label-zosaa-50mg`。切片：negation, mixed_zh_en, drug_name_zh。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 探针导入题须先完成 probe 新版本复核/冻结，再供主集导入；不绕过 PR-16。

#### pc-0017-g1 · 物理页 1 · [2612, 2859)

key_text：`ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者`

> 雙重阻斷腎素-血管昇壓素-醛固酮系統(renin-angiotensin-aldosterone system, RAAS):有證據顯示,合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品會增加低血壓、高鉀血症及腎功能下降(包括急性腎衰竭)之風險,故不建議合併使用 ACEIs、ARBs 或含 aliskiren 成分藥品來雙重阻斷 RAAS,若確有必要使用雙重阻斷治療,應密切監測患者之腎+A12 功能、電解質及血壓。ACEIs 及 ARBs 不應合併使用於糖尿病腎病變患者。

映射组：`189c6570-b688-4b28-83ec-a94026d9f772`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### pc-0028 · MA

**实际改动**：

- 原问 esomeprazole 与 nelfinavir 能否合用，改为明确“胃所樂腸溶膜衣錠40毫克（esomeprazole）仿單”；句式调整为“可以與……一起服用嗎？”。
- 增加 drug_name_zh 标签。gold、key、页码均未修改。
- 属于探针导入题，须先走探针升版。

**原 query**：esomeprazole 可以和 nelfinavir 一起服用嗎

**新 query**：根據胃所樂腸溶膜衣錠40毫克（esomeprazole）仿單，可以與 nelfinavir 一起服用嗎？

来源：`tfda-label-esomen-40mg`。切片：negation, mixed_zh_en, drug_name_zh。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 探针导入题须先完成 probe 新版本复核/冻结，再供主集导入；不绕过 PR-16。

#### pc-0028-g1 · 物理页 2 · [811, 924)

key_text：`禁止同時併用 esomeprazole 和 nelfinavir`

> 由於omeprazole 與 esomeprazole 的藥效學效應與藥動學性質類似,故不建議同時投予 esomeprazole 和 atazanavir ,禁止同時併用 esomeprazole 和 nelfinavir 。

映射组：`61c0abb1-c83b-4b30-9ebf-e93935edf2f3`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### pc-0029 · MA

**实际改动**：

- 原通用剂量问法增加“根據胃所樂腸溶膜衣錠40毫克仿單”，并调整语序和问号。
- 增加 drug_name_zh 标签。gold、key、页码均未修改；原文中的最高剂量 20 mg 未修改。产品规格 40 mg 与该人群最高剂量 20 mg 是不同概念。
- 属于探针导入题，须先走探针升版。

**原 query**：嚴重肝功能不良的病人 esomeprazole 最高劑量是多少

**新 query**：根據胃所樂腸溶膜衣錠40毫克仿單，嚴重肝功能不良病人的 esomeprazole 最高劑量是多少？

来源：`tfda-label-esomen-40mg`。切片：dose_unit, negation, mixed_zh_en, drug_name_zh。

理由：明确文档身份、版本或条件式问法；不再以未点名来源限定旧问题。 探针导入题须先完成 probe 新版本复核/冻结，再供主集导入；不绕过 PR-16。

#### pc-0029-g1 · 物理页 3 · [4174, 4258)

key_text：`此類病人的esomeprazole 最高劑量不可超過 20 mg`

> 嚴重肝功能不良的病人的 esomeprazole 代謝率降低,導致血漿濃度時間曲線下的面積加倍,因此此類病人的esomeprazole 最高劑量不可超過 20 mg 。

映射组：`2576704b-ffbb-46b0-a301-ad2f6a5301d4`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。

### ms-0525 · PV

**实际改动**：

- 新增题，没有旧 query。询问同一审计处置流程中的加急沟通对象，以及整改完成后的留证。
- 新增 2 个共同必需 gold：第 8 页的沟通对象、第 9 页的整改留证；key 分别采用完整原句。
- 新增 mixed_zh_en、long_context 标签；因真实跨页满足现行规则。该题补入回归集，不计为未见盲测。

**原 query**：新增题，无旧标注。

**新 query**：根据 EMA GVP Module IV Rev 1，审计发现中需要紧急处理的问题应向哪些管理层加急沟通？整改措施完成后，应记录什么证据，以证明哪些问题已得到处理？

来源：`ema-gvp-module-iv-rev1`。切片：mixed_zh_en, long_context。

理由：按原 PR-19 跨两页条件补长上下文样本；同一审计处置流程中的加急沟通与完成留证，不扩大 span。 该文档非派生题由 5 变为 6，低于上限 8；题目与既有问题不同。 实施者已看到题目，应列为回归用途；第一人工已确认、模型已同意，第二人工仍待完成。

#### ms-0525-g1 · 物理页 8 · [2457, 2598)

key_text：`Issues that need to be urgently addressed should be communicated in an expedited manner to the auditee’s management and the upper management.`

> Issues that need to be urgently addressed should be communicated in an expedited manner to the auditee’s management and the upper management.

映射组：`7313c35d-8d97-46d2-a2cf-f4724e14ecb4`。

#### ms-0525-g2 · 物理页 9 · [261, 391)

key_text：`Evidence of completion of actions should be recorded in order to document that issues raised during the audit have been addressed.`

> Evidence of completion of actions should be recorded in order to document that issues raised during the audit have been addressed.

映射组：`085a5ee2-c298-456c-ac7d-be1fd117b026`。

结论：**第一人工已确认（2026-10-08）；待新模型复核，第二人工暂无／pending**。
