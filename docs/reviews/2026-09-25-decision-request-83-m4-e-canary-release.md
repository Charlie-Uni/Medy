# 决策请求记录 83：M4-E——签字发布、灰度 ≤ 10%、观察窗与原子回滚演练（M4-09 / M4-10）

- 日期：2026-09-25
- 状态：**已决**（2026-09-25，见文末答复）
- 背景：记录 75 落了策略状态机（候选 → 四眼批准 → 发布 ≤ 10% 灰度 → 回滚），记录 80 让生产按 released 指针加载策略，记录 82 让发布只接受完整门禁报告。M4-09 / M4-10 还差三件事，其中两件涉及契约（M0-08 要求先批准）。

## A. 灰度真正生效：运行时按比例分流（无契约变化）

现状：`policy_releases.canary_percent` 只是记录；`released_policies` 指针一切就是 100%，而且 API / MCP 只在进程启动时读一次。

建议：

1. 运行时**每次请求**读一次 released 指针与最近一次发布记录（两张小表，一次查询，5 秒 TTL 缓存），不再只在启动时读。回滚 / 发布在 5 秒内生效，不用重启；每条 Trace 的 `policy_version` 精确等于该请求实际用的策略集——这就是 M4-10 要的「运行请求的版本一致性」。
2. 分流规则：最近一次发布的 `canary_percent = p < 100` 且有 `previous_policy` 时，按 `sha256(principal 假名 + kind/name) mod 100 < p` 把请求分到新策略，否则用前一策略；同一用户始终落在同一侧（可复现、可审计），Trace 记 `canary=true/false`。
3. MCP 走同一套（只读角色能读两张表）。

## B. 观察窗与全量发布（需要契约变化）

现状：`PolicyReleaseRequest.canary_percent` 限定 0–10，只表达「初始灰度」，没有从灰度推进到全量的动作。

建议新增 `POST /admin/policies/{policy_id}/promote`，body `{canary_percent: 11–100, reason}`：

- 只对当前 released 且 `canary_percent < 100` 的策略有效；只能**单调放大**（10 → 50 → 100），每一步记 `policy_releases(action='promote')`。
- **观察窗**：距上一次发布 / 推进不足 `observation_window_hours`（建议 24 小时，设置项）时拒绝（409 `observation_window_open`），除非 body 带 `override_reason`（记入日志）。观察窗内出现任一安全指标下降（由 M4-01 的信号视图按 `policy_version` 统计）时同样拒绝。
- 执行者：`approver` 角色（与批准同一角色，但推进者不得是该候选作者——四眼延续）。

不建议复用 `release` 路由放宽上限：会让「初始灰度 ≤ 10%」这条硬规则失去表达。

## C. 回滚演练（无契约变化，需要一次真实运行）

建议：在本机真实 API 上做一次端到端演练并入库报告（记录 67 的方式）：

1. 用记录 82 的示例候选（rrf_k 60 → 40）走完 候选 → 批准 → 门禁报告 → 发布 10%，确认 10% 用户的 Trace `policy_version` 带 `+rel:`、其余不带；
2. `rollback` 一次操作切回，5 秒内新请求全部回到前一策略，Trace 版本随之变化；
3. 回滚期间发出的请求没有一条出现混合版本。

这一步需要门禁报告真正通过（或演练时以 `approver` 显式批注「演练，门禁豁免」并记入 decision_reason）。建议演练用后者，避免为演练花一次正式评测的费用；但**发布路由不为演练开后门**：演练候选的 `evidence.gate` 用记录 82 的冒烟报告结构 + 一条明确的 `drill=true` 标记，发布路由只在 `APP_ENV=dev` 接受 `drill=true`。

## D. 需要您决定

| # | 事项 | 建议 |
| --- | --- | --- |
| 1 | 是否批准新增 `promote` 路由与观察窗规则（B） | 批准 |
| 2 | 观察窗时长与是否允许 `override_reason` | 24 小时；允许但记录 |
| 3 | 演练用「dev 环境 drill 标记」而不是正式评测（C） | 同意 |
| 4 | 首个正式候选评测（记录 82 §5）：两臂各三次 ≈ 13 美元，或 baseline 冻结复用后 ≈ 7 美元 | 先 baseline 三次 + 候选三次一次性跑完（≈ 13 美元），之后复用 baseline |

## 决策人答复

2026-09-25：「83 按照你的建议来」——D 表四项全部按建议：批准 `promote` 路由与观察窗；24 小时、允许 `override_reason` 但记录；演练用 dev 环境 `drill=true`；首个正式评测两臂各三次（约 13 美元，余额 29 美元），之后冻结复用 baseline 臂。落实顺序 A → B → C → 首个评测（记录 84 起）。
