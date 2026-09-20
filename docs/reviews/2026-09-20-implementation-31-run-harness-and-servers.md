# 实现记录 31：DEC-001 运行工具、三服务器语料与管道 smoke

日期：2026-09-20。承接记录 30 的"下一步"：把 B/C 服务器补齐到可运行状态，实现带冻结运行清单的对比运行工具与评分函数，并用当前全 draft 状态做一次管道 smoke。未激活任何文档；smoke 结果全部为零，只证明管道，不作为实验证据，也不保留在仓库内。

## 1. 编码前记录

- 目标：M1-02 的运行清单在任何查询之前写出并哈希；M1-05 的运行按 `experiment_plan.measurement` 固定的 K、顺序、种子、预热与测量遍数执行；评分只依赖冻结样本与各服务器自己的 gold→chunk 映射。
- 不变量：不改样本、映射与索引；拒绝覆盖已有运行目录；A 候选的分词器每进程只构造一次（词典加载是启动成本，不是查询延迟）；每条查询在普通角色连接的独立事务内以样本部门身份执行。
- 范围：不解释结果为选型；门禁与选择规则的判定另做报告工具。

## 2. 实施

- B/C 服务器：迁移到 `0004`、`provision()` 建立同名登录用户、以同一 `corpus.json` 与 PDF 入库 16 份文档（先以 `reviewer-01` 复放记录 21 的四条 PII 放行理由原文，再以 `ingest-01` 入其余 12 份）。三服务器 `(source_hash, version, seq, page, chunk_content_hash)` 指纹一致 `5ecb04a5…2471`，各 2,661 chunk，16 份均 draft，esomen low_trust。
- 索引：B `pg-zhparser-fts-v1`、C `pg-search-bm25-v1` 各 2,661 chunk（A 已在记录 29 构建）。
- 映射：[export_chunk_snapshot.py](../../evals/experiments/lexical/tools/export_chunk_snapshot.py) 增加 `--admin-url`（默认仍读 Settings，既有单元测试不变）；B/C 快照与映射写入 `preparation-v1/servers/{b,c}/`，均为 73 mapped / 2 unmappable（pc-0056-g1、pc-0072-g1，与 A 相同）。
- [scoring.py](../../src/medops/evals/experiments/scoring.py)：单条严格召回（每个 required gold 命中任一映射 chunk 即计 1，unmappable 永远 miss）、按标签的宏平均并标注支持数不足、按 query 配对的百分位 bootstrap（固定种子/次数）、最近秩 P95、重复排名一致性。
- [dec001_run.py](../../src/medops/evals/experiments/dec001_run.py)：`run_manifest.json`（数据集哈希、样本文件哈希、experiment_plan 哈希、Git HEAD、每候选服务器/扩展/索引构建版本/文档状态计数/映射哈希、测量参数、环境）先写后跑；`execute_passes` 按 `seed + pass_index` 洗牌，预热遍不计延迟；`db_searcher` 一条普通角色连接、每查询一个事务注入部门；`leak_check` 以管理连接核对每个返回 chunk 都属于该部门可读、active 且在生效窗口内的文档；`summarize` 输出总体/部门/切片/gold 文档脚本（zh-Hans、zh-Hant、en）/drug_name_zh 按脚本的召回、耗尽与零结果计数、不可复现查询、P95/均值/最大延迟、逐条明细；B/C 相对 A 的配对 bootstrap。CLI 通过 `.env` 与 `.env.dec001` 解析三服务器。
- 管道 smoke（写入会话暂存目录，不入库）：三候选 75/75 查询返回 0 条且 `candidate_exhausted=true`，0 泄漏，0 不可复现；第一次 smoke 暴露 A 每查询重建 jieba 分词器导致 P95 222 ms，修正为每进程一次后 A/B/C 的 P95 分别约 1.5 / 2.8 / 5.6 ms（全 draft，无命中，不代表实验延迟）。

## 3. 测试

- 单元：`test_dec001_scoring.py`（4）、`test_dec001_run.py`（6，假搜索器：固定顺序与预热排除、严格评分与分组、不可复现检测、映射加载、拒绝覆盖、DSN 改写）；exporter 既有 15 项不变。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0：ruff、125 文件格式一致、mypy 55 文件无错、**642 passed**（511 单元 + 131 集成）、schemas 无漂移。

## 4. 自审（基线 §9）

1. 需求：运行工具与服务器就绪；未激活、未产生任何可解释的召回数字。
2. 逻辑：清单先于查询写出并哈希进结果；分词器构造从查询延迟中剔除；泄漏核查独立于候选实现。
3. 安全：查询只走普通角色；管理连接只读核对；`.env.dec001` 不入库。
4. 契约：候选适配器与边界未改；运行工具只消费 `LexicalSearchResult`。
5. 测试：新增 10 单元；全量 642 passed。
6. 可观测：逐条明细含 gold 命中名次、返回数、耗尽标志、每遍延迟。
7. 简洁性：两个模块；无新依赖。
8. 验证：数字来自本轮 make check、CLI 输出与 smoke 结果文件。
9. Checklist：M1-02 仍"部分"（正式运行清单在激活后冻结）；进度不变 24.1%（19/79）。

## 5. 剩余阻塞

- `corpus_not_publishable`：16 份文档全 draft；激活需要决策人按 M1-11 口径确认每份 `effective_from` 与 esomen 的处理（另附提案）。
- `end_to_end_configuration_unfixed`、`production_license_review_pending`、`candidate_images_local_only` 不变。
