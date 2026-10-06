# 安全评测集（safety_set，spec-s1 v0.3）

规范见 [SPEC.md](SPEC.md)；决策见 `docs/reviews/2026-09-24-implementation-68-decisions.md`，建设记录见记录 69。

## 目录

| 路径 | 内容 | 入库 |
| --- | --- | --- |
| `schema/safety_sample.schema.json` | 样本 JSON Schema（§3） | 是 |
| `drafts/samples_draft_<类别>.jsonl` | 起草样本（9 个类别，170 条），`review` 块含 gpt-6-sol 独立复核结论 | 是 |
| `drafts/sheets/*.md` | annotator-01 逐条确认表（全集不抽样）与四条判定模型矛盾的人工复核表 | 是 |
| `drafts/drafting_provenance.json` | 起草模块（模板）的 SHA-256 与条数 | 是 |
| `drafts/review_verdicts.jsonl`、`drafts/review_prompt_safety.md` | 复核逐条结果与固定提示 | 是 |
| `injection_plan.json`、`corpus_safety.json` | 合成文档计划（6 份、25 段注入）与安全语料记录（含金丝雀映射） | 是 |
| `safety-v2-provisional/` | 冻结版本（2026-10-06，记录 124）：`samples.jsonl`、撤下样本、复核结论与提示、确认表、`manifest.json`、`SHA256SUMS`；`dataset_hash` 为 SHA256SUMS 文本的 SHA-256 | 是 |
| `drafts/withdrawn/` | 从现行草案撤下的样本原文（含复核块）与 `manifest.json`（替换为谁、为什么）；`load_drafts(include_withdrawn=True)` 供冻结回放集与存档运行解析旧编号（记录 114） | 是 |
| `drafts/sheets/safety-v2-changes.md` | safety-v2 变动样本的确认表（8 条待确认 + 7 条撤下） | 是 |
| `drafts/stale_expectations_2026-10-02.md`、`drafts/proposals/*.json` | 语料扩展后的裁决与待办、safety-v2 的替换题草案（未进入任何版本，待人工确认；记录 112） | 是 |
| `acl_targets.json` | 生产库文档的 source hash / 部门 / 状态快照（C1、D2、F 类引用） | 是 |
| `synthetic/<source_hash>.docx` | 合成文档源文件（复制的受许可正文 + 注入段） | 否（gitignored，`build_synthetic_docs.py` 重建） |
| `tools/authoring/*.py` | 起草模块：每条 query 与预期由起草人（claude-fable-5-1）直接写入 | 是 |

## 流程

```
python evals/safety_set/tools/gen_acl_targets.py            # 生产库快照 -> acl_targets.json
python evals/safety_set/tools/build_synthetic_docs.py       # 6 份 DOCX + corpus_safety.json（自检：每个金丝雀恰好一次）
MEDOPS_MIGRATION_URL=<安全库 admin DSN> python -m medops.ingestion.load --corpus evals/safety_set/corpus_safety.json \
    --sources-dir evals/safety_set/synthetic --actor safety-set-01 --no-av      # 然后 activate、build-lexical、向量补建
python evals/safety_set/tools/author_drafts.py              # 起草模块 -> drafts/*.jsonl + 起草溯源；重跑保留未变样本的复核块，WITHDRAWN 的样本移到 drafts/withdrawn/
python evals/safety_set/tools/check_safety.py               # schema、PR-S1..S6（含两库证明）、配额；必须为 0 问题
python evals/safety_set/tools/run_review.py --apply         # gpt-6-sol 独立复核（不同厂商），结论写回 review 块
python evals/safety_set/tools/make_sheets.py                # annotator-01 标注表
python evals/safety_set/tools/freeze.py --version safety-v2-provisional --confirmed-by <who/when>   # 冻结：校验归零、复核齐全后写 manifest 与哈希
python evals/harness/tools/safety_run.py --out evals/harness/runs/<名称> --dataset evals/safety_set/safety-v2-provisional --released   # 冻结版本上的正式运行
```

安全数据库 `medops_v2_safety` 由 medops_v2 以模板克隆后追加 `sf-` 文档；生产库与主集运行永不接触它。
