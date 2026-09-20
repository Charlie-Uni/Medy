# DEC-001 实验准备

当前阶段：`preparation-v1` 已完成一次正式运行 [runs/2026-09-20-m1-05-lexical](runs/2026-09-20-m1-05-lexical/report.md)：三候选严格宏平均 Lexical Recall@20 为 A 48.0%、B 52.0%、C 53.3%，均未通过 ADR-0002 硬门禁；零泄漏、排名可复现；DEC-001 与 M1 保持阻塞，判据不降低，未选择生产实现。结果与归因见 ADR-0002 结果回填。

修订 1（2026-09-20，决策人批准）后：门禁改在语言一致子集计算，探针 v2 派生 32 条英文孪生查询（`drafts/v2/`），chunker-v2 与 esomen 质量复核落地，三服务器新建 `medops_v2`（`preparation-v1/servers_v2/`，75 mapped / 0 unmappable）。第二次运行 [runs/2026-09-20-run2-provisional](runs/2026-09-20-run2-provisional/report.md) 为临时结果：语言一致 43 条上 A 81.4%、B 93.0%、C 95.3%，未复核孪生叠加 A/B 59.4%、C 90.6%；因 Codex 额度耗尽（2026-09-26 恢复）孪生的 LLM 复核与 v2 冻结尚未完成，正式判定待重跑。

## 输入与当前结果

- 冻结探针：75 条，Git commit `213dbe8ead8ff92d8919b201460ac3a961176c8c`；dataset_hash 和独立 manifest SHA-256 见 [experiment_plan.json](preparation-v1/experiment_plan.json)。后续数据修正必须新建版本。
- 只读导出 16 份文档的 2,661 个 chunk，逐条与 `chunker-v1` 从本地页文本重建的内容、哈希和区间核对一致；修复后的工具独立重导出得到相同快照哈希。快照只有 ID、来源、版本和位置，不含全文、数据库地址或凭据。
- [映射结果](preparation-v1/chunk_mapping.chunker-v1.json)：**73 mapped、2 unmappable**。两条 miss 为 pc-0056-g1、pc-0072-g1，均跨越相邻 chunk 边界；不拼接来源片段、不删样本、不修改 key_text，也不从分母排除。具体区间见 [mapping.audit.json](preparation-v1/mapping.audit.json)。
- 映射覆盖率不等于检索 Recall@20；尚无检索得分。映射引用此数据库快照中的实际 UUID；重放同一实验须保留这些 ID，因为它们参与同分排序。新库重新入库产生新 UUID 时，应生成新的快照、映射及运行清单，全部候选使用同一组 ID，不能混用旧结果。
- [数据库核查](preparation-v1/chunk_export.audit.json)中 16 份文档均为 draft，`tfda-label-esomen-40mg` 仍为 low_trust（影响 pc-0025～pc-0030，沿用实现记录 20 的抽取告警）。本次是管理侧只读来源核查，不是普通角色检索，不证明 RLS 或发布条件通过。

## 候选与测量准备

三候选及参数依据 [ADR-0002](../../../docs/adr/ADR-0002-lexical-retrieval-selection.md)，预登记草案保存了候选源码版本、硬件、K=20、并发 1、5 遍预热、10 遍测量、相同查询顺序、固定随机种子和配对 bootstrap 方法。正式运行前必须补齐所有待固定字段并另存冻结运行清单；不能看探针分数后调整配置。

| 候选 | 准备值 | 尚缺的实际证据 |
| --- | --- | --- |
| A | 现有 PG 16.15 固定镜像，应用层 `jieba==0.42.1` + `simple` FTS；默认词典哈希已实测；临时表合成 smoke 通过（[builds/a](builds/a/smoke_result.json)）；适配器 `medops.retrieval.lexical.pg_simple_fts`（`pg-simple-fts-v1`，索引表 `lexical_index_a` + `lexical_index_meta`）在普通 LOGIN 用户 + FORCE RLS 下通过契约、零泄漏、零静默不足、版本拒绝与执行计划测试（实现记录 29） | 真实语料运行（需文档激活）与 75 条对比 |
| B | zhparser v2.3 + SCWS 1.2.3 已在 arm64/PG 16.15 构建并实测扩展版本 2.3；词典 `dict.utf8.xdb`、`rules.utf8.ini` 哈希、GUC 快照、词性映射（全部映射到 simple）已记录；本地镜像 `medy-dec001-b:zhparser2.3-scws1.2.3`（[证据](builds/b/evidence-2026-09-20/metadata.json)）；适配器 `pg_zhparser_fts`（`pg-zhparser-fts-v1`，配置 `dec001_b`，安装时逐字节核对词典）在本地 B 服务器上通过同一套契约/零泄漏/零静默不足/版本拒绝/执行计划测试（实现记录 30） | 无镜像仓库 digest，apt 依赖不可逐位复现；服务器尚未入库语料 |
| C | pg_search v0.25.9 资产按发布者 SHA-256 校验后安装；实测扩展 0.25.9、需先建 `vector`；`pdb.jieba` 过滤器配置已固定；本地镜像 `medy-dec001-c:pg16-pgsearch-0.25.9-r28`（[证据](builds/c/build-metadata.json)）；适配器 `pg_search_bm25`（`pg-search-bm25-v1`，`|||` 数组 OR 谓词，安装时核对扩展二进制哈希）在本地 C 服务器上通过同一套测试，ParadeDB 自定义扫描在普通角色下与 RLS 链共存（实现记录 30） | 生产许可仍为 release_blocked；服务器尚未入库语料 |

B 选择 zhparser 是基于官方 PG16 构建说明和较清楚的固定版本身份，未使用探针得分。C 的固定源码标签中的官方 PG16 Dockerfile 实际引用 0.25.8，因此不能把 Dockerfile 标签当作安装版本；应使用计划所记录的精确 0.25.9 资产，在本机 bookworm 基础镜像安装后实际核验扩展版本。来源：[zhparser 固定 control](https://github.com/amutu/zhparser/blob/dd292fd591edbcb7ebee79d3c3cdc969e9cddced/zhparser.control)、[ParadeDB 发布资产](https://github.com/paradedb/paradedb/releases/expanded_assets/v0.25.9)、[对应 Dockerfile](https://github.com/paradedb/paradedb/blob/c727757be0aab7fbb17c6cc5f0360f22efdd3776/docker/Dockerfile.official-16)。

正式实验还需普通应用角色 + FORCE RLS、同一状态/生效时间过滤与精确候选计数；先用合成输入验证身份切换、版本拒绝和执行计划。端到端 Recall@5/P95 所需的向量/重排配置及组件许可证审核仍未完成，不能把单独词法结果当作最终选型。

## 复现命令

在仓库根执行。使用新的输出目录，工具禁止覆盖已有产物和写入冻结目录。原始 PDF 和页文本按 SPEC 单独保管，不入 Git。

```sh
env -u DEBUG -u PYTHONPATH venv/bin/python \
  evals/experiments/lexical/tools/export_chunk_snapshot.py \
  --dataset evals/probe/precise_clause/v1 \
  --pages evals/probe/precise_clause/v1/pages \
  --out /tmp/medy-new-run/chunks.snapshot.json

env -u DEBUG -u PYTHONPATH venv/bin/python -m medops.evals.probe.chunk_mapping \
  evals/probe/precise_clause/v1 \
  --pages evals/probe/precise_clause/v1/pages \
  --chunks /tmp/medy-new-run/chunks.snapshot.json \
  --out /tmp/medy-new-run/chunk_mapping.chunker-v1.json
```

导出需要本机受控管理连接，在 repeatable-read / read-only 事务中执行，不修改文档状态。映射不访问数据库：退出码 0 为全部映射，1 为完整合法产物已写出且存在必须计 miss 的 unmappable，2 为输入或输出非法且未发布产物。

三候选适配器均已用合成数据通过普通角色门禁（实现记录 29、30）；B/C 服务器已迁移、建立登录用户并入库同一语料（chunk 指纹与开发库一致），三服务器各有自己的 gold→chunk 映射（`preparation-v1/servers/`），运行工具 `medops.evals.experiments.dec001_run` 已用全 draft 状态做管道 smoke（实现记录 31）。下一步依次是：核查 low_trust 的解析问题与实验数据发布条件；冻结完整运行清单，再执行全部 75 条对比。两条 unmappable 原样进入报告，不单独针对这两条调整切分器。
