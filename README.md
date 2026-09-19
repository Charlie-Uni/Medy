# Medy

MedOps Copilot 是面向医学事务、药物警戒和临床运营的可信医学 RAG 与受控 Agent 项目。

开发范围、硬约束、里程碑和逐项验收以 [工程基线与开发 Checklist](docs/ENGINEERING_BASELINE.md) 为准。

已完成工作、全部待办、选做增强与对应面试基础知识，见 [开发进度与边做边学路线](docs/DEVELOPMENT_ROADMAP.md)。

每个任务的当前状态与对应基础知识点，见 [任务与知识点对照](docs/TASK_KNOWLEDGE_MAP.md)。

截至 2026-09-20：P0 加权进度 22.8%（局部实现口径，非整体验收率）；基础工程与契约、数据库 RLS、16 份文档入库已有。75 条探针已完成本地冻结：71 条复核通过、4 条争议经人工裁决、0 条待决；带页文本的完整 frozen 校验为零错误、零警告。机构邮箱按已有人工依据作精确例外，复核模型如实记录服务别名及后端版本未暴露。Git 归档尚未完成，M1-01 保持“部分”。确认依据见[人工确认记录](evals/probe/precise_clause/drafts/v1/review/owner_confirmations_2026-09-19.md)，逐轮自审与冻结证据见[实现记录 26](docs/reviews/2026-09-20-implementation-26-probe-review-and-freeze.md)，下一步见路线图 §8.3 和知识对照 §10。

本轮 `env -u DEBUG -u PYTHONPATH make check`：482 passed（418 单元 + 64 项 PostgreSQL 集成测试），格式、类型及 Schema 漂移检查通过；环境变量处理原因与验证边界见[实现记录 26](docs/reviews/2026-09-20-implementation-26-probe-review-and-freeze.md)。
