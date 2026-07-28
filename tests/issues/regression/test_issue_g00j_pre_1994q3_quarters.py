"""
Regression test for edgartools-g00j: available_quarters() hardcoded a 1994 Q3
start, structurally rejecting 1993 and 1994 H1 filings.

`available_quarters()` used `start_quarters = [(1994, 3), (1994, 4)]`, so
`expand_quarters()` filtered out every (year, quarter) pair before 1994 Q3 -
even though SEC's full-index actually serves quarterly indexes back to 1993
Q1 (verified directly against
https://www.sec.gov/Archives/edgar/full-index/1993/QTR1/form.gz through
1994/QTR2/form.gz, all HTTP 200; 1992 and earlier return 403). As a result,
`get_by_accession_number("0000003673-94-000052")` - a real 35-CERT filed by
Allegheny Power System Inc on 1994-06-30 (1994 Q2) - returned None.
"""
import itertools

import pytest

from edgar._filings import available_quarters, expand_quarters


@pytest.mark.fast
class TestAvailableQuartersCoversPre1994Q3:
    def test_1993_q1_is_now_included(self):
        assert (1993, 1) in available_quarters()

    def test_1994_h1_is_now_included(self):
        quarters = available_quarters()
        assert (1994, 1) in quarters
        assert (1994, 2) in quarters
        assert (1994, 3) in quarters
        assert (1994, 4) in quarters

    def test_1992_is_still_excluded(self):
        # SEC does not serve a full-index for 1992 or earlier (403).
        quarters = available_quarters()
        assert (1992, 4) not in quarters
        assert not any(year == 1992 for year, _ in quarters)

    def test_sequence_is_1993_through_current_quarter_with_no_gaps(self):
        quarters = available_quarters()
        current_year, current_quarter = quarters[-1]

        expected = list(itertools.product(range(1993, current_year), range(1, 5)))
        expected += list(itertools.product([current_year], range(1, current_quarter + 1)))

        assert quarters == expected

    def test_expand_quarters_includes_1993_q1(self):
        assert (1993, 1) in expand_quarters(1993, 1)

    def test_expand_quarters_still_excludes_1992(self):
        assert expand_quarters(1992, 4) == []


@pytest.mark.network
class TestPre1994Q3AccessionLookup:
    """End-to-end: a real filing from before the old 1994 Q3 boundary must resolve."""

    def test_1994_q2_filing_resolves(self):
        from edgar import get_by_accession_number

        # Real 35-CERT filed by Allegheny Power System Inc, 1994 Q2 - previously
        # rejected outright because available_quarters() only covered 1994 Q3/Q4.
        filing = get_by_accession_number("0000003673-94-000052")

        assert filing is not None
        assert filing.accession_no == "0000003673-94-000052"
        assert filing.cik == 3673
        assert filing.company == "ALLEGHENY POWER SYSTEM INC"
        assert filing.form == "35-CERT"
        assert str(filing.filing_date) == "1994-06-30"

    def test_1993_filing_resolves(self):
        from edgar import get_by_accession_number

        # Real 24F-2NT filed 1993-09-28, accessioned with a genuine "-93-" year
        # segment - previously unreachable since 1993 wasn't in available_quarters() at all.
        filing = get_by_accession_number("0000873611-93-000002")

        assert filing is not None
        assert filing.accession_no == "0000873611-93-000002"
        assert filing.cik == 873611
        assert filing.company == "MERRILL LYNCH FL MUN BOND FD OF MERRILL LYNCH MUL ST MUN SER"
        assert filing.form == "24F-2NT"
        assert str(filing.filing_date) == "1993-09-28"
