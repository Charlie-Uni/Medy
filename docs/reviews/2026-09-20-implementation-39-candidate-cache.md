# 实现记录 39：M1-19 检索候选缓存（权限/版本指纹键、命中仍回查、outbox 精确失效）

日期：2026-09-20。承接记录 38。本轮实现 M1-19：缓存键纳入身份权限指纹、会话上下文指纹、`as_of`/历史条件、复合 `retrieval_version` 与 `policy_version`；缓存只保存融合后的候选而非证据，命中路径仍在请求事务内执行 M1-18 事实回查；文档发布/归档/撤回经 outbox 消费者按部门精确失效。

## 1. 编码前记录

- 目标（基线 5.2"缓存键至少包含规范化查询、身份权限指纹、历史查询条件、检索/策略版本；文档发布通过 outbox 精确失效"；3.6"只有复合 `retrieval_version` 可进入缓存键"；威胁模型边界 B5；路线图 M1-19"测试撤权、归档、换版本后的缓存失效"；知识地图"缓存不得绕过授权、穿透/击穿/雪崩"）。
- 核心决定：**缓存值是候选不是事实**。命中后必须走 `recheck_candidates`（同一身份事务），因此撤权、归档、篡改在命中路径与未命中路径得到同样过滤；缓存只节省检索工作，不承担授权。`fetch_evidence` 是缓存通往 Evidence 的唯一函数，结构上保证这一点。
- 失效方案：**按部门纪元（epoch）**。键为 `rcache-v1:<dept>:<epoch>:<sha256(canonical_json(inputs))>`；发布事件对 payload 中 `acl_depts`（缺省 owner_dept）的每个部门 `INCR` 纪元，该部门全部条目立即失效，其他部门不受影响；旧条目靠带抖动的 TTL 过期。纪元自增在效果上幂等，与 outbox 至少一次投递相容。
- 存储：进程内存储（开发/测试与语义参考）与 Redis 存储（生产，`redis>=5.0,<7`，锁定 6.4.0，MIT）同一协议；任何存储故障以 `CacheStoreError` 冒出并由外观降级为未命中（计数并按异常类型记日志），不报错、不返回过期命中。
- 范围外：ACL 单独变更事件（目前没有发布后修改 ACL 的工具；撤权已由命中回查即时生效，新增授权在 TTL 内生效）；跨进程单飞（进程内按键单飞已做）。

## 2. 实现

- [cache.py](../../src/medops/retrieval/cache.py)：`permission_fingerprint(user)`（部门、角色、scope 排序哈希，不含 user_id，INV-OBS-02）、`context_fingerprint(entities)`（去重排序）、`CacheKeyInputs.build(...)`（norm-v1 规范化查询，空查询拒绝）、`cache_key(inputs, epoch)`、`CachedCandidates`（≤20 条、chunk_id 唯一、UTC 时间）、`CandidateCacheStore` 协议、`InMemoryCandidateCacheStore`（可注入时钟）、`CandidateCache`（`lookup`/`store`/`get_or_compute` 进程内按键单飞/`invalidate_dept`/TTL 抖动 ±10%/`degraded` 计数）、`fetch_evidence(conn, cache, inputs, compute)`。
- [cache_consumer.py](../../src/medops/retrieval/cache_consumer.py)：消费者 `retrieval-cache`；`departments_of(event)`；畸形 payload 抛错不跳过（事件留在 outbox 待重投）。
- [infrastructure/cache.py](../../src/medops/infrastructure/cache.py)：`RedisCandidateCacheStore`（命名空间、连接/读取超时 1s、`from_settings`、错误只带异常类型名）。
- 配置：`Settings.retrieval_cache_ttl_seconds`（默认 300，1..86400），`.env.example` 同步；CI 增加 Redis 7.2 服务与 `MEDOPS_TEST_REDIS_URL`；集成 conftest 新增 `redis_url` 夹具（无 Redis 时跳过并说明）。
- 依赖：`pyproject` 新增 `redis>=5.0,<7`；`make lock` 后 `requirements.lock` 仅新增 `redis==6.4.0` 与 `async-timeout==5.0.1`（8 行），其余版本不变。

## 3. 测试

- 单元 [test_cache.py](../../tests/unit/retrieval/test_cache.py)（24）：指纹与身份无关、与顺序无关；八个键成员逐一改变即换键、否则稳定；键布局含版本/部门/纪元；内存存储 TTL 与分部门纪元；未命中计算一次后命中；四线程并发未命中只计算一次；抖动落在 [270,330] 且不小于 1；部门失效只影响该部门；get/set/epoch 三种故障均降级为未命中且不抛错；损坏值与异版本值视为未命中、异版本写入拒绝；消费者只提升 payload 中部门的纪元、畸形事件拒绝。
- 集成 [test_cache_invalidation.py](../../tests/integration/test_cache_invalidation.py)（4，PostgreSQL + 候选 A + 内存存储）：**撤权**——命中后管理员删除 MA 的 ACL，下一次仍命中但回查全部 `not_visible`，证据为空；权限集变化即换键。**归档/换版本**——发布 v2 后消费者未运行时命中但回查全部 `status_not_active`；运行索引与缓存消费者后 MA 纪元提升、PV 纪元为 0，下一次未命中并只得到 v2 证据。**版本/日期**——`retrieval_version`、`policy_version`、`as_of` 任一变化即未命中。**身份隔离**——MA 计算的候选不会服务 CO；CO 在自身身份下计算得到空候选。
- 集成 [test_redis_cache_store.py](../../tests/integration/test_redis_cache_store.py)（5，真实 Redis，随机命名空间并清理）：TTL/纪元、命名空间隔离、经 Redis 的往返与失效、不可达服务器降级为未命中且错误文本不含地址、`from_settings` 不暴露 DSN。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**765 passed**（565 单元 + 200 集成）。

## 4. 自审（基线 §9）

1. 需求：键成员覆盖基线 5.2 全部要求并加入会话上下文与 `as_of`；发布经 outbox 失效；撤权/归档/换版本三类失效均有集成测试。
2. 逻辑：命中仍回查，授权不依赖失效时序；纪元按部门，精确到读者集合；`as_of` 进入键，跨日不会沿用前一日候选。
3. 安全：键不含 user_id 与原文；候选按部门与权限指纹隔离；Redis 错误不带 DSN；缓存故障不放宽任何过滤。
4. 契约：新增冻结模型；`Evidence`、`CandidateRef` 未改；`Settings` 新增带默认值字段。
5. 测试：新增 24 单元 + 9 集成；全量 765 passed。
6. 可观测：`degraded` 计数、命中布尔值由 `fetch_evidence` 返回供 Trace/指标（5.10"缓存命中"）。
7. 简洁性：一个外观、一个协议、两个存储、一个消费者。
8. 验证：数字来自 pytest 与 `git diff --stat requirements.lock`。
9. Checklist：M1-19 待做 → 已实现；**进度 27.8%（22/79），按 99 项计 22.2%**。

## 5. 下一步

M1-09 剩余项（DOCX、恶意文件扫描、多文档同源管理员确认）；M1-13 有界 Query Rewrite；M1-16 待 DEC-002；M1-14/15 待 DEC-001 最终判定。
