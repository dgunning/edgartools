"""
Regression test for edgartools-ugc2: Filing.obj_type property

Users calling filing.obj() don't know what type they'll get back.
The obj_type property tells them the class name without parsing the filing.
"""
from edgar import get_obj_info


def test_get_obj_info_returns_class_name_for_supported_forms():
    """get_obj_info returns (True, class_name, description) for supported forms."""
    supported = {
        '10-K': 'TenK',
        '10-Q': 'TenQ',
        '8-K': 'EightK',
        '4': 'Form4',
        '3': 'Form3',
        '5': 'Form5',
        '13F-HR': 'ThirteenF',
        'D': 'FormD',
        'C': 'FormC',
        'DEF 14A': 'ProxyStatement',
        'NPORT-P': 'FundReport',
    }
    for form, expected_class in supported.items():
        has_obj, class_name, description = get_obj_info(form)
        assert has_obj, f"Expected {form} to have obj"
        assert class_name == expected_class, f"{form}: expected {expected_class}, got {class_name}"
        assert description, f"{form}: description should not be empty"


def test_get_obj_info_handles_amendments():
    """Amendments (e.g. 10-K/A) should resolve to the same class as the base form."""
    has_obj, class_name, _ = get_obj_info('10-K/A')
    assert has_obj
    assert class_name == 'TenK'


def test_get_obj_info_returns_none_for_unsupported_forms():
    """Unsupported forms return (False, None, None)."""
    has_obj, class_name, description = get_obj_info('425')
    assert not has_obj
    assert class_name is None
    assert description is None


def test_filing_has_obj_type_property():
    """Filing class should have obj_type property."""
    from edgar._filings import Filing
    assert hasattr(Filing, 'obj_type')
