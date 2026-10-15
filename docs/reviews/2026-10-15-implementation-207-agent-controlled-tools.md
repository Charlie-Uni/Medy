# 记录207：AGENT-02受控工具适配

- 日期：2026-10-15；实现/自审核：Codex，不是第二独立人工。
- 主切片：AGENT-02；前置AGENT-01记录206和ARCH-02已通过，ARCH-04/11入口保持；不运行托管模型。
- 基线e86f8a5；根工作区及暂存区开始无改动。在仓库外同字节工作树实现，738维护输入先核对，无差异；不覆盖其他工作。
- 状态READY→IN_PROGRESS→REVIEW，最终门禁/八项自审通过才DONE。机器证据：[207-results.json](2026-10-15-implementation-207-results.json)；私有.local/audit207保留实际命令、错误、测试、源码摘要和发布收据，不入Git。

## 1. 改了什么

[工具说明](../agent/AGENT_TOOLS.md)详述四类工具和边界：实际复用检索链及ae_extraction/citation_verification Registry；固定任务来源传入原/翻译/聚焦检索并进入缓存上下文，原无scope缓存键保持；RLS重新读原文/邻块、当前身份、日期窗口、版本/PDF摘要、解析/来源/内容完整性。AE只给逐字唯一原文位置，不猜重复/归一化quote区间；read超8,000字符明确unsupported，搜索摘录最多500字符/8份并标truncated。

新增私有AgentToolOutcome和Schema，只返回有界payload、真实句柄/回执；不会构造未保存的result_ref或AgentObservation。完整受限输入、Skill核验、证据和attempt保留在每动作独立ExecutionAudit及共用MeteredGateway，后续AGENT-06持久化；Langfuse正文边界不变。

调用前须已有共享根额度/截止，且run快照和实际计量一致；子工具不新发额度，所有原SDK/Registry重试继承根持有权guard、身份复查和action标记。失败、超时、预算、未知usage分别保留；终态申请不当工具执行。最后通过0026身份/事实栅栏，调用者保存/提交后才能再规划。

## 2. 自审发现、错误和修复

1. 初次静态检查发现DeadlineConnection与旧具体Connection注解不兼容；保留现有数据库适配边界的Any类型，未加ignore。拆Skill桥接时还发现AgentContext被SkillContext局部变量覆盖，以及一次自动改写把错误处理helper嵌套，均恢复并用失败路径验证。
2. 首轮PG集成14 failed/3 passed：0025持久UUID只给admin/loop SELECT，readonly还不能读principal目录。未加GRANT或RLS例外；改为可信启动连接建立UUID/实际连接指纹绑定，工具在原应用角色核验绑定和实时身份；修复后17 passed。管理员连接/DSN不进入工具。另有真实反例证明app仍无fact_plane_identity SELECT。
3. 增加受限审计时32 failed/23 passed：适配器提前bind，Registry再次bind被原机制拒绝。改为每动作独立journal，由Registry为其Skill绑定一次；search/read自行绑定。剩余两个失败分别是timeout误归dependency_error、测试误读event字段；按原attempt error_code分类、使用真实kind/spans字段修复，保留失败回执。
4. 首次make check为2733 passed/70 skipped/1旧warning及1 failed：原test_no_bypass拒绝包外直接导入具体Skill的五条边。将AE词汇归领域层、实际Skill桥接留Skills包内，通过Registry.agent_adapter公开入口使用；原PUBLIC名单、断言和架构规则不修改，没有放宽门禁。
5. 中间一次全量停在格式门，skills/agent_adapter.py一条长条件需重排；对16个本轮Python路径format后稳定，最终再跑全量。所有初次失败和跳过保留于私有收据，不以中间通过代替最终快照。

原节点/Skill Prompt、输入输出Schema、风险/scopes/原时限/重试上限及handler逻辑另做前后比较；这不是生成新Prompt或更换默认模型。20条/每条1,000字符的引用工具原上限保持，超出明确unsupported，不截断或静默增加子调用。

## 3. 验证

最终定向199 passed（pytest9.80秒，总11.665秒），包括新工具、共享缓存/翻译、原AGENT-01、原装配及禁止绕过。真实临时PG：角色/身份/数据库绑定、指定来源/版本、历史窗口、相邻块、权限撤销、篡改、最终输出锁和Factory接线；模型调用期间停用用户，最终不返回payload但保留用量/回执。

首轮39定向、17 PG修复后、63工具/缓存/PG、189和193扩展均留收据；最终199覆盖本轮全部新增反例与原入口。PG17/pg_textsearch1.5.1只读预检通过；required-services开启，D实验绑定同原生服务的独立临时库/角色；不写.env或业务数据库。最终`env -u DEBUG venv/bin/python .local/audit207/run.py gate`退出0，总148.174秒：2738 passed、70 skipped、1旧JWT短密钥负例警告（pytest138.89秒）。749文件格式、350源码mypy、350模块架构0违规/原2例外、293测试文件静态断言0违规、四冻结集审计和Schema drift全过；原70项可选B/C服务跳过保留，必需PG/Redis/容器及D实验实际运行。评测审计的2个unmappable miss、历史安全集、第二人工和未见盲测缺口继续报告，不改分母。

审前范围核对退出0：26路径、144任务原ID/顺序不变，310链接/7锚点；738维护输入中732保持、6处为本轮接线/类型词汇/回归，新增10个Python输入共748。35旧Schema原字节不变；AE的SPEC/输入输出模型Schema/原生生成Schema/SYSTEM/KINDS/因果正则在两个隔离Python导入中逐项相同，handler AST与Registry原方法AST相同，仅新增公开适配工厂。原Skill禁止绕过测试、架构规则、AGENT-01模型/原Ask状态、S0/v1/v2/PLAN/ADR/AGENTS/旧生产gate保持。文档回归41 passed、无skip，退出0；最终状态/路径/保护材料审计另附机器收据。

## 4. 八项强制自审核

| 项目 | 结论 | 证据及范围 |
| --- | --- | --- |
| 需求与范围 | 通过 | 四类实际工具适配与装配；不把工具当规划循环或完整Agent |
| ADR与阶段 | 通过 | PLAN-02/ARCH-04/11已过，批准profile、实验限定和盲测/生产规则保持 |
| 正确性/失败路径 | 通过 | 199定向、2738全量；来源/历史/邻块/撤权/损坏/注入/timeout/预算反例；中间失败修复复测 |
| 权限与数据 | 通过 | 原RLS应用角色、当前身份、数据库可信绑定及最后栅栏；不新增Grant或绕过白名单 |
| 预算/取消/副作用 | 通过 | 根共享额度/截止/继承持有权guard、动作回执；0托管/0USD；完整取消/恢复仍待AGENT-04 |
| 追溯与版本 | 通过 | 固定来源/原expiry、实际版本、受限journal与逐调用记录；不伪造持久观察/回执 |
| 验证充分性 | 通过 | required全量、真实PG19新集成反例、原契约/handler/Registry AST、35旧Schema、41文档及范围核对 |
| 状态与文档 | 通过 | AGENT-02限适配器DONE，EVAL-32下一、AGENT-03 READY；质量/隔离/独立人工/发布缺口保持 |

结论为本轮工程自审通过，不是独立人工或真实模型质量验收。

## 5. 限制、发布与下一项

这是受控工具工程，不是完整Agent或真实质量通过。规划模型/行动循环、持久步数/重复检测/取消/租约/恢复、最终业务完成门、持久观察/回放和最小澄清续办仍待后续。Caller必须在栅栏下持久化并提交，不能持锁进入下一模型调用；未提供公共HTTP/MCP Agent接口，也未重启服务。

工具载荷上限不是Token足够保证，原8步/12,000 Token/0.60USD/125秒和最终预留原则不变；没有付费授权。所有模型测试为fake、0托管调用/0USD。所有者表示有另一台电脑和云主机，规格/管理归属/实际隔离尚未核验；没有访问真盲测或部署。

审核通过后AGENT-02 DONE、AGENT-03 READY；按既定顺序下一EVAL-32评分再AGENT-03循环。原任务ID/分母/冻结集/阈值/默认模型/ACL/生产策略和原Skill门保持。回滚新适配器/私有Schema/显式scope字段及AE词汇抽取即可，无迁移或服务回滚。按功能边界细分提交，根目录/审核快照/提交树核对一致再推送并检查实际SHA的CI；继续排除output/pdf和本地产物。
