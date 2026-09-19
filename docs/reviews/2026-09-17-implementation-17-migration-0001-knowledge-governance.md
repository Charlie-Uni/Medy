# 实现记录 17：首个迁移 0001 知识治理事实平面（M1-06、M1-07）与迁移工具落地（ADR-0006）

日期：2026-09-17。范围：按 [ADR-0006](../adr/ADR-0006-migration-tooling.md) 引入 Alembic + 原生 SQL + psycopg 3；交付首个迁移与 15 项针对 PostgreSQL 的集成测试；CI 增加数据库服务容器与 migration check；compose 固定 pgvector 镜像 digest。未建角色与 RLS（M1-08，下一轮）；未建 `tsvector`/`vector` 列；未修改基线、SPEC、Schema；未提交 Git。**状态：待 Codex 审核。**

## 1. 完成

### 1.1 工具与目录

- 依赖：`alembic 1.20.0`、`sqlalchemy 2.0.54`、`psycopg 3.3.5`（`psycopg-binary`），锁文件另增 `mako`、`markupsafe`；既有 pin 未动，`pip check` 无冲突。
- `alembic.ini`（无连接串）、`migrations/env.py`（URL 来源顺序：`MEDOPS_MIGRATION_URL` → `DATABASE_ADMIN_URL` → `DATABASE_URL`，规范为 psycopg 方言，每个 revision 独立事务）、`migrations/script.py.mako`、`migrations/versions/0001_knowledge_governance.py`。
- Makefile：`migrate`、`migrate-down`、`migration-check`、`test-integration`；lint/format/format-check 覆盖 `migrations/`。
- CI：`pgvector/pgvector:pg16` 服务容器 + `MEDOPS_TEST_ADMIN_URL`；步骤增加 `ruff` 覆盖 `migrations`、migration check（单一 head + 往返）。
- pytest 默认 `--tb=short`：长回溯会打印函数实参，集成测试的实参含带口令的 DSN。

### 1.2 迁移 0001 的实体（设计文档 3.3 命名，基线修正落点）

| 表 | 来源 | 与设计文档的差异 |
| --- | --- | --- |
| `source_objects` | 基线 3.3/4.2 新增 | `source_hash` 全局唯一、64 位十六进制校验；`storage_uri`、`byte_size`、`mime`、`integrity_status`；行不可删除，标识列不可改 |
| `ingestion_jobs` | 基线 4.2 新增 | `status`、`attempt`、`parser_version`、`extraction_params_hash`、`parse_quality`、`quality_score`、`failure_reason`；failed 必有原因，succeeded 的 parse_quality 不得为 pending；`(job_id, source_object_id)` 唯一以支撑复合外键 |
| `documents` | 设计文档 | 去掉 `source_hash`（改经 `source_object_id` 外键取得）；新增 `source_object_id`、`active_ingestion_job_id`、`parse_quality`、`language`；保留 `family_id`、`title`、`doc_type`、`version`、`status`、`effective_from/to`、`supersedes`、`owner_dept`、`created_by/at`、`status_changed_by/at`；`created_by`/`status_changed_by` 用 text 以容纳 surrogate id 或 HMAC 假名（INV-OBS-02） |
| `chunks` | 设计文档 | 保留 `page`、`section`、`seq`、`content`；新增 `chunk_content_hash`；**不建** `tsv tsvector` 与 `embedding vector(1024)`（3.1 DEC-001、3.8 DEC-002） |
| `chunk_spans` | SPEC 第 6 节 | chunk 的 `(page, char_start, char_end)` 片段，命中规则的依据 |
| `document_acl` | 设计文档 | `(doc_id, dept, permission)` 主键，加 `granted_by/at` |
| `doc_audit` | 设计文档 | `id, doc_id, action, from_status, to_status, actor, reason, details, occurred_at`；追加写 |

`evidence_log`（M2-05）、`outbox_events`（M1-11）、`tasks/traces/escalations/policies` 等按基线"数据模型分批建"随其里程碑追加。

### 1.3 数据库强制的规则

| 规则 | 机制 |
| --- | --- |
| INV-DATA-02 同一 family 至多一个 active | `documents_one_active_per_family` 部分唯一索引 |
| 3.4 active 必有 `effective_from`；`effective_to > effective_from`；非 draft 必有 `effective_from` | CHECK 约束 |
| INV-DATA-05 active 必须 `parse_quality = trusted` 且指向 succeeded 的入库任务，任务属于同一 source object，任务的 parse_quality 与文档一致 | CHECK + 复合外键 `(active_ingestion_job_id, source_object_id)` + BEFORE 触发器 |
| INV-DATA-04 来源不可变、chunk 不可变、文档标识列不可变、非 draft 不可删除 | BEFORE UPDATE/DELETE 触发器 |
| 状态机 draft → active → archived 单向 | BEFORE UPDATE 触发器 |
| 状态变更必须有会话身份并写审计 | 需 `SET LOCAL medops.actor`（缺失即拒绝，`insufficient_privilege`）；AFTER UPDATE 触发器同事务写 `doc_audit`，`medops.reason` 可选 |
| 审计追加写 | `doc_audit` 的 UPDATE/DELETE 触发器拒绝 |
| `chunk_content_hash = SHA-256(UTF-8 content)` | BEFORE INSERT 触发器校验或填充，与 Python `hashlib` 结果一致有测试 |
| 版本链 | `supersedes` 自引用外键、唯一、不得自指 |

## 2. 验证

```text
tests/integration/test_migrations.py -> 15 passed（约 2～3 秒，临时数据库自动创建与删除）
  单一 head；空库 upgrade→downgrade→upgrade 后表/枚举/函数清单一致且 downgrade 后无残留
  无 vector/tsvector 列；部分唯一索引定义含 UNIQUE + WHERE status='active'
  同 family 第二个 active 被拒；两会话并发激活：第二个在首个未提交时阻塞 1 秒以上、首个提交后以 UniqueViolation 失败，最终只剩一个 active
  active 缺 effective_from / 缺任务 / low_trust / 任务质量不一致 / 任务未 succeeded / 任务属他源 / 生效窗倒置 各自被对应约束或触发器拒绝；archived 同样要求 effective_from
  source_objects 哈希唯一、非法哈希拒绝、四个标识列不可改、不可删、状态列可改
  documents 四个标识列不可改，title 可改
  无 actor 的状态变更被拒且无审计行；有 actor 时写入 status_changed_by/at 与审计行（含 reason）；active→draft、archived→active/draft、draft→archived 均拒绝
  审计行不可改不可删；非 draft 不可删；draft 删除级联 chunks、chunk_spans、document_acl
  chunk 哈希校验/填充、(doc_id, seq) 唯一、chunk 与 span 不可改、span 非空区间
  ACL 主键去重、非法部门拒绝
无数据库时：15 skipped，原因 "PostgreSQL unreachable ...; start it with `make up`"
make migration-check -> single head；2 passed
make migrate（走 Settings 的 DATABASE_ADMIN_URL）-> 本机开发库升到 0001 (head)：8 张表（含 alembic_version）、4 个 documents 索引、9 个触发器
env -u PYTHONPATH make check -> ruff 通过；format-check 85 文件；mypy 39 文件；pytest 302 passed（287 单元 + 15 集成）；schemas 无漂移
compose：pgvector 镜像固定为 sha256:ccc6e83d…4d6b 后 `make up` 收敛 healthy，开发库数据保留
```

## 3. 未完成

- M1-08：应用角色（`NOSUPERUSER NOBYPASSRLS`、非表 owner）、`FORCE ROW LEVEL SECURITY`、按 `document_acl` 与状态/生效时间的策略、连接池身份切换与零泄漏/零静默不足测试。下一轮。
- M0-04 的安全测试阶段随 M2 安全集加入；远端 CI 首次运行仍待提交推送。
- `mypy` 未覆盖 `migrations/`（配置 `files = ["src"]`），仅 ruff 检查。

## 4. 下一轮（M1-08）需要决策人确认的方案

迁移里只创建 **NOLOGIN 组角色**并授权：`medops_app`（业务读写受 RLS 约束）、`medops_readonly`（MCP，只读）、`medops_admin_role`（管理与审核，绕过策略但仍非 superuser）；**LOGIN 用户由部署脚本按环境创建并 GRANT 对应组角色**，口令只在 `.env`/secret manager，不进入任何 revision。表 owner 保持迁移角色，业务角色不拥有表，从而 `FORCE ROW LEVEL SECURITY` 对其生效。请确认或调整。

## 5. Codex 审核焦点

- 触发器与 CHECK 的分工：`parse_quality` 一致性放在触发器而非生成列的取舍；`medops.actor` 用 `current_setting` 读取的安全边界（M1-08 将由 RLS 同一机制注入身份）。
- `_split` 只处理 `$$` 与单引号，是否有 SQL 形态会被误切（当前所有语句块已离线校验括号与引号成对）。
- `downgrade` 是否真正干净（测试断言表、枚举、`medops_` 函数为空；未断言序列/注释）。
- 并发测试用 1 秒观察窗判断"阻塞"是否足够稳健，或改用 `pg_stat_activity.wait_event` 断言。
- `tests/integration` 进入默认 `make test`：本机无 Docker 的开发者会看到 15 个带原因的 skip，是否可接受。

## 6. 自审（基线 §9）

1. 需求：只覆盖 M1-06/07 与 ADR-0006 约定；未加检索、权限、业务逻辑；未建向量/词法列。
2. 逻辑：所有规则在数据库层，且每条有正反测试；并发用真实两连接验证。
3. 安全：连接串不进配置文件与日志（`--tb=short`）；迁移以管理员执行、应用角色下一轮建立；`.env` 忽略。
4. 契约：字段名与基线 3.4 一致（`status`、`effective_from/to`、`source_object_id`、`active_ingestion_job_id`、`parse_quality`、`integrity_status`、`chunk_content_hash`）。
5. 测试：正常、边界、失败、并发、往返、无库跳过均覆盖。
6. 可观测：审计行自动产生，含 actor 与 reason。
7. 简洁性：一个 revision、一个 env.py、一个 conftest；未加 ORM。
8. 验证：见第 2 节；未验证项：远端 CI。
9. Checklist：基线勾选保持 0；路线图与知识对照 M0-01/03/04、M1-06/07 按证据更新。
