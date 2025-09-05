# Learning Pipeline Improvements

## Current Working System Analysis

### What Works
1. **133 companies** training set generated **120 high-confidence concepts**
2. **Two-tier system**: Static mappings (23) + Learned mappings (120)
3. **Generic GAAP concepts** provide good cross-company coverage
4. **30% occurrence threshold** filters noise while keeping useful concepts

### Key Success Factors
- Training on NYSE companies provides good concept diversity
- 0.5 confidence threshold in parser prevents false positives
- Virtual trees provide hierarchical structure

## Recommended Improvements

### 1. Training Set Optimization
```python
# Include diverse company samples
training_scenarios = {
    'mega_caps': ['AAPL', 'MSFT', 'GOOGL', 'AMZN'],  # Tech giants
    'industrials': get_companies_by_industry('Industrial'),
    'financials': get_companies_by_industry('Financial'),
    'healthcare': get_companies_by_industry('Healthcare'),
    'retail': get_companies_by_industry('Retail')
}
```

### 2. Confidence Score Tuning
- Keep **30% occurrence rate** for inclusion (working well)
- Add **confidence decay** for rare concepts:
  ```python
  if occurrence_rate < 0.5:
      confidence *= (occurrence_rate / 0.5)  # Scale down rare concepts
  ```

### 3. Concept Name Normalization
- Many companies use variations of the same concept
- Add normalization layer:
  ```python
  CONCEPT_ALIASES = {
      'RevenueFromContractWithCustomerExcludingAssessedTax': [
          'Revenues', 'NetRevenues', 'NetSales', 'TotalRevenues'
      ],
      'CostOfGoodsAndServicesSold': [
          'CostOfRevenue', 'CostOfSales', 'CostOfGoodsSold'
      ]
  }
  ```

### 4. Statement Type Validation
- Cross-validate statement assignments using calculation relationships
- If a concept sums to a known BalanceSheet total, classify as BalanceSheet

### 5. Incremental Learning
```python
def incremental_learn(new_companies, existing_mappings):
    """Add new companies without full retraining."""
    new_observations = extract_concepts(new_companies)
    merged = merge_observations(existing_mappings, new_observations)
    return recalculate_confidence(merged)
```

### 6. Quality Metrics
Track learning quality with:
- **Coverage rate**: % of facts mapped per company
- **Conflict rate**: Concepts mapped to multiple statements
- **Stability score**: How consistent mappings are across runs

### 7. Testing Strategy
```python
def validate_mappings(learned_mappings, test_companies):
    """Test mappings on holdout set."""
    results = {}
    for company in test_companies:
        facts = company.get_facts()
        coverage = calculate_coverage(facts, learned_mappings)
        results[company.ticker] = coverage
    return results
```

## Implementation Priority

1. **High Priority** (Immediate)
   - Keep current 133-company training set (it works!)
   - Don't over-engineer - 120 concepts provide good coverage
   - Document why 30% threshold works

2. **Medium Priority** (Next iteration)
   - Add concept aliasing for common variations
   - Implement incremental learning for new companies
   - Add coverage metrics to learning output

3. **Low Priority** (Future)
   - Industry-specific concept sets
   - Multi-taxonomy support (IFRS)
   - ML-based confidence optimization

## Key Principle
**"Don't fix what isn't broken"** - The current system with 120 learned concepts from 133 companies is working well for AAPL and likely other companies. Focus improvements on:
- Better documentation
- Incremental updates
- Coverage validation

Rather than trying to capture every company-specific concept.