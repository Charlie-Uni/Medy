# 模型调用回执与费用归属

更新：2026-10-11。任务 ARCH-04；实现、自审及迁移证据见[记录 175](reviews/2026-10-11-implementation-175-call-receipts-and-fee-attribution.md)。本说明覆盖调用计量，单次执行的统一 Token/费用预算仍归 ARCH-11。

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
| `estimated_cost_usd` | 调用前按现有价格表和 Token 估计器计算的预留金额 |
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

`provider_started` 表示已经进入供应商适配器，并不保证供应商收到或收取了该请求。预留金额沿用原估算算法，不是供应商计费承诺。ARCH-11 将进一步把单执行内的翻译、规划、作答、判定和重试统一纳入预算。

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
