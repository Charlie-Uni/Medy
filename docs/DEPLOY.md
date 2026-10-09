# 部署说明（M3-12 首版，2026-09-24）

## 镜像

- `Dockerfile` 为多阶段构建：builder 阶段按 `Makefile install` 的顺序安装哈希锁定的依赖（`requirements-build.lock` → `requirements.lock` → `requirements-embed-linux-<arch>.lock` → 项目本身，`--require-hashes` / `--no-build-isolation`），运行阶段只复制虚拟环境与迁移。嵌入栈按 Linux 架构分别锁定（`make lock` 生成 `aarch64` 与 `x86_64` 两份，PyTorch 取 CPU-only 索引），因为 macOS 上生成的 `requirements-embed.lock` 不含 Linux 独有依赖（如 cuda-toolkit）。
- 基础镜像 `python:3.11-slim` 以 digest 钉死（见 Dockerfile 注释，升级时标签与 digest 一起改）。
- 运行阶段以非 root 用户 `medops`（uid 10001）运行，无包管理器缓存，无编译工具。
- 镜像内不含 `.env`、密钥、语料、评测数据与模型缓存（`.dockerignore`）；配置全部来自环境变量（`Settings`，`.env.example` 列出每个键）。
- `HEALTHCHECK` 请求 `GET /healthz`；就绪检查用 `GET /readyz`（应用与检查连接指向同一库、模型线程未卡死、active 语料与生产词法/向量索引完整且版本一致才返回 200，记录 137）。

```bash
docker build -t medops-copilot:dev .
docker run --rm medops-copilot:dev python -m medops.api.serve --help
```

## 进程与优雅停机

| 进程 | 命令 | 停机行为 |
| --- | --- | --- |
| API | `python -m medops.api.serve --host 0.0.0.0 --port 8000` | uvicorn 收到 SIGTERM 后停止接收新连接、等待在途请求完成（每个请求在一个数据库事务内，中断即回滚，不会留下无审计的答案）；停机完成后 uvicorn 会重新抛出捕获的信号，因此进程退出状态是 143（`docker stop` 的正常值），不是 0，日志里以 `Application shutdown complete.` 为准（记录 67） |
| API（管理路由） | 同上 | `/admin/documents*` 与 `/admin/policies*` 在管理数据库角色上执行（INV-AUTH-05），因此 API 进程需要 `DATABASE_ADMIN_URL`；缺失时这些路由返回 503 `dependency_unavailable`；自记录 137 起 `/readyz` 也经管理连接核对索引覆盖、版本与数据库身份，缺失时同样返回 503（其余路由不受影响）。审批人需在 `principals.roles` 含 `approver`（记录 75） |
| Loop（M4） | `python -m medops.loop.observe --since <date>` → `python -m medops.loop.reflect run` → `python -m medops.loop.tickets` → `python -m medops.loop.adapt propose`（定时，依次）；人工：`reflect correct --case … --attribution … --by <假名>`（管理连接）、`adapt submit --file … --by …`；候选评测：`python evals/replay/tools/replay_run.py --out … --candidate-file …`（两臂 × 3 轮，`--estimate` 先看费用，`--max-cost-usd` 封顶），其 `results.json.gate` 放进候选的 `evidence.gate` 才能发布（记录 82） | 在 `DATABASE_LOOP_URL`（`medops_loop_user`，`make db-users` 在设置 `DB_LOOP_PASSWORD` 时创建）上读 `trace_signals`、写 `bad_cases`；Loop 角色对 released 无写权限（记录 79 / 80 集成测试证明）。升级的人工结论写 `escalations.resolution`（管理角色）。**API / worker / MCP 每 `POLICY_RELOAD_TTL_S` 秒（默认 5）重读 released 指针与灰度比例，按主体假名稳定哈希分流（`policy_version` 带 `+rel:` / `+canary:`）；发布、推进、回滚都不需要重启。灰度须坐满 `OBSERVATION_WINDOW_HOURS`（默认 24）才能 `promote`，带 `override_reason` 可提前但会记录。不支持的目标发布时被拒（`policy_target_unsupported`）；`APP_ENV=dev` 才接受 `drill: true` 的演练门禁报告（记录 85）** |
| 受限载荷（DEC-013） | `python -m medops.application.payload_retention [--dry-run]`（每日） | API 在请求事务内把节点输入 / 证据快照 / 模型输出以信封加密写入 `trace_payloads`，需要 `PAYLOAD_KEY_FILE`（JSON：`{"current": "k1", "keys": {"k1": "<base64 32 字节>"}}`，mode 0600，由部署注入，不放 `.env`）；未配置则只写 Trace 不写载荷。读取与清理走 `medops_restricted_user`（`DATABASE_RESTRICTED_URL`，`make db-users` 在设置 `DB_RESTRICTED_PASSWORD` 时创建）；密钥轮换 = 新增 KEK 版本并重包裹 DEK（`medops.core.envelope.rewrap`），密文不动（记录 76） |
| worker | `python -m medops.worker.serve [--lease 300] [--poll 2]` | SIGTERM 后完成当前任务再退出；未完成的任务由租约到期后其他 worker 接管（记录 59）。`--lease` 是租约秒数（默认 300，须大于最长 Skill 执行时间）；故障演练用短租约（记录 78 用 15 秒），生产保持默认 |
| MCP | `python -m medops.mcp.serve --transport streamable-http --host 0.0.0.0 --port 8001` | 同 API；stdio 传输在 `APP_ENV=prod` 下拒绝启动 |

API / worker 的每个数据库连接带 `DB_CONNECT_TIMEOUT_S`（默认 5 秒）与 `DB_STATEMENT_TIMEOUT_MS`（默认 30 秒）：数据库不可达时请求立刻以 503 `dependency_unavailable`（可重试）失败而不是挂起，worker 记录警告后继续轮询（记录 78 的暂停数据库演练）。`/readyz` 的检查连接使用 2 秒连接超时、每条 SQL 1 秒超时；全局索引检查走 `DATABASE_ADMIN_URL` 的只读 REPEATABLE READ 事务，结果最多缓存 5 秒。未配置检查连接、检查失败或应用连接实际库不一致均返回 503。语句超时必须大于最慢的合法语句（摄取与索引重建走独立脚本，不受此限）。

compose 中三个服务的 `stop_grace_period` 为 30 秒；worker 的单任务上限（Skill 超时 ≤ 120 秒）大于该值时，超出部分依赖租约回收，不会重复副作用（operation key 账本）。

## compose

`docker-compose.yml` 除 postgres / redis 外提供 `api`、任务 `worker`、`mcp` 和 `retrieval-cache-worker`（`profiles: [app]`，默认 `make up` 不启动它们）：

```bash
docker compose --env-file .env --profile app up -d --build
docker compose --env-file .env --profile app ps
```

- 容器内访问数据库与 Redis 用服务名，因此 `.env` 需要另给容器用的 DSN：`DATABASE_URL_DOCKER`、`DATABASE_ADMIN_URL_DOCKER`、`DATABASE_READONLY_URL_DOCKER`、`REDIS_URL_DOCKER`（主机名分别为 `postgres`、`redis`）；未设置时回退到主机用的同名键（仅在主机网络下可用）。
- 模型缓存挂载到命名卷 `model_cache`（容器内 `/models`，`MODEL_CACHE_DIR=/models`），首次启动会下载嵌入与重排模型；离线环境请预先填充该卷。
- 词表目录 `GLOSSARY_DIR`（记录 93）：存放已发布的查询改写词表 `glossary-<YYYYMMDD>-<sha12>.json`（仓库副本在 `evals/glossary/`）。一旦 released 的检索参数指向某个词表版本，API / worker / MCP 启动时会校验该文件存在且内容摘要与版本一致，缺失或不一致即以 `dependency_unavailable` 拒绝启动；未发布词表时可留空。检索参数 `multi_query` / `doc_focus` / `query_translation`（记录 93–95）及 `source_constraint`（记录 156，默认关闭）同样只经发布生效；API 与 MCP 搜索都按主体灰度结果应用同一参数，调用翻译模型时把调用次数、token、费用和实际策略/检索版本写入各自 Trace。`source_constraint` 启用后只在调用者可见的 active 文档内解析高置信点名来源，并将两个检索通道限制到该来源；正式答案级对照通过前不得发布。
- 调用链查看：`make observability-up` 可启动轻量 Jaeger。需要 score/feedback 工作流时使用已验证的 Langfuse v4.54.0 本机栈：`make langfuse-up`，UI 为 `http://127.0.0.1:3000`。初始化会安全生成项目 key 并写入本机 `.env`，不要再设冲突的手工 OTLP target/header。两种后端的 span 都不含提示词、证据或回答（INV-OBS-03）。完整部署、资源和故障恢复见 [Langfuse 运维说明](LANGFUSE.md)与记录 163。
- 模型路由 `model_route/answer`（记录 122）：第三个可发布目标，按意图类型指定作答模型（gpt-6-sol 或 gpt-6-luna）；未发布时全部走 gpt-6-sol。判定模型不受路由影响。生效的路由出现在响应的 `versions.model_config_version` 里（`;route=`）。它按 `spend` 档位（每题费用降 25%、质量不降）过门禁后才能发布。
- 检索缓存 `RETRIEVAL_CACHE`（记录 121、145、164；部署示例为 `redis`）：`memory` 为每个 API/MCP 进程一份，`redis` 经 `REDIS_URL` 共享。`RETRIEVAL_CACHE_NAMESPACE` 必须按环境/数据库独立，`RETRIEVAL_CACHE_DATABASE` 是持续消费者的显式目标。缓存的是一次检索融合后的候选清单与重排顺序；**命中后仍在提问者的连接里逐块复核权限、版本状态与内容哈希**，所以撤权、归档、内容变更不会形成失效证据。`retrieval-cache-worker` 持续消费发布、归档、撤回及 ACL 事件并提升部门 epoch；`make cache-invalidate` 只作为一次性追赶。worker 停止时旧条目最多保留 `RETRIEVAL_CACHE_TTL_SECONDS`（默认 300 秒），期间可能发现不了新文档。Redis 不可用时自动降级为未命中；评测与回放工具不使用缓存。
- 作答上下文布局 `evidence_focus`（记录 113）：同为 `retrieval_params/hybrid` 下只经发布生效的键，取值 `off`（默认，提示词与历史完全一致）、`compact-v1`（证据块头部的 chunk / 文档 UUID 换成短别名，证据正文不动）、`sentfocus-v1` / `sentfocus-v2`（再按问题相关性只显示每段的部分句子，用已加载的本机重排模型打分）。不需要额外部署件；逐句版本在作答节点前多一次本机打分（真实语料上每题约 1–2 s，见记录 113），会计入普通问答时延。状态、校验与引用始终使用完整分块；该键只改变 `model_config_version`（后缀 `;ctx=`），不改变检索版本与缓存键。
- 迁移不在容器启动时自动执行：`make migrate`（主机）或 `docker compose --profile app run --rm api python -m alembic upgrade head`（使用管理 DSN）。
- 端口只绑定 `127.0.0.1`；对外暴露须经反向代理与 TLS，bearer token 的 issuer / audience 见 `OIDC_*` 键。

## 持久化

- PostgreSQL 数据卷 `postgres_data`（事实平面、任务、Trace、审计），Redis 数据卷 `redis_data`（检索缓存，可丢失），模型缓存卷 `model_cache`（可重建）。
- 备份、恢复演练、保留清理与密钥轮换见 `docs/OPERATIONS.md`（记录 87）；事故响应与发布 / 回滚操作见 `docs/RUNBOOK.md`。连续归档与异地灾备属 P1（基线 7.1）。

## 未做

- SBOM、镜像扫描（P1）；镜像未推送到任何仓库；CI 里的镜像构建随 M0-10 CI 项。
- 容器内的 GPU（MPS）不可用，运行时用 CPU 推理，延迟高于记录 54 的本机数字。

## 入库后的索引构建（记录 109）

`ingestion.load` 与 `ingestion.activate` 只写文档、片段与发件箱事件，不构建检索索引。每次入库或激活之后必须运行 `make index-build ACTOR=<id> ADMIN_URL=<目标库管理 DSN> DEVICE=mps`（按 ACL 重建 MA/PV/CO 三个 BM25 语料索引、补齐 `chunk_embeddings`、核对覆盖），生产库与安全库各一次；或运行发件箱消费者。`make index-check` 返回非 0 表示有已激活文档的 ACL/chunk 组合不在词法索引里，或 chunk 没有向量：它们不会被完整检索。评测与性能工具在启动前强制做同一检查。

### 持续索引维护（记录 138）

完整构建及版本核对后，可以用下列独立进程处理增量事件。`--database` 必填，只指定库名，主机和密码从 `DATABASE_ADMIN_URL` 读取；不跟随本机旧库默认值。

```sh
env -u DEBUG venv/bin/python -m medops.worker.retrieval --database medops_v2 --consumer lexical-index
env -u DEBUG venv/bin/python -m medops.worker.retrieval --database medops_v2 --consumer vector-index --device cpu
# 仅当运行时已配置同一共享 Redis 缓存时启动；off / memory 会拒绝。
env -u DEBUG venv/bin/python -m medops.worker.retrieval --database medops_v2 --consumer retrieval-cache

# Compose 管理的持续缓存消费者（构建、启动并等待 PostgreSQL + Redis 专用健康检查）
make cache-worker-up
make cache-worker-ps
```

- 每个进程默认每批 10 条（1–100）、空闲或失败等待 2 秒（0.1–60）；`--once` 只处理一批，失败返回非零。一次批次成功不表示全队列已清空，以 `retrieval-check` 的各消费者 pending 为准。
- 词法、向量、缓存各用自己的 ACK 和失败账本。单个事件处理失败回滚它的派生数据和 ACK；错误类型以 `consumer:ExceptionType` 保存，错误原文和正文不进入日志。按 5 秒起、最多 1 小时指数退避；默认第 10 次失败进入该消费者的死信，仍不写 ACK。修好根因后运行 `python -m medops.worker.retrieval --database <库名> --consumer <消费者> --requeue-event <event_id> --actor <操作人>`，再检查覆盖、pending 与 dead-letter 指标。
- 事件按当前文档状态处理，防止旧事件覆盖新状态。active 和 archived 的索引保留，供普通/显式历史检索分别过滤；draft/withdrawn 从派生索引移除。事实表和权限由原发布链维护，消费者不修改它们。
- 向量增量只处理该文档缺失的块，需已有相符的索引元数据；缺元数据或版本漂移必须先明确构建，不能靠改版本字符串通过。元数据中的 build 数量是构建快照，当前覆盖以真实索引行检查为准。
- SQL 使用配置的语句/连接超时和 5 秒锁等待超时；本机 embedding 推理在单个工作线程顺序执行。每批数量有界并不表示 embedding 有硬时长上限，GPU 驱动卡死仍需进程监督器处理。SIGTERM 在当前批次结束后退出。
- 本轮提供可独立运行的入口，未自动启用长期系统服务、未追加 compose 服务；一次恢复和短时轮询检查不算长期驻留部署完成。CPU embedding 进程也需额外模型内存，部署时单独安排资源。
- `lexical-index` 应统一由这个生产维护入口处理；早期候选实验消费者的归档删除策略仅供原实验使用，不与生产维护混用。首次恢复后检查 active 覆盖与历史查询；不能只看 ACK 数。

`/readyz` 在线索法或向量消费者存在死信，或其未 ACK 事件最老年龄超过 300 秒时返回 503；`/metrics` 对三个消费者分别给出 pending、oldest age 与 dead-letter 数。`RETRIEVAL_CACHE=redis` 时，缓存消费者使用相同阻塞规则；`off` / `memory` 时仍只告警。阈值用于运行完整性，不修改质量验收门槛。

## Langfuse 评分同步（记录 141–145、163）

仓库默认模板不导出；本机运行 `make langfuse-init` 后才在忽略的 `.env` 中显式启用。三个服务及主集/安全工具使用同一项目的 OTLP/HTTP 认证，只发送结构、用量和版本；不要另设冲突的 OTLP 目标或认证头。后端适配和实际部署均固定 v4.54.0，升级时须重新执行 `make langfuse-smoke` 与 `make langfuse-outage-test`。

评分同步使用独立进程，不接入请求事务。正式凭据准备好后：

```sh
# 只读采集一批反馈进本机队列，不发送 HTTP。
env -u DEBUG venv/bin/python -m medops.worker.observability \
  --database medops_v2 --queue .local/observability/medops-v2.sqlite3 --enqueue-only

# 持续采集并发送；SIGTERM 在当前 HTTP 请求完成后停止后续发送。
env -u DEBUG venv/bin/python -m medops.worker.observability \
  --database medops_v2 --queue .local/observability/medops-v2.sqlite3

# 从有条件/数据集绑定、trace_id 和时间的新主集或安全运行导入分数。
env -u DEBUG venv/bin/python -m medops.worker.observability \
  --run PATH_TO_BOUND_RUN --queue .local/observability/evals.sqlite3 --once
```

使用 loop 读取账号，未配置时才使用 admin 账号，并强制只读事务。实际数据库名必须显式给出。队列权限 0600、Git 忽略，绑定目标 URL/public key 指纹；更换项目应使用新队列，密钥轮换需要明确处理旧队列。示例命令本身不安装常驻服务。

反馈只同步类别，无纠正文案。评测规则分不冒充语义质量分，未触发样本导出状态。发送前读取 observations v2 的 core 字段，trace 不存在则保留待送。SQLite 队列默认最多 10,000 行、30 天、10 次尝试，按 5 秒到 1 小时退避；到限进入死信，修复后用 `--requeue-score <score_id>` 重放。已投递收据在容量不足时最先清理，待送/死信占满则拒绝继续入队。score 使用固定 ID 与时间的 `score-create` ingestion 事件；真实 v4.54.0 已验证 ingestion 接受、scores v3 回读与 outage 恢复。完整约束见[记录 142](reviews/2026-10-08-implementation-142-durable-observation-scores.md)、[记录 145](reviews/2026-10-08-implementation-145-operational-ledgers-and-mcp-parity.md)及[记录 163](reviews/2026-10-09-implementation-163-langfuse-deployment-and-recovery.md)。
