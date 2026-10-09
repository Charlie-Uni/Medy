# Medy

MedOps Copilot 是面向医学事务、药物警戒和临床运营的可信医学 RAG 与受控 Agent 项目。

开发范围、硬约束、里程碑和逐项验收以 [工程基线与开发 Checklist](docs/ENGINEERING_BASELINE.md) 为准。

已完成工作、全部待办、选做增强与对应面试基础知识，见 [开发进度与边做边学路线](docs/DEVELOPMENT_ROADMAP.md)。

每个任务的当前状态与对应基础知识点，见 [任务与知识点对照](docs/TASK_KNOWLEDGE_MAP.md)。

## 最新执行入口（2026-10-08）

按用户确认的十项优先级及每轮自审规则推进，见[当前任务台账](docs/CURRENT_TASKS.md)和[分阶段执行与自审](docs/ITERATION_STAGES.md)。当前在阶段 1：评测标准与数据。修订草案 v2 为 19 条、39 个证据单元，第一人工已确认；独立模型复核已完成 19/19（15 同意、4 争议，待人工裁决），第二人工暂无，继续 provisional。记录 132 固定评分版本，记录 135 固化新回放安全输入，[记录 136](docs/reviews/2026-10-08-implementation-136-answer-quality-evidence.md)补逐句引用快照及语义/完整性诊断。[记录 137](docs/reviews/2026-10-08-implementation-137-index-readiness.md)补实际索引就绪和 outbox 积压监测，[记录 138](docs/reviews/2026-10-08-implementation-138-index-consumer-recovery.md)新增持续消费者并完成两库索引积压恢复，[记录 139](docs/reviews/2026-10-08-implementation-139-evaluation-preflight.md)统一正式工具的索引预检，[记录 140](docs/reviews/2026-10-08-implementation-140-bound-run-resume.md)绑定主集/安全集续跑条件并修复重试费用、发布提示接线，[记录 141](docs/reviews/2026-10-08-implementation-141-trace-correlation-and-redaction.md)统一遥测/审计 trace ID并修复异常脱敏，[记录 142](docs/reviews/2026-10-08-implementation-142-durable-observation-scores.md)补持久评分队列、只读反馈采集和评测分数关联，Langfuse 后端仍待部署验收。[记录 143](docs/reviews/2026-10-08-implementation-143-budgeted-model-review.md)完成预算受控的 19 题模型复核，估算 2.917528 USD，具体待决事项见[裁决表](evals/main_set/drafts/revision-2026-10-08-v2/review/adjudication_2026-10-08.md)。正式新数据版本、真实裁判校准与评测尚待完成。测试通过不代表阶段或业务门禁通过。[记录 144](docs/reviews/2026-10-08-implementation-144-refactor-verification-and-depiling.md)核验并清理重构；[记录 145](docs/reviews/2026-10-08-implementation-145-operational-ledgers-and-mcp-parity.md)补齐 Langfuse/outbox 死信、PostgreSQL 费用预留账本和 MCP 检索一致性。[记录 146](docs/reviews/2026-10-08-implementation-146-task-ledger-and-paid-run-preflight.md)修正本机 DSN 阻断，将两个正式本地事实库升至 0021，补应用角色预算读取，并明确所有模型调用逐次取得费用批准。最新全量检查 1628 passed、70 skipped。

## 早期进度快照（历史）

截至 2026-09-20：P0 加权进度 24.1%（19/79，局部实现口径，非整体验收率）。75 条探针已完成冻结和 Git 归档（`213dbe8`）：71 条复核通过、4 条人工裁决、0 条待决；M1-01 已实现，基线首项探针验收已勾选。现在进入 M1-02 / DEC-001 实验准备：已记录候选源码、环境和测量参数草案，并完成 2,661 个 chunk 的只读核验与 gold 映射（73 mapped、2 unmappable，保留并计 miss）。B/C 构建、候选适配器、low_trust 文档处理及正式运行清单仍待完成，尚无检索选型结论。证据与逐轮自审见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)，具体下一步见[实验准备说明](evals/experiments/lexical/README.md)。

本轮 `env -u DEBUG -u PYTHONPATH make check`：549 passed（485 单元 + 64 项 PostgreSQL 集成测试），格式、类型及 Schema 漂移检查通过；环境变量处理原因与验证边界见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)。
