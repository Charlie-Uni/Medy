# 实现记录 76：受限可回放载荷的加密存储（M3-07 收口，DEC-013）

- 日期：2026-09-25
- 授权：记录 74 B 部分，决策人 2026-09-25「同意」
- 范围：迁移 0015、`medops.core.envelope`、`medops.infrastructure.db.payloads`、`medops.application.payloads`、`payload_retention` CLI、`/v1/ask` 与回放的载荷写入、`GET /admin/traces/{trace_id}/payload`、设置与登录用户脚本、测试、文档

## 1. 决定与依据（记录 74 之外的实施细节）

| 决定 | 依据 |
| --- | --- |
| 信封加密在应用层：`seal()` 为每行生成 32 字节 DEK，AES-256-GCM（12 字节 nonce），关联数据 = `trace_id|node|kind`；DEK 用当前 KEK 包裹（同样 AES-GCM，附版本号）；`rewrap()` 轮换只重包裹 DEK | DEC-013；关联数据让同一密文不能被挪到别的 Trace 或 kind 下重放；密文不随轮换改变 |
| `KeyProvider` 协议 + `StaticKeyProvider`（测试）+ `LocalFileKeyProvider`（v1：JSON 密钥文件，拒绝 group / world 可读，校验 32 字节与 current 版本存在） | 记录 74 B.1；KMS / Vault 适配器随部署对象 |
| 写入路径：`/v1/ask` 与回放在**同一请求事务**里、Trace 写入之后写三类载荷（input / evidence_snapshot / model_output）；应用角色对 `trace_payloads` 只有 INSERT（无 SELECT） | 载荷存在 ⇔ Trace 存在；线上服务进程即使被攻破也读不回任何明文载荷 |
| 读取路径：`medops_restricted_role`（`DATABASE_RESTRICTED_URL`）+ 管理角色身份 + `purpose`（8–500 字）；先写 `payload_access_log` 再解密 | INV-OBS-03「分开存储、加密和授权」；访问可审计且不可篡改（追加写触发器） |
| 管理角色对 `trace_payloads` 无 SELECT，只能看访问日志 | 角色分离：管理数据库不等于看得到明文 |
| 保留期在清理规则里而不是在写入时：默认 `expires_at = created + 90 天`；清理跳过有未关闭升级的 Trace，已关闭升级的再保留 `handled_at + 30 天`；删除行即丢弃 DEK | 记录 74 B.4；升级何时关闭在写入时不可知 |
| `PAYLOAD_KEY_FILE` 未配置时只写 Trace 不写载荷（开发默认），受限读取路由 503 | 不让缺配置的部署悄悄写明文或用弱密钥 |
| 登录用户脚本增加可选的 `restricted` 用户（有 `DB_RESTRICTED_PASSWORD` 才创建） | 现有环境不因新增角色而断 |

## 2. 交付

- 迁移 0015：`trace_payloads`（FORCE RLS：应用 insert、受限 all）、`payload_access_log`（追加写；受限写、受限 / 管理读）、`medops_restricted_role`（含 traces / escalations 的只读策略，清理规则用）。本地 medops_v2、medops_v2_safety 已升到 0015。
- 代码：`medops.core.envelope`（seal / open_sealed / rewrap / payload_aad / 两个 KeyProvider）、`PgPayloadStore`（put / list / log_access / purge）、`PayloadWriter` / `PayloadReader` / `purge_expired`、`payloads_from_run`（节点输入、候选与证据快照含正文与哈希、答案 / 升级 / 复验结果）、`payload_retention` CLI（`--dry-run`）。
- API：`/v1/ask` 与 `/admin/traces/{id}/replay` 写载荷；`GET /admin/traces/{trace_id}/payload?purpose=`；契约 `TracePayloadResponse`，OpenAPI 与 schemas 重生成，`CONTRACTS.md` 增行。
- 设置：`PAYLOAD_KEY_FILE`、`DATABASE_RESTRICTED_URL`、`DB_RESTRICTED_PASSWORD`、`PAYLOAD_RETENTION_DAYS`、`ESCALATION_PAYLOAD_GRACE_DAYS`（`.env.example`、`DEPLOY.md`）。
- 测试：单元 `test_envelope.py`（往返、关联数据与密文篡改检测、轮换重包裹、退役旧 KEK、密钥文件权限与长度）、`test_payload_route.py`（问答写入三类载荷且密文不含明文、非管理 403 / 用途过短 400 / 无令牌 401 / 未写入 404、解密内容与访问日志）；集成 `test_payload_store.py`（应用角色只写不读、管理角色读不到载荷但能读日志、受限角色读 / 记日志 / 不能改、清理规则：过期删、未关闭升级留、关闭 5 天留、关闭 60 天删、日志追加写）；迁移与 RLS 期望更新。

## 3. 未做 / 限制

- 任务（worker）执行的 Trace 尚未写载荷：worker 走 `TaskRunner`，下一次触及 worker 时补同一写入（记录里的 `payloads_from_run` 可直接复用）。
- 密钥轮换只有库函数与规则，没有批量重包裹的 CLI；KMS / Vault 适配器随部署对象。
- 载荷读取路由本身未落 Trace（与管理路由同类），但每次读取都在 `payload_access_log`。
- 证据快照含条款正文：仍是受许可语料在加密存储里的副本，受同一保留期约束。

## 4. 自审（§9）

- 权限矩阵由真实 LOGIN 用户在 FORCE RLS 下证明（应用只写、受限读写日志、管理只读日志）。
- 明文只在受限连接的进程内存中出现且先记日志；密文与关联数据绑定，跨 Trace 挪用会失败。
- 保留与升级的关系用五个 Trace 的组合测试覆盖，删除即丢 DEK。
- 费用 0。

## 5. 进度

- M3-07 部分 → **已实现**（管理路由以领域审计行记录，已在 §3 说明）；P0 加权 58.9% → **59.5%**（47/79）；M3 9.5/13。
