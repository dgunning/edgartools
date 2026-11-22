"""
Filing-fee exhibit values honour the inline-XBRL ``format`` transformation.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1681

``extract_filing_fees_xbrl`` returned each fact's display text. Under
``ixt:fixed-zero`` the displayed em dash means 0, so Welltower's totals came
back as ``'—'``; under ``ixt:booleantrue`` the displayed sentence means true,
so NextEra's final-prospectus flag came back False. A digit-free amount now
takes its transformed value, and the flag is read from the transformed value
as an ``xs:boolean``. Display text with digits is kept as before
(``'4,000,000,000.00'``), as are fee-rule labels.

Fixtures (real EX-FILING FEES exhibits, values read by hand):
- tests/fixtures/fee_tables/0001193125-25-066253_exhibit.html — Welltower Inc. fee exhibit,
  accession 0001193125-25-066253: ffd:TtlOfferingAmt and ffd:TtlFeeAmt
  are tagged ``format="ixt:fixed-zero"`` over ``&#8212;``.
- tests/offerings/fixtures/ex_filing_fees_0001193125-25-338333.html — NextEra Energy
  424B5, accession 0001193125-25-338333, filed 2025-12-31: ffd:FnlPrspctsFlg is
  tagged ``format="ixt:booleantrue"``; totals 4,000,000,000.00 and 552,400.00.
"""
from pathlib import Path

import pytest

from edgar.offerings.prospectus._424b_xbrl import extract_filing_fees_xbrl

TESTS = Path(__file__).parents[2]
WELLTOWER = TESTS / "fixtures" / "fee_tables" / "0001193125-25-066253_exhibit.html"
NEXTERA = TESTS / "offerings" / "fixtures" / "ex_filing_fees_0001193125-25-338333.html"


class _Attachment:
    document_type = "EX-FILING FEES"
    url = "local"

    def __init__(self, content: bytes):
        self._content = content

    def download(self):
        return self._content


class _Filing:
    def __init__(self, content: bytes):
        self.attachments = [_Attachment(content)]


def _fees(path: Path) -> dict:
    return extract_filing_fees_xbrl(_Filing(path.read_bytes()))


@pytest.mark.fast
def test_welltower_fixed_zero_totals_read_as_zero():
    fees = _fees(WELLTOWER)
    assert fees["total_offering_amount"] == "0"
    assert fees["total_fee_amount"] == "0"
    # fee-rule labels are display text under ixt:fixed-true, and stay so
    assert {row["fee_rule"] for row in fees["offering_rows"]} == {"457(r)"}


@pytest.mark.fast
def test_nextera_booleantrue_final_prospectus_flag():
    fees = _fees(NEXTERA)
    assert fees["is_final_prospectus"] is True
    assert fees["form_type"] == "S-3"
    assert fees["registration_file_number"] == "333-278184"
    assert fees["total_offering_amount"] == "4,000,000,000.00"
    assert fees["total_fee_amount"] == "552,400.00"
