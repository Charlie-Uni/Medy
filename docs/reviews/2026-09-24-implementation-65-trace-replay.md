# 实现记录 65：单条 Trace 回放接口（M3-08 首切片、M3-03 部分）

- 日期：2026-09-24
- 范围：`POST /admin/traces/{trace_id}/replay`：管理角色对一条历史 Trace 重跑，用原问题、原 principal 的**当前**身份、本部署钉定的版本集与独立的 `replay_run_id`，把回放记为独立 Trace（kind = replay，不产生人工升级），返回两侧 outcome / reason codes / 引用 / 证据与差异字段、版本是否一致，并落库 `replays`。
- 依据：基线 3.2（回放独立 `replay_run_id`，不得复用生产 operation key）、5.7（replay 接口）、§8 M3-08「Trace replay 固定实际策略/检索/Skill/模型版本，用独立 run id 生成差异报告；禁止被原执行缓存短路」；`docs/api/CONTRACTS.md` 该行由「M3-08 定义」改为具体契约。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 回放在**原 principal** 的身份下执行（重新从目录解析；已停用或换部门即 `400 invalid_request`），不是管理员身份 | 可见性不同会让差异失真；INV-AUTH-03 默认拒绝 |
| `replay_run_id` 为新 UUID，`trace_id` 也新建；账本按 run id 生成 key，因此原运行的任何节点结果都不可复用（测试：账本行数 +5） | 3.2、M3-08「禁止被原执行缓存短路」 |
| 版本：只能用本部署钉定的版本集重跑；报告 `versions_match` 指出原 Trace 是否在同一版本集下产生。指定其他策略/检索版本的回放需要多版本并存的运行时，随 M4 策略发布机制 | 当前运行时单一钉值；如实标注 |
| 回放 Trace 不写升级记录（诊断用途），但完整记录 span 与费用 | 5.5 升级是给人接手的；回放不该制造工单 |
| 契约 `ReplayRequest{reason}` / `ReplayReport{source, replay, versions_match, changed}`，201；`schemas/` 与 `openapi.json` 重导出，新增 `admin` 标签与 `TraceIdPath` 参数 | M0-08 契约流程 |
| 回放的回放返回 404（kind = replay 的 Trace 不可再回放） | 避免无界链条 |

## 2. 交付

- 迁移 `0012_replays.py`（`traces.kind` 增 `replay`；`replays` 追加写表，应用写 / 管理读）。
- `src/medops/application/replay.py`（`ReplayService`）；`TraceStore` 增 `read_trace` / `record_replay`（内存与 PostgreSQL 实现）；`medops.api.app` 新路由；`ApiRuntime.resolve_user`。
- 测试：单元 2 项（管理员回放：原 principal、新 run id、账本无复用、kind = replay、无升级、`changed=[]`；有变化时报告差异字段；非管理员 403、未知 404、回放不可回放、Schema 422）；迁移清单 / 往返 / RLS 集合更新到 0012。

## 3. 未做 / 限制

- 数据集级回放与差异报告（目标 / 非目标 / 安全 / 延迟 / 成本变化）属 M4 Loop；本切片只做单条。
- 未在真实库上跑回放（与端到端一起）；`replays` 表的 PostgreSQL 读写路径由集成测试的存储测试间接覆盖（迁移与 RLS），`read_trace` / `record_replay` 的 Pg 实现待端到端验证。
- 回放使用模型，有费用；未做速率限制。

## 4. 进度

- M3-08 部分、M3-03 部分（管理接口第二个）。P0 加权进度 54.4%（43.0/79）；按 99 项计 43.4%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 6.5/13、M4 0/10、M5 0/8。
