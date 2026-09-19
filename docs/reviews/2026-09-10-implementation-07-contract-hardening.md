# 实现记录 07：领域契约加固 D-01 到 D-06（2026-09-10）

按基线第 9 节交付格式。来源：Codex 对实现记录 05 的六项发现（五项领域契约、一项文档门禁）。与 M0-05 第三版分批提交，本批独立复检。**状态：待 Codex 复核。**

## 完成

| 编号 | Codex 发现 | 修复（`src/medops/domain/state.py` 除注明外） | 回归测试（`tests/unit/domain/test_agent_state_hardening.py`） |
| --- | --- | --- | --- |
| D-01 | 答案引用只比对 chunk_id，伪造 doc_id/version/page 仍通过 | 答案的每条 `Citation` 必须与本次 Evidence 的 `Citation` 逐字段相等（模型相等比较） | 参数化篡改 doc_id、version、page、section 各自失败 |
| D-02 | `not_supported` 要素留在答案中仍通过；supported 指向不存在的证据通过 | 答案门禁：`verify_result.unsupported` 非空即拒绝；只要存在 `verify_result`，其引用的 `evidence_chunk_id` 必须属于本次 Evidence（与是否作答无关）。不实现 NLI | `test_not_supported_elements_block_the_answer`、`test_supported_element_must_point_at_evidence_in_this_run` |
| D-03 | 无 Intent 或 high_risk 意图仍可作答 | 答案要求 `intent` 存在且 `intent.type != high_risk`；`risk=high` 的合法核验 Skill（如超说明书检查）仍可作答 | `test_answer_requires_intent_and_high_risk_intent_cannot_be_answered`、`test_high_risk_level_on_a_legitimate_skill_still_answers` |
| D-04 | `advance` 保留过期核验：改 query、证据或策略版本后旧 Verify/Safety/Answer 仍在 | 固定依赖表 `_DOWNSTREAM`（10 行，无框架）：上游字段实际变化时，同一调用未显式提供的下游字段重置为空；显式提供的值视为新鲜并重新校验；值未变不清空 | `test_changing_upstream_inputs_clears_downstream_results`、`test_downstream_supplied_in_the_same_call_is_kept_and_revalidated`、`test_unchanged_value_in_updates_does_not_clear_downstream` |
| D-05 | frozen 为浅冻结，`source_ranks` 字典可原地改，负数排名可往返 | 新增 `SourceRank(source, rank ≥ 1)`；`CandidateRef.source_ranks` 改为不可变元组并要求来源唯一；`retrieval/fusion.py` 的 `FusedCandidate` 同步改用该结构 | `test_candidate_ranks_are_immutable_and_positive`（原地赋值与 append 均失败、rank 0 拒绝、重复来源拒绝、JSON 往返） |
| D-06 | 一致性测试永久禁止勾选，未来有证据也会令 CI 失败 | 删除“零勾选”断言，保留数量、编号、汇总一致性检查；证据要求由审核流程执行 | `tests/unit/docs` 4 passed |

三个既有测试按新语义更新：无 intent 时先命中“需要意图”；更换 safety 或 verify 而不重新提供答案时，旧答案被清空而不是报错，要断言拒绝需显式重提答案。

## 约束

- 未新增依赖图框架；`_DOWNSTREAM` 是一张固定表，新增字段时手工维护。
- 未实现 NLI 或要素抽取；D-02 只约束状态表示。
- 未勾选任何 checklist。

## 验证

```text
env -u PYTHONPATH make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!
  mypy                    -> Success: no issues found in 28 source files
  pytest -q               -> 132 passed in 2.95s（本批新增 12 项、删除 1 项、净增 11 项：121 → 132）
```

## 风险

- `advance` 的清空规则依赖“值是否变化”的相等比较；对大证据集每次比较有开销，量级在契约层可接受。
- 无新增已知安全风险。

## 第二版：按 Codex 复核关闭 D-04 三处（2026-09-10）

D-01、D-02、D-03、D-05、D-06 已获复核关闭。D-04 剩余三处：

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| 相同值被误判为变化：比较一侧是字典、一侧可能是模型 | `advance` 先用每个字段的 `TypeAdapter` 把传入值验证成字段类型，再与当前对象按类型化值比较；模型对象、字典、列表只要验证后相等就不算变化 | `test_equivalent_inputs_in_any_representation_are_not_a_change`（模型 intent、模型 versions、模型元组 evidence、字典列表 evidence 四种等价输入均不清空） |
| 会话实体变化未使旧结果失效 | `session_entities` 加入依赖表，清空 intent 起的全部结果（意图抽取与查询改写都读取会话实体） | `test_changing_session_entities_clears_dependent_results` |
| 升级草稿过期：证据换成 c2 后 Escalation 仍引用 c1 | 依赖表中所有上游变化都清空 `escalation`；另加不变量：`escalation.evidence_chunk_ids` 必须属于当前 Evidence，显式重提过期升级即拒绝。只影响状态中的草稿，不涉及已持久化审计 | `test_stale_escalation_is_cleared_and_inconsistent_escalation_is_rejected` |

`advance` 文档写明：同一调用显式提供的下游值只是受信调用方声明已重算，不是核验已执行的证明；运行时执行验证属于 M2。

验证：`env -u PYTHONPATH make check` 通过；pytest 135 passed（本批新增 3 项）。**状态：待 Codex 复核。**
