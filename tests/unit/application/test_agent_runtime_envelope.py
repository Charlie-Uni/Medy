"""Golden pv-agent-runtime-v1 AAD bytes: old encrypted journals must remain readable."""

from datetime import UTC, datetime
from uuid import UUID

from medops.application.agent_runtime_envelope import head_aad, runtime_aad


def test_head_aad_keeps_the_original_0029_byte_format():
    expected = (
        '["pv-agent-runtime-v1","00000000-0000-0000-0000-000000000001","'
        + "a" * 64
        + '","head","3","00000000-0000-0000-0000-000000000002","4",'
        '"015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862",'
        '"2026-10-19T00:00:00.000000+00:00","2027-01-17T00:00:00.000000+00:00"]'
    ).encode()
    assert (
        head_aad(
            UUID(int=1),
            "a" * 64,
            3,
            UUID(int=2),
            4,
            {"a": 1},
            datetime(2026, 10, 19, tzinfo=UTC),
            datetime(2027, 1, 17, tzinfo=UTC),
        )
        == expected
    )


def test_event_aad_keeps_original_ids_kind_and_lease_binding():
    expected = (
        '["pv-agent-runtime-v1","00000000-0000-0000-0000-000000000001","'
        + "b" * 64
        + '","event","00000000-0000-0000-0000-000000000009","call_admitted",'
        '"00000000-0000-0000-0000-00000000000a","00000000-0000-0000-0000-000000000002","4"]'
    ).encode()
    assert (
        runtime_aad(UUID(int=1), "b" * 64, "event", UUID(int=9), "call_admitted", UUID(int=10), UUID(int=2), 4)
        == expected
    )
