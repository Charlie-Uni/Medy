# 记录199：测试库边界、数据库供给与失败清理

2026-10-12。主任务CODE-06，起点`230039a5671c54349a200cdb3493d1ca412b5d77`（远端CI38201578854已成功）。实现者/自审者为Codex，同一模型，无子代理、第二独立人工或托管调用；费用0USD。本轮工程自审通过，详见[机器证据](2026-10-12-implementation-199-results.json)与[测试辅助契约](../TEST_SUPPORT.md)。未重启/替换共享部署。

## 1. 范围与交付

CODE-06要求解决测试文件被当公共库、重复数据库供给和脚本动态加载，同时保持隔离、清理、原用例及错误检出。本轮不按长度机械拆测试，不改原测试断言来配合重构。

- 20个原测试模块的共享构造内容迁至按职责命名的`tests.support`；79个顶层定义/常量AST不变。原收集模块只消费这些构造，不再互相导入。
- 三个已有基础辅助文件（证据/身份/词法合约）整文件字节相同迁入support；CI的`container_dsn`另有AST一致证明。support共25个文件（含包入口），没有测试案例或集中转发壳。
- 共享迁移/临时数据库/LOGIN生命周期归入`tests.support.database`；conftest仍负责服务发现、required失败和作用域。22处旧DB夹具逐项核对：20处module、2处function保持。15个常规模块使用公共module db，A2/B/B2/C/D等显式变体用工厂，各获得不同资源；两个任务模块用明确function供给。
- 最后一处测试filename loader改成正常`from scripts import demo`，不运行main，不产生费用；demo原CLI保留。CI容器门、诊断脚本也改用规范辅助路径。
- 修复原fixture初始化失败时清理尚未生效的问题；新增7个原生PG生命周期/隔离用例与2个静态边界用例。

所有变更仅在tests、一个CI容器测试及文档。`src`、迁移、Schema、冻结资料、query/gold、评分器/门禁/模型与生产策略不变。本轮不是业务Agent或自进化实现。

## 2. 实际缺陷、复现及修复

原`lexical_adapter_suite.make_database`在进入yield的try/finally前完成数据库创建、迁移、用户provision提交和用户DSN拼装。如果中间抛错，角色删除代码没有生效；嵌套生成器可能依赖GC才回收数据库。

直接从230039a读取旧函数并在一次性原生PostgreSQL资源复现：用户提交后让`user_dsn`抛`RuntimeError`，**5个LOGIN角色残留，保留异常堆栈时1个测试库仍存活**。探针随后显式关闭该旧生成器并删它拥有的角色，前后资源集合一致。没有改共享业务库或留残留。

新外层`temporary_database` context覆盖迁移、provision、DSN构造及用例正文；用户层finally在provision前生效。退出先终止本组LOGIN/删角色，外层即使角色清理抛错仍执行DROP DATABASE。角色前缀从6位随机十六进制扩至12位UUID十六进制，减少并行名称碰撞；角色与权限仍由原production provision函数定义。

原生新增用例覆盖：两个并存库的行/角色隔离、未关闭LOGIN回收；migration/provision/DSN/body四种失败；角色清理失败仍删除外层数据库（测试自行finally清理故意保留的角色）；默认与显式变体供给数据库不共用。服务器本身无法连接/DROP失败仍传播错误，不宣称在基础设施不可用时也一定清理成功。

## 3. 本轮错误及补救（均保留原日志）

| 过程 | 错误/问题 | 原因与补救 |
| --- | --- | --- |
| 私有迁移脚本 | `ValueError: max() arg is an empty sequence` | 原fixture-only文件没有import，插入点算法遗漏；加无import默认位置，异常前未写原项目 |
| DB扫描脚本 | `AssertionError`，遇到`db_a2` | 相同yield有不同fixture名；保留变体为独立供给，不机械当普通db删除；已写的外部准备文件核对后续跑，未据半成品验收 |
| 导入整理 | `E402`、`F821 Undefined name database_fixture` | A2文件有后置import，最初定位按多行import文本找不到已格式化单行；改为明确顶部import，ruff复测通过 |
| 收集/定向初次 | `ModuleNotFoundError: tests.unit.api._auth_fixtures`，退出2 | 首次扫描只覆盖tests，漏掉deploy/ci容器门；补CI的身份/文档/容器DSN入口，正常收集2392个用例 |
| AST对照初次 | 4个test正文报不同 | 是函数内导入路径、拆分与排序变化；对照器只规范这类连续import块，不删除断言/常量/参数，最终564个原test正文相同 |
| 首次全量 | `assert 12 == 0`；1 failed、2321 passed、70 skipped | 本轮错误地把task_audit原function供给合并为module，前题留下12条payload。恢复function，并把另一个原先已保留逐题作用域的tasks_store也改为明确同作用域工厂；22处作用域逐项比对无差异 |
| 作用域修复时 | `F811 Redefinition of unused db` | tasks_store旧fixture还有说明docstring，不符合最初“单yield”扫描条件，添加工厂时留下了旧定义；删旧重复定义，保留逐题隔离说明，再lint/复测 |
| 并行PG复测 | 6个新清理用例误报；17 passed | 新测试比较全cluster临时对象集合，两套并行测试的正常创建/清理互相干扰。改为记录本题生成的数据库/角色名，只查询这些对象；最终故意同时跑定向23项与全量，两者均成功 |
| 中间全量 | pytest SIGINT，退出2 | 并行全量已出现上述误报，停止本轮自己的pytest（PID33684）并等待fixture清理，日志不作通过证据。最终重新同步SHA后完整跑门禁 |
| 本地Git状态 | 全局status长时间无输出 | iCloud原树扫描阻塞；只终止本轮的只读status进程PID9822，其他应用Git进程未触碰。以明确116个路径与起点Git内容逐个核对后复制/验证，没有声称原树全局status成功 |

第一次全量exit2/120.756秒，pytest92.31秒。并行误报的中间全量exit2/79.671秒且被中断，不是完整接受结果。初次收集/探针问题不计产品缺陷；唯一旧fixture缺陷与本轮作用域回归分别说明。

## 4. 最终验证

- 原收集**2383**个ID全部保留，新增9个，共**2392**；无丢失/重复。删除的fixture-only文件原来没有案例。
- 79个共享定义AST一致、三文件原字节一致、container_dsn AST一致；564个原test正文在仅规范导入路径/连续import次序后相同。断言、测试输入、parametrize及测试装饰器未改变。
- 22处旧fixture作用域一致，20module/2function；共享实现不等于共享数据。原可选候选跳过规则不变。
- 初步相关定向：**2080 passed**，pytest72.45秒/总73.711秒；最终作用域与清理复测**23 passed**，pytest13.46秒/总14.452秒，与最终全量在同一PG集群同时运行成功。
- required `make check` **退出0，2322 passed、70 skipped、1 warning**；pytest101.41秒/总105.684秒。705文件格式通过，mypy327源文件通过，架构327模块0违例/2原精确例外，272测试/辅助文件断言门0违例，四冻结数据审计与公开Schema通过。
- 70skip仍是可选B/C实验；warning是原错误算法认证样例的短HMAC。2个unmappable gold仍作miss，provisional独立人工/旧安全回放/无盲测警告仍保留。测试时间不是问答时延或性能改善证明。
- 704维护输入绑定：继承记录198的681路径与230039a干净提交快照，再加27新文件/删4旧文件。原项目116明确路径先与起点Git内容核对再同步；112现存文件SHA相同、4删除一致。没有重新读所有历史PDF/JSON，也未依赖未完成的原树全局status。

命令：required环境中`make check`；`pytest -q tests/unit tests/integration/test_database_fixtures.py tests/integration/test_lexical_pg_simple_fts.py tests/integration/test_lexical_production.py tests/integration/test_retrieval_integrity.py tests/integration/test_final_output.py tests/integration/test_rls.py`；修复后`pytest -q tests/integration/test_task_audit.py tests/integration/test_tasks_store.py tests/integration/test_database_fixtures.py tests/unit/evals/test_fixture_boundaries.py`。原生PG/Redis必须可用，不打印真实DSN。私有日志/矩阵/原探针位于`.local/audit199/`，不入Git。

文档自审：41 passed、退出0、总3.133秒；143个原任务ID均保留，无重复/新增/遗漏，129个本地链接存在。第一次私有ID正则漏掉4个BM25前缀，改为允许数字的任务前缀后重验；不将错误的139计数当任务删减。一次内联文档脚本报Non-UTF-8 SyntaxError，解析期未写文件；改用明确UTF-8脚本后应用状态，并重验内容。

## 5. 八项工程自审核

| 项目 | 结论 | 依据及边界 |
| --- | --- | --- |
| 需求/范围 | 通过 | CODE-06三项边界及正常/失败/并行隔离；不机械拆所有长测试 |
| ADR/阶段 | 通过 | PLAN-02/EVAL-32人工契约、S2入口、盲测、实验激活/生产签字保持 |
| 正确性/失败 | 通过 | 旧5角色/1库反例、原断言检出scope回归；修复后22scope一致、23原生/边界复测及全量通过 |
| 权限/数据 | 通过 | 原provision/RLS/五组权限不改，所有写入一次性库；无冻结/gold/策略/共享业务数据变更 |
| 预算/取消/副作用 | 通过 | 0托管调用/0USD；测试清理、故意失败、SIGINT后等待回收；无部署/发布，预算实现未改 |
| 追溯/版本 | 通过 | 起点、704输入/116路径绑定、旧函数与收集/AST/scope对照、全部中间失败留证 |
| 验证充分性 | 通过（本轮工程范围） | 2080初步定向、23最终并行复测、required全量2322/70；不替代医学/容量/独立人工 |
| 状态/文档 | 通过 | 契约、台账、README及机器证据同步，任务编号/链接另行文档自审；新SHA的CI单独回查 |

## 6. 提交、回滚与下一步

按依赖分七批：基础数据/模型支持、Harness/API/任务支持、Skill支持、数据库/生产seed支持、全部旧消费者的路径与fixture迁移、新原生与静态回归、文档与机器证据。新辅助先于消费者提交；迁移消费者/删旧辅助作为一组，避免中间提交引用已删路径。每批明确暂存、内容与diff核对，最后推送并等待自身SHA的CI，不使用旧230039a绿色作为新版本证明。

全部仅测试/CI工具与文档，可按批次revert恢复，没有迁移或业务数据恢复。恢复旧fixture也会恢复初始化失败缺陷，不能将测试整理撤回扩大为原安全功能回退。

CODE-01～07均已完成相应工程范围。下一主项回到S0的PLAN-02行动/预算/验收决策材料及EVAL-33三方隔离准备；业务Agent未开始，不能把“继续”理解为批准尚未明确的运行profile/阈值或托管费用。FOCUS-02、SESSION/HANDOFF、消费者长期部署、正式质量/容量及盲测继续保留。不把代码质量改善宣称为Agent/自进化已完成。


The six code/test batches are committed: b7a55d3 (foundation), 11b57ad (runtime), d8d8adc (skills), c3e623f (database), 1fc5672 (consumers), 33c13f9 (regressions). The seventh batch contains the five reviewed documents; its actual SHA and remote CI are checked after commit. Final documentation tests: 41 passed, total 2.385 seconds.
