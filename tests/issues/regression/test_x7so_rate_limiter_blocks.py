"""The shared rate limiter delays a burst of requests instead of refusing any.

bead edgartools-x7so. _create_rate_limiter() carried a try/except shim for
pyrate-limiter 3.x (GH #640), whose Limiter needed max_delay and
retry_until_max_delay to block rather than raise on a full bucket. The branch
was already unreachable: httpxthrottlecache>=0.6.1, which we require, needs
pyrate-limiter>=4.0. The shim is gone and our floor says >=4.0.

What the shim protected is the SEC rate-limit contract, and this pins it on
4.x defaults: a burst past the per-second limit waits, every acquire succeeds.

Offline: the limiter is exercised directly, no HTTP.
"""
import time

import pytest
from pyrate_limiter import Limiter

import edgar.httpclient as httpclient


@pytest.mark.fast
def test_burst_past_sec_limit_is_delayed_not_refused():
    limiter = httpclient._create_rate_limiter(9)

    start = time.monotonic()
    results = [limiter.try_acquire("sec") for _ in range(10)]
    elapsed = time.monotonic() - start

    # Nine fit in the first second; the tenth has to wait for the window to slide.
    assert results == [True] * 10
    assert elapsed >= 0.8


@pytest.mark.fast
def test_shared_client_uses_the_blocking_limiter():
    mgr = httpclient.get_http_mgr(cache_enabled=False, request_per_sec_limit=9)
    assert isinstance(mgr.rate_limiter, Limiter)
    rates = mgr.rate_limiter.buckets()[0].rates
    assert [(r.limit, r.interval) for r in rates] == [(9, 1000)]
