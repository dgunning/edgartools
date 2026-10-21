"""
ReverseIndex stripped only the us-gaap and dei prefixes, so an SRT element
(srt:BankLoans, srt_PayablesToCustomers) never reached its mapping and got no
standard concept, while the same bare name found it. SRT and us-gaap share no
element name, so stripping the srt prefix cannot let a us-gaap concept answer
for an SRT one.

Charles Schwab's 10-Q for 2026-06-30 (0000316709-26-000031) reports
"Payables to brokerage clients" as srt:PayablesToCustomers: $116,341M at
2025-12-31, per SEC's frames API.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1446
"""

import pytest

from edgar.xbrl.standardization.reverse_index import get_reverse_index


@pytest.mark.fast
@pytest.mark.parametrize("tag, standard_concept", [
    ("srt:BankLoans", "ShortTermDebt"),
    ("srt_BankLoans", "ShortTermDebt"),
    ("srt:PayablesToCustomers", "OtherOperatingCurrentLiabilities"),
    ("srt_PayablesToCustomers", "OtherOperatingCurrentLiabilities"),
])
def test_srt_tag_reaches_its_mapping(tag, standard_concept):
    result = get_reverse_index().lookup(tag)
    assert result is not None
    assert result.standard_concepts[0] == standard_concept


@pytest.mark.fast
def test_unmapped_srt_tag_stays_unmapped():
    assert get_reverse_index().lookup("srt:PayablesToBrokerDealersAndClearingOrganizations") is None


@pytest.mark.network
def test_schwab_payables_to_customers_is_standardized():
    from edgar import find

    balance_sheet = find("0000316709-26-000031").xbrl().statements.balance_sheet().to_dataframe()
    rows = balance_sheet[(balance_sheet["concept"] == "srt_PayablesToCustomers") & (balance_sheet["dimension"] == False)]  # noqa: E712
    assert len(rows) == 1
    row = rows.iloc[0]
    assert row["standard_concept"] == "OtherOperatingCurrentLiabilities"
    december = [c for c in balance_sheet.columns if c.startswith("2025-12-31")]
    assert len(december) == 1
    assert row[december[0]] == 116_341_000_000
