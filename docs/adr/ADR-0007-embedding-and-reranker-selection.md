# ADR-0007：DEC-002 Embedding 与 Reranker 选型（预登记）

- 日期：2026-09-20
- 状态：已决（决策人 2026-09-20 授权："我需要的是结果 你来决定"；本 ADR 由实施方按该授权作出，决策人可随时否决）
- 决策来源：[实现记录 41](../reviews/2026-09-20-implementation-41-delegated-decisions.md)；基线 3.8、5.2、5.11；DEC-002、DEC-009（仅限本决策涉及的 embedding/reranker 部分）

## 决策

1. **Embedding**：`BAAI/bge-m3` 稠密向量，HuggingFace 修订 `5617a9f61b028005a4858fdac845db406aefb181`（2024-07-03），许可证 MIT。维度 **1024**，输出 L2 归一化为单位向量，距离为余弦（pgvector `vector_cosine_ops`），存储 `vector(1024)`（fp32）。chunk 与查询使用同一模型、同一修订、同一截断长度（`max_seq_length=1024` token）。`embedding_version` 固定为 `emb-bge-m3-dense-v1`，其元数据（模型、修订、维度、归一化、截断长度、框架版本）写入索引元数据表；查询侧配置与索引元数据任一不同即拒绝查询（与基线 3.6 的词法版本规则相同）。
2. **推理边界**：仅本地推理（`sentence-transformers` + PyTorch，CPU 或 Apple MPS），页文本与查询不离开部署环境；外部 embedding API 不在候选内（DEC-009 对 embedding/reranker 部分由此固定为"本地"；LLM 的托管边界仍待 DEC-009）。运行时依赖放在可选 extra `embed`，独立锁文件 `requirements-embed.lock`，API 与 CI 主锁不含 PyTorch。
3. **向量索引与查询规则**：pgvector HNSW（`m=16, ef_construction=64`，余弦）；查询在应用角色、FORCE RLS 与 `documents.status='active'`、生效窗口过滤下执行，采用 pgvector ≥0.8 的 `hnsw.iterative_scan=relaxed_order` 与自适应 `hnsw.ef_search`；同一事务内以精确计数（同一过滤条件下具备当前版本向量的合格 chunk 数）证明返回数 = `min(K, 合格数)`，否则失败关闭；分数并列按 `chunk_id` 升序；记录实际候选数与 `candidate_exhausted`。
4. **Reranker**：`BAAI/bge-reranker-v2-m3`，修订 `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`，许可证 Apache-2.0，本地推理；输入 ≤20 候选、输出 ≤8（基线 5.2）；`rerank_params`（模型、修订、输入/输出上限）进入 `retrieval_version`。实现随 M1-17/M2。
5. **维度切换**：按基线 3.8，未来更换模型/维度以新列与新索引后台重建完成，不原地改变已有向量语义；`embedding_version` 变化即新的 `retrieval_version`。

## 预登记的评估

- 数据：探针 v2 冻结集（`dataset_hash 1fc5089f6fa7f80a1a5e23940826b0d4c811cde29e225dd8305241a33beb0321`，107 条），chunker-v2 映射；`as_of=2026-09-20`。
- 向量通道单独报告：K=20 严格宏平均 Recall@20，按门禁作用域（语言一致 75 条 / 跨语言 32 条）、部门、切片分别输出；诊断阈值（非硬门禁）：跨语言 Recall@20 ≥ 50%，否则说明稠密检索未能承担跨语言查询，需预登记翻译/改写步骤。
- 端到端硬门禁沿用基线 M1-21：事实回查后严格宏平均 Recall@5 ≥ 85%、分部门与语言切片报告、失效版本引用率 0；融合使用 RRF（`k=60` 初始值），词法通道取 ADR-0002 修订 3 保留的 A2/B2 基线。
- 复现条件：CPU 推理、fp32、框架与模型修订固定并写入 run_manifest；同机重复运行候选集合与排名逐项一致；零越权由管理连接独立复核（与 DEC-001 运行相同的 leak check）。

## 批准边界

- 不做微调、不做蒸馏；不使用外部 API；模型缓存目录在仓库外（`MEDOPS_MODEL_CACHE`），模型权重不进入 Git。
- 未来更换 embedding 模型或维度必须另开 ADR 修订并重建索引。
- 本决策不包含 LLM 的托管与数据出境（DEC-009 其余部分）与 Verifier 模型（DEC-003）。
