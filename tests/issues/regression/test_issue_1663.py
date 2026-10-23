"""Regression: ``get_net_income()`` returned income from continuing operations as
net income when its concept lookup missed.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1663

The label fallback's r'^Net Income(?!.*noncontrolling)' and r'^Net Loss...'
have no end anchor and no continuing-operations exclusion, so a row labeled
"Net income (loss) from continuing operations" above the bottom line was
returned in its place. Continuing operations and net income differ by
discontinued operations, net of tax (ASC 205-20-45-3A).
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.financials import Financials

IBM = Path("tests/fixtures/xbrl/ibm/10k_2024")
CONT = "us-gaap_IncomeLossFromContinuingOperations"
DISC = "us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax"
EXT = "abc_NetIncomeLossAttributableToCommonStockholders"


def _net_income(rows):
    df = pd.DataFrame([{"concept": c, "label": lbl, "abstract": False, "2024-12-31": v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials.get_net_income()


@pytest.mark.fast
@pytest.mark.parametrize("continuing_label, bottom_label, continuing, bottom", [
    ("Net income (loss) from continuing operations", "Net income (loss)", 600, 450),
    ("Net loss from continuing operations", "Net loss attributable to common stockholders", -600, -750),
    ("Income (loss) from continuing operations", "Net income (loss)", 600, 450),
])
def test_the_bottom_line_not_the_continuing_operations_row(continuing_label, bottom_label, continuing, bottom):
    assert _net_income([
        (CONT, continuing_label, continuing),
        (DISC, "Loss from discontinued operations, net of tax", -150),
        (EXT, bottom_label, bottom),
    ]) == bottom


@pytest.mark.fast
@pytest.mark.parametrize("nci_label", [
    "Net income attributable to noncontrolling interests",
    "Net income attributable to non-controlling interests",
    "Net income attributable to minority interest",
    "Net income attributable to Non-Controlling Interests",
])
def test_every_spelling_of_the_nci_row_is_excluded(nci_label):
    assert _net_income([
        ("abc_NciShare", nci_label, 25),
        (EXT, "Net income attributable to ABC", 450),
    ]) == 450


@pytest.mark.fast
def test_no_net_income_row_gives_none_not_a_continuing_row():
    assert _net_income([
        (CONT, "Net income from continuing operations", 600),
        (DISC, "Net loss from discontinued operations", -150),
    ]) is None


@pytest.mark.fast
def test_ibm_with_its_bottom_line_on_an_unmapped_concept():
    """IBM 10-K FY2024, 0000051143-25-000015 (fixture): Income from continuing
    operations 6,015 $M, discontinued operations 8, Net income 6,023. With the
    continuing row relabeled "Net income from continuing operations" and the
    bottom line moved off us-gaap:NetIncomeLoss (the issue's edited copy), the
    concept pass misses and the fallback must still find 6,023."""
    from edgar.xbrl import XBRL

    ibm = Financials(XBRL.from_directory(IBM))
    assert ibm.get_net_income() == 6023000000

    render = ibm._render_statement_frame

    def edited(statement_type):
        rendered, df = render(statement_type)
        if statement_type == 'income':
            df = df.copy()
            df.loc[df['concept'] == CONT, 'label'] = 'Net income from continuing operations'
            bottom = df['concept'] == 'us-gaap_NetIncomeLoss'
            df.loc[bottom, 'concept'] = 'us-gaap_NetIncomeLossAvailableToCommonStockholdersBasic'
            df.loc[bottom, 'label'] = 'Net income attributable to IBM common stockholders'
        return rendered, df

    ibm._render_statement_frame = edited
    assert ibm.get_net_income() == 6023000000
