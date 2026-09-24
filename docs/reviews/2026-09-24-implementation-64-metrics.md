# 实现记录 64：运行指标端点（M3-10 首切片）

- 日期：2026-09-24
- 范围：基线 5.10 核心指标中能从已有审计表直接得到的部分：请求量与结果分布、拒答 / 升级 reason code、待处理升级数、请求时延分位、模型调用 / token / 费用（窗口与本月）、任务队列深度与最老排队时长，以 Prometheus 文本格式经 `GET /metrics` 暴露；标签只用低基数字段。
- 依据：基线 5.10（核心指标；「不把高基数字段作为 metrics label」）、INV-OBS-03（脱敏）、§8 M3-10；记录 60（traces / escalations 表）、59（tasks 表）。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 指标从 PostgreSQL 聚合（`traces`、`escalations`、`tasks`）而不是进程内计数器：多副本读数一致、重启不丢，代价是每次抓取一组聚合查询 | 5.10；审计表已是事实来源；M3 无共享指标后端 |
| 暴露为窗口 gauge（默认 60 分钟）+ 月累计费用 + 配置的月度预算，而不是 counter | 聚合来自数据库快照，不能保证单调；预算与实际花费同屏（ADR-0010） |
| `GET /metrics` 需要 bearer 且 principal 具 `ops` 或 `admin` 角色；无身份 401、无角色 403 | INV-AUTH-01 所有请求可验证身份；指标虽为聚合仍属内部信息 |
| 标签集合固定：kind、outcome、reason_code、quantile、status；trace_id / principal / 部门不作标签 | 5.10 明文 |

## 2. 交付

- `src/medops/application/metrics.py`：`MetricsSnapshot`、`PgMetricsSource`（窗口计数、`percentile_cont` 时延分位、用量、月费用、任务状态与最老排队时长）、`render_prometheus`、`has_role`。
- `medops.api.app` 新增 `GET /metrics`；`ApiRuntime` 增 `metrics_source` 与 `monthly_cap_usd`；`ProductionRuntime` 接 `PgMetricsSource` 与 `Settings.llm_monthly_budget_usd`。
- 测试：单元 2 项（文本格式与标签、角色门禁 200 / 403 / 401）、集成 1 项（真实表上的窗口 / 月 / 升级 / 任务聚合）。

## 3. 未做 / 限制

- 告警规则（P95、错误率、队列积压、ACL 拒绝异常、失效版本候选、完整性失败、预算）尚未落成 Prometheus rules 文件；候选过滤原因、缓存命中、各节点错误率需要 Trace 记录扩展（span 已有 outcome / error_code，但未按节点聚合暴露）。
- 无进程级指标（内存、事件循环延迟）与 OTel（M3-09）。
- HTTP 层 401 / 403 未进 traces（身份解析失败在写 Trace 之前），因此 ACL 拒绝异常暂无数据源。

## 4. 进度

- M3-10 部分。P0 加权进度 53.8%（42.5/79）；按 99 项计 42.9%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 6/13、M4 0/10、M5 0/8。
