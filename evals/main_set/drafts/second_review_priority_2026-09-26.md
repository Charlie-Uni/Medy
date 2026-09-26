# 主集第二次人工复核优先清单（2026-09-26，记录 93 §B）

来源：记录 92 的归因诊断与记录 93 的逐条复核。请复核人对每行在「结论」列填：`标注改`（说明改法：扩 gold 到哪些分块 / 改 key_text）、`标注对`（系统确实错）或 `待定`。分块 id 见 `evals/replay/replay-v1/items.jsonl` 与主集运行 `evals/harness/runs/2026-09-23-full-ask-v2/rows.jsonl`。

## 一、被引分块逐字包含标注 key_text 的「错引」题（14 道，机械核对；逐一核对后全部是**另一份文档**含相同句子——同成分他牌仿單、共用段落的姊妹指南、ICH 原版与 FDA 转载。请确认规则：点名产品 / 文件的问题必须引用该文档）

| 回放 id | 主集 id | 部门 | 问题 | 结论 |
| --- | --- | --- | --- | --- |
| rp-0053 | ms-0056 | MA | 停止使用拔痛酸錠（Allopurinol）治療後，血清尿酸濃度通常多久會回復到治療前的數值？ |  |
| rp-0236 | ms-0241 | PV | 依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reasonable possi |  |
| rp-0237 | ms-0242 | PV | According to the examples provided under § 312.32(c)(1)(i) for IND saf |  |
| rp-0275 | ms-0280 | PV | 使用 MedDRA 时,能否对术语的层级结构进行临时改动,比如变更某个 PT 的主 SOC 分配? |  |
| rp-0293 | ms-0298 | CO | 根据ICH E6(R3),在什么情况下可以不经IRB/IEC事先书面批准就对已批准的试验方案进行偏离或变更? |  |
| rp-0294 | ms-0299 | CO | 根据ICH E6(R3),研究者或研究机构工作人员是否可以对受试者施压以促使其继续参与临床试验? |  |
| rp-0325 | ms-0336 | CO | 根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？ |  |
| rp-0518 | pc-0011 | MA | 痛風停錠單次劑量的上限是多少 |  |
| rp-0524 | pc-0017 | MA | 糖尿病腎病變患者已使用 ACEI 時，可以再加用 ARB 嗎 |  |
| rp-0533 | pc-0026 | MA | 胃所樂泡在水裡崩散後要在多久之內喝完 |  |
| rp-0535 | pc-0028 | MA | esomeprazole 可以和 nelfinavir 一起服用嗎 |  |
| rp-0558 | pc-0051 | PV | 按照 ICH E2A，不良事件的定义是否要求与治疗存在因果关系？ |  |
| rp-0577 | pc-0070 | CO | ICH E6(R3) 对 IRB/IEC 应保留的相关记录列举了哪些例子？ |  |
| rp-0609 | pc-0102 | CO | What examples of relevant records does ICH E6(R3) list that the IRB/IE |  |

## 二、gold 已在前 8 却失败的 18 道（含上表中的 6 道）

| 回放 id | 主集 id | 部门 | 原标签 | 我的归类 | 问题 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| rp-0012 | ms-0012 | MA | answerable_false_abstention | 裁判过严（问题限定 CrCl<30，答 400 mg 正确） | 需要血液透析且creatinine清除率低於30 ml/min/1.73m2的病人，使用信諾隆（Ciprofloxaci |  |
| rp-0033 | ms-0036 | MA | answerable_false_abstention | 模型误弃答：禁忌句即答案 | 「安星」伊風柔錠300毫克可以用於治療急性痛風性關節炎發作嗎？ |  |
| rp-0046 | ms-0049 | MA | answerable_false_abstention | 校验规则：唯一陈述被丢弃（首轮判词未保留） | Losacar用於治療第II型糖尿病腎病變時，起始劑量為何，並可視血壓下降情形增加至多少？ |  |
| rp-0053 | ms-0056 | MA | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | 停止使用拔痛酸錠（Allopurinol）治療後，血清尿酸濃度通常多久會回復到治療前的數值？ |  |
| rp-0121 | ms-0124 | PV | answerable_false_abstention | 分块截断：三级定义分在两块 | 根据 GVP Module IV,药物警戒审计发现(audit findings)应如何分级为 critical、maj |  |
| rp-0170 | ms-0173 | PV | answerable_false_abstention | 校验规则：唯一陈述被丢弃（首轮判词未保留） | 当PRAC负责监督某项non-interventional PASS时，MAH应至少提前多久向Agency书面申请fin |  |
| rp-0174 | ms-0177 | PV | answerable_false_abstention | 裁判过严（may / 应） | 按 REG Art 10a(2) 和 DIR Art 22a(2)，MAH 希望针对被施加的义务陈述书面意见时，应在收到 |  |
| rp-0194 | ms-0199 | PV | answerable_answered_wrong_citation | 他文档同句 | 根据GVP Module XVI, 依据DIR Art 107m(3), 非介入性上市后安全性研究(PASS)在什么情况 |  |
| rp-0200 | ms-0205 | PV | answerable_false_abstention | 分块截断：4.4 内容在下一块 | 根据GVP Module XVI，SmPC(产品特性概要)各相关章节应呈现哪些与风险最小化措施(RMM)相关的信息，如果 |  |
| rp-0222 | ms-0227 | PV | answerable_false_abstention | 裁判过严 / 陈述省略条件（边界） | 在儿科 ICSR 报告中，如果无法获得患儿的确切年龄或出生日期，应改为记录什么信息以替代？ |  |
| rp-0230 | ms-0235 | PV | answerable_false_abstention | 校验规则：not exceed 1 calendar day 被丢弃 | 对于严重不良事件(SAE)的首次报告,FDA建议研究者向申办者提交初始信息的时限一般不应超过多久? |  |
| rp-0232 | ms-0237 | PV | answerable_false_abstention | 校验规则：上限表达被判否定极性 | 在IDE研究中,研究者首次获知UADE(unanticipated adverse device effect)后,最迟 |  |
| rp-0236 | ms-0241 | PV | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | 依据IND安全报告法规§ 312.32(c)(1)(i)所举实例,判定药物与不良事件之间存在'合理可能性'(reason |  |
| rp-0238 | ms-0243 | PV | answerable_false_abstention | 分块截断 | 在IND研究中,除IND安全报告和BA/BE研究中的SAE外,哪些其他类型的事件即使不符合IND安全报告标准,仍必须作为 |  |
| rp-0325 | ms-0336 | CO | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | 根据21 CFR 312.50，申办者对临床试验监查负有哪些具体职责？ |  |
| rp-0523 | pc-0016 | MA | answerable_false_abstention | 模型误弃答：禁忌症明确 | 糖尿病患者能同時使用穩壓膜衣錠和 aliskiren 嗎 |  |
| rp-0535 | pc-0028 | MA | answerable_answered_wrong_citation | 他文档同句（同成分他牌 / 姊妹文件） | esomeprazole 可以和 nelfinavir 一起服用嗎 |  |
| rp-0536 | pc-0029 | MA | answerable_answered_wrong_citation | 他文档同句（另一牌仿單） | 嚴重肝功能不良的病人 esomeprazole 最高劑量是多少 |  |

## 三、建议的规则变更（复核后再定）

- 若确认「点名文档必须引用该文档」，标注不改；改进方向是检索按点名文档定位（记录 93 §C.1）。
- 对跨两块的答案（rp-0121 / 0200 / 0238），gold 应同时列出两块，或问题改为单块可答。
