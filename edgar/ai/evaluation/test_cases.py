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
revenue = financials.get_revenue()
print(revenue)
""",
        tags=["financial", "revenue", "multi-period"],
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
    print(form4)
""",
        tags=["ownership", "form-4", "insider"],
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
company = Company("BRK-A")  # or CIK
filing_13f = company.get_filings(form="13F-HR")[0]
holdings = filing_13f.obj()
print(holdings.holdings.head(5))
""",
        tags=["holdings", "13F", "institutional"],
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
risk_factors = tenk.item_1a
print(risk_factors[:2000])  # First 2000 chars
""",
        tags=["reports", "10-K", "sections"],
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
    print(f"{ticker} Revenue:")
    print(financials.get_revenue())
    print()
""",
        tags=["comparison", "multi-company", "revenue"],
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
