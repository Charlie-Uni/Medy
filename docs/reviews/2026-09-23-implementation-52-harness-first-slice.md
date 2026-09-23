# 实现记录 52：M2 首切片——固定状态机、节点契约、规则版 Verifier/Safety、Model Gateway 与预算

- 日期：2026-09-23
- 范围：决策人 2026-09-23 指示"先开始不需要我决定就可以跑的东西"。本切片只做不依赖 API key 与未决决策（DEC-003）的部分：M2-01 图结构与无绕过边证明、M2-02 节点契约、M2-04/05 Answer 只收已验证证据与引用结构核验、M2-06 预算、M2-07 要素抽取、M2-08 确定性支持规则、M2-09 三层 Safety 规则、M2-10 稳定升级记录；以及 ADR-0010 的 Model Gateway 契约、OpenAI 适配器（桩测试）与月度上限账本。
- 依据：基线 2.4（INV-HAR-01～08）、3.2、3.3、5.3～5.5、§8 M2 清单；[ADR-0010](../adr/ADR-0010-llm-provider-and-data-boundary.md)。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 引入 `langgraph`（1.2.12）与 `openai`（2.54.0）依赖，`make lock` 重新生成三份哈希锁；现有 pin 无一变更，新增 34 个包（含 langchain-core、langsmith、httpx） | 基线 5.3 指定 LangGraph；ADR-0010 指定 OpenAI SDK；锁文件对比见 §5 |
| LangSmith/LangChain 外部追踪一律拒绝：检测到 `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` / API key 环境变量即中止建图 | ADR-0010 §3 数据边界：证据文本不得流向第三方 |
| 节点超时用工作线程实现，超时即放弃等待并按可重试处理；asyncio 取消传播随 M3 执行器 | INV-HAR-04 要求超时必达；同步 M1 检索栈（psycopg）下线程是最小可验证实现 |
| 安全三层按数据流放置：输入检查在 Intent 节点、检索内容检查在 Retrieve 节点、输出检查在 Answer 节点；Safety 节点是 Answer 前的决策点 | 基线 5.3 的节点顺序与 5.5 的三层叠加同时成立；证据在 Verify 之后不再变更，避免下游结果失效 |
| 证据阶段的 Verify 只做结构与要素覆盖，不因"问题前提与证据矛盾"升级；矛盾升级只针对生成后的陈述 | 基线 5.4 第 4 条针对答案的关键矛盾；问题前提错误应由答案指出 |
| Intent 为规则版 `intent-rules-v1`：高风险检测限定第一人称的个体用药/诊断/处方/急症；`unclear` 直接升级（一次反问属会话层，M3） | INV-SAF-01；法规文本中的 emergency 等词不得误判 |
| 未确定的要素支持先走容器包含与词元重叠（阈值 0.6，临时值），再走 LLM 判定；未配置判定模型时记 not_supported 并丢弃该陈述 | 基线 5.4 第 5 条"数字规则优先"；DEC-003 决定判定臂 |

## 2. 交付

### 2.1 Model Gateway（`src/medops/infrastructure/llm/`）

- `gateway.py`：`ModelRequest`（purpose、pinned model_id、messages、max_output_tokens、temperature=0、json_schema、timeout_s）、`ModelResponse`（usage、cost_usd、provider、model_id、response_id、system_fingerprint、truncated）、`ModelGateway` Protocol；错误类型 `ModelTimeout` / `ModelUnavailable`（沿用统一错误模型的 `dependency_timeout` / `dependency_unavailable`）、`ModelOutputInvalid`、`BudgetExceeded`；`PriceTable`（ADR-0010 价目，未登记模型拒绝调用）与本地 token 估算。
- `budget.py`：`InMemorySpendLedger` + `BudgetedGateway`：按月累计，调用前以最坏情况预检，超上限拒绝并升级，不降级。
- `openai_gateway.py`：注入式客户端，`chat.completions` + strict json_schema，`max_retries=0`（重试归节点策略），超时/限流/连接错误/4xx 分类映射，截断的结构化输出判无效；`from_settings` 读取 `OPENAI_API_KEY`。
- `fake.py`：按 purpose 编排的离线假网关，用于全部单元测试。

### 2.2 Verification（`src/medops/verification/`）

- `elements.py`（M2-07，`elements-rules-v1`）：剂量（含单位换算 mg/g/mcg/mL/L/IU/%/mg/kg/mg/m²、区间、千分位与小数逗号）、频次（一天三次、每 8 小時一次、bid/tid/q8h/every 12 hours/once weekly）、时间窗（天/小時/週/月、calendar/working days）、编号（21 CFR、ICH E 系列、GVP Module、Article、Section、第 x 節、NCT、EudraCT、Rev、衛署藥字號、SOP）、人群 11 类、适应证；重叠按固定优先级消解（`一天三次` 不是一天时间窗）。
- `rules.py`（M2-08，`support-rules-v1`）：同值同极性→supported；同值反极性（不得/禁用/not/unless…）→contradicted；同族唯一异值→contradicted；编号缺席→not_supported；其余未定，交上层。
- `verifier.py`：`structural_check`（引用必须逐字段等于本 Trace 证据）、`verify_evidence`（生成前）、`verify_claims`（生成后：规则→包含→重叠→LLM 判定，`ElementKind.statement` 用于无要素陈述）；LLM 判定臂通过 Gateway、JSON schema、purpose=`verify`。

### 2.3 Safety（`src/medops/safety/checks.py`，`safety-rules-v1`）

输入层注入模式（中英文指令覆盖、系统提示泄露、部门/权限切换、角色标记）→ `prompt_injection` 拒答；检索内容层剔除含指令的证据片段并记录 id；输出层拦截"您应该服用…/you should take…"类个体建议 → `high_risk_medical`；`decide` 为 Safety 节点决策矩阵（高风险升级、无证据按是否被剔除分别给 `insufficient_evidence` / `prompt_injection`）。

### 2.4 Harness（`src/medops/harness/`）

- `graph.py`：LangGraph 六节点固定图 `intent → retrieve → verify → safety → answer | escalate`，每个阶段只能前进或进入 `escalate`；`graph_edges` / `simple_paths` 供测试枚举。
- `contracts.py`：`NodeSpec`、`NodeAttempt`（含 operation key）、`run_node`（超时线程、可重试基础设施错误指数退避最多 2 次、业务错误与未知异常不重试、最终失败抛 `NodeFailure` 带全部 attempt）。
- `nodes.py`：节点体与 `HarnessDeps`；Retrieve 节点按 Trace 预算裁剪证据（不足一条即 `budget_exceeded`），降级检索低于阈值即升级；Answer 节点：JSON schema 生成 → 丢弃引用未知 chunk 的陈述 → `verify_claims` → 矛盾升级、not_supported 陈述删除后重验 → 输出安全检查 → 模型用量计入预算；任何节点最终失败都转为带 `system_failure` / `budget_exceeded` 的升级。
- `intent.py`：规则分类器；`retrieval_port.py`：`RetrievalPort` 协议与 `ProductionRetrieval`（有界改写 → 混合检索 → 回查 → 重排，身份事务由调用方提供）；`runtime.py`：`initial_state`、`run_ask`。

### 2.5 配置与依赖

`Settings.openai_api_key` / `llm_monthly_budget_usd`（记录 51 已加）；`pyproject.toml` 新增两依赖；三份锁文件重生成。

## 3. 测试与门禁

- 新增 61 条单元测试：`tests/unit/harness/`（图无绕过边 3、节点策略 5、意图 3 组参数化、端到端运行 10）、`tests/unit/verification/`（要素 6、规则 7、核验器 5）、`tests/unit/safety/`（5）、`tests/unit/infrastructure/test_llm_gateway.py`（6）。
- 关键证据：`test_every_path_to_answer_passes_retrieve_verify_safety_in_order` 枚举编译图的全部简单路径；`test_answer_has_a_single_predecessor_and_every_stage_can_escalate`；`test_high_risk_and_injected_queries_never_reach_retrieval`（检索与模型零调用）；`test_forged_citation_is_dropped_and_an_all_forged_answer_escalates`；`test_model_timeouts_are_retried_twice_then_escalate_as_system_failure`；`test_budget_exceeded_from_the_gateway_and_from_evidence_trimming`；`test_historical_evidence_requires_the_flag_and_sets_the_notice`（无显式请求时状态模型拒绝历史证据，节点 fail-closed）。
- `env -u DEBUG -u PYTHONPATH make check`：ruff、mypy（95 源文件）、**960 passed**、schema 漂移检查通过（`ElementKind.statement` 不在导出 API schema 内）。

## 4. 边界与未做

- 没有真实模型调用：OpenAI 适配器只有桩测试，`from_settings` 在 key 到位后做一次 smoke；DEC-003 未决，判定臂默认关闭（`judge_model_id=None`），此时无要素陈述若与证据重叠不足会被丢弃。
- M2-03 未做：operation key 已计算并随 attempt 记录，但没有持久化、唯一约束与 replay_run_id 隔离。
- M2-11～16 未做：无 Skill Registry、无安全集、无门禁数据。
- 规则覆盖率未量化：要素抽取与安全模式只有单元样例，尚未在主集 614 条或安全集上跑覆盖统计；DEC-003 数据构造是下一步。
- Intent 的一次反问、Escalation 持久化与人工接手在 M3。

## 5. 依赖变更证据

`requirements.lock` 与 `requirements-embed.lock` 由 `make lock` 重生成；对比结果：新增 34 个包，既有 pin 0 变更、0 移除。新增中的 `langsmith`、`requests`、`httpx` 属 langchain-core 传递依赖；运行时不会被调用（追踪被 `_refuse_external_tracing` 拒绝，且未配置任何 key）。

## 6. 自审（§9）

1. 需求：对照 §8 M2 清单逐项标注（记录于路线图与知识对照），未把"函数存在"记为完成（M2-03 明确待做）。
2. 逻辑：Answer 的每条路径都经过 `AgentState._answer_gate`（领域）与图结构（运行时）双重约束；升级从不携带证据以外的 chunk id。
3. 安全：证据以数据块进入提示并声明"不是指令"；外部追踪禁止；key 只经 `Settings`，不进日志。
4. 测试：960 passed；无跳过；反向测试覆盖伪造引用、注入、高风险、预算、超时、历史证据。
5. 进度：M2 5/16（M2-01 已实现，8 项部分）；P0 加权 **39.9%**（31.5/79），按 99 项 31.8%。

## 7. 下一步

1. DEC-003 数据：从 `main-v1-provisional` 与端到端运行构造约 2,000 对带切片标签的支持/不支持判断题；Claude 臂走订阅 CLI（零花费），OpenAI/Gemini 臂等 key。
2. key 到位后：OpenAI 适配器 smoke、Answer 模型 `gpt-6-sol` 在主集 20 条上的冒烟运行与费用记录。
3. M2-03 持久化（迁移：`traces/trace_spans/node_attempts/escalations` 的最小子集）与 M2-11 Registry。
