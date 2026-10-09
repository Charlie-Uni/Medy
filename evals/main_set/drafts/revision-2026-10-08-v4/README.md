# 标注修订草案 v4（2026-10-08）

本目录继承 v3，并落实项目所有者对 v3 唯一后续争议的回复“可以”。

`ms-0241-g3` 与英文孪生 `ms-0242-g3` 的 `key_text` 同步改为：

> An aggregate analysis of specific events observed in a clinical trial that indicates those events occur more frequently in the drug treatment group than in a concurrent or historical control group

该 key 在第 7 页 `[1365,1561)` 唯一出现，位于原 evidence span `[1363,1731)` 内。query、span、三个共同必需的语义证据组、物理 chunk 映射和 slices 不变。v3 输入、意见和费用保留为历史。

本目录仍为 draft，`freeze_ready=false`；两条变化输入须完成新的 EVAL-08。第二独立人工仍 pending。

## 定向复核状态

- `ms-0241`：agree，新 key 的五项检查均通过。
- `ms-0242`：首次调用达到 Claude CLI 的单次预算阈值，没有 verdict；经新的单次授权重试后 agree。

首轮两次调用的账本金额为 0.442077/0.500000 USD；单次重试为 0.185248/0.300000 USD。v4 后续复核全部尝试合计 0.627325 USD，失败调用费用保留。两条变化样本现均为 agree，见[复核状态](review/review_status_2026-10-08.json)。本目录仍是 draft；第二人工、探针导入和主集版本化尚未完成。
