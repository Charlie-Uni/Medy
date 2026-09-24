# 实现记录 72：只读 MCP 的 Streamable HTTP 真实往返（M3-06 收口）

- 日期：2026-09-24
- 授权："先继续进行无需决策的工作"；补记录 62 / 67 留下的"Streamable HTTP 真实往返"缺口
- 范围：草稿目录驱动脚本（不入库）；报告 `evals/harness/runs/2026-09-24-mcp-http-v1/report.{json,md}`；不改代码

## 1. 做法

- `python -m medops.mcp.serve --transport streamable-http --port 8011 --device mps`，环境与记录 67 相同：`DATABASE_READONLY_URL` 为只读 LOGIN 用户，`OIDC_ISSUER / OIDC_AUDIENCE / OIDC_JWKS_JSON` 指向合成签发方（kid `e2e-k1`），principal 为记录 67 写入的 `e2e-user-1`（MA）。
- 客户端用官方 SDK `mcp.client.streamable_http.streamable_http_client` + `create_mcp_http_client(headers=...)` 携带 bearer；拒绝路径同时用原始 HTTP 请求取状态码（SDK 只暴露"Server returned an error response"）。

## 2. 结果（12/12）

| 步骤 | 结果 |
| --- | --- |
| 未带令牌探测 | 401 + `WWW-Authenticate: Bearer error="invalid_token"`（服务一启动就拒绝匿名） |
| `list_tools` | 恰好四个只读工具 |
| `get_chunk`（ms-0001 的 gold chunk） | active，含引用与内容哈希 |
| `list_active_versions`（同 family） | 返回现行版本 |
| `verify_citation`（上一步的引用） | `fields_match=true` |
| `search_documents`（glimepiride 每日最高建議劑量，k=5） | 5 条命中，gold 在内（生产 Searcher = 与链路同一 `ProductionRetrieval`） |
| MA 身份取 PV 的 chunk（ICH E2D） | `isError`：`not_found: chunk not found`（不可见即不存在，无存在性泄露） |
| 无令牌 / audience 错误 / 目录中不存在的 subject | 三者原始状态均 401，SDK 会话均无法初始化 |
| SIGTERM | 进程干净退出（uvicorn 重新抛出信号，退出状态 −15，同记录 67） |

## 3. 结论与进度

- M3-06 的基线条目（四个只读工具；生产 Streamable HTTP + bearer，继承身份与数据库权限，不能写入；stdio 仅开发测试）全部有真实证据：单元 6 + 集成 4（记录 62）、stdio 真实往返（记录 67）、HTTP bearer 真实往返（本记录）。**M3-06 → 已实现**。"不能写入"由只读 LOGIN 用户与 RLS 集成测试证明，本次未再重复。
- 未做：MCP 调用审计（每次工具调用写 Trace）未在 M3-06 基线条目内，登记到 M3-07 的后续；未知 subject 目前与无效令牌同样呈现为 401（SDK 的 `TokenVerifier` 只有"有效 / 无效"两态），若需 403 区分要绕过 SDK 中间件，留待需要时再做。
- P0 加权进度 57.6% → **58.2%**（46.0/79）；M3 8.5/13。费用 0。
