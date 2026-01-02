# Mapping Quality Analysis Report

**Generated**: C:\edgartools_git

---

## 1. Coverage Analysis

### Core Mapping
- **Total Fields**: 18
- **Required Fields**: 16
- **Mapped Fields**: 16
- **Coverage Rate**: 100.0%
- **Fields with Fallbacks**: 9 (56.2%)

## 2. Confidence Analysis

### Distribution
- **High Confidence** (≥30%): 11
- **Medium Confidence** (15-30%): 3
- **Low Confidence** (<15%): 2

### Occurrence Rates
- **Mean**: 48.2%
- **Min**: 11.6% (`depreciationAndAmortization`)
- **Max**: 82.0% (`earningsPerShareBasic`)

### Low Confidence Mappings
| Field | Occurrence Rate |
|-------|----------------|
| `depreciationAndAmortization` | 11.6% |
| `interestExpense` | 11.9% |

## 3. Conflict Analysis

✅ **No conflicts found**

**Missing Parent Concepts** (5):
- `EarningsPerShareAbstract`
- `IncomeStatementAbstract`
- `NonoperatingIncomeExpenseAbstract`
- `OperatingExpensesAbstract`
- `WeightedAverageNumberOfSharesOutstandingAbstract`

## 4. Sector Overlay Analysis

### Banking
- **Total Fields**: 7
- **Overridden**: 0
- **Sector-Specific**: 0

### Insurance
- **Total Fields**: 9
- **Overridden**: 1
- **Sector-Specific**: 0

**Overridden Mappings**:
| Field | Core Concept | Sector Concept | Sector Occ | Global Occ |
|-------|--------------|----------------|------------|------------|
| `revenue` | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` | `us-gaap:Revenues` | 52.3% | 24.1% |

### Utilities
- **Total Fields**: 9
- **Overridden**: 1
- **Sector-Specific**: 0

**Overridden Mappings**:
| Field | Core Concept | Sector Concept | Sector Occ | Global Occ |
|-------|--------------|----------------|------------|------------|
| `revenue` | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` | `us-gaap:Revenues` | 40.2% | 24.1% |

## 5. Recommendations
✅ **Mappings look good!** Ready for production deployment.