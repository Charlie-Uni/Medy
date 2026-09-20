# 实现记录 49：M1-20 扩语料落地——候选签字、图像层核查、PII 复核、门禁修订、入库与激活、主评测集规范 v1.0

日期：2026-09-21。决策人回复："1确认 2五个参数按照你的建议来 3要改的是什么？"。本记录登记第 1、2 项的执行；第 3 项（三处措辞替代）在回复中列出原文与替代文，默认保持现状。

## 1. 候选签字与入库前核查

- **v0.8**：58 条新候选 `reviewer_decision=eligible`（决策人 2026-09-21 确认）。**v0.9**：登记 22 份 TFDA 仿單的图像层核查（[tfda_image_layer_check_2026-09-21.md](../../evals/main_set/tfda_image_layer_check_2026-09-21.md)）：pypdfium2 约 65 dpi 渲染、29 张检视图覆盖全部页面，逐张目视，只见廠商標誌/® 商标/GMP 与回收标志，未见任何版权或保密声明——ADR-0003 决策 1 条件 (3) 通过（分辨率限制已在核查文件注明）。
- **PII 复核**：`pii-rules-v1` 在 8 份新文档命中 17 处，全部为机构职能信箱（FDA druginfo/ocod/dsmica/gcpquestions/combination/CDRH 组信箱、EMA duplicates 与 emerging-safety-issue 信箱、MSSO 帮助台），判为 INV-DATA-01 误报，与记录 21 口径一致；留档 [pii_review_2026-09-21.json](../../evals/main_set/pii_review_2026-09-21.json)，入库用 `--accept-pii` 写入 `pii_review_override` 审计。
- **门禁修订（ADR-0009 修订 1）**：首次对 58 份运行结构性门禁误拒 6 份——3 份 `/OpenAction` 实为跳转目的地/GoTo，3 份对象图超过 20,000（49/86/301 页）。修订：`/OpenAction` 按动作类型判定（目的地与 GoTo 放行，其余拒绝）；对象图上限 500,000。新增 3 项单元测试；修订后 6 份全部通过，其他规则不变。

## 2. 主评测集 corpus 与入库

- [build_corpus.py](../../evals/main_set/tools/build_corpus.py)：由候选 v0.9 + 抽取记录 + 页文本生成 [evals/main_set/corpus.json](../../evals/main_set/corpus.json)（`dataset_version=main-v1-provisional`；corpus schema 的版本模式扩展为允许 `main-v<N>[-provisional]`），74 份文档（探针 16 + 新 58）：en 41、zh-Hant 28、zh-Hans 5；PV 30、MA 27、CO 17；guideline 47、label 27。文档键固定（ICH 代码 + Step 4 年份、GVP 模块/附录 + 修订、FDA 固定映射、MedDRA 文档种类、TFDA 英文品名）。
- 页文本：`medops.evals.probe.extract`（pypdf 6.18.1）抽取 58 份至 `evals/main_set/pages/`（不入 Git）；3 份 ICH 历史版本各有 1 页空白（分隔页）。
- 入库 `medops_v2@5432`：58 份全部 `ingested`；3 份 TFDA 仿單（施黴素、若通、舒敏樂）因 pypdf 字体编码告警为 `low_trust`——页文本经核对无替换字符、中英文比例正常，但本轮**不做复核放行**（只能在入库时 `--accept-quality`，且需决策人签字），三份保留为 draft、不进入主评测集；其余 55 份按 `version_label` 派生 `effective_from`（Step 4 日期 / EMA 日期 / FDA 月首日 / MedDRA 2022-03-01 / 仿單修订或 PDF 日期，[activation_plan_2026-09-21.json](../../evals/main_set/activation_plan_2026-09-21.json)）全部激活。库内：active 71、draft 3、chunk 9,839（active 9,806）；生产词法索引与 A2 索引已重建到 9,839；向量嵌入（约 7,177 个新 chunk）后台构建中。

## 3. 主评测集规范 v1.0（[evals/main_set/SPEC.md](../../evals/main_set/SPEC.md)）

五个参数按建议固定：每文档非派生上限 8；无答案样本 ≥40、abstention accuracy ≥90%；冲突样本允许合成（`synthetic=true`）；zh-Hans 下限 ≥20；**第二人工复核人待决策人指定**（冻结前必须补齐，此前只能 `main-v1-provisional`）。

## 4. 测试与门禁

`make check` 退出码 0，**877 passed**（634 单元 + 243 集成）。

## 5. 自审（§9）

需求：ADR-0003 四项条件逐条落实并留档；INV-DATA-01 复核留档；ADR-0009 门禁按证据修订而非放宽；逻辑：先核查后入库，低可信不激活；安全：页文本与 PDF 不入 Git，审计覆盖 PII 覆盖与激活；测试：门禁修订有单元测试；Checklist：M1-20 仍为待做（语料就绪，样本起草未开始）。

## 6. 下一步

样本起草（LLM 辅助）→ annotator-01 确认 → LLM 独立复核 → 第二人工复核 → 争议裁决 → 冻结 `main-v1`。起草前需决策人确认起草成本（估算见回复）。
