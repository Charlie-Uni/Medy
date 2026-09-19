# ADR-0006：数据库迁移工具与集成测试约定

- 状态：已决（项目负责人 2026-09-17 批准"方案 A 加四点"）
- 关联：基线 4.1（`migrations/`）、4.2（关键约束必须用 migration 与集成测试证明）、3.7（角色分离）、3.8（DEC-002 前不锁向量维度）、M0-03（migration check）、M1-06/07/08
- 记录：[实现记录 16](../reviews/2026-09-17-implementation-16-stage2-infrastructure-up.md) 第 4 节提出，[实现记录 17](../reviews/2026-09-17-implementation-17-migration-0001-knowledge-governance.md) 落地

## 决定

1. **Alembic 管理版本与升降级，revision 内只写原生 SQL**（`op.execute`）：DDL、约束、触发器、角色与 RLS 策略都以 SQL 出现在版本文件里，可直接审阅；不引入 ORM 模型，不使用 autogenerate。驱动为 psycopg 3；SQLAlchemy 仅作为 Alembic 的依赖以 Core 形式存在。新增运行时依赖：`alembic`、`sqlalchemy`、`psycopg[binary]`（锁文件另带 mako、markupsafe、psycopg-binary）。
2. **迁移目录 `migrations/`**，配置 `alembic.ini` 不含任何连接串；`migrations/env.py` 依次取 `MEDOPS_MIGRATION_URL`（测试用）、`Settings.database_admin_url`、`Settings.database_url`，并把 URL 规范为 psycopg 3 方言。应用运行时只用受限角色的 `DATABASE_URL`；迁移是唯一以管理员身份执行的路径。每个 revision 独立事务。
3. **集成测试放 `tests/integration/`**：会话级 fixture 用管理员连接创建随机命名的临时数据库、`upgrade head`、结束后 `drop ... with (force)`；每个测试一个事务并回滚。找不到数据库时以明确原因跳过；CI 提供 `pgvector/pgvector:pg16` 服务容器并设置 `MEDOPS_TEST_ADMIN_URL`，使这些测试在远端必跑，不留"未解释跳过"。
4. **migration check** 定义为：`alembic heads` 恰好一个 + 在空库上 `upgrade head → downgrade base → upgrade head` 后对象清单一致。`make migration-check` 与 CI 均执行。
5. **首个迁移只建 M1-06 的表与 M1-07 的约束**，不建 `tsvector` 或 `vector` 列；DEC-001 选定后由新 revision 加词法索引，DEC-002 选定后加向量列。
6. **compose 镜像 digest**：Redis 已固定（ADR-0004 后续决定）；pgvector 镜像的实测 digest 记录在实现记录 16，是否写入 compose 与 Redis 一致由负责人在本 ADR 批复中一并同意，落地见实现记录 17。

## 不采用的方案

自写 SQL runner（仅 psycopg）：依赖最少，但版本表、回滚、并发保护与校验都要自造并测试，审核成本高于收益。

## 后果

- 数据库规则（唯一 active、生效时间、解析质量、不可变性、状态机、审计追加写）全部有集成测试证明，符合基线 4.2。
- 集成测试依赖本机 Docker 或 CI 服务容器；无数据库时开发者仍能跑全部单元测试。
- 后续 M1-08 的角色与 RLS、M1-11 的 outbox、M2 的 evidence_log 各自作为新 revision 追加，不修改已发布 revision。
