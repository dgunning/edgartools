"""Let vcrpy >= 8.2 replay cassettes that store no reason phrase.

vcrpy 8.2.0 replaced the httpcore-level stub with an httpx-level one, and its
response deserializer (``vcr/stubs/httpx_stubs.py``) does::

    extensions = {"reason_phrase": vcr_response["status"]["message"].encode("ascii")}

Cassettes recorded through the older httpcore stub hold ``message: null`` for
most responses, so that line raises ``AttributeError: 'NoneType' object has no
attribute 'encode'``. Measured on 2026-10-03 against vcrpy 8.3.0: 79 of 214
cassettes carry a null phrase, and 63 cassette-backed tests fail on replay.

The fix is upstream as kevin1024/vcrpy#1029 and unreleased. Until it ships,
this module fills a missing phrase with the standard one for the status code,
which is what httpx derived for these cassettes when the httpcore stub left
``extensions`` unset. A recorded phrase is left alone.

vcrpy < 8.3.0 cannot intercept httpx2 at all (requests reach the real network
and nothing is recorded), so this is also what lets the suite sit on a vcrpy
that can (beads edgartools-q2iz).

Delete this module, and its call in ``tests/conftest.py``, once the pinned
vcrpy includes the upstream fix: ``install_null_reason_phrase_fix`` returns
False in that case, and ``tests/meta/test_vcr_null_reason_phrase.py`` says so.
"""
from __future__ import annotations

from http import HTTPStatus

__all__ = ["install_null_reason_phrase_fix"]


def _standard_phrase(code: int) -> str:
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        return ""


def _null_phrase_response() -> dict:
    return {
        "status": {"code": 200, "message": None},
        "headers": {"Content-Type": ["text/plain"]},
        "body": {"string": b"canary"},
    }


def _replays_null_phrase(deserialize) -> bool:
    """True if ``deserialize`` turns a null-phrase cassette response into a 200 OK."""
    import httpx

    try:
        response = deserialize(_null_phrase_response(), httpx)
    except AttributeError:
        return False
    return response.status_code == 200 and response.reason_phrase == "OK"


def install_null_reason_phrase_fix() -> bool:
    """Wrap vcrpy's httpx response deserializer so a null reason phrase replays.

    Returns:
        True if the deserializer was wrapped. False if there is nothing to fix:
        vcrpy is not installed, it predates the httpx stub (< 8.2, which replays
        these cassettes through httpcore), or it already handles a null phrase.

    Raises:
        RuntimeError: if vcrpy has the httpx stub but its internals moved, or
            if the wrapped deserializer still cannot replay a null phrase.
            Failing here names the cause once, where the alternative is dozens
            of unrelated-looking AttributeErrors in cassette-backed tests.
    """
    try:
        import vcr  # noqa: F401
    except ImportError:
        return False

    try:
        from vcr.stubs import httpx_stubs
    except ImportError:
        return False

    original = getattr(httpx_stubs, "_deserialize_response", None)
    if original is None:
        raise RuntimeError(
            "Cannot install the null-reason-phrase fix: vcr.stubs.httpx_stubs has "
            "no '_deserialize_response' (vcrpy internals changed). Update "
            "tests/_vcr_compat.py, or delete it if vcrpy now handles this."
        )

    if _replays_null_phrase(original):
        return False

    def _deserialize_response(vcr_response, httpx):
        status = vcr_response.get("status")
        if isinstance(status, dict) and "message" in status and not status["message"]:
            filled = {**status, "message": _standard_phrase(status["code"])}
            vcr_response = {**vcr_response, "status": filled}
        return original(vcr_response, httpx)

    httpx_stubs._deserialize_response = _deserialize_response

    if not _replays_null_phrase(httpx_stubs._deserialize_response):
        raise RuntimeError(
            "The null-reason-phrase fix was installed but a cassette response "
            "with 'message: null' still does not replay as 200 OK. vcrpy's "
            "httpx stub changed; update tests/_vcr_compat.py."
        )
    return True
