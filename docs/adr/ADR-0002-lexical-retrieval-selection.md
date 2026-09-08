# ADR-0002：词法检索实现选择实验预登记

| 项 | 内容 |
| --- | --- |
| 状态 | 协议已决；生产实现待 M1 入口实验 |
| 日期 | 2026-09-03 |
| 最后修订 | 2026-09-08：复核方式、gold 命中规则与切片门禁作用域按第五轮审核记录修订 |
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
- MA、PV、CO 每个部门不少于 15 条；语料只用公开文档；样本和 gold 由人工标注并经 LLM 独立复核，manifest 如实记录复核者类型，不等同于两名独立人工复核。
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

## 结果回填

M1 实验完成后在本节追加：探针集版本与哈希、候选版本/镜像 digest、各指标与置信区间、RLS/候选数测试、许可证结论、最终选择和复现命令。回填不得删除本次预登记内容。

当前状态：尚未运行，无生产实现选择。

## 后果

- 上层检索、RRF、Reranker 和业务契约保持稳定；具体词法实现通过适配器隔离。
- M1 多一个小规模选型实验，但避免在主数据入库后更换 tokenizer 和重建索引。
- 选定实现后仍必须在不少于 300 条的主评测集上通过最终门禁；探针集并入主集，但继续保留固定版本和独立报告。
