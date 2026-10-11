# 反馈来源、评分标识与恢复契约

ARCH-09；实现和核验见[记录183](reviews/2026-10-11-implementation-183-stable-feedback-identity.md)。PostgreSQL 是反馈事实库，SQLite 是目标项目绑定的本地发送队列，Langfuse 是观察视图。本文不改变正式评分器或把用户点赞计入正式质量门禁。

## 1. 两种数据库身份

| 身份 | 用途 | 生命周期 |
| --- | --- | --- |
| `retrieval.integrity.database_identity` | 就绪检查判断应用/管理连接是否到达同一运行实例 | 库名、OID、postmaster 启动时间的摘要；保留既有行为 |
| `infrastructure.db.fact_plane.fact_plane_identity` | 反馈来源与扫描游标 | 0025 的单行 `fact_plane_identity.fact_plane_id`；随机、非零 UUID，不含 DSN、地址或启动时间 |

采集要求只读事务和全局审计可见性。admin/loop 角色仅可读 UUID；应用和 MCP 只读角色无此表权限。缺迁移、缺身份、部署绑定不符都失败关闭，不降级回临时身份。新库独立生成 UUID；dump/restore 保存该行。

## 2. score ID、游标与发送保证

- 新反馈源的 namespace 为事实库 UUID。score ID 继续按既有 v1 格式，摘要输入为 `feedback:<namespace>:<feedback_id>`、Trace ID 和 `user_feedback` 名称；不修改历史评分格式。
- 元数据的 `fact_plane` 是稳定评分 namespace。新源为 UUID；已明确迁入的旧源保留旧 hash，不能把历史 payload 的此字段改成 UUID。真实 UUID 与旧 namespace 的对应存在本地 `feedback_sources` 表。
- `scans.source` 使用真实 UUID。按反馈 UUID 排序扫描；一轮到末尾后回到零游标，下一轮发现迟到提交的低 UUID。所有该批事件持久入队后才推进游标。
- 入队后、推进游标前崩溃会重扫；相同 score ID 和 payload 去重。网络丢失确认会重发原 ID、原 timestamp、原 metadata。传输为 **at least once**；远端可按固定 ID/原日期去重，不能承诺跨系统恰好一次。
- 删除已送达的本地 receipts 不删除来源绑定；旧反馈重建仍生成原 ID。队列上限、退避、死信、目标项目绑定保持。没有导出 query、correction_text、principal 或正文。

## 3. 旧队列切换

旧运行身份为 64 位十六进制 hash，不能仅凭地址或库名推断它属于哪份库。出现未绑定旧 cursor 或已入队的旧反馈时，新采集默认拒绝；即便崩溃前尚未写 cursor，已有 payload 也触发此检查。

操作人先核对库、队列、Langfuse 项目和旧 hash 的来源。使用现存队列做绑定，**保留旧 payload，不重算已导出 ID**：

```bash
# 只读查看持久 UUID；不导出正文。
env -u DEBUG venv/bin/python -m medops.infrastructure.db.fact_plane --database medops_v2

# 下列占位符替换为核验过的真实值。首次仅入队，不发 HTTP、不调模型。
env -u DEBUG venv/bin/python -m medops.worker.observability \
  --database medops_v2 --fact-plane-id <UUID> \
  --queue <existing-private-queue.db> --legacy-feedback-source <old-64-hex-hash> \
  --enqueue-only
```

绑定在 SQLite `BEGIN IMMEDIATE` 下原子建立；同一旧 namespace 不能分配给两个 UUID，已绑定 source 不能改绑。明确绑定后无需每轮重传旧 hash。首次从零游标重扫，以原 ID 去重，不相信旧游标的生命周期。

一个库如果曾跨多个重启 namespace 导出过相同反馈，远端历史重复已存在，本轮不会删除或合并。分别核对受影响的队列/namespace，选择后续的稳定延续 namespace；另列历史清理计划。无法确定来源时不填猜测值、不删除队列来绕过检查。新空队列无法判断远端是否存在旧 ID，部署人员须从历史清单恢复已知 namespace 绑定。

## 4. 灾难恢复与独立克隆

**恢复同一事实库**：保留数据库 UUID，连同 SQLite queue（包括 `settings`、`scores`、`scans`、`feedback_sources`）恢复，使用同一目标 Langfuse 项目及 `--fact-plane-id`。旧队列丢失但旧 hash 已知时，可显式重建同一绑定；hash、项目、原 timestamp 不可猜。恢复演练脚本的 inventory/report 另比较 UUID，行数相同不再足以证明身份保留。

**独立测试/实验克隆**：备份复制会携带源 UUID，不能把它直接视作新源。首次采集前，在明确选中的克隆上由迁移 owner 执行：

```bash
env -u DEBUG venv/bin/python -m medops.infrastructure.db.fact_plane \
  --database <clone_database> --rotate-clone --expected-id <copied_UUID>
```

操作要求迁移 owner 具有 RLS bypass，在行锁后比较期望 UUID 再更新，只改变身份元数据，输出前后 UUID 供部署清单留证。应用、admin、loop 角色不能执行这个写操作。采用独立队列与独立 Langfuse 项目，或者关闭克隆采集；不要把复制的历史反馈当新业务量。部署清单保存新 UUID，并通过 `--fact-plane-id` 绑定。

应用无法凭连接信息自动区分“合法恢复”和“忘记改身份的克隆”；部署流程必须作这一区分。同一个被复制的 UUID/清单/队列不会被本实现神奇识别为两个库。这个限制是明确的操作契约，不属于自动克隆发现能力。

## 5. 回滚和上线条件

先将所有采集目标升到 0025，核对唯一 UUID、队列来源和项目，再更新 worker。尚未部署的代码不等于驻留消费者已使用新身份。本轮不自动绑定历史队列、不发送真实评分、不重启服务。

代码回滚可保留新增表。**不要把 downgrade→upgrade 当普通回滚**：0025 downgrade 删除身份，重新升级会生成新 UUID；本地游标和 score ID 会失去延续关系。需要降级时先停止采集、备份 UUID/队列/绑定及项目，恢复时原值必须保留并校验；不能让随机新 UUID冒充原事实库。
