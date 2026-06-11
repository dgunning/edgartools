from edgar.xbrl.currency import normalize_currency_unit


def test_normalize_currency_unit_returns_clean_iso_code():
    assert normalize_currency_unit("USD") == "USD"


def test_normalize_currency_unit_extracts_iso4217_measure():
    assert normalize_currency_unit("iso4217:USD") == "USD"


def test_normalize_currency_unit_extracts_standard_unit_identifier():
    raw = "UNIT_STANDARD_HKD_MNUSOXGRF0O9R60JINVDUQ"

    assert normalize_currency_unit(raw) == "HKD"


def test_normalize_currency_unit_preserves_unknown_format():
    raw = "shares"

    assert normalize_currency_unit(raw) == raw
