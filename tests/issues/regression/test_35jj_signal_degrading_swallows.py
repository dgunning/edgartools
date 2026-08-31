"""The four signal-degrading swallowed exceptions named in bead edgartools-35jj.

Bead: edgartools-35jj
GitHub Issue: https://github.com/dgunning/edgartools/issues/933

The classification rule these four failed: a swallow is legitimate when the
caller gets a degraded PRESENTATION, and a bug when the caller gets a degraded
VALUE. Each of these silently turned a computed signal off while the result went
on looking complete.

  xbrl/xbrl.py       the SGML date, the only input to date-discrepancy detection
  xbrl/currency.py   FX rate extraction, twice — failure read as "no rates found"
  muniadvisors.py    disclosures — failure read as a CLEAN compliance record

Line numbers in the bead are a 2026-08 snapshot and had all moved by 2026-08-30;
these tests bind to behaviour instead.
"""

import logging

import pandas as pd
import pytest

from edgar.xbrl.currency import CurrencyConverter


def _capture():
    """Imported at call time so this module still collects against a build that
    lacks the helper — otherwise the currency and muniadvisors gates below cannot
    be demonstrated against pre-fix code."""
    from edgar.xbrl.xbrl import _capture_sgml_period_of_report
    return _capture_sgml_period_of_report


# ---------------------------------------------------------------------------
# xbrl/xbrl.py — date-discrepancy detection
# ---------------------------------------------------------------------------

class _XBRLSlot:
    """Just the two attributes the capture writes."""
    _sgml_period_of_report = None
    _period_validation_unavailable = None


class _GoodFiling:
    accession_no = "0000320193-25-000079"
    period_of_report = "2025-09-27"


class _BrokenFiling:
    accession_no = "0000320193-25-000079"

    @property
    def period_of_report(self):
        raise RuntimeError("SGML header unavailable")


def test_capture_records_the_header_date():
    xbrl = _XBRLSlot()
    _capture()(xbrl, _GoodFiling())
    assert xbrl._sgml_period_of_report == "2025-09-27"
    assert xbrl._period_validation_unavailable is None


def test_a_failed_capture_is_recorded_rather_than_swallowed(caplog):
    xbrl = _XBRLSlot()
    with caplog.at_level(logging.WARNING):
        _capture()(xbrl, _BrokenFiling())

    # The check is off, and that fact is retrievable...
    assert xbrl._sgml_period_of_report is None
    assert "SGML header unavailable" in xbrl._period_validation_unavailable
    # ...and was said out loud, naming the filing.
    assert "0000320193-25-000079" in caplog.text
    assert "discrepancy detection is disabled" in caplog.text


def test_a_failed_capture_does_not_propagate():
    """Still a guard: a broken header must not break parsing the filing."""
    _capture()(_XBRLSlot(), _BrokenFiling())


# ---------------------------------------------------------------------------
# xbrl/currency.py — FX rate extraction
# ---------------------------------------------------------------------------

class _EmptyFacts:
    """A filing that genuinely publishes no exchange rate."""
    def to_dataframe(self):
        return pd.DataFrame()

    def query(self):
        return self

    def by_concept(self, *args, **kwargs):
        return self


class _RaisingFacts:
    """Extraction that blows up — a different thing entirely."""
    def to_dataframe(self):
        return pd.DataFrame()

    def query(self):
        raise RuntimeError("fact store unavailable")


class _StubXBRL:
    units: dict = {}

    def __init__(self, facts):
        self.facts = facts


def test_a_filing_with_no_rates_reports_no_rates():
    converter = CurrencyConverter(_StubXBRL(_EmptyFacts()))
    assert not converter.has_warnings
    assert converter.extraction_warnings == []
    assert "no rates found" in repr(converter)


def test_failed_extraction_is_not_reported_as_no_rates(caplog):
    with caplog.at_level(logging.WARNING):
        converter = CurrencyConverter(_StubXBRL(_RaisingFacts()))

    assert converter.has_warnings
    # Both the average and the closing extraction failed, and both are recorded.
    assert len(converter.extraction_warnings) == 2
    assert any("average" in w for w in converter.extraction_warnings)
    assert any("closing" in w for w in converter.extraction_warnings)
    assert "fact store unavailable" in converter.extraction_warnings[0]

    # The distinction the bug erased: this must not claim the filer published none.
    text = repr(converter)
    assert "rate extraction failed" in text
    assert "no rates found" not in text
    assert "Could not extract" in caplog.text


def test_a_failed_extraction_still_converts_nothing_rather_than_guessing():
    converter = CurrencyConverter(_StubXBRL(_RaisingFacts()))
    assert converter.to_usd(1_000_000, 2024) is None


def test_the_rich_display_also_says_extraction_failed():
    """An empty rate table and a table missing rows look identical otherwise."""
    converter = CurrencyConverter(_StubXBRL(_RaisingFacts()))
    caption = converter.__rich__().caption
    assert caption is not None and "Rate extraction failed" in caption

    clean = CurrencyConverter(_StubXBRL(_EmptyFacts()))
    assert clean.__rich__().caption is None


def test_extraction_warnings_is_a_copy():
    converter = CurrencyConverter(_StubXBRL(_RaisingFacts()))
    converter.extraction_warnings.append("mutated")
    assert len(converter.extraction_warnings) == 2


# ---------------------------------------------------------------------------
# muniadvisors.py — disclosures
# ---------------------------------------------------------------------------

def _advisor(disclosures_raise: bool):
    from edgar.muniadvisors import MunicipalAdvisorForm

    class _Applicant:
        full_name = "Jane Roe"
        crd = "12345"

    class _Filer:
        cik = 1234567

    class _Flag:
        def __init__(self, present):
            self._present = present

        def any(self):
            return self._present

    class _Disclosures:
        criminal = _Flag(True)
        regulatory = _Flag(False)
        civil = _Flag(False)
        complaint = _Flag(False)
        termination = _Flag(False)
        financial = _Flag(False)

    class _Advisor(MunicipalAdvisorForm):
        def __init__(self):
            self.applicant = _Applicant()
            self.filer = _Filer()
            self.is_amendment = False
            self.is_individual = True
            self.municipal_advisor_offices = []
            self.employment_history = None
            self.contact = None

        @property
        def disclosures(self):
            if disclosures_raise:
                raise RuntimeError("disclosure block unreadable")
            return _Disclosures()

    return _Advisor()


def test_disclosures_are_summarised_when_readable():
    text = _advisor(disclosures_raise=False).to_context()
    assert "Disclosures: criminal" in text


def test_an_unreadable_disclosure_block_never_reads_as_clean(caplog):
    with caplog.at_level(logging.WARNING):
        text = _advisor(disclosures_raise=True).to_context()

    # The bug: the "Disclosures:" line simply vanished, and a reader of a
    # municipal-advisor summary takes its absence for a clean record.
    assert "could not be read" in text
    assert "NOT a clean record" in text
    assert "disclosure block unreadable" in caplog.text


def test_an_unreadable_disclosure_block_does_not_break_the_summary():
    text = _advisor(disclosures_raise=True).to_context()
    assert "Jane Roe" in text
    assert "AVAILABLE ACTIONS:" in text
