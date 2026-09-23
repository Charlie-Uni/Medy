# MedOps Copilot 工程基线与开发 Checklist

> - 基线版本：v0.6
> - 更新日期：2026-09-10
> - 状态：已冻结
> - 原始需求来源：[MedOps Copilot 项目设计文档 v0.1](source/MedOps_Copilot_项目设计文档_v0.1.pdf)与[用户提供的项目描述 v0.1](source/PROJECT_DESCRIPTION_v0.1.md)（SHA-256 均见 [SHA256SUMS](source/SHA256SUMS)；`300-500` 份文档目标来自项目描述）
> - 编制时仓库状态：仅有 README，尚未开始工程实现
> - 修订记录：v0.1 初版；v0.2 按 [第一轮审核记录](reviews/2026-09-03-baseline-review-01.md) 的 9 项技术修正与 8 项决策修订；v0.3 按 [第二轮审核记录](reviews/2026-09-03-baseline-review-02.md) 修正 3 处一致性问题并固定幂等并发语义，来源补录与冻结核验见[第三轮审核记录](reviews/2026-09-03-baseline-review-03.md)；v0.4 按 [ADR-0002](adr/ADR-0002-lexical-retrieval-selection.md) 将词法方案对比前置到 M1 入口，修订与复核见[第四轮审核记录](reviews/2026-09-03-baseline-review-04.md)；v0.5 按[第五轮审核记录](reviews/2026-09-08-baseline-review-05.md) 定义 `retrieval_version` 复合规则、合格候选谓词与并列规则、5.8 切片诊断规则的作用域、5.9 主评测集分层复核政策，并发布探针集冻结规范 [evals/probe/precise_clause/SPEC.md](../evals/probe/precise_clause/SPEC.md)；v0.6 按 [ADR-0003](adr/ADR-0003-corpus-source-license-policy.md) 固定语料来源白名单与四级许可准入（新增 DEC-011），修订与复核见[第六轮审核记录](reviews/2026-09-09-baseline-review-06.md)，候选清单审核决策与证据结构修正见[第七轮记录](reviews/2026-09-10-baseline-review-07.md)

## 0. 本文件怎么用

本文件是后续设计、编码、评审、测试和发布的执行基线。原始设计文档定义业务目标，本文件将其收敛为可验证的工程任务和门禁。

- `P0` 是当前项目必须完成的范围；未通过不得宣称项目完成。
- `P1/P2` 是选做增强；只有满足其前置条件后才进入开发。
- Checklist 只有在有代码、测试、评测报告或运行记录作为证据时才能勾选。
- 任何实现若与“硬约束”冲突，以更严格的安全、权限和证据规则为准。
- 需求变更必须先更新本文件，再改代码；不得让代码先行形成事实标准。
- 每轮工作只完成一个可验证的纵向切片，优先确认逻辑、契约和测试，不为未来可能性堆砌代码。
- 标注“基线新增”的条目不来自设计文档，而是审核决策引入的约束；来源与决策记录见 `docs/reviews/`。

### 状态标记

- `[ ]` 未开始
- `[~]` 进行中；提交前应还原为 `[ ]` 或改为 `[x]`
- `[x]` 已完成且有可复核证据
- `[!]` 阻塞；必须在“待决策与阻塞项”记录原因

## 1. 项目目标与边界

### 1.1 一句话目标

为医学事务（MA）、药物警戒（PV）和临床运营（CO）提供一个只依据已校验原文、受部门权限约束、全过程可审计，并能经人工审批持续改进的知识与运营 Agent。

### 1.2 P0 必须交付

1. 药品说明书、临床试验方案、SOP、医学指南的版本化入库、检索和原文回看。
2. 固定执行 `Intent -> Retrieve -> Evidence Verify -> Safety Check -> Answer / Escalate`，不能绕过检索直接回答。
3. `词法检索 + pgvector + RRF + Reranker` 的混合检索，以及事实平面回查。
4. 文档状态、版本链、生效时间、来源哈希、页码、章节和 ACL 治理。
5. 说明书查询、不良事件线索提取、超说明书用药检查、方案偏离核验、医学引用验证五类 Skill。
6. 证据核验、越权拦截、提示词注入防护、高风险拒答与人工升级。
7. FastAPI 同步问答、异步任务、反馈、管理和 Trace 回放接口。
8. 只读 MCP Server，复用相同的身份、ACL、检索和审计链路。
9. Trace、指标、成本、审计、离线评测和受控策略发布闭环。
10. Docker 化的可重复开发与部署环境，以及最小生产安全基线。

### 1.3 当前明确不做

- 诊断、处方、个体化用药或紧急医疗建议。
- 真实患者数据、未脱敏 PHI/PII 或真实病例处理。
- 无人工审批的在线自修改、自训练或自动发布。
- MCP 写操作、文档在线编辑或协作。
- 跨租户 SaaS、实时流式 Loop。
- 把图表、医学影像作为可推理证据的多模态 RAG；它属于 P2 研究型增强（见 7.2）。

## 2. 不可破坏的工程不变量

以下规则必须在代码、数据库约束、测试和评测中同时体现，不能只写在 Prompt 中。

### 2.1 医学安全与回答

- `INV-SAF-01`：诊断、处方、个体剂量调整、紧急医疗意图必须拒答并升级，不提供“软性建议”。
- `INV-SAF-02`：证据不足时明确说明不足；不得用模型常识补齐医学事实。
- `INV-SAF-03`：每个最终结论必须能映射到本次请求已验证的 Evidence；矛盾证据导致整条结论升级。
- `INV-SAF-04`：最终回答固定附加“基于文档检索，仅供专业人员参考”。
- `INV-SAF-05`（基线新增）：安全检查完成前不向客户端流式输出最终医学答案，防止已输出内容无法撤回。

### 2.2 数据、版本与引用

- `INV-DATA-01`：只接收公开、脱敏或合成数据；疑似 PHI/PII 默认拒绝入库并记录审核事件。
- `INV-DATA-02`：同一 `family_id` 任一时刻最多一个 `active` 版本，由数据库唯一约束保证。
- `INV-DATA-03`：默认只能引用当前生效的 `active` 版本；显式历史查询必须有权限且显著标注“历史版本，已失效”。
- `INV-DATA-04`：`source_hash` 改变即创建新版本，禁止原地覆盖；原始文件保持不可变。
- `INV-DATA-05`：无法可靠保留页码和章节的解析结果为 `low_trust`，不能转为 `active`。
- `INV-DATA-06`：引用至少包含 `doc_id / version / effective_date / page / section / chunk_id`，并可回看原文片段。
- `INV-DATA-07`：向量索引和 Reranker 结果都不是事实；进入模型上下文前必须回查事实平面。

### 2.3 身份、权限与 MCP

- `INV-AUTH-01`：所有业务和管理请求必须有可验证身份（OIDC 兼容 token，服务端校验 issuer、audience、expiry、signature）；权限默认拒绝。用户由 token `sub` 识别；部门与 scope 由服务端目录/数据库映射，IdP group claim 只能经服务端 allowlist 映射，不能直接成为数据库 scope。
- `INV-AUTH-02`：文档 ACL 必须在数据库层执行。推荐 PostgreSQL RLS 或只授予应用访问受控安全视图，禁止“全量查询后在应用层过滤”。ACL、状态和生效时间过滤必须进入数据库查询本身；RLS 运行条件见 3.7。
- `INV-AUTH-03`：Skill Registry 在执行前验证 `required_scopes`；节点不得绕过 Registry 直接调用 Skill。
- `INV-AUTH-04`：MCP 只暴露只读工具，必须从受信 token 解析身份，不能接受调用方直接声明 `dept/scopes`。生产传输为 Streamable HTTP + OIDC/OAuth bearer token；stdio 仅限本地开发与自动化测试，见 5.7。
- `INV-AUTH-05`：管理、审核、Loop 和线上服务使用分离的数据库角色；Loop 只能写 `candidate`，无权写 `released`。

### 2.4 Harness、策略与副作用

- `INV-HAR-01`：节点输入输出使用明确 Pydantic 模型；禁止用 `dict[str, Any]` 作为节点契约。
- `INV-HAR-02`：节点只通过可序列化 Agent State 交换数据；业务逻辑不得依赖可变全局状态。
- `INV-HAR-03`：Answer 节点只接收已验证 Evidence；任何直接向 LLM 请求无证据最终答案的路径都应在结构上不可达。
- `INV-HAR-04`：所有外部调用设置连接、读取和总超时；LLM 设置 `max_tokens`、并发上限与取消传播。
- `INV-HAR-05`：策略、规则、术语和检索参数全部版本化；每条 Trace 固定记录实际使用的版本集合。仓库可保留 seed/fallback Prompt 和测试 fixture，但生产“最新版”只能来自已发布策略记录，仓库明文不能成为唯一生产来源。
- `INV-HAR-06`：生产只读取 `released` 策略；候选只能经过回放、门禁、人工签字、灰度后发布。
- `INV-HAR-07`：检索文档始终作为带边界的数据传入模型，不参与系统指令优先级。
- `INV-HAR-08`：每条 Trace 有整体 Token/成本预算，不只是单次调用的 `max_tokens`；超限时先裁剪低价值 Evidence，仍不满足最小证据要求则升级，禁止扩大预算继续回答。

### 2.5 审计、隐私与评测

- `INV-OBS-01`：每次请求产生端到端 `trace_id`，记录节点决策、候选、Evidence、Verifier、Safety、调用、耗时、Token 和成本。
- `INV-OBS-02`：审计记录追加写、不可由普通业务角色修改；身份记录使用内部 surrogate ID 或带密钥的 HMAC-SHA-256 假名（支持密钥轮换），禁止无盐哈希。
- `INV-OBS-03`：Telemetry 默认脱敏；可重放的受限 Trace Payload 与普通指标/日志分开存储、加密和授权。
- `INV-EVAL-01`：冻结评测集与 Loop 候选生成上下文隔离，禁止数据泄漏。
- `INV-EVAL-02`：Prompt、规则、Skill 或检索参数变更必须附带对应离线评测结果。

## 3. 对原设计的必要工程校正

### 3.1 词法检索：P0 要求精确词法召回达标，不强制 BM25 公式

PostgreSQL 原生 `tsvector + ts_rank/ts_rank_cd` 是全文检索，不是 BM25。原设计中的“BM25”按审核决策解释为“精确词法召回能力”，而非特定排序公式。是否采用 BM25 不改变上层检索、RRF、Reranker 或业务契约，但会改变词法适配器、数据库索引、中文分词、镜像、测试、许可证与 `retrieval_version`。

1. 组件名固定为 `lexical_retriever`；M1 入口按 [ADR-0002](adr/ADR-0002-lexical-retrieval-selection.md) 比较三个生产候选：应用层预分词 + PostgreSQL `simple` FTS、PostgreSQL FTS + 数据库中文 tokenizer、`pg_search` BM25 + 固定中文 tokenizer。
2. 进程内 BM25 只作离线参考基线，不进入生产候选，避免形成数据库权限过滤之外的第二份生产索引。
3. 代码、文档和对外描述必须写实际实现，不得把 FTS 写成 BM25；RRF 和 Reranker 不能补回未进入候选集的条款。
4. 选择阈值、探针集、RLS 测试与许可证门禁在实验前固定；三个生产候选均未通过硬门禁时，DEC-001 保持阻塞，M1 不得绕过。

### 3.2 重试标识不等于幂等键

`trace_id + node + attempt` 只能唯一标识一次尝试。稳定幂等键定义为：

```text
operation_key = SHA-256(
  operation_scope + "\x1f" +
  run_id          + "\x1f" +
  node_name       + "\x1f" +
  canonical_json(input_and_versions)
)
attempt = 1..N
```

- `canonical_json`：UTF-8、对象键排序、稳定的数字/空值表示；禁止普通字符串拼接。
- `input_and_versions` 必须包含节点输入以及 `policy_version`、`retrieval_version`、`skill_version_set` 和模型配置版本。
- 生产执行 `run_id = trace_id`；回放使用独立的 `replay_run_id`，不得复用原生产运行的 operation key。
- 相同 `operation_key` 的成功结果可安全复用；每次 attempt 单独记录，指数退避最多 2 次重试。
- 有副作用操作还需数据库唯一约束或事务性 outbox，不能只依赖内存缓存。

HTTP 层幂等（基线新增，由设计中的幂等控制推导）：`POST /v1/tasks` 和反馈接口支持客户端 `Idempotency-Key`。

- 作用域：`authenticated_principal + route + key`，并保存 canonical request hash。
- 同 key、同 payload：返回原结果，包括仍在处理中的并发重复请求（返回原 `task_id` 或反馈回执，不返回 `409`）；同 key、不同 payload：返回 `422`。
- 任务记录与幂等记录必须在同一事务中创建，避免并发下产生两个 task。
- TTL 默认不少于 24 小时，且不短于对应异步任务生命周期；具体值可配置并写入 API 契约。

### 3.3 内容完整性：三级哈希

- 原文件：入库时对不可变原始文件计算 `source_hash`（SHA-256），记录对象地址、大小、MIME 与解析器版本。`source_objects.source_hash` 全局唯一，用于物理文件去重。
- 完整 Chunk：解析时计算 `chunk_content_hash`，存于 `chunks`。
- 实际送入模型的裁剪片段：记录 `evidence_text_hash` 与源 offsets。
- Verifier 重新计算实际正文哈希并比较；`evidence_log` 保存 expected/observed hash，不一致即判完整性失败。
- 查询时不重算整份原文件；后台任务定期从不可变源文件重新解析或校验 extraction manifest，失败立即阻止相关版本继续作为证据并告警。
- 多个 document/family 可显式引用同一个 source object，但必须由管理员确认并写审计。ACL 绑定 document/version，不绑定可直接访问的 source object；所有原文读取必须从授权 document 关系进入。

### 3.4 生效时间也是版本过滤条件

默认查询的可用文档应同时满足（字段落点已固定）：

```text
documents.status = active
documents.effective_from <= request_time          -- active 文档强制非空
documents.effective_to IS NULL                     -- 表示长期有效
  OR documents.effective_to > request_time
ACL allows read                                    -- 在数据库查询/RLS 内完成
source_objects.integrity_status = verified         -- 经 documents.source_object_id JOIN
documents.parse_quality = trusted                  -- 由 documents.active_ingestion_job_id 对应的解析结果写入
```

- `effective_from` 为空的文档只能处于 `draft`，不能作为证据；`active` 文档的 `effective_from` 非空由数据库约束保证。
- 历史查询必须显式携带 `as_of` 或版本号，不能通过普通问答路径偶然命中归档版本。

### 3.5 Trace 可重放不代表保存所有明文

普通日志只保存脱敏元数据。确需重放的输入、Evidence 快照和模型结果进入受限 Trace Store，设置访问审计、加密、保留期和删除策略。上线前必须完成保留期决策。

### 3.6 中文分词是词法召回的前提

说明书、SOP 和方案以中文为主，并有中英混排。PostgreSQL 默认 parser 不切分中文，BM25 类组件同样需要配置中文 tokenizer。M1 必须完成 tokenizer 选择、词典版本记录和专项评测；DEC-001 的判据包含中文药名、剂量单位、否定词、时间窗、方案编号和中英混排，而不只是排序公式。

若采用应用层预分词，入库与查询必须复用同一 tokenizer、医学词典和规范化规则版本；词元以空格连接后交给 PostgreSQL `simple` 配置，并保留 `tsvector` 位置信息，不得退化为无位置 token 集。上述版本必须进入索引元数据、`retrieval_version` 和缓存键；版本不匹配时拒绝查询，升级任一版本必须产生新的 `retrieval_version` 并重建索引。

`retrieval_version` 是复合版本：对 `{retriever_version, tokenizer_version, dictionary_version, normalization_version, embedding_version, rrf_params, rerank_params, candidate_limits}` 做 `canonical_json` 后取 SHA-256。契约中的 `retriever_version/tokenizer_version/dictionary_version` 是其组成部分，只用于诊断与实验报告，不得单独作为缓存键或回放键。

### 3.7 过滤必须进入数据库查询，并处理近似索引召回不足

- ACL、状态和生效时间过滤必须进入数据库查询和 RLS，不能先取跨权限候选再在应用层过滤。
- pgvector 近似索引在过滤后候选不足时，采用自适应 over-fetch 或 iterative scan，并记录实际候选数。
- 数据库内检索扩展的自定义扫描必须在普通应用角色、`FORCE ROW LEVEL SECURITY` 和连接池身份切换条件下证明零越权；同时验证排序与 `LIMIT` 下推后不会静默少取候选。若同一查询及过滤条件的精确计数证明合格候选不少于 `K`，必须返回 `K` 条；不足时返回实际数量并显式设置 `candidate_exhausted=true`，再按既定 over-fetch/降级规则处理。
- “合格候选”指满足该实现在实验清单中逐候选固定的词法匹配谓词（词元 AND、OR 或短语）且通过数据库权限、状态、生效时间过滤的 chunk；精确计数与检索必须使用同一谓词和过滤条件。分数相同的候选按 `chunk_id` 升序打破并列；“可复现”指候选集合与排名逐项一致。
- Recall 必须按 MA / PV / CO 部门分别报告。
- RLS 运行条件：每个请求开启事务；用 `SET LOCAL` 或事务级 `set_config` 注入服务端解析的身份；连接归还池前清除身份上下文；应用角色为 `NOSUPERUSER NOBYPASSRLS` 且不是表 owner；业务表启用 `FORCE ROW LEVEL SECURITY`；管理角色与业务角色分离；集成测试直接验证连接池复用和跨部门隔离。

### 3.8 Embedding 维度不提前锁定

- DEC-002 完成前不创建固定 `vector(1024)` 的 migration。
- ADR 确定模型和维度后再生成确定性 migration，并记录模型、维度、归一化方法和 embedding 版本。
- 未来切换维度通过新列/新索引和后台重建完成，不原地改变已有向量语义。

## 4. P0 目标架构与模块边界

建议采用模块化单体加独立 worker/MCP 进程。当前数据规模没有必要提前拆微服务；模块边界清楚后可独立扩容。

```text
API / Admin API / Read-only MCP
        |
Application Services: Ask, Ingestion, Task, Feedback, Replay, Policy
        |
Harness: Intent -> Retrieve -> Verify -> Safety -> Answer | Escalate
        |
Domain: Documents, Evidence, Skills, Policies, Traces, Evaluations
        |
Adapters: PostgreSQL/pgvector, lexical search, Redis, LLM, Reranker,
          object storage, Langfuse, OpenTelemetry
```

依赖方向只允许从外向内；领域模型不能 import FastAPI、数据库客户端或具体模型 SDK。

### 4.1 建议仓库结构

```text
src/medops/
  api/             # REST 路由、鉴权依赖、错误映射
  application/     # 用例编排
  domain/          # 领域模型、规则、接口
  harness/         # LangGraph 状态、节点、路由
  retrieval/       # query rewrite、lexical/vector、RRF、rerank
  verification/    # 引用和医学要素核验
  safety/          # 风险分类、注入检测、拒答/升级
  skills/          # Registry 与五类 Skill
  ingestion/       # 解析、切分、质量与 PII 检查
  loop/            # observe/reflect/adapt/replay/release
  infrastructure/  # DB、Redis、模型、对象存储、telemetry adapter
  mcp_server/      # 只读 MCP 工具
tests/
  unit/ integration/ contract/ e2e/ security/ evaluation/ performance/
migrations/
evals/
deploy/
docs/
```

结构是约束方向，不要求为每一项预建空目录。

### 4.2 核心数据实体

除原设计中的 `documents/chunks/document_acl/doc_audit/evidence_log` 外，P0 还需要：

- `source_objects`：不可变原文件地址、全局唯一 `source_hash`、MIME、大小、`integrity_status`。`documents` 增加 `source_object_id`、`active_ingestion_job_id`、`parse_quality`；`chunks` 增加 `chunk_content_hash`；`evidence_log` 增加 expected/observed hash 与 offsets。
- `ingestion_jobs`：解析状态、解析器版本、质量分、失败原因和重试信息。
- `tasks/task_attempts`：异步任务状态、进度、稳定幂等键和尝试记录。
- `traces/trace_spans`：执行概要；受限 payload 单独存储。
- `escalations`：升级原因、上下文引用、状态、处理人和处置结果。
- `skills/skill_versions`：Schema、权限、风险、超时和并行属性。
- `policies/policy_releases`：候选、发布、签字、灰度和回滚记录。
- `feedback/bad_cases`：反馈信号、归因和与 Trace 的关联。
- `evaluation_datasets/evaluation_runs/evaluation_results`：冻结集版本与门禁结果。
- `outbox_events`：可靠发布任务、审计和缓存失效事件。

关键数据库约束必须使用 migration 和集成测试证明，包括 active 唯一性、外键、状态机转换、只读角色和 ACL 隔离。

## 5. 全部工作流

### 5.1 文档入库与知识治理

```text
upload -> file validation -> PII scan -> immutable store -> SHA-256
-> parse -> section/page-aware chunk -> quality check -> draft
-> administrator review -> active -> index/cache invalidation
```

- 支持数字 PDF 和 DOCX；扫描件无法可靠提取时进入人工处理，不自动 active。
- 校验文件签名/MIME、大小上限、恶意文件和重复哈希。
- Chunk 保留页码、章节、序号、字符区间；可选保存 bbox 以支持精确高亮。
- 发布新版本在同一事务中归档旧版、激活新版、写审计和 outbox。
- 原始文件可点击回看，但下载同样经过 ACL。

### 5.2 检索与证据构建

- Query Rewriter 从用户查询、可信会话实体、术语表生成 1-3 条有界查询。
- 用户文本不得直接生成 SQL、过滤表达式或权限条件。
- 词法和向量召回并行，各自记录排名与分数。`LexicalRetriever` 对每个候选至少返回 `chunk_id/raw_score/rank`，并在结果级返回 `requested_k/returned_count/candidate_exhausted/retriever_version/tokenizer_version/dictionary_version`；RRF 只使用排名，原始分数用于 Trace 与实验诊断。
- 使用确定性的 RRF 融合；默认 `k=60` 只是初始配置，不是永久常量。
- Reranker 输入最多 20 个候选，输出最多 5-8 个。
- 事实回查后再构造 Evidence；失效、越权、低可信或完整性失败的候选直接丢弃并记录原因。
- 缓存键至少包含规范化查询、身份权限指纹、历史查询条件、检索/策略版本；文档发布通过 outbox 精确失效。

### 5.3 Harness 与回答

- LangGraph 只负责可检查的状态迁移，领域规则放在可单测服务中。
- 每个节点定义输入、输出、错误类型、超时、重试和降级条件。
- Intent 不明确最多反问一次；仍不明确时可进入通用检索，但不能降低安全级别。
- 单一路径失败只能在证据阈值仍满足时降级；否则升级，不能“尽力猜测”。
- Answer 使用结构化输出，先生成 claim-citation 映射，再渲染给用户。
- 最终答案生成后再次做引用存在性和关键要素支持检查。

### 5.4 Verifier

1. 确定性结构核验：引用必须属于当前 Trace 的已授权 Evidence。
2. 关键要素抽取：剂量、单位、频次、适应证、人群、时间、方案编号。
3. 支持度判断：`supported / not_supported / contradicted`，保留模型版本、置信和理由。
4. `not_supported` 项从答案删除并明确证据不足；任何关键矛盾进入升级。
5. 针对数字、单位、否定词和时间窗增加规则测试，不能只依赖 NLI/LLM。

### 5.5 Safety 与升级

- 输入前置检查、检索片段检查、输出后置检查三层叠加。
- 用户输入与检索内容分别标记来源，防止文档提示词注入。
- 高风险意图、越权、版本冲突、证据不足和系统故障使用稳定 reason code。
- Escalation 保存问题、Evidence 引用、Verifier/Safety 结果、策略版本和最小必要上下文。
- 开发环境可用内部工单记录；接入真实工单平台属于 P1。

### 5.6 Skills

每个 Skill 都要有输入/输出 Schema、版本、权限、风险、超时、幂等性、并行安全、Evidence 要求和安全测试。

| Skill | 风险 | P0 输出要求 |
| --- | --- | --- |
| 说明书查询 | 低 | 原文片段、版本化引用、证据不足状态 |
| 不良事件线索提取 | 中 | 结构化 AE 要素及每个要素的依据；不判定医学因果 |
| 超说明书用药检查 | 高 | 是否落在说明书范围、依据条款、固定声明；不提供建议 |
| 方案偏离核验 | 中 | 是否偏离、类型、适用版本和条款引用 |
| 医学引用验证 | 低 | 每条 claim 的支持状态和来源 |

### 5.7 API、异步任务与 MCP

- 保留设计中的 `/v1/ask`、`/v1/tasks`、任务查询/重试、`/v1/feedback`、管理接口和 replay 接口。
- OpenAPI 中固定请求/响应、错误码、拒答/升级模型和引用模型。
- 异步任务状态至少支持 `queued/running/completed/failed`；内部可增加 `retrying/cancelled`，但不能破坏公开契约。
- worker 使用数据库租约或原子状态转换避免重复消费；进度与结果持久化到 PostgreSQL。
- MCP 工具限定为 `search_documents/get_chunk/verify_citation/list_active_versions`，逐项做授权、参数上限和审计。
- MCP 生产传输为 Streamable HTTP：OIDC/OAuth 获取 bearer token，服务端验证 issuer、audience、expiry、signature；stdio 仅用于本地开发和自动化测试，不连接生产文档库，或只能使用固定的低权限服务身份；`dept/scopes` 不接受请求参数直接声明。
- 身份提供方（DEC-010）：架构保持 OIDC 兼容，不提前锁定厂商。token `sub` 识别用户，部门和权限由服务端目录/数据库映射；IdP group claim 必须经服务端 allowlist 映射。开发环境使用独立测试签发密钥和合成身份。
- 并发重复的 `Idempotency-Key` 请求返回原 `task_id`/反馈回执，不返回 `409`；该语义写入 OpenAPI。

### 5.8 受控自进化 Loop

```text
Execute -> Observe -> Reflect -> Adapt -> Replay -> Approve -> Canary -> Release/Rollback
```

- Observe 接收纠错、点踩、连续追问、Verifier 失败和升级结果。
- Reflect 归因为 `retrieval/intent/generation/knowledge_gap/safety`，允许人工修正。
- Adapt 只能创建结构化 diff 候选；knowledge gap 只能建补充文档工单，不能生成事实。
- Replay 固定数据集、模型版本、随机参数与运行环境，报告目标、非目标、安全、延迟和成本变化。
- 候选发布要求不少于 200 条历史 Trace，并包含安全集全量。
- 门禁：目标任务成功率至少 `+5pp`；任何非目标切片下降超过 `1pp` 拒绝；任何安全指标下降拒绝。
- 发布必须有人签字；初始灰度不超过 10%；回滚为原子切换 released 指针，并定期演练。
- 可靠性报告（当前基线必报项，不作为额外硬门禁）：至少 200 条唯一 Trace；含随机性的流程独立运行 3 次；同一批 Trace 做 paired comparison；报告 bootstrap 95% CI；`+5pp / 非目标下降不超过 1pp` 仍按点估计作为硬门禁。
- 切片样本少于 30 条时标记“样本不足”，只作诊断；安全指标采用三次运行的最差值，任何下降仍拒绝发布。本条只适用于 M4 Loop 回放报告；M1 DEC-001 探针实验是确定性检索实验，其切片门禁由 ADR-0002 规定（每类不少于 8 条），不适用本条。

### 5.9 评测

指标口径必须在第一次评测前冻结：

- `Recall@5`：严格宏平均 Recall。单条 query 的 `recall@5 = |required_gold_evidence ∩ retrieved_top5| / |required_gold_evidence|`，`retrieved_top5` 取事实回查后的 top 5 而非向量候选；`Recall@5` 为全部 query 的平均值。冗余或等价 Evidence 不重复计入 required gold。
- `Hit@5`：任一 required gold 出现在 top 5 的 query 比例，单独报告，不得称为 Recall@5。
- `Lexical Recall@20`：事实与权限过滤后、RRF/Reranker 前的词法 top 20 对 `required_gold_evidence` 的严格宏平均 Recall；专用于 DEC-001 探针实验，不替代端到端 Recall@5。探针集的 gold 锚定与 chunk 级命中规则（chunk 的 `gold.page` 来源片段覆盖 `key_text` 页内位置）以 [探针集规范](../evals/probe/precise_clause/SPEC.md) 为准。
- 无答案样本：`required_gold_evidence` 为空的样本不进入 Recall@5 和 Hit@5 的分母，单独以 abstention/no-answer accuracy（应声明证据不足或拒答的样本中被正确处理的比例）评测；若正样本出现空 gold，视为标注异常，评测任务直接失败而不是跳过。
- 引用准确率：最终答案中被原文支持的引用数 / 最终答案全部引用数。
- 失效版本引用率：非显式历史查询中 archived/未生效引用数 / 全部引用数，必须为 0。
- 正确拒答率：应拒答样本中正确拒答数 / 应拒答样本数。
- 越权拦截率：越权请求在返回任何受限元数据或正文前被拦截的比例。
- 高风险升级召回率：应升级的高风险样本中成功创建升级记录的比例。
- 任务成功率：按冻结任务 rubric 判定，不能用主观点赞替代。

至少维护以下数据切片：文档类型、部门、语言、精确数字/剂量、版本冲突、无答案、注入、高风险和长上下文。样本只能来自允许的数据，记录来源许可。主评测集复核政策：全部样本由一名人工标注并经 LLM 独立复核；全部争议样本以及剂量、否定、时间窗、版本冲突、高风险样本必须有第二人工复核；其余样本随机抽取不少于 20% 做第二人工复核；LLM 不计作第二人工，争议最终由人工裁决并记录。探针集并入主集后按同一政策补第二人工复核。

### 5.10 可观测性与运行保障

- Langfuse 记录模型和 Agent Trace；OpenTelemetry 记录 API、DB、Redis、检索、模型和 worker spans。
- 统一传播 `trace_id/task_id/policy_version/retrieval_version`，不把高基数字段作为 metrics label。
- 核心指标：请求量、成功/拒答/升级率、各节点错误与延迟、候选过滤原因、缓存命中、队列深度、Token、成本。
- 建立 P95、错误率、队列积压、ACL 拒绝异常、失效版本候选、完整性失败和预算告警。
- Trace 写入失败不能导致无审计医学回答；应转为安全失败或可靠缓冲，具体策略必须有故障测试。

### 5.11 性能、成本与推理

- 先建立质量基线，再做成本优化；任何优化都必须证明质量不下降。
- 词法与向量并行；只把通过验证的相关句放入上下文。
- 模型访问统一经 Model Gateway/adapter，固定超时、重试、并发、预算、数据出境策略和版本元数据。
- Intent 可用小模型或规则；Verifier 采用“确定性校验 + 可替换 NLI/LLM”；Answer 按风险和复杂度路由。
- 本地 Reranker 通过有界队列和批处理提高吞吐；资源不足时显式降级或升级。
- 普通问答 P95 <= 8s，复杂 Skill P95 <= 15s；在固定质量集上 Token 降低至少 25%。

### 5.12 生产级后端与部署

P0 的“生产级”指可安全部署和恢复，不等同于必须上 Kubernetes。

P0 保留：

- 多阶段镜像、非 root 用户、固定依赖、健康/就绪检查、优雅停机。
- 配置环境注入，密钥来自 secret manager；仓库和 Trace 中不得出现密钥。
- migration 前向可执行且有回滚/修复方案。
- PostgreSQL/Redis/Object Store 明确持久化与容量阈值；worker 重启后不丢任务（设计可用性要求）。
- TLS、CORS、请求大小/频率限制。
- dev/test/prod 环境隔离；生产默认关闭调试信息和交互 API 文档。
- 主链路故障测试：模型超时、worker 重启、队列重复消费。

降为 P1 生产就绪增强（见 7.1）：SBOM、依赖和镜像扫描、完整备份恢复演练，以及数据库短暂不可用、Redis 不可用、Reranker 故障等故障演练。

## 6. 里程碑、依赖和完成定义

| 阶段 | 主要交付 | 完成门禁 |
| --- | --- | --- |
| M0 工程骨架 | 契约、配置、CI、测试底座、威胁模型 | 本地一条命令启动；质量门禁可运行 |
| M1 知识与检索 | 事实平面、入库、ACL、混合检索 | Recall@5 >= 85%；失效引用 0；ACL 集成测试通过 |
| M2 Harness 与 Skills | 状态机、Verifier、Safety、Registry、先完成 2 个 Skill | 引用准确率 >= 95%；安全门禁达标 |
| M3 服务与观测 | API、worker、Trace、MCP、部署基线 | P95 达标；Trace 可重放；MCP 只读证明 |
| M4 Loop | 归因、候选、回放、审批、灰度、回滚 | 完成一轮符合门禁的发布与回滚演练 |
| M5 全量与优化 | 5 个 Skill、数据规模、成本优化 | 所有 P0 指标达标；Token 降低 >= 25% |

任何里程碑的“完成”同时要求：

1. 验收用例通过且报告可复现。
2. 安全不变量有自动化测试。
3. 失败路径、日志脱敏和权限边界已验证。
4. 文档、migration、OpenAPI 和配置示例同步更新。
5. 无未解释的跳过测试、宽泛异常吞噬或临时权限绕过。

## 7. P1/P2 选做增强

这些内容不得阻塞 P0，也不得在未验证收益前侵入核心接口。

### 7.1 P1：P0 稳定后优先考虑

- **高可用后端**：托管 PostgreSQL/Redis、读写隔离评估、多副本 worker、自动备份恢复演练、零停机迁移。
- **独立推理部署**：GPU Reranker/NLI 服务、动态 batching、量化、模型预热、并发和显存水位治理。
- **更强检索**：结构/标题感知切分、parent-child retrieval、查询路由、hard-negative 训练；必须用消融实验决定是否保留。
- **扫描文档 OCR**：版面识别、OCR 置信、人工复核队列；仍只将文字作为证据，不自动解释图表。
- **管理界面**：文档审核、ACL、升级处置、策略 diff、评测报告、灰度和回滚可视化。
- **外部工单集成**：只发送最小必要、已脱敏上下文，并保留投递审计。
- **灾备与合规加固**：明确 RPO/RTO、保留期、审计导出、密钥轮换和第三方数据处理评审。
- **生产就绪增强（自 P0 降级）**：SBOM、依赖和镜像扫描、完整备份恢复演练、数据库短暂不可用/Redis 不可用/Reranker 故障等故障演练。
- **词法引擎后续替换**：DEC-001 在 M1 定型后，仅在新的冻结评测证明收益且重新通过权限、性能、许可证与回归门禁时更换实现。

### 7.2 P2：研究型增强

- **多模态文档 RAG**：表格、流程图和图像证据，需要独立的证据坐标、引用渲染、模态级 Verifier 和安全评测；不得直接复用纯文本通过标准。
- **医学知识图谱辅助检索**：只用于候选扩展或一致性检查，不能成为无来源事实平面。
- **学习型路由与个性化**：只能使用非敏感、受控特征，不能改变部门 ACL 或安全阈值。
- **跨语言检索**：中英文术语对齐、跨语言引用一致性和分别报告的质量切片。
- **主动学习标注**：只推荐待标注样本；人工确认后才能进入训练或术语表。

### 7.3 进入选做项的统一门槛

- P0 对应主链路已达标且有稳定回归集。
- 有明确的问题、基线、预期收益和退出条件。
- 新增组件的故障模式、成本、数据流和权限边界已评审。
- 消融实验表明收益，且安全、非目标质量和可维护性没有不可接受下降。

## 8. 开发工程 Checklist

### M0：工程与契约

- [ ] 建立 `src/tests/migrations/evals/deploy/docs` 的最小必要结构。
- [ ] 固定 Python 版本与依赖锁文件，提供 `.env.example`，不提交密钥。
- [ ] 配置 lint、format、type check、unit test 和 migration check。
- [ ] 建立 CI：单元、集成、契约、安全、评测 smoke；镜像扫描为可选 job，正式要求见 P1。
- [ ] 定义统一错误模型、reason code、`trace_id` 和结构化日志格式。
- [ ] 实现 `canonical_json` 与 3.2 定义的 `operation_key`，并有确定性与跨平台测试。
- [ ] 定义 Pydantic 领域契约：UserContext、Document、Chunk、Evidence、Intent、VerifyResult、SafetyResult、Answer、Escalation、AgentState。
- [ ] 输出 OpenAPI 初版和 MCP 工具 Schema。
- [ ] 完成数据流图和威胁模型：身份伪造、越权、注入、数据泄漏、策略篡改、审计绕过、DoS。
- [ ] 建立测试数据工厂，确保全部为公开、脱敏或合成数据。
- [ ] Docker Compose 一条命令启动 API、worker、PostgreSQL/pgvector、Redis、对象存储和可选观测组件。

### M1：知识治理与检索

- [x] 在实现候选前冻结 DEC-001 精确条款探针集：不少于 60 条、目标 72 条，覆盖六类专项与 MA/PV/CO（每部门不少于 15 条）；语料只用 ADR-0003 准入为 `eligible` 的公开文档，gold 锚定到 `source_hash/version_label/page/section/key_text`，人工标注加 LLM 独立复核并如实记录，按 [evals/probe/precise_clause/SPEC.md](../evals/probe/precise_clause/SPEC.md) 通过校验后记录 `dataset_version` 与 `dataset_hash`；修正标注必须升版并重跑全部候选。
- [ ] 冻结 DEC-001 实验清单：三个生产候选的具体实现/配置、PostgreSQL/扩展/tokenizer/词典版本、镜像 digest、硬件与测量参数；进程内 BM25 仅作离线参考。
- [ ] 固定 `LexicalRetriever` 契约，包含候选 `chunk_id/raw_score/rank` 与结果级 `requested_k/returned_count/candidate_exhausted/retriever_version/tokenizer_version/dictionary_version`。
- [ ] 用最小实验 schema 在普通应用角色 + `FORCE ROW LEVEL SECURITY` 下完成词法候选对比；同时断言零跨部门泄漏与零静默候选不足，覆盖 `LIMIT`、按分数排序和连接池身份切换。
- [ ] 按 ADR-0002 的预登记阈值完成三候选实验与许可证审查，将选择、证据和复现命令回填 ADR；未产生合格方案前阻塞正式 M1 实现。
- [ ] migration 建立文档、版本、chunk、ACL、审计、source object 和 ingestion job 表。
- [ ] 数据库约束保证同一 family 只有一个 active 版本。
- [ ] 正式数据库 RLS/安全视图和角色权限测试证明跨部门不可见且候选不足可检测，覆盖 3.7 全部运行条件和连接池复用。
- [ ] 完成 PDF/DOCX 校验、PII 扫描、`source_hash` 全局唯一去重、不可变保存，以及多 document 引用同一 source object 的管理员确认与审计。
- [ ] 解析保留 page/section/seq/offset 并写入 `chunk_content_hash`；`parse_quality` 非 trusted 的文档不能 active；active 文档 `effective_from` 非空由约束保证。
- [ ] 发布/归档在事务中完成，并通过 outbox 触发索引与缓存失效。
- [ ] 建立医学术语表及版本；记录通用名、商品名、缩写的来源。
- [ ] 实现 1-3 条有界 Query Rewrite，并验证会话实体不会跨会话污染。
- [ ] 实现 DEC-001 选定的 `lexical_retriever`；若为应用层预分词，保证入库/查询版本一致、保留词元位置、版本不匹配拒绝查询且升级触发重建索引。
- [ ] 固化选定方案的中文 tokenizer、医学词典和规范化规则版本，并把它们纳入索引元数据、`retrieval_version` 与缓存键。
- [ ] DEC-002 完成后实现 pgvector 召回；migration 记录模型、维度、归一化方法和 embedding 版本；过滤后候选不足时 over-fetch 或 iterative scan。
- [ ] 实现 RRF、Reranker、候选上限和并行超时。
- [ ] 实现事实回查：状态、生效时间、ACL、完整性、解析质量。
- [ ] 缓存键包含权限与版本指纹，文档状态变化可可靠失效。
- [ ] 建立 >=300 条带 doc/version/page gold 的检索与引用评测集。
- [ ] 严格宏平均 Recall@5 >=85%（另报 Hit@5），失效版本引用率为 0%，并按 MA/PV/CO 部门和其他切片输出报告。

### M2：Harness、Verifier、Safety 与 Skills

- [ ] LangGraph 中不存在绕过 Retrieve/Verify/Safety 到 Answer 的边。
- [ ] 每个节点 Schema 校验、超时、错误类型、重试和降级已实现。
- [ ] 使用 3.2 定义的 operation key 实现节点幂等，attempt 单独记录，回放使用独立 `replay_run_id`。
- [ ] Answer 只接受 verified Evidence，输出 claim-citation 结构。
- [ ] 引用结构核验可拦截伪造 doc/version/page/chunk，并比对 `evidence_text_hash`/`chunk_content_hash`，expected/observed 写入 evidence_log。
- [ ] 整条 Trace 的 Token/成本预算生效：超限先裁剪低价值 Evidence，不满足最小证据要求则升级。
- [ ] 关键要素抽取覆盖剂量、单位、频次、适应证、人群、时间和编号。
- [ ] 支持度核验覆盖 supported/not_supported/contradicted 和确定性数字规则。
- [ ] 三层 Safety 覆盖用户输入、检索内容和最终输出。
- [ ] 拒答/升级 reason code 稳定，升级记录包含最小必要上下文。
- [ ] Skill Registry 强制 Schema、scope、risk、timeout、parallel_safe 和版本。
- [ ] 先完成说明书查询与医学引用验证两个低风险 Skill。
- [ ] 再完成 AE 线索提取、方案偏离和超说明书用药检查。
- [ ] AE Skill 明确不自动判断因果；高风险 Skill 不提供用药建议。
- [ ] 建立 >=150 条安全集，覆盖越权、注入、无依据和高风险。
- [ ] 引用准确率 >=95%；正确拒答率 >=95%；越权拦截率 >=98%；高风险升级召回率 >=95%。

### M3：API、异步、MCP、可观测性与部署

- [ ] 实现 `/v1/ask`，覆盖成功、证据不足、拒答、升级和服务失败契约。
- [ ] 实现 task 创建、查询、失败重试与 Idempotency-Key（作用域、request hash、`422`、并发返回原 task、任务与幂等记录同事务、TTL 写入 OpenAPI）。
- [ ] 实现反馈、文档管理、策略候选、审批和 Trace replay 接口。
- [ ] worker 状态转换原子、结果持久化、崩溃可恢复、重复消费安全。
- [ ] 身份来自 OIDC 兼容 token（校验 issuer/audience/expiry/signature），scope 由服务端映射；业务、管理员、审核员权限分离。
- [ ] MCP 仅暴露四个只读工具，并通过数据库权限证明不能写入或越权；生产为 Streamable HTTP + bearer token，stdio 仅限开发测试。
- [ ] 每个请求有完整 Trace，Telemetry 脱敏（身份假名为 surrogate ID 或 HMAC-SHA-256），受限 payload 单独授权。
- [ ] Trace replay 可指定策略/检索版本并生成差异报告。
- [ ] OTel spans 覆盖 API、DB、Redis、模型、Reranker 和 worker。
- [ ] 建立延迟、错误、拒答/升级、队列、缓存、Token、成本和安全告警仪表盘。
- [ ] 普通问答 P95 <=8s，复杂 Skill P95 <=15s；报告并发、数据集和硬件环境。
- [ ] 镜像以非 root 运行，具备健康检查、优雅停机和固定依赖。
- [ ] 完成主链路故障测试：模型超时、worker 重启、队列重复消费。

### M4：受控自进化 Loop

- [ ] 反馈、Verifier、安全和升级信号能关联到 Trace。
- [ ] bad case 五类归因有 Schema、置信和人工修正入口。
- [ ] 候选以可审查 diff 保存，不能直接修改 released。
- [ ] Loop 数据库角色无 released 写权限，并有自动化权限测试。
- [ ] knowledge_gap 只创建补文档工单，不生成医学事实。
- [ ] 建立 >=200 条 good/bad Trace 回放集并冻结版本。
- [ ] 回放报告覆盖目标、非目标、安全、延迟、Token 和成本，含 3 次独立运行、paired comparison 与 bootstrap 95% CI；样本少于 30 的切片标记“样本不足”。
- [ ] CI/审批服务强制 `+5pp / 非目标下降<=1pp / 安全不下降` 门禁（点估计），安全指标取三次运行最差值。
- [ ] 审核签字、候选发布、初始灰度<=10%、观察窗和全量流程可审计。
- [ ] 一次操作可原子回滚策略指针，并完成回滚演练。

### M5：规模、全量验收与成本

- [ ] 接入 300-500 份许可清楚的公开文档（目标来自项目描述；准入按 ADR-0003 四级状态判定），记录来源和版本。
- [ ] 五个 Skill 全部通过功能、安全、权限和故障测试。
- [ ] 质量、安全、性能指标在冻结集上全部达标。
- [ ] 通过上下文裁剪、缓存和模型路由使 Token 降低 >=25%，质量不降。
- [ ] 容量测试覆盖目标文档量、并发、队列积压和缓存冷启动。
- [ ] 完成数据保留/删除、密钥轮换、备份恢复和依赖升级手册。
- [ ] 完成运维 runbook、事故响应、人工升级和回滚手册。
- [ ] 生成最终验收报告，区分实测值与目标值，不保留占位式成绩。

### P1/P2 增强项

- [ ] P1：扫描件 OCR 与人工复核队列。
- [ ] P1：独立 Reranker/NLI 推理服务与批处理、量化、自动扩缩。
- [ ] P1：知识、策略、升级和评测管理界面。
- [ ] P1：高可用部署、灾备和合规审计加固。
- [ ] P1：外部工单系统的脱敏集成。
- [ ] P1：SBOM、依赖/镜像扫描、完整备份恢复演练与外部依赖故障演练。
- [ ] P1：词法引擎后续替换的冻结评测、权限/性能回归、许可证复审与 ADR。
- [ ] P2：多模态表格/图像证据与独立评测体系。
- [ ] P2：知识图谱辅助候选召回。
- [ ] P2：跨语言检索与引用核验。
- [ ] P2：人工确认的主动学习标注闭环。

## 9. 每轮工作的自检协议

每次编码前记录：本轮目标、影响的不变量、验收用例、明确不做什么。每次编码后必须自行复检：

1. **需求**：改动是否只覆盖本轮目标；是否无意扩展医学能力或数据范围。
2. **逻辑**：状态迁移、版本时间、权限、幂等、重试和降级是否存在旁路或竞态。
3. **安全**：失败是否默认拒绝；日志/Trace 是否泄露身份、文档或密钥；检索内容是否可能变成指令。
4. **契约**：Pydantic、OpenAPI、数据库 migration、Skill Schema 和错误码是否同步。
5. **测试**：正常、边界、失败、越权、注入、旧版本、超时和重复请求是否覆盖。
6. **可观测**：是否有 trace_id、reason code、耗时和版本信息；是否避免高基数指标。
7. **简洁性**：是否存在未使用抽象、重复实现、宽泛 `except`、隐藏副作用或没有收益的新依赖。
8. **验证**：运行相关 lint/type/test/eval；若无法运行，明确说明未验证内容和阻塞原因。
9. **Checklist**：仅按证据更新勾选项，并在交付说明中列出测试命令和结果。

推荐每轮交付格式：

```text
完成：<可验证结果>
约束：<本轮遵守/新增的不变量>
验证：<命令与结果>
未完成：<仍为 [ ] 的相关项>
风险：<残余风险；没有则写“无新增已知风险”>
```

## 10. 待决策与阻塞项

以下决策应通过小规模基准或 ADR 完成，不凭偏好直接锁定：

| ID | 决策 | 推荐处理时点 | 判定依据 |
| --- | --- | --- | --- |
| DEC-001 | 词法检索实现、中文 tokenizer 与词典选择；选择协议和阈值已由 [ADR-0002](adr/ADR-0002-lexical-retrieval-selection.md) 预登记，具体实现待实验 | M1 入口，后续实现前 | 探针集 Lexical Recall@20、端到端 Recall@5、关键切片、RLS/候选数、延迟、许可证与运维复杂度 |
| DEC-002 | Embedding（模型、维度、归一化）与 Reranker；决策前不建固定维度 migration。已决（[ADR-0007](adr/ADR-0007-embedding-and-reranker-selection.md)，2026-09-20，决策人授权实施方决定）：bge-m3 稠密 1024 维余弦 + bge-reranker-v2-m3，本地推理 | M1 | 中英文医学集效果、许可、延迟、部署资源、维度切换成本 |
| DEC-003 | Verifier 使用专用 NLI 还是小 LLM。已决（[ADR-0011](adr/ADR-0011-verifier-judge-division-of-labour.md)，2026-09-23）：确定性规则只裁否定极性矛盾与同极性整句包含，其余交 LLM 判定 `gpt-6-sol`；未采用专用 NLI | M2 | 支持/矛盾准确率、可解释性、成本 |
| DEC-004 | arq、Celery 或轻量 worker | M0/M3 | 可靠性需求、运维成本、任务复杂度；默认优先最小方案 |
| DEC-005 | 初始医学术语来源。已决（[ADR-0008](adr/ADR-0008-medical-glossary-sources.md)，2026-09-20，决策人授权实施方决定）：TFDA 開放資料 + 语料内定义缩写；DrugBank Open Data 待决策人下载 | M1 入库前 | 公开许可、覆盖和版本更新方式 |
| DEC-006 | 灰度按用户还是部门 | M4 | 爆炸半径、统计有效性；默认稳定 user hash |
| DEC-007 | 原始文档对象存储与备份 | M1 | 不可变、ACL、回看、恢复与成本 |
| DEC-008 | Trace 与审计保留期 | M3 上线前 | 项目要求、数据最小化、重放窗口 |
| DEC-009 | 模型托管/本地及数据传输边界。已决（[ADR-0010](adr/ADR-0010-llm-provider-and-data-boundary.md)，2026-09-23，决策人）：运行时 LLM 走 OpenAI API，月上限 30 美元可调；embedding/reranker 本地（ADR-0007）；订阅 CLI 仅用于离线数据工作 | M0/M2 | 数据政策、质量、成本、可用性 |
| DEC-010 | 身份提供方与 token 签发；架构保持 OIDC 兼容，不提前锁定厂商。OIDC 边界已决（[ADR-0001](adr/ADR-0001-identity-oidc-boundary.md)），具体 IdP 延后 | 边界：已决 / IdP：M3 上线前 | 部门与 scope 的服务端映射、group claim allowlist、开发环境测试签发密钥、审计要求 |
| DEC-011 | 评测语料来源白名单与四级许可准入政策；政策已决（[ADR-0003](adr/ADR-0003-corpus-source-license-policy.md)），探针集 v1 只收 `eligible` 文档，具体文档清单待审核 | 政策：已决 / 清单：探针集 v1 冻结前 | 发布主体权威、版本可追溯、原始 PDF 可定位、许可状态、第三方内容、署名要求 |

决策完成后应在 `docs/adr/` 增加简短 ADR，并在本表标记为已决。

## 11. 最终验收总门禁

- [ ] 300-500 份公开/脱敏/合成文档已治理入库。
- [ ] >=300 条检索/引用样本，严格宏平均 Recall@5 >=85%（另报 Hit@5），引用准确率 >=95%，失效版本引用率 =0。
- [ ] >=150 条安全样本，正确拒答率 >=95%，跨部门越权拦截率 >=98%，高风险升级召回率 >=95%。
- [ ] >=200 条历史 Trace 回放；策略发布满足 +5pp、非目标下降<=1pp、安全不下降、人工签字和灰度<=10%。
- [ ] 普通问答 P95 <=8s，复杂 Skill P95 <=15s。
- [ ] 同等质量下单次 Token 消耗降低 >=25%。
- [ ] 所有回答可审计、所有策略可追溯、一次操作可回滚。
- [ ] 没有诊断/处方输出、真实患者数据、跨部门泄漏、写入型 MCP 或自动生产策略修改路径。
- [ ] 所有数值均来自可复现的实测报告，不以目标值冒充结果。
