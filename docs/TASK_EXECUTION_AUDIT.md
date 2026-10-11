# Ask / 异步 Skill 执行审计

更新：2026-10-11。对应 ARCH-06、OPT-09、INV-OBS-01/03。实现和自审见[记录 180](reviews/2026-10-11-implementation-180-task-execution-audit.md)。这是工程审计契约，不是新 Agent 或真实医学质量的验收结论。

## 1. 修复的问题

原 TaskRunner 的 Trace 固定写入三个空列表：evidence、cited、flagged；节点只有外层 Skill。内部 Harness 虽然核验了来源，最终任务也可能返回引用，统一 Trace 无法定位这些来源。Task 没有调用受限载荷 writer，最终结构化候选和比较核验材料也无法从统一审计读取。

现在 Ask 与 Task 复用 `ExecutionAuditWriter`，Task 通过每次执行独有的 `ExecutionAudit` 汇总内层事实。原回归测试先失败于 `() != ('c1',)`，再通过真实 Skill → TaskRunner 路径核验修复。

## 2. 保存责任

| 层 | 责任 | 正文边界 |
| --- | --- | --- |
| SkillRegistry | 创建或绑定一次执行的 journal；记录外层成功、重试和失败；返回独立审计快照；批量子任务隔离 journal | journal 仅在进程内短暂保存，不输出遥测 |
| Harness nodes / runtime | 每个节点在 operation 持久化前留下尝试和可用证据；结束后记录实际 query、历史上下文、候选、证据、回答、核验和安全状态 | 中途失败保留已观测前缀，不伪造完整运行 |
| structured helpers | 记录实际结构化输入、schema、候选回复、截断标记；记录最终业务比较输入和四项核验结果 | 全部进入受限材料；错误元数据只有类型和错误码 |
| citation_verification | 记录身份范围内重读且安全筛查后的证据、被筛掉的 ID、逐条核验结果 | 无权限/未知 ID 不能晋升成 evidence；不保存被注入片段的正文 |
| TaskRunner | 固定历史上下文，验证最终输出的完整 Citation 与已观测证据一致；区分技术完成、业务结果和 lost；构造 Trace、升级摘要及三种载荷 | 普通 Trace 只保存 ID、版本、耗时、用量、错误码等；正文进加密载荷 |
| ExecutionAuditWriter | Ask / Task 共用失败关闭入口；Trace、升级和已配置的载荷在调用方事务中写入 | 存储、加密或密钥失败统一为 audit_unavailable；没有重跑业务/模型的逻辑 |
| PostgreSQL / PayloadReader | 同一事务提交；载荷应用角色只能插入，restricted 角色读取；HTTP 管理入口核验 admin 和用途，解密前留访问日志；沿用保留、轮换及销毁规则 | 普通 admin 数据库角色不能直接读 ciphertext；不能把底层 Reader 当作独立授权入口 |

逐调用费用回执仍由 [ARCH-04 会计契约](LLM_ACCOUNTING.md)负责。journal 与写入器不会新增供应商调用、费用预留或调用重试。业务核验规则见[最终判断契约](SKILL_JUDGMENT_VERIFICATION.md)。

## 3. Trace 与结果的一致性

- `evidence_chunk_ids` 是本次尝试真正观测的合法证据并集；可包含早期重试使用过的来源。
- `cited_chunk_ids` 来自最终已接受的类型化业务输出，包括 `.citations` 或逐项核验 `.sources`。每个 Citation 的文档、版本、生效日、页、节和 chunk ID 必须全部等于观测证据；只对上 ID 不足以通过。引用无匹配时失败关闭。
- 核验失败后仍保留的正确条款引用也会如实登记；被清除的错误业务比较不会被当作最终引用。
- lost 或写入失败的尝试不声称有被接受的最终引用，`cited_chunk_ids` 为空；加密材料保留候选，并明确标记 attempt_outcome。
- 注入片段只登记 flagged ID；无权限/未知 ID 可在调用者提交的原始输入里出现，但不能进入合法 evidence 清单。
- `Task.status=completed` 仅指作业执行结束；业务状态取 `Task.result.status`，Trace 随业务状态。`escalated` 建立升级记录；`insufficient_evidence` 保留独立业务状态，不自动冒充完成或新建人工工单。
- 执行前身份失效、上下文无法创建的失败也有 Trace：版本为 `{}`、query_context 为 null、调用数为零。它表示未完成上下文解析，不能猜测版本并用于精确回放。

## 4. 节点、重试与失败

保留 intent / retrieve / verify / safety / answer / escalate 的实际 NodeAttempt，以及 `skill:<name>` 外层执行。结构化阶段独立命名为 `skill:<name>:generate`，最终比较为 `skill:verify_judgment`，直接引用核验为 `skill:verify_citation`。后两类记录是对已有调用的计时观察，不开启新执行、重试、预算或期限。

数据库唯一键是 `(trace_id, node, attempt)`。外层重试再次调用 Harness 时，内层本地序号会重新从 1 开始，因此写入 Trace 前按实际起始时间为每类节点分配连续序号。原始本地序号、operation key、尝试详情继续保存在加密 events。结构化计时观察的 key 是输入与事件序号的摘要；它不是供应商费用回执的 call_id 或 attempt_id，逐调用关联继续读取费用回执。

内层 operation 写入失败时，节点观测前缀仍可在回滚后的失败报告中保存。未执行的后续节点没有记录；没有以完整成功事件补齐失败日志。旧 worker lost 后只记录自己的尝试，不覆盖或返回新 worker 的结果。

journal 不得被第二次 Registry 执行复用；Harness 在开始检索前检查 Trace/身份绑定。`execute_many` 每个子任务使用独立 journal，历史日期和共享总预算保持原规则。

## 5. 加密载荷格式与读取

沿用三个 kind 和现有 0024 数据库结构，无新迁移。Task 全部材料汇总在 `node="task"`，避免重试违反 `(trace_id,node,kind)` 唯一键。每种 Task 载荷含 `format_version="task-audit-v1"`。

| kind | Task 内容 |
| --- | --- |
| input | Skill 标签、原始 Skill input、实际历史上下文、版本、任务尝试号、各次 Harness 的输入 |
| evidence_snapshot | 合法证据正文、完整 Citation、证据文本和原 chunk 哈希、历史/状态标记、flagged ID、各次候选快照 |
| model_output | 最终 Skill 输出、失败错误、技术尝试状态、最终安全检查，以及内层 Harness、结构化候选、比较核验、直接引用核验和原始尝试 events |

Ask 保留 `node="ask"` 与三个 kind；原字段保留，证据额外包含完整 Evidence 字段，model_output 额外保存 safety_result。没有改变 HTTP 回答、TaskResult 或已冻结评测 schema。

已配置 payload key 时，API 与 worker 均通过 ProductionRuntime.payload_writer 创建同事务的 writer。通过现有 `/admin/traces/{trace_id}/payload?purpose=...` 读取，沿用 admin、用途、访问记录、默认 90 天及未关闭升级保护规则。Key 轮换和销毁继续使用既有工具。

现有无 key 的开发配置仍允许只写元数据，不悄悄改变部署策略；`audit.persist` 遥测记录 `restricted_payload_enabled` 布尔值。此配置下没有可解密正文，不能声称能精确重现业务执行。旧空 Trace 没有回填或虚构快照。

## 6. 容量与故障

journal 最多 512 个事件、序列化事件合计 16 MiB；这是 journal 限制，不是整个数据库载荷大小或生产吞吐承诺。保存时复制 JSON，避免调用者后续修改材料。达到上限后锁定失败状态，不悄悄截断后继续返回正常业务结果；失败诊断可以保留已保存的有界前缀。

Trace、密钥或载荷写入失败会回滚同事务的 TaskResult。新事务仅报告错误并保存已有执行事实，模型不因此重跑。若失败报告也无法持久化，worker 返回 audit_unavailable，任务保持尚未提交完成的租约状态；依原规则后续回收。此时不承诺已有最终 Trace。费用回执是独立账本，不能因为业务回滚而删除已产生的费用事实。

## 7. 已验证与下一步

工程验证覆盖五类生产 Skill 的正常路径、撤权、无证据、不安全候选、最终比较失败、二阶段超时、注入/未知来源、完整引用错配、并行隔离、容量、operation 写入故障及 lost。真实 PostgreSQL 验证重试序号、密文读取/访问日志，以及 Trace / seal / 部分载荷写入故障的原子回滚和持续失败恢复边界。命令、失败与结果见记录 180。

没有托管模型调用；脚本化判词只验证接线和失败关闭，不证明真实医学语义正确。性能与存储开销尚未经过真实流量测量。

**后续 ARCH-07 更新**：完整逐模型请求/实际 SDK 参数与回复/最终回执、裁剪正文/哈希/来源区间、完整执行输入和内容条件摘要已接线，诊断与原条件模式的边界见[执行记录与回放契约](EXECUTION_REPLAY.md)和[记录 181](reviews/2026-10-11-implementation-181-execution-records-and-replay-boundaries.md)。原版本加载、不可变事实/索引恢复仍未交付，原条件模式明确拒绝；Replay 仍拒绝 Task/MCP。保存材料不等于已经开放 Task 回放。S2 Agent 和 S3 自进化仍未交付，付费校准须逐次授权。
