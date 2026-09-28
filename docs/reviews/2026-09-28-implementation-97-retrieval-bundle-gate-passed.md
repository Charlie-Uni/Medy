# 实现记录 97：四合一检索候选通过发布门禁——第 3 轮补跑、续跑缺陷修复与费用核算

日期：2026-09-28。运行 `evals/harness/runs/2026-09-26-replay-eval-v2-retrieval-bundle`（候选 `evals/replay/candidates/2026-09-26-retrieval-bundle.json`：词表 glossary-20260926-e4daca58a8e4 + multi_query + doc_focus + query_translation gpt-6-luna；baseline 臂复用 rrf40 运行；记录 94）。决策人 2026-09-28 批准约 2 USD 补跑第 3 轮。

## 1. 结论

**门禁通过。** 目标指标 baseline 0.7117 → candidate 0.8083，Δ +9.67 pp，95% CI [5.5, 13.83]，门槛 +5 pp；17 个非目标切片无一下降超过 1 pp（最小 +1.39 pp，`language=zh` +22.2 pp 为诊断性切片）；9 个安全类目最差轮全部与 baseline 相等（numeric_trap 0.9 = baseline 0.9）；可靠性三轮 × 200 条完整；最终 2,178 行中 system_failure 为 0。

| 臂 | 轮 | 成功率 | 安全通过 | P95 s | 系统失败 |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 / 2 / 3 | 0.715 / 0.700 / 0.720 | 1.0 / 0.994 / 1.0 | 25.6 / 22.7 / 19.0 | 0 / 0 / 0 |
| candidate | 1 / 2 / 3 | 0.825 / 0.805 / 0.795 | 1.0 / 1.0 / 0.994 | 18.9 / 24.1 / 22.2 | 0 / 0 / 0 |

分部门：CO +5.66、MA +11.29、PV +10.98 pp；切片：drug_name_zh +13.7、time_window +12.2、protocol_id +11.9、dose_unit +13.3、negation +7.5、mixed_zh_en +8.0 pp。这与记录 92–94 的离线诊断方向一致（点名文档定位、跨语言查询翻译）。时延：候选 P95 与 baseline 同量级，第 2 轮 P50 18.0 s 偏高（与本机其他负载重叠，见 §3）。

## 2. 补跑过程与发现的运行器缺陷

1. 首次续跑（`--resume --baseline-from rrf40 --max-cost-usd 3`，caffeinate）重做了第 3 轮 200 条主集行与 baseline 臂遗留的 7 条 system_failure 行，费用 1.06 USD；结果目标指标已过，但安全类目仍为 0。
2. 原因：`replay_run.py` 的续跑规则只在主集循环里对 `system_failure` 行重做，安全集循环是 `if key in done: continue`，塌掉那轮的 87 条安全行被原样保留。修复：抽出 `needs_run(done, key)`（缺失或 `system_failure` 才重做），主集与安全集共用；回归测试 [test_replay_resume.py](../../tests/unit/evals/test_replay_resume.py) 两项（规则本身；两个循环都用同一规则、不再出现裸 `key in done`）。
3. 第二次续跑重做 87 条安全行，费用 0.60 USD，门禁通过。

## 3. 费用与可靠性核算

- 候选臂最终有效行（每个 arm/run/replay_id 取最后一次）的行内费用合计 6.79 USD；三次会话的网关计费 5.20 + 1.06 + 0.60 = 6.86 USD，差额 0.07 USD 是未归属到行的调用（查询翻译预热等）。塌轮的 138 + 87 条 system_failure 行几乎没有模型调用，沉没成本 <0.01 USD；塌轮里已成功的行被保留，没有重付。`results.json.total_cost_usd` 只记最后一次会话的 0.60，是运行器的已知口径，未改。决策人批准的「约 2 USD」补跑实际 1.66 USD。
- 09-26 的塌轮由合盖睡眠引起（pmset 14:16 Clamshell Sleep，[[feedback-macos-sleep-long-runs]] 再次验证）；本次两段补跑均在 caffeinate 下、盖子打开。首次续跑期间曾与 `make check`（含连库集成测试）重叠约 80 秒、与页文本抽取 / 重下载并行，未产生系统失败。
- 与记录 90 的 rrf40 运行相比：本候选 baseline 臂复用（`--baseline-from`），只付候选臂。

## 4. 发布前的决策点（未执行）

按记录 94 §3.3 与 M4 流程，门禁通过后的下一步是 `adapt submit` → 审批 → 金丝雀 ≤10% → 24 h 观察 → 全量。阻碍：候选的 `evidence.kind=diagnostic`、`case_ids=[]`，而 `adapt submit` 要求 bad_case ids。需要决策人决定：

1. 是否为诊断型候选增加证据例外（代码改动约几十行，改 `medops.loop.adapt` 的证据校验并写 ADR 附录），还是把记录 92 归因的 60 条失败回放项登记为 bad_case 后再提交（更合规，工作量约半天）。
2. 发布对象：四个参数一起作为一个 `retrieval_params/hybrid` 发布，还是拆分（拆分需各自重新评测，约 6.4 USD 一个）。
3. 发布后主集与回放集需要按 `corpus_v2` 重冻结（记录 96 §7），检索基线随之变化；建议先入库、重冻结，再做金丝雀，避免两次基线漂移。

## 5. 文件

- `evals/replay/tools/replay_run.py`：`needs_run`；`tests/unit/evals/test_replay_resume.py`。
- 运行目录：`rows.jsonl`（append-only，含塌轮原始行）、`results.json` / `report.md`（最终）、`*.before-resume-2026-09-28.*`（塌轮时的报告快照）。

## 6. §9 自审

- 数字全部来自 `results.json` 与 `rows.jsonl` 重算；沉没成本如实列出。
- 门禁判据未改：+5 pp、非目标 ≤1 pp、安全不降、三轮完整。
- 缺陷修复只影响续跑选择哪些行重做，不改变计分。
- 发布未执行；证据例外与拆分与否留给决策人。
