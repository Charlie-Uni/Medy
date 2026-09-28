# 主集第二次人工复核优先清单（2026-09-26，记录 93 §B）

来源：记录 92 的归因诊断与记录 93 的逐条复核。请复核人对每行在「结论」列填：`标注改`（说明改法：扩 gold 到哪些分块 / 改 key_text）、`标注对`（系统确实错）或 `待定`。分块 id 见 `evals/replay/replay-v1/items.jsonl` 与主集运行 `evals/harness/runs/2026-09-23-full-ask-v2/rows.jsonl`。

## 一、被引分块逐字包含标注 key_text 的「错引」题（14 道，机械核对；逐一核对后全部是**另一份文档**含相同句子——同成分他牌仿單、共用段落的姊妹指南、ICH 原版与 FDA 转载。请确认规则：点名产品 / 文件的问题必须引用该文档）

| 回放 id | 主集 id | 部门 | 问题 | 结论 |
| --- | --- | --- | --- | --- |
| rp-0053 | ms-0056 | MA | 停止使用拔痛酸錠（Allopurinol）治療後，血清尿酸濃度通常多久會回復到治療前的數值？ | 标注对：点名拔痛酸錠，须引用该品种仿單；他牌同句不能替代。 |
| rp-0236 | ms-0241 | PV | 依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reasonable possi | 标注改：问题点名法规条款，未点名 FDA 研究者指南；可接受同版本条款原文，或改写问题明确指定研究者指南。 |
| rp-0237 | ms-0242 | PV | According to the examples provided under § 312.32(c)(1)(i) for IND saf | 标注改：只点名法规条款，未点名 FDA 研究者指南；扩等价来源或把指南名称写入问题。 |
| rp-0275 | ms-0280 | PV | 使用 MedDRA 时,能否对术语的层级结构进行临时改动,比如变更某个 PT 的主 SOC 分配? | 标注改：仅称 MedDRA，未指定“数据检索和展示”指南；扩等价来源或补指南全名。 |
| rp-0293 | ms-0298 | CO | 根据ICH E6(R3),在什么情况下可以不经IRB/IEC事先书面批准就对已批准的试验方案进行偏离或变更? | 标注改：问题点名 ICH E6(R3)，gold 却定在 FDA 转载；应纳入 ICH 原版或明确问 FDA 版。 |
| rp-0294 | ms-0299 | CO | 根据ICH E6(R3),研究者或研究机构工作人员是否可以对受试者施压以促使其继续参与临床试验? | 标注改：问题点名 ICH E6(R3)，gold 却定在 FDA 转载；应纳入 ICH 原版或明确问 FDA 版。 |
| rp-0325 | ms-0336 | CO | 根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？ | 标注改：问题点名 21 CFR 312.50，未点名 FDA 风险监查指南；扩等价法规来源或改写指向该指南。 |
| rp-0518 | pc-0011 | MA | 痛風停錠單次劑量的上限是多少 | 标注对：点名痛風停錠，须引用该品种仿單。 |
| rp-0524 | pc-0017 | MA | 糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎 | 标注改：未点名穩壓或具体药品，不能只认其仿單；补产品名或扩同内容有效来源。 |
| rp-0533 | pc-0026 | MA | 胃所樂泡在水裡崩散後要在多久之內喝完 | 标注对：点名胃所樂，须引用该品种仿單。 |
| rp-0535 | pc-0028 | MA | esomeprazole 可以和 nelfinavir 一起服用嗎 | 标注改：只问 esomeprazole 成分，未点名胃所樂；补品牌或接受其他同成分仿單的相同禁忌。 |
| rp-0558 | pc-0051 | PV | 按照 ICH E2A，不良事件的定义是否要求与治疗存在因果关系？ | 标注对：明确问 ICH E2A，应引用该指南而非转载定义。 |
| rp-0577 | pc-0070 | CO | ICH E6(R3) 对 IRB/IEC 应保留的相关记录列举了哪些例子？ | 标注对：明确问 ICH E6(R3)，应引用 ICH 原件。 |
| rp-0609 | pc-0102 | CO | What examples of relevant records does ICH E6(R3) list that the IRB/IE | 标注对：明确问 ICH E6(R3)，应引用 ICH 原件。 |

## 二、gold 已在前 8 却失败的 18 道（含上表中的 6 道）

| 回放 id | 主集 id | 部门 | 原标签 | 我的归类 | 问题 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| rp-0012 | ms-0012 | MA | answerable_false_abstention | 裁判过严（问题限定 CrCl<30，答 400 mg 正确） | 需要血液透析且creatinine清除率低於30 ml/min/1.73m2的病人，使用信諾隆（Ciprofloxaci | 标注改：回放失败标签为裁判误判；问题限定 CrCl<30，400 mg 答案适用，主集 gold 不改。 |
| rp-0033 | ms-0036 | MA | answerable_false_abstention | 模型误弃答：禁忌句即答案 | 「安星」伊風柔錠300毫克可以用於治療急性痛風性關節炎發作嗎？ | 标注对：仿單禁忌直接回答可否使用，模型弃答错误。 |
| rp-0046 | ms-0049 | MA | answerable_false_abstention | 校验规则：唯一陈述被丢弃（首轮判词未保留） | Losacar用於治療第II型糖尿病腎病變時，起始劑量為何，並可視血壓下降情形增加至多少？ | 标注对：起始剂量与加量证据已在前 8，唯一陈述被校验流程丢弃；修校验规则。 |
| rp-0053 | ms-0056 | MA | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | 停止使用拔痛酸錠（Allopurinol）治療後，血清尿酸濃度通常多久會回復到治療前的數值？ | 标注对：点名拔痛酸錠，须引用该品种仿單；他牌同句不能替代。 |
| rp-0121 | ms-0124 | PV | answerable_false_abstention | 分块截断：三级定义分在两块 | 根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、maj | 标注改：三级定义跨 4 块，须共同覆盖 c0cb043c-cd67-4888-9e19-d1c822acd461、fc140511-65be-4a82-87ad-9dc9dd4e8543、05a7926d-889c-4182-a023-4b6f5cb97ee4、7313c35d-8d97-46d2-a2cf-f4724e14ecb4；当前任一 gold 命中即过的计分不适用，改为必需块组。 |
| rp-0170 | ms-0173 | PV | answerable_false_abstention | 校验规则：唯一陈述被丢弃（首轮判词未保留） | 当PRAC负责监督某项non-interventional PASS时，MAH应至少提前多久向Agency书面申请fin | 标注对：waiver 申请时限证据已在前 8，唯一陈述被校验流程丢弃；修校验规则。 |
| rp-0174 | ms-0177 | PV | answerable_false_abstention | 裁判过严（may / 应） | 按 REG Art 10a(2) 和 DIR Art 22a(2)，MAH 希望针对被施加的义务陈述书面意见时，应在收到 | 标注改：问题改为“若选择请求，应在多久内”，保留 30 天 gold；裁判不能把 may 与条件式时限判为矛盾。 |
| rp-0194 | ms-0199 | PV | answerable_answered_wrong_citation | 他文档同句 | 根据GVP Module XVI, 依据DIR Art 107m(3), 非介入性上市后安全性研究(PASS)在什么情况 | 标注对：明确问 GVP Module XVI，他文档同句不能替代该来源。 |
| rp-0200 | ms-0205 | PV | answerable_false_abstention | 分块截断：4.4 内容在下一块 | 根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果 | 标注改：各 SmPC 章节与额外 RMM 说明跨 4 块，须共同覆盖 05f240dd-a36c-414d-a2bc-61130c47f651、b7f9d06b-d380-4bcf-966f-f05b371b7cf9、62b7f077-0073-44cf-aab0-0740a2d7898f、737c819a-dd24-4ac1-9862-88fdd83e7113；须用必需块组而非任一命中。 |
| rp-0222 | ms-0227 | PV | answerable_false_abstention | 裁判过严 / 陈述省略条件（边界） | 在儿科 ICSR 报告中，如果无法获得患儿的确切年龄或出生日期，应改为记录什么信息以替代？ | 标注改：问题已给“无法取得年龄或生日”的前提，答案省略此前提不构成矛盾；回放失败标签应重判。 |
| rp-0230 | ms-0235 | PV | answerable_false_abstention | 校验规则：not exceed 1 calendar day 被丢弃 | 对于严重不良事件(SAE)的首次报告,FDA建议研究者向申办者提交初始信息的时限一般不应超过多久? | 标注对：“not exceed 1 calendar day”是时限上限，校验误弃答；gold 不改。 |
| rp-0232 | ms-0237 | PV | answerable_false_abstention | 校验规则：上限表达被判否定极性 | 在IDE研究中,研究者首次获知UADE(unanticipated adverse device effect)后,最迟 | 标注对：“in no event later than 10 working days”是同值上限，校验极性误判；gold 不改。 |
| rp-0236 | ms-0241 | PV | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | 依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reason | 标注改：问题点名法规条款，未点名 FDA 研究者指南；可接受同版本条款原文，或改写问题明确指定研究者指南。 |
| rp-0238 | ms-0243 | PV | answerable_false_abstention | 分块截断 | 在IND研究中,除IND安全报告和BA/BE研究中的SAE外,哪些其他类型的事件即使不符合IND安全报告标准,仍必须作为 | 标注改：原则与事件例子分别在 56c2d993-45d3-4934-a083-ecfdfb2861e3、f22428d5-feb0-473b-9c17-41c005048f26 两块；须共同引用，不能把第二块当可替代 gold。 |
| rp-0325 | ms-0336 | CO | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | 根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？ | 标注改：问题点名 21 CFR 312.50，未点名 FDA 风险监查指南；扩等价法规来源或改写指向该指南。 |
| rp-0523 | pc-0016 | MA | answerable_false_abstention | 模型误弃答：禁忌症明确 | 糖尿病患者能同時使用穩壓膜衣錠和 aliskiren 嗎 | 标注对：仿單明确列糖尿病患者合併 aliskiren 的禁忌，模型弃答错误。 |
| rp-0535 | pc-0028 | MA | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | esomeprazole 可以和 nelfinavir 一起服用嗎 | 标注改：只问 esomeprazole 成分，未点名胃所樂；补品牌或接受其他同成分仿單的相同禁忌。 |
| rp-0536 | pc-0029 | MA | answerable_answered_wrong_citation | 他文档同句（另一牌仿單） | 嚴重肝功能不良的病人 esomeprazole 最高劑量是多少 | 标注改：只问 esomeprazole 成分，未点名胃所樂；补品牌或接受其他同成分仿單的相同剂量限制。 |

## 三、本次裁决口径与落地条件（2026-09-28）

- 确认「问题明确点名产品或来源文件时，应引用该产品或文件」。上表 14 行中，6 行明确点名了金标来源；另 8 行仅点名成分、MedDRA、法规条号或 ICH 版本而金标指定的是其他载体，不能套用该规则。后 8 行按各行结论补明来源或扩充真正等价的引用来源。核对使用 `evals/replay/replay-v1/items.jsonl` 中的完整问题；本表的问题列有截断显示。
- rp-0121、0200、0238 的完整答案分别横跨 4、4、2 个分块。当前 `gold_chunks` 的多个候选按「任一命中」计分，不能简单把相邻块追加进去当作可替代 gold；应升版为共同必需的证据块组，并更新计分，或把问题收窄为单块可答。各行结论列列出当前分块快照中的完整 ID。
- 「标注改」中若只涉及回放失败标签或裁判误判，主集的原始证据与 gold 不随之改变；正式写回、重放与冻结须分别升版。
