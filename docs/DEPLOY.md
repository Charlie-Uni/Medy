# 部署说明（M3-12 首版，2026-09-24）

## 镜像

- `Dockerfile` 为多阶段构建：builder 阶段按 `Makefile install` 的顺序安装哈希锁定的依赖（`requirements-build.lock` → `requirements.lock` → `requirements-embed-linux-<arch>.lock` → 项目本身，`--require-hashes` / `--no-build-isolation`），运行阶段只复制虚拟环境与迁移。嵌入栈按 Linux 架构分别锁定（`make lock` 生成 `aarch64` 与 `x86_64` 两份，PyTorch 取 CPU-only 索引），因为 macOS 上生成的 `requirements-embed.lock` 不含 Linux 独有依赖（如 cuda-toolkit）。
- 基础镜像 `python:3.11-slim` 以 digest 钉死（见 Dockerfile 注释，升级时标签与 digest 一起改）。
- 运行阶段以非 root 用户 `medops`（uid 10001）运行，无包管理器缓存，无编译工具。
- 镜像内不含 `.env`、密钥、语料、评测数据与模型缓存（`.dockerignore`）；配置全部来自环境变量（`Settings`，`.env.example` 列出每个键）。
- `HEALTHCHECK` 请求 `GET /healthz`；就绪检查用 `GET /readyz`（数据库可达才返回 200）。

```bash
docker build -t medops-copilot:dev .
docker run --rm medops-copilot:dev python -m medops.api.serve --help
```

## 进程与优雅停机

| 进程 | 命令 | 停机行为 |
| --- | --- | --- |
| API | `python -m medops.api.serve --host 0.0.0.0 --port 8000` | uvicorn 收到 SIGTERM 后停止接收新连接、等待在途请求完成（每个请求在一个数据库事务内，中断即回滚，不会留下无审计的答案）；停机完成后 uvicorn 会重新抛出捕获的信号，因此进程退出状态是 143（`docker stop` 的正常值），不是 0，日志里以 `Application shutdown complete.` 为准（记录 67） |
| API（管理路由） | 同上 | `/admin/documents*` 与 `/admin/policies*` 在管理数据库角色上执行（INV-AUTH-05），因此 API 进程需要 `DATABASE_ADMIN_URL`；缺失时这些路由返回 503 `dependency_unavailable`，其余路由不受影响。审批人需在 `principals.roles` 含 `approver`（记录 75） |
| Loop（M4） | `python -m medops.loop.observe --since <date>` → `python -m medops.loop.reflect run` → `python -m medops.loop.tickets` → `python -m medops.loop.adapt propose`（定时，依次）；人工：`reflect correct --case … --attribution … --by <假名>`（管理连接）、`adapt submit --file … --by …`；候选评测：`python evals/replay/tools/replay_run.py --out … --candidate-file …`（两臂 × 3 轮，`--estimate` 先看费用，`--max-cost-usd` 封顶），其 `results.json.gate` 放进候选的 `evidence.gate` 才能发布（记录 82） | 在 `DATABASE_LOOP_URL`（`medops_loop_user`，`make db-users` 在设置 `DB_LOOP_PASSWORD` 时创建）上读 `trace_signals`、写 `bad_cases`；Loop 角色对 released 无写权限（记录 79 / 80 集成测试证明）。升级的人工结论写 `escalations.resolution`（管理角色）。**API / worker / MCP 每 `POLICY_RELOAD_TTL_S` 秒（默认 5）重读 released 指针与灰度比例，按主体假名稳定哈希分流（`policy_version` 带 `+rel:` / `+canary:`）；发布、推进、回滚都不需要重启。灰度须坐满 `OBSERVATION_WINDOW_HOURS`（默认 24）才能 `promote`，带 `override_reason` 可提前但会记录。不支持的目标发布时被拒（`policy_target_unsupported`）；`APP_ENV=dev` 才接受 `drill: true` 的演练门禁报告（记录 85）** |
| 受限载荷（DEC-013） | `python -m medops.application.payload_retention [--dry-run]`（每日） | API 在请求事务内把节点输入 / 证据快照 / 模型输出以信封加密写入 `trace_payloads`，需要 `PAYLOAD_KEY_FILE`（JSON：`{"current": "k1", "keys": {"k1": "<base64 32 字节>"}}`，mode 0600，由部署注入，不放 `.env`）；未配置则只写 Trace 不写载荷。读取与清理走 `medops_restricted_user`（`DATABASE_RESTRICTED_URL`，`make db-users` 在设置 `DB_RESTRICTED_PASSWORD` 时创建）；密钥轮换 = 新增 KEK 版本并重包裹 DEK（`medops.core.envelope.rewrap`），密文不动（记录 76） |
| worker | `python -m medops.worker.serve [--lease 300] [--poll 2]` | SIGTERM 后完成当前任务再退出；未完成的任务由租约到期后其他 worker 接管（记录 59）。`--lease` 是租约秒数（默认 300，须大于最长 Skill 执行时间）；故障演练用短租约（记录 78 用 15 秒），生产保持默认 |
| MCP | `python -m medops.mcp.serve --transport streamable-http --host 0.0.0.0 --port 8001` | 同 API；stdio 传输在 `APP_ENV=prod` 下拒绝启动 |

API / worker 的每个数据库连接带 `DB_CONNECT_TIMEOUT_S`（默认 5 秒）与 `DB_STATEMENT_TIMEOUT_MS`（默认 30 秒）：数据库不可达时请求立刻以 503 `dependency_unavailable`（可重试）失败而不是挂起，worker 记录警告后继续轮询（记录 78 的暂停数据库演练）；`/readyz` 用 2 秒连接超时。语句超时必须大于最慢的合法语句（摄取与索引重建走独立脚本，不受此限）。

compose 中三个服务的 `stop_grace_period` 为 30 秒；worker 的单任务上限（Skill 超时 ≤ 120 秒）大于该值时，超出部分依赖租约回收，不会重复副作用（operation key 账本）。

## compose

`docker-compose.yml` 除 postgres / redis 外新增 `api`、`worker`、`mcp` 三个服务（`profiles: [app]`，默认 `make up` 不启动它们）：

```bash
docker compose --env-file .env --profile app up -d --build
docker compose --env-file .env --profile app ps
```

- 容器内访问数据库与 Redis 用服务名，因此 `.env` 需要另给容器用的 DSN：`DATABASE_URL_DOCKER`、`DATABASE_ADMIN_URL_DOCKER`、`DATABASE_READONLY_URL_DOCKER`、`REDIS_URL_DOCKER`（主机名分别为 `postgres`、`redis`）；未设置时回退到主机用的同名键（仅在主机网络下可用）。
- 模型缓存挂载到命名卷 `model_cache`（容器内 `/models`，`MODEL_CACHE_DIR=/models`），首次启动会下载嵌入与重排模型；离线环境请预先填充该卷。
- 词表目录 `GLOSSARY_DIR`（记录 93）：存放已发布的查询改写词表 `glossary-<YYYYMMDD>-<sha12>.json`（仓库副本在 `evals/glossary/`）。一旦 released 的检索参数指向某个词表版本，API / worker / MCP 启动时会校验该文件存在且内容摘要与版本一致，缺失或不一致即以 `dependency_unavailable` 拒绝启动；未发布词表时可留空。检索参数 `multi_query` / `doc_focus` / `query_translation`（记录 93–95）同样只经发布生效，其中 `query_translation` 会在检索前调用一次翻译模型（计入 Trace 费用，MCP 搜索工具不做翻译）。
- 检索缓存 `RETRIEVAL_CACHE`（记录 121，默认 `off`）：`memory` 为每个 API 进程一份，`redis` 经 `REDIS_URL` 共享。缓存的是一次检索融合后的候选清单与重排顺序，键含规范化问题、权限指纹（部门 / 角色 / scope，不含用户 id）、as-of 日期、检索版本与策略版本；**命中后仍在提问者的连接里逐块复核权限、版本状态与内容哈希**，所以撤权、归档、内容变更在命中路径上与未命中路径同样被过滤，缓存只省检索、查询翻译与重排的时间。文档发布 / 归档 / 撤回后运行 `make cache-invalidate`（只对 `redis` 有效）使相关部门的条目立即失效；不运行则条目在 `RETRIEVAL_CACHE_TTL_SECONDS`（默认 300 秒）后过期，其间新文档可能检索不到。`memory` 模式没有跨进程失效，只靠过期时间或重启。Redis 不可用时自动降级为未命中，不报错。评测与回放工具不使用缓存。
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

`ingestion.load` 与 `ingestion.activate` 只写文档、片段与发件箱事件，不构建检索索引。每次入库或激活之后必须运行 `make index-build ACTOR=<id> ADMIN_URL=<目标库管理 DSN> DEVICE=mps`（重建词法索引 `chunk_lexical_tsv`、补齐 `chunk_embeddings`、核对覆盖），生产库与安全库各一次；或运行发件箱消费者。`make index-check` 返回非 0 表示有已激活文档的片段不在索引里：它们不会被任何查询检索到。评测与性能工具在启动前强制做同一检查。
