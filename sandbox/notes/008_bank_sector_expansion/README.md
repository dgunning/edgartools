# Bank Sector Expansion - Knowledge Base

## Objective
Document the test results, architectural patterns, and idiosyncrasies of different banking archetypes to inform future feature development.

## Bank Archetypes & Test Cohort

| Archetype | Description | Tickers | Key Specifics |
|-----------|-------------|---------|---------------|
| **Commercial Mega Banks** | Traditional deposit/lending + weak investment arm | **JPM, BAC, WFC, C** | `ShortTermBorrowings` often grossed up. High `InterestBearingDeposits` |
| **Investment Banks** | Market makers, heavy trading | **GS, MS** | "Trading Liabilities" mix shorts & debt. Small deposit base. |
| **Regional Banks** | Pure commercial banking | **USB, PNC, TFC** | Simpler balance sheets. Debt often just FHLB advances + Repos. |
| **Custody Banks** | Asset servicing, low credit risk | **BK, STT** | Huge off-balance sheet assets. Low loan-to-deposit ratios. |

## Key Metrics Under Test

1.  **ShortTermDebt**: Testing "3-Path Strategy" (Direct vs Net vs Component).
2.  **CashAndEquivalents**: Testing "<1% Asset" guardrail on restricted cash.
3.  **OperatingIncome**: Validating PPNR (Pre-Provision) vs Post-Provision models against Street consensus.

## Learnings log
*To be updated as Sprint 4 progresses*

### 2026-01-21: Income Statement Convention (JPM)
*   **Hypothesis:** Does `yfinance` "Operating Income" represent PPNR (Pre-Provision) or Post-Provision Profit?
*   **Result:** **Post-Provision**.
*   **Evidence:** JPM test passed with 0 failures using logic: `(NII + NonIntInc - NonIntExp) - ProvisionForCreditLosses`.
*   **Decision:** Default `OperatingIncome` for all banks will be **Post-Provision**. PPNR will be logged as an intermediate calculation.

### 2026-01-21: Expansion Covenant (GS, MS, USB, PNC, BK, STT)
*   **Objective:** Stress-test the "3-Path Strategy" for Debt and new Income Statement logic against non-commercial bank archetypes.
*   **Result:** **PASS (0 Failures)** across all 6 new tickers.
*   **Key Insight 1 (Investment Banks):** GS/MS "ShortTermDebt" extraction succeeded without needing a special "Trading Liabilities" deduction path, suggesting the generic "Path B (Net Construction)" or "Path C (Component Sum)" is robust enough to handle their "Financial Instruments Sold" nuances (likely by ignoring them as they don't map to standard debt tags).
*   **Key Insight 2 (Regional/Custody):** The simpler balance sheets of USB/PNC and the asset-heavy nature of BK/STT did not trigger false positives in the "Identity Check" or the "Cash < 1%" guardrail.
*   **Conclusion:** The `BankingExtractor` is now suitable for broad deployment across the S&P 500 Financials sector.
