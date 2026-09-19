"""Mechanical consistency between the baseline checklist and the roadmap progress view.

Checks only counts and identifiers: per-stage item counts, roadmap ids unique and contiguous,
totals equal. It does not compare acceptance wording; the baseline remains the contract.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BASELINE = REPO / "docs" / "ENGINEERING_BASELINE.md"
ROADMAP = REPO / "docs" / "DEVELOPMENT_ROADMAP.md"
KNOWLEDGE_MAP = REPO / "docs" / "TASK_KNOWLEDGE_MAP.md"

STAGES = ("M0", "M1", "M2", "M3", "M4", "M5", "OPT", "G")
_SECTION_HEADERS = {
    "### M0": "M0",
    "### M1": "M1",
    "### M2": "M2",
    "### M3": "M3",
    "### M4": "M4",
    "### M5": "M5",
    "### P1/P2": "OPT",
    "## 11.": "G",
}
_CHECKBOX = re.compile(r"^- \[( |x|~|!)\] ")
_ROADMAP_ROW_ID = re.compile(r"^\| ((?:M[0-5]|OPT|G)-\d{2}) \|")
_SUMMARY_ROW = re.compile(r"^\| (M[0-5]|P1/P2 checklist|最终验收)[^|]*\| (\d+) \|")


def baseline_counts() -> dict[str, int]:
    counts = dict.fromkeys(STAGES, 0)
    section = None
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        for prefix, stage in _SECTION_HEADERS.items():
            if line.startswith(prefix):
                section = stage
        if section and _CHECKBOX.match(line):
            counts[section] += 1
    return counts


def roadmap_ids(path: Path = ROADMAP) -> dict[str, list[int]]:
    ids: dict[str, list[int]] = {s: [] for s in STAGES}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ROADMAP_ROW_ID.match(line)
        if m:
            stage, num = m.group(1).rsplit("-", 1)
            ids[stage].append(int(num))
    return ids


def test_baseline_stage_counts_match_roadmap_ids():
    counts, ids = baseline_counts(), roadmap_ids()
    for stage in STAGES:
        assert len(ids[stage]) == counts[stage], (
            f"{stage}: roadmap has {len(ids[stage])} rows, baseline has {counts[stage]} items"
        )


def test_roadmap_ids_are_unique_and_contiguous_from_01():
    for stage, nums in roadmap_ids().items():
        assert nums == list(range(1, len(nums) + 1)), f"{stage}: ids are not unique and contiguous: {nums}"


def test_totals_and_summary_table_agree():
    counts = baseline_counts()
    assert sum(counts.values()) == 99
    summary = {}
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        m = _SUMMARY_ROW.match(line)
        if m:
            summary[m.group(1)] = int(m.group(2))
    expected = {
        **{s: counts[s] for s in ("M0", "M1", "M2", "M3", "M4", "M5")},
        "P1/P2 checklist": counts["OPT"],
        "最终验收": counts["G"],
    }
    assert summary == expected, f"roadmap summary table {summary} != baseline counts {expected}"


def test_knowledge_map_uses_the_same_ids_as_the_roadmap():
    assert roadmap_ids(KNOWLEDGE_MAP) == roadmap_ids()


_STATUS_ROW = re.compile(r"^\| ((?:M[0-5])-\d{2}) \| ([^|]+) \|", re.M)
_PROGRESS_LINE = re.compile(r"P0 加权进度：(\d+\.\d)%（(\d+\.\d)/79）；按 99 项计 (\d+\.\d)%")


def _weight(status: str) -> float:
    status = status.strip()
    return 1.0 if status.startswith("已实现") else 0.5 if status.startswith("部分") else 0.0


def test_roadmap_progress_percentage_matches_knowledge_map_statuses():
    """Weighted progress (已实现 1, 部分 0.5, else 0) over the 79 P0 rows, as stated in the roadmap."""
    rows = _STATUS_ROW.findall(KNOWLEDGE_MAP.read_text(encoding="utf-8"))
    assert len(rows) == 79
    weighted = sum(_weight(status) for _, status in rows)
    m = _PROGRESS_LINE.search(ROADMAP.read_text(encoding="utf-8"))
    assert m, "roadmap must state the P0 weighted progress line"
    assert float(m.group(2)) == weighted
    assert float(m.group(1)) == round(weighted / 79 * 100, 1)
    assert float(m.group(3)) == round(weighted / 99 * 100, 1)
