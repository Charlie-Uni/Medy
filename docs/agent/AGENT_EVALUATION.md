# PV Agent 评分契约 v1（EVAL-32）

2026-10-15；依据已获所有者确认的[PLAN-02 §6](PLAN-02-action-budget-and-acceptance.md)和[ADR-0012](../adr/ADR-0012-agent-evolution-goals-and-acceptance.md)。这是开发评分器及公开脚本，工程自审见[记录208](../reviews/2026-10-15-implementation-208-agent-rubric-and-development-cases.md)。不增加验收阈值，不重判历史成绩。

## 1. 当前交付与使用

实现位于 `medops.evals.agent`，生产、规划器和受控工具不得导入它。`contracts.py`定义版本化登记清单/轨迹/评价记录；`scoring.py`纯计算；`reporting.py`按完整清单汇总；`development.py`只读公开脚本，不接数据库、网关、模型凭据或网络。原12场景设计及两版PLAN-02 JSON保持原字节/当时状态，不把历史设计改成已运行。

```sh
PYTHONPATH=src env -u DEBUG venv/bin/python -m medops.evals.agent.development \
  evals/agent/development/PV-rubric-scripted-v1.json
```

[新脚本](../../evals/agent/development/PV-rubric-scripted-v1.json)把12场景展开为15个独立合成case，再给同一个澄清case登记12项续办/恢复拒绝变体，共27条执行记录。PV-S0-10两变体、PV-S0-11三变体；保留原输入中的注入文本、附件大小问题、隐藏来源、历史日期/版本及来源歧义。四条预设完成记录只是计分器正例，其他23条只是正确停止/拒绝的脚本。**27/27匹配预设不是真实Agent成功率；尚无Agent控制器执行这些任务。** 脚本不属于生产医学gold、第二独立人工或未见盲测，0个未见任务。

所有 `usage` 是演示计量累加的合成数值；`hosted_model_calls=0`、`api_cost_usd=0`描述本次评分命令的真实调用/费用。报告不能用合成Token、费用或P95宣称实际性能。`EvaluationPlan`当前强制development_only/scripted、formal_gate=false；正式/真实评测采集与隔离runner还要后续明确版本，不能仅把一个字段改为holdout。

## 2. 谁提供什么

| 输入 | 可信提供方与用途 | 不能替代什么 |
| --- | --- | --- |
| EvaluationPlan | 评测方在运行前登记case、执行ID、父执行、问题、叙述、所问来源/版本/日期、必需项、证据组、预期终态/原因、恢复和安全阻断适用性、行为检查项；原规格SHA及执行条件绑定 | 不能由规划模型修改，不能跑后删题/改N/A；plan hash本身不认证登记时间或保管人 |
| ExecutionRecord | 后续可信采集器从已持久化材料、真实动作和逐调用回执提取；当前只有公开脚本 | status=completed、audit hash、source_id或动作结果文字都不证明真实完成/权限/持久化 |
| Assessment | 评测方对确切record摘要给出逐项pass/fail/unknown、评审者、证据ref；脚本明确scripted_fixture | 不接受规划模型的自评分。字段本身不认证审核者，不证明证据真实，不等于独立人工 |
| JudgeAttempt | 模型裁判的每个成功/失败/取消尝试、独立receipt和用量/已知费用/保守预留 | 模型失败不得删除；unknown仍在分母，裁判费用另列，不混入Agent执行成本 |

运行、清单与评价全量重验，拒绝旧plan/条件/record摘要、未登记/重复/孤立行及跨case父关系。复制构造也重验Python原始类型，避免JSON序列化把bool变int。原清单顺序固定、父执行须先登记；失败/取消记录不可被新执行覆盖。摘要是内容关联，真实保管身份/运行前签名和受限证据读取仍是EVAL-33/后续collector责任。

`source_id`必须由评测方映射到固定文档、版本和PDF摘要的证据身份，不能只用标题或模型生成的名字；当前均为显式synthetic身份。`source:<claim>:<evidence>`检查还须核对来源角色、日期和适用范围，区分询问原文与询问他文档对它的引用。运行时source_scope/RLS不由本评分器实现。

## 3. 分项与分母

| 指标 | 判定与分母 |
| --- | --- |
| business_completion | 全部登记执行分母。实际completed，完整性、逐字叙述及语义、引用与来源、工具/恢复/停止、十项运行保护及登记行为均通过，且材料保存摘要存在；摘要真伪由可信审计核对。正确停止不算完成；另报预期可完成切片 |
| handling_correctness | 全部登记执行；终态和原因符合预期、行为/运行保护/适用工具/恢复通过；已输出事实/声明须正确。合理澄清、无答案升级、故障停止可通过；正常可回答题误拒答失败 |
| tool_appropriateness | 每任务和每动作分别报告；未解析规划也消耗决策并失败，错误action_id单列；相同动作/参数/结果连续两次且无新证据失败。仅事前登记的无工具安全阻断可N/A；其他正确零调用需tool:none证据 |
| result_driven_adjustment | 预登记恢复子集。实际空检索后执行不同规范化query并获得新证据，或部分证据后授权读前后邻块获得新证据；还需recovery证据。只换理由、重读当前块、重复已有句柄不通过；普通题N/A |
| narrative_fidelity | 全部已输出事实逐项；Unicode半开区间精确匹配原叙述，value必须逐字等于quote，另须fact语义判词。当前不接受未登记的归一化/推断。空输出unknown，不是100%；缺必需项另计完整性 |
| claim_support | 全部输出声明的语义判词，含数字/否定/条件/时间；与引用正确性独立计数 |
| citation_correctness | 全部声明-引用对，实际存在且对应语义支持判词通过；编号存在本身不充分 |
| source_compliance | 全部声明-引用对，固定source_id允许且来源角色/版本/日期等判词通过；无引用unknown，不能规避完整性 |
| required_completeness | 全部事前登记必需项；AND跨证据组、OR组内替代。只用该requirement真正支持且来源合规的引用，不借用其他claim。分别报必需项计数与每任务全满足判词；缺项fail，语义未知unknown |
| clarification_stop_escalation | 实际终态/原因及stop判词；必要问题、停止后无新调用、不泄露隐藏存在性、不把系统故障当正确无答案由登记behavior检查与审计证据核对 |
| execution_guards_and_traceability | 全任务：authorization/input_safety/output_safety/budget/deadline/cancellation/ownership/version_binding/audit/fee_reconciliation十项。缺任何必需判词unknown；实际超8决策/12,000输入输出Token/600,000微USD已知加保守预留/125,000ms执行窗口也失败 |
| efficiency | 每执行计决策数、物理模型attempt、输入/输出Token、已知及保守费用、根执行时间、等待、清理；全部/终态/case分别汇总，P95用nearest-rank。失败、超时仍在；缺记录单列且p95_complete_coverage=false，不填零时延冒充全量 |

组合规则fail优先于unknown；unknown绝不作为完成通过。`not_applicable`来自预登记适用性，不能由模型/裁判临时添加。空输出不能通过完整性；一个可选证据通过不满足另一个必需组。所有实际输出额外错误也影响完成，不因gold覆盖就忽略。裁判有效覆盖只把pass/fail算有效，unknown/缺失单列；缺执行另外计missing_records，不能把“没有可判句子”报成满覆盖。

执行窗口采用原125秒保护，清理耗时另列；原QA8秒、Skill15秒P95及同等质量Token节省25%门继续保留。无新增总成功率/Agent P95数值门，也未改生产旧gate代码；新生产规则接线仍属GATE-01。

## 4. 澄清续办、失败与费用

`execution_id`是每次登记执行/启动尝试的身份；`business_case_id`是业务case。同case显式新执行引用parent，原awaiting_clarification/cancelled/failed行保留；case最终完成另报，不能把续办变成新的未见题。被拒绝的启动也保留为零调用执行记录，不意味着实际新建了根预算。`same_run_recovery`脚本是拒绝未持久化恢复的负例，未实现真正恢复。

每execution usage只写本次增量，不能填case累计额再跨执行相加。case汇总保留原已知/未决预留、新执行和授权批次检查；评分器不能放行付费调用、释放预留或自动续费。清理与等待是否重叠由真实collector说明，不把相加当根时延。

新增澄清变体：补齐版本后显式续办、跨身份、跨部门、过期、删除、撤销、并发旧revision、重复启动、缺TTL/次数policy、缺授权、批次费用耗尽、缺原预算/期限/租约的同执行恢复。脚本3600秒TTL/12次followup只是合成登记条件，**不是所有者批准的部署默认值**。运行时SESSION-01/02仍未实现。

## 5. 工程验收与后续

EVAL-32只要求评分规则/公开开发脚本及计分反例符合既定设计；所有原12场景及必要变体都须预设判词匹配。实际Agent在真实工具、租约、持久审计、最终核验和澄清续办上的综合执行属于AGENT-07，托管模型基线属于获准后的AGENT-08。不能用本轮脚本替代它们。

当前没有真实语义校准、真实Agent可完成率/成本/P95、独立保管环境验收、新盲测或生产采用声明。后续AGENT-03实现模型根据观察选择动作，模型规划输入只由运行时契约投影，不读取本文件/期望/判词/私有环境。AGENT-04/05/06及最小SESSION分别承担实际保护、最终门和追溯；EVAL-33/34/35/36继续单独取证。回滚仅删除新增评测包/脚本/测试并回填文档，无迁移或生产变更。
