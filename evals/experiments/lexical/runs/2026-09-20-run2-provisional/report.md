# DEC-001 词法对比运行报告：2026-09-20-run2-provisional

- 用途：Run 2 (ADR-0002 amendment 1), PROVISIONAL: medops_v2 databases (chunker-v2, 16 active documents incl. esomen via audited quality override), frozen probe v1 scored by language_matched / cross_lingual scope, plus the 32 unreviewed English twin queries as a separate overlay (not a gate input); to be repeated on frozen probe v2 after LLM second review and annotator confirmation
- 运行清单 SHA-256：`76e6ab0827061d3b87d30920a4dd2dbad3611ecdcb216a7dc21f1ce70b14e5ce`（查询前写出）
- 数据集：v1，dataset_hash `5561bee58e37cd8d86b756f17e6c1a6ebed32ba54ba2ac48f4cd4adee254db7e`
- Git HEAD：`0ed131e85e415b74b6b186d7c3de8c901640f4b8`；as_of 2026-09-20；K=20；预热 5 遍、测量 10 遍、种子 20260920；并发 1
- 环境：macOS-26.5.2-arm64-arm-64bit，8 CPU

## 候选与索引

| 候选 | 服务器 | 镜像 | 扩展 | 索引版本 | 分词器版本 | 词典版本 | 映射 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | localhost:5432 | `dev cluster` |  | `pg-simple-fts-v1` | `tok-jieba-v1` | `jieba-0.42.1+default` | 75 mapped / 0 unmappable |
| B | localhost:5433 | `sha256:00ce3abb08cc` | zhparser 2.3 | `pg-zhparser-fts-v1` | `zhparser-2.3+scws-1.2.3+cfg-dec001_b:8d420cfb+guc:3ff9eb8a` | `scws-dict-utf8:fd76a689f996c4e6+rules-utf8:45395f794226581f+scws-1.2.3` | 75 mapped / 0 unmappable |
| C | localhost:5434 | `sha256:f564d490dfa0` | pg_search 0.25.9, vector 0.8.6 | `pg-search-bm25-v1` | `pg_search-0.25.9+pdb.jieba:6c256ba3` | `jieba-rs-0.10.1+tantivy-jieba-0.20.0+pg_search.so:74e90e4f8015246a` | 75 mapped / 0 unmappable |

## 硬门禁（ADR-0002）

| 候选 | 严格宏平均 Recall@20 | drug_name_zh | dose_unit | negation | time_window | protocol_id | mixed_zh_en | 泄漏 | 可复现 | 通过 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 81.4% ✗ | 66.7% (n=18) ✗ | 90.0% (n=20) | 82.6% (n=23) ✗ | 72.7% (n=11) ✗ | 80.0% (n=5) ✗ | 95.2% (n=21) | 0 | 是 | 未通过 |
| B | 93.0% | 94.4% (n=18) | 95.0% (n=20) | 95.7% (n=23) | 90.9% (n=11) | 80.0% (n=5) ✗ | 95.2% (n=21) | 0 | 是 | 未通过 |
| C | 95.3% | 88.9% (n=18) | 100.0% (n=20) | 95.7% (n=23) | 90.9% (n=11) | 100.0% (n=5) ✗ | 100.0% (n=21) | 0 | 是 | 未通过 |

硬门禁按 ADR-0002 修订 1 在语言一致子集内计算（每候选 43 条冻结样本）。

## 作用域分报（冻结样本）

| 候选 | 语言一致 宏平均 (n) | 跨语言 宏平均 (n) | 全部冻结样本 (n) |
| --- | --- | --- | --- |
| A | 81.4% (n=43) | 15.6% (n=32) | 53.3% (n=75) |
| B | 93.0% (n=43) | 12.5% (n=32) | 58.7% (n=75) |
| C | 95.3% (n=43) | 12.5% (n=32) | 60.0% (n=75) |

### 临时叠加：未复核、未经人工确认的英文孪生查询（不进入门禁）

| 候选 | 孪生 宏平均 (n) | 语言一致 + 孪生 宏平均 (n) | 孪生按部门 |
| --- | --- | --- | --- |
| A | 59.4% (n=32) | 72.0% (n=75) | CO 62.5% (n=16), PV 56.2% (n=16) |
| B | 59.4% (n=32) | 78.7% (n=75) | CO 62.5% (n=16), PV 56.2% (n=16) |
| C | 90.6% (n=32) | 93.3% (n=75) | CO 87.5% (n=16), PV 93.8% (n=16) |

## 部门与脚本变体（全部冻结样本）

| 候选 | MA | PV | CO | zh-Hans | zh-Hant | en | drug_name_zh/zh-Hans | drug_name_zh/zh-Hant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 76.7% (n=30) | 46.7% (n=45) | 46.9% (n=32) | 90.0% (n=10) | 78.8% (n=33) | 37.5% (n=64) | n/a | 66.7% (n=18) |
| B | 93.3% (n=30) | 46.7% (n=45) | 43.8% (n=32) | 90.0% (n=10) | 93.9% (n=33) | 35.9% (n=64) | n/a | 94.4% (n=18) |
| C | 93.3% (n=30) | 62.2% (n=45) | 56.2% (n=32) | 100.0% (n=10) | 93.9% (n=33) | 51.6% (n=64) | n/a | 88.9% (n=18) |

## 延迟与候选数

| 候选 | 词法 P95 (ms) | 均值 (ms) | 最大 (ms) | 测量次数 | 耗尽(<K) 查询数 | 零结果查询数 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 43.79 | 15.05 | 120.47 | 1070 | 0 | 0 |
| B | 41.58 | 15.61 | 63.32 | 1070 | 0 | 0 |
| C | 44.59 | 33.44 | 384.46 | 1070 | 0 | 0 |

## 相对 A 的选择规则（仅词法部分）

| 候选 | 配对提升 (pp) | 95% CI | 提升 ≥5pp 且 CI 下界 >0 | 词法 P95 ≤ 1.25×A | 硬门禁 | 许可证阻断 | 仅凭词法证据可替代 A |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B | +11.6 | [+2.3, +20.9] | 是 | 是 | 未通过 | 否 | 否 |
| C | +14.0 | [+4.7, +25.6] | 是 | 是 | 未通过 | 是 | 否 |

未在本运行评估：端到端 Recall@5 下降 ≤1pp、关键切片端到端下降 ≤5pp、端到端 P95 ≤8s；这些需要向量/重排配置固定后另测。

**词法结论：** no candidate passes the hard gates: DEC-001 and M1 stay blocked; gates are not lowered

## 未命中明细（各候选 recall < 1 的样本）

- A：48 条 — pc-0003, pc-0014, pc-0019, pc-0020, pc-0022, pc-0026, pc-0030, pc-0031, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(cross), pc-0073(cross), pc-0075(cross), pc-0076(twin), pc-0081(twin), pc-0083(twin), pc-0084(twin), pc-0086(twin), pc-0087(twin), pc-0088(twin), pc-0092(twin), pc-0094(twin), pc-0099(twin), pc-0100(twin), pc-0102(twin), pc-0107(twin)
- B：44 条 — pc-0014, pc-0030, pc-0031, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0063(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(cross), pc-0073(cross), pc-0075(cross), pc-0076(twin), pc-0081(twin), pc-0083(twin), pc-0084(twin), pc-0086(twin), pc-0087(twin), pc-0088(twin), pc-0092(twin), pc-0094(twin), pc-0099(twin), pc-0100(twin), pc-0102(twin), pc-0107(twin)
- C：33 条 — pc-0020, pc-0026, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0063(cross), pc-0064(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(cross), pc-0073(cross), pc-0076(twin), pc-0095(twin), pc-0100(twin)
