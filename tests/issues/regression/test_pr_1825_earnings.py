"""EarningsRelease must preserve reported EPS and non-USD table units.

GitHub PR: https://github.com/dgunning/edgartools/pull/1825

Ground truth: TSM 6-K 0001046179-26-000726, exhibit
a3q26e_withguidancexfinal.htm (2026-10-15). Original SEC bytes downloaded
2026-11-01 before implementation: TWD 763,064 million net income and NT$29.43
EPS with a trailing letter footnote. Fixture provenance is in its README.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.earnings import EarningsRelease, RowType, _classify_row_type, _parse_numeric, _table_context

FIXTURES = Path(__file__).parents[2] / 'fixtures' / 'html' / 'issue1824'


@pytest.fixture
def income():
    attachment = SimpleNamespace(
        content=(FIXTURES / 'a3q26e_withguidancexfinal.htm').read_text(),
        document='a3q26e_withguidancexfinal.htm')
    return EarningsRelease(attachment).income_statement


def test_real_tsm_units_and_eps_are_correct_without_financials_adapter(income):
    assert income.currency == 'TWD'
    assert income.scaled_dataframe.loc['Net income'].iloc[0] == 763_064_000_000
    assert income.scaled_dataframe.loc['EPS (NT$)'].iloc[0] == 29.43
    assert income.get_row_type('EPS (NT$)', 5) is RowType.PER_SHARE
    assert 'actual TWD' in income.to_context()
    assert 'actual USD' not in income.to_context()
    assert json.loads(income.to_json())['metadata']['currency'] == 'TWD'
    facts = income.to_facts_dataframe()
    amounts = facts.loc[facts['label'] == 'Net income']
    eps = facts.loc[facts['label'] == 'EPS (NT$)']
    assert set(amounts['unit']) == {'TWD'}
    assert amounts['numeric_value'].iloc[0] == 763_064_000_000
    assert set(eps['unit']) == {'TWD/shares'}
    assert eps['numeric_value'].iloc[0] == 29.43


def test_cleaned_tables_keep_currency_and_row_types(income):
    renamed = income.with_standardized_labels({'EPS (NT$)': 'Reported EPS'})
    cleaned = income.with_clean_columns()
    assert renamed.currency == cleaned.currency == 'TWD'
    assert renamed.scaled_dataframe.loc['Reported EPS'].iloc[0] == 29.43
    assert cleaned.scaled_dataframe.loc['EPS (NT$)'].iloc[0] == 29.43


@pytest.mark.parametrize('cell, expected', [
    ('29.43b', 29.43), ('(29.43)b', -29.43), ('-29.43b', -29.43),
    ('1,234a', 1234.0), ('0.00b', 0.0), ('1.2B', '1.2B'),
    ('29.43 basis points', '29.43 basis points'), ('1e3', 1000.0),
])
def test_numeric_footnotes_do_not_discard_values_or_prose(cell, expected):
    assert _parse_numeric(cell) == expected


@pytest.mark.parametrize('label, expected', [
    ('Weighted average shares used in EPS', RowType.SHARES),
    ('EPS growth rate', RowType.PERCENTAGE),
])
def test_eps_reference_does_not_override_share_counts_or_percentages(label, expected):
    assert _classify_row_type(label) is expected


def test_context_without_node_in_parent_does_not_raise():
    parent = SimpleNamespace(children=[SimpleNamespace(content='unrelated')], parent=None)
    node = SimpleNamespace(parent=parent)
    assert _table_context(node, 'Income') == (['Income'], [])


def test_context_reads_non_string_dom_content_safely():
    before = SimpleNamespace(content=['not text'], text=lambda: '(Unit: TWD million)')
    after = SimpleNamespace(content=5, text=lambda: 'Reported footnote')
    parent = SimpleNamespace(children=[], parent=None)
    node = SimpleNamespace(parent=parent)
    parent.children = [before, node, after]
    assert _table_context(node, 'Income') == (['Income', '(Unit: TWD million)'], ['Reported footnote'])
