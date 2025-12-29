# AI-Native API Design Patterns for EdgarTools

## Overview

This document describes design patterns for creating AI-optimized APIs in EdgarTools. These patterns emerged from real-world experience analyzing crowdfunding filings and discovering that traditional APIs, while excellent for human developers, can be inefficient for AI agents working with LLM context windows.

## The Problem

### Traditional API Design (Human-Optimized)

When analyzing SEC filings, traditional APIs require AI agents to:

1. **Access deeply nested attributes**:
   ```python
   file_number = formc.issuer_information.funding_portal.file_number
   ```

2. **Manually parse string representations**:
   ```python
   price = float(formc.offering_information.price)
   num_securities = int(float(formc.offering_information.no_of_security_offered))
   ```

3. **Combine related fields**:
   ```python
   security = formc.offering_information.security_offered_type
   if formc.offering_information.security_offered_other_desc:
       security += f" ({formc.offering_information.security_offered_other_desc})"
   ```

4. **Calculate derived metrics**:
   ```python
   days_remaining = (formc.offering_information.deadline_date - date.today()).days
   percent_to_max = (target / maximum) * 100 if maximum else None
   ```

5. **Extract and format 10+ attributes** to build context for analysis

**Result**: ~500-1000 tokens of code + ~300-500 tokens of output for a single filing summary.

### AI-Native API Design

The same analysis with AI-optimized patterns:

```python
# Single method call, configurable detail level
context = formc.to_context(detail='standard', filing_date=filing.filing_date)
print(context)
```

**Result**: ~150-500 tokens depending on detail level, computed metrics included.

---

## Design Pattern: `to_context()` Method

### Core Principle

Provide a single method that returns a token-efficient, structured text representation of complex objects, optimized for LLM context windows.

### Method Signature

```python
def to_context(self, detail: Literal['minimal', 'standard', 'full'] = 'standard', **kwargs) -> str:
    """
    Returns a token-efficient, AI-optimized text representation.

    Args:
        detail: Level of detail to include
            - 'minimal': ~100-200 tokens, essential fields only
            - 'standard': ~300-500 tokens, most important data (default)
            - 'full': ~600-1000 tokens, comprehensive view
        **kwargs: Additional context (e.g., filing_date, related data)

    Returns:
        Formatted string suitable for AI context
    """
```

### Design Guidelines

#### 1. **Structured Output Format**

Use consistent section headers and indentation:

```
FORM TYPE - DESCRIPTION (Context Info)

SECTION 1: Primary Info
  Field: Value
  Field: Value

SECTION 2: Detailed Info
  Field: Value (computed metric)
  Field: Value

STATUS: Derived Status
```

#### 2. **Detail Levels**

**Minimal (~150 tokens)**:
- Essential identification (name, CIK, form type)
- Key financial metrics only
- Most important status indicators
- Use abbreviations ($50K vs $50,000)
- Combine related fields

**Standard (~350 tokens)**:
- All minimal fields with full formatting
- Primary sections fully expanded
- Key computed metrics
- Important relationships

**Full (~800 tokens)**:
- All available data
- Complete financial tables
- All computed metrics
- Relationships and references
- Signature information

#### 3. **Include Computed Fields**

Always include derived metrics that would require calculation:

✅ **Good**:
```
Assets: $35,660 (+173% from $13,044)
Revenue: $0 (pre-revenue)
Net Income: $-654,437 (burn rate increasing)
Debt-to-Asset Ratio: 5055%
Deadline: 2026-04-30 (177 days remaining)
```

❌ **Bad**:
```
Assets Current: 35660
Assets Prior: 13044
Revenue Current: 0
Revenue Prior: 0
Net Income Current: -654437
Net Income Prior: -329037
Deadline: 2026-04-30
```

#### 4. **Handle Missing Data Gracefully**

Only show sections/fields that are populated:

```python
# Good pattern
if self.offering_information:
    lines.append("\nOFFERING:")
    # ... offering details

# Bad pattern - shows empty sections
lines.append("\nOFFERING:")
if self.offering_information:
    # ... offering details
else:
    lines.append("  No offering information")
```

#### 5. **Use Contextual Formatting**

Adapt formatting based on values:

```python
# Amount formatting
if detail == 'minimal':
    # Compact with K/M suffix
    amt_str = f"${amount/1000:.0f}K" if amount < 1000000 else f"${amount/1000000:.1f}M"
else:
    # Full precision with commas
    amt_str = f"${amount:,.2f}"

# Status formatting
if days > 0:
    status = f"{days} days remaining"
elif days == 0:
    status = "EXPIRES TODAY"  # Urgent
else:
    status = f"EXPIRED ({abs(days)} days ago)"  # Past
```

---

## Design Pattern: Convenience Properties

### Core Principle

Wrap complex access patterns, type conversions, and computed metrics in intuitive properties.

### Property Categories

#### 1. **Access Simplification**

Flatten deeply nested structures:

```python
@property
def campaign_file_number(self) -> Optional[str]:
    """File number for the crowdfunding campaign."""
    if self.issuer_information.funding_portal:
        return self.issuer_information.funding_portal.file_number
    return None

# Usage: formc.campaign_file_number
# Instead of: formc.issuer_information.funding_portal.file_number (with None checks)
```

#### 2. **Type Conversion**

Auto-parse string representations:

```python
@property
def price_per_security(self) -> Optional[float]:
    """Parse price string to float"""
    if not self.price:
        return None
    try:
        return float(self.price)
    except (ValueError, TypeError):
        return None

# Usage: formc.offering_information.price_per_security
# Instead of: float(formc.offering_information.price)  # error-prone
```

#### 3. **Field Combination**

Merge related fields into logical units:

```python
@property
def security_description(self) -> str:
    """Combined security type and description"""
    if not self.security_offered_type:
        return "Not specified"
    sec_type = self.security_offered_type
    if self.security_offered_other_desc:
        return f"{sec_type} ({self.security_offered_other_desc})"
    return sec_type

# Usage: formc.offering_information.security_description
# Instead of: Manually combining security_offered_type + security_offered_other_desc
```

#### 4. **Intuitive Aliases**

Provide clearer names for confusing fields:

```python
@property
def target_amount(self) -> Optional[float]:
    """Alias for offering_amount - more intuitive name"""
    return self.offering_amount

# Usage: formc.offering_information.target_amount
# Instead of: formc.offering_information.offering_amount  # unclear what this means
```

#### 5. **Computed Metrics**

Calculate derived values:

```python
@property
def days_to_deadline(self) -> Optional[int]:
    """Days remaining until offering deadline (negative if expired)"""
    if not self.offering_information or not self.offering_information.deadline_date:
        return None
    return (self.offering_information.deadline_date - date.today()).days

@property
def debt_to_asset_ratio(self) -> Optional[float]:
    """Debt-to-asset ratio as percentage"""
    if self.total_asset_most_recent_fiscal_year == 0:
        return None
    return (self.total_debt_most_recent / self.total_asset_most_recent_fiscal_year) * 100
```

#### 6. **Boolean Helpers**

Provide clear status checks:

```python
@property
def is_expired(self) -> bool:
    """True if offering deadline has passed"""
    days = self.days_to_deadline
    return days is not None and days < 0

@property
def is_pre_revenue(self) -> bool:
    """True if company has no revenue"""
    return self.revenue_most_recent_fiscal_year == 0
```

---

## Implementation Example: FormC

### Before (Traditional API)

```python
# Accessing campaign data requires multiple operations
filing = filings[0]
formc = filing.obj()

# Extract basic info (nested access)
company = formc.issuer_information.name
cik = formc.filer_information.cik
if formc.issuer_information.funding_portal:
    portal = formc.issuer_information.funding_portal.name
    file_num = formc.issuer_information.funding_portal.file_number
else:
    portal = None
    file_num = None

# Parse and combine security info (manual)
sec_type = formc.offering_information.security_offered_type or "Not specified"
if formc.offering_information.security_offered_other_desc:
    sec_type += f" ({formc.offering_information.security_offered_other_desc})"

# Parse amounts (string to number)
price = float(formc.offering_information.price) if formc.offering_information.price else None
target = formc.offering_information.offering_amount
maximum = formc.offering_information.maximum_offering_amount

# Calculate metrics
if target and maximum:
    percent = (target / maximum) * 100
deadline = formc.offering_information.deadline_date
if deadline:
    days_left = (deadline - date.today()).days
    expired = days_left < 0

# Format output (200-300 lines of code)
print(f"Company: {company}")
print(f"CIK: {cik}")
# ... 20+ more print statements
```

**Token count**: ~500 tokens of code + ~300 tokens output = **~800 tokens total**

### After (AI-Native API)

```python
filing = filings[0]
formc = filing.obj()

# Option 1: Direct properties (clean access)
print(f"Company: {formc.issuer_information.name}")
print(f"File Number: {formc.campaign_file_number}")
print(f"Security: {formc.offering_information.security_description}")
print(f"Target: ${formc.offering_information.target_amount:,.0f}")
print(f"Price: ${formc.offering_information.price_per_security:.2f}")
print(f"Days to Deadline: {formc.days_to_deadline}")
print(f"Is Expired: {formc.is_expired}")
print(f"Status: {formc.campaign_status}")

# Option 2: Single context call (AI-optimized)
context = formc.to_context(detail='standard', filing_date=filing.filing_date)
print(context)
```

**Token count**: ~50 tokens of code + ~350 tokens output = **~400 tokens total**

**Savings**: ~400 tokens (50% reduction)

---

## When to Use This Pattern

### ✅ Use `to_context()` when:

1. **AI agents need quick summaries** of complex objects
2. **Token efficiency matters** (LLM context limits)
3. **Multiple related fields** should be presented together
4. **Computed metrics** are frequently needed
5. **Different detail levels** serve different use cases

### ✅ Use convenience properties when:

1. **Access patterns are complex** (deeply nested, with null checks)
2. **Type conversions are needed** (string to number, parsing dates)
3. **Field names are unclear** (offering_amount → target_amount)
4. **Related fields should combine** (type + description)
5. **Calculations are common** (ratios, growth rates, days remaining)

### ❌ Don't use when:

1. **Data is already simple** (single string, straightforward access)
2. **Performance is critical** and properties add overhead
3. **Raw data access is needed** for downstream processing
4. **The object is rarely used** by AI agents

---

## Pattern Application to Other EdgarTools Classes

### Filing Class

```python
class Filing:
    def to_context(self, detail='standard') -> str:
        """
        Minimal: Form, company, date, status
        Standard: + key facts, document count, file size
        Full: + all attachments, exhibits, related filings
        """

    @property
    def filing_age_days(self) -> int:
        """Days since filing"""
        return (date.today() - self.filing_date).days

    @property
    def document_summary(self) -> str:
        """Concise summary of attached documents"""
        return f"{len(self.attachments)} documents, {self.primary_document.size} bytes"
```

### Company Class

```python
class Company:
    def to_context(self, detail='standard') -> str:
        """
        Minimal: Name, CIK, industry, status
        Standard: + key financials, recent filings count
        Full: + full facts, insider list, detailed metrics
        """

    @property
    def latest_filing_date(self) -> Optional[date]:
        """Date of most recent filing"""
        recent = self.get_filings(limit=1)
        return recent[0].filing_date if recent else None
```

### XBRL / Statements

```python
class Statement:
    def to_context(self, detail='standard') -> str:
        """
        Minimal: Statement type, period, key line items
        Standard: + important metrics, growth rates
        Full: + full statement, all periods, footnotes
        """

    @property
    def revenue_growth_rate(self) -> Optional[float]:
        """YoY revenue growth as percentage"""
        # Calculate from periods

    @property
    def is_profitable(self) -> bool:
        """True if net income is positive"""
        # Check net income
```

---

## Testing AI-Native Features

### Unit Tests

```python
def test_to_context_minimal():
    formc = FormC.from_xml(sample_xml, form="C")
    context = formc.to_context(detail='minimal')

    assert len(context) < 1000  # Token budget check
    assert "ISSUER:" in context
    assert formc.issuer_information.name in context
    assert "CAMPAIGN STATUS:" in context

def test_to_context_with_none_values():
    """to_context handles missing data gracefully"""
    formc = FormC(...)  # Create with many None values
    context = formc.to_context()

    assert "None" not in context  # No exposed None values
    assert context  # Still returns useful content

def test_convenience_properties():
    formc = FormC.from_xml(sample_xml, form="C")

    # Access simplification
    assert formc.campaign_file_number == "007-00033"

    # Type conversion
    assert isinstance(formc.offering_information.price_per_security, float)

    # Computed metrics
    assert isinstance(formc.days_to_deadline, int)
    assert isinstance(formc.is_expired, bool)
```

### Token Counting Tests

```python
def test_token_efficiency():
    """Verify token budgets for detail levels"""
    import tiktoken

    formc = FormC.from_xml(sample_xml, form="C")
    enc = tiktoken.get_encoding("cl100k_base")

    minimal = formc.to_context(detail='minimal')
    standard = formc.to_context(detail='standard')
    full = formc.to_context(detail='full')

    assert len(enc.encode(minimal)) < 250
    assert len(enc.encode(standard)) < 600
    assert len(enc.encode(full)) < 1200
```

---

## Benefits Summary

### For AI Agents

- **50-70% token reduction** for common analysis tasks
- **Single function call** instead of 10+ attribute accesses
- **Built-in computed metrics** (no manual calculation)
- **Graceful handling** of missing data
- **Configurable detail** for different use cases

### For Human Developers

- **Cleaner code** with convenience properties
- **Fewer errors** from type conversions
- **Better discoverability** through intuitive naming
- **Consistent patterns** across the library
- **Backwards compatible** (existing APIs unchanged)

### For Library Maintainers

- **Centralized formatting** logic
- **Easier to update** presentation (one place)
- **Better testing** of output quality
- **Clear extension pattern** for new classes
- **Documentation by example** (self-documenting output)

---

## Future Directions

### 1. Schema-Driven Context Generation

Define schemas for different analysis tasks:

```python
context = formc.to_context(
    schema='financial_analysis',  # Pre-defined field selections
    include_computed=True,
    format='markdown'  # or 'json', 'yaml'
)
```

### 2. Context Caching

Cache generated contexts to avoid regeneration:

```python
@lru_cache(maxsize=100)
def to_context(self, detail='standard', **kwargs) -> str:
    # Expensive formatting done once
```

### 3. Multi-Object Context

Combine related objects:

```python
campaign_context = Campaign.to_context(
    initial_filing=formc_initial,
    updates=[formc_u1, formc_u2],
    annual_reports=[formc_ar1],
    detail='standard'
)
```

### 4. AI-Specific Serialization

Optimize for specific AI models:

```python
context = formc.to_context(
    detail='standard',
    target_model='gpt-4',  # Adjust formatting for model
    include_reasoning_hints=True  # Add analysis guidance
)
```

---

## References

- **Implementation**: `edgar/offerings/formc.py` (FormC.to_context, convenience properties)
- **Example Usage**: `docs/examples/crowdfunding.py` (Step 1 demonstration)
- **Research**: `docs/examples/crowdfunding_research_goals.md` (Pattern discovery process)

---

**Version**: 1.0
**Last Updated**: 2025-11-04
**Status**: Active design pattern in EdgarTools
