# /// script
# dependencies = [
#   "edgartools>=4.25.0",
# ]
# ///
"""
ViiT Health Crowdfunding Offering Research
===========================================

LEARNING-DRIVEN RESEARCH: This script explores the ViiT Health crowdfunding
offerings to discover efficient workflows and identify API gaps.

We learn as we go, documenting what works well and what could be improved.

Research Goals:
1. Understand ViiT Health's three crowdfunding offerings (2021, 2023, 2025)
2. Discover the most efficient API patterns for offering research
3. Identify gaps in the current API
4. Document best practices for analyzing crowdfunding lifecycles
5. Test AI-native features (to_context, convenience properties, etc.)

Key Questions:
- How do we efficiently discover all offerings by a company?
- What's the best way to track offering lifecycle stages?
- How do we analyze amendments and understand what changed?
- What's missing from the API that would make this easier?
- Which approaches minimize code and maximize insight?

ViiT Health Context:
- CIK: 1881570
- Three separate offerings through Wefunder portal
- 2021: File # 020-28927 (1 filing)
- 2023: File # 020-32444 (3 filings: C + 2 C/A)
- 2025: File # 020-36002 (4 filings: C + 3 C/A)
- All use portal file # 007-00033 (Wefunder)
"""


from rich import box, print
from rich.console import Console
from rich.table import Table

from edgar import Company, set_identity
from edgar.offerings import Offering, group_offerings_by_file_number

console = Console()

# Set identity for SEC requests
set_identity('ViiT Health Researcher researcher@example.com')

print("\n" + "="*80)
print("VIIT HEALTH CROWDFUNDING OFFERING RESEARCH")
print("Learning-Driven API Exploration")
print("="*80)

# =============================================================================
# PHASE 0: RESEARCH PLAN & API APPROACH
# =============================================================================

print("\n" + "="*80)
print("PHASE 0: RESEARCH PLAN")
print("="*80 + "\n")

print("""
HIGH-LEVEL APPROACH:

Step 1: GET THE COMPANY
   Approach A: Company('ViiT Health')  # By name - requires search
   Approach B: Company('1881570')      # By CIK - direct lookup
   API Note: Which is more efficient? Test both.

Step 2: DISCOVER ALL OFFERINGS
   Approach A: company.get_filings(form=['C', 'C/A', 'C-U', 'C-AR'])
   Approach B: Use file_number filtering if we know them
   Approach C: Parse each filing to check portal_file_number
   API Question: Is there a helper to "get all campaigns"?

Step 3: ANALYZE INDIVIDUAL OFFERINGS
   Approach A: Offering(filing) - from filing object
   Approach B: formc.get_offering(filing) - from FormC object (recommended)
   Approach C: Offering('020-XXXXX', cik) - from file number
   API Note: Offering class should make lifecycle tracking easy

Step 4: AMENDMENT ANALYSIS
   Approach A: Compare FormC objects field-by-field
   Approach B: Use to_context() at different detail levels
   API Question: Is there a diff() method for comparing filings?

Step 5: FINANCIAL PROGRESSION
   Approach A: Extract financials from each offering's latest filing
   Approach B: Use campaign.latest_financials() if available
   API Question: Cross-campaign comparison tools?

EFFICIENCY GOALS:
- Minimize network calls (use caching)
- Minimize parsing (reuse parsed objects)
- Maximize insight per line of code
- Document what's easy vs hard

Let's start exploring...
""")

# =============================================================================
# PHASE 1: ENTITY & BASIC INFO
# =============================================================================

print("\n" + "="*80)
print("PHASE 1: ENTITY & BASIC INFO")
print("="*80 + "\n")

# Test both approaches to getting the company
print("🔍 Testing Company Lookup Methods:\n")

# Approach A: By name (requires search)
print("Approach A: Company name lookup")
print("  Code: Company('ViiT Health')")
print("  Note: This might require fuzzy matching...")

# Approach B: Direct CIK (recommended when known)
print("\nApproach B: Direct CIK lookup (RECOMMENDED)")
print("  Code: Company('1881570')")
viit = Company('1881570')
print(f"  ✓ Found: {viit.name}")
print(f"  ✓ CIK: {viit.cik}")

print("\n📊 Company Overview:")
print(viit)

print("\n" + "-"*80)
print("API OBSERVATION 1: Direct CIK lookup")
print("-"*80)
print("✓ Pros: Fast, no ambiguity, works even with complex names")
print("✗ Cons: Need to know CIK in advance")
print("💡 Best Practice: Use CIK when available, especially for automation")
print("-"*80)

# =============================================================================
# PHASE 2: DISCOVER ALL OFFERINGS
# =============================================================================

print("\n" + "="*80)
print("PHASE 2: DISCOVER ALL OFFERINGS")
print("="*80 + "\n")

print("🔍 Goal: Find all three ViiT Health crowdfunding campaigns\n")

# Approach A: Get all Form C variants
print("Approach A: Query all Form C filings")
print("  Code: viit.get_filings(form=['C', 'C/A', 'C-U', 'C-AR', 'C-TR'])")

all_formc_filings = viit.get_filings(form=['C', 'C/A', 'C-U', 'C-AR', 'C-TR'])
print(f"  ✓ Found {len(all_formc_filings)} total Form C filings")

# Display all filings
print("\n📋 All Form C Filings:")
print(all_formc_filings)

print("\n" + "-"*80)
print("API OBSERVATION 2: Getting all Form C filings")
print("-"*80)
print("✓ Pros: Simple, one call gets all crowdfunding activity")
print("✗ Cons: Doesn't group by campaign automatically")
print("? Question: How do we identify which filings belong to which campaign?")
print("💡 Discovery: We need to look at file_number to group them")
print("-"*80)

# Now group by campaign using file numbers
print("\n🔬 Grouping filings by campaign (issuer file number):\n")

print("Note: Each filing has TWO file numbers:")
print("  1. Issuer file # (020-XXXXX) - identifies ONE offering")
print("  2. Portal file # (007-XXXXX) - identifies the funding portal")
print("  We need the ISSUER file number to group campaigns!\n")

# Get file numbers for each filing
# Note: viit.get_filings() already returns EntityFilings (not Filing objects)
# so we can access file_number directly without conversion
campaigns_discovered = {}
for filing in all_formc_filings:
    file_num = filing.file_number  # Direct access - already an EntityFiling

    if file_num not in campaigns_discovered:
        campaigns_discovered[file_num] = []
    campaigns_discovered[file_num].append(filing)

print(f"✓ Discovered {len(campaigns_discovered)} distinct campaigns:\n")

campaigns_table = Table("Campaign", "File Number", "Filings", "Date Range", box=box.ROUNDED)
for file_num, filings in sorted(campaigns_discovered.items()):
    dates = [f.filing_date for f in filings]
    date_range = f"{min(dates)} to {max(dates)}" if len(dates) > 1 else str(dates[0])
    campaigns_table.add_row(
        f"Campaign {len(campaigns_discovered) - list(campaigns_discovered.keys()).index(file_num)}",
        file_num,
        f"{len(filings)} filing(s)",
        date_range
    )
print(campaigns_table)

print("\n" + "-"*80)
print("API OBSERVATION 3: Discovering offerings by grouping")
print("-"*80)
print("✓ Good: viit.get_filings() returns EntityFilings with file_number")
print("✓ Direct: Can access file_number without conversion")
print("✓ BETTER: Use group_offerings_by_file_number() utility!")
print("")
print("Alternative approach using utility function:")
print("  from edgar.offerings import group_offerings_by_file_number")
print("  grouped = group_offerings_by_file_number(all_formc_filings)")
print("")

# Demonstrate the utility function
print("Testing utility function:")
grouped_by_utility = group_offerings_by_file_number(all_formc_filings)
print(f"✓ Found {len(grouped_by_utility)} offerings using utility")
print(f"✓ File numbers: {', '.join(sorted(grouped_by_utility.keys()))}")
print("")
print("💡 Efficiency: Uses PyArrow operations, scales well with many filings")
print("💡 Clean: One line instead of manual loop and grouping")
print("-"*80)

# =============================================================================
# PHASE 3: OFFERING LIFECYCLE (2025 OFFERING)
# =============================================================================

print("\n" + "="*80)
print("PHASE 3: OFFERING LIFECYCLE - 2025 OFFERING")
print("="*80 + "\n")

print("🎯 Focus: Most recent offering (File # 020-36002)\n")

# Find the 2025 offering (most recent Form C)
print("Finding initial Form C filing for 2025 offering...")
recent_c_filings = viit.get_filings(form='C', amendments=False)
print(f"✓ Found {len(recent_c_filings)} initial Form C filings (no amendments)")

# Get the most recent one
if len(recent_c_filings) > 0:
    filing_2025 = recent_c_filings[0]  # Most recent due to default sort
    print(f"✓ Selected: {filing_2025.form} filed on {filing_2025.filing_date}")

    # Create Offering object - recommended approach through FormC
    print("\n📊 Creating Offering object...")
    print("  Code (Recommended):")
    print("    formc = filing_2025.obj()")
    print("    offering = formc.get_offering(filing_2025)")
    print("  Alternative:")
    print("    offering = Offering(filing_2025)")

    formc_2025 = filing_2025.obj()
    offering_2025 = formc_2025.get_offering(filing_2025)

    print("  ✓ Offering initialized")
    print(f"  ✓ Issuer file number: {offering_2025.issuer_file_number}")
    print(f"  ✓ Portal file number: {offering_2025.portal_file_number}")
    print(f"  ✓ Total filings: {len(offering_2025.all_filings)}")

    print("\n" + "-"*80)
    print("API OBSERVATION 4: Offering class initialization")
    print("-"*80)
    print("✓ Excellent: formc.get_offering(filing) is clear and explicit")
    print("✓ Smart: Offering caches EntityFiling and FormC at initialization")
    print("✓ Efficient: Avoids repeated parsing throughout lifecycle")
    print("✓ Clear: issuer_file_number vs portal_file_number distinction")
    print("✓ Flexible: Can also use Offering(filing) for direct construction")
    print("-"*80)

    # Show the offering
    print("\n📋 Offering Overview (Rich Display):")
    print(offering_2025)

    # Test the to_context() method for AI agents
    print("\n" + "-"*80)
    print("API OBSERVATION 5: Testing AI-native to_context() method")
    print("-"*80)

    print("\n🤖 Minimal Detail (~300 tokens):")
    print(offering_2025.to_context(detail='minimal'))

    print("\n" + "-"*80)
    print("✓ Excellent: to_context() provides compact, LLM-friendly summary")
    print("✓ Useful: Different detail levels for different use cases")
    print("✓ Smart: Includes computed fields (days remaining, status, etc.)")
    print("? Question: How many tokens does each detail level actually use?")
    print("💡 Enhancement: Add token counting to the method return")
    print("-"*80)

    # Access lifecycle stages
    print("\n📂 Lifecycle Stages:")
    stages_table = Table("Stage", "Count", "Forms", box=box.SIMPLE)
    stages_table.add_row("Initial", str(len(offering_2025.filings_by_stage['initial'])),
                        ", ".join([f.form for f in offering_2025.filings_by_stage['initial']]))
    stages_table.add_row("Amendments", str(len(offering_2025.filings_by_stage['amendment'])),
                        ", ".join([f.form for f in offering_2025.filings_by_stage['amendment']]))
    stages_table.add_row("Updates", str(len(offering_2025.filings_by_stage['update'])),
                        ", ".join([f.form for f in offering_2025.filings_by_stage['update']]) or "None")
    stages_table.add_row("Reports", str(len(offering_2025.filings_by_stage['report'])),
                        ", ".join([f.form for f in offering_2025.filings_by_stage['report']]) or "None")
    stages_table.add_row("Termination", str(len(offering_2025.filings_by_stage['termination'])),
                        ", ".join([f.form for f in offering_2025.filings_by_stage['termination']]) or "None")
    print(stages_table)

    print("\n" + "-"*80)
    print("API OBSERVATION 6: Lifecycle stage access")
    print("-"*80)
    print("✓ Convenient: filings_by_stage dict is well-organized")
    print("✓ Properties: initial_offering, amendments, updates, etc. are intuitive")
    print("✓ Cached: Using @cached_property for performance")
    print("? Enhancement: Would timeline() method with rich display be useful?")
    print("-"*80)

else:
    print("✗ No Form C filings found for 2025")
    offering_2025 = None

# =============================================================================
# PHASE 4: AMENDMENT ANALYSIS
# =============================================================================

print("\n" + "="*80)
print("PHASE 4: AMENDMENT ANALYSIS")
print("="*80 + "\n")

if offering_2025 and len(offering_2025.amendments) > 0:
    print(f"🔍 Analyzing {len(offering_2025.amendments)} amendments\n")

    print("Question: What changed in each amendment?")
    print("Approach: Compare to_context() output at standard detail\n")

    # Get initial offering for comparison
    initial_formc = offering_2025.initial_offering

    print("="*80)
    print("INITIAL OFFERING (Form C)")
    print("="*80)
    print(initial_formc.to_context(detail='standard', filing_date=offering_2025.launch_date))

    # Compare each amendment
    for i, amendment in enumerate(offering_2025.amendments, 1):
        print("\n" + "="*80)
        print(f"AMENDMENT {i} (Form C/A)")
        print("="*80)
        amendment_filing = offering_2025.filings_by_stage['amendment'][i-1]
        print(amendment.to_context(detail='standard', filing_date=amendment_filing.filing_date))

    print("\n" + "-"*80)
    print("API OBSERVATION 7: Amendment comparison")
    print("-"*80)
    print("✓ Good: to_context() makes manual comparison possible")
    print("✗ Limitation: No automatic diff detection")
    print("✗ Manual: Have to visually compare text output")
    print("💡 API GAP: Need a diff() or compare() method")
    print("💡 Proposed API:")
    print("   diff = offering.amendments[0].diff(offering.initial_offering)")
    print("   print(diff.changed_fields)  # ['deadline_date', 'maximum_offering_amount']")
    print("   print(diff.summary())  # Human-readable summary")
    print("-"*80)

else:
    print("✗ No amendments found for analysis")

# =============================================================================
# PHASE 5: FINANCIAL PROGRESSION
# =============================================================================

print("\n" + "="*80)
print("PHASE 5: FINANCIAL PROGRESSION ACROSS OFFERINGS")
print("="*80 + "\n")

print("🎯 Goal: Track ViiT Health's financial evolution from 2021 → 2023 → 2025\n")

print("Approach: Get latest financials from each campaign\n")

# We need to create Campaign objects for 2021 and 2023 offerings
# We already have campaign_2025

print("Creating Offering objects for all three offerings...\n")

# We know the file numbers from Phase 2
file_numbers = sorted(campaigns_discovered.keys())
print(f"Found {len(file_numbers)} offerings: {', '.join(file_numbers)}\n")

financial_progression = []

for file_num in file_numbers:
    # Get any filing from this offering to initialize
    offering_filings = campaigns_discovered[file_num]
    first_filing = offering_filings[0]

    try:
        # Create Offering from filing
        offering = Offering(first_filing)

        # Get latest financials
        financials = offering.latest_financials()

        if financials:
            financial_progression.append({
                'year': offering.launch_date.year if offering.launch_date else 'Unknown',
                'file_number': file_num,
                'launch_date': offering.launch_date,
                'assets': financials.total_asset_most_recent_fiscal_year,
                'revenue': financials.revenue_most_recent_fiscal_year,
                'net_income': financials.net_income_most_recent_fiscal_year,
                'employees': financials.current_employees,
                'is_pre_revenue': financials.is_pre_revenue
            })
    except Exception as e:
        print(f"⚠️  Could not analyze offering {file_num}: {e}")

# Display financial progression
if financial_progression:
    print("📊 Financial Progression Table:\n")

    fin_table = Table("Year", "File #", "Launch Date", "Assets", "Revenue", "Net Income",
                     "Employees", "Status", box=box.ROUNDED)

    for fp in financial_progression:
        status = "Pre-revenue" if fp['is_pre_revenue'] else "Revenue-generating"
        fin_table.add_row(
            str(fp['year']),
            fp['file_number'],
            str(fp['launch_date']),
            f"${fp['assets']:,.0f}",
            f"${fp['revenue']:,.0f}",
            f"${fp['net_income']:,.0f}" if fp['net_income'] >= 0 else f"-${abs(fp['net_income']):,.0f}",
            str(fp['employees']),
            status
        )

    print(fin_table)

    print("\n💡 Insights:")

    # Calculate growth rates
    if len(financial_progression) >= 2:
        earliest = financial_progression[0]
        latest = financial_progression[-1]

        if earliest['assets'] > 0:
            asset_growth = ((latest['assets'] - earliest['assets']) / earliest['assets']) * 100
            print(f"  • Asset growth: {asset_growth:+.1f}% from {earliest['year']} to {latest['year']}")

        if earliest['revenue'] > 0 and latest['revenue'] > 0:
            revenue_growth = ((latest['revenue'] - earliest['revenue']) / earliest['revenue']) * 100
            print(f"  • Revenue growth: {revenue_growth:+.1f}%")
        elif earliest['is_pre_revenue'] and not latest['is_pre_revenue']:
            print(f"  • Started generating revenue between {earliest['year']} and {latest['year']}")

        if earliest['employees'] > 0:
            employee_growth = latest['employees'] - earliest['employees']
            print(f"  • Employee change: {employee_growth:+d} ({earliest['employees']} → {latest['employees']})")

    print("\n" + "-"*80)
    print("API OBSERVATION 8: Cross-offering financial analysis")
    print("-"*80)
    print("✓ Possible: Can manually create Offering objects and extract financials")
    print("✗ Tedious: Have to loop through file numbers manually")
    print("✗ No helper: Would benefit from multi-offering comparison tools")
    print("💡 API GAP: Need cross-offering comparison utilities")
    print("💡 Proposed API:")
    print("   offerings = [Offering(f) for f in offering_filings]")
    print("   comparison = compare_offerings(offerings)")
    print("   print(comparison.financial_progression_table())")
    print("   print(comparison.growth_metrics())")
    print("-"*80)

else:
    print("✗ Could not extract financial data for progression analysis")

# =============================================================================
# PHASE 6: FINDINGS & API IMPROVEMENTS
# =============================================================================

print("\n" + "="*80)
print("PHASE 6: RESEARCH FINDINGS & API IMPROVEMENTS")
print("="*80 + "\n")

print("""
SUMMARY OF FINDINGS:
===================

What Works Well (✓):
- Direct CIK lookup: Fast and unambiguous
- Offering class: Well-designed, intuitive API
- formc.get_offering(filing): Clear and explicit entry point
- to_context() method: Excellent for AI/LLM integration
- Lifecycle stage grouping: Clear organization
- Property caching: Good performance optimization
- File number distinction: Clear issuer vs portal
- EntityFilings from company.get_filings(): Direct file_number access

What's Awkward/Inefficient (✗):
- Offering discovery: Manual loop and grouping by file_number
- Amendment comparison: Purely manual, no diff tools
- Cross-offering analysis: No built-in helpers
- Financial progression: Have to manually extract and compare

API GAPS DISCOVERED:
===================

1. group_offerings_by_file_number(filings) utility
   Purpose: Group Form C filings by issuer file number
   Returns: Dict[str, EntityFilings] - file_number → filings
   Benefit: Cleaner than manual looping, uses PyArrow for efficiency

2. FormC.diff(other_formc) method
   Purpose: Field-by-field comparison of two Form C filings
   Returns: Dictionary of changed fields with old/new values
   Benefit: Precise amendment tracking, automatic diff

3. compare_offerings(offerings) function
   Purpose: Cross-offering financial and timeline analysis
   Returns: Comparison object with tables, growth metrics
   Benefit: Built-in multi-offering analytics

4. Token counting in to_context()
   Purpose: Show actual token usage for each detail level
   Returns: (context_string, token_count) tuple
   Benefit: Helps optimize for LLM context windows

5. Enhanced FundingPortal navigation
   Purpose: From FormC, navigate to portal and get all offerings
   API: formc.funding_portal.get_all_offerings()
   Benefit: Portal-level analysis and discovery

EFFICIENCY LESSONS:
==================

Best Practices Discovered:
1. Use CIK when known (faster than name search)
2. company.get_filings() returns EntityFilings (direct file_number access)
3. Use formc.get_offering(filing) for explicit, clear initialization
4. Use to_context() for quick overviews before deep analysis
5. Access filings_by_stage once, then use properties
6. Cache Offering objects when doing multi-offering analysis

Code Patterns That Work:
- formc = filing.obj(); offering = formc.get_offering(filing)  # Explicit and clear
- offering = Offering(filing)  # Direct construction alternative
- for stage, filings in offering.filings_by_stage.items()  # Clean iteration
- fin = offering.latest_financials()  # Convenient helper

Code Patterns That Could Be Better:
- Manual grouping by file_number (wrap in utility function)
- Visual comparison of to_context() output (need diff method)
- Loop-and-create for multiple offerings (could use helper)

NEXT STEPS:
==========

Immediate Improvements:
1. Add group_offerings_by_file_number() utility function
2. Implement FormC.diff() for amendment comparison
3. Add compare_offerings() for multi-offering analysis

Future Enhancements:
4. Token counting in to_context()
5. Enhanced FundingPortal class with navigation methods
6. Timeline visualization improvements

Research Continuation:
- Use this script as basis for API improvement proposals
- Create test cases based on ViiT Health patterns
- Document best practices in main documentation
- Consider enhanced portal navigation (FormC → Portal → all offerings)
""")

print("\n" + "="*80)
print("RESEARCH COMPLETE")
print("="*80)
print("\nThis script serves as a living document for:")
print("  • Understanding efficient offering research workflows")
print("  • Identifying API gaps and improvement opportunities")
print("  • Demonstrating best practices")
print("  • Providing foundation for future enhancements")
