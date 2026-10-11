# 实现记录 176：单次执行共享 Token、费用和时间预算

## 0. 本轮任务与结论

- 日期：2026-10-11，Australia/Sydney；实现者与自审核者：Codex 本轮实现者。没有第二独立人工，也没有委托其他 agent 审查。
- 主切片：**ARCH-11**，对应 OPT-11、INV-HAR-08；前置 ARCH-04 已工程通过。开始 HEAD 为 `5a604050b9c0706bfd823685e5befcb9619d64a6`，已有 68 个未提交修改/新增文件；先备份并记录 SHA，保留上一轮工作。
- 所有者已对兼容 profile 回复：**“采用现有规则推导的上限”**。据此沿用 12,000 Token；按仓库固定已准入价格表最高单价折算 0.60 USD；Ask 根时限 125 秒，Skill/MCP 仍受原较短期限约束。未重新查价、未准入新模型、未批准未来 Agent 的动作/profile 或付费运行。
- 本轮工程自审通过：最终 `make check` **1830 passed、70 skipped、1 warning**，退出 **0**；490 个维护输入及环境示例配置在核验工作树与原目录 SHA 一致。机器证据见[176-results.json](2026-10-11-implementation-176-results.json)。
- **托管模型调用 0，费用 0 USD，未提交/推送、未重启服务、未新增迁移。** 默认模型/价格表、冻结数据/gold、分母/门槛、ACL、安全规则与生产策略未改变。
- 完成的是现有业务入口的共享预算及未来入口的工程契约。动态 Agent/模型 Reflect/Adapt 尚未实现，跨进程恢复、任务租约、真实质量/性能与 S2/S3 成效没有因此通过。

## 1. 原问题及真实失败证据

原先 Ask 的 Token 计数集中在作答局部：翻译不参与；模型失败/重试可能只在费用账本计入；证据检索先加一份估计，模型 input 再含同一证据；二阶段 Skill 的 grounded Ask 与后续结构化调用没有同一额度。月度和评测批次费用上限不能替代单执行约束。

把新的共享对象/反例放到上一轮 ARCH-04 的旧接线快照，限制一执行只有 1 Token，调用 query_translation。旧网关仍进入供应商替身，实际 pytest 输出：

```text
E   Failed: DID NOT RAISE ExecutionBudgetExceeded
1 failed in 0.55s
```

命令为 `pytest tests/unit/infrastructure/test_execution_budget.py::test_shared_execution_rejects_translation_before_provider_when_tokens_insufficient -q`，退出 1。旧业务接线没有读取执行预算上下文；这是本轮预先保留的缺陷反例，不是供应商请求失败，也没有真实费用。

## 2. 设计：三层上限分别负责什么

| 层次 | 范围 | 当前责任 |
| --- | --- | --- |
| 单次执行 | 一题 Ask、一次 Skill、一次 MCP 检索或同一父执行的一批嵌套 Skill | 共享 Token/费用/总期限；所有实际调用前预留，重试继续扣同一份额度 |
| 评测批次 | 获准的多题/多轮实验 | 原 `run_cap_usd` / `--max-cost-usd`，限制本批次累计费用；不因每题新建执行对象而重置 |
| 月度账本 | 多进程、多个入口的同一部署 | PostgreSQL 原子预留/结算，独立短事务；保留 0023 调用身份、回执与 pending 对账 |

执行额度并不是用户的付费授权。三层同时满足也不能自动发起实验；每个真实模型运行仍须按当次范围、费用和停止条件授权。

### 2.1 为什么用 ContextVar＋共享对象＋锁

现有 Harness/Registry 是同步主体，翻译和 parallel_safe Skill 已通过 copy_context 进入线程。ContextVar 传递同一执行对象的引用，锁让“已使用＋并发预留＋新调用”在同一个临界区检查，不依赖进程级最后一次结果。嵌套调用重新进入 scope 只缩短局部期限，不重新发放 Token/费用；显式换掉父对象会拒绝。

总期限在对象首次进入时固定，也受当时父期限约束。同一对象以后重新进入不能延长；不同根调用自然各有一个新对象。新 Agent 若需要持久恢复，必须另有恢复契约，不能把这一机制当成已经实现的 checkpointer。

### 2.2 为什么不继续使用字符 / 4 做供应商前的准入

旧估计没有 JSON Schema 和 framing，且不是精确 tokenizer。本轮预检按消息 UTF-8 字节数、Schema 字节数、固定 framing 余量与最大输出计算；输入按未缓存单价，输出按完整 allowance 算金额。月度预留取此值和旧估计的较大值，旧独立批次工具仍保持旧算法。

字节预检更保守，不能证明供应商内部 framing 或账单必然不超额。供应商若返回意外更大的 usage/费用，必须如实保存、拒绝该结果，并阻止下一调用；已产生费用不能撤回。这也可能让部分证据少装入或请求更早预算停止，真实质量/效率影响尚未重测。

## 3. 改动和入口核验

| 文件/范围 | 改动及完成边界 |
| --- | --- |
| `infrastructure/llm/execution_budget.py` | ExecutionLimits、锁保护的预留/结算、快照、根期限、上下文与单 call_id 准入；版本 `execution-budget-v1+utf8-preflight` |
| `llm/meter.py`、`budget.py`、`factory.py` | Metered/Budgeted 嵌套只计一次；回执与原 monthly/run cap 相接；同一价格表；服务工厂可强制要求执行上下文 |
| `core/config.py`、`.env.example` | 三项所有者确认的服务端配置；实际 `.env` 未改 |
| Harness runtime/contracts/deps | 根 Ask scope 与现有节点期限并存；每个节点体开始前检查共享预算；服务装配传入 profile，裸测试网关补计量包装 |
| Harness answer/nodes | 完整作答请求参与证据装入预检；证据不再假装已经发生供应商使用；终态预算保存包含翻译/失败重试；幂等复用保留历史结果的用量 |
| Skill Registry | grounded Ask 和最终结构化阶段共享；重试和 execute_many 共用父额度；预算不足归类 budget_exceeded；原 schema、scope、安全检查和输出契约保留 |
| API/worker 与 MCP 装配 | API 配置经原 SkillContext 进入 worker；MCP 原 20 秒期限、翻译 MeteredGateway 和预算连接保留；翻译吞掉预算异常也不能让根请求继续返回成功 |
| smoke_ask / skill_smoke / safety_run / replay_run | 同一服务配置与强制上下文；批次封顶仍在；Plane 传入执行 limits，真实运行没有在本轮启动 |
| 新测试与已有 fixture | Token/费用拒绝、实际/保守结算、并发、取消、嵌套、期限、真实 Skill、翻译线程、判定、幂等、PG 回执；假配置补齐新增字段 |
| Loop 与未来 Agent | 源码核验当前 `src/medops/loop` 没有 `.complete(`；现有 Reflect/Adapt 仍规则/手工。未凭空写一个空 Agent 入口作为完成证据；后续新入口必须显式 profile、最外层 scope 和 `require_execution_budget=True` |

离线原件审查、术语提取和单独检索诊断不属于本轮业务入口改造；其直接网关维持原显式批次/月度边界。不能据此称所有付费工具已变成 Agent，也不能让未来 Agent 选择该兼容缺省作为绕过方式。

## 4. 失败、取消、并发如何结算

- 已有 usage 的正常或无效结构化响应：计入回执的 Token/本地费用，释放未用预留；无效输出仍不可作答。
- 供应商已开始但超时/取消/故障且 usage 未返回：保守计入本次完整 Token 与费用预留，known_tokens 保持 0；原超时/取消继续传播。
- 费用/月度拒绝、尚未开始且确定结算为零：不计真实调用、Token 或费用；有 denied 回执。
- 预留提交确认丢失：金额继续保守占用，pending 和 reservation_id 保留；未进入供应商则不伪造供应商 Token。对账不触发模型重跑。
- 并发请求不能同时花同一余额；一个准入拒绝会锁定本执行。已启动调用仍收束、保留使用量，但不能把其结果作为超额执行的答案继续返回。
- 结构化 Skill、判定器、截断后二次输出、节点重试，都不能新建一份额度。共享预算与原 node deadline 合用；清理/结算仍可能有必要收束时间，不宣称任意代码可被瞬间终止。
- 正常幂等复用保存原结果的历史预算；该次新增调用数/费用另从根 Span 与计量器看。重复返回结果不再次扣费，也不把历史 used 清零伪装为原执行没用 Token。

## 5. 实施、自审发现的错误与补救

| 实际问题或失败 | 原因 → 修复 → 复测 |
| --- | --- |
| 原 1 Token 反例 `DID NOT RAISE` | 旧网关没读共享 scope → 统一 Metered/Budgeted 接线 → 定向及全量通过 |
| 第一轮定向 1 failed / 216 passed：重复运行 `second.state != first.state` | 根返回用本次 0 新调用清掉原历史预算 → 终态预算入操作 delta、无新增用量时保留复用结果 → 真实翻译＋幂等反例和全量通过 |
| 第二轮定向 1 failed / 229 passed：DeadlineExceeded 在 with 进入时抛出 | 修复后正确地更早拒绝过期 scope，但测试把 pytest.raises 放在其后 → 调整测试捕获范围 → 230 passed |
| 首轮全量 4 failed / 1824 passed / 70 skipped，make 退出 2 | 2 个运行工具假 Settings 未有新增字段；另 2 个仓库卫生测试因拷贝快照缺 `.git`，git ls-files 返回 128 → fixture 补字段、重建真实注册的 detached worktree → 针对修复的 22 passed、第二轮全量 1829/70 通过 |
| 自审发现嵌套计量器可能使用标准价格而月度网关使用自定义准入价格 | 提供并继承 execution_prices → 高价表反例在供应商前拒绝，多层 Metered 不重扣 |
| 自审发现同对象重入可能重新计时，或者忽略更短 scope/首次父期限 | 对象保存首次有效绝对到期时刻，限制重入；期限比 profile 更短也保留 → 两种 scope/profile 组合及父期限反例通过；最终全量 1830/70 |
| 预留前期限耗尽可能被回执误当成未知供应商失败 | 预检/价格/期限失败发布 not_started；月度网关早期 deadline 放在相应回执处理内 → 原期限/回执回归通过 |
| 初次格式检查的导入顺序、文档 patch 未匹配管道行 | Ruff 修复；patch 因缺表格前导 `\|` 原子拒绝，没有半写文档 → 按实际原行重做，最终 Ruff 与链接检查通过 |
| 阅读时误猜测试、helpers 或 runner 路径，及 zsh glob 无匹配 | 搜索命令错误，不是服务故障；改用 rg --files 定位现有文件，未新建同名壳或扩大实现范围 |

全部失败保留在本轮摘要；没有将首轮非零退出报作通过。仓库外核验用于避开之前确认的 iCloud 读文件限制，不跳过库、秘密扫描或评测审计。

## 6. 验证命令与结果

1. 原缺陷：旧 ARCH-04 接线上一条新反例，退出 1，1 failed，0.55s。
2. 首轮跨入口定向：217 项中 216 passed、1 failed；补幂等后扩展定向为 229 passed、1 failed（测试异常捕获范围），修复后 **230 passed，3.42s**。
3. 修复首轮全量的 fixture / Git 元数据及期限问题：`pytest tests/unit/docs/test_repo_hygiene.py tests/unit/evals/test_harness_runner_resume.py tests/unit/infrastructure/test_execution_budget.py -q`，**22 passed，2.88s**。
4. 最终命令：`env -u DEBUG PYTHONPATH=<worktree>/src:<worktree> make check`，退出 **0**；**1830 passed、70 skipped、1 warning，46.78s**。462 文件格式检查、195 源文件 mypy、安装检查、Ruff、4 集评测审计和公开 Schema 漂移均通过。
5. 70 skipped 为既有 DEC-001 B/C 可选实验环境未配；真实 PostgreSQL/Redis 必需集成已执行，包括本轮 PG 预留回执、老权限/迁移/费用反例。唯一 warning 是认证测试刻意使用短 HMAC 密钥。
6. 审计仍报告 unmappable gold=2 保留 miss、历史 replay 旧安全集、第二人工 pending、没有注册新 unseen holdout；本轮没有关闭这些质量缺口。
7. 最终工作树：`/Users/leaf/.cache/medy-checks/arch11-verified-3smansb5`，日志 `.local/arch11-check.log`；490 输入及 `.env.example` SHA 比对 0 错误、0 不符。旧失败快照与第二轮通过日志均保留作历史，本次以最后已修复版本为准。

## 7. 逐项自审核

| 检查项 | 结论及限制 |
| --- | --- |
| 需求/范围 | 通过：现有翻译、生成、判定、结构化、重试都共享；三层上限区分，兼容数值经所有者确认。规划/新 Loop 尚无模型入口，未来必须按同一契约接入，不假称已实现 |
| ADR/阶段硬门 | 通过：ADR v0.4 留下现有预算决定；ARCH-04/11 工程门通过，PLAN-02 Agent profile/验收及其他正确性依赖仍有效；自动激活仍限实验，不启动 S2/S3 或付费试跑 |
| 正确性/失败路径 | 通过：原反例、翻译 fallback、timeout/取消、无效 JSON usage、已知超额、并发预留、多层计量、真实两阶段 Skill、判定、重入期限和幂等均有回归 |
| 权限/数据 | 通过：未改 ACL/RLS、工具白名单、生产批准、冻结数据/gold/评分阈值；没有新 DB 权限/迁移。元数据只有预算和调用量，不上传正文/密钥 |
| 预算/取消/副作用 | 通过（当前执行范围）：0 托管调用；预留并发保护、未知费用不退空、取消传播；月度与批次仍保留。跨进程新尝试/恢复计入方式归 ARCH-05/06/07，尚未证明 |
| 追溯/版本 | 通过（预算工程范围）：现有调用回执持久化；Ask/Skill Span 带预算算法版本、根 limits、计入/保留量和阻塞原因。完整执行 profile 恢复与受限原输入回放仍待后续 |
| 验证充分性 | 通过（工程范围）：最后全量、真实 PG/Redis、维护输入 SHA 对照；真实模型质量/性能/账单为未测，不拿假网关成绩代替 |
| 状态/文档 | 通过：台账经 READY→IN_PROGRESS→REVIEW→DONE，只更新 ARCH-11 状态；全部 141 个任务 ID 保留；README/阶段/计划/ADR/部署/费用说明同步，PLAN-02 和 Agent/盲测仍保留实际状态 |

## 8. 限制、回滚与下一项

- 执行对象在内存中；不是持久 Agent 预算或已获准的 Agent profile。worker 接管和根级重跑当前是新执行尝试；月度回执持久，按尝试累计/恢复的完整责任仍需 ARCH-05/06/07。复用已经成功的节点结果不新增费用，与失败后重新启动一次请求的语义不同。
- 对供应商用量未知的预检和保守预留都不是账单承诺；物理 temperature 兼容重发仍在一逻辑调用中。总时限是协作式，必要清理不等于 P95 性能通过。
- 旧 TokenBudget Schema 不允许 used 超过 limit，意外超额完整值保留在共享快照/回执，不把超额响应交给用户；旧 schema 未改变。
- 更保守请求预检与纠正证据重复计数会改变部分上下文装入/停止行为。新冻结集质量、安全、检索和答案级对照都须在以后单独获准运行；本轮不声称医学效果提高。
- 未重启常驻服务；只有工作区代码与核验版本。生产部署、CI 推送和任何新付费运行仍按当次要求办理。
- 回退只恢复本轮文件及备份中的重叠文件。备份：`/var/folders/zj/6djhy_4x7vx_7t8xcgt_v62c0000gn/T/medy-arch11-wr8z_30a`；不能整树 reset，不能撤销已有 ARCH-01/04/场景设计工作。无需降级数据库；0023 回执结构保留。
- 下一主切片：**ARCH-05 任务总时长、租约和持有权**；PLAN-02 剩余 Agent 动作/profile 与验收契约继续准备。原生产 +5pp 问题仍待答，没有重复索要已确认的现有预算或假定未答事项已获准。
- 从开始备份到本轮记录约半小时，主要返修与等待为回归、全量门禁及核验环境；未统计人工工时，不据此重估整体 Agent 交付日期。准确运行秒数保留于机器摘要。
