# 记录214：AGENT-04 持久取消、租约与步数写入边界

日期：2026-10-16；实现者/自审核者：Codex，同一模型自审，不是第二独立人工。

任务：AGENT-04；Goal：在保留 RAG、Harness 和真实模型决策循环的前提下，实现有界、可停止、可追溯的 PV Agent。

状态：实现后进入 REVIEW，缺陷修复复测后八项工程自审通过；本切片DONE，AGENT-04整体IN_PROGRESS。

## 1. 开始依据与范围

开始前工作区/暂存区干净，基线 `a9da1bbd28d8ef75d939bf51f754251ccf9ed474`。已读 CURRENT_TASKS、阶段规则和现有 Skill 租约、AgentLoop/工具/共享预算；ARCH-04/11 和 AGENT-01/02/03 前置保持。

按台账推进“持久取消/租约/原额度恢复”，本轮主切片限定为：**真实 PostgreSQL 持久取消、随机持有权与代数、不可重置的原截止时间/决策计数，以及接入现有物理调用守卫的装配辅助。** 完整预算/规划/最终阶段恢复仍待后续，不把领取新租约称为恢复成功。

无新目标、验收幅度或付费范围变更，不需新增 ADR。没有默认生产 Driver、HTTP/MCP 接口、自动续跑或模型费用；本轮不迁移正式本地库，不发布策略。保留原7动作/8步、12000 input+output Token、600000微USD和125秒。

## 2. 改动与设计依据

| 边界 | 改动 | 原因 |
| --- | --- | --- |
| migration 0027 | 新 metadata-only `agent_run_control`、触发器、部门 RLS 和最小表权限 | 旧 tasks 是单次 Skill 的重新执行，不等同 Agent 原运行恢复；原表不改 |
| PgAgentControl | fresh create、claim/renew/cancel、原子消耗一步、调用前持有权检查、同事务 fence | 进程内 flag 不能跨 worker/重启保持；旧 worker 不能覆盖新持有者 |
| agent_lease_guard | 沿用 call_scope 的继承式 before_call，独立短连接检查并关闭 | 保护嵌套实际模型调用，不把数据库事务跨供应商请求持有 |
| 测试与入口文档 | 真实临时 PG、并发/锁等待、离线实际 AgentLoop、迁移往返及原回归 | 验证可运行行为和失败路径；不使用测试通过冒充真实回答质量 |

事实库绑定复用现有 `FactDatabaseBinding`，实际连接仍逐次比对；应用角色不读取受限事实库身份表。用户/权限变化通过当前目录和原事实写栅栏核验。新表只含 UUID、principal、部门、trace/context 摘要、时间、计数和租约；无正文、证据、Prompt、答案和密钥。

持久计数只保存已消耗决策，不保存完整 LoopCheckpoint；不改变当前循环拒绝非全新执行的规则。随机租约 ID 与递增代数是 worker 写入凭据，不是新预算或新业务执行授权。

## 3. 错误、修复与复测

1. 首轮真实 PG：31 failed、15 passed。实际错误原文：`psycopg.errors.InsufficientPrivilege: permission denied for table fact_plane_identity`。原因是新代码错误假设应用连接可直接读受限启动身份表。修复：沿用管理员启动时产生的事实库 UUID/连接绑定，应用端只核对可读连接身份；**未增加该身份表权限**。
2. 首次测试 fixture 把 fact_database_id 以字符串放进 model_copy，出现 `PydanticSerializationUnexpectedValue(Expected uuid...)`。修为使用原绑定返回的 UUID，不压制 warning。
3. 初次 lint 报 `B023 Function definition does not bind loop variable expected`。同步断言实际立即执行，但仍将 expected 显式绑定为 lambda 默认参数，避免未来延迟执行风险。
4. 后续定向出现 `NameError: name 'binding' is not defined`，1 failed、45 passed；为测试助手批量改签名时漏掉的最后一处。修为显式使用当前测试的启动绑定，再跑46 passed。
5. 新增调用途中取消/换租者的已知/未知费用反例，并补并发相同步数、直接 SQL 部门 RLS/管理员只读、错误连接绑定。控制/迁移组合51 passed。完整门禁发现旧RLS清单漏项，随后补齐并复测，见下文。

这些失败日志保留在 `.local/audit214/`，不提交包含本机服务配置的私有产物。没有把基础权限错误通过扩大权限、跳过 PG 或放宽断言解决。

6. 首次完整门禁：`test_group_roles_login_users_and_forced_rls`报 `Extra items in the left set: agent_run_control`，1 failed、3055 passed、70 skipped、1旧warning。原因是新增表已正确强制RLS，而旧完整清单漏了该表。只补精确清单，保留全部原断言；控制/迁移/RLS复测92 passed。
7. 补清单时手写缩进漏了4空格，format gate报 `unformatted: File would be reformatted`，在测试前退出2；用ruff format修复该行，再完整门禁。失败与格式轮日志独立保存，不覆盖。

## 4. 验证与可复现性

在仓库外等价 worktree、原锁定环境执行，避开本机 iCloud Git 对象占位；773份维护输入先对照基线 SHA，解除继承的 DEBUG 值，PG/Redis 为 required。命令均退出情况据真实日志回填：

```sh
env -u DEBUG venv/bin/python .local/audit214/run.py control-final tests/integration/test_agent_control.py tests/integration/test_migrations.py
env -u DEBUG venv/bin/python .local/audit214/run.py targeted-final tests/integration/test_agent_control.py tests/integration/test_migrations.py tests/unit/application/test_agent_loop.py tests/unit/infrastructure/test_execution_budget.py
env -u DEBUG venv/bin/python .local/audit214/run.py rls-fixed tests/integration/test_agent_control.py tests/integration/test_migrations.py tests/integration/test_rls.py
env -u DEBUG venv/bin/python .local/audit214/run.py gate-final
```

私有 run.py 只提供隔离 worktree 与本机测试服务参数，pytest 的公开测试文件与 make check 是提交内容。临时数据库升级 head、降级 base、再升级；正式库无 DDL/DML。

当前已验证：原 AgentLoop/预算组合114 passed（增加最后3个反例之前）；新控制/迁移组合51 passed（36个新增反例及15项迁移回归）。最后调整短租约测试等待，使 CI 调度抖动不会在消耗第一步前过早失租，已随最终全量复测通过。最终required全量3056 passed、70 skipped、1原warning，退出0。mypy365模块、架构365模块0违例/2原允许边、静态断言306文件0违例均通过；旧安全/评测warning保留。70个skip来自未提供/未连接专用扩展服务器的DEC-001候选B/C可选实验；当前已选D、主PG/Redis和本轮新增36项均实际执行，无跳过。773维护输入中771保持、2原测试仅增清单/迁移head、新4共777；旧生产代码/36Schema/冻结数据/旧迁移保持，144任务ID及其他状态不变。最终文档自审14路径、144任务ID、322链接/7锚点通过；发布收据按实际最终SHA另核对。

## 5. 八项自审核

| 项目 | 判定 | 证据及限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 实现真实PG取消/租约/决策写入边界，不冒充预算恢复或完整Agent；原七动作/8步/额度/绝对截止、数据集和采用门保持 |
| ADR与阶段硬门 | 通过 | 按已同意PLAN-02/ADR-0012及AGENT-04实现，ARCH-04/11保持；无目标/阈值/默认模型/生产批准变更，无需新增ADR |
| 正确性与失败路径 | 通过 | 临时PG验证跨连接取消、回滚、重复创建/步数、旧持有者、锁后重验时钟、取消与提交排序、版本/身份变化及调用途中失败；首轮权限错误和清单遗漏先失败后修复测 |
| 权限与数据 | 通过 | 新metadata表部门RLS+应用principal/context过滤；新表最小角色权限显式登记，旧ACL/身份表权限不改；复用可信启动绑定并逐次核对连接，不保存正文或密钥 |
| 预算/取消/副作用 | 通过 | 原预算/最终阶段代码字节保持，真实循环离线验证已知正费用与未知保守费用不丢，取消/失租后不再推进；未实现恢复、无新额度、0托管调用/0USD，正式库无DDL/DML |
| 追溯与版本 | 通过 | 原UUID/trace/context摘要/绝对时间/步数与租约代数可读；0027显式新表迁移，原Prompt/Skill/工具版本及Schema字节保持；不声称已有完整LoopCheckpoint/生产Driver |
| 验证充分性 | 通过 | required全量3056/70/1、92项控制/迁移/RLS定向通过；原安全清单断言未放宽，36公开Schema与冻结数据保持；不能代替真实质量/并发容量/盲测 |
| 状态与文档 | 通过 | 本切片DONE、AGENT-04整体IN_PROGRESS；原144任务ID/其余状态及前置保持，控制契约/入口/限制一致；正式三库只读核对仍0026，未迁移/重启/部署 |

## 6. 已知限制、回滚与下一项

- 控制层已有可调用实现；生产 Driver/worker/API 尚未装配，没有可对外演示的新增取消按钮。
- metadata不包含完整预算、在途调用、已知/未知费细节、规划板、观察、重复指纹和封闭最终阶段槽位。不能据此恢复原循环；原拒绝恢复条件和最终阶段封闭逻辑字节保持。
- 调用前检查和网络发送有时间窗口；已发请求不承诺撤回/恰好一次。已知/未知费用均留账；新持有者不能据此免费重试。超时异常可能先于下一次持有权检查成为本次 stop reason，取消/失租事实仍存于数据库。
- fence 与取消按数据库事务顺序生效，不能撤回先提交的材料。真实事实/最终业务校验仍须同事务完成；本轮未写 completed。
- 新表部门 RLS＋可信应用 principal 过滤，权限模型与现有服务一致，不声称对已泄露应用写凭据提供完整 principal 隔离。运维所有者仍可信。
- 正式本地三库仍0026；0027仅临时测试库执行，未部署/重启。metadata保留/删除与材料加密/审计在AGENT-06收敛，当前不存真实业务正文。
- 生产回滚须先停止新运行并保留控制记录；不得直接 downgrade 丢掉取消/步数。本轮仅临时环境可往返0027/0026。代码按本轮功能提交逆序回退；共享/外部改动不覆盖。
- 下一主切片：原预算/在途费用及最终阶段状态的持久检查点与恢复协议，然后接真实 Driver。完整初始最终预留与 AGENT-05 实际门共同推导；不引入未经批准的默认数值。

当前无新增需所有者裁决事项。托管质量实验、盲测独立保管、生产发布仍各自按原授权/证据办理。本轮实际投入、门禁等待和返修见机器结果与私有日志；没有完成付费试跑，不能据此重估真实可完成率或宣称S2完成。

## 7. 本轮交付核验

预定按数据库控制、调用守卫、反例测试、控制契约、台账自审五组提交。每组只暂存审核路径；提交/根目录/等价树逐字节比对后推送，远端CI按实际最终SHA核验。提交不等同部署、真实质量、独立人工复核或AGENT-04整项完成。
