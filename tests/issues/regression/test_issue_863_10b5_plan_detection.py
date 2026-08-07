#!/usr/bin/env python3
"""
Regression test for GitHub issue #863: Rule 10b5-1 plan detection.

This test ensures that the official Form 4/5 aff10b5One checkbox takes
precedence when present, and that footnote fallback matching distinguishes
Rule 10b5-1 trading plans from the separate anti-fraud Rule 10b-5.

GitHub Issue: https://github.com/dgunning/edgartools/issues/863
"""

from pathlib import Path

import pytest

from edgar.ownership.core import detect_10b5_1_plan
from edgar.ownership.forms import Form4, _parse_aff10b5_one
from edgar.ownership.summary import TransactionSummary
from edgar.ownership.summary_records import TransactionActivity

FIXTURE_374WATER = Path('data/ownership/374WaterForm4.xml')


def _summary(value=None, all_footnotes_text=''):
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
        all_footnotes_text=all_footnotes_text,
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
    summary = _summary(value=checkbox_value)

    assert summary.has_10b5_1_plan is checkbox_value


@pytest.mark.parametrize('checkbox_value', [True, False])
def test_aff10b5_one_checkbox_overrides_conflicting_footnotes(checkbox_value):
    # The structured checkbox is authoritative even when footnotes say otherwise.
    summary = _summary(
        value=checkbox_value,
        all_footnotes_text='Shares sold pursuant to a Rule 10b5-1 plan.',
    )

    assert summary.has_10b5_1_plan is checkbox_value


def test_full_footnote_scan_detects_plan_when_per_transaction_text_is_empty():
    # Problem 2 from #863: no checkbox and empty per-transaction footnote
    # attribution, but the filing's footnotes clearly describe a 10b5-1 plan.
    summary = _summary(
        value=None,
        all_footnotes_text='These shares were sold pursuant to a Rule 10b5-1 plan.',
    )

    assert summary.has_10b5_1_plan is True


def test_full_footnote_scan_returns_false_for_unrelated_footnotes():
    summary = _summary(value=None, all_footnotes_text='Shares gifted to a family trust.')

    assert summary.has_10b5_1_plan is False


def test_no_checkbox_and_no_footnotes_is_none():
    summary = _summary(value=None, all_footnotes_text='')

    assert summary.has_10b5_1_plan is None


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


@pytest.mark.skipif(not FIXTURE_374WATER.exists(), reason='fixture not available')
def test_aff10b5_one_checkbox_flows_through_xml_parsing_end_to_end():
    # 374Water Form 4 carries <aff10b5One>false</aff10b5One>; the structured value
    # must survive parse_xml -> get_ownership_summary -> has_10b5_1_plan.
    form4 = Form4.parse_xml(FIXTURE_374WATER.read_text())

    assert form4.aff10b5_one is False
    summary = form4.get_ownership_summary()
    assert summary.aff10b5_one is False
    assert summary.has_10b5_1_plan is False


@pytest.mark.network
@pytest.mark.vcr
def test_problem2_real_pre_checkbox_filing_resolves_via_per_transaction_footnotes():
    """End-to-end on the reported Problem 2 filing: AAPL insider Form 4 (2022).

    Pinned by accession (not ``.latest()``) and VCR-backed for determinism. This
    is a pre-2023-04 Form 4 that carries NO ``<aff10b5One>`` checkbox; its 10b5-1
    footnote is attached to ``<securityTitle>`` (not ``<transactionCoding>``).

    Originally (#863 Problem 2) per-transaction footnote attribution came through
    empty, so ``has_10b5_1_plan`` returned ``None`` and only the full-footnote
    fallback could recover it. After edgartools-t043 fixed the attribution, each
    transaction carries its real footnote IDs and per-transaction detection works
    directly. (The full-footnote fallback remains a safety net, covered by the
    synthetic tests above.)

    Reported in https://github.com/dgunning/edgartools/issues/863 (Problem 2).
    """
    from edgar import Filing

    filing = Filing(form='4', company='Adams Katherine L.', cik=1462356,
                    filing_date='2022-05-06', accession_no='0000320193-22-000061')
    summary = filing.obj().get_ownership_summary()

    # No structured checkbox on this pre-2023 filing.
    assert summary.aff10b5_one is None
    # Per-transaction footnote attribution is now populated (edgartools-t043)...
    assert all(t.footnote_ids for t in summary.transactions)
    # ...and at least one transaction's own footnotes describe the 10b5-1 plan.
    assert any(t.is_10b5_1_plan is True for t in summary.transactions)
    assert summary.has_10b5_1_plan is True
