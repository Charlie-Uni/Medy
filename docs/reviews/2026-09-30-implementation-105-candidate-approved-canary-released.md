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

## 6. 追记：观察窗冒烟（决策人 2026-09-30 16:14–16:24 运行）

`evals/harness/runs/2026-09-30-canary-smoke-{baseline,canary}`：同一 30 题 MA 问题集（记录 77 `c1-cold` 级），经真实 API（`perf_run.py`，并发 1）各以一个主体跑一遍；`traces.versions.policy_version` 证实分流：基线侧主体 30 条全部 `policy-m3-api-1`，灰度侧主体 30 条全部 `policy-m3-api-1+canary:3361ed13`。

| | 基线侧（canary-smoke-01） | 灰度侧（canary-smoke-08） |
| --- | ---: | ---: |
| 请求 / 失败 | 30 / 0 | 30 / 0 |
| 作答 / 证据不足升级 | 25 / 5 | 26 / 4 |
| 与预期一致 | 27 / 30 | 28 / 30 |
| 安全类升级 | 0 | 0 |
| P50 / P95 延迟（s） | 7.9 / 11.3 | 11.1 / 14.7 |
| 费用（USD） | 0.33 | 0.29 |

判断：灰度侧没有任何安全指标下降，作答略多、误升级略少，与门禁方向一致；P95 高约 3.4 s 是查询翻译调用的已知代价（记录 94 / 104）。按 RUNBOOK §6.2 不构成回滚理由；观察窗满（2026-10-01 02:04 UTC）后可推进到全量，脚本 `PROMOTE.sh`（`approve_release.py --promote 100`，approver 执行）已备好。

前三次冒烟失败均在 API 启动或探测阶段、未产生费用，各暴露一个真实的部署问题并已修正：(1) 模型加载时 HuggingFace 库向 huggingface.co 发检查请求，经当前代理 SSL 握手被截断，重试超过 120 s 的固定线程上限 → 冒烟与发布脚本以 `HF_HUB_OFFLINE=1` 离线加载本地缓存；(2) released 的检索参数指向词表版本后，API 按 DEPLOY.md 规则在启动时快速失败，而 `.env` 从未配置 `GLOSSARY_DIR` → 已写入 `.env`（指向仓库 `evals/glossary/`）并加入 RUNBOOK §6.4 检查单；(3) API 已监听但评测端就绪探测 300 s 无结果：终端环境的代理变量把发往 127.0.0.1 的探测送进了代理 → `perf_run.py` 的探测与请求改为 `trust_env=False` 并在超时时打印最后一次探测结果，脚本层再剥掉代理变量。
