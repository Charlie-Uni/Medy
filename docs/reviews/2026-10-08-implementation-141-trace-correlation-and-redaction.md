# 记录 141：可关联的遥测与异常脱敏

日期：2026-10-08。OPT-09。本轮是 Langfuse 应用接线基础；后端部署、评分回写和真实界面排障仍待完成。

## 目标与发现

请求的业务 trace_id 原本仅作为 OTel 属性，OTel 自己生成另一个随机 ID；把反馈里的业务 ID 直接交给 Langfuse score 接口，会关联不到相同 trace。MCP 虽为审计生成 ID，却未绑定到遥测上下文。离线 harness 没有统一父 span，并行 Skill 的外层线程也没有复制调用上下文。

另一个问题涉及脱敏：项目只检查 span 属性不含正文，而 OpenTelemetry 的上下文管理器默认会将异常消息和堆栈写入 exception event，并可能把原始异常消息写入 status。正文即使不在属性中，也可能随异常进入遥测。

## 实施

- 安装自定义 OTel ID generator：新根 span 使用服务端生成的 32 位业务 ID；不接受客户端 X-Trace-Id 作为身份。全零 ID 不能成为 W3C ID，SDK 在该边界回退到随机值；生产 UUID 不会产生这个边界。
- `run_ask` 增加 `harness.run` 父 span 并绑定 state 的 trace ID。API 下仍挂在 HTTP 父级；离线执行形成一条完整 trace。重放若使用新业务 ID，则建立新根并通过 OTel Link 关联外层请求，不混用两个 ID。
- Skill 执行绑定实际 context 版本；`execute_many` 为各个线程复制独立上下文。MCP 绑定它实际写入审计的 ID。
- 实际运行的 policy/retrieval/model/skill 版本传到子 span，更新同 trace 的 HTTP/worker 父 span，防止父级仍显示启动时版本。采用进程内 ContextVar，未启用向下游 HTTP 传播的 baggage。
- 增加 Langfuse generation/retriever/tool/chain 类型、版本筛选字段，以及 `gen_ai.usage.cost`。模型、tokens 已有字段保留。
- 关闭 SDK 自动 exception event 和自动异常 status；仅记录异常类型。被节点捕获的失败也标 ERROR。HTTP route 改用匹配后的路由模板，未知路径仅记 `/<unmatched>`，不把任意 URL 路径内容导出。API 意外异常日志改为类型，避免原始堆栈携带输入。

仍不导出 query、提示、证据、回答、人工纠正文案或身份明文。核心 PostgreSQL 审计的失败关闭行为保持。平台不可用不会替代数据库审计。

## 接口依据与技术选择

沿用已有 OTel/HTTP protobuf 导出器，减少新的自动采集路径和 SDK 依赖；Langfuse 提供 OTLP 接口及模型用量、费用和观测类型字段映射。当前官方文档的 v4 接收路径为 `/api/public/otel/v1/traces`，认证使用 Basic header，可用 `x-langfuse-ingestion-version=4`。接线文档以[官方 OTel 集成说明](https://langfuse.com/integrations/native/opentelemetry)为依据（2026-10-08 查询）；这不等于已验证某个部署版本的全部 UI 行为。

## 验证与错误修复

新增 11 项测试覆盖：业务 ID/费用映射、实际灰度版本、ValueError/KeyboardInterrupt 的异常正文与堆栈均不导出、新 replay 根与 parent Link、离线 harness、并行 Skill、未知 URL/伪造客户端 ID、被捕获节点失败、MCP 审计关联和实际 OTLP HTTP protobuf 传输。

完整检查在前 10 项测试加入后通过：**1549 passed、70 skipped、1 warning，37.01 秒**；181 个源文件类型检查、411 个文件格式、Schema/评测输入检查通过。随后加入的 HTTP 导出测试及该文件全部 11 项另行通过。接收端是本机临时 HTTP fixture，捕获并解析了真实导出器发出的 protobuf、路径及测试认证头；它不是 Langfuse 服务器。

初次 MCP 测试错误使用了旧 SDK `_mcp_server` 属性，修正为当前仓库已用的 helper/API；初次 Ruff 拒绝可变 ContextVar 默认字典，改成 None，初始化时复制。没有修改依赖锁。

## 五项自审

| 项 | 结论 | 依据 |
| --- | --- | --- |
| 范围 | 通过 | 仅观测、上下文与错误脱敏；未改检索策略或评分门槛 |
| 正确性/失败 | 通过 | 分离 trace 的 parent Link、线程继承、异常重抛与错误状态均有回归 |
| 权限/追溯 | 通过 | 服务端 ID、版本白名单、无正文/客户端路径；没有新远程发送目标 |
| 验证 | 通过 | 全量及实际本机 HTTP/protobuf fixture；模型 API 调用 0 |
| 状态/文档 | 通过 | 明确未启动 Langfuse、未完成 score/UI 验收 |

## 仍缺什么

版本/ID 对齐适用于新产生的 trace，不回填或改写旧审计记录。运行环境若额外安装第三方自动 instrumentation，必须单独审计其属性和异常采集；本次只保证项目的显式 span 包装路径。

还需持久、幂等的反馈和评测 score 同步、部署及访问控制、后端查询验证。主机 Docker VM 约 7.75 GiB、磁盘剩余约 25 GiB；Langfuse 自建资源及对象存储选择需要具体部署方案确认。第二人工与模型复核仍 pending，阶段 1/3 均未宣告通过。
