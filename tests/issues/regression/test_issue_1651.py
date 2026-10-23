"""
Regression test for GitHub Issue #1651: ``CurrencyConverter`` inverted a USD per
GBP rate, so GSK's 1.31 average turned GBP 100 into USD 76.34 instead of 131.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1651

``to_usd()`` always divided by the rate, which is right only for a rate quoted
as home currency per USD (Novo Nordisk's ``dkkPerUSD`` unit: 662 DKK per 100
USD). GSK tags its rates with a pure-number unit on the ``srt:CurrencyAxis``
member ``currency:USD``, and the filed quote is the other way, US$ per £.

The converter now records the direction of its rates. ``get_rate()`` still
returns the rate as filed (1.31), ``to_usd()`` multiplies by a USD-per-home rate
and divides by a home-per-USD one, and ``repr()`` names the direction. A pure
number does not state its direction, so reading it as USD per home unit is an
assumption, and ``extraction_warnings`` says so. A pure-number rate with no
currency member at all is not used.

Ground truth: GSK plc FY2025 20-F, accession 0001131399-26-000004, note 5
"Exchange rates": "Average rates: US$/£ 1.31 1.28 1.24" (2025, 2024, 2023). The
control is Novo Nordisk's FY2025 20-F, accession 0000353278-26-000012: 662 DKK
per 100 USD for 2025.
"""

import pandas as pd
import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.currency import CurrencyConverter

pytestmark = [pytest.mark.regression]

# Same instance documents and cassettes as test_issue_1650 and test_issue_1652.
GSK_URL = ("https://www.sec.gov/Archives/edgar/data/1131399/000113139926000004/"
           "gsk-20251231_htm.xml")
GSK_CASSETTE = "currency_gsk_20f_0001131399-26-000004.yaml"
NVO_URL = ("https://www.sec.gov/Archives/edgar/data/353278/000035327826000012/"
           "nvo-20251231_htm.xml")
NVO_CASSETTE = "currency_nvo_20f_0000353278-26-000012.yaml"


def _load(vcr, tmp_path_factory, url, cassette):
    folder = tmp_path_factory.mktemp("xbrl")
    with vcr.use_cassette(cassette):
        text = download_file(url)
    (folder / url.rsplit("/", 1)[-1]).write_text(text, encoding="utf-8")
    return XBRL.from_directory(folder)


@pytest.fixture(scope="module")
def gsk_converter(vcr, tmp_path_factory):
    return CurrencyConverter(_load(vcr, tmp_path_factory, GSK_URL, GSK_CASSETTE))


@pytest.fixture(scope="module")
def nvo_converter(vcr, tmp_path_factory):
    return CurrencyConverter(_load(vcr, tmp_path_factory, NVO_URL, NVO_CASSETTE))


def test_gsk_us_dollars_per_pound_converts_the_right_way(gsk_converter):
    assert gsk_converter.home_currency == "GBP"
    assert gsk_converter.get_rate(2025) == 1.31          # as filed
    # GBP 100 is USD 131 (was 76.34)
    assert gsk_converter.to_usd(100, 2025) == pytest.approx(131.0)
    assert gsk_converter.from_usd(100, 2025) == pytest.approx(76.33587786259541)
    assert gsk_converter.to_usd(100, 2025, rate_type="closing") == pytest.approx(135.0)
    assert "Rates (USD per GBP)" in repr(gsk_converter)
    assert ("the rates use a pure-number unit, which does not state their direction; "
            "read as USD per 1 GBP") in gsk_converter.extraction_warnings


def test_novo_dkk_per_100_usd_is_unchanged(nvo_converter):
    # The control from the issue: a fix that flips every rate would break this.
    assert nvo_converter.get_rate(2025) == 662.0
    assert nvo_converter.to_usd(662, 2025) == pytest.approx(100.0)
    assert nvo_converter.from_usd(100, 2025) == pytest.approx(662.0)
    assert "Rates (DKK per 100 USD)" in repr(nvo_converter)
    assert nvo_converter.extraction_warnings == []


# ---------------------------------------------------------------------------
# Offline
# ---------------------------------------------------------------------------

class _Context:
    def __init__(self, dimensions):
        self.dimensions = dimensions


class _Query:
    def __init__(self, frames):
        self._frames = frames
        self._concept = None

    def by_concept(self, concept, exact=False):
        self._concept = concept
        return self

    def to_dataframe(self):
        return self._frames.get(self._concept, pd.DataFrame())


class _Facts:
    def __init__(self, frames):
        self._frames = frames

    def to_dataframe(self):
        return pd.DataFrame({"unit_ref": ["gbp"]})

    def query(self):
        return _Query(self._frames)


class _StubXBRL:
    units = {"gbp": {"type": "simple", "measure": "iso4217:GBP"},
             "number": {"type": "simple", "measure": "xbrli:pure"}}

    def __init__(self, dimensions, value):
        self.contexts = {"c-1": _Context(dimensions)}
        self.facts = _Facts({"ifrs-full:AverageForeignExchangeRate": pd.DataFrame({
            "unit_ref": ["number"], "context_ref": ["c-1"],
            "period_end": ["2025-12-31"], "numeric_value": [value],
        })})


def test_pure_rate_on_the_usd_member_is_usd_per_home_unit():
    converter = CurrencyConverter(_StubXBRL({"srt:CurrencyAxis": "currency:USD"}, 1.31))
    assert converter.to_usd(100, 2025) == pytest.approx(131.0)
    assert converter.from_usd(131, 2025) == pytest.approx(100.0)


def test_pure_rate_naming_no_currency_is_reported_not_used():
    converter = CurrencyConverter(_StubXBRL({}, 1.31))
    assert converter.to_usd(100, 2025) is None
    assert converter.extraction_warnings == [
        "1 average exchange rate fact(s) with a pure-number unit name no currency "
        "(srt:CurrencyAxis) and were not used"
    ]
