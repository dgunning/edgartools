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
