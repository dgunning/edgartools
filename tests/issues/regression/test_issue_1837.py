"""Quarterly stitched statements reported filtered-statement positions as source filing indices.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1837

With the default ``use_optimal_periods=True`` the stitcher receives one filtered
statement per selected period, so a 10-Q that contributes both its quarter and its
year-to-date column appears twice. ``StatementStitcher._extract_periods`` enumerated
those statements and published the positions as ``period_sources``, which the query
layer reads as an index into ``XBRLS.xbrl_list``. ORCL's six-month column was
attributed to the next filing and its Q1 to index 2 of a two-filing list. Each
statement now carries the index of the filing it came from.

Ground truth:
* Apple 10-Q for the quarter ended 2023-07-01, accession 0000320193-23-000077
  (fixture tests/fixtures/xbrl/aapl/10q_2023): net sales of $81,797 million for
  2023-04-02 to 2023-07-01 and $293,787 million for 2022-09-25 to 2023-07-01, both
  undimensioned facts in the one filing.
* Oracle 10-Qs 0000950170-24-134973 (Q2 FY2025) and 0000950170-24-104905 (Q1
  FY2025): total revenues of $14,059 million for the quarter and $27,366 million
  for the six months ended 2024-11-30, and $13,307 million for the quarter ended
  2024-08-31.
"""
import pytest

from edgar.xbrl import XBRL, XBRLS

REVENUE = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"


def _revenue_and_sources(xbrls):
    statement = xbrls.get_statement("IncomeStatement", standard=False, include_quarterly=True)
    revenue = next(row for row in statement["statement_data"] if row.get("concept") == REVENUE)
    return {pid: (revenue["values"].get(pid), statement["period_sources"][pid])
            for pid, _ in statement["periods"]}


@pytest.mark.fast
def test_quarter_and_ytd_from_one_filing_share_its_index():
    xbrls = XBRLS.from_xbrl_objects([XBRL.from_directory("tests/fixtures/xbrl/aapl/10q_2023")])
    assert _revenue_and_sources(xbrls) == {
        "duration_2023-04-02_2023-07-01": (81_797_000_000, 0),
        "duration_2022-09-25_2023-07-01": (293_787_000_000, 0),
    }


@pytest.mark.network
def test_oracle_six_month_column_comes_from_the_q2_filing():
    from edgar import find

    q2 = XBRL.from_filing(find("0000950170-24-134973"))
    q1 = XBRL.from_filing(find("0000950170-24-104905"))
    assert _revenue_and_sources(XBRLS.from_xbrl_objects([q2, q1])) == {
        "duration_2024-09-01_2024-11-30": (14_059_000_000, 0),
        "duration_2024-06-01_2024-11-30": (27_366_000_000, 0),
        "duration_2024-06-01_2024-08-31": (13_307_000_000, 1),
    }
