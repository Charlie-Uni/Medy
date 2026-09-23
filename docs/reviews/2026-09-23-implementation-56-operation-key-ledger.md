# 实现记录 56：operation key 持久化执行账本（M2-03）

- 日期：2026-09-23
- 范围：基线 3.2 的 operation key 从"函数存在"变成数据库证明的幂等执行：执行前占键、成功结果可复用、每次 attempt 单独落库、失败与失联占键可重占、回放 `replay_run_id` 与生产隔离。迁移 0008，端口 `ExecutionStore`（内存版供单元测试、PostgreSQL 版供生产），状态机节点守卫接入。
- 依据：基线 3.2（"相同 operation_key 的成功结果可安全复用；每次 attempt 单独记录；生产 run_id = trace_id、回放独立 replay_run_id；有副作用操作还需数据库唯一约束"）、4.2（`tasks/task_attempts` 子集）、INV-OBS-02/03；路线图 M2-03"不能仅凭函数存在算幂等完成"、M3-08"禁止被原执行缓存短路"。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 账本表 `operation_executions`（主键 = operation key，状态 running/succeeded/failed，`claim_no`，`result` jsonb）+ `operation_attempts`（唯一 (key, claim_no, attempt)，追加写）；不复用 `outbox_events` | 3.2 要求数据库唯一约束；attempt 与 operation 是两个粒度（"trace_id + node + attempt 只能标识一次尝试"） |
| 占键在节点体执行**之前**：`insert … on conflict do nothing`，冲突时 `select … for update` 判定 reused / in_flight / retry | 两个 worker 同键只有一个能插入；成功行直接复用、运行中行不重复执行、失败行或超过 300 秒的失联占键以 claim_no+1 重占 |
| 复用载荷是节点的**状态增量**（变更字段的 JSON），回放时整体重校验 `AgentState`，不走 `advance()` | `advance()` 的下游重置规则会把节点未改动的字段清空（Answer 重验改了 verify_result 但保留 Safety 决定），增量必须原样保留；整体校验仍执行全部不变量 |
| `run_kind` 由 `run_id = trace_id` 推导并加 CHECK；回放的 key 因含 run_id 天然不同 | 3.2 与 M3-08：回放不得被生产缓存短路；表内约束防止把两类运行混记 |
| 应用角色可读写账本（状态机在它之下运行），管理角色只读（审计），只读角色无权限；成功行不可变、attempt 追加写、identity 列不可变（触发器）；两表 FORCE RLS | INV-AUTH-05 角色分离；INV-OBS-02 审计追加写 |
| 运行中的同键请求（`in_flight`）按 `system_failure` 升级而不是等待 | 5.3 失败即升级；节点级没有可靠的等待上界，HTTP 层的"返回原 task_id"语义在 M3 任务层实现 |
| `HarnessDeps.executions` 默认 `None`（无持久化） | 单元测试与离线工具无数据库；生产装配（M3 API）必须传 `PgExecutionStore` |

## 2. 交付

- `migrations/versions/0008_operation_executions.py`：两表、约束（`result` 当且仅当 succeeded、failed 必带 error_code、run_kind 与 run_id/trace_id 一致）、触发器、RLS 与授权；可完整降级。
- `src/medops/harness/executions.py`：`ExecutionStore` 协议、`ExecutionClaim`、`state_delta/apply_delta`、`InMemoryExecutionStore`、`PgExecutionStore`。
- `src/medops/harness/nodes.py`：`guarded()` 占键 → 复用/在途升级 → 执行 → attempt 落库 → 成功写增量或失败写错误码。
- 测试：单元 6 项（重复运行五个节点全部复用且模型与检索零调用、回放 run id 全部重跑且生产行不动、失败节点按 attempt 记录并在下次运行以 claim_no 2 重占、在途占键不重复执行、失联占键接管、增量往返）；集成 5 项（应用登录用户下占键/完成/复用/attempt 唯一、在途→过期重占、失败重占与成功行/attempt 不可变、run_kind 与 result 约束、只读无权限/管理只读）；迁移清单与升降级往返测试更新为 0008。`make check`：1001 项通过（含新增）。

## 3. 未做 / 限制

- 生产装配：目前没有服务进程调用状态机，`PgExecutionStore` 的接线（每请求事务、身份注入后构造）随 M3 API/worker；本记录的证明在单元与集成测试层。
- `result` 含证据文本，属受限载荷：单独存储与加密（INV-OBS-03）随 M3 Trace 持久化，本表已在注释中标明。
- 落库时机：attempt 在节点结束后批量写入；进程在节点中途崩溃只留下 `running` 行，由失联规则（300 秒）接管。
- Skill 执行（记录 55）尚未接同一账本：`SkillRegistry.execute` 已生成 operation key，落库接线与 M3 一起做。

## 4. 自审（§9）

- 数据库约束由迁移与集成测试证明（4.2 末段要求）；无应用层"先查后写"的竞态路径。
- 单元测试覆盖"重试不重复副作用"（第二次运行模型与检索调用数不变）与"回放隔离"（键不同、run_kind 不同）。
- 未触碰已冻结数据集、`.env`、生产数据库（集成测试用一次性数据库）。

## 5. 进度

- M2-03 已实现（生产接线与载荷分离登记为 M3）。P0 加权进度 43.0%（34.0/79）；按 99 项计 34.3%。分项：M0 10/11、M1 16.5/21、M2 7.5/16、M3 0/13、M4 0/10、M5 0/8。
