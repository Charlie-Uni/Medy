# Loop 回放集规范 spec-r1 v0.2（M4-06，DEC-014）

- 日期：2026-09-25；决策：记录 74 C（决策人 2026-09-25「同意」）
- 输入固化修订：2026-10-08，记录 135；原样本量、筛选、评分和发布门槛不变，历史 v0.1 冻结文件不改写。
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

## 8. 当前执行状态（2026-10-08）

- 三次运行、配对比较与 bootstrap 的回放运行器已经实现，入口为 `tools/replay_run.py`；本文件 §2 保留首版来源说明，不代表当前仍停在首版。
- 当前登记 replay-v3：614 条主集项、170 条旧安全项、200 条筛选子集。来源仍是运行导出，没有真实用户流量集；它不能作为未见验证集。
- replay-v3 的安全来源仍为 safety-v1 草案。下一版本需要 safety-v2 对应正式运行，不能只替换版本号或复用旧标签。
- 新运行导出可保存 `required_gold_groups`，组内任选、组间全需；旧扁平 gold 保留原计分语义。记录 132 起新运行固定 `main-outcome-v2`，无答案必须按预期证据不足升级，系统失败不再算成功；评分绑定、基线复用与分项分母见[评测入口 §6](../README.md)。旧冻结标签与历史成绩保持原版本。
- `make eval-check` 检查登记版本、文件哈希及来源运行关系。文件通过不等于独立人工复核完成；安全项的 `historical` 仍只对 F 类有值。

## 9. 新回放的完整输入协议（记录 135）

新导出要求两套来源均为冻结数据集，并且对应运行具有一致的 `dataset_binding.json`、结果中的版本/数据哈希和完整样本覆盖。主集运行必须使用当前 `scoring_binding.json`。逐行保存 `sample_input_sha256` 与运行 `versions`，导出时与冻结样本和运行汇总核对；不允许将旧行补写新哈希后冒充重新运行。

安全项增加 `sample`（完整冻结样本）、`sample_sha256`；manifest 标识 `safety_input_format=embedded-safety-sample-v1`。ACL、攻击 canary、Skill 调用及 scopes、历史请求参数和预期均随回放冻结。执行时只读取这些内嵌输入，在加载模型前核对哈希、身份、版本和外层字段。源安全版本来自实际 manifest，同时固定来源 `dataset_hash`、结果和绑定文件的哈希，不再写死 v1。

旧 replay-v1/v2/v3 缺少完整安全执行输入，仍可检查文件、读取旧成绩、估算费用和执行 `--skip-safety` 的主集诊断；不能在新的安全对照中从当前草案补全。安全项被跳过时，不能宣称通过安全发布门禁。记录 135 已发现 replay-v3 的 `ss-0125` 预期与当前草案不一致，这正是禁止该隐式补全的原因。

新导出命令必须显式给出来源运行；缺绑定、缺行、题目/预期变动、样本哈希不符、版本混用或安全检查与结论不一致均拒绝。输出目录存在时拒绝覆盖。只有真实运行完成后才能执行以下命令创建正式新版本：

```sh
venv/bin/python evals/replay/tools/build_replay_set.py \
  --out evals/replay/replay-v4 \
  --main-set PATH_TO_FROZEN_MAIN --main-run PATH_TO_COMPLETE_MAIN_RUN \
  --safety-set evals/safety_set/safety-v2-provisional --safety-run PATH_TO_COMPLETE_SAFETY_RUN
```

本协议实现不等于 replay-v4 已生成；当前仍等候对应的正式主集与安全运行。
