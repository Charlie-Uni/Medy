# 实现记录 124：safety-v2-provisional 冻结；ADR-0002 候选 D（pg_textsearch BM25）实验到词法单项

日期：2026-10-06。决策人对记录 123 §3 / 上一轮四件事答复「可以 按照建议来」。本记录的两项都不花模型费用；镜像下载约 250 MB（决策人同意在热点上拉取）。

## 1. safety-v2-provisional 冻结

- 变更确认表 `drafts/sheets/safety-v2-changes.md` 的 8 条结论由实现方按决策人的批准登记为 OK，并在表尾写明依据与登记人；annotator-01 的独立逐条确认仍缺，所以版本仍为 provisional。
- 新工具 `evals/safety_set/tools/freeze.py`：`check_safety.py` 必须 0 问题、复核不得 pending、草案版本标签须一致，否则拒绝；输出 `samples.jsonl`（170 条现行样本）、`withdrawn.jsonl` + `withdrawn_manifest.json`（7 条撤下样本原文）、复核结论与提示、确认表副本、`manifest.json`（计数、合成文档与金丝雀、复核来源、确认记录、supersedes）、`SHA256SUMS`；`dataset_hash` 为 SHA256SUMS 文本的 SHA-256（与主集同法）。
- 结果：`evals/safety_set/safety-v2-provisional/`，**dataset_hash a615186c7070ce5c69f3dbbac27257faa93d2c5c3292cfa81c201f4b7e139e28**，170 条（9 类配额不变），撤下 7 条。
- `safety_run.py --dataset <冻结目录>` 从冻结样本运行并把版本与哈希写进结果；`build_replay_set.py` 从安全运行结果里取安全集版本，不再写死。

接下来是付费的两步（待决策人同意）：冻结版本上的正式安全运行（约 0.7 USD），然后以它和 F2 重建回放集 replay-v4（免费）。

## 2. 候选 D：镜像、适配器、硬门禁与词法单项

| 步骤 | 结果 |
| --- | --- |
| 镜像 | `medy-dec001-d:pg17-pgtextsearch-1.5.1`（`pgvector/pgvector:pg17` + 官方 deb，资产 SHA-256 在 `builds/d/build-metadata.json`）；扩展最新版是 10-02 发布的 1.5.1，ADR 预登记时查到的是 1.5.0，已在 ADR 更正 |
| 隔离冒烟 | 扩展加载正常；`<@>` 返回取负的分数，无匹配行得 0（适配器用 `< 0` 排除）；行级权限下 2 万行、19,000 行隐藏且得分更高：k = 20 / 500 / 2000 返回 20 / 500 / 1000，零泄漏，计划为索引扫描 + 逐行过滤 |
| 服务器 | `medy-dec001-d-exp`（本机 5435），`medops_v2` 经 `pg_dump` 数据恢复：333 份 active、36,100 块、向量与词法索引齐全，chunk UUID 相同（探针 105 条 gold 映射逐一核对一致） |
| 适配器 | `medops.retrieval.lexical.pg_textsearch_bm25`：与 A2 同一套 `tok-jieba-v2` 词元，`text_config = simple`，k1 = 1.2、b = 0.75；套件 22 项通过（普通角色 + FORCE RLS 零泄漏、候选数、身份与版本规则、可复现） |
| 词法探针（75 条语言一致） | **D 78.7% 对 A2 49.3%**，六个切片全部更高，零泄漏；D 词法 P95 **40 ms** 对 A2 164 ms |
| 实现调整 | 预登记的「同一语句精确计数」在该扩展上每查询约 800 ms（给所有匹配行打分），改为多取一行判定耗尽后 top-k 只要几毫秒；召回逐题相同，两次运行都保留 |

A2 在 9 月 20 日的 16 份文档上是 77.3%，语料扩到 333 份后掉到 49.3%：`ts_rank_cd` 没有 IDF，高频词把 gold 挤出前 20。这解释了为什么已发布策略要靠向量通道、词表、多查询和文档聚焦把端到端拉回 87%。

端到端（主集 553 条有 gold 样本、已发布策略去掉翻译、A2 对 D）：Recall@5 **85.71% 对 87.34%，+1.63 pp，CI [+0.18, +3.26]**，赢 14 输 5；按预登记规则（≥ 5 pp）**D 不取代 A2**。词法单项的 29 个百分点到端到端只剩 1.6：向量通道、词表、多查询、文档聚焦和重排已经补回了大部分。判定与重试条件写在 ADR-0002 修订 5 的回填里。过程中适配器补了两处（版本核对交给首次调用、支持文档聚焦的限定检索），端到端运行因此跑了三次，前两次无结果。

## 3. 改动清单

| 文件 | 改动 |
| --- | --- |
| `evals/safety_set/tools/freeze.py`、`evals/safety_set/safety-v2-provisional/`、`drafts/sheets/safety-v2-changes.md`、README | 冻结 |
| `evals/harness/tools/safety_run.py`、`evals/replay/tools/build_replay_set.py` | `--dataset`；安全集版本从运行结果取 |
| `src/medops/retrieval/lexical/pg_textsearch_bm25.py`、`tests/integration/test_lexical_pg_textsearch_bm25.py` | 候选 D 适配器与套件 |
| `evals/experiments/lexical/builds/d/`、`runs/2026-10-06-rev5-candidate-d{,-kplus1}` | 镜像配方、构建元数据、两次探针运行 |
| `src/medops/evals/experiments/dec001_run.py`、`evals/replay/tools/recall_diag.py`、`evals/harness/tools/safety_run.py` | 运行器与诊断工具支持候选 D 与另一台服务器 |
| `docs/adr/ADR-0002-lexical-retrieval-selection.md` | 修订 5 的版本更正与词法结果回填 |

## 4. §9 自审

- 冻结前校验归零、复核齐全、版本一致由工具强制；冻结目录不可改写（工具拒绝覆盖）。
- 决策人的批准被登记为确认依据并写明登记人，没有冒充 annotator-01。
- 候选 D 的所有数字来自本机、同一语料、同一分词、同日重建的 A2 索引；实现调整与两次运行都留痕。
- 没有把 D 的词法优势写成选型结论：选择规则看端到端，另有两项硬门禁未做。
