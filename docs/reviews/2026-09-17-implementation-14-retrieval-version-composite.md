# 实现记录 14：复合 `retrieval_version` 纯函数（M1-15 切片）

日期：2026-09-17。范围：实现基线 3.6 定义的复合 `retrieval_version`，只固定函数与输入形状；不选定任何生产取值（DEC-001/DEC-002 未决），不接入索引元数据、缓存或运行时。未修改基线、SPEC、Schema、已有契约；未提交 Git。**状态：待 Codex 审核；第 5 节五处实现选择待决策人确认。**

## 完成

- [src/medops/retrieval/versioning.py](../../src/medops/retrieval/versioning.py)：`RetrievalVersionInputs`（frozen、`extra="forbid"`、`allow_inf_nan=False`）恰好含基线 3.6 的八个成员 `retriever_version / tokenizer_version / dictionary_version / normalization_version / embedding_version / rrf_params / rerank_params / candidate_limits`；`compute_retrieval_version()` 返回 `SHA-256(canonical_json(八成员))` 的 64 位十六进制。
- 与既有契约的衔接：`from_lexical(LexicalVersions, ...)` 与 `.lexical` 属性在四个诊断组成部分与复合版本之间往返；模块文档写明组成部分只用于诊断与实验报告，缓存键、operation key、回放只能用复合值（基线 3.6 最后一段）。
- 输入规则：`rrf_params` 必须含正数 `k`（bool 不算数字）；`candidate_limits` 为非空的正整数映射；`rerank_params` 允许空对象，空对象本身进入哈希；任何未知成员被拒绝而不是被静默漏出哈希。

## 约束

基线 3.2（canonical JSON）、3.6（复合版本、组成部分不得单独作缓存键）、5.2（RRF `k=60` 为初始配置且必须进入版本）、INV-HAR-05（版本集合记录在 Trace）。

## 验证

```text
tests/unit/retrieval/test_versioning.py -> 28 passed
  成员集合恰为八个且顺序与基线一致；已知答案 b649d904…48e1 与测试内按公式独立重算一致；
  10 组成员/嵌套参数变更各自改变版本；键序与构造路径无关；相同 LexicalVersions 不同 RRF k 复合值不同；
  13 组非法输入被拒（未知成员、缺成员、空串、无 k / k<=0 / k 为 bool 或字符串 / NaN、Infinity、空 limits、
  非正或非整数 limit）；frozen。
env -u PYTHONPATH make check -> ruff 通过；mypy 39 个源文件通过；pytest 287 passed（本轮新增 28）；schemas 无漂移
```

## 未完成

M1-15 保持"部分"：生产 tokenizer/词典/规范化取值、写入索引元数据与缓存键、相同版本可复现的证明，都在 DEC-001/002 之后。

## 风险

无新增已知风险。函数未被任何运行时调用，接线时必须由调用方保证八个成员全部来自实际生效配置，而不是默认值。

## 5. 实现选择，待决策人确认（不阻塞其他工作）

1. `rrf_params` 强制含正数 `k`：与 `fusion.py` 的唯一参数一致；若未来 RRF 加权重，只是多出键，不影响本规则。
2. `rerank_params` 允许 `{}`：表示"未配置 Reranker"的显式降级配置也有可复现版本；不允许省略该成员。
3. `candidate_limits` 用泛型正整数映射而非固定键：DEC-002 前候选上限的键集合（是否含 over-fetch 因子）未定；固定键集合可在选型后收紧。
4. 纯词法配置下 `embedding_version` 的取值约定未定：当前要求非空字符串，未规定哨兵值（例如 `none`）。DEC-002 前不会有生产运行，可留到那时。
5. `VersionSet.retrieval_version` 目前是任意非空字符串；是否收紧为 64 位十六进制（会改动 api/domain 测试的 fixture）。建议在 M2 节点接线时一并收紧，本轮不改契约。

状态更新（2026-09-17）：以上五处实现选择已获决策人同意，按默认执行；第 5 条留到 M2 节点接线时收紧。

## 6. Codex 审核焦点

- 成员名与基线 3.6 是否逐字一致；`model_dump(mode="json")` 是否可能引入与基线 canonical 规则不一致的表示（例如浮点 `k`）。
- 允许 `rerank_params={}` 是否会掩盖"忘了配置 Reranker"的错误，还是应由接线方在配置层强制。
- 是否应该把该函数直接挂到 `LexicalSearchResult`/`VersionSet` 上，还是保持独立模块（本轮选择独立，避免契约变更）。

## 7. 自审（基线 §9）

1. 需求：只覆盖 M1-15 的函数部分；未选型，未扩展数据范围。
2. 逻辑：封闭输入保证不会漏成员；嵌套参数变化有测试；canonical 排序保证与键序无关。
3. 安全：无 I/O、无日志、无密钥。
4. 契约：新增模块不改既有契约；`LexicalVersions` 往返有测试。
5. 测试：正常、已知答案、公式独立重算、逐成员敏感性、13 组反例、frozen。
6. 可观测：无运行时路径；版本值本身就是 Trace 记录项。
7. 简洁性：一个模型、一个函数、一个常量；无新依赖。
8. 验证：见上；未验证项：远端 CI。
9. Checklist：基线勾选保持 0；路线图与知识对照 M1-15 行按证据更新，仍为"部分"。
