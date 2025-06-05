import pytest
from rich import print

from edgar import *
from edgar.xbrl import *
from edgar.xbrl.analysis.ratios import *


@pytest.fixture(scope="session")
def comcast_xbrl():
    filing = Filing(company='COMCAST CORP', cik=1166691, form='10-K', filing_date='2025-01-31', accession_no='0001166691-25-000011')
    return XBRL.from_filing(filing)

def test_get_ratio_data(comcast_xbrl):
    fr = FinancialRatios(comcast_xbrl)
    print(comcast_xbrl.statements.balance_sheet())
    
    # Test each ratio category
    for category in ['current', 'operating_margin', 'return_on_assets', 'gross_margin', 'leverage']:
        print(f"\nValidating ratio data for category: {category}")
        ratio_data = fr.get_ratio_data(category)
        
        # Basic validation
        assert not ratio_data.calculation_df.empty, f"Calculation DataFrame is empty for {category}"
        assert len(ratio_data.periods) > 0, f"No periods found for {category}"
        
        # 1. Test that all required concepts are found with values
        for concept in ratio_data.required_concepts:
            print(f"  Checking required concept: {concept}")
            assert ratio_data.has_concept(concept), f"Required concept {concept} not found"
            
            # Get the concept values and check they're not all NaN
            values = ratio_data.get_concept(concept)
            assert not values.isna().all(), f"All values for required concept {concept} are NaN"
            
            # Check at least one period has a non-zero value (to catch potential data issues)
            if values.dtype.kind in 'iuf':  # integer, unsigned integer, or float
                # For financial statements, having all zeros is suspicious (except for some concepts)
                if concept not in ['Inventory']:  # Add exceptions here
                    assert (values != 0).any(), f"All values for concept {concept} are zero"
        
        # 2. Test that optional concepts are either found or default values work
        for opt_concept, default_value in ratio_data.optional_concepts.items():
            print(f"  Checking optional concept: {opt_concept}")
            
            # Get the concept - this should not raise an error even if concept is missing
            try:
                values = ratio_data.get_concept(opt_concept)
                assert values is not None, f"Optional concept {opt_concept} returned None"
                
                # If concept is not found in original data, it should match the default value
                if not ratio_data.has_concept(opt_concept):
                    print(f"    Using default value {default_value} for {opt_concept}")
                    assert (values == default_value).all(), f"Default value not applied for {opt_concept}"
                else:
                    print(f"    Found actual values for {opt_concept}")
            except Exception as e:
                assert False, f"Error retrieving optional concept {opt_concept}: {str(e)}"
        
        # 3. Test that we can calculate valid concepts even when using defaults
        print("  Testing concept retrieval with custom defaults")
        for idx, concept in enumerate(ratio_data.required_concepts):
            # Test overriding with a custom default (should only apply if concept is missing)
            custom_default = 100.0 + idx  # Use different values to make sure it's the right one
            value_with_default = ratio_data.get_concept(concept, default_value=custom_default)
            assert value_with_default is not None, f"Failed to get {concept} with custom default"
            
            # If concept exists, original value should be used (not custom default)
            if ratio_data.has_concept(concept):
                original = ratio_data.get_concept(concept)
                assert (value_with_default == original).all(), "Custom default overrode existing values"
        
        # 4. Test that we can calculate valid ratio values (no division by zero, etc.)
        print("  Testing ratio calculations for validity")
        
        try:
            if category == 'current':
                # Test current ratio
                current_assets = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_ASSETS)
                current_liabilities = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_LIABILITIES)
                assert not (current_liabilities == 0).any(), "Current liabilities contains zero values"
                current_ratio = current_assets / current_liabilities
                assert not current_ratio.isna().any(), "Current ratio contains NaN values"
                
                # Test quick ratio
                inventory = ratio_data.get_concept(StandardConcept.INVENTORY)
                quick_assets = current_assets - inventory
                assert (quick_assets > 0).all(), "Quick assets calculation resulted in negative values"
                quick_ratio = quick_assets / current_liabilities
                assert not quick_ratio.isna().any(), "Quick ratio contains NaN values"
                
                # Test cash ratio
                cash = ratio_data.get_concept(StandardConcept.CASH_AND_EQUIVALENTS)
                cash_ratio = cash / current_liabilities
                assert not cash_ratio.isna().any(), "Cash ratio contains NaN values"
                
                # Test working capital
                working_capital = current_assets - current_liabilities
                assert not working_capital.isna().any(), "Working capital contains NaN values"
                
            elif category == 'operating_margin':
                # Test operating margin
                operating_income = ratio_data.get_concept(StandardConcept.OPERATING_INCOME)
                revenue = ratio_data.get_concept(StandardConcept.REVENUE)
                assert not (revenue == 0).any(), "Revenue contains zero values"
                operating_margin = operating_income / revenue
                assert not operating_margin.isna().any(), "Operating margin contains NaN values"
                
            elif category == 'return_on_assets':
                # Test return on assets
                net_income = ratio_data.get_concept(StandardConcept.NET_INCOME)
                total_assets = ratio_data.get_concept(StandardConcept.TOTAL_ASSETS)
                assert not (total_assets == 0).any(), "Total assets contains zero values"
                
                # For simplicity in testing, we'll use total assets directly instead of average
                roa = net_income / total_assets
                assert not roa.isna().any(), "Return on assets contains NaN values"
                
            elif category == 'gross_margin':
                # Test gross margin
                gross_profit = ratio_data.get_concept(StandardConcept.GROSS_PROFIT)
                revenue = ratio_data.get_concept(StandardConcept.REVENUE)
                assert not (revenue == 0).any(), "Revenue contains zero values"
                gross_margin = gross_profit / revenue
                assert not gross_margin.isna().any(), "Gross margin contains NaN values"
                
            elif category == 'leverage':
                # Test debt to equity
                long_term_debt = ratio_data.get_concept(StandardConcept.LONG_TERM_DEBT)
                total_equity = ratio_data.get_concept(StandardConcept.TOTAL_EQUITY)
                if not (total_equity == 0).any():  # Some companies might have negative equity
                    debt_to_equity = long_term_debt / total_equity
                    assert not debt_to_equity.isna().all(), "Debt to equity contains all NaN values"
                
                # Test interest coverage
                operating_income = ratio_data.get_concept(StandardConcept.OPERATING_INCOME)
                interest_expense = ratio_data.get_concept(StandardConcept.INTEREST_EXPENSE)
                if not (interest_expense == 0).all():  # Some companies might not have interest expense
                    interest_coverage = operating_income / interest_expense
                    assert not interest_coverage.isna().all(), "Interest coverage contains all NaN values"
                    
        except (KeyError, ZeroDivisionError) as e:
            assert False, f"Error calculating ratio for {category}: {str(e)}"
            
        print(f"  Validation complete for {category}")
        
    print("\nAll ratio data validations passed!")


def test_validate_default_handling_in_ratios(comcast_xbrl):
    """Specifically test that default handling for missing concepts works correctly."""
    fr = FinancialRatios(comcast_xbrl)
    
    # Test the quick ratio calculation which should handle missing inventory
    print("\nTesting quick ratio calculation with default inventory handling")
    
    # 1. Get ratio data
    ratio_data = fr.get_ratio_data("current")
    
    # 2. Check if inventory exists naturally
    has_real_inventory = ratio_data.has_concept(StandardConcept.INVENTORY)
    print(f"Has real inventory data: {has_real_inventory}")
    
    if has_real_inventory:
        # Use a temp modified ratio data to simulate missing inventory
        # We'll modify the calculation_df to remove inventory
        temp_df = ratio_data.calculation_df.copy()
        if StandardConcept.INVENTORY in temp_df.index:
            # Save original inventory values
            original_inventory = temp_df.loc[StandardConcept.INVENTORY].copy()
            # Replace with NaN to simulate missing data
            temp_df.loc[StandardConcept.INVENTORY, :] = pd.NA
            
            # Create modified ratio data
            modified_ratio_data = RatioData(
                calculation_df=temp_df,
                periods=ratio_data.periods,
                equivalents_used=ratio_data.equivalents_used,
                required_concepts=ratio_data.required_concepts,
                optional_concepts=ratio_data.optional_concepts
            )
            
            # Test that inventory is treated as missing
            assert not modified_ratio_data.has_concept(StandardConcept.INVENTORY)
            
            # Get inventory with default handling
            default_inventory = modified_ratio_data.get_concept(StandardConcept.INVENTORY)
            assert (default_inventory == 0).all(), "Default inventory value should be 0"
            
            # Calculate quick ratio manually to validate
            current_assets = modified_ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_ASSETS)
            current_liabilities = modified_ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_LIABILITIES)
            
            # Using original inventory
            quick_assets_original = current_assets - original_inventory
            quick_ratio_original = quick_assets_original / current_liabilities
            
            # Using default (zero) inventory
            quick_assets_default = current_assets - default_inventory
            quick_ratio_default = quick_assets_default / current_liabilities
            
            # The quick ratio with zero inventory should equal the current ratio
            current_ratio = current_assets / current_liabilities
            assert (quick_ratio_default == current_ratio).all(), "Quick ratio with zero inventory should equal current ratio"
            
            # The original and default ratios should be different
            assert not (quick_ratio_original == quick_ratio_default).all(), "Original and default quick ratios should differ"
            
            print("Successfully tested inventory default handling with simulated missing data")
    else:
        # If inventory is naturally missing, verify default behavior
        inventory = ratio_data.get_concept(StandardConcept.INVENTORY)
        assert (inventory == 0).all(), "Missing inventory should default to 0"
        
        # Verify quick ratio equals current ratio when inventory is 0
        current_assets = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_ASSETS)
        current_liabilities = ratio_data.get_concept(StandardConcept.TOTAL_CURRENT_LIABILITIES)
        
        quick_ratio = (current_assets - inventory) / current_liabilities
        current_ratio = current_assets / current_liabilities
        
        assert (quick_ratio == current_ratio).all(), "Quick ratio should equal current ratio when inventory is 0"
        print("Successfully tested default handling with naturally missing inventory data")
    
    # Now test the actual ratio calculation method
    quick_ratio_result = fr.calculate_quick_ratio()
    assert quick_ratio_result is not None, "Quick ratio calculation failed"
    assert 'inventory' in quick_ratio_result.components, "Inventory component missing from quick ratio result"
    print("Quick ratio calculation test passed")


def test_calculate_ratio_requiring_equivalent(comcast_xbrl):
    fr = FinancialRatios(comcast_xbrl)
    # Skip this test for now until we update the leverage ratios calculation
    pytest.skip("Need to update leverage_ratios calculation to use RatioData")


def test_calculate_quick_ratio(comcast_xbrl):
    ratios = FinancialRatios(comcast_xbrl)
    ratio_data = ratios.get_ratio_data("current")
    
    # Test that we can access the inventory concept
    inventory = ratio_data.get_concept(StandardConcept.INVENTORY)
    assert inventory is not None
    
    # Calculate quick ratio
    quick_ratio = ratios.calculate_quick_ratio()
    assert quick_ratio is not None
    print(quick_ratio)