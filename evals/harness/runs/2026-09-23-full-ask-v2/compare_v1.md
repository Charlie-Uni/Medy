# 2026-09-23-full-ask-v1 vs 2026-09-23-full-ask-v2 (614 common samples)

| metric | A (common) | B (common) |
| --- | ---: | ---: |
| n | 614 | 614 |
| answered | 456 | 480 |
| system_failure | 1 | 0 |
| answerable_answered_rate | 0.822 | 0.862 |
| answerable_gold_cited_rate | 0.745 | 0.784 |
| no_answer_abstained_rate | 0.967 | 0.967 |
| answerable_false_abstention_rate | 0.178 | 0.138 |
| cost_usd | 4.6367 | 4.6496 |
| model_calls | 1230 | 1236 |
| mean_latency_s | 7.1 | 8.01 |
| p95_latency_s | 12.89 | 13.58 |

| reason code | A | B |
| --- | ---: | ---: |
| insufficient_evidence | 127 | 126 |
| system_failure | 1 | 0 |
| unsupported_conclusion | 30 | 8 |

| outcome A -> B | n |
| --- | ---: |
| answered->answered | 443 |
| answered->escalated | 13 |
| escalated->answered | 37 |
| escalated->escalated | 121 |

| gold_cited A -> B (answerable) | n |
| --- | ---: |
| False->False | 95 |
| False->True | 33 |
| True->False | 13 |
| True->True | 360 |

Regressions (answered -> not answered): 13

- ms-0049 [answerable] ['insufficient_evidence'] no claim survives verification (forged=0, dropped=1)
- ms-0071 [answerable] ['unsupported_conclusion'] a claim contradicts the evidence (baseline 5.4 item 4)
- ms-0173 [answerable] ['insufficient_evidence'] no claim survives verification (forged=0, dropped=1)
- ms-0227 [answerable] ['unsupported_conclusion'] a claim contradicts the evidence (baseline 5.4 item 4)
- ms-0237 [answerable] ['unsupported_conclusion'] a claim contradicts the evidence (baseline 5.4 item 4)
- ms-0238 [answerable] ['unsupported_conclusion'] a claim contradicts the evidence (baseline 5.4 item 4)
- ms-0261 [answerable] ['unsupported_conclusion'] a claim contradicts the evidence (baseline 5.4 item 4)
- ms-0345 [answerable] ['insufficient_evidence'] model reports the evidence does not answer the question
- ms-0389 [conflict] ['insufficient_evidence'] no claim survives verification (forged=0, dropped=1)
- ms-0391 [answerable] ['insufficient_evidence'] no claim survives verification (forged=0, dropped=1)
- ms-0416 [answerable] ['insufficient_evidence'] model reports the evidence does not answer the question
- ms-0452 [answerable] ['insufficient_evidence'] every claim only states that the evidence is silent (abstention backstop)
- ms-0495 [no_answer] ['insufficient_evidence'] every claim only states that the evidence is silent (abstention backstop)

Recoveries (not answered -> answered): 37

- ms-0018 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0020 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0021 [answerable] was ['system_failure'], gold_cited=False
- ms-0026 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0078 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0086 [conflict] was ['unsupported_conclusion'], gold_cited=True
- ms-0087 [conflict] was ['unsupported_conclusion'], gold_cited=True
- ms-0093 [conflict] was ['unsupported_conclusion'], gold_cited=True
- ms-0105 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0135 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0145 [answerable] was ['insufficient_evidence'], gold_cited=True
- ms-0155 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0160 [answerable] was ['insufficient_evidence'], gold_cited=True
- ms-0187 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0188 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0206 [answerable] was ['insufficient_evidence'], gold_cited=False
- ms-0217 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0218 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0258 [answerable] was ['insufficient_evidence'], gold_cited=True
- ms-0266 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0312 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0316 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0322 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0406 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0412 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0413 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0431 [conflict] was ['unsupported_conclusion'], gold_cited=True
- ms-0441 [conflict] was ['unsupported_conclusion'], gold_cited=False
- ms-0449 [answerable] was ['unsupported_conclusion'], gold_cited=True
- ms-0520 [no_answer] was ['insufficient_evidence'], gold_cited=False
- pc-0018 [answerable] was ['unsupported_conclusion'], gold_cited=True
- pc-0027 [answerable] was ['unsupported_conclusion'], gold_cited=True
- pc-0045 [answerable] was ['unsupported_conclusion'], gold_cited=True
- pc-0071 [answerable] was ['insufficient_evidence'], gold_cited=True
- pc-0074 [answerable] was ['insufficient_evidence'], gold_cited=True
- pc-0080 [answerable] was ['unsupported_conclusion'], gold_cited=True
- pc-0103 [answerable] was ['insufficient_evidence'], gold_cited=True
