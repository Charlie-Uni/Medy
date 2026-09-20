# 实现记录 28：DEC-001 固定候选环境构建

日期：2026-09-20。承接用户“核查完直接推进下一个阶段”的授权，在探针归档和映射完成后继续补齐候选环境。

## 编码前记录

- 目标：在独立实验镜像/临时容器中构建并验证 B（zhparser v2.3 + SCWS 1.2.3）与 C（pg_search v0.25.9 + Jieba），记录实际镜像标识、扩展版本、词典和配置证据；把准备草案中的未知项变成实测结果。
- 不变量：使用已登记源码/资产身份；不修改现有 medops-postgres 容器、数据卷、文档状态或冻结 v1；只用合成文本验证构建/分词，不观察或调优 75 条探针得分；C 生产许可仍为 release_blocked。
- 验收：下载的实际文件哈希及固定提交匹配；运行端版本与声明相同；arm64 与 PostgreSQL 16 可实际加载；所有构建参数、包版本、词典/规则/配置及镜像 ID 可追溯；失败与未测条件明确列出。
- 范围：仅本地隔离实验构建和合成 smoke，不进行生产部署、发布文档或提前选择检索实现。镜像和临时容器使用单独名称，测试后移除临时容器。
- 分工：独立线程处理 B；独立线程处理 C；主线程承接记录 27 的完整验证与归档，并交叉核对构建证据和实验清单。
- 每轮完成后按工程基线 §9 逐项自审，记录真实测试结果。

## 执行结果

三条线均只用合成文本，未读取或执行 75 条探针查询；未修改 medops-postgres 容器、数据卷与文档状态；临时容器已移除。证据文件位于 [evals/experiments/lexical/builds/](../../evals/experiments/lexical/builds/)，摘要已回填 [experiment_plan.json](../../evals/experiments/lexical/preparation-v1/experiment_plan.json) 的候选字段，`status` 仍为 `draft_not_ready_for_comparison`。

### A：应用层预分词 + simple FTS（现有开发库，临时表）

- 在现有 PG 16.15 服务器的连接级临时表上验证 `tok-jieba-v1`（jieba 0.42.1，默认词典 SHA-256 `7197c321…12ae`）预分词后写入 `tsvector`、GIN 索引、OR 谓词、`ts_rank_cd(normalization=0)` + `id ASC` 排序与精确计数；6 组用例（单词、中文、方案编号、无匹配、纯标点、双词 OR）返回集合与计数均符合预期，重复执行结果相同，事务回滚。
- 明确未覆盖：普通角色、RLS、正式索引表、真实语料。见 [smoke_result.json](../../evals/experiments/lexical/builds/a/smoke_result.json)。

### B：zhparser v2.3 + SCWS 1.2.3（新建镜像）

- 源码按固定 commit 下载并核对 tarball SHA-256（zhparser `ae670786…5584`、scws `c4f83883…4d0d`），在 `pgvector/pgvector:pg16@sha256:ccc6e83d…4d6b` 基础上于 arm64 构建；镜像本地 ID `sha256:00ce3abb08cc…245b`，tag `medy-dec001-b:zhparser2.3-scws1.2.3`，未推送仓库，因此没有注册表 digest。
- 运行实测：PostgreSQL 16.15（Debian 16.15-1.pgdg12+2）、扩展 `zhparser 2.3`、`en_US.utf8`/UTF8；8 个 `zhparser.*` GUC 全为默认值；词性映射全部映射到 `simple` 词典；无自定义词典；词典 `dict.utf8.xdb` 与 `rules.utf8.ini` 的 SHA-256 已记录。合成 OR 查询在两个新连接上输出完全一致（`fresh_connection_outputs_equal=true`）。
- 两次失败尝试如实保留：一次启动失败（未设 `POSTGRES_PASSWORD`，见 [failed-startup](../../evals/experiments/lexical/builds/b/failed-startup-2026-09-20/container.log)）；一次元数据采集因 `SHOW lc_collate` 在 PG 16 不是配置参数而退出（[failure.json](../../evals/experiments/lexical/builds/b/failed-metadata-2026-09-20/failure.json)），改为从 `pg_database` 读取后通过。
- 明确未覆盖：普通角色/RLS/计数/版本契约、75 条检索与延迟门禁、生产词典许可证、来自流动 apt 仓库的逐位复现。

### C：pg_search v0.25.9 + pdb.jieba（新建镜像）

- 发布资产 `postgresql-16-pg-search_0.25.9-1PARADEDB-bookworm_arm64.deb`（65,546,104 字节）下载后与发布者 SHA-256 `69ac9f7a…49a9` 一致；未验证 cosign 附加签名。安装到同一 pgvector 基础镜像，镜像本地 ID `sha256:f564d490dfa0…45ec`，tag `medy-dec001-c:pg16-pgsearch-0.25.9-r28`，未推送仓库。
- 运行实测：PostgreSQL 16.15、`pg_search 0.25.9`、`vector 0.8.6`；`CREATE EXTENSION pg_search` 依赖先建 `vector`（第一次 smoke 因此失败，已记录）。`pdb.jieba` 过滤器配置固定为 lowercase=true、其余关闭；扩展二进制 SHA-256 已记录。
- 观察到的 tokenizer 行为：`"alpha gamma"` 被切为 `["alpha", " ", "gamma"]`，空白作为词元被保留，导致 OR 查询命中所有含空格的行；`PROT-2042-123` 切为 `["prot-2042", "-", "123"]`。这两个行为未被调优掩盖，将在适配器的查询谓词中处理并在实验清单中声明。执行计划为 ParadeDB Base Scan / TopKScanExecState（score desc, id asc）。
- 许可证：`release_blocked` 不变（AGPL-3.0 社区版，无本项目发布方式的书面批准）。

### 交叉核对

- `experiment_plan.json`：删除已解决的 `candidate_builds_unverified`，替换为 `candidate_images_local_only`（无注册表 digest；B 空白/OR 谓词与 C 保留空白词元需在适配器中固定）；其余四项阻塞不变。A/B/C 候选条目补入镜像本地 ID、运行版本、GUC/词典/规则哈希、过滤器配置与 smoke 证据路径；未写入任何质量结果。
- [README](../../evals/experiments/lexical/README.md) 候选表按上述结果更新。ADR-0002 预登记判据未改动。

## 自审（基线 §9）

1. 需求：只做隔离构建与合成 smoke，未选型、未部署、未读取探针。
2. 逻辑：三条线的失败尝试与未覆盖项均写入证据文件，不以“构建成功”掩盖。
3. 安全：临时容器 `network=none`、只读根文件系统、已移除；无真实语料进入镜像。
4. 契约：`LexicalRetriever` 契约未变；B/C 的 OR 谓词处理留待适配器并在清单声明。
5. 测试：`env -u DEBUG -u PYTHONPATH make check` 549 passed（485 单元 + 64 集成）；构建证据不改变软件测试。
6. 可观测：镜像 ID、包清单、GUC、词典哈希、执行计划均可追溯。
7. 简洁性：每候选一个目录，一个 Dockerfile/构建脚本/smoke，无额外抽象。
8. 验证：本记录的数字与 `metadata.json`、`build-metadata.json`、`smoke_result.json` 逐项对照一致。
9. Checklist：M1-02 仍为部分（镜像已实测，运行清单未冻结）；进度百分比不变（24.1%）。
