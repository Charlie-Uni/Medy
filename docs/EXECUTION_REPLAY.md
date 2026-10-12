# 执行记录与回放边界

更新：2026-10-12。ARCH-07 的实现与八项自审见[记录 181](reviews/2026-10-11-implementation-181-execution-records-and-replay-boundaries.md)；CODE-07的MCP受限材料见[记录194](reviews/2026-10-12-implementation-194-mcp-audit-and-observability.md)。本页规定在线执行记录和单条 Ask 诊断回放，不替代正式评测、独立人工复核或 Agent 轨迹验收。

## 1. 两种模式

| 模式 | 当前行为 | 保留与变化 |
| --- | --- | --- |
| `diagnostic_current` | 默认；重新执行 Ask，写独立 Trace 与差异报告 | 保留原日期、显式历史模式；新版受限材料还恢复完整 AskRequest、初始 session entities、Token 上限和递归上限。重新解析原用户的当前身份，并应用当前路由策略、当前事实和索引。产生新的模型调用、费用、Trace/run/call ID |
| `original_conditions` | **尚未开放；409 `version_conflict`，模型准入前拒绝** | 本部署没有可恢复的不可变语料/词法与向量索引工件、经验证的原运行镜像和旧配置加载器。不会把当前事实、缓存结果或旧模型输出代作原条件 |

诊断回放不创建人工升级工单，不复用原运行的 operation key。原用户撤销、部门变化、缺失历史输入、非 Ask 来源均在模型执行前拒绝。Task/MCP 的诊断与原条件执行入口仍未开放；Task 保存的材料已丰富，但不能因此宣称具备 Task 回放。

请求示例：`{"reason":"核查证据来源差异","mode":"diagnostic_current"}`。省略 mode 保持旧调用方式。接口仍要求管理员；托管模型费用仍需要本轮明确授权，接口本身没有替代人工付费授权的机制。

旧 Trace 没有 QueryContext 时拒绝，不能从今天日期猜测原输入。有日期元数据但没有完整受限输入的旧 Trace，或材料已经清理的 Trace，可以进行原问题的诊断重查；报告必须标 `input_complete=false`，输入/身份相等性为 null。加密材料损坏、完整输入与原 Trace 不符、未知载荷版本、调用记录缺字段或哈希/回执身份不符，则拒绝后续模型调用。配置了受限写入但解密依赖不可用时失败关闭，不静默绕过依赖。

## 2. 保存什么

正文仍使用 DEC-013 的 envelope encryption、受限读角色、管理员用途与访问日志、90 天默认保留和升级工单宽限期。原有 `input / evidence_snapshot / model_output` 三类结构保留；Ask 新记录使用 `ask-audit-v2`，Task 继续使用可增量读取的 `task-audit-v1`。

MCP现使用 `mcp-audit-v1`，四工具完整typed输入/观察事实/输出与搜索逐调用记录已接通；配置key时与Trace原子持久化。完整字段、超限失败及观测边界见[MCP执行审计](MCP_EXECUTION_AUDIT.md)。这项记录能力没有开放MCP执行回放，也没有补造旧Trace的原完整输入。

### 2.1 输入与执行条件

- Ask 保存原始、经 API 验证的 AskRequest，包括 `session_id`、`historical.as_of`；另外保存真正进入 Harness 的初始实体、原用户身份快照、日期/模式、版本、Token 与递归上限。`session_id` 的保存不代表多轮会话接线已经完成。
- Task 保存排队时的 typed input 和 historical selector、实际 Skill spec、输入/输出 Schema SHA-256、版本、原用户身份、实际日期、每次内层 Harness 输入及执行尝试。上下文建立失败时明确标未知，不能补造。
- 配置记录包括实际作答/判定模型、意图路由、answer_system 摘要、裁剪模式、输出 Token 上限、节点重试与时限、执行预算；区分局部 profile（`execution_limits`）与继承的共享预算池（`shared_execution_limits`）。生产装配还记录实际灰度名单、发布策略内容摘要、检索参数、重排输出量、词表版本、翻译模型及检索开关。
- 摘要采集在整个执行预算的计时范围内，文件和包版本循环合作检查 deadline；采集到期就拒绝后续模型调用，不在预算之外偷偷增加工作时间。可信本地文件的单次操作仍是同步 I/O，没有宣称可强制中断挂起的文件系统调用。
- 在线与离线共用文件清单、环境和发布策略摘要实现。文件清单包含未提交的运行源码、资源、Schema、依赖锁和 pyproject；不读取 `.env` 的正文或把凭据写入记录。安装包环境没有仓库文件时，清单范围仅为包目录。
- **源码文件摘要表示当时磁盘上的文件，不能证明所有已加载 Python 对象来自这些字节，更不是签名镜像证明。** 环境记录是包版本/Python/平台，不是托管模型权重摘要，也不包含完整操作系统或硬件性能条件。

### 2.2 事实、候选与真正发送的片段

- 保存候选 ID 与通道名次、完整 retrieval outcome（含 cache hit、拒绝原因和是否降级）、筛查/预算后实际 Evidence、原文和块内容哈希、Citation、状态/历史模式及观察到的事实清单摘要。
- `observed_fact_manifest` **仅绑定本次观察到的证据**；不是完整数据库/ACL/索引快照。相同候选或相同 evidence 不能证明 BM25 统计、向量索引、其他未返回文档及整个语料没有变化。
- 在真实 answer 请求前保存实际布局、body/body SHA-256、E1→chunk ID 别名、渲染后的正文/哈希和来源区间。另存 messages SHA-256，可与逐调用 ModelRequest 的 messages 对照。预算试算用的预渲染不当作已发送请求；实际网关记录用于判断是否真正开始调用。
- `source_start/source_end` 是 **Evidence.text 的 Unicode code point 半开区间**；`rendered_start/rendered_end` 是渲染正文的同类区间。按选择的原始单元合并并处理 `.strip()`，不用 `find()` 猜重复句子位置；省略号和人工插入的间隔没有伪造的来源坐标。
- Citation 的 doc/version/page/section/chunk 给出来源身份；这些字符区间不是 PDF 字节偏移、页面坐标、OCR 框或全页文本的绝对位置。FOCUS-02 的跨块完整 gold span 定位仍未完成，保留字段也不等于答案已完整。

### 2.3 逐调用记录

每个 MeteredGateway 调用有独立 call ID，记录：

1. 实际进入网关的完整 ModelRequest、消息、Schema、输出限制、当时的超时与请求 SHA-256。
2. OpenAI 适配器每次发送的 SDK 参数及摘要，包括删去 temperature 的兼容重发。SDK 参数不是已验证的 HTTP wire bytes，不记录认证头、API Key 或客户端对象。
3. 实际 SDK completion JSON（真实 SDK）、原始回复文本、parsed output、实际模型标识、response ID、system fingerprint、用量、时延与截断标记。离线 SDK stub 只存选定字段，并明确标 `offline_stub_selected_fields`。
4. 最终调用回执、run/attempt/reservation 关联、费用来源与结算状态。模型返回无效 JSON/截断时仍保留已知原始回复和用量；超时等未知返回保留请求与回执，response 为 null。异常只存类型，不存异常消息或服务端错误正文。

一次逻辑调用可能有两次 temperature 兼容发送；不能把 MeteredGateway 的 calls 当作 HTTP 请求数。原费用账本仍负责真实计费、未知结果保守记账与重复结算保护；新增正文记录不重算或清零费用。

调用日志按实例隔离、线程安全，最多 128 个逻辑调用、16 MiB 序列化内容；ExecutionAudit 的事件日志另有 512 事件/16 MiB 上限。上限在后续模型开始前拒绝新增调用；返回过大导致记录不完整时不能发布成功结果。Task 失败记录保留有界前缀、独立费用回执和 `model_call_audit_complete=false`。这些上限不是整个进程的严格内存上限，SDK 自己的响应对象及序列化临时副本仍占内存。

## 3. 如何读差异报告

`versions_match` 只比较版本标签。新增 `conditions` 分别报告完整输入、当前身份、磁盘源码/环境、配置、实际路由策略内容、证据内容、渲染片段和实际模型/指纹是否一致。未观察或不可确认的信息用 null；没有完整语料快照时 `corpus_match=null`，`original_conditions_reproduced=false`。

报告仍保留旧 `changed` 字段（结果、原因码、引用与证据 ID）；具体条件的变化看 `conditions`。相同 chunk ID 内的正文变化、仅裁剪布局变化或内容变化但策略标签未变，都可分别显示。`actual_models_match` 比较逐调用的 purpose、请求/实际模型、provider 与指纹序列；缓存命中省去一次调用也会让序列不同，不自动解释为换了模型。模型未知返回不能声称实际模型一致。差异是排查线索，**不能单凭一次回放断言某个因素导致了质量变化**，贡献仍需固定条件的配对实验。

策略只解析一次，同一 RequestPolicies 同时用于构造 deps 和记录版本，避免灰度指针在两次读取间切换。Trace、受限载荷和 ReplayRecord 共用调用者数据库事务；保存失败不返回成功结果，也不自动重跑模型。内存测试替身不模拟数据库 rollback，原子性结论以 PostgreSQL 测试为准。

## 4. 未交付的能力与后续

原版本加载、不可变语料/索引归档与恢复、可验证运行镜像、Task/MCP typed replay、未来 Agent 行动轨迹重演仍未实现。本轮完成执行记录和回放边界，不把这些能力登记为已交付。完整原条件能力至少需要：可加载且内容验证的旧工件、旧策略内容与预算 profile、当前 ACL 的再次准入，以及明确允许变化的外部模型因素；无法恢复时仍拒绝。

本轮是零托管调用工程验证；语义质量、实际 API 性能、原条件复现质量、独立人工和盲测都没有因此通过。新代码未提交、未重启部署。S2/S3、实验自动激活边界、冻结数据/gold 与生产验收口径保持当前台账约束。
