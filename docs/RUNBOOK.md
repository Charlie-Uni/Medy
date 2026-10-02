# 运维 Runbook：服务、告警、事故响应、人工升级、发布与回滚（M5-07，记录 87）

配套：`docs/DEPLOY.md`（进程、环境变量、compose）、`docs/OPERATIONS.md`（保留 / 轮换 / 备份 / 升级）、`docs/api/CONTRACTS.md`（管理接口契约）。每一步都写明命令与「怎么确认做对了」。

## 1. 服务与健康

| 进程 | 就绪 | 说明 |
| --- | --- | --- |
| API | `GET /healthz`（进程活着）、`GET /readyz`（能连数据库，2 秒超时；不通 → 503） | `/metrics`（ops 角色）给出 60 分钟窗口的请求 / 升级 / 时延分位 / 费用 / 队列 |
| worker | 日志 `worker starting` / `task finished`；`select status, count(*) from tasks group by 1` | 无 HTTP；数据库不可达时记录警告并继续轮询（记录 78） |
| MCP | Streamable HTTP `initialize` 成功；`list_tools` 返回四个只读工具 | 只读角色（INV-AUTH-04） |
| Loop | 定时任务退出码 0 且输出 JSON 报告 | observe → reflect → tickets → adapt propose |

首诊命令：

```bash
curl -s localhost:8000/readyz; curl -s -H "Authorization: Bearer <ops token>" localhost:8000/metrics | head -40
docker compose ps; docker compose logs --since 10m api worker | grep -E '"level": "(WARNING|ERROR)"'
```

## 2. 事故分级

| 级别 | 定义 | 响应 |
| --- | --- | --- |
| S1 | 安全链失效：出现无审计回答、越权命中、金丝雀泄漏、错误版本被引用而无提示 | 立即回滚最近发布（§6.3）或停 API；决策人 30 分钟内知悉；事故记录进 `docs/reviews/` |
| S2 | 服务不可用或大面积 `system_failure`（供应商中断、数据库不可达、GPU 卡死） | 1 小时内恢复或降级；不改任何策略 |
| S3 | 质量退化：升级率 / 弃答率 / 时延显著上升但安全链完好 | 工作日内处理；先看是否与发布相关（§6.3 的版本对照） |
| S4 | 单个用户或单条 Trace 的问题、工单类 | 常规排期 |

安全链的判据来自基线 5.10 与安全集五项门禁：任一「安全指标下降」即 S1，不用等统计显著。

## 3. 告警 → 处置手册

每条都先确认是**服务问题还是环境问题**（记录 77：合盖睡眠与 Wi-Fi 断开曾伪装成故障）。

### 3.1 `system_failure` 升级突增（供应商中断 / 超时）

- 判定：`/metrics` 里 `dependency_unavailable` / `dependency_timeout` 的升级计数上升；Trace 的 answer span 连续 `retry` / `timeout`。
- 行为：系统不给部分答案、不重试超过 2 次、拒答仍先于模型调用（记录 61 / 78）；恢复后无需重启。
- 处置：确认供应商状态与本机网络；等待或切换网络；不要提高重试次数。若 15 分钟不恢复，向用户公告「问答暂不可用，任务排队中」。

### 3.2 `/readyz` 503 或大量 `dependency_unavailable`（数据库）

- 判定：`readyz` 503；请求 5 秒内 503（连接超时 `DB_CONNECT_TIMEOUT_S`）；worker 日志 `dependency unavailable, retrying`。
- 处置：`docker compose ps postgres`、`docker logs medops-postgres --tail 100`；磁盘满 / 容器重启 / 连接数打满（`max_connections` 100）依次排除。恢复后不需要重启服务进程。

### 3.3 `audit_unavailable` 503

- 含义：Trace 写不进去，系统按 5.10 拒绝给答案。
- 处置：检查 `traces` 表的触发器 / 磁盘 / 权限（应用角色只应有 INSERT）；不要为了恢复服务放宽审计写入。

### 3.4 GPU / 重排卡死（`pinned model call … exceeded`）

- 判定：retrieve 节点 `dependency_timeout`（不可重试）；进程 CPU 低但请求堆积。
- 处置：重启该进程（钉住线程无法解除；记录 54 §3.0）；本机 MPS 一次只跑一个模型进程。

### 3.5 队列积压（`tasks` queued 增长、`oldest_queued_age_s` 上升）

- 处置：加 worker 实例（每个自动按租约领取）；确认没有 worker 重复领取（`task_attempts` 每任务一行）；租约（`--lease`）必须大于最长 Skill 执行时间，否则会重复执行（记录 78 §4.2）。

### 3.6 载荷读取失败 / 密钥文件缺失

- 判定：`/admin/traces/{id}/payload` 503 `dependency_unavailable`，或启动日志报 `PAYLOAD_KEY_FILE`。
- 处置：核对密钥文件路径、mode 0600、`current` 版本存在；缺少旧版本密钥会让旧行无法解包裹（`PayloadIntegrityError`）——从密钥备份恢复，不要重新生成同名版本。

### 3.7 灰度后指标变差

- 判定：按 `policy_version` 拆分 `/metrics` 或 Trace：带 `+canary:<id>` 的请求升级率 / 拒答率高于其余。
- 处置：§6.3 回滚；5 秒内所有请求回到前一策略，不需重启。

## 4. 人工升级（escalations）

1. 查看：`select escalation_id, dept, reason_codes, created_at from escalations where status = 'open' order by created_at`（管理角色）。`detail` 给出节点与原因；证据只有 chunk id。需要看原文 / 模型输出时用受限角色读载荷：`GET /admin/traces/{trace_id}/payload?purpose=<≥ 8 字的用途>`（每次读取都记入 `payload_access_log`）。
2. 处理并关闭：`update escalations set status = 'closed', handled_by = '<处理人假名>', handled_at = now(), resolution = '<confirmed_issue|false_alarm|resolved_manually>' where escalation_id = '…'`（管理角色；内容列不可改）。`resolution` 会进入 Loop 的信号视图：`false_alarm` 归因 generation，`confirmed_issue` 归因 knowledge_gap（记录 80）。
3. 用户侧回复走现有渠道（系统只记录，不发送）。
4. 每周核对：未关闭升级的数量与最老时间；超过 5 个工作日未处理进 S3。

## 5. Loop 日常

- 定时：`python -m medops.loop.observe --since <昨天>` → `python -m medops.loop.reflect run` → `python -m medops.loop.tickets` → `python -m medops.loop.adapt propose`（Loop 用户）。
- 人工：`python -m medops.loop.reflect correct --case <id> --attribution <类> --by <假名>`（管理连接）；工单在 `document_requests` 表处理（accepted / rejected / fulfilled + `document_id`）。
- 候选评测：`python evals/replay/tools/replay_run.py --out … --candidate-file …`（先 `--estimate`；`--max-cost-usd` 封顶；`--resume` 续跑），`results.json.gate` 放进候选 `evidence.gate` 才能发布。

## 6. 发布、灰度、回滚（M4-09 / M4-10）

角色：候选作者（Loop 或人）≠ 批准人（`approver`）；发布 / 回滚由 `admin`；推进由 `approver` 且不是作者。所有操作支持 `Idempotency-Key`。

### 6.1 批准与发布

```bash
POST /admin/policies/{id}/approve   {"decision": "approve", "reason": "…"}        # approver，非作者
POST /admin/policies/{id}/release   {"canary_percent": 10, "reason": "…"}          # admin；需要通过的门禁报告
```

确认：响应 `status = released`、`released = true`；5 秒后（`POLICY_RELOAD_TTL_S`）新请求的 `versions.policy_version` 出现 `+canary:<id 前 8 位>`，比例约等于 canary_percent（按主体假名稳定哈希，同一用户永远同侧）。

### 6.2 观察窗与推进

- 观察 `OBSERVATION_WINDOW_HOURS`（默认 24 小时）：按 `policy_version` 拆分升级率、拒答率、时延与安全类升级；任一安全指标下降 → 回滚。
- 推进：`POST /admin/policies/{id}/promote {"canary_percent": 50, "reason": "…"}`（只能放大；未满观察窗返回 409 `observation_window_open`，确需提前时加 `override_reason`（≥ 20 字），会写进发布日志）。到 100% 即全量，`policy_version` 变为 `+rel:<id>`。

### 6.3 回滚

```bash
POST /admin/policies/{id}/rollback  {"reason": "…"}                                # admin
```

一次操作原子切回前一策略（无前策略则回到仓库常量）；TTL 内所有请求恢复，不需重启。确认：新请求 `policy_version` 不再含该 id；`policy_releases` 追加 `rollback` 行。演练记录：`evals/harness/runs/2026-09-25-release-drill-v1/report.md`。

### 6.4 发布前检查单

- [ ] 候选 `evidence.gate` 是回放运行器产出的完整报告且 `passed`（`gate_report_valid`），不是 `drill`。
- [ ] 入库 / 激活之后已运行 `make index-build`（或发件箱消费者），且 `make index-check` 在生产库与安全库都返回 0 缺失；否则新文档不可检索，任何评测都在测旧语料（记录 109）。
- [ ] 语料有变更时已对生产库重跑 `python evals/safety_set/tools/check_safety.py`：PR-S3 / PR-S7 的命中说明安全样本的预期被新文档改变，须列入人工裁决清单后才能把安全运行当作门禁依据（spec-s1 §9，记录 112）。
- [ ] released 的检索参数若指向词表版本，API / worker / MCP 的 `GLOSSARY_DIR` 已配置且该版本文件存在（否则进程启动即快速失败，记录 105）。
- [ ] `(kind, name)` 在运行时支持的目标内（否则 409 `policy_target_unsupported`）。
- [ ] 备份在 24 小时内；恢复演练在 30 天内。
- [ ] 值班人知道回滚命令与 `policy_version` 对照方法。

## 7. 变更与升级窗口

- 迁移：`make migrate` 前先备份（`scripts/db_backup.py`）并确认 `alembic downgrade` 路径存在；失败先 DOWN，再考虑恢复备份（`OPERATIONS.md` §3.3）。
- 依赖 / 镜像升级：`OPERATIONS.md` §4；升级后 `make check` + 一次真实问答冒烟。
- 长时间运行（评测、摄取）：`caffeinate -i -s` 启动，笔记本开盖或接电（记录 77 §6.2）。

## 8. 事故记录模板

放在 `docs/reviews/YYYY-MM-DD-incident-NN-<slug>.md`：时间线（UTC）、影响面（请求数 / 部门 / 是否触及安全链）、根因、处置命令、恢复确认（哪条 Trace / 指标）、后续项与负责人。记录 77 §6.2 与记录 78 §4 是两个范例。
