# 主评测集 main-v1 复核争议裁决表（复核人 reviewer-llm-02 = claude-opus-5）：第 6 轮

> 第 6 轮：上一轮决定已应用并重跑复核后，复核人对改动样本提出的新争议（上一轮 `保留` 且判定未变的 42 条不再列出）。
> 共 1 条争议。每条请在「决定」列填写：`接受`（我按建议修改样本并只对该样本重跑复核；建议不够机械时写 `接受：key_text=… | slices=a,b | query=… | topic=…`）或 `保留：<理由>`（写入 resolution_note，状态记为 disputed_resolved）。
> 同族规则（spec-v1.1 §5.1 / PR-15）：孪生的 gold、slices 与父样本完全相同；涉及 key_text、evidence_span 或 slices 的决定对父样本和孪生同时生效，query 的决定只影响被争议的那一条。无答案样本只有 query / topic / slices 可改。
> PDF 用友好名打开（`evals/main_set/pdf_by_key/<document_key>.pdf`，本机符号链接），页码为 PDF 物理页序号。
> 第 6 轮（收尾）：按决策人 2026-09-22 授权的收尾规则由实现方填写决定，不再重跑复核。

| 样本 | 批次 | 同族 | 文档 | PDF | 页 | 争议项 | query | slices | key_text / topic | 复核人理由 | 复核人建议 | 决定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ms-0391 | EN | 孪生于 ms-0390（父样本未被争议） | ich-e17-step4-2017 | `evals/main_set/pdf_by_key/ich-e17-step4-2017.pdf` | 28 | slices | Under ICH E17, when regional differences in medical practice lead to different concomitant drugs or doses being used, what must the trial protocol define in advance? | negation, mixed_zh_en | specify allowable and not allowable concomitant medications and doses | 切片标签疑缺 protocol_id。query 以指南编号定位文档（"Under ICH E17, ..."，父样本同样为"ICH E17 中，..."），召回依赖"ICH E17"这一指南编号的精确匹配，符合切片定义中"指南编号"一项；该编号并非仅作为答案出现。其余各项经核对无误：key_text "specify allowable and not allowable concomitant medications and doses" 在页文本中恰好出现一次且为逐字原文；evidence_span "The clinical trial protocol should specify allowable and not allowable concomitant medications and doses." 为完整条款并含 key_text，偏移 955–1060 与页文本实际位置及 105 字符长度一致；negation 由"not allowable"成立，mixed_zh_en 按孪生继承规则不重复质疑；英文 query 与 parent_query 问的是同一件事（方案须事先界定可用与不可用的合并用药及剂量），限定条件一致、表述自然；ICH E17 为多区域临床试验设计指南，dept=CO 相符。 | slices 增补 protocol_id，改为 ["negation", "protocol_id", "mixed_zh_en"]，并与父样本（中文）同步修改以保持孪生切片一致。 | 保留：按 2026-09-22 口径（ms-0380/0391/0482/0491/0493 同），query 中的指南名只限定来源文档，不是用于锁定条款的精确条号、节号或版本号，不计 protocol_id。 |
