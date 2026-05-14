"""
Verification tests for FundFeeNotice (24F-2NT) data object.

Ground truth filings:
  - Advisors' Inner Circle Fund (0002048251-26-002390) — single-block, 2 series,
    fund-level totals ($418,915,624 aggregate sales)
  - BNY Mellon Research Growth Fund (0000030162-26-000001) — multi-block,
    5 share classes, fund total $283,042,576 in aggregate sales

The two cached XML fixtures drive deterministic unit tests so the parser path
is covered without network access; pinned-accession network tests verify the
end-to-end ``filing.obj()`` flow.
"""
from pathlib import Path

import pytest
from lxml import etree

from edgar.funds.twentyfourf import FundClassFee, FundFeeNotice, SeriesInfo
from edgar.xmlfiling import _element_to_dict, _strip_namespaces


FIXTURES = Path(__file__).parent / "fixtures" / "funds" / "twentyfourf"
SINGLE_BLOCK_XML = FIXTURES / "single_block_advisors_inner_circle.xml"
MULTI_BLOCK_XML = FIXTURES / "multi_block_bny_mellon_research_growth.xml"


class _StubFiling:
    """Minimal Filing stub for offline construction of FundFeeNotice."""
    def __init__(self, form='24F-2NT', company='Stub Fund', accession='0000000000-00-000000'):
        self.form = form
        self.company = company
        self.filing_date = '2026-01-01'
        self.accession_no = accession


def _load_notice(path: Path, *, company: str = 'Stub Fund') -> FundFeeNotice:
    """Build a FundFeeNotice from a cached XML fixture."""
    root = etree.fromstring(path.read_bytes())
    _strip_namespaces(root)
    form_data_el = root.find('formData')
    header_data_el = root.find('headerData')
    form_data = _element_to_dict(form_data_el) if form_data_el is not None else {}
    header_data = _element_to_dict(header_data_el) if header_data_el is not None else {}
    return FundFeeNotice(
        filing=_StubFiling(company=company),
        form_data=form_data,
        header_data=header_data,
    )


# ---------------------------------------------------------------------------
# Unit tests (no network)
# ---------------------------------------------------------------------------

class TestObjInfo:

    def test_24f2nt_registered(self):
        from edgar import get_obj_info
        has_obj, class_name, desc = get_obj_info("24F-2NT")
        assert has_obj is True
        assert class_name == 'FundFeeNotice'

    def test_is_xmlfiling_subclass(self):
        from edgar.xmlfiling import XmlFiling
        assert issubclass(FundFeeNotice, XmlFiling)


class TestSeriesInfo:

    def test_series_model(self):
        s = SeriesInfo(series_name="Growth Fund", series_id="S000012345")
        assert s.series_name == "Growth Fund"
        assert s.series_id == "S000012345"
        assert s.include_all_classes is False


class TestParseFloatAccounting:
    """The XML uses accounting-parens for negative redemption credits."""

    def test_parens_become_negative(self):
        from edgar.funds.twentyfourf import _parse_float
        assert _parse_float("(695309905.00)") == -695309905.0

    def test_plain_number(self):
        from edgar.funds.twentyfourf import _parse_float
        assert _parse_float("1,234.5") == 1234.5

    def test_none_passthrough(self):
        from edgar.funds.twentyfourf import _parse_float
        assert _parse_float(None) is None
        assert _parse_float("not-a-number") is None


class TestSingleBlockFixture:
    """Fund-level filing pattern (~98% of 24F-2NT filings)."""

    @pytest.fixture
    def notice(self):
        return _load_notice(SINGLE_BLOCK_XML, company="ADVISORS' INNER CIRCLE FUND")

    def test_not_per_class(self, notice):
        assert notice.is_per_class is False
        assert len(notice._filing_info_blocks) == 1
        assert notice.class_fees == []

    def test_metadata(self, notice):
        assert notice.fund_name == "ADVISORS' INNER CIRCLE FUND"
        assert notice.fiscal_year_end == '12/31/2025'
        assert notice.investment_company_act_file_number == '811-06400'

    def test_financials_match_ground_truth(self, notice):
        assert notice.aggregate_sales == 418915624.0
        assert notice.redemptions_current_year == 309040895.54
        assert notice.net_sales == 109874728.46
        assert notice.registration_fee == 15173.7
        assert notice.total_due == 15173.7
        assert notice.interest_due == 0.0

    def test_series(self, notice):
        assert len(notice.series) == 2
        assert notice.series[0].series_name == 'Hamlin High Dividend Equity Fund'
        assert notice.series[0].series_id == 'S000036634'
        assert notice.series[0].include_all_classes is True
        assert notice.series[1].series_name == 'Sarofim Equity Fund'

    def test_rich_renders(self, notice):
        assert notice.__rich__() is not None


class TestMultiBlockFixture:
    """Per-class filing pattern (~2% of 24F-2NT filings).

    Regression for edgartools-8ohs: prior to the multi-block refactor every
    typed property crashed with AttributeError on this filing because
    xmltodict-style parsing returns repeated XML elements as a list.
    """

    @pytest.fixture
    def notice(self):
        return _load_notice(MULTI_BLOCK_XML, company='BNY MELLON RESEARCH GROWTH FUND, INC.')

    def test_per_class(self, notice):
        assert notice.is_per_class is True
        assert len(notice._filing_info_blocks) == 5

    def test_metadata_from_first_block(self, notice):
        # item1/3/4 are identical across blocks; first-block read suffices.
        assert notice.fund_name == "BNY MELLON RESEARCH GROWTH FUND, INC."
        assert notice.fiscal_year_end == '02/28/2026'
        assert notice.investment_company_act_file_number == '811-01899'

    def test_aggregate_sales_summed_across_classes(self, notice):
        # 92341147 + 117104215 + 870777 + 61461470 + 11264967
        assert notice.aggregate_sales == 283042576.0

    def test_redemptions_summed_across_classes(self, notice):
        # 67705392 + 90422241 + 1146729 + 67229352 + 36419666
        assert notice.redemptions_current_year == 262923380.0

    def test_zero_fields_remain_zero(self, notice):
        # Every class reports zero net sales / registration fee / total due.
        assert notice.net_sales == 0.0
        assert notice.registration_fee == 0.0
        assert notice.total_due == 0.0
        assert notice.interest_due == 0.0

    def test_series_deduped_across_blocks(self, notice):
        # All 5 classes point at the same parent series S000000071.
        assert len(notice.series) == 1
        assert notice.series[0].series_id == 'S000000071'

    def test_class_fees_breakdown(self, notice):
        fees = notice.class_fees
        assert len(fees) == 5
        assert [cf.series_or_class_id for cf in fees] == [
            'C000000108', 'C000069523', 'C000069524', 'C000069525', 'C000127666',
        ]
        # Class A is the second block in the BNY Mellon filing.
        class_a = fees[1]
        assert isinstance(class_a, FundClassFee)
        assert class_a.class_name == 'Class A'
        assert class_a.series_id == 'S000000071'
        assert class_a.aggregate_sales == 117104215.0
        assert class_a.net_sales == 0.0

    def test_fund_total_equals_sum_of_class_fees(self, notice):
        # Library invariant: fund-level aggregate equals the per-class sum.
        per_class_sum = sum(cf.aggregate_sales for cf in notice.class_fees)
        assert notice.aggregate_sales == per_class_sum

    def test_accounting_parens_parsed_as_negative(self, notice):
        # redemptionCreditsAvailableForUseInFutureYears is reported as (NNN)
        # for every class. Sum of negatives must be negative.
        assert notice.unused_redemption_credits is not None
        assert notice.unused_redemption_credits < 0

    def test_rich_renders_with_per_class_table(self, notice):
        assert notice.__rich__() is not None

    def test_to_context_includes_class_breakdown(self, notice):
        ctx = notice.to_context()
        assert 'Per-Class Breakdown: 5 share classes' in ctx
        assert 'C000069523' in ctx


# ---------------------------------------------------------------------------
# Network tests — real 24F-2NT filings
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestFundFeeNotice:

    def test_advisors_inner_circle(self):
        """Single-block ground truth: Advisors' Inner Circle Fund, 2 series."""
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()

        assert isinstance(notice, FundFeeNotice)
        assert notice.form in ('24F-2NT', '24F-2NT/A')
        assert notice.fund_name == "ADVISORS' INNER CIRCLE FUND"
        assert notice.fiscal_year_end == '12/31/2025'
        assert notice.investment_company_act_file_number == '811-06400'
        assert notice.is_per_class is False
        assert notice.class_fees == []

        # Financial data — ground truth values
        assert notice.aggregate_sales == 418915624.0
        assert notice.net_sales == 109874728.46
        assert notice.registration_fee == 15173.7
        assert notice.total_due == 15173.7

        # Series
        assert len(notice.series) == 2
        assert notice.series[0].series_name == 'Hamlin High Dividend Equity Fund'
        assert notice.series[0].series_id == 'S000036634'

    def test_bny_mellon_multi_block(self):
        """Per-class canary: BNY Mellon Research Growth Fund, 5 share classes.

        Regression for edgartools-8ohs — previously raised
        ``AttributeError: 'list' object has no attribute 'get'``.
        """
        from edgar import find
        filing = find('0000030162-26-000001')
        notice = filing.obj()

        assert isinstance(notice, FundFeeNotice)
        assert notice.is_per_class is True
        assert len(notice.class_fees) == 5
        assert notice.fund_name == "BNY MELLON RESEARCH GROWTH FUND, INC."

        # Fund total equals the sum of per-class aggregate sales.
        assert notice.aggregate_sales == 283042576.0
        assert notice.aggregate_sales == sum(cf.aggregate_sales for cf in notice.class_fees)

        # Class A is the second annualFilingInfo block.
        assert notice.class_fees[1].series_or_class_id == 'C000069523'
        assert notice.class_fees[1].class_name == 'Class A'
        assert notice.class_fees[1].series_id == 'S000000071'

        # Every class points at the same parent series.
        assert len(notice.series) == 1
        assert notice.series[0].series_id == 'S000000071'

    def test_rich_display(self):
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()
        assert notice.__rich__() is not None

    def test_to_context(self):
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()

        ctx = notice.to_context()
        assert '24F-2NT' in ctx
        assert 'ADVISORS' in ctx
        assert '$418,915,624.00' in ctx

    def test_to_html(self):
        """XSLT-rendered HTML from SEC."""
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()

        html = notice.to_html()
        assert html is not None
        assert '<html' in html[:500].lower()

    def test_str(self):
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()
        s = str(notice)
        assert 'FundFeeNotice' in s
        assert '418915624' in s
