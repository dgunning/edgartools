# Proxy Data Models Documentation

## Overview

The `edgar.proxy.models` module contains data classes for representing structured executive compensation and pay vs performance data from DEF 14A filings.

## Data Classes

### ExecutiveCompensation

Represents a single year of executive compensation data from the Pay vs Performance table.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class ExecutiveCompensation:
    fiscal_year_end: str
    peo_total_comp: Optional[Decimal] = None
    peo_actually_paid_comp: Optional[Decimal] = None
    neo_avg_total_comp: Optional[Decimal] = None
    neo_avg_actually_paid_comp: Optional[Decimal] = None
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `fiscal_year_end` | str | End date of fiscal year (e.g., "2023-09-30") |
| `peo_total_comp` | Decimal | PEO total from Summary Compensation Table |
| `peo_actually_paid_comp` | Decimal | PEO Compensation Actually Paid |
| `neo_avg_total_comp` | Decimal | Non-PEO NEO average total compensation |
| `neo_avg_actually_paid_comp` | Decimal | Non-PEO NEO average CAP |

**Example:**
```python
from edgar.proxy import ExecutiveCompensation
from decimal import Decimal

comp = ExecutiveCompensation(
    fiscal_year_end="2023-09-30",
    peo_total_comp=Decimal("63209914"),
    peo_actually_paid_comp=Decimal("143466695"),
    neo_avg_total_comp=Decimal("22013346"),
    neo_avg_actually_paid_comp=Decimal("49778878")
)

print(f"CEO Total Comp: ${comp.peo_total_comp:,}")
```

### PayVsPerformance

Represents a single year of pay vs performance metrics.

```python
@dataclass(frozen=True)
class PayVsPerformance:
    fiscal_year_end: str
    peo_actually_paid_comp: Optional[Decimal] = None
    neo_avg_actually_paid_comp: Optional[Decimal] = None
    total_shareholder_return: Optional[Decimal] = None
    peer_group_tsr: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    company_selected_measure_value: Optional[Decimal] = None
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `fiscal_year_end` | str | End date of fiscal year |
| `peo_actually_paid_comp` | Decimal | PEO Compensation Actually Paid |
| `neo_avg_actually_paid_comp` | Decimal | Non-PEO NEO average CAP |
| `total_shareholder_return` | Decimal | Company TSR (cumulative %) |
| `peer_group_tsr` | Decimal | Peer group TSR (cumulative %) |
| `net_income` | Decimal | Net income for the year |
| `company_selected_measure_value` | Decimal | Company-selected KPI value |

**Example:**
```python
from edgar.proxy import PayVsPerformance
from decimal import Decimal

pvp = PayVsPerformance(
    fiscal_year_end="2023-09-30",
    peo_actually_paid_comp=Decimal("143466695"),
    neo_avg_actually_paid_comp=Decimal("49778878"),
    total_shareholder_return=Decimal("205.34"),
    peer_group_tsr=Decimal("178.92"),
    net_income=Decimal("96995000000")
)

print(f"Company TSR: {pvp.total_shareholder_return}%")
print(f"vs Peer Group: {pvp.peer_group_tsr}%")
```

### NamedExecutive

Represents an individual named executive officer when dimensionally tagged in XBRL.

```python
@dataclass(frozen=True)
class NamedExecutive:
    name: str
    member_id: Optional[str] = None
    role: Optional[str] = None
    total_comp: Optional[Decimal] = None
    actually_paid_comp: Optional[Decimal] = None
    fiscal_year_end: Optional[str] = None
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Executive's name |
| `member_id` | str | XBRL member identifier (dimension value) |
| `role` | str | Role designation (PEO, NEO, etc.) |
| `total_comp` | Decimal | Total compensation |
| `actually_paid_comp` | Decimal | Compensation actually paid |
| `fiscal_year_end` | str | Fiscal year end date |

**Example:**
```python
from edgar.proxy import NamedExecutive
from decimal import Decimal

exec = NamedExecutive(
    name="Tim Cook",
    member_id="ecd:TimCookMember",
    role="PEO",
    total_comp=Decimal("63209914"),
    actually_paid_comp=Decimal("143466695"),
    fiscal_year_end="2023-09-30"
)

print(f"{exec.name} ({exec.role}): ${exec.total_comp:,}")
```

## Constants

### PROXY_FORMS

List of SEC form types that map to the ProxyStatement data object:

```python
PROXY_FORMS = ['DEF 14A', 'DEF 14A/A', 'DEFA14A', 'DEFM14A']
```

| Form | Description |
|------|-------------|
| `DEF 14A` | Definitive Proxy Statement |
| `DEF 14A/A` | Amendment to Definitive Proxy Statement |
| `DEFA14A` | Additional Definitive Proxy Materials |
| `DEFM14A` | Definitive Proxy Statement (Merger) |

**Example:**
```python
from edgar.proxy import PROXY_FORMS

filing = company.get_filings(form="DEF 14A").latest()

# Check if form is a proxy form
if filing.form in PROXY_FORMS:
    proxy = filing.obj()
```

## Immutability

All data classes are frozen (`frozen=True`), making them immutable and hashable:

```python
comp = ExecutiveCompensation(fiscal_year_end="2023-09-30")

# This raises an error - objects are immutable
comp.fiscal_year_end = "2024-09-30"  # FrozenInstanceError

# Objects can be used as dictionary keys or in sets
comp_set = {comp}
comp_dict = {comp: "Apple 2023"}
```

## Type Safety

All numeric fields use `Decimal` for financial precision:

```python
from decimal import Decimal

# Values are stored as Decimal
comp = ExecutiveCompensation(
    fiscal_year_end="2023-09-30",
    peo_total_comp=Decimal("63209914.50")
)

# Precise arithmetic
total = comp.peo_total_comp + Decimal("1000000")

# Convert to float when needed for display
print(f"${float(comp.peo_total_comp):,.2f}")
```

## Working with Optional Fields

Most fields are optional and default to `None`:

```python
# Create with minimal data
comp = ExecutiveCompensation(fiscal_year_end="2023-09-30")

# Check before using
if comp.peo_total_comp is not None:
    print(f"CEO Comp: ${comp.peo_total_comp:,}")
else:
    print("CEO compensation not available")
```
