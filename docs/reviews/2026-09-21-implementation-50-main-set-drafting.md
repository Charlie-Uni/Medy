# 实现记录 50：主评测集起草阶段——临时版决定、合成冲突 fixture、spec-m1 校验规则、LLM 起草流水线与标注表

日期：2026-09-21。决策人回复："开始 第二人工复核人暂无"。本记录登记据此执行的起草阶段：起草成本已获批（估算 40–80 美元），第二人工复核人不存在。

## 1. 决定与依据

| # | 决定 | 依据 / 说明 |
| --- | --- | --- |
| D50-1 | 主评测集首个冻结版本为 **`main-v1-provisional`**：manifest `second_human_review.status=pending`，schema 强制版本号以 `-provisional` 结尾；引用本集的报告必须标注"第二人工复核未完成" | 决策人 2026-09-21 "第二人工复核人暂无"；基线 5.9 的第二人工复核不可省略，只能如实标注。指定复核人并完成复核后再升版 `main-v1` |
| D50-2 | 探针 v2 的 107 条样本**原样并入**主集（保留 `pc-` 编号与探针复核记录），新样本用 `ms-` 编号；manifest `imported_samples` 绑定探针版本、样本文件哈希与探针复核提示哈希（PR-16） | spec-m1 §2 "有答案样本 ≥ 300（含探针 107）"；不重复复核已冻结样本，报告单列探针子集 |
| D50-3 | 起草者为 **claude-sonnet-5**（`drafter-llm-03`，Claude Code CLI、工具关闭、固定系统提示），LLM 复核人仍为 claude-opus-5 | spec-v1.1 §8.1 复核人不得是起草者；本机 CLI 2.1.79 不支持 claude-fable-5-1（需 2.1.251），未擅自升级决策人的 CLI |
| D50-4 | 冲突样本用 **5 份新文档的合成版本对**：ICH E7、E12A、E15、GVP Annex I、GVP P.I 各以同一 PDF 入库两次（`<key>--synthetic-old` 先激活、现行版 `--supersedes` + `--share-source` 入库后 `--publish` 归档旧版） | spec-m1 §5（决策人已批准合成冲突）；语料内现有文档无法回填版本链（`documents.supersedes` 为不可变身份列，且 active 文档不能 withdrawn），真实修订对的"新版"都已作为独立 family 入库，会造成重复现行文本。正文相同意味着只检验版本状态与时效过滤（INV-DATA-03），样本 `notes` 与 `conflict.synthetic=true` 如实标注 |
| D50-5 | 5 份 fixture 文档进入候选清单 **v1.0**（cand-0097…0101，`reviewer_decision=eligible`，`reviewer_note` 注明决策人授权实现方决定、可否决） | 与已签字的 ICH / EMA 同族文档同一许可依据（Legal Mentions / EMA legal notice，PDF 首页版权行已抽取记录）；结构性文件门禁与 PII 扫描通过 |
| D50-6 | `long_context` 取机械定义：任一 span > 1,500 字符或 gold 跨两页（PR-19）；`mixed_zh_en` 按 P2 机械计算；`protocol_id` 在 query 无编号模式时由工具去掉（P3），其余切片告警留给标注人 | spec-m1 §2/§3；机械规则可复核，不依赖起草者自述 |
| D50-7 | 无答案样本的 M1 判定近似：回查后无证据，或重排 top-1 分数低于阈值（默认 0.3，临时）；报告给出阈值扫描表与有答案样本的误弃权率 | spec-m1 §6（阈值待 M2 Verifier 定）；门禁 abstention accuracy ≥ 90% 在所选阈值上判定并标注临时 |

## 2. 语料与数据库（medops_v2@5432）

- 新文档 5 份（en；CO 3、PV 2），下载、pypdf 抽取（版本 6.18.1、params_hash 与探针一致）、`filecheck` 无命中、`pii-rules-v1` 无命中；[build_conflict_fixtures.py](../../evals/main_set/tools/build_conflict_fixtures.py) 生成 [DEC-011-candidates-v1.0.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.0.json)、[conflict_fixtures/corpus_fixture.json](../../evals/main_set/conflict_fixtures/corpus_fixture.json)（10 条入库记录）与 [fixtures.json](../../evals/main_set/conflict_fixtures/fixtures.json)，并把 5 条现行记录并入 [corpus.json](../../evals/main_set/corpus.json)（79 份；`build_corpus.py` 重跑时自动保留）。
- 入库与发布（actor `claude-fable-5.1`，reason 均引用本记录）：旧版 5 份 ingested → activated（effective_from 为现行版日期减 2 年）；现行版 5 份以 `--share-source`（审计 `source_share_confirmed`）+ `--supersedes` 入库 → `--publish`（同一事务归档旧版、写 outbox 事件 64–73）。库内：active 76、archived 5、draft 3（低可信仿單）、chunk 10,913（active 10,343）；生产词法索引、A2 索引重建到 10,913；bge-m3 向量补齐 1,074 个新 chunk（合计 10,913）。
- 页文本目录：`evals/main_set/pages/` 现通过符号链接覆盖探针 16 份文档，校验器与冻结工具只需一个 `--pages` 根（不入 Git）。

## 3. spec-m1 schema 与校验器

- [make_schemas.py](../../evals/main_set/tools/make_schemas.py) 从探针 schema 派生 `evals/main_set/schema/`：样本 id `^(pc|ms)-`、九个切片、`answerable` / `expected_behaviour` / `abstention`（含 `document_pages`）/ `conflict` / `drafted_by`，if-then 规则（无答案 ⇔ 无 gold、不得为孪生；冲突块 ⇔ `version_conflict` 切片）；manifest 新增 `minimums`（有答案 300、无答案 40、冲突 20、切片 20、部门 60、zh-Hans 20、zh-Hant 80、en 150、每文档 8）、`gates`、`imported_samples`、`second_human_review`（pending ⇒ 版本号 `-provisional`）、`conflict_fixtures`，复核证据批次增加 `NA`。
- [validator.py](../../src/medops/evals/probe/validator.py)：PR-03 按 spec 计数与下限（无答案按 scope 文档计语言）、PR-04 上限取 manifest、PR-06 无答案的部门校验、PR-09 并入样本按 `imported_samples` 校验，新增 PR-16（并入样本 canonical 字节一致且探针 manifest 一致）、PR-17（无答案）、PR-18（冲突 family 与 fixture 登记、gold 落在现行版、合成须写明）、PR-19（long_context 机械规则）。[review_provenance.py](../../src/medops/evals/probe/review_provenance.py)：`NA` 批次、无答案输入记录（`document_text` 由 `abstention.document_pages` 重建）、孪生 `parent_query`、并入样本不计入本版复核证据。
- 测试：[fixture_builder_main.py](../../tests/unit/evals/fixture_builder_main.py)（合成主集：探针 72 条并入 + 21 份新文档 168 条 + 88 条孪生 + 40 条无答案 + 2 个冲突 fixture，满足全部下限并冻结通过）与 [test_main_set_validator.py](../../tests/unit/evals/test_main_set_validator.py) 12 例（含 PR-16/17/18/19、上限 8、provisional 强制、探针 schema 互斥）。

## 4. 起草流水线（[evals/main_set/tools/](../../evals/main_set/tools/)）

| 工具 | 作用 |
| --- | --- |
| `draft_llm.py plan / draft / verify` | 起草计划（76 份文档、配额：新文档 4、探针文档 min(2, 8−已用)、fixture 5、短仿單 3；长文档按切片信号选页 ≤ 14 页 / 36k 字符）；每份文档一次 CLI 调用（提示 [drafting_prompt.md](../../evals/main_set/drafts/main-v1/drafting_prompt.md)，回复与调用元数据入 `raw/`，含页文本的输入包 `inputs/` 不入 Git）；`verify` 在 norm-v1 页文本中重新定位 key_text 与 span（精确或空白/引号/连字符容差）、重算偏移、核对页内唯一、机械计算 `mixed_zh_en` 与 `long_context`、附切片告警；`--mode long` 为长条款专项（span 1,500–2,000 字符，每文档至多 1 条、不超上限） |
| `draft_noanswer.py draft / verify` | 无答案样本：提示 [drafting_prompt_noanswer.md](../../evals/main_set/drafts/main-v1/drafting_prompt_noanswer.md)；`absence_terms` 在 scope 文档全部页文本中必须 0 命中，并统计语料内其他文档命中数；`nearest_clause` 重新定位供复核 |
| `backfill_query_en.py` | 为英文文档中缺少 `query_en` 的候选补英文问法（同一起草模型，调用记录入 `raw_backfill/`） |
| `make_sheets.py` | 候选 → 标注表 `samples_draft_{MA,PV,CO,EN,NA}.md/.json`；`ms-` 编号一次分配写入 `ids.json`；英文文档样本派生 EN 孪生；fixture 文档样本自动加 `version_conflict` 与 `conflict` 块；P3 机械去掉无编号的 `protocol_id` |
| `pack_review.py` / `run_review.py` | 复核输入包（与 `review_provenance._current_records` 同形）与固定模型复核运行（复用 v2 的提示拼装、分块证据与断点续跑；`NA` 批次四项判定） |
| `assemble.py` / `freeze.py` | 装配 `main-v1-provisional` 目录（并入探针 v2、复核证据 12 件、manifest）与冻结（主集 schema、单一页文本根） |
| `e2e_run.py`（扩展） | `answerable=false` 不进 Recall 分母；弃权规则与阈值扫描；冲突子集（现行版被引用 ∧ 历史版未进 top-5）；探针 / 新增子集分报；门禁增加 abstention 与冲突检查；provisional 数据集在报告中标注 |

## 5. 起草结果

### 5.1 数量与费用

| 项 | 数值 |
| --- | ---: |
| 起草调用 | 主起草 76 份文档（1 次因 CLI 挂起超时后重跑）、长条款专项 50 份、无答案 76 份、query_en 补齐 1 次；合计费用 **61.07 美元**（主 28.13、长 20.76、无答案 12.14、补齐 0.04） |
| 有答案候选 | 386 条（主 369 锚定成功 / 17 拒绝；长条款 27 锚定 / 10 拒绝，其中 17 条 span > 1,500 入选）；入选非派生 **287** 条（MA 83、PV 120、CO 84，含合成冲突 26、长条款 19）；1 条因 query 含机构邮箱剔除（PR-07） |
| 英文孪生 | **174** 条（全部英文文档样本；11 条 query_en 由补齐调用补足） |
| 无答案候选 | 152 条；102 条通过缺席核查（50 条 absence_terms 在文档中出现而拒绝）；入选 **63** 条（MA 24、PV 23、CO 16） |
| 并入探针后合计 | 样本 **631**（有答案 568、无答案 63、冲突 52、孪生 206、并入 107）；部门 MA 137 / PV 282 / CO 212；gold 语言 zh-Hant 143 / zh-Hans 30 / en 458；切片 dose_unit 82、drug_name_zh 82、negation 286、time_window 122、protocol_id 113、mixed_zh_en 582、version_conflict 52、long_context 35、no_answer 63；每文档非派生 ≤ 8；spec-m1 全部下限满足 |

标注表与规则见 [drafts/main-v1/README.md](../../evals/main_set/drafts/main-v1/README.md)；机械告警（切片模式不匹配等）保留在表的「工具提示」列供标注人裁定。

## 6. 测试与门禁

`env -u DEBUG -u PYTHONPATH make check`：退出码 0，**892 passed**（校验器扩展、复核证据扩展、e2e 扩展与新 fixture 测试均在内）。

## 7. 自审（§9）

- 需求：spec-m1 §2–§8 的每个要素（无答案、冲突、长条款、并入探针、临时版、批次）都有 schema 字段、校验规则与测试；决策人两条回复逐字落实。
- 逻辑：机械可复核优先——锚定、唯一性、缺席核查、切片机械项由工具做，语义项留给标注人与固定模型复核人；起草者与复核人分离。
- 安全：页文本、输入包、PDF 不入 Git；DSN 不出现在任何输出；入库与发布全部经审计触发器；fixture 文档许可依据逐条留档且可否决。
- 测试：新增 12 例主集校验测试 + 2 例 e2e 测试；`make check` 通过。
- Checklist：M1-20 由待做改为**部分**（语料、规范、schema、校验器、起草与标注表就绪；人工确认、LLM 复核与冻结未完成）；加权 P0 进度 32.9% → **33.5%**（26.5/79）。

## 8. 下一步

annotator-01 逐条确认五张标注表 → 按改动重算偏移 → `pack_review.py` + `run_review.py`（claude-opus-5）→ 争议裁决表 → `assemble.py` → `freeze.py`（`main-v1-provisional`）→ chunk 映射 → `e2e_run.py`（A2+V，重排）判定 M1-21（临时结论）。

## 9. 补记（2026-09-21 晚）：外部审校写回

决策人提交了三份用 ChatGPT 生成的逐条审校（MA 83、PV 120、EN 174；存于 `evals/main_set/drafts/main-v1/external_review/`，SHA-256 见 git），要求"先把这三个文件的修改读取一下"。处理口径：

1. 审校文件是 annotator-01 提交的编辑稿，不是人工签署；写回后的样本仍处于"待 annotator-01 确认"状态（`_draft.decision` 预填在表的「结论」列）。
2. 每条建议都经 [apply_external_review.py](../../evals/main_set/tools/apply_external_review.py) 在 norm-v1 页文本中重新锚定；不能定位或违反 schema 的建议不写入。审校把整段条款作为 key 的 51 条按 spec P1 处理：条款 → `evidence_span`，`key_text` 保留原最小锚点或从条款首句派生（引导句不作锚点）。PV 审校未给出新 span 原文、只给长度的 15 条，按报告长度在新 key 周围重建 span。
3. 结果：应用 224 条、删除 4 条（+1 孪生）、EN 80 条待 CO 审校（未应用）、1 条英文由实现方缩短到 300 字符内；机械检查 0 错误；合计 626 条，全部 spec-m1 下限仍满足（有答案 563、无答案 63、冲突 52、long_context 29）。
4. 新增 2 条 PII 例外（ms-0135/0136 的完整条款含 EMA 机构信箱，沿用记录 21 的机构信箱口径），待 annotator-01 确认后随装配进入 `pii_exceptions.json`。
5. 审校指出的文档级问题，逐项核实：(a) Glimaryl 仿單（b1756268da31）文本层乱码属实（第 1 页 0 个汉字），无 gold，语料中保留、建议 M2 复核抽取或剔除；(b) `fda-investigator-safety-reporting-2021` 的 PDF 封面为 December 2025，候选清单与 corpus 的 `version_label`（September 2021）有误——`documents.version` 不可变，故按 M1-11 发布流程以同一源对象（`--share-source`）入库 `fda-investigator-safety-reporting-2025`（`Final guidance, December 2025 (FDA media 152530)`，effective_from 2025-12-01，`--accept-pii` 引用 2026-09-21 机构信箱复核）并 `--publish` 归档旧记录（outbox 事件 74–75）；corpus.json 记录替换、10 条样本的 gold `version_label` 同步、索引与向量补建；库内 active 76 / archived 6 / draft 3、chunk 10,992；(c) GVP Annex I Rev 4 的 PDF 第 1–3 页含 superseded 标注，仅作合成冲突 fixture，不代表现行定义。
6. 尚缺：CO 批次审校（84 条）、NA 批次确认（63 条）、EN 80 条的父样本裁决；决策人确认后进入 LLM 复核。

## 10. 补记（2026-09-22）：NA / CO 审校写回与人工确认

决策人补交 NA（63）与 CO（84，重生成版、无逐字段 diff）两份审校并回复"可以了"。处理：审校只描述改法的条目由实现方写出新值并留档（`external_review/implementer_edits_2026-09-22.json`），[apply_external_review_2.py](../../evals/main_set/tools/apply_external_review_2.py) 重新锚定；应用 97 条、删除 6 条（含 ms-0300：审校建议移到 PV，但 PR-06 要求样本部门等于文档部门，故删除）；EN 80 条待定项全部解决（父样本存活者应用成对中文/英文改写，父样本删除者随删）。写回后 615 条（新 508），全部 spec-m1 下限满足，机械检查 0 错误。决策人的"可以了"记为 annotator-01 对五张表的人工确认（2026-09-22）；随后进入固定模型 LLM 复核（claude-opus-5，批次 MA/PV/CO/EN/NA）。

## 11. 补记（2026-09-22）：LLM 复核启动、复核输入修正与 Annex I 换版

- 复核成本实测：MA 10 条 0.61 美元、NA 3 条 0.32 美元 → 全量 508 条估算约 35 美元（与此前报出的 25–35 美元一致），据此启动五批复核（claude-opus-5，块大小 5 / NA 3）。
- 复核人首批即发现两件事，均属实：(1) 复核输入缺 `conflict` 块（打包脚本漏带）——修正 [pack_review.py](../../evals/main_set/tools/pack_review.py) 与 [review_provenance.py](../../src/medops/evals/probe/review_provenance.py) 的输入重建，PV/CO/EN 作废重跑（约 1 美元沉没）；(2) GVP Annex I Rev 4 页眉标注 superseded——EMA 现行版为 Rev 5（2024-07-26），已下载（sha 409f9f85…，32 页，门禁与 PII 通过）、登记候选 cand-0102（v1.1），以 `--supersedes` + `--publish` 入库为 Rev 4 后继版：family 合成旧版（归档）→ Rev 4（归档）→ Rev 5（现行），成为主集中唯一的真实修订对；corpus.json 用 `version_fixes/gvp-annex-i-rev5.json`（`replaces_source_hash`）替换记录；5 条样本与孪生重锚到 Rev 5（ms-0084 因原定义已被删除而改写为 Reg 536/2014 的定义，ms-0092 key 加长以保持页内唯一），NA ms-0462 迁 scope 并复查缺席词；库内 active 76 / archived 7、chunk 11,231，索引与向量已补建。
- 后续：五批复核完成 → 争议裁决表 → 上述 11 条 `--only` 重跑 → 装配、冻结 `main-v1-provisional`。

## 12. 补记（2026-09-22）：LLM 复核完成，71 条争议待裁决

- 结果：507 条新样本（NA ms-0509 复核后删除：Glimaryl 文本层乱码，复核人无法核实缺席）由 claude-opus-5 复核完毕，71 条争议（14.0%）：MA 3、PV 21、CO 20、EN 19、NA 8；费用合计 43.06 美元（含作废重跑约 1 美元与定向重跑），高于此前 35 美元的估算，差额来自三处工具侧修正后的重跑与无答案输入扩为全文。
- 复核人指出并已修正的工具缺陷：复核输入漏带 `conflict` 块；第一轮外部审校按报告长度重建的 PV span 边界错位（25 条，恢复起草者原始完整条款后重跑，PV 争议由 41 降至 21，EN 由 37 降至 19）；无答案输入只含起草选页、无法核实缺席（28 条扩页重跑）。
- 复核后删除样本的机制：manifest 新增 `dropped_after_review`（`make_schemas.py`），PR-09 复核证据校验、装配与运行脚本的覆盖检查容忍已删除样本的历史证据（[review_provenance.py](../../src/medops/evals/probe/review_provenance.py)）；`review/dropped_after_review.json` 记录原因。
- 争议构成（按裁决方式）：切片增删类可用 `接受` 机械应用；key_text / query / 无答案缺席类需 annotator-01 判断；裁决表 [disputes_sheet.md](../../evals/main_set/drafts/main-v1/review/disputes_sheet.md)。裁决 → `apply_resolutions.py`（改动样本 `--only` 重跑）→ `assemble.py --human-confirmed 2026-09-22` → `freeze.py`（`main-v1-provisional`）→ chunk 映射 → 端到端运行。
- `env -u DEBUG -u PYTHONPATH make check`：退出码 0，**893 passed**（含复核证据的 dropped_after_review 容忍逻辑）。


## 13. 补记（2026-09-22）：争议裁决写回、口径补充与第二轮复核

- 决策人交回填好「决定」列的裁决表与一份统一口径记录（ChatGPT 辅助、由 annotator-01 提交；`external_review/main_v1_disputes_readjudication_audit_2026-09-22.md`）：接受 62、保留 9。逐格核对只有决定列与原表不同。
- 六条口径中四条与 2026-09-19 批准的 P1/P2/P3 一致；两条是主集收窄并已登记到 [SPEC §3](../../evals/main_set/SPEC.md)：测量值（QTc 毫秒、体重、血压）不计 `dose_unit`；仅以指南名限定来源不计 `protocol_id`。后者与冻结的探针 v2 不一致（24 条 protocol_id 样本的 query 只含指南名，PR-16 逐字节并入不能改），已向决策人说明并在 SPEC 写明两套口径并存；决策人以裁决表维持收窄。
- 写回方式：62 条接受多为文字描述，实现方翻译为页内原文的精确改动并留档 `review/resolutions_explicit_2026-09-22.json`（每条绑定决定文字的 SHA-256）；9 条决定给出的 key_text 超过 200 字符上限（ms-0122/0123、0197、0213、0217、0229、0268、0298、0326、0432/0433），取满足意图的最长 ≤200 连续原文并注明。决定引出的一致性清扫 `review/consistency_sweep_2026-09-22.json`：13 条（含孪生 20 条）指南名式 protocol_id、ms-0364/0365 的 mmHg dose_unit、ms-0416/0434 的父问改写（与已改写的孪生一致）。
- 工具：[apply_resolutions.py](../../evals/main_set/tools/apply_resolutions.py) 新增 `--explicit`、`--sweep`、`--sheet`、`section=` / `span=` / `absence_terms=`（无答案样本改题必须重查缺席）、父问改动联动孪生 `parent_query` 并重跑孪生、`review/changed_<date>.json`；[disputes_sheet.py](../../evals/main_set/tools/disputes_sheet.py) 新增 `--round`（跳过 `保留` 且判定未变的争议）。
- 结果：111 条样本改动（62 决定 + 孪生联动 + 清扫），`check_drafts.py` 0 错误、下限全满足；`resolutions.json` 9 条 `disputed_resolved`。111 条按批次 `--only` 重跑 claude-opus-5：费用 9.16 美元（累计 52.22 美元），EN 一块因复核人回复格式不合规中断一次、续跑完成。
- 第二轮：24 条新争议（MA 2、PV 4、CO 5、EN 8、NA 5），全部落在改动样本上：切片 8（其中 6 条是指南名式 protocol_id，复核提示的切片定义仍写"指南编号"，与新口径冲突，只能靠 `保留` 消解；1 条 21 CFR 50.56(b) 应补 protocol_id；1 条克重 dose_unit）、key_text 6（含 2 条受 200 字符上限约束无法满足）、evidence_span 5（两条原本就切在句中，第一轮未被指出）、query 6（4 条是父问已改写而孪生仍是旧问法）。裁决表 [disputes_sheet_round2.md](../../evals/main_set/drafts/main-v1/review/disputes_sheet_round2.md) 已由实现方预填 `建议：`（接受 15 / 保留 9），待 annotator-01 确认；第一轮已决表仍为 `review/disputes_sheet.md`。
- 观察：复核人对同一样本在两轮给出不同异议（如 ms-0058 第一轮建议收窄 span，第二轮又要求补回适应证限定），说明 LLM 复核有非确定性；第二轮之后若仍有争议，建议以 `保留` 收敛，不再进入第三轮重跑。
- `env -u DEBUG -u PYTHONPATH make check`：893 passed（本节改动前后各跑一次，见提交）。
- 第二轮裁决（2026-09-22 13:38 交回，`external_review/main_v1_disputes_round2_audit_2026-09-22.md`）：接受 16、保留 8。与预填的差异：ms-0197 决策人自选 199 字符的连续锚点（含初步评价对象与两个时点）而非保留；ms-0372/0373 扩 span 后同步补 `negation`（排除条款，按 span 判定）；8 条保留改写了理由，口径不变。应用：21 条样本改动（含孪生与 ms-0374 父问同步），`check_drafts.py` 0 错误，`resolutions.json` 17 条；工具补两处：决定格内未转义的 `|` 拆出的多余格重新拼接，实现方预填文字被改写时忽略预填翻译、按表内语法解析。21 条重跑复核结果见下一条。
- 第二轮重跑（21 条，1.05 美元，累计 53.27 美元）：仅余 1 条争议——ms-0228（ms-0227 的英文孪生）扩 span 后含 "it is not possible to obtain" / "legislation do not permit this"，复核人要求补 `negation`。该项与决策人第二轮审计记录的口径 3 一致（negation 按完整 span 判断，明确的不允许/例外限制可命中），属机械补标签，实现方在 `disputes_sheet_round3.md` 代填 `接受` 并同步父样本 ms-0227，两条重跑；决策人可否决。
- 第三轮重跑（ms-0227/0228，0.25 美元）：两条 agree。**争议收敛**：507 条新样本现行判定中 17 条争议全部有 `resolution_note`（`disputed_resolved`），其余 agree；LLM 复核累计 53.52 美元（首轮 43.06 + 三轮重跑 10.46）。进入装配与冻结 `main-v1-provisional`。
- 装配通过（`assemble.py`：614 条，counts 与下限齐全，`second_human_review.status=pending`），但 `freeze.py` 的 PR-09 复核证据校验拒绝：复核判定绑定的是整块提示（一次 5 条）的哈希，三轮裁决改动 134 条样本后，实现方只对改动 id 单独重跑，其原块邻居仍绑在含已作废输入的提示上（"latest invocation also contains superseded input"）。这是实现方的重跑方式失误（探针 v2 的工具整块重问）。受影响 318 条（MA 13、PV 98、CO 63、EN 124、NA 20），估算 22–30 美元。决策人 2026-09-22 选择方案一：块大小 1 重跑全部 318 条（此后每条判定只绑自身输入，裁决改动不再连坐），五批并行。工具补救：`apply_resolutions.py` 的重跑改为 `--chunk 1`；新增 `review_binding_check.py` 在冻结前列出绑定到过期块的样本。
- 318 条块大小 1 重跑（2026-09-22 14:00–15:11，五批并行）：费用 34.75 美元（高于估算的 27–30：PV/CO/EN 单条约 0.10 美元），LLM 复核累计 88.27 美元。`review_binding_check.py` 归零。结果：MA 0/13、PV 10/98、CO 34/63、EN 12/124、NA 7/20 条争议；`carry_forward_resolutions.py` 把 6 条未改动样本上的同一异议沿用了决策人的保留决定（ms-0219/0220/0376/0380/0482/0491），4 条复核人转为 agree 的保留自动撤销（ms-0261/0347/0391/0493）。余 57 条进入第四轮表 `disputes_sheet_round4.md`：CO 的 34 条全部是 protocol_id——复核提示的切片定义仍写"指南编号"，与决策人 9 月 22 日的收窄口径冲突；实现方按该口径预填：query 含精确条号/节号/版本号的 18 条接受补标签，只含指南名的 27 条保留，其余 12 条（8 条 query 机械改写、1 条 key_text 最小化、3 条 span 边界）按复核人建议预填接受。空跑：57 条全部可执行，接受项影响 47 条样本（含孪生与 parent_query 联动），块大小 1 重跑约 5 美元。
- 第四轮（决策人 2026-09-22 回复"按建议来"）：57 条按预填采纳——接受 30（18 条补 protocol_id、8 条 query 改写、1 条 key_text、3 条 span）、保留 27；应用后 47 条样本改动（含孪生与 parent_query 联动），`check_drafts.py` 0 错误，`resolutions.json` 40 条；改动样本按块大小 1 重跑（PV 6、CO 17、EN 24）。
- 第四轮重跑（47 条改动 + 绑定检查新找出的 9 条 EN 邻居，均块大小 1，约 6 美元，复核累计 93.22 美元）：9 条新争议 → 第五轮表 `disputes_sheet_round5.md`（预填：接受 7——6 条父问题改写后英文孪生同步改写、1 条 span 补全；保留 2——指南名 protocol_id）；绑定检查归零。
