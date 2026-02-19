"""
Tests for RenderedStatement.to_dict() / from_dict() serialization.
"""
import json

import pytest

from edgar.xbrl.rendering import render_statement, RenderedStatement


def _make_balance_sheet_data():
    """Create synthetic balance sheet data (instant periods)."""
    return [
        {
            'label': 'Assets',
            'level': 0,
            'is_abstract': True,
            'is_total': False,
            'concept': 'us-gaap_AssetsAbstract',
            'has_values': False,
            'values': {},
            'decimals': {},
        },
        {
            'label': 'Total Assets',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'concept': 'us-gaap_Assets',
            'has_values': True,
            'values': {
                'instant_2023-12-31': 1000000000,
                'instant_2022-12-31': 900000000,
            },
            'decimals': {
                'instant_2023-12-31': -6,
                'instant_2022-12-31': -6,
            },
        },
        {
            'label': 'Common Stock Shares Outstanding',
            'level': 1,
            'is_abstract': False,
            'is_total': False,
            'concept': 'us-gaap_CommonStockSharesOutstanding',
            'has_values': True,
            'values': {
                'instant_2023-12-31': 5123456000,
                'instant_2022-12-31': 5000000000,
            },
            'decimals': {
                'instant_2023-12-31': -3,
                'instant_2022-12-31': -3,
            },
        },
    ]


def _make_income_statement_data():
    """Create synthetic income statement data (duration periods)."""
    return [
        {
            'label': 'Revenue',
            'level': 0,
            'is_abstract': False,
            'is_total': False,
            'concept': 'us-gaap_Revenue',
            'has_values': True,
            'values': {
                'duration_2023-01-01_2023-12-31': 50000000000,
                'duration_2022-01-01_2022-12-31': 45000000000,
            },
            'decimals': {
                'duration_2023-01-01_2023-12-31': -6,
                'duration_2022-01-01_2022-12-31': -6,
            },
        },
        {
            'label': 'Net Income',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'concept': 'us-gaap_NetIncomeLoss',
            'has_values': True,
            'values': {
                'duration_2023-01-01_2023-12-31': 10000000000,
                'duration_2022-01-01_2022-12-31': 8000000000,
            },
            'decimals': {
                'duration_2023-01-01_2023-12-31': -6,
                'duration_2022-01-01_2022-12-31': -6,
            },
        },
    ]


def _make_dimension_data():
    """Create data with dimension rows."""
    return [
        {
            'label': 'Revenue',
            'level': 0,
            'is_abstract': False,
            'is_total': False,
            'is_dimension': False,
            'concept': 'us-gaap_Revenue',
            'has_values': True,
            'values': {'instant_2023-12-31': 50000000000},
            'decimals': {'instant_2023-12-31': -6},
        },
        {
            'label': 'Products',
            'level': 1,
            'is_abstract': False,
            'is_total': False,
            'is_dimension': True,
            'concept': 'us-gaap_ProductRevenue',
            'has_values': True,
            'values': {'instant_2023-12-31': 30000000000},
            'decimals': {'instant_2023-12-31': -6},
        },
    ]


def _render_balance_sheet():
    periods = [
        ('instant_2023-12-31', 'Dec 31, 2023'),
        ('instant_2022-12-31', 'Dec 31, 2022'),
    ]
    return render_statement(
        _make_balance_sheet_data(), periods, 'Balance Sheet', 'BalanceSheet'
    )


def _render_income_statement():
    periods = [
        ('duration_2023-01-01_2023-12-31', 'Dec 31, 2023'),
        ('duration_2022-01-01_2022-12-31', 'Dec 31, 2022'),
    ]
    return render_statement(
        _make_income_statement_data(), periods, 'Income Statement', 'IncomeStatement'
    )


class TestToDict:
    """Tests for RenderedStatement.to_dict()."""

    def test_json_serializable(self):
        """to_dict() output must be JSON-serializable."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        # Should not raise
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_comparison_data_excluded(self):
        """comparison_data should not appear in serialized metadata."""
        rendered = _render_income_statement()
        d = rendered.to_dict()
        assert 'comparison_data' not in d['metadata']

    def test_top_level_fields(self):
        """Top-level fields are preserved."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        assert d['title'] == 'Balance Sheet'
        assert d['statement_type'] == 'BalanceSheet'
        assert d['units_note'] is not None

    def test_header_columns(self):
        """Header columns and period_keys are serialized."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        assert len(d['header']['columns']) == 2
        assert len(d['header']['period_keys']) == 2

    def test_cells_have_formatted_value(self):
        """Each cell dict should contain both value and formatted_value."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        for row in d['rows']:
            for cell in row['cells']:
                assert 'value' in cell
                assert 'formatted_value' in cell

    def test_row_attributes(self):
        """Row attributes like is_abstract, is_dimension, level are serialized."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        # First row is abstract (Assets header) — but render_statement may filter it
        # Find a non-abstract row
        non_abstract = [r for r in d['rows'] if not r['is_abstract']]
        assert len(non_abstract) > 0
        row = non_abstract[0]
        assert 'label' in row
        assert 'level' in row
        assert isinstance(row['is_abstract'], bool)
        assert isinstance(row['is_dimension'], bool)


class TestFromDict:
    """Tests for RenderedStatement.from_dict()."""

    def test_round_trip_title(self):
        """Title survives round-trip."""
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert restored.title == rendered.title

    def test_round_trip_statement_type(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert restored.statement_type == rendered.statement_type

    def test_round_trip_header_columns(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert restored.header.columns == rendered.header.columns

    def test_round_trip_period_keys(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert restored.header.period_keys == rendered.header.period_keys

    def test_round_trip_row_count(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert len(restored.rows) == len(rendered.rows)

    def test_round_trip_cell_values(self):
        """Cell raw values survive round-trip."""
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            for orig_cell, rest_cell in zip(orig_row.cells, rest_row.cells):
                assert rest_cell.value == orig_cell.value

    def test_round_trip_formatted_values(self):
        """Formatted values survive round-trip via passthrough formatter."""
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            for orig_cell, rest_cell in zip(orig_row.cells, rest_row.cells):
                assert rest_cell.get_formatted_value() == orig_cell.get_formatted_value()

    def test_round_trip_row_labels(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            assert rest_row.label == orig_row.label

    def test_round_trip_row_attributes(self):
        """Row attributes (level, is_abstract, is_dimension, etc.) survive."""
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            assert rest_row.level == orig_row.level
            assert rest_row.is_abstract == orig_row.is_abstract
            assert rest_row.is_dimension == orig_row.is_dimension
            assert rest_row.is_breakdown == orig_row.is_breakdown
            assert rest_row.has_dimension_children == orig_row.has_dimension_children

    def test_round_trip_periods(self):
        """PeriodData objects survive round-trip."""
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert len(restored.periods) == len(rendered.periods)
        for orig_p, rest_p in zip(rendered.periods, restored.periods):
            assert rest_p.key == orig_p.key
            assert rest_p.label == orig_p.label
            assert rest_p.end_date == orig_p.end_date

    def test_round_trip_units_note(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert restored.units_note == rendered.units_note

    def test_round_trip_fiscal_period_indicator(self):
        rendered = _render_balance_sheet()
        restored = RenderedStatement.from_dict(rendered.to_dict())
        assert restored.fiscal_period_indicator == rendered.fiscal_period_indicator


class TestMultipleStatementTypes:
    """Test serialization with different statement types."""

    def test_income_statement_round_trip(self):
        """Income statement with duration periods round-trips correctly."""
        rendered = _render_income_statement()
        d = rendered.to_dict()
        serialized = json.dumps(d)
        restored = RenderedStatement.from_dict(json.loads(serialized))
        assert restored.title == 'Income Statement'
        assert restored.statement_type == 'IncomeStatement'
        assert len(restored.rows) == len(rendered.rows)

    def test_balance_sheet_round_trip(self):
        """Balance sheet with instant periods round-trips correctly."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        serialized = json.dumps(d)
        restored = RenderedStatement.from_dict(json.loads(serialized))
        assert restored.title == 'Balance Sheet'
        assert restored.statement_type == 'BalanceSheet'


class TestEdgeCases:
    """Test edge cases in serialization."""

    def test_abstract_rows(self):
        """Abstract rows (no cell values) serialize correctly."""
        rendered = _render_balance_sheet()
        d = rendered.to_dict()
        abstract_rows = [r for r in d['rows'] if r['is_abstract']]
        # Abstract rows may or may not be present depending on filtering
        # but if present, they should serialize fine
        for row in abstract_rows:
            assert row['label'] != ''

    def test_dimension_rows(self):
        """Dimension rows serialize with is_dimension flag."""
        periods = [('instant_2023-12-31', 'Dec 31, 2023')]
        rendered = render_statement(
            _make_dimension_data(), periods, 'Test', 'BalanceSheet',
            include_dimensions=True
        )
        d = rendered.to_dict()
        dim_rows = [r for r in d['rows'] if r['is_dimension']]
        assert len(dim_rows) > 0
        # Round-trip preserves dimension flag
        restored = RenderedStatement.from_dict(d)
        restored_dim = [r for r in restored.rows if r.is_dimension]
        assert len(restored_dim) == len(dim_rows)

    def test_empty_cells(self):
        """Empty cell values serialize as empty strings."""
        data = [
            {
                'label': 'Sparse Item',
                'level': 0,
                'is_abstract': False,
                'is_total': False,
                'concept': 'us-gaap_SparseItem',
                'has_values': True,
                'values': {'instant_2023-12-31': 100, 'instant_2022-12-31': ''},
                'decimals': {},
            },
        ]
        periods = [
            ('instant_2023-12-31', 'Dec 31, 2023'),
            ('instant_2022-12-31', 'Dec 31, 2022'),
        ]
        rendered = render_statement(data, periods, 'Test', 'BalanceSheet')
        d = rendered.to_dict()
        restored = RenderedStatement.from_dict(d)
        # Both cells should round-trip their formatted values
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            for orig_cell, rest_cell in zip(orig_row.cells, rest_row.cells):
                assert rest_cell.get_formatted_value() == orig_cell.get_formatted_value()

    def test_from_dict_missing_optional_fields(self):
        """from_dict handles missing optional fields gracefully."""
        minimal = {
            'title': 'Minimal',
            'header': {'columns': [], 'period_keys': []},
            'rows': [],
        }
        restored = RenderedStatement.from_dict(minimal)
        assert restored.title == 'Minimal'
        assert restored.statement_type == ''
        assert restored.fiscal_period_indicator is None
        assert restored.units_note is None
        assert len(restored.rows) == 0
        assert len(restored.header.periods) == 0

    def test_full_json_round_trip(self):
        """Full serialize → JSON string → deserialize → verify cycle."""
        rendered = _render_income_statement()
        json_str = json.dumps(rendered.to_dict())
        restored = RenderedStatement.from_dict(json.loads(json_str))
        # Verify formatted values match after full JSON round-trip
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            for orig_cell, rest_cell in zip(orig_row.cells, rest_row.cells):
                assert rest_cell.get_formatted_value() == orig_cell.get_formatted_value()


class TestConsolidatedRoundTrip:
    """Single consolidated test that verifies every field survives a full JSON round-trip."""

    @pytest.mark.parametrize("render_fn,expected_title,expected_type", [
        (_render_balance_sheet, 'Balance Sheet', 'BalanceSheet'),
        (_render_income_statement, 'Income Statement', 'IncomeStatement'),
    ])
    def test_complete_round_trip(self, render_fn, expected_title, expected_type):
        """Every field must survive render → to_dict → JSON → from_dict."""
        rendered = render_fn()
        json_str = json.dumps(rendered.to_dict())
        restored = RenderedStatement.from_dict(json.loads(json_str))

        # --- Top-level fields ---
        assert restored.title == expected_title
        assert restored.statement_type == expected_type
        assert restored.units_note == rendered.units_note
        assert restored.fiscal_period_indicator == rendered.fiscal_period_indicator
        assert restored.metadata == rendered.to_dict()['metadata']

        # --- Header ---
        assert restored.header.columns == rendered.header.columns
        assert restored.header.period_keys == rendered.header.period_keys
        assert len(restored.header.periods) == len(rendered.header.periods)
        for orig_p, rest_p in zip(rendered.header.periods, restored.header.periods):
            assert rest_p.key == orig_p.key
            assert rest_p.label == orig_p.label
            assert rest_p.end_date == orig_p.end_date
            assert rest_p.start_date == orig_p.start_date
            assert rest_p.is_duration == orig_p.is_duration
            assert rest_p.quarter == orig_p.quarter

        # --- Rows ---
        assert len(restored.rows) == len(rendered.rows)
        for orig_row, rest_row in zip(rendered.rows, restored.rows):
            assert rest_row.label == orig_row.label
            assert rest_row.level == orig_row.level
            assert rest_row.is_abstract == orig_row.is_abstract
            assert rest_row.is_dimension == orig_row.is_dimension
            assert rest_row.is_breakdown == orig_row.is_breakdown
            assert rest_row.has_dimension_children == orig_row.has_dimension_children

            # --- Cells ---
            assert len(rest_row.cells) == len(orig_row.cells)
            for orig_cell, rest_cell in zip(orig_row.cells, rest_row.cells):
                assert rest_cell.value == orig_cell.value
                assert rest_cell.get_formatted_value() == orig_cell.get_formatted_value()
                assert rest_cell.style == orig_cell.style
                # Compare via JSON normalization (tuples become lists in JSON)
                assert json.loads(json.dumps(rest_cell.comparison)) == json.loads(json.dumps(orig_cell.comparison))
