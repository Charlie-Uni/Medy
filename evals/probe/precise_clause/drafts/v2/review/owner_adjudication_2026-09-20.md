# annotator-01 对探针 v2 复核争议的裁决（2026-09-20，回复“好了”）

> 决策人提交裁决文档：13 条接受、4 条修正后执行、4 条保留。gold/slices 变更父子同步并对受影响同族全部重跑复核；query 变更只作用于指定样本。以下为执行摘要；逐字段的新值见 `owner_adjudication_changes_2026-09-20.json`，应用脚本为 `tooling/apply_owner_adjudication_2026_09_20.py`。

| 样本 | 裁决 | 处理与理由 |
| --- | --- | --- |
| pc-0008 | 接受 | 删除 negation；最终 slices = [dose_unit, mixed_zh_en]。上限名词“處方限量”不等于原文存在否定表达，不扩大 span。 |
| pc-0012 | 接受 | 删除 negation；最终 slices = [protocol_id]。“須由醫師處方使用”是正向要求。 |
| pc-0022 | 接受 | 删除 negation；最终 slices = [time_window, drug_name_zh]。肯定式停药指示与至少 48 小时的时间下限。 |
| pc-0023 | 保留 negation + 补充方案 A | “倘若還未能達到滿意效果時”控制后续处置的适用条件；key_text 扩为初步处置至条件分支的连续片段（A23），span 与 slices 不变。 |
| pc-0027 | 修正后执行（补充方案 B） | 接受收缩 evidence_span 至症狀治療条款；保留 negation（“食道未發炎”为必要人群限定）；query 改为每日用量与持续有症状时的复查时点；key_text 覆盖剂量与该时点。 |
| pc-0033 | 接受 | query 改为 Q1，仍问能否由机构自行变通；证据不变。 |
| pc-0036 | 修正后执行（补充方案 C） | 肝酶检查频次既非给药频次亦非有边界时间窗；SPEC 第 7 节未把监测周期纳入 time_window，故删除 dose_unit 与 time_window，最终 [mixed_zh_en, negation]。 |
| pc-0044 / pc-0079 | 接受 | key_text = K1（补“生产过程中、成品放行前”限定），父子同步。 |
| pc-0045 / pc-0080 | 接受 | key_text = K2（补责任主体）；现有 span 已含信号确认定义句与时限句，不变；父子同步。 |
| pc-0047 | 修正后执行 | query 改为 Q2（不新增 30 天等问点）；key/span 不变；不自动改写 pc-0082（双语信息需求已核对等价）。 |
| pc-0050 / pc-0085 | 接受 | key_text = K3（条款对象、两个编号、汇总数据要求）；不新增 protocol_id；父子同步。 |
| pc-0058 | 接受 | key_text = K4（含“投予劑量、劑量單位”）。 |
| pc-0067 / pc-0099 | 接受 | key_text = K5（完整句）；不收窄 query；父子同步。 |
| pc-0069 / pc-0101 | 接受 | key_text = K6（完整句，父子同一版本）。 |
| pc-0088 | 保留 | negation 保留：“no later than 7 calendar days”为不可越过的时间上限，与 time_window 分别标记。 |
| pc-0089 | 保留 | negation 保留：“no longer than one year”为覆盖期的否定式上限。 |
| pc-0090 | 保留 | negation 保留：“no later than 60 calendar days”为否定式截止限制；与 pc-0088/0089 同一解释。 |
| pc-0092 / pc-0060 | 修正后执行 | pc-0092 query 改为 Q3（保留双问点）；key_text = K7 并按同族同步到 pc-0060。 |

## 决策人裁决文档中的原则

- negation 按“必须保留影响条款适用范围或答案的否定语义”判定；未把“标签互斥”“条件句不算否定”“比较上限一律不算否定”当作已核验的规则。若正式 SPEC 明文排除比较上限，应先统一规则再按同族重标，不由复核人临时新增排除标准。
- key_text 按 P1：不能只有孤立数字、编号或截掉关键对象/限定；最终字符串取自规范页文本（norm-v1），并验证页内唯一与 span 包含。
- 写回前检查：页内精确命中一次且落在 span 内；改动 span 重算偏移；同族字段一致；同页替代条款是否也能回答按已知限制记录。

## 新 key_text / query 文本

- K1: `does not include the exposure to one of the ingredients during the manufacturing process before the release as finished product`
- K2: `This should be done by the PRAC Rapporteur or the (lead) Member State within 30 days from receipt of the validated signal`
- K3: `the two IND safety reporting provisions (§ 312.32(c)(1)(i)(C) and (c)(1)(iv)) that require assessment of aggregate data`
- K4: `投予劑量、劑量單位,例如:「10mg」、「5mg/kg」`
- K5: `Essential records should be retained securely by sponsors and investigators for the required period in accordance with applicable regulatory requirements`
- K6: `Investigational products should be used in accordance with the protocol and relevant trial documents`
- K7: `all study procedures and assessments are necessary from a scientific viewpoint and do not place undue burden on study participants`
- A23: `初步的急救方法,係靜脈注射1〜2mg Atropine sulfate;倘若還未能達到滿意效果時,在使用 Atropine 後可接著投與升壓劑,例如metaraminol 或 noradrenaline`
- B27: `對食道未發炎之患者 20 mg 每天 1次;若 4週後仍有症狀時,則應進一步檢查患者`
- pc-0033 query: 编码时发现现有 MedDRA 术语不能准确表达个案内容，团队可以自行制定临时处理规则吗？
- pc-0047 query: 按 GVP Module IX，收到信号确认结果后，能否在流程记录中把该信号标记为“完整评估已完成”？
- pc-0092 query: When selecting procedures and assessments for a study, what does ICH E8(R1) require the team to consider about why they are needed and the demands they place on participants?
- pc-0027 query: 依胃所樂腸溶膜衣錠仿單，成人及 12 歲以上青少年若有胃食道逆流症狀、但食道沒有發炎，每日用量如何安排？治療多久仍有症狀時應進一步檢查？
- pc-0027 evidence_span: `胃食道逆流性疾病之症狀治療:對食道未發炎之患者 20 mg 每天 1次;若 4週後仍有症狀時,則應進一步檢查患者。`
