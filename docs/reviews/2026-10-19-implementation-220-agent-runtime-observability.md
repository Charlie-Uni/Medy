# 记录220：AGENT-06运行遥测与恢复关联

日期：2026-10-19。任务ID：AGENT-06。实现者/真实审核者：Codex（自审，不是第二独立人工）。基线8e1c7d2653a85de9fb94fa08fbcfab6232b84921。

状态：本切片工程自审通过，整体AGENT-06 IN_PROGRESS。本轮主切片是生产Agent的元数据Trace树、耗时、真实版本与调用计量、恢复关联；整体AGENT-06不在本轮标DONE。用户要求“继续推进Agent06”。0托管调用/0USD，无正式迁移/重启/部署或候选发布。

## 1. 前置、范围与实现

以[当前台账](../CURRENT_TASKS.md)、[阶段§3](../ITERATION_STAGES.md)和[迭代计划](../ITERATION_PLAN.md)为准。PLAN-02、ARCH-04/11、AGENT-01～05均已工程通过。AGENT-06是READY；本轮独立验证工作树基于8e1c7d2和812维护输入，暂存区为空；仅在同步前核对的本轮白名单路径写回原项目，保留其他工作，不声明全工作区干净。

契约：[AGENT_OBSERVABILITY](../agent/AGENT_OBSERVABILITY.md)。已有运行事件与模型回执加密保存，但缺完整可视化节点层级；复用既有OTel/Langfuse装配，接入execution/loop/plan/tool/final_review/terminal/result，并以原llm.call为叶子。额外metadata仅实际UUID/hash、闭集状态和数值，不导出正文/理由。

新增固定metadata投影；原调用累计与本会话新增分开、账目known/accounted/reserved分开、内部handoff与已确认业务终态分开。恢复同Trace的新会话span、真实租约代数及跨父Trace Link；清理结束再取原预算快照。没有添加执行根、扩大额度、改模型/ACL/安全规则、改发布或冻结评测；无新迁移及公开Schema变更。无需目标/验收ADR变更。

## 2. 问题、修复与复测

1. 初始变换在不存在的canonical_hash导入位置插入span，driver缺span；ruff指出两个F821。改为明确导入并复测。一次ruff命令误用原项目cwd，报告新模块不存在，原四文件format均unchanged；后续在独立工作树运行，同步前仍逐路径核对原字节。
2. 初稿cleanup_failed将调用者异常也算清理失败；改为准确的exception_raised字段，不把任意异常误归清理阶段。
3. 累计调用数不能作为恢复会话新发请求数；增加原快照差值计数，保留总数。实际恢复复用已提交审核时新增0而累计2，独立进程同样验证不重复调用。
4. 结构化failed结果未抛异常时父span最初可能仍UNSET；补固定停止码标ERROR，实际ModelTimeout反例保留已知/保守费用与无正文错误状态。
5. cached finish在退出原_session后读取时，原Telemetry Context已恢复，可能出现新随机Trace；读取入口显式绑定原ID/版本，再执行原授权结果读取，无新根或模型调用。
6. 首轮定向79 passed（13新集成＋原OTel/Loop）；新增退出后读取及父ERROR精确断言的最后3条定向与required全量均已通过，见§3。AST核对4个span包裹函数的原业务正文完全相同，其余60函数完全相同；有意改变的是finish/_session遥测生命周期和新span分类。

7. 自审补齐未提交业务结果时的闭集handoff_reason；预算在首调用前被拒绝也能定位原因，并且不把它伪报成已保存的业务终态。首轮required已83 passed/0 failed时为此主动中断，退出2，保留日志；新增token_limit=1的零调用反例，最终required重跑。

## 3. 验证结果

- required `make check`退出0：**3326 passed、70 skipped、1既有JWT短key warning**，597.517秒。382源码类型/架构、0违规/2旧例外、324断言文件、lint/format、评测输入与36Schema检查通过。
- 15新增集成用例；首轮79定向、最后3条边界复测均退出0。独立Python进程恢复新增模型调用0，原Trace/run/累计账目保留；原OTel与AgentLoop路径同时覆盖。
- 定向命令：`venv/bin/python -m pytest -q tests/integration/test_agent_observability.py tests/unit/core/test_telemetry.py tests/unit/core/test_telemetry_correlation.py tests/unit/application/test_agent_loop.py -x`；首轮79通过，43.579秒。最后3条复测选择同一集成文件的`test_actual_timeout_keeps_known_and_conservative_accounting_without_provider_error_text`、`test_repeated_finish_read_after_session_close_keeps_original_business_trace`和`test_fresh_python_process_correlates_recovery_with_original_runtime_without_model_calls`，12.946秒；零调用预算反例`test_zero_call_budget_stop_has_an_explicit_failure_reason_without_claiming_business_commit`另行1通过，2.747秒。均使用required服务、临时PG、Fake供应商和本地内存exporter，没有实际模型或新后端调用；最终15条均纳入全量。
- 4个span包裹函数去除观测上下文后业务正文AST与原版一致；其余60函数AST一致；finish/_session与span分类的有意变更单列。原812维护输入＋3新Python文件共815绑定当前测试字节，2189范围外受保护tracked blob保持。
- 144任务ID/顺序及其他状态保持；仅AGENT-06改IN_PROGRESS。无新DDL、无36Schema/冻结集/gold/模型/ACL/发布策略改动，正式三库只读核对仍0026。0托管调用/0USD，无正式迁移/重启/部署。
- 70跳过为可选候选C pg_search 25条、候选B zhparser 45条；评测输入审计保留2组unmappable miss、旧安全回放、第二人工pending和无新盲测警告，不把这些算通过。
- 契约/相对链接/任务状态重新审计；[结构化结果](2026-10-19-implementation-220-results.json)。四批分别规划/分类、工具/终检、生命周期/实际计量与测试、文档台账；同步前核对原项目字节，排除output/pdf及本地临时产物。推送和其自身SHA的CI另留实际回执。

## 4. 八项强制自审

| 自审项 | 结论 | 证据与边界 |
| --- | --- | --- |
| 需求与范围 | 通过 | 只交付AGENT-06运行metadata首切片，实际节点/计量/版本/恢复关联已接线；受限审计读取、持久业务Trace/反馈和回放不宣称完成。 |
| ADR与阶段硬门 | 通过 | 沿用ADR-0012/PLAN-02；ARCH-04/11、AGENT-01～05工程前置已过，无目标/阈值变更、自动生产激活或S3改进声明。 |
| 正确性与失败路径 | 通过 | 真实PG/原Driver验证执行树、内部handoff、三种业务交付、超时、调用者异常、终态回滚/确认丢失、同进程/独立Python恢复、foreign parent及退出后读取。 |
| 权限与数据 | 通过 | 固定UUID/hash/闭集状态/数值投影；新增span不含叙述、证据、问题、prompt/output或异常消息；没有新增授权、正文读取或Schema/SQL修改。 |
| 预算、取消与副作用 | 通过 | 0托管调用/0USD；原根/限额/准入/回执保持。累计与本次新增分别记录，已知/保守/在途分开；不靠另一个预算或重发恢复计量。 |
| 追溯与版本 | 通过 | 真实case/task/run/attempt、条件/策略hash与租约代数进入固定metadata；恢复同业务Trace新span；未确认提交不能报完成；加密runtime仍为持久事实。 |
| 验证充分性 | 通过 | required make check退出0：3326 passed/70 skipped/1旧JWT warning，15新集成，79首轮定向及3最终边界通过；4包裹函数正文和其余60函数AST等价，815输入绑定。 |
| 状态与文档 | 通过 | 本切片工程通过，AGENT-06整体IN_PROGRESS；144任务编号/顺序/其他状态保持；最新入口、计划、阶段、契约和本记录一致；部署/模型质量/实际后端交付另验。 |

八项工程自审通过，只覆盖本切片；真实审核者Codex，不等于第二独立人工。实际验证等待时长见§3；活跃编辑时间未单独计量，后续仍按台账任务独立估算。

## 5. 限制、回滚与下一步

仅运行metadata切片。受限完整审计读取/用途日志、持久业务Trace/反馈接线和诊断回放仍待，AGENT-06整体保持IN_PROGRESS；不能用span代替持久write-ahead/回执或把内部finish申请当业务完成。完整S2、真实语义、容量、独立复核/盲测及正式部署没有据此通过。

回滚本轮观测接线不涉及新DDL或预算恢复格式，旧预算/控制/终态守卫保留。真实Langfuse/UI演示仍OBS-03另验，任何未来付费运行逐次授权。下一仍AGENT-06受限审计与回放；AGENT-07等待其余前置，SESSION任务不变。工程投入与返修见本节及实际命令时长；未单独计量活跃编辑时间，不将测试等待当业务性能。
