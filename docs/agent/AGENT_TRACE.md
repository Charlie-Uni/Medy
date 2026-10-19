# Agent 持久业务 Trace 与反馈

2026-10-19记录223最新进度：当前条件诊断与差异报告已接入真实运行器，完整CI及八项工程自审已通过，AGENT-06 DONE；后续SESSION/集成/真实试跑仍待；[回放契约](AGENT_REPLAY.md)。本页后续记录220～222的原状态保留为当轮历史。

2026-10-19，AGENT-06记录222。本切片八项工程自审通过，AGENT-06整体IN_PROGRESS。继记录220运行元数据和221受限历史读取，接入既有append-only Trace与反馈；诊断回放仍待。

## 1. 什么时间产生 Trace

真实业务终态写入时，在同一数据库事务内保存受限终态事件、封闭run control并INSERT一条kind=agent的Trace。Trace失败、标识冲突或事务回滚不能对外确认完成，已保存材料不会被改写或覆盖。提交确认丢失仍按原规则标为未确认，之后授权读取可查实际结果；不重发模型或重新计费。重复finish/result不再插入。

模型提出finish、仅保存最终检查点、异常退出但未保存业务终态均不补造业务Trace，继续由持久control/runtime及OTel定位。旧Agent终态不自动回填。不是每个span对应一行traces，也不把Agent决策伪装成Harness node attempts。agent_runtime仍保存真实行动路径、短理由和调用/工具材料。

## 2. 原字段与明确的新元数据

0032增加可空agent_metadata并扩展kind=agent；只有Agent可用awaiting_clarification/cancelled，其余原kind/outcome约束保持。metadata须带pv-agent-trace-v1标记，应用投影为固定字段模型；不增加公共API/Schema、默认模型或数据库授权。

| 字段 | 语义与边界 |
| --- | --- |
| trace_id/run_id/task_id | 原业务Trace、原执行UUID的hex格式及任务UUID；不生成新的回放执行身份 |
| outcome/reason_codes | 原completed/awaiting_clarification/escalated/failed/cancelled及闭集停止码，不把澄清或系统失败算回答成功 |
| query | 空串；不复制PV叙述、任务要求、问题或文件描述 |
| versions | 兼容旧消费者的原VersionSet；metadata.versions另保留完整AgentVersions及实际Prompt/工具/核验/事实摘要 |
| evidence_chunk_ids/cited_chunk_ids | 最终授权registry及已支持AND/OR证据组的chunk标识，去重；不存正文，不以所有检索结果冒充已引用证据 |
| model_calls/tokens/cost_usd | 原累计逻辑调用、accounted Token与accounted USD（旧列六位小数）；不是本次进程增量、供应商HTTP次数或完整账单 |
| duration_ms | 原业务起止的墙钟间隔，包含恢复间隔；不是OTel活跃时长或新时延验收证据 |
| agent_metadata | 原case/task/run/attempt、context摘要、真实终态事件/材料指针与摘要、实际版本、决策计数、原预算检查点、显式预算数值摘要、pending计数及起止时间 |

accounted/known/reserved三组Token与USD在metadata原样保留，不把预留当已知零费用。accounting_complete仅表示没有pending allowance，不等于供应商usage已完全已知或账单已对账。原USD精度保留在metadata；不重新定价、扩大额度或重开预算。

新投影不复制narrative、要求/文件描述、行动理由、问题、prompt/messages、模型回复、证据文本、异常消息或凭据。版本名、UUID、hash和固定预算字段用于追溯，不等于来源真实性证明或原事实/原条件可复现承诺。既有35模型/描述、OpenAPI及旧写入路径保持；非Agent默认metadata=None，SQL不引用新列，可继续写0031及原支持的旧数据库。

## 3. 使用原反馈入口

`POST /v1/feedback`继续按当前鉴权与Trace主体所有权工作，支持up/down/correction及既有Idempotency-Key。原主体的三类交付终态可反馈；外人404、匿名401、撤权拒绝。Trace/终态未提交时不能通过另一个HTTP事务看到或留下反馈；提交后可用原未成功的key再次提交。保存反馈不触发模型、自进化候选或重跑。

既有feedback harvest/ScoreQueue保留同一trace_id、稳定score ID与事实库命名空间，恢复/重复扫描不改ID或重复入队；导出不选择query/correction_text。此处证明本地持久排队，未声称真实Langfuse后端收到新Agent反馈或UI已验收。记录220的实际元数据OTLP装配保持，未配置仍可NoOp。

Observe现有CASE_KINDS仍只含ask/task，新Agent信号不会被旧规则当作既有Prompt调优材料。S3模型候选生成、合格未见盲测及实验限定激活继续独立推进；本轮不扩展自动化范围。升级仍用原Agent受限回执，不创建或冒称旧Ask分派工单。

## 4. 读取、回放与回滚

管理员按[用途审计契约](AGENT_AUDIT.md)读取真实Agent材料；旧/admin/traces payload不是新Agent原件入口。原Ask Replay仍须在构建依赖/调用模型前拒绝kind=agent；本轮没有实现Agent诊断回放、原条件复现或同run澄清恢复。

0032没有Agent Trace时可以退0031；有保留的Agent Trace/反馈时明确拒绝降级，不能删改审计以通过迁移。代码回退后旧非Agent写入仍不引用新列。迁移只验证临时库，正式库未升级或部署。

验证、原失败及八项自审见[记录222](../reviews/2026-10-19-implementation-222-agent-business-trace.md)。整体AGENT-06仍待诊断回放及明确的原条件拒绝边界；SESSION最小续办、AGENT-07/08和真实质量/容量/盲测仍各自验收。
