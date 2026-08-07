"""
Fast unit tests for the eval harness's unavailable (unfetched) accounting.

A filing SEC would not serve is *unmeasured*, not a defect. Before this
partition existed, every fetch failure landed in the ``error`` bucket and counted
toward ``bad_rate``, so ``test_eval_ratchet`` reported an extraction regression
whenever the network was slow. It failed exactly that way under full-suite load:
the suite shares one rate limiter, a busy run starves the eval's 44 fetches, and
a quality guardrail blamed the extractor for it.

The partition has to hold in both directions, which is what these pin. A
transport failure must not be counted as bad; an extractor that genuinely raises
must still be, because that is the thing the eval exists to catch. Neither
touches the network.
"""
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent
sys.path.insert(0, str(EVAL_DIR))

from run_eval import _is_transport_failure, summarize  # noqa: E402


def _r(facet, bucket, frontier=False):
    return {"facet": facet, "bucket": bucket, "frontier": frontier}


class TestTransportFailuresAreRecognised:
    """What counts as "SEC did not give us the filing"."""

    def test_httpx_transport_and_status_errors(self):
        import httpx

        request = httpx.Request("GET", "https://www.sec.gov/x")
        assert _is_transport_failure(httpx.ConnectError("refused", request=request))
        assert _is_transport_failure(httpx.ReadTimeout("timed out", request=request))
        assert _is_transport_failure(httpx.RemoteProtocolError("reset", request=request))
        assert _is_transport_failure(httpx.HTTPStatusError(
            "429", request=request, response=httpx.Response(429, request=request)))

    def test_builtin_connection_and_timeout_errors(self):
        assert _is_transport_failure(ConnectionResetError("peer reset"))
        assert _is_transport_failure(TimeoutError("timed out"))

    def test_edgar_fetch_failures_matched_by_name(self):
        """Matched by name so this does not break when they are moved."""
        for name in ("SECFilingNotFoundError", "SECHTMLResponseError",
                     "IdentityNotSetException"):
            assert _is_transport_failure(type(name, (Exception,), {})("boom")), name


class TestExtractorFailuresAreStillDefects:
    """The silence check: the partition must not become a blanket amnesty."""

    @pytest.mark.parametrize("exception", [
        TypeError("unsupported operand type(s)"),
        AttributeError("'NoneType' object has no attribute 'text'"),
        ValueError("could not convert string to float"),
        KeyError("total_offering_amount"),
        IndexError("list index out of range"),
        ZeroDivisionError("division by zero"),
    ])
    def test_an_extractor_crash_is_not_unavailable(self, exception):
        assert not _is_transport_failure(exception)


class TestUnavailableIsExcludedFromTheSample:

    def test_unavailable_does_not_count_toward_n(self):
        results = [
            _r("fee_capacity", "ok"),
            _r("fee_capacity", "ok"),
            _r("fee_capacity", "unavailable"),
        ]
        by_facet = summarize(results)
        assert by_facet["fee_capacity"]["n"] == 2
        assert by_facet["fee_capacity"]["unavailable"] == 1

    def test_a_fetch_failure_no_longer_moves_the_bad_rate(self):
        """The regression in one assertion.

        Two filings measured clean, one unfetchable. Counted the old way that is
        a 33% bad_rate against a ceiling most facets set near zero — a failure
        caused entirely by the network.
        """
        by_facet = summarize([
            _r("fee_capacity", "ok"),
            _r("fee_capacity", "ok"),
            _r("fee_capacity", "unavailable"),
        ])
        c = by_facet["fee_capacity"]
        bad_rate = (c["bad"] + c["error"] + c["suspect"]) / c["n"]
        assert bad_rate == 0.0

    def test_a_real_error_still_moves_the_bad_rate(self):
        by_facet = summarize([
            _r("fee_capacity", "ok"),
            _r("fee_capacity", "ok"),
            _r("fee_capacity", "error"),
        ])
        c = by_facet["fee_capacity"]
        assert c["n"] == 3
        assert (c["bad"] + c["error"] + c["suspect"]) / c["n"] == pytest.approx(1 / 3)

    def test_an_all_unavailable_facet_reports_an_empty_sample(self):
        """n == 0 rather than a coverage of 100% over nothing.

        The ratchet asserts on this: a facet whose every entry failed to fetch
        was not measured, and must not read as a pass.
        """
        by_facet = summarize([
            _r("fee_capacity", "unavailable"),
            _r("fee_capacity", "unavailable"),
        ])
        assert by_facet["fee_capacity"]["n"] == 0
        assert by_facet["fee_capacity"]["unavailable"] == 2
