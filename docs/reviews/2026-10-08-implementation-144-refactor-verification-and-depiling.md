# 记录 144：记录 126–142 工作区改动的正确性核验、缺陷修复与去堆砌

日期：2026-10-08，Australia/Sydney。基线：Git `cb83abd` 加工作区内 Codex 于 2026-10-07 23:08 至 2026-10-08 12:02 写入的记录 126–142 改动（未提交）。决策人要求：「确认一下改动的正确性，之前有代码堆砌的情况，另外缺失的部分开始重构」。本记录由 Claude（实现方）完成；核验用的四路只读审查是本实现方的模型子代理，自审仍是实现者自审，不是独立人工审查。没有模型 API 付费调用，费用 0。

核验期间 Codex 仍在同一工作区运行（主集修订复核的付费调用在 12:02 写入 `evals/main_set/drafts/revision-2026-10-08-v2/review/`，由决策人在 Codex 会话中授权）。本记录没有触碰该目录及 `evals/main_set/tools/`、`src/medops/evals/review_budget.py`。

## 1. 核验结论

四路审查分别对照 `git show HEAD:<path>` 与工作区逐段比对（Harness 拆分、API 拆分与就绪检查、评测工具抽取、遥测与 Langfuse 接线）：

| 范围 | 结论 | 证据 |
| --- | --- | --- |
| Harness 拆分（nodes → answer / dependencies / transitions / assembly / focus_profiles） | 搬移代码逐字节一致：`generate_answer` 与 HEAD `answer_body` 的 diff 为空；`ANSWER_SCHEMA`、`ANSWER_SYSTEM`、`_META_ABSTENTION`、`_Meter`、截断重试、别名回映、伪造引用计数、两次 `verify_claims`、预算结算全部不变；`FOCUS_PARAMS` v1–v8 八个版本的参数逐字段一致；`build_retrieval` 传给 `ProductionRetrieval` 的参数与 HEAD 的 `api/runtime.py` 相同；无循环导入 | 子代理 A 报告；`tests/unit/harness` 96 passed |
| API 拆分（app → ports / responses / routes） | 20 条路由全部保留，处理函数为逐行搬移：状态码、响应模型、角色检查、幂等键、事务边界、错误映射不变；`/admin/policies/candidates` 仍先于 `{policy_id}` | 子代理 B 报告 |
| 评测工具抽取（safety_run → medops.evals.safety 等） | 安全门禁指标 AST 级一致：`acl_block_rate` 仍为禁用文档零泄漏口径、`acl_expected_abstention` 单列、各检查名不变；`--baseline-from` 与 `spend` 档完整；冻结数据目录（main-v1/2/3、safety-v2-provisional、replay-v1/2/3、probe）`git diff` 为空 | 子代理 C 报告；`check_safety.py` 170 条 0 问题 |
| 遥测与 Langfuse 接线 | INV-OBS-03 保持：新增属性只有版本号、trace id、观测类型与错误类型；评分载荷白名单、反馈只读 id 与信号；密钥为 `SecretStr`，配置错误不回显输入；HTTP 请求 → harness.run → 节点 → llm.call 的嵌套不变，只有回放按设计成为带 Link 的新根 | 子代理 D 报告 |

结论：记录 126–142 的搬移是行为保持的，评测与安全口径未被改写，冻结数据未动。下面是审查发现的缺陷与堆砌，本记录已处理的部分和留下的部分分列。

## 2. 发现并修复的缺陷

| # | 缺陷 | 严重度 | 修复 | 测试 |
| --- | --- | --- | --- | --- |
| 1 | `ReplayService` 用路由后的版本集执行回放并记录 Trace，但报告的回放侧与 `versions_match` 用的是服务构造时的基础版本集：灰度或发布覆盖下，报告与回放 Trace 行互相矛盾（HEAD 已有，Codex 总结中列为未修） | 高 | [replay.py](../../src/medops/application/replay.py) 两处改用实际运行的 `versions` | `test_replay_reports_the_routed_versions_it_ran_with`（金丝雀版本集下 `versions_match` 为真且两侧版本相同） |
| 2 | 记录 141 把 API 未处理异常的日志改为只记异常类型，500 错误从此无法定位 | 中 | [app.py](../../src/medops/api/app.py) `error_frames`：记录最内层帧的 `文件:行 函数`，不记异常消息（消息可能引用请求正文，记录 141 的理由保留） | `test_unhandled_errors_log_the_frames_but_never_the_message` |
| 3 | 就绪检查的数据库身份用 `inet_server_addr()`+端口哈希，应用 DSN 与管理 DSN 以不同路径（socket 与 TCP、`localhost` 解析为 ::1 与 127.0.0.1）到达同一库时会永久 503 | 中 | [integrity.py](../../src/medops/retrieval/integrity.py) `database_identity` 改为数据库名、数据库 OID、postmaster 启动时间（epoch 整数，与会话时区无关）；重启后最多 5 秒的缓存期内不就绪 | `tests/integration/test_retrieval_integrity.py` 与 `tests/unit/api/test_retrieval_readiness.py` 通过；真实 medops_v2 上 `inspect_retrieval` 38–95 ms，`ready=True` |
| 4 | `safety_run.py --rejudge` 对失效行打印「用 `--only … --resume` 重跑」，而记录 140 已把样本计划绑定进续跑条件，该命令必然被拒 | 低 | 提示改为说明需要新的运行目录 | — |
| 5 | DEPLOY.md 仍写「缺 `DATABASE_ADMIN_URL` 只影响管理路由」，记录 137 起 `/readyz` 也依赖管理连接 | 文档 | DEPLOY.md 进程表补充 | — |

## 3. 去堆砌

记录 126 的拆分把名字留在旧模块里转发（`X as X`），调用方没有迁移，新模块只能经转发层到达；评测工具抽取后又留下 26 个名字的转发壳。本记录把调用方指向规范位置并删除转发层：

| 堆砌 | 处理 |
| --- | --- |
| `evidence_focus.py` 13 个、`nodes.py` 3 个、`app.py` 6 个 `X as X` 转发 | 删除；23 处调用方改为从 `harness.dependencies`、`harness.answer`、`harness.focus_profiles`、`api.responses` 导入 |
| `evals/safety_set/tools/common.py`（26 个名字的转发壳，含私有 `_env`） | 删除；13 个安全集工具与测试直接导入 `medops.evals.safety_data`；Makefile `CHECK_PATHS` 去掉该文件 |
| `safety_run.py` 对 `summarize` / `report_markdown` 的转发；`test_safety_metrics.py` 以文件路径加载脚本 | 测试改为导入包模块 |
| `with_database` 三份（`safety_data` 正则版、`evals/runtime.py`、`dec001_run._with_database`）加 `tests/integration/conftest.py` 一份 | 保留 `safety_data.with_database`（urlsplit 实现）一份 |
| Langfuse URL 校验在 `config.py` 与 `infrastructure/observability.py` 逐字重复 | `config.check_langfuse_base_url` 一份 |
| 就绪检查的「只读 + REPEATABLE READ + 1 秒语句超时」连接块在 `api/runtime.py` 与 `retrieval/production.py` 重复；管理可见性 SQL 在 `integrity.py` 与 `run_conditions.py` 重复；向量元数据字段集在 `integrity.py` 与 `maintenance.py` 重复 | `integrity.inspect_readiness`、`integrity.has_global_view`、`embedding.EMBEDDING_FIELDS` 各一份 |
| `BudgetedGateway(OpenAIModelGateway.from_settings(settings), …)` 在四个评测工具里内联，而 `llm/factory.build_budgeted_gateway` 已存在 | 四处改用工厂 |
| `sha256_file` 三份、`read_jsonl` 三份、`write_jsonl` 两份 | 工具脚本改用 `evals.datasets.sha256_file` / `read_rows` 与 `safety_data.write_jsonl` |
| 死代码：`api.ports.NoDatabase`（HEAD 与工作区均无调用方）、`replay._unused`、`nodes.verdict_counts`（HEAD 即无引用）、`safety_data.app_dsn` 无调用方 | 前三项删除；`app_dsn` 保留（安全集工具文档仍引用，待下一轮清理） |
| `telemetry.py` 冗余条件 `is_valid_trace_id(value) and value is not None` | 简化 |

未动的重复：`answer._Meter` 与 `evals/verifier/tools/run_gateway_arm._Meter`（HEAD 即存在；用 `MeteredGateway` 替代会多出一层 `llm.call` span，不在本轮改）；`infrastructure/observability.py` 的可见性 SQL 多了只读与 loop 角色条件，不是同一判断。

## 4. MRR 补算（非门禁）

简历与原项目描述写有 MRR ≥ 0.80，仓库此前没有任何 MRR 计算。`recall_diag.py` 的行文件已记录每题首个 gold 的名次（`gold_rank_evidence`：重排后 8 条证据内；`gold_rank_candidates`：融合后 20 条候选内），据此零费用补算。定义：MRR = 样本平均的 1 / 首个 gold 名次，名次超出列表记 0；分母为 553 条有 gold 的主集样本，与 Recall@5 相同。

| 运行 | 条件 | Recall@5 | MRR@8（证据） | MRR@20（候选） |
| --- | --- | ---: | ---: | ---: |
| R4 `2026-10-02-recall-main-v3-released-indexed` | released 检索，333 份，翻译开 | 87.16% | **0.7706** | 0.6142 |
| R3 `2026-10-02-recall-main-v3-baseline-indexed` | 基线检索，333 份 | 79.57% | 0.7011 | 0.4761 |
| `2026-10-06-recall-main-v3-a2-notranslate` | A2，翻译关 | 85.71% | 0.7589 | 0.5791 |
| `2026-10-06-recall-main-v3-d-notranslate` | 候选 D，翻译关 | 87.34% | 0.7685 | 0.6199 |

两个口径都低于 0.80；工程基线没有 MRR 门禁，验收报告只登记数字。`recall_diag.py` 自本记录起在 `results.json` 与报告表中输出 `mrr_at_8` / `mrr_at_20`，存档运行的 `results.json` 不改写（上表由同一函数对存档 `rows.jsonl` 重算）。

## 5. 审查登记的行为变化（Codex 有意为之，本记录不改）

- 评测面：候选词法引擎现在对历史日期样本也生效（HEAD 的 `retrieval_for` 对历史日期固定用生产词法，且引用了未定义的 `lexical_factory`，任何 `historical.as_of` 样本都会 NameError；记录 128 修复）。
- `results.json` 的 `total_cost_usd` / `total_model_calls` 改为统计全部尝试（含被覆盖的 system_failure 行），保留行的费用单列 `retained_outcome_cost_usd`（记录 140）。
- `--rejudge` 对带绑定文件的运行一律拒绝；续跑校验全部尝试，重构前的 rows.jsonl 不能续跑，存档运行 F2 不能作为基线复用或回放来源（记录 132、140）。
- `/readyz` 需要 `DATABASE_ADMIN_URL`，且活跃语料缺索引时 503（记录 137）。
- 回放集 v1–v3 的清单没有 `safety_input_format`，在其上运行必须 `--skip-safety`，门禁不能宣告安全完整；需要新的 replay-v4（记录 135）。
- HTTP span 的 `http.route` 改为路由模板，未匹配路径记 `/<unmatched>`；`readyz` 改为同步处理函数。

## 6. 未处理项（留给决策人或下一轮）

后续状态：本节 1–6 的工程项已在[记录 145](2026-10-08-implementation-145-operational-ledgers-and-mcp-parity.md)处理；真实 Langfuse 后端/UI 验收与工作区提交切分仍保留。下列文字是记录 144 完成时的历史状态。

1. **Langfuse 评分队列**：无大小/年龄上限、无最大尝试数、无退避，失败行每轮重发；评分用的 `/api/public/ingestion` 入口已被 Langfuse 标为弃用（记录 142 自述）。后端尚未部署，阶段 3 决定部署清单时一并处理。
   **更正（2026-10-08 下午）**：「`/api/public/ingestion` 已弃用」是本记录沿用记录 142 的错误说法。Langfuse 官方迁移说明与 v4 兼容表写明 `score-create` 事件经 `POST /api/public/ingestion` 在 v4 继续受支持，弃用的是该入口的 trace / observation 事件与旧的同步写入、读取接口；记录 146 已按官方说明登记。队列上限、最大尝试数与退避已由记录 145 补上。
2. **outbox 消费者**：永久失败的事件每轮重取、无死信；失败即停且有 `MedopsOutboxConsumerStale` 告警，属失败关闭，但需要人工介入路径。词法增量消费不更新 `lexical_index_meta`，向量增量每次覆盖 `built_by/built_at`，全量构建的归属在首个事件后丢失。
3. **月度费用账本仍是进程内**（`InMemorySpendLedger`，budget.py 自述「数据库账本随 M3 到来」）：跨进程、崩溃前的费用不可见。可做的方案是一张 `(month, cost_usd)` 表加每次调用一次 upsert，但账本不可用时拒绝调用还是放行是产品决定，未动。
   **状态更新**：记录 145 已实现 PostgreSQL 账本（迁移 0020：预留、结算、失败按保守上限入账），记录 146 补迁移 0021 的应用角色聚合读取函数；本实现方以应用角色在回滚事务内核对 reserve / settle / month_total 可用、账本表直接读取被拒。
4. **MCP 服务**仍直接构造 `ProductionRetrieval`，不带查询翻译与检索缓存：同一问题经 MCP 与经 API 的检索条件不同（HEAD 即如此；MCP 进程没有模型网关，加翻译意味着费用）。
   **状态更新**：记录 145 已让 MCP 经 `build_retrieval` 装配，带缓存与按发布策略的查询翻译（翻译时按需构建计费网关）。
5. `skill_smoke.py` 的确定性 trace id 在新的 trace id 生成器下会把多次重复合并为一条 trace；该脚本目前不配置遥测，属潜在问题。
6. `safety_data.app_dsn` 无调用方；Codex 新建的评测模块中 `read_jsonl` 与更严格的 `datasets.read_rows` 并存。
7. 两个 agent 共用一个未提交的工作区：本记录的改动与记录 126–142 混在同一棵树上，提交归属需要决策人指定。

## 7. 验证

- `env -u DEBUG -u PYTHONPATH make check`（含 `eval-check`）：退出码 0；ruff 与格式通过，mypy 185 个源文件无问题，pytest 1614 passed, 70 skipped（跳过项为不可达的 B/C 实验服务，同记录 131），评测输入审计 PASS 带 5 条既有警告，Schema 无漂移。
- 子集：`tests/unit` 1326 passed；`tests/integration/test_retrieval_integrity.py`、`test_retrieval_maintenance.py`、`test_rls.py`、`test_feedback_export.py`、`test_run_conditions_facts.py` 71 passed。
- 13 个工具脚本（安全集 7、聚焦检查、回放 2、词表、校验器 2）逐个导入通过；`check_safety.py` 170 条 0 问题。
- 真实 medops_v2 上只读 `inspect_retrieval` 三次 95 / 39 / 38 ms，`ready=True`。
- diff 密钥扫描：无 DSN、无密钥。
- 非维护目录（`evals/verifier/tools` 等）里仅被 ruff 改过格式、与本记录无关的六个脚本已从 HEAD 恢复；该目录剩余 9 条 E741/B023 为既有问题，不在 `CHECK_PATHS`。

## 8. 改动清单

源码：`api/{app,ports,runtime}.py`、`api/routes/observability.py`、`application/{replay,policy_loader}.py`、`core/{config,telemetry}.py`、`evals/{runtime,run_conditions,safety_data}.py`、`evals/experiments/{dec001_run,dec002_run,e2e_run}.py`、`harness/{nodes,evidence_focus,dependencies,graph,runtime}.py`、`infrastructure/observability.py`、`retrieval/{integrity,maintenance,production}.py`、`retrieval/vector/embedding.py`、`skills/registry.py`。
测试：`tests/unit/api/{test_ask_route,test_replay_route,test_retrieval_readiness}.py`、`tests/unit/harness/{test_graph,test_evidence_focus,test_run_ask}.py`、`tests/unit/evals/{test_safety_metrics,test_safety_authoring,test_dec001_run,test_replay_baseline_reuse}.py`、`tests/integration/conftest.py`。
工具：`evals/harness/tools/{safety_run,smoke_ask,skill_smoke,focus_check}.py`、`evals/replay/tools/{recall_diag,replay_run,build_replay_set}.py`、`evals/safety_set/tools/*`（`common.py` 删除）、`evals/glossary/tools/build_concepts.py`、`evals/verifier/tools/{run_recheck_cases,run_gateway_arm}.py`、`Makefile`。
文档：本记录、README 入口、验收报告 v3.9（MRR 登记）、DEPLOY.md、ITERATION_STAGES.md。

## 9. 自审

| 自审项 | 结论 |
| --- | --- |
| 需求与范围 | 通过。对应决策人的三点要求：正确性核验（§1）、堆砌（§3）、缺失部分（§2 缺陷、§4 MRR）。没有改任何阈值、分母或默认策略；MRR 明确为非门禁。 |
| 正确性与失败路径 | 通过。三处缺陷各有回归测试；就绪身份改法的失败路径（重启后 ≤5 秒不就绪）已写明；未处理项逐条列在 §6，不以自审替代。 |
| 权限与可追溯性 | 通过。500 日志只记帧位置不记消息；冻结目录与 Codex 正在写入的复核目录未触碰；diff 无密钥。 |
| 验证 | 通过。§7 的 `make check` 退出码 0；子集、导入冒烟与真实库只读检查已通过。 |
| 状态与文档 | 通过。记录 126–142 的改动来源（Codex）、授权与并发情况写明；本记录的核验是模型子代理加实现者自审，不是独立人工；工作区仍未提交。 |
