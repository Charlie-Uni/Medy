# 主评测集 main-v1 复核争议裁决表（复核人 reviewer-llm-02 = claude-opus-5）：第 3 轮

> 第 3 轮：上一轮决定已应用并重跑复核后，复核人对改动样本提出的新争议（上一轮 `保留` 且判定未变的 17 条不再列出）。
> 共 1 条争议。每条请在「决定」列填写：`接受`（我按建议修改样本并只对该样本重跑复核；建议不够机械时写 `接受：key_text=… | slices=a,b | query=… | topic=…`）或 `保留：<理由>`（写入 resolution_note，状态记为 disputed_resolved）。
> 同族规则（spec-v1.1 §5.1 / PR-15）：孪生的 gold、slices 与父样本完全相同；涉及 key_text、evidence_span 或 slices 的决定对父样本和孪生同时生效，query 的决定只影响被争议的那一条。无答案样本只有 query / topic / slices 可改。
> PDF 用友好名打开（`evals/main_set/pdf_by_key/<document_key>.pdf`，本机符号链接），页码为 PDF 物理页序号。
> 第 3 轮仅 1 条。决定由实现方按决策人 2026-09-22 第二轮审计记录的口径 3（negation 按完整 evidence_span 判断，明确的不允许/不得/例外限制可命中）代填：span 含 "legislation do not permit this"，与父样本 ms-0227 同步补 negation；决策人可否决（撤销后两条重跑）。

| 样本 | 批次 | 同族 | 文档 | PDF | 页 | 争议项 | query | slices | key_text / topic | 复核人理由 | 复核人建议 | 决定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ms-0228 | EN | 孪生于 ms-0227（父样本未被争议） | ema-gvp-pp-iv | `evals/main_set/pdf_by_key/ema-gvp-pp-iv.pdf` | 9 | slices | In a paediatric ICSR, what information should be recorded instead if the exact age or date of birth cannot be obtained? | mixed_zh_en | affiliation to one of the paediatric age subsets if it is not possible to obtain the exact age or date of birth | 切片缺 negation。按完整 evidence_span 判定，条款含明确否定/限制表达：“affiliation to one of the paediatric age subsets if it is not possible to obtain the exact age or date of birth or if personal data protection legislation do not permit this”，其中“it is not possible to obtain”“legislation do not permit this”属否定/限制表达，且 key_text 命中保留了该否定语义（“if it is not possible to obtain the exact age or date of birth”），query 亦以“cannot be obtained”为核心条件；与本集对 negation 的其他判定（如“should not be submitted”“unless exempted”“not responsible or ethical”）相比标签口径不一致。其余四项无问题：key_text 在页文本中仅出现一次且为逐字原文，span 为完整两项择一条款且偏移与文本一致，PV 归属正确。 | 在 slices 中补加 negation，保持为 ["negation", "mixed_zh_en"]；若决策人认为“无法获得/法规不允许”属事实性条件而非禁用限制，则应在 spec 判定口径中明确排除此类表达，以免与已标注样本冲突。 | 接受：slices=negation,mixed_zh_en |
