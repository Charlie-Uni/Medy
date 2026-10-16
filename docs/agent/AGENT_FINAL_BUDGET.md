# Agent 最终引用核验预算

记录213，2026-10-16。属于AGENT-04预算切片与AGENT-05的终检接口准备；完整任务状态以[台账](../CURRENT_TASKS.md)为准。不是完整业务完成门、真实质量验收、付费授权或生产发布。

## 1. 实际入口与结果

AgentTools.verify_final_citations只供可信终态处理方使用；模型的七动作、四个可执行工具和普通execute路径不增加解锁动作。finish已经消费一个决策，run必须仍running、decision_index等于已消费数、完整context/binding一致。用只读prior视图复核原准入，不回退持久步数，也不产生第九步。

沿用原构造器的Skill/版本/身份/计量绑定、根预算快照与限额、绝对期限、当前来源/事实和输入安全。引用plans/执行仍经原Registry，不绕过原Handler/重试/事实回查。每个真实请求前继承原call_scope持有权guard并复核事实来源；真实持久Driver/取消/租约仍待，当前没有公共Agent端点或无操作生产默认实现。

私有FinalCitationBudgetResult包含action/binding、draft_sha256、引用检查payload、预算profile/原根快照及本阶段回执ID。没有status=completed字段。无指南claim时payload=None、max_calls=0；逐字支持或无judge时可以零模型请求，但仍走原Skill规则和最终事实栅栏。这些情况不等于整项任务完整或独立人工复核。

## 2. 预算如何得到

复用已实现的plan_verify：按当前授权事实筛选、原polarity_only判断路径取得实际ModelRequest，包含真实SYSTEM、原claim/原文、严格Schema、600输出上限、judge model及原timeout。免费分支不制造judge。一个attempt最多20个需要judge的claims，乘原幂等Registry最大3次attempt，最多60个逻辑调用槽；没有增加重试。

每个请求使用原UTF-8/schema/framing/最大输出估计和当前MeteredGateway.execution_prices，形成原CallEstimate。FinalizationProfile记录version、含请求/报价/根限额的plan_sha256、max_calls、estimated_tokens和estimated_cost_usd；不是供应商usage/发票。原计划受限审计保存请求正文；profile本身仅数值/摘要。

```text
最终计划Token = sum(按原重试上界展开的各请求预检Token)
最终计划费用 = sum(同一批请求按实际网关价格预检的费用)
最终计划两维 <= 根预算当前已安装的最终保护
```

不满足便在供应商前拒绝，不修改AgentProfile、增大原cap或使用空版本标签。该profile描述已知实际草稿；启动时未知草稿的完整预留仍须与AGENT-05最终检查形状共同推导，不把既有合成1,000 Token/50,000微USD当生产默认值。

## 3. 如何消费已保护的空间

finalization_scope需要原execution_scope/deadline、继承持有权检查、无在途调用、未进入过最终阶段；不能从一个正在执行的模型调用内部进入。请求必须未签发call_id，全部在进入前校验并报价。已安装保护为零、报价超出保护、期限/身份失效时不进入。

进入后在同一根ExecutionBudget内封闭普通消费，只给本阶段上下文对应的精确请求槽准入。每次原模型调用在同一把预算锁中执行：

```text
未消费的保护 P' = P - 本次请求保守额度 E
原在途调用预留 R' = R + E
已入账 A + R' + P' <= 原执行总限额
```

这不是把保护直接计成费用。仍通过原complete_in_execution/Meter/BudgetedGateway和月账本；嵌套同call只准入/结算一次。成功按真实usage/费用入账，未使用的请求上限不伪装成支出；已开始但未知usage照旧保守入账。按逻辑准入消耗槽，不因失败、零费用或供应商未开始就再生无限attempt。

除根cap外，实际已知/保守支出超出本最终计划整体报价时也保留全部记录、停止并拒绝输出；不得截断真实费用。未用到的重试槽/保护在退出后不授权普通调用，也不生成模型费用。

## 4. 请求绑定和并发

匹配模型、purpose、消息、Schema、最大输出、temperature等全部ModelRequest内容；原SDK兼容尝试仍归同一逻辑call，实际wire参数/逐attempt以原call_journal为准。call_id允许由原计量生成，timeout只允许按原规则缩短。调用时价格形成的额度也必须与槽报价相同。消息/模型/输出/Schema/费用变化、配额外调用在供应商前拒绝，当前阶段完整性故障锁存；不能用旧报价调用另一段证据。

只有本阶段上下文可消费槽，普通线程即使持同一根预算也拒绝；这种外来拒绝不毒化合法最终请求。复制了合法上下文的子线程仍共享同一锁、槽数、费用和根期限。阶段关闭后遗留线程不能再消费槽；已开始调用晚到时保留真实usage/费用及回执，拒绝其输出。没有承诺任意不合作插件或外部供应商调用恰好一次。

## 5. 阶段结束和追溯

状态只允许未开始→active→closed，每个根预算至多一次。success/异常/取消退出都closed，不能降回普通消费、重新安装保护或重新进入finalization。剩余保护与已入账/在途费用继续分列；finalization_snapshot记录计划、active/closed和已准入逻辑调用数，不是恢复凭证。

受限ExecutionAudit保留finish草稿、原重试计划、实际profile、引用结果与原Registry/model逐调用审计；普通遥测继续只有结构元数据。回执沿用run/attempt/final:action_id/原Skill attempt关联。接受结果前对照call_journal的实际请求归属字段，仅允许原月账本新增reservation_id，并核对已开始调用属于本run/trace/final动作和verify模型；异常回执保留用于诊断，不能作为有效最终检查。最后facts.final_check持有事实/身份栅栏，可信调用方须在该栅栏下原子保存并commit；方法返回不是保存成功。

预算组件execution-budget-v3+sealed-finalization、工具pv-tools-v4+final-citation-budget及真实contract SHA明确升级。旧context在首次规划/工具前失败关闭；原无最终阶段的Ask/Skill路径公式/价格/重试保持，36公开Schema和AgentProfile未改。

## 6. 仍未完成

完整任务/共同必需证据/叙述和业务安全门及原子终态保存归AGENT-05/06。本入口既不改变run终态，也不授权生产发布。启动时完整未知草稿profile还需据实际终检形状推导，当前无新默认数值。持久取消/租约/恢复要把原profile、费用、在途预留、步骤/重复计数、期限、阶段封闭和剩余槽一起一致恢复，当前尚未实现。

所有新增机制测试使用PUBLIC合成资料与fake供应商；临时PostgreSQL用例验证真实RLS/最终栅栏，没有修改正式事实库。尚无真实模型完成率、费用收益或医学质量结果；逐轮付费和盲测门保持。
