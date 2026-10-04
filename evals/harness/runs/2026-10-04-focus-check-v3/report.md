# Answer-context layout check on `2026-10-02-full-ask-v4-released` — 614 items, no model calls

Tokenizer: tiktoken o200k_base (proxy; the provider's tokenizer is not public). Rewritten queries from glossary-20260926-e4daca58a8e4. Parameters are the constants of `medops.harness.evidence_focus` ({"sentfocus-v3": {"keep_ratio": 0.6, "neighbours": 1, "whole_top": 0, "query_variants": 2}}); scorer BAAI/bge-reranker-v2-m3.

| layout | answer prompt tokens / item | cut vs off | cut as share of all model tokens |
| --- | ---: | ---: | ---: |
| off | 2229.9 | 0.0% | 0.0% |
| compact-v1 | 1874.3 | 16.0% | 11.1% |
| sentfocus-v3 | 1476.1 | 33.8% | 23.5% |

Stored run: 3212.6 model tokens per item over all calls. The last column is the input-side cut only; the gate needs 25% on the provider's own count.

## sentfocus-v3

70.0% of the evidence tokens kept (21.4 of 33.0 units per item); local scoring p50 2.12 s, P95 4.522 s on mps.

| retention | kept | n | rate |
| --- | ---: | ---: | ---: |
| annotated gold key text (gold chunk in evidence) | 484 | 496 | 0.9758 |
| sentence a stored claim leaned on | 936 | 1032 | 0.907 |

Stored successes with their gold chunk in evidence: 458; of these, the gold key text is hidden for 12: ms-0057, ms-0084, ms-0085, ms-0111, ms-0161, ms-0213, ms-0251, ms-0302, ms-0330, ms-0331, ms-0403, ms-0406.

Gold key text kept, by language: en 0.9724, mixed 0.9752, zh 1.0.

This is not a quality result: whether the model answers as well from the focused prompt is only known from a replay run.
