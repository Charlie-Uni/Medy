# Answer-context layout check on `2026-10-02-full-ask-v4-released` — 614 items, no model calls

Tokenizer: tiktoken o200k_base (proxy; the provider's tokenizer is not public). Rewritten queries from glossary-20260926-e4daca58a8e4. Parameters are the constants of `medops.harness.evidence_focus` ({"sentfocus-v8": {"keep_ratio": 0.6, "neighbours": 1, "one_sided": false, "whole_top": 1, "query_variants": 2, "markers": "v4", "source_rule": false, "title_chars": 90}}); scorer BAAI/bge-reranker-v2-m3.

| layout | answer prompt tokens / item | cut vs off | cut as share of all model tokens |
| --- | ---: | ---: | ---: |
| off | 2229.9 | 0.0% | 0.0% |
| compact-v1 | 1874.3 | 16.0% | 11.1% |
| sentfocus-v8 | 1375.1 | 38.3% | 26.6% |

Stored run: 3212.6 model tokens per item over all calls. The last column is the input-side cut only; the gate needs 25% on the provider's own count.

## sentfocus-v8

71.4% of the evidence tokens kept (22.2 of 33.0 units per item); local scoring p50 1.902 s, P95 4.116 s on mps.

| retention | kept | n | rate |
| --- | ---: | ---: | ---: |
| annotated gold key text (gold chunk in evidence) | 494 | 496 | 0.996 |
| sentence a stored claim leaned on | 983 | 1032 | 0.9525 |

Stored successes with their gold chunk in evidence: 458; of these, the gold key text is hidden for 2: ms-0057, ms-0403.

Gold key text kept, by language: en 0.9945, mixed 0.9965, zh 1.0.

This is not a quality result: whether the model answers as well from the focused prompt is only known from a replay run.
