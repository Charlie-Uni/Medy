# 主评测集 main-v1 样本草稿总览（待 annotator-01 逐条确认）

- 起草日期 2026-09-21；起草者 `drafter-llm-03`（claude-sonnet-5，Claude Code CLI、工具关闭；提示见 [drafting_prompt.md](drafting_prompt.md)、[drafting_prompt_noanswer.md](drafting_prompt_noanswer.md)；每次调用的回复与元数据在 `raw/`、`raw_long/`、`raw_noanswer/`、`raw_backfill/`，含页文本的输入包 `inputs/` 不入 Git）。全部候选均经工具在 norm-v1 页文本中重新定位、重算偏移、核对页内唯一；机械校验结论与告警见 `candidates_*.json` 的 `_draft` 字段。起草总费用 61.07 美元（决策人批准区间 40–80）。
- 五张标注表（合计 524 条新样本；探针 v2 的 107 条原样并入、不在表内）：

| 批次 | 文件 | 条数 | 说明 |
| --- | --- | ---: | --- |
| MA | [samples_draft_MA.md](samples_draft_MA.md) | 83 | 仿單，繁體問題 |
| PV | [samples_draft_PV.md](samples_draft_PV.md) | 120 | GVP / ICH E2 / FDA 安全报告 / MedDRA / TFDA 通報指引；含 10 条合成冲突样本、9 条长条款 |
| CO | [samples_draft_CO.md](samples_draft_CO.md) | 84 | ICH E 系列 / FDA 临床运营指南；含 16 条合成冲突样本、10 条长条款 |
| EN | [samples_draft_EN.md](samples_draft_EN.md) | 174 | 英文文档样本的英文问法孪生（gold、切片继承自父样本，只需判断英文问法） |
| NA | [samples_draft_NA.md](samples_draft_NA.md) | 63 | 无答案样本（问题在文档范围内、文档不回答；工具已核查 absence_terms 在该文档全部页文本中缺席） |

- 并入探针后的合计：样本 631（有答案 568、无答案 63、冲突 52、孪生 206）；部门 MA 137 / PV 282 / CO 212；gold 文档语言 zh-Hant 143 / zh-Hans 30 / en 458；九个切片均 ≥ 20（long_context 35、version_conflict 52、no_answer 63）；每文档非派生样本 ≤ 8。spec-m1 全部下限已满足（[SPEC.md](../../SPEC.md) §2/§8）。

## 确认规则

1. 有答案样本（MA/PV/CO）每条判断五件事：问题自然且只有这一句能回答；key_text 最短且页内唯一（工具已核对唯一）；span 是完整条款；切片标签；部门归属。「工具提示」列是机械告警（如 `negation: no negation word in span`），请一并裁定。
2. 孪生（EN）只判断英文问法是否与父样本问同一件事、限定条件一致、英文自然。
3. 无答案（NA）判断四件事：问题在范围内且自然；文档确实没有回答（`nearest_clause` 是起草者给出的最接近条款，`absence_terms(n)` 括号内为语料中含该词的其他文档数）；切片；部门。
4. 写法：在「结论」列填 `OK`；删除写 `DROP`；改写可直接改 query / key_text / 切片 单元格，或在「结论」列写指令 `query=…; key_text=…; span=…; slices=a,b; query_en=…; topic=…`。改动的条目由 `tools/apply_sheet_edits.py` 重新定位并重算偏移，父样本的 gold 与切片改动自动联动其孪生。
5. 你确认后的样本以 annotator-01 记为人工标注；随后由 claude-opus-5 按 [review_prompt.md](review_prompt.md) 独立复核（批次 MA/PV/CO/EN/NA），争议由你裁决。**第二人工复核人暂无**：冻结版本号为 `main-v1-provisional`，报告标注"第二人工复核未完成"。

## 已知边界

- 合成冲突样本（`version_conflict`）来自 5 份新文档（ICH E7 / E12A / E15、GVP Annex I、GVP P.I）：同一 PDF 以旧版、现行版两个 document_key 入库，旧版已归档；正文相同，检验的是版本状态与时效过滤，不检验内容差异（记录 50 D50-4）。
- 长条款（`long_context`）按机械规则标注：span 超过 1,500 字符；Markdown 表中 span 有截断，完整条款见同名 .json 与页文本。
- FDA 方案偏离草案页文本夹有行号，起草的两条均无法逐字锚定而被拒绝；GVP Module V 一条备选不足。合计拒绝 27 条（有答案 17、长条款 10）与 50 条无答案候选（absence_terms 在文档中出现），均未进入表内。
- 一条 GVP Module VI Addendum I 的问题含机构邮箱（PR-07 不允许 query 字段例外），已剔除。

## 2026-09-21 外部审校写回（annotator-01 提交的 ChatGPT 审校）

- 输入：[external_review/](external_review/) 下 `MA_review_audit_2026-09-21.md`（83 条）、`PV_review_audit_2026-09-21.md`（120 条）、`EN_review_audit_2026-09-21.md`（174 条）；CO 批次与 NA 批次没有收到审校文件。
- 写回工具：`tools/apply_external_review.py`——每条建议值都在 norm-v1 页文本中重新定位（精确或空白/引号容差）、重算偏移、核对页内唯一，`mixed_zh_en` / `long_context` 按机械规则重算，父样本的 gold 与切片自动同步孪生。审校把整段条款当作 "key" 的 51 条（> 200 字符）按规范处理为 evidence_span，key_text 保留原最小锚点（46 条）或从条款首句派生（5 条，含 3 条替换掉"以下各点应考虑："之类的引导句）。
- 结果（[apply_report_2026-09-21.json](external_review/apply_report_2026-09-21.json)）：应用 224 条（query 116、key_text 74、evidence_span 57、slices 92、section 59），删除 4 条（MA ms-0027/0028/0029：Glimaryl 仿單文本层乱码；PV ms-0195：gold 跨页）及其孪生 ms-0196；1 条英文孪生（ms-0251）因审校英文 301 字符由实现方缩短为 284 字符；EN 批次 76 条 `PENDING_PARENT` 与 4 条 `DROP`（父样本 ms-0303/0324/0414/0428 来自未提供的 CO 审校）只记录建议、未应用。
- 写回后的机械检查（`tools/check_drafts.py`）0 错误；合计 626 条（新 519：MA 80、PV 119、CO 84、EN 173、NA 63），全部下限仍满足。ms-0135/0136 的完整条款含 EMA 机构信箱，已按记录 21 的口径登记逐命中例外 [pii_exceptions_new.json](pii_exceptions_new.json)，待 annotator-01 确认。
- 五张表已按写回后的 JSON 重新生成，「结论」列预填了当前状态（`OK (external review)` / `edited (external review)` / `pending: …`），annotator-01 覆盖即可；CO 表仍是原稿，需要 CO 审校或直接在表上确认。
- 外部审校指出的文档级问题，已核实并处理：Glimaryl 仿單（b1756268da31）第 1 页文本层 0 个汉字、152 个乱码字符，确为字体编码乱码，不能作 gold（3 条样本已删，文档保留在语料、建议 M2 复核抽取或剔除）；`fda-investigator-safety-reporting-2021` 的 PDF 封面实为 December 2025 版而 `version_label` 误记 September 2021——已按 M1-11 发布流程以同一源对象升版为 `fda-investigator-safety-reporting-2025`（`Final guidance, December 2025 (FDA media 152530)`，旧记录归档），corpus.json 与该文档的 10 条样本（5 父 + 5 孪生）的 `version_label` 已同步；GVP Annex I Rev 4 的 PDF 第 1–3 页含 superseded 标注（EMA 已发布后续修订），本集仅作合成冲突 fixture 使用，不代表现行定义。

## 2026-09-22 第二轮写回（NA、CO 审校与 EN 待定项）与确认状态

- 输入：`external_review/NA_review_audit_2026-09-21.md`（63 条，表格式）、`external_review/CO_review_audit_2026-09-21.md`（84 条，重生成版，无逐字段 diff）。决策人回复"可以了"。
- NA 与 CO 的审校只描述了改法、没有给出新文本的条目，由实现方按审校结论写出新值（[implementer_edits_2026-09-22.json](external_review/implementer_edits_2026-09-22.json)：NA 13 条收窄后的问题与 topic、CO 7 条 key/query 修订；CO 父样本的中文改写取自 EN 审校的成对建议），再经 `tools/apply_external_review_2.py` 重新锚定。
- 结果（[apply_report_2026-09-22.json](external_review/apply_report_2026-09-22.json)）：应用 97 条（NA 28、CO 22、EN 47，其中 26 条为 EN 审校成对提出的父样本中文改写）；删除 6 条：NA ms-0487（文档可回答）、CO ms-0300（审校建议 CO→PV，但 PR-06 要求样本部门等于文档部门，故删除）、ms-0303/0324（gold 跨页）、ms-0414/0428（重复）及其孪生。机械检查 0 错误。
- 现状：**615 条**（新 508：MA 80、PV 119、CO 79、EN 168、NA 62；探针 107），有答案 553、无答案 62、冲突 52、long_context 23；部门 MA 134 / PV 279 / CO 202；语言 zh-Hant 140 / zh-Hans 30 / en 445；全部下限满足。五张表全部预填了决定，不再有待定项。
- **确认状态**：决策人（annotator-01）于 2026-09-22 以"可以了"确认以上写回结果作为人工标注（含实现方按审校结论写出的 NA/CO 文本与成对英文）；`drafted_by` 仍记录 LLM 起草者，人工确认日期 2026-09-22。第二人工复核人仍无，版本保持 `main-v1-provisional`。

## 2026-09-22 LLM 复核进行中的两处修正

- 复核人（claude-opus-5）在 PV/EN 首批就指出：复核输入缺少样本的 `conflict` 说明块（打包脚本漏带，提示里却说会附上）。已修正 `pack_review.py` 与 PR-09 的输入重建（`conflict` 与非空 `notes` 一并进入复核记录），PV/CO/EN 三批作废重跑（作废的运行记录在 `review/archive_2026-09-22_before_conflict_field/`）。
- 复核人同时指出 GVP Annex I Rev 4 的页眉写明 "Superseded version (not valid anymore)"。EMA 已发布 Rev 5（2024-07-26），已下载、过门禁并以发布流程作为 Rev 4 的后继版入库（候选 cand-0102，v1.1）：family 现为 合成旧版 → Rev 4 → Rev 5，是一对真实修订。Annex I 的 5 条样本与孪生已重新锚定到 Rev 5（`conflict.synthetic=false`）：3 条原文不变（ms-0086/0088/0090），ms-0092 的 key 因 Rev 5 另页有近似句而加长，ms-0084 因 Rev 5 删除了 Dir 2001/20/EC 的非干预性试验定义、改写为 Reg (EU) 536/2014 的 non-interventional study 定义；无答案 ms-0462 的 scope 迁到 Rev 5 并复查缺席词。这 11 条在各批次复核完成后用 `--only` 单独重跑。

## 2026-09-22 LLM 独立复核结果（reviewer-llm-02 = claude-opus-5）

| 批次 | 样本 | 争议 | 争议率 | 调用次数 | 费用 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MA | 80 | 3 | 3.8% | 16 | $4.43 |
| PV | 119 | 21 | 17.6% | 30 | $8.87 |
| CO | 79 | 20 | 25.3% | 16 | $5.57 |
| EN | 168 | 19 | 11.3% | 40 | $11.94 |
| NA | 61 | 8 | 13.1% | 35 | $12.25 |
| 合计 | 507 | 71 | 14.0% | 137 | **$43.06** |

- 复核中途按复核人的意见做了三处工具侧修正并定向重跑（`--only`）：(1) 复核输入补齐 `conflict` 块与 `notes`（PV/CO/EN 作废重跑，约 $1 沉没）；(2) 第一轮外部审校按"报告长度"重建的 25 条 PV span 边界错位——按复核人争议恢复为起草者原始完整条款（`tools/fix_span_boundaries.py`，孪生同步，PV 25 + EN 23 条重跑）；(3) 无答案样本的复核输入从起草时的选页扩为全文（≤ 10 万字符）或按问题相关度选页（28 条重跑，`tools/na_pages_relevant.py`）。GVP Annex I 换为 Rev 5 后相关 11 条也已重跑。
- 复核后删除 1 条：NA ms-0509（Glimaryl 文本层乱码，复核人无法核实缺席；`review/dropped_after_review.json`，manifest 将登记）。现为 **614 条**（新 507 + 探针 107）。
- 争议裁决表：[review/disputes_sheet.md](review/disputes_sheet.md)（71 条），annotator-01 在「决定」列写 `接受`（机械建议：补/删标签、改 key_text）或 `接受：key_text=… | slices=… | query=… | topic=… | span=…`，或 `保留：<理由>`；`tools/apply_resolutions.py` 应用并只对改动样本重跑复核。
- 复核运行记录：`review/run_{MA,PV,CO,EN,NA}.json`、`verdicts_*.jsonl`（含页文本的输入包与分块输入不入 Git）。


## 2026-09-22 争议裁决写回（annotator-01 决定列 + 审计记录）

- 决策人交回填好「决定」列的裁决表（`review/disputes_sheet.md`，只有决定列与原表不同，逐格核对）与统一口径记录（`external_review/main_v1_disputes_readjudication_audit_2026-09-22.md`，ChatGPT 辅助、由 annotator-01 提交）：接受 62、保留 9。
- 62 条接受多为文字描述而非工具语法，实现方逐条翻译成页内原文的精确改动并留档 `review/resolutions_explicit_2026-09-22.json`（每条绑定决定文字的 SHA-256，`apply_resolutions.py --explicit` 只在哈希一致时使用）。9 条决定文字给出的 key_text 超过 200 字符上限（ms-0122/0123、0197、0213、0217、0229、0268、0298、0326、0432/0433），取满足决定意图的最长 ≤200 连续原文并在文件中注明（`implementer_note`），标注人可否决。
- 决定引出的两条主集口径（SPEC §3 已登记）：测量值不计 `dose_unit`；仅以指南名限定来源不计 `protocol_id`。为保持全集一致，对同构的未争议样本做了一次记录在案的清扫（`review/consistency_sweep_2026-09-22.json`，`--sweep`）：去掉 13 条（含孪生 20 条）只以指南名限定的 protocol_id、去掉 ms-0364/0365（mmHg）的 dose_unit、按复核人同一争议中的父问改写更新 ms-0416/0434 的 query 以与已改写的孪生一致。并入的探针样本不动（PR-16 逐字节），其 24 条指南名式 protocol_id 保留探针口径。
- 工具增补：`apply_resolutions.py` 支持 `section=`、`span=`、`absence_terms=`（无答案样本改题必须给出并重查缺席）、父样本 query 改动联动孪生的 `parent_query` 并重跑孪生、`review/changed_<date>.json` 输出。
- 结果：111 条样本改动（含孪生与 parent_query 联动），`check_drafts.py` 0 错误、下限全部满足；`resolutions.json` 9 条 `disputed_resolved`；改动样本按批次 `--only` 重跑 claude-opus-5 复核（结果见记录 50 §13）。
- 重跑结果（2026-09-22 13:17）：111 条重跑费用 $9.16（累计 $52.22）；24 条新争议 → [review/disputes_sheet_round2.md](review/disputes_sheet_round2.md)（实现方预填 `建议：`，接受 15 / 保留 9，其中 6 条是指南名式 protocol_id 的口径冲突、2 条受 200 字符上限约束）。第一轮已决表仍为 `review/disputes_sheet.md`。第二轮应用命令：`apply_resolutions.py --sheet review/disputes_sheet_round2.md --explicit review/resolutions_explicit_round2.json --sweep review/consistency_sweep_round2.json`。
- 第二轮裁决已应用（2026-09-22）：接受 16 / 保留 8（决策人对 ms-0197 自选 199 字符锚点、ms-0372/0373 扩 span 后补 negation），21 条改动、0 错误，`resolutions.json` 17 条；已决表即 `review/disputes_sheet_round2.md`，改动清单 `review/changed_2026-09-22_round2.json`（第一轮为 `_round1`）。
- 第三轮（2026-09-22）：ms-0228 补 negation 与父样本同步，两条重跑 agree；争议收敛，17 条 `disputed_resolved`、其余 agree，复核累计 $53.52。
- 冻结前 PR-09 发现：单独重跑改动样本会让原块邻居绑在含旧输入的提示上（318 条）。决策人选方案一：318 条以块大小 1 重跑（2026-09-22 下午，五批并行）；`tools/review_binding_check.py` 可在冻结前复查，`apply_resolutions.py` 之后的重跑固定块大小 1。
- 318 条块大小 1 重跑完成（$34.75，累计 $88.27），绑定检查归零；57 条新争议 → [review/disputes_sheet_round4.md](review/disputes_sheet_round4.md)（预填：接受 30 / 保留 27），待 annotator-01 确认；`carry_forward_resolutions.py` 已把 6 条同一异议的保留决定续用、4 条转 agree 的撤销。
- 第四轮已按决策人"按建议来"应用（接受 30 / 保留 27），47 条改动，块大小 1 重跑中；已决表即 `review/disputes_sheet_round4.md`，改动清单 `review/changed_2026-09-22_round4.json`。
- 第四轮重跑完成（累计 $93.22），9 条新争议 → [review/disputes_sheet_round5.md](review/disputes_sheet_round5.md)（预填接受 7 / 保留 2），待确认。
- 第五/六轮完成（2026-09-22 17:25）：争议裁决终态 agree 464 / disputed_resolved 43 / open 0，绑定检查 0，复核累计 $94.85；进入装配、冻结 `main-v1-provisional` 与端到端运行。
