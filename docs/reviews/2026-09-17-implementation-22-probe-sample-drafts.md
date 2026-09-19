# 实现记录 22：探针集 v1 样本草稿（75 条，待决策人以 annotator-01 身份逐条确认）

日期：2026-09-17。范围：M1-01 的标注起草。按决策人确认式标注的分工（我起草、决策人逐条确认），从 16 份已入库文档起草 75 条样本，全部锚定到 norm-v1 规范化页文本并通过唯一性与偏移检查；未生成 `samples.jsonl`、`manifest.json`、`review_prompt.md`，未运行 LLM 复核，未冻结。未修改基线、SPEC、Schema、代码；未提交 Git。**状态：等待决策人确认。**

## 1. 产物

目录 [evals/probe/precise_clause/drafts/v1/](../../evals/probe/precise_clause/drafts/v1/)（版本目录 `v1/` 之外，避免混入冻结清单）：

| 文件 | 内容 |
| --- | --- |
| README.md | 总览、确认规则、已知边界 |
| samples_draft_MA.md / .json | 30 条，5 份 TFDA 仿單各 6 条 |
| samples_draft_PV.md / .json | 29 条，MedDRA 两份 10 条，GVP VI 4、GVP IX 3、FDA 申办方安全报告 3、E2A 3、E2F 3、TFDA 通報表指引 3 |
| samples_draft_CO.md / .json | 16 条，E8(R1) 5、E6(R3) 6、FDA 方案偏离草案 5 |
| tooling/draft_samples.py、specs_*.json | 起草工具与规格，便于按确认结果重算 |

每条草稿含 SPEC 第 5、6 节的全部字段：query、dept、language、slices、gold（source_hash、version_label、page、section、key_text、evidence_span 与偏移）。`review` 块留待确认与 LLM 复核后填写。

## 2. 对 SPEC 门槛的机械核对

| 门槛 | 要求 | 草稿 |
| --- | --- | --- |
| 样本总数 | 不少于 60，目标 72 | 75 |
| 每部门 | 不少于 15 | MA 30、PV 29、CO 16 |
| 每切片 | 不少于 8 | time_window 20、drug_name_zh 18、dose_unit 12、mixed_zh_en 55、negation 29、protocol_id 9 |
| gold 文档 zh-Hans | 不少于 8 | 10（MedDRA 两份） |
| 文档数与每部门文档数 | 不少于 10，每部门不少于 3 | 16；MA 5、PV 8、CO 3 |
| 每文档样本数 | 不超过 6 | 最多 6 |
| key_text 页内唯一、span 含 key_text、偏移与 span 一致、query 互不相同且不等于任何 key_text、mixed_zh_en 样本 language=mixed | PR-02/05/08/11 | 工具逐条检查通过 |

## 3. 起草口径（需决策人知悉）

- 繁体文档（仿單、TFDA 指引）的 query 用繁体书写；英文文档的 query 为中文加英文术语或编号，样本语言记为 mixed。简体 query 对繁体条款的匹配属于 DEC-001/DEC-005 要单独处理的问题，不混入本集。
- 说明书的 protocol_id 切片用許可證字號；指南用 ICH 编号、CFR 条款号或章节号。
- 胃所樂仿單避开粗体重复的抽取伪影区域；FDA 方案偏离草案页文本夹有行号，key_text 均落在单行之内，span 可能含行号数字，由决策人判断是否接受。
- 章节名由我按上下文填写，是标注内容的一部分。
- 起草者是 LLM，因此独立复核不能再由我承担；建议由 Codex 依 `review_prompt.md`（下一轮随 manifest 一起起草）执行并记录模型与版本。

## 4. 下一步

1. 决策人逐条确认或改写；改动条目由工具重算偏移并复核唯一性。
2. 起草 `review_prompt.md` 与 `manifest.json`，装配 `samples.jsonl`（含 review 块），`make canonicalize-probe`、`make validate-probe MODE=draft PAGES=...`。
3. LLM 独立复核，争议由决策人裁决并写 `resolution_note`；补 `SHA256SUMS` 与 `dataset_hash`，`status=frozen`。
4. 冻结后进入 DEC-001：实验清单（M1-02）、三候选适配器与对比（M1-04/05）。

## 5. 自审（基线 §9）

1. 需求：只起草，未替决策人签任何标注；未改规范。
2. 逻辑：唯一性、偏移、跨批 query 去重、每文档上限均由工具断言。
3. 安全：全部来自已签字公开文档；无 PII（入库时已扫描并复核）。
4. 契约：字段与 probe_sample.schema.json 一致（review 块除外，按流程后补）。
5. 测试：无代码变更；起草工具的检查等价于校验器 PR-02/05/08/11 的子集，正式校验仍以校验器为准。
6. 可观测：无。
7. 简洁性：一个脚本、三个规格文件。
8. 验证：见第 2 节。
9. Checklist：M1-01 仍为部分；进度不变。
