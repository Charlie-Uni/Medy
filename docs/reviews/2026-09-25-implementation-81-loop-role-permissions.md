# 实现记录 81：M4-C——Loop 数据库角色的权限证明（M4-04）

- 日期：2026-09-25
- 授权：记录 74 C（DEC-014）：M4-B 之后是 M4-C
- 范围：`tests/integration/test_loop_role_permissions.py`（新）；无代码改动
- 费用：0

## 1. 内容

M4-04 要求「Loop 数据库角色只能写候选，无 released 写权限；用直接数据库操作的权限测试证明」。记录 79 / 80 的集成测试里已经散落着这些断言，本记录把证明收成一个独立文件，并把授权矩阵钉死：

| 表 / 视图 | Loop 角色权限 | 行级策略 |
| --- | --- | --- |
| `traces` `escalations` `feedback` `replays` `trace_signals` | SELECT | `*_loop_read using (true)` |
| `policies` | SELECT, INSERT | 插入 `with check (status = 'candidate')` |
| `policy_releases` `released_policies` | SELECT | 只读 |
| `bad_cases` | SELECT, INSERT, UPDATE | 触发器：身份 / 快照 / 标签不可改，`human_override` 只有管理角色 |
| `document_requests` | SELECT, INSERT | 触发器：处理只有管理角色 |
| 其余 24 张表（文档、chunk、嵌入、主体、任务、载荷、幂等键…） | 无 | — |

测试用真实 LOGIN 用户直接执行 SQL：候选可插入；插入 `status='approved'` 被行级策略拒绝；改 / 删 `policies`、写 `released_policies`、写 `policy_releases`、写审计四表、处理工单、删案例、读任何语料表、任何 DDL——全部 `insufficient_privilege`。授权矩阵与 `information_schema.role_table_grants` 逐项相等，新增任何权限都必须改这里。

## 2. 未做

- 权限测试证明的是数据库边界；Loop 进程的操作系统 / 网络边界随部署对象。
- `medops_loop_user` 的口令轮换与审计随 M5。

## 3. 进度

- M4-04 → **已实现**。P0 加权进度 67.1% → **68.4%**（54/79）；按 99 项计 54.5%；M4 6/10。
