# 实现记录 171：Harness 总截止时间与执行收束

日期：2026-10-10。任务：ARCH-01 / AR01；对应 OPT-11、INV-HAR-04。本轮实现者自审通过，托管模型调用 0、费用 0 USD；没有正式答案质量或容量成绩。基线 HEAD 为 `5a604050b9c0706bfd823685e5befcb9619d64a6`，改动尚未提交。

## 1. 问题、目标与完成范围

[架构审查 AR01](2026-10-10-architecture-audit.md)已经复现：旧 `run_node` 用一次性线程池运行 body，等待超时后返回，但 Python 无法强制停止已经运行的线程。于是旧 body 仍可继续进行 SQL、模型调用和费用结算，调用方却已经结束节点 Trace 或事务，甚至启动下一次重试。

这会破坏三件事：同一节点的两次执行可能重叠；超时后的调用仍可能产生费用；Trace 的终态不再表示工作已经结束。增加 `Future.cancel()` 或缩短等待时间不能取消已运行的线程。

本轮目标是让现有生产链的执行者承担收束责任：同一节点所有尝试共用总截止时间，嵌套节点不能延长父节点；过期后不再发起业务 SQL 或模型调用；已接纳的翻译、HTTP 和本地推理结束或完成取消清理后，才能离开 body。旧工作未收束，不启动下一次重试。

覆盖 API Ask、异步 worker 的五类固定 Skill、MCP 检索，以及 `safety_run`、`smoke_ask`、`skill_smoke`、`replay_run` 四个活动运行入口。历史离线诊断中的 `PinnedThread` 仍保留，其结果与限制保持原记录；本轮不将所有 Python 扩展或未来插件的任意阻塞代码承诺为可强制取消。

## 2. 方案与技术选择

### 2.1 节点在调用线程内执行，共享单调时钟截止时间

新增 [core/deadline.py](../../src/medops/core/deadline.py)，使用 `time.monotonic()` 和 `ContextVar` 保存执行截止时间。墙上时钟用于审计时间，单调时钟用于剩余预算，避免系统校时改变超时判断。

[run_node](../../src/medops/harness/contracts.py)不再为每次尝试新建线程池。body 在调用线程内执行，执行前后检查截止时间；迟到成功结果被拒绝。重试仅针对原有可重试基础设施故障，最多两次；前一次必须已返回，退避与所有尝试共用一个节点预算。总预算耗尽时终止，不再重新获得一份完整超时。

嵌套 Skill 节点取父截止时间和自己截止时间的较早值。使用真实 LangGraph 的回归测试验证这一继承，而非仅对纯函数替身验证。原 `NodeSpec` 超时数值与公共 `NodeAttempt` 字段不变，但 `timeout_s` 的执行语义现在明确为包含重试和退避的节点总预算。最终超时沿用 `dependency_timeout`，终态记录为 `failed`。

根节点同时执行上限为 8，准入最多等待 250 ms；嵌套节点复用父名额。没有新建无上限的 executor 等待队列。这是单进程保护，不是整个部署跨进程合计 8 个请求，也不是完整问答的统一总时长；后者仍由 ARCH-05/11 分别处理。

### 2.2 PostgreSQL 在原权限连接上执行可取消语句

新增 [DeadlineConnection](../../src/medops/infrastructure/db/deadline.py)，包装现有、已经绑定用户和部门 RLS 的连接，不开第二个连接，也不切换管理员身份。每条受保护 SQL 在执行前检查截止时间，以剩余毫秒与既有 `statement_timeout` 的较小值作为语句上限。

语句放在 savepoint 内：取消只回滚该语句的子事务，外层事务仍可保存失败审计；成功时恢复旧 timeout。真实 PostgreSQL 的 `pg_sleep` 回归验证取消、旧设置恢复和外层连接继续可用。正常 `fetchone`、cursor 上下文和迭代行为也已验证。

此设置限制服务器执行中的语句，不是对操作系统、连接建立或断网后 libpq 任意阻塞的通用强杀机制。清理、回滚和审计仍使用连接既有约束，不因业务截止时间已过而被主动跳过。事务长度和连接资源优化没有夹带实施，保留 ARCH-12。

### 2.3 托管模型请求使用可取消的异步传输

生产 `OpenAIModelGateway.from_settings` 使用锁定版本 2.54.0 的 `AsyncOpenAI`，保留现有同步 `ModelGateway` 接口。新增 [AsyncChatTransport](../../src/medops/infrastructure/llm/async_transport.py)负责一个事件循环线程、8 个调用准入和最多 250 ms 的准入等待。SDK 自动重试继续关闭，重试责任由 Harness 保留。

HTTP 协程在 `asyncio.timeout` 内等待；到期取消并等待协程清理，调用线程再收到失败，而不是自己停止等一个仍运行的 Future。生产 SDK 的异步调用和 `close()` 方式已对照本地锁定包及[官方 Python SDK 文档](https://developers.openai.com/api/reference/python)；没有升级 SDK，也没有替换 HTTPX 后端。

每次发送使用当前剩余预算。既有 temperature 不支持时的兼容重发也共用该次调用预算，不能再次从零计时。用真实锁定 SDK 和 HTTPX `MockTransport` 验证：请求进入 HTTP 后触发超时，HTTP 的 `finally` 已完成、协程集合已清空、费用已结算，再结束节点。测试没有连接模型服务。

[BudgetedGateway](../../src/medops/infrastructure/llm/budget.py)在预留前和预留后检查截止时间。若等账本时已经过期，则不调用模型，释放预留并结算 0；已经开始发送的失败请求仍按既有保守费用口径结算。关闭 gateway 会向下关闭传输，API/worker/MCP 退出入口承担资源清理。

本地取消不能保证供应商已经停止计算或不收费。本轮只证明本地传输与结算收束；并发失败调用的逐 Trace 费用归属仍是 ARCH-04，未在此宣称解决。

### 2.4 本地 BGE 从不可终止线程迁入受控子进程

本地 Torch/MPS 推理可能卡在 native 调用里，合作式 Python 检查不能打断它。新增 [InferenceProcess](../../src/medops/retrieval/inference_process.py)，用 `multiprocessing` 的 `spawn` 创建进程；模型加载和推理在子进程主线程中执行，满足既有 Metal 线程约束。

私有 Pipe 只传模型配置、文本和结果；数据库连接、HTTP gateway、费用账本、Trace writer 留在父进程。模型 revision、精度、分词、排序逻辑和输出数量保持原配置。最多接纳 8 个本地调用，单 lane 串行；排队与推理共享截止时间。

已发出的推理到期或子进程退出时，父进程先终止并回收子进程，再返回失败；之后 lane 停用、readiness 为 false。不会自动重载模型或再次发送旧调用，恢复由监督进程重启服务承担。正常空闲关闭先发送退出指令、等待 2 秒，再有必要时 terminate/kill；强制清理分别最多等待 250 ms。失败时没有把数据库或生成职责转交给子进程。

这沿用[记录 169](2026-10-10-implementation-169-rerank-burst-and-process-isolation.md)已验证的隔离方向，目的是取消与资源归属。跨请求合批仍未采用，也没有接入独立网络模型服务。不同 `output` 的 scorer 仍按旧实现分别构造，权重共享与 singleflight 留给 ARCH-10。

### 2.5 翻译分支在所有退出路径上收束

原始检索与翻译仍并行，翻译池仍是 4 worker / 8 在途。提交时传递截止时间及 Trace context，已经过期的排队回调不再进入模型调用。

[ProductionRetrieval](../../src/medops/harness/retrieval_port.py)用 `finally` 收束已经接纳的翻译：尚未开始的可以取消；已经开始的必须等待其适配器结束或取消清理。即使原始检索先失败，也不能让翻译继续在返回后产生费用。两项新反例分别验证原始检索异常路径与过期排队路径。

## 3. 入口与维护边界

| 入口 | 本轮接线 |
| --- | --- |
| API | ProductionRuntime 使用进程嵌入/重排；Ask 与 Skill context 包装原权限连接；lifespan 关闭 runtime 并在 finally 刷新遥测 |
| worker | 正常退出、`--once` 和异常退出均经过 finally 清理；runtime 关闭失败也继续关闭遥测；共享 runtime 的当前五类 Skill 继承节点预算 |
| MCP | 工厂使用同样的进程适配器和权限连接；检索采用现行 retrieve 节点预算与准入；stdio/HTTP 退出清理，资源关闭异常也继续关闭遥测 |
| 四个活动运行工具 | 使用同样的进程嵌入/重排；解释器退出通过资源 owner 清理；不更换数据、模型或运行评分口径 |

公共 API/OpenAPI、Skill Schema、迁移、依赖锁和冻结数据没有改变。来源约束与裁剪发布状态不变；BM25、Redis、路由及安全策略不因这一轮重新发布。后续模块装配归一仍是 ARCH-08，避免在正确性修复时同时大范围搬目录。

## 4. 核验结果

### 4.1 最终工程门

最终 `make check` 退出码 **0**：**1774 passed、70 skipped、1 warning，pytest 45.00 s**。ruff、455 个维护文件格式、193 个源码文件 mypy、四个冻结评测输入审计和 Schema 漂移均通过。比上一轮 1753 个通过新增 21 个测试用例，旧超时测试也已改为验证不遗留 body 和不重叠重试。

70 项跳过仍为既有候选 B/C 实验环境缺失，不是本轮 PostgreSQL/Redis 必需集成测试被跳过。一个 warning 是认证反例测试的短 HMAC 假 key；没有改变生产密钥。评测审计继续报告两个 unmappable gold、旧回放安全输入、第二人工缺口和未见盲测缺口，不因工程通过而抹掉它们。

最终全量检查运行在 iCloud 范围外的等价 detached worktree：`/Users/leaf/.cache/medy-checks/arch01-76a6yhcg`。显式 `PYTHONPATH` 指向该快照；修改的 31 个 Python 文件与原工作区逐字节及 SHA-256 核对一致。构建基线也是同一 HEAD；本地数据库配置仅以权限 0600 复制，未进入 Git 或报告。

最终日志在该快照 `.local/arch01-final-check.log`；原工作区真实模型/数据库核验脚本与结果在忽略的 `.local/arch01_validation.py` 和 `.local/arch01_validation_results.json`。可提交的[证据 JSON](2026-10-10-implementation-171-results.json)保存源码绑定、最终日志哈希、计数和无正文的结果。

### 4.2 真实本地模型与事实库

| 检查 | 实测结果 | 范围 |
| --- | --- | --- |
| 真实 BGE CPU：直接调用与子进程调用 | embedding/reranker spec 相同；向量最大绝对差 0，分数最大绝对差 0 | 一个 query、两个文本的行为等价 smoke；不是全语料质量证明 |
| CPU 子进程启动 | 9.698 s | 单次测量，无 P95 含义 |
| MPS 完整 runtime 启动 | 25.393 s，ready=true | 包含 runtime 装配；不能沿用旧 10–11 s 冷启动结论作为当前值 |
| 真实 `medops_v2` 检索 | 8023.45 ms；20 个候选、8 个证据；attempt=ok | 英文问题跳过翻译，gateway 用拒绝意外调用的替身；没有回答生成或语义裁判 |
| 收束 | SQL 仍可用；两次检查的子进程均已回收 | 正常收束；卡死/退出/启动超时另有真实 spawn 反例测试 |

本地模型从已有固定缓存加载，离线开关禁止临时下载。没有调用托管生成、翻译或裁判 API。这个单题检索时间不能称作完整问答 P95，也不能替代 BM25-09、CACHE-10 或 PERF-10。

## 5. 本轮出现的问题与补救

| 问题/错误 | 原因 | 处理与保留限制 |
| --- | --- | --- |
| 首次全量 1766 passed、70 skipped、4 failed | 旧运行工具 fixture 仍 mock PinnedThread；连接 identity 断言尚未识别 facade；SDK 冷初始化干扰短超时测试 | fixture 改为实际进程适配器；断言底层仍为同一连接；HTTP 取消测试先用本地 mock 请求暖初始化，再验证已进入 HTTP 的取消。最终全部通过 |
| gateway 参数测试要求 timeout 恰好为 30.0 | 发送前按剩余预算裁剪，会减去已耗时的微秒 | 断言改为 0 < timeout <= 30；新增 temperature 重发共用预算的独立反例 |
| LangGraph 测试的版本字段类型错误 | `skill_version_set` 要求 tuple，fixture 用了不符合契约的值 | 使用符合现有 VersionSet 的空 tuple；未修改生产 Schema |
| 真实 runtime smoke 缺 OIDC issuer/audience | 启动装配校验生产认证必需设置，本地脚本没有提供 | 只在 smoke 的 Settings 对象提供合成测试 issuer/audience；不写 `.env`，不放宽认证门。DEPLOY-01 仍按原任务推进 |
| CPU 实际检索超过原 20 秒节点预算 | 两线程 CPU 下本地计算耗时，测试负载与正式 MPS 运行设备不同 | 保留超时、失败关闭和子进程回收，不放宽阈值；MPS 单题另行测得成功。CPU 性能没有据此达标 |
| 正常退出出现 Torch semaphore 的 resource_tracker 警告 | 正常路径直接 terminate，子进程没有机会主动清理 | 正常空闲路径增加退出握手；强杀仍可能依赖 CPython tracker 清理，因此 lane 不自动反复重启。警告不冒充模型质量错误 |
| 原目录全量检查停在源码读取 | iCloud 将文件标为 `compressed,dataless`，CPython 读取占位文件阻塞；ENV-02 只迁移了依赖环境，源码仍在 Documents | 精确停止自己启动的检查进程。该次 510 passed、70 skipped 后 KeyboardInterrupt，不登记为通过；从 HEAD 建仓库外快照并应用相同改动、核对源码后重跑 |
| 第一轮仓库外检查 1750 passed、92 skipped | 快照未带 `.env.dec001`，候选 D 的 22 个本地数据库测试被跳过 | 补齐本地私有配置，权限 0600；最终 1774 passed、70 skipped，恢复原覆盖。未将较多 skips 当作完整核验 |
| `The Transformer cache_dir argument is deprecated.` | 既有模型构造参数与框架版本的兼容警告 | 本轮不同时改变 revision、精度或模型加载 API；保留兼容维护项 |
| 收尾发现 worker/MCP 的遥测关闭可被跳过 | runtime/factory 关闭抛出异常，或 MCP server 抛出异常时，原来置于 finally 之后的遥测关闭无法执行 | 使用嵌套 finally；增加 MCP server 失败及资源关闭同时失败两个回归，均验证 owner 关闭和遥测收束顺序 |

失败结果先定位再修复，不覆盖历史测试输出。没有将反例 fixture 的错误描述成生产真实付费调用事故。

## 6. 自审与已知限制

| 自审项 | 结论 |
| --- | --- |
| 执行与重试 | body 不再在线程池中被遗留；迟到结果拒绝；旧尝试收束后才能重试；耗尽预算无新尝试 |
| 分支与并发 | 根准入、嵌套复用、翻译错误路径、排队过期、本地推理排队/卡死/退出均有回归 |
| 资源与停机 | HTTP 清理先于调用返回；本地 child 回收先于失败返回；API/worker/MCP 的 owner 关闭资源 |
| 费用 | 预留等待后过期不发送且结算 0；已开始调用保守结算；没有调用新付费服务 |
| 权限与事实 | facade 保留原连接和 RLS，真实检索仍走事实回查；既有权限回归与 Schema 检查通过 |
| 数据与策略 | 冻结 gold、数据文件、依赖锁、迁移、模型及策略发布指针无改动 |
| 可追溯 | 代码/测试 SHA、日志、真实本地 smoke 和已失败路径入账；自审者为实现者 |

截止时间是业务工作的预算，资源清理、事务回滚和已开始调用的费用结算可以超过它；否则只能通过丢弃工作来假装及时返回。本轮没有保证任意 Python body、native 扩展、系统级阻塞或不响应取消的自定义 SDK 都能在精确毫秒内终止。现有受支持适配器已接合作式截止时间，已知不可合作的 BGE 推理使用受控进程；未来新增适配器应复用这些约束或显式隔离。

进程停止后需要 supervisor 重启；完整部署的监督、信号与恢复演练仍在 ARCH-13。跨进程争抢、任务 lease、调用级费用归属、统一 Token/费用预算、Skill 判断及证据审计分别仍待 ARCH-05/04/11/03/06。本轮没有把 ARCH-01 工程通过扩张成整个平台架构、医学质量或原验收门禁通过。

## 7. 下一步

ARCH-01 标记 DONE，解除 ARCH-05 的工程前置。下一轮对齐任务总时长、lease 与持有权：明确 task/attempt 身份、续租与失去租约后的行为，验证两 worker 接管、完成写入栅栏以及重复外部调用的费用风险。仍先做零费用替身和真实数据库核验，实际模型运行另行申请当次费用授权。
