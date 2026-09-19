# 实现记录 20：切分器 chunker-v1、入库流水线与迁移 0003（M1-10；M1-09 部分）

日期：2026-09-17。范围：阶段 3 第一轮。交付页锚定切分器、从 corpus.json 驱动的入库流水线（校验、去重、PII 默认拒绝、chunk 与区间写入、审计）、迁移 0003（文档来源与许可字段、入库任务质量计数）、corpus.json v1 草稿，并把 12 份已签字且 PII 干净的文档写入本机事实平面。未修改基线、SPEC、Schema 规则；未提交 Git；4 份 PII 命中文档未入库，等决策人复核。**状态：待 Codex 审核。**

## 1. 完成

### 1.1 chunker-v1（[src/medops/ingestion/chunker.py](../../src/medops/ingestion/chunker.py)）

- 在 norm-v1 规范化后的页文本上切分，chunk 正文恰等于 `normalized_page[char_start:char_end]`，与校验器和 SPEC 第 6 节命中规则同一坐标系；v1 不跨页，每 chunk 一个区间。
- 句末切分（。！？；与 ASCII .!?; 后接空白），达到 400 字即收口，上限 600，无标点长串在空白处切，尾巴不足 120 字且合并后不超上限时并入前一块。
- 章节标签按原始页文本的"整行标题"识别（【】、中文说明书章节名、`4.2 …`、`VI.B.1. …` 形式）并定位到规范化文本，跨页沿用；只是尽力标签，引用以页码与 chunk_id 为准。
- `content_hash = SHA-256(content)`，与 0001 触发器的重算一致。

### 1.2 入库流水线（[pipeline.py](../../src/medops/ingestion/pipeline.py)、[load.py](../../src/medops/ingestion/load.py)，`make load-corpus`）

顺序：PDF 魔数与 50 MB 上限 → 字节数与 SHA-256 必须等于 corpus.json 声明 → 锁定 pypdf 重新抽取并与 `v1/pages/` 已存页文本逐字节比对（漂移即拒绝）→ 无文本层拒绝 → `pii-rules-v1` 扫描，命中默认拒绝（INV-DATA-01），带复核理由才放行且写 `pii_review_override` 审计 → chunker-v1 → 同一事务写 source_objects（哈希已存在则复用）、ingestion_jobs（`extractor_warnings`、`empty_pages`、`parse_quality`）、documents（draft，含 document_key 与来源许可字段）、chunks、chunk_spans、document_acl（归属部门 read）、doc_audit（`ingest`）。同 key 同版本重跑返回 `exists` 不写；同一来源上的第二份文档拒绝（基线 3.3 需管理员确认）。`parse_quality`：抽取告警为 0 记 trusted，否则 low_trust（数据库约束下不能 active）。

### 1.3 迁移 0003

documents 新增 `document_key`（部分唯一）、`source_url`、`publisher`、`retrieved_at`、`license_name`、`terms_url`、`attribution_text`；ingestion_jobs 新增 `extractor_warnings`、`empty_pages`。降级可逆；单一 head 0003。另修正 `migrations/env.py`：Alembic 的日志配置不再禁用既有日志器（此前会让 pypdf 告警计数在同进程内失效，全量测试暴露了这一点）。

### 1.4 corpus.json v1 草稿与本机入库

- [evals/probe/precise_clause/v1/corpus.json](../../evals/probe/precise_clause/v1/corpus.json)：12 份文档（MA 5、PV 5、CO 2），字段按 SPEC 3.4，`verified_by=reviewer-01`，`verified_at` 为决策人签字日期，`version_label` 记文内版本或 PDF 元数据日期并标注"未见版本行"，通过 corpus.schema.json 校验。
- 本机开发库：`make load-corpus` 12 份全部 `ingested`，共 1,245 个 chunk，长度 24～600、均值 423；`tfda-label-esomen-40mg` 因 8 条抽取告警记 low_trust；其余 trusted；12 条 `ingest` 审计。

| document_key | 部门 | chunk 数 | parse_quality |
| --- | --- | ---: | --- |
| meddra-term-selection-ptc-4-26-zh-hans | PV | 100 | trusted |
| meddra-data-retrieval-ptc-3-26-zh-hans | PV | 87 | trusted |
| ich-e8-r1-step4-2021 | CO | 175 | trusted |
| tfda-label-loformin-850mg | MA | 17 | trusted |
| tfda-label-deurinol-300mg | MA | 31 | trusted |
| tfda-label-zosaa-50mg | MA | 10 | trusted |
| tfda-label-cancliol-100mg | MA | 6 | trusted |
| tfda-label-esomen-40mg | MA | 33 | low_trust |
| ich-e2a-step4-1994 | PV | 62 | trusted |
| ich-e2f-step4-2010 | PV | 194 | trusted |
| tfda-adr-report-form-guide-4th | PV | 45 | trusted |
| ich-e6-r3-step4-2025 | CO | 485 | trusted |

### 1.5 PII 复核待决（4 份未入库、未进 corpus.json）

`pii-rules-v1` 命中原文全部为机构邮箱或指南中的数据要素名称：

| 候选 / key | 命中 |
| --- | --- |
| cand-0009 ema-gvp-module-vi-rev2 | `medical record number (from`、`medical record number,`（指南列举患者可识别性要素）；EVLIT@ema.europa.eu、duplicates@ema.europa.eu |
| cand-0010 ema-gvp-module-ix-rev1 | emerging-safety-issue@、withdrawnproducts@、qdefect@、MAH-EV-signals@ema.europa.eu |
| cand-0011 fda-sponsor-safety-reporting-2025 | druginfo@、industry.biologics@、ESUB@、PremarketSafetyReports@fda.hhs.gov |
| cand-0018 fda-protocol-deviations-draft-2024 | druginfo@、ocod@、CDRH-Guidance@fda.hhs.gov |

按 INV-DATA-01 默认拒绝；决策人确认为非个人数据后，以 `--accept-pii key=理由` 入库并留 `pii_review_override` 审计，corpus.json 的 `pii_scan.method` 同步写明人工复核结论。规则集本身不改（改规则需升版并重跑全部文档）。

## 2. 验证

```text
tests/unit/ingestion/test_chunker.py -> 8 passed：切片精确、覆盖无遗漏、句末边界与尺寸界、尾巴合并、无空白硬切、
  空页跳过、章节识别与跨页沿用、确定性与版本记录
tests/integration/test_ingestion.py -> 8 passed：七表写入与偏移/哈希/来源字段逐项核对、幂等与同源第二文档拒绝、
  哈希/字节/魔数/大小拒绝且零写入、PII 默认拒绝与覆盖审计、页文本漂移拒绝、无文本层拒绝、
  入库草稿对 app/readonly 不可见对 admin 可见、批量加载器逐条报告与退出码
tests/integration/test_migrations.py -> 单一 head 0003，往返测试通过
env -u PYTHONPATH make check -> ruff 通过；format-check 99 文件；mypy 46 文件；pytest 358 passed（298 单元 + 60 集成）；schemas 无漂移
本机：make migrate -> 0003 (head)；make load-corpus -> 12/12 ingested
```

## 3. 未完成与边界

- M1-09：DOCX、恶意文件扫描、多 document 共用 source 的管理员确认流程未做；M1-10 的 gold→chunk 映射文件随标注生成。
- 章节标签为启发式；探针 gold 的 `section` 由标注者填写，命中规则不依赖它。
- 已入库的草稿带 `ingest` 审计行，而 doc_audit 外键不级联、审计不可改，因此误入库的草稿目前无法物理删除，也不能归档（draft→archived 非法）。见第 4 节第 2 问。
- 入库文档均为 draft，无 `effective_from`；激活属管理动作（M1-11 发布流），DEC-001 实验前需决定 `effective_from` 的取值口径。

## 4. 需要决策人决定

1. **四份 PII 命中文档**：是否确认上表命中均为机构邮箱与指南术语、非个人数据，允许以覆盖方式入库并写审计。建议允许。
2. **误入库草稿的处置**：建议为 documents 增加终态 `withdrawn`（仅 draft 可进入，写审计，不物理删除），以新迁移追加枚举值；替代是允许物理删除草稿并级联其审计行，但那违背审计追加写。请选择。
3. **入库文档的 `effective_from` 口径**（激活时需要）：仿單建议取 TFDA 登记的许可证核发/异动日期之一或 PDF 元数据日期，指南取文内发布日期；请确认取值优先级，我在 M1-11 发布流里实现。

## 5. Codex 审核焦点

- chunker 的段落切分正则与尾巴合并规则是否有导致跨页或空块的边界情况（测试覆盖覆盖性与非空）。
- 流水线"先全部校验再写"的顺序与 `conn.transaction()` 的回滚保证；`exists` 判定只按 key+version。
- parse_quality 只看告警数是否过严或过松（cand-0038 的粗体重复不产生告警，而 33 条告警的安通脈已排除在外）。
- 0003 的 `document_key` 部分唯一索引与 `documents_guard` 未把新列列入不可变集合的取舍。

## 6. 自审（基线 §9）

1. 需求：只覆盖 M1-09 部分与 M1-10；未做检索、未激活文档、未改规则集。
2. 逻辑：拒绝路径在任何写入之前；PII 覆盖必须留痕；同源第二文档拒绝。
3. 安全：原件与页文本在忽略目录；入库以管理员角色执行，草稿对业务角色不可见有测试。
4. 契约：新增列有 CHECK；corpus.json 通过 Schema；字段名与 SPEC 一致。
5. 测试：正常、边界、失败、幂等、审计、RLS 可见性、CLI 退出码。
6. 可观测：每次入库一条审计，含 chunk 数、告警数、PII 命中数与版本。
7. 简洁性：三个模块、一个迁移；无新依赖。
8. 验证：见第 2 节；未验证项：远端 CI。
9. Checklist：基线勾选保持 0；路线图 M1-09 部分、M1-10 已实现；P0 加权进度 22.8%。
