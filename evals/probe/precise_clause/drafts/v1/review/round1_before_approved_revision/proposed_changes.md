# 正式复核后的具体修订提案（待人工裁决）

本文件对应 proposed_changes.json，未覆盖样本，未写人工签字，未触发重审。
当前已收到的争议逐项如下；复核是否全部完成见 [复核状态](formal_review_status.md)。

涉及 47 条；字段修改次数：{'key_text': 36, 'slices': 22, 'language': 1, 'evidence_span': 2, 'query': 2}。候选机械检查错误：0。

建议：按 P1 补足或缩短锚点，按 P2 补标签；pc-0039/0065 使用简短自然问法；pc-0025/0073 收窄 span。
pc-0026/0027 的 span 不扩展沿用既有人工决定，不要求重复确认；pc-0026 新的锚点扩展仍列作新提案。
pc-0053/0071 的原复核建议超过 200 字符，提案已改成更短的连续原文。
pc-0038 给年度文档更新加 dose_unit 的建议需人工明确：这里按当前“频次表达”的字面口径列出，不能自行收窄规范。

## pc-0003

**key_text**

原：不建議開始使用

拟改：大於80歲之老年患者不建議開始使用

## pc-0006

**slices**

原：protocol_id, dose_unit

拟改：protocol_id, dose_unit, mixed_zh_en

**language**

原：zh

拟改：mixed

## pc-0008

**key_text**

原：每一劑量300mg;每天800mg

拟改：一般成人處方限量:每一劑量300mg;每天800mg

## pc-0011

**key_text**

原：不得超過300 mg

拟改：單一劑量,都必須不得超過300 mg

## pc-0012

**slices**

原：protocol_id

拟改：protocol_id, negation

## pc-0015

**key_text**

原：改用每次 25mg

拟改：其起始劑量需考慮改用每次 25mg

## pc-0016

**key_text**

原：合併使用本品及含 aliskiren 成分藥品於糖尿病患

拟改：禁忌症:合併使用本品及含 aliskiren 成分藥品於糖尿病患

## pc-0023

**slices**

原：dose_unit, drug_name_zh, mixed_zh_en

拟改：dose_unit, drug_name_zh, mixed_zh_en, negation

## pc-0024

**key_text**

原：心壓暢錠 100 毫克(美托普洛)

拟改：心壓暢錠 100 毫克

## pc-0025

**slices**

原：negation, drug_name_zh, time_window

拟改：negation, drug_name_zh

**evidence_span**

原：本錠劑應整粒以液體吞服,不可嚼破或壓破本錠劑。對於有吞嚥困難的病人,可將藥錠置入半杯非碳酸類的水中,且不可使用他種液體,因為藥錠的腸衣膜可能因此溶解。同時攪拌直到藥錠崩散,並立即或在 30 分鐘之內將水連同小藥球喝下。再將半杯水加入杯中沖洗並喝下,小藥球不可咬碎或壓碎。本品不適用於胃管給藥。

拟改：本錠劑應整粒以液體吞服,不可嚼破或壓破本錠劑。

## pc-0026

**key_text**

原：30 分鐘之內

拟改：立即或在 30 分鐘之內將水連同小藥球喝下

span 扩展建议与已批准的 MA 试跑逐条处理重复：沿用不扩展的既有裁决，见人工确认记录及试跑表；不把该裁决扩展到其他新问题。

## pc-0027

样本不改，沿用已有人工裁决。

span 扩展建议与已批准的 MA 试跑逐条处理重复：沿用不扩展的既有裁决，见人工确认记录及试跑表；不把该裁决扩展到其他新问题。

## pc-0029

**key_text**

原：不可超過 20 mg

拟改：此類病人的esomeprazole 最高劑量不可超過 20 mg

## pc-0031

**key_text**

原：不应更改

拟改：术语层级结构,不应更改

## pc-0036

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, dose_unit, negation

## pc-0037

**key_text**

原：将一个 PT 分配给多个系统器官分类 [SOC]

拟改：将一个 PT 分配给多个系统器官分类

## pc-0038

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, dose_unit

**key_text**

原：每年更新一次

拟改：本《数据检索和展示:考虑要点》(DRP:PTC)文档是 ICH 认可的 MedDRA 用户指南,每年更新一次

复核人按频次表达的字面口径建议给文档年度更新加 dose_unit；请人工明确接受或拒绝。

## pc-0039

**query**

原：在特定 HLT 或 HLGT 中检索多轴性 PT 时，能否假定该 PT 会显示在其次 SOC 路径中？

拟改：按 HLT 或 HLGT 导出多轴性 PT 数据时，次 SOC 分支缺失可能与什么数据库限制有关？

使用简短自然的替代问题，不添加复核人建议的长场景。

## pc-0041

**key_text**

原：A valid ICSR should include

拟改：valid ICSR should include at least one identifiable reporter, one single identifiable patient, at least one suspect adverse reaction, and at least one suspect medicinal product

## pc-0042

**key_text**

原：should still be submitted within 15 days

拟改：Where a case initially sent as serious becomes non-serious based on new follow-up information, this information should still be submitted within 15 days

## pc-0043

**key_text**

原：within 90 days from the date of receipt

拟改：non-serious valid ICSRs shall be submitted by the competent authority in a Member State or by the marketing authorisation holder within 90 days from the date of receipt of the reports

## pc-0046

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, negation

**key_text**

原：no later than 3 working days

拟改：no later than 3 working days after establishing that a validated signal or a safety issue from any source meets the definition of an emerging safety issue

## pc-0047

**key_text**

原：not intended to be a full assessment

拟改：Signal confirmation is not intended to be a full assessment

## pc-0048

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, negation

**key_text**

原：in no case later than 7 calendar days

拟改：the sponsor must notify FDA as soon as possible but in no case later than 7 calendar days after the sponsor’s initial receipt of the information

## pc-0050

**slices**

原：protocol_id, mixed_zh_en

拟改：mixed_zh_en

按现有定义移除法规条款编号的 protocol_id；这也恢复了 PV 原始人工编辑中的标签选择。其他样本仍满足编号切片数量门槛。

## pc-0051

**key_text**

原：does not necessarily have to have a causal relationship

拟改：not necessarily have to have a causal relationship

## pc-0052

**key_text**

原：should not be regarded as synonymous

拟改：should not be regarded as synonymous with adverse event or adverse reaction

## pc-0053

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, negation

**key_text**

原：no later than 7 calendar days

拟改：Regulatory agencies should be notified (e.g., by telephone, facsimile transmission, or in writing) as soon as possible but no later than 7 calendar days

复核人原建议超过 key_text 的 200 字符上限；改为保留对象与数据完整性约束的连续锚点，完整定义仍在 span。

## pc-0054

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, negation

**key_text**

原：no longer than one year

拟改：period covered by the next DSUR should be no longer than one year

## pc-0055

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, negation

**key_text**

原：no later than 60 calendar days

拟改：The DSUR should be submitted to all concer ned regulatory authorities no later than 60 calendar days after the DSUR data lock point

## pc-0056

**key_text**

原：should not be used to provide the initial notification

拟改：DSUR; however, it should not be used to provide the initial notification of significant new safety info rmation

## pc-0057

**key_text**

原：不應列入可疑藥品通報

拟改：用以治療或緩解藥品不良反應之藥品不應列入可疑藥品通報

## pc-0060

**slices**

原：negation, mixed_zh_en

拟改：negation, mixed_zh_en, protocol_id

**key_text**

原：do not place undue burden

拟改：do not place undue burden on study participants

## pc-0061

**slices**

原：negation, mixed_zh_en

拟改：negation, mixed_zh_en, protocol_id

**key_text**

原：not sufficient to ensure quality

拟改：not sufficient to ensure quality of a clinical study

## pc-0062

**slices**

原：negation, mixed_zh_en

拟改：negation, mixed_zh_en, protocol_id

**key_text**

原：should not be cluttered with minor issues

拟改：critical to quality factors should be clear and should not be cluttered with minor issues

## pc-0064

**slices**

原：mixed_zh_en

拟改：mixed_zh_en, protocol_id

## pc-0065

**query**

原：按照 ICH E6(R3) 的 GCP 原则，申办方能否给受试者和研究者增加不必要的负担？

拟改：按 ICH E6(R3) 设计研究流程时，申办方应如何控制受试者和研究者的额外负担？

**slices**

原：negation, mixed_zh_en

拟改：negation, mixed_zh_en, protocol_id

**key_text**

原：should not place unnecessary burden

拟改：sponsor should not place unnecessary burden on participants and investigators

使用简短自然的替代问题，不添加复核人建议的长场景。

## pc-0066

**slices**

原：negation, mixed_zh_en

拟改：negation, mixed_zh_en, protocol_id

**key_text**

原：is not coercive

拟改：Reasonable r eimbursement of expenses incurred by participants, such as for travel and lodging, is not coercive

## pc-0067

**slices**

原：mixed_zh_en

拟改：mixed_zh_en, protocol_id

## pc-0068

**key_text**

原：outlined in ICH E8 (R1) General Considerations for Clinical Studies

拟改：This guideline builds on key conce pts outlined in ICH E8 (R1)

## pc-0069

**slices**

原：mixed_zh_en

拟改：mixed_zh_en, protocol_id

**key_text**

原：the protocol and relevant trial documents

拟改：protocol and relevant trial documents

## pc-0070

**slices**

原：mixed_zh_en

拟改：mixed_zh_en, protocol_id

## pc-0071

**key_text**

原：might significantly affect the completeness

拟改：important protocol deviation is a subset of protocol 118 deviations that might significantly affect the completeness, accuracy, and/or reliability of the 119 study data

复核人原建议超过 key_text 的 200 字符上限；改为保留对象与数据完整性约束的连续锚点，完整定义仍在 span。

## pc-0072

**key_text**

原：adopting the ICH E3(R1)

拟改：adopting the ICH E3(R1) 62 definitions of protocol deviation and important protocol deviation

## pc-0073

**slices**

原：time_window, mixed_zh_en

拟改：time_window, mixed_zh_en, negation

**key_text**

原：no later than 5 working days

拟改：any deviation from the 210 investigational plan to protect the life or physical well-being of a subject in an emergency as 211 soon as possible but no later than 5 working days

**evidence_span**

原：Similarly, for device investigations, investigators must keep records of each protocol deviation 209 (21 CFR 812.140(a)(4)) and must notify the sponsor and the IRB of any deviation from the 210 investigational plan to protect the life or physical well-being of a subject in an emergency as 211 soon as possible but no later than 5 working days after the emergency occurred (21 CFR 212 812.150(a)(4)). Except in such an emergency, investigators must get prior sponsor approval for 213 changes in or deviations from a plan, and if these changes or deviations may affect the scientific 214 soundness of the plan or the rights, safety, or welfare of human participants, prior FDA and IRB 215 approval is also required (21 CFR 812.150(a)(4)).

拟改：Similarly, for device investigations, investigators must keep records of each protocol deviation 209 (21 CFR 812.140(a)(4)) and must notify the sponsor and the IRB of any deviation from the 210 investigational plan to protect the life or physical well-being of a subject in an emergency as 211 soon as possible but no later than 5 working days after the emergency occurred (21 CFR 212 812.150(a)(4)).

## pc-0074

**key_text**

原：do not need to be immediately reported

拟改：protocol deviations that are not classified as important and do not present an apparent 355 immediate hazard to participants do not need to be immediately reported to the IRB

## pc-0075

**key_text**

原：do not include a definition

拟改：FDA regulations do not include a definition of the term protocol 17 deviation
