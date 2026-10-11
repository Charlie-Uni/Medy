# 分阶段执行与每轮自审

更新：2026-10-11。依据用户要求，将 Agent、自进化、架构及既有十项迭代统一执行。[当前任务台账](CURRENT_TASKS.md)是唯一状态与顺序入口；本页规定阶段通过条件和每轮自审核，设计见[完整迭代计划](ITERATION_PLAN.md)。[原项目描述](source/PROJECT_DESCRIPTION_v0.1.md)和[工程基线](ENGINEERING_BASELINE.md)的质量、安全、独立复核及生产签字约束继续保留。

最新沟通见 [ADR-0012 v0.4](adr/ADR-0012-agent-evolution-goals-and-acceptance.md)：所有者确认第二阶段=S2、第三阶段=S3 及首个 PV 资料整理场景；ARCH-04/11 是进入 S2 的硬前置；自动激活仅实验；S3 改进声明以未见盲测为前提。至少 200 任务、三轮配对与 CI 方向已确认，新增盲测不设固定 +5pp 幅度硬线，原生产 +5pp 是否同步修改待沟通。每轮付费仍单独授权，ADR 不构成费用批准。

## 1. 执行规则

每次只推进一个主优先项。**每次工作都需要自审核，包含代码、文档、实验、部署和台账整理。** 开始前写清任务 ID、目标、输入、依赖、固定条件与完成证据；实施后进入待审，审核通过且完成证据齐备后才可标记 DONE。发现错误先修复、重验，再给本轮结论。自审者为实际实现者，不能称为独立人工审查。

区分三种结论：

- **本轮自审通过**：这次明确范围内的行为、数据和文档已核实，风险与跳过已解释。
- **阶段待人工/待外部证据**：仍缺真实复核、业务裁决、正式运行或部署证据，不能记阶段通过。
- **阶段通过**：该项完成条件逐条有证据；才把下一依赖阶段标为进行中。

出现不确定性时，先做不依赖该决定的核查、准备可审阅结果，再向用户提出具体问题。已有授权、已裁决事项不重复索要。每批都交付可运行行为、可复现结果、已知限制。

任何会实际调用模型并产生费用的运行都必须在当次开始前取得用户对范围、预计费用、上限和停止条件的明确批准。PostgreSQL 月度预算、既有余额或以前一次运行的授权只提供技术上限，不自动授权新的数据版本、复核或正式实验。运行前还必须确认目标事实库至少包含 migration 0023（新调用回执函数）；2026-10-09 本机 `.env` 已指向 PG17 的 `medops_v2`，`medops_v2` 与 `medops_v2_safety` 均已升至 0022 并完成 BM25/向量覆盖检查。2026-10-11 本机三库追加 0023，业务/权限/策略和原费用摘要一致；新运行时代码部署前先升级，详见[费用说明](LLM_ACCOUNTING.md)。

## 2. 顺序与完成依据

### 2.1 Agent、自进化与架构的统一阶段

详细依赖、状态和工期只在[台账 §0.2、§8–12](CURRENT_TASKS.md)维护。必要修复先行，尽早交付业务 Agent 与 Prompt 自进化，不等待全部选做性能工作才验证核心能力。

| 阶段 | 主要范围 | 阶段通过证据 |
| --- | --- | --- |
| S0 | PLAN-02 先出 ADR 沟通，PLAN-01 补证；EVAL-32/33、CODE-01/02 准备 | 明确哪些决定已确认、哪些验收细则待答；具备能力/场景与行动契约，草案不能当作批准 |
| S1 | ARCH-04 → ARCH-11；ARCH-05/02/03 与相关 ARCH-06/07/09 | 费用回执与整体预算优先，各自自审及回归通过；其他租约/历史/判断/审计条件按依赖满足 |
| S2 | 硬前置 ARCH-04/11 通过及 PLAN-02 相关契约；AGENT-01～08、相关 SESSION | 两项未通过不得进入 S2 实施/集成或试跑；动作、检索补救、澄清、停止、升级、权限与预算反例通过 |
| S3 | Prompt 路径 EVOL-01/02/03/06/07/08/10，EVAL-31/33/36 | 机制证据与有效盲测报告分别完成；固定提升幅度不作新增硬线。CI 等证据支持才可声明改善；无盲测只能报机制完成/效果待验证，无正向结果则如实报未证实 |
| S4 | EVOL-04/05/11/12、AGENT-09、SESSION/HANDOFF | 声明式 Skill 改变真实行为，旧版兼容/回滚；五类业务、多轮追问、原文核对与人工接手完成 |
| S5 | 正式评测、EVOL-13/LOOP-01、检索效率、部署与成果 | 原门禁逐条报告，正式审批/灰度/回滚留证；完整业务演示和文档；未达标或缺独立人工时不得宣称整体验收通过 |

ARCH-08/10/13/14、CODE-03～07、IDX/OBS/DEPLOY 按依赖穿插，ARCH-12 有收益再实施。BM25/缓存/裁剪/路由先单变量后组合；新主集与安全基线、正式回放和人工缺口保留。开发演示不支持改进声明；盲测材料与调优隔离，已暴露题移入回归，后续改进用新未见材料。生产保留人工签字。

[记录 171](reviews/2026-10-10-implementation-171-harness-deadline-and-cancellation.md)的 ARCH-01 工程证据继续有效：源码一致的仓库外快照 1774 passed、70 skipped，真实 BGE/事实库核验、模型 API 费用 0；它不证明任务租约或全部医学/容量指标通过。PLAN-01 已提供设计证据；PLAN-02 剩余行动/验收契约继续沟通，ARCH-04 已通过调用计量范围工程自审，1807/70 全量门禁与本机三库 0023 迁移见[记录 175](reviews/2026-10-11-implementation-175-call-receipts-and-fee-attribution.md)；ARCH-11 已通过共享预算工程自审，全量 1830/70、0 托管调用见[记录 176](reviews/2026-10-11-implementation-176-shared-execution-budget.md)；ARCH-05 当前租约/尝试保护通过，全量 1857/70、0 托管调用见[记录 177](reviews/2026-10-11-implementation-177-task-lease-and-ownership.md)，当时下一项 ARCH-03；最新结论见记录 179。

ARCH-02 的日期/显式历史输入、四类 Skill 提示及 Ask 诊断 Replay 已通过工程自审；三库 0024、1908/70 全量、501 维护输入 SHA 一致、0 托管调用，见[记录 178](reviews/2026-10-11-implementation-178-historical-query-context.md)及[输入契约](HISTORICAL_QUERIES.md)。裸 version 和未知旧输入明确拒绝；完整原条件回放仍待 ARCH-07，当时下一项 ARCH-03；最新结论见记录 179。此轮不是独立人工或模型质量验收，新代码未重启上线。

ARCH-03 两类最终业务比较的工程修复与自审通过，见[记录 179](reviews/2026-10-11-implementation-179-final-skill-judgment-verification.md)和[最终判断契约](SKILL_JUDGMENT_VERIFICATION.md)：四项核验、窄规则/语义分工、严格回复与失败关闭，1969/70 全量、506 维护输入 SHA 一致、0 托管调用。真实语义校准仍待单次授权；当时下一项 ARCH-06，最新工程结论见下段。原条件复现、PLAN-02 剩余契约及 S2/S3 仍未完成。新代码本轮未重启上线。

ARCH-06 的 Ask/Task 共享审计与五类 Skill 内层证据链已通过工程自审，见[记录 180](reviews/2026-10-11-implementation-180-task-execution-audit.md)和[执行审计契约](TASK_EXECUTION_AUDIT.md)：完整引用绑定、结构化候选/最终核验、安全与重试保留，失败/撤权/lost 及数据库原子回滚通过。全量 2008/70、510 维护输入 SHA 一致、0 托管调用，无迁移；无 key 配置只存元数据。下一主切片 ARCH-07，ARCH-07/08 仅解锁无付费实现；Task/MCP 精确回放、真实语义校准、独立人工、未见盲测及 S2/S3 未完成，新代码未重启上线。

LangGraph 当前仍是固定主图，动态循环是新增待办；LG-01 仅为 checkpoint 技术选型选做，恢复要求按实际 Agent 契约落实。模型路由和 provisional 标签保持真实状态。

S0 的 PLAN-01 证据入口为[能力矩阵与 PV 场景方案](agent/PLAN-01-capability-and-scenario.md)，包括参考源码重新核验、固定 Workflow 对照及 12 个合成开发用例。其完成仅表示设计输入可审阅；所有者已确认 PV 场景范围，完整契约仍归 PLAN-02，EVAL-32 尚未冻结，ARCH-04/11 已分别通过工程自审；PLAN-02 剩余 Agent 行动/profile 与验收契约未决，相关正确性前置继续满足，不能据此把 S2 标为已解锁或完成。

ARCH-07 的执行记录和诊断边界已通过工程自审，见[记录181](reviews/2026-10-11-implementation-181-execution-records-and-replay-boundaries.md)及[回放契约](EXECUTION_REPLAY.md)：Ask/Task 完整输入、内容条件摘要、逐模型请求/实际 SDK 参数和回复/回执、渲染及 Unicode 来源区间；2038/70 全量、518维护输入一致，614条存档/6140布局比较零差异，0托管费用。原条件模式缺少归档事实/索引和经验证的旧运行工件，明确409拒绝，并未实现原条件恢复；Task/MCP回放、MCP受限正文和 FOCUS-02完整跨块定位仍未完成。当时下一项ARCH-08；真实模型质量、盲测和 S2/S3 约束保持，新代码未提交部署。

ARCH-08的共用契约、knowledge文本规则、bootstrap三入口装配与静态边界工程自审通过，见[记录182](reviews/2026-10-11-implementation-182-shared-composition-and-import-boundaries.md)和[生产装配契约](PRODUCTION_COMPOSITION.md)：全量2071/70、532维护输入一致、59定义AST与12配置/灰度版本比较一致，0托管费用。CODE-04/05可无付费继续；当时CODE-07仍待ARCH-09，并保留MCP受限完整材料未交付项。当时下一项ARCH-09；没有改变PLAN-02、S2/S3、独立人工、盲测与生产签字门。未提交部署。

ARCH-09 已完成持久UUID/稳定评分namespace/游标与恢复实现，八项工程自审通过：[记录183](reviews/2026-10-11-implementation-183-stable-feedback-identity.md)、[反馈身份契约](FEEDBACK_IDENTITY.md)。三库0025，31表内容/5索引计数不变，代码全量2089/70、536维护输入一致、0托管调用；未重启部署，未知旧源不自动绑定。下一主项ARCH-10；CODE-07后续MCP材料/观测职责仍未完成；S2/S3与人工/盲测/付费约束保持。

### 2.2 原三批十项的能力映射与进展

下表保留原任务范围和已有证据；“第一/二/三批”是原分组，当前执行先后以 §2.1 的 S0～S5 及统一台账为准，不再将自动候选生成推迟到全部性能工作之后。

| 顺序/批次 | 目标与对应 Goal | 本项通过依据 | 当前状态 |
| --- | --- | --- | --- |
| 1 / 第一批 | 评测标准与数据；OPT-12/13 | 来源/等价/必需组规则，标注与独立复核证据，新版本及正式计分口径，按家族隔离的新盲测集；分别报告 Recall、语义支持、完整性、误拒答 | **进行中，待独立人工、盲测与正式评测证据**。记录 129–157 已完成规则、修订、新版本冻结、来源契约及运行身份保护 |
| 2 / 第一批 | 运行完整性；OPT-15 | active 文档词法/向量覆盖、outbox 积压与恢复、ready 状态反映可检索性；缺索引/积压/依赖失败测试 | 工程实现完成：记录 137–146；记录 162 将生产/安全库迁至 PG17/0022 并验证 BM25 与向量零缺口、readiness=true。长期驻留部署仍待运维交付 |
| 3 / 第一批 | Langfuse；OPT-09 | 一条请求关联 trace、节点耗时、模型用量、策略/数据/评分版本和反馈；完成真实排障演示；内容脱敏与访问边界验证 | **真实后端与故障恢复完成，UI detail 待人工目视**：[记录 163](reviews/2026-10-09-implementation-163-langfuse-deployment-and-recovery.md)完成 v4.54.0 自建、OTLP→3 observations→2 scores 回读、input/output 零长度核验及 outage/recovery；登录页可用，登录后的 trace/score 页面尚未人工检查 |
| 4 / 第一批 | 指定来源与证据覆盖；OPT-13 | 文件/产品/版本约束，文件内容与他文档引用的意图区分，必需组完整性；缺陷题及正常反例同时回归 | 工程候选完成：34 条来源契约、独立计分、默认 off 的运行时约束及真实库零费用回归见记录 156；答案级正式对照与发布决定待付费授权 |
| 5 / 第二批 | BM25；OPT-07 | 复用候选 D，固定分词/其他检索条件，统计隔离和迁移/回滚方案，完整检索及作答配对结果 | 工程切换已完成：部门物理隔离、PG17 迁移和本机回滚副本已验证；新冻结集检索/作答付费门禁待授权 |
| 6 / 第二批 | Redis；OPT-08 | 共享缓存、持续失效消费、命中率/耗时；撤权/归档/新版本/Redis 故障测试，真实重复流量收益 | 工程切换与故障门完成；CACHE-10 真实重复问题收益待付费授权，记录 164 |
| 7 / 第二批 | 并发与重排；迭代计划 OPT-11，路线图 OPT-02 为选做独立服务 | 独立检索与翻译并行评估、重排批处理/服务方案、有界并发、排队、超时与过载失败关闭 | 部分完成：翻译重叠与模型 lane 背压见记录 165/166；记录 167/168 完成双连接评估并决定不实施，同时修复向量规划漂移；记录 169 合批负收益不接入，进程退出/阻塞恢复原型通过；生产服务化仍选做，真实容量复测待做 |
| 8 / 第二批 | 上下文裁剪；M5-04 / 迭代计划 OPT-11 | 数字、否定、适用条件与跨块证据保持；Token、质量、时延各自与组合对照 | **本地审查与异常分数拒绝完成，候选未通过采用审查**：记录 170 的 614 条诊断、4 个未改 query 隐藏 key、482→480 完整 key 组；614 条正常渲染重放一致。原 v7 暂不启用，实际片段追溯、跨块 span 定位与新版正式门禁仍待做 |
| 9 / 第三批 | 多轮与人工接手；OPT-14 | session 实体/身份隔离/失效，原文核对与升级材料，一次完整业务处理及失败路径 | 待开始 |
| 10 / 第三批 | 模型驱动受控 Loop；OPT-16 | 真实反馈→模型归因→模型生成 Prompt/Skill 内容→实际加载→独立评测→实验启用/拒绝→生产批准/灰度/回滚 | 拆为 EVOL-01～13；Prompt 先行，已有规则归因和发布框架不能替代模型生成能力 |

模型路由是贯穿项 OPT-10：保留已有能力，按明确、可验证的辅助任务逐项比较。当前作答/判定与翻译的代码配置分别为 gpt-6-sol、gpt-6-luna；已被否决的“说明书一律走小模型”等假设不直接重启。

第二批必须分别测 BM25、缓存、并发、裁剪，再测组合。最终用完整业务任务验证价值，并更新验收报告、演示与项目 PDF；不把组件安装或本机测试数算为业务门禁通过。

## 3. 每轮强制自审记录

每轮在 `docs/reviews/` 创建或追加唯一记录，按下面模板逐项填写；不要复制前一轮结论代替本轮检查。

```text
日期 / 实现者 / 自审核者（实际身份，不冒充独立人工）：
任务 ID / 本轮主切片 / 对应 Goal：
开始前状态、依赖与授权：
目标、范围、固定条件、完成证据：
代码版本与已有未提交改动 / 本轮改动文件：
命令、环境、退出码、结果路径 / 真实模型调用及费用：
发现的问题 → 修复 → 复测结果：
自审逐项结论（通过 / 不通过 / 不适用及理由）：
未测、跳过、残留风险和外部证据缺口：
本轮自审结论 / 工程、质量、发布分别是什么状态：
台账更新、回滚方法、下一项及需用户决定的事项：
实际投入/等待/返修、剩余工期是否需要重估：
```

| 自审项 | 必须回答的问题 |
| --- | --- |
| 需求与范围 | 对应原项目和当前任务的什么能力？验收条款是否逐项有证据？是否未经说明改变阈值、分母或默认策略？ |
| ADR 与阶段硬门 | 目标/验收变更是否已有 ADR 和真实沟通记录？S2 前 ARCH-04/11 是否确已通过？S3 改进声明是否有合格未见盲测？自动激活是否严格限实验？ |
| 正确性与失败路径 | 正常、空输入、异常、旧版、数据损坏、并发/恢复如何处理？必要反例能否失败？ |
| 权限与数据 | ACL/来源/版本边界是否保持？工具能否越权？候选生成和评测是否隔离？正文、密钥及个人数据是否受控？ |
| 预算、取消与副作用 | 调用/重试是否在本次授权内？租约、停止、遗留执行和费用归属是否正确？无模型调用也须如实说明 |
| 追溯与版本 | 真实执行的输入、证据、策略、Skill 和调用回执能否定位？新版本是否实际加载？发布/回滚记录一致吗？ |
| 验证充分性 | 验证与本次风险是否匹配？命令、退出码、跳过及环境限制是否明确？不得用测试数量替代质量结论 |
| 状态与文档 | READY/REVIEW/DONE 和依赖一致吗？实现、试验、质量、部署、生产批准是否分开？入口、链接、编号是否同步？ |

状态流程为 `READY → IN_PROGRESS → REVIEW → DONE`，仅在相应范围完成且自审通过后 DONE。存在影响结论的缺陷必须先修复复测；未解决标为未通过。依赖/人工/预算受阻使用对应状态，允许推进无关 READY 项。代码按影响运行必要回归及要求的全量门禁；纯文档轮检查链接、任务覆盖、状态和约束一致性，不重复与本轮无关的全量代码测试。阶段通过还须具备真实运行/人工证据，自审不能代替。

## 4. 阶段 1 当前交付与下一人工点

- [修订草案 v6](../evals/main_set/drafts/revision-2026-10-08-v6/README.md)已落实：probe v4 与 `main-v5-provisional` 均已冻结。主集 615 题、582 个 gold 单元、long_context=20；580 mapped、2 unmappable。EVAL-11 的四个可安全修复 miss 已完成修订与复核，两个跨 chunk GVP miss 继续留在分母；第二人工仍暂无。
- [复核分派与确认入口](../evals/review/stage-01-2026-10-08/README.md)：19 条新/改标注已由用户确认；用户明确暂时没有第二人，主集 536 条第二人工任务保留 pending；安全集保留 170 条逐条确认和独立复核的证据缺口。
- [盲测准备](../evals/holdout/README.md)：真实家族元数据清单和三组已知关系例子已整理；新题尚未出题/冻结，不能称已建独立盲测集。
- [记录 132](reviews/2026-10-08-implementation-132-versioned-outcome-scoring.md)：主集/回放新运行固定 main-outcome-v2，无答案与 system_failure 已区分，续跑及基线复用禁止混用评分版本；本轮自审通过，1399 passed、70 skipped。
- 语义支持和答案完整性的 14 题校准已完成；新主集正式质量运行、safety-v2 正式运行及新回放仍须完成。正式优化实验必须使用已固定的评分与数据口径。

- [记录 134](reviews/2026-10-08-implementation-134-multi-gold-review-preparation.md)：多证据复核工具与 19 条独立模型输入已准备；1419 passed、70 skipped，19 条实际提示全部可重建。该记录准备时调用为 0；后续实际 19 次调用及费用见记录 143，第二人工 pending。
- [记录 135](reviews/2026-10-08-implementation-135-replay-input-snapshots.md)：新回放安全输入已固化，发现并阻止旧集 ss-0125 预期漂移；1440 passed、70 skipped。正式 replay-v4 仍待真实来源运行。
- [记录 136](reviews/2026-10-08-implementation-136-answer-quality-evidence.md)：主集逐句引用/原文快照与独立语义、完整性诊断工具；全量 1461 passed、70 skipped，另 4 项 RLS 实测通过。真实裁判尚未执行/校准，诊断不进入正式门禁。

2026-10-08 用户确认目前仅有本人和模型，见[记录 133](reviews/2026-10-08-implementation-133-human-confirmation-and-provisional-review.md)。沿用主集 SPEC §4 和安全集 SPEC §6 已允许的 provisional 运行方式，继续阶段 1 的工程、模型复核准备和临时评测；不将“暂无第二人”反复作为同一项批准请求，不把模型记为第二人工。完整阶段验收仍保留此证据缺口。

原 P0 加权进度和正式门禁保持原口径。本页进入下一项时应追加实现记录，不仅改状态文字。

- [记录 144](reviews/2026-10-08-implementation-144-refactor-verification-and-depiling.md)：记录 126–142 的正确性核验（搬移逐字节一致、冻结数据未动）、三处缺陷修复、转发层与重复实现清理、MRR 补算（非门禁，0.77 / 0.61）；未处理项与决定见其 §6。
- [记录 140](reviews/2026-10-08-implementation-140-bound-run-resume.md)：主集/安全集续跑绑定实际代码、依赖、日期、样本/映射、模型/策略与事实摘要；重试费用保留，发布提示已接线。1539 passed、70 skipped；没有新的真实模型成绩。
- [记录 157](reviews/2026-10-09-implementation-157-replay-binding-and-fact-drift.md)：回放两臂与逐行实际版本绑定、严格基线复用身份、运行中事实周期/终检及重试费用来源完成；真实双库摘要稳定，全量 1705 passed、70 skipped；没有模型调用或新门禁成绩。
- [记录 158](reviews/2026-10-09-implementation-158-eval12-calibration-preparation.md)：EVAL-12 十题精确校准面板、模型判词输入边界和单次 API 运行调用前预算已准备；全量 1709 passed、70 skipped。真实回答生成仍待 0.35 USD 单独授权，后续裁判调用另行授权。
- [记录 159](reviews/2026-10-09-implementation-159-eval12-generation-and-supplement.md)：十题真实生成 10/10 终态、10/10 快照、实际 0.085875 USD；仅 6 answered，未达到预登记至少 8，未启动 Claude 裁判。四题补充面板和多运行聚合已准备，补充生成等待 0.15 USD 单独授权。
- 记录 159 后续：四题补充生成 4/4 answered，实际 0.027149 USD；合并达到 10 answered / 14 cases。Claude 裁判两轮共发起 4 次，前 2 条有效；`ms-0242` 两次都把 citation 判断错放进 `claims`，分别在 0.196300 与新增 0.056092 USD 后按规则停止。已改用原生 JSON Schema 约束输出，绑定全部历史的 8 条请求待新的 2.40 USD 授权。
- [记录 160](reviews/2026-10-09-implementation-160-eval12-structured-review-complete.md)：Schema 后续 8 次全部取得有效 verdict，其中首条从同次调用的 `structured_output` 恢复；本轮 0.578090 USD，Claude 三轮累计 0.830482 USD。最终 claim 12/12、citation 13/14、完整性 7/14；校准完成但不是正式门禁或第二人工。

- [记录 143](reviews/2026-10-08-implementation-143-budgeted-model-review.md)：19/19 模型复核完成，原始意见 15 同意、4 争议；5 USD 上限内保守入账 2.917528 USD，失败/重试/未知费用均为 0。1612 passed、70 skipped；39 个 gold 机械定位全通过。[三项待人工决定](../evals/main_set/drafts/revision-2026-10-08-v2/review/adjudication_2026-10-08.md)为偏移误读保留、联合证据必要性调整、版本标签补充。修改建议未应用，阶段 1 未通过。

- [记录 147](reviews/2026-10-08-implementation-147-owner-adjudication-and-targeted-rereview.md)：原三项已按建议落实为 v3；三条变化样本用 3 次独立调用复核，账本 0.555900/0.750000 USD，2 agree、1 个新的 key_text dispute。调用、费用和哈希审计通过，全量 1635 passed、70 skipped；`ms-0241/0242` 同一 key 的模型意见不一致，当前只待一个人工裁决，阶段 1 仍未通过。

- [记录 148](reviews/2026-10-08-implementation-148-v4-key-adjudication-and-budget-stop.md)：key 裁决已落实为 v4；页级与映射校验通过。`ms-0241` agree，`ms-0242` 在 0.25 USD 阈值处停止且无 verdict；两次账本合计 0.442077/0.500000 USD，无自动重试。全量 1635 passed、70 skipped；已准备一次 0.30 USD 的精确重试请求，尚未授权，阶段 1 仍未通过。

- [记录 149](reviews/2026-10-08-implementation-149-ms0242-retry-complete.md)：`ms-0242` 单次重试成功并 agree，账本 0.185248/0.300000 USD；v4 两条变化样本复核完成。失败调用和费用仍保留，完整调用审计通过，全量 1635 passed、70 skipped；下一步为新探针导入和 provisional 主集版本化。

- [记录 150](reviews/2026-10-08-implementation-150-main-v4-frozen.md)：probe v3 已原样导入并冻结 `main-v4-provisional`；FDA 标题修正传播到的额外 7 条样本逐条复核均 agree，实际 0.593073 USD。历史与新提示按哈希分别保存，完整映射为 568 mapped / 6 unmappable。全量数据库快照工具遇到 3 份按 ADR-0009 有意拒收入库、且无样本引用的 corpus 候选后失败关闭；没有绕过拒收策略，映射改由冻结基线与已校验修订预览确定性合成。
- [记录 155](reviews/2026-10-09-implementation-155-eval11-v6-reviewed-and-frozen.md)：v6 两条差量复核均 agree，实际 0.290727 USD；probe v4 和 `main-v5-provisional` 冻结，映射为 580 mapped / 2 unmappable。后继组装器补齐多批次复核、历史提示版本和 probe 导入提示集合的追溯支持。

- [记录 156](reviews/2026-10-09-implementation-156-source-semantics-and-runtime-candidate.md)：34 条版本化来源契约与独立来源符合率；`source-constraint-v1` 已作为默认 off 的发布参数接入。真实 `medops_v2` 的 RLS 下 34/34 来源角色结构回归通过，`ss-0090/0096` 均安全判为点名来源不可见；正式答案级对照、发布决定和第二人工仍待完成。

- [记录 145](reviews/2026-10-08-implementation-145-operational-ledgers-and-mcp-parity.md)：Langfuse 有界队列/死信、outbox 按消费者死信与重放、PostgreSQL 月费用预留账本、MCP 查询翻译与缓存一致性；正式库升 0020 后 ready。1627 passed、70 skipped；外部 Langfuse UI 仍待验收。
- [记录 164](reviews/2026-10-09-implementation-164-redis-cache-cutover.md)：主库 Redis 缓存、独立 namespace、常驻失效 worker、按模式 readiness、两库清账与断连恢复；1717 passed、70 skipped；真实流量收益待付费。
- [记录 165](reviews/2026-10-09-implementation-165-translation-retrieval-overlap.md)：翻译与原始检索重叠、4 worker / 8 在途 / 250 ms 有界背压、Trace context 与过载失败关闭；1720 passed、70 skipped；无真实性能成绩。
- [记录 166](reviews/2026-10-09-implementation-166-pinned-model-backpressure.md)：共享嵌入/重排 lane 的 8 个总在途上限、250 ms 准入等待与 stalled 快速拒绝；1721 passed、70 skipped；不把工程保护写成 P95 改善。
- [记录 167](reviews/2026-10-09-implementation-167-channel-overlap-and-vector-plan-drift.md)：真实通道双连接并行仅约 6 ms 中位收益，不实施；发现旧 auto 向量候选随计划切换漂移，转 VEC-01；iCloud 占位事故与临时恢复留证。
- [记录 168](reviews/2026-10-10-implementation-168-fixed-vector-plan-and-quality-audit.md)：554 道有 gold 题对照、4 gains / 1 loss、generic 成本与受保护切片回归完整保留，最终固定 custom；107/107 新连接/复用候选和分数一致，214 次重复无漂移；环境迁出 iCloud、最终 1730 passed、70 skipped。没有外部模型调用，完整答案/安全/容量门禁不变。
- [记录 169](reviews/2026-10-10-implementation-169-rerank-burst-and-process-isolation.md)：同模型/fp32/batch 8 的 FIFO 与合批对照，每臂 36 请求；合批吞吐 −4.71% / −13.36%，排序/分数相同，拒绝接线；真实模型进程退出/阻塞后失败关闭并恢复；1739 passed、70 skipped，API 费用 0。仅是本地就绪队列微基准，未通过完整 API P95 门禁。
- [记录 170](reviews/2026-10-10-implementation-170-focus-v7-evidence-retention-audit.md)：新标注下 614 条旧上下文诊断，14 条改 query 单列，`ms-0525` 的 2 gold 保留未测；未改 query 隐藏 4 个 key，原完整 key 组 482→480。修复异常评分仍生成的问题，614 条正常分数重放逐字段一致；1753 passed、70 skipped，API 费用 0。原 v7 暂不采用，阶段未通过。
- [记录 146](reviews/2026-10-08-implementation-146-task-ledger-and-paid-run-preflight.md)：发现本机 `.env` 仍指向 0007 的旧开发库并会阻断首次模型调用；已改指 `medops_v2`，将两个正式本地事实库升至 0021，补应用角色的受控月度费用读取函数，删除未跟踪 Finder 副本，并把所有模型运行改为逐次费用批准。
