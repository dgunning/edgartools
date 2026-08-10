"""R&D expense keeps the sign the filer reported (GH #334).

WHAT WAS BROKEN. ``us-gaap:ResearchAndDevelopmentExpense`` came back NEGATIVE
for some filers and positive for others, from the same API. Microsoft's FY2024
10-K reported R&D as a negative number while the filing itself and the SEC's
CompanyFacts API both show it positive; Apple's was positive. A caller
comparing R&D across two companies got one of each, and summing them cancelled
rather than added.

WHY THIS FILE LOOKS NEW. It is not — it was a reproduction script,
``reproductions/xbrl-parsing/test_issue_334_research_development_expense_sign.py``,
and it had two functions named ``test_*`` carrying ``@pytest.mark.regression``.
pytest collected both. Neither asserted anything: each ended in
``return negative_count > 0`` or ``return False``, and a test that returns
instead of asserting always passes. So the suite had been reporting two green
regression tests for issue #334 that could not have gone red if the sign
flipped back the same day. The bool they returned was read only by a ``main()``
that pytest never calls.

The docstrings were stale on top of that: they described the BROKEN behaviour
("should show inconsistent sign (negative in edgartools)") long after the fix
landed, so anyone reading them would have concluded the bug was still open.

GROUND TRUTH, read from the filings. Both filers report R&D positive, and the
figures match the income statements:

    Microsoft FY2024 10-K, 0000950170-24-087843
        FY2024 $29,510M   FY2023 $27,195M   FY2022 $24,512M
    Apple FY2024 10-K, 0000320193-24-000123
        FY2024 $31,370M   FY2023 $29,915M   FY2022 $26,251M

Both companies are asserted, and Microsoft is the one that carried the bug —
dropping it for being "the same as Apple now" would delete the regression.

GitHub Issue: https://github.com/dgunning/edgartools/issues/334
"""
import pytest

from edgar import get_by_accession_number

RD_CONCEPT = 'us-gaap:ResearchAndDevelopmentExpense'

# accession -> {(fiscal year end): reported R&D expense}, in dollars.
GROUND_TRUTH = {
    "MSFT": ("0000950170-24-087843", {
        "2024-06-30": 29_510_000_000,
        "2023-06-30": 27_195_000_000,
        "2022-06-30": 24_512_000_000,
    }),
    "AAPL": ("0000320193-24-000123", {
        "2024-09-28": 31_370_000_000,
        "2023-09-30": 29_915_000_000,
        "2022-09-24": 26_251_000_000,
    }),
}


def _rd_facts(accession):
    filing = get_by_accession_number(accession)
    assert filing is not None, f"could not fetch {accession}"
    facts = filing.xbrl().facts.to_dataframe()
    rd = facts[facts['concept'] == RD_CONCEPT]
    assert not rd.empty, (
        f"{accession} reports no {RD_CONCEPT} facts at all. The original "
        "version of this test treated that as a pass, which is how it stayed "
        "green while proving nothing."
    )
    return rd


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", sorted(GROUND_TRUTH))
def test_research_and_development_expense_is_positive(ticker):
    """The bug in one assertion: no filer reports R&D as a negative number."""
    accession, _expected = GROUND_TRUTH[ticker]
    rd = _rd_facts(accession)

    values = rd['numeric_value'].dropna()
    negative = values[values < 0]
    assert negative.empty, (
        f"{ticker} reports {len(negative)} negative R&D facts "
        f"({sorted(negative.unique())}). Issue #334 has returned: R&D is an "
        "expense the filer states positive, and flipping its sign makes it "
        "incomparable with every other filer."
    )
    assert (values > 0).all(), f"{ticker} has non-positive R&D values: {sorted(values.unique())}"


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", sorted(GROUND_TRUTH))
def test_research_and_development_expense_matches_the_filing(ticker):
    """Sign alone is not enough — pin the figures, per period."""
    accession, expected = GROUND_TRUTH[ticker]
    rd = _rd_facts(accession)

    by_period = {}
    for _, fact in rd.iterrows():
        end = str(fact.get('period_end'))
        value = fact['numeric_value']
        if end in expected:
            by_period.setdefault(end, set()).add(int(value))

    missing = sorted(set(expected) - set(by_period))
    assert not missing, (
        f"{ticker} is missing R&D for period(s) {missing}; found "
        f"{sorted(by_period)}"
    )
    for end, want in expected.items():
        got = by_period[end]
        assert got == {want}, (
            f"{ticker} R&D for the year ended {end} is {sorted(got)}, "
            f"expected {want:,}"
        )
