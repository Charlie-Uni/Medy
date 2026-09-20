# 实现记录 47：M1-20 扩语料——候选清单 v0.7（58 条新候选，待决策人审批）

日期：2026-09-21。承接记录 46 §6。决策人指示"先把 M1 好好做好"；M1 剩余核心是主评测集（M1-20）与由它决定的门禁（M1-21），主评测集的前置是扩语料。本轮按 ADR-0003 的来源白名单与四级许可准入，机械核验后编制候选清单 v0.7，供决策人签字。

## 1. 方法

- 来源：只用已有签字先例的四类依据——ICH Legal Mentions（cand-0012/0013/0017/0028）、EMA Legal Notice（cand-0009/0010）、fda.gov 公共领域政策（cand-0011）、TFDA 資料集 9117 OGDL-1.0（cand-0034/0037/0038，含 ADR-0003 决策 1 的四项机械条件）。不引入新的许可依据，不收录 needs_review 类来源（NMPA/CDE、DailyMed、TGA/MHRA 的企业撰写说明书等）。
- 核验：每份 PDF 于 2026-09-21 下载，记录 SHA-256、字节数、页数、文本层字符数；ICH 文档核对文内 Legal notice 是否存在（E2D/E2E/E3/E9/E10/E14 为无文内公告的历史版本，依据与 E2A/E2F 相同）；EMA 文档核对封面 © 声明；MedDRA 简体中文文档核对前页「免责声明及版权公告」；TFDA 仿單以資料集 39（仿單）与 36（許可證）同日 CSV 快照（sha256 `7a522ffc…`、`70ccaece…`）机械核对 `仿單圖檔連結` 与 pdf_url 逐字相等、註銷狀態为空、有效日期在后，并筛选单一成分、文本层 ≥500 字符/页、无空白页、≤30 页；文本层扫描版权限制字样（仅两份含 ® 商标标记）。
- 未做（待签字后）：TFDA 仿單的图像层逐页目视（ADR-0003 条件 3）；所有新文档的 pypdf 抽取入库与 PII 扫描（入库流水线自动执行）。

## 2. 结果

| 分组 | 新候选 | 语言 | 部门 |
| --- | ---: | --- | --- |
| ICH 指南（E2C(R2)、E2D、E2E、E3、E9、E9(R1)、E10、E11(R1)、E14、E17、E18、E19） | 12 | en | PV 3 / CO 9 |
| EMA GVP 模块与附录（I、II、III、IV、V、VI Add I/II、VII、VIII、IX Add I、X、XV、XVI、P-III、P-IV） | 15 | en | PV |
| FDA 指南（研究者安全报告、风险监查及其 Q&A、知情同意、E6(R3) FDA 版、研究者职责） | 6 | en | PV 1 / CO 5 |
| MedDRA 简体中文（入门指南 25.0、SMQ 入门指南 25.0、更新内容 25.0） | 3 | zh-Hans | PV |
| TFDA 仿單（valsartan、quetiapine、lamotrigine、ciprofloxacin、diclofenac ×2、allopurinol ×2、amoxicillin、tamsulosin、loratadine、glimepiride ×2、levocetirizine、clopidogrel、ondansetron、losartan ×2、enalapril、bisoprolol、esomeprazole、digoxin） | 22 | zh-Hant | MA |

清单文件：[DEC-011-candidates-v0.7.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.7.json)（schema 校验通过）与 [v0.7.md](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.7.md)（审批表）。未通过筛选而放弃的 TFDA 候选（图像型 PDF、超长、复方）不登记。ICH E20、E6(R3) Annex、E2B(R3) 实施指南的固定 URL 返回 404，未收录。

## 3. 样本预算与约束

- PR-04（每文档 ≤6 条非派生）下，现有 16 份 + 新增 58 份 = 74 份 → 上限约 440 条，足以支撑 ≥300 条主评测集。
- zh-Hans 仍只有 MedDRA 文档（现有 2 + 新增 3）；简体说明书/指南的官方来源因"版权所有"落入 needs_review，只有取得书面授权才能改变。
- 主评测集需要自己的规范（每文档上限、部门与切片最低数、无答案与冲突场景、复核流程），候选签字后与决策人一起定稿。

## 4. 决策人需要做的

1. 对 v0.7 的 58 条逐条或按分组签字（`reviewer_decision`），可直接在 v0.7.md 的「决定」列填写。
2. 是否接受 SMQ 入门指南（301 页）按章节选材入库。
3. 签字后我执行：TFDA 图像层目视 → 入库（PDF 抽取、PII 扫描、chunker-v2）→ 主评测集规范草案 → 样本起草与 LLM 复核 → 争议表交您裁决。

## 5. 自审（§9）

需求：ADR-0003 白名单与四级准入逐条落实；逻辑：只复用已签字依据，机械条件先于人工判断；安全：不写入 corpus、不改变任何 eligible 状态、页文本不入库；测试：候选文件通过 schema 校验，docs 测试通过；简洁性：一个候选文件版本、一个审批表。Checklist：M1-20 仍为待做（候选清单已备）。
