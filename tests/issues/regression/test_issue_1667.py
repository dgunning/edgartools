"""Regression: ``get_total_assets()`` returned the current-assets subtotal.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1667

The getter matched balance-sheet labels only. When the us-gaap:Assets row is
labeled "Assets" (NovaGold) or "Total consolidated assets" (Coeur Mining),
neither "Total Assets" pattern matched, and the third pattern, r'Assets$', took
the first row ending in "assets": "Total current assets". NovaGold's 10-Q for
2026-08-31 returned 349,770,000 (us-gaap:AssetsCurrent) against a filed total
of 573,286,000, and ``debt_to_assets`` came back 0.532 instead of 0.324.

The getter now looks up the concept first, as ``get_total_liabilities()`` does
(GH #1279), and its label fallback is anchored at both ends.
"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from edgar.financials import Financials


def _stub(rows):
    """A Financials whose balance sheet is ``rows`` of (concept, label, value)."""
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2026-08-31': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
@pytest.mark.parametrize("total_label", ["Assets", "Total consolidated assets"])
def test_total_assets_is_the_assets_concept_not_the_current_subtotal(total_label):
    financials = _stub([
        ('us-gaap_AssetsCurrent', 'Total current assets', 349770000),
        ('us-gaap_OtherAssetsNoncurrent', 'Other assets', 663000),
        ('us-gaap_Assets', total_label, 573286000),
    ])
    assert financials.get_total_assets() == 573286000


@pytest.mark.fast
def test_label_fallback_does_not_match_a_subtotal():
    """An unmapped total still resolves by label; a subtotal never does."""
    subtotal_only = _stub([
        ('us-gaap_AssetsCurrent', 'Total current assets', 349770000),
        ('custom_OtherAssetsTotal', 'Total other assets', 663000),
    ])
    assert subtotal_only.get_total_assets() is None

    unmapped_total = _stub([
        ('us-gaap_AssetsCurrent', 'Total current assets', 349770000),
        ('custom_AssetsGrandTotal', 'Total assets', 573286000),
    ])
    assert unmapped_total.get_total_assets() == 573286000


@pytest.mark.fast
def test_aal_total_assets_is_the_filed_assets_fact():
    """A different industry: American Airlines 10-K FY2025, 0000006201-26-000014."""
    from edgar.xbrl import XBRL

    financials = Financials(XBRL.from_directory(Path("tests/fixtures/xbrl/aal/10k_2025")))
    filed = {Decimal(f["value"]) for f in financials.xb.facts.query()
             .by_concept("us-gaap:Assets", exact=True)
             .by_period_key("instant_2025-12-31")
             .by_custom(lambda f: not f["is_dimensioned"]).execute()}
    assert filed == {Decimal("61774000000")}
    assert financials.get_total_assets() == 61774000000


@pytest.mark.network
@pytest.mark.vcr
def test_novagold_reports_its_balance_sheet_total():
    """NovaGold 10-Q 2026-08-31, 0001171843-26-006530 (thousands): the uncaptioned
    total row is 573,286 (prior 2025-11-30: 335,913); current assets 349,770."""
    from edgar import Filing

    novagold = Financials(Filing(form='10-Q', filing_date='2026-10-08', company='NOVAGOLD RESOURCES INC',
                                 cik=1173420, accession_no='0001171843-26-006530').xbrl())
    assert novagold.get_total_assets() == 573286000
    assert novagold.get_total_assets(1) == 335913000
    assert novagold.get_current_assets() == 349770000


@pytest.mark.network
@pytest.mark.vcr
def test_coeur_reports_its_balance_sheet_total():
    """Coeur Mining 10-K 2025-12-31, 0000215466-26-000004 (thousands): TOTAL ASSETS
    4,695,682 (prior 2,301,747); current assets 972,677."""
    from edgar import Filing

    coeur = Financials(Filing(form='10-K', filing_date='2026-02-18', company='Coeur Mining, Inc.',
                              cik=215466, accession_no='0000215466-26-000004').xbrl())
    assert coeur.get_total_assets() == 4695682000
    assert coeur.get_total_assets(1) == 2301747000
    assert coeur.get_current_assets() == 972677000
