# 实现记录 184：按依赖分批提交架构与目标设计

日期：2026-10-11。实现者与自审核者：Codex，同一实现者，不是第二独立人工。任务：W-03/W-04。八项工程自审通过。

## 1. 授权、范围与提交方法

所有者本轮明确授权：“把目前的文件分批次提交，越细致越好”。开始 HEAD 为 `5a604050b9c0706bfd823685e5befcb9619d64a6`，259 个待提交状态路径，暂存区为空。没有按作者拆分，也没有一次性 `git add -A`。

先逐文件保存现状和原索引，再校验每轮备份的 SHA-256。使用独立临时索引构造历史阶段树，按实际依赖将审查、设计与各项架构修复串成 12 个功能提交；每批核对暂存路径、tree、Python 语法、diff 空白和凭据模式。原工作区最终代码不回退、不重写。最后第 13 批仅同步本记录、机器结果、README、阶段表与台账。

逐批代码/配置与对应已通过全量检查的工程工作树逐字节一致。下表的 533～581 项采用扩展口径，包含历史 Python 工具及锁文件；与记录 183 的 536 项维护输入不是同一统计范围，不相加。新建提交后的独立工作树另核对 536 项维护输入，零不符。

原有 259 是状态路径计数，包含搬移前后路径；Git 默认识别 4 个 rename，整体 `--stat` 为 255 个逻辑文件。下表按各批 `--name-only` 计数，跨批反复修改同一文件，不能加总当作独立文件数。

## 2. 批次总表

| 批次 | 提交 | 功能与任务 | 本批路径 | 工程快照核对输入 |
| --- | --- | --- | ---: | ---: |
| 1 | `828a580e4721` | 架构与代码质量审查 / ARCH/CODE 审查 | 3 | 0 |
| 2 | `e81adad1130d` | Harness 截止时间与取消 / ARCH-01 | 33 | 533 |
| 3 | `ce9093ea58e9` | 统一待办、目标 ADR 与 PV 场景 / W-03 / PLAN-01 / PLAN-02 | 18 | 533 |
| 4 | `dd216e275080` | 模型调用回执与费用归属 / ARCH-04 | 23 | 537 |
| 5 | `9bc628460cf1` | 共享单执行预算 / ARCH-11 | 33 | 540 |
| 6 | `255468dab0a1` | 任务租约与尝试所有权 / ARCH-05 | 19 | 541 |
| 7 | `1163a0a71c77` | 显式历史查询上下文 / ARCH-02 | 54 | 546 |
| 8 | `8372cd6297d4` | Skill 最终业务判断核验 / ARCH-03 | 17 | 551 |
| 9 | `7de38e7811a1` | 完整 Task 执行审计 / ARCH-06 | 24 | 555 |
| 10 | `2f092181314e` | 执行记录与诊断回放 / ARCH-07 | 44 | 563 |
| 11 | `4e7355775062` | 共用模块、生产装配与导入边界 / ARCH-08 | 121 | 577 |
| 12 | `fa751e0b8fcc` | 稳定反馈身份与恢复契约 / ARCH-09 | 19 | 581 |
| 13 | 本记录与台账所在提交；用 `git log -1` 查看 | 提交自审、当前状态与下一项 | 5 | 文档检查 |

## 3. 每批详细范围与文件清单

路径清单使用 `A` 新增、`M` 修改、`D` 删除；为便于审查旧模块移除，此处禁用 rename 合并显示。路径为历史提交范围，不表示旧路径目前仍存在。

### 批 1：架构与代码质量审查

提交：`828a580e47212b1401d3d74debdd383048c8accd`。任务：ARCH/CODE 审查。

保留只读审查、失败复现和未实现能力清单。仅增加审查材料。

本轮提交前：0 项变更 Python 语法检查，0 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

```text
A	docs/reviews/2026-10-10-architecture-audit-results.json
A	docs/reviews/2026-10-10-architecture-audit.md
A	docs/reviews/2026-10-10-code-quality-audit.md
```

### 批 2：Harness 截止时间与取消

提交：`e81adad1130d144bff82e4483b261f82ad21378d`。任务：ARCH-01。

嵌套/重试共享截止时间；SQL 取消、异步 HTTP 收束、翻译分支 finally 回收、本地 BGE 子进程与准入保护。保留失败、超时、资源回收反例。

本轮提交前：31 项变更 Python 语法检查，533 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[171](2026-10-10-implementation-171-harness-deadline-and-cancellation.md)。

```text
A	docs/reviews/2026-10-10-implementation-171-harness-deadline-and-cancellation.md
A	docs/reviews/2026-10-10-implementation-171-results.json
M	evals/harness/tools/safety_run.py
M	evals/harness/tools/skill_smoke.py
M	evals/harness/tools/smoke_ask.py
M	evals/replay/tools/replay_run.py
M	src/medops/api/app.py
M	src/medops/api/runtime.py
A	src/medops/core/deadline.py
M	src/medops/evals/runtime.py
M	src/medops/harness/contracts.py
M	src/medops/harness/nodes.py
M	src/medops/harness/retrieval_port.py
A	src/medops/infrastructure/db/deadline.py
A	src/medops/infrastructure/llm/async_transport.py
M	src/medops/infrastructure/llm/budget.py
M	src/medops/infrastructure/llm/meter.py
M	src/medops/infrastructure/llm/openai_gateway.py
M	src/medops/mcp/serve.py
A	src/medops/retrieval/inference_process.py
M	src/medops/retrieval/query_translation.py
M	src/medops/worker/serve.py
A	tests/integration/test_execution_deadline.py
M	tests/unit/evals/test_harness_runner_resume.py
M	tests/unit/evals/test_runtime.py
A	tests/unit/harness/test_deadline.py
M	tests/unit/harness/test_node_policy.py
M	tests/unit/harness/test_retrieval_concurrency.py
A	tests/unit/infrastructure/test_async_model_transport.py
M	tests/unit/infrastructure/test_llm_gateway.py
M	tests/unit/mcp/test_serve.py
A	tests/unit/retrieval/test_inference_process.py
M	tests/unit/skills/test_registry.py
```

### 批 3：统一待办、目标 ADR 与 PV 场景

提交：`ce9093ea58e9f91b92f9646144bd8a065fff19a1`。任务：W-03 / PLAN-01 / PLAN-02。

统一 141 个任务、八项自审、S0～S5；记录所有者目标/验收限制与首个 PV 资料整理范围、12 个合成开发用例。ADR 的剩余验收契约仍待沟通。

本轮提交前：0 项变更 Python 语法检查，533 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[174](2026-10-10-implementation-174-plan01-capability-and-scenario.md)。目标设计另见记录 172/173；该批不增加运行时能力。

```text
A	AGENTS.md
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/DEVELOPMENT_ROADMAP.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
M	docs/TASK_KNOWLEDGE_MAP.md
A	docs/adr/ADR-0012-agent-evolution-goals-and-acceptance.md
A	docs/agent/PLAN-01-capability-and-scenario.md
A	docs/reviews/2026-10-10-implementation-172-results.json
A	docs/reviews/2026-10-10-implementation-172-unified-agent-evolution-backlog.md
A	docs/reviews/2026-10-10-implementation-173-adr12-owner-constraints.md
A	docs/reviews/2026-10-10-implementation-173-results.json
A	docs/reviews/2026-10-10-implementation-174-plan01-capability-and-scenario.md
A	docs/reviews/2026-10-10-implementation-174-results.json
A	evals/agent/README.md
A	evals/agent/development/S0-pv-case-spec-v1.json
M	evals/holdout/README.md
```

### 批 4：模型调用回执与费用归属

提交：`dd216e275080c7b68bac09f76096d916c1a217cd`。任务：ARCH-04。

0023 迁移、持久调用回执、Trace/执行/attempt/预留绑定、失败与未知用量保守结算、真实并行账本测试。

本轮提交前：15 项变更 Python 语法检查，537 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[175](2026-10-11-implementation-175-call-receipts-and-fee-attribution.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/DEPLOY.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
A	docs/LLM_ACCOUNTING.md
A	docs/reviews/2026-10-11-implementation-175-call-receipts-and-fee-attribution.md
A	docs/reviews/2026-10-11-implementation-175-results.json
A	migrations/versions/0023_llm_call_receipts.py
M	src/medops/application/tasks.py
M	src/medops/harness/contracts.py
M	src/medops/harness/runtime.py
A	src/medops/infrastructure/llm/accounting.py
M	src/medops/infrastructure/llm/budget.py
M	src/medops/infrastructure/llm/gateway.py
M	src/medops/infrastructure/llm/meter.py
M	src/medops/infrastructure/llm/openai_gateway.py
M	src/medops/mcp/server.py
M	src/medops/skills/registry.py
A	tests/integration/test_llm_call_receipts.py
M	tests/integration/test_migrations.py
M	tests/unit/harness/test_deadline.py
A	tests/unit/infrastructure/test_llm_call_receipts.py
```

### 批 5：共享单执行预算

提交：`9bc628460cf1af34f75411ffea41cd7a4183a0d3`。任务：ARCH-11。

嵌套节点、重试、Ask/Skill/MCP/活动工具继承总 Token/费用/时间池；预算耗尽阻止后续调用，沿用所有者确认的上限推导。

本轮提交前：22 项变更 Python 语法检查，540 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[176](2026-10-11-implementation-176-shared-execution-budget.md)。

```text
M	.env.example
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/DEPLOY.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
M	docs/LLM_ACCOUNTING.md
M	docs/adr/ADR-0012-agent-evolution-goals-and-acceptance.md
M	docs/agent/PLAN-01-capability-and-scenario.md
A	docs/reviews/2026-10-11-implementation-176-results.json
A	docs/reviews/2026-10-11-implementation-176-shared-execution-budget.md
M	evals/harness/tools/safety_run.py
M	evals/harness/tools/skill_smoke.py
M	evals/harness/tools/smoke_ask.py
M	evals/replay/tools/replay_run.py
M	src/medops/api/runtime.py
M	src/medops/core/config.py
M	src/medops/evals/runtime.py
M	src/medops/harness/answer.py
M	src/medops/harness/contracts.py
M	src/medops/harness/dependencies.py
M	src/medops/harness/nodes.py
M	src/medops/harness/runtime.py
M	src/medops/infrastructure/llm/budget.py
A	src/medops/infrastructure/llm/execution_budget.py
M	src/medops/infrastructure/llm/factory.py
M	src/medops/infrastructure/llm/meter.py
M	src/medops/mcp/serve.py
M	src/medops/skills/registry.py
M	tests/integration/test_llm_call_receipts.py
M	tests/unit/evals/test_harness_runner_resume.py
A	tests/unit/harness/test_execution_budget.py
A	tests/unit/infrastructure/test_execution_budget.py
```

### 批 6：任务租约与尝试所有权

提交：`255468dab0a18019b2409cde614435ecbd8ba3b6`。任务：ARCH-05。

数据库时钟、领取/续租/提交 fence、从领取起计总时限、接管与旧 worker 费用留痕；两 worker 及行锁等待反例。

本轮提交前：10 项变更 Python 语法检查，541 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[177](2026-10-11-implementation-177-task-lease-and-ownership.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/DEPLOY.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
M	docs/LLM_ACCOUNTING.md
M	docs/agent/PLAN-01-capability-and-scenario.md
A	docs/reviews/2026-10-11-implementation-177-results.json
A	docs/reviews/2026-10-11-implementation-177-task-lease-and-ownership.md
M	src/medops/application/tasks.py
M	src/medops/infrastructure/db/tasks.py
M	src/medops/infrastructure/llm/accounting.py
M	src/medops/infrastructure/llm/budget.py
M	src/medops/infrastructure/llm/execution_budget.py
M	src/medops/worker/serve.py
M	tests/integration/test_tasks_store.py
A	tests/unit/application/test_task_lease.py
M	tests/unit/application/test_tasks.py
M	tests/unit/faults/test_main_chain_faults.py
```

### 批 7：显式历史查询上下文

提交：`1163a0a71c77027ff7db84037fa810d0afacb170`。任务：ARCH-02。

0024 迁移；Ask/Task/API Schema/OpenAPI、Skill 提示、缓存与诊断 Replay 绑定查询日期/历史意图，保留归档与权限反例。

本轮提交前：40 项变更 Python 语法检查，546 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[178](2026-10-11-implementation-178-historical-query-context.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/DEPLOY.md
A	docs/HISTORICAL_QUERIES.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
M	docs/agent/PLAN-01-capability-and-scenario.md
A	docs/reviews/2026-10-11-implementation-178-historical-query-context.md
A	docs/reviews/2026-10-11-implementation-178-results.json
A	migrations/versions/0024_trace_query_context.py
M	schemas/api/AskRequest.schema.json
M	schemas/api/ReplayReport.schema.json
M	schemas/api/ReplayRequest.schema.json
M	schemas/api/TaskCreateRequest.schema.json
M	schemas/openapi.json
M	src/medops/api/contracts.py
M	src/medops/api/ports.py
M	src/medops/api/routes/ask.py
M	src/medops/api/routes/observability.py
M	src/medops/api/runtime.py
M	src/medops/application/audit.py
M	src/medops/application/payloads.py
M	src/medops/application/replay.py
M	src/medops/application/tasks.py
A	src/medops/domain/query.py
M	src/medops/domain/skill.py
M	src/medops/domain/state.py
M	src/medops/harness/dependencies.py
M	src/medops/harness/nodes.py
M	src/medops/harness/retrieval_port.py
M	src/medops/harness/runtime.py
M	src/medops/infrastructure/db/audit.py
M	src/medops/retrieval/doc_focus.py
M	src/medops/skills/_structured.py
M	src/medops/skills/citation_verification.py
M	src/medops/skills/label_query.py
M	src/medops/skills/off_label_check.py
M	src/medops/skills/production.py
M	src/medops/skills/protocol_deviation.py
M	src/medops/skills/registry.py
M	tests/integration/test_audit_store.py
M	tests/integration/test_fact_recheck.py
M	tests/integration/test_migrations.py
M	tests/unit/api/test_ask_route.py
A	tests/unit/api/test_historical_context.py
M	tests/unit/api/test_payload_route.py
M	tests/unit/api/test_replay_route.py
M	tests/unit/api/test_task_routes.py
A	tests/unit/domain/test_query_context.py
A	tests/unit/harness/test_historical_context.py
M	tests/unit/harness/test_retrieval_cache_port.py
M	tests/unit/harness/test_run_ask.py
M	tests/unit/skills/test_matrix.py
M	tests/unit/skills/test_registry.py
```

### 批 8：Skill 最终业务判断核验

提交：`8372cd6297d4b06b8fa6733d840ba248d30a7868`。任务：ARCH-03。

引用、数值/单位、否定/条件、语义支持四项核验；两类二阶段比较严格解析与失败关闭；五类 Skill、预算、权限反例。

本轮提交前：10 项变更 Python 语法检查，551 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[179](2026-10-11-implementation-179-final-skill-judgment-verification.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
A	docs/SKILL_JUDGMENT_VERIFICATION.md
A	docs/reviews/2026-10-11-implementation-179-final-skill-judgment-verification.md
A	docs/reviews/2026-10-11-implementation-179-results.json
A	src/medops/domain/skill_judgment.py
M	src/medops/skills/_structured.py
M	src/medops/skills/off_label_check.py
M	src/medops/skills/protocol_deviation.py
A	src/medops/verification/skill_judgment.py
A	tests/unit/skills/test_final_judgment_fixtures.py
A	tests/unit/skills/test_final_judgments.py
M	tests/unit/skills/test_matrix.py
M	tests/unit/skills/test_risk_skills.py
A	tests/unit/verification/test_skill_judgment.py
```

### 批 9：完整 Task 执行审计

提交：`7de38e7811a17962aec73b94460a86e6ebcd0bc4`。任务：ARCH-06。

Ask/Task 共用审计、内层证据和候选/最终判断、安全与重试材料；正文只入受限加密载荷，无 key 仅元数据；原子提交/回滚。

本轮提交前：17 项变更 Python 语法检查，555 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[180](2026-10-11-implementation-180-task-execution-audit.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
A	docs/TASK_EXECUTION_AUDIT.md
A	docs/reviews/2026-10-11-implementation-180-results.json
A	docs/reviews/2026-10-11-implementation-180-task-execution-audit.md
M	src/medops/api/routes/ask.py
A	src/medops/application/execution_audit.py
M	src/medops/application/payloads.py
M	src/medops/application/tasks.py
A	src/medops/harness/audit.py
M	src/medops/harness/dependencies.py
M	src/medops/harness/nodes.py
M	src/medops/harness/runtime.py
M	src/medops/skills/_structured.py
M	src/medops/skills/citation_verification.py
M	src/medops/skills/registry.py
A	tests/integration/test_task_audit.py
M	tests/unit/api/test_payload_route.py
A	tests/unit/application/test_task_audit.py
M	tests/unit/application/test_tasks.py
M	tests/unit/faults/test_main_chain_faults.py
M	tests/unit/skills/test_final_judgments.py
```

### 批 10：执行记录与诊断回放

提交：`2f092181314e2825b5d0ab7fa575b81cedc75a51`。任务：ARCH-07。

输入、模型实际请求/参数/回复/回执、源工件摘要、渲染哈希及 Unicode 来源区间；原条件缺工件时 409 拒绝，不假称完整恢复。

本轮提交前：33 项变更 Python 语法检查，563 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[181](2026-10-11-implementation-181-execution-records-and-replay-boundaries.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
A	docs/EXECUTION_REPLAY.md
M	docs/HISTORICAL_QUERIES.md
M	docs/ITERATION_STAGES.md
M	docs/TASK_EXECUTION_AUDIT.md
A	docs/reviews/2026-10-11-implementation-181-execution-records-and-replay-boundaries.md
A	docs/reviews/2026-10-11-implementation-181-results.json
M	evals/harness/tools/safety_run.py
M	evals/harness/tools/smoke_ask.py
M	evals/replay/tools/replay_run.py
M	schemas/api/ReplayReport.schema.json
M	schemas/api/ReplayRequest.schema.json
M	schemas/openapi.json
M	src/medops/api/contracts.py
M	src/medops/api/routes/ask.py
M	src/medops/api/routes/observability.py
M	src/medops/api/runtime.py
M	src/medops/application/execution_audit.py
M	src/medops/application/payloads.py
M	src/medops/application/policy_loader.py
M	src/medops/application/replay.py
A	src/medops/application/replay_inputs.py
M	src/medops/application/tasks.py
A	src/medops/core/run_artifacts.py
M	src/medops/evals/run_conditions.py
M	src/medops/harness/answer.py
M	src/medops/harness/audit.py
M	src/medops/harness/dependencies.py
M	src/medops/harness/evidence_focus.py
A	src/medops/harness/execution_record.py
M	src/medops/harness/nodes.py
M	src/medops/harness/runtime.py
A	src/medops/infrastructure/llm/call_audit.py
M	src/medops/infrastructure/llm/meter.py
M	src/medops/infrastructure/llm/openai_gateway.py
M	src/medops/skills/registry.py
M	tests/integration/test_task_audit.py
A	tests/unit/api/test_replay_conditions.py
M	tests/unit/api/test_replay_route.py
M	tests/unit/application/test_task_audit.py
A	tests/unit/harness/test_execution_record_deadline.py
A	tests/unit/harness/test_rendered_provenance.py
A	tests/unit/infrastructure/test_model_call_audit.py
```

### 批 11：共用模块、生产装配与导入边界

提交：`4e7355775062e8e6e0bcbd1c6c57f4604c6055f7`。任务：ARCH-08。

application 契约、infrastructure 身份、knowledge 解析/PII/norm-v1、bootstrap 三入口装配与全部导入迁移；AST 边界检查纳入 make check。

本轮提交前：109 项变更 Python 语法检查，577 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[182](2026-10-11-implementation-182-shared-composition-and-import-boundaries.md)。

```text
M	Makefile
M	README.md
M	docs/CURRENT_TASKS.md
M	docs/DEVELOPMENT_ROADMAP.md
M	docs/ITERATION_PLAN.md
M	docs/ITERATION_STAGES.md
A	docs/PRODUCTION_COMPOSITION.md
M	docs/TASK_KNOWLEDGE_MAP.md
M	docs/api/CONTRACTS.md
M	docs/reviews/2026-10-10-architecture-audit.md
A	docs/reviews/2026-10-11-implementation-182-results.json
A	docs/reviews/2026-10-11-implementation-182-shared-composition-and-import-boundaries.md
M	evals/experiments/lexical/tools/export_chunk_snapshot.py
M	evals/glossary/tools/build_glossary.py
M	evals/main_set/tools/build_conflict_fixtures.py
M	evals/main_set/tools/build_corpus.py
M	evals/main_set/tools/check_drafts.py
M	evals/main_set/tools/draft_common.py
M	evals/main_set/tools/make_sheets.py
M	evals/probe/precise_clause/drafts/v1/tooling/assemble.py
M	evals/probe/precise_clause/drafts/v1/tooling/draft_samples.py
M	evals/probe/precise_clause/drafts/v1/tooling/prepare_review_changes.py
M	evals/probe/precise_clause/drafts/v1/tooling/review_pack.py
M	evals/probe/precise_clause/drafts/v2/tooling/apply_owner_adjudication_2026_09_20.py
M	evals/probe/precise_clause/drafts/v2/tooling/apply_resolutions.py
M	evals/probe/precise_clause/drafts/v2/tooling/apply_round3_2026_09_20.py
M	evals/probe/precise_clause/drafts/v2/tooling/derive_twins.py
M	evals/probe/precise_clause/drafts/v2/tooling/review_pack.py
M	scripts/benchmark_rerank_batches.py
A	scripts/check_architecture.py
M	scripts/demo.py
M	src/medops/api/app.py
D	src/medops/api/auth.py
D	src/medops/api/contracts.py
A	src/medops/api/headers.py
M	src/medops/api/openapi.py
M	src/medops/api/ports.py
M	src/medops/api/responses.py
M	src/medops/api/routes/admin.py
M	src/medops/api/routes/ask.py
M	src/medops/api/routes/observability.py
M	src/medops/api/routes/tasks.py
D	src/medops/api/runtime.py
M	src/medops/api/serve.py
M	src/medops/application/admin.py
M	src/medops/application/audit.py
A	src/medops/application/contracts.py
M	src/medops/application/payloads.py
M	src/medops/application/replay.py
M	src/medops/application/replay_inputs.py
A	src/medops/application/search.py
M	src/medops/application/tasks.py
A	src/medops/bootstrap/__init__.py
A	src/medops/bootstrap/connections.py
A	src/medops/bootstrap/identity.py
A	src/medops/bootstrap/policies.py
A	src/medops/bootstrap/retrieval.py
A	src/medops/bootstrap/runtime.py
A	src/medops/bootstrap/search.py
M	src/medops/contracts_export.py
M	src/medops/domain/common.py
M	src/medops/evals/annotation_revision.py
M	src/medops/evals/probe/chunk_mapping.py
M	src/medops/evals/probe/extract.py
D	src/medops/evals/probe/pii.py
M	src/medops/evals/probe/validator.py
M	src/medops/harness/evidence_focus.py
M	src/medops/infrastructure/db/tasks.py
A	src/medops/infrastructure/identity.py
M	src/medops/ingestion/chunker.py
M	src/medops/ingestion/pipeline.py
A	src/medops/knowledge/__init__.py
A	src/medops/knowledge/normalization.py
A	src/medops/knowledge/pdf.py
A	src/medops/knowledge/pii.py
M	src/medops/mcp/serve.py
M	src/medops/mcp/server.py
M	src/medops/mcp/service.py
M	src/medops/retrieval/cache.py
M	src/medops/retrieval/lexical/boundary.py
D	src/medops/retrieval/lexical/normalization.py
M	src/medops/retrieval/lexical/pg_search_bm25.py
M	src/medops/retrieval/lexical/pg_textsearch_bm25.py
M	src/medops/retrieval/lexical/pg_textsearch_departmental.py
M	src/medops/retrieval/lexical/pg_zhparser_fts.py
M	src/medops/retrieval/lexical/tokenizer.py
M	src/medops/retrieval/rerank.py
M	src/medops/retrieval/rewrite.py
M	src/medops/retrieval/vector/boundary.py
M	src/medops/retrieval/vector/embedding.py
M	src/medops/retrieval/vector/pg_vector.py
M	src/medops/worker/serve.py
M	tests/integration/test_ingestion.py
M	tests/integration/test_metrics_source.py
M	tests/integration/test_principals.py
M	tests/integration/test_task_audit.py
M	tests/integration/test_tasks_store.py
M	tests/unit/api/test_admin_routes.py
M	tests/unit/api/test_ask_route.py
M	tests/unit/api/test_auth.py
M	tests/unit/api/test_contracts.py
M	tests/unit/api/test_historical_context.py
M	tests/unit/api/test_jwks_discovery.py
M	tests/unit/api/test_metrics_route.py
M	tests/unit/api/test_openapi.py
M	tests/unit/api/test_payload_route.py
M	tests/unit/api/test_replay_route.py
M	tests/unit/api/test_retrieval_readiness.py
M	tests/unit/api/test_runtime_connect.py
M	tests/unit/api/test_schema_semantics.py
M	tests/unit/application/test_task_audit.py
M	tests/unit/application/test_tasks.py
A	tests/unit/bootstrap/test_composition.py
A	tests/unit/bootstrap/test_connections.py
A	tests/unit/docs/test_architecture_boundaries.py
M	tests/unit/evals/fixture_builder.py
M	tests/unit/evals/fixture_builder_main.py
M	tests/unit/evals/test_chunk_mapping.py
M	tests/unit/evals/test_extract.py
M	tests/unit/evals/test_pii_exceptions.py
M	tests/unit/faults/test_main_chain_faults.py
M	tests/unit/ingestion/test_chunker.py
M	tests/unit/mcp/test_serve.py
M	tests/unit/mcp/test_server.py
M	tests/unit/retrieval/test_normalization.py
M	tests/unit/skills/test_final_judgments.py
```

### 批 12：稳定反馈身份与恢复契约

提交：`fa751e0b8fccc8522b75774e1638058c2574dae5`。任务：ARCH-09。

0025 持久事实库 UUID、稳定反馈 namespace/游标、旧来源显式绑定、DR/独立克隆检查；补元数据最小权限清单和受控时钟真实 DB 接管测试。

本轮提交前：13 项变更 Python 语法检查，581 项工程快照代码/配置比对，暂存 diff --check、tree 与路径集一致性通过。

原工程实现、失败与复测记录：[183](2026-10-11-implementation-183-stable-feedback-identity.md)。

```text
M	README.md
M	docs/CURRENT_TASKS.md
A	docs/FEEDBACK_IDENTITY.md
M	docs/ITERATION_STAGES.md
A	docs/reviews/2026-10-11-implementation-183-results.json
A	docs/reviews/2026-10-11-implementation-183-stable-feedback-identity.md
A	migrations/versions/0025_fact_plane_identity.py
M	scripts/db_restore_drill.py
A	src/medops/infrastructure/db/fact_plane.py
A	src/medops/infrastructure/feedback_identity.py
M	src/medops/infrastructure/observability.py
M	src/medops/worker/observability.py
M	tests/integration/test_feedback_export.py
M	tests/integration/test_loop_role_permissions.py
M	tests/integration/test_migrations.py
M	tests/integration/test_rls.py
M	tests/integration/test_tasks_store.py
A	tests/unit/infrastructure/test_feedback_identity.py
M	tests/unit/skills/test_registry.py
```

## 4. 本轮验证及已知限制

完整门禁在第 12 批提交 `fa751e0b8fccc8522b75774e1638058c2574dae5` 的新独立工作树运行，命令为 `env -u DEBUG PYTHONPATH=<snapshot>/src:<snapshot> make check`，退出码 0。

结果：**2089 passed、70 skipped、1 warning，pytest 61.0 秒**；ruff、503 维护文件格式、216 源文件 mypy、216 模块架构边界（0 违例、2 精确允许边）、四套评测审计和 Schema 漂移检查通过。

70 个跳过仍为可选 DEC-001 B/C 环境缺失；必需 PostgreSQL、Redis 及候选 D 测试由完整门禁执行。原认证反例的短 HMAC 测试 warning、两个 unmappable gold、独立人工缺口与未见盲测缺口仍保留。

最后一批只变更文档；文档定向测试 `pytest -q tests/unit/docs` 退出 0：27 passed / 2.00 秒；5 份文档、140 个本地链接、141 个任务 ID、JSON 和 diff 检查通过，零缺失/重复；生产代码 SHA 与完整门禁快照再次比对。具体结果见同目录机器结果文件。

本轮先前一次精确 apply_patch 因台账内容处于同一长行而未匹配，工具拒绝修改；改为带唯一命中断言的精确替换，没有覆盖整段旧内容。之后历史备份哈希、语法、白名单、凭据模式扫描、暂存校验和逐批 commit 均通过。 最后一次全文件凭据扫描因缺少词边界，把历史路径中 `task-lease-and-ownership` 的 `sk-` 子串误报为密钥；命令在暂存前停止，没有输出匹配内容。补上凭据前缀词边界后复核，真实凭据命中为0；不修改原路径或生产代码。若完整门禁出现失败，保留真实日志并修复复测；不能用历史成绩代替本轮失败。

历史记录 171～183 中的“未提交”、`committed=false` 和基线 HEAD 保留原时点事实；此次统一提交状态由本记录和当前台账追加说明，不改写原实验/实现历史。

提交不等于发布：没有托管模型调用，0 USD；没有业务库迁移、服务重启、真实反馈导出、部署或推送。`output/pdf`、`.env`、PDF 原件、队列、备份和本地日志未进入提交。Agent/自进化、原条件恢复、Task/MCP 精确回放、PLAN-02 剩余契约、真实语义校准、独立人工和合格盲测保持原状态。

## 5. 八项自审核

| 自审项 | 结论 | 证据与范围 |
| --- | --- | --- |
| 需求与范围 | 通过 | 259 原路径备份，按 12 个功能切片与 1 个记账切片提交；没有按作者或目录强拆依赖 |
| ADR 与阶段硬门 | 通过 | ADR-0012/PLAN-01 和原待答事项完整保留；未改变 S2/S3、实验激活、盲测、生产签字门 |
| 正确性与失败路径 | 通过 | 每批历史代码与通过快照一致；暂存 tree/路径/语法/diff 校验；最终 Git 树再运行完整门禁 |
| 权限与数据 | 通过 | 未改冻结 gold、原评测数据/历史结果、默认模型/ACL/发布指针；仅纳入原已审查的迁移/API Schema/合成开发规格；没有凭据/PDF/受限正文 |
| 预算、取消与副作用 | 通过 | 本轮无托管请求，0 USD；不执行业务库迁移、重启、导出、部署或推送；既有费用/取消实现按各批保留 |
| 追溯与版本 | 通过 | 保存初始 HEAD、备份 SHA、每批完整 commit/tree/路径/证据；历史状态按时点保留 |
| 验证充分性 | 通过 | 536 项提交后维护输入一致；完整门禁与文档定向验证；明确跳过与质量/人工证据限制 |
| 状态与文档 | 通过 | 141 任务 ID 保留；W-03 经 IN_PROGRESS/REVIEW/DONE，W-04 复测经 REVIEW/DONE；下一项 ARCH-10；最终 5 文档链接/JSON 校验 |

## 6. 回滚与下一步

本轮备份、计划、提交消息、逐批暂存统计、全量检查日志与复测证据在忽略的 `.local/commit184/`，验证工作树由 `.local/commit184-worktree-path` 定位。移除临时验证目录前先留存必要日志。

如需撤销功能，按依赖从后向前 `git revert` 对应提交并重新验证；不要将 `git reset --hard` 用作工作区清理。代码回退不会自动撤销本机已完成的 0023～0025 迁移；0025 身份的降级/再升级会破坏稳定标识，遵守反馈恢复契约。

提交整理完成后恢复主项 ARCH-10：共享重排 scorer、避免重复权重初始化和并发重复加载。该项尚未开始；后续付费实验继续逐次授权。
