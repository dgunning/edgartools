# Universal XBRL Concepts - MAG7 Analysis

**Date:** 2026-01-06  
**Source:** Analysis of calculation trees from all MAG7 companies' 10-K filings

---

## Summary

These **27 concepts** appear in the calculation trees of **ALL 7** MAG7 companies (GOOG, AMZN, AAPL, MSFT, NVDA, TSLA, META). They represent the most standardized financial metrics across major tech companies.

---

## Income Statement Concepts

| XBRL Concept | Standard Name | Description |
|--------------|---------------|-------------|
| `RevenueFromContractWithCustomerExcludingAssessedTax` | **Revenue** | Total revenue from contracts with customers |
| `OperatingIncomeLoss` | **Operating Income** | Income from operations before interest/taxes |
| `NonoperatingIncomeExpense` | **Non-Operating Income** | Interest, investment gains, other income/expense |
| `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` | **Pretax Income** | Income before income tax expense |
| `IncomeTaxExpenseBenefit` | **Income Tax Expense** | Provision for income taxes |
| `NetIncomeLoss` | **Net Income** | Bottom line profit/loss |
| `DeferredIncomeTaxExpenseBenefit` | **Deferred Tax Expense** | Non-cash deferred tax portion |
| `DeferredTaxAssetsLiabilitiesNet` | **Deferred Tax Net** | Net deferred tax position |

---

## Balance Sheet Concepts

### Assets
| XBRL Concept | Standard Name | Description |
|--------------|---------------|-------------|
| `CashAndCashEquivalentsAtCarryingValue` | **Cash** | Cash and cash equivalents |
| `MarketableSecuritiesCurrent` | **Marketable Securities** | Short-term investments |
| `AvailableForSaleSecuritiesDebtSecurities` | **Debt Securities** | AFS debt securities |
| `PropertyPlantAndEquipmentNet` | **PP&E** | Net property, plant, equipment |
| `FiniteLivedIntangibleAssetsNet` | **Intangible Assets** | Amortizable intangibles |
| `OtherAssetsNoncurrent` | **Other Assets** | Other long-term assets |

### Liabilities
| XBRL Concept | Standard Name | Description |
|--------------|---------------|-------------|
| `AccruedLiabilitiesCurrent` | **Accrued Liabilities** | Current accrued expenses |
| `LongTermDebt` | **Long-Term Debt** | Total long-term debt |
| `LongTermDebtNoncurrent` | **LT Debt (Noncurrent)** | Non-current portion of LT debt |
| `DebtInstrumentCarryingAmount` | **Debt Carrying Amount** | Book value of debt |
| `OtherLiabilitiesNoncurrent` | **Other Liabilities** | Other long-term liabilities |

### Lease Liabilities
| XBRL Concept | Standard Name | Description |
|--------------|---------------|-------------|
| `OperatingLeaseLiability` | **Operating Lease Liability** | Total operating lease liability |
| `OperatingLeaseLiabilityCurrent` | **Operating Lease (Current)** | Current portion |
| `OperatingLeaseLiabilityNoncurrent` | **Operating Lease (LT)** | Non-current portion |
| `FinanceLeaseLiability` | **Finance Lease Liability** | Total finance lease liability |
| `LesseeOperatingLeaseLiabilityPaymentsDue` | **Operating Lease Payments** | Future lease payments due |
| `LesseeOperatingLeaseLiabilityUndiscountedExcessAmount` | **Lease Discount** | Discount on lease liability |
| `FinanceLeaseLiabilityPaymentsDue` | **Finance Lease Payments** | Future finance lease payments |

---

## Cash Flow Concepts

| XBRL Concept | Standard Name | Description |
|--------------|---------------|-------------|
| `NetIncomeLoss` | **Net Income** | Starting point for operating CF |
| `ShareBasedCompensation` | **Stock Comp** | Non-cash stock compensation expense |
| `CashAndCashEquivalentsAtCarryingValue` | **Ending Cash** | Cash balance reconciliation |

---

## Usage in Concept Mapping

These 27 concepts should be:
1. **Auto-mapped** with high confidence (no AI needed)
2. **Used as anchors** for hierarchical discovery
3. **Validated** by checking calculation math (parent = sum of children × weights)

---

## Notes

- TSLA's 10-K/A (amended filings) may have 0 calculation trees due to partial XBRL data
- Some concepts appear in multiple tree types (e.g., `NetIncomeLoss` in both income and cashflow)
- The very long `IncomeLossFromContinuingOperations...` is the standard PretaxIncome concept
