# 实现记录 61：主链路故障测试（M3-13 首切片）

- 日期：2026-09-24
- 范围：用假部件把三类故障串到 API 与 worker 层面：模型超时 / 供应商中断、worker 执行中死亡、重复消费；另加审计存储中断。每个用例证明三件事——失败可定位（Trace span 或 attempt 记录指出节点、第几次尝试、错误码）、可恢复（故障消失后同一请求成功，且不多做猜测性调用）、安全链不被绕过（没有未核验答案、没有无审计答案、拒答仍先于任何模型调用）。
- 依据：基线 5.10（Trace 写失败不得产出无审计答案）、5.3（失败即升级）、3.2（重试不重复副作用）、§8 M3-13；记录 52（节点策略）、56（账本）、59（任务租约）、60（审计）。

## 1. 用例与证明

| 故障 | 注入方式 | 可定位 | 可恢复 | 安全链 |
| --- | --- | --- | --- | --- |
| 模型超时（3 次） | 假网关前三次 `ModelTimeout` | Trace 的 answer span 为 retry / retry / failed，`error_code=dependency_timeout`；升级记录存在 | 供应商恢复后同一问题回答；总调用 4 次（3 败 1 成），无额外猜测 | 响应为 `escalated system_failure`，`answer` 为空 |
| 供应商中断 | 假网关 `ModelUnavailable(retryable)` | answer span `dependency_unavailable` | — | 高风险问题在中断期间仍被拒答且零模型调用；普通问题升级而不是给出部分答案 |
| worker 执行中死亡 | worker-1 占用后不再汇报 | attempt 记录 `(1, worker-1, lost)`、`(2, worker-2, completed)` | 租约到期后 worker-2 接管并完成；租约内其他 worker 不得触碰 | worker-1 的迟到汇报被忽略，结果不可被覆盖；任务 Trace 写入 |
| 重复消费 | 两个 worker 同时 `run_once`；同 key 重复提交 | — | 恰好一个 worker 拿到任务，Skill 只执行一次；同 key 提交不入队第二份 | — |
| 审计存储中断 | 假 Trace 存储抛异常 | `503 audit_unavailable`，可重试 | 存储恢复后同一问题回答并留下 Trace | 中断期间响应里没有任何 claim |

`tests/unit/faults/test_main_chain_faults.py`，5 项；`make check` 全部通过。

## 2. 未做 / 限制

- 都是进程内假部件；真实进程级混沌（kill worker 进程、断数据库连接、模型端真实超时）与故障演练随部署（M3-12）后做，M3-13 记为部分。
- 队列层面的「重复消费」目前由数据库租约与 operation key 账本共同界定，Redis 唤醒未引入，因此没有 Redis 重复投递的用例。
- 模型超时后的恢复是新请求重跑全部节点：同 trace 的续跑（复用账本里已成功的节点）需要任务接口层的 retry 语义把 `run_id` 固定为原 trace，随 M3-08 回放一起做。

## 3. 进度

- M3-13 部分。P0 加权进度 51.9%（41.0/79）；按 99 项计 41.4%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 4.5/13、M4 0/10、M5 0/8。
