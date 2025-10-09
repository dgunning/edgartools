"""
Quick test of the abstract_detection module
"""

from edgar.xbrl.abstract_detection import is_abstract_concept

# Test cases
test_cases = [
    ('us-gaap_StatementOfStockholdersEquityAbstract', True),
    ('us-gaap_IncreaseDecreaseInStockholdersEquityRollForward', True),
    ('us-gaap_StatementTable', True),
    ('us-gaap_StatementEquityComponentsAxis', True),
    ('us-gaap_Revenue', False),
    ('us-gaap_NetIncomeLoss', False),
    ('us-gaap_StockholdersEquity', False),
    ('us-gaap_SomethingAbstract', True),  # Pattern match
    ('us-gaap_SomethingRollForward', True),  # Pattern match
    ('us-gaap_SomethingLineItems', True),  # Pattern match
]

print("Testing abstract_detection module:")
print("=" * 80)

for concept, expected in test_cases:
    result = is_abstract_concept(concept)
    status = "✅" if result == expected else "❌"
    print(f"{status} {concept}: {result} (expected {expected})")

print()
print("All tests completed!")
