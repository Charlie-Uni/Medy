# Medy

MedOps Copilot 是面向医学事务、药物警戒和临床运营的可信医学 RAG 与受控 Agent 项目。

开发范围、硬约束、里程碑和逐项验收以 [工程基线与开发 Checklist](docs/ENGINEERING_BASELINE.md) 为准。

已完成工作、全部待办、选做增强与对应面试基础知识，见 [开发进度与边做边学路线](docs/DEVELOPMENT_ROADMAP.md)。

每个任务的当前状态与对应基础知识点，见 [任务与知识点对照](docs/TASK_KNOWLEDGE_MAP.md)。

## 最新执行入口（2026-10-11）

后续统一按[当前任务台账](docs/CURRENT_TASKS.md)推进：保留此前架构、评测、BM25、Redis、Langfuse、模型路由和使用闭环任务，新增受控 Agent 与模型生成 Prompt/声明式 Skill 的自进化任务。顺序为目标与验收 → 必要执行保护 → 首个业务 Agent → Prompt 自进化 → Skill/使用闭环 → 完整验证与交付。PLAN-01 设计证据与 PV 场景范围已确认，PLAN-02 的 [ADR-0012](docs/adr/ADR-0012-agent-evolution-goals-and-acceptance.md) 剩余契约继续沟通；ARCH-04/11 及当前任务租约 ARCH-05、历史输入 ARCH-02、最终判断 ARCH-03、异步审计 ARCH-06、执行记录和诊断边界 ARCH-07 及共用装配 ARCH-08 工程自审通过；ARCH-09稳定反馈身份、ARCH-10共享scorer和ARCH-13部署监督及ARCH-14必需CI均已通过对应工程自审，ARCH-12仅诊断/方案评估通过、事务拆分未采用，下一项ARCH-15最终输出权限/事实核验；S2 仍须满足 PLAN-02 相关契约和其他正确性前置。自动激活仅实验，S3 改进声明须有未见盲测，每轮付费单独授权。新增能力尚未实现；盲测新增工作量确认后重估工期。

**每轮代码、文档、实验与部署都必须自审核，问题修复复测且证据齐备后才能标记完成。** 固定执行要求见[AGENTS.md](AGENTS.md)，模板见[分阶段执行与自审](docs/ITERATION_STAGES.md)。评测标准修订、来源契约、回放绑定和模型裁判校准已形成冻结的 `probe-v4` 与 `main-v5-provisional`；第二独立人工仍未具备，相应结论继续标为 provisional；生产签字和逐次付费授权要求保留。

最新[架构审查](docs/reviews/2026-10-10-architecture-audit.md)发现 14 项缺陷/风险，已并入台账 ARCH-01～14。首项 ARCH-01 已完成总截止时间、旧尝试收束、SQL/HTTP 取消及本地 BGE 推理进程回收；该轮工程自审与等价快照全量检查通过，1774 passed、70 skipped，费用 0。后续任务租约、历史 Skill、二阶段判断、整体预算和任务审计按统一依赖推进。范围、实际模型核验、iCloud 核验限制和错误补救见[记录 171](docs/reviews/2026-10-10-implementation-171-harness-deadline-and-cancellation.md)；原组件切换、历史成绩和验收门槛保留。本次统一待办及自审见[记录 172](docs/reviews/2026-10-10-implementation-172-unified-agent-evolution-backlog.md)。

ARCH-04 已为成功、失败、拒绝和取消调用建立独立回执，避免并发共享费用串入其他 Trace；实际 usage 计算与保守预留分开，结算不确定不重跑模型。本机三库已升至 0023，原业务和费用数据未变；全量 1807 passed、70 skipped，0 托管调用。工程自审通过；迁移和对账限制见[记录 175](docs/reviews/2026-10-11-implementation-175-call-receipts-and-fee-attribution.md)及[费用说明](docs/LLM_ACCOUNTING.md)。ARCH-11 已完成共享执行预算并通过自审核：[记录 176](docs/reviews/2026-10-11-implementation-176-shared-execution-budget.md)，全量 1830 passed、70 skipped，0 托管调用；现有 profile 为 12,000 Token / 0.60 USD、Ask 125 秒，Skill/MCP 保留较短原期限。翻译、作答、判定、结构化与重试共同扣减，不能在嵌套或线程中重开。新 Agent/模型 Loop 与跨进程恢复尚未实现，S2 仍未完成。

ARCH-02 已统一 Ask、Skill 与单条 Ask Replay 的日期/历史模式，修复归档来源选择与四类 Skill 历史提示；裸版本、缺上下文的旧 Trace 及 Task/MCP 回放明确拒绝。三库已到 0024，保护摘要不变；全量 1908 passed、70 skipped、0 托管调用，工程自审通过。输入、兼容和当前事实诊断边界见[历史查询契约](docs/HISTORICAL_QUERIES.md)及[记录 178](docs/reviews/2026-10-11-implementation-178-historical-query-context.md)。后续最终判断修复见下段，完整原条件回放仍待 ARCH-07；新代码本轮未重启到常驻服务。

ARCH-03 已增加两类结构化 Skill 的最终比较核验，结论、理由、条款适用和原观察四项须分别支持；数字反转、错误引用或无支持不再业务完成，矛盾进入升级。严格回复、共享预算及五类兼容回归通过，全量 1969 passed、70 skipped、0 托管调用，见[核验契约](docs/SKILL_JUDGMENT_VERIFICATION.md)及[记录 179](docs/reviews/2026-10-11-implementation-179-final-skill-judgment-verification.md)。真实语义比较校准仍待单次费用授权；当时下一项 ARCH-06，最新工程结论见下段，代码未重启上线。

ARCH-06 已补齐 Ask/Task 共用审计、五类 Skill 内层证据与最终核验、结构化候选、安全和重试材料；结果引用逐字段绑定实际证据，撤权、失租及审计故障均失败关闭。真实 PostgreSQL 原子回滚与访问日志验证通过，全量 2008 passed、70 skipped、0 托管调用，见[执行审计契约](docs/TASK_EXECUTION_AUDIT.md)及[记录 180](docs/reviews/2026-10-11-implementation-180-task-execution-audit.md)。无 key 配置仍仅保存元数据；Task/MCP 精确回放仍待下一项 ARCH-07。该轮验证时尚未提交；当前已按记录184提交，未重启上线。

生产词法通道已按项目所有者决定切换到部门隔离的 `pg_textsearch` BM25：PostgreSQL 17、extension 1.5.1、migration 0022，MA/PV/CO 各用独立物理语料，避免 RLS 隐藏行参与跨部门 IDF/词频统计。正式库与安全库已完成逻辑迁移、索引构建和 readiness 核验，旧 PG16 卷及逐库逻辑备份保留。设计、实测数据、故障和回滚边界见[实现记录 162](docs/reviews/2026-10-09-implementation-162-production-bm25-cutover.md)，许可与发布资产见[许可记录](docs/reviews/2026-10-09-licence-dossier-pg-textsearch.md)。新冻结集上的付费检索与答案级 BM25 对照仍需单独授权，工程切换不等同于质量门禁通过。

Langfuse v4.54.0 已以同网络、metadata-only 方式部署：真实 OTLP trace、评分与反馈类别关联、API 回读及服务中断后的队列恢复均通过，模型调用 0、费用 0；登录后的 UI detail 仍待人工目视。启动与复验见 [Langfuse 运维说明](docs/LANGFUSE.md)，实现与失败补救见[记录 163](docs/reviews/2026-10-09-implementation-163-langfuse-deployment-and-recovery.md)。

Redis 候选缓存已切换到本机主运行配置：主库与 safety 使用独立 namespace，Compose 常驻消费者已清空 338/339 条历史失效事件，启用缓存时积压会进入 readiness，断连时安全回源。真实问题流量的命中率、完整问答 P95、质量与费用收益仍待 CACHE-10 付费对照，不能用 1.14 ms 的纯命中 smoke 代替。实现与演练见[记录 164](docs/reviews/2026-10-09-implementation-164-redis-cache-cutover.md)。

向量检索现固定定制规划模式，避免连接复用后自动换计划导致候选漂移；107 题新连接/复用的候选与分数逐项一致，重复排名无变化。通用计划候选在主集 554 道 gold 题上仅 +0.54 pp，却有一题受保护切片回归和更高的排序扫描耗时，未选为默认值。基础组合版本为 `5ae70f4f…28d9`；这次是稳定性修复，未宣称完整问答召回或 P95 改善。详细错误、取舍与复现证据见[记录 167](docs/reviews/2026-10-09-implementation-167-channel-overlap-and-vector-plan-drift.md)、[记录 168](docs/reviews/2026-10-10-implementation-168-fixed-vector-plan-and-quality-audit.md)。

重排合批评估已完成：固定模型/fp32/batch 8，每臂 36 个就绪请求；两题/四题合批吞吐下降 4.71% / 13.36%，分数与排名一致，未接入生产。记录 169 的独立本地进程原型已在 ARCH-01 演进为运行入口的可终止推理，用于取消收束；独立网络服务与完整 API 容量复测仍待评估。方法、原始结果、故障边界与术语见[记录 169](docs/reviews/2026-10-10-implementation-169-rerank-burst-and-process-isolation.md)及[记录 171](docs/reviews/2026-10-10-implementation-171-harness-deadline-and-cancellation.md)。

上下文裁剪 v7 已完成 614 条历史证据诊断：未改 query 的 600 条中隐藏 4 个 key，完整 key 证据组从 482 降至 480；14 条改 query 的旧上下文单列，另保留 `ms-0525` 的未测缺口。原 v7 暂不启用。句子评分接受 NaN/无穷仍继续生成的缺陷已修；614 条真实有限分数重放，渲染与保留结果逐字段一致。数据、错误原文、范围与下一步见[记录 170](docs/reviews/2026-10-10-implementation-170-focus-v7-evidence-retention-audit.md)；实际片段追溯与跨块 span 定位仍待补，API 费用 0，未通过正式成本门禁。




ARCH-07 已补 Ask/Task 完整执行记录、实际模型请求/SDK回复/回执、渲染正文/哈希与 Unicode 来源区间；Ask 诊断回放恢复输入并分项报告条件差异，见[回放契约](docs/EXECUTION_REPLAY.md)和[记录181](docs/reviews/2026-10-11-implementation-181-execution-records-and-replay-boundaries.md)。全量2038/70、518维护输入一致；614存档上下文的6140布局比较零差异，0托管调用。原条件恢复未交付，当前明确拒绝；Task/MCP回放与完整跨块定位仍待做，不作真实质量或发布声明。

ARCH-08 已将跨入口契约移至 application、解析/PII/norm-v1移至 knowledge、生产装配移至 bootstrap。API/worker/MCP 共用策略版本与检索/缓存规则；新增自动导入边界，214模块零违例、2精确允许项。全量2071 passed、70 skipped、532维护输入一致、0托管费用，见[装配说明](docs/PRODUCTION_COMPOSITION.md)和[记录182](docs/reviews/2026-10-11-implementation-182-shared-composition-and-import-boundaries.md)。仅工程自审通过；MCP受限正文与回放、Agent/自进化尚未交付，当时下一项ARCH-09，当轮未提交或部署；当前提交见记录184。

ARCH-10已将重排scorer与冻结输出配置分开，一个lane只加载一份CrossEncoder，输出策略切换复用权重；同配置初始化singleflight、共享超时失败关闭。真实CPU八请求/五种输出加载1次、分数差0，全量2105 passed/70 skipped，见[记录185](docs/reviews/2026-10-11-implementation-185-shared-reranker-scorer.md)。仅工程自审通过，API性能/总体内存/MPS收益未作新声明；该轮代码未提交部署，当时下一主项ARCH-13。

## 早期进度快照（历史）

截至 2026-09-20：P0 加权进度 24.1%（19/79，局部实现口径，非整体验收率）。75 条探针已完成冻结和 Git 归档（`213dbe8`）：71 条复核通过、4 条人工裁决、0 条待决；M1-01 已实现，基线首项探针验收已勾选。现在进入 M1-02 / DEC-001 实验准备：已记录候选源码、环境和测量参数草案，并完成 2,661 个 chunk 的只读核验与 gold 映射（73 mapped、2 unmappable，保留并计 miss）。B/C 构建、候选适配器、low_trust 文档处理及正式运行清单仍待完成，尚无检索选型结论。证据与逐轮自审见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)，具体下一步见[实验准备说明](evals/experiments/lexical/README.md)。

本轮 `env -u DEBUG -u PYTHONPATH make check`：549 passed（485 单元 + 64 项 PostgreSQL 集成测试），格式、类型及 Schema 漂移检查通过；环境变量处理原因与验证边界见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)。

ARCH-09 持久反馈身份已完成代码核验：0025随机UUID与readiness运行指纹分离，旧namespace显式绑定保留评分ID/时间，克隆与恢复有校验契约。三库31表内容/5索引计数不变，全量2089 passed、70 skipped、536维护输入一致、0托管费用；八项工程自审通过，见[反馈身份契约](docs/FEEDBACK_IDENTITY.md)和[记录183](docs/reviews/2026-10-11-implementation-183-stable-feedback-identity.md)。当时下一主项ARCH-10；当前已按[记录184](docs/reviews/2026-10-11-implementation-184-batched-architecture-commits.md)分批提交，未重启或生产上线。

ARCH-13已补版本词表、KEK只读overlay、评分持久卷、8个监督入口与清理/Observe调度；隔离Docker卡死重启、真实PG毒事件/晚到审计记录保护通过，全量2136 passed/70 skipped、0托管费用。见[部署契约](docs/DEPLOYMENT_WORKERS.md)与[记录186](docs/reviews/2026-10-11-implementation-186-worker-deployment-and-supervision.md)。这是工程交付，目标环境长期驻留/容量仍待IDX-03/DEPLOY-02；该轮未提交或替换现有服务；后续CI门见下段。

ARCH-14已补required依赖失败门、架构显式检查与已发布配置真实容器启动；独立PG/internal网络、真实BGE向量及200→503就绪核验通过，全量2157 passed/70 skipped、556输入一致、0托管调用。见[CI契约](docs/CI_GATES.md)与[记录187](docs/reviews/2026-10-11-implementation-187-required-ci-and-container-gates.md)。远端CI/amd64冷构建仍待实际运行，本轮未提交、推送或替换共享服务；ARCH-12现已完成条件收益评估，见[记录188](docs/reviews/2026-10-11-implementation-188-request-transaction-assessment.md)及[事务方案](docs/REQUEST_TRANSACTION_PLAN.md)：12臂288次合成执行、5种变化诊断、全量2163/70、559输入一致、0费用；无限额未证明提速，Pool/事务拆分不启用。ARCH-15先核验和修复实际输出边界，不能将原型检测能力记为生产栅栏已完成。

2026-10-12：已完成记录185～188的五批提交与推送，并同步此前13个提交。再次required全量2163 passed、70 skipped，559维护输入一致、0托管费用；远端CI已触发尚未得出结论，没有部署。见[记录189](docs/reviews/2026-10-12-implementation-189-batched-push.md)；下一项ARCH-15实际最终输出核验。
