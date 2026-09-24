# 实现记录 62：只读 MCP 服务器（M3-06 首切片）

- 日期：2026-09-24
- 范围：基线 5.7 / INV-AUTH-04 的四个只读 MCP 工具（`search_documents`、`get_chunk`、`verify_citation`、`list_active_versions`）：与框架无关的服务实现、基于官方 SDK 2.x 的服务器（Streamable HTTP + bearer，stdio 仅开发测试）、只读数据库角色下的可见性与不可写证明。
- 依据：基线 2.3（INV-AUTH-04：MCP 只暴露只读工具，从受信 token 解析身份，不接受调用方声明 `dept/scopes`；生产 Streamable HTTP + OIDC bearer，stdio 仅开发）、5.7、§8 M3-06；[ADR-0001](../adr/ADR-0001-identity-oidc-boundary.md) §5；`docs/api/CONTRACTS.md` MCP 节与 `schemas/mcp/*`（M0-08 契约）。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 新增依赖官方 `mcp` SDK（2.2.0；`make lock` 重生成，无既有 pin 变更）；用 `MCPServer` + SDK 自带的 bearer 中间件，`TokenVerifier` 由 API 的 `Authenticator` 实现（同一 JWKS 校验、假名、principal 目录） | 基线技术栈指定 MCP；身份边界与 API 同源，避免两套鉴权 |
| 工具实现（`McpService`）与框架无关，在**只读 LOGIN 用户**的连接上执行，部门用事务级 `set_config` 注入；不可读的文档对工具「不存在」（`get_chunk` → not_found，`verify_citation` → `exists=false`） | INV-AUTH-04「通过数据库权限证明不能写入或越权」；契约「存在性与可见性均相对当前身份」 |
| 状态规则在 SQL 与服务两层：只取 active / archived；archived 仅当调用显式给出该版本标签 `historical_version`；draft / withdrawn 永不暴露 | 契约 `_VISIBLE_STATUS_SCHEMA`；INV-DATA-03 |
| `search_documents` 把候选获取交给 `Searcher` 端口（生产 = 与链路相同的 `ProductionRetrieval`，在只读事务内构造）；服务只做可见性过滤、去重、`candidate_exhausted` 与 snippet 截断 | 路线图「API、MCP、Skill 都走同一授权检索与证据校验服务」 |
| `get_chunk` 重算内容哈希并与事实平面比对，不一致即 `evidence_integrity_failed` | 契约 `ChunkView` 自洽性；3.3 三级哈希 |
| stdio 传输：`app_env=prod` 拒绝启动；必须给 `--dev-dept`，身份为固定的合成低权限身份，仍走只读角色 | ADR-0001 §5；5.7 |
| 工具错误以 SDK 的 `isError` 返回 `code: message`，不带内部细节 | 5.12 |
| 运行时配置新增 `DATABASE_READONLY_URL`（只读 LOGIN 用户 DSN），MCP 服务缺它即拒绝启动 | INV-AUTH-04 |

## 2. 交付

- `src/medops/mcp/service.py`（`McpService`、`Searcher` 协议）、`server.py`（`build_server`、`BearerVerifier`、`McpRuntime` 协议、`McpProductionRuntime`）、`serve.py`（`python -m medops.mcp.serve --transport streamable-http|stdio`）；`Settings.database_readonly_url`。
- 测试：单元 4 项（`tests/unit/mcp/test_server.py`，SDK 内存流驱动：恰好四个工具、全部 `readOnlyHint`、输入 Schema 无身份字段；工具在调用身份下运行、not_found 以 isError 返回且无堆栈；HTTP 无 token / 伪造签名 → 401、有效 token 通过；无任何身份即拒绝）；集成 4 项（`tests/integration/test_mcp_service.py`，只读用户 + 真实 RLS：他部门 / draft / archived 不可见、历史版本标签放行 archived、`verify_citation` 逐字段比对与不可见文档 `exists=false`、`list_active_versions` 单一 active、search 对 Searcher 输出套用同一可见性、同一连接写入被拒）。`make check` 全部通过。

## 3. 未做 / 限制

- 生产 Searcher（嵌入 + 重排 + 回查）未在 MCP 进程里实测（需要 GPU 与语料库，主集重跑结束后补一次 stdio 冒烟）；单元与集成测试用假 Searcher。
- `schemas/mcp/*.schema.json` 是契约的独立 Schema；SDK 从函数签名生成的 `inputSchema` 把契约模型包在 `input` 字段下，未做逐字节一致性测试，只测了字段名与只读标记。
- 参数上限（`k ≤ 20`、query ≤ 2000）由契约模型强制；每工具的速率限制与落库审计（5.7「逐项做授权、参数上限和审计」中的审计）随 M3-07 的 Trace 扩展到 MCP 调用，本切片未写 Trace；同日补了 `mcp.tool` OTel span（工具名、部门、错误码，记录 66）。
- OIDC 发现与 JWKS 轮换同记录 58 的限制。

## 4. 自审（§9）

- 只读性由数据库角色证明（集成测试：同一连接 insert 被拒），不是靠 `read_only` 标记。
- 身份只来自 token（HTTP）或启动参数（stdio，非 prod）；工具输入模型 `extra="forbid"` 且无身份字段。
- 未改动已冻结数据；未触碰生产库；未写 `.env`。

## 5. 进度

- M3-06 部分。P0 加权进度 52.5%（41.5/79）；按 99 项计 41.9%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 5/13、M4 0/10、M5 0/8。
