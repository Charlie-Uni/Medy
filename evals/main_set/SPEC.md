# 主评测集规范（main_set，spec-m1 v1.1）

> - 状态：v1.1（2026-09-21）。v1.0 定稿五个参数；v1.1 登记决策人回复“开始 第二人工复核人暂无”后的执行口径：首个冻结版本为 `main-v1-provisional`（第二人工复核 `pending`），并写入 §3 字段、§4 流程细节与 §8 机械规则（PR-16 至 PR-19）。
> - 依据：[工程基线](../../docs/ENGINEERING_BASELINE.md) 5.8、5.9、M1-20/M1-21；[探针集规范](../probe/precise_clause/SPEC.md)（spec-v1.1）；[ADR-0002](../../docs/adr/ADR-0002-lexical-retrieval-selection.md) 最终判定；[ADR-0007](../../docs/adr/ADR-0007-embedding-and-reranker-selection.md)。
> - 原则：能复用探针集的规则、schema、校验器与复核工具就复用；只新增主评测集必须有的部分（无答案与冲突场景、更大的样本量、第二人工复核政策）。

## 1. 目的与门禁

- M1-21 的判定输入：事实回查后（可含 ADR-0007 重排）的 **严格宏平均 Recall@5 ≥ 85%**，另报 Hit@5、失效版本引用率（必须为 0）、按部门 / 语言 / 切片的可复现报告；探针集（107 条）并入后保留独立报告。
- 无答案样本单独评测：abstention / no-answer accuracy（应声明证据不足或拒答的样本中被正确处理的比例），不进入 Recall@5 分母（基线 5.9）。目标值待决策人定（建议 ≥ 90%）。
- 冲突场景（同 family 多版本、同题多文档矛盾）单独切片报告：当前版本被引用且历史版本未被当作现行证据的比例必须为 100%（INV-DATA-03）。

## 2. 规模与构成（建议值，待定稿）

| 项 | 建议 | 说明 |
| --- | --- | --- |
| 有答案样本 | ≥ 300（含探针 107） | 每文档非派生样本上限 **8**（已定；探针为 6） |
| 无答案样本 | ≥ 40（已定） | 问题在语料范围内但语料中无对应条款（如问某药未记载的相互作用）；gold 为空，`answerable=false`；abstention accuracy 目标 **≥ 90%**（已定） |
| 冲突/版本样本 | ≥ 20 | 需要两份文档或两版本：入库一份"旧版"（归档）与"新版"（现行），问题指向被修订的条款；gold 只指向现行版本 |
| 部门 | MA / PV / CO 各 ≥ 60 | 与候选清单部门分布匹配（MA 仿單 27 份、PV 指南 30 份、CO 指南 17 份） |
| 语言（按 gold 文档） | zh-Hant ≥ 80、en ≥ 150、zh-Hans ≥ 20（已定） | zh-Hans 仅 5 份 MedDRA 文档（上限 40 条非派生），下限 20 |
| 切片 | 探针六切片各 ≥ 20；新增 `version_conflict`、`no_answer`、`long_context`（条款跨页或 > 1,500 字符）各 ≥ 20 | `injection` 与 `high_risk` 属安全评测（M2），不在本集 |
| 英文孪生 | 允许（spec-v1.1 规则不变），不计入非派生上限 | 跨语言切片继续单独报告 |

## 3. 样本结构

沿用探针 `probe_sample.schema.json`，扩展：

- `answerable: bool`（默认 true）；`answerable=false` 时 `required_gold_evidence` 必须为空，`expected_behaviour` 取 `insufficient_evidence` 或 `refuse`（高风险不在本集）。
- `conflict`（可选）：`{"family_document_keys": [...], "current_document_key": ..., "clause_topic": ...}`；gold 只能落在 `current_document_key`。
- `dataset_version` 形如 `main-v1`（第二人工复核未完成时为 `main-v1-provisional`）；`derived_from` 规则同 spec-v1.1；新样本 `sample_id` 前缀 `ms-`，并入的探针样本保留 `pc-` 编号与其探针复核记录（manifest `imported_samples` 绑定探针版本、样本文件哈希与提示哈希）。
- `answerable=false` 时另有 `abstention`：`scope_document_key`（问题所针对的语料文档）、`topic`、`absence_check`（工具的关键词缺席核查结论）、`document_pages`（打包给复核人的页号，PR-09 据此重建输入）。
- 每条新样本记录 `drafted_by`（`kind`、`id`、`model`）；`conflict.synthetic=true` 时 `notes` 必须写明“合成冲突”。
- `long_context` 由工具按规则计算：任一 gold 的 `evidence_span.text` 超过 1,500 字符，或 gold 跨两页以上。
- gold 锚定、`key_text` 最小性（P1）、切片判定口径（P2/P3）、norm-v1、命中规则全部沿用探针 SPEC §6–7。

## 4. 标注与复核流程（基线 5.9）

1. 起草：LLM 起草助手（`drafter-llm-03`，claude-sonnet-5，Claude Code CLI、工具关闭；提示原文 `drafts/main-v1/drafting_prompt.md` 与 `drafting_prompt_noanswer.md`，每次调用记录提示哈希、模型回显与费用于 `drafts/main-v1/raw*/`）按文档页文本提出候选；工具逐条在 norm-v1 页文本中重新定位 `key_text` 与 span、重算偏移、核对页内唯一、按 P2 机械计算 `mixed_zh_en`、按规则计算 `long_context`；无答案候选的 `absence_terms` 须在 scope 文档全部页文本中出现 0 次。实现方筛选后每条标注 `drafted_by`。起草者与 LLM 复核人（claude-opus-5）不同（spec-v1.1 §8.1）。
2. 人工标注：annotator-01 逐条确认或改写（query、gold、slices、answerable）；确认表为 `drafts/main-v1/samples_draft_{MA,PV,CO,EN,NA}.md`。
3. LLM 独立复核：固定模型标识 claude-opus-5（同探针 spec-v1.1 §8.1），提示原文 `review_prompt.md`（主集版本，含无答案四项与孪生对照），批次 `MA`、`PV`、`CO`（非派生有答案样本，含冲突样本）、`EN`（英文孪生）、`NA`（无答案，输入为 scope 文档的打包页文本）；并入的探针样本不重复复核。
4. 第二人工复核：**全部争议样本**，以及 `dose_unit`、`negation`、`time_window`、`version_conflict`、`no_answer` 样本必须有第二人工复核；其余随机抽取 ≥ 20%。LLM 不计作第二人工。**决策人 2026-09-21 答复“第二人工复核人暂无”**：manifest `second_human_review.status=pending`，数据集只能以 `main-v1-provisional` 冻结与运行（schema 强制），所有引用本集的报告须标注“第二人工复核未完成”；指定复核人并完成复核后再以 `main-v1` 升版。
5. 争议裁决：人工裁决并写 `resolution_note`；同族联动规则同探针。
6. 冻结：复用 `freeze_v2.py` 流程（哈希、SHA256SUMS、映射、复核证据绑定），版本 `main-v1`。

## 5. 语料与许可

- 只用 `eligible` 文档（ADR-0003）；候选清单 v0.7 签字后入库；TFDA 仿單完成图像层目视后入库。
- 冲突样本需要同 family 的两个版本：优先用真实修订对（如 GVP 模块的历史 Rev 文件、TFDA 同一許可證的历史仿單）；取不到时**允许合成冲突**（已定）：用 M1-11 的发布流程把同一文档以两个 `document_key`、不同 `version_label` 与 `effective_from` 入库并归档旧版，`notes` 标明“合成冲突”，样本的 `conflict.synthetic=true`。

## 6. 运行与报告

- 端到端运行复用 `medops.evals.experiments.e2e_run`：新增 `answerable=false` 的处理（回查后 top-5 为空或 Verifier 判"证据不足"计为正确——M1 阶段以"回查后无证据 / 重排分数低于阈值"近似，阈值待 M2 Verifier 定）。
- 报告：总表 + 部门 / 语言 / 切片 + 探针子集独立表 + 无答案表 + 冲突表；配对 bootstrap 用于系统间比较。

## 7. 参数决定（2026-09-21，决策人“按照你的建议来”）

1. 每文档非派生上限 **8**。
2. 无答案样本 **≥ 40**，abstention accuracy 目标 **≥ 90%**。
3. 第二人工复核人：**暂无**（决策人 2026-09-21）；首个版本为 `main-v1-provisional`（见 §4 第 4 条）。
4. 冲突样本：**允许合成冲突**，须标注 `synthetic=true`。
5. zh-Hans 下限 **≥ 20**。

## 8. 校验规则（spec-m1 增补）

校验器与探针共用（`python -m medops.evals.probe <version_dir> --schema-dir evals/main_set/schema --pages DIR`）；schema 由 `evals/main_set/tools/make_schemas.py` 从探针 schema 派生。探针 PR-01 至 PR-15 全部沿用，差异与增补如下：

| 规则 | 内容 |
| --- | --- |
| PR-03 | `manifest.minimums`：有答案 ≥ 300（含探针与孪生）、无答案 ≥ 40、冲突 ≥ 20、九个切片各 ≥ 20、部门各 ≥ 60、zh-Hans ≥ 20、zh-Hant ≥ 80、en ≥ 150（语言按 gold 文档计，无答案按 scope 文档计）；`counts` 另含 `answerable`、`no_answer`、`conflict`、`derived`、`imported` |
| PR-04 | 每文档非派生上限取 `manifest.minimums.max_samples_per_document`（主集 8，探针 6） |
| PR-09 | 并入的 `pc-` 样本按 `manifest.imported_samples` 的 `reviewer_id` 与 `prompt_hash` 校验；`ms-` 样本按本版复核人校验；复核证据批次为 `MA/PV/CO/EN/NA`，无答案样本的复核输入由 `abstention.document_pages` 重建 |
| PR-16 | 并入样本恰为 `imported_samples.path` 所指冻结探针版本的全部样本，逐条 canonical 字节一致；探针文件哈希、`dataset_hash`、`status=frozen` 一致 |
| PR-17 | 无答案样本：`scope_document_key` 在语料中、无 gold、`expected_behaviour` 为 `insufficient_evidence|refuse`、带 `no_answer` 切片、不得为孪生；有答案样本至少一条 gold |
| PR-18 | 冲突样本：`conflict` 块与 `version_conflict` 切片同现；`current_document_key` 在语料中且全部 gold 落在该文档；family 键与 `manifest.conflict_fixtures` 登记一致；`synthetic=true` 时 `notes` 写明合成 |
| PR-19 | `long_context` 机械规则：任一 span > 1,500 字符或 gold 跨两页以上（并入的探针样本豁免） |

manifest 另含 `gates`（Recall@5 0.85、abstention accuracy 0.9、失效版本引用率 0、冲突现行版引用率 1.0）、`second_human_review`（`pending` 时版本号必须以 `-provisional` 结尾）与 `conflict_fixtures`（记录 50 登记的 5 个合成冲突 family）。
