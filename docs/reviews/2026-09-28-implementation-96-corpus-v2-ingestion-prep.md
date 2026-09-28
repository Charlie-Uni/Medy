# 实现记录 96：M5-01 语料入库准备——234 份已签字文档的复核、抽取、图像层核查与 corpus v2 草稿

日期：2026-09-28。决策人当日批复三项：提交（已完成，e40462f / f85bda3）、重跑检索候选第 3 轮（已启动，结果另记）、开始语料入库管线。本记录覆盖入库前的全部机械与人工核查，以及 `corpus_v2.json` 草稿；**数据库入库与激活尚未执行**（与付费评测共用本机 GPU / CPU，待评测结束后再跑，见 §7）。未修改冻结的 `main-v1-provisional`。

## 1. 入库对象的确定

| 步骤 | 数量 | 说明 |
| --- | ---: | --- |
| v1.5 签字 `eligible` | 324 | v1.1 已签 82 + 本轮 227 + 15 |
| 减：已在 corpus（同 source_hash） | 71 | v1.1 批已入库 |
| 减：`notes` 无 sha256 | 8 | cand-0009～0018 的早期候选（探针 v2 语料，另有 hash 记录） |
| 减：许可证已註銷 / 廢止 | 2 | cand-0030、0031（记录 95 §5 第 1 项建议不进主体，决策人未另指示） |
| 减：合成冲突 fixture 来源 | 1 | cand-0100（GVP Annex I 旧版，仅用于 fixture） |
| 减：抽取乱码 | 7 | cand-0275、0282、0284、0307、0316、0317、0320，见 §3 |
| 减：产品身份不符 | 1 | cand-0325，见 §4 |
| **入库对象** | **234** | ICH 13、EMA 58、FDA 92、TFDA 指引 12、TFDA 仿單 59；MA 88 / PV 85 / CO 61 |

## 2. 原件与页文本

- **重新下载比对**：242 份（排除乱码与身份不符前）按 `pdf_url` 重新下载，SHA-256 与签字清单逐一相等 242/242。FDA 站点对并发请求返回 404（48 份首轮失败），单线程加退避后全部成功；签字副本未被覆盖。
- **页文本抽取**：`python -m medops.evals.probe.extract` 到 `evals/main_set/pages/<sha>/`，242/242 成功；pypdf 告警 7 份（cand-0220 5 条、0269 4、0279 1、0284 3、0294 1、0317 4、0324 1），空白页 5 份（cand-0104 p4、0105 p4、0110 p40/62、0194 p45–50、0340 p75）。告警文档入库时按 ADR-0009 落为 `low_trust`，本轮不用 `--accept-quality` 放行（同记录 49 口径，需决策人签字）。

## 3. 抽取质量：7 份乱码排除

按 2026-09-13 对欣服寧的口径逐页扫描（IPA / 修饰符号 / 组合符号区等只会由错误字形映射产生的字符，私用区项目符号与全角标点不计），页内 >2% 且页字符 ≥200 视为乱码页：

| 候选 | 乱码页 / 总页 | 占比 |
| --- | --- | ---: |
| cand-0282 摩暢 | 1/1 | 100% |
| cand-0284 美腸順 | 1/1 | 100% |
| cand-0307 抒敏 | 2/2 | 100% |
| cand-0316 撒樂 | 2/2 | 100%（文本层 © 亦由此产生，记录 95 已确认图像为 ②） |
| cand-0320 舒維速保 | 2/2 | 100% |
| cand-0317 憶如新 | 1/2 | 17% |
| cand-0275 欣服寧 1mg | 1/4 | 2.3%（与 cand-0036 同一 PDF） |

其余 13 份有零星此类字符（≤2%），保留；标注阶段按页判定。

## 4. 产品身份不符：cand-0325

候选标题「硝弗侖陶因錠100公絲（NITROFURANTOIN TABLETS）」来自资料集 39 的 中文品名 / 英文品名，但 PDF 内容是「培他旺糖衣錠 Peitaon S.C. TAB」（維他命 B1 複合劑，瑞士藥廠）。PDF 内印的許可證字號 003893 与资料集 36 该字号记录（榮民製藥）一致，即资料集把该字号的仿單連結指向了另一产品。图像层无版权标记，但产品身份不可信，本轮不入库。其余 59 份仿單的英文品名均在各自页文本中找到。

## 5. 图像层核查（ADR-0003 条件 3）与 PII 复核

- [tfda_image_layer_check_2026-09-28.md](../../evals/main_set/tfda_image_layer_check_2026-09-28.md)：60 份 264 页 86 张检视图逐张目视，59 份通过、1 份即 cand-0325。两处疑点（cand-0301 Pfizer 製造廠信息、cand-0321 印刷稿标注）高分辨率复核后均非权利声明。
- [pii_review_2026-09-28.json](../../evals/main_set/pii_review_2026-09-28.json)：`pii-rules-v1` 在 108 份命中 252 处——机构职能信箱（FDA druginfo/ocod/faersesub 等 71+59+9 处、EMA、ICH、MSSO、各成员国 PV 机构收件箱）、5 个 FDA 官员公务信箱（公开指南联系人栏，spec-m1 §3.4 职业信息不视为 PHI，已单列 `named_person_work_emails` 供决策人否决）、3 处 `medical record number` 术语提及。全部判为误报并留档；`build_corpus.py` 读该文件后才把这些文档标为 clean。

## 6. corpus v2 草稿与激活计划

- `build_corpus.py` 通用化（原来硬编码 v0.8 批的 `记录 47` 标记与 2026-09-21）：`--select-ids-file`、`--verified-at`、`--batch-note`、`--pii-review`、`--dataset-version`、`--base-corpus`（扩展现有 corpus 而不是从探针语料重建；扩展模式下不重复应用 fixture 与 version_fixes）。`document_key` 规则扩展到非 GVP 的 EMA 文件、FDA 非固定映射文件（标题主干 + `-draft` + 年份）、TFDA 指引（按候选 id 的固定映射）；键长 ≤ 60。年份取文件日期而非 EMA 文号中的数字（EMA/198270/2026 不再得 1982）。FDA 草案的标题统一追加「（FDA 草案 <日期>，Draft / Not for Implementation，非现行指南）」，cand-0347 的 `reviewer_note` 草案限制并入 `notes`，共 19 份草案。
- [corpus_v2.json](../../evals/main_set/corpus_v2.json)：`dataset_version=main-v2-provisional`，313 份 = 79（逐字承接 corpus.json）+ 234；MA 115 / PV 117 / CO 81；Schema 校验通过；`document_key` 无重复；`license_or_terms.verified_at=2026-09-28`、`verified_by=reviewer-01`。冻结的 `corpus.json` / `main-v1-provisional` 未改。
- [activation_plan_2026-09-28.json](../../evals/main_set/activation_plan_2026-09-28.json)：234 条 `effective_from`。来源：ICH 采纳日 13、EMA 文件日期 51、FDA 发布月首日 92、仿單 PDF 元数据日期 58（未见版本行）、TFDA 文件日期 7、首页人工读取 14（cand-0253/0255/0260 只有 PDF 元数据日期；cand-0256 原候选记「1924-05-20」实为 2013-05-20；cand-0257「1936-03」实为 2025-03；cand-0287 取仿單末尾印刷编码 20220701）。这些日期是检索的生效时间字段，不是说明书法定生效日；许可证现行 ≠ PDF 修订版现行的边界不变。
- [qa_sample_2026-09-28.md](../../evals/main_set/qa_sample_2026-09-28.md)：决策 86 C.3 的 10% 逐页人工复核抽样，23 份（6 批各 10%，每部门 ≥5，种子 20260928），每份 3 个抽查页，待复核人填写。

## 7. 未完成与下一步

1. **数据库入库与激活**：`python -m medops.ingestion.load --corpus evals/main_set/corpus_v2.json --sources-dir evals/main_set/sources_staging --pages-dir evals/main_set/pages --actor reviewer-01 --accept-pii <108 条>` → `python -m medops.ingestion.activate --plan evals/main_set/activation_plan_2026-09-28.json --actor reviewer-01`。等检索候选第 3 轮重跑结束后执行（同机 GPU 竞争会制造系统失败，记录 90 教训）。5 份 pypdf 告警文档会落为 `low_trust` 保持 draft。
2. 10% 逐页复核（§6）由复核人完成后，才能以 `main-v2-provisional` 重冻结主集与回放集；检索基线随之重跑。
3. 决策人待定：cand-0325 是否向 TFDA 反馈或改选同成分他牌；5 份 `low_trust` 是否签字放行；cand-0030/0031 是否作为历史版本另行安排。

## 8. §9 自审

- 边界：签字 ≠ 入库 ≠ 激活；本轮到 corpus 草稿为止，数据库未写。
- 不放宽：乱码按既定阈值排除、告警不自动放行、PII 全部留档并单列人名信箱。
- 冻结集未改：`corpus.json` 与 `main-v1-provisional` 逐字节不变；新语料写入独立文件。
- `make check` 见 §9 追记。

## 9. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`：仓库外导入、ruff、mypy、pytest **1252 passed / 70 skipped**（PostgreSQL 容器已启动，集成测试实际连库；70 项跳过为候选 C `pg_search` 服务器未启动等既有条件）、Schema 无漂移、`git diff --check` 通过。注意：本次 `make check` 与检索候选第 3 轮重跑并行运行了约 80 秒，重跑期间的系统失败计数在评测记录中单独核对。
