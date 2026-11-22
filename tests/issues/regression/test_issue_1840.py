"""Regression test for GH #1840: an entirely empty FY2016 column in Ambac's comprehensive income.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1840

``comprehensive_income()`` resolves Ambac's "Consolidated Statements of Total
Comprehensive Income", which the catalog types IncomeStatement by its abstract.
Period selection counted facts typed ComprehensiveIncome, found none for any
candidate, and its fallback returned every filing-wide annual candidate,
including FY2016, whose only fact is a 5% share-transfer restriction in another
disclosure. The fallback now keeps only candidates in which the statement itself
has a value.

Ground truth: Ambac Financial Group 10-K FY2022 (0000874501-23-000040). The
statement presents 2022, 2021 and 2020. The only fact in the FY2016 context
(D20160101-20161231) is ambc:CommonStockAdditionalTransferRestrictions = 0.05.
"""
import pytest

from edgar import find
from edgar.xbrl.period_selector import _keep_periods_with_statement_values

CANDIDATES = [('duration_2022-01-01_2022-12-31', 'FY2022'), ('duration_2021-01-01_2021-12-31', 'FY2021'),
              ('duration_2020-01-01_2020-12-31', 'FY2020'), ('duration_2016-01-01_2016-12-31', 'FY2016')]


@pytest.mark.fast
def test_fallback_keeps_only_periods_the_statement_has_values_for():
    rows = [{'concept': 'us-gaap_NetIncomeLoss',
             'values': {'duration_2022-01-01_2022-12-31': 1.0, 'duration_2021-01-01_2021-12-31': 2.0,
                        'duration_2020-01-01_2020-12-31': 3.0}}]
    kept = [key for key, _ in _keep_periods_with_statement_values(CANDIDATES, rows)]
    assert kept == ['duration_2022-01-01_2022-12-31', 'duration_2021-01-01_2021-12-31',
                    'duration_2020-01-01_2020-12-31']


@pytest.mark.fast
def test_candidates_are_untouched_without_statement_values():
    assert _keep_periods_with_statement_values(CANDIDATES, None) == CANDIDATES
    no_overlap = [{'concept': 'x', 'values': {'duration_2010-01-01_2010-12-31': 1.0}}]
    assert _keep_periods_with_statement_values(CANDIDATES, no_overlap) == CANDIDATES


@pytest.mark.network
def test_ambac_comprehensive_income_has_no_fy2016_column():
    statement = find("0000874501-23-000040").xbrl().statements.comprehensive_income()
    assert statement.role_or_type == "http://www.ambac.com/role/ConsolidatedStatementsofTotalComprehensiveIncome"
    for view in ("standard", "detailed"):
        keys = [p.key for p in statement.render(view=view, standard=True).periods]
        assert keys == ['duration_2022-01-01_2022-12-31', 'duration_2021-01-01_2021-12-31',
                        'duration_2020-01-01_2020-12-31']  # also had duration_2016-01-01_2016-12-31
    columns = [c for c in statement.to_dataframe().columns if c.endswith("(FY)")]
    assert columns == ['2022-12-31 (FY)', '2021-12-31 (FY)', '2020-12-31 (FY)']
