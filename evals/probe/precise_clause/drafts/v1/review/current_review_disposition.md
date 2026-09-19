# 当前复核与冻结状态

核查日期：2026-09-20（Australia/Sydney）。用户已同意上轮三项具体方案，并要求每轮自审；两条改题已重新独立复核，另一条已绑定人工裁决。

探针集 `v1` 已**冻结并完成 Git 归档**：75/75 条当前输入均有真实独立复核，**71 条 agreed、4 条 disputed_resolved、0 条待决**。16 份文档及 75 条样本的正式带页文本 frozen 校验通过，PR-01～PR-14 为 0 findings。**Git 归档提交为 `213dbe8ead8ff92d8919b201460ac3a961176c8c`**，基础依赖已在祖先 `2a4aef6` 归档，独立 checkout 复验通过。

| 类型 | 样本 | 当前处理 |
| --- | --- | --- |
| 已裁决 | pc-0026 | 服用时限题保持已批准的 span，不扩前句人群/液体限制；本轮锚点已获 ok |
| 已裁决 | pc-0027 | 年龄标题有抽取伪影，不放入 gold；不将进一步检查条件解释为固定疗程 |
| 已裁决 | pc-0038 | 年度文档更新频次不加 dose_unit；缩短后的锚点已获 ok |
| 改题后 agreed | pc-0052 | 已改为安全性报告模板是否继续使用旧词 side effect 的情境题，采用 200 字符锚点，原完整 span 保留；真实重审 agree |
| 改题后 agreed | pc-0066 | 已改为研究中心实报实销合理路费/住宿费的情境题，key/span/标签不动；真实重审 agree |
| 已裁决 | pc-0074 | 人工同意保留逐字核验正确且唯一的 [940,1125)；LLM 建议的 [914,1099) 不匹配，原文与坐标保持不变 |

全部 4 条裁决均绑定当前 input/verdict 哈希和具体争议范围。复核历史保留 130 次成功调用记录，当前 75 条结果使用各样本最后一次调用；修改输入不能沿用旧判定，也不能通过回退 latest 指针隐藏后续争议或空结果。

## PII 与模型记录边界

- **pc-0046 的精确 PII 例外已生效。** 沿用[记录 21 的人工决定](../../../../../../docs/reviews/2026-09-17-implementation-21-pii-release-withdrawn-status.md)，仅覆盖 `pc-0046-g1` 的 `evidence_span.text` 中机构功能邮箱 `emerging-safety-issue@ema.europa.eu`，字段内区间为 `[293,328)`。例外同时绑定来源哈希、完整字段哈希、检测规则、精确匹配及人工依据文件哈希，已进入 `manifest.files` 与 `SHA256SUMS`。页文本和 span 未修改；`pii-rules-v1` 不变，其他命中仍默认拒绝。
- **模型版本按真实证据记录。** `model_version` 为 `service-alias:gpt-6-astra;backend-version:not-exposed`，effort 为 `high`；CLI `0.154.0-alpha.6.2` 单独记录。后端模型版本未暴露，不能据此声称固定模型快照或再次调用同一后端。8 件运行证据已复制到冻结目录 `review_evidence/`，由 manifest 中的哈希绑定，不再依赖会继续变化的 drafts 文件证明本次冻结。

## 冻结标识与后续步骤

| 记录 | 值 |
| --- | --- |
| `dataset_version` / 冻结日期 | `v1` / `2026-09-20` |
| `dataset_hash` | `5561bee58e37cd8d86b756f17e6c1a6ebed32ba54ba2ac48f4cd4adee254db7e` |
| `manifest.json` SHA-256 | `062f9a536e0d811306f80dd5c24cc44f40a39a8f36ac360959c4de99b1faf54b` |
| 冻结归档 Git commit | `213dbe8ead8ff92d8919b201460ac3a961176c8c` |

Git 归档及 [ADR-0002](../../../../../../docs/adr/ADR-0002-lexical-retrieval-selection.md) 实际提交哈希回填已完成；现已进入 [DEC-001 实验准备](../../../../../../evals/experiments/lexical/README.md)。实验尚未运行，无生产实现选择。冻结 `v1` 的后续数据修正必须创建新版本。

## 证据入口

- [Git 归档回执](git_archive_2026-09-20.json)、[本地冻结时的历史摘要](local_freeze_summary_2026-09-20.json)、[正式 frozen 校验](frozen_validation_2026-09-20.json)
- [冻结 manifest](../../../v1/manifest.json)、[SHA256SUMS](../../../v1/SHA256SUMS)、[PII 逐命中裁决](../../../v1/pii_exceptions.json)
- [冻结人工裁决](../../../v1/review_evidence/resolutions.json)、[冻结模型运行元数据](../../../v1/review_evidence/reviewer_runtime_metadata.json)
- [最后三项批准落地](approved_final_changes_2026-09-20.json)、[pc-0074 偏移核验](pc-0074_offset_check_2026-09-20.json)
- [每轮自审与验证记录 26](../../../../../../docs/reviews/2026-09-20-implementation-26-probe-review-and-freeze.md)

冻结时的全套软件检查为 **482 passed（418 单元 + 64 PostgreSQL 集成）**，类型、格式与 Schema 同步检查通过；数据冻结另有上述正式校验报告。测试通过和探针冻结不等于词法召回指标已经达标。

归档和下一阶段代码验证见[实现记录 27](../../../../../../docs/reviews/2026-09-20-implementation-27-archive-and-experiment-preparation.md)：549 passed（485 单元 + 64 PostgreSQL 集成），冻结 v1 内容未修改。
