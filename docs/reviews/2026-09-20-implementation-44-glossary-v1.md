# 实现记录 44：DEC-005 术语表构建工具与初始术语表 `glossary-20260920-f569611ab3dd`

日期：2026-09-20。承接记录 41 阶段 4（ADR-0008）。

## 1. 编码前记录

- 来源与许可按 ADR-0008：TFDA「全部藥品許可證資料集」（data.fda.gov.tw，政府資料開放授權條款第1版，署名衛生福利部食品藥物管理署）与语料文档内定义的缩写；DrugBank Open Data 待决策人下载后加入。
- 收录规则（初始范围 = 当前语料）：TFDA 行只有在其**许可证字号**（去空白后，如 `衛署藥製字第048564號`）出现在语料页文本中时才收录——第一版按"品名出现在页文本"筛选把「葡萄糖」「注射劑」「胃液」这类恰为许可证品名的通名收进来（17 个"品名"、34 条），已弃用；改为许可证锚定后得到 6 个许可证、12 条（中文品名 ↔ 英文品名/主成分双向）。缩写只有在缩写与展开同页共现时才收录，页码作为证据；未验证者列入 provenance 的 rejected（本次 IB、NSAID、DLP）。
- 版本：`glossary-<日期>-<entries canonical JSON sha256 前 12 位>`；provenance 记录快照 URL、SHA-256、行数、许可、每条证据（document_key + 页码），不含页文本。
- 术语表尚未进入任何生产配置：按 INV-EVAL-02，改写器启用术语表前需要离线评测（改写前后召回对比）。

## 2. 实现

- [build_glossary.py](../../evals/glossary/tools/build_glossary.py)：读取 TFDA CSV 压缩包、按 norm-v1 规范化、一次扫描页文本建立许可证字号索引、双向品名条目（同义词去重、≤5）、缩写共现验证、去重后经 `GlossaryEntry`/`Glossary` 校验、内容寻址版本、拒绝覆盖已有版本。
- [abbreviations_curated.json](../../evals/glossary/sources/abbreviations_curated.json)：40 条候选缩写（来自对语料页文本的定义抽取，人工筛选）。
- 产物：[glossary-20260920-f569611ab3dd.json](../../evals/glossary/glossary-20260920-f569611ab3dd.json)（49 条：12 品名、37 缩写）与 provenance（TFDA 快照 sha256 `70ccaece…`，72,057 行，6 个许可证命中）。TFDA 快照文件（10 MB）不入库，按 URL + sha256 可复现。

## 3. 测试

- 单元 [test_build_glossary.py](../../tests/unit/evals/test_build_glossary.py)（3）：许可证锚定（品名在页但许可证不在 → 排除）、同义词去重与上限、双向条目与证据；缩写同页共现、整词匹配（`RAC` 不匹配 `PRAC`）；端到端构建产物可被运行时 `load_glossary` 加载、版本前缀正确、provenance 含许可与快照哈希且不含页文本、拒绝覆盖。
- 覆盖度（离线、诊断）：探针 v2 的 107 条查询中 69 条会得到术语追加（最多为 ICH → "International Council for Harmonisation" 36 次、GVP 14 次、异嘌呤醇 2 次）；效果评测另行安排。

## 4. 自审（基线 §9）

1. 需求：ADR-0008 的来源、许可、版本化、证据逐条落实。
2. 逻辑：许可证锚定消除通名误收；共现验证防止无据缩写。
3. 安全：产物只含名称与页码；快照哈希固定。
4. 契约：产物即运行时 `Glossary` 结构。
5. 测试：新增 3 单元。
6. 可观测：provenance 完整。
7. 简洁性：一个工具、一个人工候选表。
8. 验证：数字来自构建输出。
9. Checklist：M1-12 仍为部分（分词词典未变，术语表已有初版；进入生产前需评测）。

## 5. 下一步

术语表启用评测（改写前后 A2/B2/向量召回对比）；DrugBank Open Data 交付后扩展英文通用名。
