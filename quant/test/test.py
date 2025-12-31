import pytest
from datetime import date
from quant import QuantCompany
from quant.utils import TTMCalculator, detect_splits, apply_split_adjustments
from edgar.entity.models import FinancialFact

# -----------------------------------------------------------------------------
# 1. TTM and Quarterization Tests
# -----------------------------------------------------------------------------

def test_ttm_calculation_logic():
    """Verify that TTM correctly sums 4 quarters."""
    # Mock 4 consecutive quarters for Revenue
    facts = [
        FinancialFact(concept='Revenue', numeric_value=100, fiscal_year=2023, fiscal_period='Q1', period_type='duration', period_start=date(2023,1,1), period_end=date(2023,3,31), filing_date=date(2023,4,1)),
        FinancialFact(concept='Revenue', numeric_value=110, fiscal_year=2023, fiscal_period='Q2', period_type='duration', period_start=date(2023,4,1), period_end=date(2023,6,30), filing_date=date(2023,7,1)),
        FinancialFact(concept='Revenue', numeric_value=120, fiscal_year=2023, fiscal_period='Q3', period_type='duration', period_start=date(2023,7,1), period_end=date(2023,9,30), filing_date=date(2023,10,1)),
        FinancialFact(concept='Revenue', numeric_value=130, fiscal_year=2023, fiscal_period='Q4', period_type='duration', period_start=date(2023,10,1), period_end=date(2023,12,31), filing_date=date(2024,1,1)),
    ]
    
    calc = TTMCalculator(facts)
    ttm = calc.calculate_ttm()
    
    # Expected: 100+110+120+130 = 460
    assert ttm.value == 460
    assert len(ttm.periods) == 4

def test_q4_derivation_logic():
    """Verify Q4 is correctly derived from Annual - YTD_9M."""
    facts = [
        FinancialFact(concept='Revenue', numeric_value=300, fiscal_year=2023, fiscal_period='9M', period_type='duration', period_start=date(2023,1,1), period_end=date(2023,9,30), calculation_context='YTD_9M'),
        FinancialFact(concept='Revenue', numeric_value=400, fiscal_year=2023, fiscal_period='FY', period_type='duration', period_start=date(2023,1,1), period_end=date(2023,12,31)),
    ]
    
    calc = TTMCalculator(facts)
    quarters = calc._quarterize_facts()
    
    # Find the derived Q4
    q4_fact = next(q for q in quarters if q.fiscal_period == 'Q4')
    # Expected: 400 (FY) - 300 (YTD9) = 100
    assert q4_fact.numeric_value == 100
    assert 'derived_q4' in q4_fact.calculation_context

# -----------------------------------------------------------------------------
# 2. Stock Split Adjustment Tests
# -----------------------------------------------------------------------------

def test_split_detection():
    """Verify that stock split events are detected from XBRL facts."""
    split_fact = FinancialFact(
        concept='us-gaap:StockSplitConversionRatio', 
        numeric_value=10.0, 
        period_end=date(2024,6,7),
        filing_date=date(2024,6,7)
    )
    splits = detect_splits([split_fact])
    
    assert len(splits) == 1
    assert splits[0]['ratio'] == 10.0

def test_split_adjustment_application():
    """Verify math for per-share and share-count adjustments."""
    # 2-for-1 split occurred on 2024-01-01
    splits = [{'date': date(2024, 1, 1), 'ratio': 2.0}]
    
    # Fact from BEFORE the split (needs adjustment)
    old_eps = FinancialFact(concept='EarningsPerShare', numeric_value=10.0, unit='USD/share', period_end=date(2023, 12, 31))
    old_shares = FinancialFact(concept='SharesOutstanding', numeric_value=100.0, unit='shares', period_end=date(2023, 12, 31))
    
    adjusted = apply_split_adjustments([old_eps, old_shares], splits)
    
    # EPS: 10.0 / 2.0 = 5.0
    assert adjusted[0].numeric_value == 5.0
    # Shares: 100.0 * 2.0 = 200.0
    assert adjusted[1].numeric_value == 200.0

# -----------------------------------------------------------------------------
# 3. Structural Isolation Tests
# -----------------------------------------------------------------------------

def test_quant_company_inheritance():
    """Ensure QuantCompany correctly extends but does not break Company."""
    # Mocking basic initialization
    company = QuantCompany("NVDA")
    
    assert isinstance(company, QuantCompany)
    # Check that custom methods exist
    assert hasattr(company, 'get_ttm_revenue')
    assert hasattr(company, 'income_statement')