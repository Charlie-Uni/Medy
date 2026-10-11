# 记录186：部署资源、常驻消费者与进展监督（ARCH-13）

日期：2026-10-11。实现/自审：Codex；不是独立人工复核。起始HEAD `69fca598e405423b14f7a04e9336bdadc8f33163`，记录185已有12个工作区路径已逐一备份。本轮生命周期 READY → IN_PROGRESS → REVIEW → DONE；仅对应范围工程自审通过。0托管调用、0USD；未提交、推送、替换共享服务或迁移业务库。

## 1. 范围与实现

部署契约详见[常驻消费者与监督](../DEPLOYMENT_WORKERS.md)，配置为根Compose、[KEK overlay](../../docker-compose.payload.yml)、[Dockerfile](../../Dockerfile)、[宿主评分模板](../../deploy/systemd/medops-score-sync.service)。原方法/版本、冻结标注、原验收门不变。

- 公开版本词表进入镜像 `/app/glossary`；容器不依赖宿主绝对路径。构建上下文排除 `.local`/output/评测数据，只重新纳入词表JSON。
- KEK显式只读挂API/Task，不挂MCP或维护；合成私有文件验证权限。评分队列持久卷UID10001/0600。专用restricted/loop容器DSN格式与空串校验补全。
- 词法/向量/缓存有统一Compose常驻入口；评分、清理、Observe是opt-in profiles。共享YAML锚点避免重复配置；每个服务有CPU/内存/PID限制。
- 完成轮次才刷新心跳，监督器验证本次token/PID/单调时钟；健康同时检查父进程/新鲜度。卡死先TERM整进程组，再限时KILL/回收并非零退出，由restart策略重启。没有用Docker unhealthy冒充自动重启。
- Task监督收束140秒，容器150秒；其他消费者20/30秒。Task/词法/向量/缓存/评分停滞限400/90/300/90/180秒，启动300秒。MCP健康覆盖镜像错误的API8000端口，检查自身8001，仅是socket存活。
- 自动清理复用既有保留函数和专用角色，事务advisory lock不重叠；Observe扫描所有保留Trace、幂等建案例，避免滚动created_at窗口漏掉晚到反馈。生成候选、付费评测、激活仍未被调度。

## 2. 实际验证

| 验证 | 结果 | 解释 |
| --- | --- | --- |
| worker/config/outbox入口/既有评分单元 | 79 passed / 6.34s | 含真实子进程终止/停机，不只mock |
| Compose渲染契约 | 2 passed / 0.23s | 12服务，8监督入口；资源/库名/宽限/KEK范围 |
| PostgreSQL维护/保留/新调度 | 22 passed / 2.11s | 毒事件无ACK/回滚/显式重放、专用角色、事务锁、晚到材料 |
| 镜像构建 | arm64锁构建与pip check退出0 | 检查镜像独立tag，不替换dev运行实例 |
| 镜像与源码 | 218模块、零差异、UID10001 | 最终镜像重新包含清理修复；没有加载/调用模型 |
| 容器故障 | 进展后healthy，卡死强杀，restart_count=1 | 合成子进程与隔离容器，不是生产长期驻留 |
| 真实CLI容器停机 | 依赖失败可重试，SIGTERM退出0，无重启 | 不连接共享业务库 |
| 合成KEK/队列卷 | 0600可读/创建，0644密钥拒绝 | 无真实密钥接触；队列不发送HTTP |
| 最终make check | 2136 passed / 70 skipped / 1 warning，退出0 | lint/510格式/mypy218/架构0违例2精确允许/4数据集审计/schema通过 |
| 输入一致性 | 548维护输入SHA一致 | 仓库外工作树与工作区一致，规避iCloud解释器隐藏路径问题 |

最终完整门禁耗时180.755秒（pytest 174.22秒）。测试warning为既有合成JWT短HMAC key；跳过项仍为既有可选实验，required CI语义是下一项ARCH-14，不以跳过证明依赖通过。

原始证据在忽略的 `.local/arch13/`：备份/start、容器结果、构建后的源码比较、两次门禁日志/结果；核验树由 `.local/arch13-worktree-path` 定位。真实.env副本私有且字节一致，未输出DSN/key或原始Compose配置。临时容器、命名卷及两份确认空的匿名模型卷已清理；保留无关卷。测试镜像和验证工作树留作可复核工件。

## 3. 自审发现的错误与补救

1. 首次PG运行全部15跳过；宿主DEBUG非法。原文：`Input should be a valid boolean, unable to interpret input`。改用 `env -u DEBUG` 后真实数据库测试通过，不把跳过计成成功。
2. 首次lint有I001/F401/UP031，mypy对`Any | None`数字不能收窄；修正导入、f-string、明确数字/布尔排除和格式，最终门禁全过。
3. Compose渲染把150秒规范成`2m30s`，新增测试初稿报 `ValueError: could not convert string to float: '2m30s'`；修正单位解析。诊断脚本曾报 `TypeError: argument of type 'NoneType' is not iterable`，因某服务command为None；汇总改成空列表，不影响Compose本身。
4. 第一次完整门禁：1 failed、2130 passed、70 skipped，make退出2。原文：`psycopg.errors.RestrictViolation: bad cases are never deleted`，`PL/pgSQL function medops_bad_case_guard() line 7 at RAISE`。新Observe任务真实暴露：旧Trace对应的新案例/反馈尚未到期，旧purge按Trace年龄整组删除，触发逐行保留栅栏。修复候选SQL，关联case/feedback/span/closed escalation/replay report任一尚未到期就保留父Trace；原365天/最小90天和触发器不变。五类回归均证明保护新材料且继续清理真正过期、无新材料的Trace。
5. 新回归初稿以admin种Trace遭 `psycopg.errors.InsufficientPrivilege: permission denied for table traces`，5 failed/17 passed。admin没有INSERT是正确权限；改由fixture owner在回滚事务种数据，执行前SET LOCAL ROLE到medops_admin_role，未放宽授权。22条PG回归通过。
6. 短时容器的镜像VOLUME产生两份空匿名模型卷，首次清理只移除命名卷。按私有演练时间/匿名标签/悬空状态限定，再只读确认空后移除两份；未批量prune或删除未知卷。

## 4. 八项自审核

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 需求与范围 | PASS | ARCH-13资源、词表/KEK/队列、三消费者/评分、清理/Observe调度与监督；IDX-03长期部署/DEPLOY-02目标容量保留未完成。 |
| ADR与阶段门 | PASS | 保留ADR-0012、ARCH-04/11、原生产签字/独立人工/盲测/逐次付费；未解锁S2/S3。 |
| 正确性与失败路径 | PASS | 真实子进程启动停滞/完成后卡死/强杀/优雅停机；Docker重启；PG毒事件/回滚/重放；修复晚到审计记录清理冲突。 |
| 权限与数据 | PASS | 显式库名及专用角色；Loop不回退admin；镜像UID10001；合成KEK0600可读、0644拒绝；MCP不挂KEK；冻结数据无变化。 |
| 预算、取消与副作用 | PASS | 0托管调用/0USD；维护白名单不含生成、评测、激活；信号、进程组、超时及Task140/150秒宽限；共享服务未替换，真实保留清理未执行。 |
| 追溯与版本 | PASS | token/PID/单调时钟隔离心跳；评分队列身份/ID和outbox审计保持；不变模型/策略/检索版本。 |
| 验证充分性 | PASS | 79定向+2Compose+22真实PG；最终make check 2136/70退出0；548维护输入SHA一致；镜像源码核验和隔离故障证据。 |
| 状态与文档 | PASS | 记录186/台账/部署与运维契约同步；工程自审与生产驻留、容量、systemd安装分开；记录185原工作保留，当前改动未提交推送。 |

## 5. 完成边界与下一项

ARCH-13工程实现通过；IDX-03实际长期驻留、DEPLOY-02目标资源/容量/完整部署恢复仍未完成。本机Docker只有约7.75GiB，应用/维护限制合计29.75GiB，不宣称全开可运行。评分容器要可达HTTPS；本机localhost Langfuse由宿主OS监督，systemd模板未在macOS安装或验证。保留现有HTTP信任规则，未偷加内网例外。清理profile未对共享库启用，未执行真实删除；Observe全保留Trace扫描规模仍须目标环境测量。

下一主项ARCH-14：required CI依赖不可用必须失败、可选实验保留条件跳过，补已发布配置容器启动/架构门。ARCH-12仍等ARCH-14。PLAN-02、Task/MCP回放与MCP受限材料、独立人工、真实语义校准、盲测、Agent和自进化未因此完成；付费逐次授权、自动激活仅实验和生产签字继续保留。

文档同步后另验：27 passed / 4.91s；8份文档176个本地链接有效，原台账ID列表不变，8个非文档的既有改动路径字节未变，548维护输入一致，冻结评测与Schema无diff。最终镜像218模块与本工作区SHA一致，镜像ID `sha256:04a5d57fa4c6f5973129b48d74cb082abad407817a0f669128a871822e7ff3dd`。
