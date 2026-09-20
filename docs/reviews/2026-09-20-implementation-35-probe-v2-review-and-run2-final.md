# 实现记录 35：探针 v2 统一复核、争议裁决、冻结与第二次正式运行

日期：2026-09-20。承接记录 34。决策人先后决定：方案 2（全部 107 条由固定模型 claude-opus-5 统一第二复核）、确认 32 条英文孪生（16 条按其审校稿修订）、三轮争议裁决（"好了""前面的同意 剩下的按照你的建议来做""按照建议来"）。本记录覆盖复核工具、裁决执行、spec-v1.1 的校验器与模式补充、v2 冻结、第二次正式运行及回填。**结论：三候选在语言一致子集上 A 69.3%、B 76.0%、C 88.0%，均未通过硬门禁；DEC-001 与 M1 保持阻塞。**

## 1. 第二复核人更换与工具

- Codex/gpt-6-astra 额度耗尽后，决策人问能否用 Fable 复核；我建议不用（Fable 起草了孪生，SPEC 8 要求复核人独立于起草者），改用本机 Claude Code CLI 调用 claude-opus-5；决策人选方案 2。
- [run_claude_review.py](../../evals/probe/precise_clause/drafts/v2/tooling/run_claude_review.py)：与 v1 codex 运行器相同的提示字节与绑定格式；`--tools ""`、不持久化会话、不加载用户设置、固定中性系统提示（哈希入档）；模型标识由 CLI `modelUsage` 回显；推理强度为请求参数并如实记录。费用字段为 API 折算参考值，实际计入 Max 套餐额度（`claude auth status`：claude.ai 登录，subscriptionType max，无 API key）。
- 校验器：`review_provenance` 支持 `version_source=pinned_model_id` 与声明的 `reasoning_effort`；批次按 spec 版本含 `EN`；提示哈希重建接受 evidence_span 两种键序的逐记录组合（v2 输入包混合了规范键序与起草工具键序）。SPEC 8.1 记录固定模型标识规则与"同一版本单一复核人"。
- 首轮复核 107 条：23 次调用，21 条争议（MA 5、PV 7、CO 2、EN 7）。

## 2. 争议裁决（annotator-01）

- 第一轮 21 条：13 接受、4 修正后执行、4 保留，由 [apply_owner_adjudication_2026_09_20.py](../../evals/probe/precise_clause/drafts/v2/tooling/apply_owner_adjudication_2026_09_20.py) 逐条编码执行：7 个新 key_text（K1～K7，页内唯一且在 span 内）父子同步；pc-0027 span 收缩并重算偏移；pc-0023 key_text 扩展；4 组切片修正（pc-0036 经核对 SPEC 第 7 节后删除 dose_unit 与 time_window）；3 条 query 改写。保留项写入 `resolutions.json`。
- 重跑改动的 21 条：18 条同意；pc-0027、pc-0036 的再次争议用决策人裁决文档已写明的补充方案 B/C 结案；pc-0101 由决策人授权按我的建议改 query（复核人转而同意）并按 SPEC 5.1 维持 mixed_zh_en 继承。
- 冻结规则要求"最新复核批次不得含已被替换的输入"，因此与改动样本同批复核过的 58 条邻近样本全部重跑（第一次启动因 zsh 不拆分未加引号的变量而立即失败，改用 sh 脚本）。重跑新增 7 条改判：pc-0081 按决策人第五节口径结案；其余 6 条经决策人"按照建议来"：4 组 key_text 扩展（pc-0039；pc-0064/0096；pc-0093/0061；pc-0102/0070）父子同步，pc-0032、pc-0095 的 query 保留。第三轮重跑（改动样本 + 邻近样本）后剩 pc-0061、pc-0093（query）与 pc-0105（negation）三条，均按已批准原则结案。
- 最终 107 条：95 agreed、12 disputed_resolved；复核累计 ≈ 16.8 美元折算值，套餐额度内。

## 3. spec-v1.1 补充与 v2 冻结

- 模式：manifest 的 `review_provenance` 允许 `pinned_model_id`、`reasoning_effort` 与 `EN` 工件（8～10 个）；样本模式对 `derived_from` 样本免除 `language=mixed`。校验器：PR-04 每文档 6 条上限只计非派生样本；孪生继承父样本 gold 的 PII 例外（pc-0081 继承 pc-0046 的机构邮箱例外）。
- 装配器从裁决后的草稿装配（不再从 v1 samples.jsonl），corpus.json 标 v2。
- `freeze_v2.py`：draft 校验 0 错误 → SHA256SUMS → `dataset_hash 1fc5089f…0321` → frozen 校验 0 错误 0 警告，107 条（MA 30、PV 45、CO 32；gold 语言 zh-Hans 10、zh-Hant 33、en 64）。

## 4. 第二次正式运行

- 三服务器 `medops_v2` 上按 v2 重生成映射：105 mapped / 2 unmappable（pc-0070-g1、pc-0102-g1，扩长后的 key_text 跨 chunk 边界；按规则计 miss，不改切分器）。
- 运行 `2026-09-20-run2-final`（K=20，预热 5、测量 10，种子 20260920，并发 1，`as_of` 2026-09-20）：

| 子集 | A | B | C |
| --- | --- | --- | --- |
| 语言一致（75 条，门禁作用域） | 69.3% | 76.0% | 88.0% |
| 跨语言（32 条，不设门禁） | 15.6% | 12.5% | 12.5% |
| 全部冻结样本（107 条） | 53.3% | 57.0% | 65.4% |

切片（语言一致）：C 除 protocol_id 70.6%（n=17）外全部 ≥85%；B 的 negation、time_window、protocol_id、mixed_zh_en 未达；A 多数未达。零泄漏，排名可复现，P95 A 37.5 / B 37.9 / C 32.8 ms。相对 A：B +6.7 pp [+1.3, +13.3]，C +18.7 pp [+8.0, +29.3]。归因：语言一致子集的未命中除 unmappable 外全为"合格但名次 >20"；A/B 各 14 条在英文孪生上（停用词稀释、无 IDF），C 6 条。已回填 ADR-0002。

## 5. 测试与门禁

`env -u DEBUG -u PYTHONPATH make check` 退出码 0（数字见路线图核查行）。本轮新增：校验器/模式调整由既有 65 项校验器测试与 PR-15 测试覆盖。

## 6. 自审（基线 §9）

1. 需求：按决策人的三次决定执行；未在看到结果后调整候选配置、判据或样本。
2. 逻辑：每次样本改动都重新打包并重跑复核，含邻近样本；冻结前 draft/frozen 校验各 0 错误。
3. 安全：复核调用工具关闭、无网络访问、页文本只在忽略的输入包中；`.env.dec001` 不入库。
4. 契约：候选适配器与运行器未改；报告按语言一致作用域计算门禁。
5. 测试：全量 make check 通过。
6. 可观测：10 个复核证据工件由 manifest 哈希绑定；三轮裁决各有记录文件。
7. 简洁性：v2 工具为 v1 工具的路径改写 + 三个小脚本。
8. 验证：本记录数字来自 report.md、evaluation.json、freeze 输出。
9. Checklist：M1-01 已实现（v2 冻结为后续实验的输入）；M1-05 仍阻塞；进度不变 24.7%（19.5/79）。

## 7. 观察与决策人待定事项

- 同一复核模型对同一样本前后判定不一致：三轮共 31 条争议，其中 10 条发生在重看已同意的样本时。规范"最新批次不得含已替换输入"的规则使每次改动都放大为几十条重跑。
- 按裁决扩长的 key_text（pc-0070/0102 含示例清单）跨越了 chunker-v2 的边界，产生 2 条 unmappable；这是 P1 最小性与切分粒度之间的张力，留给下一版探针处理。
- 下一步需要决策人决定（均为新的预登记）：A/B 的英文停用词/IDF 变体；C 的许可证审核；是否继续 DEC-001 或接受"词法阶段不单独达标、由向量阶段补齐"的架构含义。
