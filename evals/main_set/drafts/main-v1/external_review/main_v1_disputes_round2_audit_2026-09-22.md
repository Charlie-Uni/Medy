# main-v1 第 2 轮争议裁决审计

- 日期：2026-09-22
- 第二轮争议：24 条
- 接受/修正后接受：16 条
- 保留上一轮判定：8 条
- 父/孪生规则：gold、evidence_span、key_text、slices、section 的修改按 spec-v1.1 §5.1 / PR-15 同族同步；query 仅修改本轮被争议条。
- 状态：`main-v1-provisional`

## 本轮继续沿用的统一口径

1. `dose_unit` 只覆盖药物剂量、剂量单位和具体给药频次；胎儿/新生儿体重、QT/QTc 毫秒值等测量值不因“数值+单位”自动命中。
2. `protocol_id` 仅在精确法规条号、章节号、标准版本或其他标识确实用于锁定目标条款时命中；仅以 `According to ICH E10/E11(R1)/E6(R3)` 指明来源文档，不自动命中。
3. `negation` 按完整 evidence_span 判断；明确的排除/禁用/不得/不要求/例外限制可命中。本轮 `ms-0372/0373` 扩 span 后出现 `exclusion criteria are suggested`，因此同步增加 `negation`。
4. key_text 应页内唯一、连续且保留命中对象与关键约束，同时遵守 200 字符上限；完整上下文由 evidence_span 承担。

## 两个非机械裁决

### ms-0197
复核人指出旧 key 从 `within 12-24 months` 起，丢失“初步评价”的对象，这个意见成立；但其建议的完整 key 超过 200 字符。采用 199 字符的连续折中锚点：
`initial evaluation of RMM, e.g. within 12-24 months to allow the possibility of necessary changes in healthcare; and • Within 4 years of regulatory implementation the overall effectiveness evaluation`
它同时保留初步评价对象、12–24 月时点、4 年时点与总体有效性评价对象。

### ms-0432
不接受继续扩 key。源句中“新剂型/新复方适用性”与“老年常见状况未被现行说明书处理”的完整连续判断包含较长括号举例，若全部纳入超过 200 字符。当前 key 已保留适用对象与适用性断言，必要的否定限定留在完整 evidence_span；同时避免只改中文父问而造成 EN 孪生语义漂移。

## PDF 复核要点

- GVP Module XVI Rev 3 物理第 19 页确有两个评价时点：初步评价例如 12–24 个月；监管实施后 4 年内进行总体有效性评价。
- ICH E14 物理第 6 页的 `>450 ms` 条目位于 “Until the effects ... have been characterized, the following exclusion criteria are suggested” 引导句之下；扩 span 后排除语义属于完整条款的一部分。
- FDA Informed Consent 2023 物理第 50 页同时存在 21 CFR 50.56(b)(3)/(4) 与 50.51/50.52 等多个条号；`ms-0313` 的 query 用 `21 CFR 50.56(b)` 精确锁定 advocate 要求，因此补 `protocol_id`。
- ICH E7 物理第 3 页关于新剂型/新复方的完整适用条件包含较长括号示例，支持 `ms-0432` 的 200 字符上限裁决。

## 应用后检查

完成 `apply_sheet_edits.py` 后仍需：
- 重算 char_start/char_end；
- 复核 key_text 页内唯一性；
- 同步父/EN 孪生的 gold 与 slices；
- 对 `ms-0372/0373` 检查新增 negation 后的切片统计；
- 对所有改 span 的条目重新跑完整条款机械校验。
