# 代码质量审查：堆砌与洁癖（2026-10-10，只读）

基线：`5a60405` 加工作区文档改动。方法：度量脚本（重复函数体、零引用定义、超长函数、包级依赖环、路径注入计数）加三路只读细读（评测、运行时、测试与脚本）。没有改代码，没有模型调用。审查者为 Claude 及其子代理，不是独立人工。

## 1. 总结论

整体不是堆砌：核心包（contracts、harness、loop、skills、budget、domain）干净、有不变量、文档一致；ruff、mypy 全过，无 TODO、无注释掉的代码、宽泛 except 都带理由。堆砌集中在四处：MCP 入口重写了一遍运行时装配；四个实验词法适配器留在生产包；评测工具脚本靠 sys.path 注入互相引用并大量重写小工具；测试模块被当作夹具库、数据库供给代码复制了 17 份。另有一处安全卫生问题（备份脚本把口令放进 argv）。

## 2. 度量

| 指标 | 值 |
| --- | --- |
| 源码 / 测试 / 评测脚本行数 | 30,937 / 27,212 / 19,356 |
| 重复函数体（规范化 AST，≥6 语句） | 3 组 |
| 零引用公共定义 | 10 个（约 40 行）+ 1 个一行转发 |
| 超过 80 行的函数 | 34 个，最长 282 行 |
| 包级双向依赖 | 7 对；模块级 2 环 3 个 |
| 评测脚本 sys.path 注入 / `noqa: E402` | 46 / 102（77 个脚本中 44 个） |
| `: Any` 注解 | 148 处，api/runtime.py 集中 25 处 |

## 3. 堆砌清单（按处理顺序）

### 3.1 小而确定，零风险

- `tests/unit/api/test_replay_route.py:53-57`、`tests/unit/skills/test_risk_skills.py:229`：`… or True` 使断言永不失败。
- `scripts/db_backup.py:45`、`scripts/db_restore_drill.py:91`：`PGPASSWORD=<值>` 作为 `docker exec -e` 的 argv 传入，`ps` 可见，与脚本自述矛盾。改为 `-e PGPASSWORD` 加子进程 env。
- 死代码：`ingestion/pipeline.py:138 validate_pdf`、`verification/rules.py:167 negation_count`、`retrieval/rerank.py:161 env_flag`、`retrieval/hybrid.py:145 top_k_ids`、`retrieval/doc_focus.py:185 as_sequence`、`retrieval/lexical/index_consumer.py:60,75`、`application/audit.py:245 public_error`、`application/payloads.py:121,125`；`api/runtime.py:113 retrieval_cache_from_settings` 为一行转发。
- 三组同体函数：`application/policy_loader.py:110/120/130`；`retrieval/contracts.py:63` 与 `retrieval/vector/contracts.py:41`；`retrieval/lexical/boundary.py:29` 与 `retrieval/vector/boundary.py:15`。
- `api/routes/admin.py:68-176` 六份相同的 `idempotent(...)` 调用；`loop/gate.py:156-207` cost 与 spend 两段 26 行近似。
- `getattr(settings, name, default)` 重述已声明的设置默认值：`api/runtime.py:279,287,347,451`、`worker/retrieval.py:110-112`；`ApiRuntime` 协议缺 `observation_window`、`allow_drill`。
- 重复字面量：`7 * 24 * 3600` 五处、`120.0` 三处、`== 64` 三处、连接超时参数十余处手写。

### 3.2 装配与分层

- `mcp/serve.py:22-158 _searcher_factory` 复制 `api/runtime.py` 约 95 行（pinned 线程、reranker_for、glossary_for、发布状态缓存、retrieval_version 三份、build_retrieval 参数、translator）；`worker/serve.py` 已正确复用 `ProductionRuntime`。
- 反向依赖：application→api 五个模块（tasks、replay、payloads、audit、admin）；infrastructure→api/application（db/tasks.py、db/audit.py）；application→loop（admin.py:35）；ingestion→evals（pipeline.py:36-37）；loop→evals（gate.py:34）；worker→evals（observability.py:22）；retrieval→ingestion（三个消费者引用 outbox）。模块级环：review_provenance↔validator、integrity↔production、answer↔dependencies（仅类型）。
- `infrastructure/observability.py` 一个模块四种职责（评分 schema、Langfuse 客户端、SQLite 队列、反馈采集）。

### 3.3 实验代码留在生产包

- `retrieval/lexical/{pg_simple_fts,pg_zhparser_fts,pg_search_bm25,pg_textsearch_bm25}.py` 共 1,043 行自述「实验适配器」，仅 `evals/experiments/dec001_run.py` 引用，各带独立 argparse 入口；`pg_textsearch_departmental.py` 与 `pg_textsearch_bm25.py` 约 100 行近似（扩展检查、常量、SEARCH_SQL、_params、_page、_flush）。
- `scripts/benchmark_retrieval_channels.py` 无引用；`audit_focus_candidate.py`、`benchmark_rerank_batches.py` 只被已否决记录引用。

### 3.4 评测工具脚本（堆砌最重）

- 44/77 脚本靠 sys.path 注入互相 import（`import draft_common as dc`、`from common import …`、`from run_rules_arm import summarize`）。
- 运行器启动代码三份：`safety_run.py:236-300`、`smoke_ask.py:222-290`、`replay_run.py:334-365`，`main` 各 258/433/433 行；`_AdminPlane` 借用未绑定方法、`conn_for_user` 被复制。
- 小工具重写：`read_jsonl` 四处（包内已有 `datasets.read_rows`）、`json.dumps+"\n"` 写循环 20 余处（已有 `safety_data.write_jsonl`）、sha256 包装六处、直接 `hashlib.sha256` 52 个文件、`set_config('medops.dept')` 内联七处、代码围栏剥离三份。
- 分叉孪生：`main_set/tools/freeze.py` 与 `probe/precise_clause/tools/freeze.py`；`assemble_successor.py` 两份共享 162 行相同代码。
- 两个巨石：`probe/validator.py` 940 行单类 19 个 `_prNN`；`probe/review_provenance.py:383 _validate` 282 行六层嵌套。

### 3.5 测试

- 测试模块当夹具库：`tests/unit/harness/test_run_ask.py` 被 20 个模块 import，`tests/unit/api/test_ask_route.py` 被 9 个，`tests/integration/test_migrations.py` 被 7 个。
- `tests/integration/lexical_adapter_suite.py:93-114 make_database` 重写 conftest 的供给逻辑，`def db(admin_dsn): yield from make_database(admin_dsn)` 逐字复制 17 份。
- 15 个测试用三种方式动态加载脚本（spec_from_file_location、runpy、sys.path）。
- `test_answer_review.py` 两个 200 行的流程式测试；`fixture_builder_main.py:55` 282 行并重定义已导入的辅助函数。
- 其余良好：288/305 个 `pytest.raises` 带 `match`，无 unittest 风格，无全局状态，70 个跳过全部显式且附补救（候选服务器、Redis）。

## 4. 符合洁癖的部分

标识符与 docstring 英文一致；中文只出现在面向用户的报告与提示串；无 TODO/FIXME；无注释掉的代码；19 处宽泛 except 全部重新抛出或带理由；哈希绑定（datasets、run_conditions）集中实现；预算与账本不变量成文；发布策略键集约束有测试。

## 5. 建议顺序（均不花钱）

1. §3.1 全部：机械修改，半天内可完成，先行。
2. MCP 复用 `ProductionRuntime`；`retrieval_version` 计算收敛为一个函数。
3. 四个实验适配器迁到 `evals/experiments/lexical/`，抽 `pg_textsearch_common`。
4. 评测工具打包进 `medops.evals.tools`，删除全部 sys.path 注入；抽 `bootstrap(args, settings)` 与 `dept_transaction`。
5. 测试夹具迁入 conftest 与 `_fakes.py`；`make_database` 升为 conftest 夹具。
6. 分层（ARCH-08）最后做，与台账顺序一致：先把 api 契约模型下沉到 domain/application，再把 extract/pii/scoring 移出 evals。

本审查不改变任何验收口径；清单可直接并入 CURRENT_TASKS。
