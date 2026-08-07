"""
Regression test for GH #797: viewer.financial_statements missing primary statements.

ABBV's 2021 10-K (acc 0001551152-22-000007) places its Consolidated Statements
of Earnings under MenuCategory='Uncategorized' in FilingSummary.xml — a filer
mistake. EdgarTools previously surfaced viewer.financial_statements only by
that category, so the income statement was silently dropped.

The fix in edgar/xbrl/viewer.py adds a MetaLinks.json fallback: any report
whose groupType='statement' is also surfaced as a financial statement, even
if FilingSummary.xml miscategorizes it.
"""
import pytest

from edgar import Filing


ABBV_CIK = 1551152
ABBV_2021_ACC = "0001551152-22-000007"  # 10-K filed 2022-02-04
ABBV_2020_ACC = "0001551152-21-000008"  # 10-K filed 2021-02-19 (regression baseline)


def _abbv_filing(accession_no: str, filing_date: str) -> Filing:
    return Filing(form="10-K", filing_date=filing_date,
                  company="AbbVie Inc.", cik=ABBV_CIK,
                  accession_no=accession_no)


@pytest.mark.network
def test_abbv_2021_income_statement_salvaged_from_uncategorized():
    """
    Ground truth: ABBV's 2021 10-K filer placed 'Consolidated Statements
    of Earnings' (R3) under MenuCategory='Uncategorized' instead of
    'Statements'. MetaLinks.json correctly classifies it as
    groupType='statement'. The viewer must surface it via that fallback.
    """
    filing = _abbv_filing(ABBV_2021_ACC, "2022-02-04")
    viewer = filing.viewer
    assert viewer is not None

    short_names = [vr.short_name for vr in viewer.financial_statements]

    # Income statement is present
    assert "Consolidated Statements of Earnings" in short_names

    # All four primary statements + their parentheticals = 7
    expected = {
        "Consolidated Statements of Earnings",
        "Consolidated Statements of Comprehensive Income",
        "Consolidated Statements of Comprehensive Income (Parenthetical)",
        "Consolidated Balance Sheets",
        "Consolidated Balance Sheets (Parenthetical)",
        "Consolidated Statements of Equity",
        "Consolidated Statements of Cash Flows",
    }
    assert set(short_names) == expected, (
        f"Missing: {expected - set(short_names)}, "
        f"Extra: {set(short_names) - expected}"
    )
    assert len(short_names) == 7

    # Position-preserving: Earnings is R3, comes before R4 (Comp. Income).
    earnings_idx = short_names.index("Consolidated Statements of Earnings")
    comp_idx = short_names.index("Consolidated Statements of Comprehensive Income")
    assert earnings_idx < comp_idx

    # The salvage path is the one that surfaced Earnings — its FilingSummary
    # category is still 'Uncategorized' (we don't rewrite the source data).
    earnings_vr = next(vr for vr in viewer.financial_statements
                       if vr.short_name == "Consolidated Statements of Earnings")
    assert earnings_vr.category == "Uncategorized"


@pytest.mark.network
def test_abbv_2020_unchanged_no_double_counting():
    """
    Regression: ABBV 2020 10-K is correctly categorized in FilingSummary.xml.
    All 7 primary statements are already under MenuCategory='Statements'.
    The MetaLinks fallback must not double-count them.
    """
    filing = _abbv_filing(ABBV_2020_ACC, "2021-02-19")
    viewer = filing.viewer
    assert viewer is not None

    stmts = viewer.financial_statements
    assert len(stmts) == 7

    # No duplicates
    file_names = [vr.html_file_name for vr in stmts]
    assert len(file_names) == len(set(file_names))

    # All 7 surfaced via the regular Statements category, not the fallback
    assert all(vr.category == "Statements" for vr in stmts)
