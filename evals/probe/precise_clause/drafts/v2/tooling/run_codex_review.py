"""Drive the LLM second review through the Codex CLI (SPEC section 8; reviewer must not be the drafter).

    python evals/probe/precise_clause/drafts/v1/tooling/run_codex_review.py MA [--chunk 5] [--model gpt-6-astra]
        [--codex /Applications/ChatGPT.app/Contents/Resources/codex]

For each chunk of review/input_<batch>.jsonl the prompt is: the verbatim v1/review_prompt.md, then the samples
(with page text), then one line asking for exactly N JSON lines. Codex runs non-interactively in a clean
scratch directory with a read-only sandbox and user config ignored, so it sees nothing but the prompt.
Every reply is parsed and checked (one verdict per sample, ids match, verdict/items well-formed) before it is
appended. Outputs: review/verdicts_<batch>.jsonl and review/run_<batch>.json (CLI version, model, session ids,
token counts, timestamps, sha256 of the prompt file) for the manifest's model/model_version record.
"""

import argparse
import copy
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[6]
V1 = REPO / "evals/probe/precise_clause/v2"  # version directory under construction (name kept from the v1 tooling)
PAGES = REPO / "evals/probe/precise_clause/v1/pages"  # page texts are shared with v1 (same extraction)
PROMPT_FILE = REPO / "evals/probe/precise_clause/v1/review_prompt.md"  # v2 keeps the v1 prompt byte-identical
REVIEW = REPO / "evals/probe/precise_clause/drafts/v2/review"
ITEM_KEYS = ("query", "slices", "key_text", "evidence_span", "dept")
DEFAULT_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"


def record_hash(record: dict) -> str:
    data = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def validate_resume(
    runs: dict, prompt_hash: str, model: str, effort: str, records: list[dict], only: set[str] | None = None
) -> None:
    expected = {
        "review_prompt_sha256": prompt_hash,
        "model": model,
        "reasoning_effort_requested": effort,
    }
    for key, value in expected.items():
        if runs.get(key) != value:
            raise ValueError(f"cannot reuse verdicts: {key} changed or was not recorded; archive and rerun")
    current = {r["sample_id"]: record_hash(r) for r in records}
    previous = runs.get("sample_input_sha256", {})
    if len(current) != len(records):
        raise ValueError("duplicate input sample_id")
    if only is not None and (not only or not only.issubset(current)):
        raise ValueError("--only must name at least one existing sample_id")
    if set(current) != set(previous) or any(
        previous[sid] != h for sid, h in current.items() if sid not in (only or set())
    ):
        raise ValueError("cannot reuse verdicts: sample_input_sha256 changed outside --only or was not recorded")


def build_prompt(prompt_text: str, records: list[dict]) -> str:
    parts = [
        "下面第一部分是复核提示原文，第二部分是本轮要复核的样本（每条含 gold 页的页文本）。",
        f"严格按复核提示的输出格式作答：只输出 JSON 行，每条样本一行，共 {len(records)} 行，不要任何其他文字或代码围栏。",
        "",
        "===== 第一部分：复核提示 =====",
        prompt_text.rstrip("\n"),
        "",
        "===== 第二部分：样本 =====",
    ]
    for r in records:
        parts.append(json.dumps(r, ensure_ascii=False))
    parts.append("")
    parts.append(f"===== 结束：请输出 {len(records)} 行 JSON =====")
    return "\n".join(parts) + "\n"


def parse_reply(text: str, expected_ids: list[str]) -> list[dict]:
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
        allowed = {"sample_id", "verdict", "items", "reason", "suggestion"}
        if not isinstance(v, dict) or set(v) - allowed:
            raise ValueError(f"line {n}: verdict must be an object containing only the allowed verdict fields")
        sid = v.get("sample_id")
        if sid not in expected_ids:
            raise ValueError(f"line {n}: unexpected sample_id {sid!r}")
        if sid in out:
            raise ValueError(f"duplicate verdict for {sid}")
        if v.get("verdict") not in ("agree", "dispute"):
            raise ValueError(f"{sid}: bad verdict {v.get('verdict')!r}")
        items = v.get("items")
        if (
            not isinstance(items, dict)
            or set(items) != set(ITEM_KEYS)
            or any(items[k] not in ("ok", "issue") for k in ITEM_KEYS)
        ):
            raise ValueError(f"{sid}: bad items {items!r}")
        if v["verdict"] == "agree" and any(items[k] == "issue" for k in ITEM_KEYS):
            raise ValueError(f"{sid}: agree with an issue item")
        if v["verdict"] == "dispute" and all(items[k] == "ok" for k in ITEM_KEYS):
            raise ValueError(f"{sid}: dispute with all items ok")
        v.setdefault("reason", "")
        v.setdefault("suggestion", "")
        if not isinstance(v["reason"], str) or not isinstance(v["suggestion"], str):
            raise ValueError(f"{sid}: reason and suggestion must be strings")
        if v["verdict"] == "dispute" and not v["reason"].strip():
            raise ValueError(f"{sid}: dispute requires a reason")
        out[sid] = v
    missing = [i for i in expected_ids if i not in out]
    if missing:
        raise ValueError(f"missing verdicts for {missing}")
    return [out[i] for i in expected_ids]


def atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        tmp = pathlib.Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def load_records(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def actual_prompt_hash(prompt_text: str, records: list[dict]) -> str:
    return hashlib.sha256(build_prompt(prompt_text, records).encode("utf-8")).hexdigest()


def save_chunk_inputs(chunk: dict, records: list[dict], input_dir: pathlib.Path) -> None:
    """Page text belongs only in ignored input packs, never in tracked run metadata."""
    relative = pathlib.Path("chunk_inputs") / f"input_{chunk['prompt_sha256']}.jsonl"
    atomic_write(input_dir / relative, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    chunk["input_path"] = relative.as_posix()
    chunk["sample_input_sha256"] = {r["sample_id"]: record_hash(r) for r in records}


def verify_chunk(
    chunk: dict, records: list[dict], prompt_text: str, model: str, effort: str, input_dir: pathlib.Path
) -> None:
    if chunk.get("model") != model or chunk.get("reasoning_effort") != effort or chunk.get("returncode") != 0:
        raise ValueError("review chunk did not complete with the required model and effort")
    if not chunk.get("session_id") or not chunk.get("prompt_sha256"):
        raise ValueError("review chunk is missing provenance")
    ids = chunk.get("sample_ids", [])
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("review chunk has empty or duplicate sample ids")
    current = {r["sample_id"]: r for r in records}
    recorded = chunk.get("sample_input_sha256")
    if recorded is not None and set(recorded) != set(ids):
        raise ValueError("review chunk sample_input_sha256 coverage mismatch")
    # Current records suffice for unchanged chunks. Mixed historical chunks need their archived input pack.
    if recorded is not None and any(sid not in current or record_hash(current[sid]) != recorded[sid] for sid in ids):
        relative = pathlib.Path(chunk.get("input_path", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.name.startswith("input_"):
            raise ValueError("review chunk needs a valid archived input_path")
        try:
            source = load_records(input_dir / relative)
        except OSError as exc:
            raise ValueError("review chunk archived input pack is missing") from exc
        if [r["sample_id"] for r in source] != ids:
            raise ValueError("review chunk archived input coverage mismatch")
    else:
        if not set(ids).issubset(current):
            raise ValueError("review chunk contains unexpected sample ids")
        source = [current[sid] for sid in ids]
    if recorded is not None and recorded != {r["sample_id"]: record_hash(r) for r in source}:
        raise ValueError("review chunk sample_input_sha256 mismatch")
    if actual_prompt_hash(prompt_text, source) != chunk["prompt_sha256"]:
        raise ValueError("review chunk actual prompt_sha256 mismatch; stale or modified input")


def binding(chunk: dict, index: int, verdict: dict) -> dict:
    return {
        "chunk_index": index,
        "sample_input_sha256": chunk["sample_input_sha256"][verdict["sample_id"]],
        "prompt_sha256": chunk["prompt_sha256"],
        "verdict_sha256": record_hash(verdict),
    }


def current_verdicts(run: dict) -> dict[str, dict]:
    """The atomically written run is authoritative; the JSONL file is a checked mirror."""
    result = {}
    last = {sid: index for index, chunk in enumerate(run["chunks"]) for sid in chunk["sample_ids"]}
    for sid, reference in run["latest"].items():
        index = reference.get("chunk_index")
        if type(index) is not int or not 0 <= index < len(run["chunks"]):
            raise ValueError(f"{sid}: invalid latest chunk reference")
        if index != last.get(sid):
            raise ValueError(f"{sid}: latest must reference the last recorded invocation, not an older verdict")
        chunk = run["chunks"][index]
        matches = [v for v in chunk.get("verdicts", []) if v["sample_id"] == sid]
        if len(matches) != 1 or reference != binding(chunk, index, matches[0]):
            raise ValueError(f"{sid}: latest verdict provenance mismatch")
        result[sid] = matches[0]
    return result


def verify_review(
    run: dict,
    records: list[dict],
    verdicts: dict[str, dict],
    prompt_text: str,
    model: str,
    effort: str,
    *,
    input_dir: pathlib.Path = REVIEW,
    require_complete: bool = True,
) -> dict[str, dict]:
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    validate_resume(run, prompt_hash, model, effort, records)
    expected = {r["sample_id"] for r in records}
    if run.get("provenance_version") == 2:
        current = current_verdicts(run)
        if not set(current).issubset(expected):
            raise ValueError("review contains unexpected sample ids")
        for sid, reference in run["latest"].items():
            if reference["sample_input_sha256"] != run["sample_input_sha256"][sid]:
                raise ValueError(f"{sid}: latest sample_input_sha256 does not match current input")
        for index in {r["chunk_index"] for r in run["latest"].values()}:
            verify_chunk(run["chunks"][index], records, prompt_text, model, effort, input_dir)
        active = run.get("active_review")
        if active:
            pending = set(active["pending_ids"])
            if pending & set(current) or not pending.issubset(expected):
                raise ValueError("pending review has a stale latest verdict")
    elif "provenance_version" not in run:
        # Legacy runs are accepted only when every actual invocation can be reconstructed exactly.
        current = {}
        for chunk in run["chunks"]:
            verify_chunk(chunk, records, prompt_text, model, effort, input_dir)
            for sid in chunk["sample_ids"]:
                if sid not in verdicts:
                    raise ValueError("review is incomplete or contains unexpected sample ids")
                current[sid] = verdicts[sid]
    else:
        raise ValueError("unsupported review provenance version")
    supplied = {sid: v for sid, v in verdicts.items() if sid in expected}
    if require_complete and (set(current) != expected or run.get("active_review")):
        raise ValueError("review is incomplete")
    if supplied != current:
        raise ValueError("review run/verdict coverage or content mismatch; retry after current write completes")
    parse_reply("\n".join(json.dumps(v) for v in current.values()), list(current))
    return current


def migrate_legacy(
    run: dict, records: list[dict], verdicts: dict[str, dict], prompt_text: str, input_dir: pathlib.Path
) -> dict:
    """Materialize old exact bindings before the global target hashes are allowed to change."""
    verify_review(
        run,
        records,
        verdicts,
        prompt_text,
        run["model"],
        run["reasoning_effort_requested"],
        input_dir=input_dir,
        require_complete=False,
    )
    upgraded = copy.deepcopy(run)
    upgraded.update(provenance_version=2, latest={}, active_review=None)
    by_id = {r["sample_id"]: r for r in records}
    last = {sid: i for i, c in enumerate(upgraded["chunks"]) for sid in c["sample_ids"]}
    for index, chunk in enumerate(upgraded["chunks"]):
        save_chunk_inputs(chunk, [by_id[sid] for sid in chunk["sample_ids"]], input_dir)
        # Legacy files contain only the last verdict, so do not invent superseded historical replies.
        chunk["verdicts"] = [verdicts[sid] for sid in chunk["sample_ids"] if last[sid] == index]
        for v in chunk["verdicts"]:
            upgraded["latest"][v["sample_id"]] = binding(chunk, index, v)
    return upgraded


def checkpoint(run: dict, run_path: pathlib.Path, out_path: pathlib.Path) -> None:
    verdicts = current_verdicts(run)
    atomic_write(run_path, json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    atomic_write(out_path, "".join(json.dumps(verdicts[k], ensure_ascii=False) + "\n" for k in sorted(verdicts)))


def start_targeted_review(run: dict, records: list[dict], only: set[str]) -> list[dict]:
    hashes = {r["sample_id"]: record_hash(r) for r in records}
    active = run.get("active_review")
    target = {sid: hashes[sid] for sid in sorted(only)}
    if active:
        if active["sample_input_sha256"] != target:
            raise ValueError("unfinished --only review must resume with the same selection and inputs")
    else:
        for sid in only:
            run["latest"].pop(sid, None)
        active = {"sample_input_sha256": target, "pending_ids": sorted(only)}
        run["active_review"] = active
    run["sample_input_sha256"] = hashes
    return [r for r in records if r["sample_id"] in active["pending_ids"]]


def run_chunk(codex: str, model: str, effort: str, prompt: str, workdir: pathlib.Path) -> tuple[str, dict]:
    last = workdir / "last_message.txt"
    if last.exists():
        last.unlink()
    cmd = [
        codex,
        "exec",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "-C",
        str(workdir),
        "-o",
        str(last),
        "-",
    ]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1800)
    log = proc.stdout + proc.stderr
    meta = {
        "returncode": proc.returncode,
        "cli_version": (re.search(r"OpenAI Codex v(\S+)", log) or [None, None])[1],
        "model": (re.search(r"^model: (.+)$", log, flags=re.M) or [None, None])[1],
        "session_id": (re.search(r"^session id: (\S+)$", log, flags=re.M) or [None, None])[1],
        "reasoning_effort": (re.search(r"^reasoning effort: (.+)$", log, flags=re.M) or [None, None])[1],
        "tokens_used": (re.search(r"^tokens used\n([\d,]+)", log, flags=re.M) or [None, None])[1],
    }
    if proc.returncode != 0 or not last.exists():
        raise RuntimeError(f"codex exec failed ({proc.returncode}): {log[-1500:]}")
    return last.read_text(encoding="utf-8"), meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--chunk", type=int, default=5)
    ap.add_argument("--model", default="gpt-6-astra")
    ap.add_argument("--codex", default=DEFAULT_CODEX)
    ap.add_argument(
        "--effort", default="high", help="model_reasoning_effort passed explicitly (user config is ignored)"
    )
    ap.add_argument("--only", nargs="*", help="sample_ids to (re)run; an interrupted selection resumes pending ids")
    ap.add_argument(
        "--previous-input", type=pathlib.Path, help="archived input pack for migrating a changed legacy run"
    )
    args = ap.parse_args()
    if args.chunk < 1:
        ap.error("--chunk must be positive")

    prompt_text = PROMPT_FILE.read_bytes().decode("utf-8")
    records = load_records(REVIEW / f"input_{args.batch}.jsonl")
    all_records = records
    all_ids = [r["sample_id"] for r in records]
    if len(set(all_ids)) != len(all_ids):
        sys.exit("duplicate input sample_id")
    if not records:
        sys.exit("nothing to review")
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    out_path = REVIEW / f"verdicts_{args.batch}.jsonl"
    run_path = REVIEW / f"run_{args.batch}.json"
    try:
        if args.only is not None:
            selected = set(args.only)
            if not selected or not selected.issubset(all_ids):
                raise ValueError("--only must name at least one existing sample_id")
            if out_path.exists() and not run_path.exists():
                raise ValueError("existing verdicts have no run provenance; archive and rerun")
            if run_path.exists():
                runs = json.loads(run_path.read_text(encoding="utf-8"))
                validate_resume(runs, prompt_hash, args.model, args.effort, all_records, selected)
                if "provenance_version" not in runs:
                    previous = load_records(args.previous_input) if args.previous_input else all_records
                    rows = load_records(out_path) if out_path.exists() else []
                    if len({r["sample_id"] for r in rows}) != len(rows):
                        raise ValueError("duplicate existing verdict sample_id")
                    runs = migrate_legacy(runs, previous, {v["sample_id"]: v for v in rows}, prompt_text, REVIEW)
                elif runs.get("provenance_version") != 2:
                    raise ValueError("unsupported review provenance version")
                # Verify against the old targets before invalidating the selected records. Changed inputs
                # are checked through their archived chunk packs, while current hashes remain authoritative.
                previous_verdicts = current_verdicts(runs)
                for index in {r["chunk_index"] for r in runs["latest"].values()}:
                    verify_chunk(runs["chunks"][index], all_records, prompt_text, args.model, args.effort, REVIEW)
                for sid, reference in runs["latest"].items():
                    if reference["sample_input_sha256"] != runs["sample_input_sha256"].get(sid):
                        raise ValueError(f"{sid}: latest sample_input_sha256 mismatch")
                parse_reply("\n".join(json.dumps(v) for v in previous_verdicts.values()), list(previous_verdicts))
            else:
                runs = None
        else:
            selected = set(all_ids)
            # Replacing old history requires an explicit archive, rather than silently dropping lineage.
            if run_path.exists() or out_path.exists():
                raise ValueError("existing review must be resumed with --only, or archived before a full rerun")
            runs = None
        if runs is None:
            runs = {
                "batch": args.batch,
                "codex_binary": args.codex,
                "model": args.model,
                "reasoning_effort_requested": args.effort,
                "review_prompt_sha256": prompt_hash,
                "sample_input_sha256": {r["sample_id"]: record_hash(r) for r in all_records},
                "chunks": [],
                "provenance_version": 2,
                "latest": {},
                "active_review": None,
            }
        records = start_targeted_review(runs, all_records, selected)
        # Invalidate every selected old verdict before a model call, including on failure or interruption.
        checkpoint(runs, run_path, out_path)
    except ValueError as exc:
        sys.exit(str(exc))
    with tempfile.TemporaryDirectory(prefix="codex-review-") as tmp:
        workdir = pathlib.Path(tmp)
        for i in range(0, len(records), args.chunk):
            chunk = records[i : i + args.chunk]
            ids = [r["sample_id"] for r in chunk]
            prompt = build_prompt(prompt_text, chunk)
            started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
            reply, meta = run_chunk(args.codex, args.model, args.effort, prompt, workdir)
            if meta["model"] != args.model or meta["reasoning_effort"] != args.effort:
                sys.exit(f"{ids}: observed model or reasoning effort differs from request; no verdict written")
            try:
                parsed = parse_reply(reply, ids)
            except ValueError as e:
                # Rejected output can echo full source pages. Keep it in an ignored derived-input file.
                bad_path = REVIEW / "bad_replies" / f"input_{args.batch}_{ids[0]}_bad.jsonl"
                atomic_write(bad_path, json.dumps({"raw_reply": reply}, ensure_ascii=False) + "\n")
                sys.exit(f"chunk {ids[0]}..{ids[-1]}: {e} (raw reply saved)")
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
            save_chunk_inputs(meta, chunk, REVIEW)
            verify_chunk(meta, chunk, prompt_text, args.model, args.effort, REVIEW)
            index = len(runs["chunks"])
            runs["chunks"].append(meta)
            for v in parsed:
                sid = v["sample_id"]
                runs["latest"][sid] = binding(meta, index, v)
                runs["active_review"]["pending_ids"].remove(sid)
            if not runs["active_review"]["pending_ids"]:
                runs["active_review"] = None
            checkpoint(runs, run_path, out_path)
            print(
                f"{ids[0]}..{ids[-1]}: {sum(v['verdict'] == 'dispute' for v in parsed)} dispute / {len(parsed)}; tokens {meta['tokens_used']}; session {meta['session_id']}",
                flush=True,
            )
    verdicts = current_verdicts(runs)
    total = len(verdicts)
    disputes = [k for k, v in verdicts.items() if v["verdict"] == "dispute"]
    print(f"{args.batch}: {total} verdicts, {len(disputes)} dispute: {disputes}")


if __name__ == "__main__":
    main()
