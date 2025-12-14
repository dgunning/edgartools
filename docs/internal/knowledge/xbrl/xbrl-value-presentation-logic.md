# XBRL Value Presentation Logic: Understanding Negation

**Date**: 2025-01-20
**Context**: Issue #463 - XBRL value transformations and presentation logic
**Purpose**: Document how EdgarTools determines when to negate values for display to match SEC HTML filings

---

## The Core Problem

XBRL separates **semantic meaning** (how a value is stored) from **presentation** (how it's displayed):

- **Instance Document**: Contains the raw numeric value with its semantic meaning
- **Presentation Linkbase**: Specifies how that value should be displayed in financial statements

### Example: Dividend Payments

```
Instance Document:     12,769,000,000  (positive number)
Presentation Linkbase: negatedLabel    (instruction to negate for display)
Rendered Output:       $(12,769)       (displayed in parentheses)
```

**Why?** The XBRL concept `us-gaap:PaymentsOfDividends` has a natural positive value (representing the absolute amount paid), but in financial statements, cash outflows are conventionally shown in parentheses.

---

## XBRL Metadata Affecting Presentation

### 1. **Balance Attribute** (Schema-level)

**Source**: Element definition in XBRL taxonomy schema
**Values**: `debit`, `credit`, or `None`
**Purpose**: Indicates the natural accounting balance of a concept

```xml
<element name="PaymentsOfDividends"
         type="xbrli:monetaryItemType"
         substitutionGroup="xbrli:item"
         xbrli:balance="credit"/>
```

**Examples**:
- `Assets` → `balance="debit"` (increases with debits)
- `Liabilities` → `balance="credit"` (increases with credits)
- `Revenue` → `balance="credit"` (increases with credits)
- `Expenses` → `balance="debit"` (increases with debits)
- `PaymentsOfDividends` → `balance="credit"` (cash outflow)

**Important**: The `balance` attribute is for **semantic classification**, NOT for determining presentation sign.

---

### 2. **Calculation Weight** (Calculation Linkbase)

**Source**: Calculation relationships in calculation linkbase
**Values**: `+1.0`, `-1.0`, or other numeric weights
**Purpose**: Specifies how child elements contribute to parent totals

```xml
<calculationArc
    from="NetCashFromFinancingActivities"
    to="PaymentsOfDividends"
    order="1.0"
    weight="-1.0"/>
```

**Example**:
```
Net Cash from Financing = Proceeds from Debt (+1.0)
                         + Payments of Dividends (-1.0)
                         + Repurchases of Stock (-1.0)
```

**Important**: Calculation weight is for **formulas and validation**, NOT for presentation.

---

### 3. **Preferred Label** (Presentation Linkbase) ⭐

**Source**: Presentation relationships in presentation linkbase
**Values**: XBRL label role URIs
**Purpose**: Specifies which label to use AND whether to negate for display

```xml
<presentationArc
    from="FinancingActivitiesAbstract"
    to="PaymentsOfDividends"
    preferredLabel="http://www.xbrl.org/2003/role/negatedLabel"
    order="2.0"/>
```

**Common Label Roles**:

| Label Role | Display Behavior | Use Case |
|------------|------------------|----------|
| `label` | Show as-is | Standard display |
| `terseLabel` | Show as-is | Shortened label |
| `verboseLabel` | Show as-is | Detailed label |
| **`negatedLabel`** | **Negate value** | **Cash outflows, expenses** |
| **`negatedTerseLabel`** | **Negate value** | **Shortened negated label** |

**This is the authoritative source for presentation logic.**

---

## The Negated Label Mechanism

### Official XBRL Guidance

From XBRL.org and SEC documentation:

> **"If the value reported in the HTML document is shown in parenthesis (e.g., interest expense or loss on disposition of assets), you may use a negated label to present the value in parenthesis in the SEC Interactive Data viewer without changing the positive value reported in the XBRL document."**

> **"When a negate label is applied, SEC viewer flips and renders the sign of the value tagged in XBRL instance document."**

### How It Works

1. **Filer enters raw value**: Based on element definition and balance attribute
   ```
   PaymentsOfDividends = 12,769,000,000 (positive)
   ```

2. **Filer sets presentation label**: Based on how it should appear in statements
   ```
   preferredLabel = "http://www.xbrl.org/2003/role/negatedLabel"
   ```

3. **SEC Viewer renders**: Applies negation transformation
   ```
   Display value = 12,769,000,000 × (-1) = -12,769,000,000
   Formatted as: $(12,769)
   ```

---

## EdgarTools Implementation

### Our Presentation Logic (statements.py & rendering.py)

```python
# In _generate_line_items() (xbrl.py:720-732)
preferred_sign_value = None
if node.preferred_label:
    label_lower = node.preferred_label.lower()
    is_negated = 'negated' in label_lower and (
        label_lower.startswith('negated') or  # Short form
        '/role/negated' in label_lower        # Full URI
    )
    preferred_sign_value = -1 if is_negated else 1
```

**Translation**:
- `negatedLabel` or `negatedTerseLabel` → `preferred_sign = -1`
- Any other label (terseLabel, label, etc.) → `preferred_sign = 1`
- No preferred label → `preferred_sign = None`

### Rendering Logic (rendering.py:1072-1086)

```python
# Apply presentation logic for display (Issue #463)
if value_type in (int, float) and period_key:
    statement_type = item.get('statement_type')

    # For Income Statement and Cash Flow Statement: Use preferred_sign
    if statement_type in ('IncomeStatement', 'CashFlowStatement'):
        preferred_sign = item.get('preferred_signs', {}).get(period_key)
        if preferred_sign is not None and preferred_sign != 0:
            value = value * preferred_sign  # Apply transformation
```

### DataFrame Presentation Mode (statements.py:386-404)

```python
def _apply_presentation(self, df: pd.DataFrame) -> pd.DataFrame:
    """Apply presentation logic to match SEC HTML display."""

    # For Income Statement and Cash Flow Statement: Use preferred_sign
    if statement_type in ('IncomeStatement', 'CashFlowStatement'):
        if 'preferred_sign' in result.columns:
            for col in period_cols:
                # Apply preferred_sign where it's not None and not 0
                mask = result['preferred_sign'].notna() & (result['preferred_sign'] != 0)
                result.loc[mask, col] = result.loc[mask, col] * result.loc[mask, 'preferred_sign']
```

---

## Real-World Examples

### Example 1: Apple 2024 10-K (Modern Filing)

**Cash Flow Statement - Financing Activities**:

| Concept | Raw Value | Balance | Preferred Label | Preferred Sign | Display |
|---------|-----------|---------|-----------------|----------------|---------|
| `PaymentsOfDividends` | 15,234,000,000 | credit | negatedLabel | -1 | $(15,234) |
| `RepurchasesOfCommonStock` | 94,949,000,000 | credit | negatedLabel | -1 | $(94,949) |
| `ProceedsFromIssuanceOfLongTermDebt` | 5,228,000,000 | credit | terseLabel | 1 | $5,228 |

**Result**: ✅ Perfect match with SEC HTML

---

### Example 2: Apple 2017 10-K (Older Filing)

**Cash Flow Statement - Financing Activities**:

| Concept | Raw Value | Balance | Preferred Label | Preferred Sign | Display (Our Logic) |
|---------|-----------|---------|-----------------|----------------|---------------------|
| `PaymentsOfDividends` | 12,769,000,000 | credit | **terseLabel** | **1** | **$12,769** |

**Expected from SEC HTML**: $(12,769) _(in parentheses)_
**Our Rendering**: $12,769 _(positive)_

**Why the difference?**

The 2017 filing uses `terseLabel` instead of `negatedLabel`. According to XBRL spec, this should display positive. If SEC HTML shows parentheses, it suggests:

1. **Historical SEC Viewer Logic**: Pre-2020 SEC viewer may have used fallback logic (e.g., `balance='credit'` in Cash Flow → show in parentheses)
2. **Filing Error**: The 2017 filing may have incorrect XBRL metadata
3. **Evolution of Standards**: Best practices evolved between 2017 and 2024

---

## Why We Follow preferredLabel (Not Balance)

### Authoritative Source

From XBRL guidance:
> **"Filers can change whether the amount is rendered within brackets by negating the label in the label linkbase."**

The `preferredLabel` is the **explicit presentation instruction** from the filer.

### Why Not Use Balance Attribute?

**Balance is semantic, not presentational**:

```
Concept: NetIncome
Balance: credit (accounting classification)
Preferred Label: terseLabel (show as-is, positive)
Display: $93,736 (positive)

Concept: PaymentsOfDividends
Balance: credit (accounting classification)
Preferred Label: negatedLabel (negate for display)
Display: $(15,234) (negative)
```

Both have `balance='credit'`, but **different presentation** based on `preferredLabel`.

**If we used balance for presentation logic**, we would incorrectly negate Net Income in Cash Flow statements.

---

## Edge Cases and Considerations

### 1. **No Preferred Label** (preferred_sign = None)

Some concepts may not have a `preferredLabel` specified:
- **Our behavior**: Show as-is (no transformation)
- **Fallback**: Could consider using balance attribute, but this risks errors

### 2. **Statement Type Matters**

We only apply `preferred_sign` logic for:
- Income Statement
- Cash Flow Statement

**Balance Sheet**: No transformation (assets/liabilities always shown with natural signs)

### 3. **Period-Specific Signs**

`preferred_sign` is **period-specific** because the same concept can appear in different contexts:

```python
preferred_signs: {
    'duration_2023-10-01_2024-09-28': -1,
    'duration_2022-09-25_2023-09-30': -1,
    'duration_2021-09-26_2022-09-24': -1
}
```

Each period gets its own sign based on the presentation arc for that period.

### 4. **Cross-Filing Consistency**

Different companies may use different `preferredLabel` choices for the same concept:
- **With `presentation=True`**: Show exactly as filer intended (may vary)
- **With `normalize=True`**: Apply consistent sign rules for analysis (all dividends positive)

---

## API Examples

### Default: Raw Values (No Transformation)

```python
df = statement.to_dataframe()

# Returns raw instance values
# PaymentsOfDividends: 15,234,000,000 (positive from XML)
```

### Presentation Mode: Match SEC HTML

```python
df = statement.to_dataframe(presentation=True)

# Applies preferred_sign transformation
# PaymentsOfDividends (with negatedLabel): -15,234,000,000 (negative for display)
```

### Normalization Mode: Cross-Company Analysis

```python
df = statement.to_dataframe(normalize=True)

# Applies semantic normalization (balance-based + pattern matching)
# PaymentsOfDividends: 15,234,000,000 (positive for analysis)
```

### Rich Display (Always Uses Presentation)

```python
print(statement)  # or statement.render()

# Always applies preferred_sign for display
# Shows: $(15,234) for negated items
```

---

## Design Decisions

### Why We Use preferredLabel Only

1. **Spec Compliance**: XBRL standard explicitly uses `preferredLabel` for presentation
2. **Filer Intent**: Companies explicitly choose negatedLabel when they want parentheses
3. **Modern Filings**: 2024+ filings use `negatedLabel` correctly
4. **Separation of Concerns**: Balance is semantic; preferredLabel is presentational

### Why Not Add Balance Fallback Logic?

**Pros of adding balance fallback**:
- Might match older SEC HTML renderings (pre-2020)
- Could handle filings with missing `preferredLabel`

**Cons of adding balance fallback**:
- Would violate XBRL spec (balance ≠ presentation)
- Risk of incorrect negation (e.g., Net Income in Cash Flow)
- Modern filings don't need it (they use proper labels)
- Adds complexity and ambiguity

**Decision**: Follow the spec. Trust filers to use `negatedLabel` correctly.

---

## Testing Strategy

### Test Coverage (test_issue_463_value_transformations.py)

1. **Metadata Availability**: Verify `preferred_sign` column exists in DataFrame
2. **Raw Values**: Confirm default returns positive instance values
3. **Presentation Mode**: Test `presentation=True` negates when `preferred_sign=-1`
4. **Normalization Mode**: Test `normalize=True` makes dividends consistently positive
5. **Rich Display**: Verify `print(statement)` applies presentation logic
6. **Cross-Filing**: Compare same period across different filings

### Test Data

- **2024 AAPL 10-K**: Modern filing with proper `negatedLabel` usage
- **2017 AAPL 10-K**: Older filing with `terseLabel` (edge case)
- **2016 AAPL 10-K**: Custom concepts with semantic matching

---

## Future Considerations

### 1. **Balance Attribute Fallback** (Optional)

If users report widespread issues with older filings, we could add:

```python
# Fallback logic (NOT currently implemented)
if preferred_sign is None and statement_type == 'CashFlowStatement':
    if balance == 'credit' and concept_matches_outflow_pattern(concept):
        preferred_sign = -1  # Treat as negated
```

**Trigger**: Only if we see consistent user complaints about pre-2020 filings.

### 2. **Historical Rendering Mode**

Add a flag to mimic older SEC viewer behavior:

```python
df = statement.to_dataframe(presentation=True, legacy_mode=True)
# Uses balance attribute fallback for older filings
```

### 3. **Validation Warnings**

Detect potential XBRL metadata issues:

```python
# Warn if Cash Flow outflow has balance='credit' but no negatedLabel
if balance == 'credit' and preferred_label != 'negatedLabel':
    log.warning(f"Potential presentation issue: {concept} may need negatedLabel")
```

---

## Summary

**Current Implementation**:
- ✅ Uses `preferredLabel` (negatedLabel vs. terseLabel) to determine presentation
- ✅ Applies `preferred_sign` transformation for Income/Cash Flow statements
- ✅ Matches modern SEC filings (2024+ AAPL perfectly)
- ✅ Follows XBRL specification correctly
- ⚠️ May differ from older SEC HTML (pre-2020) for filings without proper negatedLabel

**Key Principle**:
> **We render values as the filer explicitly instructed via `preferredLabel`, not based on accounting assumptions (balance attribute).**

This approach prioritizes **specification compliance** and **modern filing accuracy** over backward compatibility with potentially inconsistent older renderings.

---

## References

- XBRL.org: [Positive and Negative Values in XBRL](https://www.xbrl.org/guidance/positive-and-negative-values/)
- XBRL US: [Negated Labels: Getting XBRL Right](https://xbrlusa.wordpress.com/2011/02/12/negated-labels-getting-xbrl-right/)
- SEC: EDGAR XBRL Guide (Section 7.12 - Cash Flow Statements)
- Issue #463: [XBRL Value Transformations](https://github.com/dgunning/edgartools/issues/463)

---

**Last Updated**: 2025-01-20
**Maintained By**: EdgarTools Development Team
