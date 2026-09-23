# 实现记录 58：API 首切片——`/v1/ask`、身份边界与生产装配（M3-01、M3-05、M3-12 部分）

- 日期：2026-09-23（晚）
- 范围：M2 剩余项都依赖安全集决策或 M3 持久化，按路线图进入 M3。本切片交付 FastAPI 应用的 `POST /v1/ask`（成功 / 证据不足 / 拒答 / 升级 / 服务失败五种契约）、bearer token 身份边界（OIDC 兼容校验 + 服务端 principal 目录 + HMAC 假名 + group allowlist）、健康与就绪探针，以及把状态机、检索栈、Gateway、operation key 账本接成一个可启动的生产运行时（`python -m medops.api.serve`）。
- 依据：基线 2.3（INV-AUTH-01/02/03）、2.5（INV-OBS-02）、3.7（每请求事务、`set_config` 注入身份）、5.7、5.12、§8 M3-01/05/12；[ADR-0001](../adr/ADR-0001-identity-oidc-boundary.md)（OIDC 边界、`sub` 只识别用户、目录映射、测试签发器）；`docs/api/CONTRACTS.md` 与 `schemas/openapi.json`（M0-08 定稿的契约）。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| 新增依赖 `fastapi`、`httpx`（TestClient）、`pyjwt[crypto]`、`uvicorn`；`make lock` 重新生成三份哈希锁 | 基线技术栈指定 FastAPI；JWT 校验选 PyJWT（维护活跃、支持 JWKS、无框架绑定）——不是 DEC-010 的 IdP 选择，只是库 |
| 身份解析顺序：Authorization 头 → 签名/issuer/audience/expiry/`kid`/算法白名单校验 → `sub` 的 HMAC-SHA-256 假名 → principal 目录（未登记或停用一律 `403 forbidden`）→ group claim 只经 allowlist 变成 scope | ADR-0001 §1–§4；INV-OBS-02 假名带密钥；默认拒绝 |
| principal 目录落库（迁移 0009 `principals`）：应用角色只读、管理角色写、只读角色无权限；行只停用不删除；scope 形状由不可变函数 `medops_scopes_valid` 检查 | INV-AUTH-01「部门与 scope 由服务端目录/数据库映射」；INV-AUTH-05 角色分离 |
| 每个请求：一条应用角色连接 + 一个事务；身份解析在事务内、部门注入用事务级 `set_config` 之后才构造检索与账本；异常回滚 | 3.7 RLS 运行条件；M2-03 账本与请求同事务 |
| 拒答与升级的映射：升级原因全部落在 {`high_risk_medical`, `prompt_injection`, `acl_denied`} 时返回 `refused`，否则 `escalated`（`escalation_id` = trace_id）；每个 reason code 一句固定公开文案，内部 detail 不外泄 | 5.5 与契约 `AskResponse` 只允许一种负载；高风险问题在运行内仍留升级记录 |
| 错误契约：`MedOpsError` → `HTTP_STATUS[code]` + `ErrorResponse`；请求体校验失败 → `422 schema_violation`；未知异常 → `500 internal_error` 通用文案；所有响应带 `X-Trace-Id` | 5.12；`core.errors` 的公开模型 |
| 显式历史版本选择器（`historical.version`）暂返回 `400 invalid_request`，`as_of` 生效 | 状态机只支持 `as_of`；版本选择随 M3-03 的任务接口 |
| 生产运行时把 torch 调用固定到单线程（`medops.retrieval.pinned`，从记录 54 的工具实现搬入 src）并接 `PgExecutionStore` | 记录 54 §3.0 的驱动卡死；M2-03 生产接线 |
| 运行时配置新增 `OIDC_ISSUER` / `OIDC_AUDIENCE` / `OIDC_JWKS_JSON` / `OIDC_GROUP_SCOPES_JSON`（`.env.example` 已列，均可选；生产装配缺任一项即启动失败） | ADR-0001 §4 测试签发器；INV-AUTH-01 |

## 2. 交付

- `src/medops/api/auth.py`：`JwtVerifier`（JWKS、RS256/ES256、必需 claim）、`pseudonym`、`Principal` / `StaticDirectory` / `PgDirectory`、`Authenticator`。
- `src/medops/api/app.py`：`create_app(runtime)`，`ApiRuntime` 协议，trace 作用域中间件，错误处理，`/v1/ask`、`/healthz`、`/readyz`；`to_ask_response` 的结果映射。
- `src/medops/api/runtime.py`：`ProductionRuntime.from_settings`（连接、目录、身份注入、检索栈、Gateway、账本、版本集）；`src/medops/api/serve.py`。
- `src/medops/retrieval/pinned.py`（+3 项测试）；`migrations/versions/0009_principals.py`；`Settings` 四个 OIDC 字段。
- 测试：`tests/unit/api/test_auth.py` 8 项（有效 token、错 issuer / audience / 过期 / 未知 kid / 非白名单算法 / 他人密钥签名、缺头或畸形头、未登记与停用、allowlist、假名）；`tests/unit/api/test_ask_route.py` 7 项（answered 含版本与 trace 头且账本记录五个节点、证据不足升级、高风险与注入拒答且零模型调用、运行内模型故障为升级、运行前服务故障为 503 公开契约、Schema / 身份字段 / 无 token / 未登记 / 历史版本、健康与就绪）；`tests/integration/test_principals.py` 3 项；迁移清单、往返与 RLS 集合更新到 0009。`make check`：全部通过。

## 3. 顺带发现并修复：`intent-rules-v2`

写拒答路径的测试时用了自然的问法「我最近血压 150/95，我应该每天吃多少 losartan？」，v1 规则未识别为高风险（要求「我」后面紧跟情态词）。「我每天該吃多少」「我可以自己加量到」同样漏判。v2 允许主语、情态词、动词之间各有少量副词成分，并把「停药」「加量」纳入；新增 4 条正例与 3 条第一人称文档问题的反例（不得误判）。这是安全集（M2-15）应覆盖的类别，本记录先把已知漏洞补上。

## 4. 未做 / 限制

- JWKS 只支持静态配置（JSON），未实现从 issuer 发现端点拉取与轮换缓存；IdP 厂商未选（DEC-010）。
- `/v1/ask` 的真实 HTTP 冒烟未跑（需要一份 principals 记录与本地签发器配置）；本记录的契约证明在 TestClient + 假运行时层。
- 会话（`session_id`）未实现；反馈、任务、管理与回放接口（M3-02/03）未开始；Trace/升级/审计落库（M3-07）未开始，因此拒答与升级目前只在响应与账本里可见。
- Skill 走 API 的入口（`POST /v1/tasks`）随 M3-02。

## 5. 自审（§9）

- 身份只能由 `Authenticator` 构造，请求体的 `extra="forbid"` 拒绝 `dept` / `scopes`（测试）；未登记即 403，零模型调用。
- 事务与身份注入顺序：目录查询在 `set_config` 之前（principals 策略不依赖部门），检索与账本在之后。
- 公开错误无内部 detail（测试断言 `db down` 不出现在响应）；trace id 在中间件内绑定，错误响应也带头。
- 未改动已冻结数据、生产库与 `.env`（只改 `.env.example`）。

## 6. 进度

- M3-01 部分、M3-05 部分、M3-12 部分（健康 / 就绪探针）。P0 加权进度 47.5%（37.5/79）；按 99 项计 37.9%。分项：M0 10/11、M1 16.5/21、M2 9.5/16、M3 1.5/13、M4 0/10、M5 0/8。
