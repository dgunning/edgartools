# EdgarTools Display Design Language

A cohesive design language for all rich terminal output in EdgarTools.

## Core Principles

### 1. Professional Appearance
- Balanced use of color - not overwhelming, not bland
- Colors serve a purpose (identification, hierarchy, status)
- Consistent styling builds user trust and recognition

### 2. Card-Based Layout
- Single outer border with rounded corners (`box.ROUNDED`)
- `expand=False` - cards size to content, not terminal width
- Whitespace for internal section separation (no nested borders)

### 3. Weight-Based Typography
- Use **bold** and **dim** for hierarchy, not font sizes
- Primary elements are bold, secondary are normal, tertiary are dim
- No reliance on terminal-specific font features

### 4. Semantic Colors
- Colors have consistent meaning across all displays
- Same element type = same color everywhere
- See Color Palette below

### 5. No Emojis
- Use unicode symbols instead (arrows, bullets, checkmarks)
- Emojis render inconsistently across terminals
- Unicode symbols are more professional

---

## Color Palette

### Primary Elements (High Visibility)

| Element | Style | Usage |
|---------|-------|-------|
| `company_name` | `bold green` | Company/entity names |
| `ticker` | `bold gold1` | Stock symbols (AAPL, MSFT) |
| `form_type` | `bold` | Form types (10-K, 10-Q, 8-K) |

### Identifiers

| Element | Style | Usage |
|---------|-------|-------|
| `cik` | `dodger_blue1` | CIK numbers |
| `accession` | `dodger_blue1` | Accession numbers |

### Structure

| Element | Style | Usage |
|---------|-------|-------|
| `section_header` | `bold` | Section titles within cards |
| `subsection` | `bold dim` | Sub-section headers |
| `border` | `grey50` | Card borders |
| `separator` | `grey50` | Inline separators |

### Labels and Values

| Element | Style | Usage |
|---------|-------|-------|
| `label` | `grey70` | Left-column labels in key-value pairs |
| `value` | (default) | Right-column values |
| `value_highlight` | `bold` | Emphasized values |

### Metadata

| Element | Style | Usage |
|---------|-------|-------|
| `metadata` | `dim` | Subtitles, footers, counts |
| `hint` | `dim italic` | Helper text, tips |
| `date` | `dim` | Filing dates, timestamps |

### Status Indicators

| Element | Style | Usage |
|---------|-------|-------|
| `positive` | `green` | Success, gains, positive values |
| `negative` | `red` | Errors, losses, negative values |
| `neutral` | `dim` | Unchanged, N/A |
| `warning` | `yellow` | Alerts, cautions |
| `info` | `cyan` | Informational notes |

### Financial Statements

| Element | Style | Usage |
|---------|-------|-------|
| `total_row` | `bold` | Total/summary rows |
| `subtotal_row` | `bold dim` | Subtotal rows |
| `abstract_item` | `bold cyan` | Section headers (ASSETS, REVENUE) |

---

## Unicode Symbols

Replace emojis with these unicode characters:

| Symbol | Character | Usage |
|--------|-----------|-------|
| `arrow_right` | `→` | Navigation, progression |
| `arrow_left` | `←` | Back navigation |
| `arrow_up` | `↑` | Increase indicator |
| `arrow_down` | `↓` | Decrease indicator |
| `bullet` | `•` | List items, inline separators |
| `pipe` | `│` | Vertical separator |
| `check` | `✓` | Success, complete |
| `cross` | `✗` | Failed, error |
| `warning` | `⚠` | Warning indicator |
| `info` | `ℹ` | Information note |
| `ellipsis` | `…` | Truncation |

---

## Card Anatomy

```
╭─ [Title] ────────────────────────────────╮
│                                          │
│   [Content Area]                         │
│                                          │
│   Label          Value                   │
│   Label          Value                   │
│                                          │
╰─ [Subtitle/Footer] ──────────────────────╯
```

### Title Zone
- Company name in `bold green`
- Ticker in `bold gold1` (if applicable)
- Form type in `bold` (for filings)

### Content Area
- Key-value pairs with aligned columns
- Labels in `grey70`, values in default
- Whitespace between logical groups

### Footer Zone
- Metadata in `dim`
- Right-aligned counts or hints

---

## Component Patterns

### Company Card

```python
╭─ Apple Inc. AAPL ─────────────────────────────────╮
│   CIK                0000320193                   │
│   Type               Large Accelerated Filer      │
│   Industry           3571: Electronic Computers   │
│   Fiscal Year End    September                    │
╰───────────────────────────────────────────────────╯
```

### Filing Card

```python
╭─ 10-K  Apple Inc. AAPL ───────────────╮
│   Filed        2024-11-01             │
│   Accession    0000320193-24-000081   │
│   Period       2024-09-28             │
│   Documents    85 files               │
╰─ Annual Report ───────────────────────╯
```

### Formatted Identifiers

CIK and accession numbers use component-aware formatting:

**CIK**: Leading zeros dimmed, value in bold
```
0000320193  →  dim(0000) + bold(320193)
```

**Accession**: Leading zeros dimmed, year highlighted, sequence value bold
```
0000320193-24-000081  →  dim(0000) + bold(320193) + - + dodger_blue1(24) + - + dim(000) + bold(081)
```

---

## Implementation

### Location
```
edgar/display/
├── __init__.py      # Package exports
├── styles.py        # PALETTE, SYMBOLS, utilities
├── components.py    # Reusable card builders (future)
└── demo.py          # Interactive style preview
```

### Using the Palette

```python
from edgar.display import PALETTE, get_style, styled

# Get a style string
style = get_style("company_name")  # Returns "bold green"

# Create styled text
from rich.text import Text
title = Text("Apple Inc.", style=get_style("company_name"))

# Or use the helper
title = styled("Apple Inc.", "company_name")
```

### Creating a Card

```python
from rich.panel import Panel
from rich import box
from edgar.display import get_style

card = Panel(
    content,
    title=title,
    title_align="left",
    border_style=get_style("border"),
    box=box.ROUNDED,
    padding=(0, 1),
    expand=False,  # Always False for cards
)
```

---

## Migration Guide

When updating existing `__rich__` methods:

1. **Remove emojis** - Replace with unicode from `SYMBOLS`
2. **Use semantic colors** - Import from `PALETTE`, don't hardcode
3. **Set `expand=False`** - On all Panel components
4. **Use `box.ROUNDED`** - Standard card border
5. **Align with patterns** - Follow card anatomy above

### Before
```python
def __rich__(self):
    title = Text.assemble("🏢 ", (self.name, "bold green"))
    return Panel(title, box=box.DOUBLE)
```

### After
```python
from edgar.display import get_style, SYMBOLS

def __rich__(self):
    title = Text.assemble(
        (self.name, get_style("company_name")),
        " ",
        (self.ticker, get_style("ticker"))
    )
    return Panel(
        content,
        title=title,
        title_align="left",
        border_style=get_style("border"),
        box=box.ROUNDED,
        expand=False,
    )
```

---

## Testing the Design

Run the interactive demo to preview all styles:

```bash
python -m edgar.display.demo
```

This shows:
- Card mockups (Company, Filing, Statement)
- Full color palette with previews
- Unicode symbols reference
- Color comparison tools

---

## References

- Rich library: https://rich.readthedocs.io/
- Color names: https://rich.readthedocs.io/en/stable/appendix/colors.html
- Box styles: https://rich.readthedocs.io/en/stable/appendix/box.html

## Inspiration

- `gh` (GitHub CLI) - clean, modern, tasteful color use
- `lazygit` - dense but scannable
- `btop` - beautiful data visualization