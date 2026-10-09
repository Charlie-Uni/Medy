# 分阶段执行与每轮自审

更新：2026-10-10。依据用户确认的十项顺序、[原项目描述](source/PROJECT_DESCRIPTION_v0.1.md)、[工程基线](ENGINEERING_BASELINE.md)及[完整迭代计划](ITERATION_PLAN.md)。逐项状态见[当前任务台账](CURRENT_TASKS.md)。本页是执行状态入口，不调整原验收阈值。

## 1. 执行规则

每次只推进一个主优先项。开始前写清目标、输入、固定条件与完成证据；结束前完成自审。发现错误先修复、重验，再给本轮结论。自审者为实际实现者，不能称为独立人工审查。

区分三种结论：

- **本轮自审通过**：这次明确范围内的行为、数据和文档已核实，风险与跳过已解释。
- **阶段待人工/待外部证据**：仍缺真实复核、业务裁决、正式运行或部署证据，不能记阶段通过。
- **阶段通过**：该项完成条件逐条有证据；才把下一依赖阶段标为进行中。

出现不确定性时，先做不依赖该决定的核查、准备可审阅结果，再向用户提出具体问题。已有授权、已裁决事项不重复索要。每批都交付可运行行为、可复现结果、已知限制。

任何会实际调用模型并产生费用的运行都必须在当次开始前取得用户对范围、预计费用、上限和停止条件的明确批准。PostgreSQL 月度预算、既有余额或以前一次运行的授权只提供技术上限，不自动授权新的数据版本、复核或正式实验。运行前还必须确认目标事实库至少包含 migration 0022；2026-10-09 本机 `.env` 已指向 PG17 的 `medops_v2`，`medops_v2` 与 `medops_v2_safety` 均已升至 0022并完成 BM25/向量覆盖检查。

## 2. 顺序与完成依据

| 顺序/批次 | 目标与对应 Goal | 本项通过依据 | 当前状态 |
| --- | --- | --- | --- |
| 1 / 第一批 | 评测标准与数据；OPT-12/13 | 来源/等价/必需组规则，标注与独立复核证据，新版本及正式计分口径，按家族隔离的新盲测集；分别报告 Recall、语义支持、完整性、误拒答 | **进行中，待独立人工、盲测与正式评测证据**。记录 129–157 已完成规则、修订、新版本冻结、来源契约及运行身份保护 |
| 2 / 第一批 | 运行完整性；OPT-15 | active 文档词法/向量覆盖、outbox 积压与恢复、ready 状态反映可检索性；缺索引/积压/依赖失败测试 | 工程实现完成：记录 137–146；记录 162 将生产/安全库迁至 PG17/0022 并验证 BM25 与向量零缺口、readiness=true。长期驻留部署仍待运维交付 |
| 3 / 第一批 | Langfuse；OPT-09 | 一条请求关联 trace、节点耗时、模型用量、策略/数据/评分版本和反馈；完成真实排障演示；内容脱敏与访问边界验证 | **真实后端与故障恢复完成，UI detail 待人工目视**：[记录 163](reviews/2026-10-09-implementation-163-langfuse-deployment-and-recovery.md)完成 v4.54.0 自建、OTLP→3 observations→2 scores 回读、input/output 零长度核验及 outage/recovery；登录页可用，登录后的 trace/score 页面尚未人工检查 |
| 4 / 第一批 | 指定来源与证据覆盖；OPT-13 | 文件/产品/版本约束，文件内容与他文档引用的意图区分，必需组完整性；缺陷题及正常反例同时回归 | 工程候选完成：34 条来源契约、独立计分、默认 off 的运行时约束及真实库零费用回归见记录 156；答案级正式对照与发布决定待付费授权 |
| 5 / 第二批 | BM25；OPT-07 | 复用候选 D，固定分词/其他检索条件，统计隔离和迁移/回滚方案，完整检索及作答配对结果 | 工程切换已完成：部门物理隔离、PG17 迁移和本机回滚副本已验证；新冻结集检索/作答付费门禁待授权 |
| 6 / 第二批 | Redis；OPT-08 | 共享缓存、持续失效消费、命中率/耗时；撤权/归档/新版本/Redis 故障测试，真实重复流量收益 | 工程切换与故障门完成；CACHE-10 真实重复问题收益待付费授权，记录 164 |
| 7 / 第二批 | 并发与重排；OPT-11 | 独立检索与翻译并行评估、重排批处理/服务方案、有界并发、排队、超时与过载失败关闭 | 部分完成：翻译重叠与模型 lane 背压见记录 165/166；记录 167/168 完成双连接评估并决定不实施，同时修复向量规划漂移；重排服务基准和真实容量复测待做 |
| 8 / 第二批 | 上下文裁剪；OPT-11 | 数字、否定、适用条件与跨块证据保持；Token、质量、时延各自与组合对照 | 待开始，沿用既有候选与否决记录 |
| 9 / 第三批 | 多轮与人工接手；OPT-14 | session 实体/身份隔离/失效，原文核对与升级材料，一次完整业务处理及失败路径 | 待开始 |
| 10 / 第三批 | 受控 Loop；OPT-16 | 真实反馈案例→候选→运行应用→回放→人工批准→灰度/回滚，明确自动化边界 | 待开始，复用原受控发布能力 |

模型路由是贯穿项 OPT-10：保留已有能力，按明确、可验证的辅助任务逐项比较。当前作答/判定与翻译的代码配置分别为 gpt-6-sol、gpt-6-luna；已被否决的“说明书一律走小模型”等假设不直接重启。

第二批必须分别测 BM25、缓存、并发、裁剪，再测组合。最终用完整业务任务验证价值，并更新验收报告、演示与项目 PDF；不把组件安装或本机测试数算为业务门禁通过。

## 3. 每轮强制自审记录

| 自审项 | 必须回答的问题 |
| --- | --- |
| 需求与范围 | 对应原项目哪个能力？本轮实际完成什么？有没有未经说明改变阈值、分母、默认策略？ |
| 正确性与失败路径 | 正常、空输入、异常、旧版本兼容、数据损坏如何处理？是否会把失败算成通过？ |
| 权限与可追溯性 | ACL/版本/来源边界是否保持？是否泄漏受限正文、密钥或个人数据？证据和哈希能否重建？ |
| 验证 | 有哪些具体测试/运行？跳过和未测为何存在？结果是否足以支撑本轮结论？ |
| 状态与文档 | 实现、试验、草案、已部署是否分清？人工签字身份是否真实？当前入口与历史记录是否区分？ |

自审表必须记“通过 / 不通过 / 不适用及理由”，并记录发现、修复和复测。存在影响本轮结论的未解决错误时，本轮不得通过；外部资源缺口应明确对应阶段待办，不能用自审替代。

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
- [记录 146](reviews/2026-10-08-implementation-146-task-ledger-and-paid-run-preflight.md)：发现本机 `.env` 仍指向 0007 的旧开发库并会阻断首次模型调用；已改指 `medops_v2`，将两个正式本地事实库升至 0021，补应用角色的受控月度费用读取函数，删除未跟踪 Finder 副本，并把所有模型运行改为逐次费用批准。
