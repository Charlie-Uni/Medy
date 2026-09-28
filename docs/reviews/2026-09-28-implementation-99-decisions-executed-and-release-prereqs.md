# 实现记录 99：五项批复的执行、两库语料同步与发布前置条件核查

日期：2026-09-28。决策人对记录 97 §4 / 记录 98 §4 的五项事项批复（发布按建议处理；low_trust 五份按建议签字放行、ADR-0009 拒收三份不豁免；安全库同步；10% 复核由谁完成待答；开发库多余 draft 清理）。本记录是执行结果与执行中发现的两处规则约束。

## 1. 执行结果

| 批复 | 执行 | 核对 |
| --- | --- | --- |
| 5. 清理开发库多余 draft | `medops` 开发库（alembic 0007，仅 15 份探针期 active 文档，无 traces / policies 表）中当日误入的 231 份 draft 全部按 M1-11 `withdraw_document` 撤回（draft → withdrawn，审计 `document_withdrawn`，actor reviewer-01） | 文档表：active 15 / draft 1（09-17 旧有，非本轮）/ withdrawn 231；未删除任何行（迁移 0011/0016/0017 使文档与审计表追加写，迁移 0019 的删除路径只对超过保留期的 Trace 类数据开放） |
| 2. low_trust 五份签字放行 | 入库幂等规则按 `source_hash + document_key + version` 短路，已存在的 low_trust 记录无法原地升级；按现有规则：撤回旧 draft，以记录键 `<key>-r2`、`version_label` 追加「质量复核 2026-09-28」重新入库，`--accept-quality`（审计 `quality_review_override`）+ `--share-source`（同一源对象的第二份记录，管理员确认，审计 `source_share_confirmed`），再按计划激活 | medops_v2：5 份 `-r2` 均 trusted、active；旧 5 份 withdrawn。corpus_v2.json 与激活计划同步改键（`quality_reviewed_r2`） |
| 2. ADR-0009 拒收三份 | 不豁免；保持未入库 | 计划 `held_back` 剩 3 条 |
| 3. 安全库同步 | `medops_v2_safety` 入库 234（226 trusted + 3 拒收，与主库一致），激活 226；5 份 `-r2` 同样入库激活 | 安全库 active 313 = 主库 307 + 6 份合成注入文档（`sf-*`）；两库 active 键集除 `sf-*` 外完全相同 |
| 4. 10% 逐页复核 | 已做 LLM 预检（机械核对 + 抽查页目视），写入 [qa_sample_2026-09-28.md](../../evals/main_set/qa_sample_2026-09-28.md) 末节；「结论」列留给人工 | 23/23 无问题；cand-0254 为投影片（信息量低）已注明 |
| 1. 发布路径 | 未提交候选，原因见 §3 | — |

主库现状：medops_v2 active **307**（MA 111 / PV 115 / CO 81）、archived 7、withdrawn 5、旧 low_trust draft 3；对决策 86 目标 320（120/120/80）仍差 MA 9、PV 5。

## 2. 关于「10% 复核由我还是你来完成，有什么区别」

- 决策 86 C.3 与 spec-m1 §4 写的是**人工**逐页复核，LLM 不计作人工（manifest `review_policy` 明确「不等同于人工复核」）。我做的只能记为「LLM 预检」，冻结 `main-v2-provisional` 前仍需一个人在「结论」列签字（可以是决策人本人，也可以指定 annotator-01）。
- 区别在证据效力：人工签字后语料可冻结进入正式集；只有 LLM 预检时，冻结版本必须像现在一样标 provisional，并在报告里写明。
- 建议：决策人抽看 5～8 份（每部门至少 1 份）后在表上签字，其余采信 LLM 预检并注明；这样既满足人工复核的形式要求，又不必逐页看完 23 份。

## 3. 发布前置条件：两处规则约束与费用

1. **INV-EVAL-01 禁止把回放项登记为 bad_case。** `medops.loop.adapt` 的隔离检查拒绝任何引用 `rp-/rs-/ms-/pc-/ss-` 编号或回放查询原文的候选；记录 92 归因的 60 条失败项正是回放项，不能作为证据。合规路径是 Loop 自己的案例：`observe → reflect` 从 Trace 生成 `bad_cases`（uuid），候选 `evidence.case_ids` 引用它们。现状：medops_v2 有 231 条 Trace，但 `bad_cases` 为空、`policies` 只有 09-25 的回滚演练；`.env` 未配置 `DATABASE_LOOP_URL` / `DB_LOOP_PASSWORD`，`medops_loop_user` 未创建（记录 79–85 用的是测试库）。
2. **门禁报告必须来自将要发布所依据的回放集。** 已通过的报告（记录 97）在 replay-v1 上测得，而语料已从 76 份扩到 307 份，检索基线变了；按 2026-09-28 决策「先重冻结再金丝雀」，需要 replay-v2 上的新报告。重冻结流程（记录 79）：主集全量运行（614 条 ≈ 4.7 USD）+ 安全集运行（170 条 ≈ 0.65 USD）→ `build_replay_set.py` → 候选在 replay-v2 上跑两臂三轮（≈ 13 USD，baseline 不能复用）。合计约 18 USD；当前余额约 8 USD。
3. 因此发布路径的顺序是：人工签字 10% 复核 → 冻结 `main-v2-provisional`（零费用）→ 充值 → 全量运行与安全运行、构建 replay-v2 → 创建 loop 用户、`observe/reflect` 生成案例 → 候选带 `case_ids` 与新门禁报告提交 → 决策人批准（approver ≠ 作者）→ 金丝雀 ≤10% → 24 h 观察 → 全量。

## 4. 需要决策人

1. 充值与预算：为 replay-v2 重冻结与重测批准约 18 USD（含 M5-04 两候选另需约 13 USD）。
2. 指定 10% 复核的签字人与方式（§2 的建议）。
3. `medops` 开发库（alembic 0007）已无用途，是否整库删除（撤回已完成，删除是额外动作，需明确授权）。
4. MA / PV 缺口（9 / 5 份）：是否在白名单内再补一批（v1.6），或接受 307 份作为 M5-01 的规模。

## 5. §9 自审

- 全部数据库变更走审计路径（withdraw / load / activate），未直接改表；开发库未删除。
- 语料记录键变更（`-r2`）同步到 corpus_v2、激活计划与复核表，未改冻结的 v1。
- 规则约束如实上报，未绕过 INV-EVAL-01，未在余额不足时启动付费运行。
- `make check` 见 §6 追记。

## 6. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`：ruff、mypy、pytest **1254 passed / 70 skipped**（集成测试连库）、Schema 无漂移、`git diff --check` 通过；记录内链接全部存在。
