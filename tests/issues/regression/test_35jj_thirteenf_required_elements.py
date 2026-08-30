"""Tranche 1 of the raw-ValueError conversion: the 13F primary document parser.

Bead: edgartools-35jj
GitHub Issue: https://github.com/dgunning/edgartools/issues/933

Seven raises in `thirteenf/parsers/primary_xml.py` — six of them the same
sentence with a different noun in it — became `ValidationError` through one
`_require_element()` helper.

The conversion is additive: `ValidationError` IS-A `ValueError`, so anything
that caught the old raise still catches this one. These tests pin that, because
it is the property the whole tranche rests on.
"""

import pytest

from edgar.exceptions import ValidationError
from edgar.thirteenf.parsers.primary_xml import parse_primary_document_xml

NS = 'xmlns="http://www.sec.gov/edgar/thirteenffiler"'

MINIMAL = f"""<edgarSubmission {NS}>
  <headerData><filerInfo><periodOfReport>03-31-2025</periodOfReport></filerInfo></headerData>
  <formData>
    <coverPage>
      <reportType>13F HOLDINGS REPORT</reportType>
      <filingManager><name>Acme Capital</name><address><city>Boston</city></address></filingManager>
    </coverPage>
    <signatureBlock><name>Jane Roe</name><title>CFO</title><city>Boston</city></signatureBlock>
  </formData>
</edgarSubmission>"""


def test_the_minimal_document_still_parses():
    # NOTE: <signatureBlock> is present because the parser dereferences it
    # without a None check (edgar/thirteenf/parsers/primary_xml.py, the
    # `signature_block_el` read) — a document without one raises AttributeError
    # from deep inside xmltools rather than saying what is missing. Tracked
    # separately as edgartools-35jj.1; out of scope for the 35jj tranche, which
    # converts raw ValueErrors rather than adding new required elements.
    """Guards the helper against being stricter than the raises it replaced."""
    doc = parse_primary_document_xml(MINIMAL)
    assert doc.cover_page.filing_manager.name == "Acme Capital"


@pytest.mark.parametrize("drop,missing", [
    ("<headerData><filerInfo><periodOfReport>03-31-2025</periodOfReport></filerInfo></headerData>", "headerData"),
    ("<filerInfo><periodOfReport>03-31-2025</periodOfReport></filerInfo>", "filerInfo"),
    ("<filingManager><name>Acme Capital</name><address><city>Boston</city></address></filingManager>", "filingManager"),
    ("<address><city>Boston</city></address>", "address"),
])
def test_a_missing_required_element_names_itself(drop, missing):
    with pytest.raises(ValidationError) as exc:
        parse_primary_document_xml(MINIMAL.replace(drop, ""))
    assert f"<{missing}>" in str(exc.value)
    assert exc.value.parameter == "primary_document_xml"


def test_missing_form_data_is_reported():
    stripped = MINIMAL[:MINIMAL.index("<formData>")] + "</edgarSubmission>"
    with pytest.raises(ValidationError) as exc:
        parse_primary_document_xml(stripped)
    assert "<formData>" in str(exc.value)


def test_the_wrong_root_element_is_reported():
    with pytest.raises(ValidationError) as exc:
        parse_primary_document_xml(f'<informationTable {NS}></informationTable>')
    assert exc.value.invalid_value == "informationTable"


@pytest.mark.parametrize("bad", [
    f'<informationTable {NS}></informationTable>',
    MINIMAL.replace("<headerData><filerInfo><periodOfReport>03-31-2025</periodOfReport></filerInfo></headerData>", ""),
])
def test_every_raise_is_still_catchable_as_a_valueerror(bad):
    """The additivity the tranche depends on."""
    with pytest.raises(ValueError):
        parse_primary_document_xml(bad)
