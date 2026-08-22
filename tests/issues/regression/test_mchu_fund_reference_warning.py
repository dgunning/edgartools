"""edgartools-mchu — a failed fund reference-data load must not degrade silently.

`_build_hierarchy_from_mf_tickers` enriches series and class names from
`get_fund_reference_data()`, and falls back to the bare identifier when that is
unavailable. The fallback itself is fine; swallowing every cause of it was not.

SEC turned the investment-company dataset page into a 301 with a relative
`Location`, edgartools followed the header verbatim, and httpx raised
`UnsupportedProtocol` — an error, not an outage. A bare `except Exception: pass`
made that indistinguishable from "this class has no name", so
`find_fund("KINCX").name` returned `"C000013712"` instead of `"Advisor Class C"`
with no warning at all. It surfaced only because two literal-value assertions in
tests/test_funds.py happened to cover those tickers.

The contract these tests pin: being offline degrades quietly, every other cause
degrades loudly. The fallback value is unchanged in both cases — this is about
whether anyone is told.
"""
import logging

import pandas as pd
import pytest
from httpx import ConnectError, TimeoutException

import edgar.funds.data as fund_data

LOGGER = "edgar.funds.data"

# Minimal shape of the cached mutual-fund tickers frame: one class of one series
# of one company. Real values, so a failure message points somewhere real.
MF_TICKERS = pd.DataFrame([
    {"cik": 1083387, "seriesId": "S000008303", "classId": "C000013712", "ticker": "KINCX"},
])


def _build_with_reference_failure(monkeypatch, failure):
    """Build the hierarchy with get_fund_reference_data() raising `failure`."""
    monkeypatch.setattr(
        "edgar.reference.tickers.get_mutual_fund_tickers", lambda: MF_TICKERS
    )

    def boom():
        raise failure

    monkeypatch.setattr("edgar.funds.reference.get_fund_reference_data", boom)
    return fund_data._build_hierarchy_from_mf_tickers(
        cik="1083387", identifier_type="Class", identifier="KINCX"
    )


def test_defect_in_reference_data_warns(monkeypatch, caplog):
    """A non-transport failure is a defect and must say so.

    ValueError stands in for the whole family the old bare except hid: SEC
    restructuring the dataset page, the CSV changing shape, a bug inside
    FundReferenceData. None of them mean "no name exists".
    """
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        fund_class = _build_with_reference_failure(
            monkeypatch, ValueError("No fund data CSV file found on the SEC website.")
        )

    assert fund_class is not None
    assert fund_class.name == "C000013712"  # the fallback still applies

    warnings = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]
    assert len(warnings) == 1, "expected exactly one warning naming the cause"
    message = warnings[0].getMessage()
    assert "ValueError" in message
    assert "No fund data CSV file found" in message
    assert "fall back to their identifiers" in message


def test_offline_degrades_quietly(monkeypatch, caplog):
    """Being unreachable is not a defect — no warning, same fallback.

    Without this half, the fix would just trade a silent wrong answer for a
    warning on every offline call, which is how a useful warning gets tuned out.
    """
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        fund_class = _build_with_reference_failure(
            monkeypatch, ConnectError("[Errno 8] nodename nor servname provided")
        )

    assert fund_class is not None
    assert fund_class.name == "C000013712"

    warnings = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]
    assert warnings == [], f"offline must not warn, got: {[r.getMessage() for r in warnings]}"


@pytest.mark.parametrize(
    "failure,expect_warning",
    [
        (ValueError("bad CSV"), True),
        (AttributeError("FundReferenceData has no attribute"), True),
        (KeyError("Class ID"), True),
        (ConnectError("offline"), False),
        (TimeoutException("timed out"), False),
        # The builtin TimeoutError is deliberately NOT unreachable: UNREACHABLE_ERRORS
        # lists the httpx and httpcore types, and every fetch on this path goes
        # through httpx, so a bare builtin here means something other than a stalled
        # socket and should be reported.
        (TimeoutError("not an httpx timeout"), True),
    ],
)
def test_warning_split_follows_is_unreachable(monkeypatch, caplog, failure, expect_warning):
    """The split is `is_unreachable`, not an exception allowlist.

    Pinned as a table so that widening UNREACHABLE_ERRORS in httprequests
    changes this behaviour deliberately rather than by accident.
    """
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build_with_reference_failure(monkeypatch, failure)

    warned = any(r.name == LOGGER and r.levelno == logging.WARNING for r in caplog.records)
    assert warned is expect_warning
