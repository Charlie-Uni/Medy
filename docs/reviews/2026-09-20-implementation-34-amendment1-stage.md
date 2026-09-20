# 实现记录 34：ADR-0002 修订 1 大阶段（chunker-v2、esomen 质量复核、探针 v2 孪生、第二次运行）

日期：2026-09-20。决策人对记录 33 的建议回复"按照你的建议来 直接大阶段实现 其中的细分工作自己审核修复 通过再进行下一轮"。本记录覆盖该阶段的四个子轮次；每个子轮次通过 ruff/mypy/pytest 后才进入下一轮。阶段结论：**工程部分全部完成并通过 659 项测试；第二次运行已执行但只能作为临时结果，因为 Codex/gpt-6-astra 用量额度耗尽（2026-09-26 21:00 恢复），32 条英文孪生查询无法完成 LLM 第二复核，探针 v2 不能冻结。**

## 1. 预登记（先于任何运行）

ADR-0002 修订 1 已写入并由决策人批准：硬门禁与最低数量在"语言一致"子集内计算，跨语言样本作为 `cross_lingual` 切片单独报告；探针 v2（spec-v1.1）为 32 条英文 gold 样本各派生一条英文查询孪生；chunker-v2；esomen 经审计质量复核；三服务器新建 `medops_v2`；候选实现、前置规则与全部测量参数与第一次运行相同。`experiment_plan.json` 的 `run_2_preregistration` 与 SPEC 5.1、PR-15 同步写入。

## 2. 子轮次 1：chunker-v2 与解析质量复核放行（提交 `0ed131e`）

- `chunker-v2`：分号不再是句末（v1 在 `DSUR; however` 处切断）；超长片段优先在最后 200 字符内的子句标点后切分，再退回空白与硬切。既有 8 项切分器测试通过，新增 2 项。
- 抽取器记录 pypdf 告警文本（去重计数写入 ingest 审计）；`ingest_document(..., quality_override_reason)` 与 `--accept-quality KEY=REASON`：有告警且带复核理由时升为 trusted，并写 `quality_review_override` 审计（含告警文本、from/to）；无告警时为空操作；无理由时 INV-DATA-05 照旧。新增 1 项集成测试（低信任、放行审计、空操作）。
- esomen 的 8 条告警全部为"未完整解析 CFF Type1 字体编码"，页文本与冻结页逐字节一致且已由 annotator-01 确认 6 条样本，放行理由引用修订 1 第 4 点。

## 3. 子轮次 2：spec-v1.1 与探针 v2 草稿

- 模式：`probe_sample.schema.json` 增 `derived_from`；`manifest.schema.json` 的 `spec_version` 允许 `spec-v1.1`，增 `derived_samples`（规则、数量、`query_language=en`、LLM 起草者、`human_confirmation`）。
- 校验器：PR-15（引用、继承字段、英文 gold 文档、查询不同、数量一致、spec-v1 禁止派生）；PR-11 对派生样本免除 `language=mixed`；复核证据按 spec 版本分批（v1.1 增 `EN` 批次，10 个工件）。新增 3 项校验器测试，既有 65 项不变。SPEC 5.1 与第 10 节 PR-15 已写入。
- 孪生：我起草 32 条英文问题（[twins_queries.json](../../evals/probe/precise_clause/drafts/v2/twins_queries.json)），`derive_twins.py` 机械核对（父样本存在且为英文 gold、查询规范化后互不相同且不等于任何 key_text、key_text 页内唯一）生成 `samples_draft_EN.json`（pc-0076～pc-0107），`review_pack.py EN` 打包复核输入（含页文本，已忽略不入库）；v2 工具为 v1 工具的路径改写副本，页文本直接引用 v1/pages，不用符号链接。确认表见 [twins_confirmation_sheet.md](../../evals/probe/precise_clause/drafts/v2/twins_confirmation_sheet.md)。
- 阻塞：`codex exec` 返回 "You've hit your usage limit … try again at Sep 26th, 2026 9:00 PM"。因此 `run_codex_review.py EN`、v2 装配（含 v1 八个证据工件 + EN 两个 + 新的 resolutions/runtime）、冻结均未执行。v2 装配器尚未编写，待复核证据存在后实现。

## 4. 子轮次 3：三服务器 `medops_v2` 与映射

- 三服务器各建 `medops_v2`：迁移到 0004、以 chunker-v2 入库 16 份（PII 放行理由复放；esomen `--accept-quality`）、按 [activation_plan.run2.json](../../evals/experiments/lexical/preparation-v1/activation_plan.run2.json)（确认计划 + esomen 2013-11-08 PDF 元数据层级）全部激活；16 份 active/trusted，2,662 chunk，指纹 `2b06246a…2b11` 三处一致，每库一条 `quality_review_override` 审计。第一次运行的 `medops` 库保留。
- 三候选索引重建（各 2,662）；快照与映射写入 `preparation-v1/servers_v2/`：**75 mapped / 0 unmappable**（pc-0056-g1、pc-0072-g1 在 chunker-v2 下落入单个 chunk）。

## 5. 子轮次 4：运行工具修订与第二次（临时）运行

- `dec001_run`：样本按 `gate_scope(language, gold_script)` 分为 `language_matched`/`cross_lingual`；`--twins` 把未复核孪生作为叠加（`provisional=True`，对照父样本 gold 评分，永不进入门禁与配对 bootstrap）；`--database` 覆盖库名；清单记录作用域规则与叠加文件哈希。`dec001_report`：门禁取 `scopes.language_matched`，新增作用域分报与临时叠加表；第一次运行格式仍可评估。新增/更新 6 项单元测试。
- 运行 `2026-09-20-run2-provisional`（清单 SHA-256 `76e6ab08…e5ce`）：

| 子集 | A | B | C |
| --- | --- | --- | --- |
| 语言一致（43 条冻结样本） | 81.4% | 93.0% | 95.3% |
| 跨语言（32 条，不设门禁） | 15.6% | 12.5% | 12.5% |
| 未复核英文孪生叠加（32 条） | 59.4% | 59.4% | 90.6% |
| 语言一致 + 孪生（75 条） | 72.0% | 78.7% | 93.3% |

零泄漏、排名可复现；词法 P95 A 43.8 / B 41.6 / C 44.6 ms；相对 A（43 条）B +11.6 pp [+2.3, +20.9]、C +14.0 pp [+4.7, +25.6]。v1 的语言一致子集不满足修订 1 最低数量（CO 0、PV 13、protocol_id 5），因此不能判定通过。归因（只读，`miss_diagnostics.json`）：所有未命中都是 gold 合格但名次 >20；A/B 孪生未命中的合格候选中位数 1,558 条，原因是 `simple` 配置保留英文停用词且 `ts_rank_cd(normalization=0)` 无 IDF 加权；C 的 BM25 不受影响。此现象由预登记配置决定，不在看到结果后调整。结果已回填 ADR-0002。

## 6. 测试与门禁

`env -u DEBUG -u PYTHONPATH make check` 退出码 0：ruff、129 文件格式一致、mypy 57 文件无错、**659 passed**（522 单元 + 137 集成）、schemas 无漂移。本阶段新增：切分器 2、入库 1、校验器 3、运行/报告 6。

## 7. 自审（基线 §9）

1. 需求：修订 1 的六项全部落地；未在看到结果后调整任何候选配置；孪生未复核部分只作叠加。
2. 逻辑：chunker-v2 与放行规则先于运行固定；映射 75/75；作用域分类与配对 bootstrap 只用冻结样本。
3. 安全：质量放行需理由并写审计；`.env.dec001` 不入库；本记录不含 DSN。
4. 契约：候选适配器与 `LexicalRetriever` 未改；schema 变更为向后兼容的可选字段。
5. 测试：659 passed；PR-15 正反例。
6. 可观测：运行目录五个文件；孪生叠加在清单中带哈希与状态。
7. 简洁性：v2 工具为路径改写副本；运行器增量改动。
8. 验证：本记录数字来自 make check、CLI 输出与 report.md。
9. Checklist：M1-05 仍阻塞（临时结果）；M1-10 已实现（chunker-v2）；进度不变 **24.7%（19.5/79），按 99 项计 19.7%**。

## 8. 下一步（恢复顺序）

1. 2026-09-26 额度恢复后：`python evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py EN`；争议按 v1 流程处理。
2. annotator-01 按确认表确认 32 条英文问题（可现在进行，与复核并行）。
3. 编写 v2 装配器（v1 样本原样 + 孪生 + 复核块；manifest spec-v1.1、`derived_samples`、10 个证据工件；pii_exceptions v2），draft 校验、冻结（SHA256SUMS、dataset_hash）。
4. 以冻结 v2 重跑（`--database medops_v2 --mapping-* servers_v2`，不再需要 `--twins`），生成报告并回填 ADR-0002；届时按 75 条语言一致样本判定硬门禁。
5. 若 B/C 通过而 A 不通过：按 ADR 选择规则，C 因许可证阻断不能选入，B 需端到端 Recall@5/P95 与词典许可证审核后才能替代 A。
