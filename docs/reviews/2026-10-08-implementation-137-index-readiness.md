# 记录 137：真实索引就绪与 outbox 积压

日期：2026-10-08。阶段 2 / OPT-15 的工程交付；阶段 1 等待独立模型预算期间推进不依赖新分数的工作。本轮自审通过，阶段 1 和阶段 2 均未宣告完整通过。

## 修改及原因

旧 `/readyz` 仅执行 `SELECT 1`。记录 109 的缺索引事故表明，数据库连通无法证明文档可检索。本轮增加只读全局检查：active 文档/块、无块 active 文档、词法缺行或空向量、生产版本的 embedding 覆盖、分词和 embedding 元数据，以及应用连接与检查连接是否确实指向同一数据库。

- `retrieval/integrity.py` 通过全局可见角色检查和 REPEATABLE READ 快照读取；普通 RLS 身份不能将空结果解释为完整。
- API 将健康结果缓存最多 5 秒，连接超时 2 秒、每条 SQL 超时 1 秒；检查失败、未配置管理员检查连接或模型线程 stalled 均未就绪。`/readyz` 在 FastAPI 线程池执行，避免同步数据库访问阻塞事件循环。
- `make retrieval-check` 为运维提供同一只读检查；旧 `check-indexes` 保留原覆盖诊断用途。检查不会重建索引或修改 `.env`。
- `/metrics` 在既有 ops/admin 认证后输出聚合覆盖、就绪和消费者积压；不输出库地址、DSN、文档、正文或数据库指纹。检查失败时缺失的覆盖数保持未知，不能编成 0。
- outbox 分别按 `lexical-index` 与 `retrieval-cache` 的 ACK 计数，忽略 `published_at` 的完成暗示。历史积压与实际索引完整性分别报告，积压不单独阻断就绪。新增运维告警规则并更新 DEPLOY/RUNBOOK；没有假设 Prometheus 已部署。

边界：这里核查 active 语料，历史归档的可检索性仍由对应检索/历史评测覆盖。监测具有最多 5 秒状态滞后，不能替代请求路径的 ACL/状态/版本核对。每条 SQL 的超时不是整次检查的绝对总时限。检查当前借用管理连接只读执行，专门监控角色仍可进一步最小化权限。

## 真实核查

见[数据库结果](2026-10-08-implementation-137-live-index-health.json)。以下为一次只读观察：

| 数据库 | active 文档 / 块 | 缺词法 / 缺向量 | 就绪 | 两类消费者各自 pending |
| --- | ---: | ---: | --- | ---: |
| medops（旧库） | 15 / 2628 | 0 / 2628 | false，向量元数据也缺失 | 231 |
| medops_v2（正式语料） | 333 / 34948 | 0 / 0 | true | 338 |
| medops_v2_safety | 339 / 35273 | 0 / 0 | true | 339 |

本机 Settings 默认指向旧库，正式评测脚本会显式切换数据库。新检查把这一差异暴露出来，没有替用户静默修改连接。三个库的检查分别约 0.050 / 0.130 / 0.171 秒，仅为此次观察，不是并发性能成绩。正式库最旧未 ACK 事件约 17 天，尚未在本轮消费。

实际 `ProductionRuntime.from_settings` 使用离线缓存的 MPS embedding/reranker 启动约 10.988 秒；通过 ASGI HTTP 客户端验证 `/healthz=200`、`/readyz=200`、未认证 `/metrics=401`，切换应用连接到旧库后 `/readyz=503`，恢复后 `200`。见[运行时结果](2026-10-08-implementation-137-runtime-check.json)。这是本地真实运行时和数据库检查，未启动外部 HTTP 监听服务，未请求生成模型。

## 失败与补救

1. 两个新增测试首次因 fixture 缺 effective_from、读取用户映射层级错误失败；按真实 Schema 和 fixture 修正。
2. 全量首次结果 1445 passed、70 skipped、35 errors。原文错误：`UniqueViolation: duplicate key value violates unique constraint "source_objects_source_hash_key"`。记录 136 后补的 4 个 RLS 测试从另一模块导入 module 级 seed，导致同一 session 测试库重复插入固定 source_hash；单独运行无法暴露。将测试放回既有 RLS 模块共享同一 fixture 后修复。生产代码和业务库没有因此写入重复数据。
3. 修复后 `env -u DEBUG make check`：**1480 passed、70 skipped、1 warning，38.71 秒**；格式、177 个源文件类型检查、评测输入和 Schema 检查通过。70 个跳过仍为 B/C 专用实验服务器不可达，唯一警告仍为错误 JWT 算法测试的短 HMAC fixture。

## 五项自审

| 项 | 结论 | 依据 |
| --- | --- | --- |
| 需求与范围 | 通过 | 补运行真实性；不改检索排序、模型或业务质量阈值 |
| 正确性/失败路径 | 通过 | 真实空库/缺索引/空词法/版本错/空文档及连接错配测试 |
| 权限/追溯 | 通过 | 全局角色边界、只读一致性快照、聚合指标；业务库无写入 |
| 验证 | 通过 | 17 项针对测试、全量复测、真实三库和实际运行时验证 |
| 状态/文档 | 通过 | 明确阶段未完成、积压未处理、监控规则尚无部署证据 |

下一步是消费恢复闭环和更严格的正式评测预检。不能因 ready=true 将积压当作已清理，也不能因本輪自审通过将第一阶段评测证据缺口关闭。
