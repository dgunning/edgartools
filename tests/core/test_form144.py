from pathlib import Path
from edgar.form144 import Form144
from edgar import Filing, find
import pytest

@pytest.mark.fast
def test_form_144_from_xml():
    form144_xml = Path('data/144/EDGAR Form 144 XML Samples/Sample 144.xml').read_text()
    form144 = Form144.parse_xml(form144_xml)
    print("------\nForm 144\n------")
    print(form144)

@pytest.mark.network
def test_form144_from_filing():
    filing = Filing(form='144/A', filing_date='2022-12-22', company='Assure Holdings Corp.', cik=1798270,
                    accession_no='0001886261-22-000004')
    form144 = Form144.from_filing(filing)
    print(form144)

@pytest.mark.network
def test_amount_sold_past_3months():
    filing = Filing(form='144', filing_date='2023-04-17', company='DELTA AIR LINES, INC.', cik=27904,
                    accession_no='0001959173-23-000600')
    form144: Form144 = Form144.from_filing(filing)
    print(form144.securities_sold_past_3_months)
    assert len(form144.securities_sold_past_3_months) == 1
    assert form144.securities_sold_past_3_months.iloc[0].amount_sold == 5000

@pytest.mark.network
def test_form144_with_no_xml():
    filing = Filing(company="Esperion Therapeutics, Inc.", cik=1434868, form='144', filing_date='2015-05-08', accession_no='0000903423-15-000301')
    xml = filing.xml()
    if not xml:
        form144 = filing.obj()
        assert form144 is None

@pytest.mark.network
def test_form144_with_multiple_securities_to_be_sold():
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144:Form144 = filing.obj()
    assert len(form144.securities_to_be_sold) == 8
    assert form144.broker_name == "Fidelity Brokerage Services LLC"
    assert form144.units_to_be_sold == 3000
    assert form144.exchange_name == "NYSE"
    assert form144.approx_sale_date == "04/18/2023"
    assert form144.security_class == 'Common'
    assert form144.market_value == 300000.0
    print(form144)



def test_correct_market_value_shown():
    filing = Filing(form='144', filing_date='2025-11-26', company='Fulgent Genetics, Inc.', cik=1674930, accession_no='0001193125-25-300994')
    form144:Form144 = filing.obj()
    print()
    print(form144)
    assert form144.market_value == 28431.45


def test_correct_aggregate_market_value():
    filing = Filing(form='144', filing_date='2025-11-26', company='IMPINJ INC', cik=1114995, accession_no='0002003074-25-000033')
    form144:Form144 = filing.obj()
    print()
    print(form144)
    print(form144.market_value)


# === New Tests for Comprehensive Form 144 Improvements ===

@pytest.mark.network
def test_form144_aggregation_properties():
    """Test the new aggregation properties work correctly."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # Test aggregation properties
    assert form144.total_units_to_be_sold == form144.units_to_be_sold  # Single security
    assert form144.total_market_value == form144.market_value
    assert form144.num_securities == 1
    assert form144.is_multi_security is False

    # Test securities to be sold aggregation
    assert form144.total_amount_acquired > 0
    assert len(form144.securities_to_be_sold) == 8  # Multiple acquisition entries


@pytest.mark.network
def test_form144_holder_properties():
    """Test the new holder access properties."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # Test securities_info holder
    assert form144.securities_info is not None
    assert not form144.securities_info.empty
    assert len(form144.securities_info) == 1
    assert form144.securities_info.total_units_to_be_sold == 3000
    assert form144.securities_info.total_market_value == 300000.0
    assert 'Common' in form144.securities_info.security_classes
    assert 'NYSE' in form144.securities_info.exchanges
    assert 'Fidelity Brokerage Services LLC' in form144.securities_info.brokers

    # Test securities_selling holder
    assert form144.securities_selling is not None
    assert not form144.securities_selling.empty
    assert len(form144.securities_selling) == 8
    assert form144.securities_selling.total_amount_acquired > 0


@pytest.mark.network
def test_form144_metadata_properties():
    """Test the new metadata properties."""
    # Test non-amendment
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()
    assert form144.is_amendment is False
    assert form144.filing_date is not None

    # Test amendment
    amendment_filing = Filing(form='144/A', filing_date='2022-12-22', company='Assure Holdings Corp.', cik=1798270,
                              accession_no='0001886261-22-000004')
    form144_amendment: Form144 = Form144.from_filing(amendment_filing)
    assert form144_amendment.is_amendment is True


@pytest.mark.network
def test_form144_get_summary():
    """Test the get_summary method."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    summary = form144.get_summary()
    assert 'person_selling' in summary
    assert 'issuer' in summary
    assert 'total_units_to_be_sold' in summary
    assert 'total_market_value' in summary
    assert 'num_securities' in summary
    assert summary['num_securities'] == 1
    assert summary['total_units_to_be_sold'] == 3000


@pytest.mark.network
def test_form144_to_dataframe():
    """Test the to_dataframe method."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    df = form144.to_dataframe()
    assert len(df) == 1  # One security
    assert 'person_selling' in df.columns
    assert 'issuer' in df.columns
    assert 'filing_date' in df.columns
    assert 'is_amendment' in df.columns
    assert 'security_class' in df.columns
    assert 'units_to_be_sold' in df.columns


@pytest.mark.network
def test_form144_type_annotations():
    """Test that properties return correct types."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # Test correct types
    assert isinstance(form144.units_to_be_sold, int)
    assert isinstance(form144.market_value, float)
    assert isinstance(form144.approx_sale_date, str)
    assert isinstance(form144.security_class, str)
    assert isinstance(form144.broker_name, str)
    assert isinstance(form144.exchange_name, str)

    # Test aggregation types
    assert isinstance(form144.total_units_to_be_sold, int)
    assert isinstance(form144.total_market_value, float)
    assert isinstance(form144.num_securities, int)
    assert isinstance(form144.is_multi_security, bool)


@pytest.mark.fast
def test_form144_holder_iteration():
    """Test that holders support iteration."""
    from edgar.form144 import SecuritiesInformationHolder
    import pandas as pd

    # Create test data
    data = pd.DataFrame([
        {'security_class': 'Common', 'units_to_be_sold': 1000, 'market_value': 50000.0,
         'units_outstanding': 1000000, 'approx_sale_date': '01/01/2024',
         'exchange_name': 'NYSE', 'broker_name': 'Test Broker'},
        {'security_class': 'Preferred', 'units_to_be_sold': 500, 'market_value': 25000.0,
         'units_outstanding': 500000, 'approx_sale_date': '01/02/2024',
         'exchange_name': 'NASDAQ', 'broker_name': 'Other Broker'}
    ])

    holder = SecuritiesInformationHolder(data)

    # Test iteration
    rows = list(holder)
    assert len(rows) == 2
    assert rows[0].security_class == 'Common'
    assert rows[1].security_class == 'Preferred'

    # Test indexing
    assert holder[0].security_class == 'Common'
    assert holder[1].security_class == 'Preferred'
    assert holder[2] is None  # Out of bounds
    assert holder[-1] is None  # Negative index

    # Test aggregation
    assert holder.total_units_to_be_sold == 1500
    assert holder.total_market_value == 75000.0
    assert holder.security_classes == ['Common', 'Preferred']
    assert set(holder.exchanges) == {'NYSE', 'NASDAQ'}


@pytest.mark.fast
def test_form144_empty_holder():
    """Test holder behavior with empty data."""
    from edgar.form144 import SecuritiesInformationHolder, SecuritiesToBeSoldHolder
    import pandas as pd

    # Test empty holder
    holder = SecuritiesInformationHolder(pd.DataFrame())
    assert holder.empty is True
    assert len(holder) == 0
    assert holder.total_units_to_be_sold == 0
    assert holder.total_market_value == 0.0
    assert holder.security_classes == []
    assert holder[0] is None
    assert list(holder) == []

    # Test None holder
    holder2 = SecuritiesToBeSoldHolder(None)
    assert holder2.empty is True
    assert holder2.total_amount_acquired == 0


# === Tests for Investor/Analyst Metrics ===

@pytest.mark.network
def test_form144_percent_of_holdings():
    """Test percentage of holdings calculation."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # Verify percent_of_holdings is calculated
    assert form144.percent_of_holdings >= 0
    # With 3000 units to sell and units_outstanding in the filing, should be a small percentage
    assert form144.percent_of_holdings < 1.0  # Very small % of a large company


@pytest.mark.network
def test_form144_avg_price_per_unit():
    """Test average price per unit calculation."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # market_value / units = avg price
    expected_avg = form144.market_value / form144.units_to_be_sold
    assert form144.avg_price_per_unit == expected_avg
    assert form144.avg_price_per_unit == 100.0  # $300,000 / 3,000 shares = $100


@pytest.mark.network
def test_form144_10b5_1_plan_detection():
    """Test 10b5-1 plan detection."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # Check if is_10b5_1_plan is a boolean
    assert isinstance(form144.is_10b5_1_plan, bool)

    # If there are plan adoption dates, it should be True
    if form144.notice_signature.plan_adoption_dates:
        # Filter out placeholder dates
        valid_dates = [d for d in form144.notice_signature.plan_adoption_dates if d != '01/01/1933']
        if valid_dates:
            assert form144.is_10b5_1_plan is True


@pytest.mark.network
def test_form144_cooling_off_compliance():
    """Test 90-day cooling off period compliance check."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # cooling_off_compliant should be None if no 10b5-1 plan or return bool
    if form144.days_since_plan_adoption is not None:
        assert isinstance(form144.cooling_off_compliant, bool)
        # If >= 90 days, should be compliant
        if form144.days_since_plan_adoption >= 90:
            assert form144.cooling_off_compliant is True
        else:
            assert form144.cooling_off_compliant is False


@pytest.mark.network
def test_form144_holding_period():
    """Test holding period calculation."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # Check holding period properties
    if form144.holding_period_days is not None:
        assert isinstance(form144.holding_period_days, int)
        assert form144.holding_period_days >= 0

    if form144.holding_period_years is not None:
        assert isinstance(form144.holding_period_years, float)
        assert form144.holding_period_years >= 0


@pytest.mark.network
def test_form144_anomaly_flags():
    """Test anomaly flag detection."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    # anomaly_flags should be a list
    assert isinstance(form144.anomaly_flags, list)

    # Check individual flags are booleans
    assert isinstance(form144.is_large_liquidation, bool)
    assert isinstance(form144.is_short_hold, bool)
    assert isinstance(form144.has_multiple_plans, bool)

    # For this filing, small % should not trigger LARGE_LIQUIDATION
    if form144.percent_of_holdings < 5.0:
        assert 'LARGE_LIQUIDATION' not in form144.anomaly_flags


@pytest.mark.network
def test_form144_to_analyst_summary():
    """Test the to_analyst_summary method."""
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144: Form144 = filing.obj()

    summary = form144.to_analyst_summary()

    # Check all required fields are present
    assert 'person_selling' in summary
    assert 'issuer' in summary
    assert 'percent_of_holdings' in summary
    assert 'avg_price_per_unit' in summary
    assert 'is_10b5_1_plan' in summary
    assert 'cooling_off_compliant' in summary
    assert 'holding_period_years' in summary
    assert 'anomaly_flags' in summary

    # Check values are correct types
    assert isinstance(summary['percent_of_holdings'], float)
    assert isinstance(summary['avg_price_per_unit'], float)
    assert isinstance(summary['anomaly_flags'], list)


@pytest.mark.fast
def test_form144_holder_derived_metrics():
    """Test derived metrics on SecuritiesInformationHolder."""
    from edgar.form144 import SecuritiesInformationHolder
    import pandas as pd

    # Create test data
    data = pd.DataFrame([
        {'security_class': 'Common', 'units_to_be_sold': 1000, 'market_value': 50000.0,
         'units_outstanding': 100000, 'approx_sale_date': '01/01/2024',
         'exchange_name': 'NYSE', 'broker_name': 'Test Broker'},
    ])

    holder = SecuritiesInformationHolder(data)

    # Test percent_of_outstanding: 1000 / 100000 * 100 = 1.0%
    assert holder.percent_of_outstanding == 1.0

    # Test avg_price_per_unit: 50000 / 1000 = 50.0
    assert holder.avg_price_per_unit == 50.0


@pytest.mark.fast
def test_form144_empty_holder_derived_metrics():
    """Test derived metrics return safe defaults on empty holder."""
    from edgar.form144 import SecuritiesInformationHolder
    import pandas as pd

    holder = SecuritiesInformationHolder(pd.DataFrame())

    assert holder.percent_of_outstanding == 0.0
    assert holder.avg_price_per_unit == 0.0