# 记录213：AGENT-04 实际草稿引用核验的封闭预算

日期：2026-10-16。实现及真实审核者：Codex自审核，不是第二独立人工。已完成REVIEW及八项工程自审：本切片DONE，整项AGENT-04继续IN_PROGRESS。

## 0. 任务、前置与范围

依据CURRENT_TASKS、PLAN-02及210～212，补实际草稿引用核验请求的预算profile与可信消费。ARCH-04/11/原工具/模型循环/重复检查/共享保护/整项估计前置已过。原七动作/8步/12,000 Token/0.60 USD/125秒和逐轮付费授权保持。

root起始HEAD 06aead54ba87785dbe129cfa40e6e2846fef15df、工作区/索引干净；770维护输入在仓库外等价树核对一致后实施，审核后按路径同步，保留其他工作。不触碰冻结数据/gold/阈值、默认模型/价格、安全ACL、已发布策略、迁移或业务部署；0托管调用/0USD。

本轮具体范围是已知实际草稿的引用核验profile与封闭消费，不为未实现的完整最终门杜撰启动预留。完整初始profile与AGENT-05真实终检形状共同收敛；下一先继续持久取消/租约/原额度恢复，整项保持IN_PROGRESS。没有把预算入口当完整Agent或业务完成门。

## 1. 为什么需要与如何实现

记录211保护普通调用不能花最终空间；212增加工具整体预检，但没有安全的消费入口。这是台账已登记的能力缺口，不把旧版正确拒绝消费保护伪装为生产缺陷。

现在仅可信终态方可调用verify_final_citations，验证已计步finish/完整绑定及原根额度/期限、当前来源/事实和输入安全。复用实际plan_verify和原Registry的最多3次attempt，推导包含真实提示/原文/Schema/600输出及实际网关报价的FinalizationProfile。必须装进已安装保护；不足在供应商前拒绝，不自动扩大。

finalization_scope只准入绑定请求与次数，把相应保护在同锁内转到原在途reserve，原Meter/月账本和真实/未知费用结算不变。成功/失败/取消退出都封闭新模型调用；请求/价格/事实漂移、外来线程、超额调用或晚到结果均不能借此释放普通额度。完整计划报价是额外的阶段约束，真实超量仍保留并停止。

结果仅是带draft/binding/profile/原预算快照/回执的引用检查，不含completed状态。无指南claims时payload=None，零模型请求仍核对事实栅栏；可信调用方后续须完成业务/完整性/安全和原子保存。真实持久Driver、取消/租约及阶段恢复尚未实现。

## 2. 失败、困难与修复

1. 首轮182项原路径回归通过；新增首轮36 passed/2 failed。一个真实新代码缺陷：空claim分支试建VerificationPayload(checks=())，违反原至少1项Schema，原文`Tuple should have at least 1 item after validation, not 0`。改为私有结果payload=None及显式no_guideline_claims，不放宽原Schema/判定门。
2. 另一个失败来自测试假设final:action_id位于attempt_id结尾；实际原Registry追加`/skill_input_hash:attempt`。改为检查完整分段归属，保留原复合追溯；没有改生产attempt语义。
3. 新测试初版ruff报告42项（3可自动修、39格式问题），先格式化再检查，未关规则。mypy首次及修复后均通过，原边界规则保留。
4. 自审专门验证报价后价格或事实变化：原请求内容/额度不再匹配时在供应商前拒绝。不能仅比较Token总数而允许换prompt/证据，也不能在期望失败后删除已有真实/未知费用。
5. 关闭后迟到调用的真实响应仍先结算再拒绝输出；普通外来线程的拒绝不毒化合法最终通道。同线程重开scope不发新额度，原root绝对期限/持有权guard保持。

6. 版本比对助手初次沿用212“预算版本保持”断言，退出1；本轮实际有意升级预算v3，改为分别核对已登记的旧v2/新v3和工具v3/v4，再运行通过，不把旧断言当产品兼容缺陷。

7. 首轮全仓3019通过后继续复审，新增伪造回执反例真实复现：同call_id、异run_id仍被新入口接受，pytest原文`DID NOT RAISE AgentToolFault`，1 failed。本切片退回REVIEW，新增与实际call_journal请求归属的完整对照，仅忽略原月账本新增reservation_id，再核对本run/trace/final动作/verify模型。反例复测1 passed；正规原月账本路径离线烟测1逻辑准入/1月回执通过，保留原回执而不篡改错误归属。产品代码改变后重新运行required全量，不沿用3019结果。

6. 版本比对助手初次沿用212“预算版本保持”断言，退出1；本轮实际有意升级预算v3，改为分别核对已登记的旧v2/新v3和工具v3/v4，再运行通过，不把旧断言当产品兼容缺陷。

## 3. 版本、权限与追溯

预算升级execution-budget-v3+sealed-finalization，工具pv-tools-v4+final-citation-budget；实际新旧SHA见本轮机器回执及下节。新profile绑定请求/报价/原限额，原AgentProfile/默认模型/价格、临床规则/提示、原Registry和36公开Schema保持。新终态入口未加入TOOL_ACTIONS、七动作或公共API/MCP。

受限ExecutionAudit保存动作/原计划/profile/原引用Skill审计；回执保留原run/attempt/final:action_id/Skill attempt。正文不进入普通遥测。profile/摘要不认证身份或替代当前事实/ACL/租约；最终事实栅栏须由调用方在同事务内保存并commit。没有新生产默认Driver。

## 4. 验证

| 核验 | 结果 |
| --- | --- |
| 原路径定向pytest | 182 passed；含原Agent/预算及临时PG |
| 新机制/临时PG组合 | 62 passed；另加报价后事实漂移1 passed，共45新增用例 |
| required `make check` | 退出0；3020 passed、70 skipped、1原JWT短key测试warning；95.58秒 |
| lint/format/mypy/架构/断言 | 全过；363模块0架构违例/2原允许边，未关闭规则 |
| 评测审计/公开Schema | 4套审计通过，36Schema字节保持；unmappable/旧安全回放/独立复核/无新盲测四条原warning保留 |
| 维护输入/范围 | 770原输入中766保持、4预期修改，新增3，共773；16预期路径/144原ID、332链接/9锚点通过 |
| 最终文档 | 41 passed；退出0，4.283秒 |

仓库外等价树/原锁定环境运行，DEBUG继承值按原约定解除；PG/Redis required，70 skip仅原可选B/C实验。新PG用例对新增入口执行真实RLS和最终锁竞争；没有修改正式业务库或调用托管模型。fake超时的保守费用用于机制断言，不是实际模型账单。

全部原AgentTools方法、临床Verifier/Registry/adapter/提示字节保持；原预算顶层函数除向reserve/fits传真实request外AST保持，原estimate/receipt公式和去除新phase检查后的正常settle AST相同。新root阶段语义明确版本化，不假称根预算类整体字节相同。输入摘要、失败/命令日志、兼容对照、版本/同步及发布收据留`.local/audit213/`，不提交凭据/本地临时产物。

## 5. 八项强制自审


| 项目 | 判定 | 证据及限制 |
| --- | --- | --- |
| 需求与范围 | 通过 | 完成已知实际草稿的引用预算profile/封闭消费，原七动作/8步和总cap不变；完整初始profile/业务门及持久恢复明确待办 |
| ADR与阶段硬门 | 通过 | 按PLAN-02获准最终预留原则实施，ARCH-04/11及既有工具/循环前置保持；不新增生产默认数值/验收门/自动生产批准 |
| 正确性与失败路径 | 通过 | 45新用例覆盖精确请求/次数、免费路径、额度不足、费用漂移、取消/晚到/外来线程及真实PG撤权/栅栏；空payload缺陷先失败后修，不放宽Schema |
| 权限与数据 | 通过 | 原AgentTools方法全部AST相同，原Registry/adapter/临床Verifier/模型提示字节保持；新入口重验finish/context/当前事实安全并保留最后栅栏，不暴露给模型或公共API |
| 预算/取消/副作用 | 通过 | 保护原子转成原调用预留，原Meter/月账本计费与已知/未知费用保留；只用根额度/期限，退出永久封闭，0托管调用/0USD；持久取消/租约未完成 |
| 追溯与版本 | 通过 | 真实请求/报价/根限额产生profile SHA，受限动作/计划/结果和原复合attempt回执保留；根预算v3/工具v4实际加载，新旧工具SHA留证，未实现持久阶段恢复 |
| 验证充分性 | 通过 | required全量3020/70/1、182原路径、62机制与临时PG加1漂移反例通过；原调用公式/回执和正常settle对照保持，36公开Schema/冻结数据不变；不代替真实质量 |
| 状态与文档 | 通过 | 16路径/145原ID、332链接/9锚点核对；本切片DONE而04整体IN_PROGRESS，05/06 READY、07 BLOCKED及其余门原状态保持；下一持久取消/租约/原额度恢复 |

## 6. 限制、回滚与下一步

该profile针对已经存在的草稿引用核验，不保证初始规划/8步/未知最终草稿能放入原总额度；不使用合成fixture数字当生产默认。完整最终门/原子终态、生产Driver、持久取消/租约/原额度与阶段恢复、最小SESSION及真实质量/盲测仍待。共享锁只覆盖进程内，不能宣称跨进程恢复或外部恰好一次。

回滚按共享预算阶段/可信入口/版本与测试文档边界撤回，无迁移或新权限。旧版本context不混用新行为。完成审核后细分提交并按最终SHA核验远端CI，排除output/pdf及本地私有材料。投入/等待/返修未分项计时，命令时间据机器回执；剩余恢复工期仍需持久设计后重估。无新增必须人工裁决项；付费试跑继续单独授权。

## 7. 实际版本证据

旧工具SHA `0e242630399ae3d9424a9b1cddd0d4f1ae481d480c27b0cc64ff2e1150c13a87`；新SHA `cf4875c058258d4f482569af5b94d6a81aa097e0cab1c62052f28c73fec4a941`。原预算版本`execution-budget-v2+utf8-preflight+protected-headroom`，本轮`execution-budget-v3+sealed-finalization`；新工具版本`pv-tools-v4+final-citation-budget`。新规则是真实运行代码，不是空标签；无部署/生产策略切换，提交后远端CI按本轮最终SHA另核验。
