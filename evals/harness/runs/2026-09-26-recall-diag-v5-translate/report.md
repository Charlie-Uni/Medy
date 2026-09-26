# Recall diagnostic 2026-09-26-recall-diag-v5-translate (2026-09-26)

- replay set replay-v1 (154f576a…), subset items with label bad: 60; good controls: 60
- retrieval: production hybrid config, rerank_output 8, glossary glossary-20260926-e4daca58a8e4, multi_query True, doc_focus True, query_translation gpt-6-luna, as_of 2026-09-24, device mps; no model calls

## Failed items by stage

| stage | n | share |
| --- | ---: | ---: |
| recall | 21 | 35% |
| rerank | 4 | 7% |
| generation | 35 | 58% |

Good controls: gold in top-20 60/60, in top-8 60/60; gold rank distribution {1: 49, 2: 7, 3: 2, 4: 2}

## By label reason

| reason | n | recall | rerank | generation |
| --- | ---: | ---: | ---: | ---: |
| answerable_answered_wrong_citation | 20 | 7 | 2 | 11 |
| answerable_false_abstention | 36 | 10 | 2 | 24 |
| conflict_false_abstention | 3 | 3 | 0 | 0 |
| no_answer_answered | 1 | 1 | 0 | 0 |

## By department

| dept | n | recall | rerank | generation |
| --- | ---: | ---: | ---: | ---: |
| MA | 17 | 1 | 2 | 14 |
| PV | 27 | 9 | 1 | 17 |
| CO | 16 | 11 | 1 | 4 |

## Recall failures by slice

| slice | failed items with slice | of which recall |
| --- | ---: | ---: |
| dose_unit | 10 | 2 |
| drug_name_zh | 13 | 1 |
| long_context | 4 | 1 |
| mixed_zh_en | 53 | 21 |
| negation | 26 | 7 |
| no_answer | 1 | 1 |
| protocol_id | 16 | 7 |
| time_window | 9 | 2 |
| version_conflict | 3 | 3 |

Cross-lingual recall failures (Chinese query, English gold chunk): 13 of 21


## Items

| item | label | reason | dept | gold rank top-20 | gold rank top-8 | stage |
| --- | --- | --- | --- | ---: | ---: | --- |
| rp-0011 | bad | answerable_answered_wrong_citation | MA | 10 | 1 | generation |
| rp-0012 | bad | answerable_false_abstention | MA | 1 | 1 | generation |
| rp-0021 | bad | answerable_answered_wrong_citation | MA | 2 | 2 | generation |
| rp-0033 | bad | answerable_false_abstention | MA | 2 | 4 | generation |
| rp-0039 | bad | answerable_false_abstention | MA | 3 | 2 | generation |
| rp-0046 | bad | answerable_false_abstention | MA | 2 | 2 | generation |
| rp-0053 | bad | answerable_answered_wrong_citation | MA | 1 | 3 | generation |
| rp-0087 | bad | conflict_false_abstention | PV |  |  | recall |
| rp-0093 | bad | answerable_false_abstention | PV | 7 | 1 | generation |
| rp-0105 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0115 | bad | answerable_false_abstention | PV | 16 | 1 | generation |
| rp-0121 | bad | answerable_false_abstention | PV | 5 | 3 | generation |
| rp-0123 | bad | answerable_false_abstention | PV | 14 | 1 | generation |
| rp-0129 | bad | answerable_false_abstention | PV | 13 | 2 | generation |
| rp-0131 | bad | answerable_false_abstention | PV | 6 |  | rerank |
| rp-0160 | bad | answerable_false_abstention | PV | 19 | 2 | generation |
| rp-0170 | bad | answerable_false_abstention | PV | 1 | 1 | generation |
| rp-0172 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0174 | bad | answerable_false_abstention | PV | 1 | 1 | generation |
| rp-0188 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0192 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0194 | bad | answerable_answered_wrong_citation | PV | 1 | 2 | generation |
| rp-0200 | bad | answerable_false_abstention | PV | 4 | 2 | generation |
| rp-0222 | bad | answerable_false_abstention | PV | 1 | 1 | generation |
| rp-0230 | bad | answerable_false_abstention | PV | 9 | 1 | generation |
| rp-0232 | bad | answerable_false_abstention | PV | 3 | 1 | generation |
| rp-0236 | bad | answerable_answered_wrong_citation | PV | 1 | 2 | generation |
| rp-0238 | bad | answerable_false_abstention | PV | 3 | 1 | generation |
| rp-0259 | bad | answerable_false_abstention | PV | 15 | 1 | generation |
| rp-0267 | bad | answerable_answered_wrong_citation | PV | 13 | 3 | generation |
| rp-0293 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0294 | bad | answerable_answered_wrong_citation | CO | 18 | 2 | generation |
| rp-0325 | bad | answerable_answered_wrong_citation | CO | 1 | 6 | generation |
| rp-0349 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0379 | bad | answerable_answered_wrong_citation | CO | 13 |  | rerank |
| rp-0403 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0407 | bad | answerable_false_abstention | CO | 6 | 1 | generation |
| rp-0415 | bad | conflict_false_abstention | CO |  |  | recall |
| rp-0423 | bad | conflict_false_abstention | CO |  |  | recall |
| rp-0435 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0503 | bad | no_answer_answered | MA |  |  | recall |
| rp-0508 | bad | answerable_false_abstention | MA | 4 | 7 | generation |
| rp-0510 | bad | answerable_false_abstention | MA | 7 | 1 | generation |
| rp-0518 | bad | answerable_answered_wrong_citation | MA | 2 |  | rerank |
| rp-0523 | bad | answerable_false_abstention | MA | 1 | 5 | generation |
| rp-0527 | bad | answerable_false_abstention | MA | 2 |  | rerank |
| rp-0533 | bad | answerable_answered_wrong_citation | MA | 12 | 1 | generation |
| rp-0535 | bad | answerable_answered_wrong_citation | MA | 3 | 5 | generation |
| rp-0536 | bad | answerable_answered_wrong_citation | MA | 1 | 4 | generation |
| rp-0537 | bad | answerable_false_abstention | MA | 12 | 1 | generation |
| rp-0548 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0554 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0556 | bad | answerable_false_abstention | PV |  |  | recall |
| rp-0558 | bad | answerable_answered_wrong_citation | PV |  |  | recall |
| rp-0568 | bad | answerable_false_abstention | CO | 13 | 1 | generation |
| rp-0570 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0574 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0575 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0576 | bad | answerable_false_abstention | CO |  |  | recall |
| rp-0577 | bad | answerable_answered_wrong_citation | CO |  |  | recall |
| rp-0001 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0006 | good | answerable_answered_gold_cited | MA | 4 | 2 |  |
| rp-0008 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0009 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0014 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0016 | good | answerable_answered_gold_cited | MA | 2 | 4 |  |
| rp-0023 | good | answerable_answered_gold_cited | MA | 5 | 1 |  |
| rp-0026 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0028 | good | answerable_answered_gold_cited | MA | 4 | 1 |  |
| rp-0032 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0034 | good | answerable_answered_gold_cited | MA | 1 | 2 |  |
| rp-0035 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0038 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0044 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0047 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0048 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0052 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0055 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0057 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0058 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0060 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0065 | good | answerable_answered_gold_cited | MA | 3 | 1 |  |
| rp-0066 | good | answerable_answered_gold_cited | MA | 3 | 3 |  |
| rp-0067 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0069 | good | answerable_answered_gold_cited | MA | 8 | 1 |  |
| rp-0071 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0073 | good | answerable_answered_gold_cited | MA | 4 | 2 |  |
| rp-0076 | good | answerable_answered_gold_cited | MA | 1 | 1 |  |
| rp-0079 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0080 | good | answerable_answered_gold_cited | MA | 2 | 1 |  |
| rp-0081 | good | conflict_current_cited | PV | 2 | 1 |  |
| rp-0083 | good | conflict_current_cited | PV | 1 | 1 |  |
| rp-0089 | good | conflict_current_cited | PV | 1 | 2 |  |
| rp-0104 | good | answerable_answered_gold_cited | PV | 3 | 1 |  |
| rp-0107 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0125 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0132 | good | answerable_answered_gold_cited | PV | 15 | 1 |  |
| rp-0134 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0138 | good | answerable_answered_gold_cited | PV | 9 | 2 |  |
| rp-0146 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0150 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0154 | good | answerable_answered_gold_cited | PV | 1 | 2 |  |
| rp-0162 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0164 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0166 | good | answerable_answered_gold_cited | PV | 18 | 2 |  |
| rp-0178 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0180 | good | answerable_answered_gold_cited | PV | 2 | 4 |  |
| rp-0182 | good | answerable_answered_gold_cited | PV | 1 | 3 |  |
| rp-0190 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0202 | good | conflict_current_cited | PV | 2 | 1 |  |
| rp-0206 | good | conflict_current_cited | PV | 2 | 1 |  |
| rp-0208 | good | conflict_current_cited | PV | 1 | 1 |  |
| rp-0216 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0234 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0245 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0247 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0249 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0251 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
| rp-0253 | good | answerable_answered_gold_cited | PV | 2 | 1 |  |
| rp-0255 | good | answerable_answered_gold_cited | PV | 1 | 1 |  |
