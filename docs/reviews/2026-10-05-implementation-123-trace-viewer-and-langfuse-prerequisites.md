# 实现记录 123：调用链查看——OTLP 认证头、GenAI 属性、Jaeger 单容器；Langfuse 自建前须决定的三件事

日期：2026-10-05。决策人对「Langfuse 要不要自建」等三项答复「可以 全部添加」。本记录完成应用侧与最轻的查看器；Langfuse 整套容器没有拉取——动手前查到三个需要决策人过目的事实（§3）。没有模型调用，没有下载镜像，费用 0。

## 1. 应用侧（已完成）

- 设置 `OTEL_EXPORTER_OTLP_HEADERS`（`Key=Value[,…]`，按密钥处理、不进日志）：自建的追踪后端通常要认证头，此前导出器无法携带。API、worker、MCP 三个进程都传给导出器。
- 模型调用的 span 增加 OpenTelemetry GenAI 约定的属性：`gen_ai.operation.name`、`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`。追踪查看器（Jaeger、Langfuse 等）按这些名字识别模型与用量。原有属性不变。
- **内容仍不进 span**：提示词、证据、问题、回答都不写入任何属性（基线 INV-OBS-03「Telemetry 默认脱敏」）。新增测试断言这一点。

## 2. 查看器：Jaeger（compose 的 `observability` profile）

`make observability-up` 启动一个 Jaeger 容器（Apache-2.0，内存存储，只绑 127.0.0.1）；在 `.env` 里设 `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` 并重启 API 后，浏览器打开 `http://127.0.0.1:16686` 可以看到每次请求的调用树：HTTP 请求 → 五个节点 → 检索 / 重排 / 模型调用，各自的耗时、模型、token、费用、策略与检索版本、是否命中缓存。它不留存数据，适合演示和排查，不是审计存储（审计仍以数据库的 Trace 表为准）。镜像标签 `jaegertracing/jaeger:2.4.0` 只核对了清单存在，未拉取；首次启动会下载（数十 MB）。

## 3. Langfuse 自建：动手前查到的三个事实

| # | 事实 | 影响 | 需要的决定 |
| --- | --- | --- | --- |
| 1 | 基线 INV-OBS-03 规定遥测默认脱敏，现有 span 不含提示词与回答 | Langfuse 的主要价值（看提示词、对比回答、打分）用不上；按现状接进去只能看到调用树、耗时、token、费用——与 Jaeger 相同 | 是否修改这条不变量，允许在自建后端里保存内容；这是基线变更 |
| 2 | Langfuse 官方自建栈的对象存储是 MinIO，其许可证为 AGPL-3.0 | 与修订 4 排除 ParadeDB 的理由同类；主 compose 里「对象存储等 DEC-007」本来就悬着 | 接受 MinIO（仅内部使用）/ 换成其他 S3 兼容存储（需验证可用）/ 不建 |
| 3 | 官方栈用 `redis:7`（7.4 起为 RSALv2 / SSPLv1），而本项目 2026-09-17 已决定只用 7.2（BSD） | 须钉回 7.2 并验证 Langfuse 可用 | 无（实现方会钉版本），但要知情 |

另外两点代价：整套是 2 个应用容器 + ClickHouse + 对象存储 + Redis + PostgreSQL，下载约 1–1.5 GB，在已经跑着数据库和两个本地模型的这台笔记本上内存吃紧；官方镜像默认向 Langfuse 回传使用统计，须显式关闭（`TELEMETRY_ENABLED=false`）。

实现方建议：先用 Jaeger。它覆盖了「现在能看到什么」的全部——在不改 INV-OBS-03 的前提下，Langfuse 不会多显示任何东西。若决策人决定放开内容并接受对象存储的许可证，再建 Langfuse；应用侧已经就绪（端点 + 认证头），届时只是部署。

## 4. 改动清单

| 文件 | 改动 |
| --- | --- |
| `src/medops/core/config.py`、`.env.example` | `OTEL_EXPORTER_OTLP_HEADERS` |
| `src/medops/core/telemetry.py` | `parse_headers`；导出器带认证头 |
| `src/medops/{api,worker,mcp}/serve.py` | 传入认证头 |
| `src/medops/infrastructure/llm/meter.py` | 模型调用 span 的 `gen_ai.*` 属性 |
| `docker-compose.yml`、`Makefile` | `jaeger` 服务（profile `observability`）、`make observability-up` / `observability-down` |
| `tests/unit/core/test_telemetry.py` | GenAI 属性存在且无内容；认证头解析与传递 |

## 5. §9 自审

- 没有违反 INV-OBS-03；新增属性都是结构信息，并有测试防止内容进入 span。
- 没有擅自引入 AGPL 组件或 7.4 以上的 Redis，也没有在未告知的情况下下载上 GB 的镜像。
- Jaeger 服务未启动、未拉取；`docker compose config` 校验通过。
- 「全部添加」里 Langfuse 一项没有照字面完成，原因与所需决定写在 §3。
