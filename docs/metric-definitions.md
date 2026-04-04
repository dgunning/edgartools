# Metric Definitions

Reference guide for all 37 standardized financial metrics extracted by EdgarTools, plus 6 derived metrics.

Each metric is mapped from company-specific XBRL concepts to a standardized name, validated against yfinance reference data. This document is the authoritative human-readable companion to the machine configs in `edgar/xbrl/standardization/config/`.

**Source files:**
- `config/metrics.yaml` -- XBRL concept lists, tree hints, sign conventions
- `config/data_dictionary.yaml` -- definitions, tiers, units
- `config/industry_metrics.yaml` -- industry exclusions and alternatives
- `reference_validator.py` -- yfinance field mappings

**Metric tiers:**
- **Headline** -- must achieve >= 99% extraction fidelity (subscription-grade critical)
- **Secondary** -- must achieve >= 95% extraction fidelity

---

## 1. Income Statement Metrics

### Revenue

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Total revenues from the sale of goods and services, net of returns and allowances. |
| **XBRL concepts** | `Revenues` (primary), `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`, `Revenue`, `TotalRevenues`, `NetSales`, `PremiumsEarnedNet`, `NetPremiumsEarned`, `PremiumsEarned`, `InsuranceServiceRevenue` |
| **yfinance field** | `Total Revenue` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Insurance companies use `PremiumsEarnedNet` instead of contract revenue concepts. Banking companies use `InterestAndNoninterestRevenue`. UNH (insurance) diverges from yfinance due to premium-based reporting. |

### COGS

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Direct costs attributable to the production of goods and services sold. |
| **XBRL concepts** | `CostOfGoodsAndServicesSold` (primary), `CostOfRevenue`, `CostOfGoodsSold`, `CostOfSales`, `CostOfServices`, `CrudeOilAndProductPurchases` |
| **yfinance field** | `Cost Of Revenue` (financials) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | Banking (SIC 6020-6099), Insurance (SIC 6300-6399), REITs (SIC 6500-6553, 6798) |
| **Known differences** | Services companies (META, FDX) may not have traditional COGS. Banks use `InterestExpense` as cost analog. Insurance uses `BenefitsLossesAndExpenses`. REITs use `RealEstateOperatingExpenses`. Energy uses `CrudeOilAndProductPurchases` or production cost concepts. |

### GrossProfit

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Revenue minus cost of goods sold. Measures profitability before operating expenses. |
| **XBRL concepts** | `GrossProfit` |
| **yfinance field** | `Gross Profit` (financials) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Composite formula** | Revenue - COGS (when direct tag unavailable) |
| **Industries excluded** | Banking (SIC 6020-6099), Insurance (SIC 6300-6399), Energy (SIC 1300-1389, 2911-2999) |
| **Known differences** | Banks use `NetInterestIncome` (InterestIncome - InterestExpense) instead. Not applicable to services companies or banks. Energy companies use cost structures that don't map to standard GrossProfit. |

### SGA

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Operating expenses for selling, general, and administrative activities. |
| **XBRL concepts** | `SellingGeneralAndAdministrativeExpense` (primary), `SellingAndMarketingExpense`, `GeneralAndAdministrativeExpense` |
| **yfinance field** | `Selling General And Administrative` (financials) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | None (but banks use `NoninterestExpense` as counterpart) |
| **Known differences** | Often split into separate selling and G&A line items in filings. Banking companies report `NoninterestExpense` instead. |

### ResearchAndDevelopment

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Expenses for research and development activities. |
| **XBRL concepts** | `ResearchAndDevelopmentExpense` (primary), `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost`, `ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost` |
| **yfinance field** | `Research And Development` (financials) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | Banking (SIC 6020-6099) |
| **Known differences** | Not all companies have R&D. Energy companies may use `ExplorationExpense` as analog. Tolerance: 20%. |

### OperatingIncome

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Income from core business operations, before interest and taxes. |
| **XBRL concepts** | `OperatingIncomeLoss` |
| **yfinance field** | `Total Operating Income As Reported` (financials), fallback: `Operating Income` |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | Energy (SIC 1300-1389, 2911-2999) uses industry-specific operating measures |
| **Known differences** | yfinance provides both a Yahoo-normalized value (`Operating Income`) and a GAAP value (`Total Operating Income As Reported`). For companies with significant special charges (e.g., KO with $2.3B impairments in 2024), Yahoo "normalizes" by adding back charges. EdgarTools uses the GAAP ("As Reported") field by default. Banks use PPNR (Pre-Provision Net Revenue). Insurance uses UnderwritingIncome. REITs use NOI (Net Operating Income). |

### InterestExpense

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cost of borrowing, including interest on debt obligations. |
| **XBRL concepts** | `InterestExpense` (primary), `InterestExpenseDebt`, `InterestAndDebtExpense` |
| **yfinance field** | `Interest Expense` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | For banks, InterestExpense replaces COGS as the "raw material cost" (interest paid to depositors). Tolerance: 25%. |

### IncomeTaxExpense

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Provision for income taxes, including current and deferred. |
| **XBRL concepts** | `IncomeTaxExpenseBenefit` (primary), `CurrentIncomeTaxExpenseBenefit` |
| **yfinance field** | `Tax Provision` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Can be negative (tax benefit) in loss years. Tolerance: 25%. |

### PretaxIncome

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Income before provision for income taxes. |
| **XBRL concepts** | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` (primary), `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`, `IncomeLossFromContinuingOperationsBeforeIncomeTaxes` |
| **yfinance field** | Not mapped (no yfinance validation) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Long XBRL concept names make this metric tricky to identify in filings. The "ExtraordinaryItems" and "MinorityInterest" variants are legacy taxonomy concepts still used by some filers. |

### NetIncome

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Total earnings after all expenses, taxes, and adjustments. Bottom line of the income statement. |
| **XBRL concepts** | `NetIncomeLoss` (primary), `ProfitLoss`, `NetIncome` |
| **yfinance field** | `Net Income` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | REITs prefer FFO (Funds From Operations) as their primary profitability metric, since depreciation is a phantom expense for real estate. `ProfitLoss` includes noncontrolling interest; `NetIncomeLoss` is attributable to the parent. |

---

## 2. Balance Sheet Metrics

### TotalAssets

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Sum of all current and non-current assets owned by the company. |
| **XBRL concepts** | `Assets` (primary), `TotalAssets` |
| **yfinance field** | `Total Assets` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | None significant. This is a root-level balance sheet item with high extraction reliability. |

### CurrentAssets

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Assets expected to be converted to cash or used within one year. |
| **XBRL concepts** | `AssetsCurrent` |
| **yfinance field** | `Current Assets` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | Banking (SIC 6020-6099) -- banks use liquidity-based balance sheets, not current/non-current classification |
| **Known differences** | Banks do not report current vs. non-current assets. Their balance sheets are organized by liquidity rather than maturity. |

### CashAndEquivalents

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cash on hand and short-term liquid investments readily convertible to cash. |
| **XBRL concepts** | `CashAndCashEquivalentsAtCarryingValue` (primary), `CashAndCashEquivalents`, `Cash`, `CashAndDueFromBanks`, plus several variant names (`CashCashEquivalentsAndShortTermInvestments`, `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`) |
| **yfinance field** | `Cash And Cash Equivalents` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None (but banks use different extraction strategy) |
| **Known differences** | Banks require a "street cash composite" strategy using `CashAndDueFromBanks`, `InterestBearingDepositsInBanks` (critical for custodial banks like BK, STT), and `CashAndSecuritiesSegregatedUnderFederalAndOtherRegulations` (GS regulatory). Some companies include short-term investments in their reported cash figure. |

### AccountsReceivable

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Amounts owed to the company by customers for goods or services delivered. |
| **XBRL concepts** | `AccountsReceivableNetCurrent` (primary), `ReceivablesNetCurrent`, `TradeAccountsReceivable`, `AccountsReceivableNet`, `AccountsNotesAndLoansReceivableNetCurrent`, `AccountsAndOtherReceivablesNetCurrent`, `NotesAndAccountsReceivableNet`, plus variant names |
| **yfinance field** | `Accounts Receivable` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | None explicitly, but diverges for companies with financial subsidiaries (e.g., CAT) |
| **Known differences** | Rising AR faster than revenue may signal quality issues. Companies with financial services subsidiaries (CAT, DE) may have complex receivable structures. Tolerance: 25%. |

### Inventory

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Raw materials, work-in-progress, and finished goods held for sale. |
| **XBRL concepts** | `InventoryNet` (primary), `Inventories`, `InventoryFinishedGoods` |
| **yfinance field** | `Inventory` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | Banking (SIC 6020-6099), Insurance (SIC 6300-6399) |
| **Known differences** | Not applicable to service companies (META, GOOG, etc.) or financial companies. |

### PropertyPlantEquipment

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Net book value of tangible long-lived assets used in operations. |
| **XBRL concepts** | `PropertyPlantAndEquipmentNet` (primary), `PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization` |
| **yfinance field** | `Net PPE` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | Banking (SIC 6020-6099) |
| **Known differences** | Not meaningful for banks/financial services. Some companies include finance lease right-of-use assets in their PP&E figure. Tolerance: 20%. |

### Goodwill

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Excess of acquisition cost over fair value of net identifiable assets acquired. |
| **XBRL concepts** | `Goodwill` |
| **yfinance field** | `Goodwill` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Exclude patterns** | `IncludingGoodwill`, `Impaired`, `Gross` |
| **Industries excluded** | None |
| **Known differences** | Exclude patterns prevent matching concepts like `GoodwillIncludingGoodwill` or impairment-related tags. |

### IntangibleAssets

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Goodwill and other intangible assets combined (matches yfinance definition). |
| **XBRL concepts** | `Goodwill`, `IntangibleAssetsNetExcludingGoodwill`, `IndefiniteLivedTrademarks`, `FiniteLivedIntangibleAssetsNet`, `IndefiniteLivedIntangibleAssetsExcludingGoodwill`, `OtherIntangibleAssetsNet` |
| **yfinance field** | `Goodwill And Other Intangible Assets` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Composite** | Yes -- sum of Goodwill + IntangibleAssetsNetExcludingGoodwill |
| **Industries excluded** | None |
| **Known differences** | This is a composite metric: yfinance reports Goodwill + Intangibles as a single figure. EdgarTools sums the components. KO uses `IndefiniteLivedTrademarks` instead of `IntangibleAssetsNetExcludingGoodwill`. Tolerance: 25%. |

### ShortTermDebt

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Short-term borrowings and current portion of long-term debt. |
| **XBRL concepts** | `DebtCurrent`, `ShortTermDebt`, `ShortTermDebtAndCapitalLeaseObligationsCurrent`, `LongTermDebtCurrent`, `CommercialPaper`, `ShortTermBorrowings`, `NotesPayable`, `CurrentPortionOfLongTermDebt`, `OtherShortTermBorrowings`, `ShortTermBankLoansAndNotesPayable` |
| **yfinance field** | `Current Debt` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Composite** | Yes -- sum of LongTermDebtCurrent + CommercialPaper + ShortTermBorrowings |
| **Dimensional handling** | Includes dimensional facts |
| **Industries excluded** | None explicitly, but banks use a "wholesale funding composite" strategy |
| **Known differences** | yfinance "Current Debt" sums multiple short-term debt types. For banks, extraction uses a strict component summation strategy (CommercialPaper + OtherShortTermBorrowings + FederalHomeLoanBankAdvancesCurrent + SecuritiesSoldUnderAgreementsToRepurchase) to avoid double-counting. Companies with financial subsidiaries (CAT, DE) may show significant variance. |

### LongTermDebt

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Debt obligations due after one year (non-current portion). |
| **XBRL concepts** | `LongTermDebtNoncurrent` (preferred), `LongTermDebt`, `LongTermDebtAndCapitalLeaseObligations` |
| **yfinance field** | `Long Term Debt` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | `LongTermDebtNoncurrent` is preferred because it excludes the current portion. `LongTermDebt` may include the current portion in some filings, causing double-counting with ShortTermDebt. Companies with financial subsidiaries may show divergence. |

### AccountsPayable

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Amounts owed to suppliers for goods and services received. |
| **XBRL concepts** | `AccountsPayableCurrent` (primary), `AccountsPayableTradeCurrent`, `TradeAndOtherPayablesCurrent`, `AccountsPayableAndAccruedLiabilitiesCurrent`, `AccountsPayableAndAccruedLiabilities` |
| **yfinance field** | `Accounts Payable` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Exclude patterns** | `Liabilities` (to avoid matching combined AP + accrued liabilities line items) |
| **Industries excluded** | None |
| **Known differences** | High AP indicates supplier leverage. The exclude pattern for "Liabilities" prevents matching the combined `AccountsPayableAndAccruedLiabilities` concept when the pure AP tag is available. |

### CurrentLiabilities

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Obligations due within one year. |
| **XBRL concepts** | `LiabilitiesCurrent` |
| **yfinance field** | `Current Liabilities` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | Banking (SIC 6020-6099) -- banks use liquidity-based balance sheets, not current/non-current classification |
| **Known differences** | Banks do not report current vs. non-current liabilities. |

### TotalLiabilities

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Sum of all current and non-current obligations. |
| **XBRL concepts** | `Liabilities` |
| **yfinance field** | `Total Liabilities Net Minority Interest` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | yfinance uses the field name "Total Liabilities Net Minority Interest" which excludes noncontrolling interest portions of liabilities. |

### StockholdersEquity

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Total equity attributable to shareholders (assets minus liabilities). |
| **XBRL concepts** | `StockholdersEquity` (primary), `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`, `Equity` |
| **yfinance field** | `Stockholders Equity` (balance_sheet) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | The `IncludingPortionAttributableToNoncontrollingInterest` variant includes minority interest, which may differ from the yfinance figure that typically shows parent-only equity. |

### RetainedEarnings

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cumulative net income retained in the company rather than paid as dividends. |
| **XBRL concepts** | `RetainedEarningsAccumulatedDeficit` |
| **yfinance field** | `Retained Earnings` (balance_sheet) |
| **Sign convention** | Varies (can be negative for accumulated deficit) |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Can be significantly negative for companies with large accumulated deficits (e.g., growth companies). Tolerance: 20%. |

---

## 3. Cash Flow Statement Metrics

### OperatingCashFlow

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Net cash provided by operating activities. |
| **XBRL concepts** | `NetCashProvidedByUsedInOperatingActivities` |
| **yfinance field** | `Operating Cash Flow` (cashflow) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | None significant. This is a standard cash flow statement total line. |

### Capex

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cash spent on purchasing or improving long-term assets, including intangibles. |
| **XBRL concepts** | `PaymentsToAcquirePropertyPlantAndEquipment` (primary), `PaymentsToAcquireProductiveAssets`, `PaymentsToAcquireIntangibleAssets`, `PaymentsToDevelopSoftware`, `PaymentsToAcquireOilAndGasPropertyAndEquipment`, `PaymentsToAcquireOtherPropertyPlantAndEquipment`, `PaymentsForCapitalImprovements`, `CapitalExpenditures`, plus variant names |
| **yfinance field** | `Capital Expenditure` (cashflow) |
| **Sign convention** | Negated (reported as negative in cash flow, stored as positive) |
| **Universal** | No |
| **Exclude patterns** | `Businesses`, `Acquisitions`, `NetOfCash`, `InvestmentsInAffiliates` |
| **Industries excluded** | Banking (SIC 6020-6099) |
| **Known differences** | Includes intangible investments for pharma/tech companies. Energy sector uses `PaymentsToAcquireProductiveAssets`. Excludes M&A acquisitions via exclude patterns. Some companies' XBRL data captures acquisitions instead of organic capex, causing large divergence from yfinance. Tolerance: 40% (highest of all metrics due to definitional variation). |

### DepreciationAmortization

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Non-cash charges for depreciation of tangible assets and amortization of intangible assets. |
| **XBRL concepts** | `DepreciationDepletionAndAmortization` (primary), `DepreciationAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `Depreciation`, `DepreciationAmortizationAndOther`, `AmortizationOfIntangibleAssets`, `DepreciationNonproduction`, plus variant names |
| **yfinance field** | `Depreciation And Amortization` (cashflow) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Composite** | Yes -- sum of Depreciation + AmortizationOfIntangibleAssets when split |
| **Exclude patterns** | `Accumulated` |
| **Industries excluded** | None |
| **Known differences** | Required for EBITDA calculation. Pharma/medical companies often split into separate Depreciation + AmortizationOfIntangibleAssets line items, requiring composite summation. The "Accumulated" exclude pattern prevents matching the balance sheet accumulated depreciation concept. Tolerance: 30%. |

### StockBasedCompensation

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Non-cash expense for equity-based employee compensation. |
| **XBRL concepts** | `ShareBasedCompensation` (primary), `AllocatedShareBasedCompensationExpense`, `StockCompensationExpense`, `StockBasedCompensationNet`, `ShareBasedCompensationIncludingDiscontinuedOperations` |
| **yfinance field** | `Stock Based Compensation` (cashflow) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | None |
| **Known differences** | Critical for calculating "Real" Free Cash Flow (FCF - SBC). Typically reported as an add-back in the operating section of the cash flow statement. Tolerance: 20%. |

### DividendsPaid

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cash dividends paid to shareholders. |
| **XBRL concepts** | `PaymentsOfDividends` (primary), `PaymentsOfDividendsCommonStock`, `DividendsPaidCommonStock` |
| **yfinance field** | `Cash Dividends Paid` (cashflow) |
| **Sign convention** | Negated (reported as negative in financing section, stored as positive) |
| **Universal** | No |
| **Industries excluded** | None |
| **Known differences** | For total shareholder return and payout ratio analysis. Growth companies typically have zero dividends. |

### InvestingCashFlow

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Net cash used in or provided by investing activities. |
| **XBRL concepts** | `NetCashProvidedByUsedInInvestingActivities` (primary), `NetCashProvidedByUsedInInvestingActivitiesContinuingOperations` |
| **yfinance field** | `Investing Cash Flow` (cashflow) |
| **Sign convention** | Varies (typically negative for growing companies) |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Tolerance: 25%. The "ContinuingOperations" variant excludes discontinued operations, which may cause small differences from yfinance. |

### FinancingCashFlow

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Net cash used in or provided by financing activities. |
| **XBRL concepts** | `NetCashProvidedByUsedInFinancingActivities` (primary), `NetCashProvidedByUsedInFinancingActivitiesContinuingOperations` |
| **yfinance field** | `Financing Cash Flow` (cashflow) |
| **Sign convention** | Varies (typically negative for companies returning capital) |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Tolerance: 25%. |

### ShareRepurchases

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cash used to buy back company shares (treasury stock). |
| **XBRL concepts** | `PaymentsForRepurchaseOfCommonStock` (primary), `PaymentsForRepurchaseOfEquity`, `StockRepurchasedAndRetiredDuringPeriodValue` |
| **yfinance field** | `Repurchase Of Capital Stock` (cashflow) |
| **Sign convention** | Negated (reported as negative in financing section, stored as positive) |
| **Universal** | No |
| **Industries excluded** | None |
| **Known differences** | Tolerance: 25%. Some companies report repurchases through retirement rather than treasury stock, using the `StockRepurchasedAndRetiredDuringPeriodValue` concept. |

---

## 4. Per-Share Metrics

### EarningsPerShareDiluted

| Field | Value |
|-------|-------|
| **Tier** | Headline |
| **Definition** | Net income divided by weighted average diluted shares outstanding. |
| **XBRL concepts** | `EarningsPerShareDiluted` |
| **yfinance field** | `Diluted EPS` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Banking companies may report differently. Stock splits can cause historical divergence if XBRL reports pre-split values while yfinance adjusts retroactively (e.g., NVDA 10-for-1 split). Tolerance: 15%. |

### EarningsPerShareBasic

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Net income divided by weighted average shares outstanding (basic, no dilution). |
| **XBRL concepts** | `EarningsPerShareBasic` |
| **yfinance field** | `Basic EPS` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Same stock split considerations as diluted EPS. Tolerance: 15%. |

### WeightedAverageSharesDiluted

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Weighted average number of diluted shares outstanding during the period. |
| **XBRL concepts** | `WeightedAverageNumberOfDilutedSharesOutstanding` (primary), `WeightedAverageNumberOfSharesOutstandingDiluted`, `WeightedAverageNumberOfShareOutstandingBasicAndDiluted` |
| **yfinance field** | `Diluted Average Shares` (financials) |
| **Sign convention** | Positive |
| **Universal** | Yes |
| **Industries excluded** | None |
| **Known differences** | Essential for per-share valuation metrics. Stock splits cause known structural divergence (XBRL pre-split vs. yfinance post-split adjusted) -- this is a `wont_fix` divergence category. Tolerance: 15%. |

### DividendPerShare

| Field | Value |
|-------|-------|
| **Tier** | Secondary |
| **Definition** | Cash dividends declared per common share. |
| **XBRL concepts** | `CommonStockDividendsPerShareDeclared` (primary), `CommonStockDividendsPerShareCashPaid` |
| **yfinance field** | Not mapped (no yfinance validation) |
| **Sign convention** | Positive |
| **Universal** | No |
| **Industries excluded** | None |
| **Known differences** | Tolerance: 15%. Only applicable to dividend-paying companies. |

---

## 5. Derived Metrics

These metrics are computed from extracted metrics, not extracted directly from XBRL.

### FreeCashFlow

| Field | Value |
|-------|-------|
| **Formula** | OperatingCashFlow - Capex |
| **Requires** | OperatingCashFlow, Capex |
| **Notes** | The most commonly cited measure of cash generation. Subtract StockBasedCompensation for "Real FCF." |

### EBITDA

| Field | Value |
|-------|-------|
| **Formula** | OperatingIncome + DepreciationAmortization |
| **Requires** | OperatingIncome, DepreciationAmortization |
| **Notes** | Proxy for operating cash flow before working capital changes. Widely used for enterprise valuation (EV/EBITDA). |

### NetDebt

| Field | Value |
|-------|-------|
| **Formula** | ShortTermDebt + LongTermDebt - CashAndEquivalents |
| **Requires** | ShortTermDebt, LongTermDebt, CashAndEquivalents |
| **Notes** | Used for enterprise value calculation (Market Cap + Net Debt). Negative value indicates net cash position. |

### TotalDebt

| Field | Value |
|-------|-------|
| **Formula** | ShortTermDebt + LongTermDebt |
| **Requires** | ShortTermDebt, LongTermDebt |
| **Notes** | Total interest-bearing debt obligations. |

### TangibleAssets

| Field | Value |
|-------|-------|
| **Formula** | TotalAssets - Goodwill - IntangibleAssets |
| **Requires** | TotalAssets, Goodwill, IntangibleAssets |
| **Notes** | Useful for tangible book value calculations and asset-heavy business analysis. |

### WorkingCapital

| Field | Value |
|-------|-------|
| **Formula** | CurrentAssets - CurrentLiabilities |
| **Requires** | CurrentAssets, CurrentLiabilities |
| **Notes** | Measure of short-term liquidity. Not applicable to banks (which don't report current/non-current classification). |

---

## 6. Industry Exclusion Summary

The following table summarizes which metrics are excluded (forbidden) by industry.

| Metric | Banking | Insurance | REITs | Energy |
|--------|---------|-----------|-------|--------|
| COGS | Excluded | Excluded | Excluded | -- |
| GrossProfit | Excluded | Excluded | -- | Excluded |
| Inventory | Excluded | Excluded | -- | -- |
| Capex | Excluded | -- | -- | -- |
| PropertyPlantEquipment | Excluded | -- | -- | -- |
| ResearchAndDevelopment | Excluded | -- | -- | -- |
| CurrentAssets | Excluded | -- | -- | -- |
| CurrentLiabilities | Excluded | -- | -- | -- |
| OperatingIncome | -- | -- | -- | Excluded |

**Industry SIC ranges:**
- Banking: SIC 6020-6099
- Insurance: SIC 6300-6399
- REITs: SIC 6500-6553, 6798
- Energy: SIC 1300-1389, 2911-2999

**Industry-specific alternatives:**

| Standard Metric | Banking Alternative | Insurance Alternative | REIT Alternative | Energy Alternative |
|----------------|--------------------|-----------------------|------------------|--------------------|
| COGS | InterestExpense | LossesAndAdjustments | PropertyOperatingExpenses | ProductionCosts |
| GrossProfit | NetInterestIncome | -- | -- | -- |
| OperatingIncome | PPNR | UnderwritingIncome | NOI | -- |
| SGA | NoninterestExpense | -- | -- | -- |
| NetIncome | -- | -- | FFO | -- |
| R&D | -- | -- | -- | ExplorationExpense |

---

## 7. Validation Tolerances

Each metric has a validation tolerance (percentage) used when comparing extracted XBRL values against yfinance reference data. The default tolerance is 15%.

| Tolerance | Metrics |
|-----------|---------|
| **15% (default)** | Revenue, COGS, SGA, OperatingIncome, NetIncome, OperatingCashFlow, TotalAssets, Goodwill, LongTermDebt, CashAndEquivalents, GrossProfit, CurrentAssets, CurrentLiabilities, TotalLiabilities, StockholdersEquity, WeightedAverageSharesDiluted, EarningsPerShareDiluted, EarningsPerShareBasic, DividendPerShare |
| **20%** | ResearchAndDevelopment, StockBasedCompensation, PropertyPlantEquipment, RetainedEarnings |
| **25%** | InterestExpense, IncomeTaxExpense, AccountsReceivable, IntangibleAssets, InvestingCashFlow, FinancingCashFlow, ShareRepurchases |
| **30%** | DepreciationAmortization |
| **40%** | Capex |

---

## 8. Sign Conventions

Most metrics are stored as positive values. The following metrics use sign negation (the raw XBRL value is negative but we store the absolute value):

| Metric | Raw XBRL Sign | Stored Sign | Reason |
|--------|---------------|-------------|--------|
| Capex | Negative (cash outflow) | Positive | Convention for easier FCF calculation |
| DividendsPaid | Negative (cash outflow) | Positive | Convention for payout ratio analysis |
| ShareRepurchases | Negative (cash outflow) | Positive | Convention for total return analysis |

Metrics with "varies" sign convention (can be positive or negative depending on period):
- RetainedEarnings (accumulated deficit when negative)
- InvestingCashFlow (negative when investing, positive on divestitures)
- FinancingCashFlow (negative when returning capital, positive when raising)
