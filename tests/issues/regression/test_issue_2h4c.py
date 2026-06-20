"""
Regression test for Issue 2h4c: Deal.lead_bookrunner returns parser garbage.

Beads: edgartools-2h4c

Bug: On 424B2 structured-note / debt-shelf covers, the underwriting extractor
leaked non-name content into the underwriter name slot — whole legalese
paragraphs ("If an event of default occurs..."), note titles ("BofA Finance LLC
Accelerated Return Notes Linked to..."), table-of-contents blobs, pricing-term
labels ("Upside participation rate", "...Underlying:"), and lone bullets. Because
`lead_manager` returns `underwriters[0].name`, these surfaced verbatim as the
lead bookrunner — unpublishable to a consumer-facing surface.

Fix: validate every extracted name with `is_plausible_underwriter_name` before it
becomes an UnderwriterEntry, so garbage is filtered and a valid underwriter (if
any) surfaces as lead; otherwise the result is an honest None rather than junk.

Garbage examples verified against real 424B2/424B5 filings (2025 Q1).
"""
import pytest

from edgar.offerings._424b_tables import is_plausible_underwriter_name as ok


REAL_UNDERWRITER_NAMES = [
    "Barclays",
    "UBS Securities LLC",
    "J.P. Morgan Securities LLC",
    "BofA Securities, Inc.",
    "Morgan Stanley & Co. LLC",
    "Merrill Lynch, Pierce, Fenner & Smith Incorporated",
    "Wells Fargo Securities, LLC",
    "Citigroup Global Markets Inc.",
    "Goldman Sachs & Co. LLC",
    "RBC Capital Markets",
    "Barclays Capital Inc.",
    "Jefferies LLC",
    "Leerink Partners LLC",
    "ThinkEquity LLC",
    "Ladenburg",
    "ICBC Standard Bank plc",
]

GARBAGE = [
    # Note titles / entity + title (long).
    "BofA Finance LLC Accelerated Return Notes Linked to the iShares U.S. Aerospace and Defense",
    # Legalese paragraph.
    "If an event of default occurs and is continuing, the principal amount will be due",
    # Table-of-contents / multi-line blobs.
    "TABLE OF CONTENTS\nPricing Supplement\nPage\nSummary Information",
    "TABLE OF CONTENTS",
    "We have not authorized anyone to provide information",
    # Pricing-term fragments leaking from the cover term table.
    "Upside participation rate",
    "Notes due 2030",
    "Linked to the iShares",
    "Hypothetical Initial Value of the Worst-Performing Underlying:",
    # Single-word sentence fragments.
    "Our",
    "We",
    # Lone bullets / punctuation.
    "•",
    "- ",
    "",
]


@pytest.mark.parametrize("name", REAL_UNDERWRITER_NAMES)
def test_real_underwriter_names_accepted(name):
    assert ok(name) is True


@pytest.mark.parametrize("name", GARBAGE)
def test_garbage_rejected(name):
    assert ok(name) is False


def test_lead_manager_skips_garbage_and_promotes_valid_entry():
    """A valid underwriter after a garbage first entry should become the lead."""
    from edgar.offerings.prospectus import UnderwriterEntry, UnderwritingInfo
    # Simulate post-filter entries: garbage must never reach UnderwritingInfo,
    # so lead_manager is the first plausible name.
    names = ["Upside participation rate", "Morgan Stanley & Co. LLC", "Barclays"]
    entries = [UnderwriterEntry(name=n) for n in names if ok(n)]
    uw = UnderwritingInfo(underwriters=entries)
    assert uw.lead_manager == "Morgan Stanley & Co. LLC"


def test_all_garbage_yields_no_underwriters():
    """If every extracted name is garbage, there is no lead (honest None)."""
    from edgar.offerings.prospectus import UnderwriterEntry, UnderwritingInfo
    names = ["Upside participation rate", "TABLE OF CONTENTS", "Our"]
    entries = [UnderwriterEntry(name=n) for n in names if ok(n)]
    uw = UnderwritingInfo(underwriters=entries)
    assert uw.lead_manager is None
