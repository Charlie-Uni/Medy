# 决策人英文孪生审校稿（2026-09-20 提交，回复“修改好了”）

决策人基于 32 条中文父问题与 8 份指定 PDF 审校英文孪生：9 条优先修改、7 条小幅调整、16 条保留。修订英文已代入 `twins_queries.json` 与 `samples_draft_EN.json`（pc-0105 因 300 字符上限由起草者缩短 10 字符，问句未变）。审校稿同时提出以下冻结前须核对的标注问题及起草者据实核对结果：

| 审校稿要点 | 核对结果（起草者，2026-09-20） |
| --- | --- |
| key_text 在 120 字符处截断，疑为展示截断 | 确认为表格预览截断；底层 key_text 完整（例如 pc-0087 父样本 pc-0052 的 key_text 为 200 字符，evidence_span 307 字符含“不应视为 AE/ADR 同义词”）。表头已改为“key_text（预览）”并加省略号。 |
| 五条样本 evidence_span 是否完整覆盖问点 | 逐条核对父样本 span：pc-0092 含研究程序与评估的科学必要性及不过度负担；pc-0095 含 study conduct、participant safety、study reporting 三项；pc-0099 含 sponsors and investigators 与 applicable regulatory requirements；pc-0102 含 documented procedures 至 correspondence 的例子列表；pc-0087 见上行。 |
| pc-0086 页内存在等价证据句 | 属实。探针规范为每条样本一个 required gold，命中以锚定条款为准；等价句不计为命中也不计为错误证据。作为已知限制记录，不改 gold。 |
| 原始抽取断词与行号混入 key_text | 按 SPEC 第 4 节，偏移与 key_text 以抽取页文本为坐标系，行号是页文本的一部分；命中判定不依赖可读性。不单独修改孪生 gold。 |
| 切片口径 | 孪生按 SPEC 5.1 继承父样本切片；语言以 `language=en` 字段区分。protocol_id 对指南的口径见记录 22：指南用 ICH 编号、CFR 条款号或章节号。本次不改标签。 |
| 标题截断 | 展示截断，完整标题在 corpus.json。 |

本稿不是第二复核结论；LLM 第二复核由 reviewer-llm-02（claude-opus-5）执行并另存证据。
