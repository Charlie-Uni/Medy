# 实现记录 163：Langfuse 真实部署、关联与故障恢复

- 日期：2026-10-09
- 基线：Git `308acee` 加本轮工作区
- 授权：用户在询问“接下来做langfuse？”后回复“开始”
- 模型调用与费用：0 次，0 USD
- 结论：OBS-02、OBS-04 完成；OBS-03 的真实后端关联完成，尚差登录后的 UI 目视排障一步

## 1. 本轮交付

1. 新增独立 [Langfuse Compose](../../deploy/langfuse/docker-compose.yml)：web/worker 固定 4.54.0，依赖镜像全部带 digest；只有 web 绑定 `127.0.0.1:3000`，PostgreSQL、ClickHouse、Redis、MinIO 不发布主机端口。
2. 新增 `scripts/langfuse_local.py` 和 Make 入口：生成不回显的本地密钥并同步应用项目 key、健康与鉴权检查、零模型调用的 trace/score/feedback smoke、真实 outage/recovery。
3. 保持 `INV-OBS-03`：未改变 telemetry 字段、冻结数据、模型、策略、检索、评分门槛或事实库。Langfuse 只存元数据；PostgreSQL 审计仍为权威。
4. 新增[运维文档](../LANGFUSE.md)，包含方案比较、许可与数据边界、组件摘要、启动、验证、资源、故障和清理步骤。

## 2. 为什么这样部署

使用同网络自建而非云端，沿用 2026-09-24 “如需看板只在同网络自建”的边界。Langfuse 相比现有 Jaeger 多出 score、feedback、实验和人工标注工作流；Jaeger 仍适合低资源的调用树查看。v4.54.0 是应用评分适配器逐源码核对过的版本；2026-10-09 同日发布的 4.56.0 没有直接替换，以免把未审计接口变化混进本轮。

官方 v4 栈需要 ClickHouse、PostgreSQL、Redis 和 S3 对象存储。为了减少兼容变量，使用官方 Compose 的 MinIO 路径，只限内部本机运行；Redis 固定 7.2，避免回到项目已否决的 7.4 许可证线。依赖不复用 MedOps 事实库与运行时 Redis，避免迁移、队列、备份和故障互相影响。

## 3. 真实验证

| 检查 | 结果 |
| --- | --- |
| 六容器启动 | web、worker、PostgreSQL、ClickHouse、Redis、MinIO 全部运行；有 healthcheck 的服务 healthy |
| 健康与项目认证 | `/api/public/health=200`；带项目 key 的 observations v2 `=200` |
| 合成 Trace | `b5a59366479c12be498b98090232df96`，3 个 observation 可见 |
| 分数关联 | `deployment_smoke` 与 `user_feedback` 各 1 条，scores v3 回读 2 条，同一 trace ID |
| 内容边界 | ClickHouse `events_full FINAL`：3 行的 `input_length=0`、`output_length=0`；metadata 仅允许的版本/resource/fixture 属性 |
| outage | trace `066aebda7eb27c18154f3d1861a5234b`；停 web 后 attempted 1 / failed 1 / pending 1 / dead-letter 0 |
| recovery | 重启后 attempted 1 / acknowledged 1 / pending 0；再次 drain attempted 0；远端同 ID score 1 条 |
| UI | 本机登录页正常渲染；没有向 UI 自动化工具传 bootstrap password，登录后 detail 目视待人工 |
| 稳定资源 | web 1.291 GiB、worker 552 MiB、ClickHouse 753 MiB、PostgreSQL 85 MiB、Redis 10 MiB、MinIO 73 MiB，合计约 2.8 GiB |

以上两个 trace 都是公开合成 fixture，没有模型调用、医学正文或真实人员数据。结构化运行证据见[验证结果](2026-10-09-implementation-163-verification-results.json)。

## 4. 遇到的错误、原因与补救

| 现象/原错误 | 原因 | 修复与复测 |
| --- | --- | --- |
| `make langfuse-init` 首次返回 `ValidationError` | 宿主环境继承 `DEBUG=release`，项目的 `debug: bool` 正确拒绝；与记录 126/153 的历史环境相同 | Langfuse Make 入口按仓库既有做法用 `env -u DEBUG`；没有放松 Settings 或改宿主环境。随后配置解析通过 |
| web 反复退出，日志原文 `FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory` | 初始 `mem_limit: 1400m` 使 Node 推导的堆上限约 700 MiB；v4 首启迁移后注册 MCP 工具目录时超过该上限 | web cgroup 上限改 3 GiB，`NODE_OPTIONS=--max-old-space-size=2048`；重建后 restart count 0，稳定约 1.29 GiB |
| 主机 `GET /api/public/health` 为 200，但 Compose 判 unhealthy；容器内访问 127.0.0.1/localhost 均 `ECONNREFUSED` | 该镜像的 Next.js 监听容器 hostname 对应接口，并未监听容器 loopback | healthcheck 改为请求 `os.hostname():3000`；重建后 healthy，主机 loopback 仍为唯一发布端口 |
| 第一次 `docker compose up --wait` 失败 | 上述 OOM 与错误 healthcheck 叠加 | 没有删除已完成的迁移卷；逐项修正后在已有卷重启、health/auth/smoke/outage 全通过 |

## 5. 自审

| 项目 | 结论 |
| --- | --- |
| 需求与范围 | 通过。完成真实自建服务、应用配置、后端关联和恢复；未把模型运行或业务质量门禁混入本轮 |
| 正确性与失败路径 | 通过。真实 API 写读一致；服务中断时队列保留、退避、恢复后单次投递；首次启动错误均复测 |
| 权限与可追溯性 | 通过。UI 只在 loopback；依赖无主机端口；秘密 0600/Git 忽略/不回显；正文长度实测为 0 |
| 验证 | 后端范围通过。Compose config、health、auth、OTLP、observations v2、ingestion score、scores v3、ClickHouse 内容及 outage 都有真实证据；登录后 UI detail 尚未目视 |
| 状态与文档 | 通过。OBS-02/04 记 DONE，OBS-03 保留 READY；不以 API 证据冒充已完成 UI 人工排障 |

## 6. 剩余动作

人工从 `deploy/langfuse/.env` 读取本机 bootstrap 账号登录已经打开的 <http://127.0.0.1:3000>，按本记录 trace ID 检查三个节点与两个 score。完成后 OBS-03 才改为 DONE。正式模型请求无需为了 Langfuse 再跑；下一项可按阶段表进入指定来源答案级付费门禁，或继续第二批 Redis，但都遵守各自授权规则。

全量 `make check` 最终为 **1713 passed、70 skipped、1 条既有短 HMAC key warning**；Ruff、441 个维护文件格式、189 个源文件 mypy、评测输入审计和 Schema 漂移全部通过。运行时显式清空 Langfuse 环境键，避免软件测试把 fixture spans 写进刚创建的真实项目；真实目标另由本记录的 health/smoke/outage 检查覆盖。
