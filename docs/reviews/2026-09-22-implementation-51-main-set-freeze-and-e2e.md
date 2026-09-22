# 实现记录 51：主评测集 `main-v1-provisional` 冻结与端到端判定（M1-20 / M1-21）

- 日期：2026-09-22
- 范围：争议裁决收敛、冻结 `main-v1-provisional`、chunk 快照与 gold→chunk 映射、端到端运行（A2+V、事实回查、重排）与 M1-21 判定输入。争议裁决过程见[记录 50 §13](2026-09-21-implementation-50-main-set-drafting.md)。
- **第二人工复核未完成**：本记录引用的一切数字都来自 `main-v1-provisional`（基线 5.9 的分层第二人工复核待指定复核人后进行；spec-m1 §4 第 4 条）。

## 1. 决定与依据

| 决定 | 决策人回复 | 依据 |
| --- | --- | --- |
| 争议裁决四轮预填全部采纳 | "按建议来"（第四轮）、"按建议 收尾规则同意"（第五轮） | 预填规则：query 含精确条号/节号/版本号 → 补 protocol_id；只含指南名 → 保留（2026-09-22 口径）；query/span/key_text 项用复核人给出的改法 |
| 收尾规则 | 同上 | 第五轮之后的零星争议不再重跑：指南名 protocol_id 一律保留；复核人对已按其建议改过的字段再提新意见的，记"保留：第 N 轮复核非确定性，annotator-01 维持" |
| 块绑定修复方案一 | "方案一" | 318 条邻居样本以块大小 1 重跑（估 27–30 美元，实测 34.75），此后每条判定只绑自身输入 |

## 2. 冻结结果

- `evals/main_set/main-v1-provisional`：`dataset_hash 269be665c288e79210a255c7e2ceaadbb87ba1c088e9ce9e1ee5515e568c9699`，`frozen_at 2026-09-22`，`second_human_review.status=pending`。
- 614 条：有答案 553（含并入探针 107、英文孪生 200）、无答案 61、冲突 52（5 个合成 fixture family + Annex I Rev 4→Rev 5 真实修订对）；文档 79；部门 MA 133 / PV 279 / CO 202；语言（按 gold/scope 文档）zh-Hans 30 / zh-Hant 139 / en 445。
- 切片：drug_name_zh 112、dose_unit 65、negation 275、time_window 128、protocol_id 149、mixed_zh_en 569、version_conflict 52、no_answer 61、long_context 23；全部 spec-m1 下限满足。
- 复核证据：507 条新样本 agree 464、`disputed_resolved` 43（全部有 `resolution_note`，6 条为续用）；并入探针保留 v2 复核记录（PR-16 逐字节）。LLM 复核累计 **94.85 美元**（首轮 43.06；五轮重跑 51.79，其中 34.75 为块绑定修复）。
- 冻结前三项机械检查归零：`check_drafts.py`、`review_binding_check.py`（块含作废输入）、`review_prompt_check.py`（提示可重建）。

## 3. 快照、映射与运行配置

- chunk 快照：medops_v2（76 份现行、7 份归档、3 份 low_trust draft），11,231 chunk，`regenerated_chunks_match=true`；词法索引 `a2` / `production-lexical` 与向量索引 `emb-bge-m3-dense-v1` 均覆盖 11,231 chunk（2026-09-21 构建）。
- 映射 `evals/experiments/e2e/main-v1-provisional/chunk_mapping.chunker-v2.main-v1-provisional.json`：3 条 unmappable（ms-0441-g1、pc-0070-g1、pc-0102-g1，key 区间跨相邻 chunk 边界），原样计 miss，不改样本也不改切分器。
- 运行：`medops.evals.experiments.e2e_run --dataset evals/main_set/main-v1-provisional --system A2=<映射> --database medops_v2 --rerank --warmup 1 --measured 1 --device mps --as-of 2026-09-22`，输出 `evals/experiments/e2e/runs/2026-09-22-e2e-main-v1-provisional-rerank-v1/`；无答案样本按重排分数阈值 0.3 近似弃答（spec-m1 §6，阈值待 M2 Verifier 定，报告含 0.0–0.5 扫描）。

## 4. 端到端结果（运行 `2026-09-22-e2e-main-v1-provisional-rerank-v1`，17:30–18:38，run_manifest sha256 `66ad531d…`）

| 指标 | A2+V（重排后 top-5） | 门禁 | 结论 |
| --- | ---: | --- | --- |
| 严格宏平均 Recall@5（553 条有答案） | **84.99%** | ≥ 85% | **未过**，差 1 条样本（83 miss / 553） |
| 语言一致 / 跨语言 | 87.7% (341) / 80.7% (212) | — | — |
| Hit@5 / 融合 R@20 | 85.0% / 86.6% | — | 融合候选已含 gold 的比例只高 1.6 pp，瓶颈在召回而非重排 |
| 词法单通道 / 向量单通道 R@5 | 32.2% / 76.3% | — | 词法通道在 76 份文档语料上很弱，向量通道承担主要召回 |
| 失效版本引用 / 泄漏 / 不可复现 | 0 / 3070、0、0 | 0 | 过 |
| 冲突样本（52）：历史版未被引用 | 100% | 100% | 过（INV-DATA-03 的安全半边） |
| 冲突样本：现行版被引用且历史版未引用 | 88.5% | 100% | **未过**（现行版召回 88.5%，等同该子集的 Recall） |
| 无答案（61）：弃答准确率（重排分数阈值 0.3） | 21.3%（假弃答 1.1%） | ≥ 90% | **未过**；阈值 0.5 也只有 37.7%（假弃答 3.3%），重排分数不是弃答信号，待 M2 Verifier |
| P95 延迟（614 次测量，含重排） | 5.19 s（均值 3.44 s） | M3 P95 ≤ 8 s | 参考 |

分部门：CO 81.7%（186）、MA 87.3%（110）、PV 86.4%（257）。分切片：time_window 94.5%、version_conflict 88.5%、dose_unit 87.7%、drug_name_zh 86.7%、negation 86.5%、mixed_zh_en 85.6%、protocol_id 80.8%、long_context 69.6%（23）。分语言：zh-Hans 96.2%（26）、zh-Hant 87.8%（115）、en 83.5%（412）。子集：并入探针 107 条 68.2%（记录 45 在 16 份文档语料上为 75.7%，现在语料 76 份现行文档，干扰项增多且 3 条 unmappable 计 miss）、新样本 446 条 89.0%、冲突 52 条 88.5%。

**M1-21 判定（临时，第二人工复核未完成）：未通过。** 三项未过中，Recall@5 差 1 条样本（0.01 pp），无配对系统可做 bootstrap；无答案门禁是 spec-m1 §6 明写的近似口径（阈值待 M2 Verifier），当前结果说明重排分数对"文档无答案"几乎没有区分力；冲突门禁的失败来自现行版召回而非历史版误引。按 ADR-0002 修订 3 与基线"判据不降低"的原则，不调整门禁、不删样本、不改切分器；M1-21 保持"部分"。

可见的改进方向（供决策，不在本记录内实施）：(1) 词法通道 32% 说明 A2 在大语料上的排序缺 IDF（记录 36 已指出），M2 的 LLM 查询改写与 ADR-0002 的排序侧变体是仅剩的检索侧杠杆；(2) long_context 与 protocol_id 是最弱切片，前者与切分粒度有关（3 条 unmappable 全是跨 chunk 边界）；(3) 弃答需要 Verifier 的"证据不足"判断（M2-08），不是阈值问题；(4) 并入探针子集在大语料上跌到 68.2%，说明记录 45 的 75.7% 不能与本集直接比较。

## 5. 工具与代码改动（本记录范围）

- [review_provenance.py](../../src/medops/evals/probe/review_provenance.py)：提示重建容忍 `conflict` 块的起草键序（与 `evidence_span` 同一口径），无 gold 记录的变体越界修正；4 条单元测试 [test_review_provenance_variants.py](../../tests/unit/evals/test_review_provenance_variants.py)。
- 主集工具：`apply_resolutions.py`（`--explicit` / `--sweep` / `--sheet`、`section=` / `span=` / `absence_terms=`、父问联动 `parent_query`、重跑固定块大小 1）、`disputes_sheet.py --round`、`carry_forward_resolutions.py`、`review_binding_check.py`、`review_prompt_check.py`。
- SPEC §3 登记两条主集口径（测量值不计 dose_unit；仅指南名不计 protocol_id），并注明并入探针保留 v2 口径。

## 6. 自审（§9）

1. 需求：spec-m1 §1–§8 的全部下限与规则由校验器在冻结时机械核对；第二人工复核未完成按规范以 provisional 冻结并在报告标注。
2. 逻辑：裁决只经 annotator-01 的决定列（或其明确授权的收尾规则）进入 `resolutions.json`；实现方的预填从不自动生效。
3. 安全：DSN 只在进程内构造，不进命令行与日志；PDF、页文本、复核输入包不入 Git。
4. 测试：`make check` 897 passed（新增 4 条）。
5. 复盘：见记录 50 §13 末条（提示中的切片定义与裁决口径不一致是争议率高的根因；块绑定的重跑方式是实现方失误，已工具化防止复发）。
