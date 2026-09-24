# 实现记录 67：真实库端到端——API、worker、MCP 三进程在 medops_v2 上各跑一遍

- 日期：2026-09-24
- 范围：记录 58（API）、59（任务 + worker）、60（审计）、62（MCP）、64（指标）、65（回放）都只在 TestClient / 假运行时 / 每测试临时库上验证过；本记录把生产运行时（`ProductionRuntime` / `McpProductionRuntime`）接到 M1 冻结的知识库 medops_v2 上真实跑一遍，逐项核对 HTTP 契约、落库行、进程退出码
- 驱动脚本在会话草稿目录（不入库）；报告 `evals/harness/runs/2026-09-24-e2e-v1/report.{json,md}` 入库，只含状态码、结果类别、计数与 trace / task id，不含证据全文、DSN、令牌

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 用 medops_v2（M1 冻结库）而不是新建库：迁移 0007 → 0012 已应用（`alembic current` = 0012 head），0008–0012 只新增表 / 函数，不改既有文档、chunk、事实平面 | 链路需要真实文档与检索；记录 51 的 M1 端到端与记录 54 的全量运行都在这个库上 |
| 身份用合成签发方：本地 RSA 密钥（kid `e2e-k1`）、JWKS 以 `OIDC_JWKS_JSON` 静态注入、`OIDC_ISSUER=https://issuer.test/medops`、audience `medops-api`；principal 预先写入 `principals`（HMAC 假名、dept MA、roles analyst / admin / ops、scopes `MA:read`、`created_by=record-67-e2e`） | DEC-010（IdP）未定；静态与远程 JWKS 共用同一校验路径（记录 61），本次验证的是校验 → 假名 → 目录 → 部门注入这一整条链，不是某个 IdP |
| API / worker 用 `medops_app_user`，MCP 用 `medops_readonly_user`；DSN 在驱动进程内由 `.env` 的口令拼装并只经环境变量传给子进程，不落盘、不进报告 | `require_acl_enforced` 拒绝超级用户；INV-AUTH-04 只读由数据库角色证明；处理规范：不回显口令 |
| 三个进程串行：API（端口 8010，`--device mps`）→ 优雅停机 → `worker --once` → MCP stdio（`--dev-dept MA`）；不并行 | 本机只有一个 MPS 设备，且 torch 线程钉在单线程（记录 54 §3.0） |
| MCP 走 stdio 而不是 Streamable HTTP | HTTP bearer 路径已由记录 62 的集成测试覆盖；本次要补的是「生产 Searcher（与链路同一 `ProductionRetrieval`）+ 只读角色 + 真实库」 |
| 高风险拒答样本用「我最近血压 150/95，我应该每天吃多少 losartan？」（`intent-rules-v2` 覆盖的状语句式） | 记录 56：v1 规则漏掉过这类句式，正好作为 fail-closed 的真实核对 |

## 2. 步骤（驱动脚本顺序）

1. 启动 API，轮询 `/readyz` 直到 200（模型加载在此之前完成）。
2. `/v1/ask`：MA 样本 ms-0001「瑪爾胰(glimepiride)每日最高建議劑量是多少?」应 `answered`；高风险问句应 `refused` 且 reason code 为 `high_risk_medical`；无令牌 401；目录中不存在的 subject 403。
3. `/metrics`（ops 角色）应 200 且含 `medops_requests_window`。
4. `/v1/feedback` 同 Idempotency-Key 两次应返回同一收据（201 × 2）。
5. `/v1/tasks` 创建 `label_query@1.0.0`（Losacar 起始 / 维持剂量）应 202 `queued`，同 key 第二次返回同一 task_id。
6. `/admin/traces/{trace_id}/replay`（admin 角色）应 201，回放侧 outcome 为 answered / escalated。
7. SIGTERM → API 退出码 0。
8. `python -m medops.worker.serve --once` 退出码 0；`tasks` 行应 `completed`、`result.status` 与 excerpts 数可见。
9. 管理连接核对 traces / trace_spans / escalations / feedback / tasks / task_attempts / replays / operation_executions / operation_attempts 行数与 trace 种类。
10. MCP stdio：`list_tools` 四个工具；`get_chunk`（ms-0001 的 gold chunk）→ `list_active_versions`（同 family）→ `verify_citation`（`fields_match=true`）→ `search_documents`（gold 是否在前 5）。

## 3. 结果

跑了两轮（`report.md` 为第二轮，`run1_findings.md` 保留第一轮的逐步结果）。

| 步骤 | 第一轮（14:28–14:33） | 第二轮（14:33–14:36，修复后） |
| --- | --- | --- |
| API 就绪（模型加载后 `/readyz` 200） | ✓ | ✓ |
| `/v1/ask` ms-0001 → `answered`，1 条陈述，Trace 落库 | ✓ | ✓ |
| 高风险问句 → `refused`，`high_risk_medical`，`escalations` 有行 | ✓ | ✓ |
| 无令牌 401；目录中不存在的 subject 403 | ✓ / ✓ | ✓ / ✓ |
| `/metrics`（ops）200，含 `medops_requests_window` | ✓（34 行） | ✓（41 行） |
| `/v1/feedback` 同 Idempotency-Key 两次同一收据 | ✓ | ✓ |
| `/v1/tasks` 202 `queued`，同 key 同 task_id | ✓ | ✓ |
| `/admin/traces/{id}/replay` 201，回放 `answered`，`versions_match=true`，`changed=[]` | ✓ | ✓ |
| SIGTERM 优雅停机 | **✗** 退出状态 −15（见下） | ✓（判据改为「停机日志完整且无回溯」） |
| `worker --once` 退出 0，任务 `completed`（attempts 1，2 条摘录） | ✓ | ✓ |
| 落库行（累计）：traces / spans / escalations / feedback / tasks / attempts / replays / executions | 4 / 13 / 1 / 1 / 1 / 1 / 1 / 17 | 8 / 26 / 2 / 2 / 2 / 2 / 2 / 34 |
| MCP stdio：四个工具；`get_chunk` active；`list_active_versions`；`verify_citation` `fields_match`；`search_documents` 5 命中含 gold | ✓（但客户端报 8 次 JSON-RPC 校验警告） | ✓（0 次警告） |

两条真实发现，均已修：

1. **API 停机退出状态是 −15（容器内 143），不是 0。** 日志显示 `Shutting down → Application shutdown complete. → Finished server process`，无回溯；uvicorn 0.53 在优雅停机完成后会重新抛出捕获的信号（`Server.capture_signals` 的设计），让父进程看到「因信号结束」。这是设计行为而非缺陷：`docker stop` 下 143 就是正常值。处置：驱动判据改为「退出 0 或 −15，且停机日志完整、无 Traceback」；`docs/DEPLOY.md` 注明。
2. **MCP stdio 把结构化日志写到了 stdout。** `configure_logging` 默认 stdout，而 stdio 传输的 stdout 就是 JSON-RPC 通道；官方客户端把日志行当作消息解析失败后跳过（四个工具调用仍成功），但任何一行日志都可能破坏协议流。处置：`medops.mcp.serve` 在 stdio 传输下把日志送到 stderr；新增 `tests/unit/mcp/test_serve.py` 两条测试（stderr 日志 + 缺 `--dev-dept` 拒绝）。第二轮 0 次警告。

其他观察：

- 两轮问答的 Trace 版本集一致（`answer=gpt-6-sol;judge=gpt-6-sol;verifier-v2+support-rules-v2+polarity_only`；第二轮在 `support-rules-v3` 合入前启动的 API 进程之后、worker 之前，任务 Trace 已是 v3——版本集随进程加载的代码走，这正是它存在的意义）。回放与原问答 `changed=[]`，说明同一问题在两次独立运行里得到同一结论与引用。
- 费用：traces 表 `cost_usd` 合计 0.035 美元（两轮问答 + 回放 + 任务）。
- `list_active_versions` 返回的版本标签是 M1 摄取时的 `pdf-meta 2016-11-22（未见版本行）`——真实数据里的版本行缺失，与 M1-09 的已知问题一致，不是 MCP 的问题。

## 4. 未做 / 限制

- 合成签发方不是真实 IdP：签发、轮换、组映射（`OIDC_GROUP_SCOPES_JSON`）未经真实 IdP 验证；DEC-010 待决。
- 单用户、单部门（MA）：PV / CO 部门的 RLS 隔离本次没有再跑（记录 51 的 RLS 测试覆盖）。
- MCP 只跑了 stdio；Streamable HTTP 的真实 bearer 往返仍只在集成测试内。
- 一次性运行，不是压测；M3-11 的 P95 门禁另做。

## 5. 自审（§9）

- 数据边界：写入只发生在 medops_v2 的审计 / 任务表（追加写），知识表未动；报告不含证据全文、DSN、令牌、口令；principal 行以 HMAC 假名存储，`created_by=record-67-e2e` 便于日后清理。
- 身份：JWT 校验 → 假名 → principals 目录 → `set_config('medops.dept')`，三种失败（无令牌、未登记、非 admin/ops）都在真实 HTTP 上核对过。
- 费用 0.035 美元，在 ADR-0010 上限内。
- 未做见 §4；两条发现都在同一记录内修复并复跑，不留「已知但未修」项。

## 6. 进度

- M3-01 → **已实现**（五种契约 TestClient 测试 + 真实 HTTP 冒烟 + Trace 落库）；M3-04 → **已实现**（租约 worker 的真实库端到端，任务 completed、attempt 与 Trace 落库）；M3-06、M3-07 仍为部分（Streamable HTTP 真实往返、受限载荷加密存储待做），注记更新。
- P0 加权进度 55.1% → **56.3%**（44.5/79）；M3 8/13。
