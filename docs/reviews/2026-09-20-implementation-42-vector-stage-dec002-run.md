# 实现记录 42：M1-16 向量阶段（迁移 0006、pgvector 适配器、bge-m3 提供者）与 DEC-002 向量通道运行

日期：2026-09-20。承接记录 41 阶段 2（ADR-0007）。本轮建立向量阶段的全部实现并完成预登记的向量通道运行。

## 1. 编码前记录

- 目标（基线 3.7、3.8、5.2；ADR-0007；路线图 M1-16）：DEC-002 已决后建对应维度 migration 并记录模型/归一化/版本；pgvector 检索在权限过滤下用 iterative scan 并报告实际候选数；零越权、无静默少取、版本不匹配拒绝，与词法适配器同一套硬门禁。
- 不变量：合格候选 = 具备当前 `embedding_version` 向量且经 RLS 链可见、`status='active'` 且生效窗口含 `as_of` 的 chunk；返回数必须等于 `min(K, 合格数)`，否则失败关闭；分数并列按 `chunk_id`；索引元数据是"已构建"的唯一事实，查询侧 spec 任一字段不同即拒绝。
- 范围外：Reranker（M1-17/M2）、融合与端到端（阶段 5）。

## 2. 实现

- 迁移 [0006_chunk_embeddings.py](../../migrations/versions/0006_chunk_embeddings.py)：`create extension if not exists vector`；`embedding_index_meta`（模型、修订、维度=1024 约束、归一化、截断长度、框架、计数、构建者）；`chunk_embeddings(chunk_id, embedding_version, vector(1024))` 主键复合、HNSW 余弦（m=16, ef_construction=64）；两表 FORCE RLS，普通角色经 `chunks` 可见性只读，管理角色维护；降级不删扩展（可能预先存在）。六个本机库已迁移到 0006。
- [retrieval/vector/](../../src/medops/retrieval/vector/)：`contracts.py`（`VectorVersions`、`VectorSearchResult` 与词法契约同一组不变量、`VectorRetriever`）；`embedding.py`（`EmbeddingSpec`、`EmbeddingProvider`、测试用 `HashingEmbeddingProvider`、生产 `BgeM3EmbeddingProvider`：固定修订 `5617a9f6…`、L2 归一化、`max_seq_length=1024`、CPU 默认、懒加载）；`pg_vector.py`（`build_index` 只补缺、同版本异 spec 拒绝；`PgVectorRetriever`：`require_identity`、元数据全字段比对、同事务精确合格计数、`hnsw.iterative_scan=relaxed_order` 与自适应 `ef_search`、页长校验失败关闭、`explain`）；`boundary.py`（`run_vector_search`，与词法边界同规则）。
- [dec002_run.py](../../src/medops/evals/experiments/dec002_run.py)：复用 DEC-001 框架的加载、按 pass 播种、汇总与管理侧泄漏检查（`dec001_run.Searcher` 改为结构化协议以同时接受词法/向量结果）；冻结 run_manifest（数据集哈希、映射哈希、provider spec、服务器事实、HNSW 定义）后才执行；输出 results/report/per_query_recall 与各部门默认执行计划证据。
- 依赖与配置：可选 extra `embed`（sentence-transformers），独立哈希锁 `requirements-embed.lock`（以主锁为约束生成，`make lock`/`make install-embed`）；`Settings.model_cache_dir`（默认 `~/.cache/medops-models`）。模型权重不入库。

## 3. 测试

- 单元 [test_vector_contracts.py](../../tests/unit/retrieval/test_vector_contracts.py)（3）：结果不变量；哈希提供者确定性、单位范数、共享词元更近；边界 k/空查询/版本/回显校验。[test_dec002_run.py](../../tests/unit/evals/test_dec002_run.py)（4）：报告渲染与诊断判定、拒绝覆盖目录、未冻结数据集与外来映射拒绝。
- 集成 [test_vector_pg.py](../../tests/integration/test_vector_pg.py)（15，真实 LOGIN 用户、FORCE RLS、迁移 0006）：构建覆盖全部 chunk 且幂等、元数据等于 spec；三部门 × app/readonly 零越权含计数；状态与窗口在查询内过滤、过去 `as_of` 为空结果；k=1、n-1、n、n+1、50 均返回 `min(k, n)`；语义、并列与三次复现一致；无身份/无事务拒绝；未构建版本、同版本异 spec（构建与查询）、边界期望版本均拒绝；默认计划含策略链、强制下走 HNSW 索引；普通角色不能写；两表 FORCE RLS 与最小授权。迁移往返与 RLS 测试期望更新（仅 `chunk_embeddings.embedding` 一个 vector 列且维度 1024，无 tsvector 列）。
- 门禁：`env -u DEBUG -u PYTHONPATH make check` 退出码 0，**836 passed**（614 单元 + 222 集成）。

## 4. DEC-002 向量通道运行（预登记结果，`evals/experiments/vector/runs/2026-09-20-dec002-bge-m3-v1`）

- 输入：探针 v2 冻结集（107 条，`1fc5089f…`）、`medops_v2`（chunker-v2，16 份 active 文档，2,662 chunk，全部具备 `emb-bge-m3-dense-v1` 向量，构建 557 s），K=20，`as_of=2026-09-20`，5 预热 + 10 计量 pass，CPU 推理；run_manifest sha256 `90f43581…`。
- 结果（严格宏平均 Recall@20）：

| 作用域 | n | 向量 bge-m3 | 词法 A2 | 词法 B2 | 词法 C（已排除） |
| --- | ---: | ---: | ---: | ---: | ---: |
| language_matched | 75 | **82.7%** | 77.3% | 80.0% | 88.0% |
| cross_lingual | 32 | **65.6%** | 15.6% | 12.5% | 12.5% |

  language_matched 分部门：MA 100%（A2 76.7%、B2 93.3%）、PV 79.3%（A2 79.3%、B2 72.4%）、CO 56.2%（A2 75.0%、B2 68.8%）；分 gold 文字：zh-Hant 100%、zh-Hans 100%、en 59.4%。切片：dose_unit / drug_name_zh / time_window 100%，negation 89.5%，mixed_zh_en 75.5%，protocol_id 58.8%（跨语言 41.7%）。
- 诊断阈值（ADR-0007，跨语言 ≥ 50%）：**达到**（65.6%）。稠密检索承担了跨语言查询；其弱项是英文 GCP/ICH 文档与方案编号精确匹配，恰是词法 A2/B2 的强项，融合（阶段 5）的互补性成立。
- 完整性：泄漏 0；不可复现 0；`candidate_exhausted` 0、零结果 0；P95 138.4 ms（含 CPU 查询嵌入约 90 ms）、均值 100.1 ms、最大 898.8 ms（首次）。
- 执行计划：在 2,662 行、部门过滤后合格集较小的条件下，规划器选择精确排序而非 HNSW 路径（计划证据已存 results.json）；适配器的精确计数校验对两种计划同样成立，语料放大后再评估 HNSW 命中率。
- 未命中 24 条（含 pc-0070/0102 两条 unmappable 的强制 miss）集中在 CO/PV 的英文指南与编号查询。

## 5. 自审（基线 §9）

1. 需求：3.8 迁移记录模型/维度/归一化/版本；3.7 iterative scan + 实际候选数 + 零越权；ADR-0007 预登记项逐条执行。
2. 逻辑：精确计数与页长校验使近似索引不能静默少取；版本比对覆盖全部 spec 字段。
3. 安全：应用角色执行；两表 FORCE RLS；提供者本地推理；DSN 与页文本不入日志/工件。
4. 契约：新增向量契约与词法平行；`dec001_run` 仅放宽类型为协议。
5. 测试：新增 7 单元 + 15 集成；全量 836 passed。
6. 可观测：run_manifest/results/plan_evidence；`explain` 可随时取证。
7. 简洁性：一个迁移、四个模块、一个运行脚本。
8. 验证：数字来自 report.md / results.json。
9. Checklist：M1-16 待做 → 已实现。进度见记录 43 汇总。

## 6. 下一步

阶段 5：M1-17 融合（RRF k=60，词法 B2/A2 + 向量）与端到端 Recall@5（事实回查后）运行，据此作 DEC-001 最终判定；阶段 4：DEC-005 术语表工具与初始术语表。
