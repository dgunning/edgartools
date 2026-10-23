"""Regression: ``get_net_income()`` returned ProfitLoss, which includes the
noncontrolling interest's share, when the statement has no NetIncomeLoss row.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1688

The getter asks for us-gaap NetIncomeLoss (parent net income) first, then fell
back to the 'Profit or Loss' mapping and returned it unchanged. Caterpillar's
FY2025 10-K files ProfitLoss $8,882M and NCI $(2)M, so it got $8,882M for a
parent amount of $8,884M; Interactive Brokers' Q2 2026 10-Q got $1,338M for
$312M. For IFRS, the sorted mapping put ifrs-full_ProfitLoss ahead of
ProfitLossAttributableToOwnersOfParent (Toyota).

Parent net income is now ProfitLoss less the noncontrolling-interest rows,
which is NetIncomeLoss by definition; preferred dividends are not deducted.
"""
import pandas as pd
import pytest

from edgar.financials import Financials


def _stub(rows):
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2025-12-31': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
def test_profit_loss_less_the_noncontrolling_interest():
    """Caterpillar's shape: NCI is a loss, so the parent amount is larger."""
    financials = _stub([
        ('us-gaap_ProfitLoss', 'Profit of consolidated and affiliated companies', 8882000000),
        ('us-gaap_NetIncomeLossAttributableToNoncontrollingInterest', 'Less: NCI', -2000000),
        ('us-gaap_NetIncomeLossAvailableToCommonStockholdersBasic', 'Profit (loss)', 8884000000),
    ])
    assert financials.get_net_income() == 8884000000


@pytest.mark.fast
def test_redeemable_and_nonredeemable_rows_are_both_deducted_but_not_preferred_dividends():
    """Sempra's shape, 10-Q Q2 2026 0001032208-26-000045: 942 - 141 - 4 = 797 $M;
    the 1 of subsidiary preferred dividends stays in parent net income."""
    financials = _stub([
        ('us-gaap_ProfitLoss', 'Net income', 942000000),
        ('us-gaap_NetIncomeLossAttributableToNonredeemableNoncontrollingInterest', 'NCI', 141000000),
        ('us-gaap_NetIncomeLossAttributableToRedeemableNoncontrollingInterest', 'Redeemable NCI', 4000000),
        ('us-gaap_OtherPreferredStockDividendsAndAdjustments', 'Preferred dividends of subsidiary', 1000000),
        ('us-gaap_NetIncomeLossAvailableToCommonStockholdersBasic', 'Earnings attributable to common', 796000000),
    ])
    assert financials.get_net_income() == 797000000


@pytest.mark.fast
def test_reit_operating_partnership_rows_are_deducted():
    """A REIT's redeemable NCI split by holder (concept_linkages.json), no total row."""
    financials = _stub([
        ('us-gaap_ProfitLoss', 'Net income', 1000),
        ('us-gaap_NoncontrollingInterestInNetIncomeLossOperatingPartnershipsRedeemable',
         'Noncontrolling interests in the Operating Partnership', 50),
        ('us-gaap_NoncontrollingInterestInNetIncomeLossOtherNoncontrollingInterestsRedeemable',
         'Noncontrolling interests in other partnerships', 10),
        ('us-gaap_NoncontrollingInterestInNetIncomeLossPreferredUnitHoldersRedeemable',
         'Preferred unit holders', 5),
    ])
    assert financials.get_net_income() == 1000 - 50 - 10 - 5


@pytest.mark.fast
def test_redeemable_total_is_not_summed_with_its_holder_split():
    financials = _stub([
        ('us-gaap_ProfitLoss', 'Net income', 1000),
        ('us-gaap_NetIncomeLossAttributableToNonredeemableNoncontrollingInterest', 'NCI', 20),
        ('us-gaap_NetIncomeLossAttributableToRedeemableNoncontrollingInterest', 'Redeemable NCI', 60),
        ('us-gaap_NoncontrollingInterestInNetIncomeLossOperatingPartnershipsRedeemable', 'OP units', 50),
        ('us-gaap_NoncontrollingInterestInNetIncomeLossOtherNoncontrollingInterestsRedeemable', 'Other', 10),
    ])
    assert financials.get_net_income() == 1000 - 20 - 60


@pytest.mark.fast
def test_continuing_operations_nci_is_deducted():
    financials = _stub([
        ('us-gaap_ProfitLoss', 'Net income', 1000),
        ('us-gaap_IncomeLossFromContinuingOperationsAttributableToNoncontrollingEntity',
         'Income from continuing operations attributable to NCI', 30),
    ])
    assert financials.get_net_income() == 970


@pytest.mark.fast
def test_two_partitions_of_the_nci_share_are_not_both_deducted():
    """A redeemability split and an operations split each sum to the whole NCI share."""
    financials = _stub([
        ('us-gaap_ProfitLoss', 'Net income', 1000),
        ('us-gaap_NetIncomeLossAttributableToNonredeemableNoncontrollingInterest', 'NCI', 20),
        ('us-gaap_NetIncomeLossAttributableToRedeemableNoncontrollingInterest', 'Redeemable NCI', 10),
        ('us-gaap_IncomeLossFromContinuingOperationsAttributableToNoncontrollingEntity', 'NCI, continuing', 30),
    ])
    assert financials.get_net_income() == 970


@pytest.mark.fast
def test_ifrs_owners_of_parent_comes_before_consolidated_profit():
    """Toyota 20-F FY2026 shape (0001193125-26-264811, yen millions)."""
    financials = _stub([
        ('ifrs-full_ProfitLoss', 'Net income', 3985761000000),
        ('ifrs-full_ProfitLossAttributableToOwnersOfParent', 'Toyota Motor Corporation', 3848098000000),
        ('ifrs-full_ProfitLossAttributableToNoncontrollingInterests', 'Non-controlling interests', 137664000000),
    ])
    assert financials.get_net_income() == 3848098000000

    without_parent_row = _stub([
        ('ifrs-full_ProfitLoss', 'Net income', 3985761000000),
        ('ifrs-full_ProfitLossAttributableToNoncontrollingInterests', 'Non-controlling interests', 137664000000),
    ])
    # The filed parent line is 3,848,098; the components differ from it by rounding.
    assert without_parent_row.get_net_income() == 3985761000000 - 137664000000


@pytest.mark.fast
def test_net_income_loss_and_profit_without_nci_are_unchanged():
    with_parent_line = _stub([
        ('us-gaap_ProfitLoss', 'Net income', 942),
        ('us-gaap_NetIncomeLossAttributableToNoncontrollingInterest', 'NCI', 141),
        ('us-gaap_NetIncomeLoss', 'Net income attributable to the company', 801),
    ])
    assert with_parent_line.get_net_income() == 801

    no_nci = _stub([('us-gaap_ProfitLoss', 'Net income', 3486000)])
    assert no_nci.get_net_income() == 3486000


def _xbrl_only(**filing):
    """The filing's XBRL, read from the documents its index page lists
    (FilingSGML.from_homepage), so the cassette holds only the files parsed."""
    from edgar import Filing
    from edgar.sgml.sgml_common import FilingSGML

    filing = Filing(**filing)
    filing._sgml = FilingSGML.from_homepage(filing.homepage)
    return filing.xbrl()


@pytest.mark.network
@pytest.mark.vcr
def test_caterpillar_reports_profit_attributable_to_its_shareholders():
    """Caterpillar 10-K FY2025, 0000018230-26-000008 ($M): Profit of consolidated and
    affiliated companies 8,882; NCI (2); Profit 8,884. FY2024: 10,788; (4); 10,792."""
    cat = Financials(_xbrl_only(form='10-K', filing_date='2026-02-13', company='CATERPILLAR INC',
                                cik=18230, accession_no='0000018230-26-000008'))
    assert cat.get_net_income() == 8884000000
    assert cat.get_net_income(1) == 10792000000
