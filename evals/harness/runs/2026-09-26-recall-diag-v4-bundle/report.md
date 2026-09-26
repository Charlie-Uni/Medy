# Recall diagnostic 2026-09-26-recall-diag-v4-bundle (2026-09-26)

- replay set replay-v1 (154f576a…), subset items with label bad: 60; good controls: 140
- retrieval: production hybrid config, rerank_output 8, glossary glossary-20260926-e4daca58a8e4, multi_query True, doc_focus True, as_of 2026-09-24, device mps; no model calls

## Failed items by stage

| stage | n | share |
| --- | ---: | ---: |
| recall | 26 | 43% |
| rerank | 4 | 7% |
| generation | 30 | 50% |

Good controls: gold in top-20 117/140, in top-8 117/140; gold rank distribution {1: 95, 2: 15, 3: 6, 4: 1, None: 23}

## By label reason

| reason | n | recall | rerank | generation |
| --- | ---: | ---: | ---: | ---: |
| answerable_answered_wrong_citation | 20 | 8 | 1 | 11 |
| answerable_false_abstention | 36 | 15 | 2 | 19 |
| conflict_false_abstention | 3 | 2 | 1 | 0 |
| no_answer_answered | 1 | 1 | 0 | 0 |

## By department

| dept | n | recall | rerank | generation |
| --- | ---: | ---: | ---: | ---: |
| MA | 17 | 2 | 2 | 13 |
| PV | 27 | 13 | 1 | 13 |
| CO | 16 | 11 | 1 | 4 |

## Recall failures by slice

| slice | failed items with slice | of which recall |
| --- | ---: | ---: |
| dose_unit | 10 | 1 |
| drug_name_zh | 13 | 1 |
| long_context | 4 | 1 |
| mixed_zh_en | 53 | 25 |
| negation | 26 | 10 |
| no_answer | 1 | 1 |
| protocol_id | 16 | 9 |
| time_window | 9 | 3 |
| version_conflict | 3 | 2 |

Cross-lingual recall failures (Chinese query, English gold chunk): 17 of 26


## Items

| item | label | reason | dept | gold rank top-20 | gold rank top-8 | stage |
| --- | --- | --- | --- | ---: | ---: | --- |
| rp-0001 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0006 | good | answerable_answered_gold_cited | MA | 4 | 2 |  |
| rp-0008 | good | answerable_answered_gold_cited | MA | 6 | 1 |  |
| rp-0009 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0011 | bad | answerable_answered_wrong_citation | MA | 10 | 1 | generation |
| rp-0012 | bad | answerable_false_abstention | MA | 1 | 1 | generation |
| rp-0014 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0016 | good | answerable_answered_gold_cited | MA | 2 | 4 |  |
| rp-0021 | bad | answerable_answered_wrong_citation | MA | 2 | 2 | generation |
| rp-0023 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0026 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0028 | good | answerable_answered_gold_cited | MA | 5 | 1 |  |
| rp-0032 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0033 | bad | answerable_false_abstention | MA | 2 | 4 | generation |
| rp-0034 | good | answerable_answered_gold_cited | MA | 1 | 2 |  |
| rp-0035 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0038 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0039 | bad | answerable_false_abstention | MA | 3 | 2 | generation |
| rp-0044 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0046 | bad | answerable_false_abstention | MA | 1 | 2 | generation |
| rp-0047 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0048 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0052 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0053 | bad | answerable_answered_wrong_citation | MA | 2 | 3 | generation |
| rp-0055 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0057 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0058 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0060 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0065 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0066 | good | answerable_answered_gold_cited | MA | 3 | 3 |  |
| rp-0067 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0069 | good | answerable_answered_gold_cited | MA | 5 | 1 |  |
| rp-0071 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0073 | good | answerable_answered_gold_cited | MA | 4 | 2 |  |
| rp-0076 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0079 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0080 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0081 | good | conflict_current_cited | PV | 2 | 1 |  |
| rp-0083 | good | conflict_current_cited | PV | 1 | 1 |  |
| rp-0087 | bad | conflict_false_abstention | PV |  |  | recall |
| rp-0089 | good | conflict_current_cited | PV | 1 | 2 |  |
| rp-0093 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0104 | good | answerable_answered_gold_cited | PV | 3 | 1 |  |
| rp-0105 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0107 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0115 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0121 | bad | answerable_false_abstention | PV | 5 | 3 | generation |
| rp-0123 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0125 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0129 | bad | answerable_false_abstention | PV | 8 | 1 | generation |
| rp-0131 | bad | answerable_false_abstention | PV | 7 |  | rerank |
| rp-0132 | good | answerable_answered_gold_cited | PV | 15 | 1 |  |
| rp-0134 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0138 | good | answerable_answered_gold_cited | PV | 11 | 2 |  |
| rp-0146 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0150 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0154 | good | answerable_answered_gold_cited | PV | 2 | 2 |  |
| rp-0160 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0162 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0164 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0166 | good | answerable_answered_gold_cited | PV | 15 | 2 |  |
| rp-0170 | bad | answerable_false_abstention | PV | 2 | 1 | generation |
| rp-0172 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0174 | bad | answerable_false_abstention | PV | 1 | 1 | generation |
| rp-0178 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0180 | good | answerable_answered_gold_cited | PV | 4 | 3 |  |
| rp-0182 | good | answerable_answered_gold_cited | PV | 1 | 3 |  |
| rp-0188 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0190 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0192 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0194 | bad | answerable_answered_wrong_citation | PV | 1 | 2 | generation |
| rp-0200 | bad | answerable_false_abstention | PV | 4 | 1 | generation |
| rp-0202 | good | conflict_current_cited | PV | 4 | 1 |  |
| rp-0206 | good | conflict_current_cited | PV | 2 | 1 |  |
| rp-0208 | good | conflict_current_cited | PV | 2 | 1 |  |
| rp-0216 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0222 | bad | answerable_false_abstention | PV | 2 | 1 | generation |
| rp-0230 | bad | answerable_false_abstention | PV | 5 | 1 | generation |
| rp-0232 | bad | answerable_false_abstention | PV | 5 | 1 | generation |
| rp-0234 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0236 | bad | answerable_answered_wrong_citation | PV | 1 | 2 | generation |
| rp-0238 | bad | answerable_false_abstention | PV | 5 | 1 | generation |
| rp-0245 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0247 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0249 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0251 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0253 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0255 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0259 | bad | answerable_false_abstention | PV | 8 | 1 | generation |
| rp-0263 | good | answerable_answered_gold_cited | PV | 3 | 1 |  |
| rp-0267 | bad | answerable_answered_wrong_citation | PV | 8 | 2 | generation |
| rp-0269 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0271 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0276 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0280 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0281 | good | answerable_answered_gold_cited | PV | 3 | 2 |  |
| rp-0282 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0287 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0288 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0289 | good | answerable_answered_gold_cited | PV | 4 | 1 |  |
| rp-0292 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0293 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0294 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0295 | good | answerable_answered_gold_cited | CO | 4 | 1 |  |
| rp-0296 | good | answerable_answered_gold_cited | CO | 9 | 3 |  |
| rp-0298 | good | answerable_answered_gold_cited | CO | 3 | 1 |  |
| rp-0302 | good | answerable_answered_gold_cited | CO | 4 | 1 |  |
| rp-0304 | good | answerable_answered_gold_cited | CO | 6 | 1 |  |
| rp-0315 | good | answerable_answered_gold_cited | CO | 8 | 1 |  |
| rp-0319 | good | answerable_answered_gold_cited | CO | 1 | 1 |  |
| rp-0325 | bad | answerable_answered_wrong_citation | CO | 2 | 5 | generation |
| rp-0327 | good | answerable_answered_gold_cited | CO | 7 | 1 |  |
| rp-0329 | good | answerable_answered_gold_cited | CO | 4 | 1 |  |
| rp-0331 | good | answerable_answered_gold_cited | CO | 1 | 1 |  |
| rp-0339 | good | answerable_answered_gold_cited | CO | 6 | 1 |  |
| rp-0345 | good | answerable_answered_gold_cited | CO | 3 | 1 |  |
| rp-0349 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0351 | good | conflict_current_cited | CO | 1 | 1 |  |
| rp-0363 | good | answerable_answered_gold_cited | CO | 1 | 2 |  |
| rp-0369 | good | conflict_current_cited | CO | 5 | 2 |  |
| rp-0371 | good | conflict_current_cited | CO | 2 | 1 |  |
| rp-0373 | good | conflict_current_cited | CO | 2 | 1 |  |
| rp-0377 | good | conflict_current_cited | CO | 8 | 1 |  |
| rp-0379 | bad | answerable_answered_wrong_citation | CO | 14 | 8 | generation |
| rp-0387 | good | answerable_answered_gold_cited | CO | 6 | 1 |  |
| rp-0389 | good | answerable_answered_gold_cited | CO | 2 | 1 |  |
| rp-0399 | good | answerable_answered_gold_cited | CO | 6 | 1 |  |
| rp-0403 | bad | answerable_false_abstention | CO | 18 | 6 | generation |
| rp-0407 | bad | answerable_false_abstention | CO | 8 | 1 | generation |
| rp-0415 | bad | conflict_false_abstention | CO | 13 |  | rerank |
| rp-0417 | good | conflict_current_cited | CO | 2 | 1 |  |
| rp-0419 | good | conflict_current_cited | CO | 5 | 1 |  |
| rp-0423 | bad | conflict_false_abstention | CO |  |  | recall |
| rp-0435 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0448 | good | no_answer_abstained | PV |  |  |  |
| rp-0449 | good | no_answer_abstained | PV |  |  |  |
| rp-0456 | good | no_answer_abstained | PV |  |  |  |
| rp-0458 | good | no_answer_abstained | PV |  |  |  |
| rp-0461 | good | no_answer_abstained | CO |  |  |  |
| rp-0464 | good | no_answer_abstained | CO |  |  |  |
| rp-0465 | good | no_answer_abstained | CO |  |  |  |
| rp-0466 | good | no_answer_abstained | CO |  |  |  |
| rp-0470 | good | no_answer_abstained | CO |  |  |  |
| rp-0473 | good | no_answer_abstained | PV |  |  |  |
| rp-0475 | good | no_answer_abstained | CO |  |  |  |
| rp-0476 | good | no_answer_abstained | CO |  |  |  |
| rp-0477 | good | no_answer_abstained | CO |  |  |  |
| rp-0479 | good | no_answer_abstained | CO |  |  |  |
| rp-0482 | good | no_answer_abstained | PV |  |  |  |
| rp-0494 | good | no_answer_abstained | MA |  |  |  |
| rp-0496 | good | no_answer_abstained | MA |  |  |  |
| rp-0498 | good | no_answer_abstained | MA |  |  |  |
| rp-0499 | good | no_answer_abstained | MA |  |  |  |
| rp-0501 | good | no_answer_abstained | MA |  |  |  |
| rp-0502 | good | no_answer_abstained | MA |  |  |  |
| rp-0503 | bad | no_answer_answered | MA |  |  | recall |
| rp-0504 | good | no_answer_abstained | MA |  |  |  |
| rp-0505 | good | no_answer_abstained | MA |  |  |  |
| rp-0508 | bad | answerable_false_abstention | MA | 4 | 7 | generation |
| rp-0510 | bad | answerable_false_abstention | MA | 7 | 1 | generation |
| rp-0515 | good | answerable_answered_gold_cited | MA | 1 | 2 |  |
| rp-0518 | bad | answerable_answered_wrong_citation | MA | 2 |  | rerank |
| rp-0520 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0523 | bad | answerable_false_abstention | MA | 1 | 4 | generation |
| rp-0525 | good | answerable_answered_gold_cited | MA | 4 | 1 |  |
| rp-0527 | bad | answerable_false_abstention | MA | 2 |  | rerank |
| rp-0528 | good | answerable_answered_gold_cited | MA | 2 | 2 |  |
| rp-0530 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0531 | good | answerable_answered_gold_cited | MA | 6 | 1 |  |
| rp-0532 | good | answerable_answered_gold_cited | MA | 2 | 3 |  |
| rp-0533 | bad | answerable_answered_wrong_citation | MA | 12 | 1 | generation |
| rp-0535 | bad | answerable_answered_wrong_citation | MA | 5 | 5 | generation |
| rp-0536 | bad | answerable_answered_wrong_citation | MA | 1 | 4 | generation |
| rp-0537 | bad | answerable_false_abstention | MA |  |  | recall |
| rp-0538 | good | answerable_answered_gold_cited | PV | 9 | 2 |  |
| rp-0540 | good | answerable_answered_gold_cited | PV | 1 | 3 |  |
| rp-0545 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0548 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0550 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0552 | good | answerable_answered_gold_cited | PV | 6 | 2 |  |
| rp-0554 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0556 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0558 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0559 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0561 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0562 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0563 | good | answerable_answered_gold_cited | PV | 5 | 1 |  |
| rp-0565 | good | answerable_answered_gold_cited | PV | 10 | 1 |  |
| rp-0566 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0568 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0569 | good | answerable_answered_gold_cited | CO | 8 | 1 |  |
| rp-0570 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0572 | good | answerable_answered_gold_cited | CO | 14 | 1 |  |
| rp-0574 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0575 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0576 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0577 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0578 | good | answerable_answered_gold_cited | CO | 5 | 2 |  |
| rp-0579 | good | answerable_answered_gold_cited | CO | 1 | 1 |  |
| rp-0580 | good | answerable_answered_gold_cited | CO | 3 | 1 |  |
