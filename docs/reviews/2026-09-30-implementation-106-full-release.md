# 实现记录 106：全量发布（override 提前推进）与发布后验收补测

日期：2026-09-30。记录 105 的 10% 灰度在观察窗未满时由决策人决定提前推进（「那就直接推进下一步」），理由：本环境无真实用户流量，观察窗内无可观察对象。

## 1. 推进

决策人运行 `PROMOTE_NOW.sh`（`approve_release.py --promote 100 --override-reason …`，approver 身份 reviewer-01，经真实管理 API）。核对（medops_v2）：

| 项 | 值 |
| --- | --- |
| policy_releases | 追加 `promote`，canary 100，actor = reviewer-01 假名，2026-09-30 13:56:54 UTC；`reason` 含推进依据与 override 理由（无真实流量、冒烟两侧各 30 题安全不降、验收报告 §5 已记录限制） |
| 运行时指针 | `retrieval_params/hybrid` current = 3361ed13，canary 100%，since 13:56:54 UTC；原基线侧主体的 `policy_version` 变为 `policy-m3-api-1+rel:3361ed13` |
| policies | 状态仍为 `released`（全量后 `+rel:` 标记），可随时 `rollback` 回仓库常量 |

观察窗提前结束的性质：M4-09 预设的例外路径（`override_reason` ≥ 20 字写入发布日志），不是绕过；观察窗的意义与本环境的局限见验收报告 §5 第 4 条。

## 2. 发布后补测

- 性能复测（验收报告 P2 / §2 5a）：待决策人运行 `PERF.sh`（记录 77 问题集四级 + 8 任务，经真实 API，released 策略，约 1.5 USD）。结果另记于本记录 §3。

## 3. §9 自审

- 推进由决策人亲自执行，作者一侧未铸造或使用批准人身份；override 理由如实写入发布日志与本记录。
- 发布后的第一个真实策略即刻可回滚（一次 admin 调用），回滚路径在记录 85 演练过。
- 未启动付费运行；口令、令牌、DSN 未出现在记录或日志。
