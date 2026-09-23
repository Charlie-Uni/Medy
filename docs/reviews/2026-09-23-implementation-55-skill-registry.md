# 实现记录 55：Skill Registry 与两个低风险 Skill（M2-11、M2-12 首切片）

- 日期：2026-09-23
- 范围：决策人 2026-09-23 指示"先开始不需要我决定就可以跑的东西"的延续。本切片交付 M2-11 Skill Registry（Schema、scope、risk、timeout、parallel_safe、版本的强制执行，INV-AUTH-03）与 M2-12 的两个低风险 Skill（说明书查询 `label_query`、医学引用验证 `citation_verification`）的正向与失败链路单元测试；真实部件下的 Skill 运行待主集全量运行结束后补做。
- 依据：基线 2.3（INV-AUTH-03）、3.2（operation key）、5.6（Skill 契约表）、§8 M2 清单；路线图"服务复用：API、MCP、Skill 都走同一授权检索与证据校验服务；并行只对 parallel_safe 工具开放，部分结果不等于可以跳过最终安全门禁"。

## 1. 决定与依据（实施方按授权作出，可否决）

| 决定 | 依据 |
| --- | --- |
| Skill 契约放在领域层 `medops.domain.skill`（`SkillSpec`、`SkillOutput`、`SkillStatus`），Registry 与实现放在 `medops.skills`；领域层不 import 任何适配器 | 基线 4.1 依赖方向；5.6 要求每个 Skill 声明 Schema、版本、权限、风险、超时、幂等、并行安全 |
| `required_scopes` 至少一项（默认拒绝），支持 `$dept:<action>` 在检查时解析为调用者本部门；显式部门与 `ADMIN` 保持固定 | INV-AUTH-01 默认拒绝；两个低风险 Skill 对三个部门都开放，但只能读本部门可见文档，scope 不能写死某个部门 |
| 执行顺序固定：查表 → scope → 输入 Schema → 版本集成员 → operation key → `run_node`（超时；仅幂等 Skill 可重试）→ 输出类型 → 安全第三层 | scope 先于 Schema，避免向无权调用者泄露输入结构；INV-HAR-05 要求版本进入 Trace，未登记版本即拒绝运行；复用 M2-02 的节点策略而不是另写一套超时 |
| 输出安全检查对所有 Skill 统一执行（`check_output_text`，与 Answer 节点第三层同一规则）；被拒时载荷整体替换为裸升级 `SkillOutput`，不外发 | 5.5 三层 Safety；路线图"部分结果不等于可以跳过最终安全门禁" |
| `execute_many` 只对 `parallel_safe=True` 的 Skill 并行，其余按请求顺序串行；每项结果各自过安全检查 | 路线图并行规则 |
| 处理器抛出的 `BusinessError` 原样上抛（调用方问题，如历史证据缺 `as_of`）；超时与基础设施错误记为 `system_failure` 升级并保留全部 attempt | 5.5 稳定 reason code；基线 5.3 失败即升级不猜测 |
| `label_query` 通过固定状态机运行（产品名作为会话实体），再核对全部被引文档为 `label`；引用了非说明书文档即报"证据不足"而不是把指南内容当说明书 | 5.6 说明书查询输出"原文片段、版本化引用、证据不足状态"；检索层暂无 doc_type 过滤（登记为后续） |
| `citation_verification` 只回读被引 chunk（调用者身份、事实平面 `recheck_candidates`），经第二层筛查后用与链路相同的 verifier 判定；不生成文本 | 5.6"每条 claim 的支持状态和来源"；ADR-0011 分工同一套 |
| 结构守卫：`medops.skills` 之外的模块不得 import Skill 实现模块（AST 测试），处理器一律私有名 | INV-AUTH-03"节点不得绕过 Registry 直接调用 Skill"的可测试形式；承认它只挡静态 import，不挡反射 |

## 2. 交付

- `src/medops/domain/skill.py`：`SkillSpec`（name/version 模式、`required_scopes` ≥1、`timeout_s` ≤120、`parallel_safe`、`idempotent`、`version_tag`、`resolve_scopes`）、`SkillStatus`、`SkillOutput`（非 completed 必带 reason code；`rendered_texts()` 供安全第三层）。
- `src/medops/skills/registry.py`：`SkillRegistry.register/get/entries/catalog/version_set/describe/execute/execute_many`、`SkillContext`（身份、版本集、`HarnessDeps`、两个身份内查询端口、trace/run id）、`RegisteredSkill`、`SkillRun`（输出、attempts、operation key、安全结果）。
- `src/medops/skills/label_query.py`、`citation_verification.py`、`catalog.py`（`default_registry()`，目录版本 `skills-v1`）、`production.py`（`evidence_lookup`/`doc_type_lookup`，身份事务内，非 UUID 直接视为未知）。
- `src/medops/safety/checks.py`：`check_output_text(texts, off_label=)`，`check_output` 改为委托（off-label 的 M2-14 说明此前是死分支，现在生效）。
- 测试 26 项：`tests/unit/skills/test_registry.py`（scope 默认拒绝与 `$dept` 解析、scope 先于 Schema、四类 Schema 违规不触达处理器、未知版本、版本集缺失、超时升级与"仅幂等可重试"、输出类型违约、建议性文本被替换为裸升级、`BusinessError` 上抛、`execute_many` 顺序与并行范围、注册与规格约束）、`test_label_query.py`（说明书正向、非说明书文档、链路弃答映射、无 scope 不触发检索、Schema）、`test_citation_verification.py`（支持/矛盾/未知 chunk/注入 chunk 被筛掉、claim 上限）、`test_no_bypass.py`。`make check`：992 项通过。

## 2.1 真实部件运行（`evals/harness/runs/2026-09-23-skill-smoke-v1`，medops_v2 + OpenAI，12 个用例，0.06 美元）

| 用例 | 预期 | 结果 |
| --- | --- | --- |
| `label_query` 正向 ×3（瑪爾胰 / Losacar / 拔痛酸錠 的剂量问题） | completed，原文片段 + 版本化引用 | 2 条 completed（片段与引用来自说明书 chunk）；瑪爾胰一条 `insufficient_evidence`（Verifier 删光陈述）——同一输入重复 3 次：2 次 completed 且陈述相同、1 次删光，是模型侧非确定性（gpt-6 档不接受 temperature，回答与判定逐次可变），方向 fail-closed |
| `label_query` 非说明书主题（PV 用户问 GVP 时限） | insufficient_evidence | ✓ 「answer cites 1 non-label document(s)」——回答引用了指南而非说明书，被事后核对拦下 |
| `label_query` 无 read scope | `forbidden`，零检索 | ✓ `missing=['MA:read']`，模型调用 0 |
| `label_query` Schema 违规（空 product） | `schema_violation` | ✓ 模型调用 0 |
| `citation_verification` 实况陈述 ×3（5 条 claim，来自全量运行已回答样本） | 全部 supported 并给出来源 | ✓ 5/5 supported，来源为被引 chunk（判定模型 gpt-6-sol） |
| `citation_verification` 篡改数值（8 mg → 24 mg） | contradicted / not_supported | ✓ contradicted（「每日最高建議劑量為 8 mg，而非 24 mg」） |
| `citation_verification` 未知 chunk id（全零 UUID、非 UUID） | not_supported + unknown_citations | ✓，模型调用 0 |
| `citation_verification` 跨部门 chunk（MA 用户引用 PV 文档 chunk） | 不可见 → not_supported + unknown_citations | ✓ RLS 下回读为空，模型调用 0 |

- 越权路径（scope、跨部门 chunk）与 Schema 路径均在任何模型调用之前结束；正向路径的费用为每次 0.005–0.02 美元。
- M2-12 的正向 / 失败链路至此在真实部件上各走通一次；据此把 M2-12 记为「已实现」，持久化与 API 接线仍随 M3。

## 3. 发现（登记，不在本切片处理）

- **离线规则路径的适应证极性盲点**：无判定模型时（`rules_first`），`judge_element` 对 indication 要素只做短语包含，不比较否定极性——陈述"Losartan potassium 用於對本項產品任何組成過敏者"对证据"禁用於對本項產品任何組成過敏者"被判 supported。配判定模型的 `polarity_only` 路径由整句极性规则承接（DEC-003 否定翻转 96.4%），生产不受影响；离线工具与单元测试路径受影响。修法明确（indication 分支改用与 `contained()` 相同的对齐窗口极性比较），但会改 `support-rules-v1` 的行为，须升版本号并重跑规则臂（免费）；为不让正在进行的主集全量运行（进程内已加载 v1，看门狗重启会加载新代码）出现混合版本，安排在该运行结束后作为独立小切片处理。
- 检索层没有 `doc_type` 过滤，`label_query` 只能事后核对；进入 M3 检索服务化时应把文档类型过滤下推到 SQL。

## 4. 未做 / 限制

- Skill 运行未持久化（`skills/skill_versions` 表、attempt 落库随 M2-03/M3）；`TaskCreateRequest` 到 Registry 的接线随 M3 API。
- Skill 内的模型调用只受 `BudgetedGateway` 月度上限约束，Skill 级 Token 预算未计量（Answer 链路有 Trace 预算；`citation_verification` 的判定调用数上限由 claim ≤20、每 claim 引用 ≤8 间接限制）。
- 模型侧非确定性：gpt-6 档不接受 temperature 参数，同一输入的回答与判定逐次可变（§2.1 的 1/3 删光）；operation key 账本只保证「同键不重复执行」，不保证跨运行同答。回放对比（M3-08）必须按此解释差异。
- 中风险/高风险三类 Skill（M2-13/14）未开始；M2-14 的"只做文档范围核验"已有安全第三层的 off-label 分支作为前置。

## 5. 自审（§9）

- 不可达性：Answer 节点与 Skill 输出都必须过 `check_output_text`；Skill 处理器私有、外部 import 由 AST 测试守住；scope 检查在任何 I/O 之前（测试证明无 scope 时检索请求为零）。
- 契约：Skill 输入/输出均为 Pydantic 模型（INV-HAR-01），`describe()` 输出 JSON Schema 供 API 契约（M3）复用；版本进入 `VersionSet.skill_version_set` 与 operation key。
- 未改变已冻结数据与评测结果；未触碰 `.env`、数据库写路径；无新增依赖。

## 6. 进度

- M2-11 已实现；M2-12 在 §2.1 真实部件运行后记为已实现（2026-09-23 17:30，此前为部分）。P0 加权进度 43.7%（34.5/79）；按 99 项计 34.8%。分项：M0 10/11、M1 16.5/21、M2 8/16、M3 0/13、M4 0/10、M5 0/8。
