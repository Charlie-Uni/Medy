# 实现记录 91：M5-04 零费用部分——成本档门禁、第一个上下文裁剪候选、模型路由的表达方式（评测待您确认余额）

日期：2026-09-26。承接决策 86（B.4：M5-04 作为 M4 策略候选逐个评测，先「上下文只放已验证句」再「简单问题路由到 gpt-6-luna」；C.5：合计 ≤ 15 美元，余额不足时先做零费用代码）。本记录只有代码与候选文件，没有花钱。

## 1. 问题：现有门禁不能评成本候选

记录 82 的门禁（`medops.loop.gate.compute_gate`）以「目标指标 +5 pp」为通过条件。成本候选的目标不是提高成功率，而是「同等质量下 Token 降低 ≥ 25%」（基线 5.11、M5-04）；用质量档门禁去评它，Δ ≈ 0 必然被拒（记录 90 的 rrf_k 候选正是这样被拒的）。

## 2. 做了什么

### 2.1 门禁增加 `profile="cost"`

- 目标改为每个主集条目的模型 token 数（三轮平均、两臂配对）：候选 ≤ baseline 的 75%（`TOKEN_REDUCTION_MIN = 0.25`）。
- 质量下限：总体成功率下降不超过 1 pp（`QUALITY_MIN_PP = −1.0`），与非目标切片已有的容差一致；95% CI 照常报告、不参与判定（基线 5.8）。
- 非目标切片、安全「最差一轮不下降」、可靠性（≥ 3 轮 / ≥ 200 条）三条规则不变。
- 报告里 `target.profile` / `thresholds.profile` 写明档位；`gate_report_valid` 不改，发布路由照样只认完整且通过的报告。质量档报告的形状不变（多了 `profile` 字段）。
- 顺带修一个浮点边界：切片恰好下降 1.00 pp（100 条里少 1 条）此前会因 `−1.0000000000000009 < −1.0` 被判阻断，现在先四舍五入再比较；规则文字本来就是「不超过 1 pp」。

单元测试 `tests/unit/loop/test_gate.py` 新增三项：成本档通过（−31% token、−0.5 pp）、成本档阻断（省 9.4% 或质量 −2 pp）、缺 token 映射 / 未知档位报错、质量档形状不变。

### 2.2 运行器

`replay_run.py` 从候选文件读 `gate_profile`（默认 quality），把每条主集条目的 `model_tokens` 按臂按轮交给门禁；报告的 Gate 段在成本档下写 token/条目与降幅。配合记录 90 的 `--baseline-from`，一个成本候选只跑候选臂：估算 6.42 美元。

### 2.3 第一个候选：`evals/replay/candidates/2026-09-26-context-rerank5.json`

`retrieval_params/hybrid` 的 `rerank_output: 8 → 5`，`gate_profile: cost`。理由：answer 提示词把重排后的全部证据段（现为 8 段）整段放入，证据是每条约 3,200 token 的主体（记录 90 baseline 臂实测）；只留前 5 段是现有发布目标能表达、不需新代码的最小裁剪。运行时与加载器已支持 `rerank_output` 发布（记录 80 / 85），`validate_diff` 对该候选通过。

这不是基线 5.11 字面的「只放通过验证的相关句」（句级裁剪）。句级裁剪要改 harness（在 answer 前按 `verify_evidence` 的相关句过滤证据文本，并保持 chunk 级引用），改动面大且会改变引用语义；先用零代码的段级裁剪测出 token 弹性与质量弹性，再决定是否做句级。

### 2.4 第二个候选（模型路由）的表达方式，尚未实现

「简单问题路由到 gpt-6-luna」不在现有发布目标内（`retrieval_params/hybrid`、`prompt/answer_system`）。需要新增目标 `model_route/answer`：diff 形如 `{"simple_model": "gpt-6-luna"}`，「简单」按 intent 类型判定（label_query 等单文档事实问句），在 answer 节点按 intent 选模型，`model_config_version` 随之变化并进 Trace；加载器校验模型白名单（ADR-0010）。约 150 行 + 测试。建议在第一个候选出结果后再做，因为若段级裁剪已达 25%，路由可以留作 P1。

## 3. 需要您决定

- 余额：您报 29 美元，记录 90 的评测花了 13.12，现约 16 美元。第一个成本候选约 6.4 美元；两个候选约 13 美元，跑完只剩约 3 美元，M5-03 正式验收前必须再充值。**是否现在跑第一个候选**（我建议跑；第二个等结果再定）。
- 成本档的质量下限取 −1 pp（与切片容差一致）：若您要求更严（例如点估计 ≥ 0），改一个常数即可，但会把噪声当退化。

## 4. §9 自审

- 成本档没有放松任何安全或切片规则；只替换了目标指标，并把质量作为下限而不是目标。
- token 只算主集条目（安全集条目走各自的检查，不在「固定质量集」内）；报告里的 `tokens` 列仍是两者之和，便于对账。
- 候选文件 `evidence.case_ids` 为空：`adapt submit` 现行规则要求引用 bad_case（记录 80），成本候选没有 bad_case 可引。评测通过后若要走发布流程，需要给 submit 加 `evidence.kind = "cost"` 的例外并记录——本记录不改。
- 未改 roadmap 状态与百分比（M5-04 仍待做）。

## 5. 文件

- `src/medops/loop/gate.py`：`profile` / token 目标 / 浮点边界；`tests/unit/loop/test_gate.py` +3 项
- `evals/replay/tools/replay_run.py`：`gate_profile`、token 映射、成本档报告行
- `evals/replay/candidates/2026-09-26-context-rerank5.json`（新）
