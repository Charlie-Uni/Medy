# ADR-0002：词法检索实现选择实验预登记

| 项 | 内容 |
| --- | --- |
| 状态 | 协议已决；生产实现待 M1 入口实验 |
| 日期 | 2026-09-03 |
| 最后修订 | 2026-09-20（修订 3）：DEC-001 最终判定推迟到端到端实验，M1 其余切片继续；2026-09-20（修订 2）：预登记英文停用词变体 A2/B2；2026-09-20（修订 1）：决策人批准门禁作用域按语言一致子集计算并预登记第二次实验（探针 v2、chunker-v2、esomen 质量复核）；2026-09-20（晚）：回填 M1-05 词法对比运行结果，三候选均未通过硬门禁，判据不变；2026-09-20：完成探针 Git 归档，追加映射与实验准备状态，预登记判据不变；2026-09-10：增加 zh-Hans 样本最低数量与脚本变体分开报告（第七轮记录）；2026-09-08：复核方式、gold 命中规则与切片门禁作用域按第五轮审核记录修订 |
| 关联 | 基线 DEC-001、3.1、3.6、3.7、5.2、5.9、M1 Checklist |
| 决策人 | Qihan Zhu |

## 背景

项目要求精确条款召回，但不要求某个排序公式。PostgreSQL FTS、数据库中文 tokenizer 和数据库内 BM25 对上层均实现同一个 `LexicalRetriever`，却会影响索引、分词、镜像、权限验证、许可证和 `retrieval_version`。RRF 与 Reranker 无法补回没有进入候选集的条款，因此必须在实现主检索链前用本项目语料选型。

本 ADR 预先固定候选、数据、指标和阈值，实验完成后只回填结果和最终选择，不事后修改判据。

## 候选范围

三个生产候选为：

1. **A：应用层预分词 + PostgreSQL `simple` FTS。** Python tokenizer、医学词典和规范化规则同时用于入库与查询；空格连接词元后生成保留位置的 `tsvector`。
2. **B：PostgreSQL FTS + 数据库中文 tokenizer。** 在实验清单中从 `zhparser` 或 `pg_jieba` 固定具体实现、版本和配置；若两者都测试，必须作为独立变体完整报告，不能看结果后只保留有利变体。
3. **C：`pg_search` BM25 + 固定中文 tokenizer。** 必须固定扩展、tokenizer、配置和镜像 digest，并验证该精确版本的能力，不能以最新版文档替代运行证据。

进程内 BM25 只作为离线参考基线，不是生产候选，也不能持有绕过数据库 ACL/RLS 的全量生产索引。

## 实验输入与复现条件

- 先冻结不少于 60 条、目标 72 条的精确条款探针集，覆盖中文药名、剂量单位、否定词、时间窗、方案编号和中英混排；每类至少 8 条，允许多标签。
- MA、PV、CO 每个部门不少于 15 条；gold 来源文档为 `zh-Hans` 的样本不少于 8 条；`zh-Hant` 文档可计入 `drug_name_zh` 切片，但报告按脚本变体分开，繁体结果不证明简体达标；语料只用 ADR-0003 准入为 `eligible` 的公开文档；样本和 gold 由人工标注并经 LLM 独立复核，manifest 如实记录复核者类型，不等同于两名独立人工复核。
- gold 锚定到 `source_hash/version_label/page/section/key_text`，不引用 `chunk_id`；`key_text` 在规范化后的 `gold.page` 页文本中恰好出现一次。chunk 命中要求同一 `source_hash/version_label`，且 chunk 具有覆盖 `gold.page` 的来源片段并覆盖该 `key_text` 的页内位置，不得仅凭跨页 chunk 全文包含 `key_text` 判定；切分器变更只重生成映射文件。数据结构、校验规则与冻结流程见 [evals/probe/precise_clause/SPEC.md](../../evals/probe/precise_clause/SPEC.md)，冻结后固定 `dataset_version` 与 `dataset_hash`。
- 实验期间不得改样本。发现标注错误时创建新版本，并对全部候选完整重跑。
- 所有候选使用同一份授权语料、query/gold、数据库过滤条件和 `K=20`。记录 PostgreSQL、扩展、tokenizer、词典、规范化规则、镜像 digest、硬件、并发、预热、重复次数和复现命令。
- 应用层预分词的入库与查询必须使用同一组 tokenizer/词典/规范化版本。这些版本进入索引元数据、`retrieval_version` 和缓存键；不匹配时拒绝查询，升级时产生新版本并重建索引。

## 统一契约

`LexicalRetriever` 至少输出：

```text
LexicalSearchResult
  candidates[]: chunk_id, raw_score, rank
  requested_k
  returned_count
  candidate_exhausted
  retriever_version
  tokenizer_version
  dictionary_version
```

`raw_score` 只用于 Trace 与实验诊断；RRF 使用 `rank`。`returned_count` 必须是数据库权限、状态和生效时间过滤后的实际数量。

## 硬门禁

任一生产候选必须同时满足：

1. 探针集严格宏平均 Lexical Recall@20 不低于 90%。
2. 六个精确条款切片各自的 Lexical Recall@20 不低于 85%。
3. 跨部门受限 chunk、分数、计数和其他元数据泄漏为 0。
4. 候选不足不得静默发生：在相同查询、tokenization 与数据库过滤条件下，精确计数证明合格候选不少于 `K` 时必须返回 `K` 条并设置 `candidate_exhausted=false`；少于 `K` 时返回实际数量并设置为 `true`。“合格候选”指满足该候选在实验清单中固定的词法匹配谓词（词元 AND、OR 或短语，逐候选声明）且通过数据库过滤的 chunk；计数与检索使用同一谓词与过滤条件。
5. tokenizer/词典/规范化规则版本不匹配时拒绝查询；相同 `retrieval_version` 的索引和查询结果可复现。分数相同的候选按 `chunk_id` 升序打破并列，“可复现”指候选集合与排名逐项一致。

切片门禁按每类不少于 8 条的探针样本计算；基线 5.8 的“样本少于 30 条只作诊断”只适用于 M4 Loop 回放报告，不适用于本实验。

任何一项失败即淘汰；三个候选均失败则 DEC-001 和 M1 保持阻塞，不降低门禁。

## 选择规则

“合格候选”指通过上节全部硬门禁且许可证门禁通过的候选；技术得分不能替代许可证结论。

候选 A 通过全部硬门禁时作为复杂度基线。候选 B 或 C 只有同时满足下列条件，才能替代 A：

- 相对 A 的配对 Lexical Recall@20 点估计提升不低于 5 个百分点，且按 query 配对 bootstrap 的 95% CI 下界大于 0。
- 端到端严格宏平均 Recall@5 相对 A 下降不超过 1 个百分点。
- 任一关键切片下降不超过 5 个百分点。
- 词法检索 P95 延迟相对 A 增幅不超过 25%，且普通问答端到端 P95 仍不超过 8 秒。
- 本 ADR 的权限、候选不足、版本和许可证门禁全部通过。

若 A 未通过硬门禁，在其他合格候选中选择严格宏平均 Lexical Recall@20 较高者；差值不足 5 个百分点或配对 bootstrap 95% CI 包含 0 时，选择词法 P95 较低者。仍无法区分时保持 DEC-001 阻塞，由新的预登记实验解决，不凭偏好选型。

## RLS 与候选数测试

每个生产候选都在普通应用角色、`FORCE ROW LEVEL SECURITY` 和连接池身份切换条件下测试：

1. **零越权：** 三个部门放置相同或近似词条，任何请求均不得返回其他部门的 chunk、分数、计数或可推断元数据。
2. **零静默不足：** 覆盖按分数排序、`LIMIT` 下推、少于/等于/多于 `K`、over-fetch 和连接池复用，断言 `returned_count` 与 `candidate_exhausted` 符合硬门禁。

数据库扩展的自定义扫描不能只依据官方说明推定安全，必须对锁定镜像中的实际执行计划和查询结果留证。

## 许可证门禁

许可证是独立的非技术判据，质量实验通过不等于允许发布。每个候选必须记录直接与传递依赖的许可证、分发/托管方式、镜像来源和审核结论。

截至本 ADR 日期，ParadeDB 官方仓库将社区版标为 AGPL-3.0，并提供商业许可渠道；若候选 C 没有针对本项目发布方式的明确批准，则标记 `release_blocked`，不得因技术得分更高而选入生产。参考：[ParadeDB 官方仓库](https://github.com/paradedb/paradedb)。本段是组件现状记录，不替代正式许可证审核。

## 修订 1（2026-09-20，决策人批准）：门禁作用域与第二次实验的预登记

第一次运行（见结果回填）表明 gold 文档为英文、查询为中文的 32 条样本在任何词法候选上都无法召回，这是词法阶段对跨语言查询的固有限制。决策人于 2026-09-20 批准按建议修订并预登记第二次实验，判据阈值不变：

1. **门禁作用域。** 硬门禁 1、2 与最低数量（≥60 条、每部门 ≥15、每切片 ≥8、zh-Hans ≥8）在"语言一致"子集内计算：gold 文档为 `en` 且样本 `language=en`，或 gold 文档为 `zh-Hans`/`zh-Hant` 且样本 `language` 为 `zh`/`mixed`。gold 文档为 `en` 而查询为中文的样本构成 `cross_lingual` 切片，单独报告，不设词法门禁，由后续向量阶段承担。
2. **探针 v2（spec-v1.1）。** 在 v1 冻结样本之外，为 32 条英文 gold 样本各派生一条英文查询孪生样本（`derived_from`，gold/部门/切片继承不变），使语言一致子集达到 75 条（MA 30、PV 29、CO 16）。孪生样本由 LLM 起草、LLM 第二复核人复核、人工标注人确认后才能冻结；确认前的运行只能标为临时结果。
3. **切分器 v2。** `chunker-v2`（分号视为子句标记；超长片段优先在子句标点处切分）在看到第二次结果之前固定；两条 v1 unmappable gold 只重生成映射，不改样本。
4. **esomen 的解析质量。** 8 条 pypdf 告警均为"未完整解析 CFF Type1 字体编码"，页文本已与冻结页逐字节一致且经人工确认 6 条样本；以受审计的 `quality_review_override` 升为 trusted 并按 M1-11 口径激活（PDF 元数据日期 2013-11-08）。
5. **实验数据库。** 三服务器各新建 `medops_v2` 库（迁移到 head、chunker-v2 入库、16 份激活、重建索引），第一次运行的 `medops` 库保留为证据；三服务器语料指纹必须一致。
6. **不变项。** 候选 A/B/C 的实现、前置查询规则、K=20、并发 1、预热 5 遍、测量 10 遍、种子、配对 bootstrap 参数、同分排序与零泄漏核对全部与第一次运行相同；不因第一次结果调整任何候选配置。

7. **复核人（2026-09-20 追加，决策人方案 2）。** 因 gpt-6-astra 额度耗尽，探针 v2 的全部 107 条样本改由固定模型 `claude-opus-5`（Claude Code CLI，`reviewer-llm-02`）统一重新复核；起草孪生的模型为 claude-fable-5-1，复核人不是起草者；v1 的 gpt-6-astra 复核证据随 v1 归档。SPEC 8.1 记录固定模型标识的证据要求。

第一次运行的结果与结论保留不变；第二次运行的结果按同一格式追加到结果回填。

## 修订 2（2026-09-20，决策人批准“同意 继续”）：英文停用词变体的预登记

第二次运行的归因表明 A、B 在英文查询上的未命中几乎全部来自 `simple` 配置保留英文功能词而 `ts_rank_cd` 不做 IDF 加权。决策人批准按建议预登记两个变体，在看到变体结果之前固定如下：

1. **A2 = `pg-simple-fts-v1` + `tok-jieba-v2`。** 分词器规则与 v1 相同，另在入库与查询两侧删除出现在固定英文停用词表中的 ASCII 词元；词表为 PostgreSQL 16 随附的 `english.stop`（127 词，SHA-256 `b3f772a000465cb76e23adb03b47073c591c156fad8f7af09c8b8e80d6bd8eac`，副本存于 `evals/experiments/lexical/resources/`），哈希进入 `dictionary_version`。排序、谓词、过滤与 A 相同；索引表 `lexical_index_a2`。
2. **B2 = zhparser 2.3 + 配置 `dec001_b2`。** 与 B 相同的解析器与词性映射，但词元映射到 `simple` 模板加 `stopwords = english` 的字典 `dec001_simple_en_stop`（同一 `english.stop`，安装时逐字节核对镜像内文件），入库与查询同一配置；索引表 `lexical_index_b2`。
3. **不变项。** 探针 v2 冻结集、`medops_v2` 数据库、chunker-v2 映射、K=20、并发 1、预热 5 遍、测量 10 遍、种子、配对 bootstrap 参数、同分排序、零泄漏核对、语言一致门禁作用域；A、B、C 原样同场重跑作为对照。
4. **判定。** A2、B2 按硬门禁 1～5 独立判定；变体与其基线的差异按 query 级配对 bootstrap 报告。若 A2 通过硬门禁，A2 取代 A 作为复杂度基线（同一实现族，只增加停用词表）；B2/C 替代基线仍需选择规则的全部条件，C 的许可证阻断不变。


## 修订 3（2026-09-20，决策人批准“同意”）：DEC-001 最终判定推迟到端到端实验，M1 其余切片继续

三次预登记运行后无候选通过词法硬门禁，且证据表明跨语言查询只能由向量阶段承担、语言一致查询的剩余差距来自排序函数与繁体药名切分。决策人批准：

1. DEC-001 的最终选型推迟到端到端实验（M1-16 向量召回、M1-17 融合、M1-21 端到端 Recall@5）之后统一判定；词法阶段不再要求单独通过硬门禁作为 M1 其余工作的前置条件。已运行的三次结果、门禁阈值与选择规则保留不变，作为端到端实验中词法通道的已知基线。
2. 与词法引擎选择无关的 M1 切片先行：M1-11 发布事务与 outbox、M1-16 的向量阶段准备（DEC-002 之后）、M1-18 事实回查、M1-19 缓存失效。生产 `lexical_retriever`（M1-14）与选定方案的版本固化（M1-15 取值）仍等待 DEC-001 判定；在此之前主检索链只能以“候选适配器 + 契约”的形式存在，不进入生产配置。
3. C 的许可证审核并行推进（[licence dossier](../reviews/2026-09-20-licence-dossier-pg-search.md)）；排序侧变体（`ts_rank` 归一化、应用层 IDF）或繁体医学词典变体只在决策人另行预登记后运行。


## 修订 4（2026-09-20，决策人授权实施方决定）：候选 C 因许可证策略排除

决策人于 2026-09-20 回复"我需要的是结果 你来决定"，将悬而未决的许可证结论授权实施方作出。决定：**候选 C（pg_search / ParadeDB，AGPL-3.0 社区版）排除出生产候选**，`release_blocked` 改为 `excluded_by_decision`。理由：

1. AGPL-3.0 第 13 条在本系统可能向外部合作方提供网络访问时产生源码提供义务，且许多制药合规环境对 AGPL 组件实行一律禁止或特批；在没有书面法务批准或商业许可的前提下，不能以技术得分（语言一致 88.0%）为由选入生产。
2. C 依赖 ParadeDB 自建的 PostgreSQL 镜像与 `shared_preload_libraries` 配置，运维耦合高于 A/B 族（A 只需标准 PostgreSQL，B 需 zhparser 扩展）。
3. 修订 3 已把最终判定推迟到端到端实验；跨语言召回由向量阶段（ADR-0007）承担，A2/B2 在语言一致集上的差距（77.3% / 80.0%）由融合与重排在端到端门禁中一并检验。
4. 可逆：若端到端实验中以 B2/A2 为词法通道仍无法通过 M1-21 门禁，且组织取得书面许可结论或商业许可，可另行修订重新纳入 C。C 的适配器、镜像与三次运行结果作为实验对照保留。


## 修订 5（2026-10-05，决策人同意「全部添加」）：候选 D（`pg_textsearch` BM25）的预登记

**为什么重开。** 修订 4 排除候选 C 的理由是许可证（AGPL-3.0），不是效果——C 在语言一致探针集上的词法召回最高（88.0%，A2 77.3%）。Tiger Data 的 `pg_textsearch` 于 2026 年 4 月发布 1.0，在 PostgreSQL 内提供 BM25 排序，采用宽松的 PostgreSQL 许可证。它不在本 ADR 最初的候选范围内：那是选型范围没有覆盖到，不是评估后否决。决策人 2026-10-05 同意把它作为新候选纳入实验（记录 122 之后的四项补充之一）。本修订在任何观测之前写定候选 D 的配置、判据与风险；不改变既有三候选的结果，也不改变最终判定，除非 D 按下面的规则胜出。

**候选 D 的固定配置（观测前声明）。**

- 组件：`pg_textsearch` 的官方发布包（Linux arm64，PostgreSQL 17；预登记时查到的最新版是 1.5.0，构建当日 2026-10-06 实际最新稳定版为 2026-10-02 发布的 1.5.1，采用 1.5.1，资产 SHA-256 与镜像 digest 记在 `evals/experiments/lexical/builds/d/build-metadata.json`）；基础镜像 `pgvector/pgvector:pg17`（库里有向量列，恢复数据需要 pgvector）；`shared_preload_libraries = 'pg_textsearch'`。
- 分词：与 A2 完全相同——应用侧 `tok-jieba-v2`（同一份固定英文停用词表）产生词元，以空格连接存入索引表的文本列，索引 `using bm25(...) with (text_config = 'simple')`；查询走同一分词器。D 与 A2 的差别因此只剩「排序函数与索引引擎」，实验量的是 BM25 本身的作用，不混入分词差异。
- 参数：`k1 = 1.2`、`b = 0.75`（扩展默认值），不调参。
- 查询语义：词元之间为 OR；按 BM25 得分取前 20，得分相同按 `chunk_id` 升序；过滤条件与 A2 相同（RLS 链、`status = 'active'`、生效窗口）；合格候选的精确计数与分页在同一快照内取得。
- 数据：候选 D 的服务器由 `medops_v2` 经 `pg_dump` / 恢复得到，chunk 的 UUID、内容哈希与向量逐一保留，因此探针与主集的 gold 映射、向量通道都与 A2 侧相同。

**硬门禁（与原 ADR 相同，另加两条针对该扩展的核查）。**

1. 普通应用角色 + FORCE RLS 下零跨部门泄漏；按主键无存在性泄露。
2. 零静默候选不足：k 小于、等于、大于合格数三种情形下，返回数与精确计数一致（该扩展对 WHERE / RLS 条件做的是打分后的过滤，必须实测 LIMIT 与 RLS 的相互作用）。
3. 身份缺失拒绝、连接复用清除、版本不匹配拒绝、排名可复现——沿用适配器测试套件。
4. **统计泄漏评估**：该扩展的文档写明语料统计（词频、文档频率）包含被 RLS 隐藏的行。这意味着一个部门看到的排序受其他部门文档的词频影响，理论上可被用来推断隐藏文档里某个词是否常见。实验必须给出评估（能否通过按部门分区或分索引消除、代价多大）；未有结论前 D 不得进入生产，即使其余门禁全过。
5. **主版本依赖**：该扩展只支持 PostgreSQL 17 / 18，现行生产是 16。D 若胜出，采用它意味着数据库主版本升级，须另有迁移与回滚方案，不属于本实验。

**测量。** 全部在本机完成，不调用付费模型（端到端对比关闭查询翻译，两侧同样关闭）。

1. 词法单项：探针 v2 语言一致 75 条的严格宏平均 Lexical Recall@20 与六个切片，对照运行 2、3 的 A / A2 / B / B2 / C。
2. 端到端：主集 `main-v3-provisional` 553 条有 gold 的样本，已发布检索策略（词表、多查询、文档聚焦；翻译关闭）下的严格宏平均 Recall@5，A2 对 D，配对 bootstrap。
3. 时延：词法检索 P95（并发 1，5 遍预热、10 遍测量，与既有清单相同）。

**选择规则不变。** D 取代 A2 的条件是端到端 Recall@5 高出至少 5 个百分点且配对 bootstrap 95% CI 下界大于 0，同时全部硬门禁通过；否则保持 A2（规则要求选最简单的实现）。即使满足，上线前仍须：统计泄漏评估有结论、主版本升级方案、回放门禁（付费，约 13 USD）与决策人批准。

**许可证。** PostgreSQL License（宽松，无 copyleft）；传递依赖在构建时记录。决策人 2026-10-05 同意纳入实验。按本 ADR 的许可证门禁，生产采用前仍要补一份完整的许可证记录（直接与传递依赖、分发方式、镜像来源）。

## 结果回填

M1 实验完成后在本节追加：探针集版本与哈希、候选版本/镜像 digest、各指标与置信区间、RLS/候选数测试、许可证结论、最终选择和复现命令。回填不得删除本次预登记内容。

当前状态：2026-09-20 已完成三次预登记运行（修订 1 在冻结探针 v2 上，修订 2 加入停用词变体 A2/B2），无候选通过硬门禁；DEC-001 与 M1 保持阻塞，判据不降低，无生产实现选择（见下文结果回填）。

### 2026-09-20：实验输入已冻结并完成 Git 归档

精确条款探针集 `v1` 已在本地冻结，包含 16 份文档、75 条样本（MA 30、PV 29、CO 16；gold 来源为 zh-Hans 的样本 10 条）。当前复核结果为 71 条 `agreed`、4 条 `disputed_resolved`、0 条待决。带页文本的正式 frozen 校验通过，PR-01～PR-14 报告为 0 findings；全套软件检查为 482 passed（418 单元、64 PostgreSQL 集成）。这些结果确认实验输入与现有软件检查通过，词法检索选型实验尚未运行，无生产实现选择，以上预登记候选、指标、阈值和选择规则不变。

| 冻结记录 | 值 |
| --- | --- |
| `dataset_version` | `v1` |
| 本地冻结日期 | `2026-09-20` |
| `dataset_hash`（SHA-256 of `SHA256SUMS` bytes） | `5561bee58e37cd8d86b756f17e6c1a6ebed32ba54ba2ac48f4cd4adee254db7e` |
| `manifest.json` SHA-256 | `062f9a536e0d811306f80dd5c24cc44f40a39a8f36ac360959c4de99b1faf54b` |
| 冻结归档 Git commit | `213dbe8ead8ff92d8919b201460ac3a961176c8c`（祖先 `2a4aef6` 归档校验器与工程依赖） |

PII 规则保持 `pii-rules-v1`。`pc-0046` 的 EMA 机构联系邮箱沿用已批准的人工依据，以一条精确到样本、来源、字段哈希、匹配文本及区间的例外记录处理；例外文件已纳入 `manifest.files` 与 `SHA256SUMS`，未改动原始页文本或证据 span，也未放行其他邮箱或个人数据。

复核模型如实记录为 `service-alias:gpt-6-astra;backend-version:not-exposed`，调用 effort 为 `high`。8 件复核运行证据已随版本保存并由 manifest 中的哈希绑定；后端模型版本未暴露，CLI 版本单独记录，因此不声称固定模型快照或再次调用同一后端的可复现性。

依据：[本地冻结摘要](../../evals/probe/precise_clause/drafts/v1/review/local_freeze_summary_2026-09-20.json)、[正式 frozen 校验](../../evals/probe/precise_clause/drafts/v1/review/frozen_validation_2026-09-20.json)、[manifest](../../evals/probe/precise_clause/v1/manifest.json)、[PII 逐命中裁决](../../evals/probe/precise_clause/v1/pii_exceptions.json)、[当前处理表](../../evals/probe/precise_clause/drafts/v1/review/current_review_disposition.md)。Git 归档已完成；在独立 checkout 上，418 项既有单元测试及正式 frozen 校验再次通过。归档回执见 [git_archive_2026-09-20.json](../../evals/probe/precise_clause/drafts/v1/review/git_archive_2026-09-20.json)。


### 2026-09-20：实验准备进展（尚非选型结果）

已建立 [DEC-001 准备目录](../../evals/experiments/lexical/README.md)，记录 A/B/C 固定源码候选、实测环境和测量参数草案。B/C 镜像及部分配置尚未构建验证，三候选适配器、端到端配置及独立许可证审核未完成，实验清单状态仍为 draft，尚未观察检索得分。

只读导出当前 2,661 个 chunk，和冻结页文本重新切分后逐条内容/哈希/来源区间相同。75 条 gold 中 73 条 mapped，pc-0056-g1 与 pc-0072-g1 跨切分边界，按既有规则记录 unmappable 并计 miss，不删除或改写样本。该统计不等于 Lexical Recall@20。另有既存 low_trust 文档及 draft 发布状态需要在正式实验前处理；本次管理侧导出不作为 RLS 或生产可用性证据。

### 2026-09-20：M1-05 词法对比运行结果（三候选均未通过硬门禁）

运行目录 [evals/experiments/lexical/runs/2026-09-20-m1-05-lexical/](../../evals/experiments/lexical/runs/2026-09-20-m1-05-lexical/)：`run_manifest.json`（查询前写出，SHA-256 `a582225f5b39e24b3cb709708c53aadca54f095518a0a1ebc02c116c295926f0`）、`results.json`、`evaluation.json`、`report.md`、`miss_diagnostics.json`。Git HEAD `7c11833`。输入：探针 v1（dataset_hash `5561bee5…db7e`），75 条；15 份文档按决策人 2026-09-20 确认的激活计划转为 active，`tfda-label-esomen-40mg` 因 low_trust 保持 draft（决策人选项 A，pc-0025～pc-0030 计 miss）；`as_of` 2026-09-20；K=20；并发 1；预热 5 遍、测量 10 遍；查询顺序按 `seed 20260920 + pass_index` 洗牌；配对 bootstrap 10,000 次、种子 20260920。

| 候选 | 镜像/服务器 | 索引版本 | 分词器版本 | 词典版本 |
| --- | --- | --- | --- | --- |
| A | 开发集群 pgvector/pgvector:pg16@sha256:ccc6e83d…4d6b | `pg-simple-fts-v1` | `tok-jieba-v1` | `jieba-0.42.1+default` |
| B | `medy-dec001-b:zhparser2.3-scws1.2.3`（本地 ID `00ce3abb08cc`） | `pg-zhparser-fts-v1` | `zhparser-2.3+scws-1.2.3+cfg-dec001_b:8d420cfb+guc:3ff9eb8a` | `scws-dict-utf8:fd76a689…+rules-utf8:45395f79…+scws-1.2.3` |
| C | `medy-dec001-c:pg16-pgsearch-0.25.9-r28`（本地 ID `f564d490dfa0`） | `pg-search-bm25-v1` | `pg_search-0.25.9+pdb.jieba:6c256ba3` | `jieba-rs-0.10.1+tantivy-jieba-0.20.0+pg_search.so:74e90e4f…` |

**硬门禁 1、2（严格宏平均 Lexical Recall@20 ≥90%，六切片各 ≥85%）：**

| 候选 | 宏平均 | drug_name_zh (18) | dose_unit (20) | negation (41) | time_window (20) | protocol_id (17) | mixed_zh_en (53) | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 48.0% | 55.6% | 80.0% | 41.5% | 35.0% | 41.2% | 43.4% | 未通过 |
| B | 52.0% | 77.8% | 85.0% | 48.8% | 40.0% | 35.3% | 41.5% | 未通过 |
| C | 53.3% | 77.8% | 90.0% | 51.2% | 45.0% | 29.4% | 43.4% | 未通过 |

**硬门禁 3～5：** 管理侧逐 chunk 核对，三候选跨部门泄漏为 0；候选不足由适配器契约保证（分页 ≠ min(合格数, K) 即失败），本次运行 A/C 各 3 条查询合格候选少于 K 并显式 `candidate_exhausted=true`，B 为 0 条；版本不匹配拒绝已由集成测试证明；三候选 75 条 × 15 遍排名逐项一致。

**按部门与脚本变体：**

| 候选 | MA (30) | PV (29) | CO (16) | gold zh-Hans (10) | gold zh-Hant (33) | gold en (32) | drug_name_zh/zh-Hant (18) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 63.3% | 41.4% | 31.2% | 90.0% | 66.7% | 15.6% | 55.6% |
| B | 76.7% | 41.4% | 25.0% | 90.0% | 78.8% | 12.5% | 77.8% |
| C | 76.7% | 44.8% | 25.0% | 100.0% | 78.8% | 12.5% | 77.8% |

drug_name_zh 切片没有 zh-Hans 样本，繁体结果不证明简体达标（SPEC 第 3 节）。

**词法延迟（P95 最近秩，预热除外，750 次测量）：** A 17.2 ms、B 19.3 ms、C 92.2 ms（均值 7.3 / 9.2 / 41.7 ms）。C 的 P95 为 A 的 5.4 倍，超过选择规则的 25% 上限。

**相对 A 的配对提升（pp，query 级 bootstrap 95% CI）：** B +4.0 [−1.3, +10.7]；C +5.3 [−1.3, +12.0]。两者 CI 均包含 0，不满足"≥5pp 且下界 >0"。端到端 Recall@5、端到端 P95 与独立许可证审核未在本次评估；C 仍为 `release_blocked`。

**未命中归因（`miss_diagnostics.json`，只读复算，不调参）：**

| 候选 | 未命中 | gold 合格但名次 >20 | gold 与查询无词元重叠 | esomen 隐藏（选项 A） | unmappable |
| --- | --- | --- | --- | --- | --- |
| A | 39 | 21 | 10 | 6 | 2 |
| B | 36 | 18 | 10 | 6 | 2 |
| C | 35 | 17 | 10 | 6 | 2 |

主要失败面是 gold 文档为英文的 32 条样本（PV/CO 指南，查询为中文加英文术语）：三候选在该子集的召回为 12.5%～15.6%。中文查询词元在英文条款中不存在，能重叠的只有 `ICH`、`GVP`、`module`、`E2A` 等出现在数百个 chunk 里的通用词元，因此 gold 要么不合格，要么名次远在 20 之外。这是词法阶段对跨语言查询的固有限制，而不是某个 tokenizer 的缺陷；zh-Hant 仿單子集上 B/C（78.8%）优于 A（66.7%），说明 jieba 默认词典对繁体药名切分更差。

**必须记录的结构性上限：** 选项 A 下 esomen 的 6 条与 2 条 unmappable 共 8 条必然 miss，宏平均上限为 67/75 = 89.3%，低于 90% 门禁。本次三候选在 48%～53%，上限不是失败原因，但任何重跑要有通过的可能，必须先解决这 8 条（esomen 重新解析入库；unmappable 两条需要切分器决策并重生成映射，见 SPEC 第 6 节）。

**结论：** 按预登记规则，三个候选均未通过硬门禁，DEC-001 与 M1 保持阻塞，不降低门禁，不选型。后续路径需要决策人另行决定并作为新的预登记实验：（1）保持词法门禁不变，承认跨语言样本由后续向量阶段承担，为词法门禁另建查询语言与文档语言一致的探针版本，跨语言样本单独报告；（2）为候选增加双语医学词典或查询改写（`custom_dictionary`/`query_rewrite` 目前均为 false），作为新变体完整重跑；（3）先解决 esomen 与两条 unmappable 再重跑同一实验（只能消除上限问题，不会改变跨语言失败面）。

复现命令（仓库根，B/C 服务器 DSN 来自本机 `.env.dec001`）：

```sh
make activate-docs PLAN=evals/experiments/lexical/preparation-v1/activation_plan.proposed.json ACTOR=reviewer-01 ADMIN_URL=<各服务器管理 DSN>
env -u DEBUG -u PYTHONPATH venv/bin/python -m medops.evals.experiments.dec001_run \
  --out evals/experiments/lexical/runs/<new-run-id> --as-of 2026-09-20 --purpose "M1-05 comparison"
env -u DEBUG -u PYTHONPATH venv/bin/python -m medops.evals.experiments.dec001_report evals/experiments/lexical/runs/<new-run-id>
```

### 2026-09-20：第二次运行（修订 1，临时结果，探针 v2 未冻结）

运行目录 [evals/experiments/lexical/runs/2026-09-20-run2-provisional/](../../evals/experiments/lexical/runs/2026-09-20-run2-provisional/)（`run_manifest.json` SHA-256 `76e6ab0827061d3b87d30920a4dd2dbad3611ecdcb216a7dc21f1ce70b14e5ce`，Git HEAD `0ed131e`）。**临时结果的原因：** 32 条英文孪生查询已起草并打包，但 Codex/gpt-6-astra 的用量额度于 2026-09-20 耗尽（2026-09-26 21:00 重置），LLM 第二复核无法执行，探针 v2 不能冻结；本次以冻结的探针 v1 为输入、按修订 1 的作用域计分，并把孪生查询作为独立叠加报告，不进入门禁。数据库为三服务器的 `medops_v2`（chunker-v2，16 份 active，esomen 经审计质量复核升为 trusted），语料指纹一致，映射 75 mapped / 0 unmappable。

**语言一致子集（43 条冻结样本：MA 30、PV 13、CO 0）硬门禁：**

| 候选 | 宏平均 | drug_name_zh (18) | dose_unit (20) | negation (23) | time_window (11) | protocol_id (5) | mixed_zh_en (21) | 泄漏 | 可复现 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 81.4% | 66.7% | 90.0% | 82.6% | 72.7% | 80.0% | 95.2% | 0 | 是 |
| B | 93.0% | 94.4% | 95.0% | 95.7% | 90.9% | 80.0% | 95.2% | 0 | 是 |
| C | 95.3% | 88.9% | 100.0% | 95.7% | 90.9% | 100.0% | 100.0% | 0 | 是 |

v1 的语言一致子集本身不满足修订 1 的最低数量（CO 0 条、PV 13 条、protocol_id 5 条），因此本次不能判定任何候选通过硬门禁；这正是需要探针 v2 孪生样本的原因。A 的宏平均 81.4% 与 drug_name_zh 66.7% 即使在补齐样本后也难以达到门禁；B、C 的宏平均已超过 90%，各切片除样本不足的 protocol_id 外均 ≥85%。

**跨语言子集（32 条，不设门禁）：** A 15.6%、B 12.5%、C 12.5%，与第一次运行一致。

**临时叠加（32 条未复核英文孪生查询，评分对照父样本 gold）：** A 59.4%、B 59.4%、C 90.6%；语言一致 + 孪生（75 条）：A 72.0%、B 78.7%、C 93.3%。归因（`miss_diagnostics.json`，只读）：全部未命中都是 gold 合格但名次 >20，无"无词元重叠"；A/B 孪生未命中 13 条，其合格候选中位数 1,558 条，因为 `simple` 配置保留 `under/what/are/the` 等英文停用词而 `ts_rank_cd(normalization=0)` 不做 IDF 加权；C 的 BM25 对停用词自动降权，未命中 3 条。该现象由预登记配置决定，不在看到结果后调整；若要处理，须作为新变体预登记（例如 A/B 查询侧停用词表或 ts_rank 归一化选项）。

**相对 A（语言一致 43 条，配对 bootstrap）：** B +11.6 pp [+2.3, +20.9]，C +14.0 pp [+4.7, +25.6]；词法 P95 A 43.8 ms、B 41.6 ms、C 44.6 ms（本次每查询返回满 20 条，绝对值高于第一次运行，三者相当）。C 仍为 `release_blocked`；端到端 Recall@5/P95 与许可证审核未评估。

**状态：** DEC-001 仍阻塞。正式判定等待：（1）gpt-6-astra 额度恢复后完成孪生批次 `EN` 的第二复核；（2）annotator-01 确认 32 条英文查询；（3）冻结探针 v2 并按同一清单重跑；届时硬门禁在 75 条语言一致样本上计算。

### 2026-09-20：第二次运行（修订 1，正式结果，探针 v2 已冻结）

运行目录 [evals/experiments/lexical/runs/2026-09-20-run2-final/](../../evals/experiments/lexical/runs/2026-09-20-run2-final/)（`run_manifest.json` 查询前写出；`results.json`、`evaluation.json`、`report.md`、`miss_diagnostics.json`）。输入：探针 v2（spec-v1.1，107 条 = v1 的 75 条 + 32 条英文查询孪生，`dataset_hash 1fc5089f6fa7f80a1a5e23940826b0d4c811cde29e225dd8305241a33beb0321`，冻结于 2026-09-20），全部 107 条由固定模型 `claude-opus-5`（reviewer-llm-02，Claude Code CLI）统一第二复核，annotator-01 于 2026-09-20 确认 32 条英文孪生并裁决全部争议（三轮共 12 条 `disputed_resolved`）。数据库为三服务器的 `medops_v2`（chunker-v2，16 份 active）；映射 105 mapped / 2 unmappable（pc-0070-g1 与其孪生 pc-0102-g1：按裁决扩长后的 key_text 跨越 chunk 边界，按规则计 miss，不改切分器与样本）。测量参数与第一次运行相同。

**语言一致子集（75 条：MA 30、PV 29、CO 16）硬门禁：**

| 候选 | 宏平均 | drug_name_zh (18) | dose_unit (19) | negation (38) | time_window (19) | protocol_id (17) | mixed_zh_en (53) | 泄漏 | 可复现 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 69.3% | 66.7% | 89.5% | 68.4% | 73.7% | 64.7% | 69.8% | 0 | 是 | 未通过 |
| B | 76.0% | 94.4% | 94.7% | 73.7% | 84.2% | 64.7% | 69.8% | 0 | 是 | 未通过 |
| C | 88.0% | 88.9% | 100.0% | 94.7% | 94.7% | 70.6% | 86.8% | 0 | 是 | 未通过 |

最低数量全部满足（每部门 ≥15、每切片 ≥8、zh-Hans 10）。C 距宏平均门禁差 2.0 个百分点，protocol_id 切片 70.6% 未达 85%；B 与 A 在宏平均与多个切片未达。

**跨语言子集（32 条，不设门禁）：** A 15.6%、B 12.5%、C 12.5%。**全部 107 条：** A 53.3%、B 57.0%、C 65.4%。

**未命中归因（语言一致子集，`miss_diagnostics.json`）：** A 23 条（英文孪生 14、中文 9）、B 18 条（14、4）、C 9 条（6、3）；除各 1 条 unmappable 外全部为“gold 合格但名次 >20”，无“无词元重叠”。A/B 在英文孪生上的差距沿袭临时运行的结论：`simple` 配置保留英文停用词而 `ts_rank_cd` 无 IDF 加权；C 的 BM25 不受影响。C 的 protocol_id 未命中集中在英文孪生（pc-0095、0096、0100、0101）。

**相对 A（75 条配对 bootstrap）：** B +6.7 pp [+1.3, +13.3]，C +18.7 pp [+8.0, +29.3]，均满足“≥5 pp 且 CI 下界 >0”；词法 P95 A 37.5 ms、B 37.9 ms、C 32.8 ms（C 均值 29.0 ms 最高，P95 最低）。C 仍为 `release_blocked`；端到端 Recall@5/P95 与许可证审核未评估。

**结论：** 按修订 1 的预登记判据，三候选均未通过硬门禁，DEC-001 与 M1 保持阻塞，判据不降低，不选型。可供决策人考虑的下一步（均须新的预登记）：（1）为 A/B 增加查询侧英文停用词处理或 `ts_rank` 归一化选项作为新变体；（2）C 的许可证审核，因为即使 C 通过技术门禁也不能在 `release_blocked` 下选入；（3）pc-0070/pc-0102 的 key_text 长度与切分边界问题在下一版探针处理。

复现：`sh evals/experiments/lexical/tools/run2_final.sh`（需本机 `.env.dec001` 与三服务器 `medops_v2`）。

### 2026-09-20：第三次运行（修订 2，英文停用词变体 A2/B2，正式结果）

运行目录 [evals/experiments/lexical/runs/2026-09-20-run3-stopword-variants/](../../evals/experiments/lexical/runs/2026-09-20-run3-stopword-variants/)。输入与第二次运行相同（冻结探针 v2、`medops_v2`、chunker-v2 映射 105/2、K=20、预热 5、测量 10、种子 20260920）；新增 A2（`tok-jieba-v2`，索引 `lexical_index_a2`）与 B2（`dec001_b2`，索引 `lexical_index_b2`），A、B、C 原样同场重跑，结果与第二次逐项一致。

**语言一致子集（75 条）硬门禁：**

| 候选 | 宏平均 | drug_name_zh (18) | dose_unit (19) | negation (38) | time_window (19) | protocol_id (17) | mixed_zh_en (53) | 泄漏 | 可复现 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 69.3% | 66.7% | 89.5% | 68.4% | 73.7% | 64.7% | 69.8% | 0 | 是 | 未通过 |
| A2 | 77.3% | 66.7% | 89.5% | 81.6% | 84.2% | 70.6% | 81.1% | 0 | 是 | 未通过 |
| B | 76.0% | 94.4% | 94.7% | 73.7% | 84.2% | 64.7% | 69.8% | 0 | 是 | 未通过 |
| B2 | 80.0% | 94.4% | 94.7% | 81.6% | 89.5% | 64.7% | 75.5% | 0 | 是 | 未通过 |
| C | 88.0% | 88.9% | 100.0% | 94.7% | 94.7% | 70.6% | 86.8% | 0 | 是 | 未通过 |

**相对 A（配对 bootstrap，pp）：** A2 +8.0 [+2.7, +14.7]；B +6.7 [+1.3, +13.3]；B2 +10.7 [+2.7, +18.7]；C +18.7 [+8.0, +29.3]。**词法 P95：** A 38.0 ms、A2 21.3 ms、B 39.2 ms、B2 22.1 ms、C 32.9 ms（停用词移除使合格候选中位数从 A 718 / B 1,532 降到 A2 213 / B2 478，延迟随之下降）。跨语言子集不变（A/A2 15.6%，B/B2/C 12.5%）。

**归因（`miss_diagnostics.json`）：** 语言一致子集未命中 A 23 → A2 17（英文 14 → 8），B 18 → B2 15（英文 14 → 11），C 9；仍全部为"合格但名次 >20"。停用词移除消除了功能词稀释，剩余差距来自 `ts_rank_cd` 对语料中高频内容词（如 study、protocol、data）无 IDF 加权，以及繁体药名的切分（A 族 drug_name_zh 66.7% 不受停用词影响）。

**结论：** A2、B2 均较基线显著提升且延迟更低，但仍未通过硬门禁；C 不变。三次预登记运行后无候选通过，DEC-001 与 M1 保持阻塞，判据不降低。已穷尽"不改排序函数"的低成本变体；若继续，需要决策人预登记涉及排序的变体（例如 A/B 的 `ts_rank_cd` 归一化选项、或应用层 IDF 加权），或接受词法阶段由向量阶段补齐的架构含义并转向 M1 其余切片。C 的许可证审核材料见 [licence dossier](../reviews/2026-09-20-licence-dossier-pg-search.md)。

### 2026-09-20：端到端运行 `2026-09-20-e2e-hybrid-v1`（修订 3 的判定输入，无重排）

配置：词法 A2（5432/medops_v2）或 B2（5433/medops_v2）+ 同库 bge-m3 向量通道（ADR-0007），RRF k=60 融合各自 top-20，融合 top-20 在应用角色身份事务内经 M1-18 事实回查后取 top-5；探针 v2 107 条（每条 1 个 gold，故 Recall@5 = Hit@5）；2 预热 + 3 计量 pass。

| 系统 | Recall@5 全部 | language_matched | cross_lingual | 融合 Recall@20 | 词法单独 R@5 | 向量单独 R@5 | P95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A2+V | 54.2% | 64.0% | 31.2% | 79.4% | 38.3% | 70.1% | 164.9 |
| B2+V | 58.9% | 69.3% | 34.4% | 79.4% | 41.1% | 70.1% | 186.1 |

配对 bootstrap（B2+V − A2+V，Recall@5，10,000 次重采样）：+4.67 pp，95% CI [−1.87, +11.21]。泄漏 0、不可复现 0、失效版本引用 0/535、回查丢弃 0（索引已在查询内过滤状态与窗口）。

观察：未加权 RRF 把较弱的词法通道噪声混入 top-5，融合后的 Recall@5（54–59%）低于向量单独（70.1%），而融合 Recall@20（79.4%）高于任一通道；这正是设计中由 Reranker 承担 top-5 精度的位置，见下一条回填（带 ADR-0007 重排的运行）。

### 2026-09-20：端到端运行 `2026-09-20-e2e-hybrid-rerank-v1`（带 ADR-0007 重排）

同上配置，融合 top-20 回查后由 bge-reranker-v2-m3 重排（输出 8）再取 top-5；1 预热 + 1 计量 pass。Recall@5：A2+V **75.7%**（language_matched 81.3%、cross_lingual 62.5%），B2+V **75.7%**（82.7% / 59.4%）；配对 bootstrap B2+V − A2+V = **+0.00 pp，95% CI [−2.80, +2.80]**；泄漏 0、不可复现 0、失效版本引用 0；P95 7.6–8.9 s（CPU 重排主导）。基线 M1-21 的 85% 门禁在探针规模未通过；差距集中在 CO 英文文档与 protocol_id。

## 最终判定（2026-09-20，决策人授权实施方作出）

DEC-001 选定 **A2**（PostgreSQL `simple` FTS + 应用侧 `tok-jieba-v2` + 固定英文停用词表，`retriever_version=pg-simple-fts-v1`）为生产词法引擎。理由：B2 在两种端到端配置下均未达到预登记的选择规则（≥5 pp 且 CI 下界 >0），规则要求选择最简单实现；A2 只需标准 PostgreSQL 与 MIT 许可的 jieba；C 已按修订 4 排除。生产接线见迁移 0007 与 `medops.retrieval.production`（复合 `retrieval_version 90b57e4e…ab18`，实现记录 45）。B2 在繁体药名切片上的优势记为主评测集（M1-20）上的复核项；若届时满足选择规则可另行修订。

## 后果

- 上层检索、RRF、Reranker 和业务契约保持稳定；具体词法实现通过适配器隔离。
- M1 多一个小规模选型实验，但避免在主数据入库后更换 tokenizer 和重建索引。
- 选定实现后仍必须在不少于 300 条的主评测集上通过最终门禁；探针集并入主集，但继续保留固定版本和独立报告。
