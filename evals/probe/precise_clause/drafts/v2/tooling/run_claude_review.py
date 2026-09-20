# -*- coding: utf-8 -*-
"""Drive the LLM second review through the Claude Code CLI with a pinned model (owner decision 2026-09-20,
option 2: one uniform reviewer, claude-opus-5, for all 107 v2 samples; reviewer must not be the drafter).

    python evals/probe/precise_clause/drafts/v2/tooling/run_claude_review.py MA [--chunk 5] [--model claude-opus-5]
        [--effort high] [--binary ~/.local/bin/claude] [--only pc-0001 ...]

Same wire format and evidence records as the v1 codex runner (build_prompt / parse_reply / chunk bindings are
imported from run_codex_review.py, so review_provenance validation reconstructs the identical prompt bytes).
Differences, all recorded in the run file: the CLI is Claude Code (`claude -p`), tools are disabled, sessions
are not persisted, user settings are not loaded, a fixed neutral system prompt is used (its SHA-256 is stored),
the model identifier is pinned and echoed back by the CLI (`modelUsage`), the reasoning effort is the requested
`--effort` flag (the CLI does not echo it; recorded as such). Rejected replies are kept in an ignored file.
"""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("v2_codex_tooling", HERE / "run_codex_review.py")
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)

REVIEW = codex.REVIEW
PROMPT_FILE = codex.PROMPT_FILE
DEFAULT_BINARY = str(pathlib.Path.home() / ".local/bin/claude")
SYSTEM_PROMPT = (
    "You are an independent second reviewer. Follow the instructions in the user message exactly and output "
    "only what they ask for."
)


def cli_version(binary: str) -> str:
    out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60)
    return (out.stdout or out.stderr).strip().splitlines()[0]


def run_chunk(binary: str, model: str, effort: str, prompt: str, workdir: pathlib.Path, version: str) -> tuple[str, dict]:
    cmd = [
        binary, "-p", "--model", model, "--effort", effort, "--tools", "", "--no-session-persistence",
        "--setting-sources", "", "--system-prompt", SYSTEM_PROMPT, "--output-format", "json",
    ]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1800, cwd=workdir)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude exec returned non-JSON ({proc.returncode}): {(proc.stdout + proc.stderr)[-1200:]}") from exc
    usage = data.get("modelUsage") or {}
    observed_model = next(iter(usage)) if len(usage) == 1 else None
    tokens = sum(int(u.get("inputTokens", 0)) + int(u.get("outputTokens", 0)) for u in usage.values())
    meta = {
        "returncode": 0 if proc.returncode == 0 and not data.get("is_error") and data.get("subtype") == "success" else 1,
        "cli": "claude-code",
        "cli_version": version,
        "model": observed_model,
        "session_id": data.get("session_id"),
        "reasoning_effort": effort,
        "effort_source": "requested --effort flag; not echoed by the CLI",
        "tokens_used": str(tokens),
        "cost_usd": data.get("total_cost_usd"),
        "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "tools_disabled": True,
    }
    if meta["returncode"] != 0:
        raise RuntimeError(f"claude exec failed: {json.dumps(data)[:1200]}")
    return str(data.get("result", "")), meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--chunk", type=int, default=5)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--only", nargs="*", help="sample_ids to (re)run; without it an unfinished run resumes its pending ids")
    args = ap.parse_args()
    if args.chunk < 1:
        ap.error("--chunk must be positive")
    prompt_text = PROMPT_FILE.read_bytes().decode("utf-8")
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    all_records = codex.load_records(REVIEW / f"input_{args.batch}.jsonl")
    all_ids = [r["sample_id"] for r in all_records]
    if len(set(all_ids)) != len(all_ids) or not all_records:
        sys.exit("duplicate or empty input")
    run_path = REVIEW / f"run_{args.batch}.json"
    out_path = REVIEW / f"verdicts_{args.batch}.jsonl"
    version = cli_version(args.binary)
    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        for key, value in (("model", args.model), ("reasoning_effort_requested", args.effort), ("review_prompt_sha256", prompt_hash)):
            if run.get(key) != value:
                sys.exit(f"cannot resume: {key} changed; archive and rerun")
        current = {r["sample_id"]: codex.record_hash(r) for r in all_records}
        if args.only is None and run.get("active_review"):
            pending = set(run["active_review"]["pending_ids"])
            if run["active_review"]["sample_input_sha256"] != {sid: current[sid] for sid in sorted(run["active_review"]["sample_input_sha256"])}:
                sys.exit("cannot resume: inputs of the unfinished selection changed")
            selected = pending
            records = [r for r in all_records if r["sample_id"] in selected]
        elif args.only is not None:
            selected = set(args.only)
            if not selected or not selected.issubset(all_ids):
                sys.exit("--only must name existing sample_ids")
            changed_outside = [sid for sid, h in current.items() if sid not in selected and run["sample_input_sha256"].get(sid) != h]
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
    with tempfile.TemporaryDirectory(prefix="claude-review-") as tmp:
        workdir = pathlib.Path(tmp)
        for i in range(0, len(records), args.chunk):
            chunk = records[i : i + args.chunk]
            ids = [r["sample_id"] for r in chunk]
            prompt = codex.build_prompt(prompt_text, chunk)
            started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
            reply, meta = run_chunk(args.binary, args.model, args.effort, prompt, workdir, version)
            if meta["model"] != args.model:
                sys.exit(f"{ids}: observed model {meta['model']} differs from request; no verdict written")
            try:
                parsed = codex.parse_reply(reply, ids)
            except ValueError as e:
                bad_path = REVIEW / "bad_replies" / f"input_{args.batch}_{ids[0]}_bad.jsonl"
                codex.atomic_write(bad_path, json.dumps({"raw_reply": reply}, ensure_ascii=False) + "\n")
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
                f"{ids[0]}..{ids[-1]}: {sum(v['verdict'] == 'dispute' for v in parsed)} dispute / {len(parsed)}; "
                f"tokens {meta['tokens_used']}; cost {meta['cost_usd']}; session {meta['session_id']}",
                flush=True,
            )
    verdicts = codex.current_verdicts(run)
    print(f"{args.batch}: {len(verdicts)} verdicts, {sum(v['verdict'] == 'dispute' for v in verdicts.values())} disputes -> {out_path.relative_to(codex.REPO)}")


if __name__ == "__main__":
    main()
