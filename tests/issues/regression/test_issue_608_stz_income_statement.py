"""
Regression test for Issue #608: STZ 2023-2025 Income Statements almost entirely empty.

The issue was caused by the statement resolver falling back from IncomeStatement to
ComprehensiveIncome without properly validating that the selected statement contains
actual P&L data (Revenue, Operating Income, etc.).

STZ has two ComprehensiveIncome roles:
- ConsolidatedStatementsofComprehensiveIncomeLoss: Contains actual P&L data
- ConsolidatedStatementsofComprehensiveIncomeLoss_1: Contains only OCI items

The resolver was selecting the wrong one (pure OCI) because it was sorting candidates
by ComprehensiveIncome criteria instead of IncomeStatement criteria.

Fix: edgar/xbrl/statement_resolver.py now:
1. Re-sorts ComprehensiveIncome candidates by IncomeStatement criteria when used as fallback
2. Validates the selected statement contains P&L data (Revenue concepts) before using it

GitHub Issue: https://github.com/dgunning/edgartools/issues/608
"""
import pytest
from edgar import Filing


# STZ 10-K filings with known issues (2023-2025)
STZ_TEST_CASES = [
    # (year, accession, filing_date, period_end)
    ("2025", "0000016918-25-000022", "2025-04-23", "2025-02-28"),
    ("2024", "0000016918-24-000054", "2024-04-23", "2024-02-29"),
    ("2023", "0000016918-23-000045", "2023-04-20", "2023-02-28"),
]


@pytest.mark.network
@pytest.mark.parametrize("year,accession,filing_date,period_end", STZ_TEST_CASES)
def test_stz_income_statement_has_revenue(year, accession, filing_date, period_end):
    """
    Verify STZ income statements contain P&L data (Revenue, Gross Profit, etc).

    Issue #608: STZ income statements were returning only OCI items (foreign currency
    adjustments, hedging gains/losses) instead of actual P&L data because the resolver
    selected the wrong ComprehensiveIncome role.
    """
    filing = Filing(
        form="10-K",
        company="CONSTELLATION BRANDS, INC.",
        cik=16918,
        accession_no=accession,
        filing_date=filing_date
    )

    xbrl = filing.xbrl()
    assert xbrl is not None, f"Failed to load XBRL for STZ {year}"

    income = xbrl.statements.income_statement()
    assert income is not None, f"Income statement not found for STZ {year}"

    df = income.to_dataframe()
    assert not df.empty, f"Empty DataFrame for STZ {year}"

    # Check for essential P&L concepts
    concepts = df['concept'].tolist() if 'concept' in df.columns else []
    concept_str = ' '.join(str(c) for c in concepts).lower()

    # Must have Revenue concept
    has_revenue = any(keyword in concept_str for keyword in [
        'revenue', 'sales', 'netsales'
    ])
    assert has_revenue, (
        f"STZ {year} income statement missing Revenue concept. "
        f"Found concepts: {concepts[:5]}... "
        f"This indicates the resolver may be selecting pure OCI statement."
    )

    # Must have Cost of Goods/Services concept
    has_cogs = any(keyword in concept_str for keyword in [
        'costofgoods', 'costofrevenue', 'costofservices', 'costofproduct'
    ])
    assert has_cogs, (
        f"STZ {year} income statement missing Cost concept. "
        f"This indicates the resolver may be selecting pure OCI statement."
    )

    # Must have Operating Income concept
    has_operating_income = 'operatingincome' in concept_str
    assert has_operating_income, (
        f"STZ {year} income statement missing Operating Income concept. "
        f"This indicates the resolver may be selecting pure OCI statement."
    )


@pytest.mark.network
def test_stz_comprehensive_income_fallback_validation():
    """
    Test that the ComprehensiveIncome fallback validates P&L content.

    When no pure IncomeStatement is found and the resolver falls back to
    ComprehensiveIncome, it should validate that the selected statement
    contains actual P&L data (Revenue) and not just OCI items.
    """
    # STZ FY2025 - has two ComprehensiveIncome roles
    filing = Filing(
        form="10-K",
        company="CONSTELLATION BRANDS, INC.",
        cik=16918,
        accession_no="0000016918-25-000022",
        filing_date="2025-04-23"
    )

    xbrl = filing.xbrl()

    # Verify STZ has multiple ComprehensiveIncome roles (the problematic condition)
    statements = xbrl.get_all_statements()
    comp_income_roles = [s for s in statements if s.get('type') == 'ComprehensiveIncome']

    assert len(comp_income_roles) >= 2, (
        f"Test setup may be invalid: Expected STZ to have multiple ComprehensiveIncome roles, "
        f"found {len(comp_income_roles)}"
    )

    # Verify the resolver selects the correct one (with P&L data)
    from edgar.xbrl.statement_resolver import StatementResolver
    resolver = StatementResolver(xbrl)

    stmts, role, canonical_type, confidence = resolver.find_statement('IncomeStatement')

    assert role is not None, "Should find an IncomeStatement (via ComprehensiveIncome fallback)"

    # Verify the selected role is the one with P&L data, not pure OCI
    # The correct role should NOT end with '_1' (the pure OCI role)
    role_name = role.split('/')[-1] if role else ""
    assert not role_name.endswith('_1'), (
        f"Resolver selected wrong role: {role_name}. "
        f"Should select ConsolidatedStatementsofComprehensiveIncomeLoss (with P&L data), "
        f"not ConsolidatedStatementsofComprehensiveIncomeLoss_1 (pure OCI)."
    )


@pytest.mark.network
def test_stz_statement_has_sufficient_rows():
    """
    Verify STZ income statement has a reasonable number of line items.

    Issue #608: Before the fix, STZ income statements had only ~10 rows (OCI items).
    After the fix, they should have 30+ rows (full P&L).
    """
    filing = Filing(
        form="10-K",
        company="CONSTELLATION BRANDS, INC.",
        cik=16918,
        accession_no="0000016918-25-000022",
        filing_date="2025-04-23"
    )

    xbrl = filing.xbrl()
    income = xbrl.statements.income_statement()

    df = income.to_dataframe()

    # A proper income statement should have at least 20 line items
    # (Revenue, COGS, Gross Profit, SG&A, Operating Income, Interest, Tax, Net Income, EPS, etc.)
    min_rows = 20
    assert len(df) >= min_rows, (
        f"STZ income statement has only {len(df)} rows, expected at least {min_rows}. "
        f"This indicates the resolver may be selecting pure OCI statement which has only ~10 rows."
    )
