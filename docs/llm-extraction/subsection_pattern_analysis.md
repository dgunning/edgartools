# Subsection Pattern Analysis Across Companies

## Overview

Analyzed Item 1 sections from 4 companies (SNAP, NVDA, AAPL, BFLY) to identify common subsection patterns for markdown conversion.

## Key Findings

### 1. SNAP (Snapchat) - 14 subsections
**Pattern Type**: Standalone short lines + "Title: Description" format

**Examples of standalone subsections**:
- "Overview" (line 7)
- "Snapchat" (line 15)
- "Our Partner Ecosystem" (line 38)
- "Our Advertising Products" (line 48)
- "Technology" (line 79)
- "Employees and Culture" (line 92)
- "Competition" (line 123)
- "Intellectual Property" (line 137)

**Examples of "Title: Description" format**:
- "Camera: The Camera is a powerful tool for communication..." (line 19)
- "Visual Messaging: Visual Messaging is a fast, fun way..." (line 21)
- "Snap Map: Snap Map is a live and highly personalized map..." (line 23)
- "Stories: Stories are a fun way to stay connected..." (line 25)
- "Spotlight: Spotlight showcases the best of Snapchat..." (line 30)

### 2. NVDA (NVIDIA) - 155+ detected items
**Pattern Type**: Mostly financial statements and tables

**Note**: NVDA's Item 1 is primarily:
- Auditor reports
- Consolidated financial statements
- Tables with financial data
- These already have proper heading structure
- Not representative of narrative subsection patterns

**Conclusion**: NVDA is NOT a good example for subsection detection - it's mostly structured financial data.

### 3. AAPL (Apple) - 25 subsections
**Pattern Type**: Standalone short lines (clean hierarchy)

**Examples**:
- "Company Background" (line 7)
- "Products" (line 11)
  - "iPhone" (line 13)
  - "Mac" (line 17)
  - "iPad" (line 21)
  - "Wearables, Home and Accessories" (line 25)
- "Services" (line 35)
  - "Advertising" (line 37)
  - "AppleCare" (line 41)
  - "Cloud Services" (line 45)
  - "Digital Content" (line 49)
  - "Payment Services" (line 55)
- "Segments" (line 59)
- "Markets and Distribution" (line 63)
- "Competition" (line 67)
- "Supply of Components" (line 77)
- "Research and Development" (line 83)
- "Intellectual Property" (line 87)
- "Human Capital" (line 101)

### 4. BFLY (Butterfly Network) - 33 subsections
**Pattern Type**: Standalone short lines (similar to AAPL and SNAP)

**Examples**:
- "Overview" (line 7)
- "Corporate History and Information" (line 19)
- "The Evolution of Ultrasound" (line 30)
- "Market Opportunity" (line 49)
- "Business Strategy" (line 59)
- "Products" (line 80)
  - "Butterfly iQ+ and iQ3" (line 84)
  - "Software Subscriptions" (line 109)
  - "Butterfly iQ+ Bladder" (line 117)
  - "Butterfly for Enterprises" (line 126)
  - "Educational Tools" (line 144)
  - "Butterfly iQ+ Vet" (line 150)
- "Marketing and Sales" (line 161)
- "Geographic Areas" (line 179)

## Common Subsection Patterns

### Pattern 1: Standalone Short Lines (Most Common)
**Characteristics**:
- Preceded by blank line
- Short text (< 80 characters)
- Title case or capitalized first word
- NOT a list item (no bullets, dashes, numbers)
- NOT already a markdown heading (no # prefix)

**Detection Heuristics**:
```python
if (len(line.strip()) < 80 and
    prev_line.strip() == "" and
    not line.startswith(('•', '-', '*', '#')) and
    line.strip()[0].isupper()):
    # Potential subsection
```

### Pattern 2: "Title: Description" Format (Less Common)
**Characteristics**:
- Short title (< 50 chars) followed by colon
- Description after colon (> 20 chars)
- Title starts with capital letter

**Found in**: SNAP only (in this sample)

**Examples**:
- "Camera: The Camera is a powerful tool..."
- "Visual Messaging: Visual Messaging is a fast, fun way..."

**Potential Handling**:
1. Split into subsection heading + description paragraph
2. Or convert entire line to heading (loses description detail)

## Subsection Hierarchy Patterns

Looking at the examples, there appears to be **2-3 levels of hierarchy**:

**Level 1** (Main sections):
- "Products", "Services", "Competition", "Market Opportunity"

**Level 2** (Sub-sections):
- Under "Products": "iPhone", "Mac", "iPad", "Wearables, Home and Accessories"
- Under "Services": "Advertising", "AppleCare", "Cloud Services"

**Detection for hierarchy**:
- No clear pattern in markdown alone (would need context/indentation from HTML)
- Could use simple heuristics:
  - Longer titles = Level 1
  - Shorter titles = Level 2
  - OR: All detected subsections = same level (###)

## Current Implementation Gap

**edgar/llm_helpers.py lines 1157-1161** already converts HTML heading tags:
```python
if element.name.startswith("h"):
    txt = clean_text(element.get_text())
    if txt and not is_noise_text(txt):
        output_parts.append(f"\n### {txt}\n")
    continue
```

**Problem**: Subsections like "Overview", "Technology", "Products" are **NOT** in HTML heading tags (`<h1>-<h6>`).

They are likely:
1. Bold text (`<b>` or `<strong>` tags)
2. Standalone paragraph tags (`<p>`)
3. Plain text within divs

## Recommendations

### Option 1: Convert bold standalone lines
- Detect `<b>` or `<strong>` tags that are standalone (not mid-paragraph)
- Convert to `###` headings

### Option 2: Detect standalone short paragraphs
- Detect `<p>` tags with short text (< 80 chars)
- Preceded by empty content
- Title case
- Convert to `###` headings

### Option 3: Pattern-based detection in markdown post-processing
- Process markdown after HTML conversion
- Find standalone short lines matching patterns
- Convert to headings

**Recommended Approach**: Option 1 + Option 2 hybrid
- Check for bold tags in HTML processing (most reliable)
- Fallback to paragraph pattern detection
- Handle "Title: Description" format by splitting into heading + paragraph

## HTML Structure Analysis

### SNAP Subsections
**HTML Pattern**:
```html
<div style="margin-top:18pt;text-align:justify">
    <span style="color:#000000;font-family:'Times New Roman',sans-serif;font-size:10pt;font-weight:700;line-height:120%">
        Overview
    </span>
</div>
```

**Key Characteristics**:
- `<span>` with `font-weight:700` (bold)
- NO siblings (standalone in parent div)
- Parent div has `margin-top:18pt` or `6pt`
- Font-size: 10pt

### AAPL Subsections
**HTML Pattern**:
```html
<div style="margin-top:18pt;text-align:justify">
    <span style="color:#000000;font-family:'Helvetica',sans-serif;font-size:9pt;font-weight:700;line-height:120%">
        Products
    </span>
</div>
```

**Key Characteristics**:
- `<span>` with `font-weight:700` (bold) OR `font-style:italic`
- NO siblings (standalone in parent div)
- Parent div has `margin-top:9pt` or `18pt`
- Font-size: 9pt

**Special Case - "Advertising"**:
```html
<div style="margin-top:9pt;text-align:justify">
    <span style="font-style:italic;font-weight:400;...">
        Advertising
    </span>
</div>
```
This is a Level 2 subsection (under "Services") - uses italic instead of bold.

## Detection Logic

### Heuristic for Subsection Detection:
```python
def is_subsection_span(element, parent):
    """Check if a span element is a subsection heading."""

    # Must be a span tag
    if element.name != 'span':
        return False

    # Get text
    text = element.get_text().strip()

    # Must be short (< 80 chars)
    if not text or len(text) > 80:
        return False

    # Must be standalone (no siblings)
    if element.next_sibling or element.previous_sibling:
        # Allow whitespace siblings
        siblings = [s for s in element.parent.children if s.strip() if isinstance(s, str) else True]
        if len(siblings) > 1:
            return False

    # Check style attributes
    style = element.get('style', '')

    # Must have bold OR italic
    if 'font-weight:700' not in style and 'font-style:italic' not in style:
        return False

    # Parent should have top margin
    parent_style = parent.get('style', '') if parent else ''
    if 'margin-top' not in parent_style:
        return False

    # Text should start with capital letter (not number/bullet)
    if not text[0].isupper():
        return False

    return True
```

### Heading Level Assignment:
- **Bold (`font-weight:700`)**: Level 1 subsection → `###`
- **Italic (`font-style:italic`)**: Level 2 subsection → `####`

## Next Steps

1. ✅ Analyze patterns across companies (DONE)
2. ✅ Check HTML source to confirm subsection tags (DONE - they're `<span>` tags)
3. ⬜ Implement detection logic in edgar/llm_helpers.py
4. ⬜ Test across all 4 companies
5. ⬜ Verify hierarchy levels are appropriate
