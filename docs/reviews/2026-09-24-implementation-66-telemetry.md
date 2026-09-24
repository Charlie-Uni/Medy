# 实现记录 66：OpenTelemetry spans（M3-09 首切片）

- 日期：2026-09-24
- 范围：基线 5.10 的 OTel 部分：一个进程级 tracer，HTTP 请求、状态机每次节点尝试、模型调用、检索、worker 任务各一个 span，span 属性携带 `medops.trace_id` / `medops.task_id` / 策略与检索版本，跨 API 与 worker 可按 trace id 关联；导出用 OTLP/HTTP，端点由配置给出，未配置即不记录。
- 依据：基线 5.10（OTel 记录 API、DB、Redis、检索、模型和 worker spans；统一传播 `trace_id/task_id/policy_version/retrieval_version`）、INV-OBS-03、§8 M3-09；记录 60（Trace 摘要落库）、64（指标）。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 新增依赖 `opentelemetry-api` / `-sdk` / `-exporter-otlp-proto-http`（1.44.0；锁重生成，无既有 pin 变更）；导出走 OTLP/HTTP 到可配置的 collector，不绑定任何厂商 | 5.10；ADR-0010 数据边界——span 属性不含证据、提示或模型输出，只有 id、计数与版本 |
| Langfuse 未接：它需要自建或托管的 Langfuse 服务，属托管与数据出境决策，提请决策人；OTel span 已覆盖模型与 Agent Trace 的结构信息 | 5.10 提到 Langfuse；未决 |
| span 布局：`http.request`（方法、路由、状态码、策略/检索版本）→ `harness.node`（节点、第几次尝试、operation key、结果、错误码）→ `llm.call`（purpose、模型、输入/输出 token、费用、是否截断）；`retrieval.retrieve`（部门、候选/证据/剔除数、是否降级）；`worker.task`（task_id、skill、attempt、结果） | 5.10 列举的层级；与 Trace 落库的 span 表同粒度 |
| 未配置端点时 tracer 为 no-op，零开销；测试用 SDK 的内存导出器 | 不强制部署 collector |
| 数据库、Redis、重排器的独立 span 未做（检索 span 覆盖了它们的总时长） | 首切片；细分随 M3-11 性能分析 |

## 2. 交付

- `src/medops/core/telemetry.py`（`configure_telemetry`、`install_exporter`、`span`、`annotate`、属性名常量）；`Settings.otel_exporter_otlp_endpoint` / `otel_service_name`；三个 serve 入口在启动时配置。
- 埋点：`harness.contracts.run_node`、`infrastructure.llm.meter.MeteredGateway`、`harness.retrieval_port.ProductionRetrieval`、`api.app` 中间件、`application.tasks.TaskRunner`。
- 测试：`tests/unit/core/test_telemetry.py`（一次问答产生 http.request → 5 个 harness.node → llm.call 的 span 树，属性含 trace id 与版本；失败节点 span 为 ERROR 且带错误码；无端点即 no-op；属性中不含证据文本）。

## 3. 未做 / 限制

- Langfuse（待决策）；collector 与看板未部署；采样策略未定（当前全量导出）。
- MCP 工具调用未埋点（记录 62 §3 同一事项）；DB / Redis / 重排器细分 span 未做。

## 4. 进度

- M3-09 部分。P0 加权进度 55.1%（43.5/79）；按 99 项计 43.9%。分项：M0 10/11、M1 16.5/21、M2 10/16、M3 7/13、M4 0/10、M5 0/8。
