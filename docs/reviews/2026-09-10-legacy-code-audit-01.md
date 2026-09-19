# 旧代码审核与移植记录 01：文枢项目（2026-09-10）

| 项 | 内容 |
| --- | --- |
| 来源 | 本地目录 `~/Downloads/居丽叶的简历项目9：行政助手Agent/wenshu-project/`（文枢 · 跨部门文档处理与问答助手），只读，不入仓库 |
| 规模 | 后端 Python 119 文件、10,716 行；另有 Next.js 前端、pi-agent TypeScript 服务、K8s/Helm、k6 压测 |
| 技术栈 | FastAPI、MongoDB(motor)、Redis、jieba、纯 Python BM25、内存/Chroma/Mongo 向量库、DeepSeek 与中转站模型、自研 HMAC token |
| 审核人 | Claude（Fable 5.1） |
| 决策人 | Qihan Zhu（指示：读取可用代码并应用，不把原文件放进仓库） |
| 结论 | 三块代码经改造后移植，其余不可用；移植代码 38 个单元测试通过；未勾选任何 checklist |

## 1. 逐模块判定

| 模块 | 判定 | 依据 |
| --- | --- | --- |
| `retrieval/bm25.py` 纯 Python BM25 + jieba | **移植为离线参考基线** | ADR-0002 明确允许进程内 BM25 作为离线参考，不作生产候选；原实现在应用层按部门过滤（违反基线 3.7）、逐文档 O(N) 计算 tf、无并列规则，均已改造 |
| `retrieval/hybrid.py` RRF 融合 | **移植为纯函数** | 基线 5.2 要求 RRF 只用排名且确定性；原实现把 `_rrf` 写回候选 dict 且无并列规则 |
| `pipeline/cleaner.py` 全角转半角 | **思路吸收，代码不用** | 与 norm-v1 第 3 步一致；但同文件的 opencc 繁转简与我方 zh-Hant 政策冲突，页眉过滤会误删“版权所有”行 |
| `retrieval/reranker.py` | 不用 | 中转站/启发式静默回退违反基线 5.3“不能尽力猜测”；Medy 要求显式降级或升级 |
| `retrieval/vector_store.py` | 不用 | 内存/Chroma/Mongo 暴力检索，无 pgvector、无数据库内过滤（INV-AUTH-02、3.7） |
| `pipeline/parser.py`、`chunker.py` | 不用 | 不保留页内字符区间，chunk 只记首页页码，不满足 SPEC 第 6 节页片段契约；制度文档标题正则不适用医学说明书 |
| `pipeline/metadata_extractor.py` | 不用 | LLM 抽取学校制度元数据，与 Medy 事实平面无关 |
| `harness/*`（orchestrator、agents、base） | 不用 | dataclass 加 `dict[str, Any]`（INV-HAR-01，全后端 300 处）；先 Answer 后 Verify 且无结构核验（F1.1、3.5）；无证据时 Verifier 直接判通过（INV-SAF-02）；引用等于全部检索块（幻觉引用风险）；LLM 失败时拼接原文作答 |
| `loop/*`、`review/*` | 不用 | Hook 高置信度自动生效、`human_out_of_loop` 阶段与 F5.5/INV-HAR-06“任何候选不得绕过审批生效”冲突；沙箱以 Verifier 分数为门禁，无冻结集与统计门禁 |
| `memory/*` | 不用 | 五类记忆注入 prompt 不在 Medy 范围；组织 FAQ 与事实平面混用 |
| `auth.py`、`api/*`、`storage/*` | 不用 | 自研 HMAC token 与演示账号，Medy 采用 OIDC 边界（ADR-0001）；MongoDB 模型 `extra="allow"` |
| `utils/ratelimit.py`、`logging.py`、`metrics.py` | 暂不用 | 单进程内存限流不满足多副本；日志无 trace_id 与脱敏；指标以部门为高基数 label |
| `services/pi-agent`、`web/`、`deploy/k8s|helm` | 不用 | TypeScript 运行时与前端不在 P0；K8s 属 P1 |
| `department_files/`、`evaluation/real_document_qa.json` | **排除** | 真实高校部门文件（含答辩分组、承诺书），许可与个人信息不明；评测集为校务问答 |
| `.env.example` | 不用 | 无真实密钥（已扫描），但配置面向 DeepSeek/中转站，不适用 |

全后端另有 28 处宽泛 `except Exception` 静默回退，与基线第 9 节“失败默认拒绝”相反，进一步支持不整体复用的结论。

## 2. 已移植代码（均为改写，非复制）

| 文件 | 内容 | 相对旧代码的改造 |
| --- | --- | --- |
| `src/medops/core/canonical.py` | `canonical_json`、`sha256_hex`、`canonical_hash`、`operation_key` | 新写，实现基线 3.2：键排序、拒绝 NaN 与集合、U+001F 分隔、四段拼接 |
| `src/medops/retrieval/lexical/normalization.py` | norm-v1 | 新写，实现 SPEC 4.1；以 `tests/norm_v1_vectors.json` 为契约（PR-14） |
| `src/medops/retrieval/lexical/tokenizer.py` | `JiebaTokenizerV1`（tok-jieba-v1）、`RegexTokenizerV1`（tok-regex-v1） | 源自旧 `tokenize`：先做 norm-v1；不再整句 lower，只折叠 ASCII 词元并写明为分词器规则；`PROT-2024-017`、`NCT04283461`、`0.5` 整体保留；缺少 jieba 时抛错而非静默回退；`dictionary_version` 由 jieba 版本加用户词典 SHA-256 组成 |
| `src/medops/retrieval/contracts.py` | `ChunkRecord`、`LexicalCandidate`、`LexicalSearchResult` | 新写，实现 ADR-0002 统一契约，校验 `returned_count`、`candidate_exhausted`、排名连续与唯一 |
| `src/medops/retrieval/lexical/bm25_offline.py` | `OfflineBM25Index` | 源自旧 `BM25Index`：保留评分公式；改为倒排索引；删除部门过滤（语料必须先经数据库 RLS 取出）；按 chunk_id 打破并列；输出统一契约与版本 |
| `src/medops/retrieval/fusion.py` | `rrf_fuse` | 源自旧 RRF：纯函数、只用排名、按 chunk_id 打破并列、拒绝重复 id |
| `pyproject.toml` | 最小包定义 | Python >= 3.11，依赖 pydantic、jieba；dev 依赖 pytest、jsonschema；pytest `pythonpath=src` |
| `tests/unit/**` | 38 个单元测试 | 覆盖分隔歧义、版本变化、norm-v1 全部向量与幂等、精确条款分词、BM25 命中/耗尽/并列/重复、RRF 数学与并列 |

`OfflineBM25Index` 的文档字符串明确写明：它是 ADR-0002 的离线参考基线，不是生产检索器，不得持有全量生产索引。

## 3. 验证

```text
python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q   ->   38 passed in 0.33s
```

运行环境：Python 3.11.16、pydantic 2.13.5、jieba 0.42.1、pytest 9.1.1。`.venv/` 已加入 `.gitignore`，依赖只装在仓库内的虚拟环境，未改动系统 Python。

## 4. Checklist 状态

- 未勾选任何项。M0“实现 canonical_json 与 operation_key 并有确定性与跨平台测试”已有实现与确定性测试，但跨平台测试未运行，保持 `[ ]`。
- M1“实现 lexical_retriever”仍待 DEC-001 实验；本轮只提供实验所需的候选 A 分词器与离线参考基线。

## 5. 待决策

1. Python 版本按 `requires-python >= 3.11` 固定（本机有 3.11.16，系统默认 3.9.6 不满足）；是否在 M0 正式锁定 3.11。
2. jieba 用户词典（医学通用名、商品名、缩写）的初始来源属 DEC-005，词典文件进入仓库前需确认许可。
3. 旧项目其余部分本轮不再引用；若后续要看 Loop 或审核流程的设计文档（`design_files/`），另行按需阅读。
