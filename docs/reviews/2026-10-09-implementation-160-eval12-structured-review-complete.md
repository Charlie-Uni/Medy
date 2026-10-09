# 记录 160：EVAL-12 结构化语义裁判完成

日期：2026-10-09。状态：**完成。10/10 answered 案例均有有效 Claude verdict；14 个案例的语义支持与答案完整性校准报告已生成。该结果是开发校准诊断，不是正式门禁或第二人工。**

## 1. 授权与不可变输入

项目所有者授权原文：

> 授权 EVAL-12 Claude JSON Schema 后续裁判：再次重试 ms-0242 并处理剩余 7 条，最多 8 次，新增费用上限 2.40 USD。

执行绑定：

- 请求：`evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-followup2-request.json`，SHA-256 `6e6d0503…e276`；
- 授权：`evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-followup2-authorization.json`，SHA-256 `89ea00f9…3527`；
- 模型：Claude Opus 5，reasoning effort `high`；
- tools-off、每题独立会话；
- 最多 8 次，每次 CLI 阈值 0.28 USD、账本预留 0.30 USD，本轮总上限 2.40 USD；
- 输入：两个回答生成运行的 14 个精确快照，其中 10 answered、4 escalated；
- 历史：两条既有有效 verdict、两次 `ms-0242` 无效输出、费用与 0600 原始产物全部由哈希绑定。

## 2. 首次 Schema 调用暴露的适配器错误

本轮第一次 `ms-0242` 调用实际成功：Claude CLI `returncode=0`、`subtype=success`，`structured_output` 含完整的 `claims`、`citations` 和 `completeness`，Schema SHA-256 与请求一致。旧适配器仍读取外层自由文本 `result`，因此本地解析器报“不是 JSON 对象”，将账本 outcome 记为 `ValueError` 并停止。

这次错误属于本地输出字段选择错误，不是模型结构失败。修复后：

1. 传入 JSON Schema 时，`run_claude` 只读取并规范序列化 `structured_output`；
2. 缺少 `structured_output` 时失败关闭，不回退到自由文本；
3. 调用前拒绝 Claude 不支持的 Schema 约束；
4. 恢复器只接受哈希一致的 0600 产物、成功 CLI 状态、唯一正确模型、相同费用、相同 case/prompt/Schema hash；
5. 恢复出的 verdict 再经过完整 rubric、条数、索引、理由和 case hash 校验；
6. 原 `ValueError` 与 0.077425 USD 保留，账本追加 `validated_reply` reconciliation，不删除或改写历史。

恢复没有模型调用。随后同一授权剩余 7 次全部返回有效结构化 verdict。

## 3. 本轮调用与费用

| 样本 | 账本费用 USD | 结果 |
| --- | ---: | --- |
| `ms-0242` | 0.077425 | CLI 结构化输出有效；修复适配器后由原产物恢复 |
| `ms-0298` | 0.066503 | validated reply |
| `ms-0338` | 0.060345 | validated reply |
| `ms-0440` | 0.090923 | validated reply |
| `ms-0001` | 0.075385 | validated reply |
| `ms-0099` | 0.057679 | validated reply |
| `ms-0104` | 0.073894 | validated reply |
| `ms-0317` | 0.075936 | validated reply |

本轮 8 次费用合计 0.578090/2.400000 USD，剩余 1.821910 USD；无未知费用和未结预留。三轮 Claude 裁判共 12 次调用，账本累计 0.830482 USD：

- 初始运行 3 次：0.196300 USD，2 条有效；
- 第一次后续 1 次：0.056092 USD，模型正文无效；
- Schema 后续 8 次：0.578090 USD，8 条最终有效，其中首条由同次调用的结构化产物恢复。

回答生成另计 0.113024 USD。不同提供方/账本的数字不合并冒充供应商账单。

## 4. 最终语义结果

合并 2 条先前 verdict 与本轮 8 条 verdict 后：

| 指标 | 分子/分母 | 结果 |
| --- | ---: | ---: |
| Claim support | 12/12 | 100.0% |
| Citation support | 13/14 | 92.9% |
| Answer completeness | 7/14 | 50.0% |

完整性分母包含 10 个 answered 案例和 4 个 answerable escalation；后者依 rubric 固定为 incomplete。仅看 answered 案例，7/10 complete、3/10 incomplete。

| 案例 | Claim | Citation | 完整性 | 诊断 |
| --- | --- | --- | --- | --- |
| `ms-0056` | supported | 3/3 supported | complete | 无缺口 |
| `ms-0149` | supported | 1/2 supported | complete | 第 2 条引用只给字段标签及妊娠/哺乳场景，未支持“不重复病例”的实质结论 |
| `ms-0242` | supported | 1/1 supported | incomplete | 只回答三个法规定义示例中的第一个，遗漏 tendon rupture 与 aggregate analysis 两项 |
| `ms-0298` | supported | 1/1 supported | incomplete | 只回答消除受试者即时危险，遗漏符合监管要求的纯物流/行政变更例外 |
| `ms-0338` | supported | 1/1 supported | complete | 无缺口 |
| `ms-0440` | 3/3 supported | 2/2 supported | incomplete | 覆盖前四类研究，遗漏与可能合并用药的相互作用研究及其 PK screen 条件 |
| `ms-0001` | supported | supported | complete | 无缺口 |
| `ms-0099` | supported | supported | complete | 无缺口 |
| `ms-0104` | supported | supported | complete | 无缺口 |
| `ms-0317` | supported | supported | complete | 无缺口 |

4 个 answerable escalation 为 `ms-0012`、`ms-0177`、`ms-0227`、`pc-0068`。它们没有伪造答案，继续以 incomplete 进入完整性分母。

结果说明结构化引用命中与 claim 支持不能代表答案完整：所有 12 个 claim 均受引用支持，但 3 个 answered 案例漏答共同必需项。下一轮来源约束和多 gold 覆盖优化应把这三条作为回归案例；`ms-0149` 用于检查多余或弱相关引用。

## 5. 产物与完整性

最终目录：`evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-claude-review-followup2`。

| 文件 | SHA-256 |
| --- | --- |
| `verdicts.jsonl` | `4a002eff…841d` |
| `budget.json` | `19abf14f…3a9d` |
| `run.json` | `1713a0b…1815` |
| `report.json` | `6a14c47f…32fb` |

8 份调用产物均为 0600。最终运行有 8/8 completed case hash、8 次费用记录、1 条适配器恢复记录；报告可从两个生成运行、先前 2 条 verdict 和本轮 8 条 verdict 零调用重建。

## 6. 口径限制

- 这是有目的挑选的 14 题开发校准面板，不估计 615 题主集的总体表现；
- Claude 是模型裁判，不是第二独立人工；
- `formal_gate=false`，结果不替换原 Harness outcome，也不回填历史门禁；
- 100% claim support 只说明已输出 claim 有证据，不代表所有问题部分都已回答；
- 正式质量数字仍需 EVAL-22/EVAL-23 在新冻结主集上运行，并继续披露第二人工和未见盲测集缺口。

## 7. 自审

| 自审项 | 结论 |
| --- | --- |
| 需求与范围 | 通过。8 次调用没有超过授权次数或 2.40 USD；没有调用未授权案例。 |
| 正确性与失败路径 | 通过。适配器错误从同一原始产物恢复；原失败、费用和恢复证据同时保留。其余 7 次全部经 Schema 与本地语义结构校验。 |
| 权限与可追溯性 | 通过。请求、授权、case、prompt、Schema、产物、费用和 verdict 均有 SHA-256；模型未记为第二人工。 |
| 验证 | 定向恢复、预算和 answer review 57 passed；全量 `make check` 1712 passed、70 skipped，ruff、438 个文件格式、mypy、评测审计和 schema 均通过，仅保留既有短 HMAC 测试警告。 |
| 状态与文档 | 通过。EVAL-12 与 PAY-08 更新为 DONE；正式主集运行保持 PAID，未用校准结果冒充正式成绩。 |
