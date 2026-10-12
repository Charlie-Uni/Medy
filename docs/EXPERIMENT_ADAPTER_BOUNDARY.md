# 词法实验与生产实现的边界

日期：2026-10-12，CODE-04；核验见[记录192](reviews/2026-10-12-implementation-192-lexical-experiment-boundaries.md)。本次是结构整理，不重新选择检索引擎或修改既有评分。

## 1. 当前代码位置

| 职责 | 规范模块 |
| --- | --- |
| 当前生产：按部门物理隔离的 pg_textsearch BM25 | medops.retrieval.lexical.pg_textsearch_departmental |
| 历史 A/A2 的 PostgreSQL FTS，迁移/回滚和兼容测试需要 | medops.retrieval.lexical.pg_simple_fts |
| 身份、元数据、词法结果及 tsvector 通用规则 | medops.retrieval.lexical.pg_lexical_common |
| 生产/候选 D 共用 BM25 SQL、参数、分页和批写 | medops.retrieval.lexical.pg_bm25_common |
| 实验 B/B2：zhparser/SCWS | medops.evals.experiments.lexical.pg_zhparser_fts |
| 实验 C：pg_search | medops.evals.experiments.lexical.pg_search_bm25 |
| 实验 D：全局语料 pg_textsearch | medops.evals.experiments.lexical.pg_textsearch_bm25 |
| 离线参照 BM25 | medops.evals.experiments.lexical.bm25_offline |

生产词法模块的静态门禁止导入 medops.evals，包括函数内、TYPE_CHECKING 和字面量动态导入；没有新允许边。实验可以依赖生产通用机制，方向不能反过来。A2 保留是因为历史生产索引/回滚仍需使用，并非遗漏迁移。

## 2. 共享哪些、不共享哪些

共享 SQL 结构、k+1 分页/耗尽判断、日期/指定文档参数和批量插入。语料布局、RLS、安装规则、版本字符串、固定参数和扩展准入仍由各适配器声明。

候选 D 的全局 BM25 统计可能受隐藏部门词汇影响，所以它继续是实验。生产仍使用三个物理部门语料表及独立索引，共用 SQL 不能让候选 D 替代部门隔离。k1=1.2、b=0.75、simple 配置、tokenizer/停用词、评分符号和排序/过滤均不改变。

新 SQL 工具只接受规范固定标识符；query、日期、文档ID继续作为 SQL 参数，不把用户文本插值成表名或索引名。

## 3. 历史命令迁移

历史的 medops.retrieval.lexical.pg_zhparser_fts / pg_search_bm25 / pg_textsearch_bm25 安装或构建命令改为以下入口；action、参数、环境变量及实验服务器保持原规则：

```bash
python -m medops.evals.experiments.lexical.pg_zhparser_fts --help
python -m medops.evals.experiments.lexical.pg_search_bm25 --help
python -m medops.evals.experiments.lexical.pg_textsearch_bm25 --help
```

install/build 仍仅针对相应实验库，使用原 DEC001_B/C/D_ADMIN_URL，不使用生产事实库做候选实验。Python 导入也迁至新路径；旧路径没有转发壳。历史记录中的原命令不改写为当时不存在的新入口。

历史原代码可在本次之前的提交 [78218ae](https://github.com/Charlie-Uni/Medy/tree/78218ae6d0f9e91af613ba85e3f030eb6a808ccb/src/medops/retrieval/lexical)定位；已有实验结果、数据、参数和原文记录保留。离线 BM25 没有安装CLI，仅迁移其Python导入。

## 4. 验证边界

迁移前后对照生产/候选版本、完整 SQL、参数、分页和中英查询分词；B/C/离线模块字节不变。使用真实临时 PostgreSQL 检查生产与 D 的索引、RLS、部门统计隔离、历史查询、缓存/就绪行为；B/C 未配置服务器时继续按原规则跳过，不称本轮重新验证了其二进制行为。

不变冻结数据、gold、分母、模型、发布策略或实际数据库索引。真实模型质量和容量测试继续逐次授权；结构整理及离线测试不能证明质量提升。
