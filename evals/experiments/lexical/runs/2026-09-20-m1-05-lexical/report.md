# DEC-001 词法对比运行报告：2026-09-20-m1-05-lexical

- 用途：M1-05 comparison: ADR-0002 lexical Recall@20, slices, RLS leak check and lexical latency on the frozen probe v1 (15 active documents, esomen draft per owner option A)
- 运行清单 SHA-256：`a582225f5b39e24b3cb709708c53aadca54f095518a0a1ebc02c116c295926f0`（查询前写出）
- 数据集：v1，dataset_hash `5561bee58e37cd8d86b756f17e6c1a6ebed32ba54ba2ac48f4cd4adee254db7e`
- Git HEAD：`7c118333c5f1422427cd882147b925ac5368e402`；as_of 2026-09-20；K=20；预热 5 遍、测量 10 遍、种子 20260920；并发 1
- 环境：macOS-26.5.2-arm64-arm-64bit，8 CPU

## 候选与索引

| 候选 | 服务器 | 镜像 | 扩展 | 索引版本 | 分词器版本 | 词典版本 | 映射 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | localhost:5432 | `dev cluster` | vector 0.8.6 | `pg-simple-fts-v1` | `tok-jieba-v1` | `jieba-0.42.1+default` | 73 mapped / 2 unmappable |
| B | localhost:5433 | `sha256:00ce3abb08cc` | zhparser 2.3 | `pg-zhparser-fts-v1` | `zhparser-2.3+scws-1.2.3+cfg-dec001_b:8d420cfb+guc:3ff9eb8a` | `scws-dict-utf8:fd76a689f996c4e6+rules-utf8:45395f794226581f+scws-1.2.3` | 73 mapped / 2 unmappable |
| C | localhost:5434 | `sha256:f564d490dfa0` | pg_search 0.25.9, vector 0.8.6 | `pg-search-bm25-v1` | `pg_search-0.25.9+pdb.jieba:6c256ba3` | `jieba-rs-0.10.1+tantivy-jieba-0.20.0+pg_search.so:74e90e4f8015246a` | 73 mapped / 2 unmappable |

## 硬门禁（ADR-0002）

| 候选 | 严格宏平均 Recall@20 | drug_name_zh | dose_unit | negation | time_window | protocol_id | mixed_zh_en | 泄漏 | 可复现 | 通过 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 48.0% ✗ | 55.6% (n=18) ✗ | 80.0% (n=20) ✗ | 41.5% (n=41) ✗ | 35.0% (n=20) ✗ | 41.2% (n=17) ✗ | 43.4% (n=53) ✗ | 0 | 是 | 未通过 |
| B | 52.0% ✗ | 77.8% (n=18) ✗ | 85.0% (n=20) | 48.8% (n=41) ✗ | 40.0% (n=20) ✗ | 35.3% (n=17) ✗ | 41.5% (n=53) ✗ | 0 | 是 | 未通过 |
| C | 53.3% ✗ | 77.8% (n=18) ✗ | 90.0% (n=20) | 51.2% (n=41) ✗ | 45.0% (n=20) ✗ | 29.4% (n=17) ✗ | 43.4% (n=53) ✗ | 0 | 是 | 未通过 |

## 部门与脚本变体

| 候选 | MA | PV | CO | zh-Hans | zh-Hant | en | drug_name_zh/zh-Hans | drug_name_zh/zh-Hant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 63.3% (n=30) | 41.4% (n=29) | 31.2% (n=16) | 90.0% (n=10) | 66.7% (n=33) | 15.6% (n=32) | n/a | 55.6% (n=18) |
| B | 76.7% (n=30) | 41.4% (n=29) | 25.0% (n=16) | 90.0% (n=10) | 78.8% (n=33) | 12.5% (n=32) | n/a | 77.8% (n=18) |
| C | 76.7% (n=30) | 44.8% (n=29) | 25.0% (n=16) | 100.0% (n=10) | 78.8% (n=33) | 12.5% (n=32) | n/a | 77.8% (n=18) |

## 延迟与候选数

| 候选 | 词法 P95 (ms) | 均值 (ms) | 最大 (ms) | 测量次数 | 耗尽(<K) 查询数 | 零结果查询数 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 17.23 | 7.27 | 35.57 | 750 | 3 | 0 |
| B | 19.26 | 9.21 | 48.18 | 750 | 0 | 0 |
| C | 92.25 | 41.69 | 211.62 | 750 | 3 | 0 |

## 相对 A 的选择规则（仅词法部分）

| 候选 | 配对提升 (pp) | 95% CI | 提升 ≥5pp 且 CI 下界 >0 | 词法 P95 ≤ 1.25×A | 硬门禁 | 许可证阻断 | 仅凭词法证据可替代 A |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B | +4.0 | [-1.3, +10.7] | 否 | 是 | 未通过 | 否 | 否 |
| C | +5.3 | [-1.3, +12.0] | 否 | 否 | 未通过 | 是 | 否 |

未在本运行评估：端到端 Recall@5 下降 ≤1pp、关键切片端到端下降 ≤5pp、端到端 P95 ≤8s；这些需要向量/重排配置固定后另测。

**词法结论：** no candidate passes the hard gates: DEC-001 and M1 stay blocked; gates are not lowered

## 未命中明细（各候选 recall < 1 的样本）

- A：39 条 — pc-0003, pc-0014, pc-0019, pc-0020, pc-0022, pc-0025, pc-0026, pc-0027, pc-0028, pc-0029, pc-0030, pc-0031, pc-0041, pc-0042, pc-0043, pc-0044, pc-0045, pc-0046, pc-0047, pc-0048, pc-0049, pc-0050, pc-0051, pc-0052, pc-0053, pc-0054, pc-0055, pc-0056(unmappable), pc-0060, pc-0061, pc-0065, pc-0066, pc-0067, pc-0068, pc-0069, pc-0070, pc-0072(unmappable), pc-0073, pc-0075
- B：36 条 — pc-0014, pc-0025, pc-0026, pc-0027, pc-0028, pc-0029, pc-0030, pc-0031, pc-0041, pc-0042, pc-0043, pc-0044, pc-0045, pc-0046, pc-0047, pc-0048, pc-0049, pc-0050, pc-0051, pc-0052, pc-0053, pc-0054, pc-0055, pc-0056(unmappable), pc-0060, pc-0061, pc-0063, pc-0065, pc-0066, pc-0067, pc-0068, pc-0069, pc-0070, pc-0072(unmappable), pc-0073, pc-0075
- C：35 条 — pc-0020, pc-0025, pc-0026, pc-0027, pc-0028, pc-0029, pc-0030, pc-0041, pc-0042, pc-0043, pc-0044, pc-0045, pc-0046, pc-0047, pc-0048, pc-0049, pc-0050, pc-0051, pc-0052, pc-0053, pc-0054, pc-0055, pc-0056(unmappable), pc-0060, pc-0061, pc-0063, pc-0064, pc-0065, pc-0066, pc-0067, pc-0068, pc-0069, pc-0070, pc-0072(unmappable), pc-0073
