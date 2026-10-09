# 记录 130 既有裁决落为标注修订草案

日期：2026-10-08，Australia/Sydney。承接记录 129，用户回复“可以 开始修改”。本轮目标为落实 13 道 query/gold 修订题；授权范围内同步其英文孪生题、核查原文和映射、修正文档入口。所有写入均在草案与工具层，没有更新生产策略、数据库事实或冻结目录。

## 1. 可审阅结果

主入口：[标注修订草案 v1](../../evals/main_set/drafts/revision-2026-10-08/README.md)。含完整的新旧 query、37 个 gold 的原文、物理页码、norm-v1 偏移、对应 chunk ID、选择理由和下一步。

- [proposals.json](../../evals/main_set/drafts/revision-2026-10-08/proposals.json)：18 条结构化修订；13 道原清单题，加 5 道英文孪生题。原样本以 canonical SHA-256 绑定，修订后的 `after` 不含旧 `review`，三类复核状态均明确 pending。
- [chunk_mapping.preview.json](../../evals/main_set/drafts/revision-2026-10-08/chunk_mapping.preview.json)：37 个证据单元，37 mapped、0 unmappable，组内任选、组间全需。
- [corpus_edits.json](../../evals/main_set/drafts/revision-2026-10-08/corpus_edits.json)：一项拟议标题修正，有封面页依据；不直接修改旧 corpus。
- [manifest.json](../../evals/main_set/drafts/revision-2026-10-08/manifest.json)：状态 draft，基线/原裁决/输出哈希，明确 freeze_ready=false。本包是修订提案，不能作为正式冻结数据交给运行器。

## 2. 逐类修改

| 原题/关联题 | 修改 | 依据与注意事项 |
| --- | --- | --- |
| ms-0241、ms-0242 | 问题明确 FDA 2025 年 12 月研究者安全报告指南；gold 拆为 3 组 | 旧表允许明确指南身份；原页进一步显示示例和汇总分析补充跨三个块，仅命中导语不能证明完整覆盖。新增分组细化仍需复核 |
| ms-0280 | 明确 MedDRA《数据检索和展示：考虑要点》3.26（2026-03） | 保留原事实，不把一般 MedDRA 问题隐式绑定某指南 |
| ms-0298、ms-0299 | 明确 FDA 2025-09《E6(R3) Good Clinical Practice》 | 沿用原裁决“明确问 FDA 版”的选项，没有把 FDA 转载冒称 ICH 原件 |
| ms-0298 | 将横跨两个 chunk 的 key 拆为两项例外，各有短锚点，保留共同上下文 | 原来属于 7 条 unmappable。两组证据共同支撑完整列举，不表示两种例外要同时发生 |
| ms-0336、ms-0337 | 明确 FDA 2013-08 风险监查指南对 §312.50 的引述，问题限于原文两项职责 | 英文旧题已经提及 FDA，仍同步明确文件全名、范围，并重新检查成对一致性 |
| pc-0017、pc-0028、pc-0029 | 点明穩壓/胃所樂的具体仿单，新增 drug_name_zh 标签 | 仅形成探针新版本草案，不能改完继续伪装为逐字导入 probe v2 |
| ms-0177、ms-0178 | 写明“若选择请求”，保留 30 天事实并明确 Module VIII 来源 | 防止 may 的可选性和条件式期限被当作矛盾，也不能把可选请求改成强制要求 |
| ms-0124、ms-0125 | 4 个共同必需单元：分级原则、critical、major、minor | 映射与原裁决四块完全一致 |
| ms-0205、ms-0206 | 4 个共同必需单元：4.8、4.4/4.6、其他 SmPC 节、额外 RMM 说明 | 完整句及条件保留；映射与原裁决四块完全一致 |
| ms-0243、ms-0244 | 2 个共同必需单元：原则与示例，同时明确 FDA 2025-12 来源 | 映射与原裁决两块一致；不把例子块当原则块的替代 |

英文联动新增的五条为 ms-0125、ms-0178、ms-0206、ms-0244、ms-0337；ms-0242 本来就在 13 题内，因此不重复计数。

来源明确后的题目可能比旧宽泛问法更容易检索。修订前后分数不能直接证明系统变好；后续系统对照必须在同一新版本上重新配对运行。

## 3. 原文、数据库和元数据核对

对关联 9 份文档使用只读事务检查当前 `medops_v2`：全部 active，来源哈希、文档版本、部门与冻结 corpus 一致，抽取器/版本/参数一致。1,445 个 chunk 的内容与 norm-v1 原页区间一致，坐标与存档 chunker-v2 快照一致。

为便于复查，本包保留 12 个 gold 页的 94 条 chunk 坐标；另外固定 FDA 封面页哈希。没有导出数据库连接配置或秘密。

FDA `fda-investigator-safety-reporting-2025` 的旧 title 后缀是 September 2021；本地封面写 December 2025，version_label 本来就是 December 2025。修订草案按封面和版本字段写问题，并提出单独的 corpus.title 修正。这是现有原件的元数据一致性修复，不是抓取新文档或重做许可判断。

## 4. 新发现的冻结前缺口

### 4.1 long_context 配额由 23 降为 19

现行 PR-19 的规则是“任一 gold span 超过 1,500 字符或 gold 跨至少两页”，不是同页所有 span 字数相加。拆分 ms-0124/0125、ms-0205/0206 后，每个单元均更短且仍在同页，因此移除四条 long_context 标签。

按修订投影到全量主集，该切片为 19，低于既有 minimum=20。本轮没有扩大 span 或保留错误标签来维持配额；冻结前须补至少一道真正满足原规则的题，并检查同文档配额与新复核。语义上的“多块联合证据”与本项目定义的 long_context 切片应分开报告。

### 4.2 三道探针题须按版本链推进

PR-16 要求主集导入的 pc- 题与被引用的冻结探针逐条一致。不能修改 pc-0017/0028/0029 后继续声称导入 probe v2。顺序为探针修订复核/新冻结 → 主集完整导入新探针 → 主集重新冻结和映射。

本包未创建 probe-v3 或 main-v4 正式目录，意向版本名只描述依赖。没有改动 PR-16 或其他原门槛。

### 4.3 复核记录必须重做输入绑定

旧审批和 verdict 覆盖旧 query/gold。本轮保留原裁决为修改依据，但没有将旧 `agreed` 复制到修订样本。复核者、日期、模型、实际输入/提示哈希必须在新检查实际发生后填写；Codex 的原页核对不登记为第二独立人工。

## 5. 校验工具与验证

新增 `medops.evals.annotation_revision`，复用原样本 schema、norm-v1、冻结完整性与 canonical JSON。仅在草案检查中去掉必填的 `review` 字段并禁止传入旧 review；正式 schema 和冻结流程没有放宽。

检查内容包括：基线/裁决/文件绑定、全部目标题与英文联动闭包、source/version/部门、gold 偏移、key 唯一定位、按源坐标重算映射、组结构、旧多块裁决、父子 gold/slices 同步、long_context 机械标签。`make eval-check` 已读取目录登记；CI 无页文件时检查结构与关系，本机 `--with-pages` 追加原页检查。

```sh
venv/bin/python -m medops.evals.annotation_revision \
  evals/main_set/drafts/revision-2026-10-08 --with-pages \
  --out docs/reviews/2026-10-08-implementation-130-annotation-validation.json
env -u DEBUG make check
```

- 草案原页校验通过：[结果 JSON](2026-10-08-implementation-130-annotation-validation.json)。四套冻结输入及草案整体审计通过：[审计 JSON](2026-10-08-implementation-130-evaluation-audit.json)。
- 新增 14 项测试：携带旧 review、漏改孪生、旧样本 hash 改变、错版本、错偏移、组被打平、旧 long_context 标签、父子切片不同，以及五类真实多组题只引第一组不能通过。
- 针对性测试：37 passed。全量 `make check`：**1374 passed、70 skipped、1 warning**；383 文件格式检查、172 源文件 mypy、包外导入、lint 和 Schema 检查通过。
- 70 跳过项仍为不可达的 B/C 实验服务；既有短 HMAC fixture 警告保留。第一次 lint 提示 E731（lambda 赋值），已改为有名的 `_gold_without_ids` 函数后通过。
- 没有模型 API 调用或费用，没有重跑真实问答质量/容量。远端 CI 未运行；工作区尚未提交或推送。

## 6. 接下来的具体动作

1. 补 long_context 配额并完成修订样本的新复核；明确新增多块细化和来源措辞的判定。
2. 按 probe → main 的顺序组装新版本，重算完整分布与映射，保留全部旧目录。
3. 在同一新数据上修复指定来源行为、校准无答案评分，再做系统对照；不将数据修订收益计为系统优化收益。
4. 第一批仍包括索引完整性就绪与 Langfuse；第二批 BM25、Redis、并发、裁剪；第三批多轮与人工升级业务流程。原加权进度与正式门禁本轮不重计。
