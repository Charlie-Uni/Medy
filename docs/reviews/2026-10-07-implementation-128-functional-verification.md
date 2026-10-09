# 记录 128 整理后的功能复核

日期：2026-10-07，Australia/Sydney。范围：Git `cb83abd` 加工作区记录 126、127 的代码整理。用户要求：“确认改动后各功能正常”。本轮验证当前工作区，未追加业务代码修改。

## 1. 结论

在本轮自动化回归和实际启动检查覆盖范围内，未发现代码整理引入的功能回归。全量门禁通过，真实 API 能启动并连接现有语料库。外部模型回答质量和容量指标本次未重测，不能据此宣布项目全部业务门禁达标。

原始分项结果见[机器可读检查清单](2026-10-07-implementation-128-verification-results.json)。

## 2. 全量质量门禁

命令：

```sh
env -u DEBUG PYTEST_ADDOPTS='-rs --junitxml=/tmp/medy-verification-2026-10-07.xml' make check
```

- 包外导入：通过。
- Ruff lint：通过；376 个文件格式检查通过。
- mypy：168 个源文件通过。
- pytest：**1337 passed、70 skipped、1 warning**，其中单元测试 1083 项、集成测试 254 项通过。
- Schema：`schemas up to date`。
- `git diff --check`：通过。

验证进程移除宿主 `DEBUG`，沿用记录 126 的处理，不修改 `.env`。唯一警告仍来自拒绝错误 JWT 算法的测试使用短 HMAC fixture；没有新增生产认证警告。

## 3. 功能覆盖

以下是单元测试分组，通过数互不重叠。集成测试另列。

| 功能组 | 通过数 | 实际验证范围 |
| --- | ---: | --- |
| API | 90 | 问答响应、身份认证、任务/反馈/管理/回放/指标/受限 payload 路由、错误契约、OpenAPI |
| 应用层 | 21 | 任务幂等、worker 执行与租约、已发布策略加载和路由 |
| Harness | 91 | 固定图、回答核验、预算、重试、历史证据、聚焦配置与缓存复查 |
| Skill | 59 | 注册、输入校验、权限、证据、失败关闭和风险边界 |
| 检索 | 188 | 规范化、分词、词法/向量边界、融合、重排、改写、翻译、版本与缓存 |
| 安全与核验 | 46 | 安全检查 18 项、引用/数值/支持度核验 28 项 |
| 故障恢复 | 5 | 模型超时、供应商不可用、worker 中断、重复消费、审计故障 |
| Loop | 68 | 观察、归因、候选、工单、门禁及受控流程 |
| MCP | 14 | 契约、服务入口与工具行为 |
| 评测工具 | 333 | 数据校验、映射、评分、版本、续跑、历史日期、标注与统计 |
| 文件摄取 | 39 | 文件检查、PDF/DOCX 抽取、切分、杀毒服务边界 |
| 基础设施 | 11 | 模型网关、预算/计量生命周期及数据库用户工具 |
| 配置/核心/领域/文档 | 118 | 配置 10、核心 61、领域 37、文档一致性 10 |

API/Harness/Skill 的回答路径使用可控模型 stub，验证调用、引用、状态和失败行为。它们不测真实供应商的回答质量。

### 真实数据库与 Redis 集成

254 项集成测试实际运行，覆盖临时 PostgreSQL 数据库的迁移、摄取、激活/归档/撤回、RLS、审计、词法/向量检索、任务、策略、Loop、MCP、outbox 与 Redis。测试库按 fixture 创建并清理，业务语料库不用于写入测试数据。

关键子集：

| 子集 | 通过数 |
| --- | ---: |
| 生产词法 A2 | 22 |
| 实验词法 D | 22 |
| PostgreSQL RLS | 37 |
| pgvector 检索 | 16 |
| Redis 存储/纪元失效/故障回源 | 5 |

以上五组属于 254 项集成测试的子集，不能重复相加到总数。

### 70 项跳过的确切原因

- 候选 B / zhparser：45 项，`candidate B: server unreachable (OperationalError)`。
- 候选 C / pg_search：25 项，`candidate C: server unreachable (OperationalError)`。

这两组是专用实验服务器不可达。生产 A2、实验 D、主 PostgreSQL 与 Redis 测试均已实际执行；跳过项不计为通过。

## 4. 真实 API 启动与 HTTP 检查

另外启动了临时 `python -m medops.api.serve` 进程，监听随机 localhost 端口，使用 MPS 和离线缓存中的实际 embedding/reranker 模型。它走的是当前 `ProductionRuntime.from_settings` 与真实应用工厂。

为限定检查范围，使用临时合成 OIDC 公钥和无效的测试模型 API key；不创建 principal、不提交问答任务、不调用模型供应商。真实 API key 与环境文件保持原样。遥测出口仅在这个临时进程中关闭。

启动前只读核查 `medops_v2`：**333 份 active 文档、34,948 个 active chunks、1 条 released policy，词法与向量索引覆盖完整**。实际 API 在本次启动约 16.2 秒后就绪；这是一次启动观察，不作为容量或冷启动性能成绩。

| HTTP 检查 | 结果 |
| --- | --- |
| `GET /healthz` | 200，`status=ok` |
| `GET /readyz` | 200，`status=ok` |
| 无令牌 `POST /v1/ask`，合法请求体 | 401，`unauthenticated` |
| `POST /v1/ask`，缺少 query | 422，`schema_violation` |
| 无令牌读取任务 | 401，`unauthenticated` |
| 无令牌读取 `/metrics` | 401，`unauthenticated` |
| 无令牌读取受限 trace payload | 401，`unauthenticated` |

七项响应均携带 `X-Trace-Id`。临时 API 进程已停止，无遗留监听服务。这证明实际启动、连接和上述 HTTP 边界正常；授权回答、任务成功执行等行为由上面的自动化测试覆盖，未在业务库执行新的真实请求。

## 5. 结论适用范围

- 当前改动的回归检查通过，可继续开展局部开发。
- 记录 127 的 8 个 CLI 帮助输出、156 组统计等价对照、3 组签名等价对照仍适用；本轮未再次改动其实现。
- 原有点名来源缺陷、安全集正式重跑、P95 和成本门禁沿用既有记录，不能由本轮回归结果改记为已解决。
- 若需要确认外部模型、正式语料问答质量和并发容量，需另做绑定数据/策略/模型版本的真实运行，并记录费用；本轮未产生模型 API 费用。
- 改动与检查记录保留在工作区，未提交或推送。
