# CI 必需依赖与容器启动门禁

本契约对应 ARCH-14。工程核验记录见[记录187](reviews/2026-10-11-implementation-187-required-ci-and-container-gates.md)。

## 1. 必需服务与可选实验

`CI=true`、`GITHUB_ACTIONS=true` 或 `MEDOPS_TEST_REQUIRED_SERVICES=1` 任一成立，就进入必需模式。CI 中设置 `MEDOPS_TEST_REQUIRED_SERVICES=0` 不能取消这一要求；非法值是配置错误。

| 依赖 | 必需模式 | 本地可选模式 |
| --- | --- | --- |
| PostgreSQL | 必须显式设置 `MEDOPS_TEST_ADMIN_URL`；地址缺失、格式错误、连接失败均使 pytest 非零退出 | 可从本地 `.env` 获取管理员地址；服务缺失可 skip，并给原因 |
| Redis | 必须显式设置 `MEDOPS_TEST_REDIS_URL`；缺失、格式错误、连接失败或 PING 不成功均失败 | 可从 `.env` 获取地址，缺服务可 skip |
| Docker / Compose | 二进制或插件缺失均失败；配置渲染失败始终失败 | 二进制或插件缺失可 skip；实际配置错误仍失败 |
| `jieba` | 基础锁定依赖，导入或初始化失败会报错 | 同样要求安装；不再跳过其测试 |
| DEC-001 的 B/C/D 实验服务器 | 保留独立显式地址和可选跳过；生产 BM25 在必需 PostgreSQL 上测试 | 同一规则 |

必需模式不回退读取开发者 `.env`，以免 CI 意外使用业务库。测试错误只写服务名称、固定原因和异常类型，不输出地址、密码或异常消息。Compose 检查使用公开 `.env.example` 做插值，`--no-env-resolution` 阻止读取服务的私有 `.env`。

普通 `make check` 根据上述模式执行。要在本地强制服务门禁，先通过私有环境注入两条 `MEDOPS_TEST_*_URL`，再执行：

```sh
env -u DEBUG MEDOPS_TEST_REQUIRED_SERVICES=1 make check
```

## 2. 工作流次序

`.github/workflows/ci.yml` 的必需步骤依次覆盖：固定 PostgreSQL 镜像和 pg_textsearch 安装、Redis 健康、锁定 Python 依赖、包安装、lint/format、mypy、静态架构边界、pytest、冻结数据审计、迁移往返、Schema 漂移和探针示例，然后构建实际运行镜像并执行容器启动门禁。整个 job 有 45 分钟上限。

架构检查直接运行 `scripts/check_architecture.py`，沿用既有两条精确例外。模型缓存只包含固定 revision 的公开 BGE 文件；缓存未命中会下载，缺失或损坏导致后续加载失败。使用 `actions/cache@v4` 的 `path`/`key` 接口，缓存键包含模型定义及下载脚本摘要，参见[官方说明](https://raw.githubusercontent.com/actions/cache/main/README.md)。缓存不包含环境文件、语料、评测题、模型 API 密钥或账单信息。

## 3. 已发布配置容器核验

`deploy/ci/released-policies.json` 是 2026-10-11 只读核对后保存的公开配置快照：`hybrid@2026-09-30-c41bd6d8`，包含固定词表、多查询、文档聚焦和 `gpt-6-luna` 查询翻译设置。新的正式发布需要审核并同步这个快照。CI 为临时数据库建立自己的测试策略 ID 和 `ci:fixture` 测试批准记录；这不构成生产审批。

独立入口：

```sh
make PY=python ci-container-check
```

它要求显式提供以下环境变量，未提供就报错：

| 变量 | 用途 |
| --- | --- |
| `MEDOPS_TEST_ADMIN_URL` | 创建/删除临时测试数据库及临时 LOGIN 用户的测试服务器 |
| `MEDOPS_TEST_RUNTIME_IMAGE` | 本次准确构建的运行镜像；没有旧镜像默认值 |
| `MEDOPS_TEST_MODEL_CACHE` | 固定 revision BGE-M3 与 BGE reranker 的公开文件缓存 |
| `MEDOPS_TEST_CONTAINER_DB_HOST` | 容器可达的测试 PostgreSQL 主机名；使用容器内 5432 端口，不继承宿主随机映射端口 |
| `MEDOPS_TEST_CONTAINER_NETWORK` | Docker 测试网络 |
| `MEDOPS_TEST_CONTAINER_MEMORY` | 可选内存上限，默认 6 GiB；本机核验须按可用资源显式限制 |

核验过程：

1. fixture 创建数据库，迁移到 head，建立临时 app/admin/readonly 身份；合成一份文档、一块正文并建立真实部门 BM25。
2. 将公开已发布配置复制到这个临时库，通过 app 身份回读并核对内容。
3. 运行同一个镜像，真实 BGE-M3 对合成正文生成向量；索引版本、维度、归一化和内容保持真实。
4. 使用镜像默认 API 启动命令加载真实 BGE-M3 / reranker，通过容器内回环 HTTP 验证 `/healthz=200`、`/readyz=200`、UID=10001。internal 网络不依赖宿主端口映射；公开的 CI 探测脚本只读挂载，不替换 API 启动命令。
5. 删除临时库向量，等待最多 15 秒（包含现有 5 秒 readiness 缓存），验证 `/readyz=503`，服务存活检查仍为 200。
6. 核对没有模型费用预留记录；最后删除本次容器、私有环境文件、临时用户和数据库。模型目录显式只读挂载，避免匿名 `/models` 卷。

CI 使用私有 internal 网络连接测试 PostgreSQL；推理缓存离线加载。OpenAI 密钥是不可用的合成字符串，SDK 地址指向容器内无服务端口，月预算为 0。不会调用 Ask 或任何托管模型接口。真实身份密钥、生产数据库、生产策略指针和共享服务不参与容器测试。

公开模型缓存目录及文件必须允许运行镜像 UID=10001 读取；只调整这些公开文件的权限，不调整秘密文件。排障可设置 `MEDOPS_TEST_CONTAINER_DIAGNOSTICS` 到私有本地目录，失败时保存最多 64KiB 原始输出的 0600 文件；不打印、不自动上传这些原始文件。

## 4. 完成口径与限制

本门禁验证基础服务缺失会阻止检查通过、实际镜像能加载指定已发布配置、真实本地模型及真实索引，以及索引故障会关闭就绪状态。它使用合成材料和临时身份。

容器核验不提供答案质量、独立人工、未见盲测、吞吐容量、长期运维或生产审批证据。API/Task/MCP 同时驻留的资源预算和真实部署继续归 DEPLOY-02 / IDX-03；正式质量和性能运行继续逐次授权。架构检查沿用既有边界，新的 Agent / 自进化阶段仍按 ADR-0012 和 PLAN-02 约束推进。
