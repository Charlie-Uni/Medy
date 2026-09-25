# 实现记录 88：M5-02——五个 Skill 的功能、安全、权限、失败与故障测试矩阵

- 日期：2026-09-26
- 授权：决策请求记录 86（B 顺序第 2 项）
- 范围：`tests/unit/skills/test_matrix.py`（新，27 项参数化用例）；对既有单元测试与真实冒烟的矩阵归档
- 费用：0（真实冒烟引用 2026-09-23 的两次运行，未重跑）

## 1. 矩阵

五个已注册 Skill：`label_query`、`citation_verification`（低风险）、`ae_extraction`、`off_label_check`、`protocol_deviation`（中高风险）。每格给出证明它的测试；"矩阵" = `tests/unit/skills/test_matrix.py`。

| 维度 | 判据 | label_query | citation_verification | ae_extraction | off_label_check | protocol_deviation |
| --- | --- | --- | --- | --- | --- | --- |
| 功能 | 正确输入 → 结构化输出、引用带版本、结论只来自已验证条款 | `test_label_query::…returns_excerpts_with_versioned_citations` + 冒烟 v1 positive ×3 | `test_citation_verification::…verdicts_per_claim…` + 冒烟 v1 | `test_risk_skills::…keeps_grounded_elements…` + 冒烟 v2 positive | `test_risk_skills::…reports_scope_per_dimension…` + 冒烟 v2 outside / within | `test_risk_skills::…concludes_from_verified_clauses_only` + 冒烟 v2 deviation / no-deviation |
| 安全 | 输出层 3：任何个体用药建议被替换为空升级；注入证据被筛除；不陈述因果 | 矩阵 `no_output_carries_individual_advice`（回答含建议 → 升级、无文本） | 矩阵（建议作为陈述文本）+ 既有 `screened_evidence` | 矩阵（元素值含建议）+ 既有「不陈述因果」+ 冒烟 v2 injected-narrative | 矩阵（note 含建议）+ 既有 `refuses_advice…` | 矩阵（rationale 含建议） |
| 权限 | 缺 read scope → `forbidden`，发生在任何检索 / 模型调用之前；固定部门的 Skill 拒绝其他部门 | 矩阵 `permission_is_checked_before_any_model_call` + 既有 `caller_without_read_scope…` + 冒烟 scope-denied | 矩阵 | 矩阵 ×2（scope、他部门）+ 冒烟 wrong-dept | 矩阵 ×2 + 冒烟 wrong-dept | 矩阵 ×2 + 冒烟 wrong-dept |
| 失败 | 输入违反 schema → `schema_violation`，不进 handler；无证据 → `insufficient_evidence`，不调模型 | 矩阵 ×2 + 既有 `input_schema_is_enforced` + 冒烟 schema-violation | 矩阵 schema + 既有 `claims_are_capped_and_ids_required` | 矩阵 schema + `without_grounded_elements_is_insufficient_evidence` | 矩阵 ×2 | 矩阵 ×2 |
| 故障 | 供应商超时 / 证据存储不可用 → 有界重试后 `system_failure` 升级，输出不含任何结论 | 矩阵 `provider_fault_is_a_bounded_system_failure`（answer 超时 ×3） | 矩阵（证据查询抛 `dependency_unavailable`） | 矩阵（skill 调用超时 ×3） | 矩阵（skill 调用超时 ×3；只剩固定免责声明） | 矩阵（同左，`undetermined` / `none`） |

注册表层的通用保证另有 `test_registry.py`（默认拒绝、scope 先于 schema、超时只对幂等 Skill 重试、输出契约违规为内部错误、并发只跑 parallel-safe）与 `test_no_bypass.py`（实现只经注册表可达）。

## 2. 矩阵测试写法

- 全部走 `default_registry().execute()`，假网关按 purpose 脚本化；权限用例的网关**没有脚本**，任何模型调用都会炸——证明拒绝先于调用。
- 无证据用例用空检索 + 无脚本网关：结论必须是 `insufficient_evidence` 且 reason code 里没有 `system_failure`。
- 故障用例：`ModelTimeout` ×6 脚本在 Skill 自己的 purpose 上，harness 的 `answer` 有 6 份正确回复（每次重试都会重跑 harness），从而把故障隔离在 Skill 调用；断言 `escalated` + `system_failure`、attempt ≤ 3、渲染文本里只允许固定免责声明或 `undetermined` / `none`。
- 安全用例把建议句「您应该每天服用 100 mg」种进各自的自由文本字段；断言任何渲染文本都不含它，若升级则文本为空。

## 3. 顺带发现

`off_label_check` / `protocol_deviation` 在 harness 阶段抛异常时会由 handler 自己包成 `escalated system_failure`，但仍带固定免责声明与 `undetermined`（矩阵第一版按「空文本」断言而失败）。这不是缺陷——免责声明不是结论——已在矩阵里写成允许的白名单，并在本记录留痕。

## 4. 进度

- M5-02 → **已实现**。
- P0 加权进度 75.9% → **77.2%**（61/79）；按 99 项计 61.6%；M5 3/8。
