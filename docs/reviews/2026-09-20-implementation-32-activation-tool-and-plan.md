# 实现记录 32：文档激活工具（M1-11 首个切片）与激活提案

日期：2026-09-20。DEC-001 正式对比只差一件事：16 份文档在三台服务器上全部是 draft，普通角色查不到。本轮实现受审计的 draft→active 激活工具并附每份文档的 `effective_from` 提案；**未执行任何激活**，等待决策人逐项确认。

## 1. 编码前记录

- 目标：一次事务内、以 `medops.actor`/`medops.reason` 注入身份与理由，把 draft 文档转为 active 并写入 `effective_from`，由既有触发器记录 doc_audit；计划文件模式全有或全无。
- 不变量：INV-DATA-05（low_trust 不能 active）在工具层先拒绝，数据库 CHECK 仍是最后防线；同 family 已有 active 版本时拒绝，不用"顺手归档"替代 M1-11 的发布事务；不改样本、映射、索引。
- 范围：不含旧版归档、outbox、索引/缓存失效；这些仍是 M1-11 的剩余部分。

## 2. 实现

- [activate.py](../../src/medops/ingestion/activate.py)：`activate_document(conn, document_key, effective_from, actor=, reason=)`、`apply_plan(conn, entries, actor=)`（`effective_from: null` 的条目必须带 `flag`/`tier=blocked`，否则拒绝）、CLI `--admin-url --actor (--plan | --document-key --effective-from --reason)`；`make activate-docs PLAN= ACTOR= ADMIN_URL=`。
- 拒绝条件与消息：未知 `document_key`、非 draft、`parse_quality != trusted`（INV-DATA-05）、无 `active_ingestion_job_id`、同 family 已有 active、缺 actor/reason。
- 提案文件 [activation_plan.proposed.json](../../evals/experiments/lexical/preparation-v1/activation_plan.proposed.json)（`status=proposed_awaiting_owner_confirmation`）：按 M1-11 口径为 15 份 trusted 文档给出 `effective_from` 与依据层级；esomen 标 `blocked`。

## 3. 测试

- 集成 `tests/integration/test_activation.py`（5）：激活写入 status/effective_from/status_changed_by 与 doc_audit（from/to/actor/reason）；low_trust、非 draft、未知 key、空 actor 拒绝且不改动；同 family 第二版拒绝；计划模式跳过带 flag 的 null 条目、任一失败整体回滚、无 flag 的 null 拒绝；管理 LOGIN 用户可激活、app 用户 InsufficientPrivilege。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**647 passed**（511 单元 + 136 集成）。

## 4. 提案（需决策人逐项确认）

| 文档 | 部门 | 提议 effective_from | 依据层级 | 备注 |
| --- | --- | --- | --- | --- |
| tfda-label-zosaa-50mg | MA | 2015-10-27 | 文内修订日期（B版 104.10.27） | |
| tfda-label-deurinol-300mg | MA | 2026-07-20 | 许可证异动日期（export/36） | 无文内版本行；异动不一定对应本 PDF 修订，PDF 元数据为 2018-02-09，**请二选一** |
| tfda-label-loformin-850mg | MA | 2015-10-06 | PDF 元数据 | 无版本行、无异动记录 |
| tfda-label-cancliol-100mg | MA | 2015-12-27 | PDF 元数据 | 同上 |
| tfda-label-esomen-40mg | MA | 不激活 | low_trust（8 条抽取告警） | **选项 A** 保持 draft，pc-0025～0030 计 miss；**选项 B** 先处理抽取告警重新入库 |
| meddra-term-selection 4.26 | PV | 2026-03-01 | 文内发布月（取月初） | 站点日期 2026-03-14 备选 |
| meddra-data-retrieval 3.26 | PV | 2026-03-01 | 文内发布月（取月初） | 同上 |
| ema-gvp-module-vi-rev2 | PV | 2017-07-28 | 文内 | |
| ema-gvp-module-ix-rev1 | PV | 2017-10-09 | 文内 | |
| fda-sponsor-safety-reporting-2025 | PV | 2025-12-01 | 文内发布月（取月初） | |
| ich-e2a-step4-1994 | PV | 1994-10-27 | 文内 | |
| ich-e2f-step4-2010 | PV | 2010-08-17 | 文内 | |
| tfda-adr-report-form-guide-4th | PV | 2025-03-01 | 文内发布月（取月初） | |
| ich-e8-r1-step4-2021 | CO | 2021-10-06 | 文内 | |
| ich-e6-r3-step4-2025 | CO | 2025-01-06 | 文内 | |
| fda-protocol-deviations-draft-2024 | CO | 2024-12-01 | 文内发布月（取月初） | 草案文件 |

需要确认的三点：月份粒度按月初取值的约定；deurinol 取异动日期还是 PDF 元数据日期；esomen 选项 A 或 B。确认后我在三台服务器上以同一计划文件执行 `make activate-docs`，随后冻结运行清单并跑 75 条对比。

## 5. 自审（基线 §9）

1. 需求：只做工具与提案，未激活。
2. 逻辑：拒绝路径先于 UPDATE；计划模式单事务。
3. 安全：只允许管理角色；理由与身份进入审计。
4. 契约：不改 schema；使用既有触发器。
5. 测试：5 项集成；全量 647 passed。
6. 可观测：doc_audit 记录 from/to/actor/reason。
7. 简洁性：一个模块、一个 CLI、一个提案文件。
8. 验证：数字来自本轮 make check。
9. Checklist：M1-11 由待做转为部分（+0.5）；**进度 24.7%（19.5/79）；按 99 项计 19.7%**。
