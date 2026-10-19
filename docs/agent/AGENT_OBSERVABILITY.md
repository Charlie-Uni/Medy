# Agent 运行遥测：元数据切片

2026-10-19，AGENT-06，记录220。本切片八项工程自审通过；整体AGENT-06 IN_PROGRESS，尚待受限审计与回放。依据[行动契约](PLAN-02-action-budget-and-acceptance.md)、[持久运行](AGENT_RUNTIME.md)和[业务终态](AGENT_TERMINALS.md)。

## 1. 实际接线

复用现有OpenTelemetry与Langfuse OTLP配置，无新遥测后端/模型配置。未配置exporter时保持NoOp；配置后由同一生产SDK发送新spans。

| Span | 范围与关联 |
| --- | --- |
| agent.execution | 一次持有租约的执行会话，包含原清理/结算；不是跨重启一直存活的内存span |
| agent.loop | 当前运行或恢复后的模型循环 |
| agent.plan | 一次实际规划尝试，包括原准入、供应商调用和返回检查点；带真实decision_id/index |
| agent.tool | 已准入工具执行与提交；带原action名、UUID和decision index |
| agent.final_review | finish材料核验或已提交审核材料复用 |
| agent.terminal | 最终核验、财务对账和业务终态保存确认；失败不标完成 |
| agent.result | 已保存终态的重复finish读取，退出原会话后仍绑定原业务Trace |
| llm.call | 复用既有逐调用记录、用量、费用与错误类型，父节点为实际规划/工具/终检 |

agent.execution/loop/plan/final_review/terminal映射Langfuse chain，agent.tool映射tool。未改既有Ask/Skill/MCP的span分类。时间是本次进程中实际span时长，不补造跨进程停机时长或旧丢失span。

## 2. 身份、版本与恢复

业务trace_id直接来自已绑定AgentContext，与持久runtime事件相同。case/task/run/attempt采用实际UUID，租约代数取真实AgentLease；版本标签复用现有run_metadata，额外导出实际planning_prompt/tool_contract/verification_policy/fact_conditions SHA-256与事实库UUID。

恢复后使用同一业务Trace、新span_id及新lease_generation；不会重用已结束span或重开原预算。已有不同Trace的HTTP/调用者父节点以Link关联，退出后恢复原上下文。真实独立Python进程读取原runtime验证此关联，供应商为Fake。

源码工件摘要会随新增代码变化；生产的原条件绑定仍失败关闭，不将旧context静默重绑为新代码。Span不是签名工件、不可变事实库快照或持久审计替代品。

## 3. 计量与状态

- model_calls_total：原共享预算中的累计已开始逻辑调用；恢复前的调用保留。
- model_calls_this_session：从本次会话开始的原预算调用数差值。恢复复用已保存回复可为0，而total仍大于0。不是HTTP发送次数。
- accounted/known/reserved Token与USD分别导出，不把未知费用写成已知零；均为原预算快照累计值，不另行定价或扣款。
- business_committed仅表示本实例确认保存了业务终态，包括明确的失败终态；成功必须同时检查business_status=completed。
- handoff_reason记录本次循环实际返回的闭集停止码；业务结果未保存时也能定位预算等停止原因，系统失败码标ERROR。
- 内部run返回reason=completed仅为finish申请；未完成业务保存时business_committed=false、business_status=unconfirmed。
- 提交回滚或确认丢失仍报unconfirmed，即使数据库可能已经提交；后续授权读取可查实际结果，遥测不猜测提交成功。
- 已保存的failed状态即使没有异常抛给调用者，也标为ERROR及固定停止码。执行异常仅输出固定错误码/异常类型，不输出异常消息。exception_raised表示Python异常边界被触发。

## 4. 正文与权限边界

新增投影只显式选择UUID、SHA-256、闭集动作/状态/停止码、布尔和数值。叙述、要求描述、完整Action/State、行动理由、问题、指南/患者事实、证据文本、prompt/messages、模型回复、SDK正文、密钥和异常消息都不能进入新增spans的属性、名称、事件或错误描述。

这些正文仍只在现有加密runtime/受限审计中；本切片未扩大任何数据库授权或公开正文读取能力。禁止将任意model_dump/Exception字符串递归传入telemetry。已有目录/ACL/来源/版本检查和最终事实栅栏继续执行。

遥测采用现有SDK交付语义；没有证明后端收到全部spans，也没有将遥测作为业务完成凭证。进程硬退出前未导出的span可能缺失，不能据缺失span推断没有调用；持久准入和费用回执才用于对账。

## 5. 验证和后续

真实临时PG＋离线Fake供应商＋OpenTelemetry InMemory exporter，覆盖父子关系、实际ID/版本、原调用数/预算、成功/澄清/升级/超时、内部handoff、提交回滚/确认丢失、外部父Trace、重新装配与独立进程恢复、无exporter及退出后重复读取。原核心OTel测试另验证本地HTTP OTLP/脱敏协议；本轮没有向真实Langfuse后端执行新排障演示。

记录221已完成[管理员用途审计读取](AGENT_AUDIT.md)，本切片工程自审通过。AGENT-06后续仍含持久业务Trace/反馈入口、诊断回放接线及原条件不可恢复时的明确拒绝。完整任务保持IN_PROGRESS。SESSION最小续办、真实质量/性能、正式部署和未见盲测仍分别验收。

实际命令、原失败、复测与八项自审见[记录220](../reviews/2026-10-19-implementation-220-agent-runtime-observability.md)。
