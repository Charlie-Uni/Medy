# Loop 回放集规范 spec-r1 v0.1（M4-06，DEC-014）

- 日期：2026-09-25；决策：记录 74 C（决策人 2026-09-25「同意」）
- 依据：工程基线 5.8（Replay）、§8 M4-06 / M4-07、`INV-EVAL-01`（冻结评测集与候选生成上下文隔离）

## 1. 目的

给 Loop 的 Replay 阶段一个**冻结、可哈希校验、样本独立**的评测集：候选策略在其上重放，与 released 策略做配对比较（M4-07）。安全项单独构成安全回归集。

## 2. 来源与「运行导出」声明

真实用户流量尚不存在。首版 `replay-v1` 从两次已归档的运行导出：

| 来源 | 数据集 | 运行 | 项数 |
| --- | --- | --- | ---: |
| 主集 | `main-v1-provisional`（哈希 269be665…） | `evals/harness/runs/2026-09-23-full-ask-v2`（每个样本取最后一行） | 614 |
| 安全集 | `safety-v1-provisional`（草稿 170 条） | `evals/harness/runs/2026-09-24-safety-v1-draft-r2` | 170 |

manifest 以 `origin = run_export_not_live_traffic` 与 `provisional = true` 如实标注：两个来源都还没有完成人工复核；真实 Trace 积累到 ≥ 200 条 good / bad 后换版（`replay-v2`），换版走与主集相同的冻结流程（新 manifest、`supersedes`、变更原因）。

## 3. 项与标签

主集项（`items.jsonl`，`rp-####`）：样本身份（部门、kind、语言、切片、`imported` / `derived` 标志）、问题、gold chunk、观察到的运行结果（结论、reason code、引用、是否引用 gold、版本集）、标签与原因。标签规则见 `tools/build_replay_set.py` 文档表：good = 行为符合样本类型的期望（有答案且引用 gold；无答案弃答；冲突引用现行版），bad = 其余（错引、误弃答、误答、错版本）。

安全项（`safety_items.jsonl`，`rs-####`）：类别、期望块（`expected`，含 `must_not_contain` / `must_cite` / `outcome` 等）、历史请求参数、运行的检查结果；good = 全部检查通过，bad = 有检查失败，`not_exercised` = 注入 chunk 未被检索到（保留但不计数）。

## 4. 独立性

- 一项对应一个样本；`derived`（同义改写孪生）项打标并**不进入筛选子集**；`imported`（探针并入）项保留。
- 三次重复运行只算三次运行，不算三倍样本（M4-06 原文）。
- `check` 校验：id 唯一、主集问题文本无重复、good / bad 项 ≥ 200、子集 ⊆ 项集且不含 derived。

## 5. 筛选子集（DEC-014：候选筛选 200 条、三次运行约 5 美元）

`subset.json`：种子 20260925，排除 derived，bad 占 30%（不足时取全部 bad），每个标签内部门按比例分层。只有拟发布的候选才跑全量（三次约 16 美元）。

## 6. 冻结与校验

`manifest.json` 记录来源哈希（主集 `dataset_hash`、两次运行 `rows.jsonl` 的 sha256、版本集）、计数、独立性声明、隔离声明、文件哈希与 `dataset_hash`（= 排序后文件哈希行的 sha256）；`SHA256SUMS` 同步。`python evals/replay/tools/build_replay_set.py --check evals/replay/replay-v1` 重新计算并核对；单元测试 `tests/unit/evals/test_replay_set.py` 在 `make check` 里做同样的核对，任何改动都必须以新版本出现。

## 7. 隔离（INV-EVAL-01）

回放项的 id、问题文本与 gold id **不得进入** Adapt 的候选生成上下文。规则在 manifest 里声明；执行点在 M4-03：候选的 `evidence` 字段列出其生成所用的 bad case / Trace 来源，检查工具拒绝任何引用回放项的候选。

## 8. 未做

- 真实流量回放集；M4-07 的运行器（三次运行 + 配对 bootstrap）；安全项的 `historical` 只对 F 类有值。
