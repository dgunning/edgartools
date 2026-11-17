"""
Verification of edgar.abs.AssetData, the streaming ABS-EE EX-102 reader.

Fixtures (tests/fixtures/absee/, provenance in its README) are SEC files:

- World Omni Auto Receivables Trust 2022-C, ABS-EE 0001104659-26-111517 (autoloan),
  first 25 assets, verbatim
- BMW Vehicle Lease Trust 2023-2, ABS-EE 0000929638-25-004537 (autolease),
  first 25 assets, verbatim
- BANK 2025-BNK49, ABS-EE 0001888524-26-019640 (cmbs), the whole EX-102
- GNMAG Asset Backed Securitizations Trust 2020-1, ABS-EE/A 0001213900-21-000188
  (debtsecurities), the whole submission .txt

Every expected value below was read by hand from those files.
"""
import gzip
import io
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from edgar.abs import AssetData, AssetDataInfo
from edgar.abs import asset_data as asset_data_module
from edgar.abs.absee_schemas import CONTRACT_VERSION, SCHEMAS
from edgar.exceptions import DataObjectError, ParsingError

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "absee"
WOART = FIXTURES / "woart_2022c_0001104659-26-111517_first25.xml"
BMW = FIXTURES / "bmwlt_2023-2_0000929638-25-004537_first25.xml"
BANK49 = FIXTURES / "bank_2025-bnk49_0001888524-26-019640_ex102.xml"
GNMAG = FIXTURES / "gnmag_2020-1_0001213900-21-000188.txt"

AUTOLOAN_NS = SCHEMAS['autoloan']['namespace']


def _autoloan_xml(*asset_bodies: str) -> bytes:
    assets = "".join(f"<assets>{body}</assets>" for body in asset_bodies)
    return f'<?xml version="1.0"?><assetData xmlns="{AUTOLOAN_NS}">{assets}</assetData>'.encode()


@pytest.fixture(scope="module")
def woart():
    return AssetData.from_source(WOART)


@pytest.fixture(scope="module")
def bmw():
    return AssetData.from_source(BMW)


@pytest.fixture(scope="module")
def bank49():
    return AssetData.from_source(BANK49)


@pytest.fixture(scope="module")
def gnmag():
    return AssetData.from_source(GNMAG)


class TestAutoLoan:

    def test_schema_and_metadata(self, woart):
        info = woart.info
        assert isinstance(info, AssetDataInfo)
        assert (info.schema, info.curated, info.row_count) == ('autoloan', True, 25)
        assert info.namespace == AUTOLOAN_NS
        assert info.contract_version == CONTRACT_VERSION
        assert info.reporting_period_start == date(2026, 8, 1)
        assert info.reporting_period_end == date(2026, 8, 31)
        assert info.unmapped_tags == ()
        assert info.coercion_failures == {}

    def test_every_schema_column_is_present_in_xsd_order(self, woart):
        expected = [column for column, _, _ in SCHEMAS['autoloan']['tables']['assets'].values()]
        assert list(woart.assets.columns) == expected

    def test_ground_truth_first_loan(self, woart):
        # <assetNumber>998989999995338439</assetNumber> in woart2022cex102aug26.xml
        loan = woart.assets.iloc[0]
        assert loan['asset_number'] == '998989999995338439'
        assert loan['obligor_credit_score'] == 760
        assert loan['original_loan_amount'] == 40241.75
        assert loan['original_loan_term'] == 78
        assert loan['original_interest_rate_percentage'] == 0.0324
        assert loan['origination_date'] == pd.Timestamp('2022-02-01')      # 02/2022
        assert loan['interest_paid_through_date'] == pd.Timestamp('2026-08-25')
        assert loan['obligor_geographic_location'] == 'FL'
        assert loan['vehicle_model_year'] == 2022
        assert loan['co_obligor_indicator'] is True or loan['co_obligor_indicator'] == True  # noqa: E712
        assert loan['reporting_period_actual_end_balance_amount'] == 12653.93

    def test_dtypes(self, woart):
        dtypes = woart.assets.dtypes
        assert dtypes['obligor_credit_score'] == 'Int64'
        assert dtypes['original_loan_amount'] == 'float64'
        assert dtypes['origination_date'] == 'datetime64[ns]'
        assert dtypes['reporting_period_beginning_date'] == 'datetime64[ns]'
        assert dtypes['co_obligor_indicator'] == 'boolean'
        assert dtypes['vehicle_type_code'] == pd.StringDtype("pyarrow")
        assert dtypes['obligor_geographic_location'] == pd.StringDtype("pyarrow")

    def test_code_meanings_come_from_the_xsd(self, woart):
        assert woart.code_meanings('vehicle_type_code')['3'] == 'SUV'
        with pytest.raises(KeyError, match="not a code column"):
            woart.code_meanings('obligor_credit_score')

    def test_summary(self, woart):
        summary = woart.summary()
        assert summary.num_assets == 25
        assert summary.top_makes == {'TOYOTA': 25}
        assert summary.total_original_amount == pytest.approx(woart.assets['original_loan_amount'].sum())

    def test_metadata_travels_with_the_frame(self, woart):
        assert woart.assets.attrs['absee']['schema'] == 'autoloan'


class TestAutoLease:

    def test_ground_truth_first_lease(self, bmw):
        assert (bmw.info.schema, bmw.info.row_count) == ('autolease', 25)
        assert bmw.info.reporting_period_start == date(2025, 10, 1)
        assert bmw.info.reporting_period_end == date(2025, 10, 31)
        lease = bmw.assets.iloc[0]
        assert lease['asset_number'] == '361929D918B654E80248'
        assert lease['lessee_credit_score'] == 792
        assert lease['acquisition_cost'] == 46002.46
        assert lease['lessee_geographic_location'] == 'CA'
        # paidThroughDate is MM-DD-YYYY; the old parser read it as MM/YYYY and lost it
        assert lease['paid_through_date'] == pd.Timestamp('2024-02-03')
        assert lease['zero_balance_effective_date'] == pd.Timestamp('2024-02-01')
        assert lease['zero_balance_code'] == '1'
        assert bmw.code_meanings('zero_balance_code')['1'] == 'Terminated'


class TestCMBS:

    def test_loans_and_properties(self, bank49):
        info = bank49.info
        assert (info.schema, info.curated) == ('cmbs', True)
        assert info.table_counts == {'assets': 37, 'property': 65}
        assert info.reporting_period_start == date(2026, 9, 12)
        assert info.reporting_period_end == date(2026, 10, 13)

    def test_ground_truth_first_loan_and_property(self, bank49):
        loan = bank49.assets.iloc[0]
        assert loan['asset_number'] == '1'
        assert loan['original_loan_amount'] == 92_250_000.0
        assert loan['report_period_end_actual_balance_amount'] == 90_888_267.42
        assert loan['maturity_date'] == pd.Timestamp('2035-03-11')
        assert loan['interest_only_indicator'] == False  # noqa: E712

        prop = bank49.properties.iloc[0]
        assert prop['asset_number'] == '1'
        assert prop['property_name'] == 'Marriott Dallas Las Colinas'
        assert prop['property_state'] == 'TX'
        assert prop['property_type_code'] == 'LO'
        assert prop['year_built_number'] == 1999
        assert bank49.code_meanings('property_type_code')['LO'] == 'Lodging'

    def test_summary(self, bank49):
        summary = bank49.summary()
        assert (summary.num_assets, summary.num_properties) == (37, 65)
        assert summary.property_types['MH'] == 26


class TestRawTier:
    """A schema without a curated spec keeps every tag, as filed, as strings."""

    def test_debt_securities_parse_raw(self, gnmag):
        info = gnmag.info
        assert (info.schema, info.curated, info.row_count) == ('debtsecurities', False, 2)
        assert info.contract_version is None
        assert info.reporting_period_start == date(2021, 1, 1)
        assert info.reporting_period_end == date(2021, 1, 4)
        assets = gnmag.assets
        assert assets.shape[1] == 49
        first = assets.iloc[0]
        assert first['assetNumber'] == '36179V4W7'
        assert first['originalSecurityAmount'] == '-50000000'
        assert first['securityTitleName'] == 'GinnieMaeIIPool'

    def test_summary_is_count_only(self, gnmag):
        summary = gnmag.summary()
        assert summary.num_assets == 2
        assert summary.total_original_amount is None


class TestSources:
    """One document, many byte sources: the result does not depend on how it arrived."""

    def test_submission_gz_stream_and_bytes_agree(self, gnmag, tmp_path):
        raw = GNMAG.read_bytes()
        gz = tmp_path / "0001213900-21-000188.nc.gz"
        gz.write_bytes(gzip.compress(raw))
        for source in (gz, str(gz), raw, io.BytesIO(raw), gzip.open(gz, 'rb')):
            data = AssetData.from_source(source)
            pd.testing.assert_frame_equal(data.assets, gnmag.assets)

    def test_markers_split_across_chunks(self, gnmag, monkeypatch):
        # 7-byte chunks split <TYPE>EX-102, <TEXT>, <XML> and </XML> mid-marker
        monkeypatch.setattr(asset_data_module, '_CHUNK_SIZE', 7)
        data = AssetData.from_source(io.BytesIO(GNMAG.read_bytes()))
        pd.testing.assert_frame_equal(data.assets, gnmag.assets)

    def test_xml_text(self, bank49):
        data = AssetData.from_xml(BANK49.read_text())
        assert data.info.table_counts == bank49.info.table_counts

    def test_rows_are_typed_in_blocks(self, monkeypatch, woart):
        # Typing every few rows and concatenating must equal typing once
        monkeypatch.setattr(asset_data_module, '_FLUSH_ROWS', 4)
        data = AssetData.from_source(WOART)
        pd.testing.assert_frame_equal(data.assets, woart.assets)


class TestValueRules:

    def test_repeated_tag_is_joined(self):
        data = AssetData.from_xml(_autoloan_xml(
            "<assetNumber>A1</assetNumber><zeroBalanceCode>1</zeroBalanceCode><zeroBalanceCode>3</zeroBalanceCode>"))
        assert data.assets.loc[0, 'zero_balance_code'] == '1|3'

    def test_unconvertible_value_is_counted_not_hidden(self):
        data = AssetData.from_xml(_autoloan_xml(
            "<assetNumber>A1</assetNumber><obligorCreditScore>NONE</obligorCreditScore>",
            "<assetNumber>A2</assetNumber><obligorCreditScore>701</obligorCreditScore>"))
        assert data.assets['obligor_credit_score'].tolist() == [pd.NA, 701]
        assert data.info.coercion_failures == {'obligor_credit_score': 1}

    def test_undeclared_tag_is_kept_and_listed(self):
        data = AssetData.from_xml(_autoloan_xml("<assetNumber>A1</assetNumber><filerExtraField>x</filerExtraField>"))
        assert data.assets.loc[0, 'filer_extra_field'] == 'x'
        assert data.info.unmapped_tags == ('filerExtraField',)

    def test_document_with_no_assets_is_empty_but_typed(self):
        data = AssetData.from_xml(f'<assetData xmlns="{AUTOLOAN_NS}"/>')
        assert len(data) == 0
        assert data.info.schema == 'autoloan'
        assert data.assets.dtypes['obligor_credit_score'] == 'Int64'


class TestErrors:
    """Input that is not ABS-EE asset data raises; it never comes back as an empty frame."""

    def test_xml_in_another_namespace(self):
        with pytest.raises(DataObjectError, match="not ABS-EE asset data"):
            AssetData.from_xml("<ownershipDocument><schemaVersion>X0508</schemaVersion></ownershipDocument>")

    def test_asset_data_without_a_namespace(self):
        with pytest.raises(DataObjectError, match="not ABS-EE asset data"):
            AssetData.from_xml("<assetData><assets><assetNumber>1</assetNumber></assets></assetData>")

    def test_malformed_xml(self):
        with pytest.raises(ParsingError, match="not well-formed"):
            AssetData.from_xml(f'<assetData xmlns="{AUTOLOAN_NS}"><assets><assetNumber>1</assets>')

    def test_submission_without_ex102(self):
        submission = GNMAG.read_bytes().replace(b'<TYPE>EX-102', b'<TYPE>EX-999')
        with pytest.raises(DataObjectError, match="no EX-102"):
            AssetData.from_source(submission)

    def test_empty_input(self):
        with pytest.raises(ParsingError, match="empty"):
            AssetData.from_source(b"")

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            AssetData.from_source(tmp_path / "nope.xml")

    def test_unsupported_source_type(self):
        with pytest.raises(TypeError, match="Cannot read ABS-EE"):
            AssetData.from_source(42)


class TestLegacyClasses:

    def test_auto_lease_asset_data_is_deprecated_and_fixed(self):
        from edgar.abs import AutoLeaseAssetData
        with pytest.warns(DeprecationWarning, match="AssetData"):
            legacy = AutoLeaseAssetData(BMW.read_text())
        row = legacy.assets.iloc[0]
        assert row['credit_score'] == 792
        assert row['paid_through_date'] == pd.Timestamp('2024-02-03')
        # these seven were always empty: their tags were not in the schema
        for column in ('scheduled_payment', 'actual_payment', 'paid_through_date', 'remaining_term_months',
                       'securitization_balance', 'ending_balance'):
            assert legacy.assets[column].notna().all(), column
        assert 'beginning_balance' not in legacy.assets.columns

    def test_cmbs_asset_data_reads_through_the_new_reader(self):
        from edgar.abs import CMBSAssetData
        cmbs = CMBSAssetData(BANK49.read_text())
        assert len(cmbs.loans) == 37
        assert len(cmbs.properties) == 65
        assert cmbs.loans.loc[0, 'original_amount'] == 92_250_000.0
        assert cmbs.properties.loc[0, 'loan_id'] == '1'
        assert cmbs.properties.loc[0, 'name'] == 'Marriott Dallas Las Colinas'
        assert cmbs.summary().num_properties == 65
