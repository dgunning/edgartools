"""
Regression tests for edgartools-n93w: five defects in the public FactQuery /
FactsView API, all in edgar/xbrl/facts.py.

GH #1287 -- sort_by() REORDERED THE SHARED CACHE. FactQuery.execute() starts with
`results = self._facts_view.get_facts()`, which hands back FactsView's cached list
BY REFERENCE. With no filter and no transform that identity survived all the way to
`results.sort(...)`, so sorting one query permanently reordered the cache every
other query reads from, and a later unrelated `.limit(n)` returned different facts.
Measured on 15 large 10-Ks: an unrelated 5-fact query changed on 15 of 15 before
the fix, 0 of 15 after.

GH #1288 -- the same sort block, two more faults. The guard
`self._sort_by in results[0]` decided from the FIRST ROW ONLY, so sorting by
'period_end' was skipped outright whenever the first fact happened to be an instant
(instants carry period_instant, not period_end). And the comparator
`f.get(self._sort_by, '')` kept an explicit None, so sort_by('numeric_value') raised
`TypeError: '<' not supported between instances of 'NoneType' and 'float'` on any
filing mixing numeric and text facts -- which is all 15 measured.

GH #1277 -- aggregate() summed fact['value'], the LEXICAL STRING as filed
('298085000000'), so `sum()` raised TypeError on ordinary numeric facts. The parsed
number was already sitting on the same row in numeric_value.

GH #1276 -- by_concept() rewrote EVERY underscore to a colon before matching, to
accept the element-id spelling 'us-gaap_Revenues'. A local name may contain a
literal underscore of its own, and rewriting it produced a second colon, so the
concept could never be matched. YUM files
yum:YUM_LesseeOperatingLeaseLeaseNotYetCommenced... (USD 90,000,000) and an exact
query for it returned zero rows.

GH #1286 -- facts_history(include_dimensions=True) was a no-op: it built its frame
with a query that leaves _include_dimensions False, so every dim_* column was
projected away, and the later `if include_dimensions:` branch searched that
projected frame for dim_* columns, found none, and fell through to the
undimensioned series. Sibling of #1243, which PR #1259 fixed only in
get_facts_with_dimensions().

FIXTURES. These are the real filed rows, transcribed from the filings named above
so the assertions are ground truth and the tests stay offline and deterministic:
Spectrum Brands 10-K 0000109177-24-000047 (us-gaap:DeferredCosts, six instant
facts across two fiscal years and two retirement-plan locations) and YUM 10-K
0001041061-25-000013.
"""

import pytest

from edgar.exceptions import ValidationError
from edgar.xbrl.facts import FactsView


def _spb_deferred_costs_facts():
    """The six us-gaap:DeferredCosts facts of Spectrum Brands' FY2024 10-K.

    Values as filed: $39.9M / $31.8M consolidated, $0 for country:US, and
    $12.4M / $9.6M for us-gaap:ForeignPlanMember. All six are INSTANT facts, so
    every one carries period_instant and none carries period_end -- which is what
    made this concept a witness for the date-column defect as well.
    """
    axis = 'dim_us-gaap_RetirementPlanSponsorLocationAxis'
    rows = [
        ('f-62', 'c-5', '2024-09-30', 39900000.0, None, 'Deferred charges and other'),
        ('f-63', 'c-6', '2023-09-30', 31800000.0, None, 'Deferred charges and other'),
        ('f-1492', 'c-400', '2024-09-30', 0.0, 'country:US', 'United States'),
        ('f-1493', 'c-392', '2023-09-30', 0.0, 'country:US', 'United States'),
        ('f-1494', 'c-401', '2024-09-30', 12400000.0, 'us-gaap:ForeignPlanMember', 'Non U.S. Plans'),
        ('f-1495', 'c-394', '2023-09-30', 9600000.0, 'us-gaap:ForeignPlanMember', 'Non U.S. Plans'),
    ]
    facts = []
    for fact_id, context_ref, instant, numeric, member, label in rows:
        fact = {
            'concept': 'us-gaap:DeferredCosts',
            'fact_id': fact_id,
            'context_ref': context_ref,
            'label': label,
            'value': str(int(numeric)),
            'numeric_value': numeric,
            'units': 'USD',
            'unit_ref': 'usd',
            'period_type': 'instant',
            'period_instant': instant,
            'period_end': None,
            'is_dimensioned': member is not None,
        }
        if member is not None:
            fact[axis] = member
        facts.append(fact)
    return facts


def _facts_view(facts):
    """A FactsView over a fixed fact list.

    get_facts() short-circuits on a populated _facts_cache, so no XBRL instance is
    needed -- and the cache being the very object queries read is precisely the
    thing GH #1287 corrupted.
    """
    view = FactsView(None)
    view._facts_cache = facts
    return view


# ---------------------------------------------------------------------------
# GH #1287 -- sort_by() must not reorder the shared cache
# ---------------------------------------------------------------------------

def test_sort_by_does_not_reorder_the_shared_fact_cache():
    facts = _spb_deferred_costs_facts()
    view = _facts_view(facts)

    order_before = [f['fact_id'] for f in view.get_facts()]
    unrelated_before = [f['fact_id'] for f in view.query().limit(3).execute()]

    view.query().sort_by('numeric_value').execute()

    assert [f['fact_id'] for f in view.get_facts()] == order_before, \
        "sort_by() reordered FactsView's cached list in place"
    assert [f['fact_id'] for f in view.query().limit(3).execute()] == unrelated_before, \
        "a later, independent query returned different facts after an unrelated sort"


def test_sort_by_still_returns_its_own_results_sorted():
    """The cache is left alone, but the caller still gets a sorted result."""
    view = _facts_view(_spb_deferred_costs_facts())
    values = [f['numeric_value'] for f in view.query().sort_by('numeric_value').execute()]
    assert values == sorted(values)

    descending = [f['numeric_value'] for f in
                  view.query().sort_by('numeric_value', ascending=False).execute()]
    assert descending == sorted(values, reverse=True)


# ---------------------------------------------------------------------------
# GH #1288 -- sparse columns and null values
# ---------------------------------------------------------------------------

def test_sort_by_sparse_column_is_not_skipped_because_of_the_first_row():
    """period_end is absent from the first fact and present on a later one.

    The old guard read results[0] alone and skipped the sort entirely.
    """
    facts = _spb_deferred_costs_facts()
    facts[0] = dict(facts[0], period_end=None, period_instant='2024-09-30')
    facts[3] = dict(facts[3], period_end='2023-09-30')
    facts[5] = dict(facts[5], period_end='2021-09-30')

    view = _facts_view(facts)
    ends = [f.get('period_end') for f in view.query().sort_by('period_end').execute()]
    populated = [e for e in ends if e]

    assert populated == ['2021-09-30', '2023-09-30'], \
        "sort_by() ignored a column that the first fact does not carry"


def test_sort_by_numeric_value_survives_non_numeric_facts():
    """A filing mixes numeric facts with text facts (a TextBlock has no
    numeric_value). Comparing None with a float used to raise TypeError."""
    facts = _spb_deferred_costs_facts()
    facts.append({
        'concept': 'us-gaap:AccountingPoliciesTextBlock',
        'fact_id': 'f-text', 'context_ref': 'c-5',
        'label': 'Accounting Policies', 'value': '<p>Basis of presentation</p>',
        'numeric_value': None, 'period_type': 'instant', 'period_instant': '2024-09-30',
    })
    view = _facts_view(facts)

    results = view.query().sort_by('numeric_value').execute()  # used to raise TypeError

    assert len(results) == 7
    numbers = [f['numeric_value'] for f in results if f['numeric_value'] is not None]
    assert numbers == sorted(numbers)
    assert results[-1]['fact_id'] == 'f-text', "a fact with no value should sort last"


def test_sort_by_mixed_types_in_one_column_does_not_raise():
    """value is a str on most facts, but a query may sort a column a filing
    populated inconsistently; the order must be total, not a TypeError."""
    facts = _spb_deferred_costs_facts()
    facts[0] = dict(facts[0], decimals=-5)
    facts[1] = dict(facts[1], decimals='INF')
    facts[2] = dict(facts[2], decimals=None)

    view = _facts_view(facts)
    results = view.query().sort_by('decimals').execute()
    assert len(results) == 6


# ---------------------------------------------------------------------------
# GH #1277 -- aggregate() must sum numbers, not the filed strings
# ---------------------------------------------------------------------------

def test_aggregate_sums_parsed_numbers_not_lexical_strings():
    view = _facts_view(_spb_deferred_costs_facts())

    results = view.query().aggregate('us-gaap_RetirementPlanSponsorLocationAxis', 'sum').execute()

    sums = {r['value']: r['values']['sum'] for r in results}
    # $12.4M (FY2024) + $9.6M (FY2023) as filed for the non-US plans.
    assert sums['us-gaap:ForeignPlanMember'] == 22000000.0
    assert sums['country:US'] == 0.0
    assert all(isinstance(v, (int, float)) for v in sums.values())


def test_aggregate_average_over_a_dimension():
    view = _facts_view(_spb_deferred_costs_facts())
    results = view.query().aggregate('us-gaap_RetirementPlanSponsorLocationAxis', 'average').execute()
    averages = {r['value']: r['values']['average'] for r in results}
    assert averages['us-gaap:ForeignPlanMember'] == 11000000.0


def test_aggregate_skips_facts_that_are_not_numbers():
    """A TextBlock carried on the same axis cannot be summed and must not
    poison the group."""
    facts = _spb_deferred_costs_facts()
    facts.append({
        'concept': 'us-gaap:PensionPlanTextBlock', 'fact_id': 'f-text',
        'context_ref': 'c-401', 'label': 'Pension narrative',
        'value': '<p>Non U.S. plans are funded locally.</p>', 'numeric_value': None,
        'dim_us-gaap_RetirementPlanSponsorLocationAxis': 'us-gaap:ForeignPlanMember',
    })
    view = _facts_view(facts)
    results = view.query().aggregate('us-gaap_RetirementPlanSponsorLocationAxis', 'sum').execute()
    sums = {r['value']: r['values']['sum'] for r in results}
    assert sums['us-gaap:ForeignPlanMember'] == 22000000.0


# ---------------------------------------------------------------------------
# GH #1276 -- a literal underscore inside a local name
# ---------------------------------------------------------------------------

YUM_CONCEPT = ('yum:YUM_LesseeOperatingLeaseLeaseNotYetCommenced'
               'AssumptionAndJudgmentValueOfUnderlyingLiabilityAmount')


def _yum_facts():
    """The extension concept YUM files with a schema-declared literal underscore
    in its local name, at USD 90,000,000 (fact f-1172 of 0001041061-25-000013)."""
    return [{
        'concept': YUM_CONCEPT,
        'fact_id': 'f-1172', 'context_ref': 'c-1', 'label': 'Value of underlying liability',
        'value': '90000000', 'numeric_value': 90000000.0,
        'units': 'USD', 'unit_ref': 'usd',
        'period_type': 'instant', 'period_instant': '2024-12-31',
    }]


def test_by_concept_exact_matches_a_local_name_containing_an_underscore():
    view = _facts_view(_yum_facts())
    results = view.query().by_concept(YUM_CONCEPT, exact=True).execute()
    assert len(results) == 1, "an already-qualified QName was rewritten and stopped matching"
    assert results[0]['numeric_value'] == 90000000.0


def test_by_concept_still_accepts_the_element_id_spelling():
    """'us-gaap_Revenues' for 'us-gaap:Revenues' is a documented convenience and
    must keep working: only the NAMESPACE separator is rewritten."""
    view = _facts_view(_spb_deferred_costs_facts())
    assert len(view.query().by_concept('us-gaap_DeferredCosts', exact=True).execute()) == 6
    assert len(view.query().by_concept('us-gaap:DeferredCosts', exact=True).execute()) == 6


def test_by_concept_element_id_spelling_of_a_name_with_an_underscore():
    """Both separators are underscores in the element-id form; only the first is
    the namespace."""
    view = _facts_view(_yum_facts())
    namespace, local = YUM_CONCEPT.split(':', 1)
    results = view.query().by_concept(f'{namespace}_{local}', exact=True).execute()
    assert len(results) == 1


def test_by_concept_regex_branch_keeps_the_literal_underscore():
    view = _facts_view(_yum_facts())
    assert len(view.query().by_concept('YUM_LesseeOperatingLease').execute()) == 1


# ---------------------------------------------------------------------------
# GH #1286 -- facts_history(include_dimensions=True)
# ---------------------------------------------------------------------------

def test_facts_history_include_dimensions_returns_the_breakdown():
    view = _facts_view(_spb_deferred_costs_facts())

    history = view.facts_history('us-gaap:DeferredCosts', include_dimensions=True)

    assert not history.empty, "include_dimensions never reached the query"
    assert set(history.columns) == {'No dimensions', 'country:US', 'us-gaap:ForeignPlanMember'}
    assert history.loc['2024-09-30', 'us-gaap:ForeignPlanMember'] == 12400000.0
    assert history.loc['2023-09-30', 'us-gaap:ForeignPlanMember'] == 9600000.0
    assert history.loc['2024-09-30', 'No dimensions'] == 39900000.0
    assert history.loc['2023-09-30', 'No dimensions'] == 31800000.0


def test_facts_history_falls_back_to_the_date_column_the_facts_populate():
    """date_col defaults to 'period_end', but an instant fact carries only
    period_instant -- and every balance-sheet concept is an instant, so the
    default used to drop every row and return an empty frame."""
    view = _facts_view(_spb_deferred_costs_facts())

    history = view.facts_history('us-gaap:DeferredCosts')

    assert not history.empty
    assert 'period_instant' in history.columns
    assert sorted(history['period_instant'].dt.strftime('%Y-%m-%d').unique()) == \
        ['2023-09-30', '2024-09-30']


def test_facts_history_rejects_a_date_column_that_does_not_exist():
    """A bad date_col must say so rather than raising a bare KeyError.

    ValidationError IS-A ValueError, so it carries the parameter and the valid
    options without breaking a caller that catches ValueError.
    """
    view = _facts_view(_spb_deferred_costs_facts())
    with pytest.raises(ValidationError, match="date_col"):
        view.facts_history('us-gaap:DeferredCosts', date_col='filing_date')
