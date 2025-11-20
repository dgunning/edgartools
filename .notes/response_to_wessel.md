# Response to Wessel - LinkedIn Message

## Context
User reached out via LinkedIn about using edgartools for financial modeling. Trying to extract:
- Revenue ✓
- Operating Income ✓
- Total Assets ✗ (harder)
- Short-term Debt ✗ (harder)

For graphing and ratio analysis over time.

Created Beads issue: **edgartools-bly** (P2) to track UX improvement.

---

## Draft Response

Hi Wessel,

Thank you so much for reaching out and for the detailed feedback about your workflow! This is exactly the kind of real-world use case that helps make edgartools better.

You've identified a genuine gap in the API. You're right that **revenue and operating income work well** (income statement items are more standardized), but **balance sheet items like total assets and short-term debt are harder** because the current API requires knowing exact XBRL concept names and manual DataFrame wrangling.

**Here's the best current approach for your workflow:**

```python
from edgar import Company
import pandas as pd

company = Company("AAPL")
facts = company.get_facts()

# Get the statements
inc = facts.income_statement()
bs = facts.balance_sheet()

# Extract metrics using find_item() - returns time series as dict
revenue_item = inc.find_item('Revenues')
op_income_item = inc.find_item('OperatingIncomeLoss')
assets_item = bs.find_item('Assets')

# Combine into DataFrame for your model
model_data = pd.DataFrame({
    'revenue': revenue_item.values if revenue_item else None,
    'operating_income': op_income_item.values if op_income_item else None,
    'total_assets': assets_item.values if assets_item else None,
})

# Now you can graph and calculate ratios
model_data.plot()
model_data['asset_turnover'] = model_data['revenue'] / model_data['total_assets']
```

**For short-term debt**, you'll need to search for the right concept name (it varies by company):

```python
# See what's available
bs_df = bs.to_dataframe()
debt_concepts = bs_df[bs_df['label'].str.contains('debt|borrowing', case=False, na=False)]
print(debt_concepts[['label']].head(10))

# Then use the concept you need
short_term_debt_item = bs.find_item('DebtCurrent')  # or 'ShortTermBorrowings'
```

**That said**, I completely agree this workflow should be simpler. Based on your feedback, I've created a tracking issue to design a more intuitive API that supports financial modeling workflows directly—where you can request multiple metrics and get back a clean time-series DataFrame without needing XBRL expertise.

The Company Facts API you discovered is indeed the right data source (it's what `get_facts()` uses internally), and it gives you the longest available time series. The challenge is just making it easier to extract and combine multiple metrics.

Really appreciate you taking the time to share this—please keep the feedback coming! Would love to hear how your model turns out.

Best regards,
Dwight

---

## Key Points
- ✓ Acknowledges the problem honestly
- ✓ Validates his experience (income statement easy, balance sheet hard)
- ✓ Provides best current workaround with working code
- ✓ Shows we're taking action (created issue edgartools-bly)
- ✓ Keeps dialogue open for future feedback

---

## IMPORTANT FOLLOW-UP (2025-11-09)

Wessel clarified the real problem:
- ✓ Standard metrics (Revenue, Total Assets, Operating Income) - **HE GOT THESE WORKING**
- ✗ Non-standard items (Short-term Debt, D&A, etc.) - **THESE ARE THE PROBLEM**

The challenge is:
1. Non-standard items have highly variable concept names
2. They're deeper in statement hierarchies
3. May not exist for all companies (e.g., Apple/Microsoft don't report short-term debt)
4. Require DataFrame + string search + manual extraction

Updated research document with follow-up section:
`docs-internal/research/codebase/2025-11-09-entity-facts-time-series-api.md`

This changes the solution from "multi-metric time series API" to "fuzzy search + extraction for non-standard line items".
