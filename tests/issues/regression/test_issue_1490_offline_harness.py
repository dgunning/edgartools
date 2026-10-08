"""Preserve asyncio startup without weakening the opt-in offline harness.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1490

The reported Windows 11/Python 3.14.4 default-Proactor probe passes ordinary
pytest and errors during setup with the harness. The native async control below
uses the host's normal loop. The synthetic TCP-pair child forces an internal
connect on Linux; it does not emulate Proactor or establish Windows support.
It uses public APIs and does not require a private stdlib fallback or skip.
All global patching happens in bounded children. Denial controls replace saved
network functions with spies, so weakened guards cannot reach external hosts.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.regression]
ROOT = Path(__file__).resolve().parents[3]

_CHILD_HELPERS = """
import asyncio
import contextvars
import socket
import threading
from contextlib import contextmanager
from queue import Queue
from types import SimpleNamespace

proxy4 = SimpleNamespace(family=socket.AF_INET)
proxy6 = SimpleNamespace(family=socket.AF_INET6)
# Synthetic family sentinel avoids requiring AF_UNIX on every platform.
proxy_other = SimpleNamespace(family=object())

@contextmanager
def offline():
    from tests import _offline_harness as harness
    originals = (socket.socket.connect, socket.socket.connect_ex,
                 socket.getaddrinfo, socket.create_connection, socket.socketpair)
    harness.pytest_configure(None)
    try:
        yield harness
    finally:
        harness.pytest_unconfigure(None)
        assert (socket.socket.connect, socket.socket.connect_ex,
                socket.getaddrinfo, socket.create_connection,
                socket.socketpair) == originals

def expect_denied(harness, call):
    try:
        call()
    except harness.NetworkBlockedError:
        return
    raise AssertionError('network call was admitted')

def synthetic_tcp_pair():
    # A test trigger, not a copy of CPython's fallback implementation.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client = None
    peer = None
    try:
        listener.settimeout(2)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect(listener.getsockname())
        peer, _ = listener.accept()
        peer.settimeout(2)
        return peer, client
    except BaseException:
        if peer is not None:
            peer.close()
        if client is not None:
            client.close()
        raise
    finally:
        listener.close()
"""


def _run_child(script):
    try:
        result = subprocess.run(  # noqa: S603 - interpreter and scripts are test-owned.
            [sys.executable, "-B", "-c", _CHILD_HELPERS + dedent(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("offline harness child exceeded its deadline")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_no_data_async_loop_can_start():
    """Native default-loop control for ordinary pytest and the scoped audit."""
    assert asyncio.get_running_loop().is_running()
    await asyncio.sleep(0)


@pytest.mark.parametrize("synthetic", [False, True], ids=["native", "synthetic-tcp"])
def test_socketpairs_support_loop_startup(synthetic):
    _run_child(f"""
        if {synthetic!r}:
            # Select before import so the plugin captures this public original.
            socket.socketpair = synthetic_tcp_pair
        with offline():
            reader, writer = socket.socketpair()
            with reader, writer:
                reader.settimeout(2)
                writer.settimeout(2)
                writer.sendall(b'x')
                assert reader.recv(1) == b'x'
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(asyncio.sleep(0))
            finally:
                loop.close()
    """)


_DENIED_CALLS = [
    "socket.socket.connect(proxy4, ('203.0.113.1', 443))",
    "socket.socket.connect(proxy6, ('2001:db8::1', 443))",
    "socket.socket.connect_ex(proxy4, ('127.0.0.1', 9))",
    "socket.getaddrinfo('example.invalid', 443)",
    "socket.create_connection(('example.invalid', 443))",
]


def _run_denial_child(call, inside_pair):
    _run_child(f"""
        calls = []
        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return 0
        socket.socket.connect = spy
        socket.socket.connect_ex = spy
        socket.getaddrinfo = spy
        socket.create_connection = spy
        marker = object()
        def pair():
            expect_denied(harness, lambda: {call})
            return marker
        socket.socketpair = pair
        with offline() as harness:
            if {inside_pair!r}:
                assert socket.socketpair() is marker
            else:
                expect_denied(harness, lambda: {call})
        assert calls == []
    """)


@pytest.mark.parametrize("call", _DENIED_CALLS, ids=["ipv4", "ipv6", "connect-ex", "dns", "create-connection"])
@pytest.mark.parametrize("inside_pair", [False, True], ids=["ordinary", "during-pair"])
def test_external_and_other_hooks_stay_denied(call, inside_pair):
    _run_denial_child(call, inside_pair)


@pytest.mark.parametrize(
    "call",
    [
        "socket.socket.connect(proxy4, ('localhost', 9))",
        "socket.socket.connect(proxy4, ('127.0.0.2', 9))",
        "socket.socket.connect(proxy4, ('::1', 9))",
        "socket.socket.connect(proxy6, ('127.0.0.1', 9))",
        "socket.socket.connect(proxy_other, ('127.0.0.1', 9))",
        "socket.socket.connect(proxy4, '127.0.0.1')",
        "socket.socket.connect(proxy4, ['127.0.0.1', 9])",
        "socket.socket.connect(proxy4, ())",
    ],
    ids=["hostname", "other-127", "ipv4-ipv6-host", "ipv6-ipv4-host", "other-family", "string-address", "list-address", "empty-tuple"],
)
def test_socketpair_allowance_requires_exact_numeric_family_matches(call):
    _run_denial_child(call, inside_pair=True)


@pytest.mark.parametrize("family,host", [("AF_INET", "127.0.0.1"), ("AF_INET6", "::1")])
def test_direct_numeric_loopback_remains_denied(family, host):
    _run_child(f"""
        calls = []
        def spy(*args):
            calls.append(args)
        socket.socket.connect = spy
        proxy = SimpleNamespace(family=socket.{family})
        with offline() as harness:
            expect_denied(harness, lambda: socket.socket.connect(proxy, ({host!r}, 9)))
        assert calls == []
    """)


@pytest.mark.parametrize("family,host", [("AF_INET", "127.0.0.1"), ("AF_INET6", "::1")])
def test_socketpair_forwarding_and_nested_scope_restore(family, host):
    _run_child(f"""
        connections = []
        invocations = []
        proxy = SimpleNamespace(family=socket.{family})
        host = {host!r}
        marker = object()
        def connect(sock, address):
            connections.append((sock, address))
            return marker
        socket.socket.connect = connect
        def pair(*args, **kwargs):
            invocations.append((args, kwargs))
            if kwargs.get('nested'):
                assert socket.socketpair('inner') is marker
            return socket.socket.connect(proxy, (host, 9))
        socket.socketpair = pair
        with offline() as harness:
            assert socket.socketpair('outer', nested=True) is marker
            assert invocations == [(('outer',), {{'nested': True}}), (('inner',), {{}})]
            assert connections == [(proxy, (host, 9))] * 2
            expect_denied(harness, lambda: socket.socket.connect(proxy, (host, 9)))
        assert len(connections) == 2
    """)


@pytest.mark.parametrize("origin", ["socketpair", "connect"])
def test_socketpair_error_restores_denial(origin):
    _run_child(f"""
        calls = []
        origin = {origin!r}
        marker = BlockingIOError('connect in progress') if origin == 'connect' else ValueError('pair failed')
        def connect(*args):
            calls.append(args)
            if origin == 'connect':
                raise marker
        socket.socket.connect = connect
        def pair():
            socket.socket.connect(proxy4, ('127.0.0.1', 9))
            if origin == 'connect':
                raise AssertionError('connect exception was swallowed')
            raise marker
        socket.socketpair = pair
        with offline() as harness:
            try:
                socket.socketpair()
            except type(marker) as exc:
                assert exc is marker
            else:
                raise AssertionError('original exception was lost')
            expect_denied(harness, lambda: socket.socket.connect(proxy4, ('127.0.0.1', 9)))
        assert len(calls) == 1
    """)


def test_socketpair_scope_does_not_leak_to_other_threads_or_copied_context():
    _run_child("""
        calls = []
        errors = Queue()
        contexts = Queue()
        release = threading.Event()
        started = threading.Event()
        def connect(*args):
            calls.append(args)
        socket.socket.connect = connect
        def pair():
            contexts.put(contextvars.copy_context())
            started.set()
            assert release.wait(5), 'pair was never released'
            return None
        socket.socketpair = pair
        def create_pair():
            try:
                socket.socketpair()
            except BaseException as exc:
                errors.put(exc)
        def direct_connect():
            try:
                expect_denied(harness, lambda: socket.socket.connect(proxy4, ('127.0.0.1', 9)))
            except BaseException as exc:
                errors.put(exc)
        with offline() as harness:
            worker = threading.Thread(target=create_pair)
            worker.start()
            try:
                assert started.wait(5), 'pair did not start'
                direct_connect()
                copied = contexts.get(timeout=5)
                other = threading.Thread(target=copied.run, args=(direct_connect,))
                other.start()
                other.join(5)
                assert not other.is_alive(), 'copied-context thread did not finish'
            finally:
                release.set()
                worker.join(5)
            assert not worker.is_alive(), 'socketpair thread did not finish'
        assert errors.empty(), 'socketpair or denial worker failed'
        assert calls == []
    """)
