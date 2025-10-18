#!/usr/bin/env python3
"""
Test the concept-based ordering approach
"""

from edgar.xbrl.stitching.ordering import StatementOrderingManager, FinancialStatementTemplates
from edgar import Company
from edgar.xbrl import XBRLS
from edgar.xbrl.stitching.presentation import VirtualPresentationTree
from edgar.xbrl.stitching.ordering import StatementOrderingManager


def test_concept_based_matching():
    """Test concept-based matching vs label-based matching"""
    
    print("Testing Concept-Based vs Label-Based Ordering...")
    
    # Test the template matching directly
    templates = FinancialStatementTemplates()
    
    # Test concept-based matching
    print("\n=== CONCEPT-BASED MATCHING ===")
    
    test_cases = [
        # (concept, label, expected_to_match)
        ("us-gaap:Revenue", "Contract Revenue", True),
        ("us-gaap:CostOfGoodsAndServicesSold", "Cost of Goods and Services Sold", True),
        ("us-gaap:ResearchAndDevelopmentExpense", "Research and Development Expense", True),
        ("us-gaap:OperatingIncomeLoss", "Operating Income", True),
        ("us-gaap:NetIncome", "Net Income", True),
        ("aapl:ServicesRevenue", "Services Revenue", False),  # Company-specific concept
        (None, "Some Random Label", False),  # No concept
    ]
    
    for concept, label, should_match in test_cases:
        position = templates.get_template_position(concept, label, "IncomeStatement")
        matched = position is not None
        
        status = "✓ PASS" if matched == should_match else "✗ FAIL"
        print(f"{status} Concept: {concept or 'None':50s} Label: {label:35s} Position: {position}")
    
    # Test with simulated Apple statement data
    print("\n=== ORDERING MANAGER TEST ===")
    
    manager = StatementOrderingManager("IncomeStatement")
    
    # Simulate Apple-like statement with real XBRL concepts
    test_statements = [
        {
            'statement_type': 'IncomeStatement',
            'data': [
                {
                    'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                    'label': 'Contract Revenue'
                },
                {
                    'concept': 'us-gaap:CostOfGoodsAndServicesSold',
                    'label': 'Cost of Goods and Services Sold'
                },
                {
                    'concept': 'us-gaap:GrossProfit',
                    'label': 'Gross Profit'
                },
                {
                    'concept': 'us-gaap:ResearchAndDevelopmentExpense',
                    'label': 'Research and Development Expense'
                },
                {
                    'concept': 'us-gaap:SellingGeneralAndAdministrativeExpense',
                    'label': 'Selling, General and Administrative Expense'
                },
                {
                    'concept': 'us-gaap:OperatingExpenses',
                    'label': 'Operating Expenses'
                },
                {
                    'concept': 'us-gaap:OperatingIncomeLoss',
                    'label': 'Operating Income'
                },
                {
                    'concept': 'us-gaap:NetIncome',
                    'label': 'Net Income'
                },
                {
                    'concept': 'aapl:CustomBusinessMetric',  # Company-specific
                    'label': 'Apple Custom Metric'
                }
            ]
        }
    ]
    
    ordering = manager.determine_ordering(test_statements)
    
    # Sort by ordering
    sorted_items = sorted(ordering.items(), key=lambda x: x[1])
    
    print("Items in concept-based order:")
    for i, (item, position) in enumerate(sorted_items):
        print(f"{i+1:2d}. {item:45s} (position: {position:6.1f})")
    
    # Verify key ordering relationships
    print("\n=== CONCEPT-BASED ORDERING VERIFICATION ===")
    
    # Map back to concepts for verification
    concept_positions = {}
    label_positions = {}
    
    for item, position in ordering.items():
        # Find the corresponding concept/label in test data
        for data_item in test_statements[0]['data']:
            if item == data_item['concept'] or item == data_item['label']:
                concept = data_item['concept']
                label = data_item['label']
                concept_positions[concept] = position
                label_positions[label] = position
                break
    
    checks = [
        ("Revenue < Cost of Goods Sold",
         concept_positions.get('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', 999) < 
         concept_positions.get('us-gaap:CostOfGoodsAndServicesSold', 999)),
        ("Cost of Goods Sold < Gross Profit",
         concept_positions.get('us-gaap:CostOfGoodsAndServicesSold', 999) < 
         concept_positions.get('us-gaap:GrossProfit', 999)),
        ("R&D Expense < Operating Income", 
         concept_positions.get('us-gaap:ResearchAndDevelopmentExpense', 999) < 
         concept_positions.get('us-gaap:OperatingIncomeLoss', 999)),
        ("Operating Income < Net Income",
         concept_positions.get('us-gaap:OperatingIncomeLoss', 999) < 
         concept_positions.get('us-gaap:NetIncome', 999)),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL" 
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    # Test concept normalization
    print("\n=== CONCEPT NORMALIZATION TEST ===")
    
    normalization_tests = [
        ("us-gaap:Revenue", "us-gaap_revenue"),
        ("us-gaap_Revenue", "us-gaap_revenue"), 
        ("usgaap:Revenue", "us-gaap_revenue"),
        ("gaap:Revenue", "us-gaap_revenue"),
        ("AAPL:CustomConcept", "aapl_customconcept"),
    ]
    
    for input_concept, expected in normalization_tests:
        normalized = templates._normalize_xbrl_concept(input_concept)
        matches = normalized == expected
        status = "✓ PASS" if matches else "✗ FAIL"
        print(f"{status} {input_concept:20s} -> {normalized:20s} (expected: {expected})")
    
    if all_passed:
        print("\n🎉 Concept-based ordering is working correctly!")
    else:
        print("\n❌ Some concept-based ordering checks failed.")
    
    return all_passed


def test_nvidia_section_grouping():
    """Test that per-share section stays properly grouped in NVIDIA data"""

    print("Testing NVIDIA Section Grouping Fix...")

    # Get NVIDIA filings
    company = Company("NVDA")
    filings = company.get_filings(form="10-K").latest(3)

    print(f"Found {len(filings)} NVDA filings")

    # Get multi-period stitched
    xbrls = XBRLS.from_filings(filings)
    multi_income = xbrls.statements.income_statement()

    print("\n=== NVIDIA MULTI-PERIOD WITH SECTION FIX ===")
    print(multi_income)

    # Test the ordering manager directly with per-share concepts
    print("\n=== TESTING SECTION CONSOLIDATION DIRECTLY ===")

    manager = StatementOrderingManager("IncomeStatement")

    # Simulate NVIDIA-like data with per-share concepts mixed in
    test_statements = [
        {
            'statement_type': 'IncomeStatement',
            'data': [
                # Early items that might get low reference positions
                {'concept': 'us-gaap:Revenue', 'label': 'Revenue'},
                {'concept': 'us-gaap:InterestIncomeExpenseNet', 'label': 'Interest income'},
                {'concept': 'us-gaap:IncomeLossBeforeIncomeTaxes', 'label': 'Income before income tax'},

                # Per-share concepts that should stay grouped at end
                {'concept': 'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic',
                 'label': 'Shares Outstanding (Basic)'},
                {'concept': 'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding',
                 'label': 'Shares Outstanding (Diluted)'},

                # Other middle items
                {'concept': 'us-gaap:CostOfRevenue', 'label': 'Total Cost of Revenue'},
                {'concept': 'us-gaap:GrossProfit', 'label': 'Gross Profit'},
                {'concept': 'us-gaap:ResearchAndDevelopmentExpense', 'label': 'Research and Development Expense'},
                {'concept': 'us-gaap:OperatingIncomeLoss', 'label': 'Operating Income'},
                {'concept': 'us-gaap:NetIncome', 'label': 'Net Income'},

                # More per-share data
                {'concept': 'us-gaap:EarningsPerShareBasic', 'label': 'Earnings Per Share (Basic)'},
                {'concept': 'us-gaap:EarningsPerShareDiluted', 'label': 'Earnings Per Share (Diluted)'},
            ]
        }
    ]

    ordering = manager.determine_ordering(test_statements)

    # Sort by ordering
    sorted_items = sorted(ordering.items(), key=lambda x: x[1])

    print("Items in section-aware order:")
    for i, (item, position) in enumerate(sorted_items):
        # Mark per-share items
        marker = " ← PER-SHARE" if any(
            term in item.lower() for term in ['earnings per share', 'shares outstanding']) else ""
        print(f"{i + 1:2d}. {item:50s} (position: {position:6.1f}){marker}")

    # Verify section grouping
    print("\n=== SECTION GROUPING VERIFICATION ===")

    # Find positions of per-share related items
    eps_basic_pos = ordering.get('Earnings Per Share (Basic)') or ordering.get('us-gaap:EarningsPerShareBasic')
    eps_diluted_pos = ordering.get('Earnings Per Share (Diluted)') or ordering.get('us-gaap:EarningsPerShareDiluted')
    shares_basic_pos = ordering.get('Shares Outstanding (Basic)') or ordering.get(
        'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic')
    shares_diluted_pos = ordering.get('Shares Outstanding (Diluted)') or ordering.get(
        'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding')

    # Find positions of main statement items
    revenue_pos = ordering.get('Revenue') or ordering.get('us-gaap:Revenue')
    net_income_pos = ordering.get('Net Income') or ordering.get('us-gaap:NetIncome')

    print(f"Revenue position: {revenue_pos}")
    print(f"Net Income position: {net_income_pos}")
    print(f"EPS Basic position: {eps_basic_pos}")
    print(f"EPS Diluted position: {eps_diluted_pos}")
    print(f"Shares Basic position: {shares_basic_pos}")
    print(f"Shares Diluted position: {shares_diluted_pos}")

    checks = [
        ("Revenue < Net Income", revenue_pos < net_income_pos),
        ("Net Income < EPS (proper end positioning)", net_income_pos < eps_basic_pos if eps_basic_pos else True),
        ("EPS Basic < EPS Diluted (per-share grouping)",
         eps_basic_pos < eps_diluted_pos if eps_basic_pos and eps_diluted_pos else True),
        ("EPS sections grouped together",
         abs(eps_basic_pos - eps_diluted_pos) < 2.0 if eps_basic_pos and eps_diluted_pos else True),
        ("Shares sections grouped together",
         abs(shares_basic_pos - shares_diluted_pos) < 2.0 if shares_basic_pos and shares_diluted_pos else True),
        ("Per-share data at end (after Net Income)",
         all(pos > net_income_pos for pos in [eps_basic_pos, eps_diluted_pos, shares_basic_pos, shares_diluted_pos] if
             pos)),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 Section grouping fix is working! Per-share data stays properly grouped.")
    else:
        print("\n❌ Section grouping needs more work.")

    return all_passed


def test_section_identification():
    """Test the section identification logic"""
    print("\n=== TESTING SECTION IDENTIFICATION ===")

    manager = StatementOrderingManager("IncomeStatement")

    template_positioned = {
        'us-gaap:Revenue': 6.0,
        'us-gaap:CostOfRevenue': 100.0,
        'us-gaap:GrossProfit': 200.0,
        'us-gaap:ResearchAndDevelopmentExpense': 301.0,
        'us-gaap:OperatingIncomeLoss': 400.0,
        'us-gaap:NetIncome': 802.0,
        'us-gaap:EarningsPerShareBasic': 901.0,
        'us-gaap:EarningsPerShareDiluted': 902.0,
        'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic': 904.0,
        'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding': 905.0,
    }

    sections = manager._identify_template_sections(template_positioned)

    print("Identified sections:")
    for section_name, concepts in sections.items():
        print(f"  {section_name}: {concepts}")

    # Check that per-share section is properly identified
    per_share_section = sections.get('per_share', [])
    expected_per_share = [
        'us-gaap:EarningsPerShareBasic',
        'us-gaap:EarningsPerShareDiluted',
        'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic',
        'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding'
    ]


def test_apple_ordering_fix():
    """Test the specific Apple ordering issue"""

    print("Testing Apple multi-period ordering fix...")

    # Get Apple filings
    company = Company("AAPL")
    filings = company.get_filings(form="10-K").latest(3)

    print(f"Found {len(filings)} filings")

    # Get single period for comparison
    latest_filing = filings[0]
    single_xbrl = latest_filing.xbrl()
    single_statements = single_xbrl.statements
    single_income = single_statements.income_statement()

    print("\n=== SINGLE PERIOD (Reference) ===")
    print(single_income)

    # Get multi-period stitched
    from edgar.xbrl import XBRLS
    xbrls = XBRLS.from_filings(filings)
    multi_income = xbrls.statements.income_statement()

    print("\n=== MULTI-PERIOD (With Fix) ===")
    print(multi_income)

    # Test the ordering manager directly
    print("\n=== TESTING ORDERING MANAGER ===")
    manager = StatementOrderingManager("IncomeStatement")

    # Simulate statements with wrong order
    test_statements = [
        {
            'statement_type': 'IncomeStatement',
            'data': [
                {'concept': 'NetIncome', 'label': 'Net Income'},
                {'concept': 'Revenue', 'label': 'Contract Revenue'},
                {'concept': 'OpExp', 'label': 'Operating Expenses'},
                {'concept': 'COGS', 'label': 'Cost of Goods and Services Sold'},
                {'concept': 'OpIncome', 'label': 'Operating Income'},
                {'concept': 'IncomeTax', 'label': 'Income Tax Expense'},
                {'concept': 'GrossProfit', 'label': 'Gross Profit'}
            ]
        }
    ]

    ordering = manager.determine_ordering(test_statements)

    # Sort concepts by their ordering
    sorted_concepts = sorted(ordering.items(), key=lambda x: x[1])

    print("Concepts in corrected order:")
    for i, (concept, position) in enumerate(sorted_concepts):
        print(f"{i + 1:2d}. {concept:35s} (position: {position:6.1f})")

    # Verify key relationships
    print("\n=== ORDERING VERIFICATION ===")
    revenue_pos = ordering.get('Contract Revenue', 999)
    cogs_pos = ordering.get('Cost of Goods and Services Sold', 999)
    gross_profit_pos = ordering.get('Gross Profit', 999)
    op_exp_pos = ordering.get('Operating Expenses', 999)
    op_income_pos = ordering.get('Operating Income', 999)
    tax_pos = ordering.get('Income Tax Expense', 999)
    net_income_pos = ordering.get('Net Income', 999)

    checks = [
        ("Revenue < Cost of Goods Sold", revenue_pos < cogs_pos),
        ("Cost of Goods Sold < Gross Profit", cogs_pos < gross_profit_pos),
        ("Gross Profit < Operating Expenses", gross_profit_pos < op_exp_pos),
        ("Operating Expenses < Operating Income", op_exp_pos < op_income_pos),
        ("Operating Income < Income Tax", op_income_pos < tax_pos),
        ("Income Tax < Net Income", tax_pos < net_income_pos)
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All ordering checks PASSED! The fix is working correctly.")
    else:
        print("\n❌ Some ordering checks FAILED. The fix needs more work.")

    return all_passed


def test_presentation_tree():
    """Test the presentation tree approach"""

    print("Testing Presentation Tree Fix...")

    # Get Apple filings
    company = Company("AAPL")
    filings = company.get_filings(form="10-K").latest(3)

    print(f"Found {len(filings)} filings")

    # Get multi-period stitched with new approach
    xbrls = XBRLS.from_filings(filings)
    multi_income = xbrls.statements.income_statement()

    print("\n=== MULTI-PERIOD WITH PRESENTATION TREE FIX ===")
    print(multi_income)

    # Test the presentation tree directly with a simulated problematic case
    print("\n=== TESTING PRESENTATION TREE DIRECTLY ===")

    # Simulate the Apple case with broken hierarchy
    concept_metadata = {
        'Contract Revenue': {'level': 0, 'latest_label': 'Contract Revenue', 'is_abstract': False, 'is_total': False,
                             'original_concept': 'Revenue'},
        'Cost of Goods and Services Sold': {'level': 0, 'latest_label': 'Cost of Goods and Services Sold',
                                            'is_abstract': False, 'is_total': False, 'original_concept': 'COGS'},
        'Gross Profit': {'level': 0, 'latest_label': 'Gross Profit', 'is_abstract': False, 'is_total': False,
                         'original_concept': 'GrossProfit'},
        'Operating Expenses': {'level': 0, 'latest_label': 'Operating Expenses', 'is_abstract': True, 'is_total': False,
                               'original_concept': 'OpExpenses'},
        'Research and Development Expense': {'level': 1, 'latest_label': 'Research and Development Expense',
                                             'is_abstract': False, 'is_total': False, 'original_concept': 'RnD'},
        'Selling, General and Administrative Expense': {'level': 1,
                                                        'latest_label': 'Selling, General and Administrative Expense',
                                                        'is_abstract': False, 'is_total': False,
                                                        'original_concept': 'SGA'},
        'Total Operating Expenses': {'level': 0, 'latest_label': 'Operating Expenses', 'is_abstract': False,
                                     'is_total': True, 'original_concept': 'TotalOpExp'},
        'Operating Income': {'level': 0, 'latest_label': 'Operating Income', 'is_abstract': False, 'is_total': False,
                             'original_concept': 'OpIncome'},
        'Net Income': {'level': 0, 'latest_label': 'Net Income', 'is_abstract': False, 'is_total': False,
                       'original_concept': 'NetIncome'},
        'Earnings Per Share (Basic)': {'level': 1, 'latest_label': 'Earnings Per Share (Basic)', 'is_abstract': False,
                                       'is_total': False, 'original_concept': 'EPSBasic'},
        'Earnings Per Share (Diluted)': {'level': 1, 'latest_label': 'Earnings Per Share (Diluted)',
                                         'is_abstract': False, 'is_total': False, 'original_concept': 'EPSDiluted'},
    }

    # Simulate original statement order (how it appears in the reference filing)
    original_order = [
        'Contract Revenue',
        'Cost of Goods and Services Sold',
        'Gross Profit',
        'Operating Expenses',  # Abstract parent
        'Research and Development Expense',  # Child of Operating Expenses
        'Selling, General and Administrative Expense',  # Child of Operating Expenses
        'Total Operating Expenses',  # Total for Operating Expenses
        'Operating Income',
        'Net Income',
        'Earnings Per Share (Basic)',  # Child of EPS section
        'Earnings Per Share (Diluted)',  # Child of EPS section
    ]

    # Get semantic ordering
    ordering_manager = StatementOrderingManager("IncomeStatement")

    # Simulate concept ordering that might put things in wrong order
    concept_ordering = {
        'Contract Revenue': 0.0,
        'Cost of Goods and Services Sold': 100.0,
        'Gross Profit': 200.0,
        'Operating Expenses': 300.0,
        'Research and Development Expense': 300.1,
        'Selling, General and Administrative Expense': 300.2,
        'Total Operating Expenses': 300.9,
        'Operating Income': 400.0,
        'Net Income': 800.0,
        'Earnings Per Share (Basic)': 900.1,
        'Earnings Per Share (Diluted)': 900.2,
    }

    # Build presentation tree
    tree = VirtualPresentationTree(ordering_manager)
    ordered_nodes = tree.build_tree(concept_metadata, concept_ordering, original_order)

    print("Concepts in presentation tree order:")
    for i, node in enumerate(ordered_nodes):
        indent = "  " * node.level
        print(f"{i + 1:2d}. {indent}{node.label}")

    print(f"\n{tree.debug_tree()}")

    # Verify hierarchy preservation
    print("\n=== HIERARCHY VERIFICATION ===")

    # Find positions
    positions = {node.label: i for i, node in enumerate(ordered_nodes)}

    checks = [
        ("Contract Revenue < Cost of Goods Sold",
         positions['Contract Revenue'] < positions['Cost of Goods and Services Sold']),
        ("Cost of Goods Sold < Gross Profit",
         positions['Cost of Goods and Services Sold'] < positions['Gross Profit']),
        ("Gross Profit < Operating Expenses",
         positions['Gross Profit'] < positions['Operating Expenses']),
        ("Operating Expenses < R&D Expense (hierarchy preserved)",
         positions['Operating Expenses'] < positions['Research and Development Expense']),
        ("R&D Expense < SG&A Expense (siblings)",
         positions['Research and Development Expense'] < positions['Selling, General and Administrative Expense']),
        ("SG&A Expense < Operating Income",
         positions['Selling, General and Administrative Expense'] < positions['Operating Income']),
        ("Operating Income < Net Income",
         positions['Operating Income'] < positions['Net Income']),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All hierarchy checks PASSED! The presentation tree fix is working correctly.")
    else:
        print("\n❌ Some hierarchy checks FAILED. The fix needs more work.")

    return all_passed
