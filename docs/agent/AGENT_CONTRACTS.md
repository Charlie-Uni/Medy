# AGENT-01：首版 PV Agent 私有契约

日期：2026-10-15。实现与自审：Codex，不是第二独立人工。范围为[PLAN-02 v0.2](PLAN-02-action-budget-and-acceptance.md)的动作、状态、观察和停止边界；本轮记录见[206](../reviews/2026-10-15-implementation-206-agent-action-and-state-contracts.md)，执行顺序见[台账](../CURRENT_TASKS.md)。

## 1. 实际交付与接入边界

本轮提供可调用的纯校验函数、Pydantic 模型及三份确定性 JSON Schema。它们尚未注册到 HTTP/MCP，也没有连接规划模型、实际工具或数据库；不是完整 Agent。

- [agent_actions.py](../../src/medops/domain/agent_actions.py)：只接收规划者提出的动作参数。
- [agent_execution.py](../../src/medops/domain/agent_execution.py)：可信服务端维护的任务、状态、预算快照、证据句柄和结果元数据。
- [agent_contracts.py](../../src/medops/application/agent_contracts.py)：`admit_action`、`context_binding`、`validate_run_snapshot`、`validate_observation`。
- [schemas/agent](../../schemas/agent)：`PlannerProposal`、`PVAgentRun`、`AgentObservation`。已有 API/MCP/OpenAPI 合约保持兼容。

服务端必须先认证用户、加载受限任务与事实版本、核对持有权/取消/授权预算，再提供可信对象。公开或模型请求不可自己构造服务端上下文。摘要不是签名，UUID 不是访问凭据，终态回执引用不是实际核验成功的证明。

## 2. 规划者可以提交什么

统一外层格式：

```json
{
  "proposal": {
    "action": "search_documents",
    "rationale": "核对指定指南的缺失信息要求",
    "query": "minimum criteria and follow-up information"
  }
}
```

`rationale` 是最多500字符的简短可核对目的，不要求隐藏推理链。字符串必须含非空白字符。所有层级拒绝额外字段、未知动作及重复 JSON key；原始输入上限65,536 UTF-8字节，只是工程载荷限额，不修改12,000 Token总限额。解析错误只返回固定代码，不回显叙述或模型回复。

| 动作 | 允许参数（另有action/rationale） | 本轮验证 | 后续实际执行 |
| --- | --- | --- | --- |
| `extract_ae` | `narrative_ref="task_narrative"`、`source_type` | 必须匹配服务端的叙述类型，不允许模型另塞一份原文 | AGENT-02复用AE提取Skill、绑定原始叙述区间 |
| `search_documents` | 最多2,000字符`query` | 模型可改写查询，不可覆盖用户、ACL、指定来源、日期、模型或预算 | AGENT-02受约束检索/翻译/重排接线 |
| `read_evidence` | 当前运行句柄`handle`、`region=current/previous/next` | 校验句柄身份、版本、有效期和允许来源 | 相邻块须由工具再次查询、重新鉴权后签发新句柄 |
| `verify_citations` | 1～32条`claims` | 指南需求ID、每条1～8个不重复合法句柄 | 核验来源、引用语义、数字/否定/条件和共同必需证据 |
| `clarify` | 1～8项`field/question/reason` | 字段必须列在服务端`clarifiable_fields`，不重复 | 保存问题/审计，结束本次执行；最小续办另接SESSION |
| `finish` | `draft` | 结构、需求ID、原文精确区间、合法证据引用 | AGENT-05独立最终核验及原子保存后才可completed |
| `escalate` | 受限业务停止`reason`、`draft` | 同上；模型不能把系统故障自报为业务无答案 | 保存审核材料、缺口及业务升级原因 |

叙述类型为call_note/email/literature/other，首版上下文要求`synthetic`严格为true。七动作没有任意Python、shell、URL抓取、写策略、上报或医学建议工具。后续工具白名单仍须显式注册，不能让模型声明工具就产生执行权限。

`draft`必有三组：叙述事实、指南结论、缺失需求ID。叙述事实包括`requirement_id/value/quote/char_start/char_end`；区间按原始Unicode字符、左闭右开，不改空白、不按UTF-8字节或Token计。校验`narrative[start:end] == quote`且跨度等于引用长度；这只证明引文来自原文，**不证明value被引文语义支持**。指南结论包括需求ID、文本和句柄；不允许用叙述事实冒充指南证据。完整性、冲突、因果或安全判断由后续最终门处理，不能靠模型标记“缺失”就算正确停止。

## 3. 服务端上下文与证据绑定

`AgentContext`保留：case/task/run/attempt/Trace身份、既有`UserContext`、`QueryContext`、合成叙述、来源范围、需求、可澄清字段、实际版本摘要及profile。复用现有身份/日期/证据模型，没有复制旧Ask `AgentState`或改变其含义。

`context_binding`对完整规范化上下文计算SHA-256，再与四个UUID组成绑定。叙述、用户权限快照、日期/历史模式、允许文档版本、需求、规划Prompt/工具合约/最终核验策略/rubric、事实库与条件摘要或profile变化，原绑定随即不匹配。应用入口重新验证嵌套实例，不能用Pydantic `model_copy`绕过类型校验。

证据登记表最多64项，每个句柄保存绑定、官方来源文件摘要、既有`Evidence`和绝对过期时间。使用前校验：

1. 句柄存在且无重复，属于当前case/task/run/attempt及相同条件。
2. 尚未过期；citation的文档ID、版本与来源PDF摘要在服务端允许清单。
3. 生效日期不晚于请求日期；历史证据只用于显式历史请求。
4. 草稿和核验动作只引用本任务的指南类需求；叙述区间精确匹配原文。

这是结构和快照准入，**不是实时授权**。AGENT-02仍须用真实用户访问数据库并检查当前ACL、撤权、归档、指定来源解析及相邻块，重查正文/内容哈希与实际事实。模型看不到完整登记表，不能自行签发或借用句柄。条件摘要来自可信装配内容，并不自行检查文件是否实际加载、索引是否完备或事实库是否漂移。

## 4. 六种运行状态与停止契约

| 状态 | 结构要求 | 语义 |
| --- | --- | --- |
| `running` | 无stopped_at/terminal | 可尝试下一步；计数和授权由控制器维护 |
| `awaiting_clarification` | clarification_required终态、材料/审计引用 | 当前执行已结束，等待显式关联新执行，不是暂停续期 |
| `completed` | completed原因、最终verification_ref、材料/审计引用；期限内、无未结预留、未超限 | 只能由可信最终门写入；仅构造DTO不能证明真实完成 |
| `escalated` | insufficient_evidence/source_ambiguous/version_conflict/unsupported_requirement/safety_boundary/no_progress/step_limit | 业务缺口或合理停止，不能算业务完成 |
| `failed` | dependency_error/budget_exceeded/timeout/lease_lost/audit_failure/unsupported_recovery | 系统失败；不能包装成正确拒答 |
| `cancelled` | cancelled原因 | 已取消，后续不得继续发起动作 |

所有非running快照须有匹配状态的终态、停止时间及材料/审计UUID和摘要，四身份必须一致；应用入口另核对完整条件摘要。失败快照允许保留超额的真实usage，不能把用量裁到上限掩盖超支。旧TaskStatus/数据库枚举未修改，API映射和真实持久化归AGENT-06。

JSON Schema表达状态与负载配对、终态原因、完成核验引用、来源解析与清单非空配对、观察结果配对和可重试范围；日期先后、原文字段区间、身份/条件相等、总预算及实时事实需服务端Pydantic/应用/执行门核验。不得把单独的JSON Schema valid当业务通过。

## 5. 预算和决策步

批准profile固定为：最多8决策步、12,000 Token、600,000微美元即0.60 USD、125,000毫秒、相同无进展最多2次。Token、微美元和毫秒是严格整数，布尔值不作为数字接受；时间必须带时区，统一UTC。截止时间严格为开始时间加125秒，不能通过恢复延长。

最终核验预留Token及费用是**必须显式提供**的工程输入，未给正式默认数值；测试中的1,000 Token/50,000微美元仅公开合成夹具，不能当用户批准的分配策略。准入扣除已结用量与未结预留；不足时拒绝，非终态工具不得侵占最终预留。终态申请可消耗预留，但实际调用前仍须由共享预算器作最坏用量预留。

`admit_action`读取**本次尝试之前**的`decisions_consumed`，合法结果绑定序号prior+1，函数本身不修改状态。AGENT-03必须在规划/失败/非法动作及终态申请时也消耗决策步，防止解析失败无限重试。重复检测、稳定结果指纹、新合法信息判断、租约/取消/幂等/恢复及共享费用预留归AGENT-03/04；本轮不声称已执行这些机制。检查预算快照不构成调用费用授权，所有付费运行仍须逐次审批。

澄清续办保留case，生成关联新task/run；旧终态、原支出/未结预留和批次上限不重置。业务TTL、续办次数和授权尚未配置时不能启动付费续办。此处只定义身份和终态所需材料，不提供完整SESSION。

## 6. 观察结果、错误和遥测

`AgentObservation`包含action_id、同条件绑定、动作名、受限结果引用/摘要、句柄UUID、是否新增合法信息、可重试标志和调用回执ID；没有正文/原始异常/自由文本错误字段。kind为ok、empty、ambiguous、unsupported、denied_or_unavailable、invalid_action、dependency_error、budget_exceeded、timeout、cancelled、lease_lost。

ok必须有成对结果引用/摘要。非ok不能发新证据句柄或自报新增合法信息；只有dependency_error可设置retryable，仍不自动授权重试。`validate_observation`检查动作ID/绑定/动作名一致；它不验证签发者、数据库结果是否存在或新句柄是否确实登记，后续适配器须完成这些操作。

固定准入错误代码：invalid_agent_payload、invalid_agent_metadata、agent_payload_limit、agent_binding_mismatch、agent_handle_unavailable、agent_not_running、agent_deadline、agent_step_limit、agent_budget_exhausted、agent_final_reserve。输入中的拒权/不存在统一处理，不能泄露其他用户文档。私有上下文/动作的叙述和引文不直接送Langfuse；AGENT-06须使用现有受限正文审计与元数据遥测边界。

## 7. 后续接线与复现

下一AGENT-02接真实只读检索、AE提取、原文/相邻块及引用工具；再做EVAL-32固定开发评分、AGENT-03模型决策循环、AGENT-04预算/停止/恢复、AGENT-05最终核验、AGENT-06追溯、SESSION最小澄清及AGENT-07无付费集成。真实模型质量/路径收益归AGENT-08单次授权，真实盲测仍须独立保管验收。

复现契约：`python -m medops.contracts_export --check`，新测试在`tests/unit/domain/test_pv_agent_contracts.py`、`tests/unit/application/test_agent_contracts.py`和`tests/unit/core/test_strict_json.py`。完整命令/结果和环境条件见记录206。回滚本轮契约及新增Schema即可移除未接线能力，无数据库迁移、策略切换或部署变更。
