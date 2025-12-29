"""
Test TTM derivation safety for non-additive concepts.

Verifies:
1. Revenue (additive) -> Q4 derived
2. EPS (per-share) -> Q4 skipped
3. Shares (UnitType.SHARES) -> Q4 skipped
4. Negative Net Income -> Q4 derived (negative preserved)
"""
from datetime import date
from edgar.entity.models import FinancialFact
from edgar.entity.ttm import TTMCalculator


def test_ttm_derivation_safety():
    print("=" * 60)
    print("TTM DERIVATION SAFETY TEST")
    print("=" * 60)

    # === Setup Facts ===
    # Revenue (Additive - should derive)
    rev_fy = FinancialFact(
        concept='us-gaap:Revenue', taxonomy='us-gaap', label='Revenue',
        value=1000, numeric_value=1000, unit='USD',
        fiscal_year=2023, fiscal_period='FY', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 12, 31)
    )
    rev_ytd9 = FinancialFact(
        concept='us-gaap:Revenue', taxonomy='us-gaap', label='Revenue',
        value=700, numeric_value=700, unit='USD',
        fiscal_year=2023, fiscal_period='Q3', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 9, 30)
    )

    # EPS (Per-Share - should NOT derive)
    eps_fy = FinancialFact(
        concept='us-gaap:EarningsPerShareBasic', taxonomy='us-gaap', label='EPS',
        value=4.00, numeric_value=4.00, unit='USD/share',
        fiscal_year=2023, fiscal_period='FY', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 12, 31)
    )
    eps_ytd9 = FinancialFact(
        concept='us-gaap:EarningsPerShareBasic', taxonomy='us-gaap', label='EPS',
        value=3.00, numeric_value=3.00, unit='USD/share',
        fiscal_year=2023, fiscal_period='Q3', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 9, 30)
    )

    # Shares Outstanding (shares unit - should NOT derive)
    shares_fy = FinancialFact(
        concept='us-gaap:CommonStockSharesOutstanding', taxonomy='us-gaap', label='Shares',
        value=100, numeric_value=100, unit='shares',
        fiscal_year=2023, fiscal_period='FY', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 12, 31)
    )
    shares_ytd9 = FinancialFact(
        concept='us-gaap:CommonStockSharesOutstanding', taxonomy='us-gaap', label='Shares',
        value=100, numeric_value=100, unit='shares',
        fiscal_year=2023, fiscal_period='Q3', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 9, 30)
    )

    # Net Income Loss (Additive Negative - should derive as negative)
    loss_fy = FinancialFact(
        concept='us-gaap:NetIncome', taxonomy='us-gaap', label='Net Income',
        value=600, numeric_value=600, unit='USD',
        fiscal_year=2023, fiscal_period='FY', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 12, 31)
    )
    loss_ytd9 = FinancialFact(
        concept='us-gaap:NetIncome', taxonomy='us-gaap', label='Net Income',
        value=700, numeric_value=700, unit='USD',
        fiscal_year=2023, fiscal_period='Q3', period_type='duration',
        period_start=date(2023, 1, 1), period_end=date(2023, 9, 30)
    )

    # === Test 1: Revenue (Should Derive) ===
    print("\n1. Testing Revenue (Additive)...")
    calc_rev = TTMCalculator([rev_fy, rev_ytd9])
    quarters_rev = calc_rev._quarterize_facts()
    q4_rev = next((q for q in quarters_rev if q.calculation_context and 'q4' in str(q.calculation_context).lower()), None)
    assert q4_rev is not None, "FAIL: Revenue Q4 should be derived"
    assert q4_rev.numeric_value == 300, f"FAIL: Revenue Q4 should be 300, got {q4_rev.numeric_value}"
    print("   PASS: Revenue Q4 derived = 300")

    # === Test 2: EPS (Should NOT Derive) ===
    print("\n2. Testing EPS (Per-Share)...")
    calc_eps = TTMCalculator([eps_fy, eps_ytd9])
    quarters_eps = calc_eps._quarterize_facts()
    q4_eps = next((q for q in quarters_eps if q.calculation_context and 'q4' in str(q.calculation_context).lower()), None)
    assert q4_eps is None, f"FAIL: EPS Q4 should NOT be derived (found: {q4_eps})"
    print("   PASS: EPS derivation correctly skipped")

    # === Test 3: Shares (Should NOT Derive) ===
    print("\n3. Testing Shares Outstanding...")
    calc_shares = TTMCalculator([shares_fy, shares_ytd9])
    quarters_shares = calc_shares._quarterize_facts()
    q4_shares = next((q for q in quarters_shares if q.calculation_context and 'q4' in str(q.calculation_context).lower()), None)
    assert q4_shares is None, "FAIL: Shares Q4 should NOT be derived"
    print("   PASS: Shares derivation correctly skipped")

    # === Test 4: Negative Value (Should Derive) ===
    print("\n4. Testing Negative Net Income...")
    calc_loss = TTMCalculator([loss_fy, loss_ytd9])
    quarters_loss = calc_loss._quarterize_facts()
    q4_loss = next((q for q in quarters_loss if q.calculation_context and 'q4' in str(q.calculation_context).lower()), None)
    assert q4_loss is not None, "FAIL: Negative Q4 should be derived"
    assert q4_loss.numeric_value == -100, f"FAIL: Q4 should be -100, got {q4_loss.numeric_value}"
    print("   PASS: Negative Q4 derived = -100")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_ttm_derivation_safety()
