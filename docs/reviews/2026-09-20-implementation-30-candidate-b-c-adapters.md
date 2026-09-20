# 实现记录 30：DEC-001 候选 B/C 适配器与共享门禁测试套件

日期：2026-09-20。承接决策人对记录 29 四项的"同意"：已按授权提交记录 27～29 与候选 A（`9e43175`、`3877895`）；实验范围 DDL 方案照此执行。本轮实现候选 B（zhparser）与 C（pg_search BM25）的数据库适配器，把候选 A 的集成测试提炼为三候选共用的门禁套件，并在各自的本地服务器上通过。未读取或执行任何探针查询；未改动 ADR-0002 预登记判据与冻结的 v1。

## 1. 编码前记录

- 目标：B/C 各自实现 `LexicalRetriever`，与 A 使用同一过滤、计数、排序与身份/版本规则；三候选在同一套合成语料与断言下通过普通角色 + FORCE RLS 门禁。
- 不变量：候选配置以记录 28 构建证据为准，不因合成观察调优索引侧；查询侧的前置规则只允许在任何探针查询执行之前声明并写入实验清单。
- 范围：不入库真实语料、不激活文档、不跑 75 条对比；C 的许可状态仍为 `release_blocked`，只产生对照证据。
- 基础设施：从记录 28 的镜像各启动一个持久实验服务器（B `127.0.0.1:5433`，C `127.0.0.1:5434`，各 2 CPU/2 GiB，命名卷），管理 DSN 写入被 `.gitignore` 忽略的 `.env.dec001`，`Settings` 不读取它。

## 2. 实现

- 抽出 [pg_lexical_common.py](../../src/medops/retrieval/lexical/pg_lexical_common.py)：元数据表 DDL、tsvector 索引表 DDL、文本索引表 DDL、同一条"计数 + 分页"语句模板、字面量转义、身份要求、版本比对与结果装配。候选 A 改为复用，公开接口与测试不变。
- 候选 B [pg_zhparser_fts.py](../../src/medops/retrieval/lexical/pg_zhparser_fts.py)（`pg-zhparser-fts-v1`）：
  - `install()` 以超级用户创建/核对 `zhparser 2.3`，逐字节核对镜像内 `dict.utf8.xdb` 与 `rules.utf8.ini` 的 SHA-256（与记录 28 证据一致），创建文本搜索配置 `dec001_b`（除 `w` 外全部词性映射到 `simple`，与 smoke 一致）并核对映射；
  - 分词在数据库内：入库 `to_tsvector('dec001_b', content)`，查询先 norm-v1 再 `to_tsvector`；`tokenizer_version` 由运行时扩展版本、配置映射哈希与 `zhparser.*` GUC 哈希组成，`dictionary_version` 为固定的词典/规则哈希 + SCWS 1.2.3；
  - 前置规则（本轮声明，未跑探针）：查询侧丢弃纯标点词元。原因：zhparser 保留 `。 . - /` 作为词元，OR 谓词带上它们会命中几乎所有 chunk。索引侧不改。
- 候选 C [pg_search_bm25.py](../../src/medops/retrieval/lexical/pg_search_bm25.py)（`pg-search-bm25-v1`）：
  - `install()` 先建 `vector` 再建 `pg_search 0.25.9`，核对 `pg_search.so` 的 SHA-256（`74e90e4f…d50b`），建表 `lexical_index_c(chunk_id, content)` 与 bm25 索引（`key_field=chunk_id`，`pdb.jieba` 四项固定过滤器）；
  - 查询先 norm-v1，再用同一 `pdb.jieba` 配置在 SQL 内分词，丢弃空白与纯标点词元，谓词为 `||| text[]`（数组 OR）。探针前在 C 服务器临时库验证：`||| 'alpha gamma'`（文本）因空白词元命中 4/5 行，`||| ARRAY['alpha','gamma']` 命中正确的 3 行；`paradedb.score()` + `count(*) over ()` + `LIMIT` 计数正确；
  - 排序 `paradedb.score()` 降序、`chunk_id` 升序；过滤与计数语句与 A/B 同形。
- 共享套件 [lexical_adapter_suite.py](../../tests/integration/lexical_adapter_suite.py)：`CandidateUnderTest` 注入安装/构建/构造/期望版本/漂移版本/计划标记；种子（三部门相同条款、active×2、archived、draft、未生效、过期、MA/PV 共享、CO 名下 25 条契约语料）与 19 项断言对三候选完全相同；服务器通过 `DEC001_<X>_ADMIN_URL` 解析，缺失或不可达时跳过并说明。
- CLI：`python -m medops.retrieval.lexical.pg_zhparser_fts|pg_search_bm25 install|build --admin-url`。

## 3. 测试

| 模块 | 数量 | 服务器 | 结果 |
| --- | --- | --- | --- |
| test_lexical_pg_simple_fts.py（A） | 20 | 开发库集群临时库 | 通过 |
| test_lexical_pg_zhparser_fts.py（B） | 23 | 本地 B 服务器临时库 | 通过 |
| test_lexical_pg_search_bm25.py（C） | 24 | 本地 C 服务器临时库 | 通过 |
| 单元 test_pg_zhparser_fts_unit.py / test_pg_search_bm25_unit.py | 4 + 4 | 无 | 通过 |

三候选共同通过：幂等安装与最小授权、构建版本记录、M1-03 契约、三部门 × app/readonly 零越权（含 k=n/n-1/n+1 的计数不泄露）、状态与生效窗口在查询内过滤、无身份/无事务拒绝、连接复用不残留身份、k 边界在两种执行计划下不静默少取、并列按 `chunk_id`、重复运行一致、纯标点查询 0 条、版本漂移双重拒绝、普通角色执行计划含 RLS 链、普通角色不能写索引、管理登录用户可重建。

候选特有：B 词典字节核对与篡改哈希拒绝、运行时版本串、`PROT-2024-017` 被切为 `017/2024/prot`、繁体 `觀察時間` 逐字切分（特征化记录，非质量断言）、简体 `观察时间` 切为两词；C 扩展版本与二进制核对、`alpha gamma` 不再因空白命中、ParadeDB 自定义扫描与 `document_acl`/`current_setting('medops.dept')` 同在一个计划中、`sigma 随访` 返回本部门 4 条。

门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0：ruff、120 文件格式一致、mypy 52 文件无错、**632 passed**（501 单元 + 131 集成）、schemas 无漂移。CI 环境没有 B/C 服务器，两个模块会以明确原因跳过，本地证据以本记录为准。

## 4. 观察

- B 的 SCWS 词典不含繁体词条，繁体条款按单字切分；这是候选 B 固定配置的已知属性，影响 MA 五份仿單与 TFDA 指引，不在探针前调优。
- C 的 `pdb.jieba` 将 `PROT-2024-017` 切为 `prot-2024` 与 `017`，A 的 `tok-jieba-v1` 另外保留整词 `prot-2024-017`，B 切为 `prot/2024/017`。三者对方案编号切片的行为不同，将在报告中按切片体现。
- 三候选的"合格候选"谓词均已在 `experiment_plan.json` 按候选声明；`adapters_unimplemented` 阻塞移除，新增 `candidate_servers_not_loaded`（B/C 服务器尚无 schema、登录用户与语料）。

## 5. 自审（基线 §9）

1. 需求：只做 B/C 适配器与共享门禁；未选型、未读探针、未激活。
2. 逻辑：三候选共用同一条计数 + 分页语句形状与 `len(page) == min(eligible, k)` 失败闭合；前置规则在探针前声明。
3. 安全：B/C 索引表 FORCE RLS，经 chunks 策略；C 自定义扫描在普通角色下实测未绕过 RLS（合成三部门零泄漏）；`.env.dec001` 被忽略，Settings 不读取。
4. 契约：`LexicalRetriever` 不变；三候选通过同一契约测试。
5. 测试：新增 8 单元 + 47 集成；全量 632 passed。
6. 可观测：每候选 `explain()`；`install()` 拒绝时报出实际与期望哈希/版本。
7. 简洁性：公共模块一个；每候选一个模块；测试套件一个类。
8. 验证：数字来自本轮 make check 与 pytest 输出。
9. Checklist：M1-03 仍"已实现（契约范围）"；M1-04 仍"部分"（三候选零静默不足均已在合成数据证明，真实探针待跑）；进度不变 24.1%（19/79）。

## 6. 下一步（不需新决定的部分先做）

1. B/C 服务器：迁移到 head、建立登录用户、以同一 corpus.json 与 PDF 入库 16 份文档（含记录 21 的四条 PII 放行理由原文）、构建索引。
2. 冻结运行清单（M1-02）：三服务器的 chunk UUID 不同，运行清单按服务器记录 `chunk_mapping`，gold 命中按 `source_hash/version_label/page/key_text` 位置判定，不依赖跨服务器 UUID 一致。
3. 等决策人确认文档激活方案后执行 75 条对比（M1-05）。
