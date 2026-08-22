"""edgartools-07lk.25 — BDC probe loops must not report a guess as a finding.

Both loops ask SEC "does this year/quarter exist?" by probing URLs. A year SEC
never published answers 404, which `get_with_retry` returns as a response rather
than raising — so reaching the `except` means the probe got no answer at all.
Swallowing that was the bug: it made "we could not ask" indistinguishable from
"SEC has nothing", and each loop then stated a conclusion it had not earned.

  get_latest_bdc_report_year()  returned a hardcoded 2024 as "the latest year"
  get_available_quarters()      returned [], which reads as "SEC published none"

If SEC moves BDC_REPORT_BASE_URL the way it moved the fund dataset page, the
first one reports 2024 as current indefinitely, with nothing in the logs.

The value returned is deliberately unchanged — callers keep their fallback. What
changes is that using the fallback is now stated out loud, and the message
distinguishes the two causes.
"""
import logging

import pytest
from httpx import ConnectError

REFERENCE_LOGGER = "edgar.bdc.reference"
DATASETS_LOGGER = "edgar.bdc.datasets"


class _Response:
    """Minimal stand-in — the loops only read status_code."""

    def __init__(self, status_code):
        self.status_code = status_code


def _warnings(caplog, logger):
    return [r.getMessage() for r in caplog.records
            if r.name == logger and r.levelno == logging.WARNING]


class TestLatestReportYear:

    def test_unreachable_says_so_and_does_not_claim_a_year(self, monkeypatch, caplog):
        from edgar.bdc import reference

        monkeypatch.setattr(
            reference, "get_with_retry",
            lambda *a, **k: (_ for _ in ()).throw(ConnectError("offline")),
        )
        with caplog.at_level(logging.WARNING, logger=REFERENCE_LOGGER):
            year = reference.get_latest_bdc_report_year()

        assert year == reference._BDC_REPORT_FALLBACK_YEAR  # value unchanged
        messages = _warnings(caplog, REFERENCE_LOGGER)
        assert len(messages) == 1
        assert "Could not reach SEC" in messages[0]
        assert "may be stale" in messages[0]

    def test_all_404s_reports_a_moved_dataset_not_an_outage(self, monkeypatch, caplog):
        """404 everywhere is an answer — and the answer is 'it moved'."""
        from edgar.bdc import reference

        monkeypatch.setattr(reference, "get_with_retry", lambda *a, **k: _Response(404))
        with caplog.at_level(logging.WARNING, logger=REFERENCE_LOGGER):
            year = reference.get_latest_bdc_report_year()

        assert year == reference._BDC_REPORT_FALLBACK_YEAR
        messages = _warnings(caplog, REFERENCE_LOGGER)
        assert len(messages) == 1
        assert "No BDC report found" in messages[0]
        assert reference.BDC_REPORT_BASE_URL in messages[0]

    def test_a_real_hit_is_silent(self, monkeypatch, caplog):
        """The healthy path must stay quiet, or the warning gets tuned out."""
        from edgar.bdc import reference

        monkeypatch.setattr(reference, "get_with_retry", lambda *a, **k: _Response(200))
        with caplog.at_level(logging.WARNING, logger=REFERENCE_LOGGER):
            year = reference.get_latest_bdc_report_year()

        assert year > reference._BDC_REPORT_FALLBACK_YEAR
        assert _warnings(caplog, REFERENCE_LOGGER) == []


class TestAvailableQuarters:

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """get_available_quarters is lru_cached; without this the result depends
        on whichever test ran first."""
        from edgar.bdc.datasets import get_available_quarters
        get_available_quarters.cache_clear()
        yield
        get_available_quarters.cache_clear()

    def test_empty_from_unreachable_is_flagged(self, monkeypatch, caplog):
        from edgar.bdc import datasets

        monkeypatch.setattr(
            datasets, "get_with_retry",
            lambda *a, **k: (_ for _ in ()).throw(ConnectError("offline")),
        )
        with caplog.at_level(logging.WARNING, logger=DATASETS_LOGGER):
            quarters = datasets.get_available_quarters()

        assert quarters == []  # value unchanged
        messages = _warnings(caplog, DATASETS_LOGGER)
        assert len(messages) == 1
        assert "Could not reach SEC" in messages[0]
        assert "does not mean none exist" in messages[0]

    def test_empty_from_404s_points_at_the_dataset_url(self, monkeypatch, caplog):
        from edgar.bdc import datasets

        monkeypatch.setattr(datasets, "get_with_retry", lambda *a, **k: _Response(404))
        with caplog.at_level(logging.WARNING, logger=DATASETS_LOGGER):
            quarters = datasets.get_available_quarters()

        assert quarters == []
        messages = _warnings(caplog, DATASETS_LOGGER)
        assert len(messages) == 1
        assert "No BDC datasets found" in messages[0]

    def test_found_quarters_are_silent(self, monkeypatch, caplog):
        from edgar.bdc import datasets

        monkeypatch.setattr(datasets, "get_with_retry", lambda *a, **k: _Response(200))
        with caplog.at_level(logging.WARNING, logger=DATASETS_LOGGER):
            quarters = datasets.get_available_quarters()

        assert len(quarters) > 0
        assert _warnings(caplog, DATASETS_LOGGER) == []
