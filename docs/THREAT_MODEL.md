# 数据流与最小威胁模型（M0-09，v0.1，2026-09-10）

> 范围：基线第 4 节架构与 P0 主链路。本文只登记信任边界、七类风险的防护点与对应测试；不引入新组件，不替代基线不变量。状态列以仓库实物为准：已有 = 有代码与测试；规划 = 对应里程碑条目。

## 1. 数据流与信任边界

```text
[外部 Agent / 客户端]
        │ OIDC bearer token（边界 B1：身份）
        ▼
[API / 只读 MCP]  ── 解析身份、限流、Idempotency-Key、错误模型
        │ AgentState（边界 B2：应用内部，只有可序列化状态）
        ▼
[Harness: Intent → Retrieve → Evidence Verify → Safety → Answer/Escalate]
        │ 检索候选 / 证据（边界 B3：数据库权限，RLS 内过滤）
        ▼
[PostgreSQL 事实平面 + pgvector] ←── 入库流水线（边界 B4：文件与 PII 校验，来源哈希）
        │
[Redis 缓存/队列]（边界 B5：缓存键含权限与版本指纹）
        │
[Trace / 审计存储]（边界 B6：追加写、脱敏、受限 payload 单独授权）
        │
[Loop 进程]（边界 B7：只能写 candidate，无 released 写权限）
        │
[外部模型 / Reranker]（边界 B8：数据出境策略 DEC-009，超时与预算）
```

信任假设：token 由服务端验证后的身份可信；文档内容永远不可信（只作数据）；模型输出永远不可信（必须经证据核验与安全检查）；Loop 产物不可信直到人工签字发布。

## 2. 七类风险与防护点

| 风险 | 攻击面 | 防护点（基线条款） | 测试与状态 |
| --- | --- | --- | --- |
| 身份伪造 | 伪造或篡改 token；请求参数直接声明 dept/scopes | INV-AUTH-01/04：服务端校验 issuer、audience、expiry、signature；scope 由服务端映射；MCP 不接受参数声明身份 | 规划 M3-05/06；`UserContext` 目前只是数据契约，不能保证由服务端构造，该约束由 M3 鉴权层强制 |
| 越权访问 | 跨部门读取文档、候选或元数据；应用层先取后滤 | INV-AUTH-02、3.7：ACL/状态/生效时间在数据库查询与 RLS 内完成；候选不足显式标记；Registry 校验 scope | 数据库层已实现（迁移 0002，实现记录 18）：三组角色、FORCE RLS、按 `document_acl` 与部门的策略、无身份默认拒绝、草稿不可见；`tests/integration/test_rls.py` 证明零跨部门泄漏、LIMIT/排序不丢可见行、连接池身份切换、只读角色无写路径、管理角色不能改 schema 或策略；API 层把 token 部门注入 `SET LOCAL medops.dept` 的接线在 M3；候选不足标记随 M1-04 实验；Registry 校验 M2-11；`UserContext.has_scopes` 默认拒绝（已有） |
| 提示词注入 | 用户输入与检索文档携带指令；文档内容改变权限范围 | INV-HAR-07、5.5 三层 Safety：用户输入与文档分别标记为数据；权限只来自数据库；Hook/Skill 产物不进入指令优先级 | 规划 M2-09/15；契约层高风险意图不可作答（已有 D-03） |
| 数据泄漏 | 日志与 Trace 含身份、密钥、原文；错误响应回传内部细节；.env 入库 | INV-OBS-02/03：surrogate/HMAC 假名、脱敏、受限 payload 授权；错误模型 detail 不外泄；密钥不入仓库 | 已有：`core/logging` 脱敏与边界、`core/errors` 公开响应无 detail、`Settings` SecretStr、`test_repo_hygiene`；规划 M3-07 |
| 策略篡改 | Loop 或调用方直接改 released 策略；未经门禁的候选生效 | INV-HAR-05/06、INV-AUTH-05：策略版本化，生产只读 released，Loop 角色无 released 写权限，发布需回放、门禁、签字、灰度 | 规划 M4-03/04/08/09；`VersionSet` 与 `operation_key` 工具已有，运行时强制携带全部版本尚未接线（M2-03） |
| 审计绕过 | 审计写失败时仍作答；Trace 缺节点输入；回放复用旧缓存 | INV-OBS-01、5.10、3.2：审计失败为 `audit_unavailable` 安全失败；每节点输入快照；回放使用独立 run_id | 已有：`ErrorCode.audit_unavailable` 错误码与 `operation_key` 含 run_id；审计失败时禁止作答的执行门禁与回放隔离尚未实现（M2-03、M3-07/08/13） |
| DoS | 大请求、深层 JSON、重复任务、无限重试、日志放大 | 5.12 请求大小与频率限制；INV-HAR-04 超时与并发上限；INV-HAR-08 Token 预算；幂等键去重；日志有界处理 | 已有：`redact` 深度/大小/长度上限、`TokenBudget`、`AgentState` 候选与证据上限；规划 M3-02/12 |

## 3. 已知未覆盖项

- OIDC、限流、MCP 传输未实现；RLS 已在数据库层实现并有集成测试（迁移 0002），但请求到 `SET LOCAL medops.dept` 的注入尚未接线，本表对应行在 API 层仍只有契约层防护。
- 外部模型数据出境策略取决于 DEC-009；在此之前不得向外部模型发送真实语料。
- 对象存储（DEC-007）未选型，入库流水线的不可变存储边界（B4）未落地。

## 4. 维护规则

新增组件或外部调用时，先在第 1 节补边界、第 2 节补行，再写代码；每行必须指向具体测试或里程碑编号，不允许只写“已考虑”。
