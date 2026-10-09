# 记录 148：v4 key 裁决与预算阈值停止

日期：2026-10-08。OPT-12/13。状态：**人工 key 裁决已落实，v4 确定性校验通过；两次授权调用均已结算，`ms-0241` agree，`ms-0242` 因 CLI 单次预算阈值停止且没有 verdict。未重试，v4 仍不可冻结。**

## 授权与数据修改

项目所有者回复“可以”，确认上一轮的两个绑定事项：

1. 把 `ms-0241-g3` 和 `ms-0242-g3` 的 key 同步补全到药物治疗组与同期/历史对照组的比较对象，生成 v4；
2. 仅复核这两题，最多 2 次、每次 0.25 USD、总额 0.50 USD、无自动重试，失败或费用不明立即停止。

新 key 在 FDA 指南第 7 页 `[1365,1561)` 唯一出现，并完整落在原 span `[1363,1731)` 内。query、span、三个共同必需的语义证据组、物理 chunk 和 slices 不变。v4 manifest SHA-256 为 `4adb18739e21261ab6a4a22d391301751488dfd6286ea3afa301a4e8a47ea8a3`；人工确认 SHA-256 为 `c251d81bf3078ca027458fbd8a291e404edf2310925d77ec7ab7e6024e80c304`。

`annotation_revision --with-pages` 通过：19 条 proposals、39/39 gold mapped、投影主集 615 条、配额短缺为空。v3 输入、意见和费用保持原样。

## 实际调用

| 样本 | 结果 | CLI 原始估算 | 账本金额 | 说明 |
| --- | --- | ---: | ---: | --- |
| `ms-0241` | agree | 0.19007875 USD | 0.190079 USD | 五项均 ok；新 key 通过 |
| `ms-0242` | 无 verdict | 0.25199750 USD | 0.251998 USD | `error_max_budget_usd`；CLI 没有返回结果正文 |
| 合计 | 1 agree / 1 未完成 | 0.44207625 USD | **0.442077 USD** | 授权余额 0.057923 USD |

第二次调用的报告费用比 `--max-budget-usd 0.25` 多 0.0019975 USD。预算账本将该次标为 `cli_call_failed` 与 `cli_cap_exceeded=true`，但费用已知，所以没有记成 unknown charge。两次尝试上限已用完；工具没有自动重试，也没有把空结果写成 agree/dispute。

这个结果进一步界定 Claude CLI 限额的实际语义：它能在生成过程中触发停止，却不是结算层严格不越界的硬上限。项目自己的总账本仍正确保守入账并阻止后续调用。

[逐调用审计 JSON](2026-10-08-implementation-148-review-audit.json)绑定授权、v4 manifest/人工确认、输入、提示、模型、session、费用、capture 哈希与 0600 权限。

## 已准备但未授权的补救

[`retry_request_2026-10-08.json`](../../evals/main_set/drafts/revision-2026-10-08-v4/review/eval08_followup_retry1/retry_request_2026-10-08.json)绑定完全相同的 `ms-0242` 输入和提示，建议：

- 只调用 `ms-0242`；
- `claude-opus-5`、effort=high；
- 最多 1 次、总授权 0.30 USD，CLI 停止参数 0.28 USD，留 0.02 USD 处理已观测到的停止阈值小幅越界；
- 无自动重试，任何失败即停止。

该目录没有授权文件、预算账本或模型调用。0.30 USD 是新授权建议，不把上次剩余 0.057923 USD 误算为足够重试额度。由于 Claude CLI 的停止阈值不是结算硬上限，0.02 USD 是工程缓冲，不能声称供应商绝不会出现更大的越界；若再次触发阈值或超出预留，仍立即停止且不再重试。

## 验证与自审

- v4 页文本、offset、key 唯一性、孪生一致性、证据组与映射校验通过。
- 成功调用的 prompt、run、verdict 和原始回复可重建；失败调用的 capture、模型与费用可核账。
- 原始 capture 均为 0600 且被 `.gitignore` 递归排除。
- `env -u DEBUG make check`：1635 passed、70 skipped、1 个沿用的测试短 HMAC key 警告；ruff、423 个文件格式、186 个源文件 mypy、四套评测输入审计和 Schema 漂移检查全部通过。评测审计继续如实报告 7 个 unmappable gold、旧历史回放、第二人工 pending、无未见盲测及 19 条修订仍为 draft。

| 自审项 | 结论 | 依据与限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 只修改获准的两个 key，只调用授权的两题；未冻结或改门禁 |
| 正确性与失败路径 | 通过（执行控制） | 预算停止没有被当成模型结论；超出单次预留被捕获；未重试 |
| 权限与追溯 | 通过 | 精确输入/授权/费用绑定，原始文件 0600 且不入 Git；第二人工仍 pending |
| 验证 | 通过 | 数据与调用审计通过；全量 1635 passed、70 skipped，lint、格式、mypy、评测审计与 Schema 均通过 |
| 状态与文档 | 通过 | `ms-0241=agree`、`ms-0242=pending_no_verdict`，v4 明确不可冻结 |

**本轮数据修改与失败关闭行为自审通过；EVAL-08 尚缺 `ms-0242` 的有效 verdict，阶段 1 不通过。**
