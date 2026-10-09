# 记录 161：干净 CI runner 配置隔离修复

日期：2026-10-09。

## 1. 失败现象

推送 `3e5e46c` 后，GitHub Actions `ci` 运行 `37906443818` 在 `python -m pytest -q` 失败：

- 1684 passed、92 skipped、6 failed；
- 批量摄取测试 1 条、Loop CLI dry-run 参数化测试 3 条、MCP stdio 测试 2 条失败；
- Ruff、格式和 mypy 在失败前均已通过，后续评测输入、迁移和 Schema 步骤因 pytest 失败而跳过。

六条失败都发生在业务断言之前。`Settings` 缺少必填的 `DATABASE_URL` 和 `REDIS_URL`，Pydantic 因此拒绝启动 CLI。

## 2. 根因

本地仓库存在被 Git 忽略的 `.env`，会被 `pydantic-settings` 自动读取，所以原本不完整的测试 fixture 在本地仍能通过。GitHub runner 是干净检出，没有 `.env`。

CI 已提供 `MEDOPS_TEST_ADMIN_URL` 和 `MEDOPS_TEST_REDIS_URL`，供集成测试 fixture 创建临时数据库及访问测试 Redis；它们不是应用 `Settings` 的 `DATABASE_URL` / `REDIS_URL`，也不应被单元测试隐式当成应用配置。

## 3. 修复

没有修改生产默认值或把测试 DSN 写入应用代码：

1. 批量摄取测试显式传入 `--no-av`。该测试验证逐文档状态与退出码，使用显式 `--admin-url`，不测试 ClamAV；因此不再为了一个未使用的 scanner 构造完整应用配置。
2. Loop CLI fixture 显式设置测试用 `DATABASE_URL`、`DATABASE_LOOP_URL` 和 `REDIS_URL`。
3. MCP stdio fixture 在已有应用与只读 DSN 之外显式设置测试用 `REDIS_URL`。

这些值只存在于测试进程的 `monkeypatch` 环境中，不进入运行产物或部署配置。

## 4. 验证

- 从 `/tmp` 运行 Loop 与 MCP 测试，并清除相关数据库、Redis 和 Loop 环境变量：5 passed；该工作目录没有仓库 `.env`。
- 批量摄取定向集成测试：1 passed。
- `env -u DEBUG -u PYTHONPATH make check`：1712 passed、70 skipped；Ruff、格式、mypy、评测输入审计与 Schema 检查通过，仅保留既有的短 HMAC 测试警告。
- Git diff whitespace 检查通过。

远端修复验证由本记录对应提交触发的新 GitHub Actions 运行给出；本地验证不替代远端结论。

## 5. 自审

| 项目 | 结论 |
| --- | --- |
| 范围 | 通过。只修复测试 fixture 的配置隔离，没有修改生产行为、数据集、模型或门禁。 |
| 根因 | 通过。远端六条失败具有同一配置前置原因，本机 `.env` 对缺口的遮蔽已在无 `.env` 工作目录复现。 |
| 权限与秘密 | 通过。测试 DSN 使用合成用户名和密码；没有读取或提交本机 `.env`。 |
| 验证 | 通过。无 `.env` 定向测试、数据库集成测试和全量门禁均通过；远端状态仍以新 CI 运行结果为准。 |
