# 进度复核记录 23：当前进度、下一步流程与知识确认

日期：2026-09-19。范围：读取仓库、复跑现有门禁、核对 MA 修改后的草稿与开发库状态，更新 README、路线图、知识对照和草稿入口。未改变基线阈值或任务状态权重；未修改业务代码、样本内容、review_prompt 或用户原始反馈；未提交 Git。

## 1. 当前状态与证据

- Git HEAD 为 `aa5e503`；大量 v0.6 文档与实现仍在未提交工作区。当前进度按工作区判断，不能从提交日志推断所有实现已入版本历史。
- P0 加权进度保持 22.8%（18.0/79），按 99 个基线项计 18.2%；M0 权重 10/11，M1 8/21。基线仍为 0 勾选，最终九项门禁尚未验收。
- 已有领域/API/MCP 契约、工程门禁、迁移 0001～0004、RLS、PDF 入库切分与探针工具；问答服务、运行时 Harness、生产混合检索与 Loop 待实现。
- PostgreSQL、Redis 的 Compose 健康状态均正常。通过只读数据库事务核查：迁移版本 0004、16 份文档全部为 draft、2,661 个 chunk；不表示已发布或可用于线上回答。

## 2. 本轮测试与环境问题

| 验证 | 真实结果 |
| --- | --- |
| `env -u PYTHONPATH make check` | 静态检查和 Schema 检查通过，pytest 298 passed / 64 skipped |
| 集成跳过原因追踪 | 当前进程有继承的 `DEBUG`，Settings 报 `debug / bool_parsing`；fixture 将配置失败解释为没有可用测试 DSN。诊断只输出字段与错误类型，未输出连接串或配置值 |
| `env -u DEBUG -u PYTHONPATH make check` | 仓库外导入通过；ruff 通过；101 文件格式检查通过；mypy 46 个源文件通过；362 passed（298 单元 + 64 集成），Schema 无漂移 |
| 迁移 | `alembic heads` 为单一 `0004 (head)`；全套 pytest 已包含单 head/离线 SQL 与升降级往返用例 |
| 草稿机械检查 | 75 条锚点页内唯一、span 与 norm-v1 页文本区间一致、包含 key_text、部门/版本一致；规范化 query 无重复且不等于任何 key_text |
| 草稿 Schema 检查 | 仅在内存移除 `_draft`；除所有样本缺少 `review` 这一预期缺口外，没有其他样本 Schema 错误；未伪造 review 使检查通过 |

移除 DEBUG 仅作用于验证子进程，使项目 `.env` 生效；未修改用户会话环境或 `.env`。测试 fixture 当前会把配置错误转成 skipped，因此后续应持续核对 skipped，不能只看命令退出码。本轮是流程复核，未扩展为配置加载器或 CI 改造。

未运行：远端 CI、真实 v1 完整 draft/frozen 校验、检索质量/性能实验。本轮不重复声称历史来源哈希、全部链接或许可审核已经重新验证。

## 3. 探针草稿现状

| 项目 | 当前值 |
| --- | --- |
| 样本 / 部门 | 75；MA 30、PV 29、CO 16 |
| 文档 / 部门 | corpus 16；MA 5、PV 8、CO 3；每文档最多 6 条样本 |
| 切片 | time_window 20、drug_name_zh 23、dose_unit 12、mixed_zh_en 55、negation 28、protocol_id 9 |
| gold 文档语言 | zh-Hant 33、zh-Hans 10、en 32 |
| 本地源资料 | 18 份 PDF、18 组页文本；v1 主体 16 份 |
| 已有版本文件 | corpus.json、review_prompt.md 草稿 |
| 尚缺版本文件 | manifest.json、samples.jsonl、SHA256SUMS；未生成冻结 dataset_hash |
| 人工确认 | MA 原始反馈为 23 行修改、7 行 OK；重算后的 23 行待再确认，PV/CO 待确认；正式 review 块尚无 |

MA 调整使 drug_name_zh 从 18 增至 23、negation 从 29 减至 28；其他总数不变。现有草稿总览未同步这两个数，本轮已修正。

机械定位通过不等于内容复核通过。下一轮重点核对：pc-0007 的 query 是否需要明确范围；pc-0017 的限定条件及 `腎+A12` 伪影是否可接受；pc-0027 的 query 已由上轮调整为对应新证据，须由人工确认。这里只登记待审点，未替人工裁决。

已有 review_prompt 将 MA 展开为“药政注册”，而项目基线为“医学事务”；正式复核前应对齐称谓并固定 prompt_hash。本轮没有运行正式 LLM 第二复核，也未修改或冻结 prompt。

## 4. 更新后的执行顺序

1. 按 MA 对照表逐条确认修订，保留原始 7 条 OK 的来源；继续 PV、CO，任何改动重算偏移与分布。
2. 定稿复核提示，记录真实模型标识/版本；独立 LLM 复核，人工裁决争议；将真实记录写入 review 块，装配 manifest/samples，完成 draft 与 frozen 校验。
3. 冻结后执行 M1-02 / DEC-001：预登记候选与环境、构建适配器与 gold 映射、运行全部门禁、形成选型报告。
4. 等待标注反馈时，可独立推进 M1-11 的发布/归档/审计/outbox 同事务切片；索引和缓存消费随组件接入完成，不能提前宣称整项完成。
5. 完成剩余 M1 后推进 M2～M5；领域模型与 M0 基础工具继续复用，不再列成下一轮从零建设。

知识确认入口更新到 TASK_KNOWLEDGE_MAP §10：锚点与证据、规范化与偏移、冻结能证明什么、发布事务与 outbox、词法检索实验。当前未收到学习者回答，掌握程度待确认；这些问题不新增验收门禁。

文档更新后验证：`pytest -q tests/unit/docs` 10 passed；本轮五份更新文档的本地链接目标均存在；`git diff --check` 通过。未新增测试或修改业务行为。
