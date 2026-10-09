# 实现记录 145：运行账本、死信与 MCP 检索一致性

- 日期：2026-10-08
- 基线：Git `cb83abd` 加工作区记录 126–144 的未提交改动
- 授权：用户要求“先修改再处理”，即先修正记录编号冲突，再处理记录 144 §6 的遗留项
- 结论：本轮工程自审通过；正式 Langfuse 后端/UI 仍未部署验收，阶段 1 的人工标注裁决仍待用户处理

## 1. 记录编号与小项清理

同日两个 agent 都使用了“记录 143”。预算受控模型复核保留 143；时间更晚的重构核验改为[记录 144](2026-10-08-implementation-144-refactor-verification-and-depiling.md)，README、阶段表、验收报告和 MRR 工具引用同步修正。

`skill_smoke.py` 不再用样本名生成可重复的 trace ID：每次执行生成新的 W3C trace ID，另用稳定 `run_id` 表示同一任务实例，重复执行不会在观测后端合并成一条 Trace。删除无调用方的 `safety_data.app_dsn`；安全集工具统一用 `evals.datasets.read_rows`，对本来允许缺省的 withdrawn 分类文件保留显式 `_optional_rows`，严格解析已有文件但不把“文件不存在”误判为损坏。

## 2. Langfuse 评分队列

`ScoreQueue` 的 SQLite 结构在打开旧队列时就地增加 `created_at`、`next_attempt_at`、`dead_lettered_at`，保留既有事件的固定 ID、固定 timestamp 和目标项目绑定。

默认策略：最多 10,000 行、最长待送 30 天、最多 10 次尝试；失败从 5 秒指数退避，最多 1 小时。达到年龄或次数上限后进入本地死信，不再每轮发送。容量不足时先删最老的已投递收据；若待送/死信本身占满则抛出固定码 `score_queue_capacity_reached`，不会无限写磁盘。`--requeue-score <id>` 是修复依赖后的显式重放入口。

没有把 score 写入改成未经验证的新接口。2026-10-08 重新查阅 Langfuse 官方[弃用迁移说明](https://langfuse.com/faq/all/deprecated-api-migration)和[版本兼容表](https://langfuse.com/docs/compatibility)：`POST /api/public/ingestion` 的 trace/observation 事件已弃用，但 `score-create` 事件仍受 v4 支持；官方 SDK 仍用这条路径。现实现因此继续发送 score-create，读取则已使用 observations v2。真实后端接受、v3 score 回读和 UI 关联仍须部署后验证。

## 3. 检索 outbox 死信与就绪

迁移 0020 新增 `outbox_consumer_failures`，失败次数、下一次尝试、死信和人工重放按 `(consumer,event_id)` 隔离。词法失败不会消耗向量消费者的次数。默认第 10 次失败进入死信；死信事件始终没有 ACK，也不会被 `published_at` 掩盖。修复后使用：

```sh
python -m medops.worker.retrieval --database medops_v2 \
  --consumer lexical-index --requeue-event <event_id> --actor <operator>
```

`/metrics` 增加每个消费者的 dead-letter 数。`/readyz` 只在决定实际可检索性的词法/向量消费者存在死信或积压超过 300 秒时失败。首次在真实 `medops_v2` 验证时发现缓存消费者有 338 条历史未 ACK 事件，而缓存默认关闭；若把它也作为阻塞项，完整索引会永久 503。本轮据此把 `retrieval-cache` 保留为指标/告警，不作为索引就绪条件，并补了 1 小时缓存积压的反例测试。

## 4. PostgreSQL 月度费用预留账本

迁移 0020 新增 `llm_monthly_spend`、`llm_spend_reservations` 与两个 `SECURITY DEFINER` 函数。应用角色没有表写权限，只能执行经过校验的原子操作：

1. 模型调用前锁定月份行，检查 `spent + reserved + worst_case <= cap`，再写唯一 reservation。
2. 成功后释放预留并按供应商返回的实际费用结算。
3. 供应商报错也可能计费，因此按 worst case 保守结算。
4. 进程在调用期间崩溃时 reservation 保留并继续占用上限；管理员可查到 reservation ID，依据供应商账单后调用同一结算函数。没有自动过期，因为无法仅凭时间判断供应商是否已收费。

`build_budgeted_gateway` 生产默认改用 `PostgresSpendLedger`，API、MCP 翻译和正式评测共享同一事实账本。账本连接/结算失败会使模型调用失败关闭。`InMemorySpendLedger` 只保留给隔离单元测试并实现相同的 reserve/settle 协议。

## 5. MCP 与 API 检索一致性

MCP 不再手工拼一套 `ProductionRetrieval`。它与 API/评测共同调用 `harness.assembly.build_retrieval`，并按当前主体的 release/canary 路由应用：

- 相同的 hybrid 参数、词表、多查询和指定文档聚焦；
- 发布的 query translation，通过共享费用账本调用模型；
- `RETRIEVAL_CACHE=memory|redis`，缓存键含实际 retrieval/policy version；
- 缓存命中后仍在 MCP 的只读、部门绑定连接内复核权限、状态和内容哈希；
- 相同的 reranker 与 evidence 上限。

MCP 搜索 Trace 现在记录翻译调用数、token、费用、实际 policy/retrieval version。翻译成功但后续检索失败时也保留已经发生的费用；缓存命中跳过翻译与搜索时相应模型调用为 0。其他三个纯数据库 MCP 工具仍记录 0 次模型调用。

## 6. 实现中发现的错误与补救

| 现象 | 根因 | 修复与复测 |
| --- | --- | --- |
| `uv run pytest`：`Failed to spawn: pytest` | `uv run` 临时重建 `.venv`，默认依赖没有 dev extra；项目规定的环境是 `venv/` | 改用 `venv/bin/python -m pytest`；未把环境错误记为代码失败 |
| Langfuse 重启测试第二次 drain 没有发送 | 新增退避后，测试时钟仍停在第一次失败时刻 | 测试改为可控时钟并推进 6 秒；35 项相关测试通过 |
| 安全集定向测试因 withdrawn JSONL 不存在失败 | 把旧的“文件缺省等于空列表”行为直接换成严格读取 | 仅对约定可选文件增加 `_optional_rows`；已有文件仍严格校验 |
| 0020 升级：`role "medops_app_role" does not exist` | 写错仓库真实组角色名；0002 定义的是 `medops_app` | 修正 UP/DOWN 授权；迁移 upgrade→downgrade→upgrade 通过 |
| 全量测试 1 项失败：RLS 表集合多出三张表 | 0020 正确启用强制 RLS，但测试白名单未更新 | 将三表加入权限清单；随后全量通过 |
| 真实库升级后 `/readyz` 报 `outbox_critical_lag` | 可选缓存消费者 338 条历史积压也被当成检索必需项 | 就绪只阻塞 lexical/vector；真实库恢复 ready，新增反例测试 |

## 7. 本机正式库状态

`medops_v2` 已从 0019 升到 0020；三张新表存在。升级后的只读检查：词法 pending 0、向量 pending 0、两者死信 0，`ready=True`。缓存 pending 338、最老约 17.5 天，继续显示但当前缓存关闭，不阻塞服务；若启用 Redis，应先运行 `retrieval-cache` 消费者清空。

本记录完成时 `.env` 默认仍指向 0007 的旧开发库 `medops`，这会使随后接入的持久费用账本在首次模型调用时找不到 0020 表。该后续问题已由[记录 146](2026-10-08-implementation-146-task-ledger-and-paid-run-preflight.md)修复：本机 `.env` 改指 `medops_v2`，`medops_v2` 与 `medops_v2_safety` 升至 0021，并补上应用角色可执行但不暴露账本行的月度总额函数；旧 `medops` 保持 0007 待退役或迁移。

## 8. 验证

- `env -u DEBUG -u PYTHONPATH make check`：退出码 0；ruff、423 个文件格式、mypy 187 个源码文件、Schema 漂移均通过；pytest **1627 passed、70 skipped**，1 条既有测试短 HMAC key 警告。
- 评测输入审计：PASS；保留 5 条已登记警告（7 个 unmappable gold、旧 replay safety、独立人工 pending、无 unseen holdout、19 条 annotation draft pending）。
- 定向：Langfuse/费用/MCP/outbox/就绪/RLS 共 85 项通过；迁移往返 2 项通过；真实 `medops_v2` 在 0020 上 `ready=True`。
- `git diff --check` 通过；冻结数据版本未由本轮改写。

## 9. 提交规划与剩余边界

工作区包含两个 agent 的连续未提交成果，不按 agent 拆提交。建议顺序：评测标准与工具；API/Harness 重构；遥测与 Langfuse；运行完整性/迁移 0020/MCP 一致性；文档与证据。记录 143 的代码归 API/Harness 组，文档归文档组。当前未创建提交，避免替用户决定如何切分已有大工作区。

本轮没有把 Langfuse 组件测试写成“已部署”：正式项目、凭据、回读与 UI 排障演示仍是 OPT-09 的外部验收项。也没有清除缓存历史积压；缓存关闭时它不影响行为，启用 Redis 前需要运维处理。

## 10. 自审

| 自审项 | 结论 |
| --- | --- |
| 需求与范围 | 通过。处理记录 144 §6 的可实现项；没有更改质量门槛、数据分母或 BM25 结论。 |
| 正确性与失败路径 | 通过。队列/账本均先预留或持久写入后调用外部依赖；死信不 ACK；缓存命中仍回查；真实库验证发现的误伤已修复。 |
| 权限与可追溯性 | 通过。新表强制 RLS；应用只能执行预算函数；MCP 仍使用只读事实连接；错误与队列不存正文/凭据。 |
| 验证 | 通过。全量、迁移、权限、真实库检查均有上节证据。跳过项为既有不可达实验服务。 |
| 状态与文档 | 通过。组件实现、本机迁移、外部部署和人工裁决分别陈述；本自审不是第二人工复核。 |
