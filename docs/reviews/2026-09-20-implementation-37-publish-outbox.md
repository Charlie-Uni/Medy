# 实现记录 37：M1-11 发布事务、事务性 outbox 与索引消费者

日期：2026-09-20。决策人对记录 36 的建议回复"同意"：DEC-001 最终判定推迟到端到端实验（ADR-0002 修订 3），与词法引擎无关的 M1 切片继续，C 许可证审核并行。本轮实现 M1-11：新版发布在同一事务中归档旧版、激活新版、写审计与 outbox，并提供至少一次投递、按消费者幂等的消费契约与一个索引消费者。

## 1. 编码前记录

- 目标（基线 5.1、4.2 `outbox_events`、M1-11）：`publish_version` 一次事务完成 archive + activate + audit + outbox；outbox 追加写、管理角色专用；消费者 `FOR UPDATE SKIP LOCKED` 领取、按消费者记录 ack、处理与 ack 同事务。
- 不变量：INV-DATA-02（同 family 单一 active，由部分唯一索引保证，事务内先归档后激活）；INV-DATA-04（`supersedes` 为插入时固定的不可变身份列，版本链在入库时建立）；3.4（旧版 `effective_to` = 新版 `effective_from`，窗口相接不重叠，`effective_to > effective_from` 由约束保证）；"索引延迟不能令旧版本成为有效证据"由查询内 `status='active'` 与生效窗口过滤保证，不依赖消费者时序。
- 范围：不含缓存失效消费者（M1-19 尚无缓存，事件 payload 已含其所需字段）；不含 DOCX 与管理员确认流程（M1-09）。

## 2. 实现

- 迁移 0005 [0005_outbox_events.py](../../migrations/versions/0005_outbox_events.py)：`outbox_events`（事件类型受限枚举、聚合与 family、jsonb payload、创建者/时间、投递簿记 `published_at/attempts/last_error`）、`outbox_consumer_acks`（消费者 × 事件主键）；触发器禁止删除与修改身份/payload 列，ack 表禁止更新与删除；两表 FORCE RLS，仅 `medops_admin_role` 可读写（无 DELETE 授权），app/readonly 无任何访问。
- [outbox.py](../../src/medops/ingestion/outbox.py)：`emit`（在生产事务内）、`claim`（`SKIP LOCKED`，排除已 ack）、`ack`、`run`（每事件 savepoint，处理与 ack 同事务）、`mark_published_when_complete`、`record_failure`。
- [activate.py](../../src/medops/ingestion/activate.py)：`publish_version(conn, new_key, effective_from, actor=, reason=)`：前置检查（新版为 trusted draft 且有作业与 `supersedes`；被替代者为 family 当前唯一 active；`effective_from` 晚于旧版）全部在写入前完成；随后同一事务归档旧版（写 `effective_to`）、激活新版、由触发器写两条 doc_audit、发出 `document_archived` 与 `document_activated` 两条事件（payload 含 doc/family/key/version/部门 ACL/来源对象/理由与窗口）。首次激活 `activate_document` 亦发 `document_activated`。CLI `--document-key … --publish`。
- 入库：`ingest_document(..., supersedes=)` 使新版加入被替代者的 family；`make load-corpus ARGS="--supersedes NEWKEY=OLDKEY"`。`document_key` 唯一，因此新版用新的 key，family 由 `supersedes` 链定。
- [index_consumer.py](../../src/medops/retrieval/lexical/index_consumer.py)：消费者 `lexical-index`，对注册的索引表按事件增删该文档的 chunk 行（A 族 tsvector 字面量、B 族 SQL 配置、C 内容表），`on conflict do nothing`/幂等删除。
- 六个本机库（三服务器 × medops/medops_v2）已迁移到 0005。

## 3. 测试

- [test_publish_outbox.py](../../tests/integration/test_publish_outbox.py)（5，独立临时库、真实 LOGIN 用户）：outbox 对 app/readonly 不可见，管理角色不能删，owner 也被追加写触发器拦下，payload 不可改而簿记列可改；发布后旧版 archived 且 `effective_to` 相接、新版 active，两条审计与两条事件同事务、payload 字段齐全，同 family 只剩一个 active，重复发布被拒；`effective_from` 不晚于旧版、无 `supersedes` 链均在写入前拒绝；模拟 outbox 写入失败时两处状态更新与审计全部回滚；**索引延迟性质**：发布前普通角色只见 v1 chunk，发布后消费者尚未运行时已只见 v2 chunk（v1 行仍在索引表中），消费者运行后 v1 行被清除、重复消费无效果；两个消费者并发领取互斥、重复 ack 被主键拒绝、`published_at` 簿记。
- 既有测试：迁移往返期望新增两表两函数；RLS 测试期望新增两张 FORCE RLS 表。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**705 passed**（523 单元 + 182 集成）。

## 4. 自审（基线 §9）

1. 需求：发布/归档/审计/outbox 同事务；消费契约至少一次 + 幂等；未实现缓存消费者并如实标注。
2. 逻辑：所有拒绝在写入前；先归档后激活满足部分唯一索引；生效窗口相接由约束保证。
3. 安全：outbox 仅管理角色；app/readonly 无访问；消费者只用管理连接；无 DSN 入库。
4. 契约：候选适配器不变；事件类型受 CHECK 约束；payload JSON 安全。
5. 测试：新增 5 集成；全量 705 passed。
6. 可观测：doc_audit + outbox 双记录；`attempts/last_error/published_at` 簿记。
7. 简洁性：一个迁移、一个 outbox 模块、发布函数并入 activate、一个消费者模块。
8. 验证：数字来自 make check 与 pytest 输出。
9. Checklist：M1-11 由部分转为已实现（缓存消费者归 M1-19）；**进度 25.3%（20/79），按 99 项计 20.2%**。

## 5. 下一步

按修订 3：M1-18 事实回查（候选回查 ACL/active/生效时间/完整性/解析质量）与 M1-19 缓存键与失效（消费 outbox 事件）可继续；M1-16 待 DEC-002（embedding）决定；M1-09 剩余项（DOCX、恶意文件扫描、多文档同源管理员确认）可独立推进。C 许可证审核由决策人推动。
