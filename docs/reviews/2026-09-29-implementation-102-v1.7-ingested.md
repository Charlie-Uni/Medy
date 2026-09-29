# 实现记录 102：候选清单 v1.7 签字执行——26 份入库激活、三份暂缓、10% 抽样待签

日期：2026-09-29。决策人对记录 101 §4 的 v1.6 签字表回复「**可以签字**」。本记录是签字回填与零费用入库流水线的执行结果；付费步骤仍未启动。

## 1. 签字回填

- [v1.7](../../evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.7.md)：cand-0348～0374 中 **26 条 `eligible`**（FDA PV 官方指南 12、TFDA 仿單 14），逐条 `reviewer_note` 写明签字依据与入库前置条件；**cand-0357 保持 `needs_review`、不入库**（文本层「reproduced with permission … W.B. Saunders Company」，第三方教科书图表；决策人未单独表态，可另行裁决）。v1.6 JSON 保留签字前快照；ADR-0003 追加「白名单补件许可裁决（2026-09-29）」。`test_candidate_lists.py` 19 通过（id 跨版本指向同一文档）。

## 2. 入库前核查（26 份）

| 步骤 | 结果 |
| --- | --- |
| 重新下载比对 | 26/26 SHA-256 与签字清单相等。FDA 站点对并发请求再次返回 404（4 份首轮失败：cand-0348/0351/0355/0358），单线程退避重试后全部成功；签字副本未被覆盖 |
| 页文本抽取 | `python -m medops.evals.probe.extract` 26/26 成功；pypdf 告警 2 份（cand-0364 抑痛寧 2 条、cand-0374 鹽酸氯普魯麻淨 4 条）；空白页 1 份（cand-0367 第 2 页，印刷稿背面） |
| 乱码扫描 | 26 份逐页 0 页超过 2% 阈值（IPA / 修饰符号 / 组合符号区） |
| 产品身份 | 14 份仿單的英文品名或成分名均在页文本中找到；cand-0366 页面印作 "Antoohin"（資料集 ANTOCHIN），中文品名与成分 indomethacin 一致，判为同一产品。12 份 FDA 指南标题词首页命中 4/4 以上 |
| 图像层核查 | [tfda_image_layer_check_2026-09-29.md](../../evals/main_set/tfda_image_layer_check_2026-09-29.md)：14 份 28 页 14 张检视图全部目视，13 份通过；**cand-0371 美贊錠** 第 1 页廠商地址栏末尾有单独的 Ⓒ 记号（200 dpi 裁切确认，无年份、无权利人、无声明文字；同厂 cand-0372 同位置为 Ⓐ，判为印刷版次代号），按 ADR-0003 条件 3 从严：入库不激活，待决策人裁决 |
| PII 复核 | [pii_review_2026-09-29.json](../../evals/main_set/pii_review_2026-09-29.json)：`pii-rules-v1` 在 12 份 FDA 指南命中 38 处，全部为 FDA 机构职能信箱（druginfo / ocod / faersesub / esub / esghelpdesk 等），无个人公务信箱；14 份仿單无命中。全部判为误报并留档 |

## 3. corpus v3、激活计划与两库入库

- [corpus_v3.json](../../evals/main_set/corpus_v3.json)：`build_corpus.py --base-corpus corpus_v2.json --dataset-version main-v3-provisional`，339 份 = 313（逐字承接 v2）+ 26；Schema 校验通过、`document_key` 无重复；`verified_at = 2026-09-29`。FDA 键取标题主干 + 年份（两份 Real-World Data 指南以年份区分：`fda-real-world-data-2023` / `-2024`）。
- [activation_plan_2026-09-29.json](../../evals/main_set/activation_plan_2026-09-29.json)：`documents` 23 条（FDA 取指引总表 issue 日期所在月首日，与记录 96 口径一致；仿單优先取版本行民國日期 2 份，其余取 PDF 元数据日期 12 份）；`held_back` 3 条：cand-0371（Ⓒ 记号）、cand-0364 与 cand-0374（入库时 pypdf 告警落为 `low_trust`，INV-DATA-05 只允许 trusted 激活；按记录 96/99 口径不用 `--accept-quality` 放行，需决策人签字后按 `-r2` 流程重新入库）。
- 入库：`python -m medops.ingestion.load --corpus corpus_v3.json --only <26 键> --admin-url <medops_v2 / medops_v2_safety 管理 DSN> --accept-pii <12 条，引用 pii_review_2026-09-29.json>`，两库各 26 份 `ingested`（24 trusted + 2 low_trust）；`activate --plan` 两库各 23 份 `activated`（首次执行因计划含 low_trust 文档被整体拒绝，拆出后重跑）。
- 现状：**medops_v2 active 330（MA 122 / PV 127 / CO 81）**，draft 6（3 份本批暂缓 + 3 份旧 low_trust），archived 7，withdrawn 5；**medops_v2_safety active 336** = 330 + 6 份 `sf-*` 合成注入文档，两库 active 键集除 `sf-*` 外相同。决策 86 的 320（MA 120 / PV 120 / CO 80）在数量上已达到；M5-01 仍不勾选，理由见 §5。

## 4. 10% 抽样（待签字）

[qa_sample_2026-09-29.md](../../evals/main_set/qa_sample_2026-09-29.md)：从 26 份中抽 10 份（MA 5 / PV 5，种子 20260929，每份 ≤ 3 个抽查页）；LLM 预检 10/10 机械核对与目视通过（不计作人工复核）；「结论」列待决策人或指定复核人填写。

## 5. 需要决策人

1. **cand-0371 美贊錠**：Ⓒ 记号按印刷版次代号处理并激活，还是撤回？建议：激活（同厂 cand-0372 同位置为 Ⓐ，且资料集 9117 的 OGDL-1.0 授权与仿單内是否印有版次记号无关）。
2. **cand-0364 抑痛寧、cand-0374 鹽酸氯普魯麻淨**：pypdf 告警 2 / 4 条，页文本机械核对与目视均正常；是否签字 `--accept-quality` 放行（按记录 99 的 `-r2` 流程重新入库并激活）？建议：放行。
3. **10% 抽样签字**（§4）。签字后零费用冻结 `main-v3-provisional`（339 份，614 条样本不变，`supersedes = main-v2-provisional`）。
4. 充值后再开付费运行（记录 101 §5 的顺序）：主集全量 + 安全集 → replay-v2 → 两臂门禁 → 候选提交（带 `case_ids` 与新门禁）→ 批准 → 金丝雀。

## 6. §9 自审

- 只从已签字的 v1.7 `eligible` 候选入库；cand-0357 未入库；三份存疑 / 低信任文档入库为 draft 不激活，未用任何放行开关。
- 入库与激活全部经审计路径（load / activate），两库用显式 `--admin-url`，开发库 `medops` 未触碰。
- 冻结的 `main-v2-provisional` 与 `corpus_v2.json` 未改；v3 只追加。
- 口令、DSN 未出现在记录、日志或提交中；未启动付费运行。

## 7. 追记：门禁实测

`env -u DEBUG -u PYTHONPATH make check`：ruff、mypy、pytest **1263 passed / 70 skipped**（集成测试连库）、Schema 无漂移、`git diff --check` 通过；记录内链接全部存在。
