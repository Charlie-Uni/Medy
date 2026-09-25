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
- 迁移不在容器启动时自动执行：`make migrate`（主机）或 `docker compose --profile app run --rm api python -m alembic upgrade head`（使用管理 DSN）。
- 端口只绑定 `127.0.0.1`；对外暴露须经反向代理与 TLS，bearer token 的 issuer / audience 见 `OIDC_*` 键。

## 持久化

- PostgreSQL 数据卷 `postgres_data`（事实平面、任务、Trace、审计），Redis 数据卷 `redis_data`（检索缓存，可丢失），模型缓存卷 `model_cache`（可重建）。
- 备份与恢复演练属 P1（基线 7.1）。

## 未做

- SBOM、镜像扫描（P1）；镜像未推送到任何仓库；CI 里的镜像构建随 M0-10 CI 项。
- 容器内的 GPU（MPS）不可用，运行时用 CPU 推理，延迟高于记录 54 的本机数字。
