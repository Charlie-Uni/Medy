# 记录198：无用定义核实、重复检索与策略契约收敛

2026-10-12。主任务CODE-03；起点`5a21f74178b9a41956ff8ac23598f18a0a01bc55`，工作区干净，上轮ARCH-16已修三项权限缺陷，其远端CI38197199807成功。实现者与自审者为Codex，同一模型，无子代理、第二独立人工或托管模型调用；费用0USD。本轮只做代码质量切片，不改变Agent场景、发布或质量验收标准。

## 1. 范围与结果

历史审查的“零引用”先作为线索核实：检查src/tests/scripts及维护评测代码、历史文档、包导出、动态查找与CLI/包入口声明。没有对所有长函数或相同数字机械重构。删除9个未被使用或声明为兼容入口的定义；保留文档明确约定的`validate_pdf`。共用策略布尔读取、检索请求/结果校验、管理幂等接线、Token/费用门禁计算；显式读取Settings字段，补连接设置协议。

本轮相关源文件合计3339→3304行，净减35行。这个数字包括新共享模块，不能用删行数衡量质量；主要收益是每项校验只有一个实现、变更责任清楚。测试增加17个用例，检出错误过滤、版本漂移及不完整配置供给。没有声称项目全部无用代码已清零。

## 2. 逐项修改与兼容边界

| 内容 | 修改 | 保持的契约 |
| --- | --- | --- |
| 无用定义 | 删除`negation_count`、`env_flag`、`top_k_ids`、`as_sequence`、`sql_tsvector_target`、`content_target`、`public_error`、`snapshot_sizes`、`kinds_present`；清理相应无用导入 | 对应实际生产/实验调用均走其他实现；既有CLI不删，A2回滚、B/C实验适配器不改。没有声称未知外部代码不可能直接导入这些内部辅助 |
| PDF兼容 | 保留`ingestion.pipeline.validate_pdf`；与起点AST相同 | 记录43明确“保留为validate_file的PDF专用包装”，静态零调用不足以取消这一承诺 |
| 策略读取 | `ReleasedPolicySet._retrieval_bool`集中处理multi_query/doc_focus/source_constraint | 三个公开方法的签名/base、缺字段返回、严格bool类型、`_to`错误与含键名错误文字相同；未统一整数/字符串等不同策略类型 |
| 请求边界 | 新`retrieval.boundary.run_search`，词法/向量公开函数仅提供模型与各自冲突文字 | K严格整数且1..20、norm-v1空查询检查、原query传入适配器、调用前版本快照、结果重新验证、requested_k回声及领域错误透传相同 |
| 结果边界 | `retrieval.contracts.check_candidates`共用数量、耗尽、名次、唯一性、分数及平分排序检查 | 两个Pydantic结果模型保持原字段、冻结/extra规则、版本类与各自candidate_exhausted错误文字；没有用继承改变JSONSchema |
| 旧检索入口 | 保留`lexical.boundary.MAX_K`和vector路径导出、两公开run函数签名 | doc_ids=None时不向旧适配器增加keyword；显式空列表也原样传入，不能按假值丢弃过滤条件；词法/向量与重排证据上限语义分开 |
| 管理幂等 | 路由内`_idempotent`集中receipt store、HTTP header及TTL配置 | 六变更路由的actor、route key、DTO、callback、角色/四眼与mutation=True栅栏相同，操作与receipt仍在原权限写事务提交；核心idempotent未改 |
| Token/费用门禁 | compute_gate的cost/spend分支共用覆盖检查、均值、下降率、quality判断及报告拼装 | cost输出tokens键/1位精度，spend输出usd键/6位精度；两个25%阈值仍为独立常量，quality/slice/safety/CI/可靠性规则及门禁报告相同 |
| 设置契约 | Runtime直接读observation_window_hours/app_env/retrieval_cache；worker直接读三outbox字段；连接入口增加ConnectionSettings协议 | Settings默认值不改；旧open_connection(None/部分字段对象)的fallback只在连接兼容边界保留，值来自Settings.model_fields；没有把不同任务/TTL/连接错误语义的相似字面量强行合并 |

修改入口：[共享检索边界](../../src/medops/retrieval/boundary.py)、[词法模型](../../src/medops/retrieval/contracts.py)、[向量模型](../../src/medops/retrieval/vector/contracts.py)、[策略读取](../../src/medops/application/policy_loader.py)、[管理路由](../../src/medops/api/routes/admin.py)、[效率门禁](../../src/medops/loop/gate.py)、[连接协议](../../src/medops/bootstrap/connections.py)、[运行时](../../src/medops/bootstrap/runtime.py)、[消费者](../../src/medops/worker/retrieval.py)。

## 3. 失败、原因、补救与复测

首次mypy发现两项：

```text
Cannot use a covariant type variable as a parameter [misc]
Incompatible return value type (got "LexicalSearchResult | VectorSearchResult", expected "R") [return-value]
```

原因是共享函数的参数混用了协变类型变量，Pydantic的model_validate在union上又被推断为联合返回。改为内部结构协议及普通返回TypeVar，只有model_validate返回处保留有明确依据的cast；两个外部边界继续使用各自版本/结果类型。复测327个源文件mypy通过，该共享检索模块没有用新增Any或type-ignore绕过类型检查；管理连接参数沿用原有Any端口类型。

首次定向`2 failed,324 passed`，两个worker once测试原使用缺三outbox字段的SimpleNamespace。直接字段读取暴露供给缺失，出现`batch_failed/error_type=AttributeError`，失败分支没有到commit。生产入口始终构造完整Settings；修正测试为真实Settings并设自定义3/7/19，断言三值实际传至消费者，没有把fallback加回运行时。最终定向433 passed。

旧代码行为对照首次报48项差异。探针给旧Pydantic结果类返回旧版本类，却与新版本类比较；字段相同但Pydantic按类身份判断不相等，旧侧错误地在正常请求就拒绝。修正探针只统一版本类身份，不改旧函数/validator/gate源码或期望；先保留初次结果，再复跑1060次全部一致。这些48项不计为产品缺陷或本轮修复成果。

一次格式化后同步曾尚未完成就又启动同步；两个都完成且对同一稳定源路径比较一致，未据此启动接受测试。后续全面核验前严格等待同步完成。全局Git diff又因iCloud本地对象/工作树访问长时间无输出；终止本轮两个只读同步进程（退出143），使用已验证干净起点与明确21个源/测试变更路径重新逐个复制、SHA核对，并重验外部树681个维护输入。所有接受证据均在同步完成后运行，不将旧快照/卡住任务计为通过。

格式化清除末尾多余空行；最终diff卫生单独核对。未提交任何私有配置、测试DSN、output/pdf或本地验证工件。

## 4. 验证与可复核口径

行为对照固定起点5a21，直接读取Git中的旧函数/模型源码，在同一依赖环境对照。矩阵摘要及旧源码SHA见[机器证据](2026-10-12-implementation-198-results.json)：

- 6个模型JSONSchema；两个公开检索函数签名。
- 252个结果校验组合：正常/平分/错误平分/逆序/名次/重复/空集合，K、returned_count、candidate_exhausted组合；比较结构化错误loc/type/msg。
- 630个检索调用组合：K含bool/零/上限/超限/浮点/字符串；正常/空/全角query；doc_ids None/空/非空；正常/版本/回声/非法结果/调用中版本变更；返回结果、异常code/message/detail/retryable及实际适配器参数逐项比较。
- 54个布尔策略组合：三键、base真假、缺失/畸形/真假/整数/字符串参数。
- 108个quality/cost/spend报告与8个费用输入错误：零基线、极小金额、边界/超出下降率、质量持平/下降/上升；完整报告字段、阈值、blockers相同。

这是有界兼容证据，1060比较不是1060道真实医学任务。没有调用语义模型、修改评分版本或重跑正式质量。新增14个检索兼容反例、3个策略用例全部进入仓库正常测试，不把专门对照探针作为唯一依据。

AST补查586个Python文件，9名字剩余静态引用均为0；validate_pdf AST不变；10个管理路由的签名/decorator及六变更路由action/role/fence一致。静态扫描不能证明任意外部插件行为。

最终required `make check`退出0：**2313 passed、70 skipped、1 warning**，pytest285.79秒/总303.384秒；682文件格式通过、mypy327源文件通过、架构327模块0违例/2原精确例外、249测试文件断言静态门0违例，四套冻结数据审计与公开Schema通过。70 skip仍为既有可选B/C候选，warning仍为测试短HMAC key；2个unmappable gold继续作为miss留分母，主/安全provisional及无未见盲测告警保持。测试耗时不是API性能测量。

验证命令：带`MEDOPS_TEST_REQUIRED_SERVICES=1`的隔离树中运行`make check`；定向`pytest -q tests/unit/retrieval tests/unit/application/test_policy_loader.py tests/unit/loop/test_gate.py tests/unit/api/test_admin_routes.py tests/unit/api/test_runtime_connect.py tests/unit/bootstrap tests/integration/test_ingestion.py tests/integration/test_publish_outbox.py tests/integration/test_admin_stores.py tests/integration/test_final_output.py`。原生PostgreSQL/Redis必需，测试只在一次性数据库/临时角色运行，不更新共享业务数据。

文档自审41 passed、退出0，pytest10.20秒/总11.040秒；143个唯一任务ID无新增/遗漏/重复，129本地链接均存在，21代码/测试路径SHA再次一致。

完整私有日志和对照脚本保存在`.local/audit198/`，不入Git；公开机器证据记录输入矩阵、源文件哈希、命令、退出码和限制。维护输入绑定继承记录197的679路径，干净起点HEAD逐个匹配后添加本轮两文件；后续只对明确变更路径重新读根目录SHA，未宣称本轮重读所有历史JSON/PDF。

## 5. 八项工程自审核

| 项目 | 结论 | 依据与限制 |
| --- | --- | --- |
| 需求/范围 | 通过 | CODE-03核实后删除/归一，兼容入口保留；CODE-06、动态Agent及部署不混记完成 |
| ADR/阶段 | 通过 | PLAN-02/EVAL-32、S2/S3、实验激活、盲测与逐次付费约束不变 |
| 正确性/失败 | 通过 | 1060次旧行为比较，17新增回归，初次类型/供给/探针问题已修复复测；领域错误透传、版本及过滤失败关闭 |
| 权限/数据 | 通过 | 六管理mutation栅栏、角色/action不变；最终输出原生回归；无冻结/gold/生产策略/迁移修改 |
| 预算/取消/副作用 | 通过 | 0托管调用/0USD；compute_gate原阈值和精度不变，预算/回执/取消实现未改变；没有服务重启、部署或候选激活 |
| 追溯/版本 | 通过 | 起点/旧源码SHA/输入矩阵/失败补救/接受命令留证；未把局部机械改善写成真实质量或提速 |
| 验证充分性 | 通过（本轮范围） | 定向、旧行为、required全量及文档检查；只对本轮工程范围负责 |
| 状态/文档 | 通过 | 台账、README、机器证据与记录一致，所有原任务ID保留；新提交CI按自身SHA核对 |

## 6. 提交、回滚、限制与下一步

按七个功能批次明确路径提交：无用定义、共享检索及回归、策略布尔读取、管理幂等接线、效率计算、设置契约、文档/机器证据。每批暂存路径/cached diff/内容核对，全部完成后一次推送；原5a21的CI不能代表本轮新SHA。

第一批普通`git commit`在工作树刷新阶段持续无输出，HEAD仍为5a21、index.lock为0字节。本轮只终止该Git进程，确认锁已清理、HEAD/七个已暂存路径与内容保留；改用`git commit --only -- <明确路径>`后提交成功。第二批同样出现迟滞，进程随后正常完成；一次终止请求返回no such process，没有改变提交。第三批起Git只在本次命令指定已验证的外部工作树，先逐个比对它与原项目字节，并关闭无关提交摘要输出；根仓库main和文件仍保留，提交内容来自相同已审快照。后续各批同样核对暂存及工作树内容，只提交所列路径；没有强推、重写历史、清空暂存或覆盖他人文件。

代码回滚可按对应批次撤回，没有迁移或业务数据恢复。恢复被删定义与旧重复实现不会改事实数据；管理路由的ARCH-16权限会话须保留，不能将CODE-03回退扩大为旧安全修复回退。

下一主切片CODE-06：测试fake/seed的规范入口、数据库夹具供给与脚本加载。继续保持隔离清理、用例数量和错误检出能力。当前仍为固定RAG Workflow/Harness与静态Skills，业务Agent及模型自进化尚未交付；CODE-03不支持质量/性能改进声明。长期消费者、原条件/Task-MCP回放、真实容量/盲测/第二人工、PLAN-02及逐次付费授权仍各自跟踪。

六批代码/测试提交：

- `8874dc8`：dead，7个明确路径。
- `f43d275`：retrieval，6个明确路径。
- `7e00cc0`：policy，2个明确路径。
- `cdf605e`：admin，1个明确路径。
- `f03112b`：gate，1个明确路径。
- `a6564f7`：settings，4个明确路径。

第七批仅README、当前台账、本记录及机器证据；最终推送/CI按它的实际SHA回查，不递归为记录自身CI另建提交。
