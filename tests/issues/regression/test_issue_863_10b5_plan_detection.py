#!/usr/bin/env python3
"""
Regression test for GitHub issue #863: Rule 10b5-1 plan detection.

This test ensures that the official Form 4/5 aff10b5One checkbox takes
precedence when present, and that footnote fallback matching distinguishes
Rule 10b5-1 trading plans from the separate anti-fraud Rule 10b-5.

GitHub Issue: https://github.com/dgunning/edgartools/issues/863
"""

import pytest

from edgar.ownership.core import detect_10b5_1_plan
from edgar.ownership.forms import _parse_aff10b5_one
from edgar.ownership.summary import TransactionSummary
from edgar.ownership.summary_records import TransactionActivity


def _summary_with_checkbox(value):
    return TransactionSummary(
        reporting_date='2026-05-30',
        issuer_name='Walmart Inc.',
        issuer_ticker='WMT',
        insider_name='Reporting Person',
        position='Officer',
        form_type='4',
        transactions=[
            TransactionActivity(
                transaction_type='sale',
                code='S',
                footnotes_text='',
            )
        ],
        aff10b5_one=value,
    )


@pytest.mark.parametrize(
    ('raw_value', 'expected'),
    [
        ('1', True),
        ('true', True),
        ('0', False),
        ('false', False),
        (None, None),
        ('', None),
    ],
)
def test_aff10b5_one_checkbox_values_are_parsed(raw_value, expected):
    assert _parse_aff10b5_one(raw_value) is expected


@pytest.mark.parametrize('checkbox_value', [True, False])
def test_aff10b5_one_checkbox_takes_precedence_over_empty_footnotes(checkbox_value):
    summary = _summary_with_checkbox(checkbox_value)

    assert summary.has_10b5_1_plan is checkbox_value


def test_anti_fraud_rule_10b5_is_not_a_10b5_1_trading_plan():
    assert (
        detect_10b5_1_plan('The Reporting Person violated anti-fraud Rule 10b-5.')
        is False
    )


@pytest.mark.parametrize(
    'text',
    [
        'Sale under a 10b5-1 trading plan.',
        'Sale under a 10b5 1 trading plan.',
        'Sale under a 10b51 trading plan.',
        'Sale under a 10b-5-1 trading plan.',
        'Sale under a 10b5\u20141 trading plan.',
        'Sale under a 10b5 plan.',
        'Sale under a 10b-5 plan.',
    ],
)
def test_typographic_10b5_1_variants_are_detected(text):
    assert detect_10b5_1_plan(text) is True
