# 记录197：当前代码与架构复核、权限边界修复

2026-10-12。起点 `8361d8d`，工作区干净；项目所有者要求继续前先检查当前代码/架构。主切片 ARCH-16，关联 ARCH-15、INV-AUTH-01/04/05、INV-DATA-03、INV-OBS-03；CODE-03只补显式协议字段，不把完整冗余治理标为完成。实现者/自审者为Codex，同一模型，无子代理或第二独立人工。本轮0托管模型调用、0USD。

## 1. 结论与检查范围

当前结构适合继续以模块化单体推进：HTTP API、异步worker、MCP协议入口分开；bootstrap共用策略、检索、连接与预算装配；Harness约束生成/核验；PostgreSQL保存事实、RLS、任务与费用；Redis只缓存候选/排序；受限加密材料与Langfuse元数据分开。实验适配器和维护评测工具已归入evals包。新的动态Agent可以使用这一底座，但目前主问答仍是固定LangGraph Workflow和五类静态Skill，S2自主行动与S3模型生成候选尚未实现。

**不能以此前CI绿色确认代码完全没有问题。** 本轮实际复现三个权限缺陷，补充16个反例在旧实现全部失败；已修复。当前已声明的工程边界与相关回归通过，仍有CODE-03/06、部署/容量、真实质量、独立复核及盲测缺口，不作通用“优秀架构认证”或生产安全无缺陷承诺。

检查范围：当前提交/台账/ADR约束；三入口装配；最终输出及跨连接事务；管理权限与受限材料读取；共享预算、期限、回执、任务持有权；检索事实回查与缓存边界；观测拆分和静态依赖规则；历史代码质量清单与测试供给。没有部署、激活候选、重跑真实API性能或重新核验全部历史文件/PDF。

## 2. 三个已复现缺陷及修复

| ID / 优先级 | 旧实现的实际行为 | 为什么发生 | 修复 |
| --- | --- | --- | --- |
| AR16-01 / P1 | MCP事实连接设为REPEATABLE READ或SERIALIZABLE；首次读取后撤销ACL，四工具仍能返回旧结果 | 最终栅栏检查app审计连接的隔离级别，事实读取却仍在另一条连接的旧快照中 | 共用`require_current_fact_transaction`要求事实连接处于调用方事务、READ COMMITTED且受ACL/RLS；MCP服务开始和最终输出都检查 |
| AR16-02 / P1 | MCP的readonly配置误用owner/admin LOGIN，ACL已撤销的文档仍被get/verify/list返回 | DSN变量名不保证数据库权限；raw工具没有搜索通道的角色回查，终检在同一越权连接重复读仍可一致 | 工具前及终检都检查实际角色，拒绝superuser/BYPASSRLS/admin-role事实连接；错误留下失败审计，不返回文档 |
| AR16-03 / P1 | 管理员首次鉴权后、admin连接开始前停用主体，仍能读取管理列表或成功grant PV ACL | `_admin_user`事务已关闭，后续用管理连接执行旧UserContext，缺少提交前身份保护 | 管理路由共用`privileged_connection`，在目标事务开始后重新验Bearer/完整身份、同一事实库，并持锁到目标提交；读操作持app共享锁，写操作在实际admin写连接持排他锁 |

修复位置：[数据库边界](../../src/medops/infrastructure/db/final_output.py)、[生产运行时](../../src/medops/bootstrap/runtime.py)、[MCP边界](../../src/medops/mcp/server.py)、[API权限会话](../../src/medops/api/authorization.py)、[管理路由](../../src/medops/api/routes/admin.py)、[观测路由](../../src/medops/api/routes/observability.py)。

排他锁使用migration0026已有key，没有新迁移，也没有在共享业务库执行UPDATE/ALTER ROLE。锁必须在实际写连接持有；如果在另一条app连接持共享锁后让admin写触发器取排他锁，会等待自己的连接。原生回归验证了写连接的触发器重入成功、并发主体撤权被阻塞，提交后正常撤权恢复。

受限payload读取也进入同一身份边界，撤权后不能到达明文reader。metrics读取持共享身份锁。诊断Replay读取原材料时用独立短会话，释放锁后才执行模型；报告提交前再验管理员。没有将全局锁扩展到模型等待。ApiRuntime显式增加`observation_window`/`allow_drill`和权限校验方法，移除路由静默fallback；生产值和原角色/四眼/灰度/批准规则保持。

MCP raw工具仍表示原片段、字段一致性与版本元数据，`verify_citation.fields_match`不等于当前可引用；没有擅自把这类工具改成医学证据质量裁判。来源质量与完整Evidence的七项规则仍由检索/终检执行。

## 3. 反例、返修与实际验证

先在等价隔离工作树重跑起点：required `make check`退出0，2276 passed、70 skipped、1 warning，总162.110秒。基线绿色没有覆盖新增配置/撤权反例。

第一次补充探针：8 failed、8 passed。两处测试供给错误随后修正：

- 用DSN `options`模拟旧快照，但`open_connection`的statement_timeout参数覆盖了该options，实际服务仍是READ COMMITTED，不能据此认定旧快照安全。改为在**一次性测试库的临时LOGIN角色**设置数据库级默认隔离，finally RESET；没有改业务角色。
- 合成documents未设document_key，管理列表/ACL先得到500/404，不能证明撤权后仍成功操作。补合法唯一key后，旧实现两项都实际返回200。

修正后的16反例：四工具×两种旧快照=8，三raw工具×owner/admin=6，管理列表/ACL撤权=2；旧源码**16 failed，退出1，pytest2.90秒/总3.880秒**。失败原文包括：

```text
AssertionError: old fact snapshot passed the final authorization boundary
AssertionError: privileged fact connection exposed a document hidden from the user
AssertionError: revoked administrator retained a privileged operation
assert 200 == 403
```

新回归追加到现有`test_final_output.py`，没有另建一个通过导入测试模块供给夹具的公共库。另加读/写锁持续保护两例、跨库拒绝一例、撤权不能到达明文reader一例，共20新增用例。

准备验证树时一次未等同步结束便启动了定向测试，早到结果209 passed；不能作为新反例已跑的证据，已排除。同步结束后，对全部变更路径核对SHA并顺序重跑；最终定向为**229 passed、1 warning**，pytest16.22秒/总17.294秒，退出0。范围含最终输出、真实MCP服务/加密审计、API/MCP契约、管理数据库服务。

最终required `make check`退出0：**2296 passed、70 skipped、1 warning**，pytest84.83秒/总90.377秒；680文件格式通过，mypy326源文件通过，架构326模块0违例/2既有精确允许边，248测试文件静态断言0违例，四套冻结审计及公开Schema通过。70 skip为既有可选B/C候选；warning为测试短HMAC key，非生产密钥问题。

679维护输入与隔离树一致：开始时全量SHA核对，之后按Git新增/变更/删除逐个同步并核对SHA；完整命令/退出码和结果摘要见[机器证据](2026-10-12-implementation-197-results.json)。未将仅静态扫描或早到209结果作为工程通过依据。

文档自审41 passed、退出0，总2.136秒；151个本地链接全部存在。台账142→143个唯一任务ID，仅新增ARCH-16，无遗漏或重复。冻结数据、迁移、Schema及生产策略tracked diff为空。

## 4. 可维护性与未完成边界

| 类别 | 当前证据/判断 | 后续任务 |
| --- | --- | --- |
| 装配与分层 | 三入口共用bootstrap，协议/评测与生产边界有静态门；无新增允许例外。规则只证明已声明导入方向，不等于所有动态依赖无环或严格Clean Architecture | 保持模块化单体，新增Agent按契约接入，避免复制装配 |
| 追溯 | Ask/Task/MCP保存实际版本、输入、证据、逐调用回执；加密材料可选配置，失败不返回成功 | 原条件恢复与Task/MCP回放仍未交付；无key开发配置仍仅元数据 |
| 冗余 | AST再次找到10个具名零静态引用候选；策略布尔读取、词法/向量边界和部分预算/幂等分支仍相似。零引用不是公共/动态调用不存在的证明 | CODE-03核实入口后删除/归一；本轮只补协议，不整体DONE |
| 测试供给 | 仍大量从`test_*.py`导入fake/seed，数据库供给及脚本加载存在重复 | CODE-06，保留隔离、清理和错误检出能力 |
| 并发与事务 | 模型等待期间原事务保留；输出/管理权限使用短栅栏，普通事实写入被串行化 | IDX-03/DEPLOY-02/PERF-10：部署与真实容量；不据工程回归声明提速 |
| 观测与缓存 | Redis/BM25/Langfuse工程接线有旧轮证据，本轮未替换常驻服务 | 消费者长期驻留、真实混合流量、Langfuse登录后UI目视仍待 |
| 质量可信度 | frozen主/安全集仍provisional；两个unmappable gold仍留分母，开发题不能当未见盲测 | 独立人工、≥200新未见任务、正式质量/安全配对测量，费用逐次授权 |
| Agent与自进化 | 固定主图和静态Skill可复用，尚无结果驱动行动/模型生成候选/实验自动激活全链 | PLAN-02行动/profile与EVAL-32先冻结；S2/S3按ADR-0012推进 |

静态初查遍历src/tests/scripts的584个Python文件（src325个），其中54个src函数超过100行，包含evals维护工具；这只是审查线索。具名零引用列表为validate_pdf、negation_count、env_flag、top_k_ids、as_sequence、sql_tsvector_target、content_target、public_error、snapshot_sizes、kinds_present。没有据此机械删函数或重构所有长函数。

## 5. 八项自审核

| 项目 | 结论 | 证据/限制 |
| --- | --- | --- |
| 需求/范围 | 通过 | 根据当前所有者要求先审查，三已复现权限缺陷优先修复，CODE-03/06不冒充完成 |
| ADR/阶段硬门 | 通过 | 目标/验收未变；PLAN-02、盲测、单次费用和生产签字门保持，未开始S2/S3实现 |
| 正确性/失败 | 通过 | 16旧实现失败→20新增反例通过；正常四工具/管理角色/幂等/灰度回归保留，配置错误失败关闭 |
| 权限/数据 | 通过 | 真实LOGIN角色、旧快照、撤权、同库及锁保持验证；仅一次性测试数据，冻结/gold/共享库不变 |
| 预算/取消/副作用 | 通过 | 0托管调用；短锁不跨模型等待；临时角色设置finally清理，无服务重启/发布 |
| 追溯/版本 | 通过 | 起点SHA、三缺陷、供给错误/重测、命令与结果有记录；实际部署和精确回放未冒充完成 |
| 验证充分性 | 通过（已检查范围） | 229定向、2296/70必需全量、679输入绑定、架构/冻结/Schema通过；不是形式证明/医学质量通过 |
| 状态/文档 | 通过 | ARCH-16工程DONE；台账、输出/装配/MCP契约及README更新；CODE-03/06/人工/付费仍保持真实状态 |

## 6. 交付、回滚及下一步

本轮代码未重启到共享部署，当前常驻服务不一定使用这些检查。回滚源代码可撤回本轮API/连接校验变化，无迁移或业务数据恢复步骤；但会重新引入三个权限漏洞，不应作为常规运行选择。配置旧快照或admin事实DSN的MCP现在拒绝服务，操作方应修正角色/隔离设置，不能以绕过检查恢复。

本轮按功能边界分批提交，最终推送/CI以其实际SHA核对；基线8361d8d的远端CI38193674785此前29步成功，不能用于证明本轮新改动远端通过。未纳入output/pdf、凭据或私有验证产物。

下一CODE-03，然后CODE-06。上线前仍需IDX-03/DEPLOY-02及相应真实门禁；进入Agent前仍需PLAN-02相关契约裁决。此轮无需新增产品/医学裁决，未申请付费运行。

分批代码提交：`7e4717b`数据库/运行时/MCP，3个路径；`8908931`API权限会话/协议/路由及20新增回归，6个路径。第三批同步七个文档/机器证据。每批明确路径暂存并检查cached diff，推送只在全部批次完成后进行。
