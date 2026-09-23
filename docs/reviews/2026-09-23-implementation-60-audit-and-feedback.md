# 实现记录 60：Trace 与升级记录落库、反馈接口（M3-07 首切片、M3-03 部分、M2-10 收口）

- 日期：2026-09-23（夜）
- 范围：每个请求（同步问答与任务执行）在请求事务内写一条 Trace 摘要与全部节点 span；未回答的运行写升级记录（问题、证据 chunk id、Verifier / Safety 结果、策略版本、最小上下文），可由管理角色改状态接手；审计写失败即 `503 audit_unavailable`、不返回医学答案；`POST /v1/feedback` 把用户信号绑定到本人的 Trace，支持 Idempotency-Key 回执。
- 依据：基线 2.5（INV-OBS-01/02/03）、4.2（`traces/trace_spans`、`escalations`、`feedback/bad_cases`）、5.5（Escalation 保存内容）、5.10（「Trace 写入失败不能导致无审计医学回答」）、§8 M3-03/07、M2-10；`docs/api/CONTRACTS.md` 反馈接口语义。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| Trace 与答案同一事务：`run_ask` 之后、响应之前写 `traces` + `trace_spans`（+ `escalations`）；存储抛任何异常都转成 `audit_unavailable`（可重试）并回滚，客户端得到 503 而不是答案 | 5.10 明文；测试证明答案文本不出现在失败响应里 |
| Trace 里不存证据正文，只存 chunk id（证据、被引、被筛掉三组）、版本集、reason codes、调用数 / token / 费用 / 时长；问题原文保留（人工接手与回放需要） | INV-OBS-03 受限载荷分离；5.5 升级记录必须含问题 |
| 费用与 token 用每请求的 `MeteredGateway` 计量（生产运行时在 `build_deps` 中包装）；无计量时退回 Trace 预算已用 token | INV-OBS-01「调用、耗时、Token 和成本」 |
| 升级记录 `escalation_id = trace_id`（与 API 回执一致），内容不可变，只有管理角色能改 `status / handled_by / handled_at`（open → acknowledged → closed，closed 不可逆）；应用角色对四张审计表只能追加 | INV-OBS-02 审计追加写、普通业务角色不可改；M2-10「可由人工接手」 |
| 反馈只接受本人 Trace（否则 `404 not_found`）；Idempotency-Key 作用域与任务相同（principal + 路由 + key），回执存 `idempotency_keys.receipt`；correction 必带文本的规则由契约模型校验 | CONTRACTS 反馈行；3.2 幂等 |
| worker 执行任务同样写 Trace（kind = task，span 为 Skill 的 attempt），与任务结果同一事务 | INV-OBS-01 覆盖异步路径 |

## 2. 交付

- 迁移 `0011_traces.py`：`traces`、`trace_spans`、`escalations`、`feedback`；追加写触发器、升级状态守卫、FORCE RLS、按角色授权。
- `src/medops/application/audit.py`：`TraceRecord` / `EscalationRecord` / `FeedbackRecord`、`TraceStore` 协议、`trace_from_run`、`record_or_fail_closed`、`FeedbackService`、`InMemoryTraceStore`；`src/medops/infrastructure/db/audit.py`：`PgTraceStore`；`src/medops/infrastructure/llm/meter.py`：`MeteredGateway`。
- `medops.api.app`：`/v1/ask` 计量 + 落库 + fail-closed；`POST /v1/feedback`（201）；`ApiRuntime.trace_store`；`ProductionRuntime` 每请求计量网关与 `PgTraceStore`；`TaskRunner` 写任务 Trace。
- 测试：路由 4 项（每次问答留下含五个 span 的 Trace、拒答留下升级记录、审计失败 → 503 且无答案泄漏；反馈回执 / 幂等 / 不匹配 / 他人 Trace 404 / correction 规则 / 401）、worker 1 项（任务 Trace）、集成 2 项（Trace + span + 升级同写且应用角色不可改、管理角色只能改状态、只读无权限；反馈绑定与回执幂等竞争、约束）；迁移清单、往返、RLS 集合更新到 0011。`make check`：1070 项通过。

## 3. 未做 / 限制

- 受限可回放载荷（证据正文、模型原始输入输出）尚无单独加密存储；当前 Trace 只有 chunk id，回放（M3-08）需重新取证。
- Langfuse / OTel（M3-09）与指标告警（M3-10）未接；日志脱敏沿用 M0 的 `core.logging`。
- 反馈只落库，未接 Loop（M4）的归因；管理端查看升级队列的接口随 M3-03 其余部分。
- 真实库端到端（含审计表）仍待 medops_v2 应用迁移后一并做（记录 59 §3 同一事项）。

## 4. 自审（§9）

- fail-closed 由测试证明（存储抛异常 → 503 `audit_unavailable`、`retryable=true`、响应不含 claims 与内部错误文本）。
- 应用角色对审计表只有 insert / select（数据库层证明），管理角色只能改升级状态字段（触发器证明）。
- 未存证据正文；身份为假名；未改动已冻结数据与生产库。

## 5. 进度

- M3-07 部分、M3-03 部分（反馈）、M2-10 已实现（升级记录持久化且可接手）。P0 加权进度 51.3%（40.5/79）；按 99 项计 40.9%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 4/13、M4 0/10、M5 0/8。
