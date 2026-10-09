# 记录 146：任务台账校正与付费运行数据库预检

日期：2026-10-08。

## 1. 发现的问题

当前代码已经把生产模型网关接到 PostgreSQL 持久费用账本，但本机 `.env` 的应用和管理 DSN 仍指向 migration 0007 的旧开发库 `medops`。该库没有 `llm_monthly_spend`、`llm_spend_reservations` 和 migration 0020 的预算函数，因此 API、`smoke_ask` 或 `safety_run` 第一次真实模型调用会在供应商调用前因数据库对象不存在而失败。

安全事实库 `medops_v2_safety` 停在 0019，也缺少相同对象。`medops_v2` 已在 0020。

工作区另有未跟踪的 Finder 副本 `src/medops/infrastructure/llm/budget 2.py`；其内容来自 9 月 23 日，若执行 `git add -A` 会被误提交。

## 2. 修复

1. 仅修改本机、被 Git 忽略的 `.env`，将 `DATABASE_URL` 与 `DATABASE_ADMIN_URL` 的数据库名由 `medops` 改为 `medops_v2`；主机、端口、用户和凭据未输出、未改写。
2. 将 `medops_v2_safety` 从 migration 0019 升至 0020。
3. 保留旧 `medops` 在 0007，当前运行不再默认连接它；后续单独决定退役或迁移。
4. 删除未跟踪 Finder 副本。
5. 新建[当前任务台账](../CURRENT_TASKS.md)，将所有会产生模型调用的运行标为逐次 `PAID`：数据库月度上限只负责 fail-closed，不能代替用户对本次费用的明确批准。
6. 提交按功能边界拆分，不按作者拆。记录 143 的代码归 API/Harness 组，文档归文档组。

## 3. 核对结果

修复前实测：

| 数据库 | migration | 费用表 | lexical pending | vector pending | cache pending |
| --- | --- | --- | ---: | ---: | ---: |
| `medops` | 0007 | 无 | 231 | 231 | 231 |
| `medops_v2` | 0020 | 有 | 0 | 0 | 338 |
| `medops_v2_safety` | 0019 | 无 | 0 | 0 | 339 |

第一次只读复测又发现：应用登录角色不能直接读取 `llm_monthly_spend`，而 `PostgresSpendLedger.month_total()` 仍直接查询该表。代码会在读取月度总额时收到 `InsufficientPrivilege`。集成测试原先只用迁移所有者 DSN，未覆盖真实应用角色。

追加 migration 0021：增加 `medops_llm_month_total(date)`，使用固定 `search_path` 的 `SECURITY DEFINER` 读取聚合总额；只向 `medops_app` 和 `medops_admin_role` 授予执行权，不授予底层表 `SELECT`。`PostgresSpendLedger` 改为调用该函数，并增加真实 app 登录用户能够完成读取、预留、结算但不能读取账本行的集成测试。两个正式本地事实库最终均升至 0021。

修复后，`.env` 指向 `medops_v2`。缓存消费者积压仍保留；Redis 关闭时不阻塞 ready，启用 Redis 前分别处理 338 和 339 条。旧开发库的 231 份 draft 与三组积压没有被静默删除。

## 4. 其他核对

- `skill_smoke` 已在当前工作区使用 `new_trace_id()`，每次执行的 Trace ID 不再固定；稳定的 run ID 与 Trace ID 分开。
- `safety_data.app_dsn` 已不存在，无需再改。
- Langfuse 官方 v4 兼容说明明确保留 `score-create` 经 `/api/public/ingestion` 的写入支持；弃用的是该入口的旧 trace/observation 事件以及旧读接口。真实后端、凭据、回读和 UI 演示仍未验收。
- MRR 必须写明两个不同口径：证据内 MRR@8 0.7706；候选内 MRR@20 0.6142。

## 5. 当前人工门

三项标注裁决仍是无费用修订的唯一前置。裁决后可以先应用修改、重算哈希和完成机械检查；模型复核属于新的付费运行，需要用户同时或之后明确给出本次授权额度、范围和停止条件。

## 6. 验证

- `medops_v2` 与 `medops_v2_safety`：migration 0021。
- 两库均由真实 `medops_app_user` 成功调用 `medops_llm_month_total`；直接 `SELECT llm_monthly_spend` 均被拒绝。
- 费用账本、Skill Trace ID、Langfuse 队列定向测试：38 passed。
- migration 单头、离线渲染和完整 upgrade→downgrade→upgrade 由全量检查覆盖。
- `env -u DEBUG -u PYTHONPATH make check`：1628 passed、70 skipped；ruff、format、mypy、评测审计和 Schema 检查通过。评测审计保留原 5 条已登记警告。
- `git diff --check` 通过；`.env` 仍被 Git 忽略；Finder 副本不存在。

第一次定向运行没有清除 shell 中格式非法的 `DEBUG`，导致一个 Settings 单测在配置解析阶段失败；按项目既定命令清除 `DEBUG` 后通过。该环境错误没有记为代码失败。

## 7. 自审

| 项目 | 结论 |
| --- | --- |
| 范围 | 通过。修正本地事实库目标、安全库 migration、应用角色预算读取、误提交文件和任务状态；未运行模型。 |
| 数据 | 通过。未修改文档、chunk、ACL、冻结数据或历史运行。 |
| 权限 | 通过。DSN 凭据未写入文档或命令输出；`.env` 继续被 Git 忽略。 |
| 费用 | 通过。没有供应商调用；后续所有模型运行逐次等待明确批准。 |
| 状态 | 通过。工程实现、数据库可用、付费授权和正式评测分别记录。 |
