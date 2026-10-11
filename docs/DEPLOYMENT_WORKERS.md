# 常驻消费者、调度与进程监督（ARCH-13）

实现范围与证据见[记录186](reviews/2026-10-11-implementation-186-worker-deployment-and-supervision.md)。这是可部署的工程配置与隔离故障验证；生产长期驻留、容量验收和备份恢复仍由 IDX-03 / DEPLOY-02 跟踪。本轮没有替换现有容器，也没有调用托管模型。

## 1. 资源与权限分配

| 服务 | profile | 内存上限 / CPU 上限 | 数据库职责 | 其他资源 |
| --- | --- | --- | --- | --- |
| API | app | 8 GiB / 2 | app；审批及完整性检查使用 admin | 模型缓存；镜像内版本词表；可选只读 KEK |
| Task worker | app | 8 GiB / 2 | app；沿用已批准的 Task 执行及费用账本 | 模型缓存；版本词表；可选只读 KEK |
| MCP | app | 8 GiB / 2 | readonly | 模型缓存；版本词表；不挂 KEK |
| lexical-index-worker | app | 512 MiB / 1 | admin，仅重建派生 BM25 数据及 outbox ACK | 无模型加载；每批 1 事件 |
| vector-index-worker | app | 4 GiB / 2 | admin，仅维护派生向量及 outbox ACK | 固定 BGE-M3、本地 CPU、模型缓存；每批 1 事件 |
| retrieval-cache-worker | app | 256 MiB / 0.5 | admin 读事件/写 ACK；Redis 更新 epoch | 与应用相同数据库/namespace |
| score-sync-worker | score-sync | 256 MiB / 0.5 | loop；历史兼容允许 admin，但强制只读采集 | 独立 `score_queue` 卷；显式 Langfuse 项目 |
| payload-retention | maintenance | 256 MiB / 0.5 | restricted，仅执行既有载荷保留规则 | 不解密，不需要 KEK |
| audit-retention | maintenance | 256 MiB / 0.5 | admin，既有 365 天规则/事务删除栅栏 | 不改永久审计记录、未关闭升级保留规则 |
| loop-observe | loop-observe | 256 MiB / 0.5 | loop，读信号、幂等建案例 | 每 300 秒；不生成/评测/激活候选 |

这些是起始**限制值，不是实测需求、内存预留或吞吐承诺**。同一服务的重复字段来自 Compose 的 `x-supervised-worker`；应用进程仍分别拥有模型运行时，ARCH-10 只在单个运行时内共享重排权重。

全开应用/维护容器的内存限制合计 29.75 GiB，另外还有 PostgreSQL、Redis、Langfuse 和操作系统。本机 Docker 可用约 7.75 GiB，不能用它证明全套模型服务同时运行的容量。部署者先按业务选择所需进程，在目标环境测 RSS、CPU、OOM、排队和服务 P95，再确定最终资源；DEPLOY-02 尚未完成。本轮不调整 Redis maxmemory 或其淘汰策略。

## 2. 容器可见的配置与秘密

1. 版本词表作为公开运行配置随镜像复制到 `/app/glossary`；API/Task/MCP 显式设置 `GLOSSARY_DIR=/app/glossary`，不会继承宿主机绝对路径。现有加载器仍核对已发布版本和内容摘要，缺失/漂移即失败。镜像不携带评测题、PDF、语料或 `.local`/output。
2. 模型使用命名卷 `/models`；向量消费者与三个运行时复用下载缓存，但各进程分别加载权重。首次联网下载/离线预填充仍是部署责任；初始化超时可以根据目标环境调整。
3. KEK 不进镜像。启用加密载荷时明确叠加 `docker-compose.payload.yml`，把 `PAYLOAD_KEY_FILE` 指定的宿主文件只读提供给 API/Task worker，容器读取 `/run/secrets/payload-kek`。未启用 overlay 时，宿主路径不会自动变成容器挂载，错误路径会启动失败，不能据此声明可回放。
4. Compose 的文件型 secret 是绑定挂载，不能用 YAML 的 uid/gid/mode 修复宿主所有权。部署者必须让 UID 10001 可读，且文件为 0600 或 0400；Linux 可把单独的部署副本交给 UID 10001，Docker Desktop 也须以实际容器读取验证。禁止为解决读取失败把密钥改成 0644。本轮只用隔离卷内的合成 KEK，验证了 UID 10001 可读 0600、0644 被现有加载器拒绝；没有读取或修改真实 KEK。
5. 评分队列挂 `/queue`，镜像先创建并赋予 UID 10001；SQLite 文件仍为 0600。不同事实库/项目使用不同队列卷。变更 backend URL/public key 前按[反馈身份契约](FEEDBACK_IDENTITY.md)迁移或新建队列，不能自动猜旧来源。
6. 新增 `DATABASE_RESTRICTED_URL_DOCKER`、`DATABASE_LOOP_URL_DOCKER`，与原容器 DSN 同样验证格式、空串转未配置、秘密屏蔽。清理和 Observe 不回退到更高权限角色。`--database` 仍必填，明确选择应用所在事实库。

```sh
# 先核对配置；输出会含秘密，只在受控终端查看，不保存或提交原始 config。
docker compose --env-file .env --profile app config --quiet
# 全量索引版本/覆盖先完成，且目标环境有足够资源后再启用。
docker compose --env-file .env --profile app up -d --build lexical-index-worker vector-index-worker retrieval-cache-worker
# 真实 KEK 已准备好时，再使用该 overlay 启动所需服务。
docker compose --env-file .env -f docker-compose.yml -f docker-compose.payload.yml --profile app up -d --build api worker
```

只在启动需要的服务时执行 `up`。普通 `make up` 保持只启动 PostgreSQL/Redis；`--profile app up` 会启动所有 app 服务，包括模型进程。

## 3. 心跳与恢复

`python -m medops.worker.supervision` 只允许 retrieval、scores、tasks、maintenance 四种入口。子进程在完成一轮处理后写私有原子心跳；监督器按本次随机 token、子 PID、单调时钟验证。上次运行的文件、其他进程或未来时间都不能使当前运行就绪。空闲但成功的数据库轮询有效；连接失败不刷新进展。毒事件写入失败/死信账本后表示这一轮有进展，不等于该事件处理成功。

Compose healthcheck 查询监督器的健康文件和父 PID，而不是仅 ping PostgreSQL/Redis。健康文件超过 15 秒未刷新、父进程消失、启动未完成或停止都失败。监督器默认启动等待 300 秒；首次进展后 Task/词法/向量/缓存/评分的停滞限分别为 400/90/300/90/180 秒。向量每批 1 事件降低单批工作量，但不是“任意文档 300 秒内一定处理完”的保证；大文档或慢设备需明确调整，持续重启要告警和处置。

MCP 单独检查自身 8001 端口，覆盖镜像默认的 API 8000 检查；这个检查仅证明 socket 存活。API 仍通过 `/readyz` 提供索引/事实库就绪信息，部署验收不得把 MCP socket 或 API `/healthz` 当作检索完整性证据。

卡死时先把健康置失败，向整组进程发 SIGTERM；20 秒仍未结束则 SIGKILL 并回收直接子进程，监督器非零退出，Compose `restart: unless-stopped` 才会重启。`init: true` 收束被收养的子进程。**Docker unhealthy 本身不触发重启**，这里由监督器退出实现恢复。各容器拥有自己的状态目录，宿主多个实例必须设置不同 `--state`。

Task 的优雅收束为监督器 140 秒/容器 150 秒，其余监督消费者为 20 秒/容器 30 秒。超过期限的进程可能被杀；未提交索引/ACK 回滚，任务按原租约和写入栅栏接管。已发出的供应商调用仍可能收费，监督器不保证供应商恰好执行一次，也不增加付费授权。

就绪分三层检查，不能只看容器绿色：

- 进程：心跳是否新鲜，是否频繁重启。
- 数据：`make retrieval-check` 与 `/readyz` 的 active 覆盖、版本、pending 最老年龄、dead-letter。既有 300 秒积压阈值不变。
- 评分投递：队列 collection/delivery 日志中的 pending、failed、dead-letter 和目标身份；心跳表示采集/投递循环可推进，不表示 Langfuse 每次都成功接收。队列退避、容量和死信规则保持不变。

### 毒事件操作

```sh
env -u DEBUG venv/bin/python -m medops.worker.retrieval --database TARGET_DB --consumer lexical-index --requeue-event EVENT_ID --actor OPERATOR
env -u DEBUG venv/bin/python -m medops.worker.retrieval --database TARGET_DB --consumer lexical-index --once
make retrieval-check
```

先定位并修复根因，再显式 requeue；不自动清死信、不写假 ACK。检查清单：单事件派生数据/ACK 已回滚、失败类型被脱敏、死信仍未 ACK、操作者 requeue 被审计、重试后覆盖和 ACK 恢复、其他正常事件未被毒事件阻塞。本轮真实 PostgreSQL 隔离测试完成上述路径；不宣称已在生产注入故障。

## 4. 评分同步的网络边界

现有规则仅允许 HTTPS 或本机回环 HTTP。宿主机 `http://127.0.0.1:3000` 在评分容器里指向该容器自身，不能直接连宿主 Langfuse；`http://langfuse-web:3000` 也不符合现有 HTTPS/回环规则。本轮保留该规则。

- 容器方案：部署者提供容器可达的 HTTPS Langfuse endpoint，确认它与 OTLP 使用同一项目，才启用 `score-sync` profile。若主机和容器域名不同，使用受控的单独部署环境文件；队列指纹随 endpoint 变化须明确处理。
- 本机回环方案：评分同步运行在宿主进程监督下。Linux 提供[systemd 模板](../deploy/systemd/medops-score-sync.service)，需要运维替换仓库路径/数据库名、准备 medops 账号及私有 `.env` 后安装；macOS 可用同一命令接入 launchd。该模板未在 macOS 安装或宣称验证 systemd。

```sh
env -u DEBUG venv/bin/python -m medops.worker.supervision --state .local/observability/worker \
  --kind scores --stall 180 -- --database medops_v2 \
  --queue .local/observability/medops-v2.sqlite3 --batch 10
```

这仍是本机监督命令，关闭终端后要由 OS 服务管理器接续。禁止把 HTTP allowlist 偷改成任意内网地址以让示例运行；若以后采用内网 HTTP，先单独记录并批准网络信任边界。

## 5. 调度责任与边界

| 作业 | 负责方 / 调度 | 失败恢复与限制 |
| --- | --- | --- |
| 词法/向量/缓存 | 运维启用 app 的对应常驻服务 | 监督重启、outbox 退避和人工死信重放；先完整 bootstrap，不修造版本 |
| 评分同步 | 运维选择容器 HTTPS 或宿主服务管理器 | 持久队列、固定 score ID、显式 requeue；不得跨项目复用队列 |
| 载荷清理 | 运维显式启用 maintenance，restricted，每次成功后等 86400 秒 | 启动立即执行既有规则；事务回滚/失败退出重启；无需 KEK |
| 审计清理 | 同 profile，admin，每次成功后等 604800 秒 | 保留原 365 天/≥90 天限制、升级和工单保护；永久表不删 |
| Observe | 运维显式启用 loop-observe，loop，每次成功后等 300 秒 | 从 1970 起扫描全部保留 Trace，避免晚到反馈漏采；按 Trace 幂等；大库完整扫描成本仍需测 |
| Reflect / tickets / adapt | 实现者/业务负责人按现有流程执行 | 当前仍需人工/显式候选流程，不等于模型自进化；生成、评测、发布不在本调度白名单 |
| 每日备份 / 每月恢复演练 / 轮换 | 运维保留[既有操作手册](OPERATIONS.md)的外部定时任务 | 需 Docker/备份存储权限，未塞进应用镜像；DEPLOY-02/目标环境安装证据仍待补 |

调度是“成功后等待固定间隔”，不是日历 cron；重启会立即重跑。数据库/作业的事务 advisory lock 避免多个调度实例重叠，关闭事务即释放，原清理/Observe 均保持幂等。失败不会等待一整天才重试，而由进程重启策略恢复。首次部署先执行 `medops.worker.maintenance --database TARGET_DB --job JOB --dry-run` 并核对保留规则，再启用 profile；不要把演练回滚结果写成实际删除。

全量自审发现并修复了晚到审计记录的清理冲突：Trace 虽已满 365 天，相关新反馈/案例/span/已关闭升级/回放报告仍各有保留时钟。清理候选现在等待这些关联记录也到期，避免触发追加写保护而使整个批次回滚；原期限、数据库删除栅栏和永久表没有变。五类真实 PostgreSQL 回归同时证明新材料保留、无关联新材料的过期 Trace 仍可清理。

本轮没有改变用户已批准的 Agent 目标、盲测门槛、自动激活仅实验环境的边界，也没有完成 PLAN-02 或解锁 S2/S3。
