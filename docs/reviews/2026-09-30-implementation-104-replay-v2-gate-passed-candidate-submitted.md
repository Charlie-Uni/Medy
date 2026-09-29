# 实现记录 104：replay-v2 重冻结与检索四件套门禁通过、候选提交

日期：2026-09-30（运行自 2026-09-29 18:55 起）。决策人充值 50 USD 并确认预算后，按记录 101 §5 / 103 §4 的顺序执行付费步骤；本记录是三次运行的结果与候选提交。批准与金丝雀待决策人。

## 1. 主集全量与安全集（记录 103 之后的第一步）

| 运行 | 结果 | 费用 |
| --- | --- | ---: |
| `evals/harness/runs/2026-09-29-full-ask-v3`（main-v3-provisional，614 条，gpt-6-sol 答题与判定，as-of 2026-09-29） | 有答案题作答率 84.6%、作答中引用 gold 77.0%、无答案题正确弃答 98.4%、有答案题误弃答 14.2%；P95 13.5 s；1 条 system_failure 经 `--resume` 补做后为 0 | 4.64 USD |
| `evals/harness/runs/2026-09-29-safety-v2`（安全集 170 条，as-of 2026-09-29） | 163 条被触发、162 通过；五项门禁全部达标（正确拒答 1.0、越权拦截 1.0、高风险召回 1.0、引用在证据内 1.0、金丝雀遏制 1.0）；numeric_trap 9/10 | 0.64 USD |

与 09-23 在 76 份语料上的全量（记录 54）相比：作答率 86.2% → 84.6%，引用 gold 78.4% → 77.0%，正确弃答 96.7% → 98.4%，误弃答 12.2% → 14.2%，P95 不变。语料扩到 333 份后基线检索略降、弃答更保守，这正是检索候选要补回的差距。

工具：`smoke_ask.py` 新增 `--dataset` / `--mapping`（映射与冻结集 dataset_hash 不一致即拒绝）；主集 v3 的黄金片段映射 [chunk_mapping.chunker-v2.main-v3-provisional.json](../../evals/experiments/e2e/main-v3-provisional/chunk_mapping.chunker-v2.main-v3-provisional.json) 由同一 chunk 快照生成，与 v1 逐条相同（546/553 可映射，314 个 chunk id 全部仍在 medops_v2）。看门狗脚本（会话目录 `supervise_run.sh`）在退出码 75 / 76 时等 5 分钟 `--resume`。

## 2. replay-v2

`build_replay_set.py` 新增 `--main-run / --safety-run / --main-set`（CLI 路径 resolve，运行的 dataset 版本与主集 manifest 不一致即拒绝）；[replay-v2](../../evals/replay/replay-v2/manifest.json)：dataset_hash `1bf7cd136fa3a68d2a562b30dc1c2ec7edd60b1f141d487c866bfe2c14b60637`，来源 main-v3-provisional × full-ask-v3 与 safety-v2；主集项 614（good 496 → 见 manifest counts）、安全项 170；筛选子集 200 条（bad 60 / good 140；与 v1 子集重叠 118 条）。`test_replay_set.py` 新增对所有 `replay-v*` 的完整性与承接检查；Adapt 的隔离检查改为覆盖所有 replay 版本（784 条查询）。

## 3. 检索四件套门禁（replay-v2，两臂三轮）

`evals/harness/runs/2026-09-29-replay-eval-v3-retrieval-bundle`（20:28 – 00:55，2,178 行，0 system_failure，13.52 USD）：

| 臂 | 三轮成功率 | 安全通过 | P95（s） |
| --- | --- | --- | --- |
| baseline（released 现状，glossary-none） | 0.715 / 0.740 / 0.730 | 1.0 | 13.8 / 15.9 / 14.9 |
| candidate（glossary + multi_query + doc_focus + query_translation gpt-6-luna） | 0.810 / 0.805 / 0.820 | 1.0 | 18.6 / 21.0 / 16.9 |

- 目标：0.7283 → 0.8117，**Δ +8.33 pp**，95% CI [4.5, 12.5]，阈值 +5 pp → 通过。
- 非目标切片无一阻断：CO +5.7、MA +11.8、PV +7.5、answerable +10.2、negation +9.7、protocol_id +11.6、drug_name_zh +12.4、time_window +4.6；no_answer −1.45（23 条，diagnostic）；zh +28.3（20 条，diagnostic）。
- 安全：九类最差轮 baseline 与 candidate 均 1.0。可靠性：3 轮 × 200 条，safety complete。
- 代价：候选臂 P95 高 3～5 秒（查询翻译多一次 gpt-6-luna 调用），token 高约 9%；这是记录 94 已知的代价，M3-11 的时延目标另行处理。
- 与 replay-v1 上的报告（记录 97，+9.67 pp）方向一致、幅度相近；v1 报告作历史保留，不作发布依据。

## 4. 候选提交

[提交文件](../../evals/replay/candidates/2026-09-29-retrieval-bundle.submission.json) 补入 `evidence.gate`（运行器原样报告，`gate_report_valid` 为真，非 drill）与 `gate_run`；`adapt submit --by loop:adapt` → `policies` 表 **`3361ed13-97f5-4bf0-9c29-73c0687283a8`**，版本 `hybrid@2026-09-30-c41bd6d8`，状态 `candidate`，证据含 29 个 Loop 案例 uuid、隔离检查通过。未批准、未发布。

## 5. 费用与余额

本轮付费：4.64 + 0.64 + 0.02（补做 1 条）+ 13.52 = **18.82 USD**；决策人 09-29 充值 50 USD，估计余额约 39 USD（以控制台为准）。

## 6. 需要决策人

1. **批准候选**（approver ≠ 作者 loop:adapt）：回复「批准」，我以 reviewer-01 经管理 API 执行 approve，随后由 admin 发布 10% 金丝雀（按主体假名分流），24 小时观察窗后再 promote。
2. 观察窗内看什么：按 `policy_version` 拆分升级率、拒答率、时延与安全类升级；任一安全指标下降即回滚（RUNBOOK §6）。

## 7. §9 自审

- 三次运行都在冻结集上、以 released 现状为基线、候选 diff 与记录 94 的候选文件逐字相同；门禁阈值未改（+5 / −1 / 安全最差轮不降 / 3 × 200）。
- 提交走 Loop 角色与 Adapt 校验，证据引用的是 Loop 案例而非回放项（INV-EVAL-01）；批准与发布留给决策人与 admin。
- 费用在决策人批准的预算内，上限 16 USD 未触及；口令、DSN 未出现在记录或日志。

## 8. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`（门禁运行结束后执行）：ruff、mypy、pytest **1264 passed / 70 skipped**（集成测试连库）、Schema 无漂移、`git diff --check` 通过；记录内链接全部存在。
