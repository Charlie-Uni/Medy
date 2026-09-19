# 新口径正式复核进度与争议

提示 SHA-256：`f4a3804e969b23ec9ab467406937e62f0b9e30933d6a680d4b00ee59b2631c38`。模型 gpt-6-astra，逐条 high；本表由 review_summary.py 生成。

本表列当前样本的独立 LLM 复核意见；人工裁决见 [确认记录](owner_confirmations_2026-09-19.md) 及 resolutions.json。
统计仅按 LLM 的 agree/dispute 结论，不表示争议是否已由人工裁决；草稿、页文本或提示变更后须重新复核。

- MA：30/30；agree 28，dispute 2。
- PV：29/29；agree 28，dispute 1。
- CO：16/16；agree 15，dispute 1。

合计 75/75；agree 71，dispute 4。
复核已跑完，人工裁决状态另见确认记录及 resolutions.json；未冻结。

## pc-0026 / MA / evidence_span

问题：胃所樂泡在水裡崩散後要在多久之內喝完

当前锚点：立即或在 30 分鐘之內將水連同小藥球喝下

原文位置：tfda-label-esomen-40mg，物理页 1，用法用量。

复核理由：evidence_span 遗漏该服用方式的适用人群和液体限制。前句明确规定：「對於有吞嚥困難的病人,可將藥錠置入半杯非碳酸類的水中,且不可使用他種液體,因為藥錠的腸衣膜可能因此溶解。」现有 span 单独引用时未保留这些必要限定条件。

复核人建议：将 evidence_span 起点前移至「對於有吞嚥困難的病人」，保留至现有终点并更新偏移；扩展后按完整 span 增加 negation 标签。

人工裁决：请核对确认记录及 resolutions.json 中绑定本次输入与结论的记录。

## pc-0027 / MA / evidence_span

问题：胃所樂腸溶膜衣錠用於食道未發炎的胃食道逆流症狀治療，劑量和療程是多少

当前锚点：食道未發炎之患者 20 mg 每天 1次

原文位置：tfda-label-esomen-40mg，物理页 1，用法用量。

复核理由：evidence_span 遗漏适用人群的上位限定。页文本将该条款置于“成人成人成人成人及及及及 12 歲以上之青少年歲以上之青少年歲以上之青少年歲以上之青少年”之下，现有 span 未保留此年龄范围。

复核人建议：证据应保留成人及12岁以上青少年的适用范围，并同步核对文本及偏移；回答疗程时应区分“若 4週後仍有症狀時,則應進一步檢查患者。”与固定4周疗程，原文未明确规定固定疗程。

人工裁决：请核对确认记录及 resolutions.json 中绑定本次输入与结论的记录。

## pc-0038 / PV / slices

问题：MedDRA《数据检索和展示：考虑要点》多久更新一次？

当前锚点：MedDRA 用户指南,每年更新一次

原文位置：meddra-data-retrieval-ptc-3-26-zh-hans，物理页 4，SECTION 1 – 引言。

复核理由：按给定定义，dose_unit 包含“频次表达”，且按完整 evidence_span 判定；原文“每年更新一次”属于频次表达，现有标签漏标 dose_unit。定义未将频次表达限定为给药频次。

复核人建议：补充 dose_unit 标签；若本意仅纳入给药频次，应先明确收窄切片定义，再复核此项。

人工裁决：请核对确认记录及 resolutions.json 中绑定本次输入与结论的记录。

## pc-0074 / CO / evidence_span

问题：按照 FDA 2024 年《方案偏离》指南草案，未被归类为 important 且不对受试者构成明显即时危险的方案偏离，需要立即报告给 IRB 吗？

当前锚点：protocol deviations that are not classified as important and do not present an apparent 355 immediate hazard to participants do not need to be immediately reported to the IRB

原文位置：fda-protocol-deviations-draft-2024，物理页 13，III.B.3. Role of the IRB in Evaluating Protocol Deviations。

复核理由：evidence_span.text 内容完整且能回答 query，但偏移与页文本不一致：按零基、右端不含的字符偏移，该文本位于 [914,1099)，不是所标注的 [940,1125)。

复核人建议：将 evidence_span.char_start 改为 914，char_end 改为 1099，保留其余内容。

人工裁决：请核对确认记录及 resolutions.json 中绑定本次输入与结论的记录。
