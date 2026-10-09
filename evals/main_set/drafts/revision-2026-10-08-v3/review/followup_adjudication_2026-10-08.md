# v3 EVAL-08 后续人工裁决

状态：**待项目所有者裁决 1 项**。原三项裁决已落实；本轮三次调用全部成功，`ms-0242` 与 `ms-0280` 为 agree，`ms-0241` 对 `key_text` 提出新争议。

## 2026-10-08 裁决执行

项目所有者回复“可以”，建议 key 已同步写入 [v4](../../revision-2026-10-08-v4/README.md)。v4 的 `ms-0241` 复核 agree；`ms-0242` 调用因单次预算阈值停止、没有 verdict，未自动重试。后续运行状态见 [记录 148](../../../../../docs/reviews/2026-10-08-implementation-148-v4-key-adjudication-and-budget-stop.md)。 本目录的结构化 JSON 保留裁决前、由 v4 确认文件绑定的待决快照；后续决定另存于 [v4 决定事件](../../revision-2026-10-08-v4/review/owner_decision_2026-10-08.json)，不覆盖旧哈希。

## 已裁决的决定

建议接受争议，并把 `ms-0241-g3` 与英文孪生 `ms-0242-g3` 的 key 同步改为：

> An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group

理由：当前 key 截在 `occur more frequently`，没有保留“药物治疗组相对同期或历史对照组”的比较对象；这属于 P1 所要求的约束。建议 key 在第 7 页 `[1365,1561)` 唯一出现，仍完全位于原 span `[1363,1731)`，span、query、证据组和 chunk 映射都不用改。`g2` 的 `not commonly associated` 是描述性属性，不按当前规则增加 `negation`。

英文孪生使用完全相同的 key，却在另一独立会话得到 agree；因此记录为复核者不一致，不覆盖任一原始意见。若接受修改，两条输入都发生变化，须重新复核。现有 3 次调用上限已经用完，虽有 0.194100 USD 账面余额也不能续用；建议另批最多 2 次、总上限 0.50 USD、无自动重试。
