"""
Offline evaluation framework tests.

Verifies that the evaluation framework (pattern compliance + token efficiency)
works correctly without any network calls or LLM generation. Uses pre-written
reference code samples evaluated against test case criteria.
"""

import pytest

from edgar.ai.evaluation.test_cases import (
    SEC_TEST_SUITE,
    get_test_by_id,
    get_tests_by_difficulty,
    get_tests_not_requiring_network,
)
from edgar.ai.evaluation.evaluators import evaluate_code


# =============================================================================
# Reference code samples (hand-written, not LLM-generated)
# =============================================================================

REFERENCE_SAMPLES = {
    # TC001 - Easy: Basic company lookup
    "TC001": '''
from edgar import Company
company = Company("AAPL")
print(f"Ticker: {company.ticker}, CIK: {company.cik}")
''',
    # TC002 - Easy: Most recent 10-K filing date
    "TC002": '''
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
print(f"Filing date: {filing.filing_date}")
''',
    # TC003 - Easy: Count 10-K filings
    "TC003": '''
from edgar import Company
company = Company("AAPL")
filings_10k = company.get_filings(form="10-K")
print(f"Apple has {len(filings_10k)} 10-K filings")
''',
    # TC005 - Medium: Net income and total assets
    "TC005": '''
from edgar import Company
company = Company("TSLA")
financials = company.get_financials()
net_income = financials.get_net_income()
balance = financials.balance_sheet()
print(f"Net Income: {net_income}")
print(f"Balance Sheet:\\n{balance}")
''',
    # TC009 - Hard: Multi-company revenue comparison
    "TC009": '''
from edgar import Company

for ticker in ["AAPL", "MSFT", "GOOGL"]:
    company = Company(ticker)
    financials = company.get_financials()
    income = financials.income_statement()
    print(f"{ticker} Revenue:")
    print(income)
    print()
''',
    # TC017 - Medium: 13F holdings
    "TC017": '''
from edgar import Company
company = Company("BRK-A")
filing = company.get_filings(form="13F-HR")[0]
thirteenf = filing.obj()
print(thirteenf.holdings.head(10))
''',
    # TC025 - Hard: Multi-step name to risk factors
    "TC025": '''
from edgar import Company
company = Company("GOOGL")
print(f"CIK: {company.cik}")
filing = company.get_filings(form="10-K")[0]
tenk = filing.obj()
risk_factors = tenk.risk_factors
print(str(risk_factors)[:2000])
''',
    # TC026 - Easy: Fund lookup by ticker
    "TC026": '''
from edgar import Fund
fund = Fund("VFINX")
print(f"Name: {fund.name}, Ticker: {fund.ticker}")
''',
    # TC027 - Medium: Fund NPORT portfolio
    "TC027": '''
from edgar import Fund
fund = Fund("VFINX")
filing = fund.get_filings(form="NPORT-P")[0]
nport = filing.obj()
print(nport)
''',
    # TC028 - Medium: Money market fund portfolio
    "TC028": '''
from edgar import Company
company = Company("0000036405")
filing = company.get_filings(form="N-MFP3")[0]
mmf = filing.obj()
portfolio = mmf.portfolio_data()
print(portfolio)
''',
    # TC029 - Medium: Search funds by name
    "TC029": '''
from edgar import find_funds
results = find_funds("Vanguard")
for fund in results[:10]:
    print(fund)
''',
    # TC030 - Hard: Multi-step fund pipeline
    "TC030": '''
from edgar import Fund
fund = Fund("VFINX")
print(f"Fund: {fund.name}")
filing = fund.get_filings(form="NPORT-P")[0]
nport = filing.obj()
print(nport)
''',
    # TC031 - Easy: 10-Q items
    "TC031": '''
from edgar import Company
company = Company("TSLA")
filing = company.get_filings(form="10-Q")[0]
tenq = filing.obj()
print(f"Items: {tenq.items}")
print(tenq)
''',
    # TC032 - Medium: 8-K Item 2.02
    "TC032": '''
from edgar import Company
company = Company("MSFT")
filings_8k = company.get_filings(form="8-K").head(10)
for filing in filings_8k:
    eightk = filing.obj()
    if hasattr(eightk, 'item_2_02') and eightk.item_2_02:
        print(f"Item 2.02: {str(eightk.item_2_02)[:500]}")
        break
''',
    # TC033 - Medium: Auditor info from 10-K
    "TC033": '''
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
tenk = filing.obj()
auditor = tenk.auditor
print(f"Auditor: {auditor}")
''',
    # TC034 - Medium: Subsidiaries from 10-K
    "TC034": '''
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
tenk = filing.obj()
subsidiaries = tenk.subsidiaries
print(subsidiaries)
''',
    # TC035 - Hard: Compare risk factors
    "TC035": '''
from edgar import Company

for ticker in ["AAPL", "MSFT"]:
    company = Company(ticker)
    filing = company.get_filings(form="10-K")[0]
    tenk = filing.obj()
    risk_factors = tenk.risk_factors
    print(f"{ticker} Risk Factors:")
    print(str(risk_factors)[:2000])
    print()
''',
    # TC036 - Easy: Safe filing check
    "TC036": '''
from edgar import Company
company = Company("AAPL")
filings = company.get_filings(form="10-K")
if len(filings) > 0:
    filing = filings[0]
    print(f"Latest 10-K: {filing.filing_date}")
else:
    print("No 10-K filings found")
''',
    # TC037 - Medium: Financials with fallback
    "TC037": '''
from edgar import Company
company = Company("AAPL")
try:
    financials = company.get_financials()
    income = financials.income_statement()
    print(income)
except Exception as e:
    print(f"Could not retrieve financials: {e}")
''',
    # TC038 - Medium: Bounded iteration with .head()
    "TC038": '''
from edgar import Company
company = Company("AAPL")
filings = company.get_filings(form="10-K").head(5)
for filing in filings:
    print(f"{filing.filing_date}: {filing.form}")
''',
    # TC039 - Hard: Multi-company with error recovery
    "TC039": '''
from edgar import Company

for ticker in ["AAPL", "MSFT", "GOOGL"]:
    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K")[0]
        print(f"{ticker}: {filing.filing_date}")
    except Exception as e:
        print(f"{ticker}: Error - {e}")
        continue
''',
    # TC040 - Medium: XBRL availability check
    "TC040": '''
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
try:
    xbrl = filing.xbrl()
    if xbrl is not None:
        print(f"XBRL available with {len(xbrl.facts)} facts")
    else:
        print("No XBRL data")
except Exception as e:
    print(f"XBRL parsing failed: {e}")
''',
    # TC041 - Medium: XBRL fact query
    "TC041": '''
from edgar import Company
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
xbrl = filing.xbrl()
revenue = xbrl.facts.query().by_concept("Revenue").to_dataframe()
print(revenue)
''',
    # TC042 - Hard: Schedule 13D analysis
    "TC042": '''
from edgar import Company
company = Company("AAPL")
filings = company.get_filings(form="SC 13D").head(5)
if len(filings) > 0:
    filing = filings[0]
    schedule = filing.obj()
    print(f"Issuer: {schedule.issuer_info}")
    for person in schedule.reporting_persons:
        print(f"  {person.name}: {person.percent_of_class}%")
''',
}

# Anti-pattern code samples (should score poorly on pattern compliance)
ANTI_PATTERN_SAMPLES = {
    # TC001 but with forbidden patterns
    "TC001_bad": '''
from edgar import Company
company = Company("AAPL")
for f in company.get_filings():
    print(f)
''',
    # TC003 but manually counting instead of len()
    "TC003_bad": '''
from edgar import Company
company = Company("AAPL")
filings = company.get_filings(form="10-K")
count = 0
for f in filings:
    count += 1
print(f"Apple has {count} 10-K filings")
''',
    # TC026 but using Company instead of Fund
    "TC026_bad": '''
from edgar import Company
company = Company("VFINX")
print(f"Name: {company.name}")
''',
    # TC038 but with unbounded iteration
    "TC038_bad": '''
from edgar import Company
company = Company("AAPL")
for filing in company.get_filings():
    print(f"{filing.filing_date}: {filing.form}")
''',
}


# =============================================================================
# Test suite metadata tests
# =============================================================================


@pytest.mark.fast
class TestTestSuiteMetadata:
    """Verify test suite structure and helper functions."""

    def test_suite_has_42_test_cases(self):
        assert len(SEC_TEST_SUITE) == 42

    def test_all_test_cases_have_unique_ids(self):
        ids = [tc.id for tc in SEC_TEST_SUITE]
        assert len(ids) == len(set(ids))

    def test_difficulty_distribution(self):
        easy = get_tests_by_difficulty("easy")
        medium = get_tests_by_difficulty("medium")
        hard = get_tests_by_difficulty("hard")
        assert len(easy) >= 9
        assert len(medium) >= 13
        assert len(hard) >= 6
        assert len(easy) + len(medium) + len(hard) == 42

    def test_all_tests_marked_no_network(self):
        """Pattern+efficiency evaluation doesn't need network."""
        offline_tests = get_tests_not_requiring_network()
        assert len(offline_tests) == 42

    def test_get_test_by_id(self):
        tc = get_test_by_id("TC001")
        assert tc is not None
        assert tc.difficulty == "easy"
        assert tc.category == "lookup"

    def test_get_test_by_id_missing(self):
        assert get_test_by_id("TC999") is None


# =============================================================================
# Pattern compliance tests
# =============================================================================


@pytest.mark.fast
class TestPatternCompliance:
    """Verify pattern matching evaluator with known-good code."""

    @pytest.mark.parametrize("tc_id", list(REFERENCE_SAMPLES.keys()))
    def test_reference_code_scores_high(self, tc_id):
        """Reference code from test cases should score well on patterns."""
        test_case = get_test_by_id(tc_id)
        code = REFERENCE_SAMPLES[tc_id]
        result = evaluate_code(code, test_case, execute=False)
        assert result.pattern.score >= 0.75, (
            f"{tc_id}: pattern score {result.pattern.score} < 0.75. "
            f"Missing: {[p for p, found in result.pattern.expected_matches if not found]}"
        )

    @pytest.mark.parametrize("tc_id", list(REFERENCE_SAMPLES.keys()))
    def test_reference_code_no_forbidden_violations(self, tc_id):
        """Reference code should not trigger forbidden pattern violations."""
        test_case = get_test_by_id(tc_id)
        code = REFERENCE_SAMPLES[tc_id]
        result = evaluate_code(code, test_case, execute=False)
        violations = [p for p, found in result.pattern.forbidden_violations if found]
        assert len(violations) == 0, f"{tc_id}: forbidden patterns found: {violations}"

    def test_anti_pattern_tc001_has_violation(self):
        """Code with forbidden patterns should be flagged."""
        test_case = get_test_by_id("TC001")
        code = ANTI_PATTERN_SAMPLES["TC001_bad"]
        result = evaluate_code(code, test_case, execute=False)
        violations = [p for p, found in result.pattern.forbidden_violations if found]
        assert len(violations) > 0, "Expected forbidden pattern violation for unbounded iteration"

    def test_anti_pattern_tc026_has_violation(self):
        """Fund lookup using Company() should trigger forbidden pattern."""
        test_case = get_test_by_id("TC026")
        code = ANTI_PATTERN_SAMPLES["TC026_bad"]
        result = evaluate_code(code, test_case, execute=False)
        violations = [p for p, found in result.pattern.forbidden_violations if found]
        assert len(violations) > 0, "Expected forbidden pattern violation for using Company instead of Fund"

    def test_anti_pattern_tc038_has_violation(self):
        """Unbounded iteration should trigger forbidden pattern."""
        test_case = get_test_by_id("TC038")
        code = ANTI_PATTERN_SAMPLES["TC038_bad"]
        result = evaluate_code(code, test_case, execute=False)
        violations = [p for p, found in result.pattern.forbidden_violations if found]
        assert len(violations) > 0, "Expected forbidden pattern violation for unbounded iteration"

    def test_anti_pattern_tc003_scores_lower(self):
        """Manual counting loop should score lower than len()."""
        test_case = get_test_by_id("TC003")
        good_code = REFERENCE_SAMPLES["TC003"]
        bad_code = ANTI_PATTERN_SAMPLES["TC003_bad"]
        good_result = evaluate_code(good_code, test_case, execute=False)
        bad_result = evaluate_code(bad_code, test_case, execute=False)
        assert good_result.overall_score >= bad_result.overall_score


# =============================================================================
# Token efficiency tests
# =============================================================================


@pytest.mark.fast
class TestTokenEfficiency:
    """Verify token efficiency evaluator."""

    @pytest.mark.parametrize("tc_id", list(REFERENCE_SAMPLES.keys()))
    def test_reference_code_within_budget(self, tc_id):
        """Reference code should be within token budget."""
        test_case = get_test_by_id(tc_id)
        code = REFERENCE_SAMPLES[tc_id]
        result = evaluate_code(code, test_case, execute=False)
        assert result.efficiency.efficiency_score > 0.0, (
            f"{tc_id}: efficiency score is 0 "
            f"(tokens={result.efficiency.token_count}, max={test_case.max_tokens})"
        )

    def test_bloated_code_scores_lower(self):
        """Unnecessarily verbose code should get lower efficiency score."""
        test_case = get_test_by_id("TC001")
        concise = REFERENCE_SAMPLES["TC001"]
        bloated = concise + "\n" + "# " * 200 + "\n" + "pass\n" * 50
        concise_result = evaluate_code(concise, test_case, execute=False)
        bloated_result = evaluate_code(bloated, test_case, execute=False)
        assert concise_result.efficiency.efficiency_score >= bloated_result.efficiency.efficiency_score


# =============================================================================
# Combined evaluation tests
# =============================================================================


@pytest.mark.fast
class TestCombinedEvaluation:
    """Verify the combined evaluation pipeline."""

    def test_evaluate_code_returns_combined_result(self):
        """evaluate_code returns CombinedEvaluation with all fields."""
        test_case = get_test_by_id("TC001")
        code = REFERENCE_SAMPLES["TC001"]
        result = evaluate_code(code, test_case, execute=False)
        assert hasattr(result, "execution")
        assert hasattr(result, "pattern")
        assert hasattr(result, "efficiency")
        assert hasattr(result, "overall_score")
        assert 0.0 <= result.overall_score <= 1.0

    def test_no_execute_skips_execution(self):
        """With execute=False, execution result should be synthetic success."""
        test_case = get_test_by_id("TC001")
        code = REFERENCE_SAMPLES["TC001"]
        result = evaluate_code(code, test_case, execute=False)
        assert result.execution.success is True
        assert result.execution.output == "(not executed)"

    def test_weights_without_execution(self):
        """Without execution, weights should be pattern=0.7, efficiency=0.3."""
        test_case = get_test_by_id("TC001")
        code = REFERENCE_SAMPLES["TC001"]
        result = evaluate_code(code, test_case, execute=False)
        # Overall should be: 0.7 * pattern + 0.3 * efficiency
        expected = round(
            0.7 * result.pattern.score + 0.3 * result.efficiency.efficiency_score,
            3,
        )
        assert result.overall_score == expected

    def test_to_dict_serialization(self):
        """CombinedEvaluation.to_dict() should produce serializable output."""
        test_case = get_test_by_id("TC001")
        code = REFERENCE_SAMPLES["TC001"]
        result = evaluate_code(code, test_case, execute=False)
        d = result.to_dict()
        assert "execution" in d
        assert "pattern" in d
        assert "efficiency" in d
        assert "overall_score" in d
        assert isinstance(d["overall_score"], float)
