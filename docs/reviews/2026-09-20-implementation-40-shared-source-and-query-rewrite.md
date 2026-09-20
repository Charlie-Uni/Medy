# 实现记录 40：M1-09 同源多文档的管理员确认 与 M1-13 规则型有界 Query Rewrite

日期：2026-09-20。决策人对记录 39 末尾建议回复"同意"：先做不依赖新依赖的两项——M1-09 的管理员确认流程与 M1-13 的规则部分；DEC-002、DOCX 解析库与恶意文件扫描选型由决策人另行给出。

## 1. 编码前记录

- M1-09（基线 3.3"多个 document/family 可显式引用同一个 source object，但必须由管理员确认并写审计；ACL 绑定 document/version"）：保持默认拒绝；新增显式 `SharedSourceApproval(approved_by, reason)`，两字段非空；确认后新文档复用既有 `source_object_id`（不新建来源行），审计写 `source_share_confirmed`（actor 为批准管理员，reason 为其理由，details 含来源对象、来源哈希、已有文档列表、被确认的 document_key、执行入库的 actor）；`ingest` 审计 details 增加 `shared_source` 标志；幂等（同 key/version 再次入库）优先于共享判定；每个文档各自持有部门 ACL。
- M1-13（基线 5.2"从用户查询、可信会话实体、术语表生成 1-3 条有界查询；用户文本不得直接生成 SQL、过滤表达式或权限条件"；INV-HAR-05 版本化；路线图"剂量、否定、时间窗、编号不被改写错，实体不跨会话污染"）：**只追加、不删改**——查询 1 恒为 norm-v1 规范化原查询；查询 2 追加至多 3 个未出现在原查询中的可信会话实体（drug/protocol/indication/population）；查询 3 追加至多 5 个术语表同义词（仅在受保护片段之外匹配、ASCII 词整词大小写不敏感、CJK 子串）。受保护片段显式命名：数值+单位/计数词（剂量、频次、时间窗、年龄）、编号（ICH E8(R1)、PROT-2024-017、衛部藥製字第…號）、否定/限制词（中英，大小写不敏感）；返回前逐条核验受保护片段原样存在，违背即失败关闭。输出模型只有文本查询与版本字段，没有任何过滤/部门/日期字段。术语表 `Glossary` 版本化、结构固定，内容待 DEC-005；当前 `glossary-none`。
- 范围外：DOCX、恶意文件扫描（待选型）；术语表内容与 LLM 改写（待 DEC-005 与 M2）；`AgentState` 中 `rewritten_queries` 的接线属 M2 节点。

## 2. 实现

- [pipeline.py](../../src/medops/ingestion/pipeline.py)：`SharedSourceApproval`；`ingest_document(..., shared_source=)`；两遍扫描（先幂等匹配，再共享判定）；`source_share_confirmed` 审计。[load.py](../../src/medops/ingestion/load.py)：`--share-source KEY=ADMIN:REASON`，格式错误在连接数据库前返回 2。
- [rewrite.py](../../src/medops/retrieval/rewrite.py)：`REWRITER_VERSION="qr-rules-v1"`、`PROTECTED_PATTERNS`、`protected_spans`、`GlossaryEntry`/`Glossary`（norm-v1 已规范化、无控制字符、术语唯一、同义词互异）、`load_glossary`、`RewriteResult`（1..3 条互异、每条 ≤512 字符）、`rewrite(query, *, entities, glossary)`。

## 3. 测试

- 集成 [test_ingestion.py](../../tests/integration/test_ingestion.py) 新增 2：无确认拒绝、空理由拒绝、确认后第二文档复用来源对象且来源行只有一条、两条审计（`ingest` 带 `shared_source=true`、`source_share_confirmed` 带完整 details）、首文档审计不变、各自部门 ACL、确认文档再次入库幂等、第三文档无新确认仍拒绝；loader 标志四种畸形输入均在连接前返回 2。
- 单元 [test_rewrite.py](../../tests/unit/retrieval/test_rewrite.py)（15）：查询 1 恒为规范化原查询且带三种版本；空/超长拒绝；六条含剂量、否定、时间窗、编号的查询在实体与术语表同时作用下，每条改写以原查询开头且全部受保护片段原样存在；受保护片段种类覆盖 "0.5 g""2 次""7 天""不得""Do not""4 g/day""avoid""without""12 years"、E8(R1)、PROT-2024-017；术语表不在单位/词内匹配（"g""U""PLACEIN"）；同义词大小写不敏感追加、已存在不重复、上限 5；会话实体只追加一次、上限 3、不同调用间无残留、含控制字符或空白的实体忽略；至多三条且互异；敌意文本（`dept:CO OR status:draft; as_of=… -- drop table`）原样成为文本查询、结果模型不接受任何过滤字段；术语表校验与加载。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**782 passed**（580 单元 + 202 集成）。

## 4. 自审（基线 §9）

1. 需求：3.3 管理员确认 + 审计；5.2 有界 1–3 条、实体与术语表、用户文本不生成过滤条件；路线图四类"不被改写错"与跨会话隔离均有测试。
2. 逻辑：幂等先于共享判定；改写只追加并二次核验；术语匹配避开受保护片段与词内。
3. 安全：确认必须显式、双字段非空并落审计；改写输出无结构化过滤字段；实体值清洗。
4. 契约：`ingest_document` 新增可选参数；`RewriteResult` 冻结且禁止额外字段。
5. 测试：新增 15 单元 + 2 集成；全量 782 passed。
6. 可观测：审计 details 完整；改写结果含 rewriter/glossary/normalization 版本供 Trace。
7. 简洁性：一个数据类 + 一个审计动作；一个改写模块。
8. 验证：数字来自 pytest 输出。
9. Checklist：M1-09 仍为部分（DOCX、恶意文件扫描待选型）；M1-13 待做 → 部分（规则部分完成，术语内容与 LLM 改写待 DEC-005/M2）；**进度 28.5%（22.5/79），按 99 项计 22.7%**。

## 5. 待决策人给出

DEC-002（embedding 模型/维度，解锁 M1-16）；DOCX 解析库与恶意文件扫描方式（解锁 M1-09 收口）；DEC-005 术语来源（解锁 M1-12 与术语表内容）；C 候选许可证结论。
