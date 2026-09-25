# 实现记录 79：M4-A——信号关联到 Trace（M4-01）与回放集 replay-v1 冻结（M4-06）

- 日期：2026-09-25
- 授权：记录 74 C（DEC-014，决策人 2026-09-25「同意」）：M3 收尾后从 M4-A 起
- 范围：迁移 0016（`trace_signals` 视图、`bad_cases`、`escalations.resolution`、Loop 角色读路径）、`medops.loop.observe`（Observe 步骤与 CLI）、Loop 登录用户与 `DATABASE_LOOP_URL`、`evals/replay/`（规范 spec-r1 v0.1、构建 / 校验工具、冻结的 `replay-v1`）、测试、文档
- 费用：0（没有模型调用）

## 1. 决定与依据

| 决定 | 依据 |
| --- | --- |
| 信号的统一来源是一个 `security_invoker` 视图 `trace_signals`，不是新表：每个 Trace 一行，把 `feedback`（点赞 / 点踩 / 纠错数）、`escalations`（状态、reason code、人工结论）、Verifier 失败（`unsupported_conclusion` 或 `verify_result.structural_ok=false`）、安全标记（被标记证据或 `prompt_injection` / `acl_denied`）、回放（次数、是否有差异）拼到 Trace 上 | 基线 5.8「Execute/Observe 有统一数据来源」；信号已经各自以 `trace_id` 落库（记录 60 / 65），缺的是一个不复制数据的联合读模型；`security_invoker` 让基表的 RLS 对查询者生效而不是对视图属主生效 |
| `escalations` 增加 `resolution`（`confirmed_issue` / `false_alarm` / `resolved_manually`），只有管理角色可写；0011 的守护触发器继续保护其余列 | 基线 5.8「Observe 接收…升级结果」——升级的人工结论此前没有落点；写入接口（管理路由）涉及契约，随 M4-09 的审批界面一起提，本记录只建列 |
| `bad_cases` 表：每个 Trace 至多一个案例，记录打开它的信号快照、标签与原因；归因列（类别 / 置信 / 归因者 / 备注）留给 M4-02，`human_override` 是人工修正入口；身份、快照、标签不可改；`human_override` 只有管理角色能写 | 基线 5.8 Reflect「允许人工修正」与 M4-02「带置信与人工修正入口」；把「谁能改什么」放进触发器与策略，而不是应用代码 |
| Loop 角色：可读 `traces` / `escalations` / `feedback` / `replays` 与视图，可读写 `bad_cases`（不能删、不能改标签与快照、不能写 `human_override`），对 `policies` 仍只能插入候选，对 `released_policies` 无写权限 | INV-AUTH-05；M4-04 的权限测试以此为基线，本记录的集成测试已经用真实 LOGIN 用户证明了这些边界 |
| Observe 的标签故意窄：任一负面信号 → `bad`；已回答且有明确点赞且无负面信号 → `good`；其余不建案例；`system_failure` / `budget_exceeded` 升级不是 Loop 材料；回放与 MCP 的 Trace 不建案例；每个 Trace 只建一次 | 没人反应的回答不是任何证据；基础设施故障归 M3-13 而不是策略；回放是诊断 |
| 回放集首版从两次已归档运行导出（主集 v2 全量 614 条 + 安全集 r2 170 条），manifest 标注 `origin=run_export_not_live_traffic`、`provisional=true` | DEC-014；两个来源的人工复核都未完成，如实标注而不是等 |
| 主集项标签由样本类型 × 观察结果决定（8 条规则，见工具文档表）：good 496 / bad 118；安全项 good 163 / `not_exercised` 7（注入 chunk 未被检索到，保留不计数） | 基线 M4-06「good / bad 历史 Trace」；标签规则写在代码里并被单元测试逐项核对 |
| 候选筛选子集 200 条：排除 `derived`（同义改写孪生），bad 占 30%（60 条），每个标签内部门按比例，种子 20260925 | DEC-014 的预算分级；独立性（M4-06「不以 3 次重复运行充当 600 条独立样本」）；bad 过采样让候选对失败的影响可测 |
| 隔离规则（INV-EVAL-01）写进 manifest 与规范：回放项 id、问题、gold 不进入 Adapt 上下文；执行点在 M4-03 | 现在没有候选生成代码，规则先于代码存在 |

## 2. 交付

- 迁移 0016（本地 medops_v2 / medops_v2_safety 已升级）：视图、表、列、四条 `*_loop_read` 策略、授权、`medops_bad_case_guard` 触发器；DOWN 全部回收（往返测试通过）。
- `medops.loop.observe`：`TraceSignals` / `Case` / `classify()` / `observe()`、`PgSignalSource` / `PgCaseStore`、内存实现、CLI `python -m medops.loop.observe --since … [--dept] [--dry-run]`（在 `DATABASE_LOOP_URL` 上，带 0016 之前引入的连接与语句超时）。
- 登录用户脚本新增可选 `loop` 用户（`DB_LOOP_PASSWORD`）；设置 `database_loop_url`；`.env.example`。
- `evals/replay/SPEC.md`（spec-r1 v0.1）、`tools/build_replay_set.py`（构建 + `--check`）、`replay-v1/`：`items.jsonl`（614）、`safety_items.jsonl`（170）、`subset.json`（200）、`manifest.json`、`SHA256SUMS`；`dataset_hash = 154f576a…`。
- 测试：单元 `tests/unit/loop/test_observe.py`（17 条标签表 + 幂等建案 + 报告 + 快照）、`tests/unit/evals/test_replay_set.py`（哈希与 manifest 一致、≥ 200 且无重复、标签与规则一致、安全项期望块齐全、子集规则）；集成 `tests/integration/test_loop_signals.py`（视图逐项信号、Loop 用户建案一次 / 可归因 / 不能覆盖 / 不能改标签、五类越权写全部被拒、管理用户修正与登记升级结论、应用用户看不到案例与视图）；迁移 / RLS 期望更新。

## 3. replay-v1 概况

| | 项数 | 说明 |
| --- | ---: | --- |
| 主集项 | 614 | MA 133 / PV 279 / CO 202；answerable 501、conflict 52、no_answer 61；good 496、bad 118（有答案误弃答 69、错引 39、冲突误弃答 6、冲突错版本 2、无答案误答 2）；`derived` 200、`imported` 107；问题文本无重复 |
| 安全项 | 170 | 九类；good 163、not_exercised 7 |
| 筛选子集 | 200 | good 140 / bad 60；MA / PV / CO 各 ≥ 30；不含 derived |

## 4. 未做 / 限制

- 「连续追问」信号没有来源：会话（M3 sessions）未实现；视图有位置，等会话落地后加列。
- `escalations.resolution` 只有列没有接口：管理路由随 M4-09 的审批契约一起提（M0-08 流程）。
- Observe 只建案例不归因（M4-02）；`bad_cases` 现在只有集成测试写入的行，真实流量到来前主要由回放结果驱动。
- 回放集是运行导出，且两个来源都是临时版；真实 Trace ≥ 200 条 good / bad 后换 `replay-v2`。
- 隔离规则的执行（拒绝引用回放项的候选）随 M4-03。

## 5. 自审（§9）

- 权限边界全部由真实 LOGIN 用户在 FORCE RLS 下证明（Loop 用户五类越权写被拒；应用用户读不到案例与视图）。
- 回放集可复现（同一命令、同一种子得到同一哈希）、可校验（`--check` 与单元测试），标签规则可读且被逐项测试；不含证据正文（只有 chunk id 与问题文本，问题文本本就在冻结主集里）。
- 没有模型费用；服务运行时代码未改（只有迁移与新包）。
- `make check` 通过。

## 6. 进度

- M4-01 → **已实现**；M4-06 → **已实现**（运行导出、临时来源，如实标注）。
- P0 加权进度 60.8% → **63.3%**（50/79）；按 99 项计 50.5%；M4 2/10。
