# 记录195：备份/恢复的口令与临时库边界

2026-10-12，CODE-01；HEAD75c751d，CODE-07已经四批推送。本轮实现者/自审者Codex，同一模型，不是第二独立人工。只处理运维备份/恢复的安全卫生和直接失败路径，不修改数据库迁移/事实数据、默认模型、索引、评测或发布指针。没有托管模型调用，本轮费用0USD。

## 原缺陷与修复

- 两脚本的 `docker exec -e PGPASSWORD=<值>` 把管理口令放入argv；原“Nothing secret leaves the process”并不成立。改为裸 `-e PGPASSWORD` 与独立child env，保留Docker连接环境，剔除child env中的 `DATABASE_ADMIN_URL`，父环境不变、不使用shell。
- Docker stderr可能回显DSN/口令。共同 `pg_subprocess` 先替换已知完整DSN、解码DSN、原口令、原URL编码及quote/quote_plus形式，再截取尾部，避免截断后留下口令后缀；保留其余诊断。启动OSError仅记录类型，不输出可能含秘密的消息。环境可由宿主机/容器管理员读取，本轮不声称有密钥托管/全系统日志分类器。
- 新dump以0600排他创建；目标已存在拒绝覆盖，启动失败/非零退出删除本次半成品，成功自带SHA-256旁文件。沿用pg_dump custom格式、所有者/授权信息及原CLI选项，新增项目公共基础设施导入，须使用已安装项目的Python环境。
- 自审直接发现恢复脚本预删固定 `<source>_restore_drill` 的既有库，且restore非零后仍尝试完整inventory。改为UUID临时库，不预删；只有本次成功创建后才进入finally清理，不接管同名既有库。restore失败记录FAILED，不对半成品inventory；成功沿用原alembic/表/逐表行数/语料MD5/grantee/fact-plane identity判据。
- CI显式配置其PostgreSQL容器名；本机默认medops-postgres。不是新建业务数据库部署、重启共享服务或迁移业务库。

## 验证与迭代

第一次静态检查发现两处新测试import分组，按Ruff规则纠正，不放宽门禁。

定向 `tests/unit/scripts/test_db_tools.py tests/integration/test_backup_restore.py tests/integration/test_feedback_export.py`：21 passed，pytest4.23秒、总5.123秒，required服务模式，无skip。包含带Unicode/URL字符/shell符号的明确假口令、argv/env/父环境、私有文件/哈希、不覆盖、非零/启动异常、脱敏后截断、创建碰撞不得drop、真实容器backup→restore、坏dump失败后自己的scratch已删除；原inventory与事实平面身份回归保持。实际恢复仅针对session唯一测试库，不读取真实业务语料，不替代正式灾备演练。

**required `make check`退出0：2265 passed、70 skipped、1 warning，pytest92.85秒、总121.354秒。** 678格式文件、mypy325、架构325模块零违例/2既有精确例外，4套冻结审计与公开Schema通过。70 skip来自可选B/C实验；1 warning为测试短HMAC。677维护输入与仓库外验证树SHA一致，两个CLI的 `--help` 输出/退出码逐字相同。没有对1023历史JSON重新全量哈希。

CODE-07的75c751d远端[CI38191713877](https://github.com/Charlie-Uni/Medy/actions/runs/38191713877)全部28步骤成功，包括运行镜像/真实容器门。本轮按自己的最终SHA另验。

文档32 passed，142任务集合不变，115个本地链接存在，冻结数据/迁移/Schema/策略无tracked diff。机器证据见[机器结果](2026-10-12-implementation-195-results.json)。

## 八项自审核

| 项目 | 状态 | 证据/范围 |
| --- | --- | --- |
| 需求/范围 | 通过 | 核实原argv缺陷，修复口令/日志及直接关联的临时库/文件失败路径 |
| ADR/阶段门 | 通过 | 不变Agent/自进化目标、PLAN-02、盲测、付费及生产签字边界 |
| 正确性/失败 | 通过 | 假凭据反例和真实pg_dump/pg_restore、坏dump与启动失败；创建失败不drop |
| 权限/数据 | 通过 | 只用隔离测试库；source inventory相同，dump0600，不修改业务库/冻结材料 |
| 预算/取消/副作用 | 通过 | 0托管调用/费用；保留原同步CLI时限，未新增总时限承诺；共享部署未变 |
| 追溯/兼容 | 通过 | SHA旁文件和原比对指标保持；报告注明新唯一scratch及原错误退出；历史演练不重写 |
| 验证充分性 | 通过 | 定向21、required全量2265/70、677输入一致、CLI帮助一致；不代替业务灾备/医学质量 |
| 状态/文档 | 通过 | IN_PROGRESS→REVIEW→工程DONE；运维说明、台账与自审结果同步，不宣称正式灾备完成 |

## 限制与下一步

容器必须由运维明确匹配源数据库实例，脚本仍在指定容器内部连接localhost；本轮不是跨主机备份设计。临时库cleanup连接失效时不能保证删除，进程被kill也可能留下临时库；同一默认报告目录仍可能被多次运行覆盖，部署定时任务应提供独立 `--out`。child env保留Docker连接所需的其他继承变量，没有扫描全部环境中的秘密。普通脱敏只覆盖已知凭据形式，不是任意外部工具输出的秘密分类器。备份目录、KEK异地备份、正式灾备/RPO/RTO和长期部署仍由DEPLOY-02验收。

回滚源码可恢复旧执行方式，但不建议恢复argv口令和固定scratch删除；不删除已生成的备份或历史报告。接下来CODE-02核实当前全部恒真断言，随后按台账做CODE-03/06。已推送CODE-07的CI回执按75c751d单独登记。

## 分批提交

- `d763cf1`：security，3个路径，精确暂存/cached diff通过。
- `62c5556`：verification，3个路径，精确暂存/cached diff通过。
- 第三批文档：运维说明、台账、README与自审/机器清单；最终SHA从Git查询，推送与CI分别核对。
