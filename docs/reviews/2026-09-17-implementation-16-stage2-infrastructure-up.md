# 实现记录 16：阶段 2 启动，本机基础设施拉起验证（M0-11 部分证据）与迁移工具选型请示

日期：2026-09-17。范围：决策人安装 Docker Desktop 后，用仓库现有 `docker-compose.yml` 在本机拉起 PostgreSQL/pgvector 与 Redis，取得 M0-11 的启动、健康与重启持久化证据；登记 M1-06/07/08 开工前必须由决策人确定的迁移工具选型。未修改基线、SPEC、Schema、代码；未提交 Git。**状态：环境验证完成；迁移工具待决策人批复后开工。**

## 1. 环境

| 项 | 实测 |
| --- | --- |
| Docker Desktop | 引擎 29.8.0（linux/arm64），Compose v5.5.1，8 CPU，约 8.3 GB 内存 |
| CLI 位置 | 安装器未把 `docker` 链接到 `/usr/local/bin`（需管理员权限），本轮使用应用内置 CLI `/Applications/Docker.app/Contents/Resources/bin/docker`，未改动系统 PATH。若要在终端直接用 `docker`，可在 Docker Desktop 设置里启用系统级 CLI 安装或自行建符号链接 |
| `.env` | 由 `.env.example` 生成，口令与假名密钥为本机随机值，文件在 `.gitignore`（已用 `git check-ignore` 确认），`Settings` 可加载 |

## 2. `make up` 结果

```text
docker compose --env-file .env up -d --wait  -> 约 20 秒，两个容器 Healthy
medops-postgres  pgvector/pgvector:pg16  -> PostgreSQL 16.15 (Debian, aarch64)，vector 0.8.6，max_connections 100
                 镜像 digest sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b（本轮实测，compose 中仍为标签）
medops-redis     redis:7.2-alpine@sha256:ccd6aa8d…28ed -> redis_version 7.2.16，appendonly yes，PONG
命名卷 medops_postgres_data、medops_redis_data 存在；端口仅绑定 127.0.0.1
```

重启持久化：在 PostgreSQL 建临时表并插入一行、在 Redis 写一个键，`docker compose restart postgres redis` 后两者均读回原值，随后清理。健康检查在重启后 6 秒内恢复 healthy。

新库初始状态：仅存在 `medops_admin`（superuser、bypassrls 均为真），public schema 0 张表。这符合基线 3.7 的前提：应用角色（`NOSUPERUSER NOBYPASSRLS`、非表 owner）、`FORCE ROW LEVEL SECURITY` 与管理/业务角色分离必须由 M1 的 migration 建立，不能沿用管理员连接。

## 3. M0-11 状态

已取得：一条命令启动基础设施、健康检查、命名卷持久化、重启恢复、镜像 digest。仍缺：API 与 worker 服务（随 M3 代码加入）、对象存储（DEC-007）、可选观测组件、远端 CI 中的容器化集成测试。保持"部分"，不勾选。

## 4. 迁移工具选型，待决策人批复（阻塞 M1-06/07/08 开工）

基线没有指定 migration 工具，只要求"migration 前向可执行且有回滚/修复方案"、关键约束"必须使用 migration 和集成测试证明"（4.2、5.12）。两个候选：

| 方案 | 内容 | 新增依赖 | 利 | 弊 |
| --- | --- | --- | --- | --- |
| A（建议） | Alembic 管版本与升降级，revision 内用原生 SQL（`op.execute`）写 DDL、角色、RLS 策略；驱动 psycopg 3；不引入 ORM 模型 | `alembic`、`sqlalchemy`（仅 Core，Alembic 依赖）、`psycopg[binary]` 三个运行时依赖 | 版本链、`upgrade/downgrade`、`alembic check` 现成，正好补 M0-03 的 migration check；知识对照 M1-06 本就写着 Alembic；后续 API 层无论如何需要驱动与查询构造 | 依赖体积增加；SQLAlchemy 只用到很小一部分 |
| B | 仓库自写极简 runner：`migrations/NNNN_*.sql` 加 `NNNN_*.down.sql`，一张版本表记录已应用项 | 仅 `psycopg[binary]` | 依赖最少，SQL 完全透明 | 自造轮子；回滚、校验、并发保护都要自己写并测试，审核成本反而更高 |

建议 A。连带约定（同样待批）：
1. 迁移目录 `migrations/`（基线 4.1 已列），Alembic 环境读取 `DATABASE_ADMIN_URL`；应用运行时只用 `DATABASE_URL` 对应的受限角色。
2. 集成测试目录 `tests/integration/`，通过环境变量指向本机 compose 库；无数据库时按明确原因跳过，并在 CI 增加 PostgreSQL 服务容器（pgvector 镜像）使其在远端必跑，不留"未解释跳过"。
3. 首个迁移只建 M1-06 列出的表与 M1-07 的 active 唯一约束，不建 `vector` 列（3.8：DEC-002 前不锁维度）。
4. 是否同样把 `pgvector/pgvector:pg16` 的 digest 写进 compose（本轮实测值见上）。

## 5. 自审（基线 §9）

1. 需求：只做环境验证与选型登记；未建表、未写迁移。
2. 逻辑：重启验证覆盖两个服务；口令不在输出中出现。
3. 安全：`.env` 已忽略；端口仅本机；未创建任何额外角色。
4. 契约：无变化。
5. 测试：无代码变更；`make check` 保持 287 passed。
6. 可观测：无新增运行时路径。
7. 简洁性：未新增文件或抽象，compose 未改。
8. 验证：见第 2 节；未验证项：远端 CI。
9. Checklist：基线勾选保持 0；路线图 M0-11 行按证据更新。
