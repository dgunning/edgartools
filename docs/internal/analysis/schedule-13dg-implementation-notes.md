# Schedule 13D/G Implementation Notes

Quick reference for developers implementing or maintaining Schedule 13D/G code in EdgarTools.

## Quick Reference: SEC Technical Specification Compliance

### Critical Fields (Must Implement)

| Field | XML Element (13D) | XML Element (13G) | Type | Purpose |
|-------|------------------|------------------|------|---------|
| member_of_group | `<memberOfGroup>` | `<memberGroup>` | str ("a"/"b") | Joint vs separate filer |
| is_aggregate_exclude_shares | `<isAggregateExcludeShares>` | `<isAggregateExcludeShares>` | bool ("Y"/"N") | Exclude from aggregate |
| no_cik | `<reportingPersonNoCIK>` | `<reportingPersonNoCIK>` | bool ("Y"/"N") | Person has no CIK |
| cik | `<reportingPersonCIK>` | `<rptOwnerCik>` | str | CIK number |
| aggregate_amount | `<aggregateAmountOwned>` | `<shrsOrPrnAmt>` → `<value>` | int | Share count |
| percent_of_class | `<percentOfClass>` | `<pctOfClass>` | float | Ownership % |
| amendment_number | Form name | Form name | Optional[int] | Amendment sequence |

### Aggregation Algorithm

```python
def calculate_total_shares(reporting_persons):
    """
    Calculate total beneficial ownership per SEC specification.

    Algorithm:
    1. Filter out shares flagged for exclusion
    2. Check for joint filers (member_of_group == "a")
    3. If joint filers exist, take unique count (they report the same shares)
    4. Otherwise, sum all separate positions
    """
    # Step 1: Exclude flagged shares
    included = [p for p in reporting_persons
                if not p.is_aggregate_exclude_shares]

    if not included:
        return 0

    # Step 2: Identify joint filers
    group_members = [p for p in included if p.member_of_group == "a"]

    # Step 3: Aggregate appropriately
    if group_members:
        # Joint filers: all report the same shares
        # Take max in case of any data inconsistencies
        return max(p.aggregate_amount for p in group_members)
    else:
        # Separate filers or legacy data without member_of_group: sum all
        return sum(p.aggregate_amount for p in included)
```

### Common Pitfalls

1. **Don't use heuristics**: Always use `member_of_group` field, not "same share count = joint"
   - Why: Share counts can coincidentally match without being joint filers
   - Use the official SEC field instead

2. **Different element names**: 13D uses `memberOfGroup`, 13G uses `memberGroup`
   - Your parser must handle both
   - See `edgar/beneficial_ownership/schedule13.py` lines 223 and 591

3. **Boolean format**: SEC XML uses `"Y"`/`"N"`, not `"true"`/`"false"`
   - Use `get_bool()` function from `edgar.core`
   - Don't use `== 'true'` comparison

4. **Excluded shares**: Check `is_aggregate_exclude_shares` flag before aggregating
   - Filter these out in Step 1 of algorithm
   - They should NOT appear in total_shares calculation

5. **No CIK persons**: Handle `no_cik == True` cases (rare but valid)
   - When True, `cik` field will be empty or None
   - Don't fail validation on missing CIK if flag is set

### Test Cases Matrix

| Scenario | member_of_group | Expected Behavior | Example Filing |
|----------|----------------|-------------------|----------------|
| Joint filing (2 persons) | Both "a" | Take unique count (max) | Ryan Cohen / RC Ventures |
| Joint filing (3+ persons) | All "a" | Take unique count (max) | Abu Dhabi Investment |
| Separate filings | Both "b" or None | Sum all positions | TBD |
| Mixed (joint + separate) | Some "a", some "b" | Unique from "a" + sum "b" | TBD |
| Legacy (no field) | All None | Default to sum (safe fallback) | Older filings |
| With exclusions | Any | Filter excluded first, then aggregate | TBD |

### Real Filings for Testing

**Joint Filers:**
- **Ryan Cohen / RC Ventures**: 0001193125-22-071007 (Bed Bath & Beyond)
  - 2 persons, both `member_of_group == "a"`
  - Both report 9,800,000 shares (11.8%)
  - Correct total: 9,800,000 (not 19,600,000!)

- **Abu Dhabi Investment Authority**: Filed 2025-12-15
  - Multiple persons filing jointly
  - All have `member_of_group == "a"`

**Separate Filers:**
- TBD - need to find example where `member_of_group == "b"`

**With Exclusions:**
- TBD - need to find example where `isAggregateExcludeShares == "Y"`

**No CIK:**
- TBD - need to find example where `reportingPersonNoCIK == "Y"`

### XML Parsing Examples

#### Schedule 13D - Joint Filers

```xml
<reportingPersons>
  <reportingPersonInfo>
    <reportingPersonCIK>0001364742</reportingPersonCIK>
    <reportingPersonName>RC Ventures LLC</reportingPersonName>
    <citizenshipOrOrganization>DE</citizenshipOrOrganization>
    <soleVotingPower>9800000</soleVotingPower>
    <sharedVotingPower>0</sharedVotingPower>
    <soleDispositivePower>9800000</soleDispositivePower>
    <sharedDispositivePower>0</sharedDispositivePower>
    <aggregateAmountOwned>9800000</aggregateAmountOwned>
    <percentOfClass>11.8</percentOfClass>
    <typeOfReportingPerson>OO</typeOfReportingPerson>
    <memberOfGroup>a</memberOfGroup>  <!-- CRITICAL -->
    <isAggregateExcludeShares>N</isAggregateExcludeShares>
  </reportingPersonInfo>
  <reportingPersonInfo>
    <reportingPersonCIK>0001822844</reportingPersonCIK>
    <reportingPersonName>Ryan Cohen</reportingPersonName>
    <citizenshipOrOrganization>CA</citizenshipOrOrganization>
    <soleVotingPower>9800000</soleVotingPower>
    <sharedVotingPower>0</sharedVotingPower>
    <soleDispositivePower>9800000</soleDispositivePower>
    <sharedDispositivePower>0</sharedDispositivePower>
    <aggregateAmountOwned>9800000</aggregateAmountOwned>  <!-- SAME shares -->
    <percentOfClass>11.8</percentOfClass>
    <typeOfReportingPerson>IN</typeOfReportingPerson>
    <memberOfGroup>a</memberOfGroup>  <!-- Both are group members -->
    <isAggregateExcludeShares>N</isAggregateExcludeShares>
  </reportingPersonInfo>
</reportingPersons>
```

**Parsing Code:**
```python
for person_el in reporting_persons_el.find_all('reportingPersonInfo'):
    person = ReportingPerson(
        cik=child_text(person_el, 'reportingPersonCIK') or '',
        name=child_text(person_el, 'reportingPersonName') or '',
        # ... other fields ...
        member_of_group=child_text(person_el, 'memberOfGroup'),
        is_aggregate_exclude_shares=get_bool(child_text(person_el, 'isAggregateExcludeShares')),
        no_cik=get_bool(child_text(person_el, 'reportingPersonNoCIK'))
    )
```

#### Schedule 13G - Joint Filers

```xml
<coverPageHeaderReportingPersonDetails>
  <reportingPersonName>Marex Securities Products Inc.</reportingPersonName>
  <citizenshipOrOrganization>DE</citizenshipOrOrganization>
  <reportingPersonBeneficiallyOwnedNumberOfShares>
    <soleVotingPower>10000000.00</soleVotingPower>
    <sharedVotingPower>0.00</sharedVotingPower>
    <soleDispositivePower>10000000.00</soleDispositivePower>
    <sharedDispositivePower>0.00</sharedDispositivePower>
  </reportingPersonBeneficiallyOwnedNumberOfShares>
  <reportingPersonBeneficiallyOwnedAggregateNumberOfShares>10000000.00</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>
  <classPercent>5.1</classPercent>
  <memberGroup>a</memberGroup>  <!-- Different element name! -->
  <typeOfReportingPerson>CO</typeOfReportingPerson>
</coverPageHeaderReportingPersonDetails>
```

**Note**: 13G uses `<memberGroup>` not `<memberOfGroup>`.

### Code Structure

**Files:**
- `edgar/beneficial_ownership/models.py` - Data models (ReportingPerson, etc.)
- `edgar/beneficial_ownership/schedule13.py` - Main parsing and classes
- `edgar/beneficial_ownership/rendering.py` - Rich console display
- `tests/test_beneficial_ownership.py` - Test suite

**Key Functions:**
- `Schedule13D.parse_xml()` - Parse 13D XML to dict
- `Schedule13G.parse_xml()` - Parse 13G XML to dict
- `Schedule13D.total_shares` - Property that calculates total (uses algorithm)
- `Schedule13G.total_shares` - Property that calculates total (uses algorithm)

### Testing Strategy

1. **Unit Tests**: Test algorithm with mock data
   ```python
   def test_joint_filers_not_summed():
       # Create 2 persons with member_of_group="a"
       # Both have 1M shares
       # Assert total_shares == 1M (not 2M)
   ```

2. **Integration Tests**: Test with real XML
   ```python
   def test_parse_ryan_cohen_filing():
       # Use real filing XML
       # Verify member_of_group field is parsed
       # Verify total_shares is correct
   ```

3. **Regression Tests**: Ensure old behavior preserved
   ```python
   def test_legacy_filing_without_member_field():
       # Use old XML without memberOfGroup element
       # Should still work (sum all shares as fallback)
   ```

4. **Edge Cases**:
   - Empty reporting persons list
   - All persons have `is_aggregate_exclude_shares=True`
   - Mixed joint and separate filers
   - No CIK persons

### Migration Notes

**Breaking Changes:** None. All new fields have safe defaults:
- `member_of_group`: None (triggers sum behavior - safe fallback)
- `is_aggregate_exclude_shares`: False (include in total by default)
- `no_cik`: False (expect CIK by default)
- `amendment_number`: None (not all filings have this)

**Backward Compatibility:**
- Old code without these fields will continue to work
- Legacy filings without XML elements will use defaults
- New algorithm gracefully handles missing data

### Performance Considerations

- **Minimal overhead**: Only adds 3 fields to dataclass
- **No extra API calls**: All data from same XML document
- **Cached properties**: `total_shares` is a property, not a method

### References

- **SEC Specification**: `data/SCHEDULE13DG/Schedule13Dand13GTechnicalSpecification.pdf`
- **Gap Analysis**: `docs/internal/analysis/schedule-13dg-gap-analysis.md`
- **Research Document**: `docs/internal/knowledge/sec-forms/ownership/schedule-13d-13g-research.md`
- **Rendering Guide**: `docs/guides/schedule-13-rendering-guide.md`
- **Implementation**: `edgar/beneficial_ownership/schedule13.py`

### Quick Debugging

**Problem**: Total ownership showing 232% instead of 116%?
**Cause**: Not using `member_of_group` field
**Fix**: Check that joint filers (member_of_group=="a") are using max() not sum()

**Problem**: `is_aggregate_exclude_shares` always False even when XML has "Y"?
**Cause**: Using `== 'true'` instead of `get_bool()`
**Fix**: Use `get_bool(child_text(el, 'isAggregateExcludeShares'))`

**Problem**: `memberOfGroup` element not found in 13G?
**Cause**: Wrong element name - 13G uses `memberGroup`
**Fix**: Check form type and use correct element name

**Problem**: Parser fails on foreign filer without CIK?
**Cause**: Validation requires CIK even when `reportingPersonNoCIK=="Y"`
**Fix**: Check `no_cik` flag before validating CIK field

---

**Last Updated**: 2025-12-16
**Maintainer**: EdgarTools Team
