# 实现记录 09：API 与 MCP 工具契约及 JSON Schema 输出（M0-08）（2026-09-10）

按基线第 9 节交付格式。范围：M0-08。不引入 FastAPI，不建服务。（历史表述：首版曾写“OpenAPI 在 M3-01 由同一批模型生成”；现行结论见文末文档收尾：OpenAPI 初版仍属 M0-08 未交付部分，延期须批准。）**状态：首版，已被第二版与复核结论取代。**

## 完成

| 产物 | 内容 |
| --- | --- |
| `src/medops/api/contracts.py` | `AskRequest`（长度上限、显式历史版本选择器二选一）、`AskResponse`（outcome 与负载一一对应，答案复用领域 `Answer`，拒答/升级必带 `ReasonCode`）、`TaskCreateRequest`（skill 名格式、JSON 对象输入）、`TaskResponse`（终态负载规则）、`FeedbackRequest`（correction 必带文本）、`FeedbackReceipt`；`Idempotency-Key` 语义以常量文档记录；错误复用 `ErrorResponse` |
| `src/medops/mcp/contracts.py` | 四个只读工具的输入输出模型与 `MCP_TOOLS` 清单：k ≤ 20、`candidate_exhausted` 一致性、draft 永不暴露、archived 必标 historical、`verify_citation` 存在性与状态一致、每 family 至多一个 active；输入不接受身份字段 |
| `src/medops/contracts_export.py` | 从模型导出 15 个 JSON Schema（api 7、mcp 8）加 1 个工具清单到 `schemas/`，输出确定性；`--check` 检测漂移 |
| `schemas/` | 已生成、未提交的导出结果（15 个 Schema 加 1 个清单） |
| `docs/api/CONTRACTS.md` | 端点与模型对照、`Idempotency-Key` 与错误语义、MCP 工具语义 |
| `Makefile`、CI | `make schemas` 导出；`make check` 与 CI 增加漂移检查 |
| `tests/unit/api`、`tests/unit/mcp` | 10 个测试：outcome 互斥、历史选择器、任务终态规则、反馈规则、身份字段拒绝、四工具只读与命名、耗尽一致性、draft 隐藏、引用核验一致性、已提交 Schema 与模型一致 |

## 自审（基线第 9 节）

1. 需求：只覆盖 M0-08；未实现任何路由、鉴权或数据访问；管理端点只登记归属里程碑。
2. 逻辑：`AskResponse` 用集合比较保证恰好一个负载；`TaskResponse` 终态规则覆盖 completed/failed/非终态三向；MCP 输出的耗尽标记与命中数强绑定。
3. 安全：请求体与工具输入 `extra="forbid"`，`dept/scopes` 一律拒绝并有测试；错误响应结构上无 detail。
4. 契约：JSON Schema 由模型导出并有漂移测试；领域 `Answer`、`Citation`、`ReasonCode`、`VersionSet` 直接复用，避免两套定义。
5. 测试：正常、边界（长度、k 上限）、失败（互斥、缺负载、身份字段）。
6. 可观测：`AskResponse` 与 `TaskResponse` 携带 `trace_id`、`versions`。
7. 简洁性：导出器只有渲染、写入、检查三个函数；未加 OpenAPI 生成器；`TaskResponse.result` 暂复用 `AskResponse`，Skill 输出结构随 M2 定义时再分化。
8. 验证：见下。
9. Checklist：不勾选 M0-08，OpenAPI 初版待 M3-01 生成。

## 验证

```text
env -u PYTHONPATH make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!
  mypy                    -> Success: no issues found in 34 source files
  pytest -q               -> 159 passed（本轮新增 10 项）
  contracts_export --check-> schemas up to date
```

## 待 Codex 审核的重点

1. `AskResponse` 把领域 `Answer` 原样暴露到线上是否合适，或应有单独的 wire 模型隐藏内部字段。
2. `TaskCreateRequest.input` 用 `dict[str, JsonValue]` 是否满足 INV-HAR-01 的精神（节点契约不用 Any），还是应要求每个 Skill 的输入模型在此处引用。
3. MCP `verify_citation` 的 `fields_match` 语义是否足够，或应逐字段返回差异。
4. 导出的 JSON Schema 提交到仓库并用测试守护漂移，是否比在 CI 中现生成更合适。

## 第二版：按 Codex 审核修订（2026-09-11）

Codex 结论为“暂不通过，六组契约问题”。全部修复；四个审核点按结论保留现有设计。**状态：待 Codex 复核。**

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| 任务终态负载不互斥：completed/failed 都允许同时带 result 与 error | 固定为 completed 有 result 无 error、failed 有 error 无 result、queued/running 两者皆无 | `test_task_response_terminal_payloads_are_mutually_exclusive`（两种双负载各一条反例） |
| 导出 Schema 丢失跨字段规则 | 用模型侧 `json_schema_extra` 补入：历史选择器二选一（oneOf）、outcome 与负载配对（if/then）、任务终态、correction 文本、可见状态枚举与 historical 配对、verify_citation 存在性规则；不手改生成文件 | `tests/unit/api/test_schema_semantics.py`：30 组一致性用例同时跑模型与导出 Schema，要求判定一致；另 1 组哈希例外列为 Schema 放行、模型拒绝（服务端规则） |
| ChunkView 正文与哈希不一致可构造 | `content_hash` 定义为完整正文 UTF-8 SHA-256 并重算比较；文档写明这只保证自洽，可信哈希仍来自事实平面 | `test_chunk_view_content_hash_is_recomputed`（正文篡改、随意哈希） |
| MCP 三处自洽漏检 | 命中 chunk 唯一（重复不能凑满 K）；active 文档必须属于请求的 family；`effective_to` 必须晚于 `effective_from` | `test_search_output_exhaustion_uniqueness_and_visibility`、`test_list_active_versions_family_and_window_consistency` |
| verify_citation 可见性契约不完整 | `exists` 定义为当前身份可见范围内存在；draft 永不可见（`exists=True, status=draft` 被拒绝）；archived 遵循显式历史查询；`fields_match` 比较全部 Citation 字段含 `effective_date`，不代表当前可引用 | `test_verify_citation_visibility_contract` |
| 请求边界 | `HistoricalRequest.version` 改为非空类型；`ApiModel`/`McpModel` 设 `allow_inf_nan=False`，嵌套 NaN/Infinity 一律拒绝 | `test_ask_request_bounds_and_historical_selector`、`test_task_create_rejects_non_finite_numbers_and_bad_names` |

文档同步：`schemas/` 为“已生成、未提交”，实际 15 个 Schema 加 1 个工具清单；`tools.json` 加注为本地描述清单而非 MCP `tools/list` 响应，后续映射到 `inputSchema/outputSchema`，`read_only` 不构成权限控制；`extra="forbid"` 的说明限定为已定义模型字段，查询参数解析与鉴权在 M3 实现；OpenAPI 初版仍是 M0-08 未交付部分，可分切片补齐，未经批准不把基线要求后移到 M3，也不为此现在建 FastAPI 空壳。

验证：`env -u PYTHONPATH make check` 通过；mypy 34 个源文件；pytest 192 passed（本轮新增 33 项）；`contracts_export --check` 最新。

文档收尾（2026-09-11，按复核意见）：首表“16 个 Schema、已提交”改为“15 个 Schema 加 1 个清单、已生成未提交”；一致性用例计为 30 组加 1 组哈希例外；API 模块首段的 OpenAPI 表述与“M0-08 未交付部分、延期须批准”对齐；路线图 M0-02 的选型表述改为 uv/pip 已由 ADR-0004 批准、Redis 单独待确认。复核结论：六组修复通过，M0-08 保持“部分”。
