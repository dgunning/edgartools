"""Regression: context decides between mappings that are right for some filings only.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1452

Core scope, by maintainer decision (bead edgartools-k7mi8.35). The proposed
resolve()/ResolutionResult API was not adopted.

1. ``Financials.get_operating_cash_flow()`` searched the 'Net Cash from
   Operating Activities' mapping, which also carries
   ``NetCashProvidedByUsedInOperatingActivitiesContinuingOperations``. A filer
   reporting only that element and discontinued operating cash got the
   continuing figure as its total. On SEC's CY2025 frames 95 filers report the
   continuing element without a total and 88 of them also report
   ``CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations``. A total
   still wins; the continuing figure answers only when the statement has no
   nonzero discontinued operating cash for the same period column; otherwise
   None. Real filings (fixtures under tests/fixtures/xbrl/, values read from
   the filings and from SEC's CY2025 frames):

   - SIFCO Industries (CIK 90168), 10-K FY ended 2025-09-30, accession
     0001628280-25-058405: continuing $127,000, discontinued $5,000, no total.
     Was 127000 on main; now None.
   - Exceed World (CIK 1634293), 10-K FY ended 2025-09-30, accession
     0001634293-26-000002: continuing -$8,147,821 (2024: $2,724,235), no
     total, no discontinued. Returns the continuing figure.
   - Waste Energy Corp. (CIK 1515139), 10-K FY 2025, accession
     0001493152-26-033196: continuing -$390,107 (2024: -$402,563), discontinued
     only for 2024 (-$1,554,250). Returns -390107 for 2025 and None for 2024
     (main returned -402563).

2. ``get_standard_concept()`` ignored context for three tags. They are now
   candidate lists in gaap_mappings.json, decided by the section or, for a tag
   used on two statements, by the statement type.
"""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from edgar.exceptions import ValidationError
from edgar.financials import Financials
from edgar.xbrl import XBRL
from edgar.xbrl.standardization.reverse_index import get_reverse_index

FIXTURES = Path("tests/fixtures/xbrl")


@pytest.fixture(scope="module")
def sifco():
    return Financials(XBRL.from_directory(FIXTURES / "sif" / "10k_2025"))


@pytest.fixture(scope="module")
def exceed_world():
    return Financials(XBRL.from_directory(FIXTURES / "exdw" / "10k_2025"))


@pytest.fixture(scope="module")
def waste_energy():
    return Financials(XBRL.from_directory(FIXTURES / "wast" / "10k_2025"))


# --- Part 1: operating cash, real filings -----------------------------------

def test_continuing_with_discontinued_is_not_the_total(sifco):
    # Main returned 127000, the continuing-operations figure.
    assert sifco.get_operating_cash_flow() is None
    assert sifco.get_operating_cash_flow(1) is None


def test_continuing_without_discontinued_is_the_total(exceed_world):
    assert exceed_world.get_operating_cash_flow() == -8147821
    assert exceed_world.get_operating_cash_flow(1) == 2724235


def test_discontinued_is_read_for_the_same_period(waste_energy):
    # Discontinued operating cash only in the 2024 column.
    assert waste_energy.get_operating_cash_flow() == -390107
    assert waste_energy.get_operating_cash_flow(1) is None


# --- Part 1: the rule on synthetic statements --------------------------------

TOTAL = "us-gaap_NetCashProvidedByUsedInOperatingActivities"
CONT = "us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"
DISC = "us-gaap_CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations"


def _financials(rows):
    """Financials over a cash flow frame of (concept, label, current, prior) rows."""
    df = pd.DataFrame(rows, columns=["concept", "label", "2025-12-31", "2024-12-31"])
    df["abstract"] = False
    rendered = SimpleNamespace(periods=[])
    financials = Financials(xb=object())
    financials._render_statement_frame = lambda statement_type, *a, **k: (
        (rendered, df.copy()) if statement_type == "cashflow" else (None, None))
    return financials


def test_a_reported_total_wins():
    fin = _financials([
        (CONT, "Continuing", 90, 80),
        (DISC, "Discontinued", 10, 5),
        (TOTAL, "Net Cash from Operating Activities", 100, 85),
    ])
    assert fin.get_operating_cash_flow() == 100
    assert fin.get_operating_cash_flow(1) == 85


def test_continuing_plus_discontinued_gives_none():
    fin = _financials([
        (CONT, "Net Cash from Operating Activities", 90, 80),
        (DISC, "Net cash used in operating activities of discontinued operations", 10, 5),
    ])
    assert fin.get_operating_cash_flow() is None


def test_continuing_alone_gives_continuing():
    fin = _financials([(CONT, "Net Cash from Operating Activities", 90, 80)])
    assert fin.get_operating_cash_flow() == 90


def test_zero_or_empty_discontinued_is_nothing_discontinued():
    fin = _financials([
        (CONT, "Net Cash from Operating Activities", 90, 80),
        (DISC, "Net cash from discontinued operations", 0, None),
    ])
    assert fin.get_operating_cash_flow() == 90
    assert fin.get_operating_cash_flow(1) == 80


def test_extension_discontinued_element_counts():
    fin = _financials([
        (CONT, "Net Cash from Operating Activities", 90, 80),
        ("abc_NetCashUsedInOperatingActivitiesOfDiscontinuedOperations", "Discontinued", -4, None),
    ])
    assert fin.get_operating_cash_flow() is None
    assert fin.get_operating_cash_flow(1) == 80


def test_label_fallback_does_not_revive_a_part():
    # An extension continuing element with a total-like label, and an
    # extension discontinued row the last label pattern would match.
    fin = _financials([
        ("abc_OperatingCashContinuing", "Net cash provided by operating activities - continuing operations", 90, 80),
        ("abc_OperatingCashDiscontinued", "Net cash used in operating activities of discontinued operations", 10, 5),
    ])
    assert fin.get_operating_cash_flow() is None
    fin = _financials([
        ("abc_NetCashFromOperations", "Net cash provided by operating activities", 100, 85),
        ("abc_OperatingCashDiscontinued", "Net cash used in operating activities of discontinued operations", 10, 5),
    ])
    assert fin.get_operating_cash_flow() == 100


# --- Part 2: context in get_standard_concept() -------------------------------

@pytest.fixture(scope="module")
def ri():
    return get_reverse_index()


@pytest.mark.parametrize("tag, context, expected", [
    ("DividendsReceivable", {"statement_type": "BalanceSheet", "section": "Current Assets"},
     "OtherNonOperatingCurrentAssets"),
    ("DividendsReceivable", {"statement_type": "BalanceSheet", "section": "Non-Current Assets"},
     "OtherNonOperatingNonCurrentAssets"),
    ("us-gaap:DividendsPreferredStock", {"statement_type": "StatementOfEquity"}, "DividendsEquity"),
    ("us-gaap:DividendsPreferredStock", {"statement_type": "IncomeStatement"}, "PreferredDividendExpense"),
    ("us-gaap_ImpairmentOfInvestments", {"statement_type": "CashFlowStatement"}, "ImpairmentChargesCF"),
    ("us-gaap_ImpairmentOfInvestments", {"statement_type": "IncomeStatement"}, "AssetImpairmentChargesIS"),
    # A section on the statement that names no candidate still lets the statement decide.
    ("ImpairmentOfInvestments", {"statement_type": "IncomeStatement", "section": "Non-Operating Items"},
     "AssetImpairmentChargesIS"),
])
def test_context_decides(ri, tag, context, expected):
    assert ri.get_standard_concept(tag, context=context) == expected


@pytest.mark.parametrize("tag, expected", [
    # Dividends declared are normally collected within the operating cycle
    # (ASC 210-10-45-1, 45-3), so the default moved to the current side.
    ("DividendsReceivable", "OtherNonOperatingCurrentAssets"),
    ("DividendsPreferredStock", "PreferredDividendExpense"),
    ("ImpairmentOfInvestments", "ImpairmentChargesCF"),
])
def test_defaults_without_context(ri, tag, expected):
    assert ri.get_standard_concept(tag) == expected


def test_section_control_is_unchanged(ri):
    tag = "AccountsPayableCurrentAndNoncurrent"
    assert ri.get_standard_concept(tag) == "TradePayables"
    assert ri.get_standard_concept(tag, context={"section": "Current Liabilities"}) == "TradePayables"
    assert ri.get_standard_concept(
        tag, context={"statement_type": "BalanceSheet", "section": "Non-Current Liabilities"}
    ) == "OtherOperatingNonCurrentLiabilities"


def test_single_candidate_entries_ignore_context(ri):
    assert ri.get_standard_concept(
        "AssetImpairmentCharges", context={"statement_type": "CashFlowStatement"}) == "AssetImpairmentChargesIS"


def test_invalid_input_raises_a_useful_error(ri):
    with pytest.raises(ValidationError, match="xbrl_tag must be an XBRL concept name"):
        ri.get_standard_concept(None)
    with pytest.raises(ValidationError, match="context must be a dict"):
        ri.get_standard_concept("DividendsReceivable", context="Current Assets")
