"""Regression: rendered statements formatted rates, share counts and per-share values as money.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1737

The renderer chose a cell's format from two built-in concept lists and label
words. Any other value went through the statement's monetary scale: a rate
filed as 0.147 divided by a million rendered ``0.00``, and an unlisted share
count rendered as money-scaled ``68.32``. A monetary row whose label contains
"ratio" ("Net cash from operations") lost its currency symbol.

Each cell is now formatted from its own unit definition (GH #1747,
``classify_unit_definition``): money takes the statement scale and its own
currency's symbol, shares the share scale, per-share amounts and pure or other
units are never scaled. A cell with no unit definition (a hand-built statement)
keeps the concept-list formatting.

Ground truth, read from the tracked fixtures' instance documents:

- Apple 10-K FY2023, 0000320193-23-000106 (tests/fixtures/xbrl/aapl/10k_2023):
  EffectiveIncomeTaxRateContinuingOperations 0.147 / 0.162 / 0.133 (unit
  ``number`` = xbrli:pure, decimals 3); IncrementalCommonSharesAttributableTo
  ShareBasedPaymentArrangements 68,316,000 / 109,856,000 / 163,647,000 (unit
  ``shares``, decimals -3; fact f-413 for FY2023).
- ExxonMobil 10-K FY2022, 0000034088-23-000020 (tests/fixtures/xbrl/xom/10k_2023):
  EffectiveIncomeTaxRateContinuingOperations 0.33 / 0.31 / 0.17 (pure, decimals 2).
- Coca-Cola 10-K FY2023, 0000021344-24-000009 (tests/fixtures/xbrl/ko/10k_2024):
  WeightedAverageNumberDilutedSharesOutstandingAdjustment 16,000,000 /
  22,000,000 / 25,000,000 (shares, decimals -6) on the income statement.
- Microsoft 10-K FY2024, 0000950170-24-087843 (tests/fixtures/xbrl/msft/10k_2024):
  NetCashProvidedByUsedInOperatingActivities 118,548,000,000 (U_USD, decimals -6).
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import classify_unit_definition, unit_definition
from edgar.xbrl.rendering import _format_value_for_display_as_string

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"
APPLE_TAX = ("http://www.apple.com/role/IncomeTaxesReconciliationofProvisionforIncomeTaxesto"
             "AmountComputedbyApplyingtheStatutoryFederalIncomeTaxRatetoIncomeBeforeProvisionfor"
             "IncomeTaxesDetails")
APPLE_EPS = "http://www.apple.com/role/EarningsPerShareComputationofBasicandDilutedEarningsPerShareDetails"
XOM_TAX = ("http://www.exxonmobil.com/role/IncomeAndOtherTaxesReconciliationBetweenIncomeTaxExpense"
           "AndTheoreticalUSTaxDetails")
KO_INCOME = "http://www.thecocacolacompany.com/role/CONSOLIDATEDSTATEMENTSOFINCOME"
MSFT_CASH = "http://www.microsoft.com/20240630/taxonomy/role/Role_StatementCASHFLOWSSTATEMENTS"

XBRLI = "{http://www.xbrl.org/2003/instance}"
ISO = "{http://www.xbrl.org/2003/iso4217}"


def _render(fixture, role):
    return XBRL.from_directory(FIXTURES / fixture).render_statement(role)


def _row(rendered, concept):
    return next(r for r in rendered.rows if r.metadata.get("concept") == concept and not r.is_dimension)


def _text(rendered, concept):
    return [cell.get_formatted_value() for cell in _row(rendered, concept).cells]


def test_apple_effective_tax_rate_renders_as_filed():
    rendered = _render("aapl/10k_2023", APPLE_TAX)
    concept = "us-gaap_EffectiveIncomeTaxRateContinuingOperations"
    assert _text(rendered, concept) == ["0.147", "0.162", "0.133"]
    # Display only: the raw values and the DataFrame are unchanged
    assert [c.value for c in _row(rendered, concept).cells] == [0.147, 0.162, 0.133]
    frame = rendered.to_dataframe()
    row = frame.loc[frame["concept"].eq(concept)].iloc[0]
    assert [row[p.end_date] for p in rendered.header.periods] == [0.147, 0.162, 0.133]
    # Monetary rows of the same table keep the statement's millions
    assert _text(rendered, "us-gaap_IncomeTaxExpenseBenefit") == ["16,741", "19,300", "14,527"]


def test_apple_unlisted_share_count_uses_the_share_scale():
    rendered = _render("aapl/10k_2023", APPLE_EPS)
    assert _text(rendered, "us-gaap_IncrementalCommonSharesAttributableToShareBasedPaymentArrangements") == [
        "68,316", "109,856", "163,647"]
    # Same thousands as the listed share rows it sits between
    assert _text(rendered, "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic") == [
        "15,744,231", "16,215,963", "16,701,272"]
    assert _text(rendered, "us-gaap_EarningsPerShareDiluted") == ["6.13", "6.11", "5.61"]
    assert rendered.header.metadata["shares_scale"] == -3


def test_exxon_effective_tax_rate_renders_as_filed():
    rendered = _render("xom/10k_2023", XOM_TAX)
    assert _text(rendered, "us-gaap_EffectiveIncomeTaxRateContinuingOperations") == ["0.33", "0.31", "0.17"]


def test_coca_cola_dilutive_shares_are_not_money():
    rendered = _render("ko/10k_2024", KO_INCOME)
    assert _text(rendered, "us-gaap_WeightedAverageNumberDilutedSharesOutstandingAdjustment") == ["16", "22", "25"]


def test_monetary_row_labelled_with_ratio_substring_keeps_its_symbol():
    """'operations' contains 'ratio'; the label no longer decides what is money."""
    rendered = _render("msft/10k_2024", MSFT_CASH)
    assert _text(rendered, "us-gaap_NetCashProvidedByUsedInOperatingActivities") == [
        "$118,548", "$87,582", "$89,035"]


def _unit(numerator, denominator=()):
    return classify_unit_definition(unit_definition(list(numerator), list(denominator),
                                                    list(numerator), list(denominator)))


def _format(value, unit_class, concept="custom_Anything", decimals=-6, monetary=True):
    item = {"concept": concept, "label": "Income from operations", "decimals": {"p": decimals}}
    return _format_value_for_display_as_string(value, item, "p", monetary, -6, None, None, None,
                                               unit_class=unit_class)


def test_unit_decides_the_format_not_the_concept_or_label():
    usd = _unit([f"{ISO}USD"])
    assert _format(5_000_000_000, usd) == "$5,000"
    assert _format(5_000_000_000, usd, monetary=False) == "5,000"
    assert _format(-0.37, _unit([f"{ISO}USD"], [f"{XBRLI}shares"]), decimals=2) == "-0.37"
    assert _format(150_000_000, _unit([f"{XBRLI}shares"]), decimals=0) == "150,000,000"
    assert _format(0.213, _unit([f"{XBRLI}pure"]), decimals=3) == "0.213"
    assert _format(0.00001, _unit([f"{XBRLI}pure"]), decimals="INF") == "0.00001"
    assert _format(4.0, _unit(["{http://example.com/x}segment"]), decimals="INF") == "4"


def test_unconfigured_currency_shows_its_code_never_a_dollar():
    assert _format(8_220_000_000, _unit([f"{ISO}NZD"])) == "NZD 8,220"


def test_zero_stays_blank_whatever_its_unit():
    assert _format(0, _unit([f"{XBRLI}pure"])) == ""
    assert _format(0.0, _unit([f"{XBRLI}shares"])) == ""
