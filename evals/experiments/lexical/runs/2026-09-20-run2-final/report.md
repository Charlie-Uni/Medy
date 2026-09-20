# DEC-001 词法对比运行报告：2026-09-20-run2-final

- 用途：Run 2 final (ADR-0002 amendment 1): frozen probe v2 (107 samples: 75 v1 + 32 confirmed English twins, all re-reviewed by claude-opus-5), medops_v2 databases (chunker-v2, 16 active documents), hard gates on the language_matched scope, cross_lingual reported separately
- 运行清单 SHA-256：`6cbcc17497854bede85eb342fc43bb9b47aef6cdd8f4fb7b0e2fa99eac757d4f`（查询前写出）
- 数据集：v2，dataset_hash `1fc5089f6fa7f80a1a5e23940826b0d4c811cde29e225dd8305241a33beb0321`
- Git HEAD：`47cd360faa4958fa1660e09c748aa3d28f99bd71`；as_of 2026-09-20；K=20；预热 5 遍、测量 10 遍、种子 20260920；并发 1
- 环境：macOS-26.5.2-arm64-arm-64bit，8 CPU

## 候选与索引

| 候选 | 服务器 | 镜像 | 扩展 | 索引版本 | 分词器版本 | 词典版本 | 映射 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | localhost:5432 | `dev cluster` |  | `pg-simple-fts-v1` | `tok-jieba-v1` | `jieba-0.42.1+default` | 105 mapped / 2 unmappable |
| B | localhost:5433 | `sha256:00ce3abb08cc` | zhparser 2.3 | `pg-zhparser-fts-v1` | `zhparser-2.3+scws-1.2.3+cfg-dec001_b:8d420cfb+guc:3ff9eb8a` | `scws-dict-utf8:fd76a689f996c4e6+rules-utf8:45395f794226581f+scws-1.2.3` | 105 mapped / 2 unmappable |
| C | localhost:5434 | `sha256:f564d490dfa0` | pg_search 0.25.9, vector 0.8.6 | `pg-search-bm25-v1` | `pg_search-0.25.9+pdb.jieba:6c256ba3` | `jieba-rs-0.10.1+tantivy-jieba-0.20.0+pg_search.so:74e90e4f8015246a` | 105 mapped / 2 unmappable |

## 硬门禁（ADR-0002）

| 候选 | 严格宏平均 Recall@20 | drug_name_zh | dose_unit | negation | time_window | protocol_id | mixed_zh_en | 泄漏 | 可复现 | 通过 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 69.3% ✗ | 66.7% (n=18) ✗ | 89.5% (n=19) | 68.4% (n=38) ✗ | 73.7% (n=19) ✗ | 64.7% (n=17) ✗ | 69.8% (n=53) ✗ | 0 | 是 | 未通过 |
| B | 76.0% ✗ | 94.4% (n=18) | 94.7% (n=19) | 73.7% (n=38) ✗ | 84.2% (n=19) ✗ | 64.7% (n=17) ✗ | 69.8% (n=53) ✗ | 0 | 是 | 未通过 |
| C | 88.0% ✗ | 88.9% (n=18) | 100.0% (n=19) | 94.7% (n=38) | 94.7% (n=19) | 70.6% (n=17) ✗ | 86.8% (n=53) | 0 | 是 | 未通过 |

硬门禁按 ADR-0002 修订 1 在语言一致子集内计算（每候选 75 条冻结样本）。

## 作用域分报（冻结样本）

| 候选 | 语言一致 宏平均 (n) | 跨语言 宏平均 (n) | 全部冻结样本 (n) |
| --- | --- | --- | --- |
| A | 69.3% (n=75) | 15.6% (n=32) | 53.3% (n=107) |
| B | 76.0% (n=75) | 12.5% (n=32) | 57.0% (n=107) |
| C | 88.0% (n=75) | 12.5% (n=32) | 65.4% (n=107) |

## 部门与脚本变体（全部冻结样本）

| 候选 | MA | PV | CO | zh-Hans | zh-Hant | en | drug_name_zh/zh-Hans | drug_name_zh/zh-Hant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 76.7% (n=30) | 42.2% (n=45) | 46.9% (n=32) | 90.0% (n=10) | 78.8% (n=33) | 34.4% (n=64) | n/a | 66.7% (n=18) |
| B | 93.3% (n=30) | 42.2% (n=45) | 43.8% (n=32) | 90.0% (n=10) | 93.9% (n=33) | 32.8% (n=64) | n/a | 94.4% (n=18) |
| C | 93.3% (n=30) | 60.0% (n=45) | 46.9% (n=32) | 100.0% (n=10) | 93.9% (n=33) | 45.3% (n=64) | n/a | 88.9% (n=18) |

## 延迟与候选数

| 候选 | 词法 P95 (ms) | 均值 (ms) | 最大 (ms) | 测量次数 | 耗尽(<K) 查询数 | 零结果查询数 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 37.52 | 13.06 | 63.40 | 1070 | 0 | 0 |
| B | 37.87 | 14.54 | 65.72 | 1070 | 0 | 0 |
| C | 32.78 | 29.01 | 54.10 | 1070 | 0 | 0 |

## 相对 A 的选择规则（仅词法部分）

| 候选 | 配对提升 (pp) | 95% CI | 提升 ≥5pp 且 CI 下界 >0 | 词法 P95 ≤ 1.25×A | 硬门禁 | 许可证阻断 | 仅凭词法证据可替代 A |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B | +6.7 | [+1.3, +13.3] | 是 | 是 | 未通过 | 否 | 否 |
| C | +18.7 | [+8.0, +29.3] | 是 | 是 | 未通过 | 是 | 否 |

未在本运行评估：端到端 Recall@5 下降 ≤1pp、关键切片端到端下降 ≤5pp、端到端 P95 ≤8s；这些需要向量/重排配置固定后另测。

**词法结论：** no candidate passes the hard gates: DEC-001 and M1 stay blocked; gates are not lowered

## 未命中明细（各候选 recall < 1 的样本）

- A：50 条 — pc-0003, pc-0014, pc-0019, pc-0020, pc-0022, pc-0026, pc-0030, pc-0031, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(unmappable)(cross), pc-0073(cross), pc-0075(cross), pc-0076, pc-0079, pc-0082, pc-0083, pc-0084, pc-0086, pc-0087, pc-0088, pc-0091, pc-0094, pc-0099, pc-0100, pc-0101, pc-0102(unmappable), pc-0107
- B：46 条 — pc-0014, pc-0030, pc-0031, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0063(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(unmappable)(cross), pc-0073(cross), pc-0075(cross), pc-0076, pc-0079, pc-0082, pc-0083, pc-0084, pc-0086, pc-0087, pc-0088, pc-0091, pc-0094, pc-0099, pc-0100, pc-0101, pc-0102(unmappable), pc-0107
- C：37 条 — pc-0020, pc-0026, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0063(cross), pc-0064(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(unmappable)(cross), pc-0073(cross), pc-0076, pc-0082, pc-0095, pc-0096, pc-0100, pc-0101, pc-0102(unmappable)
