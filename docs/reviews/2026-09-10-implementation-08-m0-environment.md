# 实现记录 08：M0 工程环境——依赖锁、配置示例、最小 Compose、威胁模型（2026-09-10）

按基线第 9 节交付格式。范围：M0-02、M0-09、M0-11（最小形态）；不建 API/worker 空壳，不新增平台组件。**当前状态：第三版已通过 Codex 复核；锁工具与 Compose 阶段范围已获人工批准，Redis 版本与许可仍待确认。** 下文第一至第三版保留各轮当时记录，最新批准范围见末节。

## 完成

| 条目 | 产物 | 说明 |
| --- | --- | --- |
| M0-02 依赖锁 | `requirements.lock`（24 个包，全部带 sha256 哈希） | 由 `uv pip compile pyproject.toml --extra dev --python-version 3.11 --generate-hashes` 生成，输出为 pip 兼容格式；CI 与 `make install` 改为 `pip install -r requirements.lock` 加 `pip install --no-deps -e .`；`make lock` 重新生成。本地 venv 已同步到锁（ruff 0.16.6、mypy 2.3.1、pydantic 2.13.5、pydantic-settings 2.15.0） |
| M0-02 配置 | `src/medops/core/config.py`、`.env.example` | pydantic-settings `Settings`：`extra="forbid"` 拦截拼写错误；`PostgresDsn/RedisDsn` 校验；秘密字段为 `SecretStr` 并在 repr/dump 中掩码；空值 `KEY=` 视为未设置；prod 禁止 debug、交互文档与 DEBUG 级别并要求假名密钥（INV-OBS-02）。示例文件只含 change-me 占位，DEC-007/009/010 相关键明确延后 |
| M0-02 密钥排除 | `.gitignore` 增加 `.env`、`.env.*`（保留 `.env.example`）；`tests/unit/docs/test_repo_hygiene.py` | 测试断言 .env 被忽略且未被跟踪、跟踪文件中无 sk-/AKIA/私钥头模式、锁文件覆盖 pyproject 全部声明依赖且含哈希 |
| M0-11 最小 Compose | `docker-compose.yml`、`deploy/postgres/init/01-extensions.sql`、`make up/down/ps` | 只含 PostgreSQL（pgvector/pgvector:pg16）与 Redis 7；口令来自 .env 且缺失即报错；端口只绑定 127.0.0.1；健康检查、命名卷、Redis AOF、优雅停机宽限；初始化只启用 `vector` 扩展，角色与 RLS 留给 M1 migration |
| M0-09 威胁模型 | `docs/THREAT_MODEL.md` v0.1 | 八条信任边界的数据流；七类风险各对应攻击面、基线条款、已有测试或规划里程碑；列出未覆盖项与维护规则 |

## 自审（基线第 9 节）

1. 需求：只覆盖 M0-02/09/11；未扩展医学能力或数据范围；Compose 未包含未决的对象存储与未存在的服务。
2. 逻辑：`Settings` 空秘密归一为未设置，避免 `KEY=` 通过存在性检查；Compose 口令用 `${VAR:?}` 强制提供。
3. 安全：示例文件无真实密钥；`.env` 被忽略并有测试；端口仅本机；prod 硬化由校验器强制。
4. 契约：新增依赖 pydantic-settings 已进 pyproject 与锁；CI 与 Makefile 同步改为锁安装。
5. 测试：正常、边界（空秘密、未知键、错误 DSN）、失败（prod 违规）、仓库卫生、锁覆盖；Compose 只有静态校验。
6. 可观测：无新增运行时路径；Settings 未接日志级别，留待入口接线。
7. 简洁性：无新抽象；`database_admin_url` 为 3.7 角色分离预留字段，当前无消费者，已注明。
8. 验证：见下；**本机无 Docker，Compose 未实际启动**。
9. Checklist：不勾选。M0-02 缺“干净环境可安装”的远端证据；M0-11 缺启动、健康与重启证据；M0-09 为 v0.1，随组件补行。

## 验证

```text
env -u PYTHONPATH make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!（ruff 0.16.6）
  mypy                    -> Success: no issues found in 29 source files
  pytest -q               -> 143 passed in 2.95s（本轮新增 8 项）
uv run --with pyyaml python -c "<parse docker-compose.yml>"
  -> 2 services, healthchecks present, ports bound to localhost, named volumes（静态校验）
docker compose up        -> 未运行：本机无 Docker
```

## 待批准的选型点

1. 依赖锁工具：用 uv 作为编译器、输出 pip 兼容的 `requirements.lock`（带哈希），不把 uv 作为运行时依赖；可换 pip-tools 得到等价文件。
2. 镜像：`pgvector/pgvector:pg16` 与 `redis:7-alpine`；PostgreSQL 大版本 16 是本轮假设，DEC-001/002 若需要特定扩展镜像（如 pg_search、zhparser）再改。
3. Compose 范围：只含基础设施，端口只绑本机，对象存储等 DEC-007。

## 待 Codex 审核的重点

1. `Settings` 的 `extra="forbid"` 与 Compose 变量共存的方式（把 POSTGRES_* 纳入模型）是否合理，或应拆成独立文件。
2. `.env.example` 的内联注释在 python-dotenv 与 docker compose 两种解析器下是否一致。
3. 仓库卫生测试的密钥模式是否够用；是否需要覆盖 `.pth`/二进制之外的更多类型。
4. Compose 健康检查命令在 pgvector 镜像与 redis alpine 镜像下是否可用（本机无法验证）。
5. 威胁模型第 2 节各行的测试映射是否有夸大“已有”的地方。

## 第二版：按 Codex 审核修订（2026-09-10）

Codex 结论为“暂不通过”；四项必修与两项补充全部处理。**状态：待 Codex 复核。**

| Codex 发现 | 修复 | 回归测试 |
| --- | --- | --- |
| 连接串密码未掩码：三个 DSN 出现在 repr、dump、JSON、日志与校验异常中 | DSN 改为 `SecretStr` 存储，格式仍由 `PostgresDsn/RedisDsn` 的 TypeAdapter 校验，校验失败只抛“value withheld”并 `hide_input_in_errors=True`，异常不回显输入；消费者显式 `get_secret_value()` | `test_dsn_passwords_are_masked_everywhere_and_available_on_request`（repr、str、dump、JSON、经 redact 的日志字典五个面）、`test_invalid_dsn_error_does_not_echo_the_value` |
| 密钥扫描只看已跟踪文件，新增测试里的合成密钥提交后会让 CI 失败 | 扫描范围改为 `git ls-files --cached --others --exclude-standard`（已跟踪加未忽略的新文件）；测试中的合成密钥改为运行时拼接（`"sk-" + "..."`），仓库文本不再含密钥形状字符串 | `test_no_secret_patterns_in_tracked_or_stageable_text_files` |
| 安装链路未锁构建依赖：pip 无上限升级；editable 安装经构建隔离重新解析 setuptools；锁校验不逐包 | pip 固定 26.2.1（Makefile `PIP_VERSION` 与 CI 同步）；`setuptools>=68,<85` 进入 dev 依赖并被锁定为 84.0.0；editable 安装改为 `--no-build-isolation --no-deps`；CI 增加 `pip check`；锁校验改为逐包统计 `--hash` 行数，任一包缺哈希即失败，并有对解析器本身的单元测试 | `test_lock_pins_every_declared_dependency_with_hashes_per_package`、`test_lock_hash_check_detects_a_missing_hash` |
| 威胁模型把约定写成已实现 | 三处状态文字改为“数据契约，不能保证服务端构造（M3）”“工具已有，运行时强制携带未接线（M2-03）”“错误码已有，禁止作答的执行门禁未实现（M2/M3）” | 文档 |
| 两种解析器差异；未知键语义 | `.env.example` 写明不用引号与 `${VAR}`，口令用随机十六进制并与 DSN 同步；`config.py` 文档写明未知键拒绝只对 dotenv 与显式输入有效，未知进程环境变量被忽略 | `test_unknown_process_env_is_ignored_but_unknown_dotenv_key_is_rejected` |
| 仓库出现 `uv.lock` 与 `.venv/` | 确认来自 `uv run --with pyyaml` 在项目内自动创建；已删除，`uv.lock` 加入 .gitignore（单锁策略）并有测试；后续一次性运行使用 `uv run --no-project` | `test_env_files_are_ignored_and_untracked` |

路线图 C-10 的“尚无依赖锁”已更正。Compose 中 Redis 镜像加注：`7-alpine` 当前对应 7.4 系列（RSALv2/SSPLv1），版本与许可待决策人确认，实验冻结时固定 digest。

验证：`env -u PYTHONPATH make check` 通过（pip 26.2.1、setuptools 84.0.0、`pip check` 无损坏依赖）；pytest 147 passed（本轮新增 4 项）。Compose 仍未在本机运行。

## 第三版：收口安装链路与配置错误输出边界（2026-09-10）

Codex 复核关闭了新增文件扫描、合成夹具、逐包缺哈希检测、威胁模型更正、dotenv 说明与双环境清理；剩余两处如下。**状态：待 Codex 复核。** 更正：第二版起 `requirements.lock` 为 25 个包（新增 setuptools），第一版的 24 为当时实测，不改写。

| Codex 发现 | 修复 | 证据 |
| --- | --- | --- |
| `pip install -r requirements.lock` 仍开启构建隔离，jieba 只有源码包，其构建依赖在隔离环境中重新解析，不受锁约束 | 新增 `requirements-build.in` 与带哈希的 `requirements-build.lock`（setuptools 84.0.0，与主锁同版本，有测试保证一致）；安装顺序改为：固定 pip → 按哈希装构建后端 → 以 `--no-build-isolation` 装主锁 → 以 `--no-build-isolation --no-deps` 装项目 → `pip check`；Makefile、CI 同步，CI 加 `--no-cache-dir`；`make lock` 同时重生成两个锁 | 干净环境实测（/tmp 新建 venv，`--no-cache-dir`）：构建后端安装成功 → `Successfully built jieba` → 25 包安装成功 → 项目安装成功 → `pip check` 无损坏 → 仓库外导入通过，jieba 0.42.1、setuptools 84.0.0；环境已删除 |
| `hide_input_in_errors` 只保护 `str(error)`；`errors()`/`json()` 及交给 JSON 日志的结构化形式仍含密码 | 不改写 Pydantic：新增 `safe_config_errors()` 作为配置错误唯一允许的结构化形式（`errors(include_input=False, include_context=False, include_url=False)` 并只保留 loc/type/msg）；模块文档写明入口接线时禁止直接记录原始 `.errors()`/`.json()` | `test_structured_error_output_contract`：原始形式含密码（特征化断言，说明不安全）；安全形式与经 `redact` 的安全形式均不含密码 |

验证：`env -u PYTHONPATH make check` 通过；pytest 149 passed（本轮新增 2 项）。Compose 仍未在本机运行。

复核结论（2026-09-10，Codex）：第三版两处问题关闭，切片内无新阻塞项；通过范围仅限本轮实现，不代表远端 CI、Docker 启动或整个 M0 已验收；后续入口必须使用 `safe_config_errors()`。三项选型（uv 编译锁与 pip 安装、仅基础设施 Compose、Redis 版本与许可）仍待决策人批准。

## 人工批准记录（2026-09-10）

项目负责人在上述复核后回复“批准”，按上一轮建议的边界落实为：

- 已批准：uv 编译带哈希锁文件、pip 安装；当前 M0 切片的 Compose 仅含基础设施。
- 仍待人工确认：Redis 具体版本、镜像 digest 与许可证适用性；本次不改镜像标签。
- 不包含：完整 M0 验收、后续轮次审核、Git 提交/推送或部署授权；基线 checklist 不变。

决策及后续边界见 [ADR-0004](../adr/ADR-0004-m0-tooling-and-compose-scope.md)。
