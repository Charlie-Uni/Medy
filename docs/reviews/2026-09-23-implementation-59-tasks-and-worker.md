# 实现记录 59：异步任务与 worker（M3-02、M3-04 首切片）

- 日期：2026-09-23（夜）
- 范围：`POST /v1/tasks`、`GET /v1/tasks/{id}`、`POST /v1/tasks/{id}/retry` 三个接口的完整语义（Idempotency-Key 作用域与 request hash、同 key 同 payload 返回原任务、不同 payload 422、创建与幂等记录同事务、并发重复返回原任务、创建者可见、失败且可重试才允许重试），任务表与 worker（数据库租约、原子状态转换、attempt 单独记录、失联租约回收、重复消费有界、崩溃可恢复），以及把 Skill 结果接入任务契约。
- 依据：基线 3.2（HTTP 幂等）、4.2（`tasks/task_attempts`）、5.7（异步任务与 worker）、§8 M3-02/04；`docs/api/CONTRACTS.md`（决策人 2026-09-17 批准的状态码与幂等语义）；记录 55/57（Registry 与五个 Skill）、记录 58（API 与身份边界）。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| **契约演进**：`TaskResponse.result` 由 `AskResponse` 改为新的 `TaskResult`（Skill `name@version`、状态 completed / insufficient_evidence / escalated、reason codes、按该 Skill 注册的输出 Schema 校验过的 `output`、版本集）；`schemas/` 与 `openapi.json` 重新导出，`CONTRACTS.md` 标注变更日期与原因 | M0 定契约时 Skill 尚未定义；五个 Skill 的输出是按 Skill 定义的结构（AE 要素、偏离结论、范围判定），塞进 `AskResponse` 会丢失结构或伪造 claim。属契约变更，**提请决策人确认** |
| 幂等作用域 = principal 假名 + 路由 + key；存 canonical request hash；同 key 同 payload 返回原任务（含处理中，202），不同 payload `422 idempotency_payload_mismatch`；任务与幂等记录同一事务，并发重复插入由主键冲突判定后返回赢家的任务（savepoint 保证外层事务可继续） | 3.2 与 CONTRACTS 明文；「并发返回原 task 不返回 409」 |
| 任务可见性 = 创建者本人（principal 假名）；其他一律 `404 not_found` | CONTRACTS「Tasks outside the caller's visibility are 404」；部门级共享属 P1 |
| PostgreSQL 是队列与事实来源：worker 用 `update … where task_id = (select … for update skip locked limit 1)` 原子占用并写租约；租约到期的 running 任务可被再次占用，原 attempt 记 `lost`；attempts 达 `max_attempts` 即 fail-closed；worker 的迟到汇报（租约已丢）被忽略 | 5.7「数据库租约或原子状态转换」「不把 Redis 队列当唯一事实来源」；3.2 重试不重复副作用（配合 M2-03 账本） |
| worker 执行时重新解析 principal（目录中已停用或换部门即 `forbidden` 失败），Skill 经 Registry 执行；Skill 处理器崩溃是「已完成的任务 + escalated 的结果」（Registry 语义），基础设施错误才是「失败的任务」 | INV-AUTH-03 默认拒绝；Registry 已把处理器异常收敛为 system_failure 升级（记录 55） |
| 完成 / 失败的公开形状直接持久化（`TaskResult` / `ErrorResponse` JSON），内部 detail 不落库、不外发 | 5.12；错误契约 |
| worker 入口 `python -m medops.worker.serve`：轮询间隔可配、SIGTERM 完成当前任务后退出 | M3-12 优雅停机的第一步 |

## 2. 交付

- 迁移 `0010_tasks.py`：`tasks`（状态、attempts、租约、trace、result/error 形状约束、身份与输入不可变、completed 不可变、failed 只能回 queued）、`task_attempts`（每次尝试一行，唯一 (task_id, attempt)）、`idempotency_keys`（主键 = principal + route + key，追加写，过期索引）；应用角色读写、管理角色只读、只读角色无权限，FORCE RLS。
- `src/medops/application/tasks.py`：`TaskRecord`、`TaskStore` 协议、`TaskService`（create / get / retry）、`to_response`、`TaskRunner`（一次 worker 步骤）、`InMemoryTaskStore`；`src/medops/infrastructure/db/tasks.py`：`PgTaskStore`；`src/medops/worker/serve.py`。
- `medops.api.app` 三个任务路由；`ApiRuntime` 增 `task_store`；`ProductionRuntime` 增 worker 环境（`resolve_user`、`skill_context`）。
- 契约：`TaskResult` / `TaskResultStatus`，`schemas/api/TaskResult.schema.json`、`TaskResponse.schema.json`、`openapi.json` 重导出；`CONTRACTS.md` 更新。
- 测试：单元 5 项（幂等作用域 / 过期 / 无 key、可见性与重试规则、worker 在存储身份下执行并持久化结果、principal 消失与处理器崩溃的失败路径、租约丢失回收与 attempts 上限）；路由 3 项（202 / 重复 key / 422 / 401 / 404 / Schema、他人不可见、retry 409 → 202 与 completed 结果）；集成 4 项（幂等竞争与 savepoint、占用 / 租约 / 迟到汇报 / attempt 行、耗尽即失败与 requeue、只读角色无权限）；迁移清单、往返与 RLS 集合更新到 0010。

## 3. 未做 / 限制

- 未在真实库上跑通「API 创建 → worker 执行 → 结果可查」的端到端（需要给 medops_v2 应用迁移 0008–0010 并登记一条 principal；主集 v2 全量运行结束后做，避免与其争用）。
- 幂等记录的过期清理（按 `expires_at`）没有任务；TTL 只在查询时生效。
- 反馈接口的 Idempotency-Key（`receipt` 列已预留）随 M3-03。
- worker 没有并发限制与 Redis 唤醒（可选优化）；租约续期未做，长任务以 `lease_s` 覆盖 Skill 超时（默认 300 秒 > Skill 最长 120 秒）。

## 4. 自审（§9）

- 幂等与创建同一事务、并发由数据库主键判定（集成测试证明竞争者拿到赢家任务且事务可继续）。
- 状态转换全部带 `where status = … and lease_owner = … and attempts = …` 条件；触发器拒绝 completed 后的任何更新与非法回退。
- 身份在执行时重新解析；输出形状是公开契约，内部 detail 不落库。
- 未改动已冻结数据；未触碰 medops_v2（集成测试用一次性数据库）。

## 5. 进度

- M3-02 已实现（契约变更待决策人确认）、M3-04 部分（缺真实库端到端）。P0 加权进度 49.4%（39.0/79）；按 99 项计 39.4%。分项：M0 10/11、M1 16.5/21、M2 9.5/16、M3 3/13、M4 0/10、M5 0/8。
