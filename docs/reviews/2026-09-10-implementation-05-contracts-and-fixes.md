# 实现记录 05：文字纠正与一致性测试、分词器隔离、领域契约与 AgentState（2026-09-10）

按基线第 9 节交付格式。三步按决策顺序执行，每步单独复检，最后跑完整门禁。

## 第一步：文字纠正与机械一致性测试

- 基线 1.3 节“多模态 RAG…仅是 P1 增强项”改为“属于 P2 研究型增强（见 7.2）”，保持 v0.6，不新增 ADR；第七轮记录追加第 8 节更正说明，历史结论不改。
- 新增 `tests/unit/docs/test_baseline_roadmap_consistency.py`：基线各阶段条目数与路线图行数一致；路线图编号唯一且从 01 连续；总数 99 且路线图汇总表数字与基线一致；基线无勾选项。只比对数量与编号，不比对验收文字。
- 复检：`pytest tests/unit/docs` 4 passed。

## 第二步：分词器隔离

- `JiebaTokenizerV1` 改为每实例持有独立 `jieba.Tokenizer`，不再调用模块级 `load_userdict/cut`。
- 回归：`test_instances_with_different_dictionaries_do_not_pollute_each_other`（不同词典实例互不污染、版本号不同）、`test_default_instance_is_unaffected_by_later_dictionary_loads`（默认实例不受后加载词典影响，新默认实例结果一致）。
- 复检：`pytest tests/unit/retrieval/test_tokenizer.py` 8 passed；复核记录 04 的原复现脚本在修复后不再复现（第一实例结果与版本均不变）。

## 第三步：领域契约与 AgentState（M0-07）

`src/medops/domain/`，全部模型 frozen、禁止额外字段、可 JSON 往返；不依赖 FastAPI、数据库或模型 SDK；不含 `Any` 与 `dict[str, Any]`（有元测试守护）。

| 模型 | 关键约束 | 对应条款 |
| --- | --- | --- |
| `UserContext` | surrogate id；scope 形如 `MA:read`；`has_scopes` 默认拒绝 | INV-AUTH-01/03、INV-OBS-02 |
| `Document` | active 必须有 effective_from；effective_to 晚于 effective_from；不可自我 supersede | 3.4、INV-DATA-02 |
| `Chunk` | 页内字符区间长度等于内容长度；`content_hash` 等于内容 SHA-256 | 3.3、5.1 |
| `Citation` / `Evidence` | 引用含 doc_id/version/effective_date/page/section/chunk_id；draft 不能成为证据；archived 必须标记 historical；`evidence_text_hash` 等于正文 SHA-256 | INV-DATA-03/06、3.3 |
| `Intent` | off_label_check 与 high_risk 最低风险 high，AE 与方案偏离最低 medium；high_risk 不得路由到 Skill | F2、INV-SAF-01 |
| `VerifyResult` / `ElementSupport` | supported 必须指明证据 chunk；存在幻觉引用时 structural_ok 不能为真；`contradicted`/`unsupported` 属性 | 3.5、5.4 |
| `SafetyResult` | allow 无 reason code；refuse/escalate 至少一个稳定 reason code | 3.6、5.5 |
| `Answer` / `Claim` | claim 到引用的映射；claim 只能引用已列出的 citation；免责声明为固定 Literal | 5.3、INV-SAF-04 |
| `Escalation` | reason_codes 非空；带 policy_version 与最小必要上下文 | F4.2 |
| `AgentState` | 改写查询至多 3 条、候选至多 20、证据至多 8；证据 chunk 唯一；历史证据需显式请求且答案必须带 historical_notice；答案与升级互斥；答案只有在证据、structural_ok 且无矛盾的 verify_result、safety allow 同时存在且引用全部落在证据内时才可表示；升级的 policy_version 必须等于运行版本；`advance()` 产生新状态并重新校验全部不变量 | INV-HAR-02/03/08、INV-SAF-03/05、4.4 |

复检：`tests/unit/domain` 19 个测试（含 JSON 往返、非法状态反向用例、无 Any 元测试）通过。

## 完整门禁

```text
env -u PYTHONPATH make check
  install-check           -> medops importable outside the repo
  ruff check src tests    -> All checks passed!
  mypy                    -> Success: no issues found in 25 source files
  pytest -q               -> 87 passed in 2.87s
```

## 约束与未做

- 未接入 LangGraph、数据库、模型调用；AgentState 只让非法组合不可表示，不执行检索、核验或安全检查。
- 未实现 M0-05 的统一错误模型；`ReasonCode` 只覆盖拒答/升级原因，作为其一部分。
- 未勾选任何 checklist：M0-07 缺与运行时节点的对接与跨平台证据，M1-03/M1-15 仍待 DEC-001 实验固化版本。

## 风险

- `Chunk` 与 `Evidence` 的哈希校验在构造时重算 SHA-256，批量加载时有 CPU 开销；数据量上来后如需关闭，必须以显式的“已核验来源”类型替代，不能删掉校验。
- 无新增已知安全风险。
