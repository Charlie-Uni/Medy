# 实现记录 36：ADR-0002 修订 2 —— 英文停用词变体 A2/B2 的预登记、实现与第三次运行

日期：2026-09-20。决策人对记录 35 的建议回复"同意 继续"：预登记 A/B 的英文停用词变体并运行，准备 C 的许可证审核材料。**结论：A2 77.3%、B2 80.0%（语言一致 75 条），较基线显著提升且延迟减半，但仍未通过 90% 硬门禁；C 88.0% 不变。三次预登记运行后无候选通过，DEC-001 与 M1 保持阻塞。**

## 1. 预登记（先于运行）

ADR-0002 修订 2 与 `experiment_plan.json` 的 `run_3_preregistration`：A2 = `pg-simple-fts-v1` + `tok-jieba-v2`（入库与查询两侧删除固定英文停用词表中的 ASCII 词元；词表为 PostgreSQL 16 随附 `english.stop`，127 词，SHA-256 `b3f772a0…6eac`，副本入库 `evals/experiments/lexical/resources/`）；B2 = zhparser 配置 `dec001_b2`，词性映射到 `simple` 模板加 `stopwords = english` 的字典 `dec001_simple_en_stop`（安装时逐字节核对镜像内 `english.stop`）。排序、谓词、过滤、K、遍数、种子、作用域全部不变；A、B、C 同场对照。判定规则：变体按硬门禁独立判定，A2 通过则取代 A 作为复杂度基线。

## 2. 实现

- [tokenizer.py](../../src/medops/retrieval/lexical/tokenizer.py)：`JiebaTokenizerV2(stopwords=Path)`，`dictionary_version` 追加词表哈希；CJK、编号与数字词元不受影响。
- [pg_simple_fts.py](../../src/medops/retrieval/lexical/pg_simple_fts.py)：`install/build_index/PgSimpleFtsRetriever` 增加 `index_name/table` 参数，变体索引 `lexical_index_a2` 与 `lexical_index_a` 共存于同一库；CLI `--variant a2`。
- [pg_zhparser_fts.py](../../src/medops/retrieval/lexical/pg_zhparser_fts.py)：`ZhparserVariant`（配置名、字典、表、词典版本、是否停用词），`VARIANT_B`/`VARIANT_B2`；`install()` 对 B2 先核对 `english.stop` 字节并创建字典与配置；`tokenizer_version` 含配置名与映射哈希，B2 的 `dictionary_version` 追加 `+stop-english:<hash>`。CLI `--variant b2`。
- 运行器：候选 `A2`/`B2` 复用基线服务器、数据库与映射，各自索引；`server_facts` 与 `make_retriever` 识别变体。
- 测试：分词器 v2 单元测试；共享门禁套件新增 `TestCandidateA2`、`TestCandidateB2`（各自独立临时库，19 项断言全部通过），B2 的停用词侧向对比测试。
- 索引：A2 与 B2 各 2,662 chunk。

## 3. 第三次运行 `2026-09-20-run3-stopword-variants`

| 候选 | 语言一致 75 条 | 相对 A（pp，95% CI） | 词法 P95 | 语言一致未命中（英文） | 合格候选中位数 |
| --- | --- | --- | --- | --- | --- |
| A | 69.3% | 基线 | 38.0 ms | 23（14） | 718 |
| A2 | 77.3% | +8.0 [+2.7, +14.7] | 21.3 ms | 17（8） | 213 |
| B | 76.0% | +6.7 [+1.3, +13.3] | 39.2 ms | 18（14） | 1,532 |
| B2 | 80.0% | +10.7 [+2.7, +18.7] | 22.1 ms | 15（11） | 478 |
| C | 88.0% | +18.7 [+8.0, +29.3] | 32.9 ms | 9（6） | 687 |

零泄漏、排名可复现；A、B、C 与第二次运行逐项一致（对照有效）。切片：A2 的 negation 81.6%、time_window 84.2%、protocol_id 70.6% 仍未达 85%；B2 仅 negation、protocol_id、mixed_zh_en 未达；C 仅 protocol_id 未达。归因：停用词移除后剩余未命中仍是"合格但名次 >20"，来自 `ts_rank_cd` 对高频内容词无 IDF 加权与繁体药名切分（A 族 drug_name_zh 66.7% 不变）。结果与结论已回填 ADR-0002。

## 4. 许可证审核材料

[licence dossier](2026-09-20-licence-dossier-pg-search.md)：pg_search 的许可证事实、获取与修改情况、部署模型、需要法务回答的五个问题与可能的结论形式。不是法律意见；C 的 `release_blocked` 只能由书面审核结论改变。

## 5. 测试与门禁

`env -u DEBUG -u PYTHONPATH make check` 退出码 0：ruff、格式一致、mypy 无错、**700 passed**（523 单元 + 177 集成，其中 B/B2/C 候选服务器上的集成测试仅本地运行）、schemas 无漂移。

## 6. 自审（基线 §9）

1. 需求：变体在预登记之后实现与运行；A/B/C 未改动并同场对照。
2. 逻辑：停用词处理入库与查询同侧同表（3.6）；词表哈希进入版本元组，版本不一致即拒绝。
3. 安全：变体索引表 FORCE RLS，经共享套件零泄漏断言；B2 安装核对镜像内词表字节。
4. 契约：`LexicalRetriever`、运行器输出格式不变；报告对任意候选集合评估。
5. 测试：新增 1 单元 + 2 套件类（38 项）+ 1 对比测试；全量 700 passed。
6. 可观测：每候选 `explain()`；构建报告含版本元组；运行目录五个文件。
7. 简洁性：以参数化复用 A/B 模块，未复制实现。
8. 验证：数字来自 report.md、evaluation.json、miss_diagnostics.json、make check。
9. Checklist：M1-05 仍阻塞；进度不变 24.7%（19.5/79），按 99 项计 19.7%。

## 7. 需要决策人决定

三次预登记运行的证据显示：跨语言样本需要向量阶段；语言一致样本上最接近门禁的是 C（88.0%，许可证阻断）与 B2（80.0%）。剩余差距来自排序函数（无 IDF）与繁体药名切分，不是停用词。可选路径（均需新的预登记）：（1）排序侧变体：`ts_rank_cd` 归一化选项或应用层 IDF 加权（A 族）；（2）B 族加繁体医学词典（`custom_dictionary` 当前为 false）；（3）推进 C 的许可证审核；（4）接受"词法阶段不单独达标、由向量阶段补齐"的架构含义，把 DEC-001 的最终判定推迟到端到端实验，先做 M1 其余切片（M1-11 发布事务、向量阶段准备）。我的建议是 (4) 与 (3) 并行：继续在词法阶段追加变体的边际收益在下降，而 M1 其余切片与向量阶段是端到端门禁的前置条件。
