# 实现记录 73：MCP 工具调用逐次落 Trace（M3-07 后续）

- 日期：2026-09-24
- 授权："先继续进行无需决策的工作"；补记录 62 / 72 留下的"MCP 调用审计"缺口
- 范围：迁移 0013、`medops.mcp.server`（每次工具调用一条 `kind='mcp'` 的 Trace，审计失败即拒绝返回数据）、`McpProductionRuntime.audit`（应用角色连接）、单元 + 集成测试、本地两库迁移到 0013

## 1. 决定与依据

| 决定 | 依据 |
| --- | --- |
| 复用 `traces` 表，新增 `kind='mcp'`（迁移 0013 只改 CHECK 约束），不建新表 | 基线 4.2「每次请求完整 Trace」；MCP 调用就是请求；同一张表让 `/metrics` 与回放读取路径不变 |
| Trace 内容：principal 假名（开发身份哈希成 64 hex 以满足列约束）、部门、`query = 工具名 + 输入摘要（≤ 500 字）`、outcome（answered / refused / escalated）、错误码作为 reason code、交出的 chunk id（递归收集输出里的 `chunk_id`）、耗时；模型调用 / 费用为 0；versions = MCP 服务版本 + 检索复合版本 | INV-OBS-01/02：最小必要、假名化；chunk id 而不是内容 |
| **fail-closed**：Trace 在数据离开进程前写入；审计写失败 → `ToolError("internal_error: audit unavailable, call refused")`，不返回数据 | 与 `/v1/ask` 的 `record_or_fail_closed`（记录 60）同一策略 |
| 写入走应用角色连接（`app_dsn_for_directory`，已用于 principals 目录），工具本身仍在只读角色事务内执行 | INV-AUTH-04 只读由角色证明不变；审计需要写权限 |
| 错误路径也审计（forbidden / unauthenticated → refused，其余如 not_found → escalated + 错误码）；未通过 bearer 校验的请求在 SDK 中间件层被拒，没有身份可记，不落 Trace | 与 API 一致：401 无身份不产生 Trace |

## 2. 验证

- 单元（`tests/unit/mcp/test_server.py`）：每次调用一条 Trace（kind、工具名、chunk id、假名长度 64）；`not_found` 路径记 escalated + `("not_found",)`；审计存储故障时 `isError` 且无 `structured_content`。
- 集成：`McpProductionRuntime.audit` 经应用 LOGIN 用户写入 `kind='mcp'` 行；迁移 0013 往返（`test_migrations` 头为 0013）；全量 `make check` 通过。
- 真实：记录 72 的 Streamable HTTP 驱动重跑 12/12 通过，medops_v2 新增 5 条 `mcp` Trace（get_chunk 1 chunk、search_documents 5 chunks、list_active_versions / verify_citation 0、跨部门 get_chunk → escalated `not_found`）。
- 本地 medops_v2 与 medops_v2_safety 已升到 0013。

## 3. 未做 / 限制

- `/metrics` 的窗口统计按 kind 聚合时会把 mcp 计入请求总数（低基数标签 kind 已有）；MCP 专属指标（工具名维度）未加。
- 未通过认证的 MCP 请求不留痕（与 API 相同）；如需记录匿名 401 计数，属指标层而不是 Trace。
- 进度：M3-07 保持部分（受限载荷加密存储待做）；M3-06 的"调用审计待做"注记撤销。P0 不变 58.2%。
