# 实现记录 89：M5-01——候选清单 v1.2（230 条扩语料候选，逐条许可引文，分 5 批待签字）

日期：2026-09-26。承接决策记录 86（B.3：先出候选清单，按部门配额与来源白名单，目标 320 份；C.1–C.3：MA 120 / PV 120 / CO 80、每批 50 份签字、摄取后抽 10% 复核）。本记录只做到「候选清单 + 机械核对 + 签字表」；下载复核、图像层目视、摄取与人工复核在签字之后进行，M5-01 状态保持 **待做**，进度百分比不变。

## 1. 做了什么

| 步骤 | 产出 |
| --- | --- |
| 来源盘点（ADR-0003 白名单内） | ICH 数据库（E/M 系列现行版）、EMA（GVP 页、信号 / PSUR / 用药错误 / GCP / EudraVigilance / 生物统计学 / RWE 页及 22 个指南页）、FDA 指引总表（`search-for-guidance.json`，2,790 行）、TFDA 网站（藥物安全監視 / 臨床試驗 / 仿單格式页）与开放数据（資料集 39 仿單、36 許可證，同日快照） |
| 种子脚本 | `evals/main_set/tools/seed_candidates_v12.py`：每份候选的标题 / 出版者 / 部门 / 落地页 / PDF 链接 / 归属理由；TFDA 仿單按成分（INN）从快照机械选取（现行、處方藥、单一成分、上传 PDF 链接、优先本地厂与口服固体剂型），每成分最多 3 个备选 |
| 编译工具 | `evals/main_set/tools/compile_candidates.py`：逐份下载 → `%PDF` 魔数 → SHA-256 / 字节 / 页数 / 文本层字符（pypdf 6.18.1）→ 限制标记扫描 → 提取文内许可声明（ICH Legal notice、EMA 封面 ©）→ TFDA 仿單对快照逐字核对（决策 1 条件 (1)(2)）与现行性 → 填四级预判与证据数组 → `candidate.schema.json` 校验 → 追加到 v1.1 → 按 50 条分批写签字表 |
| 清单 | `evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.2.json`（332 条 = v1.1 的 102 + 新增 230）、`…-v1.2.md`（签字表）、`…-v1.2.seeds.jsonl`（种子，可复现） |
| 单元测试 | `tests/unit/evals/test_candidate_compiler.py`：限制标记只认文件标记不认正文用词、EMA / ICH 版本与声明抽取、台湾日期与仿單版本行 |

PDF 本身只进 `evals/main_set/sources_staging/<sha256>.pdf`（gitignored），不进 Git。

## 2. 结果

### 2.1 新增 230 条（预判 eligible 226，needs_review 4）

| 分组 | 条数 | 部门 | 许可依据（与已签字候选同源） | 逐份补充证据 |
| --- | ---: | --- | --- | --- |
| ICH 指南 | 14 | CO 9, PV 5 | ICH Legal Mentions（公共许可，承认版权、排除徽标与第三方内容） | 7 份有文内 Legal notice，逐字抽取；其余同 E2A/E2F 只有站点 Legal Mentions |
| EMA 指南 / 程序文件 | 48 | PV 29, CO 17, MA 2 | EMA Legal Notice（2026-09-26 curl 复核一致） | 封面 「© EMA … Reproduction is authorised provided the source is acknowledged」逐份抽取；文号 + 日期从首页识别 |
| FDA 指南 | 87 | CO 31, PV 31, MA 25 | fda.gov 公共领域声明（2026-09-26 复核一致） | 最终 / 草案与 docket 号来自 FDA 总表 |
| TFDA 指引 / 法規 / 公告 | 12 | PV 6, CO 4, MA 2 | 網站資料開放宣告（OGDL-1.0）+ 著作權聲明（2026-09-26 复核一致） | 首页日期识别 |
| TFDA 仿單 | 69 | MA 69 | 資料集 9117/39 OGDL-1.0（决策 2026-09-10 第 1 项、2026-09-12 第 2 项） | 条件 (1)(2)：pdf_url 与快照字段逐字相等、快照 SHA-256 与行数入证据；条件 (3) 文本层扫描已做、图像层目视待签字后；(4) 入库时署名 |

同日快照：資料集 39 zip `4d3ad3be…5233`（内层 `39_2.csv` `0b024337…7946`，29,875 行）；資料集 36 zip `1f72990c…aa3d5`（内层 `36_2.csv` `9a393665…6ea4`，66,499 行）。

预判 eligible 的部门分布（含现有 79 份）：

| 部门 | 现有 | 新增 eligible | 合计 | 决策 86 目标 | 差 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MA | 27 | 95 | 122 | 120 | +2 |
| PV | 32 | 70 | 102 | 120 | **−18** |
| CO | 20 | 61 | 81 | 80 | +1 |
| 合计 | 79 | 226 | 305 | 320 | −15 |

### 2.2 预判 needs_review 的 4 条（建议）

| 候选 | 问题 | 建议 |
| --- | --- | --- |
| cand-0114 ICH E2B(R3) ICSR 实施指南（Step 3 咨询版） | 文内 「jointly by ISO and Health Level Seven International. ALL RIGHTS RESERVED」——嵌入 ISO/HL7 版权材料，且为咨询版 | 不入库（ADR-0003：无法分离的第三方内容）；PV 的 E2B 需求由 E2B(R3) Q&A v2.4（cand-0113）覆盖 |
| cand-0293 理思必妥膜衣錠（Risperdal，嬌生） | 文本层 「© Johnson & Johnson」，原厂版权标记 | 不入库（同 cand-0032 处理） |
| cand-0298 妥泰膜衣錠（Topamax）、cand-0316 撒樂腸溶錠 | 文本层乱码（字体编码）中出现 「©」，不能判定是否真实标记 | 保留 needs_review，签字后图像层目视决定 |

### 2.3 未列入（机械核对未通过，全部记录在 `dropped.json`）

| 原因 | 条数 | 说明 |
| --- | ---: | --- |
| 仿單无文本层（扫描件） | 70 | 试过 110 个成分，47 个成分的首选仿單是扫描件；按 ADR-0003 决策 2026-09-12 第 4 项不做 OCR，改试同成分第 2 / 3 备选（23 份也是扫描件），最终 66 个成分各 1 份 eligible，另 3 个成分只剩带 © 标记的仿單（2.2） |
| TFDA 指引无文本层 | 3 | 藥品定期安全性報告總結報告格式、通報格式（2005 / 2008 公告扫描件）、西藥非處方藥仿單外盒格式及規範公告 |
| 非 PDF | 5 | TFDA 藥品安全資訊風險溝通表 ×4 与 藥品臨床試驗計畫技術性文件指引 是 .docx（spec-v1 PDF-only），第二轮已从种子移除 |
| 同成分已有候选 / 超出 66 份配额 | 20 | 备选与超配额，未评估许可 |
| 已在清单中 | 2 | warfarin（cand-0036）等 |

未纳入的来源：WHO 出版物为 CC BY-NC-SA 3.0 IGO，按 ADR-0003 §2 落入 `research_only`，不能进商业兼容验收语料，故未播种。

### 2.4 PV 缺口 18 份的处置（需决策人表态）

- **先在白名单内补（推荐，v1.3）**：FDA 尚有 Establishing Pregnancy Exposure Registries（2002）、Postapproval Pregnancy Safety Studies（草案 2019）、Best Practices for FDA Staff in the Postmarketing Safety Surveillance（2019）、Classifying Significant Postmarketing Drug Safety Issues（2012）、Providing Submissions in Electronic Format — Postmarketing Safety Reports for Vaccines、REMS Assessment: Planning and Reporting（草案）等约 8–10 份；EMA 尚有 RMP 模板 / 格式指南、EudraVigilance 用户手册、PSUR 评估模板等约 5 份。预计可到 PV 112–115。
- **仍不够时扩来源（需补 ADR-0003）**：英国 MHRA（Open Government Licence v3，允许商业复用并署名）与澳大利亚 TGA（CC BY 3.0 AU）的 PV 指南各约 10 份。这一步改变白名单，**未经您同意不做**。

## 3. 请您签字

签字表 `DEC-011-candidates-v1.2.md` 共 5 批：批 1（cand-0103–0152：ICH 14 + EMA 前 36）、批 2（cand-0153–0202：EMA 后 12 + FDA 前 38）、批 3（cand-0203–0252：FDA 后 49 + TFDA 指引 1）、批 4（cand-0253–0302：TFDA 指引 11 + 仿單 39）、批 5（cand-0303–0332：仿單 30）。回复方式沿用 v0.7：「批 1 确认」或「批 1 确认，除 cand-xxxx」；对 2.2 的 4 条与 2.4 的两个选项请一并表态。

## 4. 签字后的流程（不在本记录范围）

1. 按 pdf_url 重新下载并与清单 SHA-256 比对，pypdf 抽取页文本并记录页数与告警（与 v0.8 → corpus 相同）。
2. 66 份仿單逐页图像层目视（条件 3），结果写 `evals/main_set/tfda_image_layer_check_<日期>.md`。
3. `build_corpus.py --candidates <签字后的 v1.3.json>` 摄取；`license_or_terms.attribution_text` 落实署名（条件 4）。
4. 每批抽 10%（每部门至少 5 份）逐页人工核对，其余走 M1-10 机械核对（决策 86 C.3）。
5. 语料规模确定后进入 M5-05 容量测试。

## 5. §9 自审

- 每条候选的 `license_evidence` 是数组，url / locator / quote 一一对应，无 「同上」；ICH 引文的复核方式如实写明（节点 `updated` 时间戳未变，引文沿用 2026-09-09 抓取）。
- `eligible` 只表示机械核对通过且许可依据与已签字候选同源；4 条例外逐条给出理由；扫描件一律未列入而不是 OCR。
- 第一轮扫描把正文里的 "confidential" / "not for distribution to patients" 当成限制标记（16 条误判），第二轮改为只认文件标记（大写 CONFIDENTIAL、固定短语、不跟宾语的 not for distribution），并用单元测试钉住；ISO/HL7 的 ALL RIGHTS RESERVED 仍被正确标出。
- 两处 EMA 链接第一轮 404（QRD 约定、自发报告解读指南），已修正为站内实际路径并重跑。
- 仿單的 `version_or_date` 多数为 「未见版本行 + PDF 元数据日期 + 許可證现行性」，与 v0.7 口径一致；文内识别到版本行的照抄。
- 未改动 `corpus.json`、未改动进度百分比；M5-01 状态仍为待做。

## 6. 文件

- `evals/main_set/tools/seed_candidates_v12.py`、`evals/main_set/tools/compile_candidates.py`（新）
- `evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.2.json` / `.md` / `.seeds.jsonl`（新）
- `tests/unit/evals/test_candidate_compiler.py`（新）
- `docs/DEVELOPMENT_ROADMAP.md`、`docs/TASK_KNOWLEDGE_MAP.md`：M5-01 行加注候选清单状态（状态与百分比不变）
