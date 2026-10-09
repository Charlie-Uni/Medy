# Langfuse 本机部署与观测闭环

当前适配版本为 **Langfuse 4.54.0**。它接收 MedOps 已有的 OpenTelemetry spans，并把评测分数、用户反馈类别与同一个 W3C `trace_id` 关联。PostgreSQL 审计仍是权威记录；Langfuse 是排障和比较界面，不参与请求判定或策略发布。

## 1. 选择与边界

| 方案 | 能力 | 本项目结论 |
| --- | --- | --- |
| Jaeger | 调用树、耗时、错误 | 保留为轻量查看器；不提供 score/feedback 工作流 |
| 托管 Langfuse | trace、score、实验、人工标注 | 不采用；医学业务元数据不离开本机网络 |
| 自建 Langfuse | 与托管版相同的工作流，数据在本机 | 采用；UI 只绑定 `127.0.0.1:3000` |
| 只用 PostgreSQL 与本地报告 | 权威审计、可复现门禁 | 继续保留；没有交互式 trace/score 排障界面 |

`INV-OBS-03` 不变：OTel 不发送问题、提示词、证据或回答。允许字段为 trace/task ID、节点与 observation 类型、版本、耗时、Token、费用、候选数量、受控状态和脱敏 score metadata。受限回放正文仍走独立加密载荷与授权读取。

本机栈与 MedOps 事实面分离。Langfuse 自用 PostgreSQL、ClickHouse、Redis 和 MinIO 都只在 Compose 内网开放；主机只开放 UI/API 的 loopback 端口。使用统计显式关闭，内置 Agent 和实验功能关闭，注册关闭。MinIO 是官方 v4 Compose 的对象存储依赖，AGPL-3.0 组件仅在这个内部本机栈运行；Redis 固定在 7.2 BSD 许可线。

## 2. 固定组件

| 组件 | 固定版本或摘要 | 作用 |
| --- | --- | --- |
| Langfuse web | `4.54.0@sha256:ea9f…f2c` | UI、公共 API、OTLP 接收 |
| Langfuse worker | `4.54.0@sha256:fe7e…1f2` | 异步摄取 |
| ClickHouse | `25.12@sha256:8a79…ba6` | observation/score 分析存储 |
| PostgreSQL | `17-alpine@sha256:b0f9…b24` | 项目、用户和配置 |
| Redis | `7.2-alpine@sha256:ccd6…8ed` | Langfuse 队列 |
| MinIO | `latest@sha256:f746…a18` | S3 兼容事件/媒体存储；摘要已固定 |

完整摘要以 [Compose 文件](../deploy/langfuse/docker-compose.yml)为准。v4.54.0 与 `LangfuseScores` 已审计的 observations v2、scores v3 和 `score-create` ingestion 路径一致；升级必须重新跑本页全部验收，不直接跟随浮动大版本。

## 3. 启动与访问

```sh
make langfuse-init
make langfuse-up
make langfuse-check
```

`langfuse-init` 首次生成 `deploy/langfuse/.env`，并把同一项目的 URL/public key/secret key写入根 `.env`。两个文件均为 `0600` 且被 Git 忽略；命令不会打印秘密。重复执行不会轮换已有值。

UI：<http://127.0.0.1:3000>。本机登录邮箱和密码只保存在 `deploy/langfuse/.env`；需要人工登录时在本机读取 `LANGFUSE_INIT_USER_EMAIL` 与 `LANGFUSE_INIT_USER_PASSWORD`，不要复制到工单、日志或提交中。`make langfuse-ps` 查看六个容器；`make langfuse-down` 停止并保留数据卷。

主机进程可直接使用根 `.env` 的 `LANGFUSE_BASE_URL=http://127.0.0.1:3000`。容器化 MedOps 服务不能把容器内 `127.0.0.1` 当成 Langfuse；正式容器部署应提供同网络 HTTPS 地址和证书，并继续满足 `check_langfuse_base_url` 的 HTTPS 边界。

## 4. 零费用验收

```sh
make langfuse-smoke
make langfuse-outage-test
```

`langfuse-smoke` 不调用模型。它发送一个合成根 span、一个检索 span、一个校验 span，轮询真实 observations v2，再通过持久 SQLite 队列发送 `deployment_smoke` 和合成 `user_feedback` 两个 score，最后通过 scores v3 回读。成功输出应满足：

- `model_calls=0`；
- `observations=3`；
- `scores=2`；
- `linked=true` 且 `feedback_linked=true`。

`langfuse-outage-test` 先等 trace 可见，再停掉 web。第一次发送必须是 `failed=1, pending=1, dead_lettered=0`；重启后必须 `acknowledged=1`，第二次 drain 的 `attempted=0`，远端同 ID score 只能有一条。失败码和队列不含响应正文、凭据或业务文本。

本轮真实 ClickHouse 核验显示三个 observation 的 `input_length=0`、`output_length=0`；metadata 只有 OTel resource、受控版本和 fixture 属性。已有单元测试还会解析实际导出的 protobuf，防止异常消息、问题、证据和输出进入 span。

## 5. 分数与真实反馈同步

评分进程独立于请求事务，服务不可用不会阻塞问答：

```sh
env -u DEBUG venv/bin/python -m medops.worker.observability \
  --database medops_v2 --queue .local/observability/medops-v2.sqlite3

env -u DEBUG venv/bin/python -m medops.worker.observability \
  --run PATH_TO_BOUND_RUN --queue .local/observability/evals.sqlite3 --once
```

反馈只导出 `up/down/correction` 类别和反馈 ID，不导出纠正文案或主体。发送前要求对应 trace 已在同一 Langfuse 项目可见，避免因历史随机 OTel ID或丢失遥测产生孤儿 score。队列默认 10,000 行、30 天、10 次尝试，5 秒至 1 小时指数退避；到限进入可检查的死信，修复后用 `--requeue-score` 显式重放。

## 6. 资源、故障与清理

8 GiB Docker VM 上的本轮稳定占用约 2.8 GiB：web 1.29 GiB、worker 0.55 GiB、ClickHouse 0.75 GiB，其余合计约 0.17 GiB。首次启动 web 在 1400 MiB cgroup 下因 Node 默认堆约 700 MiB而 OOM；当前给 web 3 GiB上限并设置 2 GiB Node heap。生产容量仍应按目标负载重测，不能把本机空载数当作部署规格。

```sh
make langfuse-check             # 健康端点 + 项目 API Key
make langfuse-ps                # 容器状态
docker compose --env-file deploy/langfuse/.env \
  -f deploy/langfuse/docker-compose.yml logs --tail=200 --no-color langfuse-web langfuse-worker
make langfuse-down              # 保留数据卷
```

删除卷会永久删除本机 Langfuse 项目、账号、trace 和 score，只有明确需要全量重建时才运行 `docker compose ... down -v`。若轮换项目 key，使用新队列文件或按运维流程处理旧队列；队列会拒绝把旧目标的数据发送到新项目。

## 7. 当前验收边界

真实 OTLP→observation→score/user feedback→API 回读和一次 outage→retry→幂等恢复已完成。登录页已从本机 UI 渲染；为避免自动化记录本机密码，本轮没有把 bootstrap password 写入浏览器工具日志，因此“登录后从 UI 点进该 trace 并目视 score”仍是 OBS-03 最后一项人工界面检查。它不影响后端关联与故障恢复结论，也不能被写成已完成的 UI 人工排障演示。

实现、错误和逐项证据见[记录 163](reviews/2026-10-09-implementation-163-langfuse-deployment-and-recovery.md)。
