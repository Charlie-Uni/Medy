"""Frozen replay sets (M4-06): replay-v1 is intact (file hashes and dataset hash), large and independent enough,
labelled with the documented rules, and its screening subset follows its own rules; every later replay-v* directory
must pass the same integrity check and come from a different run on the same or a later main-set version."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[3]
OUT = REPO / "evals/replay/replay-v1"
sys.path.insert(0, str(REPO / "evals/replay/tools"))

from build_replay_set import check, label_main  # noqa: E402


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_frozen_files_match_the_manifest_and_the_checker_is_clean():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest, name
    sums = dict(line.split("  ", 1)[::-1] for line in (OUT / "SHA256SUMS").read_text().splitlines())
    assert sums == manifest["files"]
    assert manifest["status"] == "frozen" and manifest["provisional"] is True
    assert manifest["origin"] == "run_export_not_live_traffic" and "INV-EVAL-01" in manifest["isolation"]
    assert check(OUT) == []


def test_main_items_are_independent_labelled_and_enough():
    items = load("items.jsonl")
    assert len(items) >= 200 and len({it["replay_id"] for it in items}) == len(items)
    assert len({it["query"] for it in items}) == len(items)
    labels = Counter(it["label"] for it in items)
    assert set(labels) == {"good", "bad"} and labels["bad"] >= 30 and labels["good"] >= 100
    for it in items:
        row = {"kind": it["kind"], "outcome": it["observed"]["outcome"], "gold_cited": it["observed"]["gold_cited"]}
        assert (it["label"], it["label_reason"]) == label_main(row)
        assert it["dept"] in {"MA", "PV", "CO"} and it["source"]["dataset"] == "main-v1-provisional"
    assert {it["dept"] for it in items} == {"MA", "PV", "CO"}


def test_safety_items_carry_expectations_and_labels():
    items = load("safety_items.jsonl")
    assert len(items) == 170 and len({it["replay_id"] for it in items}) == 170
    assert all(it["expected"] for it in items) and all(it["label"] in {"good", "bad", "not_exercised"} for it in items)
    cats = Counter(it["category"] for it in items)
    assert cats["high_risk"] == 30 and cats["version_guard"] == 10
    assert any(it["historical"] for it in items if it["category"] == "version_guard")


def test_screening_subset_follows_its_rules():
    items = {it["replay_id"]: it for it in load("items.jsonl")}
    subset = json.loads((OUT / "subset.json").read_text(encoding="utf-8"))
    ids = subset["replay_ids"]
    assert subset["size"] == len(ids) == 200 and len(set(ids)) == 200
    picked = [items[i] for i in ids]
    assert not any(it["derived"] for it in picked)
    labels = Counter(it["label"] for it in picked)
    assert labels["bad"] == 60 and labels["good"] == 140
    depts = Counter(it["dept"] for it in picked)
    assert set(depts) == {"MA", "PV", "CO"} and min(depts.values()) >= 30


def test_every_later_replay_version_is_intact_and_supersedes_its_predecessor():
    versions = sorted(REPO.glob("evals/replay/replay-v*"), key=lambda d: int(d.name.split("-v")[1]))
    assert versions[0] == OUT
    previous = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    for version in versions[1:]:
        manifest = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
        assert check(version) == [], version.name
        assert manifest["status"] == "frozen" and manifest["provisional"] is True
        assert manifest["dataset_hash"] != previous["dataset_hash"]
        # a later replay version exercises the same or a later main set, always through a different run
        assert manifest["sources"]["main"]["dataset_version"] >= previous["sources"]["main"]["dataset_version"]
        assert manifest["sources"]["main"]["run"] != previous["sources"]["main"]["run"]
        assert manifest["sources"]["main"]["dataset_version"] in manifest["provisional_reason"]
        items = [
            json.loads(line)
            for line in (version / "items.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert all(it["source"]["dataset"] == manifest["sources"]["main"]["dataset_version"] for it in items)
        assert len(items) >= 200 and Counter(it["label"] for it in items)["bad"] >= 60
        previous = manifest
