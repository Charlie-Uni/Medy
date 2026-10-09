# 记录 158：EVAL-12 裁判校准准备与单次运行预算

日期：2026-10-09。状态：**零费用准备与自审完成；等待真实回答生成的单独付费授权。**

## 1. 目标

EVAL-12 要校准 `answer-quality-v1-provisional` 的 claim 支持、citation 支持和答案完整性判断。记录 136 已有快照和汇总协议，但仓库没有任何真实 `answer_review_inputs`；旧运行无法可靠恢复当时的逐句引用关系。因此不能直接拿旧答案补造校准结果，必须先对新版冻结集产生一小批真实回答和授权证据快照。

本轮只做选择、绑定、提示/解析及预算保护，不调用模型、不生成质量分数，也不把模型当第二人工。

## 2. 十题校准面板

新增 `evals/answer_quality/calibration-v1-plan.json`，绑定：

- `main-v5-provisional` dataset hash `23bf8530…842b0` 和 samples 文件哈希；
- 当前 rubric 版本与文件 SHA-256；
- 每道题完整 sample SHA-256、部门、语言、gold 组数、选择维度和原因；
- 生成、复核的模型范围、费用上限、次数及停止条件。

| 样本 | 主要校准点 |
| --- | --- |
| `ms-0012` | 问题条件改变适用剂量；历史裁判误判 |
| `ms-0056` | 点名产品与时间窗 |
| `ms-0149` | E2B(R2) 与已裁决等价载体、重复报告否定语义 |
| `ms-0177` | may/if 条件式与时限；历史裁判误判 |
| `ms-0227` | 问题已给前提时答案可省略该前提；历史裁判误判 |
| `ms-0242` | 英文、点名 FDA 版本、三个共同必需示例 |
| `ms-0298` | 两个共同必需例外、否定、点名版本 |
| `ms-0338` | FDA 宿主文件讨论 ICH/ISO 引用，不能错换来源 |
| `ms-0440` | long context、版本冲突、五个共同必需 gold |
| `pc-0068` | 两份 ICH 文件的关系陈述 |

这是有目的的开发集校准面板，用于暴露 rubric/裁判失效模式；不是随机抽样、未见集或总体准确率估计。计划文件 SHA-256 为 `9ca4342e…d05bb`。

## 3. 两阶段付费边界

### 第一阶段：真实回答和快照

精确命令将使用 `smoke_ask.py --released --dataset main-v5-provisional --ids <上述十题> --max-cost-usd 0.35`。完成条件：

- 10 道均有持久行；系统故障会保留费用并可恢复；
- 至少 8 道得到 answered，且全部行的 exact review snapshot 完整；
- 运行条件和事实摘要通过记录 157 的开始、周期和终检；
- 费用上限 0.35 USD，调用前预留；达到上限退出 77，不继续下一次调用。

### 第二阶段：独立模型意见

第一阶段完成后才能取得实际 `case_sha256` 和提示哈希。届时另生成精确授权请求，再请用户单独批准。当前计划为 Claude Opus 5/high、每 case 一次、最多 10 次、每次 0.30 USD、总上限 3.00 USD；首个失败、未知费用或无法通过结构校验的回复立即停止。

该 3.00 USD 只是后续计划，不由本轮或第一阶段授权自动批准。

## 4. 单次 API 运行硬上限

`BudgetedGateway` 新增可选 `run_cap_usd`：

1. 每个 provider call 前按固定价格表、完整输入估算和最大输出 Token 预留最坏费用；
2. 同一进程并发调用共享预留额，避免并发穿透；
3. provider 成功按实际费用结算；provider 失败按最坏预留结算；
4. 下一次调用会超过上限时，在接触 provider 前抛 `BudgetExceeded`；
5. 月度 PostgreSQL 总账继续独立生效。

`MeteredGateway` 现在会把 provider 失败后已入账的最坏费用纳入运行计量。主集、安全集和回放 runner 接受/使用本次上限；费用阻断时先保存当前尝试、强制事实终检，再以 77 退出供新授权后恢复。默认未传上限时，API/服务行为不变。

月度账本现场读取为 0/30 USD，但这只说明当前数据库账本容量，不构成本次模型调用授权，也不代表外部供应商余额。

## 5. 模型裁判输入保护

新增并测试单 case 模型提示和回复装配：

- query、answer、逐句 citation links、实际授权 evidence、文档身份和全部 gold 一次性提供；
- 明确把问题和证据视为不可信数据，工具关闭；
- 模型只返回 claims/citations/completeness 三段，不允许自报 reviewer、case hash 或人工身份；
- reviewer/model/prompt hash/`independent_second_human=false` 由可信调用方写入；
- claim/citation 索引、完整覆盖、非空理由、rubric 和 case hash 再由现有 validator 校验。

真实调用 runner 和第二阶段预算授权将在第一阶段产生 exact case 后绑定；本轮没有生成伪 verdict。

## 6. 实现中遇到的问题

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| runner 定向测试最初 2 项失败：mock `build_budgeted_gateway` 不接受 `run_cap_usd` | 测试替身仍是旧签名 | 测试替身接受关键字并显式暴露 `run_cap_blocked=false`；复跑 16/16 通过 |
| 首次读取月度账本时 `Settings` 报 `debug` 无法解析布尔值 | 当前 shell 注入了不合法的 `DEBUG`，与项目 `make check` 一直使用的清理方式相同 | 用 `env -u DEBUG` 执行只读查询；没有修改 `.env` 或隐藏错误 |
| 修改 rubric 后计划校验失败风险 | 计划绑定 rubric 文件哈希，文档变化会使旧哈希失效 | 文档定稿后重算计划哈希并重新运行 plan validator |

## 7. 验证与自审

- 校准计划校验：10/10 样本、dataset、sample、rubric、费用范围与 reviewer 身份绑定通过；
- 定向：51 passed；ruff 与目标 mypy 通过；
- `env -u DEBUG -u PYTHONPATH make check`：**1709 passed、70 skipped、1 条既有短 HMAC key warning**；ruff、436 个文件格式、188 个源文件 mypy、评测审计和 schema 漂移通过；
- 评测审计仍为四项既有警告；本轮没有缩小第二人工或未见集缺口；
- 模型调用 0，新增费用 0 USD。

| 自审项 | 结论 |
| --- | --- |
| 需求与范围 | 通过。只准备裁判校准和费用边界；未改 rubric verdict 含义、正式门槛或数据。 |
| 正确性与失败路径 | 通过。并发预留、成功、provider 失败、调用前拒绝、runner 恢复均有测试。 |
| 权限与可追溯性 | 通过。计划绑定冻结输入；正文仍只在忽略目录；模型不能自报可信身份。 |
| 验证 | 准备范围通过。没有真实回答或模型意见，因此 EVAL-12 仍为 PAID。 |
| 状态与文档 | 通过。第一阶段 0.35 USD 与后续最多 3.00 USD 分开，不用月度余额替代授权。 |
