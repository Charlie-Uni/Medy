# DEC-001 候选 D：`pg_textsearch` BM25（ADR-0002 修订 5）

固定环境：`pgvector/pgvector:pg17`（PostgreSQL 17.11）+ `pg_textsearch` 1.5.1 官方发布 deb（PostgreSQL License）。资产、镜像与冒烟结果见 [build-metadata.json](build-metadata.json)。

冒烟（隔离容器，无网络、无端口、tmpfs 数据目录）核到的行为：

- `<@>` 运算符返回**取负的** BM25 分数（越小越相关），不含任何查询词的行得 0 分且仍会被 `ORDER BY … LIMIT` 返回——适配器用 `< 0` 谓词把它们排除。
- 行级权限下 2 万行（19,000 行被隐藏且得分更高）：PV 读者 k = 20 / 500 / 2000 分别得到 20 / 500 / 1000（全部可见匹配）行，执行计划是 BM25 索引扫描 + 策略逐行过滤，没有静默不足，零泄漏。
- 语料统计（词频、文档频率）包含被隐藏的行：排序受其他部门文档影响。ADR-0002 修订 5 把这项评估列为进生产前的硬门禁。

复现：

```sh
d_build_dir=$(mktemp -d /tmp/medy-dec001-d.XXXXXX)
curl --fail --location --retry 2 --output "$d_build_dir/pg_textsearch.zip" \
  https://github.com/timescale/pg_textsearch/releases/download/v1.5.1/pg-textsearch-v1.5.1-pg17-arm64.zip
unzip -q "$d_build_dir/pg_textsearch.zip" -d "$d_build_dir/unpacked"
cp "$d_build_dir"/unpacked/pg-textsearch-postgresql-17_1.5.1-1_arm64.deb "$d_build_dir/pg_textsearch.deb"
docker build --platform linux/arm64 -f evals/experiments/lexical/builds/d/Dockerfile \
  -t medy-dec001-d:pg17-pgtextsearch-1.5.1 "$d_build_dir"
docker run -d --name medy-dec001-d-exp --platform linux/arm64 -p 127.0.0.1:5435:5432 \
  -e POSTGRES_DB=medops -e POSTGRES_USER=medops_admin -e POSTGRES_PASSWORD=<local only> \
  -v medy_dec001_d_data:/var/lib/postgresql/data medy-dec001-d:pg17-pgtextsearch-1.5.1 \
  -c shared_preload_libraries=pg_textsearch
# .env.dec001: DEC001_D_ADMIN_URL=postgresql://medops_admin:<password>@localhost:5435/medops
env -u DEBUG -u PYTHONPATH venv/bin/python -m pytest tests/integration/test_lexical_pg_textsearch_bm25.py -q
```

适配器：`medops.retrieval.lexical.pg_textsearch_bm25`（`pg-textsearch-bm25-v1`，索引表 `lexical_index_d`，与生产引擎 A2 同一套 `tok-jieba-v2` 词元，只换排序引擎）。
