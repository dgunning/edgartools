"""
Regression tests for edgartools-uetp (GH #1170): a divided XBRL unit was parsed
as a simple unit, so every per-share amount lost its denominator.

`_extract_units` searched for a measure with a DESCENDANT lookup:

    measure_elem = unit_elem.find('.//{...}measure')
    if measure_elem is not None and measure_elem.text:
        self.units[unit_id] = {'type': 'simple', 'measure': measure_elem.text}
        continue                       # <- always taken
    divide_elem = unit_elem.find('.//{...}divide')   # unreachable

A well-formed `xbrli:divide` necessarily contains measures inside its
`unitNumerator` and `unitDenominator`, so the descendant search always matched
the numerator first and returned. `usdPerShare` was recorded as
`{'type': 'simple', 'measure': 'iso4217:USD'}` — a per-share amount was
indistinguishable from a dollar amount at the unit level — and the `divide`
branch could not run for any real filing. Measured before the fix: zero units of
type `divide` across the fixture corpus.

`divide` is now tested first, and a simple unit's measure is looked up as a
direct child, which is where the spec puts it.

THE SECOND HALF. Fixing the parser alone would have introduced a silent
regression, because a `divide` unit has no `'measure'` key at all and two
consumers tested for one. Verified by running the parser fix WITHOUT the
consumer fix: `get_currency_for_fact` returned `None` for
`EarningsPerShareBasic` and `EarningsPerShareDiluted` on both Apple and
JPMorgan, where it had returned `iso4217:USD` — so every per-share cell would
have lost its currency symbol. The rule now lives once in
`edgar.xbrl.core.unit_currency`, since spelling a per-unit rule out in three
places is how the negated-label matchers drifted apart (edgartools-hxnw).
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import unit_currency, unit_currency_measure

AAPL = Path("tests/fixtures/xbrl/aapl/10k_2023")
JPM = Path("tests/fixtures/xbrl/jpm/10k_2013")


@pytest.fixture(scope="module")
def aapl():
    return XBRL.from_directory(AAPL)


@pytest.fixture(scope="module")
def jpm():
    return XBRL.from_directory(JPM)


def test_per_share_unit_keeps_its_denominator(aapl):
    """`usdPerShare` was `{'type': 'simple', 'measure': 'iso4217:USD'}`."""
    unit = aapl.units["usdPerShare"]

    assert unit["type"] == "divide"
    assert unit["numerator"] == ["iso4217:USD"]
    assert unit["denominator"] == ["shares"]


def test_a_filing_now_has_divided_units_at_all(aapl, jpm):
    """Zero units parsed as `divide` on any filing before the fix."""
    for xbrl in (aapl, jpm):
        divided = [u for u in xbrl.units.values() if u.get("type") == "divide"]
        assert len(divided) >= 1


def test_simple_units_are_untouched(aapl):
    """The overwhelming majority of units are simple and must stay that way."""
    assert aapl.units["usd"] == {"type": "simple", "measure": "iso4217:USD"}
    assert aapl.units["shares"] == {"type": "simple", "measure": "shares"}

    simple = [u for u in aapl.units.values() if u.get("type") == "simple"]
    assert len(simple) == 8


def test_per_share_facts_keep_their_currency(aapl, jpm):
    """
    The regression the parser fix would have caused on its own: a divide unit
    has no 'measure' key, and `get_currency_for_fact` tested for one.
    """
    for xbrl in (aapl, jpm):
        for element in ("us-gaap_EarningsPerShareBasic", "us-gaap_EarningsPerShareDiluted"):
            found = None
            for period in xbrl.reporting_periods:
                found = xbrl.get_currency_for_fact(element, period.get("key"))
                if found:
                    break
            assert found == "iso4217:USD", element


def test_eps_facts_report_usd_on_the_facts_api(aapl):
    df = aapl.facts.query().to_dataframe()
    eps = df[df["concept"].str.contains("EarningsPerShare", na=False)]

    assert len(eps) > 0
    assert set(eps["currency"].dropna()) == {"USD"}


@pytest.mark.parametrize(
    "unit_info, code, measure",
    [
        ({"type": "divide", "numerator": ["iso4217:USD"], "denominator": ["shares"]}, "USD", "iso4217:USD"),
        ({"type": "divide", "numerator": ["iso4217:HKD"], "denominator": ["xbrli:shares"]}, "HKD", "iso4217:HKD"),
        ({"type": "simple", "measure": "iso4217:EUR"}, "EUR", "iso4217:EUR"),
        # Non-monetary units have no currency, by either spelling.
        ({"type": "simple", "measure": "shares"}, None, None),
        ({"type": "simple", "measure": "pure"}, None, None),
        # A ratio of two non-monetary measures is not a currency either.
        ({"type": "divide", "numerator": ["shares"], "denominator": ["pure"]}, None, None),
        (None, None, None),
    ],
)
def test_the_shared_currency_rule(unit_info, code, measure):
    """One rule, so the three consumers cannot drift apart."""
    assert unit_currency(unit_info) == code
    assert unit_currency_measure(unit_info) == measure
