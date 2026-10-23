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
    # 1.31 is plausible only as USD per GBP (0.76 USD per GBP or 76 are not),
    # and the yen rate (198) agrees, so nothing is assumed.
    assert gsk_converter.rate_basis[(2025, "average")] == "USD per GBP (only plausible reading)"
    assert gsk_converter.extraction_warnings == []


def test_novo_dkk_per_100_usd_is_unchanged(nvo_converter):
    # The control from the issue: a fix that flips every rate would break this.
    assert nvo_converter.get_rate(2025) == 662.0
    assert nvo_converter.to_usd(662, 2025) == pytest.approx(100.0)
    assert nvo_converter.from_usd(100, 2025) == pytest.approx(662.0)
    assert "Rates (DKK per 100 USD)" in repr(nvo_converter)
    assert nvo_converter.rate_basis[(2025, "average")] == \
        "DKK per 100 USD (only plausible reading)"
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


# ---------------------------------------------------------------------------
# Review follow-up: the direction is read per rate, from the plausible band
# for the currency, never from a fixed rule. Values are those the review read
# from SEC companyfacts (scratchpad scan.log, 404 IFRS filers).
# ---------------------------------------------------------------------------

def _pure(home, value, year=2025, member="currency:USD", kind="average", siblings=()):
    """A filing with one pure-number rate (plus optional sibling currencies)."""
    rows = [(member, value)] + [(f"currency:{code}", v) for code, v in siblings]
    contexts = {f"c-{i}": _Context({"srt:CurrencyAxis": m} if m else {})
                for i, (m, _) in enumerate(rows)}
    date = f"{year}-12-31"
    frame = pd.DataFrame({
        "unit_ref": ["number"] * len(rows),
        "context_ref": [f"c-{i}" for i in range(len(rows))],
        "period_start": [f"{year}-01-01" if kind == "average" else float("nan")] * len(rows),
        "period_end": [date if kind == "average" else float("nan")] * len(rows),
        "period_instant": [float("nan") if kind == "average" else date] * len(rows),
        "numeric_value": [v for _, v in rows],
    })
    concept = ("ifrs-full:AverageForeignExchangeRate" if kind == "average"
               else "ifrs-full:ClosingForeignExchangeRate")
    stub = _StubXBRL({}, 1.0)
    stub.units = {"home": {"type": "simple", "measure": f"iso4217:{home}"},
                  "number": {"type": "simple", "measure": "xbrli:pure"}}
    stub.contexts = contexts
    stub.facts = _Facts({concept: frame})
    stub.facts.to_dataframe = lambda: pd.DataFrame({"unit_ref": ["home"]})
    return CurrencyConverter(stub)


def test_sun_life_cad_per_usd_is_not_inverted():
    # Sun Life Financial 40-F, average 2019, pure unit: 1.33 CAD per USD.
    # A fixed "USD per home" rule read it as USD 1.33 per CAD.
    converter = _pure("CAD", 1.33, year=2019)
    assert converter.to_usd(133, 2019) == pytest.approx(100.0)
    assert converter.rate_basis[(2019, "average")] == "CAD per USD (only plausible reading)"


def test_tata_motors_inr_per_usd_is_not_inverted():
    # Tata Motors 20-F, closing 2019-03-31 (as year 2019), pure unit: 69.155.
    # Read as USD per INR it was 8,300x off; as "per 100" (the old > 10 rule) 100x.
    converter = _pure("INR", 69.155, year=2019, kind="closing")
    assert converter.to_usd(69.155, 2019, rate_type="closing") == pytest.approx(1.0)


def test_national_grid_usd_per_gbp_reads_the_other_way():
    # National Grid 6-K, average to 2024-09-30, pure unit: 1.30 USD per GBP.
    converter = _pure("GBP", 1.30, year=2024)
    assert converter.to_usd(100, 2024) == pytest.approx(130.0)


def test_immatics_eur_rate_near_parity_is_refused_not_guessed():
    # Immatics 20-F, average 2023, pure unit: 0.9246. It is EUR per USD, but
    # 0.9246 USD per EUR (2000-2002) is also plausible and the filing says
    # nothing more, so no rate is better than a coin toss.
    converter = _pure("EUR", 0.9246, year=2023)
    assert converter.get_rate(2023) is None
    assert converter.to_usd(100, 2023) is None
    assert ("the average rate for 2023 (0.9246) was not used: it is plausible as "
            "USD per EUR or EUR per USD, and nothing in the filing says which"
            ) in converter.extraction_warnings


def test_biontech_usd_per_eur_alone_is_refused():
    # BioNTech 20-F (0001776985-26-000049), 2024 average 1.0824 on the USD
    # member, with no other currency in the table: ambiguous the same way.
    converter = _pure("EUR", 1.0824, year=2024)
    assert converter.to_usd(100, 2024) is None


def test_a_sibling_currency_settles_a_near_parity_rate():
    # By construction: the same EUR table with a yen rate of 160. As JPY per
    # EUR that is plausible; as EUR per JPY it is not. So the table quotes
    # foreign currency per euro and 1.0824 is USD per EUR.
    converter = _pure("EUR", 1.0824, year=2024, siblings=[("JPY", 160.0)])
    assert converter.to_usd(100, 2024) == pytest.approx(108.24)
    assert converter.rate_basis[(2024, "average")] == (
        "USD per EUR (plausible either way, settled by the other currencies' "
        "rates in the filing)")


def test_a_lone_pure_rate_with_no_currency_is_used_when_unambiguous():
    # Sun Life's 1.33 again, but with no srt:CurrencyAxis member at all.
    converter = _pure("CAD", 1.33, year=2019, member=None)
    assert converter.to_usd(133, 2019) == pytest.approx(100.0)
    assert ("the average rate for 2019 (1.33) names no currency (srt:CurrencyAxis); "
            "it was read as a USD rate because that is its only plausible reading"
            ) in converter.extraction_warnings


def test_a_lone_pure_rate_with_no_currency_is_refused_when_ambiguous():
    converter = _pure("EUR", 1.0824, year=2024, member=None)
    assert converter.to_usd(100, 2024) is None


def test_a_currency_with_no_known_band_is_refused():
    # Argentine peso: too volatile for any band to tell the readings apart.
    converter = _pure("ARS", 1032.5, year=2024)
    assert converter.to_usd(1032.5, 2024) is None
    assert any("no plausible range is known for USD per ARS" in w
               for w in converter.extraction_warnings)


# The old "> 10 means per 100 USD" rule, on divide-unit filers (values from
# scan.log). Each came out 100x off.
@pytest.mark.parametrize("home, value, year", [
    ("MXN", 19.9493, 2020),   # Grupo Televisa, MXN/USD closing 2020-12-31
    ("ZAR", 17.77, 2023),     # Sasol, ZAR/USD average to 2023-06-30
    ("RUB", 73.6541, 2021),   # QIWI, RUB/USD average 2021
    ("INR", 69.16, 2019),     # Wipro, INR/USD closing 2019-03-31
])
def test_home_per_usd_divide_units_above_ten_are_not_per_100(home, value, year):
    stub = _StubXBRL({}, value)
    stub.units = {"home": {"type": "simple", "measure": f"iso4217:{home}"},
                  "u": {"type": "divide", "numerator": [f"iso4217:{home}"],
                        "denominator": ["iso4217:USD"]}}
    stub.facts = _Facts({"ifrs-full:AverageForeignExchangeRate": pd.DataFrame({
        "unit_ref": ["u"], "context_ref": ["c-1"],
        "period_end": [f"{year}-12-31"], "numeric_value": [value],
    })})
    stub.facts.to_dataframe = lambda: pd.DataFrame({"unit_ref": ["home"]})
    converter = CurrencyConverter(stub)
    assert converter.to_usd(value, year) == pytest.approx(1.0)
    assert converter.rate_basis[(year, "average")] == f"{home} per USD (only plausible reading)"
