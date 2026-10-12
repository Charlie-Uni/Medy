# 测试辅助模块与数据库所有权

2026-10-12，CODE-06。[记录199](reviews/2026-10-12-implementation-199-test-fixture-boundaries.md)及[机器证据](reviews/2026-10-12-implementation-199-results.json)记录迁移、失败与复测。此约定维护测试工程边界，不改变医学评分、正式质量或生产门禁。

## 1. 依赖方向

测试用例与诊断脚本导入 `tests.support` 中的假适配器、合成样例和构造函数；不能把 `test_*.py` 当共享库。辅助模块不包含被收集的测试，不导入 `conftest`。按职责划分 harness、API/MCP runtime、model_gateway、任务、各类 Skill、文档与冻结数据；通用身份、基础证据及词法合约也放在这里。模块间的引用显式声明，不设集中重导出壳。

正常 Python 导入替代按文件路径动态载入脚本。本轮最后一处测试加载器改成 `from scripts import demo`，不运行 demo main，也不产生模型调用；demo 原 CLI 行为仍保留。历史评测工具的原命令兼容与包内规范入口继续遵守 [工具约定](EVALUATION_TOOLING.md)。

静态边界测试禁止收集模块相互导入、测试中的 filename loader/runpy/path 注入以及 support 反向导入 conftest。它检查已登记的静态形式，不能证明任意非字面动态插件行为。

## 2. 数据库供给与作用域

`tests.support.database` 管理迁移、一次性数据库及 LOGIN 用户；`tests.integration.conftest` 决定公共 pytest 作用域和必需服务判定。

| 入口 | 作用域/用途 |
| --- | --- |
| `fresh_database` / `migrated` / `login_users` | session；保留迁移/RLS测试原来的一库与用户关系 |
| `scratch_database` | function；迁移往返测试逐题独立 |
| 公共 `db` | module；每个请求它的测试模块独立数据库，不因供给实现共用而跨模块共享 |
| `db = database_fixture("admin_dsn", scope="function")` | 任务审计及持久任务队列逐题独立；任务不能随意删除，前题残留不能影响后题领取 |
| `database_fixture("server")` | module；可选候选的 server 仍由原 fixture 提供，B与B2、A与A2分别声明，得到不同资源 |
| `make_database(admin_dsn)` | 兼容诊断工具的 generator；`yield from` 或 `contextlib.closing`管理生命周期，不能只next后丢弃未关闭的生成器 |

22处旧数据库夹具逐项核对，20处module、2处function不变；模块DB只按相同作用域归一。实验B/C缺失仍是70个明确可选skip；原生PostgreSQL/Redis在CI或required模式缺失时失败，不因本轮整理变成静默跳过。

## 3. 创建与清理

一次性数据库用随机名，数据库名/角色名在本题拥有的范围内管理；迁移先完成，再创建五个最低权限LOGIN，所有测试DSN留在私有运行环境，不打印。

数据库外层context覆盖迁移、用户供给及用例正文。用户层在provision/连接信息构造前登记finally，终止相关LOGIN连接并删除该前缀角色；外层数据库finally即使角色清理抛错仍会执行。角色前缀扩为12个UUID十六进制字符，减小并行运行的名字碰撞概率。角色权限来自原生产provision函数，原五组及RLS没有变化。

原生测试覆盖迁移失败、事务内用户创建后失败、用户提交后DSN构造失败、用例正文失败、持有未关闭LOGIN、两个同时存活的数据库及角色组、角色清理失败后的外层数据库清理。只有角色清理被故意破坏的用例由测试finally手动收尾，不掩盖真实故障。

清理检查只查询本题实际创建的名字，不用整个PostgreSQL集群前后集合做等式：后者会把并行测试的正常创建/清理误报为残留。基础设施无法连接或DROP失败时错误仍传播，本轮不承诺服务器不可用时强制清理成功；排障时只能处理有所有权记录的临时资源。

## 4. 修改时的核验

1. 共享构造函数迁移核对AST、参数、常量与Schema，内部导入路径变化单列；原test正文的断言/参数/装饰器不改。
2. 比较pytest收集ID，原用例不能因改路径消失，新增用例单独列明；辅助文件不计为测试案例。
3. 逐项比较作用域，不把相同 `yield from` 当作相同生命周期。
4. 原生PG正常与失败路径、任务审计/队列和相关入口回归，运行required `make check`。测试耗时不代表API性能或质量提升。
5. 整理与自审记录绑定最终源码SHA、实际退出码、所有中间失败/中断及已知限制；自审不等于第二独立人工。
