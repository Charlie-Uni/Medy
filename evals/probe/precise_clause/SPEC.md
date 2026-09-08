# 精确条款探针集冻结规范（precise_clause）

> - 规范版本：spec-v1（2026-09-08 就地修订；修订时尚无冻结数据集或下游引用）
> - 日期：2026-09-08
> - 依据：[ADR-0002](../../../docs/adr/ADR-0002-lexical-retrieval-selection.md)、[工程基线](../../../docs/ENGINEERING_BASELINE.md) 3.2、3.6、3.7、5.1、5.8、5.9 与 M1 Checklist
> - 载体：本规范与 `schema/` 下的 JSON Schema（draft 2020-12）。Pydantic 模型与校验器随 M0 生成，以 JSON Schema 为准；两者冲突时以本规范文字为准并修正 Schema
> - 数据状态：尚无冻结版本。`examples/` 只是示意，不是标注数据，`status` 固定为 `draft`

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
  tests/
    norm_v1_vectors.json          # norm-v1 正反向测试向量，M0 校验器必须全部通过
  examples/                       # 示意文件，status=draft，禁止复制进版本目录
  v1/                             # 第一个冻结版本，尚未创建
    manifest.json
    corpus.json
    samples.jsonl
    review_prompt.md
    acl_probes.jsonl              # 可选
    SHA256SUMS
    mappings/
      chunk_mapping.<chunker_version>.json   # 工具生成，按切分器版本
    sources/                      # 可选的本地原始 PDF 目录，永不入 Git（.gitignore 已排除）
```

- 版本目录一经冻结不可修改。任何修正创建新目录（`v2` 或 `v1.1`），`manifest.supersedes` 指向旧版本，`change_reason` 必填，且必须对全部候选完整重跑实验。
- `samples.jsonl` 与 `acl_probes.jsonl` 每行一个 canonical JSON：UTF-8、对象键排序、无多余空白、`ensure_ascii=false`，按 `sample_id`/`probe_id` 升序，文件以换行结尾。
- 原始 PDF 不进入 Git。存放位置记录在 `manifest.source_store`；若使用版本目录内的 `sources/`，该目录只存在于本地，完整性只由 `source_hash` 校验。

## 3. 语料来源规则

- 只允许公开文档：药品说明书、临床试验方案、SOP、医学指南，来源为监管机构、试验注册库、学会或机构的公开页面。
- 每份文档在 `corpus.json` 记录 `document_key`、`title`、`doc_type`、`owner_dept`、`source_url`、`publisher`、`license_or_terms`、`terms_url`、`retrieved_at`、`version_label`、`source_hash`、`byte_size`、`pages`、`pii_scan`。
- 许可不清楚的文档不得进入语料；`license_or_terms` 不允许为空或“未知”。
- 文件不可变：`source_hash` 变化即新文档条目，不允许原地替换。
- PII：`pii_scan` 记录方法、规则集版本、时间与结果；结果不是 `clean` 的文档不得使用。公开文档中的研究者、作者等职业信息不视为 PHI。
- 部门归属由标注者按文档用途指定并在 `notes` 说明；默认映射为说明书归 MA、方案与 SOP 归 CO、不良反应监测类指南与 PV SOP 归 PV。
- 每份文档最多贡献 6 条样本。由此语料至少 10 份文档，每个部门至少 3 份。
- 已知风险：PV 部门的公开语料（不良反应监测指南、PV SOP）数量有限，凑足每部门 15 条样本和 3 份文档可能困难；语料清单在冻结 v1 前按 DEC-005 确认，不足时先补语料，不降低最低数量。

## 4. 抽取与规范化基线

- `extraction` 由 `extractor`、`extractor_version`、`params`、`params_hash` 组成，冻结在 manifest。`params` 是实际参数对象；`params_hash = SHA-256(UTF-8 canonical_json(params))`，canonical JSON 规则与基线 3.2 相同。所有偏移量都相对该版本抽取出的“页文本”。
- `page` 为 PDF 物理页序号，从 1 起；印刷页码放在 `printed_page_label`，只作展示。
- 抽取失败、乱码或无法保留章节的页不得作为 gold 来源。

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

## 6. Gold 锚定与命中规则

- 锚定字段：`source_hash`、`version_label`、`page`、`section`、`key_text`。`evidence_span` 提供完整条款与偏移量。gold 不引用 `chunk_id`。
- `key_text` 是判定条款被召回所必需的最小连续文本，2 到 200 字符，在规范化后的 `gold.page` 页文本中必须恰好出现一次；不唯一时扩展 `key_text` 直到唯一。`key_text` 的页内位置由校验器和映射器按此唯一出现计算，不单独存储。
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
| `mixed_zh_en` | query 或条款中英混排，含 AE、SAE、PK、CYP3A4 等缩写或英文术语 |

最低数量：样本总数不少于 60，目标 72；六个切片各不少于 8；MA、PV、CO 各不少于 15。多标签样本在每个所属切片各计一次。`manifest.minimums.per_slice` 固定为 8。

## 8. 标注与复核

- `annotator` 为人工，记录 surrogate id，不记录真实姓名。
- `second_reviewer` 为 LLM，必须记录 `model`、`model_version` 和 `prompt_hash`。复核 prompt 原文保存在版本目录 `review_prompt.md`：UTF-8、LF、无 BOM、文件末尾有换行；`prompt_hash` 为该文件原始字节的 SHA-256。
- manifest 的 `reviewers` 恰好一个 human annotator 和一个 LLM second reviewer；每条样本的 `review` 引用的 id、model、model_version、prompt_hash 必须与 manifest 一致（PR-09）。
- 复核内容：query 自然性、切片标签正确性、`key_text` 最小且页内唯一、`evidence_span` 确实回答 query、部门归属。
- `review.status` 为 `agreed` 或 `disputed_resolved`；后者必须由人工裁决并填写 `resolution_note`。
- 如实标注：`manifest.review_policy` 固定为 `human_reviewers=1`、`llm_reviewers=1`，并声明这不等同于两名独立人工复核。任何报告引用本集时沿用该表述。并入主评测集后，按基线 5.9 补第二人工复核。

## 9. 冻结流程

1. 校验器按第 10 节全部规则通过。
2. 生成 `SHA256SUMS`，覆盖 `corpus.json`、`samples.jsonl`、`review_prompt.md` 与（若存在）`acl_probes.jsonl`，行按路径排序，格式与 `shasum -a 256 -c` 兼容；`manifest.files` 的路径与哈希必须与之完全一致。
3. `dataset_hash = SHA-256(SHA256SUMS 文件字节)`，写入 `manifest.dataset_hash`。`manifest.json` 自身不进入 `SHA256SUMS`，其 SHA-256 记录在 ADR 回填与实验运行清单中。
4. `manifest.status` 改为 `frozen`，填写 `frozen_at`。
5. 提交 Git；将提交哈希、`dataset_version`、`dataset_hash` 回填 ADR-0002。
6. 之后任何改动都产生新版本目录。

## 10. 校验规则

校验器随 M0 实现，规则编号在报告中引用：

| 规则 | 内容 |
| --- | --- |
| PR-01 | `manifest.json`、`corpus.json`、每行样本、ACL 探针和映射文件通过对应 JSON Schema |
| PR-02 | `sample_id` 唯一且升序；`gold_id` 以所属 `sample_id` 为前缀且样本内唯一 |
| PR-03 | 样本总数不少于 60；六个切片各不少于 8；三个部门各不少于 15；`manifest.counts` 与实际一致 |
| PR-04 | 每条 gold 的 `source_hash` 存在于 `corpus.json`；单份文档样本数不超过 6；文档总数不少于 10 且每部门不少于 3 |
| PR-05 | 在 `extraction` 与 norm-v1 下，`key_text` 在 `gold.page` 页文本中出现次数等于 1；`evidence_span.text` 包含 `key_text`，`char_end - char_start` 等于 `text` 长度，且页文本对应区间等于 `text` |
| PR-06 | 样本 `dept` 等于其全部 gold 文档的 `owner_dept` |
| PR-07 | `query`、`key_text`、`evidence_span.text`、`notes` 不命中 PII 规则集；规则集版本记录在 manifest |
| PR-08 | 规范化后的 `query` 两两不同，且不等于任一 `key_text` |
| PR-09 | `manifest.reviewers` 恰好一个 human annotator 与一个 LLM second reviewer，并与 `review_policy` 一致；每条样本的 `review` 引用与 manifest 一致；`prompt_hash` 等于 `review_prompt.md` 原始字节的 SHA-256；`disputed_resolved` 必有 `resolution_note` |
| PR-10 | 冻结版本：`status=frozen`、`frozen_at` 非空、`manifest.files` 与 `SHA256SUMS` 的路径和哈希完全一致、`SHA256SUMS` 校验通过、`dataset_hash` 与重算一致、目录内无 `*.example.*` 文件 |
| PR-11 | 带 `mixed_zh_en` 的样本 `language=mixed`；`language=en` 的样本不得带 `drug_name_zh` |
| PR-12 | 映射文件的 `dataset_version` 与 `dataset_hash` 等于当前版本；每条 gold 恰有一条映射记录 |
| PR-13 | `corpus.json` 中每份文档的 `license_or_terms`、`source_url`、`pii_scan.status=clean` 齐全 |
| PR-14 | 校验器自检：其 norm-v1 实现通过 `tests/norm_v1_vectors.json` 全部 fold 与 preserve 用例；`extraction.params_hash` 与 `params` 重算一致 |

## 11. ACL 探针

- 用于 ADR-0002 的零越权测试。`acl_probes.jsonl` 为可选文件；缺省时由测试按规则派生：对每条样本，用另外两个部门的身份提交相同 `query`，禁止返回该样本 gold 所属文档的任何 chunk、分数、计数或元数据。
- 显式文件用于补充“相同或近似词条分布在三个部门”的对照样本，结构见 `acl_probe.schema.json`。

## 12. 与基线和 ADR 的对应

| 本规范 | 对应条款 |
| --- | --- |
| 第 1 节切片门禁作用域 | 基线 5.8（仅 M4 Loop 回放）；ADR-0002 硬门禁 |
| 第 3 节公开语料与许可 | 基线 `INV-DATA-01`、M5“许可清楚的公开文档”、DEC-005 |
| 第 4 节抽取与规范化 | 基线 3.2 canonical JSON、3.6 版本进入 `retrieval_version`；ADR-0002 复现条件 |
| 第 6 节命中规则与 chunk 片段 | 基线 5.1 chunk 字符区间、5.9 `Lexical Recall@20`；ADR-0002 硬门禁 1、2 |
| 第 8 节复核 | ADR-0002 实验输入（人工标注 + LLM 复核）；基线 5.9 主集复核政策 |
| 第 9 节冻结 | ADR-0002 `dataset_version` 与哈希；M1 Checklist 第 1 项 |
| 第 11 节 ACL 探针 | 基线 3.7；ADR-0002 RLS 零越权测试 |
