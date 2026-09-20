# DEC-001 候选 C：固定构建与合成 smoke

本目录只证明 pg_search **0.25.9** 能在固定 PostgreSQL **16.15 / linux arm64 / Debian 12 bookworm** 环境加载，并完成合成 Jieba 分词及基本 BM25 查询。C 的生产许可状态仍是 **`release_blocked`**；尚未证明普通角色、FORCE RLS、候选计数、性能、质量或生产选型门禁。

源码身份为 `c727757be0aab7fbb17c6cc5f0360f22efdd3776`。实际使用官方发布 DEB，没有使用该 tag 中仍下载 0.25.8 的旧 Dockerfile。下载文件 65,546,104 字节，SHA-256 已实算为 `69ac9f7ade7ec66b3e062d823e023f28440b5c87be30d6ee85b16f51eab549a9`。未验证其 cosign bundle，不将发布哈希校验描述为签名验证。

## 运行证据

- [build-metadata.json](build-metadata.json)：资产、源码、Docker 构建身份、完整 tokenizer 配置、失败及限制。
- [runtime-smoke.json](runtime-smoke.json)：最终运行版本、156 个已安装包的版本清单、实际词元、查询结果、执行计划和 warning；临时容器已删除。
- [smoke.sql](smoke.sql)：仅三条独立合成文本；先启用 `vector=0.8.6`，再 `CREATE EXTENSION pg_search`。
- [run_smoke.py](run_smoke.py)：通过 Docker inspect 的不可变 ID 启动临时容器；无网络、无发布端口、1 CPU、1 GiB 内存、512 MiB tmpfs 数据目录。正常或失败均删除本次容器。

实际扩展版本是 `0.25.9`，`paradedb.version_info()` 返回 release build。中英文单词查询、零匹配断言通过；“研究”返回合成 ID 1、2，同分按 ID 升序；执行计划为 `ParadeDB Base Scan / TopKScanExecState`。这些使用临时库的 bootstrap superuser，不能代表应用角色门禁。`array_agg` 产生的 Aggregate Scan 未采用 warning 已原样保留。

Docker 本地 inspect 返回的 ID 是 OCI index digest：

```text
sha256:f564d490dfa01b0d95b6f4f446d51ce188d537a18a2aac67c33a42466ea945ec
```

BuildKit config digest 为 `sha256:e9852729aff0222b14d9e6d834d48589e8713b59ced153c97d82b118718327fc`，平台 manifest digest 为 `sha256:cc7657cd6adfb42cb375518605bdac5ada22ba98f7c3cfa16a6cbb2468104901`。这三者分开记录。镜像没有推送；虽 Docker 本地提供 RepoDigest，`registry_digest` 仍为 `null`，不声称其他机器能从远程 registry 拉取它。

## 保留的分词诊断

配置固定为 `pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')`。未配置 length、stemming、stopwords、normalizer、繁简转换或自定义词典；完整 null/false 值与嵌入词典的二进制身份在 metadata 内记录。

默认 Jieba 保留空格词元。查询 `alpha gamma` 的实际词元为 `['alpha', ' ', 'gamma']`，OR 查询返回 **[1, 2, 3]**，因为三条合成文本都有空格。首次将结果假设为 [1, 3] 的断言失败，已保留为开发记录；此后仅将这个查询作为实际行为诊断，未更改 filters。方案编号样式的合成文本 `PROT-2042-123` 被切为 `['prot-2042', '-', '123']`。这些现象需由后续适配器的精确谓词、计数及质量实验评估；没有用 75 条探针挑选配置或调整参数。

## 复现

在仓库根执行。DEB 和构建上下文放入临时目录，不复制到 Git 工作树。需要 Docker，以及仓库 `venv/bin/python`（3.11.16）；macOS 系统 Python 3.9 不满足脚本运行环境。

```sh
c_build_dir=$(mktemp -d /tmp/medy-dec001-c.XXXXXX)
curl --fail --location --retry 2 \
  --output "$c_build_dir/pg_search.deb" \
  https://github.com/paradedb/paradedb/releases/download/v0.25.9/postgresql-16-pg-search_0.25.9-1PARADEDB-bookworm_arm64.deb
printf '%s  %s\n' \
  69ac9f7ade7ec66b3e062d823e023f28440b5c87be30d6ee85b16f51eab549a9 \
  "$c_build_dir/pg_search.deb" | shasum -a 256 -c -
docker build --platform linux/arm64 --progress plain \
  -f evals/experiments/lexical/builds/c/Dockerfile \
  -t medy-dec001-c:pg16-pgsearch-0.25.9-r28 "$c_build_dir"
venv/bin/python evals/experiments/lexical/builds/c/run_smoke.py \
  --out "$c_build_dir/runtime-smoke.json"
venv/bin/ruff check evals/experiments/lexical/builds/c/run_smoke.py
venv/bin/ruff format --check evals/experiments/lexical/builds/c/run_smoke.py
```

Dockerfile 固定基础镜像、DEB 哈希与 OpenBLAS 版本，并断言 PostgreSQL 包版本未升级。APT 仓库时间快照尚未固定；实际传递依赖版本已全部保存，因此后续重新构建可能得到新镜像 ID，须记录新身份并重新验证。当前本机后续实验应使用上面已验证的不可变 ID。不要将临时数据目录替换为现有 `medops-postgres` 的卷。

## 本轮九项自审

1. **需求**：仅固定 C 环境与合成 smoke；未新增医学能力、语料或真实探针查询。
2. **逻辑**：先校验资产，再安装并断言版本；实际发现 vector 依赖后显式启用；运行使用 inspect 得到的 ID，避免 tag 漂移；每次全新临时库。
3. **安全**：无网络、无端口、tmpfs 数据；trust 认证仅用于这个隔离容器；未读取应用凭证，未连接现有服务；失败清理只使用本次创建的容器 ID。
4. **契约**：未修改应用 Schema、migration 或检索接口；build smoke 与普通角色生产门禁分开记录；配置完整且 C 保持 `release_blocked`。
5. **测试**：真实 CREATE EXTENSION、运行版本、中英分词、单词检索、零匹配、BM25 与执行计划已验证；多词 OR 的初始假设失败后保留实际诊断，未宣称 OR/count/RLS 通过；未跑真实 probe。
6. **可观测**：保存 UTC 时间、运行输出、warning、SQL 哈希、包清单、扩展文件哈希、镜像 index/config/platform manifest；本地 smoke 不增加业务指标或 Trace。
7. **简洁性**：一个 Dockerfile、一个 SQL fixture、一个标准库 smoke runner；没有新增项目依赖；二进制只留临时目录。
8. **验证**：固定镜像构建成功；最终合成 smoke 通过并移除临时容器；`ruff check`、`ruff format --check` 通过。APT 快照、签名验证、正式适配器与生产许可仍未验证。
9. **Checklist**：仅将 C 的构建/加载/合成基本查询标为已验证；正式比较、ACL/RLS、计数、延迟、端到端指标及许可证结论保持未完成。

来源：[官方发布资产](https://github.com/paradedb/paradedb/releases/expanded_assets/v0.25.9)、[固定 Cargo.lock](https://github.com/paradedb/paradedb/blob/c727757be0aab7fbb17c6cc5f0360f22efdd3776/Cargo.lock)、[固定 tokenizer 实现](https://github.com/paradedb/paradedb/blob/c727757be0aab7fbb17c6cc5f0360f22efdd3776/tokenizers/src/manager.rs)、[固定许可证](https://github.com/paradedb/paradedb/blob/c727757be0aab7fbb17c6cc5f0360f22efdd3776/LICENSE)。
