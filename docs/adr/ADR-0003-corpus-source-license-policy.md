# ADR-0003：评测语料的来源白名单与四级许可准入

| 项 | 内容 |
| --- | --- |
| 状态 | 政策已决；候选清单 v0.1 已审（2026-09-10），进入 corpus 前的机械核对与决策见下文 |
| 日期 | 2026-09-09 |
| 关联 | 基线 `INV-DATA-01`、DEC-011、M1/M5 Checklist；探针集规范第 3 节；`corpus.schema.json`、`candidate.schema.json` |
| 决策人 | Qihan Zhu |

## 背景

探针集与主评测集只能使用公开、脱敏或合成数据，并要求“许可清楚”。公开可下载不等于允许保存、索引、引用和展示；官方网站也常带“版权所有”声明，ClinicalTrials.gov 上传的申办方方案可能受第三方版权约束。需要一条可执行的工程准入标准，而不是逐份临时判断。

## 决策

### 1. 来源范围：权威来源白名单 + 逐文档许可门禁

- 优先候选：药品说明书来自 NMPA、CDE、各省药监等官方来源；临床方案来自 ClinicalTrials.gov、政府或高校试验机构公开的 protocol PDF；医学/PV 指南来自 WHO、EMA、FDA/NLM、ICH、国家监管机构及专业学会官网。
- 排除：聚合站、转载站、网盘、无法确认发布主体的文件。
- 新来源同时满足“发布主体权威、版本可追溯、原始 PDF 可定位、许可通过”即可加入，不需要修改基线。

### 2. 许可标准：四级状态，政府公开信息本身不足以通过

| 状态 | 定义 |
| --- | --- |
| `eligible` | 明确开放许可、公共领域，或条款明确允许本项目所需的保存、索引、引用和展示 |
| `research_only` | 仅允许非商业使用（例如部分 WHO 材料的 CC BY-NC-SA）；不得进入生产或商业兼容验收语料 |
| `needs_review` | 公开可下载但没有明确复用授权 |
| `rejected` | 禁止复用、权利主体不明或包含无法分离的第三方内容 |

- 只有 `eligible` 可以进入探针集 v1 与商业兼容验收语料。
- `license_or_terms` 必须记录许可名称或条款摘要、允许范围、署名要求、第三方内容检查和核验日期；不能只写“政府公开信息”或“官方来源”。
- 已知情形：NMPA 官方页面标注版权所有，其文件可进入候选清单但不能仅凭官方来源标为 `eligible`；ClinicalTrials.gov 允许使用其数据但提示部分内容可能受第三方版权约束，申办方上传的方案 PDF 必须逐份检查权利归属；WHO 按具体出版物许可判断，部分材料仅允许非商业使用且第三方内容需另行确认；EMA 自有公共材料通常允许商业及非商业复制并要求署名，第三方材料不在授权内。参考：[NMPA 政务服务门户](https://zwfw.nmpa.gov.cn/web/taskdir/01)、[ClinicalTrials.gov 使用条款](https://clinicaltrials.gov/about-site/terms-conditions)、[WHO 版权与许可政策](https://www.who.int/about/policies/publishing/copyright)、[EMA Legal Notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)。

本节是工程准入标准，不替代正式法律意见；最终许可签字由决策人完成，`verified_by` 记录签字者的 surrogate id。

### 3. PV 语料补足：接受官方 PV 指南归入 PV

- 内容必须主要涉及 AE/SAE 报告、信号管理、风险管理计划、定期安全报告或 GVP。
- 保持真实 `doc_type`：指南写 `guideline`，不得为凑数伪标为 `sop`。
- `owner_dept=PV` 表示本项目的实验权限域，不代表来源文件自身有部门限制。
- `notes` 写清归属理由，例如“用于 PV 部门不良事件报告时限与信号管理条款检索”。
- 至少 3 份独立文件：不同 `document_key` 与 `source_hash`，不得用同一文件重复登记或仅拆版本凑数。

## 落地

- `corpus.schema.json`：`license_status` 固定为 `eligible`；`license_or_terms` 改为结构化对象；`terms_url` 必填；新增 `language`。
- `candidate.schema.json`：候选清单结构，允许四种状态，含 `reviewer_decision` 与 `reviewer_note`；候选进入 `corpus.json` 前必须 `reviewer_decision=eligible`。
- 探针集规范第 3 节与 PR-13 按本 ADR 修订。
- 候选清单存放于 `evals/probe/precise_clause/corpus_candidates/`，每轮审核产生新版本文件，不覆盖旧版本。

## 后果

- 中文简体说明书与指南的官方来源多带“版权所有”声明，在本政策下大多先落入 `needs_review`，需要决策人逐份判定或取得授权；探针集 v1 的每部门 15 条、每部门 3 份文档最低要求可能因此延后达成，但不降低门槛。
- 候选清单中的 URL、版本与许可引文由检索代理实际抓取并原文引用，仍需决策人复核后才能计入语料。

## 决策记录（2026-09-10，候选清单 v0.1 审核）

1. **台湾 TFDA 仿單（cand-0001 至 0006）**：有条件接受以 data.gov.tw 数据集 9117 的 OGDL-1.0 作为特定授权依据，可覆盖平台页脚的“未經同意不得重製”。进入 corpus 前必须机械证明：每个 `pdf_url` 在同日下载的数据集快照中逐字出现；记录快照 SHA-256、获取日期与字段；PDF 本身无附加限制声明；遵守 OGDL 署名，不主张商标权。任一条件失败即保持 `needs_review`，不得整体推定通过。2026-09-10 的机械核对结果见第七轮记录：六份的数据集字段均为 `exportpdf/<許可證字號>` 而非上传 PDF 链接，条件一不成立，六份保持 `needs_review`。
2. **NIH 作者、带 CONFIDENTIAL 页眉的方案（cand-0021）**：维持 `rejected`。明确保密页眉与 Moderna 第三方内容优先于 NIH 作者身份；只有取得书面授权后才能作为新候选重新审核，不得原地翻转。
3. **DailyMed 说明书（cand-0007、0008）**：降为 `needs_review`。openFDA 的 CC0 只覆盖其自身分发的 SPL 数据，DailyMed PDF 是另一分发对象与呈现形式，NLM 明确不保证第三方内容的版权状态；许可不跨渠道传递。若使用 openFDA，应建立新的 openFDA 来源候选。
4. **格式规则**：spec-v1 保持 PDF-only；官方 `.doc` 可留在候选清单但不进入本轮探针集。
5. **脚本变体**：`zh-Hant` 可进入语料并计入 `drug_name_zh` 业务切片，报告按 `zh-Hans`、`zh-Hant` 分开；探针集另加硬门禁：gold 来源为 `zh-Hans` 的样本不少于 8。
6. **ClinicalTrials.gov 条款**：决策人已于 2026-09-10 经 Chrome 核实官方 Terms and Conditions；站点条款不构成对具体上传 protocol PDF 的独立开放许可。
7. **证据结构**：候选的 `license_evidence` 改为数组，每条 `url/locator/quote` 一一对应，禁止跨候选“Same as”。

## 决策记录（2026-09-12，候选清单 v0.2 审核）

决策人对[实现记录 11](../reviews/2026-09-11-implementation-11-corpus-candidates-v0.2.md) 第 4 节五项一并回复“全部批准”，落地为候选清单 v0.3：

1. **ICH 公共许可文档（cand-0026、0027、0028）**：`reviewer_decision=eligible`。使用条件：始终承认 ICH 版权；对文本的任何改写、翻译须标明；不得给人 ICH 认可或发起的印象；MedDRA/ICH 徽标与第三方内容不在许可内。MedDRA 两份指南的许可只覆盖指南文档本身，不覆盖 MedDRA 术语库、发行数据或 SMQ 数据集，不构成 DEC-005 术语源授权。
2. **TFDA 仿單（cand-0029、0030、0031）**：`reviewer_decision=eligible`。决策人确认：仿單正文由 MAH 撰写这一事实不排除数据集 9117 的 OGDL-1.0 覆盖；“同日快照”按下载日（快照与 PDF 同日下载）理解，快照文件内的生成时间戳可以早于下载日。决策 1 的四项条件继续作为每份 TFDA 仿單进入 corpus 的机械前提。
3. **现行性与图像层核查**：由实现方机械核对并写入候选 `reviewer_note`，决策人在候选清单签字时一并确认。现行性以 TFDA 开放数据“全部藥品許可證資料集”（data.fda.gov.tw export/36，同日快照，记录 SHA-256）的 `註銷狀態/有效日期` 为准；仿單版本以文内版本行为准，无版本行时记录 PDF 元数据日期并标注“未见版本行”。图像层核查用本机 Quartz 渲染逐页人工目视，只判断版权/保密标记，不替代法律意见。
4. **cand-0032（Ⓒ）与 cand-0033（扫描件）**：允许继续核查，不当场放弃。核查结果：cand-0032 图像层确认为 © 标记，且许可证已註銷，保持 `needs_review`；cand-0033 图像层未见版权标记，但无文本层且许可证已註銷，保持 `needs_review`，不做 OCR。
5. **抽取库选型**：批准 pypdf 进入锁文件，见 [ADR-0005](ADR-0005-pdf-extraction-library.md)。

附带发现：v0.2 的五份 TFDA 仿單中四份许可证已註銷或廢止（仅美洛醣 850mg 现行），本决策的 `eligible` 只表示许可可用，不表示文档现行；现行性作为 corpus 条目字段与探针集选材条件另行处理，见候选清单 v0.3 与实现记录 12。
