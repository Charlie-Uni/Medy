# 记录 201：EVAL-33 离线隔离原语、合成验证与自审

- 日期：2026-10-12；实现及自审：Codex。不是第二独立人工。
- 任务：EVAL-33；Goal：让后续候选生成、验证、盲测有可检查的内容绑定、最小输入与暴露记录。
- 基线：`c2dcdf2b7a4958b9058cc1048d06b5f604dbab34`。按台账只推进一个无付费 S0 切片；D-01/D-02 未决，不进入 S2。
- 状态：**本轮原语范围工程自审通过，EVAL-33 仍 IN_PROGRESS**。没有完整 runner、真实身份隔离、新盲测题或 Agent 实现。
- 机器收据：[201-results.json](2026-10-12-implementation-201-results.json)；协议：[EVALUATION_ISOLATION v0.2](../agent/EVALUATION_ISOLATION.md)。

## 1. 范围和改动

新增评测包 [isolation](../../src/medops/evals/isolation/__init__.py)，七个模块；新增五个测试/支持文件、71个用例。复用现有 `DomainModel`、SHA/canonical JSON 和 norm-v1，不复制 hash、文本规则或生产装配。原704维护输入逐字节保持；生产入口不导入此评测包。冻结 query/gold、评分器、分母、阈值、默认模型、ACL、安全规则、发布策略、数据库迁移与 S0 原开发规格均未改。

| 能力 | 行为及证据 |
| --- | --- |
| 内容绑定 | 公开manifest不含正文/逐题ID/自由标签；私有inventory绑定题、家族、关联组、query/norm/payload摘要。未知资格固定unknown |
| 分组检查 | 跨集合精确/规范化query、题ID、家族和已核实关联组重叠拒绝；不假称模糊近重复或未见证明 |
| 投影 | 在任何读取前拒绝非法role/split/grant/lock；runtime仅load_input且只出item_id/query，审核路径才读gold |
| 账本 | POSIX共享/独占锁＋调用方头CAS＋hash链；并发仅一个旧头写者成功，重复/篡改/倒序/截断/不完整行拒绝 |
| 失败关闭 | 固定错误代码；重复JSON键、model_copy非法字段重新校验；16MiB上限、软链接/非普通文件/公开权限拒绝 |
| 合成入口 | 实际执行九项canary检查，临时文件自动清理；无数据库、缓存、遥测或托管模型依赖 |

运行：`env -u DEBUG PYTHONPATH=src venv/bin/python -m medops.evals.isolation --self-check`。只输出内容为空的检查摘要；canary已公开，不能计入盲测题数。grant/lock必须由可信runner提供，这些DTO不认证调用者，不能直接接受模型自报角色。

## 2. 自审发现、错误原文与修复

1. 首轮lint：`UP017 Use datetime.UTC alias`，`B904`（except内显式异常链要求）。改用UTC、`from None`与规范import；复测与全量lint通过。
2. Pydantic的`model_copy`不执行重新校验；JSON默认解析允许重复键覆盖。新增关键入口重验和全层重复键拒绝，验证非法role/lock/event/嵌套hash/public字段；错误不回显canary正文。
3. 初版用途/角色判断遗漏：runtime或validator事件即使写了`candidate_generation`也可能被忽略。用途是直接优化接触证据，现任何角色该用途都记exposed；真实runtime执行记`runtime_execution`。新增三种相反角色反例。没有记录仍unknown，绝不判clean。
4. 初版文件权限只保证新建0600，既有0644文件仍可操作。现发现group/other权限直接拒绝读写，原文件字节/权限保持；不擅自修权限或追加。补原生文件反例。
5. 首次完整门禁出现旧用例失败，原输出为：

```text
test_five_skills_unchanged_facts_still_complete[off_label_check]
AssertionError: {'code': 'dependency_timeout', 'message': '服务暂时不可用，请稍后重试', ...}
1 failed, 407 passed, 70 skipped in 347.99s
KeyboardInterrupt ... psycopg/cursor.py:117
make: *** [test] Error 2
```

最后两行是实现者发现本轮暴露判定缺陷后，核对父PID，仅对自己的pytest进程发SIGINT的结果；不是门禁通过。该轮总552.807秒，日志/收据在本机`.local/audit201/initial-gate.*`保留。生产/原测试代码未变；原off-label用例定向复测通过，第二完整门禁通过。底层瞬时延迟原因未确立，不能声称性能缺陷已修，也没有放宽生产或测试时限、跳过此用例。

账本fsync失败专项测试证明：可能已写入字节但操作返回`ledger_io`；旧头重试拒绝。保管方需外部回执核对，不能删除行/替换链来假装成功或无暴露。

## 3. 验证结果与追溯

在仓库外字节一致快照执行，使用固定venv，移除继承的非法DEBUG值，要求原生PostgreSQL/Redis。只在一次性测试数据库做测试写入；没有业务库DML、迁移或服务重启。

| 命令/核验 | 结果 |
| --- | --- |
| 原语四个测试文件＋旧off-label失败用例 | 72 passed，pytest7.67秒，总10.835秒 |
| required-services `make check` | 退出0：2393 passed、70 skipped、1 warning，pytest330.42秒，总349.402秒 |
| mypy / 架构 / 静态断言 | 334源文件通过 / 334模块0违例、2既有例外 / 277文件0违例 |
| `python -m medops.evals.isolation --self-check` | 退出0，9/9 true，0 model calls，qualification=unknown |
| 文档测试与一致性 | 41 passed；206本地链接/9片段核对，143任务ID保留，0异常 |
| 维护输入与范围核对 | 原704项不变；新增12个Python维护文件；仅18条本轮路径；143任务ID保留 |

70 skip继续是原可选检索B/C依赖范围，不是必需PG/Redis缺失，也不是把本轮失败改成skip。本机完整日志/根目录绑定与提交收据放`.local/audit201/`（不入Git）；公开结果包含基线、命令和失败补救，最终提交/远端CI另按实际SHA核对。文档测试及链接/状态核对已通过并回填机器结果。1 warning来自既有JWT负例测试有意使用短HMAC key，不是本轮生产配置变化。

## 4. 八项强制自审

| 自审项 | 结论 | 依据 |
| --- | --- | --- |
| scope | 通过（本轮范围） | 离线原语与公开合成验证；原有704维护输入不变，未改gold/评分器/模型/阈值 |
| ADR_and_stage | 通过（本轮范围） | D-01/D-02仍pending；S0准备，S2未开始；ARCH-04/11既有证据不冒充新Agent契约 |
| correctness_and_failures | 通过（本轮范围） | 校验model_copy/重复键/绑定、权限、并发、篡改、fsync不确定性与文件权限；发现暴露用途缺陷后修复 |
| permissions_and_data | 通过（本轮范围） | 投影不出gold，拒绝不允许角色；无正文遥测；真实鉴权/封存隔离仍未实现，unknown不自动升级 |
| budget_cancellation_side_effects | 通过（本轮范围） | 无托管模型/业务库写入/部署；只中断自己的失败门禁进程，保留日志；合成临时目录自动清理 |
| traceability_and_versions | 通过（本轮范围） | c2dcdf2基线、内容摘要、外部头CAS与本轮收据可定位；未承诺签名/WORM/原条件回放 |
| verification | 通过（本轮范围） | 71新用例＋旧失败用例定向72通过，完整required门禁通过；保留首次失败/中断及70可选skip |
| status_and_documentation | 通过（本轮范围） | EVAL-33 IN_PROGRESS，PLAN-02 HUMAN，EVAL-32 BLOCKED；文档和待办保持部分范围 |

## 5. 限制、回滚与下一步

当前开发助手仍可读工作区，本轮没有提供账户隔离或封存新题。私有inventory不能公开；hash不是加密、签名或正确标注证明。头回执必须独立保管；与账本一起可任意改写的头不能验证真实性。父目录由可信调用方提供，不是通用路径沙箱；文件锁协调遵守协议的写者。16MiB整链核验适合离线准备，不作长期吞吐承诺；Windows未测。fsync错误、断电与文件丢失按外部头失败关闭，不自动消除未知状态。

没有聚合结果出口白名单/最小切片规则、完整runner与批次揭盲时间门；没有模糊近重复方法或历史暴露扫描；没有独立保管凭据、缓存/日志/telemetry部署泄漏核验。258来源候选资格仍未知；没有新增200题，更没有三轮正式盲测、真实模型质量或独立第二人工证据。

按六批功能边界提交18路径，不纳入`output/pdf`、凭据、本地收据或他人改动；推送完成任务后核对自身SHA的CI。新包未接生产，无迁移，无业务状态改写；回滚对应代码/文档提交即可，不删除保管账本或篡改冻结资料。

下一主切片：EVAL-33聚合出口规则和具体保管部署提案，随后按预登记方法补近重复与历史扫描。PLAN-02仍HUMAN、EVAL-32仍BLOCKED；D-01/D-02要所有者明确裁决，不能将“继续”当新Agent profile批准。所有付费运行仍逐次授权；本轮费用0 USD，自动激活/生产门未变。

实际等待/返修以本轮收据为准（包含首轮552.807秒的失败/中断）；本轮不修改总项目工期，不把检查时间当Agent训练或推理耗时。
