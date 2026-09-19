# Medy

MedOps Copilot 是面向医学事务、药物警戒和临床运营的可信医学 RAG 与受控 Agent 项目。

开发范围、硬约束、里程碑和逐项验收以 [工程基线与开发 Checklist](docs/ENGINEERING_BASELINE.md) 为准。

已完成工作、全部待办、选做增强与对应面试基础知识，见 [开发进度与边做边学路线](docs/DEVELOPMENT_ROADMAP.md)。

每个任务的当前状态与对应基础知识点，见 [任务与知识点对照](docs/TASK_KNOWLEDGE_MAP.md)。

截至 2026-09-20：P0 加权进度 24.1%（19/79，局部实现口径，非整体验收率）。75 条探针已完成冻结和 Git 归档（`213dbe8`）：71 条复核通过、4 条人工裁决、0 条待决；M1-01 已实现，基线首项探针验收已勾选。现在进入 M1-02 / DEC-001 实验准备：已记录候选源码、环境和测量参数草案，并完成 2,661 个 chunk 的只读核验与 gold 映射（73 mapped、2 unmappable，保留并计 miss）。B/C 构建、候选适配器、low_trust 文档处理及正式运行清单仍待完成，尚无检索选型结论。证据与逐轮自审见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)，具体下一步见[实验准备说明](evals/experiments/lexical/README.md)。

本轮 `env -u DEBUG -u PYTHONPATH make check`：549 passed（485 单元 + 64 项 PostgreSQL 集成测试），格式、类型及 Schema 漂移检查通过；环境变量处理原因与验证边界见[实现记录 27](docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)。
