# 实现记录 98：M5-01 语料入库与激活——medops_v2 现有 302 份 active 文档

日期：2026-09-28。承接记录 96（入库准备）。检索候选评测结束后执行数据库入库与激活。

## 1. 结果

| 项 | 数量 |
| --- | ---: |
| 入库对象（corpus_v2 新增） | 234 |
| `ingested`（draft） | 231 = trusted 226 + low_trust 5 |
| `refused`（ADR-0009 恶意内容策略） | 3 |
| 按激活计划激活（draft → active） | 226 |
| 新增 chunk | 23,076（含 low_trust 5 份） |
| medops_v2 现状 | active 302（MA 107 / PV 114 / CO 81）、archived 7、draft low_trust 8（旧 3 + 新 5） |

与决策 86 目标（320：MA 120 / PV 120 / CO 80）相比：CO 已达，MA 缺 13，PV 缺 6。缺口来源：签字后排除的 8 份乱码 / 身份不符仿單、3 份策略拒收、5 份 low_trust（全部有明确原因，见下）。

## 2. 三类未激活文档

| 类别 | 文档 | 处置 |
| --- | --- | --- |
| ADR-0009 拒收：`pdf.launch` | fda-meta-analyses-of-randomized-controlled-clinic-draft-2018（cand-0214） | 未入库。PDF 含 Launch 动作；策略正确拒收，不豁免 |
| ADR-0009 拒收：`pdf.javascript` | tfda-label-plusdmax-tablets-sinphar（cand-0314） | 未入库。仿單 PDF 含 JavaScript；不豁免 |
| ADR-0009 拒收：`pdf.embedded_file` | fda-providing-submissions-in-electronic-format-2015（cand-0218） | 未入库。含嵌入文件；不豁免 |
| `low_trust`（pypdf 字体告警，INV-DATA-05） | fda-reports-on-the-status-of-postmarketing-study-commit-2006（cand-0220）、tfda-label-carvedil-tablets-25mg（0269）、tfda-label-quimadine-f-c-tablets-20mg-famotidine（0279）、tfda-label-arizole-orally-disintegrating-tablets-10（0294）、tfda-label-acylete-tablets-200-mg-acyclovir（0324） | 保持 draft。与记录 49 口径相同：只能由决策人签字后以 `--accept-quality` 重新入库；本轮页文本已做逐页字形扫描（记录 96 §3），五份均无乱码页，可作为签字依据 |

激活计划文件 [activation_plan_2026-09-28.json](../../evals/main_set/activation_plan_2026-09-28.json) 拆为 `documents`（226 条已激活）与 `held_back`（8 条，含原因）。

## 3. 入库过程中的一次操作失误（已纠正，无损害）

`medops.ingestion.load` 的管理员连接默认取 `.env` 的 `DATABASE_ADMIN_URL`（指向开发库 `medops`），主集语料在 `medops_v2`。第一次入库落到了 `medops`（231 份 draft），第二次因 shell 替换在 BSD sed 下未生效再次落到 `medops`（全部报 `exists`），第三次以 `MEDOPS_MIGRATION_URL` 显式指向 `medops_v2` 后成功。后果：开发库 `medops` 多了 231 份 draft（未激活、不参与任何评测），本轮未清理，留待决策人决定是否用保留清除路径处理；三次运行的审计记录均在各自库的 `doc_audit`。改进：入库脚本应显式传 `--admin-url`，已写入记录 96 §7 的命令模板。

## 4. 未做与下一步

1. **安全库 `medops_v2_safety` 未同步**：安全集的预期（`must_cite` 等）基于旧语料；同步新语料会改变安全集结果，应与主集 / 回放集重冻结一并做，需决策人确认顺序。
2. **10% 逐页人工复核**（[qa_sample_2026-09-28.md](../../evals/main_set/qa_sample_2026-09-28.md)，23 份）尚未完成；完成前 `corpus_v2` 保持 `main-v2-provisional` 草稿，不冻结。
3. 检索基线随语料变化：已通过门禁的检索候选（记录 97）若发布，回放集需在 `corpus_v2` 上重跑 baseline。
4. `medops_v2` 的 `alembic` 版本未变（0019）；无 schema 变更。

## 5. §9 自审

- 拒收与 low_trust 均按既有策略处理，未加豁免；激活只覆盖 trusted draft。
- 失误如实记录，开发库的多余 draft 未隐瞒、未擅自删除。
- 数字来自数据库查询与入库日志，可复现。
