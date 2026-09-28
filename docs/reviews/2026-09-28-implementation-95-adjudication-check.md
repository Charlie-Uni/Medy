# 实现记录 95：2026-09-28 六项人工裁决的回填核对

日期：2026-09-28。范围：核对决策人对六项待人工事项（候选清单 v1.2 签字、4 条 needs_review、PV 缺口、探针 v2 争议裁决表、主集第二次复核清单、安全集 D2 六行）的回填结果，以及由此产生的候选清单 v1.3 / v1.4 与 ADR-0003 决策记录。未摄取语料、未改冻结集、未提交 Git。

## 1. 核对结果

| # | 事项 | 回填状态 | 独立核对 |
| --- | --- | --- | --- |
| 1 | v1.2 新增 230 条签字 | [v1.3](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.3.json)：227 `eligible`、2 `needs_review`、1 `rejected`；v1.2 JSON 保留签字前状态，签字表只追加决定索引 | Schema 校验 0 错误；编号连续；前 332 条中 228 条只改 `reviewer_decision/reviewer_note`，cand-0114、cand-0316 另有说明字段修正（见 2）；签字后 `eligible` 合计 309（MA 125 / PV 103 / CO 81） |
| 2 | 4 条 needs_review | cand-0114 `rejected`；cand-0293、cand-0298 `needs_review`；cand-0316 `eligible` | 本机复核原件：cand-0114 第 14 页文本含 "held jointly by ISO and Health Level Seven International. ALL RIGHTS RESERVED"；第 2 页文档历史表把 July 2025 v5.03 列为 "Step 4 document"，v1.3 把版本栏从 "Step 3" 改为 "v5.03（文档历史列为 Step 4；文件名含 Step3）" 正确。cand-0293 第 26 页、cand-0298 第 2 页 Quartz 渲染均见 "© Johnson & Johnson Taiwan Ltd. 2021"（cand-0298 为 CCDS 5 October 2020_v2102，製造廠 Cilag AG，藥商 嬌生）。cand-0316 第 2 页渲染：厂商地址后为印刷序号 "40419010 ②"，无版权或保密声明，文本层的 © 是字形误抽 |
| 3 | PV 缺口 18 份 | ADR-0003 新增 2026-09-28 决策记录：白名单优先，MHRA/TGA 须另行决定；[v1.4](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.4.md) 新增 cand-0333～0347 共 15 条 PV 候选（EMA 10、FDA 5，cand-0347 为 FDA 草案），`reviewer_decision` 全部为空 | Schema 0 错误；前 332 条与 v1.3 逐字相同；15 份本地副本存在且 SHA-256 与清单一致；许可依据为 EMA Legal notice / FDA Website Policies（2026-09-28 复核）。**新增 15 条尚需签字** |
| 4 | 探针 v2 争议裁决表 | 21/21 填写：接受 13、保留 8（均注明理由） | 与 [2026-09-20 裁决记录](../../evals/probe/precise_clause/drafts/v2/review/owner_adjudication_2026-09-20.md) 逐条一致（保留的 8 条对应该记录的「保留 / 修正后执行」）；表头去掉了文档与 PDF 列，21 行列数一致；表头注明只是补齐历史索引，不重开冻结的探针 v2 |
| 5 | 主集第二次复核清单 | 32/32 填写，并新增 §三「裁决口径与落地条件」 | 口径收窄为「问题明确点名产品或来源文件时才须引用该文档」，14 行中 6 行适用、8 行不适用；rp-0121/0200/0238 答案横跨 4/4/2 块，要求升版为共同必需证据块组而不是把相邻块加进「任一命中」；「标注改」不直接改主集 gold，须分别升版。这些是后续工作项，本轮未执行 |
| 6 | 安全集 D2 六行 | ss-0132/0133/0136/0137/0138/0139 填 `OK`，附回填说明 | 与记录 84 的建议一致；ss-0131/0134/0135/0140 仍为空，属 annotator-01 的 164 条抽检范围，不在本次六行内 |

## 2. 本轮修正

- `tests/unit/evals/test_candidate_lists.py`：跨版本编号稳定性原来以标题为锚，cand-0114 的标题订正使其误报；改为以 `pdf_url`（无 PDF 时 `landing_url`）为锚，即同一编号必须指向同一文档，标题允许订正。
- `make check`：ruff、mypy、pytest 1024 passed / 297 skipped、Schema 无漂移、`git diff --check` 通过。297 项跳过全部是集成测试因本机 PostgreSQL 未启动（`make up` 后可跑），不是新增跳过。

## 3. 数字口径

- 签字后 `eligible` 309 = v1.1 已签 82 + 本次 227；其中已摄取的仍是 corpus 的 79 份。ADR 决策记录用「预判可用 PV 102 → 补 15 后名义缺 3」，而按签字口径 PV 为 103；两者基数不同（预判 vs 签字、含未摄取的已签候选），主集重冻结前须按实际可摄取份数重算，ADR 已注明。

## 4. 待决策人

1. v1.4 新增 15 条 PV 候选（cand-0333～0347）签字；cand-0347 为草案，签字时确认是否接受草案入库。
2. 第 5 项产生的三类后续工作是否排期：主集标注升版（14 行中的 8 行补来源）、rp-0121/0200/0238 的证据块组计分改造、回放集相应升版。
3. 以上回填与 v1.3 / v1.4、ADR-0003 决策记录、本记录均未提交；请确认是否提交。

## 4a. 追记（2026-09-28 下午）：v1.4 的 15 条已签字

决策人回复「确认，无排除项」，cand-0347 接受为 2019 年 FDA 草案入库（题目、引用、展示须显著标明草案与日期，不得作为现行指南或约束性规则）。回填为 [v1.5](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.5.md)，v1.4 保留签字前快照。本机核对：Schema 0 错误；347 条编号与 v1.4 相同，仅 cand-0333～0347 的 `reviewer_decision/reviewer_note` 变化，15 条均 `eligible`；cand-0347 的 `reviewer_note` 含草案限制；15 份本地副本哈希一致；候选清单测试 17 项通过。签字后 `eligible` 合计 324（MA 125 / PV 118 / CO 81）；按签字口径 PV 距 120 名义缺 2，重冻结前按实际可摄取份数重算。§4 第 1 项关闭，第 2、3 项仍待决策人。

## 5. §9 自审

- 未代签：v1.4 的 15 条与后续排期均留待决策人；v1.3 的决定字段与决策人回复一致。
- 核对以原件为准：三份 © 争议均用本机渲染或文本层复核，不依赖回填说明。
- 边界：签字 ≠ 摄取；集成测试本轮未连库；主集与回放集未改动。
