# Medy

MedOps Copilot 是面向医学事务、药物警戒和临床运营的可信医学 RAG 与受控 Agent 项目。

开发范围、硬约束、里程碑和逐项验收以 [工程基线与开发 Checklist](docs/ENGINEERING_BASELINE.md) 为准。

已完成工作、全部待办、选做增强与对应面试基础知识，见 [开发进度与边做边学路线](docs/DEVELOPMENT_ROADMAP.md)。

每个任务的当前状态与对应基础知识点，见 [任务与知识点对照](docs/TASK_KNOWLEDGE_MAP.md)。

## 最新执行入口（2026-10-10）

按用户确认的十项优先级及每轮自审规则推进，见[当前任务台账](docs/CURRENT_TASKS.md)和[分阶段执行与自审](docs/ITERATION_STAGES.md)。评测标准修订、来源契约、回放绑定和模型裁判校准已经形成冻结的 `probe-v4` 与 `main-v5-provisional`；第二独立人工仍未具备，因此相应结论继续标为 provisional。

生产词法通道已按项目所有者决定切换到部门隔离的 `pg_textsearch` BM25：PostgreSQL 17、extension 1.5.1、migration 0022，MA/PV/CO 各用独立物理语料，避免 RLS 隐藏行参与跨部门 IDF/词频统计。正式库与安全库已完成逻辑迁移、索引构建和 readiness 核验，旧 PG16 卷及逐库逻辑备份保留。设计、实测数据、故障和回滚边界见[实现记录 162](docs/reviews/2026-10-09-implementation-162-production-bm25-cutover.md)，许可与发布资产见[许可记录](docs/reviews/2026-10-09-licence-dossier-pg-textsearch.md)。最新本地全量检查为 1730 passed、70 skipped；新冻结集上的付费检索与答案级 BM25 对照仍需单独授权，工程切换不等同于质量门禁通过。

Langfuse v4.54.0 已以同网络、metadata-only 方式部署：真实 OTLP trace、评分与反馈类别关联、API 回读及服务中断后的队列恢复均通过，模型调用 0、费用 0；登录后的 UI detail 仍待人工目视。启动与复验见 [Langfuse 运维说明](docs/LANGFUSE.md)，实现与失败补救见[记录 163](docs/reviews/2026-10-09-implementation-163-langfuse-deployment-and-recovery.md)。

Redis 候选缓存已切换到本机主运行配置：主库与 safety 使用独立 namespace，Compose 常驻消费者已清空 338/339 条历史失效事件，启用缓存时积压会进入 readiness，断连时安全回源。真实问题流量的命中率、完整问答 P95、质量与费用收益仍待 CACHE-10 付费对照，不能用 1.14 ms 的纯命中 smoke 代替。实现与演练见[记录 164](docs/reviews/2026-10-09-implementation-164-redis-cache-cutover.md)。

向量检索现固定定制规划模式，避免连接复用后自动换计划导致候选漂移；107 题新连接/复用的候选与分数逐项一致，重复排名无变化。通用计划候选在主集 554 道 gold 题上仅 +0.54 pp，却有一题受保护切片回归和更高的排序扫描耗时，未选为默认值。基础组合版本为 `5ae70f4f…28d9`；这次是稳定性修复，未宣称完整问答召回或 P95 改善。详细错误、取舍与复现证据见[记录 167](docs/reviews/2026-10-09-implementation-167-channel-overlap-and-vector-plan-drift.md)、[记录 168](docs/reviews/2026-10-10-implementation-168-fixed-vector-plan-and-quality-audit.md)。

## 早期进度快照（历史）

截至 2026-09-20：P0 加权进度 24.1%（19/79，局部实现口径，非整体验收率）。75 条探针已完成冻结和 Git 归档（`213dbe8`）：71 条复核通过、4 条人工裁决、0 条待决；M1-01 已实现，基线首项探针验收已勾选。现在进入 M1-02 / DEC-001 实验准备：已记录候选源码、环境和测量参数草案，并完成 2,661 个 chunk 的只读核验与 gold 映射（73 mapped、2 unmappable，保留并计 miss）。B/C 构建、候选适配器、low_trust 文档处理及正式运行清单仍待完成，尚无检索选型结论。证据与逐轮自审见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)，具体下一步见[实验准备说明](evals/experiments/lexical/README.md)。

本轮 `env -u DEBUG -u PYTHONPATH make check`：549 passed（485 单元 + 64 项 PostgreSQL 集成测试），格式、类型及 Schema 漂移检查通过；环境变量处理原因与验证边界见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)。
