from edgar import Company, set_identity
set_identity("Antigravity Agent <antigravity@example.com>")

print("Fetching MSFT facts...")
company = Company("MSFT")
facts = company.facts
df = facts.to_dataframe()

print("\nTop 20 Concepts by Count:")
print(df['concept'].value_counts().head(20))

print("\nSearching for 'nue' (Revenue/Venue) in concepts:")
rev_concepts = [c for c in df['concept'].unique() if 'Venue' in c or 'nue' in c]
for c in rev_concepts:
    print(c)
