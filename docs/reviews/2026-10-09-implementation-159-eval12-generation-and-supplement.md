# 记录 159：EVAL-12 首轮生成结果与补充面板

日期：2026-10-09。状态：**首轮与补充生成完成；提示词 JSON 裁判两轮均因 `ms-0242` 的无效结构按授权规则停止；本记录准备的 JSON Schema 后续请求随后已完成，最终结果见[记录 160](2026-10-09-implementation-160-eval12-structured-review-complete.md)。**

## 1. 实际运行

按记录 158 和用户对第一阶段的明确授权，使用发布配置在 `main-v5-provisional` 上运行十题校准面板：

- 输出：`evals/harness/runs/2026-10-09-eval12-calibration-v1-generation`；
- 数据集：`main-v5-provisional`，dataset hash `23bf8530…842b0`；
- 运行条件：`e1d3fac…7797`；
- 策略：`policy-m2-smoke-1+rel:3361ed13`；
- 检索版本：`2c872c44…47d05`；
- 模型配置：answer/judge=`gpt-6-sol`，query translation=`gpt-6-luna`；
- 上限：0.35 USD，进程内调用前预留；
- 结果：10/10 终态、0 system failure、30 次模型调用、实际 0.085875 USD、P95 14.49 s。

PostgreSQL 持久月度账本在运行后读数为 0.085876 USD。它与运行逐行费用之和 0.085875 USD 的差异仅为六位小数向上取整；没有未结预留或未知费用迹象。

| 样本 | 结果 | gold cited | 费用 USD | 说明 |
| --- | --- | ---: | ---: | --- |
| `ms-0012` | escalated / unsupported_conclusion | 否 | 0.012223 | 候选回答 400 mg；verifier 忽略 query 已限定血透且 CrCl<30，将其他条件的 800 mg 当成反证 |
| `ms-0056` | answered | 是 | 0.012242 | 正常回答 |
| `ms-0149` | answered | 是 | 0.007609 | 正常回答 |
| `ms-0177` | escalated / unsupported_conclusion | 否 | 0.007082 | query 已给“若选择请求”的条件，verifier 仍以 may/应 的表面差异否决 |
| `ms-0227` | escalated / unsupported_conclusion | 否 | 0.007045 | query 已给“无法取得年龄”的条件，verifier 要求答案重复该前提 |
| `ms-0242` | answered | 否 | 0.008164 | 有答案，结构 gold 未覆盖；正是语义/完整性裁判要区分的案例 |
| `ms-0298` | answered | 否 | 0.009087 | 有答案，结构 gold 未覆盖 |
| `ms-0338` | answered | 是 | 0.005647 | 正常回答 |
| `ms-0440` | answered | 否 | 0.011504 | 五组 gold 的长上下文案例 |
| `pc-0068` | escalated / insufficient_evidence | 否 | 0.005272 | 检索中出现 E6、E8 材料，但最终引用未共同支持两份文件的关系 |

这些是开发集诊断，不是总体准确率或正式门禁。首轮结构结果为 6 answered / 4 escalated；`answerable_answered_rate=0.556` 等 runner 指标继续按 main-outcome-v2 原口径保留。

## 2. 为什么不能直接进入模型裁判

记录 158 在付费前明确写了“至少 8 道得到 answered”。本轮只有 6 道。虽然计划 JSON 的 `minimum_cases=8` 字段较宽松，不能在看到结果后采用较松字段覆盖已经公开的严格完成条件。

因此：

- 十题运行和费用审计本身完成；
- EVAL-12 第一阶段验收未通过；
- 不启动 Claude Opus 5 裁判；
- 不重复运行同一四道升级题来碰随机结果；
- 原四条升级仍留在完整性分母，不被替补题删除或替换。

## 3. 快照与报告核验

十条运行行与原计划 ID、顺序完全一致；十份 `answer-review-input-v1` 快照均存在、哈希通过，`rows.jsonl` SHA-256 为 `c9ce5386…e1b7d`。零费用 pending 报告位于 `evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-pending.json`：

- 10 cases；
- 8 个 claim occurrence 待判断；
- 10 个 citation occurrence 待判断；
- 6 个 answered case 的完整性待判断；
- 4 个 answerable escalation 已按 rubric 固定计为 incomplete。

`answer_review.py` 原先要求输出父目录预先存在，实际生成 pending 报告时触发 `FileNotFoundError`。工具现在自行创建父目录，并增加回归测试。它还支持从多个独立运行目录合并快照，记录每个 `rows.jsonl` 和 snapshot hash，并拒绝重复 sample ID，供补充运行后无复制聚合。

## 4. 零费用补救方案

新增 `evals/answer_quality/calibration-v1-supplement-plan.json`，SHA-256 `f1736e59…bf17`。精确选择四道一组 gold、直接可回答的问题：

| 样本 | 补充维度 |
| --- | --- |
| `ms-0001` | MA、点名产品、剂量 |
| `ms-0099` | PV、英文、点名法规字段 |
| `ms-0104` | PV、中文、时限 |
| `ms-0317` | CO、英文、CFR 时限 |

补充面板有意偏向高概率可作答的短问题，只用于取得至少两个新增可裁判答案，不估计总体表现。完成条件为：合并后 answered 至少 8；补充行快照齐全；无 system failure；原十题与四条升级全部保留。

建议运行上限 0.15 USD，达到上限在调用 provider 前停止；任何 provider/system failure 或事实平面漂移停止。该范围超出原十题授权，必须单独获得用户批准。原 0.35 USD 上限的未使用部分不自动授权新增样本。

后续 Claude 裁判仍是另一笔独立授权；在补充方案准备这一阶段没有调用 Claude，也没有生成语义 verdict。后续实际执行见第 7 节。

## 5. 补充运行结果

用户单独授权四题补充生成最多 0.15 USD 后，运行目录 `evals/harness/runs/2026-10-09-eval12-calibration-v1-supplement` 完成：

- 4/4 answered、4/4 gold cited、4/4 exact review snapshot；
- 10 次模型调用、0 system failure；
- 实际费用 0.027149 USD，P95 10.75 s；
- 四题 ID 与顺序精确匹配补充计划；事实开始/终检均通过。

PostgreSQL 月账本由 0.085876 USD 增至 0.113025 USD，增量与补充运行 0.027149 USD 精确一致。两次运行文件逐行费用合计 0.113024 USD；与月账本的一百万分之一美元差异来自每次账本结算向上取整。

合并后共有 14 个案例：10 answered、4 escalated，已达到预登记至少 8 answered。合并 pending 报告为 `evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-combined-pending.json`，包含 12 个 claim occurrence、14 个 citation occurrence、10 个待裁判完整性项；4 个升级案例继续固定计为 incomplete。

## 6. Claude 裁判精确请求

新增：

- `evals/harness/tools/prepare_answer_review.py`：从一个或多个已绑定运行生成零调用请求；少于 8 个 answered 时拒绝准备；
- `evals/harness/tools/run_answer_review.py`：重建 run/case/prompt hash，校验项目所有者的独立授权文件，逐 case 调用 tools-off Claude CLI，持久保存预算、原始私有 CLI 产物、verdict 和 checkpoint；
- `evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-request.json`：请求 SHA-256 `300721bc…e5df`。

请求精确绑定 10 个 answered case，合计提示 125,250 字符。建议范围沿用原计划：Claude Opus 5 / high、每 case 一个独立会话、最多 10 次；CLI 每次停止阈值 0.28 USD，账本每次预留 0.30 USD，总上限 3.00 USD。CLI 阈值并非供应商最终结算的绝对硬上限；若任一实际调用超过 0.30 USD、失败、回复无效、模型不符或费用未知，账本保留该尝试并停止，不能在同一授权下自动重试。

项目所有者随后明确授权最多 10 次、总费用上限 3.00 USD。授权文件为
`evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-authorization.json`，SHA-256
`52943ac0…f041`；它精确绑定请求、模型、10 个 sample ID、逐次预留和失败停止条件。

## 7. Claude 裁判部分运行与停止原因

执行目录为 `evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-claude-review`。实际发起 3 次调用：

| 样本 | 结果 | 账本费用 USD | 说明 |
| --- | --- | ---: | --- |
| `ms-0056` | validated | 0.073723 | claim、3 个 citation occurrence、完整性均通过结构和 rubric 校验 |
| `ms-0149` | validated | 0.066435 | claim 和完整性通过；第 2 个 citation occurrence 判为 `not_supported` |
| `ms-0242` | invalid | 0.056142 | provider 成功返回，但顶层缺少 `citations`，并把引用判断错放进 `claims` |

累计账本费用为 0.196300 USD；3 次均有明确费用，没有未知扣费或未结预留。第三次的运行错误原文为：

```text
RuntimeError: ms-0242: review stopped after a nonvalidated call
```

底层校验错误为：

```text
ValueError: answer-quality model reply has unexpected fields
```

这不是 Claude CLI、模型选择或传输失败。外层 CLI JSON、模型身份和计费信息均有效；无效的是模型正文没有遵守预先声明的三顶层字段契约。执行器没有猜测或搬移字段，也没有把这次输出计为 verdict。根据授权中的 `stop_on_nonvalidated_attempt=true` 和 `automatic_retry=false`，程序在此立即停止，未调用后续 7 条。原授权已经消费一次失败尝试，不能据剩余额度自行重试。

两条有效 verdict 保留在 `verdicts.jsonl`，并由原 case hash、prompt hash、模型和 rubric 版本约束。三份私有 CLI 原始产物权限为 0600；公开记录只保留结构性失败说明及 SHA-256，不复制正文。

## 8. 八条后续请求

工具升级为 `answer-quality-review-request-v2`：后续请求可以选择未完成案例，同时绑定先前停止运行的 `run.json`、`budget.json`、`verdicts.jsonl` 和每次调用产物哈希。最终报告会合并先前 2 条与后续 8 条，但新预算只计算后续调用。任一先前文件、有效 verdict、费用记录或调用产物变化都会在调用前拒绝执行。

后续请求：`evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-followup1-request.json`，SHA-256 `66b4140a…1916`。范围按原顺序固定为：

1. 重试 `ms-0242`；
2. 首次处理 `ms-0298`、`ms-0338`、`ms-0440`、`ms-0001`、`ms-0099`、`ms-0104`、`ms-0317`。

请求合计 8 次、101,541 个提示字符；Claude Opus 5 / high、每条独立 tools-off 会话、CLI 单次停止阈值 0.28 USD、账本单次预留 0.30 USD、新总上限 2.40 USD。它不是原授权的自动续跑，尚未生成授权文件，也没有发起新调用。

## 9. 第一次后续运行

项目所有者按第 8 节的精确范围授权最多 8 次、总费用上限 2.40 USD。授权文件
`evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-followup1-authorization.json` 的 SHA-256 为
`c26a0dd7…d6c2`。

运行在第一条 `ms-0242` 再次停止：

- Claude CLI 正常结束，`returncode=0`、`subtype=success`、模型为 `claude-opus-5`；
- 实际费用 0.056092 USD，无未知费用或未结预留；
- 回复正文不是合法 JSON，在 `completeness` 前缺少关闭 `claims` 数组所需的结构；
- citation 判断再次被直接接在 `claims` 数组中，没有生成顶层 `citations` 字段；
- 没有新增有效 verdict，后续 7 条没有调用。

该轮目录为 `evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-claude-review-followup1`；私有调用产物 SHA-256 为 `888acb15…76c6`，权限 0600。两轮 Claude 账本费用累计 0.252392 USD。虽然授权金额尚有余额，`stop_on_nonvalidated_attempt=true` 与 `automatic_retry=false` 使该授权在这次失败后终止，不能继续处理剩余案例。

## 10. 结构化输出修复与第二次后续请求

两次结果说明仅靠提示词无法可靠维持输出协议。Claude Code 2.1.79 本机 CLI 提供 `--json-schema`；执行器现在把每个案例的动态 Schema 传给 Claude，并在请求、预算身份、调用元数据中记录 Schema SHA-256。Schema 强制三个顶层字段、对象字段、类型、枚举和 `additionalProperties:false`；原有本地校验器继续负责精确数组长度、索引唯一性、非空理由和 rubric 语义。案例、rubric、system prompt 与每条原 prompt hash 均未改变。

按 Anthropic 当前结构化输出限制，Schema 没有使用 `minimum`、`maximum`、`minLength`、`maxLength`、`maxItems` 等不受支持的约束，`minItems` 只取 0 或 1。工具内增加相同的调用前检查，防止以后重新引入这些字段而浪费付费调用。

第二次后续请求为 `evals/answer_quality/reviews/2026-10-09-eval12-calibration-v1-review-followup2-request.json`，SHA-256 `6e6d0503…e276`。它同时绑定：

- 两个先前停止运行及累计 0.252392 USD 费用；
- `ms-0056`、`ms-0149` 两条有效 verdict；
- `ms-0242` 两次无效尝试及各自私有产物哈希；
- 重试 `ms-0242` 和首次处理其余 7 条；
- Claude Opus 5/high、最多 8 次、每次预留 0.30 USD、新总上限 2.40 USD；
- 逐案例 Schema hash 和调用后 Schema 元数据一致性检查。

该请求尚无授权文件，也没有调用模型。

## 11. 自审

| 自审项 | 结论 |
| --- | --- |
| 需求与范围 | 通过。两次生成和两轮 Claude 调用分别匹配授权；每次失败后都没有自动重试。 |
| 正确性与失败路径 | 通过。两次 `ms-0242` 无效输出均已计费、保留原始产物且未计入 verdict；第二次后其余 7 条未调用。 |
| 权限与可追溯性 | 通过。第二次后续请求绑定 14 个 case、8 个待处理 prompt、2 个先前 verdict、4 次费用记录、私有调用产物和逐案例 Schema hash；模型意见没有冒充第二人工。 |
| 验证 | answer review 与调用预算定向 36 passed；v1、v2、v3 三版请求均能重建，v3 能合并两个停止运行。隔离环境全量 `make check` 通过：1711 passed、70 skipped，ruff、438 个文件格式、mypy、评测审计和 schema 均通过，仅保留既有短 HMAC 测试警告。 |
| 状态与文档 | 通过。EVAL-12 保持 PAID/部分完成；受 JSON Schema 约束的 8 条裁判等待新的 2.40 USD 明确授权。 |

以上第 11 节是后续请求执行前的自审快照。项目所有者随后完成授权；执行、适配器恢复、最终费用和指标以记录 160 为准。
