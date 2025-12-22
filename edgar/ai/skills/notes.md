# Research Notes: Edgartools AI Skills Evaluation

## Original Prompt
"My library edgartools has a edgar.ai.skills package that teaches ai agents how to use edgartools to do research. install edgartools, poke around to see if you can figure out how to use it. Use the task to 'perform some research on the Atlanta Braves BATRB' to test edgartools. Generate a report. Then report on how easy is it to use as an agent, identify gaps"

## Research Log

### Step 1: Installation
Starting installation of edgartools...

### Step 2: Installation Complete
- edgartools v4.26.1 installed successfully
- Found edgar.ai.skills package at /usr/local/lib/python3.11/dist-packages/edgar/ai/skills/

### Step 3: Understanding the Skills Structure
The edgar.ai.skills package contains:

**Core Files:**
- `__init__.py` - Skill discovery and management (list_skills, get_skill functions)
- `base.py` - BaseSkill class
- `core/` directory with main skill documentation

**Documentation Structure:**
Located in `/edgar/ai/skills/core/`:
- `SKILL.md` - Main skill documentation (~10,000 tokens)
- `readme.md` - Package overview and usage guide
- `quickstart-by-task.md` - Fast task routing by task type (~5,000 tokens)
- `form-types-reference.md` - SEC form catalog with 311 forms (~7,000 tokens)
- `workflows.md` - End-to-end analysis examples (~4,000 tokens)
- `objects.md` - Core EdgarTools objects with token estimates (~3,000 tokens)
- `data-objects.md` - Form-specific data objects (~4,000 tokens)

**Key Features:**
1. Multi-tier documentation (Quick Start → Core → Advanced)
2. Progressive disclosure structure
3. Natural language question mapping
4. Token size estimates for efficient AI usage
5. Designed for Anthropic Claude Desktop Skills compatibility

**Three Main Approaches for Getting Filings:**
1. Published Filings - Discovery & bulk analysis (quarterly SEC indexes)
2. Current Filings - Real-time monitoring (RSS feed, last 24h)
3. Company Filings - Known entity analysis (specific companies)

**For Financial Statements:**
1. Entity Facts API - Multi-period comparison (fastest, most token-efficient)
2. Filing XBRL - Single period details (most comprehensive)

### Step 4: Testing with Atlanta Braves (BATRB)
Now attempting to research Atlanta Braves using ticker BATRB...

### Step 4: Research Results - Atlanta Braves (BATRB)

✓ **Successfully retrieved:**
- Company name: Atlanta Braves Holdings, Inc.
- Multiple tickers: BATRA, BATRK, BATRB (different share classes)
- CIK: 1958140
- Industry: Services-Amusement & Recreation Services
- SIC: 7900
- Fiscal year end: December 31

✓ **Filings Retrieved:**
- 41 total filings available
- Mix of 10-K (annual), 10-Q (quarterly), and 8-K (current reports)
- Latest 10-K from 2025-03-03 for period ending 2024-12-31

✓ **Financial Data Extracted:**
- Income Statement: Successfully retrieved for 3 fiscal years
  - Revenue FY 2024: $662.7M
  - Operating Loss FY 2024: $(39.7M)
  - Net Loss FY 2024: $(31.3M)
- Balance Sheet: Successfully retrieved
  - Total Assets: $1.52B
  - Total Liabilities: $987.6M
  - Stockholders' Equity: $536.2M
- Cash Flow: Method name issue (cash_flow_statement not found)

### Step 5: Agent Usability Evaluation

**Issues Encountered:**

1. **CRITICAL: User-Agent Required**
   - Must call `set_identity()` before any operations
   - Error message: "User-Agent identity is not set"
   - This is NOT documented in the skill materials reviewed
   - SEC requirement, but not surfaced in quickstart

2. **API Discovery Issues:**
   - Attribute name mismatches (`sic_code` vs `sic`, `category` vs not available)
   - `.latest(1)` returns single object, not list (not obvious)
   - `cash_flow_statement()` method doesn't exist (correct name unknown)

3. **Documentation Gaps:**
   - No mention of `set_identity()` requirement in skill.md, quickstart-by-task.md, or readme.md
   - Attribute names not clearly documented
   - Return types ambiguous (`.latest()` returns single vs list)

**Positive Aspects:**

1. **Excellent Documentation Structure:**
   - Multi-tier approach (Quick Start → Core → Advanced) is well-designed
   - Task-based routing in quickstart-by-task.md is very helpful
   - Token estimates for objects is unique and valuable
   - Form types reference with 311 forms is comprehensive

2. **Clean API Design:**
   - Once working, the API is intuitive
   - Method chaining works well: `company.get_filings(form="10-K")`
   - Rich formatting of output (tables) is helpful

3. **Good Helper Functions:**
   - Helper functions in edgar.ai.helpers provide convenient patterns
   - Good separation of three filing approaches (Published, Current, Company)

4. **Comprehensive Data Access:**
   - Successfully retrieved company info, filings, and financial statements
   - XBRL parsing works well
   - Multi-period financial analysis via Entity Facts API is efficient

### Step 6: Gap Analysis

**Critical Gaps:**

1. **Setup/Prerequisites Section Missing:**
   - Need clear "Before You Start" section with `set_identity()` requirement
   - Should include example: `from edgar import set_identity; set_identity("Your Name your@email.com")`

2. **API Reference Inconsistency:**
   - Company object attributes not clearly documented in skill files
   - Should include quick reference table of key attributes
   - Method return types should be explicit

3. **Error Handling Guidance:**
   - No guidance on common errors and how to fix them
   - User-Agent error should have clear fix in documentation
   - Troubleshooting section would be helpful

4. **Method Name Discovery:**
   - Cash flow statement method name unclear
   - Need comprehensive list of statement methods available

**Minor Gaps:**

1. **Examples Missing Edge Cases:**
   - No examples of companies with multiple ticker symbols
   - Limited error handling examples

2. **Version/Compatibility Info:**
   - README mentions "Part of EdgarTools v4.22.0+" but current version is 4.26.1
   - Should clarify version compatibility

### Recommendations:

1. Add "Setup & Prerequisites" section at top of skill.md with set_identity() example
2. Create attribute reference table for Company object
3. Add troubleshooting section with common errors
4. Clarify method return types (single vs collection)
5. Test all code examples in documentation
6. Add error handling patterns to workflows
