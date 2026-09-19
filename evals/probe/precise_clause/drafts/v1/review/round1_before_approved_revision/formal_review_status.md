# 新口径正式复核进度与争议

提示 SHA-256：`f4a3804e969b23ec9ab467406937e62f0b9e30933d6a680d4b00ee59b2631c38`。模型 gpt-6-astra，逐条 high；本表由 review_summary.py 生成。

下列建议来自独立复核人，尚未自动采纳，也不是人工裁决。
已有人工依据见 [确认记录](owner_confirmations_2026-09-19.md)；草稿、页文本或提示变更后须重新复核。

- MA：30/30；agree 17，dispute 13。
- PV：29/29；agree 10，dispute 19。
- CO：16/16；agree 1，dispute 15。

合计 75/75；agree 28，dispute 47。
复核已跑完，争议尚未裁决；未冻结。

## pc-0003 / MA / key_text

问题：超過八十歲的老人家可以開始用美洛醣嗎

当前锚点：不建議開始使用

原文位置：tfda-label-loformin-850mg，物理页 1，用法用量。

复核理由：key_text「不建議開始使用」虽为页内唯一原文，但未保留适用对象「大於80歲之老年患者」，不符合 P1 要求的同时保留对象与约束。

复核人建议：将 key_text 改为「大於80歲之老年患者不建議開始使用」。

人工裁决：待处理。

## pc-0006 / MA / slices

问题：衛部藥製字第058257號是哪一個藥品

当前锚点：衛部藥製字第058257號 Code No. 美洛醣膜衣錠850毫克

原文位置：tfda-label-loformin-850mg，物理页 2，許可證資訊。

复核理由：切片漏标 mixed_zh_en：key_text 含英文标识及缩写“Code No.”，按 P2 应计入；protocol_id 和 dose_unit 均成立。

复核人建议：将 slices 改为 ["protocol_id","dose_unit","mixed_zh_en"]。

人工裁决：待处理。

## pc-0008 / MA / key_text

问题：allopurinol 一般成人的處方限量是多少（每一劑量與每天）

当前锚点：每一劑量300mg;每天800mg

原文位置：tfda-label-deurinol-300mg，物理页 3，用法用量。

复核理由：key_text 虽为页内唯一的逐字原文，但未保留一般成人这一对象及处方限量这一约束，单独命中无法区分常规剂量与处方上限，不符合 P1。完整 evidence_span 中的“處方限量”属于限制表达，支持 negation 标签。

复核人建议：将 key_text 改为“一般成人處方限量:每一劑量300mg;每天800mg”。

人工裁决：待处理。

## pc-0011 / MA / key_text

问题：痛風停錠單次劑量的上限是多少

当前锚点：不得超過300 mg

原文位置：tfda-label-deurinol-300mg，物理页 8，注意事項。

复核理由：key_text「不得超過300 mg」雖為頁內唯一的逐字原文，但缺少受限對象「單一劑量」，未符合 P1 同時保留對象與約束的要求，無法單獨區分單次劑量上限與每日劑量限制。

复核人建议：將 key_text 改為頁內連續原文「單一劑量,都必須不得超過300 mg」，保留受限對象及上限約束。

人工裁决：待处理。

## pc-0012 / MA / slices

问题：衛署藥製字第 048564 號的藥品須由醫師處方使用嗎

当前锚点：本藥須由醫師處方使用

原文位置：tfda-label-deurinol-300mg，物理页 10，許可證資訊。

复核理由：切片缺少 negation：完整 evidence_span 中的「本藥須由醫師處方使用」限定藥品須憑醫師處方使用，屬於切片定義中的限制表達。

复核人建议：將 slices 改為 ["protocol_id", "negation"]。

人工裁决：待处理。

## pc-0015 / MA / key_text

问题：高血壓且血管內體液缺乏的病人使用穩壓膜衣錠的起始劑量是多少

当前锚点：改用每次 25mg

原文位置：tfda-label-zosaa-50mg，物理页 1，用法用量。

复核理由：key_text「改用每次 25mg」虽为页内唯一原文，但未保留剂量对象「起始劑量」及「需考慮」的限定语义，不符合 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为「其起始劑量需考慮改用每次 25mg」。

人工裁决：待处理。

## pc-0016 / MA / key_text

问题：糖尿病患者能同時使用穩壓膜衣錠和 aliskiren 嗎

当前锚点：合併使用本品及含 aliskiren 成分藥品於糖尿病患

原文位置：tfda-label-zosaa-50mg，物理页 1，禁忌症。

复核理由：key_text 虽为页内唯一原文，但未保留“禁忌症:”这一限制，无法表达糖尿病患者禁止合并用药的含义，不符合 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为“禁忌症:合併使用本品及含 aliskiren 成分藥品於糖尿病患”，保留禁忌语义。

人工裁决：待处理。

## pc-0023 / MA / slices

问题：心壓暢錠過量時，該如何急救

当前锚点：靜脈注射1〜2mg Atropine sulfate

原文位置：tfda-label-cancliol-100mg，物理页 2，過量處理。

复核理由：完整 evidence_span 中的「倘若還未能達到滿意效果時」是接續投與升壓劑的必要限制條件，須保留其否定語義；現有切片缺少 negation。

复核人建议：在 slices 中補入 negation。

人工裁决：待处理。

## pc-0024 / MA / key_text

问题：衛署藥製字第 029301 號是哪個藥品

当前锚点：心壓暢錠 100 毫克(美托普洛)

原文位置：tfda-label-cancliol-100mg，物理页 1，許可證資訊。

复核理由：key_text 虽为页内唯一的逐字原文，但仍可缩短为“心壓暢錠 100 毫克”，保留药品对象及规格约束；末尾“(美托普洛)”不是该查询命中所必需的信息，不符合 P1 最小性要求。

复核人建议：将 key_text 改为“心壓暢錠 100 毫克”，完整 evidence_span 保持不变。

人工裁决：待处理。

## pc-0025 / MA / evidence_span

问题：胃所樂腸溶膜衣錠可以嚼碎或壓碎再吃嗎

当前锚点：不可嚼破或壓破本錠劑

原文位置：tfda-label-esomen-40mg，物理页 1，用法用量。

复核理由：evidence_span 范围过宽。首句已完整回答能否嚼碎或压碎药片，后续吞咽困难患者的分散服药步骤、30 分钟时限及胃管给药限制不是回答该问题所必需的限定条件，不符合围绕一个条款保留必要限定条件的要求。现有切片按所给完整 span 判断成立。

复核人建议：将 evidence_span 缩为“本錠劑應整粒以液體吞服,不可嚼破或壓破本錠劑。”并同步更新偏移；缩短后删除 time_window 标签，保留 negation 和 drug_name_zh。

人工裁决：待处理。

## pc-0026 / MA / key_text, evidence_span

问题：胃所樂泡在水裡崩散後要在多久之內喝完

当前锚点：30 分鐘之內

原文位置：tfda-label-esomen-40mg，物理页 1，用法用量。

复核理由：key_text“30 分鐘之內”仅含时限，未保留服用对象与动作，不符合 P1。evidence_span 虽回答时限，但遗漏前文对该服用方式的限定：“對於有吞嚥困難的病人,可將藥錠置入半杯非碳酸類的水中,且不可使用他種液體,因為藥錠的腸衣膜可能因此溶解。”

复核人建议：将 key_text 改为“立即或在 30 分鐘之內將水連同小藥球喝下”；将 evidence_span 向前扩展以包含上述适用人群及用水限定，并同步更新偏移。扩展后的 span 含“不可使用他種液體”，应增加 negation 标签。

人工裁决：待处理。

## pc-0027 / MA / evidence_span

问题：胃所樂腸溶膜衣錠用於食道未發炎的胃食道逆流症狀治療，劑量和療程是多少

当前锚点：食道未發炎之患者 20 mg 每天 1次

原文位置：tfda-label-esomen-40mg，物理页 1，用法用量。

复核理由：evidence_span 遗漏适用人群的上位限定。页文本将该条款置于“成人成人成人成人及及及及 12 歲以上之青少年歲以上之青少年歲以上之青少年歲以上之青少年”之下，现有 span 未保留此年龄范围。

复核人建议：证据应保留成人及12岁以上青少年的适用范围，并同步核对文本及偏移；回答疗程时应区分“若 4週後仍有症狀時,則應進一步檢查患者。”与固定4周疗程，原文未明确规定固定疗程。

人工裁决：待处理。

## pc-0029 / MA / key_text

问题：嚴重肝功能不良的病人 esomeprazole 最高劑量是多少

当前锚点：不可超過 20 mg

原文位置：tfda-label-esomen-40mg，物理页 3，特殊族群。

复核理由：key_text「不可超過 20 mg」虽为页内唯一的逐字原文，但仅保留限制与数值，未保留药物及剂量对象，不符合 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为页内原文「此類病人的esomeprazole 最高劑量不可超過 20 mg」，保留现有 evidence_span 以明确严重肝功能不良的人群限定。

人工裁决：待处理。

## pc-0031 / PV / key_text

问题：MedDRA 的术语层级结构可以由使用机构自行更改吗？

当前锚点：不应更改

原文位置：meddra-term-selection-ptc-4-26-zh-hans，物理页 9，2.3 不要改动 MedDRA。

复核理由：key_text“不应更改”仅保留限制表达，未保留对象“术语层级结构”，不符合 P1 要求的同时保留对象与约束。

复核人建议：将 key_text 改为页内唯一的逐字原文“术语层级结构,不应更改”。

人工裁决：待处理。

## pc-0036 / PV / slices

问题：药物说明书要求每月监测肝酶，患者却每六个月才测一次，这类用药错误应选择哪个 LLT？

当前锚点：用药监测步骤执行不正确

原文位置：meddra-term-selection-ptc-4-26-zh-hans，物理页 38，3.15.1.3 用药监测错误。

复核理由：切片标签缺失：完整 evidence_span 中“每 6 个月测一次肝酶”和“每月一次”属于频次表达，应标注 dose_unit；“没有按照推荐日程即每月一次”及“没有遵照推荐的实验室检查”包含判定监测错误所必需的否定语义，应标注 negation。

复核人建议：保留现有标签，补充 dose_unit 和 negation。

人工裁决：待处理。

## pc-0037 / PV / key_text

问题：MedDRA 的多轴性是指什么？

当前锚点：将一个 PT 分配给多个系统器官分类 [SOC]

原文位置：meddra-data-retrieval-ptc-3-26-zh-hans，物理页 4，SECTION 1 – 引言。

复核理由：key_text 中的“ [SOC]”可删除，删除后仍完整保留将一个 PT 分配给多个系统器官分类的对象与约束，且在页内唯一，故现有 key_text 不满足 P1 最小性要求。

复核人建议：将 key_text 缩短为“将一个 PT 分配给多个系统器官分类”，evidence_span 保持不变。

人工裁决：待处理。

## pc-0038 / PV / slices, key_text

问题：MedDRA《数据检索和展示：考虑要点》多久更新一次？

当前锚点：每年更新一次

原文位置：meddra-data-retrieval-ptc-3-26-zh-hans，物理页 4，SECTION 1 – 引言。

复核理由：key_text“每年更新一次”仅保留更新频次，未保留更新对象，不符合 P1 要求。按 dose_unit 定义中“或频次表达”的字面口径，完整 evidence_span 中的“每年更新一次”也应计入该标签，现有切片遗漏 dose_unit。

复核人建议：将 key_text 改为“本《数据检索和展示:考虑要点》(DRP:PTC)文档是 ICH 认可的 MedDRA 用户指南,每年更新一次”；补充 dose_unit 标签。若 dose_unit 仅拟涵盖给药频次，须先明确收窄标签定义。

人工裁决：待处理。

## pc-0039 / PV / query

问题：在特定 HLT 或 HLGT 中检索多轴性 PT 时，能否假定该 PT 会显示在其次 SOC 路径中？

当前锚点：不要假定 PT 会显示在其次 SOC 路径中

原文位置：meddra-data-retrieval-ptc-3-26-zh-hans，物理页 9，2.4 机构自身数据的特点。

复核理由：query 将原文“不要假定 PT 会显示在其次 SOC 路径中”直接改为“能否假定该 PT 会显示在其次 SOC 路径中”，虽符合 PV 语境，但属于将 key_text 原句改成问句。

复核人建议：建议改为：我们准备按 HLT/HLGT 导出多轴性 PT 的数据，核对次 SOC 分支的结果时，需要留意数据库的什么限制？

人工裁决：待处理。

## pc-0041 / PV / key_text

问题：按照 GVP Module VI，一份有效的 ICSR 至少需要包含哪些要素？

当前锚点：A valid ICSR should include

原文位置：ema-gvp-module-vi-rev2，物理页 9，VI.A.1.7. Individual case safety report (ICSR)。

复核理由：key_text 虽为页内唯一的逐字原文，但仅含对象及引导语，未保留有效 ICSR 所需的具体要素和最低数量约束，不满足 P1 要求的对象与约束同时保留。

复核人建议：将 key_text 改为“valid ICSR should include at least one identifiable reporter, one single identifiable patient, at least one suspect adverse reaction, and at least one suspect medicinal product”。

人工裁决：待处理。

## pc-0042 / PV / key_text

问题：按照 GVP Module VI，已按严重个案提交的 ICSR 因本次随访改判为非严重，这次随访信息仍应在多少天内提交？

当前锚点：should still be submitted within 15 days

原文位置：ema-gvp-module-vi-rev2，物理页 22，VI.B.7.1. Submission time frames of ICSRs。

复核理由：key_text 仅保留提交要求与时限，未保留提交对象及由严重改判为非严重的适用条件，不符合 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为页内原文：Where a case initially sent as serious becomes non-serious based on new follow-up information, this information should still be submitted within 15 days

人工裁决：待处理。

## pc-0043 / PV / key_text

问题：按照 GVP Module VI，对于需在欧盟提交的非严重有效 ICSR，成员国主管机构或上市许可持有人应在收到报告后多少天内提交？

当前锚点：within 90 days from the date of receipt

原文位置：ema-gvp-module-vi-rev2，物理页 41，VI.C.3. Submission time frames of ICSRs in EU。

复核理由：key_text 虽为页内唯一的逐字原文，但仅保留提交时限及起算点，未保留对象“non-serious valid ICSRs”及提交行为，不符合 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为从“non-serious valid ICSRs”至“within 90 days from the date of receipt of the reports”的连续原文，以同时保留对象、提交要求、时限及起算点。

人工裁决：待处理。

## pc-0046 / PV / slices, key_text

问题：按照 GVP Module IX，欧盟上市许可持有人确认某个经验证的信号或其他来源的安全问题符合 emerging safety issue 定义后，最迟多久应通知有关监管机构？

当前锚点：no later than 3 working days

原文位置：ema-gvp-module-ix-rev1，物理页 12，IX.C.2. Emerging safety issues。

复核理由：slices 缺少 negation：完整 evidence_span 中的“no later than 3 working days”限定通知不得晚于该时限，命中必须保留这一限制语义。key_text 虽为页内唯一的逐字原文，但仅保留时限，未保留 emerging safety issue 这一对象，不符合 P1 同时保留对象与约束的要求。

复核人建议：补充 negation 标签；将 key_text 扩为“no later than 3 working days after establishing that a validated signal or a safety issue from any source meets the definition of an emerging safety issue”，保留对象、时限及计时起点。

人工裁决：待处理。

## pc-0047 / PV / key_text

问题：按照 GVP Module IX，信号确认是否等同于对信号的完整评估？

当前锚点：not intended to be a full assessment

原文位置：ema-gvp-module-ix-rev1，物理页 6，IX.A.1.2. Terminology specific to the EU signal management process with oversight of the Pharmacovigilance Risk Assessment Committee (PRAC)。

复核理由：key_text 虽为页内唯一的逐字原文，但未保留受约束对象“Signal confirmation”，不符合 P1 要求同时保留对象与约束的口径。

复核人建议：将 key_text 改为“Signal confirmation is not intended to be a full assessment”。

人工裁决：待处理。

## pc-0048 / PV / slices, key_text

问题：按照 FDA 的 IND 安全报告要求，申办方首次收到未预期的致死或危及生命的可疑不良反应信息后，最迟多久必须通知 FDA？

当前锚点：in no case later than 7 calendar days

原文位置：fda-sponsor-safety-reporting-2025，物理页 12，IV. OVERVIEW OF IND SAFETY REPORTING REQUIREMENTS。

复核理由：slices 缺少 negation：完整 evidence_span 中的“in no case later than 7 calendar days”含不得超过期限的限制语义。key_text 虽为页内唯一的逐字原文，但仅保留期限约束，缺少申办方向 FDA 通知这一对象与行为，不符合 P1。

复核人建议：slices 增加 negation；key_text 建议改为“the sponsor must notify FDA as soon as possible but in no case later than 7 calendar days after the sponsor’s initial receipt of the information”，以保留通知对象、期限及起算条件。

人工裁决：待处理。

## pc-0050 / PV / slices

问题：21 CFR 312.32 中，哪两条 IND 安全报告条款要求评估汇总数据？

当前锚点：§ 312.32(c)(1)(i)(C) and (c)(1)(iv)

原文位置：fda-sponsor-safety-reporting-2025，物理页 5，I. INTRODUCTION。

复核理由：protocol_id 标签不成立：query 中的“21 CFR 312.32”是法规条款编号，不属于切片定义中的方案编号、注册号、SOP 编号或版本号。mixed_zh_en 标签成立。

复核人建议：删除 protocol_id 标签，slices 改为 ["mixed_zh_en"]。

人工裁决：待处理。

## pc-0051 / PV / key_text

问题：按照 ICH E2A，不良事件的定义是否要求与治疗存在因果关系？

当前锚点：does not necessarily have to have a causal relationship

原文位置：ich-e2a-step4-1994，物理页 4，II.A.1. Adverse Event (or Adverse Experience)。

复核理由：key_text 不满足最小性：开头的“does”可删除，不影响因果关系这一对象及不必存在该关系的约束含义；缩短后的文本仍在页内唯一出现。

复核人建议：将 key_text 缩短为“not necessarily have to have a causal relationship”。

人工裁决：待处理。

## pc-0052 / PV / key_text

问题：按照 ICH E2A，side effect 能否作为 adverse event 或 adverse reaction 的同义词？

当前锚点：should not be regarded as synonymous

原文位置：ich-e2a-step4-1994，物理页 4，II.A.2. Adverse Drug Reaction (ADR)。

复核理由：key_text 虽为页内唯一的逐字原文，但仅保留否定判断，未保留同义关系的对象，不符合 P1 要求的同时保留对象与约束。

复核人建议：将 key_text 扩展为“should not be regarded as synonymous with adverse event or adverse reaction”。

人工裁决：待处理。

## pc-0053 / PV / slices, key_text

问题：按照 ICH E2A，申办方首次获知临床研究病例符合致死或危及生命的未预期不良反应快速报告条件后，最迟多久应首次通知监管机构？

当前锚点：no later than 7 calendar days

原文位置：ich-e2a-step4-1994，物理页 7，III.B.1. Fatal or Life-Threatening Unexpected ADRs。

复核理由：slices 缺少 negation：完整 evidence_span 中的“no later than 7 calendar days”明确限制最迟通知时间，命中必须保留该限制语义。key_text 仅保留时限约束，未保留通知监管机构这一对象与行为，不符合 P1。

复核人建议：增加 negation 标签；将 key_text 改为页内连续原文“Regulatory agencies should be notified (e.g., by telephone, facsimile transmission, or in writing) as soon as possible but no later than 7 calendar days after first knowledge by the sponsor that a case qualifies”。

人工裁决：待处理。

## pc-0054 / PV / slices, key_text

问题：按照 ICH E2F，同步 DSUR 与 PSUR 的数据锁定点时，下一份 DSUR 最多可以覆盖多长时间？

当前锚点：no longer than one year

原文位置：ich-e2f-step4-2010，物理页 8，2.2 Periodicity and DSUR Data Lock Point。

复核理由：slices 漏标 negation：完整 evidence_span 中的“should be no longer than one year”明确限制覆盖时长。key_text 虽为页内唯一的逐字原文，但“no longer than one year”未保留受约束对象，不符合 P1 要求。

复核人建议：slices 增加 negation；key_text 改为“period covered by the next DSUR should be no longer than one year”。

人工裁决：待处理。

## pc-0055 / PV / slices, key_text

问题：按照 ICH E2F，DSUR 最迟应在数据锁定点后多少个日历日内提交给监管机构？

当前锚点：no later than 60 calendar days

原文位置：ich-e2f-step4-2010，物理页 8，2.2 Periodicity and DSUR Data Lock Point。

复核理由：slices 缺少 negation：完整 evidence_span 中的“no later than”表示不得晚于指定期限，命中必须保留该限制语义。key_text 虽为页内唯一的逐字原文，但“no later than 60 calendar days”未保留 DSUR 提交这一对象及期限起算点，不满足 P1 的对象与约束要求。

复核人建议：slices 增加 negation；key_text 改为“The DSUR should be submitted to all concer ned regulatory authorities no later than 60 calendar days after the DSUR data lock point”。

人工裁决：待处理。

## pc-0056 / PV / key_text

问题：按照 ICH E2F，DSUR 可以用于首次通报重大新安全信息吗？

当前锚点：should not be used to provide the initial notification

原文位置：ich-e2f-step4-2010，物理页 6，1.2 Objectives。

复核理由：key_text 虽为页内唯一的逐字原文，但省略了适用对象 DSUR 及首次通报所针对的“significant new safety info rmation”，未满足 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为“DSUR; however, it should not be used to provide the initial notification of significant new safety info rmation”。

人工裁决：待处理。

## pc-0057 / PV / key_text

问题：填寫藥品不良反應通報表時，用來治療或緩解不良反應的藥品，要填進「可疑藥品」欄位嗎？

当前锚点：不應列入可疑藥品通報

原文位置：tfda-adr-report-form-guide-4th，物理页 15，6.1 可疑藥品（必填）。

复核理由：key_text 虽为页内唯一的逐字原文，但未保留限制所针对的对象「用以治療或緩解藥品不良反應之藥品」，不能独立保留该条款的对象与约束，不符合 P1。

复核人建议：将 key_text 改为「用以治療或緩解藥品不良反應之藥品不應列入可疑藥品通報」。

人工裁决：待处理。

## pc-0060 / CO / slices, key_text

问题：ICH E8(R1) 对研究程序和评估的科学必要性及受试者负担有什么要求？

当前锚点：do not place undue burden

原文位置：ich-e8-r1-step4-2021，物理页 8，2.1 Protection of Clinical Study Participants。

复核理由：query 依赖 ICH E8(R1) 的编号及修订版本精确检索，缺少 protocol_id 标签。key_text 虽为页内唯一的逐字原文，但“do not place undue burden”未保留负担所作用的对象，不符合 P1 同时保留对象与约束的要求。evidence_span 条款完整，偏移与文本一致。

复核人建议：补充 protocol_id 标签；将 key_text 改为“do not place undue burden on study participants”。

人工裁决：待处理。

## pc-0061 / CO / slices, key_text

问题：按照 ICH E8(R1)，回顾性开展的文件和数据审查、监查，即使结合稽查，是否足以保证临床研究质量？

当前锚点：not sufficient to ensure quality

原文位置：ich-e8-r1-step4-2021，物理页 9，3.1 Quality by Design of Clinical Studies。

复核理由：query 明确限定 ICH E8(R1)，检索依赖指南版本号，按版本号的切片定义应补充 protocol_id。key_text 中的“not sufficient to ensure quality”未保留质量所属对象“a clinical study”，不满足 P1 同时保留对象与约束的要求。

复核人建议：slices 增加 protocol_id；key_text 改为页内唯一的逐字原文“not sufficient to ensure quality of a clinical study”。

人工裁决：待处理。

## pc-0062 / CO / slices, key_text

问题：按照 ICH E8(R1)，关键质量因素（critical to quality factors）应避免混入哪类事项？

当前锚点：should not be cluttered with minor issues

原文位置：ich-e8-r1-step4-2021，物理页 11，3.2 Critical to Quality Factors。

复核理由：query 依赖 ICH E8(R1) 的版本标识定位指南，按版本号精确匹配口径应补充 protocol_id。key_text 虽为页内唯一的逐字原文，但未保留约束对象 critical to quality factors，不符合 P1 同时保留对象与约束的要求。

复核人建议：slices 补充 protocol_id；key_text 改为页内连续原文“critical to quality factors should be clear and should not be cluttered with minor issues”。

人工裁决：待处理。

## pc-0064 / CO / slices

问题：按照 ICH E8(R1)，quality by design 要把质量主动设计进研究的哪些部分？

当前锚点：study protocol and processes

原文位置：ich-e8-r1-step4-2021，物理页 8，2.2 Scientific Approach in Clinical Study Design, Planning, Conduct, Analysis, and Reporting。

复核理由：query 明确以 ICH E8(R1) 限定指南及修订版本，检索依赖该版本标识的精确匹配，缺少 protocol_id 标签。

复核人建议：将 slices 修改为 ["protocol_id", "mixed_zh_en"]。

人工裁决：待处理。

## pc-0065 / CO / query, slices, key_text

问题：按照 ICH E6(R3) 的 GCP 原则，申办方能否给受试者和研究者增加不必要的负担？

当前锚点：should not place unnecessary burden

原文位置：ich-e6-r3-step4-2025，物理页 13，II. PRINCIPLES OF ICH GCP / 7.4。

复核理由：query 基本将原文条款翻译后改成“能否”问句，缺少独立的业务提问情境。query 明确依赖 ICH E6(R3) 的版本匹配，缺少 protocol_id 标签。key_text 虽为页内唯一原文，但未保留承担义务的申办方及负担涉及的受试者和研究者，不满足 P1 保留对象与约束的要求。evidence_span 为完整条款，偏移正确；CO 归属符合临床试验质量管理用途。

复核人建议：将 query 改为具体业务情境，例如“我们正在按 ICH E6(R3) 审查研究流程，发现有些安排只会增加受试者和研究者的工作量，没有必要保留；申办方应依据哪项原则处理？”补充 protocol_id 标签；key_text 改为“sponsor should not place unnecessary burden on participants and investigators”。

人工裁决：待处理。

## pc-0066 / CO / slices, key_text

问题：按照 ICH E6(R3)，合理报销受试者实际发生的交通和住宿等费用，是否属于胁迫？

当前锚点：is not coercive

原文位置：ich-e6-r3-step4-2025，物理页 16，III. ANNEX 1 / 1.2 Responsibilities / 1.2.8。

复核理由：query 明确依赖 ICH E6(R3) 的版本标识，缺少 protocol_id 标签。key_text“is not coercive”仅保留判断，未保留报销对象及合理性限定，不符合 P1 要求。

复核人建议：补充 protocol_id 标签；将 key_text 改为“Reasonable r eimbursement of expenses incurred by participants, such as for travel and lodging, is not coercive”，保留页文本中的原始空格。

人工裁决：待处理。

## pc-0067 / CO / slices

问题：按照 ICH E6(R3)，必要记录应由哪些主体安全保存，保存期限依据什么确定？

当前锚点：retained securely by sponsors and investigators

原文位置：ich-e6-r3-step4-2025，物理页 13，II. PRINCIPLES OF ICH GCP / 9.5。

复核理由：query 明确以 ICH E6(R3) 限定所依据的指南版本，召回依赖该版本标识的精确匹配，按版本号归入 protocol_id 的定义，现有 slices 漏标 protocol_id。

复核人建议：将 slices 改为 ["protocol_id", "mixed_zh_en"]。

人工裁决：待处理。

## pc-0068 / CO / key_text

问题：ICH E6(R3) 与 ICH E8(R1) 是什么关系？

当前锚点：outlined in ICH E8 (R1) General Considerations for Clinical Studies

原文位置：ich-e6-r3-step4-2025，物理页 8，I. INTRODUCTION。

复核理由：key_text 虽为页内唯一原文，但未保留回答两份指南关系的“builds on”表述，且包含可省略的指南全名；存在更短、同时保留对象与关系的连续原文。

复核人建议：将 key_text 改为“This guideline builds on key conce pts outlined in ICH E8 (R1)”，其余保持不变。

人工裁决：待处理。

## pc-0069 / CO / slices, key_text

问题：按照 ICH E6(R3)，试验用药品应依据哪些文件使用？

当前锚点：the protocol and relevant trial documents

原文位置：ich-e6-r3-step4-2025，物理页 14，II. PRINCIPLES OF ICH GCP / 11.3。

复核理由：query 明确以 ICH E6(R3) 限定指南版本，按版本号精确匹配的定义应补充 protocol_id。key_text 可删除开头的“the ”，缩为“protocol and relevant trial documents”，仍保留所问文件范围且在页内唯一。evidence_span 完整回答问题，偏移与文本一致。

复核人建议：slices 改为 ["protocol_id","mixed_zh_en"]；key_text 改为“protocol and relevant trial documents”。

人工裁决：待处理。

## pc-0070 / CO / slices

问题：ICH E6(R3) 对 IRB/IEC 应保留的相关记录列举了哪些例子？

当前锚点：retain all relevant records

原文位置：ich-e6-r3-step4-2025，物理页 18，III. ANNEX 1 / 1.5 Records / 1.5.1。

复核理由：缺少 protocol_id 标签：query 明确以 ICH E6(R3) 限定所问指南及版本，检索依赖 E6(R3) 的精确匹配，符合版本号标签定义。

复核人建议：将 slices 改为 ["protocol_id", "mixed_zh_en"]。

人工裁决：待处理。

## pc-0071 / CO / key_text

问题：FDA 2024 年《方案偏离》指南草案如何定义 important protocol deviation？

当前锚点：might significantly affect the completeness

原文位置：fda-protocol-deviations-draft-2024，物理页 7，III.A.1. Important Protocol Deviations。

复核理由：key_text 虽为页内唯一的逐字原文，但“might significantly affect the completeness”未保留被定义的对象，也未说明完整性所指对象，不能保留该定义的对象与约束，不符合 P1。

复核人建议：将 key_text 改为“important protocol deviation is a subset of protocol 118 deviations that might significantly affect the completeness, accuracy, and/or reliability of the 119 study data or that might significantly affect a subject’s rights, safety, or well-being”。

人工裁决：待处理。

## pc-0072 / CO / key_text

问题：FDA 2024 年《方案偏离》指南草案采用了 ICH E3(R1) 的哪些定义？

当前锚点：adopting the ICH E3(R1)

原文位置：fda-protocol-deviations-draft-2024，物理页 5，II. BACKGROUND。

复核理由：key_text 虽为页内唯一的逐字片段，但截断在来源名称处，未保留采用的对象，即 protocol deviation 和 important protocol deviation 的定义，不符合 P1 同时保留对象与约束的要求。

复核人建议：将 key_text 改为“adopting the ICH E3(R1) 62 definitions of protocol deviation and important protocol deviation”。

人工裁决：待处理。

## pc-0073 / CO / slices, key_text, evidence_span

问题：按照 FDA 2024 年《方案偏离》指南草案，医疗器械研究为紧急保护受试者生命或身体健康而偏离研究计划时，研究者最迟应在紧急情况发生后几个工作日内通知申办方和 IRB？

当前锚点：no later than 5 working days

原文位置：fda-protocol-deviations-draft-2024，物理页 9，III.B.1. Role of the Investigator in Monitoring, Mitigating, and Reporting Protocol Deviations。

复核理由：slices 缺少 negation：完整证据含“no later than 5 working days”的时限限制及“Except in such an emergency”的例外限制。key_text 虽为页内唯一原文，但仅保留期限，未保留通知对象、通知行为及紧急情况这一适用条件，不符合 P1。evidence_span 还纳入了非紧急情况下变更或偏离计划的事先审批条款，超出回答本题所需范围。

复核人建议：将 evidence_span 收至首句末尾“812.150(a)(4)).”，删除后续非紧急情况审批条款并更新偏移；将 key_text 扩展为保留医疗器械研究、紧急偏离通知义务及期限的连续原文；补充 negation 标签。

人工裁决：待处理。

## pc-0074 / CO / key_text

问题：按照 FDA 2024 年《方案偏离》指南草案，未被归类为 important 且不对受试者构成明显即时危险的方案偏离，需要立即报告给 IRB 吗？

当前锚点：do not need to be immediately reported

原文位置：fda-protocol-deviations-draft-2024，物理页 13，III.B.3. Role of the IRB in Evaluating Protocol Deviations。

复核理由：key_text 虽为页内唯一的逐字原文，但仅保留报告义务的谓语，未保留方案偏离这一对象及其分类、即时危险限定，不符合 P1 的对象与约束保留要求。

复核人建议：将 key_text 改为：protocol deviations that are not classified as important and do not present an apparent 355 immediate hazard to participants do not need to be immediately reported to the IRB

人工裁决：待处理。

## pc-0075 / CO / key_text

问题：根据 FDA 2024 年《方案偏离》指南草案的说明，FDA 法规是否给 protocol deviation 下了定义？

当前锚点：do not include a definition

原文位置：fda-protocol-deviations-draft-2024，物理页 4，I. INTRODUCTION。

复核理由：key_text 虽为页内唯一的逐字原文，但“do not include a definition”未保留法规主体及被定义对象，不能同时保留对象与约束的命中含义，不符合 P1。

复核人建议：将 key_text 改为“FDA regulations do not include a definition of the term protocol 17 deviation”，保留页文本中的行号 17。

人工裁决：待处理。
