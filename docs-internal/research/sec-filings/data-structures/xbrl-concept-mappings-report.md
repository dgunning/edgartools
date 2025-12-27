# XBRL Concept Mappings Update Report

## Scope
This report documents updates to the core XBRL standardization mappings and the mapping logic used to normalize concepts across taxonomies. Changes focus on revenue hierarchy coverage, IFRS alignment for key totals, and safer mapping resolution.

## Sources and evidence
- `edgar/xbrl/standardization/concept_mappings.json`
- `edgar/xbrl/standardization/company_mappings/tsla_mappings.json`
- `edgar/xbrl/standardization/company_mappings/msft_mappings.json`
- `edgar/xbrl/stitching/ordering.py`
- `edgar/xbrl/statement_resolver.py`
- `tests/issues/reproductions/data-quality/issue_446_root_cause_investigation.py`
- `edgar/standardization/synonym_groups.py`
- `edgar/xbrl/standardization/core.py`
- `edgar/xbrl/standardization/utils.py`

## Mapping updates
- Revenue hierarchy expanded with Service, Subscription, and Leasing categories; total revenue and contract revenue now include IFRS tags where evidence exists.
- Industry-specific revenue labels (Automotive, Energy, Software, Hardware, Platform) were added as placeholders so company mappings can supply tags without overloading core mappings.
- Added `us-gaap_CostOfServices` under Cost of Goods and Services Sold to cover service-model cost reporting.
- Added `us-gaap_OtherNonoperatingIncomeExpense` for non-operating coverage consistency with ordering templates.
- Reclassified `us-gaap_IncomeTaxesPaidNet` into a new cash flow line item (Income Taxes Paid (Net)) and removed it from Income Tax Expense.
- Deferred Revenue now includes contract liability concepts for better taxonomy alignment.
- Added IFRS tags for Operating Income, Profit/Loss, EPS Basic/Diluted, Total Assets, Total Liabilities, Total Equity, and key cash flow totals.
- Cleaned a label typo (Proceeds from Sale of Debt Securities) and normalized indentation for consistency.
- Added a Sales Expense placeholder to prevent accidental duplication with Selling Expense until company-specific tags are available.

## Mapping logic changes
- Mapping loaders now skip `_comment_*` keys in core and company mapping files to prevent non-mapping strings from being treated as concepts.
- Concept normalization now standardizes `:` vs `_` separators and aligns `us_gaap`/`ifrs_full` variants to `us-gaap` and `ifrs-full` prefixes.
- Entity detection uses normalized prefixes so both `tsla:Concept` and `tsla_Concept` resolve consistently.
- Hierarchy rules ignore comment keys to keep rule dictionaries clean.

## Validation snapshot
- `validate_mappings` reports 0 errors, 1 warning, 1 info.
- Warning: `edgar/xbrl/standardization/company_mappings/brka_mappings.json` is missing metadata.
- Info: 46 mapping labels exist in core mappings but are not represented in `StandardConcept` (pre-existing; unchanged in this update).

## Rationale notes
- IFRS tags were added only where the repository already references those concepts (statement resolver and issue 446 investigation list).
- Industry-specific revenue categories remain empty in core mappings because company mappings already define the relevant tags and preserve business context.

## Follow-ups
- Add metadata to `edgar/xbrl/standardization/company_mappings/brka_mappings.json` to clear the validation warning.
- Consider expanding `StandardConcept` if the extra mapping labels are intended to be first-class standardized concepts.
