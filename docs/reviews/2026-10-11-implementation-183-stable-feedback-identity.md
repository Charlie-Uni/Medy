# 记录183：ARCH-09 稳定反馈来源与恢复

日期：2026-10-11。实施者/自审核者：Codex；不是第二独立人工。任务 ARCH-09，Goal OPT-09/16。开始时 READY，依照“继续”推进无付费工程；本轮进入 IN_PROGRESS，经历IN_PROGRESS、REVIEW与修复复测，最终八项工程自审通过，记DONE。

HEAD `5a604050b9c0706bfd823685e5befcb9619d64a6`；开始前246个未提交路径逐一备份，没有提交、推送、发布、默认模型/冻结 gold/门禁变化。具体使用规则见[反馈身份契约](../FEEDBACK_IDENTITY.md)；[机器结果](2026-10-11-implementation-183-results.json)。

## 1. 原因与修改

原采集以包含 postmaster 启动时间的 readiness 指纹作为反馈来源。数据库重启使来源、score ID 与 cursor namespace 同时变化。去掉启动时间仍不能保证跨集群身份唯一，因此改为事实库持久 UUID；原运行指纹继续用于就绪检查。

0025 新增单行 UUID 表，admin/loop 仅读；只读采集按 UUID 取 cursor。旧队列采用不可变 namespace 绑定，保留原 score ID、metadata 和原始 timestamp。未知旧源拒绝采集，明确绑定后从头扫描，已入队和远端原 ID 去重。namespace 绑定原子且唯一，不能被另一份事实库占用。

增加只读查看与迁移 owner 的显式 clone rotation CLI、部署 UUID 校验。恢复保留 UUID 和队列；独立克隆必须旋转身份并隔离目标项目。恢复演练 inventory/report 增加 UUID 相等检查。没有自动克隆识别或远端历史重复清理。

## 2. 初步核验与失败保留

- 首轮定向82 passed / 6.14s；扩展并发/迁移22 passed / 1.24s，退出0；后续失败与最终结果如下。
- 三库升级前后31张保护表内容 SHA、5索引行数不变；各具不同 UUID，localhost/127.0.0.1 实连同一库 UUID 相同；三库均0025，0托管调用。原运行指纹不变，未重启。
- 首次备份命令误用宿主旧 Python，`datetime.UTC` AttributeError；没有修改项目或台账，改用锁定 venv 完成备份。
- 首次保护摘要脚本假设已有 pgcrypto `digest` 函数，UndefinedFunction，发生于迁移前。改用客户端流式 SHA-256，不安装扩展、不改依赖；失败摘要留 `.local/arch09-database-first.json`，最终三库报告 `.local/arch09-database.json`。
- 恢复脚本配套测试导入顺序 I001，按规范修复；没有改恢复条件以绕过测试。
- 首轮全量：5 failed / 2084 passed / 70 skipped / 187.21s，make退出2。三项权限清单未包含新表：grant matrix 多出 `fact_plane_identity: SELECT`、hidden集合误把元数据当无权表、forced RLS集合缺该表；按实际最小只读权限更新清单并保留无写入反例。
- 另两项是短时限测试未控制工件/数据库I/O：50ms Skill handler 测试在工件扫描处抛 `DeadlineExceeded`；双worker未知 usage 结算场景在handler同步前已返回 `outcome='lost', record=None`。真实工件采集耗时本来就计入执行预算，本轮没有改变这项失败关闭行为。
- 分别隔离工件扫描后，初次修复定向1 failed / 70 passed / 25.77s；将测试租约改1秒后，16项定向通过，但第二轮全量仍2 failed / 2087 passed / 70 skipped / 314.83s（make退出2）：一个接管worker也失租，一个原worker未到达同步点。没有把定向通过冒称完整通过。
- 最终双worker测试用真实数据库事务与可控租约时钟，显式越过库中lease_until；仅该合成Skill配置5秒以完成SQL/费用动作，租约10秒用于虚拟失效。保留旧调用不能再次付费、旧结果不覆盖新结果、两条attempt、两份回执和已知/未知费用断言。生产默认租约/Skill配置完全未改，真实数据库时钟/锁等待与短deadline反例继续运行。
- 配套50项：真实TaskStore、worker费用/失租、TaskLease短时限、工件采集期限及Skill registry全部通过，33.59s、退出0。最终全量退出0：2089 passed、70 skipped、1 warning，174.56s；lint、503维护文件格式、216源文件mypy、216模块架构边界（0违例/2精确允许边）、评测审计与Schema均通过。

## 3. 最终核验证据与八项自审：通过

最终命令：`env -u DEBUG PYTHONPATH=<snapshot>/src:<snapshot> make check`；核验工作树由`.local/arch09-worktree-path`定位，开始快照由`.local/arch09-backup-path`定位。536维护输入/配置SHA一致，0missing/mismatch；本地秘密配置只比较字节相等，不输出内容或摘要。1023已有evals/Schema JSON/JSONL与开始状态一致，没有改冻结数据/gold、历史结果、评分分母、阈值、默认模型或发布指针。

五个CLI检查：identity/worker帮助退出0；clone缺expected-id、feedback绑定非法UUID均在连接/创建队列前退出2；实际主库UUID只读查看退出0并与迁移报告相符。0024:0025离线SQL渲染退出0。三库纯本地采集后重开队列重扫，0新增ID，未做HTTP导出。首轮82项及22项扩展、最终50项异常/租约定向均已有日志，最终全量覆盖全部修改。

70 skipped 是既有可选B/zhparser 45项和C/pg_search 25项不可达；当前PostgreSQL、Redis、D/BM25必需集成实际执行。JWT warning是既有故意短HMAC认证反例。四集审计继续保留2个unmappable miss、旧安全回放、第二人工缺口和无未见盲测提示，不把这些警告清除。

| 自审项目 | 结论 | 本轮依据 |
| --- | --- | --- |
| 需求与范围 | 通过 | ARCH-09四项已实现；元数据身份/旧队列/游标/恢复规则，不宣称Agent或质量提升 |
| ADR与阶段硬门 | 通过 | ADR-0012及S2/S3约束保持，未改业务范围/门槛/自动批准 |
| 正确性与失败路径 | 通过 | 同源重开、入队后崩溃、迟到低UUID、旧payload保持/receipt回收、并发绑定/冲突、错UUID/缺迁移、迁移往返与最终全量 |
| 权限与数据 | 通过 | 新表只有admin/loop只读；角色写入拒绝；只选控制元数据；三库31表内容/5索引计数、1023保护输入均保持 |
| 预算、取消与副作用 | 通过 | 0托管调用/0USD；无真实评分导出、库重启、生产切换或提交；UUID旋转只在临时库示范并回滚；期限专测未移除 |
| 追溯与版本 | 通过 | 持久UUID与运行指纹分离；旧format/ID/timestamp/payload不变；目标绑定/命令/源码SHA/迁移报告留证 |
| 验证充分性 | 通过 | 定向、真实DB角色/三库保护/地址别名、CLI/迁移与全量已通过；重启/跨日远端与人工证据限制明确 |
| 状态与文档 | 通过 | 六份文档同步，141任务ID/128本地链接完整；docs回归27 passed/2.01s；READY→IN_PROGRESS→REVIEW→DONE，CODE-07仅解工程前置 |

## 4. 边界与下一步

0托管调用/0 USD，没有向真实 Langfuse 发 HTTP；实际采集仅写本地忽略的核验队列。三库31表保护摘要与5索引计数不变，不含动态 outbox 消费状态。未运行真实 PostgreSQL 重启/跨日远端演练，重启不变通过持久字段与不再调用运行指纹的回归验证；跨地址做了实连核验。复用既有丢确认重试相同 payload 的测试，不将其冒称新远端演练。

旧 namespace 的真实来源确认属于部署切换操作，未知来源停止；本轮没有替人工猜绑定。代码尚未重启进驻留服务。回滚保留 UUID 表与队列；降级删除 UUID 的风险见契约。ARCH-10 待共享重排 scorer；CODE-07 的观测职责/MCP受限材料仍未完成；PLAN-02、S2/S3、独立人工、未见盲测及逐轮费用授权约束保持。

最终文档检查：6份文档、128条本地链接、141任务ID，无缺失/重复；docs回归27 passed/2.01秒、退出0。最终记录和台账回填后，仅再核对文件/编号/链接及536输入SHA，没有修改验证后的生产代码。70可选跳过单独复核0.10秒，全部为B/C服务OperationalError。此前246路径中240字节不变、6项明确重叠，无丢失；本轮19文件切片留`.local/arch09-slice-files.json`，原备份保留于`.local/arch09-backup-path`。本轮只有工程DONE；真实模型质量、运行性能和生产部署没有由本轮通过。
