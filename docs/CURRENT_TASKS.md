# 当前任务台账

更新：2026-10-09。完整设计与任务说明见[迭代计划](ITERATION_PLAN.md)，阶段通过条件见[阶段表](ITERATION_STAGES.md)。本页只记录当前有效状态；历史记录中的旧待办不自动覆盖本页。

状态：`DONE` 已完成并验证；`READY` 可无付费继续；`HUMAN` 需要真实人工决定；`PAID` 每次运行前需要用户明确批准本次范围和费用；`BLOCKED` 等待前置；`OPTIONAL` 不阻塞当前迭代。

## 0. 当前执行门

| ID | 任务 | 状态 | 完成或前置证据 |
| --- | --- | --- | --- |
| ENV-01 | 本地 `DATABASE_URL` 与 `DATABASE_ADMIN_URL` 指向具备持久费用账本的正式本地事实库 | DONE | 本机 `.env` 已由 `medops` 改为 `medops_v2`；不记录凭据 |
| DB-01 | `medops_v2` 升至 migration 0021 | DONE | 0020 提供费用/失败账本；0021 提供不暴露账本行的月度总额函数 |
| DB-02 | `medops_v2_safety` 升至 migration 0021 | DONE | 2026-10-08 从 0019 连续升至 0021 |
| DB-03 | 旧开发库 `medops` 的去留 | READY | 保持 0007、231 份 draft；API/正式评测不再默认连接它。后续决定退役或迁移，不阻塞当前工作 |
| ADJ-01 | 裁决 `ms-0125` | DONE | 项目所有者按建议保留现有 `char_end=2226` |
| ADJ-02 | 裁决 `ms-0241/ms-0242` 的证据组 | DONE | 三类正式示例共同必需，standard-of-care 仅作补充；已落实到 v3 |
| ADJ-03 | 裁决 `ms-0280` | DONE | 已增加 `protocol_id`，query、gold 与日期保留 |
| PAY-01 | 裁决后受影响题模型复核 | DONE | 3/3 调用成功，0.555900/0.750000 USD，2 agree、1 dispute；记录 147 |
| ADJ-04 | 裁决 `ms-0241/ms-0242` 第三个示例的 key | DONE | 已同步补全药物组与同期/历史对照组的比较对象并生成 v4 |
| PAY-02 | ADJ-04 修改后的两题复核 | DONE | `ms-0241`、`ms-0242` 均 agree；失败调用费用保留，v4 后续尝试合计 0.627325 USD |
| PAY-03 | FDA 标题修正传播到 7 条既有样本后的定向复核 | DONE | 7/7 agree；7 次调用、无失败或重试，0.593073/2.250000 USD；记录 150 |
| ADJ-05 | 裁决 EVAL-11 的 3 组跨块 gold 修订 | DONE | 项目所有者回复“确认”；6 条样本、18 个共同必需 gold，精确哈希见记录 152 |
| PAY-04 | EVAL-11 v5 修订后独立模型复核 | DONE | 4 次有效调用后因两个父题争议停止；2 agree、2 dispute、0.579062/1.950000 USD；未调用两个同源孪生，记录 153 |
| ADJ-06 | 裁决 EVAL-11 v6：保留 2 个 GVP miss，并接受 IRB/IEC 单 gold 修订 | DONE | 项目所有者回复“确认 EVAL-11 v6 建议”；确认哈希 `d23e9326…3171`，记录 154 |
| PAY-05 | EVAL-11 v6 两条变更后的 `pc-*` 输入独立模型复核 | DONE | 2/2 agree；2 次调用、无失败或重试，0.290727/0.650000 USD；记录 155 |
| PAY-06 | EVAL-12 十题真实回答与快照 | DONE | 10/10 终态、10/10 快照、0 system failure；6 answered / 4 escalated，实际 0.085875/0.350000 USD；记录 159 |
| PAY-07 | EVAL-12 四题补充生成 | DONE | 4/4 answered 且 gold cited，0 system failure，实际 0.027149/0.150000 USD；记录 159 |
| PAY-08 | EVAL-12 十条真实答案的 Claude 语义裁判 | DONE | 10/10 有效 verdict；三轮 12 次累计 0.830482 USD。Schema 轮 8 次实际 0.578090/2.400000 USD；claim 12/12、citation 13/14、完整性 7/14；记录 160 |

probe v4 与 `main-v5-provisional` 均已冻结。EVAL-11 已完成：580 个 gold mapped、2 个 GVP 跨 chunk gold 继续作为 unmappable miss 留在分母。EVAL-13 的来源契约与默认关闭候选、EVAL-14 的回放绑定与运行中事实漂移检测均已完成零费用工程核验；正式答案级回归仍需逐次付费授权。

## 1. 工作区治理

| ID | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| W-01 | 删除 Finder 副本 `src/medops/infrastructure/llm/budget 2.py` | DONE | 文件未跟踪，已删除，避免 `git add -A` 误收 |
| W-02 | 区分源码、评测产物和临时 `output/` | READY | 提交前逐组检查 |
| W-03 | 按功能边界拆分提交 | READY | 不按作者拆；记录 143 的代码归 API/Harness 组，文档归文档组 |
| W-04 | 每组提交前运行定向检查，最终运行 `make check` | DONE | 记录 160 最新隔离复测：1712 passed、70 skipped；ruff、格式、mypy、Schema 漂移与评测审计均通过；改动仍未提交 |
| W-05 | 更新 README、阶段表、路线图和验收报告 | READY | 状态必须区分实现、部署、付费运行和正式门禁 |

建议提交顺序：评测标准与工具；API/Harness 重构（含记录 143 的代码）；遥测与 Langfuse；运行完整性/0020/MCP；文档与证据（含记录 143 的文档）。

## 2. 第一批：评测可信

### 2.1 数据修订

| ID | 任务 | 状态 |
| --- | --- | --- |
| EVAL-04 | 应用三项人工裁决，保留旧值、修改值、依据和裁决记录 | DONE |
| EVAL-05 | 重建修订输入、manifest、SHA-256 和 gold 映射 | DONE |
| EVAL-06 | 重跑字符区间、页码、key 唯一性、来源身份、证据组和配额检查 | DONE |
| EVAL-07 | 为受影响题生成新的复核输入 | DONE |
| EVAL-08 | 调用模型复核受影响题 | DONE | v4：`ms-0241`、`ms-0242` 均 agree；原失败调用与费用保留，记录 149 |
| EVAL-09 | 将三道 `pc-*` 修订写入新的探针版本 | DONE | probe v3；107 条；dataset hash `5707f29d…97f` |
| EVAL-10 | 生成并冻结新的主集版本 | DONE | `main-v5-provisional`；615 条；dataset hash `23bf8530…842b0`；582 个 gold 中 580 mapped、2 unmappable |
| EVAL-11 | 处理剩余 6 个 unmappable gold；不能修复的继续保留在失败分母 | DONE | 安全修复 4 个原 miss；2 个 GVP 跨 chunk miss 保留；probe v4 与 main v5 已冻结，见记录 155 |

### 2.2 评分、正式运行与独立性

| ID | 任务 | 状态 |
| --- | --- | --- |
| EVAL-12 | 校准语义支持与答案完整性裁判 | DONE | 14-case 校准完成：10/10 answered 有 verdict；claim support 100%、citation support 92.9%、overall completeness 50.0%，formal_gate=false；记录 160 |
| EVAL-13 | 区分指定来源、等价来源、共同必需和任选证据 | DONE | 34 条版本化来源契约、独立来源计分；记录 156 |
| EVAL-14 | 加强运行中事实变化检测及回放两臂实际版本绑定 | DONE | 两臂/逐行版本绑定、基线执行身份与来源尝试、300 秒周期及终检；记录 157 |
| EVAL-22 | 新主集正式检索/回答运行 | PAID |
| EVAL-23 | 新主集正式端到端质量运行 | PAID |
| EVAL-24 | 冻结 safety-v2 上的首次正式安全运行 | PAID |
| EVAL-25 | 使用新主集和 safety-v2 构建 replay-v4 | BLOCKED |
| EVAL-26 | 正式多轮回放对照 | PAID |
| EVAL-27 | 分别报告 Recall、Hit、MRR、语义支持、完整性、误拒答、系统失败、安全、时延、Token 和费用 | BLOCKED |
| EVAL-28 | 更新正式验收报告 | BLOCKED |
| EVAL-29 | 主集 536 条第二独立人工复核 | HUMAN |
| EVAL-30 | 安全集 170 条人工证据缺口 | HUMAN |
| EVAL-31 | 建立按文档家族隔离的未见盲测集和暴露账本 | HUMAN |

模型复核、正式回答、安全运行和回放均会产生模型费用。月度数据库预算上限只是技术保护，不代替逐次用户批准。

## 3. 第一批：指定来源、运行完整性和 Langfuse

| ID | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| SRC-01 | 标注显式指定、上下文指代和未指定来源 | DONE | 34 条来源角色契约；记录 156 |
| SRC-02 | 建立产品、文件、版本和别名解析 | DONE | `source-constraint-v1` 候选，发布参数默认 off |
| SRC-03 | 区分文件内容与他文档引用意图 | DONE | 宿主/引用/讨论/采用/合订/关系反例通过 |
| SRC-04 | 执行共同必需证据覆盖检查 | DONE | 事实组与来源组均为组间 AND、组内 OR，分别计分 |
| SRC-05 | 修复 `ss-0090/ss-0096` 并回归 14 道正常题 | PAID | 真实库结构回归通过；答案级正式对照及发布决定待授权 |
| IDX-01 | active 文档词法/向量覆盖、版本和 readiness | DONE | 记录 137–139、145 |
| IDX-02 | outbox 退避、死信和人工重放 | DONE | migration 0020 |
| IDX-03 | 长期部署消费者并演练毒事件恢复 | READY | 本机实现不等于常驻部署 |
| CACHE-BACKLOG-01 | `medops_v2` 缓存积压 338 条 | READY | Redis 关闭时不阻塞；启用前处理 |
| CACHE-BACKLOG-02 | `medops_v2_safety` 缓存积压 339 条 | READY | 同上 |
| DEV-BACKLOG-01 | 旧 `medops` 三个消费者各积压 231 条 | READY | 与 DB-03 一并退役或迁移处理 |
| OBS-01 | Trace、版本、费用、评分队列、退避和死信 | DONE | 记录 141、142、145 |
| OBS-02 | 部署真实 Langfuse、配置凭据和访问边界 | READY | 外部依赖 |
| OBS-03 | 完成 trace→score→feedback→UI 排障演示 | READY | 真实后端验收 |
| OBS-04 | 验证故障时本地排队、恢复和告警 | READY | 真实后端验收 |

Langfuse 的 `score-create` 通过 `/api/public/ingestion` 在 v4 仍受支持；弃用范围是旧 trace/observation 事件和旧读接口。OBS-02 仍需用真实部署的 OpenAPI、返回码和 UI 验证。

`skill_smoke` 每次执行生成唯一 W3C Trace ID、稳定 run ID；`safety_data.app_dsn` 已删除。这两项是 `DONE`，不再列为待办。

## 4. 第二批：检索更准、运行更快

| ID | 任务 | 状态 |
| --- | --- | --- |
| BM25-01 | 固定分词和其他检索配置，完成统计隔离、PG17 迁移与回滚方案 | READY |
| BM25-09 | 在新冻结集上跑完整检索与回答对照 | PAID |
| BM25-10 | 依据预登记采用标准决定是否切换生产 | HUMAN |
| CACHE-01 | 部署 Redis、namespace 和持续失效消费者 | READY |
| CACHE-02 | 验证撤权、归档、新版本和 Redis 故障 | READY |
| CACHE-10 | 真实重复问题流量收益测试 | PAID |
| PERF-01 | 翻译与原始查询检索并行、重排批处理/服务、有界并发和背压 | READY |
| PERF-10 | 并发 1/2/4/8/16 的真实模型容量复测 | PAID |
| FOCUS-01 | 保护数字、否定、条件和跨块证据，选定逐句裁剪候选 | READY |
| FOCUS-09 | 逐句裁剪正式多轮门禁 | PAID |
| ROUTE-01 | 为结构化、可验证的辅助任务寻找小模型候选 | READY |
| ROUTE-02 | 模型路由质量/费用/时延正式对照 | PAID |
| COMBO-01 | BM25、Redis、并发和裁剪组合对照 | PAID |

第二批必须先单变量测试，再做组合测试。每个 `PAID` 项都要单独给出样本、轮数、预计费用、上限和停止条件，并获得当次明确批准。

## 5. 第三批：使用闭环

| ID | 任务 | 状态 |
| --- | --- | --- |
| SESSION-01 | 接通 `session_id`、结构化实体、身份隔离、TTL、删除和并发更新 | READY |
| SESSION-02 | 测试跨用户、跨部门和跨会话污染 | READY |
| HANDOFF-01 | 原文页、证据块和来源版本查看入口 | READY |
| HANDOFF-02 | 人工升级材料、状态、负责人、结论和审计 | READY |
| LOOP-01 | 真实反馈→归因→候选→回放→批准→灰度→回滚完整案例 | READY |
| DEPLOY-01 | 选择 OIDC/IdP 并完成真实身份验证 | HUMAN |
| DEPLOY-02 | 远端 CI、资源预算、故障演练和备份恢复 | READY |
| DEMO-01 | 完成一个端到端药物警戒业务任务演示 | BLOCKED |
| DOC-01 | 更新验收、时间线、演示、简历和最终 PDF/Word | BLOCKED |

简历指标必须分别写：证据内 `MRR@8 = 0.7706`，候选内 `MRR@20 = 0.6142`。二者都没有达到项目描述中的 0.80。

## 6. 许可与选做项

- 当前 333 份 active 语料没有新的许可批次阻塞。
- DEC-011 v1.7 仍有 9 个早期候选没有 `reviewer_decision`；不影响当前语料，属于台账清理。
- OCR、独立推理服务、管理界面、外部工单、高可用、SBOM、多模态、知识图谱、跨语言增强和主动学习均为 `OPTIONAL`，不阻塞三批迭代。

## 7. 每轮完成定义

每项必须交付：可运行行为、可复现结果、已知限制、自审记录。不得隐式改变阈值、分母、模型、gold、ACL、发布策略或安全规则；不得把模型复核记为第二人工；不得把数据库费用上限当作付费授权。
