# Answer-context layout check on `2026-10-02-full-ask-v4-released` — 614 items, no model calls

Tokenizer: tiktoken o200k_base (proxy; the provider's tokenizer is not public). Parameters fixed in `medops.harness.evidence_focus` before this run: keep ratio 0.6, whole chunks up to 60 tokens, scorer BAAI/bge-reranker-v2-m3.

| layout | answer prompt tokens / item | cut vs off | cut as share of all model tokens |
| --- | ---: | ---: | ---: |
| off | 2229.9 | 0.0% | 0.0% |
| compact-v1 | 1874.3 | 16.0% | 11.1% |
| sentfocus-v1 | 1389.7 | 37.7% | 26.2% |

Stored run: 3212.6 model tokens per item over all calls. The last column is the input-side cut only; the gate needs 25% on the provider's own count.

Sentence focus: 61.9% of the evidence tokens kept (17.7 of 33.0 units per item); local scoring p50 0.934 s, P95 2.068 s on mps.

| retention under sentfocus-v1 | kept | n | rate |
| --- | ---: | ---: | ---: |
| annotated gold key text (gold chunk in evidence) | 466 | 496 | 0.9395 |
| sentence a stored claim leaned on | 913 | 1032 | 0.8847 |

Stored successes with their gold chunk in evidence: 458; of these, the gold key text is hidden for 26: ms-0057, ms-0094, ms-0095, ms-0106, ms-0137, ms-0138, ms-0169, ms-0180, ms-0181, ms-0182, ms-0199, ms-0200, ms-0209, ms-0210, ms-0338, ms-0339, ms-0342, ms-0394, ms-0395, ms-0406, ms-0407, ms-0417, ms-0418, ms-0452, ms-0453, pc-0071.

Gold key text kept, by language: en 0.9337, mixed 0.9362, zh 1.0.

This is not a quality result: whether the model answers as well from the focused prompt is only known from a replay run.
