# DEC-001 实验准备

当前阶段：`preparation-v1`。探针已完成 Git 冻结归档，实验清单仍是准备草案，尚未运行 A/B/C 召回对比，也未选择生产实现。

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
| A | 现有 PG 16.15 固定镜像，应用层 `jieba==0.42.1` + `simple` FTS；默认词典哈希已实测 | 候选适配器、索引配置和普通角色契约实测 |
| B | zhparser v2.3 + SCWS 1.2.3，两个源码 commit 已记录 | arm64 构建、最终镜像、词典/规则哈希、词性映射/GUC 与运行版本 |
| C | pg_search v0.25.9 + `pdb.jieba`，bookworm/PG16/arm64 发布资产和发布者 SHA-256 已记录 | 资产下载校验、安装、最终镜像、完整 filters 与运行版本；生产许可仍为 release_blocked |

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

下一步依次是：补齐并构建 B/C 的固定配置，用合成数据验证三候选适配器；核查 low_trust 的解析问题与实验数据发布条件；冻结完整运行清单，再执行全部 75 条对比。两条 unmappable 原样进入报告，不单独针对这两条调整切分器。
