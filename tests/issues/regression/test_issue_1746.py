"""
Regression test for GitHub issue #1746.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1746

Statement unit labels were guessed from substrings of the opaque unit id, so
Microsoft's basic EPS, filed in a unit with id
`U_UnitedStatesOfAmericaDollarsShare` that the parser correctly reads as
iso4217:USD divided by shares, was labelled `shares` -- the same label as the
weighted-average share count -- and revenue in unit `U_USD` was labelled
`u_usd`. The id only references a unit; its measures define it (XBRL 2.1
sections 4.8.1-4.8.4).

Each parsed unit now carries a `definition` descriptor (expanded-QName
numerator and denominator lists, GH #1747), and both statement DataFrame paths
label a row from the definitions of the cells it shows.

Real filing: Microsoft FY2024 10-K, accession 0000950170-24-087843, tracked
under tests/fixtures/xbrl/msft/10k_2024. Its `shares` and `pure` measures are
filed unprefixed under the default XBRL instance namespace.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import (
    UNIT_MIXED,
    UNIT_UNAVAILABLE,
    classify_unit_definition,
    get_unit_display_name,
    summarize_unit_definitions,
)
from edgar.xbrl.parsers import XBRLParser
from edgar.xbrl.rendering import RenderedStatement

ISO = "{http://www.xbrl.org/2003/iso4217}"
XBRLI = "{http://www.xbrl.org/2003/instance}"

# The issue's own synthetic units, plus ids that say the opposite of their measures
INSTANCE = """<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:my="http://example.com/my">
<xbrli:unit id="U_UnitedStatesOfAmericaDollarsShare"><xbrli:divide>
  <xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>
  <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>
</xbrli:divide></xbrli:unit>
<xbrli:unit id="U_USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
<xbrli:unit id="USD"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
<xbrli:unit id="U_shares"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
<xbrli:unit id="u1"><xbrli:measure xmlns:cur="http://www.xbrl.org/2003/iso4217">cur:GBP</xbrli:measure></xbrli:unit>
<xbrli:unit id="u2"><xbrli:measure xmlns:iso4217="http://example.com/not-iso">iso4217:USD</xbrli:measure></xbrli:unit>
<xbrli:unit id="u3"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>
<xbrli:unit id="u4"><xbrli:divide>
  <xbrli:unitNumerator><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unitNumerator>
  <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>
</xbrli:divide></xbrli:unit>
<xbrli:unit id="u5"><xbrli:measure>iso4217:USD</xbrli:measure><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
<xbrli:unit id="u6"><xbrli:divide>
  <xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>
  <xbrli:unitDenominator><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unitDenominator>
</xbrli:divide></xbrli:unit>
<xbrli:unit id="u7"><xbrli:measure>my:feet</xbrli:measure></xbrli:unit>
<xbrli:unit id="u8"><xbrli:measure>undeclared:USD</xbrli:measure></xbrli:unit>
</xbrli:xbrl>"""

EPS = "us-gaap_EarningsPerShareBasic"
REVENUE = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"
SHARES = "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic"


@pytest.fixture(scope="module")
def units():
    parser = XBRLParser()
    parser.parse_instance_content(INSTANCE)
    return parser.units


def _label(units, unit_id):
    return get_unit_display_name(unit_id, definition=units[unit_id])


@pytest.mark.fast
def test_issue_units_are_labelled_from_their_definitions(units):
    assert units["U_UnitedStatesOfAmericaDollarsShare"]["definition"] == {
        "numerator": [ISO + "USD"], "denominator": [XBRLI + "shares"], "expression": "iso4217:USD/xbrli:shares"}
    assert _label(units, "U_UnitedStatesOfAmericaDollarsShare") == "usdPerShare"
    assert _label(units, "U_USD") == "usd"
    # The descriptor alone works too
    assert get_unit_display_name(None, definition=units["U_USD"]["definition"]) == "usd"


@pytest.mark.fast
def test_misleading_ids_do_not_decide_the_label(units):
    assert _label(units, "USD") == "shares"
    assert _label(units, "U_shares") == "eur"


@pytest.mark.fast
def test_measures_resolve_by_namespace_not_prefix(units):
    # A local declaration with another prefix for the ISO namespace is still a currency
    assert _label(units, "u1") == "gbp"
    # The iso4217 prefix bound to another namespace confers no currency
    unit_class = classify_unit_definition(units["u2"])
    assert unit_class.kind == "other" and unit_class.currency is None
    assert unit_class.label == "iso4217:USD"


@pytest.mark.fast
def test_supported_shapes_and_complete_expressions(units):
    assert _label(units, "u3") == "number"  # pure: no percentage inferred
    assert _label(units, "u4") == "eurPerShare"
    # A product or another quotient is never reduced to its currency factor
    assert _label(units, "u5") == "iso4217:USD*xbrli:shares"
    assert _label(units, "u6") == "iso4217:USD/iso4217:EUR"
    assert classify_unit_definition(units["u6"]).currency is None
    assert _label(units, "u7") == "my:feet"


@pytest.mark.fast
def test_unresolved_unit_is_unavailable_never_guessed(units):
    assert units["u8"]["definition"] is None
    assert _label(units, "u8") == UNIT_UNAVAILABLE
    # An explicitly missing definition never falls back to reading the id
    assert get_unit_display_name("U-Monetary", definition=None) == UNIT_UNAVAILABLE


@pytest.mark.fast
def test_one_argument_legacy_heuristic_is_kept():
    assert get_unit_display_name("U-USD-per-shares") == "usdPerShare"
    assert get_unit_display_name("U_UnitedStatesOfAmericaDollarsShare") == "shares"
    assert get_unit_display_name(None) is None


@pytest.mark.fast
def test_row_summary(units):
    usd, usd_again = units["U_USD"], units["u1"]
    assert summarize_unit_definitions([usd, units["U_USD"]["definition"]]) == "usd"
    # Two unit ids with the same measures are one unit
    same_measures = {"numerator": [ISO + "USD"], "denominator": [], "expression": "cur:USD"}
    assert summarize_unit_definitions([usd, same_measures]) == "usd"
    assert summarize_unit_definitions([usd, usd_again]) == UNIT_MIXED
    assert summarize_unit_definitions([usd, None]) == UNIT_UNAVAILABLE
    assert summarize_unit_definitions([]) is None


@pytest.fixture(scope="module")
def msft():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/msft/10k_2024"))


def _rows(df):
    return df[df.concept.isin([REVENUE, EPS, SHARES])].drop_duplicates("concept").set_index("concept")


@pytest.mark.fast
def test_msft_source_facts(msft):
    """The facts the labels describe, from the filed instance."""
    eps = msft.facts.query().by_concept(EPS, exact=True).to_dataframe()
    eps = eps[eps.period_end == "2024-06-30"].iloc[0]
    assert (eps.period_start, eps.numeric_value, eps.decimals) == ("2023-07-01", 11.86, "2")
    assert eps.unit_ref == "U_UnitedStatesOfAmericaDollarsShare"


@pytest.mark.fast
@pytest.mark.parametrize("path", ["statement", "rendered"])
def test_msft_income_statement_units(msft, path):
    statement = msft.statements.income_statement()
    df = (statement.to_dataframe(include_unit=True) if path == "statement"
          else statement.render().to_dataframe(include_unit=True))
    rows = _rows(df)
    assert rows.loc[REVENUE, "unit"] == "usd"
    assert rows.loc[EPS, "unit"] == "usdPerShare"
    assert rows.loc[SHARES, "unit"] == "shares"
    # The labels change; the values beside them do not
    column = next(c for c in df.columns if str(c).startswith("2024-06-30"))
    assert rows.loc[REVENUE, column] == 245_122_000_000
    assert rows.loc[EPS, column] == 11.86
    assert rows.loc[SHARES, column] == 7_431_000_000


@pytest.mark.fast
def test_rendered_unit_survives_serialization_and_legacy_rows_are_unavailable(msft):
    rendered = msft.statements.income_statement().render()
    data = rendered.to_dict()
    assert _rows(RenderedStatement.from_dict(data).to_dataframe(include_unit=True)).loc[EPS, "unit"] == "usdPerShare"
    # A row serialized before #1746 has no unit definitions: no dollar guess
    for row in data["rows"]:
        row["metadata"].pop("unit_definitions", None)
    legacy = _rows(RenderedStatement.from_dict(data).to_dataframe(include_unit=True))
    assert legacy.loc[EPS, "unit"] == UNIT_UNAVAILABLE


@pytest.mark.fast
@pytest.mark.parametrize("path", ["statement", "rendered"])
def test_row_with_periods_in_different_units_is_mixed(path):
    xbrl = XBRL.from_directory(Path("tests/fixtures/xbrl/msft/10k_2024"))
    # Re-point the FY2022 EPS facts at the filing's EUR unit; FY2024/FY2023 stay USD per share
    for fact in xbrl._facts.values():
        if fact.element_id.endswith("EarningsPerShareBasic") and xbrl.contexts[fact.context_ref].period.get("startDate") == "2021-07-01":
            fact.unit_ref = "U_EUR"
    statement = xbrl.statements.income_statement()
    df = (statement.to_dataframe(include_unit=True) if path == "statement"
          else statement.render().to_dataframe(include_unit=True))
    assert _rows(df).loc[EPS, "unit"] == UNIT_MIXED
    assert _rows(df).loc[REVENUE, "unit"] == "usd"
