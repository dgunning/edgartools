# Income Statement Sector Sample Scan

## Scope
- 15 sectors, 5 tickers per sector (income statement concepts only).
- Concepts derived from SEC company facts using statement-type mapping.
- Coverage compared against core + company standardization mappings.

## Coverage summary
- Tickers processed: 70 of 75.
- Tickers with errors: 5.
- Unique income statement concepts: 148.
- Unique concepts missing mappings: 106.

## Global top missing concepts (by ticker count)
- us-gaap_CurrentIncomeTaxExpenseBenefit: 42
- us-gaap_GoodwillImpairmentLoss: 36
- us-gaap_CommonStockDividendsPerShareDeclared: 35
- us-gaap_InvestmentIncomeInterest: 27
- us-gaap_BusinessCombinationAcquisitionRelatedCosts: 26
- us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare: 25
- us-gaap_IncomeLossFromEquityMethodInvestments: 25
- us-gaap_IncomeLossFromContinuingOperationsPerBasicShare: 24
- us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic: 23
- us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax: 22
- us-gaap_ForeignCurrencyTransactionGainLossBeforeTax: 21
- us-gaap_OperatingLeaseExpense: 20
- us-gaap_OtherOperatingIncomeExpenseNet: 18
- us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToReportingEntity: 18
- us-gaap_RestructuringCharges: 18
- us-gaap_OtherIncome: 18
- us-gaap_InterestIncomeExpenseNonoperatingNet: 17
- us-gaap_GainLossOnInvestments: 17
- us-gaap_OtherCostAndExpenseOperating: 14
- us-gaap_GainLossRelatedToLitigationSettlement: 13

## Sector highlights (top missing concepts)
- aerospace: concepts=69, missing=35
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 5
  - us-gaap_OtherOperatingIncomeExpenseNet: 4
  - us-gaap_GoodwillImpairmentLoss: 4
  - us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic: 3
  - us-gaap_InterestIncomeExpenseNonoperatingNet: 3
- automotive: concepts=49, missing=20
  - us-gaap_InvestmentIncomeInterest: 4
  - us-gaap_OtherIncome: 4
  - us-gaap_InvestmentIncomeNet: 3
  - us-gaap_BusinessCombinationAcquisitionRelatedCosts: 2
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 2
- banking: concepts=66, missing=46
  - us-gaap_CommonStockDividendsPerShareDeclared: 4
  - us-gaap_BankOwnedLifeInsuranceIncome: 3
  - us-gaap_BusinessCombinationAcquisitionRelatedCosts: 3
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 3
  - us-gaap_GainLossOnInvestments: 3
- consumergoods: concepts=46, missing=23
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 2
  - us-gaap_InsuranceRecoveries: 2
  - ifrs-full_GeneralAndAdministrativeExpense: 1
  - ifrs-full_GrossProfit: 1
  - ifrs-full_InterestExpense: 1
- energy: concepts=55, missing=27
  - us-gaap_OtherOperatingIncomeExpenseNet: 3
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 2
  - us-gaap_GainLossOnInvestments: 2
  - us-gaap_GainLossRelatedToLitigationSettlement: 2
  - us-gaap_GoodwillImpairmentLoss: 2
- healthcare: concepts=51, missing=21
  - ifrs-full_OtherIncome: 2
  - ifrs-full_ResearchAndDevelopmentExpense: 2
  - us-gaap_LaborAndRelatedExpense: 2
  - us-gaap_InterestExpenseDebt: 2
  - ifrs-full_GrossProfit: 1
- hospitality: concepts=61, missing=28
  - us-gaap_GoodwillImpairmentLoss: 5
  - us-gaap_InvestmentIncomeInterest: 5
  - us-gaap_CommonStockDividendsPerShareDeclared: 4
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 4
  - us-gaap_BusinessCombinationAcquisitionRelatedCosts: 4
- insurance: concepts=63, missing=40
  - us-gaap_CededPremiumsWritten: 5
  - us-gaap_CommonStockDividendsPerShareDeclared: 5
  - us-gaap_DeferredPolicyAcquisitionCostAmortizationExpense: 5
  - us-gaap_InvestmentIncomeNet: 5
  - us-gaap_LiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseIncurredClaims1: 5
- mining: concepts=52, missing=21
  - us-gaap_OtherIncome: 2
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 2
  - us-gaap_ForeignCurrencyTransactionGainLossBeforeTax: 2
  - us-gaap_OtherExpenses: 2
  - us-gaap_OtherOperatingIncomeExpenseNet: 2
- realestate: concepts=71, missing=43
  - us-gaap_CommonStockDividendsPerShareDeclared: 5
  - us-gaap_IncomeLossFromContinuingOperationsPerBasicShare: 4
  - us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare: 4
  - us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax: 4
  - us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToReportingEntity: 4
- retail: concepts=55, missing=25
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 5
  - us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare: 5
  - us-gaap_IncomeLossFromContinuingOperationsPerBasicShare: 4
  - us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax: 4
  - us-gaap_InterestIncomeExpenseNonoperatingNet: 3
- tech: concepts=66, missing=31
  - us-gaap_GoodwillImpairmentLoss: 5
  - us-gaap_RestructuringCharges: 5
  - us-gaap_InvestmentIncomeInterest: 4
  - us-gaap_BusinessCombinationAcquisitionRelatedCosts: 3
  - us-gaap_ForeignCurrencyTransactionGainLossBeforeTax: 3
- telecom: concepts=69, missing=31
  - us-gaap_GoodwillImpairmentLoss: 3
  - us-gaap_IncomeLossFromContinuingOperationsPerBasicShare: 3
  - us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare: 3
  - us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax: 3
  - us-gaap_CommonStockDividendsPerShareDeclared: 2
- transportation: concepts=62, missing=31
  - us-gaap_CommonStockDividendsPerShareDeclared: 5
  - us-gaap_CurrentIncomeTaxExpenseBenefit: 5
  - us-gaap_InvestmentIncomeInterest: 5
  - us-gaap_ForeignCurrencyTransactionGainLossBeforeTax: 3
  - us-gaap_FuelCosts: 3
- utilities: concepts=52, missing=28
  - us-gaap_GoodwillImpairmentLoss: 2
  - us-gaap_IncomeLossFromContinuingOperationsPerBasicShare: 2
  - us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare: 2
  - us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax: 2
  - us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToReportingEntity: 2

## Sources
- edgar/xbrl/standardization/concept_mappings.json
- edgar/xbrl/standardization/company_mappings/*.json
- edgar/reference/data/company_tickers.pq
- SEC company facts API (cached in local edgar cache)

## Related
- docs-internal/research/sec-filings/data-structures/xbrl-concept-mappings-report.md

## Outputs
- docs-internal\research\sec-filings\data-structures\income-statement-sector-samples.json