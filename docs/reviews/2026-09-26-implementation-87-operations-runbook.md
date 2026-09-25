# 实现记录 87：M5-06 / M5-07——保留与删除、密钥轮换、备份恢复、依赖升级手册与运维 Runbook

- 日期：2026-09-26
- 授权：决策请求记录 86（决策人 2026-09-26「可以 继续」：六项按建议；先做 M5-06 + M5-07）
- 范围：迁移 0019、`medops.application.retention`（审计保留清理）、`medops.application.payload_rotation`（KEK 重包裹）、`scripts/db_backup.py` / `scripts/db_restore_drill.py` 与一次真实恢复演练、`docs/OPERATIONS.md`、`docs/RUNBOOK.md`、测试
- 费用：0

## 1. 决定与依据

| 决定 | 依据 |
| --- | --- |
| 审计表对所有角色保持追加写，只开一条受控删除路径：事务内 `medops.retention_purge = on` 且 `medops.retention_days = N`（触发器强制 N ≥ 90）时，管理角色才能删早于 N 天的行；升级记录只删已关闭的；有工单的案例及其 Trace 不删；`payload_access_log`、`document_requests` 永久 | 决策 86 第 4 项（365 天）；基线 5.10「上线前必须完成保留期决策」；把「谁在什么条件下能删」写进触发器而不是应用代码 |
| `retention` CLI 就是那个事务：按外键顺序 载荷 → 案例 → 回放 → 反馈 → 升级 → span → Trace，`--dry-run` 回滚 | 删除顺序必须与外键一致；候选集一次算好（临时表）避免中途漂移 |
| 载荷行只能以「KEK 重包裹」方式更新：受限角色得到 `dek_wrapped` / `kek_version` 两列的列级 UPDATE，触发器要求其余列全等；`payload_rotation` CLI 分批重包裹到 `stale = 0`，过程不解密载荷、不写访问日志 | DEC-013 密钥轮换的登记后续；密文不动是信封加密的意义 |
| 备份 = 容器内 `pg_dump -Fc` + sha256；恢复演练 = 恢复到 `<db>_restore_drill`，比对 alembic 版本 / 表集合 / 逐表行数 / 语料指纹 / 授权角色，最后总是删演练库 | 基线 7.1：P0 只要求迁移恢复方案与可演练的备份恢复；KEK 文件必须单独异地备份（备份里只有密文与已包裹 DEK） |
| 假名密钥轮换记为有损操作、需签字；数据主体删除 = 假名替换 + 载荷即时清除，不物理删审计行 | INV-OBS-02；升级记录与访问日志是合规证据 |

## 2. 交付

- 迁移 0019（本地两库已升级）：`medops_retention_purge_allowed()`、带保留期的追加写守护（traces / trace_spans / feedback / replays）、升级与案例守护的删除分支、`medops_payload_rewrap_guard()`、管理角色的 DELETE 授权与策略、受限角色的列级 UPDATE 授权；DOWN 全部还原（往返测试通过）。
- CLI：`python -m medops.application.retention [--days] [--dry-run]`（`TRACE_RETENTION_DAYS=365`）；`python -m medops.application.payload_rotation [--batch] [--dry-run]`。
- 脚本：`scripts/db_backup.py`、`scripts/db_restore_drill.py`（`backups/` 已忽略）。
- 文档：`docs/OPERATIONS.md`（保留期表、执行与验证、删除请求、四类密钥轮换、备份与恢复、依赖升级、定时任务表）；`docs/RUNBOOK.md`（服务健康、事故四级、七条告警处置、人工升级处理、Loop 日常、发布 / 灰度 / 回滚操作与检查单、变更窗口、事故记录模板）。
- 测试：`tests/integration/test_retention_and_rotation.py`（无 GUC 时管理角色删除被拒、90 天下限、应用角色无权；清理保留未关闭升级与有工单案例，dry-run 不落盘；轮换后 `kek_version` 变、密文不变、仍可解密，改密文被触发器拒、改其他列无权限）；`test_payload_store.py` 更新为「可重包裹、不可改内容」；迁移期望 0019。

## 3. 恢复演练（本机 medops_v2，2026-09-26）

`evals/harness/runs/2026-09-26-backup-drill-v1/report.md`：dump 66.8 MB（sha256 记录在案），恢复到 `medops_v2_restore_drill` 用时 88 秒，alembic 0019，34 张表、63,293 行；表集合、alembic 版本、逐表行数、语料指纹（chunk 哈希 md5）、授权角色全部一致；演练库已删。RTO 目标 1 小时在本机规模下有两个数量级余量。

## 4. 未做 / 限制

- 连续归档、异地副本、整套环境的灾备演练是 P1（基线 7.1）。
- `pip-audit` 未进 CI；依赖安全公告目前手动跑。
- 观察窗内的自动安全回归检查（记录 85 §4）与告警的自动投递（P1）未做，Runbook 里的告警是「看指标 → 处置」的人工流程。
- 数据主体删除流程没有工单系统承接（P1），现阶段记在运维记录里。

## 5. 自审（§9）

- 删除路径的每个条件（GUC、下限、未关闭升级、工单、角色）都有对应断言；不存在无 GUC 的删除方式。
- 轮换用真实受限用户在 FORCE RLS 下证明「只能改两列、密文不动、仍可解密」。
- 备份 / 恢复用真实容器与真实库做了一次完整往返并比对五项指纹。
- 费用 0；`make check` 通过。

## 6. 进度

- M5-06、M5-07 → **已实现**。
- P0 加权进度 73.4% → **75.9%**（60/79）；按 99 项计 60.6%；M5 2/8。
