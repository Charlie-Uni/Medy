# ADR-0010：DEC-009 运行时 LLM 托管与数据传输边界

- 日期：2026-09-23
- 状态：已决（决策人 2026-09-23："厂商用 openai 上限 30 刀美元 看情况调整"）
- 决策来源：[实现记录 51](../reviews/2026-09-22-implementation-51-main-set-freeze-and-e2e.md) §1；基线 2.4（INV-HAR-04/05/08）、5.7（Model Gateway）、§10 DEC-009；ADR-0007 已把 embedding 与 reranker 固定为本地推理，本 ADR 只决定 LLM 部分。

## 决策

1. **运行时 LLM 走 OpenAI API（platform.openai.com）**，按量计费、预充值。M2 Harness 的 Intent、Answer、Verifier 节点及端到端评测中的这三类调用都经此路径；不使用任何订阅制 CLI（Claude Code、Codex）作为运行时或评测链路的一部分。
2. **月度上限 30 美元**，决策人视情况调整。上限在两处生效：OpenAI 控制台的用量硬限额（由决策人设置），以及 Model Gateway 的本地账本（M2-06 实现：按 `usage` 累计当月美元开销，达到 `LLM_MONTHLY_BUDGET_USD` 后拒绝新调用并升级，不静默降级）。INV-HAR-08 的单 Trace 预算另行设置，不与月上限混用。
3. **数据边界**：发往 OpenAI 的内容只有：用户查询（M2 前为合成查询）、已回查证据的文本片段（全部来自 ADR-0003 准入的公开文档）、系统提示。不发送身份信息（INV-OBS-02 的化名不进入提示）、不发送整份文档、不发送数据库标识以外的内部对象。OpenAI API 默认不用客户数据训练；Gateway 记录每次调用的 `model`、`system_fingerprint`（如返回）、token 用量与费用到 Trace（INV-HAR-05）。
4. **模型 ID 固定**：生产只使用带明确 ID 的稳定模型，preview 模型只可用于实验。候选：Answer `gpt-6-sol`（$2/$10 每百万 token）；Verifier 从 `gpt-6-luna`（$0.10/$0.50）起试，`gpt-5.4-mini`、`gpt-6-sol` 为升级档；最终 ID 由 DEC-003 实验（ADR-0011 待写）按切片准确率、格式合规率、延迟与费用选定，选定后写入 `VersionSet` 与 `retrieval_version` 同级的策略版本。
5. **离线数据工作继续走订阅**：评测集起草与 LLM 复核使用 Claude Code（Max）与 Codex（ChatGPT）CLI，消耗套餐额度、不计入本上限；起草者与复核者不得同源（spec-v1.1 §8.1），M2-15 安全集若由一家起草则由另一家复核。
6. **Gateway 抽象不绑定厂商**：`medops.infrastructure.llm` 提供 `ModelGateway` Protocol（超时、重试、并发上限、取消传播、预算、版本元数据）与 OpenAI 适配器；领域模型不得 import 厂商 SDK（基线 4.1）。测试使用 fake provider；Anthropic / Gemini 适配器在需要对比或迁移时再加，不在 M2-01/02 范围。

## 依据

- 三家官方价目（2026-09-23 查证）：OpenAI `gpt-6-luna` $0.10/$0.50、`gpt-6-sol` $2/$10、`gpt-6-astra` $10/$50；Anthropic Haiku 4.5 $1/$5、Sonnet 5 $2/$10、Opus 5 $5/$25；Gemini 3.5 Flash-Lite $0.30/$2.50、3.8 Flash $0.75/$3.75。按主集一次端到端（614 条 × Answer + Verifier ≈ 6k 输入 / 600 输出 token）折算：luna 约 $0.6、sol 约 $11、Haiku 4.5 约 $5.5、Sonnet 5 约 $11。M2 期间约 15 次等量调用，30 美元上限在 Verifier 用 luna、Answer 用 sol 的组合下可覆盖，全部用 sol 则需分批或提高上限。
- 订阅 CLI 不能作运行时：两家消费者条款只允许开发者交互式使用；CLI 子进程也满足不了 INV-HAR-04 的超时、并发与取消传播要求。
- 未选 Anthropic API：价格与 OpenAI 同档相当，决策人选择 OpenAI；已有 ChatGPT 订阅账号便于同一结算主体管理。未选 Gemini 作主厂商：付费层条款合规，但稳定 ID 换代快（3.5→3.8 Flash 数月内并列，2.5 系列已限访问，Pro 仅 preview），与固定模型 ID 的要求冲突；可作为 DEC-003 实验臂。

## 后果

- `Settings` 新增 `openai_api_key`（SecretStr，可空）与 `llm_monthly_budget_usd`（默认 30）；`.env.example` 登记键名；key 由决策人在控制台创建并放入本机 `.env`，不进 Git、不进日志、不进聊天。
- 依赖锁在 M2-02 加入 OpenAI 官方 Python SDK（带哈希锁定）；在此之前不新增依赖。
- 每次端到端评测在 run_manifest 记录实际费用；月账本在 `docs/reviews` 的阶段记录中报告。
- 若上限调整或换厂商，修订本 ADR 并记录日期与原因；换厂商必须重跑 M2-16 门禁。
