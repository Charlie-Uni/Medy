# 实现记录 80：M4-B——Reflect 归因（M4-02）、Adapt 候选 diff 与线上只读 released（M4-03）、knowledge_gap 工单（M4-05）

- 日期：2026-09-25
- 授权：记录 74 C（DEC-014，决策人 2026-09-25「同意」）：M4-A 之后是 M4-B
- 范围：迁移 0017、`medops.loop.reflect` / `adapt` / `tickets`、`medops.application.policy_loader`、生产运行时（API 与 MCP）按 released 指针加载策略、发布路由的目标守卫与新错误码、测试、文档
- 费用：0（全部确定性；没有模型调用）

## 1. 决定与依据

| 决定 | 依据 |
| --- | --- |
| Reflect 第一遍是**规则**归因（`attributed_by='rules'`，0017 放宽枚举）：安全标记 → safety 0.9；`intent_unclear` → intent 0.8；被点踩的高风险拒答 → intent 0.6（疑似过度拒答）；人工判「误报」的升级 → generation 0.7；Verifier 失败 → generation 0.7；人工确认的证据不足 → knowledge_gap 0.8；证据不足且**什么都没检索到** → knowledge_gap 0.7；证据不足但有候选 → retrieval 0.5；回放漂移 → generation 0.5；只有用户不同意 → generation 0.4；其余留给人 | 记录 74 C「复用 reason code 与检索上限复查的分类」；规则可解释、零费用、每条置信是规则特异性的固定值而不是概率；模型归因随后可加，人工修正永远覆盖 |
| 人工修正入口 = `bad_cases.human_override`（管理角色）+ CLI `reflect correct`；`effective_attribution()` 让覆盖优先于规则 | M4-02「带置信与人工修正入口」；0016 的触发器已经限定只有管理角色能写该列 |
| Adapt 只产**结构化 diff 候选**：允许的种类 prompt / rule / skill / retrieval_params，diff 形状写死并校验（retrieval_params 是 `{参数: {from, to}}` 且 `from` 必须等于当前生效值；prompt 是 `{text, text_sha256}`；rule 只能 `{add: [pattern…]}` 且可编译；skill 是 `{params}`）；候选经 Loop 角色写入 `policies`（只能是 candidate） | 基线 5.8「Adapt 只能创建结构化 diff 候选」；M4-03「不改 released」；记录 75 的状态机负责其后的一切 |
| 机械可推导的 diff 只有一种：通道 k 低于基线上限 20 时提到 20。当前生产配置已在上限（20/20/融合 20/重排 8），所以 `propose` 对 retrieval 簇报 `needs_author`；prompt / rule 内容也需要作者（人，或以后的模型遍） | 基线 4.4 / `HybridConfig` 把通道 k 与融合上限钉在 20；没有 LLM 时凭空生成正则或提示词不诚实。Adapt 的价值是簇 + 证据 + 校验 + 隔离，而不是编内容 |
| 隔离（INV-EVAL-01）在写入前强制：候选的 diff / evidence / name 里出现 `rp-` / `rs-` / `ms-` / `pc-` / `ss-` 编号，或任何字符串等于回放集问题文本，一律拒绝；evidence 必须列出 case id | 记录 79 只声明了规则，本记录把执行点放进 `submit()` |
| **生产读 released**：`policy_loader.load_released()` 在进程启动时读 `released_policies ⋈ policies`，把能应用的 diff 叠到常量上——`retrieval_params/hybrid`（通道 k、rrf_k、融合上限、重排输出）与 `prompt/answer_system`（回答节点系统提示，带 sha256 校验）；仓库常量是「released v0」。应用了什么写进版本集：`policy_version` 追加 `+rel:<8 位 id>`，提示覆盖改 `model_config_version`（`;prompt=<sha8>`），检索覆盖重算复合 `retrieval_version` | INV-HAR-06 / M4-03「线上只读 released，生产来源不是仓库最新 Prompt 明文」；基线 3.6 只有复合版本进缓存键 |
| API 与 MCP 用同一份 released 检索策略（MCP 用只读角色读指针） | 否则 `/v1/ask` 与 MCP `search_documents` 会在一次发布后分叉 |
| 发布路由新增守卫：`(kind, name)` 不在加载器支持集内 → `409 policy_target_unsupported`（新错误码）。rule / skill 候选可以创建、可以批准，但在运行时学会应用之前不能发布 | 「可发布」必须等于「生产会应用」，否则指针切了而行为不变是最坏的假发布 |
| knowledge_gap 只建 `document_requests` 工单：问题（≤ 500 字）+ 一行缺口描述；没有任何能放答案的字段；Loop 只能建，管理角色处理（accepted / rejected / fulfilled，可关联补上的文档），关闭即终态 | 基线 5.8「不能生成事实」、308「开发环境可用内部工单记录」 |

## 2. 交付

- 迁移 0017（本地两库已升级）：`attributed_by` 增加 `rules`；`document_requests` + `medops_document_request_guard`（内容不可改、只有管理角色能处理、关闭即终态）+ FORCE RLS + 授权；DOWN 全部回收。
- `medops.loop.reflect`（规则表、`reflect()`、`correct()`、CLI `run | correct`）、`medops.loop.adapt`（`propose()`、`Candidate` / `validate_candidate()` / `check_isolation()` / `submit()`、CLI `propose | submit`）、`medops.loop.tickets`（`build_ticket()` / `open_tickets()`、CLI）。
- `medops.application.policy_loader`（`ReleasedPolicySet`、`load_released()`、`validate_diff()`、`SUPPORTED_RELEASE_TARGETS`）；`ProductionRuntime.from_settings` 与 `medops.mcp.serve` 启动时加载并应用；`HarnessDeps.answer_system`；`production_retrieval_inputs(config, rerank_output)` 参数化；`PolicyService.release` 目标守卫；错误码 `policy_target_unsupported`（409，domain）。
- 测试：单元 `tests/unit/loop/test_reflect.py`（14 行规则表 + 覆盖载荷）、`test_adapt.py`（分簇 / 最小支持 / 自动 diff、11 类拒绝、隔离扫描）、`test_tickets.py`、`tests/unit/application/test_policy_loader.py`（叠加与上限、提示哈希、版本串、各类 diff 校验）、`test_admin_routes.py` 新增「不支持的发布目标 409」；集成 `tests/integration/test_loop_pipeline.py`（真实角色：Reflect 归因 7 例 → 人工覆盖 → 工单 3 张且 Loop 不能处理、管理角色处理且关闭即终态、应用角色看不到 → Adapt 提案 + 提交候选 + 隔离拒绝 + Loop 不能发布 → 审批人批准并发布 → 应用角色的加载器得到 rrf_k 40 与 `+rel:` 版本 → 回滚后恢复）；迁移 / RLS 期望更新。

## 3. 未做 / 限制

- Reflect 没有模型遍；「检索上限复查」在无 gold 的真实 Trace 上退化为「有没有检索到候选」，置信 0.5 明确标为需要人看。
- Adapt 生成不了 prompt / rule 的内容；rule / skill 候选能建不能发（守卫），运行时对规则表的叠加（意图规则追加模式、支持规则限值短语）是登记的后续。
- `escalations.resolution` 与工单处理仍是 SQL / CLI 路径，没有管理 API（随 M4-09 审批契约）。
- 加载器只在进程启动时读一次；发布后要滚动重启（灰度 ≤ 10% 的实现随 M4-09）。
- 候选评测（三次运行 + 配对 bootstrap）与门禁计算是 M4-D；`gate_passed` 仍是记录 75 的占位。

## 4. 自审（§9）

- 权限：Loop 用户在真实 RLS 下证明「能建候选、不能发布、不能处理工单、不能写人工覆盖」；应用用户看不到案例与工单。
- 隔离：拒绝测试覆盖编号与问题文本两条路径；集成测试里一条含 `rp-0001` 的 prompt 候选被拒。
- 版本诚实：发布后 `policy_version`、`retrieval_version`（复合重算）、`model_config_version`（提示哈希）三处都变；回滚后加载器回到空集。
- 费用 0；`make check` 通过。

## 5. 进度

- M4-02、M4-03、M4-05 → **已实现**（限制见 §3）。
- P0 加权进度 63.3% → **67.1%**（53/79）；按 99 项计 53.5%；M4 5/10。
