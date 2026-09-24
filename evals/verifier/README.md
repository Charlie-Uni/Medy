# DEC-003：Verifier 支持度判定的对比实验（`evals/verifier/`）

- 决策：基线 §10 DEC-003 "Verifier 使用专用 NLI 还是小 LLM"，判据为支持/矛盾准确率、可解释性、成本。ADR-0010 已定运行时厂商为 OpenAI；本实验决定判定臂用哪一档模型，以及确定性规则能覆盖多少。
- 原则：基线 5.4 第 5 条——数字、单位、否定词、时间窗先由确定性规则判定，模型只处理规则未决的部分。所以对比对象不是"规则 vs 模型"，而是"规则 + 各档模型的兜底"。

## 数据（`dec003/pairs.jsonl`，本地生成，不入 Git）

`tools/build_pairs.py` 只用已冻结、已复核的数据构造，不新增标注：

| 类别 | 来源 | 标签依据 |
| --- | --- | --- |
| supported | 陈述 = 样本 gold `key_text`，证据 = 映射到的 gold chunk 文本 | 映射保证 key_text 落在该 chunk（PR 命中规则） |
| not_supported/same_doc | 同一文档中与 gold chunk 最近、且不含 key_text 的 chunk | 规范化后不包含 |
| not_supported/other_doc | 另一文档的随机 chunk（seed 20260923） | 同上 |
| contradicted/numeric | key_text 中第一个剂量/时限/频次数值改为两倍 | 变换已记录，可逐条审 |
| contradicted/negation | key_text 的否定翻转（删除 不得/禁用/not…，或在 應/should 后插入 不/not） | 同上 |

2026-09-23 生成：546 条样本（553 条有答案中 7 条 gold unmappable 跳过）→ 2,076 对：supported 546、same_doc 546、other_doc 546、numeric 148、negation 290。切片、部门、语言随样本。局限：陈述是逐字条款而非改写后的回答句，对"包含"类规则偏乐观；矛盾为合成，只覆盖数值与否定两种形态。

## 臂与指标

- 臂 0 `rules`：`medops.verification.verify_claims` 不配判定模型（规则 → 包含 → 词元重叠，均带否定极性）。`tools/run_rules_arm.py`。
- 臂 1+ `cli`：同一 `JUDGE_SYSTEM` 提示，经订阅 CLI 批量判定（Claude 各档，零 API 花费）。`tools/run_cli_arm.py --model <id> --limit 300 --seed 1`。
- 臂（待 key）：OpenAI 各档经 Model Gateway（`gpt-6-luna`、`gpt-5.4-mini`、`gpt-6-sol`），Gemini 可选。
- 指标：总体准确率；**错接受率**（非 supported 被判 supported，安全相关，越低越好）；分类别、分切片准确率；混淆矩阵；费用；规则独立决定的比例。

## 结果

见 `dec003/results_*.md`（追踪）与实现记录 53。

- 复验用例 `dec003/recheck_cases.jsonl`（claim + chunk id，证据文本运行时从库中读取，不入库）：`tools/run_recheck_cases.py` 让这些对走生产 Verifier（规则 + 判定模型）并与预期比对；`--no-judge` 只跑规则用于工具冒烟。首个用例来自安全集 ss-0124（记录 69 缺陷 3）。
