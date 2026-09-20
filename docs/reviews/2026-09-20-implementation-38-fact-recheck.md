# 实现记录 38：M1-18 事实回查（候选进入回答上下文前的数据库回查）

日期：2026-09-20。承接记录 37（修订 3 后 M1 其余切片继续）。本轮实现 M1-18：融合/重排后的候选 chunk 在成为 `Evidence` 之前，在携带可信部门身份的请求事务内回读 PostgreSQL 事实平面，逐项核对 ACL、状态、生效时间、来源完整性、解析质量、内容哈希与页锚点；不通过的候选连同原因一并返回，禁止进入回答上下文。

## 1. 编码前记录

- 目标（基线 3.3、3.4、3.7、5.2；INV-DATA-03/06/07；路线图 M1-18）：索引命中、融合排名与重排分数都不是事实；进入模型上下文前必须回查事实平面，"失效、越权、低可信或完整性失败的候选直接丢弃并记录原因"。
- 判定顺序固定：可见性（RLS 链 `chunks -> documents -> document_acl`，越权/草稿/撤回/不存在一律只报 `not_visible`，不区分原因）→ 状态（`active`；`archived` 仅在调用方显式允许历史且显式给出 `as_of` 时可用，并标 `historical`）→ 生效窗口（`effective_from <= as_of < effective_to`，`effective_to` 空为长期有效）→ `source_objects.integrity_status = verified` → `documents.parse_quality = trusted` → 应用侧重算 SHA-256 与 `chunk_content_hash` 比对（expected/observed 一并返回供日志）→ 至少一条 `chunk_spans` 页锚点。
- 失败关闭：无身份事务、连接角色不受 ACL 策略约束（superuser / BYPASSRLS / 管理角色成员）、非 UUID 的 chunk_id（适配器缺陷）均抛错，不返回"空结果"。
- 范围外：`evidence_log` 表与 Trace 落库（属 M2 Trace 存储）；裁剪片段的 `evidence_text_hash`（本轮证据文本即完整 chunk 内容，哈希由该文本计算）。

## 2. 实现

- [recheck.py](../../src/medops/retrieval/recheck.py)：`recheck_candidates(conn, chunk_ids, *, as_of=None, allow_historical=False) -> RecheckResult`；一条语句 `FACT_SQL` 在应用角色事务内回读（`documents` 内连接、`source_objects` 左连接、`chunk_spans` 存在性）；纯函数 `judge(row, as_of, allow_historical)` 给出第一条不通过原因；`evidence_from` 构造领域 `Evidence`（`Citation` 含 doc_id/version/effective_date/page/section/chunk_id，INV-DATA-06）。`RejectReason` 九种；`Rejection` 携带输入名次，仅 `content_hash_mismatch` 附带两个哈希；保持输入（融合名次）顺序；重复候选记 `duplicate`。
- `require_acl_enforced`：查 `pg_roles.rolsuper/rolbypassrls` 与 `pg_has_role(current_user, 'medops_admin_role', 'member')`，任一为真即拒绝运行（回查在这些角色下无意义）。
- 复用 `pg_lexical_common.require_identity`（事务内且已绑定 `medops.dept`）。

## 3. 测试

- 单元 [test_recheck.py](../../tests/unit/retrieval/test_recheck.py)：健全行通过并生成正确引用；13 个参数化用例逐条规则各得其原因；窗口边界（`from <= as_of`、`to > as_of`）；多重缺陷时按文档顺序取第一条；历史模式仅对窗口内 `archived` 生效并标 `historical`，对 draft/withdrawn 不放宽；领域模型二次防线。
- 集成 [test_fact_recheck.py](../../tests/integration/test_fact_recheck.py)（独立临时库、真实 LOGIN 用户、FORCE RLS）：13 种案例（含 owner 绕过不可变触发器制造的篡改 chunk、无锚点 chunk、完整性 pending/failed、未来/过期/归档/低可信归档/草稿/PV 专属/共享）在 app 与 readonly 角色下各得其判定，名次顺序保持，未知 UUID 与重复候选各计原因；跨部门（PV、CO 身份）只见 `not_visible` 且不泄露任何字段；历史模式无 `as_of` 拒绝、有 `as_of` 时归档版本标 `historical`、低可信归档拒绝、窗口外拒绝；无身份/无事务拒绝；admin 与 owner 连接拒绝；非 UUID 输入失败关闭、空输入空结果；**与候选 A 串接**：词法 SQL 只过滤状态与窗口，完整性未验证、篡改与无锚点的 chunk 仍被返回，回查全部拦下且保留名次。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**732 passed**（541 单元 + 191 集成）。

## 4. 自审（基线 §9）

1. 需求：3.4 六项条件全部进入判定；INV-DATA-03 历史需显式 `as_of`；INV-DATA-06 引用字段齐全；INV-DATA-07 回查后才构造 Evidence。
2. 逻辑：越权与不存在不可区分（RLS 之下本就如此，且不应区分）；判定顺序固定且有测试；窗口边界与词法 SQL 一致。
3. 安全：应用角色执行；管理/超级用户角色拒绝；拒绝记录不含任何文档字段；无 DSN 打印。
4. 契约：`Evidence`/`Citation` 领域模型未改；新增 `RecheckResult` 冻结模型。
5. 测试：新增 18 单元 + 9 集成；全量 732 passed。
6. 可观测：`Rejection.reason/rank` 与哈希对可直接进入 Trace（落库随 M2）。
7. 简洁性：一个模块、一条 SQL、一个纯判定函数。
8. 验证：数字来自 pytest 输出。
9. Checklist：M1-18 待做 → 已实现；**进度 26.6%（21/79），按 99 项计 21.2%**。

## 5. 下一步

M1-19 缓存键与失效（消费 outbox 事件；键含规范化查询、身份权限指纹、`as_of`/历史条件、`retrieval_version` 与策略版本）；M1-09 剩余项；M1-16 待 DEC-002。
