# 记录 126 代码整理目标与验收

日期：2026-10-07。基线：`cb83abd`。用户授权：汇总上一轮审查发现的修复项、goal、约束并开始优化。

范围：本记录覆盖代码整理 G1–G6。BM25、Redis、Langfuse、模型路由与后续建议见[项目完整迭代计划](../ITERATION_PLAN.md)。本维护记录原本地编号 125 与模型路由试跑记录重复，现更正为 126。

本次处理评测可靠性、公共组件重复和模块职责扩张。质量与性能指标沿用既有实验记录；结构整理本身不构成质量提升或发布达标的证据。

## 目标与验收清单

| Goal | 优先级 | 问题和操作 | 验收条件 | 状态 |
| --- | --- | --- | --- | --- |
| G1 历史检索正确性 | P0 | 修复 `Plane.retrieval_for` 的未定义变量；历史日期与候选词法检索器一起传递 | 默认/候选引擎在普通与历史日期下均使用正确工厂、版本和日期；回归测试不调用外部模型 | 已完成 |
| G2 活跃工具质量门禁 | P0 | 把 harness、replay 和运维入口纳入 Ruff；本地与 CI 使用同一范围 | lint、format 检查覆盖活跃入口；未定义变量可被门禁检出 | 已完成 |
| G3 公共运行环境复用 | P1 | 统一固定线程、模型包装器、计量；提取评测 Plane 与安全评测公共逻辑，消除运行脚本互相动态加载；共用检索装配 | 旧 CLI 参数、结果字段、断点续跑和退出码保留；生产入口与评测使用同一检索装配；关键导入与测试通过 | 已完成 |
| G4 回答流程职责拆分 | P1 | 从节点调度提取回答生成、解析、引用与核验流程 | 图边、operation key、拒答、预算、重试、核验和输出保持；既有 Harness/Skill 测试通过 | 已完成 |
| G5 API 路由职责拆分 | P1 | 按问答、任务、观测/回放、管理职责分组；接口协议独立 | 路径、方法、响应、认证、事务、审计、权限及幂等约束保持；API 测试及 schema drift 检查通过 | 已完成 |
| G6 历史聚焦配置整理 | P2 | 分离 evidence focus 的版本参数与执行算法；保留历史版本导入兼容性 | 所有模式输出保持，历史配置不改写；现有聚焦测试通过 | 已完成 |

## 共同约束

1. 保留固定 Harness 图、安全三层检查、证据核验、失败关闭、RLS 身份注入、缓存复查、操作键与审计语义。
2. 保持默认模型、生产 A2 检索器、检索版本、发布策略和实验口径。BM25 仍是显式实验覆盖；历史请求不得悄悄切换实验引擎。
3. 冻结数据集、gold、人工签字、原始实验输出、迁移与锁文件保持原样。历史工具快照不做批量格式化。
4. 所有验证使用本地测试、脚本帮助和静态检查；本次不发起付费模型评测、不修改业务数据库或发布策略。
5. 已有 `output/` 是用户工作区内容，保留原样。改动留在工作区供审查，不自动提交或推送。
6. 按职责提取共享代码，避免增加功能开关或引入新的框架；兼容导入只做薄转发。

## 已确认的错误与成因

`evals/harness/tools/safety_run.py:191` 使用方法作用域中不存在的 `lexical_factory`。Ruff 原始输出：`F821 Undefined name lexical_factory`。Git blame 指向 `99d3161`（2026-10-06）。历史样本 `historical.as_of` 调用该分支时会失败。

构造器已支持候选词法检索器，但历史方法仍直接构造生产词法检索器。修复同时传递候选工厂和历史日期；仅替换变量名不能完整修复。普通与历史装配已收敛为一个方法。

## 各目标的实际改动

### G1 和 G3 检索及评测运行环境

- [harness/assembly.py](../../src/medops/harness/assembly.py)：统一 API、问答冒烟、Skill 冒烟和评测 Plane 的检索装配。`DatedLexicalFactory` 接收 `(conn, *, as_of)`，普通与历史调用均显式传递日期。生产使用固定词法版本；候选引擎由原有 `ProductionRetrieval` 在首次调用捕获版本并继续检查。
- [evals/runtime.py](../../src/medops/evals/runtime.py)：保存共享 Plane、检索调用计数、数据库名称选择和评测超时退出码。构造器与历史查询都调用 `retrieval_for`，保留应用角色的部门事务、只读 admin 查询和索引覆盖预检。
- [evals/safety.py](../../src/medops/evals/safety.py)：承载安全判断、单样本运行、汇总和报告。安全 CLI 与 replay 直接导入此模块。
- [evals/safety_data.py](../../src/medops/evals/safety_data.py)：承载原安全集公共工具；原 `evals/safety_set/tools/common.py` 保留显式转发，人工标注工具的入口保持。
- 五个活跃入口改用已有 `PinnedThread`、`PinnedEmbedding`、`PinnedReranker` 和 `MeteredGateway`。退出码 75 与断点续跑保留；计费字段仍输出 `cost_usd`。固定线程的异常 detail 统一为公共组件的措辞，评测计量开始复用已有的结构化 LLM span，提示词与回答正文不进入 span。
- [test_runtime.py](../../tests/unit/evals/test_runtime.py)：验证普通与历史日期下默认/候选引擎的连续性、两路日期一致、生产版本固定、候选版本捕获模式、部门事务及只读覆盖预检。

活跃 harness/replay 工具中的 `sys.path.insert`、脚本之间的 `spec_from_file_location` 和旧 GPU 包装类均已移除。历史 probe 标注快照、主集人工裁决工具保留原样，不属于这次运行环境迁移范围。

### G2 统一质量检查入口

`Makefile` 的 `CHECK_PATHS` 包含 `src tests migrations evals/harness/tools evals/replay/tools scripts evals/safety_set/tools/common.py`。CI 改为调用 `make PY=python lint format-check`，避免两套路径清单漂移。提取到 `src` 的评测模块同时纳入 mypy。

`chaos_run.py` 因首次纳入格式门禁产生格式变更，其函数主体 AST 对比一致。

### G4 回答流程拆分

- `nodes.py`：节点调度、操作键、执行记录、重试、安全节点与图所需接口。
- [answer.py](../../src/medops/harness/answer.py)：回答提示、模型调用、截断重试、引用映射、拒答、陈述核验与预算结算。
- [dependencies.py](../../src/medops/harness/dependencies.py)：`HarnessDeps` 和默认节点策略。
- [transitions.py](../../src/medops/harness/transitions.py)：共享升级状态构建。

原 `nodes.HarnessDeps`、`nodes.default_specs` 和 `nodes.ANSWER_SYSTEM` 保留转发。固定图文件、默认模型版本与检索版本文件没有改动。

### G5 API 拆分

[app.py](../../src/medops/api/app.py) 保留应用工厂、生命周期、错误处理、trace 中间件和健康检查。业务路由分到 `routes/ask.py`、`routes/tasks.py`、`routes/observability.py`、`routes/admin.py`；环境接口移到 `ports.py`，公共响应映射移到 `responses.py`。原 app 模块的公开导入保留兼容转发。

拆分保留原事务范围、身份验证与注入、管理员角色限制、幂等键、trace 必须落账的规则，以及受限 payload 的独立连接。

### G6 聚焦版本配置

[focus_profiles.py](../../src/medops/harness/focus_profiles.py) 保存 `off`、`compact-v1`、`sentfocus-v1`～`v8` 的原参数与历史说明。[evidence_focus.py](../../src/medops/harness/evidence_focus.py) 保留选句、打分与渲染算法，并转发原配置名称。所有历史参数保留原值。

### 主要文件规模变化

| 文件 | 基线行数 | 当前行数 | 职责归属 |
| --- | ---: | ---: | --- |
| `harness/nodes.py` | 547 | 245 | 回答处理进入独立模块 |
| `api/app.py` | 505 | 111 | 路由、环境协议、响应映射分离 |
| `evals/harness/tools/safety_run.py` | 875 | 298 | 公共运行环境、评分和报告进入包内模块 |

行数包含注释和空行。这些变化主要是职责迁移，整体评价以共享实现、依赖明确和门禁覆盖为准。

## 验证与最终结果

1. 评测运行环境、安全指标、标注工具兼容、replay 续跑与公共固定线程：17 项通过。
2. `pytest -q tests/unit/harness tests/unit/skills`：150 项通过。
3. `pytest -q tests/unit/api tests/unit/faults`：95 项通过。
4. 从修改前保存运行时 OpenAPI 与 5 个 CLI 的 `--help` 输出；修改后逐项相等。独立 schema 导出检查同样通过。
5. 对比基线 AST：23 个提取后的 API 函数主体一致；回答生成、解析、核验、预算、聚焦渲染、安全判断/汇总/报告主体一致。安全 `run_sample` 的计数改为持有本次使用的 `CountingRetrieval`，避免从通用 `RetrievalPort` 接口读取不存在的计数属性。
6. 全量命令：`env -u DEBUG make check`。结果：**1329 passed, 70 skipped, 1 warning**；Ruff lint、372 个文件格式检查、165 个源文件类型检查、包外导入检查与 schema drift 均通过。
7. 跳过项核实：候选 B（zhparser）45 项、候选 C（pg_search）25 项，均因实验服务器不可达。候选 D（pg_textsearch）的 22 项集成测试通过。没有把跳过项记为通过，也没有改动这些实验引擎。
8. `git diff --check` 通过；冻结材料、原始实验输出、迁移、生产模型/检索版本、schema 与锁文件没有改动。数据库测试使用既有临时数据库 fixture，测试后清理；没有运行付费模型 API。

### 验证期间的问题

首次直接执行 `make check` 得到 7 failed、1095 passed、297 skipped。7 项失败的共同原因是宿主进程的 `DEBUG` 环境变量不是合法布尔值，原错误为 `Input should be a valid boolean, unable to interpret input [type=bool_parsing]`。它也使集成测试配置读取失败而增加跳过项。仅对验证进程使用 `env -u DEBUG` 后通过；项目 `.env`、配置校验和宿主环境均未改写。

新提取的安全模块首次进入 mypy 时暴露 `RetrievalPort has no attribute calls`。已通过显式保存本次评测计数器修复，无需扩大生产检索接口或抑制类型错误。

唯一测试警告来自已有 JWT 错误算法用例中的短 HMAC 测试密钥（`InsecureKeyLengthWarning`）；该用例使用构造的无效令牌验证拒绝路径，未改动生产认证配置。

## 后续边界

本次六个目标已完成，改动保留在工作区，尚未提交或推送。若需要验证候选 B/C，恢复其专用实验服务器后再运行对应集成测试。现有 P95、费用、正式发布门禁和人工复核状态沿用此前记录，本次没有重测或重新判定。

今后增加检索开关时统一更新共享装配；增加评测逻辑时放到 `medops.evals`，CLI 保持参数与输出职责；聚焦新版本追加配置并保留旧版本；新的活跃工具路径同步纳入 `CHECK_PATHS`。
