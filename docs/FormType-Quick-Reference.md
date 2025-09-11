# FormType Quick Reference Guide

## 🚀 **Getting Started**

```python
from edgar import Company
from edgar.enums import FormType

company = Company("AAPL")

# New: IDE autocomplete for form types
filings = company.get_filings(form=FormType.ANNUAL_REPORT)

# Old: Still works perfectly
filings = company.get_filings(form="10-K")
```

## 📋 **All Available FormTypes**

### **Periodic Reports**
```python
FormType.ANNUAL_REPORT              # "10-K"
FormType.QUARTERLY_REPORT           # "10-Q" 
FormType.ANNUAL_REPORT_AMENDED      # "10-K/A"
FormType.QUARTERLY_REPORT_AMENDED   # "10-Q/A"
FormType.FOREIGN_ANNUAL             # "20-F"
FormType.CANADIAN_ANNUAL            # "40-F"
FormType.EMPLOYEE_BENEFIT_PLAN      # "11-K"
```

### **Current Reports**  
```python
FormType.CURRENT_REPORT             # "8-K"
FormType.FOREIGN_CURRENT_REPORT     # "6-K"
```

### **Proxy Statements**
```python
FormType.PROXY_STATEMENT            # "DEF 14A"
FormType.PRELIMINARY_PROXY          # "PRE 14A"
FormType.ADDITIONAL_PROXY           # "DEFA14A"
FormType.MERGER_PROXY               # "DEFM14A"
```

### **Registration Statements**
```python
FormType.REGISTRATION_S1            # "S-1"
FormType.REGISTRATION_S3            # "S-3"
FormType.REGISTRATION_S4            # "S-4" 
FormType.REGISTRATION_S8            # "S-8"
FormType.FOREIGN_REGISTRATION_F1    # "F-1"
FormType.FOREIGN_REGISTRATION_F3    # "F-3"
FormType.FOREIGN_REGISTRATION_F4    # "F-4"
```

### **Prospectuses**
```python
FormType.PROSPECTUS_424B1           # "424B1"
FormType.PROSPECTUS_424B2           # "424B2"
FormType.PROSPECTUS_424B3           # "424B3"
FormType.PROSPECTUS_424B4           # "424B4"
FormType.PROSPECTUS_424B5           # "424B5"
```

### **Ownership Reports**
```python
FormType.BENEFICIAL_OWNERSHIP_13D   # "SC 13D"
FormType.BENEFICIAL_OWNERSHIP_13G   # "SC 13G"
```

### **Other Important Forms**
```python
FormType.SPECIALIZED_DISCLOSURE     # "SD"
FormType.ASSET_BACKED_SECURITIES    # "ARS"
FormType.LATE_10K_NOTICE           # "NT 10-K"
FormType.LATE_10Q_NOTICE           # "NT 10-Q"
```

## 📚 **Form Collections**

```python
from edgar.enums import PERIODIC_FORMS, PROXY_FORMS, REGISTRATION_FORMS

# Pre-defined collections for common workflows
PERIODIC_FORMS      # [10-K, 10-Q, 10-K/A, 10-Q/A]
PROXY_FORMS         # [DEF 14A, PRE 14A, DEFA14A, DEFM14A]  
REGISTRATION_FORMS  # [S-1, S-3, S-4, S-8]
```

## ⚡ **Usage Examples**

### **Basic Usage**
```python
# Annual reports with autocomplete
annual_filings = company.get_filings(form=FormType.ANNUAL_REPORT)

# Quarterly reports  
quarterly_filings = company.get_filings(form=FormType.QUARTERLY_REPORT)

# Current reports (8-Ks)
current_filings = company.get_filings(form=FormType.CURRENT_REPORT)
```

### **Combined Filters**
```python
# Recent annual reports
filings = company.get_filings(
    form=FormType.ANNUAL_REPORT,
    year=[2022, 2023]
)

# Proxy statements this year
proxies = company.get_filings(
    form=FormType.PROXY_STATEMENT,
    year=2023
)
```

### **Multiple Form Types**
```python
# Mix FormType and strings
filings = company.get_filings(form=[
    FormType.ANNUAL_REPORT,
    FormType.QUARTERLY_REPORT,
    "8-K"  # String still works
])

# Using form collections
periodic_filings = company.get_filings(form=PERIODIC_FORMS)
```

## 🛡️ **Error Handling**

```python
# Typos get helpful suggestions
try:
    filings = company.get_filings(form="10k")  # Missing hyphen
except ValueError as e:
    print(e)
    # "Invalid form type '10k'. Use FormType enum for autocomplete..."
```

## 🔄 **Migration Guide**

### **No Breaking Changes**
```python
# ALL existing code works unchanged:
company.get_filings(form="10-K")                    # ✅ Works
company.get_filings(form=["10-K", "10-Q"])          # ✅ Works  
company.get_filings(form="8-K", year=2023)          # ✅ Works
```

### **Gradual Adoption**
```python
# Option 1: Keep using strings
filings = company.get_filings(form="10-K")

# Option 2: Migrate to FormType for autocomplete
filings = company.get_filings(form=FormType.ANNUAL_REPORT)

# Option 3: Mix as convenient
filings = company.get_filings(form=[FormType.ANNUAL_REPORT, "8-K"])
```

## 💡 **IDE Benefits**

- **Autocomplete**: Type `FormType.` to see all 31 options
- **Documentation**: Hover over enums to see SEC form codes  
- **Type Safety**: mypy/PyCharm catches invalid form parameters
- **Refactoring**: Find all usages of specific form types

## 🔗 **Links**

- **GitHub Discussion**: [#423 Type Hinting Implementation](https://github.com/dgunning/edgartools/discussions/423)
- **Feature Branch**: `feat/strenum-type-hinting`
- **Test Files**: Run `python formtype_demo_examples.py` for live examples

---

*Perfect backwards compatibility + modern Python typing = Happy developers! 🎉*