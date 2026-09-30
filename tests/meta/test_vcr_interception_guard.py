"""Cassette replay has to reach edgartools' own HTTP stack, or every cassette test is decorative.

vcrpy intercepts by patching httpcore's connection pools by name. When that
patching stops matching the client (an httpx or vcrpy upgrade, or the planned
httpx2 swap), nothing fails: a test with a cassette quietly fetches from the
network instead, and passes as long as SEC answers. The q2iz spike measured
exactly this on 2026-08-06 (vcrpy 8.1.1 + httpx2 recorded 0 interactions and
still passed). Nothing in the suite would notice (bead edgartools-243z).

These tests replay a cassette for an address where nothing can answer, through
``edgar.httprequests`` rather than bare httpx, so the throttle and cache layers
that sit above vcr are in the path, as they are for every real test. The
response can only have come from vcr. If interception is lost, the request goes
to the socket layer and fails: connection refused normally, NetworkBlockedError
under tests/_offline_harness.py.

The bead also asked for a RECORD guard against a local HTTP server. It is left
out on purpose: the offline audit (scripts/check_offline_audit.py) runs changed
test files with every socket blocked, loopback included, so a local server
would fail the PR gate as "needs the network". Recording and replay go through
the same httpcore patch, so losing one loses the other, and the second test
below shows vcr also sits in the path of requests the cassette does NOT hold.

``127.0.0.1:9`` is the discard port, and nothing listens on it in CI. The
127.0.0.1 host matches no rule in edgar.httpclient.CACHE_RULES, so the HTTP
cache never stores it and cannot answer in vcr's place.

Bead: edgartools-243z
"""

import asyncio

import pytest
import vcr
from vcr.errors import CannotOverwriteExistingCassetteException

from edgar.httpclient import async_http_client
from edgar.httprequests import get_with_retry, get_with_retry_async

# Measured, not assumed: this module passes under `-p tests._offline_harness`,
# because a replayed request never opens a socket. That is the whole claim.
pytestmark = pytest.mark.fast

URL = "http://127.0.0.1:9/edgartools-vcr-guard/replayed.txt"
BODY = "served from the cassette, not the network"

CASSETTE = f"""\
interactions:
- request:
    body: ''
    headers: {{}}
    method: GET
    uri: {URL}
  response:
    body:
      string: {BODY}
    headers:
      Content-Type:
      - text/plain
    status:
      code: 200
      message: OK
version: 1
"""


@pytest.fixture
def replay_only(tmp_path, vcr_config):
    """A VCR built from the suite's own vcr_config, pointed at one guard cassette."""
    (tmp_path / "guard.yaml").write_text(CASSETTE)
    config = {**vcr_config, "cassette_library_dir": str(tmp_path), "record_mode": "none"}
    return vcr.VCR(**config)


def test_sync_requests_are_replayed_by_vcr(replay_only):
    with replay_only.use_cassette("guard.yaml") as cassette:
        response = get_with_retry(URL)
    assert response.status_code == 200
    assert response.text == BODY
    assert cassette.play_count == 1


def test_async_requests_are_replayed_by_vcr(replay_only):
    async def fetch():
        async with async_http_client() as client:
            return await get_with_retry_async(client, URL)

    with replay_only.use_cassette("guard.yaml") as cassette:
        response = asyncio.run(fetch())
    assert response.text == BODY
    assert cassette.play_count == 1


def test_a_request_the_cassette_lacks_is_refused_by_vcr_not_sent(replay_only):
    # With interception lost this raises a connection error, or
    # NetworkBlockedError under the offline harness, and never vcr's refusal.
    with replay_only.use_cassette("guard.yaml"):
        with pytest.raises(CannotOverwriteExistingCassetteException):
            get_with_retry("http://127.0.0.1:9/edgartools-vcr-guard/not-in-cassette.txt")
