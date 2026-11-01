"""
Forty-four ``IncomeTaxReconciliation*`` elements, the statutory-rate starting amount and the
reconciling items of the income-tax rate reconciliation, were standardized as ``IncomeTaxes``
("Income Tax Expense"), the concept of the reported provision. A reconciliation table then had
up to a dozen "Income Tax Expense" rows, and the hypothetical tax at the statutory rate passed
for the provision. No standard concept fits these amounts, so the 44 entries are removed, with
the four ``EffectiveIncomeTaxRateReconciliation*Amount`` reconciling items that carried the same
mapping (#1440 removed their share-based-compensation sibling). The provision
(``IncomeTaxExpenseBenefit``) keeps ``IncomeTaxes``.

Ground truth: Apple FY2023 10-K, accession 0000320193-23-000106 (tracked fixture), income-tax
rate reconciliation for fiscal 2023: computed expected tax $23,885M, state taxes $1,124M,
earnings of foreign subsidiaries $(5,744)M, research and development credit $1,212M (presented
as a reduction), foreign-derived intangible income deduction $0 (2022: $296M, a reduction),
other $(192)M, provision for income taxes $16,741M. Those six rows were
``IncomeTaxes`` beside the provision; only the $16,741M provision is now. The issue reports the same
shape on Oracle's FY2026 10-K (0001193125-26-277521).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1857
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import ReverseIndex

FIXTURE = Path(__file__).parents[2] / "fixtures" / "xbrl" / "aapl" / "10k_2023"
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# The 44 keys that mapped to IncomeTaxes on main 8e601ec6.
REMOVED = [
    "IncomeTaxReconciliationChangeInDeferredTaxAssetsValuationAllowance",
    "IncomeTaxReconciliationChangeInEnactedTaxRate",
    "IncomeTaxReconciliationDeductions",
    "IncomeTaxReconciliationDeductionsDividends",
    "IncomeTaxReconciliationDeductionsExtraterritorialIncomeExclusion",
    "IncomeTaxReconciliationDeductionsOther",
    "IncomeTaxReconciliationDeductionsQualifiedProductionActivities",
    "IncomeTaxReconciliationDispositionOfAssets",
    "IncomeTaxReconciliationDispositionOfBusiness",
    "IncomeTaxReconciliationEquityInEarningsLossesOfUnconsolidatedSubsidiary",
    "IncomeTaxReconciliationForeignIncomeTaxRateDifferential",
    "IncomeTaxReconciliationIncomeTaxExpenseBenefitAtFederalStatutoryIncomeTaxRate",
    "IncomeTaxReconciliationMinorityInterestIncomeExpense",
    "IncomeTaxReconciliationNondeductibleExpense",
    "IncomeTaxReconciliationNondeductibleExpenseAmortization",
    "IncomeTaxReconciliationNondeductibleExpenseDepletion",
    "IncomeTaxReconciliationNondeductibleExpenseImpairmentLosses",
    "IncomeTaxReconciliationNondeductibleExpenseMealsAndEntertainment",
    "IncomeTaxReconciliationNondeductibleExpenseOther",
    "IncomeTaxReconciliationNondeductibleExpenseResearchAndDevelopment",
    "IncomeTaxReconciliationNondeductibleExpenseRestructuringCharges",
    "IncomeTaxReconciliationNondeductibleExpenseShareBasedCompensationCost",
    "IncomeTaxReconciliationOtherAdjustments",
    "IncomeTaxReconciliationOtherReconcilingItems",
    "IncomeTaxReconciliationPriorYearIncomeTaxes",
    "IncomeTaxReconciliationRepatriationOfForeignEarnings",
    "IncomeTaxReconciliationRepatriationOfForeignEarningsJobsCreationActOf2004",
    "IncomeTaxReconciliationStateAndLocalIncomeTaxes",
    "IncomeTaxReconciliationTaxContingencies",
    "IncomeTaxReconciliationTaxContingenciesDomestic",
    "IncomeTaxReconciliationTaxContingenciesForeign",
    "IncomeTaxReconciliationTaxContingenciesOther",
    "IncomeTaxReconciliationTaxContingenciesStateAndLocal",
    "IncomeTaxReconciliationTaxCredits",
    "IncomeTaxReconciliationTaxCreditsForeign",
    "IncomeTaxReconciliationTaxCreditsInvestment",
    "IncomeTaxReconciliationTaxCreditsOther",
    "IncomeTaxReconciliationTaxCreditsResearch",
    "IncomeTaxReconciliationTaxExemptIncome",
    "IncomeTaxReconciliationTaxHolidays",
    "IncomeTaxReconciliationTaxSettlements",
    "IncomeTaxReconciliationTaxSettlementsDomestic",
    "IncomeTaxReconciliationTaxSettlementsForeign",
    "IncomeTaxReconciliationTaxSettlementsStateAndLocal",
]
# Reconciling items named EffectiveIncomeTaxRateReconciliation*Amount with the same mapping.
REMOVED_RATE_RECONCILIATION_AMOUNTS = [
    "EffectiveIncomeTaxRateReconciliationFdiiAmount",
    "EffectiveIncomeTaxRateReconciliationGiltiAmount",
    "EffectiveIncomeTaxRateReconciliationTaxCutsAndJobsActOf2017Amount",
    "EffectiveIncomeTaxRateReconciliationTaxCutsAndJobsActOf2017TransitionTaxOnAccumulatedForeignEarningsAmount",
]


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.mark.fast
def test_forty_four_reconciliation_keys():
    assert len(REMOVED) == len(set(REMOVED)) == 44


@pytest.mark.fast
@pytest.mark.parametrize("tag", REMOVED + REMOVED_RATE_RECONCILIATION_AMOUNTS)
def test_reconciliation_item_has_no_standard_concept(index, tag):
    assert tag not in GAAP_MAPPINGS
    for spelling in (tag, f"us-gaap:{tag}", f"us-gaap_{tag}"):
        assert index.lookup(spelling) is None, spelling
        assert index.get_standard_concept(spelling, {"section": "Income Tax", "statement_type": "IncomeStatement"}) is None


@pytest.mark.fast
@pytest.mark.parametrize("tag", ["IncomeTaxExpenseBenefit", "us-gaap:IncomeTaxExpenseBenefit", "IncomeTaxExpenseContinuingOperations"])
def test_the_provision_keeps_income_taxes(index, tag):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == ["IncomeTaxes"]
    assert result.display_names == ["Income Tax Expense"]


@pytest.mark.fast
def test_apple_rate_reconciliation_has_one_income_tax_expense_row():
    """Apple FY2023 10-K, 0000320193-23-000106, rate reconciliation for fiscal 2023 ($M)."""
    xbrl = XBRL.from_directory(FIXTURE)
    role = next(
        s["role"] for s in xbrl.get_all_statements()
        if s["role"].endswith("/IncomeTaxesReconciliationofProvisionforIncomeTaxestoAmountComputedbyApplyingtheStatutoryFederalIncomeTaxRatetoIncomeBeforeProvisionforIncomeTaxesDetails")
    )
    frame = xbrl.statements[role].render(standard=True).to_dataframe()
    frame = frame[~frame["dimension"]].set_index("concept")

    taxes = frame[frame["standard_concept"] == "IncomeTaxes"]
    assert taxes.index.tolist() == ["us-gaap_IncomeTaxExpenseBenefit"]
    assert taxes["2023-09-30"].tolist() == [16_741_000_000]

    reconciliation = {
        "us-gaap_IncomeTaxReconciliationIncomeTaxExpenseBenefitAtFederalStatutoryIncomeTaxRate": 23_885_000_000,
        "us-gaap_IncomeTaxReconciliationStateAndLocalIncomeTaxes": 1_124_000_000,
        "us-gaap_IncomeTaxReconciliationForeignIncomeTaxRateDifferential": -5_744_000_000,
        "us-gaap_IncomeTaxReconciliationTaxCreditsResearch": 1_212_000_000,
        "us-gaap_IncomeTaxReconciliationOtherAdjustments": -192_000_000,
        "us-gaap_EffectiveIncomeTaxRateReconciliationFdiiAmount": 0,
    }
    for concept, value in reconciliation.items():
        assert frame.loc[concept, "2023-09-30"] == value, concept
        assert pd.isna(frame.loc[concept, "standard_concept"]), concept
    assert frame.loc["us-gaap_EffectiveIncomeTaxRateReconciliationFdiiAmount", "2022-09-24"] == 296_000_000
