# 实现记录 78：进程级故障演练（M3-13 收口）——真实进程、真实库、可切换的供应商代理

- 日期：2026-09-25
- 授权：记录 74 C「M3 收尾清单」（决策人 2026-09-25「同意」），预算约 0.1 美元
- 范围：`evals/harness/tools/chaos_run.py`（新）、运行 `evals/harness/runs/2026-09-25-chaos-v1`（两轮：`report.run1.*` 与 `report.*`）、由演练引出的两个服务改动（数据库连接快速失败、worker 循环守护）与 worker 的 `--lease` 参数
- 前置：记录 61 用进程内假部件做了 5 个故障用例并把 M3-13 记为部分；本记录把同类故障放到真实进程上，并新增网络层与数据库层的故障

## 1. 方法

被测对象与记录 77 相同：`medops.api.serve`（MPS）、`medops.worker.serve`、medops_v2、记录 67 的合成签发方。三类注入手段：

- **供应商代理**：工具进程内起一个 HTTP 代理，API 以 `OPENAI_BASE_URL` 指向它。`pass` 模式原样转发到 OpenAI（授权头只经过本进程内存，不落盘不打印）；`blackhole` 收下请求后不回应（真实的连接级超时）；`http_503` / `http_429` 立即返回对应状态（429 的 body 是 `insufficient_quota`，与 9 月 24 日两次余额耗尽时的真实响应同型）。
- **数据库**：管理连接上创建 `before insert on traces` 的触发器抛异常（审计存储中断）；`docker pause / unpause medops-postgres`（数据库整体不可达）。
- **进程**：SIGKILL 正在执行任务的 worker，再起一个 worker（租约接管）；两个 worker 同时消费 4 个任务（重复消费）。

每个场景记录记录 61 的三件事：**可定位**（trace span 的 error_code、task_attempts、escalations 行）、**可恢复**（故障解除后同一请求在同一进程里成功）、**安全链不被绕过**（失败响应里没有 claim、拒答在任何模型调用之前、没有无审计回答、任务只执行一次）。

## 2. 第一轮（工具与服务改动之前）：7/8 通过

| 场景 | 结果 | 事实 |
| --- | --- | --- |
| 代理直通基线 | ✓ | answered，1 条陈述，3 次供应商调用（回答 + 判定） |
| 模型真实超时（blackhole） | ✓ | answer 节点 attempt 1 `timeout dependency_timeout`（60,003 ms），随后两次重试即失败；升级 `system_failure`，`answer` 为空，escalation 行 open；黑洞期间高风险问句仍 `refused high_risk_medical` 且供应商 0 次调用；切回 pass 后同一问题 answered |
| 供应商 503 | ✓ | 三次 `retry/failed dependency_unavailable`（各 2 ms）→ 升级；恢复后 answered |
| 供应商 429 insufficient_quota | ✓ | 同上：429 被映射为可重试的 `dependency_unavailable`，三次后升级，无回答 |
| 审计存储中断（触发器） | ✓ | 模型已被调用 2 次（回答 + 判定），但响应是 **503 `audit_unavailable` retryable=true、无 claim**，`traces` 没有这条记录；触发器删除后同一问题 answered；触发器与函数确认已清理 |
| 数据库暂停 | ✓（有发现） | 暂停中 `/readyz` 503；`/v1/ask` **挂起直到客户端 45 秒放弃**（`ReadTimeout`），供应商 0 次调用；恢复后 `/readyz` 200、同一问题 answered。见 §4.1 |
| worker SIGKILL 后接管 | ✓ | `task_attempts`：(1, worker-6ac8af0b, lost)、(2, worker-c446fd67, completed)；接管发生在 kill 后 29.1 秒（15 秒租约 + 新 worker 20 秒模型加载）；任务 completed，任务 trace 恰 1 条（被杀 worker 死在检索阶段，尚未写 trace） |
| 双 worker 恰好一次 | **✗（配置引出的真实行为）** | 4 个任务都 completed，但 1 个任务有 2 次 attempt。见 §4.2 |

费用 0.045 美元。

## 3. 第二轮（修正后）

代理直通基线通过后，8/8 场景通过（`report.md` / `report.json`），费用 0.041 美元：

| 场景 | 故障期间 | 可定位 | 恢复后 |
| --- | --- | --- | --- |
| 模型真实超时（blackhole） | 183 秒后 `escalated system_failure`，无 claim；期间高风险问句 0.05 秒 `refused`，供应商 0 次调用 | answer 节点 3 次 attempt 全部 `dependency_timeout`（各 60,00x ms）；escalation 行 open | 同一问题 answered |
| 供应商 503 | 2.9 秒 `escalated system_failure`，无 claim | 3 次 `dependency_unavailable`（2–5 ms）；供应商恰 3 次调用 | answered（7.1 秒） |
| 供应商 429 insufficient_quota | 2.8 秒，同上 | 同上 | answered（6.1 秒） |
| 审计存储中断（触发器） | **503 `audit_unavailable`，retryable=true，无 claim**；模型已调用 2 次但 `traces` 无此行 | 响应码本身；触发器与函数确认清理 | answered（6.7 秒） |
| 数据库暂停（容器） | `/readyz` 503；`/v1/ask` **5.05 秒即 503 `dependency_unavailable`，retryable=true**（第一轮是挂到客户端放弃）；供应商 0 次调用 | 响应码；连接超时 5 秒 | `/readyz` 200，answered（6.6 秒） |
| worker SIGKILL 后接管 | 被杀 worker 的 attempt 1 记 `lost` | `task_attempts` (1, worker-005a6cfc, lost)、(2, worker-1c06cf59, completed)；kill 后 31.3 秒接管；任务 trace 恰 1 条 | 任务 completed |
| 双 worker（180 秒租约） | 4 个任务、2 个 worker | 每个任务恰 1 次 attempt，全部 completed；两个 worker 都有份 | — |

第一轮与第二轮的差别只有两处，都由 §4 的处置解释：数据库暂停从「挂起」变为「5 秒 503」，双 worker 从「1 个任务 2 次 attempt」变为「每个任务 1 次」。

## 4. 发现与处置

### 4.1 数据库不可达时请求挂起（已修）

`ProductionRuntime.connection()` 之前用不带超时的 `psycopg.connect`，数据库暂停时请求线程一直等到客户端放弃；如果客户端不放弃，anyio 线程池会被这类线程占满。处置：每个运行时连接带 `connect_timeout`（`DB_CONNECT_TIMEOUT_S`，默认 5 秒）与 `statement_timeout`（`DB_STATEMENT_TIMEOUT_MS`，默认 30 秒），连接失败映射为 `dependency_unavailable`（503，可重试，detail 只含异常类名）；worker 主循环捕获该错误、记录警告后继续轮询而不是进程退出（`--once` 下返回 1）。单元测试 `tests/unit/api/test_runtime_connect.py`（真实拒绝连接 → 503 映射；连接参数）。第二轮的数据库暂停场景据此改为要求「快速 503」。

### 4.2 租约短于执行时间 = 至少一次而不是恰好一次（设计行为，已记录）

第一轮双 worker 场景用的是 15 秒租约（为 SIGKILL 场景设的短租约），而 CPU 上一次 label_query 要 18–22 秒：任务 fc19024c 的 attempt 1 执行到第 15 秒时租约到期，另一个 worker 按设计接管（attempt 2），Skill **完整执行了两次**（两次模型调用与两条任务 trace），先到期的 worker 稍后汇报时被 `complete()` 拒绝（attempt 1 记为 lost），任务结果只有一份、状态只 completed 一次。这正是记录 59 的语义：队列保证的是「结果不被覆盖、副作用不重复（operation key 账本）」，不是「不重复执行」；生产租约 300 秒 > Skill 上限 120 秒，正常情况下不会触发，但机器被挂起（记录 77 §6.2 的合盖睡眠）或严重过载时会。两点处置：`DEPLOY.md` 写明 `--lease` 必须大于最长 Skill 执行时间；第二轮的双 worker 场景用 180 秒租约，测它本来要测的「两个消费者、每个任务只被一个拿到」。登记后续：worker 在执行期间续租（heartbeat）可以把「至少一次」收紧到「除非 worker 死亡否则恰好一次」，随 M4 的任务量再决定。**决策人 2026-09-25 答复：按建议——接受至少一次语义，续租随 M4 任务量再定。**

### 4.3 其他观察

- 记录 77 §6.2 里 Wi-Fi 断开造成的 14 个 `system_failure` 是一次未经安排的真实供应商中断演练：结论与 blackhole / 503 场景一致（无回答、可定位、无需重启即恢复）。
- 代理在 blackhole 模式下会收到 SDK 放弃后的连接重置（第一轮日志里的 `ConnectionResetError` 回溯来自工具的代理线程，与被测服务无关）；第二轮已吞掉。
- 升级记录只写「answer: ModelUnavailable」，看不出是 429、连接错误还是 5xx（记录 77 §6.3 已登记）。

## 5. 未做 / 限制

- 没有 Redis 唤醒，因此没有 Redis 重复投递用例（同记录 61）。
- 数据库暂停只测了 API 路径；worker 在数据库暂停期间的行为（记录警告后继续轮询）只有单元级证明，没有在演练里跑。
- 没有测 API 进程被 SIGKILL 时的客户端行为（无状态进程，由部署层重启）。
- 合成签发方、单部门；与记录 67 相同。

## 6. 自审（§9）

- 每个场景的三件事都由数据库行或 HTTP 响应证明，不靠日志判断；工具把判据写死在代码里。
- 触发器、函数、容器暂停都在 `finally` 里恢复，并在报告里记录「是否残留」；本地 medops_v2 只增加了审计 / 任务行。
- 费用两轮合计约 0.09 美元，在预算内。
- 服务改动（连接超时、worker 守护）只影响故障路径；`make check` 通过。

## 7. 进度

- M3-13 部分 → **已实现**（记录 61 的进程内用例 + 本记录的进程级用例：模型超时、供应商中断、worker 死亡与接管、重复消费、审计中断、数据库不可达，均证明可定位 / 可恢复 / 不绕过安全链；演练随部署对象重跑）。
- P0 加权进度：60.1% → **60.8%**（48.0/79）；按 99 项计 48.5%；M3 10.5/13。
