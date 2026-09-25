# API 与 MCP 契约初版（M0-08，2026-09-10）

> 机器可读形式在 `schemas/`（15 个 Schema、`mcp/tools.json` 本地描述清单与 `openapi.json`），由 `make schemas` 从 Pydantic 模型导出，`make check` 会检测漂移；可用 JSON Schema 表达的跨字段规则已通过模型的 `json_schema_extra` 导出，需要服务端状态的规则（哈希重算、授权）只在服务端执行。OpenAPI 3.1 初版（2026-09-17，`info.version` 0.1.0）由 `src/medops/api/openapi.py` 从同一批模型生成，不引入 Web 框架：`components.schemas` 与单文件 Schema 逐模型相等（测试断言），错误响应由 `core.errors.HTTP_STATUS` 推导，每个操作列出统一错误处理器可能返回的全部状态码。本文只登记端点与模型的对应关系和语义，不是第二份契约。

## REST（设计文档 3.10）

| 端点 | 请求模型 | 响应模型 | 语义要点 |
| --- | --- | --- | --- |
| `POST /v1/ask` | `AskRequest` | `AskResponse` | `outcome` 为 answered、refused、escalated 之一，且只带对应负载；答案复用领域 `Answer`（claim-citation 与固定免责声明）；拒答与升级必须带稳定 `ReasonCode` |
| `POST /v1/tasks` | `TaskCreateRequest` | `TaskResponse` | 支持 `Idempotency-Key`（作用域为身份 + 路由 + key；同 key 同 payload 返回原受理，含处理中；不同 payload 返回 422 `idempotency_payload_mismatch`）；`input` 为 JSON 对象，由 Skill Registry 按注册 Schema 校验 |
| `GET /v1/tasks/{id}` | 路径参数 | `TaskResponse` | 状态 queued、running、completed、failed；completed 必带 `result`（`TaskResult`：Skill 的 `name@version`、状态、reason codes、按该 Skill 注册的输出 Schema 校验过的 `output`、版本集；2026-09-23 M3-02 由 `AskResponse` 改为此结构，因为 Skill 输出是按 Skill 定义的结构；决策人 2026-09-24 批准），failed 必带 `ErrorResponse`，非终态两者皆无；只有创建者可见，其余 `404 not_found` |
| `POST /v1/tasks/{id}/retry` | 路径参数 | `TaskResponse` | 只允许 failed 且 `error.retryable` 为真的任务；其他状态返回 `409 task_not_retryable` |
| `POST /v1/feedback` | `FeedbackRequest` | `FeedbackReceipt` | correction 必带文本，其余信号不得带；支持 `Idempotency-Key` |
| `GET /admin/documents`、`GET /admin/documents/{doc_id}` | 查询参数 dept / status / family_id | `DocumentListResponse`、`DocumentDetail` | 管理角色；只返回元数据、读 ACL 与最近 20 条审计，不返回正文；上传不是 HTTP 操作（入库流程离线，DEC-012，2026-09-25 决策人批准） |
| `PATCH /admin/documents/{doc_id}/status` | `DocumentStatusRequest`（action activate / archive / withdraw、effective_date、reason） | `DocumentDetail` | 管理角色；draft→active、active→archived、draft→withdrawn，其余 `409 status_conflict`；复用发布链（触发器审计、outbox 事件、缓存失效）；支持 `Idempotency-Key` |
| `PATCH /admin/documents/{doc_id}/acl` | `DocumentAclRequest`（grant / revoke 部门、reason） | `DocumentAclResponse` | 管理角色；所有者部门不可撤销；每次变更写 `doc_audit` 与 `document_acl_changed` 事件（涉及部门的缓存 epoch 失效）；支持 `Idempotency-Key` |
| `GET /admin/policies/candidates`、`GET /admin/policies/{policy_id}` | — | `PolicyListResponse`、`PolicyResponse` | 审核（approver）或管理角色；候选 diff 只能是 prompt / rule / skill / retrieval_params 的结构化差异，含回放 / 门禁证据 |
| `POST /admin/policies/{policy_id}/approve` | `PolicyDecisionRequest`（approve / reject、reason） | `PolicyResponse` | 审核角色；四眼：候选作者不得裁决（403）；只有 candidate 可裁决（409）；支持 `Idempotency-Key` |
| `POST /admin/policies/{policy_id}/release`、`POST /admin/policies/{policy_id}/rollback` | `PolicyReleaseRequest`（canary_percent ≤ 10、reason）、`PolicyRollbackRequest` | `PolicyResponse` | 管理角色；发布要求 approved 且 `evidence.gate` 是回放运行器产出的**完整通过报告**（`medops.loop.gate.gate_report_valid`：结构齐全、`passed`、冻结回放集哈希、安全跑全、≥ 3 轮 ≥ 200 项；占位 `{passed: true}` 被拒，`409 gate_not_passed`，记录 82），且 `(kind, name)` 必须是运行时加载器能应用的目标（目前 `retrieval_params/hybrid`、`prompt/answer_system`，否则 `409 policy_target_unsupported`，记录 80）；released 指针按 (kind, name) 原子切换并记录前值；回滚只对当前发布有效，指针回到前一次发布；支持 `Idempotency-Key`（DEC-012） |
| `POST /admin/traces/{id}/replay` | `ReplayRequest` | `ReplayReport` | 管理角色；用原问题、原 principal 的当前身份与本部署钉定的版本集重跑，`replay_run_id` 独立于原运行（不复用任何 operation key 结果）；报告两侧的 outcome / reason codes / 引用与差异字段、版本是否一致；201（2026-09-24 M3-08 定义，决策人同日批准） |
| `GET /admin/traces/{trace_id}/payload?purpose=` | 查询参数 purpose（8–500 字） | `TracePayloadResponse` | 管理角色；返回该 Trace 的节点输入、证据快照与模型输出（请求事务内以信封加密写入：每行随机 DEK + 版本化 KEK，AES-256-GCM），只在受限数据库角色上解密；读取前先写 `payload_access_log`（假名 + 用途）；从未写入或已按保留期（90 天；升级案关闭后 30 天）清除时 404（DEC-013，2026-09-25 决策人批准） |
| 所有错误 | | `ErrorResponse` | 只含 code、message、trace_id、retryable；内部 detail 不外泄；HTTP 状态按 `core.errors.HTTP_STATUS` |

OpenAPI 初版的成功状态码与约定（决策人 2026-09-17 批准）：`POST /v1/ask` 200；`POST /v1/tasks` 202（重复 `Idempotency-Key` 返回原任务与原状态码）；`GET /v1/tasks/{id}` 200；`POST /v1/tasks/{id}/retry` 202，不满足"failed 且 retryable"时返回 `409 task_not_retryable`（专用错误码，domain 类）；`POST /v1/feedback` 201。`Idempotency-Key` 为可选请求头，文档写明作用域、同 payload 返回原回执（含处理中、不返回 409）、异 payload 返回 422、同事务落库；保留期由 `IDEMPOTENCY_KEY_TTL_SECONDS` 配置，默认 604800 秒（7 天），下限 86400 秒由 `Settings` 强制，并写入 OpenAPI。管理、策略与回放端点在其模型定义后加入 OpenAPI，不预置空路径。

身份永远来自已验证的 bearer token。`extra="forbid"` 保证已定义模型的请求体中不接受 `dept`、`scopes` 等身份字段；查询参数解析与鉴权在 M3 随路由实现。

## MCP 只读工具（基线 5.7、INV-AUTH-04）

传输为 Streamable HTTP，鉴权为 OIDC bearer；stdio 仅限本地开发与测试。`schemas/mcp/tools.json` 是本地描述清单，不是 MCP `tools/list` 响应；M3-06 把它映射到协议的 `inputSchema`/`outputSchema`，`read_only` 标记不构成权限控制。存在性与可见性均相对当前身份：不可读的文档对这些工具即不存在。

| 工具 | 输入 | 输出 | 语义要点 |
| --- | --- | --- | --- |
| `search_documents` | `SearchDocumentsInput`（query、k ≤ 20、可选 historical_version） | `SearchDocumentsOutput` | 命中只含 active 文档，除非显式请求历史版本；`candidate_exhausted` 与命中数一致；draft 永不暴露 |
| `get_chunk` | `GetChunkInput` | `ChunkView` | 含完整 `Citation`、正文与 `content_hash`，受 ACL 与状态约束 |
| `verify_citation` | `VerifyCitationInput` | `VerifyCitationOutput` | 不存在的引用没有状态也不可能匹配；存在的引用必报状态 |
| `list_active_versions` | `ListActiveVersionsInput` | `ListActiveVersionsOutput` | 每个 family 至多一个 active（INV-DATA-02） |

工具集合固定为四个且全部只读；名称中不得出现写操作词，输入不接受身份字段，均有测试。
