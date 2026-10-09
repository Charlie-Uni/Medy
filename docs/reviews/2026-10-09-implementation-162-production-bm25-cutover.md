# 实现记录 162：生产词法切换到部门隔离 BM25

日期：2026-10-09（Australia/Sydney）。触发决定：项目所有者明确回复“切换BM25”。范围包括生产适配器、统计隔离、PostgreSQL 17 与扩展镜像、migration 0022、CI、本机三个数据库的可回滚迁移和自审核。没有调用任何付费模型；新冻结集的检索/答案级正式对照仍是 BM25-09。

## 1. 决定边界

候选 D 的历史事实保持不变：词法 Recall@20 78.7% 对 A2 49.3%，词法 P95 40 ms 对 164 ms；553 条主集检索 Recall@5 为 87.34% 对 85.71%，差 +1.63 pp，95% CI [+0.18,+3.26]。它没有达到修订 5 预登记的 +5 pp 替换线，所以历史判定仍是“D 未胜出”。本次由所有者按综合价值重新作出生产采用决定，不把工程切换描述成历史门禁通过。

生产固定项：

- PostgreSQL 17.11；`pg_textsearch` 1.5.1；PostgreSQL License；必须预加载。
- `tok-jieba-v2`、固定英文停用词 SHA-256、`text_config=simple`、`k1=1.2`、`b=0.75`。
- 词法 top 20、向量 top 20、RRF k=60、融合 20、重排输出 8 均不变。
- 新 `retriever_version=pg-textsearch-bm25-departmental-v1`；复合 `retrieval_version=19c755df9adf44e8df9badba547f9b0f21391edbf8f3ab3631f5ea0256b3e4d1`。旧缓存键不会复用。

## 2. 为什么不能直接上线实验 D

`pg_textsearch` 官方说明 BM25 的 IDF/词频统计覆盖同一索引的全部行，包括被 RLS 隐藏的行。实验 D 的单表结构能阻止直接返回隐藏行，却会让一个部门的排序受其他部门词频影响。项目文档允许文档通过 ACL 共享，按 owner 分区也不正确。

生产结构为三张表/三个物理索引：

| 部门 | 表 | 索引 |
| --- | --- | --- |
| MA | `chunk_lexical_bm25_ma` | `chunk_lexical_bm25_ma_idx` |
| PV | `chunk_lexical_bm25_pv` | `chunk_lexical_bm25_pv_idx` |
| CO | `chunk_lexical_bm25_co` | `chunk_lexical_bm25_co_idx` |

chunk 按 `document_acl(permission=read)` 复制；共享文档进入每个有权部门的物理语料。每张表 FORCE RLS，并同时要求事务 `medops.dept` 等于表所属部门，再经过 `chunks → documents → document_acl` 权限链。全量构建排除 draft/withdrawn，避免未发布文本进入统计。ACL revoke 的数据库触发器在同一事务内删除被撤部门副本；grant/activate/archive 由原 transactional outbox 重新按当前事实构建。

全量重建会在同一事务中锁定现有 document/ACL 行，再开启服务端游标。正式 ACL 与状态写路径先对文档 `FOR UPDATE`，直接撤销现有 ACL 也会与行锁冲突；这样可避免游标读到旧 ACL 后又在并发撤权完成之后提交过期部门副本，同时不为 admin 扩大 immutable chunks 的写权限。重建期间相关摄取、状态或 ACL 写入会短暂等待。单文档 outbox 路径沿用文档行锁与事实对账；适配器自身也只为 active/archived 文档生成副本。

合成测试先记录 PV 查询的候选及浮点分数，再只向 MA 增加 40 个含同一已知词的 chunk；PV 结果逐项不变。另有测试证明 ACL revoke 在事务提交前已经删除 PV BM25 行。直接行泄漏、统计串扰、连接身份复用、候选不足、历史窗口、版本漂移和写权限继续走共享适配器门禁。

## 3. 代码与迁移

- `src/medops/retrieval/lexical/pg_textsearch_departmental.py`：部门选择、查询、全量构建、ACL 复制、outbox reconcile、单文档缺口检查。
- `src/medops/retrieval/production.py`：默认生产通道改为 BM25；检索版本、构建、消费者和覆盖检查改为部门语料口径。
- `src/medops/retrieval/maintenance.py`：去掉 A2 `tsvector` 特有修复，按当前 ACL 原子重建一个文档的所有部门副本。
- migration 0022：版本/预加载硬检查、三表三索引、FORCE RLS、最小授权、同步撤权触发器；保留 migration 0007 A2 表作为回滚资产。
- `deploy/postgres/Dockerfile.pg17-bm25`：固定 `pgvector/pgvector:pg17` 多架构 digest；核验发布者 zip 和 deb 的 amd64/arm64 SHA-256 后安装 1.5.1。
- `docs/reviews/2026-10-09-licence-dossier-pg-textsearch.md`：直接组件、包/ELF 依赖、基础镜像、资产哈希和分发义务；生产直接组件无 AGPL 阻塞。
- Compose 改为 PG17 新卷 `medops_postgres17_data`；CI 使用 PG17 service，下载、核验、安装、预加载同一 amd64 包后才运行迁移和测试。
- 覆盖、RLS、迁移 inventory、生产适配器、维护和版本测试全部更新；部署、运维、任务和 ADR 同步更新。

## 4. 本机逻辑迁移

先从 PG16 容器为三个数据库生成 custom-format dump 与旁路 SHA-256：

| 数据库 | dump bytes | SHA-256 |
| --- | ---: | --- |
| `medops` | 14,495,272 | `7401671ca58409b34568a7154df42753fba424314ff311a4346c591e9d0813bc` |
| `medops_v2` | 210,989,057 | `7f45497ec54561ad41a38b971a71d551a90727564035da24089dfd6a86c998bd` |
| `medops_v2_safety` | 202,715,971 | `acf3d51ec874ecf6590fd60b55d1e24d224f9783cb67202f22e2be04beedd91c` |

备份目录 `backups/bm25-cutover-2026-10-09/` 被 Git 忽略。PG17 使用新卷和隔离端口 5436。空 bootstrap 库先完整升到 0022，以验证扩展和建立集群级 group roles，然后删除。三个 dump 以 `--no-owner --exit-on-error` 恢复。

升级 0022 前逐库比较源/目标：Alembic revision、public 表集合、逐表行数、chunk 哈希聚合指纹、grantee；三库全部相同、row-count mismatch 均为 0。原始 revision 为 `medops=0007`、另外两库 `0021`。随后三库升到 0022并构建 BM25：

| 数据库 | 已索引 published chunk | active chunk | lexical 缺口 | embedding 缺口 |
| --- | ---: | ---: | ---: | ---: |
| `medops` | 2,628 | 2,628 | 0 | 2,628（旧开发库从未建向量，不作为事实面） |
| `medops_v2` | 35,797 | 34,948 | 0 | 0 |
| `medops_v2_safety` | 36,122 | 35,273 | 0 | 0 |

正式库 active 333 份，安全库 active 339 份；两库 `lexical_version_ok=true`、`embedding_version_ok=true`、`ready=true`。真实语料的 MA/PV/CO 普通角色查询均返回 5 个 BM25 候选，未读取正文到日志。默认 5432 最后切到 PG17；旧 PG16 卷 `medops_postgres_data` 和三份逻辑备份保留。当前 PG17 卷为 `medops_postgres17_data`。

## 5. 真实遇到的问题

1. 首次用系统 `python` 跑 Ruff/mypy/import 失败，分别报 `No module named ruff`、`No module named mypy`、`No module named 'medops'`。原因是仓库工具链在 `venv/bin/python`；改用 Makefile 指定的解释器后通过。这没有修改代码或环境。
2. 第一次切换端口的轮询脚本把变量命名为 zsh 只读特殊变量 `status`，报 `zsh:11: read-only variable: status`。数据库容器已经成功启动；改为只读检查容器状态后确认 healthy。后续脚本避免使用 shell 特殊变量名。
3. 在切换前把旧 Compose 容器改名为 `medops-postgres16-rollback`，再执行 `docker compose up` 时，Compose 根据 service labels 识别并重建了该容器，因此没有保留“旧容器对象”。旧 PG16 命名卷没有被删除，且另有三份已核验 dump，回滚资产仍完整。之后把 PG17 volume 显式命名，避免项目名推导歧义。
4. `medops` 开发库的索引检查仍显示 2,628 个 embedding 缺口。它原本停在 migration 0007，历史上没有建立向量；`.env` 已指向 `medops_v2`，正式库和安全库均为零缺口。本次不加载本地嵌入模型去修复退役开发事实面，也不把它误报为生产故障。

## 6. 自审核与结果

- 定向静态门禁：Ruff、格式、mypy 189 个 source files 全部通过。
- 定向数据库门禁：迁移、RLS、生产词法、维护、完整性共 **102 passed**。
- Docker arm64 与 amd64 镜像均从固定资产构建成功；两个架构的 zip/deb 哈希、包版本、扩展二进制和 control 文件都已由构建步骤核验。
- 本机实际服务：PostgreSQL 17.11、`shared_preload_libraries=pg_textsearch`、extension 1.5.1、migration 0022、Compose healthy。
- 全量 `make check`：**1713 passed、70 skipped**；Ruff、440 文件格式、mypy、评测输入审计、Schema 漂移均通过。70 skipped 仍是未启动的 B/C 等实验环境，不计为通过。
- 零模型调用、零新增费用。

## 7. 剩余工作

- BM25-09：在当前新冻结集上做完整检索及答案级对照，另行给出样本、轮数、费用上限和停止条件后请求授权。
- CI 工作流的 service-container 安装、重启与 health 流程仍需在推送后由远端 runner 实际验证；本机已覆盖 arm64/amd64 镜像构建与完整测试。
- 正式验收报告的历史数字不重计；得到新冻结集运行结果后再更新业务质量、时延与费用结论。
