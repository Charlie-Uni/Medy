# 第七轮记录：候选清单 v0.1 审核决策与证据结构修正（2026-09-10）

| 项 | 内容 |
| --- | --- |
| 触发 | 决策人对第六轮 6 项待决事项的裁定，以及候选清单证据结构问题 |
| 执行 | Claude（Fable 5.1） |
| 决策人 | Qihan Zhu |
| 结论 | 六项决定全部落地；证据结构改为逐条 url/locator/quote；TFDA 六份按决策人要求做了机械核对，条件一不成立，保持 needs_review；探针集 v1 仍被两项门禁阻塞 |

## 1. 证据结构修正

- `candidate.schema.json`：删除 `license_evidence_quote/license_evidence_url`，改为 `license_evidence` 数组，每条 `url`、`locator`、`quote` 一一对应；`quote` 与 `reasoning` 禁止以“Same as”“As cand”“同上”开头。
- 候选清单 v0.1 重建：25 条全部自带完整证据，无跨候选引用；此前代理写的 6 条“As cand-…”理由改为完整文字，`compiled_by` 超长也被 Schema 拦下并修正。
- SPEC 3.3 同步写明该规则。

## 2. 六项决定的落地

| # | 决定 | 落地 |
| --- | --- | --- |
| 1 | TFDA 仿單有条件接受 OGDL，进入 corpus 前须机械证明四项条件 | ADR-0003 决策记录；cand-0001 至 0006 的 `reviewer_note` 记录四项条件与核对结果 |
| 2 | cand-0021 维持 rejected，不作例外 | `reviewer_decision=rejected`，备注说明书面授权后只能作为新候选 |
| 3 | DailyMed 降为 needs_review，许可不跨渠道传递 | cand-0007、0008 状态与决策改为 needs_review |
| 4 | spec-v1 保持 PDF-only，.doc 留在候选不进探针集 | SPEC 3.3 新增说明；cand-0024 备注 |
| 5 | zh-Hant 可入语料并计入 drug_name_zh，报告分脚本变体；新增 zh-Hans 样本不少于 8 的硬门禁 | SPEC 3.4、第 7 节、PR-03；`manifest.schema.json` 新增 `minimums.zh_hans_samples=8` 与 `counts.per_language`；ADR-0002 实验输入 |
| 6 | ClinicalTrials.gov 条款已经 Chrome 核实 | cand-0021、0022、0023 的 `reviewer_note` 采用决策人提供的文字；证据 locator 标注核实日期 |

## 3. TFDA 机械核对（2026-09-10）

| 条件 | 结果 |
| --- | --- |
| (1) `pdf_url` 在同日数据集快照中逐字出现 | 不成立。快照来源 `https://data.fda.gov.tw/data/opendata/export/39/json`（zip sha256 `4817da5299bdf4d66a38ba17e42986b25c7d0ee47787a961aabe1c1f9ad92abe`，内层 `39_5.json` sha256 `ce8276a050ee039a55609b55aad158b0d3c5266584fe691f22dc6f37f4e72c4d`，29,855 行，字段 許可證字號/中文品名/英文品名/仿單圖檔連結/外盒圖檔連結）。六个許可證字號各有一行，`仿單圖檔連結` 均为 `https://mcp.fda.gov.tw/exportpdf/<許可證字號>`，不是代理选用的 `/insert/pdfcasefile/` 上传 PDF |
| (2) 记录快照哈希、日期、字段 | 已记录于每条候选的 `license_evidence` |
| (3) PDF 无附加限制声明 | 五份通过（命中的“禁止”“未經”均为临床文本）；cand-0005（耐適恩）含“© AstraZeneca 2009 - 2013”“本註冊商標屬 AstraZeneca 集團之財產”，不通过 |
| (4) OGDL 署名、不主张商标权 | 作为进入 corpus 时的记录义务写入 `reviewer_note` |

结论：六份全部保持 `needs_review`。快照中另有 16,989 行的 `仿單圖檔連結` 为 `/insert/pdfcasefile/` 形式，下一轮可从中改选仿單，使条件 (1) 可被机械证明；`/exportpdf/` 形式按代理观察为需 POST 的电子仿单，spec-v1 规则 1 下不可用，如要采用需另行验证其能否作为稳定 PDF 获取。六份 PDF 已于 2026-09-10 重新下载并记录 SHA-256（见候选 `notes`），副本留在会话 scratchpad，未入仓库。

## 4. 修订后的分布

| 部门 | eligible | research_only | needs_review | rejected | 合计 |
| --- | --- | --- | --- | --- | --- |
| MA | 0 | 0 | 8 | 0 | 8 |
| PV | 6 | 1 | 1 | 0 | 8 |
| CO | 2 | 0 | 4 | 3 | 9 |
| 合计 | 8 | 1 | 13 | 3 | 25 |

与第六轮相比 eligible 从 10 降到 8（DailyMed 两份降级），TFDA 六份因条件 (1) 不成立未能升级。探针集 v1 当前被三项门禁阻塞：MA 没有 eligible 文档，CO 只有 2 份，`zh-Hans` 样本为 0。

## 5. 验证

| 检查项 | 实测 |
| --- | --- |
| 六个 Schema 元校验 | 通过 |
| 示例 manifest、corpus、3 条样本 | 通过；示例哈希同步 |
| 候选清单（25 条）按新 Schema 校验 | 通过 |
| 结构断言：ID 有序唯一、证据非空、无 Same as、决策已写入 | 通过 |
| 反向测试：Same as 引文、空证据、As cand 理由、旧字段残留、zh_hans_samples=0、缺 per_language | 6/6 被拒绝 |
| 机械核对 | 见文末 |

## 6. 待办

- 从数据集快照中 `/insert/pdfcasefile/` 形式的行改选 TFDA 仿單并重做四项核对（需决策人确认是否进行）。
- MA 与 CO 的 eligible 文档不足，以及 zh-Hans 为 0：需要简体来源授权或新的白名单来源，才能冻结探针集 v1。
- 若决定使用 openFDA，建立 openFDA 来源候选。
- 本轮所有改动未提交。

| 检查项 | 实测 |
| --- | --- |
| 不变量 / 重复 ID | 30 / 0 |
| checklist / 已勾选 | 99 / 0 |
| DEC 行数 | 11 |
| 代码围栏（基线 / SPEC） | 14 / 2 |
| 相对链接缺失 | 0 |
| 候选清单中 “Same as / As cand” 残留 | 0 |
| 来源 SHA256SUMS | MedOps_Copilot_项目设计文档_v0.1.pdf: OK PROJECT_DESCRIPTION_v0.1.md: OK  |
| git diff --check | 输出行数 0 |

## 8. 更正说明（2026-09-10，第四轮复核后追加）

- 基线 1.3 节原文把多模态 RAG 写为“P1 增强项”，与 7.2 节和 P1/P2 checklist 的 P2 定位不一致。按决策就地更正为“P2 研究型增强（见 7.2）”，保持 v0.6，不新增 ADR，本记录以上各节结论不变。
- 同时新增机械一致性测试 `tests/unit/docs/test_baseline_roadmap_consistency.py`：核对基线各阶段条目数、路线图编号唯一且连续、总数一致。该测试不比对验收文字，验收要求始终以基线为准。
