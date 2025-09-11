# Portfolio Manager Database - Manual Maintenance Guide

This guide explains how to manually add, update, and maintain portfolio manager information in the EdgarTools database.

## File Location
**Database File**: `/Users/dwight/PycharmProjects/edgartools/edgar/data/portfolio_managers.json`

## Database Structure

The JSON file has two main sections:

### 1. Metadata Section
```json
{
  "metadata": {
    "version": "2024.12.01",
    "description": "Curated database of portfolio managers for major 13F filing institutions", 
    "total_companies": 15,
    "total_managers": 25,
    "last_updated": "2024-12-01",
    "sources": ["company_websites", "sec_filings", "press_releases", "public_records"]
  }
}
```

**Update when adding managers:**
- Increment `total_companies` when adding new companies
- Increment `total_managers` when adding new individual managers
- Update `last_updated` to current date

### 2. Managers Section
Each company entry follows this structure:

```json
{
  "managers": {
    "company_key": {
      "company_name": "Full Legal Company Name",
      "aum_billions": 123,
      "match_patterns": ["pattern1", "pattern2", "pattern3"],
      "website": "https://www.company.com",
      "managers": [
        {
          "name": "Manager Full Name",
          "title": "Official Title",
          "status": "active|retired|deceased|former", 
          "confidence": "high|medium|low",
          "sources": ["source1", "source2"],
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "last_verified": "YYYY-MM-DD",
          "note": "Additional context or details"
        }
      ]
    }
  }
}
```

## Adding New Companies

### Step 1: Choose Company Key
Use lowercase, underscore-separated format:
- ✅ Good: `berkshire_hathaway`, `goldman_sachs`, `two_sigma`  
- ❌ Bad: `Berkshire-Hathaway`, `goldmanSachs`, `TwoSigma`

### Step 2: Research Company Information
Gather the following data:

**Required:**
- Full legal company name (from SEC filings)
- Current AUM in billions (approximate is fine)
- Company website URL
- Portfolio manager names and titles

**Recommended Sources:**
1. Company website "Leadership" or "Team" pages
2. Latest 10-K filing (Item 1A - Directors and Executive Officers)
3. Latest DEF 14A proxy statement  
4. Recent press releases
5. Financial news articles

### Step 3: Add Company Entry
```json
{
  "new_company": {
    "company_name": "New Company Inc", 
    "aum_billions": 50,
    "match_patterns": ["new company", "newco", "nc inc"],
    "website": "https://www.newcompany.com",
    "managers": []
  }
}
```

**Match Patterns Tips:**
- Include common variations of company name
- Include stock ticker symbols if applicable  
- Include abbreviations commonly used
- All patterns should be lowercase

### Step 4: Add Manager Information
```json
{
  "managers": [
    {
      "name": "Jane Smith",
      "title": "Chief Investment Officer",
      "status": "active",
      "confidence": "high", 
      "sources": ["company_website", "sec_filing_2024"],
      "start_date": "2020-01-01",
      "last_verified": "2024-12-01",
      "note": "Former Goldman Sachs managing director"
    }
  ]
}
```

## Manager Status Definitions

- **active**: Currently in active management role
- **retired**: Retired but may retain advisory role
- **deceased**: Deceased (include year in status like "deceased_2023")
- **former**: No longer with the organization

## Confidence Levels

- **high**: Verified from multiple official sources (company website + SEC filing)
- **medium**: Verified from single official source  
- **low**: Approximate or historical information

## Common Sources

**Primary (High Confidence):**
- `company_website` - Official leadership pages
- `sec_filings` - 10-K, DEF 14A proxy statements
- `annual_report_2024` - Latest annual report

**Secondary (Medium Confidence):**  
- `press_releases` - Official company announcements
- `financial_press` - WSJ, FT, Bloomberg articles
- `industry_publications` - Trade publications

**Tertiary (Low Confidence):**
- `linkedin_profile` - Professional profiles
- `wikipedia` - Publicly edited sources
- `interview_transcript` - Media interviews

## Example: Adding a New Manager

Let's add a new company "Example Capital Management":

```json
{
  "example_capital": {
    "company_name": "Example Capital Management LLC",
    "aum_billions": 25,
    "match_patterns": ["example capital", "example", "ecm"],
    "website": "https://www.examplecapital.com",
    "managers": [
      {
        "name": "John Doe",
        "title": "Founder & Chief Investment Officer", 
        "status": "active",
        "confidence": "high",
        "sources": ["company_website", "sec_filing_2024"],
        "start_date": "2015-01-01",
        "last_verified": "2024-12-01",
        "note": "Former hedge fund analyst at Two Sigma"
      },
      {
        "name": "Sarah Wilson",
        "title": "Portfolio Manager",
        "status": "active", 
        "confidence": "medium",
        "sources": ["company_website"],
        "start_date": "2018-06-01",
        "last_verified": "2024-12-01",
        "note": "Specializes in technology sector investments"
      }
    ]
  }
}
```

## Data Validation Checklist

Before adding entries, verify:

- [ ] Company key is lowercase with underscores
- [ ] Company name matches legal entity in SEC filings
- [ ] AUM is reasonable (check recent 13F filings)
- [ ] Match patterns are comprehensive and lowercase
- [ ] Manager names are spelled correctly (double-check sources)
- [ ] Status is appropriate (active/retired/deceased/former)
- [ ] Confidence level matches quality of sources
- [ ] Dates are in YYYY-MM-DD format
- [ ] Sources are specific and verifiable
- [ ] Notes provide helpful context

## Updating Existing Entries

### Manager Status Changes
When a manager retires, is promoted, or leaves:

```json
{
  "name": "John Smith",
  "title": "Former CEO", 
  "status": "retired",
  "end_date": "2024-06-30",
  "note": "Retired June 2024, remains on board of directors"
}
```

### Adding New Managers to Existing Companies
Simply add to the managers array:

```json
{
  "managers": [
    // ... existing managers ...
    {
      "name": "New Manager Name",
      "title": "Chief Investment Officer",
      "status": "active",
      // ... complete manager entry
    }
  ]
}
```

## Testing Your Changes

After making changes, test the functionality:

```python
import edgar

# Test with a company you added/modified
company = edgar.Company("COMPANY_TICKER")
filing = company.get_filings(form="13F-HR").head(1)[0]
thirteen_f = filing.obj()

# Check if your managers are returned
managers = thirteen_f.get_portfolio_managers()
print(f"Found managers: {managers}")

# Test manager info summary
summary = thirteen_f.get_manager_info_summary()
print(f"Manager count: {summary['external_sources']['manager_count']}")
```

## Common Mistakes to Avoid

1. **Inconsistent naming**: Use exact legal names from SEC filings
2. **Missing match patterns**: Add common abbreviations and variations
3. **Outdated information**: Always verify against recent sources
4. **Low confidence data**: Avoid unverified Wikipedia or blog sources  
5. **JSON syntax errors**: Use a JSON validator before saving
6. **Forgetting metadata**: Update total counts and last_updated date

## Priority Companies to Add

Focus on top 13F filers by AUM:

1. **Immediate Priority (AUM > $100B):**
   - Already added: BlackRock, Vanguard, Fidelity, State Street
   - Still needed: T. Rowe Price, Capital Group, Invesco

2. **High Priority (AUM $50-100B):**
   - Already added: AQR, Citadel, Two Sigma, Renaissance
   - Still needed: Millennium, D.E. Shaw, Baupost Group

3. **Medium Priority (AUM $20-50B):**
   - Already added: Elliott, Pershing Square, Icahn
   - Still needed: Third Point, ValueAct, Jana Partners

This systematic approach will provide coverage for the majority of institutional investment assets tracked in 13F filings.

---

## Enhancement Planning

**Current Status**: As of January 2025, this database covers 21 companies with verified CIKs (53.8% by count, 63.5% by AUM).

**Enhancement Roadmap**: See `docs-internal/features/FEAT-021-portfolio-manager-enhancement-followup.md` for:
- Systematic expansion plans to reach 85% AUM coverage
- Quarterly maintenance automation
- International firm integration strategy
- Historical manager tracking capabilities

**Priority Targets for Next Expansion**:
1. **Vanguard Group** ($8.1T AUM) - Research filing patterns
2. **Capital Group Companies** ($2.8T AUM) - American Funds family  
3. **T. Rowe Price Group** ($1.6T AUM) - Major active manager
4. **Wellington Management** ($1.3T AUM) - Institutional specialist

For enhancement requests or database improvements, see the follow-up planning document and contribute via GitHub issues.