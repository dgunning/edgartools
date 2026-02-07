"""
SEC Analysis Test Cases for Skill Evaluation.

This module defines the SECAnalysisTestCase dataclass and provides a suite
of test cases across different difficulty levels and categories.

Test case design principles:
    - Each test has expected_patterns (correct API usage)
    - Each test has forbidden_patterns (anti-patterns to avoid)
    - Token budgets enforce efficiency constraints
    - Categories align with skill handoffs (financials, holdings, ownership, etc.)

Example:
    >>> from edgar.ai.evaluation.test_cases import SEC_TEST_SUITE, get_tests_by_difficulty
    >>> easy_tests = get_tests_by_difficulty("easy")
    >>> print(f"Found {len(easy_tests)} easy tests")
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SECAnalysisTestCase:
    """
    Represents a single SEC analysis test case for skill evaluation.

    Attributes:
        id: Unique identifier (e.g., "TC001")
        task: Natural language prompt describing the analysis task
        expected_patterns: Regex patterns that SHOULD appear in correct code
        forbidden_patterns: Regex patterns that should NOT appear (anti-patterns)
        max_tokens: Maximum tokens allowed for efficiency scoring
        difficulty: "easy", "medium", or "hard"
        category: Task category (lookup, filing, financial, ownership, etc.)
        description: Optional detailed description for documentation
        reference_code: Optional reference implementation for comparison
        network_required: Whether this test requires SEC API calls
        tags: Optional list of tags for filtering

    Example:
        >>> case = SECAnalysisTestCase(
        ...     id="TC001",
        ...     task="Get Apple's ticker and CIK",
        ...     expected_patterns=[r"Company\\(['\"]AAPL['\"]\\)", r"\\.cik"],
        ...     forbidden_patterns=[r"for\\s+.*\\s+in\\s+.*get_filings\\(\\)"],
        ...     max_tokens=500,
        ...     difficulty="easy",
        ...     category="lookup"
        ... )
    """

    id: str
    task: str
    expected_patterns: List[str]
    forbidden_patterns: List[str] = field(default_factory=list)
    max_tokens: int = 1000
    difficulty: str = "medium"  # easy, medium, hard
    category: str = "general"
    description: Optional[str] = None
    reference_code: Optional[str] = None
    network_required: bool = True
    tags: List[str] = field(default_factory=list)

    # Constitution goal alignment (for diagnostics)
    constitution_goals: List[str] = field(default_factory=list)
    #   Goal IDs from constitution.yaml this test measures

    # Agent evaluation fields (optional, backward compatible)
    expected_tools: List[str] = field(default_factory=list)
    #   Tools the agent SHOULD use, e.g. ["edgar_company"]
    expected_in_answer: List[str] = field(default_factory=list)
    #   Strings that MUST appear in the final answer (case-insensitive)
    max_tool_calls: int = 10
    #   Max tool calls allowed for efficiency scoring

    def __post_init__(self):
        """Validate the test case configuration."""
        valid_difficulties = {"easy", "medium", "hard"}
        if self.difficulty not in valid_difficulties:
            raise ValueError(
                f"difficulty must be one of {valid_difficulties}, got '{self.difficulty}'"
            )

        valid_categories = {
            "lookup",
            "filing",
            "counting",
            "financial",
            "ownership",
            "holdings",
            "reports",
            "comparison",
            "multi-step",
            "general",
        }
        if self.category not in valid_categories:
            raise ValueError(
                f"category must be one of {valid_categories}, got '{self.category}'"
            )


# =============================================================================
# Predefined Test Suite - Initial 10 Test Cases
# =============================================================================

SEC_TEST_SUITE: List[SECAnalysisTestCase] = [
    # -------------------------------------------------------------------------
    # EASY: Basic lookup and simple operations
    # -------------------------------------------------------------------------
    SECAnalysisTestCase(
        id="TC001",
        task="Get Apple's ticker symbol and CIK number.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",  # Uses Company("AAPL")
            r"\.cik|\.ticker",  # Accesses cik or ticker property
        ],
        forbidden_patterns=[
            r"for\s+.*\s+in\s+.*get_filings\(\)",  # No unbounded iteration
            r"get_filings\(\)\s*$",  # No get_filings() without filters
        ],
        max_tokens=300,
        difficulty="easy",
        category="lookup",
        description="Basic company lookup using Company class",
        reference_code="""
from edgar import Company
company = Company("AAPL")
print(f"Ticker: {company.ticker}, CIK: {company.cik}")
""",
        tags=["company", "basic"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Apple", "320193"],
        max_tool_calls=2,
    ),
    SECAnalysisTestCase(
        id="TC002",
        task="Get the filing date of Apple's most recent 10-K.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",  # Company lookup
            r"get_filings\(.*form=['\"]10-K['\"]",  # Filtered by form
            r"\[0\]|\.latest\(\)|\.head\(",  # Gets first filing
            r"\.filing_date|\.filed",  # Accesses date
        ],
        forbidden_patterns=[
            r"for\s+.*\s+in\s+.*get_filings\(\)",  # No unbounded iteration
        ],
        max_tokens=400,
        difficulty="easy",
        category="filing",
        description="Get most recent 10-K filing date",
        reference_code="""
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
print(f"Filing date: {filing.filing_date}")
""",
        tags=["filing", "10-K"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["10-K"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC003",
        task="Count how many 10-K filings Apple has.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",  # Company lookup
            r"get_filings\(.*form=['\"]10-K['\"]",  # Filtered by form
            r"len\(|\.shape|count",  # Counts results
        ],
        forbidden_patterns=[
            r"for\s+f\s+in\s+.*:\s*.*\+=\s*1",  # No manual counting loop
        ],
        max_tokens=400,
        difficulty="easy",
        category="counting",
        description="Count filings without iteration",
        reference_code="""
from edgar import Company
company = Company("AAPL")
filings_10k = company.get_filings(form="10-K")
print(f"Apple has {len(filings_10k)} 10-K filings")
""",
        tags=["filing", "counting"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Apple", "10-K"],
        max_tool_calls=3,
    ),
    # -------------------------------------------------------------------------
    # MEDIUM: Financial analysis and ownership
    # -------------------------------------------------------------------------
    SECAnalysisTestCase(
        id="TC004",
        task="Get Microsoft's revenue for the last 3 fiscal years.",
        expected_patterns=[
            r"Company\(['\"]MSFT['\"]\)",  # Company lookup
            # Either get_financials() or income_statement()
            r"get_financials\(\)|income_statement\(|get_revenue\(",
        ],
        forbidden_patterns=[
            r"for\s+.*\s+in\s+range\(.*3\)",  # No manual year iteration
            r"\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\)",  # No 3x XBRL parsing
        ],
        max_tokens=600,
        difficulty="medium",
        category="financial",
        description="Multi-year revenue trend using efficient API",
        reference_code="""
from edgar import Company
company = Company("MSFT")
financials = company.get_financials()
income = financials.income_statement()
print(income)  # Shows 3 years of revenue and other metrics
""",
        tags=["financial", "revenue", "multi-period"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Microsoft", "Revenue"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC005",
        task="Get Tesla's net income and total assets from the latest 10-K.",
        expected_patterns=[
            r"Company\(['\"]TSLA['\"]\)",  # Company lookup
            r"get_filings\(.*form=['\"]10-K['\"]\)|get_financials\(\)",
            # Either direct financials or XBRL
            r"net_income|income_statement|balance_sheet|get_net_income|total_assets",
        ],
        forbidden_patterns=[
            r"for\s+filing\s+in\s+.*:",  # No iteration
        ],
        max_tokens=700,
        difficulty="medium",
        category="financial",
        description="Extract multiple financial metrics",
        reference_code="""
from edgar import Company
company = Company("TSLA")
financials = company.get_financials()
net_income = financials.get_net_income()
balance = financials.balance_sheet()
print(f"Net Income: {net_income}")
print(f"Balance Sheet:\n{balance}")
""",
        tags=["financial", "net-income", "balance-sheet"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Tesla", "net income"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC006",
        task="Get recent Form 4 insider transactions for NVIDIA (NVDA).",
        expected_patterns=[
            r"Company\(['\"]NVDA['\"]\)",  # Company lookup
            r"form=['\"]4['\"]|form=['\"]Form 4['\"]",  # Form 4 filter
            r"\[0\]|\.head\(|\.latest\(\)",  # Limits results
            r"\.obj\(\)",  # Parses Form 4
        ],
        forbidden_patterns=[
            r"for\s+filing\s+in\s+company\.get_filings\(\):",  # No unbounded
        ],
        max_tokens=700,
        difficulty="medium",
        category="ownership",
        description="Form 4 insider trading lookup",
        reference_code="""
from edgar import Company
company = Company("NVDA")
form4_filings = company.get_filings(form="4").head(5)
for filing in form4_filings:
    form4 = filing.obj()
    summary = form4.get_ownership_summary()
    print(f"{summary.insider_name}: {summary.primary_activity} {summary.net_change:,} shares (${summary.net_value:,.0f})")
""",
        tags=["ownership", "form-4", "insider"],
        constitution_goals=["correctness", "routing", "efficiency", "sharp_edges"],
        expected_tools=["edgar_ownership"],
        expected_in_answer=["NVDA"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC007",
        task="Get Berkshire Hathaway's top 5 holdings from their most recent 13F.",
        expected_patterns=[
            r"Company\(['\"]BRK|CIK|berkshire",  # Berkshire lookup
            r"form=['\"]13F|13F-HR",  # 13F filter
            r"\[0\]|\.latest\(\)",  # Gets most recent
            r"\.obj\(\)",  # Parses 13F
            r"\.holdings|InfoTable",  # Accesses holdings
        ],
        forbidden_patterns=[
            r"for\s+.*\s+in\s+.*get_filings\(\):",  # No unbounded
        ],
        max_tokens=700,
        difficulty="medium",
        category="holdings",
        description="13F institutional holdings analysis",
        reference_code="""
from edgar import Company
company = Company("BRK-A")
filing = company.get_filings(form="13F-HR")[0]
thirteenf = filing.obj()
print(thirteenf.holdings.head(5))
""",
        tags=["holdings", "13F", "institutional"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_ownership"],
        expected_in_answer=["Berkshire"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC008",
        task="Extract the risk factors section from Apple's latest 10-K.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",  # Company lookup
            r"form=['\"]10-K['\"]",  # 10-K filter
            r"\[0\]|\.latest\(\)",  # Gets most recent
            r"\.obj\(\)|TenK",  # Gets TenK object
            r"risk_factors|item_1a|Item 1A",  # Risk factors access
        ],
        forbidden_patterns=[],
        max_tokens=700,
        difficulty="medium",
        category="reports",
        description="Extract specific section from 10-K",
        reference_code="""
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
tenk = filing.obj()
risk_factors = tenk.risk_factors  # Convenience property for Item 1A
print(str(risk_factors)[:2000])  # First 2000 chars
""",
        tags=["reports", "10-K", "sections"],
        constitution_goals=["correctness", "routing"],
        expected_tools=["edgar_filing"],
        expected_in_answer=["Apple", "risk"],
        max_tool_calls=3,
    ),
    # -------------------------------------------------------------------------
    # HARD: Multi-company comparison and multi-step analysis
    # -------------------------------------------------------------------------
    SECAnalysisTestCase(
        id="TC009",
        task="Compare revenue trends for Apple, Microsoft, and Google for the last 3 years.",
        expected_patterns=[
            r"AAPL|Apple",  # Apple
            r"MSFT|Microsoft",  # Microsoft
            r"GOOGL?|Google|Alphabet",  # Google
            # Efficient pattern: income_statement with periods
            r"income_statement\(|get_financials\(|get_revenue\(",
        ],
        forbidden_patterns=[
            # No individual XBRL parsing per year per company (9 calls)
            r"\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\)",
        ],
        max_tokens=1200,
        difficulty="hard",
        category="comparison",
        description="Multi-company financial comparison",
        reference_code="""
from edgar import Company

for ticker in ["AAPL", "MSFT", "GOOGL"]:
    company = Company(ticker)
    financials = company.get_financials()
    income = financials.income_statement()  # 3-year income table
    print(f"{ticker} Revenue:")
    print(income)
    print()
""",
        tags=["comparison", "multi-company", "revenue"],
        constitution_goals=["correctness", "routing", "efficiency", "token_economy"],
        expected_tools=["edgar_compare"],
        expected_in_answer=["Apple", "Microsoft"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC010",
        task="Find companies that filed an 8-K today with CEO changes.",
        expected_patterns=[
            r"get_current_filings\(\)|get_filings\(.*filing_date",  # Recent filings
            r"form=['\"]8-K['\"]",  # 8-K filter
            r"\.obj\(\)|EightK",  # Parse 8-K
            r"item_5_02|Item 5\.02|ceo|chief executive|departure|appointment",
        ],
        forbidden_patterns=[],
        max_tokens=1500,
        difficulty="hard",
        category="multi-step",
        description="Filter current filings by content",
        reference_code="""
from edgar import get_current_filings

filings_8k = get_current_filings().filter(form="8-K")
for filing in filings_8k.head(20):
    eightk = filing.obj()
    # Check for Item 5.02 (personnel changes)
    if hasattr(eightk, 'item_5_02') and eightk.item_5_02:
        text = str(eightk.item_5_02).lower()
        if 'chief executive' in text or 'ceo' in text:
            print(f"{filing.company}: {filing.filing_date}")
""",
        tags=["8-K", "current", "filtering", "ceo"],
        constitution_goals=["correctness", "routing", "sharp_edges"],
        expected_tools=["edgar_search"],
        expected_in_answer=["8-K"],
        max_tool_calls=5,
    ),
    # -------------------------------------------------------------------------
    # EASY: Additional basic lookups (TC011-TC013)
    # -------------------------------------------------------------------------
    SECAnalysisTestCase(
        id="TC011",
        task="Look up Apple's SIC code and industry description.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",
            r"\.sic|sic_description|industry",
        ],
        forbidden_patterns=[
            r"get_filings\(\)\s*$",
        ],
        max_tokens=300,
        difficulty="easy",
        category="lookup",
        description="SIC code and industry lookup",
        reference_code="""
from edgar import Company
company = Company("AAPL")
print(f"SIC: {company.sic} - {company.sic_description}")
""",
        tags=["company", "sic", "basic"],
        constitution_goals=["correctness", "routing"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Apple", "SIC"],
        max_tool_calls=2,
    ),
    SECAnalysisTestCase(
        id="TC012",
        task="Get Apple's most recent proxy statement (DEF 14A) filing date.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",
            r"form=['\"]DEF 14A['\"]",
            r"\[0\]|\.latest\(\)|\.head\(",
            r"\.filing_date|\.filed",
        ],
        forbidden_patterns=[
            r"for\s+.*\s+in\s+.*get_filings\(\):",
        ],
        max_tokens=400,
        difficulty="easy",
        category="filing",
        description="Proxy statement filing lookup",
        reference_code="""
from edgar import Company
company = Company("AAPL")
proxy = company.get_filings(form="DEF 14A")[0]
print(f"Proxy filing date: {proxy.filing_date}")
""",
        tags=["filing", "proxy", "DEF14A"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Apple", "DEF 14A"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC013",
        task="Get the items reported in Tesla's most recent 8-K filing.",
        expected_patterns=[
            r"Company\(['\"]TSLA['\"]\)",
            r"form=['\"]8-K['\"]",
            r"\[0\]|\.latest\(\)|\.head\(",
            r"\.obj\(\)|EightK",
        ],
        forbidden_patterns=[],
        max_tokens=500,
        difficulty="easy",
        category="filing",
        description="8-K items extraction",
        reference_code="""
from edgar import Company
company = Company("TSLA")
filing = company.get_filings(form="8-K")[0]
eightk = filing.obj()
print(f"Items: {eightk.items}")
print(eightk)
""",
        tags=["filing", "8-K", "items"],
        constitution_goals=["correctness", "routing", "sharp_edges"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Tesla", "8-K"],
        max_tool_calls=3,
    ),
    # -------------------------------------------------------------------------
    # MEDIUM: Financial analysis and data extraction (TC014-TC020)
    # -------------------------------------------------------------------------
    SECAnalysisTestCase(
        id="TC014",
        task="Get Apple's balance sheet for the last 2 fiscal years.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",
            r"balance_sheet|get_financials\(\)|get_facts\(\)",
        ],
        forbidden_patterns=[
            r"\.xbrl\(\).*\.xbrl\(\)",  # No repeated XBRL parsing
        ],
        max_tokens=600,
        difficulty="medium",
        category="financial",
        description="Balance sheet extraction",
        reference_code="""
from edgar import Company
company = Company("AAPL")
financials = company.get_financials()
balance = financials.balance_sheet()
print(balance)  # Shows 2-year balance sheet
""",
        tags=["financial", "balance-sheet"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Apple", "balance"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC015",
        task="Get Microsoft's cash flow statement for the last 4 quarters.",
        expected_patterns=[
            r"Company\(['\"]MSFT['\"]\)",
            r"cash_flow|get_facts\(\)",
            r"annual\s*=\s*False|quarterly",
        ],
        forbidden_patterns=[],
        max_tokens=600,
        difficulty="medium",
        category="financial",
        description="Quarterly cash flow extraction",
        reference_code="""
from edgar import Company
company = Company("MSFT")
facts = company.get_facts()
cash_flow = facts.cash_flow(periods=4, annual=False)
print(cash_flow)
""",
        tags=["financial", "cash-flow", "quarterly"],
        constitution_goals=["correctness", "routing"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Microsoft", "cash"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC016",
        task="Compare Apple and Microsoft revenue for the last 3 years.",
        expected_patterns=[
            r"AAPL|Apple",
            r"MSFT|Microsoft",
            r"income_statement|get_revenue|get_financials|get_facts",
        ],
        forbidden_patterns=[
            r"\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\)",
        ],
        max_tokens=800,
        difficulty="medium",
        category="comparison",
        description="Two-company revenue comparison",
        reference_code="""
from edgar import Company

for ticker in ["AAPL", "MSFT"]:
    company = Company(ticker)
    financials = company.get_financials()
    income = financials.income_statement()  # 3-year income table
    print(f"{ticker}:")
    print(income)
    print()
""",
        tags=["comparison", "revenue", "two-company"],
        constitution_goals=["correctness", "routing", "efficiency", "token_economy"],
        expected_tools=["edgar_compare"],
        expected_in_answer=["Apple", "Microsoft"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC017",
        task="Get Berkshire Hathaway's top 10 holdings from their most recent 13F-HR filing.",
        expected_patterns=[
            r"Company|1067983|BRK",
            r"form=['\"]13F-HR['\"]|form=['\"]13F",
            r"\[0\]|\.latest\(\)|\.head\(",
            r"\.obj\(\)",
        ],
        forbidden_patterns=[],
        max_tokens=700,
        difficulty="medium",
        category="holdings",
        description="13F holdings with specific count",
        reference_code="""
from edgar import Company
company = Company("BRK-A")
filing = company.get_filings(form="13F-HR")[0]
thirteenf = filing.obj()
print(thirteenf.holdings.head(10))
""",
        tags=["holdings", "13F", "berkshire"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_ownership"],
        expected_in_answer=["Berkshire"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC018",
        task="Search for the 5 most recent 10-K filings across all companies.",
        expected_patterns=[
            r"get_filings\(",
            r"form=['\"]10-K['\"]",
            r"\.head\(5\)|\[:5\]",
        ],
        forbidden_patterns=[
            r"list\(.*get_filings",  # No list() materialization
        ],
        max_tokens=400,
        difficulty="medium",
        category="filing",
        description="Global filing search with limit",
        reference_code="""
from edgar import get_filings
filings = get_filings(form="10-K").head(5)
for f in filings:
    print(f"{f.company}: {f.filing_date}")
""",
        tags=["filing", "search", "global"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_search"],
        expected_in_answer=["10-K"],
        max_tool_calls=2,
    ),
    SECAnalysisTestCase(
        id="TC019",
        task="Look up the SEC filing with accession number 0000320193-23-000077.",
        expected_patterns=[
            r"find\(|Filing\(",
            r"0000320193-23-000077",
        ],
        forbidden_patterns=[],
        max_tokens=400,
        difficulty="medium",
        category="filing",
        description="Filing lookup by accession number",
        reference_code="""
from edgar import find
filing = find("0000320193-23-000077")
print(f"{filing.form} filed by {filing.company} on {filing.filing_date}")
""",
        tags=["filing", "accession", "lookup"],
        constitution_goals=["correctness", "routing"],
        expected_tools=["edgar_filing"],
        expected_in_answer=["0000320193-23-000077"],
        max_tool_calls=2,
    ),
    SECAnalysisTestCase(
        id="TC020",
        task="Extract the MD&A section from Microsoft's latest 10-K.",
        expected_patterns=[
            r"Company\(['\"]MSFT['\"]\)",
            r"form=['\"]10-K['\"]",
            r"\.obj\(\)|TenK",
            r"mda|item_7|item7|management_discussion",
        ],
        forbidden_patterns=[],
        max_tokens=700,
        difficulty="medium",
        category="reports",
        description="MD&A section extraction from 10-K",
        reference_code="""
from edgar import Company
company = Company("MSFT")
filing = company.get_filings(form="10-K")[0]
tenk = filing.obj()
mda = tenk.management_discussion  # Convenience property for Item 7
print(str(mda)[:2000])
""",
        tags=["reports", "10-K", "mda", "sections"],
        constitution_goals=["correctness", "routing"],
        expected_tools=["edgar_filing"],
        expected_in_answer=["Microsoft"],
        max_tool_calls=3,
    ),
    # -------------------------------------------------------------------------
    # HARD: Complex multi-step analysis (TC021-TC025)
    # -------------------------------------------------------------------------
    SECAnalysisTestCase(
        id="TC021",
        task="Find the top 5 largest insider purchases by value for NVIDIA in the last 20 Form 4 filings.",
        expected_patterns=[
            r"Company\(['\"]NVDA['\"]\)",
            r"form=['\"]4['\"]",
            r"\.obj\(\)",
            r"\.head\(|\.latest\(\)|\[:20\]|\[0\]",
            r"sort|max|largest|value|price.*shares",
        ],
        forbidden_patterns=[
            r"for\s+.*\s+in\s+.*get_filings\(\):",  # No unbounded
        ],
        max_tokens=1200,
        difficulty="hard",
        category="ownership",
        description="Insider purchases ranked by value",
        reference_code="""
from edgar import Company
company = Company("NVDA")
form4s = company.get_filings(form="4").head(20)
purchases = []
for filing in form4s:
    f4 = filing.obj()
    summary = f4.get_ownership_summary()
    if summary.primary_activity == 'Purchase':
        purchases.append((summary.insider_name, summary.net_value, filing.filing_date))
purchases.sort(key=lambda x: x[1], reverse=True)
for name, val, date in purchases[:5]:
    print(f"{name}: ${val:,.0f} on {date}")
""",
        tags=["ownership", "form-4", "insider", "ranking"],
        constitution_goals=["correctness", "routing", "efficiency", "sharp_edges"],
        expected_tools=["edgar_ownership"],
        expected_in_answer=["NVDA"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC022",
        task="Compare revenue, net income, and total assets for Apple, Microsoft, and Google.",
        expected_patterns=[
            r"AAPL|Apple",
            r"MSFT|Microsoft",
            r"GOOGL?|Google|Alphabet",
            r"income_statement|get_facts|get_financials",
            r"balance_sheet|total_assets|assets",
        ],
        forbidden_patterns=[
            r"\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\)",
        ],
        max_tokens=1500,
        difficulty="hard",
        category="comparison",
        description="Three-company multi-metric comparison",
        reference_code="""
from edgar import Company

for ticker in ["AAPL", "MSFT", "GOOGL"]:
    company = Company(ticker)
    financials = company.get_financials()
    revenue = financials.get_revenue()
    net_income = financials.get_net_income()
    total_assets = financials.get_total_assets()
    print(f"{ticker}: Revenue=${revenue:,} NI=${net_income:,} Assets=${total_assets:,}")
""",
        tags=["comparison", "multi-company", "multi-metric"],
        constitution_goals=["correctness", "routing", "efficiency", "token_economy"],
        expected_tools=["edgar_compare"],
        expected_in_answer=["Apple", "Microsoft"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC023",
        task="Get today's 8-K filings and list the companies and items reported.",
        expected_patterns=[
            r"get_current_filings\(\)",
            r"form=['\"]8-K['\"]|filter\(.*8-K",
            r"\.obj\(\)|EightK",
            r"\.head\(|\.latest|\[:.*\]",
        ],
        forbidden_patterns=[],
        max_tokens=1000,
        difficulty="hard",
        category="multi-step",
        description="Current 8-K filtering and content extraction",
        reference_code="""
from edgar import get_current_filings

filings = get_current_filings().filter(form="8-K")
for filing in filings.head(10):
    eightk = filing.obj()
    print(f"{filing.company} ({filing.filing_date}): {eightk}")
""",
        tags=["8-K", "current", "filtering"],
        constitution_goals=["correctness", "routing", "sharp_edges"],
        expected_tools=["edgar_search"],
        expected_in_answer=["8-K"],
        max_tool_calls=5,
    ),
    SECAnalysisTestCase(
        id="TC024",
        task="Calculate Apple's gross margin trend over the last 4 years using income statement data.",
        expected_patterns=[
            r"Company\(['\"]AAPL['\"]\)",
            r"income_statement|get_facts|get_financials",
            r"gross|margin|revenue|cost",
        ],
        forbidden_patterns=[
            r"\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\).*\.xbrl\(\)",
        ],
        max_tokens=1200,
        difficulty="hard",
        category="financial",
        description="Gross margin trend calculation",
        reference_code="""
from edgar import Company
company = Company("AAPL")
facts = company.get_facts()
income = facts.income_statement(periods=4, annual=True)
print(income)
# Gross margin = (Revenue - Cost of Revenue) / Revenue
""",
        tags=["financial", "margin", "trend"],
        constitution_goals=["correctness", "routing", "efficiency"],
        expected_tools=["edgar_company"],
        expected_in_answer=["Apple", "gross", "margin"],
        max_tool_calls=3,
    ),
    SECAnalysisTestCase(
        id="TC025",
        task="Given the company name 'Alphabet Inc', find their CIK, get their latest 10-K, and extract the risk factors section.",
        expected_patterns=[
            r"Company\(|find_company|Alphabet|GOOGL",
            r"form=['\"]10-K['\"]",
            r"\.obj\(\)|TenK",
            r"risk_factors|item_1a|item1a|Item 1A",
        ],
        forbidden_patterns=[],
        max_tokens=1500,
        difficulty="hard",
        category="multi-step",
        description="Multi-step: name to company to filing to section",
        reference_code="""
from edgar import Company
company = Company("GOOGL")
print(f"CIK: {company.cik}")
filing = company.get_filings(form="10-K")[0]
tenk = filing.obj()
risk_factors = tenk.risk_factors  # Convenience property for Item 1A
print(str(risk_factors)[:2000])
""",
        tags=["multi-step", "10-K", "risk-factors", "name-resolution"],
        constitution_goals=["correctness", "routing", "token_economy"],
        expected_tools=["edgar_company", "edgar_filing"],
        expected_in_answer=["Alphabet", "risk"],
        max_tool_calls=4,
    ),
]


# =============================================================================
# Helper Functions for Test Suite Access
# =============================================================================


def get_test_by_id(test_id: str) -> Optional[SECAnalysisTestCase]:
    """
    Get a test case by its ID.

    Args:
        test_id: Test case ID (e.g., "TC001")

    Returns:
        SECAnalysisTestCase or None if not found

    Example:
        >>> test = get_test_by_id("TC001")
        >>> print(test.task)
        "Get Apple's ticker symbol and CIK number."
    """
    for test in SEC_TEST_SUITE:
        if test.id == test_id:
            return test
    return None


def get_tests_by_category(category: str) -> List[SECAnalysisTestCase]:
    """
    Get all test cases in a specific category.

    Args:
        category: Category name (lookup, filing, financial, etc.)

    Returns:
        List of matching test cases

    Example:
        >>> financial_tests = get_tests_by_category("financial")
        >>> print(f"Found {len(financial_tests)} financial tests")
    """
    return [test for test in SEC_TEST_SUITE if test.category == category]


def get_tests_by_difficulty(difficulty: str) -> List[SECAnalysisTestCase]:
    """
    Get all test cases at a specific difficulty level.

    Args:
        difficulty: "easy", "medium", or "hard"

    Returns:
        List of matching test cases

    Example:
        >>> easy_tests = get_tests_by_difficulty("easy")
        >>> print(f"Found {len(easy_tests)} easy tests")
    """
    return [test for test in SEC_TEST_SUITE if test.difficulty == difficulty]


def get_tests_by_tag(tag: str) -> List[SECAnalysisTestCase]:
    """
    Get all test cases with a specific tag.

    Args:
        tag: Tag to filter by (e.g., "financial", "10-K")

    Returns:
        List of matching test cases

    Example:
        >>> tenk_tests = get_tests_by_tag("10-K")
    """
    return [test for test in SEC_TEST_SUITE if tag in test.tags]


def get_tests_not_requiring_network() -> List[SECAnalysisTestCase]:
    """
    Get test cases that don't require network access.

    Returns:
        List of test cases with network_required=False

    Note:
        Currently all tests require network for SEC API.
        This is useful for future mock-based tests.
    """
    return [test for test in SEC_TEST_SUITE if not test.network_required]
