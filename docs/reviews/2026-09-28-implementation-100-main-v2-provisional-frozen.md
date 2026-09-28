# 实现记录 100：10% 复核签字与 main-v2-provisional 冻结

日期：2026-09-28。决策人对记录 99 §4 第 2 项回复「签字」；据此完成 10% 抽样复核的人工签字记录，并以零费用冻结扩语料后的主评测集版本。

## 1. 签字

- [qa_sample_2026-09-28.md](../../evals/main_set/qa_sample_2026-09-28.md)：23 行「结论」列填「通过（决策人 2026-09-28 签字，采信 LLM 预检）」，末节记录签字依据：LLM 预检（机械核对 + 抽查页目视）与记录 96 的机械核查，决策人未逐页亲自对照。
- 效力：满足决策 86 C.3 的形式要求；第二人工复核仍缺，版本继续为 provisional。

## 2. 冻结 main-v2-provisional

| 项 | 值 |
| --- | --- |
| 目录 | `evals/main_set/main-v2-provisional/` |
| corpus.json | = `corpus_v2.json`，313 份（79 份与 v1 相同 + 234 份新增，含 5 份 `-r2` 质量复核记录） |
| samples.jsonl | 与 main-v1-provisional 逐字节相同（614 条：answerable 553 / no_answer 61 / conflict 52；derived 200；imported 107） |
| review_prompt.md / review_evidence/ | 原样承接 v1 |
| pii_exceptions.json | 承接 v1，`dataset_version` 改为 main-v2-provisional |
| manifest | `supersedes = main-v1-provisional`，`change_reason` 写明语料扩展与「须以新版本重跑全部实验」；`counts.documents = 313`；`second_human_review = pending` |
| 冻结 | `freeze.py --frozen-at 2026-09-28`：draft 模式零错误 → SHA256SUMS → frozen 模式零错误；`dataset_hash = 0924987ed7f6f9ba43883969d2be6122053fde811dc42d09eea3f940288b2338` |

冻结只固定数据；spec 规定的「对全部候选完整重跑实验」是付费步骤，待预算（记录 99 §3–§4）。v1 目录未改动。

复核：`shasum -a 256 -c SHA256SUMS` 四文件 OK；以 spec-m1 schema（`evals/main_set/schema`）在 frozen 模式重跑校验器，v1 与 v2 均 0 错误 0 警告。注意 `python -m medops.evals.probe <dir>` 默认用探针 spec-v1 schema，对主集目录会报 1,846 / 1,847 条 `pii_exceptions` 编号模式错误（v1 同样如此），不是数据问题；主集须用 `freeze.py` 或显式传入 spec-m1 schema 目录校验。

## 3. 后续（与记录 99 §3 相同的顺序）

充值 → 主集全量运行与安全集运行（在 307 份语料上）→ `build_replay_set.py` 构建 replay-v2 → 创建 loop 用户、从 Trace 生成案例 → 候选带 `case_ids` 与新门禁报告提交 → 批准 → 金丝雀。零费用且已获指示的部分到此全部完成。

## 4. §9 自审

- 冻结用的是仓库既有工具与校验器，未改规则；样本未动，只换语料。
- 签字如实记录了依据与边界（LLM 预检 ≠ 逐页人工）。
- 未启动任何付费运行。
