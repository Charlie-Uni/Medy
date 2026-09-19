# 实现记录 10：LexicalRetriever 调用边界与适配器契约测试（M1-03）（2026-09-11）

按基线第 9 节交付格式。范围：M1-03。不实现生产检索，不替代真实数据库验收。**状态：自审已做，待 Codex 审核。**

## 完成

| 产物 | 内容 | 对应条款 |
| --- | --- | --- |
| `retrieval/contracts.py` | 新增 `LexicalVersions`（retriever、tokenizer、dictionary、normalization 四元组）与 `LexicalRetriever` Protocol（`versions` 属性 + `search(query, k)`）；`LexicalSearchResult` 增加 `raw_score` 沿排名非递增的校验与 `versions` 属性 | ADR-0002 统一契约；基线 3.6 |
| `retrieval/lexical/boundary.py` | `run_lexical_search`：k 在 1 到 20 之间、规范化后非空的 query；期望版本与索引版本不一致时抛 `BusinessError(version_conflict)`；适配器返回的版本或 `requested_k` 与声明不符时抛 `InfrastructureError(internal_error, retryable=False)`，失败关闭 | 基线 3.6、4.4、5.3 |
| `retrieval/lexical/bm25_offline.py` | 暴露 `versions` 属性以满足 Protocol | |
| `tests/unit/retrieval/lexical_contract.py` | 可复用的适配器契约：确定性、版本一致、来源于给定语料、排名连续且分数单调、k 语义（k=1、耗尽标记）、边界的版本拒绝；后续 DEC-001 候选 A/B/C 直接复用 | ADR-0002 硬门禁 4、5 |
| 测试 | `test_lexical_boundary.py`（边界 4 组）、`test_offline_bm25_contract.py`（离线 BM25 在 regex 与 jieba 两种分词器下通过契约） | |

## 自审（基线第 9 节）

1. 需求：只做调用边界与契约测试；未接数据库、未做权限过滤（语料由调用方经数据库授权后提供）。
2. 逻辑：版本比较用模型相等；适配器违约与调用方错误分属基础设施错误与业务错误，不混淆。
3. 安全：版本冲突的公开文案不含内部版本串，细节进 detail。
4. 契约：`LexicalSearchResult` 新增的分数单调校验会让乱序适配器在模型层即失败。
5. 测试：正常、边界（k 上下限、空 query）、失败（版本不匹配、适配器撒谎两种）。
6. 可观测：无新增运行时路径。
7. 简洁性：无新抽象层；契约测试放在 tests 目录，不随包发布。
8. 验证：见下。
9. Checklist：不勾选 M1-03，缺 DEC-001 候选适配器与真实语料上的运行证据。

## 验证

```text
env -u PYTHONPATH make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!
  mypy                    -> Success: no issues found in 35 source files
  pytest -q               -> 199 passed（本轮新增 7 项）
  contracts_export --check-> schemas up to date
```

## 待 Codex 审核的重点

1. 版本不匹配归为 `version_conflict`（业务/409）是否合适，或应视为部署配置错误归基础设施类。
2. 契约测试要求 `raw_score` 沿排名单调，对分数非数值可比的候选（如 FTS 的 ts_rank）是否过严。
3. 边界未做权限过滤是否需要在签名上显式表达“已授权语料”，避免误用。

## 第二版：按 Codex 审核修订（2026-09-11）

Codex 结论为“暂不通过，四组问题”。全部修复；三个审核问题按结论处理。**状态：待 Codex 复核。**

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| 版本检查未绑定实际建索引版本：换分词器不重建仍被接受；适配器在 search 内改版本也能通过 | `OfflineBM25Index.index()` 记录建索引时的版本快照，`versions` 返回快照；查询时当前配置与快照不一致抛不可重试内部错误，重建后才更新。边界在调用前固定 `declared = retriever.versions`，返回结果与该快照比较；`expected` 改为必填，来自本次执行固定的配置 | `test_tokenizer_swap_without_rebuild_is_refused_and_rebuild_updates_versions`、`test_expected_versions_are_mandatory_and_checked_against_the_index_build` |
| 结果模型放行不合法数据：NaN/Infinity、frozen 未冻结内部列表、同分乱序 | `raw_score` 限定有限值并在模型级 `allow_inf_nan=False`；`candidates` 改为不可变元组；同分必须按 `chunk_id` 升序；边界对返回结果 `model_validate(model_dump())` 重校验，绕过校验的 `model_construct` 结果同样被拒 | `test_result_model_rejects_non_finite_scores_bad_order_and_is_immutable`、`test_adapter_contract_violations_fail_closed[count]` |
| 契约测试不能验证候选数量 | 夹具改为已知匹配数的合成语料（alpha 1、beta 3、gamma 7、delta 25，ASCII 词元在所有分词器下一致），覆盖零匹配、少于/等于/多于 K 与同分排序；用“只返回第一条”的适配器证明契约会失败 | `test_offline_bm25_satisfies_the_adapter_contract[regex|jieba]`、`test_contract_harness_detects_undercounting_adapters`、`test_fixture_corpus_is_well_formed` |
| k 类型边界不完整：True 被当作 1，1.5 触发 TypeError | 调用边界做严格整数检查（排除 bool 与浮点）并统一返回 `invalid_request`；离线索引内部同样拒绝，但作为内部函数抛 `ValueError` | `test_request_bounds_and_strict_integer_k`（0、21、True、1.5、"5"） |

审核问题结论：调用方指定版本的前置冲突保留 `version_conflict`，服务端配置漂移与适配器违约为不可重试内部错误；分数单调保留；不新增仅有名字的授权类型，Protocol 与边界文档区分离线预授权语料与生产事务内过滤。文档收尾：`MAX_K=20` 注明来自 ADR-0002 实验设置而非 Reranker 上限；记录 09 首段的直接延期表述标为历史。

验证：`env -u PYTHONPATH make check` 通过；pytest 203 passed（本轮新增 4 项，重写 7 项）。

## 第三版：收口两条失败路径（2026-09-11）

Codex 复核确认上一轮反例已修复，剩余两处失败路径与两处收尾。**状态：待 Codex 复核。**

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| 重建失败后半成品仍可查询：`index()` 先清空再写入，最后才更新统计与版本；首次构建失败后查询触发 ZeroDivisionError | 改为全部在局部结构中构建，全部成功后才一次替换 postings、文档长度、平均长度与版本快照；失败时旧索引与版本完全保留，首次失败时索引为空且可查询 | `test_failed_first_build_leaves_an_empty_queryable_index`、`test_failed_rebuild_keeps_the_previous_index_and_versions_intact` |
| 适配器内部构造非法结果抛原始 `ValidationError` | `retriever.search()` 纳入现有 `ValidationError` 捕获并转为不可重试内部错误；适配器自身抛出的业务/基础设施错误保持原类型，不扩大为捕获全部异常 | `test_validation_error_inside_the_adapter_becomes_a_non_retryable_internal_error` |
| 缺“调用中变更声明版本”的真实回归 | 新增在 `search()` 内改变 `versions` 属性并以新版本盖章结果的适配器，边界按调用前快照拒绝 | `test_versions_changed_during_the_call_are_rejected_against_the_pre_call_snapshot` |
| 记录文案“统一返回 invalid_request”范围过宽 | 限定为调用边界；离线索引内部仍抛 `ValueError` | 文档 |

验证：`env -u PYTHONPATH make check` 通过；pytest 207 passed（本轮新增 4 项）。

复核结论（2026-09-11，Codex）：第三版两处失败路径与两处收尾关闭，无新阻塞项；M1-03 标为“契约切片已复核通过”，整项不勾选（生产适配器、真实数据库权限验证与语料实验未完成）；“原子化”仅指失败时不发布半成品，不代表并发重建安全，当前不加锁。非阻塞测试修正已做：k=0 的误注释改为真正抛错的适配器透传测试（BusinessError 与 InfrastructureError 原对象透传）。
