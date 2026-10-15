# 模型调用回执与费用归属

更新：2026-10-11。任务 ARCH-04/11/05；调用计量与迁移证据见[记录 175](reviews/2026-10-11-implementation-175-call-receipts-and-fee-attribution.md)，单次预算见[记录 176](reviews/2026-10-11-implementation-176-shared-execution-budget.md)，任务租约/尝试归属见[记录 177](reviews/2026-10-11-implementation-177-task-lease-and-ownership.md)。

## 1. 为什么需要调用回执

API、worker、MCP 和评测可共享一个月度预算网关。请求 A 失败前后，共享累计费用也可能因请求 B 完成而改变，因此不能把“共享计数结束值减开始值”当作 A 的费用。原反例中 A 应记 0.0000502 USD，却记成 0.0000753 USD。

每次逻辑网关调用现在有独立 `call_id` 和不可变回执。成功随 `ModelResponse` 返回；失败经 ContextVar 作用域传给本次 `MeteredGateway`，原异常继续传播。回执不挂到异常对象上，不依赖共享的最后一次结果。请求计量器按 call_id 去重，并用锁保护聚合。

这里的“一次调用”指网关的逻辑调用。OpenAI 适配器原有的 temperature 参数兼容重发仍在同一逻辑调用内；没有宣称每次物理 HTTP 尝试都有独立回执。

## 2. 身份与费用字段

| 字段 | 含义 |
| --- | --- |
| `call_id` | 本次逻辑模型调用的 UUID；重试产生新 ID |
| `trace_id` | Medy 业务 Trace；缺少执行上下文的直接网关调用可为空 |
| `run_id` | 执行身份；普通请求通常等于 trace_id，回放可另设 |
| `attempt_id` | worker 的 task/attempt 与 Harness operation_key/attempt，可按 `/` 嵌套；不是模型响应 ID |
| `reservation_id` | 本次月度预算预留的 UUID；调用供应商前产生，可用于结算不确定时查账 |
| `purpose` / `requested_model` / `provider` | 本次用途、请求模型及供应商适配器，不含 prompt |
| `estimated_cost_usd` | 调用前按现有价格表计算的预留金额；执行内取字节预检与旧月度估计的较大值，执行外仍沿用旧算法 |
| `actual_cost_usd` | 有供应商 usage 时的本地价格计算；未知时为空。它不是供应商最终账单 |
| `accounted_cost_usd` | 预算账本本次计入金额；已知时按本地计算，未知失败可能按预留保守计入 |
| `usage` | 本调用已返回的 input/output/cached Token；没有返回就为空，不能借用另一调用的 usage |
| `response_id` / `response_model` | 已返回的供应商响应 ID 与模型标识；完整输入、fingerprint 等复现材料仍归 ARCH-07 |
| `outcome` | 模型调用 succeeded/failed/cancelled/denied；不等同于整个业务任务成功 |
| `settlement_status` | not_required/settled/pending；pending 需要查库或人工对账，不触发模型重跑 |
| `error_type` / `settlement_error_type` | 原失败和结算失败的类型，均不保存异常消息 |

`MeteredGateway.cost_usd` 继续表示预算计入费用，以保持现有 Trace/实验接口兼容。`actual_cost_usd` 聚合已知本地计算费用，`conservative_cost_usd` 聚合保守预留；应连同 receipt 的 cost_basis 查看，不能把未知 usage 写成实际零费用。

## 3. 失败与停止的处理

| 情况 | 计量与停止行为 |
| --- | --- |
| 正常返回 | usage 与本地费用写入回执并结算，返回带回执的响应 |
| 已收到 usage，但结构化结果截断、无效 JSON 或非对象 | `ModelOutputInvalid` 保留内部响应，按已知费用结算；仍拒绝使用无效结果 |
| 供应商调用开始后超时/故障/取消，usage 未返回 | `conservative_reservation`；实际费用为空，预算计入预留金额，继续传播原失败/取消 |
| run/月度预算拒绝 | `not_started`、费用和调用数为零，未进入供应商 |
| 预留耗时导致总期限已过 | 未启动供应商，预留结算为零，传播期限错误 |
| 预留提交结果不确定 | `reservation_uncertain`、pending；未启动供应商，run 上限仍保守占用，保留 reservation_id 查账 |
| 模型完成但结算失败 | 保留已知 usage/费用，pending；以不重试的 audit_unavailable 失败关闭，避免再次付费 |
| 模型取消且结算失败 | 保留 cancelled 和 pending 回执，继续抛取消；结算故障不能让任务继续运行 |

`provider_started` 表示已经进入供应商适配器，并不保证供应商收到或收取了该请求。预留金额是本地估算，不是供应商计费承诺。单执行内的翻译、作答、判定和重试现在共享 §6 的预算；模型规划与候选生成尚未实现，后续必须通过同一入口。

## 4. 持久化、权限和迁移

必须先升级数据库，再启动使用新代码的 API、worker、MCP 或评测：

```sh
make migrate
```

目标为 Alembic head **0023**。迁移在原 `llm_spend_reservations` 增加 `call_context`、`call_receipt` 和调用/Trace 索引，以及两个只接受计量元数据的受控函数。预留身份与预留金额同事务写入，回执与结算同事务写入。它们使用独立短事务，不随问答事务回滚消失。

- 旧 reserve/settle 函数保留，旧应用可以继续运行；新预算网关需要 0023 的新函数，不能接仍停在 0022 的库。
- app 只能执行受控函数，不能直接读改费用表；只读/MCP 数据角色无此执行权限。MCP 翻译仍使用原有独立预算连接。
- 相同回执重放幂等；call_id、金额、身份或已保存回执不一致会被拒绝，预算不产生部分更新。
- 顶层字段、嵌套 usage 字段及类型受限；回执不保存 prompt、回答、证据正文或异常消息。普通 OTel Span 也只带计量元数据。
- 原月度金额与 `actual_usd` 列保留 numeric(14,6)，回执保留本地费用的更高精度。旧列 `actual_usd` 是历史命名，失败时也可能保存保守预算金额；查实际费用依据 JSON 的 actual_cost_usd/cost_basis。
- 旧预留的 call_context 为 `{}`、call_receipt 为 null；未生成历史回执。

2026-10-11 已将本机 `medops_v2`、`medops_v2_safety`、`medops` 从 0022 升到 0023；文档、块、ACL、策略/发布和原费用数据前后摘要一致。新旧迁移往返在临时库验证，本机事实库未降级。

## 5. 查询与对账

授权管理员可以按业务 Trace 查调用元数据。不要在普通 API/MCP 新增直接读账权限：

```sql
SELECT reservation_id, status, reserved_usd, actual_usd,
       call_context, call_receipt
FROM llm_spend_reservations
WHERE call_context->>'trace_id' = :trace_id
ORDER BY created_at;
```

处理 pending 时先按 reservation_id 查询：数据库可能已提交，只是确认丢失。已保存相同回执可幂等结算；若数据库未提交，原预留继续占用容量，需按供应商 usage/账单补充对账证据。不得因业务回答失败而直接退回保守金额，也不得重跑模型来完成结算。

目前没有自动供应商账单对账/预留修复器。数据库不可用且进程崩溃时，最终响应或 pending 回执仍可能丢失；库中已提交的调用身份及预留能定位，但不能保证恢复丢失的实际 usage。拒绝或未提交的预留没有持久回执行，启用遥测时可通过 Span 定位；完整执行审计与原条件复现仍由 ARCH-06/07 补齐。

回滚优先回退应用代码并保留 0023 的附加字段/函数。`alembic downgrade 0022` 会删除新调用元数据，虽然保留原费用与预留金额，也必须先导出回执并停止新写入；不能把数据库降级描述为无损回滚。

## 6. 单次执行共享预算（ARCH-11）

2026-10-11 所有者明确回复“采用现有规则推导的上限”。本轮沿用 12,000 Token，按仓库已准入价格表的最高单价 50 USD / 百万 Token 折算费用上限 0.60 USD；这不是重新查价或新的模型准入。Ask 总期限为六节点默认时限之和 125 秒。配置在 `.env.example`，实际 `.env` 未改动：

| 配置 | 默认值 | 作用 |
| --- | --- | --- |
| `LLM_EXECUTION_TOKEN_LIMIT` | 12000 | 一次根执行全部逻辑模型调用的 input + output Token |
| `LLM_EXECUTION_COST_LIMIT_USD` | 0.60 | 一次根执行的预算计入费用，包含未知 usage 时的保守金额 |
| `LLM_EXECUTION_TIMEOUT_S` | 125 | 根执行总期限；Skill 取本值与其原 SkillSpec 时限的较小值，MCP 检索取本值与原 20 秒时限的较小值 |

`execution_scope` 建立共享对象；嵌套 Ask/Skill 复用它，翻译线程与并行 Skill 经复制 ContextVar 引用同一对象，由锁保护预留和结算。子作用域不能换掉父对象，也不能扩大或重新计时；同一个对象离开再进入也保留原到期时间。嵌套参数不重新发放 Token/费用额度，局部节点仍受自己的时间限制。`execute_many` 对一批 Skill 只建一份额度；没有配置 profile 时其根期限按该批 Skill 时限之和推导，配置环境采用上表根期限。

### 6.1 调用前预留、调用后结算

1. 为全部消息、JSON Schema、固定 framing 余量和完整 `max_output_tokens` 计算字节预检。它比原字符 / 4 算法更保守，仍不是供应商精确 tokenizer。调用前同时检查“已计入＋所有正在执行的预留＋本次预留”是否超过 Token/费用限额。
2. 通过后才预留评测批次上限和 PostgreSQL 月度账本。嵌套 Metered/Budgeted 包装同一个 call_id 时只预留一次。执行内月度预留取新的费用预检与旧算法的较大值；嵌套计量器使用同一价格表。
3. 正常返回或无效结构化结果已有 usage 时，按回执计入实际 Token 和本地价格计算费用，释放未使用额度。超时、取消或供应商失败但未返回 usage 时，保守计入本次预留 Token 和费用；`known_tokens` 不伪装为预估值。
4. 月度拒绝或供应商尚未开始且预留结算为零时，不计 Token/费用。预留提交不确定仍保守占用金额、保留 pending 回执；不因未开始供应商而错误释放不确定的金额。
5. 某次调用不能预留时锁定本执行，后续调用不得继续。并发正在执行的调用仍须收束并结算，其结果不再变成可用回答。供应商意外报告的 usage/费用超过总上限时保留真实值、拒绝该响应、阻止后续调用；不能把已发生的供应商超额描述为可撤回。

翻译原有的失败降级逻辑保留，但不能隐藏共享预算耗尽：Ask 后续节点或 MCP 返回检查会以预算不足停止。两阶段 Skill 的证据作答和最终结构化调用、判定器、截断后的加倍输出重试、节点重试都共用额度。Skill 的预算失败归类为 `budget_exceeded`，不再误写成 `system_failure`。

原先“检索证据的估计 Token＋真实模型 input/output”会把证据重复计入；现在证据只用于上下文能否装入的预检，实际 `AgentState.budget.used` 在终态采用共享执行计入 Token。已成功操作复用时保留原结果中的历史用量，当前根执行的 Span/计量器单独记录新增调用为零；历史结果用量不是再次扣费。

### 6.2 入口与后续约束

| 入口 | 当前行为 |
| --- | --- |
| API Ask / worker Skill | 服务端配置 profile；BudgetedGateway 要求有效执行上下文，无上下文时在供应商前拒绝 |
| MCP retrieve | 服务端 profile，原 20 秒检索期限继续约束；翻译与费用回执沿用原连接/权限边界 |
| smoke_ask / skill_smoke / safety_run / replay_run | 采用同一配置与强制上下文；每题/每任务额度独立，原 `--max-cost-usd` 批次上限与月度上限同时适用 |
| 测试或直接调用 `run_ask` / Registry | 没有服务配置时按已确认旧规则推导；自动包装计量器，完整运行仍有共享额度 |
| 离线原件审查、术语提取、检索诊断等直接网关工具 | 未把这些批次工具改造为业务 Agent；原显式批次/月度上限继续有效，工厂默认允许旧独立调用。各付费运行仍须单独授权 |
| 新 Agent / 模型 Reflect/Adapt | 尚无运行时入口，不能称已接线或试跑。后续实现必须显式选择获准 profile、使用 `require_execution_budget=True` 的受控网关，并在最外层只建一次执行 scope；规划、工具内模型、修复及重试都在该 scope 内 |

### 6.3 范围和限制

- 执行预算对象目前在进程内，约束本次调用期间的嵌套、线程与重试。PostgreSQL 已持久化单调用回执/月度额度，但没有持久化可跨进程恢复的执行 profile、累计 Token 与截止时间。worker 接管是新根尝试；ARCH-05 已补当前租约/尝试责任；ARCH-06/07 与 Agent 契约仍须补完整恢复审计，未来持久 Agent 恢复不能直接重新发放一份额度。
- 参数兼容重发仍属于一个逻辑调用；未知物理 HTTP 尝试可能发生费用，不能保证供应商账单完全等于本地预留。月度精度和 pending 对账限制沿用 §4/5。
- `AgentState.TokenBudget` 的既有 Schema 不允许 used 大于 limit。意外超额不会截断成虚假的精确数字；完整超额值在共享预算快照和回执/遥测中保留，业务输出失败关闭。Schema 和冻结数据未改。
- 字节预检可能减少装入的证据或提前拒绝请求；其真实质量、成本和吞吐影响尚未重测，不等同于质量门禁通过。更精细 tokenizer 或新 Agent profile 需要另行评估。
- 期限是协作式截止时间，已开始调用的取消、资源回收与结算需要收束；不是任意代码的通用强杀承诺，也不是原 P95 8 秒 / 15 秒性能目标。
- 本轮只有离线网关、数据库和代码验证；0 次托管模型调用、0 USD。所有付费实验、生产发布与独立人工要求不变。

## 7. 任务接管、失租与重复费用

`task_id` 是稳定任务身份；`attempt` 是每次领取递增的编号，worker ID 不能单独作为栅栏。每个 attempt 有独立 Trace/run；调用回执的 `attempt_id` 以 `task:<task_id>:<attempt>/…` 连接内部节点尝试。`TaskExecution` 报告本 worker 的 `completed / failed / lost`，公开 API 继续返回当前任务状态，两者不能混用。

模型调用前用独立短事务验证当前 owner、attempt 与未过期租约，月度费用预留等待后再次验证；可确定尚未开始的调用结算为零。失租之前已经返回 usage 的费用按原尝试记录；已经发出但没有 usage 的调用保留保守费用。旧 worker 返回时，将自己的 Trace 写入原 lost attempt，不能覆盖新结果或清空旧费用。硬崩溃无法补写 Trace 时，0023 账本中的调用上下文/回执仍可关联原 task/attempt，pending 需对账。

单执行 12,000 Token / 0.60 USD 当前作用于一个 attempt；接管会创建新执行预算，并非已实现跨进程恢复同一预算。默认最多 3 次尝试，重跑的费用与旧尝试累加受共享月度账本限制；不能把 0.60 USD 声称为整个任务生命周期的硬账单上限。相同 run 的安全复用与新 attempt 自动重做也不同。未来 Agent 恢复、完整证据审计和回放继续按 ARCH-06/07 与 Agent 契约处理。

在一次持有权检查与真正发送之间，进程仍可能被暂停；已发送请求也不能由数据库撤回。因此执行截止、请求超时、写入栅栏、调用回执提供有界执行与可解释记账，不提供供应商“恰好一次”保证。当前 Skill 为读取/判断；新增业务写工具需另外设计事务栅栏/幂等契约。

## 8. 2026-10-15 Agent设计确认与尚未接线的边界

[PLAN-02 v0.2](agent/PLAN-02-action-budget-and-acceptance.md)已获所有者同意：新Agent设计共享12,000 Token / 0.60 USD / 125秒，加入结构化规划/有界证据/合法复用/最终核验预留；分配比例/Token预留数尚未固定，工程必须按实际锁定调用上界算出，不承诺走满8步。此批准不修改本文件§6/7描述的现有Ask/Skill运行时，也不授权模型试跑。

最小澄清保存业务case后结束当前执行，用户显式续办创建关联新task/run，核查权限/版本/并发/期限/授权，旧费用保留并显示case累计；同一授权批次上限不能因新task重置。case TTL/续办次数等需显式配置，缺少配置或费用授权则模型前拒绝。新run不等于恢复旧run；真正故障恢复需持久化原额度/预留/步骤/截止/持有权，超期不恢复，不重新发一份额度。上述均待AGENT/SESSION实现和反例验证，不能把本段视作已存在的数据库原子预算恢复。
