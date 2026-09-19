# 实现记录 13：目标确认、阶段划分与 M0 收口（OpenAPI 初版、canonical 已知答案向量、草稿 JSONL 重写）

日期：2026-09-17。范围：(1) 逐条确认项目描述的规划与约束已写入基线；(2) 按当前进度划分阶段；(3) 执行阶段 1 的四轮本机可验证切片：M0-08 OpenAPI 初版、M0-06 跨平台已知答案向量、M1-01 配套的草稿 canonical JSONL 重写命令、进度文档刷新。未修改冻结基线、SPEC、Schema 或校验器规则；未提交 Git；未替决策人签字或作阶段 3 的任何决定。**状态：待 Codex 审核与决策人批复。**

## 1. 目标确认：项目描述 → 基线

来源：[项目描述 v0.1](../source/PROJECT_DESCRIPTION_v0.1.md) 与设计文档 PDF，`shasum -a 256 -c docs/source/SHA256SUMS` 两项 OK。核对方法：把项目描述拆成 49 个要点，用正则在 [基线 v0.6](../ENGINEERING_BASELINE.md) 全文检索落点；47 个直接命中，2 个措辞不同但语义覆盖（见表末）。

| 项目描述要点 | 基线落点 |
| --- | --- |
| 面向 MA/PV/CO；说明书、方案、SOP、指南；只用公开/脱敏/合成数据 | 1.1、1.2 第 1 项、INV-DATA-01、1.3 |
| LangGraph 固定 `Intent → Retrieve → Evidence Verify → Safety Check → Answer / Escalate`，不能绕过检索 | 1.2 第 2 项、INV-HAR-03、M2-01 |
| Pydantic/JSON Schema 约束节点 IO；Skill Registry 管理权限 | INV-HAR-01、INV-AUTH-03、M2-11 |
| 超时重试、失败降级、幂等控制、人工升级、Trace 重放 | INV-HAR-04、3.2、5.3、M2-02/03、M3-08 |
| PostgreSQL 事实平面：draft/active/archived、版本链、生效时间、来源哈希、页码、章节 | 1.2 第 4 项、INV-DATA-02～06、3.3、3.4、4.2 |
| pgvector 只做候选召回，命中后回查原文、版本与权限 | INV-DATA-07、3.7、M1-18 |
| `BM25 + pgvector + RRF + Reranker`；Query Rewriter 用术语表与会话实体；Verifier 核对剂量、适应证、时间、引用 | 1.2 第 3 项、3.1（BM25 解释为精确词法召回，ADR-0002）、5.2、5.4、M1-13/17、M2-07/08 |
| 五类 Skill；证据不足/版本冲突/越权/注入/高风险拒答或升级；不给诊断处方 | 1.2 第 5、6 项、INV-SAF-01～04、5.5、5.6、M2-12～14 |
| Loop `Execute → Observe → Reflect → Adapt → Approve → Deploy`；信号采集；五类归因；生成 Prompt/Rule/Skill/检索参数候选；禁止在线改生产；回放、人工审核、灰度、门禁 | 5.8（链为 `Execute -> Observe -> Reflect -> Adapt -> Replay -> Approve -> Canary -> Release/Rollback`，是描述六步的超集）、INV-HAR-05/06、M4-01～10 |
| Langfuse + OpenTelemetry；FastAPI；只读 MCP 继承身份权限 | 1.2 第 7～9 项、INV-AUTH-04、5.7、M3-05/06/09 |
| 验收：300–500 份文档；≥300 样本；Recall@5 ≥85%；引用准确率 ≥95%；失效引用 0；≥150 安全样本；拒答 ≥95%、越权拦截 ≥98%、升级召回 ≥95%；≥200 Trace 回放；+5pp / −1pp；版本审计与一键回滚；P95 8s/15s；Token −25% | 第 6 节里程碑门禁、5.9 指标口径、第 11 节九条总门禁（逐条对应） |
| 可替换两条：FastAPI/PostgreSQL/Redis 异步服务，`queued/running/completed/failed`，失败重试与进度查询；部门 Skill 与 ACL 强制过滤、并行工具、部分结果、超时降级、审计 | 5.7、5.12、INV-AUTH-02/05、M3-02/04、`parallel_safe`（M2-11） |
| 技术栈：Python、FastAPI、LangGraph、pgvector、BM25、RRF、Reranker、Redis、Pydantic、Langfuse、OTel、MCP、Docker | 4、5.7、5.12、M0-11 |

措辞不同的两处：Loop 链在基线中多出 Replay、Canary、Release/Rollback 三步，属于收紧而非缺失；“自动生成 Prompt、Rule、Skill 或检索参数候选”在基线中写为 INV-HAR-05 的四类版本化对象与 M4-03 的“候选以可审查 diff 保存”。两处均不需要修改基线。

基线机械检查（本轮重算）：不变量 30 条、无重复；DEC 11 项；复选项 99 个，`[x]` 0、`[!]` 0、`[~]` 0；代码围栏 14 个成对；`docs/` 下相对链接 0 失效。结论：实现目标存在、已冻结、与原始描述一致；本轮未发现需要补进基线的要点。

## 2. 按当前进度划分的阶段

| 阶段 | 内容 | 本机能否验证 | 状态 |
| --- | --- | --- | --- |
| 阶段 1：M0 收口 | 轮 1 OpenAPI 初版（M0-08）；轮 2 canonical 已知答案向量（M0-06）；轮 3 草稿 JSONL 重写命令（M1-01 配套）；轮 4 进度文档刷新 | 能 | **本记录完成** |
| 阶段 2：M1 事实平面与权限 | M1-06/07 migration 与 active 唯一约束、M1-04/08 RLS 零泄漏与零静默不足 | 不能：本机无 Docker、无 PostgreSQL 服务与客户端（`docker`、`psql`、`pg_isready` 均不存在，Homebrew 与 /Applications 无 PostgreSQL） | 阻塞，见第 8 节第 4 问 |
| 阶段 3：语料与探针冻结 | 记录 12 §5 四项决定、原件本地存储、`corpus.json`、标注与 LLM 复核、frozen 校验、DEC-001 实验 | 部分能（工具已备） | 阻塞于决策人 |
| 阶段 4 及以后 | M2 → M3 → M4 → M5，按路线图 8.3 | 依赖前三阶段 | 未开始 |

M0 剩余的“部分”项（M0-01 migrations 目录、M0-03 migration check、M0-04 集成/契约/安全/评测 smoke、M0-11 API/worker 进 Compose）都依赖 M1 数据库或 M3 服务代码，按路线图随对应里程碑补，不在阶段 1 造空壳。M0-03 的格式检查是例外：可以立即做，但 `ruff format --check` 当前会改动 73 个文件中的 51 个，属于一次性大 diff，未经批准不做（第 8 节第 1 问）。

## 3. 轮 1：OpenAPI 3.1 初版（M0-08）

完成：[src/medops/api/openapi.py](../../src/medops/api/openapi.py) 从与 `schemas/api/*.schema.json` 相同的 7 个 Pydantic 模型构建 OpenAPI 3.1.0 文档，导出为 [schemas/openapi.json](../../schemas/openapi.json)，纳入 `contracts_export` 的 `render()`，因此 `make check`/CI 的 `--check` 漂移检查自动覆盖。不引入 FastAPI（记录 09 复核结论：不为 OpenAPI 建空壳）。

- `components.schemas`（20 个）由 `models_json_schema(..., ref_template="#/components/schemas/{model}")` 生成；测试断言每个 API 模型的组件 Schema 与单文件 Schema 在 `#/$defs/`→`#/components/schemas/` 重写后完全相等，全文无嵌套 `$defs`。
- paths：`POST /v1/ask` 200、`POST /v1/tasks` 202、`GET /v1/tasks/{task_id}` 200、`POST /v1/tasks/{task_id}/retry` 202、`POST /v1/feedback` 201；每个操作恰好一个成功码，`operationId` 唯一。管理、策略与回放端点不预置空路径，随其模型加入。
- 错误响应由 `core.errors.HTTP_STATUS` 推导：10 个状态码（400/401/403/404/409/422/429/500/503/504）各一个 `components.responses`，描述逐条列出映射到该状态的 `ErrorCode`，全部指向 `ErrorResponse`；每个操作列出全部 10 个，即统一错误处理器可能返回的并集，不臆造逐端点子集。
- `Idempotency-Key` 为可选请求头参数，仅挂在 `POST /v1/tasks` 与 `POST /v1/feedback`；描述写明作用域、同 payload 返回原回执（含处理中、不返回 409）、异 payload 返回 422 `idempotency_payload_mismatch`、同事务落库、保留期下限 86400 秒。
- 全局 `security: bearerAuth`（http bearer，OIDC）；测试断言无操作覆盖它，且所有请求体经 `$ref` 可达的属性名不含 `dept/scopes/user_id/sub`，顶层 `additionalProperties=false`。

约束：INV-AUTH-01（身份只来自 token）、INV-SAF-05（描述中写明不流式）、INV-DATA-03（历史版本显式选择器）、3.2 幂等语义；错误模型不外泄 detail（`ErrorResponse` 四字段断言）。

验证：新增 [tests/unit/api/test_openapi.py](../../tests/unit/api/test_openapi.py) 7 项（openapi-spec-validator 通过、`$ref` 全部可解析、操作表逐项匹配、错误响应推导、幂等头位置、安全与身份字段、组件与单文件 Schema 相等且导出最新）。变异自检：13 种坏文档（删一个错误码、请求体加 `dept`、放开 `additionalProperties`、幂等头挂错端点、去掉全局安全、单操作覆盖安全、双成功码、悬空 `$ref`、422 描述缺码、头改 cookie、非法参数位置、多出端点）每种至少被一项测试或规范校验器拒绝。

依赖：`pyproject.toml` dev 依赖新增 `openapi-spec-validator>=0.7,<1`；`make lock`（uv）后 `requirements.lock` 新增 8 个包（openapi-spec-validator 0.9.0、openapi-schema-validator 0.9.0、jsonschema-path 0.5.0、lazy-object-proxy 1.12.0、pathable 0.6.0、pyyaml 6.0.3、rfc3339-validator 0.1.4、six 1.17.0），既有 25 个包版本一条未动，`requirements-build.lock` 不变；venv 按锁安装后 `pip check` 无冲突。

未完成：M0-08 不勾选。成功状态码、retry 失败码、保留期配置值待审核（第 8 节第 2 问）；远端 CI 未运行。

风险：`retryTask` 非法状态用 `400 invalid_request` 是权宜（无专用错误码）；保留期只固定了下限。

## 4. 轮 2：canonical 已知答案向量（M0-06）

完成：[tests/unit/core/test_canonical_vectors.py](../../tests/unit/core/test_canonical_vectors.py) 固定 10 组输入的 canonical 字符串与 SHA-256（空对象/数组、嵌套键序、数字表示 `1.0`/`-0.0`/`1e+21`/`1e-07`/大整数/`1/3`、布尔与整数、NFC 与 NFD、星形字符与控制字符转义、按码点排序的键、空串与空格键）以及一组 `operation_key` 已知答案（`0e7dd6d5…5b44`）。另有两项性质测试：canonical_json 不做 Unicode 归一（NFC ≠ NFD，NFC 归一后相等，提醒调用方先做 norm-v1）；在 `PYTHONHASHSEED` 为 0、1、4294967295 的三个子进程中复算全部向量与 `operation_key` 一致。

约束：基线 3.2（canonical JSON、分隔符防歧义）；SPEC §4 `params_hash` 与 3.6 `retrieval_version` 依赖同一函数的字节稳定。

验证：15 项通过（含 3 个子进程）。期望值在 CPython 3.11.16 / macOS arm64 计算并写死；其他平台运行本套件即为跨平台证据。

未完成：M0-06 不勾选：Linux/Windows 证据待远端 CI；调用方纳入完整版本集合的检查属 M2-03。

风险：无新增已知风险。

## 5. 轮 3：草稿 canonical JSONL 重写命令（M1-01 配套，路线图 3.2 要求）

完成：[src/medops/evals/probe/canonicalize.py](../../src/medops/evals/probe/canonicalize.py)，`python -m medops.evals.probe.canonicalize <version_dir> [--check] [--pages DIR] [--schema-dir DIR]`，Makefile 目标 `canonicalize-probe`。

- 只对草稿生效：`manifest.status == draft` 且 `frozen_at` 为空且目录内无 `SHA256SUMS`，否则拒绝（退出码 2）。
- 只改表示与顺序：去 BOM、CR/CRLF→LF、删空行、键排序、紧凑、`ensure_ascii=false`、按 `sample_id`/`probe_id` 升序；写前重新解析输出并断言记录集（canonical 字符串多重集）与输入一致。
- 拒绝一切非表示问题：非对象行、无效 JSON、重复键（`json.loads` 默认静默保留后者）、NaN/Infinity（`json.loads` 默认静默接受）、缺 id、重复 id；全部文件先解析检查，任一失败则一个字节都不写；写入用同目录临时文件 + `os.replace` 原子发布。
- 不碰 `manifest.json`、`corpus.json`、`review_prompt.md`、`mappings/`；不“修正”gold：内容问题由写后自动执行的 draft 校验报告（退出码 1）。
- 行切分只认 CR/LF，字符串内的 U+2028/U+0085 不会被当作换行。

约束：SPEC §2（canonical JSONL 要求）、§9（冻结目录不可修改）、PR-01/PR-02。

验证：新增 [tests/unit/evals/test_canonicalize.py](../../tests/unit/evals/test_canonicalize.py) 15 项：乱序/反转键序/ASCII 转义/CRLF/空行/BOM 的草稿被重写为与 fixture 逐字节相同的 canonical 形式且 draft 校验 PASS、其余文件哈希不变、无临时文件残留；二次运行为 no-op；`--check` 不写并以退出码 1 标记待改；`acl_probes.jsonl` 同样排序与规范化；status=frozen、frozen_at 非空、SHA256SUMS 存在三种情况均拒绝且目录快照不变；六种坏行（非对象、无效 JSON、重复键、NaN、缺 id、重复 id）出现在第二个文件时第一个文件也不被写；非法 `dept` 被原样保留并由校验器报错；U+2028 保留。对 `examples/` 副本 `--check` 报告 unchanged。

未完成：M1-01 仍为部分/阻塞（真实语料、签字、原件存储、标注）。

风险：无新增已知风险。

## 6. 轮 4：进度文档刷新

- [路线图](../DEVELOPMENT_ROADMAP.md)：核查日期与复跑数字（259 passed、mypy 38 文件、示例 CLI PASS/17 警告）、C-05/C-08/C-09/C-10 证据更新、新增 C-11（领域契约，此前只在知识对照中有）与 C-12、3.2 的重写命令段落改为已交付、M0-06/M0-08 状态、8.3 第 2 步标记完成。
- [任务知识对照](../TASK_KNOWLEDGE_MAP.md)：核查日期、总览表（M0 已实现 5→7、部分 6→4；P0 已实现 6→8、部分 10→8）、C-12、M0-06/M0-08/M1-01 状态。
- [CONTRACTS.md](../api/CONTRACTS.md)：OpenAPI 已交付及成功码、幂等头、错误并集的约定。
- 路线图正文此前的“61 passed / mypy 15 文件”是记录 04 时的数字，与头部“207 passed”不一致，已统一为本轮实测并注明历史数字见各记录。

## 7. 验证汇总

```text
env -u PYTHONPATH make check
  install-check            -> medops importable outside the repo
  ruff check src tests     -> All checks passed!
  mypy                     -> Success: no issues found in 38 source files
  pytest -q                -> 259 passed（本记录新增 37：OpenAPI 7、向量 15、canonicalize 15）
  contracts_export --check -> schemas up to date（含 openapi.json）
python -m medops.evals.probe <examples 副本> --mode draft   -> PASS (draft); errors=0 warnings=17（/tmp 下、不设 PYTHONPATH）
python -m medops.evals.probe.canonicalize <examples 副本> --check -> samples.jsonl: unchanged (3 records)，exit 0
pip check -> No broken requirements found
docs/source/SHA256SUMS -> 2 项 OK
基线机械检查 -> INV 30 唯一、DEC 11、复选 99/0/0/0、围栏成对、相对链接 0 失效
```

改动文件：新增 `src/medops/api/openapi.py`、`src/medops/evals/probe/canonicalize.py`、`schemas/openapi.json`、`tests/unit/api/test_openapi.py`、`tests/unit/core/test_canonical_vectors.py`、`tests/unit/evals/test_canonicalize.py`、本记录；修改 `pyproject.toml`、`requirements.lock`、`Makefile`、`src/medops/contracts_export.py`、`src/medops/api/contracts.py`（仅模块文档）、`docs/api/CONTRACTS.md`、`docs/DEVELOPMENT_ROADMAP.md`、`docs/TASK_KNOWLEDGE_MAP.md`。Git 未提交。

## 8. 需要决策人决定

1. **格式检查进门禁（M0-03）**：`ruff format --check` 现在会重排 51/73 个文件。是否接受一次性格式化（建议单独一轮、单独提交，便于审阅），之后把 `ruff format --check` 加入 `make check` 与 CI？
2. **OpenAPI 约定**：(a) 成功码 `POST /v1/tasks` 与 retry 用 202、`POST /v1/feedback` 用 201、其余 200；(b) retry 非法状态返回 `400 invalid_request`，还是新增专用错误码（例如 `task_not_retryable`，409）；(c) `Idempotency-Key` 配置保留期的具体值（基线 3.2 要求写入契约，目前只写了下限 86400 秒）。
3. **新增 dev 依赖 openapi-spec-validator**（带入 pyyaml、six 等 7 个传递包，仅 dev）。替代方案是把 OAS 3.1 元 Schema（Apache-2.0）vendoring 进仓库用 jsonschema 校验。请确认接受哪种。
4. **阶段 2 的 PostgreSQL 环境**：本机无 Docker 与 PostgreSQL。可选：安装 Docker Desktop 或 OrbStack 后用现有 `make up`；Homebrew `postgresql@16` + pgvector；或允许把 `pgserver`（pip 内嵌 PostgreSQL，含 pgvector）作为测试依赖。选定并安装或授权后，M1-06/07/08 才能在本机验证。
5. **记录 12 §5 的四项**仍待答复：非现行仿單是否入 v1；cand-0034/0035/0037/0038 签字；`verified_by` 代号；欣服寧处置。原件复制到 `evals/probe/precise_clause/v1/sources/` 仍待你手动执行或授权。
6. **Redis 版本与许可**（记录 08 遗留）：`redis:7-alpine` 对应 7.4（RSALv2/SSPLv1），是否改用 7.2（BSD）并固定 digest。

### 8.1 结果（2026-09-17）

八项均按本记录与后续讨论中的建议执行，落实情况见[实现记录 15](2026-09-17-implementation-15-approved-follow-ups.md)：格式检查已进门禁；OpenAPI 成功码维持、新增 `task_not_retryable`（409）、保留期由 `IDEMPOTENCY_KEY_TTL_SECONDS` 配置并写入 OpenAPI；openapi-spec-validator 保留且 8 个包许可证已核对；PostgreSQL 采用 Docker Desktop 路线，安装为本机操作；语料原件已按 URL 重新取得并逐份核对哈希；Redis 固定为 7.2 并锁 digest。

## 9. Codex 审核焦点

- OpenAPI：组件与单文件 Schema 相等的断言是否足以证明“同一批模型”；错误响应“每操作列全部状态码”的取舍；`Idempotency-Key` 描述与基线 3.2 是否逐句一致；`retryTask` 400 的选择。
- 已知答案向量：所选输入是否覆盖 `json.dumps` 在不同平台可能分歧的点（浮点 repr、大整数、`-0.0`、`ensure_ascii=False` 下的星形字符）；期望值是否应另存为独立 JSON 供其他语言复用。
- canonicalize：全有或全无的实现（先解析全部再写）是否有遗漏的写路径；`utf-8-sig` 容错是否会掩盖真正的编码错误；行切分只认 CR/LF 的取舍；退出码约定（0 通过、1 校验失败或 `--check` 有变更、2 拒绝）。
- 锁文件：只新增 8 个包、既有 pin 未动、构建锁不变。
- 文档：路线图与知识对照的状态口径是否夸大（“已实现”均限定了范围并写明不勾选）。

## 10. 自审（基线 §9）

1. 需求：只覆盖 M0-08、M0-06、M1-01 配套与文档；未扩展医学能力、数据范围或基线契约。
2. 逻辑：OpenAPI 无手写 Schema，全部由模型或 `HTTP_STATUS` 推导；canonicalize 先检查后写、原子发布、记录集自检；向量只读。
3. 安全：请求体无身份字段有测试；错误响应结构上无 detail；canonicalize 对冻结目录默认拒绝。
4. 契约：OpenAPI、单文件 Schema、模型三者由测试绑定；CONTRACTS.md 同步；Makefile 帮助同步。
5. 测试：正常、边界、失败、变异（13 种坏文档）、拒绝路径（9 种）、幂等/重复运行、hash seed 变化均覆盖。
6. 可观测：CLI 输出逐文件状态与记录数；无新增运行时路径。
7. 简洁性：`openapi.py` 只有构建函数与三个小助手；`canonicalize.py` 单模块单 CLI，不做标注平台；未加其他抽象。新依赖仅 dev，且列为待批准。
8. 验证：见第 7 节；未验证项：远端 CI、非 macOS 平台、Docker/PostgreSQL 相关一切。
9. Checklist：基线勾选保持 0；路线图与知识对照按证据更新状态，均标注“不勾选”。
