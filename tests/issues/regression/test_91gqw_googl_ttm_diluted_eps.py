"""Regression test: GOOGL TTM diluted EPS was NaN for Q2 and Q3 2026.

Bead: edgartools-91gqw

Alphabet's Q2 2026 10-Q (0001652044-26-000071) tags no
NetIncomeLossAvailableToCommonStockholdersDiluted, so the TTM windows ending
Q2 and Q3 2026 must use the basic numerator. GH #1692's rule refuses a lesser
numerator wherever the filer shows it differing from the better one, and the
Q3 2026 10-Q (0001652044-26-000084) tags 9M 2026 diluted 201,239M against
basic 200,855M, a 0.19% gap. Diluted EPS was left NaN. A substitute now stands
in when the filer's figures differ by at most 0.5% of the preferred value
(``EPS_NUMERATOR_REL_TOLERANCE``); #1692's preferred-dividend case (10%) is
still refused.

Values read from SEC companyfacts (CIK 1652044), basic numerator in $M:
FY 2025 132,170 and 9M 2025 97,715 (Q4 2025 = 34,455); Q3 2025 34,979;
Q1 2026 62,578; Q2 2026 112,107; Q3 2026 26,170. Diluted weighted shares (M):
Q1 2025 12,291, Q2 2025 12,198, Q3 2025 12,203, FY 2025 12,230, Q1 2026 12,238,
Q2 2026 12,309, Q3 2026 12,368.
"""
from datetime import date

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json
from edgar.ttm.calculator import EPS_NUMERATOR_REL_TOLERANCE, numerator_agrees_within

pytestmark = pytest.mark.regression

GOOGL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json"


def _fact(concept, value, start, end, filed):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept, value=value,
        numeric_value=float(value), unit="USD", period_start=start, period_end=end,
        period_type="duration", fiscal_year=end.year, fiscal_period="Q3",
        filing_date=filed, form_type="10-Q", statement_type="IncomeStatement",
    )


def _nine_months(concept, value):
    return [_fact(concept, value, date(2026, 1, 1), date(2026, 9, 30), date(2026, 10, 29))]


def _agrees(diluted, basic):
    return numerator_agrees_within(
        _nine_months("NetIncomeLossAvailableToCommonStockholdersDiluted", diluted),
        _nine_months("NetIncomeLossAvailableToCommonStockholdersBasic", basic),
        date(2025, 10, 1), date(2026, 9, 30))


def test_tolerance_is_half_a_percent():
    assert EPS_NUMERATOR_REL_TOLERANCE == 0.005


def test_googl_gap_of_0_19_percent_is_accepted():
    # Before the fix: refused (any gap over max($1, 1e-6 of the value)).
    assert _agrees(201_239e6, 200_855e6)


def test_gap_at_the_boundary_is_accepted_and_just_above_is_refused():
    assert _agrees(1_000_000e3, 995_000e3)          # 0.5%
    assert not _agrees(1_000_000e3, 994_000e3)      # 0.6%


def test_1692_preferred_dividend_gap_is_still_refused():
    # GH #1692's issuer: income available to common 900 vs net income 1,000.
    assert not _agrees(900e6, 1_000e6)


def test_periods_tagged_with_one_concept_only_are_no_evidence():
    late = [_fact("NetIncomeLoss", 5e9, date(2026, 4, 1), date(2026, 6, 30), date(2026, 7, 23))]
    assert numerator_agrees_within(_nine_months("X", 1e9), late, date(2025, 10, 1), date(2026, 9, 30))


def _window_shares(counts):
    """Day-weighted diluted share count over a window of (count, days) quarters."""
    return sum(c * d for c, d in counts) / sum(d for _, d in counts)


@pytest.mark.vcr
def test_googl_ttm_diluted_eps_uses_basic_numerator_when_diluted_quarter_missing():
    facts = EntityFactsParser.parse_company_facts(download_json(GOOGL_FACTS))
    items = {item["concept"]: item["values"]
             for item in facts.income_statement(period="ttm", periods=4).items}
    diluted = items["EarningsPerShareDiluted"]

    # Q4 2025 diluted count solved from the year: (FY x 365 - Q1..Q3 x days) / 92.
    q4_2025 = (12_230 * 365 - 12_291 * 90 - 12_198 * 91 - 12_203 * 92) / 92    # 12,229.0
    q2_numerator = 34_979 + 34_455 + 62_578 + 112_107                          # 244,119
    q3_numerator = 34_455 + 62_578 + 112_107 + 26_170                          # 235,310
    q2_shares = _window_shares([(12_203, 92), (q4_2025, 92), (12_238, 90), (12_309, 91)])
    q3_shares = _window_shares([(q4_2025, 92), (12_238, 90), (12_309, 91), (12_368, 92)])

    # Before the fix: NaN / None in both cells.
    assert diluted["Q2 2026"] == pytest.approx(q2_numerator / q2_shares)
    assert diluted["Q3 2026"] == pytest.approx(q3_numerator / q3_shares)
    assert round(diluted["Q2 2026"], 2) == 19.94
    assert round(diluted["Q3 2026"], 2) == 19.15
    # The window with a filed diluted numerator is unchanged: 62,578 + ... (Q1 2026).
    assert diluted["Q1 2026"] == pytest.approx(13.1136, abs=1e-4)

