# 记录 182：ARCH-08 共用契约、文本处理和三入口装配

日期：2026-10-11。实现者 / 自审核者：Codex（同一实现者自审，不是第二独立人工）。

任务：ARCH-08；相关 CODE-07 的装配部分仅留证，不把整个 CODE-07 标完成。对应 OPT-01～06。按仓库入口与阶段要求从 READY → IN_PROGRESS → REVIEW 推进，全量门禁、维护输入一致性和八项核对通过后登记 DONE，结果见[机器可读证据](2026-10-11-implementation-182-results.json)。

## 1. 范围与开始条件

开始 HEAD `5a604050b9c0706bfd823685e5befcb9619d64a6`，已有154个 stageable 未提交路径。本轮开始前逐文件备份与 SHA 清单已保存本地 `.local/arch08-backup-path` 所指目录；不提交凭据和临时产物。

ARCH-01/02/03/04/06 正确性和审计工程前置已过，对应171/175/178/179/180；ARCH-07 的执行记录/诊断边界见181。用户“继续”授权推进已登记的无付费工程修复，不授权托管调用、改变目标/门禁、部署或生产自动激活。没有托管模型调用，费用0 USD。本轮八项自审通过，仅工程DONE；真实质量/性能与发布未通过本轮验收。

完成条件：application 不导入 API；生产入库不依赖 evals；三入口共用身份、策略版本、日期、缓存和模型预算/回执的装配规则；自动边界检查。完整设计与迁移表见[生产装配契约](../PRODUCTION_COMPOSITION.md)。

## 2. 实际修改

- 跨入口 Pydantic 命令/结果移至 application.contracts，HTTP Header 留在 API；JWT/目录实现移至 infrastructure.identity，Settings 装配由 bootstrap.identity 负责。HTTP/MCP 模型字段与 Schema 不变。
- PDF 原始解析、PII 和 norm-v1 位于 knowledge；生产入库、检索、评测直接使用同一实现。probe 写页/CLI 保留。所有仓库 Python 调用方迁入规范模块，无 `X as X` 转发壳。
- ProductionRuntime 移至 bootstrap；共用 PolicyRouter、版本计算、RetrievalServices 和执行配置绑定。worker 不再导入 API runtime；MCP 删除整套重复策略/缓存/翻译组装，使用 SearchRuntime。
- 共用连接配置保留应用/管理/受限/只读角色的区分；检索绑定事务不能由不同身份复用。MCP 搜索 Trace 保留实际完整 VersionSet，失败仍有本次计量。
- 资源包装器/术语和懒模型网关有锁；初始化、MCP runtime/server 构造或关闭异常仍释放已拥有推理资源。检索装配和返回后显式检查墙钟期限。
- 增加 `make architecture-check` 并纳入 `make check`；局部、TYPE_CHECKING、相对和常见动态导入受约束；两条有理由的精确允许边仅供观测 worker 显式导入冻结评测评分。
- 历史本地代码链接仅迁移目标路径；原文与历史执行结论保留。当前技术入口/待办和下一项另行同步。

## 3. 发现的问题、修复与复测

| 检查 | 实际失败 | 修复和结果 |
| --- | --- | --- |
| 首轮 mypy | 3处：两处路由仍导入已搬走的 Header；ModelGateway 无 close 属性 | Header改指HTTP模块，关闭采用现有可选close契约；214个src文件类型检查通过 |
| 首轮回归收集 | 9处 ImportError，都由残留 Header 导入造成 | 修复路由后可收集；没有改错误响应或任务幂等规则 |
| 解析回归 | 3个 AttributeError：测试局部pdf路径遮蔽迁入模块 | 测试用pdf_text别名；后续复测通过，不改抽取输出 |
| 单次定向测试命令 | 未移除宿主DEBUG，Settings布尔解析失败2题 | 遵循既有env -u DEBUG；不是修改配置校验，失败日志保留 |
| 新截止时间反例 | 装配超时后没有抛出DeadlineExceeded | Token/费用检查不检查墙钟；装配前后和返回后显式check_deadline，复测通过且没有网关调用 |
| 静态边界 | worker观测CLI的冻结成绩导入触发两条边 | 精确允许模块及符号两条，理由和失效检查登记；实时装配无此依赖 |
| 过宽Ruff命令 | 对历史draft工具检查产生旧E702/E741等错误，并修了部分无关格式 | 还原evals历史文件后仅应用必要导入路径迁移；后续使用Makefile维护范围，冻结/历史结果不改 |
| 导入迁移/格式检查 | 一处测试的新pdf_text引用漏加import | 补规范import后lint通过；没有隐藏或跳过失败用例 |

本地保留失败日志：`arch08-mypy.log`、`arch08-targeted.log`、`arch08-targeted-fixed.log`、`arch08-extraction-fixed.log`、`arch08-composition.log`、`arch08-lint.log`。按当前代码重跑后以最终门禁为准。

## 4. 最终验证证据

- 扩展定向回归：364 passed，1个已有JWT负例警告，10.42秒。
- 数据库定向：入库/MCP可见性/Task原子审计/主体/灰度路由五个文件，30 passed，5.38秒。
- 初始化/关闭/连接/装配/导入失败路径定向：34 passed，1.61秒；后续动态导入新增反例纳入最终门禁。
- 迁移前后59个共用定义AST一致；12组基础/检索/翻译/来源/作答路由/提示策略×灰度版本计算结果相同，0调用。结果在`.local/arch08-equivalence.json`。
- `mypy`：214个src文件通过；Schema导出`--check`：schemas up to date。
- 四个保留CLI的`--help`退出0；bootstrap runtime/search导入后`medops.api`模块列表为空；静态214模块、0违例、2精确允许边。
- 最终`env -u DEBUG PYTHONPATH=<snapshot>/src:<snapshot> make check`退出0：2071 passed、70 skipped、1 warning，60.15秒；lint、499维护文件格式、214源文件mypy、导入边界、4集评测审计和Schema全部通过。验证快照位于`.local/arch08-worktree-path`所指仓库外工作树。
- 532维护输入SHA完全一致，无missing/mismatch；忽略的env仅比较字节相等，不输出内容/摘要。开始前154路径中120保持字节，34按本轮迁移/最终文档修改，无丢失。
- 1023个已有evals/Schema的JSON/JSONL与开始状态逐字节一致；冻结样本/gold、历史结果、阈值、默认模型和发布指针未改。
- 10个更新Markdown、315条本地链接均存在；141任务ID无缺失/重复。最终结果JSON加入后再次核对。
- 70跳过为可选B/zhparser 45项、C/pg_search 25项不可达（OperationalError）。当前PG/Redis/D测试运行；JWT warning为既有故意短密钥反例。评测仍提示2个unmappable miss、旧安全回放、独立人工未完和无未见盲测，不消除这些缺口。
- 四CLI帮助退出0没有启动服务。定向连接/关闭/身份/历史/期限反例、实际数据库角色与审计检查均使用本地离线网关，无托管费用。

## 5. 八项强制自审核：通过

| 项目 | 当前状态 | 依据 |
| --- | --- | --- |
| 需求与范围 | 通过 | 对应ARCH-08四项；正文保存/Agent/真实质量不计入本轮完成 |
| ADR与阶段硬门 | 通过 | 沿用ADR-0012，未改变目标/阈值；无S2/S3实现或自动激活 |
| 正确性与失败路径 | 通过 | 迁移等价和正常/身份不符/历史/异常/资源/期限反例已测，全量通过 |
| 权限与数据 | 通过 | 数据库角色、RLS、受限正文边界保留；冻结与旧工作1023输入字节核对通过 |
| 预算、取消与副作用 | 通过 | 0托管调用；网关执行预算强制、失败计量和截止时间已测 |
| 追溯与版本 | 通过 | 同一RequestPolicies/绑定规则；12组迁移比较、MCP实际VersionSet；原条件回放仍拒绝 |
| 验证充分性 | 通过 | 定向/数据库/Schema/AST检查已有证据；最终全量通过 |
| 状态与文档 | 通过 | READY→IN_PROGRESS→REVIEW→DONE；链接/状态/编号/依赖核对通过 |

## 6. 限制、回滚与下一项

不宣称整个仓库已满足严格洋葱架构。应用仍保留必要的Harness/预算/适配器依赖；CODE-04/05/06继续负责实验模块、评测工具与测试夹具。单进程共用装配不意味着跨进程强一致缓存；发布TTL规则保持。ARCH-10底层scorer共享验收未完成。

MCP受限完整输入/逐模型正文持久化、Task/MCP回放和原条件恢复未交付，继续CODE-07及回放契约；只读角色不能因此获得事实写权限。新内部Python导入路径需外部脚本自行按迁移表更新，四CLI与对外Schema保留。

回滚按本轮开始快照恢复迁移文件和调用方、删除本轮新增文件；不覆盖其余已有改动。无数据库迁移、发布指针/默认模型/gold/阈值变更，无提交/推送/重启。下一主项为ARCH-09稳定反馈来源和score ID；付费实验仍逐次授权。本轮开始至初次最终记录约23.3分钟（含实现、自审、工具等待与返修，不等同纯编码工时）；完整门禁的pytest为60.15秒。未以工程通过重估Agent/自进化真实运行工期。最终文档回填到同一验证快照后，docs回归27 passed/1.18秒、退出0；随后仅回填该结果，不改生产代码。
