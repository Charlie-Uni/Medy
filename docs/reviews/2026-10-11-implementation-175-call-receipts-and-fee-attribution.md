# 实现记录 175：调用回执与并发费用归属

## 0. 任务、范围和结论

- 日期：2026-10-11（Australia/Sydney）；实现者及自审核者：Codex 本轮实现者。自审不等于第二独立人工。
- 任务：ARCH-04；对应 OPT-09、INV-OBS-01。用户指令“明白了 继续”，按台账推进本轮无付费架构修复；ARCH-11 不在本轮实现范围。
- 开始 HEAD：`5a604050b9c0706bfd823685e5befcb9619d64a6`；已有 54 个修改/新增文件，先按 SHA-256 备份，保留 ARCH-01 与既有设计/台账工作。
- 目标：避免失败请求从共享 run 累计费用差值串入另一请求；为成功、失败、拒绝、取消和结算故障提供调用身份、独立费用依据及可查询的持久回执。
- 固定条件：冻结数据/gold、评测分母/门槛、默认模型/价格表、ACL、安全规则、发布策略均未调整。托管模型调用 **0**、费用 **0 USD**；未提交/推送。
- **本轮工程自审通过**；最终保护/台账检查证据见[175-results.json](2026-10-11-implementation-175-results.json)。工程通过不能代替真实模型质量、性能、生产验收或第二人工。

## 1. 原缺陷复现

原 `MeteredGateway` 在失败时取共享 BudgetedGateway 的 run_accounted_cost_usd 前后差。阻塞失败 A、使成功 B 先结算再释放 A，可以确定性复现串账。

新增反例在原实现上实际失败，pytest 原输出：

```text
assert 7.53e-05 == 5.02e-05 ± 5.0e-11
Obtained: 7.53e-05
Expected: 5.02e-05 ± 5.0e-11
1 failed
```

这是调用归属错误；本轮没有宣称月度总账也存在相同串账。预留和月度结算原本使用短独立事务，继续保留。

## 2. 实施与设计

1. `gateway.py` 增加 ModelCall/ModelCallReceipt，响应可携带回执；请求 call 字段是内部身份，不发送给供应商。
2. 新 `accounting.py` 通过 ContextVar 保存 run/attempt 作用域和单调用回执通道。不会修改可被多个线程重复抛出的共享异常对象，也没有进程级 last_receipt。
3. `budget.py` 在调用前确定 reservation_id，记录失败/拒绝/取消以及不确定提交。run 总数仅用于 run cap；请求费用不再依赖该共享数值的差。
4. `meter.py` 按 call_id 聚合并去重，锁保护并发；分开已知本地费用和保守预算占用。拒绝且未启动的调用不计入供应商调用次数，未返回的 Token 不伪造。
5. `openai_gateway.py` 在结构化解析前保留 usage 与价格结果；无效 JSON/非对象/截断仍拒绝使用，但按已有 usage 计费。ARCH-01 的截止时间及可取消传输保持。
6. Harness run/node、Skill Registry、worker task/attempt、MCP tool 注入上下文；翻译线程现有 copy_context 保留归属。真实 LangGraph 假模型执行和节点重试验证 run 与 operation/attempt 关联。
7. 迁移 0023 在原费用预留表追加元数据列与索引。新受控 reserve_call/settle_call 函数将身份/预留、回执/结算各自同事务保存，保留原函数/权限。新增调用不允许重复 call_id，回执重放幂等，不同回执不能覆盖。

详细字段、失败矩阵、DB 前置、管理员查账及回滚边界见[模型调用费用说明](../LLM_ACCOUNTING.md)。本轮不另建业务编排器，不把计量 ContextVar 当作 Agent 持久状态。

## 3. 实施与自审发现的问题

| 问题/错误 | 修正及复核 |
| --- | --- |
| 原实现并发失败串账 | 替换为调用回执；原反例与两失败、拒绝/成功交错均通过 |
| 首次 Ruff 检查 5 项错误：4 个 I001 与 ContextVar 默认实例 B039 | 整理导入，Scope 默认改 None 后按上下文实例化；最终全量 Ruff 通过 |
| 自审发现取消与结算同时失败时取消会被包装成普通 InfrastructureError | 保留取消异常，发布 pending 回执；供应商取消/结算取消两个边界回归通过 |
| 内存替身重复结算未补回执、重复 call_id 与 PG 契约不一致 | 对齐校验和 legacy settle 后附加回执；替身及 PG 幂等/冲突测试通过 |
| 原数值列只保留六位小数，精细费用重复结算可被原函数误判为不同金额 | 新回执函数先对完全相同 JSON 幂等返回；legacy 已结算按原列精度核对。0.0000502 回执保留，原列为 0.000050，重复无再扣账 |
| 遥测新测试报 `KeyError: 'accounted_cost_usd'`，当时只保留兼容 cost_usd 名 | 显式追加 accounted_cost_usd，保留原名；最终全量含该反例通过 |
| 全仓 tracked 文件读取 SHA 尝试触发 `[Errno 60] Operation timed out` | iCloud 文件读取限制；采用仓库外快照，全量门禁实际输入的 486 个源码/测试/配置逐个 SHA 一致，无错误/不符。没有把中断的原目录命令报作通过 |
| 最终检查器用 app 读取 alembic_version，实际报 InsufficientPrivilege；首版任务正则也漏计 4 行带说明状态 | 改用 admin 查迁移、app 仅查自身函数/表权限，不扩大授权；状态前缀解析覆盖全部 141 个任务，再复核状态变化 |
| 查找时误猜 docs/DEPLOYMENT.md 不存在 | 用 rg --files 定位实际 docs/DEPLOY.md；属检索命令错误，不是项目运行故障 |

## 4. 验证命令与结果

- 原反例：`venv/bin/python -m pytest tests/unit/infrastructure/test_llm_call_receipts.py -q` 在修改前退出 1，1 failed；初次修复加网关旧回归退出 0，13 passed。
- 扩展 API/worker/MCP/Harness/遥测定向检查：52 passed，退出 0；类型检查 194 源文件通过。
- 调用回执单元、PG 回执、原费用账本及迁移专项：`pytest tests/unit/infrastructure/test_llm_call_receipts.py tests/integration/test_llm_call_receipts.py tests/integration/test_llm_spend_ledger.py tests/integration/test_migrations.py -q -ra`：48 passed，退出 0（最后三项 Harness/遥测测试在此后加入，最终全量覆盖）。
- 加入遥测反例后的小批验证实际为 32 passed、1 failed；失败后增加明确字段并由最终全量复核。
- 最终 `env -u DEBUG PYTHONPATH=<snapshot>/src:<snapshot> make check`：退出 **0**，**1807 passed、70 skipped、1 warning，51.14s**；459 文件格式、194 源文件 mypy、4 集评测审计及 Schema 漂移通过。
- 70 skipped 为既有可选 DEC-001 B/C 实验环境未配；本轮 PostgreSQL、app 权限、迁移与 Redis 必需集成实际执行。唯一警告为刻意短 HMAC 密钥的认证反例，未调整生产配置。
- 评测审计仍报告两个 unmappable gold 保留 miss、历史 replay 旧安全集、第二人工 pending、未建 unseen holdout；没有借工程检查关闭这些问题。
- 工作树：`/Users/leaf/.cache/medy-checks/arch04-vzdp5qlh`；日志 `.local/arch04-check.log`。可移植摘要、哈希及真实结果保存在本记录的 JSON；完整运行日志、源文件对比及本机备份为本地临时产物。

## 5. 本机迁移与保护

本机三个库分别由 0022 升至 0023。每个库先备份费用表到本地 mode 0600 文件，再用实际 Alembic 升级；前后文档、chunk、ACL、policy/release/released pointer、原月度费用以及预留基本字段摘要完全一致。

| 库 | 文档 / chunk | 原预留 | 迁移后 |
| --- | --- | --- | --- |
| medops_v2 | 350 / 36100 | 40 | 0023；40 条 call_context={}、receipt=null，不补造历史 |
| medops_v2_safety | 351 / 36184 | 0 | 0023 |
| medops | 247 / 25737 | 0 | 0023；仍非正式 API 目标库 |

数量逐项从实际迁移机器证据回填；初稿两个库的 chunk 数写错，最终自审已改为 36184 / 25737。原目录另跑 `medops.evals.audit --summary` 也退出 0，4 集 PASS，保留相同四项警告。迁移往返测试在临时库执行：0022→0023→0022→0023 保留旧费用和预留金额，降级会删除调用元数据，已在操作说明明确。

## 6. 逐项自审

| 项目 | 结论与证据边界 |
| --- | --- |
| 需求与范围 | 通过：ARCH-04 原反例先失败，修后成功；调用/Trace/run/attempt/reservation、估计与已知费用各自留证；原模型、价格及门禁不变 |
| ADR 与阶段硬门 | 通过：未改目标/验收；ARCH-11、PLAN-02 尚未完成，不解锁 S2，不实施动态 Agent/Loop |
| 正确性与失败路径 | 通过：确定性交错、64 并发、同异常对象、拒绝、无效结构、期限、取消、提交确认丢失、结算故障及重复/冲突结算回归通过 |
| 权限与数据 | 通过：新函数无 PUBLIC/readonly 执行权，app 不可直接读改账表，正文与嵌套伪装字段拒绝；实际 ACL/策略/业务数据前后摘要一致 |
| 预算/取消/副作用 | 通过（ARCH-04 范围）：0 托管调用；预留不确定仍占用 run cap，pending 不重跑模型，取消仍传播；统一 Token/单执行预算归 ARCH-11 |
| 追溯与版本 | 通过（调用计量范围）：新预留身份/结算回执独立持久化；实际 response_model 与 ID 可查。受限完整输入、任务证据审计及原条件复现归 ARCH-06/07 |
| 验证充分性 | 通过（工程范围）：全量 + 真实 PG 权限/迁移，维护输入 SHA 一致；供应商计费/真实质量/容量不适用本轮且未证明 |
| 状态与文档 | 通过：141 个任务 ID 完整保留、ARCH-04 经 REVIEW 到 DONE、ARCH-11 仅由依赖解锁为 READY；其余 Agent/质量门保持，台账/阶段/README 与操作说明同步 |

## 7. 限制、回滚与下一步

- usage 计算费用不是最终供应商账单；未知的失败用量留空。原 Token 估算算法不是供应商硬上界，本轮未改变它。
- 崩溃且 DB 不可用时实际响应/回执可能丢失；已提交预留及身份仍保留，需外部 usage/账单对账。没有自动对账器，也没有完整物理 HTTP 尝试记录。
- 未提交/被拒的预留只有本次内存回执和启用时的 Span，没有持久费用行。完整失败任务审计继续由 ARCH-06/07 负责。
- 旧应用可继续调用原 DB 函数；新代码启动前要求 0023，外部部署未自动升级。应用回滚优先保留新 DB 结构；数据降级前必须导出元数据并停新写入。
- 开始时 54 文件已备份到 `/var/folders/zj/6djhy_4x7vx_7t8xcgt_v62c0000gn/T/medy-arch04-10957dhq`。回退本轮只恢复本轮改动与备份中的重叠文件，不能整树 reset 或删除既有 ARCH-01/设计工作。
- 下一主切片 **ARCH-11：统一单执行 Token/费用预算**。继续无付费实现及自审；任何真实模型实验另申请当次范围与预算授权。没有新增人工裁决请求，也没有把既有 PLAN-02 待答问题默认通过。
- 本轮没有统计人工作时或重估整体周期；实际命令耗时及文件哈希在机器结果中留证。
