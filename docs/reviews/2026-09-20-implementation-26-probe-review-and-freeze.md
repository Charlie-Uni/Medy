# 实现记录 26：最后三项裁决与探针本地冻结

日期：2026-09-20。用户在记录 25 的三项具体提案之后回复“可以 继续”。承接为：pc-0052 采用旧术语使用场景及 200 字符锚点；pc-0066 采用费用报销场景；pc-0074 保留已逐字验证的 [940,1125) 坐标，记录人工裁决。此前 pc-0026/0027/0038 的决定继续有效。

## 1. 编码前记录

- 目标：落实两条改题并重新独立复核；绑定 pc-0074 人工裁决；处理已有人工依据的机构邮箱误报；诚实表达后端模型版本未暴露的运行条件；完成可达到的正式装配与冻结校验。
- 不变量：INV-EVAL-01/02、norm-v1 与页内连续原文、完整 review 输入绑定、PII 默认拒绝与逐项可审计裁决、冻结文件不可静默修改。
- 验收：批准前后差异精确；修改后旧判定不可复用；新 query/key 唯一与偏移正确；PII 例外只能放行已确认的确切命中，错配/过期/额外字段仍失败；缺失后端版本不得伪装成 CLI 版本或固定快照；完整带页文本校验及本地测试真实运行。
- 分工：主线程处理样本、实际重审、装配和最终文档；独立实现线程处理 PR-07 的最小可审计例外与反例测试；另一独立线程先核查模型记录与冻结边界，再实现运行证据校验并交叉审查。每轮按工程基线 §9 自审。
- Git：保留全部既有工作区修改，不默认将大量历史未提交工作一并提交；若形成冻结候选，明确本地校验与 Git/ADR 完整封存的区别。

## 2. 执行与逐轮自审

### 第一轮：批准事项落地

1. 需求：两条采用已呈精确提案，pc-0074 原内容不变并绑定新人工裁决；没有重复请求确认。
2. 逻辑：修改前状态归档；使用构建器临时重建并逐字段比较目标；旧判定在真实重审前失效。
3. 安全：原始页文本仍仅位于忽略的输入包；当前变更不涉及实际患者数据。
4. 契约：pc-0052 key 长 200 字符，连续且唯一；pc-0066 仅改 query；全部 span、标签与批准范围一致。
5. 测试：两条重建、输入打包和实际逐条 gpt-6-astra / high 重审通过，报告 Token 分别 2,986 和 2,952。
6. 可观测性：批准原话、修改前后值与旧判定哈希写入 approved_final_changes_2026-09-20.json；两条新判定均为 agree。
7. 简洁性：复用构建和重审工具，没有扩展题库。
8. 验证：当前 71 agree、4 disputed_resolved；四条裁决均对应真实批准与当前判定，已装配 75 条正式 samples.jsonl。
9. Checklist：此时仅完成语义复核与装配，冻结检查另报。

### 第二轮：精确例外与诚实运行记录

1. 需求：机构邮箱沿用记录 21 已有人工决定；model_version 明示服务别名与未暴露后端，未声称固定快照。
2. 逻辑：PII 例外绑定样本/gold/来源/字段/字段哈希/确切匹配和位置；query、notes、其他邮箱及非邮箱规则不开放例外。
3. 安全：人工依据文件真实存在且哈希匹配；过期、重复、跨样本或跨字段、未消费例外均拒绝。错误日志不回显非法输入值。PII 检测规则本身保持 pii-rules-v1。
4. 契约：新增 pii_exceptions Schema 与 manifest.review_provenance。例外文件纳入 SHA256SUMS；8 个运行证据通过 manifest 文件哈希传递绑定，dataset_hash 计算公式不变；review_prompt 字节未改。
5. 测试：新增 55 项 PII 正反测试、模型元数据与来源校验测试；实际 75 条带页文本 draft 校验为 0 errors / 0 warnings。
6. 可观测性：正式目录包含 8 个运行证据快照，不再引用会继续变化的 drafts 作为冻结证明；运行元数据由真实记录派生，拒绝任意 CLI 版本参数冒充后端。
7. 简洁性：只增加当前需要的公开机构邮箱逐项裁决，没有按域名或 corpus notes 自动豁免。
8. 验证：临时冻结候选完整 frozen 校验通过，16 份源文件 SHA-256/大小重新验证；正式冻结发布前仍执行完整代码测试及交叉审查。
9. Checklist：仅当正式冻结目录校验通过才更新本地冻结状态；Git 完整归档与实验选择保持单列。

### 第三轮：交叉审查、修复与正式验证

1. 需求：审查只针对复核证据可被错误复用或替换的风险；没有变更实验候选、质量阈值、gold 或批准范围。
2. 逻辑：发现 latest 指针可回退旧 agree、隐藏后追加的 dispute；runner 与 PR-09 改为强制引用 append 顺序最后一次调用，后续空 verdict 也不能借旧结果通过。另发现 assembler 验证后再次读取草稿的并发修改窗口；现缓存首次读取且已验证的样本，装配同一个快照。
3. 安全：回退、删改证据、伪造元数据及裁决错配均默认拒绝；运行证据路径限定在版本目录内，外部人工依据仍逐次验哈希。未扩展个人数据例外，也未引入真实患者数据。
4. 契约：PR-09 独立重建样本输入及实际组合提示，检查历史最新调用、verdict 镜像和人工裁决绑定；新 Schema 与 SPEC 一致，未修改数据库、API 或错误码契约。模型服务别名不宣称后端快照已固定。
5. 测试：新增 runner 指针回退反例、两项运行证据历史反例与 assembler 实际并发修改回归。第一遍 478 passed 属于修复前记录；修复后完整复跑为 **482 passed（418 单元 + 64 PostgreSQL 集成，无跳过）**，以后者为最终证据。
6. 可观测性：当前 75 条均有输入和判定哈希；正式 profile 共 130 次成功复核调用，本轮新增两次报告 Token 合计 5,938。8 件运行证据、冻结校验报告、dataset_hash 和独立 manifest SHA-256 均已留存。
7. 简洁性：复用已有 runner、装配器与 PR-09 入口，仅增加必要的绑定和反例；没有新增依赖或另造标注平台。
8. 验证：仓库外导入、ruff、106 文件格式、mypy 47 个源文件、482 项测试及 Schema 漂移检查全部通过。16 份原件 SHA-256/大小、4 项 SHA256SUMS 条目和正式带页文本 frozen 校验通过；独立线程再次重算哈希并核对 75 条冻结业务内容与当前草稿一致。
9. Checklist：75 条已本地冻结，Git 归档与实际 commit 回填尚未完成，M1-01 保持“部分”；P0 加权进度仍为 22.8%（18/79），基线 99 项复选项仍未勾选。没有把测试通过写成检索质量已达标。

## 3. 本地冻结结果

正式目录：[v1](../../evals/probe/precise_clause/v1/)。发布前在临时目录构造并验证 frozen 候选；完整代码检查通过后核对正式输入未变，再发布 SHA256SUMS 和 frozen manifest。正式目录校验为 **0 errors / 0 warnings**，当前内容不再原地修改。

| 项目 | 结果 |
| --- | --- |
| dataset_version / frozen_at | `v1` / `2026-09-20` |
| 文档 / 样本 | 16 / 75；MA 30、PV 29、CO 16；zh-Hans gold 10 |
| 最终复核 | 71 agreed、4 disputed_resolved、0 待决 |
| dataset_hash | `5561bee58e37cd8d86b756f17e6c1a6ebed32ba54ba2ac48f4cd4adee254db7e` |
| manifest.json SHA-256 | `062f9a536e0d811306f80dd5c24cc44f40a39a8f36ac360959c4de99b1faf54b` |
| PII 例外 | 1 条；pc-0046 的公开机构邮箱，沿用记录 21 人工依据并绑定确切字段、位置及哈希 |
| model_version | `service-alias:gpt-6-astra;backend-version:not-exposed`；effort `high`，CLI 版本另存 |
| Git 归档 commit | 尚未生成；现有 HEAD 不代表本次冻结提交 |

运行证据由 manifest 中的逐文件哈希绑定；归档须同时保留 dataset_hash 和 manifest SHA-256。后端模型版本未暴露，保存本次真实输入、输出与运行记录可以审计本次判断，不能保证再次请求得到同一后端。

证据入口：[最终批准落地](../../evals/probe/precise_clause/drafts/v1/review/approved_final_changes_2026-09-20.json)、[当前复核审计](../../evals/probe/precise_clause/drafts/v1/review/formal_review_audit.json)、[正式 frozen 校验](../../evals/probe/precise_clause/drafts/v1/review/frozen_validation_2026-09-20.json)、[本地冻结摘要](../../evals/probe/precise_clause/drafts/v1/review/local_freeze_summary_2026-09-20.json)、[ADR-0002](../adr/ADR-0002-lexical-retrieval-selection.md)。历史记录 24、25 保留当时状态，当前处理以[复核与冻结状态](../../evals/probe/precise_clause/drafts/v1/review/current_review_disposition.md)为准。

## 4. 验证与下一步

- 完整软件检查：`env -u DEBUG -u PYTHONPATH make check`，482 passed；继承的 DEBUG 不是合法布尔值，仅在子进程移除；集成测试实际连库执行。
- 冻结复验：`env -u DEBUG -u PYTHONPATH make validate-probe DIR=evals/probe/precise_clause/v1 MODE=frozen PAGES=evals/probe/precise_clause/v1/pages`，75 条通过、零错误、零警告；另重算 SHA256SUMS 和 manifest 哈希。
- 文档同步：README、路线图、知识对照、当前复核状态与 ADR 已更新；保留 M1-01 部分完成和 Git 归档待办。`env -u DEBUG -u PYTHONPATH venv/bin/python -m pytest -q tests/unit/docs` 为 10 passed；88 个本地链接有效，三份记录中的两组冻结哈希与实文件重算一致，`git diff --check` 通过。
- 下一步：核查未提交工作区的依赖与提交范围，完成冻结材料、校验器及依据的 Git 归档，回填实际 commit；之后固定 DEC-001 实验清单和候选版本，再开展实验。M1-11 发布事务可独立推进。
- 知识确认：已追加 manifest 独立哈希的问题，等待学习者解释，不以未回答阻塞已授权工作，也不记为已掌握。
