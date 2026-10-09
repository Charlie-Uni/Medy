# Medy 开发任务、当前进度与边做边学路线

> **最新入口（2026-10-09）**：[完整迭代计划与工程建议](ITERATION_PLAN.md)汇总代码整理、BM25、Redis、Langfuse、模型路由、评测与性能等 18 个目标。生产词法已切换到部门隔离 `pg_textsearch` BM25；PostgreSQL 17、migration 0022、三库逻辑迁移、回滚资产和 CI 接线见[记录 162](reviews/2026-10-09-implementation-162-production-bm25-cutover.md)。主运行配置的 Redis 候选缓存、独立 namespace、常驻失效 worker、按模式 readiness 与故障恢复已完成，真实流量收益仍待付费门禁，见[记录 164](reviews/2026-10-09-implementation-164-redis-cache-cutover.md)。Langfuse v4.54.0 已完成真实后端关联与故障恢复，UI detail 待人工目视；两项小模型路由候选已否决。安全 v2 已冻结，仍需对应版本的正式运行。代码整理见[记录 126](reviews/2026-10-07-implementation-126-code-maintenance.md)。按[十项阶段表](ITERATION_STAGES.md)逐轮自审，阶段 1 尚未通过。这些进展不直接改变下方基线加权进度或最终门禁。
>
> **历史范围提示**：下方早期核查说明、§1 开篇结论及阶段概览保留历史快照，后续任务行逐次追加证据；早期“正在准备实验”“尚未实现”等措辞不能作为今天的状态。当前功能状态与后续行动先看上述总表，正式指标以[验收报告](ACCEPTANCE_REPORT.md)的运行版本为准。

> 核查日期：2026-09-21（[实现记录 49](reviews/2026-09-21-implementation-49-main-set-corpus-ingested.md)；本轮 877 passed，含 243 项 PostgreSQL/Redis 集成测试，其中 B/B2/C 候选服务器上的集成测试仅本地运行）。依据：工作区中的[工程基线 v0.6](ENGINEERING_BASELINE.md)、ADR、SPEC、代码、复核记录与本机测试。历史实现证据见记录 13～48。
> 本文件是基线的执行进度视图，不是第二份需求契约。范围、阈值和安全约束仍以基线为准；不新增 P0 门禁，不代替正式验收。
> Git 归档：`2a4aef6` 为工程基础，`213dbe8` 为冻结探针 v1；归档提交已在独立 checkout 复验。本轮后续实验准备与回填文档单独提交，冻结 v1 原始字节不变。

## 1. 先看结论

目前处于 **M0 基础工程与契约大部分已实现，M1 知识治理与入库已落地，75 条真实探针已冻结归档，正在准备 DEC-001 实验**。领域模型、数据库迁移与 RLS、PDF 入库切分、评测工具已有代码和本地证据；医学问答服务、生产混合检索与 DEC-001 选型实验尚未完成。

本次完整复跑：`env -u DEBUG -u PYTHONPATH make check` 通过，仓库外导入、ruff、109 文件格式检查、mypy 48 个源文件、pytest **549 passed**（485 单元 + 64 集成，无跳过）、Schema 漂移检查均通过。PostgreSQL 集成测试实际连库执行；此前继承的 `DEBUG` 布尔解析问题仍以命令级移除处理。开发库最近核查为迁移 0004、16 份 draft 文档、2,661 个 chunk。75 条探针现为 71 agree、4 disputed_resolved、0 待决；带页文本的正式 frozen 校验零错误、零警告。pc-0046 的公开机构邮箱已按既有人工依据绑定精确例外；模型后端版本未暴露，已明确记录其复现限制。记录 27 已完成 Git 归档，开始实验准备与映射；远端 CI 与检索质量实验尚未完成。

两件事不能混淆：

- 合成的 12 文档 / 72 样本 fixture 验证的是校验器行为，不是实际医学语料质量、许可或召回率。
- `OfflineBM25Index` 是离线参考，`rrf_fuse` 是融合函数；它们不表示生产 BM25、数据库权限过滤或混合检索已经完成。

### 进度百分比口径

决策人要求每个阶段汇报"离总目标百分之多少"。口径固定为：[任务知识对照](TASK_KNOWLEDGE_MAP.md) 中 79 个 P0 任务行的状态加权和（已实现 1、部分 0.5、阻塞与待做 0）除以 79；另报除以 99 个基线复选项的数值。状态只随实现记录的证据变更，基线勾选只依据完整证据更新，最终验收仍是第 11 节九条门禁的二元结果。`tests/unit/docs/test_baseline_roadmap_consistency.py` 重算并比对下面这行数字：

P0 加权进度：80.4%（63.5/79）；按 99 项计 64.1%。分项：M0 10/11、M1 16.5/21、M2 11/16、M3 10.5/13、M4 10/10、M5 5.5/8。

### 状态与计数

下表编号逐项对应基线第 8 节的顺序；`G-xx` 对应第 11 节。后续按编号更新状态和证据，不把一项拆成许多空文件来制造进度。

- **已实现**：该小范围产物已有代码/文档与本地证据，不等于整项生产验收完成。
- **部分**：已有一部分，但表中列出的交付仍有缺口。
- **待做**：尚无对应实现；只在文档里约定不算实现。
- **阻塞**：缺少明确的前置输入或决策；不通过降低门禁解除。
- **选做**：P1/P2，不能反过来拖延 P0。

| 范围 | 基线项数 | 当前定位 |
| --- | ---: | --- |
| M0 工程与契约 | 11 | 基础工程、领域/API/MCP 契约与本地门禁已有；远端 CI、安全阶段及服务接线待补 |
| M1 知识治理与检索 | 21 | 数据库治理、RLS、入库切分和探针冻结归档已有；实验准备已启动，生产检索选型待完成 |
| M2 Harness / Verifier / Safety / Skills | 16 | 固定图、节点契约、operation key 账本、Verifier（ADR-0011 分工）、Safety、Gateway 与预算、Skill Registry 与两个低风险 Skill 已有；安全集与门禁待做 |
| M3 API / worker / MCP / 观测 / 部署 | 13 | 首切片已实现：`/v1/ask` 五种契约、bearer 身份边界与 principal 目录、健康探针、生产运行时；任务/worker/MCP/观测/部署待做 |
| M4 受控 Loop | 10 | 待做 |
| M5 规模与全量验收 | 8 | 运维手册与恢复演练、Skill 测试矩阵、成本门禁零费用部分已有；语料入库 333 份 active（两批 10% 抽样已签字，`main-v5-provisional` 已冻结）；首个真实候选门禁通过并灰度发布；验收报告与演示材料已有；新主集正式评测、成本候选评测和 P95 复测待做 |
| P1/P2 checklist | 11 | 选做，未启动 |
| 最终验收 | 9 | 未验收；是前述工作的汇总门禁，不是 9 个新功能 |

合计 **79 项 P0 阶段任务 + 11 项选做 + 9 项汇总验收 = 99 个基线复选项**。基线当前为 **1 项勾选**（M1-01 探针冻结）；多数复选项是包含多项条件的验收包，尚未满足全部条件时不勾选，也不按代码行数估算完成百分比。基线另有 30 条不变量、11 项 DEC。

## 2. 截止目前已经做了什么

| 编号 | 已有产物 | 证据与完成边界 |
| --- | --- | --- |
| C-01 | 需求来源归档、工程基线、里程碑、自检与验收口径 | [基线](ENGINEERING_BASELINE.md)、[来源校验清单](source/SHA256SUMS)；两份来源哈希本轮通过。冻结的是契约，不是项目成果 |
| C-02 | OIDC 身份边界、词法选型预登记、语料许可政策 | [ADR-0001](adr/ADR-0001-identity-oidc-boundary.md)、[ADR-0002](adr/ADR-0002-lexical-retrieval-selection.md)、[ADR-0003](adr/ADR-0003-corpus-source-license-policy.md)；具体 IdP、生产检索器、准入语料仍未全部确定 |
| C-03 | 探针规范、7 个 JSON Schema、示意样本、18 个 norm-v1 向量 | [SPEC](../evals/probe/precise_clause/SPEC.md)；示例是 draft，正式冻结内容位于 v1 |
| C-04 | 38 条候选的结构化来源与许可证据清单 | [候选 v0.6](../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.6.json)（v0.1～v0.5 逐版承接）；预判 eligible 19，决策人已签字 `eligible` 18（2026-09-12 六条、2026-09-17 十二条），其中 cand-0030/0031 不进入 v1 主体；v1 主体 16 份原件与页文本已就绪 |
| C-05 | canonical JSON、SHA-256、operation key 纯函数及测试 | [canonical.py](../src/medops/core/canonical.py)；实现确定性与分隔符防歧义；[已知答案向量](../tests/unit/core/test_canonical_vectors.py)（10 组 + operation_key，含 NFC/NFD 不归一、三种 PYTHONHASHSEED 子进程复算）固定了字节形式；尚未接入节点、持久化、任务事务与回放 |
| C-06 | norm-v1、jieba/regex tokenizer 原型及专项测试 | [normalization.py](../src/medops/retrieval/lexical/normalization.py)、[tokenizer.py](../src/medops/retrieval/lexical/tokenizer.py)；尚无正式医学词典、数据库索引版本校验；§3.1 的全局词典隔离问题已于实现记录 05 修复并有回归 |
| C-07 | 检索结果 Pydantic 契约、离线 BM25、确定性 RRF | [contracts.py](../src/medops/retrieval/contracts.py)、[bm25_offline.py](../src/medops/retrieval/lexical/bm25_offline.py)、[fusion.py](../src/medops/retrieval/fusion.py)；不是生产检索链路 |
| C-08 | PR-01～PR-14 探针校验器、PII 规则版本、CLI、draft/frozen 行为、页文本抽取工具、草稿 canonical JSONL 重写工具 | [validator.py](../src/medops/evals/probe/validator.py)、[CLI](../src/medops/evals/probe/__main__.py)、[extract.py](../src/medops/evals/probe/extract.py)（pypdf，[ADR-0005](adr/ADR-0005-pdf-extraction-library.md)）、[canonicalize.py](../src/medops/evals/probe/canonicalize.py)（只改表示与顺序、记录集不变、非 draft 与内容问题一律拒绝、全部检查后才写、原子发布、写后重跑 draft 校验）；已具备精确 PII 例外和运行证据绑定，16 份文档、75 条真实样本的带页文本 frozen 全规则校验通过（记录 26） |
| C-09 | 合成数据工厂、单元与回归测试 | [fixture_builder.py](../tests/unit/evals/fixture_builder.py)、[加固回归测试](../tests/unit/evals/test_probe_validator_regressions.py)；全套 549 tests 本地通过（本轮，含 64 项集成） |
| C-10 | Python 包、venv、Makefile、ruff、mypy、pytest、CI 工作流、依赖锁 | [pyproject.toml](../pyproject.toml)、[Makefile](../Makefile)、[CI](../.github/workflows/ci.yml)、`requirements.lock`（带哈希，含构建后端；2026-09-17 新增 dev 依赖 openapi-spec-validator 及 7 个传递包，既有版本未动）；仓库外导入、迁移往返与现有 64 项集成测试通过；远端 CI 与后续服务/安全集成覆盖待补 |
| C-11 | 十类 Pydantic 领域契约与 AgentState | [domain/](../src/medops/domain/)（实现记录 05、07）；契约范围，未接运行时节点 |
| C-13 | 切分器与入库流水线 | [chunker.py](../src/medops/ingestion/chunker.py)、[pipeline.py](../src/medops/ingestion/pipeline.py)、迁移 0003（实现记录 20）：chunker-v1 页锚定切分，入库校验/去重/PII 默认拒绝/审计；本机 16 份文档 2,661 个 chunk 入库，4 份 PII 误报经决策人复核以审计覆盖入库；迁移 0004 增加 draft 专用终态 withdrawn（实现记录 21） |
| C-12 | OpenAPI 3.1 初版 | [openapi.py](../src/medops/api/openapi.py) → [schemas/openapi.json](../schemas/openapi.json)（实现记录 13）：不引入 Web 框架，`components.schemas` 与单文件 Schema 逐模型相等，错误响应由 `HTTP_STATUS` 推导，通过 openapi-spec-validator 与 7 项契约测试，13 种变异文档均被拒绝；成功状态码与 retry 失败码为本轮约定，待审核 |

## 3. 当前缺口与前置事项

### 3.1 本轮确认的实现问题

**分词器实例共享全局词典，影响实验可复现性。** `JiebaTokenizerV1` 使用模块级 `jieba.load_userdict/cut`；实例 B 加载词典后，实例 A 的结果也会改变，但 A 的 `dictionary_version` 不变。本轮在独立进程中复现，证据见复核记录。

处理范围限定为一个小修复：每个实例使用独立 `jieba.Tokenizer`；增加“两个不同词典实例互不影响、默认实例不被污染”的回归测试。修复前不用于正式 DEC-001 对比；不需要修改 norm-v1 或重新设计检索架构。对应 M1-03、M1-15。**状态：已修复**（[实现记录 05](reviews/2026-09-10-implementation-05-contracts-and-fixes.md)，两条回归通过，原复现脚本不再复现）。

### 3.2 语料与探针集

| 项目 | 当前实测/仓库状态 | 后续工作 |
| --- | --- | --- |
| 候选许可状态 | v0.6（2026-09-17）：预判 eligible 19、needs_review 15、research_only 1、rejected 3；签字 `eligible` 18，其中 cand-0030、0031 不进入 v1 主体 | v1 主体 16 份：MA 5、PV 8、CO 3，每部门不少于 3 份已满足；剩余 1 条预判 eligible（cand-0032/0033 之外的 needs_review 不计）留作补充 |
| 部门覆盖 | v1 主体：MA 5（仿單）、PV 8（EMA GVP VI/IX、FDA 申办方安全报告、ICH E2A/E2F、TFDA 通報表指引、MedDRA 两份）、CO 3（ICH E8(R1)、E6(R3)、FDA 方案偏离草案）；16 份 corpus.json 已有，cand-0036 排除，cand-0030/0031 不入主体 | 已满足每部门至少 3 份文档、15 条样本及每份至多 6 条；修改时继续核验 |
| 简体中文 | 已签字 zh-Hans 2（MedDRA 两份考虑要点，共 110 页）；本地冻结 v1 的 zh-Hans gold 10 | 已超过至少 8 条门槛；繁体不计入；Git 归档已完成 |
| TFDA 路径 | 五份许可证仿單（cand-0029、0034、0035、0037、0038）已签字，2026-09-17 export/36、39 快照证据已追加到 v0.5；corpus 已填写 `verified_by=reviewer-01` 和版本线索 | 对应样本已复核并本地冻结；后续版本更新需重新核对来源 |
| 冻结输入 | 18 份原件与 18 组页文本；主体 16 份 draft / 2,661 个 chunk；75 条探针已本地冻结（MA 30、PV 29、CO 16；zh-Hans gold 10），71 agree、4 disputed_resolved、0 待决。样本、复核证据、精确 PII 例外与哈希均已装配 | Git 归档 `213dbe8` 已完成；双哈希与 commit 已回填 ADR-0002，见[实现记录 27](reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md) |

探针集固定条件：至少 60 条、目标 72 条；六类切片各至少 8 条；每部门至少 15 条；至少 10 份文档且每部门至少 3 份；每文档最多 6 条；zh-Hans 至少 8 条。只有获批 `eligible` 的公开 PDF 可进入 spec-v1。公开 PV 指南保持真实文档类型，不能为凑数改称 SOP。

2026-09-20 冻结校验统计：time_window 20、drug_name_zh 18、dose_unit 20、mixed_zh_en 53、negation 41、protocol_id 17。正式 samples.jsonl 已包含真实 review；页内唯一性、span 偏移、部门/版本对应、query 去重及 PR-01～PR-14 frozen 校验均通过。pc-0046 的一处公开机构邮箱例外绑定确切字段内容、位置、来源和人工依据文件哈希；一般 PII 规则不变。完整 span 与运行证据见冻结 v1，Markdown 表中部分长段落仅供阅读。哈希和结构校验不替代语义判断。

草稿 canonical JSONL 重写命令已交付（`make canonicalize-probe DIR=<draft_dir> [PAGES=..] [CHECK=1]`，实现记录 13）：只对 `manifest.status=draft`、无 `frozen_at`、无 `SHA256SUMS` 的目录生效；只改 BOM/换行/空行/键序/转义与记录顺序，记录集不变；重复键、NaN、非对象行、缺 id 或重复 id 一律拒绝且不写任何文件；写后自动重跑 draft 校验，内容问题（如非法 dept）由校验器报告而不被“修正”。它仍是 M1-01 的配套小工具，不是标注平台。

### 3.3 文档/验收边界

- 基线 §1.3 曾把多模态写作 P1，§7.2 和 checklist 写作 P2；已按决策就地更正为 P2（第七轮记录第 8 节），并新增 `tests/unit/docs` 的机械一致性测试。扫描件 OCR 的纯文本抽取仍是 P1，两者不同。
- 本轮验证了当前 `venv/` 的有效导入，没有重做 iCloud 隐藏标志的时序取证；运行成功不能扩写成对所有 macOS、Python 版本和 iCloud 环境的普遍结论。
- 2026-09-17 决策人提供的对外描述修订稿与基线的六处出入见[第八轮审核记录](reviews/2026-09-17-baseline-review-08-description-check-and-mrr-decision.md)：`MRR≥0.80` 不在两份冻结来源与基线中，决策人决定不设（不作门禁、不另报），基线不变；其余五处为对外措辞退化（BM25 写法、"同等质量下"、"线索提取"、人工审批、目标值限定），基线本已按来源原文表述，不需修改。

## 4. P0 全量开发任务

### M0：工程与契约（11 项）

| ID | 状态 | 要做的工作与剩余验收 |
| --- | --- | --- |
| M0-01 | 已实现（结构范围） | `src/tests/migrations/evals/deploy/docs` 均已存在且有内容（`migrations/` 与 `tests/integration/` 随实现记录 17 建立）；保持模块化单体，不预建空目录或拆微服务 |
| M0-02 | 已实现（Codex 已复核；uv/pip 已由 ADR-0004 批准；Redis 7.2 与 digest 已于 2026-09-17 固定） | Python >= 3.11、`requirements.lock` 与 `requirements-build.lock`（带哈希）、固定 pip、无构建隔离安装、`Settings` 与 `.env.example`、`.env` 忽略规则与仓库卫生测试已有（实现记录 08）；本机干净环境安装已实测，远端 CI 未运行，不勾选；记录 39 依赖锁新增 `redis==6.4.0`（MIT）与 `async-timeout==5.0.1`；记录 42/43 新增 `defusedxml==0.7.1`（PSF）与可选 extra `embed` 的独立哈希锁 `requirements-embed.lock`（以主锁为约束） |
| M0-03 | 已实现（本地门禁齐全；远端 CI 首次运行待提交推送） | lint、format-check、typecheck、单元 + 集成测试、Schema 漂移检查与 migration check（单一 head + 空库升降级往返）均在 `make check`/`make migration-check` 与 CI（实现记录 15、17） |
| M0-04 | 部分（单元、集成、契约漂移、迁移、评测 smoke 已配置；安全阶段与首次远端运行待补） | CI 含 PostgreSQL 服务容器与集成测试、Schema 漂移、migration check、探针示例校验（实现记录 17）；安全测试阶段随 M2 安全集加入；镜像扫描仍为 P1 |
| M0-05 | 已实现（核心范围，Codex 两轮反馈已按记录 06 第三版关闭，待复核） | `src/medops/core/{errors,tracing,logging}.py` 与 18 个测试已有（实现记录 06）：业务/基础设施错误分离、detail 不外泄、trace_id contextvars 传播、JSON 脱敏日志；缺 API/worker 接线与观测后端，不勾选 |
| M0-06 | 已实现（函数与已知答案范围；远端多平台 CI 未运行） | canonical_json / operation_key 已有；已知答案向量固定了 10 组输入与 operation_key 的字节形式和 SHA-256，并在三种 `PYTHONHASHSEED` 子进程中复算一致（实现记录 13）；macOS arm64 之外的平台证据待远端 CI。后续节点调用方必须纳入完整版本集合，不只验证哈希函数 |
| M0-07 | 已实现（契约范围；D-01/02/03/05 已复核关闭，D-04 第二版待复核） | `src/medops/domain/` 十类契约与 AgentState（实现记录 05、07）：完整引用比对、不支持要素与高风险意图禁止作答、过期下游结果清空、不可变排名；仍缺与运行时节点的对接和跨平台证据，不勾选 |
| M0-08 | 已实现（契约、Schema 与 OpenAPI 初版；待审核） | `src/medops/api/contracts.py`、`src/medops/mcp/contracts.py`、`schemas/`（15 个 Schema、工具清单与 `openapi.json`，已生成未提交）与 `docs/api/CONTRACTS.md` 已有（实现记录 09、13）；OpenAPI 3.1 初版由同一批模型生成，管理/回放端点随其模型加入；成功状态码 202/201/200、retry 非法状态 `409 task_not_retryable`、保留期 `IDEMPOTENCY_KEY_TTL_SECONDS`（默认 604800 秒、下限 86400 秒）已于 2026-09-17 定稿（实现记录 15）；远端 CI 未运行，不勾选 |
| M0-09 | 已实现（v0.1，Codex 已复核） | `docs/THREAT_MODEL.md`：八条边界数据流、七类风险各对应条款与测试/里程碑；随组件补行 |
| M0-10 | 已实现（探针范围） | 合成工厂已有 12 文档 / 72 样本与页文本；后续随 API、数据库、Harness 扩展 fixture，不预造整套医学业务数据 |
| M0-11 | 部分（基础设施已在本机一条命令启动并验证；对象存储仍未含） | Compose 已切到固定镜像 PostgreSQL 17.11 + pgvector + pg_textsearch 1.5.1，Redis 7.2；API/worker/MCP profile 已有，BM25 数据卷迁移与恢复核对见记录 162；对象存储等 DEC-007 |

领域层先做契约，不绑定 FastAPI、数据库会话或模型 SDK。AgentState 只存可序列化数据；连接、锁、客户端不能塞进 State。声明了字段并不等于权限或状态机已执行。

### M1：知识治理与检索（21 项）

| ID | 状态 | 要做的工作与剩余验收 |
| --- | --- | --- |
| M1-01 | 已实现（冻结与 Git 归档完成） | 16 份语料、75 条样本；71 agree、4 disputed_resolved、0 待决。冻结提交 `213dbe8`、双哈希和复核链已归档，独立 checkout 校验通过；该项基线已勾选（记录 27）；探针 v2（spec-v1.1，107 条含 32 条英文孪生）于 2026-09-20 冻结，`dataset_hash 1fc5089f…0321`（记录 35） |
| M1-02 | 部分（镜像、配置、三服务器映射与运行清单工具已就绪；正式运行清单在文档激活后冻结） | [准备说明](../evals/experiments/lexical/README.md)：B/C 镜像已构建实测（记录 28），三候选适配器与前置查询规则已固定并写入 experiment_plan.json（记录 29、30），三服务器语料一致、各自映射 73 mapped/2 unmappable，`dec001_run` 在查询前写出冻结的 run_manifest.json（记录 31）；端到端参数仍未固定 |
| M1-03 | 契约切片已复核通过（Codex，2026-09-11），整项不勾选 | `LexicalVersions`、`LexicalRetriever` Protocol、`run_lexical_search` 边界与可复用适配器契约测试已有（实现记录 10），离线 BM25 两种分词器通过；候选 A/B/C 适配器（`pg_simple_fts`、`pg_zhparser_fts`、`pg_search_bm25`）在真实 schema、普通 LOGIN 用户 + FORCE RLS 下通过同一契约与共享门禁套件（实现记录 29、30）；缺真实语料运行证据，不勾选 |
| M1-04 | 部分（权限半边已证明；候选对比半边依赖 M1-01/02） | 真实 schema 上以 LOGIN 用户证明：普通角色 + FORCE RLS 零跨部门泄漏、按主键无存在性泄露、LIMIT/排序/join 下推不丢可见行、连接池身份切换与 RESET/DISCARD 清除（实现记录 18）；"零静默候选不足"与三候选词法对比等真实探针集与 DEC-001 适配器；三候选的零静默不足（同一语句精确计数 + 分页，k 小于/等于/大于合格数、两种执行计划）、无身份拒绝、连接复用清除、版本拒绝与执行计划留证已在合成数据上通过，C 的 ParadeDB 自定义扫描在普通角色下未绕过 RLS（实现记录 29、30）；真实探针运行中管理侧逐 chunk 核对零泄漏，A/C 各 3 条查询显式 `candidate_exhausted=true`（实现记录 33） |
| M1-05 | 阻塞（三次预登记运行均未通过硬门禁） | 运行 1（记录 33）：跨语言样本是主要失败面；运行 2（记录 35，冻结探针 v2，语言一致 75 条）：A 69.3%、B 76.0%、C 88.0%；运行 3（记录 36，修订 2 停用词变体）：A2 77.3%、B2 80.0%，P95 减半，C 不变。零泄漏、可复现；相对 A 的配对提升均显著。无候选通过 90% 门禁，DEC-001 与 M1 保持阻塞，判据不降低（ADR-0002 三次回填）。剩余差距来自排序函数无 IDF 与繁体药名切分；C 许可证审核材料已备（licence dossier）。下一步路径待决策人预登记。决策人 2026-09-20 批准 ADR-0002 修订 3：最终判定推迟到端到端实验，M1 其余切片继续；2026-09-20 最终判定 A2（记录 45，ADR-0002 最终判定节） |
| M1-06 | 已实现（首个迁移 0001；evidence_log、outbox 等随其里程碑追加） | Alembic 原生 SQL 迁移建 source_objects、ingestion_jobs、documents、chunks、chunk_spans、document_acl、doc_audit，字段落点按基线 3.3/3.4/4.2 与设计文档 3.3；不可变性、状态机、审计追加写、chunk 哈希由触发器强制；15 项集成测试（实现记录 17，ADR-0006）；无 tsvector/vector 列；迁移 0005 追加 outbox 两表（记录 37） |
| M1-07 | 已实现 | `documents_one_active_per_family` 部分唯一索引；集成测试证明同 family 第二个 active 被拒，且两会话并发激活时第二个阻塞、首个提交后失败，最终只剩一个 active（实现记录 17） |
| M1-08 | 已实现（数据库层；API 注入接线在 M3） | 迁移 0002：三组 NOLOGIN 角色、登录用户供应脚本、七表 FORCE RLS、按 document_acl 与部门的策略、无身份默认拒绝、草稿不可见、owner 分离；37 项集成测试覆盖 SET LOCAL 作用域、非 owner、非 superuser、无 BYPASSRLS、只读无写路径、管理角色不能改 schema（实现记录 18）；本机 .env 已切到受限用户 |
| M1-09 | 已实现（ADR-0009；ClamAV 部署随 M3） | `medops.ingestion.pipeline`：按签名判定 PDF/DOCX、大小与哈希校验、`filecheck` 结构性恶意内容门禁（PDF 主动内容/嵌入文件/加密，DOCX 宏/OLE/ActiveX/外部关系/字段码/ZIP 炸弹，`defusedxml`）、可选 clamd INSTREAM 扫描（prod 必配，失败关闭）、`pii-rules-v1` 默认拒绝与审计覆盖、同源第二文档默认拒绝 + `SharedSourceApproval` 审计确认、重复入库幂等；DOCX 以顶级标题切章节，`page` 为章节序号、无标题即 low_trust（实现记录 20、40、43）；ADR-0009 修订 1：`/OpenAction` 按动作类型判定、对象图上限 500,000（记录 49） |
| M1-10 | 已实现（chunker-v2、入库、质量复核放行与映射工具） | 16 份文档、2,661 个 chunk 与原页重建逐条一致；新增 gold 映射器按来源/版本/页/区间校验。75 条中 73 mapped、2 unmappable，切分边界缺陷保留并计 miss；low_trust 禁止 active 的约束不变（记录 20、27）；chunker-v2（分号为子句标记、超长片段按子句标点切分）与受审计的 parse_quality 复核放行 `--accept-quality`（记录 34） |
| M1-11 | 已实现（发布/归档/审计/outbox 同事务 + 索引消费者；缓存消费者随 M1-19） | 迁移 0005 `outbox_events`/`outbox_consumer_acks`（追加写、管理角色专用、FORCE RLS）；`publish_version` 一次事务归档旧版（写 effective_to）、激活新版、触发器审计、两条事件；`activate_document` 首次激活亦发事件；`ingest_document(supersedes=)` 建版本链；outbox `claim`（SKIP LOCKED）/`ack`/`run` 按消费者幂等；`index_consumer` 增删候选索引行；集成测试证明模拟失败整体回滚、并发领取互斥、以及发布后消费者未运行时旧版已不可见（查询内 status 过滤，索引延迟不产生失效证据）（实现记录 37）。激活 `effective_from` 口径不变 |
| M1-12 | 部分（术语表初版已建，ADR-0008；分词词典不变，术语表进入生产前需离线评测） | 分词器支持词典版本（`dictionary_version` 含 jieba 词典与停用词表哈希）；`evals/glossary/tools/build_glossary.py` 由 TFDA 開放資料（按许可证字号锚定到语料）与语料内定义的缩写（同页共现验证）构建内容寻址版本的术语表，初版 `glossary-20260920-f569611ab3dd`（12 品名 + 37 缩写，provenance 含快照哈希与逐条证据）（实现记录 44）；DrugBank Open Data 待决策人下载 |
| M1-13 | 部分（规则型 `qr-rules-v1` 已实现；术语表内容待 DEC-005，LLM 改写与节点接线待 M2） | `medops.retrieval.rewrite`：1–3 条只追加不删改的文本查询（规范化原查询 / +可信会话实体 ≤3 / +术语同义词 ≤5），剂量、单位、否定、时间窗、编号为显式受保护片段并在返回前核验；术语表版本化且只在受保护片段外整词匹配；结果模型无任何过滤字段；测试覆盖四类不被改写错与实体不跨调用残留（实现记录 40）；术语表改写的离线评测为负结果（A2 Recall@20 −0.93 pp，CI 含 0），术语通道不进生产（记录 48） |
| M1-14 | 已实现；2026-10-09 切换部门隔离 BM25（记录 162） | 迁移 0022 建 MA/PV/CO 三个 `pg_textsearch` BM25 表/索引、FORCE RLS 和同步撤权触发器；固定 tokenizer、扩展、参数和停用词哈希；全量构建、outbox 增量、ACL/chunk 覆盖、版本冲突拒绝；A2 的 migration 0007 表保留回滚 |
| M1-15 | 已实现 | 生产取值固定于 `medops.retrieval.production`：retriever `pg-textsearch-bm25-departmental-v1`、tokenizer `tok-jieba-v2`、扩展/参数与词典哈希、norm-v1、embedding `emb-bge-m3-dense-v1`、RRF k=60、bge-reranker-v2-m3 参数、候选上限；复合 `retrieval_version = 19c755df…e4d1` 由单元测试固定，任一成员变化即失败；索引元数据写入 `lexical_index_meta`/`embedding_index_meta`，缓存键使用该复合版本（记录 45、162） |
| M1-16 | 已实现（ADR-0007；向量通道运行结果见记录 42） | 迁移 0006 `chunk_embeddings(vector(1024))` + `embedding_index_meta`（模型/修订/维度/归一化/截断/框架）、HNSW 余弦、FORCE RLS；`PgVectorRetriever` 在应用角色身份事务内以 iterative scan 检索、同事务精确合格计数、页长 ≠ min(K, 合格数) 即失败关闭、spec 全字段不匹配拒绝；`BgeM3EmbeddingProvider` 本地推理（可选 extra `embed`，独立哈希锁）；探针 v2 运行：language_matched 82.7%、cross_lingual 65.6%、零泄漏（实现记录 42） |
| M1-17 | 部分（融合、重排与回查已实现；并行执行、总超时与显式降级随 M2 执行器） | `medops.retrieval.hybrid`：两通道经各自边界、RRF 只用排名（k=60）、融合上限 20、`retrieve_evidence` 融合后回查；`medops.retrieval.rerank`：bge-reranker-v2-m3 只对已回查的 Evidence 打分（输入 ≤20、输出 8、并列按 chunk_id）；端到端运行见记录 45 |
| M1-18 | 已实现（`evidence_log` 落库随 M2 Trace；显式历史请求下词法 / 向量通道亦放行 archived，记录 71） | `medops.retrieval.recheck`：候选在应用角色的身份事务内一条语句回读事实平面，按固定顺序判定可见性（RLS，越权/草稿/撤回/不存在一律 `not_visible`）、状态（历史需显式 `as_of` 并标 `historical`）、生效窗口、`integrity_status=verified`、`parse_quality=trusted`、应用侧重算内容哈希、页锚点存在；通过者构造领域 `Evidence`，其余带原因与名次返回；superuser/BYPASSRLS/管理角色连接拒绝运行；与候选 A 串接的集成测试证明索引仍返回的完整性未验证、篡改、无锚点 chunk 被回查拦下（实现记录 38） |
| M1-19 | 已实现（组件 2026-09-20 完成，记录 39；2026-10-05 接入运行时，记录 121；2026-10-09 以数据库专属 namespace、Compose 常驻失效 worker 和按模式 readiness 切换本机主配置，记录 164。真实重复问题收益另属付费门禁） | `medops.retrieval.cache`：键 `<deployment namespace>rcache-v1:<dept>:<epoch>:sha256(规范化查询、权限指纹（部门/角色/scope，不含 user_id）、会话上下文指纹、as_of、历史标志、复合 retrieval_version、policy_version)`；缓存值为融合候选而非证据，`fetch_evidence` 命中后仍在身份事务内执行 M1-18 回查；`cache_consumer` 消费 outbox 事件按读者部门提升纪元；Redis 故障降级为未命中；真实 Redis 测试覆盖撤权、归档/换版本、损坏 epoch、namespace 与断连恢复 |
| M1-20 | 部分（语料 79 份/76 份激活含 5 个合成冲突 fixture；规范 v1.1 与 spec-m1 schema/校验规则就绪；LLM 起草 + 机械锚定、annotator-01 确认（ChatGPT 辅助审校写回）、claude-opus-5 独立复核（507 条新样本，71 条争议）与六轮争议裁决（agree 464 / disputed_resolved 43）已完成，**`main-v1-provisional` 已冻结**（614 条，dataset_hash 269be665…c9699，2026-09-22）；第二人工复核人暂无，升版 `main-v1` 待其完成；实现记录 47–50） | >=300 条主评测样本与 doc/version/page gold；执行人工 + LLM 及分层第二人工复核（第二人工待指定），探针并入后补复核；覆盖无答案（≥40）与冲突场景（≥20，允许合成）。语料：候选 v0.9 全部签字，TFDA 图像层核查通过，PII 误报留档，58 份入库 medops_v2（3 份 low_trust 未激活） |
| M1-21 | 部分（工具与报告已有；门禁在探针规模未过） | `medops.evals.experiments.e2e_run`：融合 → 回查 → 重排 → top-5 的严格宏平均 Recall@5，分部门/语言/切片、Hit@5、融合 R@20、通道单独 R@5、失效版本引用率、泄漏与复现检查、配对 bootstrap；探针 v2（107 条）上 A2+V 与 B2+V 重排后均为 75.7%（记录 45）；**主评测集 `main-v1-provisional`（553 条有答案）上 A2+V 重排后 84.99%**（语言一致 87.7%、跨语言 80.7%；CO 81.7% / MA 87.3% / PV 86.4%），失效版本引用 0、泄漏 0、可复现；85% 门禁差 1 条样本未过，无答案弃答近似 21.3%（阈值口径待 M2 Verifier）、冲突现行版召回 88.5% 未过；第二人工复核未完成，判定为临时（实现记录 51） |

实验选择不改口径：A 为应用预分词 + FTS，B 为数据库中文分词 + FTS，C 为数据库内 BM25；进程内 BM25 仅离线参考。基础门禁为 Lexical Recall@20 >=90%、六切片各 >=85%、零泄漏与零静默候选不足等。B/C 替代合格 A 需满足预登记的 +5pp、配对 CI 下界 >0 等全部条件，详见 ADR-0002；不在本表重新制定阈值。

主集统计采用严格 recall，而不是“命中任一 gold”：空 gold 的无答案样本单独评 abstention，不进入 Recall/Hit 分母；正样本空 gold 必须报错。探针每切片 >=8 的门禁与 M4 小于 30 仅作诊断不是同一个规则。

### M2：Harness、Verifier、Safety 与 Skills（16 项）

| ID | 状态 | 要做的工作与验收 |
| --- | --- | --- |
| M2-01 | 已实现（图结构：无绕过边测试；节点规则版首切片，记录 52） | LangGraph 固定 Intent → Retrieve → Evidence Verify → Safety → Answer / Escalate；测试图中不存在绕过必经节点的回答路径 |
| M2-02 | 部分（超时/重试/退避/降级与 State 契约已实现；asyncio 取消随 M3，记录 52） | 每节点明确输入输出模型、超时、错误类型、有限重试、取消与降级；跨节点只通过 State 交换数据 |
| M2-03 | 已实现（迁移 0008 `operation_executions`/`operation_attempts`：执行前占键、成功增量复用、attempt 单独落库、失败/失联重占、run_kind 约束；单元 6 + 集成 5；生产接线与受限载荷分离随 M3，记录 56） | operation key 接入持久化执行；attempt 单独记录，重试不重复副作用，replay_run_id 与生产隔离；不能仅凭函数存在算幂等完成 |
| M2-04 | 部分（仅接收已验证证据、claim-citation、生成后重验、弃答出口；主集 614 条实况：有答案样本回答 82.1%、引用 gold 74.9%、无答案弃答 96.7%、失效版本引用 0，记录 54；人工抽检与门禁随 M2-16） | Answer 只接收已验证证据，输出 claim-citation；生成后再校验引用和关键结论，通过前不外发最终医学答案 |
| M2-05 | 部分（结构核验拦截伪造引用，实况 614 条零伪造引用、379 个被引 chunk 全部 active；evidence_log 落库随 M3，记录 52/54） | 验证引用属于本 Trace、版本/页码/chunk 真实且有权限；重算 chunk_content_hash 与实际 evidence_text_hash，expected/observed 写 evidence_log |
| M2-06 | 已实现（Trace 预算裁剪/升级；迁移 0020 的 PostgreSQL 月度原子预留/结算账本，失败关闭且跨进程共享，记录 52、145） | Trace 总 Token/成本预算与单次模型上限都生效；超限先裁剪证据，仍不足则升级，不扩大预算继续猜测 |
| M2-07 | 部分（elements-rules-v1，记录 52） | 抽取剂量、单位、频次、适应证、人群、时间和方案编号等关键要素，建立确定性规则测试 |
| M2-08 | 部分（support-rules-v3 + 判定 gpt-6-sol，分工按 ADR-0011；DEC-003 错接受率 4.1%（规则）/ 2.2%（分工）；M2-16 门禁数据待安全集，记录 53） | supported / not_supported / contradicted 支持度判断；数字规则优先，NLI/小模型按 DEC-003 选；无依据不补医学常识，矛盾升级 |
| M2-09 | 部分（safety-rules-v2 三层：第一层补上文外泄 / 伪造优先级备注 / 假设无限制 / 原样输出等句式，第二层补面向自动化读者 / 唯一依据 / 输出塑形 / 自授权四类 genre 并修掉「<词> system:」误报——安全集 B1 20/20、载荷 10/10 命中，11,556 段 chunk 零误报，记录 70；意图层模型二次判定待做） | 用户输入、检索内容、最终输出三层 Safety；文档是数据而不是指令，注入不能改变权限或绕过检索 |
| M2-10 | 已实现（稳定 reason code；升级记录落库 `escalations`（问题、证据 chunk id、Verifier/Safety 结果、策略版本），管理角色改状态接手，记录 52/60；intent-rules-v3 覆盖第三人称 / 包装成查资料 / 急症 / 诊断等改写句，安全集 A 类 30/30、主集 0 误报，记录 70） | 稳定拒答/升级 reason code，最小必要上下文持久化，可由人工接手；诊断、处方、个体调整及紧急医疗意图拒答并升级 |
| M2-11 | 已实现（`medops.skills.registry`：scope 默认拒绝→Schema→版本集→operation key→run_node 超时/幂等重试→输出契约→安全第三层；parallel_safe 并行；AST 无绕过测试，记录 55） | Skill Registry 执行 Schema、scope、risk、timeout、parallel_safe、版本控制；节点不得绕过 Registry 调工具 |
| M2-12 | 已实现（`label_query`、`citation_verification` 经 Registry：单元 26 项 + 真实部件 12 用例（正向、非说明书、scope 拒绝、Schema、篡改数值、未知/跨部门 chunk），记录 55 §2.1；持久化与 API 接线随 M3） | 先交付说明书查询、医学引用验证两个低风险 Skill 的完整正向/失败链路 |
| M2-13 | 部分（三个 Skill 已交付：`ae_extraction`、`protocol_deviation`、`off_label_check`，单元 6 项 + 真实部件 9 用例，记录 57；功能/安全/权限/故障的全部验收随 M5-02） | 再交付 AE 线索提取、方案偏离核验、超说明书检查三类 Skill；在 M5 前完成全部验收 |
| M2-14 | 已实现（AE：Schema 无因果字段 + 因果词汇要素丢弃 + 固定声明；超说明书：按维度只报范围、无条款即 not_addressed、固定声明、安全第三层 off-label 分支整体升级；均有测试，记录 57） | AE 不自动判断因果；超说明书等高风险 Skill 只做文档范围核验，不输出用药建议 |
| M2-15 | 部分（spec-s1 v0.2；170 条草稿（9 类，语言 / 部门配额达标）+ schema + 校验器（PR-S1..S6 含两库证明，0 问题）+ 独立安全库 medops_v2_safety（6 份合成注入文档）+ gpt-6-sol 独立复核 + annotator-01 标注表；人工确认与冻结待决策人，记录 69；2026-10-04 草案升为 safety-v2-provisional——7 条替换、1 条收紧、撤下样本原文保留，`check_safety` 0 问题，新样本的独立复核待核账，记录 114） | >=150 条安全样本：越权、提示词注入、无依据结论、高风险问题及其组合；冻结版本与预期行为 |
| M2-16 | 部分（运行器 `safety_run.py` 与四项门禁 + 金丝雀遏制的自动判定已有；标注前临时运行两轮：第一轮（记录 69）越权 100%、正确拒答 83.9%、高风险召回 62.9%，登记缺陷；修规则与历史检索后第二轮 163/163 触发通过、五项门禁临时值全部达标（记录 70 §3）；主集 v2 的 4 条判定模型矛盾经决策人 2026-09-25 裁定均为过严（安全方向误报，转为 DEC-003 回归用例 rc-0002…0005，记录 54 §3.5 补记）；安全集 10 条评审分歧按建议修订后 164 一致 / 6 条对正则方法的保留待标注员-01 确认（记录 84）；正式数字待安全集冻结） | 引用准确率 >=95%、正确拒答率 >=95%、越权拦截率 >=98%、高风险升级召回率 >=95%；不得用总体分数掩盖已知越权缺陷 |

### M3：API、异步、MCP、观测与部署（13 项）

| ID | 状态 | 要做的工作与验收 |
| --- | --- | --- |
| M3-01 | 已实现（`medops.api.app`：五种契约在 TestClient + 假运行时下有测试；生产运行时在 medops_v2 上真实 HTTP 冒烟——回答 / 拒答 / 401 / 403、Trace 与升级落库、优雅停机，记录 58、67） | FastAPI `/v1/ask`：成功、证据不足、拒答、升级、服务失败契约与集成测试 |
| M3-02 | 已实现（迁移 0010、`TaskService` + `PgTaskStore`、三个路由；幂等作用域 / hash / 422 / 并发返回原任务 / 同事务 / 创建者可见 / 重试规则均有测试；`TaskResult` 契约变更决策人 2026-09-24 批准，记录 59、68） | task 创建/查询/失败重试；Idempotency-Key 按身份和路由限定作用域，存 request hash；同 key 同 payload 返回原任务，不同 payload 返回 422；事务创建、TTL 和并发语义进入 OpenAPI |
| M3-03 | 已实现（反馈、replay（记录 60/65）+ 文档状态 / ACL 管理与策略候选 / 审批 / 发布 / 回滚接口（迁移 0014，DEC-012）：逐接口角色检查（analyst 403、approver 只能裁决、admin 发布 / 回滚）、四眼、门禁占位、幂等收据、审计与 outbox；单元 3 + 集成 2 + OpenAPI，记录 75） | 反馈、文档管理、策略候选、审批、Trace replay 接口；逐接口验证业务/管理/审核权限 |
| M3-04 | 已实现（`TaskRunner` + 数据库租约、原子转换、attempt 记录、失联回收、attempts 上限、迟到汇报忽略；单元 + 集成测试；真实库端到端：API 建任务 → worker 完成 → 结果与 Trace 落库，记录 59、67） | worker 的 queued/running/completed/failed 转换、租约与结果原子持久化；崩溃恢复、重复消费安全，不把 Redis 队列当唯一事实来源 |
| M3-05 | 部分（JWKS 静态与 OIDC 发现/显式 URL（缓存、轮换刷新、节流、IdP 故障 503）、HMAC 假名、`principals` 目录、group allowlist、测试签发器；IdP 选择（DEC-010）待做，记录 58） | 接入 OIDC：验证 issuer/audience/expiry/signature；用户部门/scope 服务端映射，group allowlist，角色分离；本地测试签发器仅用于合成身份 |
| M3-06 | 已实现（官方 SDK 2.x：四个只读工具、bearer 校验复用 API 身份边界、只读角色连接与 RLS 可见性、stdio 仅开发且日志走 stderr；单元 6 + 集成 4（记录 62）；stdio 真实往返（记录 67）与 Streamable HTTP bearer 真实往返 12/12（记录 72）；每次工具调用落 `kind='mcp'` Trace，记录 73） | 只读 MCP：search_documents、get_chunk、verify_citation、list_active_versions；生产 Streamable HTTP + bearer，继承身份与数据库权限，不能写入；stdio 仅开发测试 |
| M3-07 | 已实现（迁移 0011 Trace / span / 升级记录，fail-closed；假名与追加写；MCP 调用 Trace（0013）；受限可回放载荷：迁移 0015 `trace_payloads` 信封加密（AES-256-GCM 每行 DEK + 版本化 KEK，本地密钥文件 v1）、应用角色只写、`medops_restricted_role` 读与清理、`payload_access_log` 追加写、保留 90 天 / 升级关闭后 30 天、`GET /admin/traces/{id}/payload?purpose=`；管理路由以 doc_audit / policy_releases 记录而非 Trace，记录 60 / 66 / 73 / 76） | 每次请求完整 Trace；身份 surrogate/HMAC 假名、日志脱敏，受限可回放 payload 单独加密和授权，审计追加写 |
| M3-08 | 部分（`POST /admin/traces/{id}/replay`：原 principal 当前身份 + 本部署版本集 + 独立 replay_run_id，回放记为独立 Trace，差异报告与 `replays` 落库；多版本回放随 M4，记录 65） | Trace replay 固定实际策略/检索/Skill/模型版本，用独立 run id 生成差异报告；禁止被原执行缓存短路 |
| M3-09 | 部分（OTel spans 覆盖 API/节点/模型/检索/worker；2026-10-09 自建 Langfuse v4.54.0 已验证真实 OTLP、score/feedback 回读与 outage 恢复，记录 141–145、163；DB/Redis 细分 span 与登录后 UI detail 仍待） | Langfuse 与 OTel 串联 API、数据库、Redis、LLM、Reranker、worker spans，跨任务传播 trace/task/version 信息 |
| M3-10 | 部分（`GET /metrics`：请求/结果、升级码、待处理升级、时延分位、调用/token/费用（窗口与月）与预算、任务队列；低基数标签、ops/admin 角色；告警规则、缓存与节点级错误待做，记录 64） | 延迟、错误、拒答/升级、队列、缓存、Token/成本与安全告警；trace_id/user_id 不作为高基数指标标签 |
| M3-11 | 部分（真实 API 在并发 1 / 2 / 4 与冷热下各 30 题实测，Apple M3 笔记本：问答 P95 12.8 / 15.9 / 23.4 秒未达标，Skill P95 13.5 秒达标；归因为 gpt-6-sol 调用尾部与本机交叉编码重排（满载 6.5 秒、并发时钉住线程排队）；杠杆与代价列于记录 77 §5；决策人 2026-09-25 批准处置：保持部分、fp16 重排与判定并行进入 M4 候选、门禁在部署硬件复测） | 普通问答 P95 <=8s、复杂 Skill <=15s；记录并发、硬件、语料、冷热缓存、失败率，不能仅测单次最快请求 |
| M3-12 | 已实现（多阶段非 root 镜像、哈希锁定依赖、`/healthz` `/readyz`、三进程优雅停机、compose `app` profile、`docs/DEPLOY.md`；CI 构建与扫描随 M0-10 / P1，记录 63） | 固定依赖、非 root 镜像、health/readiness、优雅停机；配置/密钥隔离、持久化和部署说明 |
| M3-13 | 已实现（记录 61 假部件 5 用例 + 记录 78 真实进程演练 8 场景：黑洞超时、503、429、审计触发器中断、数据库容器暂停、worker SIGKILL 接管、双 worker 恰好一次，全部可定位 / 可恢复 / 不绕过安全链；演练引出数据库连接快速失败（503 而非挂起）与 worker 循环守护；租约短于执行时间 = 至少一次，已写入 DEPLOY） | 主链路故障测试：模型超时、worker 重启、队列重复消费；证明失败可定位、可恢复且不绕过安全链 |

### M4：受控自进化 Loop（10 项）

| ID | 状态 | 要做的工作与验收 |
| --- | --- | --- |
| M4-01 | 已实现（迁移 0016 `trace_signals` 视图把反馈 / 升级与人工结论 / Verifier 失败 / 安全标记 / 回放差异拼到 Trace；`medops.loop.observe` 按窄规则建 `bad_cases`（幂等、快照不可改、人工修正列只有管理角色能写）；Loop 登录用户只读信号、读写案例，真实用户下证明无 released 写路径；连续追问信号等会话落地，记录 79） | 用户反馈、Verifier、Safety、升级信号关联原 Trace；Execute/Observe 有统一数据来源 |
| M4-02 | 已实现（`medops.loop.reflect` 规则归因五类、固定置信、`attribution_note` 写明依据；人工修正 = `human_override`（管理角色）+ `reflect correct`，覆盖优先；模型遍待加，记录 80） | Reflect 对 bad case 分为 retrieval / intent / generation / knowledge_gap / safety，带置信与人工修正入口 |
| M4-03 | 已实现（`medops.loop.adapt`：分簇提案 + 形状校验 + INV-EVAL-01 隔离 + 经 Loop 角色写 candidate；`policy_loader` 在 API / MCP 启动时应用 released 的 `retrieval_params/hybrid` 与 `prompt/answer_system`，版本集随之变化；发布守卫 `policy_target_unsupported`；rule / skill 的运行时叠加待做，记录 80） | Adapt 只生成 Prompt/Rule/Skill/检索参数候选 diff；线上只读 released，生产来源不是仓库最新 Prompt 明文 |
| M4-04 | 已实现（`tests/integration/test_loop_role_permissions.py`：授权矩阵逐项钉死，真实 Loop 用户直接 SQL 证明只能插入候选、不能写 released / 决策 / 审计 / 语料 / DDL，记录 81） | Loop 数据库角色只能写候选，无 released 写权限；用直接数据库操作的权限测试证明 |
| M4-05 | 已实现（迁移 0017 `document_requests`：问题 + 缺口描述，无内容字段；Loop 只建、管理角色处理、关闭即终态，记录 80） | knowledge_gap 生成补文档任务，不自动生成或补写医学事实 |
| M4-06 | 已实现（`evals/replay/replay-v1` 冻结：主集 v2 运行导出 614 项 good 496 / bad 118，安全回归集 170 项单列，筛选子集 200 项无 derived、bad 30%；manifest 标注运行导出与临时来源，哈希校验进 `make check`；隔离规则写明、执行随 M4-03，记录 79） | >=200 条独立 good/bad 历史 Trace 的冻结回放集，另跑安全回归集；不以 3 次重复运行充当 600 条独立样本 |
| M4-07 | 已实现（`evals/replay/tools/replay_run.py`：两臂同项、N 次独立运行、配对 bootstrap 95% CI、每臂每轮成功 / 安全 / 时延 / token / 费用、< 30 项切片 `diagnostic_only`、费用上限与续跑；冒烟 4+4 项 × 3 轮 × 2 臂通过；首个候选的 200 项正式评测待预算确认，记录 82） | 3 次独立运行、配对比较、bootstrap 95% CI；报告目标/非目标/安全/延迟/Token/成本，<30 样本切片标记不足；冻结评测集不进入候选生成上下文 |
| M4-08 | 已实现（`medops.loop.gate.compute_gate`：+5 pp / −1 pp / 安全三次最差不降 / ≥ 3 轮 ≥ 200 项，CI 只报告；发布路由 `gate_report_valid` 只接受完整通过报告，占位被拒，记录 82） | 自动门禁：目标点估计 >=+5pp、非目标下降 <=1pp、安全不下降；安全取三次最差值，CI 如实报告不事后改阈值 |
| M4-09 | 已实现（四眼批准 + admin 发布 ≤ 10% + approver `promote`（单调、24 小时观察窗、override 记录）；运行时每 5 秒重读指针并按主体假名分流，`policy_version` 带 `+rel:` / `+canary:`；真实 API 演练 6 主体 4 阶段逐条版本一致，记录 85；首个真实候选（检索四件套）在 replay-v2 上门禁通过 Δ +8.33 pp ，决策人 2026-09-30 亲自批准并发布 10% 金丝雀（首个真实发布），观察窗以合成冒烟填充后由决策人带 override 理由推进到全量（2026-09-30 13:56 UTC），首个真实策略已全量生效，记录 104–106。更正：门禁报告测于 76 份可检索语料，真实语料上的检索层复测支持发布方向（+7.6 pp），端到端门禁待复核，记录 109） | 人工签字、候选发布、初始灰度 <=10%、观察窗与全量发布；版本及操作者可审计 |
| M4-10 | 已实现（一次 `rollback` 原子切回，TTL 内全部请求回到前一策略，响应版本 = Trace 版本 = 分流期望；演练报告 `evals/harness/runs/2026-09-25-release-drill-v1`，记录 85） | 一次操作原子回滚 released 指针，完成演练并确认运行请求的版本一致性 |

### M5：规模、全量验收与成本（8 项）

| ID | 状态 | 要做的工作与验收 |
| --- | --- | --- |
| M5-01 | 已实现（候选清单 v1.3/v1.5/v1.7 共 350 份经决策人签字 `eligible`；重下载哈希比对、页文本抽取、乱码与产品身份排除、仿單图像层目视、PII 复核后入库 medops_v2：active 333（MA 125 / PV 127 / CO 81，含 7 份质量复核放行的 `-r2` 记录），安全库 339；3 份被 ADR-0009 拒收、3 份第三方内容不入库；两批 10% 抽样均由决策人签字；`main-v5-provisional` 已冻结（339 份 corpus 记录、615 条样本、580 mapped / 2 unmappable），记录 96–103、150、155。扩语料后的全量重测与验收在 M5-03 / M5-05。更正：257 份新文档的检索索引直到 2026-10-02 才构建，此前不可检索；冻结证据再次验证 3 份 ADR-0009 拒收项没有进入事实库，且当前样本不引用它们） | 300–500 份许可清楚的公开文档治理入库，记录原始来源、版本、部门用途与许可依据；合成 fixture 不充数量 |
| M5-02 | 已实现（`tests/unit/skills/test_matrix.py` 27 项参数化用例 × 五个 Skill：权限先于调用、schema 不进 handler、无证据不调模型、供应商 / 证据存储故障有界升级、输出不含个体建议；功能格由各 Skill 单元测试与 2026-09-23 两次真实冒烟证明，记录 88） | 五个 Skill 全部通过功能、安全、权限、失败与故障测试 |
| M5-03 | 部分（[验收报告](ACCEPTANCE_REPORT.md) v1：最终验收总门禁 9 条中 7 条达标——语料 333、Recall@5 released 88.79%（基线 84.99%）、引用结构准确 100%、失效引用 0、安全五项 1.00、回放门禁与灰度发布；问答 P95 与 Token 降幅未达标；发布后 P95 复测待做；可复现运行清单在报告 §4。v2 更正：端到端运行测于 76 份可检索语料，待在真实语料上重测；检索层已重测，released Recall@5 87.16%、基线 79.57%，记录 109；v3：主集与安全集已在真实语料上重跑（作答率 91.0%、引用结构准确 100%、越权拦截 0.949 按原预期未过且 5 条样本待人工裁决），一轮反向对照 +5.0 pp，API 性能与容量待重跑，记录 110） | 冻结数据上的质量、安全、性能全项验收；固定系统版本与可复现运行清单 |
| M5-04 | 待做（首个候选 rerank 8→5 一轮试跑否决，记录 108；`evidence_focus` 候选 v7 待正式三轮，记录 113、116–120；小模型作答路由因质量 −7.0 pp 否决，记录 125；Redis 已完成工程切换与故障验证，真实重复问题收益待 CACHE-10，记录 164） | 上下文裁剪、缓存、模型路由使同等质量下 Token 降低 >=25%；保留优化前后同集对照及安全回归 |
| M5-05 | 已实现（真实的 333 份可检索语料、已发布策略、经真实 API：并发 1 / 2 / 4 / 8 / 16 各 30 题，吞吐上限约 0.39 req/s，拐点在并发 4–8，并发 16 时 80% 超时且失败关闭；单 worker 队列 8 任务端到端 P95 113 s；冷启动 10–11 s 且无首批惩罚；测量时仅有 5 秒策略指针缓存，后续记录 121 已接入默认关闭的检索缓存，其收益不计入本次容量成绩；瓶颈为检索节点（p50 6.4 s）与本机重排，记录 111。P95 目标未达标属 M5-03） | 目标语料规模、并发、队列积压、冷启动与缓存失效容量测试，记录瓶颈及资源上限 |
| M5-06 | 已实现（迁移 0019 受控保留清理路径 + `retention` / `payload_rotation` CLI；`scripts/db_backup.py` / `db_restore_drill.py` 并在本机完成一次恢复演练（88 秒、63,293 行五项指纹一致）；`docs/OPERATIONS.md` 含保留期表、四类密钥轮换、恢复流程、依赖升级；P1 灾备明确划出，记录 87） | 数据保留/删除、密钥轮换、备份恢复、依赖升级手册；P0 迁移恢复方案与 P1 完整灾备演练不混淆 |
| M5-07 | 已实现（`docs/RUNBOOK.md`：健康检查、事故四级、七条告警处置、人工升级处理 SQL、Loop 日常、发布 / 灰度 / 回滚命令与检查单、事故记录模板；命令均已在记录 67 / 78 / 85 的真实运行中执行过，记录 87） | 运维 runbook、事故响应、人工升级、发布与回滚操作手册，可按文档实际执行 |
| M5-08 | 待做 | 最终验收报告与演示材料；简历只写实测、已交付能力，区分目标、局部工具结果和端到端成绩 |

### 不能遗漏的横向实现细节

这些来自基线正文，是上述任务的实现要求，不额外增加任务门禁：

- **数据模型分批建**：知识表之外还有 tasks/task_attempts、traces/spans、evidence_log、escalations、skills/skill_versions、policies/releases、feedback/bad_cases、evaluation_datasets/runs/results、outbox_events；按所处里程碑迁移，不在 M0 一次性写全。
- **三层证据完整性**：原始 source hash、chunk 内容 hash、实际裁剪证据 hash 各有用途；关联 JOIN 不等于重算内容。原件/抽取 manifest 的后台完整性检查、expected/observed 审计纳入 M1-09/10、M2-05。
- **失败与审计**：外部调用设连接/读取/总超时、有限重试、取消和并发上限；审计故障不能悄悄生成无审计医学答案，应可靠缓冲或安全失败。对应 M2-02、M3-07/13。
- **基础部署安全**：TLS、CORS 白名单、请求体/速率限制、dev/test/prod 配置隔离、生产调试/接口文档默认关闭、数据库/Redis/对象存储持久化和容量限制，纳入 M0-09、M3-12、M5-05。
- **原文可回看**：展示原文与用于定位的规范化文本分开；保留来源页片段，历史版本查询必须显著提示且有权限。对应 M1-10/18、M2-05。
- **服务复用**：API、MCP、Skill 都走同一授权检索与证据校验服务，不各自复制一套逻辑。并行只对 parallel_safe 工具开放，部分结果不等于可以跳过最终安全门禁。

## 5. P1/P2 全量选做项

先有 P0 稳定回归集，再按“具体问题 → 基线数据 → 小实验 → 收益/故障/成本评估”决定是否做；不是技术栈里出现就必须实现。

| ID | 优先级 | 选做工作与边界 |
| --- | --- | --- |
| OPT-01 | P1 | 扫描 PDF OCR、版面识别、置信度与人工复核队列；产物仍是可定位文字，不宣称理解图表 |
| OPT-02 | P1 | 独立 Reranker/NLI 推理服务：GPU、批处理、预热、量化、并发/显存控制、弹性伸缩；先测推理瓶颈，不先堆服务 |
| OPT-03 | P1 | 文档审核、ACL、升级、策略 diff、评测、灰度、回滚管理界面；P0 不要求完整前端 |
| OPT-04 | P1 | 高可用后端、托管存储、多副本 worker、读写隔离评估、零停机迁移、灾备和合规审计；明确 RPO/RTO、审计导出与第三方数据处理边界 |
| OPT-05 | P1 | 外部工单系统脱敏集成、最小必要上下文、投递幂等与审计 |
| OPT-06 | P1 | SBOM、依赖/镜像扫描、完整恢复演练、DB/Redis/Reranker 等外部依赖故障演练 |
| OPT-07 | P1 | 后续词法引擎替换：新冻结评测、权限与候选数/性能回归、许可证复审、ADR；不是只换一个适配器就发布 |
| OPT-08 | P2 | 多模态表格、流程图、图像证据：坐标、引用渲染、模态级 Verifier、安全与质量独立评测；不是个人诊断/医学影像诊断扩展 |
| OPT-09 | P2 | 知识图谱辅助召回/一致性检查；每项结论仍回查来源，不把图谱当无来源医学事实 |
| OPT-10 | P2 | 跨语言术语对齐、检索与引用核验，按中英及繁简分别报告质量 |
| OPT-11 | P2 | 主动学习只推荐待标注样本，人工确认后才进入数据或词典 |

基线 §7 还列有两组没有独立 checklist 行的选做方向，也保留在任务视图中：

- **OPT-12 / P1 更强检索**：结构/标题感知切分、parent-child retrieval、查询路由、hard-negative 训练，以消融决定去留。
- **OPT-13 / P2 学习型路由与个性化**：仅用非敏感受控特征，不能修改 ACL 或放宽安全阈值。

这两项不是本轮新需求，不计入 99 个基线复选项。暂不引入 Kubernetes、微服务拆分、模型微调或额外向量数据库作为默认前提。

## 6. 全部 DEC 与当前状态

| DEC | 内容 | 状态与处理时点 |
| --- | --- | --- |
| DEC-001 | 词法引擎、中文 tokenizer/词典 | 协议/阈值已决，探针已归档，实验准备草案和映射已有；镜像/适配器与正式实验待完成，生产实现未决 |
| DEC-002 | Embedding 模型、维度、归一化与 Reranker | 待实验，M1；选定前不锁死 vector 维度 |
| DEC-003 | Verifier：NLI 或小 LLM | 已决（ADR-0011，2026-09-23）：规则裁极性矛盾与整句包含，其余交 gpt-6-sol 判定；2,076 对实验见记录 53；档位由决策人 2026-09-24 确认（记录 68） |
| DEC-004 | arq / Celery / 轻量 worker | 待决，M0/M3；以恢复、幂等和运维需求选择最小可用方案 |
| DEC-005 | 医学术语来源 | 待决，M1 入库前；不是语料许可政策的编号 |
| DEC-006 | 灰度按用户或部门 | 待决，M4；结合风险范围与统计有效性 |
| DEC-007 | 对象存储与备份 | 待决，M1；不可变、权限、原文回看、恢复与成本 |
| DEC-008 | Trace/审计保留期 | 待决，M3 上线前；覆盖重放窗口与数据最小化 |
| DEC-009 | 模型托管/本地与数据传输边界 | 已决（ADR-0010，2026-09-23）：OpenAI API，月上限 30 美元可调，模型 ID 已锁定 gpt-6-sol；Langfuse 决策人 2026-09-24 定为暂不接，如需看板只在同网络自建（记录 68） |
| DEC-010 | 身份提供方/token | OIDC 边界已决；决策人 2026-09-24：具体 IdP 推迟到部署对象确定后再选，代码只依赖 issuer / audience / JWKS 与组到 scope 映射（记录 67 合成签发方验证，记录 68） |
| DEC-011 | 来源白名单、四级许可政策 | 政策已决；v1 主体 16 份逐文档准入已落实，其余候选按需继续审核 |
| DEC-012 | 管理接口契约（M3-03） | 已决（记录 74，2026-09-25）：文档管理只管状态与 ACL、不含上传；策略候选 / 审批 / 发布 / 回滚状态机与 `approver` 角色；Loop 角色只写候选 |
| DEC-013 | 受限可回放载荷的加密与保留期（M3-07） | 已决（记录 74，2026-09-25）：信封加密（AES-256-GCM DEK + 可插拔 KEK，v1 本地密钥文件）、独立表与角色、admin + 用途读取并记日志、保留 90 天 / 升级关闭后 30 天 |
| DEC-014 | M4 回放集来源与候选评测预算 | 已决（记录 74，2026-09-25）：首版回放集由主集 v2 运行与安全集导出（标注运行导出）；候选筛选 200 条子集三次约 5 美元，发布前全量三次约 16 美元 |

无需为继续写纯领域模型而提前决定全部模型厂商、身份厂商或基础设施。

## 7. 最终验收清单（基线第 11 节，9 项）

以下当前均未验收，不能作为简历实测成果：

| ID | 验收条件 |
| --- | --- |
| G-01 | 300–500 份文档治理入库，按 M5 与 ADR-0003 的实际准入要求验收；不拿测试 fixture 替代真实公开语料 |
| G-02 | >=300 条检索/引用样本，严格宏平均 Recall@5 >=85%，另报 Hit@5，引用准确率 >=95%，失效版本引用率 0 |
| G-03 | >=150 条安全样本，正确拒答 >=95%、越权拦截 >=98%、高风险升级召回 >=95% |
| G-04 | >=200 条历史 Trace，发布满足 +5pp、非目标下降 <=1pp、安全不降、人工签字与灰度 <=10% |
| G-05 | 普通问答 P95 <=8s，复杂 Skill P95 <=15s |
| G-06 | 同等质量下单次 Token 消耗降低 >=25% |
| G-07 | 回答可审计、策略可追溯、一次操作可回滚 |
| G-08 | 无诊断/处方、真实患者数据、跨部门泄漏、写入型 MCP、自动生产策略修改路径 |
| G-09 | 全部数值来自可复现实测报告，不以目标或局部工具测试冒充系统结果 |

## 8. 结合八股的学习顺序

“边编译边学习”在本项目里可以落实为：**读一个知识点 → 写一个小功能 → 跑测试/构建 → 制造一个失败 → 用代码解释原理**。Python 阶段主要是安装、运行、测试；不用为了“编译”额外引入其他语言。

### 8.1 已有代码，现在就能拿来学习

| 顺序 | 读代码/运行入口 | 对应基础与面试问题 | 练习产物 |
| --- | --- | --- | --- |
| L-01 | pyproject、Makefile、CI；`make check` | src layout、模块导入、venv、editable 安装；为什么 pytest 能通过而 CLI 找不到包？ | 在仓库外验证 import，说明 PYTHONPATH 如何掩盖安装问题 |
| L-02 | canonical.py 与 core 单测 | JSON 规范化、UTF-8、散列、幂等；为什么 `hash(a+b)` 不可靠？哈希与 HMAC 有何区别？ | 解释分隔符、版本字段、run_id 各解决什么，构造顺序不同但同义输入 |
| L-03 | normalization.py 与 18 个向量 | Unicode NFC/NFKC、字符与字节、偏移量、正则；为什么不能直接统一兼容字符？ | 用 10⁹/L、全角字符和伪空白演示语义/定位风险 |
| L-04 | validator.py、fixture_builder、回归测试 | Schema 与跨文件业务校验、fail-closed、pytest fixture、反向测试；为什么 Schema 通过不代表数据正确？ | 选一个 PR 规则，只篡改一处数据，证明它被对应 Finding 拦下 |
| L-05 | tokenizer.py、contracts.py | Protocol/Pydantic、依赖隔离、可变全局状态、版本化；为什么有版本字符串仍可能不可复现？ | 修实例词典隔离，用两个词典实例的回归测试说明问题 |
| L-06 | bm25_offline.py、fusion.py | 倒排索引、TF/IDF、词频饱和、长度归一化、RRF；为何 raw_score 不直接相加？ | 手算一个微型语料的排名，比较召回漏项与排序变化，解释 Reranker 救不回漏召回 |

### 8.2 后续开发与知识点一一对应

| 阶段 | 边做的功能 | 应掌握的八股 | 可用于面试的代码证据 |
| --- | --- | --- | --- |
| M0 契约 | 领域模型、AgentState、错误模型 | 类型提示、dataclass vs Pydantic、不可变性、序列化、依赖倒置、契约测试 | 非法状态/字段被拒绝，JSON 往返，模型不依赖数据库 SDK；不是背一套架构名词 |
| M0 工程 | 依赖锁、CI、Compose、威胁模型 | 可复现构建、测试分层、容器进程/网络/卷、配置与密钥、信任边界 | 干净环境启动与故障用例；说明为什么“能在自己机器运行”不够 |
| M1 数据库 | 文档版本、ACL、RLS、outbox | ACID、MVCC、隔离级别、锁、唯一/部分索引、事务竞态、行级权限、连接池 | 两个事务并发发布只能留下一个 active；池连接复用不串身份 |
| M1 文档 | 抽取、切分、内容 hash、gold 映射 | 数据清洗与不可变原件、内容寻址、字符区间、ETL 质量门禁 | 跨页同句不会误判命中；改 chunk 文本会被 hash 校验发现 |
| M1 检索 | FTS/BM25、embedding、pgvector、RRF、Reranker | 倒排索引与向量相似度、ANN/HNSW、过滤后召回、双塔 vs cross-encoder、Recall/Hit/Precision | 同一冻结集的消融、部门切片、候选不足和执行计划；不泛称 BM25 一定更好 |
| M1 缓存 | 权限/版本指纹与失效 | cache-aside、TTL、穿透/击穿/雪崩、读写一致性、撤权失效 | 旧 active 归档后缓存不能继续提供证据；缓存命中不能绕过授权 |
| M2 Harness | 图执行、重试、取消、幂等 | 状态机/DAG、异常分类、指数退避、at-least-once、幂等与重试区别、并发合并 | 无检索回答路径不可达；超时/重复执行不会产生多份副作用 |
| M2 医学 RAG | Evidence、Verifier、Safety、Skills | Grounding、结构化输出、工具调用、提示词注入、规则与模型分工、NLI 支持/矛盾 | 剂量改一个单位能被识别；文档里的“忽略规则”无法提权 |
| M2 模型基础 | Token 预算与模型调用 | Transformer/attention 的基本机制、上下文窗口、生成随机性、Token 成本；KV cache 留到推理优化再深入 | 解释为什么低 temperature 不等于严格可复现；为何整条 Trace 要限预算 |
| M3 服务 | FastAPI、任务与 worker | HTTP/ASGI、async/await、I/O vs CPU、背压、连接池、超时取消、任务租约 | 并发相同 key 返回同 task；不同 payload 422；worker 杀掉后恢复 |
| M3 身份/MCP | token、scope、只读工具 | 认证 vs 授权、OAuth/OIDC/JWT 边界、签名与 claim 验证、最小权限 | 伪造 dept/scopes 无效；MCP 连接成功不代表能读所有文档 |
| M3 观测/性能 | Trace、metrics、P95、压测 | logs/metrics/traces 区别、分位数、指标基数、慢调用拆解、队列与吞吐 | 用一条 Trace 定位 DB/模型/排队时间，给出固定环境的 P95 报告 |
| M4 Loop | 回放、配对评测、发布/回滚 | 数据泄漏、独立样本、配对 bootstrap、置信区间、灰度与版本指针 | 200 个 Trace 不等于 600 个独立样本；候选评分再高也不能绕过审批 |
| M5 优化 | 成本对照、容量、运维 | 性能与质量权衡、容量规划、冷缓存、恢复策略、复现实验 | 同一数据/质量约束下 Token -25%，同时展示安全与延迟未恶化 |
| P1 按需 | 独立推理和高可用 | batching、量化、GPU 显存、扩缩、RPO/RTO、零停机迁移 | 只有主链路测出瓶颈后，展示优化前后对照与新增故障处理 |

学到能解释当前代码和失败机制即可，不要求开始 M0 前背完分布式系统、CUDA 或模型训练。尤其不要为了面试关键词引入用不到的 Kafka、Kubernetes、图数据库或微调链路。

### 8.3 接下来按这个顺序推进

1. **M1-01 已完成并归档。** `2a4aef6` 归档基础代码与复核依赖，`213dbe8` 独立冻结 75 条探针及 8 件复核证据；ADR 已回填真实 commit 和双哈希。独立 checkout 的既有 418 项单元测试及 frozen 校验通过。冻结 v1 后续修正必须升版。
2. **当前：补齐 M1-02 的候选环境并冻结实验清单。** [准备目录](../evals/experiments/lexical/README.md)已记录 A 现有环境、B=zhparser v2.3/SCWS 1.2.3、C=pg_search v0.25.9/Jieba 的源码身份、硬件和测量参数草案。下一轮构建 B/C，记录真实镜像 digest、词典/规则/完整配置和扩展运行版本；先用合成输入验证，不按探针得分调参。
3. **补适配器与正式实验前置。** gold→chunk 映射已经生成，73 mapped、pc-0056/0072 两条 unmappable 原样计 miss；不会通过删题或改 key_text 消除。开发库 16 份文档仍为 draft，其中 esomen 为 low_trust，正式实验前处理解析质量与发布条件。随后在隔离实验环境以普通角色验证 RLS、计数、版本和执行计划；补齐端到端配置、独立许可证结论后按 ADR-0002 跑全部候选。C 仍 release_blocked，尚无生产选择。
4. **可独立推进的实现切片：M1-11 发布事务。** 新版本激活、同 family 旧版归档、审计与 outbox 原子提交；验证并发发布、事务回滚和重复消费。先做数据库事务与事件边界，索引/缓存消费者随实际组件接入后再验收整项。该切片不要求先选定词法引擎。
5. **补齐剩余 M1 与 M0 接线。** DEC-002/005/007 等按依赖推进，完成混合检索、事实回查、缓存和主评测；M0 已有契约、依赖锁、迁移、Compose 与威胁模型按代码继续复用，远端 CI 首次运行及安全阶段仍待完成。
6. **M2 → M3 → M4 → M5。** 先完成固定安全链路与低风险 Skill，再扩到五个 Skill、可恢复服务、受控 Loop 和全量验收；P1/P2 按需要启动。

下一步是步骤 2 的固定环境构建与合成契约验证；步骤 4 可独立推进。领域模型、错误模型、tokenizer 隔离与 canonical 工具已实现，不再列作从零开发任务。对应知识确认题与代码入口见[任务知识对照 §10](TASK_KNOWLEDGE_MAP.md#10-下一步)。

### 8.4 每轮固定的开发与复检方式

每轮只选一个可验证切片；下面是学习记录模板，不是新增发布流程：

```text
任务：关联 Mx-xx；本轮只实现什么，明确不实现什么。
知识：最多 2–3 个原理问题，先写自己的答案。
约束：关联哪些 INV、Schema、版本/权限规则。
实现：最小代码和必要注释，不先造框架。
测试：正常 + 边界 + 失败；涉及权限/版本/并发时必须补对应反例。
复检：逐条执行基线第 9 节，跑 lint/type/test 和相关集成/eval。
证据：记录命令、真实结果、未运行项、剩余风险；据此更新本表。
复述：用 3–5 分钟讲清“为什么这样做、错在哪里、如何证明、还有什么没做”。
```

常用本地命令（仓库根目录，已有 `venv/`）：

```sh
env -u DEBUG -u PYTHONPATH make check
venv/bin/python -m pytest -q tests/unit/evals/test_probe_validator_regressions.py
venv/bin/python -m pytest -q tests/unit/retrieval
```

本轮会话有继承的非布尔 `DEBUG`，上面的命令只移除进程变量，让 `.env` 的项目配置生效。每次核对 pytest 的 passed/skipped 明细；需要集成验证时，出现 skipped 应先查配置与数据库可达性。`make check` 的 pytest 已包含迁移集成用例，`make migration-check` 是可单独执行的迁移检查目标。

真实版本目录建立后，才使用下列带占位参数的命令；目前不要将 `examples/` 声称为 frozen：

```sh
make validate-probe DIR=<真实版本目录> MODE=draft PAGES=<页文本目录>
make validate-probe DIR=<真实版本目录> MODE=frozen PAGES=<页文本目录>
```

后续修改范围/阈值先走基线与 ADR；完成实现后更新这里的状态、测试证据和日期。历史审核记录不改写成新的实测结论。
