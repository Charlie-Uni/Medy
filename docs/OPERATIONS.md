# 运维手册：数据保留与删除、密钥轮换、备份恢复、依赖升级（M5-06，记录 87）

适用范围：P0 部署（单 PostgreSQL、单 Redis、API / worker / MCP 三类进程，`docs/DEPLOY.md`）。每节都是可照做的步骤 + 验证方法；数字来自决策记录 86（2026-09-26）。事故处置与发布操作见 `docs/RUNBOOK.md`。

## 1. 数据保留与删除

### 1.1 保留期（决策 86 第 4 项）

| 数据 | 保留 | 删除方式 | 执行角色 |
| --- | --- | --- | --- |
| 受限可回放载荷 `trace_payloads` | 90 天（`PAYLOAD_RETENTION_DAYS`）；有升级案的 Trace 保留到升级关闭后 30 天（`ESCALATION_PAYLOAD_GRACE_DAYS`） | `python -m medops.application.payload_retention`（每日） | `medops_restricted_user` |
| Trace、span、反馈、回放记录、Loop 案例 | 365 天（`TRACE_RETENTION_DAYS`，下限 90） | `python -m medops.application.retention`（每周） | `medops_admin_user` |
| 升级记录 `escalations` | 365 天，**且只删已关闭的**；未关闭的升级连同其 Trace 一直保留 | 同上 | 同上 |
| 有补文档工单的案例及其 Trace | 保留到工单终态后再按上表 | 同上（工单存在即跳过） | 同上 |
| 载荷访问日志 `payload_access_log`、补文档工单 `document_requests`、策略与发布日志、文档审计 `doc_audit` | 永久 | 不删 | — |
| 主体假名 `principals` | 账号停用时 `active=false`；删除 = 假名替换（见 1.3） | 手工 SQL（管理角色） | `medops_admin_user` |

保留期以外的一切表对所有角色保持追加写（迁移 0011 / 0016 / 0017 触发器）。迁移 0019 只开了一条受控路径：事务内设置 `medops.retention_purge = on` 与 `medops.retention_days = N`（触发器强制 N ≥ 90）时，管理角色才能删除早于 N 天的行。`retention` CLI 就是这个事务；任何其他代码路径删不掉审计行。

### 1.2 执行

```bash
# 先看会删什么（回滚，不落盘）
python -m medops.application.retention --dry-run
# 正式执行（默认 TRACE_RETENTION_DAYS）
python -m medops.application.retention
# 载荷（每日）
python -m medops.application.payload_retention --dry-run
python -m medops.application.payload_retention
```

输出是 JSON：候选 Trace 数与各表删除行数。验证：`select min(created_at) from traces` 不早于保留期；`select count(*) from escalations where status <> 'closed' and created_at < now() - interval '365 days'` 的行仍存在（它们不该被删）。

### 1.3 删除请求（数据主体）

系统不存原始身份，只存 HMAC 假名（INV-OBS-02）。收到删除请求时：(1) 由 IdP 侧确认主体；(2) 管理角色把 `principals.active` 置 false 并把 `sub_pseudonym` 替换为随机值（Trace 里的假名随之失去可关联性，行本身按保留期自然过期）；(3) 该主体的受限载荷立刻按 Trace 清除（`delete from trace_payloads where trace_id in (select trace_id from traces where principal = <旧假名>)`，受限角色）；(4) 在 `payload_access_log` 之外另建工单记录（工单系统 P1，现阶段用 `document_requests` 之外的运维记录）。不承诺物理删除审计行：升级记录与访问日志是合规证据。

## 2. 密钥轮换

### 2.1 载荷加密主密钥（KEK，DEC-013）

密钥文件 `PAYLOAD_KEY_FILE`：`{"current": "k2", "keys": {"k1": "<base64 32B>", "k2": "<base64 32B>"}}`，mode 0600，由部署注入。

1. 生成新密钥：`python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`。
2. 把新版本加入 `keys` 并把 `current` 指向它；**旧密钥先保留**（解包裹旧行需要）。
3. 滚动重启 API 与 worker（新写入立即用新 KEK；读取按行上记录的版本选密钥，不受影响）。
4. 重包裹存量：`python -m medops.application.payload_rotation --dry-run` 看 `stale_before`，再去掉 `--dry-run` 执行，直到 `stale_before = 0`。只有 `dek_wrapped` / `kek_version` 两列变化（迁移 0019 触发器与列级授权保证），密文不动，过程中不解密任何载荷、不写访问日志。
5. 确认 `select kek_version, count(*) from trace_payloads group by 1` 只剩新版本后，从文件里删除旧密钥，再滚动重启一次。

回滚：只要旧密钥还在文件里，把 `current` 改回去并重启即可；已重包裹的行用新密钥解，未重包裹的用旧密钥解，两者并存无害。

### 2.2 数据库口令

`make db-users` 按 `.env` 里的 `DB_*_PASSWORD` 创建 / 轮换六个 LOGIN 用户（app / readonly / admin / restricted / loop 与迁移用户）。轮换顺序：改 `.env` → `make db-users` → 依次重启 API、worker、MCP、Loop 定时任务。旧口令立即失效，因此先在低峰期做，并在重启前确认新口令能连上（`psql` 或 `python -c "import psycopg; psycopg.connect(...)"`，不要把 DSN 打到日志）。

### 2.3 身份假名密钥 `IDENTITY_PSEUDONYM_KEY`

轮换会让所有历史假名失效（Trace、principals、feedback 都以假名关联）。因此只在密钥泄露时轮换，且必须同时：导出 `principals` 的旧假名 → 新假名映射（由 IdP 侧 `sub` 重算），用映射更新 `principals.sub_pseudonym`；历史 Trace 的假名不改（保留期内视为孤儿）。这是有损操作，需决策人签字。

### 2.4 OIDC 签名密钥

由 IdP 轮换；API 通过 JWKS（`OIDC_JWKS_URL` 或静态 `OIDC_JWKS_JSON`）取新公钥。静态 JWKS 部署必须在 IdP 轮换前先把新公钥加进 `OIDC_JWKS_JSON` 并重启。

## 3. 备份与恢复

### 3.1 备份

```bash
DATABASE_ADMIN_URL=<管理 DSN> python scripts/db_backup.py --db medops --out /backups
```

`pg_dump -Fc` 在 Postgres 容器内执行，产物 `<db>-<UTC 时间>.dump` 与同名 `.sha256`。频率：每日一次（P0 的 RPO = 24 小时；连续归档与异地副本是 P1）。Redis 是检索缓存，可丢失，不备份；模型缓存卷可重建。备份文件含加密载荷的密文与已包裹的 DEK，但不含 KEK——**密钥文件必须单独、异地备份**，否则备份里的载荷无法解密（其他表不受影响）。

### 3.2 恢复演练（每月一次，且每次迁移上线前一次）

```bash
DATABASE_ADMIN_URL=<管理 DSN> python scripts/db_restore_drill.py --dump /backups/<file>.dump --source medops
```

脚本把 dump 恢复到 `<db>_restore_drill`，比对 alembic 版本、表集合、每表行数、语料指纹（chunk 哈希的 md5）与角色授权，写 `report.json` / `report.md`，最后**总是**删掉演练库。2026-09-26 在本机 medops_v2 上的演练结果见 `evals/harness/runs/2026-09-26-backup-drill-v1/report.md`。

### 3.3 真正恢复（P0：迁移失败回退或数据卷损坏）

1. 停 API / worker / MCP（`docker compose stop api worker mcp` 或 systemd 等价物），确认没有写入。
2. 若是迁移失败：优先 `alembic downgrade <上一版本>`（所有迁移都有 DOWN 且经往返测试）；只有 DOWN 也失败时才恢复备份。
3. 恢复：`create database medops_new` → `pg_restore -d medops_new --no-owner`（容器内）→ 用 3.2 的比对脚本核对 → `alter database medops rename to medops_broken; alter database medops_new rename to medops`。
4. 起服务，跑 `/readyz`，用 `evals/harness/tools/smoke_ask.py --ids ms-0001` 或记录 67 的端到端脚本做一次真实问答。
5. RTO 目标：1 小时内（本机演练 11k chunk 恢复用时见报告，秒级）。丢失的是备份点之后的 Trace / 任务 / 反馈：在事故记录里如实写明窗口。

P1 完整灾备（异地、连续归档、演练恢复整套环境）不在本手册范围（基线 7.1）。

### 3.4 PostgreSQL 16 → 17 / BM25 切换与回滚

`pg_textsearch` 只支持 PostgreSQL 17/18，且必须在服务器启动前加入 `shared_preload_libraries`。禁止把 PG16 的物理 data directory 直接挂给 PG17；使用逻辑 dump/restore。仓库镜像 `deploy/postgres/Dockerfile.pg17-bm25` 固定 PG17/pgvector 基础镜像 digest、`pg_textsearch` 1.5.1 及 amd64/arm64 发布资产 SHA-256。

切换顺序：

1. 停止应用写入，为每个数据库运行 `scripts/db_backup.py`，核对 `.dump.sha256`。
2. 在独立端口和新命名卷启动 PG17 镜像。先在临时空库运行 `alembic upgrade head`，确认扩展能加载并创建集群级 group roles，然后删除临时库。
3. 创建目标数据库，以 `pg_restore --no-owner --exit-on-error` 恢复。升级前逐库比较：Alembic revision、public 表集合、逐表行数、按 chunk_id 排序的语料指纹和 grantee；任何一项不同都停止切换。
4. 对目标库运行 `alembic upgrade head`，确认 revision 0022；运行 `make lexical-index ACTOR=<切换记录> ADMIN_URL=<目标管理 DSN>`。正式库和安全库分别运行 `make index-check`、`make retrieval-check`。
5. 用 app/readonly LOGIN 用户分别设置 MA/PV/CO 事务身份，做一次零模型词法查询；核对每个部门只能读取自己的 BM25 表，并确认 `retrieval_version` 为 `19c755…e4d1`。
6. 停旧 PG16，保留旧卷；让默认 5432 指向新卷并再次运行覆盖、readiness、`make check`。至少保留旧卷和切换前 dump 到新版本观察期结束。

快速回滚有两层：

- **代码/检索回滚：** migration 0022 没有删除 migration 0007 的 `chunk_lexical_tsv`。将生产装配和检索版本恢复到 A2，再失效候选缓存；不要在 BM25 代码仍运行时直接 downgrade 0022。
- **数据库主版本回滚：** 在没有 PG17 新写入，或新写入已另行回灌的前提下，停服务并把 5432 切回保留的 PG16 卷。发生新写入后不能直接切旧卷，必须先停写、逻辑导出 PG17 增量/全库并在 PG16 兼容 schema 中恢复验证。

未来升级 `pg_textsearch` 二进制时，所有副本必须先安装并重启到新二进制，再升级主库；`shared_preload_libraries` 对 WAL 回放同样是必需配置。每次升级重跑 extension version、RLS/统计隔离、索引读写、备份恢复和 `make check`。

## 4. 依赖升级

- Python 依赖全部锁定并带哈希（`requirements.lock`、`requirements-build.lock`、`requirements-embed*.lock`）。升级流程：改 `pyproject.toml` 约束 → `make lock`（uv 解析，含 Linux 镜像锁）→ `make install` → `make check` → 记录在实现记录里（版本、原因、`make check` 结果）。不要手改 lock 文件。
- 模型权重：`RERANK_REVISION` / 嵌入模型 revision 钉在代码里；换 revision = 检索版本变化 = 走 M4 候选评测与发布，不是依赖升级。
- 容器镜像：compose 里 Postgres / Redis 用 digest 钉住；升级要同时改 tag 与 digest，跑 `make up` + 迁移 + 3.2 的恢复演练（新版本能恢复旧 dump）。
- 安全公告：`pip-audit`（P1 接入 CI 前手动跑）；有 CVE 时按上面流程升级，或在记录里写明为何不升级。
- 每次升级后必跑：`make check`、一次真实问答冒烟、`/metrics` 有输出。

## 5. 定时任务一览

| 频率 | 命令 | 角色 |
| --- | --- | --- |
| 每日 | `python -m medops.application.payload_retention` | restricted |
| 每日 | `python scripts/db_backup.py` | 管理 DSN |
| 每周 | `python -m medops.application.retention` | admin |
| 每月 | `python scripts/db_restore_drill.py --dump <最新>` | 管理 DSN |
| 每季或泄露时 | KEK 轮换（2.1）；口令轮换（2.2） | 见各节 |
| Loop 定时 | `observe → reflect run → tickets → adapt propose`（`docs/DEPLOY.md`） | loop |
