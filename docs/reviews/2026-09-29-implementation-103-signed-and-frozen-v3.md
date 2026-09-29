# 实现记录 103：「签字批准」执行——三份暂缓文档激活、10% 抽样签字、main-v3-provisional 冻结

日期：2026-09-29。决策人对记录 102 §5 的三项回复「**签字批准**」：cand-0371 激活、cand-0364 / cand-0374 质量复核放行、10% 抽样签字。本记录是执行结果；付费步骤仍未启动。

## 1. 签字与激活

| 事项 | 执行 | 核对 |
| --- | --- | --- |
| 10% 抽样签字 | [qa_sample_2026-09-29.md](../../evals/main_set/qa_sample_2026-09-29.md) 10 行「结论」填「通过（决策人 2026-09-29 签字，采信 LLM 预检）」，末节记录签字依据（LLM 预检 + 记录 102 §2 机械核查，未逐页亲自对照） | 满足决策 86 C.3 的形式要求；第二人工复核仍缺，版本继续为 provisional |
| cand-0371 美贊錠 | 两库 `activate --document-key tfda-label-misul-tablets-200-mg --effective-from 2016-06-02`，理由写明 Ⓒ 记号按印刷版次代号处理（同厂 cand-0372 同位置为 Ⓐ） | 两库均 `activated`；审计 reason 含决策来源 |
| cand-0364 抑痛寧、cand-0374 鹽酸氯普魯麻淨 | 与记录 99 同一流程：M1-11 `withdraw_document` 撤回 low_trust draft（审计 `document_withdrawn`）→ corpus_v3 记录键改为 `<key>-r2`、`version_label` 追加「质量复核 2026-09-29」→ `load --only <2 键> --accept-quality（审计 quality_review_override）--share-source reviewer-01（审计 source_share_confirmed）` → `activate --document-key` | 两库：`-r2` 均 trusted、active；旧键 withdrawn。[activation_plan_2026-09-29.json](../../evals/main_set/activation_plan_2026-09-29.json) 三条从 `held_back` 移入 `documents`（保留 `held_reason_2026-09-29`），`quality_reviewed_r2` 记录新旧键 |

现状：**medops_v2 active 333（MA 125 / PV 127 / CO 81）**，archived 7，withdrawn 7，draft 3（09-28 之前的旧 low_trust）；**medops_v2_safety active 339** = 333 + 6 份 `sf-*` 合成注入文档。决策 86 的 320（120 / 120 / 80）已达到并全部经签字流程。

## 2. 冻结 main-v3-provisional

| 项 | 值 |
| --- | --- |
| 目录 | `evals/main_set/main-v3-provisional/` |
| corpus.json | = [corpus_v3.json](../../evals/main_set/corpus_v3.json)（字节相同），339 份 = 313（逐字承接 v2）+ 26（含 2 份 `-r2` 记录） |
| samples.jsonl / review_prompt.md / review_evidence/ | 与 main-v1/v2-provisional 逐字节相同（614 条：answerable 553 / no_answer 61 / conflict 52；derived 200；imported 107） |
| pii_exceptions.json | 承接 v2，`dataset_version` 改为 main-v3-provisional |
| manifest | `supersedes = main-v2-provisional`，`change_reason` 写明新增 26 份、样本未变、须以新版本重跑全部实验；`counts.documents = 339`；`second_human_review = pending` |
| 冻结 | `freeze.py --frozen-at 2026-09-29`：draft 模式零错误 → SHA256SUMS → frozen 模式零错误；`dataset_hash = 56c1627af2655a8e9438fdedc9dd61aca76d5b2f1115053ee45c804280469994`；`shasum -a 256 -c SHA256SUMS` 四文件 OK |

v1 / v2 目录未改动。冻结只固定数据；spec 规定的「对全部候选完整重跑实验」是付费步骤。

## 3. 里程碑状态

M5-01 的验收口径是「300–500 份许可清楚的公开文档治理入库，记录原始来源、版本、部门用途与许可依据；合成 fixture 不充数量」：现有 333 份真实文档，每份带许可证据、来源、版本与部门，均经决策人签字与 10% 抽样签字，判为**已实现**（进度 77.8% → 78.5%，M5 3.5/8 → 4/8）。扩语料后的全量重测与验收属 M5-03 / M5-05，不在本项之内。此判断由实现方作出；决策人 2026-09-29 回复「可以 按照建议来」，确认 M5-01 标为已实现，重测的账记在 M5-03 / M5-05 名下。

## 4. 下一步（付费，待充值与「开始」）

按记录 101 §5 的顺序：主集全量运行（614 条 ≈ 4.7 USD）+ 安全集运行（≈ 0.65 USD）→ `build_replay_set.py` 构建 replay-v2 → 检索四件套候选在 replay-v2 上两臂三轮（≈ 13 USD）→ 门禁报告写入 [提交文件](../../evals/replay/candidates/2026-09-29-retrieval-bundle.submission.json) 的 `evidence.gate` → `adapt submit` → 决策人批准（approver ≠ 作者）→ 金丝雀 ≤ 10% → 24 h 观察 → 全量。余额约 8 USD，需先充值约 18 USD（<https://platform.openai.com/settings/organization/billing/overview>）。运行须 caffeinate、合盖不睡眠、不与其他重负载并行。

## 5. §9 自审

- 三份文档的激活都有决策人「签字批准」为依据，理由写入审计；`-r2` 流程与记录 99 一致，未原地改写任何记录。
- 冻结用仓库既有工具与 spec-m1 校验器，样本未动，只换语料；v1 / v2 未改。
- M5-01 状态变更按验收口径判断并在本记录与回复中标明，可否决。
- 未启动付费运行；口令、DSN 未出现在记录或日志。

## 6. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`：ruff、mypy、pytest **1263 passed / 70 skipped**（集成测试连库）、Schema 无漂移、`git diff --check` 通过；记录内链接全部存在。
