"""
Regression test for Issue #1174: XBRLS.from_filings() silently swallows
unexpected parsing exceptions and returns partial results.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1174

Problem:
- XBRLS.from_filings() wrapped XBRL.from_filing(filing) in a blanket
  `except Exception: pass`, so any unexpected parser failure disappeared
  with no trace of which filing failed or why. The caller received a
  normally-returned XBRLS built from only the filings that happened to
  succeed, indistinguishable from a fully successful multi-filing parse.

Root Cause:
- edgar/xbrl/stitching/xbrls.py, the for loop in from_filings(), caught
  every Exception and discarded it silently.

Fix:
- The failing filing's accession number, form and exception are now logged
  (edgar.core log, WARNING) every time, the same shape used to fix the
  parser's own swallowed-extraction-error report
  (test_issue_xbrl_warning_traceability.py): a per-instance message is safe
  here because logging has no message-dedup registry, unlike warnings.warn.
- The pre-existing, intentional tolerance for a filing with no XBRL data at
  all (XBRL.from_filing() returning None, issue #459) is untouched: that path
  never raises, so it never logs, and xbrl_list still carries the None
  exactly as it did before.
"""
import logging
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from edgar.xbrl import XBRLS

CORE_LOGGER = "edgar.core"


def _filing(accession_no, form="10-K", filing_date=date(2025, 2, 1)):
    return SimpleNamespace(accession_no=accession_no, form=form, filing_date=filing_date)


def _good_xbrl(entity_name):
    return SimpleNamespace(entity_info={"entity_name": entity_name})


@pytest.mark.fast
class TestIssue1174SwallowedExceptions:
    def test_unexpected_exception_is_logged_and_the_filing_still_skipped(self, caplog):
        """The reporter's own repro: one filing parses, one raises."""
        filings = [_filing("good"), _filing("broken", filing_date=date(2024, 2, 1))]

        def parse(filing):
            if filing.accession_no == "broken":
                raise RuntimeError("parser invariant failed")
            return _good_xbrl("Good Co")

        with patch("edgar.xbrl.xbrl.XBRL.from_filing", side_effect=parse):
            with caplog.at_level(logging.WARNING, logger=CORE_LOGGER):
                result = XBRLS.from_filings(filings, filter_amendments=False)

        # Existing contract preserved: the failed filing is dropped, not raised,
        # and the successful one still comes through.
        assert len(result.xbrl_list) == 1
        assert result.xbrl_list[0].entity_info["entity_name"] == "Good Co"

        # The whole point: which filing failed, and why, must be observable.
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "broken" in message
        assert "RuntimeError" in message
        assert "parser invariant failed" in message

    def test_warning_names_form_and_exception_type_for_a_different_filing(self, caplog):
        """Guards against a fix that hardcodes the reporter's own field names."""
        filings = [_filing("acc-0001", form="10-Q")]

        with patch("edgar.xbrl.xbrl.XBRL.from_filing", side_effect=ValueError("bad state")):
            with caplog.at_level(logging.WARNING, logger=CORE_LOGGER):
                result = XBRLS.from_filings(filings, filter_amendments=False)

        assert result.xbrl_list == []
        message = caplog.records[0].getMessage()
        assert "acc-0001" in message
        assert "10-Q" in message
        assert "ValueError" in message

    def test_none_for_no_xbrl_is_not_treated_as_a_failure(self, caplog):
        """Issue #459's tolerance: from_filing() returning None must stay silent."""
        # A second, newer filing with real XBRL keeps XBRLS.__init__'s own
        # xbrl_list[0].entity_info read (a pre-existing, unrelated assumption
        # that the newest filing has XBRL) out of this issue's blast radius.
        filings = [
            _filing("has-xbrl", filing_date=date(2025, 6, 1)),
            _filing("no-xbrl-filing", filing_date=date(2020, 1, 1)),
        ]

        def parse(filing):
            return None if filing.accession_no == "no-xbrl-filing" else _good_xbrl("Good Co")

        with patch("edgar.xbrl.xbrl.XBRL.from_filing", side_effect=parse):
            with caplog.at_level(logging.WARNING, logger=CORE_LOGGER):
                result = XBRLS.from_filings(filings, filter_amendments=False)

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(result.xbrl_list) == 1
        assert result.xbrl_list[0].entity_info["entity_name"] == "Good Co"
