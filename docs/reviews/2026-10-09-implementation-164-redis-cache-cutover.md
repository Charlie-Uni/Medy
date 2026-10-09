# 实现记录 164：Redis 检索缓存切换、持续失效与故障恢复

日期：2026-10-09。范围：CACHE-01、CACHE-02、CACHE-BACKLOG-01/02 的零模型工程部分。本轮没有调用模型 API，费用为 0；CACHE-10 的真实重复问题流量收益仍需单独付费授权。

## 1. 起点与目标

记录 39 已实现候选缓存，记录 121 才把它接入 API/MCP 检索端口。切换前仍有三个运行缺口：

1. `.env` 没有设置 `RETRIEVAL_CACHE`，程序按默认 `off` 运行；
2. `make cache-invalidate` 只能人工一次性消费，没有 Compose 常驻进程；
3. 主库有 338 条、safety 库有 339 条 `retrieval-cache` 历史未 ACK 事件，最老约 18.9 天。

缓存保存的是融合候选和重排顺序，不保存最终回答。命中后仍以调用者身份逐块回查 PostgreSQL 的 ACL、状态、生效日期、来源完整性、解析质量、正文哈希和页锚点。Redis 因此只能省掉查询翻译、词法/向量检索及重排，不能成为事实面或授权依据。

## 2. 切换实现

### 2.1 部署隔离

- 新增 `RETRIEVAL_CACHE_NAMESPACE`，只允许有界的字母、数字、点、下划线、横线和冒号，并要求尾部冒号。本机主库使用独立前缀 `medops:local:v2:rcache:`；safety 清账使用 `medops:local:v2-safety:rcache:`。
- 新增 `RETRIEVAL_CACHE_DATABASE`，常驻 worker 仍以显式数据库名启动，不从可能指向错误库的 DSN 路径静默推断。
- `RedisCandidateCacheStore.from_settings` 现在默认读取部署 namespace，测试仍可显式传随机 namespace。
- Compose 使用的数据库/Redis DSN 字段纳入严格 Settings 校验并继续以 `SecretStr` 脱敏。实际本机 `.env` 由现有主机 DSN 派生容器服务名 `postgres` / `redis`，文件权限保持 `0600`，凭据没有进入记录或 Git。

固定 namespace 很危险：主库和 safety 库可能拥有相同 query、权限、日期、策略及检索版本，若共用前缀，就可能读到另一数据库的候选 UUID。事实回查会拒绝不存在的 UUID，因此不会越权，但会产生跨库污染、空结果和不必要的回源。独立前缀消除了这一运行歧义。

### 2.2 常驻失效消费者

Compose 新增 `retrieval-cache-worker`：

- 使用既有 `medops.worker.retrieval --consumer retrieval-cache`；
- 通过事务性 outbox 独立 ACK、指数退避、死信和人工重放；
- `restart: unless-stopped`，依赖 PostgreSQL 与 Redis 健康；
- 专用健康检查同时连接显式目标数据库并 ping Redis，不再继承 API 的 8000 端口健康检查；
- `make cache-worker-up/down/ps` 提供可复现运维入口，`make cache-invalidate` 保留为一次性追赶工具。

文档激活、归档、撤回或 ACL 变化后，消费者提升受影响部门的 epoch。新查询使用新 epoch 构造 key，旧条目留到 TTL 自然过期。重复投递只会再次提升 epoch，结果仍安全。

### 2.3 readiness 语义

旧逻辑始终把缓存积压当成非阻塞告警，这是缓存关闭时的正确选择。切换后改为按运行配置判断：

- `off` / `memory`：`retrieval-cache` 积压继续只显示，不影响 readiness；
- `redis`：死信立即阻塞；最老未 ACK 事件超过 300 秒时阻塞；
- 词法和向量消费者原有规则不变。

这避免新文档已经进入事实面但候选缓存仍在 TTL 内看不到它时，服务继续宣称完全就绪。Redis 本身短暂不可用仍按设计回源，因此不会仅因缓存断连把问答关闭。

## 3. 真实清账与运行状态

| 数据库 | 切换前 pending | 本轮 ACK | 失败 | 新死信 | 切换后 pending |
| --- | ---: | ---: | ---: | ---: | ---: |
| `medops_v2` | 338 | 338 | 0 | 0 | 0 |
| `medops_v2_safety` | 339 | 339 | 0 | 0 | 0 |

主库由常驻容器按 10 条一批追赶；safety 用独立 namespace 一次性清账。旧开发库 `medops` 未启用缓存，原有 231 条积压不属于本次生产切换。

切换后 `make retrieval-check`：333 份 active 文档、34,948 个 active chunk、词法缺口 0、向量缺口 0；词法、向量、缓存三个消费者 pending/dead-letter 均为 0；`cache_required=true`、`ready=true`。

Redis 7.2.16 使用 AOF，写入与重写状态均为 `ok`，`evicted_keys=0`。清理测试键后只保留主库与 safety 库各 MA/PV/CO 三个 epoch 键。采样资源：Redis 约 14.61 MiB，cache worker 约 40.48 MiB，worker 重启次数 0。

## 4. 功能与故障演练

### 4.1 本机真实配置 smoke

使用实际 `.env`、实际 Redis namespace 和合成空候选执行两次相同 cache-aside 调用：

| 调用 | 命中 | 计算函数累计调用 | 观测耗时 |
| --- | --- | ---: | ---: |
| 第一次 | 否 | 1 | 7.61 ms |
| 第二次 | 是 | 1 | 1.14 ms |

两次值相同，`degraded=0`；烟测 key 随即删除。这里只证明实际接线与共享命中，不能外推为完整问答 P95 或真实命中率。

### 4.2 Redis 断连与恢复

短暂停止 `medops-redis` 后，同一缓存入口在 5.08 ms 内返回未命中并执行回源函数，`hit=false`、候选 0、`degraded=3`。三次降级分别来自双重命中检查和写回，均只记录 `CacheStoreError` 类型。worker 的依赖探测退出码为 1。脚本的 `finally` 强制重启 Redis；随后 Redis 与 worker 均恢复 `healthy`。

### 4.3 权限与版本场景

- 撤权：已有真实事实面集成测试证明，即使 epoch 尚未提升，命中旧候选也会被 RLS 回查为 `not_visible`，不会形成证据。
- 归档/新版本：新增临时 PostgreSQL + 真实 Redis 端到端测试。旧候选在消费者运行前被状态回查清空；消费归档和激活事件后 MA epoch 提升，下一次为 miss 并找到新版本块。
- Redis 数据损坏：非整数 epoch 现在转换为 `CacheStoreError` 并降级为 miss，避免 `ValueError` 直接打断请求。
- namespace：真实 Redis 测试继续覆盖 TTL、部门 epoch、隔离与 DSN 脱敏。

## 5. 实际遇到的问题与修复

1. **严格配置拒绝容器 DSN。** 写入 `DATABASE_URL_DOCKER`、`DATABASE_ADMIN_URL_DOCKER`、`REDIS_URL_DOCKER` 后，Settings 报三项 `Extra inputs are not permitted`。原因是 `.env.example` 列出了 Compose 键，但之前空值被忽略，Settings 没声明这些字段；一旦真实赋值就失败。修复为显式的可选 `SecretStr` 字段，并复用 PostgreSQL/Redis DSN 校验与空值归一规则。
2. **worker 继承了 API 健康检查。** 第一次启动时消费者已正常 ACK 338 条事件，但容器一直显示 `health: starting`，因为镜像默认探测 `127.0.0.1:8000/healthz`，而该进程不提供 HTTP。修复为 PostgreSQL `select 1` + Redis `PING` 的专用检查，重建后 `healthy`。
3. **集成测试留下随机键。** 自审核发现“损坏 epoch”测试没有依赖负责 teardown 的 store fixture，Redis 留下 3 个 `medops-test:*` 键。改为统一 fixture，删除残留并复跑；现有键集合只含六个部署 epoch。
4. **缓存积压原先不阻塞 readiness。** 这是记录 145 在缓存关闭时的刻意行为；若不随切换调整，常驻消费者停止超过 TTL 时仍会报告 ready。现在只有实际 Redis 模式把缓存消费者加入关键集合，并有正反测试钉住。
5. **空轮询产生高频日志。** 初次常驻运行每 2 秒打印一个空批次，约 43,000 行/天。连续模式现只在 ACK、失败或死信时输出；操作员使用 `--once` 时仍输出空结果，便于确认目标库和消费者确实可用。

## 6. 验证

- Redis/事实面定向集成：11/11 通过；配置、readiness、worker 等定向集合 47/47 通过。
- 全量 `make check`：**1717 passed、70 skipped、1 个既有短测试 HMAC warning**；Ruff、441 个文件格式、mypy 189 个 source file、评测审计及 Schema 漂移全部通过。
- 评测审计的四项既有 warning 不变：2 个 unmappable gold、旧 safety replay、独立人工复核待完成、无未见 holdout。
- 本轮所有 smoke、清账和故障演练均为零模型调用，费用 0。

## 7. 尚未完成

- CACHE-10：按预先固定的重复比例，在真实 API 问题流量上比较命中率、完整问答 P50/P95、翻译/重排/模型调用、Token、费用和质量；需要新的付费授权。
- 缓存切换不修改既有问答时延门槛，也不把 1.14 ms 的纯缓存读取写成完整问答成绩。
- Redis 目前 `maxmemory=0`、策略 `noeviction`，本机开发数据量很小。正式受限环境部署前要按资源预算设置内存上限并监测拒绝写入；候选缓存故障会回源，但应避免由无限增长挤压宿主机。
