# 实现记录 85：M4-E——按请求重读 released、灰度分流、promote 与观察窗、回滚演练（M4-09 / M4-10）

- 日期：2026-09-25
- 授权：决策请求记录 83（决策人 2026-09-25「按照你的建议来」：批准 promote 路由与 24 小时观察窗、允许记录在案的 override、演练用 dev 环境 `drill` 标记）
- 范围：迁移 0018、`policy_loader` 的发布状态与分流、运行时 / worker / MCP 的按请求重读、`POST /admin/policies/{id}/promote` 与错误码 `observation_window_open`、门禁的 dev 演练模式、真实 API 上的发布 → 灰度 → 全量 → 回滚演练、测试、文档
- 费用：演练约 0.07 美元

## 1. 决定与依据

| 决定 | 依据 |
| --- | --- |
| 运行时不再只在启动时读一次 released：每个请求经 `route_policies()` 取 `ReleaseState`（`released_policies ⋈ policies ⋈ 最近一次 release / promote 行`），5 秒 TTL 缓存（`POLICY_RELOAD_TTL_S`）；worker 的 Skill 上下文与 MCP 的检索同样按请求重读 | 记录 83 A；回滚 / 发布在 TTL 内生效，无需重启；M4-10「运行请求的版本一致性」由 Trace 逐条记录实际使用的策略集来证明 |
| 分流规则：目标 (kind, name) 的最近一次发布 / 推进给出 `canary_percent = p`；`sha256(主体假名 + kind/name) mod 100 < p` → 新策略，否则前一策略（首次发布无前策略时 = 仓库常量）；每个目标独立分流，同一主体永远落同一侧 | 记录 83 A；可复现、可审计；`policy_version` 用 `+rel:<id>` 表示全量、`+canary:<id>` 表示灰度侧，不改 `VersionSet` 契约 |
| 重排输出大小随策略变化时按需构造第二个重排器实例（同一钉住线程） | 一个进程里两个策略集可能要求不同的 `rerank_output` |
| `promote`：只有 `approver` 且不是候选作者；只对当前 released 且灰度 < 100% 的策略；只能放大；距上一次发布 / 推进不足观察窗（`OBSERVATION_WINDOW_HOURS`，默认 24）时 `409 observation_window_open`，带 `override_reason`（≥ 20 字）可推进并写进 `policy_releases.reason`；指针不动，只追加一条 `promote` 行（迁移 0018 放开 action 枚举） | 记录 83 B、D 表第 1、2 项；不复用 release 路由放宽上限，保住「初始灰度 ≤ 10%」 |
| 门禁演练模式：`gate_report_valid(..., allow_drill)` 只在 `APP_ENV=dev`（运行时属性 `allow_drill`）接受标了 `drill: true` 的报告（仍需 `passed`、冻结回放集哈希与 arms 字段）；`drill` 标记留在 evidence 里 | 记录 83 C、D 表第 3 项；不为演练在发布路由开后门 |
| 观察窗内的安全指标回归检查（信号视图按 `policy_version` 统计）本记录未做，只做了时间规则 + 人工 override | 记录 83 B 里写的是建议；先落时间规则，指标规则随真实流量 |

## 2. 演练（真实 API，CPU 设备，dev 环境，`POLICY_RELOAD_TTL_S=2`）

报告 `evals/harness/runs/2026-09-25-release-drill-v1/report.{json,md}`（脚本在会话草稿目录）。6 个演练主体（`created_by=record-85-drill`）事先按分流哈希挑选：桶值 5、6 的两名落在 10% 灰度侧，桶值 16、66、70、88 的四名在另一侧；批准人 `drill-approver-1`（approver 角色），发布 / 回滚人是记录 67 的 admin 身份；候选 = rrf_k 60 → 40，`evidence.gate` 带 `drill: true` 与 replay-v1 哈希。11 项检查全部通过：

| 步骤 | 结果 |
| --- | --- |
| 阶段 0（发布前）6 次问答 | 全部 `policy-m3-api-1`，响应版本 = Trace 版本 |
| approver 批准；admin 发布 10% | 200 / 200 |
| 阶段 1（灰度 10%） | 两名预选主体 `policy-m3-api-1+canary:e72a6a08`，其余四名基线；逐主体与预先算出的期望一致，0 不符 |
| 观察窗内 promote 100% | `409 observation_window_open` |
| 带 override_reason 的 promote 100% | 200；`policy_releases` 记 `promote, 100, "… [override: …]"` |
| 阶段 2（全量） | 六名全部 `policy-m3-api-1+rel:e72a6a08`，切换后第一条请求即是新版本（TTL 2 秒） |
| admin 回滚 | 200，状态 `rolled_back`，指针清空 |
| 阶段 3（回滚后） | 六名全部回到 `policy-m3-api-1`，第一条请求即生效 |
| 发布日志 | `release(10) → promote(100) → rollback`，追加写 |

费用 0.07 美元。一处如实说明：阶段 0、1 各耗时 1.7 小时与 59 分钟，不是切换慢——API 跑在 CPU 上，同时机器在跑候选评测（MPS + CPU）与两轮 `make check`，单次问答被拖到十几分钟；阶段 2、3 无争用时 6 次问答共 62–79 秒，与记录 77 的时延一致。「切换生效时间」的证据是每个阶段切换后的**第一条**请求就带新版本，而不是阶段总时长。

## 3. 交付

- 迁移 0018（本地两库已升级）：`policy_releases.action` 允许 `promote`。
- `policy_loader`：`ReleaseTarget` / `ReleaseState.for_principal()` / `RoutedPolicies.policy_version()` / `RequestPolicies` / `load_release_state()`；`ProductionRuntime.release_state()`（TTL）、`route_policies()`、`request_policies()`、`reranker_for()`、`build_deps(..., routed)`；`skill_context` 与 `ReplayService.versions_for` 用路由后的版本；MCP `_searcher_factory` 每次调用按主体分流。
- `PgPolicyStore.last_release()` / `promote()`；`PolicyService.promote()`（四眼、单调、观察窗、override 记录）；`PolicyPromoteRequest`、错误码 `observation_window_open`、OpenAPI `promotePolicy`、schemas 重生成、`CONTRACTS.md`、`DEPLOY.md`、`.env.example`。
- 测试：单元 `tests/unit/application/test_policy_router.py`（全量 / 灰度分流稳定且接近比例 / 无前策略回落常量 / 多目标独立分流 / drill 模式）、路由测试「promote 只对 released、非作者 approver、观察窗 409、override 200、不能缩小、100% 后拒绝」；集成 `tests/integration/test_policy_router.py`（发布 10% → 应用角色看到的状态与分流 → promote 100 → 继任者带前策略 → 回滚 → 日志顺序）；迁移期望 0018。

## 4. 未做 / 限制

- 观察窗内的自动安全回归检查（按 `policy_version` 聚合信号）未做；现在靠人工 + override 记录。
- MCP 的审计 Trace 版本仍写常量 `retrieval_version`（分流已生效，记录待补字段）。
- 灰度按主体假名分流，匿名 / 无主体的请求（不存在于本系统）无定义。
- 首个正式候选评测（记录 82 §5）正在运行，结果另记。

## 5. 自审（§9）

- 每次切换后的「版本一致性」用三处对照：响应体 `versions.policy_version`、Trace 账本、按分流规则预先算出的期望——逐主体相等。
- 权限：approve / promote 由 approver 完成，作者被拒；release / rollback 由 admin 完成；Loop 角色的写边界未变（记录 81 测试仍过）。
- 费用见 §2；`make check` 通过。

## 6. 进度

- M4-09、M4-10 → **已实现**（观察窗指标回归检查登记为后续）。
- P0 加权进度 70.9% → **73.4%**（58/79）；按 99 项计 58.6%；**M4 10/10**。
