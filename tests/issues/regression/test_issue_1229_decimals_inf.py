"""Regression test for issue #1229.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1229

`get_statement()` rewrote the XBRL accuracy sentinel `decimals="INF"` to integer
0. Apple's $0.00001 par value is filed exactly; `FactQuery` reported
`decimals='INF'` for facts f-196 and f-197 while the statement built from the
same facts claimed 0, which says something different -- rounded to the unit.

The conversion was written out five times in `edgar/xbrl/xbrl.py`. It now lives
in `edgar.xbrl.core.normalize_decimals`, which keeps the sentinel, and the
places that scale or format ask `decimals_for_scaling` for a number.

That second helper is load-bearing rather than cosmetic: a share count filed
with `decimals="INF"` carries the same "do not scale" signal as 0, and treating
the sentinel as unknown scaled AEON's 38,818,536 dilutive securities down to 39
in the rendered statement.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import decimals_for_scaling, normalize_decimals

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"


# --- the two helpers --------------------------------------------------------

@pytest.mark.parametrize("filed,expected", [
    ("INF", "INF"),
    ("inf", "INF"),
    (" INF ", "INF"),
    ("-6", -6),
    (-6, -6),
    ("2", 2),
    ("nonsense", 0),
    (None, None),
])
def test_normalize_decimals_keeps_the_sentinel(filed, expected):
    assert normalize_decimals(filed) == expected


@pytest.mark.parametrize("stored,expected", [
    ("INF", 0),      # exact: implies no scale
    (None, 0),
    (-6, -6),
    (0, 0),
    ("nonsense", 0),
])
def test_decimals_for_scaling_always_returns_a_number(stored, expected):
    assert decimals_for_scaling(stored) == expected


# --- the reported filing ----------------------------------------------------

def test_apple_par_value_keeps_inf_through_get_statement():
    xbrl = XBRL.from_directory(DATA / "aapl")
    role = "http://www.apple.com/role/CONSOLIDATEDBALANCESHEETSParenthetical"
    concept = "us-gaap_CommonStockParOrStatedValuePerShare"

    facts = xbrl.query().by_concept("us-gaap:CommonStockParOrStatedValuePerShare",
                                    exact=True).execute()
    assert facts, "expected the par-value facts in the AAPL fixture"
    assert {fact["decimals"] for fact in facts} == {"INF"}

    item = next(item for item in xbrl.get_statement(role)
                if item.get("concept") == concept)

    assert set(item["values"].values()) == {1e-05}
    # The statement must report what was filed, not a rounded-to-the-unit 0.
    assert set(item["decimals"].values()) == {"INF"}


def test_a_share_count_filed_as_inf_is_not_scaled_down():
    """The sentinel means exact, so nothing about it implies a scale."""
    xbrl = XBRL.from_directory(DATA / "aeon")
    role = ("http://www.aeonbiopharma.com/role/DisclosureSummaryOfSignificant"
            "AccountingPoliciesPotentiallyDilutiveSecuritiesOutstandingDetails")

    rendered = str(xbrl.statements[role])

    assert "38,818,536" in rendered
    assert "14,479,999" in rendered
