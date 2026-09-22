"""Tests for Statement.extension_arcs() — Issue #766 / edgartools-ixk9 Layer 2.

Extension arcs surface filer-authored concepts that participate in a statement's
calculation linkbase but are absent from its presentation tree — concepts that
silently drop out of `render()` today.

Ground-truth: JPM FY2023 10-K cash flow statement contains two such arcs:
    jpm:NetChangeInAdvancesToandInvestmentsInSubsidiaries
        -> us-gaap:NetCashProvidedByUsedInInvestingActivities  w=+1.0
    jpm:NetBorrowingsFromSubsidiaries
        -> us-gaap:NetCashProvidedByUsedInFinancingActivities  w=+1.0
"""

from pathlib import Path

import pytest

from edgar.xbrl.statements import ExtensionArc, Statement
from edgar.xbrl.xbrl import XBRL


@pytest.fixture(scope='module')
def jpm_xbrl():
    return XBRL.from_directory(Path('tests/fixtures/xbrl/jpm/10k_2024'))


@pytest.fixture(scope='module')
def jpm_cash_flow(jpm_xbrl):
    return Statement(
        jpm_xbrl, 'CashFlowStatement',
        canonical_type='CashFlowStatement', skip_concept_check=True,
    )


@pytest.fixture(scope='module')
def jpm_income(jpm_xbrl):
    return Statement(
        jpm_xbrl, 'IncomeStatement',
        canonical_type='IncomeStatement', skip_concept_check=True,
    )


@pytest.fixture(scope='module')
def aapl_xbrl():
    return XBRL.from_directory(Path('tests/fixtures/xbrl/aapl/10k_2023'))


@pytest.mark.fast
class TestJPMCashFlowExtensions:
    """JPM cash flow has two extension arcs missing from its presentation tree."""

    def test_two_extension_arcs_found(self, jpm_cash_flow):
        arcs = jpm_cash_flow.extension_arcs()
        assert len(arcs) == 2, (
            f"Expected exactly 2 extension arcs in JPM cash flow, got {len(arcs)}. "
            "If this changed, the calc/presentation diff is no longer surfacing them."
        )

    def test_net_change_in_advances_arc_present(self, jpm_cash_flow):
        """jpm:NetChangeInAdvancesToandInvestmentsInSubsidiaries -> investing activities, w=+1.0."""
        arcs = jpm_cash_flow.extension_arcs()
        match = [a for a in arcs if a.concept == 'NetChangeInAdvancesToandInvestmentsInSubsidiaries']
        assert len(match) == 1
        arc = match[0]
        assert arc.concept_taxonomy == 'jpm'
        assert arc.parent_concept == 'NetCashProvidedByUsedInInvestingActivities'
        assert arc.parent_taxonomy == 'us-gaap'
        assert arc.weight == 1.0

    def test_net_borrowings_arc_present(self, jpm_cash_flow):
        """jpm:NetBorrowingsFromSubsidiaries -> financing activities, w=+1.0."""
        arcs = jpm_cash_flow.extension_arcs()
        match = [a for a in arcs if a.concept == 'NetBorrowingsFromSubsidiaries']
        assert len(match) == 1
        arc = match[0]
        assert arc.parent_concept == 'NetCashProvidedByUsedInFinancingActivities'
        assert arc.parent_taxonomy == 'us-gaap'
        assert arc.weight == 1.0

    def test_role_uri_matches_cash_flow_statement(self, jpm_cash_flow):
        """role_uri must be the full URI for the cash flow statement, not another role."""
        arcs = jpm_cash_flow.extension_arcs()
        assert all(a.role_uri.endswith('ConsolidatedStatementsofCashFlows') for a in arcs)


@pytest.mark.fast
class TestStructuralVsValueMode:
    """Default mode is structural (no values). include_values=True emits one arc per fact."""

    def test_structural_mode_has_no_values(self, jpm_cash_flow):
        arcs = jpm_cash_flow.extension_arcs()
        for arc in arcs:
            assert arc.value is None
            assert arc.period_key is None
            assert arc.context_ref is None

    def test_values_mode_emits_one_arc_per_period(self, jpm_cash_flow):
        """Each of the 2 concepts has 3 fiscal-year facts → 6 ExtensionArcs total."""
        arcs = jpm_cash_flow.extension_arcs(include_values=True)
        assert len(arcs) == 6, (
            f"Expected 6 arcs (2 concepts × 3 years), got {len(arcs)}"
        )

    def test_values_mode_specific_value(self, jpm_cash_flow):
        """JPM FY2023: NetBorrowingsFromSubsidiaries = -2.249B."""
        arcs = jpm_cash_flow.extension_arcs(include_values=True)
        match = [
            a for a in arcs
            if a.concept == 'NetBorrowingsFromSubsidiaries'
            and a.period_key == 'duration_2023-01-01_2023-12-31'
        ]
        assert len(match) == 1
        assert match[0].value == -2249000000.0

    def test_values_mode_populates_period_and_context(self, jpm_cash_flow):
        arcs = jpm_cash_flow.extension_arcs(include_values=True)
        for arc in arcs:
            assert arc.period_key is not None
            assert arc.context_ref is not None
            assert arc.value is not None


@pytest.mark.fast
class TestStandardTaxonomyExclusion:
    """Standard taxonomies (us-gaap, dei, srt, ...) must never appear in results."""

    def test_no_standard_taxonomies_surface(self, jpm_cash_flow):
        arcs = jpm_cash_flow.extension_arcs()
        for arc in arcs:
            assert arc.concept_taxonomy not in {'us-gaap', 'dei', 'srt', 'ifrs'}, (
                f"Standard taxonomy {arc.concept_taxonomy!r} leaked into extension_arcs"
            )

    def test_jpm_income_statement_has_no_gaps(self, jpm_income):
        """JPM income statement has every calc concept also in presentation tree → 0 arcs."""
        arcs = jpm_income.extension_arcs()
        assert arcs == [], (
            f"JPM income statement should have 0 extension gaps, got {len(arcs)}"
        )


@pytest.mark.fast
class TestSilenceCheck:
    """Bad/unresolvable inputs return [] cleanly, never None."""

    def test_unresolvable_statement_returns_empty_list(self, jpm_xbrl):
        """A statement type that can't be resolved returns an empty list."""
        stmt = Statement(
            jpm_xbrl, 'http://example.com/nonexistent-role',
            canonical_type=None, skip_concept_check=True,
        )
        result = stmt.extension_arcs()
        assert isinstance(result, list)
        assert result == []

    def test_returns_list_not_none(self, jpm_cash_flow):
        result = jpm_cash_flow.extension_arcs()
        assert isinstance(result, list), "Must return list, never None"


@pytest.mark.fast
class TestNoRegressionInRender:
    """The key promise: adding extension_arcs() must NOT alter render() output."""

    def test_render_output_unchanged_by_extension_arcs_calls(self, jpm_cash_flow):
        """Calling extension_arcs() must not mutate state observable by render()."""
        # Snapshot render output before
        before = jpm_cash_flow.render()
        before_repr = repr(before)

        # Call extension_arcs in both modes
        jpm_cash_flow.extension_arcs()
        jpm_cash_flow.extension_arcs(include_values=True)

        # Render again
        after = jpm_cash_flow.render()
        after_repr = repr(after)

        assert before_repr == after_repr, (
            "render() output changed after calling extension_arcs() — "
            "the new method must be side-effect-free"
        )


@pytest.mark.fast
class TestExtensionArcDataclass:
    """ExtensionArc is part of the public API."""

    def test_dataclass_fields(self):
        arc = ExtensionArc(
            concept='Foo', concept_taxonomy='abc',
            parent_concept='Bar', parent_taxonomy='us-gaap',
            weight=1.0, label='Foo bar', role_uri='http://example.com/role',
            element_id='abc_Foo',
        )
        assert arc.value is None
        assert arc.period_key is None
        assert arc.context_ref is None

    def test_dataclass_accepts_values(self):
        arc = ExtensionArc(
            concept='Foo', concept_taxonomy='abc',
            parent_concept='Bar', parent_taxonomy='us-gaap',
            weight=-1.0, label='', role_uri='http://example.com/role',
            element_id='abc_Foo',
            value=1234.0, period_key='duration_2023-01-01_2023-12-31',
            context_ref='c-1',
        )
        assert arc.value == 1234.0
        assert arc.weight == -1.0
