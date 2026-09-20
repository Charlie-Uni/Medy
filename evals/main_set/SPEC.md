# 主评测集规范草案（main_set，spec-m1 v0.1，待决策人定稿）

> - 状态：草案（2026-09-21），供决策人与候选清单 v0.7 一起审阅；定稿前不起草样本。
> - 依据：[工程基线](../../docs/ENGINEERING_BASELINE.md) 5.8、5.9、M1-20/M1-21；[探针集规范](../probe/precise_clause/SPEC.md)（spec-v1.1）；[ADR-0002](../../docs/adr/ADR-0002-lexical-retrieval-selection.md) 最终判定；[ADR-0007](../../docs/adr/ADR-0007-embedding-and-reranker-selection.md)。
> - 原则：能复用探针集的规则、schema、校验器与复核工具就复用；只新增主评测集必须有的部分（无答案与冲突场景、更大的样本量、第二人工复核政策）。

## 1. 目的与门禁

- M1-21 的判定输入：事实回查后（可含 ADR-0007 重排）的 **严格宏平均 Recall@5 ≥ 85%**，另报 Hit@5、失效版本引用率（必须为 0）、按部门 / 语言 / 切片的可复现报告；探针集（107 条）并入后保留独立报告。
- 无答案样本单独评测：abstention / no-answer accuracy（应声明证据不足或拒答的样本中被正确处理的比例），不进入 Recall@5 分母（基线 5.9）。目标值待决策人定（建议 ≥ 90%）。
- 冲突场景（同 family 多版本、同题多文档矛盾）单独切片报告：当前版本被引用且历史版本未被当作现行证据的比例必须为 100%（INV-DATA-03）。

## 2. 规模与构成（建议值，待定稿）

| 项 | 建议 | 说明 |
| --- | --- | --- |
| 有答案样本 | ≥ 300（含探针 107） | 每文档非派生样本上限 **8**（探针为 6；主集文档更多、条款更长，放宽到 8 仍避免文档集中） |
| 无答案样本 | ≥ 40 | 问题在语料范围内但语料中无对应条款（如问某药未记载的相互作用）；gold 为空，`answerable=false` |
| 冲突/版本样本 | ≥ 20 | 需要两份文档或两版本：入库一份"旧版"（归档）与"新版"（现行），问题指向被修订的条款；gold 只指向现行版本 |
| 部门 | MA / PV / CO 各 ≥ 60 | 与候选清单部门分布匹配（MA 仿單 27 份、PV 指南 30 份、CO 指南 17 份） |
| 语言（按 gold 文档） | zh-Hant ≥ 80、en ≥ 150、zh-Hans ≥ 20 | zh-Hans 受开放许可来源限制（仅 MedDRA 文档），下限按可得文档定 |
| 切片 | 探针六切片各 ≥ 20；新增 `version_conflict`、`no_answer`、`long_context`（条款跨页或 > 1,500 字符）各 ≥ 20 | `injection` 与 `high_risk` 属安全评测（M2），不在本集 |
| 英文孪生 | 允许（spec-v1.1 规则不变），不计入非派生上限 | 跨语言切片继续单独报告 |

## 3. 样本结构

沿用探针 `probe_sample.schema.json`，扩展：

- `answerable: bool`（默认 true）；`answerable=false` 时 `required_gold_evidence` 必须为空，`expected_behaviour` 取 `insufficient_evidence` 或 `refuse`（高风险不在本集）。
- `conflict`（可选）：`{"family_document_keys": [...], "current_document_key": ..., "clause_topic": ...}`；gold 只能落在 `current_document_key`。
- `dataset_version` 形如 `main-v1`；`derived_from` 规则同 spec-v1.1；`sample_id` 前缀 `ms-`。
- gold 锚定、`key_text` 最小性（P1）、切片判定口径（P2/P3）、norm-v1、命中规则全部沿用探针 SPEC §6–7。

## 4. 标注与复核流程（基线 5.9）

1. 起草：由实现方按文档条款起草（LLM 辅助），每条标注 `drafted_by`。
2. 人工标注：annotator-01 逐条确认或改写（query、gold、slices、answerable）。
3. LLM 独立复核：固定模型标识（当前 claude-opus-5，同探针 spec-v1.1 §8.1），逐条给出同意/争议与理由。
4. 第二人工复核：**全部争议样本**，以及 `dose_unit`、`negation`、`time_window`、`version_conflict`、`no_answer` 样本必须有第二人工复核；其余随机抽取 ≥ 20%。LLM 不计作第二人工。决策人指定第二人工（可为外部标注人；记录 surrogate id）。
5. 争议裁决：人工裁决并写 `resolution_note`；同族联动规则同探针。
6. 冻结：复用 `freeze_v2.py` 流程（哈希、SHA256SUMS、映射、复核证据绑定），版本 `main-v1`。

## 5. 语料与许可

- 只用 `eligible` 文档（ADR-0003）；候选清单 v0.7 签字后入库；TFDA 仿單完成图像层目视后入库。
- 冲突样本需要同 family 的两个版本：优先用 TFDA 仿單的修订版本（同一許可證的历史仿單 PDF，如平台保留）或 EMA GVP 模块的 Rev 1/Rev 2 并存文件；无法取得历史版本时，用 M1-11 的发布流程把同一文档以两个 `document_key` 入库并模拟修订（在 `notes` 标明"合成冲突"）。

## 6. 运行与报告

- 端到端运行复用 `medops.evals.experiments.e2e_run`：新增 `answerable=false` 的处理（回查后 top-5 为空或 Verifier 判"证据不足"计为正确——M1 阶段以"回查后无证据 / 重排分数低于阈值"近似，阈值待 M2 Verifier 定）。
- 报告：总表 + 部门 / 语言 / 切片 + 探针子集独立表 + 无答案表 + 冲突表；配对 bootstrap 用于系统间比较。

## 7. 待决策人决定

1. 每文档非派生上限 8（还是沿用 6）。
2. 无答案样本数量与 abstention 目标值。
3. 第二人工复核人选与其 surrogate id。
4. 冲突样本是否允许"合成冲突"（同一 PDF 以两个版本入库）。
5. zh-Hans 下限。
