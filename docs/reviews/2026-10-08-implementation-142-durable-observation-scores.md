# 记录 142：持久评分同步与评测关联

日期：2026-10-08。OPT-09。本轮代码及故障恢复自审通过；Langfuse 后端部署、真实服务器回读和 UI 演示未完成。

## 完成内容

1. `LANGFUSE_BASE_URL/PUBLIC_KEY/SECRET_KEY` 三项共同启用。API、worker、MCP 与主集/安全评测工具使用同一项目的 OTLP 目标和认证。配置冲突、部分配置、含用户名密码的 URL、非本机 HTTP 拒绝。默认仍关闭。
2. 本地 SQLite 持久队列绑定目标地址和项目 public key 的哈希；文件权限 0600，目录不入 Git。事件 ID、正文和原始时间不可变，重复入队幂等；接收确认后才 ACK，失败保留次数和安全错误码。更换项目不能沿用旧队列。
3. 独立同步进程只读 PostgreSQL 的反馈 ID、trace ID、signal 和时间，不读取 query、principal、correction_text。反馈用 up/down/correction 分类展示，未把用户纠正直接换算成答案质量分数。
4. 扫描分页游标持久化；每轮扫到末尾后重新扫描，用队列去重。这样晚提交且 UUID/时间早于当前游标的反馈仍能被后续轮次发现。只读事务及全局审计读取身份有检查；未提交的反馈不可见。
5. 主集/安全新结果记录实际 trace_id 与 observed_at。安全 Skill 原本按题号生成固定 trace ID，现改为每次尝试生成独立 ID，避免多轮观测合并。
6. 导入评分前验证运行条件文件自身哈希、冻结数据集版本/哈希、全部 attempt/sample/版本绑定。主集重新计算 outcome 规则并核对原记录；安全检查核对已有布尔检查。每个尝试独立评分，全部标 formal_gate=false；它们不是语义支持/完整性分，也不是最终数据集均值。
7. 未触发安全行为导出 `evaluation_status=not_exercised`，不写通过或零分。缺 trace/time、旧无绑定运行、漂移数据和不一致判词拒绝。
8. 发送评分前，以 `fields=core` 查询同项目的 observations v2，确认 trace 已可见；未导出、丢失、旧随机 OTel ID 或暂未落库的 trace 保留 pending，避免制造孤立评分。

## 为什么使用这个接口

查询时最新发布为 [Langfuse v4.54.0](https://github.com/langfuse/langfuse/releases/tag/v4.54.0)。官方[评分说明](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk)说明去重涉及 ID、名称及时间日期。核对[该版本创建服务源码](https://github.com/langfuse/langfuse/blob/v4.54.0/web/src/features/public-api/server/scores-api-service.ts)后发现普通 POST `/scores` 每次创建新的事件时间，重试无法显式保持原日期。

因此当前适配器发送固定时间的 `score-create` 事件到兼容 ingestion 接口；[该版本入口源码](https://github.com/langfuse/langfuse/blob/v4.54.0/web/src/pages/api/public/ingestion.ts)仍允许 score 事件，包括 events-only 模式。这个兼容入口已标弃用，不能当作永久接口；部署升级必须重验或迁移到能保持同等语义的新接口。Trace 继续走 OTLP，没有退回 legacy trace ingestion。

查 trace 使用[版本化 observations v2 入口](https://github.com/langfuse/langfuse/blob/v4.54.0/web/src/pages/api/public/v2/observations/index.ts)。它依赖 v4 模式/相应启用条件，旧 v3 后端不会被静默兼容。正式部署必须验证该 API 与实际镜像配置。复用现有 httpx/SQLite/OTel，无新增依赖锁；完整 Langfuse SDK 可作为后续兼容替代，但仍需审计时间及正文采集行为。

## 可靠性与边界

- 同步在请求事务外执行；平台不可用不阻塞问答或反馈写入。核心数据库审计失败关闭保持。
- HTTP 使用 10 秒超时、不跟随重定向、不继承环境代理；错误输出不含服务器正文、连接秘密或纠正文案。停止信号到达后在当前请求完成后停止后续发送。
- 每批独立尝试各事件，一个失败事件不会撤销已经确认的其他事件。进程在接收成功后、ACK 前崩溃时仍可能重发，需要固定事件身份的后端去重。
- ACK 表示 ingestion 接口接受，尚不等于 ClickHouse 可查询、UI 已显示或保留策略已经执行。后者需要真实后端回读验证。
- 原始审计以 PostgreSQL 为准。当前为本机队列，未提供多主机共享队列、永久进程管理或自动清理策略。删除队列会丢失本机发送历史；不得随意清理。public key 轮换会改变目标指纹，需要明确迁移队列。
- 旧运行没有 trace 身份和时间，不补造。历史反馈可以排队，但没有对应后端 trace 时不会发送。当前没有实现历史 audit trace 导入，也没有声称历史观测关联完成。

## 验证

新增 **44 项**：包括固定 ID/时间重试、ACK 丢失后重启恢复、目标隔离、严格字段白名单、远端错误/部分响应、停止发送、trace 不存在、配置秘密隐藏、主集/安全分数与绑定校验，以及真实数据库的晚提交、未提交不可见和只读/权限边界。

`env -u DEBUG make check`：**1594 passed、70 skipped、1 warning，38.35 秒**；184 个源文件类型检查、417 个文件格式、Schema 和评测输入检查通过。70 项跳过和测试用 HMAC 短密钥警告同前，未增加正式业务分数。

真实 CLI 以 `--enqueue-only` 分别读取 medops_v2 与 medops_v2_safety：每库 2 条反馈入本机测试队列，文件权限 0600，发送数 0。使用明确的本机测试目标和合成认证配置；没有启动或访问 Langfuse 后端。见[实际采集记录](2026-10-08-implementation-142-live-feedback-harvest.json)。业务库写入 0、HTTP 发送 0、模型调用 0。

修复过程保留：初次集成测试误用 fixture 的 `db['app']`，改为实际 `db['users']['app']`；首次全量发现 `.env.example` 的占位符含 `sk-`，违反仓库示例密钥检查，改用 replace-me。批量脚本编辑先遇到主入口是 sys.exit 而非 raise SystemExit 的断言，核对后完成剩余编辑，没有重复写入已修改部分。随后重新全量通过。

## 五项自审

| 项 | 结论 | 依据 |
| --- | --- | --- |
| 范围 | 通过 | 观测和评分同步，不改业务门槛或默认开启状态 |
| 正确性/失败 | 通过 | 固定事件、重启、ACK 丢失、未触发/缺测、停止和部分错误测试 |
| 权限/追溯 | 通过 | 元数据只读、目标绑定、0600；未见 trace 不发送；无正文字段 |
| 验证 | 通过 | 44 项新增、全量及两库真实只读采集 |
| 状态/文档 | 通过 | 区分本地队列、接口接受、真实后端物化与 UI 验收 |

## 下一步

准备锁定版本的本地 Langfuse 部署清单，明确对象存储许可、Docker 资源及保留方案，再实际验证 OTLP→trace 查询→评分→评分回读→人工反馈；这仍是阶段 3 的完成前置。新数据集模型复核、第二人工和盲测等仍沿用阶段 1 pending 状态。
