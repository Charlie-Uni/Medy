# DEC-001 词法对比运行报告：2026-10-06-rev5-candidate-d

- 用途：ADR-0002 revision 5: candidate D (pg_textsearch BM25) against A2 on the full 333-document corpus (36,100 chunks); D holds a restored copy of medops_v2 with identical chunk ids
- 运行清单 SHA-256：`4c1a18aa0b2d7c4434820b2d4b131e2c7aaeacb206cfbad0d8d3a6a1394db2fd`（查询前写出）
- 数据集：v2，dataset_hash `1fc5089f6fa7f80a1a5e23940826b0d4c811cde29e225dd8305241a33beb0321`
- Git HEAD：`ea54347d53425876555d1825e0f7eee96853fac9`；as_of 2026-09-20；K=20；预热 5 遍、测量 10 遍、种子 20260920；并发 1
- 环境：macOS-26.5.2-arm64-arm-64bit，8 CPU

## 候选与索引

| 候选 | 服务器 | 镜像 | 扩展 | 索引版本 | 分词器版本 | 词典版本 | 映射 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A2 | localhost:5432 | `dev cluster` | vector 0.8.6 | `pg-simple-fts-v1` | `tok-jieba-v2` | `jieba-0.42.1+default+stop:b3f772a000465cb7` | 105 mapped / 2 unmappable |
| D | localhost:5435 | `dev cluster` | pg_textsearch 1.5.1, vector 0.8.7 | `pg-textsearch-bm25-v1` | `tok-jieba-v2+pg_textsearch-1.5.1:simple:k1=1.2:b=0.75` | `jieba-0.42.1+default+stop:b3f772a000465cb7` | 105 mapped / 2 unmappable |

## 硬门禁（ADR-0002）

| 候选 | 严格宏平均 Recall@20 | drug_name_zh | dose_unit | negation | time_window | protocol_id | mixed_zh_en | 泄漏 | 可复现 | 通过 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A2 | 49.3% ✗ | 27.8% (n=18) ✗ | 47.4% (n=19) ✗ | 57.9% (n=38) ✗ | 52.6% (n=19) ✗ | 41.2% (n=17) ✗ | 62.3% (n=53) ✗ | 0 | 是 | 未通过 |
| D | 78.7% ✗ | 50.0% (n=18) ✗ | 73.7% (n=19) ✗ | 89.5% (n=38) | 84.2% (n=19) ✗ | 70.6% (n=17) ✗ | 86.8% (n=53) | 0 | 是 | 未通过 |

硬门禁按 ADR-0002 修订 1 在语言一致子集内计算（每候选 75 条冻结样本）。

## 作用域分报（冻结样本）

| 候选 | 语言一致 宏平均 (n) | 跨语言 宏平均 (n) | 全部冻结样本 (n) |
| --- | --- | --- | --- |
| A2 | 49.3% (n=75) | 0.0% (n=32) | 34.6% (n=107) |
| D | 78.7% (n=75) | 15.6% (n=32) | 59.8% (n=107) |

## 部门与脚本变体（全部冻结样本）

| 候选 | MA | PV | CO | zh-Hans | zh-Hant | en | drug_name_zh/zh-Hans | drug_name_zh/zh-Hant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A2 | 36.7% (n=30) | 37.8% (n=45) | 28.1% (n=32) | 90.0% (n=10) | 39.4% (n=33) | 23.4% (n=64) | n/a | 27.8% (n=18) |
| D | 70.0% (n=30) | 62.2% (n=45) | 46.9% (n=32) | 100.0% (n=10) | 72.7% (n=33) | 46.9% (n=64) | n/a | 50.0% (n=18) |

## 延迟与候选数

| 候选 | 词法 P95 (ms) | 均值 (ms) | 最大 (ms) | 测量次数 | 耗尽(<K) 查询数 | 零结果查询数 |
| --- | --- | --- | --- | --- | --- | --- |
| A2 | 163.87 | 73.49 | 203.66 | 1070 | 0 | 0 |
| D | 858.76 | 512.88 | 2041.26 | 1070 | 0 | 0 |

## 相对 A 的选择规则（仅词法部分）


**词法结论：** no candidate passes the hard gates: DEC-001 and M1 stay blocked; gates are not lowered

## 未命中明细（各候选 recall < 1 的样本）

- A2：70 条 — pc-0001, pc-0002, pc-0003, pc-0007, pc-0010, pc-0012, pc-0013, pc-0014, pc-0015, pc-0018, pc-0019, pc-0020, pc-0021, pc-0022, pc-0024, pc-0025, pc-0026, pc-0028, pc-0030, pc-0031, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0046(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0058, pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0063(cross), pc-0064(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(unmappable)(cross), pc-0071(cross), pc-0072(cross), pc-0073(cross), pc-0074(cross), pc-0075(cross), pc-0076, pc-0079, pc-0081, pc-0082, pc-0083, pc-0084, pc-0086, pc-0087, pc-0088, pc-0091, pc-0094, pc-0095, pc-0099, pc-0100, pc-0101, pc-0102(unmappable), pc-0107
- D：43 条 — pc-0001, pc-0002, pc-0003, pc-0011, pc-0014, pc-0019, pc-0020, pc-0021, pc-0026, pc-0041(cross), pc-0042(cross), pc-0043(cross), pc-0044(cross), pc-0045(cross), pc-0047(cross), pc-0048(cross), pc-0049(cross), pc-0050(cross), pc-0051(cross), pc-0052(cross), pc-0053(cross), pc-0054(cross), pc-0055(cross), pc-0056(cross), pc-0060(cross), pc-0061(cross), pc-0062(cross), pc-0063(cross), pc-0064(cross), pc-0065(cross), pc-0066(cross), pc-0067(cross), pc-0068(cross), pc-0069(cross), pc-0070(unmappable)(cross), pc-0073(cross), pc-0076, pc-0082, pc-0095, pc-0096, pc-0100, pc-0101, pc-0102(unmappable)
