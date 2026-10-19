# Agent 诊断回放

2026-10-19，AGENT-06，记录223。本切片八项工程自审及完整CI通过，AGENT-06 DONE；台账状态以 CURRENT_TASKS 为准。沿用 PLAN-02 §7 的“当前条件诊断 + 差异报告”，原条件恢复继续明确拒绝。

## 1. 入口与用途

`bootstrap.agent_replay.production_agent_replay(...)` 是可信服务装配入口；显式提供 ProductionRuntime、PlannerConfig、FinalGateConfig、FactDatabaseBinding、当前 rubric SHA-256 和租约周期。返回 `AgentReplayService`，调用 `replay(source_run_id, AgentReplayRequest(...), authorization=管理员Bearer凭据)`。凭据只在内存鉴权，不写报告、事件或遥测。

这是可运行的内部服务接线，使用真实 AgentRuntime、Driver、当前策略/来源解析、既有 RAG/Skill 工具、终检与终态提交。公开业务 HTTP/CLI 准入和演示由后续集成/交付任务处理；旧 Ask `/admin/traces/{trace_id}/replay` 继续拒绝 Agent，不把 PV 叙述改成空 query 的 Ask。没有新增公开 Schema 或隐式 Agent 规划/终检默认值。

示意（配置和密钥必须由可信启动层提供；此代码执行可能产生费用，不是本轮运行授权）：

```python
from uuid import uuid4
from medops.application.agent_replay import AgentReplayRequest
from medops.bootstrap.agent_replay import production_agent_replay

service = production_agent_replay(
    runtime, config=planner, final_config=final_gate,
    database_binding=fact_binding, rubric_sha256=current_rubric_sha, lease_s=10,
)
command = AgentReplayRequest(replay_id=uuid4(), reason="已授权的具体诊断用途")
report = service.replay(original_run_id, command, authorization=authorization)
# 网络或报告写入失败：保留同一个 command / replay_id，不生成新 UUID 自动重试。
```

调用者须另行取得所有者对本次托管运行范围、费用上限和停止条件的明确授权。服务接口和数据库月度上限均不替代该授权。本轮只有公开合成材料、Fake provider 和临时 PostgreSQL 测试，0 次托管调用。

## 2. 原输入与当前条件

1. 先验证当前管理员、实际身份库和受限库一致。用途至少8个非填充字符、至多500字符；受限审计访问日志必须提交成功，才使用解密材料。
2. 只接收有真实终态、Trace、受限 head/事件及匹配元数据的 Agent。完整输入/终态/逐调用/预算链须受支持且一致；缺失、损坏、过期或未知输入不从普通 Trace 猜测。历史读取仍不运行旧循环；诊断解析不加载旧 LoopState/RuntimeBody 为当前可执行状态。
3. 原叙述、synthetic=True、来源类型、要求、可澄清字段、原日期与显式历史模式、请求的文件及版本保持。原用户从当前目录重新解析，不能换成管理员；停用、跨部门或丢失 read scope 在模型前拒绝。当前身份的非授权性属性变化在报告中反映。
4. 重新解析原文件/版本选择器，绑定当前获准路由、Prompt/工具/终检配置及事实库；不复制旧证据句柄、预算、租约、未决调用或模型回复。原明确来源已不可访问时在新调用前拒绝，不能用别的文件替代；原模糊范围仍按真实当前解析结果处理。
5. 新建独立 case/task/run/attempt/trace 五身份，由显式请求 UUID 确定；以报告和受限 provenance 关联原运行。新执行仍受8步、12,000 Token、0.60 USD、125秒及真实终检预留约束，不承诺走满8步。它不是旧执行恢复或澄清续办，也不合并为原 case 的续办。
6. 实际资源检查同时重新验证管理员权限和身份库；每次模型准入及最终保存仍走原 Driver 的原用户/来源/预算/取消检查。管理员撤权后的财务结算路径继续保留，不能因禁止后续动作而丢弃已发生费用。

## 3. 持久化和重试

控制/head 初始化成功后、第一笔供应商调用前，以既有 `checkpoint` 事件保存受限 `diagnostic_replay` provenance，包含请求 UUID、管理员假名、来源运行/Trace、原 context 摘要和请求摘要。提交不确定时不进入供应商；已有运行 UUID 不能被再次创建。

业务终态仍与真实 Agent Trace 原子保存；随后读取真实已提交原件，计算无正文报告并追加既有 `replays` 表。诊断 Trace 保持 `kind=agent`，保留六状态/停止原因语义；不能标作 Ask answered。无需新迁移、新角色或新权限。

报告不是与业务终态同一事务：报告写入/提交失败，终态和计量保留，调用返回失败。同一请求 UUID 重试只读取已保存终态并补写/核对报告，无新根预算、模型或工具调用；报告使用原停止时间，幂等比较稳定。运行存在但终态或 provenance 不完整时拒绝自动重启；不同用途/来源/管理员复用同 UUID 拒绝。并发重复请求由真实 control 主键保护，只有一个能够进入执行。

不能以诊断运行再作为新的回放来源。新 UUID 表示新的独立实验请求，须重新获得相应付费授权；服务不自动轮询、换 UUID 或扩预算。

控制记录已清理但普通Trace或replays记录尚存时，也在新模型前拒绝复用身份。幂等证据受实际保留期约束；全部相关记录已清理后无法证明一个UUID从未使用，不承诺永久去重。调用方不得在清理后把旧请求作为自动重试；应重新登记并授权明确的新实验。

## 4. 如何读报告

`AgentReplayReport` 是私有 `pv-agent-replay-v1`，普通表只保存固定身份、版本、数值预算、动作名称/观察类型、哈希和差异标签。叙述、文件描述、要求正文、短理由、问题、证据、Prompt、回复、异常消息和凭据不复制到报告。自由文本用途只在既有受限访问日志，`replays.reason` 使用固定前缀和请求摘要。

| 字段 | 实际含义 |
| --- | --- |
| source / replay | 两个真实已保存终态的身份、版本、原预算/已知/保守计量、状态和原停止时间 |
| conditions.input_match | 原用户输入（含日期/模式和明确来源选择器）摘要是否相同；新执行身份、当前解析与版本不混入这项 |
| identity_match | 原用户身份快照与当前实际身份是否相同；始终不使用管理员身份执行 |
| source_scope_match / profile_match | 实际解析来源集合/原件哈希、工程终检预留配置是否一致 |
| versions_match | 只比较基础 VersionSet 标签；不等于原 Prompt、配置或事实环境相同 |
| configuration_match / routed_policy_match | 实际 PlannerConfig+profile、实际 Agent 条件摘要是否一致；不把摘要称作完整语料快照 |
| evidence_match | 原实际证据 Citation、原件哈希、块文本哈希的集合是否一致；同 chunk ID 改正文也能报告变化 |
| actual_models_match | 请求 purpose/模型、实际 provider/模型/fingerprint 序列摘要；不完整返回标 null，参数差异另看配置/原调用审计 |
| changed | 状态/原因/决策步数、已提交工具动作路径、证据/引用 ID、实际证据注册表内容和规范化输出摘要的变化；新随机句柄、回执与执行绑定不造成必然差异 |

输出摘要对证据句柄作真实引用映射，保持 AND 组/OR 组语义；不把多块共同必需关系扁平成任选其一。完整短理由、逐调用 SDK 参数、回复与证据仍走管理员用途审计读取，不导出到 Langfuse。没有增加 S3 的自动评分/反馈采纳；原 Observe 仍只接 ask/task。

生产块保持不可变，修改应走正常的新版本摄取。相同ID不同正文的反例只在有明确前缀保护的临时库中模拟恢复快照；正常写入仍会被数据库拒绝，哈希不一致的快照仍会被检索完整性检查拒绝。`rubric_sha256`登记可信调用方提供的评测契约身份，本诊断服务不计算rubric得分或医学质量成功率。

`source_artifacts_match`、`rendered_evidence_match`、`corpus_match` 当前为 null；没有交付签名旧运行工件、原词法/向量索引快照、逐请求渲染差异比较。`original_conditions_reproduced` 恒 false。相同模型标识/指纹不锁定供应商权重，差异也不是质量变化的因果归因。

## 5. 原条件、集成与质量边界

管理员请求 `mode="original_conditions"` 时，5秒有界鉴权后、解密/依赖装配/模型准入前，以 `version_conflict` 拒绝；不会回退到当前条件。完整恢复原条件、Task/MCP 通用回放、真实 Langfuse 后端 Agent 排障、托管模型质量/时延/成本、独立盲测及生产发布分别验收。

AGENT-06 的完成只覆盖记录220～223的工程接线与回放边界。SESSION最小澄清续办仍是AGENT-07前置；AGENT-08真实试跑须逐次授权，S2整体尚未完成。验证失败、修复与八项自审见[记录223](../reviews/2026-10-19-implementation-223-agent-diagnostic-replay.md)。正式三库维持0026，新代码未部署。
