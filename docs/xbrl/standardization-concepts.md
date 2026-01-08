# XBRL Standardization Concepts Reference

This document describes the 95 standard concepts used by EdgarTools to normalize
XBRL financial data across different companies. These concepts enable cross-company
comparison by mapping the ~18,000 possible SEC GAAP taxonomy tags to a consistent
set of standardized line items.

## Overview

| Metric | Value |
|--------|-------|
| **Total Standard Concepts** | 95 |
| **XBRL Tags Mapped** | 2,067 |
| **Coverage** | ~95% of common financial statement tags |
| **Source** | mpreiss9's production taxonomy (390+ companies) |

## Architecture

```
XBRL Tag (e.g., AccountsPayableCurrent)
    ↓ gaap_mappings.json (2,067 mappings)
Standard Concept (e.g., TradePayables)
    ↓ display_names.json (95 mappings)
Display Name (e.g., "Accounts Payable")
```

## Industry Context

The number of standardized concepts varies by provider:

| Provider | Line Items | Notes |
|----------|------------|-------|
| EdgarTools | 95 | Production-tested on 390+ companies |
| Capital IQ | ~100-150 | Varies by data package |
| Bloomberg | ~80-120 | Core financial line items |
| Refinitiv | ~100-200 | Standardized fundamentals |
| Morningstar | ~80-100 | Balance/Income/Cash Flow |

---

## Standard Concepts by Statement


### Balance Sheet - Current Assets

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `CashAndMarketableSecurities` | Cash and Cash Equivalents | 61 | `AssetBackedSecuritiesAtCarryingValue`, `AvailableForSaleDebtSecuritiesAmortizedCostBasis`, `AvailableForSaleSecurities`, ... |
| `TradeReceivables` | Accounts Receivable | 34 | `AccountsAndNotesReceivableNet`, `AccountsAndOtherReceivablesNetCurrent`, `AccountsNotesAndLoansReceivableNetCurrent`, ... |
| `Inventories` | Inventory | 66 | `AgriculturalRelatedInventory`, `AgriculturalRelatedInventoryFeedAndSupplies`, `AgriculturalRelatedInventoryGrowingCrops`, ... |
| `DeferredTaxCurrentAssets` | Deferred Tax Assets, Current | 44 | `DeferredIncomeTaxesAndOtherAssetsCurrent`, `DeferredIncomeTaxesAndOtherTaxReceivableCurrent`, `DeferredTaxAssetsDeferredIncome`, ... |
| `OtherOperatingCurrentAssets` | Other Current Assets | 50 | `AdvanceRoyaltiesCurrent`, `AdvancesOnInventoryPurchases`, `AmountOfDeferredCostsRelatedToLongTermContracts`, ... |
| `OtherNonOperatingCurrentAssets` | Other Non-Operating Current Assets | 131 | `AccountsReceivableRelatedParties`, `AccountsReceivableRelatedPartiesCurrent`, `AllowanceForDoubtfulOtherReceivablesCurrent`, ... |
| `RetirementRelatedCurrentAssets` | Retirement Related Assets, Current | 1 | `DefinedBenefitPlanCurrentAssets` |
| `CurrentAssetsTotal` | Total Current Assets | 1 | `AssetsCurrent` |


### Balance Sheet - Non-Current Assets

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `PlantPropertyEquipmentNet` | Property, Plant and Equipment | 53 | `AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment`, `AcquisitionCostsCumulative`, `BuildingsAndImprovementsGross`, ... |
| `Goodwill` | Goodwill | 10 | `Goodwill`, `GoodwillGross`, `GoodwillImpairedAccumulatedImpairmentLoss`, ... |
| `IntangibleAssets` | Intangible Assets | 17 | `BusinessCombinationRecognizedIdentifiableAssetsAcquiredAndLiabilitiesAssumedIntangibles`, `FiniteLivedCustomerListsGross`, `FiniteLivedCustomerRelationshipsGross`, ... |
| `LongtermInvestments` | Long-Term Investments | 60 | `AdvancesToAffiliate`, `AuctionRateSecuritiesNoncurrent`, `AvailableForSaleSecuritiesDebtMaturitiesAfterFiveThroughTenYearsFairValue`, ... |
| `DeferredTaxNoncurrentAssets` | Deferred Tax Assets, Non-Current | 45 | `DeferredIncomeTaxAssetsNet`, `DeferredIncomeTaxesAndOtherAssetsNoncurrent`, `DeferredTaxAssetsCapitalLossCarryforwards`, ... |
| `OtherOperatingNonCurrentAssets` | Other Non-Current Assets | 49 | `AccountsReceivableExcludingAccruedInterestAfterAllowanceForCreditLossNoncurrent`, `AccountsReceivableGross`, `AccountsReceivableGrossNoncurrent`, ... |
| `OtherNonOperatingNonCurrentAssets` | Other Non-Operating Non-Current Assets | 140 | `AccountsReceivableRelatedParties`, `AccountsReceivableRelatedPartiesNoncurrent`, `AccruedFeesAndOtherRevenueReceivable`, ... |
| `OperatingLeaseRightOfUseAsset` | Operating Lease Right-of-Use Asset | 1 | `OperatingLeaseRightOfUseAsset` |
| `RetirementRelatedNonCurrentAssets` | Retirement Related Assets, Non-Current | 4 | `AssetRetirementObligationLegallyRestrictedAssetsFairValue`, `DeferredCompensationPlanAssets`, `DefinedBenefitPlanAmountsRecognizedInBalanceSheet`, ... |
| `NonCurrentAssetsTotal` | Total Non-Current Assets | 2 | `AssetsNoncurrent`, `NoncurrentAssets` |
| `Assets` | Total Assets | 2 | `Assets`, `AssetsNet` |


### Balance Sheet - Current Liabilities

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `TradePayables` | Accounts Payable | 27 | `AccountsPayableAndAccruedLiabilitiesCurrent`, `AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent`, `AccountsPayableAndOtherAccruedLiabilities`, ... |
| `ShortTermDebt` | Short-Term Debt | 62 | `BankLoans`, `BankOverdrafts`, `BorrowingsUnderGuaranteedInvestmentAgreements`, ... |
| `DeferredTaxCurrentLiabilities` | Deferred Tax Liabilities, Current | 20 | `DeferredIncomeTaxLiabilities`, `DeferredIncomeTaxLiabilitiesNet`, `DeferredTaxAssetsLiabilitiesNetCurrent`, ... |
| `TaxesPayable` | Taxes Payable | 7 | `AccrualForTaxesOtherThanIncomeTaxesCurrent`, `AccruedIncomeTaxes`, `AccruedIncomeTaxesCurrent`, ... |
| `DividendsPayable` | Dividends Payable | 2 | `DividendsPayableCurrent`, `DividendsPayableCurrentAndNoncurrent` |
| `OtherOperatingCurrentLiabilities` | Other Current Liabilities | 68 | `AccrualForEnvironmentalLossContingencies`, `AccruedAdvertisingCurrent`, `AccruedAdvertisingCurrentAndNoncurrent`, ... |
| `OtherNonOperatingCurrentLiabilities` | Other Non-Operating Current Liabilities | 82 | `AccountsPayableOtherCurrentAndNoncurrent`, `AccrualForTaxesOtherThanIncomeTaxesCurrentAndNoncurrent`, `AccruedCappingClosurePostClosureAndEnvironmentalCosts`, ... |
| `RetirementRelatedCurrentLiabilities` | Retirement Related Liabilities, Current | 18 | `DeferredCompensationCashBasedArrangementsLiabilityCurrent`, `DeferredCompensationLiabilityCurrent`, `DeferredCompensationLiabilityCurrentAndNoncurrent`, ... |
| `OperatingLeaseCurrentDebtEquivalent` | Operating Lease Liability, Current | 2 | `OperatingLeaseLiability`, `OperatingLeaseLiabilityCurrent` |
| `CurrentLiabilitiesTotal` | Total Current Liabilities | 1 | `LiabilitiesCurrent` |


### Balance Sheet - Non-Current Liabilities

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `LongTermDebt` | Long-Term Debt | 71 | `CapitalLeaseObligations`, `CapitalLeaseObligationsNoncurrent`, `CommercialPaperNoncurrent`, ... |
| `DeferredTaxNonCurrentLiabilities` | Deferred Tax Liabilities, Non-Current | 35 | `AccruedIncomeTaxes`, `AccruedIncomeTaxesNoncurrent`, `AccumulatedDeferredInvestmentTaxCredit`, ... |
| `OtherOperatingNonCurrentLiabilities` | Other Non-Current Liabilities | 31 | `AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent`, `AccountsPayableAndAccruedLiabilitiesNoncurrent`, `AccountsPayableAndOtherAccruedLiabilities`, ... |
| `OtherNonOperatingNonCurrentLiabilities` | Other Non-Operating Non-Current Liabilities | 81 | `AccountsPayableOtherCurrentAndNoncurrent`, `AccrualForTaxesOtherThanIncomeTaxesCurrentAndNoncurrent`, `AccruedEmployeeBenefitsCurrentAndNoncurrent`, ... |
| `RetirementRelatedNonCurrentLiabilities` | Retirement Related Liabilities, Non-Current | 18 | `AssetRetirementObligation`, `DeferredCompensationLiabilityClassifiedNoncurrent`, `DeferredCompensationLiabilityCurrentAndNoncurrent`, ... |
| `OperatingLeaseNonCurrentDebtEquivalent` | Operating Lease Liability, Non-Current | 3 | `OperatingLeaseLiability`, `OperatingLeaseLiabilityNoncurrent`, `OperatingLeaseLiabilityStatementOfFinancialPositionExtensibleList` |
| `OngoingOperatingProvisions(WarrantiesEtc)` | Warranty and Other Provisions | 22 | `ContractWithCustomerRefundLiability`, `ContractWithCustomerRefundLiabilityNoncurrent`, `CustomerAdvancesAndDeposits`, ... |
| `DefinteLivedOperatingProvisions(DecommissioningEtc)` | Asset Retirement Obligations | 10 | `AccruedCappingClosurePostClosureAndEnvironmentalCosts`, `AccruedCappingClosurePostClosureAndEnvironmentalCostsNoncurrent`, `AssetRetirementObligationsNoncurrent`, ... |
| `RestructuringProvisions` | Restructuring Provisions | 2 | `RestructuringReserve`, `RestructuringReserveNoncurrent` |
| `NonCurrentLiabilitiesTotal` | Total Non-Current Liabilities | 1 | `LiabilitiesNoncurrent` |
| `Liabilities` | Total Liabilities | 1 | `Liabilities` |


### Balance Sheet - Equity

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `CommonEquity` | Total Stockholders' Equity | 50 | `AccumulatedOtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentNetOfTax`, `AccumulatedOtherComprehensiveIncomeLossCumulativeChangesInNetGainLossFromCashFlowHedgesEffectNetOfTax`, `AccumulatedOtherComprehensiveIncomeLossDefinedBenefitPensionAndOtherPostretirementPlansNetOfTax`, ... |
| `PreferredStock` | Preferred Stock | 6 | `AdditionalPaidInCapitalPreferredStock`, `PreferredStockRedemptionAmount`, `PreferredStockSharesSubscribedButUnissuedSubscriptionsReceivable`, ... |
| `TreasuryShares` | Treasury Stock | 2 | `TreasuryStockCommonShares`, `TreasuryStockShares` |
| `MinorityInterestBalance` | Noncontrolling Interest | 10 | `MembersEquityAttributableToNoncontrollingInterest`, `MinorityInterest`, `MinorityInterestInJointVentures`, ... |
| `TemporaryAndMezzanineFinancing` | Temporary Equity | 11 | `RedeemableNoncontrollingInterestEquityCarryingAmount`, `RedeemableNoncontrollingInterestEquityCommonCarryingAmount`, `RedeemableNoncontrollingInterestEquityCommonFairValue`, ... |
| `AllEquityBalance` | Total Equity | 1 | `StockholdersEquity` |
| `AllEquityBalanceIncludingMinorityInterest` | Total Equity Including Noncontrolling Interest | 4 | `AociIncludingPortionAttributableToNoncontrollingInterestTax`, `DefinedBenefitPlanAccumulatedOtherComprehensiveIncomeBeforeTax`, `LimitedLiabilityCompanyLlcMembersEquityIncludingPortionAttributableToNoncontrollingInterest`, ... |
| `LiabilitiesAndEquity` | Total Liabilities and Equity | 1 | `LiabilitiesAndStockholdersEquity` |


### Income Statement - Revenue & Gross Profit

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `Revenue` | Revenue | 139 | `AdmissionsRevenue`, `AdvertisingRevenue`, `BinderSalesRevenue`, ... |
| `CostOfGoodsAndServicesSold` | Cost of Revenue | 142 | `AdvertisingRevenueCost`, `AffiliateCosts`, `AircraftRentalAndLandingFees`, ... |
| `GrossProfit` | Gross Profit | 1 | `GrossProfit` |


### Income Statement - Operating Expenses

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `ResearchAndDevelopementExpenses` | Research and Development Expense | 6 | `ExplorationExpense`, `ResearchAndDevelopmentAssetAcquiredOtherThanThroughBusinessCombinationWrittenOff`, `ResearchAndDevelopmentExpense`, ... |
| `SellingGeneralAndAdminExpenses` | Selling, General and Administrative Expense | 16 | `CommunicationsAndInformationTechnology`, `GeneralAndAdministrativeExpense`, `GeneralInsuranceExpense`, ... |
| `MarketingExpenses` | Marketing Expense | 4 | `AdvertisingExpense`, `CooperativeAdvertisingExpense`, `MarketingAndAdvertisingExpense`, ... |
| `DepreciationExpense` | Depreciation Expense | 13 | `CapitalizedComputerSoftwareAmortization`, `CapitalizedComputerSoftwareImpairments`, `CostDepreciationAmortizationAndDepletion`, ... |
| `AmortizationOfIntangibles` | Amortization of Intangibles | 4 | `AmortizationOfIntangibleAssets`, `ImpairmentOfIntangibleAssetsExcludingGoodwill`, `ImpairmentOfIntangibleAssetsFinitelived`, ... |
| `OtherOperatingExpense` | Other Operating Expense | 45 | `AccretionExpense`, `AcquisitionCosts`, `AllocatedShareBasedCompensationExpense`, ... |
| `RestructuringExpenseBenefit` | Restructuring Expense | 32 | `AmortizationOfAcquisitionCosts`, `BusinessCombinationAcquisitionRelatedCosts`, `BusinessCombinationIntegrationRelatedCosts`, ... |
| `GoodwillWriteoffs` | Goodwill Impairment | 9 | `AdjustmentForAmortization`, `AssetImpairmentCharges`, `CostOfGoodsAndServicesSoldAmortization`, ... |
| `CostsSubtotal` | Total Costs and Expenses | 5 | `BenefitsLossesAndExpenses`, `CostsAndExpenses`, `EmployeeBenefitsAndShareBasedCompensation`, ... |
| `OperatingIncomeLoss` | Operating Income | 1 | `OperatingIncomeLoss` |


### Income Statement - Non-Operating & Tax

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `InterestExpense` | Interest Expense | 38 | `AmortizationOfDebtDiscountPremium`, `AmortizationOfDeferredHedgeGains`, `AmortizationOfFinancingCosts`, ... |
| `InterestIncome` | Interest Income | 20 | `InterestAndDividendIncomeOperating`, `InterestAndOtherIncome`, `InterestIncomeExpenseAfterProvisionForLoanLoss`, ... |
| `NonoperatingIncomeExpense` | Non-Operating Income (Expense) | 199 | `AccretionAmortizationOfDiscountsAndPremiumsInvestments`, `AccretionExpenseIncludingAssetRetirementObligations`, `AvailableForSaleSecuritiesGrossRealizedGainLossNet`, ... |
| `SpecialItemsIncomeExpense(Pretax)` | Special Items | 2 | `UnusualOrInfrequentItemInsuranceProceeds`, `UnusualOrInfrequentItemNetOfInsuranceProceeds` |
| `PretaxIncomeLoss` | Income Before Tax | 1 | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` |
| `IncomeTaxes` | Income Tax Expense | 78 | `AdjustmentsToAdditionalPaidInCapitalTaxEffectFromShareBasedCompensation`, `CurrentFederalStateAndLocalTaxExpenseBenefit`, `CurrentFederalTaxExpenseBenefit`, ... |
| `IncomeLossContinuingOperations` | Income from Continuing Operations | 1 | `IncomeLossFromContinuingOperations` |
| `ExtraordinaryItemsIncomeExpense(PostTax)` | Extraordinary Items | 35 | `DiscontinuedOperationAmountOfAdjustmentToPriorPeriodGainLossOnDisposalBeforeIncomeTax`, `DiscontinuedOperationAmountOfAdjustmentToPriorPeriodGainLossOnDisposalNetOfTax`, `DiscontinuedOperationAmountOfOtherIncomeLossFromDispositionOfDiscontinuedOperationNetOfTax`, ... |
| `MinorityInterestIncomeExpense` | Net Income Attributable to Noncontrolling Interest | 10 | `ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest`, `EquityMethodInvestmentOtherThanTemporaryImpairment`, `IncomeLossFromContinuingOperationsAttributableToNoncontrollingEntity`, ... |
| `NetIncome` | Net Income | 2 | `IncomeLossAttributableToParent`, `NetIncomeLoss` |
| `NetIncomeToCommonShareholders` | Net Income to Common Shareholders | 3 | `NetIncomeLossAvailableToCommonStockholdersBasic`, `NetIncomeLossFromContinuingOperationsAvailableToCommonShareholdersBasic`, `ParticipatingSecuritiesDistributedAndUndistributedEarnings` |
| `PreferredDividendExpense` | Preferred Dividends | 13 | `DividendsPreferredStock`, `DividendsPreferredStockCash`, `DividendsPreferredStockStock`, ... |
| `ProfitLoss` | Profit or Loss | 1 | `ProfitLoss` |


### Cash Flow & Capital

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `CapitalExpenses` | Capital Expenditures | 4 | `PaymentsToAcquireOtherProductiveAssets`, `PaymentsToAcquireOtherPropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets`, ... |
| `CommonDividendsPaid` | Dividends Paid | 4 | `Dividends`, `DividendsCash`, `DividendsCommonStock`, ... |
| `EquityExpenseIncome(BuybackIssued)` | Stock Repurchases (Issuances) | 4 | `PaymentsForRepurchaseOfCommonStock`, `ProceedsFromIssuanceOfCommonStock`, `ProceedsFromSaleOfTreasuryStock`, ... |


### Per Share Data

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `CommonDividendsPerShare` | Dividends Per Share | 3 | `CommonStockDividendsPerShareCashPaid`, `CommonStockDividendsPerShareDeclared`, `DividendsPayableAmountPerShare` |
| `SharesAverage` | Weighted Average Shares Outstanding | 2 | `WeightedAverageBasicSharesOutstandingProForma`, `WeightedAverageNumberOfSharesOutstandingBasic` |
| `SharesDilutionAdjustment` | Dilution Adjustment | 2 | `IncrementalCommonSharesAttributableToShareBasedPaymentArrangements`, `WeightedAverageNumberDilutedSharesOutstandingAdjustment` |
| `SharesFullyDilutedAverage` | Weighted Average Shares Outstanding, Diluted | 2 | `WeightedAverageNumberOfDilutedSharesOutstanding`, `WeightedAverageNumberOfShareOutstandingBasicAndDiluted` |
| `SharesIssued` | Shares Issued | 2 | `CommonStockSharesIssued`, `SharesIssued` |
| `SharesYearEnd` | Shares Outstanding | 3 | `CommonStockSharesOutstanding`, `EntityCommonStockSharesOutstanding`, `SharesOutstanding` |


### Operating Lease Commitments

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `OperatingLeaseCommitmentYear1` | Operating Lease Commitment, Year 1 | 1 | `OperatingLeasesFutureMinimumPaymentsDueCurrent` |
| `OperatingLeaseCommitmentYear2` | Operating Lease Commitment, Year 2 | 1 | `OperatingLeasesFutureMinimumPaymentsDueInTwoYears` |
| `OperatingLeaseCommitmentYear3` | Operating Lease Commitment, Year 3 | 1 | `OperatingLeasesFutureMinimumPaymentsDueInThreeYears` |
| `OperatingLeaseCommitmentYear4` | Operating Lease Commitment, Year 4 | 1 | `OperatingLeasesFutureMinimumPaymentsDueInFourYears` |
| `OperatingLeaseCommitmentYear5` | Operating Lease Commitment, Year 5 | 1 | `OperatingLeasesFutureMinimumPaymentsDueInFiveYears` |
| `OperatingLeaseCommitmentAfterYear5` | Operating Lease Commitment, Thereafter | 1 | `OperatingLeasesFutureMinimumPaymentsDueThereafter` |


### Intangible Amortization Forecast

| Standard Concept | Display Name | XBRL Tags | Examples |
|------------------|--------------|-----------|----------|
| `ForecastedIntangibleAmortizationYear1` | Forecasted Amortization, Year 1 | 3 | `FiniteLivedIntangibleAssetsAmortizationExpenseNextRollingTwelveMonths`, `FiniteLivedIntangibleAssetsAmortizationExpenseNextTwelveMonths`, `FiniteLivedIntangibleAssetsAmortizationExpenseRemainderOfFiscalYear` |
| `ForecastedIntangibleAmortizationYear2` | Forecasted Amortization, Year 2 | 2 | `FiniteLivedIntangibleAssetsAmortizationExpenseRollingYearTwo`, `FiniteLivedIntangibleAssetsAmortizationExpenseYearTwo` |
| `ForecastedIntangibleAmortizationYear3` | Forecasted Amortization, Year 3 | 2 | `FiniteLivedIntangibleAssetsAmortizationExpenseRollingYearThree`, `FiniteLivedIntangibleAssetsAmortizationExpenseYearThree` |
| `ForecastedIntangibleAmortizationYear4` | Forecasted Amortization, Year 4 | 1 | `FiniteLivedIntangibleAssetsAmortizationExpenseYearFour` |
| `ForecastedIntangibleAmortizationYear5` | Forecasted Amortization, Year 5 | 1 | `FiniteLivedIntangibleAssetsAmortizationExpenseYearFive` |
| `ForecastedIntangibleAmortizationAfterYear5` | Forecasted Amortization, Thereafter | 2 | `FiniteLivedIntangibleAssetsAmortizationExpenseAfterYearFive`, `FiniteLivedIntangibleAssetsAmortizationExpenseRollingAfterYearFive` |

---

## Concept Details

### Balance Sheet Concepts

#### Current vs Non-Current Classification

The taxonomy distinguishes between current (due within 1 year) and non-current items:

- **Current Assets**: `CashAndMarketableSecurities`, `TradeReceivables`, `Inventories`, etc.
- **Non-Current Assets**: `PlantPropertyEquipmentNet`, `Goodwill`, `LongtermInvestments`, etc.
- **Current Liabilities**: `TradePayables`, `ShortTermDebt`, etc.
- **Non-Current Liabilities**: `LongTermDebt`, `DeferredTaxNonCurrentLiabilities`, etc.

#### Operating vs Non-Operating Classification

Items are also classified by their relationship to core operations:

- **Operating**: Related to primary business activities (e.g., `OtherOperatingCurrentAssets`)
- **Non-Operating**: Related to financing/investing activities (e.g., `OtherNonOperatingCurrentAssets`)

### Income Statement Concepts

#### Revenue Recognition

All revenue-related XBRL tags (139 variations) map to the single `Revenue` concept.
This includes:
- `RevenueFromContractWithCustomerExcludingAssessedTax`
- `Revenues`
- `SalesRevenueNet`
- `SalesRevenueGoodsNet`
- And 135 more industry-specific variations

#### Cost of Revenue

Cost tags (142 variations) map to `CostOfGoodsAndServicesSold`:
- `CostOfRevenue`
- `CostOfGoodsAndServicesSold`
- `CostOfGoodsSold`
- `CostOfServices`

### Operating Lease Accounting (ASC 842)

Following the ASC 842 lease accounting standard, the taxonomy includes:

- **Right-of-Use Asset**: `OperatingLeaseRightOfUseAsset`
- **Current Liability**: `OperatingLeaseCurrentDebtEquivalent`
- **Non-Current Liability**: `OperatingLeaseNonCurrentDebtEquivalent`
- **Future Commitments**: Years 1-5 and thereafter

### Provisions and Reserves

The taxonomy distinguishes between:

- **Ongoing Provisions**: `OngoingOperatingProvisions(WarrantiesEtc)` - recurring obligations
- **Definite-Lived Provisions**: `DefinteLivedOperatingProvisions(DecommissioningEtc)` - asset retirement
- **Restructuring**: `RestructuringProvisions` - one-time reorganization costs

---

## Ambiguous Tags

Some XBRL tags can map to multiple concepts depending on context. These are flagged
as "ambiguous" and require context-aware resolution (Phase 4 of implementation).

**Total Ambiguous Tags**: 215 (9.2% of mapped tags)

### Common Ambiguity Types

1. **Current/Non-Current Ambiguity** (202 tags)
   - Example: `AccountsPayableCurrentAndNoncurrent` → `TradePayables` OR `OtherOperatingNonCurrentLiabilities`
   - Resolution: Based on balance sheet section placement

2. **Asset/Liability Ambiguity** (12 tags)
   - Example: `DeferredTaxAssetsLiabilitiesNet` → `DeferredTaxNoncurrentAssets` OR `DeferredTaxNonCurrentLiabilities`
   - Resolution: Based on sign (positive = asset, negative = liability)

3. **Operating/Non-Operating Ambiguity**
   - Example: `OtherAssetsNoncurrent` → `OtherOperatingNonCurrentAssets` OR `OtherNonOperatingNonCurrentAssets`
   - Resolution: Based on statement section context

---

## Excluded Tags (DropThisItem)

276 XBRL tags are explicitly excluded from standardization because they:
- Confuse financial analysis (EPS details, pro-forma metrics)
- Are redundant with other tags
- Don't map cleanly to standard concepts

**Examples of excluded tags:**
- `AcceleratedShareRepurchasesFinalPricePaidPerShare`
- `BasicEarningsPerShareProForma`
- `BusinessAcquisitionProFormaEarningsPerShareBasic`
- Various per-share calculation details

---

## Deprecated Tags

410 XBRL tags are marked as deprecated by the SEC with the year of deprecation.
The mapping still works for historical filings, but these tags should not appear
in recent filings.

**Example:**
- `Revenues` (deprecated 2018) → Still maps to `Revenue`
- `AccountsPayableRelatedPartiesCurrent` (deprecated 2023) → Still maps to `TradePayables`

---

## Usage Examples

### Python API

```python
from edgar.xbrl.standardization.reverse_index import (
    get_standard_concept,
    get_display_name,
    lookup
)

# Simple lookup
concept = get_standard_concept("AccountsPayableCurrent")
# Returns: "TradePayables"

display = get_display_name("AccountsPayableCurrent")
# Returns: "Accounts Payable"

# Full result with metadata
result = lookup("AccountsPayableCurrentAndNoncurrent")
result.is_ambiguous          # True
result.standard_concepts     # ['TradePayables', 'OtherOperatingNonCurrentLiabilities']
result.display_names         # ['Accounts Payable', 'Other Non-Current Liabilities']
result.comment               # 'Curr/NonCurr ambiguity'
```

### Checking Coverage

```python
from edgar.xbrl.standardization.reverse_index import get_reverse_index

index = get_reverse_index()
print(index.stats)
# {'total_mappings': 2067, 'ambiguous_count': 215, 'deprecated_count': 410, 'excluded_count': 276}
```

---

## Files

| File | Purpose |
|------|---------|
| `gaap_mappings.json` | 2,067 XBRL tag → standard concept mappings |
| `display_names.json` | 95 standard concept → display name mappings |
| `exclusions.py` | 276 excluded (DropThisItem) tags |
| `reverse_index.py` | O(1) lookup implementation |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01 | Initial release with 95 concepts, 2,067 mappings |

---

## Credits

The standardization taxonomy is based on the production mappings shared by
[@mpreiss9](https://github.com/mpreiss9), tested across 390+ companies.

See: [GitHub Issue #494](https://github.com/dgunning/edgartools/issues/494)
