# 实现记录 29：DEC-001 候选 A 适配器（普通角色 + FORCE RLS）

日期：2026-09-20。承接决策人"查看一下修订的文件 确认进度 继续"。先复核记录 23～28 与工作区，再补齐记录 28 的执行结果，然后实现 ADR-0002 候选 A 的数据库适配器并在真实 schema、真实 LOGIN 用户下通过契约与门禁测试。未读取或执行任何探针查询；未改动基线、ADR 预登记判据、冻结的 v1；未提交 Git。

## 1. 复核结论（进入本轮前）

| 项 | 实测 |
| --- | --- |
| 探针 v1 | `manifest.status=frozen`，`dataset_hash 5561bee5…db7e`，`SHA256SUMS` 全部 OK，frozen 校验 `errors=0 warnings=0` |
| Git | `2a4aef6`、`213dbe8`、`4b5fa71` 存在；工作区仅记录 27 一行空行删除与未跟踪的 `evals/experiments/lexical/builds/` |
| 软件门禁 | `env -u DEBUG -u PYTHONPATH make check`：549 passed（485 单元 + 64 集成） |
| 进度 | 路线图 24.1%（19/79）；基线 `[x]` 仅 M1-01 |
| 记录 28 | "执行结果"仍为"构建中"，已按 B/C/A 的实测证据补齐并自审（见该记录） |

## 2. 编码前记录

- 目标：候选 A（应用层 `tok-jieba-v1` 预分词 + PostgreSQL `simple` FTS）实现 `LexicalRetriever`，在普通应用角色、`FORCE ROW LEVEL SECURITY` 与连接池身份切换条件下证明零越权、零静默候选不足、版本拒绝，并留执行计划证据（基线 3.6、3.7；ADR-0002 硬门禁 3～5）。
- 不变量：过滤只在数据库内（RLS 链 + `status='active'` + 生效窗口）；精确计数与分页同一语句、同一谓词；同分按 `chunk_id` 升序；索引与查询版本不一致必须拒绝；无身份不得返回"空但已耗尽"的结果。
- 范围：只做 A；B/C 适配器与 75 条对比留下一轮。只用合成数据测试。
- 决定（可由决策人推翻）：索引表 `lexical_index_meta`、`lexical_index_a` 由 `install()` 在管理连接下创建，**不写入 Alembic 迁移**，因为 DEC-001 尚未选定生产引擎，候选表保持实验范围；选定后再以正式迁移落地。

## 3. 实现

- `src/medops/retrieval/lexical/pg_simple_fts.py`（`RETRIEVER_VERSION = pg-simple-fts-v1`）：
  - 分词结果直接写成**带位置的 tsvector 字面量**（`'词':1,3`），不经过文本解析器，索引词元与查询词元逐字等于分词器输出（基线 3.6 "保留位置信息"）；引号与反斜杠按 tsvector 规则转义，位置与每词元位置数按服务器上限裁剪。
  - 查询：去重词元的 OR `tsquery`（与实验清单 `matching_predicate` 一致）；`ts_rank_cd(tsv, q, 0)` 降序、`chunk_id` 升序；`count(*) over ()` 在同一语句给出合格候选精确计数；`candidate_exhausted = eligible < k`，若分页大小 ≠ `min(eligible, k)` 直接抛内部错误，不猜测。
  - 过滤：`lexical_index_a → chunks → documents` 的 RLS 策略链 + `documents.status = 'active'` + `effective_from <= as_of < effective_to`；`as_of` 可固定以便实验复现。
  - 身份：无打开事务或事务内无 `medops.dept` 时抛 `unauthenticated`（不让 RLS 静默返回空页）；`versions` 读取 `lexical_index_meta` 中的构建版本，与当前分词器配置不一致时抛 `version_conflict`；边界 `run_lexical_search` 再核对一次。
  - `install()`（幂等 DDL：两表、GIN 索引、FORCE RLS、`via_chunk` 策略、最小授权）、`build_index()`（管理角色一次事务内全量重建，空词元 chunk 计入 `skipped_empty`）、`explain()`（同一语句的 `EXPLAIN (FORMAT JSON)`）、CLI `install|build`；`make lexical-index-a ACTOR=<id>`。
- 本机开发库：`install` + `build` 完成，`chunk_count=2661`、`skipped_empty=0`，版本 `pg-simple-fts-v1 / tok-jieba-v1 / jieba-0.42.1+default / norm-v1`。以 `medops_app_user` 查询时 16 份文档均为 draft，返回 0 条（预期）。

## 4. 测试

- 单元 `tests/unit/retrieval/test_pg_simple_fts_literals.py`（8）：位置与首现顺序、引号/反斜杠转义、CJK 与编号原样、OR 去重、空/超长词元拒绝、服务器上限、版本元组来源、SQL 结构。
- 集成 `tests/integration/test_lexical_pg_simple_fts.py`（20，独立临时数据库 + 三个真实 LOGIN 用户；种子为三部门相同条款，各含 active×2、archived、draft、未生效、已过期文档，MA/PV 共享文档，以及 CO 名下 25 条契约语料）：
  - 幂等安装、两表 `relforcerowsecurity=true`、app/readonly 仅 SELECT、admin 角色 SELECT/INSERT/UPDATE/DELETE；
  - 通过 M1-03 的可复用适配器契约（零/少于/等于/多于 K、并列排序、版本拒绝）；
  - 三部门 × app/readonly 零越权：返回集合恰为本部门可见 chunk，`k = n / n-1 / n+1` 的 `candidate_exhausted` 不泄露他部门计数；
  - draft/archived/未生效/已过期均被查询内过滤，`as_of` 前移/后移分别纳入过期与未来文档；
  - 无身份、无事务、事务提交后复用连接、`RESET ALL` 后均拒绝；
  - `gamma`（7 条）k=6/7/8 与 `delta`（25 条）k=20 在 `enable_seqscan` on/off 两种计划下计数与旗标一致；
  - 并列同分按 `chunk_id` 升序，重复 3 次逐项一致；纯标点查询 0 条且 exhausted；
  - 用户词典导致 `dictionary_version` 漂移时适配器与边界均拒绝，而 `versions` 仍报告索引构建版本；
  - 普通角色下的执行计划包含 `lexical_index_a`、`document_acl`、内联后的 `current_setting('medops.dept')`、`@@` 谓词与生效窗口，`status='active'` 由部分唯一索引 `documents_one_active_per_family` 承担；
  - app/readonly 不能写索引表；字面量经 PostgreSQL 往返一致；管理 LOGIN 用户可重建。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0：ruff 通过、112 文件格式一致、mypy 49 文件无错、**577 passed**（493 单元 + 84 集成）、schemas 无漂移。

## 5. 观察（供实验清单与后续决策）

- jieba 默认词典把 `美洛醣` 切为 `美洛 | 醣`：候选 A 在无医学词典（实验清单 `custom_dictionary=false`）时对繁体商品名的召回依赖 OR 谓词的部分命中，这是预登记时已知的设计限制，本轮不调优。
- 开发库文档全部 draft，`tfda-label-esomen-40mg` 为 low_trust，不能激活（INV-DATA-05）。正式 75 条对比前需要决策人决定：按 M1-11 口径激活 15 份 trusted 文档（说明书取文内修订日期 → 许可证异动日期 → PDF 元数据日期；指南取发布日期），esomen 保持不可见则 pc-0025～pc-0030 计 miss，或先解决其抽取告警再重新入库。
- `experiment_plan.json`：A `adapter_runtime_verified=true` 并记录适配器信息；`adapters_unimplemented` 收窄为 B/C；`candidate_builds_unverified` 由 `candidate_images_local_only` 替代。状态仍 `draft_not_ready_for_comparison`。

## 6. 自审（基线 §9）

1. 需求：只做 A 适配器与门禁测试，未选型、未读探针、未激活文档。
2. 逻辑：计数与分页同一语句；`len(candidates) != min(eligible, k)` 直接失败；无身份/无事务显式拒绝。
3. 安全：普通角色只读；索引表 FORCE RLS 且经 chunks 策略；三部门种子相同条款下零泄漏（含计数）。
4. 契约：`LexicalRetriever`/`LexicalSearchResult` 未改；通过既有契约测试；版本元组进入 `lexical_index_meta`。
5. 测试：8 单元 + 20 集成新增；全量 577 passed；集成测试在独立数据库运行，不干扰 `test_rls` 的精确可见性断言。
6. 可观测：`explain()` 提供逐语句计划；构建报告含 chunk 数、跳过数、版本与 `built_by`。
7. 简洁性：一个模块、两张表、一条 SQL；无新依赖。
8. 验证：本记录数字来自本轮实测输出（make check 日志、CLI 输出、计划树）。
9. Checklist：M1-03 仍"已实现（契约范围）"，M1-04 仍"部分"（A 已证零静默不足，B/C 待做），进度不变 24.1%（19/79）。

## 7. 需要决策人确认

1. 是否授权提交：记录 27（空行）、28、29，`evals/experiments/lexical/builds/`，README/experiment_plan 更新，适配器与测试、Makefile。
2. 候选索引表以实验范围 DDL（`install()`）而非 Alembic 迁移落地，是否同意。
3. 正式对比前的文档激活方案（第 5 节第二条）。
4. C 的许可证审核由谁、何时做；在此之前 C 只能作为对照数据，不能选入。
