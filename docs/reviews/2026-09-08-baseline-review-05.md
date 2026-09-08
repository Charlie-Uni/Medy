# 第五轮审核与探针集规范记录（2026-09-04 起草，2026-09-08 定稿）

| 项 | 内容 |
| --- | --- |
| 审核对象 | 基线 v0.4（提交 cf26da0）、ADR-0002、第四轮审核记录 |
| 审核人 | Claude（Fable 5.1） |
| 决策人 | Qihan Zhu |
| 结论 | v0.4 语义与机械核对通过；4 处精确性问题按决策并入 v0.5；探针集冻结规范 spec-v1 发布 |

## 1. v0.4 独立核对

- 提交 cf26da0：3 个文件，178 行新增、15 行删除，`git diff --check` 通过。
- 不变量 30 无重复；checklist 99 项无勾选；DEC 10 项；围栏配对；链接可解析；两份来源 SHA256SUMS 通过；工作树干净。
- ADR-0002 与基线 3.1、3.6、3.7、5.2、5.9、7.1、M1 Checklist、DEC-001 的差异逐段核对，与第四轮达成的五点细化和探针集前置一致。

## 2. v0.5 精确性修订

| # | 问题 | 处置 | 落点 |
| --- | --- | --- | --- |
| 1 | `retriever_version` 与 `retrieval_version` 关系未定义 | `retrieval_version` 定义为对 retriever/tokenizer/dictionary/normalization/embedding 版本与 RRF、Reranker、候选上限参数做 canonical_json 后的 SHA-256；分量只用于诊断，不得单独作缓存键或回放键 | 基线 3.6 |
| 2 | “合格候选”匹配谓词未定义 | 谓词（词元 AND、OR 或短语）在实验清单中逐候选固定；精确计数与检索使用同一谓词与过滤条件 | 基线 3.7、ADR-0002 硬门禁 4 |
| 3 | 选择规则中“合格候选者”未含许可证门禁 | 明确合格等于硬门禁加许可证门禁通过；技术得分不能替代许可证结论 | ADR-0002 选择规则 |
| 4 | 可复现要求缺并列规则 | 分数相同按 `chunk_id` 升序打破并列；可复现指候选集合与排名逐项一致 | 基线 3.7、ADR-0002 硬门禁 5 |

## 3. 探针集决策

| # | 事项 | 决策 | 落点 |
| --- | --- | --- | --- |
| 1 | gold 锚定 | `source_hash/version_label/page/section/key_text`，不引用 chunk_id；最终命中规则见第 7 节：chunk 的 `gold.page` 来源片段必须覆盖 `key_text` 页内位置；每个切分器版本生成映射文件 | SPEC 第 6 节、ADR-0002、基线 5.9 与 M1 |
| 2 | 语料来源 | 只用公开文档，许可、来源、哈希、PII 扫描逐份记录 | SPEC 第 3 节、corpus.schema.json |
| 3 | 第二复核人 | LLM 复核，manifest 与每条样本如实记录模型、版本、prompt 哈希，并声明不等同于两名人工复核 | SPEC 第 8 节、manifest/probe_sample schema、ADR-0002 |
| 4 | 规范载体 | 语言无关的规范文档加 JSON Schema（draft 2020-12）放在 `evals/probe/precise_clause/`；Pydantic 与校验器随 M0 生成 | SPEC 全文、schema/ |

## 4. 本轮交付

- `evals/probe/precise_clause/SPEC.md`：目录、语料规则、抽取与规范化基线、样本结构、命中规则、切片定义、复核流程、冻结流程、14 条校验规则、ACL 探针、与基线/ADR 的对应。
- `evals/probe/precise_clause/schema/`：manifest、corpus、probe_sample、acl_probe、chunk_mapping 五个 Schema。
- `evals/probe/precise_clause/examples/`：由脚本生成的示意 manifest、corpus、3 条样本与复核 prompt；corpus 中的原始文档哈希为占位值，示例文件哈希为实算值，`status=draft`，不得进入版本目录。
- `.gitignore`：探针集原始 PDF 目录不进入 Git。
- 基线 v0.5 与 ADR-0002 修订如上。

## 5. 初稿验证（已由 7.1 的定稿复核覆盖）

| 检查项 | 实测 |
| --- | --- |
| 五个 Schema 通过 Draft 2020-12 元校验（jsonschema 4.25.1） | 通过 |
| 示例 manifest、corpus、3 条样本通过对应 Schema | 通过 |
| 示例一致性：canonical JSONL、id 前缀、source_hash 存在、dept 与 owner_dept 一致、偏移量与文本长度一致、文件哈希与 manifest 一致 | 通过 |
| 反向测试：en 带 drug_name_zh、mixed_zh_en 非 mixed、disputed 无 note、LLM 复核无 prompt_hash、frozen 无哈希、许可证“未知” | 6/6 被拒绝 |
| 基线不变量 / 重复 | 30 / 0 |
| 基线 checklist / 已勾选 | 99 / 0 |
| DEC 行数 | 10 |
| 代码围栏（基线 / ADR-0002 / SPEC） | 14 / 2 / 2，均配对 |
| 基线、ADR、审核记录、README、SPEC 相对链接缺失 | 0（记录文件写入后复核） |
| 来源 SHA256SUMS | MedOps_Copilot_项目设计文档_v0.1.pdf: OK PROJECT_DESCRIPTION_v0.1.md: OK  |
| PR-05 页文本定位、PR-07 PII、PR-10 冻结校验 | 未运行：示例无真实页文本与冻结版本，校验器随 M0 实现 |

## 6. 初稿待决策与待办

- 已关闭：切片最低数量保持 8；基线 5.8 的 30 条规则仅适用于 M4 Loop，最终落点见第 7 节。
- 已关闭：主评测集采用分层复核政策，最终落点见第 7 节。
- 公开语料的具体文档清单与许可确认（DEC-005）在冻结 v1 前完成。
- 校验器（PR-01 到 PR-14）随 M0 实现；在此之前不得宣称任何数据集版本已冻结。
- 定稿审核开始时本轮改动尚未提交；最终提交状态以 Git 历史为准。

## 7. 2026-09-08 定稿修订（采纳第五轮审核发现）

| 项 | 决策与落地 |
| --- | --- |
| norm-v1 | 改为 NFC + 固定顺序显式折叠（伪空白删除、全角 ASCII 转半角、µ→μ、unit-map-v1 白名单、空白折叠），保留上下标与带圈数字；`tests/norm_v1_vectors.json` 收录 18 条 fold/preserve 向量并作为 PR-14 |
| gold 命中 | 删除 `occurrence`；`key_text` 页内恰好一次；命中需同一 `source_hash/version_label`、chunk 具有覆盖 `gold.page` 的片段且覆盖 `key_text` 页内位置；PR-05 改为出现次数等于 1 |
| 切片门禁 | `per_slice` 保持 8；基线 5.8、ADR-0002、SPEC 均写明“少于 30 条只作诊断”仅适用于 M4 Loop 回放 |
| 主评测集复核 | 基线 5.9 改为分层政策：全部样本人工标注 + LLM 复核；争议及剂量/否定/时间窗/版本冲突/高风险样本第二人工复核；其余随机不少于 20%；LLM 不计作第二人工 |
| manifest Schema | `files` 三个必需路径各恰一个、`acl_probes.jsonl` 至多一个；`reviewers` 恰好一名 human annotator 与一名 LLM second reviewer；`extraction.params` 对象与 `params_hash = SHA-256(canonical_json(params))`；`minimums` 增加 documents=10、documents_per_dept=3 |
| 样本 Schema | `second_reviewer.kind` 固定为 llm |
| SPEC | 第 2 节补充可选本地 `v*/sources/` 永不入 Git；第 3 节写明至少 10 份文档、每部门 3 份及 PV 语料风险；第 8 节 `review_prompt.md` 固定 UTF-8/LF/无 BOM/末尾换行；PR-10 要求 `manifest.files` 与 `SHA256SUMS` 完全一致 |
| 日期 | 基线 v0.5 与 SPEC 更新为 2026-09-08；本记录改名为 2026-09-08 并同步链接；ADR-0002 保留 2026-09-03 并加“最后修订 2026-09-08”；历史记录日期不变 |
| 全角映射解释 | 步骤 3 按 U+FF01–FF5E 整区映射，规范化文本中“，：（）”变为 ASCII 标点，“。、《》【】”不变；若只需映射字母数字可改 SPEC 4.1 第 3 步并重生成示例 |

### 7.1 定稿复核实测

| 检查项 | 实测 |
| --- | --- |
| Schema 元校验 / 示例校验 | 5 个通过 / manifest、corpus、3 条样本通过 |
| 示例一致性（canonical、无 occurrence、部门与版本、区间、norm-v1 幂等、prompt 字节、params_hash、文件哈希） | 通过 |
| norm-v1 向量 | 18/18 通过（10 fold、8 preserve） |
| 反向测试 | 14/14 被拒绝 |
| 不变量 / 重复 | 30 / 0 |
| checklist / 已勾选 | 99 / 0 |
| DEC | 10 |
| 代码围栏（基线 / ADR-0002 / SPEC） | 14 / 2 / 2 |
| 相对链接缺失 | 0 |
| 旧文件名残留引用 / occurrence 残留文件 | 0 / 0 |
| 来源 SHA256SUMS | MedOps_Copilot_项目设计文档_v0.1.pdf: OK PROJECT_DESCRIPTION_v0.1.md: OK  |
| git diff --check | 输出行数 0 |
| 未运行 | PR-05 真实页文本定位、PR-07 PII、PR-10 冻结校验、PR-14 正式校验器（M0 实现后） |
