# AGENT-02：PV Agent 受控工具

日期：2026-10-15。实现及自审核：Codex，不是第二独立人工。依据[PLAN-02](PLAN-02-action-budget-and-acceptance.md)、[AGENT-01契约](AGENT_CONTRACTS.md)和[台账](../CURRENT_TASKS.md)；本轮证据见[记录207](../reviews/2026-10-15-implementation-207-agent-controlled-tools.md)。

## 1. 可以运行的内容

本轮提供四类内部工具适配器，以及基于现有ProductionRuntime资源的装配函数。没有注册新的HTTP/MCP入口，没有启动规划模型或改变现有演示链。

| 工具 | 实现 | 强制约束 |
| --- | --- | --- |
| extract_ae | 实际调用ae_extraction@1.0.0 Registry | 原合成叙述、PV:read、原60秒时限、原因果过滤、安全检查；逐字唯一quote才生成Unicode区间 |
| search_documents | 使用原检索port，沿用翻译/BM25/向量/重排/缓存装配 | 服务端固定文档ID、版本/PDF摘要、身份、日期；模型改写不能替换来源 |
| read_evidence | 重新查询原块及同文档前/后一个实际块，再经事实回查 | 先核验原句柄，邻块独立鉴权/状态/来源/区间校验；不跨文档、不接受任意路径 |
| verify_citations | 实际调用citation_verification@1.0.0 Registry及原Verifier | 只核验本次合法句柄；原文重新读取、注入筛查、语义判定及逐claim支持/未确认句柄分别返回 |

clarify/finish/escalate属于终态申请，交后续AGENT-05处理；工具适配器不会执行它们或直接写completed。所有注册项为服务端固定白名单，不开放任意Skill名、Python、Shell、浏览器或写策略。

## 2. 文件和职责

- [agent_tools.py](../../src/medops/application/agent_tools.py)：一次动作的准入、共享额度/期限、结果投影、句柄签发和错误归类；不实现循环。
- [skills/agent_adapter.py](../../src/medops/skills/agent_adapter.py)：位于Skills包内的两个原Registry Skill适配，保留原Prompt/Schema/重试和安全门。
- [agent_tool_results.py](../../src/medops/application/agent_tool_results.py)：封闭的payload、EvidenceView、事实快照及私有AgentToolOutcome；[Schema](../../schemas/agent/AgentToolOutcome.schema.json)。
- [agent_tool_ports.py](../../src/medops/application/agent_tool_ports.py)：类型化事实端口，无MCP/HTTP协议依赖。
- [agent_facts.py](../../src/medops/infrastructure/db/agent_facts.py)：普通应用角色的RLS/身份/来源/原文/邻块查询及0026最终栅栏。
- [bootstrap/agent.py](../../src/medops/bootstrap/agent.py)：装配一次动作，复用ProductionRuntime.build_deps、实际路由版本和现有资源，不另建检索栈。

AE字段词汇复用领域层[ae.py](../../src/medops/domain/ae.py)，原Skill字段/Prompt/Schema保持。没有application→具体Skill实现/MCP/bootstrap/evals依赖，也没有为了复用MCP服务复制其协议层；直接使用共用事实回查、Registry和检索能力。

## 3. 一次工具调用如何执行

1. 可信服务端先认证用户、建立获准AgentContext，持有本次根execution_scope、绝对截止和动作事务。
2. 用admit_action重新核验BoundAction、原run预算/步数、来源和句柄；适配器只能使用一次，非法参数/终态申请不会执行工具。
3. 当前共享额度与run快照必须一致，父额度不得高于12,000 Token/0.60 USD/125秒；没有父scope不启动。子工具取原时限与根剩余时限较小值，不能重开额度。
4. 查当前身份/部门/scopes及实际数据库绑定；输入安全通过后执行工具。每次模型物理调用和原重试前仍继承原持有权guard，并重新检查身份；需要指南的调用还复查来源。
5. 实际调用经同一个MeteredGateway，回执携带run/attempt和action片段；仅返回本动作的回执ID，失败和未知usage不清零。
6. 结果再经来源、当前事实及安全检查。最后获得0026输出栅栏并重新核对身份/事实；保留栅栏，等待调用者保存受限材料和结果、提交事务。

**每次动作使用独立、短期事务。** 调用者必须在下一次规划/工具调用前结束本动作事务，避免把输出栅栏持有跨越模型调用。适配器不自动commit、创建任务、重试整步或保存持久观察；这些编排分别归AGENT-03/04/06。

## 4. 事实库身份与权限

持久fact_plane_identity UUID按0025只允许admin/loop读取，principal目录也不对纯readonly角色开放。工具使用既有应用角色完成身份回查及事实读取，不增加任何GRANT/RLS例外。

可信启动/准备环节在同一允许读取的连接调用bind_fact_database，建立`FactDatabaseBinding`：持久事实库UUID加当前数据库连接身份摘要。只把这份元数据交工具，管理员DSN/连接不进入适配器。工具核对context的UUID与该绑定，并在实际应用连接上检查数据库名/OID/postmaster启动条件形成的原有database_identity摘要。

这能拒绝误接其他数据库和过期绑定；PostgreSQL重启后旧绑定失败关闭，需要可信环节重新核验。绑定是服务端配置，不是签名或认证凭据；模型/请求不能自行提供。正式保管环境如何加载、封存和防篡改属于后续部署/隔离验收。

## 5. 指定来源、改写与缓存

准备任务时，PgAgentFacts.resolve_scope仅查询调用者可见且在日期窗口内的文档，支持精确文档ID/标题及已有命名来源规则，随后检查版本、解析质量和来源文件完整性。唯一匹配才resolved；多个匹配返回ambiguous；未知、不可见或不符合条件统一denied_or_unavailable，不返回隐藏标题/部门/存在性。

运行时允许来源保存在服务端AgentContext中。新增内部RetrievalRequest.source_document_ids将这个范围传到全部原查询、翻译查询和聚焦通道；若已发布来源约束还解析出范围，则求交集，空交集停止，不扩大范围。候选和证据在缓存命中与未命中路径都作防御过滤，工具侧再次按真实来源版本/PDF摘要核验。

缓存沿用原CacheKeyInputs，把任务来源ID集合以`agent-source-scope-v1`命名的结构折入context_fingerprint；未指定这个新内部字段时，原缓存键保持原字节。同一query对不同文档的任务不会共享候选缓存。来源文档ID对应具体版本记录，PDF摘要在使用前后均检查；缓存不能跳过ACL、撤权、内容哈希或来源完整性验证。

这是Agent的显式任务约束，没有启用默认关闭的全局来源候选，也不修改已发布检索参数、BM25/翻译配置或旧质量成绩。

## 6. 有界投影与原文区间

搜索每次最多8份证据，给规划者每份最多500字符的摘录，明确truncated；完整Evidence留在服务端登记表。read_evidence返回一个完整块，最多8,000字符，超过则unsupported，不截断后假称原块完整。这个载荷上限不保证下一模型调用能放进剩余Token，调用前仍按真实渲染保守预留。

句柄绑定case/task/run/attempt及完整上下文摘要，期限不晚于原run；同一仍合法的事实优先复用句柄，不因换一个UUID制造进展。登记总量最多64。new_handles_issued只表示实际新句柄，完整“新合法信息/无进展”判断由AGENT-04结合历史结果完成。

AE quote只有在原叙述中逐字、唯一出现时才附char_start/char_end，区间左闭右开、按Unicode字符。归一化后匹配、重复出现或丢失原文的项目不猜位置，记录unaligned/缺失并返回未确认状态；不把指南内容填进患者叙述。严重性词仍只是原文提取，不新增法规判断或因果评估。

## 7. 引用核验结果的含义

引用工具返回每条claim的verdict、requested_handles、supporting_handles和unconfirmed_handles。每个来源必须属于该claim自己的句柄，不借用其他claim来源；来源、版本、页码、原文和PDF摘要由事实层再次检查。未知/撤权/被注入筛除的来源不能继续算支持。

沿用原Skill上限：一次最多20条、每条1,000字符。AGENT-01通用动作契约允许的更大输入会明确unsupported；不截断、不静默拆成更多付费调用。原Schema/模型不因此放宽。

这份结果不等于最终材料完整。共同必需/任选证据的业务要求、全部需求覆盖、数字/否定/条件、安全和合理停止还须由AGENT-05/EVAL-32接线判断；模型自报“核验通过”不能完成任务。这里复用原Verifier，不声明新的医学语义准确率。

## 8. 观察、审计与失败

AgentToolOutcome是私有执行信封：payload是之后可给规划者的有界投影；issued_handles只留服务端；call_receipt_ids关联真实动作调用。它没有持久result_ref，也不伪造AgentObservation。AGENT-06须先在输出栅栏保护下保存payload/审计、提交，再生成绑定结果引用的观察。

每个动作独立保留ExecutionAudit及共用MeteredGateway的实际调用记录。audit_snapshot可取得受限输入、Skill判定、证据和attempt；它不发送遥测、不等于加密持久化回执。规划者不能读取该快照，Langfuse继续只接版本/耗时等获准元数据。

权限/不存在使用统一响应；timeout、budget_exceeded、dependency_error、ambiguous和unsupported分别处理。故障不返回部分答案；原调用回执/未知usage仍保留。原节点/SDK重试照旧，没有新增工具重试层；retryable元数据不产生重试或费用授权。取消/失租的持久状态与恢复仍由根控制器后续实现，不把工具适配器当完整恢复机制。

## 9. 尚未交付与下一项

尚无规划循环、Agent公共接口、持久run/观察、完整回放、最终完成门、最小澄清续办或真实模型路径/质量结果。下一EVAL-32评分与开发用例，随后AGENT-03模型决策循环；AGENT-04/05/06及SESSION最小切片通过后，AGENT-07才做完整集成。真实托管模型试跑归AGENT-08逐次授权。

回滚本轮新适配器/Schema、来源字段与条件缓存指纹即可移除未接线能力；无数据库迁移、GRANT、默认策略或本机服务部署变更。测试命令、失败修复、保护范围及自审证据见记录207。

## 10. 后继循环接线

记录208已实现EVAL-32开发评分；记录209的[内部决策循环](AGENT_LOOP.md)按实际工具观察构造下一模型请求。本文记录207时点的历史范围保留；生产Driver/真实事务持久化和最终完成门尚未交付，不能把本轮fake Driver当正式实现。

## 11. 记录211：原工具共享最终核验保护

AgentTools在原根预算快照和profile匹配后安装Token/费用保护，AE/引用Skill及检索内翻译继续通过原Registry/检索链/计量网关。禁止子工具重开额度或消耗显式profile中的最终预留；拒绝/未知usage/取消的原回执保持，预算拒绝即使被翻译fallback捕获也不能成为成功工具结果。实际保护单独记录，不计成真实费用/待结算调用。

工具版本变为`pv-tools-v2+protected-headroom`，契约SHA绑定预算组件版本；旧摘要不能直接用于新循环。工具输出Schema、参数、来源/ACL/事实检查、Skill handler、规划SYSTEM和默认模型未变。实际核验profile数值推导、整项工具估计与最终阶段消费仍待后续；只使用已有合成配置核验机制，0托管调用/0USD。详见[循环预算保护](AGENT_LOOP.md#52-共享预算的最终核验预留记录211)。

## 12. 记录212：工具整项模型预算预检

四类工具在执行前生成服务端预算计划，AE和引用Skill按原最大3次attempt计算，搜索按一次原query翻译的cache-miss路径估计，读取为零模型调用。请求内容、Schema、输出上限与当前网关价目表共用真实执行逻辑；引用核验的免费分支不虚构模型调用。Token/费用估计必须连同原最终预留一起容纳，否则在第一个逻辑模型调用前返回budget_exceeded，无模型费用/回执。原逐调用reserve/settle及失败未知费用不变。

这是只读预检而非整项原子预留；并发/事实漂移/异常usage仍可让后续调用失败。保守估计可能拒绝实际能靠首试或缓存完成的任务，待获准真实试跑衡量完成率，不静默缩小安全空间。Agent搜索要求可信检索适配器提供预览，旧Ask仍按原端口工作。工具版本现为pv-tools-v3+whole-tool-preflight，具体公式、事实边界和剩余最终核验工作见[循环整项预算契约](AGENT_LOOP.md#53-工具开始前的整项估计记录212)。
