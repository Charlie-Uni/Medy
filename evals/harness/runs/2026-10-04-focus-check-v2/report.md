# Answer-context layout check on `2026-10-02-full-ask-v4-released` — 614 items, no model calls

Tokenizer: tiktoken o200k_base (proxy; the provider's tokenizer is not public). Rewritten queries from glossary-20260926-e4daca58a8e4. Parameters are the constants of `medops.harness.evidence_focus` ({"sentfocus-v1": {"keep_ratio": 0.6, "neighbours": 0, "whole_top": 0, "query_variants": 1}, "sentfocus-v2": {"keep_ratio": 0.6, "neighbours": 1, "whole_top": 1, "query_variants": 2}}); scorer BAAI/bge-reranker-v2-m3.

| layout | answer prompt tokens / item | cut vs off | cut as share of all model tokens |
| --- | ---: | ---: | ---: |
| off | 2229.9 | 0.0% | 0.0% |
| compact-v1 | 1874.3 | 16.0% | 11.1% |
| sentfocus-v1 | 1389.7 | 37.7% | 26.2% |
| sentfocus-v2 | 1491.4 | 33.1% | 23.0% |

Stored run: 3212.6 model tokens per item over all calls. The last column is the input-side cut only; the gate needs 25% on the provider's own count.

## sentfocus-v1

61.9% of the evidence tokens kept (17.7 of 33.0 units per item); local scoring p50 1.135 s, P95 2.779 s on mps.

| retention | kept | n | rate |
| --- | ---: | ---: | ---: |
| annotated gold key text (gold chunk in evidence) | 466 | 496 | 0.9395 |
| sentence a stored claim leaned on | 913 | 1032 | 0.8847 |

Stored successes with their gold chunk in evidence: 458; of these, the gold key text is hidden for 26: ms-0057, ms-0094, ms-0095, ms-0106, ms-0137, ms-0138, ms-0169, ms-0180, ms-0181, ms-0182, ms-0199, ms-0200, ms-0209, ms-0210, ms-0338, ms-0339, ms-0342, ms-0394, ms-0395, ms-0406, ms-0407, ms-0417, ms-0418, ms-0452, ms-0453, pc-0071.

Gold key text kept, by language: en 0.9337, mixed 0.9362, zh 1.0.

## sentfocus-v2

71.4% of the evidence tokens kept (22.2 of 33.0 units per item); local scoring p50 1.888 s, P95 4.102 s on mps.

| retention | kept | n | rate |
| --- | ---: | ---: | ---: |
| annotated gold key text (gold chunk in evidence) | 494 | 496 | 0.996 |
| sentence a stored claim leaned on | 983 | 1032 | 0.9525 |

Stored successes with their gold chunk in evidence: 458; of these, the gold key text is hidden for 2: ms-0057, ms-0403.

Gold key text kept, by language: en 0.9945, mixed 0.9965, zh 1.0.

This is not a quality result: whether the model answers as well from the focused prompt is only known from a replay run.
