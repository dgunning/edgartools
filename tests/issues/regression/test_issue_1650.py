"""
Regression test for GitHub Issue #1650: ``CurrencyConverter`` ignored the
currency and hedge axes, so GSK's average rate came from EUR hedge and JPY rows.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1650

``ifrs-full:AverageForeignExchangeRate`` carries one fact per currency
(``srt:CurrencyAxis``) and, in GSK's financial-instruments note, the contracted
rates of its hedging instruments. The converter read every fact without looking
at its dimensions and kept the last one per year: 1.19 (a EUR cross-currency
swap) for 2025, 1.17 (a EUR forward) for 2024 and 175.0 (the yen rate) for 2023.
It now keeps only facts for the target currency that are not on a hedge axis,
prefers the one with no other dimension, and reports a year whose remaining facts
disagree instead of picking one.

Ground truth: GSK plc FY2025 20-F, accession 0001131399-26-000004, note 5
"Exchange rates": average rates US$/£ 1.31 / 1.28 / 1.24 and period-end rates
US$/£ 1.35 / 1.25 / 1.27 for 2025 / 2024 / 2023. They are the facts whose only
dimension is ``srt:CurrencyAxis=currency:USD``.
"""

import pandas as pd
import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.currency import CurrencyConverter

pytestmark = [pytest.mark.regression]

# The instance document alone carries the facts, contexts and units the
# converter reads, so the cassette holds one 15.9 MB response.
GSK_FOLDER = "https://www.sec.gov/Archives/edgar/data/1131399/000113139926000004/"
GSK_INSTANCE = "gsk-20251231_htm.xml"
GSK_CASSETTE = "currency_gsk_20f_0001131399-26-000004.yaml"


@pytest.fixture(scope="module")
def gsk_xbrl(vcr, tmp_path_factory):
    folder = tmp_path_factory.mktemp("gsk")
    with vcr.use_cassette(GSK_CASSETTE):
        text = download_file(GSK_FOLDER + GSK_INSTANCE)
    (folder / GSK_INSTANCE).write_text(text, encoding="utf-8")
    return XBRL.from_directory(folder)


def _selection_warnings(converter):
    return [w for w in converter.extraction_warnings
            if "none was used" in w or "hedging" in w]


def test_gsk_rates_come_from_the_usd_translation_rows(gsk_xbrl):
    converter = CurrencyConverter(gsk_xbrl)

    assert converter.home_currency == "GBP"
    # Note 5, average rates US$/£ (was 1.19 / 1.17 / 175.0)
    assert converter.get_rate(2025, "average") == 1.31
    assert converter.get_rate(2024, "average") == 1.28
    assert converter.get_rate(2023, "average") == 1.24
    # Note 5, period-end rates US$/£ (not the yen rows 211 / 197 / 180)
    assert converter.get_rate(2025, "closing") == 1.35
    assert converter.get_rate(2024, "closing") == 1.25
    assert converter.get_rate(2023, "closing") == 1.27
    assert _selection_warnings(converter) == []


# ---------------------------------------------------------------------------
# Offline: the selection rules, on hand-built facts
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

    def __init__(self, rows):
        # rows: (dimensions, value), all average rates for 2025
        self.contexts = {f"c-{i}": _Context(dims) for i, (dims, _) in enumerate(rows)}
        frame = pd.DataFrame({
            "unit_ref": ["number"] * len(rows),
            "context_ref": [f"c-{i}" for i in range(len(rows))],
            "period_end": ["2025-12-31"] * len(rows),
            "period_instant": [float("nan")] * len(rows),
            "numeric_value": [value for _, value in rows],
        })
        self.facts = _Facts({"ifrs-full:AverageForeignExchangeRate": frame})


USD = {"srt:CurrencyAxis": "currency:USD"}
EUR = {"srt:CurrencyAxis": "currency:EUR"}
JPY = {"srt:CurrencyAxis": "currency:JPY"}
USD_HEDGE = {"srt:CurrencyAxis": "currency:USD",
             "ifrs-full:TypesOfHedgesAxis": "gsk:NetInvestmentHedgesMember",
             "ifrs-full:HedgingInstrumentsAxis": "gsk:ForeignExchangeContractsMember"}
EUR_HEDGE = {"srt:CurrencyAxis": "currency:EUR",
             "ifrs-full:TypesOfHedgesAxis": "gsk:NetInvestmentHedgesMember"}


def test_other_currencies_and_hedge_rows_are_not_used():
    # GSK's 2025 shape, with the selected row first so "last row wins" fails.
    converter = CurrencyConverter(_StubXBRL([
        (USD, 1.31), (EUR, 1.17), (JPY, 198.0), (USD_HEDGE, 1.33), (EUR_HEDGE, 1.19),
    ]))
    assert converter.get_rate(2025, "average") == 1.31
    assert _selection_warnings(converter) == []


def test_the_fact_with_fewest_other_dimensions_wins():
    risk = {"srt:CurrencyAxis": "currency:USD",
            "ifrs-full:TypesOfRisksAxis": "ifrs-full:CurrencyRiskMember"}
    converter = CurrencyConverter(_StubXBRL([(risk, 1.30), (USD, 1.31)]))
    assert converter.get_rate(2025, "average") == 1.31


def test_disagreeing_rates_are_reported_not_guessed():
    converter = CurrencyConverter(_StubXBRL([(USD, 1.31), (USD, 1.29)]))
    assert converter.get_rate(2025, "average") is None
    assert "2 different average USD rates for 2025 (1.29, 1.31); none was used" \
        in converter.extraction_warnings


def test_a_year_with_only_hedge_rates_says_so():
    converter = CurrencyConverter(_StubXBRL([(USD_HEDGE, 1.33), (EUR, 1.17)]))
    assert converter.get_rate(2025, "average") is None
    assert ("the only average USD rates for 2025 are 1 hedging-instrument rate(s), "
            "which were not used") in converter.extraction_warnings


def test_rates_set_aside_do_not_read_as_an_extraction_failure():
    converter = CurrencyConverter(_StubXBRL([(USD_HEDGE, 1.33)]))
    text = repr(converter)
    assert "no usable rates: the only average USD rates for 2025" in text
    assert "rate extraction failed" not in text
    assert "Rate extraction failed" not in converter.__rich__().caption
