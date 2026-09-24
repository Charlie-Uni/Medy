# 实现记录 71：显式历史查询可召回 archived 版本——安全集缺陷 4 的处置

- 日期：2026-09-24
- 授权："先继续进行无需决策的工作"；处置记录 69 §4 缺陷 4
- 范围：`medops.retrieval`（词法 / 向量通道 SQL、边界、hybrid、契约协议）、`evals/harness/tools/safety_run.py`（按样本 as_of 构造检索）、单元与集成测试

## 1. 问题

`AskRequest.historical.as_of` 走到检索层后只影响回查（`recheck_candidates(..., allow_historical=...)`）：两个通道的 SQL 固定 `documents.status = 'active'`（`pg_lexical_common.tsvector_search_sql`、`pg_vector.SEARCH_SQL` / `ELIGIBLE_COUNT_SQL`），archived 版本永远进不了候选，回查里"显式历史请求放行 archived"的分支从未被触发。安全集 F 类 5 条历史查询因此全部"未触发"（记录 69 §4）。另一个只影响安全集运行器的错误：运行器把检索按运行级 `as_of` 构造，样本级 `as_of` 只到回查；API 是按请求构造检索的，没有这个问题。

## 2. 决定与依据

| 决定 | 依据 |
| --- | --- |
| `allow_historical` 作为每次 `search()` 调用的关键字参数穿过边界（`run_lexical_search` / `run_vector_search`）进入通道 SQL：`and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))`，生效窗口条件不变 | INV-DATA-03：只有显式历史请求可见 archived；把开关放在 SQL 而不是应用侧过滤，越权与计数语义（`eligible_count`、`min(k, eligible)`）保持在查询内 |
| 三个 DEC-001 候选适配器（simple_fts、zhparser、bm25）与离线 bm25 全部接受该关键字：前三者进 SQL，离线候选忽略（它索引调用方给定的 chunk 列表，不做状态过滤） | 协议统一，契约套件（`assert_lexical_adapter_contract`）继续对所有候选生效 |
| 非历史请求的结果逐字节不变：默认 `False` 时 SQL 谓词等价于原来的 `status = 'active'`；`PRODUCTION_RETRIEVAL_VERSION` 的成员未变，不重钉 | 复合版本的成员是"塑造检索结果的配置"，历史开关是请求属性且已在缓存键与 Trace 里（`as_of`、历史标志） |
| 回查对 `allow_historical=True` 且无 `as_of` 的请求仍抛 `invalid_request`（INV-DATA-03） | 探针验证：不给日期的历史请求被拒，而不是悄悄退化 |
| 安全集运行器：带 `historical.as_of` 的样本按该日期构造一套检索（`Plane.retrieval_for`），与 API 的按请求构造一致 | 运行器错误曾把 F 类历史行的通道过滤日期固定为运行日 |

## 3. 验证

- 单元：hybrid 转发测试（默认 False、显式 True 两通道都收到）；所有假适配器接受新关键字；全量单元 870 通过，mypy 干净。
- 集成（真实 LOGIN 用户 + FORCE RLS）：词法适配器套件新增「archived 只在显式历史请求下返回」——默认结果与 archived 无交集，历史请求结果 = 现行可见 ∪ archived，draft / 未生效 / 已过期仍被排除；向量通道同一断言；生产词法、候选 A / A2、向量、事实回查共 89 项通过。
- 生产库探针（medops_v2，PV 身份，不调模型）：「Under GVP Annex I, how is an 'adverse reaction' defined?」在 `as_of=2020-01-01` + 历史请求下候选 20 条中 12 条 archived，证据含 `ema-gvp-annex-i-rev4` 且 `historical=True`；同日期不带历史请求候选全部 active；历史请求不带日期被回查拒绝。
- 安全集 F 类历史行的正式复跑需要模型（Answer 节点），待 OpenAI 额度恢复后随第二轮运行续跑。
- 顺手修正：`test_audit_store` 与 `test_tasks_store` 的幂等键过期时间写成固定日期（2026-09-23 12:00 UTC + 1 天），2026-09-24 12:00 UTC 起必然失败——改为相对数据库时钟；这两条失败与本记录的改动无关（HEAD 同样失败）。

## 4. 未做 / 限制

- `historical.version`（按版本标签查历史）仍未实现（API 已明确拒绝，随 M3-03 任务接口）。
- MCP `search_documents` 的 `historical_version` 走的是 `McpService` 自己的 SQL，本次未动（记录 62 已按状态过滤）。
- 缓存键已含 `allow_historical` 与 `as_of`，无需变更；但缓存命中路径（`fetch_evidence`）仍按身份回查，语义不变。

## 5. 自审（§9）

- 改动只放宽了一个显式、带日期的请求路径；默认路径的 SQL 谓词与之前等价（集成测试逐部门断言）。
- 越权与计数：过滤仍在查询内，RLS 链不变，`eligible_count` 与 `search` 用同一谓词。
- 费用 0（探针只用本地模型做嵌入 / 重排）。

## 6. 进度

- 记录 69 缺陷 4 处置完成；M1-18 / M2-16 注记更新。P0 加权进度不变 57.6%。
