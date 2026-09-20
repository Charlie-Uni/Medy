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
