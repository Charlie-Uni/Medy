# 实现记录 45：M1-17 融合与重排、端到端运行（两种配置）、DEC-001 最终判定与生产词法接线（M1-14/15）

日期：2026-09-20。承接记录 41 阶段 5 与记录 42 的向量通道结果。决策人授权（"我需要的是结果 你来决定"）下，本记录作出 DEC-001 最终判定并完成生产接线。

## 1. 编码前记录

- 端到端定义（基线 M1-21、5.2；ADR-0002 修订 3；ADR-0007）：词法 top-20 + 向量 top-20 → RRF（k=60，只用排名）→ 融合 top-20 → 事实回查（应用角色身份事务，M1-18）→（可选）bge-reranker-v2-m3 重排已回查证据，输出 8 → 取 top-5 计严格宏平均 Recall@5；同时报告 Hit@5、融合 Recall@20、通道单独 R@5、回查丢弃、失效版本引用率、P95、复现性与管理侧泄漏检查；A2+V 与 B2+V 配对 bootstrap。
- 选择规则沿用 ADR-0002：挑战者相对 A 族需 ≥5 pp 且 CI 下界 >0，否则选择最简单实现；判定在端到端配置上作出（修订 3）。
- 两个系统各自与向量通道同库（5432/medops_v2 与 5433/medops_v2 均已构建 `emb-bge-m3-dense-v1`），chunk id 一致，融合无需跨库映射。

## 2. 实现

- [hybrid.py](../../src/medops/retrieval/hybrid.py)：`HybridConfig`（k 与上限校验、`rrf_params`/`candidate_limits` 供 `retrieval_version`）、`hybrid_search`（两通道各经边界、`rrf_fuse`）、`retrieve_evidence`（融合后回查，Evidence 唯一来源）。
- [rerank.py](../../src/medops/retrieval/rerank.py)：`RerankerSpec`、`Reranker` 协议、`rerank_evidence`（只接受已回查 Evidence，输入 ≤20、输出 8、并列按 chunk_id、分数数目校验）、`BgeRerankerV2M3`（固定修订 `953dc6f6…`，本地 CPU，max_length 512）、测试用 `OverlapReranker`。
- [e2e_run.py](../../src/medops/evals/experiments/e2e_run.py)：端到端运行框架（冻结 manifest、按 pass 播种、每查询一个身份事务、门禁视图、配对 bootstrap、报告、`--rerank`）。
- 生产接线（M1-14/15）：迁移 [0007](../../migrations/versions/0007_production_lexical_index.py)（`chunk_lexical_tsv` + `lexical_index_meta`，FORCE RLS）；[production.py](../../src/medops/retrieval/production.py)：固定 tokenizer `tok-jieba-v2` + 包内停用词表（SHA-256 `b3f772a0…6eac` 校验）、索引名 `production-lexical`、构建/检索/消费者目标、生产混合配置、复合 **`retrieval_version = 90b57e4e86b4bb462fc4de58f7f7749666fb6f50a588c129bd5f9aa50585ab18`**（单元测试钉住；任一成员变化即失败）；`make lexical-index`；六个本机库已迁移到 0007，`medops`/`medops_v2`（5432）已构建生产索引（2,661 / 2,662 chunk）。

## 3. 测试

- 单元：[test_hybrid.py](../../tests/unit/retrieval/test_hybrid.py)（3）、[test_rerank.py](../../tests/unit/retrieval/test_rerank.py)（2）、[test_e2e_run.py](../../tests/unit/evals/test_e2e_run.py)（3）、[test_production.py](../../tests/unit/retrieval/test_production.py)（4：成员取值、复合版本钉住、任一成员变化即换版、停用词表校验、向量提供者版本约束）。
- 集成：[test_lexical_production.py](../../tests/integration/test_lexical_production.py)：生产索引通过与 DEC-001 候选相同的适配器套件（14 项：零越权含计数、无静默少取、状态/窗口过滤、身份与版本拒绝、连接复用、执行计划、写保护）+ 消费者目标增删 + 停用词来源；迁移/RLS 期望更新（仅 `chunk_embeddings.embedding` 与 `chunk_lexical_tsv.tsv` 两个专用列）。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**872 passed**（629 单元 + 243 集成）。

## 4. 端到端运行结果（探针 v2，107 条，每条 1 gold，故 Recall@5 = Hit@5）

| 配置 | 系统 | Recall@5 全部 | language_matched | cross_lingual | 融合 R@20 | 词法单独 R@5 | 向量单独 R@5 | P95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 无重排（`2026-09-20-e2e-hybrid-v1`，2+3 pass） | A2+V | 54.2% | 64.0% | 31.2% | 79.4% | 38.3% | 70.1% | 165 |
|  | B2+V | 58.9% | 69.3% | 34.4% | 79.4% | 41.1% | 70.1% | 186 |
| 重排（`2026-09-20-e2e-hybrid-rerank-v1`，1+1 pass） | A2+V | **75.7%** | 81.3% | 62.5% | 79.4% | 38.3% | 70.1% | 7,567 |
|  | B2+V | **75.7%** | 82.7% | 59.4% | 79.4% | 41.1% | 70.1% | 8,877 |

- 配对 bootstrap（B2+V − A2+V，Recall@5，10,000 次）：无重排 +4.67 pp，95% CI [−1.87, +11.21]；重排 **+0.00 pp，CI [−2.80, +2.80]**。
- 完整性：两配置泄漏 0、不可复现 0、失效版本引用 0/535、回查丢弃 0（索引已在查询内过滤状态与窗口）。
- 重排把 Recall@5 从 54–59% 提到 75.7%，与融合 Recall@20 79.4% 的差距缩至 3.7 pp；分部门 MA 93–97%、PV 77.8%、CO 53–56%；切片 time_window 100%、dose_unit 94.7%、drug_name_zh 89–94%、negation 82–84%、mixed_zh_en 71–72%、protocol_id 48–52%；gold 为英文文档 61–63%、中文 94–100%。
- 延迟：CPU 上 cross-encoder 对 ≤20 候选打分均值约 5 s，P95 7.6–8.9 s，超出基线 5.11 普通问答 P95 ≤ 8 s 的预算；需要 GPU/MPS 推理、缩短 `max_length` 或减少重排输入（如 12）——作为 M2/M3 的性能项处理，不改变本判定。
- **基线 M1-21 门禁（Recall@5 ≥ 85%）在探针规模未通过**（75.7%）；失效版本引用率 0 与零越权通过。剩余差距集中在 CO 的英文 GCP/ICH 文档与方案编号精确匹配；主评测集（M1-20，≥300 条）建立后重判。

## 5. DEC-001 最终判定

**选定 A2（PostgreSQL `simple` FTS + 应用侧 jieba `tok-jieba-v2` + 固定英文停用词表）为生产词法引擎。** 依据：

1. 预登记选择规则：B2 相对 A2 在两种端到端配置下均未达到"≥5 pp 且 CI 下界 >0"（+4.67 pp CI 含 0；重排后 +0.00 pp）；规则要求此时选择最简单实现。
2. 运维：A2 只需标准 PostgreSQL（含 pgvector 镜像即可）与 MIT 许可的 jieba；B2 需要 zhparser + SCWS 扩展与自建镜像；C 已按修订 4 排除。
3. 词法通道单独表现（语言一致 Recall@20：A2 77.3%、B2 80.0%）的差距在融合与重排后消失；B2 在 drug_name_zh/zh-Hant 上的优势（94% vs 89%）保留为后续主评测集上的复核项——若 ≥300 条主集上 B2 满足选择规则，可另行修订。
4. 可逆：适配器契约不变，切换到 B2 只需替换 `production.py` 的 tokenizer/表与迁移中的索引表，索引重建由 outbox 消费者与 `make lexical-index` 完成。

## 6. 自审（基线 §9）

1. 需求：M1-17 融合与重排；M1-21 端到端指标与切片报告；M1-14/15 生产接线与版本固化；DEC-001 按预登记规则判定。
2. 逻辑：Evidence 只经回查产生；重排只对已回查证据；复合版本包含全部八个成员。
3. 安全：应用角色执行；泄漏检查 0；生产表 FORCE RLS；停用词表哈希校验。
4. 契约：新增模块不改既有契约；`dec001_run.Searcher` 放宽为协议。
5. 测试：新增 12 单元 + 16 集成；全量 872 passed。
6. 可观测：两次运行的 manifest/results/report 与配对检验入库。
7. 简洁性：混合、重排、生产配置各一个模块。
8. 验证：数字来自 report.md/results.json。
9. Checklist：M1-14 待做 → 已实现；M1-15 部分 → 已实现；M1-17 部分（融合/重排/回查已有，并行/超时/降级随 M2）；M1-21 待做 → 部分（工具与报告已有、门禁未过）；**进度 32.9%（26/79），按 99 项计 26.3%**。

## 7. 下一步

M1-20 主评测集（≥300 条）；重排延迟优化（设备/长度/输入数）；术语表启用评测（记录 44）；M2 执行器（并行通道、总超时、降级）。
