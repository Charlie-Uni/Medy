# 实现记录 75：管理接口契约落地（M3-03，DEC-012）

- 日期：2026-09-25
- 授权：记录 74 A 部分，决策人 2026-09-25「同意」
- 范围：迁移 0014、`medops.ingestion.activate`（archive / withdraw）、`medops.ingestion.acl`、`medops.infrastructure.db.{documents,policies,idempotency}`、`medops.application.admin`、API 契约与九条路由、OpenAPI 与 schemas、单元 + 集成测试、`DEPLOY.md`、`CONTRACTS.md`

## 1. 决定与依据（记录 74 之外的实施细节）

| 决定 | 依据 |
| --- | --- |
| 管理路由在**管理数据库角色**上执行：身份仍用应用连接校验，操作用 `DATABASE_ADMIN_URL` 打开的连接；缺配置时 503 `dependency_unavailable` | INV-AUTH-05 角色分离；文档状态、ACL、策略表的写权限只授予 `medops_admin_role`；不给应用角色加写权限 |
| 幂等收据复用 `idempotency_keys.receipt`（作用域 principal + 路由（含路径 id）+ key），新增管理角色的 insert 策略与授权 | 与任务 / 反馈同一语义（基线 3.2）；管理动作不是任务，收据就是响应体 |
| `released_policies` 单独成表作为「released 指针」（每个 (kind, name) 至多一行），`policies.status` 记生命周期，`policy_releases` 追加写记录每次切换与前值 | INV-HAR-06「生产只读 released」；原子回滚 = 一条 update；历史可审计 |
| `medops_loop_role` 只授 `insert`（RLS `with check (status = 'candidate')`）与 `select`；无 update / delete | INV-AUTH-05「Loop 只能写 candidate」；集成测试用真实 LOGIN 用户证明 update 与直接插入 released 都被拒 |
| 门禁在 M3 只做「证据里必须有 `gate.passed = true`」的占位校验 | 门禁数值计算是 M4-08 的事；契约与状态机先稳 |
| 四眼在服务层：`created_by == 裁决人假名` → 403 | 基线「人工签字」的最小实现；角色检查在路由层，状态机在服务层 |
| ACL 变更发 `document_acl_changed` 事件，payload 的 `acl_depts` 为变更前后并集加所有者部门 | 让缓存消费者把所有可能持有该文档候选的部门 epoch 都失效（补 M1-19 登记项） |
| 状态变更沿用发布链：`activate_document`（既有）、新增 `archive_document`（active→archived，关闭生效窗口）与 `withdraw_document`（draft→withdrawn）；非法转换由触发器与函数双重拒绝 → `409 status_conflict` | 迁移 0004 的状态机不变；管理路由只是给它一个 HTTP 入口 |

## 2. 交付

- 迁移 0014：`policies` / `policy_releases` / `released_policies`（FORCE RLS，追加写守卫）、`medops_loop_role`、outbox 事件类型 `document_acl_changed`、管理角色的幂等收据 insert；本地 medops_v2 与 medops_v2_safety 已升到 0014。
- 契约：`DocumentListResponse` / `DocumentDetail` / `DocumentStatusRequest` / `DocumentAclRequest` / `DocumentAclResponse` / `PolicyListResponse` / `PolicyResponse` / `PolicyDecisionRequest` / `PolicyReleaseRequest` / `PolicyRollbackRequest`；错误码 `status_conflict`、`gate_not_passed`（409）；OpenAPI 新增 9 个操作、2 个路径参数，`schemas/` 重生成；`CONTRACTS.md` 第 14–15 行占位改为正式行。
- 路由：`GET /admin/documents`、`GET /admin/documents/{doc_id}`、`PATCH …/status`、`PATCH …/acl`、`GET /admin/policies/candidates`、`GET /admin/policies/{policy_id}`、`POST …/approve`、`POST …/release`、`POST …/rollback`。
- 测试：单元 `tests/unit/api/test_admin_routes.py`（角色逐接口：analyst 403 / 无令牌 401 / approver 只能裁决 / admin 发布回滚；状态机 409；ACL 幂等与所有者保护；四眼、门禁、灰度上限 422、指针与回滚日志）；集成 `tests/integration/test_admin_stores.py`（loop LOGIN 用户只能插入候选、指针切换与回滚、追加写；文档链的审计行与 outbox 事件、收据存储）；OpenAPI 契约表与迁移往返测试更新。

## 3. 未做 / 限制

- 门禁数值（+5pp / 非目标 ≤ 1pp / 安全不降、三次运行取最差）随 M4-07/08；现在发布只看 `evidence.gate.passed`。
- 灰度只记录比例，没有流量分配器（M4-09 随发布机制）。
- 管理路由未落每次调用的 Trace（与 MCP 记录 73 同类）；`doc_audit` 与 `policy_releases` 已记录谁做了什么，请求级 Trace 留待 M3-07 收尾统一处理。
- 真实 HTTP 冒烟（管理路由）随下一次端到端一起跑。

## 4. 自审（§9）

- 权限：写操作全部在管理角色连接上，应用角色对新表只读；loop 角色的限制由真实 LOGIN 用户在 FORCE RLS 下证明。
- 审计：状态变更由触发器写审计（沿用），ACL 变更显式写审计，策略决定与发布记录假名、时间、理由。
- 契约流程：记录 74 决策 → 契约 → OpenAPI / schemas 重生成 → 测试；`CONTRACTS.md` 与 `openapi.json` 同步。
- 费用 0。

## 5. 进度

- M3-03 部分 → **已实现**；P0 加权 58.2% → **58.9%**（46.5/79）；M3 9/13。
