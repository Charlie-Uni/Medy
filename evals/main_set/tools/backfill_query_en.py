"""Backfill `query_en` for anchored English-document candidates whose drafter reply omitted it (one CLI call per
batch of at most 20 queries; same pinned drafter model; results are written back into candidates_*.json with the
call metadata under raw_backfill/). Twins are derived from these by make_sheets.py."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402
import draft_llm  # noqa: E402

RAW = dc.DRAFTS / "raw_backfill"
PROMPT = (
    "下面是若干条针对英文法规文档的中文检索问题（含英文术语）。请为每条给出自然、同义的英文问法（问同一件事、限定条件一致，"
    '保留原有英文术语与编号），只输出 JSON 数组，每个元素形如 {"handle": "...", "query_en": "..."}，不输出其他文字。\n\n'
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--binary", default=dc.DEFAULT_BINARY)
    args = ap.parse_args()
    corpus = dc.load_corpus()
    todo: dict[str, tuple[str, dict]] = {}
    files = {}
    for dept in ("MA", "PV", "CO"):
        path = dc.DRAFTS / f"candidates_{dept}.json"
        cands = json.loads(path.read_text(encoding="utf-8"))
        files[dept] = (path, cands)
        for c in cands:
            d = c["_draft"]
            if d["status"] == "ok" and corpus[d["document_key"]]["language"] == "en" and not d.get("query_en"):
                todo[f"{d['document_key']}#{d['rank']}"] = (dept, c)
    print(f"{len(todo)} candidates without query_en")
    if not todo:
        return 0
    RAW.mkdir(exist_ok=True)
    version = dc.cli_version(args.binary)
    handles = sorted(todo)
    with tempfile.TemporaryDirectory(prefix="main-backfill-") as tmp:
        for i in range(0, len(handles), 20):
            batch = handles[i : i + 20]
            prompt = PROMPT + json.dumps(
                [{"handle": h, "query": todo[h][1]["query"]} for h in batch], ensure_ascii=False, indent=1
            )
            started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
            reply, meta = dc.run_claude(
                args.binary, args.model, args.effort, draft_llm.SYSTEM_PROMPT, prompt, pathlib.Path(tmp)
            )
            items = {
                it["handle"]: str(it.get("query_en") or "").strip()
                for it in dc.parse_json_array(reply)
                if isinstance(it, dict)
            }
            rec = {
                "handles": batch,
                "cli_version": version,
                "started_at": started,
                "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                **meta,
                "reply": reply,
            }
            (RAW / f"backfill_{i // 20:02d}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            for h in batch:
                q = items.get(h)
                if q and 4 <= len(q) <= 300:
                    todo[h][1]["_draft"]["query_en"] = q
                    todo[h][1]["_draft"]["query_en_source"] = "backfill"
            print(
                f"batch {i // 20}: {sum(1 for h in batch if items.get(h))}/{len(batch)} filled, ${meta['cost_usd']:.3f}"
            )
    for _dept, (path, cands) in files.items():
        path.write_text(json.dumps(cands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
