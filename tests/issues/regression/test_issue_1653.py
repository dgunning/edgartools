"""
Regression test for GitHub Issue #1653: ``CurrencyConverter`` returned no
exchange rates for SAP, because its divide-unit USD/EUR facts failed the unit-ID
filter.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1653

A rate unit was accepted only if its opaque id contained ``eurPerUSD``,
``eur_USD`` or ``eurUSD`` (for a EUR filer), or was ``number``/``pure``/``ratio``.
SAP's unit is ``Unit_Divide_USD_EUR_yMgaKio6_EuddQDx4uqKhg``, a divide unit with
numerator ``iso4217:USD`` and denominator ``iso4217:EUR``, so all 30 of its rate
facts were skipped and ``exchange_rates`` was ``{}`` with no warning.

Units are now read from their resolved numerator and denominator, either way
round: home per target keeps the old conversion, target per home (SAP's USD per
EUR) uses the quote direction added for #1651. The other 25 SAP rate facts (AUD,
CAD, CHF, GBP and JPY per EUR) are other currency pairs and stay unused.

Ground truth: SAP SE FY2025 20-F, accession 0001104659-26-020058, Exchange Rates
table ("Equivalent to €1", page F-12), USD row: annual averages 1.1293 (2025),
1.0821 (2024), 1.0816 (2023); middle rates at 12/31 1.1750 (2025), 1.0389 (2024).
"""

import pandas as pd
import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.currency import CurrencyConverter

pytestmark = [pytest.mark.regression]

# The instance document alone carries the facts, contexts and units the
# converter reads, so the cassette holds one 13.6 MB response.
SAP_URL = ("https://www.sec.gov/Archives/edgar/data/1000184/000110465926020058/"
           "sap-20251231x20f_htm.xml")
SAP_CASSETTE = "currency_sap_20f_0001104659-26-020058.yaml"


@pytest.fixture(scope="module")
def sap_converter(vcr, tmp_path_factory):
    folder = tmp_path_factory.mktemp("sap")
    with vcr.use_cassette(SAP_CASSETTE):
        text = download_file(SAP_URL)
    (folder / SAP_URL.rsplit("/", 1)[-1]).write_text(text, encoding="utf-8")
    return CurrencyConverter(XBRL.from_directory(folder))


def test_sap_usd_per_eur_rates_are_read(sap_converter):
    assert sap_converter.home_currency == "EUR"
    # As filed (was: no rates at all)
    assert sap_converter.get_rate(2025, "average") == 1.1293
    assert sap_converter.get_rate(2024, "average") == 1.0821
    assert sap_converter.get_rate(2023, "average") == 1.0816
    assert sap_converter.get_rate(2025, "closing") == 1.1750
    assert sap_converter.get_rate(2024, "closing") == 1.0389
    assert sap_converter.get_rate(2023, "closing") is None   # not in the table
    # EUR 1,000 is USD 1,129.30 at the 2025 average
    assert sap_converter.to_usd(1000, 2025) == pytest.approx(1129.3)
    assert sap_converter.from_usd(1129.3, 2025) == pytest.approx(1000.0)
    assert "Rates (USD per EUR)" in repr(sap_converter)
    # The divide unit states the direction, so nothing is assumed.
    assert sap_converter.extraction_warnings == []


# ---------------------------------------------------------------------------
# Offline
# ---------------------------------------------------------------------------

class _Query:
    def __init__(self, frame):
        self._frame = frame
        self._concept = None

    def by_concept(self, concept, exact=False):
        self._concept = concept
        return self

    def to_dataframe(self):
        if self._concept == "ifrs-full:AverageForeignExchangeRate":
            return self._frame
        return pd.DataFrame()


class _Facts:
    def __init__(self, frame):
        self._frame = frame

    def to_dataframe(self):
        return pd.DataFrame({"unit_ref": ["eur"]})

    def query(self):
        return _Query(self._frame)


class _StubXBRL:
    contexts: dict = {}

    def __init__(self, units, unit_refs, values):
        self.units = {"eur": {"type": "simple", "measure": "iso4217:EUR"}, **units}
        self.facts = _Facts(pd.DataFrame({
            "unit_ref": unit_refs, "context_ref": ["c-1"] * len(values),
            "period_end": ["2025-12-31"] * len(values), "numeric_value": values,
        }))


def _divide(numerator, denominator):
    return {"type": "divide", "numerator": [numerator], "denominator": [denominator]}


def test_divide_unit_with_an_opaque_id_is_read_from_its_measures():
    converter = CurrencyConverter(_StubXBRL(
        {"U_1": _divide("iso4217:USD", "iso4217:EUR"),
         "U_2": _divide("iso4217:AUD", "iso4217:EUR")},
        ["U_2", "U_1"], [1.7514, 1.1293],
    ))
    assert converter.get_rate(2025) == 1.1293
    assert converter.to_usd(1000, 2025) == pytest.approx(1129.3)


def test_extension_measure_denominator_is_read_by_local_name():
    # Vodafone's units divide by 'vod:EUR', not 'iso4217:EUR'.
    converter = CurrencyConverter(_StubXBRL(
        {"Unit_USD_EUR": _divide("iso4217:USD", "vod:EUR")}, ["Unit_USD_EUR"], [1.08],
    ))
    assert converter.get_rate(2025) == 1.08


def test_home_per_usd_divide_unit_keeps_the_old_conversion():
    converter = CurrencyConverter(_StubXBRL(
        {"U_1": _divide("iso4217:EUR", "iso4217:USD")}, ["U_1"], [0.8855],
    ))
    assert converter.to_usd(0.8855, 2025) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Review follow-up: a unit's measure order is a hint, not the truth. Some
# filers write it backwards; values from SEC companyfacts (scan.log).
# ---------------------------------------------------------------------------

class _OneRateXBRL:
    contexts: dict = {}

    def __init__(self, home, numerator, denominator, value, year, kind):
        self.units = {"home": {"type": "simple", "measure": f"iso4217:{home}"},
                      "u": _divide(f"iso4217:{numerator}", f"iso4217:{denominator}")}
        date = f"{year}-12-31"
        frame = pd.DataFrame({
            "unit_ref": ["u"], "context_ref": ["c-1"],
            "period_end": [date if kind == "average" else float("nan")],
            "period_instant": [float("nan") if kind == "average" else date],
            "numeric_value": [value],
        })
        concept = ("ifrs-full:AverageForeignExchangeRate" if kind == "average"
                   else "ifrs-full:ClosingForeignExchangeRate")

        class _Q(_Query):
            def to_dataframe(self):
                return frame if self._concept == concept else pd.DataFrame()

        facts = _Facts(frame)
        facts.query = lambda: _Q(frame)
        facts.to_dataframe = lambda: pd.DataFrame({"unit_ref": ["home"]})
        self.facts = facts


@pytest.mark.parametrize("filer, home, num, den, value, year, kind, reading", [
    # Ecopetrol 20-F, closing 2024-12-31: unit USD/COP, value 4,409.15 COP per USD
    ("Ecopetrol", "COP", "USD", "COP", 4409.15, 2024, "closing", "COP per USD"),
    # Andina 20-F, closing 2025-12-31: unit USD/CLP, value 907.13 CLP per USD
    ("Andina", "CLP", "USD", "CLP", 907.13, 2025, "closing", "CLP per USD"),
    # Genmab 20-F, average 2024: unit DKK/USD, value 0.1452 USD per DKK
    ("Genmab", "DKK", "DKK", "USD", 0.1452, 2024, "average", "USD per DKK"),
])
def test_a_backwards_unit_is_overruled_by_the_only_plausible_reading(
        filer, home, num, den, value, year, kind, reading):
    converter = CurrencyConverter(_OneRateXBRL(home, num, den, value, year, kind))
    expected_usd = value if reading.startswith("USD") else 1 / value
    assert converter.to_usd(1, year, rate_type=kind) == pytest.approx(expected_usd)
    assert converter.rate_basis[(year, kind)] == (
        f"{reading} (only plausible reading; its unit says the opposite)")
    assert (f"the {kind} rate for {year} ({value}) is plausible only as {reading}, "
            f"which its unit contradicts; it was read as {reading}"
            ) in converter.extraction_warnings


# ---------------------------------------------------------------------------
# Review round 2: the other currencies' rates outrank the unit, and rates in
# divide units count among them. By construction: EUR home, 2024 averages.
# ---------------------------------------------------------------------------

class _Context:
    def __init__(self, dimensions):
        self.dimensions = dimensions


class _TableXBRL:
    """An EUR filing's 2024 average-rate table, one row per (unit, member, value)."""

    def __init__(self, units, rows):
        self.units = {"home": {"type": "simple", "measure": "iso4217:EUR"},
                      "number": {"type": "simple", "measure": "xbrli:pure"}, **units}
        self.contexts = {f"c-{i}": _Context({"srt:CurrencyAxis": member} if member else {})
                         for i, (_, member, _) in enumerate(rows)}
        frame = pd.DataFrame({
            "unit_ref": [unit for unit, _, _ in rows],
            "context_ref": [f"c-{i}" for i in range(len(rows))],
            "period_start": ["2024-01-01"] * len(rows),
            "period_end": ["2024-12-31"] * len(rows),
            "numeric_value": [value for _, _, value in rows],
        })
        facts = _Facts(frame)
        facts.to_dataframe = lambda: pd.DataFrame({"unit_ref": ["home"]})
        self.facts = facts


def test_other_currencies_outrank_a_backwards_unit():
    # 1.0824 USD per EUR, tagged EUR/USD; the yen row (163.8 JPY per EUR) shows
    # the table quotes foreign currency per euro. The unit used to decide first
    # and gave EUR 100 = USD 92.39, with no warning.
    converter = CurrencyConverter(_TableXBRL(
        {"eur_usd": _divide("iso4217:EUR", "iso4217:USD")},
        [("eur_usd", "currency:USD", 1.0824), ("number", "currency:JPY", 163.8)],
    ))
    assert converter.to_usd(100, 2024) == pytest.approx(108.24)
    assert converter.rate_basis[(2024, "average")] == (
        "USD per EUR (plausible either way, settled by the other currencies' rates "
        "in the filing; its unit says the opposite)")
    assert ("the average rate for 2024 (1.0824) is plausible as USD per EUR or EUR "
            "per USD; the other currencies' rates in the filing say USD per EUR, "
            "which its unit contradicts") in converter.extraction_warnings


@pytest.mark.parametrize("member", [None, "currency:JPY"])
def test_a_divide_unit_sibling_settles_a_near_parity_rate(member):
    # The yen rate in a JPY/EUR unit, with or without its currency member, now
    # counts; it used to be dropped, leaving 1.0824 ambiguous and unused.
    converter = CurrencyConverter(_TableXBRL(
        {"jpy_eur": _divide("iso4217:JPY", "iso4217:EUR")},
        [("number", "currency:USD", 1.0824), ("jpy_eur", member, 163.8)],
    ))
    assert converter.to_usd(100, 2024) == pytest.approx(108.24)
