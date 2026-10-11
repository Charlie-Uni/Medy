# 实现记录 177：任务租约、执行期限与持有权

## 0. 本轮范围与状态

- 日期：2026-10-11，Australia/Sydney。主切片 **ARCH-05**，关联 OPT-11 与任务幂等；ARCH-01/04/11 工程前置已通过。
- 实现与自审核者：Codex 本轮实现者；没有第二独立人工，没有委托子 agent。起始 HEAD `5a604050b9c0706bfd823685e5befcb9619d64a6`，78 个已有未提交文件已备份；保留以前各轮工作。
- 本轮工程自审通过：最终全量 **1857 passed / 70 skipped / 1 warning，52.34s，退出 0**；491 个维护输入与核验工作树 SHA 一致、0 不符，忽略的两份测试配置也一致。机器证据见[177-results.json](2026-10-11-implementation-177-results.json)。台账已按 IN_PROGRESS→REVIEW→DONE 回填。
- 托管模型调用 **0**，费用 **0 USD**；真实数据库测试使用供应商替身与合成任务，合成账本金额不是实际供应商费用。未新增迁移、未升级业务库、未重启部署、未提交/推送。
- 不更改冻结数据/gold、评分分母/阈值、默认模型、ACL/RLS、安全规则或生产指针；本轮不实现 Agent/模型自进化，不开展真实质量或性能试跑。

## 1. 原问题、预先反例与历史依据

[架构审查 AR05](2026-10-10-architecture-audit.md)指出原默认 lease 300s 与重试名义 360.6s 不一致，任务执行没有续租，完成被拒也没有处理。ARCH-01 已把重试改成同一节点总期限，ARCH-11 又引入共享期限，因此“当前仍会等 360.6s”不再成立。本轮在当前代码上确认仍有以下实际缺陷：

1. PostgreSQL 与内存存储完成写入仅检查 owner/attempt，没有检查租约是否过期；即使尚无第二 worker，失去时间持有权的结果也能落库。
2. TaskRunner 忽略 complete/fail 返回 false，最后 get 可能读取接管者的结果，并以当前 worker 的完成返回；日志也记为 task finished。
3. 调用前没有检查任务持有权，费用预留等待期间失租仍可能进入供应商。
4. PostgreSQL 领取先批量更新所有过期 attempt，再 SKIP LOCKED 领任务，可能提前改变未实际接管的旧尝试；排队任务耗尽 max_attempts 的处理也与内存不同。
5. 内存存储用 `"result" in fields` 判断 attempt 完成/失败，而 fail 也传 result=None，所以失败被标 completed；并发测试存储未加锁。

在实现前添加两个反例运行，退出 1，**2 failed / 0.37s**。真实 pytest 原话：

```text
E   AssertionError: assert True is False
E   AssertionError: assert 'completed' == 'failed'
2 failed in 0.37s
```

分别对应过期租约完成返回 True、失败尝试错误写成 completed。没有真实模型调用。

## 2. 设计与为什么这样处理

### 2.1 用有界执行覆盖租约，不加心跳续租

当前 SkillSpec 最大期限 120s，重试已经共享总期限；默认 lease 300s 足够。保留现有默认和 profile，通过 `deadline = claim_start_monotonic + lease − min(5s, 10% lease)` 留出收束余量，并按 claim_start 同时计算原 Skill/profile 更短期限。领取/连接/等待提交/身份及依赖装配均消费这份时间；profile 在装配时确定后按已消耗时长缩短，过期即拒绝，不会从 handler 开始才重新计时。短租约演练会同步缩短执行体。

这是一项执行保护，不是新的性能目标。余量不保证网络、数据库清理总能在 5s 完成；如果收束越过租约，最后写入必须按失租处理。未来长时间 Agent 若需不断续租，要按新 profile 与恢复契约另做，当前没有用永久心跳无限延长一个卡住的任务。

### 2.2 数据库时钟与结果栅栏

生产 TaskRunner 不注入 wall-clock 时间；PgTaskStore 用 `clock_timestamp()` 判断领取、持有权和完成。显式 now 只用于确定性测试，不会由 API/Skill 入参设置。单进程总期限用 monotonic，避免机器时钟调整延长主体。

领取按 task 行锁→旧 attempt→新 attempt 顺序，`FOR UPDATE SKIP LOCKED` 跳过其他事务锁住的任务；只更新本次实际接管任务的旧 attempt。完成先取得当前 task 行锁，随后重新检查数据库期限。只在 UPDATE 谓词中检查时间不充分：谓词可能在等待一个未改变的被锁元组之前已经计算。

持有权是 `task_id + worker + attempt + 未过期 running`。复用同一 worker 名称也不能越过 attempt 栅栏。失租只更新原 attempt 的 outcome/trace/error_code，保留已有 takeover finished_at，不更改现任任务结果；无法记录失租则抛 audit_unavailable，不把缺记录当作成功。

### 2.3 付费调用与嵌套上下文

现有 call_scope 增加继承的 before_call 栅栏，子 Skill/Harness/翻译线程不能用新 scope 删除父任务检查。共享执行准入前检查；BudgetedGateway 在月度预留等待后、实际调用前再次检查，并按剩余总时间刷新供应商 timeout。独立短事务不复用长业务连接，也不让多个线程共用同一 psycopg 连接。

确定没有进入供应商的拒绝/失租回执为 not_started、费用 0，已预留金额按原账本结算释放。已经成功或 usage 未知的调用继续沿用 ARCH-04/11 的已知/保守费用，失租不会退掉已经发生的金额。

### 2.4 任务状态与本 worker 尝试状态分开

`TaskExecution(task_id, attempt, trace_id, outcome, record)` 报告本次尝试。outcome 只有 completed / failed / lost；lost 的 record=None，不返回新 worker 的状态。公开 TaskResponse/TaskStatus 不变，仍显示当前任务。worker 日志/Span 带 attempt 与失租 outcome，不伪装完成。

Trace/run 按 attempt 独立；回执的 attempt_id 保持 `task:<task_id>:<attempt>/<operation_key>:<node_attempt>`，原稳定 task_id 连接这些尝试。单执行额度当前按 attempt 重新建立，整个任务生命周期并不是已实现的同一持久预算。

## 3. 改动范围

| 范围 | 改动 |
| --- | --- |
| application/tasks.py | 有界租约主体、deadline-aware 装配、独立持有权检查、TaskExecution、失败/失租记录与费用 Trace、内存锁及 failed attempt 修复 |
| infrastructure/db/tasks.py | 数据库时钟、原子领取、仅接管项的 lost、max_attempts 一致、锁后期限重验、record_lost 防错身份/Trace覆盖 |
| llm/accounting.py | 父 scope 栅栏继承；原调用身份/回执形状保持 |
| llm/execution_budget.py、budget.py | 执行准入前及月度预留后持有权检查、timeout 更新、尚未调用零费用 |
| worker/serve.py | lost 日志与独立 attempt 报告；lease/poll 拒绝零、负数、NaN、Infinity |
| 单元/故障/API/PG 测试 | 旧正常路径按新内部返回契约读取 record；新增过期、嵌套线程、两 worker、真实行锁、已知/未知费用及 CLI 回归 |
| DEPLOY、LLM_ACCOUNTING、CURRENT_TASKS | 当前保护、短租约语义、强制停机接管、费用累计、有限保证与下一步骤 |

无需新数据库结构或公开 Schema 迁移。复用 tasks/task_attempts 和 0023 调用账本；不删除原版本记录或历史实验。

## 4. 实施、自审发现的失败与修复

| 失败/发现 | 原因、修复与复验 |
| --- | --- |
| 原 2 条反例失败 | 期限未作为完成条件、内存按 result 字段存在与否判断 → 补期限/正确状态 → 定向通过 |
| 首个 patch 原子拒绝 | 猜测 budget.py 导入行未匹配真实代码；没有半写入 → 读取实际导入后分段编辑 |
| 新 PG 两 worker 测试 19 passed / 2 failed，4.72s | 应用角色直接 SELECT llm_spend_reservations 得 InsufficientPrivilege；这是既有权限有效，不扩大权限 → 测试只把账本回读改为临时库 owner |
| 下一轮 116 passed / 2 failed，6.84s | 临时库 fixture 的 owner DSN 键是 owner，测试误用 dsn 得 KeyError → 按已读 fixture 修正 → 126 passed / 7.36s |
| 自审发现等待行锁期间期限可能失效 | 时间谓词可能先计算后等锁 → 先取得行锁，再执行期限更新 → 实际锁等待/过期 SQL 回归通过 |
| 首轮全量退出 2，mypy 1 error，pytest 尚未运行 | reason_codes 初值被推断成固定长度 tuple[str]，后来赋可变长 tuple[str, ...] → 显式声明 tuple[str, ...] → 类型检查通过 |
| 自审发现依赖装配可能不消费 Skill/profile 总期限 | deadline 原先只提前限制 lease，Registry 再从执行时计 Skill 时间 → 从领取开始同时限制 Skill、已确认 profile → 两个短时限装配反例与最终范围 31 passed / 5.73s |
| 中间全量退出 0，但 1835 passed / 92 skipped / 1 warning，54.53s | 核验工作树漏带忽略的 .env.dec001，BM25 候选 D 22 项没跑；新增单元 22 项已跑，不是缺执行 → 单独 -rs 查明原因、复制相同配置 → 最终重新跑门禁，不能据中间绿灯标 DONE |
| 自审发现失租记录也不能忽略返回值 | record_lost 若拒绝应显式 audit_unavailable → 增加拒绝处理；lost 仍不暴露接管者结果 |
| 阅读时猜错 connection/test 路径 | 只读工具错误，不是服务/编译故障；用 rg 定位实际文件，未新增转发壳 |
| 收尾文档脚本出现 Non-UTF-8 SyntaxError | stdin 中非 ASCII 字节解析失败，脚本未执行、没有半写入 → 改用 apply_patch 与 ASCII 转义脚本 → 最终文档及链接核验通过 |

新增测试尚未使用第二独立人工或真实供应商质量判断。定向失败均保留，修复后才报告通过。

## 5. 验证

- 初始修复含 PG 原任务回归：32 passed，3.07s。
- 扩展定向命令：`env -u DEBUG PYTHONPATH=src:. venv/bin/python -m pytest tests/unit/application/test_tasks.py tests/unit/application/test_task_lease.py tests/unit/faults/test_main_chain_faults.py tests/unit/api/test_task_routes.py tests/unit/infrastructure/test_execution_budget.py tests/unit/infrastructure/test_llm_gateway.py tests/unit/infrastructure/test_llm_call_receipts.py tests/unit/skills/test_registry.py tests/unit/harness/test_deadline.py tests/integration/test_tasks_store.py tests/integration/test_llm_call_receipts.py -q`。
- 定向结果：**126 passed，7.36s，退出 0**；日志 `.local/arch05-directed.log`。PG 使用临时迁移库与真实应用角色，最终只用 owner 读受限账本；没有给运行角色加权限。
- 两真实 worker 用供应商替身完成正常 usage / 超时无 usage 两种接管：原尝试 lost、新尝试 completed；新结果不变、原费用保留、两份 Trace 与两份 durable receipt/账本金额相符；超时无 usage 保守收费，没有第三次供应商调用。
- 最终边界定向：`pytest tests/unit/application/test_task_lease.py tests/integration/test_tasks_store.py -q`，**31 passed / 5.73s，退出 0**；包含装配消耗 Skill/profile 的两个反例。
- 最终全量：`env -u DEBUG PYTHONPATH=<worktree>/src:<worktree> make check`，**1857 passed / 70 skipped / 1 warning，52.34s，退出 0**；463 文件格式检查、195 源文件 mypy、lint、安装检查、4 集数据审计与公开 Schema 漂移均通过。
- 70 skipped 是既有 B/C 可选环境缺失；BM25 候选 D 的 22 项已执行，真实 PG/Redis 必需集成已执行。唯一 warning 来自认证反例刻意使用短 HMAC 密钥。第二人工 pending、unmappable gold=2、历史安全集与无新未见盲测的审计警告继续保留。
- 核验工作树 `/Users/leaf/.cache/medy-checks/arch05-verified-2nwqwl6t` 是注册 detached Git worktree；日志 `.local/arch05-check.log`。491 个维护输入与原目录 SHA 一致、0 不符；.env/.env.dec001 一致但不提交、不输出密钥。中间失败与缺配置日志保留。

## 6. 强制自审核（工程范围通过）

| 检查项 | 当前结论 |
| --- | --- |
| 需求/范围 | 通过：ARCH-05 执行/持有权/尝试/费用范围；未以新 Agent 壳替代后续目标 |
| 正确性/失败路径 | 通过：原反例、过期未接管、同名 worker、锁等待、max_attempts、晚到结果、装配超时和已知/未知费用接管已验证 |
| 权限/数据 | 通过：生产权限未扩大，公开 Schema/冻结数据/模型/安全不改；PG 账本拒绝保留 |
| 预算/取消/副作用 | 通过（当前只读 Skill 范围）：0 托管调用；失租拒绝新调用、已发出费用保留，主体期限不超 lease；外部恰好一次与任意代码瞬时终止未保证 |
| 追溯/版本 | 通过（尝试范围）：旧 attempt 绑定自己的 Trace，调用回执按 task/attempt 分组；完整内部证据与载荷仍归 ARCH-06/07 |
| 验证充分性 | 通过（工程范围）：126 项定向、最终 31 项边界反例、1857/70 全量，实际 PG 锁/应用身份/BM25 D/Redis 已跑，491 输入 SHA 一致；质量/性能/供应商账单未重测 |
| 状态/文档 | 通过：READY→IN_PROGRESS→REVIEW→DONE，仅 ARCH-05 状态改变；141 任务 ID 全部保留，下一项 ARCH-02。README/计划/阶段/部署/费用与场景进展同步；原 78 个未提交文件无丢失，66 个不变、12 个本轮明确重叠 |
| 独立复核/阶段 | 通过：明确本轮仅实现者自审；不据此宣称 S2/S3 或原整体质量门通过 |

## 7. 限制、回滚与下一项

1. deadline 是协作式；原 ARCH-01 的 async I/O/进程推理保护继续使用。领取前的数据库连接等待不保证整个 run_once 在一个 lease 内返回；领取后的迟到操作不会继续付费或覆盖结果。结算/审计必要清理可能越过余量，失租与 pending 据实记录。
2. 持有权检查到发送之间存在进程暂停窗口；已发送请求无法撤回。强制停机/未知响应接管可能产生两次供应商费用，已知或保守金额分别保留，不能声称外部恰好一次。
3. current Skill 为读取/判断；未来业务写入工具需要另有事务栅栏/幂等契约。新增 Agent 的持久预算与历史恢复仍未实现。
4. 单 attempt 预算与 task 生命周期预算不同；默认最多 3 次领取，月度账本累计保护仍在。0.60 USD 不是整个任务硬账单上限，不据此自动批准实验重跑。
5. 失租发生在依赖装配前时可能没有业务 Trace，attempt 仍保存 trace_id/lost，零调用无费用；硬崩溃无法补写 Trace，已有 durable receipts 仍可关联，完整审计补齐待 ARCH-06。
6. 新增持有权短查询会有额外开销；真实 P95、容量、质量未重测。新代码尚未重启到常驻服务。
7. 只按本轮备份恢复重叠文件与新增测试，不整树 reset。备份 `/var/folders/zj/6djhy_4x7vx_7t8xcgt_v62c0000gn/T/medy-arch05-7h1y1spg`；无需降级数据库，保留先前 0023、ARCH-04/11 及设计工作。
8. 下一主切片 **ARCH-02：修复 Skill/Replay 历史输入传递与查询一致性**；PLAN-02 剩余动作/profile 与验收契约继续有效，原生产 +5pp 决定仍待答。本轮无新增人工问题或费用请求。
