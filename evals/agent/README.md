# Agent 评测准备

当前只有 S0 的开发设计输入，尚无已运行的多步 Agent benchmark。

2026-10-10 所有者已确认 PV 资料整理与指定指南核对的业务范围；具体动作/预算/验收仍需定稿，场景确认不授权模型费用。

- 场景、能力矩阵、参考实现及行动契约草案：[PLAN-01](../../docs/agent/PLAN-01-capability-and-scenario.md)。
- [development/S0-pv-case-spec-v1.json](development/S0-pv-case-spec-v1.json)：12 个合成工程用例规格，已有暴露，`unseen_holdout=false`；没有真实模型判词或成功率。
- 这里的合成文档是测试夹具，不属于生产事实库、医学标准答案或已获准官方资料。后续假网关/假事实库验证读取该规格；真实场景必须重新绑定获准原文和版本。
- EVAL-32 的任务 rubric、时限和阈值尚未冻结；动态 Agent 实现/集成先满足 PLAN-02、ARCH-04/11 及对应正确性依赖。
- 未见盲测的来源、保管、家族隔离和题量见[独立盲测准备](../holdout/README.md)，不能把这些开发用例移入盲测凑数。
- 正式 Workflow/Agent 对照归 EVAL-34；Prompt/Skill 改进声明归 EVAL-36，真实调用每轮另行批准。
