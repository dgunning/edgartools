"""Tests for XBRL.calculation_linkbase() — Issue #766 / edgartools-ixk9 Layer 1.

These tests assert specific values from real SEC filings (JPM FY2023 10-K and
AAPL FY2023 10-K) per the verification constitution: data correctness assertions
on specific concept/parent/weight tuples, not just `is not None`.
"""

from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl.xbrl import XBRL


@pytest.fixture(scope='module')
def jpm_10k_2024():
    """JPM 10-K filed 2024-02-16 (FY2023). Heaviest extension load in the fixture set."""
    return XBRL.from_directory(Path('tests/fixtures/xbrl/jpm/10k_2024'))


@pytest.fixture(scope='module')
def aapl_10k_2023():
    """AAPL 10-K filed 2023 (FY2023). Tech control — minimal extension footprint."""
    return XBRL.from_directory(Path('tests/fixtures/xbrl/aapl/10k_2023'))


EXPECTED_COLUMNS = [
    'concept', 'concept_taxonomy', 'parent_concept', 'parent_taxonomy',
    'weight', 'role_uri', 'role_short', 'menucat', 'is_abstract', 'label',
]


@pytest.mark.fast
class TestSchema:
    """The DataFrame schema is part of the public API contract."""

    def test_columns_present_and_ordered(self, jpm_10k_2024):
        df = jpm_10k_2024.calculation_linkbase()
        assert list(df.columns) == EXPECTED_COLUMNS

    def test_dtypes_are_reasonable(self, jpm_10k_2024):
        df = jpm_10k_2024.calculation_linkbase()
        assert df['weight'].dtype.kind == 'f', "weight must be float"
        assert df['is_abstract'].dtype == bool, "is_abstract must be bool"

    def test_returns_dataframe(self, jpm_10k_2024):
        df = jpm_10k_2024.calculation_linkbase()
        assert isinstance(df, pd.DataFrame)


@pytest.mark.fast
class TestJPMExtensions:
    """Ground-truth assertions against JPM FY2023 10-K."""

    def test_extension_count_meets_threshold(self, jpm_10k_2024):
        """JPM is a bank with heavy extension usage — expect at least 100 jpm: concepts.
        Per 0ywfe's cross-filer validation, JPM has 123 extensions in this filing class.
        """
        df = jpm_10k_2024.calculation_linkbase()
        jpm_extensions = df[df['concept_taxonomy'] == 'jpm']
        assert len(jpm_extensions) >= 100, (
            f"Expected ≥100 jpm: extensions, got {len(jpm_extensions)}. "
            "If this dropped, the taxonomy split or filtering regressed."
        )

    def test_asset_management_fees_rolls_into_noninterest_income(self, jpm_10k_2024):
        """jpm:AssetManagementFees → us-gaap:NoninterestIncome, weight=+1.0.

        This is the marquee bank-disaggregation example from the design doc and
        amcamc92's Layer 2 problem. If this regresses, the entire feature is broken.
        """
        df = jpm_10k_2024.calculation_linkbase()
        arc = df[(df['concept'] == 'AssetManagementFees') & (df['concept_taxonomy'] == 'jpm')]
        assert len(arc) >= 1, "jpm:AssetManagementFees arc missing"

        row = arc.iloc[0]
        assert row['parent_concept'] == 'NoninterestIncome'
        assert row['parent_taxonomy'] == 'us-gaap'
        assert row['weight'] == 1.0

    def test_signed_weight_preserved_for_extensions(self, jpm_10k_2024):
        """Extension arcs with weight=-1.0 must round-trip with the sign intact.

        Regression guard: flattening this to +1.0 would corrupt cash-flow rollups
        like jpm:IncreaseDecreaseInAccruedInterestsAndAccountsReceivable, which
        subtracts from operating cash flow.
        """
        df = jpm_10k_2024.calculation_linkbase()
        negative_extensions = df[(df['weight'] == -1.0) & (df['concept_taxonomy'] == 'jpm')]
        assert len(negative_extensions) >= 1, (
            "JPM has at least one jpm: extension with weight=-1.0; none found"
        )

    def test_signed_weight_preserved_for_standard_concepts(self, jpm_10k_2024):
        """us-gaap arcs with weight=-1.0 must also preserve the sign.

        Example: us-gaap:InterestExpense subtracts from InterestIncomeExpenseNet.
        """
        df = jpm_10k_2024.calculation_linkbase()
        interest_expense = df[
            (df['concept'] == 'InterestExpense') &
            (df['concept_taxonomy'] == 'us-gaap')
        ]
        assert len(interest_expense) >= 1
        # At least one row should be the negative-weight rollup
        assert (interest_expense['weight'] == -1.0).any(), (
            "us-gaap:InterestExpense should appear with weight=-1.0 somewhere"
        )

    def test_role_uri_is_full_uri_not_fragment(self, jpm_10k_2024):
        """role_uri must be the full extended-link role URI, not just the fragment."""
        df = jpm_10k_2024.calculation_linkbase()
        sample_roles = df['role_uri'].unique()
        assert len(sample_roles) > 1
        for role in sample_roles[:5]:
            assert role.startswith('http'), f"role_uri should be full URI, got {role!r}"


@pytest.mark.fast
class TestAAPLTaxonomySplit:
    """Apple is a tech filer with a small extension footprint — good control case."""

    def test_taxonomy_split_distinguishes_aapl_from_us_gaap(self, aapl_10k_2023):
        df = aapl_10k_2023.calculation_linkbase()
        taxonomies = set(df['concept_taxonomy'].unique())
        assert 'us-gaap' in taxonomies
        assert 'aapl' in taxonomies

    def test_us_gaap_prefix_not_split_on_hyphen(self, aapl_10k_2023):
        """'us-gaap' contains a hyphen; split must use the first underscore.

        Regression guard: a naive split on `-` or last `_` would yield 'us' or 'gaap'.
        """
        df = aapl_10k_2023.calculation_linkbase()
        us_gaap_rows = df[df['concept_taxonomy'] == 'us-gaap']
        assert len(us_gaap_rows) > 50, "Expected many us-gaap arcs in AAPL 10-K"

        # Verify no rows have a mangled taxonomy
        bad = df[df['concept_taxonomy'].isin(['us', 'gaap'])]
        assert len(bad) == 0, "Found mangled us-gaap split"


@pytest.mark.fast
class TestAbstractFilter:
    """include_abstract behavior — additive, never reduces rows."""

    def test_include_abstract_is_superset(self, jpm_10k_2024):
        """include_abstract=True must return ≥ the default count."""
        default = jpm_10k_2024.calculation_linkbase()
        with_abstract = jpm_10k_2024.calculation_linkbase(include_abstract=True)
        assert len(with_abstract) >= len(default)

    def test_default_excludes_abstract_rows(self, jpm_10k_2024):
        """Default filter strips is_abstract=True rows."""
        df = jpm_10k_2024.calculation_linkbase()
        assert not df['is_abstract'].any(), (
            "Default mode must not include abstract concepts"
        )


@pytest.mark.fast
class TestSilenceCheck:
    """Bad/empty input must produce empty DataFrame with correct columns, not None."""

    def test_empty_calculation_trees_returns_empty_df(self):
        """An XBRL with no calculation trees returns an empty DataFrame, not None."""
        xbrl = XBRL()
        # Don't load any linkbases — calculation_trees stays empty
        df = xbrl.calculation_linkbase()
        assert isinstance(df, pd.DataFrame), "Must return DataFrame, not None"
        assert len(df) == 0
        assert list(df.columns) == EXPECTED_COLUMNS, (
            "Empty DataFrame must still have the documented schema"
        )

    def test_root_nodes_excluded(self, jpm_10k_2024):
        """Root nodes have no parent and must not appear as rows.

        Every row must have a non-null parent_concept.
        """
        df = jpm_10k_2024.calculation_linkbase()
        assert df['parent_concept'].notna().all(), (
            "Root nodes leaked into the DataFrame"
        )
        # parent_concept should never be an empty string either
        assert (df['parent_concept'] != '').all()


@pytest.mark.fast
class TestSplitElementId:
    """Direct tests of the split_element_id helper for taxonomy attribution."""

    def test_us_gaap_split(self):
        from edgar.xbrl.core import split_element_id
        assert split_element_id('us-gaap_Revenues') == ('us-gaap', 'Revenues')

    def test_extension_split(self):
        from edgar.xbrl.core import split_element_id
        assert split_element_id('tsla_RestructuringAndOtherExpenses') == (
            'tsla', 'RestructuringAndOtherExpenses'
        )

    def test_no_underscore(self):
        """Pathological input: element ID with no underscore."""
        from edgar.xbrl.core import split_element_id
        assert split_element_id('NoUnderscore') == ('', 'NoUnderscore')

    def test_empty_string(self):
        from edgar.xbrl.core import split_element_id
        assert split_element_id('') == ('', '')

    def test_only_splits_on_first_underscore(self):
        """If the local name contains underscores, they must be preserved."""
        from edgar.xbrl.core import split_element_id
        assert split_element_id('us-gaap_Foo_Bar_Baz') == ('us-gaap', 'Foo_Bar_Baz')
