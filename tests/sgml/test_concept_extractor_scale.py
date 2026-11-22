"""
Display scale and currency values as the SEC R*.htm pages state them (GH #807).

Every title cell and display value below is copied from the named filing's
page. The pages are built inline (title cell plus one data row), so no
fixtures are needed.

GitHub Issue: https://github.com/dgunning/edgartools/issues/807
"""
from unittest.mock import MagicMock

import pytest

from edgar.sgml.concept_extractor import extract_concepts_from_report, parse_numeric
from edgar.sgml.filing_summary import Report
from edgar.xbrl.viewer import ViewerReport


def _page(title_cell: str, value: str = '$ 1') -> str:
    """An R*.htm report table with the given title cell content and one data row."""
    return ('<table class="report">'
            '<tr><th class="tl" colspan="1" rowspan="1"><div style="width: 200px;"><strong>'
            f'{title_cell}</strong></div></th><th class="th"><div>Dec. 31, 2024</div></th></tr>'
            '<tr class="re"><td class="pl"><a class="a" onclick="top.Show.showAR( this, '
            "'defref_us-gaap_Revenues', window );\">Revenues</a></td>"
            f'<td class="nump">{value}<span></span></td></tr>'
            '</table>')


def _report(cr, viewer):
    report = Report(instance=None, is_default=False, has_embedded_reports=False,
                    html_file_name="R2.htm", long_name='', report_type=None, role='r',
                    parent_role=None, short_name='Ops', menu_category='Statements',
                    position='2', reports=None)
    return ViewerReport(report, None, cr, viewer=viewer)


class TestTitleCellScale:

    def test_dollars_in_millions(self):
        # Spirit AeroSystems 10-K 0001628280-20-002543, R2.htm; net revenues "$ 1,959.3".
        cr = extract_concepts_from_report(_page(
            'Consolidated Statements of Operations - USD ($)<br> $ in Millions', '$ 1,959.3'))
        assert (cr.header_found, cr.header_unit, cr.unit_scales) == (True, 'USD ($)', {'$': 1_000_000})
        assert (cr.currency_scaling, cr.shares_scaling) == (1_000_000, 1)
        assert cr.rows[0].numeric_values == {'Dec. 31, 2024': 1959.3}

    def test_dollars_in_thousands_shares_in_millions(self):
        # Amgen 10-K 0000318154-26-000010, R3.htm; total revenues "$ 36,751,000".
        cr = extract_concepts_from_report(_page(
            'CONSOLIDATED STATEMENTS OF INCOME - USD ($)<br> $ in Thousands, shares in Millions',
            '$ 36,751,000'))
        assert cr.unit_scales == {'$': 1_000, 'shares': 1_000_000}
        assert (cr.currency_scaling, cr.shares_scaling) == (1_000, 1_000_000)

    def test_only_a_shares_statement_leaves_amounts_in_whole_units(self):
        # Airbnb 10-K 0001559720-25-000010, R5.htm: revenue "$ 11,102,000,000" in whole dollars.
        cr = extract_concepts_from_report(_page(
            'Consolidated Statements of Operations - USD ($)<br> shares in Millions', '$ 11,102,000,000'))
        assert cr.unit_scales == {'shares': 1_000_000}
        assert (cr.currency_scaling, cr.shares_scaling) == (1, 1_000_000)
        assert cr.rows[0].numeric_values == {'Dec. 31, 2024': 11_102_000_000.0}

    def test_scale_of_a_symbol_other_than_dollar(self):
        # On Holding 20-F 0001858985-26-000008, R3.htm, in Swiss francs: net sales "SFr 3,014.0".
        # The old "$ in" match left this page at 1.
        cr = extract_concepts_from_report(_page(
            'Consolidated statements of income - CHF (SFr)<br> SFr in Millions'))
        assert (cr.header_unit, cr.unit_scales, cr.currency_scaling) == ('CHF (SFr)', {'SFr': 1_000_000}, 1_000_000)

    def test_two_currencies_at_one_scale(self):
        # Azure Power 20-F 0001174947-24-000443, R2.htm: rupee and dollar columns, cash "₨ 12,724".
        cr = extract_concepts_from_report(_page(
            'Consolidated Balance Sheets<br> &#8360; in Millions, $ in Millions', '&#8360; 12,724'))
        assert (cr.header_unit, cr.unit_scales) == (None, {'₨': 1_000_000, '$': 1_000_000})
        assert cr.currency_scaling == 1_000_000
        assert cr.rows[0].numeric_values == {'Dec. 31, 2024': 12_724.0}

    def test_declared_scale_wins_over_decimals_inference(self):
        cr = extract_concepts_from_report(_page(
            'Consolidated Statements of Operations - USD ($)<br> $ in Millions', '$ 1,959.3'))
        viewer = MagicMock()
        viewer._resolve_currency_scaling.return_value = 100_000  # Spirit's decimals=-5
        assert _report(cr, viewer).currency_scaling == 1_000_000
        viewer._resolve_currency_scaling.assert_not_called()

    def test_whole_unit_page_is_not_replaced_by_decimals_inference(self):
        # IREN 10-K 0001878848-25-000063, R5.htm: "USD ($)" and no scale statement;
        # total revenue "$ 501,023,000" in whole dollars, filed at decimals=-3.
        cr = extract_concepts_from_report(_page(
            'Consolidated Statements of Operations - USD ($)', '$ 501,023,000'))
        viewer = MagicMock()
        viewer._resolve_currency_scaling.return_value = 1_000
        assert (cr.header_found, _report(cr, viewer).currency_scaling) == (True, 1)
        viewer._resolve_currency_scaling.assert_not_called()

    def test_report_without_a_title_cell_falls_back_to_decimals(self):
        cr = extract_concepts_from_report(
            '<table class="report"><tr><th class="th"><div>Dec. 31, 2024</div></th></tr></table>')
        viewer = MagicMock()
        viewer._resolve_currency_scaling.return_value = 1_000
        assert (cr.header_found, _report(cr, viewer).currency_scaling) == (False, 1_000)


class TestDisplayValuesWithCurrency:

    @pytest.mark.parametrize('display, expected', [
        ('$ 1,959.3', 1959.3),            # Spirit 0001628280-20-002543 R2
        ('₨ 12,724', 12724.0),            # Azure Power 0001174947-24-000443 R2
        ('R$ 88,242.5', 88242.5),         # Ambev 20-F 0001292814-26-000640 R2
        ('(279)', -279.0),
    ])
    def test_values_as_pages_print_them(self, display, expected):
        assert parse_numeric(display) == expected

    @pytest.mark.parametrize('display, expected', [
        # The renderer prints a unit's id when the registry gives it no symbol; no
        # page read for this PR shows one, so these are constructed.
        ('CHF 10', 10.0), ('(CHF 1,234)', -1234.0), ('US$ 5', 5.0),
        # Letters that are not a currency prefix are not stripped.
        ('ABC 12', None), ('No 5', None),
    ])
    def test_currency_prefixes_in_letters(self, display, expected):
        assert parse_numeric(display) == expected
