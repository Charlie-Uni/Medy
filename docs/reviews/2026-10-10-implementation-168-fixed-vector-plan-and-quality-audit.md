# 实现记录 168：固定向量计划、真实连接基线与质量自审

日期：2026-10-10。承接[记录 167](2026-10-09-implementation-167-channel-overlap-and-vector-plan-drift.md)，对应 VEC-01、PERF-01C。外部模型调用 0，API 费用 0；本轮实际执行本地 BGE-M3/MPS 推理，不能称“没有模型运行”。

## 1. 为什么先修复计划漂移

记录 167 在顺序执行时也发现 Top-20 向量集合变化，排除了“只是并发不安全”的解释。同一嵌入输入固定时，配置了 HNSW 索引的向量语句仍可能在不同执行计划下给出不同候选。若实验连接预热后进入通用计划，而 API 的新连接仍走定制计划，实验与实际请求可能使用不同的候选规则。

因此不能只测平均耗时，也不能让连接执行次数悄悄改变检索语义。此修复固定生产向量语句的计划策略，并把该策略写进版本。计划稳定不保证任意数据规模下的近似检索都等于精确扫描；文档、统计、DDL 或模型变化后仍须复测。

PostgreSQL 的 `auto` 模式比较定制和通用计划成本，并不保证一定切换；psycopg 的预备阈值是另一层机制。依据：[PostgreSQL 17 PREPARE](https://www.postgresql.org/docs/17/sql-prepare.html)、[psycopg 预备语句](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html)。

## 2. 实现、版本与边界

### 2.1 查询计划

`PgVectorRetriever` 支持三个显式模式：

| 模式 | 向量 retriever version | 用途 |
| --- | --- | --- |
| `auto` | `pgvector-hnsw-cosine-v1` | 保留旧实验默认行为 |
| `force_custom_plan` | `pgvector-hnsw-cosine-custom-plan-v1` | 每次按参数规划；本轮最终生产工厂选择 |
| `force_generic_plan` | `pgvector-hnsw-cosine-generic-plan-v2` | 已完成质量对照但否决为生产默认值的候选 |

强制模式读取原来的 `plan_cache_mode`，在当前事务局部设置目标模式，以 `prepare=True` 执行向量语句，然后恢复原模式。没有改服务器或数据库的全局设置，也没有把普通角色换成管理员。SQL 失败时事务进入失败状态，由事务回滚恢复局部设置。

保持原有向量、余弦、HNSW 参数、候选 K、精确合格数、页面不足失败关闭、ACL、状态、时间窗、历史版本与指定文档过滤。Embedding 模型与索引语义没有改变，无需重嵌入或迁移。

### 2.2 实际缓存语句的计划诊断

普通 MA 角色、K=20、相同过滤条件下，用已有索引中的一个向量作为固定输入，读取实际预备语句名称，以安全的标识符/字面量构造 `EXPLAIN EXECUTE`。这次没有重新生成 query embedding，向量输入与 Recall 测量分开记录，不进入质量分母。产物：[cached search plans](../../evals/experiments/vector/plan-cache-2026-10-10/cached_search_plans.json)。

实际执行计数为 custom `0 generic / 1 custom`、generic `1 generic / 0 custom`。当前 custom 计划使用 `chunk_embeddings_hnsw_cosine`；generic 计划按可见文档/chunk、向量主键路径取出数据后执行 `Sort`，没有走 HNSW。它在此条件下是排序扫描。这解释了早期少量固定向量诊断为何与精确 Top-20 重合；不能据此称 HNSW 已经被调成完全精确。

规划模式进入版本，但 PostgreSQL 仍会根据统计、DDL 和参数类型重新选择物理计划。当前语料上使用排序扫描的成本必须报告，语料扩大后要重新测量；若全量向量比较成为瓶颈，应另行评估有明确召回/一致性规则的 ANN 查询形态，不能继续套用本轮时延。

### 2.3 组合版本

此前组合版本未单独包含向量检索器语义。这次加入可选 `vector_retriever_version`，仅在提供时进入规范化哈希；未提供的历史八成员版本保持原字节结果。

原基础生产组合版本是 `19c755df9adf44e8df9badba547f9b0f21391edbf8f3ab3631f5ea0256b3e4d1`。最初通用计划的工作区装配得到 `3f4f57fad62a6c9c7f2bff6b40bc07f397ca0844f4466994ba2ad6fb1b30fb6a`，但在 §5 自审后撤回该默认选择，未单独推送。最终固定定制计划的基础生产组合版本为：

```text
5ae70f4f59559cf3126af16de7219ed73d5a5f093cd50f1c0fe4383c877d28d9
```

缓存与回放使用新组合版本，旧缓存不会冒充新规则结果。已启动进程须重启才加载新代码；缓存失效消费者的职责没有改变。若回退，应恢复生产工厂的 `auto` 及相应组合输入/固定哈希，通过版本测试后重启；不能只改 GUC 却保留新版本标识。

发布策略中的翻译、文档聚焦、改写等参数还会进入实际运行的组合版本；上述固定值是默认输入的基础版本，不代表所有发布策略使用同一个哈希。

最初实现提交：`3214733`；评测输入预检、定制计划对照与原始排名留证：`9818ca2`；最终生产选择 custom：`7e447b8`。记录/产物另批提交；正式 manifest 绑定实际执行时的源码提交，不把旧 generic 实验标成最终生产运行。

## 3. 固定计划后的通道基准

与记录 167 相同的 8 道问题、10 轮、每臂 80 次，普通 MA 身份、真实 BM25 与本地向量。下表为临时 generic 装配，产物保留原文件名：[通道 JSON](2026-10-10-implementation-168-production-generic-plan-channel-benchmark.json)。最终 custom 的装配另行验证。

| 指标 | 顺序 | 双连接并行 |
| --- | ---: | ---: |
| 中位耗时 | 127.87 ms | 121.81 ms |
| P95 | 146.18 ms | 137.64 ms |
| 词法顺序/集合变化 | 0/76 | 0/76 |
| 向量顺序/集合变化 | 0/76 | 0/76 |
| 向量最小 Top-20 交集 | 20/20 | 20/20 |

固定计划消除了这批重复查询的排名漂移。并行中位收益仍只有 6.06 ms（4.7%），且预开连接已经省掉额外建连成本。因此 PERF-01C 完成评估但不实施双连接并行；重排服务/动态批处理另列 PERF-01D。

## 4. 冻结探针：复现性对照

探针 v4，107 题，dataset hash `1427274ecd04ab6193e572ad1633cfa3bd897520315af52c40fd93e792492286`。映射从主集 v5 的已冻结映射按相同 gold ID 确定性抽取，107 mapped、0 unmappable；映射 hash `12b826a929bb663c31d2f8aa8c3430ca5e63a06e6540d36e0aded04ee09c549e`。

固定 `as_of=2026-10-09`、K=20、seed=20261010、1 次完整预热及 2 次完整测量、并发 1、BGE-M3/MPS。两个 run 的 git HEAD 为 `3214733`。

| 指标 | 旧 auto | 固定 generic |
| --- | ---: | ---: |
| 全集 strict macro Recall@20 | 65.42%（70/107） | 65.42%（70/107） |
| 语言一致，75 题 | 68.00% | 68.00% |
| 跨语言，32 题 | 59.38% | 59.38% |
| 不可复现题 | 1：`pc-0062` | 0 |
| 越权 / 页面耗尽 / 零结果 | 0 / 0 / 0 | 0 / 0 / 0 |
| 测量次数 | 214 | 214 |
| 含嵌入 P95 | 342.45 ms | 332.88 ms |

每题 Recall 和 gold 名次相同，`pc-0062` 的 gold 仍在第 2 位，变化发生在其他候选。产物：[auto run](../../evals/experiments/vector/runs/2026-10-10-pgvector-auto-plan-v1/report.md)、[generic run](../../evals/experiments/vector/runs/2026-10-10-pgvector-generic-plan-v2/report.md)。这两个旧 runner 产物没有完整原始排名文件，其复现统计来自当时执行结果；后续 runner 已增加排名留证。

**自审发现的不足：** runner 复用一个连接，预热后 auto 可能已使用通用计划；API 则每次建立新连接。这项对照支持固定计划的重复性，但不能单独证明实际 API 的质量变化。因此追加主集的强制定制计划对照。此处不是完整 BM25+向量+翻译+重排，也没有生成答案。

本轮曾有临时诊断得到 generic P95 439.48 ms，而上表为 332.88 ms；两个独立时段没有足够控制条件，不能宣称固定计划带来稳定的性能改善或退化。

## 5. 主集连接语义对照

执行前登记：[main comparison plan](../../evals/experiments/vector/plan-cache-2026-10-10/main_comparison_plan.json)。主集 `main-v5-provisional` 615 题中，554 题有 gold、61 题没有 gold；纯向量 Recall 只报告显式 gold 子集，拒答与安全题须在端到端评测中另计。582 个 gold 中 580 mapped、2 unmappable，两个 miss 继续保留在分母。

主集 hash `23bf8530d63f6605b10fb2b1f9d7b3cf5cb805f5d3b20caa16f2fa2e7e5842b0`，代码 `9818ca2`，K=20、相同 as_of/seed、MPS、每臂 1 次完整测量、无预热。强制定制计划模拟新连接按参数规划的规则；它不包含 API 建连、融合、重排、翻译或回答开销。顺序运行两臂，耗时只作诊断。

两臂完成；原始排名、manifest 与结果的哈希一致。产物：[custom run](../../evals/experiments/vector/runs/2026-10-10-main-v5-custom-plan-v1/report.md)、[generic run](../../evals/experiments/vector/runs/2026-10-10-main-v5-generic-plan-v2/report.md)、[逐题对照](../../evals/experiments/vector/plan-cache-2026-10-10/main_comparison_results.json)。

| 指标 | 固定 custom | 固定 generic |
| --- | ---: | ---: |
| 554 题 strict macro Recall@20 | 82.90% | 83.44% |
| 语言一致，341 题 | 85.52% | 85.82% |
| 跨语言，213 题 | 78.70% | 79.64% |
| CO / MA / PV | 80.16% / 83.64% / 84.56% | 80.70% / 83.64% / 85.34% |
| dose_unit，65 题 | 81.54% | 80.00% |
| protocol_id，147 题 | 76.81% | 78.85% |
| 越权 / 零结果 / 页面耗尽 | 0 / 0 / 0 | 0 / 0 / 0 |
| 含嵌入平均耗时 | 145.54 ms | 263.11 ms |
| 含嵌入 P95 | 194.97 ms | 367.42 ms |

Generic 比 custom 多 4 道命中、少 1 道命中，549 道 Recall 不变，总差 +0.54 pp。116 道的候选集合变化，最小 Top-20 交集 5/20；相同 Recall 不能解释成候选逐项等价。

| 题号 | custom → generic | 核对内容 |
| --- | --- | --- |
| ms-0141 | miss → gold 第 7 位 | GVP V/申请人提交风险管理计划与摘要 |
| ms-0320 | miss → gold 第 1 位 | 方案指定任务资格不能仅因州法允许而替换 |
| ms-0321 | miss → gold 第 1 位 | 上题英文孪生，使用同一证据；两项不是两个独立文档案例 |
| pc-0052 | miss → gold 第 5 位 | ICH E2A 不建议沿用 side effect 旧称 |
| ms-0388 | gold 第 19 位 → miss | ICH E15 匿名基因组样本可关联有限临床数据的示例，含年龄范围和胆固醇单位 |

`ms-0388` 不是直接询问给药剂量，但属于既有 `dose_unit` 切片。保留原题、原 gold 和切片；不能重标注来消除这一回归。ANN 命中而排序扫描未命中并不矛盾：近似候选可能漏掉比 gold 更靠前的其他块，使 gold 进入前 20；这只是解释候选差异的可能机制，不能据此判 gold 错误或把 miss 改成成功。

**采用判断：generic 不作为生产默认值。** +0.54 pp 的局部收益伴随有支持量的受保护切片下降，以及本次观察到的平均耗时增加 80.8%（117.58 ms）。此处为单次顺序测量，不宣称是稳定的全系统性能差异；但它不足以支持在当前时延未达标时扩大排序扫描成本。最终固定 custom，让复用连接也沿用当前 API 新连接的按参数规划规则；本轮交付是修复隐式计划切换，不宣称提高主集召回。

三次事实摘要（前检、custom 后、generic 后）完全一致，hash `2760fd817b631e91b3459da78e5f188ebd43e737b1a0d164f0f1fb598102828e`，见[事实记录](../../evals/experiments/vector/plan-cache-2026-10-10/main_comparison_facts.json)。该摘要包含来源、文档、chunk/页锚点、ACL 与语义索引元数据；不重新哈希向量字节或 PostgreSQL 统计。

### 5.1 最终 custom 的重复性与新连接等价性

代码 `7e447b8`、相同 v4/映射/as_of/K/seed、1 次预热 + 2 次测量：107 题重复排名无变化，越权/零结果/耗尽均为 0，测量 214 次。Strict macro Recall@20 **64.49%（69/107）**，语言一致 **68.00%**、跨语言 **56.25%**；平均 **133.43 ms**、P95 **193.74 ms**，见[custom probe run](../../evals/experiments/vector/runs/2026-10-10-pgvector-custom-plan-v1/report.md)。

这比 §4 的预热后 auto 少一个 `pc-0052` 命中，必须如实保留。它反映两个连接语义的差别，不能宣传成“与复用连接旧实验质量相同”。为确认真实新连接的初始规则，进一步逐题比较：每题新建 ordinary-role 连接、默认 `auto` 且只执行一次向量检索；另一臂在同一连接跨题复用最终生产工厂的 `force_custom_plan`。**107/107 的候选顺序与 raw score 完全一致**，新连接臂没有任何已预备的向量语句。源事实前后 hash 均为 `2760fd81…2828e`。产物：[新连接/复用对照](../../evals/experiments/vector/plan-cache-2026-10-10/fresh_auto_vs_reused_custom.json)、[执行前计划](../../evals/experiments/vector/plan-cache-2026-10-10/final_custom_verification_plan.json)。

据此 VEC-01 工程修复通过：已消除自动规划模式切换，并证明本组问题保留新连接的初始候选行为。不能推广为任意统计变化后永不漂移，也不能把这些原始单通道查询当作发布策略下的完整 QA。答案级质量门禁继续 pending。

## 6. 评测失败与补救

先前把全部主集送入仅接受 gold 的旧 runner，全部检索执行后在汇总处失败：

```text
ValueError: a query must have at least one required gold
```

最初排查曾把错误归因于 2 个 unmappable gold；检查评分器后更正：unmappable 会形成空的候选替代组，并正常计 miss；真正原因是 61 道无 gold 题。失败运行没有最终结果，不纳入成绩。

补救：

1. 执行前拒绝含无 gold 的输入，要求显式 `--gold-only` 才能选子集；拒绝空子集与非法测量轮数。
2. Manifest 保存源题数、选中和排除的 sample ID、保留 unmappable miss 的规则。不能悄悄缩小主集分母。
3. 汇总前保存 `rankings.json` 和 SHA-256，留下完整候选序列与逐次耗时；即使评分失败也能检查已完成的检索。
4. 单次测量报告明确写“repeatability was not assessed”，不把不可复现列表为空当成复现成功。
5. `plan_evidence` 标为独立 `EXPLAIN`，不冒充实际缓存语句的 `EXPLAIN EXECUTE`。集成测试通过 `pg_prepared_statements.generic_plans/custom_plans` 验证强制模式真正使用。

## 7. iCloud 环境恢复

记录 167 的临时补下载后，venv 的占位文件再次达到 5,064，pytest 等待 langsmith 导入。此次在 `/Users/leaf/.cache/medy-runtime/venv-py311` 重建运行环境，使用 Python 3.11.16、现有 build/main/embed 三份锁、`--require-hashes` 与无构建隔离安装，再执行 editable 安装及 `pip check`。结果为 `No broken requirements found.`

原 `venv` 改名为 `venv_icloud_backup_20261010` 保留，本地 `venv` 链接到外部环境；两者加入 `.git/info/exclude`，不提交机器路径或环境文件。`make install-check` 在 `/tmp` 中导入项目通过，Makefile 和安装锁没有改。源码和冻结数据仍留在项目内。运行环境离开 iCloud 管理范围能避免该环境被自动变成占位文件，但仓库内源码/Git 对象仍可能受 iCloud 影响，不能宣称仓库层面的故障已永久消除。

## 8. 工程验证与自审

- 最终全量 `env -u DEBUG make check`：1730 passed、70 skipped、1 个既有短 HMAC key warning；Ruff、443 个文件格式、mypy 189 个 source file、评测审计、Schema 检查通过。此前中间版本为 1729 passed，追加 custom 跨身份/过滤回归后再跑最终全量。
- 实测两种强制计划的计数分别为 generic/custom `3/0`、`0/3`，原事务 GUC 恢复。
- 两种强制模式在同一预备连接跨 MA/PV/CO、历史开关与指定文档过滤的集合/计数正确。
- 显式子集测试证明无 gold 题排除留证、unmappable 仍计 miss、原始排名与哈希对应。
- 最终 `make retrieval-check`：ready=true，333 份 active 文档、34,948 个 active chunk，词法/向量缺口均为 0，三个 outbox 消费者 pending/dead letter 均为 0；[readiness 产物](../../evals/experiments/vector/plan-cache-2026-10-10/retrieval_readiness.json)。35,830 是索引 chunk 总数：active 34,948、archived 849、draft 33；draft 仍被状态/RLS 过滤，不能用索引总数冒充当前可检索 active 数。
- 独立人工、未见盲测、新主集答案级质量、安全和真实容量门禁继续 pending；没有用本轮局部指标替代它们。

| 自审项 | 结论 | 证据与限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | VEC-01 的连接复用稳定性；PERF-01C 不实施双连接；未调整验收门槛 |
| 正确性 | 通过 | 107/107 新连接与复用的候选/分数一致；214 次重复测量无排名漂移 |
| 权限与失败关闭 | 通过 | 三部门/历史/doc_ids 回归，真实结果管理员复核无泄漏；页面精确计数仍保留 |
| 质量取舍 | 通过，generic 否决 | 4 gains / 1 loss 与 dose_unit 回归完整留证；生产保留初始 custom 行为，不宣称召回提升 |
| 数据与运行证据 | 通过 | 无 gold 显式排除、unmappable 保留、原始排名哈希、事实摘要一致；单次主集不承担复现结论 |
| 环境与工程检查 | 通过 | 外部锁定 venv、pip check、repo 外导入；最终 1730 passed；源码/Git 的 iCloud 风险仍存在 |
| 阶段验收 | 仍未通过 | 第二人工、未见题、正式答案/安全/容量与受控发布证据仍缺，未借本轮关闭 |

下一项为 PERF-01D：先独立测重排批处理/服务化的吞吐、尾延迟、排序一致性与故障隔离，再决定是否接入；真实容量复测与答案级运行另须按当次范围/费用取得授权。

## 9. 本地复现入口

前置：按现有锁安装本地 embed 依赖，目标为 PG17/0022 的 `medops_v2`，索引已完整，使用 `.env` 的受限应用与管理 DSN；不在命令中打印凭据。下面输出到新目录，runner 拒绝覆盖已有产物。只运行本地 embedding 和数据库，未调用 hosted LLM。

```sh
env -u DEBUG venv/bin/python -m medops.evals.experiments.dec002_run \
  --dataset evals/main_set/main-v5-provisional \
  --mapping evals/experiments/e2e/main-v5-provisional/chunk_mapping.chunker-v2.main-v5-provisional.json \
  --out /tmp/medy-main-custom-reproduction \
  --database medops_v2 --device mps --as-of 2026-10-09 \
  --k 20 --warmup 0 --measured 1 --seed 20261010 \
  --plan-cache-mode force_custom_plan --gold-only \
  --purpose 'VEC-01 main custom reproduction'
```

Generic 臂只换 `--plan-cache-mode force_generic_plan`、新输出目录与 purpose；探针复现改为 `evals/probe/precise_clause/v4` 和本记录目录中的 probe-v4 映射，`--warmup 1 --measured 2`。不要拿不同代码/事实/日期/设备的耗时作直接配对比较。

新连接等价性检查按 `final_custom_verification_plan.json`：加载 107 个冻结 Query 和同一 BGE-M3 provider；每题独立新连接、事务局部注入该题部门、调用默认 auto 检索一次并检查无已预备向量语句；复用连接按题切事务/身份，经 `production_vector_retriever` 检索。对比每个 `(chunk_id, raw_score)`，同时保留前后 `fact_snapshot_from_dsn`。这比较原始向量搜索，没有启动 API、翻译、重排或生成。

## 10. 推送后的 CI 基础设施失败与恢复

五个提交推至 `ca08793` 后，[远端 run 37994091525](https://github.com/Charlie-Uni/Medy/actions/runs/37994091525) 的三次 attempt 均在 `Initialize containers` 失败，checkout、lint、类型和测试尚未执行。前两次错误原文包含：

```text
Get "https://auth.docker.io/token?account=githubactions&scope=repository%3Apgvector%2Fpgvector%3Apull&service=registry.docker.io": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
net/http: request canceled (Client.Timeout exceeded while awaiting headers)
```

这是已观察到的 runner→Docker Hub 鉴权请求失败；[Docker 状态页](https://www.dockerstatus.com/)在核对时没有公布全局故障，不能将它确定归因为全局宕机。重复原配置两次没有恢复。

核对 Google 缓存中的同一 OCI manifest：HTTP 200、响应摘要及实际 1609 字节的 SHA-256 都是原 `ac08538c…2a75d`。按[官方缓存说明](https://docs.cloud.google.com/artifact-registry/docs/pull-cached-dockerhub-images)配置 Docker daemon；缓存未命中时仍会尝试原仓库，缓存驻留也没有永久保证。

Actions 的 `services` 在步骤前初始化，无法在失败前配置 daemon。CI 因此改为 checkout 后的显式启动步骤：保留已有 daemon 设置、追加缓存镜像配置、每张原镜像最多 3 次/每次 120 秒 pull；保持 PostgreSQL 的原固定摘要和 Redis 原 7.2-alpine；仅发布 localhost 端口。两个容器健康后才执行原 pinned pg_textsearch 安装、全部 lint/类型/测试/评测/迁移/Schema 步骤，最后始终清理。依赖不健康即失败，不能借跳过集成测试得到绿灯。没有修改本机 Docker daemon 或中断本机服务。

YAML 解析、启动块 `bash -n` 与镜像 manifest 字节摘要核对通过。真实恢复结果在新 CI 完成后补记；此前远端三次失败仍保留，不能把本地 1730 passed 写成它们已经通过。
