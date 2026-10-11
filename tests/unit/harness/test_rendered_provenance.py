"""Exact source coordinates survive alias layouts, whitespace, repeated sentences and elisions."""

import pytest

from medops.core.canonical import sha256_hex
from medops.harness.evidence_focus import _join_parts, render_evidence
from medops.harness.focus_profiles import ALLOWED_EVIDENCE_FOCUS
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_evidence_focus import DOSE, ENGLISH, SCORER


def test_repeated_sentence_coordinates_refer_to_the_selected_occurrence():
    text = "same sentence. same sentence.  other sentence. "
    spans = [(0, 14), (14, 29), (29, len(text))]
    shown, ranges = _join_parts(text, spans, {1})
    assert shown == "[…] same sentence. […]"
    assert ranges == [{"source_start": 15, "source_end": 29, "rendered_start": 4, "rendered_end": 18}]
    span = ranges[0]
    assert text[span["source_start"] : span["source_end"]] == shown[span["rendered_start"] : span["rendered_end"]]


@pytest.mark.parametrize("mode", sorted(ALLOWED_EVIDENCE_FOCUS))
def test_all_released_layouts_bind_source_hashes_exact_slices_aliases_and_body(mode):
    items = [evidence("c1", DOSE), evidence("c2", ENGLISH)]
    rendered = render_evidence(
        "6 至 12 歲 劑量",
        items,
        mode=mode,
        scorer=SCORER,
        titles={e.citation.doc_id: "Official guidance v2" for e in items},
    )
    assert len(rendered.fragments) == 2
    for original, fragment in zip(items, rendered.fragments, strict=True):
        assert fragment["citation"] == original.citation.model_dump(mode="json")
        assert fragment["source_text_sha256"] == original.evidence_text_hash
        text = fragment["rendered_text"]
        assert sha256_hex(text) == fragment["rendered_text_sha256"] and text in rendered.body()
        for span in fragment["source_ranges"]:
            assert (
                original.text[span["source_start"] : span["source_end"]]
                == text[span["rendered_start"] : span["rendered_end"]]
            )
    if rendered.chunk_ids:
        assert rendered.resolve("E1") == "c1" and rendered.resolve("E2") == "c2"
