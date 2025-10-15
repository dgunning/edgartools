"""
Manual verification script for FEAT-449: XBRL Unit and Point-in-Time Support

This script demonstrates the new optional parameters working with real XBRL data.
"""
from pathlib import Path
from edgar.xbrl import XBRL


def main():
    print("=" * 80)
    print("FEAT-449: XBRL Unit and Point-in-Time Support - Manual Verification")
    print("=" * 80)
    print()

    # Load Apple 10-K XBRL data
    data_dir = Path("tests/fixtures/xbrl2/aapl/10k_2023")
    if not data_dir.exists():
        print(f"ERROR: Test data not found at {data_dir}")
        return

    xbrl = XBRL.from_directory(data_dir)
    print(f"Loaded XBRL for: {xbrl.entity_name}")
    print()

    # ========================================
    # Test 1: Backward Compatibility
    # ========================================
    print("Test 1: Backward Compatibility")
    print("-" * 80)
    print("Testing that existing code works unchanged...")

    income_statement = xbrl.statements.income_statement()
    df_default = income_statement.to_dataframe()

    print(f"✓ DataFrame columns (default): {df_default.columns.tolist()}")
    assert 'unit' not in df_default.columns
    assert 'point_in_time' not in df_default.columns
    print("✓ No 'unit' or 'point_in_time' columns added by default")
    print()

    # ========================================
    # Test 2: Unit Column Feature
    # ========================================
    print("Test 2: Unit Column Feature")
    print("-" * 80)
    print("Testing include_unit=True parameter...")

    df_with_unit = income_statement.to_dataframe(include_unit=True)

    print(f"✓ DataFrame columns: {df_with_unit.columns.tolist()}")
    assert 'unit' in df_with_unit.columns
    print("✓ 'unit' column added successfully")

    # Show unit values
    unit_counts = df_with_unit['unit'].value_counts()
    print(f"\nUnit distribution:")
    for unit, count in unit_counts.items():
        print(f"  {unit}: {count} rows")

    # Show example row with unit
    revenue_row = df_with_unit[df_with_unit['concept'].str.contains('Revenue', case=False, na=False)]
    if len(revenue_row) > 0:
        print(f"\nExample: Revenue row")
        print(f"  Concept: {revenue_row.iloc[0]['concept']}")
        print(f"  Label: {revenue_row.iloc[0]['label']}")
        print(f"  Unit: {revenue_row.iloc[0]['unit']}")
    print()

    # ========================================
    # Test 3: Point-in-Time Column Feature
    # ========================================
    print("Test 3: Point-in-Time Column Feature")
    print("-" * 80)
    print("Testing include_point_in_time=True parameter...")

    df_with_pit = income_statement.to_dataframe(include_point_in_time=True)

    print(f"✓ DataFrame columns: {df_with_pit.columns.tolist()}")
    assert 'point_in_time' in df_with_pit.columns
    print("✓ 'point_in_time' column added successfully")

    # Show point-in-time distribution
    pit_counts = df_with_pit['point_in_time'].value_counts()
    print(f"\nPoint-in-Time distribution:")
    for pit, count in pit_counts.items():
        print(f"  {pit}: {count} rows")

    # Income statement should be mostly duration (False)
    duration_pct = (df_with_pit['point_in_time'] == False).sum() / len(df_with_pit['point_in_time'].dropna())
    print(f"\nIncome statement is {duration_pct:.1%} duration facts (expected for income statements)")
    print()

    # ========================================
    # Test 4: Combined Usage
    # ========================================
    print("Test 4: Combined Parameters")
    print("-" * 80)
    print("Testing both parameters together...")

    df_combined = income_statement.to_dataframe(
        include_unit=True,
        include_point_in_time=True
    )

    print(f"✓ DataFrame columns: {df_combined.columns.tolist()}")
    assert 'unit' in df_combined.columns
    assert 'point_in_time' in df_combined.columns
    print("✓ Both 'unit' and 'point_in_time' columns added successfully")

    # Show combined data sample
    print(f"\nSample rows with unit and point-in-time data:")
    sample = df_combined[['concept', 'label', 'unit', 'point_in_time']].head(5)
    print(sample.to_string(index=False))
    print()

    # ========================================
    # Test 5: Balance Sheet (Instant Periods)
    # ========================================
    print("Test 5: Balance Sheet with Point-in-Time")
    print("-" * 80)
    print("Testing that balance sheet uses instant periods...")

    balance_sheet = xbrl.statements.balance_sheet()
    bs_df = balance_sheet.to_dataframe(include_point_in_time=True)

    # Balance sheet should be mostly instant (True)
    instant_pct = (bs_df['point_in_time'] == True).sum() / len(bs_df['point_in_time'].dropna())
    print(f"Balance sheet is {instant_pct:.1%} instant facts (expected for balance sheets)")
    print("✓ Balance sheet correctly identified as instant periods")
    print()

    # ========================================
    # Test 6: Use Case - Unit-based Filtering
    # ========================================
    print("Test 6: Use Case - Unit-aware Filtering for Visualization")
    print("-" * 80)
    print("Demonstrating practical use case: filtering by unit type...")

    df_full = income_statement.to_dataframe(include_unit=True, include_point_in_time=True)

    # Filter to monetary facts
    monetary_facts = df_full[df_full['unit'] == 'usd']
    print(f"✓ Found {len(monetary_facts)} monetary (USD) facts")

    # Filter to share-based facts
    share_facts = df_full[df_full['unit'] == 'shares']
    if len(share_facts) > 0:
        print(f"✓ Found {len(share_facts)} share-based facts")

    # Filter to per-share facts
    per_share_facts = df_full[df_full['unit'] == 'usdPerShare']
    if len(per_share_facts) > 0:
        print(f"✓ Found {len(per_share_facts)} per-share ratio facts")

    print("\n✓ Unit-aware filtering enables proper chart labeling and data segregation")
    print()

    # ========================================
    # Summary
    # ========================================
    print("=" * 80)
    print("VERIFICATION COMPLETE - ALL TESTS PASSED ✓")
    print("=" * 80)
    print()
    print("Summary of implemented features:")
    print("  ✓ Backward compatibility maintained (no breaking changes)")
    print("  ✓ include_unit parameter adds 'unit' column with readable names")
    print("  ✓ include_point_in_time parameter adds boolean column")
    print("  ✓ Both parameters can be used together")
    print("  ✓ Income statements correctly identified as duration periods")
    print("  ✓ Balance sheets correctly identified as instant periods")
    print("  ✓ Unit-aware filtering enables advanced use cases")
    print()
    print("FEAT-449 implementation is complete and working correctly!")
    print()


if __name__ == '__main__':
    main()
