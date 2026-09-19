# 实现记录 11：语料候选清单 v0.2（新来源核验与登记）

日期：2026-09-11。范围：对决策人提供的来源检索报告（临时目录 `SOURCE_RESEARCH_2026-09-11.md`，8 份 PDF + 1 份 TFDA 数据集快照）做独立复核，并按 ADR-0003 追加候选清单 v0.2。未修改冻结基线、ADR、Schema 或校验器；未签任何许可；未提交 Git；第三方 PDF 与快照原件未放入仓库。

## 1. 交付

| 文件 | 内容 |
| --- | --- |
| [DEC-011-candidates-v0.2.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.2.json) / [.md](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.2.md) | 33 条：cand-0001～0025 逐字承接 v0.1（程序比对相等），cand-0026～0033 新增；新增条目 `reviewer_decision` 全部为空 |
| [test_candidate_lists.py](../../tests/unit/evals/test_candidate_lists.py) | 每个候选清单文件对 `candidate.schema.json` 校验；编号自 cand-0001 连续；后续版本不得改动或丢弃既有编号的标题 |
| [DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md) §3.2、C-04；[TASK_KNOWLEDGE_MAP.md](../TASK_KNOWLEDGE_MAP.md) C-04 | 数字更新为 v0.2 口径 |

v0.1 文件未改动。Markdown 由脚本从 JSON 渲染，渲染器先在 v0.1 上验证：从 v0.1 JSON 渲染结果与仓库内 v0.1 Markdown 逐字节相同。

## 2. 独立复核实测

| 检查 | 结果 |
| --- | --- |
| 8 份 PDF + zip 的 SHA-256 与字节数 | 与报告表 5 全部一致；zip 内 `39_5.json` sha256 `1d27fcc3…4378` 一致 |
| 原始 URL 可达性 | 8 个 PDF URL HEAD 200，`Content-Length` 与本地字节数逐一相等；5 个 TFDA `im_detail_1` 落地页 200 且含许可证字号与品名 |
| 许可页原文 | 两份 MedDRA 指南物理第 1 页、ICH E8(R1) 物理第 3 页，用 pypdf 6.15.0 抽取；ICH 公共许可条款（承认版权、标明修改、不暗示背书、徽标与第三方内容除外）逐字入证据 `quote` |
| 许可页以外的权利提示 | 三份指南正文再扫描 版权/授权/不得/商标/®/第三方/copyright/licen 等词：命中均为业务文本（如「用户不得对 MedDRA 进行临时的结构改动」「support licensing」），无附加限制 |
| MedDRA 发布主体与版本 | 站点为 Angular 客户端渲染；经站点 API `admin.meddra.org/api/guidances-page` 的 Chinese 分组核对，两份 PDF 的官方链接与字节数（927064 / 979986）与本地一致；报告中 R-02 的 `alt.meddra.org` 链接与官方 `admin.meddra.org` 同名文件 sha256 相同，候选 `pdf_url` 采用官方链接 |
| TFDA 快照逐字匹配 | 5 个 `pdf_url` 各恰好匹配 1 条记录（序号 69 / 4778 / 2927 / 375 / 2933，与报告一致）；29,860 条记录中 16,915 条为 `/insert/pdfcasefile/` 形式 |
| TFDA PDF 文本层扫描 | 美洛醣 2 页 7548 字符，唯一命中「禁止合併服用」为临床文本；安通脈 13 页 33443 字符，唯一命中 ® 为 Maalox TC® 第三方产品引用；吉福坦 2 页 13244 字符零命中；艾摩喜林 1 页 695 字符，末尾 U+24B8「Ⓒ」；血脂安 9 页每页 0 字符 |
| 同名不同规格 | 美洛醣 500mg（衛署藥製字第034549號）、吉福坦 50mg（衛部藥輸字第026321號）在快照中各有独立记录且指向不同上传 PDF；本版只登记匹配记录，各按一份文档 |
| 既有页面证据复核 | data.gov.tw/license、fda.gov.tw 開放宣告与著作權聲明、mcp.fda.gov.tw 页脚、数据集 9117 元数据：2026-09-11 curl 复核关键句仍在；fda.gov.tw 開放宣告另补「本授權範圍…不及於…商標、及機關標誌」入证据。ICH 站点 Legal Mentions 节点接口本日只返回元数据，沿用 2026-09-09 取得的正文并在 locator 注明，以文内 Legal notice 为主证据 |

`make check`：仓库外导入通过，ruff 通过，mypy 35 个源文件通过，pytest **213 passed**（新增 4 个），Schema 导出无漂移。`git diff --check`、新文件 UTF-8/LF/结尾换行、相对链接、代码围栏配对均通过。

## 3. 预判结果（不是审批）

| 部门 | eligible | research_only | needs_review | rejected | 合计 |
| --- | --- | --- | --- | --- | --- |
| MA | 3 | 0 | 10 | 0 | 13 |
| PV | 8 | 1 | 1 | 0 | 10 |
| CO | 3 | 0 | 4 | 3 | 10 |
| 合计 | 14 | 1 | 15 | 3 | 33 |

eligible 按语言：en 8、zh-Hans 2、zh-Hant 4。`reviewer_decision=eligible` 仍为 0。若决策人签字通过 cand-0026～0031 六份，探针集 v1 的三项门禁（MA 0 份、CO 不足 3 份、zh-Hans 0）在文档层面都有了达标路径，但样本层面的 zh-Hans ≥ 8、每部门 15 条等仍需标注后才能证明。

预判依据：

- cand-0026/0027/0028 与 cand-0017（ICH E6(R3)，v0.1 预判 eligible）同类：文内 ICH 公共许可原文。
- cand-0029～0031 按 ADR-0003 决策记录 1 的四项条件：(1) 同日快照逐字出现、(2) 快照哈希/日期/字段记录、(3) 文本层无附加限制声明，均通过；(4) 署名与不主张商标权在入库 `license_or_terms` 落实。
- cand-0032 条件 (3) 不通过（Ⓒ）；cand-0033 条件 (3) 无法验证（扫描件）；按决策 1 保持 needs_review。

## 4. 需要决策人决定（本轮不代签）

1. cand-0026、0027、0028 的许可签字：ICH 公共许可要求承认 ICH 版权、标明改动、不暗示背书、排除徽标与第三方内容。需确认项目的存储、索引、引用、展示方式能满足这些条件后填写 `reviewer_decision` 与 `reviewer_note`。
2. cand-0029～0031 两个决策 1 未明示的点：(a) 仿單正文由 MAH 撰写，是否视为在数据集 9117 的 OGDL 覆盖范围内；(b) 快照 zip 成员时间戳为 2026-09-10 10:02，下载日期 2026-09-11 与 PDF 同日，「同日快照」按下载日理解是否成立。
3. 图像层视觉核查与现行性：五份 TFDA 的图像层未做视觉版权检查；仿單版本（安通脈 2014/11/05、吉福坦 V2.01_20190124、美洛醣与艾摩喜林无版本行）与许可证现行状态未向主管机关记录核对。入 corpus 时 `version_label`、生效时间由谁核对、以什么记录为准。
4. cand-0032（Ⓒ）与 cand-0033（扫描件）是否进一步处理（人工看图 / OCR / 向权利人求证），还是本轮放弃。
5. 抽取工具选型：本轮页数、字符数与许可页原文用 pypdf 6.15.0 在会话临时环境抽取，未进入仓库依赖锁。M1 正式抽取（`<pages>/<source_hash>/<page>.txt`）需要选定 PDF 抽取库并进入 `requirements.lock`，属于选型，需批准。

## 5. Codex 审核焦点

- v0.2 中 cand-0001～0025 是否与 v0.1 逐字相同（程序比对为相等）；新增 8 条的 `license_evidence` 每条 url/locator/quote 是否一一对应、无跨候选「同上」。
- ICH 公共许可原文摘录是否忠实（可对照 PDF 物理页）；MedDRA 许可是否被误扩到术语库/SMQ 数据集（记录已明确不覆盖）。
- TFDA 条件 (3) 的判断是否只基于文本层且已如实标注；Ⓒ 与扫描件是否被正确保持 needs_review。
- 测试 `test_later_versions_keep_earlier_ids` 的口径：只约束既有编号的标题不变，允许后续版本更新 `reviewer_decision`；是否需要更严的字段冻结。
- 路线图与知识图数字是否与 v0.2 一致（33 / 14 / MA 3 PV 8 CO 3 / zh-Hans 2）。

## 6. 自审（基线 §9）

- 未改冻结契约：基线、ADR-0003、`candidate.schema.json`、SPEC 均未改动；新增文件符合 SPEC §3.3「按版本追加，不覆盖旧版本」。
- 未越权：所有 `reviewer_decision` 为空；未把预判写成审批；报告与原件留在临时目录。
- 边界如实：文本层扫描 ≠ 图像层核查；可抽取 ≠ 抽取质量合格；URL HEAD 一致 ≠ 版本现行；MedDRA 指南许可 ≠ DEC-005 术语源授权。
- 测试最小：一个数据一致性测试文件，不新增校验器分支或工具。
- 未做：真实语料抽取、gold 标注、冻结校验、检索实验、远端 CI。
