# 探针集 v1 样本草稿总览（待决策人确认）

- 合计 75 条，文档 16 份，每份不超过 6 条。
- 部门：MA 30、PV 29、CO 16（要求各不少于 15）。
- 切片（2026-09-19 MA 修订后重算）：time_window 21, drug_name_zh 18, dose_unit 19, mixed_zh_en 52, negation 32, protocol_id 9（要求各不少于 8）。
- gold 文档语言：zh-Hant 33, zh-Hans 10, en 32（要求 zh-Hans 不少于 8）。
- 批次文件：[MA](samples_draft_MA.md) 30 条、[PV](samples_draft_PV.md) 29 条、[CO](samples_draft_CO.md) 16 条；机器可读版为同名 .json。
- 当前入口：[人工确认依据](review/owner_confirmations_2026-09-19.md)。交接已确认 MA 处理方案与 P1/P2/P3；PV/CO 原始表分别 29/16 条 OK，改动已重建；新口径 high 独立复核已完成：28 agree / 47 dispute，当前处理新争议裁决与重审。Markdown 长 span 有截断，完整条款见 JSON 与页文本。
- `v1/review_prompt.md` 已有草稿；`manifest.json`、`samples.jsonl`、`SHA256SUMS` 尚未生成，75 条草稿均未填写正式 `review` 块。当前仍未冻结。

## 确认规则

1. 每条判断五件事：问题自然且只有该句能回答；key_text 最短且页内唯一（工具已核对唯一）；span 是完整条款；切片标签正确；部门归属正确。
2. 在「结论」列填 OK，或直接改写 query、key_text、span、slices；改过的条目我重算偏移并复核唯一性。
3. 你确认后的样本以 annotator-01 记为人工标注；LLM 独立复核由 Codex 按 review_prompt.md 执行并记录模型与版本。

## 已知边界

- 仿單与 TFDA 指引为繁体，query 也用繁体书写；简体 query 对繁体条款的词法匹配是 DEC-001/DEC-005 要单独处理的问题，不混进本集。
- 英文文档的 query 为中文加英文术语，样本语言记为 mixed；这类样本考验的是中英混排检索。
- 胃所樂仿單有粗体重复的抽取伪影，已避开受影响的标题区域；FDA 方案偏离草案的页文本夹有行号，key_text 均落在单行之内。
- 章节名是我按上下文填写的，属于标注内容，请一并核对。

## 确认轮次记录

- 2026-09-19：决策人改写 MA 表（23 行有改动，7 行 OK）。原始改动备份为 `samples_draft_MA.owner-edit-2026-09-19.md`；按改动重算后的 MA 草稿已覆盖 `samples_draft_MA.md/.json`，逐行映射与待确认项见 `MA_reconcile_2026-09-19.md`。PV、CO 表此轮无改动。
- 2026-09-19：MA 表 30 条经决策人确认（含对照表中的映射）。新增 `tooling/review_pack.py`（生成 `review/input_<批次>.jsonl` 给 LLM 第二复核人，含 gold 页的 norm-v1 页文本，已 gitignore）、`tooling/assemble.py`（按 `review/verdicts_<批次>.jsonl` 与 `review/resolutions.json` 装配 `v1/samples.jsonl` 与 `v1/manifest.json`，只写 draft 目录）；复核提示已写入 `v1/review_prompt.md`。装配工具在临时目录用全 agree 假判定干跑通过校验器 draft 模式，未向 v1 写入 samples/manifest。

- 本轮正式复核：[完整结果与争议](review/formal_review_status.md)、[具体修订提案](review/proposed_changes.md)、[复核绑定审计](review/formal_review_audit.json)。旧口径 14 条已归档排除；新结果不代表检索质量指标，未冻结。
