# 实现记录 46：annotator-01 预审稿（2026-09-20，AI 辅助）与仓库证据的对账

日期：2026-09-20。决策人提交《文档授权证据预审与探针 v2 争议裁决记录》（annotator-01，ChatGPT 辅助）。该稿只见到 12 份上传 PDF 与争议表，未见 corpus.json、候选清单 v0.6、ADR-0003 与已冻结的 v2 samples，因此其"未建立证据""不能自动关闭"多数是缺少上下文所致。本记录逐项对账，只陈述仓库中已有的证据与仍然开放的点，不改动任何已冻结数据。

## 1. 结论

- **21 条争议：v2 冻结版本已经包含预审稿 B 节的全部决定**（13 条接受、4 条分项修正、4 条保留），三处仅措辞不同（见 §3），一处规则问题由 SPEC 原文关闭（pc-0036）；预审稿要求的三项核对全部通过（§4）。**不需要重新冻结 v2**，已跑的 DEC-001/002 与端到端结果继续有效。
- **12 份文档的授权证据：预审稿 A 节要求的每一项在仓库中均有记录**（§2 表），并有决策人 2026-09-12 / 09-17 的签字批复；两点作为"已知依赖"保留（ICH 历史版本依赖站点级 Legal Mentions；用途分项审批未逐条列出），不改变 `eligible` 状态。

## 2. 授权证据对账（预审稿 A 节 ↔ 仓库记录）

| 文档 | 预审稿判断 | 仓库证据（候选清单 v0.6 / corpus.json / ADR-0003） | 结论 |
| --- | --- | --- | --- |
| 三份 TFDA 仿單（痛風停、心壓暢、胃所樂） | "药品许可证不是著作权许可，未建立再利用授权" | ADR-0003 决策记录 2026-09-10 第 1 项与 2026-09-12 第 2 项：以 data.gov.tw 資料集 9117 的 OGDL-1.0 为特定授权依据，条件 (1) 仿單 PDF 链接逐字出现在同日快照（export/39，2026-09-17）、(2) 快照 SHA-256 与日期、(3) PDF 无附加限制（图像层目视）、(4) 署名与不主张商标权——cand-0034/0037/0038 的 `reviewer_note` 记录 (1)(2)(3) 已机械证明；`landing_url`（mcp.fda.gov.tw/im_detail_1/<許可證字號>）、`pdf_url`、`retrieved_at=2026-09-17`、现行性（export/36 快照：註銷狀態空、有效日期）均在；决策人 2026-09-17 批复"许可通过" | 证据齐备；预审稿的顾虑正是 ADR-0003 第 1/2 项决策处理过的问题 |
| MedDRA 术语选择 4.26（简体） | 文内 ICH 许可，需履行条件 | cand-0026：文内"ICH 免责申明和版权公告"原文引用（第 1 页）、meddra.org 列表 API 证据、2026-09-12 决策：许可仅覆盖指南文档，不覆盖术语库 | 一致 |
| GVP Module VI / IX | 文内复制许可，需履行条件 | cand-0009/0010：EMA Legal Notice 原文 + PDF 封面版权声明；署名文本 "Source: European Medicines Agency and Heads of Medicines Agencies (GVP)"；第三方内容核查记录 | 一致 |
| FDA Sponsor Safety Reporting 2025 | 发布方政策已核实，来源链待补 | cand-0011：`landing_url`（fda.gov 指南页）、`pdf_url`（media/150356/download）、Website Policies 原文、`attribution_required=false`；未标为 CC0 | 来源链已有 |
| TFDA 通報表填寫指引 第四版 | 网站政策已找到，本件适用性未闭合 | cand-0014：`landing_url`（siteContent.aspx?sid=4240）、`pdf_url`、網站資料開放宣告与著作權聲明两条原文、"文件无「另需同意」标记"核查、决策人 2026-09-17 批复 | 适用性已核 |
| ICH E6(R3)、E8(R1) | 文内 ICH 许可 | cand-0017/0028：文内公告 + Legal Mentions；决策 2026-09-12 | 一致 |
| ICH E2A（1994）、E2F（2010） | 版权许可范围待核实 | cand-0012/0013：1994/2010 PDF 无文内公告，依据 ich.org Legal Mentions（站点级，覆盖 database.ich.org 托管材料），`third_party_note` 已写明此依赖；决策人 2026-09-17 批复"与已签字的 E8(R1) 同一依据" | **已知依赖**：如需更强证据，可向 ICH 秘书处书面确认历史版本适用；不影响当前 `eligible` |

预审稿要求的字段落点：`original_landing_url` = 候选 `landing_url`；`original_download_url` = `pdf_url`（与 corpus `source_url` 一致）；下载时间 = `retrieved_at` 与记录 15 的重下载核对（2026-09-17，SHA-256 10/10 一致）；版本/采纳日期 = `version_label`；许可适用证据 = `license_evidence[]`（url/locator/quote 一一对应，ADR-0003 决策 7）。**用途分项**：`permitted_scope` 对 12 份均含"保存、索引、引用、展示"，EMA/ICH/FDA/OGDL 另含复制与分发；本项目已实际发生的用途为内部检索、向 LLM 复核人（claude-opus-5，Claude Code CLI）提供页文本片段、在仓库中公开 gold 的 `key_text`/`evidence_span` 节选——三者均在上述范围内；公开原始 PDF 未发生也未计划。建议候选 schema 增加 `approved_uses[]` 逐项显式登记（M1-20 起执行）。

## 3. 21 条争议对账（预审稿 B–E 节 ↔ v2 冻结状态）

| 样本 | 预审稿决定 | v2 冻结状态 | 差异 |
| --- | --- | --- | --- |
| pc-0008 / 0012 / 0022 | 删除 negation | 已删除 | 无 |
| pc-0023 | 保留 negation，key 采用 K8（含 glucagon 句） | negation 保留；key 已扩为"初步的急救方法…noradrenaline"（含否定条件句，101 字）；span 189 字含 glucagon 句 | **措辞差异**：K8 再并入 β-blocker/glucagon 句（约 170 字）。SPEC §6 的最小性（P1：保留对象与约束）当前 key 已满足；K8 属于另一分支条款。默认保持现状；如决策人要 K8，属 key 扩展，需重跑该样本复核 |
| pc-0027 | 收缩 span、保留 negation、Q27/S27/K27 | 完全一致（Q、S、K 逐字相同，标点为 norm-v1 形式） | 无 |
| pc-0033 | Q33（"能否不走术语变更流程，直接用内部替代办法…"） | 决策人 2026-09-20 的 Q1（"团队可以自行制定临时处理规则吗"），已复核 agreed | **等价措辞**；默认保持 |
| pc-0036 | 删除 dose_unit；time_window 待 SPEC | 两者均已删除，slices = [mixed_zh_en, negation] | SPEC §7 原文：time_window 为"14 天内""给药后 24 小时""±3 天"类有边界时间窗；P2 确认"给药频次归 dose_unit"。监测频次"每月一次/每 6 个月一次"既非有边界时间窗，也非给药频次 → 两标签均不适用。**按 SPEC 关闭**，与冻结状态一致 |
| pc-0044/0079、0045/0080、0050/0085、0067/0099、0069/0101 | K1、K2、K3、K5、K6，父子同步 | key 逐字等于 K1/K2/K3/K5/K6；父子 gold 与 slices 逐字段相同（本轮机械核对 9 对全部一致） | 无 |
| pc-0045 | span 必须含 "Signal confirmation by the PRAC Rapporteur…" 先行定义 | span 以该定义开头，含 EPITT（376 字） | 无 |
| pc-0047 | Q47 | 决策人 Q2（"能否在流程记录中把该信号标记为'完整评估已完成'"），已复核 agreed | **等价措辞**；默认保持 |
| pc-0058 | K4 | 逐字相同 | 无 |
| pc-0088 / 0089 / 0090 | 保留 negation | 已保留（disputed_resolved） | 无 |
| pc-0092 / 0060 | Q92 + K7，父版本须为双要点问题 | pc-0060 query 为双要点版本，K7 已应用于父子 | 无 |
| pc-0101 | K6 完整主语版本 | 逐字相同 | 无 |

## 4. 预审稿要求的三项核对

1. **pc-0088 的 key 是否截断**：冻结 key 长 152 字，结尾为 "as soon as possible but no later than 7 calendar days"；争议表中的 "7 c" 是表格生成时的显示截断，不是数据损坏。pc-0053 同值。
2. **pc-0045 的 span 是否含先行定义**：含（§3）。
3. **pc-0092 的父版本**：pc-0060 当前 query 为"ICH E8(R1) 对研究程序和评估的科学必要性及受试者负担有什么要求？"，K7 已同步；复核状态 agreed。

## 5. 需要决策人确认的三处（默认保持现状，不回复即视为保持）

pc-0023 是否改用 K8；pc-0033 是否改用 Q33；pc-0047 是否改用 Q47。任一改动都会产生 v2.1（新的 dataset_hash），需对改动样本重跑 LLM 复核并重跑向量/端到端运行；三处都不影响门禁结论。

## 6. 对 M1-20 的直接影响

- 预审稿要求的字段（`original_landing_url`、`original_download_url`、下载时间、版本/采纳日期、辖区生效日期、许可证据、`approved_uses[]`）在候选清单 schema 中除 `approved_uses` 与辖区生效日期外均已存在；M1-20 候选清单 v0.7 起补这两项。
- 主评测集需要扩语料：PR-04 上限（每文档 6 条非派生样本）下 16 份文档最多 96 条非派生样本；≥300 条需要约 50 份文档，或由主评测集规范另定上限。语言分布现状：en 9、zh-Hant 5、zh-Hans 2；zh-Hans 的开放许可来源稀缺（NMPA/CDE 页面"版权所有"落入 needs_review），是扩语料的主要约束。
