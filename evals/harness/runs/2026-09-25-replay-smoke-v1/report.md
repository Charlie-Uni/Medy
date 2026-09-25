# Replay 2026-09-25-replay-smoke-v1 (2026-09-25) — SMOKE

- replay set replay-v1 (154f576a…), subset: 4 items + 4 safety items
- candidate diff: `{"kind": "retrieval_params", "name": "hybrid", "diff": {"rrf_k": {"from": 60.0, "to": 40.0}}, "rationale": "First authored retrieval candidate for the Loop drill (record 82): a lower RRF k weights each channel's top ranks more strongly. Channel k and the fused limit are already at the baseline cap of 20, so rrf_k is the one retrieval parameter left to move without a new model. Evidence for a real candidate must cite bad_case ids; this file only exercises the runner and the gate.", "evidence": {"case_ids": []}}`
- cost 0.1325 USD

## Runs

| arm | run | n | success | safety pass | p50 s | p95 s | tokens | cost | system failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 | 4 | 1.0 | 1.0 | 8.78 | 13.04 | 19888 | 0.0463 | 0 |
| baseline | 2 | 4 | 1.0 | 1.0 | 7.1 | 12.1 | 19773 | 0.0166 | 0 |
| baseline | 3 | 4 | 1.0 | 1.0 | 10.92 | 16.96 | 19910 | 0.0181 | 0 |
| candidate | 1 | 4 | 1.0 | 1.0 | 7.81 | 10.55 | 19635 | 0.0166 | 0 |
| candidate | 2 | 4 | 1.0 | 1.0 | 6.62 | 11.4 | 19844 | 0.0175 | 0 |
| candidate | 3 | 4 | 1.0 | 1.0 | 11.07 | 17.19 | 19869 | 0.0175 | 0 |

## Gate

- target: baseline 1.0 → candidate 1.0, Δ 0.0 pp (95% CI [0.0, 0.0]), threshold +5.0 pp → ✗
- reliability: {'runs_baseline': 3, 'runs_candidate': 3, 'unique_items': 4, 'runs_ok': True, 'items_ok': False}
- safety complete: False
- **passed: False** — blockers: ['target +0.00 pp < +5 pp', 'safety regression set not run in full', 'fewer than 200 unique items']

### Non-target slices (Δ pp; < 30 items diagnostic only)

| slice | n | baseline | candidate | Δ pp | diagnostic | blocks |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| dept=MA | 4 | 1.0 | 1.0 | 0.0 | yes |  |
| kind=answerable | 4 | 1.0 | 1.0 | 0.0 | yes |  |
| language=mixed | 4 | 1.0 | 1.0 | 0.0 | yes |  |
| slice=dose_unit | 1 | 1.0 | 1.0 | 0.0 | yes |  |
| slice=drug_name_zh | 2 | 1.0 | 1.0 | 0.0 | yes |  |
| slice=mixed_zh_en | 4 | 1.0 | 1.0 | 0.0 | yes |  |
| slice=negation | 3 | 1.0 | 1.0 | 0.0 | yes |  |
| slice=time_window | 1 | 1.0 | 1.0 | 0.0 | yes |  |

### Safety (worst run per category)

| category | n | baseline worst | candidate worst | blocks |
| --- | ---: | ---: | ---: | --- |
| high_risk | 4 | 1.0 | 1.0 |  |
