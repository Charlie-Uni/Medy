# 实现记录 18：迁移 0002 角色、授权与行级安全（M1-08；M1-04 权限部分）

日期：2026-09-17。范围：按决策人批准的角色方案（本日"可以，那就继续吧"，方案见记录 17 第 4 节）交付迁移 0002、登录用户供应脚本、37 项针对真实 LOGIN 用户的集成测试，并把本机开发环境切换到受限应用用户。未接线 API 层身份注入（M3）、未做候选对比实验（M1-04/05）；未修改基线、SPEC、Schema；未提交 Git。**状态：待 Codex 审核。**

## 1. 完成

### 1.1 迁移 0002（[migrations/versions/0002_roles_and_rls.py](../../migrations/versions/0002_roles_and_rls.py)）

- 组角色（NOLOGIN、NOSUPERUSER、NOBYPASSRLS、NOCREATEDB、NOCREATEROLE，仅缺失时创建，降级不删除）：`medops_app`、`medops_readonly`、`medops_admin_role`。
- 身份函数 `medops_current_dept()`：读事务级 `medops.dept`，未设置返回 NULL，所有策略随之为假，即默认拒绝（INV-AUTH-01）。非法值（如 `HR`）在类型转换处报错，不会放行。
- 授权：app 与 readonly 只有 `documents`、`chunks`、`chunk_spans`、`document_acl`、`source_objects` 的 SELECT；admin 有知识表的 SELECT/INSERT/UPDATE、documents 与 document_acl 的 DELETE、doc_audit 的 SELECT/INSERT、序列使用权；无人获得 schema 的 CREATE。
- 七张表全部 `ENABLE` 且 `FORCE ROW LEVEL SECURITY`。策略：document_acl 只见本部门行；documents 只见非 draft 且本部门有 read 授权的版本；chunks 经 documents、chunk_spans 经 chunks、source_objects 经 documents 递推；ingestion_jobs 与 doc_audit 对 app/readonly 无授权也无策略；admin 各表 `using (true)`。
- 表 owner 保持迁移角色，任何业务角色都不是 owner，因而不能 ALTER TABLE、改策略或关闭 RLS。

### 1.2 登录用户供应（[src/medops/infrastructure/db/login_users.py](../../src/medops/infrastructure/db/login_users.py)，`make db-users`）

按前缀创建或轮换 `<prefix>_app_user`、`<prefix>_readonly_user`、`<prefix>_admin_user`（LOGIN、NOSUPERUSER、NOBYPASSRLS、NOCREATEDB、NOCREATEROLE、INHERIT），加入对应组；口令来自 `Settings`（`DB_APP_PASSWORD`、`DB_READONLY_PASSWORD`、`DB_ADMIN_PASSWORD`），不打印；组角色不存在时拒绝并提示先跑迁移；重复执行为幂等且轮换口令。`.env.example` 增加三个键与说明。

### 1.3 本机环境

`make migrate` 把开发库升到 0002；`make db-users` 创建三个用户；`.env` 的 `DATABASE_URL` 已改为 `medops_app_user`，`DATABASE_ADMIN_URL` 保持管理员只供迁移与供应脚本。验证：以应用用户连接 `current_user=medops_app_user`、非 superuser、非 bypassrls；无身份时 documents 可见 0 行；写 doc_audit 被拒。

## 2. 验证（[tests/integration/test_rls.py](../../tests/integration/test_rls.py)，37 项；连同迁移测试共 52 项集成测试）

种子：每部门 2 份 active、1 份 archived、1 份 draft（各带本部门 ACL），另 1 份 MA 与 PV 共享的 active；每份 2 个 chunk、各 1 个 span。测试通过真实 LOGIN 用户连接，不用 `SET ROLE`。

| 断言 | 结果 |
| --- | --- |
| 组角色与登录用户属性、组成员关系、七表 FORCE RLS、owner 不含任何业务角色 | 通过 |
| app/readonly 无身份：五张可读表 count 均为 0，按主键探测不返回行，ingestion_jobs/doc_audit 直接无权限 | 通过 |
| 三个部门 × 两种角色：可见文档集合恰等于"本部门 active+archived+共享"，chunks/spans/source_objects 一致，document_acl 只见本部门，按主键探测他部门文档返回空，本部门 draft 不可见 | 通过（6 组） |
| 身份作用域：`SET LOCAL` 随事务结束失效；会话级设置会跨请求泄漏，`RESET ALL` 与 `DISCARD ALL` 均能清除 | 通过 |
| 非法部门值报错而非放行；空值等于无身份 | 通过 |
| MA 可见 8 个 chunk：`order by ... limit 4` 恰 4 行且全部可见、`limit 100` 恰 8 行、带 join 与状态过滤的 `limit 3` 恰 3 行，无静默少取也无越界 | 通过 |
| app 与 readonly 各 11 种写入或提权尝试（插入/更新/删除各表、写审计、`SET ROLE` 到管理组、建表）全部 `insufficient_privilege` | 通过（22 组） |
| admin：看全部文档，非 superuser/bypassrls；无 actor 的状态变更被拒；有 actor 时激活 draft 并自动写审计（随后回滚）；关闭 RLS、去 FORCE、删策略、建策略、建表、给组角色加 BYPASSRLS/SUPERUSER、建角色全部被拒；`GRANT ... TO PUBLIC` 为无效果的告警型空操作，断言 PUBLIC 无授权 | 通过 |
| 供应脚本幂等且轮换口令：旧口令连接失败、新口令成功；缺口令拒绝 | 通过 |

`make check`：ruff 通过；format-check 90 文件；mypy 42 个源文件通过；pytest **339 passed**（287 单元 + 52 集成）；schemas 无漂移。迁移往返测试已扩展：升级后策略数大于 0 且七表 FORCE RLS，降级后策略为 0、组角色保留。

## 3. 未完成与边界

- 请求到 `SET LOCAL medops.dept` / `medops.actor` 的注入、连接归还池前的 `RESET ALL` 是 M3 API 层的接线，本轮只在测试中模拟。
- M1-04 的"词法候选对比 + 零静默候选不足"要等真实探针集与 DEC-001 候选适配器；本轮证明的是 RLS 在普通扫描、排序与 LIMIT 下的零泄漏与零少取，M1-04 记为部分。
- 状态与生效时间的证据过滤仍由查询承担（基线 3.4）；RLS 是部门与草稿边界。若后续需要"当前有效证据"的安全视图（3.7 备选），随 M1-18 加。
- 供应脚本的口令随 SQL 语句传输；服务器 `log_statement` 不应为 `all`，文档已注明。
- 组角色为集群级对象，降级不删除；CI 服务容器每次全新，不受影响。

## 4. Codex 审核焦点

- 策略递推（chunks 经 documents、spans 经 chunks、source_objects 经 documents）是否可能被规划器改写成绕过内层策略的形式（PostgreSQL 对 RLS 子查询按调用者身份评估，测试覆盖了 join 与 LIMIT，但未做 EXPLAIN 级别检查）。
- admin 用 `using (true)` 的宽策略而非 BYPASSRLS 的取舍；是否应进一步把 admin 拆成"入库写"与"审核改状态"两组。
- readonly 与 app 当前权限相同（都只读），差异在于 app 未来会获得 tasks/traces 的写权限；是否现在就该在名字之外体现区别。
- 测试用会话级 `set_config(..., false)` 模拟"忘了用 SET LOCAL"的错误用法并证明 `RESET ALL`/`DISCARD ALL` 能清除，是否足以覆盖连接池实现差异。

## 5. 自审（基线 §9）

1. 需求：只覆盖 M1-08 与 M1-04 的权限部分；未加业务逻辑，未改契约。
2. 逻辑：默认拒绝、部门边界、草稿不可见、身份作用域、LIMIT 不少取均有正反测试；管理角色的越权路径逐条验证。
3. 安全：口令不进版本文件与日志；应用连接不再使用管理员；owner 与业务角色分离。
4. 契约：`Settings` 新增三个可选 SecretStr 字段并纳入空值归一；`.env.example` 同步。
5. 测试：真实登录用户、六种部门×角色组合、22 组写入尝试、供应脚本轮换。
6. 可观测：状态变更审计沿用 0001 触发器。
7. 简洁性：一个 revision、一个脚本、一个测试文件；无新依赖。
8. 验证：见第 2 节；未验证项：远端 CI、API 接线。
9. Checklist：基线勾选保持 0；路线图与知识对照 M1-08 记为已实现（数据库层）、M1-04 记为部分。
