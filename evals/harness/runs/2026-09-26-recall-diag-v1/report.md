# Recall diagnostic 2026-09-26-recall-diag-v1 (2026-09-26)

- replay set replay-v1 (154f576a…), subset items with label bad: 60; good controls: 30
- retrieval: production hybrid config, rerank_output 8, as_of 2026-09-24, device mps; no model calls

## Failed items by stage

| stage | n | share |
| --- | ---: | ---: |
| recall | 40 | 67% |
| rerank | 2 | 3% |
| generation | 18 | 30% |

Good controls: gold in top-20 30/30, in top-8 30/30; gold rank distribution {1: 25, 2: 2, 3: 1, 4: 1, 5: 1}

## By label reason

| reason | n | recall | rerank | generation |
| --- | ---: | ---: | ---: | ---: |
| answerable_answered_wrong_citation | 20 | 13 | 1 | 6 |
| answerable_false_abstention | 36 | 23 | 1 | 12 |
| conflict_false_abstention | 3 | 3 | 0 | 0 |
| no_answer_answered | 1 | 1 | 0 | 0 |

## By department

| dept | n | recall | rerank | generation |
| --- | ---: | ---: | ---: | ---: |
| MA | 17 | 8 | 2 | 7 |
| PV | 27 | 17 | 0 | 10 |
| CO | 16 | 15 | 0 | 1 |

## Recall failures by slice

| slice | failed items with slice | of which recall |
| --- | ---: | ---: |
| dose_unit | 10 | 4 |
| drug_name_zh | 13 | 7 |
| long_context | 4 | 2 |
| mixed_zh_en | 53 | 35 |
| negation | 26 | 17 |
| no_answer | 1 | 1 |
| protocol_id | 16 | 11 |
| time_window | 9 | 4 |
| version_conflict | 3 | 3 |

Cross-lingual recall failures (Chinese query, English gold chunk): 24 of 40


## Items

| item | label | reason | dept | gold rank top-20 | gold rank top-8 | stage |
| --- | --- | --- | --- | ---: | ---: | --- |
| rp-0011 | bad | answerable_answered_wrong_citation | MA |  |  | recall |
| rp-0012 | bad | answerable_false_abstention | MA | 1 | 1 | generation |
| rp-0021 | bad | answerable_answered_wrong_citation | MA |  |  | recall |
| rp-0033 | bad | answerable_false_abstention | MA | 2 | 4 | generation |
| rp-0039 | bad | answerable_false_abstention | MA |  |  | recall |
| rp-0046 | bad | answerable_false_abstention | MA | 1 | 2 | generation |
| rp-0053 | bad | answerable_answered_wrong_citation | MA | 5 | 3 | generation |
| rp-0087 | bad | conflict_false_abstention | PV |  |  | recall |
| rp-0093 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0105 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0115 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0121 | bad | answerable_false_abstention | PV | 8 | 2 | generation |
| rp-0123 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0129 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0131 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0160 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0170 | bad | answerable_false_abstention | PV | 2 | 1 | generation |
| rp-0172 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0174 | bad | answerable_false_abstention | PV | 1 | 1 | generation |
| rp-0188 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0192 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0194 | bad | answerable_answered_wrong_citation | PV | 3 | 2 | generation |
| rp-0200 | bad | answerable_false_abstention | PV | 1 | 1 | generation |
| rp-0222 | bad | answerable_false_abstention | PV | 2 | 1 | generation |
| rp-0230 | bad | answerable_false_abstention | PV | 3 | 1 | generation |
| rp-0232 | bad | answerable_false_abstention | PV | 5 | 1 | generation |
| rp-0236 | bad | answerable_answered_wrong_citation | PV | 1 | 2 | generation |
| rp-0238 | bad | answerable_false_abstention | PV | 5 | 1 | generation |
| rp-0259 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0267 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0293 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0294 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0325 | bad | answerable_answered_wrong_citation | CO | 1 | 4 | generation |
| rp-0349 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0379 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0403 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0407 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0415 | bad | conflict_false_abstention | CO |  |  | recall |
| rp-0423 | bad | conflict_false_abstention | CO |  |  | recall |
| rp-0435 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0503 | bad | no_answer_answered | MA |  |  | recall |
| rp-0508 | bad | answerable_false_abstention | MA | 15 |  | rerank |
| rp-0510 | bad | answerable_false_abstention | MA |  |  | recall |
| rp-0518 | bad | answerable_answered_wrong_citation | MA | 11 |  | rerank |
| rp-0523 | bad | answerable_false_abstention | MA | 1 | 5 | generation |
| rp-0527 | bad | answerable_false_abstention | MA |  |  | recall |
| rp-0533 | bad | answerable_answered_wrong_citation | MA |  |  | recall |
| rp-0535 | bad | answerable_answered_wrong_citation | MA | 5 | 5 | generation |
| rp-0536 | bad | answerable_answered_wrong_citation | MA | 1 | 4 | generation |
| rp-0537 | bad | answerable_false_abstention | MA |  |  | recall |
| rp-0548 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0554 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0556 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0558 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0568 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0570 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0574 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0575 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0576 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0577 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0001 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0006 | good | answerable_answered_gold_cited | MA | 16 | 2 |  |
| rp-0008 | good | answerable_answered_gold_cited | MA | 6 | 1 |  |
| rp-0009 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0014 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0016 | good | answerable_answered_gold_cited | MA | 2 | 4 |  |
| rp-0023 | good | answerable_answered_gold_cited | MA | 7 | 1 |  |
| rp-0026 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0028 | good | answerable_answered_gold_cited | MA | 18 | 1 |  |
| rp-0032 | good | answerable_answered_gold_cited | MA | 5 | 1 |  |
| rp-0034 | good | answerable_answered_gold_cited | MA | 3 | 5 |  |
| rp-0035 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0038 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0044 | good | answerable_answered_gold_cited | MA | 6 | 1 |  |
| rp-0047 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0048 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0052 | good | answerable_answered_gold_cited | MA | 6 | 1 |  |
| rp-0055 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0057 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0058 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0060 | good | answerable_answered_gold_cited | MA | 6 | 1 |  |
| rp-0065 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0066 | good | answerable_answered_gold_cited | MA | 7 | 3 |  |
| rp-0067 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0069 | good | answerable_answered_gold_cited | MA | 15 | 1 |  |
| rp-0071 | good | answerable_answered_gold_cited | MA | 5 | 1 |  |
| rp-0073 | good | answerable_answered_gold_cited | MA | 12 | 2 |  |
| rp-0076 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0079 | good | answerable_answered_gold_cited | MA | 12 | 1 |  |
| rp-0080 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
