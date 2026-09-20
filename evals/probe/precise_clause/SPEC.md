# 精确条款探针集冻结规范（precise_clause）

> - 规范版本：spec-v1（2026-09-08、2026-09-09、2026-09-10 就地修订；修订时尚无冻结数据集或下游引用）
> - 日期：2026-09-20（冻结前补充精确 PII 裁决与运行证据绑定；既有命中与实验判据不变）
> - 依据：[ADR-0002](../../../docs/adr/ADR-0002-lexical-retrieval-selection.md)、[工程基线](../../../docs/ENGINEERING_BASELINE.md) 3.2、3.6、3.7、5.1、5.8、5.9 与 M1 Checklist
> - 载体：本规范与 `schema/` 下的 JSON Schema（draft 2020-12）。Pydantic 模型与校验器随 M0 生成，以 JSON Schema 为准；两者冲突时以本规范文字为准并修正 Schema
> - 数据状态：`v1` 已于 2026-09-20 本地冻结，归档状态见 ADR-0002。`examples/` 只是示意，不是标注数据，`status` 固定为 `draft`

## 1. 目的与边界

- 本探针集是 DEC-001 词法检索选型实验的唯一输入，用于计算 ADR-0002 定义的 Lexical Recall@20、六个切片指标和端到端 Recall@5 对比。
- 只含有答案样本：每条样本至少 1 条 required gold。无答案样本不属于本集，按基线 5.9 单独评测。
- 冻结后并入不少于 300 条的主评测集，但保留独立版本、独立哈希和独立报告。并入后这些样本按基线 5.9 的主集复核政策补第二人工复核。
- 不进入 Loop 候选生成上下文（`INV-EVAL-01`）。
- 切片门禁作用域：ADR-0002 的每类不少于 8 条与各切片 Lexical Recall@20 门禁适用于本实验；基线 5.8 的“样本少于 30 条只作诊断”只适用于 M4 Loop 回放报告，不适用于本实验。
- spec-v1 只支持 PDF 来源；DOCX 定位器留待后续规范版本。

## 2. 目录与文件

```text
evals/probe/precise_clause/
  SPEC.md                         # 本规范
  schema/                         # JSON Schema，draft 2020-12
    manifest.schema.json
    corpus.schema.json
    probe_sample.schema.json
    acl_probe.schema.json
    chunk_mapping.schema.json
    candidate.schema.json         # 候选清单结构（四级许可状态）
    pii_exceptions.schema.json    # 逐命中的公开机构邮箱人工误报裁决
  tests/
    norm_v1_vectors.json          # norm-v1 正反向测试向量，M0 校验器必须全部通过
  examples/                       # 示意文件，status=draft，禁止复制进版本目录
  corpus_candidates/              # DEC-011 候选清单，按版本追加，不覆盖
  v1/                             # 第一个冻结版本，已本地冻结
    manifest.json
    corpus.json
    samples.jsonl
    review_prompt.md
    acl_probes.jsonl              # 可选
    pii_exceptions.json          # 可选；存在时必须纳入 manifest.files 与冻结哈希
    SHA256SUMS
    mappings/
      chunk_mapping.<chunker_version>.json   # 工具生成，按切分器版本
    sources/                      # 可选的本地原始 PDF 目录，永不入 Git（.gitignore 已排除）
```

- 版本目录一经冻结不可修改。任何修正创建新目录（`v2` 或 `v1.1`），`manifest.supersedes` 指向旧版本，`change_reason` 必填，且必须对全部候选完整重跑实验。
- `samples.jsonl` 与 `acl_probes.jsonl` 每行一个 canonical JSON：UTF-8、对象键排序、无多余空白、`ensure_ascii=false`，按 `sample_id`/`probe_id` 升序，文件以换行结尾。
- 原始 PDF 不进入 Git。存放位置记录在 `manifest.source_store`；若使用版本目录内的 `sources/`，该目录只存在于本地，完整性只由 `source_hash` 校验。

## 3. 语料来源与许可准入（DEC-011，ADR-0003）

### 3.1 来源白名单与排除

- 权威来源白名单：药品说明书来自 NMPA、CDE、各省药监等官方来源；临床方案来自 ClinicalTrials.gov、政府或高校试验机构公开的 protocol PDF；医学/PV 指南来自 WHO、EMA、FDA/NLM、ICH、国家监管机构及专业学会官网。
- 排除：聚合站、转载站、网盘、无法确认发布主体的文件。
- 新来源同时满足“发布主体权威、版本可追溯、原始 PDF 可定位、许可通过”即可加入，不需要修改基线。

### 3.2 四级许可状态

| 状态 | 定义 |
| --- | --- |
| `eligible` | 明确开放许可、公共领域，或条款明确允许本项目所需的保存、索引、引用和展示 |
| `research_only` | 仅允许非商业使用；不得进入生产或商业兼容验收语料 |
| `needs_review` | 公开可下载但没有明确复用授权 |
| `rejected` | 禁止复用、权利主体不明或包含无法分离的第三方内容 |

- 政府公开信息或“官方来源”本身不足以通过；“版权所有”声明的官方文件先落入 `needs_review`。
- 只有 `eligible` 可以进入探针集 v1；`corpus.json` 的 `license_status` 固定为 `eligible`。
- 这是工程准入标准，不替代法律意见；最终许可签字由决策人完成，`license_or_terms.verified_by` 记录签字者的 surrogate id。

### 3.3 候选清单

- 候选清单存放于 `corpus_candidates/`，文件名 `DEC-011-candidates-<version>.json`，结构见 `candidate.schema.json`；每轮审核产生新版本，不覆盖旧版本。
- 候选可含四种 `license_status`；`license_evidence` 为数组，每条含 `url`、`locator`、`quote`，`quote` 必须是对应 `url` 中的原文摘录，一段证据对应一个来源；每个候选自带完整证据，禁止跨候选写“Same as”或“同上”；`fetch_verified` 必须为 true。
- 官方 `.doc/.docx` 附件可保留在候选清单，但在 spec-v1 的 PDF-only 规则下不进入探针集；DOCX 与 legacy DOC 支持留待后续 ingestion 版本。
- 候选进入 `corpus.json` 前必须 `reviewer_decision=eligible`，由决策人填写 `reviewer_note`。

### 3.4 corpus.json 文档记录

- 每份文档记录 `document_key`、`title`、`doc_type`、`owner_dept`、`language`（`zh-Hans`、`zh-Hant`、`en`、`mixed`）、`source_url`、`publisher`、`license_status`、`license_or_terms`、`terms_url`、`retrieved_at`、`version_label`、`source_hash`、`byte_size`、`pages`、`pii_scan`、`notes`。
- `license_or_terms` 为结构化对象：`name_or_summary`（许可名称或条款摘要）、`permitted_scope`（须覆盖保存、索引、引用、展示）、`attribution_required` 与 `attribution_text`、`third_party_content_checked`（必须为 true）与 `third_party_note`、`verified_at`、`verified_by`。`terms_url` 必填。
- `language=zh-Hant` 的文档必须在 `notes` 标注脚本变体；它可以进入语料并计入 `drug_name_zh` 业务切片，但实验报告必须按 `zh-Hans`、`zh-Hant` 分开，繁体结果不能用于证明简体中文检索达标。
- 文件不可变：`source_hash` 变化即新文档条目，不允许原地替换。
- PII：`pii_scan` 记录方法、规则集版本、时间与结果；结果不是 `clean` 的文档不得使用。公开文档中的研究者、作者等职业信息不视为 PHI。
- 部门归属由标注者按文档用途指定并在 `notes` 说明；默认映射为说明书归 MA、方案与 SOP 归 CO、PV 类指南与 PV SOP 归 PV。
- 每份文档最多贡献 6 条样本。由此语料至少 10 份文档，每个部门至少 3 份。

### 3.5 PV 语料归入规则

- 内容必须主要涉及 AE/SAE 报告、信号管理、风险管理计划、定期安全报告或 GVP。
- 保持真实 `doc_type`：指南写 `guideline`，不得为凑数伪标为 `sop`。
- `owner_dept=PV` 表示本项目的实验权限域，不代表来源文件自身有部门限制；`notes` 必须写清归属理由。
- 至少 3 份独立文件：`document_key` 与 `source_hash` 两两不同，不得用同一文件重复登记或仅拆版本凑数。
- 已知风险：简体中文官方来源多带“版权所有”声明，在本政策下先落入 `needs_review`；每部门 15 条样本与 3 份文档的最低要求可能因此延后达成，不降低门槛。

## 4. 抽取与规范化基线

- `extraction` 由 `extractor`、`extractor_version`、`params`、`params_hash` 组成，冻结在 manifest。`params` 是实际参数对象；`params_hash = SHA-256(UTF-8 canonical_json(params))`，canonical JSON 规则与基线 3.2 相同。所有偏移量都相对该版本抽取出的“页文本”。
- `page` 为 PDF 物理页序号，从 1 起；印刷页码放在 `printed_page_label`，只作展示。
- 抽取失败、乱码或无法保留章节的页不得作为 gold 来源。
- 校验器读取页文本的本地约定：`<pages_dir>/<source_hash>/<page>.txt` 存放该页的原始抽取文本（不进入 Git），校验器自行施加 norm-v1；`pages_dir` 通过 `--pages` 传入。

### 4.1 norm-v1

按固定顺序执行，`key_text` 匹配与偏移量都在规范化后的页文本上计算：

1. Unicode NFC。不使用 NFKC，不做通用兼容分解。
2. 删除抽取伪空白：位于 CJK 与 CJK 之间、CJK 与中文/全角标点之间、标点与 CJK 之间的连续空白（含 U+3000）删除。CJK 指 U+3400–4DBF、U+4E00–9FFF、U+F900–FAFF；中文/全角标点指 U+3001–3003、U+3008–3011、U+3014–301F、U+FF01–FF0F、U+FF1A–FF20、U+FF3B–FF40、U+FF5B–FF65。
3. 全角 ASCII 映射为半角：U+FF01–FF5E 逐字映射到 U+0021–007E；U+3000 映射为 U+0020。后果：规范化文本中“，：（）”等全角标点变为 ASCII 标点，“。、《》【】”不变；展示给用户的原文不受影响。
4. `µ`（U+00B5）统一为 `μ`（U+03BC）。
5. 医学单位兼容字符只按版本化白名单 `unit-map-v1` 映射：`㎎→mg`、`㎍→μg`、`㎖→mL`、`㎏→kg`、`㎜→mm`、`㎝→cm`、`㎡→m²`、`㎕→μL`、`㎗→dL`、`℃→°C`。白名单变更即新的 normalization 版本。
6. 折叠剩余连续空白为一个半角空格，去除首尾空白。

必须保留：上下标、带圈数字与其他非白名单字符。`10⁹/L`、`CO₂`、`m²`、`①` 不得退化。不折叠大小写，不做术语替换。

`tests/norm_v1_vectors.json` 给出 fold 与 preserve 两类用例；M0 校验器中的 norm-v1 实现必须全部通过（PR-14）。

## 5. 样本结构

| 字段 | 说明 |
| --- | --- |
| `sample_id` | `pc-` 加 4 位序号，跨版本稳定，删除后不复用 |
| `query` | 用户会提出的自然问题，4 到 300 字符；规范化后不得与任一 `key_text` 相等 |
| `dept` | 请求身份所属部门：`MA`、`PV`、`CO`；spec-v1 要求与全部 gold 文档的 `owner_dept` 相同 |
| `language` | `zh`、`en`、`mixed`；带 `mixed_zh_en` 切片的样本必须为 `mixed` |
| `slices` | 六个切片标签的非空子集，允许多标签 |
| `required_gold_evidence` | 1 到 5 条 gold，见第 6 节 |
| `review` | 标注与复核记录，见第 8 节 |
| `notes` | 标注说明，可为空字符串 |

### 5.1 spec-v1.1：派生英文查询孪生样本（2026-09-20 修订）

背景：DEC-001 第一次词法对比（ADR-0002 结果回填）显示，gold 文档为英文而查询为中文的 32 条样本在任何词法候选上只有 12.5%～15.6% 的召回，因为中文查询词元不会出现在英文条款中。决策人于 2026-09-20 批准：词法硬门禁只对"查询语言与 gold 文档语言一致"的样本计算，跨语言样本作为独立切片单独报告，由后续向量阶段承担。为了在不放宽 ADR-0002 最低数量（每部门 ≥15、每切片 ≥8）的前提下得到语言一致的 PV/CO 样本，spec-v1.1 允许派生孪生样本：

- 字段 `derived_from`（可选，`pc-` 加 4 位序号）指向一条已确认的父样本；孪生样本的 `dept`、`slices` 与全部 gold（除 `gold_id` 前缀外逐字段相同）从父样本继承，`language` 固定为 `en`，只有 `query` 不同（英文提问）。父样本的 gold 文档 `language` 必须为 `en`。
- 孪生样本继承 `mixed_zh_en` 等切片标签以便与父样本逐切片对比；PR-11 对 `derived_from` 非空的样本不再要求 `language=mixed`。
- manifest 必须含 `derived_samples`：规则、数量、`query_language=en`、起草者（`kind=llm`，含模型标识）与 `human_confirmation`（`pending` 或 `confirmed`，含 `annotator_id` 与 `confirmed_on`）。起草者为 LLM 时，人工标注人在确认前数据集不得冻结；`pending` 状态下的运行只能标为临时结果。
- 复核：孪生样本作为独立批次 `EN` 由 LLM 第二复核人复核，证据文件为 `run_EN.json` 与 `verdicts_EN.jsonl`；`review_evidence/` 共 10 个工件（三部门批次各两个、`EN` 两个、`resolutions.json`、`reviewer_runtime_metadata.json`）。父样本批次仍按部门划分，只含非派生样本。
- 门禁作用域（ADR-0002 修订）：语言一致 = gold 文档为 `en` 且样本 `language=en`，或 gold 文档为 `zh-Hans`/`zh-Hant` 且样本 `language` 为 `zh`/`mixed`；跨语言 = gold 文档为 `en` 且样本 `language` 为 `zh`/`mixed`。硬门禁与最低数量在语言一致子集内计算，跨语言子集按切片单独报告。
- 校验规则 PR-15：`derived_from` 指向存在且非派生的样本；`language=en`；`dept`、`slices`、gold 与父样本一致；父样本 gold 文档为英文；查询与父样本不同；数量与 `derived_samples.count` 一致；`spec-v1` 数据集不得含派生样本。

## 6. Gold 锚定与命中规则

- 锚定字段：`source_hash`、`version_label`、`page`、`section`、`key_text`。`evidence_span` 提供完整条款与偏移量。gold 不引用 `chunk_id`。
- `key_text` 是判定条款被召回所必需的最小连续文本，2 到 200 字符，在规范化后的 `gold.page` 页文本中必须恰好出现一次；不唯一时扩展 `key_text` 直到唯一。`key_text` 的页内位置由校验器和映射器按此唯一出现计算，不单独存储。
- 2026-09-19 人工确认 P1：最小性以同时保留对象与约束的命中含义为前提，不以孤立数字、编号或动词作为更短锚点。此语义规则由人工与 LLM 复核，机械唯一性不能代替它。
- `evidence_span.text` 是完整条款；`char_start`/`char_end` 为左闭右开区间，相对规范化页文本，且 `text` 必须包含 `key_text`。
- chunk 的来源片段：chunk 由一个或多个 `(page, char_start, char_end)` 片段构成，偏移量相对同一 `extraction_version` 与 norm-v1 下的页文本。这是 M1 切分器的输出契约，对应基线 5.1 “chunk 保留页码与字符区间”。
- 命中规则：一个 chunk 命中某条 gold，当且仅当同时满足：`source_hash` 与 `version_label` 相同；chunk 具有 `page == gold.page` 的来源片段；该页片段的区间覆盖 `key_text` 在该页的唯一位置。不得仅凭 chunk 全文包含 `key_text` 判定命中，跨页 chunk 也必须以 `gold.page` 上的片段覆盖为准。
- 映射文件 `mappings/chunk_mapping.<chunker_version>.json` 由工具生成，禁止手改。某条 gold 在该切分器下没有任何 chunk 满足命中规则时记为 `unmappable`：对该切分器计为 miss，并在报告中单独列为切分缺陷。
- `recall@K(query) = 命中的 gold 数 / required_gold_evidence 数`，探针集指标为全部 query 的宏平均。
- `extraction_version` 或 normalization 版本变更时，按 `key_text` 在页内重新定位；唯一性不满足即视为标注失效，必须升版。

## 7. 切片与部门

| 切片 | 定义 |
| --- | --- |
| `drug_name_zh` | 召回依赖中文通用名或商品名的精确匹配，含易混淆名 |
| `dose_unit` | 条款含数值加单位（mg、g、mL、μg、IU、%）或频次表达 |
| `negation` | 条款含禁用、不得、不推荐、无需、除外等否定或限制表达，命中必须保留否定语义 |
| `time_window` | 条款含时间窗，如“14 天内”“给药后 24 小时”“访视窗 ±3 天” |
| `protocol_id` | 召回依赖方案编号、注册号、SOP 编号或版本号的精确匹配 |
| `mixed_zh_en` | query 或 key_text 含英文术语/缩写；仅 evidence_span 其他位置出现的英文不计，单独单位符号不计英文术语（2026-09-19 人工确认 P2） |

2026-09-19 人工确认 P2/P3：dose_unit、negation、time_window 按 evidence_span 判定，span 围绕一个条款保留必要限定条件；给药频次归 dose_unit，单独半衰期数值不归 time_window。drug_name_zh、protocol_id 按 query 的检索依赖判定；编号仅为答案时不计 protocol_id，许可证样本改为 query 含编号的反向检索。确认依据与旧提示复核的失效边界见[续接记录 24](../../../docs/reviews/2026-09-19-implementation-24-probe-review-continuation.md)。数量门槛不变。

最低数量：样本总数不少于 60，目标 72；六个切片各不少于 8；MA、PV、CO 各不少于 15；gold 来源文档为 `zh-Hans` 的样本不少于 8（硬门禁，`manifest.minimums.zh_hans_samples` 固定为 8）。多标签样本在每个所属切片各计一次。`manifest.minimums.per_slice` 固定为 8。`manifest.counts.per_language` 按样本 gold 文档的 `language` 统计（gold 跨语言时记为 `mixed`）。

## 8. 标注与复核

- `annotator` 为人工，记录 surrogate id，不记录真实姓名。
- `second_reviewer` 为 LLM，必须记录 `model`、`model_version` 和 `prompt_hash`。复核 prompt 原文保存在版本目录 `review_prompt.md`：UTF-8、LF、无 BOM、文件末尾有换行；`prompt_hash` 为该文件原始字节的 SHA-256。
- 服务仅报告模型别名、未暴露后端版本时，`model_version` 使用明确的运行身份描述 `service-alias:<model>;backend-version:not-exposed`；它不是固定快照版本，也不保证再次调用同一后端。CLI 版本单独记录，不能冒充模型版本。该描述只允许由已验证的真实运行证据生成，不接受任意命令行版本字符串。
- 使用上述描述时，manifest 必须包含 `review_provenance`：复核者 ID、`version_source=service_alias`、`backend_model_version=null`、明确的复现限制和 8 个证据文件的相对路径/SHA-256。证据复制进版本目录 `review_evidence/`，包括三个批次的 run、三个 verdict JSONL、精确绑定的 resolutions 和派生的 runtime metadata，不复制含完整页文本的输入包。PR-09 校验实际文件哈希、模型/强度、全部实际样本覆盖、输入/组合提示/判定及裁决绑定；最新引用必须指向最后一次追加的成功调用，不能隐藏较新的争议。页文本缺失在 draft 报警告，frozen 由 PR-05 拒绝。
- manifest 的 `reviewers` 恰好一个 human annotator 和一个 LLM second reviewer；每条样本的 `review` 引用的 id、model、model_version、prompt_hash 必须与 manifest 一致（PR-09）。
- 复核内容：query 自然性、切片标签正确性、`key_text` 最小且页内唯一、`evidence_span` 确实回答 query、部门归属。
- `review.status` 为 `agreed` 或 `disputed_resolved`；后者必须由人工裁决并填写 `resolution_note`。
- 如实标注：`manifest.review_policy` 固定为 `human_reviewers=1`、`llm_reviewers=1`，并声明这不等同于两名独立人工复核。任何报告引用本集时沿用该表述。并入主评测集后，按基线 5.9 补第二人工复核。

### 8.1 spec-v1.1：固定模型标识的 LLM 复核人（2026-09-20 修订）

- 当复核 CLI 回显固定的模型标识（如 Claude Code CLI 的 `modelUsage` 键）时，`model_version` 直接使用该标识，manifest `review_provenance.version_source = pinned_model_id`，`backend_model_version` 等于该标识，`reasoning_effort` 记录实际请求的强度；运行元数据须写明"标识由 CLI 回显、CLI 版本单独记录、服务端权重不保证永不变化"。校验器按声明的强度而不是固定的 `high` 校验各批次与运行元数据的一致性。
- 复核人更换（例如 v2 由 gpt-6-astra 改为 claude-opus-5）时，同一版本内所有样本必须由同一复核人复核；不得在一个版本内混用两个 LLM 复核人。复核人不得是该版本任何样本的起草者。

## 9. 冻结流程

1. 校验器按第 10 节全部规则通过。
2. 生成 `SHA256SUMS`，覆盖 `corpus.json`、`samples.jsonl`、`review_prompt.md` 与（若存在）`acl_probes.jsonl`、`pii_exceptions.json`，行按路径排序，格式与 `shasum -a 256 -c` 兼容；`manifest.files` 的路径与哈希必须与之完全一致。
3. `dataset_hash = SHA-256(SHA256SUMS 文件字节)`，写入 `manifest.dataset_hash`。`manifest.json` 自身不进入 `SHA256SUMS`，其 SHA-256 记录在 ADR 回填与实验运行清单中。`review_evidence/` 的 8 个运行证据文件通过 `manifest.review_provenance.artifacts` 的逐文件哈希传递绑定；不改变 dataset_hash 公式。完整复现必须同时校验 dataset_hash 与外部记录的 manifest SHA-256。
4. `manifest.status` 改为 `frozen`，填写 `frozen_at`。
5. 提交 Git；将提交哈希、`dataset_version`、`dataset_hash` 回填 ADR-0002。
6. 之后任何改动都产生新版本目录。

## 10. 校验规则

校验器实现为 `python -m medops.evals.probe <version_dir> --mode draft|frozen [--pages DIR]`（`src/medops/evals/probe/`）；`draft` 模式把数量不足与页文本缺失记为警告，`frozen` 模式全部为错误并执行 PR-10 完整性检查。规则编号在报告中引用：

| 规则 | 内容 |
| --- | --- |
| PR-01 | `manifest.json`、`corpus.json`、每行样本、ACL 探针和映射文件通过对应 JSON Schema；JSONL 为 UTF-8 无 BOM、LF、无空行、末尾换行且每行 canonical JSON；`corpus.dataset_version` 等于 manifest；`source_hash` 与 `document_key` 各自唯一；解析失败以带文件与行号的 Finding 报告 |
| PR-02 | `sample_id` 唯一且升序；`gold_id` 以所属 `sample_id` 为前缀且样本内唯一；`acl_probes.jsonl` 的 `probe_id` 唯一且升序，`derived_from_sample` 必须存在 |
| PR-03 | 样本总数不少于 60；六个切片各不少于 8；三个部门各不少于 15；gold 来源为 `zh-Hans` 的样本不少于 8；`manifest.counts`（含 `per_language`）与实际一致 |
| PR-04 | 每条 gold 的 `source_hash` 存在于 `corpus.json`，`version_label` 与文档一致，`page` 不超过文档 `pages`；单份文档样本数不超过 6；文档总数不少于 10 且每部门不少于 3 |
| PR-05 | 不依赖页文本的检查始终执行：`key_text` 与 `evidence_span.text` 为 norm-v1 形式，`text` 包含 `key_text`，`char_end - char_start` 等于 `text` 长度；提供页文本时，`key_text` 在 `gold.page` 页文本中出现次数等于 1，且页文本对应区间等于 `text`；缺页文本在 draft 为警告、frozen 为错误 |
| PR-06 | 样本 `dept` 等于其全部 gold 文档的 `owner_dept` |
| PR-07 | `query`、`key_text`、`evidence_span.text`、`notes` 的 PII 命中默认拒绝；只允许下述逐命中人工裁决的机构邮箱例外；规则集版本记录在 manifest，例外文件有完整性绑定 |
| PR-08 | 规范化后的 `query` 两两不同，且不等于全集中任一 `key_text`（含其他样本的） |
| PR-09 | `manifest.reviewers` 恰好一个 human annotator 与一个 LLM second reviewer，并与 `review_policy` 一致；每条样本的 `review` 引用与 manifest 一致；`prompt_hash` 等于 `review_prompt.md` 原始字节的 SHA-256；`disputed_resolved` 必有 `resolution_note`。service-alias/未暴露后端描述还必须满足第 8 节的证据文件与逐条绑定校验 |
| PR-10 | 冻结版本：`status=frozen`、`frozen_at` 非空；`SHA256SUMS` 逐行为 `<64 hex>  <path>`，路径不重复、按路径排序、恰为版本目录内的清单文件、末尾换行；`manifest.files` 与之路径和哈希完全一致；各文件哈希重算一致；`dataset_hash` 等于 `SHA256SUMS` 字节的 SHA-256；目录内无 `*.example.*` 文件 |
| PR-11 | 带 `mixed_zh_en` 的样本 `language=mixed`；`language=en` 的样本不得带 `drug_name_zh` |
| PR-12 | 映射文件的 `dataset_version` 与 `dataset_hash` 等于当前版本，`extraction`（extractor、extractor_version、params_hash）与 `normalization` 等于 manifest；每条 gold 恰有一条映射记录 |
| PR-13 | `corpus.json` 中每份文档 `license_status=eligible`，`license_or_terms` 各字段齐全且 `third_party_content_checked=true`，`verified_at` 不晚于 `frozen_at`，`terms_url`、`source_url` 齐全，`pii_scan.status=clean`；`owner_dept=PV` 的文档不少于 3 份且 `document_key`、`source_hash` 两两不同 |
| PR-14 | 校验器自检：其 norm-v1 实现通过 `tests/norm_v1_vectors.json` 全部 fold 与 preserve 用例；`extraction.params_hash` 与 `params` 重算一致 |
| PR-15 | 派生孪生样本（spec-v1.1，见 5.1）：引用、继承字段、英文 gold 文档、查询不同、数量与 manifest 一致 |

PR-07 机构邮箱误报裁决（2026-09-20）：依据[实现记录 21](../../../docs/reviews/2026-09-17-implementation-21-pii-release-withdrawn-status.md)的人工决定，公开机构功能邮箱可逐命中确认为非个人数据；不修改 `pii-rules-v1`，不从样本或 corpus 的自由文本 `notes` 推断放行。

- 可选文件 `pii_exceptions.json` 遵循 `pii_exceptions.schema.json`，记录当前 `dataset_version`、`pii_ruleset_version` 与非空 `exceptions`。每条绑定 `sample_id`、`gold_id`、`source_hash`、`field`、完整字段的 UTF-8 字节 `field_sha256`、检测器的 `rule`、精确 `match` 和字段内 `char_start`/`char_end`。偏移是 Unicode code point 半开区间，不是页内偏移或 UTF-8 字节偏移。
- 仅允许 `rule=email`，且 `field` 为 gold 的 `key_text` 或 `evidence_span.text`；`query`、`notes`、身份证、手机和患者编号不开放例外。不得按域名或机构名批量放行。同一邮箱在两个字段或同一字段两个位置出现，必须分别有对应裁决。重复身份、字段哈希变化、引用错配及未消费的过期条目均为错误。
- `human_review` 必须记录 manifest 中的 human annotator id、实际裁决日期、固定决定 `public_institutional_contact`、具体理由，以及 `docs/reviews/*.md` 下人工依据文件的仓库相对路径和原始字节 SHA-256；理由不得额外引入 PII 命中。日期不得在未来或晚于冻结日期。校验器每次实际读取依据并重算哈希，文件缺失、不可读、路径逃出指定根目录或内容变化均拒绝；默认从源码仓库根解析，也可用 `--approval-records-root` 指定携带该依据的仓库根。
- draft 和 frozen 都要求例外文件与 `manifest.files` 双向对应、哈希相符；冻结时还必须进入 `SHA256SUMS`，从而进入 `dataset_hash`。人工依据文件的哈希由例外文件传递绑定；修改依据会使已有例外失效。文件加载拒绝重复 JSON 属性，所有对象拒绝额外字段。
- 该机制验证具体命中与裁决记录的完整性；是否确为非个人机构联系信息仍须人工判断，不能由“存在理由文本”自动推断批准。

## 11. ACL 探针

- 用于 ADR-0002 的零越权测试。`acl_probes.jsonl` 为可选文件；缺省时由测试按规则派生：对每条样本，用另外两个部门的身份提交相同 `query`，禁止返回该样本 gold 所属文档的任何 chunk、分数、计数或元数据。
- 显式文件用于补充“相同或近似词条分布在三个部门”的对照样本，结构见 `acl_probe.schema.json`。

## 12. 与基线和 ADR 的对应

| 本规范 | 对应条款 |
| --- | --- |
| 第 1 节切片门禁作用域 | 基线 5.8（仅 M4 Loop 回放）；ADR-0002 硬门禁 |
| 第 3 节来源白名单、四级许可与 PV 归入 | 基线 `INV-DATA-01`、M5“许可清楚的公开文档”、DEC-011、ADR-0003 |
| 第 4 节抽取与规范化 | 基线 3.2 canonical JSON、3.6 版本进入 `retrieval_version`；ADR-0002 复现条件 |
| 第 6 节命中规则与 chunk 片段 | 基线 5.1 chunk 字符区间、5.9 `Lexical Recall@20`；ADR-0002 硬门禁 1、2 |
| 第 8 节复核 | ADR-0002 实验输入（人工标注 + LLM 复核）；基线 5.9 主集复核政策 |
| 第 9 节冻结 | ADR-0002 `dataset_version` 与哈希；M1 Checklist 第 1 项 |
| 第 11 节 ACL 探针 | 基线 3.7；ADR-0002 RLS 零越权测试 |
