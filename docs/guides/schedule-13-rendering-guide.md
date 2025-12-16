# Schedule 13D/G Rendering Guide

## Overview

This guide provides recommendations for rendering Schedule 13D and Schedule 13G beneficial ownership data in downstream applications. It focuses on data presentation, visual hierarchy, and user experience rather than specific technologies.

## What are Schedule 13D and 13G?

**Schedule 13D** and **Schedule 13G** are SEC filings that disclose when investors acquire more than 5% of a company's voting securities. They provide critical insights into significant ownership positions and investment intentions.

### Key Differences

| Aspect | Schedule 13D | Schedule 13G |
|--------|--------------|--------------|
| **Intent** | Active/Activist - may seek control | Passive - investment purposes only |
| **Filers** | Activists, strategic buyers, PE firms | Mutual funds, ETFs, institutional investors |
| **Disclosure** | Detailed narrative about purpose and plans | Brief, structured responses |
| **Updates** | Required on material changes | Annual updates |
| **Signal** | Potential catalyst for change | Portfolio position disclosure |

## Data Object Structure

### Core Objects

```
Schedule13D / Schedule13G
├── Filing Metadata
│   ├── filing_date
│   ├── is_amendment
│   └── date_of_event / event_date
├── IssuerInfo (the company being reported)
│   ├── name
│   ├── cik
│   ├── cusip
│   └── address
├── SecurityInfo
│   ├── title (e.g., "Common Stock")
│   └── cusip
├── ReportingPerson[] (one or more investors)
│   ├── name
│   ├── cik
│   ├── citizenship
│   ├── aggregate_amount (total shares)
│   ├── percent_of_class
│   ├── sole_voting_power
│   ├── shared_voting_power
│   ├── sole_dispositive_power
│   ├── shared_dispositive_power
│   ├── type_of_reporting_person
│   └── comment (optional)
├── Items (Schedule13DItems or Schedule13GItems)
│   └── [Narrative disclosures - see below]
└── Signature[]
    ├── reporting_person
    ├── signature
    ├── title
    └── date
```

## Visual Hierarchy & Information Priority

### Priority Levels

#### CRITICAL (Always prominently display)
1. **Reporting Person Name** - Who is filing
2. **Issuer Name** - Which company's stock
3. **Ownership Percentage** - How much they own
4. **Total Shares** - Absolute position size
5. **Filing Date** - When disclosed
6. **Form Type** - 13D (active) vs 13G (passive)

#### HIGH (Display in primary view)
1. **Amendment Status** - Is this an update?
2. **Voting Power** - Can they vote the shares?
3. **Purpose (13D only)** - Why did they buy? (Item 4)
4. **Event Date** - When the reportable event occurred
5. **Multiple Filers** - Joint filing indicator

#### MEDIUM (Secondary information)
1. **Dispositive Power** - Can they sell the shares?
2. **Citizenship/Organization**
3. **Source of Funds (13D)** - How was purchase funded?
4. **Type of Reporting Person** - Institution type
5. **CUSIP** - Security identifier

#### LOW (Tertiary/detail view)
1. **Full Item Narratives** - Complete disclosures
2. **Signatures** - Who signed
3. **Address Information**
4. **Additional Items** - Other disclosures

## Recommended Layouts

### 1. Summary Card View (Compact)

**Best for:** Lists, feeds, dashboards

```
┌─────────────────────────────────────────────────┐
│ 📊 Schedule 13D - ACTIVE INVESTOR               │
├─────────────────────────────────────────────────┤
│ RC Ventures LLC                                 │
│ GameStop Corp. (GME)                            │
│                                                 │
│ 8.6% • 36,847,842 shares                        │
│ Filed: Jun 11, 2024 • Amendment #9              │
└─────────────────────────────────────────────────┘
```

**Key Elements:**
- Badge/indicator for 13D vs 13G (use color: 13D = amber/yellow, 13G = green/blue)
- Reporting person name (bold, larger)
- Issuer name with ticker
- Ownership % (large, bold) + share count
- Filing date + amendment status

### 2. Standard Detail View

**Best for:** Full-page views, detail panels

```
╔═══════════════════════════════════════════════════╗
║  Schedule 13D - Beneficial Ownership Report       ║
╠═══════════════════════════════════════════════════╣
║                                                   ║
║  HEADER SECTION                                   ║
║  ├─ Form: Schedule 13D (Amendment)                ║
║  ├─ Filing Date: June 11, 2024                    ║
║  ├─ Event Date: May 24, 2024                      ║
║  ├─ Issuer: GameStop Corp. (0001326380)           ║
║  ├─ Security: Common Stock, $0.001 par value      ║
║  └─ CUSIP: 36467W109                              ║
║                                                   ║
║  OWNERSHIP SUMMARY                                ║
║  ├─ Total Shares: 36,847,842                      ║
║  └─ Total Percent: 8.60%                          ║
║                                                   ║
║  REPORTING PERSONS                                ║
║  ┌────────────────────────────────────────────┐   ║
║  │ Name          │ Shares      │ %     │ Vote │   ║
║  ├────────────────────────────────────────────┤   ║
║  │ RC Ventures   │ 36,847,842 │ 8.6% │ Sole   │   ║
║  │ Ryan Cohen    │ 36,847,842 │ 8.6% │ Sole   │   ║
║  └────────────────────────────────────────────┘   ║
║                                                   ║
║  PURPOSE OF TRANSACTION (Item 4) - 13D ONLY       ║
║  ┌────────────────────────────────────────────┐   ║
║  │ [Narrative text about investment purpose]  │   ║
║  │ [Intent, plans, potential actions]         │   ║
║  └────────────────────────────────────────────┘   ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
```

**Sections (in order):**
1. **Header** - Filing metadata
2. **Ownership Summary** - Aggregate numbers
3. **Reporting Persons Table** - Detailed breakdown
4. **Purpose** (13D) or **Certification** (13G) - Key narrative
5. **Additional Details** (collapsible/expandable)

### 3. Comparison View (Amendments)

**Best for:** Showing changes over time

```
┌─────────────────────────────────────────────────┐
│ Amendment History: RC Ventures / GameStop       │
├─────────────────────────────────────────────────┤
│                                                 │
│ Current (Amendment #9)      Previous (#8)       │
│ ━━━━━━━━━━━━━━━━━━━━━━     ━━━━━━━━━━━━━━       │
│ Jun 11, 2024                May 24, 2024        │
│                                                 │
│ 36,847,842 shares  →  No change                 │
│ 8.60%              →  8.51% (+0.09%)            │
│                                                 │
│ Reason: Triggered by change in outstanding      │
│         shares due to ATM offering              │
└─────────────────────────────────────────────────┘
```

**Key Elements:**
- Side-by-side or diff view
- Highlight what changed
- Show deltas (↑/↓ arrows, +/- values)
- Explain reason for amendment

### 4. Timeline View

**Best for:** Historical ownership tracking

```
      10% ┤
         │     ●───●
       9% ┤    ╱     ╲
         │   ╱       ╲
       8% ┤  ●         ●───●───●
         │
       7% ┤
         └──────────────────────────────
           Jan  Feb  Mar  Apr  May  Jun
           2024 2024 2024 2024 2024 2024
```

**Key Elements:**
- Ownership % over time
- Mark filing dates
- Indicate amendments
- Show trend direction

## Form-Specific Rendering Guidelines

### Schedule 13D (Active/Activist)

**Visual Identity:**
- Color: Amber/Yellow/Orange (signals action/attention)
- Icon: Chart with upward arrow or activist megaphone
- Badge: "ACTIVE INVESTOR" or "13D"

**Critical Information to Highlight:**

1. **Purpose of Transaction (Item 4)** - THE most important section
   - Use prominent panel/card
   - Highlight key terms: "board representation", "strategic alternatives", "merger", "control"
   - Consider keyword extraction for quick scanning
   - Length: Can be long (multiple paragraphs)

2. **Contracts & Agreements (Item 6)**
   - List any agreements
   - Link to exhibits if available
   - Flag: Standstill, voting agreements, board seat rights

3. **Source of Funds (Item 3)**
   - How acquisition was funded
   - Important for understanding commitment level

**Content Emphasis:**
- This is an ACTIVE position - investor may seek change
- Purpose narrative is critical for understanding intent
- Watch for terms: "control", "influence", "board", "strategy", "alternatives"

### Schedule 13G (Passive/Institutional)

**Visual Identity:**
- Color: Green/Blue (signals passive/stable)
- Icon: Building or institutional symbol
- Badge: "PASSIVE INVESTOR" or "13G"

**Critical Information to Highlight:**

1. **Rule Designation**
   - Which exemption rule allows 13G filing
   - Indicates institution type

2. **Institution Type (Item 3)**
   - Investment adviser, bank, insurance company, etc.
   - Helps classify investor

3. **Certification (Item 10)**
   - Passive investor certification
   - Can be brief

**Content Emphasis:**
- This is a PASSIVE position - no control intent
- Routine institutional holding
- Less narrative, more structured data
- Annual updates are common

## Data Presentation Best Practices

### Reporting Persons Table

When displaying multiple reporting persons (joint filers):

```
┌──────────────────────────────────────────────────────────────────┐
│ Reporting Persons                                                │
├──────────────────────────────────────────────────────────────────┤
│ Name              │ Shares       │ %    │ Voting   │ Dispositive │
├──────────────────────────────────────────────────────────────────┤
│ RC Ventures LLC   │ 36,847,842  │ 8.6% │ Sole     │ Sole         │
│ (Type: OO)        │             │      │ 36.8M    │ 36.8M        │
├──────────────────────────────────────────────────────────────────┤
│ Ryan Cohen        │ 36,847,842  │ 8.6% │ Sole     │ Sole         │
│ (Type: IN)        │ via LLC     │      │ 36.8M    │ 36.8M        │
└──────────────────────────────────────────────────────────────────┘
```

**Guidelines:**
- Show type code (IN=Individual, CO=Corporation, etc.) - see Appendix
- Indicate when shares are held indirectly ("via LLC")
- Break down voting/dispositive into sole vs. shared
- Use "N/A" or "0" clearly when no power exists
- **IMPORTANT**: Clearly indicate whether persons are filing jointly or separately (see next section)

### Joint Filer vs. Separate Filer Indication

**CRITICAL**: When multiple reporting persons exist, you **MUST** clearly indicate whether they are filing jointly or separately. This determines how shares are counted.

#### Why This Matters

- **Joint Filers** (`member_of_group == "a"`): All report the **same shares**. Total ownership is the unique count, NOT the sum.
- **Separate Filers** (`member_of_group == "b"` or None): Each reports **different shares**. Total ownership is the sum.

Failing to distinguish these leads to incorrect ownership calculations (e.g., showing 232% instead of 116%!).

#### Display Format: Joint Filers

When `member_of_group == "a"` for all or some reporting persons:

```
┌──────────────────────────────────────────────────────────────────┐
│ 🤝 Reporting Persons (Joint Filing Group)                        │
├──────────────────────────────────────────────────────────────────┤
│ Name              │ Shares       │ %    │ Role                   │
├──────────────────────────────────────────────────────────────────┤
│ RC Ventures LLC   │ 36,847,842  │ 8.6% │ Group Member            │
│ Ryan Cohen        │ 36,847,842  │ 8.6% │ Group Member            │
├──────────────────────────────────────────────────────────────────┤
│ TOTAL (GROUP)     │ 36,847,842  │ 8.6% │ ⚠️ Not summed           │
└──────────────────────────────────────────────────────────────────┘

⚠️  Joint filers report the SAME shares. Total ownership is 8.6%, not 17.2%.
```

**Visual Indicators:**
- **Badge**: "Joint Filing" or "Group Filing"
- **Icon**: 🤝 (handshake) or 👥 (people)
- **Warning**: Clearly state shares are not summed
- **Row styling**: Consider subtle background color to group members together

#### Display Format: Separate Filers

When `member_of_group == "b"` or None:

```
┌──────────────────────────────────────────────────────────────────┐
│ Reporting Persons (Separate Positions)                           │
├──────────────────────────────────────────────────────────────────┤
│ Name              │ Shares       │ %    │ Role                   │
├──────────────────────────────────────────────────────────────────┤
│ Investor A        │ 10,000,000  │ 5.2% │ Individual Position     │
│ Investor B        │  8,500,000  │ 4.4% │ Individual Position     │
├──────────────────────────────────────────────────────────────────┤
│ TOTAL             │ 18,500,000  │ 9.6% │ ✓ Summed                │
└──────────────────────────────────────────────────────────────────┘

✓  Separate positions. Total ownership is the sum: 9.6%
```

**Visual Indicators:**
- **Badge**: "Separate Filers" or no badge (default case)
- **Icon**: None or 📊 (chart)
- **Confirmation**: Clearly state shares ARE summed

#### Mixed Case: Both Joint and Separate

When some persons have `member_of_group == "a"` and others have `"b"` or None:

```
┌──────────────────────────────────────────────────────────────────┐
│ Reporting Persons (Mixed)                                        │
├──────────────────────────────────────────────────────────────────┤
│ Name              │ Shares       │ %    │ Filing Type            │
├──────────────────────────────────────────────────────────────────┤
│ 🤝 Entity A       │ 10,000,000  │ 5.2% │ Joint Group Member      │
│ 🤝 Entity B       │ 10,000,000  │ 5.2% │ Joint Group Member      │
│ Investor C        │  8,500,000  │ 4.4% │ Separate Position       │
├──────────────────────────────────────────────────────────────────┤
│ TOTAL             │ 18,500,000  │ 9.6% │ Group + Separate        │
└──────────────────────────────────────────────────────────────────┘

ℹ️  Total = 10M (unique from group) + 8.5M (separate) = 18.5M (9.6%)
```

**Calculation Notes:**
- Group members: Take unique count (10M, not 20M)
- Separate filers: Add their individual positions (8.5M)
- Total: 10M + 8.5M = 18.5M

#### Implementation Guidance

**Required Fields:**
```python
schedule.reporting_persons[0].member_of_group  # "a", "b", or None
```

**Display Logic:**
```python
# Determine filing type
joint_filers = [p for p in reporting_persons if p.member_of_group == "a"]
separate_filers = [p for p in reporting_persons if p.member_of_group != "a"]

if joint_filers and not separate_filers:
    display_mode = "joint_only"
    header = "🤝 Reporting Persons (Joint Filing Group)"
    note = "⚠️ Joint filers report the SAME shares."
elif separate_filers and not joint_filers:
    display_mode = "separate_only"
    header = "Reporting Persons (Separate Positions)"
    note = "✓ Separate positions. Shares are summed."
else:
    display_mode = "mixed"
    header = "Reporting Persons (Mixed)"
    note = "ℹ️ Combining unique group count with separate positions."
```

**Tooltips/Help Text:**
- **Joint**: "These persons are filing together as a group. They each report the same shares, so the total is NOT doubled."
- **Separate**: "These are independent positions. Each person owns different shares."
- **member_of_group field**: "SEC field indicating 'a' = group member, 'b' = separate filer"

#### Common Mistakes to Avoid

❌ **DON'T**: Sum all shares when persons are joint filers
```
Ryan Cohen: 9.8M (11.8%)
RC Ventures: 9.8M (11.8%)
WRONG TOTAL: 19.6M (23.6%)  ← Incorrect!
```

✅ **DO**: Take unique count for joint filers
```
Ryan Cohen: 9.8M (11.8%)  } Joint Group
RC Ventures: 9.8M (11.8%) } Same shares
CORRECT TOTAL: 9.8M (11.8%)  ← They're the same shares!
```

❌ **DON'T**: Assume same share count = joint filing (unreliable heuristic)

✅ **DO**: Use the `member_of_group` field from SEC data

### Voting and Dispositive Power

These are CRITICAL for understanding control:

**Voting Power:**
- **Sole Voting Power**: Can vote shares independently
- **Shared Voting Power**: Shares voting with others (e.g., joint account)
- **Total Voting Power**: Sum of sole + shared

**Dispositive Power:**
- **Sole Dispositive Power**: Can sell/transfer shares independently
- **Shared Dispositive Power**: Must coordinate with others to sell
- **Total Dispositive Power**: Sum of sole + shared

**Visual Representation:**

```
Voting Power: 36,847,842
  ├─ Sole:   36,847,842 (100%)
  └─ Shared:          0 (0%)

Dispositive Power: 36,847,842
  ├─ Sole:   36,847,842 (100%)
  └─ Shared:          0 (0%)
```

Or as a compact ratio: `Voting: 36.8M (100% sole) | Dispositive: 36.8M (100% sole)`

### Ownership Percentage

**Display Guidelines:**
1. Always show 2 decimal places: `8.60%` not `8.6%`
2. Context matters:
   - < 5%: Should not appear (below reporting threshold)
   - 5-10%: Significant position
   - 10-25%: Large position
   - 25-50%: Major stakeholder
   - > 50%: Control position
3. Consider visual indicators:
   - 5-10%: Normal text
   - 10-25%: Bold or highlighted
   - > 25%: Bold + warning color (this is huge!)

### Amendment Status

Amendments are common and important:

```
Original Filing        Amendment #1       Amendment #5
    2020-08-28    →    2021-03-15    →   2024-06-11
    5.5%               8.2%              8.6%
```

**Display Options:**
- Badge: "Amendment #9"
- Timeline: Show progression
- Diff view: Highlight changes
- Reason: Extract from filing if available

## Content Display Patterns

### Item 4: Purpose of Transaction (13D)

This narrative can range from brief to extensive. Consider these approaches:

**1. Summary + Expandable Detail**
```
Purpose: Investment with potential for board representation
         and strategic input on business direction.

[Show More ▼]
```

**2. Keyword Highlighting**
Extract and highlight key terms:
- Board representation
- Strategic alternatives
- Merger or acquisition
- Asset sales
- Management changes
- Voting agreements
- Control or influence

**3. Intent Classification**
Automatically categorize:
- 🟢 Passive Investment
- 🟡 Strategic/Monitoring
- 🟠 Board Representation
- 🔴 Activist/Control

### Handling Long Narratives

Item 4 can be multiple paragraphs. Strategies:

1. **Truncation with Expansion**
   - Show first 200-300 characters
   - "Read more" link/button
   - Expand inline or modal

2. **Tabbed/Sectioned View**
   - Tab for each Item
   - Easy navigation between Items

3. **Highlight Key Passages**
   - Use AI/NLP to extract key sentences
   - Show as bullet points
   - Link to full text

## Interactive Elements

### Recommended Interactions

1. **Hover/Tooltip**
   - Type codes (IN, CO, OO, etc.) - show full description
   - CUSIP - show full security info
   - Terms - define "dispositive power", "beneficial ownership"

2. **Links**
   - Reporting person name → all filings by this person
   - Issuer name → company page
   - Amendment reference → previous filings
   - CUSIP → security details

3. **Filtering/Sorting** (in list views)
   - Filter by: 13D vs 13G, amendment vs original, date range
   - Sort by: % ownership, filing date, shares

4. **Comparison**
   - Compare to previous amendment
   - Track ownership changes over time
   - See all positions by this investor

## Accessibility Considerations

1. **Color Usage**
   - Don't rely solely on color (13D=amber, 13G=green)
   - Use text labels + icons + color
   - Ensure sufficient contrast

2. **Data Tables**
   - Proper table headers for screen readers
   - Row/column associations clear
   - Support keyboard navigation

3. **Long Content**
   - Provide skip links for long narratives
   - Clear heading structure (H1, H2, H3)
   - Allow text resizing

4. **Numbers**
   - Format with commas: `36,847,842` not `36847842`
   - Provide context for percentages
   - Use `aria-label` for complex data

## Mobile Considerations

### Responsive Patterns

**Small Screens:**
```
┌─────────────────────┐
│ 13D - ACTIVE        │
├─────────────────────┤
│ RC Ventures LLC     │
│ → GameStop Corp.    │
│                     │
│ 8.60%               │
│ 36,847,842 shares   │
│                     │
│ Filed: Jun 11, 2024 │
│ Amendment #9        │
│                     │
│ [View Details]      │
└─────────────────────┘
```

**Stack vertically:**
- One reporting person at a time (if multiple)
- Collapsible sections for Items
- Simplified table → stacked key-value pairs

**Touch Targets:**
- Minimum 44x44px for tap targets
- Adequate spacing between interactive elements
- Expandable sections instead of hover

## Error States & Edge Cases

### Missing Data

1. **No Reporting Persons** (rare but possible)
   - Display: "Reporting persons information not available"
   - Don't show empty table

2. **No Purpose Text** (13D)
   - Display: "Purpose not disclosed" or "See full filing"
   - Don't leave blank space

3. **Zero Voting/Dispositive Power**
   - Display: "0" or "None"
   - Explain: "Shares held by custodian" or similar

### Amendment Without Changes

When amendment is filed but ownership unchanged:
```
⚠️ Amendment #9

No change in share count. Amendment triggered by
change in total shares outstanding.

Previous: 8.51% → Current: 8.60%
(Same 36,847,842 shares, different denominator)
```

## Color Palette Recommendations

**Schedule 13D (Active):**
- Primary: Amber (#F59E0B) or Orange (#F97316)
- Accent: Red (#EF4444) for high ownership
- Background: Warm light (#FEF3C7)
- Border: Dark amber (#D97706)

**Schedule 13G (Passive):**
- Primary: Green (#10B981) or Blue (#3B82F6)
- Accent: Teal (#14B8A6)
- Background: Cool light (#DBEAFE or #D1FAE5)
- Border: Dark green/blue (#059669 or #2563EB)

**Neutral Elements:**
- Headers: Dark gray (#1F2937)
- Body text: Medium gray (#4B5563)
- Borders: Light gray (#E5E7EB)
- Background: White (#FFFFFF) or very light gray (#F9FAFB)

## Typography Recommendations

**Hierarchy:**
- H1 (Form type): 24-32px, bold
- H2 (Sections): 18-24px, semibold
- H3 (Subsections): 16-18px, medium
- Body: 14-16px, regular
- Small/meta: 12-14px, regular

**Emphasis:**
- Ownership %: +2-4px larger, bold
- Reporting person name: Bold
- Issuer name: Medium or semibold
- Numbers: Tabular figures (monospace numbers)

**Families:**
- Headers: Sans-serif (e.g., Inter, Roboto, System UI)
- Body: Sans-serif
- Code/CUSIP: Monospace (e.g., SF Mono, Consolas)

## Example UI Components

### Mini Card (for Lists)

```
┌─────────────────────────────────────────┐
│ 🟠 13D                      Jun 11, 2024│
│                                         │
│ RC Ventures LLC                         │
│ GameStop Corp.                          │
│                                         │
│ 8.60% • 36.8M shares • Amendment #9     │
└─────────────────────────────────────────┘
```

### Detail Panel Header

```
╔════════════════════════════════════════════╗
║ 🟠 Schedule 13D - Active Beneficial Owner  ║
╠════════════════════════════════════════════╣
║                                            ║
║  RC Ventures LLC → GameStop Corp.          ║
║  36,847,842 shares (8.60%)                 ║
║  Amendment #9 • Filed: June 11, 2024       ║
║                                            ║
╚════════════════════════════════════════════╝
```

### Ownership Breakdown

```
┌──────────────────────────────────────────┐
│ Ownership Summary                        │
├──────────────────────────────────────────┤
│                                          │
│  Total Shares      36,847,842            │
│  Ownership %       8.60%                 │
│                                          │
│  Voting Rights                           │
│  ├─ Sole           36,847,842 (100%)     │
│  └─ Shared                 0 (0%)        │
│                                          │
│  Disposition Rights                      │
│  ├─ Sole           36,847,842 (100%)     │
│  └─ Shared                 0 (0%)        │
└──────────────────────────────────────────┘
```

### Purpose Panel (13D)

```
┌────────────────────────────────────────────┐
│ 💡 Purpose of Transaction (Item 4)         │
├────────────────────────────────────────────┤
│                                            │
│ The Shares were acquired for investment    │
│ purposes. The Reporting Persons may        │
│ engage with the Issuer's management and    │
│ board regarding strategic alternatives,    │
│ business plans, and corporate governance.  │
│                                            │
│ Key Terms:                                 │
│ • Strategic alternatives                   │
│ • Board engagement                         │
│ • Corporate governance                     │
│                                            │
│ [Read Full Purpose Text ▼]                 │
└────────────────────────────────────────────┘
```

## Appendix: Type Codes Reference

Display these codes with tooltips/expandable definitions:

### Type of Reporting Person

| Code | Full Description | Use |
|------|------------------|-----|
| IN | Individual | Single person |
| CO | Corporation | Company entity |
| PN | Partnership | Partnership entity |
| IA | Investment Adviser (registered under Investment Advisers Act) | Professional manager |
| IV | Investment Company (registered under Investment Company Act) | Mutual fund, ETF |
| HC | Holding Company | Parent company |
| BD | Broker-Dealer | Securities broker |
| BK | Bank | Banking institution |
| IC | Insurance Company | Insurance entity |
| EP | Employee Benefit Plan | Pension fund, 401k |
| OO | Other | Catch-all category |

### Source of Funds (13D only)

| Code | Full Description |
|------|------------------|
| WC | Working Capital |
| OO | Personal Funds |
| AF | Affiliated Entities |
| BK | Bank Loan |
| PF | Personal Funds of Individuals |
| OB | Other Borrowed Funds |
| NA | Not Applicable |

## Summary: Quick Reference

### Must Display
1. Form type (13D vs 13G) with visual distinction
2. Reporting person name(s)
3. Issuer name
4. Ownership percentage
5. Total shares
6. Filing date
7. Amendment status
8. Purpose (13D) or certification (13G)

### Visual Identity
- **13D**: Amber/orange, active/alert styling, highlight purpose
- **13G**: Green/blue, stable/institutional styling, simpler layout

### Key UX Principles
1. **Hierarchy**: Most critical info (who, what, how much) first
2. **Scannability**: Use numbers, formatting, whitespace
3. **Context**: Explain what data means (tooltips, help text)
4. **Comparison**: Enable tracking changes over time
5. **Depth**: Summary view → detail view → full filing

### Common Patterns
- Card/panel layout for overview
- Table for multiple reporting persons
- Highlighted panel for purpose/narrative
- Collapsible sections for long content
- Timeline for amendment history
- Diff view for changes

---

This guide provides a framework for presenting Schedule 13D/G data effectively. Adapt these patterns to your specific platform, audience, and design system while maintaining the core principles of clarity, hierarchy, and context.
