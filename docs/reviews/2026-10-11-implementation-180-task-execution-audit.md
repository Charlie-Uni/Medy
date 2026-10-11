# 记录 180：异步 Skill 的统一执行审计

日期：2026-10-11。任务 ID：**ARCH-06**。对应 Goal：OPT-09、INV-OBS-01/03。实现者：Codex；自审核者：Codex（同一实现者，不是第二独立人工）。开始为 READY，随后 IN_PROGRESS → REVIEW；本轮工程自审通过后 DONE。

## 1. 目标、范围与固定条件

依据台账与 AR06，在 ARCH-02/03 通过后补 Task 的证据和最终核验审计；Ask/Task 共享持久化与失败关闭责任。所有者授权继续无付费实施；没有把历史费用余额当成本轮实验授权。

保留五类生产 Skill、原 Claim/最终判断策略、默认模型、Skill 标签、预算/重试/期限、租约栅栏、ACL、冻结数据与 gold、评测分母/阈值和已发布策略指针。无迁移，本机三库仍 0024。没有把保存材料等同于精确回放或新 Agent。契约见[执行审计说明](../TASK_EXECUTION_AUDIT.md)，结构化业务核验沿用[记录179](2026-10-11-implementation-179-final-skill-judgment-verification.md)。

HEAD `5a604050b9c0706bfd823685e5befcb9619d64a6`。开始已有 133 个未提交文件，逐文件备份；116 个字节不变，17 个明确重叠文件按差异核对，0 缺失，141 个任务 ID 完整保留。完整原改动未覆盖或提交，备份和 SHA 结果见本地结果路径。

## 2. 实现及保存责任

- 新增 `harness/audit.py`：每次 Registry 执行一个 journal，512 事件 / 序列化事件16 MiB 有界；JSON 拷贝，容量失败锁定，失败可保存已观测前缀。Trace/身份检查在检索之前；批量子任务隔离 journal，日期/总预算保持原规则。
- Harness nodes 在 operation 写入前保存真实 NodeAttempt 与合法证据，正常结束再保存输入、候选、回答、核验和安全快照。中途持久化异常不会抹掉已运行节点，也不编造未执行步骤。
- 二阶段/AE 的结构化输入、schema、原候选和截断状态进入受限 events；最终比较的四项判词及原始输入、直接引用核验的逐条结果分别保存。结构化计时为 `skill:<name>:generate`，与外层执行区分。计时不添加调用、重试、预算或 deadline。
- SkillRun 返回独立审计快照，TaskRunner 同时保留执行 journal，以便在没有 SkillRun 的异常路径报告事实。Task 上下文在入口固定；最终完整 Citation 必须逐字段等于观测证据。Task 结果与 Trace 的业务状态、证据和引用一致；lost/写入失败不声称候选已被接受。
- 新增 `application/execution_audit.py`，Ask/Task 共用 writer；同一事务保存 Trace、升级摘要和可选加密载荷。Span 带实际路由版本和 restricted_payload_enabled 布尔值；正文不进入普通遥测。Task 载荷三个 kind 聚合在 task 节点，格式 task-audit-v1，兼容现有表的唯一键。
- 重试内层本地序号在 Trace 中转为按时间的连续序号，原序号/key/detail 仍在密文 events。不会改模型回执的 call/attempt 身份。无法创建上下文的早期失败明确版本未解析，不猜测用于回放。
- Ask 原 payload 字段保留，证据增加完整 Evidence 字段，model_output 增加 safety_result。没有新 HTTP/TaskResult schema。

普通 Trace 不含证据正文、结构化候选或观察叙述；错误日志/Span 只用类型及错误码。被筛掉的注入正文不入证据快照，未知/越权来源只保留调用者提交的 ID，不晋升为 evidence。生产 payload key 配置存在才持久化加密正文；没有 key 的原开发配置仍只保存元数据，不能声称精确复现。admin HTTP 入口、restricted DB 角色、用途日志、保留和轮换规则沿用。

## 3. 自审发现、错误与补救

| 发现 / 失败 | 原因 → 修复与复验 |
| --- | --- |
| 原缺陷回归 1 failed | Task 结果保留 c1 引用，而 Trace evidence 固定为空 → 真实 journal 与最终引用绑定 → 原 TaskRunner 反例通过，retrieve/verify/最终判断节点可见 |
| 新测试首轮 10 failed / 6 passed | 新夹具把 str 部门传给要求 Dept 的 user builder → 转为真实枚举；五类路径32项及后续全量通过，没有改生产枚举口径 |
| 重试导致同名节点序号重复 | DB 唯一键为 trace/node/attempt，内层每次从1开始 → Trace 连续序号、密文保留本地原号；真实 PostgreSQL 三轮重试写入通过 |
| 内层存储错误可能丢失已运行事实 | 只在 Harness 完整返回时收集不够 → 节点在 operation 写入前留下尝试/证据；存储失败前缀测试通过 |
| stage 与 outer 使用同名 | 难区分生成计时和 Skill 重试 → 结构化命名增加 generate，最终核验单独命名；无 provider purpose 或费用身份变化 |
| lost 新测试 1 failed / 34 passed | 夹具仅拒绝 complete，但旧 worker 仍实际持有租约，record_lost 正确拒绝 → 用真实时钟在最终写入前过期模拟竞态；没有弱化持有权栅栏 |
| full 首次退出2 / Error127 | Makefile 寻找 venv/bin/python，而新快照只建立了 .venv 链接 → 增加正确外部 venv 链接，保留失败日志 |
| full 第二次4 failed / 2004 passed /70 skipped | 新 audit.persist Span 在 Harness 元数据 scope 外丢失实际路由版本；另一个独立 worker 故障夹具未实现 payload_writer → 共用 writer 显式绑定 Trace 的实际版本，夹具明确 None；修复复测49 passed、最终full2008/70通过 |
| 审计失败下伪成功风险 | 必须验证真实事务而非无回滚内存夹具 → PostgreSQL 在真实 trace / 部分ciphertext插入后注入异常；结果、Trace与半份载荷回滚，仅失败报告提交，模型不重跑 |

有一处只读 glob 未匹配导致 zsh no matches、两处猜测的既有文件名不存在和一次跨工作树读取本地日志路径错误；均按实际 rg 路径修正，无内容写入副作用。原红灯输出被成功 tail 包装，pytest 实际为1、包装退出0，明确记录而非称测试成功。

## 4. 验证命令与证据

1. 原红灯：`python -m pytest tests/unit/skills/test_final_judgments.py::test_async_task_preserves_non_completion_of_the_business_judgment -q`，**1 failed**，明确 `() != ('c1',)`；日志 .local/arch06-red.log。
2. 定向：`env -u DEBUG venv/bin/python -m pytest tests/unit/application/test_task_audit.py tests/unit/application/test_tasks.py tests/unit/application/test_task_lease.py tests/unit/skills tests/unit/api/test_payload_route.py tests/unit/api/test_ask_route.py tests/unit/api/test_historical_context.py tests/unit/harness/test_execution_budget.py tests/unit/harness/test_historical_context.py -q`，**172 passed /2.25s /exit0**。包含五类正常/撤权/不安全/无证据、二阶段失败、完整 Citation、并行隔离、容量、前缀和租约保护。最后的4项修复由下一条覆盖。
3. 修复复测：`python -m pytest tests/unit/core/test_telemetry_correlation.py tests/unit/faults/test_main_chain_faults.py tests/unit/application/test_task_audit.py -q`，**49 passed /2.07s /exit0**；新 Span 的实际灰度版本与正文保护、原故障恢复门保持。
4. 数据库：`env -u DEBUG python -m pytest tests/integration/test_task_audit.py tests/integration/test_tasks_store.py tests/integration/test_audit_store.py tests/integration/test_payload_store.py -q`，**24 passed /7.34s /exit0**。新增5项实测原子提交/回滚、三轮重试唯一性、密文读取/访问日志、持续错误恢复；原两worker费用/结果保护与角色限制继续通过。
5. 最终完整：注册仓库外工作树 `arch06-verified-4mwb5pgz`，同外部py311 venv、同.env/.env.dec001，`env -u DEBUG PYTHONPATH=<snapshot>/src:<snapshot> make check`，**2008 passed、70 skipped、1 warning /53.92s /exit0**。477格式文件、200源码类型文件、安装/lint/数据集审计/Schema检查通过。510维护输入和配置 SHA 相等，0不符；秘密配置仅报告相等，不公布内容/哈希。
6. 可选跳过：仅 B/C 候选两文件 `-rs` 复核，**70 skipped /0.04s**，均 OperationalError 不可达；本轮 PostgreSQL、Redis、生产 BM25 D 等必需依赖实际执行。warning 仍为 JWT 认证反例的刻意短 HMAC key。CI required 依赖缺失不得 skip 的独立强化仍属ARCH-14。

7. 最终文档：同一核验树 `python -m pytest tests/unit/docs -q`，**10 passed /0.87s /exit0**；6份文档173个本地链接均存在，141任务ID保留，仅ARCH-06/07/08改变状态，git diff --check退出0。

全量数据审计继续提示：两个 unmappable gold 留在分母、旧安全回放不能代替当前集、主/安全集第二独立人工未完成、尚无合格未见盲测。本轮没有掩盖这些提示或据此宣称发布通过。最终文档检查、链接、任务编号、状态和本轮保存清单详见[结果JSON](2026-10-11-implementation-180-results.json)。

## 5. 八项强制自审

| 自审项 | 结论与本轮证据 |
| --- | --- |
| 需求与范围 | 通过：AR06 原引用缺失失败已复现修复，五类 Skill 统一审计及正文保存责任明确；冻结分母/阈值/默认策略未改 |
| ADR 与阶段硬门 | 通过：原架构修复，未改目标或验收；ARCH-04/11 保持工程结论，PLAN-02剩余契约/S2/S3未通过，自动激活只限实验 |
| 正确性与失败路径 | 通过：正常、撤权、空证据、安全拒绝、最终比较/二阶段失败、并行/重试/损坏引用/容量/中途持久化/lost均有证据；真实事务回滚与持续失败不放出结果 |
| 权限与数据 | 通过：合法观察与文档事实区分，完整Citation绑定，未知/注入不晋升；正文仅密文，admin+purpose/RLS与访问日志沿用；已有元数据配置限制明确 |
| 预算、取消与副作用 | 通过：审计无供应商调用或业务重试，共享预算/日期/租约测试和真实两worker回归通过；0托管调用/0USD，未迁移/提交/推送/重启 |
| 追溯与版本 | 通过（本轮范围）：证据/候选/最终核验/安全/原始尝试与输出可定位，实际版本Scope复测；call receipts独立保存。渲染后逐请求与原条件复现仍明确归ARCH-07 |
| 验证充分性 | 通过（工程）：定向172、修复49、数据库24和full2008/70，510输入一致及失败日志保留；真实医学语义校准/性能/独立人工未测，不替代质量结论 |
| 状态与文档 | 通过：IN_PROGRESS→REVIEW→DONE留证；141任务未删，ARCH-07/08仅因工程前置满足转READY，ARCH-12继续等ARCH-14；入口与审计契约同步 |

## 6. 状态、回滚与下一步

工程范围 DONE；真实模型质量、正式发布、第二独立人工、未见盲测和S2/S3不是本轮通过项。所有工作区改动仍未提交、未推送、未重启上线。无生产DDL/data迁移，仅临时集成测试数据库。

下一主切片 **ARCH-07**：完整逐调用输入与实际渲染片段、回执/版本绑定、诊断与原条件复现区别；目前Replay仍拒绝Task/MCP，不把有载荷等同于已能回放。ARCH-08仅解锁待后续收敛装配；ARCH-12仍等ARCH-14。

回滚仅撤本轮4个新增Python模块/测试、审计契约/记录及17份原文件本轮差异；使用开始前逐文件备份，不运行git reset、不要删除已有未提交工作。具体备份、本轮差异和核验快照见结果JSON。

本轮时间主要用于契约接线、反例、真实数据库故障注入、两次完整门禁及修复；没有供应商等待或人工等待。未据单轮局部投入重估项目整体工期；真实流量存储/时延开销和ARCH-07实现仍需单独估算。遇到需改变保存策略或费用实验时再提供可审核方案请所有者裁决。
