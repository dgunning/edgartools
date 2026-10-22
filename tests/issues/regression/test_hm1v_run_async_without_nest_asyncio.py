"""Sync wrappers run their coroutines without nest-asyncio, inside a running loop too.

bead edgartools-hm1v. nest-asyncio is archived upstream (no maintenance, no
security fixes) and was a required dependency only so that sync calls could
drive a coroutine while Jupyter's event loop runs: core.run_async_or_sync and
storage._run_coroutine patched the running loop to be re-entrant. Attachments
.download() had no such guard at all; it called get_event_loop()
.run_until_complete(), which raises "This event loop is already running"
inside Jupyter unless something else had already applied nest-asyncio.

All three now go through run_async_or_sync, which runs the coroutine on a
private loop in a worker thread when the caller's thread already has one.
A running loop in this thread is exactly Jupyter's situation, so
asyncio.run(caller()) reproduces it offline.
"""
import asyncio
import importlib.metadata
import sys
import threading

import pytest

from edgar.core import run_async_or_sync


async def _answer(value):
    await asyncio.sleep(0)
    return value, threading.get_ident()


async def _fail():
    await asyncio.sleep(0)
    raise ValueError("from the coroutine")


@pytest.mark.fast
def test_runs_on_this_thread_when_no_loop_is_running():
    value, thread = run_async_or_sync(_answer(42))
    assert value == 42
    assert thread == threading.get_ident()


@pytest.mark.fast
def test_runs_inside_a_running_loop_like_jupyter():
    async def notebook_cell():
        # A sync library call made from code that already runs on a loop
        return run_async_or_sync(_answer("ok")), threading.get_ident()

    (value, worker), caller = asyncio.run(notebook_cell())
    assert value == "ok"
    assert worker != caller  # a private loop on a worker thread, not re-entrancy


@pytest.mark.fast
@pytest.mark.parametrize("inside_loop", [False, True])
def test_coroutine_exceptions_propagate(inside_loop):
    if inside_loop:
        async def cell():
            return run_async_or_sync(_fail())
        with pytest.raises(ValueError, match="from the coroutine"):
            asyncio.run(cell())
    else:
        with pytest.raises(ValueError, match="from the coroutine"):
            run_async_or_sync(_fail())


@pytest.mark.fast
def test_the_callers_loop_is_left_running_and_usable():
    async def cell():
        run_async_or_sync(_answer(1))
        loop = asyncio.get_running_loop()
        assert loop.is_running()
        # the caller's loop still schedules its own work afterwards
        return await _answer(2)

    assert asyncio.run(cell())[0] == 2


@pytest.mark.fast
def test_storage_and_attachments_use_the_shared_runner():
    import inspect

    from edgar.attachments import Attachments
    from edgar.storage import _local

    assert "run_async_or_sync" in inspect.getsource(_local._run_coroutine)
    download_source = inspect.getsource(Attachments.download)
    assert "run_async_or_sync(" in download_source
    assert "get_event_loop" not in download_source


@pytest.mark.fast
def test_nest_asyncio_is_not_a_dependency_and_never_imported():
    requires = importlib.metadata.requires("edgartools") or []
    assert not any(r.lower().replace("_", "-").startswith("nest-asyncio") for r in requires)

    async def cell():
        return run_async_or_sync(_answer(None))

    asyncio.run(cell())
    import edgar.storage._local  # noqa: F401
    assert "nest_asyncio" not in sys.modules
