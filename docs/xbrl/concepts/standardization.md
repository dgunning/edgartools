# XBRL Standardization Concepts Reference

This document describes the 95 standard concepts used by EdgarTools to normalize
XBRL financial data across different companies. These concepts enable cross-company
comparison by mapping the ~18,000 possible SEC GAAP taxonomy tags to a consistent
set of standardized line items.

## How Standardization Works

**Labels are always preserved** - the company's original presentation is shown exactly as filed.

Standardization adds a `standard_concept` column to DataFrames, mapping each line item to
one of 95 standard categories:

```python
# Get a statement DataFrame
df = statement.to_dataframe()

# Labels show original company presentation
# standard_concept maps to standard categories for analysis
print(df[['label', 'standard_concept']].head())
#                          label           standard_concept
# 0        Cash and cash items  CashAndMarketableSecurities
# 1      Trade receivables, net             TradeReceivables
# 2        Prepaid expenses       OtherNonOperatingCurrentAssets

# Aggregate by standard concept for cross-company comparison
standardized = df.groupby('standard_concept')[['2024-09-30']].sum()
```

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

## Python API (v5.9.0+)

EdgarTools provides several APIs for working with standardized concepts:

### Module-Level Singletons (Recommended)

For best performance, use the module-level singletons which load mappings once per session:

```python
from edgar.xbrl.standardization import (
    get_default_mapper,
    get_default_store,
    StandardConcept,
    StandardizationCache
)

# Get the singleton mapper - eliminates redundant file I/O
mapper = get_default_mapper()

# Map a company concept to standardized label
label = mapper.map_concept(
    "us-gaap_AccountsPayableCurrent",
    "Accounts Payable",
    {"statement_type": "BalanceSheet"}
)
# Returns: "Accounts Payable"
```

### StandardConcept Enum

Type-safe enum for all standardized concepts:

```python
from edgar.xbrl.standardization import StandardConcept

# Access standard concept labels
StandardConcept.REVENUE.value           # "Revenue"
StandardConcept.NET_INCOME.value        # "Net Income"
StandardConcept.TOTAL_ASSETS.value      # "Total Assets"
StandardConcept.ACCOUNTS_PAYABLE.value  # "Accounts Payable"

# Look up a concept by its label
concept = StandardConcept.get_from_label("Revenue")
# Returns: StandardConcept.REVENUE

# Get all available standard values
all_values = StandardConcept.get_all_values()
# Returns: {'Revenue', 'Net Income', 'Total Assets', ...}
```

### StandardizationCache (Per-XBRL Caching)

For high-performance workflows, use `StandardizationCache` which caches results per XBRL instance:

```python
# The cache is automatically attached to XBRL instances
xbrl = filing.xbrl()

# Access via the standardization property
cache = xbrl.standardization

# Get cached label lookups
label = cache.get_standard_label(
    "us-gaap_Revenue",
    "Total Revenue",
    {"statement_type": "IncomeStatement"}
)

# Standardize entire statement with caching
raw_data = xbrl.get_statement_data("IncomeStatement")
standardized = cache.standardize_statement_data(raw_data, "IncomeStatement")

# Check cache statistics
print(cache.cache_stats)
# {'label_cache_size': 42, 'statement_cache_size': 1, 'cached_statements': ['IncomeStatement']}

# Clear cache when needed
cache.clear_cache()  # Clear all
cache.clear_cache("IncomeStatement")  # Clear specific statement
```

### Reverse Index API (Low-Level)

Direct O(1) lookup for XBRL tags:

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

## Context-Aware Disambiguation

Starting in v5.9.0, EdgarTools uses context-aware disambiguation to resolve ambiguous tags.

### How It Works

Ambiguous tags (e.g., `AccountsPayableCurrentAndNoncurrent`) can map to multiple concepts.
EdgarTools uses two complementary strategies to disambiguate:

#### 1. Calculation Parent Derivation

When an item has a `calculation_parent`, EdgarTools infers its section:

```python
# Item with calculation_parent="us-gaap:AssetsCurrent"
# → Inferred section: "Current Assets"
# → Resolves ambiguity toward current asset concepts

# Supported parent → section mappings:
# AssetsCurrent → "Current Assets"
# AssetsNoncurrent → "Non-Current Assets"
# LiabilitiesCurrent → "Current Liabilities"
# LiabilitiesNoncurrent → "Non-Current Liabilities"
# StockholdersEquity → "Equity"
```

#### 2. Bottom-Up Section Scanning (mpreiss9 method)

For items without calculation parents, EdgarTools scans the statement from bottom to top,
using subtotals as section boundaries:

```
Total Current Assets        ← Defines boundary for "Current Assets" section
  ↑
  All items above until next subtotal belong to "Current Assets"
  ↑
Property, Plant & Equipment ← This item gets assigned "Current Assets"
                              section based on its position relative to subtotal
```

### Passing Context to the Mapper

When calling the mapper directly, you can provide context for disambiguation:

```python
mapper = get_default_mapper()

# Provide context for accurate disambiguation
label = mapper.map_concept(
    "us-gaap_OtherAssetsNoncurrent",
    "Other Assets",
    {
        "statement_type": "BalanceSheet",
        "section": "Non-Current Assets",  # Helps resolve operating vs non-operating
        "calculation_parent": "us-gaap:AssetsNoncurrent",
        "level": 2,
        "is_total": False
    }
)
```

### Context Keys

| Key | Description | Used For |
|-----|-------------|----------|
| `statement_type` | "BalanceSheet", "IncomeStatement", etc. | Statement-specific matching |
| `section` | "Current Assets", "Equity", etc. | Disambiguating current/non-current |
| `calculation_parent` | Parent concept in calculation tree | Deriving section automatically |
| `level` | Indentation level (0-5) | Identifying subtotals vs details |
| `is_total` | True for subtotal/total rows | Section boundary detection |
| `balance` | "debit" or "credit" | Sign-based disambiguation |

---

## Files

| File | Purpose |
|------|---------|
| `gaap_mappings.json` | 2,067 XBRL tag → standard concept mappings |
| `display_names.json` | 95 standard concept → display name mappings |
| `exclusions.py` | 276 excluded (DropThisItem) tags |
| `reverse_index.py` | O(1) lookup implementation |
| `core.py` | StandardConcept enum, MappingStore, ConceptMapper, standardize_statement |
| `cache.py` | StandardizationCache for per-XBRL instance caching |
| `sections.py` | Section classification for disambiguation |
| `__init__.py` | Module exports and singleton accessors |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 5.9.0 | 2026-01 | Context-aware disambiguation, bottom-up section scanning, StandardizationCache |
| 5.8.0 | 2026-01 | Module-level singletons (get_default_mapper, get_default_store) |
| 1.0 | 2026-01 | Initial release with 95 concepts, 2,067 mappings |

---

## Related Resources

- [XBRL Documentation Hub](../index.md) - Central navigation for all XBRL docs
- [Extract Financial Statements Guide](../../guides/extract-statements.md) - Complete guide to extracting financial data
- [Dimension Handling Guide](dimension-handling.md) - Understanding dimensional data and segment breakdowns
- [Multi-Period Analysis Guide](../guides/multi-period-analysis.md) - Working with XBRLS for multi-period comparison

---

## Credits

The standardization taxonomy is based on the production mappings shared by
[@mpreiss9](https://github.com/mpreiss9), tested across 390+ companies.

See: [GitHub Issue #494](https://github.com/dgunning/edgartools/issues/494)
