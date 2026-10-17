# 记录215：AGENT-04 显式冻结后的持久预算交接

日期：2026-10-17；实现者/自审核者：Codex，同一模型自审，不是第二独立人工。

任务：AGENT-04。Goal：保留原费用、在途预留、步数和截止时间，使PV Agent能够有界停止和安全交接。

状态：实现后进入REVIEW，修复复测后八项工程自审通过；本切片DONE，整项AGENT-04继续IN_PROGRESS。

## 1. 基线与范围

开始前工作区与暂存区干净，基线 `0f60d4b73e07e1159ad502328bd6f1f04c492cab`。按CURRENT_TASKS推进原预算/最终阶段状态的持久恢复。已读AGENTS、计划与阶段§3，核对214控制层、原预算/最终槽位、PLAN-02与现有数据权限；ARCH-04/11及AGENT-01/02/03前置保持。

本轮主切片：**冻结原根预算→PG持久写入→一次性领取→提交后重建原预算**。实现完整预算元数据与最终阶段的封闭保留，但不开放完整AgentLoop恢复；真实Driver、规划/观察/重复状态及任意崩溃write-ahead仍待后续。没有目标/阈值/默认模型/原ACL/生产批准变更，无需新增ADR；0托管模型调用/0USD。

## 2. 实现与依据

| 层 | 实现 | 约束 |
| --- | --- | --- |
| 原ExecutionBudget | 永久冻结、完整metadata捕获、内部重建、共用原snapshot构造 | 原路径不使用冻结时保持；late settle照常留费，不解冻原根 |
| 私有codec | 严格完整字段/版本、调用唯一与预留合计、最终槽位一致性 | 不能用公开Snapshot的兼容默认值补缺失字段；不含正文 |
| 0028/PgAgentBudget | 单次领取/递增revision、SHA、原控制fence、最小新表权限 | 原消费/ID/limits/原截止/最终封闭不可回退；缺失或已领拒绝 |
| bootstrap | 原run/步数/消费匹配、独立短事务、提交后才构造根 | 未确认提交返回无根；已有parent不能替换；持久化失败原根保持停止 |
| 测试支持 | 214真实PG控制fixture移入support复用 | 旧36个测试函数保持；不复制两份数据库身份/时钟供给 |

为什么不直接恢复四个AgentBudget汇总字段：它们不含活动/已结算ID、known/unknown差别、最终保护与精确槽位，直接赋值会丢失预留或重用调用。为什么先做显式交接：单纯周期快照不足以记录后续调用，崩溃回放会少算。先冻结使原根不再新增占额；未结算状态保留并停止恢复调用。

运行时预算v3、最终预算v1和原工具契约版本保持；新增私有交接版本`budget-checkpoint-v1+sealed-handoff`。原默认路径仅增加未启用的suspended检查，原snapshot构造抽为锁内共用函数；正常reserve/settle公式及调用/重试/价格保持，不增加隐藏重试。没有新增model action、公共API或MCP接口。

## 3. 失败、修复与复测

1. 首次patch因格式化后目标行不同，报`apply_patch verification failed: Failed to find expected lines`，未据此宣称完成。读取实际代码后按当前签名完成修改与格式检查。
2. 初次新增测试含单行try/with/if，lint报`E701 Multiple statements on one line`；ruff format展开并复查，全部通过，没有关闭规则。
3. 初轮定向1 failed、127 passed：`test_downtime_consumes_original_budget_deadline`在保存途中报`DeadlineExceeded: dependency_timeout`。原因是fixture只给0.15秒，尚未完成多次真实PG身份/fence检查就超时。改为1秒并在成功保存后等待1.05秒，仍严格验证停机耗尽原期限，未扩大原profile或运行预算。
4. 文档开启脚本经stdin出现一次`SyntaxError: Non-UTF-8 code`；未运行任何目标修改。改为ASCII转义数据传入后成功，实际仓库文档UTF-8正常，不修改业务编码规则。
5. 显式时钟复核发现按“剩余秒数”在解码后重新起表会多给解码耗时；实现改为提交前计算monotonic绝对点，重建直接绑定该点，保存/领取/提交/解码都不重新计满。最终按真实反例与门禁复测。

独立失败日志和命令收据在`.local/audit215/`，不提交本机服务配置/凭据/临时产物。实际投入未全程精确计时，测试/返修等待以机器elapsed为准；不能据此承诺整个S2/S3工期。

## 4. 验证

仓库外等价worktree、原锁定venv，777份原维护输入先SHA绑定；解除继承DEBUG，PG/Redis和当前已选D为required，B/C仍按原可选机制。公开复现为指定pytest路径及`make check`；私有run.py只装配服务环境和等价路径。

测试中的0.001/0.7 USD等金额是离线fake网关报告的机制数据，用于验证已知费用与超额不丢失，不是托管模型账单；实际托管调用与费用均为0。

```sh
env -u DEBUG venv/bin/python .local/audit215/run.py focused-final tests/unit/infrastructure/test_budget_checkpoint.py tests/integration/test_agent_budget.py tests/integration/test_agent_control.py tests/integration/test_migrations.py tests/integration/test_rls.py tests/unit/infrastructure/test_execution_budget.py tests/unit/infrastructure/test_finalization_budget.py tests/unit/application/test_agent_final_budget.py tests/unit/application/test_agent_loop.py
env -u DEBUG venv/bin/python .local/audit215/run.py mechanisms-final tests/unit/infrastructure/test_budget_checkpoint.py tests/integration/test_agent_budget.py
env -u DEBUG venv/bin/python .local/audit215/run.py gate-final
```

当前：241项原/新组合通过；最后43项机制反例通过，覆盖新Python进程领取、同revision并发、旧根停用、回滚/提交结果不确定、消费与步数错配、父预算替换拒绝、已知/未知/超额费用、真正inflight与late settle、PG最终槽位封闭、当前取消/租约/权限、严格缺字段/损坏/版本及短期限。最终required `make check`退出0：3099 passed、70 skipped、1原JWT短key warning；mypy368模块/架构368模块0违例2原允许边/静态断言309文件0违例通过。70 skip仍为无专用服务器的可选DEC-001 B/C，新增43项和required PG/Redis/D实际执行。原777输入中773保持、4预期修改、新7共784；旧公开36Schema、数据/门禁/既有迁移和其余生产模块保持。最终文档另核对。

## 5. 八项自审

| 项目 | 判定 | 证据及限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 实际实现冻结/PG单次领取/提交后重建，严格限定预算交接；非完整AgentLoop或任意崩溃恢复，原动作/步数/额度/期限与门禁不改 |
| ADR与阶段硬门 | 通过 | 沿用已获准PLAN-02/ADR-0012及原ARCH-04/11，未改目标/阈值/自动生产批准；没有付费实验或新增真实盲测声明 |
| 正确性与失败路径 | 通过 | 43新反例覆盖新进程、单次/并发、父根替换、旧根冻结、保存/提交失败与不确定、损坏/缺字段、过期/当前取消/租约/权限及最终阶段封闭；首轮时间fixture失败已修复复测 |
| 权限与数据 | 通过 | 新表metadata-only，显式最小新表权限与部门RLS；原principal/context/fact/步数fence保持；无正文/密钥、旧ACL/身份表权限不改 |
| 预算/取消/副作用 | 通过 | 完整原消费/known/unknown/pending/settled/保护/最终槽位保留；在途/active阶段停止、超额不裁剪，恢复一次且截止不重开；0托管调用/0USD、正式库无DDL/DML |
| 追溯与版本 | 通过 | 私有checkpoint-v1与实际state/SHA/revision/lease绑定；原预算v3/最终v1及Prompt/Skill/工具版本保持；原顶层调用/正常settle/公开模型AST一致，无完整轨迹恢复声明 |
| 验证充分性 | 通过 | required全量3099/70/1、241原/新定向和最终43机制通过，真实临时PG/独立Python进程；旧36控制测试函数及迁移/RLS原断言保持，36Schema/冻结数据不改；不代替真实质量 |
| 状态与文档 | 通过 | 18路径/144原ID及其他任务状态保持，八项自审通过；预算交接本切片DONE而AGENT-04整体IN_PROGRESS，后续Driver/完整检查点/write-ahead/对账及05/06前置未消失 |

## 6. 限制与下一步

- 这是显式冻结的预算层交接，不是任意崩溃恢复。已领根在再次冻结前消失，原image保持已领，拒绝重放；无检查点拒绝，不提供0预算回退。
- 有在途call时保留原reserved并`recovery_inflight`停止新调用，old root晚到费用照常留账；跨进程晚到回执对账尚未实现。对已结算usage未知保留原保守accounted，known仍为0。
- active最终阶段在image保留原状态，重建后封闭并停止；不自动续用余槽。原closed保持closed，实际超额不裁剪，blocked不清除。
- 费用/Token/limits/最终保护保留，期限取原run与原根较小者；以可信PG时钟和本进程monotonic绝对点计算。不承诺通用服务器时钟异常容错或供应商恰好一次。
- 当前循环仍拒绝非全新运行；尚无生产Driver/worker/公开入口。预算不是业务/权限授权，实际使用须原guard、当前事实与完整循环状态验证。
- 交接入口依赖可信执行者提供该run的原根；四个汇总字段匹配不等于完整调用归属证明。真实Driver仍需把根、原run和CallJournal/受限轨迹绑定，不能把本入口直接暴露为用户传入的恢复JSON。
- 只保存metadata，不存叙述/证据/Prompt正文；新表最小角色权限/RLS显式添加，旧ACL和身份表权限保持。受限材料、轨迹、保留/删除仍AGENT-06；完整最终业务门/初始预留与AGENT-05共同收敛。
- 0028仅临时测试库执行，正式三库仍0026，未迁移/部署/重启。回滚须先停止新运行并保留控制和交接数据，不能直接downgrade抹掉费用/已领取状态；临时测试库可往返。
- 下一项：完整LoopCheckpoint与write-ahead/回执对账、原规划/观察/重复状态和真实Driver；不以本轮工程结果代替完整AGENT-04、真实质量、盲测或生产门禁。当前无新增需人工裁决或付费事项。

## 7. 审核与交付边界

同版本代码全量门禁通过后，仅更新审核/状态文档。原预算所有顶层函数、公开模型、正常settle/公式AST保持；snapshot锁内构造逐节点等价，旧控制fixture原样移到support且全部旧测试函数保持，迁移/RLS只补0028库存。没有生产Driver、真实托管试跑或完整Loop恢复。按预算核心、PG持久层、提交后激活、测试支持及文档五组提交；精确路径和字节绑定后推送，CI按实际最终SHA另核验。
