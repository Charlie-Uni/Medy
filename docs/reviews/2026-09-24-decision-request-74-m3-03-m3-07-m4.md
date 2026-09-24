# 记录 74：待批事项与建议——管理接口契约（M3-03）、受限载荷加密存储（M3-07）、M4 规划

- 日期：2026-09-24
- 性质：决策请求（M0-08 契约流程 / 基线 3.5 保留期决策 / M4 排期）。决策人答复后写回本记录并转入 ADR 与契约文档。
- 已有约束：INV-AUTH-05（Loop 只能写 candidate，无 released 写权限）、INV-HAR-06（生产只读 released）、INV-OBS-03（受限 payload 分开存储、加密、授权）、基线 3.5（上线前完成保留期决策）、4.2（`policies/policy_releases`）、5.7（管理接口与 replay 接口）、CONTRACTS.md 第 14–15 行的占位。

## A. M3-03 管理接口契约

### 需要批准的内容

1. **文档管理接口 = 状态与权限管理，不含 HTTP 上传。** 入库（AV 扫描、PII、许可证准入、抽取质量复核）仍走 M1-11 的离线流程与工具；接口只操作已入库文档。
2. 路由与角色（管理角色 `admin`）：
   - `GET /admin/documents`（按 dept / status / family 过滤，只返回元数据，不返回正文）；`GET /admin/documents/{doc_id}`（元数据 + ACL + 最近审计）。
   - `PATCH /admin/documents/{doc_id}/status`，body `{action: activate | archive | withdraw, effective_from?, reason}`：复用 `activate_document` / `publish_version`（同事务归档旧版、写 `doc_audit`、outbox 事件、缓存失效）；非法转换 `409 status_conflict`；`reason` 必填。
   - `PATCH /admin/documents/{doc_id}/acl`，body `{grant: [dept], revoke: [dept], reason}`：写 `document_acl` + 审计 + 缓存 epoch（补 M1-19 登记的"ACL 单独变更事件"）。
3. 策略候选与审批（新增角色 `approver`，写入 `principals.roles`）：
   - 迁移 0014：`policies`（policy_id、kind ∈ prompt | rule | skill | retrieval_params、version、diff jsonb、status ∈ candidate | approved | rejected | released | rolled_back、created_by、evidence 引用）与 `policy_releases`（签字人、时间、灰度比例、回滚记录）。
   - `GET /admin/policies/candidates`、`GET /admin/policies/{id}`（含回放 / 门禁报告）：`approver` 或 `admin`。
   - `POST /admin/policies/{id}/approve`，body `{decision: approve | reject, reason}`：`approver`，且不得是候选作者（四眼）。
   - `POST /admin/policies/{id}/release`，body `{canary_percent ≤ 10}`：`admin`，前提 status = approved 且门禁报告达标（M3 先做服务端校验框架，门禁计算随 M4-07/08 落地）；`POST /admin/policies/{id}/rollback`：`admin`，原子切换 released 指针。
   - Loop 的数据库角色只能 insert candidate（INV-AUTH-05），用权限测试证明。
4. 横切语义：所有 POST/PATCH 支持 `Idempotency-Key`（同任务接口作用域）、`X-Trace-Id`、审计追加写、错误码沿用 `ErrorResponse`。

### 建议与理由

- 上传不进 HTTP：文件安全与许可证准入是人工步骤，放进 API 会把最危险的入口暴露给最弱的校验；离线流程已经过 M1 验证。
- 先落契约与状态机、后落门禁计算：契约稳定能让 M4 的 Reflect/Adapt 直接对接，而门禁阈值本身是 M4-08 的事。
- `approver` 单独成角色而不是复用 `admin`：签字与发布分开是基线"人工签字"的最小实现。

## B. M3-07 受限可回放载荷的加密存储

### 需要决定的内容

1. **加密方案**：应用层信封加密——每条 payload 随机 DEK（AES-256-GCM），DEK 由 KEK 包裹；KEK 经 `KeyProvider` 接口提供，v1 实现为部署注入的本地密钥文件（不在 `.env`，权限 0600，带版本号），KMS / Vault 适配器随部署对象再定（与 DEC-010 同一推迟逻辑）。轮换 = 用新 KEK 重包裹 DEK，不重加密 payload。
2. **存什么**：节点输入（原问题、改写查询、会话实体）、Evidence 快照（chunk id、文本哈希与文本）、模型原始输出。普通 `traces` 只保留现有摘要。
3. **存哪里、谁能读**：新表 `trace_payloads`（trace_id、node、kind、ciphertext、nonce、dek_wrapped、kek_version、expires_at）+ 独立数据库角色 `medops_restricted`（只对该表有权）；读取只经 `GET /admin/traces/{id}/payload`，要求 `admin` 角色 + 必填 `purpose`，每次读取写 `payload_access_log`。
4. **保留期**（基线 3.5 要求上线前定）：普通请求 90 天；升级案的 payload 保留到升级关闭后 30 天；删除 = 删行 + 丢弃 DEK（密码学粉碎）；每日清理任务。

### 建议与理由

- 不用 pgcrypto 列级加密：密钥会经过 SQL 语句、数据库进程与可能的日志。
- 不用"只靠角色隔离"：违反 INV-OBS-03。
- 90 / 30 天是可回放性与最小保留的折中；可回放集（M4-06）需要的样本在冻结时另行导出为脱敏副本，不依赖受限存储的保留期。

## C. M4 规划与排期

### 需要决定的内容

1. **回放集来源**：M4-06 要求 ≥ 200 条独立 good / bad 历史 Trace。目前没有真实用户流量，建议首版回放集从主集 v2 全量运行（614 条，有 gold 标注可判 good / bad）与安全集（170 条）导出并冻结为 `replay-v1`，如实标注"运行导出而非真实流量"，真实流量到来后换版。
2. **每个候选的评测预算**：M4-07 要求 3 次独立运行 + 配对 bootstrap。全量主集 3 次约 14 美元 + 安全集 3 次约 2 美元，一个候选约 16 美元；建议候选评测用冻结的 200 条回放子集（3 次约 5 美元），只有拟发布的候选才跑全量。请确认每候选预算上限（建议 5 美元，发布前一次 16 美元）。
3. **顺序**（M3 收尾之后）：
   - M4-A：M4-01 + M4-06——信号关联与回放集冻结（无模型费用）。
   - M4-B：M4-02 / 03 / 05——Reflect 归因（复用 reason code 与检索上限复查的分类）、Adapt 只产 diff 候选（意图规则 v3、支持规则 v3 这类改动就是候选的样子）、knowledge_gap 只建补文档工单。
   - M4-C：M4-04——Loop 数据库角色与权限测试。
   - M4-D：M4-07 / 08——三次运行、CI、门禁（+5pp / 非目标 ≤ 1pp / 安全不降，安全取三次最差）。
   - M4-E：M4-09 / 10——签字、灰度 ≤ 10%、原子回滚与演练（依赖 A 部分的接口）。
4. **M3 收尾清单**（M4 之前）：M3-03 接口（A）、M3-07 受限存储（B）、M3-11 性能门禁（约 1–2 美元）、M3-13 进程级故障演练（约 0.1 美元）。

### 建议与理由

- 先接口后 Loop：M4-09/10 的发布与回滚必须落在 A 部分的状态机上，否则 Loop 无处可发布。
- 用运行导出的回放集起步：等真实流量会让 M4 无法开工；冻结、哈希与"不进入候选生成上下文"的隔离规则同样适用。
- 预算分级：候选筛选用子集、发布用全量，是在 30 美元/月上限内跑通一轮闭环的唯一办法。

## 决策人答复

（待填写：A 1–4、B 1–4、C 1–4 逐项同意 / 修改）
