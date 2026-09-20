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
