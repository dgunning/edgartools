"""
Find all shares-related concepts in NVDA.
"""
from edgar import Company, set_identity

set_identity("AI Agent SaifA@example.com")

company = Company("NVDA")
facts = company.facts

# Find all concepts containing "shares" or "diluted"
shares_concepts = set()
for f in facts:
    concept_lower = f.concept.lower()
    if 'share' in concept_lower or 'dilut' in concept_lower:
        shares_concepts.add(f.concept)

print("Shares-related concepts found:")
for c in sorted(shares_concepts):
    count = len([f for f in facts if f.concept == c])
    print(f"  {c}: {count} facts")
