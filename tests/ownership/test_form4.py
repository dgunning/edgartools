from edgar import *
from edgar.ownership import Form4
import pytest

@pytest.mark.network
def test_form4_with_derivatives():
    filing = Filing(company='VERTEX PHARMACEUTICALS INC / MA',
                    cik=875320,
                    form='4',
                    filing_date='2020-10-19',
                    accession_no='0001209191-20-055264')
    form4:Form4 = filing.obj()
    print()
    _repr = repr(form4)
    assert _repr
    activities = form4.get_transaction_activities()
    assert len(activities) == 1
    activity = activities[0]
    assert activity.transaction_type == 'derivative_purchase'
    assert activity.value == 43750.08036
    assert activity.shares == 196.356
    assert activity.security_title == 'Deferred Stock Units'
    assert activity.underlying_security == 'Common Stock'

    # Data
    df = form4.to_dataframe()
    print(df)

@pytest.mark.network
def test_create_form4_with_non_numeric_underlying():
    filing = Filing(form='4', filing_date='2024-10-02', company='Arnaboldi Nicole S', cik=1950032, accession_no='0001062993-24-017232')
    form4:Form4 = filing.obj()
    assert form4
    print()
    print(form4)

@pytest.mark.network
def test_detailed_transaction_counts():
    filing = Filing(form='4', filing_date='2025-03-07', company='DYADIC INTERNATIONAL INC', cik=1213809, accession_no='0001437749-25-006667')
    form4 = filing.obj()
    df = form4.to_dataframe(detailed=False)
    print()
    print(df.columns)
    assert df['Tax Shares'][0] == 27517

    assert not df.empty

@pytest.mark.network
def test_form4_owner_name_unreversed_individual():
    """Test that name_unreversed preserves unreversed name format for individuals"""
    # Use Apple Form 4 (recent valid filing)
    filing = Filing(company='APPLE INC', cik=320193, form='4',
                    filing_date='2025-10-17',
                    accession_no='0002050912-25-000008')
    form4 = filing.obj()
    owner = form4.reporting_owners[0]

    # Both properties should exist
    assert hasattr(owner, 'name')
    assert hasattr(owner, 'name_unreversed')

    # Unreversed name should be different from formatted name (for individuals)
    assert owner.name_unreversed != owner.name
    assert owner.name_unreversed  # Not empty

@pytest.mark.network
def test_form4_owner_name_unreversed_preserved():
    """Test that name_unreversed is preserved from XML without name reversal"""
    # Use a filing where we can verify the unreversed format
    filing = Filing(form='4', filing_date='2020-10-19',
                    company='VERTEX PHARMACEUTICALS INC / MA',
                    cik=875320, accession_no='0001209191-20-055264')
    form4 = filing.obj()
    owner = form4.reporting_owners[0]

    # Verify both names exist and are different for individuals
    assert owner.name == "Bruce I Sachs"  # Formatted (reversed)
    assert owner.name_unreversed == "SACHS BRUCE I"  # Unreversed from XML
    assert owner.name != owner.name_unreversed

@pytest.mark.network
def test_form4_multiple_owners_name_unreversed():
    """Test name_unreversed property exists for all owners"""
    filing = Filing(form='4', filing_date='2024-10-02',
                    company='Arnaboldi Nicole S', cik=1950032,
                    accession_no='0001062993-24-017232')
    form4 = filing.obj()

    for owner in form4.reporting_owners.owners:
        # All owners should have both properties
        assert hasattr(owner, 'name')
        assert hasattr(owner, 'name_unreversed')
        assert owner.name_unreversed  # Not empty

        # For individuals, names should differ (formatted vs unreversed)
        if not owner.is_company:
            # Name order should be different
            assert owner.name != owner.name_unreversed

@pytest.mark.network
def test_form4_backward_compatibility():
    """Test that existing code continues to work"""
    filing = Filing(company='APPLE INC', cik=320193, form='4',
                    filing_date='2025-10-17',
                    accession_no='0002050912-25-000008')
    form4 = filing.obj()

    # Existing property access should work unchanged
    owner = form4.reporting_owners[0]
    assert owner.name  # Still works
    assert owner.cik  # Still works
    assert owner.position  # Still works

    # Rich display should still work
    repr_str = repr(form4.reporting_owners)
    assert "Reporting Owner" in repr_str
