import asyncio

import pytest

from medops.core.errors import ErrorCode, InfrastructureError
from medops.core.tracing import bind_trace_id, current_trace_id, is_valid_trace_id, new_trace_id, require_trace_id


def test_new_trace_id_format():
    tid = new_trace_id()
    assert is_valid_trace_id(tid) and len({new_trace_id() for _ in range(50)}) == 50


def test_bind_scopes_and_restores():
    assert current_trace_id() is None
    with bind_trace_id("a" * 32) as outer:
        assert outer == current_trace_id() == "a" * 32
        with bind_trace_id() as inner:
            assert inner != outer and current_trace_id() == inner
        assert current_trace_id() == outer
    assert current_trace_id() is None


def test_require_without_binding_is_an_internal_error():
    with pytest.raises(InfrastructureError) as exc:
        require_trace_id()
    assert exc.value.code is ErrorCode.internal_error and exc.value.retryable is False
    with bind_trace_id("c" * 32):
        assert require_trace_id() == "c" * 32


def test_invalid_trace_id_rejected():
    with pytest.raises(ValueError):
        with bind_trace_id("not-hex"):
            pass


def test_asyncio_tasks_inherit_and_isolate_trace_ids():
    async def child(expected: str) -> None:
        await asyncio.sleep(0)
        assert current_trace_id() == expected

    async def main() -> None:
        with bind_trace_id("d" * 32):
            t1 = asyncio.create_task(child("d" * 32))
            with bind_trace_id("e" * 32):
                t2 = asyncio.create_task(child("e" * 32))
            await asyncio.gather(t1, t2)
            assert current_trace_id() == "d" * 32

    asyncio.run(main())


@pytest.mark.parametrize("bad", ["", "a" * 32 + "\n", "A" * 32, "a" * 31, "a" * 33, " " + "a" * 31])
def test_only_exact_32_lowercase_hex_is_accepted(bad):
    assert not is_valid_trace_id(bad)
    with pytest.raises(ValueError):
        with bind_trace_id(bad):
            pass


def test_only_none_generates_a_fresh_id():
    with bind_trace_id(None) as generated:
        assert is_valid_trace_id(generated)
