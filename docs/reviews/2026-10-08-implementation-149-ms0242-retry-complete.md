# 记录 149：ms-0242 单次重试完成

日期：2026-10-08。OPT-12/13。状态：**授权的单次重试成功，`ms-0242` agree；v4 两条 key 变化样本均完成独立模型复核。调用审计通过，无重试、失败、未知费用或限额越界。**

## 授权与执行

项目所有者回复“授权”，批准已准备的精确重试：只含 `ms-0242`，固定 `claude-opus-5`、请求 effort=high，最多 1 次，总授权 0.30 USD，CLI 停止阈值 0.28 USD，并保留 0.02 USD 处理已观测到的阈值小幅越界；无自动重试。

授权绑定 v4 manifest、人工确认、重试请求、输入和提示 SHA-256。调用返回 agree，五项均为 ok；原始 CLI 费用 0.1852475 USD，向上取整后的账本金额 0.185248 USD，剩余 0.114752 USD。调用 1 次、独立 session 1 个、12,180 Token（含缓存输入）、耗时 59,444 ms。

原始 capture 权限为 0600 且不进入 Git。run、verdict、实际 prompt 和原始回复逐字重建一致。详见[审计 JSON](2026-10-08-implementation-149-review-audit.json)。

## v4 当前结论

- `ms-0241`：agree；初次 v4 调用账本 0.190079 USD。
- `ms-0242`：agree；本次重试账本 0.185248 USD。
- 前次没有 verdict 的失败调用仍按 0.251998 USD 保留，不能删除或用成功重试覆盖。
- v4 后续复核全部尝试合计账本 **0.627325 USD**；分属已明确批准的 0.50 USD 首轮与 0.30 USD 单次重试两份授权。

[`review_status_2026-10-08.json`](../../evals/main_set/drafts/revision-2026-10-08-v4/review/review_status_2026-10-08.json)只声明两条 v4 变化样本的独立模型复核完成。第二独立人工仍 pending；新探针导入与 provisional 主集冻结仍是后续独立步骤，因此 v4 本身保持 draft、`freeze_ready=false`。

## 验证与自审

- v4 页文本、offset、key 唯一性、孪生一致性、证据组和 chunk 映射再次通过。
- 精确授权、总账本、单次费用、输入、提示、模型、session、原始回复与 verdict 绑定通过。
- 没有把失败调用当作意见，也没有覆盖失败费用。
- `env -u DEBUG make check`：1635 passed、70 skipped、1 个沿用的测试短 HMAC key 警告；ruff、423 个文件格式、186 个源文件 mypy、四套评测输入审计和 Schema 漂移检查全部通过。评测审计继续如实报告 7 个 unmappable gold、旧历史回放、第二人工 pending、无未见盲测及 19 条修订仍为 draft。

| 自审项 | 结论 | 依据与限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 只调用授权的 `ms-0242` 一次；未扩大样本、模型或预算 |
| 正确性与失败路径 | 通过 | 有效 JSON verdict 才入账为 agree；历史失败与费用完整保留 |
| 权限与追溯 | 通过 | 全部哈希可重建，capture 0600 且忽略；第二人工未冒充完成 |
| 验证 | 通过 | 数据、调用和费用专项审计通过；全量 1635 passed、70 skipped，lint、格式、mypy、评测审计与 Schema 均通过 |
| 状态与文档 | 通过 | EVAL-08 可完成；v4 仍是待版本化的 provisional 草案 |

**本次付费重试与 EVAL-08 变化样本复核自审通过；阶段 1 仍需探针导入、主集版本化及其完整冻结校验。**
