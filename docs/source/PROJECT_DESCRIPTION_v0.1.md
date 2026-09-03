# MedOps Copilot 项目描述 v0.1

> - 来源：用户在项目首次请求中提供的项目描述。
> - 固化日期：2026-09-03。
> - 收录边界：仅收录项目标题、背景、解决方案、验收口径、可替换的平台能力描述和技术栈；不包含用户角色设定、工作方式或后续执行指令。

## 原文

**MedOps Copilot｜医药合规与临床运营 Agent：基于 Harness Engineering 的可信医学 RAG 与受控自进化系统**　`2026.06–至今（开发中）`

**项目背景**

面向医学事务、药物警戒和临床运营团队，处理药品说明书、临床试验方案、SOP 与医学指南的检索、核验和合规问答。传统 RAG 容易引用失效版本、遗漏精确条款或生成无依据医学结论，也缺少部门权限、执行审计和反馈改进机制。项目计划构建具备**可信医学 RAG、Agent Harness、安全护栏和受控自进化 Loop** 的医药知识与运营助手，全程使用公开、脱敏或合成数据。

**解决方案**

- **Agent Harness 编排治理：** 基于 LangGraph 将执行链路固定为 `Intent → Retrieve → Evidence Verify → Safety Check → Answer / Escalate` 状态机；使用 Pydantic/JSON Schema 约束节点输入输出，通过 Skill Registry 管理医学工具及调用权限，并加入超时重试、失败降级、幂等控制、人工升级和 Trace 重放，防止 Agent 跳过检索或直接生成医学结论。

- **可信医学知识治理：** 使用 PostgreSQL 建立事实平面，维护文档 `draft / active / archived` 状态、版本链、生效时间、来源哈希、页码和章节信息；pgvector 只负责语义候选召回，命中后必须回查原始文档，验证版本状态与访问权限后才能进入回答上下文。

- **混合检索与证据核验：** 针对药品名称、剂量、时间窗、方案编号和不良事件术语等精确信息，设计 `BM25 + pgvector + RRF + Reranker` 检索链路；Query Rewriter 结合医学术语表与会话实体生成查询，Verifier 检查答案中的剂量、适应证、时间节点和引用是否得到原文支持。

- **医学 Skills 与安全约束：** 将药品说明书查询、不良事件线索提取、超说明书用药检查、方案偏离核验及医学引用验证封装为可执行 Skills；对证据不足、版本冲突、越权访问、提示词注入和高风险医学问题执行拒答或人工升级，不提供诊断和处方建议。

- **受控自进化 Loop：** 实现 `Execute → Observe → Reflect → Adapt → Approve → Deploy` 闭环，采集用户纠错、点踩、追问和 Verifier 结果，将 bad case 归因为 `retrieval / intent / generation / knowledge_gap / safety`；自动生成 Prompt、Rule、Skill 或检索参数候选，但禁止在线直接修改生产策略，必须经过历史 Trace 回放、人工审核、灰度发布和指标门禁才能生效。

- **评测、可观测性与服务集成：** 使用 Langfuse 和 OpenTelemetry 记录检索证据、节点决策、工具调用、延迟、Token 与成本；通过 FastAPI 提供业务接口，并将受控医学检索能力封装为只读 MCP Server，使外部 Agent 在继承用户身份和权限的前提下调用知识服务。

**验收口径（完成后替换为实测结果）**

- 接入 300–500 份公开药品说明书、临床方案、SOP 和医学指南，构建不少于 300 条带文档版本、页码及证据标注的评测样本；目标 Recall\@5 ≥ 85%、引用准确率 ≥ 95%、失效版本引用率为 0%。

- 建设不少于 150 条安全测试样本，覆盖越权访问、提示词注入、无依据医学结论和高风险问题；目标正确拒答率 ≥ 95%、跨部门越权拦截率 ≥ 98%、高风险问题人工升级召回率 ≥ 95%。

- 每轮策略更新使用不少于 200 条历史 Trace 离线回放；发布门槛为目标任务成功率提升不少于 5 个百分点、非目标能力下降不超过 1 个百分点，并支持版本审计与一键回滚。

- 性能目标为普通医学问答 P95 ≤ 8 秒、复杂 Skill 工作流 P95 ≤ 15 秒；通过上下文裁剪、检索缓存和模型路由，将同等回答质量下的单次 Token 消耗降低至少 25%。

**如需突出后端与平台能力，可替换的两条**

- 基于 FastAPI、PostgreSQL 和 Redis 搭建异步 Agent 服务，统一管理工作流执行、文档入库、Loop 任务、离线回放和 Skill 发布，持久化 `queued / running / completed / failed` 状态并提供失败重试和进度查询。

- 将医学事务、药物警戒和临床运营能力拆分为独立 Skill 与权限域，通过部门身份和文档 ACL 强制过滤；支持并行工具调用、部分结果合并、超时降级和完整审计，避免跨部门知识泄露。

**技术栈：** Python、FastAPI、LangGraph、Harness Engineering、Agent DAG、可信 RAG、Feedback Loop、Skill Workflow、PostgreSQL/pgvector、BM25、RRF、Reranker、Redis、Pydantic、Langfuse、OpenTelemetry、MCP、Docker
