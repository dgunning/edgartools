# Documentation Guidelines

Standards for writing and maintaining EdgarTools documentation pages. These guidelines codify the patterns already established across existing data-object guides and user guides.

---

## Page Types

### 1. User Guide

Task-oriented pages that walk users through accomplishing a goal.

**Required sections:**
- Introduction (1-2 paragraphs explaining the domain)
- Prerequisites or context (what forms/data are involved)
- Step-by-step code examples with output
- Common patterns or queries
- Next steps / cross-references

**Examples:** `docs/13f-filings.md`, `docs/guides/working-with-filing.md`

### 2. Data Object Guide

The definitive page for a filing type's data class. Structured so a user learns something valuable within 15 seconds of scanning and can go deep if they stay longer.

**Core principle: lead with the payoff, push reference to the bottom.**

A user opens this page to answer "what can I do with this object?" -- not to read a property catalog. Structure the page around actions and outcomes, not class anatomy.

**Page structure (in order):**

| Section | Purpose |
|---------|---------|
| **Hero: code + image** | 3-5 lines to get the object, then a screenshot of what it looks like. This is the first thing on the page after a one-line description. |
| **Core capabilities** | One `##` section per major thing you can *do* (e.g., "See the Holdings", "Compare to Last Quarter", "Track Trends Over Time"). Each has 2-4 lines of code, optionally an image, and a short explanation. |
| **View objects / integration** | How to iterate, slice, and access `.data` on view objects for users building their own apps. |
| **Common analysis patterns** | Short recipes (3-5 lines each) for frequent tasks like concentration analysis, filtering options, finding new positions. |
| **Quick reference tables** | Property table and method table pushed to the bottom. These are lookup, not content. Use compact 3-column format (Property / Returns / Example). |
| **Things to know** | Short, direct sentences about gotchas and data quality. No numbered lists of paragraphs -- keep each point to 1-2 sentences. Lead with the most important (e.g., "Values are in thousands"). |
| **Related** | Links to the companion user guide and other relevant pages. |

**What to leave out:**

- Internal class anatomy (cover page dataclass, signature dataclass, etc.) -- these are implementation details, not user-facing content
- "View Design Recommendations" for UI builders -- this belongs in internal docs if needed
- "Example Data Structure" JSON dumps -- the code examples and screenshots already show the data
- Form-type taxonomy tables at the top -- move to the companion user guide or keep minimal

**Canonical example:** `docs/guides/thirteenf-data-object-guide.md`

**Older pattern (to be migrated):** `docs/guides/eightk-data-object-guide.md`, `docs/guides/npx-data-object-guide.md`

### 3. Concept Page

Explains a domain concept (XBRL, SEC filing lifecycle, standardization) without being tied to a specific class.

**Required sections:**
- What it is (plain-language definition)
- Why it matters
- How EdgarTools handles it
- Related API entry points

**Examples:** `docs/concepts/sec-filings.md`, `docs/xbrl/concepts/standardization.md`

---

## Formatting Conventions

### Property / Method Tables

Use four-column tables for properties:

```markdown
| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `report_period` | `str` | Quarter end date | `"2024-03-31"` |
```

Use three-column tables for methods:

```markdown
| Method | Returns | Description |
|--------|---------|-------------|
| `to_dataframe()` | `pd.DataFrame` | All holdings as DataFrame |
```

### Code Examples

- Use real tickers and realistic data (`"AAPL"`, `"BRK.A"`, not `"ACME"`)
- Every example must be runnable (copy-paste ready)
- Show expected output as comments or in a separate block when helpful
- Start with the simplest usage, then build complexity
- Use `filing.obj()` as the standard entry point for data objects

```python
# Good: real data, runnable
from edgar import Company
berkshire = Company("BRK.A")
filing = berkshire.get_filings(form="13F-HR").latest(1)
thirteen_f = filing.obj()
print(thirteen_f.management_company_name)
```

### Headings

- `#` for page title (one per page)
- `##` for major sections
- `###` for subsections
- `####` sparingly, for deeply nested content

### Cross-References

Use relative paths from the file's location:

```markdown
See [Working with Filings](../guides/working-with-filing.md) for details.
```

For links within the same `docs/` directory level:

```markdown
See the [user guide](../13f-filings.md) for a task-oriented walkthrough.
```

---

## Writing Tone

- Professional and direct
- No emojis in prose -- use Unicode symbols per `docs/internal/design-language.md`
- Acceptable Unicode: arrows (`->`), bullets, checkmarks, dashes
- Second person ("you") is fine for guides; third person for reference pages
- Avoid filler phrases ("it should be noted that", "as you can see")
- Prefer active voice

---

## Image Guidelines

### Format Preference

1. **WebP** -- preferred for all new screenshots and images (smaller, high quality)
2. **PNG** -- acceptable fallback
3. **SVG** -- for diagrams and vector graphics only

### Naming Convention

```
docs/images/{topic}-{description}.webp
```

Examples:
- `docs/images/thirteenf-holdings.webp`
- `docs/images/company-card.webp`

### Sizing

- Standard width: 800px for full-width screenshots
- Use `convert_png_to_webp.py` for batch conversion of existing PNGs
- Use `snapshot_rich.py` to capture Rich console output directly

### Embedding

```markdown
![13F Holdings table](../images/thirteenf-holdings.webp)
```

---

## SEO

Documentation pages are the primary way users discover EdgarTools through search. Every public-facing page should be written with search visibility in mind.

### Meta description

Add YAML frontmatter with a `description` field. This becomes the `<meta name="description">` tag and controls what Google shows in search results. Keep it under 160 characters, include the primary keyword and "Python."

```markdown
---
description: Parse SEC 13F institutional holdings filings with Python. Extract hedge fund portfolios and compare quarter-over-quarter changes using edgartools.
---
```

Without this, Google auto-generates a snippet from the page body -- often a code block or table, which looks bad in results.

### Page title (H1)

The H1 is the strongest on-page SEO signal. Include the primary search phrase naturally. Think about what someone would type into Google.

| Weak | Strong |
|------|--------|
| `13F Holdings` | `13F Holdings: Parse SEC Institutional Portfolio Filings with Python` |
| `Form 4 Insider Trading` | `Form 4: Track SEC Insider Trades with Python` |

The nav label (shown in the sidebar) is set separately in `mkdocs.yml` and can be shorter.

### Opening paragraph

The first paragraph appears in search previews when no meta description is set, and reinforces keyword relevance either way. Mention **EdgarTools**, **Python**, and the SEC form/concept within the first two sentences.

### Headings (H2, H3)

Headings are indexed by search engines. Use descriptive phrases that match how people search, not clever or vague labels.

| Weak | Strong |
|------|--------|
| `See the Holdings` | `Access Holdings Data` |
| `Compare to Last Quarter` | `Compare 13F Holdings Quarter-over-Quarter` |
| `Track Trends Over Time` | `Track Holdings Trends Across Quarters` |

Don't keyword-stuff -- the heading should still read naturally.

### Image alt text

Alt text is used by Google Image Search and screen readers. Describe what the image shows and include relevant keywords.

| Weak | Strong |
|------|--------|
| `13F Holdings Report` | `13F holdings report parsed with Python edgartools` |
| `Holdings Comparison` | `Python 13F holdings quarter-over-quarter comparison` |

### Target keywords

For each page, identify 1-2 primary search phrases. Common patterns:

- `parse {form type} filings python` (e.g., "parse 13F filings python")
- `SEC {form type} python library`
- `{form type} {what you learn} python` (e.g., "13F hedge fund holdings python")

Work these into the meta description, H1, and opening paragraph. The rest of the page should focus on being useful -- search engines reward pages that answer the query well.

---

## Checklist for New Doc Pages

Before merging a new documentation page, verify:

**Structure and content:**

- [ ] Page type identified (user guide / data object guide / concept page)
- [ ] First thing a user sees is working code (3-5 lines) and an image of the result
- [ ] Sections are named after actions ("See the Holdings") not objects ("Holdings Data")
- [ ] A user scanning for 15 seconds learns what the object does and how to get one
- [ ] A user scanning for 60 seconds knows the 3-4 main things they can do with it
- [ ] Reference tables (properties, methods) are at the bottom, not the top
- [ ] No internal-dev sections (view design recommendations, example data structures)

**SEO:**

- [ ] YAML frontmatter includes `description` (under 160 characters, includes "Python")
- [ ] H1 contains the primary search phrase naturally
- [ ] Opening paragraph mentions EdgarTools, Python, and the SEC form/concept
- [ ] H2s use descriptive phrases that match search intent
- [ ] Image alt texts are descriptive and include relevant keywords

**Quality:**

- [ ] Code examples use real tickers and are copy-paste runnable
- [ ] Cross-references use correct relative paths
- [ ] No emojis in prose (Unicode symbols are acceptable)
- [ ] Images are WebP format where possible
- [ ] Page is referenced in `mkdocs.yml` nav
- [ ] `mkdocs serve` renders without broken links

---

## Tooling

| Script | Purpose |
|--------|---------|
| `scripts/convert_svg_to_png.py` | SVG to PNG via Inkscape |
| `scripts/convert_png_to_webp.py` | PNG to WebP via Pillow |
| `scripts/snapshot_rich.py` | Capture Rich console output as images |

---

## References

- [Design Language](design-language.md) -- color palette, typography, Unicode symbols
- [MkDocs Configuration](../../mkdocs.yml) -- site nav structure
