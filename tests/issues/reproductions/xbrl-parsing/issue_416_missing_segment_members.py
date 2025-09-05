"""
Issue #416: Product and service values not appearing in income statement
https://github.com/dgunning/edgartools/issues/416

Description:
When extracting MSFT's income statement from filing 0000950170-25-100235,
the us-gaap_ProductMember and us-gaap_ServiceOtherMember rows are missing
even though they are present in the original SEC filing.

Expected: Segment member data should appear in the income statement dataframe
Actual: Segment member rows are missing
"""

from edgar import *

def test_msft_segment_members():
    """Test that segment members appear in Microsoft's income statement"""
    
    print("Testing Microsoft filing for missing segment members...")
    print("=" * 60)
    
    # Get the specific filing mentioned in the issue
    filing = Company('MSFT').get_filings().filter(accession_number="0000950170-25-100235").latest()
    
    print(f"Filing: {filing.accession_number}")
    print(f"Form: {filing.form}")
    print(f"Date: {filing.filing_date}")
    print()
    
    # Extract financials
    financials = Financials.extract(filing)
    
    # Get income statement
    income_statement = financials.income_statement()
    
    print("Income Statement Structure:")
    print(f"Statement type: {type(income_statement)}")
    print(income_statement)
    print()
    
    # Convert to dataframe
    df = income_statement.to_dataframe()
    
    print(f"Dataframe shape: {df.shape}")
    print(f"Dataframe columns: {list(df.columns)}")
    print()
    
    print("Dataframe structure:")
    print(df.head(10))
    print()
    
    # Show the full dataframe for the missing concepts
    print("Full dataframe:")
    print(df.to_string())
    print()
    
    # Check for missing/empty values in the segment member rows
    segment_member_rows = df[df['concept'].isin(['us-gaap_ProductMember', 'us-gaap_ServiceOtherMember'])]
    print("Segment member rows:")
    print(segment_member_rows.to_string())
    print()
    
    # Extract concept names from the dataframe
    if 'concept' in df.columns:
        concepts = df['concept'].tolist()
    elif 'label' in df.columns:
        concepts = df['label'].tolist() 
    else:
        # Fallback to index
        concepts = df.index.tolist()
    
    print(f"Total concepts in dataframe: {len(concepts)}")
    print()
    
    # Look for segment-related concepts
    segment_concepts = []
    product_concepts = []
    service_concepts = []
    
    for concept in concepts:
        concept_str = str(concept).lower()
        if 'member' in concept_str:
            segment_concepts.append(concept)
        if 'product' in concept_str:
            product_concepts.append(concept)
        if 'service' in concept_str:
            service_concepts.append(concept)
    
    print("Segment-related concepts found:")
    for concept in segment_concepts:
        print(f"  - {concept}")
    
    print("\nProduct-related concepts found:")
    for concept in product_concepts:
        print(f"  - {concept}")
        
    print("\nService-related concepts found:")
    for concept in service_concepts:
        print(f"  - {concept}")
    
    print("\nLooking for specific missing concepts:")
    missing_concepts = ['us-gaap_ProductMember', 'us-gaap_ServiceOtherMember']
    
    for missing_concept in missing_concepts:
        found = any(missing_concept in str(concept) for concept in concepts)
        print(f"  {missing_concept}: {'FOUND' if found else 'MISSING'}")
    
    # Show sample of concepts to understand the structure
    print(f"\nSample of concepts (first 10):")
    for i, concept in enumerate(concepts[:10]):
        print(f"  {i+1}. {concept}")
    
    # Check the dimension column for segment information
    if 'dimension' in df.columns:
        print(f"\nDimension column values:")
        dimension_values = df['dimension'].dropna().unique()
        for dim in dimension_values:
            print(f"  - {dim}")
    
    # Check if these concepts exist in the raw XBRL data
    print("\nInvestigating raw XBRL structure...")
    
    # Debug the dimension detection logic
    print(f"\nDebug: Checking _has_product_service_dimensions()...")
    
    # Try to access the XBRL instance directly
    try:
        xbrl_doc = filing.xbrl()
        if xbrl_doc:
            print(f"XBRL class type: {type(xbrl_doc)}")
            print(f"XBRL class methods: {[m for m in dir(xbrl_doc) if m.startswith('_has') or m.startswith('_is_dim')]}")
            print(f"Has _has_product_service_dimensions: {hasattr(xbrl_doc, '_has_product_service_dimensions')}")
            print(f"Has _is_dimension_display_statement: {hasattr(xbrl_doc, '_is_dimension_display_statement')}")
            
            # Test our dimension detection method if it exists
            if hasattr(xbrl_doc, '_has_product_service_dimensions'):
                has_dimensions = xbrl_doc._has_product_service_dimensions()
                print(f"_has_product_service_dimensions() returns: {has_dimensions}")
            
                # Test the overall _is_dimension_display_statement logic
                should_display = xbrl_doc._is_dimension_display_statement('IncomeStatement', '')
                print(f"_is_dimension_display_statement('IncomeStatement', '') returns: {should_display}")
            
            print()
            print(f"XBRL document loaded successfully")
            
            # Look for segment-related contexts or members
            contexts = getattr(xbrl_doc, 'contexts', [])
            print(f"Number of contexts: {len(contexts) if contexts else 'N/A'}")
            
            # Look for facts that might contain segment information  
            facts_view = xbrl_doc.facts
            print(f"Facts view type: {type(facts_view)}")
            
            # Try to query for segment-related facts
            segment_query = facts_view.query().by_concept(".*Member.*", exact=False)
            segment_results = segment_query.execute()
            print(f"Segment member facts found: {len(segment_results)}")
            
            # Try to query for product/service revenue facts with dimensions
            product_query = facts_view.query().by_concept(".*Revenue.*", exact=False).by_dimension("ProductOrService", None)
            product_results = product_query.execute()
            print(f"Product/Service revenue facts found: {len(product_results)}")
            
            # Look for facts with the srt:ProductOrServiceAxis dimension
            axis_query = facts_view.query().by_dimension("srt_ProductOrServiceAxis", None)
            axis_results = axis_query.execute()
            print(f"Facts with ProductOrServiceAxis dimension: {len(axis_results)}")
            
            if axis_results:
                print("Sample dimensional facts:")
                for fact in axis_results[:5]:
                    print(f"  Concept: {fact.get('concept', 'N/A')}")
                    print(f"  Value: {fact.get('value', 'N/A')}")
                    print(f"  Period: {fact.get('period', 'N/A')}")
                    print(f"  Date: {fact.get('date', 'N/A')}")
                    # Show dimension info
                    dim_info = {k: v for k, v in fact.items() if k.startswith('dim_')}
                    print(f"  Dimensions: {dim_info}")
                    print()
                    
                # Create a summary of revenue values by dimension
                print("\nRevenue breakdown by Product/Service dimension:")
                revenue_by_member = {}
                for fact in axis_results:
                    if 'Revenue' in fact.get('concept', '') and fact.get('value'):
                        member = fact.get('dim_srt_ProductOrServiceAxis', 'Unknown')
                        date = fact.get('date', 'Unknown')
                        if member not in revenue_by_member:
                            revenue_by_member[member] = {}
                        revenue_by_member[member][date] = fact.get('value')
                        
                for member, dates in revenue_by_member.items():
                    print(f"  {member}:")
                    for date, value in sorted(dates.items()):
                        print(f"    {date}: ${value:,.0f}" if isinstance(value, (int, float)) else f"    {date}: {value}")
                print()
        
    except Exception as e:
        print(f"Error accessing XBRL data: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"- Expected concepts missing: {missing_concepts}")
    print(f"- Total concepts in income statement: {len(concepts)}")
    print(f"- Segment-related concepts found: {len(segment_concepts)}")
    
    return {
        'filing': filing,
        'income_statement': income_statement,
        'dataframe': df,
        'missing_concepts': missing_concepts,
        'segment_concepts_found': segment_concepts,
        'all_concepts': concepts
    }

if __name__ == "__main__":
    result = test_msft_segment_members()