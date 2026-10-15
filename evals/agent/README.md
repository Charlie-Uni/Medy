# Agent 开发评测

EVAL-32已实现开发评分器与公开脚本，自审见[记录208](../../docs/reviews/2026-10-15-implementation-208-agent-rubric-and-development-cases.md)。详细口径和命令见[评分契约](../../docs/agent/AGENT_EVALUATION.md)。当前仍没有已运行的真实多步Agent benchmark。

- [PV-rubric-scripted-v1.json](development/PV-rubric-scripted-v1.json)：12原场景及必要变体，15个合成case/27登记执行（含同case12续办/恢复拒绝变体）；全部为scripted_fixture，不是实际Agent输出、医学gold或未见任务。
- [S0-pv-case-spec-v1.json](development/S0-pv-case-spec-v1.json)、[PLAN-02契约v1](development/PLAN-02-contract-v1.json)、[PLAN-02契约v2](development/PLAN-02-contract-v2.json)保留历史字节与当时状态；新版本通过SHA关联，不反写历史为已实现。
- 评分器分别报告业务完成、处理正确、工具适当性、实际结果驱动调整、叙述忠实、claim/引用语义、来源合规、AND/OR必需证据、停止和保护、效率；unknown/失败/取消/缺记录保留分母。
- 合成文档不属于生产事实库或获准官方医学资料，不得移入盲测凑数。所有脚本计量值均为合成，实际0托管调用/0USD。
- 业务与阶段见[PLAN-01](../../docs/agent/PLAN-01-capability-and-scenario.md)、[PLAN-02](../../docs/agent/PLAN-02-action-budget-and-acceptance.md)；真实保管/暴露账本归[EVAL-33](../holdout/README.md)，正式对照归EVAL-34，改进证据归EVAL-36；每次付费另行授权。
