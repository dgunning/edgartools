"""Regression: ``get_operating_income()`` returned pretax income from continuing
operations when the filer reports no operating income.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1664

When the concept pass missed, the label fallback r'Income.*Operations' took the
first row whose label contained both words: "Income from continuing operations
before income taxes". IBM's FY2024 10-K, which presents no operating subtotal
and files no us-gaap:OperatingIncomeLoss, returned $5.797B. The unanchored
r'Operating Income$' also matched banks' "Other operating income" and
"Non-operating income". The fallback is now anchored at both ends.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.financials import Financials

IBM = Path("tests/fixtures/xbrl/ibm/10k_2024")


def _stub(rows):
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2024-12-31': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
@pytest.mark.parametrize("label", [
    "Income from continuing operations before income taxes",
    "Income (loss) from continuing operations, before income taxes",
    "Income from continuing operations",
    "Other operating income",
    "Non-operating income",
    "(Loss) income from continuing operations before income taxes",
    "Operating income before income taxes",
    "Income from operations before income taxes",
])
def test_rows_that_are_not_an_operating_subtotal_are_not_operating_income(label):
    financials = _stub([('custom_Line', label, 5797000000)])
    assert financials.get_operating_income() is None


@pytest.mark.fast
@pytest.mark.parametrize("label", [
    "Operating income", "Operating income (loss)", "Operating loss",
    "Income from operations", "Income (loss) from operations", "Loss from operations",
    # Sign orderings and suffixes filers put on extension concepts (review of #1664)
    "(Loss) income from operations", "Operating income/(loss)", "Income from operations, net",
    "Operating (loss) income", "Operating income (loss), net", "Income/(loss) from operations",
])
def test_an_unmapped_operating_subtotal_still_resolves_by_label(label):
    financials = _stub([
        ('us-gaap_OtherNonoperatingIncomeExpense', 'Other operating income', 7),
        ('custom_OperatingSubtotal', label, 1234),
    ])
    assert financials.get_operating_income() == 1234


@pytest.mark.fast
def test_ibm_reports_no_operating_income():
    """IBM 10-K FY2024, 0000051143-25-000015 (fixture): no us-gaap:OperatingIncomeLoss
    fact; "Income from continuing operations before income taxes" is 5,797 $M."""
    from edgar.xbrl import XBRL

    ibm = Financials(XBRL.from_directory(IBM))
    assert ibm.xb.facts.query().by_concept('us-gaap:OperatingIncomeLoss', exact=True).to_dataframe().empty
    pretax = ibm.xb.facts.query().by_concept(
        'us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        exact=True).to_dataframe()
    assert 5797000000 in set(pretax['numeric_value'])

    assert ibm.get_operating_income() is None
    assert ibm.get_operating_income(1) is None
