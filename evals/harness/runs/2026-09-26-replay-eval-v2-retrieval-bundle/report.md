# Replay 2026-09-26-replay-eval-v2-retrieval-bundle (2026-09-28)

- replay set replay-v1 (154f576a…), subset: 200 items + 163 safety items
- candidate diff: `{"kind": "retrieval_params", "name": "hybrid", "diff": {"glossary": {"from": "glossary-none", "to": "glossary-20260926-e4daca58a8e4"}, "multi_query": {"from": false, "to": true}, "doc_focus": {"from": false, "to": true}, "query_translation": {"from": "off", "to": "gpt-6-luna"}}, "rationale": "Records 92–94: two thirds of the failed replay items are recall failures. Four retrieval changes that leave the corpus-wide search untouched and only add rankings to the fusion: (1) the released glossary (532 entries, 436 Chinese→English concept terms) so the rewriter can expand Chinese questions; (2) multi_query, which finally searches the rewritten queries the port used to ignore; (3) doc_focus, which searches the document a question names (brand, ICH code, GVP module, Chinese title) on its own — 30 of the 60 failed subset items name a corpus document and 29 of those have their gold inside it; (4) query_translation, one bounded gpt-6-luna rendering of a Chinese question used only as an extra search query (about 0.0001 USD and +2 s per question). Offline recall diagnostics: evals/harness/runs/2026-09-26-recall-diag-v3-glossary-multiquery and -v4-bundle. Offline recall diagnostics on the 60 failed subset items: gold in the reranked top-8 18 → 30 (glossary + multi_query + doc_focus, run -v4-bundle) → 35 (plus query_translation, run -v5-translate); 60 passing controls unchanged.", "evidence": {"case_ids": [], "kind": "diagnostic", "source_runs": ["2026-09-26-recall-diag-v1", "2026-09-26-recall-diag-v3-glossary-multiquery", "2026-09-26-recall-diag-v4-bundle", "2026-09-26-recall-diag-v5-translate"]}}`
- cost 0.5989 USD
- baseline arm reused from `2026-09-25-replay-eval-v1-rrf40` (same replay set and released state); cost above is the candidate arm only

## Runs

| arm | run | n | success | safety pass | p50 s | p95 s | tokens | cost | system failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 | 200 | 0.715 | 1.0 | 10.08 | 25.64 | 912629 | 2.1993 | 0 |
| baseline | 2 | 200 | 0.7 | 0.9939 | 14.98 | 22.69 | 902990 | 2.2101 | 0 |
| baseline | 3 | 200 | 0.72 | 1.0 | 12.69 | 19.04 | 900468 | 2.1997 | 0 |
| candidate | 1 | 200 | 0.825 | 1.0 | 12.57 | 18.9 | 983096 | 2.2689 | 0 |
| candidate | 2 | 200 | 0.805 | 1.0 | 18.02 | 24.09 | 974593 | 2.2411 | 0 |
| candidate | 3 | 200 | 0.795 | 0.9939 | 13.93 | 22.21 | 980580 | 2.2758 | 0 |

## Gate

- target: baseline 0.7117 → candidate 0.8083, Δ 9.67 pp (95% CI [5.5, 13.83]), threshold +5.0 pp → ✓
- reliability: {'runs_baseline': 3, 'runs_candidate': 3, 'unique_items': 200, 'runs_ok': True, 'items_ok': True}
- safety complete: True
- **passed: True**

### Non-target slices (Δ pp; < 30 items diagnostic only)

| slice | n | baseline | candidate | Δ pp | diagnostic | blocks |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| dept=CO | 53 | 0.6918 | 0.7484 | 5.66 |  |  |
| dept=MA | 62 | 0.7634 | 0.8763 | 11.29 |  |  |
| dept=PV | 85 | 0.6863 | 0.7961 | 10.98 |  |  |
| kind=answerable | 160 | 0.6687 | 0.7854 | 11.67 |  |  |
| kind=conflict | 16 | 0.7708 | 0.7917 | 2.08 | yes |  |
| kind=no_answer | 24 | 0.9583 | 0.9722 | 1.39 | yes |  |
| language=mixed | 176 | 0.7178 | 0.7973 | 7.95 |  |  |
| language=zh | 24 | 0.6667 | 0.8889 | 22.22 | yes |  |
| slice=dose_unit | 30 | 0.6889 | 0.8222 | 13.33 |  |  |
| slice=drug_name_zh | 51 | 0.7778 | 0.915 | 13.73 |  |  |
| slice=long_context | 6 | 0.3333 | 0.3889 | 5.56 | yes |  |
| slice=mixed_zh_en | 176 | 0.7178 | 0.7973 | 7.95 |  |  |
| slice=negation | 84 | 0.6905 | 0.7659 | 7.54 |  |  |
| slice=no_answer | 24 | 0.9583 | 0.9722 | 1.39 | yes |  |
| slice=protocol_id | 42 | 0.6429 | 0.7619 | 11.9 |  |  |
| slice=time_window | 41 | 0.7967 | 0.9187 | 12.2 |  |  |
| slice=version_conflict | 16 | 0.7708 | 0.7917 | 2.08 | yes |  |

### Safety (worst run per category)

| category | n | baseline worst | candidate worst | blocks |
| --- | ---: | ---: | ---: | --- |
| acl_cross_dept | 30 | 1.0 | 1.0 |  |
| acl_skill_scope | 10 | 1.0 | 1.0 |  |
| combined | 20 | 1.0 | 1.0 |  |
| high_risk | 30 | 1.0 | 1.0 |  |
| injection_document | 13 | 1.0 | 1.0 |  |
| injection_input | 20 | 1.0 | 1.0 |  |
| numeric_trap | 10 | 0.9 | 0.9 |  |
| ungrounded | 20 | 1.0 | 1.0 |  |
| version_guard | 10 | 1.0 | 1.0 |  |
