# 记录 178：ARCH-02 历史输入、Skill 提示与 Ask Replay

日期：2026-10-11。任务：ARCH-02。实施与审核：Codex（实现者自审核，不是第二独立人工）。依据项目所有者“继续”、统一台账与每轮自审要求。本轮没有托管模型调用、没有医学结论/评测 gold 裁决、没有提交或推送。

## 1. 范围与原缺陷

原 AR02 指出 `skill_context` 只把历史日期传给 Context/引用 lookup，而实际依赖由 `AskRequest(query="task", historical=None)` 装配。两个 Skill Harness 入口也缺少历史状态。Task 接受 `historical.version` 后不解析，Ask 则提示“将由任务 API 支持”，与事实不符。Replay 只保存摘要问题，没有原日期/模式，容易静默运行成普通问题。

先用替身复现：请求 2025-01-01、runtime 普通日期 2026-10-11，`ctx.as_of` 是前者、`ctx.deps.as_of` 是后者，**1 failed / 0.79s**；修复前反例真实失败。本轮只修日期/模式/选择器与诊断回放，二阶段判断、完整 Task 审计和原条件复现继续归 ARCH-03/06/07。

## 2. 设计与改动

| 范围 | 实现 |
| --- | --- |
| domain/query.py | 传输无关的 `QueryContext(as_of, historical_requested)`；有效原选择器可从 selector 属性恢复。普通固定日期不自动开启历史模式；规范日历日期严格解析 |
| API / worker 装配 | Ask 和 Skill 共用解析规则；日期进入检索装配、Harness 状态、来源解析与事实回查；相互矛盾的输入在模型调用前拒绝 |
| 版本选择器 | Ask/Task 的裸 version 均 400 invalid_request，提示改用 as_of；旧队列在装配前拒绝。缺文档家族身份不能猜 v1 属于哪份文档；没有新增全局版本解析规则 |
| Harness / Registry | 状态携带完整上下文；日期/模式进入 operation key；同一批 Skill 在分发前固定日期，不能跨午夜产生不同条件 |
| 文档选取 / 引用 | 指定来源和聚焦按同一生效期选 active/显式 archived；lookup 显式传 allow_historical；RLS、状态、生效期、来源完整性、解析信任和哈希回查保留 |
| Skill 最终结果 | label、off-label、protocol、citation 四类文档 Skill 保留实际归档使用的 historical_notice。AE 只提取用户叙述，不会仅因带历史日期而声称用了历史文档 |
| Trace / payload | nullable 日期/模式元数据；受限 input 同步保存；没有新增正文进入普通遥测，没有改受限载荷加密/保留/读取审计 |
| Replay | 只支持保存了上下文的 Ask；在原主体当前权限、当前事实/发布策略下沿用原日期/显式模式。Task/MCP、旧 NULL 输入明确拒绝，独立新 run/Trace/operation key 保留 |
| Schema / 部署 | 迁移 0024、可空 ReplaySide.query_context、请求文档说明同步导出；Skill 基类新增默认 false 的提示字段。严格旧响应客户端需更新；未迁移环境不可运行新 Trace store |

规则说明见[历史查询执行契约](../HISTORICAL_QUERIES.md)。没有改默认模型、发布策略指针、ACL、安全门禁、冻结样本、gold 或指标阈值。

## 3. 自审发现、错误与补救

| 失败/发现 | 原因、处置及复验 |
| --- | --- |
| 原反例 1 failed | Skill 的实际检索日期被普通请求覆盖 → 共用 QueryContext 装配 → 原反例通过 |
| 首次类型检查 1 error | mypy 无法从复合条件证明 `deps.as_of` 非空 → 分开历史分支并显式拒绝 None → 196 源文件检查通过 |
| 一次测试插入落在旧用例中间 | 补丁的短上下文匹配到较早的括号 → 移出新增函数，恢复旧测试全部断言 → API 定向通过；没有削弱原检查 |
| 定向 85 passed / 7 failed，2.38s | 2 项测试漏配必需 redis_url，5 项误把既有 invalid_request HTTP 400 写成 422 → 修测试配置/契约预期，没有改错误映射 → 80 项扩展定向通过 |
| 数次批量 patch 被原子拒绝 | 猜测导入/断言或仅写出半段文档行，未匹配真实文件 → 阅读真实位置，删除不必要的匹配段后重写小补丁，没有半写入；最终文档链接和 diff 检查通过 |
| 数据库反例的潜在假绿 | 手写 INSERT 缺 duration_ms，宽泛捕获 psycopg.Error 可能只测了 NOT NULL → 补正常必需字段，限制 SQLSTATE，并核对 `traces_query_context_shape` 约束名 → 六种错误载荷真实被目标约束/日期解析拒绝 |
| 归档来源仍找不到 | 标题候选原来只选 active → 把来源解析/聚焦文档列表纳入同一日期/状态过滤 → 真实 RLS、日期边界与候选列表回归通过 |
| 结构化 Skill 提示丢失 | 内部 Answer 有历史提示，最终业务 Output 没复制 → 提升为共用结果字段并从实际证据传递 → 四类文档 Skill 复验通过 |
| 批量跨午夜条件漂移 | 每个子 Skill 才解析 today → 分发前固定 Context → 模拟跨日的批量用例通过，16 项 Registry 定向通过 |
| 初次多库迁移只升级主库 | `migrations/env.py` 不读取 cfg.attributes[dsn]，实际优先读 MEDOPS_MIGRATION_URL；命令正常返回不能证明所选库升级 → 保留首次报告，改用真实支持的环境变量并恢复环境，逐库强制核对 revision=0024 和列存在 → 三库都到 0024、保护摘要一致 |
| 日期可能被 API 隐式转换 | 通用 date 字段可接受数字/午夜时间戳，与日历日期选择器不符 → API 使用共用严格解析；数字、bool、紧凑/周日期、时间戳、非法日期均不接受 |
| 新校验首次 lint F821 | 忘记新增 field_validator 导入，lint 阶段退出，测试未运行 → 按实际含 JsonValue 的导入补齐 → 26 项日期/Registry 定向通过 |

只读定位时几次使用不存在的测试/模块路径，属于工具读取错误；之后用 rg 定位，未据此猜测新增转发模块。所有错误均在通过前修复或明确作为范围限制保存。

## 4. 数据库与兼容

- 本机 `medops_v2`、`medops_v2_safety`、`medops` 最终均 **0024**；逐库核对新列存在。每库 **25 张受保护事实/任务/Trace/策略/费用/索引元数据表内容 SHA-256 不变，5 张派生索引表行数不变**。比较排除唯一新增的 nullable query_context 列；旧 Trace 没有回填。动态 outbox 消费表未列入这份内容摘要。
- 首次和最终报告本地保留在 `.local/arch02-migration-first.json`、`.local/arch02-migration.json`，不含 DSN/密钥/正文。费用账本和调用回执内容不变，0 新供应商费用。
- 0024 的数据库形状仅允许规范日期字符串和布尔值；正文键、空对象、缺键、null/字符串布尔与非法日期由应用角色真实测试拒绝。没有给角色增加权限。
- 公开 Ask/Task 请求形状未改变，描述和日期校验变严格；Replay 追加可空上下文。Skill 的新提示字段有默认值；使用旧严格输出模型的客户端应更新。
- 当前代码仍未重启进常驻服务。数据库先升可供旧代码继续运行；新代码部署前必须保证所有目标库具备 0024。

## 5. 验证

- 初始已有功能回归：92 passed / 2.65s；覆盖 Ask、Replay、五类 Skill、Harness 主链和节点规则。
- 日期、版本拒绝、历史传递、缓存、真实 PG 生效窗/角色和迁移定向：**80 passed / 5.30s，退出 0**；日志 `.local/arch02-directed.log`。
- 四类最终历史提示、五类 Skill 原矩阵、真实 PG 引用/元数据约束：**86 passed / 2.74s，退出 0**；日志 `.local/arch02-skills-and-pg.log`。
- 日期严格解析/批量 Registry 最终定向：**26 passed / 0.99s，退出 0**。
- 收尾前两轮完整检查分别为 **1901 passed / 70 skipped / 1 warning，52.67s** 与 **1902 passed / 70 skipped / 1 warning，50.27s**；后续又补严格 API 日期校验，因此最终以第三轮为准。重复门禁用于复验新增的跨日与输入转换风险，没有把中间通过当作最终结果。
- **最终全量：1908 passed / 70 skipped / 1 warning，50.94s，退出 0。** 命令：`env -u DEBUG PYTHONPATH=<worktree>/src:<worktree> make check`；468 文件格式检查、196 源文件类型检查、lint、安装检查、四集数据审计与 Schema 漂移均通过。注册 detached 核验工作树 `/Users/leaf/.cache/medy-checks/arch02-verified-y0509r6m`；沿用相同外部 venv，带入相同 .env 与 .env.dec001，不输出或提交凭据；最终日志 `.local/arch02-check.log`。
- 70 skipped 均为既有 B/C 可选实验服务不可达；单独 `pytest` 两适配器 `-q -rs` 为 70 skipped / 0.06s，原因明确。BM25 D 与 PG/Redis 必需集成在完整检查实际执行；warning 来自认证反例刻意使用短 HMAC 密钥。
- **501 维护输入/配置 SHA 一致，0 不符；两个本地秘密配置内容一致，仅保存相等结论。** 原 85 个未提交文件全部保留，70 个不变、15 个本轮明确重叠；141 个任务 ID 完整，仅 ARCH-02 从 READY 到 DONE；8 份同步文档的 177 个本地链接存在，`git diff --check` 通过。Ask/Task 请求 Schema 剔除描述后与 HEAD 形状相同。
- 真实模型语义质量、延迟、供应商账单对账、Agent 和未见盲测没有在本轮测量。独立人工 pending、2 个 unmappable gold 与历史安全回放限制保留。

## 6. 强制自审核

| 检查项 | 结论 |
| --- | --- |
| 需求/范围 | 通过：日期/显式模式/选择器/诊断回放一致；不把日期修复写成完整 Agent 或原条件复现 |
| 正确性/失败路径 | 通过：原错位、边界日、无日期历史、冲突上下文、遗留版本、旧 Trace/错误类型、跨日、日期隐式转换均有反例 |
| 权限/数据 | 通过：真实应用角色/RLS 与跨部门拒绝验证；25 表保护摘要/5 索引计数不变；冻结数据和阈值未改 |
| 预算/取消/副作用 | 通过（本轮输入范围）：0 托管调用；拒绝发生在模型前；ARCH-01/04/05/11 执行保护保留；新迁移只加元数据列 |
| 追溯/版本 | 通过（日期范围）：状态、缓存、operation key、Trace、payload、Replay 同一日期/模式；保存当前事实诊断语义；完整版本/Prompt/证据恢复仍待 ARCH-06/07 |
| 验证充分性 | 通过（工程范围）：定向、真实 PG/约束/边界、1908/70 全量、501 输入 SHA、真实迁移与保护摘要；不据此声明模型质量或性能提升 |
| 状态/文档 | 通过：READY→IN_PROGRESS→REVIEW→DONE；141 ID 无增减，仅 ARCH-02 状态变化；原 85 文件无丢失，70 不变/15 明确重叠；177 链接与 diff 通过，契约/部署/README/计划/阶段/场景同步 |
| 独立复核/阶段 | 通过：本轮仅实现者自审，第二人工与原质量门仍 pending；S2/S3 未完成 |

## 7. 限制、回滚与下一项

1. 裸 version 精确查询未实现，已明确拒绝；MCP 原历史输入契约保留，MCP/Task 单条回放不在本次 Ask Replay 范围。
2. Replay 使用当前事实/权限/策略、沿用原日期；NULL 旧输入拒绝，没有为其生成伪上下文。完整输入、原渲染片段、原条件复现归 ARCH-07。
3. 四类 Skill 的历史提示与日期已修，不证明最终判断可靠；下一主切片 **ARCH-03** 修二阶段最终业务判断，工程核验后再单独申请真实质量校准。
4. 代码回滚按本轮文件备份恢复；不整树 reset。备份 `/var/folders/zj/6djhy_4x7vx_7t8xcgt_v62c0000gn/T/medy-arch02-we_nvmtc`。保留旧代码兼容的 0024；如果降级数据库，先停写并导出新上下文，否则元数据会丢失。
5. 当前未提交、不推送、不重启服务；本轮无新增人工决定与费用请求。PLAN-02 剩余 Agent 行动/profile 和验收契约继续有效，未获真实试跑授权。
