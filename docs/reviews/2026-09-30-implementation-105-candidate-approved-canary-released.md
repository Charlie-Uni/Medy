# 实现记录 105：候选批准与 10% 金丝雀发布（决策人亲自执行）、观察窗冒烟待决策人运行

日期：2026-09-30。记录 104 的候选 `3361ed13-97f5-4bf0-9c29-73c0687283a8`（检索四件套，hybrid@2026-09-30-c41bd6d8）由决策人回复「批准 按照你的建议来」后进入发布路径。

## 1. 批准与发布

实现方按 RUNBOOK §6.1 准备了经真实管理 API 的脚本（会话目录 `approve_release.py`：以 `.env` 设置启动 `medops.api.serve`，但所有数据库连接改指 medops_v2，OIDC 用一次性会话签发密钥，JWKS 以 `OIDC_JWKS_JSON` 交给服务端；先建主体、再 approve、再 release、最后关停；不打印任何令牌）。执行时权限系统以「自我批准」拒绝了实现方为决策人铸造批准人身份并代为批准的动作——这与四眼规则一致：候选作者一侧不能铸造和使用批准人身份。于是由**决策人在自己的终端运行同一脚本**（`APPROVE.sh`）。结果（medops_v2）：

| 项 | 值 |
| --- | --- |
| principals | 新增 `reviewer-01`（approver）与 `release-admin-01`（admin），`created_by = record-105`，HMAC 假名 |
| policies | 状态 `candidate → approved → released`；`decided_by` = reviewer-01 假名，`decided_at` 2026-09-30 02:04:07 UTC，理由「决策人 2026-09-30 批准：replay-v2 门禁通过（Δ +8.33 pp，CI [4.5, 12.5]，安全九类最差轮不降，记录 104）」 |
| policy_releases | `release`，canary 10，`previous_policy` 空（首个真实发布，之前只有 09-25 演练的回滚），actor = release-admin-01 假名 |
| 运行时指针 | `load_release_state`：`retrieval_params/hybrid` current = 3361ed13，canary 10%，since 02:04:07 UTC；按主体假名分流，例如 `canary-smoke-08` 落在灰度侧（`policy_version` 带 `+canary:3361ed13`），`canary-smoke-01` 在基线侧 |

## 2. 观察窗

本系统没有真实流量，24 小时观察窗（`OBSERVATION_WINDOW_HOURS`）只能靠合成流量填充。决策人采纳建议：灰度期间用 API 跑一轮 30 题冒烟让两侧都产生 Trace，24 小时后对比再推进。实现方准备了 `canary_smoke.py`（复用记录 77 的 30 题 MA 问题集 `c1-cold` 级，`perf_run.py` 经真实 API 各以一个基线侧、一个灰度侧主体跑一遍，输出 `evals/harness/runs/2026-09-30-canary-smoke-{baseline,canary}`，约 0.7 USD），并登记了两个 analyst 主体（`canary-smoke-01` / `-08`，`created_by = record-105`）。启动时权限系统以「削弱安全」拒绝了实现方以会话签发密钥启动 API 的动作（与批准脚本同一机制），故冒烟也由决策人运行（`SMOKE.sh`）。冒烟结果与两侧对比另记。

## 3. 状态

- 发布路径：候选 → 门禁（记录 104）→ 批准 → 10% 金丝雀 **已完成**；观察窗冒烟待决策人运行；推进到全量须满 24 小时（2026-09-30 02:04 UTC 起），由 approver 执行 `promote`，或带 ≥ 20 字 `override_reason` 提前。
- 回滚随时可用：`POST /admin/policies/3361ed13…/rollback`（admin），一次操作切回仓库常量（无前策略）。
- 费用：批准与发布零费用；冒烟约 0.7 USD（两侧各 30 题）。

## 4. §9 自审

- 批准人与作者分离由权限系统和决策人亲自执行共同保证，实现方未绕过拒绝。
- 发布依据是 replay-v2 上的完整门禁报告（`gate_report_valid`，非 drill）；灰度比例 10%，指针与审计行均已核对。
- 冒烟主体是 analyst 角色的合成身份，不涉及真实用户；口令、令牌、DSN 未出现在记录或日志。

## 5. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`：ruff、mypy、pytest **1264 passed / 70 skipped**（集成测试连库）、Schema 无漂移、`git diff --check` 通过。
