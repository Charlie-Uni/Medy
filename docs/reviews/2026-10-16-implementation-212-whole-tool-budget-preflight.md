# 记录212：AGENT-04 工具整项模型预算预检

日期：2026-10-16。真实审核者：Codex自审核；不是第二独立人工。已完成REVIEW及八项工程自审：本切片DONE，AGENT-04整项仍IN_PROGRESS。

## 0. 目标、前置与范围

- 依据CURRENT_TASKS、PLAN-02和记录210/211，接着做工具整体估计；原七动作、8步、12,000 Token、0.60 USD、125秒及最终保护不变。
- 不调用托管模型，不迁移/修改业务库、不部署、不接触盲测，不调整冻结输入/gold/评分门/ACL/默认模型/价格/已发布策略。
- 首先核对root HEAD 1e12b24a72bee4cdb745a30c858a1cf86bc16c7a、空工作区/索引；767维护输入逐字节匹配后在仓库外等价树实施，再按审核后的路径同步，保护并行工作。
- 本轮范围收敛为四类工具的实际请求估计与执行前准入；实际初始最终核验profile、可信最终阶段消费和持久恢复继续待办，不为赶进度引入任意解除保护接口。

## 1. 真实复现与改动

在未修改产品代码的原版本上执行新反例：总额度容得下一次但容不下原Skill的三次attempt加最终保护。原实现先发生一次AE超时调用，下一次才拒绝。pytest原文：`AssertionError: assert ('budget_exceeded' == 'budget_exceeded' ... and not [ModelRequest(...purpose='skill:ae_extraction'...)])`，1 failed。PUBLIC fake供应商只复现机制，不产生真实费用。新行为是在首次逻辑模型调用前拒绝；该反例修改的断言和原失败日志均保留在本地审核材料。

实现ModelCallPlan与无call_id的CallEstimate；复用原request_tokens与实际价目表计算，乘原Registry retry上界，不增加重试。AE/structured与QueryTranslator共用实际request builder；引用预览沿用原polarity_only核验代码、在第一次模型请求前专用异常退出，免模型分支不虚构judge。读取零模型调用；搜索按照cache miss保守计算，生产装配绑定同一个翻译对象的执行/预览。

AgentTools在原授权/安全检查后、原工具前记录受限计划并检查根预算：accounted+active+protected+plan <= 原上限，Token与费用两维。原实际调用的reserve/settle、未知费用/取消/超量回执、Registry与最终事实栅栏继续有效。整项拒绝没有模型调用，所以没有模型回执和费用；这与原物理调用拒绝的零费用denied回执明确区分。

## 2. 可追溯与兼容

工具版本升级pv-tools-v3+whole-tool-preflight，契约摘要绑定实际model-call-plan-v1+original-retry-bound版本；旧context在首次规划/工具前拒绝。预算组件公式、原默认模型/价格、SYSTEM、严格Schema、输出上限、Skill spec/handler身份和36公开Schema保持。请求构造抽取是实际使用的共用函数；没有手写第二套提示词或临床判断。

计划在既有受限ExecutionAudit记录实际请求/上界/估计和plan_sha256；不进入普通遥测、模型可见工具结果或费用账本。现有实际CallAllowance、原调用计量/持久账本、原生产输出/授权栅栏不变。旧Ask的RetrievalPort不强制新增方法；仅Agent要求可审核的模型请求预览，缺失则检索前失败关闭。

## 3. 失败、困难与修复

1. 新反例真实复现原预算缺口后才修改产品代码，没有把改后测试当旧缺陷证据。
2. 首次mypy报告agent_adapter.requests需要list[ModelRequest]标注；已补并复测。ruff发现5处导入/格式问题，自动修正后复测，未关规则。
3. 自审发现费用估计若读模块默认PRICES会与装有专用execution_prices的实际网关不一致；改从当前MeteredGateway取表，并用100倍费率反例证明在工具前拒绝。
4. 引用核验不能简单按全部claims一律假设付费，也不能为估计复制医学规则。现有核验预览在真实请求位置退出，保留包含/极性/无judge路径；策略变化明确拒绝，避免rules_first多调用时少算。
5. 保守上界按三次attempt整包估计，可能拒绝实际只需首试的任务；属于明确工程边界，不能据此声称完成率提升。引用资料/并发变化仍由逐调用保护和最终事实检查兜底。

## 4. 验证

| 核验 | 结果 |
| --- | --- |
| 原版本新反例 | 1 failed；预期在调用前拒绝，实际先发生一次fake AE调用 |
| 关键路径定向pytest | 166 passed；含真实临时PG事实/授权回归 |
| 新增与更新用例 | 32 passed；24新增、8既有预算测试按新准入行为核对 |
| required `make check` | 退出0；2975 passed、70 skipped、1既有JWT短key测试warning；103.542秒 |
| lint/format/mypy/架构/断言 | 通过，362模块0架构违例/2原精确允许边；未关闭规则 |
| 评测审计/Schema | 4套审计通过，36Schema原样保持；2 unmappable/旧安全回放/独立复核缺失/未见题缺失四条原warning保留 |
| 维护输入/范围 | 767原维护输入中755不变、12预期修改，新增3，共770；23预期路径、144原ID、327链接/9锚点通过 |
| 文档最终核验 | 41 passed；退出0，2.231秒 |

在仓库外等价工作树、原锁定环境运行，DEBUG继承值按既有测试约定解除；PG/Redis required，70 skip仅原可选B/C实验。没有用skip掩盖必需服务缺失。私有命令日志、源码摘要/版本对照/根同步及发布收据留`.local/audit212/`，不提交凭据或本地临时材料。

原调用公式、reserve/settle/计量路径AST保持；structured/translation的ModelRequest字段表达式、AE原user字符串和所有原临床核验函数/常量AST相同；原引用事实解析与Registry/coverage后半段相同。工程保守上界不是供应商精确Token或医学语义证据。

## 5. 八项强制自审


| 项目 | 判定 | 证据及限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 按已批准预算原则补四类工具整项预检；只完成该切片，实际最终profile/消费/持久恢复仍待 |
| ADR与阶段硬门 | 通过 | 原七动作/8步/12000 Token/0.60 USD/125秒及ARCH-04/11保持；不增加生产默认profile或放宽验收 |
| 正确性与失败路径 | 通过 | 原三attempt容不下却先调用AE的反例真实复现；24新增/8更新与166定向通过；缺失预览、未知策略、多claim、免模型判断与价格差异验证 |
| 权限与数据 | 通过 | 原事实解析段与Registry执行/coverage、临床核验AST保持；前后当前授权/安全/最终栅栏不变，临时PG集成通过，36Schema/冻结输入不变 |
| 预算/取消/副作用 | 通过 | 0托管/0USD；按原最大retry及当前网关价格做只读fit；不造usage/回执/占额，不释放最终保护，保留逐调用硬限制/未知费用/截止处理 |
| 追溯与版本 | 通过 | 受限计划记录请求/attempt上界/估计/hash，不进入普通遥测或工具结果；工具v3和新旧SHA留证，旧context失败关闭，原预算公式/版本保持 |
| 验证充分性 | 通过 | required make check 2975/70/1；32聚焦和166定向、AST/维护输入与文档核对；新测试为公开合成，不替代真实质量/盲测 |
| 状态与文档 | 通过 | 23路径/144原任务ID、327链接/9锚点；AGENT-04本切片完成、整体IN_PROGRESS，05/06 READY、07 BLOCKED、EVAL-33和GATE-01原状态保持 |

## 6. 限制、回滚与下一步

只是工具开始前的只读fit检查，不是整项原子占额或成功保证。UTF-8估计不是供应商精确Token，真实usage/未知费用继续原样保留；原root cap、绝对期限、8步和最终保护没有扩大。自定义检索适配器须可信声明全部调用，不声称能推断不合作插件。

plan_verify只对已给定的claims/句柄估计实际引用判断；未推导未知最终草稿的完整初始profile，未实现最终保护消费、最终业务门/生产Driver/持久取消租约与恢复/SESSION。测试全部PUBLIC合成，不代表真实医学质量、安全盲测或独立人工。下一先完成实际最终核验profile与可信消费，再持久取消/租约/原额度恢复；整项AGENT-04继续IN_PROGRESS。

回滚按请求构造/估计接线/工具版本与相应测试文档撤回，无数据库迁移。旧工具摘要不与新行为混用。提交按功能边界细分，明确路径，排除output/pdf与本地凭据/材料；远端CI按本轮最终SHA核验，不能用旧CI替代。

## 7. 版本证据与发布边界

旧工具SHA `83d106b2a9ec5671f429b304196ed32521036154a4cc2712cea813c24c1d0943`；新SHA `0e242630399ae3d9424a9b1cddd0d4f1ae481d480c27b0cc64ff2e1150c13a87`。实际预算组件版本保持`execution-budget-v2+utf8-preflight+protected-headroom`，新call-plan版本进入工具摘要。提交/推送仍按本轮独立SHA核验CI，记录211的旧CI不代替本轮；未部署业务服务。
