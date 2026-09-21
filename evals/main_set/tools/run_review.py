"""LLM second review of the main-set draft batches through the Claude Code CLI with a pinned model (spec-m1 §4
step 3; wire format, chunk evidence and resume semantics identical to the probe v2 runner, whose helpers are
imported by path so that review_provenance reconstructs the same prompt bytes).

    python evals/main_set/tools/run_review.py MA [--chunk 5] [--model claude-opus-5] [--effort high] [--only ms-0001 ...]

Batch NA uses the no-answer verdict items {query, absence, slices, dept}; all other batches use the five
answerable items. Rejected replies are kept under review/bad_replies/ (ignored).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import draft_common as dc  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "v2_codex_tooling", dc.REPO / "evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py"
)
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)

REVIEW = dc.DRAFTS / "review"
PROMPT_FILE = dc.DRAFTS / "review_prompt.md"
ITEM_KEYS = {
    "MA": codex.ITEM_KEYS,
    "PV": codex.ITEM_KEYS,
    "CO": codex.ITEM_KEYS,
    "EN": codex.ITEM_KEYS,
    "NA": ("query", "absence", "slices", "dept"),
}
SYSTEM_PROMPT = (
    "You are an independent second reviewer. Follow the instructions in the user message exactly and output "
    "only what they ask for."
)


def parse_reply(text: str, expected_ids: list[str], keys: tuple[str, ...]) -> list[dict]:
    body = re.sub(r"^```(?:json)?\s*$", "", text, flags=re.M).strip()
    out: dict[str, dict] = {}
    for n, line in enumerate(body.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            v = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {n} is not JSON: {e}: {line[:120]}") from e
        if not isinstance(v, dict) or set(v) - {"sample_id", "verdict", "items", "reason", "suggestion"}:
            raise ValueError(f"line {n}: verdict must contain only the allowed fields")
        sid = v.get("sample_id")
        if sid not in expected_ids or sid in out:
            raise ValueError(f"line {n}: unexpected or duplicate sample_id {sid!r}")
        items = v.get("items")
        if not isinstance(items, dict) or set(items) != set(keys) or any(items[k] not in ("ok", "issue") for k in keys):
            raise ValueError(f"{sid}: bad items {items!r}")
        expected = "dispute" if any(items[k] == "issue" for k in keys) else "agree"
        if v.get("verdict") != expected:
            raise ValueError(f"{sid}: verdict {v.get('verdict')!r} disagrees with items")
        v.setdefault("reason", "")
        v.setdefault("suggestion", "")
        if not isinstance(v["reason"], str) or not isinstance(v["suggestion"], str):
            raise ValueError(f"{sid}: reason and suggestion must be strings")
        if expected == "dispute" and not v["reason"].strip():
            raise ValueError(f"{sid}: dispute requires a reason")
        out[sid] = v
    missing = [i for i in expected_ids if i not in out]
    if missing:
        raise ValueError(f"missing verdicts for {missing}")
    return [out[i] for i in expected_ids]


def run_chunk(
    binary: str, model: str, effort: str, prompt: str, workdir: pathlib.Path, version: str
) -> tuple[str, dict]:
    reply, meta = dc.run_claude(binary, model, effort, SYSTEM_PROMPT, prompt, workdir, timeout=1800)
    return reply, {
        "returncode": 0,
        "cli": "claude-code",
        "cli_version": version,
        "model": meta["model_observed"],
        "session_id": meta["session_id"],
        "reasoning_effort": effort,
        "effort_source": "requested --effort flag; not echoed by the CLI",
        "tokens_used": str(meta["input_tokens"] + meta["output_tokens"]),
        "cost_usd": meta["cost_usd"],
        "system_prompt_sha256": meta["system_prompt_sha256"],
        "tools_disabled": True,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", choices=sorted(ITEM_KEYS))
    ap.add_argument("--chunk", type=int, default=5)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--binary", default=dc.DEFAULT_BINARY)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--max-chunks", type=int, default=None, help="stop after N chunks (the run stays resumable)")
    args = ap.parse_args()
    if args.chunk < 1:
        ap.error("--chunk must be positive")
    keys = tuple(ITEM_KEYS[args.batch])
    prompt_text = PROMPT_FILE.read_bytes().decode("utf-8")
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    all_records = codex.load_records(REVIEW / f"input_{args.batch}.jsonl")
    all_ids = [r["sample_id"] for r in all_records]
    if len(set(all_ids)) != len(all_ids) or not all_records:
        sys.exit("duplicate or empty input")
    run_path = REVIEW / f"run_{args.batch}.json"
    out_path = REVIEW / f"verdicts_{args.batch}.jsonl"
    version = dc.cli_version(args.binary)
    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        for key, value in (
            ("model", args.model),
            ("reasoning_effort_requested", args.effort),
            ("review_prompt_sha256", prompt_hash),
        ):
            if run.get(key) != value:
                sys.exit(f"cannot resume: {key} changed; archive and rerun")
        current = {r["sample_id"]: codex.record_hash(r) for r in all_records}
        if args.only is None and run.get("active_review"):
            pending = set(run["active_review"]["pending_ids"])
            if run["active_review"]["sample_input_sha256"] != {
                sid: current[sid] for sid in sorted(run["active_review"]["sample_input_sha256"])
            }:
                sys.exit("cannot resume: inputs of the unfinished selection changed")
            records = [r for r in all_records if r["sample_id"] in pending]
        elif args.only is not None:
            selected = set(args.only)
            if not selected or not selected.issubset(all_ids):
                sys.exit("--only must name existing sample_ids")
            changed_outside = [
                sid for sid, h in current.items() if sid not in selected and run["sample_input_sha256"].get(sid) != h
            ]
            if changed_outside or set(current) != set(run["sample_input_sha256"]):
                sys.exit(f"cannot reuse verdicts: inputs changed outside --only: {changed_outside[:5]}")
            records = codex.start_targeted_review(run, all_records, selected)
        else:
            sys.exit("review already complete; rerun individual samples with --only or archive the run")
    else:
        if out_path.exists():
            sys.exit("verdicts exist without a run record; archive them first")
        run = {
            "batch": args.batch,
            "reviewer_cli": "claude-code",
            "cli_binary": args.binary,
            "cli_version": version,
            "model": args.model,
            "model_version_source": "pinned_model_id",
            "reasoning_effort_requested": args.effort,
            "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            "review_prompt_sha256": prompt_hash,
            "sample_input_sha256": {r["sample_id"]: codex.record_hash(r) for r in all_records},
            "chunks": [],
            "provenance_version": 2,
            "latest": {},
            "active_review": None,
        }
        records = codex.start_targeted_review(run, all_records, set(all_ids))
    codex.checkpoint(run, run_path, out_path)
    with tempfile.TemporaryDirectory(prefix="main-review-") as tmp:
        workdir = pathlib.Path(tmp)
        for n_chunk, i in enumerate(range(0, len(records), args.chunk)):
            if args.max_chunks is not None and n_chunk >= args.max_chunks:
                print(f"stopping after {n_chunk} chunks (--max-chunks); rerun without --only to resume", flush=True)
                break
            chunk = records[i : i + args.chunk]
            ids = [r["sample_id"] for r in chunk]
            prompt = codex.build_prompt(prompt_text, chunk)
            started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
            reply, meta = run_chunk(args.binary, args.model, args.effort, prompt, workdir, version)
            try:
                parsed = parse_reply(reply, ids, keys)
            except ValueError as e:
                bad = REVIEW / "bad_replies" / f"input_{args.batch}_{ids[0]}_bad.jsonl"
                codex.atomic_write(bad, json.dumps({"raw_reply": reply}, ensure_ascii=False) + "\n")
                sys.exit(f"chunk {ids[0]}..{ids[-1]}: {e} (raw reply saved; rerun resumes pending ids)")
            meta.update(
                {
                    "sample_ids": ids,
                    "started_at": started,
                    "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                    "prompt_chars": len(prompt),
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "verdicts": parsed,
                }
            )
            codex.save_chunk_inputs(meta, chunk, REVIEW)
            codex.verify_chunk(meta, chunk, prompt_text, args.model, args.effort, REVIEW)
            index = len(run["chunks"])
            run["chunks"].append(meta)
            for v in parsed:
                run["latest"][v["sample_id"]] = codex.binding(meta, index, v)
                run["active_review"]["pending_ids"].remove(v["sample_id"])
            if not run["active_review"]["pending_ids"]:
                run["active_review"] = None
            codex.checkpoint(run, run_path, out_path)
            print(
                f"{ids[0]}..{ids[-1]}: {sum(v['verdict'] == 'dispute' for v in parsed)} dispute / {len(parsed)}; cost {meta['cost_usd']}",
                flush=True,
            )
    verdicts = codex.current_verdicts(run)
    cost = sum(float(c.get("cost_usd") or 0) for c in run["chunks"])
    print(
        f"{args.batch}: {len(verdicts)} verdicts, {sum(v['verdict'] == 'dispute' for v in verdicts.values())} disputes, "
        f"${cost:.2f} so far -> {out_path.relative_to(dc.REPO)}"
    )


if __name__ == "__main__":
    main()
