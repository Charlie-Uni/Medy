# 实现记录 101：Loop 用户与案例生成、候选清单 v1.6（白名单内补批）

日期：2026-09-29（工作自 2026-09-28 晚开始）。决策人对记录 99 §4 / 记录 100 §3 的批复：给出充值网址；「开始」= 创建 loop 用户并从 Trace 生成 Loop 案例；旧开发库 `medops` **不删除**（作为 v1.0 上传后再删）；MA / PV 缺口「按照你的建议来」= 在白名单内再补一批（v1.6）。本记录是零费用部分的执行结果；付费步骤未启动。

## 1. Loop 用户：两处既有缺陷与修复

1. 记录 79 写明「登录用户脚本新增可选 loop 用户（`DB_LOOP_PASSWORD`）」，但 `Settings` 没有 `db_loop_password` 字段、`login_users.main` 也没有把它交给 `provision`；`.env` 一加 `DB_LOOP_PASSWORD` 就被 `extra="forbid"` 拒绝（`extra_forbidden`），loop 用户从未能由脚本创建（记录 79–85 用的是测试库里由 fixture 直接调用 `provision` 建的用户）。修复：`Settings.db_loop_password`（SecretStr，纳入「空值即未设」校验器，顺带补上遗漏的 `db_restricted_password`）；CLI 把 `loop` 口令传入 `provision`，可选用户（restricted / loop）缺口令不再阻塞必需的三个用户。测试：`tests/unit/infrastructure/test_login_users_cli.py`（3）、`tests/unit/config/test_settings.py` 新增 1。
2. Observe / Reflect / Tickets 三个 CLI 的 `--dry-run` 在 `conn.transaction()` 块内调用 `conn.rollback()`，psycopg 3 抛 `ProgrammingError: Explicit rollback() forbidden within a Transaction context`，dry-run 从未能跑通。改为 `raise psycopg.Rollback`；`tests/unit/loop/test_cli_dry_run.py`（3，伪连接按 psycopg 的 transaction 契约验证 dry-run 回滚、正式运行提交）。
3. 执行：`MEDOPS_MIGRATION_URL=<medops_v2 管理 DSN> python -m medops.infrastructure.db.login_users` → 四个登录用户就位，新增 `medops_loop_user`（成员 `medops_loop_role`；角色为集群级，迁移 0016 已建）。`.env` 增加 `DB_LOOP_PASSWORD` 与指向 medops_v2 的 `DATABASE_LOOP_URL`（口令不入记录）。验证：以 loop 用户连接 `current_user = medops_loop_user`、`current_database = medops_v2`；集成测试 `test_loop_signals / test_rls / test_loop_role_permissions` 59 通过。

## 2. 从 Trace 生成案例（medops_v2，Loop 角色）

Trace 现状：2026-09-24 13 条；2026-09-25 218 条；部门 MA 231。

| 步骤 | 结果 |
| --- | --- |
| `observe --since 2026-09-24`（先 dry-run 后正式） | scanned 231 / opened 31 / already_open 0 / skipped_no_signal 193 / skipped_kind 7；label bad 29（reason `escalated_insufficient_evidence`）、good 2（`feedback_up`） |
| `reflect run` | scanned 29 / attributed 29 / left_open 0；全部归因 `retrieval`（规则归因，`human_override` 为空） |
| `tickets` | scanned 29 / not_knowledge_gap 29；未开文档票 |
| `adapt propose --min-support 3` | 1 条提案：attribution retrieval / dept MA / 29 个 case_id；`auto_diff` 为空（通道 k 已在上限 20），`needs_author = true`，提示「rrf_k / reranker 变更需要作者候选」 |

`bad_cases` 31 行（MA：bad 29 已归因、good 2 未归因）。`policies` 表仍只有 09-25 演练的 `rolled_back` 记录。

## 3. 候选提交文件（未提交）

[2026-09-29-retrieval-bundle.submission.json](../../evals/replay/candidates/2026-09-29-retrieval-bundle.submission.json)：kind / name / diff 与 2026-09-26 的检索四件套候选完全一致；`evidence.case_ids` = §2 的 29 个 uuid；`evidence.cases` 记录案例来源；`evidence.gate = null`，`gate_note` 说明 replay-v1 上通过的报告（记录 97）不作为发布依据，须在 replay-v2 上重测后填入。离线 `validate_candidate`（diff 形状、`from` 值与 released 现值核对、`case_ids` 形态、隔离检查含回放查询原文）通过，版本将为 `hybrid@<提交日>-c41bd6d8`。**未执行 `adapt submit`**：等 replay-v2 门禁报告与决策人批准。

## 4. 候选清单 v1.6（白名单内补批，待签字）

输入（同日下载，哈希留档）：

| 文件 | sha256 |
| --- | --- |
| FDA 指引总表 `search-for-guidance.json`（2,790 行） | `fef58be1469cb68a17c403bc961ad948330572953dbab15d6d3e07c2769d6224` |
| TFDA 資料集 39 `39.zip` / `39_2.csv`（29,921 行） | `aee50292055432c58c51337af5f050ac1f427ffd4c6c8af09be79d5587647b78` / `edbdf663712b9b630e4e38dfa9ab5150cdc059821ead0c59e568e4af2c087d08` |
| TFDA 資料集 36 `36.zip` / `36_2.csv`（83,536 行） | `0eb8811bcbe59433fff7cbd8580c12ccb24413ce554fbe3290331df60320a31e` / `4257bb38c58d0c97d09400f058a85d734e17e7210c85fbf3703e4c5faec833bd` |

工具：`seed_candidates_v12.py` 新增 `--groups`（只播 fda + tfda_label）、`--skip-inns`（跳过 132 个成分：v1.2 试过的 110、清单已有仿單的成分、原语料 22）、`--today`（现行性过滤与快照同日）、`--fda-media`（按 media id 指定 FDA 文件）；`compile_candidates.py` 新增 `--record`，表头「承接」版本改取自 base JSON（此前写死 v1.1 / 记录 89）。种子 76 条：FDA PV 13（record 89 §2.4 名单中尚未列入的 PV 官方文件，均为 Final）+ 仿單 25 个成分 × ≤ 3 备选 63 条。

结果（[v1.6.json](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.6.json) / [签字表](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.6.md)，承接 v1.5 的 347 条全部原样）：新增 27 条 cand-0348–0374，一批。

| 分组 | 条数 | 预判 | 说明 |
| --- | ---: | --- | --- |
| FDA 指南（PV） | 13 | eligible 12、needs_review 1 | cand-0357《Evaluating the Risks of Drug Exposure in Human Pregnancies》文本层出现「reproduced with permission … W.B. Saunders Company」，为第三方教科书图表，与 cand-0114 同理**建议不入库**；其余 12 份含 E2B(R3) FDA 区域实施指南、IND 安全性报告三份、REMS 文件电子递交、组合产品上市后安全性报告、DHCP 信函、RWD 登记 / 病历理赔两份、获益-风险评估 |
| TFDA 仿單（MA） | 14 | eligible 14 | 成分：amisulpride, benzbromarone, chlorpromazine, clozapine, flupentixol, indomethacin, ketorolac, mefenamic, nabumetone, oxybutynin, paliperidone, piroxicam, probenecid, sulpiride；条件 (1)(2) 对 09-29 快照机械证明，图像层目视与署名在签字后入库时完成 |

丢弃 23：扫描件 15、超出上限 7、同成分低序 1；4 个成分三档备选全为扫描件（baclofen, oxcarbazepine, tizanidine, tolterodine），超出上限未评估的成分 7 个（amitriptyline, buspirone, clomipramine, doxepin, fluvoxamine, imipramine, zopiclone）。

若 27 条全部签字并通过入库核查：medops_v2 active 由 307（MA 111 / PV 115 / CO 81）变为 MA 125 / PV 127 / CO 81 = 333，MA、PV 均超过决策 86 的 120。

证据页 2026-09-29 复核：FDA Website Policies（WebFetch，页面 last updated 2024-01-19，公共领域引文一致）；data.gov.tw 資料集 9117（WebFetch：授權方式「政府資料開放授權條款-第1版」、主要欄位与引文一致，詮釋資料更新 2026-09-15）；fda.gov.tw 網站資料開放宣告、著作權聲明、mcp.fda.gov.tw 页脚、OGDL 条款（curl，引文片段逐一命中）。发现自 v1.2 起著作權聲明引文漏掉「即著作人為本署者」一句，本版起逐字引用；该句限定的是本署著作，仿單的许可依据是資料集 9117 的 OGDL-1.0 条款而非该声明，已签字裁决不受影响。ADR-0003 追加执行记录。

## 5. 未做、保持与建议顺序

- 未启动任何付费运行；余额约 8 USD。充值：<https://platform.openai.com/settings/organization/billing/overview>（platform.openai.com → Settings → Billing → Add to credit balance）。
- 开发库 `medops` 保留，按决策在 v1.0 上传后再删。
- 建议顺序调整：先完成 v1.6 签字与入库（重下载比对 → 页文本 → 仿單图像层目视 → PII → `build_corpus.py --base-corpus corpus_v2.json` → 两库入库激活 → 10% 抽样签字 → 冻结 main-v3-provisional），**再**做付费的主集全量运行 + 安全集运行 + replay-v2 + 两臂门禁；否则 27 份入库后又要再冻结、再花约 18 USD 重跑。充值可先做，运行等 v1.6 入库后再开。

## 6. §9 自审

- 修的是记录 79 已声明却未落实的功能与 dry-run 从未跑通的缺陷，都有测试钉住；未改 Loop 的规则（归因、隔离、门禁）。
- 案例生成只用 Loop 角色，写入 `bad_cases` / 无票；提交文件离线验证但未 submit，评估证据仍空。
- v1.6 只从已签字来源补件，`reviewer_decision` 为空；证据页当日复核，引文差异如实记录并修正；候选 id 延续 v1.5，测试 `test_candidate_lists.py` 通过。
- 口令、DSN 未出现在任何记录或日志。

## 7. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`：ruff、mypy、pytest **1262 passed / 70 skipped**（集成测试连库）、Schema 无漂移、`git diff --check` 通过；记录内链接全部存在。
