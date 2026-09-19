# 实现记录 15：已批准事项落地（格式门禁、OpenAPI 约定、依赖许可、Redis 锁定、语料原件重取）

日期：2026-09-17。范围：落实决策人对[实现记录 13 第 8 节](2026-09-17-implementation-13-goal-confirmation-and-m0-closure.md)与[记录 14 第 5 节](2026-09-17-implementation-14-retrieval-version-composite.md)的批复。五个小轮次各自独立验证；未修改基线、SPEC、Schema 规则；未提交 Git；未替决策人签字任何候选。**状态：待 Codex 审核。**

## 轮 A：格式化与格式门禁（M0-03）

完成：`ruff format src tests` 一次性重排 58 个文件（比记录 13 预估的 51 个多出本日新增文件）；Makefile 新增 `format-check` 并纳入 `make check`；CI 增加 `ruff format --check src tests` 步骤。

验证：格式化后 `ruff check` 通过、`ruff format --check` 80 个文件全部已格式化、pytest 287 passed，行为无变化。

发现并修正：经写文件工具写入的三个测试源文件中，`\u001f`、`\u0301`、`\u2028`、`\u0085` 形式的转义在写入环节被解码成了不可见的字面字符（共 7 处），ruff 本身不做此转换（已用最小样例验证）。已把它们改回可见转义，并对 `src/`、`tests/` 全量扫描控制字符、组合字符、行分隔符与零宽字符，结果为 0。今后凡含此类转义的源码一律经 Python 生成写入，不经写文件工具。

未完成：M0-03 只剩 migration check，随 M1-06 建立。

## 轮 B：OpenAPI 约定（M0-08）

完成：
- `core/errors.py` 新增 `ErrorCode.task_not_retryable`，类别 domain，HTTP 409；`POST /v1/tasks/{task_id}/retry` 在任务非 "failed 且 retryable" 时返回它，不再借用 `400 invalid_request`。
- `Settings.idempotency_key_ttl_seconds`（默认 604800 秒即 7 天，下限 86400 秒由 `ge` 强制）；`.env.example` 增加 `IDEMPOTENCY_KEY_TTL_SECONDS=604800`；OpenAPI 的 `Idempotency-Key` 描述写明由该配置决定、默认值与下限。
- 成功状态码维持 202（创建任务、重试）、201（反馈）、200（其余）。
- `schemas/` 重新导出：`ErrorResponse` 与 `openapi.json` 的 `ErrorCode` 枚举、Error409 描述随之更新；[CONTRACTS.md](../api/CONTRACTS.md) 同步。

验证：`test_openapi.py` 的幂等头描述断言新增 `604800`；错误码测试的映射完整性、类别与状态码一致性断言覆盖新码；`contracts_export --check` 无漂移；全套 287 passed。

## 轮 C：dev 依赖许可证核对（记录 13 第 8 节第 3 问）

用 `importlib.metadata` 读取本机安装元数据：

| 包 | 版本 | 许可 |
| --- | --- | --- |
| openapi-spec-validator | 0.9.0 | Apache-2.0 |
| openapi-schema-validator | 0.9.0 | BSD-3-Clause |
| jsonschema-path | 0.5.0 | Apache-2.0 |
| lazy-object-proxy | 1.12.0 | BSD-2-Clause |
| pathable | 0.6.0 | Apache-2.0 |
| pyyaml | 6.0.3 | MIT |
| rfc3339-validator | 0.1.4 | MIT |
| six | 1.17.0 | MIT |

结论：全部为宽松许可，仅进入 dev 依赖；保留。

## 轮 D：Redis 镜像锁定（M0-11、记录 08 遗留）

完成：`docker-compose.yml` 改为 `redis:7.2-alpine@sha256:ccd6aa8d45ff3f033d6fa15b8cc1a50579f65c89f38cf9bb607a954c4f2128ed`。digest 为 2026-09-17 从 Docker Hub registry API 解析的多架构索引，当时 `7.2-alpine` 对应 `7.2.16-alpine`；Redis 7.2 系列为 BSD-3-Clause，7.4 起为 RSALv2/SSPLv1。注释写明标签与 digest 必须一起升级。

验证：本机无 Docker，仅用 PyYAML 静态解析 compose（镜像字段、健康检查、仅本机端口）；实际启动待 Docker Desktop 安装后在阶段 2 完成。

## 轮 E：语料原件重取与持久化（M1-01 前置；记录 12 第 6 节阻塞解除）

背景：记录 12 存放原件的 `/tmp/medy-corpus-research.ji2oNC/` 与上个会话 scratchpad 均已不存在。

完成：
- 按候选清单 v0.4 的 `pdf_url` 重新下载 10 份（cand-0026～0031 已签字六份；cand-0034/0035/0037/0038 待签字四份），逐份计算 SHA-256 并与 v0.4 `notes` 中记录的"下载 sha256"比对：**10/10 一致**，即 MedDRA、ICH 与 TFDA 六个仿單链接当前提供的字节与 2026-09-11/12 完全相同。
- 持久化到 SPEC 第 2 节指定的本地目录 `evals/probe/precise_clause/v1/sources/`，文件名为 `<source_hash>.pdf`，另附 `SOURCES.index.json`（候选号、标题、URL、哈希、字节数、下载日期）。该目录已在 `.gitignore`，`git status` 确认不可跟踪。本次写入未被权限分类器拦截。
- 用锁定的 pypdf 6.18.1 抽取页文本到 `evals/probe/precise_clause/v1/pages/<source_hash>/<page>.txt`，并把 `evals/probe/precise_clause/v*/pages/` 加入 `.gitignore`（第三方文本不进 Git）。

抽取结果与记录 12 逐项复现：

| 候选 | 页数 | 空页 | 抽取告警 |
| --- | ---: | --- | ---: |
| cand-0026 MedDRA 术语选择 | 61 | 无 | 0 |
| cand-0027 MedDRA 数据检索 | 49 | 无 | 0 |
| cand-0028 ICH E8(R1) | 29 | 第 2、6 页 | 0 |
| cand-0029 美洛醣 | 2 | 无 | 0 |
| cand-0030 安通脈 | 13 | 无 | 33 |
| cand-0031 吉福坦 | 2 | 无 | 0 |
| cand-0034 痛風停 | 10 | 无 | 0 |
| cand-0035 穩壓 | 1 | 无 | 0 |
| cand-0037 心壓暢 | 2 | 无 | 0 |
| cand-0038 胃所樂 | 4 | 无 | 8 |

`params_hash` 十份一致（`7c3f1766…6b8d`），说明抽取参数与记录 12 相同。cand-0030/0031 已按决策不进入 v1 主体，仍保留原件以备"历史版本"样本决定。

未完成：cand-0034/0035/0037/0038 的文内版本行核对与签字仍待决策人；`corpus.json`、标注与冻结未开始。

### 轮 E 补充：TFDA 现行性复核（2026-09-17 17:31 快照）

重新下载 `https://data.fda.gov.tw/data/opendata/export/36/json`（zip sha256 `ff39d1f98ff341e3d2521f6280e2f0399e7e0c8b7e94bbd6b1205a13e5bfbce7`，内层 `36_5.json` sha256 `738075819a70ee583450f1a2bb87ccf2218f5f14cc1e724bb5b65504e0eed16e`，72,057 行）与 `export/39/json`（zip sha256 `f0bb02742b8238e03dd5b8c6ccace3984b0ef01f292140c15603194975429f21`，内层 `39_5.json` sha256 `67572df10d1a3e9c0061782e9280c8ec946458b81fb4a89b87592600ff091ca9`，29,873 行）。两个数据集自 2026-09-12 起已更新（行数分别 +14、+13），但下列五条记录的结论不变：

| 候选 | 許可證字號 | 註銷狀態 | 有效日期 | 許可證異動日期 | export/39 仿單連結是否仍指向本地已核验的 PDF |
| --- | --- | --- | --- | --- | --- |
| cand-0029 美洛醣 | 衛部藥製字第058257號 | 现行 | 2029/04/21 | 2023/12/29 | 是 |
| cand-0034 痛風停 | 衛署藥製字第048564號 | 现行 | 2027/01/30 | 2026/07/20 | 是 |
| cand-0035 穩壓 | 衛署藥製字第047911號 | 现行 | 2031/03/30 | 2026/04/02 | 是 |
| cand-0037 心壓暢 | 衛署藥製字第029301號 | 现行 | 2029/11/28 | 2024/12/05 | 是 |
| cand-0038 胃所樂 | 衛部藥製字第058102號 | 现行 | 2028/10/18 | 2023/05/19 | 是 |

边界：export/39 只有 `仿單圖檔連結`，没有仿單修订日期字段；"该 PDF 修订版现行"的可得证据是"监管方今日登记的仿單链接就是本地这份文件，且字节与 09-12 一致"。`異動日期` 是许可证记录的异动日期，不是仿單修订日期。文内版本线索：只有 cand-0035 印有 `B版 104.10.27`，其余三份只有许可证号。四份签字后将以候选清单 v0.5 追加本节证据并填写 `reviewer_decision`。

### 轮 E 补充 2：候选清单 v0.5（决策人 2026-09-17 批复签字）

决策人对"签字 cand-0034/0035/0037/0038 并按建议 reviewer_note"回复"可以，那就继续吧"。据此生成 [DEC-011-candidates-v0.5.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.5.json) / [.md](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v0.5.md)：四份 `reviewer_decision=eligible`，`reviewer_note` 逐条记录许可依据、export/36 与 export/39 同日快照的现行性证据、文内版本线索、文本层页数与告警；cand-0029/0034/0035/0037/0038 各追加两条 2026-09-17 快照证据（locator 含 zip 与内层 JSON 的 sha256 和记录序号，quote 为记录字段原文或仿單链接原文）；cand-0030/0031 的 `reviewer_note` 登记"不进入 v1 主体"的决定；其余字段与 v0.4 逐字相同。Schema 校验与 v0.1～v0.5 跨版本 id/标题一致性测试通过。已签字 `eligible` 共 10 条，v1 主体可用 8 份：MA 5、PV 2、CO 1。若决策人事后不认可其中任一签字，以 v0.6 撤回，不改写 v0.5。

## 验证汇总

```text
env -u PYTHONPATH make check
  ruff check        -> All checks passed!
  ruff format --check -> 80 files already formatted
  mypy              -> Success: no issues found in 39 source files
  pytest -q         -> 287 passed
  contracts_export --check -> schemas up to date
不可见字符扫描（src/ tests/）-> 0
语料哈希比对 -> 10/10 MATCH；v1 目录 git 不可跟踪
```

## 需要决策人操作或决定

1. 安装 Docker Desktop 并启动一次（首次需在图形界面接受条款），之后我用 `make up` 拉起 PostgreSQL/pgvector 与 Redis 进入阶段 2。
2. 对外描述修订稿定稿后告知，我再归档为 `docs/source/PROJECT_DESCRIPTION_v0.2.md`。
3. cand-0034/0035/0037/0038 的签字：原件与页文本已就绪，我下一轮先做文内版本行核对并把结果列给你。

## 自审（基线 §9）

1. 需求：只落实已批复事项；未新增门禁，未扩展数据范围（10 份均为清单内已批准或待签字文档）。
2. 逻辑：新增错误码与状态映射有完整性测试；保留期下限由 Settings 强制而非仅文档。
3. 安全：原件与页文本均在忽略目录，`git status` 验证；`.env.example` 无真实密钥；许可证逐包核对。
4. 契约：ErrorCode、OpenAPI、单文件 Schema、CONTRACTS.md 同步；compose 静态解析通过。
5. 测试：格式化前后测试集不变；新增断言覆盖 604800；错误码映射测试覆盖新码。
6. 可观测：无新增运行时路径。
7. 简洁性：无新抽象；`SOURCES.index.json` 只是本地清单。
8. 验证：见上；未验证项：Docker 启动、远端 CI。
9. Checklist：基线勾选保持 0；路线图与知识对照按证据更新。
