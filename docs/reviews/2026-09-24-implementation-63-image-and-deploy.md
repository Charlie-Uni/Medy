# 实现记录 63：运行镜像、compose 应用服务与部署说明（M3-12）

- 日期：2026-09-24
- 范围：基线 4.3 / §8 M3-12 的运行时交付形态：多阶段、非 root、哈希锁定依赖的镜像；`/healthz` 与 `/readyz`；三个进程（API、worker、MCP）的优雅停机语义；compose 里的应用服务（`app` profile）；配置与密钥隔离；持久化与部署说明。
- 依据：基线 4.3、5.12（生产禁 debug / docs）、§8 M3-12「固定依赖、非 root 镜像、health/readiness、优雅停机；配置/密钥隔离、持久化和部署说明」；记录 58（健康探针与 serve 入口）、59（worker 优雅停机）、62（MCP serve）。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 一份镜像三个入口（api / worker / mcp 只是 `command` 不同），builder 阶段按 `make install` 的顺序 `--require-hashes` 安装三份锁（含 embed 锁，因为 API 与 MCP 的检索需要嵌入与重排模型），运行阶段只带虚拟环境、迁移与 `alembic.ini` | 4.3「多阶段、固定依赖」；三个进程共享同一代码与版本集，避免漂移 |
| 基础镜像 `python:3.11-slim` 以多架构索引 digest 钉死（2026-09-24 解析），与 compose 里 postgres / redis 的做法一致 | ADR-0006 第 6 项的既有惯例 |
| 运行用户 `medops`（uid 10001），无编译工具与包缓存；`.dockerignore` 排除 `.env`、venv、语料、评测运行、模型缓存、文档与测试 | 4.3「非 root」「配置/密钥隔离」 |
| `HEALTHCHECK` 用标准库请求 `/healthz`（slim 无 curl）；就绪探针 `/readyz` 查数据库 | 记录 58 已有端点 |
| compose 应用服务放在 `app` profile，`make up` 默认仍只起数据库与缓存；容器用 DSN 通过 `*_DOCKER` 键覆盖（服务名 postgres / redis），模型缓存挂命名卷 `/models`（`MODEL_CACHE_DIR`） | 不改变 M0-11 的本地开发习惯；容器内主机名不同 |
| 迁移不随容器启动自动执行（显式 `make migrate` 或一次性 `compose run`） | 管理 DSN 不进入长期运行的服务进程（记录 58 的角色分离） |
| `stop_grace_period` 30 秒；worker 完成当前任务再退出，超出者靠租约回收且不重复副作用 | 5.7 与记录 59 |

## 2. 交付

- `Dockerfile`、`.dockerignore`、`docker-compose.yml`（`api` / `worker` / `mcp` 服务、`model_cache` 卷）、`.env.example`（四个 `*_DOCKER` 键）、`docs/DEPLOY.md`。
- 验证：`docker build` 成功（日志见构建输出），`docker run --rm medops-copilot:dev python -m medops.api.serve --help` 与 `python -c "import medops, torch"` 在非 root 用户下通过；`docker compose --profile app config` 校验通过。

## 3. 未做 / 限制

- 镜像未在 CI 构建（M0-10 CI 项未做）；SBOM 与镜像扫描属 P1。
- 容器内无 GPU，推理走 CPU；延迟需另测（M3-11）。
- 未做端到端「compose 起全部服务 → 迁移 → 请求」的演练（需要容器可达的 OIDC 配置与 principal 记录；与记录 58/59 的真实库端到端合并做）。

## 4. 自审（§9）

- 镜像内无密钥、无 `.env`（`.dockerignore` + 运行阶段只复制虚拟环境与迁移）；生产 `Settings` 仍禁 debug / docs。
- 非 root 由 `USER medops` 与文件属主保证；健康与就绪探针分离。
- 未改动已冻结数据、生产库与代码逻辑。

## 5. 进度

- M3-12 已实现（镜像、探针、优雅停机、配置隔离、持久化与部署说明齐备；CI 构建与扫描为 M0-10 / P1）。P0 加权进度 53.2%（42.0/79）；按 99 项计 42.4%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 5.5/13、M4 0/10、M5 0/8。
