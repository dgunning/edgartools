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

from edgar import find
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


# ============================================================
# Deeper half of 2h4c: positively extract the cover agent.
#
# Beyond filtering garbage, recover the real distributor from the structured-note
# cover's "Selling Agent:" summary field, where it appears inline as a defined
# abbreviation ("Selling Agent:  BofAS", defined once as
# 'BofA Securities, Inc. ("BofAS")'). Before this the field was unparsed and the
# lead came back None, which is honest but uninformative; lifting it took the
# eval's lead_bookrunner coverage from 21% to 71%.
# ============================================================

def test_resolve_abbreviation_expands_defined_tag():
    """A defined abbreviation expands to its full name; an undefined one is kept."""
    from edgar.offerings._424b_cover import _resolve_abbreviation
    text = 'Calculation Agent: BofA Securities, Inc. (“BofAS”), an affiliate.'
    assert _resolve_abbreviation("BofAS", text) == "BofA Securities, Inc."
    # Already a full name (not a defined tag) — unchanged.
    assert _resolve_abbreviation("Barclays Capital Inc.", text) == "Barclays Capital Inc."


class TestCoverAgentExtraction:
    """Ground-truth lead_manager from real 424B2 structured-note covers."""

    def _lead(self, accession):
        from edgar.offerings.prospectus import Prospectus424B
        uw = Prospectus424B.from_filing(find(accession)).underwriting
        return uw.lead_manager if uw else None

    @pytest.mark.vcr
    def test_bofa_selling_agent_colon_field(self):
        """'Selling Agent:  BofAS' resolves to the full firm name."""
        assert self._lead("0001918704-25-005439") == "BofA Securities, Inc."

    @pytest.mark.vcr
    def test_bofa_selling_agents_plural_lead_is_first(self):
        """'Selling Agents  BofAS and UBS' — the lead is the first agent."""
        assert self._lead("0001213900-25-026186") == "BofA Securities, Inc."

    @pytest.mark.vcr
    def test_bofa_selling_agent_summary_box(self):
        """The summary-box field is recovered even when it sits past the cover window."""
        assert self._lead("0001918704-25-005486") == "BofA Securities, Inc."

    @pytest.mark.vcr
    def test_equity_underwriter_unaffected(self):
        """A standard equity 424B5 still surfaces its table-extracted lead."""
        assert self._lead("0001193125-25-068732") == "Barclays Capital Inc."

    @pytest.mark.vcr
    def test_prose_only_agent_stays_none(self):
        """Silence check: an agent mentioned only in lowercase prose is not guessed."""
        # 005479 references "selling agent in the case of BofAS" only in prose —
        # no labeled cover field — so we must not fabricate a lead.
        assert self._lead("0001918704-25-005479") is None


class TestAgencyDealAgentExtraction:
    """Lead agent from best-efforts / ATM equity covers named inline in prose.

    Registered directs and ATMs don't carry an underwriter allocation table; the
    agent appears in cover prose ("We have engaged <Firm> ... as the placement
    agent", "Sales Agreement ... with <Firm> relating to ..."). Recovering these
    took the eval's lead_bookrunner coverage from 71% to 93%.
    """

    def _lead(self, accession):
        from edgar.offerings.prospectus import Prospectus424B
        uw = Prospectus424B.from_filing(find(accession)).underwriting
        return uw.lead_manager if uw else None

    @pytest.mark.vcr
    def test_registered_direct_placement_agent(self):
        """'engaged Laidlaw & Company (UK) Ltd. ... the placement agent' — the
        country parenthetical is preserved in the recovered name."""
        assert self._lead("0001108205-25-000026") == "Laidlaw & Company (UK) Ltd."

    @pytest.mark.vcr
    def test_atm_sales_agent(self):
        """'Sales Agreement ... with Robert W. Baird & Co. Incorporated relating to'."""
        assert self._lead("0001628280-25-015699") == "Robert W. Baird & Co. Incorporated"

    @pytest.mark.vcr
    def test_placement_agent_defined_inline(self):
        """'engaged H.C. Wainwright & Co., LLC (the "placement agent")'."""
        assert self._lead("0001641172-25-001566") == "H.C. Wainwright & Co., LLC"

    @pytest.mark.vcr
    def test_cover_grid_wrapped_name_not_truncated(self):
        """edgartools-zzr4: a cover-grid firm name that wraps across lines.

        Calidi's cover renders the placement agent as 'Placement\\nAgent\\n\\n'
        'Ladenburg\\nThalmann' — the firm name wrapped onto two lines. The
        cover-role pattern grabbed only the first line, truncating the lead to a
        bare 'Ladenburg'. It must now stitch the wrapped continuation line.
        Found by the Tier C LLM-judge audit (a clean, plausible, but incomplete
        name that Tier A/B coverage/validity checks cannot catch).
        """
        assert self._lead("0001641172-25-001350") == "Ladenburg Thalmann"
