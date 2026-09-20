#!/bin/sh
# DEC-001 run 2 (final, ADR-0002 amendment 1): assemble + freeze probe v2, map golds on the three medops_v2
# servers, run the pre-registered comparison and evaluate. Run from the repository root after the LLM
# re-review has finished and every remaining dispute has a human resolution. Stops at the first failure.
set -eu
PY="env -u DEBUG -u PYTHONPATH venv/bin/python"
V2=evals/probe/precise_clause/v2
PAGES=evals/probe/precise_clause/v1/pages
TOOLS=evals/probe/precise_clause/drafts/v2/tooling
S=evals/experiments/lexical/preparation-v1/servers_v2
RUN=${RUN_ID:-2026-09-20-run2-final}
CONFIRMED=${HUMAN_CONFIRMED:-2026-09-20}

echo "== assemble v2 (draft)"; $PY $TOOLS/assemble_v2.py --out $V2 --human-confirmed "$CONFIRMED"
echo "== freeze v2";           $PY $TOOLS/freeze_v2.py $V2 --pages $PAGES
for X in a b c; do
  echo "== mapping $X";        $PY -m medops.evals.probe.chunk_mapping $V2 --pages $PAGES --chunks $S/$X/chunks.snapshot.json --out $S/$X/chunk_mapping.chunker-v2.probe-v2.json || test $? -eq 1
done
echo "== run";                 $PY -m medops.evals.experiments.dec001_run --dataset $V2 --out evals/experiments/lexical/runs/$RUN --as-of 2026-09-20 --database medops_v2 \
  --mapping-a $S/a/chunk_mapping.chunker-v2.probe-v2.json --mapping-b $S/b/chunk_mapping.chunker-v2.probe-v2.json --mapping-c $S/c/chunk_mapping.chunker-v2.probe-v2.json \
  --purpose "Run 2 final (ADR-0002 amendment 1): frozen probe v2 (107 samples: 75 v1 + 32 confirmed English twins, all re-reviewed by claude-opus-5), medops_v2 databases (chunker-v2, 16 active documents), hard gates on the language_matched scope, cross_lingual reported separately"
echo "== evaluate";            $PY -m medops.evals.experiments.dec001_report evals/experiments/lexical/runs/$RUN
